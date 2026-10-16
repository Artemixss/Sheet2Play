"""Identify the authorized title-only research deviation from the shipped baseline."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def identity(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def title_disabled_profile(runtime: str) -> dict:
    if len(runtime) != 64 or any(c not in "0123456789abcdef" for c in runtime):
        raise ValueError("Expected a SHA-256 baseline identity")
    contract = {"schema": 1, "name": "shipped-426-no-title-phase1",
                "baseline_runtime_identity": runtime,
                "processing_config_delta": {"title_detection": False},
                "musical_settings": "Unchanged native CUDA pipeline, weights, images, tuplets cleanup and XML arguments",
                "safeguards": {"system_stop_percent": 85, "reserve_bytes": 4294967296,
                               "worker_bytes": 4294967296, "active_processes": 16,
                               "gpu_stop_percent": 90, "one_heavy_worker": True},
                "network_limit_bytes": 2000000000, "phase": 1}
    return {**contract, "identity_sha256": identity(contract)}


def validate_profile(path: Path, runtime: str) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    expected = title_disabled_profile(runtime)
    if value != expected:
        raise ValueError("Research profile drift: only the authorized title-disable setting is allowed")
    return value


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    runtime = json.loads((args.evidence / "runtime-inventory.json").read_text())["identity_sha256"]
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(title_disabled_profile(runtime), stream, indent=2)
        stream.write("\n")
