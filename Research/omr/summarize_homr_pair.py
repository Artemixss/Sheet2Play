"""Summarize paired, composition-grouped HOMR canary checkpoints."""

from __future__ import annotations

import argparse
import json
import random
import statistics
from collections import defaultdict
from pathlib import Path


METRICS = ("pitch_f1", "onset_f1", "onset_duration_f1")
RESAMPLES = 10_000
SEED = 20260924


def load_checkpoint(path: Path) -> dict[str, object]:
    document = json.loads(path.read_text(encoding="utf-8"))
    rows = document.get("rows")
    if not isinstance(rows, dict) or len(rows) != 100:
        raise ValueError(f"Expected 100 completed checkpoint rows: {path}")
    return document


def row_metric(row: dict[str, object], metric: str) -> float:
    values = row.get("metrics")
    return float(values[metric]) if isinstance(values, dict) else 0.0


def grouped_differences(
    baseline: dict[str, object], candidate: dict[str, object], metric: str
) -> tuple[list[float], list[float], list[float]]:
    baseline_rows = baseline["rows"]
    candidate_rows = candidate["rows"]
    if set(baseline_rows) != set(candidate_rows):
        raise ValueError("Candidate and baseline must contain identical item IDs")
    groups: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for item_id, old in baseline_rows.items():
        new = candidate_rows[item_id]
        group = old.get("composition_group")
        if not group or group != new.get("composition_group"):
            raise ValueError(f"Composition group mismatch: {item_id}")
        groups[str(group)].append((row_metric(old, metric), row_metric(new, metric)))
    old_group_means = [statistics.fmean(old for old, _ in values) for values in groups.values()]
    new_group_means = [statistics.fmean(new for _, new in values) for values in groups.values()]
    differences = [new - old for old, new in zip(old_group_means, new_group_means)]
    return old_group_means, new_group_means, differences


def bootstrap_interval(group_differences: list[float]) -> tuple[float, float, float]:
    rng = random.Random(SEED)
    count = len(group_differences)
    samples = sorted(
        statistics.fmean(group_differences[rng.randrange(count)] for _ in range(count))
        for _ in range(RESAMPLES)
    )
    one_sided_p = (1 + sum(value <= 0 for value in samples)) / (RESAMPLES + 1)
    return samples[250], samples[9750], one_sided_p


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    baseline = load_checkpoint(args.baseline)
    candidate = load_checkpoint(args.candidate)
    if baseline["identity"]["manifest_sha256"] != candidate["identity"]["manifest_sha256"]:
        raise ValueError("Candidates used different frozen manifests")
    if baseline["identity"]["protocol_sha256"] != candidate["identity"]["protocol_sha256"]:
        raise ValueError("Candidates used different scoring protocols")

    measurements = {}
    for metric in METRICS:
        old, new, differences = grouped_differences(baseline, candidate, metric)
        lower, upper, p_value = bootstrap_interval(differences)
        measurements[metric] = {
            "baseline": statistics.fmean(old),
            "candidate": statistics.fmean(new),
            "absolute_gain": statistics.fmean(differences),
            "paired_bootstrap_95pct_interval": [lower, upper],
            "one_sided_p_value": p_value,
        }
    report = {
        "item_count": len(baseline["rows"]),
        "composition_groups": len(grouped_differences(baseline, candidate, METRICS[0])[2]),
        "baseline_failures": sum(row.get("metrics") is None for row in baseline["rows"].values()),
        "candidate_failures": sum(row.get("metrics") is None for row in candidate["rows"].values()),
        "bootstrap_resamples": RESAMPLES,
        "bootstrap_seed": SEED,
        "metrics": measurements,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
