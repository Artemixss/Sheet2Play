"""Locate the HOMR rhythm error before paying for GPU time.

The Phase 3 canary measured HOMR at pitch_f1 0.960 but onset_f1 0.584 on 100 OLiMPiC
scanned systems. That gap is not evenly spread: per-sample onset_f1 is bimodal, the failing
systems keep their pitches, and every clean system is tuplet-free while 47% of the failing
ones contain a tuplet. homr's own post-processing is the obvious suspect - see
_fix_over_eager_tuplets in homr/transformer/vocabulary.py, which strips all tuplets from
any measure shorter than the system median.

This script separates three candidate explanations, cheapest first:

  1. Metric strictness. sheet2play_omr.metrics matches onsets by exact rational equality,
     so a note off by 1/48 of a beat scores zero. Bridge/evaluate_omr.evaluate scores the
     same notes with a tolerance. Comparing them bounds how much of the gap is quantisation
     rather than misreading.
  2. Harness asymmetry. Ground truth was loaded with expand_repeats=False /
     skip_grace_notes=True while predictions came from bridge.py with the opposite flags.
     Ground truth is scored both ways here so the cost of that mismatch is visible.
  3. The tuplet repair itself. Re-running with SHEET2PLAY_HOMR_KEEP_TUPLETS=1 neutralises
     _fix_over_eager_tuplets and nothing else.

Predictions are cached per (sample, variant), so re-scoring is free once a run completes.

    .venv/Scripts/python.exe diagnose_rhythm.py --only-tuplets
    .venv/Scripts/python.exe diagnose_rhythm.py --variants baseline,keep-tuplets
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from dataclasses import asdict
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parent.parent
sys.path.insert(0, str(HERE / "src"))
sys.path.insert(0, str(WORKSPACE / "Bridge"))

from sheet2play_omr.engines import run_bridge_engine  # noqa: E402
from sheet2play_omr.metrics import (  # noqa: E402
    MetricNote,
    calculate_note_metrics,
    span_ratio,
)

HOMR_TIMEOUT_SECONDS = 600
TOLERANCES = (0.0, 1 / 32, 1 / 16, 1 / 8)

# Flag pairs as (expand_repeats, skip_grace_notes).
GROUND_TRUTH_FLAGS = {
    # What phase3_benchmark.load_ground_truth_notes has always used.
    "legacy": (False, True),
    # What Bridge/bridge.py actually applies to predictions, so both sides match.
    "bridge-symmetric": (True, False),
}


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=HERE / "reports" / "phase3" / "olimpic-scanned-canary.jsonl",
        help="JSONL of OlimpicSample rows; defaults to the Phase 3 canary.",
    )
    parser.add_argument(
        "--variants", default="baseline", help="Comma-separated: baseline, keep-tuplets."
    )
    parser.add_argument("--limit", type=int, default=0, help="Cap sample count (0 = all).")
    parser.add_argument(
        "--only-tuplets",
        action="store_true",
        help="Restrict to samples whose ground truth contains a tuplet.",
    )
    parser.add_argument("--out", type=Path, default=HERE / "reports" / "diagnosis")
    parser.add_argument("--rerun", action="store_true", help="Ignore cached predictions.")
    return parser.parse_args(argv)


def load_manifest(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def has_tuplet(musicxml: Path) -> bool:
    return "<time-modification" in musicxml.read_text(encoding="utf-8", errors="replace")


def ground_truth_notes(musicxml: Path, expand_repeats: bool, skip_grace_notes: bool):
    """Ground truth as both metric families, from one normalizer pass."""
    from evaluate_omr import EvaluationNote
    from musicxml_normalizer import normalize_musicxml

    score = normalize_musicxml(
        musicxml, expand_repeats=expand_repeats, skip_grace_notes=skip_grace_notes
    )
    exact = [
        MetricNote(
            pitch=note.midi_pitch,
            onset=Fraction(str(note.start_beat)).limit_denominator(4096),
            duration=Fraction(str(note.duration_beats)).limit_denominator(4096),
            staff=note.staff_index,
            voice=note.voice_identifier,
        )
        for note in score.notes
    ]
    tolerant = [
        EvaluationNote(
            midi_pitch=note.midi_pitch,
            start_beat=note.start_beat,
            duration_beats=note.duration_beats,
        )
        for note in score.notes
    ]
    return exact, tolerant


def predict(sample: dict[str, Any], variant: str, cache_dir: Path, rerun: bool) -> dict[str, Any]:
    """Run bridge.py --engine homr, caching the raw payload per (sample, variant)."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = cache_dir / (sample["identifier"].replace("/", "_") + ".json")
    if cached.is_file() and not rerun:
        return json.loads(cached.read_text(encoding="utf-8"))

    # bridge.py copies os.environ when it launches homr, so this reaches homr_gpu.py.
    extra_env = {"SHEET2PLAY_HOMR_KEEP_TUPLETS": "1"} if variant == "keep-tuplets" else {}
    if variant != "keep-tuplets":
        os.environ.pop("SHEET2PLAY_HOMR_KEEP_TUPLETS", None)

    result = run_bridge_engine(
        sample["image"],
        engine="homr",
        timeout_seconds=HOMR_TIMEOUT_SECONDS,
        extra_env=extra_env,
    )
    if result.ok:
        record: dict[str, Any] = {
            "ok": True,
            "seconds": result.seconds,
            "payload": result.payload,
        }
    else:
        record = {
            "ok": False,
            "error": result.error_code,
            "seconds": result.seconds,
        }
        if result.stderr_tail:
            record["stderr_tail"] = result.stderr_tail
    cached.write_text(json.dumps(record), encoding="utf-8")
    return record


def score(payload: dict[str, Any], truth: dict[str, tuple]) -> dict[str, Any]:
    """Score one prediction: exact metrics per ground-truth flag set, plus a tolerance sweep."""
    from evaluate_omr import EvaluationNote, evaluate

    notes = payload["notes"]
    exact_prediction = [
        MetricNote(
            pitch=int(note["midi_pitch"]),
            onset=Fraction(str(note["start_beat"])).limit_denominator(4096),
            duration=Fraction(str(note["duration_beats"])).limit_denominator(4096),
            staff=int(note["staff_index"]),
            voice=str(note["voice_identifier"]),
        )
        for note in notes
    ]
    tolerant_prediction = [
        EvaluationNote(
            midi_pitch=int(note["midi_pitch"]),
            start_beat=float(note["start_beat"]),
            duration_beats=float(note["duration_beats"]),
        )
        for note in notes
    ]

    result: dict[str, Any] = {"predicted_notes": len(notes), "exact": {}, "tolerance": {}}
    result["span_ratio"] = span_ratio(exact_prediction, truth["bridge-symmetric"][0])
    for flag_name, (exact_truth, _) in truth.items():
        metrics = asdict(calculate_note_metrics(exact_prediction, exact_truth))
        if metrics["mean_offset_error"] in (float("inf"), float("-inf")):
            metrics["mean_offset_error"] = None
        result["exact"][flag_name] = metrics

    # The tolerance sweep uses the bridge-symmetric truth: the like-for-like comparison.
    _, tolerant_truth = truth["bridge-symmetric"]
    for tolerance in TOLERANCES:
        metrics = evaluate(
            tolerant_truth,
            tolerant_prediction,
            onset_tolerance=tolerance,
            duration_tolerance=tolerance,
        )
        result["tolerance"]["%.5f" % tolerance] = asdict(metrics)
    return result


def mean(values: Iterable[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    return statistics.mean(present) if present else None


def main(argv: list[str] | None = None) -> int:
    args = parse_arguments(argv)
    variants = [variant.strip() for variant in args.variants.split(",") if variant.strip()]
    for variant in variants:
        if variant not in ("baseline", "keep-tuplets"):
            print(f"Unknown variant: {variant}", file=sys.stderr)
            return 2

    samples = load_manifest(args.manifest)
    for sample in samples:
        sample["has_tuplet"] = has_tuplet(Path(sample["musicxml"]))
    if args.only_tuplets:
        samples = [sample for sample in samples if sample["has_tuplet"]]
    if args.limit:
        samples = samples[: args.limit]

    tuplet_count = sum(sample["has_tuplet"] for sample in samples)
    print(f"samples  : {len(samples)} ({tuplet_count} with tuplets)")
    print(f"variants : {', '.join(variants)}")
    print("")

    args.out.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []

    for index, sample in enumerate(samples, start=1):
        identifier = sample["identifier"]
        try:
            truth = {
                name: ground_truth_notes(Path(sample["musicxml"]), *flags)
                for name, flags in GROUND_TRUTH_FLAGS.items()
            }
        except Exception as error:
            print(f"  [{index}/{len(samples)}] {identifier}: GROUND TRUTH FAILED ({error})")
            continue

        row: dict[str, Any] = {
            "id": identifier,
            "has_tuplet": sample["has_tuplet"],
            "variants": {},
        }
        for variant in variants:
            record = predict(sample, variant, args.out / "predictions" / variant, args.rerun)
            if not record.get("ok"):
                row["variants"][variant] = {"ok": False, "error": record.get("error")}
                continue
            try:
                scored = score(record["payload"], truth)
                scored["ok"] = True
                scored["seconds"] = record["seconds"]
                row["variants"][variant] = scored
            except Exception as error:
                row["variants"][variant] = {"ok": False, "error": f"SCORING: {error}"}

        rows.append(row)
        summary = []
        for variant in variants:
            entry = row["variants"][variant]
            if entry.get("ok"):
                summary.append(
                    "%s exact=%.3f tol=%.3f"
                    % (
                        variant,
                        entry["exact"]["bridge-symmetric"]["onset_f1"],
                        entry["tolerance"]["%.5f" % 0.125]["onset_f1"],
                    )
                )
            else:
                summary.append(f"{variant} FAILED({entry.get('error')})")
        flag = "T" if sample["has_tuplet"] else " "
        print(f"  [{index}/{len(samples)}] {flag} {identifier}: " + " | ".join(summary))

    report = {"manifest": str(args.manifest), "samples": len(rows), "rows": rows}
    (args.out / "diagnosis.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )

    print_summary(rows, variants)
    print("\nReport: " + str(args.out / "diagnosis.json"))
    return 0


def print_summary(rows: list[dict[str, Any]], variants: list[str]) -> None:
    def valid(variant: str, subset: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            row["variants"][variant]
            for row in subset
            if row["variants"].get(variant, {}).get("ok")
        ]

    groups = [
        ("all", rows),
        ("tuplet", [row for row in rows if row["has_tuplet"]]),
        ("no tuplet", [row for row in rows if not row["has_tuplet"]]),
    ]

    print("\n=== exact-match onset_f1, by ground-truth flags ===")
    print("%-10s %-14s %5s %9s %10s" % ("group", "variant", "n", "legacy", "symmetric"))
    for label, subset in groups:
        for variant in variants:
            entries = valid(variant, subset)
            if not entries:
                continue
            print(
                "%-10s %-14s %5d %9s %10s"
                % (
                    label,
                    variant,
                    len(entries),
                    _format(mean(entry["exact"]["legacy"]["onset_f1"] for entry in entries)),
                    _format(
                        mean(entry["exact"]["bridge-symmetric"]["onset_f1"] for entry in entries)
                    ),
                )
            )

    print("\n=== tolerance sweep (bridge-symmetric truth), onset_f1 ===")
    header = "%-10s %-14s %5s" % ("group", "variant", "n")
    for tolerance in TOLERANCES:
        header += " %9s" % (("+/-%.4g" % tolerance) if tolerance else "exact")
    print(header)
    for label, subset in groups:
        for variant in variants:
            entries = valid(variant, subset)
            if not entries:
                continue
            line = "%-10s %-14s %5d" % (label, variant, len(entries))
            for tolerance in TOLERANCES:
                key = "%.5f" % tolerance
                line += " %9s" % _format(
                    mean(entry["tolerance"][key]["onset_f1"] for entry in entries)
                )
            print(line)

    print("\n=== span ratio: predicted timeline length / ground truth ===")
    print("%-10s %-14s %5s %10s %9s" % ("group", "variant", "n", "mean ratio", "too long"))
    for label, subset in groups:
        for variant in variants:
            entries = valid(variant, subset)
            ratios = [e["span_ratio"] for e in entries if e.get("span_ratio") is not None]
            if not ratios:
                continue
            inflated = sum(1 for r in ratios if r > 1.02) / len(ratios)
            print(
                "%-10s %-14s %5d %10s %8.0f%%"
                % (label, variant, len(ratios), _format(mean(ratios)), 100 * inflated)
            )

    print("\n=== pitch_f1 (sanity: should stay high everywhere) ===")
    print("%-10s %-14s %5s %9s" % ("group", "variant", "n", "pitch_f1"))
    for label, subset in groups:
        for variant in variants:
            entries = valid(variant, subset)
            if not entries:
                continue
            print(
                "%-10s %-14s %5d %9s"
                % (
                    label,
                    variant,
                    len(entries),
                    _format(
                        mean(entry["exact"]["bridge-symmetric"]["pitch_f1"] for entry in entries)
                    ),
                )
            )


def _format(value: float | None) -> str:
    return "-" if value is None else "%.3f" % value


if __name__ == "__main__":
    raise SystemExit(main())
