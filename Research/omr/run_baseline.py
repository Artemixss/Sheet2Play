from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return payload


def _require_fixture_files(fixture_dir: Path) -> dict[str, Any]:
    manifest = _read_json(fixture_dir / "fixture-manifest.json")
    for entry in manifest["files"].values():
        path = fixture_dir / entry["name"]
        if not path.is_file():
            raise FileNotFoundError(f"Fixture file is missing: {path}")
        if path.stat().st_size != int(entry["bytes"]) or _sha256(path) != entry["sha256"]:
            raise ValueError(f"Fixture hash mismatch: {path}")
    return manifest


def run(project_root: Path, real_pdf: Path) -> dict[str, Any]:
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"

    from sheet2play_omr.assets import RuntimePaths, verify_runtime
    from sheet2play_omr.benchmark import run_benchmark
    from sheet2play_omr.errors import ResearchError
    from sheet2play_omr.inference import check_determinism, infer_document

    started = time.perf_counter()
    fixture_dir = project_root / "tests" / "fixtures" / "transcoda-baseline"
    artifacts = project_root / "artifacts" / "baseline"
    reports = project_root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    artifacts.mkdir(parents=True, exist_ok=True)
    report_path = reports / "baseline-smoke.json"
    report: dict[str, Any] = {
        "schema_version": 1,
        "passed": False,
        "offline": True,
        "fixture": {},
        "runtime": {},
        "benchmark": {},
        "determinism": {},
        "real_pdf": {},
        "acceptance": {},
    }
    try:
        fixture_manifest = _require_fixture_files(fixture_dir)
        runtime = verify_runtime(RuntimePaths.discover(project_root))
        report["fixture"] = fixture_manifest
        report["runtime"] = runtime
        benchmark_report = run_benchmark(
            fixture_dir / "benchmark.jsonl",
            reports / "fixture-benchmark.json",
            modes=("beam", "grammar"),
        )
        report["benchmark"] = benchmark_report
        selected_mode = benchmark_report["selected_mode"]
        if selected_mode is None:
            raise ResearchError(
                "BASELINE_FAILED",
                "fixture_benchmark",
                "Neither decoder produced structurally valid fixture output",
            )
        selected_summary = benchmark_report["modes"][selected_mode]["summary"]
        required_metrics = ("pitch_f1", "onset_f1", "onset_duration_f1", "staff_accuracy", "voice_accuracy")
        if any(not isinstance(selected_summary.get(name), (int, float)) for name in required_metrics):
            raise ResearchError("BASELINE_FAILED", "fixture_benchmark", "Selected decoder metrics are incomplete")
        report["selected_mode"] = selected_mode
        report["selected_metrics"] = {name: selected_summary[name] for name in required_metrics}
        report["acceptance"].update(
            fixture_structurally_valid=selected_summary["structural_validity"] == 1.0,
            fixture_structure_exact=selected_summary["structural_assertions"] == 1.0,
            f1_metrics_calculated=True,
        )

        determinism = check_determinism(fixture_dir / "baseline-piano.png", selected_mode, runs=3)
        report["determinism"] = determinism
        report["acceptance"]["three_run_determinism"] = bool(determinism["deterministic"])
        if not determinism["deterministic"]:
            raise ResearchError("BASELINE_FAILED", "determinism", "Three identical fixture runs produced different outputs")

        if not real_pdf.resolve().is_file():
            raise ResearchError("INPUT_INVALID", "real_pdf", f"Real PDF is missing: {real_pdf.resolve()}")
        dexter = infer_document(real_pdf.resolve(), artifacts / "dexter", selected_mode)
        report["real_pdf"] = {
            "input": str(real_pdf.resolve()),
            "source_sha256": _sha256(real_pdf.resolve()),
            "summary": dexter,
        }
        omr_result_path = Path(dexter["outputs"]["omr_result"])
        omr_result = _read_json(omr_result_path)
        if omr_result.get("schema_version") != 2 or not omr_result.get("notes"):
            raise ResearchError("BASELINE_FAILED", "real_pdf", "Dexter export is empty or has the wrong schema")

        import torch

        device = str(torch.cuda.get_device_name(0))
        if "RTX 4050" not in device.upper():
            raise ResearchError("CUDA_DEVICE_MISMATCH", "acceptance", f"Expected RTX 4050, found {device}")
        if selected_summary["structural_assertions"] != 1.0:
            raise ResearchError(
                "BASELINE_FAILED",
                "acceptance",
                "The selected decoder did not reproduce the fixture's structural events exactly",
            )
        report.update(
            passed=True,
            runtime={**runtime, "cuda_device": device, "torch": torch.__version__},
            acceptance={
                "cuda_rtx_4050": True,
                "fixture_structurally_valid": selected_summary["structural_validity"] == 1.0,
                "fixture_structure_exact": selected_summary["structural_assertions"] == 1.0,
                "f1_metrics_calculated": True,
                "three_run_determinism": True,
                "real_pdf_nonempty": True,
                "schema_version_2": True,
                "musicxml_midi_round_trip": True,
                "latency_recorded_not_gated": True,
            },
        )
    except Exception as error:
        report["error"] = {
            "type": type(error).__name__,
            "code": getattr(error, "code", "BASELINE_INTERNAL_ERROR"),
            "stage": getattr(error, "stage", "baseline"),
            "message": str(error),
            "page": getattr(error, "page", None),
        }
    finally:
        report["total_seconds"] = time.perf_counter() - started
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")

    if not report["passed"]:
        print(json.dumps(report["error"], sort_keys=True), file=sys.stderr)
        return report
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
    return report


def main() -> int:
    default_root = Path(__file__).resolve().parent
    default_pdf = (
        default_root.parents[1]
        / "Visualization_engine"
        / "songs"
        / "pdf"
        / "Daniel LITCH - Dexter Main theme.pdf"
    )
    parser = argparse.ArgumentParser(description="Run the Sheet2Play Transcoda Phase 3 baseline")
    parser.add_argument("--project-root", type=Path, default=default_root)
    parser.add_argument("--real-pdf", type=Path, default=default_pdf)
    args = parser.parse_args()
    report = run(args.project_root.resolve(), args.real_pdf.resolve())
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
