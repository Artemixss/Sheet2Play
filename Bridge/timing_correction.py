"""HOMR timing correction: re-lay each page's measures where a lost `<backup>` misplaced them.

Shipped behind the app's "Timing fix" setting, off by default. This module is a port of the
frozen research variant `fit+anchor-all-keep3-even-time` (`Research/omr/timing_correct.py`;
`Research/omr/reports/timing/handoff.md`). On 94 held-out engraved scores, scored once, it
raised onset F1 over the previous fix (`fit+anchor-holes-keep3`) from 0.606 to 0.680 with
HOMR 465 and from 0.545 to 0.588 with 426, pitch unchanged; one near-correct 465 score went
from 0.995 to 0.952. Over the uncorrected engines that is about 0.43 to 0.68 and 0.42 to 0.59.

HOMR's MusicXML sometimes drops or shortens a `<backup>`, so a whole voice starts late and
its measure overflows although its notes are right. Every later note then plays late. Per
page, both staves of a part together:

1. **fit**: a measure longer than the page meter whose late voices can all be moved back to
   end on the bar is fitted, all or nothing. A real longer bar has a voice from beat 0 past
   the meter, so it never fits and is left alone.
2. **anchor**: every measure advances by its meter, unless it looks like a real bar of its
   own length: three hole-free measures on the page share its decoded length (a recurring
   meter), or it has no hole between two notes of a voice (the other mark of a lost
   `<backup>`) and either every voice ends on its decoded length or HOMR recognised a time
   signature at it. An opening pickup keeps its length.

Notes keep their place inside their measure, and pages are stitched by the bridge's own
`combine_score_pages`, which reads the corrected page length. The meter is the one music21
gives the measure, normally HOMR's page meter, so a real one-off meter change whose voices
end unevenly and whose time signature HOMR missed is still anchored wrongly.

Run in place of `bridge.py`, with the same arguments. It changes only the normalized pages
of the HOMR engines; any other engine runs unchanged. This file is not one of the pinned
HOMR 465 bridge files: the app keys corrected results by this file's SHA-256 instead.
"""

from __future__ import annotations

import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field, replace
from fractions import Fraction
from pathlib import Path
from typing import Sequence

KEEP_RECURRING = 3  # hole-free measures sharing a decoded length that mark it as a real meter
HOMR_ENGINES = {"homr", "homr465", "homr480"}


def exact(value: float) -> Fraction:
    return Fraction(value).limit_denominator(4096)


@dataclass
class Element:
    """One note, chord or rest as music21 placed it inside its measure."""
    offset: Fraction  # within the measure
    duration: Fraction
    container: int  # 0 for the measure itself, else the voice's position
    pitches: tuple[int, ...]  # empty for a rest
    voice: str
    original: Fraction  # music21's start within the page, as the normalizer reports it


@dataclass
class PageMeasure:
    start: Fraction
    advance: Fraction
    bar: Fraction
    elements: list[Element] = field(default_factory=list)
    time_here: bool = False  # HOMR recognised a time signature at this measure, after the page's first


@dataclass
class Staff:
    part: int
    staff: int
    measures: list[PageMeasure]


def load_page(path: Path) -> list[Staff]:
    """A page's measures, read exactly as `musicxml_normalizer.normalize_musicxml` reads it."""
    import musicxml_normalizer as normalizer
    from music21 import chord, converter, meter, note, stream

    score = normalizer._prepare_score(
        lambda: normalizer._parse_musicxml_with_repair(converter, path.resolve(strict=True), force_source=False),
        str(path.resolve(strict=True)), expand_repeats=True)
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
                              exact(signature.barDuration.quarterLength) if signature else Fraction(0),
                              time_here=index > 0 and measure.timeSignature is not None)
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
    return staves


def internal_holes(measure: PageMeasure) -> bool:
    """Whether some voice leaves a hole between two of its notes.

    A voice may enter late and may run past the bar line (the normalizer merges a tie across
    it into one note, which also leaves the next measure opening with a hole); neither counts.
    """
    by_container: dict[int, list[Element]] = defaultdict(list)
    for element in measure.elements:
        by_container[element.container].append(element)
    for elements in by_container.values():
        ordered = sorted(elements, key=lambda element: element.offset)
        cursor = ordered[0].offset + ordered[0].duration
        for element in ordered[1:]:
            if element.offset > cursor:
                return True
            cursor = max(cursor, element.offset + element.duration)
    return False


def fit_shifts(measures: list[PageMeasure], bar: Fraction) -> list[dict[int, Fraction]] | None:
    """How far to move each voice that runs past the bar so it ends on it, or None if one cannot."""
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


def evenly_ended(measures: list[PageMeasure], offsets: list[list[Fraction]]) -> bool:
    """Whether every voice of the measure, on every staff, ends at the same point."""
    ends = set()
    for measure, measure_offsets in zip(measures, offsets):
        by_container: dict[int, Fraction] = {}
        for element, offset in zip(measure.elements, measure_offsets):
            by_container[element.container] = max(by_container.get(element.container, offset), offset + element.duration)
        ends.update(by_container.values())
    return len(ends) == 1


@dataclass
class Layout:
    starts: dict[tuple, list[Fraction]]  # (part, staff, midi, voice, original, duration) -> new starts
    measures: list[tuple[Fraction, Fraction]]  # part 0: (original start, new start) per measure
    length: Fraction
    fitted: int = 0
    anchored: int = 0


def lay_out(staves: list[Staff], first_page: bool) -> Layout:
    """The corrected start of every note on one page, and the page's corrected length."""
    by_part: dict[int, list[Staff]] = defaultdict(list)
    for staff in staves:
        by_part[staff.part].append(staff)
    layout = Layout(starts=defaultdict(list), measures=[], length=Fraction(0))
    for part, part_staves in by_part.items():
        count = max(len(staff.measures) for staff in part_staves)
        present = [[staff.measures[index] for staff in part_staves if index < len(staff.measures)]
                   for index in range(count)]
        lengths = [max(measure.advance for measure in measures) for measures in present]
        bars = [measures[0].bar for measures in present]
        moves: list[list[dict[int, Fraction]]] = [[{} for _ in measures] for measures in present]
        for index, measures in enumerate(present):
            shifts = fit_shifts(measures, bars[index]) if 0 < bars[index] < lengths[index] else None
            if shifts is not None:
                moves[index] = shifts
                lengths[index] = bars[index]
                layout.fitted += 1
        offsets = [[[element.offset - moved.get(element.container, Fraction(0)) for element in measure.elements]
                    for measure, moved in zip(measures, measure_moves)]
                   for measures, measure_moves in zip(present, moves)]
        holes = [any(internal_holes(PageMeasure(measure.start, measure.advance, measure.bar, [
                     replace(element, offset=offset) for element, offset in zip(measure.elements, measure_offsets)]))
                     for measure, measure_offsets in zip(measures, measure_offsets_list))
                 for measures, measure_offsets_list in zip(present, offsets)]
        hole_free = Counter(length for length, hole in zip(lengths, holes) if not hole)
        chosen = []
        for index, (length, bar) in enumerate(zip(lengths, bars)):
            pickup = first_page and index == 0 and length < bar
            kept = hole_free[length] >= KEEP_RECURRING
            if not holes[index] and (evenly_ended(present[index], offsets[index])
                                     or any(measure.time_here for measure in present[index])):
                kept = True
            if bar > 0 and not pickup and not kept:
                chosen.append(bar)
                layout.anchored += int(bar != length)
            else:
                chosen.append(length)
        starts = [sum(chosen[:index], Fraction(0)) for index in range(count)]
        layout.length = max(layout.length, sum(chosen, Fraction(0)))
        for index, measures in enumerate(present):
            for staff, measure, measure_offsets in zip(part_staves, measures, offsets[index]):
                for element, offset in zip(measure.elements, measure_offsets):
                    for pitch in element.pitches:
                        layout.starts[(staff.part, staff.staff, pitch, element.voice, element.original,
                                       element.duration)].append(starts[index] + offset)
            if part == min(by_part):
                layout.measures.append((measures[0].start, starts[index]))
    return layout


def _key(part: int, staff: int, pitch: int, voice: str, start: float, duration: float) -> tuple:
    return part, staff, pitch, voice, round(start * 1e6), round(duration * 1e6)


def correct_page(path: Path, page, first_page: bool):
    """`page` (the normalizer's NormalizedScore for `path`) with corrected starts and length.

    Raises ValueError when the page's notes and the measures read here do not match one to
    one; the caller then keeps the page as the app reads it.
    """
    layout = lay_out(load_page(path), first_page)
    targets: dict[tuple, list[Fraction]] = {}
    for (part, staff, pitch, voice, original, duration), starts in layout.starts.items():
        targets.setdefault(_key(part, staff, pitch, voice, float(original), float(duration)), []).extend(starts)
    notes = []
    for note in page.notes:
        starts = targets.get(_key(note.part_index, note.staff_index, note.midi_pitch, note.voice_identifier,
                                  note.start_beat, note.duration_beats))
        if not starts:
            raise ValueError(f"note {note.pitch} at beat {note.start_beat:g} has no measure")
        notes.append(replace(note, start_beat=float(starts.pop(0))))
    if any(targets.values()):
        raise ValueError("measures hold notes the normalizer did not report")

    def moved(beat: float) -> float:
        # A tempo mark moves with the measure that holds it.
        original, new = max((pair for pair in layout.measures if float(pair[0]) <= beat + 1e-9),
                            default=(Fraction(0), Fraction(0)), key=lambda pair: pair[0])
        return float(new) + beat - float(original)

    tempos = tuple(replace(change, start_beat=moved(change.start_beat)) for change in page.tempo_changes)
    print(f"[timing] page={path.name} fitted={layout.fitted} anchored={layout.anchored} "
          f"decoded={page.total_beats:g} corrected={float(layout.length):g}", file=sys.stderr, flush=True)
    return replace(page, notes=tuple(notes), tempo_changes=tempos, total_beats=float(layout.length))


def install(bridge) -> None:
    """Make `bridge.run_homr_engine` normalize each page and then correct it."""
    normalize = bridge.normalize_musicxml
    pages_seen = [0]

    def normalize_and_correct(path: Path, *args, **kwargs):
        page = normalize(path, *args, **kwargs)
        first = pages_seen[0] == 0
        pages_seen[0] += 1
        try:
            return correct_page(Path(path), page, first)
        except Exception as error:  # noqa: BLE001 - any failure keeps the app's own reading
            print(f"[timing] page={Path(path).name} kept uncorrected: {type(error).__name__}: {error}",
                  file=sys.stderr, flush=True)
            return page

    bridge.normalize_musicxml = normalize_and_correct


def engine_argument(arguments: Sequence[str]) -> str | None:
    for index, argument in enumerate(arguments):
        if argument == "--engine" and index + 1 < len(arguments):
            return arguments[index + 1]
        if argument.startswith("--engine="):
            return argument.split("=", 1)[1]
    return None


def main(arguments: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if arguments is None else arguments)
    import bridge

    if engine_argument(arguments) in HOMR_ENGINES:
        install(bridge)
    return bridge.main(arguments)


if __name__ == "__main__":
    sys.exit(main())
