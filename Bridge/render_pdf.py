from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Sequence


LOGGER = logging.getLogger("sheet2play.pdf-renderer")


class PdfRenderError(RuntimeError):
    pass


def parse_arguments(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render PDF pages to PNG images.")
    parser.add_argument("input_path", type=Path)
    parser.add_argument("output_directory", type=Path)
    return parser.parse_args(arguments)


def render_pdf(input_path: Path, output_directory: Path) -> int:
    try:
        import pymupdf
    except ImportError as error:
        raise PdfRenderError("PyMuPDF is unavailable in the PDF renderer environment.") from error

    try:
        document = pymupdf.open(input_path)
    except Exception as error:
        raise PdfRenderError(f"Cannot open PDF '{input_path}': {error}") from error

    page_count = document.page_count
    with document:
        if page_count == 0:
            raise PdfRenderError(f"PDF contains no pages: {input_path}")

        output_directory.mkdir(parents=True, exist_ok=True)
        scale = 300 / 72
        matrix = pymupdf.Matrix(scale, scale)

        for page_index, page in enumerate(document):
            output_path = output_directory / f"page-{page_index + 1:04d}.png"
            try:
                pixmap = page.get_pixmap(
                    matrix=matrix,
                    colorspace=pymupdf.csRGB,
                    alpha=False,
                )
                pixmap.save(output_path)
            except Exception as error:
                raise PdfRenderError(
                    f"Failed to render PDF page {page_index + 1}: {error}"
                ) from error

    return page_count


def main(arguments: Sequence[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )

    try:
        parsed = parse_arguments(arguments)
        page_count = render_pdf(parsed.input_path, parsed.output_directory)
        LOGGER.info("Rendered %d PDF page(s)", page_count)
        return 0
    except PdfRenderError as error:
        LOGGER.error("%s", error)
        return 1
    except Exception:
        LOGGER.exception("Unexpected PDF rendering failure")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
