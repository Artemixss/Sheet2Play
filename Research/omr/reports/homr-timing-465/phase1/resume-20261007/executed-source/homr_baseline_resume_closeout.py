"""Close a resource-stopped Phase 1 resumption without changing older evidence."""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

from homr_baseline import digest, save
from homr_baseline_closeout import verify_rows


def read(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def identity(path: Path) -> dict:
    return {"path": str(path.resolve()), "sha256": digest(path)}


def review_traces(evidence: Path, resumed: Path, analysis: dict, ledger: list[dict]) -> list[dict]:
    old = read(evidence / "failure-traces.json")
    for trace in old:
        verify_rows(trace["artifacts"] + [trace["reference"]])
    findings = read(resumed / "reviewed-findings.json")
    references = {row["item_id"]: row for row in ledger}
    rows = {row["item_id"]: row for row in analysis["development"]}
    traces = list(old)
    for item, finding in findings.items():
        row = rows[item]
        if row["status"] != "complete" or "first_difference" not in row:
            raise ValueError("Finding lacks completed reference trace: " + item)
        root = resumed / "development" / item
        artifacts = [identity(root / name) for name in
                     ("input.png", f"input_staff-{finding['crop_index']}_input.jpg",
                      "tokens.json", "input.musicxml", "result.json")]
        traces.append({"item_id": item, "first_difference": row["first_difference"],
                       "earliest_demonstrated_stage": finding["stage"], "finding": finding["finding"],
                       "method": "Visual source/native crop review, pre-cleanup and cleaned tokens, literal XML and timed events; no reference-driven correction",
                       "reference": references[item]["reference"], "artifacts": artifacts,
                       "diagnostic_only": row["diagnostic_only"]})
    save(resumed / "failure-traces.json", traces)
    return traces


def verify_capture_set(evidence: Path, resumed: Path, original: dict, analysis: dict) -> tuple[int, int]:
    old_count = 0
    for row in original["development"]:
        path = evidence / "development" / row["item_id"] / "result.json"
        if digest(path) != row["result_sha256"]:
            raise ValueError("Original receipt changed: " + str(path))
        old_count += verify_rows(read(path)["artifacts"])
    new_count = 0
    for row in analysis["development"]:
        if "receipt" not in row:
            continue
        path = Path(row["receipt"])
        if digest(path) != row["receipt_sha256"]:
            raise ValueError("Resumed analysis receipt changed")
        if not row.get("reused_pre_failure_evidence"):
            new_count += verify_rows(read(path)["artifacts"])
    return old_count, new_count


def closeout(evidence: Path, resumed: Path) -> dict:
    inventory = read(evidence / "runtime-inventory.json")
    ledger = read(evidence / "reference-eligibility.json")
    analysis_path = resumed / "analysis-reviewed/development-analysis.json"
    analysis = read(analysis_path)
    protected = verify_rows(inventory["homr_source"] + inventory["active_weights"] +
                            inventory["installed_bridge"] + inventory["tokenizers"] +
                            [inventory["python"], inventory["executable"]])
    for row in ledger:
        verify_rows([row["image"], row["reference"]])
    old_count, new_count = verify_capture_set(evidence, resumed, read(evidence / "development-analysis.json"), analysis)
    pages = read(Path(analysis["page_ledger"]))["pages"]
    if digest(Path(analysis["page_ledger"])) != analysis["page_ledger_sha256"]:
        raise ValueError("Page ledger changed")
    for page in pages:
        verify_rows([{"path": page["bounded_reference"], "sha256": page["bounded_reference_sha256"]},
                     {"path": page["rendered_pdf_page"], "sha256": page["rendered_pdf_page_sha256"]}])
    traces = review_traces(evidence, resumed, analysis, ledger)
    suite = ET.parse(resumed / "regression.xml").getroot().find("testsuite")
    counters = {key: int(suite.attrib[key]) for key in ("tests", "failures", "errors", "skipped")}
    if counters["failures"] or counters["errors"]:
        raise ValueError("Regression failed")
    network = read(resumed / "network-closeout.json")
    if (network["Processes"] or network["RootWorkerLockPresent"] or network["BlockedActionsPresent"]
            or network["RequestedResearchNetworkTransfers"] or analysis["phase2_started"]):
        raise ValueError("Closure scope/process/network check failed")
    sources = resumed / "executed-source"
    sources.mkdir(exist_ok=False)
    for name in ("homr_baseline_infer.py", "homr_baseline_resources.py", "homr_baseline_pages.py",
                 "homr_baseline_resume_analyze.py", "homr_baseline_resume_closeout.py"):
        path = Path(__file__).with_name(name)
        ast.parse(path.read_text(encoding="utf-8"))
        shutil.copy2(path, sources / name)
    shutil.copy2(Path(__file__).parent / "tests/test_homr_baseline.py", sources / "test_homr_baseline.py")
    jobs = {path.parent.name: {key: read(path).get(key) for key in
                              ("status", "worker_exit_code", "stop_reason", "elapsed_seconds")}
            for path in sorted((resumed / "jobs").glob("*/result.json"))}
    result = {"phase": 1, "status": "partial; resource-stopped", "phase2_started": False,
              "runtime_identity": inventory["identity_sha256"], "protected_artifacts_verified": protected,
              "original_inference_artifacts_verified": old_count, "resumed_inference_artifacts_verified": new_count,
              "inputs_and_references_verified": len(ledger), "generated_controls_scored": analysis["generated_controls_scored"],
              "open_captures_completed": analysis["completed_xml"] - analysis["generated_controls_scored"],
              "resumed_failed": analysis["recovery_failures"], "not_attempted": analysis["not_attempted"],
              "page_pixel_identity_verified": sum(p["pixel_identity_verified"] for p in pages),
              "page_ranges_verified": sum(p["range_verified"] for p in pages), "failure_traces": len(traces),
              "regression": counters, "network": network, "jobs": jobs,
              "remaining": [r["item_id"] for r in analysis["development"] if r["status"] != "complete"],
              "artifacts": [identity(p) for p in [analysis_path, Path(analysis["page_ledger"]),
                              resumed / "failure-traces.json", resumed / "reviewed-findings.json",
                              resumed / "regression.xml"] + sorted(sources.glob("*.py"))]}
    save(resumed / "closeout.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--resumed", type=Path, required=True)
    args = parser.parse_args()
    result = closeout(args.evidence, args.resumed)
    print(json.dumps({key: result[key] for key in ("status", "protected_artifacts_verified",
                     "original_inference_artifacts_verified", "resumed_inference_artifacts_verified", "failure_traces")}))
