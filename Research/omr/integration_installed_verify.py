"""Freeze published-app latency evidence and apply the authorized one-time selection."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import time

from integration_qualify import WORKSPACE, sha256, save_new
from guarded_execution import run_guarded
from sheet2play_omr.safety_policy import SafetyLimits

ROOT = WORKSPACE / "Research/omr/reports/homr-465-app-integration/phase2"
LIBRARY = Path(r"C:\Users\bur4x\AppData\Local\Sheet2Play")


def select_engine() -> None:
    backup = ROOT / "installed-backup/private/settings.json"
    settings = LIBRARY / "settings.json"
    before = json.loads(backup.read_text())
    current = json.loads(settings.read_text())
    if current != before:
        raise ValueError("Release unexpectedly changed real saved settings")
    marker = ROOT / "real-engine-selection.json"
    if marker.exists():
        raise FileExistsError("One-time selection already has a receipt")
    updated = {**before, "omr_engine": "homr465"}
    temporary = settings.with_suffix(".integration.tmp")
    with temporary.open("x", encoding="utf-8") as stream:
        json.dump(updated, stream, indent=2)
        stream.write("\n")
    temporary.replace(settings)
    if json.loads(settings.read_text()) != updated:
        raise ValueError("Saved selection differs from the authorized update")
    save_new(marker, {"before_sha256": sha256(backup), "after_sha256": sha256(settings),
                     "changed_fields": ["omr_engine"], "engine": "homr465"})
    print("Real saved engine set to465; all other settings preserved.")


def latency() -> None:
    from integration_analyze import percentile95
    input_path = ROOT.parent / "phase1/qualification/inputs.json"
    rows = json.loads(input_path.read_text())
    if len(rows) != 14:
        raise ValueError("Unexpected matched input count")
    identity = sha256(WORKSPACE / "dist/Sheet2Play.exe")
    report_rows = []
    deadline = time.monotonic() + 3600
    for row in rows:
        if time.monotonic() >= deadline:
            raise TimeoutError("Installed qualification session expired")
        source = Path(row["image"]["path"])
        if sha256(source) != row["image"]["sha256"]:
            raise ValueError("Matched input identity drift")
        if sha256(WORKSPACE / "dist/Sheet2Play.exe") != identity:
            raise ValueError("Published executable changed during qualification")
        os.environ["SHEET2PLAY_HOME"] = str(ROOT / "installed-qualification-library")
        os.environ["SHEET2PLAY_SETTINGS_PATH"] = str(ROOT / "installed-qualification-settings/settings.json")
        output = ROOT / "installed-qualification" / row["item_id"]
        command = [str(WORKSPACE / "dist/Sheet2Play.exe"), "--verify-omr", str(source), "Homr465", str(output)]
        job = ROOT / "jobs" / ("installed-" + row["item_id"])
        if job.exists():
            raise FileExistsError("Do not retry an existing installed qualification job implicitly")
        result = run_guarded(command, WORKSPACE, job, SafetyLimits(max_seconds=600), lock_path=WORKSPACE / ".research-worker.lock")
        if result["status"] != "complete":
            raise RuntimeError("Installed qualification failed; review its preserved receipt")
        scan = json.loads((output / "result.json").read_text())
        if scan["LoadedFromCache"]:
            raise ValueError("Latency observation reused a cache")
        log = (job / "worker.log").read_text(errors="replace")
        native_receipts = sorted((ROOT / "installed-qualification-library/omr-jobs").glob("*/native.json"), key=lambda p: p.stat().st_mtime_ns)
        native_path = native_receipts[-1]
        native = json.loads(native_path.read_text())
        if native["status"] != "complete" or not all(str(WORKSPACE / "dist/Bridge/.runtime/homr-465/source") in p for p in native["module_origins"].values()):
            raise ValueError("Installed isolated source identity mismatch")
        if str(native_path.parent) not in log:
            raise ValueError("Native receipt cannot be attributed to this app scan")
        control = json.loads((ROOT.parent / "phase1/qualification/homr" / row["item_id"] / "result.json").read_text())
        report_rows.append({"item_id": row["item_id"], "source_sha256": row["image"]["sha256"],
                            "native_seconds": native["elapsed_seconds"], "control_native_seconds": control["elapsed_seconds"],
                            "app_scan_seconds": scan["elapsedSeconds"], "native_receipt": str(native_path), "job": str(job)})
        print(json.dumps({"item": row["item_id"], "native_seconds": native["elapsed_seconds"], "status": "complete"}), flush=True)
    candidate = percentile95([r["native_seconds"] for r in report_rows])
    control = percentile95([r["control_native_seconds"] for r in report_rows])
    save_new(ROOT / "installed-latency.json", {"executable_sha256": identity, "rows": report_rows,
        "p95_native_seconds": candidate, "control_p95_native_seconds": control, "ratio": candidate / control,
        "control_scope": "Fresh Phase1 matched no-title426 pages in the same unchanged app interpreter; no cached results"})
    if candidate > 2 * control:
        raise RuntimeError("Installed-runtime p95 exceeds the selected2x latency gate")
    print(json.dumps({"p95_native_seconds": candidate, "control_p95_native_seconds": control, "ratio": candidate / control}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("select", "latency"))
    arguments = parser.parse_args()
    select_engine() if arguments.mode == "select" else latency()
