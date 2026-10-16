"""Audit local migration accounting, immutable old files and published-native receipts."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re

from integration_qualify import WORKSPACE, sha256, save_new

ROOT = WORKSPACE / "Research/omr/reports/homr-465-app-integration/phase3"
LIBRARY = Path(r"C:\Users\bur4x\AppData\Local\Sheet2Play")


def library_path(relative: str) -> Path:
    path = (LIBRARY / relative.replace("\\", "/")).resolve()
    path.relative_to(LIBRARY)
    return path


def normalize_recent(row: dict) -> dict:
    return {**row, "manifest_relative_path": row["manifest_relative_path"].replace("\\", "/")}


def verify_native_coverage(log: str, records: dict, items: list[dict]) -> None:
    inventory = {item["id"]: item for item in items}
    seen = set()
    pages = Counter()
    for line in log.splitlines():
        receipt = re.search(r"HOMR 465 receipt=[^\r\n]+? status=(\w+)", line)
        if receipt:
            pages[receipt[1]] += 1
        terminal = re.fullmatch(r"MIGRATION \d+/\d+ ([a-f0-9]{64}) (success|failed|unavailable) .*", line)
        if not terminal:
            continue
        identity, status = terminal.groups()
        if identity in seen or identity not in inventory or records[identity]["status"] != status:
            raise ValueError("Native page attribution does not match the frozen journal")
        seen.add(identity)
        page_count = inventory[identity]["pages"]
        if status == "success":
            expected = 0 if records[identity]["success"]["reused_cache"] else page_count
            if pages != Counter({"complete": expected}):
                raise ValueError("A successful score lacks its exact fresh native page coverage")
        elif status == "unavailable" and pages:
            raise ValueError("A source orphan unexpectedly ran native inference")
        elif status == "failed" and (not pages or sum(pages.values()) > page_count or
                                     pages["failed"] > 1 or set(pages) - {"complete", "failed"}):
            raise ValueError("Failed-score native pages are not completely accounted")
        pages.clear()
    if seen != set(inventory) or pages:
        raise ValueError("Unattributed native pages or missing migration terminal records")


def audit() -> None:
    inventory = json.loads((ROOT / "inventory.json").read_text())
    journal = json.loads((ROOT / "journal.json").read_text())
    if journal["inventory_sha256"] != sha256(ROOT / "inventory.json") or journal["profile_sha256"] != inventory["profile_sha256"]:
        raise ValueError("Migration input/profile identity drift")
    if journal["executable_sha256"] != sha256(WORKSPACE / "dist/Sheet2Play.exe"):
        raise ValueError("Published executable changed after migration")
    if len(inventory["items"]) != 59 or sum(item["pages"] for item in inventory["items"]) != 266:
        raise ValueError("Selected private inventory count/pages changed")
    records = {entry["id"]: entry for entry in journal["entries"]}
    if set(records) != {item["id"] for item in inventory["items"]} or len(journal["entries"]) != len(records):
        raise ValueError("Migration accounting omitted or duplicated entries")
    counts = Counter(entry["status"] for entry in records.values())
    if counts["pending"] or sum(counts.values()) != 59 or set(counts) - {"success", "failed", "unavailable"}:
        raise ValueError("Migration is not fully accounted")
    mapped = {}
    reused = 0
    expected_native_pages = 0
    for item in inventory["items"]:
        old = library_path(item["old_manifest"])
        if sha256(old) != item["old_manifest_sha256"]:
            raise ValueError("Old426 manifest changed")
        midi = Path(str(old)[:-len(".cache.json")])
        if (sha256(midi) if midi.exists() else None) != item["old_midi_sha256"]:
            raise ValueError("Old426 MIDI changed")
        if item["source_relative_path"] and sha256(library_path(item["source_relative_path"])) != item["source_sha256"]:
            raise ValueError("Original retained source changed")
        entry = records[item["id"]]
        if entry["status"] == "failed" and (entry.get("error_code") not in
                {"NORMALIZATION_FAILED", "HOMR_INFERENCE_FAILED"} or not entry.get("error")):
            raise ValueError("Failed score has no ordinary model failure receipt")
        if (entry["status"] == "unavailable") != (item["source_relative_path"] is None):
            raise ValueError("Unavailable accounting does not match source inventory")
        if entry["status"] != "success":
            continue
        success = entry["success"]
        candidate_path = library_path(success["manifest"])
        candidate = json.loads(candidate_path.read_text())
        candidate_midi = Path(str(candidate_path)[:-len(".cache.json")])
        if sha256(candidate_path) != success["manifest_sha256"] or sha256(candidate_midi) != success["midi_sha256"]:
            raise ValueError("Committed candidate bytes changed")
        for key, expected in (("source_sha256", item["source_sha256"]), ("runtime_profile_sha256", inventory["profile_sha256"]),
                              ("model_revision", inventory["model_revision"]), ("engine_revision", inventory["engine_revision"]),
                              ("midi_sha256", success["midi_sha256"]), ("note_count", success["note_count"]), ("engine", "homr465")):
            if candidate.get(key) != expected:
                raise ValueError("Candidate identity or complete-score notes do not match")
        mapped[item["old_manifest"].replace("\\", "/")] = success["manifest"].replace("\\", "/")
        reused += bool(success["reused_cache"])
        if not success["reused_cache"]:
            expected_native_pages += item["pages"]
    before = [normalize_recent(row) for row in json.loads((ROOT / "recents-before.json").read_text())]
    after = [normalize_recent(row) for row in json.loads((LIBRARY / "recent.json").read_text())]
    expected_recents = [{**row, "manifest_relative_path": mapped[row["manifest_relative_path"]], "engine": "homr465"}
                        if row["engine"] == "homr" and row["manifest_relative_path"] in mapped else row for row in before]
    if expected_recents != after:
        raise ValueError("Recent references/order/timestamps do not match committed successes")
    if json.loads((ROOT / "settings-before.json").read_text()) != json.loads((LIBRARY / "settings.json").read_text()):
        raise ValueError("Migration changed saved settings")
    backup_records = json.loads((ROOT.parent / "phase2/installed-backup/metadata.json").read_text())
    for row in backup_records:
        if row["relative_path"].endswith(".cache.json") and sha256(library_path(row["relative_path"])) != row["sha256"]:
            raise ValueError("An existing cache manifest outside the migration changed")
    preserved = json.loads((ROOT.parent / "phase2/private-probe.json").read_text())["preserved"]
    preserved_count = 0
    for name, identity in preserved.items():
        path = Path(name).resolve()
        path.relative_to(LIBRARY)
        if path == LIBRARY / "recent.json":
            continue
        if sha256(path) != identity:
            raise ValueError("An original source, old cache or saved metadata file changed")
        preserved_count += 1
    native_count = 0
    native_statuses = Counter()
    receipt_folders = set()
    log = (ROOT / "jobs/library-migration/worker.log").read_text(errors="replace")
    verify_native_coverage(log, records, inventory["items"])
    for folder, status in re.findall(r"HOMR 465 receipt=([^\r\n]+?) status=(\w+)", log):
        if folder in receipt_folders:
            raise ValueError("Duplicate native receipt attribution")
        receipt_folders.add(folder)
        receipt = json.loads((Path(folder) / "native.json").read_text())
        if status not in {"complete", "failed"} or receipt["status"] != status or \
                receipt["runtime_profile_sha256"] != inventory["profile_sha256"] or \
                receipt["source_revision"] != inventory["engine_revision"] or receipt["model_revision"] != inventory["model_revision"]:
            raise ValueError("Native migration identity mismatch")
        if (status == "complete" and len(receipt["sessions"]) != 3) or not all(
                session["providers"][0] == "CUDAExecutionProvider" for session in receipt["sessions"]):
            raise ValueError("Native migration provider mismatch")
        source = WORKSPACE / "dist/Bridge/.runtime/homr-465/source"
        for origin in receipt["module_origins"].values():
            Path(origin).resolve().relative_to(source)
        native_statuses[status] += 1
        if status == "complete":
            native_count += 1
    if not counts["failed"] and native_count != expected_native_pages:
        raise ValueError("Completed native page receipts do not cover every fresh score")
    resume_log = (ROOT / "jobs/library-migration-resume/worker.log").read_text(errors="replace")
    resume_result = json.loads((ROOT / "jobs/library-migration-resume/result.json").read_text())
    if resume_result["status"] != "complete" or "HOMR 465 receipt=" in resume_log or \
            resume_log.count("success reused-journal") != counts["success"]:
        raise ValueError("Fresh-process resume did not validate every success without inference")
    save_new(ROOT / "audit.json", {"records": 59, "recoverable_scores": 57, "pages": 266,
        "counts": dict(counts), "reused_candidate_caches": reused, "native_completed_pages": native_count,
        "successful_score_pages": sum(item["pages"] for item in inventory["items"] if records[item["id"]]["status"] == "success"),
        "failed_score_pages": sum(item["pages"] for item in inventory["items"] if records[item["id"]]["status"] == "failed"),
        "expected_fresh_success_pages": expected_native_pages, "resume_without_inference": True,
        "native_status_counts": dict(native_statuses),
        "preserved_baseline_files": preserved_count,
        "old_caches_sources_preserved": True, "settings_preserved": True,
        "recents_order_timestamps_preserved": True, "recent_count": len(after),
        "inventory_sha256": sha256(ROOT / "inventory.json"), "journal_sha256": sha256(ROOT / "journal.json"),
        "physical_audio_tested": False})
    print(json.dumps({"counts": dict(counts), "pages": 266, "native_completed_pages": native_count,
                      "old_caches_sources_preserved": True, "settings_recents_preserved": True}))


if __name__ == "__main__":
    audit()
