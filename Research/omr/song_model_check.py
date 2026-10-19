#!/usr/bin/env python3
"""Phase 1 acceptance check for the MusicXML song model (`plans/2026-10-19-musicxml-songs.md`).

For every cached recognition of the displacement ruler and replan sets, with the shipped 465
and 480 runtimes, this compares `Bridge/song_model.py` with the shipped bridge path (the pinned
normalizer, the shipped timing fix per page with the app's fallback, `combine_score_pages`), with
the fix off and on, and builds and opens the combined score in music21 and the MuseScore CLI.
For every exact label (MuseScore's own MusicXML) it compares the feature counts with an
independent element count and the played notes with the bridge's MusicXML import, and records
what music21 loses. It then times the largest recognitions in a fresh process, checks that
interpretation is byte-for-byte repeatable, and that no pinned file changed. No inference.

    Research\\omr\\.venv\\Scripts\\python.exe -B Research\\omr\\guarded_execution.py
        --output Research\\omr\\reports\\musicxml-songs\\phase1\\jobs\\check-1 --max-seconds 10800 --
        Bridge\\.venv-homr-gpu\\Scripts\\python.exe -I -B Research\\omr\\song_model_check.py

Rows go to `rows.jsonl` as they finish, so a rerun resumes where an interrupted one stopped; the
summary and acceptance go to `summary.json`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BRIDGE = ROOT / "Bridge"
sys.path.insert(0, str(BRIDGE))
sys.path.insert(0, str(HERE / "src"))
sys.path.insert(0, str(HERE))

import musicxml_normalizer as normalizer  # noqa: E402
import song_model  # noqa: E402
import timing_correction  # noqa: E402
from build_dataset import find_musescore  # noqa: E402
from displacement_attribution import app_pages  # noqa: E402
from displacement_correct import RULER, manifest_items  # noqa: E402

ENGINES = ("homr465", "homr480-ab369ac")
SPLITS = ("dev", "test", "dev-b", "test-b")
REPORT = HERE / "reports/musicxml-songs/phase1"
DETERMINISM_SAMPLE = 20
COST_SAMPLE = 3
COST_LIMIT_SECONDS = 10.0


def key(start: float, pitch: int, duration: float) -> tuple[int, int, int]:
    return round(start * 1e6), pitch, round(duration * 1e6)


def difference(reference: Counter, candidate: Counter) -> dict[str, int]:
    return {"missing": sum((reference - candidate).values()), "extra": sum((candidate - reference).values())}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def open_in_musescore(musescore: str, document: bytes, work: Path, *, force: bool = False) -> dict[str, Any]:
    """Convert with the MuseScore CLI. Without --force MuseScore refuses a score it judges
    corrupted, which includes any incomplete measure; HOMR's own pages contain those."""
    source, target = work / "score.musicxml", work / "score.mscz"
    source.write_bytes(document)
    target.unlink(missing_ok=True)
    started = time.perf_counter()
    command = [musescore, *(["-f"] if force else []), "-o", str(target), str(source)]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=300)
    result = {"exit": completed.returncode, "written": target.is_file() and target.stat().st_size > 0,
              "seconds": round(time.perf_counter() - started, 2)}
    if completed.returncode != 0:
        result["detail"] = (completed.stderr or completed.stdout or "").strip()[-300:]
    return result


def check_recognition(item: dict[str, Any], engine: str, musescore: str, work: Path, repeat: bool) -> dict[str, Any]:
    from music21 import converter, stream

    paths = [path for path, _ in app_pages(item, engine)]
    names = [f"page-{number:04d}.musicxml" for number in range(1, len(paths) + 1)]
    repeats = any(marker in path.read_bytes() for path in paths for marker in (b"<repeat", b"<ending"))
    row: dict[str, Any] = {"kind": "recognition", "id": item["id"], "split": item["split"], "engine": engine,
                           "pages": len(paths), "stand_in_pages": sum(stand_in for _, stand_in in app_pages(item, engine)),
                           "repeats": repeats}
    for timing in (False, True):
        shipped, fallbacks = [], []
        for number, path in enumerate(paths):
            page = normalizer.normalize_musicxml(path)
            if timing:
                try:
                    page = timing_correction.correct_page(path, page, number == 0)
                except Exception:  # noqa: BLE001 - the app keeps the page as read on any failure
                    fallbacks.append(number + 1)
            shipped.append(page)
        reference = Counter(key(note.start_beat, note.midi_pitch, note.duration_beats)
                            for note in normalizer.combine_score_pages(shipped).notes)
        started = time.perf_counter()
        performance = song_model.interpret(paths, timing_correction_enabled=timing, names=names)
        seconds = time.perf_counter() - started
        data = song_model.performance_bytes(performance)
        sequential = Counter(key(*note) for note in song_model.sequential_notes(performance))
        played = Counter(key(*note) for note in song_model.played_notes(performance))
        result = {
            "reference_notes": sum(reference.values()),
            "sequential": difference(reference, sequential),
            "played": difference(reference, played),
            "reference_fallback_pages": fallbacks,
            "kept_pages": [page["index"] + 1 for page in performance["pages"] if page["timing"] == "kept"],
            "seconds": round(seconds, 3),
            "warnings": performance["warnings"],
            "sha256": sha256(data),
        }
        if repeat:
            again = song_model.interpret(paths, timing_correction_enabled=timing, names=names)
            result["repeatable"] = song_model.performance_bytes(again) == data
        row["timing" if timing else "plain"] = result
        if not timing:
            features = performance["features"]
            row["features"] = {name: features[name] for name in (
                "measures", "played_measures", "notes", "grace_notes", "tied_notes", "slurs", "articulations",
                "articulation_marks", "unjoined_marked_notes", "repeat_forward", "repeat_backward", "endings",
                "jump_marks", "pedal_marks", "dynamics_marks", "wedges", "metronome_marks", "tempo_sounds")}
            measures = len(performance["measures"])
    combined = song_model.combined_musicxml(paths)
    try:
        parsed = converter.parse(combined.decode("utf-8"), format="musicxml")
        music21_measures = len(parsed.parts[0].getElementsByClass(stream.Measure))
        row["combined"] = {"music21": "ok", "measures": music21_measures, "model_measures": measures}
    except Exception as error:  # noqa: BLE001 - recorded as a failure of the combined score
        row["combined"] = {"music21": f"{type(error).__name__}: {error}"[:300], "model_measures": measures}
    row["combined"]["sha256"] = sha256(combined)
    strict = open_in_musescore(musescore, combined, work)
    row["combined"]["musescore"] = strict
    if strict["exit"] != 0 or not strict["written"]:
        # Refused as corrupted: the combined score adds no fault of its own only if a page it
        # was built from is refused too.
        pages = [open_in_musescore(musescore, path.read_bytes(), work) for path in dict.fromkeys(paths)]
        row["combined"]["pages_refused"] = sum(page["exit"] != 0 or not page["written"] for page in pages)
        forced = open_in_musescore(musescore, combined, work, force=True)
        row["combined"]["musescore_forced"] = forced
        if forced["exit"] != 0 or not forced["written"]:
            # MuseScore 4 sometimes crashes outright on a forced corrupted score; that is a fault
            # of the combined score only if every page it was built from opens.
            pages = [open_in_musescore(musescore, path.read_bytes(), work, force=True) for path in dict.fromkeys(paths)]
            row["combined"]["pages_failing_forced"] = sum(page["exit"] != 0 or not page["written"] for page in pages)
    return row


def check_label(folder: Path, repeat: bool) -> dict[str, Any]:
    from music21 import converter, expressions

    label = folder / "label.musicxml"
    document = song_model.read_document(label)
    started = time.perf_counter()
    performance = song_model.interpret([label], kind=song_model.MUSICXML)
    seconds = time.perf_counter() - started
    features = performance["features"]
    independent = song_model.independent_counts(document)
    reference_score = normalizer.normalize_musicxml(label, expand_repeats=True, skip_grace_notes=False)
    reference = Counter(key(note.start_beat, note.midi_pitch, note.duration_beats) for note in reference_score.notes)
    played = Counter(key(*note) for note in song_model.played_notes(performance))
    try:
        parsed = converter.parse(str(label))
        music21_pedals = len(parsed.spannerBundle.getByClass(expressions.PedalMark))
    except Exception as error:  # noqa: BLE001 - informational only
        music21_pedals = f"{type(error).__name__}: {error}"[:200]
    row = {
        "kind": "label", "id": folder.name,
        "count_mismatch": {name: [features[name], value] for name, value in independent.items() if features[name] != value},
        "independent": independent,
        "repeats": features["repeat_backward"] + features["endings"] + features["jump_marks"] > 0,
        "measures": features["measures"], "played_measures": features["played_measures"],
        "reference_notes": sum(reference.values()),
        "played": difference(reference, played),
        "grace_notes": features["grace_notes"],
        "unjoined_marked_notes": features["unjoined_marked_notes"],
        "pedal_events": len(performance["pedals"]),
        "pedal_starts": sum(pedal["type"] == "start" for pedal in performance["pedals"]),
        "music21_pedal_spanners": music21_pedals,
        "dynamics_events": len(performance["dynamics"]), "wedges": len(performance["wedges"]),
        "tempos": [[tempo["measure"], tempo["quarter_bpm"], tempo["source"]] for tempo in performance["tempos"]],
        "music21_tempos": [[change.start_beat, change.bpm] for change in reference_score.tempo_changes],
        "seconds": round(seconds, 3),
        "warnings": performance["warnings"],
    }
    if repeat:
        again = song_model.interpret([label], kind=song_model.MUSICXML)
        row["repeatable"] = song_model.performance_bytes(again) == song_model.performance_bytes(performance)
    return row


def cost(rows: list[dict[str, Any]], work: Path) -> list[dict[str, Any]]:
    """Time and peak memory of the largest recognitions, each interpreted in a fresh process."""
    measured = []
    for engine in ENGINES:
        largest = sorted((row for row in rows if row["kind"] == "recognition" and row["engine"] == engine),
                         key=lambda row: (row["pages"], row["plain"]["reference_notes"]), reverse=True)[:COST_SAMPLE]
        for row in largest:
            item = {"id": row["id"]}
            paths = [str(path) for path, _ in app_pages(item, engine)]
            command = [sys.executable, "-B", str(BRIDGE / "song_model.py"), "--resources", "--timing-correction",
                       "--output", str(work / "cost"), *paths]
            started = time.perf_counter()
            completed = subprocess.run(command, capture_output=True, text=True, timeout=600, cwd=BRIDGE)
            wall = time.perf_counter() - started
            summary = json.loads(completed.stdout.strip().splitlines()[-1]) if completed.returncode == 0 else {}
            measured.append({"id": row["id"], "engine": engine, "pages": row["pages"],
                             "notes": row["plain"]["reference_notes"], "exit": completed.returncode,
                             "interpret_seconds": summary.get("seconds"), "process_seconds": round(wall, 2),
                             "peak_working_set_mib": round(summary["peak_working_set_bytes"] / 1024 ** 2, 1)
                             if summary.get("peak_working_set_bytes") else None})
    return measured


def pins() -> list[dict[str, Any]]:
    source = (ROOT / "Visualization_engine/OmrPipeline.cs").read_text(encoding="utf-8")
    results = []
    for runtime in ("465", "480"):
        profile_path = BRIDGE / f"homr{runtime}-profile.json"
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        changed = [row["path"] for row in profile["bridge_files"]
                   if sha256((BRIDGE / row["path"]).read_bytes()) != row["sha256"]]
        pinned = re.search(rf'Homr{runtime}ProfileSha256 = "([0-9a-f]{{64}})"', source)
        results.append({"runtime": runtime, "bridge_files": len(profile["bridge_files"]), "changed": changed,
                        "profile_matches_csharp": bool(pinned) and pinned.group(1) == sha256(profile_path.read_bytes())})
    return results


def summarize(rows: list[dict[str, Any]], measured: list[dict[str, Any]], pinned: list[dict[str, Any]]) -> dict[str, Any]:
    recognitions = [row for row in rows if row["kind"] == "recognition"]
    labels = [row for row in rows if row["kind"] == "label"]
    required = [row for row in recognitions if not row["repeats"]]

    def exact(row: dict[str, Any]) -> bool:
        return all(row[mode]["sequential"] == {"missing": 0, "extra": 0}
                   and row[mode]["played"] == {"missing": 0, "extra": 0} for mode in ("plain", "timing")) \
            and row["timing"]["kept_pages"] == row["timing"]["reference_fallback_pages"]

    parity_failures = [f"{row['id']} {row['engine']}" for row in required if not exact(row)]
    with_repeats = [{"id": row["id"], "engine": row["engine"], "sequential_plain": row["plain"]["sequential"],
                     "played_plain": row["plain"]["played"], "sequential_timing": row["timing"]["sequential"],
                     "played_timing": row["timing"]["played"],
                     "fallbacks_match": row["timing"]["kept_pages"] == row["timing"]["reference_fallback_pages"],
                     "played_measures": row["features"]["played_measures"], "measures": row["features"]["measures"]}
                    for row in recognitions if row["repeats"]]
    count_failures = [row["id"] for row in labels if row["count_mismatch"]]
    repeatable = [row.get("repeatable") for row in rows if "repeatable" in row] + \
        [row[mode].get("repeatable") for row in recognitions for mode in ("plain", "timing") if "repeatable" in row[mode]]
    def combined_fault(row: dict[str, Any]) -> bool:
        combined = row["combined"]
        if combined["music21"] != "ok" or combined.get("measures") != combined["model_measures"]:
            return True
        if combined["musescore"]["exit"] == 0 and combined["musescore"]["written"]:
            return False
        if combined["pages_refused"] == 0:
            return True
        forced = combined["musescore_forced"]
        return (forced["exit"] != 0 or not forced["written"]) and combined["pages_failing_forced"] == 0

    combined_failures = [f"{row['id']} {row['engine']}" for row in recognitions if combined_fault(row)]
    musescore_strict_refusals = sum(row["combined"]["musescore"]["exit"] != 0 for row in recognitions)
    slowest = max((item["interpret_seconds"] or 1e9 for item in measured), default=None)
    survives: dict[str, Counter] = {engine: Counter() for engine in ENGINES}
    for row in recognitions:
        for name, value in row["features"].items():
            if isinstance(value, dict):
                survives[row["engine"]].update({f"articulation:{key}": count for key, count in value.items()})
            else:
                survives[row["engine"]][name] += value
    label_totals = Counter()
    for row in labels:
        label_totals.update({name: value for name, value in row["independent"].items()})
        label_totals["pedal_events"] += row["pedal_events"]
        label_totals["pedal_starts"] += row["pedal_starts"]
        label_totals["music21_pedal_spanners"] += row["music21_pedal_spanners"] if isinstance(row["music21_pedal_spanners"], int) else 0
        label_totals["labels_with_pedals"] += row["independent"]["pedal_marks"] > 0
        label_totals["labels_with_tempo"] += bool(row["tempos"])
        label_totals["unjoined_marked_notes"] += row["unjoined_marked_notes"]
    label_repeats = [{"id": row["id"], "played": row["played"], "played_measures": row["played_measures"],
                      "measures": row["measures"]} for row in labels if row["repeats"]]
    acceptance = {
        "parity": {"passed": not parity_failures, "required": len(required), "failures": parity_failures},
        "features": {"passed": not count_failures, "labels": len(labels), "failures": count_failures},
        "rebuild": {"passed": bool(repeatable) and all(repeatable) and not combined_failures,
                    "repeatability_checks": len(repeatable), "not_repeatable": repeatable.count(False),
                    "combined_checked": len(recognitions), "combined_failures": combined_failures,
                    "musescore_strict_refusals": musescore_strict_refusals,
                    "musescore_forced_failures": [f"{row['id']} {row['engine']}" for row in recognitions
                                                  if row["combined"].get("musescore_forced", {}).get("exit", 0) != 0],
                    "rule": "music21 opens every combined score with the model's measure count; MuseScore opens it, "
                            "or refuses it only where it refuses one of its own pages, and opens it with --force "
                            "unless it also fails on one of its pages with --force"},
        "cost": {"passed": slowest is not None and slowest < COST_LIMIT_SECONDS, "slowest_seconds": slowest,
                 "limit_seconds": COST_LIMIT_SECONDS},
        "pins": {"passed": all(not row["changed"] and row["profile_matches_csharp"] for row in pinned)},
    }
    return {
        "acceptance": acceptance,
        "recognitions": len(recognitions),
        "recognitions_with_repeats": with_repeats,
        "labels_with_repeats": label_repeats,
        "label_parity_failures_without_repeats": [row["id"] for row in labels if not row["repeats"]
                                                  and row["played"] != {"missing": 0, "extra": 0}],
        "label_totals": dict(label_totals),
        "pdf_features_by_engine": {engine: dict(sorted(values.items())) for engine, values in survives.items()},
        "cost": measured,
        "pins": pinned,
        "interpret_seconds": {mode: max((row[mode]["seconds"] for row in recognitions), default=None)
                              for mode in ("plain", "timing")},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--limit", type=int, default=None, help="check only the first N items of each kind")
    arguments = parser.parse_args()
    arguments.report.mkdir(parents=True, exist_ok=True)
    rows_path = arguments.report / "rows.jsonl"
    rows = [json.loads(line) for line in rows_path.read_text(encoding="utf-8").splitlines()] if rows_path.is_file() else []
    done = {(row["kind"], row["id"], row.get("engine")) for row in rows}
    musescore = find_musescore(None)
    with tempfile.TemporaryDirectory(prefix="song-model-check-") as temporary, rows_path.open("a", encoding="utf-8") as log:
        work = Path(temporary)

        def record(row: dict[str, Any]) -> None:
            rows.append(row)
            log.write(json.dumps(row) + "\n")
            log.flush()

        items = manifest_items(SPLITS)[:arguments.limit]
        for engine in ENGINES:
            checked = 0
            for item in items:
                result = RULER / "captures" / engine / item["id"] / "result.json"
                if not result.is_file() or json.loads(result.read_text())["status"] != "ok":
                    continue
                checked += 1
                if ("recognition", item["id"], engine) in done:
                    continue
                record(check_recognition(item, engine, musescore, work, repeat=checked <= DETERMINISM_SAMPLE))
                print(f"[check] {engine} {item['id']} done ({checked})", flush=True)
        folders = sorted(path.parent for path in RULER.glob("*/label.musicxml"))[:arguments.limit]
        for number, folder in enumerate(folders):
            if ("label", folder.name, None) in done:
                continue
            record(check_label(folder, repeat=number < DETERMINISM_SAMPLE))
            print(f"[check] label {folder.name} done", flush=True)
        measured = cost(rows, work)
    summary = summarize(rows, measured, pins())
    (arguments.report / "summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({name: value["passed"] for name, value in summary["acceptance"].items()}))
    return 0 if all(value["passed"] for value in summary["acceptance"].values()) else 1


if __name__ == "__main__":
    sys.exit(main())
