"""Run the frozen Phase-3 tracks sequentially with resumable stage records."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from phase3_freeze import verify_freeze
from sheet2play_omr.adapter_contract import sha256_file


HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[1]


@dataclass(frozen=True, slots=True)
class Step:
    name: str
    arguments: tuple[str, ...]
    expect_summary: bool = False


def _steps(freeze: Path) -> list[Step]:
    token = str(freeze)
    steps: list[Step] = []
    for candidate in ("homr_page", "audiveris_page", "zeus_page"):
        steps.extend((
            Step(f"primary_{candidate}_infer", ("Research/omr/phase3_infer.py", "--freeze", token,
                                               "--candidate", candidate, "--collection", "smb-pianoform")),
            Step(f"primary_{candidate}_score", ("Research/omr/phase3_score.py", "--freeze", token,
                                               "--candidate", candidate, "--collection", "smb-pianoform"), True),
        ))
    steps.extend((
        Step("olimpic_zeus_infer", ("Research/omr/phase3_olimpic.py", "infer", "--freeze", token)),
        Step("olimpic_zeus_score", ("Research/omr/phase3_olimpic.py", "score", "--freeze", token), True),
    ))
    for candidate in ("homr_page", "audiveris_page", "zeus_page"):
        steps.extend((
            Step(f"secondary_{candidate}_infer", ("Research/omr/phase3_infer.py", "--freeze", token,
                                                 "--candidate", candidate, "--collection", "smb-complete")),
            Step(f"secondary_{candidate}_score", ("Research/omr/phase3_score.py", "--freeze", token,
                                                 "--candidate", candidate, "--collection", "smb-complete"), True),
        ))
    for candidate in ("homr_page", "audiveris_page", "zeus_page"):
        steps.extend((
            Step(f"private_{candidate}_infer", ("Research/omr/phase3_private_diagnostic.py", "infer",
                                               "--freeze", token, "--candidate", candidate)),
            Step(f"private_{candidate}_summarize", ("Research/omr/phase3_private_diagnostic.py", "summarize",
                                                   "--freeze", token, "--candidate", candidate), True),
        ))
    return steps


def _write_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(state, indent=2, sort_keys=True, allow_nan=False) + "\n",
                         encoding="utf-8")
    temporary.replace(path)


def _load_state(path: Path, freeze_sha256: str, steps: list[Step]) -> dict[str, Any]:
    names = [step.name for step in steps]
    if len(names) != len(set(names)):
        raise RuntimeError("Phase-3 sequence contains duplicate stage names")
    if path.is_file():
        state = json.loads(path.read_text(encoding="utf-8"))
        if state.get("freeze_sha256") != freeze_sha256 or state.get("stage_order") != names:
            raise RuntimeError("Existing Phase-3 sequence state differs from the current freeze")
        return state
    state = {"schema_version": 1, "freeze_sha256": freeze_sha256, "stage_order": names,
             "stages": {name: {"status": "pending"} for name in names}}
    _write_state(path, state)
    return state


def _last_json(path: Path) -> dict[str, Any]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise RuntimeError("Phase-3 stage produced no progress output")
    try:
        value = json.loads(lines[-1])
    except json.JSONDecodeError as error:
        raise RuntimeError("Phase-3 stage did not end with a JSON result") from error
    if not isinstance(value, dict):
        raise RuntimeError("Phase-3 stage result is not an object")
    return value


def _verify_completed(entry: dict[str, Any]) -> None:
    if "summary" not in entry:
        return
    path = Path(entry["summary"])
    if not path.is_file() or sha256_file(path) != entry["summary_sha256"]:
        raise RuntimeError("Completed Phase-3 stage summary changed")


def run(freeze: Path) -> None:
    freeze = freeze.resolve()
    verify_freeze(freeze)
    freeze_sha256 = sha256_file(freeze)
    steps = _steps(freeze)
    root = HERE / ".runtime" / "phase3" / "sequence" / freeze_sha256[:12]
    state_path = root / "state.json"
    state = _load_state(state_path, freeze_sha256, steps)
    for index, step in enumerate(steps, start=1):
        entry = state["stages"][step.name]
        if entry["status"] == "complete":
            _verify_completed(entry)
            print(json.dumps({"stage": index, "total": len(steps), "name": step.name,
                              "status": "verified_cache"}, sort_keys=True), flush=True)
            continue
        if entry["status"] != "pending":
            raise RuntimeError(f"Stage {step.name} needs process/output inspection before resume: {entry}")
        out = root / f"{step.name}.out.log"
        err = root / f"{step.name}.err.log"
        if out.exists() or err.exists():
            raise FileExistsError(f"Stage {step.name} has logs without a completion record")
        command = (sys.executable, *step.arguments)
        with out.open("wb") as stdout, err.open("wb") as stderr:
            process = subprocess.Popen(command, cwd=WORKSPACE, stdout=stdout, stderr=stderr,
                                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            entry.update({"status": "running", "pid": process.pid,
                          "command": list(command), "working_directory": str(WORKSPACE),
                          "stdout": str(out), "stderr": str(err)})
            _write_state(state_path, state)
            print(json.dumps({"stage": index, "total": len(steps), "name": step.name,
                              "status": "running", "pid": process.pid}, sort_keys=True), flush=True)
            return_code = process.wait()
        entry["exit_code"] = return_code
        if return_code != 0:
            entry["status"] = "failed"
            _write_state(state_path, state)
            raise RuntimeError(f"Phase-3 stage {step.name} failed with exit code {return_code}; inspect its logs")
        final = _last_json(out)
        if step.expect_summary:
            summary = Path(final.get("summary", ""))
            if not summary.is_file():
                raise RuntimeError(f"Phase-3 stage {step.name} did not produce a summary")
            entry["summary"] = str(summary)
            entry["summary_sha256"] = sha256_file(summary)
        entry["status"] = "complete"
        _write_state(state_path, state)
        print(json.dumps({"stage": index, "total": len(steps), "name": step.name,
                          "status": "complete"}, sort_keys=True), flush=True)
    print(json.dumps({"sequence": str(state_path), "completed_stages": len(steps)},
                     sort_keys=True), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", required=True, type=Path)
    args = parser.parse_args()
    run(args.freeze)


if __name__ == "__main__":
    main()
