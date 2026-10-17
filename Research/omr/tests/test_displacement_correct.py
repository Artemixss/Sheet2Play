from __future__ import annotations

import unittest
from fractions import Fraction

from displacement_correct import Element, PageMeasure, Staff, internal_holes, lay_out, source_hash


def element(offset: Fraction, duration: Fraction, container: int = 0, pitch: int = 60) -> Element:
    return Element(offset=offset, duration=duration, container=container, pitches=(pitch,), voice="1",
                   original=offset)


def measure(advance: Fraction, elements: list[Element], bar: Fraction = Fraction(4)) -> PageMeasure:
    return PageMeasure(start=Fraction(0), advance=advance, bar=bar, elements=elements)


def quarters(count: int, start: Fraction = Fraction(0), step: Fraction = Fraction(1)) -> list[Element]:
    return [element(start + index * step, Fraction(1), pitch=60 + index) for index in range(count)]


def starts(notes: list[tuple]) -> list[Fraction]:
    return sorted(start for *_, start, _ in notes)


class InternalHolesTest(unittest.TestCase):
    def test_a_hole_between_two_notes_counts(self) -> None:
        self.assertTrue(internal_holes(measure(Fraction(5), quarters(4, step=Fraction(4, 3)))))

    def test_a_late_entry_and_a_tie_past_the_bar_do_not(self) -> None:
        late = [element(Fraction(2), Fraction(1), container=2), element(Fraction(3), Fraction(1), container=2)]
        tie = [element(Fraction(0), Fraction(2)), element(Fraction(2), Fraction(3))]  # runs to beat 5
        self.assertFalse(internal_holes(measure(Fraction(4), late + tie)))


class LayOutTest(unittest.TestCase):
    def page(self) -> list[Staff]:
        # A correct short bar, a 4/4 bar that a lost backup stretched to 6 beats, then a 4/4 bar.
        short = measure(Fraction(2), quarters(2))
        stretched = measure(Fraction(6), [element(Fraction(0), Fraction(1)), element(Fraction(3), Fraction(1)),
                                          element(Fraction(4), Fraction(2))])
        return [Staff(part=0, staff=0, measures=[measure(Fraction(4), quarters(4)), short, stretched,
                                                  measure(Fraction(4), quarters(4))])]

    def test_anchor_holes_shortens_only_the_stretched_bar(self) -> None:
        notes, length = lay_out(self.page(), "anchor-holes", first_page=False)
        self.assertEqual(length, 4 + 2 + 4 + 4)
        self.assertEqual(starts(notes)[-4:], [10, 11, 12, 13])

    def test_plain_anchor_also_forces_the_short_bar(self) -> None:
        _, length = lay_out(self.page(), "anchor", first_page=False)
        self.assertEqual(length, 16)

    def test_an_opening_pickup_keeps_its_length(self) -> None:
        pickup = [Staff(part=0, staff=0, measures=[measure(Fraction(1), quarters(1)), measure(Fraction(4), quarters(4))])]
        notes, length = lay_out(pickup, "anchor", first_page=True)
        self.assertEqual(length, 5)
        self.assertEqual(starts(notes), [0, 1, 2, 3, 4])

    def test_the_control_leaves_the_app_placement_alone(self) -> None:
        notes, length = lay_out(self.page(), "control", first_page=False)
        self.assertEqual(length, -1)
        self.assertEqual(len(notes), 4 + 2 + 3 + 4)


class MeterGateTest(unittest.TestCase):
    """anchor-holes-keepN keeps a hole measure's length when N hole-free measures share it."""

    def hole_bar(self, length: Fraction) -> PageMeasure:
        notes = [element(Fraction(0), Fraction(1)), element(length - 1, Fraction(1))]
        return measure(length, notes)

    def page(self) -> list[Staff]:
        # A 4/4 page that turns to 3/4: two clean 3/4 bars, then a 3/4 bar with a held-over hole
        # (a real meter), and later a 4/4 bar a lost backup stretched to 6 (an error).
        three = [measure(Fraction(3), quarters(3)), measure(Fraction(3), quarters(3))]
        bars = [measure(Fraction(4), quarters(4)), measure(Fraction(4), quarters(4)), *three,
                self.hole_bar(Fraction(3)), self.hole_bar(Fraction(6)), measure(Fraction(4), quarters(4))]
        return [Staff(part=0, staff=0, measures=bars)]

    def test_a_recurring_minority_meter_survives(self) -> None:
        _, plain = lay_out(self.page(), "anchor-holes", first_page=False)
        _, gated = lay_out(self.page(), "anchor-holes-keep2", first_page=False)
        self.assertEqual(plain, 4 + 4 + 3 + 3 + 4 + 4 + 4)
        self.assertEqual(gated, 4 + 4 + 3 + 3 + 3 + 4 + 4)

    def test_a_length_seen_once_is_still_anchored(self) -> None:
        _, gated = lay_out(self.page(), "anchor-holes-keep3", first_page=False)
        self.assertEqual(gated, 4 + 4 + 3 + 3 + 4 + 4 + 4)

    def test_a_clean_neighbour_counts_with_nb(self) -> None:
        _, gated = lay_out(self.page(), "anchor-holes-keep9-nb", first_page=False)
        self.assertEqual(gated, 4 + 4 + 3 + 3 + 3 + 4 + 4)


class FitTest(unittest.TestCase):
    """fit moves a voice a lost backup started late, and only if the whole bar then fits."""

    def test_a_late_voice_moves_back_to_the_bar(self) -> None:
        # 2/4: the upper voice is right; a half note in voice 2 starts at 1/4 instead of 0.
        late = measure(Fraction(9, 4), quarters(2) + [element(Fraction(1, 4), Fraction(2), container=2)],
                       bar=Fraction(2))
        page = [Staff(part=0, staff=0, measures=[late, measure(Fraction(2), quarters(2), bar=Fraction(2))])]
        notes, length = lay_out(page, "fit", first_page=False)
        self.assertEqual(length, 4)
        self.assertEqual(starts(notes), [0, 0, 1, 2, 3])

    def test_a_real_longer_bar_is_left_alone(self) -> None:
        # A 3/4 bar on a 2/4 page: its main voice runs from beat 0, so nothing can fit.
        longer = measure(Fraction(3), quarters(3) + [element(Fraction(1), Fraction(2), container=2)], bar=Fraction(2))
        page = [Staff(part=0, staff=0, measures=[longer])]
        notes, length = lay_out(page, "fit", first_page=False)
        self.assertEqual(length, 3)
        self.assertEqual(starts(notes), [0, 1, 1, 2])


class FreezeTest(unittest.TestCase):
    def test_the_hash_ignores_line_endings(self) -> None:
        self.assertEqual(len(source_hash()), 64)


if __name__ == "__main__":
    unittest.main()
