"""The shipped tempo reader (`Bridge/tempo_marks.py`) must read exactly as the frozen research reader.

Phase 3 of the per-song tempo plan ships Phase 2's OCR reader. Its accuracy was measured on the
frozen `tempo_read.py`, so every function the bridge copies must still be that function, word
for word, and the constants it restates must be equal.
"""

from __future__ import annotations

import ast
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
BRIDGE = HERE.parents[1] / "Bridge"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(BRIDGE))

import tempo_marks  # noqa: E402
import tempo_read  # noqa: E402

COPIED = ["Staff", "System", "render", "page_count", "longest_run", "find_staves", "group_systems", "find_barlines",
          "repeat_dots_after", "layout", "lexicon_word", "parse_bpm", "strip_region", "classify_unit", "Detection",
          "read_page_ocr", "place_bars"]


def definitions(path: Path) -> dict[str, str]:
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    found = {}
    for node in ast.parse(source).body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            start = (node.decorator_list[0].lineno if node.decorator_list else node.lineno) - 1
            found[node.name] = "\n".join(lines[start:node.end_lineno])
    return found


class ParityTests(unittest.TestCase):
    def test_every_copied_definition_is_the_frozen_one_word_for_word(self) -> None:
        research = definitions(HERE / "tempo_read.py")
        shipped = definitions(BRIDGE / "tempo_marks.py")
        for name in COPIED:
            with self.subTest(name=name):
                self.assertEqual(shipped[name], research[name])

    def test_the_restated_constants_and_ocr_settings_are_equal(self) -> None:
        self.assertEqual(tempo_marks.DPI, tempo_read.DPI)
        self.assertEqual(tempo_marks.BPM_RANGE, tempo_read.BPM_RANGE)
        self.assertEqual(tempo_marks.BPM_PATTERN.pattern, tempo_read.BPM_PATTERN.pattern)
        self.assertEqual(tempo_marks.FROZEN_LEXICON, tempo_read.LEXICON)
        self.assertEqual(tempo_marks.UNIT_NAMES, tempo_read.UNIT_NAMES)
        self.assertEqual(tempo_marks.OcrReader.SETTINGS, tempo_read.OcrReader.SETTINGS)

    def test_the_shipped_lexicon_is_the_frozen_one_plus_words_that_are_never_numbers(self) -> None:
        self.assertEqual(set(tempo_marks.LEXICON), set(tempo_marks.FROZEN_LEXICON) | set(tempo_marks.EXTRA_WORDS))
        for word in tempo_marks.EXTRA_WORDS:
            with self.subTest(word=word):
                self.assertIsNone(tempo_marks.parse_bpm(word))
        self.assertEqual(tempo_marks.lexicon_word("Agitato"), "agitato")
        self.assertEqual(tempo_marks.lexicon_word("Più mosso"), "più mosso")
        self.assertEqual(tempo_marks.lexicon_word("Lento"), "lento")

    def test_every_word_the_app_guesses_for_reaches_it(self) -> None:
        import tempo_word_corpus
        for word in (*tempo_word_corpus.ABSOLUTE, *tempo_word_corpus.FASTER, *tempo_word_corpus.SLOWER):
            with self.subTest(word=word):
                self.assertEqual(tempo_marks.lexicon_word(word.capitalize()), word)

    def test_it_names_the_reader_that_was_frozen_before_the_test_splits(self) -> None:
        frozen = json.loads((tempo_read.FREEZE).read_text(encoding="utf-8"))
        self.assertEqual(tempo_marks.FROZEN_READER_SHA256, frozen["tempo_read_sha256"])


if __name__ == "__main__":
    unittest.main()
