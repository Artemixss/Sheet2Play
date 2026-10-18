#!/usr/bin/env python3
"""Where the timing fix leaves onset F1: bars in the wrong place, notes misplaced inside bars, or wrong notes.

Phase 1 of the remaining-timing-loss plan (`plans/2026-10-18-remaining-timing-loss.md`).
The shipped timing fix (`Bridge/timing_correction.py`, research variant `fit+anchor-holes-keep3`)
re-lays bar lengths. What onset F1 it leaves is split three ways, each by an oracle fitted against
the exact label, so these are ceilings, not results:

- **fixed**: the app with the timing fix on, rebuilt bar by bar and checked against `predict`.
- **bars in place**: every bar aligned to a label bar starts where the label's does; notes keep
  their offset inside the bar. The gain over *fixed* is the displacement the fix leaves.
- **notes in place**: as above, and each note is snapped to the nearest unused label onset of
  the same pitch in the aligned bar. The gain over *bars in place* is in-bar placement; what is
  still missing is notes read wrongly or not at all, which this plan does not cover.

Each part is then split by mechanism with undo counterfactuals, one family at a time: bar
families are given their true length (displacement), voice families their true onsets
(placement). Families overlap, so their gains need not add up to the total.

Bars are aligned by pitch content (`displacement_attribution.align`) over both staves together,
and classified by `displacement_attribution.classify` with the bar's fixed length.

    Bridge\\.venv-homr-gpu\\Scripts\\python.exe -I -B Research/omr/timing_residual.py
"""

from __future__ import annotations

import argparse
import copy
import json
import statistics
import sys
from bisect import bisect_right
from collections import Counter, defaultdict
from dataclasses import dataclass, field, replace
from fractions import Fraction
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "dist" / "Bridge"))
sys.path.insert(0, str(HERE / "src"))
sys.path.insert(0, str(HERE))

from diagnose_rhythm import ground_truth_notes  # noqa: E402
from displacement_attribution import (GARBLED, Measure, PageContext, align, app_pages, classify,  # noqa: E402
                                      engine_log, load_measures, page_advance, similarity)
from displacement_correct import (ENGINES, RULER, fit_shifts, internal_holes, load_page,  # noqa: E402
                                  manifest_items, predict)
from sheet2play_omr.metrics import MetricNote, calculate_note_metrics  # noqa: E402

VARIANT = "fit+anchor-holes-keep3"
KEEP_RECURRING = 3
SPLITS = ("dev", "test", "dev-b", "test-b")
REPORT = HERE / "reports/timing/phase1"
FIX_HARM = "timing fix: moved a bar HOMR decoded right"


@dataclass
class Bar:
    """One bar of part 0 after the timing fix, both staves."""
    page: int
    index: int  # within part 0 of its page
    decoded: Fraction
    length: Fraction  # after the timing fix
    meter: Fraction  # HOMR's page meter
    notes: list[tuple[int, int, str, int, Fraction, Fraction]] = field(default_factory=list)
    # (staff, pitch, voice, container, offset in bar, duration)


def fixed_page(staves, first_page: bool) -> tuple[list[Bar], list[tuple[int, int, str, Fraction, Fraction]], Fraction]:
    """`displacement_correct.lay_out(..., VARIANT)` keeping each note's bar: part 0's bars, other
    parts' notes as (staff, pitch, voice, page start, duration), and the page's fixed length."""
    staves = copy.deepcopy(staves)
    by_part: dict[int, list] = defaultdict(list)
    for staff in staves:
        by_part[staff.part].append(staff)
    bars: list[Bar] = []
    others: list[tuple[int, int, str, Fraction, Fraction]] = []
    page_length = Fraction(0)
    for part, part_staves in by_part.items():
        count = max(len(staff.measures) for staff in part_staves)
        present = [[staff.measures[index] for staff in part_staves if index < len(staff.measures)]
                   for index in range(count)]
        owners = [[staff for staff in part_staves if index < len(staff.measures)] for index in range(count)]
        decoded = [max(measure.advance for measure in measures) for measures in present]
        lengths = list(decoded)
        meters = [measures[0].bar for measures in present]
        holes = [any(internal_holes(measure) for measure in measures) for measures in present]
        for index, measures in enumerate(present):
            shifts = fit_shifts(measures, meters[index]) if 0 < meters[index] < lengths[index] else None
            if shifts is None:
                continue
            for measure, moves in zip(measures, shifts):
                for element in measure.elements:
                    element.offset -= moves.get(element.container, Fraction(0))
            lengths[index] = meters[index]
            holes[index] = any(internal_holes(measure) for measure in measures)
        hole_free = Counter(length for length, hole in zip(lengths, holes) if not hole)
        chosen = []
        for index, (length, meter) in enumerate(zip(lengths, meters)):
            if meter <= 0 or (first_page and index == 0 and length < meter):
                chosen.append(length)
            else:
                anchored = holes[index] and hole_free[length] < KEEP_RECURRING
                chosen.append(meter if anchored else length)
        starts = [sum(chosen[:index], Fraction(0)) for index in range(count)]
        page_length = max(page_length, sum(chosen, Fraction(0)))
        for index, measures in enumerate(present):
            notes = [(staff.staff, pitch, element.voice, element.container, element.offset, element.duration)
                     for staff, measure in zip(owners[index], measures) for element in measure.elements
                     for pitch in element.pitches]
            if part == min(by_part):
                bars.append(Bar(-1, index, decoded[index], chosen[index], meters[index], notes))
            else:
                others.extend((staff, pitch, voice, starts[index] + offset, duration)
                              for staff, pitch, voice, _, offset, duration in notes)
    return bars, others, page_length


def merged(measures: list[Measure]) -> Measure:
    """Both staves of one bar as one measure, for alignment and classification."""
    first = measures[0]
    out = replace(first, pitches=Counter(), durations=Counter())
    for measure in measures:
        out.pitches += measure.pitches
        out.durations += measure.durations
    out.advance = max(measure.advance for measure in measures)
    for name in ("tremolos", "notes", "grace", "tuplets", "voices", "chords"):
        setattr(out, name, sum(getattr(measure, name) for measure in measures))
    out.rests = sum((measure.rests for measure in measures), Fraction(0))
    out.gaps = max(measure.gaps for measure in measures)
    for name in ("new_system", "new_page", "reused", "copy"):
        setattr(out, name, any(getattr(measure, name) for measure in measures))
    return out


def matched_onsets(predicted: list[Fraction], truth: list[Fraction]) -> list[Fraction | None]:
    """For each predicted onset (sorted), the label onset of a monotone one-to-one matching with the
    least total distance, or None where the label has fewer notes of this pitch in the bar."""
    swap = len(predicted) > len(truth)
    short, long_ = (truth, predicted) if swap else (predicted, truth)
    rows, cols = len(short), len(long_)
    inf = float("inf")
    cost = [[inf] * (cols + 1) for _ in range(rows + 1)]
    cost[0] = [0.0] * (cols + 1)
    for i in range(1, rows + 1):
        for j in range(i, cols + 1):
            cost[i][j] = min(cost[i][j - 1], cost[i - 1][j - 1] + abs(float(short[i - 1] - long_[j - 1])))
    pairs: dict[int, int] = {}
    i, j = rows, cols
    while i > 0:
        if j > i and cost[i][j] == cost[i][j - 1]:
            j -= 1
        else:
            pairs[i - 1] = j - 1
            i, j = i - 1, j - 1
    if swap:  # short is the label: map predicted index -> label onset
        out: list[Fraction | None] = [None] * len(predicted)
        for truth_index, predicted_index in pairs.items():
            out[predicted_index] = truth[truth_index]
        return out
    return [truth[pairs[index]] for index in range(len(predicted))]


def onset_f1(notes: list[tuple[int, Fraction]], truth: list[MetricNote]) -> float:
    predicted = [MetricNote(pitch=pitch, onset=onset, duration=Fraction(1), staff=0, voice="1") for pitch, onset in notes]
    return calculate_note_metrics(predicted, truth).onset_f1


def family(mechanism: str) -> str:
    return mechanism.split(":")[0]


def residual(item: dict[str, Any], engine: str) -> dict[str, Any]:
    label = HERE / item["label"]
    truth_notes, _ = ground_truth_notes(label, expand_repeats=True, skip_grace_notes=False)
    truth_staves = load_measures(label, 0)[0]
    truth_bars = [merged([staff[index] for staff in truth_staves]) for index in range(len(truth_staves[0]))]
    truth_starts = [measure.start for measure in truth_bars]

    paths = [path for path, _ in app_pages(item, engine)]
    pages = [load_page(path) for path in paths]
    bars: list[Bar] = []
    predicted: list[Measure] = []
    page_lengths, page_meters, other_notes = [], [], []
    for number, (path, (staves, _, meter)) in enumerate(zip(paths, pages)):
        page_bars, others, length = fixed_page(staves, number == 0)
        measures = [staff for staff in load_measures(path, number)[0]]
        part0 = [[measure for measure in staff if measure.part == min(m.part for m in staff)] for staff in measures]
        if len(part0[0]) != len(page_bars):
            raise AssertionError(f"{item['id']} {engine} page {number + 1}: loaders disagree on bar count")
        for index, bar in enumerate(page_bars):
            bar.page = number
            predicted.append(merged([staff[index] for staff in part0 if index < len(staff)]))
        bars.extend(page_bars)
        page_lengths.append(length)
        page_meters.append(meter)
        other_notes.append(others)

    def page_offsets(lengths: list[Fraction]) -> list[Fraction]:
        offsets, offset = [], Fraction(0)
        for number, (length, meter) in enumerate(zip(lengths, page_meters)):
            offsets.append(offset)
            offset += page_advance(length, meter, number == 0)
        return offsets

    offsets = page_offsets(page_lengths)

    def bar_starts(lengths: list[Fraction], page_override: list[Fraction] | None = None) -> list[Fraction]:
        """Absolute start of each bar when bars take `lengths` and pages stitch as the app does."""
        sums: dict[int, Fraction] = defaultdict(Fraction)
        for bar, length in zip(bars, lengths):
            sums[bar.page] += length
        # A page's length is the longest part's; part 0's bars only change part 0's sum.
        totals = [max(page_lengths[number] - sum((b.length for b in bars if b.page == number), Fraction(0))
                      + sums[number], sums[number]) for number in range(len(pages))]
        page_start = page_override or page_offsets(totals)
        starts, cursor, page = [], Fraction(0), -1
        for bar, length in zip(bars, lengths):
            if bar.page != page:
                page, cursor = bar.page, page_start[bar.page]
            starts.append(cursor)
            cursor += length
        return starts

    fixed_lengths = [bar.length for bar in bars]
    fixed_starts = bar_starts(fixed_lengths)
    fixed_notes = [(pitch, fixed_starts[k] + offset) for k, bar in enumerate(bars)
                   for _, pitch, _, _, offset, _ in bar.notes]
    fixed_notes += [(pitch, offsets[number] + start) for number, others in enumerate(other_notes)
                    for _, pitch, _, start, _ in others]
    reference = Counter((pitch, start) for _, _, pitch, _, start, _ in predict(pages, VARIANT))
    if Counter(fixed_notes) != reference:
        raise AssertionError(f"{item['id']} {engine}: bar-by-bar rebuild differs from predict()")

    pairs = align(predicted, truth_bars)
    to_truth = {k: j for k, j in pairs if k is not None and j is not None}
    dropped_after: dict[int, list[int]] = defaultdict(list)  # last predicted bar before a label-only bar
    last = None
    for k, j in pairs:
        if k is not None:
            last = k
        elif j is not None:
            dropped_after[-1 if last is None else last].append(j)

    # Label page of each label bar, and systems per page, as Phase 2 does.
    label_page, page_index = [], 0
    for measure in truth_staves[0]:
        page_index += int(measure.new_page and measure.index > 0)
        label_page.append(page_index)
    pages_agree = page_index + 1 == len(pages)
    label_systems = Counter(page for measure, page in zip(truth_staves[0], label_page)
                            if measure.index == 0 or measure.new_system or measure.new_page) if pages_agree else Counter()
    detected = Counter(bar.page for bar, measure in zip(bars, predicted) if bar.index == 0 or measure.new_system)
    try:
        log = engine_log(item["id"], engine)
    except KeyError:  # the 426 log index covers the Phase 1 ruler only; without it nothing is "stripped"
        log = {}

    def context(page: int) -> PageContext:
        entry = log.get(str(page + 1), {})
        tokens = sum(len(system) for system in entry.get("systems", []))
        exported = len({measure.number for bar, measure in zip(bars, predicted) if bar.page == page})
        trusted = bool(entry) and tokens == exported
        values = lambda key: {str(v[0] if isinstance(v, list) else v) for v in entry.get(key, [])} if trusted else set()
        return PageContext(
            label_meters={truth_bars[j].bar for k, j in to_truth.items() if bars[k].page == page and truth_bars[j].bar},
            systems_match=not pages_agree or detected[page] == label_systems[page],
            stripped=values("stripped"), retimed=values("retimed"))

    contexts = [context(number) for number in range(len(pages))]

    # Bars in place: an aligned bar starts at its label bar's start; an unaligned one keeps the
    # shift of the last aligned bar before it on its page (or the next one after it).
    shifts: list[Fraction | None] = [truth_starts[to_truth[k]] - fixed_starts[k] if k in to_truth else None
                                     for k in range(len(bars))]
    for k in range(len(bars)):
        if shifts[k] is None:
            same_page = [m for m in range(len(bars)) if bars[m].page == bars[k].page and shifts[m] is not None]
            before = [m for m in same_page if m < k]
            shifts[k] = shifts[max(before)] if before else (shifts[min(same_page)] if same_page else Fraction(0))
    page_shift = {}
    for number in range(len(pages)):
        on_page = [shifts[k] for k in range(len(bars)) if bars[k].page == number]
        page_shift[number] = Counter(on_page).most_common(1)[0][0] if on_page else Fraction(0)
    other_in_place = [(pitch, offsets[number] + start + page_shift[number]) for number, others in enumerate(other_notes)
                      for _, pitch, _, start, _ in others]
    in_place = [(pitch, fixed_starts[k] + shifts[k] + offset) for k, bar in enumerate(bars)
                for _, pitch, _, _, offset, _ in bar.notes]

    # Notes in place: snap to label onsets of the same pitch in the aligned label bar.
    truth_by_bar: dict[int, dict[int, list[Fraction]]] = defaultdict(lambda: defaultdict(list))
    for note in truth_notes:
        j = bisect_right(truth_starts, note.onset) - 1
        if j >= 0:
            truth_by_bar[j][note.pitch].append(note.onset)
    snapped: dict[tuple[int, int], Fraction] = {}  # (bar, note index) -> label onset
    for k, bar in enumerate(bars):
        if k not in to_truth:
            continue
        by_pitch: dict[int, list[int]] = defaultdict(list)
        for index, (_, pitch, _, _, offset, _) in enumerate(bar.notes):
            by_pitch[pitch].append(index)
        for pitch, indices in by_pitch.items():
            indices.sort(key=lambda index: bar.notes[index][4])
            targets = sorted(truth_by_bar[to_truth[k]].get(pitch, []))
            guesses = [fixed_starts[k] + shifts[k] + bar.notes[index][4] for index in indices]
            for index, onset in zip(indices, matched_onsets(guesses, targets)):
                if onset is not None:
                    snapped[(k, index)] = onset

    def placed(families: set[str] | None) -> list[tuple[int, Fraction]]:
        return [(pitch, snapped.get((k, index), fixed_starts[k] + shifts[k] + offset)
                 if families is None or voice_family.get((k, staff, container)) in families
                 else fixed_starts[k] + shifts[k] + offset)
                for k, bar in enumerate(bars) for index, (staff, pitch, _, container, offset, _) in enumerate(bar.notes)]

    # Displacement families: the fixed length of each aligned bar that is wrong, by mechanism.
    mechanisms: dict[int, str] = {}
    for k, j in to_truth.items():
        if bars[k].length != truth_bars[j].advance:
            # A bar HOMR decoded right that the fix then moved is the fix's own harm (a real
            # meter change it anchored), not something left to fix in the recognition.
            mechanisms[k] = FIX_HARM if bars[k].decoded == truth_bars[j].advance else classify(
                replace(predicted[k], advance=bars[k].length), truth_bars[j], contexts[bars[k].page])
    unaligned_label = sum(len(js) for js in dropped_after.values())

    def undo_lengths(undo: set[str]) -> list[tuple[int, Fraction]]:
        lengths = [truth_bars[to_truth[k]].advance if k in mechanisms and family(mechanisms[k]) in undo
                   else (Fraction(0) if k not in to_truth and "extra bar" in undo else bars[k].length)
                   for k in range(len(bars))]
        if "dropped bar" in undo:
            for k, js in dropped_after.items():
                if k >= 0:
                    lengths[k] += sum(truth_bars[j].advance for j in js)
        starts = bar_starts(lengths)
        return [(pitch, starts[k] + offset) for k, bar in enumerate(bars) for _, pitch, _, _, offset, _ in bar.notes] + \
            [(pitch, offsets[number] + start) for number, others in enumerate(other_notes)
             for _, pitch, _, start, _ in others]

    # Placement families: per voice of each aligned bar, after bars are in place.
    voice_family: dict[tuple[int, int, int], str] = {}
    misplaced_by_family: Counter = Counter()
    for k, bar in enumerate(bars):
        if k not in to_truth:
            continue
        garbled = similarity(predicted[k].pitches, truth_bars[to_truth[k]].pitches) < GARBLED
        deltas: dict[tuple[int, int], list[Fraction]] = defaultdict(list)
        for index, (staff, _, _, container, offset, _) in enumerate(bar.notes):
            if (k, index) in snapped:
                deltas[(staff, container)].append(snapped[(k, index)] - (fixed_starts[k] + shifts[k] + offset))
        truth_tuplets = truth_bars[to_truth[k]].tuplets or truth_bars[to_truth[k]].tremolos
        for container, values in deltas.items():
            wrong = [value for value in values if value]
            if not wrong:
                continue
            if garbled:
                name = "garbled bar"
            elif len(set(values)) == 1:
                name = "voice offset"  # the whole voice starts in the wrong place
            elif truth_tuplets and not predicted[k].tuplets:
                name = "rhythm: tuplet missing"
            elif truth_tuplets or predicted[k].tuplets:
                name = "rhythm: tuplet differs"
            else:
                name = "rhythm: durations"
            voice_family[(k, *container)] = name
            misplaced_by_family[name] += len(wrong)

    scores = {
        "fixed": onset_f1(fixed_notes, truth_notes),
        "bars_in_place": onset_f1(in_place + other_in_place, truth_notes),
        "notes_in_place": onset_f1(placed(None) + other_in_place, truth_notes),
    }
    displacement = {name: onset_f1(undo_lengths({name}), truth_notes) - scores["fixed"]
                    for name in sorted({family(m) for m in mechanisms.values()}
                                       | ({"dropped bar"} if unaligned_label else set())
                                       | ({"extra bar"} if len(bars) > len(to_truth) else set()))}
    displacement_all = onset_f1(undo_lengths({family(m) for m in mechanisms.values()} | {"dropped bar", "extra bar"}),
                                truth_notes) - scores["fixed"]
    placement = {name: onset_f1(placed({name}) + other_in_place, truth_notes) - scores["bars_in_place"]
                 for name in sorted(misplaced_by_family)}
    return {
        "scores": {key: round(value, 4) for key, value in scores.items()},
        "notes": len(fixed_notes), "label_notes": len(truth_notes), "other_part_notes": len(other_in_place),
        "bars": len(bars), "aligned": len(to_truth), "label_bars": len(truth_bars), "label_only": unaligned_label,
        "wrong_length_bars": dict(Counter(family(m) for m in mechanisms.values())),
        "displacement_gain": {key: round(value, 4) for key, value in displacement.items()},
        "displacement_gain_all_lengths": round(displacement_all, 4),
        "misplaced_notes": dict(misplaced_by_family),
        "placement_gain": {key: round(value, 4) for key, value in placement.items()},
    }


def summarise(rows: dict[str, dict[str, Any]], items: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for engine in ENGINES:
        ok = [rows[item["id"]][engine] for item in items if rows[item["id"]][engine].get("status") == "ok"]
        means = lambda values: round(statistics.fmean(values), 4) if values else None
        families = lambda key: {name: means([row[key].get(name, 0.0) for row in ok])
                                for name in sorted({name for row in ok for name in row[key]})}
        summary[engine] = {
            "recognitions": len(ok),
            **{key: means([row["scores"][key] for row in ok]) for key in ("fixed", "bars_in_place", "notes_in_place")},
            "displacement_gain_all_lengths": means([row["displacement_gain_all_lengths"] for row in ok]),
            "displacement_gain": dict(sorted(families("displacement_gain").items(), key=lambda pair: -(pair[1] or 0))),
            "placement_gain": dict(sorted(families("placement_gain").items(), key=lambda pair: -(pair[1] or 0))),
            "misplaced_notes": dict(sum((Counter(row["misplaced_notes"]) for row in ok), Counter()).most_common()),
            "wrong_length_bars": dict(sum((Counter(row["wrong_length_bars"]) for row in ok), Counter()).most_common()),
        }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ids", nargs="*")
    parser.add_argument("--output", type=Path, default=REPORT / "residual.json")
    args = parser.parse_args()
    items = [item for item in manifest_items(SPLITS) if not args.ids or item["id"] in args.ids]
    rows: dict[str, dict[str, Any]] = {}
    for item in items:
        rows[item["id"]] = {}
        for engine in ENGINES:
            result = json.loads((RULER / "captures" / engine / item["id"] / "result.json").read_text())
            if result["status"] != "ok":
                rows[item["id"]][engine] = {"status": result["status"]}
                continue
            row = {"status": "ok", **residual(item, engine)}
            rows[item["id"]][engine] = row
            print(item["id"], engine, row["scores"], flush=True)
    report = {"variant": VARIANT, "splits": list(SPLITS),
              "summary": {"all": summarise(rows, items)} | {
                  split: summarise(rows, [item for item in items if item["split"] == split]) for split in SPLITS
                  if any(item["split"] == split for item in items)},
              "rows": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"]["all"], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
