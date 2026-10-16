"""Read-only recovery of interrupted Phase-3 evidence; never launches inference."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any

from phase3_freeze import verify_freeze, verify_secondary_audit
from phase3_infer import _paths
from sheet2play_omr.adapter_contract import sha256_file
from sheet2play_omr.phase3_references import frozen_smb_rows

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[1]
FREEZE = HERE / "reports/phase3/phase3-config-freeze-v1-89f385c8790b.json"
FREEZE_HASH = "3fdd3d76aeab4188244795ea7b5eb310b2129d8d50131290297aeb1a32020633"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def file_record(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(WORKSPACE).as_posix(), "bytes": path.stat().st_size,
            "sha256": sha256_file(path), "mtime_ns": path.stat().st_mtime_ns}


def verify_completed(path: Path, identity: dict[str, Any], group: str,
                     workspace: Path) -> dict[str, Any]:
    """Check failed outcomes too, without using prediction quality for selection."""
    if read_json(path.with_suffix(".identity.json")) != identity:
        raise ValueError("Identity sidecar mismatch")
    result = read_json(path)
    provenance = result["provenance"]
    config = provenance["adapter_config"]
    digest = hashlib.sha256(json.dumps(config, sort_keys=True, separators=(",", ":"),
                                       ensure_ascii=False).encode()).hexdigest()
    if (result["schema_version"] != 1 or result["item_id"] != identity["item_id"]
            or result["composition_group"] != group
            or result["measurement_path"] != "complete_document"
            or result["adapter_config_sha256"] != identity["adapter_config_sha256"]
            or digest != identity["adapter_config_sha256"]
            or provenance["input_sha256"] != identity["image_sha256"]
            or result["candidate_id"] != config["candidate_id"]
            or result["adapter_id"] != config["adapter_id"]
            or provenance["source_revision"] != config["source_revision"]):
        raise ValueError("Result/configuration/input identity mismatch")
    status = result["status"]
    artifacts = result["artifacts"]
    if status == "succeeded":
        if (result["exit_status"] != 0 or result["error"] is not None
                or not {"native", "musicxml", "canonical_events"} <=
                {artifact["role"] for artifact in artifacts} or not result["timings"]):
            raise ValueError("Incomplete successful outcome")
    elif status == "failed":
        if not result.get("error", {}).get("code"):
            raise ValueError("Failure has no typed error")
    else:
        raise ValueError("Outcome is pending or unavailable, not completed")
    for artifact in artifacts:
        source = (workspace / artifact["path"]).resolve()
        if not source.is_relative_to(workspace.resolve()):
            raise ValueError("Artifact escapes workspace")
        if (not source.is_file() or source.stat().st_size != artifact["bytes"]
                or sha256_file(source) != artifact["sha256"]):
            raise ValueError(f"Artifact hash/size mismatch: {source}")
    return {"status": status, "artifact_count": len(artifacts),
            "error_code": (result.get("error") or {}).get("code"),
            "report_sha256": sha256_file(path),
            "sidecar_sha256": sha256_file(path.with_suffix(".identity.json"))}


def preserve_history(destination: Path, partials: list[Path]) -> list[dict[str, Any]]:
    runtime = HERE / ".runtime/phase3"
    files = set(runtime.glob("*.log"))
    files.update((runtime / "sequence/3fdd3d76aeab").rglob("*"))
    for partial in partials:
        files.update(partial.rglob("*"))
        (destination / partial.relative_to(runtime)).mkdir(parents=True, exist_ok=True)
    records = []
    for source in sorted(path for path in files if path.is_file()):
        target = destination / source.relative_to(runtime)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        record = file_record(source)
        if sha256_file(target) != record["sha256"]:
            raise OSError(f"Preservation copy differs: {source}")
        records.append(record)
    return records


def audit(destination: Path) -> dict[str, Any]:
    destination.mkdir(parents=True, exist_ok=False)
    if sha256_file(FREEZE) != FREEZE_HASH:
        raise ValueError("Historical freeze bytes changed")
    freeze = verify_freeze(FREEZE)
    secondary = verify_secondary_audit()
    audit_identity = freeze["reference_audit"]
    references = {entry["id"]: entry["reference_sha256"]
                  for entry in read_json(WORKSPACE / audit_identity["path"])["items"]}
    config = freeze["ready"]["homr_page"]["adapter_config_sha256"]
    completed, pending, corrupt, partials = [], [], [], []
    expected_files: set[Path] = set()
    for index, row in enumerate(frozen_smb_rows(WORKSPACE, "smb-pianoform"), 1):
        report, raw = _paths("homr_page", row["id"], config, "smb-pianoform",
                             audit_identity["sha256"])
        sidecar = report.with_suffix(".identity.json")
        expected_files.update((report, sidecar))
        identity = {"schema_version": 1, "freeze_sha256": FREEZE_HASH,
                    "collection": "smb-pianoform", "reference_audit_sha256": audit_identity["sha256"],
                    "candidate": "homr_page", "item_id": row["id"],
                    "image_sha256": row["image_sha256"], "reference_sha256": references[row["id"]],
                    "adapter_config_sha256": config}
        item = {"index": index, "item_id": row["id"], "report": str(report.relative_to(WORKSPACE))}
        if report.is_file():
            try:
                completed.append({**item, **verify_completed(report, identity,
                                                             row["composition_group"], WORKSPACE)})
            except (OSError, ValueError, KeyError, TypeError) as error:
                corrupt.append({**item, "error": str(error)})
        else:
            if raw.exists():
                partials.append(raw)
            pending.append({**item, "raw_directory_exists": raw.exists(),
                            "orphan_sidecar": sidecar.exists(),
                            "partial_files": [file_record(p) for p in sorted(raw.rglob("*")) if p.is_file()]})
    report_dir = HERE / "reports/phase3/evaluation/smb-pianoform/homr_page"
    unexpected = [str(p.relative_to(WORKSPACE)) for p in report_dir.glob("*.json")
                  if p not in expected_files]
    preserved = preserve_history(destination / "preserved", partials)
    state = read_json(HERE / ".runtime/phase3/sequence/3fdd3d76aeab/state.json")
    result = {"schema_version": 1, "checked_utc": datetime.now(timezone.utc).isoformat(),
              "command": " ".join(__import__("sys").argv), "working_directory": str(WORKSPACE),
              "audit_source": file_record(Path(__file__).resolve()),
              "freeze": file_record(FREEZE), "live_freeze_identity_verified": True,
              "primary_audit": audit_identity, "secondary_audit": secondary,
              "completed": completed, "pending": pending, "corrupt": corrupt,
              "unexpected_reports": unexpected, "preserved": preserved,
              "historical_state": state, "reconciled_status": "interrupted_retired_do_not_resume",
              "reuse_scope": "Verified historical identity only; new screening identity must match all relevant fields. Timing is not comparable to resource-limited runs.",
              "counts": dict(Counter(item["status"] for item in completed)),
              "inference_started": False}
    (destination / "audit.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New evidence directory")
    args = parser.parse_args()
    result = audit(args.output.resolve())
    print(json.dumps({"counts": result["counts"], "pending": len(result["pending"]),
                      "corrupt": len(result["corrupt"]),
                      "unexpected": len(result["unexpected_reports"]),
                      "artifacts": sum(item["artifact_count"] for item in result["completed"])}))
    if result["corrupt"] or result["unexpected_reports"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
