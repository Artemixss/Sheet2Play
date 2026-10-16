"""Verify the first closed Zeus chunk before continuing the frozen run."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from screening_common import completed_path, output_root, read_json, result_identity, verify_completed, write_new
from screening_cpu_manifest import verify_manifest
from sheet2play_omr.adapter_contract import sha256_file

manifest_path = Path("Research/omr/reports/screening/v1/manifest-v5-607ff64134da.json").resolve()
manifest = verify_manifest(manifest_path)
root = output_root(manifest_path)
session = read_json(root / "sessions/stage3-zeus-screen-01.json")
if (root / "worker.lock").exists() or session["active_since_utc"] is not None:
    raise RuntimeError("Chunk must be closed before verification")
config = manifest["candidates"]["zeus_page"]["identity_sha256"]
records = []
for item in manifest["items"][:5]:
    directory = completed_path(root, "zeus_page", item["id"], config)
    result = verify_completed(directory, result_identity(manifest, "zeus_page", item))
    records.append({"item_id": item["id"], "status": result["status"],
                    "error": result.get("error"), "result_sha256": sha256_file(directory / "result.json"),
                    "artifact_count": len(result["artifacts"])})
evidence = {"manifest_sha256": sha256_file(manifest_path), "configuration_sha256": config,
            "sample_sha256": manifest["sample_sha256"], "records": records, "session": session}
write_new(Path(__file__).with_name("zeus-first5-audit.json"), evidence)
print(json.dumps({"verified": len(records), "statuses": [row["status"] for row in records],
                  "session_seconds": session["used_seconds"]}))
