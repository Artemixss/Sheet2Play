from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

BRIDGE_DIRECTORY = Path(__file__).resolve().parents[1]
if str(BRIDGE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(BRIDGE_DIRECTORY))

import timing_correction  # noqa: E402
from musicxml_normalizer import combine_score_pages, normalize_musicxml  # noqa: E402

# 2/4. Measure 2 has the fault HOMR's exporter makes: its <backup> is one beat short, so the
# second voice's half note starts on beat 2 and the measure overflows to three beats.
LOST_BACKUP_PAGE = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="4.0">
  <part-list><score-part id="P1"><part-name>Piano</part-name></score-part></part-list>
  <part id="P1">
    <measure number="1">
      <attributes><divisions>1</divisions><time><beats>2</beats><beat-type>4</beat-type></time>
        <clef><sign>G</sign><line>2</line></clef></attributes>
      <note><pitch><step>C</step><octave>4</octave></pitch><duration>2</duration><voice>1</voice><type>half</type></note>
    </measure>
    <measure number="2">
      <note><pitch><step>E</step><octave>4</octave></pitch><duration>1</duration><voice>1</voice><type>quarter</type></note>
      <note><pitch><step>F</step><octave>4</octave></pitch><duration>1</duration><voice>1</voice><type>quarter</type></note>
      <backup><duration>1</duration></backup>
      <note><pitch><step>G</step><octave>3</octave></pitch><duration>2</duration><voice>2</voice><type>half</type></note>
    </measure>
    <measure number="3">
      <note><pitch><step>D</step><octave>4</octave></pitch><duration>2</duration><voice>1</voice><type>half</type></note>
    </measure>
  </part>
</score-partwise>
"""


def page_of(*measures: str) -> str:
    """A 2/4 piano page whose measures hold the given notes, the first carrying the attributes."""
    body = "".join(f'<measure number="{number}">{notes}</measure>' for number, notes in enumerate(measures, start=1))
    body = body.replace('<measure number="1">', '<measure number="1"><attributes><divisions>1</divisions>'
                        '<time><beats>2</beats><beat-type>4</beat-type></time><clef><sign>G</sign><line>2</line>'
                        '</clef></attributes>', 1)
    return ('<?xml version="1.0" encoding="UTF-8"?><score-partwise version="4.0"><part-list>'
            '<score-part id="P1"><part-name>Piano</part-name></score-part></part-list>'
            f'<part id="P1">{body}</part></score-partwise>')


def note(step: str, octave: int, beats: int, voice: int = 1) -> str:
    kind = {1: "quarter", 2: "half"}[beats]
    return (f"<note><pitch><step>{step}</step><octave>{octave}</octave></pitch><duration>{beats}</duration>"
            f"<voice>{voice}</voice><type>{kind}</type></note>")


def backup(beats: int) -> str:
    return f"<backup><duration>{beats}</duration></backup>"


def starts(score) -> dict[int, float]:
    return {note.midi_pitch: note.start_beat for note in score.notes}


class TimingCorrectionTests(unittest.TestCase):
    def test_a_late_voice_moves_back_into_its_bar(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "page.musicxml"
            path.write_text(LOST_BACKUP_PAGE, encoding="utf-8")
            page = normalize_musicxml(path)
            self.assertEqual(starts(page)[55], 3.0)  # G3, a beat late
            self.assertEqual(page.total_beats, 7.0)
            corrected = timing_correction.correct_page(path, page, first_page=False)
        self.assertEqual(starts(corrected), {60: 0.0, 64: 2.0, 65: 3.0, 55: 2.0, 62: 4.0})
        self.assertEqual(corrected.total_beats, 6.0)
        # The next page starts on the corrected bar line, through the bridge's own stitching.
        self.assertEqual(combine_score_pages([corrected, corrected]).notes[-1].start_beat, 10.0)

    def correct(self, xml: str):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "page.musicxml"
            path.write_text(xml, encoding="utf-8")
            page = normalize_musicxml(path)
            return page, timing_correction.correct_page(path, page, first_page=False)

    def test_an_overlong_bar_without_holes_is_anchored(self) -> None:
        # Measure 2 reads an extra quarter in its upper voice: three beats against the lower
        # voice's two, no hole, too long to fit. Its voices end unevenly, so it is anchored.
        page, corrected = self.correct(page_of(
            note("C", 4, 2),
            note("E", 4, 1) + note("F", 4, 1) + note("G", 4, 1) + backup(3) + note("G", 3, 2, voice=2),
            note("D", 4, 2)))
        self.assertEqual(page.total_beats, 7.0)
        self.assertEqual(corrected.total_beats, 6.0)
        self.assertEqual(starts(corrected)[62], 4.0)

    def test_a_short_bar_whose_voices_end_together_keeps_its_length(self) -> None:
        # A real one-beat bar: both voices end on beat one, so it is not stretched to the meter.
        page, corrected = self.correct(page_of(
            note("C", 4, 2), note("C", 4, 2),
            note("E", 4, 1) + backup(1) + note("G", 3, 1, voice=2),
            note("D", 4, 2)))
        self.assertEqual(corrected.total_beats, page.total_beats)
        self.assertEqual(starts(corrected)[62], 5.0)

    def test_a_page_that_cannot_be_matched_keeps_the_app_reading(self) -> None:
        page = SimpleNamespace(name="page")
        fake_bridge = SimpleNamespace(normalize_musicxml=lambda path: page)
        timing_correction.install(fake_bridge)
        with mock.patch.object(timing_correction, "correct_page", side_effect=ValueError("no match")):
            self.assertIs(fake_bridge.normalize_musicxml(Path("page-0001.musicxml")), page)

    def test_only_homr_engines_are_wrapped(self) -> None:
        self.assertEqual(timing_correction.engine_argument(["--engine", "homr465", "a.pdf"]), "homr465")
        self.assertEqual(timing_correction.engine_argument(["--engine=homr", "a.pdf"]), "homr")
        fake_bridge = SimpleNamespace(normalize_musicxml=object(), main=lambda arguments: 0)
        original = fake_bridge.normalize_musicxml
        with mock.patch.dict(sys.modules, {"bridge": fake_bridge}):
            self.assertEqual(timing_correction.main(["--engine", "zeus", "a.pdf"]), 0)
            self.assertIs(fake_bridge.normalize_musicxml, original)
            timing_correction.main(["--engine", "homr", "a.pdf"])
            self.assertIsNot(fake_bridge.normalize_musicxml, original)


if __name__ == "__main__":
    unittest.main()
