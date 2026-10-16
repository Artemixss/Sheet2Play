"""Record a reviewed resumption without changing the frozen comparison."""
from __future__ import annotations

from datetime import datetime, timezone
import ctypes
import json
import os
import subprocess

from homr_465_audit import profiles, read, verify_artifacts
from homr_465_common import write_new
from homr_465_prepare import EVIDENCE, HERE, artifact
from screening_homr_compatibility import digest


class MemoryStatus(ctypes.Structure):
    _fields_ = [("length", ctypes.c_uint32), ("load", ctypes.c_uint32)] + [
        (name, ctypes.c_uint64) for name in ("physical_total", "physical_available",
            "pagefile_total", "pagefile_available", "virtual_total", "virtual_available", "extended_available")]


def memory_status() -> MemoryStatus:
    if os.name != "nt":
        raise OSError("Windows physical-memory admission is required")
    query = ctypes.WinDLL("kernel32", use_last_error=True).GlobalMemoryStatusEx
    query.argtypes = [ctypes.POINTER(MemoryStatus)]
    query.restype = ctypes.c_int32
    memory = MemoryStatus()
    memory.length = ctypes.sizeof(memory)
    if not query(ctypes.byref(memory)):
        raise ctypes.WinError(ctypes.get_last_error())
    return memory


def admission() -> None:
    configs = profiles()
    freeze = read(EVIDENCE / "comparison-freeze.json")
    identity = freeze.pop("identity_sha256")
    if digest(freeze) != identity:
        raise ValueError("Frozen comparison identity drift")
    declarations = [value for value in freeze.values()
                    if isinstance(value, dict) and "path" in value and "sha256" in value]
    verify_artifacts(declarations + freeze["additional_scoring_sources"])
    item_id = "be1ce479aa1490d66b01"
    job = EVIDENCE / "jobs" / ("comparison-control-" + item_id)
    failed = read(job / "result.json")
    if failed["status"] != "blocked" or failed["stop_reason"] != "RuntimeError: session_deadline":
        raise ValueError("Resumption is restricted to the reviewed deadline stop")
    samples = [json.loads(line) for line in (job / "resources.jsonl").read_text().splitlines()]
    gaps = [(datetime.fromisoformat(second["utc"]) - datetime.fromisoformat(first["utc"])).total_seconds()
            for first, second in zip(samples, samples[1:])]
    partial = EVIDENCE / "comparison/control" / item_id
    if (partial / "result.json").exists():
        raise ValueError("Interrupted capture unexpectedly has a final receipt")
    memory = memory_status()
    current = {"physical_percent": memory.load, "commit_limit_bytes": memory.pagefile_total,
               "committed_bytes": memory.pagefile_total - memory.pagefile_available,
               "scope": "GlobalMemoryStatusEx; supervisor independently samples system commit"}
    if (memory.load >= 85 or memory.pagefile_available < 4 * 1024**3):
        raise RuntimeError("Current system pressure prevents resumption")
    gpu = subprocess.run(["nvidia-smi", "--query-gpu=name,uuid,driver_version,memory.total",
                          "--format=csv,noheader"], check=True, capture_output=True,
                         text=True, timeout=15).stdout.strip()
    if gpu != read(EVIDENCE / "hardware.json")["gpu"]:
        raise ValueError("GPU/driver changed since freeze")
    counts = {name: len(list((EVIDENCE / "comparison" / name).glob("*/result.json")))
              for name in configs}
    result = {"utc": datetime.now(timezone.utc).isoformat(), "physical_total_bytes": memory.physical_total,
              "physical_available_bytes": memory.physical_available, "resource_sample": current,
              "gpu": gpu, "processor_count": os.cpu_count(), "comparison_identity": identity,
              "completed_or_explicit_failed_receipts": counts, "interrupted_item": item_id,
              "failed_supervisor": artifact(job / "result.json"),
              "largest_sampling_gap_seconds": max(gaps, default=0),
              "last_pre_gap_sample": samples[-2], "last_sample": samples[-1],
              "partial_capture_artifacts": [artifact(path) for path in sorted(partial.rglob("*")) if path.is_file()],
              "preservation_destination": str(EVIDENCE / "interrupted-20261008/control" / item_id),
              "safeguards": configs["control"]["safeguards"],
              "authorization": "User requested continuation of Phase 2 and reported a 16-to-32 GB RAM upgrade",
              "diagnosis": "Deadline follows a long telemetry gap; initiating cause unverified, no recorded RAM/commit stop",
              "performance_qualification": "Preserve pre-upgrade timings; report matched RAM cohorts separately"}
    write_new(EVIDENCE / "resumption-admission-20261008.json", result)
    print(json.dumps({key: result[key] for key in ("physical_total_bytes", "physical_available_bytes",
                                                "completed_or_explicit_failed_receipts", "largest_sampling_gap_seconds")}))


if __name__ == "__main__":
    admission()
