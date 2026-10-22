import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tempo_words import return_kind, score_rows  # noqa: E402

# Shared with Visualization_engine.Tests/TempoTests.cs (TempoWords.Kind), so the app reads them the same way.
CASES = {
    "a tempo": "a_tempo",
    "A tempo": "a_tempo",
    "a Tempo.": "a_tempo",
    "sempre a tempo": "a_tempo",
    "poco rit. a tempo": "a_tempo",
    "a tempo (J = 71)": "a_tempo",
    "a tempo deciso": "a_tempo",
    "Tempo I": "first",
    "Tempo I.": "first",
    "Tempo l": "first",
    "Tempo 1°": "first",
    "a Tempo 1°": "first",
    "1° Tempo": "first",
    "Tempo primo": "first",
    "come prima": "first",
    "Tempo I (J = 44)": "first",
    "a tempo, più lento": None,
    "a tempo moins vite": None,
    "Tempo I ma più mosso": None,
    "Tempo di valse": None,
    "Tempo rubato": None,
    "Tempo lento": None,
    "Andante": None,
    "": None,
}


class ReturnKindTests(unittest.TestCase):
    def test_spellings(self) -> None:
        for text, kind in CASES.items():
            with self.subTest(text=text):
                self.assertEqual(return_kind(text), kind)


class ScoreTests(unittest.TestCase):
    def test_a_mark_read_from_the_next_system_is_false_and_its_truth_missed(self) -> None:
        row = {"id": "x", "truth_page_first_measure": [0],
               "truth_marks": [{"measure": 25, "page": 0, "system": 3, "words": "a tempo", "bpm": None}],
               "detections": [{"page": 0, "system": 4, "measure": 32, "page_measure": 32, "text": "a tempo"}]}
        result = score_rows([row])
        self.assertEqual(result["counts"]["matched"], 0)
        self.assertEqual(result["counts"]["false"], 1)
        self.assertEqual(result["return_precision"], 0.0)

    def test_a_matched_mark_checks_kind_and_page_bar(self) -> None:
        row = {"id": "x", "truth_page_first_measure": [0, 40],
               "truth_marks": [{"measure": 45, "page": 1, "system": 0, "words": "Tempo I", "bpm": None}],
               "detections": [{"page": 1, "system": 0, "measure": 45, "page_measure": 5, "text": "Tempo I."}]}
        result = score_rows([row])
        self.assertEqual(result["return_recall"], 1.0)
        self.assertEqual(result["kind_exact_of_matched"], 1.0)
        self.assertEqual(result["page_bar_exact_of_matched"], 1.0)


if __name__ == "__main__":
    unittest.main()
