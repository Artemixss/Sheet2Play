from __future__ import annotations

import sys
import unittest
from pathlib import Path


BRIDGE_DIRECTORY = Path(__file__).resolve().parents[1]
if str(BRIDGE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(BRIDGE_DIRECTORY))

from evaluate_omr import EvaluationNote, evaluate  # noqa: E402


class EvaluateOmrTests(unittest.TestCase):
    def test_exact_score_has_perfect_metrics(self) -> None:
        notes = [
            EvaluationNote(60, 0, 1),
            EvaluationNote(64, 1, 2),
        ]
        metrics = evaluate(notes, notes)
        self.assertEqual(metrics.pitch_f1, 1.0)
        self.assertEqual(metrics.onset_and_duration_f1, 1.0)
        self.assertEqual(metrics.mean_overlap_iou, 1.0)

    def test_wrong_duration_preserves_pitch_but_fails_structure(self) -> None:
        truth = [EvaluationNote(60, 0, 1)]
        prediction = [EvaluationNote(60, 0, 2)]
        metrics = evaluate(truth, prediction)
        self.assertEqual(metrics.pitch_f1, 1.0)
        self.assertEqual(metrics.onset_f1, 1.0)
        self.assertEqual(metrics.onset_and_duration_f1, 0.0)
        self.assertEqual(metrics.mean_overlap_iou, 0.5)


if __name__ == "__main__":
    unittest.main()
