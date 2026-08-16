from __future__ import annotations

import unittest
from fractions import Fraction

from sheet2play_omr.metrics import MetricNote, calculate_note_metrics


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


if __name__ == "__main__":
    unittest.main()

