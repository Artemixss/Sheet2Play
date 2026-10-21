#!/usr/bin/env python3
"""Does the shipped `Bridge/tempo_marks.py` read what the frozen research reader read?

Phase 3 of the per-song tempo plan. Runs the shipped reader on the dev and dev-b scores (truth
and control) and on the library PDFs of the Phase 2 library check, and compares every mark with
the frozen reader's runs (`runs/dev/ocr-*` and `library/library.json`): page, system, measure,
BPM, beat unit and text. The test splits are not read again.

    python tempo_marks_parity.py --output DIR

Writes `DIR/parity.json` (counts only) and `DIR/library/` (song names; local only).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "Bridge"))
import tempo_marks  # noqa: E402

PHASE2 = HERE / "reports/song-tempo/phase2"
KEYS = ("page", "system", "page_measure", "bpm", "unit", "text", "words", "suggestion")


def key(mark: dict[str, Any]) -> tuple:
    return tuple(mark.get(name) for name in KEYS)


def compare(expected: list[dict[str, Any]], found: list[dict[str, Any]]) -> list[str]:
    want, got = sorted(map(key, expected), key=repr), sorted(map(key, found), key=repr)
    return [] if want == got else [f"expected {want}", f"found {got}"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = {item["id"]: item for item in json.loads((PHASE2 / "truth-manifest.json").read_text(encoding="utf-8"))["items"]}
    summary: dict[str, Any] = {"reader_sha256": tempo_marks.sha256(HERE.parents[1] / "Bridge" / "tempo_marks.py"),
                               "frozen_reader_sha256": tempo_marks.FROZEN_READER_SHA256, "sets": {}}
    for split in ("dev", "dev-b"):
        for kind in ("truth", "control"):
            run = PHASE2 / "runs/dev" / f"ocr-{split}-{kind}"
            if json.loads((run / "run.json").read_text(encoding="utf-8"))["tempo_read_sha256"] != tempo_marks.FROZEN_READER_SHA256:
                raise SystemExit(f"{run} was not read by the frozen reader")
            scores = marks = same = 0
            differences = []
            for line in (run / "rows.jsonl").read_text(encoding="utf-8").splitlines():
                row = json.loads(line)
                item = manifest[row["id"]]
                pdf = HERE / (item["pdf"] if kind == "truth" else item["control_pdf"])
                result = tempo_marks.read_pdf(pdf)
                scores += 1
                marks += len(row["detections"])
                problems = compare(row["detections"], result["marks"])
                pages_same = [page["measures"] for page in result["pages"]] == [sum(system) for system in row["measures"]]
                if problems or not pages_same:
                    differences.append({"id": row["id"], "marks": problems, "pages_same": pages_same})
                else:
                    same += 1
                print(json.dumps({"set": f"{split}-{kind}", "id": row["id"], "same": not problems and pages_same}), flush=True)
            summary["sets"][f"{split}-{kind}"] = {"scores": scores, "marks": marks, "identical_scores": same,
                                                  "differences": differences}

    library = json.loads((PHASE2 / "library/library.json").read_text(encoding="utf-8"))
    if library["tempo_read_sha256"] != tempo_marks.FROZEN_READER_SHA256:
        raise SystemExit("the library check was not read by the frozen reader")
    songs = Path(os.environ["LOCALAPPDATA"]) / "Sheet2Play" / "songs" / "pdf"
    rows, same = [], 0
    for row in library["rows"]:
        result = tempo_marks.read_pdf(songs / (row["song"] + ".pdf"))
        expected = [(m["page"], m["bpm"], m["unit"], m["text"]) for m in row["ocr"]["marks"]]
        found = [(m["page"], m["bpm"], m["unit"], m["text"]) for m in result["marks"] if m["bpm"] is not None]
        identical = sorted(expected, key=repr) == sorted(found, key=repr)
        same += identical
        rows.append({"song": row["song"], "identical": identical, "expected": expected, "found": found})
    (args.output / "library").mkdir(exist_ok=True)
    (args.output / "library" / "parity.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    summary["library"] = {"songs": len(rows), "identical_songs": same}
    summary["identical"] = (same == len(rows) and
                            all(not entry["differences"] for entry in summary["sets"].values()))
    (args.output / "parity.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"identical": summary["identical"], "library": summary["library"],
                      **{name: entry["identical_scores"] for name, entry in summary["sets"].items()}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
