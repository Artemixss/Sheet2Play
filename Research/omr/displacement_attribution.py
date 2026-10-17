#!/usr/bin/env python3
"""Attribute displacement on the ruler's development set to the measures that cause it.

Phase 2 of the displacement plan. The Phase 1 captures keep each page's raw engine MusicXML,
so this runs on cached recognitions only, with no inference.

The app places a note at its page's offset plus its offset inside the page. music21 lays each
staff of the grand staff out as its own part, and a measure advances that staff's timeline by
its decoded length, so an overfull or underfull measure moves every later note on that staff
and page. A page then advances the timeline by its longest staff, rounded to whole bars
except on page one (`musicxml_normalizer._page_advance`). This script rebuilds that timeline
per staff and checks it reproduces the app's cached payload note for note, aligns the
predicted measures to the label's by pitch content (affine gaps), and gives every measure one
mechanism ("family: detail") from its features and, for 426, HOMR's own log.

A label measure's displacement is exact: its page's start error (the stitch errors of earlier
pages, each split between that page's mechanisms by Shapley shares, with page rounding as a
player) plus its offset from that page start (the length errors, extra and dropped measures,
and part rewinds before it on its page). Its notes are then split between the mechanisms by
Shapley shares of the binary in-place outcome, the unit onset F1 counts. Counterfactuals undo
one mechanism, one family, or all but one, and rebuild the timeline with page rounding.

Run it with the app's interpreter, so music21 is the app's version:

    Bridge\\.venv-homr-gpu\\Scripts\\python.exe -I -B Research/omr/displacement_attribution.py
    ... --ids 5079459   # one development score, for inspection

It needs `displacement_evidence.py index` first, for the 426 log.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from fractions import Fraction
from functools import cache
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[1]
sys.path.insert(0, str(WORKSPACE / "dist" / "Bridge"))

REPORT = HERE / "reports/displacement/phase2"
RULER = HERE / "data/displacement-ruler"
MANIFEST = HERE / "reports/displacement/phase1/manifest.json"
ENGINES = ("homr465", "homr")
MATCH_FLOOR = Fraction(3, 10)
GAP_OPEN = Fraction(1)
GAP_EXTEND = Fraction(1, 5)
MAX_PLAYERS = 10
GARBLED = Fraction(1, 2)  # pitch similarity below which a matched measure was not really read
ENGINE_LOG = RULER / "evidence/426-log.json"  # from displacement_evidence.py index


@cache
def engine_logs() -> dict[str, Any]:
    if not ENGINE_LOG.is_file():
        raise FileNotFoundError(f"{ENGINE_LOG} is missing: run displacement_evidence.py index first")
    return json.loads(ENGINE_LOG.read_text())


def engine_log(score: str, engine: str) -> dict[str, Any]:
    """The 426 subprocess log's per-page tuplet strips and re-timings; 465 logs neither."""
    return engine_logs()[score] if engine == "homr" else {}


def exact(value: float) -> Fraction:
    return Fraction(value).limit_denominator(4096)


@dataclass
class Measure:
    staff: int
    part: int  # the normalizer's part index; a page split into parts restarts at beat 0 per part
    page: int
    index: int  # within its page (prediction) or score (label)
    number: str
    start: Fraction  # page-local for predictions, absolute for the label
    advance: Fraction
    bar: Fraction | None
    signature: str | None
    pitches: Counter = field(default_factory=Counter)
    durations: Counter = field(default_factory=Counter)  # (midi, quarter length) per sounding pitch
    tremolos: int = 0  # notes under a 2:1 time modification, how MusicXML writes a two-note tremolo
    gaps: Fraction = Fraction(0)  # largest hole any voice leaves between its notes and rests
    notes: int = 0
    grace: int = 0
    tuplets: int = 0
    voices: int = 0
    chords: int = 0
    rests: Fraction = Fraction(0)
    new_system: bool = False
    new_page: bool = False
    reused: bool = False
    copy: bool = False  # inside a section that repeat expansion plays more than once


def load_measures(path: Path, page: int, expand: bool = True) -> tuple[list[list[Measure]], Fraction, Fraction]:
    """Per-staff measures as the app's normalizer lays them out, the page's decoded length, and
    the bar length its page advance rounds to."""
    import musicxml_normalizer as normalizer
    from music21 import converter, layout, meter, note, stream

    score = normalizer._prepare_score(
        lambda: normalizer._parse_musicxml_with_repair(converter, path, force_source=False),
        str(path), expand_repeats=expand)
    coordinates = normalizer._musicxml_part_coordinates(score.parts)
    staves: dict[int, list[Measure]] = defaultdict(list)
    for part in score.parts:
        part_index, staff = coordinates[id(part)]
        measures = list(part.getElementsByClass(stream.Measure))
        part_end = exact(part.highestTime)
        rows: list[Measure] = []
        played_twice = {number for number, count in Counter(str(measure.number) for measure in measures).items()
                        if count > 1}
        for index, measure in enumerate(measures):
            start = exact(measure.getOffsetInHierarchy(part))
            following = (exact(measures[index + 1].getOffsetInHierarchy(part))
                         if index + 1 < len(measures) else max(part_end, start + exact(measure.highestTime)))
            signature = measure.timeSignature or measure.getContextByClass(meter.TimeSignature)
            row = Measure(staff=staff, part=part_index, page=page, index=index, number=str(measure.number), start=start,
                          advance=following - start,
                          bar=exact(signature.barDuration.quarterLength) if signature else None,
                          signature=signature.ratioString if signature else None,
                          copy=str(measure.number) in played_twice)
            voices = set()
            for element in measure.recurse().notesAndRests:
                if isinstance(element, note.Rest):
                    row.rests += exact(element.duration.quarterLength)
                    continue
                if element.duration.isGrace:
                    row.grace += 1
                    continue
                row.notes += 1
                row.chords += int(len(element.pitches) > 1)
                row.tuplets += int(bool(element.duration.tuplets))
                row.tremolos += int(any(tuplet.numberNotesActual == 2 and tuplet.numberNotesNormal == 1
                                        for tuplet in element.duration.tuplets))
                for pitch in element.pitches:
                    row.pitches[pitch.midi] += 1
                    row.durations[(pitch.midi, exact(element.duration.quarterLength))] += 1
                container = element.getContextByClass(stream.Voice)
                voices.add(container.id if container is not None else "1")
            row.voices = len(voices)
            containers = [measure, *measure.getElementsByClass(stream.Voice)]
            for container in containers:
                cursor, holes = Fraction(0), Fraction(0)
                for element in sorted((element for element in container.getElementsByClass(note.GeneralNote)
                                       if not element.duration.isGrace), key=lambda element: element.offset):
                    start = exact(element.offset)
                    holes += max(start - cursor, Fraction(0))
                    cursor = max(cursor, start + exact(element.duration.quarterLength))
                if cursor:
                    row.gaps = max(row.gaps, holes)
            for system in measure.getElementsByClass(layout.SystemLayout):
                row.new_system |= bool(system.isNew)
            for page_layout in measure.getElementsByClass(layout.PageLayout):
                row.new_page |= bool(page_layout.isNew)
            rows.append(row)
        staves[staff].extend(rows)
    ordered = [sorted(staves[staff], key=lambda row: row.part) for staff in sorted(staves)]
    return ordered, exact(score.highestTime), exact(normalizer._extract_measure_beats(score))


def page_advance(length: Fraction, bar: Fraction, first: bool) -> Fraction:
    """`musicxml_normalizer._page_advance`, on exact fractions."""
    if first or bar <= 0 or length <= 0:
        return length
    count = round(length / bar)
    return length if count < 1 else count * bar


def similarity(left: Counter, right: Counter) -> Fraction:
    total = sum(left.values()) + sum(right.values())
    if total == 0:
        return Fraction(1)
    return Fraction(2 * sum((left & right).values()), total)


def align(predicted: list[Measure], truth: list[Measure]) -> list[tuple[int | None, int | None]]:
    """Global alignment of one staff's measures by pitch content, with affine gaps.

    Opening a gap costs more than extending one, so a lost system comes out as one run of
    dropped measures rather than scattered across repetitive passages that match equally well.
    """
    rows, cols = len(predicted), len(truth)
    low = Fraction(-10**9)
    # match[i][j]: ends pairing i-1 with j-1; up: ends with predicted i-1 unpaired; left: label j-1.
    match = [[low] * (cols + 1) for _ in range(rows + 1)]
    up = [[low] * (cols + 1) for _ in range(rows + 1)]
    left = [[low] * (cols + 1) for _ in range(rows + 1)]
    back: dict[tuple[str, int, int], str] = {}
    match[0][0] = Fraction(0)
    for i in range(1, rows + 1):
        up[i][0] = -GAP_OPEN - (i - 1) * GAP_EXTEND
        back[("up", i, 0)] = "up" if i > 1 else "match"
    for j in range(1, cols + 1):
        left[0][j] = -GAP_OPEN - (j - 1) * GAP_EXTEND
        back[("left", 0, j)] = "left" if j > 1 else "match"
    for i in range(1, rows + 1):
        for j in range(1, cols + 1):
            gain = similarity(predicted[i - 1].pitches, truth[j - 1].pitches) - MATCH_FLOOR
            best = max((match[i - 1][j - 1], "match"), (up[i - 1][j - 1], "up"), (left[i - 1][j - 1], "left"),
                       key=lambda option: option[0])
            match[i][j], back[("match", i, j)] = best[0] + gain, best[1]
            best = max((match[i - 1][j] - GAP_OPEN, "match"), (up[i - 1][j] - GAP_EXTEND, "up"),
                       (left[i - 1][j] - GAP_OPEN, "left"), key=lambda option: option[0])
            up[i][j], back[("up", i, j)] = best
            best = max((match[i][j - 1] - GAP_OPEN, "match"), (left[i][j - 1] - GAP_EXTEND, "left"),
                       (up[i][j - 1] - GAP_OPEN, "up"), key=lambda option: option[0])
            left[i][j], back[("left", i, j)] = best
    tables = {"match": match, "up": up, "left": left}
    state = max(tables, key=lambda name: (tables[name][rows][cols], name == "match"))
    pairs: list[tuple[int | None, int | None]] = []
    i, j = rows, cols
    while i or j:
        previous = back[(state, i, j)]
        if state == "match":
            pairs.append((i - 1, j - 1))
            i, j = i - 1, j - 1
        elif state == "up":
            pairs.append((i - 1, None))
            i -= 1
        else:
            pairs.append((None, j - 1))
            j -= 1
        state = previous
    return pairs[::-1]


LOST_PAGE = "lost page (previous page reused)"
PARALLEL = "page split into parallel parts"
DROPPED_SYSTEM = "dropped system"
REPEAT = "repeat expansion"


def app_pages(item: dict[str, Any], engine: str) -> list[tuple[Path, bool]]:
    """The page files the app normalized, and whether each stands in for a missing page.

    `bridge.select_generated_output` falls back to any MusicXML modified in the two seconds
    before a run, so a 426 page that writes nothing reuses the page written just before it.
    """
    folder = RULER / "captures" / engine / item["id"] / "pages"
    count = json.loads((folder.parent / "result.json").read_text())["pages"]
    pages: list[tuple[Path, bool]] = []
    for number in range(1, count + 1):
        path = folder / f"page-{number:04d}.musicxml"
        if path.is_file():
            pages.append((path, False))
        elif pages:
            pages.append((pages[-1][0], True))
        else:
            raise FileNotFoundError(f"{item['id']} {engine}: page 1 has no MusicXML")
    return pages


@dataclass
class PageContext:
    """What classification needs to know about the page a measure sits on."""
    label_meters: set[Fraction]  # bar lengths the label uses on this page
    systems_match: bool  # the engine found as many systems as the label has
    stripped: set[str] = field(default_factory=set)  # 426 log: measures stripped of tuplets
    retimed: set[str] = field(default_factory=set)  # 426 log: measures re-timed to the page meter


def classify(pred: Measure | None, true: Measure | None, context: PageContext | None) -> str:
    """One mechanism per measure, "family: detail", in a fixed order of precedence.

    Causes come before co-occurrences: a measure whose content was not read at all is garbled
    whatever its meter, and a measure counts as a meter error only when it decoded to exactly
    the page's computed meter while the true bar differs.
    """
    if pred is not None and pred.reused:
        return LOST_PAGE
    if (pred is None and true is not None and true.copy) or (true is None and pred is not None and pred.copy):
        return REPEAT
    if pred is None:
        return "dropped measure"
    if true is None:
        return "extra measure"
    if pred.advance == true.advance:
        return "correct length"
    if similarity(pred.pitches, true.pitches) < GARBLED:
        if context is not None and not context.systems_match:
            return "garbled measure: system mis-detected on the page"
        return "garbled measure: content does not match"
    if pred.durations == true.durations:
        # Every pitch was read with its true duration, yet the measure's length is wrong: the
        # MusicXML places the notes wrongly (voices, backups), which TrOmr's tokens leave to
        # HOMR's exporter.
        return "layout: every note right, placed wrong in the MusicXML"
    if pred.gaps > true.gaps:
        # Some voice has holes the label does not: the exporter placed notes past where their
        # voice's own durations reach, whatever else the measure got wrong.
        return "layout: notes placed with gaps, other errors too"
    # Without re-timing a written meter cannot change a measure's decoded length (music21 lays a
    # measure out by its content), so meter counts only where 426 re-timed toward it.
    if context is not None and pred.number in context.retimed:
        return "meter: re-timed by HOMR to the page meter"
    if true.bar and true.advance != true.bar:
        return "irregular measure (pickup or short bar)"
    if true.tremolos and not pred.tuplets:
        return "tuplet: two-note tremolo read as plain notes"
    if true.tuplets or pred.tuplets:
        # The log names measures `_fix_over_eager_tuplets` stripped; the exporter can re-infer
        # tuplets afterwards, so it counts only where the measure really ends up without any.
        if context is not None and pred.number in context.stripped and not pred.tuplets:
            return "tuplet: stripped by HOMR's tuplet heuristic"
        if not pred.tuplets:
            return "tuplet: missing in the prediction"
        if not true.tuplets:
            return "tuplet: added by the prediction"
        return "tuplet: timing differs"
    if true.grace and pred.notes > true.notes:
        return "grace note read as a note"
    family = "overflow" if pred.advance > true.advance else "underflow"
    if pred.voices != true.voices:
        return f"{family}: voice structure differs"
    if pred.notes != true.notes:
        return f"{family}: note count differs"
    return f"{family}: durations differ"


ROUNDING = "page rounding"


def page_lengths(staves: list[list[dict[str, Any]]], undo: set[str]) -> dict[tuple[int, int, int], Fraction]:
    """Decoded length of every (staff, page, part) run with the given mechanisms undone."""
    lengths: dict[tuple[int, int, int], Fraction] = defaultdict(Fraction)
    for staff, entries in enumerate(staves):
        for entry in entries:
            mechanism = entry["mechanism"]
            if entry["pred"] is None and mechanism not in undo:
                continue
            if entry["true"] is None and mechanism in undo:
                continue
            key = (staff, entry["page"], 0 if PARALLEL in undo else entry["part"])
            lengths[key] += entry["true_advance"] if mechanism in undo else entry["pred_advance"]
    return lengths


def advance_of(lengths: dict[tuple[int, int, int], Fraction], page: int, bar: Fraction, undo: set[str]) -> Fraction:
    longest = max((length for key, length in lengths.items() if key[1] == page), default=Fraction(0))
    return longest if ROUNDING in undo else page_advance(longest, bar, page == 0)


def simulate(staves: list[list[dict[str, Any]]], page_bars: list[Fraction],
             undo: set[str]) -> tuple[dict[int, list[Fraction | None]], list[Fraction]]:
    """Rebuild every staff's measure starts with the given mechanisms' events undone.

    Undoing a matched measure's mechanism gives it the label length; undoing an extra measure
    removes it; undoing a dropped one restores it; undoing the parallel-part split lays a page's
    parts end to end; undoing page rounding advances each page by its longest staff unrounded.
    Returns, per staff, the absolute start of every label measure (None where it was dropped and
    stays dropped), and the page offsets.
    """
    lengths = page_lengths(staves, undo)
    offsets, offset = [], Fraction(0)
    for page, bar in enumerate(page_bars):
        offsets.append(offset)
        offset += advance_of(lengths, page, bar, undo)
    running: dict[tuple[int, int, int], Fraction] = defaultdict(Fraction)
    starts: dict[int, list[Fraction | None]] = {}
    for staff, entries in enumerate(staves):
        count = 1 + max((entry["true"] for entry in entries if entry["true"] is not None), default=-1)
        row: list[Fraction | None] = [None] * count
        for entry in entries:
            mechanism = entry["mechanism"]
            if entry["pred"] is None and mechanism not in undo:
                continue
            if entry["true"] is None and mechanism in undo:
                continue
            key = (staff, entry["page"], 0 if PARALLEL in undo else entry["part"])
            if entry["true"] is not None:
                row[entry["true"]] = offsets[entry["page"]] + running[key]
            running[key] += entry["true_advance"] if mechanism in undo else entry["pred_advance"]
        starts[staff] = row
    return starts, offsets


def shapley(players: list[str], value: Any) -> dict[str, Fraction]:
    """Exact Shapley shares of value(all players) - value(none)."""
    from itertools import combinations
    from math import factorial

    count = len(players)
    cache: dict[frozenset[str], Fraction] = {}

    def worth(members: frozenset[str]) -> Fraction:
        if members not in cache:
            cache[members] = value(set(members))
        return cache[members]

    shares: dict[str, Fraction] = {}
    for player in players:
        others = [other for other in players if other != player]
        total = Fraction(0)
        for size in range(len(others) + 1):
            weight = Fraction(factorial(size) * factorial(count - size - 1), factorial(count))
            for members in combinations(others, size):
                coalition = frozenset(members)
                total += weight * (worth(coalition | {player}) - worth(coalition))
        shares[player] = total
    return shares


def attribute(item: dict[str, Any], engine: str) -> dict[str, Any]:
    page_files = app_pages(item, engine)
    pages = [path for path, _ in page_files]
    repeat = repeat_across_pages(HERE / item["label"])
    # The app expands repeats one page at a time. Where the label's repeat spans a page break,
    # the true and played orders differ from the first repeat on, and no page model fits both;
    # that effect is measured on the label alone, and the rest is attributed unexpanded.
    expand = repeat is None
    truth_staves, _, _ = load_measures(HERE / item["label"], 0, expand)
    predicted_pages = [load_measures(page, number, expand) for number, page in enumerate(pages)]
    for (_, reused), (staves, _, _) in zip(page_files, predicted_pages):
        for measure in (measure for staff in staves for measure in staff):
            measure.reused = reused
    staff_count = len(truth_staves)
    if any(len(staves) != staff_count for staves, _, _ in predicted_pages):
        return {"status": "staff_count_mismatch",
                "pages": [len(staves) for staves, _, _ in predicted_pages], "truth": staff_count}
    page_bars = [bar for _, _, bar in predicted_pages]
    label_page, page_index = [], 0
    for measure in truth_staves[0]:
        page_index += int(measure.new_page and measure.index > 0)
        label_page.append(page_index)
    if page_index + 1 != len(pages):
        return {"status": "page_count_mismatch", "pages": len(pages), "label_pages": page_index + 1}
    label_systems = [0] * len(pages)
    for measure, page in zip(truth_staves[0], label_page):
        label_systems[page] += int(measure.index == 0 or measure.new_system or measure.new_page)
    detected_systems = [sum(int(measure.index == 0 or measure.new_system) for measure in staves[0])
                        for staves, _, _ in predicted_pages]
    first_of_page = [label_page.index(page) for page in range(len(pages))]
    truth_page_start = [truth_staves[0][index].start for index in first_of_page]
    label_end = truth_staves[0][-1].start + truth_staves[0][-1].advance
    truth_page_length = [following - start for start, following
                         in zip(truth_page_start, truth_page_start[1:] + [label_end])]
    log = engine_log(item["id"], engine)

    def logged(number: int, key: str) -> set[str]:
        # The log numbers measures as HOMR's token grouping does; trust it only on pages where
        # that grouping and the exported MusicXML have the same number of measures.
        entry = log.get(str(number + 1), {})
        tokens = sum(len(system) for system in entry.get("systems", []))
        exported = len({measure.number for measure in predicted_pages[number][0][0] if measure.part == 0})
        if not entry or tokens != exported:
            return set()
        return {str(value[0] if isinstance(value, list) else value) for value in entry.get(key, [])}

    contexts = [PageContext(
        label_meters={measure.bar for measure, page in zip(truth_staves[0], label_page) if page == number and measure.bar},
        systems_match=detected_systems[number] == label_systems[number],
        stripped=logged(number, "stripped"),
        retimed=logged(number, "retimed"),
    ) for number in range(len(pages))]

    entries_by_staff: list[list[dict[str, Any]]] = []
    measures_by_staff: list[list[Measure]] = []
    for staff in range(staff_count):
        predicted = [measure for staves, _, _ in predicted_pages for measure in staves[staff]]
        truth = truth_staves[staff]
        entries: list[dict[str, Any]] = []
        for left, right in align(predicted, truth):
            pred = predicted[left] if left is not None else None
            true = truth[right] if right is not None else None
            entries.append({
                "page": pred.page if pred is not None else label_page[right],
                "part": pred.part if pred is not None else 0, "pred": left, "true": right,
                "pred_advance": pred.advance if pred else None,
                "true_advance": true.advance if true else None,
                "mechanism": classify(pred, true, contexts[pred.page] if pred is not None else None),
            })
        mark_lost_pages(entries)
        mark_dropped_systems(entries, label_page, label_systems, detected_systems)
        entries_by_staff.append(entries)
        measures_by_staff.append(predicted)

    baseline, offsets = simulate(entries_by_staff, page_bars, set())
    decoded_end = offsets[-1] + page_advance(predicted_pages[-1][1], page_bars[-1], len(pages) == 1)
    check_timeline(item, engine, pages, offsets, decoded_end, expand)

    # Across pages: each page break moves every later note by the page's stitch error, its
    # advance minus its label length. Shapley shares split it between the mechanisms on that
    # page; what remains with all of them undone is the app's rounding itself.
    stitches: list[dict[str, Any]] = []
    for page in range(len(pages) - 1):
        on_page = [[entry for entry in entries if entry["page"] == page] for entries in entries_by_staff]

        def error(undo: set[str], on_page: list[list[dict[str, Any]]] = on_page, page: int = page) -> Fraction:
            return advance_of(page_lengths(on_page, undo), page, page_bars[page], undo) - truth_page_length[page]

        players = sorted({entry["mechanism"] for entries in on_page for entry in entries if effective(entry)}
                         | ({PARALLEL} if any(entry["part"] for entries in on_page for entry in entries) else set()))
        players.append(ROUNDING)
        total = error(set())
        shares = shapley(players, lambda undo: total - error(undo)) if total else {}
        residual = error(set(players))
        if residual:
            shares["alignment residual"] = residual
        stitches.append({"page": page + 1, "error": total, "shares": {key: value for key, value in shares.items() if value}})

    # Within a page: a staff's offset from its page start moves by each measure's own length
    # error and by every extra or dropped measure before it. Each label measure's displacement
    # is the sum of those and the stitch errors of earlier pages; its notes are split among them.
    note_weight = {staff: [measure.notes for measure in truth_staves[staff]] for staff in range(staff_count)}
    total_notes = sum(sum(weights) for weights in note_weight.values())
    drift: dict[str, Fraction] = defaultdict(Fraction)
    displaced: dict[str, Fraction] = defaultdict(Fraction)
    lost: dict[str, int] = defaultdict(int)
    events: list[dict[str, Any]] = []
    total_drift, total_displaced, approximated = Fraction(0), 0, 0
    for staff, entries in enumerate(entries_by_staff):
        context, contributions, last_part = None, [], None
        for entry in entries:
            if entry["page"] != context:
                context, contributions, last_part = entry["page"], [], None
            true, left = entry["true"], entry["pred"]
            pred = measures_by_staff[staff][left] if left is not None else None
            truth_measure = truth_staves[staff][true] if true is not None else None
            if true is None:
                contributions.append((entry["mechanism"], entry["pred_advance"]))
                events.append(event_row(item, engine, staff, entry, pred, None, entry["pred_advance"]))
                continue
            if pred is None:
                lost[entry["mechanism"]] += note_weight[staff][true]
                contributions.append((entry["mechanism"], -entry["true_advance"]))
                events.append(event_row(item, engine, staff, entry, None, truth_measure, -entry["true_advance"]))
                continue
            page = entry["page"]
            local = baseline[staff][true] - offsets[page] - (truth_measure.start - truth_page_start[page])
            residual = local - sum((beats for _, beats in contributions), Fraction(0))
            if residual:
                label = PARALLEL if last_part is not None and last_part != entry["part"] else "alignment residual"
                contributions.append((label, residual))
                events.append(event_row(item, engine, staff, entry, pred, truth_measure, residual, mechanism=label))
            offset = baseline[staff][true] - truth_measure.start
            parts = [(key, value) for stitch in stitches[:page] for key, value in stitch["shares"].items()]
            parts = [(f"{key} (across pages)", value) for key, value in parts] + contributions
            if sum((value for _, value in parts), Fraction(0)) != offset:
                raise AssertionError(f"{item['id']} {engine}: staff {staff} measure {truth_measure.number} "
                                     f"contributions do not sum to its offset {offset}")
            weight = note_weight[staff][true]
            if offset and weight:
                sign = 1 if offset > 0 else -1
                total_drift += weight * abs(offset)
                total_displaced += weight
                by_key: dict[str, Fraction] = defaultdict(Fraction)
                for key, value in parts:
                    drift[key] += weight * value * sign
                    by_key[key] += value
                # Which mechanisms, undone, would put this measure back: Shapley shares of the
                # binary outcome, so partly cancelling mechanisms split the blame, not net it.
                players = [key for key, value in by_key.items() if value]
                if len(players) <= MAX_PLAYERS:
                    shares = shapley(players, lambda undo: Fraction(int(
                        sum((value for key, value in by_key.items() if key not in undo), Fraction(0)) == 0)))
                else:  # exact Shapley is exponential; share by size instead, and count how often
                    scale = sum((abs(by_key[key]) for key in players), Fraction(0))
                    shares = {key: abs(by_key[key]) / scale for key in players}
                    approximated += weight
                for key, share in shares.items():
                    displaced[key] += weight * share
            own = entry["pred_advance"] - entry["true_advance"]
            if own:
                contributions.append((entry["mechanism"], own))
                events.append(event_row(item, engine, staff, entry, pred, truth_measure, own))
            last_part = entry["part"]

    truth_starts = {staff: [measure.start for measure in truth_staves[staff]] for staff in range(staff_count)}

    def in_place(starts: dict[int, list[Fraction | None]]) -> float:
        hit = sum(weight for staff in starts for start, true_start, weight
                  in zip(starts[staff], truth_starts[staff], note_weight[staff])
                  if start is not None and start == true_start)
        return round(hit / total_notes, 4) if total_notes else 0.0

    mechanisms = sorted({entry["mechanism"] for entries in entries_by_staff for entry in entries}
                        | {PARALLEL, ROUNDING})
    impact: dict[str, Any] = {"baseline": in_place(baseline), "undo_one": {}, "undo_all_but": {}}
    for mechanism in mechanisms:
        impact["undo_one"][mechanism] = in_place(simulate(entries_by_staff, page_bars, {mechanism})[0])
        impact["undo_all_but"][mechanism] = in_place(
            simulate(entries_by_staff, page_bars, set(mechanisms) - {mechanism})[0])
    impact["undo_all"] = in_place(simulate(entries_by_staff, page_bars, set(mechanisms))[0])
    families: dict[str, set[str]] = defaultdict(set)
    for mechanism in mechanisms:
        families[mechanism.split(":")[0]].add(mechanism)
    impact["undo_family"] = {family: in_place(simulate(entries_by_staff, page_bars, members)[0])
                             for family, members in families.items()}
    impact["undo_all_but_family"] = {family: in_place(simulate(entries_by_staff, page_bars,
                                                               set(mechanisms) - members)[0])
                                     for family, members in families.items()}
    return {"status": "ok", "expanded": expand, "repeat_across_pages": repeat,
            "pages": len(pages), "staves": staff_count,
            "label_systems_per_page": label_systems, "detected_systems_per_page": detected_systems,
            "truth_measures": [len(staff) for staff in truth_staves],
            "predicted_measures": [len(staff) for staff in measures_by_staff],
            "notes": total_notes, "decoded_end": str(decoded_end),
            "reused_pages": [index + 1 for index, (_, reused) in enumerate(page_files) if reused],
            "page_bars": [str(bar) for bar in page_bars],
            "drift_note_beats": float(total_drift), "displaced_notes": total_displaced,
            "displaced_notes_shared_by_size": approximated,
            "drift_by_mechanism": {key: float(value) for key, value in sorted(drift.items()) if value},
            "displaced_by_mechanism": {key: float(value) for key, value in sorted(displaced.items()) if value},
            "lost_notes_by_mechanism": dict(sorted(lost.items())),
            "stitches": [{"page": stitch["page"], "error": str(stitch["error"]),
                          "shares": {key: str(value) for key, value in stitch["shares"].items()}}
                         for stitch in stitches],
            "impact": impact, "events": events}


def expand_order(marks: list[tuple[bool, bool]], start: int, stop: int) -> list[int]:
    """Measure order for simple repeats within [start, stop): an end repeat without a start
    repeats from `start`, as music21 does. Each end repeat is taken once."""
    order, index, back, taken = [], start, start, set()
    while index < stop:
        opens, closes = marks[index]
        if opens and index not in taken:
            back = index
        order.append(index)
        if closes and index not in taken:
            taken.add(index)
            index = back
            continue
        index += 1
    return order


def repeat_across_pages(label: Path) -> dict[str, Any] | None:
    """Where the label's repeats play differently when each page is expanded on its own.

    Returns None when page-wise expansion gives the true order. Otherwise reports the first
    label measure where the orders part, and the truly played notes from there on: those are
    displaced or missing whatever the engine reads.
    """
    from music21 import converter, layout, stream

    score = converter.parse(label)
    parts = list(score.parts)
    measures = list(parts[0].getElementsByClass(stream.Measure))

    def direction(barline: Any) -> str | None:
        return getattr(barline, "direction", None) if barline is not None else None

    marks = [(direction(measure.leftBarline) == "start", direction(measure.rightBarline) == "end")
             for measure in measures]
    if not any(opens or closes for opens, closes in marks):
        return None
    breaks = [index for index, measure in enumerate(measures) if index and any(
        getattr(page, "isNew", False) for page in measure.getElementsByClass(layout.PageLayout))]
    bounds = [0, *breaks, len(measures)]
    true_order = expand_order(marks, 0, len(measures))
    app_order = [index for start, stop in zip(bounds, bounds[1:]) for index in expand_order(marks, start, stop)]
    if true_order == app_order:
        return None
    split = next((position for position, (left, right) in enumerate(zip(true_order, app_order)) if left != right),
                 min(len(true_order), len(app_order)))
    notes = [sum(sum(1 for element in part.getElementsByClass(stream.Measure)[index].recurse().notes
                     if not element.duration.isGrace) for part in parts)
             for index in range(len(measures))]
    return {"true_measures": len(true_order), "app_measures": len(app_order),
            "first_divergence_played_measure": split + 1,
            "first_divergence_label_measure": str(measures[true_order[split]].number) if split < len(true_order) else None,
            "notes_from_divergence": sum(notes[index] for index in true_order[split:]),
            "played_notes": sum(notes[index] for index in true_order)}


def effective(entry: dict[str, Any]) -> bool:
    """Whether undoing this entry's mechanism changes any length."""
    if entry["pred"] is None or entry["true"] is None:
        return True
    return entry["pred_advance"] != entry["true_advance"]


def mark_lost_pages(entries: list[dict[str, Any]]) -> None:
    """A label measure dropped next to a reused page, or next to one so marked, was lost with it."""
    changed = True
    while changed:
        changed = False
        for position, entry in enumerate(entries):
            if entry["pred"] is not None or entry["mechanism"] == LOST_PAGE:
                continue
            neighbours = [entries[index] for index in (position - 1, position + 1) if 0 <= index < len(entries)]
            if any(neighbour["mechanism"] == LOST_PAGE for neighbour in neighbours):
                entry["mechanism"], changed = LOST_PAGE, True


def mark_dropped_systems(entries: list[dict[str, Any]], label_page: list[int], label_systems: list[int],
                         detected_systems: list[int]) -> None:
    """A run of three or more dropped label measures, on a page where the engine found fewer
    systems than the label has, is a lost system. The run's edges can be off by a measure or two
    in repetitive music, so they need not fall on system breaks."""
    position = 0
    while position < len(entries):
        if entries[position]["pred"] is not None or entries[position]["mechanism"] != "dropped measure":
            position += 1
            continue
        end = position
        while (end + 1 < len(entries) and entries[end + 1]["pred"] is None
               and entries[end + 1]["mechanism"] == "dropped measure"):
            end += 1
        page = label_page[entries[position]["true"]]
        if end - position >= 2 and detected_systems[page] < label_systems[page]:
            for index in range(position, end + 1):
                entries[index]["mechanism"] = DROPPED_SYSTEM
        position = end + 1


def check_timeline(item: dict[str, Any], engine: str, pages: list[Path], offsets: list[Fraction],
                   decoded_end: Fraction, expand: bool) -> None:
    """Fail unless the rebuilt page offsets are the normalizer's under the same repeat flag, and
    the cached payload is this output."""
    import musicxml_normalizer as normalizer

    normalized = [normalizer.normalize_musicxml(page, expand_repeats=expand) for page in pages]
    app_offsets, offset = [], 0.0
    for index, page in enumerate(normalized):
        app_offsets.append(offset)
        offset += normalizer._page_advance(page, index == 0)
    rebuilt = [float(value) for value in offsets] + [float(decoded_end)]
    if any(abs(left - right) > 1e-6 for left, right in zip(rebuilt, app_offsets + [offset])):
        raise AssertionError(f"{item['id']} {engine}: rebuilt offsets {offsets} != app {app_offsets}")
    if not expand:
        normalized = [normalizer.normalize_musicxml(page) for page in pages]
    # The cached payload is what the app produced. Under this interpreter the pages must give it
    # note for note, or the music21 here lays the score out differently from the app's.
    payload = json.loads((RULER / "captures" / engine / item["id"] / "payload.json").read_text())
    combined = normalizer.combine_score_pages(normalized)

    def key(start: float, pitch: int, duration: float) -> tuple[int, int, int]:
        return round(start * 1e6), pitch, round(duration * 1e6)

    played = sorted(key(note["start_beat"], note["midi_pitch"], note["duration_beats"]) for note in payload["notes"])
    rebuilt_notes = sorted(key(note.start_beat, note.midi_pitch, note.duration_beats) for note in combined.notes)
    if played != rebuilt_notes:
        raise AssertionError(f"{item['id']} {engine}: the pages do not reproduce the app's payload here")


def event_row(item: dict[str, Any], engine: str, staff: int, entry: dict[str, Any], pred: Measure | None,
              true: Measure | None, beats: Fraction, *, mechanism: str | None = None) -> dict[str, Any]:
    return {
        "id": item["id"], "engine": engine, "staff": staff, "part": pred.part if pred else None,
        "mechanism": mechanism or entry["mechanism"],
        "beats": str(beats), "abs_beats": float(abs(beats)),
        "page": pred.page + 1 if pred else entry["page"] + 1,
        "page_measure": pred.index + 1 if pred else None,
        "label_measure": true.number if true else None,
        "label_index": entry["true"],
        "pred_advance": str(pred.advance) if pred else None,
        "true_advance": str(true.advance) if true else None,
        "pred_bar": str(pred.bar) if pred and pred.bar else None,
        "true_bar": str(true.bar) if true and true.bar else None,
        "pred_signature": pred.signature if pred else None,
        "true_signature": true.signature if true else None,
        "pred_notes": pred.notes if pred else None, "true_notes": true.notes if true else None,
        "pred_tuplets": pred.tuplets if pred else None, "true_tuplets": true.tuplets if true else None,
        "true_grace": true.grace if true else None,
        "pred_voices": pred.voices if pred else None, "true_voices": true.voices if true else None,
        "pred_chords": pred.chords if pred else None, "true_chords": true.chords if true else None,
        "pred_rests": str(pred.rests) if pred else None, "true_rests": str(true.rests) if true else None,
        "similarity": float(similarity(pred.pitches, true.pitches)) if pred and true else None,
        "pred_new_system": pred.new_system if pred else None,
        "true_new_system": true.new_system if true else None,
    }


RESIDUALS = {"alignment residual", "unexplained"}


def ledger(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Pool the per-score attributions into one ledger per engine.

    Shares are of displaced label notes (a note whose measure starts off its true place), the
    unit onset F1 loses, and of drift in note-beats. Within-page and across-page parts of a
    mechanism are reported together and separately. A negative share is a mechanism that
    cancelled others' displacement.
    """
    summary: dict[str, Any] = {}
    for engine in ENGINES:
        scored = {score: row[engine] for score, row in rows.items() if row[engine]["status"] == "ok"}
        displaced: dict[str, float] = defaultdict(float)
        across: dict[str, float] = defaultdict(float)
        drift: dict[str, float] = defaultdict(float)
        lost: dict[str, int] = defaultdict(int)
        scores: dict[str, set[str]] = defaultdict(set)
        fix_alone: dict[str, float] = defaultdict(float)
        only_left: dict[str, float] = defaultdict(float)
        gained: dict[str, float] = defaultdict(float)
        for score, row in scored.items():
            # Gained beats as the plan defines them: every measure's decoded length against the
            # label's, every extra or dropped measure, each parallel-part rewind, and what page
            # rounding itself adds at a page break.
            for event in row["events"]:
                gained[event["mechanism"]] += event["abs_beats"]
            for stitch in row["stitches"]:
                gained[ROUNDING] += abs(float(Fraction(stitch["shares"].get(ROUNDING, "0"))))
            for key, value in row["displaced_by_mechanism"].items():
                mechanism = key.removesuffix(" (across pages)")
                displaced[mechanism] += value
                if key != mechanism:
                    across[mechanism] += value
                if row["displaced_notes"] and value / row["displaced_notes"] >= 0.05:
                    scores[mechanism].add(score)
            for key, value in row["drift_by_mechanism"].items():
                drift[key.removesuffix(" (across pages)")] += value
            for key, value in row["lost_notes_by_mechanism"].items():
                lost[key] += value
            impact = row["impact"]
            for mechanism, value in impact["undo_one"].items():
                fix_alone[mechanism] += value - impact["baseline"]
            for mechanism, value in impact["undo_all_but"].items():
                only_left[mechanism] += impact["undo_all"] - value
        total_displaced = sum(row["displaced_notes"] for row in scored.values())
        total_drift = sum(row["drift_note_beats"] for row in scored.values())
        notes = sum(row["notes"] for row in scored.values())
        count = len(scored)
        total_gained = sum(gained.values())
        mechanisms = sorted(set(displaced) | set(lost) | set(fix_alone) | set(gained),
                            key=lambda key: -displaced.get(key, 0.0))
        summary[engine] = {
            "scores": count, "label_notes": notes, "displaced_notes": total_displaced,
            "displaced_share_of_notes": round(total_displaced / notes, 4) if notes else None,
            "lost_notes": sum(lost.values()),
            "notes_in_place_mean": round(sum(row["impact"]["baseline"] for row in scored.values()) / count, 4),
            "named_share_of_displaced": round(sum(value for key, value in displaced.items() if key not in RESIDUALS)
                                              / total_displaced, 4) if total_displaced else None,
            "gained_beats": round(total_gained, 2),
            "mechanisms": {mechanism: {
                "displaced_share": round(displaced.get(mechanism, 0.0) / total_displaced, 4) if total_displaced else 0.0,
                "across_pages_share": round(across.get(mechanism, 0.0) / total_displaced, 4) if total_displaced else 0.0,
                "drift_share": round(drift.get(mechanism, 0.0) / total_drift, 4) if total_drift else 0.0,
                "gained_beats": round(gained.get(mechanism, 0.0), 2),
                "gained_share": round(gained.get(mechanism, 0.0) / total_gained, 4) if total_gained else 0.0,
                "lost_notes": lost.get(mechanism, 0),
                "scores_at_5pct": len(scores.get(mechanism, ())),
                "fix_alone_mean_gain": round(fix_alone.get(mechanism, 0.0) / count, 4),
                "only_left_mean_loss": round(only_left.get(mechanism, 0.0) / count, 4),
            } for mechanism in mechanisms},
            "repeat_across_pages": {score: row["repeat_across_pages"] for score, row in scored.items()
                                    if row["repeat_across_pages"]},
        }
        families: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        for mechanism, values in summary[engine]["mechanisms"].items():
            family = families[mechanism.split(":")[0]]
            for key in ("displaced_share", "across_pages_share", "drift_share", "gained_beats", "gained_share",
                        "lost_notes"):
                family[key] = round(family[key] + values[key], 4)
        for name in families:
            families[name]["fix_alone_mean_gain"] = round(sum(
                row["impact"]["undo_family"].get(name, row["impact"]["baseline"]) - row["impact"]["baseline"]
                for row in scored.values()) / count, 4)
            families[name]["only_left_mean_loss"] = round(sum(
                row["impact"]["undo_all"] - row["impact"]["undo_all_but_family"].get(name, row["impact"]["undo_all"])
                for row in scored.values()) / count, 4)
        summary[engine]["families"] = dict(sorted(((name, dict(values)) for name, values in families.items()),
                                                  key=lambda item: -item[1]["displaced_share"]))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ids", nargs="*")
    parser.add_argument("--output", type=Path, default=REPORT / "attribution.json")
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text())
    items = [item for item in manifest["items"] if (item["id"] in args.ids if args.ids else item["split"] == "dev")]
    if any(item["split"] != "dev" for item in items):
        parser.error("Phase 2 diagnoses the development split only; test stays held out")
    rows: dict[str, dict[str, Any]] = {}
    for item in items:
        rows[item["id"]] = {}
        for engine in ENGINES:
            result = json.loads((RULER / "captures" / engine / item["id"] / "result.json").read_text())
            if result["status"] != "ok":
                rows[item["id"]][engine] = {"status": result["status"], "code": result.get("code")}
                continue
            rows[item["id"]][engine] = attribute(item, engine)
            print(item["id"], engine, rows[item["id"]][engine]["status"], flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    summary = ledger(rows)
    report = {"manifest": "../phase1/manifest.json", "split": "dev", "ledger": summary, "rows": rows}
    args.output.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    write_compact(report, args.output.with_name("ledger.json"))
    print(json.dumps(summary, indent=1))
    return 0


def write_compact(report: dict[str, Any], path: Path) -> None:
    """The tracked record: the ledger and every score's summary, without the event lists, which
    `attribution.json` keeps and which this script rebuilds from the local captures."""
    rows = {score: {engine: {key: value for key, value in row.items() if key != "events"}
                    for engine, row in engines.items()} for score, engines in report["rows"].items()}
    path.write_text(json.dumps({**report, "rows": rows, "full": path.with_name("attribution.json").name},
                               indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
