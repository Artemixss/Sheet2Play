"""Recheck saved Stage 3 evidence for Stage 4 without inference or rescoring."""
from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path
import statistics
import sys
from typing import Any

HERE = Path(__file__).resolve().parent
OMR = HERE.parents[3]
sys.path.insert(0, str(OMR))

from phase3_score import _summary, _percentile
from screening_common import (WORKSPACE, completed_path, digest, output_root,
                              read_json, write_new)
from screening_consolidated_report import (ROSTER, cpu_candidate, cpu_operation,
                                          outcome_counts, same_sample)
from screening_homr_analysis import operation_evidence, practical_evidence
from screening_homr_statistics import paired_statistics
from screening_report import holm_adjust, verified_candidate
from screening_score import require_complete_results
from sheet2play_omr.adapter_contract import sha256_file

REPORT = OMR / "reports/screening/v1/2c98d5638c36/reports/consolidated-stage3-836fb923bb33/report.json"
EXPECTED = "22423ca7343b5382881577b6b6146066974cfd35710a48d964faa04b1ef8bb85"


def require_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(f"Saved evidence differs: {label}")


def require_hash(path: Path, expected: str) -> None:
    require_equal(sha256_file(path), expected, str(path))


def timeline_diagnostics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    successful = [row for row in rows if row["status"] == "succeeded"]
    lengths = [abs(float(Fraction(row["timeline_length_error"]))) for row in successful
               if row["timeline_length_error"] is not None]
    return {"time_unit": "quarter notes", "successful_page_count": len(successful),
            "measured_timeline_count": len(lengths),
            "absolute_timeline_error_median": statistics.median(lengths) if lengths else None,
            "absolute_timeline_error_p95": _percentile(lengths, 0.95),
            "successful_first_divergence_measure_1_count": sum(
                row["first_divergent_measure"] == 1 for row in successful),
            "successful_no_divergence_count": sum(
                row["first_divergent_measure"] is None for row in successful),
            "failed_page_count": len(rows) - len(successful),
            "interpretation": "Timeline summaries condition on successes. Failures retain null length and a measure-1 sentinel; primary metrics retain failure penalties. Errors can reflect recognition, representation or conversion and do not establish a cause.",
            "per_page": [{key: row[key] for key in (
                "item_id", "status", "timeline_length_error", "first_divergent_measure")} for row in rows]}


def check_summary(rows: list[dict[str, Any]], manifest: dict[str, Any],
                  candidate: str, saved: dict[str, Any]) -> None:
    lookup = {item["id"]: item for item in manifest["items"]}
    rebuilt = _summary(rows, lookup, {"training_overlap": saved["training_overlap"]}, candidate)
    for key, value in rebuilt.items():
        if key not in {"scope", "latency_seconds"}:
            require_equal(saved[key], value, f"{candidate} summary {key}")
    times = [row["elapsed_seconds"] for row in rows
             if row.get("timing_source") == "screening_complete_path"]
    require_equal(saved["latency_seconds"], {
        "median": statistics.median(times) if times else None,
        "p95": _percentile(times, 0.95), "includes_failures": True,
        "comparable_page_count": len(times),
        "excluded_noncomparable_page_count": len(rows) - len(times)}, f"{candidate} latency")


def check_candidate(candidate: str, report: dict[str, Any],
                    sample: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source = report["sources"][candidate]
    path = WORKSPACE / source["manifest"]
    require_hash(path, source["manifest_sha256"])
    manifest = read_json(path)
    same_sample(sample, manifest)
    config = manifest["candidates"][candidate]
    require_equal(digest(config["identity"]), config["identity_sha256"], f"{candidate} identity")
    require_equal(config["identity_sha256"], source["configuration_sha256"], f"{candidate} configuration")
    for name, expected in config["identity"]["source_files"].items():
        require_hash(WORKSPACE / name, expected)
    root = output_root(path)
    require_complete_results(root, manifest, candidate)
    if candidate in ROSTER[:3]:
        rows, summary, summary_source = verified_candidate(root, manifest, candidate)
        operation = operation_evidence(root, manifest, candidate)
    else:
        rows, summary, summary_source = cpu_candidate(root, manifest, candidate)
        operation = cpu_operation(root, manifest, candidate)
    require_equal(summary_source, source["summary"], f"{candidate} summary source")
    require_equal(summary, report["candidate_summaries"][candidate], f"{candidate} saved summary")
    require_equal(operation, report["operations"][candidate], f"{candidate} operating evidence")
    require_equal(outcome_counts(rows), report["outcome_counts"][candidate], f"{candidate} outcomes")
    require_equal([{ "item_id": row["item_id"], "error": row["error"]}
                   for row in rows if row["status"] == "failed"],
                  report["failed_pages"][candidate], f"{candidate} failed pages")
    check_summary(rows, manifest, candidate, summary)
    artifact_count = 0
    for item in manifest["items"]:
        result = completed_path(root, candidate, item["id"], config["identity_sha256"]) / "result.json"
        require_hash(result, source["result_sha256"][item["id"]])
        artifact_count += len(read_json(result)["artifacts"])
    if (root / "worker.lock").exists() or operation["session"]["active_since_utc"] is not None:
        raise ValueError(f"Candidate session/lock remains active: {candidate}")
    return rows, {"result_count": len(rows), "score_count": len(rows),
                  "declared_artifacts_verified": artifact_count,
                  "summary_recalculated_from_saved_scores": True,
                  "full_duration_matrix_and_metrics_recalculated": True,
                  "session_closed": True, "worker_lock_absent": True}


def audit() -> dict[str, Any]:
    require_hash(REPORT, EXPECTED)
    report = read_json(REPORT)
    markdown_sha256 = sha256_file(REPORT.with_name("REPORT.md"))
    require_equal(report["candidates"], list(ROSTER), "roster")
    require_equal((report["pages"], report["compositions"]), (59, 18), "coverage")
    for name, expected in report["analysis_source_sha256"].items():
        require_hash(OMR / name, expected)
    sample = read_json(WORKSPACE / report["sources"]["zeus_page"]["manifest"])
    require_equal(sample["sample_sha256"], report["sample_sha256"], "sample")
    require_hash(OMR / "reports/phase1/scoring-protocol.json", sample["scoring_protocol_sha256"])
    require_hash(OMR / "src/sheet2play_omr/phase3_scoring.py", sample["scorer_sha256"])
    require_hash(OMR / "reports/phase3/phase3-config-freeze-v1-89f385c8790b.json",
                 sample["historical_phase3_freeze_sha256"])
    for item in sample["items"]:
        require_hash(WORKSPACE / item["image_path"], item["image_sha256"])
        require_hash(WORKSPACE / item["reference_path"], item["reference_sha256"])
    rows, checks = {}, {}
    for candidate in ROSTER:
        rows[candidate], checks[candidate] = check_candidate(candidate, report, sample)
        print(json.dumps({"candidate": candidate, **checks[candidate]}), flush=True)
    paired = {f"{candidate}_minus_{baseline}": paired_statistics(rows[candidate], rows[baseline], int(sample["seed"]))
              for baseline in ("homr_page", "fine_tuned_homr") for candidate in ROSTER if candidate != baseline}
    adjusted = holm_adjust({name: value["one_sided_superiority_p"] for name, value in paired.items()})
    for name, value in paired.items():
        value["holm_adjusted_superiority_p"] = adjusted[name]
    require_equal(paired, report["paired"], "all eight paired statistics")
    protocol = read_json(OMR / "reports/phase1/scoring-protocol.json")
    practical = {name: practical_evidence(report["candidate_summaries"][name],
        report["candidate_summaries"]["homr_page"], report["operations"][name], protocol) for name in ROSTER}
    require_equal(practical, report["practical"], "frozen practical eligibility")
    require_hash(REPORT, EXPECTED)
    require_hash(REPORT.with_name("REPORT.md"), markdown_sha256)
    return {"scope": "canonical_stage4_saved_evidence_audit", "report_sha256": EXPECTED,
            "report_markdown_sha256": sha256_file(REPORT.with_name("REPORT.md")),
            "audit_source_sha256": sha256_file(Path(__file__)), "candidate_checks": checks,
            "verified_results": 295, "verified_scores": 295, "paired_claims_recalculated": 8,
            "declared_artifacts_verified": sum(row["declared_artifacts_verified"] for row in checks.values()),
            "timeline_diagnostics": {name: timeline_diagnostics(values) for name, values in rows.items()},
            "new_inference_count": 0, "new_scoring_count": 0,
            "runtime_readmission": "Not required for analysis; pinned saved evidence verified without executing candidates"}


if __name__ == "__main__":
    evidence = audit()
    destination = HERE / "screen-audit.json"
    if destination.exists():
        require_equal(read_json(destination), evidence, "existing audit")
    else:
        write_new(destination, evidence)
    print(json.dumps({key: value for key, value in evidence.items()
                      if key not in {"candidate_checks", "timeline_diagnostics"}}))
