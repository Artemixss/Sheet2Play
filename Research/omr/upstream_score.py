#!/usr/bin/env python3
"""Score the upstream candidates against the shipped 465 captures, raw and with the timing fix.

`plans/2026-10-17-upstream-exporter-480.md`, step 3. Every engine is scored on the same exact
labels by `displacement_correct`'s own path: `control` is the app as captured (checked against
each capture's payload) and `fixed` is the shipped timing fix, the frozen
`fit+anchor-all-keep3-even-time`. Each candidate is paired with the shipped `homr465` score by
score, with the plan's bootstrap. `homr465-ab369ac` against `homr465` is the effect of upstream's
code alone; `homr480-ab369ac` against `homr465-ab369ac` is the effect of the weights (and the FP32
decoder). Page latency compares the two candidates, which ran interleaved in one session.

    Bridge\\.venv-homr-gpu\\Scripts\\python.exe -I -B Research/omr/upstream_score.py --splits dev dev-b
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "src"))
sys.path.insert(0, str(HERE))

import timing_correct  # noqa: E402,F401  (installs the frozen variant and its page loader)
import displacement_correct as dc  # noqa: E402
from summarize_homr_pair import bootstrap_interval  # noqa: E402

SHIPPED = "homr465"
CANDIDATES = ("homr465-ab369ac", "homr480-ab369ac")
FIXED = json.loads(timing_correct.FREEZE.read_text())["variant"]
METRICS = ("onset_duration_f1", "onset_f1", "pitch_f1")
PAIRS = (("homr465-ab369ac", SHIPPED, "upstream code, 465 weights"),
         ("homr480-ab369ac", SHIPPED, "upstream code, 480 weights"),
         ("homr480-ab369ac", "homr465-ab369ac", "480 weights alone"))
REPORT = HERE / "reports/upstream-480"


def paired(rows: dict, items: list, left: str, right: str, variant: str) -> dict:
    out = {}
    for metric in METRICS:
        differences = [rows[item["id"]][left][variant][metric] - rows[item["id"]][right][variant][metric]
                       for item in items]
        lower, upper, p_value = bootstrap_interval(differences)
        out[metric] = {"gain": round(statistics.fmean(differences), 4), "gain_95": [round(lower, 4), round(upper, 4)],
                       "one_sided_p": round(p_value, 4)}
    onset = [rows[item["id"]][left][variant]["onset_f1"] - rows[item["id"]][right][variant]["onset_f1"]
             for item in items]
    out["scores_better"] = sum(value > 0.0001 for value in onset)
    out["scores_worse"] = sum(value < -0.0001 for value in onset)
    out["worst_drop"] = round(min(onset), 4)
    return out


def latency(items: list, engine: str) -> dict:
    seconds = sorted(second for item in items for second in json.loads(
        (dc.RULER / "captures" / engine / item["id"] / "result.json").read_text())["page_seconds"])
    return {"pages": len(seconds), "median": round(statistics.median(seconds), 2),
            "p95": round(seconds[min(len(seconds) - 1, int(0.95 * len(seconds)))], 2)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--splits", nargs="+", default=["dev", "dev-b"], choices=("dev", "dev-b", "test", "test-b"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    items = [item for item in dc.manifest_items(tuple(args.splits))
             if all((dc.RULER / "captures" / engine / item["id"] / "result.json").is_file()
                    for engine in (SHIPPED, *CANDIDATES))]
    dc.ENGINES = (SHIPPED, *CANDIDATES)
    manifest = json.loads(dc.MANIFEST.read_text())
    rows = dc.evaluate(items, ("control", FIXED), manifest["truth_flags"])
    summary = {"scores": len(items), "fixed_variant": FIXED, "means": {}, "paired": {}, "failures": {}}
    for engine in dc.ENGINES:
        summary["means"][engine] = {variant: {metric: round(statistics.fmean(rows[item["id"]][engine][variant][metric]
                                                                               for item in items), 4)
                                              for metric in METRICS} for variant in ("control", FIXED)}
        summary["failures"][engine] = [item["id"] for item in items if rows[item["id"]][engine]["status"] != "ok"]
    for left, right, label in PAIRS:
        summary["paired"][f"{left} vs {right}"] = {"meaning": label} | {
            variant: paired(rows, items, left, right, variant) for variant in ("control", FIXED)}
    summary["latency"] = {engine: latency(items, engine) for engine in CANDIDATES}
    summary["latency"]["p95_ratio_480_to_465"] = round(summary["latency"]["homr480-ab369ac"]["p95"]
                                                      / summary["latency"]["homr465-ab369ac"]["p95"], 3)
    output = args.output or REPORT / f"score-{'-'.join(args.splits)}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"splits": args.splits, "summary": summary, "rows": rows}, indent=1) + "\n",
                      encoding="utf-8")
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
