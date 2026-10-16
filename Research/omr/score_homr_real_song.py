"""Score two HOMR Bridge outputs against one locally held MIDI reference."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "src"))

from evaluate_library import notes_from_midi, notes_from_payload  # noqa: E402
from sheet2play_omr.metrics import calculate_note_metrics  # noqa: E402


def file_sha256(path: Path) -> str:
    if not path.is_file():
        raise ValueError(f"Missing input: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def bridge_payload(path: Path) -> dict[str, object]:
    lines = path.read_text(encoding="utf-8").splitlines()
    for line in reversed(lines):
        if line.startswith("{"):
            payload = json.loads(line)
            if isinstance(payload, dict) and isinstance(payload.get("notes"), list):
                return payload
    raise ValueError(f"No valid Bridge payload: {path}")


def score(payload: dict[str, object], reference: list[object]) -> dict[str, object]:
    predicted = notes_from_payload(payload)
    if not predicted or not reference:
        raise ValueError("Both prediction and reference must contain notes")
    metrics = calculate_note_metrics(predicted, reference)
    return {
        "predicted_notes": len(predicted),
        "pitch_f1": metrics.pitch_f1,
        "onset_f1": metrics.onset_f1,
        "onset_duration_f1": metrics.onset_duration_f1,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--encoder", type=Path, required=True)
    parser.add_argument("--decoder", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    source_hash = file_sha256(args.pdf)
    reference_hash = file_sha256(args.reference)
    baseline_record = json.loads(args.baseline.read_text(encoding="utf-8"))
    if not baseline_record.get("ok") or baseline_record.get("source_sha256") != source_hash:
        raise ValueError("Baseline source identity does not match the requested PDF")
    baseline_payload = baseline_record.get("payload")
    if not isinstance(baseline_payload, dict):
        raise ValueError("Baseline record has no Bridge payload")
    candidate_payload = bridge_payload(args.candidate)
    if candidate_payload.get("engine") != "homr":
        raise ValueError("Candidate output was not produced by HOMR")

    reference = notes_from_midi(args.reference)
    baseline = score(baseline_payload, reference)
    candidate = score(candidate_payload, reference)
    metrics = ("pitch_f1", "onset_f1", "onset_duration_f1")
    report = {
        "source_sha256": source_hash,
        "reference_sha256": reference_hash,
        "reference_notes": len(reference),
        "baseline": baseline,
        "candidate": candidate,
        "candidate_revision": candidate_payload.get("engine_revision"),
        "candidate_encoder_sha256": file_sha256(args.encoder),
        "candidate_decoder_sha256": file_sha256(args.decoder),
        "candidate_minus_baseline": {
            name: candidate[name] - baseline[name] for name in metrics
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
