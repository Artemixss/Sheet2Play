"""Run one gated, resumable screening chunk; Stage 2 never invokes this command."""
from __future__ import annotations

import argparse
import contextlib
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
from typing import Any

import psutil

from screening_common import (POLICY, RUNNABLE, WORKSPACE, commit_completed, completed_path,
                              digest, output_root, read_json, require_current_policy,
                              result_identity, screening_adapter,
                              threads_limit, validate_result, verify_completed, verify_manifest,
                              write_new)
from screening_stage1_development import pressure_expired, stop_tree
from screening_stage1_preflight import resource_sample
from sheet2play_omr import phase2_adapters
from sheet2play_omr.adapter_contract import AdapterInput, MeasurementPath, sha256_file
from sheet2play_omr.phase2r_validation import run_with_typed_failure


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def replace_json(path: Path, payload: Any) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def acquire_lock(root: Path, recover_stale: bool = False) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    lock = root / "worker.lock"
    if lock.exists():
        saved = read_json(lock)
        try:
            live = psutil.Process(saved["pid"])
            if abs(live.create_time() - saved["creation_time"]) < 1:
                raise RuntimeError(f"Screening worker is still live: PID {live.pid}")
        except psutil.NoSuchProcess:
            pass
        if not recover_stale:
            raise RuntimeError(f"Stale lock requires checked recovery: {lock}")
        lock.rename(root / f"worker-lock-retired-{uuid.uuid4().hex}.json")
    process = psutil.Process()
    write_new(lock, {"pid": process.pid, "creation_time": process.create_time(),
                     "command": sys.argv, "working_directory": str(WORKSPACE),
                     "created_utc": utc_now()})
    return lock


def release_lock(lock: Path) -> None:
    saved = read_json(lock)
    if (saved["pid"] != os.getpid() or
            abs(saved["creation_time"] - psutil.Process().create_time()) >= 1):
        raise RuntimeError("Screening lock identity changed; refusing to remove it")
    lock.unlink()


def validate_admission(path: Path, manifest: dict[str, Any], candidate: str) -> None:
    admission = read_json(path)
    config = manifest["candidates"][candidate]["identity"]
    if (admission.get("status") != "passed" or admission.get("complete_page") is not True
            or admission.get("candidate") != candidate
            or admission.get("sample_sha256") != manifest["sample_sha256"]
            or admission.get("configuration_sha256") != manifest["candidates"][candidate]["identity_sha256"]
            or admission.get("adapter_config_sha256") != config["adapter_config_sha256"]):
        raise ValueError("Screening pipeline development entry has not passed")
    if candidate in {"homr_455", "fine_tuned_homr"}:
        compatibility = config["compatibility_report"]
        path_to_report = (WORKSPACE / compatibility["path"]).resolve()
        if (admission.get("compatibility_report_sha256") != compatibility["sha256"] or
                not path_to_report.is_relative_to(WORKSPACE.resolve()) or
                not path_to_report.is_file() or
                sha256_file(path_to_report) != compatibility["sha256"]):
            raise ValueError(f"{candidate} compatibility admission differs")
    report = (WORKSPACE / admission["development_report"]).resolve()
    if (not report.is_relative_to(WORKSPACE.resolve()) or not report.is_file()
            or sha256_file(report) != admission["development_report_sha256"]):
        raise ValueError("Development entry report is missing or changed")
    result = read_json(report)
    sidecar = report.with_suffix(".identity.json")
    if (not sidecar.is_file() or
            sha256_file(sidecar) != admission.get("development_identity_sha256")):
        raise ValueError("Development identity sidecar is missing or changed")
    if (result.get("status") != "succeeded"
            or result.get("measurement_path") != "complete_document"
            or result.get("adapter_config_sha256") != config["adapter_config_sha256"]):
        raise ValueError("Development entry result does not match the screening pipeline")
    for artifact in result["artifacts"]:
        source = (WORKSPACE / artifact["path"]).resolve()
        if (not source.is_relative_to(WORKSPACE.resolve()) or not source.is_file()
                or source.stat().st_size != artifact["bytes"]
                or sha256_file(source) != artifact["sha256"]):
            raise ValueError("Development entry artifact changed")


def command_monitor(command, *, cwd, timeout_seconds, environment=None):
    """Persist every child command's logs, including interrupted system jobs."""
    attempt = Path(os.environ["S2P_SCREENING_ATTEMPT"])
    sequence = len(list(attempt.glob("command-*.stdout.log"))) + 1
    out = attempt / f"command-{sequence}.stdout.log"
    err = attempt / f"command-{sequence}.stderr.log"
    started = time.monotonic()
    peak_ram, timed_out = 0, False
    with out.open("x", encoding="utf-8") as stdout, err.open("x", encoding="utf-8") as stderr:
        process = subprocess.Popen(command, cwd=cwd, env=environment, stdin=subprocess.DEVNULL,
                                   stdout=stdout, stderr=stderr,
                                   creationflags=subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS)
        root = psutil.Process(process.pid)
        root.cpu_affinity(root.cpu_affinity()[:threads_limit()])
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
        out.read_text(encoding="utf-8", errors="replace"),
        err.read_text(encoding="utf-8", errors="replace"), peak_ram or None, None,
        "device-wide readings in resources.jsonl; not per-process", timed_out)


def is_scored_model_outcome(result: dict[str, Any]) -> bool:
    if result.get("status") == "succeeded":
        return True
    if result.get("status") != "failed" or result.get("exit_status") == 127:
        return False
    error = result.get("error") or {}
    if error.get("code") in {"ADAPTER_INPUT_INVALID", "HOMR_RUNTIME_MISSING",
                              "ZEUS_RUNTIME_MISSING", "AUDIVERIS_RUNTIME_MISSING",
                              "OSError", "PermissionError", "FileNotFoundError"}:
        return False
    if error.get("stage") in {"input_validation", "adapter"}:
        return False
    message = str(error.get("message", "")).lower()
    if any(fragment in message for fragment in ("cudaexecutionprovider is unavailable",
                                                 "could not preload cuda", "runtime unavailable")):
        return False
    return bool(error.get("code"))


def worker(manifest_path: Path, candidate: str, index: int, attempt: Path) -> None:
    manifest = verify_manifest(manifest_path)
    require_current_policy(manifest)
    item = manifest["items"][index]
    root = psutil.Process()
    root.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    root.cpu_affinity(root.cpu_affinity()[:threads_limit()])
    adapter = screening_adapter(candidate, threads_limit(), sha256_file(Path(__file__)))
    if adapter.config.sha256 != manifest["candidates"][candidate]["identity"]["adapter_config_sha256"]:
        raise ValueError("Live adapter configuration differs from screening manifest")
    if candidate == "homr_455":
        from screening_homr_extension import candidate_environment
        os.environ.update(candidate_environment(manifest["candidates"][candidate]["identity"]))
    elif candidate == "fine_tuned_homr":
        from screening_finetune_extension import candidate_environment
        os.environ.update(candidate_environment(manifest["candidates"][candidate]["identity"]))
    image = AdapterInput(item["id"], item["composition_group"], WORKSPACE / item["image_path"],
                         item["image_sha256"], MeasurementPath.COMPLETE_DOCUMENT,
                         WORKSPACE / item["reference_path"], item["reference_sha256"])
    image.validate()
    if not adapter.probe()["available"]:
        raise RuntimeError("Candidate runtime is unavailable")
    phase2_adapters.run_monitored = command_monitor
    result = run_with_typed_failure(adapter, image, attempt / "raw")
    if not is_scored_model_outcome(result.to_json()):
        write_new(attempt / "unavailable.json", result.to_json())
        raise RuntimeError("Runtime/infrastructure outcome remains pending, not a model failure")
    write_new(attempt / "staged-result.json", result.to_json())


def promote_staged(attempt: Path, completed: Path, identity: dict[str, Any]) -> bool:
    staged = attempt / "staged-result.json"
    if not staged.is_file():
        return False
    if read_json(attempt / "attempt.json")["identity"] != identity:
        raise ValueError(f"Staged result identity changed: {attempt}")
    result = read_json(staged)
    validate_result(result, identity)
    outcome_path = attempt / "outcome.json"
    outcome = read_json(outcome_path) if outcome_path.is_file() else None
    if outcome is not None and (outcome.get("reason") is not None or outcome.get("worker_exit") != 0):
        return False
    if outcome is not None and outcome.get("reason") is None and outcome.get("worker_exit") == 0:
        result["provenance"]["adapter_timings"] = result["timings"]
        result["timings"] = [{"stage": "screening_complete_path",
                              "seconds": outcome["elapsed_seconds"]}]
        result["provenance"]["timing_source"] = "screening_complete_path"
        samples = attempt / "resources.jsonl"
        if samples.is_file() and result.get("resources"):
            readings = [json.loads(line) for line in samples.read_text(encoding="utf-8").splitlines()]
            vram = [gpu["used_mib"] * 1024 * 1024 for sample in readings
                    for gpu in sample["device_wide_gpu"] or []]
            if vram:
                result["resources"]["peak_vram_bytes"] = max(vram)
                result["resources"]["measurement_notes"] = [
                    *result["resources"].get("measurement_notes", []),
                    "device-wide nvidia-smi sample; not per-process VRAM"]
    else:
        result["provenance"]["timing_source"] = "adapter_only_unverified"
    commit_completed(completed, identity, result,
                     {"origin": "completed_attempt", "attempt_path": str(attempt.relative_to(WORKSPACE)),
                      "attempt_sha256": sha256_file(staged),
                      "timing_source": result["provenance"]["timing_source"]})
    return True


def run_attempt(manifest_path: Path, candidate: str, index: int, attempt: Path,
                deadline: float) -> dict[str, Any]:
    attempt.mkdir(parents=True)
    manifest = read_json(manifest_path)
    item = manifest["items"][index]
    identity = result_identity(manifest, candidate, item)
    write_new(attempt / "attempt.json", {"identity": identity, "status": "pending",
                                          "started_utc": utc_now(), "working_directory": str(WORKSPACE)})
    temporary = attempt / "temporary"
    temporary.mkdir()
    threads = threads_limit()
    environment = {**os.environ, "S2P_SCREENING_ATTEMPT": str(attempt),
                   "S2P_PREFLIGHT_THREADS": str(threads),
                   "TEMP": str(temporary), "TMP": str(temporary), "PYTHONUNBUFFERED": "1"}
    for key in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        environment[key] = str(threads)
    command = [sys.executable, str(Path(__file__).resolve()), "--manifest", str(manifest_path),
               "--candidate", candidate, "--worker-index", str(index), "--attempt", str(attempt)]
    started, since = time.monotonic(), None
    reason, samples = None, []
    with (attempt / "worker.stdout.log").open("x") as stdout, \
            (attempt / "worker.stderr.log").open("x") as stderr:
        process = subprocess.Popen(command, cwd=WORKSPACE, env=environment, stdin=subprocess.DEVNULL,
                                   stdout=stdout, stderr=stderr,
                                   creationflags=subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS)
        root = psutil.Process(process.pid)
        write_new(attempt / "process.json", {"pid": root.pid, "creation_time": root.create_time(),
                                              "executable": root.exe(), "command": command})
        try:
            with (attempt / "resources.jsonl").open("x", encoding="utf-8") as stream:
                while True:
                    sample = resource_sample()
                    samples.append(sample)
                    stream.write(json.dumps(sample) + "\n")
                    stream.flush()
                    now = time.monotonic()
                    since, expired = pressure_expired(now, since, bool(sample["admission_blockers"]))
                    if expired or now >= deadline - POLICY["shutdown_reserve_seconds"]:
                        reason = "resource_interruption" if expired else "session_limit"
                        stop_tree(root)
                        break
                    if process.poll() is not None:
                        break
                    time.sleep(max(0, started + len(samples) * POLICY["sample_seconds"] - time.monotonic()))
            process.wait(timeout=10)
        finally:
            if process.poll() is None:
                stop_tree(root)
    outcome = {"status": "pending", "reason": reason, "worker_exit": process.returncode,
               "elapsed_seconds": time.monotonic() - started,
               "peak_system_ram_percent": max(s["ram_percent"] for s in samples),
               "peak_device_vram_mib": max((g["used_mib"] for s in samples
                                             for g in s["device_wide_gpu"] or []), default=None)}
    write_new(attempt / "outcome.json", outcome)
    return outcome


def existing_attempts(root: Path, candidate: str, item_id: str, config_sha256: str) -> list[Path]:
    parent = root / "attempts" / candidate / config_sha256[:12] / digest(item_id)[:20]
    return sorted(path for path in parent.glob("attempt-*")) if parent.exists() else []


def session_budget(root: Path, session_id: str) -> tuple[Path, float]:
    if not session_id or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789-" for char in session_id):
        raise ValueError("Session ID must be lowercase letters, digits, or hyphens")
    sessions = root / "sessions"
    sessions.mkdir(exist_ok=True)
    path = sessions / f"{session_id}.json"
    now = datetime.now(timezone.utc)
    if path.exists():
        state = read_json(path)
        if state.get("active_since_utc"):
            # Count an interrupted invocation's full wall time conservatively.
            started = datetime.fromisoformat(state["active_since_utc"])
            state["used_seconds"] += max(0, (now - started).total_seconds())
    else:
        state = {"session_id": session_id, "used_seconds": 0.0, "active_since_utc": None}
    if state["used_seconds"] >= POLICY["session_seconds"] - POLICY["shutdown_reserve_seconds"]:
        raise RuntimeError("Four-hour session limit reached")
    state["active_since_utc"] = now.isoformat()
    if path.exists():
        replace_json(path, state)
    else:
        write_new(path, state)
    return path, time.monotonic() + POLICY["session_seconds"] - state["used_seconds"]


def close_session(path: Path, started: float) -> None:
    state = read_json(path)
    state["used_seconds"] += time.monotonic() - started
    state["active_since_utc"] = None
    replace_json(path, state)


def run(manifest_path: Path, candidate: str, admission: Path, session_id: str,
        start_index: int, max_items: int, retry_pending: bool,
        recover_stale_lock: bool) -> list[dict[str, Any]]:
    if candidate not in RUNNABLE or not 1 <= max_items <= POLICY["max_pages_per_chunk"]:
        raise ValueError("Unsupported candidate or chunk size")
    manifest = verify_manifest(manifest_path)
    require_current_policy(manifest)
    if not 1 <= start_index <= len(manifest["items"]):
        raise ValueError("Start index is outside selected items")
    validate_admission(admission, manifest, candidate)
    root = output_root(manifest_path)
    lock = acquire_lock(root, recover_stale_lock)
    session_path, session_start = None, time.monotonic()
    try:
        session_path, deadline = session_budget(root, session_id)
        progress = []
        for index in range(start_index - 1, min(len(manifest["items"]), start_index - 1 + max_items)):
            item = manifest["items"][index]
            identity = result_identity(manifest, candidate, item)
            config_sha256 = manifest["candidates"][candidate]["identity_sha256"]
            completed = completed_path(root, candidate, item["id"], config_sha256)
            if completed.exists():
                status = verify_completed(completed, identity)["status"]
                progress.append({"index": index + 1, "item_id": item["id"], "status": status,
                                 "origin": "verified_completed"})
                continue
            attempts = existing_attempts(root, candidate, item["id"], config_sha256)
            staged = [prior for prior in attempts if (prior / "staged-result.json").is_file()]
            if len(staged) > 1:
                raise ValueError(f"Ambiguous staged candidate results: {item['id']}")
            if staged:
                promote_staged(staged[0], completed, identity)
            if completed.exists():
                status = verify_completed(completed, identity)["status"]
                progress.append({"index": index + 1, "item_id": item["id"], "status": status,
                                 "origin": "verified_staged"})
                continue
            if attempts and not retry_pending:
                raise RuntimeError(f"Pending partial attempt requires --retry-pending: {item['id']}")
            admission_sample = resource_sample()
            if admission_sample["admission_blockers"] or time.monotonic() >= deadline - POLICY["shutdown_reserve_seconds"]:
                progress.append({"index": index + 1, "item_id": item["id"], "status": "pending",
                                 "origin": "admission_blocked", "blockers": admission_sample["admission_blockers"]})
                break
            attempt_parent = root / "attempts" / candidate / config_sha256[:12] / digest(item["id"])[:20]
            attempt_parent.mkdir(parents=True, exist_ok=True)
            attempt = attempt_parent / f"attempt-{uuid.uuid4().hex}"
            outcome = run_attempt(manifest_path, candidate, index, attempt, deadline)
            if outcome["reason"] is None and outcome["worker_exit"] == 0:
                if not promote_staged(attempt, completed, identity):
                    raise RuntimeError(f"Worker exited without a completed or failed result: {attempt}")
                status = verify_completed(completed, identity)["status"]
                progress.append({"index": index + 1, "item_id": item["id"], "status": status,
                                 "origin": "inferred"})
            else:
                progress.append({"index": index + 1, "item_id": item["id"], "status": "pending",
                                 "origin": outcome["reason"] or "worker_error"})
                break
        return progress
    finally:
        if session_path is not None:
            close_session(session_path, session_start)
        release_lock(lock)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--candidate", choices=RUNNABLE, required=True)
    parser.add_argument("--admission", type=Path)
    parser.add_argument("--session-id")
    parser.add_argument("--start-index", type=int, default=1)
    parser.add_argument("--max-items", type=int, default=5)
    parser.add_argument("--retry-pending", action="store_true")
    parser.add_argument("--recover-stale-lock", action="store_true")
    parser.add_argument("--worker-index", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--attempt", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker_index is not None:
        if args.attempt is None:
            raise ValueError("Worker attempt path is required")
        worker(args.manifest.resolve(), args.candidate, args.worker_index, args.attempt.resolve())
    else:
        if args.admission is None or args.session_id is None:
            raise ValueError("A verified development admission and session ID are required")
        for outcome in run(args.manifest.resolve(), args.candidate, args.admission.resolve(),
                           args.session_id, args.start_index, args.max_items,
                           args.retry_pending, args.recover_stale_lock):
            print(json.dumps(outcome, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
