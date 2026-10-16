"""Bounded, read-only artifact audit after the second Windows crash."""
import ctypes
from ctypes import wintypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import threading
import time


class PerformanceInfo(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD)] + [
        (name, ctypes.c_size_t) for name in (
            "CommitTotal", "CommitLimit", "CommitPeak", "PhysicalTotal",
            "PhysicalAvailable", "SystemCache", "KernelTotal", "KernelPaged",
            "KernelNonpaged", "PageSize",
        )
    ] + [(name, wintypes.DWORD) for name in ("HandleCount", "ProcessCount", "ThreadCount")]


def memory_sample():
    info = PerformanceInfo()
    info.cb = ctypes.sizeof(info)
    library = ctypes.WinDLL("psapi", use_last_error=True)
    query = library.GetPerformanceInfo
    query.argtypes = [ctypes.POINTER(PerformanceInfo), wintypes.DWORD]
    query.restype = wintypes.BOOL
    if not query(ctypes.byref(info), info.cb):
        raise ctypes.WinError(ctypes.get_last_error())
    if not info.CommitLimit or not info.PhysicalTotal:
        raise RuntimeError("Windows returned invalid memory totals")
    return {
        "commit_percent": 100 * info.CommitTotal / info.CommitLimit,
        "physical_percent": 100 * (1 - info.PhysicalAvailable / info.PhysicalTotal),
        "committed_bytes": info.CommitTotal * info.PageSize,
        "commit_limit_bytes": info.CommitLimit * info.PageSize,
    }


def require_memory():
    sample = memory_sample()
    if max(sample["commit_percent"], sample["physical_percent"]) >= 90:
        raise RuntimeError(f"Audit refused at memory pressure: {sample}")
    return sample


def streaming_hash(path, expected):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    actual = digest.hexdigest()
    if actual != expected:
        raise ValueError(f"Hash mismatch: {path}")
    return actual


def main():
    destination = Path(__file__).resolve().parent.parent / "crash-audit-20261004-02"
    destination.mkdir(exist_ok=True)
    if (destination / "verification.json").exists():
        raise FileExistsError("Preserve the existing audit; choose a fresh destination")
    samples = [require_memory()]
    started = time.monotonic()
    done = threading.Event()

    def monitor():
        while not done.wait(0.5):
            try:
                samples.append(require_memory())
                if time.monotonic() - started >= 120:
                    raise TimeoutError("Audit exceeded its 120-second budget")
            except Exception as error:
                print(f"AUDIT ABORTED: {error}", flush=True)
                os._exit(2)

    guardian = threading.Thread(target=monitor, daemon=True)
    guardian.start()
    try:
        source = destination.parent / "verify-corrected.py"
        spec = importlib.util.spec_from_file_location("saved_verifier", source)
        if spec is None or spec.loader is None:
            raise ImportError("Could not load the existing independent verifier")
        verifier = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(verifier)
        verifier.HERE = destination
        verifier.hashed = streaming_hash
        verifier.main()
        samples.append(require_memory())
        evidence = {
            "scope": "Saved Phase 2 artifacts only; no Git, inference, scoring or tests",
            "elapsed_seconds": time.monotonic() - started,
            "threshold_percent": 90,
            "deadline_seconds": 120,
            "sample_interval_seconds": 0.5,
            "samples": len(samples),
            "initial": samples[0],
            "final": samples[-1],
            "peak_commit_percent": max(row["commit_percent"] for row in samples),
            "peak_physical_percent": max(row["physical_percent"] for row in samples),
        }
        with (destination / "resource-audit.json").open("x", encoding="utf-8") as stream:
            json.dump(evidence, stream, indent=2)
            stream.write("\n")
        print(json.dumps(evidence), flush=True)
    finally:
        done.set()
        guardian.join(timeout=1)


if __name__ == "__main__":
    main()
