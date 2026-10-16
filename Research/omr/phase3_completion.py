"""Finish the frozen Phase-3 record after its existing sequence exits."""
from __future__ import annotations

import argparse
import json
import math
import os
import time
from pathlib import Path
from typing import Any

import psutil

from phase3_freeze import verify_freeze, verify_secondary_audit
from phase3_sequence import _steps
from sheet2play_omr.adapter_contract import sha256_file


HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[1]
FREEZE = HERE / "reports/phase3/phase3-config-freeze-v1-89f385c8790b.json"
FREEZE_SHA256 = "3fdd3d76aeab4188244795ea7b5eb310b2129d8d50131290297aeb1a32020633"
STATE = HERE / ".runtime/phase3/sequence" / FREEZE_SHA256[:12] / "state.json"
REPORT = HERE / "reports/phase3/PHASE3_COMPLETION_REPORT.md"
HANDOFF = HERE / "PHASE3_HANDOFF.md"
CONTEXT = WORKSPACE / "CONTEXT.md"
PAGE_CANDIDATES = ("homr_page", "audiveris_page", "zeus_page")


def _json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def _state() -> dict[str, Any]:
    state = _json_object(STATE)
    expected = [step.name for step in _steps(FREEZE)]
    if (state.get("freeze_sha256") != FREEZE_SHA256
            or state.get("stage_order") != expected or len(expected) != 20):
        raise RuntimeError("Phase-3 sequence state differs from the frozen plan")
    if set(state.get("stages", {})) != set(expected):
        raise RuntimeError("Phase-3 sequence stage coverage changed")
    return state


def _sequence_status(state: dict[str, Any]) -> str:
    statuses = {name: state["stages"][name].get("status") for name in state["stage_order"]}
    if any(status == "failed" for status in statuses.values()):
        raise RuntimeError(f"Phase-3 stage failed: {[name for name, status in statuses.items() if status == 'failed']}")
    if any(status not in {"pending", "running", "complete"} for status in statuses.values()):
        raise RuntimeError("Phase-3 sequence has an unknown stage status")
    return "complete" if all(status == "complete" for status in statuses.values()) else "running"


def _watch_process(pid: int, created_at: float) -> None:
    try:
        process = psutil.Process(pid)
        if abs(process.create_time() - created_at) > 0.01 or not process.is_running():
            raise RuntimeError("Phase-3 sequence process identity changed or stopped")
    except psutil.NoSuchProcess as error:
        raise RuntimeError("Phase-3 sequence stopped before all stages completed") from error


def _summary(state: dict[str, Any], stage: str) -> tuple[dict[str, Any], Path, str]:
    entry = state["stages"][stage]
    if entry.get("status") != "complete" or not entry.get("summary_sha256"):
        raise RuntimeError(f"Phase-3 summary stage is incomplete: {stage}")
    path = Path(entry["summary"]).resolve()
    if not path.is_relative_to(WORKSPACE) or not path.is_file():
        raise RuntimeError(f"Phase-3 summary path is missing or outside workspace: {stage}")
    digest = sha256_file(path)
    if digest != entry["summary_sha256"]:
        raise RuntimeError(f"Phase-3 summary hash changed: {stage}")
    return _json_object(path), path, digest


def _validate_page(summary: dict[str, Any], collection: str, candidate: str,
                   expected_count: int, audit_sha256: str) -> None:
    if (summary.get("freeze_sha256") != FREEZE_SHA256
            or summary.get("reference_audit_sha256") != audit_sha256
            or summary.get("collection") != collection
            or summary.get("candidate") != candidate
            or summary.get("eligible_page_count") != expected_count
            or summary.get("scored_page_count") != expected_count
            or sum(summary.get("status_counts", {}).values()) != expected_count):
        raise RuntimeError(f"Incomplete Phase-3 page summary: {collection}/{candidate}")
    for name in ("pitch_f1", "onset_f1", "onset_duration_f1"):
        value = summary.get("composition_macro", {}).get(name)
        if not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
            raise RuntimeError(f"Invalid Phase-3 {name}: {collection}/{candidate}")


def _fmt(value: Any, digits: int = 4) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def _link(path: Path) -> str:
    return Path(os.path.relpath(path, REPORT.parent)).as_posix()


def _page_row(summary: dict[str, Any], path: Path) -> str:
    metrics = summary["composition_macro"]
    statuses = summary["status_counts"]
    duration = summary["duration_classification"]
    latency = summary["latency_seconds"]
    return (f"| `{summary['candidate']}` | {summary['scored_page_count']} | "
            f"{statuses.get('failed', 0)} | {_fmt(metrics['pitch_f1'])} | "
            f"{_fmt(metrics['onset_f1'])} | {_fmt(metrics['onset_duration_f1'])} | "
            f"{_fmt(summary['failure_penalized_omr_ned_mean'])} | "
            f"{_fmt(duration['macro_f1'])} | {_fmt(latency['median'], 1)} | "
            f"{_fmt(latency['p95'], 1)} | [summary]({_link(path)}) |")


def _write_same_or_new(path: Path, content: str) -> None:
    if path.exists():
        if path.read_text(encoding="utf-8") != content:
            raise FileExistsError(f"Refusing to overwrite a different Phase-3 report: {path}")
        return
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def _update_context() -> None:
    text = CONTEXT.read_text(encoding="utf-8")
    start = text.index("**Current recorded status:**")
    end = text.index("**Planned Phase 4 extension", start)
    replacement = (
        "**Current recorded status:** Historical Phases 1 and 2, the Phase 2R coordinate\n"
        "correction, and the reduced pretrained Phase 3 comparison are complete. The\n"
        "[Phase 3 completion report](Research/omr/reports/phase3/PHASE3_COMPLETION_REPORT.md)\n"
        "and [handoff](Research/omr/PHASE3_HANDOFF.md) contain the frozen evidence and\n"
        "limitations. Phase 4 fine-tuned evaluation has not started.\n\n"
    )
    updated = text[:start] + replacement + text[end:]
    if updated != text:
        CONTEXT.write_text(updated, encoding="utf-8")


def _update_handoff() -> None:
    text = HANDOFF.read_text(encoding="utf-8")
    notice = ("**Phase 3 complete:** All 20 frozen sequence stages completed and their\n"
              "summaries were rehashed. See the [completion report](reports/phase3/PHASE3_COMPLETION_REPORT.md).\n"
              "Phase 4 was not started.\n\n")
    if notice not in text:
        if "\n\n" not in text:
            raise RuntimeError("Phase-3 handoff has no insertion point")
        HANDOFF.write_text(text.replace("\n\n", "\n\n" + notice, 1), encoding="utf-8")


def finalize() -> Path:
    if sha256_file(FREEZE) != FREEZE_SHA256:
        raise RuntimeError("Phase-3 freeze hash changed")
    freeze = verify_freeze(FREEZE)
    audit = verify_secondary_audit()
    state = _state()
    if _sequence_status(state) != "complete":
        raise RuntimeError("Phase-3 sequence is not complete")
    for name in state["stage_order"]:
        entry = state["stages"][name]
        if entry.get("exit_code") != 0:
            raise RuntimeError(f"Phase-3 stage did not exit cleanly: {name}")
        if "summary" in entry:
            _summary(state, name)
    groups: dict[str, list[str]] = {"smb-pianoform": [], "smb-complete": []}
    for collection, prefix, count, audit_sha256 in (
        ("smb-pianoform", "primary", 402, freeze["reference_audit"]["sha256"]),
        ("smb-complete", "secondary", 611, audit["sha256"]),
    ):
        for candidate in PAGE_CANDIDATES:
            summary, path, _ = _summary(state, f"{prefix}_{candidate}_score")
            _validate_page(summary, collection, candidate, count, audit_sha256)
            groups[collection].append(_page_row(summary, path))
    olympic, olympic_path, _ = _summary(state, "olimpic_zeus_score")
    if (olympic.get("freeze_sha256") != FREEZE_SHA256
            or olympic.get("reference_audit_sha256") != freeze["olimpic_system_audit"]["sha256"]
            or olympic.get("eligible_system_count") != 100
            or sum(olympic.get("status_counts", {}).values()) != 100):
        raise RuntimeError("OLiMPiC system summary is incomplete")
    olympic_f1 = olympic.get("composition_macro", {}).get("onset_duration_f1")
    if not isinstance(olympic_f1, (int, float)) or not math.isfinite(olympic_f1) or not 0 <= olympic_f1 <= 1:
        raise RuntimeError("OLiMPiC system primary F1 is invalid")
    private_rows: list[str] = []
    for candidate in PAGE_CANDIDATES:
        private, path, _ = _summary(state, f"private_{candidate}_summarize")
        if (private.get("freeze_sha256") != FREEZE_SHA256
                or private.get("eligible_page_count") != 8
                or sum(private.get("status_counts", {}).values()) != 8):
            raise RuntimeError(f"Private diagnostic summary is incomplete: {candidate}")
        pitch_f1 = private.get("pitch_multiset_f1")
        if pitch_f1 is not None and (not isinstance(pitch_f1, (int, float))
                                     or not math.isfinite(pitch_f1) or not 0 <= pitch_f1 <= 1):
            raise RuntimeError(f"Private diagnostic pitch-count F1 is invalid: {candidate}")
        private_rows.append(f"| `{candidate}` | {private['status_counts'].get('failed', 0)} | "
                            f"{_fmt(private['pitch_multiset_f1'])} | [summary]({_link(path)}) |")
    lines = [
        "# Phase 3 reduced pretrained comparison — completion record", "",
        "The frozen 20-stage sequence completed. This report records descriptive Phase 3",
        "results only. It does not evaluate fine-tuned HOMR, apply the Phase 5 paired",
        "promotion gate, or claim the best engine across deferred candidates.", "",
        f"- Freeze SHA-256: `{FREEZE_SHA256}`.",
        "- Primary SMB audit: 402/402 valid; secondary SMB audit: 611/611 valid.",
        f"- Secondary audit SHA-256: `{audit['sha256']}`; "
        f"{audit['pedal_import_warning_count']} reviewed pedal-import warnings.",
        "- All eligible failures remain in the denominators; local cloud cost is $0.", "",
        "## Primary SMB pianoform pages", "",
        "| Candidate | Pages | Failed | Pitch F1 | Onset F1 | Pitch/onset/duration F1 | Penalized OMR-NED | Duration macro-F1 | Median s | P95 s | Evidence |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        *groups["smb-pianoform"], "",
        "## Secondary complete SMB pages", "",
        "This 611-page collection contains the primary 402 pages. Its additional pages",
        "extend coverage but do not provide an independent replication.", "",
        "| Candidate | Pages | Failed | Pitch F1 | Onset F1 | Pitch/onset/duration F1 | Penalized OMR-NED | Duration macro-F1 | Median s | P95 s | Evidence |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        *groups["smb-complete"], "",
        "## Separate annotated-system track", "",
        f"Zeus upstream was evaluated on 100 OLiMPiC systems: "
        f"{olympic['status_counts'].get('failed', 0)} failed; composition-macro "
        f"pitch/onset/duration F1 {_fmt(olympic['composition_macro']['onset_duration_f1'])}. "
        f"[System summary]({_link(olympic_path)}). This track is not a page comparison.", "",
        "## Already-inspected private diagnostic", "",
        "The eight-page diagnostic has no verified page-level timing split. The metric",
        "below is unaligned document-wide pitch-count F1 only.", "",
        "| Candidate | Failed pages | Pitch-count F1 | Evidence |",
        "| --- | ---: | ---: | --- |", *private_rows, "",
        "## Interpretation and limits", "",
        "- Each linked SMB page summary contains the full duration confusion matrix, majority baseline,",
        "  balanced accuracy, macro-F1, failure classes, feature breakdowns, and resource data.",
        "  A single-class duration predictor is flagged there; such a result is not evidence",
        "  of useful duration classification.",
        "- Valid-output OMR-NED and failure-penalized OMR-NED are separate in the summaries.",
        "  Any incomplete OMR-NED scoring is explicitly counted there.",
        "- Device-wide WDDM VRAM readings cannot establish the per-process practical gate.",
        "  Paired confidence intervals, multiple-comparison correction, practical ranking,",
        "  and a replacement decision belong to Phase 5 after Phase 4.",
        "- Rokot Q8, vanilla Qwen, LEGATO, HOMR PR #156, MuSViT, and fine-tuned HOMR",
        "  were not evaluated in this frozen reduced roster. They are not zero-scored.",
        "- The neutral Zeus page pipeline differs from the old app extractor. See the",
        "  [Phase 2R correction handoff](../../PHASE2R_CORRECTION_HANDOFF.md) for adapter",
        "  and integration attribution; no shipped runtime was changed in Phase 3.", "",
    ]
    _write_same_or_new(REPORT, "\n".join(lines))
    _update_handoff()
    _update_context()
    return REPORT


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wait-pid", type=int)
    parser.add_argument("--created-at", type=float)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if (args.wait_pid is None) != (args.created_at is None):
        parser.error("--wait-pid and --created-at must be supplied together")
    while True:
        state = _state()
        status = _sequence_status(state)
        if args.check:
            print(json.dumps({"status": status,
                              "complete_stages": sum(state["stages"][name]["status"] == "complete"
                                                     for name in state["stage_order"])}))
            return
        if status == "complete":
            report = finalize()
            print(json.dumps({"status": "complete", "report": str(report),
                              "report_sha256": sha256_file(report)}), flush=True)
            return
        if args.wait_pid is None:
            raise RuntimeError("Phase-3 sequence is still running; supply process identity to wait")
        _watch_process(args.wait_pid, args.created_at)
        time.sleep(60)


if __name__ == "__main__":
    main()
