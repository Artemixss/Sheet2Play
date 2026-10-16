"""Failure-penalized Phase-3 page metrics under the frozen Phase-1 protocol."""
from __future__ import annotations

import math
import json
from bisect import bisect_right
from collections import Counter, defaultdict
from dataclasses import asdict
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable

from .adapter_contract import sha256_file
from .metrics import MetricNote, calculate_note_metrics, timeline_span
from .omr_ned import score_pair


def metric_notes(payload: dict[str, Any]) -> list[MetricNote]:
    rows = payload.get("notes")
    if not isinstance(rows, list):
        raise ValueError("Canonical event payload has no notes list")
    result: list[MetricNote] = []
    for row in rows:
        pitch = int(row["midi_pitch"])
        onset = Fraction(str(row["onset"]))
        duration = Fraction(str(row["duration"]))
        if not 0 <= pitch <= 127 or onset < 0 or duration <= 0:
            raise ValueError("Canonical note has invalid pitch or rational timing")
        result.append(MetricNote(pitch, onset, duration, int(row["staff"]), str(row["voice"])))
    if not result:
        raise ValueError("Canonical event payload contains no sounding notes")
    return result


def _artifact(result: dict[str, Any], role: str, workspace: Path) -> Path:
    matches = [item for item in result["artifacts"] if item["role"] == role]
    if len(matches) != 1:
        raise ValueError(f"Adapter result must have exactly one {role} artifact")
    item = matches[0]
    path = Path(item["path"])
    resolved = path if path.is_absolute() else workspace / path
    if not resolved.is_file() or sha256_file(resolved) != item["sha256"]:
        raise ValueError(f"Adapter {role} artifact missing or hash mismatched: {resolved}")
    return resolved


def _duration_pairs(predicted: list[MetricNote], expected: list[MetricNote]) -> dict[str, Any]:
    predictions: dict[tuple[int, Fraction], Counter[Fraction]] = defaultdict(Counter)
    references: dict[tuple[int, Fraction], Counter[Fraction]] = defaultdict(Counter)
    for item in predicted:
        predictions[(item.pitch, item.onset)][item.duration] += 1
    for item in expected:
        references[(item.pitch, item.onset)][item.duration] += 1
    confusion: Counter[tuple[str, str]] = Counter()
    unmatched_predicted = 0
    unmatched_expected = 0
    for key in predictions.keys() | references.keys():
        pred = predictions[key].copy()
        truth = references[key].copy()
        for duration in pred.keys() & truth.keys():
            count = min(pred[duration], truth[duration])
            confusion[(str(duration), str(duration))] += count
            pred[duration] -= count
            truth[duration] -= count
        remaining_pred = [duration for duration, count in sorted(pred.items()) for _ in range(count)]
        remaining_true = [duration for duration, count in sorted(truth.items()) for _ in range(count)]
        for actual, guess in zip(remaining_true, remaining_pred):
            confusion[(str(actual), str(guess))] += 1
        unmatched_predicted += max(0, len(remaining_pred) - len(remaining_true))
        unmatched_expected += max(0, len(remaining_true) - len(remaining_pred))
    return {
        "confusion": [{"actual": actual, "predicted": predicted_duration, "count": count}
                      for (actual, predicted_duration), count in sorted(confusion.items()) if count],
        "unmatched_predicted": unmatched_predicted,
        "unmatched_expected": unmatched_expected,
    }


def _first_divergent_measure(predicted: list[MetricNote], expected: list[MetricNote],
                             reference: dict[str, Any]) -> int | None:
    boundaries = sorted({Fraction(value) for value in reference["measure_boundaries"]})
    if not boundaries or boundaries[0] != 0:
        raise ValueError("Reference measure boundaries must start at zero")
    pred_by_measure: dict[int, Counter[tuple[int, Fraction, Fraction]]] = defaultdict(Counter)
    true_by_measure: dict[int, Counter[tuple[int, Fraction, Fraction]]] = defaultdict(Counter)
    for collection, output in ((predicted, pred_by_measure), (expected, true_by_measure)):
        for note in collection:
            index = max(0, bisect_right(boundaries, note.onset) - 1)
            output[index][(note.pitch, note.onset, note.duration)] += 1
    for index in range(len(boundaries)):
        if pred_by_measure[index] != true_by_measure[index]:
            return index + 1
    return None


def _elapsed_seconds(result: dict[str, Any]) -> float:
    timings = result.get("timings", [])
    total = next((float(item["seconds"]) for item in timings
                  if item["stage"] == "total_failed_attempt"), None)
    return total if total is not None else sum(float(item["seconds"]) for item in timings)


def _failed_score(base: dict[str, Any], expected_count: int) -> dict[str, Any]:
    return {
        **base, "predicted_note_count": 0, "pitch_f1": 0.0, "onset_f1": 0.0,
        "onset_duration_f1": 0.0, "omr_ned": None,
        "failure_penalized_omr_ned": 1.0, "omr_ned_status": "engine_failed",
        "duration": None, "missing_note_count": expected_count, "extra_note_count": 0,
        "timeline_length_error": None, "first_divergent_measure": 1,
    }


def score_result(result: dict[str, Any], reference: dict[str, Any], workspace: Path) -> dict[str, Any]:
    if (result.get("item_id") != reference.get("item_id")
            or result.get("provenance", {}).get("input_sha256") != reference.get("image_sha256")):
        raise ValueError("Adapter result and reference identities differ")
    if result["status"] == "unavailable":
        raise ValueError("Unavailable configurations cannot receive a frozen evaluation score")
    expected = metric_notes(reference)
    base: dict[str, Any] = {
        "schema_version": 1,
        "item_id": reference["item_id"],
        "composition_group": reference["composition_group"],
        "candidate_id": result["candidate_id"],
        "adapter_id": result["adapter_id"],
        "status": result["status"],
        "error": result.get("error"),
        "elapsed_seconds": _elapsed_seconds(result),
        "peak_ram_bytes": result["resources"]["peak_ram_bytes"],
        "peak_vram_bytes": result["resources"]["peak_vram_bytes"],
        "vram_measurement_notes": result["resources"]["measurement_notes"],
        "reference_note_count": len(expected),
        "reference_quarter_length": str(timeline_span(expected)),
        "reference_measure_count": len(reference["measure_boundaries"]),
        "cold_start": result["resources"]["cold_start"],
    }
    if result["status"] == "failed":
        return _failed_score(base, len(expected))
    if result["status"] != "succeeded":
        raise ValueError(f"Unexpected adapter status: {result['status']}")
    canonical = _artifact(result, "canonical_events", workspace)
    musicxml = _artifact(result, "musicxml", workspace)
    try:
        predicted = metric_notes(json.loads(canonical.read_text(encoding="utf-8")))
    except (ValueError, KeyError, TypeError, UnicodeError) as error:
        return _failed_score({**base, "status": "failed",
                              "error": {"code": "INVALID_CANONICAL_OUTPUT", "stage": "scoring",
                                        "message": f"{type(error).__name__}: {error}"[:500]}},
                             len(expected))
    metrics = asdict(calculate_note_metrics(predicted, expected))
    expected_counts = Counter((note.pitch, note.onset, note.duration) for note in expected)
    predicted_counts = Counter((note.pitch, note.onset, note.duration) for note in predicted)
    if not math.isfinite(metrics["mean_offset_error"]):
        metrics["mean_offset_error"] = None
    reference_xml = workspace / reference["reference_musicxml"]
    if not reference_xml.is_file() or sha256_file(reference_xml) != reference["reference_musicxml_sha256"]:
        raise ValueError("Reference MusicXML is missing or hash mismatched")
    omr_ned_status = "valid"
    omr_ned_error = None
    try:
        distance = score_pair(musicxml, reference_xml)
        if distance is None or not math.isfinite(distance.score) or not 0 <= distance.score <= 1:
            raise ValueError("OMR-NED returned no finite normalized score")
        omr_ned = distance.score
    except Exception as error:
        omr_ned_status = "scoring_error"
        omr_ned_error = f"{type(error).__name__}: {error}"[:500]
        omr_ned = None
    return {
        **base, **metrics, "predicted_note_count": len(predicted),
        "missing_note_count": sum((expected_counts - predicted_counts).values()),
        "extra_note_count": sum((predicted_counts - expected_counts).values()),
        "duration": _duration_pairs(predicted, expected),
        "timeline_length_error": str(timeline_span(predicted) - timeline_span(expected)),
        "first_divergent_measure": _first_divergent_measure(predicted, expected, reference),
        "omr_ned": omr_ned,
        "failure_penalized_omr_ned": omr_ned,
        "omr_ned_status": omr_ned_status,
        "omr_ned_error": omr_ned_error,
    }
