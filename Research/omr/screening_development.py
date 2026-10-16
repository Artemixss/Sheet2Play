"""Run one open development page through the exact pinned screening adapter."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

import psutil

from screening_admit import allowed_development_pages
from screening_common import (POLICY, WORKSPACE, output_root, read_json,
                              require_current_policy, screening_adapter, threads_limit,
                              verify_manifest, write_new)
from screening_run import acquire_lock, command_monitor, release_lock
from screening_stage1_development import pressure_expired, stop_tree
from screening_stage1_preflight import resource_sample
from sheet2play_omr import phase2_adapters
from sheet2play_omr.adapter_contract import AdapterInput, MeasurementPath, sha256_file
from sheet2play_omr.phase2r_validation import run_with_typed_failure


def development_blockers(sample: dict, ram_limit_percent: int) -> list[str]:
    blockers = [reason for reason in sample["admission_blockers"]
                if not (reason.startswith("system_ram_at_or_above_") and reason.endswith("_percent"))]
    if sample["ram_percent"] >= ram_limit_percent:
        blockers.append(f"system_ram_at_or_above_{ram_limit_percent}_percent")
    return blockers


def development_input(item_id: str) -> AdapterInput:
    pages = allowed_development_pages()
    if item_id not in pages:
        raise ValueError(f"Not a frozen open development page: {item_id}")
    page = pages[item_id]
    rows = [json.loads(line) for line in
            (WORKSPACE / "Research/omr/reports/phase1/development-open.jsonl")
            .read_text(encoding="utf-8").splitlines()]
    composition = next(row for row in rows if row["composition_group"] == page["composition_group"])
    item = AdapterInput(item_id, page["composition_group"],
                        WORKSPACE / page["image_path"], page["image_sha256"],
                        MeasurementPath.COMPLETE_DOCUMENT,
                        WORKSPACE / composition["musicxml_path"], composition["musicxml_sha256"])
    item.validate()
    return item


def worker(manifest_path: Path, candidate: str, item_id: str, attempt: Path) -> None:
    manifest = verify_manifest(manifest_path)
    require_current_policy(manifest)
    if candidate not in {"homr_page", "homr_455", "fine_tuned_homr"}:
        raise ValueError("Development entry supports HOMR candidates only")
    root = psutil.Process()
    threads = threads_limit()
    root.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    root.cpu_affinity(root.cpu_affinity()[:threads])
    adapter = screening_adapter(candidate, threads, sha256_file(Path(__file__).with_name("screening_run.py")))
    if adapter.config.sha256 != manifest["candidates"][candidate]["identity"]["adapter_config_sha256"]:
        raise ValueError("Live adapter configuration differs from the frozen screening identity")
    item = development_input(item_id)
    if not adapter.probe()["available"]:
        raise RuntimeError(f"HOMR runtime is unavailable: {candidate}")
    if candidate == "homr_455":
        from screening_homr_extension import candidate_environment
        os.environ.update(candidate_environment(manifest["candidates"][candidate]["identity"]))
    elif candidate == "fine_tuned_homr":
        from screening_finetune_extension import candidate_environment
        os.environ.update(candidate_environment(manifest["candidates"][candidate]["identity"]))
    phase2_adapters.run_monitored = command_monitor
    result = run_with_typed_failure(adapter, item, attempt / "raw").to_json()
    if candidate in {"homr_455", "fine_tuned_homr"}:
        result["compatibility_report"] = manifest["candidates"][candidate]["identity"]["compatibility_report"]
    write_new(attempt / "staged-result.json", result)
    write_new(attempt / "worker-identity.json", {
        "pid": root.pid, "creation_time": root.create_time(), "priority": "below_normal",
        "cpu_affinity_count": len(root.cpu_affinity()), "adapter_config_sha256": adapter.config.sha256,
        "compatibility_report": result.get("compatibility_report"),
        "development_ram_admission_percent": adapter.config.settings.get(
            "development_ram_admission_percent", POLICY["ram_admission_percent"])})


def run(manifest_path: Path, candidate: str, item_id: str, session_id: str) -> Path | None:
    manifest = verify_manifest(manifest_path)
    require_current_policy(manifest)
    if candidate not in {"homr_page", "homr_455", "fine_tuned_homr"}:
        raise ValueError("Development entry supports HOMR candidates only")
    item = development_input(item_id)
    identity = manifest["candidates"][candidate]["identity"]
    ram_limit = identity["adapter_config"]["settings"].get(
        "development_ram_admission_percent", POLICY["ram_admission_percent"])
    root = output_root(manifest_path)
    report_dir = root / "development" / candidate / manifest["candidates"][candidate]["identity_sha256"][:12]
    report = report_dir / f"{item_id}.json"
    if report.exists() or report.with_suffix(".identity.json").exists():
        raise FileExistsError(f"Development evidence already exists: {report}")
    sample = resource_sample()
    blockers = development_blockers(sample, ram_limit)
    if blockers:
        raise RuntimeError(f"Resource admission blocked: {blockers}")
    lock = acquire_lock(root)
    try:
        attempt = root / "development-attempts" / candidate / f"{session_id}-{uuid.uuid4().hex}"
        attempt.mkdir(parents=True)
        temporary = attempt / "temporary"
        temporary.mkdir()
        command = [sys.executable, str(Path(__file__).resolve()), "--manifest", str(manifest_path),
                   "--candidate", candidate, "--item-id", item_id, "--session-id", session_id,
                   "--worker-attempt", str(attempt)]
        write_new(attempt / "job.json", {"command": command, "working_directory": str(WORKSPACE),
                                         "manifest_sha256": sha256_file(manifest_path),
                                         "input_sha256": item.input_sha256,
                                         "adapter_config_sha256": identity["adapter_config_sha256"],
                                         "admission": {**sample, "development_ram_admission_percent": ram_limit,
                                                       "effective_admission_blockers": blockers},
                                         "started_utc": datetime.now(timezone.utc).isoformat()})
        environment = {**os.environ, "S2P_SCREENING_ATTEMPT": str(attempt),
                       "S2P_PREFLIGHT_THREADS": str(threads_limit()),
                       "TEMP": str(temporary), "TMP": str(temporary), "PYTHONUNBUFFERED": "1"}
        for key in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
            environment[key] = str(threads_limit())
        started, pressure_since = time.monotonic(), None
        samples = []
        reason = None
        with (attempt / "worker.stdout.log").open("x") as stdout, \
                (attempt / "worker.stderr.log").open("x") as stderr:
            process = subprocess.Popen(command, cwd=WORKSPACE, env=environment,
                                       stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                                       creationflags=subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS)
            child = psutil.Process(process.pid)
            write_new(attempt / "process.json", {"pid": child.pid, "creation_time": child.create_time(),
                                                  "executable": child.exe(), "command": command})
            try:
                with (attempt / "resources.jsonl").open("x", encoding="utf-8") as stream:
                    while True:
                        current = resource_sample()
                        effective = development_blockers(current, ram_limit)
                        current["development_ram_admission_percent"] = ram_limit
                        current["effective_admission_blockers"] = effective
                        samples.append(current)
                        stream.write(json.dumps(current) + "\n")
                        stream.flush()
                        now = time.monotonic()
                        pressure_since, expired = pressure_expired(now, pressure_since,
                                                                   bool(effective))
                        if expired or now - started >= POLICY["session_seconds"] - POLICY["shutdown_reserve_seconds"]:
                            reason = "resource_interruption" if expired else "session_limit"
                            stop_tree(child)
                            break
                        if process.poll() is not None:
                            break
                        time.sleep(max(0, started + len(samples) * POLICY["sample_seconds"] - time.monotonic()))
                process.wait(timeout=10)
            finally:
                if process.poll() is None:
                    stop_tree(child)
        write_new(attempt / "outcome.json", {"reason": reason, "worker_exit": process.returncode,
                                              "elapsed_seconds": time.monotonic() - started,
                                              "peak_system_ram_percent": max(s["ram_percent"] for s in samples),
                                              "peak_device_vram_mib": max((gpu["used_mib"] for s in samples
                                                                          for gpu in s["device_wide_gpu"] or []),
                                                                          default=None)})
        if reason or process.returncode != 0:
            return None
        result = read_json(attempt / "staged-result.json")
        if result.get("status") != "succeeded" or result.get("exit_status") != 0:
            return None
        witness = read_json(attempt / "worker-identity.json")
        if witness["adapter_config_sha256"] != identity["adapter_config_sha256"]:
            raise ValueError("Development worker identity differs")
        if witness["development_ram_admission_percent"] != ram_limit:
            raise ValueError("Development worker RAM policy differs")
        write_new(report, result)
        write_new(report.with_suffix(".identity.json"), {
            "item_id": item_id, "input_sha256": item.input_sha256,
            "adapter_config_sha256": identity["adapter_config_sha256"],
            "report_sha256": sha256_file(report),
            "resource_policy_sha256": manifest["candidates"][candidate]["identity"]["adapter_config"]["settings"]["screening_resource_policy_sha256"],
            "priority": witness["priority"], "cpu_affinity_count": witness["cpu_affinity_count"],
            "development_ram_admission_percent": witness["development_ram_admission_percent"],
            "compatibility_report": witness["compatibility_report"],
            "attempt": str(attempt.relative_to(WORKSPACE)).replace("\\", "/")})
        return report
    finally:
        release_lock(lock)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--item-id", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--worker-attempt", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker_attempt:
        worker(args.manifest.resolve(), args.candidate, args.item_id, args.worker_attempt.resolve())
    else:
        report = run(args.manifest.resolve(), args.candidate, args.item_id, args.session_id)
        print(json.dumps({"development_report": str(report) if report else None,
                          "status": "succeeded" if report else "pending_or_failed"}), flush=True)


if __name__ == "__main__":
    main()
