from __future__ import annotations

import json
import math
import os
import statistics
import sys
from dataclasses import asdict
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable

from .engines import (
    DEFAULT_TIMEOUT_SECONDS,
    metric_notes_from_bridge,
    run_bridge_engine,
    workspace_root,
)
from .errors import ResearchError
from .metrics import MetricNote, calculate_note_metrics
from .olimpic import OlimpicSample


CHECKPOINT_SCHEMA_VERSION = 1
HOMR_TIMEOUT_SECONDS = 600


def _fraction(value: float | int | str | Fraction) -> Fraction:
    if isinstance(value, Fraction):
        return value
    return Fraction(str(value)).limit_denominator(4096)


def load_ground_truth_notes(path: Path) -> list[MetricNote]:
    bridge_directory = workspace_root() / "Bridge"
    bridge_path = str(bridge_directory)
    if bridge_path not in sys.path:
        sys.path.insert(0, bridge_path)
    try:
        from musicxml_normalizer import MusicXmlNormalizationError, normalize_musicxml

        # These must match what Bridge/bridge.py applies to predictions, or the two sides
        # of every comparison are normalized differently. They previously did not:
        # ground truth used expand_repeats=False / skip_grace_notes=True against
        # predictions built with the opposite flags. Measured impact on the OLiMPiC canary
        # is under 0.005 onset F1 (repeats and grace notes are rare there), but the
        # mismatch silently corrupts any corpus where they are not.
        score = normalize_musicxml(
            path,
            expand_repeats=True,
            skip_grace_notes=False,
        )
    except (ImportError, OSError) as error:
        raise ResearchError(
            "GROUND_TRUTH_INVALID", "ground_truth", f"Cannot load MusicXML normalizer: {error}"
        ) from error
    except MusicXmlNormalizationError as error:
        raise ResearchError(
            "GROUND_TRUTH_INVALID", "ground_truth", f"Cannot normalize {path}: {error}"
        ) from error
    notes = [
        MetricNote(
            pitch=note.midi_pitch,
            onset=_fraction(note.start_beat),
            duration=_fraction(note.duration_beats),
            staff=note.staff_index,
            voice=note.voice_identifier,
        )
        for note in score.notes
    ]
    if not notes:
        raise ResearchError("GROUND_TRUTH_INVALID", "ground_truth", f"No notes in {path}")
    return notes


def _serialize_metrics(predicted: list[MetricNote], expected: list[MetricNote]) -> dict[str, Any]:
    payload = asdict(calculate_note_metrics(predicted, expected))
    if not math.isfinite(payload["mean_offset_error"]):
        payload["mean_offset_error"] = None
    return payload


def _error_payload(error: Exception) -> dict[str, Any]:
    return {
        "code": str(getattr(error, "code", error.__class__.__name__)),
        "stage": str(getattr(error, "stage", "benchmark")),
        "message": str(error)[:2000],
        "page": getattr(error, "page", None),
    }


def _run_homr(sample: OlimpicSample, expected: list[MetricNote]) -> dict[str, Any]:
    """Score one OLiMPiC sample through the bridge, as a checkpoint row."""
    result = run_bridge_engine(
        sample.image, engine="homr", timeout_seconds=DEFAULT_TIMEOUT_SECONDS
    )
    row: dict[str, Any] = {
        "id": sample.identifier,
        "score_id": sample.score_id,
        "seconds": result.seconds,
        "peak_vram_bytes": 0,
    }
    if not result.ok:
        row["valid"] = False
        row["error"] = result.error
        if result.stderr_tail:
            row["stderr_tail"] = result.stderr_tail
        if result.stdout_tail:
            row["stdout_tail"] = result.stdout_tail
        return row
    try:
        predicted = metric_notes_from_bridge(result.payload, stage="homr")
    except ResearchError as error:
        row["valid"] = False
        row["error"] = _error_payload(error)
        return row
    row["valid"] = True
    row["metrics"] = _serialize_metrics(predicted, expected)
    return row


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def _mean_metric(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [
        float(row["metrics"][key])
        for row in rows
        if row.get("valid") and row.get("metrics", {}).get(key) is not None
    ]
    values = [value for value in values if math.isfinite(value)]
    return statistics.fmean(values) if values else None


def aggregate_results(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    samples = list(rows)
    valid = [row for row in samples if row.get("valid")]
    latencies = [float(row["seconds"]) for row in samples if row.get("seconds") is not None]
    return {
        "samples": len(samples),
        "valid_samples": len(valid),
        "structural_validity": len(valid) / len(samples) if samples else 0.0,
        "catastrophic_page_failure_rate": 1.0 - len(valid) / len(samples) if samples else 1.0,
        "pitch_f1": _mean_metric(samples, "pitch_f1") or 0.0,
        "onset_f1": _mean_metric(samples, "onset_f1") or 0.0,
        "onset_duration_f1": _mean_metric(samples, "onset_duration_f1") or 0.0,
        "mean_offset_error": _mean_metric(samples, "mean_offset_error"),
        "staff_accuracy": _mean_metric(samples, "staff_accuracy") or 0.0,
        "voice_accuracy": _mean_metric(samples, "aligned_voice_accuracy") or 0.0,
        "median_seconds_per_system": statistics.median(latencies) if latencies else None,
        "p95_seconds_per_system": _percentile(latencies, 0.95),
        "peak_vram_bytes": max((int(row.get("peak_vram_bytes", 0)) for row in samples), default=0),
    }


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.{os.getpid()}.tmp"
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _load_checkpoint(path: Path, sample_ids: list[str]) -> dict[str, Any]:
    if not path.is_file():
        return {
            "schema_version": CHECKPOINT_SCHEMA_VERSION,
            "sample_ids": sample_ids,
            "homr": {},
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ResearchError("BENCHMARK_INVALID", "checkpoint", str(error)) from error
    if payload.get("schema_version") != CHECKPOINT_SCHEMA_VERSION or payload.get("sample_ids") != sample_ids:
        raise ResearchError(
            "BENCHMARK_INVALID",
            "checkpoint",
            "Checkpoint schema or sample selection does not match this run",
        )
    return payload


def _ordered_rows(results: dict[str, Any], sample_ids: list[str]) -> list[dict[str, Any]]:
    return [results[identifier] for identifier in sample_ids if identifier in results]


def run_checkpointed_benchmark(
    samples: list[OlimpicSample],
    checkpoint_path: Path,
    *,
    progress: Any = print,
) -> dict[str, Any]:
    sample_ids = [sample.identifier for sample in samples]
    checkpoint = _load_checkpoint(checkpoint_path, sample_ids)

    for index, sample in enumerate(samples, start=1):
        if sample.identifier in checkpoint["homr"]:
            continue
        progress(f"[HOMR] {index}/{len(samples)} {sample.identifier}")
        expected = load_ground_truth_notes(Path(sample.musicxml))
        checkpoint["homr"][sample.identifier] = _run_homr(sample, expected)
        _atomic_write_json(checkpoint_path, checkpoint)

    rows = _ordered_rows(checkpoint["homr"], sample_ids)
    return {
        "schema_version": 1,
        "sample_count": len(samples),
        "checkpoint": str(checkpoint_path.resolve()),
        "homr": {
            "summary": aggregate_results(rows),
            "samples": rows,
        },
    }
