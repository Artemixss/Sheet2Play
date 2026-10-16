"""Verify frozen first-page identity and exported notation layout, without inference."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save(path: Path, value: dict) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def margin_words(page, first: bool) -> list[dict]:
    return [word for word in page.extract_words()
            if word["text"].isdigit() and word["x0"] < 50
            and (130 if first else 10) < word["top"] < 760]


def layout_markers(first_page, second_page, expected: list[str]) -> tuple[list[str], list[str]]:
    first = margin_words(first_page, True)
    heights = Counter(round(word["height"], 1) for word in first if word["text"] in expected)
    if not heights:
        return [word["text"] for word in first], []
    # Some scores put page numbers in the same margin; use the score's actual label font.
    height = heights.most_common(1)[0][0]
    def select(words: list[dict]) -> list[str]:
        return [word["text"] for word in words if abs(word["height"] - height) < 0.15]
    return select(first), select(margin_words(second_page, False)) if second_page else []


def inspect(row: dict, output: Path, renderer: Path, reuse: Path | None = None) -> dict:
    import pdfplumber
    from PIL import Image, ImageChops
    for field in ("source", "pdf", "musicxml"):
        if digest(Path(row[field + "_path"])) != row[field + "_sha256"]:
            raise ValueError(f"Frozen {field} mismatch: {row['id']}")
    image = row["page_images"][0]
    if digest(Path(image["path"])) != image["sha256"]:
        raise ValueError(f"Frozen image mismatch: {row['id']}")
    item = output / row["id"]
    item.mkdir(parents=True, exist_ok=False)
    rendered = item / "pdf-page"
    if reuse is None:
        subprocess.run([str(renderer), "-f", "1", "-l", "1", "-png", "-r", "300",
                        row["pdf_path"], str(rendered)], check=True, timeout=60,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    pages = list(((reuse / row["id"]) if reuse else item).glob("pdf-page-*.png"))
    if len(pages) != 1:
        raise ValueError("Expected one rendered PDF page")
    with Image.open(pages[0]) as reproduced, Image.open(image["path"]) as frozen:
        pixel_match = (reproduced.size == frozen.size and
                       ImageChops.difference(reproduced.convert("RGB"), frozen.convert("RGB")).getbbox() is None)
    xml = ET.parse(row["musicxml_path"])
    ranges = []
    for part in xml.getroot().findall("part"):
        measures = part.findall("measure")
        stop = next((i for i, measure in enumerate(measures) if i and
                     any(p.get("new-page") == "yes" for p in measure.findall("print"))), len(measures))
        systems = [m.get("number") for i, m in enumerate(measures[:stop]) if i and
                   any(p.get("new-system") == "yes" for p in m.findall("print"))]
        ranges.append({"part": part.get("id"), "first_page_measure_count": stop,
                       "first_number": measures[0].get("number"),
                       "last_number": measures[stop - 1].get("number"),
                       "next_page_first_number": measures[stop].get("number") if stop < len(measures) else None,
                       "printed_system_numbers": systems})
        for measure in measures[stop:]:
            part.remove(measure)
    if not ranges:
        raise ValueError("No partwise notation")
    expected = ranges[0]
    with pdfplumber.open(row["pdf_path"]) as pdf:
        first, second = layout_markers(pdf.pages[0], pdf.pages[1] if len(pdf.pages) > 1 else None,
                                       expected["printed_system_numbers"])
    consistent = all((p["first_page_measure_count"], p["next_page_first_number"]) ==
                     (expected["first_page_measure_count"], expected["next_page_first_number"]) for p in ranges)
    layout_match = (expected["printed_system_numbers"] == first and
                    (expected["next_page_first_number"] is None or
                     bool(second) and second[0] == expected["next_page_first_number"]))
    eligible = pixel_match and consistent and layout_match
    bounded = item / "reference-first-page.musicxml"
    xml.write(bounded, encoding="utf-8", xml_declaration=True)
    return {"item_id": row["id"], "pixel_identity_verified": pixel_match,
            "rendered_pdf_page": str(pages[0].resolve()), "rendered_pdf_page_sha256": digest(pages[0]),
            "source_sha256": row["source_sha256"], "pdf_sha256": row["pdf_sha256"],
            "whole_reference_sha256": row["musicxml_sha256"], "image_sha256": image["sha256"],
            "parts": ranges, "pdf_page1_left_margin_numbers": first,
            "pdf_page2_left_margin_numbers": second, "export_layout_matches_pdf": layout_match,
            "range_verified": eligible, "bounded_reference": str(bounded.resolve()),
            "bounded_reference_sha256": digest(bounded),
            "numeric_accuracy_eligible": False,
            "limitations": ["Page identity/layout checks do not validate note semantics or tie clipping",
                            "Original MSCX pagination differs from exported PDF; not used as page oracle"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--renderer", type=Path, required=True)
    parser.add_argument("--reuse-render-root", type=Path)
    args = parser.parse_args()
    rows = [json.loads(line) for line in Path("Research/omr/reports/phase1/development-open.jsonl")
            .read_text(encoding="utf-8").splitlines() if line.strip()]
    results = [inspect(row, args.output / "pages", args.renderer, args.reuse_render_root) for row in rows]
    save(args.output / "page-correspondence.json", {"pages": results, "phase2_started": False})
    print(json.dumps({"pages": len(results), "range_verified": sum(r["range_verified"] for r in results)}))


if __name__ == "__main__":
    main()
