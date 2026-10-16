"""Exercise the already-published scratch executable across fresh processes."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

WORKSPACE = Path(__file__).resolve().parents[2]
ROOT = WORKSPACE / "Research/omr/reports/homr-465-app-integration/phase2"


def run() -> None:
    exe = WORKSPACE / "tmp/homr465-scratch-app/Sheet2Play.exe"
    scan = json.loads((ROOT / "scratch-scan/result.json").read_text())
    settings_path = Path(os.environ["SHEET2PLAY_SETTINGS_PATH"])
    settings = json.loads(settings_path.read_text())
    settings["omr_engine"] = "homr"
    settings_path.write_text(json.dumps(settings, indent=2) + "\n")
    subprocess.run([str(exe), "--verify-omr-reopen", scan["manifest"], "Homr465", str(ROOT / "scratch-reopen-current")], check=True)
    reopened = json.loads((ROOT / "scratch-reopen-current/result.json").read_text())
    if reopened["savedEngine"] != "Homr" or reopened["midiSha256"] != scan["midiSha256"]:
        raise ValueError("Fallback selection or cross-process cache persistence failed")
    manifest = json.loads((ROOT.parent / "phase1/playback-manifest.json").read_text(encoding="utf-8-sig"))
    subprocess.run([str(exe), "--verify-omr", manifest["inputs"][0]["input"], "MusicXml", str(ROOT / "scratch-xml-current")], check=True)
    subprocess.run([str(exe), "--smoke", str(ROOT / "scratch-screens-current")], check=True)
    after = json.loads(settings_path.read_text())
    if after != settings:
        raise ValueError("Read-only reopen/import verification changed saved settings")
    if (settings_path.parent / "recent.json").exists():
        raise ValueError("Verification unexpectedly wrote recent-song history")
    print("Scratch cross-process reopen, saved 426 selection, direct XML import and UI states passed.")


if __name__ == "__main__":
    run()

