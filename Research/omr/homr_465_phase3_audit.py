"""Verify Phase 3 acceptance artifacts without inference or score mutation."""
from __future__ import annotations

import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from homr_465_common import write_new
from homr_465_readiness import PHASE2, PHASE3, WORKSPACE, identity, load, verify
from screening_homr_compatibility import sha256_file


def check_jobs() -> list[dict]:
    expected_failures = {"cached-traces": "WinError 5", "playback-inputs": "golden mismatch",
                         "playback-probe": "Unknown OMR engine", "frontend-regression": "CS0122",
                         "frontend-regression-linked": "failed to connect", "final-audit": "Broken link"}
    rows = []
    for path in sorted((PHASE3 / "jobs").glob("*/result.json")):
        value = load(path)
        name = path.parent.name
        limits = value["limits"]
        if (limits["worker_bytes"] != 4 * 1024**3 or limits["system_stop_percent"] != 85
                or limits["commit_headroom_bytes"] != 4 * 1024**3 or limits["active_processes"] != 16
                or limits["max_seconds"] > 4 * 3600 or value["stop_reason"] is not None):
            raise ValueError("Job safeguards/stop require review: " + name)
        if name in expected_failures:
            if value["status"] != "failed" or expected_failures[name] not in (path.parent / "worker.log").read_text(encoding="utf-8"):
                raise ValueError("Expected retained failure differs: " + name)
        elif value["status"] != "complete":
            raise ValueError("Incomplete job: " + name)
        rows.append({"name": name, "status": value["status"], "elapsed_seconds": value["elapsed_seconds"],
                     "peak_physical_percent": value["peak_physical_percent"],
                     "peak_commit_percent": value["peak_commit_percent"],
                     "peak_external_git_count": value["peak_git_count"], "receipt": identity(path)})
    return rows


def check_tests() -> dict:
    result = {}
    for name in ("focused-fixtures", "full-regression"):
        path = PHASE3 / (name + ".xml")
        suite = ET.parse(path).getroot().find("testsuite")
        if suite is None:
            raise ValueError("Missing JUnit suite")
        counts = {key: int(suite.get(key, "0")) for key in ("tests", "skipped", "failures", "errors")}
        if counts["failures"] or counts["errors"]:
            raise ValueError("Regression failure: " + name)
        result[name] = {**counts, "artifact": identity(path)}
    path = PHASE3 / "frontend-test-results-diagnostic/phase3-frontend.trx"
    counter = ET.parse(path).getroot().find(".//{*}Counters")
    if counter is None or int(counter.get("total", "0")) == 0 or counter.get("failed") != "0" or counter.get("passed") != counter.get("total"):
        raise ValueError("Frontend regression incomplete")
    result["frontend"] = {**counter.attrib, "artifact": identity(path)}
    return result


def check_repair() -> dict:
    repair = load(PHASE3 / "runtime-repair.json")
    original, copy = Path(repair["source"]), Path(repair["copy"])
    for path, key in ((original, "source_sha256"), (copy, "copy_sha256")):
        if sha256_file(path) != repair[key]:
            raise ValueError("Repair identity drift")
    marker = "public static string GetEngineRevision(OmrEngine engine) => engine switch\n    {\n        OmrEngine.Homr => HomrEngineRevision,\n        OmrEngine.Zeus => ZeusEngineRevision,"
    if copy.read_text(encoding="utf-8") != original.read_text(encoding="utf-8").replace(marker, marker + '\n        OmrEngine.MusicXml => "direct-xml",'):
        raise ValueError("Repair differs from single reviewed branch")
    return repair


def check_links(*, allow_self: bool = False) -> list[dict]:
    paths = [WORKSPACE / "plans/MAIN_PLAN.md", WORKSPACE / "plans/README.md", PHASE2.parent / "handoff.md"]
    paths += [PHASE3 / name for name in ("REPORT.md", "acceptance-ledger.md", "three-voices-diagnosis.md", "tuplet-aligned-diagnosis.md", "runtime-playback.md", "job-record.md")]
    result = []
    for path in paths:
        targets = re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8"))
        for target in targets:
            if "://" in target or target.startswith("#"):
                continue
            file = target.split("#", 1)[0]
            pending = {(PHASE3 / name).resolve() for name in ("audit.json", "preservation-after.json")}
            if file and not (path.parent / file).exists() and not (allow_self and (path.parent / file).resolve() in pending):
                raise ValueError(f"Broken link {path}: {target}")
        result.append({"document": identity(path), "links_checked": len(targets)})
    return result


def main() -> None:
    before = load(PHASE3 / "preservation-before.json")
    if {str(path.resolve()) for path in PHASE2.rglob("*") if path.is_file()} != {row["path"] for row in before["phase2_files"]}:
        raise ValueError("Phase 2 file inventory changed")
    replay = []
    for label in ("shared", "installed"):
        runtime = load(PHASE3 / ("runtime-" + label + ".json"))
        if not runtime["native_import"]["success"] or any(not row["declared_compatible"] for row in runtime["dependencies"]):
            raise ValueError("Runtime compatibility failure")
        for row in runtime["replays"]:
            if sha256_file(Path(row["path"])) != row["sha256"] or not row["musical_xml_matches_cached"]:
                raise ValueError("Export replay changed")
        replay.append({"label": label, "replays": len(runtime["replays"])})
    manifest = load(PHASE3 / "playback-manifest.json")
    playback = load(PHASE3 / "playback-results-repaired/results.json")
    if {row["id"] for row in playback} != {row["id"] for row in manifest["inputs"]}:
        raise ValueError("Playback coverage differs")
    for row in manifest["inputs"]:
        if sha256_file(Path(row["input"])) != row["input_sha256"]:
            raise ValueError("Playback input changed")
    jobs, tests, repair, documents = check_jobs(), check_tests(), check_repair(), check_links(allow_self=True)
    verify()
    write_new(PHASE3 / "audit.json", {"jobs": jobs, "tests": tests, "repair": repair,
              "fixed_token_replays": replay, "playback_inputs": len(playback), "documents": documents,
              "max_midi_start_error_seconds": max(row["maxStartErrorSeconds"] for row in playback),
              "max_midi_duration_error_seconds": max(row["maxDurationErrorSeconds"] for row in playback),
              "phase2_preservation": load(PHASE3 / "preservation-after.json"),
              "scope": "Phase 3 complete; no inference/training/production adoption; six failed receipts retained with verified failure boundaries"})
    check_links()
    print(json.dumps({"phase2_preserved": len(before["phase2_files"]), "playback_inputs": len(playback), "tests": check_tests()}))


if __name__ == "__main__":
    main()
