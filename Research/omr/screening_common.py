"""Immutable identities and storage contracts for the bounded OMR screen."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any
import uuid

from phase3_development_entry import _adapter, _source_paths
from phase3_freeze import verify_freeze
from sheet2play_omr.adapter_contract import sha256_file
from sheet2play_omr.phase3_references import frozen_smb_rows

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[1]
REPORTS = HERE / "reports/screening/v1"
FROZEN = HERE / "reports/phase3/phase3-config-freeze-v1-89f385c8790b.json"
SEED = "20260926"
GROUP_COUNTS = (("1-2", 7), ("3-4", 8), ("5+", 3))
BASE_RUNNABLE = ("homr_page", "audiveris_page", "zeus_page")
RUNNABLE = (*BASE_RUNNABLE, "homr_455", "fine_tuned_homr")
PINNED_V1_RUNNER_SHA256 = "0e7a288b0e9af3c20024f259f528ce8749b2556a530746d1f89606da74eeb72a"
LEGACY_POLICY = {"max_pages_per_chunk": 5, "session_seconds": 14400,
          "shutdown_reserve_seconds": 30, "sample_seconds": 5,
          "pressure_seconds": 30, "ram_admission_percent": 75,
          "device_vram_admission_percent": 90,
          "priority": "below_normal", "one_candidate_worker": True,
          "concurrent_scoring": False}
POLICY = {**LEGACY_POLICY, "ram_admission_percent": 90}


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_new(path: Path, payload: Any) -> None:
    """Publish a single file without replacing any existing evidence."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def stratum(size: int) -> str:
    if size < 1:
        raise ValueError("Composition group cannot be empty")
    return "1-2" if size <= 2 else "3-4" if size <= 4 else "5+"


def select_groups(rows: list[dict[str, Any]]) -> tuple[list[str], list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    ids: set[str] = set()
    for row in rows:
        if row["id"] in ids:
            raise ValueError(f"Duplicate item: {row['id']}")
        ids.add(row["id"])
        groups[row["composition_group"]].append(row)
    if len(rows) != 402 or len(groups) != 117:
        raise ValueError("Primary frozen manifest coverage changed")
    selected = []
    for category, count in GROUP_COUNTS:
        options = [group for group, items in groups.items() if stratum(len(items)) == category]
        options.sort(key=lambda group: (hashlib.sha256((SEED + group).encode("utf-8")).hexdigest(), group))
        if len(options) < count:
            raise ValueError(f"Not enough composition groups in {category}")
        selected.extend(options[:count])
    if len(selected) != 18 or len(set(selected)) != 18:
        raise ValueError("Selected composition groups are incomplete or duplicated")
    selected_set = set(selected)
    chosen = [row for row in rows if row["composition_group"] in selected_set]
    remainder = [row for row in rows if row["composition_group"] not in selected_set]
    if (len(chosen) + len(remainder) != 402 or
            {row["composition_group"] for row in chosen} &
            {row["composition_group"] for row in remainder}):
        raise ValueError("Screening and remainder groups overlap")
    return selected, chosen


def feature_coverage(rows: list[dict[str, Any]]) -> dict[str, Any]:
    keys = ("has_independent_voices", "cross_staff", "has_ties", "has_tuplets",
            "has_meter_changes", "has_repeats")
    features = {}
    for key in keys:
        counts = Counter(str(row["notation_features"].get(key, "unknown")).lower() for row in rows)
        features[key] = dict(sorted(counts.items()))
    return {"page_count": len(rows), "group_count": len({r["composition_group"] for r in rows}),
            "features": features,
            "note_token_count": {"min": min(r["notation_features"]["note_token_count"] for r in rows),
                                 "max": max(r["notation_features"]["note_token_count"] for r in rows)}}


def threads_limit() -> int:
    logical = os.cpu_count()
    if logical is None or logical < 2:
        raise RuntimeError("At least two logical processors are needed")
    return logical // 2


def screening_adapter(name: str, threads: int, runner_sha256: str,
                      policy: dict[str, Any] = POLICY):
    if name == "fine_tuned_homr":
        from screening_finetune_extension import fine_tune_adapter
        return fine_tune_adapter(threads, runner_sha256)
    if name == "homr_455":
        from screening_homr_extension import homr_455_adapter
        return homr_455_adapter(threads, runner_sha256)
    if name not in BASE_RUNNABLE:
        raise ValueError(f"No verified screening adapter: {name}")
    adapter, _ = _adapter(name)
    extra = {"screening_runner_sha256": runner_sha256,
             "screening_resource_policy_sha256": digest(policy),
             "cpu_threads": threads, "cpu_affinity_count": threads,
             "priority": "below_normal"}
    if name == "homr_page":
        launcher = HERE / "screening_homr_development_launcher.py"
        adapter.launcher = launcher
        extra["screening_launcher_sha256"] = sha256_file(launcher)
        extra["onnx_intra_op_threads"] = threads
        extra["onnx_inter_op_threads"] = 1
    adapter.config = replace(adapter.config, settings={**adapter.config.settings, **extra})
    return adapter


def candidate_identities(freeze: dict[str, Any], policy: dict[str, Any],
                         runner: str) -> dict[str, dict[str, Any]]:
    threads = threads_limit()
    candidates = {}
    for name in BASE_RUNNABLE:
        adapter = screening_adapter(name, threads, runner, policy)
        source_paths = _source_paths(name)
        if name == "homr_page":
            source_paths = [*source_paths, HERE / "screening_homr_development_launcher.py"]
        files = {path.resolve().relative_to(WORKSPACE).as_posix(): sha256_file(path)
                 for path in source_paths}
        runtime_key = "homr" if name == "homr_page" else "audiveris" if name == "audiveris_page" else "zeus"
        identity = {"adapter_config": adapter.config.to_json(),
                    "adapter_config_sha256": adapter.config.sha256,
                    "historical_entry_sha256": freeze["ready"][name]["entry_report_sha256"],
                    "source_files": files, "runtime": freeze["runtime"][runtime_key],
                    "resource_policy": policy,
                    "worker_source_sha256": runner,
                    "normalizer_sha256": sha256_file(WORKSPACE / "Bridge/musicxml_normalizer.py")}
        candidates[name] = {"status": "requires_screening_pipeline_development_entry",
                            "identity": identity, "identity_sha256": digest(identity)}
    fine_tune = HERE / "reports/screening/stage1-20260926/fine-tune-inventory.json"
    candidates["fine_tuned_homr"] = {"status": "blocked_export_identity_mismatch",
                                     "evidence_sha256": sha256_file(fine_tune),
                                     "identity": None, "identity_sha256": None}
    candidates["homr_455"] = {"status": "blocked_isolated_runtime_weights_decoder_unverified",
                              "identity": None, "identity_sha256": None}
    return candidates


def build_manifest(*, historical: bool = False) -> dict[str, Any]:
    if historical:
        from phase4_validation import historical_screen
        return historical_screen(REPORTS / "manifest-v1-9126bc5feefc.json")
    policy = LEGACY_POLICY if historical else POLICY
    schema_version = 1 if historical else 4
    runner = PINNED_V1_RUNNER_SHA256 if historical else sha256_file(HERE / "screening_run.py")
    freeze = verify_freeze(FROZEN)
    rows = frozen_smb_rows(WORKSPACE, "smb-pianoform")
    selected_groups, chosen = select_groups(rows)
    audit_path = WORKSPACE / freeze["reference_audit"]["path"]
    audit = read_json(audit_path)
    references = {entry["id"]: entry for entry in audit["items"]}
    if len(references) != 402 or set(references) != {row["id"] for row in rows}:
        raise ValueError("Frozen reference coverage changed")
    items = []
    for row in chosen:
        reference = references[row["id"]]
        image = HERE / "data/smb" / row["image_path"]
        canonical = WORKSPACE / reference["reference_path"]
        if (sha256_file(image) != row["image_sha256"] or
                sha256_file(canonical) != reference["reference_sha256"]):
            raise ValueError(f"Selected input/reference changed: {row['id']}")
        items.append({"id": row["id"], "composition_group": row["composition_group"],
                      "image_path": str(image.relative_to(WORKSPACE)).replace("\\", "/"),
                      "image_sha256": row["image_sha256"],
                      "source_revision": row["source_revision"],
                      "source_region_sha256": row["reference_region_sha256"],
                      "reference_path": reference["reference_path"],
                      "reference_sha256": reference["reference_sha256"],
                      "reference_musicxml_sha256": reference["reference_musicxml_sha256"],
                      "notation_features": row["notation_features"],
                      "training_overlap_by_candidate": row["training_overlap_by_candidate"]})
    remainder = [row for row in rows if row["composition_group"] not in set(selected_groups)]
    sample_identity = {"collection": "smb-pianoform", "seed": SEED,
                       "selected": [{"id": item["id"],
                                     "composition_group": item["composition_group"],
                                     "image_sha256": item["image_sha256"],
                                     "reference_sha256": item["reference_sha256"]} for item in items],
                       "protocol_sha256": sha256_file(HERE / "reports/phase1/scoring-protocol.json")}
    return {"schema_version": schema_version,
            "name": "smb-pianoform-screening-v1" if historical else "smb-pianoform-screening-v4-ram90",
            "collection": "smb-pianoform", "seed": SEED,
            "sample_sha256": digest(sample_identity),
            "selection_algorithm": "for each page-count stratum, ascending SHA-256 UTF-8 of seed concatenated with composition ID; tie-break composition ID; take 7, 8, 3 groups; keep all group pages in frozen manifest order",
            "strata": [{"name": label, "group_count": count} for label, count in GROUP_COUNTS],
            "selected_groups": selected_groups, "selected_group_count": len(selected_groups),
            "selected_item_count": len(items), "items": items,
            "remainder_group_count": len({r["composition_group"] for r in remainder}),
            "remainder_item_count": len(remainder),
            "selected_feature_coverage": feature_coverage(chosen),
            "remainder_feature_coverage": feature_coverage(remainder),
            "frozen_primary_manifest_sha256": sha256_file(HERE / "reports/phase1/smb-pianoform.jsonl"),
            "frozen_smb_lock_sha256": sha256_file(HERE / "smb.lock.json"),
            "reference_audit_sha256": sha256_file(audit_path),
            "historical_phase3_freeze_sha256": sha256_file(FROZEN),
            "scoring_protocol_sha256": sha256_file(HERE / "reports/phase1/scoring-protocol.json"),
            "scorer_sha256": sha256_file(HERE / "src/sheet2play_omr/phase3_scoring.py"),
            "scoring_summary_sha256": sha256_file(HERE / "phase3_score.py"),
            "candidates": candidate_identities(freeze, policy, runner),
            "resource_policy": policy,
            "stage2_only_no_candidate_inference": True}


def verify_manifest(path: Path) -> dict[str, Any]:
    saved = read_json(path)
    if saved.get("schema_version") == 1:
        expected = build_manifest(historical=True)
    elif saved.get("schema_version") == 2:
        raise ValueError("Historical HOMR 455 manifest uses incompatible source; read-only evidence")
    elif saved.get("schema_version") == 3:
        from screening_homr_extension import build_extended_manifest
        expected = build_extended_manifest()
    elif saved.get("schema_version") == 4:
        if saved.get("extension_scope") == "verified_homr_only; unchanged_frozen_sample_and_scoring":
            from screening_prepare_homr_stage4 import build_manifest as build_homr_manifest
            expected = build_homr_manifest()
        elif saved.get("extension_scope") == "verified_epoch14_only; unchanged_frozen_sample_and_scoring":
            from screening_finetune_extension import build_extended_manifest
            expected = build_extended_manifest()
        else:
            expected = build_manifest()
    else:
        raise ValueError("Unsupported screening manifest version")
    if saved != expected:
        raise ValueError("Screening manifest, scorer, input, reference, or runtime identity changed")
    if path.name != f"manifest-v{saved['schema_version']}-{digest(saved)[:12]}.json":
        raise ValueError("Screening manifest filename does not match its content")
    return saved


def require_current_policy(manifest: dict[str, Any]) -> None:
    if manifest.get("schema_version") != 4 or manifest.get("resource_policy") != POLICY:
        raise ValueError("Saved screening manifest uses the historical 75% RAM policy; prepare a v4 manifest")


def output_root(manifest_path: Path) -> Path:
    return REPORTS / read_json(manifest_path)["sample_sha256"][:12]


def completed_path(root: Path, candidate: str, item_id: str, config_sha256: str) -> Path:
    return (root / "completed" / candidate / config_sha256[:12] /
            hashlib.sha256(item_id.encode()).hexdigest()[:20])


def scored_path(root: Path, candidate: str, item_id: str,
                config_sha256: str, scorer_sha256: str) -> Path:
    return (root / "scored" / candidate / config_sha256[:12] / scorer_sha256[:12] /
            hashlib.sha256(item_id.encode()).hexdigest()[:20])


def result_identity(manifest: dict[str, Any], candidate: str, item: dict[str, Any]) -> dict[str, Any]:
    return {"schema_version": 1, "sample_sha256": manifest["sample_sha256"], "candidate": candidate,
            "configuration_sha256": manifest["candidates"][candidate]["identity_sha256"],
            "adapter_config_sha256": manifest["candidates"][candidate]["identity"]["adapter_config_sha256"],
            "item_id": item["id"], "image_sha256": item["image_sha256"],
            "reference_sha256": item["reference_sha256"]}


def verify_completed(directory: Path, identity: dict[str, Any]) -> dict[str, Any]:
    if not directory.is_dir():
        raise FileNotFoundError(f"No completed result: {directory}")
    if set(path.name for path in directory.iterdir()) != {"result.json", "identity.json", "provenance.json"}:
        raise ValueError(f"Incomplete completed-result directory: {directory}")
    if read_json(directory / "identity.json") != identity:
        raise ValueError(f"Completed identity changed: {directory}")
    result = read_json(directory / "result.json")
    provenance = read_json(directory / "provenance.json")
    if (provenance.get("identity") != identity or
            provenance.get("result_sha256") != sha256_file(directory / "result.json")):
        raise ValueError(f"Completed provenance changed: {directory}")
    validate_result(result, identity)
    return result


def validate_result(result: dict[str, Any], identity: dict[str, Any]) -> None:
    configuration = result.get("provenance", {}).get("adapter_config")
    if (result.get("schema_version") != 1 or result.get("item_id") != identity["item_id"]
            or result.get("adapter_config_sha256") != identity["adapter_config_sha256"]
            or result.get("provenance", {}).get("input_sha256") != identity["image_sha256"]
            or not isinstance(configuration, dict)
            or digest(configuration) != identity["adapter_config_sha256"]
            or result.get("candidate_id") != configuration.get("candidate_id")
            or result.get("adapter_id") != configuration.get("adapter_id")
            or result.get("status") not in {"succeeded", "failed"}):
        raise ValueError("Completed result identity or status changed")
    if result["status"] == "succeeded" and (result.get("exit_status") != 0 or result.get("error")):
        raise ValueError("Successful result has an error or nonzero exit")
    if result["status"] == "failed" and not (result.get("error") or {}).get("code"):
        raise ValueError("Completed failure has no typed error")
    if result["status"] == "succeeded" and not {"native", "musicxml", "canonical_events"} <= {
            a["role"] for a in result.get("artifacts", [])}:
        raise ValueError("Completed success lacks required artifacts")
    for artifact in result.get("artifacts", []):
        source = (WORKSPACE / artifact["path"]).resolve()
        if (not source.is_relative_to(WORKSPACE.resolve()) or not source.is_file()
                or source.stat().st_size != artifact["bytes"]
                or sha256_file(source) != artifact["sha256"]):
            raise ValueError(f"Completed artifact differs: {artifact['path']}")



def commit_completed(directory: Path, identity: dict[str, Any], result: dict[str, Any],
                     provenance: dict[str, Any]) -> None:
    validate_result(result, identity)
    directory.parent.mkdir(parents=True, exist_ok=True)
    temporary = directory.parent / f".{directory.name}.{uuid.uuid4().hex}.tmp"
    temporary.mkdir()
    try:
        write_new(temporary / "result.json", result)
        write_new(temporary / "identity.json", identity)
        provenance = {**provenance, "identity": identity,
                      "result_sha256": sha256_file(temporary / "result.json")}
        write_new(temporary / "provenance.json", provenance)
        if directory.exists():
            raise FileExistsError(f"Completed result already exists: {directory}")
        rename_directory_with_retry(temporary, directory)
        verify_completed(directory, identity)
    finally:
        if temporary.exists():
            for path in temporary.iterdir():
                path.unlink()
            temporary.rmdir()


def rename_directory_with_retry(source: Path, destination: Path) -> None:
    for attempt in range(5):
        try:
            source.rename(destination)
            return
        except PermissionError:
            if attempt == 4 or destination.exists():
                raise
            time.sleep(0.2 * (2 ** attempt))
