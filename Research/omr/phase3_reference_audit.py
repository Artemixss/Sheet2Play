"""Validate and checkpoint complete-page SMB truth before Phase-3 inference."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from phase2 import verify_phase1_freeze
from sheet2play_omr.adapter_contract import sha256_file
from sheet2play_omr.phase3_references import (
    frozen_smb_rows, metadata_by_id, reference_identity, reference_payload,
)


WORKSPACE = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def _write_once(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite Phase-3 reference evidence: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
                         encoding="utf-8")
    temporary.replace(path)


def _reference_path(item_id: str, identity: dict[str, str]) -> Path:
    payload = json.dumps({"item_id": item_id, "identity": identity}, sort_keys=True).encode("utf-8")
    return HERE / ".runtime" / "phase3" / "references" / f"{hashlib.sha256(payload).hexdigest()[:24]}.json"


def audit(collection: str, max_items: int = 0) -> Path:
    if max_items < 0:
        raise ValueError("max_items cannot be negative")
    verify_phase1_freeze()
    rows = frozen_smb_rows(WORKSPACE, collection)
    if collection == "smb-pianoform" and len(rows) != 402:
        raise ValueError("Frozen SMB pianoform page count changed")
    selected = rows[:max_items] if max_items else rows
    metadata = metadata_by_id(HERE / "data" / "smb" / "metadata.jsonl")
    identity = reference_identity(WORKSPACE, collection)
    outcomes: list[dict[str, Any]] = []
    for index, row in enumerate(selected, start=1):
        image = HERE / "data" / "smb" / row["image_path"]
        output = _reference_path(row["id"], identity)
        musicxml = output.with_suffix(".musicxml")
        try:
            if not image.is_file() or sha256_file(image) != row["image_sha256"]:
                raise ValueError("Frozen SMB page image missing or hash mismatch")
            if row["id"] not in metadata:
                raise ValueError("SMB metadata item missing")
            if output.is_file():
                payload = json.loads(output.read_text(encoding="utf-8"))
                if (payload.get("identity") != identity or payload.get("item_id") != row["id"]
                        or payload.get("image_sha256") != row["image_sha256"]
                        or not musicxml.is_file()
                        or payload.get("reference_musicxml_sha256") != sha256_file(musicxml)):
                    raise ValueError("Cached reference identity differs from frozen input")
                state = "verified_cache"
            else:
                payload = reference_payload(row, metadata[row["id"]], identity, musicxml, WORKSPACE)
                _write_once(output, payload)
                state = "generated"
            outcome: dict[str, Any] = {
                "id": row["id"], "status": "valid", "state": state,
                "reference_path": output.relative_to(WORKSPACE).as_posix(),
                "reference_sha256": sha256_file(output),
                "reference_musicxml_sha256": sha256_file(musicxml),
                "note_count": len(payload["notes"]),
                "normalization_warning_count": len(payload["normalization_warnings"]),
            }
        except Exception as error:
            outcome = {"id": row["id"], "status": "invalid", "error_type": type(error).__name__,
                       "error": str(error)[:500]}
        outcomes.append(outcome)
        print(json.dumps({"item": index, "total": len(selected), **outcome}, sort_keys=True), flush=True)
    report = {
        "schema_version": 1,
        "collection": collection,
        "scope": "complete_page_reference_preflight",
        "full_collection": len(selected) == len(rows),
        "identity": identity,
        "eligible_count": len(rows),
        "audited_count": len(selected),
        "valid_count": sum(row["status"] == "valid" for row in outcomes),
        "invalid_count": sum(row["status"] == "invalid" for row in outcomes),
        "items": outcomes,
    }
    suffix = "full" if len(selected) == len(rows) else f"first-{len(selected)}"
    destination = HERE / "reports" / "phase3" / f"reference-audit-{collection}-{suffix}-{identity['builder_sha256'][:12]}.json"
    _write_once(destination, report)
    print(json.dumps({"report": str(destination), "valid": report["valid_count"],
                      "invalid": report["invalid_count"]}, sort_keys=True), flush=True)
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection", choices=("smb-pianoform", "smb-complete"), default="smb-pianoform")
    parser.add_argument("--max-items", type=int, default=0)
    args = parser.parse_args()
    destination = audit(args.collection, args.max_items)
    report = json.loads(destination.read_text(encoding="utf-8"))
    return 0 if report["invalid_count"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
