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

Run with the app's interpreter so music21 is the app's version:

    Bridge\\.venv-homr-gpu\\Scripts\\python.exe -I -B Research/omr/displacement_correct.py
    ... --freeze anchor-holes     # record the selected variant and this file's hash
    ... --test                    # score it on the test set, once
"""

from __future__ import annotations

import argparse
import json
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


def load_page(path: Path) -> tuple[list[Staff], Fraction, Fraction]:
    """A page as the app's normalizer reads it: per-staff measures, decoded length, rounding bar."""
    import musicxml_normalizer as normalizer
    from music21 import chord, converter, meter, note, stream

    score = normalizer._prepare_score(
        lambda: normalizer._parse_musicxml_with_repair(converter, path, force_source=False),
        str(path), expand_repeats=True)
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
                row.elements.append(Element(
                    offset=original - start, duration=exact(element.duration.quarterLength),
                    container=voices[id(container)] if in_voice else 0, pitches=pitches,
                    voice=normalizer._voice_identifier(element, stream), original=original))
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


def lay_out(staves: list[Staff], variant: str, first_page: bool) -> tuple[list[tuple[int, int, int, str, Fraction, Fraction]], Fraction]:
    """Notes of one page as (part, staff, midi, voice, start, duration), and the page's length."""
    notes = []
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

        chosen = []
        for index, (length, bar) in enumerate(zip(lengths, bars)):
            if bar <= 0 or (first_page and index == 0 and length < bar):
                chosen.append(length)  # no meter to anchor to, or an opening pickup
            elif variant == "anchor":
                chosen.append(bar)
            elif variant == "anchor-holes":
                chosen.append(bar if holes[index] else length)
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
TEST_OUTPUT = REPORT / "test.json"
BASELINE = HERE / "reports/displacement/phase1/baseline.json"


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
            pages = [load_page(path) for path, _ in app_pages(item, engine)]
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
    parser.add_argument("--output", type=Path, default=REPORT / "development.json")
    parser.add_argument("--freeze", metavar="VARIANT", help="record the selected variant and this script's hash")
    parser.add_argument("--test", action="store_true", help="score the frozen variant on the test set, once")
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text())

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

    items = [item for item in manifest["items"] if (item["id"] in args.ids if args.ids else item["split"] == "dev")]
    if any(item["split"] != "dev" for item in items):
        parser.error("tuning runs on the development split only; the test set is scored once, after freezing")
    rows = evaluate(items, VARIANTS, manifest["truth_flags"])
    summary = summarise(items, rows, VARIANTS)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"split": "dev", "variants": VARIANTS, "summary": summary, "rows": rows},
                                      indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
