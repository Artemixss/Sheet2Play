from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

import tempo_read  # noqa: E402
import tempo_truth  # noqa: E402

LABEL = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="4.0"><part id="P1">
<measure number="1"><print/><direction placement="above"><direction-type><words>Andante</words></direction-type>
<direction-type><metronome parentheses="no"><beat-unit>quarter</beat-unit><beat-unit-dot/><per-minute>72</per-minute></metronome></direction-type>
<staff>1</staff><sound tempo="108"/></direction></measure>
<measure number="2"><direction placement="below"><direction-type><words>cresc.</words></direction-type></direction></measure>
<measure number="3"><print new-system="yes"/><direction placement="above"><direction-type><words>Più mosso (  = 147)</words></direction-type></direction></measure>
<measure number="4"><print new-page="yes"/><direction placement="above"><direction-type><words>a tempo</words></direction-type></direction></measure>
</part></score-partwise>"""


class TruthTests(unittest.TestCase):
    def test_label_truth_reads_metronomes_embedded_marks_and_tempo_words_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            label = Path(directory) / "label.musicxml"
            label.write_text(LABEL, encoding="utf-8")
            truth = tempo_truth.label_truth(label)
        self.assertEqual([(m["page"], m["system"], m["system_start"]) for m in truth["measures"]],
                         [(0, 0, True), (0, 0, False), (0, 1, True), (1, 0, True)])
        marks = [(m["measure"], m["words"], m["bpm"], m["unit"]) for m in truth["marks"]]
        # "cresc." is not a tempo word; the parenthesised mark came back as words with a SMuFL quarter.
        self.assertEqual(marks, [(0, "Andante", 72.0, "dotted_quarter"), (2, "Più mosso", 147.0, "quarter"),
                                 (3, "a tempo", None, None)])

    def test_plans_are_seeded_spaced_and_respect_existing_marks(self) -> None:
        meters = [(4, 4)] * 60
        first = tempo_truth.plan_marks("123", meters, set())
        self.assertEqual(first, tempo_truth.plan_marks("123", meters, set()))
        self.assertEqual(first[0]["measure"], 0)
        later = [plan["measure"] for plan in first[1:]]
        self.assertTrue(all(abs(a - b) >= 4 for a in later for b in later if a != b))
        self.assertNotIn(0, [plan["measure"] for plan in tempo_truth.plan_marks("123", meters, {0})])


class ParsingTests(unittest.TestCase):
    def test_bpm_follows_the_equals_sign_and_stays_in_range(self) -> None:
        self.assertEqual(tempo_read.parse_bpm("Andante quasi larghetto (J = 80)"), 80.0)
        self.assertEqual(tempo_read.parse_bpm("J=c. 120"), 120.0)
        self.assertIsNone(tempo_read.parse_bpm("Allegro"))
        self.assertIsNone(tempo_read.parse_bpm("= 900"))

    def test_lexicon_matches_whole_words_and_ignores_dynamics(self) -> None:
        self.assertEqual(tempo_read.lexicon_word("Più mosso"), "più mosso")
        self.assertEqual(tempo_read.lexicon_word("Andante con moto"), "andante con moto")
        self.assertIsNone(tempo_read.lexicon_word("cresc. poco a poco"))
        self.assertIsNone(tempo_read.lexicon_word("Largamente"))  # not "largo"


class LayoutTests(unittest.TestCase):
    def test_a_grand_staff_with_spanning_barlines_is_one_system_of_three_measures(self) -> None:
        page = np.full((600, 1000), 255, dtype=np.uint8)
        for top in (100, 260):
            for line in range(5):
                page[top + 15 * line:top + 15 * line + 2, 100:900] = 0
        page[100:322, 100:102] = 0  # the system's opening line
        for x in (370, 640, 898):
            page[100:322, x:x + 2] = 0
        for x in (200, 210):  # stems that fill a staff but not the gap
            page[100:162, x] = 0
            page[260:322, x] = 0
        systems = tempo_read.layout(page)
        self.assertEqual(len(systems), 1)
        self.assertEqual(len(systems[0].staves), 2)
        self.assertEqual(systems[0].measures, 3)


class UnitGlyphTests(unittest.TestCase):
    BOX = (100, 100, 260, 148)

    def mark(self, head: str, flag: bool = False, dot: bool = False, speck: bool = False) -> str | None:
        import cv2

        page = np.zeros((300, 400), dtype=np.uint8)
        page[104:139, 122:124] = 1  # stem
        cv2.ellipse(page, (116, 136), (7, 5), -20, 0, 360, 1, -1 if head == "filled" else 2)
        if flag:
            cv2.line(page, (123, 104), (131, 118), 1, 2)
        if dot:
            page[133:137, 127:131] = 1
        if speck:  # the top of a barline below the mark, just right of the note
            page[150:156, 126:128] = 1
        page[118:120, 140:157] = 1  # "="
        page[126:128, 140:157] = 1
        return tempo_read.classify_unit(page.astype(bool), self.BOX)[0]

    def test_heads_flags_and_dots_name_the_beat_unit(self) -> None:
        self.assertEqual(self.mark("filled"), "quarter")
        self.assertEqual(self.mark("filled", dot=True), "dotted_quarter")
        self.assertEqual(self.mark("hollow"), "half")
        self.assertEqual(self.mark("hollow", dot=True), "dotted_half")
        self.assertEqual(self.mark("filled", flag=True), "eighth")

    def test_a_speck_below_the_note_is_not_a_dot(self) -> None:
        self.assertEqual(self.mark("filled", speck=True), "quarter")


class ScoringTests(unittest.TestCase):
    def test_matching_counts_exact_wrong_missed_and_false_marks(self) -> None:
        mark = {"page": 0, "system": 0, "measure": 0, "bpm": 72.0, "unit": "quarter", "words": None}
        later = {**mark, "system": 2, "measure": 9, "bpm": 140.0}
        detection = {"page": 0, "system": 0, "measure": 0, "page_measure": 0, "bpm": 72.0, "unit": "quarter", "unit_source": "glyph",
                     "text": "J = 72", "suggestion": None}
        stray = {**detection, "system": 1, "measure": 5, "page_measure": 5, "bpm": 60.0}
        row = {"id": "x", "error": None, "pages": 1, "seconds": 1.0, "peak_rss_mib": 1.0, "measures": [[3, 3, 4]],
               "truth_measures_per_system": [[3, 3, 4]], "truth_page_first_measure": [0], "truth_marks": [mark, later], "detections": [detection, stray]}
        summary = tempo_read.score_rows([row])
        self.assertEqual(summary["mark_recall"], 0.5)
        self.assertEqual(summary["start_tempo_correct"], 1.0)
        self.assertEqual(summary["false_tempos_per_score"], 1.0)
        self.assertEqual(summary["layout_exact_page_fraction"], 1.0)

    def test_the_verdict_pools_the_test_splits_and_refuses_unfrozen_runs(self) -> None:
        import json
        mark = {"page": 0, "system": 0, "measure": 0, "bpm": 72.0, "unit": "quarter", "words": None}
        found = {"page": 0, "system": 0, "measure": 0, "page_measure": 0, "bpm": 72.0, "unit": "quarter",
                 "unit_source": "glyph", "text": "J = 72", "suggestion": None}
        base = {"error": None, "pages": 1, "seconds": 1.0, "peak_rss_mib": 1.0, "measures": [[3]],
                "truth_measures_per_system": [[3]], "truth_page_first_measure": [0]}
        rule = {"truth": {"start_tempo_correct": [">=", 0.75]}, "control": {"false_tempos_per_score": ["<=", 0.0]}}
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            saved = tempo_read.FREEZE
            tempo_read.FREEZE = root / "freeze.json"
            try:
                tempo_read.write_json(tempo_read.FREEZE, {"candidate": "ocr", "tempo_read_sha256": "frozen", "rule": rule})

                def run(name: str, split: str, kind: str, rows: list[dict], sha: str = "frozen") -> str:
                    path = root / name
                    path.mkdir()
                    tempo_read.write_json(path / "run.json", {"split": split, "set": kind, "candidate": "ocr", "tempo_read_sha256": sha})
                    (path / "rows.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
                    return str(path)

                right = {**base, "id": "a", "truth_marks": [mark], "detections": [found]}
                wrong = {**base, "id": "b", "truth_marks": [mark], "detections": [{**found, "bpm": 60.0}]}
                quiet = {**base, "id": "c", "truth_marks": [], "detections": []}
                args = type("Args", (), {})()
                args.truth = [run("t", "test", "truth", [right, right]), run("tb", "test-b", "truth", [right, wrong])]
                args.control = [run("c", "test", "control", [quiet]), run("cb", "test-b", "control", [quiet])]
                args.out = str(root / "verdict.json")
                tempo_read.verdict(args)
                result = json.loads((root / "verdict.json").read_text(encoding="utf-8"))
                self.assertEqual(result["sets"]["truth"]["pooled"]["start_tempo_correct"], 0.75)
                self.assertTrue(result["accepted"])
                args.control = [run("stale", "test", "control", [quiet], sha="other")]
                with self.assertRaises(SystemExit):
                    tempo_read.verdict(args)
            finally:
                tempo_read.FREEZE = saved


if __name__ == "__main__":
    unittest.main()
