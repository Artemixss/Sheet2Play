"""Pinned epoch-14 candidate on the unchanged v4 composition screen."""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import subprocess
from typing import Any

from screening_common import HERE, POLICY, REPORTS, WORKSPACE, digest, read_json, write_new
from screening_finetune_compatibility import checked_files
from screening_homr_extension import runtime_inventory as shared_runtime_inventory
from sheet2play_omr.adapter_contract import sha256_file
from sheet2play_omr.phase2_adapters import ShippedHomrAdapter

ROOT = HERE / ".runtime/finetune-verified"
SOURCE = ROOT / "source"
CONTRACT = REPORTS / "finetune-export/contract-v1.json"
VALIDATOR = HERE / "screening_finetune_compatibility.py"
RUNTIME = HERE / ".runtime/homr-455/venv"
MODELS = HERE / ".runtime/finetune-ab/epoch14"
ENCODER = MODELS / "homr_epoch14_encoder_fp16.onnx"
DECODER = MODELS / "homr_epoch14_decoder_fp16.onnx"
BASE_MANIFEST = REPORTS / "manifest-v4-3af78028afa2.json"


def relative(path: Path) -> str:
    return path.resolve().relative_to(WORKSPACE.resolve()).as_posix()


def runtime_inventory() -> dict[str, Any]:
    inventory = shared_runtime_inventory()
    ocr_models = {relative(path): sha256_file(path)
                  for path in (RUNTIME / "Lib/site-packages/rapidocr/models").glob("*.onnx")}
    if not ocr_models:
        raise FileNotFoundError("Fine-tune page path requires pinned RapidOCR models")
    return {**inventory,
            "ocr_models": ocr_models,
            "encoder": {"path": relative(ENCODER), "sha256": sha256_file(ENCODER)},
            "decoder": {"path": relative(DECODER), "sha256": sha256_file(DECODER)}}


def compatibility_evidence(*, allow_create: bool = False) -> tuple[Path, str]:
    command = [str(RUNTIME / "Scripts/python.exe"), "-B", str(VALIDATOR),
               "--source", str(SOURCE), "--encoder", str(ENCODER),
               "--decoder", str(DECODER), "--contract", str(CONTRACT)]
    process = subprocess.run(command, cwd=WORKSPACE, capture_output=True,
                             text=True, timeout=90)
    if process.returncode:
        raise ValueError(f"Fine-tune compatibility failed: {process.stderr[-2000:]}")
    result = json.loads(process.stdout)
    path = REPORTS / "compatibility" / f"finetune-{digest(result)[:12]}.json"
    if path.is_file():
        if read_json(path) != result:
            raise ValueError("Fine-tune compatibility evidence changed")
    elif allow_create:
        write_new(path, result)
    else:
        raise FileNotFoundError(f"Fine-tune compatibility evidence is missing: {path}")
    return path, sha256_file(path)


def fine_tune_adapter(threads: int, runner_sha256: str,
                      inventory: dict[str, Any] | None = None,
                      evidence: tuple[Path, str] | None = None) -> ShippedHomrAdapter:
    inventory = inventory or runtime_inventory()
    evidence = evidence or compatibility_evidence()
    contract = read_json(CONTRACT)
    adapter = ShippedHomrAdapter(WORKSPACE)
    adapter.python = RUNTIME / "Scripts/python.exe"
    adapter.launcher = HERE / "screening_finetune_launcher.py"
    adapter.config = replace(
        adapter.config, candidate_id="fine_tuned_homr", adapter_id="epoch14_verified_onnx",
        source_revision=contract["source_revision"], checkpoint="checkpoint-135674 (epoch 14)",
        checkpoint_revision=contract["checkpoint_sha256"],
        settings={**adapter.config.settings, "precision": "fp16", "cpu_threads": threads,
                  "keep_tuplets_override": False,
                  "cpu_affinity_count": threads, "onnx_intra_op_threads": threads,
                  "onnx_inter_op_threads": 1, "priority": "below_normal",
                  "development_ram_admission_percent": POLICY["ram_admission_percent"],
                  "screening_runner_sha256": runner_sha256,
                  "screening_resource_policy_sha256": digest(POLICY),
                  "screening_launcher_sha256": sha256_file(adapter.launcher),
                  "compatibility_contract_sha256": sha256_file(CONTRACT),
                  "compatibility_validator_sha256": sha256_file(VALIDATOR),
                  "compatibility_report_sha256": evidence[1],
                  "encoder_sha256": inventory["encoder"]["sha256"],
                  "decoder_sha256": inventory["decoder"]["sha256"],
                  "segnet_sha256": inventory["segnet"]["sha256"],
                  "report_commit": contract["report_commit"]})
    return adapter


def candidate_identity(runner_sha256: str, threads: int) -> dict[str, Any]:
    contract = read_json(CONTRACT)
    checked_files(SOURCE, contract["source_files"])
    inventory = runtime_inventory()
    evidence = compatibility_evidence()
    adapter = fine_tune_adapter(threads, runner_sha256, inventory, evidence)
    files = {relative(SOURCE / name): sha for name, sha in contract["source_files"].items()}
    scripts = ("screening_finetune_extension.py", "screening_finetune_launcher.py",
               "screening_finetune_compatibility.py", "screening_homr_development_launcher.py",
               "screening_homr_compatibility.py", "screening_homr_extension.py",
               "homr_candidate_launcher.py", "screening_development.py", "screening_common.py",
               "src/sheet2play_omr/phase2_adapters.py", "src/sheet2play_omr/adapter_contract.py",
               "src/sheet2play_omr/phase2r_validation.py")
    files.update({relative(HERE / name): sha256_file(HERE / name) for name in scripts})
    files[relative(WORKSPACE / "Bridge/homr_gpu.py")] = sha256_file(WORKSPACE / "Bridge/homr_gpu.py")
    identity = {"adapter_config": adapter.config.to_json(), "adapter_config_sha256": adapter.config.sha256,
                "source_revision": contract["source_revision"], "source_files": files,
                "runtime": inventory, "resource_policy": POLICY,
                "worker_source_sha256": runner_sha256,
                "compatibility_report": {"path": relative(evidence[0]), "sha256": evidence[1]},
                "contract": {"path": relative(CONTRACT), "sha256": sha256_file(CONTRACT)},
                "normalizer_sha256": sha256_file(WORKSPACE / "Bridge/musicxml_normalizer.py")}
    return {"status": "requires_screening_pipeline_development_entry",
            "identity": identity, "identity_sha256": digest(identity)}


def candidate_environment(identity: dict[str, Any]) -> dict[str, str]:
    result = {"PYTHONPATH": str(SOURCE.resolve()), "S2P_FINETUNE_SOURCE": str(SOURCE.resolve()),
              "SHEET2PLAY_HOMR_KEEP_TUPLETS": "0",
              "S2P_FINETUNE_CONTRACT": str(CONTRACT.resolve()),
              "S2P_FINETUNE_CONTRACT_SHA256": identity["contract"]["sha256"],
              "S2P_FINETUNE_COMPATIBILITY_REPORT": str(
                  (WORKSPACE / identity["compatibility_report"]["path"]).resolve()),
              "S2P_FINETUNE_COMPATIBILITY_REPORT_SHA256": identity["compatibility_report"]["sha256"]}
    for name in ("encoder", "decoder", "segnet"):
        asset = identity["runtime"][name]
        prefix = "S2P_FINETUNE_SEGNET" if name == "segnet" else f"SHEET2PLAY_CANDIDATE_{name.upper()}"
        result[prefix] = str((WORKSPACE / asset["path"]).resolve())
        result[prefix + "_SHA256"] = asset["sha256"]
    result["S2P_FINETUNE_AUXILIARY_MODELS"] = json.dumps({
        str((WORKSPACE / path).resolve()): sha for path, sha in identity["runtime"]["ocr_models"].items()},
        sort_keys=True)
    return result


def build_extended_manifest() -> dict[str, Any]:
    from screening_common import build_manifest, threads_limit
    base, current = read_json(BASE_MANIFEST), build_manifest()
    for key in ("sample_sha256", "items", "selected_groups", "scoring_protocol_sha256", "scorer_sha256"):
        if current[key] != base[key]:
            raise ValueError(f"Fine-tune extension changed frozen {key}")
    runner = sha256_file(HERE / "screening_run.py")
    return {**current, "name": "smb-pianoform-screening-v4-finetune-verified",
            "candidates": {**current["candidates"], "fine_tuned_homr": candidate_identity(runner, threads_limit())},
            "supersedes_manifest_sha256": sha256_file(BASE_MANIFEST),
            "extension_scope": "verified_epoch14_only; unchanged_frozen_sample_and_scoring"}
