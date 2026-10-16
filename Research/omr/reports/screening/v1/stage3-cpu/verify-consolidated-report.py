"""Check complete report coverage and duration diagnostics without rerunning models."""
from collections import Counter
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from screening_common import read_json, write_new
from sheet2play_omr.adapter_contract import sha256_file

path = Path("Research/omr/reports/screening/v1/2c98d5638c36/reports/consolidated-stage3-836fb923bb33/report.json")
report = read_json(path)
expected_sha = "22423ca7343b5382881577b6b6146066974cfd35710a48d964faa04b1ef8bb85"
if sha256_file(path) != expected_sha or len(report["candidates"]) != 5 or len(report["paired"]) != 8:
    raise ValueError("Consolidated identity/roster/statistical claim coverage differs")
checks = {}
for name, summary in report["candidate_summaries"].items():
    duration = summary["duration_classification"]
    matrix, labels = duration["confusion_matrix"], duration["labels"]
    cells = {(row["actual"], row["predicted"]) for row in matrix}
    actual, predicted, correct = Counter(), Counter(), Counter()
    if len(cells) != len(matrix) or len(set(labels)) != len(labels):
        raise ValueError(f"Duplicate duration cells/labels: {name}")
    for row in matrix:
        if row["count"] <= 0 or row["actual"] not in labels or row["predicted"] not in labels:
            raise ValueError(f"Invalid duration cell: {name}")
        actual[row["actual"]] += row["count"]
        predicted[row["predicted"]] += row["count"]
        if row["actual"] == row["predicted"]:
            correct[row["actual"]] += row["count"]
    total = sum(actual.values())
    majority = max(actual.values())
    expected = {"balanced_accuracy": sum(correct[label] / count for label, count in actual.items()) / len(actual),
                "macro_f1": sum(2 * correct[label] / (actual[label] + predicted[label]) for label in labels) / len(labels),
                "majority_baseline_accuracy": majority / total,
                "majority_baseline_macro_f1": 2 * majority / (total + majority) / len(labels)}
    if (total != duration["matched_pitch_onset_notes"] or summary["scored_page_count"] != 59
            or summary["composition_count"] != 18 or len(summary["item_score_sha256"]) != 59
            or len(report["sources"][name]["result_sha256"]) != 59
            or not summary["failure_penalized_omr_ned_complete"] or summary["failure_penalized_omr_ned_count"] != 59):
        raise ValueError(f"Coverage/diagnostic support differs: {name}")
    if any(not math.isclose(duration[key], value, abs_tol=1e-12) for key, value in expected.items()):
        raise ValueError(f"Duration diagnostics do not agree with full matrix: {name}")
    checks[name] = {"verified_result_count": 59, "verified_score_count": 59,
                    "duration_matrix_cells": len(matrix), "duration_labels": len(labels), "matched_note_support": total}
for name, comparison in report["paired"].items():
    if (comparison["page_count"] != 59 or comparison["composition_count"] != 18
            or comparison["null_assignments"] != 262144 or comparison["bootstrap_resamples"] != 10000):
        raise ValueError(f"Paired comparison coverage differs: {name}")
evidence = {"report_sha256": expected_sha, "result_count": 295, "score_count": 295,
            "paired_claims": 8, "candidate_checks": checks}
destination = Path(__file__).with_name("consolidated-final-audit.json")
write_new(destination, evidence)
print(json.dumps(evidence))
