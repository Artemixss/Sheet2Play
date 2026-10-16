"""Inventory development inputs and sample admission resources; no inference entry point."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any

import psutil

from phase2 import verify_phase1_freeze
from phase3_development_entry import _adapter, _identity
from screening_common import POLICY
from sheet2play_omr.adapter_contract import AdapterInput, MeasurementPath, sha256_file

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[1]


def admission_blockers(ram_percent: float, gpu_percent: float | None) -> list[str]:
    if not math.isfinite(ram_percent) or not 0 <= ram_percent <= 100:
        raise ValueError("Invalid RAM measurement")
    ram_limit = POLICY["ram_admission_percent"]
    blockers = [f"system_ram_at_or_above_{ram_limit}_percent"] if ram_percent >= ram_limit else []
    if gpu_percent is None:
        blockers.append("device_vram_measurement_unavailable")
    elif not math.isfinite(gpu_percent) or not 0 <= gpu_percent <= 100:
        raise ValueError("Invalid VRAM measurement")
    elif gpu_percent >= POLICY["device_vram_admission_percent"]:
        blockers.append(f"device_vram_at_or_above_{POLICY['device_vram_admission_percent']}_percent")
    return blockers


def resource_sample() -> dict[str, Any]:
    memory = psutil.virtual_memory()
    gpu, error = None, None
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,driver_version,memory.used,memory.total,utilization.gpu,temperature.gpu",
             "--format=csv,noheader,nounits"], capture_output=True, text=True, check=True,
            timeout=4, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        devices = []
        for line in result.stdout.splitlines():
            index, name, driver, used, total, utilization, temperature = [v.strip() for v in line.split(",")]
            if int(total) <= 0:
                raise ValueError("Invalid device memory total")
            devices.append({"index": int(index), "name": name, "driver": driver,
                            "used_mib": int(used), "total_mib": int(total),
                            "percent": int(used) / int(total) * 100,
                            "utilization_percent": int(utilization), "temperature_c": int(temperature)})
        gpu = devices or None
    except (OSError, subprocess.SubprocessError, ValueError) as failure:
        error = str(failure)
    gpu_percent = max(device["percent"] for device in gpu) if gpu else None
    return {"utc": datetime.now(timezone.utc).isoformat(), "ram_percent": memory.percent,
            "ram_total_bytes": memory.total, "ram_available_bytes": memory.available,
            "cpu_percent": psutil.cpu_percent(), "device_wide_gpu": gpu, "gpu_error": error,
            "disk_free_bytes": shutil.disk_usage(WORKSPACE).free,
            "admission_blockers": admission_blockers(memory.percent, gpu_percent)}


def development_inventory() -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in
            (HERE / "reports/phase1/development-open.jsonl").read_text(encoding="utf-8").splitlines()]
    planned = []
    # Manifest order and first page only: selection does not inspect candidate predictions.
    for row in rows[:3]:
        if row["composition_overlap_with_evaluation"]:
            raise ValueError("Development composition overlaps evaluation")
        page = row["page_images"][0]
        item = AdapterInput(f"{row['id']}-page-1", row["composition_group"],
                            WORKSPACE / page["path"], page["sha256"], MeasurementPath.COMPLETE_DOCUMENT,
                            WORKSPACE / row["musicxml_path"], row["musicxml_sha256"])
        item.validate()
        planned.append({"item_id": item.item_id, "image": page,
                        "reference_path": row["musicxml_path"], "reference_sha256": row["musicxml_sha256"],
                        "reference_scope": "whole composition, not a page-level scoring reference",
                        "status": "pending_not_started"})
    if len(planned) != 3:
        raise ValueError("Three development pages are required")
    return planned


def preflight(output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"Preserve previous evidence: {output}")
    freeze = verify_phase1_freeze()
    planned = development_inventory()
    runtimes = {}
    for name in ("homr_page", "audiveris_page", "zeus_page"):
        adapter, item = _adapter(name)
        digest, identity = _identity(name, adapter, item)
        runtimes[name] = {"probe": adapter.probe(), "identity_sha256": digest, "identity": identity}
    output.parent.mkdir(parents=True, exist_ok=True)
    logical_cpus = os.cpu_count()
    if not logical_cpus:
        raise RuntimeError("Logical CPU count unavailable")
    samples = []
    psutil.cpu_percent()
    started = time.monotonic()
    for index in range(7):
        time.sleep(max(0, started + index * 5 - time.monotonic()))
        samples.append(resource_sample())
    blockers = sorted({reason for sample in samples for reason in sample["admission_blockers"]})
    result = {"schema_version": 1, "source_sha256": sha256_file(Path(__file__)),
              "working_directory": str(WORKSPACE), "phase1": freeze, "runtimes": runtimes,
              "development_pages": planned, "samples": samples, "admission_blockers": blockers,
              "logical_processors": logical_cpus, "intended_cpu_thread_limit": max(1, logical_cpus // 2),
              "intended_priority": "BELOW_NORMAL_PRIORITY_CLASS at worker creation",
              "intended_limits": {"sample_seconds": 5, "pressure_grace_seconds": 30,
                                  "pages_per_chunk_max": 5, "session_seconds_max": 14400},
              "development_runs_completed": 0, "inference_started": False,
              "status": "blocked_before_admission" if blockers else "admission_observation_passed_only",
              "scope": "This command samples resources; it never launches a candidate or implements worker supervision."}
    with output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = preflight(args.output.resolve())
    print(json.dumps({"status": result["status"], "blockers": result["admission_blockers"],
                      "development_pages": [p["item_id"] for p in result["development_pages"]],
                      "ram_range": [min(s["ram_percent"] for s in result["samples"]),
                                    max(s["ram_percent"] for s in result["samples"])]}))


if __name__ == "__main__":
    main()
