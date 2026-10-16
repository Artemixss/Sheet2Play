"""Three fixed development pages only; guarded resource preflight, never SMB screening."""
from __future__ import annotations

import argparse
import contextlib
from dataclasses import replace
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

import psutil

from screening_stage1_preflight import HERE, WORKSPACE, development_inventory, resource_sample
from phase3_freeze import verify_freeze
from screening_stage1_audit import FREEZE, FREEZE_HASH
from sheet2play_omr import phase2_adapters
from sheet2play_omr.adapter_contract import AdapterInput, MeasurementPath, sha256_file, write_result
from sheet2play_omr.phase2r_validation import run_with_typed_failure


def write_json(path: Path, payload: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def stop_tree(process: psutil.Process) -> None:
    with contextlib.suppress(psutil.NoSuchProcess):
        children = process.children(recursive=True)
        for child in reversed(children):
            with contextlib.suppress(psutil.NoSuchProcess):
                child.terminate()
        with contextlib.suppress(psutil.NoSuchProcess):
            process.terminate()
        _, alive = psutil.wait_procs([*children, process], timeout=5)
        for child in alive:
            with contextlib.suppress(psutil.NoSuchProcess):
                child.kill()


def persistent_command(command, *, cwd, timeout_seconds, environment=None):
    output = Path(os.environ["S2P_PREFLIGHT_OUTPUT"])
    started = time.monotonic()
    timed_out, peak_ram = False, 0
    with (output / "engine.stdout.log").open("w", encoding="utf-8") as stdout, \
            (output / "engine.stderr.log").open("w", encoding="utf-8") as stderr:
        process = subprocess.Popen(command, cwd=cwd, env=environment, stdin=subprocess.DEVNULL,
                                   stdout=stdout, stderr=stderr,
                                   creationflags=subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS)
        root = psutil.Process(process.pid)
        while process.poll() is None:
            with contextlib.suppress(psutil.Error):
                peak_ram = max(peak_ram, sum(p.memory_info().rss for p in [root, *root.children(recursive=True)]))
            if time.monotonic() - started >= timeout_seconds:
                timed_out = True
                stop_tree(root)
                break
            time.sleep(0.2)
        process.wait(timeout=10)
    return phase2_adapters.CommandResult(
        124 if timed_out else process.returncode, time.monotonic() - started,
        (output / "engine.stdout.log").read_text(encoding="utf-8", errors="replace"),
        (output / "engine.stderr.log").read_text(encoding="utf-8", errors="replace"),
        peak_ram, None, "device-wide readings are in parent resources.jsonl", timed_out)


def worker(output: Path, page_index: int) -> None:
    root = psutil.Process()
    threads = int(os.environ["S2P_PREFLIGHT_THREADS"])
    root.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    root.cpu_affinity(root.cpu_affinity()[:threads])
    planned = development_inventory()[page_index]
    item = AdapterInput(planned["item_id"], planned["item_id"].split("-")[1],
                        WORKSPACE / planned["image"]["path"], planned["image"]["sha256"],
                        MeasurementPath.COMPLETE_DOCUMENT,
                        WORKSPACE / planned["reference_path"], planned["reference_sha256"])
    adapter = phase2_adapters.ShippedHomrAdapter(WORKSPACE)
    launcher = HERE / "screening_homr_development_launcher.py"
    adapter.launcher = launcher
    adapter.config = replace(adapter.config, settings={**adapter.config.settings,
        "cpu_threads": threads, "inter_op_threads": 1, "cpu_affinity_count": threads,
        "priority": "below_normal", "development_launcher_sha256": sha256_file(launcher),
        "supervisor_sha256": sha256_file(Path(__file__))})
    phase2_adapters.run_monitored = persistent_command
    write_json(output / "identity.json", {"historical_freeze_sha256": FREEZE_HASH,
        "adapter_config": adapter.config.to_json(), "adapter_config_sha256": adapter.config.sha256,
        "input": planned, "worker_pid": os.getpid(), "worker_creation_time": root.create_time(),
        "priority": root.nice(), "cpu_affinity": root.cpu_affinity(),
        "timings_comparable_to_historical_run": False})
    result = run_with_typed_failure(adapter, item, output / "raw")
    write_result(output / "candidate-result.json", result)


def pressure_expired(now: float, since: float | None, blocked: bool) -> tuple[float | None, bool]:
    since = (now if since is None else since) if blocked else None
    return since, since is not None and now - since >= 30


def run_page(output: Path, index: int, deadline: float) -> dict[str, Any]:
    output.mkdir()
    temporary = output / "temporary"
    temporary.mkdir()
    threads = max(1, (os.cpu_count() or 1) // 2)
    env = {**os.environ, "S2P_PREFLIGHT_THREADS": str(threads),
           "S2P_PREFLIGHT_OUTPUT": str(output), "TEMP": str(temporary), "TMP": str(temporary),
           "PYTHONUNBUFFERED": "1"}
    for key in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        env[key] = str(threads)
    command = [sys.executable, str(Path(__file__).resolve()), "--output", str(output),
               "--worker-index", str(index)]
    start, pressure_since = time.monotonic(), None
    reason, samples = None, []
    write_json(output / "attempt.json", {"status": "pending", "command": command,
        "working_directory": str(WORKSPACE), "started_utc": datetime.now(timezone.utc).isoformat()})
    with (output / "worker.stdout.log").open("w") as stdout, (output / "worker.stderr.log").open("w") as stderr:
        process = subprocess.Popen(command, cwd=WORKSPACE, env=env, stdout=stdout, stderr=stderr,
                                   stdin=subprocess.DEVNULL,
                                   creationflags=subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS)
        root = psutil.Process(process.pid)
        write_json(output / "process.json", {"pid": process.pid, "creation_time": root.create_time(),
                                             "executable": root.exe(), "command": command})
        try:
            with (output / "resources.jsonl").open("w", encoding="utf-8") as stream:
                while True:
                    sample = resource_sample()
                    with contextlib.suppress(psutil.Error):
                        sample["worker_tree_rss_bytes"] = sum(p.memory_info().rss for p in [root, *root.children(recursive=True)])
                    samples.append(sample)
                    stream.write(json.dumps(sample) + "\n")
                    stream.flush()
                    now = time.monotonic()
                    pressure_since, expired = pressure_expired(now, pressure_since, bool(sample["admission_blockers"]))
                    if expired or now >= deadline - 30:
                        reason = "resource_interruption" if expired else "session_limit"
                        stop_tree(root)
                        break
                    if process.poll() is not None:
                        break
                    time.sleep(max(0, start + len(samples) * 5 - time.monotonic()))
            process.wait(timeout=10)
        finally:
            if process.poll() is None:
                stop_tree(root)
    report = output / "candidate-result.json"
    outcome = {"status": "pending", "reason": reason, "elapsed_seconds": time.monotonic() - start,
               "exit_code": process.returncode, "sample_count": len(samples),
               "peak_ram_percent": max(s["ram_percent"] for s in samples),
               "peak_worker_tree_rss_bytes": max(s.get("worker_tree_rss_bytes", 0) for s in samples),
               "peak_device_vram_mib": max((g["used_mib"] for s in samples for g in s["device_wide_gpu"] or []), default=None)}
    if reason is None and process.returncode == 0 and report.is_file():
        result = json.loads(report.read_text())
        if result["status"] in {"succeeded", "failed"}:
            outcome.update(status=result["status"], report_sha256=sha256_file(report), error=result["error"])
    write_json(output / "outcome.json", outcome)
    return outcome


def run(output: Path, max_pages: int) -> None:
    if not 1 <= max_pages <= 3:
        raise ValueError("Stage 1 permits at most three development pages")
    # Exclusive lock is intentionally retained after interruption for checked recovery.
    lock = HERE / ".runtime/screening-stage1-development.lock"
    with lock.open("x", encoding="utf-8") as stream:
        json.dump({"pid": os.getpid(), "creation_time": psutil.Process().create_time(), "output": str(output)}, stream)
    try:
        output.mkdir(parents=True, exist_ok=False)
        deadline = time.monotonic() + 14400
        if sha256_file(FREEZE) != FREEZE_HASH:
            raise ValueError("Historical freeze changed")
        verify_freeze(FREEZE)
        planned = development_inventory()
        write_json(output / "session.json", {"status": "running", "pages": planned[:max_pages],
            "command": sys.argv, "working_directory": str(WORKSPACE),
            "source_sha256": sha256_file(Path(__file__)), "screening_inference_started": False})
        outcomes = []
        for index in range(max_pages):
            admission = resource_sample()
            write_json(output / f"admission-{index + 1}.json", admission)
            if admission["admission_blockers"] or time.monotonic() >= deadline - 30:
                outcomes.append({"page": planned[index]["item_id"], "status": "pending", "reason": "admission_blocked"})
                break
            outcome = run_page(output / f"page-{index + 1}", index, deadline)
            outcomes.append({"page": planned[index]["item_id"], **outcome})
            print(json.dumps(outcomes[-1]), flush=True)
            if outcome["status"] == "pending":
                break
        write_json(output / "summary.json", {"outcomes": outcomes, "planned_count": max_pages,
            "remaining_count": max_pages - sum(o["status"] != "pending" for o in outcomes),
            "screening_inference_started": False})
        session = json.loads((output / "session.json").read_text())
        session["status"] = "stopped"
        write_json(output / "session.json", session)
    finally:
        lock.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--worker-index", type=int, choices=range(3), help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker_index is None:
        run(args.output.resolve(), args.max_pages)
    else:
        worker(args.output.resolve(), args.worker_index)


if __name__ == "__main__":
    main()
