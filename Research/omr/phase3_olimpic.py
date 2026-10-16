"""Audit and evaluate the frozen 100-system OLiMPiC regression canary."""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import statistics
import sys
import warnings
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import Any

from phase1 import olimpic_warning_is_fatal
from phase2 import verify_phase1_freeze
from phase3_development_entry import _adapter
from phase3_freeze import verify_freeze
from phase3_infer import _verify_existing
from phase3_score import _duration_summary, _macro, _percentile
from sheet2play_omr.adapter_contract import (
    AdapterInput, MeasurementPath, sha256_file, write_result,
)
from sheet2play_omr.phase2r_validation import run_with_typed_failure
from sheet2play_omr.phase3_scoring import score_result


WORKSPACE = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "reports" / "phase1" / "olimpic-canary.jsonl"
REFERENCE_ROOT = HERE / ".runtime" / "phase3" / "olimpic-references"


def _rows() -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in MANIFEST.read_text(encoding="utf-8").splitlines() if line]
    if len(rows) != 100 or len({row["id"] for row in rows}) != 100:
        raise RuntimeError("Frozen OLiMPiC canary must contain 100 unique systems")
    return rows


def _write_once(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite frozen OLiMPiC evidence: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
                         encoding="utf-8")
    temporary.replace(path)


def _audit_path() -> Path:
    return HERE / "reports" / "phase3" / f"olimpic-canary-reference-audit-{sha256_file(Path(__file__))[:12]}.json"


def _reference_path(item_id: str, identity: dict[str, str]) -> Path:
    payload = json.dumps({"item_id": item_id, "identity": identity}, sort_keys=True)
    return REFERENCE_ROOT / f"{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:24]}.json"


def _reference_identity() -> dict[str, str]:
    return {"manifest_sha256": sha256_file(MANIFEST),
            "normalizer_sha256": sha256_file(WORKSPACE / "Bridge" / "musicxml_normalizer.py"),
            "builder_sha256": sha256_file(Path(__file__))}


def _reference(row: dict[str, Any], identity: dict[str, str]) -> dict[str, Any]:
    from music21 import converter, stream

    image = WORKSPACE / row["image_path"]
    musicxml = WORKSPACE / row["musicxml_path"]
    if (not image.is_file() or sha256_file(image) != row["image_sha256"]
            or not musicxml.is_file() or sha256_file(musicxml) != row["musicxml_sha256"]):
        raise ValueError("Frozen OLiMPiC image or MusicXML is missing or changed")
    bridge = WORKSPACE / "Bridge"
    if str(bridge) not in sys.path:
        sys.path.insert(0, str(bridge))
    from musicxml_normalizer import normalize_musicxml

    output = io.StringIO()
    errors = io.StringIO()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            source = converter.parse(str(musicxml), forceSource=True)
            normalized = normalize_musicxml(musicxml, expand_repeats=False,
                                             skip_grace_notes=True, force_source=True)
    messages = [f"{item.category.__name__}: {item.message}" for item in caught]
    messages.extend(line for line in (output.getvalue() + "\n" + errors.getvalue()).splitlines() if line)
    fatal = [message for message in messages
             if olimpic_warning_is_fatal(message.split(": ", 1)[-1])]
    if fatal:
        raise ValueError(f"Unreviewed OLiMPiC reference warnings: {fatal[:3]}")
    boundaries = sorted({Fraction(0)} | {
        Fraction(str(measure.getOffsetInHierarchy(part))).limit_denominator(4096)
        for part in source.parts
        for measure in part.getElementsByClass(stream.Measure)
    })
    notes = [{"midi_pitch": note.midi_pitch,
              "onset": str(Fraction(str(note.start_beat)).limit_denominator(4096)),
              "duration": str(Fraction(str(note.duration_beats)).limit_denominator(4096)),
              "staff": note.staff_index, "voice": note.voice_identifier}
             for note in normalized.notes]
    if not notes or not boundaries:
        raise ValueError("OLiMPiC reference has no sounding notes or measure boundaries")
    return {
        "schema_version": 1, "item_id": row["id"],
        "identity": identity,
        "composition_group": row["composition_group"],
        "image_sha256": row["image_sha256"],
        "reference_musicxml": row["musicxml_path"],
        "reference_musicxml_sha256": row["musicxml_sha256"],
        "measure_boundaries": [str(value) for value in boundaries],
        "normalization_warnings": messages,
        "notes": notes,
    }


def audit() -> Path:
    verify_phase1_freeze()
    destination = _audit_path()
    if destination.exists():
        raise FileExistsError(f"Frozen OLiMPiC audit already exists: {destination}")
    identity = _reference_identity()
    outcomes = []
    for index, row in enumerate(_rows(), start=1):
        path = _reference_path(row["id"], identity)
        try:
            if path.is_file():
                payload = json.loads(path.read_text(encoding="utf-8"))
                if (payload["item_id"] != row["id"]
                        or payload.get("identity") != identity
                        or payload["image_sha256"] != row["image_sha256"]
                        or payload["reference_musicxml_sha256"] != row["musicxml_sha256"]):
                    raise ValueError("Cached OLiMPiC reference identity differs")
                state = "verified_cache"
            else:
                payload = _reference(row, identity)
                _write_once(path, payload)
                state = "generated"
            outcome = {"id": row["id"], "status": "valid", "state": state,
                       "reference_path": path.relative_to(WORKSPACE).as_posix(),
                       "reference_sha256": sha256_file(path),
                       "note_count": len(payload["notes"]),
                       "warning_count": len(payload["normalization_warnings"])}
        except Exception as error:
            outcome = {"id": row["id"], "status": "invalid",
                       "error": f"{type(error).__name__}: {error}"[:500]}
        outcomes.append(outcome)
        print(json.dumps({"item": index, "total": 100, **outcome}, sort_keys=True), flush=True)
    report = {"schema_version": 1, "collection": "olimpic-canary", "eligible_count": 100,
              "valid_count": sum(item["status"] == "valid" for item in outcomes),
              "invalid_count": sum(item["status"] == "invalid" for item in outcomes),
              **identity, "items": outcomes}
    _write_once(destination, report)
    print(json.dumps({"audit": str(destination), "valid": report["valid_count"],
                      "invalid": report["invalid_count"]}, sort_keys=True), flush=True)
    return destination


def _verified_audit() -> dict[str, Any]:
    report = json.loads(_audit_path().read_text(encoding="utf-8"))
    if (report["valid_count"] != 100 or report["invalid_count"] != 0
            or any(report.get(key) != value for key, value in _reference_identity().items())
            or len({item["id"] for item in report["items"]}) != 100):
        raise RuntimeError("Frozen OLiMPiC reference audit is incomplete or changed")
    for item in report["items"]:
        path = WORKSPACE / item["reference_path"]
        if not path.is_file() or sha256_file(path) != item["reference_sha256"]:
            raise RuntimeError(f"OLiMPiC reference changed: {path}")
    return report


def _result_path(item_id: str, config_hash: str) -> tuple[Path, Path]:
    stem = f"{hashlib.sha256(item_id.encode('utf-8')).hexdigest()[:20]}-{config_hash[:12]}"
    report = HERE / "reports" / "phase3" / "evaluation" / "olimpic-canary" / "zeus_system" / f"{stem}.json"
    raw = HERE / ".runtime" / "phase3" / "evaluation" / "olimpic-canary" / "zeus_system" / stem
    return report, raw


def infer(freeze_path: Path, start_index: int = 1, max_items: int = 0) -> None:
    if start_index < 1 or max_items < 0:
        raise ValueError("Invalid frozen OLiMPiC item range")
    freeze = verify_freeze(freeze_path.resolve())
    audit_report = _verified_audit()
    references = {item["id"]: item for item in audit_report["items"]}
    adapter, _ = _adapter("zeus_system")
    config_hash = adapter.config.sha256  # type: ignore[attr-defined]
    if config_hash != freeze["ready"]["zeus_system"]["adapter_config_sha256"]:
        raise RuntimeError("Zeus system adapter changed since freeze")
    rows = _rows()
    selected = rows[start_index - 1:]
    if max_items:
        selected = selected[:max_items]
    if not selected:
        raise ValueError("Selected OLiMPiC range is empty")
    freeze_hash = sha256_file(freeze_path)
    for offset, row in enumerate(selected, start=start_index):
        item = AdapterInput(row["id"], row["composition_group"],
                            WORKSPACE / row["image_path"], row["image_sha256"],
                            MeasurementPath.ANNOTATED_CROP)
        item.validate()
        path, raw = _result_path(item.item_id, config_hash)
        identity = {"schema_version": 1, "freeze_sha256": freeze_hash,
                    "candidate": "zeus_system", "item_id": item.item_id,
                    "image_sha256": item.input_sha256,
                    "reference_sha256": references[item.item_id]["reference_sha256"],
                    "adapter_config_sha256": config_hash}
        if path.is_file():
            status = _verify_existing(path, identity)
        else:
            if raw.exists() or path.with_suffix(".identity.json").exists():
                raise FileExistsError(f"Partial OLiMPiC inference needs inspection: {raw}")
            result = run_with_typed_failure(adapter, item, raw)
            if result.status.value == "unavailable":
                raise RuntimeError(f"Zeus became unavailable on {item.item_id}")
            write_result(path, result)
            _write_once(path.with_suffix(".identity.json"), identity)
            status = result.status.value
        print(json.dumps({"item": offset, "total": 100, "id": item.item_id,
                          "status": status}, sort_keys=True), flush=True)


def score(freeze_path: Path) -> Path:
    freeze = verify_freeze(freeze_path.resolve())
    audit_report = _verified_audit()
    references = {item["id"]: item for item in audit_report["items"]}
    freeze_hash = sha256_file(freeze_path)
    config_hash = freeze["ready"]["zeus_system"]["adapter_config_sha256"]
    metrics = []
    for index, row in enumerate(_rows(), start=1):
        path, _ = _result_path(row["id"], config_hash)
        if not path.is_file():
            raise RuntimeError(f"OLiMPiC inference incomplete at {index}/100: {row['id']}")
        reference_meta = references[row["id"]]
        identity = {"schema_version": 1, "freeze_sha256": freeze_hash,
                    "candidate": "zeus_system", "item_id": row["id"],
                    "image_sha256": row["image_sha256"],
                    "reference_sha256": reference_meta["reference_sha256"],
                    "adapter_config_sha256": config_hash}
        _verify_existing(path, identity)
        score_identity = {"freeze_sha256": freeze_hash,
                          "result_sha256": sha256_file(path),
                          "reference_sha256": reference_meta["reference_sha256"],
                          "scoring_module_sha256": sha256_file(HERE / "src" / "sheet2play_omr" / "phase3_scoring.py"),
                          "scoring_runner_sha256": sha256_file(Path(__file__))}
        scored_path = HERE / "reports" / "phase3" / "scored" / "olimpic-canary" / "zeus_system" / path.name
        sidecar = scored_path.with_suffix(".identity.json")
        if scored_path.is_file():
            if not sidecar.is_file() or json.loads(sidecar.read_text(encoding="utf-8")) != score_identity:
                raise RuntimeError(f"Frozen OLiMPiC score identity changed: {scored_path}")
            item_metrics = json.loads(scored_path.read_text(encoding="utf-8"))
        else:
            if sidecar.exists():
                raise FileExistsError(f"Partial OLiMPiC score sidecar exists: {sidecar}")
            reference = json.loads((WORKSPACE / reference_meta["reference_path"]).read_text(encoding="utf-8"))
            result = json.loads(path.read_text(encoding="utf-8"))
            item_metrics = score_result(result, reference, WORKSPACE)
            _write_once(scored_path, item_metrics)
            _write_once(sidecar, score_identity)
        metrics.append(item_metrics)
        print(json.dumps({"item": index, "total": 100, "id": row["id"],
                          "status": metrics[-1]["status"]}, sort_keys=True), flush=True)
    valid_ned = [row["omr_ned"] for row in metrics if row["omr_ned_status"] == "valid"]
    penalized = [row["failure_penalized_omr_ned"] for row in metrics
                 if row["failure_penalized_omr_ned"] is not None]
    elapsed = [row["elapsed_seconds"] for row in metrics]
    summary = {
        "schema_version": 1, "scope": "phase3_annotated_system_regression_no_paired_ranking",
        "collection": "olimpic-canary", "candidate": "zeus_system",
        "freeze_sha256": freeze_hash, "reference_audit_sha256": sha256_file(_audit_path()),
        "eligible_system_count": 100, "status_counts": dict(Counter(row["status"] for row in metrics)),
        "composition_count": len({row["composition_group"] for row in metrics}),
        "composition_macro": {name: _macro(metrics, name)
                              for name in ("pitch_f1", "onset_f1", "onset_duration_f1")},
        "valid_output_omr_ned_mean": statistics.mean(valid_ned) if valid_ned else None,
        "valid_output_omr_ned_count": len(valid_ned),
        "failure_penalized_omr_ned_mean": statistics.mean(penalized) if penalized else None,
        "failure_penalized_omr_ned_count": len(penalized),
        "omr_ned_scoring_error_count": sum(row["omr_ned_status"] == "scoring_error" for row in metrics),
        "duration_classification": _duration_summary(metrics),
        "latency_seconds": {"median": statistics.median(elapsed),
                            "p95": _percentile(elapsed, 0.95), "includes_failures": True},
        "peak_ram_bytes_max": max((row["peak_ram_bytes"] for row in metrics
                                   if row["peak_ram_bytes"] is not None), default=None),
        "peak_vram_bytes_max": max((row["peak_vram_bytes"] for row in metrics
                                    if row["peak_vram_bytes"] is not None), default=None),
        "vram_measurement_notes": sorted({note for row in metrics
                                          for note in row["vram_measurement_notes"]}),
        "training_overlap": "Known OLiMPiC repertoire family overlap; regression collection only",
        "actual_cloud_cost_usd": 0.0,
    }
    output = HERE / "reports" / "phase3" / f"summary-olimpic-canary-zeus-system-{freeze_hash[:12]}.json"
    _write_once(output, summary)
    print(json.dumps({"summary": str(output),
                      "primary_f1": summary["composition_macro"]["onset_duration_f1"]},
                     sort_keys=True), flush=True)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("audit", "infer", "score"))
    parser.add_argument("--freeze", type=Path)
    parser.add_argument("--start-index", type=int, default=1)
    parser.add_argument("--max-items", type=int, default=0)
    args = parser.parse_args()
    if args.action == "audit":
        report = audit()
        if json.loads(report.read_text(encoding="utf-8"))["invalid_count"]:
            raise SystemExit(2)
    elif args.freeze is None:
        parser.error("--freeze is required for infer and score")
    elif args.action == "infer":
        infer(args.freeze, args.start_index, args.max_items)
    else:
        score(args.freeze)


if __name__ == "__main__":
    main()
