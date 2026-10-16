"""Verify diagnostic runtime bytes and inherited detector pins before any replay."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

from zeus_provenance import WORKSPACE, file_record, verify


def verify_inherited(value: Any, root: Path = WORKSPACE) -> int:
    count = 0
    if isinstance(value, dict):
        if isinstance(value.get("root"), str):
            root = (WORKSPACE / value["root"]).resolve()
        if isinstance(value.get("path"), str) and isinstance(value.get("sha256"), str):
            path = root / value["path"]
            if file_record(path)["sha256"] != value["sha256"]:
                raise ValueError(f"Inherited detector file changed: {path}")
            count += 1
        for item in value.values():
            count += verify_inherited(item, root)
    elif isinstance(value, list):
        for item in value:
            count += verify_inherited(item, root)
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("identity", type=Path)
    args = parser.parse_args()
    try:
        result = verify(args.identity)
        payload = json.loads(args.identity.read_text(encoding="utf-8"))
        result["inherited_detector_files_verified"] = verify_inherited(
            payload["identity"]["inherited_detector_identity"])
        if result["inherited_detector_files_verified"] == 0:
            raise ValueError("Empty inherited detector identity")
        result["verification_source"] = file_record(Path(__file__))
        print(json.dumps(result))
        return 0
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
