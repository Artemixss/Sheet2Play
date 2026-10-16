"""Attest a successful complete-page development smoke for a pinned screen configuration."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from screening_common import (HERE, WORKSPACE, digest, output_root, read_json,
                               write_new)
from screening_cpu_manifest import require_current_policy, verify_manifest
from screening_cpu_profile import cpu_environment

from sheet2play_omr.adapter_contract import sha256_file


def allowed_development_pages() -> dict[str, dict[str, Any]]:
    allowed = {}
    source = HERE / "reports/phase1/development-open.jsonl"
    for line in source.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row["composition_overlap_with_evaluation"]:
            raise ValueError("Development composition overlaps evaluation")
        for index, page in enumerate(row["page_images"], 1):
            allowed[f"{row['id']}-page-{index}"] = {
                "image_path": page["path"], "image_sha256": page["sha256"],
                "composition_group": row["composition_group"]}
    return allowed


def validate_development_report(manifest: dict[str, Any], candidate: str,
                                report_path: Path) -> tuple[dict[str, Any], Path]:
    report_path = report_path.resolve()
    if not report_path.is_relative_to(WORKSPACE.resolve()) or not report_path.is_file():
        raise ValueError("Development report must exist inside the workspace")
    result = read_json(report_path)
    config = manifest["candidates"][candidate]
    if config["identity"] is None:
        raise ValueError(f"Candidate has no verified identity: {candidate}")
    allowed = allowed_development_pages().get(result.get("item_id"))
    if allowed is None:
        raise ValueError("Development result is not a frozen development page")
    if (result.get("status") != "succeeded" or result.get("measurement_path") != "complete_document"
            or result.get("exit_status") != 0 or result.get("composition_group") != allowed["composition_group"]
            or result.get("adapter_config_sha256") != config["identity"]["adapter_config_sha256"]
            or result.get("provenance", {}).get("input_sha256") != allowed["image_sha256"]
            or digest(result.get("provenance", {}).get("adapter_config")) !=
            config["identity"]["adapter_config_sha256"]):
        raise ValueError("Development outcome does not match the screened configuration")
    image = WORKSPACE / allowed["image_path"]
    if sha256_file(image) != allowed["image_sha256"]:
        raise ValueError("Development input image changed")
    if not {"native", "musicxml", "canonical_events"} <= {
            artifact["role"] for artifact in result.get("artifacts", [])}:
        raise ValueError("Successful development result lacks complete-path artifacts")
    for artifact in result["artifacts"]:
        source = (WORKSPACE / artifact["path"]).resolve()
        if (not source.is_relative_to(WORKSPACE.resolve()) or not source.is_file()
                or source.stat().st_size != artifact["bytes"]
                or sha256_file(source) != artifact["sha256"]):
            raise ValueError("Development artifact is missing or changed")
    sidecar = report_path.with_suffix(".identity.json")
    saved = read_json(sidecar)
    required = {"item_id": result["item_id"], "input_sha256": allowed["image_sha256"],
                "adapter_config_sha256": config["identity"]["adapter_config_sha256"],
                "report_sha256": sha256_file(report_path),
                "resource_policy_sha256": digest(manifest["resource_policy"])}
    if any(saved.get(key) != value for key, value in required.items()):
        raise ValueError("Development identity sidecar differs")
    if (saved.get("priority") != "below_normal" or
            saved.get("cpu_affinity_count") != config["identity"]["adapter_config"]["settings"]["cpu_affinity_count"]):
        raise ValueError("Development worker did not verify resource limits")
    if candidate in {"homr_455", "fine_tuned_homr"}:
        compatibility = config["identity"]["compatibility_report"]
        expected_ram_limit = config["identity"]["adapter_config"]["settings"]["development_ram_admission_percent"]
        compatibility_path = (WORKSPACE / compatibility["path"]).resolve()
        if (not compatibility_path.is_relative_to(WORKSPACE.resolve()) or
                not compatibility_path.is_file() or
                sha256_file(compatibility_path) != compatibility["sha256"] or
                result.get("compatibility_report") != compatibility or
                saved.get("compatibility_report") != compatibility or
                saved.get("development_ram_admission_percent") != expected_ram_limit):
            raise ValueError(f"{candidate} development compatibility evidence differs")
    settings = config["identity"]["adapter_config"]["settings"]
    if (saved.get("cpu_profile_sha256") != settings["cpu_profile_sha256"]
            or saved.get("development_entry_sha256") != sha256_file(HERE / "screening_cpu_development.py")
            or saved.get("effective_cpu_environment") != settings["cpu_environment"]
            or saved.get("development_ram_admission_percent") != manifest["resource_policy"]["ram_admission_percent"]):
        raise ValueError("CPU development source, environment or RAM witness differs")
    return result, sidecar


def admit(manifest_path: Path, candidate: str, report_path: Path) -> Path:
    manifest = verify_manifest(manifest_path)
    require_current_policy(manifest)
    if candidate not in manifest["candidates"]:
        raise ValueError("Candidate is not registered")
    result, sidecar = validate_development_report(manifest, candidate, report_path)
    entry = manifest["candidates"][candidate]
    payload = {"schema_version": 1, "status": "passed", "complete_page": True,
               "sample_sha256": manifest["sample_sha256"],
               "candidate": candidate,
               "configuration_sha256": entry["identity_sha256"],
               "adapter_config_sha256": entry["identity"]["adapter_config_sha256"],
               "development_item_id": result["item_id"],
               "development_report": str(report_path.resolve().relative_to(WORKSPACE)).replace("\\", "/"),
               "development_report_sha256": sha256_file(report_path),
               "development_identity_sha256": sha256_file(sidecar),
               "scope": "development_entry_only; does not authorize screening inference"}
    if candidate in {"homr_455", "fine_tuned_homr"}:
        payload["compatibility_report_sha256"] = entry["identity"]["compatibility_report"]["sha256"]
    root = output_root(manifest_path)
    path = (root / "admissions" / candidate / entry["identity_sha256"][:12] /
            f"admission-{digest(payload)[:12]}.json")
    if path.exists():
        if read_json(path) != payload:
            raise ValueError("Existing admission differs")
    else:
        write_new(path, payload)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--development-report", type=Path, required=True)
    args = parser.parse_args()
    path = admit(args.manifest.resolve(), args.candidate, args.development_report.resolve())
    print(json.dumps({"admission": str(path), "sha256": sha256_file(path),
                      "screening_inference_started": False}))


if __name__ == "__main__":
    main()
