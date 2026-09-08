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
import hashlib
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
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "src"))

from library_pairs import DEFAULT_PAIRS, load_pairs, truth_for  # noqa: E402
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
    parser.add_argument(
        "--pairs",
        type=Path,
        default=DEFAULT_PAIRS,
        help="Reviewed PDF-to-reference pairing. Falls back to filename equality if absent.",
    )
    parser.add_argument(
        "--songs",
        default="",
        help="Comma-separated substrings; only PDFs matching one of them are run.",
    )
    parser.add_argument(
        "--rerun",
        action="store_true",
        help="Ignore cached payloads and re-transcribe every song.",
    )
    parser.add_argument(
        "--variants",
        default="baseline,patched",
        help="Which engines to run. 'patched' alone halves the runtime when only the "
        "shipped engine's output is wanted.",
    )
    return parser.parse_args(argv)


def source_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


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


def run_engine(
    pdf: Path, patched: bool, cache_dir: Path | None = None, rerun: bool = False
) -> dict[str, Any]:
    """Transcribe one PDF through bridge.py, optionally with the patched clone in front.

    PYTHONPATH rather than installing: the wheel in Bridge/.venv-homr-gpu stays exactly as the
    app has it, so nothing here can change what the user launches.

    The payload is cached per (song, variant) and keyed on the source hash, the same way
    diagnose_rhythm.py caches the canary. A full paired run costs about twelve minutes of GPU,
    and every question asked of these predictions afterwards - drift curves, offset sweeps,
    a different ground truth - would otherwise pay that again. Failures are not cached, so a
    transient error does not freeze into the report.
    """
    variant = "patched" if patched else "baseline"
    cached: Path | None = None
    digest = source_digest(pdf)
    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cached = cache_dir / f"{pdf.stem}.{variant}.json"
        if cached.is_file() and not rerun:
            record = json.loads(cached.read_text(encoding="utf-8"))
            if record.get("source_sha256") == digest:
                record["cached"] = True
                return record

    # musicxml_normalizer prints one "[page] decoded=... advance=..." line per page under this
    # flag. It is the only way to learn where each page landed on the combined timeline, which is
    # what tells a drift jump at a page boundary apart from one in the middle of a page.
    environment = {**os.environ, "PYTHONUNBUFFERED": "1", "SHEET2PLAY_PAGE_DEBUG": "1"}
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

    record = {
        "ok": True,
        "payload": payload,
        "seconds": seconds,
        "source_sha256": digest,
        "variant": variant,
        "song": pdf.stem,
        "pages": parse_page_debug(completed.stderr or ""),
    }
    if cached is not None:
        cached.write_text(json.dumps(record), encoding="utf-8")
    return record


def parse_page_debug(stderr: str) -> list[dict[str, float]]:
    """Per-page decoded length and advance, from the normalizer's SHEET2PLAY_PAGE_DEBUG output."""
    pages: list[dict[str, float]] = []
    offset = 0.0
    for line in stderr.splitlines():
        if not line.startswith("[page]"):
            continue
        fields = dict(
            part.split("=", 1) for part in line[len("[page]") :].split() if "=" in part
        )
        try:
            entry = {name: float(value) for name, value in fields.items()}
        except ValueError:
            continue
        entry["offset"] = offset
        offset += entry.get("advance", 0.0)
        pages.append(entry)
    return pages


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


def score_song(
    pdf: Path,
    truth_midi: Path | None,
    cache_dir: Path | None = None,
    rerun: bool = False,
    variants: tuple[str, ...] = ("baseline", "patched"),
) -> dict[str, Any]:
    row: dict[str, Any] = {"song": pdf.stem, "paired": truth_midi is not None}
    for label, patched in (("baseline", False), ("patched", True)):
        if label not in variants:
            continue
        result = run_engine(pdf, patched, cache_dir, rerun)
        if not result["ok"]:
            row[label] = {"ok": False, "error": result["error"]}
            continue
        payload = result["payload"]
        entry: dict[str, Any] = {
            "ok": True,
            "notes": len(payload.get("notes", [])),
            "seconds": round(timeline_seconds(payload), 2),
            "runtime": round(result["seconds"], 1),
            "cached": bool(result.get("cached")),
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
    variants = tuple(part.strip() for part in args.variants.split(",") if part.strip())

    pdf_directory = args.library / "pdf"
    custom_directory = args.library / "midi" / "custom"
    if not pdf_directory.is_dir():
        print(f"No PDFs at {pdf_directory}", file=sys.stderr)
        return 2

    pairs = load_pairs(args.pairs)
    wanted = [part.strip().lower() for part in args.songs.split(",") if part.strip()]

    songs: list[tuple[Path, Path | None, str]] = []
    for pdf in sorted(pdf_directory.glob("*.pdf")):
        if wanted and not any(part in pdf.stem.lower() for part in wanted):
            continue
        paired, status = truth_for(pdf.stem, args.library, pairs)
        if args.paired_only and paired is None:
            continue
        songs.append((pdf, paired, status))
    if args.limit:
        songs = songs[: args.limit]

    print(f"{len(songs)} songs ({sum(1 for _, truth, _ in songs if truth)} with ground truth)")
    print(f"pairing: {args.pairs if pairs else 'filename equality (no pairs file)'}\n")
    rows = []
    for index, (pdf, truth, status) in enumerate(songs, start=1):
        print(f"[{index}/{len(songs)}] {pdf.stem[:60]}", flush=True)
        row = score_song(pdf, truth, args.out / "predictions", args.rerun, variants)
        row["pair_status"] = status
        rows.append(row)
        base, patch = row.get("baseline", {}), row.get("patched", {})
        if len(variants) == 1:
            only = row.get(variants[0], {})
            if only.get("ok"):
                summary = (
                    f"    onset_f1 {only['onset_f1']:.3f}   span {only['span_ratio']:.2f}"
                    if row["paired"]
                    else f"    length {only['seconds'] / 60:.1f}m"
                )
                print(summary + ("   (cached)" if only.get("cached") else ""), flush=True)
            else:
                print(f"    failed: {only.get('error')}", flush=True)
        elif base.get("ok") and patch.get("ok"):
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

    paired = [
        r
        for r in rows
        if r["paired"] and all(r.get(variant, {}).get("ok") for variant in variants)
    ]
    if paired and len(variants) > 1:
        mean = lambda values: sum(values) / len(values)  # noqa: E731
        print("\n=== songs with MuseScore ground truth ===")
        print(f"  onset_f1  {mean([r['baseline']['onset_f1'] for r in paired]):.4f}"
              f" -> {mean([r['patched']['onset_f1'] for r in paired]):.4f}")
        print(f"  span      {mean([r['baseline']['span_ratio'] for r in paired]):.3f}"
              f" -> {mean([r['patched']['span_ratio'] for r in paired]):.3f}   (1.00 is correct)")
    elif paired:
        mean = lambda values: sum(values) / len(values)  # noqa: E731
        variant = variants[0]
        # Confirmed and candidate pairs are summarised apart on purpose. A candidate reference has
        # not been shown to be the same arrangement as the PDF, and averaging it into the headline
        # is how an unverified pairing becomes a quoted number.
        for status in ("confirmed", "candidate", "filename-match"):
            group = [r for r in paired if r.get("pair_status") == status]
            if not group:
                continue
            print(f"\n=== {status} pairs ({len(group)} songs, {variant}) ===")
            print(f"  onset_f1  {mean([r[variant]['onset_f1'] for r in group]):.4f}")
            print(f"  span      {mean([r[variant]['span_ratio'] for r in group]):.3f}"
                  "   (1.00 is correct)")
    print(f"\nwrote {args.out / 'library.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
