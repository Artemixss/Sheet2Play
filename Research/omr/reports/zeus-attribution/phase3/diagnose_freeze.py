"""Compare the historical freeze without permitting Git subprocesses."""
from __future__ import annotations

import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parents[2]
sys.path.insert(0, str(RESEARCH))


def reject_git(event: str, args: tuple) -> None:
    if event != "subprocess.Popen":
        return
    executable, command = args[:2]
    values = [executable, *(command if isinstance(command, (tuple, list)) else [command])]
    if any(Path(str(value)).name.lower() in {"git", "git.exe"} for value in values):
        raise RuntimeError("Git is prohibited during this read-only freeze diagnosis")


def differences(saved: object, current: object, path: str = "") -> list[dict]:
    if saved == current:
        return []
    if isinstance(saved, dict) and isinstance(current, dict):
        result = []
        for key in sorted(saved.keys() | current.keys()):
            name = f"{path}.{key}" if path else key
            if key not in saved or key not in current:
                result.append({"path": name, "kind": "added" if key not in saved else "removed"})
            else:
                result.extend(differences(saved[key], current[key], name))
        return result
    if isinstance(saved, list) and isinstance(current, list) and len(saved) == len(current):
        return [entry for index, (old, new) in enumerate(zip(saved, current))
                for entry in differences(old, new, f"{path}[{index}]")]
    return [{"path": path, "saved": saved, "current": current}]


def main() -> None:
    sys.addaudithook(reject_git)
    from phase3_freeze import snapshot
    from screening_cpu_profile import cpu_environment
    import os
    os.environ.update(cpu_environment(8))
    frozen = RESEARCH / "reports/phase3/phase3-config-freeze-v1-89f385c8790b.json"
    saved = json.loads(frozen.read_text(encoding="utf-8"))
    result = {"differences": differences(saved, snapshot()), "git_invocations": 0,
              "limitation": "Git prohibited; this is a freeze comparison, not a revision attestation"}
    with (HERE / "freeze-differences.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
    print(json.dumps(result, allow_nan=False))


if __name__ == "__main__":
    main()
