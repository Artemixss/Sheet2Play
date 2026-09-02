from __future__ import annotations

import unittest
from pathlib import Path

from sheet2play_omr.errors import ResearchError
from sheet2play_omr.inference import infer_document


class InferenceModeTests(unittest.TestCase):
    def test_only_the_zeus_engine_is_accepted(self) -> None:
        for mode in ("beam", "grammar", "transcoda"):
            with self.subTest(mode=mode):
                with self.assertRaises(ResearchError) as raised:
                    infer_document(Path("missing.pdf"), Path("artifacts"), mode)
                self.assertEqual("DECODER_INVALID", raised.exception.code)
                self.assertEqual("inference", raised.exception.stage)


if __name__ == "__main__":
    unittest.main()
