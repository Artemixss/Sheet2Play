"""Combine approved pre-failure controls with isolated recovery captures offline."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from homr_baseline import digest, save
from homr_baseline_analyze import duration_diagnostics, first_difference, reference_notes
from homr_baseline_closeout import verify_rows
from sheet2play_omr.research_ties import merge_ties, verify_midi
from sheet2play_omr.zeus_trace import metric_summary, normalized_notes, xml_trace


def completed_trace(row: dict, root: Path, output: Path, page: dict | None) -> dict:
    predicted = normalized_notes(root / "input.musicxml")
    segments, measures = xml_trace(root / "input.musicxml")
    result = {"production_normalized_events": [
        {"pitch": n.pitch, "onset": str(n.onset), "duration": str(n.duration),
         "staff": n.staff, "voice": n.voice} for n in predicted],
        "literal_xml_events": [n.json() for n in segments], "xml_measures": measures,
        "earliest_demonstrated_error": "Pending independent image/crop/raw-token review"}
    if row["collection"] == "generated":
        expected, reference_measures = reference_notes(row)
        result["metrics"] = metric_summary(predicted, [n.metric() for n in expected])
        result["first_difference"] = first_difference(predicted, expected, reference_measures)
        result["reference_midi"] = verify_midi(tuple(expected), output / (row["item_id"] + "-reference.mid"))
    elif page and page["range_verified"]:
        source = Path(page["bounded_reference"])
        if digest(source) != page["bounded_reference_sha256"]:
            raise ValueError("Page reference changed")
        expected_segments, reference_measures = xml_trace(source)
        expected, issues = merge_ties(expected_segments)
        result["first_difference"] = first_difference(predicted, list(expected), reference_measures)
        result["reference_tie_issues"] = list(issues)
        result["reference_interpretation"] = "Literal first-page diagnostic; ties clipped at page boundary, no repeat expansion or accuracy score"
    return result


def analyze(evidence: Path, output: Path, page_ledger: Path, destination: Path | None = None,
            fallback: Path | None = None) -> dict:
    destination = destination or output
    destination.mkdir(parents=True, exist_ok=True)
    ledger = json.loads((evidence / "reference-eligibility.json").read_text())
    original = json.loads((evidence / "development-analysis.json").read_text())
    approved = {row["item_id"]: row for row in original["development"] if "metrics" in row}
    pages = {p["item_id"]: p for p in json.loads(page_ledger.read_text())["pages"]}
    runtime = json.loads((evidence / "runtime-inventory.json").read_text())["identity_sha256"]
    rows = []
    for row in ledger:
        item_id = row["item_id"]
        root = (evidence if item_id in approved else output) / "development" / item_id
        if not (root / "result.json").exists() and fallback:
            root = fallback / "development" / item_id
        receipt = root / "result.json"
        trace = {"item_id": item_id, "status": "not_attempted_after_resource_stop",
                 "accuracy_claim": False, "diagnostic_only": row["collection"] == "open"}
        if receipt.exists():
            result = json.loads(receipt.read_text())
            if result["runtime_identity"] != runtime or result["input_sha256"] != row["image"]["sha256"]:
                raise ValueError("Capture identity mismatch")
            if result.get("research_profile_identity"):
                from homr_baseline_profile import validate_profile
                profile = validate_profile(root.parents[1] / "profile.json", runtime)
                if result["research_profile_identity"] != profile["identity_sha256"]:
                    raise ValueError("Research profile identity mismatch")
            verify_rows(result["artifacts"])
            trace.update(status=result["status"], receipt=str(receipt.resolve()),
                         receipt_sha256=digest(receipt), artifacts=result["artifacts"],
                         capture_profile=result["profile"],
                         research_profile_identity=result.get("research_profile_identity"),
                         title_detection=result.get("title_detection", True))
            if result["status"] == "complete":
                if item_id in approved:
                    trace.update({k: v for k, v in approved[item_id].items()
                                  if k not in ("status", "result_sha256", "quarantined")})
                    trace["reused_pre_failure_evidence"] = True
                else:
                    trace.update(completed_trace(row, root, destination, pages.get(item_id)))
            else:
                trace.update(error=result.get("error"),
                             earliest_demonstrated_error="Runtime allocation failure; musical attribution unavailable")
        rows.append(trace)
    duration = duration_diagnostics([r for r in rows if "metrics" in r])
    duration["interpretation"] = "Conditional on exact pitch/onset pairs in twelve authoritative generated controls; no corpus/model-ranking claim"
    report = {"development": rows, "duration": duration, "phase2_started": False,
              "completed_xml": sum(r["status"] == "complete" for r in rows),
              "generated_controls_scored": sum("metrics" in r for r in rows),
              "recovery_failures": sum(r["status"] not in ("complete", "not_attempted_after_resource_stop") for r in rows),
              "not_attempted": sum(r["status"] == "not_attempted_after_resource_stop" for r in rows),
              "page_ledger": str(page_ledger.resolve()), "page_ledger_sha256": digest(page_ledger)}
    save(destination / "development-analysis.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--page-ledger", type=Path, required=True)
    parser.add_argument("--analysis-root", type=Path)
    parser.add_argument("--fallback-root", type=Path)
    args = parser.parse_args()
    report = analyze(args.evidence, args.output, args.page_ledger, args.analysis_root, args.fallback_root)
    print(json.dumps({k: report[k] for k in ("completed_xml", "generated_controls_scored", "recovery_failures", "not_attempted")}))
