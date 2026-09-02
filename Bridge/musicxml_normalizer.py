from __future__ import annotations

import bisect
import contextlib
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence


DEFAULT_TEMPO_BPM = 120.0
_PART_STAFF_PATTERN = re.compile(
    r"^(?P<part>.+?)[-_]Staff(?P<staff>\d+)$", re.IGNORECASE
)


class MusicXmlNormalizationError(RuntimeError):
    def __init__(self, message: str, *, stage: str = "normalization") -> None:
        super().__init__(message)
        self.stage = stage


@dataclass(frozen=True, slots=True)
class TempoChange:
    start_beat: float
    bpm: float


@dataclass(frozen=True, slots=True)
class RawMusicNote:
    pitch: str
    midi_pitch: int
    start_beat: float
    duration_beats: float
    part_index: int
    staff_index: int
    voice_identifier: str


@dataclass(frozen=True, slots=True)
class MusicNote:
    pitch: str
    midi_pitch: int
    start_beat: float
    duration_beats: float
    start_seconds: float
    duration_seconds: float
    part_index: int
    staff_index: int
    voice_identifier: str


@dataclass(frozen=True, slots=True)
class NormalizedScore:
    notes: tuple[RawMusicNote, ...]
    tempo_changes: tuple[TempoChange, ...]
    total_beats: float
    part_count: int
    staff_count: int


def _load_music21_types() -> tuple[Any, Any, Any, Any]:
    try:
        with contextlib.redirect_stdout(sys.stderr):
            from music21 import chord, converter, note, stream
    except ImportError as error:
        raise MusicXmlNormalizationError(
            "music21 is not installed for the bridge interpreter. "
            "Run the matching Bridge setup script.",
            stage="runtime",
        ) from error
    return chord, converter, note, stream


def _validate_number(value: float, name: str, *, allow_zero: bool = True) -> float:
    if not math.isfinite(value):
        raise MusicXmlNormalizationError(f"{name} must be finite; received {value!r}")
    minimum_is_valid = value >= 0 if allow_zero else value > 0
    if not minimum_is_valid:
        qualifier = "non-negative" if allow_zero else "positive"
        raise MusicXmlNormalizationError(
            f"{name} must be {qualifier}; received {value!r}"
        )
    return value


def _musicxml_part_coordinates(parts: Sequence[Any]) -> dict[int, tuple[int, int]]:
    coordinates: dict[int, tuple[int, int]] = {}
    logical_parts: dict[str, int] = {}
    next_part_index = 0

    for part in parts:
        identifier = str(getattr(part, "id", "") or "").strip()
        match = _PART_STAFF_PATTERN.match(identifier)
        if match:
            logical_key = match.group("part").casefold()
            if logical_key not in logical_parts:
                logical_parts[logical_key] = next_part_index
                next_part_index += 1
            part_index = logical_parts[logical_key]
            staff_index = max(0, int(match.group("staff")) - 1)
        else:
            part_index = next_part_index
            staff_index = 0
            next_part_index += 1
        coordinates[id(part)] = (part_index, staff_index)

    return coordinates


def _voice_identifier(element: Any, stream_type: Any) -> str:
    try:
        hierarchy = element.containerHierarchy()
    except Exception:
        hierarchy = ()

    for container in hierarchy:
        if isinstance(container, stream_type.Voice):
            identifier = str(getattr(container, "id", "") or "1").strip()
            return identifier or "1"
    return "1"


def _extract_tempo_changes(score: Any) -> tuple[TempoChange, ...]:
    changes: list[TempoChange] = []
    try:
        boundaries = score.metronomeMarkBoundaries()
    except Exception as error:
        raise MusicXmlNormalizationError(
            f"Could not extract score tempo changes: {error}", stage="tempo"
        ) from error

    for start, _, mark in boundaries:
        try:
            bpm_value = mark.getQuarterBPM()
        except Exception:
            bpm_value = None
        if bpm_value is None:
            continue
        start_beat = _validate_number(float(start), "tempo start beat")
        bpm = _validate_number(float(bpm_value), "tempo BPM", allow_zero=False)
        changes.append(TempoChange(start_beat=start_beat, bpm=bpm))

    return normalize_tempo_changes(changes)


def normalize_tempo_changes(
    changes: Iterable[TempoChange],
) -> tuple[TempoChange, ...]:
    by_beat: dict[float, float] = {}
    for change in changes:
        beat = _validate_number(float(change.start_beat), "tempo start beat")
        bpm = _validate_number(float(change.bpm), "tempo BPM", allow_zero=False)
        by_beat[beat] = bpm

    if 0.0 not in by_beat:
        by_beat[0.0] = DEFAULT_TEMPO_BPM

    normalized: list[TempoChange] = []
    for beat, bpm in sorted(by_beat.items()):
        if normalized and math.isclose(
            normalized[-1].bpm, bpm, rel_tol=0, abs_tol=1e-9
        ):
            continue
        normalized.append(TempoChange(start_beat=beat, bpm=bpm))
    return tuple(normalized)


# music21's clefFromString reads a clef as a letter followed by a line number - "G2", "F4".
# homr sometimes emits a clef that does not fit that shape; a TAB clef comes out as
# <sign>T</sign><line>A</line>, and music21 then calls int("A") and raises, losing the whole
# score over one symbol. Dropping the bad clef lets music21 fall back to its default, which
# costs a clef and saves the piece.
_PARSEABLE_CLEF = re.compile(r"^[A-Za-z][0-9]$")
_CLEF_ELEMENT = re.compile(r"<clef(?![A-Za-z])[^>]*>.*?</clef>", re.DOTALL)


def _drop_unparseable_clefs(document: str) -> tuple[str, int]:
    """Remove clef elements music21 cannot read. Returns the text and how many went."""
    removed = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal removed
        block = match.group(0)
        sign = re.search(r"<sign>([^<]*)</sign>", block)
        line = re.search(r"<line>([^<]*)</line>", block)
        combined = (sign.group(1) if sign else "") + (line.group(1) if line else "")
        if _PARSEABLE_CLEF.match(combined):
            return block
        removed += 1
        return ""

    return _CLEF_ELEMENT.sub(replace, document), removed


def _parse_musicxml_with_repair(converter: Any, path: Path) -> Any:
    """Parse MusicXML, retrying once without malformed clefs if music21 refuses it.

    The retry only runs after a real failure, so a document that parses today takes exactly
    the path it always did. This is the same bargain as the skipped notes and the repeat
    fallback: degrade the broken element rather than discard the score.
    """
    try:
        with contextlib.redirect_stdout(sys.stderr):
            return converter.parse(str(path))
    except Exception as original:
        try:
            document = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            raise original from None
        repaired, removed = _drop_unparseable_clefs(document)
        if not removed:
            raise original from None

        import os
        import tempfile

        # mkstemp hands back an open descriptor; on Windows leaving it open locks the file
        # and the write below fails. Close it before touching the path.
        descriptor, raw_path = tempfile.mkstemp(suffix=".musicxml")
        os.close(descriptor)
        temporary = Path(raw_path)
        try:
            temporary.write_text(repaired, encoding="utf-8")
            with contextlib.redirect_stdout(sys.stderr):
                score = converter.parse(str(temporary))
        except Exception:
            raise original from None
        finally:
            temporary.unlink(missing_ok=True)

        print(
            f"[WARNING] Dropped {removed} unreadable clef(s) from {path} to recover the "
            "score; affected staves fall back to a default clef",
            file=sys.stderr,
        )
        return score


def _prepare_score(
    parser: Callable[[], Any],
    source: str,
    *,
    expand_repeats: bool = True,
) -> Any:
    try:
        with contextlib.redirect_stdout(sys.stderr):
            parsed_score = parser()
    except Exception as error:
        raise MusicXmlNormalizationError(
            f"music21 could not parse {source}: {error}", stage="parse"
        ) from error

    if parsed_score is None:
        raise MusicXmlNormalizationError(
            f"music21 returned no score for {source}", stage="parse"
        )

    expanded_score = parsed_score
    if expand_repeats:
        try:
            expanded_score = parsed_score.expandRepeats()
        except Exception as error:
            # OMR output routinely contains unbalanced repeat barlines - a closing repeat with
            # no opening, or one spanning a page boundary - and music21 refuses to expand
            # those. Aborting the whole conversion over it loses a score that is otherwise
            # fine; playing the repeated section once is a far better outcome than playing
            # nothing. This follows the same principle as the skipped notes below and the
            # dropped notes in PlaybackSession: degrade the bad element, keep the score.
            #
            # Only reachable where expansion already failed, so scores that convert today are
            # unaffected. The cost is that repeats are played once instead of twice.
            print(
                f"[WARNING] Could not expand repeats in {source} ({error}); "
                "continuing without repeat expansion, so repeated sections play once",
                file=sys.stderr,
            )
            expanded_score = parsed_score

    try:
        score = expanded_score.stripTies(inPlace=False, matchByPitch=True)
    except Exception as error:
        raise MusicXmlNormalizationError(
            f"Could not merge ties in {source}: {error}", stage="tie_merging"
        ) from error

    if score is None:
        raise MusicXmlNormalizationError(
            f"Tie normalization returned no score for {source}", stage="tie_merging"
        )
    return score


def _extract_score(
    score: Any,
    source: str,
    coordinate_resolver: Callable[[Sequence[Any]], dict[int, tuple[int, int]]],
    *,
    skip_grace_notes: bool = False,
) -> NormalizedScore:
    chord_type, _, note_type, stream_type = _load_music21_types()
    parts = tuple(score.parts)
    if not parts:
        parts = (score,)
    coordinates = coordinate_resolver(parts)
    extracted_notes: list[RawMusicNote] = []

    for part in parts:
        part_index, staff_index = coordinates[id(part)]
        try:
            elements = tuple(part.recurse().notes)
        except Exception as error:
            raise MusicXmlNormalizationError(
                f"Could not traverse notes in {source}: {error}", stage="note_traversal"
            ) from error

        for element in elements:
            if skip_grace_notes and bool(getattr(element.duration, "isGrace", False)):
                continue
            try:
                start_beat = _validate_number(
                    float(element.getOffsetInHierarchy(part)), "note start beat"
                )
                duration_beats = _validate_number(
                    float(element.duration.quarterLength),
                    "note duration",
                    allow_zero=False,
                )
            except Exception as error:
                print(f"[WARNING] Skipping hallucinated or invalid note timing: {error}", file=sys.stderr)
                continue

            if isinstance(element, note_type.Note):
                pitches: Iterable[Any] = (element.pitch,)
            elif isinstance(element, chord_type.Chord):
                pitches = element.pitches
            else:
                continue

            voice_identifier = _voice_identifier(element, stream_type)
            for pitch in pitches:
                try:
                    pitch_name = str(getattr(pitch, "nameWithOctave", "")).strip()
                    if not pitch_name:
                        raise ValueError(f"Score element has an empty pitch: {element!r}")
                        
                    midi_value = float(pitch.midi)
                    midi_pitch = int(round(midi_value))
                    
                    if not math.isclose(midi_value, midi_pitch, abs_tol=1e-6):
                        raise ValueError(f"Microtonal pitch {pitch_name!r} cannot be represented in MIDI")
                    
                    if midi_pitch < 0 or midi_pitch > 127:
                        raise ValueError(f"Pitch {pitch_name!r} is outside the MIDI range")
                except Exception as error:
                    print(f"[WARNING] Skipping note with invalid pitch: {error}", file=sys.stderr)
                    continue
                extracted_notes.append(
                    RawMusicNote(
                        pitch=str(pitch_name),
                        midi_pitch=int(round(midi_value)),
                        start_beat=start_beat,
                        duration_beats=duration_beats,
                        part_index=part_index,
                        staff_index=staff_index,
                        voice_identifier=voice_identifier,
                    )
                )

    extracted_notes.sort(
        key=lambda item: (
            item.start_beat,
            item.part_index,
            item.voice_identifier,
            item.midi_pitch,
            item.staff_index,
            item.duration_beats,
        )
    )
    try:
        total_beats = _validate_number(float(score.highestTime), "score duration")
    except Exception as error:
        if isinstance(error, MusicXmlNormalizationError):
            raise
        raise MusicXmlNormalizationError(
            f"Could not determine duration for {source}: {error}", stage="timing"
        ) from error

    part_count = len({coordinate[0] for coordinate in coordinates.values()})
    staff_count = len(set(coordinates.values()))
    return NormalizedScore(
        notes=tuple(extracted_notes),
        tempo_changes=_extract_tempo_changes(score),
        total_beats=total_beats,
        part_count=part_count,
        staff_count=staff_count,
    )


def normalize_musicxml(
    musicxml_path: Path,
    *,
    expand_repeats: bool = True,
    skip_grace_notes: bool = False,
) -> NormalizedScore:
    _, converter, _, _ = _load_music21_types()
    try:
        resolved_path = musicxml_path.resolve(strict=True)
    except OSError as error:
        raise MusicXmlNormalizationError(
            f"MusicXML file does not exist or cannot be accessed: {musicxml_path}",
            stage="input",
        ) from error

    score = _prepare_score(
        lambda: _parse_musicxml_with_repair(converter, resolved_path),
        str(resolved_path),
        expand_repeats=expand_repeats,
    )
    return _extract_score(
        score,
        str(resolved_path),
        _musicxml_part_coordinates,
        skip_grace_notes=skip_grace_notes,
    )


def combine_score_pages(pages: Iterable[NormalizedScore]) -> NormalizedScore:
    notes: list[RawMusicNote] = []
    tempos: list[TempoChange] = []
    page_offset = 0.0
    part_count = 0
    staff_count = 0

    for page in pages:
        notes.extend(
            RawMusicNote(
                pitch=note.pitch,
                midi_pitch=note.midi_pitch,
                start_beat=note.start_beat + page_offset,
                duration_beats=note.duration_beats,
                part_index=note.part_index,
                staff_index=note.staff_index,
                voice_identifier=note.voice_identifier,
            )
            for note in page.notes
        )
        tempos.extend(
            TempoChange(start_beat=change.start_beat + page_offset, bpm=change.bpm)
            for change in page.tempo_changes
        )
        page_offset += page.total_beats
        part_count = max(part_count, page.part_count)
        staff_count = max(staff_count, page.staff_count)

    notes.sort(
        key=lambda item: (
            item.start_beat,
            item.part_index,
            item.voice_identifier,
            item.midi_pitch,
            item.staff_index,
            item.duration_beats,
        )
    )
    return NormalizedScore(
        notes=tuple(notes),
        tempo_changes=normalize_tempo_changes(tempos),
        total_beats=page_offset,
        part_count=part_count,
        staff_count=staff_count,
    )


class TempoTimeline:
    def __init__(self, changes: Sequence[TempoChange]) -> None:
        normalized = normalize_tempo_changes(changes)
        self._beats = tuple(change.start_beat for change in normalized)
        self._bpms = tuple(change.bpm for change in normalized)
        cumulative_seconds: list[float] = [0.0]
        for index in range(1, len(normalized)):
            elapsed_beats = self._beats[index] - self._beats[index - 1]
            cumulative_seconds.append(
                cumulative_seconds[-1]
                + elapsed_beats * 60.0 / self._bpms[index - 1]
            )
        self._seconds = tuple(cumulative_seconds)

    def seconds_at(self, beat: float) -> float:
        validated_beat = _validate_number(float(beat), "beat position")
        index = bisect.bisect_right(self._beats, validated_beat) - 1
        return self._seconds[index] + (
            (validated_beat - self._beats[index]) * 60.0 / self._bpms[index]
        )


def add_seconds(score: NormalizedScore) -> tuple[MusicNote, ...]:
    timeline = TempoTimeline(score.tempo_changes)
    notes: list[MusicNote] = []
    for note in score.notes:
        start_seconds = timeline.seconds_at(note.start_beat)
        end_seconds = timeline.seconds_at(note.start_beat + note.duration_beats)
        notes.append(
            MusicNote(
                pitch=note.pitch,
                midi_pitch=note.midi_pitch,
                start_beat=note.start_beat,
                duration_beats=note.duration_beats,
                start_seconds=start_seconds,
                duration_seconds=max(0.0, end_seconds - start_seconds),
                part_index=note.part_index,
                staff_index=note.staff_index,
                voice_identifier=note.voice_identifier,
            )
        )
    return tuple(notes)
