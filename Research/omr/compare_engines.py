"""Compare the Sheet Music Transformer against the current engine on real scores.

Answers the question that decides Phase 2: is a published pianoform model better
than HOMR on the scores this project actually receives?

The two engines are not directly comparable token for token - HOMR returns
MusicXML for a whole page, SMT returns bekern for one system - so this reports
coverage and structure per system rather than a single accuracy number. The point
is to see whether SMT produces plausible, complete transcriptions of these pages
at all, which is the precondition for spending effort on a proper metric.

Run:
    .venv/Scripts/python.exe compare_engines.py --pdf <file.pdf> --pages 1 --out report
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import cv2  # noqa: E402

import slice_systems  # noqa: E402
from smt_infer import GRANDSTAFF, SMTTranscriber, kern_stats  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True, help="Score to transcribe.")
    parser.add_argument("--pages", type=int, default=1, help="How many pages.")
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--out", default="smt_report", help="Output directory.")
    parser.add_argument("--model", default=GRANDSTAFF)
    parser.add_argument("--max-systems", type=int, default=0,
                        help="Stop after N systems (0 = all).")
    args = parser.parse_args()

    pdf = Path(args.pdf)
    out_dir = Path(args.out)
    (out_dir / "systems").mkdir(parents=True, exist_ok=True)

    print("score  : " + pdf.name)
    print("model  : " + args.model)
    transcriber = SMTTranscriber(args.model)
    print("device : " + transcriber.device)
    print("")

    records = []
    system_index = 0
    for page in range(args.pages):
        try:
            image = slice_systems.render_pdf_page(pdf, page, args.dpi)
        except Exception as error:  # page out of range or render failure
            print("page %d: %s" % (page + 1, error))
            break

        bands = slice_systems.find_systems(image)
        print("page %d: %d system(s)" % (page + 1, len(bands)))

        for top, bottom in bands:
            if args.max_systems and system_index >= args.max_systems:
                break
            system_index += 1
            top = max(0, top - 12)
            bottom = min(image.shape[0] - 1, bottom + 12)
            crop = image[top:bottom, :]

            crop_path = out_dir / "systems" / ("p%02d_s%02d.png" % (page + 1, system_index))
            cv2.imwrite(str(crop_path), crop)

            started = time.time()
            try:
                text = transcriber.transcribe(crop)
                error = None
            except Exception as exc:
                text, error = "", str(exc)[:120]
            elapsed = time.time() - started

            stats = kern_stats(text) if text else {}
            record = {
                "page": page + 1,
                "system": system_index,
                "crop": crop_path.name,
                "size": [int(crop.shape[1]), int(crop.shape[0])],
                "seconds": round(elapsed, 1),
                "error": error,
                **stats,
            }
            records.append(record)
            (out_dir / ("p%02d_s%02d.krn" % (page + 1, system_index))).write_text(
                text, encoding="utf-8")

            if error:
                print("   s%02d  FAILED  %s" % (system_index, error))
            else:
                print("   s%02d  %5.1fs  %2d spines  %3d notes  %2d bars  %s"
                      % (system_index, elapsed, stats["spines"], stats["notes"],
                         stats["barlines"],
                         "well-formed" if stats["well_formed"] else "MALFORMED"))

    (out_dir / "report.json").write_text(
        json.dumps(records, indent=2), encoding="utf-8")

    if records:
        ok = [r for r in records if not r.get("error") and r.get("well_formed")]
        total_notes = sum(r.get("notes", 0) for r in records)
        mean_time = sum(r["seconds"] for r in records) / len(records)
        print("")
        print("=== %d systems | %d well-formed | %d notes total | %.1fs mean ==="
              % (len(records), len(ok), total_notes, mean_time))
        print("Report: " + str(out_dir / "report.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
