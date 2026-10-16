"""Operational CPU-job supervisor; never imports or changes the frozen scorer."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

from execution_safety.execution_resources import WindowsResourceSampler, process_evidence
from execution_safety.safety_policy import SafetyLimits, admission_reason, blocking_reason
from execution_safety.windows_job import WindowsJob

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parent
LOG_BYTES = 8 * 1024**2


def _process_evidence() -> dict:
    try:
        return process_evidence()
    except Exception as error:
        return {"capture_error": f"{type(error).__name__}: {error}"}


def _output_reader(pipe, destination: Path, errors: list[str]) -> None:
    written = 0
    try:
        with destination.open("xb") as stream:
            for block in iter(lambda: pipe.read1(65536), b""):
                remaining = LOG_BYTES - written
                stream.write(block[:max(0, remaining)])
                stream.flush()
                written += len(block)
                if written > LOG_BYTES and not errors:
                    errors.append("worker_output_exceeded_8_MiB")
    except Exception as error:
        errors.append(f"worker_log_failure: {error}")


def run_guarded(command: list[str], cwd: Path, output: Path, limits: SafetyLimits,
                *, sampler=None, job_factory=WindowsJob, lock_path: Path | None = None) -> dict:
    if not command or any(not isinstance(value, str) or not value or "\0" in value for value in command):
        raise ValueError("A nonempty argument list is required")
    if not cwd.is_dir():
        raise ValueError("Working directory does not exist")
    output.mkdir(parents=True, exist_ok=False)
    lock = lock_path or WORKSPACE / ".research-worker.lock"
    child = None
    job = None
    reader = None
    lock_owned = False
    started = time.monotonic()
    result = {"status": "blocked", "command": command, "cwd": str(cwd),
              "limits": asdict(limits), "sampling_interval_seconds": 0.5,
              "worker_pid": None, "worker_exit_code": None, "stop_reason": None,
              "scope": "Own CPU worker tree only; external Git processes are observed, never killed"}
    try:
        sources = [Path(__file__), HERE / "guarded_worker.py"] + [
            HERE / "execution_safety" / name for name in (
                "execution_resources.py", "safety_policy.py", "windows_job.py")]
        result["operational_sources"] = {str(path.relative_to(WORKSPACE)):
            hashlib.sha256(path.read_bytes()).hexdigest() for path in sources}
        with lock.open("x", encoding="utf-8") as stream:
            lock_owned = True
            json.dump({"supervisor_pid": os.getpid(), "output": str(output)}, stream)
        sample_resources = sampler or WindowsResourceSampler()
        with (output / "resources.jsonl").open("x", encoding="utf-8") as resources:
            sample = sample_resources()
            result["initial"] = sample
            resources.write(json.dumps(sample) + "\n")
            resources.flush()
            reason = admission_reason(sample, limits)
            if reason:
                raise RuntimeError(reason)
            result["admission_process_evidence"] = _process_evidence()
            errors: list[str] = []
            job = job_factory(limits.worker_bytes, limits.active_processes)
            with job:
                child = subprocess.Popen(
                    [sys.executable, "-B", str(HERE / "guarded_worker.py")], cwd=cwd,
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                result["worker_pid"] = child.pid
                job.assign(child.pid)
                reader = threading.Thread(target=_output_reader,
                    args=(child.stdout, output / "worker.log", errors), daemon=True)
                reader.start()
                gate_sample = sample_resources()
                result["gate_admission"] = gate_sample
                resources.write(json.dumps(gate_sample) + "\n")
                resources.flush()
                reason = blocking_reason(gate_sample, time.monotonic() - started, limits)
                reason = reason or admission_reason(gate_sample, limits)
                if reason:
                    raise RuntimeError(reason)
                message = json.dumps({"action": "start", "command": command}).encode() + b"\n"
                if len(message) >= 1024 * 1024:
                    raise ValueError("Worker command exceeds start-message limit")
                child.stdin.write(message)
                child.stdin.close()
                result["status"] = "running"
                peak_commit, peak_ram = 0.0, 0.0
                peak_git_count = max(sample["git_count"], gate_sample["git_count"])
                peak_git_memory = max(sample["git_private_bytes"], gate_sample["git_private_bytes"])
                result["git_process_count_policy"] = "record_only; user-authorized 2026-10-04"
                result["git_private_memory_policy"] = "record_only; user-authorized 2026-10-05; system RAM/commit safeguards retained"
                last_log = 0.0
                while True:
                    sample = sample_resources()
                    elapsed = time.monotonic() - started
                    result["final"] = sample
                    reason = blocking_reason(sample, elapsed, limits)
                    peak_commit = max(peak_commit, sample["committed_bytes"] / sample["commit_limit_bytes"] * 100)
                    peak_ram = max(peak_ram, sample["physical_percent"])
                    result["peak_commit_percent"] = peak_commit
                    result["peak_physical_percent"] = peak_ram
                    new_git_peak = sample["git_count"] > peak_git_count or sample["git_private_bytes"] > peak_git_memory
                    peak_git_count = max(peak_git_count, sample["git_count"])
                    peak_git_memory = max(peak_git_memory, sample["git_private_bytes"])
                    result["peak_git_count"] = peak_git_count
                    result["peak_git_private_bytes"] = peak_git_memory
                    if reason or new_git_peak or elapsed - last_log >= 5 or child.poll() is not None:
                        resources.write(json.dumps(sample) + "\n")
                        resources.flush()
                        last_log = elapsed
                    if reason or errors:
                        raise RuntimeError(reason or errors[0])
                    if child.poll() is not None:
                        result["worker_exit_code"] = child.returncode
                        result["status"] = "complete" if child.returncode == 0 else "failed"
                        break
                    time.sleep(0.5)
    except BaseException as error:
        result["status"] = "blocked"
        result["stop_reason"] = f"{type(error).__name__}: {error}"
        if getattr(error, "__notes__", None):
            result["error_notes"] = error.__notes__
    finally:
        try:
            if child is not None:
                if child.poll() is None:
                    child.kill()
                child.wait(timeout=5)
                result["worker_exit_code"] = child.returncode
                if child.stdin is not None and not child.stdin.closed:
                    child.stdin.close()
            if reader is not None:
                reader.join(timeout=5)
                if reader.is_alive():
                    raise RuntimeError("Worker output reader did not close")
                if errors:
                    result["status"] = "blocked"
                    result["output_errors"] = errors
                    result["stop_reason"] = result["stop_reason"] or errors[0]
            if child is not None and child.stdout is not None:
                child.stdout.close()
        except Exception as error:
            result["status"] = "blocked"
            result["cleanup_error"] = f"{type(error).__name__}: {error}"
        if job is not None and not job.closed:
            result["status"] = "blocked"
            result["job_cleanup_error"] = "Windows Job closure is unconfirmed; inspect before retry"
        if result["status"] == "blocked":
            result["stop_process_evidence"] = _process_evidence()
        result["elapsed_seconds"] = time.monotonic() - started
        with (output / "result.json").open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        if lock_owned and not result.get("cleanup_error") and not result.get("job_cleanup_error"):
            lock.unlink()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-seconds", type=float, default=4 * 3600 - 30)
    parser.add_argument("--worker-limit-mib", type=int, default=4096)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    result = run_guarded(command, Path.cwd(), args.output.resolve(), SafetyLimits(
        worker_bytes=args.worker_limit_mib * 1024**2, max_seconds=args.max_seconds))
    print(json.dumps({key: result[key] for key in (
        "status", "stop_reason", "worker_exit_code", "elapsed_seconds")}))
    return 0 if result["status"] == "complete" else 2


if __name__ == "__main__":
    sys.exit(main())
