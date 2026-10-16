"""Exact, opt-in development tie normalization; shipped Bridge is unchanged."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from fractions import Fraction
from pathlib import Path
import xml.etree.ElementTree as ET

from .zeus_trace import Segment, xml_trace


@dataclass(frozen=True)
class TieResult:
    notes: tuple[Segment, ...]
    issues: tuple[dict, ...]
    measures: tuple[dict, ...]


def merge_ties(segments: list[Segment]) -> tuple[tuple[Segment, ...], tuple[dict, ...]]:
    output: list[Segment] = []
    active: dict[tuple, int] = {}
    issues: list[dict] = []
    counts = Counter((n.part, n.staff, n.voice, n.pitch, n.onset) for n in segments)
    for note in sorted(segments, key=lambda n: (n.onset, n.part, n.staff, n.voice, n.pitch)):
        if note.duration <= 0 or note.onset < 0:
            raise ValueError("Tie segments require positive duration and nonnegative onset")
        if set(note.ties) - {"start", "stop"} or len(set(note.ties)) != len(note.ties):
            raise ValueError("Unsupported or duplicate tie type")
        key = (note.part, note.staff, note.voice, note.pitch)
        duplicate = counts[(*key, note.onset)] > 1
        previous_index = active.get(key)
        if duplicate:
            active.pop(key, None)
            issues.append({"kind": "ambiguous_same_voice_unison", "note": note.json()})
        elif "stop" in note.ties and previous_index is not None:
            previous = output[previous_index]
            if previous.onset + previous.duration == note.onset:
                output[previous_index] = replace(previous, duration=previous.duration + note.duration,
                                                 ties=())
                if "start" not in note.ties:
                    active.pop(key)
                continue
        if "stop" in note.ties and not duplicate:
            issues.append({"kind": "unmatched_or_noncontiguous_stop", "note": note.json()})
        if key in active:
            issues.append({"kind": "interrupted_start", "note": output[active.pop(key)].json()})
        output.append(replace(note, ties=()))
        if "start" in note.ties and not duplicate:
            active[key] = len(output) - 1
    issues.extend({"kind": "open_start", "note": output[index].json()} for index in active.values())
    return tuple(output), tuple(issues)


def normalize_ties_exact(path: Path) -> TieResult:
    root = ET.parse(path).getroot()
    if root.findall(".//repeat"):
        raise ValueError("Repeat expansion is unsupported by the bounded literal-XML variant")
    segments, measures = xml_trace(path)
    notes, issues = merge_ties(segments)
    return TieResult(notes, issues, tuple(measures))


def verify_midi(notes: tuple[Segment, ...], destination: Path) -> dict:
    """Round-trip through music21's MIDI exporter and inspect native tick events."""
    from music21 import midi, note as music_note, stream
    score = stream.Score()
    groups: dict[tuple, list[Segment]] = defaultdict(list)
    for event in notes:
        groups[(event.part, event.staff, event.voice)].append(event)
    for index, events in enumerate(groups.values()):
        part = stream.Part(id=str(index))
        for event in events:
            item = music_note.Note(event.pitch)
            item.duration.quarterLength = event.duration
            part.insert(event.onset, item)
        score.insert(0, part)
    exported = midi.translate.streamToMidiFile(score)
    ticks = exported.ticksPerQuarterNote
    expected = Counter()
    for event in notes:
        start, length = event.onset * ticks, event.duration * ticks
        if start.denominator != 1 or length.denominator != 1:
            raise ValueError("Exact MIDI tick representation is unavailable for this timing")
        expected[(event.pitch, int(start), int(length))] += 1
    exported.open(str(destination), "wb")
    try:
        exported.write()
    finally:
        exported.close()
    imported = midi.MidiFile()
    imported.open(str(destination))
    try:
        imported.read()
    finally:
        imported.close()
    actual = Counter()
    for track in imported.tracks:
        tick = 0
        sounding: dict[tuple, list[int]] = defaultdict(list)
        for event in track.events:
            if isinstance(event, midi.DeltaTime):
                tick += event.time
            elif event.isNoteOn():
                sounding[(event.channel, event.pitch)].append(tick)
            elif event.isNoteOff():
                key = (event.channel, event.pitch)
                if not sounding[key]:
                    raise ValueError("MIDI contains an unmatched note-off")
                start = sounding[key].pop(0)
                actual[(event.pitch, start, tick - start)] += 1
        if any(sounding.values()):
            raise ValueError("MIDI contains an unterminated note")
    if actual != expected:
        raise ValueError(f"MIDI event preservation failed: missing={expected - actual}, extra={actual - expected}")
    return {"preserved": True, "notes": sum(actual.values()), "ticks_per_quarter": ticks,
            "scope": "pitch/onset/duration multiplicity; no audio-output or playback claim"}
