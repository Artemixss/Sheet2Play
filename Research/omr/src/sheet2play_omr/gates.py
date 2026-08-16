from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .errors import ResearchError


@dataclass(frozen=True, slots=True)
class GateDecision:
    passed: bool
    failures: tuple[str, ...]


def baseline_adaptation_gate(candidate: dict[str, float], homr: dict[str, float]) -> GateDecision:
    failures: list[str] = []
    if candidate.get("structural_validity", 0.0) < 0.95:
        failures.append("structural validity is below 0.95")
    if candidate.get("pitch_f1", 0.0) < homr.get("pitch_f1", 0.0) - 0.02:
        failures.append("pitch F1 is more than 0.02 below homr")
    if candidate.get("onset_duration_f1", 0.0) < homr.get("onset_duration_f1", 0.0) + 0.05:
        failures.append("onset-duration F1 is less than 0.05 above homr")
    return GateDecision(not failures, tuple(failures))


def canary_gate(candidate: dict[str, float], homr: dict[str, float]) -> GateDecision:
    requirements = (
        (
            candidate.get("structural_validity", 0.0) >= 0.90,
            "structural validity is below 0.90",
        ),
        (
            candidate.get("catastrophic_page_failure_rate", 1.0) <= 0.10,
            "catastrophic-page failure rate is above 0.10",
        ),
        (
            candidate.get("pitch_f1", 0.0) >= homr.get("pitch_f1", 0.0) - 0.05,
            "pitch F1 is more than 0.05 below homr",
        ),
        (
            candidate.get("onset_duration_f1", 0.0)
            >= homr.get("onset_duration_f1", 0.0),
            "onset-duration F1 is below homr",
        ),
    )
    failures = tuple(message for passed, message in requirements if not passed)
    return GateDecision(not failures, failures)


def retention_gate(
    candidate: dict[str, float],
    homr: dict[str, float],
    *,
    deterministic: bool,
) -> GateDecision:
    requirements = (
        (
            candidate.get("structural_validity", 0.0) >= 0.95,
            "structural validity is below 0.95",
        ),
        (
            candidate.get("catastrophic_page_failure_rate", 1.0) <= 0.05,
            "catastrophic-page failure rate is above 0.05",
        ),
        (
            candidate.get("pitch_f1", 0.0) >= homr.get("pitch_f1", 0.0) - 0.02,
            "pitch F1 is more than 0.02 below homr",
        ),
        (
            candidate.get("onset_duration_f1", 0.0)
            >= homr.get("onset_duration_f1", 0.0) + 0.05,
            "onset-duration F1 is less than 0.05 above homr",
        ),
        (
            candidate.get("median_seconds_per_system", math.inf) < 30.0,
            "median latency is not below 30 seconds per system",
        ),
        (
            candidate.get("peak_vram_bytes", math.inf) < 5.5 * 1024**3,
            "peak VRAM is not below 5.5 GB",
        ),
        (deterministic, "three-run determinism failed"),
    )
    failures = tuple(message for passed, message in requirements if not passed)
    return GateDecision(not failures, failures)


def promotion_gate(candidate: dict[str, float], homr: dict[str, float]) -> GateDecision:
    requirements = (
        (candidate.get("structural_validity", 0.0) >= 1.0, "not every output is parseable and nonempty"),
        (candidate.get("pitch_f1", 0.0) >= 0.98, "pitch F1 is below 0.98"),
        (candidate.get("onset_duration_f1", 0.0) >= 0.90, "onset-duration F1 is below 0.90"),
        (
            candidate.get("onset_duration_f1", 0.0) >= homr.get("onset_duration_f1", 0.0) + 0.15,
            "onset-duration F1 is less than 0.15 above homr",
        ),
        (candidate.get("staff_accuracy", 0.0) >= 0.95, "staff accuracy is below 0.95"),
        (candidate.get("voice_accuracy", 0.0) >= 0.95, "voice accuracy is below 0.95"),
        (candidate.get("structural_assertions", 0.0) >= 1.0, "structural fixtures are not exact"),
        (candidate.get("median_seconds_per_page", math.inf) < 30.0, "median latency is not below 30 seconds"),
        (candidate.get("peak_vram_bytes", math.inf) < 5.5 * 1024**3, "peak VRAM is not below 5.5 GB"),
        (candidate.get("deterministic_runs", 0.0) >= 1.0, "three-run determinism failed"),
    )
    failures = tuple(message for passed, message in requirements if not passed)
    return GateDecision(not failures, failures)


def enforce_cloud_budget(hourly_rate: float, estimated_hours: float, maximum_cost: float = 10.0) -> float:
    values = (hourly_rate, estimated_hours, maximum_cost)
    if any(not math.isfinite(value) or value < 0 for value in values):
        raise ResearchError("BUDGET_INVALID", "adaptation", "Budget values must be finite and non-negative")
    estimated_cost = hourly_rate * estimated_hours
    if estimated_cost > maximum_cost:
        raise ResearchError(
            "BUDGET_EXCEEDED",
            "adaptation",
            f"Estimated cloud cost ${estimated_cost:.2f} exceeds the ${maximum_cost:.2f} cap",
        )
    return round(estimated_cost, 2)
