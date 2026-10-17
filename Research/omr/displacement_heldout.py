#!/usr/bin/env python3
"""Build the Phase 3 replan sets: a meter-change development set and a fresh held-out set.

Phase 3 of the displacement plan (plans/MAIN_PLAN.md) spent its test set: the frozen
correction gained on single-meter scores and lost on scores that change meter. The replan
(user decision, 2026-10-17) gates the correction away from real meter changes, which needs
more meter-change music to develop on and a held-out set nobody has looked at.

Both come from the Phase 1 scan, never reusing a Phase 1 ruler score:

- **dev-b**: songs by the Phase 1 dev composers that change bar length, most polyphonic first.
  Tuning already saw these composers, so nothing held out is spent.
- **test-b**: songs by composers in neither Phase 1 split. Every one that changes bar length,
  and an equal-sized draw of single-meter songs, so both sides of the gate are measured.

Engraving is the Phase 1 path unchanged (`displacement_ruler.engrave_one`), as is the label
check. Steps, each writing one file the next one reads:

    python displacement_heldout.py select     # meter profile of every candidate, then the pick order
    python displacement_heldout.py engrave    # MuseScore, in pick order, until each stratum is full
    python displacement_heldout.py freeze     # first eligible scores per stratum, hashed
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ElementTree
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import Any, Sequence

from displacement_ruler import (OUT, REVISION, SEED, SOURCE, engrave_one, favoured_order, note_bin, sha256,
                                write_json)

HERE = Path(__file__).resolve().parent
PHASE1 = HERE / "reports/displacement/phase1"
REPORT = HERE / "reports/displacement/phase3b"
# Stratum targets. Short and medium only: Phase 1 took every long candidate.
TARGETS = {"dev-b/meter": 20, "test-b/meter": 28, "test-b/single": 28}
COMPOSER_CAP = {"dev-b/meter": 5, "test-b/meter": 5, "test-b/single": 3}
SPARE = 1.25  # engrave this many per slot, for single-page and failed engravings


def bar_lengths(path: Path) -> list[str]:
    """Every distinct bar length the source writes, in quarters, as exact fractions."""
    lengths = set()
    for signature in ElementTree.parse(path).getroot().iter("TimeSig"):
        numerator, denominator = signature.findtext("sigN"), signature.findtext("sigD")
        if numerator and denominator:
            lengths.add(Fraction(4 * int(numerator), int(denominator)))
    return [str(length) for length in sorted(lengths)]


def stratum(row: dict[str, Any], dev: set[str], test: set[str]) -> str | None:
    if note_bin(row["notes"]) is None:
        return None
    changes = len(row["bar_lengths"]) > 1
    if row["composer"] in dev:
        return "dev-b/meter" if changes else None
    if row["composer"] in test:
        return None  # their other songs stay unused, for a later held-out set
    return "test-b/meter" if changes else "test-b/single"


def select(_: argparse.Namespace) -> None:
    scan = json.loads((PHASE1 / "scan.json").read_text())["candidates"]
    manifest = json.loads((PHASE1 / "manifest.json").read_text())
    used = {item["id"] for item in manifest["items"]}
    dev = {item["composer"] for item in manifest["items"] if item["split"] == "dev"}
    test = {item["composer"] for item in manifest["items"] if item["split"] == "test"}
    pools: dict[str, list[dict[str, Any]]] = {name: [] for name in TARGETS}
    for row in scan:
        if row["id"] in used:
            continue
        row = {**row, "bar_lengths": bar_lengths(SOURCE / row["source"])}
        name = stratum(row, dev, test)
        if name:
            row["stratum"] = name
            pools[name].append(row)
    order = []
    for name, pool in pools.items():
        per_composer: Counter[str] = Counter()
        chosen = 0
        for row in favoured_order(pool):
            if chosen >= round(TARGETS[name] * SPARE):
                break
            if per_composer[row["composer"]] >= COMPOSER_CAP[name]:
                continue
            per_composer[row["composer"]] += 1
            chosen += 1
            order.append(row)
    write_json(REPORT / "selection.json", {"targets": TARGETS, "composer_cap": COMPOSER_CAP, "order": order})
    print(json.dumps({name: {"pool": len(pool), "queued": sum(row["stratum"] == name for row in order)}
                      for name, pool in pools.items()}))


def engrave(_: argparse.Namespace) -> None:
    """Engrave in pick order. A score Phase 1 already engraved and never used is reused if unchanged."""
    from build_dataset import find_musescore

    musescore = find_musescore(None)
    phase1 = json.loads((PHASE1 / "engraved.json").read_text())
    record_path = REPORT / "engraved.json"
    record = json.loads(record_path.read_text()) if record_path.is_file() else {
        "musescore": musescore, "musescore_version": phase1["musescore_version"], "scores": {}}
    import subprocess
    version = subprocess.run([musescore, "--version"], capture_output=True, text=True, timeout=120).stdout.strip()
    if version != record["musescore_version"]:
        raise ValueError("MuseScore version differs from the Phase 1 engraving")
    for row in json.loads((REPORT / "selection.json").read_text())["order"]:
        identifier = row["id"]
        if identifier in record["scores"]:
            continue
        earlier = phase1["scores"].get(identifier, {})
        work = OUT / identifier
        if earlier.get("status") == "ok" and all(
                (work / name).is_file() and sha256(work / name) == earlier[key] for name, key in (
                    ("score.pdf", "pdf_sha256"), ("label.musicxml", "label_sha256"), ("piano.musicxml", "piano_sha256"))):
            outcome = {**earlier, "reused_phase1_engraving": True}
        else:
            try:
                outcome = {"status": "ok", **engrave_one(row, musescore, work)}
            except (ValueError, RuntimeError, ElementTree.ParseError, subprocess.TimeoutExpired, OSError) as error:
                outcome = {"status": "failed", "error": str(error)[:400]}
        record["scores"][identifier] = outcome
        write_json(record_path, record)
        print(json.dumps({"id": identifier, "stratum": row["stratum"], **{
            key: outcome.get(key) for key in ("status", "pages", "error")}}), flush=True)


def freeze(_: argparse.Namespace) -> None:
    from diagnose_rhythm import ground_truth_notes

    if (REPORT / "manifest.json").exists():
        raise FileExistsError("The replan manifest is frozen; a new set needs a new name")
    engraved = json.loads((REPORT / "engraved.json").read_text())["scores"]
    picked, rejected = [], {}
    count: Counter[str] = Counter()
    for row in json.loads((REPORT / "selection.json").read_text())["order"]:
        name = row["stratum"]
        if count[name] >= TARGETS[name]:
            continue
        outcome = engraved.get(row["id"], {"status": "not engraved"})
        if outcome["status"] != "ok" or outcome["pages"] < 2:
            rejected[row["id"]] = outcome.get("error") or f"{outcome.get('pages')} page(s)"
            continue
        work = OUT / row["id"]
        if any(sha256(work / file) != outcome[key] for file, key in (
                ("score.pdf", "pdf_sha256"), ("label.musicxml", "label_sha256"), ("piano.musicxml", "piano_sha256"))):
            raise ValueError(f"{row['id']}: engraved files changed after engraving")
        try:
            truth, _ = ground_truth_notes(work / "label.musicxml", expand_repeats=True, skip_grace_notes=False)
        except Exception as error:  # the bridge normalizer raises its own error types
            rejected[row["id"]] = f"label does not normalize: {error}"[:300]
            continue
        count[name] += 1
        picked.append({key: row[key] for key in (
            "id", "composer", "source", "source_sha256", "measures", "notes", "multi_voice_fraction", "tuplets",
            "time_signatures", "irregular_measures", "repeat_marks", "bar_lengths", "stratum")} | {
            "split": name.split("/")[0], "bin": note_bin(row["notes"]), "pages": outcome["pages"],
            "label_notes": len(truth), "label_span_quarters": float(max(note.onset + note.duration for note in truth)),
            "pdf": (work / "score.pdf").relative_to(HERE).as_posix(), "pdf_sha256": outcome["pdf_sha256"],
            "label": (work / "label.musicxml").relative_to(HERE).as_posix(), "label_sha256": outcome["label_sha256"],
            "piano_sha256": outcome["piano_sha256"]})
    short = {name: target - count[name] for name, target in TARGETS.items() if count[name] < target}
    manifest = {"plan": "2026-10-17-displacement-correction", "phase": "3 replan", "corpus": "OpenScore Lieder",
                "revision": REVISION, "license": "CC0-1.0",
                "musescore_version": json.loads((REPORT / "engraved.json").read_text())["musescore_version"],
                "seed": SEED, "targets": TARGETS, "composer_cap": COMPOSER_CAP, "short_of_target": short,
                "phase1_manifest_sha256": sha256(PHASE1 / "manifest.json"),
                "truth_flags": {"expand_repeats": True, "skip_grace_notes": False},
                "rejected": rejected, "items": picked}
    write_json(REPORT / "manifest.json", manifest)
    print(json.dumps({"items": len(picked), "by_stratum": dict(count), "short_of_target": short,
                      "rejected": len(rejected), "manifest_sha256": sha256(REPORT / "manifest.json"),
                      "pages": dict(sorted(Counter(item["pages"] for item in picked).items()))}))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    for name, handler in (("select", select), ("engrave", engrave), ("freeze", freeze)):
        commands.add_parser(name).set_defaults(handler=handler)
    args = parser.parse_args(argv)
    REPORT.mkdir(parents=True, exist_ok=True)
    args.handler(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
