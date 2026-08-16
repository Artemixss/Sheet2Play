from __future__ import annotations

import contextlib
import json
import math
import os
import sys
import tempfile
from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

from .errors import ResearchError


@dataclass(frozen=True, slots=True)
class CanonicalEvent:
    kind: str
    measure: int
    staff: int
    voice: str
    onset: str
    duration: str
    pitch: str | None = None
    midi_pitch: int | None = None
    chord_id: str | None = None
    tie: str | None = None


@dataclass(frozen=True, slots=True)
class StructuralEvent:
    kind: str
    measure: int
    staff: int
    onset: str
    value: str


@dataclass(frozen=True, slots=True)
class CanonicalScore:
    events: tuple[CanonicalEvent, ...]
    structure: tuple[StructuralEvent, ...]

    def to_json(self) -> dict[str, Any]:
        return {
            "events": [asdict(event) for event in self.events],
            "structure": [asdict(event) for event in self.structure],
        }


def _fraction(value: Any) -> Fraction:
    if isinstance(value, Fraction):
        return value
    return Fraction(str(value)).limit_denominator(15360)


def _fraction_text(value: Any) -> str:
    fraction = _fraction(value)
    return f"{fraction.numerator}/{fraction.denominator}"


def _load_music21(*, register_converter: bool = False) -> tuple[Any, Any, Any, Any, Any, Any]:
    try:
        with contextlib.redirect_stdout(sys.stderr):
            from music21 import chord, converter, meter, note, stream, tempo
            if register_converter:
                import converter21

                converter21.register()
    except ImportError as error:
        raise ResearchError(
            "RUNTIME_MISSING",
            "symbolic_parse",
            "music21 and converter21 are required; run setup_research.ps1",
        ) from error
    return chord, converter, meter, note, stream, tempo


def parse_kern(kern_text: str) -> Any:
    _, converter, _, _, _, _ = _load_music21(register_converter=True)
    temporary_path: Path | None = None
    try:
        descriptor, raw_path = tempfile.mkstemp(suffix=".krn")
        os.close(descriptor)
        temporary_path = Path(raw_path)
        temporary_path.write_text(kern_text, encoding="utf-8")
        with contextlib.redirect_stdout(sys.stderr):
            parsed = converter.parse(str(temporary_path))
        converter_error = str(getattr(parsed, "c21_parse_err", "") or "").strip()
        if converter_error:
            raise ResearchError(
                "KERN_PARSE_FAILED",
                "symbolic_parse",
                f"converter21 rejected rhythmic or spine semantics: {converter_error}",
            )
        return parsed
    except Exception as error:
        if isinstance(error, ResearchError):
            raise
        raise ResearchError("KERN_PARSE_FAILED", "symbolic_parse", f"converter21 failed: {error}") from error
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _voice_id(element: Any, stream_module: Any) -> str:
    try:
        hierarchy = element.containerHierarchy()
    except Exception:
        hierarchy = ()
    for container in hierarchy:
        if isinstance(container, stream_module.Voice):
            if isinstance(container.id, str) and container.id.strip():
                return container.id.strip()
            parent = getattr(container, "activeSite", None)
            if parent is not None:
                voices = tuple(parent.getElementsByClass(stream_module.Voice))
                for index, voice in enumerate(voices, start=1):
                    if voice is container:
                        return f"voice-{index}"
            return "voice-1"
    return "voice-1"


def _measure_number(element: Any) -> int:
    try:
        measure = element.getContextByClass("Measure")
        return int(measure.number or 0) if measure is not None else 0
    except Exception:
        return 0


def extract_canonical_events(
    score: Any,
    *,
    validate_measures: bool = True,
    validate_ties: bool = True,
    validate_voice_overlap: bool = True,
) -> CanonicalScore:
    chord_module, _, meter_module, note_module, stream_module, tempo_module = _load_music21()
    parts = tuple(score.parts)
    if len(parts) != 2:
        raise ResearchError(
            "SEMANTIC_INVALID",
            "semantic_validation",
            f"Expected exactly two piano staves, found {len(parts)}",
        )
    events: list[CanonicalEvent] = []
    structure: list[StructuralEvent] = []
    chord_sequence = 0

    for staff, part in enumerate(parts):
        for measure in part.getElementsByClass(stream_module.Measure):
            if not validate_measures:
                break
            try:
                if measure.barDuration is not None and measure.quarterLength > measure.barDuration.quarterLength:
                    raise ResearchError(
                        "SEMANTIC_INVALID",
                        "semantic_validation",
                        f"Measure {measure.number} on staff {staff} exceeds its time signature",
                    )
            except ResearchError:
                raise
            except Exception:
                pass

        for element in part.recurse().notesAndRests:
            onset = _fraction(element.getOffsetInHierarchy(part))
            duration = _fraction(element.duration.quarterLength)
            if onset < 0:
                raise ResearchError(
                    "SEMANTIC_INVALID",
                    "semantic_validation",
                    f"Negative onset timing at staff {staff}, beat {onset}",
                )
            if duration <= 0:
                # Likely a grace note, skip it
                continue
            common = {
                "measure": _measure_number(element),
                "staff": staff,
                "voice": _voice_id(element, stream_module),
                "onset": _fraction_text(onset),
                "duration": _fraction_text(duration),
            }
            if isinstance(element, note_module.Rest):
                events.append(CanonicalEvent(kind="rest", **common))
                continue
            if isinstance(element, note_module.Note):
                notes = (element,)
                chord_id = None
            elif isinstance(element, chord_module.Chord):
                chord_sequence += 1
                chord_id = f"s{staff}-c{chord_sequence}"
                notes = tuple(element.notes)
            else:
                continue
            for member in notes:
                midi_value = float(member.pitch.midi)
                midi_pitch = round(midi_value)
                if not math.isclose(midi_value, midi_pitch, abs_tol=1e-6) or not 0 <= midi_pitch <= 127:
                    raise ResearchError(
                        "SEMANTIC_INVALID",
                        "semantic_validation",
                        f"Unrepresentable MIDI pitch {member.pitch.nameWithOctave}",
                    )
                tie_type = getattr(getattr(member, "tie", None), "type", None)
                events.append(
                    CanonicalEvent(
                        kind="note",
                        pitch=str(member.pitch.nameWithOctave),
                        midi_pitch=int(midi_pitch),
                        chord_id=chord_id,
                        tie=str(tie_type) if tie_type else None,
                        **common,
                    )
                )

        for element in part.recurse():
            onset = _fraction_text(element.getOffsetInHierarchy(part))
            measure_number = _measure_number(element)
            if isinstance(element, meter_module.TimeSignature):
                structure.append(StructuralEvent("meter", measure_number, staff, onset, element.ratioString))
            elif isinstance(element, tempo_module.MetronomeMark) and element.number is not None:
                structure.append(StructuralEvent("tempo", measure_number, staff, onset, str(float(element.number))))
            elif element.__class__.__name__ == "KeySignature":
                structure.append(StructuralEvent("key", measure_number, staff, onset, str(element.sharps)))
            elif element.__class__.__name__ == "Repeat":
                structure.append(StructuralEvent("repeat", measure_number, staff, onset, str(element.direction)))

    if validate_ties:
        _validate_ties(events)
    if validate_voice_overlap:
        _validate_voice_overlap(events)
    events.sort(key=lambda item: (_fraction(item.onset), item.staff, item.voice, item.midi_pitch or -1, item.kind))
    structure.sort(key=lambda item: (_fraction(item.onset), item.staff, item.kind, item.value))
    if not any(event.kind == "note" for event in events):
        raise ResearchError("SEMANTIC_INVALID", "semantic_validation", "Score contains no notes")
    return CanonicalScore(tuple(events), tuple(structure))


def _validate_ties(events: list[CanonicalEvent]) -> None:
    active: set[tuple[int, str, int]] = set()
    notes = sorted(
        (event for event in events if event.kind == "note"),
        key=lambda event: (_fraction(event.onset), event.staff, event.voice, event.midi_pitch or -1),
    )
    for event in notes:
        key = (event.staff, event.voice, int(event.midi_pitch or -1))
        if event.tie == "start":
            if key in active:
                raise ResearchError("SEMANTIC_INVALID", "semantic_validation", f"Nested tie for {key}")
            active.add(key)
        elif event.tie == "continue":
            if key not in active:
                raise ResearchError("SEMANTIC_INVALID", "semantic_validation", f"Tie continuation without start for {key}")
        elif event.tie == "stop":
            if key not in active:
                raise ResearchError("SEMANTIC_INVALID", "semantic_validation", f"Tie stop without start for {key}")
            active.remove(key)
    if active:
        raise ResearchError("SEMANTIC_INVALID", "semantic_validation", f"Unterminated ties: {sorted(active)}")


def _validate_voice_overlap(events: list[CanonicalEvent]) -> None:
    groups: dict[tuple[int, str], list[CanonicalEvent]] = {}
    for event in events:
        if event.kind == "note":
            groups.setdefault((event.staff, event.voice), []).append(event)
    for key, notes in groups.items():
        ordered = sorted(notes, key=lambda item: (_fraction(item.onset), _fraction(item.duration)))
        prior_end = Fraction(0)
        prior_chord: str | None = None
        prior_onset = Fraction(-1)
        for event in ordered:
            onset = _fraction(event.onset)
            end = onset + _fraction(event.duration)
            same_chord = event.chord_id is not None and event.chord_id == prior_chord and onset == prior_onset
            if onset < prior_end and not same_chord:
                raise ResearchError(
                    "SEMANTIC_INVALID",
                    "semantic_validation",
                    f"Overlapping events in staff/voice {key} at beat {onset}",
                )
            prior_end = max(prior_end, end)
            prior_chord = event.chord_id
            prior_onset = onset


def _tempo_changes(score: Any) -> list[tuple[float, float]]:
    changes: dict[float, float] = {}
    for mark in score.recurse().getElementsByClass("MetronomeMark"):
        if mark.number is None:
            continue
        beat = float(mark.getOffsetInHierarchy(score))
        bpm = float(mark.getQuarterBPM())
        if math.isfinite(beat) and beat >= 0 and math.isfinite(bpm) and bpm > 0:
            changes[beat] = bpm
    changes.setdefault(0.0, 120.0)
    ordered: list[tuple[float, float]] = []
    for item in sorted(changes.items()):
        if not ordered or not math.isclose(ordered[-1][1], item[1], abs_tol=1e-9):
            ordered.append(item)
    return ordered


def _seconds_at(beat: float, tempos: list[tuple[float, float]]) -> float:
    elapsed = 0.0
    current_beat, bpm = tempos[0]
    for next_beat, next_bpm in tempos[1:]:
        if beat <= next_beat:
            break
        elapsed += (next_beat - current_beat) * 60.0 / bpm
        current_beat, bpm = next_beat, next_bpm
    return elapsed + max(0.0, beat - current_beat) * 60.0 / bpm


def build_omr_result(
    score: Any,
    *,
    engine: str = "sheet2play",
    engine_revision: str = "transcoda-d4e2e687-research",
) -> tuple[dict[str, Any], Any]:
    try:
        expanded = score.expandRepeats()
        playback = expanded.stripTies(inPlace=False, matchByPitch=True)
    except Exception as error:
        raise ResearchError("NORMALIZATION_FAILED", "playback_normalization", str(error)) from error
    canonical = extract_canonical_events(playback, validate_measures=False, validate_ties=False, validate_voice_overlap=False)
    tempos = _tempo_changes(playback)
    notes: list[dict[str, Any]] = []
    for event in canonical.events:
        if event.kind != "note":
            continue
        start = float(_fraction(event.onset))
        duration = float(_fraction(event.duration))
        end = start + duration
        start_seconds = _seconds_at(start, tempos)
        notes.append(
            {
                "pitch": event.pitch,
                "midi_pitch": event.midi_pitch,
                "start_beat": start,
                "duration_beats": duration,
                "start_seconds": start_seconds,
                "duration_seconds": _seconds_at(end, tempos) - start_seconds,
                "part_index": 0,
                "staff_index": event.staff,
                "voice_identifier": event.voice,
            }
        )
    notes.sort(key=lambda item: (item["start_beat"], item["staff_index"], item["voice_identifier"], item["midi_pitch"]))
    result = {
        "schema_version": 2,
        "engine": engine,
        "engine_revision": engine_revision,
        "tempo_changes": [{"start_beat": beat, "bpm": bpm} for beat, bpm in tempos],
        "notes": notes,
    }
    return result, playback


def write_exports(
    score: Any,
    canonical: CanonicalScore,
    output_dir: Path,
    *,
    engine: str = "sheet2play",
    engine_revision: str = "transcoda-d4e2e687-research",
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    result, playback = build_omr_result(
        score,
        engine=engine,
        engine_revision=engine_revision,
    )
    paths = {
        "events": output_dir / "score.events.json",
        "omr_result": output_dir / "omr-result.json",
        "musicxml": output_dir / "score.musicxml",
        "midi": output_dir / "score.mid",
    }
    paths["events"].write_text(json.dumps(canonical.to_json(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    paths["omr_result"].write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        score.write("musicxml", fp=str(paths["musicxml"]))
        playback.write("midi", fp=str(paths["midi"]))
    except Exception as error:
        raise ResearchError("EXPORT_FAILED", "export", str(error)) from error
    if not paths["musicxml"].is_file() or not paths["midi"].is_file() or paths["midi"].stat().st_size < 14:
        raise ResearchError("EXPORT_FAILED", "export", "MusicXML or MIDI export is empty")
    _, converter, _, _, _, _ = _load_music21()
    try:
        with contextlib.redirect_stdout(sys.stderr):
            musicxml_round_trip = converter.parse(str(paths["musicxml"]))
            midi_round_trip = converter.parse(str(paths["midi"]))
        if not tuple(musicxml_round_trip.recurse().notes) or not tuple(midi_round_trip.recurse().notes):
            raise ValueError("round-trip score contains no notes")
    except Exception as error:
        raise ResearchError("EXPORT_FAILED", "round_trip_validation", str(error)) from error
    return paths
