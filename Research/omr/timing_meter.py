#!/usr/bin/env python3
"""Per-bar ledger of what anchoring hole-free bars changes, for gating `anchor-all`.

Phase 2 of `plans/2026-10-18-remaining-timing-loss.md`. `anchor-all-keepN` (timing_correct.py)
adds one kind of decision to the shipped fix: a bar without holes whose decoded length is not
the meter and recurs on fewer than N hole-free bars is moved to the meter. Each such decision
is a **fix** where the label's bar has the meter's length, a **harm** where the label kept the
decoded length, and **neither** otherwise, as in `displacement_meter.py`. Beside each one are
blind signals, among them whether HOMR recognised a time signature at that bar, which the
correction does not read. Labels only grade decisions, on development items only.

    Bridge\\.venv-homr-gpu\\Scripts\\python.exe -I -B Research/omr/timing_meter.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "dist" / "Bridge"))
sys.path.insert(0, str(HERE / "src"))
sys.path.insert(0, str(HERE))

from displacement_attribution import align, app_pages, load_measures, repeat_across_pages  # noqa: E402
from displacement_correct import (ENGINES, RULER, covers, fit_shifts, internal_holes, load_page,  # noqa: E402
                                  manifest_items)

OUTPUT = HERE / "reports/timing/phase2/anchor-ledger.json"


def recognised_times(path: Path, part: int | None = 0) -> list[list[bool]]:
    """Per staff (of `part`, or of every part in load_page's order), whether each measure carries a
    time signature HOMR recognised."""
    import musicxml_normalizer as normalizer
    from music21 import converter, stream

    score = normalizer._prepare_score(
        lambda: normalizer._parse_musicxml_with_repair(converter, path, force_source=False),
        str(path), expand_repeats=True)
    coordinates = normalizer._musicxml_part_coordinates(score.parts)
    return [[measure.timeSignature is not None for measure in staff.getElementsByClass(stream.Measure)]
            for staff in score.parts if part is None or coordinates[id(staff)][0] == part]


def page_rows(path: Path, first_page: bool) -> list[dict[str, Any]]:
    staves = load_page(path)[0]
    times = recognised_times(path)
    part = [staff for staff in staves if staff.part == 0]
    count = max(len(staff.measures) for staff in part)
    rows = []
    for index in range(count):
        present = [staff.measures[index] for staff in part if index < len(staff.measures)]
        bar = present[0].bar
        advance = max(measure.advance for measure in present)
        if 0 < bar < advance and fit_shifts(present, bar) is not None:
            advance = bar  # the shipped fit already repairs it
        ends = {max(element.offset + element.duration for element in measure.elements if element.container == container)
                for measure in present for container in {element.container for element in measure.elements}}
        rows.append({"advance": advance, "bar": bar,
                     "hole": any(internal_holes(measure) for measure in present),
                     "covered": any(covers(measure, advance) for measure in present),
                     "even": len(ends) == 1,
                     "time_here": index > 0 and any(index < len(staff) and staff[index] for staff in times),
                     "time_next": any(index + 1 < len(staff) and staff[index + 1] for staff in times),
                     "pickup": first_page and index == 0, "last": index == count - 1})
    hole_free = Counter(row["advance"] for row in rows if not row["hole"])
    for row in rows:
        row["same_length_hole_free"] = hole_free[row["advance"]]
    return rows


def ledger(item: dict[str, Any], engine: str) -> list[dict[str, Any]]:
    label = HERE / item["label"]
    if repeat_across_pages(label) is not None:
        return []
    truth = load_measures(label, 0)[0][0]
    predicted, rows = [], []
    for number, (path, _) in enumerate(app_pages(item, engine)):
        staves = load_measures(path, number)[0]
        if not staves:
            continue
        predicted.extend(measure for measure in staves[0] if measure.part == 0)
        rows.extend(row | {"page": number} for row in page_rows(path, number == 0))
    if len(predicted) != len(rows):
        raise AssertionError(f"{item['id']} {engine}: loaders disagree on measure count")
    pairs = dict(align(predicted, truth))
    out = []
    for index, row in enumerate(rows):
        if row["hole"] or row["bar"] <= 0 or row["advance"] == row["bar"] or row["pickup"] and row["advance"] < row["bar"]:
            continue
        true = truth[pairs[index]] if pairs.get(index) is not None else None
        verdict = "neither"
        if true is not None and true.advance == row["bar"]:
            verdict = "fix"
        elif true is not None and true.advance == row["advance"]:
            verdict = "harm"
        out.append({"id": item["id"], "engine": engine, "measure": index, "verdict": verdict,
                    "true_advance": str(true.advance) if true else None,
                    **{key: (str(value) if isinstance(value, Fraction) else value) for key, value in row.items()}})
    return out


def main() -> int:
    done: dict[str, list[dict[str, Any]]] = json.loads(OUTPUT.read_text()) if OUTPUT.is_file() else {}
    for item in manifest_items(("dev", "dev-b")):
        for engine in ENGINES:
            key = f"{item['id']} {engine}"
            result = RULER / "captures" / engine / item["id"] / "result.json"
            if key in done or not result.is_file() or json.loads(result.read_text())["status"] != "ok":
                continue
            done[key] = ledger(item, engine)
            OUTPUT.parent.mkdir(parents=True, exist_ok=True)
            OUTPUT.write_text(json.dumps(done, indent=1) + "\n", encoding="utf-8")
            print(key, dict(Counter(row["verdict"] for row in done[key])), flush=True)
    rows = [row for found in done.values() for row in found]
    table: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        short = "short" if Fraction(row["advance"]) < Fraction(row["bar"]) else "long"
        for signal in ("time_here", "time_next", "covered", "even", "last"):
            table[f"{row['engine']} {short} {signal}={row[signal]}"][row["verdict"]] += 1
        table[f"{row['engine']} {short} recurs={row['same_length_hole_free']}"][row["verdict"]] += 1
    for key in sorted(table):
        print(key, dict(table[key]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
