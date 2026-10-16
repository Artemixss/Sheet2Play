"""Score a pinned HOMR ONNX pair on the frozen OLiMPiC canary."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
import sys
from collections import defaultdict
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parent.parent
sys.path.insert(0, str(HERE / "src"))

from sheet2play_omr.adapter_contract import (  # noqa: E402
    AdapterInput,
    MeasurementPath,
    RunStatus,
    sha256_file,
)
from sheet2play_omr.metrics import MetricNote, calculate_note_metrics  # noqa: E402
from sheet2play_omr.phase2_adapters import ShippedHomrAdapter, _canonicalize  # noqa: E402
from sheet2play_omr.phase2r_validation import run_with_typed_failure  # noqa: E402


REPORT_DIR = HERE / "reports" / "phase1"
FROZEN_REPORT = REPORT_DIR / "phase1-report.json"
MANIFEST = REPORT_DIR / "olimpic-canary.jsonl"
PROTOCOL = REPORT_DIR / "scoring-protocol.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--encoder", type=Path, required=True)
    parser.add_argument("--encoder-sha256", required=True)
    parser.add_argument("--decoder", type=Path, required=True)
    parser.add_argument("--decoder-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-items", type=int, default=0)
    args = parser.parse_args()
    if not args.candidate_id.strip() or not args.revision.strip():
        parser.error("Candidate ID and revision must be nonempty")
    if args.max_items < 0:
        parser.error("--max-items cannot be negative")
    return args


def verify_hash(path: Path, expected: str) -> Path:
    if not path.is_file() or len(expected) != 64 or sha256_file(path) != expected.lower():
        raise ValueError(f"Missing file or SHA-256 mismatch: {path}")
    return path.resolve()


def frozen_items() -> list[dict[str, object]]:
    report = json.loads(FROZEN_REPORT.read_text(encoding="utf-8"))
    verify_hash(MANIFEST, report["artifact_sha256"][MANIFEST.name])
    verify_hash(PROTOCOL, report["artifact_sha256"][PROTOCOL.name])
    items = [json.loads(line) for line in MANIFEST.read_text(encoding="utf-8").splitlines() if line]
    if len(items) != 100 or len({row["id"] for row in items}) != 100:
        raise ValueError("Frozen OLiMPiC canary must contain 100 unique eligible items")
    return items


def notes_from_canonical(path: Path) -> list[MetricNote]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [
        MetricNote(
            pitch=int(note["midi_pitch"]),
            onset=Fraction(str(note["onset"])).limit_denominator(4096),
            duration=Fraction(str(note["duration"])).limit_denominator(4096),
            staff=int(note["staff"]),
            voice=str(note["voice"]),
        )
        for note in payload["notes"]
    ]


def reference_notes(item: dict[str, object], output: Path) -> list[MetricNote]:
    path = verify_hash(WORKSPACE / str(item["musicxml_path"]), str(item["musicxml_sha256"]))
    destination = output / "references" / str(item["id"]).replace("/", "__") / "canonical.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.is_file():
        _canonicalize(path, destination)
    return notes_from_canonical(destination)


def make_adapter(args: argparse.Namespace, encoder: Path, decoder: Path) -> ShippedHomrAdapter:
    adapter = ShippedHomrAdapter(WORKSPACE)
    adapter.launcher = HERE / "homr_candidate_launcher.py"
    adapter.config = replace(
        adapter.config,
        candidate_id=args.candidate_id,
        adapter_id="homr_explicit_onnx_pair",
        checkpoint=f"encoder={encoder.name}; decoder={decoder.name}",
        checkpoint_revision=args.revision,
        settings={
            **adapter.config.settings,
            "encoder_sha256": args.encoder_sha256.lower(),
            "decoder_sha256": args.decoder_sha256.lower(),
        },
    )
    return adapter


def score_item(
    item: dict[str, object], adapter: ShippedHomrAdapter, args: argparse.Namespace,
    encoder: Path, decoder: Path,
) -> dict[str, object]:
    item_id = str(item["id"])
    item_output = args.output / "artifacts" / item_id.replace("/", "__")
    image = WORKSPACE / str(item["image_path"])
    adapter_input = AdapterInput(
        item_id=item_id,
        composition_group=str(item["composition_group"]),
        input_path=image,
        input_sha256=str(item["image_sha256"]),
        measurement_path=MeasurementPath.ANNOTATED_CROP,
        reference_path=WORKSPACE / str(item["musicxml_path"]),
        reference_sha256=str(item["musicxml_sha256"]),
    )
    adapter_input.validate()
    truth = reference_notes(item, args.output)
    environment = {
        "SHEET2PLAY_CANDIDATE_ENCODER": str(encoder),
        "SHEET2PLAY_CANDIDATE_ENCODER_SHA256": args.encoder_sha256.lower(),
        "SHEET2PLAY_CANDIDATE_DECODER": str(decoder),
        "SHEET2PLAY_CANDIDATE_DECODER_SHA256": args.decoder_sha256.lower(),
    }
    with patch.dict(os.environ, environment):
        result = run_with_typed_failure(adapter, adapter_input, item_output)
    row: dict[str, object] = {
        "id": item_id,
        "composition_group": str(item["composition_group"]),
        "adapter_result": result.to_json(),
        "metrics": None,
        "primary_f1": 0.0,
    }
    if result.status is RunStatus.SUCCEEDED:
        predicted = notes_from_canonical(item_output / "canonical-events.json")
        metrics = calculate_note_metrics(predicted, truth)
        row["metrics"] = {
            "pitch_f1": metrics.pitch_f1,
            "onset_f1": metrics.onset_f1,
            "onset_duration_f1": metrics.onset_duration_f1,
            "predicted_notes": len(predicted),
            "reference_notes": len(truth),
        }
        row["primary_f1"] = metrics.onset_duration_f1
    return row


def composition_macro(rows: list[dict[str, object]], key: str) -> float:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        metrics = row.get("metrics")
        value = float(metrics[key]) if isinstance(metrics, dict) else 0.0
        grouped[str(row["composition_group"])].append(value)
    return statistics.fmean(statistics.fmean(values) for values in grouped.values())


def save_json(path: Path, document: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(document, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    args = parse_args()
    encoder = verify_hash(args.encoder, args.encoder_sha256)
    decoder = verify_hash(args.decoder, args.decoder_sha256)
    if encoder == decoder:
        raise ValueError("Encoder and decoder paths must differ")
    items = frozen_items()
    adapter = make_adapter(args, encoder, decoder)
    checkpoint_path = args.output / "checkpoint.json"
    identity = {
        "candidate_id": args.candidate_id,
        "adapter_config_sha256": adapter.config.sha256,
        "manifest_sha256": sha256_file(MANIFEST),
        "protocol_sha256": sha256_file(PROTOCOL),
        "launcher_sha256": sha256_file(HERE / "homr_candidate_launcher.py"),
        "runner_sha256": sha256_file(Path(__file__)),
    }
    if checkpoint_path.is_file():
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        if checkpoint.get("identity") != identity:
            raise ValueError("Existing checkpoint has a different model, protocol, or runner identity")
    else:
        checkpoint = {"identity": identity, "rows": {}}
    maximum = args.max_items or len(items)
    for index, item in enumerate(items[:maximum], start=1):
        item_id = str(item["id"])
        if item_id in checkpoint["rows"]:
            continue
        print(f"[{index}/{len(items)}] {args.candidate_id}: {item_id}", flush=True)
        checkpoint["rows"][item_id] = score_item(item, adapter, args, encoder, decoder)
        save_json(checkpoint_path, checkpoint)
    rows = [checkpoint["rows"][str(item["id"])] for item in items if str(item["id"]) in checkpoint["rows"]]
    summary = {
        "completed": len(rows),
        "expected": len(items),
        "failures": sum(row["metrics"] is None for row in rows),
        "primary_f1": composition_macro(rows, "onset_duration_f1") if rows else None,
        "onset_f1": composition_macro(rows, "onset_f1") if rows else None,
        "pitch_f1": composition_macro(rows, "pitch_f1") if rows else None,
    }
    if any(isinstance(value, float) and not math.isfinite(value) for value in summary.values()):
        raise ValueError("Non-finite benchmark summary")
    save_json(args.output / "summary.json", {"identity": identity, "summary": summary})
    print(json.dumps(summary, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
