from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from sheet2play_omr.omr_ned import score_pair

FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "transcoda-baseline"
    / "baseline-piano.krn"
)


def _musicdiff_available() -> bool:
    try:
        import musicdiff  # noqa: F401
    except ImportError:
        return False
    return True


@unittest.skipUnless(_musicdiff_available(), "musicdiff is not installed")
class OmrNedTests(unittest.TestCase):
    """OMR-NED runs in the opposite direction to every other metric here: lower is better.

    These tests pin that direction as much as the arithmetic, because a silent sign flip
    would make a worse engine look better and would not otherwise be obvious.
    """

    def test_identical_scores_have_zero_distance(self) -> None:
        result = score_pair(FIXTURE, FIXTURE)
        self.assertIsNotNone(result)
        self.assertEqual(0.0, result.score)
        self.assertEqual(0, result.edit_distance)
        self.assertEqual(result.ground_truth_symbols, result.predicted_symbols)
        self.assertEqual(1.0, result.accuracy_like)

    def test_a_damaged_score_is_penalised(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            damaged = Path(temporary) / "damaged.krn"
            lines = FIXTURE.read_text(encoding="utf-8").splitlines()
            # Drop a run of data records; the exact content does not matter, only that the
            # prediction is now missing symbols the ground truth has.
            kept = [line for index, line in enumerate(lines) if not (20 <= index < 40)]
            damaged.write_text("\n".join(kept) + "\n", encoding="utf-8")

            result = score_pair(damaged, FIXTURE)

        self.assertIsNotNone(result)
        self.assertGreater(result.score, 0.0)
        self.assertLess(result.accuracy_like, 1.0)

    def test_score_is_symmetric_enough_to_be_a_distance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copy = Path(temporary) / "copy.krn"
            shutil.copyfile(FIXTURE, copy)
            self.assertEqual(0.0, score_pair(copy, FIXTURE).score)
            self.assertEqual(0.0, score_pair(FIXTURE, copy).score)


if __name__ == "__main__":
    unittest.main()
