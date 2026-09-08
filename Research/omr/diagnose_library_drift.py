#!/usr/bin/env python3
"""Decide whether the library's onset failure is displacement or genuine scatter.

`evaluate_library.py` reports an onset F1 that falls off a cliff with page count - 0.904 at two
pages, 0.028 at eleven - while pitch stays high and the timeline stays the right length. The
standing reading is that errors accumulate per measure inside the pages. That reading fits the
numbers, but it is not the only one that does, because of how the metric works:

`calculate_note_metrics` matches onsets as a multiset intersection of (pitch, onset) with exact
rational equality, onsets measured absolutely from the start of the score. There is no alignment
step and no tolerance. So a transcription that is musically correct but *displaced* - by a pickup
bar, by a repeat the reference plays and the printed page does not, by one page landing a beat
early - scores near zero while span_ratio stays at 1.00 and pitch_f1 stays high. Displacement and
chaos are indistinguishable in that one number.

This separates them, and needs no ground truth beyond what is already on disk:

1. **Reference sanity.** Note counts, pitch agreement and span, per song. Where the reference
   disagrees about which notes exist, the onset number is not an engine result at all, and the
   song should leave the sample rather than be explained.

2. **Global offset sweep.** The best single shift and the onset F1 it buys. Candidates are the
   exact differences between same-pitch predicted and truth onsets, so the search finds the true
   optimum rather than the best point on some arbitrary grid. A large gain at a non-zero shift
   means the transcription is right and the reference is offset - a measurement bug, not an
   engine bug.

3. **Local offset curve.** The same mode-of-differences estimate per window of the predicted
   timeline. Its shape is the diagnosis: flat and non-zero is a constant offset, a staircase is
   per-page jumps, a steady ramp is the per-measure accumulation the notes assume, and no
   consistent mode anywhere is genuine local scatter.

4. **Recoverable onset F1.** Onset F1 after shifting each window by its own local offset. This is
   the headline: how much of the gap is displacement that correct alignment would recover,
   against how much is the engine putting notes in genuinely wrong places.

Reads the payload cache `evaluate_library.py` writes, so it costs no GPU:

    python evaluate_library.py --paired-only --variants patched   # once, ~12 minutes
    python diagnose_library_drift.py                              # free, repeatable
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable, Sequence

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "src"))
sys.path.insert(0, str(WORKSPACE / "Bridge"))

from evaluate_library import notes_from_midi, notes_from_payload  # noqa: E402
from library_pairs import DEFAULT_PAIRS, load_pairs, truth_for  # noqa: E402
from sheet2play_omr.metrics import (  # noqa: E402
    MetricNote,
    calculate_note_metrics,
    span_ratio,
    timeline_span,
)

LIBRARY = Path(os.environ.get("LOCALAPPDATA", "")) / "Sheet2Play" / "songs"

# What bridge.py itself applies, so both sides of the comparison are loaded the same way. An
# earlier revision of the canary loaded truth with the opposite flags; the asymmetry was small
# here but would silently corrupt any corpus where repeats or grace notes are common.
BRIDGE_SYMMETRIC_FLAGS = {"expand_repeats": True, "skip_grace_notes": False}

# A shift wider than this stops being an alignment error and becomes a different piece of music.
# Sixty-four quarters is sixteen bars of 4/4, comfortably past any pickup, intro or single repeat.
MAX_SHIFT = Fraction(64)

# Below this many agreeing pairs a window's modal difference is noise rather than an offset, and
# correcting by it would manufacture matches instead of measuring them.
MIN_SUPPORT = 4


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--source",
        choices=("library", "olimpic", "oracle"),
        default="library",
        help="library: the user's PDFs against MuseScore references. "
        "olimpic: the canary's single systems against their exact MusicXML. "
        "oracle: the round-trip oracle's rebuilt MusicXML against the same truth, so the "
        "representation ceiling is corrected the same way homr's score is.",
    )
    parser.add_argument("--library", type=Path, default=LIBRARY)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=HERE / "reports" / "phase3" / "olimpic-scanned-canary.jsonl",
        help="OLiMPiC sample manifest, for --source olimpic.",
    )
    parser.add_argument(
        "--predictions",
        type=Path,
        default=None,
        help="Payload cache. Defaults to reports/library/predictions for the library source "
        "and reports/diagnosis/predictions/<variant> for the OLiMPiC one.",
    )
    parser.add_argument("--variant", default="patched")
    parser.add_argument(
        "--window",
        type=float,
        default=16.0,
        help="Window length in quarter notes for the local offset curve (16 = four bars of 4/4).",
    )
    parser.add_argument(
        "--pairs",
        type=Path,
        default=DEFAULT_PAIRS,
        help="Reviewed PDF-to-reference pairing. Falls back to filename equality if absent.",
    )
    parser.add_argument("--out", type=Path, default=None)
    arguments = parser.parse_args(argv)
    defaults = {
        "library": (
            HERE / "reports" / "library" / "predictions",
            HERE / "reports" / "library" / "drift.json",
        ),
        "olimpic": (
            HERE / "reports" / "diagnosis" / "predictions" / arguments.variant,
            HERE / "reports" / "diagnosis" / "drift-canary.json",
        ),
        "oracle": (
            HERE / "reports" / "diagnosis" / "oracle-corrected" / "roundtrip_olimpic",
            HERE / "reports" / "diagnosis" / "drift-oracle.json",
        ),
    }
    predictions, out = defaults[arguments.source]
    if arguments.predictions is None:
        arguments.predictions = predictions
    if arguments.out is None:
        arguments.out = out
    return arguments


def shift_notes(notes: Iterable[MetricNote], delta: Fraction) -> list[MetricNote]:
    if delta == 0:
        return list(notes)
    return [
        MetricNote(
            pitch=note.pitch,
            onset=note.onset + delta,
            duration=note.duration,
            staff=note.staff,
            voice=note.voice,
        )
        for note in notes
    ]


def difference_histogram(
    predicted: Sequence[MetricNote],
    expected: Sequence[MetricNote],
    max_shift: Fraction = MAX_SHIFT,
) -> Counter:
    """How often each exact shift would line a predicted note up with a truth note of that pitch.

    Exact Fractions rather than a quantised grid, on purpose: a real displacement reproduces the
    *same* difference over and over, so the mode is sharp and needs no tolerance. A grid would
    blur genuine offsets into neighbouring bins and invent agreement between notes that merely
    land near each other.
    """
    expected_by_pitch: dict[int, list[Fraction]] = {}
    for note in expected:
        expected_by_pitch.setdefault(note.pitch, []).append(note.onset)

    histogram: Counter = Counter()
    for note in predicted:
        for onset in expected_by_pitch.get(note.pitch, ()):
            difference = onset - note.onset
            if -max_shift <= difference <= max_shift:
                histogram[difference] += 1
    return histogram


def modal_offset(
    predicted: Sequence[MetricNote],
    expected: Sequence[MetricNote],
    minimum_support: int = MIN_SUPPORT,
) -> tuple[Fraction, int]:
    """The most-agreed shift and how many note pairs agree on it; zero when too few do."""
    histogram = difference_histogram(predicted, expected)
    if not histogram:
        return Fraction(0), 0
    # Ties break towards the smaller shift: on equal evidence the smaller displacement is the more
    # plausible reading, and it keeps the answer stable across reruns.
    delta, support = min(histogram.items(), key=lambda item: (-item[1], abs(item[0]), item[0]))
    if support < minimum_support:
        return Fraction(0), support
    return delta, support


def best_global_offset(
    predicted: Sequence[MetricNote], expected: Sequence[MetricNote], candidates: int = 12
) -> dict[str, Any]:
    """Score the strongest candidate shifts through the real metric and report the best.

    The modal difference is only a hint - it counts pairs, while onset F1 counts matched notes
    under a multiset intersection, so the two can disagree. The top candidates are therefore
    re-scored properly rather than trusted.
    """
    histogram = difference_histogram(predicted, expected)
    ranked = sorted(histogram.items(), key=lambda item: (-item[1], abs(item[0])))[:candidates]
    tested = {Fraction(0)} | {delta for delta, _ in ranked}

    scored = []
    for delta in sorted(tested):
        onset_f1 = calculate_note_metrics(shift_notes(predicted, delta), expected).onset_f1
        scored.append((delta, onset_f1))
    baseline = next(value for delta, value in scored if delta == 0)
    best_delta, best_f1 = max(scored, key=lambda item: (item[1], -abs(item[0])))
    return {
        "delta": float(best_delta),
        "onset_f1": round(best_f1, 4),
        "onset_f1_at_zero": round(baseline, 4),
        "gain": round(best_f1 - baseline, 4),
        "tested": [(float(delta), round(value, 4)) for delta, value in scored],
    }


def local_offsets(
    predicted: Sequence[MetricNote],
    expected: Sequence[MetricNote],
    window: Fraction,
    max_shift: Fraction = MAX_SHIFT,
) -> list[dict[str, Any]]:
    """The modal offset per window of the *predicted* timeline.

    Windowing the prediction rather than the truth is what makes the result usable as a
    correction: every predicted note falls in exactly one window, so applying each window's offset
    is unambiguous. Windowing the truth instead would leave predicted notes that match nothing
    with no window to belong to.
    """
    if not predicted:
        return []
    span = timeline_span(predicted)
    windows: list[dict[str, Any]] = []
    start = Fraction(0)
    while start <= span:
        end = start + window
        inside = [note for note in predicted if start <= note.onset < end]
        if inside:
            nearby = [
                note for note in expected if start - max_shift <= note.onset <= end + max_shift
            ]
            delta, support = modal_offset(inside, nearby)
        else:
            delta, support = Fraction(0), 0
        windows.append(
            {
                "start": float(start),
                "notes": len(inside),
                "delta": float(delta),
                "support": support,
            }
        )
        start = end
    return windows


def apply_local_offsets(
    predicted: Sequence[MetricNote], windows: Sequence[dict[str, Any]], window: Fraction
) -> list[MetricNote]:
    """Shift every predicted note by the offset of the window it sits in.

    A note displaced far enough to cross a window boundary is indexed into its neighbour and
    corrected by the wrong offset, so the recovered score understates what alignment could
    reach. That is the safe direction: it cannot manufacture evidence that the failure is
    displacement rather than the engine.
    """
    corrected: list[MetricNote] = []
    for note in predicted:
        index = int(note.onset // window)
        delta = Fraction(0)
        if 0 <= index < len(windows):
            delta = Fraction(windows[index]["delta"]).limit_denominator(4096)
        corrected.append(
            MetricNote(
                pitch=note.pitch,
                onset=note.onset + delta,
                duration=note.duration,
                staff=note.staff,
                voice=note.voice,
            )
        )
    return corrected


def classify(windows: Sequence[dict[str, Any]], global_offset: dict[str, Any]) -> str:
    """Name the shape of the drift, which is what decides where the next fix belongs."""
    supported = [entry for entry in windows if entry["support"] >= MIN_SUPPORT and entry["notes"]]
    if len(supported) < 2:
        return "scatter (no window has a consistent offset)"

    deltas = [entry["delta"] for entry in supported]
    if global_offset["gain"] >= 0.10 and global_offset["delta"] != 0:
        return "global offset (one shift recovers the score)"
    if max(deltas) - min(deltas) <= 0.25:
        return "flat (offset constant across the score)"

    increasing = sum(1 for earlier, later in zip(deltas, deltas[1:]) if later > earlier + 0.01)
    decreasing = sum(1 for earlier, later in zip(deltas, deltas[1:]) if later < earlier - 0.01)
    changes = increasing + decreasing
    # Steps before ramp, because a single jump is one-directional too and would otherwise be
    # reported as accumulation. Accumulation has to show up as a change in most windows, not one.
    if changes <= max(2, len(supported) // 4):
        return "steps (offset constant in stretches, jumping between them)"
    if max(increasing, decreasing) / changes >= 0.8:
        return "ramp (offset accumulates in one direction)"
    return "scatter (offset changes window to window)"


def shuffled_control(expected: Sequence[MetricNote], seed: int = 0) -> list[MetricNote]:
    """The same onsets with their pitches permuted - correspondence destroyed, structure kept.

    Fitting an offset per window means picking, from many candidate shifts, the one that agrees
    best. That will find *some* agreement even in noise, so a recovered F1 is only evidence if it
    is far above what the same procedure extracts from a reference it cannot legitimately match.
    Permuting pitches leaves the onset grid, the note density and the pitch distribution exactly
    as they were, and removes only the thing being measured.
    """
    generator = random.Random(seed)
    pitches = [note.pitch for note in expected]
    generator.shuffle(pitches)
    return [
        MetricNote(
            pitch=pitch,
            onset=note.onset,
            duration=note.duration,
            staff=note.staff,
            voice=note.voice,
        )
        for pitch, note in zip(pitches, expected)
    ]


def jumps_against_pages(
    windows: Sequence[dict[str, Any]], page_offsets: Sequence[float], window: Fraction
) -> list[dict[str, Any]]:
    """Where the local offset changes, and how far each change sits from a page boundary.

    This settles the page question directly rather than through aggregate F1. A drift that jumps
    at page joins and holds steady between them is a stitching error however small the aggregate
    says it is; one that jumps mid-page is not, whatever the page-count correlation suggests.
    """
    supported = [entry for entry in windows if entry["support"] >= MIN_SUPPORT and entry["notes"]]
    boundaries = list(page_offsets[1:]) if page_offsets else []
    jumps: list[dict[str, Any]] = []
    for earlier, later in zip(supported, supported[1:]):
        if abs(later["delta"] - earlier["delta"]) < 0.01:
            continue
        # The change happened somewhere inside the later window, so that window is the locator.
        start, end = later["start"], later["start"] + float(window)
        nearest = min(boundaries, key=lambda edge: abs(edge - start), default=None)
        jumps.append(
            {
                "window_start": start,
                "from": earlier["delta"],
                "to": later["delta"],
                "nearest_page_boundary": nearest,
                "inside_window": nearest is not None and start <= nearest < end,
            }
        )
    return jumps


def pitch_agreement(predicted: Sequence[MetricNote], expected: Sequence[MetricNote]) -> float:
    """Fraction of truth notes whose pitch is present in the prediction, ignoring time entirely.

    This is the arrangement check. No timing error can move it; a different arrangement, a missing
    repeat, or a two-piano reduction scored against a solo reference all do.
    """
    if not expected:
        return 0.0
    predicted_pitches = Counter(note.pitch for note in predicted)
    expected_pitches = Counter(note.pitch for note in expected)
    return sum((predicted_pitches & expected_pitches).values()) / len(expected)


def page_count(pdf: Path) -> int | None:
    """Page count read straight from the PDF page tree, so this needs no PDF library."""
    try:
        data = pdf.read_bytes()
    except OSError:
        return None
    counts = [int(value) for value in re.findall(rb"/Count\s+(\d+)", data)]
    if counts:
        return max(counts)
    return len(re.findall(rb"/Type\s*/Page[^s]", data)) or None


def diagnose(
    song: str,
    predicted: Sequence[MetricNote],
    expected: Sequence[MetricNote],
    pages: int | None = None,
    window: Fraction = Fraction(16),
    page_offsets: Sequence[float] = (),
) -> dict[str, Any]:
    metrics = calculate_note_metrics(predicted, expected)
    global_offset = best_global_offset(predicted, expected)
    windows = local_offsets(predicted, expected, window)
    corrected = apply_local_offsets(predicted, windows, window)
    recovered = calculate_note_metrics(corrected, expected)

    control = shuffled_control(expected)
    control_windows = local_offsets(predicted, control, window)
    control_recovered = calculate_note_metrics(
        apply_local_offsets(predicted, control_windows, window), control
    )

    return {
        "song": song,
        "pages": pages,
        "reference": {
            "predicted_notes": len(predicted),
            "truth_notes": len(expected),
            "note_ratio": round(len(predicted) / len(expected), 3) if expected else None,
            "pitch_agreement": round(pitch_agreement(predicted, expected), 4),
            "pitch_f1": round(metrics.pitch_f1, 4),
            "span_ratio": round(span_ratio(predicted, expected) or 0.0, 4),
            "predicted_span": float(timeline_span(predicted)),
            "truth_span": float(timeline_span(expected)),
        },
        "onset_f1": round(metrics.onset_f1, 4),
        "global_offset": global_offset,
        "recovered_onset_f1": round(recovered.onset_f1, 4),
        "recovered_gain": round(recovered.onset_f1 - metrics.onset_f1, 4),
        "control_onset_f1": round(calculate_note_metrics(predicted, control).onset_f1, 4),
        "control_recovered_onset_f1": round(control_recovered.onset_f1, 4),
        "windows": windows,
        "page_offsets": list(page_offsets),
        "jumps": jumps_against_pages(windows, page_offsets, window),
        "shape": classify(windows, global_offset),
    }


def format_curve(windows: Sequence[dict[str, Any]], limit: int = 20) -> str:
    """The local offset per window as one scannable line: '.' empty, '?' no consistent offset."""
    parts = []
    for entry in windows[:limit]:
        if not entry["notes"]:
            parts.append("    .")
        elif entry["support"] < MIN_SUPPORT:
            parts.append("    ?")
        else:
            parts.append(f"{entry['delta']:+5.2f}")
    return " ".join(parts) + (" ..." if len(windows) > limit else "")


def pearson(left: Sequence[float], right: Sequence[float]) -> float | None:
    if len(left) < 3:
        return None
    mean_left = sum(left) / len(left)
    mean_right = sum(right) / len(right)
    covariance = sum((a - mean_left) * (b - mean_right) for a, b in zip(left, right))
    spread = (
        sum((a - mean_left) ** 2 for a in left) * sum((b - mean_right) ** 2 for b in right)
    ) ** 0.5
    return covariance / spread if spread else None


def summarise(rows: Sequence[dict[str, Any]]) -> None:
    """Group means and the page-count correlations, on the repaired scoreboard.

    Confirmed and candidate pairs are reported apart because a candidate reference has not been
    shown to be the same arrangement as the PDF; averaging the two is how an unverified pairing
    turns into a quoted number.
    """
    if not rows:
        return
    mean = lambda values: sum(values) / len(values)  # noqa: E731

    seen: list[str] = []
    for row in rows:
        if row.get("pair_status") not in seen:
            seen.append(row.get("pair_status"))
    for status in seen:
        group = [row for row in rows if row.get("pair_status") == status]
        print(f"=== {status} ({len(group)} songs) ===")
        print(
            f"  onset_f1 {mean([row['onset_f1'] for row in group]):.4f}"
            f"   after local correction {mean([row['recovered_onset_f1'] for row in group]):.4f}"
            f"   control {mean([row['control_recovered_onset_f1'] for row in group]):.4f}"
        )

    trustworthy = [row for row in rows if row["reference"]["pitch_agreement"] >= 0.9]
    for label, group in (("all pairs", list(rows)), ("pitch agreement >= 0.9", trustworthy)):
        pages = [row["pages"] for row in group if row["pages"]]
        if len(pages) < 3 or len(set(pages)) < 2:
            continue
        scored = [row for row in group if row["pages"]]
        print(f"=== page count vs ... ({label}, n={len(pages)}) ===")
        for name, values in (
            ("onset_f1 as measured  ", [row["onset_f1"] for row in scored]),
            ("onset_f1 corrected    ", [row["recovered_onset_f1"] for row in scored]),
            ("reference quality     ", [row["reference"]["pitch_agreement"] for row in scored]),
        ):
            correlation = pearson(pages, values)
            if correlation is not None:
                print(f"  {name} r = {correlation:+.3f}")


def library_rows(args: argparse.Namespace, window: Fraction) -> list[dict[str, Any]]:
    """The user's PDFs, scored against the references in pairs.json."""
    pdf_directory = args.library / "pdf"
    pairs = load_pairs(args.pairs)
    rows: list[dict[str, Any]] = []
    for path in sorted(args.predictions.glob(f"*.{args.variant}.json")):
        song = path.name[: -len(f".{args.variant}.json")]
        record = json.loads(path.read_text(encoding="utf-8"))
        if not record.get("ok"):
            continue
        truth, status = truth_for(song, args.library, pairs)
        if truth is None:
            continue
        row = diagnose(
            song,
            notes_from_payload(record["payload"]),
            notes_from_midi(truth),
            page_count(pdf_directory / (song + ".pdf")),
            window,
            [entry["offset"] for entry in record.get("pages") or []],
        )
        row["pair_status"] = status
        rows.append(row)
    return rows


def olimpic_rows(args: argparse.Namespace, window: Fraction) -> list[dict[str, Any]]:
    """The canary's single systems, scored against the exact MusicXML shipped with each image.

    This is the control the library measurement never had. OLiMPiC's label *is* the music in the
    image, so any displacement found here belongs to the engine rather than to a reference that
    happens to be a different edition - and if the canary drifts too, the round-trip ceiling that
    prices a fine-tune is being compared against an understated number.
    """
    from diagnose_rhythm import ground_truth_notes, load_manifest

    rows: list[dict[str, Any]] = []
    for sample in load_manifest(args.manifest):
        identifier = sample["identifier"]
        path = args.predictions / (identifier.replace("/", "_") + ".json")
        if not path.is_file():
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        if not record.get("ok"):
            continue
        expected, _ = ground_truth_notes(Path(sample["musicxml"]), **BRIDGE_SYMMETRIC_FLAGS)
        row = diagnose(
            identifier,
            notes_from_payload(record["payload"]),
            expected,
            sample.get("pages", 1),
            window,
        )
        row["pair_status"] = "exact-label"
        rows.append(row)
    return rows


def oracle_rows(args: argparse.Namespace, window: Fraction) -> list[dict[str, Any]]:
    """The round-trip oracle's rebuilt MusicXML, corrected exactly as homr's output is.

    Without this the comparison is unfair in homr's favour: correcting homr for displacement and
    then measuring the remaining headroom against an *uncorrected* ceiling would credit homr with
    an alignment allowance the target never gets. The oracle's rebuilt score inflates timelines on
    its own - FINDINGS records 31 of 75 systems coming back long with no recognition involved - so
    it is displaced too, and by the same kind of error.

    Produce the inputs with:  roundtrip_oracle.py --keep-xml --out reports/diagnosis/oracle-corrected
    """
    from diagnose_rhythm import ground_truth_notes, load_manifest

    rows: list[dict[str, Any]] = []
    for sample in load_manifest(args.manifest):
        identifier = sample["identifier"]
        rebuilt = args.predictions / (identifier.replace("/", "_") + ".rebuilt.musicxml")
        if not rebuilt.is_file():
            continue
        predicted, _ = ground_truth_notes(rebuilt, **BRIDGE_SYMMETRIC_FLAGS)
        expected, _ = ground_truth_notes(Path(sample["musicxml"]), **BRIDGE_SYMMETRIC_FLAGS)
        row = diagnose(identifier, predicted, expected, 1, window)
        row["pair_status"] = "ceiling"
        rows.append(row)
    return rows


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_arguments(argv)
    window = Fraction(args.window).limit_denominator(64)

    if not args.predictions.is_dir():
        print(f"No cached payloads in {args.predictions}", file=sys.stderr)
        return 2

    collect = {"library": library_rows, "olimpic": olimpic_rows, "oracle": oracle_rows}
    rows = collect[args.source](args, window)
    if not rows:
        print(f"Nothing to diagnose from {args.predictions}", file=sys.stderr)
        return 2

    for row in rows:
        song, status = row["song"], row["pair_status"]
        reference = row["reference"]
        print(f"{song[:70]}   [{status}]")
        print(
            f"  pages {row['pages']}   notes {reference['predicted_notes']}/"
            f"{reference['truth_notes']} ({reference['note_ratio']}x)   "
            f"pitch agree {reference['pitch_agreement']:.3f}   span {reference['span_ratio']:.3f}"
        )
        print(
            f"  onset_f1 {row['onset_f1']:.4f}   best global shift "
            f"{row['global_offset']['delta']:+g} -> {row['global_offset']['onset_f1']:.4f} "
            f"({row['global_offset']['gain']:+.4f})"
        )
        print(f"  local offsets: {format_curve(row['windows'])}")
        print(
            f"  after local correction {row['recovered_onset_f1']:.4f} "
            f"({row['recovered_gain']:+.4f})   "
            f"control {row['control_recovered_onset_f1']:.4f}   shape: {row['shape']}"
        )
        if row["jumps"]:
            at_boundary = sum(1 for jump in row["jumps"] if jump["inside_window"])
            print(
                f"  {len(row['jumps'])} offset jumps, {at_boundary} of them in a window "
                "containing a page boundary"
                if row["page_offsets"]
                else f"  {len(row['jumps'])} offset jumps (page offsets not cached; rerun "
                "evaluate_library.py --rerun to place them against page boundaries)"
            )
        print()

    summarise(rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
