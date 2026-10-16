"""Freeze and recheck the reduced, development-qualified Phase-3 roster."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
from importlib import metadata
from pathlib import Path
from typing import Any

from phase2r import verify_historical_artifacts
from phase3_development_entry import _adapter, _identity
from phase3_private_preflight import REPORT as PRIVATE_PREFLIGHT_REPORT, verify as verify_private_preflight
from sheet2play_omr.adapter_contract import sha256_file
from sheet2play_omr.phase2r_identity import (
    _homr_identity, _zeus_identity, file_identity, source_tree_identity,
)
from sheet2play_omr.phase3_references import frozen_smb_rows, reference_identity


WORKSPACE = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
REPORTS = HERE / "reports" / "phase3"
READY = ("homr_page", "audiveris_page", "zeus_page", "zeus_system")


def _version(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError as error:
        raise RuntimeError(f"Required scoring package is missing: {name}") from error


def _installed_distributions(venv: Path) -> dict[str, str]:
    installed = venv / "Lib" / "site-packages"
    if not installed.is_dir():
        raise RuntimeError(f"Candidate Python environment is missing: {venv}")
    packages: dict[str, str] = {}
    for distribution in metadata.distributions(path=[str(installed)]):
        name = distribution.metadata.get("Name", "").strip().lower().replace("_", "-")
        if not name or not distribution.version:
            continue
        if name in packages:
            raise RuntimeError(f"Candidate Python environment has ambiguous package metadata: {venv}")
        packages[name] = distribution.version
    if not packages:
        raise RuntimeError(f"Candidate Python environment has no package metadata: {venv}")
    return dict(sorted(packages.items()))


def _audiveris_identity() -> dict[str, Any]:
    root = HERE / ".runtime" / "phase2r" / "audiveris-extract" / "Audiveris"
    executable = root / "Audiveris.exe"
    jars = list((root / "app").rglob("*.jar"))
    if not executable.is_file() or not jars:
        raise RuntimeError("Pinned Audiveris executable or application JARs are missing")
    historical_path = HERE / "reports" / "phase2r" / "runtime-identity-v1.json"
    historical = json.loads(historical_path.read_text(encoding="utf-8"))["runtime_identity"]
    version = historical["audiveris_version"]
    recorded_executable = historical["files"]["audiveris_executable"]
    current_executable = file_identity(executable)
    if (version["status"] != "verified" or "5.11.0" not in version["version_output"]
            or recorded_executable["sha256"] != current_executable["sha256"]
            or recorded_executable["status"] != "verified"):
        raise RuntimeError("Audiveris version evidence or executable hash changed")
    return {
        "executable": current_executable,
        "version_evidence": version,
        "version_evidence_report_sha256": sha256_file(historical_path),
        "application_jars": source_tree_identity(root / "app", jars),
        "java": file_identity(root / "runtime" / "bin" / "java.exe"),
    }


def _entry_identity(name: str) -> dict[str, Any]:
    adapter, item = _adapter(name)
    item.validate()
    if not adapter.probe()["available"]:  # type: ignore[attr-defined]
        raise RuntimeError(f"Phase-3 entry runtime unavailable: {name}")
    digest, files = _identity(name, adapter, item)
    path = REPORTS / "development-entry" / f"{name}-{item.item_id}-{digest[:12]}.json"
    sidecar = path.with_suffix(".identity.json")
    if not path.is_file() or not sidecar.is_file():
        raise RuntimeError(f"Phase-3 development entry missing for {name}: {path}")
    result = json.loads(path.read_text(encoding="utf-8"))
    saved_identity = json.loads(sidecar.read_text(encoding="utf-8"))
    if (saved_identity != files or result.get("status") != "succeeded"
            or result.get("adapter_config_sha256") != adapter.config.sha256  # type: ignore[attr-defined]
            or result.get("provenance", {}).get("input_sha256") != item.input_sha256):
        raise RuntimeError(f"Development entry identity or status changed: {name}")
    for artifact in result["artifacts"]:
        artifact_path = Path(artifact["path"])
        resolved = artifact_path if artifact_path.is_absolute() else WORKSPACE / artifact_path
        if not resolved.is_file() or sha256_file(resolved) != artifact["sha256"]:
            raise RuntimeError(f"Development artifact changed: {resolved}")
    return {
        "adapter_config": adapter.config.to_json(),  # type: ignore[attr-defined]
        "adapter_config_sha256": adapter.config.sha256,  # type: ignore[attr-defined]
        "source_input_identity_sha256": digest,
        "source_input_identity": files,
        "entry_report": path.relative_to(WORKSPACE).as_posix(),
        "entry_report_sha256": sha256_file(path),
        "entry_identity_sha256": sha256_file(sidecar),
    }


def _reference_audit(collection: str = "smb-pianoform") -> dict[str, Any]:
    expected_count = {"smb-pianoform": 402, "smb-complete": 611}.get(collection)
    if expected_count is None:
        raise ValueError(f"Unsupported frozen SMB collection: {collection}")
    identity = reference_identity(WORKSPACE, collection)
    path = REPORTS / f"reference-audit-{collection}-full-{identity['builder_sha256'][:12]}.json"
    if not path.is_file():
        raise RuntimeError(f"Current full {collection} reference audit is missing: {path}")
    report = json.loads(path.read_text(encoding="utf-8"))
    if (report.get("identity") != identity or report.get("eligible_count") != expected_count
            or report.get("valid_count") != expected_count or report.get("invalid_count") != 0):
        raise RuntimeError(f"Current full {collection} reference audit did not pass {expected_count}/{expected_count}")
    if (len(report["items"]) != expected_count
            or len({item["id"] for item in report["items"]}) != expected_count):
        raise RuntimeError("SMB reference audit coverage is incomplete or duplicated")
    if {item["id"] for item in report["items"]} != {
            row["id"] for row in frozen_smb_rows(WORKSPACE, collection)}:
        raise RuntimeError("SMB reference audit item set differs from the frozen manifest")
    pedal_warnings = {
        "MusicXMLWarning: Could not import pedal: Error in getting PedalMark",
        "MusicXMLWarning: Could not import pedal: unidentified mxType of pedal: sustain",
    }
    voice_warning = ("MusicXMLWarning: Cannot put in an element with a missing voice tag "
                     "when no previous voice tag was given.  Assuming voice 1... ")
    pedal_warning_count = 0
    voice_warning_count = 0
    for item in report["items"]:
        reference = WORKSPACE / item["reference_path"]
        if not reference.is_file() or sha256_file(reference) != item["reference_sha256"]:
            raise RuntimeError(f"Reference artifact changed: {reference}")
        payload = json.loads(reference.read_text(encoding="utf-8"))
        if (payload.get("item_id") != item["id"] or payload.get("identity") != identity
                or len(payload.get("notes", [])) != item["note_count"]):
            raise RuntimeError(f"SMB canonical reference changed: {reference}")
        warnings = payload["normalization_warnings"]
        if len(warnings) != item["normalization_warning_count"] or any(
                warning not in pedal_warnings | {voice_warning} for warning in warnings):
            raise RuntimeError(f"SMB reference has unreviewed normalization warnings: {reference}")
        pedal_warning_count += sum(warning in pedal_warnings for warning in warnings)
        voice_warning_count += warnings.count(voice_warning)
        if not payload.get("roundtrip_note_timing_verified"):
            raise RuntimeError(f"SMB reference timing was not verified: {reference}")
        musicxml = WORKSPACE / payload["reference_musicxml"]
        if (not musicxml.is_file()
                or sha256_file(musicxml) != payload["reference_musicxml_sha256"]
                or item["reference_musicxml_sha256"] != payload["reference_musicxml_sha256"]):
            raise RuntimeError(f"Reference MusicXML changed: {musicxml}")
    return {"path": path.relative_to(WORKSPACE).as_posix(), "sha256": sha256_file(path),
            "identity": identity, "eligible_count": expected_count, "valid_count": expected_count,
            "pedal_import_warning_count": pedal_warning_count,
            "missing_voice_tag_warning_count": voice_warning_count,
            "warning_interpretation": "Pedal marks and missing voice tags may affect notation-detail or voice diagnostics; exact pitch/onset/duration raw note timing was separately verified"}


def verify_secondary_audit() -> dict[str, Any]:
    audit = _reference_audit("smb-complete")
    rows = frozen_smb_rows(WORKSPACE, "smb-complete")
    if len(rows) != 611:
        raise RuntimeError("Frozen complete SMB count changed")
    for row in rows:
        image = HERE / "data" / "smb" / row["image_path"]
        if not image.is_file() or sha256_file(image) != row["image_sha256"]:
            raise RuntimeError(f"Frozen complete SMB image missing or changed: {image}")
    return audit


def _input_identity() -> dict[str, Any]:
    rows = frozen_smb_rows(WORKSPACE, "smb-pianoform")
    if len(rows) != 402:
        raise RuntimeError("Frozen primary SMB count changed")
    for row in rows:
        image = HERE / "data" / "smb" / row["image_path"]
        if not image.is_file() or sha256_file(image) != row["image_sha256"]:
            raise RuntimeError(f"Frozen primary SMB image missing or changed: {image}")
    return {"collection": "smb-pianoform", "count": 402,
            "manifest_sha256": sha256_file(HERE / "reports" / "phase1" / "smb-pianoform.jsonl"),
            "all_image_hashes_verified": True}


def _olimpic_audit() -> dict[str, Any]:
    builder = HERE / "phase3_olimpic.py"
    path = REPORTS / f"olimpic-canary-reference-audit-{sha256_file(builder)[:12]}.json"
    if not path.is_file():
        raise RuntimeError(f"Frozen OLiMPiC system reference audit is missing: {path}")
    report = json.loads(path.read_text(encoding="utf-8"))
    manifest_path = HERE / "reports" / "phase1" / "olimpic-canary.jsonl"
    rows = [json.loads(line) for line in manifest_path.read_text(encoding="utf-8").splitlines() if line]
    by_id = {row["id"]: row for row in rows}
    if (len(rows) != 100 or len(by_id) != 100 or report.get("valid_count") != 100
            or report.get("invalid_count") != 0 or len(report.get("items", [])) != 100
            or {item["id"] for item in report["items"]} != set(by_id)
            or report.get("manifest_sha256") != sha256_file(manifest_path)
            or report.get("normalizer_sha256") != sha256_file(WORKSPACE / "Bridge" / "musicxml_normalizer.py")
            or report.get("builder_sha256") != sha256_file(builder)):
        raise RuntimeError("Frozen OLiMPiC reference audit identity or coverage changed")
    for item in report["items"]:
        row = by_id[item["id"]]
        reference = WORKSPACE / item["reference_path"]
        image = WORKSPACE / row["image_path"]
        musicxml = WORKSPACE / row["musicxml_path"]
        if (not reference.is_file() or sha256_file(reference) != item["reference_sha256"]
                or not image.is_file() or sha256_file(image) != row["image_sha256"]
                or not musicxml.is_file() or sha256_file(musicxml) != row["musicxml_sha256"]):
            raise RuntimeError(f"Frozen OLiMPiC source changed: {item['id']}")
        payload = json.loads(reference.read_text(encoding="utf-8"))
        if (payload.get("item_id") != item["id"]
                or payload.get("identity") != {
                    "manifest_sha256": report["manifest_sha256"],
                    "normalizer_sha256": report["normalizer_sha256"],
                    "builder_sha256": report["builder_sha256"]}
                or payload.get("image_sha256") != row["image_sha256"]
                or payload.get("reference_musicxml_sha256") != row["musicxml_sha256"]
                or len(payload.get("notes", [])) != item["note_count"]
                or len(payload.get("normalization_warnings", [])) != item["warning_count"]):
            raise RuntimeError(f"Frozen OLiMPiC canonical reference changed: {item['id']}")
    return {"path": path.relative_to(WORKSPACE).as_posix(), "sha256": sha256_file(path),
            "manifest_sha256": sha256_file(manifest_path), "eligible_count": 100,
            "warning_count": sum(item["warning_count"] for item in report["items"])}


def snapshot() -> dict[str, Any]:
    verify_historical_artifacts()
    comparison = HERE / "comparison-config-v2.json"
    protocol = HERE / "reports" / "phase1" / "scoring-protocol.json"
    config = json.loads(comparison.read_text(encoding="utf-8"))
    if sha256_file(protocol) != config["phase1_protocol"]["sha256"]:
        raise RuntimeError("Frozen Phase-1 scoring protocol changed")
    scoring = json.loads(protocol.read_text(encoding="utf-8"))
    versions = {name: _version(name) for name in ("music21", "converter21", "musicdiff")}
    if versions != scoring["frozen_parser_versions"]:
        raise RuntimeError(f"Scoring parser versions differ from the freeze: {versions}")
    homr = _homr_identity(WORKSPACE)
    if not homr["source_revision_verified"] or homr["weight_count"] != 5 or homr["tokenizer_count"] != 4:
        raise RuntimeError("Shipped HOMR source, weights, or tokenizers are incomplete")
    zeus = _zeus_identity(WORKSPACE)
    if any(value["status"] != "hashed" for value in zeus["checkpoint"].values()):
        raise RuntimeError("Zeus checkpoint files are missing")
    research_sources = {
        name: sha256_file(HERE / name)
        for name in ("phase3_freeze.py", "phase3_infer.py", "phase3_score.py",
                     "phase3_olimpic.py",
                     "phase3_private_preflight.py",
                     "phase3_private_diagnostic.py",
                     "phase3_sequence.py",
                     "phase3_bootstrap.py",
                     "phase3_reference_audit.py", "src/sheet2play_omr/phase3_references.py",
                     "src/sheet2play_omr/phase3_scoring.py", "src/sheet2play_omr/metrics.py",
                     "src/sheet2play_omr/omr_ned.py")
    }
    private_preflight = verify_private_preflight()
    return {
        "schema_version": 1,
        "phase": "3_pretrained_reduced_roster",
        "phase4_started": False,
        "approval_baseline": "fine_tuned_homr_pending_phase4",
        "comparison_config_sha256": sha256_file(comparison),
        "scoring_protocol_sha256": sha256_file(protocol),
        "failure_policy": scoring["failure_policy"],
        "normalization": scoring["normalization"],
        "measurement_paths": scoring["measurement_paths"],
        "input": _input_identity(),
        "reference_audit": _reference_audit(),
        "olimpic_system_audit": _olimpic_audit(),
        "private_diagnostic": {
            "preflight_report": PRIVATE_PREFLIGHT_REPORT.relative_to(WORKSPACE).as_posix(),
            "preflight_sha256": sha256_file(PRIVATE_PREFLIGHT_REPORT),
            "rendered_pages": len(private_preflight["pages"]),
            "ranking_eligible": False,
        },
        "ready": {name: _entry_identity(name) for name in READY},
        "runtime": {"homr": homr, "zeus": zeus, "audiveris": _audiveris_identity(),
                    "research_python": file_identity(HERE / ".venv" / "Scripts" / "python.exe"),
                    "homr_python": file_identity(WORKSPACE / "Bridge" / ".venv-homr-gpu" / "Scripts" / "python.exe"),
                    "zeus_python": file_identity(HERE / "zeus" / ".venv" / "Scripts" / "python.exe"),
                    "python_distributions": {
                        "research": _installed_distributions(HERE / ".venv"),
                        "homr": _installed_distributions(WORKSPACE / "Bridge" / ".venv-homr-gpu"),
                        "zeus": _installed_distributions(HERE / "zeus" / ".venv"),
                    }},
        "scoring_versions": versions,
        "research_source_sha256": research_sources,
        "platform": platform.platform(),
        "training_overlap": {"shipped_homr": "unknown", "audiveris": "unknown",
                             "zeus": "known OLiMPiC repertoire family; SMB overlap unknown"},
        "excluded": {
            "zeus_direct_app_extraction": "development event extraction failure; separate integration evidence",
            "rokot_q8_page": "no accepted corrected development page",
            "qwen3_vl_2b_instruct": "no accepted development output under tested settings",
            "legato": "recognition checkpoint/runtime not provisioned or measured",
            "homr_pr156": "compatible weights unverified",
            "musvit": "requires training and decoder verification; not evaluated",
            "fine_tuned_homr": "Phase 4 checkpoint verification and selection",
        },
        "scope": {"local_first": True, "cloud_spend_usd": 0.0,
                  "primary_pages": 402, "page_and_system_tracks_separate": True,
                  "olimpic_annotated_systems": 100,
                  "no_promotion": True, "frozen_inference_started": False},
    }


def _digest(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode("utf-8")).hexdigest()


def create_freeze() -> Path:
    payload = snapshot()
    digest = _digest(payload)
    destination = REPORTS / f"phase3-config-freeze-v1-{digest[:12]}.json"
    if destination.exists():
        if json.loads(destination.read_text(encoding="utf-8")) != payload:
            raise RuntimeError("Existing Phase-3 freeze has a different payload")
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
                         encoding="utf-8")
    temporary.replace(destination)
    return destination


def verify_freeze(path: Path) -> dict[str, Any]:
    saved = json.loads(path.read_text(encoding="utf-8"))
    current = snapshot()
    if saved != current:
        raise RuntimeError("Phase-3 runtime, configuration, inputs, or scorer changed since freeze")
    return saved


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    path = args.verify if args.verify else create_freeze()
    payload = verify_freeze(path)
    print(json.dumps({"freeze": str(path), "sha256": sha256_file(path),
                      "ready": sorted(payload["ready"]), "primary_pages": payload["input"]["count"]},
                     sort_keys=True))


if __name__ == "__main__":
    main()
