"""Development-only checks for typed OMR failures and system coverage."""
from __future__ import annotations

from collections import defaultdict
import json
import time
from pathlib import Path
from typing import Iterable

from .adapter_contract import (
    AdapterConfig,
    AdapterInput,
    AdapterResult,
    Artifact,
    ResourceMeasurements,
    RunStatus,
    StageTiming,
    base_provenance,
)
from .errors import ResearchError


def require_complete_systems(expected: Iterable[int], observed: Iterable[int]) -> None:
    expected_ids = tuple(expected)
    observed_ids = tuple(observed)
    if not expected_ids or expected_ids != tuple(range(1, len(expected_ids) + 1)):
        raise ValueError("Detector systems must be sequential and start at one")
    if observed_ids != expected_ids:
        raise ResearchError(
            "MISSING_SYSTEM",
            "stitching",
            f"Detected systems {expected_ids}; transcribed systems {observed_ids}",
        )


def record_attempt_measurement(
    output_directory: Path, *, stage: str, seconds: float,
    peak_ram_bytes: int | None = None, peak_vram_bytes: int | None = None,
    vram_measurement: str | None = None,
) -> None:
    if not stage or seconds < 0:
        raise ValueError("Attempt stage and elapsed time are required")
    destination = output_directory / "attempt-measurements.json"
    previous = json.loads(destination.read_text(encoding="utf-8")) if destination.is_file() else []
    previous.append({"stage": stage, "seconds": seconds, "peak_ram_bytes": peak_ram_bytes,
                     "peak_vram_bytes": peak_vram_bytes, "vram_measurement": vram_measurement})
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(previous, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(destination)


def typed_failure(
    config: AdapterConfig,
    item: AdapterInput,
    error: Exception,
    output_directory: Path,
    elapsed_seconds: float = 0.0,
) -> AdapterResult:
    from .phase2_adapters import _portable_text

    artifacts = tuple(
        Artifact.from_path(f"partial_{path.name}", path, "application/octet-stream")
        for path in sorted(output_directory.iterdir())
        if path.is_file() and path.stat().st_size > 0
    )
    measurement_path = output_directory / "attempt-measurements.json"
    try:
        measurements = json.loads(measurement_path.read_text(encoding="utf-8")) if measurement_path.is_file() else []
    except (OSError, ValueError):
        measurements = []
    ram_values = [entry["peak_ram_bytes"] for entry in measurements if entry["peak_ram_bytes"] is not None]
    vram_values = [entry["peak_vram_bytes"] for entry in measurements if entry["peak_vram_bytes"] is not None]
    notes = tuple(sorted({str(entry["vram_measurement"]) for entry in measurements
                          if entry["vram_measurement"]}))
    result = AdapterResult(
        schema_version=1,
        candidate_id=config.candidate_id,
        adapter_id=config.adapter_id,
        adapter_config_sha256=config.sha256,
        item_id=item.item_id,
        composition_group=item.composition_group,
        measurement_path=item.measurement_path,
        status=RunStatus.FAILED,
        exit_status=1,
        warnings=(),
        timings=(StageTiming("total_failed_attempt", elapsed_seconds),
                 *(StageTiming(entry["stage"], entry["seconds"]) for entry in measurements)),
        resources=ResourceMeasurements(max(ram_values) if ram_values else None,
                                       max(vram_values) if vram_values else None,
                                       0.2 if measurements else None, True, notes),
        artifacts=artifacts,
        provenance=base_provenance(config, item),
        error={
            "code": str(getattr(error, "code", type(error).__name__)),
            "stage": str(getattr(error, "stage", "adapter")),
            "message": _portable_text(str(error))[:2000],
        },
    )
    result.validate()
    return result


def run_with_typed_failure(adapter: object, item: AdapterInput, output_directory: Path) -> AdapterResult:
    item.validate()
    output_directory.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    try:
        result = adapter.run(item, output_directory)  # type: ignore[attr-defined]
        result.validate()
        return result
    except Exception as error:
        return typed_failure(adapter.config, item, error, output_directory,
                             time.perf_counter() - started)  # type: ignore[attr-defined]


def failure_penalized_composition_macro(
    rows: Iterable[tuple[str, AdapterResult, float | None]],
) -> float:
    by_composition: dict[str, list[float]] = defaultdict(list)
    for composition, result, primary_f1 in rows:
        if not composition:
            raise ValueError("Composition identity is required")
        result.validate()
        if result.status is RunStatus.SUCCEEDED:
            if primary_f1 is None or not 0 <= primary_f1 <= 1:
                raise ValueError("A successful result requires a primary F1 in [0, 1]")
            score = primary_f1
        elif result.status is RunStatus.FAILED:
            if primary_f1 is not None:
                raise ValueError("Failed results cannot carry an accuracy score")
            score = 0.0
        else:
            raise ValueError("Unavailable candidates have no evaluation score")
        by_composition[composition].append(score)
    if not by_composition:
        raise ValueError("At least one result is required")
    return sum(sum(values) / len(values) for values in by_composition.values()) / len(by_composition)
