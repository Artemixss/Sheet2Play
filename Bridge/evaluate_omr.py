from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from musicxml_normalizer import add_seconds, normalize_musicxml


@dataclass(frozen=True, slots=True)
class EvaluationNote:
    midi_pitch: int
    start_beat: float
    duration_beats: float

    @property
    def end_beat(self) -> float:
        return self.start_beat + self.duration_beats


@dataclass(frozen=True, slots=True)
class EvaluationMetrics:
    truth_notes: int
    predicted_notes: int
    pitch_f1: float
    onset_f1: float
    offset_f1: float
    onset_and_duration_f1: float
    mean_overlap_iou: float


def parse_arguments(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare bridge JSON with ground-truth MusicXML."
    )
    parser.add_argument("ground_truth_musicxml", type=Path)
    parser.add_argument("prediction_json", type=Path)
    parser.add_argument("--onset-tolerance", type=float, default=0.125)
    parser.add_argument("--duration-tolerance", type=float, default=0.125)
    return parser.parse_args(arguments)


def _f1(matches: int, truth_count: int, prediction_count: int) -> float:
    if truth_count == 0 and prediction_count == 0:
        return 1.0
    if truth_count == 0 or prediction_count == 0:
        return 0.0
    precision = matches / prediction_count
    recall = matches / truth_count
    return 2.0 * precision * recall / (precision + recall) if matches else 0.0


def _load_truth(path: Path) -> list[EvaluationNote]:
    score = normalize_musicxml(path)
    add_seconds(score)
    return [
        EvaluationNote(
            midi_pitch=note.midi_pitch,
            start_beat=note.start_beat,
            duration_beats=note.duration_beats,
        )
        for note in score.notes
    ]


def _load_prediction(path: Path) -> list[EvaluationNote]:
    document = json.loads(path.resolve(strict=True).read_text(encoding="utf-8"))
    if document.get("schema_version") != 2 or not isinstance(document.get("notes"), list):
        raise ValueError("Prediction is not a Sheet2Play bridge schema version 2 result")

    notes: list[EvaluationNote] = []
    for index, item in enumerate(document["notes"]):
        try:
            note = EvaluationNote(
                midi_pitch=int(item["midi_pitch"]),
                start_beat=float(item["start_beat"]),
                duration_beats=float(item["duration_beats"]),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"Invalid prediction note at index {index}: {error}") from error
        if (
            note.midi_pitch < 0
            or note.midi_pitch > 127
            or not math.isfinite(note.start_beat)
            or not math.isfinite(note.duration_beats)
            or note.start_beat < 0
            or note.duration_beats < 0
        ):
            raise ValueError(f"Invalid prediction note at index {index}: {item!r}")
        notes.append(note)
    return notes


def _greedy_matches(
    truth: Sequence[EvaluationNote],
    predicted: Sequence[EvaluationNote],
    predicate: Any,
    distance: Any,
) -> list[tuple[int, int]]:
    candidates: list[tuple[float, int, int]] = []
    for truth_index, truth_note in enumerate(truth):
        for predicted_index, predicted_note in enumerate(predicted):
            if predicate(truth_note, predicted_note):
                candidates.append(
                    (distance(truth_note, predicted_note), truth_index, predicted_index)
                )
    candidates.sort()

    used_truth: set[int] = set()
    used_prediction: set[int] = set()
    matches: list[tuple[int, int]] = []
    for _, truth_index, predicted_index in candidates:
        if truth_index in used_truth or predicted_index in used_prediction:
            continue
        used_truth.add(truth_index)
        used_prediction.add(predicted_index)
        matches.append((truth_index, predicted_index))
    return matches


def evaluate(
    truth: Sequence[EvaluationNote],
    predicted: Sequence[EvaluationNote],
    onset_tolerance: float = 0.125,
    duration_tolerance: float = 0.125,
) -> EvaluationMetrics:
    if onset_tolerance < 0 or duration_tolerance < 0:
        raise ValueError("Evaluation tolerances must be non-negative")

    truth_pitches = Counter(note.midi_pitch for note in truth)
    predicted_pitches = Counter(note.midi_pitch for note in predicted)
    pitch_matches = sum((truth_pitches & predicted_pitches).values())

    same_pitch = lambda left, right: left.midi_pitch == right.midi_pitch
    onset_matches = _greedy_matches(
        truth,
        predicted,
        lambda left, right: same_pitch(left, right)
        and abs(left.start_beat - right.start_beat) <= onset_tolerance,
        lambda left, right: abs(left.start_beat - right.start_beat),
    )
    offset_matches = _greedy_matches(
        truth,
        predicted,
        lambda left, right: same_pitch(left, right)
        and abs(left.end_beat - right.end_beat) <= duration_tolerance,
        lambda left, right: abs(left.end_beat - right.end_beat),
    )
    structural_matches = _greedy_matches(
        truth,
        predicted,
        lambda left, right: same_pitch(left, right)
        and abs(left.start_beat - right.start_beat) <= onset_tolerance
        and abs(left.duration_beats - right.duration_beats) <= duration_tolerance,
        lambda left, right: abs(left.start_beat - right.start_beat)
        + abs(left.duration_beats - right.duration_beats),
    )

    overlap_values: list[float] = []
    for truth_index, prediction_index in onset_matches:
        truth_note = truth[truth_index]
        predicted_note = predicted[prediction_index]
        intersection = max(
            0.0,
            min(truth_note.end_beat, predicted_note.end_beat)
            - max(truth_note.start_beat, predicted_note.start_beat),
        )
        union = max(truth_note.end_beat, predicted_note.end_beat) - min(
            truth_note.start_beat, predicted_note.start_beat
        )
        overlap_values.append(intersection / union if union > 0 else 1.0)

    return EvaluationMetrics(
        truth_notes=len(truth),
        predicted_notes=len(predicted),
        pitch_f1=_f1(pitch_matches, len(truth), len(predicted)),
        onset_f1=_f1(len(onset_matches), len(truth), len(predicted)),
        offset_f1=_f1(len(offset_matches), len(truth), len(predicted)),
        onset_and_duration_f1=_f1(
            len(structural_matches), len(truth), len(predicted)
        ),
        mean_overlap_iou=(
            sum(overlap_values) / len(overlap_values) if overlap_values else 0.0
        ),
    )


def main(arguments: Sequence[str] | None = None) -> int:
    try:
        args = parse_arguments(arguments)
        metrics = evaluate(
            _load_truth(args.ground_truth_musicxml),
            _load_prediction(args.prediction_json),
            onset_tolerance=args.onset_tolerance,
            duration_tolerance=args.duration_tolerance,
        )
        json.dump(asdict(metrics), sys.stdout, separators=(",", ":"))
        sys.stdout.write("\n")
        return 0
    except Exception as error:
        print(f"OMR evaluation failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
