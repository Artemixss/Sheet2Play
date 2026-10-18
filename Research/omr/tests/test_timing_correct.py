from __future__ import annotations

import unittest
from fractions import Fraction

from displacement_correct import Staff, lay_out as frozen_lay_out
from test_displacement_correct import element, measure, quarters, starts
from timing_correct import evenly_ended, lay_out


def page(*bars) -> list[Staff]:
    return [Staff(part=0, staff=0, measures=list(bars))]


def four() -> object:
    return measure(Fraction(4), quarters(4))


def uneven_long() -> object:
    # Two voices that should share the bar, the second exported a full bar late: 8 beats, no hole.
    return measure(Fraction(8), quarters(4) + [element(Fraction(4), Fraction(4), container=2)])


class AnchorAllTest(unittest.TestCase):
    def test_a_lone_gap_free_bar_off_the_meter_is_anchored(self) -> None:
        _, length = lay_out(page(four(), uneven_long(), four()), "anchor-all-keep3", first_page=False)
        self.assertEqual(length, 12)

    def test_the_shipped_rule_leaves_it_alone(self) -> None:
        _, length = frozen_lay_out(page(four(), uneven_long(), four()), "anchor-holes-keep3", first_page=False)
        self.assertEqual(length, 16)

    def test_a_recurring_length_is_kept(self) -> None:
        threes = [measure(Fraction(3), quarters(3)) for _ in range(3)]
        _, length = lay_out(page(four(), *threes), "anchor-all-keep3", first_page=False)
        self.assertEqual(length, 13)

    def test_other_variants_are_the_frozen_ones(self) -> None:
        bars = page(four(), uneven_long(), measure(Fraction(2), quarters(2)), four())
        for variant in ("control", "anchor", "fit+anchor-holes-keep3"):
            self.assertEqual(lay_out(bars, variant, first_page=False), frozen_lay_out(bars, variant, first_page=False))


class GateTest(unittest.TestCase):
    def short_even(self) -> object:
        return measure(Fraction(2), quarters(2) + [element(Fraction(0), Fraction(2), container=2)])

    def test_evenly_ended_needs_every_voice_on_the_same_end(self) -> None:
        self.assertTrue(evenly_ended([self.short_even()]))
        self.assertFalse(evenly_ended([uneven_long()]))

    def test_evenunder_keeps_a_whole_short_bar_but_not_a_long_one(self) -> None:
        bars = page(four(), self.short_even(), uneven_long(), four())
        notes, length = lay_out(bars, "anchor-all-keep3-evenunder", first_page=False)
        self.assertEqual(length, 4 + 2 + 4 + 4)
        self.assertEqual(starts(notes)[-4:], [10, 11, 12, 13])

    def test_time_keeps_a_bar_where_homr_read_a_time_signature(self) -> None:
        marked = measure(Fraction(6), quarters(4) + [element(Fraction(4), Fraction(2), container=2)])
        marked.time_here = True
        _, length = lay_out(page(four(), marked, four()), "anchor-all-keep3-time", first_page=False)
        self.assertEqual(length, 14)
        _, length = lay_out(page(four(), marked, four()), "anchor-all-keep3", first_page=False)
        self.assertEqual(length, 12)


if __name__ == "__main__":
    unittest.main()
