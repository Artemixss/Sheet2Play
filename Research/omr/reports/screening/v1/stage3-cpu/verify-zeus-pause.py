"""Verify saved scores at the user's pause without restarting any worker."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from screening_common import completed_path, output_root, read_json, scored_path, write_new
from screening_cpu_manifest import verify_manifest
from screening_consolidated_report import verified_cpu_score
from screening_cpu_score import score_identity
from sheet2play_omr.adapter_contract import sha256_file

manifest_path = Path("Research/omr/reports/screening/v1/manifest-v5-607ff64134da.json").resolve()
manifest = verify_manifest(manifest_path)
root = output_root(manifest_path)
session = read_json(root / "sessions/stage3-zeus-screen-01.json")
if (root / "worker.lock").exists() or session["active_since_utc"] is not None:
    raise RuntimeError("Pause verification requires a closed worker and session")
config = manifest["candidates"]["zeus_page"]["identity_sha256"]
records = []
for item in manifest["items"][:23]:
    result = completed_path(root, "zeus_page", item["id"], config) / "result.json"
    directory = scored_path(root, "zeus_page", item["id"], config, manifest["scorer_sha256"])
    row = verified_cpu_score(directory, score_identity(manifest, "zeus_page", item, result))
    records.append({"item_id": item["id"], "score_sha256": sha256_file(directory / "score.json"),
                    "omr_ned_status": row["omr_ned_status"]})
pending_item = manifest["items"][23]
if scored_path(root, "zeus_page", pending_item["id"], config, manifest["scorer_sha256"]).exists():
    raise ValueError("Pause coverage changed; inspect before recording it")
evidence = {"manifest_sha256": sha256_file(manifest_path), "configuration_sha256": config,
            "sample_sha256": manifest["sample_sha256"], "verified_score_count": len(records),
            "pending_item": pending_item["id"], "session": session, "records": records}
destination = Path(__file__).with_name("zeus-pause-audit-20260930.json")
if destination.exists():
    if read_json(destination) != evidence:
        raise ValueError("Existing pause audit differs from reverified saved scores")
else:
    write_new(destination, evidence)
print(json.dumps({"verified_scores": len(records), "ned_statuses": sorted({r['omr_ned_status'] for r in records}),
                  "pending_item": pending_item["id"], "session_seconds": session["used_seconds"]}))
