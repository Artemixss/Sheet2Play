"""Inventory recorded inference exposure; do not select or run confirmation."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


WORKSPACE = Path(__file__).resolve().parents[6]
RESEARCH = WORKSPACE / "Research/omr"
OUTPUT = Path(__file__).with_name("confirmation-exposure.json")
INPUTS = {
    "primary_manifest": RESEARCH / "reports/phase1/smb-pianoform.jsonl",
    "screening_manifest": RESEARCH / "reports/screening/v1/manifest-v5-607ff64134da.json",
    "stage1_recovery": RESEARCH / "reports/screening/stage1-20260926/recovery-v2/audit.json",
    "consolidated_stage3": RESEARCH / "reports/screening/v1/2c98d5638c36/reports/consolidated-stage3-836fb923bb33/report.json",
    "scoring_protocol": RESEARCH / "reports/phase1/scoring-protocol.json",
    "audit_source": Path(__file__).resolve(),
}


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def file_record(path: Path) -> dict[str, str | int]:
    data = path.read_bytes()
    return {"path": path.relative_to(WORKSPACE).as_posix(), "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def historical_inventory(recovery: dict[str, Any]) -> tuple[set[str], list[dict[str, Any]]]:
    completed = recovery["completed"]
    if recovery["corrupt"] or recovery["unexpected_reports"]:
        raise ValueError("Stage-1 recovery records unresolved corrupt or unexpected results")
    ids: set[str] = set()
    records: list[dict[str, Any]] = []
    for row in completed:
        report = WORKSPACE / row["report"]
        sidecar = report.with_suffix(".identity.json")
        report_record, sidecar_record = file_record(report), file_record(sidecar)
        if report_record["sha256"] != row["report_sha256"]:
            raise ValueError(f"Historical report changed: {report}")
        if sidecar_record["sha256"] != row["sidecar_sha256"]:
            raise ValueError(f"Historical identity changed: {sidecar}")
        identity = read_json(sidecar)
        if identity["item_id"] != row["item_id"] or row["item_id"] in ids:
            raise ValueError(f"Duplicate or mismatched historical item: {report}")
        ids.add(row["item_id"])
        records.append({"item_id": row["item_id"], "report": report_record,
                        "identity": sidecar_record})
    directory = RESEARCH / "reports/phase3/evaluation/smb-pianoform/homr_page"
    actual = {path for path in directory.glob("*.json")
              if not path.name.endswith(".identity.json")}
    if actual != {WORKSPACE / row["report"] for row in completed}:
        raise ValueError("Live historical HOMR inventory differs from recovery audit")
    return ids, records


def other_frozen_entry_inventory() -> tuple[set[str], list[dict[str, Any]]]:
    ids: set[str] = set()
    records: list[dict[str, Any]] = []
    for candidate in ("audiveris_page", "zeus_page"):
        directory = RESEARCH / "reports/phase3/evaluation/smb-pianoform" / candidate
        for path in sorted(directory.glob("*.identity.json")):
            identity = read_json(path)
            item_id = identity["item_id"]
            report = path.with_name(path.name.replace(".identity.json", ".json"))
            ids.add(item_id)
            records.append({"candidate": candidate, "item_id": item_id,
                            "report": file_record(report), "identity": file_record(path)})
    return ids, records


def partial_attempt_inventory(recovery: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in recovery["pending"]:
        if not (row["raw_directory_exists"] or row["orphan_sidecar"] or row["partial_files"]):
            continue
        report = WORKSPACE / row["report"]
        raw = RESEARCH / ".runtime/phase3/evaluation/smb-pianoform/homr_page" / report.stem
        files = [file_record(path) for path in sorted(raw.rglob("*")) if path.is_file()]
        if raw.is_dir() != row["raw_directory_exists"] or files != row["partial_files"]:
            raise ValueError(f"Recorded partial attempt changed: {raw}")
        if report.exists() or report.with_suffix(".identity.json").exists():
            raise ValueError(f"Pending historical attempt now has a report: {report}")
        records.append({"item_id": row["item_id"], "index": row["index"],
                        "raw_directory": raw.relative_to(WORKSPACE).as_posix(),
                        "raw_directory_exists": raw.is_dir(), "partial_files": files})
    return records


def runtime_estimates(report: dict[str, Any], pages: int) -> dict[str, Any]:
    estimates: dict[str, Any] = {}
    for candidate, operation in report["operations"].items():
        seconds = operation["session"]["used_seconds"] * pages / report["pages"]
        policy = operation["resource_policy"]
        budget = policy["session_seconds"] - policy["shutdown_reserve_seconds"]
        estimates[candidate] = {
            "pages": pages, "screened_pages": report["pages"],
            "observed_session_seconds": operation["session"]["used_seconds"],
            "estimated_inference_and_scoring_seconds": seconds,
            "estimated_hours": seconds / 3600,
            "minimum_four_hour_sessions_with_shutdown_reserve": math.ceil(seconds / budget),
            "basis": "linear observed same-PC inference-plus-scoring session throughput; descriptive only",
            "limitations": "different admission/execution contexts; holdout page complexity may differ; development/admission/preflight and extra retries not budgeted",
        }
    return estimates


def build_audit() -> dict[str, Any]:
    records = {name: file_record(path) for name, path in INPUTS.items()}
    screen, recovery, report = (read_json(INPUTS[key]) for key in
                                 ("screening_manifest", "stage1_recovery", "consolidated_stage3"))
    if records["primary_manifest"]["sha256"] != screen["frozen_primary_manifest_sha256"]:
        raise ValueError("Screening source differs from frozen primary manifest")
    if report["sample_sha256"] != screen["sample_sha256"]:
        raise ValueError("Consolidated report differs from screening sample")
    rows = [json.loads(line) for line in INPUTS["primary_manifest"].read_text(encoding="utf-8").splitlines()
            if line.strip()]
    groups: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        groups[row["composition_group"]].add(row["id"])
    all_ids = {row["id"] for row in rows}
    selected = {row["id"] for row in screen["items"]}
    selected_groups = set(screen["selected_groups"])
    if len(all_ids) != len(rows) or selected != set().union(*(groups[group] for group in selected_groups)):
        raise ValueError("Duplicate items or partial screening composition group")
    old, historical = historical_inventory(recovery)
    other, other_records = other_frozen_entry_inventory()
    partials = partial_attempt_inventory(recovery)
    partial_ids = {row["item_id"] for row in partials}
    completed_exposure = old | other
    recorded_exposure = completed_exposure | partial_ids
    if not recorded_exposure <= all_ids:
        raise ValueError("Exposure inventory contains non-primary items")
    remainder, remainder_groups = all_ids - selected, set(groups) - selected_groups
    exposed_groups = {group for group in remainder_groups if groups[group] & recorded_exposure}
    no_attempt_groups = remainder_groups - exposed_groups
    no_attempt_ids = set().union(*(groups[group] for group in no_attempt_groups))
    group_records = [{"composition_group": group, "page_count": len(groups[group]),
                      "item_ids": sorted(groups[group])} for group in sorted(no_attempt_groups)]
    partial_groups = [{"composition_group": group, "page_count": len(groups[group]),
                       "completed_old_pages": len(groups[group] & old),
                       "recorded_partial_pages": len(groups[group] & partial_ids),
                       "item_ids": sorted(groups[group])}
                      for group in sorted(remainder_groups)
                      if groups[group] & old and groups[group] - old]
    counts = {
        "primary_pages": len(all_ids), "primary_compositions": len(groups),
        "screening_pages": len(selected), "screening_compositions": len(selected_groups),
        "screening_remainder_pages": len(remainder), "screening_remainder_compositions": len(remainder_groups),
        "historical_homr_completed_pages": len(old), "historical_homr_screening_overlap_pages": len(old & selected),
        "historical_homr_remainder_overlap_pages": len(old & remainder),
        "remainder_compositions_with_completed_old_inference": sum(bool(groups[group] & old) for group in remainder_groups),
        "remainder_pages_without_completed_old_inference": len(remainder - old),
        "remainder_recorded_partial_attempt_pages": len(remainder & partial_ids),
        "remainder_compositions_with_any_recorded_inference_attempt": len(exposed_groups),
        "complete_remainder_compositions_without_recorded_inference_attempt": len(no_attempt_groups),
        "complete_remainder_pages_without_recorded_inference_attempt": len(no_attempt_ids),
    }
    if (counts["screening_remainder_pages"], counts["screening_remainder_compositions"]) != (screen["remainder_item_count"], screen["remainder_group_count"]):
        raise ValueError("Remainder inventory differs from frozen screening metadata")
    return {
        "schema_version": 1, "scope": "read-only Stage-4 recorded inference-exposure and runtime audit",
        "inputs": records, "sample_sha256": screen["sample_sha256"], "counts": counts,
        "historical_report_inventory": historical, "other_frozen_entry_inventory": other_records,
        "recorded_partial_attempts": partials, "partly_completed_remainder_compositions": partial_groups,
        "complete_remainder_compositions_without_recorded_inference_attempt": group_records,
        "no_recorded_attempt_page_count_strata": dict(sorted(Counter("1-2" if len(groups[group]) <= 2 else "3-4" if len(groups[group]) <= 4 else "5+" for group in no_attempt_groups).items())),
        "no_recorded_attempt_composer_group_counts": dict(sorted(Counter(group.split("/")[0] for group in no_attempt_groups).items())),
        "runtime_estimates": {"screening_remainder": runtime_estimates(report, len(remainder)),
                              "complete_groups_without_recorded_inference_attempt": runtime_estimates(report, len(no_attempt_ids))},
        "practical_evidence": report["practical"], "frozen_practical_requirements": read_json(INPUTS["scoring_protocol"])["practical_eligibility"],
        "limitations": [
            "343 pages are disjoint from the screening sample, not untouched by old inference.",
            "135 pages/44 full groups have no recorded old primary inference attempt in the inspected evidence; this is not proof of no human review or no training overlap.",
            "Reference building/auditing previously processed all 402 primary pages; this inventory concerns candidate-inference exposure only.",
            "The no-recorded-attempt inventory follows historical processing order and has composer imbalance; do not claim a representative random holdout.",
            "No future confirmation manifest was selected or frozen. A separate decision must preregister scope, identities, comparisons, multiplicity, and reuse policy.",
            "No prediction quality was inspected to derive exposure subsets; IDs, sidecars, immutable result hashes, and saved operation summaries determine this audit.",
        ],
        "conditional_options": [
            "Retain shipped HOMR; no accuracy-led full confirmation for 455, Audiveris, or Zeus is supported by this screen.",
            "If deciding between shipped and fine-tuned HOMR, optionally run a paired, preregistered confirmation on complete groups without recorded inference, with the composer/review/training limitations explicit.",
            "A 343-page extension is larger but partly previously inferred; report it as a screen-disjoint extension, not wholly untouched confirmation.",
            "For a genuinely independent confirmation across the target population, acquire a separately eligible and composition-disjoint external holdout with review/training overlap audited.",
        ],
        "execution_started": False,
    }


def main() -> None:
    result = build_audit()
    serialized = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if OUTPUT.exists() and OUTPUT.read_text(encoding="utf-8") != serialized:
        raise ValueError("Existing exposure audit differs; preserve it and version a new audit")
    if not OUTPUT.exists():
        temporary = OUTPUT.with_suffix(".json.tmp")
        temporary.write_text(serialized, encoding="utf-8")
        temporary.replace(OUTPUT)
    print(json.dumps({"output": file_record(OUTPUT), "counts": result["counts"],
                      "runtime_estimates": result["runtime_estimates"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
