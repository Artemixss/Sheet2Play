#!/usr/bin/env python3
"""Measure the ceiling a HOMR fine-tune could reach, without training anything.

The rhythm diagnosis (reports/diagnosis/FINDINGS.md) concluded that HOMR's timing failures are
recognition errors rather than representation errors - the vocabulary can express the passages
it gets wrong, and the model simply does not emit that structure. That conclusion decides
whether fine-tuning is worth days of GPU time, and until now it rested on reading a handful of
token streams by hand.

This tests it directly and cheaply. It takes ground-truth MusicXML, encodes it into homr's
token vocabulary, decodes it straight back out, and scores the result against the original
using the same metrics applied to real predictions. No model is involved, so what comes back
is the best score any perfectly trained model could achieve:

    MusicXML(truth) --music_xml_file_to_tokens--> tokens --generate_xml--> MusicXML(rebuilt)

The number answers a question the loss curve cannot:

  * A high ceiling means the vocabulary is not the blocker, the gap to today's 0.58 is
    learnable, and the fine-tune is worth starting.
  * A low ceiling means no amount of training helps, because the target itself is out of
    reach - and worse, the labels are wrong in exactly the places the model already fails.

That second point is why the encoder matters beyond this test. `music_xml_file_to_tokens` is
the same function `convert_pdmx.py` uses to build training labels, so whatever it cannot
encode is not merely undecodable at inference; it is actively taught wrong.

    python roundtrip_oracle.py                  # the 100-sample OLiMPiC canary
    python roundtrip_oracle.py --polyrhythm     # the constructed cases
    python roundtrip_oracle.py --both
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parent.parent
sys.path.insert(0, str(HERE / "src"))
sys.path.insert(0, str(WORKSPACE / "Bridge"))
# The vendored clone, not the installed wheel: the wheel is inference-only and ships no
# training tree, and the clone is what the fine-tune will actually run.
sys.path.insert(0, str(HERE / "vendor" / "homr"))

from sheet2play_omr.metrics import (  # noqa: E402
    MetricNote,
    calculate_note_metrics,
    span_ratio,
)

# Matches Bridge/bridge.py, so the ceiling is directly comparable to the measured HOMR scores.
EXPAND_REPEATS = True
SKIP_GRACE_NOTES = False


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=HERE / "reports" / "phase3" / "olimpic-scanned-canary.jsonl",
        help="JSONL with a 'musicxml' key per row; defaults to the Phase 3 canary.",
    )
    parser.add_argument(
        "--polyrhythm",
        action="store_true",
        help="Score data/polyrhythm/*.musicxml instead of the canary.",
    )
    parser.add_argument("--both", action="store_true", help="Score both corpora.")
    parser.add_argument("--limit", type=int, default=0, help="Cap sample count (0 = all).")
    parser.add_argument("--out", type=Path, default=HERE / "reports" / "diagnosis")
    parser.add_argument(
        "--keep-xml",
        action="store_true",
        help="Keep each rebuilt MusicXML beside the report for inspection.",
    )
    return parser.parse_args(argv)


def roundtrip(musicxml: Path) -> str:
    """Encode to homr tokens and decode straight back, returning the rebuilt MusicXML."""
    from homr.music_xml_generator import XmlGeneratorArguments, generate_xml
    from training.omr_datasets.music_xml_parser import music_xml_file_to_tokens

    parts = music_xml_file_to_tokens(str(musicxml))
    # The encoder nests parts -> measures -> symbols, while generate_xml wants one flat symbol
    # list per staff; the upper/lower position tokens carry the grand staff split.
    symbols = [symbol for part in parts for measure in part for symbol in measure]
    if not symbols:
        raise ValueError("encoder produced no symbols")
    xml = generate_xml(XmlGeneratorArguments(None, None, None), [symbols], "")
    return ET.tostring(xml, encoding="unicode")


def notes_of(musicxml: Path) -> list[MetricNote]:
    """Note list via the same normalizer both sides of the comparison go through."""
    from musicxml_normalizer import normalize_musicxml

    score = normalize_musicxml(
        musicxml, expand_repeats=EXPAND_REPEATS, skip_grace_notes=SKIP_GRACE_NOTES
    )
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


def has_tuplet(musicxml: Path) -> bool:
    return "<time-modification" in musicxml.read_text(encoding="utf-8", errors="replace")


def score_sample(identifier: str, musicxml: Path, scratch: Path) -> dict[str, Any]:
    row: dict[str, Any] = {"identifier": identifier, "has_tuplet": has_tuplet(musicxml)}
    try:
        rebuilt_xml = roundtrip(musicxml)
    except Exception as error:  # noqa: BLE001 - one bad sample must not stop the sweep
        row["error"] = f"encode/decode: {type(error).__name__}: {error}"
        return row

    rebuilt_path = scratch / (identifier.replace("/", "_") + ".rebuilt.musicxml")
    rebuilt_path.write_text(rebuilt_xml, encoding="utf-8")
    try:
        expected = notes_of(musicxml)
        predicted = notes_of(rebuilt_path)
    except Exception as error:  # noqa: BLE001
        row["error"] = f"normalize: {type(error).__name__}: {error}"
        return row

    metrics = calculate_note_metrics(predicted, expected)
    row.update(
        {
            "expected_notes": len(expected),
            "rebuilt_notes": len(predicted),
            "pitch_f1": round(metrics.pitch_f1, 4),
            "onset_f1": round(metrics.onset_f1, 4),
            "onset_duration_f1": round(metrics.onset_duration_f1, 4),
            "span_ratio": span_ratio(predicted, expected),
            "rebuilt_xml": str(rebuilt_path),
        }
    )
    return row


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [row for row in rows if "onset_f1" in row]
    lossless = [row for row in scored if row["onset_f1"] >= 0.9999]
    return {
        "samples": len(rows),
        "scored": len(scored),
        "failed": len(rows) - len(scored),
        "pitch_f1": round(mean([row["pitch_f1"] for row in scored]), 4),
        "onset_f1": round(mean([row["onset_f1"] for row in scored]), 4),
        "onset_duration_f1": round(mean([row["onset_duration_f1"] for row in scored]), 4),
        "lossless": len(lossless),
        "lossless_fraction": round(len(lossless) / len(scored), 4) if scored else 0.0,
    }


def run_corpus(
    name: str, samples: list[tuple[str, Path]], out: Path, keep_xml: bool
) -> dict[str, Any]:
    scratch = out / f"roundtrip_{name}"
    scratch.mkdir(parents=True, exist_ok=True)

    rows = []
    for index, (identifier, musicxml) in enumerate(samples, start=1):
        row = score_sample(identifier, musicxml, scratch)
        rows.append(row)
        state = row.get("error") or f"onset_f1 {row['onset_f1']:.3f}"
        print(f"[{index}/{len(samples)}] {identifier}: {state}", flush=True)
        if not keep_xml and "rebuilt_xml" in row:
            Path(row.pop("rebuilt_xml")).unlink(missing_ok=True)

    if not keep_xml:
        try:
            scratch.rmdir()
        except OSError:
            pass
    return {"corpus": name, "summary": summarize(rows), "samples": rows}


def print_report(result: dict[str, Any]) -> None:
    summary = result["summary"]
    rows = result["samples"]
    print(f"\n===== {result['corpus']} =====")
    print(
        f"  samples            {summary['samples']}  "
        f"(scored {summary['scored']}, failed {summary['failed']})"
    )
    print(f"  pitch_f1           {summary['pitch_f1']:.4f}")
    print(f"  onset_f1           {summary['onset_f1']:.4f}   <- the ceiling")
    print(f"  onset_duration_f1  {summary['onset_duration_f1']:.4f}")
    print(
        f"  lossless samples   {summary['lossless']}/{summary['scored']} "
        f"({summary['lossless_fraction']:.0%})"
    )

    scored = [row for row in rows if "onset_f1" in row]
    for label, subset in (
        ("tuplet", [row for row in scored if row["has_tuplet"]]),
        ("no tuplet", [row for row in scored if not row["has_tuplet"]]),
    ):
        if subset:
            print(
                f"  {label:<18} n={len(subset):<4} "
                f"onset_f1 {mean([row['onset_f1'] for row in subset]):.4f}"
            )

    worst = sorted(scored, key=lambda row: row["onset_f1"])[:8]
    if worst and worst[0]["onset_f1"] < 0.9999:
        print("  worst samples:")
        for row in worst:
            print(
                f"    {row['identifier']:<28} onset_f1 {row['onset_f1']:.3f}  "
                f"span {row['span_ratio']}  "
                f"notes {row['rebuilt_notes']}/{row['expected_notes']}"
            )
    for row in rows:
        if "error" in row:
            print(f"    FAILED {row['identifier']}: {row['error']}")


def main(argv: list[str] | None = None) -> int:
    args = parse_arguments(argv)
    args.out.mkdir(parents=True, exist_ok=True)

    corpora: list[tuple[str, list[tuple[str, Path]]]] = []
    if not args.polyrhythm or args.both:
        manifest_rows = [
            json.loads(line)
            for line in args.manifest.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        corpora.append(
            ("olimpic", [(row["identifier"], Path(row["musicxml"])) for row in manifest_rows])
        )
    if args.polyrhythm or args.both:
        directory = HERE / "data" / "polyrhythm"
        corpora.append(
            ("polyrhythm", [(f.stem, f) for f in sorted(directory.glob("*.musicxml"))])
        )

    results = []
    for name, samples in corpora:
        if args.limit:
            samples = samples[: args.limit]
        results.append(run_corpus(name, samples, args.out, args.keep_xml))

    for result in results:
        print_report(result)

    report = args.out / "roundtrip_oracle.json"
    report.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nwrote {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
