"""Cut a score page into system images using a horizontal ink profile.

The Sheet Music Transformer is trained on single systems, so a full page has to be
sliced before it can be transcribed. Engraved scores are well separated vertically,
so summing dark pixels per row and splitting on the gaps is enough here; this avoids
depending on the homr staff detector, which lives in a different virtual environment.

Run:  .venv/Scripts/python.exe slice_systems.py <pdf-or-image> <out-dir> [--page N]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np


def render_pdf_page(pdf_path: Path, page_index: int, dpi: int) -> np.ndarray:
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(str(pdf_path))
    page = document[page_index]
    image = page.render(scale=dpi / 72.0).to_numpy()
    if image.ndim == 3 and image.shape[2] == 4:
        image = cv2.cvtColor(image, cv2.COLOR_RGBA2BGR)
    elif image.ndim == 3 and image.shape[2] == 3:
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    return image


def find_systems(image: np.ndarray, min_height_ratio: float = 0.03,
                 gap_ratio: float = 0.012) -> list[tuple[int, int]]:
    """Return (top, bottom) row ranges that contain a system."""
    grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    binary = (grey < 160).astype(np.uint8)
    profile = binary.sum(axis=1)

    height, width = binary.shape
    # A row belongs to a system when a meaningful fraction of it is inked.
    threshold = max(3.0, 0.010 * width)
    inked = profile > threshold

    min_gap = max(4, int(height * gap_ratio))
    min_height = max(12, int(height * min_height_ratio))

    bands: list[tuple[int, int]] = []
    start = None
    gap = 0
    for row in range(height):
        if inked[row]:
            if start is None:
                start = row
            gap = 0
        elif start is not None:
            gap += 1
            if gap >= min_gap:
                end = row - gap
                if end - start >= min_height:
                    bands.append((start, end))
                start = None
                gap = 0
    if start is not None and height - start >= min_height:
        bands.append((start, height - 1))
    return bands


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("out_dir")
    parser.add_argument("--page", type=int, default=0)
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--pad", type=int, default=12, help="rows of padding per side")
    args = parser.parse_args()

    source = Path(args.source)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if source.suffix.lower() == ".pdf":
        image = render_pdf_page(source, args.page, args.dpi)
    else:
        image = cv2.imread(str(source))
    if image is None:
        print("could not read " + str(source))
        return 2

    print("page      : %dx%d" % (image.shape[1], image.shape[0]))
    bands = find_systems(image)
    print("systems   : %d" % len(bands))

    height = image.shape[0]
    for index, (top, bottom) in enumerate(bands, start=1):
        top = max(0, top - args.pad)
        bottom = min(height - 1, bottom + args.pad)
        crop = image[top:bottom, :]
        name = out_dir / ("%s_p%d_s%02d.png" % (source.stem[:40].replace(" ", "_"),
                                                args.page + 1, index))
        cv2.imwrite(str(name), crop)
        print("   %-46s %dx%d" % (name.name, crop.shape[1], crop.shape[0]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
