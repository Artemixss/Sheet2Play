"""Freeze and execute the bounded app-runtime qualification without implicit retries."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[1]
ROOT = HERE / "reports/homr-465-app-integration/phase1"
FROZEN = HERE / "reports/homr-timing-465/phase2"
APP_PYTHON = WORKSPACE / "Bridge/.venv-homr-gpu/Scripts/python.exe"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def save_new(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def prepare() -> None:
    from screening_homr_compatibility import digest
    rows = json.loads((FROZEN / "development-inputs.json").read_text())
    selected = [row for row in rows if row["collection"] == "generated" or row["item_id"] in {"openscore-6211535", "openscore-6211549"}]
    if len(selected) != 14:
        raise ValueError("Expected twelve generated controls and two diagnostic pages")
    for row in selected:
        for artifact in (row["image"], row["reference"]):
            if sha256(Path(artifact["path"])) != artifact["sha256"]:
                raise ValueError("Selected input/reference drift")
    destination = ROOT / "qualification"
    destination.mkdir(exist_ok=False)
    save_new(destination / "inputs.json", selected)
    control = json.loads((FROZEN / "control-configuration.json").read_text())
    control.pop("identity_sha256")
    control["python"] = {"path": str(APP_PYTHON), "sha256": sha256(APP_PYTHON)}
    control["candidate"] = "app-426-no-title-control"
    control["identity_sha256"] = digest(control)
    save_new(destination / "control-configuration.json", control)
    save_new(destination / "selection.json", {"native_captures": 28, "earlier_native_captures": 1,
        "total_ceiling": 64, "selection": "all twelve generated; first two explicit OpenScore IDs diagnostic-only",
        "profile_sha256": sha256(WORKSPACE / "Bridge/homr465-profile.json"),
        "inputs_sha256": sha256(destination / "inputs.json"), "capture_sha256": sha256(HERE / "integration_capture.py")})
    print("Frozen fourteen matched app-runtime qualification inputs")


def run() -> None:
    from guarded_execution import run_guarded
    from sheet2play_omr.safety_policy import SafetyLimits
    root = ROOT / "qualification"
    selection = json.loads((root / "selection.json").read_text())
    if (sha256(root / "inputs.json") != selection["inputs_sha256"] or
        sha256(HERE / "integration_capture.py") != selection["capture_sha256"] or
        sha256(WORKSPACE / "Bridge/homr465-profile.json") != selection["profile_sha256"]):
        raise ValueError("Qualification identity drift")
    os.environ["PYTHONPATH"] = os.pathsep.join((str(FROZEN / "gate"), str(HERE), str(HERE / "src")))
    rows = json.loads((root / "inputs.json").read_text())
    started = time.monotonic()
    for index, row in enumerate(rows):
        engines = ("homr465", "homr") if index % 2 == 0 else ("homr", "homr465")
        for engine in engines:
            if time.monotonic() - started > 13740:
                raise RuntimeError("Session boundary reached before another worker")
            output = root / engine / row["item_id"]
            job = ROOT / "jobs" / f"qualify-{engine}-{row['item_id']}"
            if job.exists():
                raise FileExistsError("Existing attempt requires explicit inspection, never implicit retry")
            command = [str(APP_PYTHON), "-B", str(HERE / "integration_capture.py"), engine,
                       str(root / "inputs.json"), row["item_id"], str(output)]
            result = run_guarded(command, WORKSPACE, job, SafetyLimits(max_seconds=600))
            receipt = json.loads((output / "result.json").read_text()) if (output / "result.json").exists() else {}
            error = receipt.get("error", "")
            print(json.dumps({"engine": engine, "item": row["item_id"], "status": result["status"],
                              "native_status": receipt.get("status"), "seconds": result["elapsed_seconds"]}), flush=True)
            if (result["status"] == "blocked" or not receipt or receipt.get("status") == "resource_stopped" or
                any(term in error for term in ("ProfileError", "CUDA", "MemoryError", "quota"))):
                raise RuntimeError("Resource/identity/infrastructure interruption requires review")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "run"))
    args = parser.parse_args()
    (prepare if args.mode == "prepare" else run)()
