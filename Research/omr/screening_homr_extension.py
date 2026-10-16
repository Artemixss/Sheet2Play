"""Versioned HOMR 455 configuration on the frozen 59-page screening sample."""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import subprocess
from typing import Any

from screening_common import HERE, POLICY, REPORTS, WORKSPACE, digest, read_json, write_new
from sheet2play_omr.adapter_contract import sha256_file
from sheet2play_omr.phase2_adapters import ShippedHomrAdapter


BASE_MANIFEST = HERE / "reports/screening/v1/manifest-v1-9126bc5feefc.json"
SOURCE = HERE / ".runtime/homr-455-compatible/source"
RUNTIME = HERE / ".runtime/homr-455/venv"
MODELS = HERE / ".runtime/homr-455/models"
REVISION = "a4865663e7278f908d6d1b1a57d549f9ca3d1067"
CONTRACT = HERE / "homr_455_contract.json"
VALIDATOR = HERE / "screening_homr_compatibility.py"
MODEL_ID = "455-7bf1389908b44047d4cba9d5d06e868ceaf946ef"
ENCODER = MODELS / f"encoder_pytorch_model_{MODEL_ID}_fp16.onnx"
DECODER = MODELS / f"decoder_pytorch_model_{MODEL_ID}_fp16.onnx"
SEGNET = (RUNTIME / "Lib/site-packages/homr/segmentation" /
          "segnet_308-3296ccd40960f90ca6ab9c035cca945675d30a0f_fp16.onnx")
TOKENIZER_NAMES = ("lift", "note", "pitch", "rhythm")
DEVELOPMENT_RAM_ADMISSION_PERCENT = 90


def relative(path: Path) -> str:
    return path.resolve().relative_to(WORKSPACE.resolve()).as_posix()


def checked_source_files() -> dict[str, str]:
    from phase4_validation import checked_homr_source
    files = checked_homr_source(SOURCE, REVISION)
    return {relative(SOURCE / name): digest for name, digest in files.items()}


def runtime_inventory() -> dict[str, Any]:
    python = RUNTIME / "Scripts/python.exe"
    native = RUNTIME / "Lib/site-packages/onnxruntime/capi/onnxruntime_pybind11_state.pyd"
    packages = ("numpy", "opencv-python-headless", "Pillow", "rapidocr",
                "onnxruntime-gpu", "pypdfium2")
    program = ("import importlib.metadata as m,json;"
               f"print(json.dumps({{name:m.version(name) for name in {packages!r}}},sort_keys=True))")
    versions = json.loads(subprocess.run([str(python), "-c", program], capture_output=True,
                                         text=True, check=True, timeout=20).stdout)
    return {"python": {"path": relative(python), "sha256": sha256_file(python)},
            "pyvenv_sha256": sha256_file(RUNTIME / "pyvenv.cfg"),
            "onnxruntime_native_sha256": sha256_file(native),
            "package_versions": versions,
            "segnet": {"path": relative(SEGNET), "sha256": sha256_file(SEGNET)},
            "encoder": {"path": relative(ENCODER), "sha256": sha256_file(ENCODER)},
            "decoder": {"path": relative(DECODER), "sha256": sha256_file(DECODER)}}


def compatibility_evidence(*, allow_create: bool = False) -> tuple[Path, str]:
    command = [str(RUNTIME / "Scripts/python.exe"), "-B", str(VALIDATOR),
               "--source", str(SOURCE), "--encoder", str(ENCODER),
               "--decoder", str(DECODER), "--contract", str(CONTRACT)]
    completed = subprocess.run(command, cwd=WORKSPACE, capture_output=True,
                               text=True, check=True, timeout=90)
    report = json.loads(completed.stdout)
    if (report.get("source_revision") != REVISION or
            report.get("contract_sha256") != sha256_file(CONTRACT) or
            report.get("validator_sha256") != sha256_file(VALIDATOR)):
        raise ValueError("HOMR 455 compatibility report identity differs")
    path = REPORTS / "compatibility" / f"homr455-{digest(report)[:12]}.json"
    if path.exists():
        if read_json(path) != report:
            raise ValueError("HOMR 455 compatibility report changed")
    elif allow_create:
        write_new(path, report)
    else:
        raise FileNotFoundError(f"Pinned HOMR 455 compatibility report is missing: {path}")
    return path, sha256_file(path)


def homr_455_adapter(threads: int, runner_sha256: str,
                     inventory: dict[str, Any] | None = None,
                     evidence: tuple[Path, str] | None = None) -> ShippedHomrAdapter:
    inventory = inventory or runtime_inventory()
    evidence = evidence or compatibility_evidence()
    adapter = ShippedHomrAdapter(WORKSPACE)
    adapter.python = RUNTIME / "Scripts/python.exe"
    adapter.launcher = HERE / "screening_homr_455_launcher.py"
    adapter.config = replace(
        adapter.config,
        candidate_id="homr_455", adapter_id="homr_455_explicit_onnx_pair",
        source_revision=REVISION, checkpoint=f"encoder+decoder {MODEL_ID}",
        checkpoint_revision="onnx_checkpoints:fp16:7bf1389908b44047d4cba9d5d06e868ceaf946ef",
        settings={**adapter.config.settings,
                  "cpu_threads": threads, "cpu_affinity_count": threads,
                  "onnx_intra_op_threads": threads, "onnx_inter_op_threads": 1,
                  "priority": "below_normal", "precision": "fp16",
                  "keep_tuplets_override": False,
                  "development_ram_admission_percent": DEVELOPMENT_RAM_ADMISSION_PERCENT,
                  "screening_runner_sha256": runner_sha256,
                  "screening_resource_policy_sha256": digest(POLICY),
                  "screening_launcher_sha256": sha256_file(adapter.launcher),
                  "encoder_sha256": inventory["encoder"]["sha256"],
                  "decoder_sha256": inventory["decoder"]["sha256"],
                  "segnet_sha256": inventory["segnet"]["sha256"],
                  "compatibility_contract_sha256": sha256_file(CONTRACT),
                  "compatibility_validator_sha256": sha256_file(VALIDATOR),
                  "compatibility_report_sha256": evidence[1]})
    return adapter


def candidate_identity(runner_sha256: str, threads: int) -> dict[str, Any]:
    runtime = runtime_inventory()
    evidence = compatibility_evidence()
    adapter = homr_455_adapter(threads, runner_sha256, runtime, evidence)
    source_files = checked_source_files()
    extra_files = [HERE / "screening_homr_455_launcher.py",
                   HERE / "screening_homr_development_launcher.py",
                   HERE / "homr_candidate_launcher.py",
                   HERE / "screening_homr_extension.py",
                   CONTRACT,
                   VALIDATOR,
                   HERE / "phase4_validation.py",
                   HERE / "screening_development.py",
                   HERE / "screening_common.py",
                   HERE / "src/sheet2play_omr/phase2_adapters.py",
                   HERE / "src/sheet2play_omr/adapter_contract.py",
                   HERE / "src/sheet2play_omr/phase2r_validation.py",
                   WORKSPACE / "Bridge/homr_gpu.py",
                   WORKSPACE / "Bridge/musicxml_normalizer.py"]
    source_files.update({relative(path): sha256_file(path) for path in extra_files})
    tokenizers = {name: sha256_file(SOURCE / "homr/transformer" / f"tokenizer_{name}.json")
                  for name in TOKENIZER_NAMES}
    identity = {"adapter_config": adapter.config.to_json(),
                "adapter_config_sha256": adapter.config.sha256,
                "source_repository": "https://github.com/liebharc/homr",
                "source_revision": REVISION,
                "source_files": source_files,
                "tokenizers": tokenizers,
                "compatibility_report": {"path": relative(evidence[0]), "sha256": evidence[1]},
                "runtime": runtime,
                "resource_policy": POLICY,
                "worker_source_sha256": runner_sha256,
                "normalizer_sha256": sha256_file(WORKSPACE / "Bridge/musicxml_normalizer.py")}
    return {"status": "requires_screening_pipeline_development_entry",
            "identity": identity, "identity_sha256": digest(identity)}


def candidate_environment(identity: dict[str, Any]) -> dict[str, str]:
    runtime = identity["runtime"]
    return {"PYTHONPATH": str(SOURCE.resolve()),
            "SHEET2PLAY_HOMR_KEEP_TUPLETS": "0",
            "S2P_HOMR_455_SOURCE": str(SOURCE.resolve()),
            "S2P_HOMR_455_SOURCE_REVISION": identity["source_revision"],
            "S2P_HOMR_455_TOKENIZER_SHA256": json.dumps(identity["tokenizers"], sort_keys=True),
            "S2P_HOMR_455_CONTRACT": str(CONTRACT.resolve()),
            "S2P_HOMR_455_CONTRACT_SHA256": sha256_file(CONTRACT),
            "S2P_HOMR_455_COMPATIBILITY_REPORT": str((WORKSPACE / identity["compatibility_report"]["path"]).resolve()),
            "S2P_HOMR_455_COMPATIBILITY_REPORT_SHA256": identity["compatibility_report"]["sha256"],
            "SHEET2PLAY_CANDIDATE_ENCODER": str((WORKSPACE / runtime["encoder"]["path"]).resolve()),
            "SHEET2PLAY_CANDIDATE_ENCODER_SHA256": runtime["encoder"]["sha256"],
            "SHEET2PLAY_CANDIDATE_DECODER": str((WORKSPACE / runtime["decoder"]["path"]).resolve()),
            "SHEET2PLAY_CANDIDATE_DECODER_SHA256": runtime["decoder"]["sha256"],
            "S2P_HOMR_455_SEGNET": str((WORKSPACE / runtime["segnet"]["path"]).resolve()),
            "S2P_HOMR_455_SEGNET_SHA256": runtime["segnet"]["sha256"]}


def build_extended_manifest() -> dict[str, Any]:
    from screening_common import build_manifest, threads_limit
    base = read_json(BASE_MANIFEST)
    if base != build_manifest(historical=True):
        raise ValueError("Frozen Stage-2 manifest changed before HOMR extension")
    runner = sha256_file(HERE / "screening_run.py")
    candidates = {**base["candidates"], "homr_455": candidate_identity(runner, threads_limit())}
    return {**base, "schema_version": 3, "name": "smb-pianoform-screening-v3-homr455-compatible",
            "candidates": candidates,
            "supersedes_manifest_sha256": sha256_file(BASE_MANIFEST),
            "stage2_only_no_candidate_inference": False,
            "extension_scope": "corrected_homr_455_candidate_identity_only; same frozen sample and scorer",
            "retired_455_configuration_sha256":
            "cb45056ebb223f4bb82fc7b4eecd4f4fd28d5cd0a00b439bc00e8bde6537a99f"}
