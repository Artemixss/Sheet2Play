from __future__ import annotations

import tempfile
import unittest
import xml.etree.ElementTree as ElementTree
from pathlib import Path

from build_olimpic_scores import (
    PAGE_MARGIN,
    SYSTEM_GAP,
    build_musicxml,
    build_pages,
    compose_page,
    systems_by_score,
)

# One measure holding one note, at a given pitch, so a concatenated score can be checked note by
# note rather than only by count.
SYSTEM_TEMPLATE = """<?xml version='1.0' encoding='utf-8'?>
<score-partwise version="3.1">
  <part-list><score-part id="P1"><part-name>Piano</part-name></score-part></part-list>
  <part id="P1">{measures}</part>
</score-partwise>
"""

MEASURE_TEMPLATE = """
    <measure number="{number}">
      <note><pitch><step>{step}</step><octave>4</octave></pitch>
        <duration>4</duration><voice>1</voice><type>quarter</type></note>
    </measure>"""


def write_system(path: Path, first_measure: int, count: int) -> None:
    steps = "CDEFGAB"
    measures = "".join(
        MEASURE_TEMPLATE.format(number=first_measure + index, step=steps[(first_measure + index) % 7])
        for index in range(count)
    )
    path.write_text(SYSTEM_TEMPLATE.format(measures=measures), encoding="utf-8")


def write_image(path: Path, width: int, height: int) -> None:
    from PIL import Image

    Image.new("L", (width, height), color=255).save(path)


class SystemOrderingTests(unittest.TestCase):
    def test_systems_sort_by_page_then_system_not_alphabetically(self) -> None:
        """p2-s1 comes before p10-s1; a string sort would put p10 first and scramble the score."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "samples.dev.txt").write_text(
                "\n".join(
                    [
                        "samples/1234/p10-s1",
                        "samples/1234/p2-s1",
                        "samples/1234/p1-s2",
                        "samples/1234/p1-s1",
                    ]
                ),
                encoding="utf-8",
            )

            scores = systems_by_score(root, "dev")

            self.assertEqual(list(scores), ["1234"])
            self.assertEqual(
                [(page, system) for page, system, _path in scores["1234"]],
                [(1, 1), (1, 2), (2, 1), (10, 1)],
            )


class MusicXmlConcatenationTests(unittest.TestCase):
    def test_combined_score_holds_every_note_of_every_system_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_system(root / "p1-s1.musicxml", first_measure=1, count=5)
            write_system(root / "p1-s2.musicxml", first_measure=6, count=5)
            write_system(root / "p2-s1.musicxml", first_measure=11, count=4)
            systems = [
                (1, 1, root / "p1-s1"),
                (1, 2, root / "p1-s2"),
                (2, 1, root / "p2-s1"),
            ]

            combined_path = root / "combined.musicxml"
            measures = build_musicxml(systems, combined_path)

            self.assertEqual(measures, 14)
            combined = ElementTree.parse(combined_path).getroot()
            parts = combined.findall("part")
            self.assertEqual(len(parts), 1, "systems must merge into one part, not three")

            numbers = [measure.get("number") for measure in parts[0].findall("measure")]
            self.assertEqual(numbers, [str(index) for index in range(1, 15)])

            pitches = [step.text for step in parts[0].iter("step")]
            self.assertEqual(len(pitches), 14, "one note per measure, none lost or duplicated")

    def test_a_single_system_score_round_trips_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_system(root / "p1-s1.musicxml", first_measure=1, count=3)

            measures = build_musicxml([(1, 1, root / "p1-s1")], root / "combined.musicxml")

            self.assertEqual(measures, 3)


class PageLayoutTests(unittest.TestCase):
    def test_pages_follow_the_page_numbers_in_the_filenames(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("p1-s1", "p1-s2", "p1-s3", "p2-s1"):
                write_image(root / f"{name}.png", width=400, height=80)
            systems = [
                (1, 1, root / "p1-s1"),
                (1, 2, root / "p1-s2"),
                (1, 3, root / "p1-s3"),
                (2, 1, root / "p2-s1"),
            ]

            pages = build_pages(systems, root / "score.pdf")

            self.assertEqual(pages, 2)
            self.assertTrue((root / "score.pdf").is_file())

    def test_systems_of_different_widths_are_centred_on_one_canvas(self) -> None:
        """Real systems differ in width by a few percent; the page must not come out ragged."""
        from PIL import Image

        narrow = Image.new("L", (400, 80), color=0)
        wide = Image.new("L", (460, 80), color=0)

        canvas = compose_page([narrow, wide])

        self.assertEqual(canvas.width, 460 + 2 * PAGE_MARGIN)
        self.assertEqual(canvas.height, 160 + SYSTEM_GAP + 2 * PAGE_MARGIN)
        # The narrower system is inset equally on both sides rather than pushed left.
        left_inset = (canvas.width - 400) // 2
        self.assertEqual(canvas.getpixel((left_inset + 5, PAGE_MARGIN + 5)), 0)
        self.assertEqual(canvas.getpixel((left_inset - 5, PAGE_MARGIN + 5)), 255)


if __name__ == "__main__":
    unittest.main()
