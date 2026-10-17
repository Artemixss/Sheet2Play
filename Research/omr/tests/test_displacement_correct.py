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


class FreezeTest(unittest.TestCase):
    def test_the_hash_ignores_line_endings(self) -> None:
        self.assertEqual(len(source_hash()), 64)


if __name__ == "__main__":
    unittest.main()
