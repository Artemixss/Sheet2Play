"""Exclusive evidence writes compatible with the restricted Windows workspace."""
from __future__ import annotations

import json
import os
from pathlib import Path


def write_new(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def write_or_verify(path: Path, value: object) -> None:
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != value:
            raise ValueError("Existing derived evidence differs: " + str(path))
        return
    write_new(path, value)
