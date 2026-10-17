#!/usr/bin/env python3
"""Build the displacement ruler: piano-only Lieder scores engraved with exact labels.

Phase 1 of the displacement plan (plans/MAIN_PLAN.md, `2026-10-17-displacement-correction`).
Displacement - one measure's error shifting everything after it - only shows on whole
multi-page scores, and only an exact label can price it. The library's MuseScore MIDI
references cannot. The OpenScore Lieder corpus is CC0 and local, and each song carries
a two-staff piano part. Strip the voice, let MuseScore engrave the piano part afresh,
and the engraved MusicXML is the truth for the PDF it was engraved into.

Three steps, each writing one file the next step reads:

    python displacement_ruler.py scan       # parse every .mscx, no MuseScore
    python displacement_ruler.py engrave    # MuseScore: full XML -> piano XML -> PDF + label
    python displacement_ruler.py freeze     # pick the ruler, split dev/test, hash everything

The label and PDF come out of one MuseScore job, so they are two exports of the same
in-memory score. `build_dataset.py` is not used end to end because even its clean variant
recompresses pages as JPEG at a random quality, while the library holds born-digital PDFs.
Its MuseScore helpers are reused.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import subprocess
import sys
import xml.etree.ElementTree as ElementTree
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Sequence

HERE = Path(__file__).resolve().parent
LIEDER = HERE / "data/openscore/lieder"
REVISION = "6b2dc542ce2e8aa4b78c8ee62103b210efc07015"
SOURCE = LIEDER / "source" / f"Lieder-{REVISION}"
OLIMPIC = HERE / "data/olimpic/olimpic-1.0-scanned"
OUT = HERE / "data/displacement-ruler"
REPORT = HERE / "reports/displacement/phase1"

PIANO_NAME = re.compile(r"piano|pianoforte|klavier|clavier", re.IGNORECASE)
VOCAL_ID = re.compile(r"voice|vocal|soprano|mezzo|alto|contralto|tenor|baritone|^bass$|choir",
                      re.IGNORECASE)
# Length bins by note count, not pages. Engraved Lieder piano parts run 300-900 notes a page
# against the library's median 286 (465's own output), so equal music fills fewer pages here.
# Library multi-page scores split 39% / 28% / 33% across these bins (2026-10-17, n=46).
NOTE_BINS = {"short": (650, 1000), "medium": (1000, 2000), "long": (2000, 10**6)}
RULER_TARGET = {"short": 20, "medium": 24, "long": 36}
ENGRAVE_POOL = {"short": 60, "medium": 60, "long": 10**6}
COMPOSER_CAP = 5
SEED = 20261017


def note_bin(notes: int) -> str | None:
    return next((name for name, (low, high) in NOTE_BINS.items() if low <= notes < high), None)


def favoured_order(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Most independent-voice writing first; ties broken by a seeded hash, not by file order."""
    def key(row: dict[str, Any]) -> tuple[float, str]:
        return (-row["multi_voice_fraction"], hashlib.sha256(f"{SEED}:{row['id']}".encode()).hexdigest())
    return sorted(rows, key=key)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def excluded_ids() -> dict[str, str]:
    """Scores this project has already measured on, so the test set never reuses them."""
    excluded: dict[str, str] = {}
    for split in ("dev", "test"):
        for line in (OLIMPIC / f"samples.{split}.txt").read_text().split():
            excluded[line.split("/")[1]] = f"olimpic-{split}"
    for label in (LIEDER / "labels").glob("lc*.musicxml"):
        excluded.setdefault(label.stem[2:], "existing-openscore-pair")
    return excluded


def piano_staff_profile(score: ElementTree.Element, staff_ids: Sequence[str]) -> dict[str, Any]:
    staves = {staff.get("id"): staff for staff in score.findall("Staff")}
    measures = [staves[staff_id].findall("Measure") for staff_id in staff_ids if staff_id in staves]
    if len(measures) != 2 or len(measures[0]) != len(measures[1]) or not measures[0]:
        raise ValueError("piano staves missing or unequal")
    notes = multi_voice = tuplets = irregular = time_signatures = repeats = 0
    for top, bottom in zip(*measures):
        voiced = False
        for measure in (top, bottom):
            voices = [voice for voice in measure.findall("voice") if voice.find("Chord") is not None]
            voiced |= len(voices) > 1
            notes += len(measure.findall(".//Note"))
            tuplets += len(measure.findall(".//Tuplet"))
            time_signatures += len(measure.findall(".//TimeSig"))
        multi_voice += voiced
        irregular += top.get("len") is not None
        repeats += sum(top.find(tag) is not None for tag in ("startRepeat", "endRepeat"))
        repeats += len(top.findall(".//Volta")) + len(top.findall(".//Jump"))
    count = len(measures[0])
    return {"measures": count, "notes": notes, "notes_per_measure": round(notes / count, 2),
            "multi_voice_fraction": round(multi_voice / count, 3), "tuplets": tuplets,
            "irregular_measures": irregular, "time_signatures": time_signatures // 2,
            "repeat_marks": repeats}


def scan_score(path: Path) -> dict[str, Any]:
    score = ElementTree.parse(path).getroot().find("Score")
    if score is None:
        raise ValueError("no Score element")
    pianos, others = [], []
    for part in score.findall("Part"):
        instrument = part.find("Instrument")
        identifier = instrument.get("id", "") if instrument is not None else ""
        names = " ".join(filter(None, (part.findtext("trackName"), identifier,
                                       instrument.findtext("longName") if instrument is not None else "")))
        staves = [staff.get("id") for staff in part.findall("Staff")]
        if PIANO_NAME.search(names) and len(staves) == 2:
            pianos.append(staves)
        else:
            others.append(identifier or names)
    if len(pianos) != 1:
        raise ValueError(f"{len(pianos)} two-staff piano parts")
    non_vocal = [name for name in others if not VOCAL_ID.search(name)]
    if non_vocal:
        raise ValueError("non-vocal parts: " + ", ".join(sorted(set(non_vocal))))
    return {"vocal_parts": len(others), **piano_staff_profile(score, pianos[0])}


def scan(_: argparse.Namespace) -> None:
    excluded = excluded_ids()
    rows, rejected = [], Counter()
    for path in sorted((SOURCE / "scores").rglob("lc*.mscx")):
        identifier = path.stem[2:]
        relative = path.relative_to(SOURCE).as_posix()
        row = {"id": identifier, "source": relative, "composer": relative.split("/")[1]}
        if identifier in excluded:
            rejected[excluded[identifier]] += 1
            continue
        try:
            row.update(scan_score(path))
        except (ValueError, ElementTree.ParseError, KeyError) as error:
            rejected[str(error).split(":")[0]] += 1
            continue
        row["source_sha256"] = sha256(path)
        rows.append(row)
    write_json(REPORT / "scan.json", {"revision": REVISION, "excluded_ids": excluded,
                                      "rejected": dict(rejected), "candidates": rows})
    measures = sorted(row["measures"] for row in rows)
    print(json.dumps({"candidates": len(rows), "rejected": dict(rejected),
                      "measures_quartiles": [measures[len(measures) * q // 4] for q in (1, 2, 3)]}))


def strip_to_piano(full: Path, target: Path) -> int:
    """Keep only the piano part, and drop the voice-and-piano layout so MuseScore lays it out anew."""
    tree = ElementTree.parse(full)
    root = tree.getroot()
    part_list = root.find("part-list")
    pianos = []
    for score_part in part_list.findall("score-part"):
        names = " ".join(filter(None, [score_part.findtext("part-name"), score_part.findtext("part-abbreviation")]
                                + [element.text for element in score_part.iter("instrument-name")]))
        if PIANO_NAME.search(names):
            pianos.append(score_part.get("id"))
    if len(pianos) != 1:
        raise ValueError(f"{len(pianos)} piano parts in the MusicXML export")
    for element in list(part_list):
        if element.tag != "score-part" or element.get("id") != pianos[0]:
            part_list.remove(element)
    for part in root.findall("part"):
        if part.get("id") != pianos[0]:
            root.remove(part)
    piano = root.find("part")
    if piano.findtext("measure/attributes/staves") != "2":
        raise ValueError("piano part is not a two-staff grand staff")
    for measure in piano.findall("measure"):
        for layout in measure.findall("print"):
            measure.remove(layout)
    tree.write(target, encoding="UTF-8", xml_declaration=True)
    return len(piano.findall("measure"))


def pdf_pages(pdf: Path) -> int:
    counts = [int(value) for value in re.findall(rb"/Count\s+(\d+)", pdf.read_bytes())]
    if not counts:
        raise ValueError("PDF page tree not found")
    return max(counts)


def engrave_one(row: dict[str, Any], musescore: str, work: Path) -> dict[str, Any]:
    from build_dataset import run_musescore

    work.mkdir(parents=True, exist_ok=True)
    full, piano = work / "full.musicxml", work / "piano.musicxml"
    pdf, label = work / "score.pdf", work / "label.musicxml"
    run_musescore(musescore, SOURCE / row["source"], full, None)
    measures = strip_to_piano(full, piano)
    full.unlink()
    if measures != row["measures"]:
        raise ValueError(f"export has {measures} measures, source piano staff {row['measures']}")
    job = work / "job.json"
    job.write_text(json.dumps([{"in": str(piano), "out": [str(pdf), str(label)]}]), encoding="utf-8")
    completed = subprocess.run([musescore, "-j", str(job)], capture_output=True, text=True, timeout=600)
    job.unlink()
    if completed.returncode != 0 or not pdf.is_file() or not label.is_file():
        detail = (completed.stderr or completed.stdout or "").strip()[-300:]
        raise ValueError(f"MuseScore job exit {completed.returncode}: {detail}")
    label_measures = len(ElementTree.parse(label).getroot().findall("part/measure"))
    if label_measures != measures:
        raise ValueError(f"label has {label_measures} measures, piano export {measures}")
    return {"pages": pdf_pages(pdf), "piano_sha256": sha256(piano), "pdf_sha256": sha256(pdf),
            "label_sha256": sha256(label)}


def engrave(args: argparse.Namespace) -> None:
    from build_dataset import find_musescore

    musescore = find_musescore(None)
    scan_rows = {row["id"]: row for row in json.loads((REPORT / "scan.json").read_text())["candidates"]}
    record_path = REPORT / "engraved.json"
    record = json.loads(record_path.read_text()) if record_path.is_file() else {"musescore": musescore, "scores": {}}
    version = subprocess.run([musescore, "--version"], capture_output=True, text=True, timeout=120).stdout.strip()
    if record.setdefault("musescore_version", version) != version:
        raise ValueError("MuseScore version changed between engraving runs")
    ids = list(args.ids)
    if args.from_selection:
        ids += json.loads((REPORT / "engrave-selection.json").read_text())
    for identifier in ids:
        if identifier in record["scores"]:
            continue
        row = scan_rows[identifier]
        try:
            outcome = {"status": "ok", **engrave_one(row, musescore, OUT / identifier)}
        except (ValueError, RuntimeError, ElementTree.ParseError, subprocess.TimeoutExpired, OSError) as error:
            outcome = {"status": "failed", "error": str(error)[:400]}
        record["scores"][identifier] = outcome
        write_json(record_path, record)
        print(json.dumps({"id": identifier, "notes": row["notes"], "measures": row["measures"], **{
            key: outcome.get(key) for key in ("status", "pages", "error")}}), flush=True)


def select(_: argparse.Namespace) -> None:
    """Choose which candidates to engrave: every long one, and the most polyphonic of the rest."""
    candidates = json.loads((REPORT / "scan.json").read_text())["candidates"]
    chosen = []
    for name in NOTE_BINS:
        per_composer: Counter[str] = Counter()
        pool = [row for row in favoured_order(candidates) if note_bin(row["notes"]) == name]
        for row in pool:
            if len([r for r in chosen if note_bin(r["notes"]) == name]) >= ENGRAVE_POOL[name]:
                break
            if name != "long" and per_composer[row["composer"]] >= COMPOSER_CAP:
                continue
            per_composer[row["composer"]] += 1
            chosen.append(row)
    write_json(REPORT / "engrave-selection.json", [row["id"] for row in chosen])
    print(json.dumps(Counter(note_bin(row["notes"]) for row in chosen)))


def split_by_composer(rows: Sequence[dict[str, Any]]) -> dict[str, str]:
    """Composers never straddle dev and test, so tuning never sees a held-out composer's style."""
    by_composer: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_composer[row["composer"]].append(row)
    rng = random.Random(SEED)
    composers = sorted(by_composer)
    rng.shuffle(composers)
    composers.sort(key=lambda name: -len(by_composer[name]))
    sizes = {"dev": Counter(), "test": Counter()}
    split = {}
    for composer in composers:
        bins = Counter(row["bin"] for row in by_composer[composer])
        target = min(("dev", "test"), key=lambda side: (sum(sizes[side].values()),
                                                         sum(sizes[side][name] for name in bins)))
        sizes[target].update(bins)
        split.update({row["id"]: target for row in by_composer[composer]})
    return split


def freeze(_: argparse.Namespace) -> None:
    from diagnose_rhythm import ground_truth_notes

    if (REPORT / "manifest.json").exists():
        raise FileExistsError("The ruler manifest is frozen; a new ruler needs a new name")
    scan_rows = {row["id"]: row for row in json.loads((REPORT / "scan.json").read_text())["candidates"]}
    engraved = json.loads((REPORT / "engraved.json").read_text())
    order = json.loads((REPORT / "engrave-selection.json").read_text())
    picked, rejected = [], {}
    count = Counter()
    for identifier in order:
        row = {**scan_rows[identifier], **engraved["scores"].get(identifier, {"status": "not engraved"})}
        row["bin"] = note_bin(row["notes"])
        if count[row["bin"]] >= RULER_TARGET[row["bin"]]:
            continue
        if row["status"] != "ok" or row["pages"] < 2:
            rejected[identifier] = row.get("error") or f"{row.get('pages')} page(s)"
            continue
        work = OUT / identifier
        if any(sha256(work / name) != row[key] for name, key in (
                ("score.pdf", "pdf_sha256"), ("label.musicxml", "label_sha256"), ("piano.musicxml", "piano_sha256"))):
            raise ValueError(f"{identifier}: engraved files changed after engraving")
        try:
            truth, _ = ground_truth_notes(work / "label.musicxml", expand_repeats=True, skip_grace_notes=False)
        except Exception as error:  # the bridge normalizer raises its own error types
            rejected[identifier] = f"label does not normalize: {error}"[:300]
            continue
        row["label_notes"] = len(truth)
        row["label_span_quarters"] = float(max(note.onset + note.duration for note in truth))
        count[row["bin"]] += 1
        picked.append(row)
    split = split_by_composer(picked)
    items = []
    for row in picked:
        work = OUT / row["id"]
        items.append({key: row[key] for key in (
            "id", "composer", "source", "source_sha256", "bin", "pages", "measures", "notes", "label_notes",
            "label_span_quarters", "multi_voice_fraction", "tuplets", "time_signatures", "irregular_measures",
            "repeat_marks")} | {
            "split": split[row["id"]],
            "pdf": (work / "score.pdf").relative_to(HERE).as_posix(), "pdf_sha256": row["pdf_sha256"],
            "label": (work / "label.musicxml").relative_to(HERE).as_posix(), "label_sha256": row["label_sha256"],
            "piano_sha256": row["piano_sha256"]})
    manifest = {"plan": "2026-10-17-displacement-correction", "phase": 1, "corpus": "OpenScore Lieder",
                "revision": REVISION, "license": "CC0-1.0", "musescore_version": engraved["musescore_version"],
                "seed": SEED, "note_bins": NOTE_BINS, "targets": RULER_TARGET, "composer_cap": COMPOSER_CAP,
                "truth_flags": {"expand_repeats": True, "skip_grace_notes": False},
                "rejected": rejected, "items": items}
    write_json(REPORT / "manifest.json", manifest)
    summary = Counter((item["split"], item["bin"]) for item in items)
    print(json.dumps({"items": len(items), "rejected": len(rejected), "manifest_sha256": sha256(REPORT / "manifest.json"),
                      "by_split_bin": {f"{a}/{b}": n for (a, b), n in sorted(summary.items())},
                      "pages": dict(sorted(Counter(item["pages"] for item in items).items()))}))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("scan").set_defaults(handler=scan)
    engraving = commands.add_parser("engrave")
    engraving.add_argument("ids", nargs="*", help="Scan ids to engrave, in order; finished ids are skipped.")
    engraving.add_argument("--from-selection", action="store_true",
                           help="Append the ids in engrave-selection.json.")
    engraving.set_defaults(handler=engrave)
    commands.add_parser("select").set_defaults(handler=select)
    commands.add_parser("freeze").set_defaults(handler=freeze)
    args = parser.parse_args(argv)
    args.handler(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
