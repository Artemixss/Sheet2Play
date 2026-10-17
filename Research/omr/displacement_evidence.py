#!/usr/bin/env python3
"""Pull the evidence for displacement Phase 2 examples out of the Phase 1 captures.

The 426 engine runs HOMR as a subprocess, so the capture log holds, per page, the decoded
TrOmr tokens ("Writing XML [[...]]"), the measures HOMR's `_fix_over_eager_tuplets` stripped of
tuplets ("Removing tuplets from measure #"), and the measures `_plan_voice_repairs` re-timed.
The 465 engine runs in-process and logs none of these, so its evidence is the page MusicXML
and the system crops.

    python displacement_evidence.py index            # writes data/displacement-ruler/evidence/426-log.json
    python displacement_evidence.py show ID ENGINE PAGE MEASURE [STAFF]
    python displacement_evidence.py label ID MEASURE STAFF
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RULER = HERE / "data/displacement-ruler"
LOG = HERE / "reports/displacement/phase1/jobs/capture-all-1/worker.log"
SMOKE_LOGS = [HERE / "reports/displacement/phase1/jobs/capture-smoke/worker.log",
              HERE / "reports/displacement/phase1/jobs/capture-smoke-nocap/worker.log"]
INDEX = RULER / "evidence/426-log.json"
PAGE = re.compile(r"captures[\\/]homr[\\/](\d+)[\\/]pages[\\/]page-(\d+)\.png")


def build_index() -> dict[str, dict[str, dict[str, object]]]:
    """Per 426 score and page: tokens split into systems and measures, stripped and re-timed measures."""
    index: dict[str, dict[str, dict[str, object]]] = {}
    for log in [LOG, *SMOKE_LOGS]:
        if not log.is_file():
            continue
        current: dict[str, object] | None = None
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("Processing ") and (match := PAGE.search(line)):
                current = {"stripped": [], "retimed": [], "error": None, "systems": []}
                index.setdefault(match.group(1), {})[str(int(match.group(2)))] = current
            elif current is None:
                continue
            elif line.startswith("Removing tuplets from measure #"):
                current["stripped"].append(int(line.rsplit("#", 1)[1]))
            elif line.startswith("Re-timed voices of measure #"):
                number, expected = re.match(r"Re-timed voices of measure # (\d+) to close on (\S+)", line).groups()
                current["retimed"].append([int(number), expected])
            elif line.startswith("An error occurred while processing"):
                current["error"] = line.rsplit(":", 1)[1].strip() or "(empty message)"
            elif line.startswith("Writing XML [[") and line.endswith("]]"):
                tokens = [token.strip() for token in line[len("Writing XML [["):-2].split(", ")]
                systems, system, measure = [], [], []
                for token in tokens:
                    if token.startswith("newline"):
                        if measure:
                            system.append(measure)
                        systems.append(system)
                        system, measure = [], []
                    elif token.startswith("barline") or token.startswith("repeat"):
                        measure.append(token)
                        system.append(measure)
                        measure = []
                    else:
                        measure.append(token)
                if measure:
                    system.append(measure)
                if system:
                    systems.append(system)
                current["systems"] = systems
    return index


def show(score: str, engine: str, page: int, measure: int, staff: int | None) -> None:
    """Print one predicted page measure: its MusicXML, and for 426 its tokens and log lines."""
    folder = RULER / "captures" / engine / score / "pages"
    text = (folder / f"page-{page:04d}.musicxml").read_text(encoding="utf-8")
    measures = re.findall(r'<measure number="(\d+)"[^>]*>(.*?)</measure>', text, re.S)
    number, body = measures[measure - 1]
    notes = re.findall(r"<note>(.*?)</note>", body, re.S)
    rows = []
    for note in notes:
        if staff is not None and f"<staff>{staff + 1}</staff>" not in note:
            continue
        pitch = re.search(r"<step>(\w)</step><octave>(\d)</octave>(?:<alter>(-?\d)</alter>)?", note)
        kind = "rest" if "<rest" in note else (pitch.group(1) + {"1": "#", "-1": "b"}.get(pitch.group(3) or "", "") + pitch.group(2))
        duration = re.search(r"<duration>(\d+)", note)
        voice = re.search(r"<voice>(\d+)", note)
        marks = ("(t)" if "<time-modification" in note else "") + ("(g)" if "<grace" in note else "")
        rows.append(f"{'+' if '<chord' in note else ' '}{kind}:{duration.group(1) if duration else 0}{marks}"
                    f"v{voice.group(1) if voice else '?'}")
    divisions = re.search(r"<divisions>(\d+)</divisions>", text).group(1)
    times = re.findall(r"<time><beats>(\d+)</beats><beat-type>(\d+)</beat-type>", text)
    print(f"{engine} {score} page {page} measure {measure} (xml number {number}), divisions {divisions}/quarter, "
          f"time signatures on page {sorted(set(times))}")
    print("  " + " ".join(rows))
    if engine == "homr":
        entry = json.loads(INDEX.read_text())[score][str(page)]
        print(f"  stripped tuplets in page measures {entry['stripped']}; re-timed {entry['retimed']}; error {entry['error']}")
        flat = [measure_tokens for system in entry["systems"] for measure_tokens in system]
        if measure - 1 < len(flat):
            print("  tokens: " + ", ".join(flat[measure - 1]))


def show_label(score: str, number: str, staff: int) -> None:
    """Print one label measure as written: pitch, duration in quarters, tuplet and grace marks."""
    from music21 import converter, stream

    part = converter.parse(RULER / score / "label.musicxml").parts[staff]
    measure = next(m for m in part.getElementsByClass(stream.Measure) if str(m.number) == number)
    signature = measure.getContextByClass("TimeSignature")
    rows = []
    for element in measure.recurse().notesAndRests:
        name = "rest" if element.isRest else "+".join(pitch.nameWithOctave for pitch in element.pitches)
        tuplet = "".join(f"({t.numberNotesActual}:{t.numberNotesNormal})" for t in element.duration.tuplets)
        grace = "(g)" if element.duration.isGrace else ""
        voice = element.getContextByClass(stream.Voice)
        rows.append(f"{name}:{element.duration.quarterLength}{tuplet}{grace}@{element.offset}v{voice.id if voice else 1}")
    print(f"label {score} staff {staff} measure {number}: {signature.ratioString if signature else None}, "
          f"length {measure.highestTime}")
    print("  " + " ".join(rows))


def crop(score: str, page: int, measures: list[int], out: Path) -> None:
    """Cut 465 page measures out of the rendered PDF page, from the imgpos HOMR writes per note.

    The app renders pages at 300 dpi (`render_pdf.py`), the frame imgpos is in. The crop spans the
    measures' notes with a margin, and the full height of their system.
    """
    import fitz

    text = (RULER / "captures/homr465" / score / "pages" / f"page-{page:04d}.musicxml").read_text(encoding="utf-8")
    bodies = re.findall(r'<measure number="\d+"[^>]*>(.*?)</measure>', text, re.S)
    points = [(int(x), int(y)) for index in measures
              for x, y in re.findall(r"imgpos: (\d+), (\d+)", bodies[index - 1])]
    if not points:
        raise SystemExit(f"no imgpos in page {page} measures {measures}")
    scale = 300 / 72
    xs, ys = [x for x, _ in points], [y for _, y in points]
    clip = fitz.Rect((min(xs) - 60) / scale, (min(ys) - 140) / scale, (max(xs) + 60) / scale, (max(ys) + 140) / scale)
    document = fitz.open(RULER / score / "score.pdf")
    pixmap = document[page - 1].get_pixmap(matrix=fitz.Matrix(scale / 2, scale / 2), clip=clip)
    out.parent.mkdir(parents=True, exist_ok=True)
    pixmap.save(out)
    print(f"wrote {out} ({pixmap.width}x{pixmap.height}, 150 dpi)")


def top(mechanism: str, engine: str, count: int) -> None:
    """The largest within-page events of one mechanism, for picking examples."""
    data = json.loads((HERE / "reports/displacement/phase2/attribution.json").read_text())
    events = [event for row in data["rows"].values() if row[engine]["status"] == "ok"
              for event in row[engine]["events"] if event["mechanism"] == mechanism]
    for event in sorted(events, key=lambda event: -event["abs_beats"])[:count]:
        print(f"{event['id']} staff {event['staff']} page {event['page']} measure {event['page_measure']} "
              f"label m{event['label_measure']}: {event['beats']} beats (decoded {event['pred_advance']}, "
              f"true {event['true_advance']}, notes {event['pred_notes']}/{event['true_notes']}, "
              f"voices {event['pred_voices']}/{event['true_voices']}, tuplets {event['pred_tuplets']}/{event['true_tuplets']}, "
              f"similarity {event['similarity']})")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("index")
    view = sub.add_parser("show")
    view.add_argument("score")
    view.add_argument("engine", choices=("homr465", "homr"))
    view.add_argument("page", type=int)
    view.add_argument("measure", type=int)
    view.add_argument("staff", type=int, nargs="?")
    label = sub.add_parser("label")
    label.add_argument("score")
    label.add_argument("measure")
    label.add_argument("staff", type=int)
    cut = sub.add_parser("crop")
    cut.add_argument("score")
    cut.add_argument("page", type=int)
    cut.add_argument("measures", type=int, nargs="+")
    cut.add_argument("--out", type=Path, required=True)
    largest = sub.add_parser("top")
    largest.add_argument("mechanism")
    largest.add_argument("engine", choices=("homr465", "homr"))
    largest.add_argument("--count", type=int, default=8)
    args = parser.parse_args()
    if args.command == "crop":
        crop(args.score, args.page, args.measures, args.out)
    elif args.command == "top":
        top(args.mechanism, args.engine, args.count)
    elif args.command == "label":
        show_label(args.score, args.measure, args.staff)
    elif args.command == "index":
        index = build_index()
        INDEX.parent.mkdir(parents=True, exist_ok=True)
        INDEX.write_text(json.dumps(index) + "\n", encoding="utf-8")
        print(f"{sum(len(pages) for pages in index.values())} pages from {len(index)} scores")
    else:
        show(args.score, args.engine, args.page, args.measure, args.staff)
    return 0


if __name__ == "__main__":
    sys.exit(main())
