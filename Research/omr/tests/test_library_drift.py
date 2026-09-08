from __future__ import annotations

import unittest
from fractions import Fraction

from diagnose_library_drift import (
    apply_local_offsets,
    best_global_offset,
    classify,
    local_offsets,
    modal_offset,
    pitch_agreement,
    shift_notes,
)
from sheet2play_omr.metrics import MetricNote, calculate_note_metrics

WINDOW = Fraction(16)

# Distinct pitches per beat, so a mistaken alignment cannot pick up an accidental match from a
# pitch that repeats. Real music is not this obliging, which is why MIN_SUPPORT exists.
PITCHES = [60, 62, 64, 65, 67, 69, 71, 72]


def straight_score(beats: int, start: Fraction = Fraction(0)) -> list[MetricNote]:
    """One note on every quarter, cycling through PITCHES."""
    return [
        MetricNote(
            pitch=PITCHES[index % len(PITCHES)],
            onset=start + Fraction(index),
            duration=Fraction(1),
            staff=0,
            voice="1",
        )
        for index in range(beats)
    ]


def displace_per_window(
    notes: list[MetricNote], deltas: list[Fraction], window: Fraction = WINDOW
) -> list[MetricNote]:
    """Shift each note by the delta of the window it falls in - a synthetic drift curve."""
    moved = []
    for note in notes:
        index = min(int(note.onset // window), len(deltas) - 1)
        moved.append(
            MetricNote(
                pitch=note.pitch,
                onset=note.onset + deltas[index],
                duration=note.duration,
                staff=note.staff,
                voice=note.voice,
            )
        )
    return moved


class GlobalOffsetTests(unittest.TestCase):
    def test_constant_shift_is_recovered_exactly(self) -> None:
        truth = straight_score(48)
        predicted = shift_notes(truth, Fraction(-4))

        delta, support = modal_offset(predicted, truth)

        self.assertEqual(delta, Fraction(4))
        self.assertGreaterEqual(support, 40)

    def test_a_shifted_score_scores_zero_until_it_is_shifted_back(self) -> None:
        """The premise of the whole diagnosis: displacement is invisible to onset F1."""
        truth = straight_score(48)
        predicted = shift_notes(truth, Fraction(-4))

        self.assertEqual(calculate_note_metrics(predicted, truth).pitch_f1, 1.0)
        self.assertLess(calculate_note_metrics(predicted, truth).onset_f1, 0.95)

        result = best_global_offset(predicted, truth)

        self.assertEqual(result["delta"], 4.0)
        self.assertEqual(result["onset_f1"], 1.0)
        self.assertGreater(result["gain"], 0.05)

    def test_an_aligned_score_reports_no_shift(self) -> None:
        truth = straight_score(48)

        result = best_global_offset(list(truth), truth)

        self.assertEqual(result["delta"], 0.0)
        self.assertEqual(result["gain"], 0.0)
        self.assertEqual(result["onset_f1"], 1.0)

    def test_a_fractional_shift_is_recovered_exactly(self) -> None:
        """Offsets are not always whole beats - a short final measure moves things by a third."""
        truth = straight_score(48)
        predicted = shift_notes(truth, Fraction(-1, 3))

        result = best_global_offset(predicted, truth)

        self.assertEqual(Fraction(result["delta"]).limit_denominator(64), Fraction(1, 3))
        self.assertEqual(result["onset_f1"], 1.0)


class LocalCurveTests(unittest.TestCase):
    def test_accumulating_drift_reads_as_a_ramp_not_a_step(self) -> None:
        truth = straight_score(96)
        deltas = [Fraction(index) for index in range(6)]
        predicted = displace_per_window(truth, deltas)

        windows = local_offsets(predicted, truth, WINDOW)
        supported = [entry for entry in windows if entry["support"] >= 4]

        self.assertGreaterEqual(len(supported), 5)
        self.assertEqual(
            [entry["delta"] for entry in supported[:6]],
            [0.0, -1.0, -2.0, -3.0, -4.0, -5.0],
        )
        self.assertIn("ramp", classify(windows, best_global_offset(predicted, truth)))

    def test_a_single_jump_reads_as_a_step(self) -> None:
        truth = straight_score(96)
        deltas = [Fraction(0)] * 3 + [Fraction(2)] * 3
        predicted = displace_per_window(truth, deltas)

        windows = local_offsets(predicted, truth, WINDOW)

        self.assertIn("steps", classify(windows, best_global_offset(predicted, truth)))

    def test_scatter_leaves_windows_without_a_consistent_offset(self) -> None:
        """Onsets moved individually, not as a block: there is no local offset to find."""
        truth = straight_score(96)
        predicted = [
            MetricNote(
                pitch=note.pitch,
                onset=note.onset + Fraction((index * 7) % 5, 4),
                duration=note.duration,
                staff=note.staff,
                voice=note.voice,
            )
            for index, note in enumerate(truth)
        ]

        windows = local_offsets(predicted, truth, WINDOW)
        strong = [entry for entry in windows if entry["support"] >= 4 and entry["notes"]]

        self.assertTrue(all(entry["support"] < 12 for entry in strong))

    def test_local_correction_recovers_a_drifted_score(self) -> None:
        """The headline number: displacement is fully recoverable, genuine scatter is not."""
        truth = straight_score(96)
        deltas = [Fraction(index) for index in range(6)]
        predicted = displace_per_window(truth, deltas)

        windows = local_offsets(predicted, truth, WINDOW)
        corrected = apply_local_offsets(predicted, windows, WINDOW)

        # Not 1.0, and that is the honest ceiling: a note displaced across a window boundary is
        # indexed into its neighbour's window and gets that window's offset. The estimate
        # therefore understates what is recoverable, which is the safe direction for a claim
        # that displacement rather than the engine is at fault.
        self.assertLess(calculate_note_metrics(predicted, truth).onset_f1, 0.6)
        self.assertGreater(calculate_note_metrics(corrected, truth).onset_f1, 0.85)


class ReferenceSanityTests(unittest.TestCase):
    def test_pitch_agreement_ignores_time(self) -> None:
        truth = straight_score(48)
        predicted = shift_notes(truth, Fraction(-4))

        self.assertEqual(pitch_agreement(predicted, truth), 1.0)

    def test_pitch_agreement_falls_when_the_arrangement_differs(self) -> None:
        truth = straight_score(48)
        # Transposed by an octave and a semitone, so no transposed pitch collides with one that
        # PITCHES already contains and the disagreement is exactly half.
        predicted = [
            MetricNote(note.pitch + 13, note.onset, note.duration, note.staff, note.voice)
            for note in truth[:24]
        ] + list(truth[24:])

        self.assertEqual(pitch_agreement(predicted, truth), 0.5)


if __name__ == "__main__":
    unittest.main()
