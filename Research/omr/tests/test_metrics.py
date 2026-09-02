from __future__ import annotations

import unittest
from fractions import Fraction

from sheet2play_omr.metrics import (
    MetricNote,
    calculate_note_metrics,
    span_ratio,
    timeline_span,
)


class MetricTests(unittest.TestCase):
    def test_exact_score_is_perfect_with_renamed_voices(self) -> None:
        expected = [
            MetricNote(60, Fraction(0), Fraction(1), 0, "upper"),
            MetricNote(60, Fraction(0), Fraction(1), 0, "lower"),
            MetricNote(48, Fraction(0), Fraction(2), 1, "bass"),
        ]
        predicted = [
            MetricNote(60, Fraction(0), Fraction(1), 0, "voice-9"),
            MetricNote(60, Fraction(0), Fraction(1), 0, "voice-2"),
            MetricNote(48, Fraction(0), Fraction(2), 1, "voice-x"),
        ]
        metrics = calculate_note_metrics(predicted, expected)
        self.assertEqual(1.0, metrics.pitch_f1)
        self.assertEqual(1.0, metrics.onset_duration_f1)
        self.assertEqual(1.0, metrics.aligned_voice_accuracy)

    def test_duration_error_preserves_pitch_and_onset(self) -> None:
        expected = [MetricNote(60, Fraction(0), Fraction(1), 0, "1")]
        predicted = [MetricNote(60, Fraction(0), Fraction(2), 0, "1")]
        metrics = calculate_note_metrics(predicted, expected)
        self.assertEqual(1.0, metrics.pitch_f1)
        self.assertEqual(1.0, metrics.onset_f1)
        self.assertEqual(0.0, metrics.onset_duration_f1)
        self.assertEqual(1.0, metrics.mean_offset_error)



class SpanRatioTests(unittest.TestCase):
    """span_ratio is the Step 1 diagnosis's best single predictor of onset accuracy.

    On the OLiMPiC canary, systems within 1.02x scored 0.884 onset F1 while those beyond
    1.15x scored 0.269, so these tests pin the behaviour the diagnosis relies on.
    """

    @staticmethod
    def note(onset: int | Fraction, duration: int | Fraction) -> MetricNote:
        return MetricNote(60, Fraction(onset), Fraction(duration), 0, "1")

    def test_identical_timelines_score_one(self) -> None:
        notes = [self.note(0, 1), self.note(1, 1), self.note(2, 2)]
        self.assertEqual(1.0, span_ratio(notes, notes))

    def test_doubled_durations_double_the_ratio(self) -> None:
        expected = [self.note(0, 1), self.note(1, 1), self.note(2, 1), self.note(3, 1)]
        predicted = [self.note(0, 2), self.note(2, 2), self.note(4, 2), self.note(6, 2)]
        self.assertEqual(2.0, span_ratio(predicted, expected))

    def test_inflation_is_detected_without_any_pitch_error(self) -> None:
        """The signature that matters: right notes, longer timeline."""
        expected = [self.note(0, Fraction(3, 2)), self.note(Fraction(3, 2), Fraction(1, 2))]
        predicted = [self.note(0, Fraction(3, 2)), self.note(2, Fraction(1, 2))]
        ratio = span_ratio(predicted, expected)
        self.assertIsNotNone(ratio)
        self.assertGreater(ratio, 1.0)
        self.assertAlmostEqual(2.5 / 2.0, ratio)

    def test_empty_ground_truth_is_undefined_rather_than_zero(self) -> None:
        self.assertIsNone(span_ratio([self.note(0, 1)], []))

    def test_empty_prediction_scores_zero(self) -> None:
        self.assertEqual(0.0, span_ratio([], [self.note(0, 1)]))

    def test_timeline_span_uses_the_latest_offset_not_the_latest_onset(self) -> None:
        # A long note starting early must extend the span past a short later one.
        notes = [self.note(0, 8), self.note(1, 1)]
        self.assertEqual(Fraction(8), timeline_span(notes))


if __name__ == "__main__":
    unittest.main()

