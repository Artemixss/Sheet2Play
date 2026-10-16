"""Wait for the primary reference gate, freeze Phase 3, and run the local sequence."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import psutil

from phase3_freeze import _reference_audit, create_freeze, verify_freeze
from phase3_sequence import run as run_sequence
from sheet2play_omr.adapter_contract import sha256_file


HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[1]
PREFLIGHT = HERE / ".runtime" / "phase3" / "bootstrap-preflight"


@dataclass(frozen=True, slots=True)
class Check:
    name: str
    arguments: tuple[str, ...]


def _wait_for_primary(pid: int, created_at: float) -> None:
    try:
        process = psutil.Process(pid)
    except psutil.NoSuchProcess:
        process = None
    if process is not None:
        if abs(process.create_time() - created_at) > 1:
            raise RuntimeError("Primary audit PID was reused by another process")
        print(json.dumps({"primary_audit": "waiting", "pid": pid}), flush=True)
        process.wait()
    audit = _reference_audit()
    print(json.dumps({"primary_audit": "verified", "valid": audit["valid_count"],
                      "sha256": audit["sha256"]}, sort_keys=True), flush=True)


def _checks(freeze: Path) -> list[Check]:
    token = str(freeze)
    checks = [
        Check(f"{candidate}_primary_first",
              ("Research/omr/phase3_infer.py", "--freeze", token, "--candidate", candidate,
               "--collection", "smb-pianoform", "--max-items", "1"))
        for candidate in ("homr_page", "audiveris_page", "zeus_page")
    ]
    checks.append(Check("zeus_system_first",
                        ("Research/omr/phase3_olimpic.py", "infer", "--freeze", token,
                         "--max-items", "1")))
    checks.extend(
        Check(f"{candidate}_private_first",
              ("Research/omr/phase3_private_diagnostic.py", "infer", "--freeze", token,
               "--candidate", candidate, "--max-pages", "1"))
        for candidate in ("homr_page", "audiveris_page", "zeus_page")
    )
    return checks


def _run_preflights(freeze: Path) -> None:
    PREFLIGHT.mkdir(parents=True, exist_ok=True)
    for check in _checks(freeze):
        stdout = PREFLIGHT / f"{check.name}.out.log"
        stderr = PREFLIGHT / f"{check.name}.err.log"
        if stdout.exists() or stderr.exists():
            raise FileExistsError(f"Frozen entry preflight {check.name} has existing logs; inspect before retry")
        command = (sys.executable, *check.arguments)
        print(json.dumps({"preflight": check.name, "status": "running",
                          "command": list(command)}, sort_keys=True), flush=True)
        with stdout.open("wb") as out, stderr.open("wb") as err:
            result = subprocess.run(command, cwd=WORKSPACE, stdout=out, stderr=err,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                                    check=False)
        if result.returncode != 0 or stdout.stat().st_size == 0:
            raise RuntimeError(f"Frozen entry preflight {check.name} failed; inspect its logs")
        print(json.dumps({"preflight": check.name, "status": "completed",
                          "stdout_sha256": sha256_file(stdout)}, sort_keys=True), flush=True)


def run(primary_pid: int, primary_created_at: float) -> None:
    if primary_pid <= 0 or primary_created_at <= 0:
        raise ValueError("Primary audit process identity is invalid")
    _wait_for_primary(primary_pid, primary_created_at)
    freeze = create_freeze()
    verify_freeze(freeze)
    print(json.dumps({"freeze": str(freeze), "sha256": sha256_file(freeze)},
                     sort_keys=True), flush=True)
    _run_preflights(freeze)
    run_sequence(freeze)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--primary-pid", type=int, required=True)
    parser.add_argument("--primary-created-at", type=float, required=True)
    args = parser.parse_args()
    run(args.primary_pid, args.primary_created_at)


if __name__ == "__main__":
    main()
