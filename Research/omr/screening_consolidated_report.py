"""Consolidate the five canonical priority candidates across preserved manifests."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import uuid
from typing import Any

from screening_common import (HERE, WORKSPACE, completed_path, scored_path, digest, output_root,
                              read_json, write_new, rename_directory_with_retry)
from screening_cpu_manifest import verify_manifest
import screening_cpu_score as cpu_scores
from screening_score import require_complete_results
from screening_report import verified_candidate, holm_adjust
from screening_homr_statistics import paired_statistics
from screening_homr_analysis import (decision_evidence, practical_evidence,
                                    operation_evidence as homr_operation, markdown as homr_markdown)
from sheet2play_omr.adapter_contract import sha256_file

ROSTER = ("homr_page", "fine_tuned_homr", "homr_455", "audiveris_page", "zeus_page")
HOMR_REPORT = HERE / "reports/screening/v1/2c98d5638c36/reports/homr-only-stage4-e35f73ca9f75/report.json"
HOMR_SHA256 = "d2a8d0a48bc3eb7cc929f8969ae38449b58565ef98f32fc22b8b892c63a0e5eb"
CPU_SESSIONS = {"audiveris_page": "stage3-audiveris-screen-01", "zeus_page": "stage3-zeus-screen-01"}


def same_sample(left: dict[str, Any], right: dict[str, Any]) -> None:
    for key in ("sample_sha256", "items", "selected_groups", "seed", "selection_algorithm",
                "scorer_sha256", "scoring_summary_sha256", "scoring_protocol_sha256",
                "historical_phase3_freeze_sha256"):
        if left[key] != right[key]:
            raise ValueError(f"Cross-manifest frozen contract differs: {key}")


def verified_cpu_score(path: Path, identity: dict[str, Any]) -> dict[str, Any]:
    if read_json(path / "identity.json") != identity:
        raise ValueError(f"CPU score requires its exact pinned runner identity: {path}")
    return cpu_scores.verify_score(path, identity)


def outcome_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    failed = [row for row in rows if row["status"] == "failed"]
    codes = [row["error"]["code"].upper() for row in failed]
    return {"completed": len(rows), "succeeded": len(rows) - len(failed), "failed": len(failed),
            "successful_empty_output": sum(row["status"] == "succeeded" and row["predicted_note_count"] == 0
                                           for row in rows),
            "typed_empty_output": sum("EMPTY" in code for code in codes),
            "typed_invalid_output": sum("INVALID" in code for code in codes),
            "typed_timeout": sum("TIMEOUT" in code for code in codes),
            "omr_ned_scoring_error": sum(row["omr_ned_status"] == "scoring_error" for row in rows)}


def cpu_candidate(root: Path, manifest: dict[str, Any], name: str) -> tuple[list, dict, dict]:
    require_complete_results(root, manifest, name)
    config = manifest["candidates"][name]["identity_sha256"]
    rows, hashes = [], {}
    for item in manifest["items"]:
        result = completed_path(root, name, item["id"], config) / "result.json"
        path = scored_path(root, name, item["id"], config, manifest["scorer_sha256"])
        rows.append(verified_cpu_score(path, cpu_scores.score_identity(manifest, name, item, result)))
        hashes[item["id"]] = sha256_file(path / "score.json")
    summaries = list((root / "summaries" / name / config[:12]).glob("summary-*.json"))
    if len(summaries) != 1:
        raise ValueError(f"Expected one immutable complete summary: {name}")
    path = summaries[0]
    summary = read_json(path)
    if (summary.get("item_score_sha256") != hashes or summary.get("scored_page_count") != 59
            or summary.get("composition_count") != 18 or summary.get("configuration_sha256") != config
            or summary.get("sample_sha256") != manifest["sample_sha256"]):
        raise ValueError(f"CPU summary identity/coverage differs: {name}")
    return rows, summary, {"path": str(path.relative_to(WORKSPACE)), "sha256": sha256_file(path)}


def cpu_operation(root: Path, manifest: dict[str, Any], name: str) -> dict[str, Any]:
    config = manifest["candidates"][name]["identity_sha256"][:12]
    def evidence(directory: str) -> tuple[list, list]:
        base = root / directory / name / config
        samples = [json.loads(line) for path in base.rglob("resources.jsonl")
                   for line in path.read_text(encoding="utf-8").splitlines()]
        return samples, [read_json(path) for path in base.rglob("outcome.json")]
    inference, outcomes = evidence("attempts")
    scoring, score_outcomes = evidence("score-attempts")
    session = read_json(root / "sessions" / f"{CPU_SESSIONS[name]}.json")
    if session["active_since_utc"] is not None or not inference:
        raise ValueError(f"CPU session active or resource evidence missing: {name}")
    samples = inference + scoring
    return {"resource_policy": manifest["resource_policy"], "session": session,
        "inference_attempt_count": len(outcomes), "scoring_attempt_count": len(score_outcomes),
        "inference_interruption_count": sum(row.get("reason") is not None for row in outcomes),
        "scoring_interruption_count": sum(row.get("reason") is not None or row.get("exit_code") != 0
                                           for row in score_outcomes),
        "inference_system_ram_percent_max": max(row["ram_percent"] for row in inference),
        "scoring_system_ram_percent_max": max((row["ram_percent"] for row in scoring), default=None),
        "sampled_system_ram_percent_max": max(row["ram_percent"] for row in samples),
        "sampled_device_vram_mib_max": max((gpu["used_mib"] for row in samples
                                             for gpu in row["device_wide_gpu"] or []), default=None),
        "hardware_ram_bytes": inference[0]["ram_total_bytes"],
        "hardware_vram_mib": inference[0]["device_wide_gpu"][0]["total_mib"]
            if inference[0]["device_wide_gpu"] else None,
        "execution_context": "fully_readable_local",
        "timing_policy_comparability": "Historical control uses 75% admission; new candidates 90%; CPU execution context differs"}


def build_report(path: Path) -> dict[str, Any]:
    manifest = verify_manifest(path)
    root = output_root(path)
    if (root / "worker.lock").exists():
        raise RuntimeError("Inference/scorer lock exists; do not consolidate active work")
    if sha256_file(HOMR_REPORT) != HOMR_SHA256:
        raise ValueError("Preserved HOMR-only report changed")
    historical = read_json(HOMR_REPORT)
    for name, expected in historical["analysis_source_sha256"].items():
        if sha256_file(HERE / name) != expected:
            raise ValueError(f"Preserved HOMR analysis source changed: {name}")
    rows, summaries, sources, operations = {}, {}, {}, {}
    for name in ROSTER:
        source_path = path
        source_manifest = manifest
        if name in historical["candidates"]:
            source = historical["sources"][name]
            source_path = WORKSPACE / source["manifest"]
            if sha256_file(source_path) != source["manifest_sha256"]:
                raise ValueError(f"Preserved HOMR manifest changed: {name}")
            source_manifest = read_json(source_path)
            same_sample(manifest, source_manifest)
            identity = source_manifest["candidates"][name]
            if digest(identity["identity"]) != identity["identity_sha256"]:
                raise ValueError(f"Historical candidate identity differs: {name}")
            for file, expected in identity["identity"]["source_files"].items():
                if sha256_file(WORKSPACE / file) != expected:
                    raise ValueError(f"Historical candidate source changed: {file}")
            require_complete_results(root, source_manifest, name)
            rows[name], summaries[name], summary_source = verified_candidate(root, source_manifest, name)
            if summary_source != source["summary"]:
                raise ValueError(f"Preserved summary changed: {name}")
            operations[name] = homr_operation(root, source_manifest, name)
        else:
            rows[name], summaries[name], summary_source = cpu_candidate(root, manifest, name)
            operations[name] = cpu_operation(root, manifest, name)
        config = source_manifest["candidates"][name]["identity_sha256"]
        sources[name] = {"manifest": str(source_path.relative_to(WORKSPACE)),
                        "manifest_sha256": sha256_file(source_path), "configuration_sha256": config,
                        "summary": summary_source, "result_sha256": {item["id"]: sha256_file(
                            completed_path(root, name, item["id"], config) / "result.json")
                            for item in manifest["items"]}}
    paired = {f"{name}_minus_{baseline}": paired_statistics(rows[name], rows[baseline], int(manifest["seed"]))
              for baseline in ("homr_page", "fine_tuned_homr") for name in ROSTER if name != baseline}
    adjusted = holm_adjust({name: value["one_sided_superiority_p"] for name, value in paired.items()})
    for name, value in paired.items():
        value["holm_adjusted_superiority_p"] = adjusted[name]
    protocol = read_json(HERE / "reports/phase1/scoring-protocol.json")
    practical = {name: practical_evidence(summaries[name], summaries["homr_page"], operations[name], protocol)
                 for name in ROSTER}
    decision = decision_evidence(summaries, paired)
    decision["remaining_decision"] = "Stop for a separate decision before untouched confirmation or Stage 5 work"
    for name in ("audiveris_page", "zeus_page"):
        if not practical[name]["observed_limits_pass"]:
            decision["provisional_confirmation_interest"][name] += "; current practical-limit checks fail"
    return {"schema_version": 1, "scope": "consolidated_canonical_stage3_bounded_screen",
        "sample_sha256": manifest["sample_sha256"], "pages": 59, "compositions": 18,
        "candidates": list(ROSTER), "candidate_summaries": summaries, "sources": sources,
        "operations": operations, "practical": practical, "paired": paired, "decision": decision,
        "outcome_counts": {name: outcome_counts(values) for name, values in rows.items()},
        "failed_pages": {name: [{"item_id": row["item_id"], "error": row["error"]}
                                 for row in values if row["status"] == "failed"] for name, values in rows.items()},
        "excluded_historical_455_configuration": historical["excluded_historical_455_configuration"],
        "deferred": {"qwen": "current complete-page readiness failed", "rokot": "bounded development remedy deferred",
                     "legato": "recognition runtime unavailable", "musvit": "verified decoder/checkpoint unavailable",
                     "homr_465_multi_voice": "PR #156 merged and weights published; local matching source/weights/vocabulary/decoder and development admission remain unverified", "homr_combined": "compatibility unverified"},
        "statistics": {**historical["statistics"], "superiority_claim_count": len(paired),
                       "multiple_testing": "Holm across all eight reported superiority claims"},
        "confirmation_estimate": {name: {"untouched_pages": 343,
            "estimated_inference_and_scoring_seconds": operations[name]["session"]["used_seconds"] * 343 / 59,
            "minimum_four_hour_sessions": math.ceil(operations[name]["session"]["used_seconds"] * 343 / 59 / 14370),
            "basis": "Observed same-PC session time per screened page, including scoring; provisional and execution contexts differ"}
            for name in ROSTER},
        "runtime_inventory_disclosure": "CPU v5 pins fully readable inventory; historical inventory omitted 33 metadata entries. Existing versions, sources, models, parser and scoring contracts match; no historical rewrite or dependency installation occurred",
        "zeus_route": "Neutral CPU recognizer with existing GPU HOMR detector; direct app extractor is excluded",
        "training_overlap": {name: summary["training_overlap"] for name, summary in summaries.items()},
        "promotion": "Not authorized; bounded screen and practical observations do not satisfy promotion",
        "analysis_source_sha256": {name: sha256_file(HERE / name) for name in (
            "screening_consolidated_report.py", "screening_homr_analysis.py", "screening_homr_statistics.py",
            "screening_score.py", "screening_cpu_score.py", "screening_cpu_manifest.py", "screening_cpu_profile.py")}}


def markdown(report: dict[str, Any]) -> str:
    text = homr_markdown(report).replace("# Corrected HOMR-only Stage 4 report", "# Consolidated canonical Stage 3 screening report")
    text = text.replace("This is the HOMR-only decision input. Audiveris and Zeus are deferred; the consolidated engine "
                        "decision remains pending. No confirmation run or production promotion is authorized by this report.",
                        "All five priority candidates are included. Canonical Stage 3 is complete. Stop for a separate "
                        "confirmation decision; no confirmation, training or production promotion is authorized.")
    text = text.replace("## Duration, failures and operating evidence\n", "## Duration, failures and operating evidence\n\n"
                        "Duration diagnostics condition on matched pitch/onset notes; full sparse confusion matrices "
                        "and majority-baseline macro-F1 are in report.json. Headline scores retain all failed/unmatched notes.\n")
    text += "\n" + report["runtime_inventory_disclosure"] + ".\n\n" + report["zeus_route"] + ".\n"
    text += "\nOutcome counts retain successful empty outputs separately; typed empty/invalid/timeout " \
            "counts use the saved engine error codes. Generic failures retain their original stage/code.\n"
    for name, counts in report["outcome_counts"].items():
        text += f"\n- **{name}:** {counts}.\n"
    text += "\nDeferred configurations: " + "; ".join(f"{name}: {reason}" for name, reason in report["deferred"].items()) + ".\n"
    return text


def publish(path: Path) -> Path:
    report = build_report(path)
    directory = output_root(path) / "reports" / f"consolidated-stage3-{digest(report)[:12]}"
    if directory.exists():
        if read_json(directory / "report.json") != report or (directory / "REPORT.md").read_text(encoding="utf-8") != markdown(report):
            raise ValueError("Existing consolidated report differs")
        return directory
    directory.parent.mkdir(parents=True, exist_ok=True)
    temporary = directory.parent / f".{directory.name}.{uuid.uuid4().hex}.tmp"
    temporary.mkdir()
    write_new(temporary / "report.json", report)
    (temporary / "REPORT.md").write_text(markdown(report), encoding="utf-8")
    rename_directory_with_retry(temporary, directory)
    return directory


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    result = publish(args.manifest.resolve())
    print(json.dumps({"report": str(result / "REPORT.md"), "sha256": sha256_file(result / "report.json")}))
