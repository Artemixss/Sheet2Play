"""Preserve the complete installed release and current private metadata."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

WORKSPACE = Path(__file__).resolve().parents[2]
LIBRARY = Path(r"C:\Users\bur4x\AppData\Local\Sheet2Play")
DESTINATION = WORKSPACE / "Research/omr/reports/homr-465-app-integration/phase2/installed-backup"


def backup() -> None:
    DESTINATION.mkdir(parents=True, exist_ok=False)
    shutil.copytree(WORKSPACE / "dist", DESTINATION / "dist")
    paths = sorted(LIBRARY.glob("*.json")) + sorted((LIBRARY / "songs/midi").glob("*/*.cache.json"))
    records = []
    for source in paths:
        relative = source.relative_to(LIBRARY)
        target = DESTINATION / "private" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        identity = hashlib.sha256(source.read_bytes()).hexdigest()
        if hashlib.sha256(target.read_bytes()).hexdigest() != identity:
            raise ValueError("Private metadata backup differs from source")
        records.append({"relative_path": relative.as_posix(), "sha256": identity})
    (DESTINATION / "metadata.json").write_text(json.dumps(records, indent=2) + "\n")
    print(json.dumps({"private_metadata_files": len(records), "release_files": sum(1 for p in (DESTINATION / "dist").rglob("*") if p.is_file())}))


if __name__ == "__main__":
    backup()
