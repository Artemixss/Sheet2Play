#!/usr/bin/env python3
"""Build the tempo-truth set: the displacement ruler's scores with known tempo marks engraved in.

Phase 2 of the per-song tempo plan (plans/2026-10-19-song-tempo.md). The ruler's exact labels
hold almost no tempo marks (5 of 207), so they can show false detections but not whether a
printed mark is read. This takes each ruler item's piano MusicXML (the file MuseScore engraved
the ruler from), adds seeded metronome marks and tempo words, and engraves PDF and label in one
MuseScore job, as displacement_ruler.py did. Truth is read back from the exported label, not
from what was asked for, so it holds what MuseScore actually printed and where.

The frozen manifests are only read. Output goes to data/tempo-truth/<id>/ and
reports/song-tempo/phase2/truth-manifest.json.

    python tempo_truth.py build [--ids ID ...]   # engrave (resumable; one MuseScore job at a time)
    python tempo_truth.py freeze                 # hash everything into the truth manifest
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
from pathlib import Path
from typing import Any, Sequence

HERE = Path(__file__).resolve().parent
RULER = HERE / "data/displacement-ruler"
TRUTH = HERE / "data/tempo-truth"
REPORT = HERE / "reports/song-tempo/phase2"
SOURCE_MANIFESTS = {
    "phase1": HERE / "reports/displacement/phase1/manifest.json",    # dev, test
    "phase3b": HERE / "reports/displacement/phase3b/manifest.json",  # dev-b, test-b
}
SPLITS = ("dev", "dev-b", "test", "test-b")
SEED = 20261021
MUSESCORE_VERSION = "MuseScore4 4.6.5"

# Opening words, and words that change the tempo mid-score. Words never fix a BPM, so the
# reader may only suggest them; a words-only mark tests that it does not invent one.
OPENING_WORDS = ["Allegro", "Andante", "Moderato", "Adagio", "Lento", "Allegretto", "Andantino", "Larghetto",
                 "Presto", "Vivace", "Con moto", "Maestoso", "Largo", "Allegro moderato", "Andante con moto",
                 "Tempo di valse", "Grave", "Allegro vivace"]
CHANGE_WORDS = ["Più mosso", "Meno mosso", "Poco più lento", "a tempo", "Tempo I", "Più animato", "Calmando",
                "Poco meno mosso", "Animato"]
# (MusicXML beat unit, dots, BPM range) per unit the app's TEMPO panel offers.
UNITS = {
    "quarter": ("quarter", 0, (40, 200)),
    "dotted_quarter": ("quarter", 1, (40, 140)),
    "half": ("half", 0, (30, 110)),
    "dotted_half": ("half", 1, (30, 80)),
    "eighth": ("eighth", 0, (60, 220)),
}
UNIT_NAMES = {(beat_unit, dots): name for name, (beat_unit, dots, _) in UNITS.items()}
# SMuFL metronome glyphs, as MuseScore writes them into a tempo text it exports as words (it
# does so when words and a parenthesised metronome share one tempo text).
SMUFL_NOTES = {"": "whole", "": "half", "": "half", "": "quarter", "": "quarter",
               "": "eighth", "": "eighth"}
SMUFL_DOT = ""
SMUFL_METRONOME = re.compile(r"\(?\s*([-])\s*((?:\s*)*)=\s*(\d+(?:\.\d+)?)\s*\)?")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def source_items() -> list[dict[str, Any]]:
    items = []
    for name, path in SOURCE_MANIFESTS.items():
        manifest = json.loads(path.read_text(encoding="utf-8"))
        for item in manifest["items"]:
            if item["split"] in SPLITS:
                items.append({**item, "source_manifest": name})
    return sorted(items, key=lambda item: (SPLITS.index(item["split"]), item["id"]))


# --- Reading a score -----------------------------------------------------------------------

def measure_meters(part: ElementTree.Element) -> list[tuple[int, int]]:
    """The time signature in force in each measure of a part."""
    meters, current = [], (4, 4)
    for measure in part.findall("measure"):
        time = measure.find("attributes/time")
        if time is not None and time.findtext("beats") and time.findtext("beat-type"):
            try:
                current = (int(time.findtext("beats").split("+")[0]), int(time.findtext("beat-type")))
            except ValueError:
                pass
        meters.append(current)
    return meters


def label_truth(label: Path) -> dict[str, Any]:
    """Every measure's page and system, and every printed tempo mark, read from an exported label."""
    root = ElementTree.parse(label).getroot()
    part = root.find("part")
    measures, marks = [], []
    page, system = 0, 0
    for index, measure in enumerate(part.findall("measure")):
        printed = measure.find("print")
        if index > 0 and printed is not None:
            if printed.get("new-page") == "yes":
                page, system = page + 1, 0
            elif printed.get("new-system") == "yes":
                system += 1
        system_start = index == 0 or (printed is not None and
                                      (printed.get("new-page") == "yes" or printed.get("new-system") == "yes"))
        measures.append({"index": index, "number": measure.get("number"), "page": page, "system": system,
                         "system_start": system_start})
        for direction in measure.findall("direction"):
            words = " ".join(" ".join(element.itertext()).strip() for element in direction.iter("words")).strip()
            metronome = direction.find("direction-type/metronome")
            mark: dict[str, Any] = {"measure": index, "page": page, "system": system, "system_start": system_start,
                                    "placement": direction.get("placement"), "words": words or None,
                                    "bpm": None, "unit": None}
            if metronome is not None and metronome.findtext("per-minute"):
                beat_unit = metronome.findtext("beat-unit")
                dots = len(metronome.findall("beat-unit-dot"))
                number = re.search(r"\d+(?:\.\d+)?", metronome.findtext("per-minute"))
                if number:
                    mark["bpm"] = float(number.group())
                    mark["unit"] = UNIT_NAMES.get((beat_unit, dots), f"{beat_unit}+{dots}")
                    mark["parentheses"] = metronome.get("parentheses") == "yes"
            elif words and (embedded := SMUFL_METRONOME.search(words)):
                beat_unit, dots = SMUFL_NOTES[embedded.group(1)], embedded.group(2).count(SMUFL_DOT)
                mark["bpm"] = float(embedded.group(3))
                mark["unit"] = UNIT_NAMES.get((beat_unit, dots), f"{beat_unit}+{dots}")
                mark["parentheses"] = embedded.group(0).lstrip().startswith("(")
                mark["words"] = (words[:embedded.start()] + words[embedded.end():]).strip() or None
            if mark["bpm"] is not None or (words and is_tempo_word(words)):
                marks.append(mark)
    return {"measures": measures, "marks": marks}


def is_tempo_word(text: str) -> bool:
    lowered = text.lower()
    return any(word.lower() in lowered for word in OPENING_WORDS + CHANGE_WORDS)


# --- Choosing and writing marks ------------------------------------------------------------

def choose_unit(rng: random.Random, meter: tuple[int, int]) -> str:
    beats, beat_type = meter
    if beat_type == 8 and beats in (6, 9, 12):
        return "dotted_quarter" if rng.random() < 0.85 else "quarter"
    if beat_type == 2:
        return "half" if rng.random() < 0.7 else "quarter"
    roll = rng.random()
    if beats == 3 and beat_type == 4 and roll < 0.05:
        return "dotted_half"
    return "quarter" if roll < 0.85 else "half" if roll < 0.93 else "eighth" if roll < 0.97 else "dotted_quarter"


def plan_marks(item_id: str, meters: list[tuple[int, int]], taken: set[int]) -> list[dict[str, Any]]:
    """The marks to add: one at the start (unless the score has one) and 0-3 later, 4+ bars apart."""
    rng = random.Random(f"{SEED}:{item_id}")
    count = len(meters)
    wanted = rng.choice([0, 1, 1, 2, 2, 3])
    candidates = [index for index in range(4, max(4, count - 2)) if index not in taken]
    rng.shuffle(candidates)
    chosen: list[int] = []
    for index in candidates:
        if len(chosen) == wanted:
            break
        if all(abs(index - other) >= 4 for other in chosen):
            chosen.append(index)
    plans = []
    for position in ([0] if 0 not in taken else []) + sorted(chosen):
        opening = position == 0
        style_roll = rng.random()
        if opening:
            style = "metronome" if style_roll < 0.4 else "words+metronome"
        else:
            style = "metronome" if style_roll < 0.4 else "words+metronome" if style_roll < 0.8 else "words"
        unit = choose_unit(rng, meters[position])
        low, high = UNITS[unit][2]
        plans.append({
            "measure": position,
            "style": style,
            "words": rng.choice(OPENING_WORDS if opening else CHANGE_WORDS) if "words" in style else None,
            "unit": unit if "metronome" in style else None,
            "bpm": rng.randint(low, high) if "metronome" in style else None,
            "parentheses": "words" in style and rng.random() < 0.6,
        })
    return plans


def direction_element(plan: dict[str, Any]) -> ElementTree.Element:
    direction = ElementTree.Element("direction", placement="above")
    if plan["words"]:
        words_type = ElementTree.SubElement(direction, "direction-type")
        ElementTree.SubElement(words_type, "words", {"font-weight": "bold"}).text = plan["words"]
    if plan["bpm"] is not None:
        beat_unit, dots, _ = UNITS[plan["unit"]]
        metronome_type = ElementTree.SubElement(direction, "direction-type")
        metronome = ElementTree.SubElement(metronome_type, "metronome",
                                           parentheses="yes" if plan["parentheses"] else "no")
        ElementTree.SubElement(metronome, "beat-unit").text = beat_unit
        for _ in range(dots):
            ElementTree.SubElement(metronome, "beat-unit-dot")
        ElementTree.SubElement(metronome, "per-minute").text = str(plan["bpm"])
    ElementTree.SubElement(direction, "staff").text = "1"
    if plan["bpm"] is not None:
        quarters = {"quarter": 1, "dotted_quarter": 1.5, "half": 2, "dotted_half": 3, "eighth": 0.5}[plan["unit"]]
        ElementTree.SubElement(direction, "sound", tempo=f"{plan['bpm'] * quarters:g}")
    return direction


def add_marks(piano: Path, target: Path, item_id: str) -> list[dict[str, Any]]:
    tree = ElementTree.parse(piano)
    part = tree.getroot().find("part")
    measures = part.findall("measure")
    taken = {index for index, measure in enumerate(measures) if measure.find("direction/direction-type/metronome") is not None}
    plans = plan_marks(item_id, measure_meters(part), taken)
    for plan in plans:
        measure = measures[plan["measure"]]
        children = list(measure)
        # After the measure's attributes and layout, before its first note.
        at = next((position for position, child in enumerate(children) if child.tag not in ("attributes", "print")),
                  len(children))
        measure.insert(at, direction_element(plan))
    tree.write(target, encoding="UTF-8", xml_declaration=True)
    return plans


# --- Engraving -----------------------------------------------------------------------------

def find_musescore() -> str:
    sys.path.insert(0, str(HERE))
    from build_dataset import find_musescore as find
    return find(None)


def engrave_one(item: dict[str, Any], musescore: str) -> dict[str, Any]:
    work = TRUTH / item["id"]
    work.mkdir(parents=True, exist_ok=True)
    piano = RULER / item["id"] / "piano.musicxml"
    if sha256(piano) != item["piano_sha256"]:
        raise ValueError("the ruler's piano MusicXML does not match its frozen hash")
    marked, pdf, label = work / "piano-tempo.musicxml", work / "score.pdf", work / "label.musicxml"
    plans = add_marks(piano, marked, item["id"])
    job = work / "job.json"
    job.write_text(json.dumps([{"in": str(marked), "out": [str(pdf), str(label)]}]), encoding="utf-8")
    completed = subprocess.run([musescore, "-j", str(job)], capture_output=True, text=True, timeout=600)
    job.unlink()
    if completed.returncode != 0 or not pdf.is_file() or not label.is_file():
        detail = (completed.stderr or completed.stdout or "").strip()[-300:]
        raise ValueError(f"MuseScore job exit {completed.returncode}: {detail}")
    truth = label_truth(label)
    if len(truth["measures"]) != item["measures"]:
        raise ValueError(f"label has {len(truth['measures'])} measures, the ruler item {item['measures']}")
    # Every planned mark must come back at its measure, with its tempo.
    printed = {(mark["measure"], mark["bpm"]) for mark in truth["marks"]}
    missing = [plan for plan in plans if plan["bpm"] is not None and (plan["measure"], float(plan["bpm"])) not in printed]
    if missing:
        raise ValueError(f"{len(missing)} planned marks are not in the exported label")
    write_json(work / "truth.json", {"id": item["id"], "planned": plans, **truth})
    return {"pages": 1 + truth["measures"][-1]["page"], "planned": len(plans),
            "metronome_marks": sum(mark["bpm"] is not None for mark in truth["marks"]),
            "word_marks": sum(mark["bpm"] is None for mark in truth["marks"])}


def build(args: argparse.Namespace) -> None:
    musescore = find_musescore()
    version = subprocess.run([musescore, "--version"], capture_output=True, text=True, timeout=120).stdout.strip()
    if version != MUSESCORE_VERSION:
        raise ValueError(f"MuseScore is {version!r}; the ruler was engraved with {MUSESCORE_VERSION}")
    record_path = REPORT / "engraved.json"
    record = json.loads(record_path.read_text(encoding="utf-8")) if record_path.is_file() else {
        "musescore": musescore, "musescore_version": version, "seed": SEED, "items": {}}
    wanted = set(args.ids) if args.ids else None
    for item in source_items():
        if (wanted and item["id"] not in wanted) or (not wanted and item["id"] in record["items"]):
            continue
        try:
            outcome = {"status": "ok", **engrave_one(item, musescore)}
        except (ValueError, OSError, ElementTree.ParseError, subprocess.TimeoutExpired) as error:
            outcome = {"status": "failed", "error": str(error)[:400]}
        record["items"][item["id"]] = {"split": item["split"], **outcome}
        write_json(record_path, record)
        print(json.dumps({"id": item["id"], "split": item["split"], **outcome}), flush=True)


def freeze(_: argparse.Namespace) -> None:
    record = json.loads((REPORT / "engraved.json").read_text(encoding="utf-8"))
    items, failed = [], {}
    for item in source_items():
        outcome = record["items"].get(item["id"])
        if not outcome or outcome["status"] != "ok":
            failed[item["id"]] = (outcome or {}).get("error", "not engraved")
            continue
        work = TRUTH / item["id"]
        truth = json.loads((work / "truth.json").read_text(encoding="utf-8"))
        items.append({
            "id": item["id"], "split": item["split"], "composer": item["composer"],
            "pages": outcome["pages"], "measures": item["measures"],
            "marks": truth["marks"],
            "pdf": f"data/tempo-truth/{item['id']}/score.pdf", "pdf_sha256": sha256(work / "score.pdf"),
            "label_sha256": sha256(work / "label.musicxml"),
            "control_pdf": item["pdf"], "control_pdf_sha256": item["pdf_sha256"],
            "control_label": item["label"], "control_label_sha256": item["label_sha256"],
        })
    write_json(REPORT / "truth-manifest.json", {
        "plan": "2026-10-19-song-tempo", "phase": 2,
        "corpus": "OpenScore Lieder piano parts (CC0) via the displacement ruler",
        "musescore_version": record["musescore_version"], "seed": SEED,
        "generator_sha256": sha256(Path(__file__)),
        "source_manifests": {name: sha256(path) for name, path in SOURCE_MANIFESTS.items()},
        "failed": failed, "items": items})
    print(json.dumps({"items": len(items), "failed": len(failed),
                      "by_split": {split: sum(item["split"] == split for item in items) for split in SPLITS},
                      "metronome_marks": sum(mark["bpm"] is not None for item in items for mark in item["marks"])}))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    build_parser = commands.add_parser("build")
    build_parser.add_argument("--ids", nargs="*", default=[])
    build_parser.set_defaults(run=build)
    commands.add_parser("freeze").set_defaults(run=freeze)
    args = parser.parse_args(argv)
    args.run(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
