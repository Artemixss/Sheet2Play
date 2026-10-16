"""Verify the bounded title-OCR unblock without repeating inference."""
from __future__ import annotations

import ast
import json
from pathlib import Path
import re
import shutil
from urllib.parse import unquote
import xml.etree.ElementTree as ET

from homr_baseline import digest, save
from homr_baseline_closeout import verify_rows
from homr_baseline_profile import validate_profile
from homr_baseline_resume_closeout import identity, read

ROOT = Path(__file__).resolve().parent
EVIDENCE = ROOT.parent
PREVIOUS = EVIDENCE / "resume-20261007"
WORKSPACE = EVIDENCE.parents[4]


def preserved_capture_count(root: Path) -> int:
    count = 0
    for path in sorted((root / "development").glob("*/result.json")):
        count += verify_rows(read(path)["artifacts"])
    return count


def verify_new_captures(profile: dict) -> tuple[int, list[dict]]:
    count, rows = 0, []
    for path in sorted((ROOT / "development").glob("*/result.json")):
        receipt = read(path)
        if (receipt["status"] != "complete" or receipt["title_detection"] is not False
                or receipt["research_profile_identity"] != profile["identity_sha256"]
                or receipt["research_profile_sha256"] != digest(ROOT / "profile.json")):
            raise ValueError("Incomplete or mismatched title-disabled capture")
        count += verify_rows(receipt["artifacts"])
        job = read(ROOT / "jobs" / receipt["item_id"] / "result.json")
        if (job["status"] != "complete" or job["worker_exit_code"] != 0
                or job["limits"] != {"worker_bytes": 4294967296, "max_seconds": 600.0,
                                     "active_processes": 16, "system_stop_percent": 85,
                                     "commit_headroom_bytes": 4294967296}):
            raise ValueError("Inference supervisor/safeguard drift")
        samples = read(path.parent / "tokens.json")["memory"]
        rows.append({"item_id": receipt["item_id"], "receipt": identity(path),
                     "peak_private_bytes": max(s["peak_private_bytes"] for s in samples),
                     "guard_seconds": job["elapsed_seconds"]})
    if len(rows) != 15:
        raise ValueError("Expected two equivalence captures, one probe and twelve later captures")
    return count, rows


def verify_evidence() -> dict:
    inventory = read(EVIDENCE / "runtime-inventory.json")
    protected = verify_rows(inventory["homr_source"] + inventory["active_weights"]
                            + inventory["installed_bridge"] + inventory["tokenizers"]
                            + [inventory["python"], inventory["executable"]])
    profile = validate_profile(ROOT / "profile.json", inventory["identity_sha256"])
    for root in (EVIDENCE, PREVIOUS):
        frozen = [row for row in read(root / "verification.json")["artifacts"]
                  if Path(row["path"]).is_relative_to(EVIDENCE)]
        verify_rows(frozen)
    verify_rows(read(PREVIOUS / "closeout.json")["artifacts"])
    references = read(EVIDENCE / "reference-eligibility.json")
    for row in references:
        verify_rows([row["image"], row["reference"]])
    new_count, captures = verify_new_captures(profile)
    equivalence = read(ROOT / "equivalence.json")
    if not equivalence["passed"] or len(equivalence["examples"]) != 2:
        raise ValueError("Two-example equivalence gate failed")
    for row in equivalence["examples"]:
        if not row["passed"] or not all(row["checks"].values()):
            raise ValueError("Musical equivalence failed")
        verify_rows([row["baseline_receipt"], row["profile_receipt"]])
    analysis = read(ROOT / "analysis/development-analysis.json")
    if (analysis["completed_xml"] != 32 or analysis["generated_controls_scored"] != 12
            or analysis["recovery_failures"] or analysis["not_attempted"] or analysis["phase2_started"]):
        raise ValueError("Incomplete combined development capture set")
    for row in analysis["development"]:
        verify_rows([{"path": row["receipt"], "sha256": row["receipt_sha256"]}])
    pages = read(Path(analysis["page_ledger"]))["pages"]
    if digest(Path(analysis["page_ledger"])) != analysis["page_ledger_sha256"]:
        raise ValueError("Combined page ledger changed")
    for page in pages:
        if not page["range_verified"] or not page["pixel_identity_verified"]:
            raise ValueError("Unverified page range")
        verify_rows([{"path": page["bounded_reference"], "sha256": page["bounded_reference_sha256"]},
                     {"path": page["rendered_pdf_page"], "sha256": page["rendered_pdf_page_sha256"]}])
    if len(pages) != 20:
        raise ValueError("Expected twenty OpenScore page ranges")
    for case in read(ROOT / "boundaries/boundary-evidence.json")["cases"]:
        verify_rows(case["artifacts"] + [case["source_xml"], case["source_pdf"]])
    suite = ET.parse(ROOT / "regression.xml").getroot().find("testsuite")
    counters = {key: int(suite.attrib[key]) for key in ("tests", "failures", "errors", "skipped")}
    if counters != {"tests": 400, "failures": 0, "errors": 0, "skipped": 2}:
        raise ValueError("Unexpected regression outcome")
    network = read(ROOT / "network-closeout.json")
    if (network["Processes"] or network["RootWorkerLockPresent"] or network["BlockedActionsPresent"]
            or network["RequestedResearchNetworkTransfers"] or network["LimitBytes"] != 2000000000):
        raise ValueError("Process/network closure failed")
    sources = ROOT / "executed-source"
    sources.mkdir(exist_ok=False)
    for name in ("homr_baseline_infer.py", "homr_baseline_resources.py", "homr_baseline_profile.py",
                 "homr_title_equivalence.py", "homr_title_boundaries.py", "homr_baseline_resume_analyze.py"):
        source = WORKSPACE / "Research/omr" / name
        ast.parse(source.read_text(encoding="utf-8"))
        shutil.copy2(source, sources / name)
    shutil.copy2(WORKSPACE / "Research/omr/tests/test_homr_baseline.py", sources / "test_homr_baseline.py")
    old_traces = read(PREVIOUS / "failure-traces.json")
    for trace in old_traces:
        verify_rows(trace["artifacts"] + [trace["reference"]])
    reviewed = {row["item_id"] for row in old_traces}
    pending = [r["item_id"] for r in analysis["development"]
               if r.get("first_difference") and r["item_id"] not in reviewed]
    jobs = {p.parent.name: {k: read(p).get(k) for k in
                           ("status", "worker_exit_code", "stop_reason", "elapsed_seconds")}
            for p in sorted((ROOT / "jobs").glob("*/result.json"))}
    paths = [ROOT / p for p in ("profile.json", "equivalence.json", "sequence.json",
             "analysis/development-analysis.json", "boundaries/page-correspondence.json",
             "boundaries/boundary-evidence.json", "boundaries/reviewed-findings.json", "regression.xml",
             "network-closeout.json")] + sorted(sources.glob("*.py"))
    result = {"status": "bounded title-OCR unblock complete; Phase 1 first-error review remains",
              "phase2_started": False, "runtime_identity": inventory["identity_sha256"],
              "profile_identity": profile["identity_sha256"], "protected_artifacts_verified": protected,
              "original_inference_artifacts_verified": preserved_capture_count(EVIDENCE),
              "resumed_inference_artifacts_verified": preserved_capture_count(PREVIOUS),
              "new_inference_artifacts_verified": new_count, "new_captures": captures,
              "completed_development_inputs": 32, "page_ranges_verified": 20,
              "preserved_failure_traces": len(old_traces), "pending_first_error_reviews": pending,
              "regression": counters, "network": network, "jobs": jobs,
              "artifacts": [identity(p) for p in paths]}
    save(ROOT / "closeout.json", result)
    return result


def verify_documentation() -> None:
    result = read(ROOT / "closeout.json")
    verify_rows(result["artifacts"])
    paths = [WORKSPACE / "plans/MAIN_PLAN.md", EVIDENCE.parent / "handoff.md",
             ROOT / "REPORT.md", ROOT / "job-record.md"]
    links = 0
    for path in paths:
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            if re.match(r"\w+://", target) or target.startswith("#"):
                continue
            if not (path.parent / unquote(target.split("#", 1)[0].strip("<>"))).exists():
                raise ValueError(f"Broken local link: {path} -> {target}")
            links += 1
    if (WORKSPACE / ".research-worker.lock").exists():
        raise ValueError("Worker lock remains")
    save(ROOT / "verification.json", {"status": result["status"], "local_links_checked": links,
         "phase2_started": False, "artifacts": [identity(p) for p in paths + [Path(__file__), ROOT / "closeout.json"]]})
    print(json.dumps({"status": result["status"], "local_links_checked": links}))


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["--docs"]:
        verify_documentation()
    elif not sys.argv[1:]:
        closure = verify_evidence()
        print(json.dumps({key: closure[key] for key in ("status", "protected_artifacts_verified",
              "original_inference_artifacts_verified", "resumed_inference_artifacts_verified",
              "new_inference_artifacts_verified", "pending_first_error_reviews", "regression")}))
    else:
        raise ValueError("Expected no arguments or --docs")
