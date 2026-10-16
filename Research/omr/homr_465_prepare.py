"""Prepare isolated native-page research profiles and freeze the comparison."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from homr_465_download import REVISION
from screening_homr_compatibility import digest, sha256_file
from homr_465_common import write_new

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[1]
EVIDENCE = HERE / "reports/homr-timing-465/phase2"
PHASE1 = EVIDENCE.parent / "phase1"


def artifact(path: Path) -> dict:
    return {"path": str(path.resolve()), "sha256": sha256_file(path)}


def prepare() -> None:
    contract_path = HERE / "homr_465_contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    acquisition = json.loads((EVIDENCE / "acquisition.json").read_text(encoding="utf-8"))
    baseline = json.loads((PHASE1 / "runtime-inventory.json").read_text(encoding="utf-8"))
    source = HERE / ".runtime/homr-465-upstream/source"
    baseline_source = WORKSPACE / "Bridge/.venv-homr-gpu/Lib/site-packages/homr"
    common = {"schema_version": 1, "phase": 2, "python": artifact(Path(contract["python_executable"])),
              "package_versions": contract["package_versions"], "title_detection": False,
              "metadata_qualification": "Native no-title setting excludes optional OCR; musical pipeline unchanged; no general title-equivalence claim",
              "processing": {"enable_debug": True, "enable_cache": False, "write_staff_positions": True,
                             "read_staff_positions": False, "selected_staff": -1, "transformer_use_gpu": True,
                             "segnet_use_gpu": True, "coreml_encoder": False, "title_detection": False},
              "threads": 8, "inter_op_threads": 1, "provider": "CUDAExecutionProvider",
              "segnet": baseline["active_weights"][2], "xml_args": {"large_page": False, "metronome": None, "tempo": None},
              "safeguards": {"system_stop_percent": 85, "worker_bytes": 4 * 1024**3, "reserve_bytes": 4 * 1024**3,
                             "active_processes": 16, "gpu_stop_percent": 90},
              "capture_script": artifact(HERE / "homr_465_capture.py")}
    sources = [{"path": str((source / name).resolve()), "sha256": value} for name, value in contract["source_files"].items()]
    candidate = {**common, "candidate": "homr-465-upstream", "source_revision": REVISION,
                 "source": str(source.resolve()), "source_files": sources, "contract": artifact(contract_path),
                 "models": {name: {"path": value["absolute_path"], "sha256": value["sha256"]} for name, value in acquisition["models"].items()}}
    control = {**common, "candidate": "shipped-426-phase2-control", "baseline_runtime_identity": baseline["identity_sha256"],
               "source": str(baseline_source.parent.resolve()), "source_files": baseline["homr_source"],
               "models": {name: baseline["active_weights"][i] for i, name in enumerate(("encoder", "decoder"))}}
    for name, config in (("candidate", candidate), ("control", control)):
        config["identity_sha256"] = digest(config)
        write_new(EVIDENCE / (name + "-configuration.json"), config)
    rows = json.loads((PHASE1 / "reference-eligibility.json").read_text(encoding="utf-8"))
    write_new(EVIDENCE / "development-inputs.json", rows)
    write_new(EVIDENCE / "protected-artifacts.json", baseline["homr_source"] + baseline["active_weights"] + baseline["installed_bridge"] + [artifact(HERE / "homr_455_contract.json")])
    print(json.dumps({"development_items": len(rows), "candidate_identity": candidate["identity_sha256"], "control_identity": control["identity_sha256"]}))


def freeze() -> None:
    analysis = json.loads((EVIDENCE / "development-analysis.json").read_text(encoding="utf-8"))
    if analysis["not_attempted"] or analysis["resource_stopped"]:
        raise ValueError("Development resource stop or missing items blocks comparison")
    sample_path = HERE / "reports/screening/v1/manifest-v5-607ff64134da.json"
    sample = json.loads(sample_path.read_text(encoding="utf-8"))
    if len(sample["items"]) != 59 or len(sample["selected_groups"]) != 18:
        raise ValueError("Expected the unchanged 59-page/18-composition screen")
    rows = []
    for item in sample["items"]:
        image = WORKSPACE / item["image_path"]
        if sha256_file(image) != item["image_sha256"]:
            raise ValueError("Comparison image drift")
        reference = WORKSPACE / item["reference_path"]
        if sha256_file(reference) != item["reference_sha256"]:
            raise ValueError("Comparison reference drift")
        rows.append({"item_id": digest(item["id"])[:20], "original_item_id": item["id"], "composition_group": item["composition_group"],
                     "image": artifact(image), "reference": artifact(reference), "numeric_accuracy_eligible": True})
    write_new(EVIDENCE / "comparison-inputs.json", rows)
    config = {"schema_version": 1, "phase": 2, "frozen_utc": datetime.now(timezone.utc).isoformat(),
              "sample": artifact(sample_path), "sample_sha256": sample["sample_sha256"],
              "development_analysis": artifact(EVIDENCE / "development-analysis.json"),
              "candidate_configuration": artifact(EVIDENCE / "candidate-configuration.json"),
              "control_configuration": artifact(EVIDENCE / "control-configuration.json"),
              "primary_metric": "composition-macro exact rational pitch/onset/duration F1; failures zero",
              "claims": ["homr-465-upstream has greater primary F1 than shipped HOMR on the observed 59-page screen"],
              "statistics": {"bootstrap_seed": 20261007, "bootstrap_repetitions": 10000,
                             "test": "exact paired composition label swaps, one-sided", "multiplicity": "Holm; one preregistered claim"},
              "no_tuning_from_comparison": True, "fresh_control_runtime": True,
              "normalizer": artifact(WORKSPACE / "dist/Bridge/musicxml_normalizer.py"),
              "scoring_code": artifact(HERE / "src/sheet2play_omr/zeus_trace.py"),
              "metrics_code": artifact(HERE / "src/sheet2play_omr/metrics.py"),
              "statistics_code": artifact(HERE / "screening_homr_statistics.py"),
              "analysis_code": artifact(HERE / "homr_465_analyze.py"),
              "additional_scoring_sources": [artifact(path) for path in (
                  HERE / "homr_465_common.py", HERE / "homr_baseline_analyze.py",
                  HERE / "src/sheet2play_omr/corrected_scoring.py",
                  HERE / "src/sheet2play_omr/timing.py", HERE / "screening_report.py",
                  HERE / "homr_465_prepare.py", HERE / "homr_465_capture.py", HERE / "homr_465_compatibility.py",
                  HERE / "homr_baseline_infer.py", HERE / "homr_baseline_resources.py",
                  HERE / "homr_candidate_launcher.py", HERE / "zeus_attribution_prepare.py",
                  HERE / "run-homr-465-phase2.ps1", EVIDENCE / "gate/sitecustomize.py",
                  WORKSPACE / "dist/Bridge/homr_gpu.py", EVIDENCE / "hardware.json")],
              "comparison_inputs": artifact(EVIDENCE / "comparison-inputs.json")}
    config["identity_sha256"] = digest(config)
    write_new(EVIDENCE / "comparison-freeze.json", config)
    print(json.dumps({"items": len(rows), "groups": 18, "comparison_identity": config["identity_sha256"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("development", "freeze"))
    args = parser.parse_args()
    prepare() if args.mode == "development" else freeze()
