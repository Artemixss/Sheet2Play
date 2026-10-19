"""Phase 3 tempo check for the MusicXML songs plan (2026-10-19-musicxml-songs).

For each MusicXML score with tempo marks, interpret it with the app's own song interpreter
(``Bridge/song_model.py`` under the HOMR venv, as the app runs it), have MuseScore 4 export the
same score to MIDI, and let the app compare the two (``--verify-timeline``). The criterion is the
plan's: total length within 1% and every bar onset within 50 ms of MuseScore's export.

Inputs are the hand-written fixture ``fixtures/expression-tempo.musicxml`` and every exact label
in the displacement ruler that has a tempo mark. MuseScore stretches fermatas and plays "rit."
lines; the app plays neither (the plan keeps fermatas unplayed), so the report counts both marks
beside each score's result.

Usage (the app executable is the published one for the evidence run):

    Research/omr/.venv/Scripts/python.exe -I Research/omr/expression_tempo_check.py --app dist/Sheet2Play.exe
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BRIDGE = ROOT / "Bridge"
PYTHON = BRIDGE / ".venv-homr-gpu" / "Scripts" / "python.exe"
FIXTURE = HERE / "fixtures" / "expression-tempo.musicxml"
RULER = HERE / "data" / "displacement-ruler"
REPORT = HERE / "reports" / "musicxml-songs" / "phase3" / "tempo"
MUSESCORE = Path(r"C:\Program Files\MuseScore 4\bin\MuseScore4.exe")
BAR_LIMIT_SECONDS = 0.050
LENGTH_LIMIT_PERCENT = 1.0


def marks(path: Path) -> dict[str, int]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return {
        "tempo_sounds": len(re.findall(r"<sound[^>]*\btempo=", text)),
        "fermatas": len(re.findall(r"<fermata", text)),
        "gradual_tempo_words": len(re.findall(r"<words[^>]*>\s*(rit|rall|accel|riten)", text, re.IGNORECASE)),
        "pedals": len(re.findall(r"<pedal ", text)),
        "dynamics": len(re.findall(r"<dynamics", text)),
        "wedges": len(re.findall(r"<wedge ", text)),
    }


def stretched_measures(path: Path) -> set[str]:
    """Numbers of the measures holding a fermata or a gradual tempo word, which MuseScore stretches."""
    text = path.read_text(encoding="utf-8", errors="replace")
    found = set()
    for measure in re.finditer(r'<measure [^>]*number="([^"]+)"(.*?)</measure>', text, re.DOTALL):
        body = measure.group(2)
        if "<fermata" in body or re.search(r"<words[^>]*>\s*(rit|rall|accel|riten)", body, re.IGNORECASE):
            found.add(measure.group(1))
    return found


def run(command: list[str], timeout: int = 300) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout, cwd=str(ROOT))


def check(score_id: str, source: Path, app: Path, work: Path) -> dict[str, Any]:
    work.mkdir(parents=True, exist_ok=True)
    row: dict[str, Any] = {"id": score_id, "source": source.relative_to(ROOT).as_posix(), "marks": marks(source)}

    interpretation = work / "interpretation"
    shutil.rmtree(interpretation, ignore_errors=True)
    started = time.perf_counter()
    interpreted = run([str(PYTHON), "-B", str(BRIDGE / "song_model.py"), "--output", str(interpretation),
                       "--score", str(source)])
    row["interpret_seconds"] = round(time.perf_counter() - started, 2)
    if interpreted.returncode != 0:
        row["error"] = "interpreter: " + (interpreted.stderr or interpreted.stdout)[-400:]
        return row

    reference = work / "musescore.mid"
    reference.unlink(missing_ok=True)
    exported = run([str(MUSESCORE), "-o", str(reference), str(source)])
    row["musescore_exit"] = exported.returncode
    if not reference.is_file():
        forced = run([str(MUSESCORE), "-f", "-o", str(reference), str(source)])
        row["musescore_forced_exit"] = forced.returncode
    if not reference.is_file():
        row["error"] = "MuseScore wrote no MIDI file"
        return row

    output = work / "timeline.json"
    compared = run([str(app), "--verify-timeline", str(interpretation / "performance.json"), str(reference),
                    str(output)])
    if compared.returncode != 0 or not output.is_file():
        row["error"] = "app: " + (compared.stderr or compared.stdout)[-400:]
        return row
    result = json.loads(output.read_text(encoding="utf-8"))
    bars = result.pop("barRows")
    # A stretch moves every bar after it; the bars up to and including the first stretched one
    # measure the tempo marks alone.
    stretched = stretched_measures(source)
    first = next((index for index, bar in enumerate(bars) if bar["measure"] in stretched), len(bars) - 1)
    row["first_stretched_bar"] = None if first == len(bars) - 1 and bars[-1]["measure"] not in stretched else first
    row["max_bar_difference_before_stretch"] = max(abs(bar["difference"]) for bar in bars[:first + 1])
    row["bars_before_stretch_pass"] = row["max_bar_difference_before_stretch"] <= BAR_LIMIT_SECONDS
    # Paths and the raw pedal lists stay in the job's own timeline.json.
    for key in ("performance", "reference", "appPedal", "referencePedal"):
        result.pop(key, None)
    row["timeline"] = result
    row["bars_pass"] = result["maxBarDifferenceSeconds"] <= BAR_LIMIT_SECONDS
    row["length_pass"] = abs(result["lengthDifferencePercent"]) <= LENGTH_LIMIT_PERCENT
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--app", type=Path, required=True, help="Sheet2Play executable with --verify-timeline")
    parser.add_argument("--report", type=Path, default=REPORT)
    arguments = parser.parse_args()
    app = arguments.app.resolve()
    for required in (app, PYTHON, MUSESCORE, FIXTURE):
        if not required.is_file():
            print(f"missing: {required}", file=sys.stderr)
            return 2

    sources = [("fixture", FIXTURE)]
    for label in sorted(RULER.glob("*/label.musicxml")):
        if marks(label)["tempo_sounds"]:
            sources.append((label.parent.name, label))
    rows = []
    for score_id, source in sources:
        row = check(score_id, source, app, arguments.report / "jobs" / score_id)
        rows.append(row)
        timeline = row.get("timeline", {})
        print(f"[tempo] {score_id}: bars {timeline.get('maxBarDifferenceSeconds')} s, "
              f"length {timeline.get('lengthDifferencePercent')} %, {row.get('error', 'ok')}", flush=True)

    clean = [row for row in rows if "timeline" in row and not row["marks"]["fermatas"]
             and not row["marks"]["gradual_tempo_words"]]
    summary = {
        "plan": "2026-10-19-musicxml-songs",
        "phase": 3,
        "criterion": f"bar onsets within {BAR_LIMIT_SECONDS * 1000:.0f} ms and length within "
                     f"{LENGTH_LIMIT_PERCENT:g}% of MuseScore 4's MIDI export",
        "app": app.name,
        "musescore": str(MUSESCORE),
        "scores": len(rows),
        "errors": [row["id"] for row in rows if "error" in row],
        "without_fermata_or_gradual_tempo": {
            "scores": [row["id"] for row in clean],
            "pass": all(row["bars_pass"] and row["length_pass"] for row in clean) and bool(clean),
        },
        "bars_before_first_stretch_pass": all(row.get("bars_before_stretch_pass") for row in rows),
        "rows": rows,
    }
    arguments.report.mkdir(parents=True, exist_ok=True)
    (arguments.report / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: summary[key] for key in ("scores", "errors", "without_fermata_or_gradual_tempo",
                                                    "bars_before_first_stretch_pass")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
