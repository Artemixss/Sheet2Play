"""Executable fixture matrix for the frozen Phase-1 scoring contract."""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
from collections import Counter
from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable

from .metrics import MetricNote, calculate_note_metrics, timeline_span
from .adapter_contract import AdapterConfig, AdapterInput, MeasurementPath, RunStatus, sha256_file
from .phase2r_validation import (
    failure_penalized_composition_macro,
    require_complete_systems,
    run_with_typed_failure,
)


@dataclass(frozen=True, slots=True)
class FixtureOutcome:
    name: str
    passed: bool
    evidence: dict[str, Any]


def _note(
    pitch: int,
    onset: int | Fraction,
    duration: int | Fraction,
    *,
    staff: int = 0,
    voice: str = "1",
) -> MetricNote:
    return MetricNote(pitch, Fraction(onset), Fraction(duration), staff, voice)


def _counts(predicted: Iterable[MetricNote], expected: Iterable[MetricNote]) -> dict[str, int]:
    left = Counter((item.pitch, item.onset, item.duration) for item in predicted)
    right = Counter((item.pitch, item.onset, item.duration) for item in expected)
    return {
        "missing": sum((right - left).values()),
        "extra": sum((left - right).values()),
    }


def _score(predicted: list[MetricNote], expected: list[MetricNote]) -> dict[str, Any]:
    metrics = asdict(calculate_note_metrics(predicted, expected))
    if metrics["mean_offset_error"] == float("inf"):
        metrics["mean_offset_error"] = None
    return {
        **metrics,
        **_counts(predicted, expected),
        "predicted_span": str(timeline_span(predicted)),
        "expected_span": str(timeline_span(expected)),
    }


def _fixture(name: str, condition: bool, evidence: dict[str, Any]) -> FixtureOutcome:
    return FixtureOutcome(name, bool(condition), evidence)


def _failure_fixture(temporary: Path, *, missing_system: bool) -> FixtureOutcome:
    from music21 import stream
    from .phase2_adapters import _canonicalize

    image = temporary / "fixture.png"
    image.write_bytes(b"fixture")
    item = AdapterInput(
        "missing-system" if missing_system else "empty-output",
        "fixture-composition",
        image,
        sha256_file(image),
        MeasurementPath.COMPLETE_DOCUMENT,
    )
    config = AdapterConfig(
        "fixture", "fixture-adapter", "phase2r", "local-fixture", "phase2r",
        None, None, "MusicXML", "page", (MeasurementPath.COMPLETE_DOCUMENT,),
    )

    class FixtureAdapter:
        def __init__(self) -> None:
            self.config = config

        def run(self, _item: AdapterInput, output: Path) -> Any:
            if missing_system:
                require_complete_systems((1, 2, 3), (1, 3))
            else:
                source = output / "empty.musicxml"
                score = stream.Score()
                score.append(stream.Part())
                score.write("musicxml", fp=source)
                _canonicalize(source, output / "canonical-events.json")
            raise AssertionError("The fixture failure path was incorrectly accepted")

    result = run_with_typed_failure(FixtureAdapter(), item, temporary / item.item_id)
    aggregate = failure_penalized_composition_macro(
        [(item.composition_group, result, None)]
    )
    expected_code = "MISSING_SYSTEM" if missing_system else "ADAPTER_OUTPUT_INVALID"
    return _fixture(
        "missing middle system" if missing_system else "empty output",
        result.status is RunStatus.FAILED
        and result.error is not None
        and result.error["code"] == expected_code
        and aggregate == 0.0,
        {
            "status": result.status.value,
            "failure_code": result.error["code"] if result.error else None,
            "failure_stage": result.error["stage"] if result.error else None,
            "primary_f1": aggregate,
            "expected_systems": [1, 2, 3] if missing_system else None,
            "observed_systems": [1, 3] if missing_system else None,
        },
    )


def _shared_normalizer() -> Any:
    for candidate in Path(__file__).resolve().parents:
        bridge = candidate / "Bridge"
        if (bridge / "musicxml_normalizer.py").is_file():
            if str(bridge) not in sys.path:
                sys.path.insert(0, str(bridge))
            from musicxml_normalizer import normalize_musicxml

            return normalize_musicxml
    raise RuntimeError("Cannot locate shared MusicXML normalizer")


def _write_score(path: Path, *, tied: bool = False) -> None:
    from music21 import meter, note, stream, tie

    score = stream.Score()
    for part_index, pitch in enumerate(("C4", "C3"), start=1):
        part = stream.Part(id=f"P{part_index}")
        first = stream.Measure(number=1)
        first.insert(0, meter.TimeSignature("2/4"))
        first_note = note.Note(pitch, quarterLength=2 if tied else 4)
        if tied:
            first_note.tie = tie.Tie("start")
        first.append(first_note)
        part.append(first)
        if tied:
            second = stream.Measure(number=2)
            continuation = note.Note(pitch, quarterLength=2)
            continuation.tie = tie.Tie("stop")
            second.append(continuation)
            part.append(second)
        score.append(part)
    score.write("musicxml", fp=path)


def _canonical_note_tuples(path: Path) -> list[tuple[int, str, str, int, str]]:
    normalized = _shared_normalizer()(
        path, expand_repeats=False, skip_grace_notes=True, force_source=True
    )
    return [
        (
            item.midi_pitch,
            str(item.start_beat),
            str(item.duration_beats),
            item.staff_index,
            item.voice_identifier,
        )
        for item in normalized.notes
    ]


def _source_musicxml_control(source: Path) -> bool:
    bridge_directory = source.parents[0]
    del bridge_directory
    workspace_bridge = None
    for candidate in Path(__file__).resolve().parents:
        path = candidate / "Bridge"
        if (path / "bridge.py").is_file():
            workspace_bridge = path
            break
    if workspace_bridge is None:
        raise RuntimeError("Cannot locate bridge.py")
    if str(workspace_bridge) not in sys.path:
        sys.path.insert(0, str(workspace_bridge))
    import bridge

    expected = _shared_normalizer()(source, expand_repeats=True, skip_grace_notes=False)
    output = io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
        status = bridge.main(["--engine", "musicxml", str(source)])
    if status != 0:
        return False
    actual = json.loads(output.getvalue())
    expected_tuples = [
        (
            item.midi_pitch,
            float(item.start_beat),
            float(item.duration_beats),
            item.part_index,
            item.staff_index,
            item.voice_identifier,
        )
        for item in expected.notes
    ]
    actual_tuples = [
        (
            item["midi_pitch"],
            item["start_beat"],
            item["duration_beats"],
            item["part_index"],
            item["staff_index"],
            item["voice_identifier"],
        )
        for item in actual["notes"]
    ]
    return actual_tuples == expected_tuples


def run_fixture_matrix() -> list[FixtureOutcome]:
    expected = [_note(60, 0, 1), _note(64, 1, 1), _note(67, 2, 2)]
    outcomes: list[FixtureOutcome] = []

    exact = _score(expected, expected)
    outcomes.append(_fixture("identical score", exact["onset_duration_f1"] == 1.0, exact))

    omitted = _score(expected[:-1], expected)
    outcomes.append(
        _fixture(
            "omitted note",
            omitted["missing"] == 1 and omitted["extra"] == 0 and omitted["onset_duration_f1"] < 1,
            omitted,
        )
    )

    inserted = _score([*expected, _note(72, 4, 1)], expected)
    outcomes.append(
        _fixture(
            "inserted note",
            inserted["extra"] == 1 and inserted["missing"] == 0 and inserted["onset_duration_f1"] < 1,
            inserted,
        )
    )

    shifted = _score([_note(item.pitch, item.onset + 8, item.duration) for item in expected], expected)
    outcomes.append(
        _fixture(
            "shifted onsets",
            shifted["pitch_f1"] == 1 and shifted["onset_f1"] == 0,
            shifted,
        )
    )

    voices = [
        _note(60, 0, 1, voice="upper"),
        _note(60, 0, 1, voice="lower"),
        _note(48, 0, 2, staff=1, voice="bass"),
    ]
    renamed = [
        _note(60, 0, 1, voice="a"),
        _note(60, 0, 1, voice="b"),
        _note(48, 0, 2, staff=1, voice="c"),
    ]
    voice_score = _score(renamed, voices)
    outcomes.append(
        _fixture(
            "overlapping voices",
            voice_score["onset_duration_f1"] == 1 and voice_score["aligned_voice_accuracy"] == 1,
            voice_score,
        )
    )

    tuplets = [_note(60, Fraction(i, 3), Fraction(1, 3)) for i in range(3)]
    tuplet_score = _score(tuplets, tuplets)
    outcomes.append(
        _fixture(
            "tuplets",
            tuplet_score["onset_duration_f1"] == 1 and tuplet_score["expected_span"] == "1",
            tuplet_score,
        )
    )

    pickup = [_note(60, 0, Fraction(1, 2)), _note(62, Fraction(1, 2), 1)]
    pickup_score = _score(pickup, pickup)
    outcomes.append(
        _fixture(
            "pickup",
            pickup_score["onset_duration_f1"] == 1 and pickup[0].onset == 0,
            pickup_score,
        )
    )

    before_change = [_note(60, 0, 4), _note(62, 4, 3), _note(64, 7, 3)]
    changed = [_note(60, 0, 4), _note(62, 4, 4), _note(64, 8, 3)]
    meter_score = _score(changed, before_change)
    outcomes.append(
        _fixture(
            "meter change",
            meter_score["pitch_f1"] == 1 and meter_score["onset_duration_f1"] < 1,
            {**meter_score, "first_divergent_measure": 2},
        )
    )

    notated = [_note(60, 0, 1), _note(62, 1, 1)]
    expanded = [*notated, _note(60, 2, 1), _note(62, 3, 1)]
    notated_score = _score(notated, notated)
    expanded_score = _score(expanded, notated)
    outcomes.append(
        _fixture(
            "repeats",
            notated_score["onset_duration_f1"] == 1 and expanded_score["extra"] == 2,
            {"printed_page": notated_score, "expanded_playback_diagnostic": expanded_score},
        )
    )

    with tempfile.TemporaryDirectory(prefix="s2p-phase2r-failures-") as temporary_name:
        temporary = Path(temporary_name)
        outcomes.append(_failure_fixture(temporary, missing_system=False))
        outcomes.append(_failure_fixture(temporary, missing_system=True))

    with tempfile.TemporaryDirectory(prefix="s2p-phase2-fixtures-") as temporary_name:
        temporary = Path(temporary_name)
        tied = temporary / "tied.musicxml"
        sustained = temporary / "sustained.musicxml"
        _write_score(tied, tied=True)
        _write_score(sustained, tied=False)
        tied_notes = _canonical_note_tuples(tied)
        sustained_notes = _canonical_note_tuples(sustained)
        outcomes.append(
            _fixture(
                "tied versus sustained equivalent",
                tied_notes == sustained_notes,
                {"tied": tied_notes, "sustained": sustained_notes},
            )
        )

        malformed = temporary / "malformed.musicxml"
        malformed.write_text("<score-partwise><part>", encoding="utf-8")
        malformed_failed = False
        try:
            _canonical_note_tuples(malformed)
        except Exception:
            malformed_failed = True
        outcomes.append(
            _fixture(
                "malformed XML",
                malformed_failed,
                {"status": "failure" if malformed_failed else "incorrectly accepted"},
            )
        )

        outcomes.append(
            _fixture(
                "source MusicXML to app control",
                _source_musicxml_control(sustained),
                {"path": "direct bridge musicxml engine", "fields": ["pitch", "midi_pitch", "onset", "duration", "part", "staff", "voice"]},
            )
        )

    return outcomes
