"""Preserve installed code and private metadata before the app integration."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil


def snapshot(workspace: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    installed = workspace / "dist"
    library = Path(r"C:\Users\bur4x\AppData\Local\Sheet2Play")
    paths = [installed / "Sheet2Play.exe"]
    paths.extend(sorted((installed / "Bridge").glob("*.py")))
    paths.extend(sorted((workspace / "Visualization_engine").glob("*.cs")))
    paths.extend(sorted((workspace / "Bridge").glob("*.py")))
    paths.extend(sorted(library.glob("*.json")))
    paths.extend(sorted((library / "songs/midi").glob("*/*.cache.json")))
    records = []
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(path)
        relative = path.relative_to(workspace) if path.is_relative_to(workspace) else Path("private") / path.relative_to(library)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        records.append({"path": str(path), "backup": str(relative),
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size})
    (destination / "inventory.json").write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"snapshotted_files": len(records), "private_metadata_files": sum(r["backup"].startswith("private") for r in records)}))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    snapshot(Path(__file__).resolve().parents[2], args.output)
