"""Verify preserved intermediate evidence after the full Zeus screen closes."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from screening_common import WORKSPACE, completed_path, output_root, read_json, result_identity, verify_completed, write_new
from screening_cpu_manifest import verify_manifest
from sheet2play_omr.adapter_contract import sha256_file


def raw_evidence(result, item):
    native = next((entry for entry in result["artifacts"] if entry["role"] == "native"), None)
    if result["status"] != "succeeded":
        return {"item_id": item["id"], "status": result["status"], "error": result["error"],
                "declared_artifacts": result["artifacts"]}
    if native is None:
        raise ValueError(f"Successful Zeus page lacks native LMX: {item['id']}")
    raw = (WORKSPACE / native["path"]).parent
    crops = read_json(raw / "detector/crop-manifest.json")
    if crops["source_image"]["sha256"] != item["image_sha256"]:
        raise ValueError(f"Crop source differs: {item['id']}")
    detector = raw / "detector/detector-preprocessed.png"
    if sha256_file(detector) != crops["detector_image"]["sha256"]:
        raise ValueError(f"Detector image changed: {item['id']}")
    if len(read_json(WORKSPACE / native["path"])) != len(crops["crops"]):
        raise ValueError(f"Native LMX/system count differs: {item['id']}")
    for crop in crops["crops"]:
        crop_path = raw / "detector" / f"system-{crop['system']:04d}.png"
        if sha256_file(crop_path) != crop["sha256"]:
            raise ValueError(f"Preserved crop changed: {item['id']} system {crop['system']}")
        if not (raw / f"system-{crop['system']:04d}.musicxml").is_file():
            raise ValueError(f"Preserved system XML missing: {item['id']} system {crop['system']}")
    required = ("detector/detected-systems.json", "score.musicxml", "canonical-events.json")
    if any(not (raw / name).is_file() for name in required):
        raise ValueError(f"Preserved detector/stitch/normalization evidence missing: {item['id']}")
    return {"item_id": item["id"], "status": result["status"], "systems": len(crops["crops"]),
            "raw_files": {str(file.relative_to(WORKSPACE)): sha256_file(file)
                          for file in sorted(raw.rglob("*")) if file.is_file()}}


manifest_path = Path("Research/omr/reports/screening/v1/manifest-v5-607ff64134da.json").resolve()
manifest = verify_manifest(manifest_path)
root = output_root(manifest_path)
session = read_json(root / "sessions/stage3-zeus-screen-01.json")
if (root / "worker.lock").exists() or session["active_since_utc"] is not None:
    raise RuntimeError("Screen must be closed before intermediate-evidence verification")
config = manifest["candidates"]["zeus_page"]["identity_sha256"]
records = []
for item in manifest["items"]:
    directory = completed_path(root, "zeus_page", item["id"], config)
    result = verify_completed(directory, result_identity(manifest, "zeus_page", item))
    records.append(raw_evidence(result, item))
evidence = {"manifest_sha256": sha256_file(manifest_path), "configuration_sha256": config,
            "sample_sha256": manifest["sample_sha256"], "records": records}
write_new(Path(__file__).with_name("zeus-preserved-evidence-audit.json"), evidence)
print(json.dumps({"verified_pages": len(records), "preserved_systems": sum(row.get("systems", 0) for row in records),
                  "hashed_raw_files": sum(len(row.get("raw_files", {})) for row in records)}))
