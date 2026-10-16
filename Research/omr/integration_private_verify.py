"""Verify one retained private source through the published app without touching recents."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from guarded_execution import run_guarded
from sheet2play_omr.safety_policy import SafetyLimits
from integration_qualify import WORKSPACE, sha256, save_new

ROOT = WORKSPACE / "Research/omr/reports/homr-465-app-integration/phase2"
LIBRARY = Path(r"C:\Users\bur4x\AppData\Local\Sheet2Play")
SELECTION = ROOT / "private-probe.json"


def preserved_files() -> dict[str, str]:
    paths = list(LIBRARY.glob("*.json"))
    paths += list((LIBRARY / "songs/midi/homr").glob("*"))
    paths += list((LIBRARY / "songs/pdf").glob("*"))
    return {str(path): sha256(path) for path in paths if path.is_file()}


def prepare() -> None:
    import pymupdf

    sources = {sha256(path): path for path in (LIBRARY / "songs/pdf").glob("*.pdf")}
    candidates = []
    for manifest_path in (LIBRARY / "songs/midi/homr").glob("*.cache.json"):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        source = sources.get(manifest["source_sha256"])
        midi = Path(str(manifest_path)[:-len(".cache.json")])
        if source is None or not midi.is_file():
            continue
        with pymupdf.open(source) as document:
            if document.page_count == 1:
                candidates.append((source.stat().st_size, str(source)))
    if not candidates:
        raise ValueError("No recoverable one-page PDF; review before expanding the private probe")
    source = Path(min(candidates)[1])
    save_new(SELECTION, {"source": str(source), "source_sha256": sha256(source),
                        "pages": 1, "preserved": preserved_files(),
                        "executable_sha256": sha256(WORKSPACE / "dist/Sheet2Play.exe")})
    print("Frozen one recoverable one-page private probe; source names remain local.")


def verify() -> None:
    selection = json.loads(SELECTION.read_text())
    os.environ["SHEET2PLAY_HOME"] = str(LIBRARY)
    os.environ["SHEET2PLAY_SETTINGS_PATH"] = str(LIBRARY / "settings.json")
    executable = WORKSPACE / "dist/Sheet2Play.exe"
    if sha256(executable) != selection["executable_sha256"]:
        raise ValueError("Published executable changed before private verification")
    if sha256(Path(selection["source"])) != selection["source_sha256"]:
        raise ValueError("Private source identity changed")
    scan = ROOT / "private-scan"
    reopen = ROOT / "private-reopen"
    for mode, input_path, output in (("--verify-omr", selection["source"], scan),
                                    ("--verify-omr-reopen", None, reopen)):
        if input_path is None:
            input_path = json.loads((scan / "result.json").read_text())["manifest"]
        command = [str(executable), mode, input_path, "Homr465", str(output)]
        job = ROOT / "jobs" / output.name
        if job.exists():
            raise FileExistsError("Existing private job needs review before any retry")
        result = run_guarded(command, WORKSPACE, job, SafetyLimits(max_seconds=600),
                             lock_path=WORKSPACE / ".research-worker.lock")
        if result["status"] != "complete":
            raise RuntimeError("Private app verification failed; preserve its receipt")
        report = json.loads((output / "result.json").read_text())
        if report["library"] != str(LIBRARY) or report["savedEngine"] != "Homr465":
            raise ValueError("Private verification used the wrong real settings/library")
    first = json.loads((scan / "result.json").read_text())
    second = json.loads((reopen / "result.json").read_text())
    if first["LoadedFromCache"] or not second["LoadedFromCache"]:
        raise ValueError("Expected one fresh scan followed by a new-process cache hit")
    if first["midiSha256"] != second["midiSha256"] or first["manifestSha256"] != second["manifestSha256"]:
        raise ValueError("Restart changed the candidate cache")
    for name, identity in selection["preserved"].items():
        if sha256(Path(name)) != identity:
            raise ValueError("Private verification changed preserved metadata, source or426 cache")
    log = (ROOT / "jobs/private-scan/worker.log").read_text(errors="replace")
    receipts = sorted((LIBRARY / "omr-jobs").glob("*/native.json"), key=lambda p: p.stat().st_mtime_ns)
    receipt = receipts[-1]
    native = json.loads(receipt.read_text())
    origin = str(WORKSPACE / "dist/Bridge/.runtime/homr-465/source")
    if str(receipt.parent) not in log or native["status"] != "complete" or not all(
            origin in path for path in native["module_origins"].values()):
        raise ValueError("Private published-native receipt attribution/origins failed")
    save_new(ROOT / "private-verification.json", {
        "pages": 1, "notes": first["NoteCount"], "restart_cache_hit": True,
        "old_caches_sources_settings_recents_unchanged": True,
        "native_receipt": str(receipt), "physical_audio_tested": False})
    print(json.dumps({"private_scan": "complete", "notes": first["NoteCount"],
                      "restart_cache_hit": True, "preserved_files": len(selection["preserved"])}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "verify"))
    options = parser.parse_args()
    prepare() if options.mode == "prepare" else verify()
