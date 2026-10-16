"""Audit corrected development-page inputs and strict per-system conversion without references."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from PIL import Image


HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parent.parent
SRC = HERE / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sheet2play_omr.adapter_contract import sha256_file  # noqa: E402


def _audit_system(source: Path, crop: Path, output: Path, converter: Path) -> dict[str, Any]:
    raw = source.with_suffix(".raw.txt")
    abc = source.with_suffix(".abc")
    record: dict[str, Any] = {
        "system": source.stem,
        "crop_sha256": sha256_file(crop),
        "raw_sha256": sha256_file(raw) if raw.is_file() else None,
        "abc_sha256": sha256_file(abc) if abc.is_file() else None,
        "strict_conversion_exit": None,
        "strict_conversion_warning_codes": [],
        "musicxml_sha256": None,
    }
    if not abc.is_file():
        return record
    musicxml = output / f"{source.stem}.musicxml"
    try:
        completed = subprocess.run(
            [str(converter), "xml", "--strict", "--warnings-as-errors", str(abc),
             "--output", str(musicxml)],
            check=False, capture_output=True, text=True, timeout=120,
            encoding="utf-8", errors="replace",
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        record["converter_error"] = f"{type(error).__name__}: {error}"
        return record
    log = output / f"{source.stem}.croma.log"
    log.write_text(completed.stdout + completed.stderr, encoding="utf-8")
    record["strict_conversion_exit"] = completed.returncode
    record["strict_conversion_warning_codes"] = sorted(set(re.findall(
        r"(?:warning|error)\[([^]]+)\]", completed.stderr)))
    record["musicxml_sha256"] = sha256_file(musicxml) if musicxml.is_file() else None
    record["converter_log_sha256"] = sha256_file(log)
    return record


def _audit_page(row: dict[str, Any], output: Path, converter: Path) -> dict[str, Any]:
    report_path = WORKSPACE / row["result_path"]
    if sha256_file(report_path) != row["result_sha256"]:
        raise ValueError(f"Per-item result hash mismatch: {report_path}")
    result = json.loads(report_path.read_text(encoding="utf-8"))
    item_output = HERE / ".runtime" / "phase2r" / "smokes" / report_path.stem
    manifest_path = item_output / "crops" / "crop-manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"Corrected crop manifest is missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["coordinate_space"] != "homr_predictions_preprocessed":
        raise ValueError(f"Unexpected coordinate space: {report_path}")
    if manifest["source_image"]["sha256"] != row["input_sha256"]:
        raise ValueError(f"Source image hash mismatch: {report_path}")
    detector = item_output / "detector-preprocessed.png"
    if sha256_file(detector) != manifest["detector_image"]["sha256"]:
        raise ValueError(f"Detector image hash mismatch: {report_path}")
    with Image.open(detector) as image:
        if image.size != (manifest["detector_image"]["width"],
                          manifest["detector_image"]["height"]):
            raise ValueError(f"Detector image dimensions mismatch: {report_path}")
    page_output = output / row["item_id"]
    page_output.mkdir(parents=True, exist_ok=False)
    systems = []
    for crop_row in manifest["crops"]:
        index = crop_row["system"]
        base = f"system-{index:04d}"
        crop = item_output / "crops" / f"{base}.png"
        if sha256_file(crop) != crop_row["sha256"]:
            raise ValueError(f"Crop hash mismatch: {crop}")
        with Image.open(crop) as image:
            if image.size != (crop_row["width"], crop_row["height"]):
                raise ValueError(f"Crop dimensions mismatch: {crop}")
        systems.append(_audit_system(item_output / base, crop, page_output, converter))
    return {
        "item_id": row["item_id"],
        "result_sha256": row["result_sha256"],
        "status": result["status"],
        "failure": result.get("error"),
        "source_image": manifest["source_image"],
        "detector_image": manifest["detector_image"],
        "crop_manifest_sha256": sha256_file(manifest_path),
        "system_count": len(systems),
        "systems": systems,
    }


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("aggregate", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(arguments)
    if args.output.exists():
        parser.error(f"Refusing to overwrite diagnostic report: {args.output}")
    aggregate = json.loads(args.aggregate.read_text(encoding="utf-8"))
    if aggregate.get("candidate_id") != "rokot" or len(aggregate.get("items", [])) != 32:
        parser.error("Expected a complete 32-item Rokot development aggregate")
    converter = HERE / ".runtime" / "phase2r" / "croma" / "croma-windows-x86_64.exe"
    if not converter.is_file():
        parser.error("Pinned converter is missing")
    artifact_root = HERE / ".runtime" / "phase2r" / "correction" / "strict-system-diagnostics"
    if artifact_root.exists():
        parser.error(f"Refusing to overwrite diagnostic artifacts: {artifact_root}")
    artifact_root.mkdir(parents=True)
    pages = [_audit_page(row, artifact_root, converter) for row in aggregate["items"]
             if row["collection"] == "open"]
    counts = Counter(page["status"] for page in pages)
    strict_counts = Counter(system["strict_conversion_exit"] for page in pages
                            for system in page["systems"])
    report = {
        "schema_version": 1,
        "scope": "corrected Phase 2R open development first pages; strict model-output conversion only",
        "diagnostic_source_sha256": sha256_file(Path(__file__)),
        "aggregate_sha256": sha256_file(args.aggregate),
        "converter_sha256": sha256_file(converter),
        "status_counts": dict(counts),
        "strict_system_conversion_exit_counts": {str(key): value for key, value in strict_counts.items()},
        "pages": pages,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps({"pages": len(pages), "status_counts": dict(counts),
                      "strict_system_conversion_exit_counts": report["strict_system_conversion_exit_counts"],
                      "report": str(args.output)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
