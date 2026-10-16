"""Bounded native check of pressure-gate latency before Phase 3 resume."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path.cwd() / "Research/omr/src"))

from sheet2play_omr.execution_resources import WindowsResourceSampler
from sheet2play_omr.safety_policy import SafetyLimits, admission_reason


def check_monitor(seconds: float = 45.0) -> dict:
    sampler = WindowsResourceSampler()
    limits = SafetyLimits()
    samples = []
    started = time.monotonic()
    while time.monotonic() - started < seconds:
        before = time.monotonic()
        sample = sampler()
        latency = time.monotonic() - before
        samples.append({**sample, "sampling_seconds": latency})
        reason = admission_reason(sample, limits)
        if reason or latency > 1:
            return {"passed": False, "reason": reason or "sampling_exceeded_one_second",
                    "samples": samples}
        time.sleep(0.5)
    return {"passed": True, "samples": samples,
            "max_sampling_seconds": max(row["sampling_seconds"] for row in samples),
            "peak_RAM_percent": max(row["physical_percent"] for row in samples),
            "peak_commit_percent": max(row["committed_bytes"] / row["commit_limit_bytes"] * 100
                                       for row in samples),
            "peak_observed_git_count": max(row["git_count"] for row in samples),
            "limitation": "Bounded observation does not establish a durable external-app fix"}


def main() -> int:
    result = check_monitor()
    with Path(__file__).with_name("monitor.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
    print(json.dumps({key: value for key, value in result.items() if key != "samples"}), flush=True)
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
