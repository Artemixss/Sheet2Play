"""Run resumable frozen Phase-3 complete-page inference on the primary SMB set."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from phase3_development_entry import _adapter
from phase3_freeze import verify_freeze, verify_secondary_audit
from sheet2play_omr.adapter_contract import (
    AdapterInput, MeasurementPath, sha256_file, write_result,
)
from sheet2play_omr.phase2r_validation import run_with_typed_failure
from sheet2play_omr.phase3_references import frozen_smb_rows


WORKSPACE = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PAGE_CANDIDATES = ("homr_page", "audiveris_page", "zeus_page")
COLLECTIONS = ("smb-pianoform", "smb-complete")


def _write_once(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite frozen inference identity: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _paths(name: str, item_id: str, config_hash: str,
           collection: str, audit_sha256: str) -> tuple[Path, Path]:
    if collection not in COLLECTIONS or len(audit_sha256) != 64:
        raise ValueError(f"Unsupported frozen SMB collection: {collection}")
    stem = (f"{hashlib.sha256(item_id.encode('utf-8')).hexdigest()[:20]}-"
            f"{config_hash[:12]}-{audit_sha256[:12]}")
    report = HERE / "reports" / "phase3" / "evaluation" / collection / name / f"{stem}.json"
    output = HERE / ".runtime" / "phase3" / "evaluation" / collection / name / stem
    return report, output


def _verify_existing(path: Path, identity: dict[str, Any]) -> str:
    sidecar = path.with_suffix(".identity.json")
    if not sidecar.is_file() or json.loads(sidecar.read_text(encoding="utf-8")) != identity:
        raise ValueError(f"Existing inference identity differs from current freeze: {path}")
    result = json.loads(path.read_text(encoding="utf-8"))
    if (result.get("adapter_config_sha256") != identity["adapter_config_sha256"]
            or result.get("item_id") != identity["item_id"]
            or result.get("provenance", {}).get("input_sha256") != identity["image_sha256"]
            or result.get("status") not in {"succeeded", "failed"}):
        raise ValueError(f"Existing inference result is incomplete or changed: {path}")
    for artifact in result.get("artifacts", []):
        source = Path(artifact["path"])
        resolved = source if source.is_absolute() else WORKSPACE / source
        if not resolved.is_file() or sha256_file(resolved) != artifact["sha256"]:
            raise ValueError(f"Existing inference artifact changed: {resolved}")
    return result["status"]


def _reusable_primary_result(name: str, row: dict[str, Any], config_hash: str,
                             freeze_hash: str, primary_rows: dict[str, dict[str, Any]],
                             primary_audit: dict[str, Any],
                             primary_reference_hashes: dict[str, str]) -> dict[str, Any] | None:
    primary = primary_rows.get(row["id"])
    if primary is None:
        return None
    if (primary["image_sha256"] != row["image_sha256"]
            or primary["composition_group"] != row["composition_group"]):
        raise RuntimeError(f"Shared SMB item identity differs between collections: {row['id']}")
    path, _ = _paths(name, row["id"], config_hash, "smb-pianoform", primary_audit["sha256"])
    if not path.is_file():
        return None
    identity = {"schema_version": 1, "freeze_sha256": freeze_hash,
                "collection": "smb-pianoform",
                "reference_audit_sha256": primary_audit["sha256"],
                "candidate": name, "item_id": row["id"],
                "image_sha256": row["image_sha256"],
                "reference_sha256": primary_reference_hashes[row["id"]],
                "adapter_config_sha256": config_hash}
    _verify_existing(path, identity)
    return json.loads(path.read_text(encoding="utf-8"))


def run(name: str, freeze_path: Path, collection: str, start_index: int, max_items: int) -> None:
    if (name not in PAGE_CANDIDATES or collection not in COLLECTIONS
            or start_index < 1 or max_items < 0):
        raise ValueError("Unsupported candidate or item range")
    freeze = verify_freeze(freeze_path.resolve())
    adapter, _ = _adapter(name)
    config_hash = adapter.config.sha256  # type: ignore[attr-defined]
    if config_hash != freeze["ready"][name]["adapter_config_sha256"]:
        raise RuntimeError("Adapter configuration changed after Phase-3 freeze")
    audit_identity = (freeze["reference_audit"] if collection == "smb-pianoform"
                      else verify_secondary_audit())
    audit_path = WORKSPACE / audit_identity["path"]
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    reference_hashes = {item["id"]: item["reference_sha256"] for item in audit["items"]}
    rows = frozen_smb_rows(WORKSPACE, collection)
    if set(reference_hashes) != {row["id"] for row in rows}:
        raise RuntimeError("Frozen reference coverage differs from the eligible page set")
    selected = rows[start_index - 1:]
    if max_items:
        selected = selected[:max_items]
    if not selected:
        raise ValueError("Selected evaluation item range is empty")
    freeze_hash = sha256_file(freeze_path)
    primary_rows = ({row["id"]: row for row in frozen_smb_rows(WORKSPACE, "smb-pianoform")}
                    if collection == "smb-complete" else {})
    primary_reference_hashes = ({item["id"]: item["reference_sha256"] for item in
                                 json.loads((WORKSPACE / freeze["reference_audit"]["path"])
                                            .read_text(encoding="utf-8"))["items"]}
                                if collection == "smb-complete" else {})
    counts = {"succeeded": 0, "failed": 0, "reused": 0, "reused_primary": 0}
    for offset, row in enumerate(selected, start=start_index):
        image = HERE / "data" / "smb" / row["image_path"]
        item = AdapterInput(row["id"], row["composition_group"], image,
                            row["image_sha256"], MeasurementPath.COMPLETE_DOCUMENT)
        item.validate()
        report, output = _paths(name, item.item_id, config_hash, collection,
                                audit_identity["sha256"])
        identity = {"schema_version": 1, "freeze_sha256": freeze_hash,
                    "collection": collection, "reference_audit_sha256": audit_identity["sha256"],
                    "candidate": name, "item_id": item.item_id,
                    "image_sha256": item.input_sha256,
                    "reference_sha256": reference_hashes[item.item_id],
                    "adapter_config_sha256": config_hash}
        if report.is_file():
            state = _verify_existing(report, identity)
            counts["reused"] += 1
            origin = "existing"
        else:
            if output.exists() or report.with_suffix(".identity.json").exists():
                raise FileExistsError(f"Partial frozen result needs inspection: {output}")
            reused = (_reusable_primary_result(name, row, config_hash, freeze_hash,
                                               primary_rows, freeze["reference_audit"],
                                               primary_reference_hashes)
                      if collection == "smb-complete" else None)
            if reused is not None:
                _write_once(report, reused)
                state = reused["status"]
                origin = "reused_primary"
                counts["reused_primary"] += 1
            else:
                result = run_with_typed_failure(adapter, item, output)
                if result.status.value == "unavailable":
                    raise RuntimeError(f"Frozen runtime became unavailable on {item.item_id}")
                write_result(report, result)
                state = result.status.value
                origin = "inferred"
                counts[state] += 1
            _write_once(report.with_suffix(".identity.json"), identity)
        print(json.dumps({"item": offset, "total": len(rows), "id": item.item_id,
                          "candidate": name, "collection": collection,
                          "status": state, "origin": origin,
                          "result": report.relative_to(WORKSPACE).as_posix()},
                         sort_keys=True), flush=True)
    print(json.dumps({"candidate": name, "collection": collection,
                      "selected_count": len(selected),
                      "counts": counts, "freeze_sha256": freeze_hash}, sort_keys=True), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--candidate", choices=PAGE_CANDIDATES, required=True)
    parser.add_argument("--collection", choices=COLLECTIONS, default="smb-pianoform")
    parser.add_argument("--start-index", type=int, default=1)
    parser.add_argument("--max-items", type=int, default=0)
    args = parser.parse_args()
    run(args.candidate, args.freeze, args.collection, args.start_index, args.max_items)


if __name__ == "__main__":
    main()
