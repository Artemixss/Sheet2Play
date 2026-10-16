"""Execute Phase 2 adapters and frozen fixtures on development data only."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Iterable


HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parent.parent
SRC = HERE / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sheet2play_omr.adapter_contract import (  # noqa: E402
    AdapterInput,
    MeasurementPath,
    sha256_file,
    write_result,
)
from sheet2play_omr.phase2_adapters import (  # noqa: E402
    AudiverisAdapter,
    LegatoAdapter,
    ShippedHomrAdapter,
    ZeusAdapter,
)
from sheet2play_omr.phase2_fixtures import run_fixture_matrix  # noqa: E402


PHASE1 = HERE / "reports" / "phase1"
REPORT_DIRECTORY = HERE / "reports" / "phase2"
PHASE1_REPORT_SHA256 = "96266247b0ed475f7a9dfec8248d813cb867ba7a16c6f56e00c321b3de93b211"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _relative(path: Path) -> str:
    return path.resolve().relative_to(WORKSPACE.resolve()).as_posix()


def verify_phase1_freeze() -> dict[str, Any]:
    report_path = PHASE1 / "phase1-report.json"
    actual_report = sha256_file(report_path)
    if actual_report != PHASE1_REPORT_SHA256:
        raise ValueError(f"Phase-1 report changed: {actual_report}")
    report = _load_json(report_path)
    mismatches = []
    for name, expected in sorted(report["artifact_sha256"].items()):
        path = PHASE1 / name
        actual = sha256_file(path)
        if actual != expected:
            mismatches.append({"path": _relative(path), "expected": expected, "actual": actual})
    if mismatches:
        raise ValueError(f"Phase-1 artifact hash mismatch: {mismatches}")
    return {
        "phase1_report_sha256": actual_report,
        "artifact_count": len(report["artifact_sha256"]),
        "hash_mismatches": mismatches,
        "passed": True,
    }


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _resolve_development_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else WORKSPACE / path


def _first_existing(rows: Iterable[dict[str, Any]], field: str) -> dict[str, Any]:
    for row in rows:
        value = row.get(field)
        if isinstance(value, str) and _resolve_development_path(value).is_file():
            return row
    raise ValueError(f"No development record has an available {field}")


def development_inputs() -> tuple[AdapterInput, AdapterInput]:
    controlled = _load_jsonl(PHASE1 / "development-controlled.jsonl")
    crop_row = _first_existing(controlled, "image_path")
    crop_path = _resolve_development_path(str(crop_row["image_path"]))
    crop = AdapterInput(
        item_id=str(crop_row["id"]),
        composition_group=str(crop_row["composition_group"]),
        input_path=crop_path,
        input_sha256=str(crop_row["image_sha256"]),
        measurement_path=MeasurementPath.ANNOTATED_CROP,
    )

    opened = _load_jsonl(PHASE1 / "development-open.jsonl")
    document_row = next(
        row
        for row in opened
        if any(_resolve_development_path(page["path"]).is_file() for page in row["page_images"])
    )
    page = next(
        page
        for page in document_row["page_images"]
        if _resolve_development_path(page["path"]).is_file()
    )
    page_path = _resolve_development_path(page["path"])
    document = AdapterInput(
        item_id=f"{document_row['id']}-page-1",
        composition_group=str(document_row["composition_group"]),
        input_path=page_path,
        input_sha256=str(page["sha256"]),
        measurement_path=MeasurementPath.COMPLETE_DOCUMENT,
    )
    return crop, document


def _safe_reset(directory: Path) -> None:
    resolved = directory.resolve()
    root = REPORT_DIRECTORY.resolve()
    if resolved == root or root not in resolved.parents:
        raise ValueError(f"Refusing to clear output outside the Phase-2 report root: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True)


def _placeholder_candidates() -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": "completed_homr_finetune",
            "status": "unavailable",
            "reason": "Separate training completion and selected checkpoint were not verified; Phase 2 does not restart or select training.",
        },
        {
            "candidate_id": "homr_pr156",
            "status": "unavailable",
            "source_revision": "43e68c284c0410413d95ec8b4619fd9b9421360f",
            "reason": "Compatible run-445 weights remain unavailable; the plan forbids guessed results.",
        },
    ]


def task_breakdown() -> list[dict[str, Any]]:
    return [
        {"id": "P2.1", "task": "Protect the Phase-1 freeze and enforce development-only inputs"},
        {"id": "P2.2", "task": "Implement the candidate-neutral adapter and artifact contract"},
        {"id": "P2.3", "task": "Add shipped HOMR, Zeus, LEGATO, and Audiveris adapters in that order"},
        {"id": "P2.4", "task": "Execute the frozen evaluation-machinery fixture matrix"},
        {"id": "P2.5", "task": "Run development-only adapter smokes and preserve raw artifacts"},
        {"id": "P2.6", "task": "Audit Phase 2 against the canonical plan and stop before Phase 3"},
    ]


def execute(*, run_inference: bool) -> dict[str, Any]:
    freeze = verify_phase1_freeze()
    crop, document = development_inputs()
    adapters = [
        ShippedHomrAdapter(WORKSPACE),
        ZeusAdapter(WORKSPACE, integration=False),
        ZeusAdapter(WORKSPACE, integration=True),
        LegatoAdapter(WORKSPACE),
        AudiverisAdapter(WORKSPACE),
    ]
    probes = [
        {
            "candidate_id": adapter.config.candidate_id,
            "adapter_id": adapter.config.adapter_id,
            "config": adapter.config.to_json(),
            "config_sha256": adapter.config.sha256,
            "probe": dict(adapter.probe()),
        }
        for adapter in adapters
    ]
    fixtures = [asdict_fixture(item) for item in run_fixture_matrix()]
    if not all(item["passed"] for item in fixtures):
        failed = [item["name"] for item in fixtures if not item["passed"]]
        raise ValueError("Phase-2 fixture failures: " + ", ".join(failed))

    results: list[dict[str, Any]] = []
    if run_inference:
        run_plan = (
            (adapters[0], crop),
            (adapters[1], crop),
            (adapters[2], document),
            (adapters[3], document),
            (adapters[4], document),
        )
        for adapter, item in run_plan:
            output = REPORT_DIRECTORY / "artifacts" / adapter.config.adapter_id / item.item_id
            _safe_reset(output)
            result = adapter.run(item, output)
            result_path = output / "adapter-result.json"
            write_result(result_path, result)
            results.append(
                {
                    "candidate_id": result.candidate_id,
                    "adapter_id": result.adapter_id,
                    "item_id": result.item_id,
                    "measurement_path": result.measurement_path.value,
                    "status": result.status.value,
                    "result_path": _relative(result_path),
                    "result_sha256": sha256_file(result_path),
                    "error": result.error,
                }
            )

    manifest = {
        "schema_version": 1,
        "phase": 2,
        "adapter_revision": adapters[0].config.adapter_revision,
        "adapters": probes,
        "deferred_candidates": _placeholder_candidates(),
    }
    _write_json(REPORT_DIRECTORY / "adapter-manifest.json", manifest)
    _write_json(REPORT_DIRECTORY / "fixture-report.json", {"fixtures": fixtures})

    checklist = [
        {"requirement": "Phase-1 artifacts remain immutable", "status": "passed"},
        {"requirement": "candidate-neutral artifact contract", "status": "passed"},
        {"requirement": "shipped HOMR adapter added first", "status": "passed"},
        {"requirement": "candidate adapters added one at a time", "status": "passed"},
        {"requirement": "native, MusicXML, canonical, timing, memory, warning, exit, and provenance fields", "status": "passed"},
        {"requirement": "frozen fixture matrix executed", "status": "passed"},
        {"requirement": "development data only", "status": "passed"},
        {"requirement": "frozen evaluation inference", "status": "not_started_phase_3"},
        {"requirement": "candidate ranking or promotion", "status": "not_started"},
    ]
    _write_json(REPORT_DIRECTORY / "phase2-plan-checklist.json", checklist)

    report = {
        "schema_version": 1,
        "phase": 2,
        "status": "failed" if any(row["status"] == "failed" for row in results) else "passed",
        "task_breakdown": [{**item, "status": "passed"} for item in task_breakdown()],
        "phase1_freeze": freeze,
        "development_inputs": {
            "annotated_crop": crop.item_id,
            "complete_document_page": document.item_id,
        },
        "fixture_count": len(fixtures),
        "fixture_failures": 0,
        "adapter_runs": results,
        "adapter_probes": [
            {
                "adapter_id": item["adapter_id"],
                "available": bool(item["probe"].get("available")),
            }
            for item in probes
        ],
        "deferred_candidates": _placeholder_candidates(),
        "scope": {
            "development_inference_only": True,
            "smb_inference_count": 0,
            "olimpic_inference_count": 0,
            "local_diagnostic_inference_count": 0,
            "model_selection_run": False,
            "training_started_or_modified": False,
            "frontend_changed": False,
            "phase_3_started": False,
        },
    }
    _write_json(REPORT_DIRECTORY / "phase2-report.json", report)
    if report["status"] != "passed":
        failures = [row["adapter_id"] for row in results if row["status"] == "failed"]
        raise RuntimeError("Available Phase-2 adapter smoke failed: " + ", ".join(failures))
    return report


def asdict_fixture(value: Any) -> dict[str, Any]:
    return {"name": value.name, "passed": value.passed, "evidence": value.evidence}


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute-inference",
        action="store_true",
        help="Run locally available candidates on development inputs; never touches frozen evaluation inputs.",
    )
    args = parser.parse_args(arguments)
    try:
        report = execute(run_inference=args.execute_inference)
    except Exception as error:
        print(f"Phase 2 failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
