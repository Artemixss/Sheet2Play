"""Offline Phase 3 preservation and downstream traces; no inference or scoring edits."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import importlib.metadata
import json
from pathlib import Path
import sys

from homr_465_common import write_new
from screening_homr_compatibility import sha256_file

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[1]
PHASE2 = HERE / "reports/homr-timing-465/phase2"
PHASE3 = PHASE2.parent / "phase3"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def identity(path: Path) -> dict:
    return {"path": str(path.resolve()), "sha256": sha256_file(path)}


def snapshot() -> None:
    from sheet2play_omr.execution_resources import process_evidence, WindowsResourceSampler
    protected = load(PHASE2 / "protected-artifacts.json")
    configuration = load(PHASE2 / "candidate-configuration.json")
    pinned = protected + configuration["source_files"] + list(configuration["models"].values())
    for row in pinned:
        if sha256_file(Path(row["path"])) != row["sha256"]:
            raise ValueError("Protected/pinned artifact drift: " + row["path"])
    files = [identity(path) for path in sorted(PHASE2.rglob("*")) if path.is_file()]
    sources = [identity(path) for directory in ("Bridge", "Visualization_engine")
               for path in sorted((WORKSPACE / directory).glob("*"))
               if path.is_file() and path.suffix in {".py", ".cs", ".csproj", ".ps1"}]
    write_new(PHASE3 / "preservation-before.json", {
        "phase2_files": files, "protected": pinned, "production_sources": sources,
        "resources": WindowsResourceSampler()(), "processes": process_evidence(),
        "scope": "Phase 3 only; cached evidence, offline, no inference or production writes"})
    print(json.dumps({"phase2_files": len(files), "protected": len(pinned), "production_sources": len(sources)}))


def verify() -> None:
    saved = load(PHASE3 / "preservation-before.json")
    counts = {}
    for category in ("phase2_files", "protected", "production_sources"):
        for row in saved[category]:
            if sha256_file(Path(row["path"])) != row["sha256"]:
                raise ValueError("Preserved file drift: " + row["path"])
        counts[category] = len(saved[category])
    from sheet2play_omr.execution_resources import process_evidence
    write_new(PHASE3 / "preservation-after.json", {"verified": counts, "processes": process_evidence()})
    print(json.dumps(counts))


def events(score) -> list[dict]:
    from sheet2play_omr.timing import rational_time
    return [{"pitch": n.midi_pitch, "onset": str(rational_time(n.start_beat)),
             "duration": str(rational_time(n.duration_beats)), "staff": n.staff_index,
             "voice": n.voice_identifier} for n in score.notes]


def trace() -> None:
    sys.path.insert(0, str(WORKSPACE / "dist/Bridge"))
    import musicxml_normalizer as normalizer
    from homr_baseline_analyze import reference_notes
    from sheet2play_omr.zeus_trace import xml_trace
    from sheet2play_omr.research_ties import verify_midi
    from dataclasses import replace
    from fractions import Fraction
    frozen = load(PHASE2 / "scoring-environment.json")["normalizer"]
    if identity(Path(normalizer.__file__)) != frozen:
        raise ValueError("Unexpected normalizer origin/hash")
    rows = []
    inputs = [row for row in load(PHASE2 / "development-inputs.json") if row["collection"] == "generated"]
    old = {row["item_id"]: row for row in load(PHASE2 / "development-analysis.json")["development"]}
    for row in inputs:
        item = row["item_id"]
        root = PHASE2 / "development" / item
        literal, measures = xml_trace(root / "input.musicxml")
        score = normalizer.normalize_musicxml(root / "input.musicxml", expand_repeats=False, force_source=True)
        actual = events(score)
        if actual != load(root / "timed-events.json")["production_normalized_events"]:
            raise ValueError("Cached conversion drift: " + item)
        expected, _ = reference_notes(row)
        normalized_counter = Counter((n["pitch"], n["onset"], n["duration"]) for n in actual)
        literal_counter = Counter((n.pitch, str(n.onset), str(n.duration)) for n in literal)
        midi_events = tuple(replace(literal[0], pitch=n["pitch"], onset=Fraction(n["onset"]),
                                    duration=Fraction(n["duration"]), staff=n["staff"], voice=n["voice"], ties=()) for n in actual)
        midi_path = PHASE3 / "midi" / (item + ".mid")
        midi_path.parent.mkdir(exist_ok=True)
        midi_result = verify_midi(midi_events, midi_path)
        result = {"item_id": item, "reference_events": [n.json() for n in expected],
                  "literal_events": [n.json() for n in literal], "measures": measures,
                  "normalized_events": actual, "literal_equals_normalized_without_tie_merge": normalized_counter == literal_counter,
                  "cached_primary_f1": old[item]["metrics"]["onset_duration_f1"],
                  "midi": {**midi_result, **identity(midi_path)},
                  "seconds": [asdict(n) for n in normalizer.add_seconds(score)]}
        if item in {"generated-three_voices", "generated-tuplet_aligned"}:
            result["tokens"] = {key: load(root / "tokens.json")[key] for key in ("decoder_outputs", "exporter_inputs")}
            result["evidence"] = [identity(root / name) for name in ("input.png", "input.txt", "input_staff-0_input.jpg", "input_staff-0_debug_span_points.png", "tokens.json", "input.musicxml", "timed-events.json")]
        rows.append(result)
    write_new(PHASE3 / "downstream-traces.json", {"normalizer": frozen,
              "music21": importlib.metadata.version("music21"), "generated": rows})
    print(json.dumps({"controls": len(rows), "midi_preserved": sum(r["midi"]["preserved"] for r in rows),
                      "literal_normalized_differences": [r["item_id"] for r in rows if not r["literal_equals_normalized_without_tie_merge"]]}))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("snapshot", "trace", "verify"))
    arguments = parser.parse_args()
    {"snapshot": snapshot, "trace": trace, "verify": verify}[arguments.mode]()


if __name__ == "__main__":
    main()
