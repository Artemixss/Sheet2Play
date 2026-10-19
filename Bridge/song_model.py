"""Sheet2Play song model: a song's playable performance, read from the MusicXML it came from.

Phase 1 of `plans/2026-10-19-musicxml-songs.md`. A song keeps its MusicXML - HOMR's page files,
unmodified, or the imported score - and everything playback needs is derived from it here, so a
new interpretation never needs OMR again:

- **measures**, stitched across pages exactly as `musicxml_normalizer.combine_score_pages` does
  it, and re-laid by the timing fix (`timing_correction.lay_out`) when asked;
- the **play order**, with repeats, voltas and D.C./D.S. jumps expanded over the whole score.
  The bridge expands repeats one page at a time, so a repeat that crosses a page plays once;
- **notes** placed by measure and offset, ties merged as the normalizer merges them, grace notes
  kept and flagged (the normalizer drops them: their zero length fails its duration check), and
  articulations, slurs and ties attached from the XML;
- **pedals, dynamics, hairpins and tempo marks**, read straight from the XML. music21 10.5 drops
  MuseScore's pedal marks with an import warning, so it cannot be the source for them.

With the play order taken in sequence and grace notes left out, every note lands where the
shipped bridge puts it; `Research/omr/song_model_check.py` checks that on the cached
recognitions. This file is not one of the pinned bridge files and changes none of them: it calls
the pinned normalizer's own parsing and stitching functions, and the timing fix's own layout, so
the pinned runtimes keep their identity. Interpretations are keyed by `interpretation_key`
instead, which hashes this file and, when the fix is on, `timing_correction.py`.

    song_model.py --output DIR [--timing-correction] PAGE.musicxml [PAGE.musicxml ...]
    song_model.py --output DIR --score SCORE.mxl

writes `performance.json` (schema 3, described in `interpret`) and `score.musicxml` to DIR.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ElementTree
import zipfile
from bisect import bisect_right
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any, Sequence

import musicxml_normalizer as normalizer
import timing_correction

SCHEMA_VERSION = 3
OMR_PAGES = "omr-pages"
MUSICXML = "musicxml"
# An expansion this many times longer than the score is a jump loop in a broken score, not music.
MAX_EXPANSION_FACTOR = 16

exact = timing_correction.exact

_STEPS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
# Note-type lengths in quarter notes, for metronome beat units.
_BEAT_UNITS = {
    "maxima": Fraction(32), "long": Fraction(16), "breve": Fraction(8), "whole": Fraction(4),
    "half": Fraction(2), "quarter": Fraction(1), "eighth": Fraction(1, 2), "16th": Fraction(1, 4),
    "32nd": Fraction(1, 8), "64th": Fraction(1, 16), "128th": Fraction(1, 32),
}
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


class SongModelError(RuntimeError):
    pass


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def interpretation_key(timing_correction_enabled: bool) -> str:
    """Identity of an interpretation: this file, the timing fix when it is on, and the schema.

    A cached performance is valid only for the key it was written under, so editing this file or
    the timing fix re-interprets every song from its stored MusicXML, while OMR never re-runs.
    """
    digest = hashlib.sha256()
    digest.update(f"schema={SCHEMA_VERSION}\nsong_model={file_sha256(Path(__file__))}\n".encode())
    timing = file_sha256(Path(timing_correction.__file__)) if timing_correction_enabled else "off"
    digest.update(f"timing_correction={timing}\n".encode())
    return digest.hexdigest()


def read_document(path: Path) -> bytes:
    """The MusicXML text of a `.musicxml`/`.xml` file, or of the score inside an `.mxl` archive."""
    path = Path(path)
    if not zipfile.is_zipfile(path):
        return path.read_bytes()
    with zipfile.ZipFile(path) as archive:
        rootfile = None
        try:
            container = ElementTree.fromstring(archive.read("META-INF/container.xml"))
            for element in container.iter():
                if element.tag.rpartition("}")[2] == "rootfile" and element.get("full-path"):
                    rootfile = element.get("full-path")
                    break
        except KeyError:
            pass
        if rootfile is None:
            candidates = sorted(name for name in archive.namelist()
                                if not name.startswith("META-INF/") and name.lower().endswith((".xml", ".musicxml")))
            if not candidates:
                raise SongModelError(f"{path.name} holds no MusicXML score")
            rootfile = candidates[0]
        return archive.read(rootfile)


# --- The XML pass ------------------------------------------------------------------------------
# Directions, barlines and notations, read with their position in the measure. The position is
# the running time of the measure's notes, backups and forwards, the way a MusicXML reader plays
# them; a direction's <offset> moves only its drawing unless it says sound="yes".


@dataclass
class XmlNote:
    part: int
    staff: int
    measure: int
    onset: Fraction
    midi: int
    grace: bool
    tie_start: bool
    tie_stop: bool
    articulations: tuple[str, ...]
    slurs: tuple[str, ...]


@dataclass
class XmlMeasure:
    number: str
    repeat_forward: bool = False
    repeat_backward: int = 0  # play count of a closing repeat, 0 when there is none
    ending_start: tuple[int, ...] = ()
    ending_stop: bool = False
    jumps: dict[str, Any] = field(default_factory=dict)


@dataclass
class XmlMark:
    kind: str  # pedal, dynamics, wedge or tempo
    part: int
    staff: int
    measure: int
    onset: Fraction
    details: dict[str, Any]


@dataclass
class XmlPage:
    measures: list[XmlMeasure]
    notes: list[XmlNote]
    marks: list[XmlMark]
    part_names: list[str]
    counts: dict[str, int]
    measure_counts: list[int]


def _fraction(text: str | None) -> Fraction | None:
    try:
        return Fraction(text.strip()) if text and text.strip() else None
    except (ValueError, ZeroDivisionError):
        return None


def _quarters(text: str | None, divisions: Fraction) -> Fraction:
    # An unreadable duration counts as none: one bad number costs a position, not the score.
    value = _fraction(text)
    return value / divisions if value is not None else Fraction(0)


def _midi(note: ElementTree.Element) -> int | None:
    pitch = note.find("pitch")
    if pitch is None:
        return None
    step = (pitch.findtext("step") or "").strip().upper()
    if step not in _STEPS:
        return None
    try:
        octave = int((pitch.findtext("octave") or "").strip())
        alter = Fraction((pitch.findtext("alter") or "0").strip())
    except (ValueError, ZeroDivisionError):
        return None
    value = (octave + 1) * 12 + _STEPS[step] + alter
    return int(value) if value.denominator == 1 else None


def _notation_names(note: ElementTree.Element) -> tuple[tuple[str, ...], tuple[str, ...], bool, bool]:
    articulations: list[str] = []
    slurs: list[str] = []
    tie_start = any(tie.get("type") == "start" for tie in note.findall("tie"))
    tie_stop = any(tie.get("type") == "stop" for tie in note.findall("tie"))
    for notations in note.findall("notations"):
        for child in notations:
            tag = child.tag
            if tag in ("articulations", "ornaments"):
                articulations.extend(item.tag for item in child if item.tag != "accidental-mark")
            elif tag in ("fermata", "arpeggiate", "non-arpeggiate"):
                articulations.append(tag)
            elif tag == "slur" and child.get("type") in ("start", "stop"):
                slurs.append(child.get("type"))
            elif tag == "tied":
                tie_start |= child.get("type") == "start"
                tie_stop |= child.get("type") == "stop"
    return tuple(articulations), tuple(slurs), tie_start, tie_stop


def _staff(element: ElementTree.Element) -> int:
    try:
        return max(0, int((element.findtext("staff") or "1").strip()) - 1)
    except ValueError:
        return 0


def _dynamic_name(dynamics: ElementTree.Element) -> str:
    names = [(child.text or "").strip() if child.tag == "other-dynamics" else child.tag for child in dynamics]
    return "+".join(name for name in names if name)


def _tempo_details(metronome: ElementTree.Element) -> dict[str, Any] | None:
    units = [child for child in metronome if child.tag in ("beat-unit", "beat-unit-dot", "per-minute")]
    unit = metronome.findtext("beat-unit")
    per_minute = metronome.findtext("per-minute")
    if unit is None or per_minute is None:
        # A metric modulation (note = note) has no per-minute value of its own.
        return {"beat_unit": unit, "dots": 0, "per_minute": None, "quarter_bpm": None} if units else None
    dots = 0
    for child in metronome:
        if child.tag == "beat-unit-dot":
            dots += 1
        elif child.tag == "per-minute":
            break
    match = _NUMBER.search(per_minute)
    value = float(match.group(0)) if match else None
    length = _BEAT_UNITS.get(unit.strip())
    if value is None or length is None:
        quarter_bpm = None
    else:
        quarter_bpm = float(value * length * (2 - Fraction(1, 2 ** dots)))
    return {"beat_unit": unit.strip(), "dots": dots, "per_minute": value, "quarter_bpm": quarter_bpm}


def read_xml_page(document: bytes) -> XmlPage:
    root = ElementTree.fromstring(document)
    if root.tag != "score-partwise":
        raise SongModelError(f"Only score-partwise MusicXML is supported, not {root.tag}")
    part_names = [(score_part.findtext("part-name") or "").strip()
                  for score_part in root.findall("part-list/score-part")]
    counts = dict.fromkeys(("pedal_marks", "damper_sounds", "soft_sounds", "sostenuto_sounds",
                            "dynamics_marks", "dynamics_sounds", "wedges", "metronome_marks",
                            "tempo_sounds", "articulation_marks", "repeat_forward", "repeat_backward", "endings",
                            "jump_marks"), 0)
    measures: list[XmlMeasure] = []
    notes: list[XmlNote] = []
    marks: list[XmlMark] = []
    measure_counts: list[int] = []

    for part_index, part in enumerate(root.findall("part")):
        divisions = Fraction(1)
        part_measures = part.findall("measure")
        measure_counts.append(len(part_measures))
        for measure_index, measure in enumerate(part_measures):
            if part_index == 0:
                measures.append(XmlMeasure(number=measure.get("number", str(measure_index + 1))))
            # Repeat and volta marks belong to the barline, which every part repeats; jumps may be
            # written in any part. Measures past the first part's count have nowhere to go.
            bar = measures[min(measure_index, len(measures) - 1)] if measures else None
            cursor = Fraction(0)
            chord_onset = Fraction(0)

            def add_mark(kind: str, staff: int, onset: Fraction, details: dict[str, Any]) -> XmlMark:
                mark = XmlMark(kind, part_index, staff, measure_index, onset, details)
                marks.append(mark)
                return mark

            def read_sound(sound: ElementTree.Element, onset: Fraction, staff: int,
                           found: dict[str, XmlMark]) -> None:
                if sound.get("tempo") is not None:
                    counts["tempo_sounds"] += 1
                    try:
                        bpm = float(sound.get("tempo"))
                    except ValueError:
                        bpm = None
                    if "tempo" in found:
                        found["tempo"].details.update(quarter_bpm=bpm, source="metronome+sound")
                    else:
                        add_mark("tempo", staff, onset, {"beat_unit": None, "dots": 0, "per_minute": None,
                                                         "quarter_bpm": bpm, "source": "sound"})
                if sound.get("dynamics") is not None:
                    counts["dynamics_sounds"] += 1
                    try:
                        value = float(sound.get("dynamics"))
                    except ValueError:
                        value = None
                    if "dynamics" in found:
                        found["dynamics"].details["sound_dynamics"] = value
                    else:
                        add_mark("dynamics", staff, onset, {"mark": None, "sound_dynamics": value})
                for attribute, kind, counter in (("damper-pedal", "damper", "damper_sounds"),
                                                 ("soft-pedal", "soft", "soft_sounds"),
                                                 ("sostenuto-pedal", "sostenuto", "sostenuto_sounds")):
                    value = sound.get(attribute)
                    if value is None:
                        continue
                    counts[counter] += 1
                    if kind == "damper" and "pedal" in found:
                        found["pedal"].details["sound_value"] = value
                    else:
                        add_mark("pedal", staff, onset, {"type": kind, "source": "sound", "sound_value": value})
                for attribute in ("segno", "coda", "dacapo", "dalsegno", "fine", "tocoda"):
                    value = sound.get(attribute)
                    if value is not None and bar is not None:
                        counts["jump_marks"] += 1
                        bar.jumps[attribute] = value

            for child in measure:
                tag = child.tag
                if tag == "attributes":
                    value = _fraction(child.findtext("divisions"))
                    if value is not None and value > 0:
                        divisions = value
                elif tag == "note":
                    grace = child.find("grace") is not None
                    if child.find("chord") is not None:
                        onset = chord_onset
                    else:
                        onset = chord_onset = cursor
                        if not grace:
                            cursor += _quarters(child.findtext("duration"), divisions)
                    articulations, slurs, tie_start, tie_stop = _notation_names(child)
                    counts["articulation_marks"] += len(articulations)
                    for notations in child.findall("notations"):
                        for dynamics in notations.findall("dynamics"):
                            counts["dynamics_marks"] += 1
                            add_mark("dynamics", _staff(child), onset,
                                     {"mark": _dynamic_name(dynamics), "sound_dynamics": None})
                    midi = _midi(child)
                    if midi is not None:
                        notes.append(XmlNote(part_index, _staff(child), measure_index, onset, midi, grace,
                                             tie_start, tie_stop, articulations, slurs))
                elif tag == "backup":
                    cursor -= _quarters(child.findtext("duration"), divisions)
                elif tag == "forward":
                    cursor += _quarters(child.findtext("duration"), divisions)
                elif tag == "direction":
                    onset = cursor
                    offset = child.find("offset")
                    if offset is not None and offset.get("sound") == "yes":
                        onset += _quarters(offset.text, divisions)
                    staff = _staff(child)
                    found: dict[str, XmlMark] = {}
                    for direction_type in child.findall("direction-type"):
                        for item in direction_type:
                            if item.tag == "pedal":
                                counts["pedal_marks"] += 1
                                found["pedal"] = add_mark("pedal", staff, onset,
                                                          {"type": item.get("type"), "source": "mark"})
                            elif item.tag == "dynamics":
                                counts["dynamics_marks"] += 1
                                found["dynamics"] = add_mark("dynamics", staff, onset,
                                                             {"mark": _dynamic_name(item), "sound_dynamics": None})
                            elif item.tag == "wedge":
                                counts["wedges"] += 1
                                add_mark("wedge", staff, onset,
                                         {"type": item.get("type"), "number": item.get("number", "1")})
                            elif item.tag == "metronome":
                                counts["metronome_marks"] += 1
                                details = _tempo_details(item)
                                if details is not None:
                                    found["tempo"] = add_mark("tempo", staff, onset, {**details, "source": "metronome"})
                            elif item.tag in ("segno", "coda") and bar is not None:
                                bar.jumps.setdefault(f"{item.tag}_sign", True)
                    sound = child.find("sound")
                    if sound is not None:
                        read_sound(sound, onset, staff, found)
                elif tag == "sound":
                    read_sound(child, cursor, 0, {})
                elif tag == "barline" and part_index == 0 and bar is not None:
                    repeat = child.find("repeat")
                    if repeat is not None:
                        if repeat.get("direction") == "forward":
                            counts["repeat_forward"] += 1
                            bar.repeat_forward = True
                        elif repeat.get("direction") == "backward":
                            counts["repeat_backward"] += 1
                            try:
                                bar.repeat_backward = max(2, int(repeat.get("times", "2")))
                            except ValueError:
                                bar.repeat_backward = 2
                    ending = child.find("ending")
                    if ending is not None:
                        if ending.get("type") == "start":
                            counts["endings"] += 1
                            bar.ending_start = tuple(int(number) for number in re.findall(r"\d+", ending.get("number", "")))
                        elif ending.get("type") in ("stop", "discontinue"):
                            bar.ending_stop = True
    return XmlPage(measures, notes, marks, part_names, counts, measure_counts)


def independent_counts(document: bytes) -> dict[str, int]:
    """Feature counts by plain element search, as a check on `read_xml_page`'s measure walk."""
    root = ElementTree.fromstring(document)
    sounds = list(root.iter("sound"))
    parents = {child: parent for parent in root.iter() for child in parent}
    articulations = sum(len([item for item in element if item.tag != "accidental-mark"])
                        for tag in ("articulations", "ornaments") for element in root.iter(tag))
    # Fermatas may also sit on a barline; only those on notes are note marks.
    articulations += sum(1 for tag in ("fermata", "arpeggiate", "non-arpeggiate")
                         for element in root.iter(tag) if parents.get(element) is not None
                         and parents[element].tag == "notations")
    return {
        "pedal_marks": sum(1 for _ in root.iter("pedal")),
        "damper_sounds": sum(sound.get("damper-pedal") is not None for sound in sounds),
        "dynamics_marks": sum(1 for _ in root.iter("dynamics")),
        "dynamics_sounds": sum(sound.get("dynamics") is not None for sound in sounds),
        "wedges": sum(1 for _ in root.iter("wedge")),
        "metronome_marks": sum(1 for _ in root.iter("metronome")),
        "tempo_sounds": sum(sound.get("tempo") is not None for sound in sounds),
        "articulation_marks": articulations,
    }


# --- The music21 pass --------------------------------------------------------------------------
# Notes and measures read exactly as the pinned normalizer reads them, without expanding repeats:
# the play order does that, over the whole score.


@dataclass
class PageNote:
    pitch: str
    midi: int
    start: float  # within the page, as music21 places it
    duration: float  # 0 for a grace note
    part: int
    staff: int
    voice: str
    grace: bool
    slash: bool
    own_measure: int  # index among the measures of the note's own staff
    own_onset: Fraction  # onset within that measure
    measure: int = 0  # page-local index on the first part's measures
    articulations: tuple[str, ...] = ()
    slurs: tuple[str, ...] = ()
    tied: bool = False


@dataclass
class Page:
    name: str
    sha256: str
    notes: list[PageNote]
    starts: list[Fraction]  # first part's measure starts within the page
    bars: list[Fraction]  # bar length of each measure's time signature, 0 when there is none
    signatures: list[tuple[int, int] | None]
    numbers: list[str]
    decoded: float
    measure_beats: float
    staves: list[timing_correction.Staff]
    xml: XmlPage
    part_staves: dict[int, int]
    warnings: list[str]
    unjoined: int = 0


def _note_order(note: PageNote) -> tuple:
    return (note.start, note.part, note.voice, note.midi, note.staff, note.duration)


def read_page(path: Path, name: str | None = None) -> Page:
    from music21 import chord, converter, meter, note as note_module, stream

    path = Path(path)
    document = read_document(path)
    xml = read_xml_page(document)
    warnings: list[str] = []
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise SongModelError(f"MusicXML file cannot be accessed: {path}") from error
    score = normalizer._prepare_score(
        lambda: normalizer._parse_musicxml_with_repair(converter, resolved), str(resolved), expand_repeats=False)
    parts = tuple(score.parts) or (score,)
    coordinates = normalizer._musicxml_part_coordinates(parts)

    notes: list[PageNote] = []
    part_staves: dict[int, int] = {}
    staff_starts: dict[tuple[int, int], list[Fraction]] = {}
    for part in parts:
        part_index, staff_index = coordinates[id(part)]
        part_staves[part_index] = max(part_staves.get(part_index, 0), staff_index + 1)
        measures = list(part.getElementsByClass(stream.Measure))
        position = {id(measure): index for index, measure in enumerate(measures)}
        measure_starts = [exact(measure.getOffsetInHierarchy(part)) for measure in measures]
        staff_starts[(part_index, staff_index)] = measure_starts
        for element in part.recurse().notes:
            grace = bool(getattr(element.duration, "isGrace", False))
            try:
                start = normalizer._validate_number(float(element.getOffsetInHierarchy(part)), "note start beat")
                duration = 0.0 if grace else normalizer._validate_number(
                    float(element.duration.quarterLength), "note duration", allow_zero=False)
            except Exception as error:
                print(f"[WARNING] Skipping hallucinated or invalid note timing: {error}", file=sys.stderr)
                continue
            if isinstance(element, note_module.Note):
                pitches: Sequence[Any] = (element.pitch,)
            elif isinstance(element, chord.Chord):
                pitches = element.pitches
            else:
                continue
            container = element.getContextByClass(stream.Measure)
            own = position.get(id(container)) if container is not None else None
            if own is None:
                own = max(0, bisect_right(measure_starts, exact(start)) - 1) if measure_starts else 0
            own_onset = exact(start) - (measure_starts[own] if measure_starts else Fraction(0))
            voice = normalizer._voice_identifier(element, stream)
            for pitch in pitches:
                try:
                    pitch_name = str(getattr(pitch, "nameWithOctave", "")).strip()
                    if not pitch_name:
                        raise ValueError(f"Score element has an empty pitch: {element!r}")
                    midi_value = float(pitch.midi)
                    midi_pitch = int(round(midi_value))
                    if abs(midi_value - midi_pitch) > 1e-6:
                        raise ValueError(f"Microtonal pitch {pitch_name!r} cannot be represented in MIDI")
                    if midi_pitch < 0 or midi_pitch > 127:
                        raise ValueError(f"Pitch {pitch_name!r} is outside the MIDI range")
                except Exception as error:
                    print(f"[WARNING] Skipping note with invalid pitch: {error}", file=sys.stderr)
                    continue
                notes.append(PageNote(pitch_name, midi_pitch, start, duration, part_index, staff_index, voice,
                                      grace, bool(getattr(element.duration, "slash", False)), own, own_onset))

    first = parts[0]
    first_measures = list(first.getElementsByClass(stream.Measure))
    starts = [exact(measure.getOffsetInHierarchy(first)) for measure in first_measures]
    bars: list[Fraction] = []
    signatures: list[tuple[int, int] | None] = []
    for measure in first_measures:
        signature = measure.timeSignature or measure.getContextByClass(meter.TimeSignature)
        bars.append(exact(signature.barDuration.quarterLength) if signature else Fraction(0))
        signatures.append((int(signature.numerator), int(signature.denominator)) if signature else None)
    if not first_measures:
        starts, bars, signatures = [Fraction(0)], [Fraction(0)], [None]
        warnings.append(f"{name or path.name}: no measures; the page is read as one")
    numbers = [measure.number for measure in xml.measures]
    if len(numbers) != len(starts):
        warnings.append(f"{name or path.name}: the XML has {len(numbers)} measures and music21 {len(starts)}; "
                        "barline marks follow the XML order")
        numbers = [str(getattr(measure, "number", index + 1)) for index, measure in enumerate(first_measures)] \
            or ["1"]
    for item in notes:
        # The page's measure grid is the first part's, which is where the bridge's page
        # stitching and the timing fix take their measure starts from.
        item.measure = max(0, bisect_right(starts, exact(item.start)) - 1) if item.own_measure >= len(starts) \
            else item.own_measure
    unjoined = _attach_notations(notes, xml, staff_starts, warnings, name or path.name)
    notes.sort(key=_note_order)
    return Page(
        name=name or path.name, sha256=file_sha256(path), notes=notes, starts=starts,
        bars=bars, signatures=signatures, numbers=numbers,
        decoded=normalizer._validate_number(float(score.highestTime), "score duration"),
        measure_beats=normalizer._extract_measure_beats(score), staves=_timing_staves(score),
        xml=xml, part_staves=part_staves, warnings=warnings, unjoined=unjoined)


def _attach_notations(notes: list[PageNote], xml: XmlPage, staff_starts: dict[tuple[int, int], list[Fraction]],
                      warnings: list[str], name: str) -> int:
    """Give each music21 note the articulations, slurs and tie of the XML note it was read from.

    The join is on part, staff, measure, onset and pitch. A tied note music21 merged starts with
    its first XML note; marks written on a later note of the tie, such as a fermata on the note
    tied to, go to the merged note that sounds through it.
    """
    candidates: dict[tuple, list[XmlNote]] = {}
    for item in xml.notes:
        candidates.setdefault((item.part, item.staff, item.measure, item.onset, item.midi), []).append(item)
    for item in notes:
        options = candidates.get((item.part, item.staff, item.own_measure, item.own_onset, item.midi))
        if not options:
            continue
        chosen = next((option for option in options if option.grace == item.grace and not
                       (option.tie_stop and not option.tie_start)), None) or options[0]
        options.remove(chosen)
        item.articulations, item.slurs, item.tied = chosen.articulations, chosen.slurs, chosen.tie_start
    unjoined = 0
    for options in candidates.values():
        for option in options:
            if not (option.articulations or option.slurs):
                continue
            starts = staff_starts.get((option.part, option.staff))
            if option.tie_stop and starts and option.measure < len(starts):
                position = float(starts[option.measure] + option.onset)
                holder = next((item for item in notes if not item.grace and item.part == option.part
                               and item.staff == option.staff and item.midi == option.midi
                               and item.start - 1e-6 <= position < item.start + item.duration - 1e-6), None)
                if holder is not None:
                    holder.articulations += tuple(mark for mark in option.articulations
                                                  if mark not in holder.articulations)
                    continue
            unjoined += 1
    if unjoined:
        warnings.append(f"{name}: {unjoined} marked XML note(s) matched no played note; their marks are not played")
    return unjoined


def _timing_staves(score: Any) -> list[timing_correction.Staff]:
    """The page as `timing_correction.load_page` reads it, from this unexpanded parse."""
    from music21 import chord, meter, note, stream

    coordinates = normalizer._musicxml_part_coordinates(score.parts)
    staves = []
    for part in score.parts:
        part_index, staff_index = coordinates[id(part)]
        measures = list(part.getElementsByClass(stream.Measure))
        end = exact(part.highestTime)
        rows = []
        for index, measure in enumerate(measures):
            start = exact(measure.getOffsetInHierarchy(part))
            following = exact(measures[index + 1].getOffsetInHierarchy(part)) if index + 1 < len(measures) \
                else max(end, start + exact(measure.highestTime))
            signature = measure.timeSignature or measure.getContextByClass(meter.TimeSignature)
            row = timing_correction.PageMeasure(
                start, following - start, exact(signature.barDuration.quarterLength) if signature else Fraction(0),
                time_here=index > 0 and measure.timeSignature is not None)
            voices = {id(voice): position + 1 for position, voice in enumerate(measure.getElementsByClass(stream.Voice))}
            for element in measure.recurse().notesAndRests:
                if element.duration.isGrace or element.duration.quarterLength <= 0:
                    continue
                container = element.getContextByClass(stream.Voice)
                in_voice = container is not None and id(container) in voices
                pitches: tuple[int, ...] = ()
                if isinstance(element, (note.Note, chord.Chord)):
                    pitches = tuple(int(round(pitch.midi)) for pitch in element.pitches)
                original = exact(element.getOffsetInHierarchy(part))
                row.elements.append(timing_correction.Element(
                    offset=original - start, duration=exact(element.duration.quarterLength),
                    container=voices[id(container)] if in_voice else 0, pitches=pitches,
                    voice=normalizer._voice_identifier(element, stream), original=original))
            rows.append(row)
        staves.append(timing_correction.Staff(part_index, staff_index, rows))
    return staves


def _corrected(page: Page, first_page: bool) -> tuple[list[Fraction], dict[int, Fraction], Fraction]:
    """The timing fix's measure starts, note starts (by note position) and page length.

    Notes map to the layout exactly as `timing_correction.correct_page` maps the normalizer's
    notes, and like there any mismatch raises so the caller keeps the page as read.
    """
    layout = timing_correction.lay_out(page.staves, first_page)
    if len(layout.measures) != len(page.starts):
        raise ValueError(f"the layout has {len(layout.measures)} measures and the page {len(page.starts)}")
    targets: dict[tuple, list[Fraction]] = {}
    for (part, staff, pitch, voice, original, duration), starts in layout.starts.items():
        targets.setdefault(timing_correction._key(part, staff, pitch, voice, float(original), float(duration)),
                           []).extend(starts)
    moved: dict[int, Fraction] = {}
    for index, item in enumerate(page.notes):
        if item.grace:
            continue
        starts = targets.get(timing_correction._key(item.part, item.staff, item.midi, item.voice,
                                                    item.start, item.duration))
        if not starts:
            raise ValueError(f"note {item.pitch} at beat {item.start:g} has no measure")
        moved[index] = starts.pop(0)
    if any(targets.values()):
        raise ValueError("measures hold notes the normalizer did not report")
    return [new for _, new in layout.measures], moved, layout.length


# --- Play order --------------------------------------------------------------------------------


def _ending_end(measures: list[XmlMeasure], start: int) -> int:
    for index in range(start, len(measures)):
        if index > start and measures[index].ending_start:
            return index - 1
        if measures[index].ending_stop or measures[index].repeat_backward:
            return index
    return start


def _find_jump_target(measures: list[XmlMeasure], key: str, name: Any, after: int = -1) -> int | None:
    for index in range(after + 1, len(measures)):
        if measures[index].jumps.get(key) == name:
            return index
    for index in range(after + 1, len(measures)):
        if key in measures[index].jumps or measures[index].jumps.get(f"{key}_sign"):
            return index
    return None


def expand_play_order(measures: list[XmlMeasure], warnings: list[str]) -> list[int]:
    """Measure indices in performance order: repeats, voltas, then one D.C./D.S. jump.

    Follows the usual conventions (and MuseScore's defaults): a closing repeat with no opening one
    returns to the start of the section; a volta plays on the passes its numbers name; after a
    D.C. or D.S. jump repeats are not taken again, only the endings that do not repeat play, and
    Fine and To Coda apply.
    """
    count = len(measures)
    order: list[int] = []
    index = 0
    section_start = 0
    pass_number = 1
    returned = False
    after_jump = False
    repeats_done: dict[int, int] = {}
    while index < count:
        if len(order) > MAX_EXPANSION_FACTOR * count:
            warnings.append("the repeat structure does not terminate; repeats are played once")
            return list(range(count))
        measure = measures[index]
        if measure.repeat_forward and not returned:
            section_start, pass_number = index, 1
        returned = False
        if measure.ending_start:
            end = _ending_end(measures, index)
            repeats_back = any(measures[position].repeat_backward for position in range(index, end + 1))
            if (after_jump and repeats_back) or (not after_jump and pass_number not in measure.ending_start):
                index = end + 1
                continue
        order.append(index)
        if measure.repeat_backward and not after_jump:
            done = repeats_done.get(index, 0)
            if done < measure.repeat_backward - 1:
                repeats_done[index] = done + 1
                pass_number += 1
                index, returned = section_start, True
                continue
            repeats_done[index] = 0
            section_start, pass_number = index + 1, 1
        elif measure.ending_stop:
            section_start, pass_number = index + 1, 1
        jumps = measure.jumps
        if not after_jump and ("dacapo" in jumps or "dalsegno" in jumps):
            target = 0 if "dacapo" in jumps else _find_jump_target(measures, "segno", jumps["dalsegno"])
            if target is None:
                warnings.append(f"D.S. in measure {measure.number} has no segno; the jump is not taken")
            else:
                after_jump, index, returned = True, target, True
                continue
        if after_jump and "fine" in jumps:
            break
        if after_jump and "tocoda" in jumps:
            target = _find_jump_target(measures, "coda", jumps["tocoda"], after=index)
            if target is not None:
                index = target
                continue
            warnings.append(f"To Coda in measure {measure.number} has no coda; play continues")
        index += 1
    return order


# --- The performance ---------------------------------------------------------------------------


def _number(value: Fraction | float) -> float:
    return float(value)


def interpret(sources: Sequence[Path], *, kind: str = OMR_PAGES, timing_correction_enabled: bool = False,
              names: Sequence[str] | None = None) -> dict[str, Any]:
    """The performance document for a song's MusicXML (schema 3).

    Positions are quarter notes. A note, pedal, dynamic, hairpin or tempo mark sits at `offset`
    beats from the start of its `measure`; the measure starts at `start_beat` on the score read
    in order, and `length_beats` is the distance to the next measure's start, which page
    rounding can make shorter than the bar or, rarely, negative. Playback walks `play_order`,
    advancing by `length_beats` after each measure. `tempos` holds only marks the score prints or
    sounds; with none, the player chooses the tempo. Nothing here depends on playback settings.
    """
    if kind not in (OMR_PAGES, MUSICXML):
        raise ValueError(f"Unknown song kind {kind!r}")
    if not sources:
        raise SongModelError("A song needs at least one MusicXML file")
    if kind == MUSICXML and len(sources) != 1:
        raise SongModelError("An imported song is one MusicXML file")
    timing = timing_correction_enabled and kind == OMR_PAGES
    labels = list(names) if names is not None else [Path(source).name for source in sources]
    pages = [read_page(Path(source), label) for source, label in zip(sources, labels)]
    warnings = [warning for page in pages for warning in page.warnings]

    measures_out: list[dict[str, Any]] = []
    measure_marks: list[XmlMeasure] = []
    notes_out: list[dict[str, Any]] = []
    marks_out: list[tuple[XmlMark, int]] = []
    pages_out: list[dict[str, Any]] = []
    page_offset = 0.0
    for page_number, page in enumerate(pages):
        first_page = page_number == 0
        starts = page.starts
        note_starts: dict[int, Fraction] = {}
        total = page.decoded
        timing_state = "off"
        if timing:
            try:
                starts, note_starts, length = _corrected(page, first_page)
                total = float(length)
                timing_state = "corrected"
            except Exception as error:  # noqa: BLE001 - any failure keeps the page as read, as the app does
                warnings.append(f"{page.name}: timing fix not applied ({type(error).__name__}: {error})")
                starts, note_starts, timing_state = page.starts, {}, "kept"
        advance = normalizer._page_advance(normalizer.NormalizedScore(
            notes=(), tempo_changes=(), total_beats=total, part_count=1, staff_count=1,
            measure_beats=page.measure_beats), first_page)
        first_measure = len(measures_out)
        for local, start in enumerate(starts):
            following = page_offset + advance if local + 1 == len(starts) else page_offset + float(starts[local + 1])
            begin = page_offset + float(start)
            bar = page.bars[local] if local < len(page.bars) else Fraction(0)
            xml_measure = page.xml.measures[local] if local < len(page.xml.measures) else XmlMeasure(str(local + 1))
            measure_marks.append(xml_measure)
            signature = page.signatures[local] if local < len(page.signatures) else None
            measures_out.append({
                "index": first_measure + local,
                "page": page_number,
                "number": page.numbers[local] if local < len(page.numbers) else str(local + 1),
                "start_beat": begin,
                "length_beats": following - begin,
                "bar_beats": _number(bar),
                "time_signature": list(signature) if signature else None,
                "pickup": first_page and local == 0 and len(starts) > 1 and 0 < bar and starts[1] - starts[0] < bar,
                "repeat_start": xml_measure.repeat_forward,
                "repeat_end": xml_measure.repeat_backward,
                "ending": list(xml_measure.ending_start) if xml_measure.ending_start else None,
                "ending_stop": xml_measure.ending_stop,
                "jumps": {key: value for key, value in sorted(xml_measure.jumps.items())} or None,
            })
        for index, item in enumerate(page.notes):
            measure_start = starts[min(item.measure, len(starts) - 1)]
            if index in note_starts:
                onset = note_starts[index] - measure_start
            elif timing_state == "corrected":
                # Grace notes take no part in the layout and move with their measure.
                onset = exact(item.start) - page.starts[min(item.measure, len(page.starts) - 1)]
            else:
                onset = exact(item.start) - measure_start
            notes_out.append({
                "pitch": item.pitch, "midi": item.midi,
                "measure": first_measure + min(item.measure, len(starts) - 1),
                "offset": _number(onset), "duration": item.duration,
                "part": item.part, "staff": item.staff, "voice": item.voice,
                "grace": item.grace, "grace_slash": item.slash if item.grace else False,
                "tied": item.tied, "articulations": list(item.articulations), "slurs": list(item.slurs),
            })
        for mark in page.xml.marks:
            local = min(mark.measure, len(starts) - 1)
            if mark.measure >= len(starts):
                warnings.append(f"{page.name}: a {mark.kind} mark in XML measure {mark.measure + 1} is placed "
                                "in the last measure")
            marks_out.append((mark, first_measure + local))
        pages_out.append({"index": page_number, "name": page.name, "first_measure": first_measure,
                          "measures": len(starts), "start_beat": page_offset, "decoded_beats": page.decoded,
                          "advance_beats": advance, "timing": timing_state})
        page_offset += advance

    play_order = expand_play_order(measure_marks, warnings)
    pedals, dynamics, wedges, tempos = [], [], [], []
    open_wedges: dict[tuple, dict[str, Any]] = {}
    for mark, measure in marks_out:
        where = {"measure": measure, "offset": _number(mark.onset), "part": mark.part, "staff": mark.staff}
        if mark.kind == "pedal":
            pedals.append({**where, **mark.details})
        elif mark.kind == "dynamics":
            dynamics.append({**where, **mark.details})
        elif mark.kind == "tempo":
            tempos.append({**where, **mark.details})
        elif mark.kind == "wedge":
            key = (mark.part, mark.details["number"])
            if mark.details["type"] in ("crescendo", "diminuendo"):
                if key in open_wedges:
                    warnings.append(f"a hairpin in measure {measures_out[measure]['number']} starts before "
                                    "the previous one stops; the previous one is dropped")
                open_wedges[key] = {"kind": mark.details["type"], "part": mark.part, "staff": mark.staff,
                                    "start_measure": measure, "start_offset": _number(mark.onset)}
            elif mark.details["type"] == "stop":
                span = open_wedges.pop(key, None)
                if span is None:
                    continue
                wedges.append({**span, "end_measure": measure, "end_offset": _number(mark.onset)})
    if open_wedges:
        warnings.append(f"{len(open_wedges)} hairpin(s) never stop and are dropped")

    counts: dict[str, int] = {}
    for page in pages:
        for key, value in page.xml.counts.items():
            counts[key] = counts.get(key, 0) + value
    articulations: dict[str, int] = {}
    for item in notes_out:
        for name in item["articulations"]:
            articulations[name] = articulations.get(name, 0) + 1
    xml_articulations = sum(len(note.articulations) for page in pages for note in page.xml.notes)
    parts: dict[int, int] = {}
    for page in pages:
        for part, staves in page.part_staves.items():
            parts[part] = max(parts.get(part, 0), staves)
    part_names = pages[0].xml.part_names
    features = {
        **counts,
        "measures": len(measures_out),
        "played_measures": len(play_order),
        "notes": sum(not item["grace"] for item in notes_out),
        "grace_notes": sum(item["grace"] for item in notes_out),
        "tied_notes": sum(item["tied"] for item in notes_out),
        "slurs": sum(item["slurs"].count("start") for item in notes_out),
        "articulations": dict(sorted(articulations.items())),
        "pitched_xml_articulations": xml_articulations,
        "unjoined_marked_notes": sum(page.unjoined for page in pages),
        "played_articulations": sum(articulations.values()),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": kind,
        "sources": [{"name": page.name, "sha256": page.sha256} for page in pages],
        "timing_correction": timing,
        "parts": [{"index": part, "staves": parts[part], "name": part_names[part] if part < len(part_names) else ""}
                  for part in sorted(parts)],
        "pages": pages_out,
        "measures": measures_out,
        "play_order": play_order,
        "notes": notes_out,
        "pedals": pedals,
        "dynamics": dynamics,
        "wedges": wedges,
        "tempos": tempos,
        "features": features,
        "warnings": warnings,
    }


def performance_bytes(performance: dict[str, Any]) -> bytes:
    return (json.dumps(performance, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")


def sequential_notes(performance: dict[str, Any], *, include_grace: bool = False) -> list[tuple[float, int, float]]:
    """(start beat, MIDI pitch, duration) of every note, with the measures read in order."""
    starts = [measure["start_beat"] for measure in performance["measures"]]
    return [(starts[item["measure"]] + item["offset"], item["midi"], item["duration"])
            for item in performance["notes"] if include_grace or not item["grace"]]


def played_notes(performance: dict[str, Any], *, include_grace: bool = False) -> list[tuple[float, int, float]]:
    """(start beat, MIDI pitch, duration) of every note as the play order performs it."""
    by_measure: dict[int, list[dict[str, Any]]] = {}
    for item in performance["notes"]:
        if include_grace or not item["grace"]:
            by_measure.setdefault(item["measure"], []).append(item)
    measures = performance["measures"]
    played = []
    position = measures[0]["start_beat"] if measures else 0.0
    for index in performance["play_order"]:
        played.extend((position + item["offset"], item["midi"], item["duration"]) for item in by_measure.get(index, ()))
        position += measures[index]["length_beats"]
    return played


# --- The combined score ------------------------------------------------------------------------


def combined_musicxml(sources: Sequence[Path], kind: str = OMR_PAGES) -> bytes:
    """One MusicXML document for the song, for export and for opening in a score editor.

    An import is its own score. OMR pages are joined measure by measure: measures are numbered
    through, each page after the first starts with a page break, and a part a page does not have
    gets empty measures, which score readers fill with rests. Playback never reads this file: it is built from the pages, and
    page stitching rounds lengths in ways one document cannot record.
    """
    if kind == MUSICXML:
        return read_document(Path(sources[0]))
    roots = [ElementTree.fromstring(read_document(Path(source))) for source in sources]
    for root in roots:
        if root.tag != "score-partwise":
            raise SongModelError(f"Only score-partwise MusicXML is supported, not {root.tag}")
    widest = max(roots, key=lambda root: len(root.findall("part")))
    combined = ElementTree.Element("score-partwise", {"version": roots[0].get("version", "4.0")})
    for tag in ("work", "movement-number", "movement-title", "identification", "defaults"):
        element = roots[0].find(tag)
        if element is not None:
            combined.append(element)
    part_list = widest.find("part-list")
    combined.append(part_list if part_list is not None else ElementTree.Element("part-list"))
    part_ids = [score_part.get("id") for score_part in combined.find("part-list").findall("score-part")]
    part_count = max(len(root.findall("part")) for root in roots)
    while len(part_ids) < part_count:
        part_ids.append(f"P{len(part_ids) + 1}")
        ElementTree.SubElement(combined.find("part-list"), "score-part", {"id": part_ids[-1]})
    outputs = [ElementTree.SubElement(combined, "part", {"id": part_ids[index]}) for index in range(part_count)]
    # A part that a first page lacks would open with empty measures that declare nothing; score
    # readers need its divisions, staves and clefs from the start, so it borrows the attributes
    # its first real measure begins with.
    opening: dict[int, list[ElementTree.Element]] = {}
    for root in roots:
        for part_index, part in enumerate(root.findall("part")):
            first_measure = part.find("measure")
            if part_index not in opening and first_measure is not None:
                opening[part_index] = [copy.deepcopy(child) for child in first_measure if child.tag == "attributes"]
    number = 0
    for page_number, root in enumerate(roots):
        parts = root.findall("part")
        count = len(parts[0].findall("measure")) if parts else 0
        for part_index, output in enumerate(outputs):
            if part_index < len(parts):
                page_measures = parts[part_index].findall("measure")
            else:
                page_measures = _empty_measures(count)
                if len(output) == 0 and page_measures:
                    page_measures[0].extend(copy.deepcopy(element) for element in opening.get(part_index, []))
            for local, measure in enumerate(page_measures):
                measure.set("number", str(number + local + 1))
                if local == 0 and page_number > 0:
                    printed = measure.find("print")
                    if printed is None:
                        printed = ElementTree.Element("print")
                        measure.insert(0, printed)
                    printed.set("new-page", "yes")
                output.append(measure)
        number += count
    return ElementTree.tostring(combined, encoding="utf-8", xml_declaration=True)


def _empty_measures(count: int) -> list[ElementTree.Element]:
    # Left empty rather than filled with rests: MuseScore and music21 fill an empty measure with
    # a rest of the measure's own length. A rest sized from HOMR's <duration> values can disagree
    # with the written note types MuseScore measures by, and MuseScore then refuses the score.
    return [ElementTree.Element("measure") for _ in range(count)]


def _write_atomic(path: Path, data: bytes) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def write_song(sources: Sequence[Path], output: Path, *, kind: str = OMR_PAGES,
               timing_correction_enabled: bool = False, names: Sequence[str] | None = None) -> dict[str, Any]:
    performance = interpret(sources, kind=kind, timing_correction_enabled=timing_correction_enabled, names=names)
    output.mkdir(parents=True, exist_ok=True)
    _write_atomic(output / "score.musicxml", combined_musicxml(sources, kind))
    _write_atomic(output / "performance.json", performance_bytes(performance))
    return performance


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("pages", nargs="*", type=Path, help="HOMR page MusicXML files, in page order")
    parser.add_argument("--score", type=Path, help="an imported MusicXML or MXL score")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timing-correction", action="store_true")
    parser.add_argument("--resources", action="store_true", help="report time and peak memory on stdout")
    parsed = parser.parse_args(arguments)
    if bool(parsed.score) == bool(parsed.pages):
        parser.error("give either page files or --score")
    started = time.perf_counter()
    sources = [parsed.score] if parsed.score else parsed.pages
    kind = MUSICXML if parsed.score else OMR_PAGES
    performance = write_song(sources, parsed.output, kind=kind, timing_correction_enabled=parsed.timing_correction)
    summary: dict[str, Any] = {"output": str(parsed.output), "features": performance["features"],
                               "warnings": len(performance["warnings"])}
    if parsed.resources:
        summary["seconds"] = round(time.perf_counter() - started, 3)
        try:
            import psutil

            memory = psutil.Process().memory_info()
            summary["peak_working_set_bytes"] = getattr(memory, "peak_wset", None) or memory.rss
        except ImportError:
            summary["peak_working_set_bytes"] = None
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
