"""Assemble frozen SMB region truth into complete-page sounding note events."""
from __future__ import annotations

import hashlib
import json
import contextlib
import copy
import io
import sys
import warnings
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import Any

from .adapter_contract import portable_path, sha256_file
from .events import parse_kern


def _fraction(value: Any) -> Fraction:
    return Fraction(str(value)).limit_denominator(4096)


def _raw_note_counter(score: Any) -> Counter[tuple[int, Fraction, Fraction]]:
    from music21 import chord, note

    counts: Counter[tuple[int, Fraction, Fraction]] = Counter()
    sounding = score.stripTies(inPlace=False, matchByPitch=True)
    for part in sounding.parts:
        for element in part.recurse().notes:
            onset = _fraction(element.getOffsetInHierarchy(part))
            duration = _fraction(element.duration.quarterLength)
            if duration <= 0:
                continue
            members = element.notes if isinstance(element, chord.Chord) else (element,)
            for member in members:
                if isinstance(member, note.Note):
                    counts[(int(round(member.pitch.midi)), onset, duration)] += 1
    return counts


def _insert_rests(container: Any, start: Fraction, length: Fraction) -> None:
    from music21 import duration, note

    if length <= 0:
        return
    offset = start
    components = duration.Duration(float(length)).components
    if not components or sum((_fraction(item.quarterLength) for item in components), Fraction(0)) != length:
        raise ValueError(f"Cannot notate rest duration {length}")
    for component in components:
        component_length = _fraction(component.quarterLength)
        container.insert(offset, note.Rest(quarterLength=component_length))
        offset += component_length


def _rest_measure(number: int, length: Fraction, template: Any) -> Any:
    from music21 import stream

    if length <= 0:
        raise ValueError("A missing staff measure must have positive length")
    result = stream.Measure(number=number)
    result.paddingLeft = template.paddingLeft
    result.paddingRight = template.paddingRight
    if template.timeSignature is not None:
        result.insert(0, copy.deepcopy(template.timeSignature))
    _insert_rests(result, Fraction(0), length)
    if _fraction(result.quarterLength) < _fraction(result.barDuration.quarterLength):
        result.padAsAnacrusis()
    return result


def _remove_redundant_rests(measure: Any) -> None:
    from music21 import note, stream

    for container in (measure, *measure.getElementsByClass(stream.Voice)):
        rests = list(container.getElementsByClass(note.Rest))
        intervals = [(_fraction(rest.offset), _fraction(rest.offset + rest.duration.quarterLength))
                     for rest in rests]
        for index, rest in enumerate(rests):
            start, end = intervals[index]
            if any((other_start <= start and end <= other_end
                    and (other_start < start or end < other_end or other_index < index))
                   for other_index, (other_start, other_end) in enumerate(intervals)
                   if other_index != index):
                container.remove(rest)


def frozen_smb_rows(workspace: Path, collection: str) -> list[dict[str, Any]]:
    if collection not in {"smb-pianoform", "smb-complete"}:
        raise ValueError(f"Unsupported SMB collection: {collection}")
    path = workspace / "Research" / "omr" / "reports" / "phase1" / f"{collection}.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("Frozen SMB item identities are not unique")
    return rows


def metadata_by_id(path: Path) -> dict[str, dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    lookup = {row["file_name"]: row for row in rows}
    if len(lookup) != len(rows):
        raise ValueError("SMB metadata contains duplicate image identities")
    return lookup


def reference_identity(workspace: Path, collection: str) -> dict[str, str]:
    research = workspace / "Research" / "omr"
    return {
        "manifest_sha256": sha256_file(research / "reports" / "phase1" / f"{collection}.jsonl"),
        "metadata_sha256": sha256_file(research / "data" / "smb" / "metadata.jsonl"),
        "parser_sha256": sha256_file(research / "src" / "sheet2play_omr" / "events.py"),
        "builder_sha256": sha256_file(Path(__file__)),
        "normalizer_sha256": sha256_file(workspace / "Bridge" / "musicxml_normalizer.py"),
    }


def _export_page_musicxml(regions: list[dict[str, Any]], expected_hashes: list[str],
                          destination: Path) -> tuple[list[str], Counter[tuple[int, Fraction, Fraction]]]:
    from music21 import stream

    if not regions or len(regions) != len(expected_hashes):
        raise ValueError("SMB region count differs from the frozen manifest")
    score = stream.Score()
    parts: list[Any] = []
    elapsed = Fraction(0)
    measure_number = 1
    timeline: list[tuple[Fraction, Fraction, int, Any]] = []
    durations: list[str] = []
    for index, (region, expected_hash) in enumerate(zip(regions, expected_hashes, strict=True), start=1):
        kern = region.get("kern")
        if not isinstance(kern, str) or hashlib.sha256(kern.encode("utf-8")).hexdigest() != expected_hash:
            raise ValueError(f"SMB region {index} is missing or differs from Phase 1")
        parsed = parse_kern(kern)
        duration = _fraction(parsed.duration.quarterLength)
        if duration <= 0:
            raise ValueError(f"SMB region {index} has nonpositive duration")
        source_measures = []
        for part in parsed.parts:
            measures = []
            for measure in part.getElementsByClass(stream.Measure):
                if _fraction(measure.offset) == duration and _fraction(measure.quarterLength) == 0:
                    if list(measure.recurse().notes):
                        raise ValueError(f"SMB region {index} has notes in a zero-length trailing measure")
                    continue
                measures.append(measure)
            source_measures.append(measures)
        if not source_measures or any(not measures for measures in source_measures):
            raise ValueError(f"SMB region {index} has a part without measures")
        templates: dict[Fraction, Any] = {}
        for measures in source_measures:
            for measure in measures:
                offset = _fraction(measure.offset)
                if offset not in templates or (templates[offset].timeSignature is None
                                               and measure.timeSignature is not None):
                    templates[offset] = measure
        starts = sorted(templates)
        if not starts or starts[0] != 0 or starts[-1] >= duration:
            raise ValueError(f"SMB region {index} has invalid measure offsets")
        spans = [(start, end - start, measure_number + ordinal, templates[start])
                 for ordinal, (start, end) in enumerate(zip(starts, starts[1:] + [duration]))]
        if any(length <= 0 for _, length, _, _ in spans):
            raise ValueError(f"SMB region {index} has nonpositive measure span")
        while len(parts) < len(parsed.parts):
            part = stream.Part(id=f"P{len(parts) + 1}")
            for start, length, number, template in timeline:
                part.insert(start, _rest_measure(number, length, template))
            score.insert(0, part)
            parts.append(part)
        for part_index, part in enumerate(parts):
            measures = source_measures[part_index] if part_index < len(source_measures) else []
            by_start = {_fraction(measure.offset): measure for measure in measures}
            if len(by_start) != len(measures):
                raise ValueError(f"SMB region {index} part {part_index} repeats a measure offset")
            occupied_until = Fraction(0)
            for start, length, number, template in spans:
                source = by_start.get(start)
                if start < occupied_until:
                    if source is not None and _fraction(source.quarterLength) > 0:
                        raise ValueError(f"SMB region {index} part {part_index} overlaps sounding measures")
                    continue
                if source is None:
                    preserved = _rest_measure(number, length, template)
                else:
                    preserved = copy.deepcopy(source)
                    preserved.number = number
                    _remove_redundant_rests(preserved)
                    current_length = _fraction(preserved.quarterLength)
                    if current_length < length:
                        if preserved.voices:
                            for voice in preserved.voices:
                                voice_length = _fraction(voice.highestTime)
                                if voice_length < length:
                                    _insert_rests(voice, voice_length, length - voice_length)
                        else:
                            _insert_rests(preserved, current_length, length - current_length)
                    if _fraction(preserved.quarterLength) < _fraction(preserved.barDuration.quarterLength):
                        preserved.padAsAnacrusis()
                part.insert(elapsed + start, preserved)
                occupied_until = start + _fraction(preserved.quarterLength)
        timeline.extend((elapsed + start, length, number, template)
                        for start, length, number, template in spans)
        durations.append(str(duration))
        elapsed += duration
        measure_number += len(spans)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(f"Reference MusicXML already exists without a result: {destination}")
    source_notes = _raw_note_counter(score)
    # music21's notation rewrite synthesizes tie continuations on some SMB systems and
    # shifts the following notes. The parsed **kern measures already carry notation.
    score.write("musicxml", fp=destination, makeNotation=False)
    if not destination.is_file() or destination.stat().st_size == 0:
        raise ValueError("SMB reference MusicXML export is missing or empty")
    return durations, source_notes


def reference_payload(row: dict[str, Any], metadata: dict[str, Any], identity: dict[str, str],
                      musicxml_path: Path, workspace: Path) -> dict[str, Any]:
    output = io.StringIO()
    error_output = io.StringIO()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error_output):
            durations, source_notes = _export_page_musicxml(
                metadata["regions"], row["reference_region_sha256"], musicxml_path)
            from music21 import converter

            roundtrip_score = converter.parse(str(musicxml_path), forceSource=True)
            roundtrip_notes = _raw_note_counter(roundtrip_score)
            if source_notes != roundtrip_notes:
                missing = sum((source_notes - roundtrip_notes).values())
                extra = sum((roundtrip_notes - source_notes).values())
                raise ValueError(f"SMB reference MusicXML changed sounding note timing: {missing} missing, {extra} extra")
            bridge = workspace / "Bridge"
            if str(bridge) not in sys.path:
                sys.path.insert(0, str(bridge))
            from musicxml_normalizer import normalize_musicxml

            score = normalize_musicxml(musicxml_path, expand_repeats=False,
                                       skip_grace_notes=True, force_source=True)
    from music21 import stream

    boundaries = sorted({Fraction(0)} | {
        _fraction(measure.getOffsetInHierarchy(part))
        for part in roundtrip_score.parts
        for measure in part.getElementsByClass(stream.Measure)
    })
    notes = [
        {"midi_pitch": note.midi_pitch, "onset": str(_fraction(note.start_beat)),
         "duration": str(_fraction(note.duration_beats)), "staff": note.staff_index,
         "voice": note.voice_identifier}
        for note in score.notes
    ]
    if not notes:
        raise ValueError("SMB page produced no sounding notes")
    messages = [f"{item.category.__name__}: {item.message}" for item in caught]
    messages += [line for line in (output.getvalue() + "\n" + error_output.getvalue()).splitlines() if line]
    return {
        "schema_version": 1,
        "item_id": row["id"],
        "composition_group": row["composition_group"],
        "image_sha256": row["image_sha256"],
        "reference_region_sha256": row["reference_region_sha256"],
        "identity": identity,
        "region_durations": durations,
        "measure_boundaries": [str(value) for value in boundaries],
        "reference_musicxml": portable_path(musicxml_path),
        "reference_musicxml_sha256": sha256_file(musicxml_path),
        "normalization_warnings": messages,
        "part_count": score.part_count,
        "roundtrip_sounding_note_count": sum(source_notes.values()),
        "roundtrip_note_timing_verified": True,
        "time_unit": "rational quarter-note time",
        "expand_repeats": False,
        "grace_notes_in_primary": False,
        "notes": notes,
    }
