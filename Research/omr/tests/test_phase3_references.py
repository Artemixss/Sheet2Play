from __future__ import annotations

import hashlib
from pathlib import Path

from music21 import meter, note, stream, tie
import pytest

from sheet2play_omr import phase3_references


def _part(pitches: tuple[str, ...], *, tie_type: str | None = None,
          meter_signature: str | None = None) -> stream.Part:
    part = stream.Part()
    measure = stream.Measure(number=1)
    if meter_signature:
        measure.insert(0, meter.TimeSignature(meter_signature))
    for pitch in pitches:
        value = note.Note(pitch, quarterLength=1)
        if tie_type and pitch == "C4":
            value.tie = tie.Tie(tie_type)
        measure.append(value)
    part.append(measure)
    if meter_signature:
        measure.padAsAnacrusis()
    return part


def test_page_reference_preserves_pickup_tie_and_extra_staff(tmp_path: Path, monkeypatch) -> None:
    first = stream.Score()
    first.insert(0, _part(("C4",), tie_type="start", meter_signature="3/4"))
    first.insert(0, _part(("G3",), meter_signature="3/4"))
    second = stream.Score()
    second.insert(0, _part(("C4", "E4"), tie_type="stop"))
    second.insert(0, _part(("A3", "A3")))
    second.insert(0, _part(("C5", "D5")))
    sources = {"first": first, "second": second}
    monkeypatch.setattr(phase3_references, "parse_kern", lambda value: sources[value])

    regions = [{"kern": "first"}, {"kern": "second"}]
    hashes = [hashlib.sha256(value["kern"].encode()).hexdigest() for value in regions]
    row = {"id": "synthetic-page", "composition_group": "synthetic", "image_sha256": "a" * 64,
           "reference_region_sha256": hashes}
    workspace = Path(__file__).resolve().parents[3]
    destination = tmp_path / "reference.musicxml"
    payload = phase3_references.reference_payload(row, {"regions": regions},
                                                 {"test": "identity"}, destination, workspace)
    events = {(item["midi_pitch"], item["onset"], item["duration"]) for item in payload["notes"]}
    assert payload["part_count"] == 3
    assert (60, "0", "2") in events
    assert (64, "2", "1") in events
    assert (55, "0", "1") in events
    assert (72, "1", "1") in events
    assert payload["normalization_warnings"] == []


def test_reference_rejects_changed_frozen_region_hash(tmp_path: Path) -> None:
    workspace = Path(__file__).resolve().parents[3]
    row = {"id": "synthetic-page", "composition_group": "synthetic", "image_sha256": "a" * 64,
           "reference_region_sha256": ["0" * 64]}
    with pytest.raises(ValueError, match="differs from Phase 1"):
        phase3_references.reference_payload(row, {"regions": [{"kern": "altered"}]},
                                            {"test": "identity"}, tmp_path / "reference.musicxml", workspace)


def test_unpadded_pickup_retains_following_measure_onsets(tmp_path: Path, monkeypatch) -> None:
    score = stream.Score()
    part = stream.Part()
    pickup = stream.Measure(number=0)
    pickup.insert(0, meter.TimeSignature("2/4"))
    pickup.append(note.Note("C4", quarterLength=0.5))
    part.append(pickup)
    full = stream.Measure(number=0)
    full.append(note.Note("D4", quarterLength=2))
    part.append(full)
    score.insert(0, part)
    monkeypatch.setattr(phase3_references, "parse_kern", lambda _: score)
    row = {"id": "pickup", "composition_group": "synthetic", "image_sha256": "a" * 64,
           "reference_region_sha256": [hashlib.sha256(b"pickup").hexdigest()]}
    workspace = Path(__file__).resolve().parents[3]
    payload = phase3_references.reference_payload(
        row, {"regions": [{"kern": "pickup"}]}, {"test": "identity"},
        tmp_path / "reference.musicxml", workspace)
    assert [(item["midi_pitch"], item["onset"]) for item in payload["notes"]] == [
        (60, "0"), (62, "1/2")]


def test_partial_measure_inside_page_does_not_shift_later_regions(tmp_path: Path, monkeypatch) -> None:
    def region(pitch: str, length: float) -> stream.Score:
        score = stream.Score()
        part = stream.Part()
        first = stream.Measure(number=0)
        first.insert(0, meter.TimeSignature("2/4"))
        first.append(note.Note(pitch, quarterLength=length))
        part.append(first)
        second = stream.Measure(number=0)
        second.append(note.Note("E4", quarterLength=2))
        part.append(second)
        score.insert(0, part)
        return score

    sources = {"one": region("C4", 2), "two": region("D4", 0.5)}
    monkeypatch.setattr(phase3_references, "parse_kern", lambda value: sources[value])
    regions = [{"kern": value} for value in sources]
    row = {"id": "partial-middle", "composition_group": "synthetic", "image_sha256": "a" * 64,
           "reference_region_sha256": [hashlib.sha256(value.encode()).hexdigest()
                                       for value in sources]}
    workspace = Path(__file__).resolve().parents[3]
    payload = phase3_references.reference_payload(row, {"regions": regions},
                                                 {"test": "identity"},
                                                 tmp_path / "reference.musicxml", workspace)
    events = {(item["midi_pitch"], item["onset"]) for item in payload["notes"]}
    assert (62, "4") in events
    assert (64, "9/2") in events


def test_empty_trailing_measure_at_region_boundary_is_ignored(tmp_path: Path, monkeypatch) -> None:
    score = stream.Score()
    part = stream.Part()
    sounding = stream.Measure(number=1)
    sounding.append(note.Note("C4", quarterLength=2))
    part.append(sounding)
    part.insert(2, stream.Measure(number=2))
    score.insert(0, part)
    monkeypatch.setattr(phase3_references, "parse_kern", lambda _: score)
    row = {"id": "empty-tail", "composition_group": "synthetic", "image_sha256": "a" * 64,
           "reference_region_sha256": [hashlib.sha256(b"empty-tail").hexdigest()]}
    workspace = Path(__file__).resolve().parents[3]

    payload = phase3_references.reference_payload(
        row, {"regions": [{"kern": "empty-tail"}]}, {"test": "identity"},
        tmp_path / "reference.musicxml", workspace)

    assert [(item["midi_pitch"], item["onset"], item["duration"]) for item in payload["notes"]] == [
        (60, "0", "2")]
    assert payload["measure_boundaries"] == ["0"]


def test_missing_staff_rest_with_complex_length_exports(tmp_path: Path, monkeypatch) -> None:
    first = stream.Score()
    first.insert(0, _part(("C4",)))
    first.insert(0, _part(("G3",)))
    second = stream.Score()
    part = stream.Part()
    measure = stream.Measure(number=1)
    measure.append(note.Note("D4", quarterLength=2))
    measure.append(note.Note("E4", quarterLength=0.75))
    part.append(measure)
    second.insert(0, part)
    sources = {"first": first, "second": second}
    monkeypatch.setattr(phase3_references, "parse_kern", lambda value: sources[value])
    regions = [{"kern": value} for value in sources]
    row = {"id": "complex-rest", "composition_group": "synthetic", "image_sha256": "a" * 64,
           "reference_region_sha256": [hashlib.sha256(value.encode()).hexdigest()
                                       for value in sources]}
    workspace = Path(__file__).resolve().parents[3]

    payload = phase3_references.reference_payload(
        row, {"regions": regions}, {"test": "identity"},
        tmp_path / "reference.musicxml", workspace)

    events = {(item["midi_pitch"], item["onset"], item["duration"]) for item in payload["notes"]}
    assert (62, "1", "2") in events
    assert (64, "3", "3/4") in events
    assert len(payload["notes"]) == 4
