import io
import sys
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tempo_word_corpus import (absolute_key, directions, evaluate, normalized_words,  # noqa: E402
                               relative_class, score_xml, sign_test, split_of, word_pairs)

SCORE = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="3.1"><part-list><score-part id="P1"/><score-part id="P2"/></part-list>
<part id="P1">
 <measure number="1"><attributes><time><beats>6</beats><beat-type>8</beat-type></time></attributes>
  <direction placement="above"><direction-type><words>Andante </words></direction-type>
   <direction-type><metronome><beat-unit>quarter</beat-unit><per-minute>76</per-minute></metronome></direction-type>
   <sound tempo="76"/></direction>
 </measure>
 <measure number="2">
  <direction><direction-type><metronome print-object="no"><beat-unit>quarter</beat-unit><per-minute>80</per-minute>
   </metronome></direction-type><sound tempo="80"/></direction>
 </measure>
 <measure number="3">
  <direction><direction-type><words>più mosso</words></direction-type><sound tempo="90"/></direction>
  <direction><direction-type><metronome><beat-unit>quarter</beat-unit><beat-unit-dot/><per-minute>c. 60</per-minute>
   </metronome></direction-type></direction>
 </measure>
</part>
<part id="P2"><measure number="1"><direction><direction-type><words>Allegro</words></direction-type></direction>
</measure></part>
</score-partwise>"""


def mxl(xml: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("META-INF/container.xml", '<container><rootfiles><rootfile full-path="score.xml"/>'
                                                   "</rootfiles></container>")
        archive.writestr("score.xml", xml)
    return buffer.getvalue()


class DirectionTests(unittest.TestCase):
    def test_visible_marks_of_the_first_part_with_their_bar(self) -> None:
        marks = directions(score_xml(mxl(SCORE)))
        self.assertEqual(marks, [
            {"bar": 0, "time": [6, 8], "words": "Andante", "unit": "quarter", "dots": 0, "per_minute": 76.0, "sound_tempo": "76"},
            {"bar": 2, "time": [6, 8], "words": "più mosso", "sound_tempo": "90"},
            {"bar": 2, "time": [6, 8], "unit": "quarter", "dots": 1, "per_minute": 60.0},
        ])

    def test_words_lose_numbers_glyphs_and_punctuation(self) -> None:
        self.assertEqual(normalized_words("Allegro moderato (♩ = c. 120)"), "allegro moderato")
        self.assertEqual(normalized_words("Andante, ma non troppo."), "andante ma non troppo")

    def test_a_group_always_lands_in_the_same_split(self) -> None:
        self.assertEqual(split_of("joe hisaishi"), split_of("joe hisaishi"))
        self.assertEqual({split_of(f"composer {index}") for index in range(40)}, {"dev", "held-out"})


class TableTests(unittest.TestCase):
    def test_words_are_sorted_into_kinds(self) -> None:
        self.assertEqual(relative_class("più mosso"), "faster")
        self.assertEqual(relative_class("poco meno mosso"), "slower")
        self.assertIsNone(relative_class("allegro con brio"))
        table = {"allegro": 130.0, "allegro moderato": 110.0}
        self.assertEqual(absolute_key("allegro con brio", table), "allegro")
        self.assertEqual(absolute_key("allegro moderato", table), "allegro moderato")
        self.assertIsNone(absolute_key("a tempo allegro", table))
        self.assertIsNone(absolute_key("swing", table))

    def test_the_sign_test_is_one_sided(self) -> None:
        self.assertAlmostEqual(sign_test(10, 0), 1 / 1024)
        self.assertEqual(sign_test(0, 0), 1.0)
        self.assertGreater(sign_test(3, 7), 0.5)

    def test_a_guess_is_the_table_tempo_in_quarters_and_relatives_use_the_number_before(self) -> None:
        score = {"marks": [
            {"bar": 0, "time": [6, 8], "words": "Allegro", "unit": "quarter", "dots": 1, "per_minute": 120.0},
            {"bar": 8, "time": [6, 8], "words": "Più mosso", "unit": "quarter", "dots": 1, "per_minute": 144.0},
            {"bar": 9, "time": [6, 8], "words": "Allegro", "unit": "quarter", "dots": 1, "per_minute": 60.0},
        ]}
        self.assertEqual([(words, previous) for words, _, previous in word_pairs(score)],
                         [("allegro", None), ("più mosso", 180.0)])
        result = evaluate([score], {"absolute": {"allegro": 180.0}, "relative": {"faster": 1.2}})
        self.assertEqual(result["absolute"]["pairs"], 1)
        self.assertEqual(result["absolute"]["median_error"], 0.0)
        self.assertAlmostEqual(result["relative"]["median_error"], 0.0)


class AppParityTests(unittest.TestCase):
    """The app's TempoWords.cs guesses with the survey's table (all PDMX pairs) and the same word lists."""

    APP = Path(__file__).resolve().parents[3] / "Visualization_engine/TempoWords.cs"
    SURVEY = Path(__file__).resolve().parents[1] / "reports/song-tempo/phase4/word-survey.json"

    def test_the_table_and_factors_match_the_survey(self) -> None:
        import json
        import re
        source = self.APP.read_text(encoding="utf-8")
        frozen = json.loads(self.SURVEY.read_text(encoding="utf-8"))["table_v2"]
        table = {words: float(value) for words, value in re.findall(r'\["([^"]+)"\] = ([\d.]+)', source)}
        self.assertEqual(table, frozen["absolute"])
        self.assertIn(f"FasterFactor = {frozen['relative']['faster']}", source)
        self.assertIn(f"SlowerFactor = {frozen['relative']['slower']}", source)

    def test_the_word_lists_match(self) -> None:
        import re
        import tempo_word_corpus
        source = self.APP.read_text(encoding="utf-8")
        for name, words in (("AbsoluteWords", tempo_word_corpus.ABSOLUTE), ("FasterWords", tempo_word_corpus.FASTER),
                            ("SlowerWords", tempo_word_corpus.SLOWER)):
            block = re.search(rf"{name} =\s*\[(.*?)\];", source, re.S).group(1)
            self.assertEqual(tuple(re.findall(r'"([^"]+)"', block)), words, name)


if __name__ == "__main__":
    unittest.main()
