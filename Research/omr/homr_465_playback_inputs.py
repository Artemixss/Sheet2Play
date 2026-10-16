"""Prepare offline, isolated inputs for the real Bridge/C# playback probe."""
from __future__ import annotations

from dataclasses import asdict
import importlib.util
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


def expected_result(path: Path) -> dict:
    import musicxml_normalizer as normalizer
    score = normalizer.normalize_musicxml(path, expand_repeats=True, force_source=True)
    return {"schema_version": 2, "engine": "musicxml", "engine_revision": "direct-xml",
            "tempo_changes": [asdict(value) for value in score.tempo_changes],
            "notes": [asdict(value) for value in normalizer.add_seconds(score)]}


def known_inputs(destination: Path) -> list[tuple[str, Path]]:
    module_path = WORKSPACE / "Bridge/tests/test_musicxml_normalizer.py"
    spec = importlib.util.spec_from_file_location("phase3_known_normalizer", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load known-correct fixture builders")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    builder = module.MusicXmlNormalizerTests()
    names = ("monophonic_melody", "dotted_notes_and_ties", "triplet_tuplets",
             "piano_grand_staff_chords", "multiple_voices_repeats_accidentals", "piecewise_tempo")
    result = [("known-" + name, builder.write_score(getattr(builder, "build_" + name)(), destination, name))
              for name in names]
    pickup = destination / "pickup-tempo.musicxml"
    pickup.write_text('''<?xml version="1.0" encoding="utf-8"?>
<score-partwise version="4.0"><part-list><score-part id="P1"><part-name>Piano</part-name></score-part></part-list><part id="P1">
<measure number="0" implicit="yes"><attributes><divisions>3</divisions><time><beats>4</beats><beat-type>4</beat-type></time><clef><sign>G</sign><line>2</line></clef></attributes><direction><sound tempo="60"/></direction><note><pitch><step>C</step><octave>4</octave></pitch><duration>3</duration><voice>1</voice><type>quarter</type></note></measure>
<measure number="1"><direction><sound tempo="120"/></direction><note><pitch><step>D</step><octave>4</octave></pitch><duration>12</duration><voice>1</voice><type>whole</type></note></measure>
</part></score-partwise>''', encoding="utf-8")
    result.append(("known-pickup-tempo", pickup))
    return result


def main() -> None:
    sys.path.insert(0, str(WORKSPACE / "dist/Bridge"))
    import musicxml_normalizer as normalizer
    frozen = load(PHASE2 / "scoring-environment.json")["normalizer"]
    if sha256_file(Path(normalizer.__file__)) != frozen["sha256"]:
        raise ValueError("Published normalizer changed")
    destination = PHASE3 / "playback-inputs-validated"
    destination.mkdir(exist_ok=False)
    inputs = [("candidate-" + path.parent.name, path) for path in sorted((PHASE2 / "development").glob("generated-*/input.musicxml"))]
    for row in load(PHASE2 / "development-inputs.json"):
        if row["collection"] == "generated" and row["reference_format"] == "musicxml":
            inputs.append(("source-" + row["item_id"], Path(row["reference"]["path"])))
    inputs += known_inputs(destination)
    inputs.append(("known-four-positions", PHASE3 / "export-installed/four-position-voices.musicxml"))
    tie_reproducer = HERE / "reports/zeus-attribution/phase2/cross-system-chord-tie.musicxml"
    inputs.append(("known-independent-voice-tie-limitation", tie_reproducer))
    rows = []
    golden = {row["id"]: row for row in load(WORKSPACE / "Bridge/tests/golden_scores.json")}
    for name, path in inputs:
        expected = expected_result(path)
        if name.startswith("known-") and name[6:] in golden:
            wanted = golden[name[6:]]["notes"]
            actual = expected["notes"]
            if sorted((n["pitch"], n["start_beat"], n["duration_beats"]) for n in actual) != sorted(
                    (n["pitch"], n["start_beat"], n["duration_beats"]) for n in wanted):
                raise ValueError("Known-correct golden mismatch: " + name)
        if name == "known-pickup-tempo":
            if [(n["start_beat"], n["duration_beats"], n["start_seconds"], n["duration_seconds"]) for n in expected["notes"]] != [(0, 1, 0, 1), (1, 4, 1, 2)]:
                raise ValueError("Pickup/tempo fixture differs from explicit expectation")
        if name == "known-independent-voice-tie-limitation" and len(expected["notes"]) != 6:
            raise ValueError("Known tie limitation behavior changed")
        rows.append({"id": name, "input": str(path), "input_sha256": sha256_file(path), "expected": expected})
    write_new(PHASE3 / "playback-manifest.json", {"inputs": rows, "normalizer": frozen,
              "bridge": str(WORKSPACE / "dist/Bridge/bridge.py"),
              "python": str(WORKSPACE / "Bridge/.venv-homr-gpu/Scripts/python.exe"),
              "tie_limitation": "Six production events; four independent-voice tie-merged events required. Compatibility is not correctness for this known case."})
    print(json.dumps({"inputs": len(rows), "known": sum(r["id"].startswith("known-") for r in rows)}))


if __name__ == "__main__":
    main()
