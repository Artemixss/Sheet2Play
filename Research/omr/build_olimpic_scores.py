#!/usr/bin/env python3
"""Rebuild whole multi-page scores out of OLiMPiC's single systems, with exact labels.

Every benchmark in this project measures **one staff system at a time**. `p1-s1.png` is page 1,
system 1 - about five bars. The user's library is complete pieces of one to thirteen pages, and
the displacement effect measured in `diagnose_library_drift.py` lives precisely in that gap: it
grows with the number of opportunities a score offers, and a five-bar crop offers almost none.
So the finding has never been tested on a whole score whose label is exact, only on whole scores
whose label is a MuseScore MIDI of possibly another edition.

OLiMPiC makes the test possible, because its per-system MusicXML carries **consecutive measure
numbers** - `p1-s1` holds measures 1 to 5, `p1-s2` holds 6 to 10. The systems of one score tile it
completely, with no gaps and no overlaps, so they can be put back together:

- the images stack, grouped by the page number already in each filename, into a multi-page PDF
  that looks like the page they were cut from;
- the MusicXML concatenates, measure list after measure list, into one exact score.

The result is what the library never had: a real multi-page piece whose ground truth is the music
in the image rather than a performance of it.

    python build_olimpic_scores.py --limit 20            # build and transcribe
    python diagnose_library_drift.py --source olimpic \\
        --manifest data/olimpic-scores/manifest.jsonl \\
        --predictions reports/diagnosis/predictions/composite

Dev partition by default, so the test-partition systems the canary is drawn from are left alone.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
import xml.etree.ElementTree as ElementTree
from collections import defaultdict
from pathlib import Path
from typing import Any, Sequence

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parent.parent
sys.path.insert(0, str(HERE / "src"))

from sheet2play_omr.engines import run_bridge_engine  # noqa: E402

OLIMPIC_ROOT = HERE / "data" / "olimpic" / "olimpic-1.0-scanned"
VENDOR_HOMR = HERE / "vendor" / "homr"
TIMEOUT_SECONDS = 1800

# Page geometry in pixels, at the scans' own resolution (systems are about 2500 x 670). homr
# rescales every detected staff to a canonical height, so these only have to look like a page -
# they do not have to match any particular DPI.
PAGE_MARGIN = 120
SYSTEM_GAP = 90

SYSTEM_NAME = re.compile(r"^p(\d+)-s(\d+)$")


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--root", type=Path, default=OLIMPIC_ROOT)
    parser.add_argument(
        "--partition",
        choices=("dev", "test"),
        default="dev",
        help="dev by default: the canary is drawn from test, and reusing it would entangle them.",
    )
    parser.add_argument("--limit", type=int, default=20, help="Number of scores (0 = all).")
    parser.add_argument("--out", type=Path, default=HERE / "data" / "olimpic-scores")
    parser.add_argument(
        "--predictions",
        type=Path,
        default=HERE / "reports" / "diagnosis" / "predictions" / "composite",
    )
    parser.add_argument("--rerun", action="store_true", help="Ignore cached payloads.")
    parser.add_argument(
        "--build-only", action="store_true", help="Assemble the scores without transcribing."
    )
    return parser.parse_args(argv)


def systems_by_score(root: Path, partition: str) -> dict[str, list[tuple[int, int, Path]]]:
    """Every system of every score in one partition, in reading order.

    The sort key is the page and system number parsed out of the filename, which is also what
    puts a score back into the order it was printed in.
    """
    listing = root / f"samples.{partition}.txt"
    scores: dict[str, list[tuple[int, int, Path]]] = defaultdict(list)
    for line in listing.read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if not value:
            continue
        parts = Path(value).parts
        if len(parts) != 3:
            raise ValueError(f"Unexpected sample path: {value}")
        match = SYSTEM_NAME.match(parts[2])
        if match is None:
            raise ValueError(f"Cannot read page/system from {value}")
        page, system = int(match.group(1)), int(match.group(2))
        scores[parts[1]].append((page, system, root / value))
    return {score: sorted(entries) for score, entries in scores.items()}


def compose_page(images: Sequence[Any]) -> Any:
    """Stack one page's systems on a white canvas, centred, with margins and gaps.

    Separate from the file handling so the layout can be asserted on directly: it is the part
    that decides whether the result looks like a page to homr's staff detector.
    """
    from PIL import Image

    width = max(image.width for image in images) + 2 * PAGE_MARGIN
    height = (
        sum(image.height for image in images) + SYSTEM_GAP * (len(images) - 1) + 2 * PAGE_MARGIN
    )
    canvas = Image.new("L", (width, height), color=255)
    cursor = PAGE_MARGIN
    for image in images:
        # Centred rather than left-aligned: systems of one page differ in width by a few percent,
        # and a ragged left edge is not what a printed page looks like.
        canvas.paste(image, ((width - image.width) // 2, cursor))
        cursor += image.height + SYSTEM_GAP
    return canvas


def build_pages(systems: Sequence[tuple[int, int, Path]], pdf_path: Path) -> int:
    """Stack the systems of each page onto a white page and write one multi-page PDF."""
    from PIL import Image

    by_page: dict[int, list[Path]] = defaultdict(list)
    for page, _system, path in systems:
        by_page[page].append(path.with_suffix(".png"))

    pages = []
    for page in sorted(by_page):
        images = [Image.open(path).convert("L") for path in by_page[page]]
        pages.append(compose_page(images).convert("RGB"))

    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pages[0].save(pdf_path, save_all=True, append_images=pages[1:])
    return len(pages)


def build_musicxml(systems: Sequence[tuple[int, int, Path]], xml_path: Path) -> int:
    """Concatenate the per-system MusicXML into one score.

    Sound because the measure numbers already run consecutively across systems: the parts tile
    the piece rather than each restarting at bar 1. Each system repeats the clef, key and time
    signature in its first measure, which is exactly what a real score does at a system break,
    so those are left in place.
    """
    trees = [ElementTree.parse(path.with_suffix(".musicxml")) for _page, _system, path in systems]
    combined = copy.deepcopy(trees[0])
    target = combined.getroot().find("part")
    if target is None:
        raise ValueError(f"No <part> in {systems[0][2]}")

    measures = len(target.findall("measure"))
    for tree in trees[1:]:
        source = tree.getroot().find("part")
        if source is None:
            raise ValueError("No <part> in a continuation system")
        for measure in source.findall("measure"):
            target.append(copy.deepcopy(measure))
            measures += 1

    xml_path.parent.mkdir(parents=True, exist_ok=True)
    combined.write(xml_path, encoding="utf-8", xml_declaration=True)
    return measures


def transcribe(pdf: Path, cache: Path, rerun: bool) -> dict[str, Any]:
    """Through bridge.py with the vendored clone in front, matching every other measurement here."""
    if cache.is_file() and not rerun:
        return json.loads(cache.read_text(encoding="utf-8"))

    result = run_bridge_engine(
        pdf,
        engine="homr",
        timeout_seconds=TIMEOUT_SECONDS,
        extra_env={"PYTHONPATH": str(VENDOR_HOMR)},
    )
    if result.ok:
        record: dict[str, Any] = {"ok": True, "seconds": result.seconds, "payload": result.payload}
    else:
        record = {"ok": False, "error": result.error_code, "seconds": result.seconds}
        if result.stderr_tail:
            record["stderr_tail"] = result.stderr_tail
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(record), encoding="utf-8")
    return record


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_arguments(argv)
    if not args.root.is_dir():
        print(f"OLiMPiC not found at {args.root}", file=sys.stderr)
        return 2

    scores = systems_by_score(args.root, args.partition)
    selected = sorted(scores)[: args.limit] if args.limit else sorted(scores)
    print(f"{len(selected)} {args.partition} scores of {len(scores)}\n")

    manifest: list[dict[str, Any]] = []
    for index, score_id in enumerate(selected, start=1):
        systems = scores[score_id]
        pdf = args.out / f"{score_id}.pdf"
        xml = args.out / f"{score_id}.musicxml"
        pages = build_pages(systems, pdf)
        measures = build_musicxml(systems, xml)
        entry = {
            "identifier": score_id,
            "image": str(pdf),
            "musicxml": str(xml),
            "pages": pages,
            "systems": len(systems),
            "measures": measures,
        }
        manifest.append(entry)
        print(
            f"[{index}/{len(selected)}] {score_id}: {len(systems)} systems -> "
            f"{pages} pages, {measures} measures",
            flush=True,
        )

        if not args.build_only:
            record = transcribe(pdf, args.predictions / f"{score_id}.json", args.rerun)
            state = (
                f"{len(record['payload']['notes'])} notes in {record['seconds']:.0f}s"
                if record.get("ok")
                else f"FAILED {record.get('error')}"
            )
            print(f"    {state}", flush=True)

    manifest_path = args.out / "manifest.jsonl"
    manifest_path.write_text(
        "\n".join(json.dumps(entry) for entry in manifest) + "\n", encoding="utf-8"
    )
    print(f"\nwrote {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
