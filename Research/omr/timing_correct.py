#!/usr/bin/env python3
"""Development variants for the timing loss the shipped fix leaves, on cached recognitions.

The residual map (`timing_residual.py`, `reports/timing/phase1/residual.json`) leaves most of
465's onset F1 in bars that still start in the wrong place: 0.55 with the fix, 0.85 with every
bar in place. The shipped fix (`fit+anchor-holes-keep3`) anchors a bar to the page meter only
where a voice has an internal hole. Anchoring every bar gained more on dev in Phase 3
(+0.168 against +0.107) but moved real meter changes; the keep3 gate that protects meter
changes was only ever tried on the hole rule. This tries it on every bar.

`displacement_correct.py` is the frozen Phase 3 record, so this extends its variant grammar
here instead: `[fit+]anchor-all-keepN[-gate...]` anchors every bar to the page meter unless
N hole-free bars on the page share its decoded length (a real meter), or a gate keeps a
hole-free bar: `coverunder` (shorter than the meter, one voice spells it out from beat 0),
`even` (every voice ends on its decoded length), `evenunder` (the same, short bars only) and
`time` (HOMR recognised a time signature at it). Every other variant is
`displacement_correct.lay_out` unchanged. Development splits only.

    Bridge\\.venv-homr-gpu\\Scripts\\python.exe -I -B Research/omr/timing_correct.py --splits dev dev-b
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "src"))
sys.path.insert(0, str(HERE))

import displacement_correct as dc  # noqa: E402
from displacement_correct import covers, fit_shifts, internal_holes  # noqa: E402

REPORT = HERE / "reports/timing/phase2"
SHIPPED = "fit+anchor-holes-keep3"
DEFAULT_VARIANTS = (SHIPPED, "fit+anchor", "fit+anchor-all-keep2", "fit+anchor-all-keep3",
                    "fit+anchor-all-keep3-coverunder", "fit+anchor-all-keep4",
                    "fit+anchor-all-keep3-even", "fit+anchor-all-keep3-evenunder", "fit+anchor-all-keep3-time",
                    "fit+anchor-all-keep3-even-time", "fit+anchor-all-keep3-evenunder-time",
                    "fit+anchor-all-keep2-even-time")
frozen_lay_out = dc.lay_out
frozen_load_page = dc.load_page


def load_page(path: Path, positions: bool = False):
    """`displacement_correct.load_page`, with each measure after a page's first marked where HOMR
    recognised a time signature (`time_here`), for the `time` gate."""
    from timing_meter import recognised_times

    staves, decoded, bar = frozen_load_page(path, positions)
    for staff, marks in zip(staves, recognised_times(path, part=None), strict=True):
        for index, measure in enumerate(staff.measures):
            measure.time_here = index > 0 and index < len(marks) and marks[index]
    return staves, decoded, bar


def evenly_ended(measures) -> bool:
    """Whether every voice of the bar, on every staff, ends at the same point."""
    ends = {max(element.offset + element.duration for element in measure.elements if element.container == container)
            for measure in measures for container in {element.container for element in measure.elements}}
    return len(ends) == 1


def lay_out(staves, variant: str, first_page: bool):
    body = variant.removeprefix("fit+")
    if not body.startswith("anchor-all-"):
        return frozen_lay_out(staves, variant, first_page)
    options = body.removeprefix("anchor-all-").split("-")
    least = next(int(option[4:]) for option in options if option.startswith("keep"))
    staves = copy.deepcopy(staves)  # pages are shared between variants
    notes = []
    by_part = defaultdict(list)
    for staff in staves:
        by_part[staff.part].append(staff)
    page_length = Fraction(0)
    for part_staves in by_part.values():
        count = max(len(staff.measures) for staff in part_staves)
        present = [[staff.measures[index] for staff in part_staves if index < len(staff.measures)]
                   for index in range(count)]
        lengths = [max(measure.advance for measure in measures) for measures in present]
        bars = [measures[0].bar for measures in present]
        holes = [any(internal_holes(measure) for measure in measures) for measures in present]
        if variant.startswith("fit+"):
            for index, measures in enumerate(present):
                shifts = fit_shifts(measures, bars[index]) if 0 < bars[index] < lengths[index] else None
                if shifts is None:
                    continue
                for measure, moves in zip(measures, shifts):
                    for element in measure.elements:
                        element.offset -= moves.get(element.container, Fraction(0))
                lengths[index] = bars[index]
                holes[index] = any(internal_holes(measure) for measure in measures)
        hole_free = Counter(length for length, hole in zip(lengths, holes) if not hole)
        chosen = []
        for index, (length, bar) in enumerate(zip(lengths, bars)):
            if bar <= 0 or (first_page and index == 0 and length < bar):
                chosen.append(length)  # no meter to anchor to, or an opening pickup
                continue
            # The shipped gate exactly, now for bars without holes too.
            kept = hole_free[length] >= least
            if "coverunder" in options and length < bar and any(covers(measure, length) for measure in present[index]):
                kept = True
            if not holes[index]:
                # even: every voice ends on the decoded length, so the bar is spelled out whole;
                # evenunder: the same, for a short bar only; time: HOMR read a time signature here.
                if ("even" in options or "evenunder" in options and length < bar) and evenly_ended(present[index]):
                    kept = True
                if "time" in options and any(getattr(measure, "time_here", False) for measure in present[index]):
                    kept = True
            chosen.append(length if kept else bar)
        starts = [sum(chosen[:index], Fraction(0)) for index in range(count)]
        page_length = max(page_length, sum(chosen, Fraction(0)))
        for staff in part_staves:
            for index, measure in enumerate(staff.measures):
                for element in measure.elements:
                    notes.extend((staff.part, staff.staff, pitch, element.voice, starts[index] + element.offset,
                                  element.duration) for pitch in element.pitches)
    return notes, page_length


dc.lay_out = lay_out
dc.load_page = load_page


FREEZE = REPORT / "freeze.json"
TEST_OUTPUT = REPORT / "test.json"
HELD_OUT = ("test", "test-b")


def source_hash() -> str:
    """The behaviour's code: this file, the frozen library it extends and the time-signature reader."""
    import hashlib

    digest = hashlib.sha256()
    for name in ("timing_correct.py", "displacement_correct.py", "timing_meter.py"):
        digest.update((HERE / name).read_bytes().replace(b"\r\n", b"\n"))
    return digest.hexdigest()


def versus(items, rows, base: str, variant: str, engine: str) -> dict:
    """`variant` against `base` per score: the plan's acceptance figures with the shipped fix as control."""
    import statistics

    from summarize_homr_pair import bootstrap_interval

    baseline = json.loads(dc.BASELINE.read_text())["rows"]
    for path in dc.BASELINES_B:
        baseline |= json.loads(path.read_text())["rows"]
    engine_rows = [(item["id"], rows[item["id"]][engine]) for item in items]
    differences = [row[variant]["onset_f1"] - row[base]["onset_f1"] for _, row in engine_rows]
    lower, upper, p_value = bootstrap_interval(differences)
    near = [score for score, row in engine_rows if row["status"] == "ok" and row[base]["onset_f1"] >= 0.9
            and 0.98 <= baseline[score][engine]["reference"]["span_ratio"] <= 1.02]
    near_drops = {score: round(rows[score][engine][variant]["onset_f1"] - rows[score][engine][base]["onset_f1"], 4)
                  for score in near}
    return {"onset_gain": round(statistics.fmean(differences), 4), "onset_gain_95": [round(lower, 4), round(upper, 4)],
            "one_sided_p": round(p_value, 4),
            "pitch_change": round(statistics.fmean(row[variant]["pitch_f1"] - row[base]["pitch_f1"]
                                                   for _, row in engine_rows), 4),
            "scores_better": sum(difference > 0.0001 for difference in differences),
            "scores_worse": sum(difference < -0.0001 for difference in differences),
            "worst_drop": round(min(differences), 4), "near_correct_scores": len(near),
            "near_correct_worst_drop": min(near_drops.values(), default=0.0),
            "near_correct_losing_over_0.01": {score: drop for score, drop in near_drops.items() if drop < -0.01}}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--splits", nargs="+", default=["dev", "dev-b"], choices=("dev", "dev-b"))
    parser.add_argument("--variants", nargs="+", default=list(DEFAULT_VARIANTS))
    parser.add_argument("--ids", nargs="*")
    parser.add_argument("--output", type=Path, default=REPORT / "development.json")
    parser.add_argument("--freeze", metavar="VARIANT", help="record the selected variant and the code's hash")
    parser.add_argument("--test", action="store_true", help="score the frozen variant on test and test-b, once")
    args = parser.parse_args()
    manifest = json.loads(dc.MANIFEST.read_text())
    if args.freeze:
        development = json.loads(args.output.read_text())
        if args.freeze not in development["variants"] or args.freeze in ("control", SHIPPED):
            parser.error("freeze a candidate from a dev + dev-b run that scored it")
        if FREEZE.exists():
            parser.error(f"{FREEZE.name} exists: the candidate is frozen once")
        FREEZE.write_text(json.dumps({"variant": args.freeze, "control": SHIPPED, "source_sha256": source_hash(),
                                      "development": {engine: development["summary"][engine][args.freeze]
                                                      for engine in dc.ENGINES}}, indent=1) + "\n", encoding="utf-8")
        print(f"froze {args.freeze} at {source_hash()}")
        return 0
    if args.test:
        frozen = json.loads(FREEZE.read_text())
        if frozen["source_sha256"] != source_hash():
            parser.error("the code changed after freezing; the frozen variant is no longer the code here")
        if TEST_OUTPUT.exists():
            parser.error(f"{TEST_OUTPUT.name} exists: the held-out sets are scored once")
        items = dc.manifest_items(HELD_OUT)
        variants = ("control", SHIPPED, frozen["variant"])
        rows = dc.evaluate(items, variants, manifest["truth_flags"])
        groups = {"all": items} | {split: [item for item in items if item["split"] == split] for split in HELD_OUT}
        groups |= {stratum: [item for item in items if item.get("stratum") == stratum]
                   for stratum in sorted({item["stratum"] for item in items if item.get("stratum")})}
        summary = {name: {"against_raw": dc.summarise(group, rows, variants),
                          "against_shipped": {engine: versus(group, rows, SHIPPED, frozen["variant"], engine)
                                              for engine in dc.ENGINES}}
                   for name, group in groups.items()}
        TEST_OUTPUT.write_text(json.dumps({"splits": HELD_OUT, "frozen": frozen, "summary": summary, "rows": rows},
                                          indent=1) + "\n", encoding="utf-8")
        print(json.dumps({name: value["against_shipped"] for name, value in summary.items()}, indent=1))
        return 0
    items = [item for item in dc.manifest_items(tuple(args.splits)) if not args.ids or item["id"] in args.ids]
    variants = ("control", *args.variants)
    rows = dc.evaluate(items, variants, manifest["truth_flags"])
    summary = dc.summarise(items, rows, variants)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"splits": args.splits, "variants": variants, "summary": summary,
                                       "rows": rows}, indent=1) + "\n", encoding="utf-8")
    for engine, by_variant in summary.items():
        for variant in variants:
            row = by_variant[variant]
            print(engine, variant, {key: row[key] for key in ("onset_f1", "onset_gain", "onset_gain_95", "pitch_change",
                                                               "scores_worse", "worst_drop", "near_correct_worst_drop")
                                    if key in row}, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
