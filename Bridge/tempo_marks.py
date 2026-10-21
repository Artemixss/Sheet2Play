#!/usr/bin/env python3
"""Read the tempo marks printed in a sheet-music PDF ("♩ = 110"), for the app's TEMPO panel.

Phase 3 of `plans/2026-10-19-song-tempo.md`. HOMR reads no tempo marks, so a converted PDF plays at
120 unless the user sets a tempo. This reads the marks so the panel can offer them, each with Use
and Ignore; nothing is applied without the user.

The reading is the OCR reader of `Research/omr/tempo_read.py` as frozen in Phase 2
(`022d782858a2…`), which on the held-out test scores read the start tempo right on 97.9% of them,
found 96.3% of marks and invented none (`Research/omr/reports/song-tempo/phase2/REPORT.md`). The
layout, OCR strip, beat-unit and bar functions below are copied from it unchanged, so that
measurement holds; `Research/omr/tests/test_tempo_marks.py` checks they still match. The OCR
cache the research runs kept on disk is left out, and one thing is added: a page on which the
frozen layout finds no staff, as with light grey staff lines, is read again with lighter ink
counted (see `read_pdf`).

Not part of any recognition or interpretation key, and no pinned file imports it. The app runs it
once per source PDF, after a conversion or from the panel, and keeps the result by the PDF's hash.

    tempo_marks.py --output OUT.json SOURCE.pdf

OUT.json holds each mark's page, its measure counted from the top of that page, the BPM, the beat
unit and the text OCR read, and the identity the result was made under. Progress goes to stderr
as `SHEET2PLAY_TEMPO_PROGRESS:{"page": 1, "pages": 11}`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Sequence

import numpy as np

SCHEMA_VERSION = 1
PROGRESS_PREFIX = "SHEET2PLAY_TEMPO_PROGRESS:"
# The research reader this file copies, as frozen before the test splits were scored.
FROZEN_READER_SHA256 = "022d782858a298222d6d036ba44394d07280c60deb1967c475cc0e65cba49e77"

DPI = 300
# What counts as ink on a page where the frozen layout's 128 finds no staff (see read_pdf).
LIGHT_INK = 200
BPM_RANGE = (20, 300)
BPM_PATTERN = re.compile(r"[=＝]\s*(?:c\.|ca\.?|circa)?\s*(\d{2,3}(?:[.,]\d)?)")
# `tempo_truth.OPENING_WORDS` and `CHANGE_WORDS`, then the words `tempo_read.LEXICON` adds.
OPENING_WORDS = ["Allegro", "Andante", "Moderato", "Adagio", "Lento", "Allegretto", "Andantino", "Larghetto",
                 "Presto", "Vivace", "Con moto", "Maestoso", "Largo", "Allegro moderato", "Andante con moto",
                 "Tempo di valse", "Grave", "Allegro vivace"]
CHANGE_WORDS = ["Più mosso", "Meno mosso", "Poco più lento", "a tempo", "Tempo I", "Più animato", "Calmando",
                "Poco meno mosso", "Animato"]
LEXICON = sorted({word.lower() for word in OPENING_WORDS + CHANGE_WORDS} | {
    "allegro", "andante", "moderato", "adagio", "lento", "largo", "presto", "vivace", "grave", "maestoso",
    "allegretto", "andantino", "larghetto", "adagietto", "prestissimo", "vivo", "a tempo", "tempo i",
    "più mosso", "meno mosso", "mosso", "animato", "tranquillo", "tempo di", "rubato", "moderato"}, key=len,
    reverse=True)
# (MusicXML beat unit, dots) to the names the TEMPO panel knows, as `tempo_truth.UNIT_NAMES`.
UNIT_NAMES = {("quarter", 0): "quarter", ("quarter", 1): "dotted_quarter", ("half", 0): "half",
              ("half", 1): "dotted_half", ("eighth", 0): "eighth"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --- Copied unchanged from Research/omr/tempo_read.py ---------------------------------------

@dataclass
class Staff:
    lines: list[float]
    left: int
    right: int

    @property
    def top(self) -> float:
        return self.lines[0]

    @property
    def bottom(self) -> float:
        return self.lines[-1]

    @property
    def space(self) -> float:
        return (self.bottom - self.top) / 4


@dataclass
class System:
    staves: list[Staff]
    barlines: list[int] = field(default_factory=list)

    @property
    def top(self) -> float:
        return self.staves[0].top

    @property
    def bottom(self) -> float:
        return self.staves[-1].bottom

    @property
    def left(self) -> int:
        return min(staff.left for staff in self.staves)

    @property
    def right(self) -> int:
        return max(staff.right for staff in self.staves)

    @property
    def measures(self) -> int:
        return max(1, len(self.barlines))


def render(pdf: Path, page_index: int) -> np.ndarray:
    import fitz
    with fitz.open(pdf) as document:
        pixmap = document[page_index].get_pixmap(matrix=fitz.Matrix(DPI / 72, DPI / 72), colorspace=fitz.csGRAY,
                                                 alpha=False)
        return np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width).copy()


def page_count(pdf: Path) -> int:
    import fitz
    with fitz.open(pdf) as document:
        return document.page_count


def longest_run(row: np.ndarray) -> int:
    padded = np.concatenate(([0], row.astype(np.int8), [0]))
    edges = np.flatnonzero(np.diff(padded))
    return int((edges[1::2] - edges[::2]).max()) if edges.size else 0


def find_staves(dark: np.ndarray) -> list[Staff]:
    """Five evenly spaced long horizontal lines make a staff."""
    height, width = dark.shape
    # A staff line is one long run, not many short ones (the ledger lines of a run of high notes);
    # a short last system can be a tenth of the page wide.
    runs = {row: longest_run(dark[row]) for row in np.flatnonzero(dark.sum(axis=1) > 0.1 * width)}
    runs = {row: run for row, run in runs.items() if run > 0.1 * width}
    # Long beams pass that too, and lying next to a line they would merge with it and break the
    # five-line pattern. A line runs the length of its staff, so near it they are much shorter.
    window = max(20, height // 50)
    rows = [row for row, run in runs.items()
            if run >= 0.8 * max(other for near, other in runs.items() if abs(near - row) <= window)]
    lines: list[float] = []
    start = previous = None
    for row in rows:
        if start is None:
            start = previous = row
        elif row == previous + 1:
            previous = row
        else:
            lines.append((start + previous) / 2)
            start = previous = row
    if start is not None:
        lines.append((start + previous) / 2)
    staves: list[Staff] = []
    index = 0
    while index + 4 < len(lines):
        group = lines[index:index + 5]
        gaps = np.diff(group)
        if gaps.min() > 4 and gaps.max() < 1.25 * gaps.min():
            # Where the lines themselves start and end. A brace crosses some of them further left,
            # so the latest start of the five is the staff's own left edge.
            starts, ends = [], []
            for line in group:
                row = int(round(line))
                columns = np.flatnonzero(dark[row - 1:row + 2].any(axis=0))
                starts.append(int(columns.min()))
                ends.append(int(columns.max()))
            # Better still, the vertical line that opens the system, where there is one: the first
            # column near the lines' starts that fills the staff's whole height.
            coverage = dark[int(group[0]):int(round(group[-1])) + 1].mean(axis=0)
            space = (group[-1] - group[0]) / 4
            window = range(min(starts), min(dark.shape[1], int(max(starts) + 2 * space)))
            opening = next((column for column in window if coverage[column] > 0.95), max(starts))
            staves.append(Staff(list(group), int(opening), int(np.median(ends))))
            index += 5
        else:
            index += 1
    return staves


def group_systems(dark: np.ndarray, staves: list[Staff]) -> list[System]:
    """Staves joined by the system's left-hand line are one system."""
    systems: list[System] = []
    for staff in staves:
        if systems:
            above = systems[-1].staves[-1]
            band = dark[int(above.bottom):int(staff.top) + 1,
                        max(0, min(above.left, staff.left) - 3):max(above.left, staff.left) + 4]
            joined = band.size > 0 and band.mean(axis=0).max() > 0.9
            if joined:
                systems[-1].staves.append(staff)
                continue
        systems.append(System([staff]))
    for system in systems:
        system.barlines = find_barlines(dark, system)
    return systems


def find_barlines(dark: np.ndarray, system: System) -> list[int]:
    """
    Columns that fill every staff of the system from its top line to its bottom line, and every gap
    between staves that the system's barlines cross (a grand staff's run through the gap; a voice
    above a piano's do not). A gap counts as crossed when any staff-filling column crosses it,
    since a stem never fills a whole gap; then stems lined up in both staves are not barlines.
    """
    covered = np.ones(dark.shape[1], dtype=bool)
    for staff in system.staves:
        band = dark[int(staff.top):int(round(staff.bottom)) + 1]
        covered &= band.mean(axis=0) > 0.92
    for upper, lower in zip(system.staves, system.staves[1:]):
        gap = dark[int(round(upper.bottom)) + 1:int(lower.top)]
        if gap.size == 0:
            continue
        # MuseScore breaks a barline where text such as "dim." crosses it, so a crossing barline
        # may fill only part of the gap; stems reaching in from both staves fill less. 0.7 is the best
        # of 0.5-0.85 on dev and dev-b (87% of pages, 96.7% of systems exact).
        coverage = gap.mean(axis=0)
        if (covered & (coverage > 0.9))[system.left + int(system.staves[0].space):].any():
            covered &= coverage > 0.7
    # A barline stops at the top and bottom lines; a stem always runs on past them to its notes.
    space = system.staves[0].space
    top, bottom = int(system.staves[0].top), int(round(system.staves[-1].bottom))
    reach = max(2, int(0.3 * space))
    outside = np.vstack([dark[max(0, top - 2 * reach):top - reach], dark[bottom + reach:bottom + 2 * reach]])
    if outside.size:
        covered &= outside.mean(axis=0) < 0.5
    columns = np.flatnonzero(covered)
    groups: list[list[int]] = []
    for column in columns:
        if groups and column - groups[-1][-1] <= max(3, int(system.staves[0].space)):
            groups[-1].append(column)
        else:
            groups.append([column])
    barlines = []
    for group in groups:
        # A thin line, or a double or final barline; a stem never fills two staves at once.
        if group[-1] - group[0] > 1.5 * space:
            continue
        x = group[-1]
        # The brace and the system's opening line; no barline comes before the clef, which alone
        # is wider than three spaces.
        if x - system.left < 3 * space:
            continue
        # A start-repeat right after the clef and key opens the system's first measure rather than
        # ending one; elsewhere a start-repeat does end the measure before it.
        if not barlines and x - system.left < 12 * space and repeat_dots_after(dark, system, x):
            continue
        barlines.append(int(x))
    return barlines


def repeat_dots_after(dark: np.ndarray, system: System, x: int) -> bool:
    """Repeat dots just right of a barline: ink in the second and third spaces of every staff."""
    for staff in system.staves:
        space = staff.space
        for middle in (staff.top + 1.5 * space, staff.top + 2.5 * space):
            spot = dark[int(middle - 0.25 * space):int(middle + 0.25 * space) + 1,
                        int(x + 0.3 * space):int(x + 1.5 * space) + 1]
            if spot.size == 0 or spot.mean() < 0.15:
                return False
    return True


def layout(gray: np.ndarray) -> list[System]:
    dark = gray < 128
    return group_systems(dark, find_staves(dark))


def lexicon_word(text: str) -> str | None:
    lowered = text.lower()
    return next((word for word in LEXICON if re.search(rf"(?<![a-zà-ü]){re.escape(word)}(?![a-zà-ü])", lowered)),
                None)


def parse_bpm(text: str) -> float | None:
    found = BPM_PATTERN.search(text)
    if not found:
        return None
    value = float(found.group(1).replace(",", "."))
    return value if BPM_RANGE[0] <= value <= BPM_RANGE[1] else None


def strip_region(systems: list[System], index: int, height: int) -> tuple[int, int, int, int]:
    """The band above a system where its tempo mark would be printed."""
    system = systems[index]
    space = system.staves[0].space
    top_limit = systems[index - 1].bottom + 2 * space if index > 0 else 0
    top = int(max(top_limit, system.top - 14 * space, 0))
    bottom = int(system.top + space)
    left = max(0, system.left - int(4 * space))
    right = min(system.right + int(2 * space), height * 10)
    return left, top, right, bottom


def classify_unit(dark: np.ndarray, box: tuple[int, int, int, int]) -> tuple[str | None, str]:
    """The beat unit from the note glyph left of "=": an enclosed head is a half, a flag an eighth."""
    import cv2

    left, top, right, bottom = box
    pad = max(4, (bottom - top) // 3)
    region = dark[max(0, top - pad):bottom + pad, max(0, left - pad):right + pad].astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(region, connectivity=8)
    parts = [tuple(stats[index][:5]) for index in range(1, count)]
    line_height = bottom - top
    # "=" is two flat bars, one above the other, with nearly the same left and right ends.
    bars = [part for part in parts if part[2] > 2.2 * part[3] and part[3] <= 0.2 * line_height and part[2] < line_height]
    equals = None
    for upper in bars:
        for lower in bars:
            if lower is upper:
                continue
            if abs(upper[0] - lower[0]) <= 3 and abs(upper[2] - lower[2]) <= 3 and 0 < lower[1] - upper[1] <= 0.5 * line_height:
                if equals is None or upper[0] < equals[0]:
                    equals = upper
    if equals is None:
        return None, "no_equals"
    eq_left = equals[0]
    before = [part for part in parts if part[0] + part[2] <= eq_left and part[0] + part[2] > eq_left - 2.2 * line_height]
    tall = [part for part in before if part[3] >= 0.55 * line_height]
    if not tall:
        return None, "no_glyph"
    note = max(tall, key=lambda part: part[0] + part[2])
    x, y, w, h, _ = note
    note_right = x + w
    # A dot is a small, roughly square blob beside the head. Specks of a barline or staff line
    # below the glyph also sit right of it, but are thin and lie below the head.
    dotted = any(part[3] <= 0.25 * line_height and part[2] <= 0.25 * line_height and part[4] >= 4
                 and max(part[2], part[3]) <= 2 * min(part[2], part[3])
                 and part[0] >= note_right - 1 and part[0] + part[2] <= eq_left
                 and part[1] >= y + 0.5 * h and part[1] + part[3] <= y + 1.1 * h
                 for part in before if part is not note)
    glyph = region[y:y + h, x:x + w]
    stem_x = int(np.argmax(glyph.sum(axis=0)))
    # A hollow head encloses background: flood the outside and count what the flood cannot reach.
    # The head's ink fraction is no test, since a half's outline is nearly as dark as a quarter.
    outside = np.pad(glyph, 1).astype(np.uint8)
    cv2.floodFill(outside, np.zeros((h + 4, w + 4), np.uint8), (0, 0), 1)
    hollow = (outside == 0).sum() >= 0.08 * w * (h - int(0.65 * h))
    flag = glyph[: int(0.45 * h), min(w, stem_x + 3):]
    flagged = flag.size > 0 and flag.mean() > 0.12
    if hollow:
        unit = "half"
    elif flagged:
        unit = "eighth"
    else:
        unit = "quarter"
    name = UNIT_NAMES.get({"half": ("half", 1 if dotted else 0), "quarter": ("quarter", 1 if dotted else 0),
                           "eighth": ("eighth", 1 if dotted else 0)}[unit], unit + ("+dot" if dotted else ""))
    return name, "glyph"


@dataclass
class Detection:
    page: int
    system: int
    box: tuple[int, int, int, int]
    text: str
    source: str
    bpm: float | None = None
    unit: str | None = None
    unit_source: str | None = None
    words: str | None = None
    suggestion: str | None = None
    page_measure: int | None = None
    measure: int | None = None


def read_page_ocr(reader: OcrReader, gray: np.ndarray, page: int, source: str | None = None
                  ) -> tuple[list[Detection], list[System]]:
    systems = layout(gray)
    dark = gray < 128
    detections = []
    for index, system in enumerate(systems):
        left, top, right, bottom = strip_region(systems, index, gray.shape[1])
        if bottom - top < 4 or right - left < 4:
            continue
        key = f"{source}-p{page}-{left}-{top}-{right}-{bottom}" if source else None
        for (x0, y0, x1, y1), text, _ in reader.lines(gray[top:bottom, left:right], key):
            box = (x0 + left, y0 + top, x1 + left, y1 + top)
            # Text whose bottom sits inside the staff is a note's lyric or fingering, not a mark above it.
            if box[3] > system.top + system.staves[0].space:
                continue
            bpm = parse_bpm(text)
            word = lexicon_word(text)
            if bpm is None and word is None:
                continue
            detection = Detection(page, index, box, text, "ocr", bpm=bpm, suggestion=word)
            if bpm is not None:
                detection.unit, detection.unit_source = classify_unit(dark, box)
                if detection.unit is None:
                    detection.unit, detection.unit_source = "quarter", f"fallback:{detection.unit_source}"
            detection.words = re.split(r"[(=]|\bJ\b", text)[0].strip() or None
            detections.append(detection)
    return detections, systems


def place_bars(detections: list[Detection], pages: list[list[System]]) -> None:
    """Each mark's measure: its left edge against the barlines of its system, counted through the score."""
    before_page = 0
    for page_index, systems in enumerate(pages):
        before_system = 0
        for system_index, system in enumerate(systems):
            for detection in detections:
                if detection.page != page_index or detection.system != system_index:
                    continue
                anchor = detection.box[0] + 0.5 * system.staves[0].space
                within = sum(1 for barline in system.barlines if barline <= anchor)
                within = min(within, system.measures - 1)
                detection.page_measure = before_system + within
                detection.measure = before_page + before_system + within
            before_system += system.measures
        before_page += before_system


# --- The shipped reader ---------------------------------------------------------------------

class OcrReader:
    """rapidocr, as the research reader runs it, without its on-disk cache."""

    SETTINGS = {"Det.limit_type": "max", "Det.limit_side_len": 2400}

    def __init__(self) -> None:
        import logging
        from rapidocr import RapidOCR
        logging.getLogger("RapidOCR").setLevel(logging.WARNING)
        self.engine = RapidOCR(params=self.SETTINGS)

    def lines(self, image: np.ndarray, key: str | None = None) -> list[tuple[tuple[int, int, int, int], str, float]]:
        import cv2
        result = self.engine(cv2.cvtColor(image, cv2.COLOR_GRAY2BGR))
        if result.boxes is None:
            return []
        found = []
        for box, text, score in zip(result.boxes, result.txts, result.scores):
            xs, ys = box[:, 0], box[:, 1]
            found.append(((int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())), str(text), float(score)))
        return found


def ocr_identity() -> dict[str, Any]:
    """The OCR engine, its settings and the hashes of the models it loads."""
    import rapidocr
    models = Path(rapidocr.__file__).parent / "models"
    return {
        "engine": "rapidocr",
        "version": getattr(rapidocr, "__version__", None) or _distribution_version("rapidocr"),
        "settings": OcrReader.SETTINGS,
        "models": {path.name: sha256(path) for path in sorted(models.glob("*.onnx"))},
    }


def _distribution_version(name: str) -> str | None:
    from importlib import metadata
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def read_pdf(pdf: Path, progress: Any = None) -> dict[str, Any]:
    """Every mark in the PDF, with the identity it was read under."""
    started = time.perf_counter()
    reader = OcrReader()
    count = page_count(pdf)
    detections: list[Detection] = []
    pages: list[list[System]] = []
    light_pages = []
    for page in range(count):
        gray = render(pdf, page)
        found, systems = read_page_ocr(reader, gray, page)
        if not systems:
            # Some PDFs draw thin, light grey staff lines that never get darker than the 128 the
            # frozen layout counts as ink, so it finds no staff and reads nothing. Such a page is
            # read again with everything darker than LIGHT_INK made black. No page of the
            # measured sets lacked staves, so this never changes a measured result; 27 pages of 3
            # library PDFs need it (Research/omr/reports/song-tempo/phase3/REPORT.md).
            found, systems = read_page_ocr(reader, np.where(gray < LIGHT_INK, 0, 255).astype(np.uint8), page)
            if systems:
                light_pages.append(page)
        detections.extend(found)
        pages.append(systems)
        if progress is not None:
            progress(page + 1, count)
    place_bars(detections, pages)
    marks = []
    for detection in detections:
        row = asdict(detection)
        row["box"] = list(row["box"])
        marks.append(row)
    return {
        "schema_version": SCHEMA_VERSION,
        "reader_sha256": sha256(Path(__file__)),
        "frozen_reader_sha256": FROZEN_READER_SHA256,
        "ocr": ocr_identity(),
        "dpi": DPI,
        "source_name": pdf.name,
        "source_sha256": sha256(pdf),
        "pages": [{"systems": len(systems), "measures": sum(system.measures for system in systems),
                   "light_ink": index in light_pages}
                  for index, systems in enumerate(pages)],
        "marks": marks,
        "seconds": round(time.perf_counter() - started, 3),
    }


def _report_progress(page: int, pages: int) -> None:
    sys.stderr.write(PROGRESS_PREFIX + json.dumps({"page": page, "pages": pages}) + "\n")
    sys.stderr.flush()


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read the tempo marks printed in a sheet-music PDF.")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("source", type=Path)
    args = parser.parse_args(arguments)
    if args.source.suffix.lower() != ".pdf" or not args.source.is_file():
        parser.error(f"{args.source} is not a PDF file")
    result = read_pdf(args.source, _report_progress)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(f".{args.output.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
