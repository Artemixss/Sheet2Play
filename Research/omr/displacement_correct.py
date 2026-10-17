#!/usr/bin/env python3
"""Blind displacement corrections on cached recognitions, scored against the ruler's labels.

Phase 3 of the displacement plan. Every variant rewrites only where notes start, from the
engine's own page MusicXML: no inference, no labels. The control reproduces the app, and the
script fails unless it matches the app's cached payload note for note.

Variants (a part's measures are re-laid from the page start, both staves alike; notes keep
their place inside their measure; an opening pickup on page one always keeps its length):

- control: the app as shipped. music21 advances each staff by its measures' decoded lengths.
- anchor: every measure advances by its bar length, HOMR's computed page meter (C2 in the plan).
- anchor-holes: a measure advances by its bar length only where some voice leaves a hole
  between two of its notes, the mark of the lost `<backup>` Phase 2 found; every other measure
  keeps its decoded length, so correctly read meter changes survive.
- anchor-holes-local3, -local6: as anchor-holes, but the length is the most common decoded
  length among hole-free measures within 3 or 6 measures, falling back to the page meter.

Tried on the development set and dropped (see the Phase 3 report): keeping lengths that both
staves agree on (they come from one MusicXML part, so they almost always agree), keeping
recurring or repeated lengths (errors recur too), anchoring only over-long measures, splitting
pages at HOMR's time-signature marks, and packing voices to close their holes (it moves onsets
that were right).

Phase 3 replan (option 1, a meter-change gate; option 2, layout repair), developed on dev and
the meter-change set dev-b (`displacement_heldout.py`):

- anchor-holes-OPTIONS: anchor-holes with gates, joined by "-": keepN keeps a hole measure's
  length when N hole-free measures on the page share it (a recurring real meter); nb also when a
  hole-free neighbour does; cover when some voice spells the decoded length out from beat 0;
  coverunder, cover for short measures only.
- fit, fit+VARIANT: in a measure longer than the page meter, every voice that runs past the bar
  moves earlier to end on it, all or nothing (`fit_shifts`); then VARIANT (default: decoded).
- place, place+VARIANT: 465 only. Runs of a voice re-placed from the page's note positions
  (`imgpos`) where they start later than notes clearly to their right (`place_measure`).

Dropped on dev and dev-b: the cover gates (they cost most of the gain), and, in the per-measure
ledger `displacement_meter.py`, gates on x inversions, measure width, the page's share of
measures at the meter, and decisions per score: none separates a real one-off meter change from
an error.

Run with the app's interpreter so music21 is the app's version:

    Bridge\\.venv-homr-gpu\\Scripts\\python.exe -I -B Research/omr/displacement_correct.py
    ... --freeze anchor-holes     # record the selected variant and this file's hash
    ... --test                    # score it on the test set, once
    ... --splits dev dev-b --variants V... --output reports/displacement/phase3b/development.json
    ... --freeze-b PRIMARY SECONDARY   # the replan's pre-registered pair, and this file's hash
    ... --test-b                       # score both on test-b, once
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[1]
sys.path.insert(0, str(WORKSPACE / "dist" / "Bridge"))
sys.path.insert(0, str(HERE / "src"))
sys.path.insert(0, str(HERE))

from displacement_attribution import app_pages, exact, page_advance  # noqa: E402

REPORT = HERE / "reports/displacement/phase3"
RULER = HERE / "data/displacement-ruler"
MANIFEST = HERE / "reports/displacement/phase1/manifest.json"
# The Phase 3 replan sets: dev-b (meter changes, dev composers) and test-b (new composers).
MANIFEST_B = HERE / "reports/displacement/phase3b/manifest.json"
REPORT_B = HERE / "reports/displacement/phase3b"
ENGINES = ("homr465", "homr")
VARIANTS = ("control", "anchor", "anchor-holes", "anchor-holes-local3", "anchor-holes-local6")


@dataclass
class Element:
    """One note, chord or rest as music21 placed it inside its measure."""
    offset: Fraction  # within the measure
    duration: Fraction
    container: int  # 0 for the measure itself, else the voice's position
    pitches: tuple[int, ...]  # empty for a rest
    voice: str
    original: Fraction  # the app's start within the page, for the control check
    x: int | None = None  # 465's page position of the notehead (`imgpos`), when loaded


@dataclass
class PageMeasure:
    start: Fraction  # music21's offset within its staff on the page
    advance: Fraction
    bar: Fraction
    elements: list[Element] = field(default_factory=list)


@dataclass
class Staff:
    part: int
    staff: int
    measures: list[PageMeasure]


IMGPOS = re.compile(r"<note>((?:(?!</note>).)*?)<!-- imgpos: (\d+), (\d+) -->", re.DOTALL)


def load_page(path: Path, positions: bool = False) -> tuple[list[Staff], Fraction, Fraction]:
    """A page as the app's normalizer reads it: per-staff measures, decoded length, rounding bar.

    With `positions`, each note's `imgpos` comment (465 writes one per note) is copied into
    the note's `default-x` first, which music21 keeps as `style.absoluteX` and which changes
    no timing.
    """
    import tempfile

    import musicxml_normalizer as normalizer
    from music21 import chord, converter, meter, note, stream

    with tempfile.TemporaryDirectory() as folder:
        source = path
        if positions:
            source = Path(folder) / path.name
            source.write_text(IMGPOS.sub(lambda match: f'<note default-x="{match.group(2)}">{match.group(1)}',
                                         path.read_text(encoding="utf-8")), encoding="utf-8")
        score = normalizer._prepare_score(
            lambda: normalizer._parse_musicxml_with_repair(converter, source, force_source=False),
            str(source), expand_repeats=True)
    coordinates = normalizer._musicxml_part_coordinates(score.parts)
    staves = []
    for part in score.parts:
        part_index, staff_index = coordinates[id(part)]
        measures = list(part.getElementsByClass(stream.Measure))
        end = exact(part.highestTime)
        rows = []
        for index, measure in enumerate(measures):
            start = exact(measure.getOffsetInHierarchy(part))
            following = exact(measures[index + 1].getOffsetInHierarchy(part)) if index + 1 < len(measures) \
                else max(end, start + exact(measure.highestTime))
            signature = measure.timeSignature or measure.getContextByClass(meter.TimeSignature)
            row = PageMeasure(start, following - start,
                              exact(signature.barDuration.quarterLength) if signature else Fraction(0))
            voices = {id(voice): position + 1 for position, voice in enumerate(measure.getElementsByClass(stream.Voice))}
            for element in measure.recurse().notesAndRests:
                if element.duration.isGrace or element.duration.quarterLength <= 0:
                    continue
                container = element.getContextByClass(stream.Voice)
                in_voice = container is not None and id(container) in voices
                pitches: tuple[int, ...] = ()
                if isinstance(element, (note.Note, chord.Chord)):
                    pitches = tuple(int(round(pitch.midi)) for pitch in element.pitches)
                original = exact(element.getOffsetInHierarchy(part))
                members = element.notes if isinstance(element, chord.Chord) else (element,)
                xs = [member.style.absoluteX for member in members if isinstance(member.style.absoluteX, (int, float))]
                row.elements.append(Element(
                    offset=original - start, duration=exact(element.duration.quarterLength),
                    container=voices[id(container)] if in_voice else 0, pitches=pitches,
                    voice=normalizer._voice_identifier(element, stream), original=original,
                    x=int(min(xs)) if xs else None))
            rows.append(row)
        staves.append(Staff(part_index, staff_index, rows))
    return staves, exact(score.highestTime), exact(normalizer._extract_measure_beats(score))


def internal_holes(measure: PageMeasure, main_only: bool = False) -> bool:
    """Whether some voice leaves a hole between two of its notes.

    A voice may enter late and may run past the bar line (stripTies merges a tie across it into
    one note, which also leaves the next measure opening with a hole); neither counts. A hole
    after a voice's first note is how a lost `<backup>` shows. With `main_only`, only the voice
    with the most notes in the measure is checked.
    """
    by_container: dict[int, list[Element]] = defaultdict(list)
    for element in measure.elements:
        by_container[element.container].append(element)
    groups = list(by_container.values())
    if main_only and groups:
        groups = [max(groups, key=len)]
    for elements in groups:
        ordered = sorted(elements, key=lambda element: element.offset)
        cursor = ordered[0].offset + ordered[0].duration
        for element in ordered[1:]:
            if element.offset > cursor:
                return True
            cursor = max(cursor, element.offset + element.duration)
    return False


JUMP = 15  # px: a voice's next note this far left of its last one starts a new run (a lost <backup>)
STALL = 3  # px: or at the same x, which no two successive notes of one voice share
CLEAR = 20  # px: one note is clearly left of another; 93% of one onset's notes spread less
MATCH = 12  # px: a run's first note lines up with a note of another run


def place_measure(items: list[tuple[int, Element]]) -> tuple[list[Fraction], int]:
    """New in-measure offsets for one measure of a part, staves together, and the runs moved.

    A run is a voice's notes in time order until x jumps back or stalls. Its durations are
    trusted and its start is not: a lost `<backup>` starts a run where the previous one ended.
    Notes clearly left of another must not start later. Each run with such inversions is tried
    at the onsets of the other runs' notes it lines up with (and at the bar start, if it is
    leftmost), and moves only where that removes inversions; the best move goes first.
    """
    offsets = [element.offset for _, element in items]
    if not items or any(element.x is None for _, element in items):
        return offsets, 0
    groups: dict[tuple[int, int], list[int]] = defaultdict(list)
    for index, (staff, element) in enumerate(items):
        groups[(staff, element.container)].append(index)
    segments: list[list[int]] = []
    for members in groups.values():
        members.sort(key=lambda index: (items[index][1].offset, items[index][1].x))
        current = [members[0]]
        for previous, index in zip(members, members[1:]):
            step = items[index][1].x - items[previous][1].x
            if items[index][1].offset > items[previous][1].offset and (step < -JUMP or abs(step) <= STALL):
                segments.append(current)
                current = []
            current.append(index)
        segments.append(current)
    if len(segments) < 2:
        return offsets, 0
    xs = [element.x for _, element in items]
    leftmost = min(xs)

    def inversions(segment: list[int], trial: list[Fraction]) -> int:
        inside = set(segment)
        return sum(1 for a in segment for b in range(len(items)) if b not in inside and (
            (xs[a] < xs[b] - CLEAR and trial[a] > trial[b]) or (xs[b] < xs[a] - CLEAR and trial[b] > trial[a])))

    moved = 0
    for _ in range(len(segments)):
        best = None
        for segment in segments:
            now = inversions(segment, offsets)
            if not now:
                continue
            first = segment[0]
            inside = set(segment)
            shifts = {offsets[other] - offsets[first] for other in range(len(items))
                      if other not in inside and abs(xs[other] - xs[first]) <= MATCH}
            if xs[first] <= leftmost + MATCH:
                shifts.add(-offsets[first])
            for shift in shifts:
                if shift == 0 or offsets[first] + shift < 0:
                    continue
                trial = list(offsets)
                for index in segment:
                    trial[index] += shift
                gain = now - inversions(segment, trial)
                if gain > 0 and (best is None or (gain, -abs(shift)) > best[0]):
                    best = ((gain, -abs(shift)), segment, shift)
        if best is None:
            break
        _, segment, shift = best
        for index in segment:
            offsets[index] += shift
        moved += 1
    return offsets, moved


def place(staves: list[Staff]) -> tuple[list[Staff], int]:
    """Each part's measures re-placed by `place_measure`; a moved measure's length is its notes' end."""
    placed = copy.deepcopy(staves)
    moved = 0
    by_part: dict[int, list[Staff]] = defaultdict(list)
    for staff in placed:
        by_part[staff.part].append(staff)
    for part_staves in by_part.values():
        for index in range(max(len(staff.measures) for staff in part_staves)):
            items = [(number, element) for number, staff in enumerate(part_staves) if index < len(staff.measures)
                     for element in staff.measures[index].elements]
            offsets, count = place_measure(items)
            if not count:
                continue
            moved += count
            for (_, element), offset in zip(items, offsets):
                element.offset = offset
            end = max(element.offset + element.duration for _, element in items)
            for staff in part_staves:
                if index < len(staff.measures):
                    staff.measures[index].advance = end
    return placed, moved


def fit_shifts(measures: list[PageMeasure], bar: Fraction) -> list[dict[int, Fraction]] | None:
    """How far to move each voice that runs past the bar so it ends on it, or None if one cannot.

    A lost or short `<backup>` starts a whole voice late, so the measure overflows although its
    notes are right. Moving it is allowed only if every voice of the measure, on both staves,
    then fits the bar. A real longer bar has a voice from beat 0 past the page meter, so it never
    fits and is left alone, as is a measure whose notes are wrong rather than misplaced.
    """
    shifts = []
    for measure in measures:
        by_container: dict[int, list[Element]] = defaultdict(list)
        for element in measure.elements:
            by_container[element.container].append(element)
        moves = {}
        for container, elements in by_container.items():
            excess = max(element.offset + element.duration for element in elements) - bar
            if excess > 0:
                if min(element.offset for element in elements) < excess:
                    return None
                moves[container] = excess
        shifts.append(moves)
    return shifts


def x_inversions(measures: list[PageMeasure]) -> int | None:
    """Pairs of notes, staves together, where the one clearly left on the page starts later.

    A correctly placed bar, however long, starts its notes in page order; a voice that a lost
    `<backup>` started late sits back at the left. None where 465 gave no positions (426).
    """
    elements = [element for measure in measures for element in measure.elements]
    if not elements or any(element.x is None for element in elements):
        return None
    ordered = sorted(elements, key=lambda element: element.x)
    return sum(1 for index, left in enumerate(ordered) for right in ordered[index + 1:]
               if left.x < right.x - CLEAR and left.offset > right.offset)


def covers(measure: PageMeasure, length: Fraction) -> bool:
    """Whether one voice runs without a gap from beat 0 to `length`: the decoded bar is written out.

    A lost `<backup>` overflows a bar by starting a voice late, so no voice covers the overflow;
    a real longer (or shorter) bar is spelled out by at least one voice from its first beat.
    """
    by_container: dict[int, list[Element]] = defaultdict(list)
    for element in measure.elements:
        by_container[element.container].append(element)
    for elements in by_container.values():
        cursor = Fraction(0)
        for element in sorted(elements, key=lambda element: element.offset):
            if element.offset > cursor:
                break
            cursor = max(cursor, element.offset + element.duration)
        if cursor >= length:
            return True
    return False


def lay_out(staves: list[Staff], variant: str, first_page: bool) -> tuple[list[tuple[int, int, int, str, Fraction, Fraction]], Fraction]:
    """Notes of one page as (part, staff, midi, voice, start, duration), and the page's length."""
    notes = []
    if variant.startswith("place"):
        staves, _ = place(staves)
        variant = variant.removeprefix("place").removeprefix("+") or "decoded"
    fit = variant.startswith("fit")
    if fit:
        staves = copy.deepcopy(staves)  # pages are shared between variants
        variant = variant.removeprefix("fit").removeprefix("+") or "decoded"
    if variant == "control":
        for staff in staves:
            for measure in staff.measures:
                for element in measure.elements:
                    notes.extend((staff.part, staff.staff, pitch, element.voice, element.original, element.duration)
                                 for pitch in element.pitches)
        return notes, Fraction(-1)  # -1: use the decoded page length, as the app does

    by_part: dict[int, list[Staff]] = defaultdict(list)
    for staff in staves:
        by_part[staff.part].append(staff)
    page_length = Fraction(0)
    for part_staves in by_part.values():
        count = max(len(staff.measures) for staff in part_staves)

        lengths = [max(staff.measures[index].advance for staff in part_staves if index < len(staff.measures))
                   for index in range(count)]
        bars = [next((staff.measures[index].bar for staff in part_staves if index < len(staff.measures)), Fraction(0))
                for index in range(count)]
        holes = [any(internal_holes(staff.measures[index]) for staff in part_staves if index < len(staff.measures))
                 for index in range(count)]

        def local_bar(index: int, reach: int, fallback: Fraction) -> Fraction:
            """The most common decoded length among hole-free measures near this one."""
            near = Counter(lengths[other] for other in range(max(0, index - reach), min(count, index + reach + 1))
                           if other != index and not holes[other])
            if not near:
                return fallback
            best = max(near.values())
            tied = [length for length, seen in near.items() if seen == best]
            return fallback if fallback in tied else min(tied, key=lambda length: abs(length - fallback))

        hole_free = Counter(length for length, hole in zip(lengths, holes) if not hole)

        def recurring(index: int, least: int, neighbour: bool) -> bool:
            """Whether hole-free measures on the page share this one's decoded length: a real meter."""
            if neighbour and any(0 <= other < count and not holes[other] and lengths[other] == lengths[index]
                                 for other in (index - 1, index + 1)):
                return True
            return hole_free[lengths[index]] >= least

        if fit:
            for index in range(count):
                bar = bars[index]
                present = [staff.measures[index] for staff in part_staves if index < len(staff.measures)]
                shifts = fit_shifts(present, bar) if 0 < bar < lengths[index] else None
                if shifts is None:
                    continue
                for measure, moves in zip(present, shifts):
                    for element in measure.elements:
                        element.offset -= moves.get(element.container, Fraction(0))
                lengths[index] = bar
                holes[index] = any(internal_holes(measure) for measure in present)
            hole_free = Counter(length for length, hole in zip(lengths, holes) if not hole)

        covered = [any(covers(staff.measures[index], lengths[index]) for staff in part_staves
                       if index < len(staff.measures)) for index in range(count)]
        chosen = []
        for index, (length, bar) in enumerate(zip(lengths, bars)):
            if variant == "decoded" or bar <= 0 or (first_page and index == 0 and length < bar):
                chosen.append(length)  # no meter to anchor to, or an opening pickup
            elif variant == "anchor":
                chosen.append(bar)
            elif variant == "anchor-holes":
                chosen.append(bar if holes[index] else length)
            elif variant.startswith("anchor-holes-") and not variant.startswith("anchor-holes-local"):
                # Gates, combinable: keepN (N hole-free measures share the length), nb (or a
                # hole-free neighbour does), cover (a voice spells the decoded bar out), coverunder
                # (cover, for a short bar only).
                options = variant.removeprefix("anchor-holes-").split("-")
                least = next((int(option[4:]) for option in options if option.startswith("keep")), None)
                anchored = holes[index]
                if least is not None and recurring(index, least, "nb" in options):
                    anchored = False
                if covered[index] and ("cover" in options or ("coverunder" in options and length < bar)):
                    anchored = False
                chosen.append(bar if anchored else length)
            elif variant.startswith("anchor-holes-local"):
                reach = int(variant.removeprefix("anchor-holes-local"))
                chosen.append(local_bar(index, reach, bar) if holes[index] else length)
            else:
                raise ValueError(f"unknown variant {variant}")
        starts = [sum(chosen[:index], Fraction(0)) for index in range(count)]
        page_length = max(page_length, sum(chosen, Fraction(0)))
        for staff in part_staves:
            for index, measure in enumerate(staff.measures):
                for element in measure.elements:
                    notes.extend((staff.part, staff.staff, pitch, element.voice, starts[index] + element.offset,
                                  element.duration)
                                 for pitch in element.pitches)
    return notes, page_length


def predict(pages: list[tuple[list[Staff], Fraction, Fraction]], variant: str) -> list[tuple]:
    """A whole score, pages stitched the way the app stitches them."""
    notes, offset = [], Fraction(0)
    for number, (staves, decoded_length, bar) in enumerate(pages):
        page_notes, length = lay_out(staves, variant, number == 0)
        notes.extend((part, staff, pitch, voice, offset + start, duration)
                     for part, staff, pitch, voice, start, duration in page_notes)
        offset += page_advance(decoded_length if length < 0 else length, bar, number == 0)
    return notes


def check_control(item: dict[str, Any], engine: str, notes: list[tuple]) -> None:
    payload = json.loads((RULER / "captures" / engine / item["id"] / "payload.json").read_text())

    def key(start: float, pitch: int, duration: float) -> tuple[int, int, int]:
        return round(start * 1e6), pitch, round(duration * 1e6)

    played = sorted(key(note["start_beat"], note["midi_pitch"], note["duration_beats"]) for note in payload["notes"])
    rebuilt = sorted(key(float(start), pitch, float(duration)) for _, _, pitch, _, start, duration in notes)
    if played != rebuilt:
        raise AssertionError(f"{item['id']} {engine}: the control does not reproduce the app's payload")


def score(notes: list[tuple], truth: list) -> dict[str, float]:
    from sheet2play_omr.metrics import MetricNote, calculate_note_metrics

    predicted = [MetricNote(pitch=pitch, onset=start, duration=duration, staff=staff, voice=voice)
                 for _, staff, pitch, voice, start, duration in notes]
    metrics = calculate_note_metrics(predicted, truth)
    return {name: round(getattr(metrics, name), 4) for name in ("onset_duration_f1", "onset_f1", "pitch_f1")}


FREEZE = REPORT / "freeze.json"
FREEZE_B = REPORT_B / "freeze.json"
TEST_B_OUTPUT = REPORT_B / "test.json"
DEVELOPMENT_B = REPORT_B / "development.json"
TEST_OUTPUT = REPORT / "test.json"
BASELINE = HERE / "reports/displacement/phase1/baseline.json"
BASELINES_B = (REPORT_B / "baseline-dev-b.json", REPORT_B / "baseline.json")


def manifest_items(splits: tuple[str, ...]) -> list[dict[str, Any]]:
    """Items of the named splits from the Phase 1 ruler and the replan sets, in manifest order."""
    items = []
    for path in (MANIFEST, MANIFEST_B):
        if path.is_file():
            items.extend(item for item in json.loads(path.read_text())["items"] if item["split"] in splits)
    return items


def source_hash() -> str:
    import hashlib

    # Line endings vary with Git's checkout settings, so hash the text with LF endings.
    return hashlib.sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def evaluate(items: list[dict[str, Any]], variants: tuple[str, ...], truth_flags: dict[str, bool]) -> dict[str, Any]:
    from diagnose_rhythm import ground_truth_notes

    rows: dict[str, dict[str, Any]] = {}
    for item in items:
        truth, _ = ground_truth_notes(HERE / item["label"], **truth_flags)
        rows[item["id"]] = {}
        for engine in ENGINES:
            result = json.loads((RULER / "captures" / engine / item["id"] / "result.json").read_text())
            if result["status"] != "ok":  # a failed capture scores 0 under every variant
                rows[item["id"]][engine] = {variant: {"onset_duration_f1": 0.0, "onset_f1": 0.0, "pitch_f1": 0.0}
                                            for variant in variants} | {"status": result["status"]}
                continue
            positions = any(variant.startswith("place") for variant in variants)
            pages = [load_page(path, positions) for path, _ in app_pages(item, engine)]
            entry: dict[str, Any] = {"status": "ok"}
            for variant in variants:
                notes = predict(pages, variant)
                if variant == "control":
                    check_control(item, engine, notes)
                entry[variant] = score(notes, truth)
            rows[item["id"]][engine] = entry
            print(item["id"], engine, {variant: entry[variant]["onset_f1"] for variant in variants}, flush=True)
    return rows


def summarise(items: list[dict[str, Any]], rows: dict[str, Any], variants: tuple[str, ...]) -> dict[str, Any]:
    """Composition-macro means and the plan's acceptance checks, each variant against control.

    Near-correct is the plan's definition: the control's span ratio is 0.98-1.02 and its onset
    F1 is 0.9 or above (span from the Phase 1 baseline).
    """
    from summarize_homr_pair import bootstrap_interval

    baseline = json.loads(BASELINE.read_text())["rows"]
    for path in BASELINES_B:
        if path.is_file():
            baseline |= json.loads(path.read_text())["rows"]
    summary: dict[str, Any] = {}
    for engine in ENGINES:
        engine_rows = [(item["id"], rows[item["id"]][engine]) for item in items]
        near = [score for score, row in engine_rows if row["status"] == "ok"
                and row["control"]["onset_f1"] >= 0.9
                and 0.98 <= baseline[score][engine]["reference"]["span_ratio"] <= 1.02]
        summary[engine] = {"near_correct_scores": near}
        for variant in variants:
            means = {metric: round(statistics.fmean(row[variant][metric] for _, row in engine_rows), 4)
                     for metric in ("onset_duration_f1", "onset_f1", "pitch_f1")}
            differences = [row[variant]["onset_f1"] - row["control"]["onset_f1"] for _, row in engine_rows]
            lower, upper, p_value = bootstrap_interval(differences)
            near_drops = [rows[score][engine][variant]["onset_f1"] - rows[score][engine]["control"]["onset_f1"]
                          for score in near]
            summary[engine][variant] = means | {
                "onset_gain": round(statistics.fmean(differences), 4),
                "onset_gain_95": [round(lower, 4), round(upper, 4)], "one_sided_p": round(p_value, 4),
                "pitch_change": round(means["pitch_f1"] - statistics.fmean(row["control"]["pitch_f1"]
                                                                            for _, row in engine_rows), 4),
                "scores_better": sum(difference > 0.0001 for difference in differences),
                "scores_worse": sum(difference < -0.0001 for difference in differences),
                "worst_drop": round(min(differences), 4),
                "near_correct_worst_drop": round(min(near_drops, default=0.0), 4),
            }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ids", nargs="*", help="development scores to inspect")
    parser.add_argument("--variants", nargs="*", help="development variants to run (control is always run)")
    parser.add_argument("--splits", nargs="*", default=["dev"], help="development splits: dev, dev-b")
    parser.add_argument("--output", type=Path, default=REPORT / "development.json")
    parser.add_argument("--freeze", metavar="VARIANT", help="record the selected variant and this script's hash")
    parser.add_argument("--test", action="store_true", help="score the frozen variant on the test set, once")
    parser.add_argument("--freeze-b", nargs=2, metavar=("PRIMARY", "SECONDARY"),
                        help="record the replan's two variants from phase3b/development.json, and this script's hash")
    parser.add_argument("--test-b", action="store_true", help="score the frozen replan variants on test-b, once")
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text())

    if args.freeze_b:
        development = json.loads(DEVELOPMENT_B.read_text())
        if sorted(development["split"]) != ["dev", "dev-b"] or any(
                variant not in development["variants"] or variant == "control" for variant in args.freeze_b):
            parser.error("freeze from a dev + dev-b run that scored both variants")
        if FREEZE_B.exists():
            parser.error(f"{FREEZE_B.name} exists: the replan is frozen once")
        FREEZE_B.write_text(json.dumps({
            "primary": args.freeze_b[0], "secondary": args.freeze_b[1], "source_sha256": source_hash(),
            "development": {variant: {engine: development["summary"][engine][variant] for engine in ENGINES}
                            for variant in args.freeze_b}}, indent=1) + "\n", encoding="utf-8")
        print(f"froze {args.freeze_b} at {source_hash()}")
        return 0

    if args.test_b:
        frozen = json.loads(FREEZE_B.read_text())
        if frozen["source_sha256"] != source_hash():
            parser.error("this script changed after freezing; the frozen variants are no longer the code here")
        if TEST_B_OUTPUT.exists():
            parser.error(f"{TEST_B_OUTPUT.name} exists: test-b is scored once")
        items = manifest_items(("test-b",))
        variants = ("control", frozen["primary"], frozen["secondary"])
        rows = evaluate(items, variants, manifest["truth_flags"])
        summary = {"all": summarise(items, rows, variants)}
        for stratum in sorted({item["stratum"] for item in items}):
            summary[stratum] = summarise([item for item in items if item["stratum"] == stratum], rows, variants)
        TEST_B_OUTPUT.write_text(json.dumps({"split": "test-b", "frozen": frozen, "summary": summary, "rows": rows},
                                            indent=1) + "\n", encoding="utf-8")
        print(json.dumps(summary, indent=1))
        return 0

    if args.freeze:
        if args.freeze not in VARIANTS or args.freeze == "control":
            parser.error(f"unknown variant {args.freeze}")
        development = json.loads(args.output.read_text())
        FREEZE.write_text(json.dumps({"variant": args.freeze, "source_sha256": source_hash(),
                                      "development": {engine: development["summary"][engine][args.freeze]
                                                      for engine in ENGINES}}, indent=1) + "\n", encoding="utf-8")
        print(f"froze {args.freeze} at {source_hash()}")
        return 0

    if args.test:
        frozen = json.loads(FREEZE.read_text())
        if frozen["source_sha256"] != source_hash():
            parser.error("this script changed after freezing; the frozen variant is no longer the code here")
        if TEST_OUTPUT.exists():
            parser.error(f"{TEST_OUTPUT.name} exists: the test set is scored once")
        items = [item for item in manifest["items"] if item["split"] == "test"]
        variants = ("control", frozen["variant"])
        rows = evaluate(items, variants, manifest["truth_flags"])
        summary = summarise(items, rows, variants)
        TEST_OUTPUT.write_text(json.dumps({"split": "test", "frozen": frozen, "summary": summary, "rows": rows},
                                          indent=1) + "\n", encoding="utf-8")
        print(json.dumps(summary, indent=1))
        return 0

    if set(args.splits) - {"dev", "dev-b"}:
        parser.error("tuning runs on development splits only; held-out sets are scored once, after freezing")
    items = [item for item in manifest_items(tuple(args.splits)) if not args.ids or item["id"] in args.ids]
    variants = ("control", *args.variants) if args.variants else VARIANTS
    rows = evaluate(items, variants, manifest["truth_flags"])
    summary = summarise(items, rows, variants)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"split": args.splits, "variants": variants, "summary": summary, "rows": rows},
                                      indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
