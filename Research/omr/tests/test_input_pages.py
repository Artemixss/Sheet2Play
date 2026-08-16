from __future__ import annotations

import tempfile
import unittest
import importlib.util
from pathlib import Path

from PIL import Image

from sheet2play_omr.input_pages import TARGET_HEIGHT, TARGET_WIDTH, inspect_page_count, iter_document_pages, normalize_page


class InputPageTests(unittest.TestCase):
    def test_normalization_uses_fixed_canvas_without_aspect_distortion(self) -> None:
        source = Image.new("RGBA", (400, 800), (0, 0, 0, 0))
        normalized = normalize_page(source)
        self.assertEqual((TARGET_WIDTH, TARGET_HEIGHT), normalized.size)
        self.assertEqual("RGB", normalized.mode)
        source.close()
        normalized.close()

    def test_multiframe_tiff_is_processed_one_frame_at_a_time(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "score.tiff"
            first = Image.new("RGB", (100, 200), "white")
            second = Image.new("RGB", (120, 220), "white")
            first.save(path, save_all=True, append_images=[second])
            first.close()
            second.close()
            self.assertEqual(2, inspect_page_count(path))
            with iter_document_pages(path) as pages:
                page_list = []
                for info, image in pages:
                    page_list.append((info.number, info.total, image.size))
                    image.close()
            self.assertEqual([(1, 2, (100, 200)), (2, 2, (120, 220))], page_list)

    @unittest.skipUnless(importlib.util.find_spec("pypdfium2"), "pypdfium2 is not installed")
    def test_pdf_page_count_and_rendering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "score.pdf"
            first = Image.new("RGB", (200, 300), "white")
            second = Image.new("RGB", (200, 300), "white")
            first.save(path, save_all=True, append_images=[second], resolution=300)
            first.close()
            second.close()
            self.assertEqual(2, inspect_page_count(path))
            with iter_document_pages(path) as pages:
                rendered = []
                for info, image in pages:
                    rendered.append((info.number, info.total, image.width > 0, image.height > 0))
                    image.close()
            self.assertEqual([(1, 2, True, True), (2, 2, True, True)], rendered)


if __name__ == "__main__":
    unittest.main()
