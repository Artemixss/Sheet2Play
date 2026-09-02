"""Compare OMR engines on the same pages, with real numbers where ground truth exists.

This file used to run SMT only and report counts - spines, notes, barlines - with no ground
truth and no second engine, which is why "SMT is worse than HOMR" was inferred rather than
measured. It now runs any registered engine over the same input and scores them identically.

Two modes:

  scored       --manifest <jsonl>   Rows carrying `image` and `musicxml`, so every engine is
                                    scored against ground truth: onset/pitch F1, OMR-NED, and
                                    span_ratio. OLiMPiC's canary manifest works today; the
                                    Sheet Music Benchmark slots in unchanged once its access
                                    request clears.

  descriptive  --pdf <file>         No labels, so it reports coverage and span-consistency
                                    only. This is the mode for the local PDF library, which
                                    is the material the app actually receives.

`--dpi` accepts a comma-separated sweep. Rendering resolution dominated every earlier SMT
result (7x swing between 200 and 300 DPI), and HOMR's own path hardcodes 300, so a single
number is not a finding - a grid is.

    .venv/Scripts/python.exe compare_engines.py --engine homr \\
        --manifest reports/phase3/olimpic-scanned-canary.jsonl --limit 20
    .venv/Scripts/python.exe compare_engines.py --engine both --pdf score.pdf --dpi 200,300
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "src"))
sys.path.insert(0, str(WORKSPACE / "Bridge"))

from sheet2play_omr.engines import metric_notes_from_bridge, run_bridge_engine  # noqa: E402
from sheet2play_omr.metrics import (  # noqa: E402
    MetricNote,
    calculate_note_metrics,
    span_ratio,
)


@dataclass
class Transcription:
    """One engine's attempt at one image."""

    notes: list[MetricNote] = field(default_factory=list)
    seconds: float = 0.0
    error: str | None = None
    musicxml: Path | None = None
    descriptive: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.error is None and bool(self.notes)


# --- Engines -------------------------------------------------------------------------------
#
# Each engine is a callable taking one image path and returning a Transcription. Keeping the
# interface at "one image in, notes out" is what makes the comparison fair: both engines see
# exactly the same pixels, rendered once.


def transcribe_homr(image: Path) -> Transcription:
    result = run_bridge_engine(image, engine="homr")
    if not result.ok:
        return Transcription(seconds=result.seconds, error=result.error_code)
    try:
        notes = metric_notes_from_bridge(result.payload, stage="homr")
    except Exception as error:  # ResearchError, or a malformed payload
        return Transcription(seconds=result.seconds, error=str(error)[:120])
    return Transcription(notes=notes, seconds=result.seconds)


def transcribe_smt(image: Path) -> Transcription:
    """SMT via the vendored 2024 checkpoint.

    Kept because it is what the original comparison targeted, but note SMT has been
    superseded twice (SMT++ and then LEGATO), so a poor result here is expected rather than
    informative. SMT emits bekern for one system, so the descriptive counts are reported and
    note-level scoring is left empty rather than faked.
    """
    import cv2

    from smt_infer import GRANDSTAFF, SMTTranscriber, kern_stats

    transcriber = _smt_transcriber(GRANDSTAFF)
    crop = cv2.imread(str(image))
    if crop is None:
        return Transcription(error="unreadable image")
    started = time.time()
    try:
        text = transcriber.transcribe(crop)
    except Exception as error:
        return Transcription(seconds=time.time() - started, error=str(error)[:120])
    return Transcription(
        seconds=time.time() - started,
        descriptive=kern_stats(text) if text else {},
    )


_SMT_CACHE: dict[str, Any] = {}


def _smt_transcriber(model: str) -> Any:
    """Load SMT once per process; the checkpoint is expensive to initialise."""
    if model not in _SMT_CACHE:
        from smt_infer import SMTTranscriber

        _SMT_CACHE[model] = SMTTranscriber(model)
    return _SMT_CACHE[model]


ENGINES: dict[str, Callable[[Path], Transcription]] = {
    "homr": transcribe_homr,
    "smt": transcribe_smt,
}


# --- Ground truth --------------------------------------------------------------------------


def ground_truth_notes(musicxml: Path) -> list[MetricNote]:
    """Load labels through the same normalizer the prediction path uses.

    Flag parity matters: bridge.py applies expand_repeats=True / skip_grace_notes=False, so
    ground truth must too, or the two sides of the comparison are normalized differently.
    """
    from fractions import Fraction

    from musicxml_normalizer import normalize_musicxml

    score = normalize_musicxml(musicxml, expand_repeats=True, skip_grace_notes=False)
    return [
        MetricNote(
            pitch=note.midi_pitch,
            onset=Fraction(str(note.start_beat)).limit_denominator(4096),
            duration=Fraction(str(note.duration_beats)).limit_denominator(4096),
            staff=note.staff_index,
            voice=note.voice_identifier,
        )
        for note in score.notes
    ]


def score_transcription(
    transcription: Transcription, expected: list[MetricNote], ground_truth: Path | None
) -> dict[str, Any]:
    row: dict[str, Any] = {"seconds": round(transcription.seconds, 2)}
    if not transcription.ok:
        row["ok"] = False
        row["error"] = transcription.error or "no notes"
        return row
    metrics = asdict(calculate_note_metrics(transcription.notes, expected))
    if metrics["mean_offset_error"] in (float("inf"), float("-inf")):
        metrics["mean_offset_error"] = None
    row["ok"] = True
    row.update(metrics)
    row["span_ratio"] = span_ratio(transcription.notes, expected)
    row["predicted_notes"] = len(transcription.notes)
    row["expected_notes"] = len(expected)

    # OMR-NED needs both sides as files. Only available when the engine wrote MusicXML.
    if transcription.musicxml is not None and ground_truth is not None:
        try:
            from sheet2play_omr.omr_ned import score_pair

            result = score_pair(transcription.musicxml, ground_truth)
            row["omr_ned"] = None if result is None else result.score
        except Exception as error:
            row["omr_ned_error"] = str(error)[:120]
    return row


# --- Modes ---------------------------------------------------------------------------------


def load_manifest(path: Path, limit: int) -> list[dict[str, Any]]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return rows[:limit] if limit else rows


def run_scored(args: argparse.Namespace, engines: list[str]) -> list[dict[str, Any]]:
    samples = load_manifest(args.manifest, args.limit)
    print(f"manifest : {args.manifest} ({len(samples)} samples)")
    print(f"engines  : {', '.join(engines)}\n")

    rows: list[dict[str, Any]] = []
    for index, sample in enumerate(samples, start=1):
        image = Path(sample["image"])
        truth_path = Path(sample["musicxml"]) if sample.get("musicxml") else None
        if truth_path is None or not truth_path.is_file():
            print(f"  [{index}/{len(samples)}] {image.name}: SKIP (no ground truth)")
            continue
        try:
            expected = ground_truth_notes(truth_path)
        except Exception as error:
            print(f"  [{index}/{len(samples)}] {image.name}: GROUND TRUTH FAILED ({error})")
            continue

        row: dict[str, Any] = {"id": sample.get("identifier", image.stem), "engines": {}}
        summary = []
        for engine in engines:
            transcription = ENGINES[engine](image)
            scored = score_transcription(transcription, expected, truth_path)
            row["engines"][engine] = scored
            if scored.get("ok"):
                summary.append(
                    "%s onset=%.3f span=%.2f"
                    % (engine, scored["onset_f1"], scored.get("span_ratio") or float("nan"))
                )
            else:
                summary.append(f"{engine} FAILED({scored.get('error')})")
        rows.append(row)
        print(f"  [{index}/{len(samples)}] {row['id']}: " + " | ".join(summary))
    return rows


def run_descriptive(args: argparse.Namespace, engines: list[str], dpis: list[int]) -> list[dict]:
    """No ground truth: render the PDF at each DPI and report what each engine returns."""
    import slice_systems

    rows: list[dict[str, Any]] = []
    work_dir = args.out / "pages"
    work_dir.mkdir(parents=True, exist_ok=True)

    for dpi in dpis:
        for page in range(args.pages):
            try:
                image = slice_systems.render_pdf_page(args.pdf, page, dpi)
            except Exception as error:
                print(f"dpi {dpi} page {page + 1}: {error}")
                break
            import cv2

            page_path = work_dir / ("p%02d_dpi%d.png" % (page + 1, dpi))
            cv2.imwrite(str(page_path), image)

            for engine in engines:
                transcription = ENGINES[engine](page_path)
                row = {
                    "dpi": dpi,
                    "page": page + 1,
                    "engine": engine,
                    "seconds": round(transcription.seconds, 2),
                    "error": transcription.error,
                    "notes": len(transcription.notes),
                    **transcription.descriptive,
                }
                rows.append(row)
                print(
                    "  dpi %-4d page %-2d %-6s %6.1fs  %4d notes  %s"
                    % (
                        dpi,
                        page + 1,
                        engine,
                        transcription.seconds,
                        len(transcription.notes),
                        transcription.error or "ok",
                    )
                )
    return rows


# --- Reporting -----------------------------------------------------------------------------


def _mean(values: Iterable[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    return statistics.mean(present) if present else None


def print_scored_summary(rows: list[dict[str, Any]], engines: list[str]) -> None:
    print("\n=== scored comparison ===")
    header = "%-8s %5s %9s %9s %11s %10s %9s" % (
        "engine", "n", "pitch_f1", "onset_f1", "onset+dur", "span", "too long")
    print(header)
    for engine in engines:
        scored = [
            row["engines"][engine]
            for row in rows
            if row["engines"].get(engine, {}).get("ok")
        ]
        if not scored:
            print("%-8s %5d %s" % (engine, 0, "no successful runs"))
            continue
        ratios = [row["span_ratio"] for row in scored if row.get("span_ratio") is not None]
        inflated = (
            "%.0f%%" % (100 * sum(1 for r in ratios if r > 1.02) / len(ratios))
            if ratios
            else "-"
        )
        omr_ned = _mean(row.get("omr_ned") for row in scored)
        print(
            "%-8s %5d %9.3f %9.3f %11.3f %10s %9s"
            % (
                engine,
                len(scored),
                _mean(row["pitch_f1"] for row in scored),
                _mean(row["onset_f1"] for row in scored),
                _mean(row["onset_duration_f1"] for row in scored),
                "%.3f" % _mean(ratios) if ratios else "-",
                inflated,
            )
        )
        if omr_ned is not None:
            print("%-8s %5s OMR-NED %.4f (lower is better)" % ("", "", omr_ned))


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--manifest", type=Path,
                        help="JSONL with `image` and `musicxml` per row: scored mode.")
    source.add_argument("--pdf", type=Path, help="Score to transcribe: descriptive mode.")
    parser.add_argument("--engine", default="homr",
                        help="Comma-separated, or 'both'. Available: " + ", ".join(ENGINES))
    parser.add_argument("--pages", type=int, default=1, help="Pages, in --pdf mode.")
    parser.add_argument("--dpi", default="300",
                        help="Comma-separated DPI sweep, in --pdf mode.")
    parser.add_argument("--limit", type=int, default=0, help="Cap samples in --manifest mode.")
    parser.add_argument("--out", type=Path, default=HERE / "reports" / "comparison")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_arguments(argv)

    requested = "homr,smt" if args.engine == "both" else args.engine
    engines = [name.strip() for name in requested.split(",") if name.strip()]
    unknown = [name for name in engines if name not in ENGINES]
    if unknown:
        print(f"Unknown engine(s): {', '.join(unknown)}. Available: {', '.join(ENGINES)}",
              file=sys.stderr)
        return 2

    args.out.mkdir(parents=True, exist_ok=True)

    if args.manifest:
        rows = run_scored(args, engines)
        print_scored_summary(rows, engines)
        report = {"mode": "scored", "manifest": str(args.manifest), "rows": rows}
    else:
        dpis = [int(value) for value in args.dpi.split(",") if value.strip()]
        rows = run_descriptive(args, engines, dpis)
        report = {"mode": "descriptive", "pdf": str(args.pdf), "rows": rows}

    report_path = args.out / "comparison.json"
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print("\nReport: " + str(report_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
