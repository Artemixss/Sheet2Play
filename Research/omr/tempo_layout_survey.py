#!/usr/bin/env python3
"""On how many library pages does the shipped tempo reader find no staves?

Phase 3 of the per-song tempo plan. The reader finds staves in pixels darker than 128 (out of
255). Some PDFs draw thin, light grey staff lines that never reach that, and then the reader
sees no system and reads no mark. This counts, per library PDF, the pages where the shipped
layout finds no system, and whether it finds them once pixels darker than 200 count as ink.
No OCR runs.

    python tempo_layout_survey.py --output DIR

Writes `DIR/survey.json` (counts only) and `DIR/library/survey.json` (song names; local only).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "Bridge"))
import tempo_marks  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    songs = Path(os.environ["LOCALAPPDATA"]) / "Sheet2Play" / "songs" / "pdf"
    rows = []
    for pdf in sorted(songs.glob("*.pdf")):
        pages = tempo_marks.page_count(pdf)
        empty, recovered = 0, 0
        for page in range(pages):
            gray = tempo_marks.render(pdf, page)
            if tempo_marks.layout(gray):
                continue
            empty += 1
            recovered += bool(tempo_marks.layout((gray >= 200).astype("uint8") * 255))
        rows.append({"song": pdf.stem, "pages": pages, "pages_without_staves": empty,
                     "found_at_200": recovered})
        print(json.dumps({"pages": pages, "pages_without_staves": empty, "found_at_200": recovered}), flush=True)
    (args.output / "library").mkdir(parents=True, exist_ok=True)
    (args.output / "library" / "survey.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n",
                                                         encoding="utf-8")
    summary = {
        "reader_sha256": tempo_marks.sha256(HERE.parents[1] / "Bridge" / "tempo_marks.py"),
        "pdfs": len(rows), "pages": sum(row["pages"] for row in rows),
        "pdfs_with_a_page_without_staves": sum(row["pages_without_staves"] > 0 for row in rows),
        "pdfs_without_any_staves": sum(row["pages_without_staves"] == row["pages"] for row in rows),
        "pages_without_staves": sum(row["pages_without_staves"] for row in rows),
        "of_those_found_at_200": sum(row["found_at_200"] for row in rows),
    }
    (args.output / "survey.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
