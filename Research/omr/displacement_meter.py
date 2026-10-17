#!/usr/bin/env python3
"""Per-measure ledger of what anchor-holes changes, for developing a meter-change gate.

Phase 3 replan, option 1 (plans/MAIN_PLAN.md). anchor-holes moves a hole-marked measure to
HOMR's page meter. Each such decision is a **fix** where the label's measure has the page
meter's length, a **harm** where the label kept the decoded length, and **neither** otherwise.
A gate needs blind signals that separate harms from fixes; this writes every decision with
the candidate signals beside it. Labels are used only to grade decisions, on development
items only.

Pages come from `displacement_correct.load_page`, the correction's own view; label measures
are matched by `displacement_attribution.align` (pitch content). Scores whose label repeats
across a page break are skipped: the app's page-wise expansion has no single measure order.

    Bridge\\.venv-homr-gpu\\Scripts\\python.exe -I -B Research/omr/displacement_meter.py
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "dist" / "Bridge"))
sys.path.insert(0, str(HERE / "src"))
sys.path.insert(0, str(HERE))

from displacement_attribution import align, app_pages, load_measures, repeat_across_pages  # noqa: E402
from displacement_correct import (ENGINES, RULER, covers, internal_holes, load_page, manifest_items,  # noqa: E402
                                  x_inversions)

OUTPUT = HERE / "reports/displacement/phase3b/meter-ledger.json"


def width(measures) -> int | None:
    """The page distance from a bar's leftmost note to its rightmost, staves together."""
    xs = [element.x for measure in measures for element in measure.elements if element.x is not None]
    return max(xs) - min(xs) if len(xs) > 1 else None


def page_rows(staves, first_page: bool) -> list[dict[str, Any]]:
    """Part 0 of one page, measure by measure, as lay_out sees it."""
    part = [staff for staff in staves if staff.part == 0]
    count = max(len(staff.measures) for staff in part)
    rows = []
    for index in range(count):
        present = [staff.measures[index] for staff in part if index < len(staff.measures)]
        advance = max(measure.advance for measure in present)
        rows.append({"advance": advance, "bar": present[0].bar,
                     "hole": any(internal_holes(measure) for measure in present),
                     "covered": any(covers(measure, advance) for measure in present),
                     "inversions": x_inversions(present),
                     "width": width(present),
                     "pickup": first_page and index == 0})
    typical = sorted(row["width"] for row in rows if row["width"] and row["advance"] == row["bar"])
    for row in rows:
        row["width_ratio"] = round(row["width"] / typical[len(typical) // 2], 3) if typical and row["width"] else None
    at_bar = sum(row["advance"] == row["bar"] for row in rows) / len(rows)
    for row in rows:
        row["page_at_bar_share"] = round(at_bar, 3)
    hole_free = Counter(row["advance"] for row in rows if not row["hole"])
    for index, row in enumerate(rows):
        others = hole_free.copy()
        if not row["hole"]:
            others[row["advance"]] -= 1
        row["same_length_hole_free"] = others[row["advance"]]
        row["page_hole_free"] = sum(hole_free.values())
        row["page_hole_free_at_bar"] = hole_free[row["bar"]]
        row["page_lengths"] = len([length for length, seen in hole_free.items() if seen >= 2])
        row["neighbour_same"] = any(0 <= other < len(rows) and not rows[other]["hole"]
                                    and rows[other]["advance"] == row["advance"] for other in (index - 1, index + 1))
    return rows


def ledger(item: dict[str, Any], engine: str) -> list[dict[str, Any]]:
    label = HERE / item["label"]
    if repeat_across_pages(label) is not None:
        return []
    truth = load_measures(label, 0)[0][0]
    files = [path for path, _ in app_pages(item, engine)]
    predicted, rows = [], []
    for number, path in enumerate(files):
        staves = load_measures(path, number)[0]
        if not staves:
            continue
        predicted.extend(measure for measure in staves[0] if measure.part == 0)
        for row in page_rows(load_page(path, positions=True)[0], number == 0):
            rows.append(row | {"page": number})
    if len(predicted) != len(rows):
        raise AssertionError(f"{item['id']} {engine}: loaders disagree on measure count")
    pairs = dict(align(predicted, truth))
    label_bars_by_page: dict[int, set[Fraction]] = {}
    for index, row in enumerate(rows):
        true = truth[pairs[index]] if pairs.get(index) is not None else None
        row["true_advance"] = true.advance if true else None
        row["true_bar"] = true.bar if true else None
        if true and true.bar:
            label_bars_by_page.setdefault(row["page"], set()).add(true.bar)
    out = []
    for index, row in enumerate(rows):
        row["label_page_changes_meter"] = len(label_bars_by_page.get(row["page"], ())) > 1
        anchored = row["hole"] and row["bar"] > 0 and not (row["pickup"] and row["advance"] < row["bar"])
        if not anchored or row["advance"] == row["bar"]:
            continue
        verdict = "neither"
        if row["true_advance"] == row["bar"]:
            verdict = "fix"
        elif row["true_advance"] == row["advance"]:
            verdict = "harm"
        out.append({"id": item["id"], "engine": engine, "measure": index, "verdict": verdict,
                    **{key: (str(value) if isinstance(value, Fraction) else value) for key, value in row.items()}})
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ids", nargs="*")
    args = parser.parse_args()
    # Keyed by "id engine". Pages and labels are frozen, so an entry is reused while this file is
    # unchanged; a code change needs the ledger deleted.
    done: dict[str, list[dict[str, Any]]] = json.loads(OUTPUT.read_text()) if OUTPUT.is_file() else {}
    for item in manifest_items(("dev", "dev-b")):
        if args.ids and item["id"] not in args.ids:
            continue
        for engine in ENGINES:
            key = f"{item['id']} {engine}"
            result = RULER / "captures" / engine / item["id"] / "result.json"
            if key in done or not result.is_file() or json.loads(result.read_text())["status"] != "ok":
                continue
            done[key] = ledger(item, engine)
            OUTPUT.write_text(json.dumps(done, indent=1) + "\n", encoding="utf-8")
            print(key, dict(Counter(row["verdict"] for row in done[key])), flush=True)
    rows = [row for found in done.values() for row in found]
    print(json.dumps(Counter((row["engine"], row["verdict"]) for row in rows).most_common()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
