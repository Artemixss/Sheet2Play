from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps

from .errors import ResearchError


SUPPORTED_RASTER_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff"}
TARGET_WIDTH = 1050
TARGET_HEIGHT = 1485
PDF_DPI = 300


@dataclass(frozen=True, slots=True)
class PageInfo:
    number: int
    total: int
    source_size: tuple[int, int]


def inspect_page_count(path: Path) -> int:
    resolved = path.resolve()
    if not resolved.is_file():
        raise ResearchError("INPUT_INVALID", "input", f"Input file does not exist: {resolved}")
    suffix = resolved.suffix.lower()
    if suffix == ".pdf":
        try:
            import pypdfium2 as pdfium

            document = pdfium.PdfDocument(str(resolved))
            try:
                count = len(document)
            finally:
                document.close()
        except Exception as error:
            raise ResearchError("INPUT_INVALID", "input", f"Cannot inspect PDF: {error}") from error
    elif suffix in SUPPORTED_RASTER_SUFFIXES:
        try:
            with Image.open(resolved) as image:
                count = int(getattr(image, "n_frames", 1))
        except (OSError, ValueError) as error:
            raise ResearchError("INPUT_INVALID", "input", f"Cannot inspect image: {error}") from error
    else:
        raise ResearchError("INPUT_INVALID", "input", f"Unsupported input type: {suffix or '<none>'}")
    if count < 1:
        raise ResearchError("INPUT_INVALID", "input", "Input contains no pages")
    return count


def _flatten_to_rgb(image: Image.Image) -> Image.Image:
    oriented = ImageOps.exif_transpose(image)
    if oriented.mode in {"RGBA", "LA"} or "transparency" in oriented.info:
        rgba = oriented.convert("RGBA")
        white = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        return Image.alpha_composite(white, rgba).convert("RGB")
    return oriented.convert("RGB")


@contextmanager
def iter_document_pages(path: Path) -> Iterator[Iterator[tuple[PageInfo, Image.Image]]]:
    resolved = path.resolve()
    total = inspect_page_count(resolved)
    suffix = resolved.suffix.lower()

    if suffix == ".pdf":
        import pypdfium2 as pdfium

        document = pdfium.PdfDocument(str(resolved))

        def pdf_pages() -> Iterator[tuple[PageInfo, Image.Image]]:
            scale = PDF_DPI / 72.0
            for index in range(total):
                page = document[index]
                bitmap = page.render(scale=scale)
                try:
                    image = _flatten_to_rgb(bitmap.to_pil())
                finally:
                    bitmap.close()
                    page.close()
                yield PageInfo(index + 1, total, image.size), image

        try:
            yield pdf_pages()
        finally:
            document.close()
        return

    image_file = Image.open(resolved)

    def raster_pages() -> Iterator[tuple[PageInfo, Image.Image]]:
        for index in range(total):
            image_file.seek(index)
            page = _flatten_to_rgb(image_file.copy())
            yield PageInfo(index + 1, total, page.size), page

    try:
        yield raster_pages()
    finally:
        image_file.close()


def normalize_page(image: Image.Image) -> Image.Image:
    rgb = _flatten_to_rgb(image)
    if rgb.width < 1 or rgb.height < 1:
        raise ResearchError("INPUT_INVALID", "preprocessing", "Page has invalid dimensions")
    new_height = max(1, round(rgb.height * TARGET_WIDTH / rgb.width))
    resized = rgb.resize((TARGET_WIDTH, new_height), Image.Resampling.BILINEAR)
    if new_height >= TARGET_HEIGHT:
        normalized = resized.crop((0, 0, TARGET_WIDTH, TARGET_HEIGHT))
    else:
        normalized = Image.new("RGB", (TARGET_WIDTH, TARGET_HEIGHT), "white")
        normalized.paste(resized, (0, 0))
    if normalized.size != (TARGET_WIDTH, TARGET_HEIGHT):
        raise ResearchError("PREPROCESSING_FAILED", "preprocessing", "Unexpected model input size")
    return normalized

