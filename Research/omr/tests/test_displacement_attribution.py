from __future__ import annotations

import unittest
from collections import Counter
from fractions import Fraction

from displacement_attribution import (
    PARALLEL,
    ROUNDING,
    Measure,
    PageContext,
    align,
    classify,
    expand_order,
    page_advance,
    shapley,
    simulate,
)


def measure(index: int, pitches: list[int], advance: Fraction = Fraction(4), *, page: int = 0, part: int = 0,
            bar: Fraction = Fraction(4), durations: Counter | None = None, **features: object) -> Measure:
    row = Measure(staff=0, part=part, page=page, index=index, number=str(index + 1), start=Fraction(0),
                  advance=advance, bar=bar, signature=None, pitches=Counter(pitches),
                  durations=durations if durations is not None else Counter((pitch, Fraction(1)) for pitch in pitches),
                  notes=len(pitches))
    for key, value in features.items():
        setattr(row, key, value)
    return row


def entry(page: int, pred: int | None, true: int | None, pred_advance: Fraction | None,
          true_advance: Fraction | None, mechanism: str = "correct length", part: int = 0) -> dict:
    return {"page": page, "part": part, "pred": pred, "true": true, "pred_advance": pred_advance,
            "true_advance": true_advance, "mechanism": mechanism}


class PageAdvanceTest(unittest.TestCase):
    def test_matches_the_app_normalizer(self) -> None:
        import musicxml_normalizer as normalizer

        for length in (Fraction(0), Fraction(7, 2), Fraction(16), Fraction(33, 2), Fraction(18), Fraction(1)):
            for bar in (Fraction(0), Fraction(3), Fraction(4)):
                for first in (True, False):
                    page = normalizer.NormalizedScore(notes=(), tempo_changes=(), total_beats=float(length),
                                                      part_count=1, staff_count=1, measure_beats=float(bar))
                    self.assertEqual(float(page_advance(length, bar, first)), normalizer._page_advance(page, first))


class ShapleyTest(unittest.TestCase):
    def test_shares_sum_to_the_whole_and_split_symmetric_players(self) -> None:
        contributions = {"a": Fraction(2), "b": Fraction(2), "c": Fraction(-1)}

        def in_place(undo: set[str]) -> Fraction:
            return Fraction(int(sum(value for key, value in contributions.items() if key not in undo) == 0))

        shares = shapley(list(contributions), in_place)
        self.assertEqual(sum(shares.values()), 1)
        self.assertEqual(shares["a"], shares["b"])


class AlignTest(unittest.TestCase):
    def test_a_lost_run_in_repetitive_music_stays_contiguous(self) -> None:
        truth = [measure(index, [60, 64, 67] if index % 2 else [62, 65, 69]) for index in range(12)]
        predicted = truth[:3] + truth[7:]  # four measures lost, inside a repeating pattern
        pairs = align(predicted, truth)
        dropped = [true for pred, true in pairs if pred is None]
        self.assertEqual(len(dropped), 4)
        self.assertEqual(dropped, list(range(dropped[0], dropped[0] + 4)))


class RepeatOrderTest(unittest.TestCase):
    def test_a_repeat_across_a_page_break_plays_differently_page_by_page(self) -> None:
        marks = [(False, False)] * 6
        marks[1] = (True, False)   # start repeat at measure 2, page 1
        marks[4] = (False, True)   # end repeat at measure 5, page 2
        self.assertEqual(expand_order(marks, 0, 6), [0, 1, 2, 3, 4, 1, 2, 3, 4, 5])
        page_wise = expand_order(marks, 0, 3) + expand_order(marks, 3, 6)
        self.assertEqual(page_wise, [0, 1, 2, 3, 4, 3, 4, 5])


class SimulateTest(unittest.TestCase):
    def setUp(self) -> None:
        # Two pages of two 4/4 measures; measure 1 decodes a beat long.
        self.staves = [[
            entry(0, 0, 0, Fraction(5), Fraction(4), "overflow: durations differ"),
            entry(0, 1, 1, Fraction(4), Fraction(4)),
            entry(1, 2, 2, Fraction(4), Fraction(4)),
            entry(1, 3, 3, Fraction(4), Fraction(4)),
        ]]
        self.bars = [Fraction(4), Fraction(4)]

    def test_page_one_is_not_rounded_so_the_error_carries_on(self) -> None:
        starts, offsets = simulate(self.staves, self.bars, set())
        self.assertEqual(starts[0], [0, 5, 9, 13])
        self.assertEqual(offsets, [0, 9])

    def test_undoing_every_mechanism_restores_the_truth(self) -> None:
        starts, _ = simulate(self.staves, self.bars, {"overflow: durations differ", PARALLEL, ROUNDING})
        self.assertEqual(starts[0], [0, 4, 8, 12])

    def test_rounding_repairs_a_small_error_on_a_later_page(self) -> None:
        staves = [[entry(0, 0, 0, Fraction(4), Fraction(4)),
                   entry(1, 1, 1, Fraction(5), Fraction(4), "overflow: durations differ"),
                   entry(1, 2, 2, Fraction(4), Fraction(4)),
                   entry(2, 3, 3, Fraction(4), Fraction(4))]]
        starts, _ = simulate(staves, [Fraction(4)] * 3, set())
        self.assertEqual(starts[0], [0, 4, 9, 12])  # page 2's 9 beats round to 8

    def test_a_second_part_restarts_at_the_page_start(self) -> None:
        staves = [[entry(0, 0, 0, Fraction(4), Fraction(4)),
                   entry(0, 1, 1, Fraction(4), Fraction(4), part=1)]]
        starts, _ = simulate(staves, [Fraction(4)], set())
        self.assertEqual(starts[0], [0, 0])
        starts, _ = simulate(staves, [Fraction(4)], {PARALLEL})
        self.assertEqual(starts[0], [0, 4])


class ClassifyTest(unittest.TestCase):
    def test_every_note_right_but_wrong_length_is_layout(self) -> None:
        true = measure(0, [60, 64, 67])
        pred = measure(0, [60, 64, 67], Fraction(7))
        self.assertTrue(classify(pred, true, None).startswith("layout: every note right"))

    def test_unread_content_is_garbled_whatever_the_meter(self) -> None:
        true = measure(0, [60, 62, 64], Fraction(2), bar=Fraction(2))
        pred = measure(0, [70, 72, 74], Fraction(4), bar=Fraction(4))
        self.assertTrue(classify(pred, true, None).startswith("garbled measure"))

    def test_a_tremolo_without_tuplets_in_the_prediction(self) -> None:
        true = measure(0, [65, 71, 65, 71], tuplets=4, tremolos=4,
                       durations=Counter({(65, Fraction(1)): 2, (71, Fraction(1)): 2}))
        pred = measure(0, [65, 71, 65, 71], Fraction(8),
                       durations=Counter({(65, Fraction(2)): 2, (71, Fraction(2)): 2}))
        self.assertEqual(classify(pred, true, None), "tuplet: two-note tremolo read as plain notes")

    def test_meter_counts_only_where_homr_re_timed(self) -> None:
        true = measure(0, [60, 62, 64], Fraction(3), bar=Fraction(3),
                       durations=Counter({(60, Fraction(1)): 1, (62, Fraction(1)): 1, (64, Fraction(1)): 1}))
        pred = measure(0, [60, 62, 64], Fraction(4), bar=Fraction(4),
                       durations=Counter({(60, Fraction(2)): 1, (62, Fraction(1)): 1, (64, Fraction(1)): 1}))
        context = PageContext(label_meters={Fraction(3)}, systems_match=True)
        self.assertFalse(classify(pred, true, context).startswith("meter"))
        context.retimed = {"1"}
        self.assertEqual(classify(pred, true, context), "meter: re-timed by HOMR to the page meter")


if __name__ == "__main__":
    unittest.main()
