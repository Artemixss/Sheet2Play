"""
Sheet2Play Phase 3 — Rhythm Constraint Experiment Runner.

Runs the rhythm-aware constrained decoder against the failed canary subset
(beam-invalid samples) and compares results against beam-only and grammar-only.

Usage:
    .\\Research\\omr\\.venv\\Scripts\\python.exe .\\Research\\omr\\run_rhythm_experiment.py ^
        --canary-checkpoint .\\Research\\omr\\reports\\phase3\\canary.checkpoint.json ^
        --dataset-root .\\Research\\omr\\data\\olimpic\\olimpic-1.0-scanned ^
        --output-dir .\\Research\\omr\\reports\\phase3\\rhythm_experiment

The script:
  1. Reads the canary checkpoint to identify beam-invalid samples.
  2. Loads the Transcoda model once with RhythmAwareTranscodaRunner.
  3. Runs rhythm-aware grammar decoding on each failed sample.
  4. Writes a per-sample JSONL log and a summary JSON comparison report.

Constraints honoured:
  - No modification of pinned Transcoda source.
  - 60-second deadline per retry (inherited).
  - CUDA-only, deterministic.
  - No decoded-token repair.
  - Stops after a fatal GPU error; checkpoint is not atomic (small experiment).
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from fractions import Fraction
from pathlib import Path
from typing import Any

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent


def _add_src_to_path() -> None:
    src = Path(__file__).resolve().parent / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


_add_src_to_path()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run rhythm-aware grammar decoder on beam-failed canary samples"
    )
    parser.add_argument(
        "--canary-checkpoint",
        type=Path,
        default=WORKSPACE_ROOT / "Research" / "omr" / "reports" / "phase3" / "canary.checkpoint.json",
    )
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=WORKSPACE_ROOT / "Research" / "omr" / "data" / "olimpic" / "olimpic-1.0-scanned",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=WORKSPACE_ROOT / "Research" / "omr" / "reports" / "phase3" / "rhythm_experiment",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit the number of samples to evaluate (for quick spot-checks)",
    )
    return parser.parse_args()


def _load_checkpoint(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _get_failed_beam_samples(checkpoint: dict[str, Any]) -> list[str]:
    """Return sample IDs where beam decoding failed (invalid output)."""
    beam = checkpoint.get("transcoda_beam_only", {})
    return sorted(sid for sid, row in beam.items() if not row.get("valid"))


def _load_sample_image(dataset_root: Path, sample_id: str):
    """Load the source image for a given sample ID (score_id/page-system)."""
    from PIL import Image
    from sheet2play_omr.olimpic import OlimpicSample, load_test_partition

    score_id, page_system = sample_id.split("/", 1)
    page_str, system_str = page_system.split("-")
    page = int(page_str[1:])
    system = int(system_str[1:])

    # Find the image file: images are stored as page scans
    # OLiMPiC structure: <dataset_root>/<score_id>/images/p<page>.png
    img_candidates = [
        dataset_root / score_id / "images" / f"p{page}.png",
        dataset_root / score_id / "images" / f"p{page:02d}.png",
        dataset_root / score_id / f"p{page}.png",
    ]
    for candidate in img_candidates:
        if candidate.exists():
            return Image.open(candidate).convert("RGB")

    # Fall back to using OlimpicSample discovery
    all_samples = load_test_partition(dataset_root)
    for sample in all_samples:
        if sample.id == sample_id:
            return Image.open(sample.image_path).convert("RGB")

    raise FileNotFoundError(f"Cannot find image for sample {sample_id}")


def _get_ground_truth_notes(dataset_root: Path, sample_id: str, workspace_root: Path) -> list:
    """Load ground truth metric notes from OLiMPiC MusicXML."""
    bridge_dir = str(workspace_root / "Bridge")
    if bridge_dir not in sys.path:
        sys.path.insert(0, bridge_dir)

    from sheet2play_omr.olimpic import load_test_partition
    all_samples = load_test_partition(dataset_root)
    sample = next((s for s in all_samples if s.id == sample_id), None)
    if sample is None:
        return []

    from sheet2play_omr.phase3_benchmark import load_ground_truth_notes
    try:
        return load_ground_truth_notes(sample.musicxml_path)
    except Exception:
        return []


def _serialize_error(error: Exception) -> dict[str, Any]:
    return {
        "code": str(getattr(error, "code", error.__class__.__name__)),
        "stage": str(getattr(error, "stage", "rhythm_experiment")),
        "message": str(error)[:1000],
    }


def main() -> int:
    args = _parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading canary checkpoint: {args.canary_checkpoint}", flush=True)
    checkpoint = _load_checkpoint(args.canary_checkpoint)

    failed_samples = _get_failed_beam_samples(checkpoint)
    print(f"Beam-invalid samples: {len(failed_samples)}", flush=True)

    if args.limit:
        failed_samples = failed_samples[: args.limit]
        print(f"Limiting to {len(failed_samples)} samples (--limit)", flush=True)

    grammar_results = checkpoint.get("transcoda_beam_then_grammar", {})

    from sheet2play_omr.rhythm_decoder import (
        RHYTHM_POLICY_HASH,
        RHYTHM_POLICY_ID,
        RHYTHM_POLICY_VERSION,
        RhythmAwareTranscodaRunner,
    )
    from sheet2play_omr.assets import RuntimePaths
    from sheet2play_omr.errors import ResearchError
    from sheet2play_omr.events import extract_canonical_events, parse_kern
    from sheet2play_omr.phase3_benchmark import load_ground_truth_notes
    from sheet2play_omr.olimpic import load_test_partition
    from fractions import Fraction
    from sheet2play_omr.metrics import MetricNote, calculate_note_metrics
    from dataclasses import asdict
    import math

    print(f"Policy: {RHYTHM_POLICY_ID}", flush=True)
    print(f"Policy hash: {RHYTHM_POLICY_HASH}", flush=True)

    paths = RuntimePaths.discover()
    print("Loading model (grammar+rhythm mode)...", flush=True)
    runner = RhythmAwareTranscodaRunner(mode="grammar", paths=paths)
    print("Model loaded.", flush=True)

    # Load all samples for image/ground-truth access
    all_samples = {s.identifier: s for s in load_test_partition(args.dataset_root)}

    results: list[dict[str, Any]] = []
    log_path = args.output_dir / "rhythm_experiment.jsonl"

    rescued = 0
    failed = 0
    error_codes: dict[str, int] = {}

    for idx, sample_id in enumerate(failed_samples):
        sample = all_samples.get(sample_id)
        if sample is None:
            print(f"  [{idx+1}/{len(failed_samples)}] {sample_id}: SKIP (not in dataset)", flush=True)
            continue

        print(f"  [{idx+1}/{len(failed_samples)}] {sample_id}...", end=" ", flush=True)
        started = time.perf_counter()

        row: dict[str, Any] = {
            "sample_id": sample_id,
            "policy_version": RHYTHM_POLICY_VERSION,
            "policy_hash": RHYTHM_POLICY_HASH,
            "beam_error": checkpoint.get("transcoda_beam_only", {}).get(sample_id, {}).get("error"),
            "grammar_error": grammar_results.get(sample_id, {}).get("error"),
        }

        try:
            from PIL import Image
            with Image.open(Path(sample.image)).convert("RGB") as img:
                result = runner.predict(img, page=1, total_pages=1, mode="grammar")

            elapsed = time.perf_counter() - started
            row["valid"] = True
            row["seconds"] = elapsed
            row["tokens"] = result.tokens
            row["peak_vram_bytes"] = result.peak_vram_bytes

            # Compute note metrics if ground truth is available
            try:
                from sheet2play_omr.events import CanonicalScore
                score = parse_kern(result.kern)
                canonical = extract_canonical_events(score)
                predicted_notes = [
                    MetricNote(
                        pitch=int(e.midi_pitch),
                        onset=Fraction(e.onset),
                        duration=Fraction(e.duration),
                        staff=e.staff,
                        voice=e.voice,
                    )
                    for e in canonical.events
                    if e.kind == "note" and e.midi_pitch is not None
                ]
                expected_notes = load_ground_truth_notes(Path(sample.musicxml))
                metrics = asdict(calculate_note_metrics(predicted_notes, expected_notes))
                if not math.isfinite(metrics.get("mean_offset_error", float("nan"))):
                    metrics["mean_offset_error"] = None
                row["metrics"] = metrics
            except Exception as metrics_error:
                row["metrics"] = None
                row["metrics_error"] = str(metrics_error)[:200]

            rescued += 1
            print(f"VALID ({elapsed:.1f}s, {result.tokens} tokens)", flush=True)

        except ResearchError as error:
            elapsed = time.perf_counter() - started
            row["valid"] = False
            row["seconds"] = elapsed
            row["error"] = _serialize_error(error)
            code = str(getattr(error, "code", "UNKNOWN"))
            error_codes[code] = error_codes.get(code, 0) + 1
            failed += 1
            print(f"FAILED {code} ({elapsed:.1f}s)", flush=True)

        except Exception as error:
            elapsed = time.perf_counter() - started
            row["valid"] = False
            row["seconds"] = elapsed
            row["error"] = _serialize_error(error)
            code = "INFERENCE_ERROR"
            error_codes[code] = error_codes.get(code, 0) + 1
            failed += 1
            print(f"ERROR {error} ({elapsed:.1f}s)", flush=True)

        results.append(row)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")

    # --- Summary report ---
    total_evaluated = len(results)
    rescue_rate = rescued / total_evaluated if total_evaluated else 0.0

    # Compare note metrics: rhythm vs beam-only vs grammar
    rhythm_valid_metrics = [r["metrics"] for r in results if r.get("valid") and r.get("metrics")]

    def _avg(rows: list[dict], key: str) -> float | None:
        vals = [r[key] for r in rows if r.get(key) is not None]
        return statistics.mean(vals) if vals else None

    summary = {
        "policy_version": RHYTHM_POLICY_VERSION,
        "policy_id": RHYTHM_POLICY_ID,
        "policy_hash": RHYTHM_POLICY_HASH,
        "evaluated": total_evaluated,
        "rescued": rescued,
        "failed": failed,
        "rescue_rate": rescue_rate,
        "error_breakdown": error_codes,
        "rhythm_note_metrics": {
            "pitch_f1": _avg(rhythm_valid_metrics, "pitch_f1"),
            "onset_f1": _avg(rhythm_valid_metrics, "onset_f1"),
            "onset_duration_f1": _avg(rhythm_valid_metrics, "onset_duration_f1"),
            "mean_offset_error": _avg(rhythm_valid_metrics, "mean_offset_error"),
            "staff_accuracy": _avg(rhythm_valid_metrics, "staff_accuracy"),
            "aligned_voice_accuracy": _avg(rhythm_valid_metrics, "aligned_voice_accuracy"),
        },
        "latency": {
            "median_seconds": statistics.median(r["seconds"] for r in results if "seconds" in r) if results else None,
            "p95_seconds": sorted(r["seconds"] for r in results if "seconds" in r)[int(len(results) * 0.95)] if results else None,
        },
        "comparison": {
            "note": (
                "Rhythm constraint rescued {rescued} of {total} beam-invalid samples "
                "({rate:.1%} rescue rate). Grammar-only rescued {gram_rescued}."
            ).format(
                rescued=rescued,
                total=total_evaluated,
                rate=rescue_rate,
                gram_rescued=sum(
                    1 for sid in failed_samples[:total_evaluated]
                    if grammar_results.get(sid, {}).get("valid")
                ),
            )
        },
    }

    report_path = args.output_dir / "rhythm_experiment_report.json"
    report_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    print("\n=== RHYTHM EXPERIMENT SUMMARY ===", flush=True)
    print(f"Evaluated: {total_evaluated}", flush=True)
    print(f"Rescued:   {rescued} ({rescue_rate:.1%})", flush=True)
    print(f"Failed:    {failed}", flush=True)
    print(f"Errors:    {error_codes}", flush=True)
    if rhythm_valid_metrics:
        print(f"Pitch F1 (avg valid): {_avg(rhythm_valid_metrics, 'pitch_f1'):.4f}", flush=True)
        print(f"Onset-dur F1 (avg):   {_avg(rhythm_valid_metrics, 'onset_duration_f1'):.4f}", flush=True)
    print(f"\nReport: {report_path}", flush=True)
    print(f"Log:    {log_path}", flush=True)

    print(json.dumps({"status": "complete", "policy": RHYTHM_POLICY_VERSION, **summary}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Rhythm experiment cancelled.", file=sys.stderr)
        raise SystemExit(130)
