#!/usr/bin/env python3
"""Score the engine on the user's own library instead of a research corpus.

Every measurement in reports/diagnosis/ runs on OLiMPiC, which is *scanned* sheet music. The
library this app actually plays is engraved MuseScore PDFs, and the two behave differently -
upstream measures tie recovery at 0.93-1.00 recall on engraved input against 0.04-0.12 on
scans. So a canary result predicts app behaviour only loosely, and shipping decisions should
not rest on it alone.

The library has no ground-truth MusicXML, but part of it has something better: a handful of
songs exist both as a MuseScore MIDI the user downloaded and as a PDF the engine transcribed.
For those the MIDI *is* ground truth, on exactly the material the app runs on. This script
scores against it, and falls back to reporting the timeline length change for the rest, which
is still meaningful because the defect being fixed is duration over-accounting: a song that
came out 45% too long and now comes out the right length is the whole point.

    python evaluate_library.py --paired-only     # just the songs with real ground truth
    python evaluate_library.py                   # every PDF; duration only where unpaired
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from fractions import Fraction
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parent.parent
sys.path.insert(0, str(HERE / "src"))

from sheet2play_omr.metrics import (  # noqa: E402
    MetricNote,
    calculate_note_metrics,
    span_ratio,
)

LIBRARY = Path(os.environ.get("LOCALAPPDATA", "")) / "Sheet2Play" / "songs"
VENDOR_HOMR = HERE / "vendor" / "homr"
TIMEOUT_SECONDS = 1800


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--library", type=Path, default=LIBRARY)
    parser.add_argument(
        "--paired-only",
        action="store_true",
        help="Only songs that have a MuseScore MIDI to score against.",
    )
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--out", type=Path, default=HERE / "reports" / "library")
    return parser.parse_args(argv)


def notes_from_midi(path: Path) -> list[MetricNote]:
    """Note events in quarter-length units, which is what MetricNote compares in."""
    from music21 import converter

    score = converter.parse(str(path))
    notes: list[MetricNote] = []
    for element in score.flatten().notes:
        onset = Fraction(element.offset).limit_denominator(4096)
        duration = Fraction(element.duration.quarterLength).limit_denominator(4096)
        for pitch in getattr(element, "pitches", []):
            notes.append(
                MetricNote(
                    pitch=pitch.midi, onset=onset, duration=duration, staff=0, voice="1"
                )
            )
    return notes


def run_engine(pdf: Path, patched: bool) -> dict[str, Any]:
    """Transcribe one PDF through bridge.py, optionally with the patched clone in front.

    PYTHONPATH rather than installing: the wheel in Bridge/.venv-homr-gpu stays exactly as the
    app has it, so nothing here can change what the user launches.
    """
    environment = {**os.environ, "PYTHONUNBUFFERED": "1"}
    if patched:
        environment["PYTHONPATH"] = str(VENDOR_HOMR)
    else:
        environment.pop("PYTHONPATH", None)

    started = time.perf_counter()
    completed = subprocess.run(
        [sys.executable, str(WORKSPACE / "Bridge" / "bridge.py"), "--engine", "homr", str(pdf)],
        cwd=WORKSPACE / "Bridge",
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
        timeout=TIMEOUT_SECONDS,
    )
    seconds = time.perf_counter() - started
    payload = None
    for line in reversed(completed.stdout.splitlines()):
        if line.startswith("{"):
            try:
                payload = json.loads(line)
                break
            except json.JSONDecodeError:
                continue
    if payload is None:
        tail = (completed.stderr or completed.stdout or "").strip().splitlines()[-3:]
        return {"ok": False, "error": " / ".join(tail) or "no JSON payload", "seconds": seconds}
    return {"ok": True, "payload": payload, "seconds": seconds}


def notes_from_payload(payload: dict[str, Any]) -> list[MetricNote]:
    return [
        MetricNote(
            pitch=note["midi_pitch"],
            onset=Fraction(str(note["start_beat"])).limit_denominator(4096),
            duration=Fraction(str(note["duration_beats"])).limit_denominator(4096),
            staff=note.get("staff_index", 0),
            voice=str(note.get("voice_identifier", "1")),
        )
        for note in payload.get("notes", [])
    ]


def timeline_seconds(payload: dict[str, Any]) -> float:
    notes = payload.get("notes", [])
    if not notes:
        return 0.0
    return max(n["start_seconds"] + n["duration_seconds"] for n in notes)


def score_song(pdf: Path, truth_midi: Path | None) -> dict[str, Any]:
    row: dict[str, Any] = {"song": pdf.stem, "paired": truth_midi is not None}
    for label, patched in (("baseline", False), ("patched", True)):
        result = run_engine(pdf, patched)
        if not result["ok"]:
            row[label] = {"ok": False, "error": result["error"]}
            continue
        payload = result["payload"]
        entry: dict[str, Any] = {
            "ok": True,
            "notes": len(payload.get("notes", [])),
            "seconds": round(timeline_seconds(payload), 2),
            "runtime": round(result["seconds"], 1),
        }
        if truth_midi is not None:
            expected = notes_from_midi(truth_midi)
            predicted = notes_from_payload(payload)
            metrics = calculate_note_metrics(predicted, expected)
            entry.update(
                {
                    "pitch_f1": round(metrics.pitch_f1, 4),
                    "onset_f1": round(metrics.onset_f1, 4),
                    "span_ratio": span_ratio(predicted, expected),
                }
            )
        row[label] = entry
    return row


def main(argv: list[str] | None = None) -> int:
    args = parse_arguments(argv)
    args.out.mkdir(parents=True, exist_ok=True)

    pdf_directory = args.library / "pdf"
    custom_directory = args.library / "midi" / "custom"
    if not pdf_directory.is_dir():
        print(f"No PDFs at {pdf_directory}", file=sys.stderr)
        return 2

    songs: list[tuple[Path, Path | None]] = []
    for pdf in sorted(pdf_directory.glob("*.pdf")):
        truth = custom_directory / (pdf.stem + ".mid")
        paired = truth if truth.is_file() else None
        if args.paired_only and paired is None:
            continue
        songs.append((pdf, paired))
    if args.limit:
        songs = songs[: args.limit]

    print(f"{len(songs)} songs ({sum(1 for _, t in songs if t)} with ground truth)\n")
    rows = []
    for index, (pdf, truth) in enumerate(songs, start=1):
        print(f"[{index}/{len(songs)}] {pdf.stem[:60]}", flush=True)
        row = score_song(pdf, truth)
        rows.append(row)
        base, patch = row.get("baseline", {}), row.get("patched", {})
        if base.get("ok") and patch.get("ok"):
            if row["paired"]:
                print(
                    f"    onset_f1 {base['onset_f1']:.3f} -> {patch['onset_f1']:.3f}   "
                    f"span {base['span_ratio']:.2f} -> {patch['span_ratio']:.2f}",
                    flush=True,
                )
            else:
                print(
                    f"    length {base['seconds'] / 60:.1f}m -> {patch['seconds'] / 60:.1f}m",
                    flush=True,
                )
        else:
            print(f"    failed: {base.get('error') or patch.get('error')}", flush=True)
        (args.out / "library.json").write_text(
            json.dumps(rows, indent=2), encoding="utf-8"
        )

    paired = [r for r in rows if r["paired"] and r["baseline"].get("ok") and r["patched"].get("ok")]
    if paired:
        mean = lambda values: sum(values) / len(values)  # noqa: E731
        print("\n=== songs with MuseScore ground truth ===")
        print(f"  onset_f1  {mean([r['baseline']['onset_f1'] for r in paired]):.4f}"
              f" -> {mean([r['patched']['onset_f1'] for r in paired]):.4f}")
        print(f"  span      {mean([r['baseline']['span_ratio'] for r in paired]):.3f}"
              f" -> {mean([r['patched']['span_ratio'] for r in paired]):.3f}   (1.00 is correct)")
    print(f"\nwrote {args.out / 'library.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
