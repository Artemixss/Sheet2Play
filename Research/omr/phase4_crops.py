"""Reviewed development-only vertical coverage correction in detector coordinates."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from phase4_validation import file_hash
from zeus_attribution_prepare import configure_cpu, save_json

HERE = Path(__file__).resolve().parent
OLD = HERE / "reports/zeus-attribution/phase3"
OUT = HERE / "reports/zeus-attribution/phase4"


def reviewed_dedup(boxes: list[tuple[int, int]], removals: dict[int, int]) -> list[tuple[int, int]]:
    for child, parent in removals.items():
        if child == parent or parent in removals or not 0 <= child < len(boxes) or not 0 <= parent < len(boxes):
            raise ValueError("Invalid reviewed duplicate mapping")
        if not boxes[parent][0] <= boxes[child][0] < boxes[child][1] <= boxes[parent][1]:
            raise ValueError("Reviewed duplicate is not contained in its parent")
    retained = [box for index, box in enumerate(boxes) if index not in removals]
    if any(a[1] > b[0] for a, b in zip(retained, retained[1:])):
        raise ValueError("Overlapping systems require an explicit image review")
    return retained


def expand_boxes(image: np.ndarray, boxes: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if image.ndim != 2 or not boxes:
        raise ValueError("Expected grayscale page and nonempty boxes")
    height = image.shape[0]
    if any(not 0 <= top < bottom <= height for top, bottom in boxes):
        raise ValueError("Crop is outside page")
    blank = np.all(image >= 245, axis=1)
    separators = []
    for a, b in zip(boxes, boxes[1:]):
        runs, start = [], None
        for y in range(a[1], b[0] + 1):
            if y < b[0] and blank[y]:
                if start is None:
                    start = y
            elif start is not None:
                runs.append((start, y))
                start = None
        safe = [run for run in runs if run[1] - run[0] >= 16]
        if not safe:
            raise ValueError("No whitespace separator between systems; manual review required")
        left, right = max(safe, key=lambda run: run[1] - run[0])
        separators.append((left + right) // 2)
    bounds = [0] + separators + [height]
    corrected = []
    for index, (top, bottom) in enumerate(boxes):
        low, high = bounds[index:index + 2]
        if not low <= top < bottom <= high:
            raise ValueError("Overlapping or out-of-order systems")
        starts = [y for y in range(max(low, top - 8), max(low, top - 128) - 1, -1)
                  if y >= low + 8 and np.all(blank[y - 8:y])]
        ends = [y for y in range(min(high, bottom + 8), min(high, bottom + 128) + 1)
                if y + 8 <= high and np.all(blank[y:y + 8])]
        if not starts or not ends:
            raise ValueError(f"No whitespace-safe expanded boundary for system {index + 1}: "
                             f"box={(top, bottom)}, limits={(low, high)}, starts={starts}, ends={ends}; manual review required")
        corrected.append((max(low, starts[0] - 8), min(high, ends[0] + 8)))
    return corrected


def prepare() -> None:
    manifest = json.loads((OLD / "experiment-manifest.json").read_text())
    rows, previews = [], []
    for item in manifest["items"]:
        crop_metadata = Path(item["crops"][0]["path"]).parent / "crop-manifest.json"
        metadata = json.loads(crop_metadata.read_text())
        page_path = crop_metadata.parent.parent / "detector-preprocessed.png"
        if file_hash(page_path) != metadata["detector_image"]["sha256"] or file_hash(Path(item["image"])) != item["image_sha256"]:
            raise ValueError(f"Input identity changed: {item['item_id']}")
        original = [(b["top"], b["bottom"]) for b in metadata["crops"]]
        removals = {1: 0} if item["item_id"] == "openscore-6211555-page-1" else {}
        retained = reviewed_dedup(original, removals)
        with Image.open(page_path) as page:
            page = page.convert("L")
            corrected = expand_boxes(np.asarray(page), retained)
            destination = OUT / "crops" / item["item_id"]
            destination.mkdir(parents=True, exist_ok=False)
            crops = []
            for index, (top, bottom) in enumerate(corrected, 1):
                path = destination / f"system-{index:04d}.png"
                crop = page.crop((0, top, page.width, bottom))
                crop.save(path)
                crops.append({"path": str(path), "sha256": file_hash(path), "box": [0, top, page.width, bottom]})
                width = 1200
                preview = crop.resize((width, max(1, round(crop.height * width / crop.width))))
                label = f"{item['item_id']} system {index}: {retained[index-1]} -> {(top, bottom)}"
                previews.append((label, preview))
        rows.append({**item, "crops": crops, "crop_policy": "research vertical whitespace expansion; full width unchanged",
            "old_boxes": original, "retained_boxes": retained,
            "removed_duplicate_indices_zero_based": removals,
            "detector_page": str(page_path), "detector_page_sha256": file_hash(page_path)})
    review = OUT / "crop-review"
    review.mkdir(exist_ok=False)
    for sheet_index, start in enumerate(range(0, len(previews), 4), 1):
        subset = previews[start:start + 4]
        sheet = Image.new("RGB", (1220, sum(i.height + 32 for _, i in subset)), "white")
        draw, y = ImageDraw.Draw(sheet), 0
        for label, preview in subset:
            draw.text((10, y + 4), label, fill="black")
            sheet.paste(preview, (10, y + 24))
            draw.rectangle((9, y + 23, 1210, y + 24 + preview.height), outline="red")
            y += preview.height + 32
        sheet.save(review / f"sheet-{sheet_index}.png")
    save_json(OUT / "crop-manifest.json", {"items": rows,
        "previous_manifest_sha256": file_hash(OLD / "experiment-manifest.json"),
        "source_sha256": file_hash(Path(__file__)), "systems": sum(len(i["crops"]) for i in rows),
        "pre_inference_review": "pending; no inference until every sheet is inspected",
        "scope": "15 fixed development inputs; no general detector or benchmark claim"})
    print(json.dumps({"items": len(rows), "systems": sum(len(i["crops"]) for i in rows)}), flush=True)


if __name__ == "__main__":
    configure_cpu()
    prepare()
