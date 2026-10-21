#!/usr/bin/env python3
"""Read printed tempo marks from sheet-music PDFs, and score the reading against exact truth.

Phase 2 of the per-song tempo plan (plans/2026-10-19-song-tempo.md). Research only: nothing here
is shipped, and HOMR's pinned files and title policy are untouched.

Two candidates read a mark:

* ``ocr``: render each page at 300 DPI, as the bridge does, and run rapidocr (the OCR HOMR
  already ships) on the strip above each system. OCR reads words and the BPM after "=" but not
  the note glyph before it (a quarter comes out as "J"), so the beat unit is classified from the
  glyph's pixels: a filled or hollow head, a flag, a dot.
* ``text``: the PDF's own text layer, which MuseScore writes with the note as a SMuFL code
  point. Only some PDFs have one (14 of the user's 61 library PDFs), so it is a shortcut, not a
  reader on its own.

The bar is the mark's left edge against the barlines of its system. Staves, systems and barlines
come from the rendered page by projection: engraved pages have exact horizontal staff lines and
vertical barlines, so no model is needed for them.

    python tempo_read.py read  --split dev [--set truth|control] [--candidate ocr|text] --run DIR
    python tempo_read.py score --run DIR
    python tempo_read.py freeze --runs DIR ...      # pre-register the rule before any test split
    python tempo_read.py library --run DIR          # the user's PDF/MIDI pairs (private, local)

``read`` on a test split refuses to run unless ``freeze`` has recorded this file's hash.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from tempo_truth import (CHANGE_WORDS, OPENING_WORDS, SMUFL_DOT, SMUFL_METRONOME, SMUFL_NOTES, UNIT_NAMES,  # noqa: E402
                         label_truth)

REPORT = HERE / "reports/song-tempo/phase2"
TRUTH_MANIFEST = REPORT / "truth-manifest.json"
FREEZE = REPORT / "freeze.json"
TEST_SPLITS = ("test", "test-b")
DPI = 300
BPM_RANGE = (20, 300)
BPM_PATTERN = re.compile(r"[=＝]\s*(?:c\.|ca\.?|circa)?\s*(\d{2,3}(?:[.,]\d)?)")
LEXICON = sorted({word.lower() for word in OPENING_WORDS + CHANGE_WORDS} | {
    "allegro", "andante", "moderato", "adagio", "lento", "largo", "presto", "vivace", "grave", "maestoso",
    "allegretto", "andantino", "larghetto", "adagietto", "prestissimo", "vivo", "a tempo", "tempo i",
    "più mosso", "meno mosso", "mosso", "animato", "tranquillo", "tempo di", "rubato", "moderato"}, key=len,
    reverse=True)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


# --- Page layout ---------------------------------------------------------------------------

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


# --- Reading marks -------------------------------------------------------------------------

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


class OcrReader:
    """rapidocr, with each strip's result cached on disk by PDF, page, box and settings."""

    SETTINGS = {"Det.limit_type": "max", "Det.limit_side_len": 2400}
    CACHE = REPORT / "ocr-cache"

    def __init__(self) -> None:
        import logging
        from rapidocr import RapidOCR
        logging.getLogger("RapidOCR").setLevel(logging.WARNING)
        # The default scales a strip's short side up to 736 px, which blows a 300 px strip up 2.5
        # times; capping the long side instead reads the same text in half the time.
        self.engine = RapidOCR(params=self.SETTINGS)
        self.tag = hashlib.sha256(json.dumps(self.SETTINGS, sort_keys=True).encode()).hexdigest()[:12]

    def lines(self, image: np.ndarray, key: str | None = None) -> list[tuple[tuple[int, int, int, int], str, float]]:
        path = self.CACHE / f"{key}-{self.tag}.json" if key else None
        if path is not None and path.is_file():
            return [(tuple(box), text, score) for box, text, score in json.loads(path.read_text(encoding="utf-8"))]
        found = self._read(image)
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(found, ensure_ascii=False), encoding="utf-8")
        return found

    def _read(self, image: np.ndarray) -> list[tuple[tuple[int, int, int, int], str, float]]:
        import cv2
        result = self.engine(cv2.cvtColor(image, cv2.COLOR_GRAY2BGR))
        if result.boxes is None:
            return []
        found = []
        for box, text, score in zip(result.boxes, result.txts, result.scores):
            xs, ys = box[:, 0], box[:, 1]
            found.append(((int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())), str(text), float(score)))
        return found


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


def read_page_text(pdf: Path, gray: np.ndarray, page: int) -> tuple[list[Detection], list[System]]:
    import fitz
    systems = layout(gray)
    scale = DPI / 72
    detections = []
    with fitz.open(pdf) as document:
        for block in document[page].get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                text = "".join(span["text"] for span in line["spans"])
                embedded = SMUFL_METRONOME.search(text)
                word = lexicon_word(text)
                if not embedded and not word:
                    continue
                x0, y0, x1, y1 = (int(value * scale) for value in line["bbox"])
                index = system_below(systems, y1)
                if index is None:
                    continue
                detection = Detection(page, index, (x0, y0, x1, y1), text, "text", suggestion=word)
                if embedded:
                    beat_unit, dots = SMUFL_NOTES[embedded.group(1)], embedded.group(2).count(SMUFL_DOT)
                    detection.bpm = float(embedded.group(3))
                    detection.unit = UNIT_NAMES.get((beat_unit, dots), f"{beat_unit}+{dots}")
                    detection.unit_source = "smufl"
                    detection.words = text[:embedded.start()].strip() or None
                detections.append(detection)
    return detections, systems


def system_below(systems: list[System], y: float) -> int | None:
    for index, system in enumerate(systems):
        if y <= system.top + system.staves[0].space:
            return index
    return None


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


def read_pdf(pdf: Path, candidate: str, reader: OcrReader | None) -> tuple[list[Detection], dict[str, Any]]:
    detections: list[Detection] = []
    pages: list[list[System]] = []
    started = time.perf_counter()
    count = page_count(pdf)
    source = sha256(pdf)[:16]
    for page in range(count):
        gray = render(pdf, page)
        found, systems = (read_page_ocr(reader, gray, page, source) if candidate == "ocr"
                          else read_page_text(pdf, gray, page))
        detections.extend(found)
        pages.append(systems)
    place_bars(detections, pages)
    return detections, {"pages": count, "seconds": round(time.perf_counter() - started, 3),
                        "systems": [len(systems) for systems in pages],
                        "measures": [[system.measures for system in systems] for systems in pages]}


# --- Commands ------------------------------------------------------------------------------

def manifest_items(split: str) -> list[dict[str, Any]]:
    manifest = json.loads(TRUTH_MANIFEST.read_text(encoding="utf-8"))
    return [item for item in manifest["items"] if item["split"] == split]


def check_freeze(split: str) -> None:
    if split not in TEST_SPLITS:
        return
    if not FREEZE.is_file():
        raise SystemExit(f"{split} is a test split: freeze the rule on dev and dev-b first (tempo_read.py freeze).")
    frozen = json.loads(FREEZE.read_text(encoding="utf-8"))
    if frozen["tempo_read_sha256"] != sha256(Path(__file__)) or frozen["tempo_truth_sha256"] != sha256(HERE / "tempo_truth.py"):
        raise SystemExit("tempo_read.py or tempo_truth.py changed since the freeze; the test splits are scored once.")


def read(args: argparse.Namespace) -> None:
    check_freeze(args.split)
    import psutil
    run = Path(args.run)
    run.mkdir(parents=True, exist_ok=True)
    rows_path = run / "rows.jsonl"
    done = {json.loads(line)["id"] for line in rows_path.read_text(encoding="utf-8").splitlines()} if rows_path.is_file() else set()
    reader = OcrReader() if args.candidate == "ocr" else None
    process = psutil.Process()
    peak = process.memory_info().rss
    with rows_path.open("a", encoding="utf-8") as rows:
        for item in manifest_items(args.split):
            if item["id"] in done:
                continue
            pdf = HERE / (item["pdf"] if args.set == "truth" else item["control_pdf"])
            label = (HERE / "data/tempo-truth" / item["id"] / "label.musicxml" if args.set == "truth"
                     else HERE / item["control_label"])
            try:
                detections, stats = read_pdf(pdf, args.candidate, reader)
                error = None
            except Exception as failure:  # one bad score must not stop the run; it is recorded
                detections, stats, error = [], {}, f"{type(failure).__name__}: {failure}"
            peak = max(peak, process.memory_info().rss)
            truth = label_truth(label)
            rows.write(json.dumps({
                "id": item["id"], "split": item["split"], "set": args.set, "candidate": args.candidate,
                "error": error, **stats, "peak_rss_mib": round(peak / 2**20, 1),
                "truth_marks": truth["marks"],
                "truth_systems": [sum(1 for m in truth["measures"] if m["page"] == page and m["system_start"])
                                  for page in range(1 + truth["measures"][-1]["page"])],
                "truth_measures_per_system": system_lengths(truth["measures"]),
                "truth_page_first_measure": [next(m["index"] for m in truth["measures"] if m["page"] == page)
                                             for page in range(1 + truth["measures"][-1]["page"])],
                "detections": [detection.__dict__ for detection in detections],
            }, ensure_ascii=False) + "\n")
            rows.flush()
            print(json.dumps({"id": item["id"], "detections": len(detections), "error": error,
                              "seconds": stats.get("seconds")}), flush=True)
    write_json(run / "run.json", {"split": args.split, "set": args.set, "candidate": args.candidate,
                                  "tempo_read_sha256": sha256(Path(__file__)),
                                  "tempo_truth_sha256": sha256(HERE / "tempo_truth.py"),
                                  "truth_manifest_sha256": sha256(TRUTH_MANIFEST)})


def system_lengths(measures: list[dict[str, Any]]) -> list[list[int]]:
    pages: list[list[int]] = []
    for measure in measures:
        while len(pages) <= measure["page"]:
            pages.append([])
        if measure["system_start"] or not pages[measure["page"]]:
            pages[measure["page"]].append(0)
        pages[measure["page"]][-1] += 1
    return pages


def score_rows(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    totals: dict[str, float] = {key: 0 for key in (
        "scores", "pages", "truth_marks", "matched", "bpm_exact", "unit_exact", "bar_exact", "mid_marks",
        "mid_matched", "mid_bar_exact", "start_marks", "start_correct", "start_bpm_exact", "detections_with_bpm",
        "false_tempos", "word_marks", "word_suggested", "layout_pages_exact", "errors", "seconds",
        "page_bar_exact", "mid_page_bar_exact")}
    units: dict[str, list[int]] = {}
    failures: list[dict[str, Any]] = []
    peak = 0.0
    for row in rows:
        totals["scores"] += 1
        totals["pages"] += row.get("pages") or 0
        totals["seconds"] += row.get("seconds") or 0
        totals["errors"] += row["error"] is not None
        peak = max(peak, row.get("peak_rss_mib") or 0)
        if row.get("measures") == row["truth_measures_per_system"]:
            totals["layout_pages_exact"] += row.get("pages") or 0
        detections = [d for d in row["detections"] if d["bpm"] is not None]
        totals["detections_with_bpm"] += len(detections)
        used: set[int] = set()
        for mark in row["truth_marks"]:
            if mark["bpm"] is None:
                totals["word_marks"] += 1
                totals["word_suggested"] += any(d["suggestion"] and d["page"] == mark["page"] and d["system"] == mark["system"]
                                                for d in row["detections"])
                continue
            totals["truth_marks"] += 1
            start = mark["measure"] == 0
            totals["start_marks"] += start
            totals["mid_marks"] += not start
            candidates = [(index, d) for index, d in enumerate(detections)
                          if index not in used and d["page"] == mark["page"] and d["system"] == mark["system"]]
            if not candidates:
                failures.append({"id": row["id"], "mark": mark, "why": "missed"})
                continue
            index, found = min(candidates, key=lambda pair: abs((pair[1]["measure"] or 0) - mark["measure"]))
            used.add(index)
            totals["matched"] += 1
            bpm_ok = found["bpm"] == mark["bpm"]
            unit_ok = found["unit"] == mark["unit"]
            bar_ok = found["measure"] == mark["measure"]
            page_bar_ok = found["page_measure"] == mark["measure"] - row["truth_page_first_measure"][mark["page"]]
            totals["page_bar_exact"] += page_bar_ok
            totals["bpm_exact"] += bpm_ok
            totals["unit_exact"] += unit_ok
            totals["bar_exact"] += bar_ok
            units.setdefault(f"{mark['unit']}->{found['unit']}", [0])[0] += 1
            if start:
                totals["start_correct"] += bpm_ok and unit_ok
                totals["start_bpm_exact"] += bpm_ok
            else:
                totals["mid_matched"] += 1
                totals["mid_bar_exact"] += bar_ok
                totals["mid_page_bar_exact"] += page_bar_ok
            if not (bpm_ok and unit_ok and bar_ok):
                failures.append({"id": row["id"], "mark": mark, "found": {k: found[k] for k in (
                    "bpm", "unit", "unit_source", "measure", "text")}, "why": "wrong"})
        false = [d for index, d in enumerate(detections) if index not in used]
        totals["false_tempos"] += len(false)
        failures.extend({"id": row["id"], "found": {k: d[k] for k in ("page", "system", "bpm", "text")},
                         "why": "false_tempo"} for d in false)

    def ratio(numerator: str, denominator: str) -> float | None:
        return round(totals[numerator] / totals[denominator], 4) if totals[denominator] else None

    return {
        "counts": {key: (int(value) if key != "seconds" else round(value, 1)) for key, value in totals.items()},
        "mark_recall": ratio("matched", "truth_marks"),
        "mark_precision": round(totals["matched"] / totals["detections_with_bpm"], 4) if totals["detections_with_bpm"] else None,
        "bpm_exact_of_matched": ratio("bpm_exact", "matched"),
        "unit_exact_of_matched": ratio("unit_exact", "matched"),
        "bar_exact_of_matched": ratio("bar_exact", "matched"),
        "start_tempo_correct": ratio("start_correct", "start_marks"),
        "start_bpm_exact": ratio("start_bpm_exact", "start_marks"),
        "mid_bar_exact": ratio("mid_bar_exact", "mid_matched"),
        # Counted from the top of the mark's page, as the app would place it among HOMR's measures
        # for that page, so one wrong system elsewhere does not move it.
        "page_bar_exact_of_matched": ratio("page_bar_exact", "matched"),
        "mid_page_bar_exact": ratio("mid_page_bar_exact", "mid_matched"),
        "false_tempos_per_score": ratio("false_tempos", "scores"),
        "word_suggestion_recall": ratio("word_suggested", "word_marks"),
        "layout_exact_page_fraction": ratio("layout_pages_exact", "pages"),
        "seconds_per_page": ratio("seconds", "pages"),
        "peak_rss_mib": peak,
        "unit_confusion": {key: value[0] for key, value in sorted(units.items())},
        "failures": failures[:200],
    }


def score(args: argparse.Namespace) -> None:
    run = Path(args.run)
    rows = [json.loads(line) for line in (run / "rows.jsonl").read_text(encoding="utf-8").splitlines()]
    summary = {**json.loads((run / "run.json").read_text(encoding="utf-8")), **score_rows(rows)}
    write_json(run / "score.json", summary)
    print(json.dumps({key: value for key, value in summary.items() if key not in ("failures", "counts")}, ensure_ascii=False))


def freeze(args: argparse.Namespace) -> None:
    for run in args.runs:
        recorded = json.loads((Path(run) / "run.json").read_text(encoding="utf-8"))
        if recorded["split"] in TEST_SPLITS:
            raise SystemExit("A freeze is made from development runs only.")
        if recorded["tempo_read_sha256"] != sha256(Path(__file__)):
            raise SystemExit(f"{run} was read with another version of tempo_read.py; rerun it before freezing.")
    write_json(FREEZE, {
        "plan": "2026-10-19-song-tempo", "phase": 2, "frozen_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tempo_read_sha256": sha256(Path(__file__)), "tempo_truth_sha256": sha256(HERE / "tempo_truth.py"),
        "truth_manifest_sha256": sha256(TRUTH_MANIFEST), "development_runs": args.runs,
        "candidate": args.candidate, "rule": json.loads(args.rule)})
    print(FREEZE.read_text(encoding="utf-8"))


def verdict(args: argparse.Namespace) -> None:
    """The frozen rule applied to the test runs, pooled over test and test-b, with each split shown."""
    frozen = json.loads(FREEZE.read_text(encoding="utf-8"))
    rule = frozen["rule"]
    passes = {"=": lambda value, limit: value == limit, ">=": lambda value, limit: value >= limit,
              "<=": lambda value, limit: value <= limit}
    result: dict[str, Any] = {"freeze": frozen, "sets": {}, "checks": []}
    for name in ("truth", "control"):
        runs = [Path(run) for run in getattr(args, name)]
        rows = []
        for run in runs:
            recorded = json.loads((run / "run.json").read_text(encoding="utf-8"))
            if recorded["split"] not in TEST_SPLITS or recorded["set"] != name or recorded["candidate"] != frozen["candidate"]:
                raise SystemExit(f"{run} is not a {frozen['candidate']} {name} run of a test split.")
            if recorded["tempo_read_sha256"] != frozen["tempo_read_sha256"]:
                raise SystemExit(f"{run} was read with another version of tempo_read.py than the frozen one.")
            rows.append([json.loads(line) for line in (run / "rows.jsonl").read_text(encoding="utf-8").splitlines()])
        pooled = score_rows(row for split_rows in rows for row in split_rows)
        result["sets"][name] = {"pooled": {k: v for k, v in pooled.items() if k != "failures"},
                                "splits": {str(run): {k: v for k, v in score_rows(split_rows).items() if k != "failures"}
                                           for run, split_rows in zip(runs, rows)}}
        for metric, (operator, limit) in rule.get(name, {}).items():
            value = pooled["counts"][metric] if metric == "errors" else pooled[metric]
            result["checks"].append({"set": name, "metric": metric, "rule": f"{operator} {limit}", "value": value,
                                     "pass": value is not None and passes[operator](value, limit)})
    result["accepted"] = all(check["pass"] for check in result["checks"])
    write_json(Path(args.out), result)
    for check in result["checks"]:
        print(f"{'PASS' if check['pass'] else 'FAIL'}  {check['set']:8s} {check['metric']:24s} {check['value']}  ({check['rule']})")
    print("ACCEPTED" if result["accepted"] else "NOT ACCEPTED")


QUARTERS = {"quarter": 1.0, "dotted_quarter": 1.5, "half": 2.0, "dotted_half": 3.0, "eighth": 0.5}


def midi_tempos(path: Path) -> list[tuple[float, float]]:
    """(beat, quarter BPM) for each tempo change in a MIDI file, de-duplicated across tracks."""
    from music21 import midi
    document = midi.MidiFile()
    document.open(str(path))
    document.read()
    document.close()
    found: dict[float, float] = {}
    for track in document.tracks:
        ticks = 0
        for event in track.events:
            if event.isDeltaTime():
                ticks += event.time
            elif event.type == midi.MetaEvents.SET_TEMPO:
                found[ticks / document.ticksPerQuarterNote] = round(60e6 / int.from_bytes(event.data, "big"), 2)
    changes = []
    for beat, bpm in sorted(found.items()):
        if not changes or abs(changes[-1][1] - bpm) > 1e-6:
            changes.append((beat, bpm))
    return changes


def library(args: argparse.Namespace) -> None:
    """The user's library PDFs that have a MuseScore MIDI of the same name. Private: stays local."""
    import os
    songs = Path(os.environ["LOCALAPPDATA"]) / "Sheet2Play" / "songs"
    run = Path(args.run)
    run.mkdir(parents=True, exist_ok=True)
    reader = OcrReader()
    rows = []
    for midi_path in sorted((songs / "midi" / "custom").glob("*.mid")):
        pdf = songs / "pdf" / (midi_path.stem + ".pdf")
        if not pdf.is_file():
            continue
        reference = midi_tempos(midi_path)
        row: dict[str, Any] = {"song": midi_path.stem, "midi_tempos": reference}
        for candidate in ("ocr", "text"):
            try:
                detections, stats = read_pdf(pdf, candidate, reader if candidate == "ocr" else None)
            except Exception as failure:
                row[candidate] = {"error": f"{type(failure).__name__}: {failure}"}
                continue
            marks = [d for d in detections if d.bpm is not None]
            quarter = [round(d.bpm * QUARTERS.get(d.unit or "quarter", 1.0), 2) for d in marks]
            row[candidate] = {
                "seconds": stats["seconds"], "pages": stats["pages"],
                "marks": [{"page": d.page, "measure": d.measure, "bpm": d.bpm, "unit": d.unit, "text": d.text}
                          for d in marks],
                "start_matches": bool(marks) and bool(reference) and abs(quarter[0] - reference[0][1]) < 0.6,
                "values_found": sorted({bpm for _, bpm in reference} & set(quarter)),
                "values_missed": sorted({bpm for _, bpm in reference} - set(quarter)),
                "values_extra": sorted(set(quarter) - {bpm for _, bpm in reference}),
            }
        rows.append(row)
        print(json.dumps({"song": row["song"], "midi": [bpm for _, bpm in reference],
                          "ocr": [m["bpm"] for m in row["ocr"].get("marks", [])],
                          "ocr_units": [m["unit"] for m in row["ocr"].get("marks", [])]}, ensure_ascii=False), flush=True)
    write_json(run / "library.json", {"tempo_read_sha256": sha256(Path(__file__)), "rows": rows})
    # Counts only, without song names, are what may be quoted in the report.
    summary = {"songs": len(rows),
               "songs_with_midi_tempo": sum(bool(row["midi_tempos"]) for row in rows)}
    for candidate in ("ocr", "text"):
        results = [row[candidate] for row in rows if "marks" in row.get(candidate, {})]
        summary[candidate] = {
            "read": len(results),
            "start_matches": sum(result["start_matches"] for result in results),
            "with_any_mark": sum(bool(result["marks"]) for result in results),
            "values_found": sum(len(result["values_found"]) for result in results),
            "values_missed": sum(len(result["values_missed"]) for result in results),
            "values_extra": sum(len(result["values_extra"]) for result in results),
        }
    write_json(run / "summary.json", summary)
    print(json.dumps(summary))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    read_parser = commands.add_parser("read")
    read_parser.add_argument("--split", required=True, choices=("dev", "dev-b", "test", "test-b"))
    read_parser.add_argument("--set", default="truth", choices=("truth", "control"))
    read_parser.add_argument("--candidate", default="ocr", choices=("ocr", "text"))
    read_parser.add_argument("--run", required=True)
    read_parser.set_defaults(run_command=read)
    score_parser = commands.add_parser("score")
    score_parser.add_argument("--run", required=True)
    score_parser.set_defaults(run_command=score)
    freeze_parser = commands.add_parser("freeze")
    freeze_parser.add_argument("--runs", nargs="+", required=True)
    freeze_parser.add_argument("--candidate", required=True)
    freeze_parser.add_argument("--rule", required=True, help="JSON thresholds, pre-registered before the test splits")
    freeze_parser.set_defaults(run_command=freeze)
    verdict_parser = commands.add_parser("verdict")
    verdict_parser.add_argument("--truth", nargs="+", required=True)
    verdict_parser.add_argument("--control", nargs="+", required=True)
    verdict_parser.add_argument("--out", required=True)
    verdict_parser.set_defaults(run_command=verdict)
    library_parser = commands.add_parser("library")
    library_parser.add_argument("--run", required=True)
    library_parser.set_defaults(run_command=library)
    args = parser.parse_args(argv)
    args.run_command(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
