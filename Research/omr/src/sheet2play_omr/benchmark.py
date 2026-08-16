from __future__ import annotations

import json
import math
import statistics
from dataclasses import asdict
from fractions import Fraction
from pathlib import Path
from typing import Any

from PIL import Image

from .errors import ResearchError
from .events import CanonicalScore, extract_canonical_events, parse_kern

from .metrics import MetricNote, calculate_note_metrics


def _metric_notes(score: CanonicalScore) -> list[MetricNote]:
    return [
        MetricNote(
            pitch=int(event.midi_pitch),
            onset=Fraction(event.onset),
            duration=Fraction(event.duration),
            staff=event.staff,
            voice=event.voice,
        )
        for event in score.events
        if event.kind == "note" and event.midi_pitch is not None
    ]


def load_event_file(path: Path) -> CanonicalScore:
    from .events import CanonicalEvent, StructuralEvent

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        events = tuple(CanonicalEvent(**item) for item in payload["events"])
        structure = tuple(StructuralEvent(**item) for item in payload["structure"])
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise ResearchError("BENCHMARK_INVALID", "benchmark", f"Invalid event file {path}: {error}") from error
    return CanonicalScore(events, structure)


def load_benchmark_manifest(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    manifest_root = path.resolve().parent

    def resolve_entry(value: Any) -> str:
        candidate = Path(str(value))
        return str((candidate if candidate.is_absolute() else manifest_root / candidate).resolve(strict=True))

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise ResearchError("BENCHMARK_INVALID", "benchmark", f"Cannot read {path}: {error}") from error
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            row["id"] = str(row["id"])
            row["image"] = resolve_entry(row["image"])
            row["ground_truth_events"] = resolve_entry(row["ground_truth_events"])
            if row.get("homr_events"):
                row["homr_events"] = resolve_entry(row["homr_events"])
            row["kind"] = str(row.get("kind", "system"))
        except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
            raise ResearchError(
                "BENCHMARK_INVALID",
                "benchmark",
                f"Invalid manifest line {line_number}: {error}",
            ) from error
        rows.append(row)
    if not rows:
        raise ResearchError("BENCHMARK_INVALID", "benchmark", "Benchmark manifest is empty")
    identifiers = [row["id"] for row in rows]
    if len(identifiers) != len(set(identifiers)):
        raise ResearchError("BENCHMARK_INVALID", "benchmark", "Benchmark IDs must be unique")
    return rows


def _mean(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [
        float(row["metrics"][key])
        for row in rows
        if row.get("valid") and row["metrics"].get(key) is not None
    ]
    finite_values = [value for value in values if math.isfinite(value)]
    return statistics.fmean(finite_values) if finite_values else None


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [row for row in rows if row.get("valid")]
    latencies = [float(row["seconds"]) for row in valid]
    fixture_rows = [row for row in valid if row.get("is_structural_fixture")]
    return {
        "samples": len(rows),
        "structural_validity": len(valid) / len(rows) if rows else 0.0,
        "catastrophic_page_failure_rate": 1.0 - (len(valid) / len(rows)) if rows else 1.0,
        "pitch_f1": _mean(rows, "pitch_f1") or 0.0,
        "onset_f1": _mean(rows, "onset_f1") or 0.0,
        "onset_duration_f1": _mean(rows, "onset_duration_f1") or 0.0,
        "mean_offset_error": _mean(rows, "mean_offset_error"),
        "staff_accuracy": _mean(rows, "staff_accuracy") or 0.0,
        "voice_accuracy": _mean(rows, "aligned_voice_accuracy") or 0.0,
        "median_seconds_per_page": statistics.median(latencies) if latencies else None,
        "peak_vram_bytes": max((int(row["peak_vram_bytes"]) for row in valid), default=0),
        "structural_assertions": (
            sum(bool(row.get("structure_exact")) for row in fixture_rows) / len(fixture_rows)
            if fixture_rows
            else 0.0
        ),
    }


def _evaluate_homr(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    evaluated: list[dict[str, Any]] = []
    for row in rows:
        if not row.get("homr_events"):
            continue
        expected = load_event_file(Path(row["ground_truth_events"]))
        predicted = load_event_file(Path(row["homr_events"]))
        metrics = calculate_note_metrics(_metric_notes(predicted), _metric_notes(expected))
        evaluated.append({"valid": True, "metrics": asdict(metrics), "seconds": 0.0, "peak_vram_bytes": 0})
    return _aggregate(evaluated) if evaluated else None


def run_benchmark(
    manifest_path: Path,
    output_path: Path,
    *,
    modes: tuple[DecodeMode, ...] = ("beam", "grammar"),
    require_acceptance_size: bool = False,
) -> dict[str, Any]:
    manifest = load_benchmark_manifest(manifest_path)
    if require_acceptance_size:
        systems = sum(row["kind"] == "system" for row in manifest)
        pages = sum(row["kind"] == "page" for row in manifest)
        if systems < 500 or pages < 100:
            raise ResearchError(
                "BENCHMARK_INVALID",
                "benchmark",
                f"Acceptance benchmark requires at least 500 systems and 100 pages; found {systems} and {pages}",
            )
    mode_reports: dict[str, Any] = {}
    for mode in modes:
        runner = TranscodaRunner(mode)
        samples: list[dict[str, Any]] = []
        for index, row in enumerate(manifest, start=1):
            expected = load_event_file(Path(row["ground_truth_events"]))
            sample: dict[str, Any] = {"id": row["id"], "valid": False}
            try:
                with Image.open(row["image"]) as image:
                    converted = image.convert("RGB")
                try:
                    prediction = runner.predict(converted, page=index, total_pages=len(manifest))
                finally:
                    converted.close()
                parsed = parse_kern(prediction.kern)
                canonical = extract_canonical_events(parsed)
                metrics = calculate_note_metrics(_metric_notes(canonical), _metric_notes(expected))
                serialized_metrics = asdict(metrics)
                if not math.isfinite(serialized_metrics["mean_offset_error"]):
                    serialized_metrics["mean_offset_error"] = None
                is_fixture = bool(row.get("structural_fixture", False))
                sample.update(
                    valid=True,
                    metrics=serialized_metrics,
                    seconds=prediction.seconds,
                    peak_vram_bytes=prediction.peak_vram_bytes,
                    is_structural_fixture=is_fixture,
                    structure_exact=(canonical.structure == expected.structure) if is_fixture else None,
                )
            except ResearchError as error:
                sample["error"] = {
                    "code": error.code,
                    "stage": error.stage,
                    "message": str(error),
                }
            samples.append(sample)
        mode_reports[mode] = {"summary": _aggregate(samples), "samples": samples}

    eligible = [
        (name, report["summary"])
        for name, report in mode_reports.items()
        if report["summary"]["structural_validity"] == 1.0
    ]
    selected_mode: str | None = None
    if eligible:
        selected_mode = max(
            eligible,
            key=lambda item: (
                item[1]["onset_duration_f1"],
                -item[1]["median_seconds_per_page"],
            ),
        )[0]
    report = {
        "schema_version": 1,
        "manifest": str(manifest_path.resolve()),
        "modes": mode_reports,
        "selected_mode": selected_mode,
        "homr": _evaluate_homr(manifest),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    return report
