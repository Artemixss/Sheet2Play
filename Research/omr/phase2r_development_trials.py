"""Run a candidate on every generated control and one page of each open development composition."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parent.parent
SRC = HERE / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from phase2r import verify_historical_artifacts  # noqa: E402
from phase2r_smoke import _adapter  # noqa: E402
from sheet2play_omr.adapter_contract import (  # noqa: E402
    AdapterInput, MeasurementPath, sha256_file, write_result,
)
from sheet2play_omr.phase2r_development import development_records  # noqa: E402
from sheet2play_omr.phase2r_validation import run_with_typed_failure  # noqa: E402


def _items(candidate: str) -> list[tuple[str, AdapterInput]]:
    items: list[tuple[str, AdapterInput]] = []
    for record in development_records(WORKSPACE):
        if record.collection == "generated":
            path = MeasurementPath.COMPLETE_DOCUMENT if candidate == "audiveris" else MeasurementPath.ANNOTATED_CROP
            items.append((record.collection, AdapterInput(
                record.item_id, record.composition_group, record.image,
                record.image_sha256, path,
            )))
        else:
            page, digest = record.page_images[0]
            items.append((record.collection, AdapterInput(
                f"{record.item_id}-page-1", record.composition_group,
                page, digest, MeasurementPath.COMPLETE_DOCUMENT,
            )))
    return items


def _existing_result(path: Path, config_hash: str, item: AdapterInput) -> dict[str, Any]:
    row = json.loads(path.read_text(encoding="utf-8"))
    if (row.get("adapter_config_sha256") != config_hash or row.get("item_id") != item.item_id
            or row.get("provenance", {}).get("input_sha256") != item.input_sha256):
        raise ValueError(f"Existing development result has a different identity: {path}")
    item.validate()
    for artifact in row.get("artifacts", []):
        artifact_path = Path(artifact["path"])
        resolved = artifact_path if artifact_path.is_absolute() else WORKSPACE / artifact_path
        if not resolved.is_file() or sha256_file(resolved) != artifact["sha256"]:
            raise ValueError(f"Existing development artifact is missing or changed: {resolved}")
    return row


def _write_once(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite development trial report: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", choices=("rokot", "qwen", "audiveris"), required=True)
    parser.add_argument("--max-items", type=int, default=0, help="Stop after this many items; 0 runs all 32")
    parser.add_argument("--item-id", help="Run only one frozen development item without writing an aggregate")
    args = parser.parse_args(arguments)
    if args.max_items < 0:
        parser.error("--max-items cannot be negative")
    if args.item_id and args.max_items:
        parser.error("--item-id and --max-items cannot be combined")
    verify_historical_artifacts()
    adapter = _adapter(args.candidate)
    config_hash = adapter.config.sha256  # type: ignore[attr-defined]
    executable = getattr(adapter, "executable", None) or getattr(adapter, "cli", None)
    runtime_hash = sha256_file(executable)[:12] if executable is not None and executable.is_file() else "no-runtime"
    rows: list[dict[str, Any]] = []
    all_items = _items(args.candidate)
    selected = ([entry for entry in all_items if entry[1].item_id == args.item_id]
                if args.item_id else all_items[:args.max_items] if args.max_items else all_items)
    if not selected:
        parser.error(f"Unknown frozen development item: {args.item_id}")
    for collection, item in selected:
        identity = f"{args.candidate}-{item.item_id}-{config_hash[:12]}-{runtime_hash}"
        result_path = HERE / "reports" / "phase2r" / "development-smokes" / f"{identity}.json"
        output = HERE / ".runtime" / "phase2r" / "smokes" / identity
        legacy_path = HERE / "reports" / "phase2r" / "development-smokes" / (
            f"{args.candidate}-{item.item_id}-{config_hash[:12]}-no-runtime.json"
        )
        if result_path.is_file():
            result = _existing_result(result_path, config_hash, item)
            print(f"{item.item_id}: reused {result['status']}", flush=True)
        elif legacy_path != result_path and legacy_path.is_file():
            result_path = legacy_path
            result = _existing_result(result_path, config_hash, item)
            print(f"{item.item_id}: reused legacy-named {result['status']}", flush=True)
        else:
            if output.exists():
                raise FileExistsError(f"Partial output exists without a result; inspect before retry: {output}")
            print(f"{item.item_id}: starting {collection}", flush=True)
            adapter_result = run_with_typed_failure(adapter, item, output)
            write_result(result_path, adapter_result)
            result = adapter_result.to_json()
            print(f"{item.item_id}: {result['status']}", flush=True)
        rows.append({
            "item_id": item.item_id,
            "collection": collection,
            "input_sha256": item.input_sha256,
            "measurement_path": item.measurement_path.value,
            "status": result["status"],
            "error": result.get("error"),
            "result_path": result_path.relative_to(WORKSPACE).as_posix(),
            "result_sha256": sha256_file(result_path),
        })
    if len(selected) != len(all_items):
        print(json.dumps({"completed_items": len(rows), "total_items": len(all_items),
                          "final_report_written": False}, sort_keys=True))
        return 0
    counts = Counter(row["status"] for row in rows)
    report = {
        "schema_version": 1,
        "phase": "2R",
        "candidate_id": adapter.config.candidate_id,  # type: ignore[attr-defined]
        "adapter_config_sha256": config_hash,
        "runtime_executable_sha256_prefix": runtime_hash,
        "scope": {"development_only": True, "open_composition_count": 20,
                  "one_page_per_open_composition": True, "generated_control_count": 12,
                  "full_composition_accuracy_claim": False, "phase3_started": False},
        "status_counts": dict(sorted(counts.items())),
        "items": rows,
    }
    destination = HERE / "reports" / "phase2r" / "development-trials" / (
        f"{args.candidate}-{config_hash[:12]}-{runtime_hash}-v1.json"
    )
    _write_once(destination, report)
    print(json.dumps({"completed_items": len(rows), "status_counts": report["status_counts"],
                      "final_report": str(destination)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
