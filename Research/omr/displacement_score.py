#!/usr/bin/env python3
"""Score captured 465 and 426 output against the displacement ruler's exact labels.

Phase 1 baseline of the displacement plan. Truth and prediction both pass through the
shipped normalizer with the app's own flags (repeats expanded, grace notes kept), so the
comparison is symmetric. Per the frozen scoring protocol, the primary metric is the
composition-macro pitch+onset+duration F1, a failed capture scores 0.0, and the engines are
compared paired by composition with a 10,000-resample bootstrap.

The drift profile is `diagnose_library_drift.diagnose`: best single shift, per-window offsets,
and the onset F1 recovered when each 16-quarter window takes its own offset. That figure is
an oracle, fitted against the truth; it bounds what a blind correction could recover.

    python displacement_score.py              # writes reports/displacement/phase1/baseline.json
    python displacement_score.py --manifest reports/displacement/phase3b/manifest.json
                                              # the replan sets, baseline.json beside their manifest
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "src"))

from diagnose_library_drift import diagnose  # noqa: E402
from diagnose_rhythm import ground_truth_notes  # noqa: E402
from evaluate_library import notes_from_payload  # noqa: E402
from sheet2play_omr.metrics import calculate_note_metrics  # noqa: E402
from summarize_homr_pair import RESAMPLES, SEED, bootstrap_interval  # noqa: E402

REPORT = HERE / "reports/displacement/phase1"
CAPTURES = HERE / "data/displacement-ruler/captures"
WORKSPACE = HERE.parents[1]
ENGINES = ("homr465", "homr")
METRICS = ("onset_duration_f1", "onset_f1", "pitch_f1")


def score_item(item: dict[str, Any], engine: str, truth: list) -> dict[str, Any]:
    result = json.loads((CAPTURES / engine / item["id"] / "result.json").read_text())
    row: dict[str, Any] = {"status": result["status"], "elapsed_seconds": result["elapsed_seconds"],
                           "page_seconds": result["page_seconds"]}
    if result["status"] != "ok":
        row.update({metric: 0.0 for metric in METRICS}, code=result.get("code"),
                   error=(result.get("error") or "").replace(str(WORKSPACE) + "\\", "") or None)
        return row
    payload = json.loads((CAPTURES / engine / item["id"] / "payload.json").read_text())
    predicted = notes_from_payload(payload)
    metrics = calculate_note_metrics(predicted, truth)
    drift = diagnose(item["id"], predicted, truth, item["pages"], Fraction(16))
    row.update({metric: round(getattr(metrics, metric), 4) for metric in METRICS})
    row.update({key: drift[key] for key in ("global_offset", "recovered_onset_f1", "recovered_gain",
                                            "control_onset_f1", "control_recovered_onset_f1", "shape")},
               reference=drift["reference"], windows=drift["windows"])
    return row


def summarise(items: list[dict[str, Any]], rows: dict[str, dict[str, dict[str, Any]]]) -> dict[str, Any]:
    summary: dict[str, Any] = {"items": len(items)}
    for engine in ENGINES:
        engine_rows = [rows[item["id"]][engine] for item in items]
        ok = [row for row in engine_rows if row["status"] == "ok"]
        pages = sorted(second for row in engine_rows for second in row["page_seconds"])
        summary[engine] = {
            **{metric: round(statistics.fmean(row[metric] for row in engine_rows), 4) for metric in METRICS},
            "failures": len(engine_rows) - len(ok),
            "oracle_recovered_onset_f1": round(statistics.fmean(
                row["recovered_onset_f1"] if row["status"] == "ok" else 0.0 for row in engine_rows), 4),
            "shapes": dict(Counter(row["shape"] for row in ok)),
            "median_span_ratio": round(statistics.median(row["reference"]["span_ratio"] for row in ok), 4) if ok else None,
            "page_seconds_p50_p95": [pages[len(pages) // 2], pages[int(len(pages) * 0.95)]] if pages else None,
        }
    paired = {}
    for metric in METRICS + ("recovered_onset_f1",):
        differences = [rows[item["id"]]["homr465"].get(metric, 0.0) - rows[item["id"]]["homr"].get(metric, 0.0)
                       for item in items]
        lower, upper, p_value = bootstrap_interval(differences)
        paired[metric] = {"mean_465_minus_426": round(statistics.fmean(differences), 4),
                          "bootstrap_95": [round(lower, 4), round(upper, 4)], "one_sided_p_465_gain": round(p_value, 4)}
    summary["paired"] = paired
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--manifest", type=Path, default=REPORT / "manifest.json")
    parser.add_argument("--output", type=Path, help="default: baseline.json beside the manifest")
    parser.add_argument("--splits", nargs="*", help="score only these splits, so a held-out set stays unseen")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    if args.splits:
        manifest["items"] = [item for item in manifest["items"] if item["split"] in args.splits]
    output = args.output or args.manifest.parent / "baseline.json"
    flags = manifest["truth_flags"]
    rows: dict[str, dict[str, dict[str, Any]]] = {}
    for item in manifest["items"]:
        truth, _ = ground_truth_notes(HERE / item["label"], **flags)
        rows[item["id"]] = {engine: score_item(item, engine, truth) for engine in ENGINES}
    report = {"manifest": args.manifest.name, "truth_flags": flags, "bootstrap": {"resamples": RESAMPLES, "seed": SEED,
              "group": "composition (one item each)"}, "metrics_primary": METRICS[0], "summary": {}}
    splits = list(dict.fromkeys(item["split"] for item in manifest["items"]))
    strata = sorted({item["stratum"] for item in manifest["items"] if "stratum" in item})
    for split in splits:
        for bin_name in (None, "short", "medium", "long"):
            chosen = [item for item in manifest["items"]
                      if item["split"] == split and (bin_name is None or item["bin"] == bin_name)]
            if chosen:
                report["summary"][split if bin_name is None else f"{split}/{bin_name}"] = summarise(chosen, rows)
    for name in strata:
        report["summary"][name] = summarise([item for item in manifest["items"] if item.get("stratum") == name], rows)
    report["rows"] = rows
    output.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({key: {engine: {metric: value[engine][metric] for metric in METRICS + ("failures", "oracle_recovered_onset_f1")}
                            for engine in ENGINES} | {"paired_onset_duration": value["paired"]["onset_duration_f1"]}
                      for key, value in report["summary"].items() if "/" not in key}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
