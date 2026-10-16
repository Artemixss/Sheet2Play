"""Fetch frozen SMB evaluation images at the Phase-1 pinned revision."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from phase2 import verify_phase1_freeze
from sheet2play_omr.adapter_contract import sha256_file


HERE = Path(__file__).resolve().parent
ROOT = HERE / "data" / "smb"
MANIFEST_ROOT = HERE / "reports" / "phase1"


def _rows(collection: str) -> list[dict[str, Any]]:
    path = MANIFEST_ROOT / f"{collection}.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    if not rows or len({row["id"] for row in rows}) != len(rows):
        raise ValueError(f"Frozen {collection} manifest is empty or contains duplicate IDs")
    return rows


def _image_path(row: dict[str, Any]) -> Path:
    relative = Path(str(row["image_path"]))
    if relative.is_absolute() or ".." in relative.parts or relative.suffix.lower() != ".png":
        raise ValueError(f"Invalid frozen SMB image path: {relative}")
    path = (ROOT / relative).resolve()
    if ROOT.resolve() not in path.parents:
        raise ValueError(f"SMB image escaped the dataset root: {relative}")
    return path


def fetch(collection: str, max_items: int = 0) -> None:
    if max_items < 0:
        raise ValueError("max_items cannot be negative")
    verify_phase1_freeze()
    lock = json.loads((HERE / "smb.lock.json").read_text(encoding="utf-8"))
    revision = lock.get("revision")
    if not isinstance(revision, str) or len(revision) != 40:
        raise ValueError("SMB lock has no pinned 40-character revision")
    rows = _rows(collection)
    selected = rows[:max_items] if max_items else rows
    from huggingface_hub import hf_hub_download

    for index, row in enumerate(selected, start=1):
        image = _image_path(row)
        expected = str(row["image_sha256"])
        if image.is_file():
            actual = sha256_file(image)
            if actual != expected:
                raise ValueError(f"Existing SMB image hash mismatch: {image}")
            state = "verified"
        else:
            fetched = Path(hf_hub_download(
                "PRAIG/SMB", filename=Path(row["image_path"]).as_posix(),
                repo_type="dataset", revision=revision, local_dir=str(ROOT),
            ))
            if fetched.resolve() != image or sha256_file(image) != expected:
                raise ValueError(f"Downloaded SMB image did not match frozen identity: {image}")
            state = "fetched"
        print(json.dumps({"item": index, "total": len(selected), "id": row["id"],
                          "state": state}, sort_keys=True), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection", choices=("smb-pianoform", "smb-complete"),
                        default="smb-pianoform")
    parser.add_argument("--max-items", type=int, default=0)
    args = parser.parse_args()
    fetch(args.collection, args.max_items)


if __name__ == "__main__":
    main()
