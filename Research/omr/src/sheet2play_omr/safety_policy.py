"""Operational safety policy, separate from frozen evaluation identities."""
from __future__ import annotations

from dataclasses import dataclass
import math

GIB = 1024**3


@dataclass(frozen=True)
class SafetyLimits:
    # Optional per-worker memory cap. None (the default since 2026-10-17, at the user's request)
    # leaves a worker bounded by the system stops below instead of a fixed allowance.
    worker_bytes: int | None = None
    max_seconds: float = 4 * 3600 - 30
    active_processes: int = 16
    system_stop_percent: int = 85
    commit_headroom_bytes: int = 4 * GIB

    def __post_init__(self) -> None:
        for name in ("active_processes", "system_stop_percent", "commit_headroom_bytes"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if self.worker_bytes is not None and (
                isinstance(self.worker_bytes, bool) or not isinstance(self.worker_bytes, int)
                or self.worker_bytes < 64 * 1024**2):
            raise ValueError("A worker allowance, when set, must be an integer of at least 64 MiB")
        if not 50 <= self.system_stop_percent <= 90:
            raise ValueError("System pressure threshold must be between 50 and 90 percent")
        if not 2 * GIB <= self.commit_headroom_bytes <= 8 * GIB:
            raise ValueError("Commit headroom must be between 2 and 8 GiB")
        if (isinstance(self.max_seconds, bool) or not isinstance(self.max_seconds, (int, float))
                or not math.isfinite(self.max_seconds)
                or not 0 < self.max_seconds <= 4 * 3600 - 30):
            raise ValueError("Deadline must be positive and below the four-hour session limit")


def blocking_reason(sample: dict, elapsed_seconds: float, limits: SafetyLimits) -> str | None:
    required = ("committed_bytes", "commit_limit_bytes", "physical_percent",
                "git_count", "git_private_bytes")
    if any(name not in sample for name in required):
        raise ValueError("Incomplete resource sample")
    for name in required:
        value = sample[name]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"Invalid resource counter: {name}")
        if value < 0:
            raise ValueError(f"Negative resource counter: {name}")
        if name != "physical_percent" and not isinstance(value, int):
            raise ValueError(f"Counter must be an integer: {name}")
    committed, capacity = sample["committed_bytes"], sample["commit_limit_bytes"]
    if capacity <= 0 or committed > capacity or sample["physical_percent"] > 100:
        raise ValueError("Invalid memory totals")
    if (isinstance(elapsed_seconds, bool) or not isinstance(elapsed_seconds, (int, float))
            or not math.isfinite(elapsed_seconds) or elapsed_seconds < 0):
        raise ValueError("Invalid elapsed time")
    if elapsed_seconds >= limits.max_seconds:
        return "session_deadline"
    if committed / capacity * 100 >= limits.system_stop_percent:
        return f"system_commit_at_or_above_{limits.system_stop_percent}_percent"
    if capacity - committed < limits.commit_headroom_bytes:
        return "system_commit_headroom_below_required_reserve"
    if sample["physical_percent"] >= limits.system_stop_percent:
        return f"physical_RAM_at_or_above_{limits.system_stop_percent}_percent"
    return None


def admission_reason(sample: dict, limits: SafetyLimits) -> str | None:
    reason = blocking_reason(sample, 0, limits)
    if reason:
        return reason
    if limits.worker_bytes is not None and             sample["commit_limit_bytes"] - sample["committed_bytes"] < limits.worker_bytes + limits.commit_headroom_bytes:
        return "insufficient_commit_headroom_for_worker_budget"
    return None
