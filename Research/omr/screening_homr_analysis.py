"""Analyze corrected HOMR scores against the preserved shipped control."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import statistics
from typing import Any
import uuid

from screening_common import (HERE, WORKSPACE, completed_path, digest, output_root,
                              read_json, rename_directory_with_retry, verify_manifest, write_new)
from screening_homr_statistics import paired_statistics
from screening_report import holm_adjust, verified_candidate
from screening_score import require_complete_results
from sheet2play_omr.adapter_contract import sha256_file


ROSTER = ("homr_page", "fine_tuned_homr", "homr_455")
SESSIONS = {"homr_page": "homr-screen-01", "fine_tuned_homr": "stage4-finetune-screen-01",
            "homr_455": "stage4-homr455-screen-01"}
RETIRED_455 = "cb45056ebb223f4bb82fc7b4eecd4f4fd28d5cd0a00b439bc00e8bde6537a99f"


def check_sample_agreement(current: dict[str, Any], control: dict[str, Any]) -> None:
    for key in ("sample_sha256", "items", "selected_groups", "scorer_sha256",
                "scoring_protocol_sha256", "seed"):
        if current[key] != control[key]:
            raise ValueError(f"Candidate/control frozen {key} differs")
    candidate = current["candidates"]["homr_455"]
    if candidate["identity_sha256"] == RETIRED_455:
        raise ValueError("Incompatible historical 455 configuration cannot be ranked")


def operation_evidence(root: Path, manifest: dict[str, Any], candidate: str) -> dict[str, Any]:
    config = manifest["candidates"][candidate]["identity_sha256"][:12]
    attempts = root / "attempts" / candidate / config
    samples = [read_json_line for path in attempts.rglob("resources.jsonl")
               for line in path.read_text(encoding="utf-8").splitlines()
               if (read_json_line := json.loads(line))]
    outcomes = [read_json(path) for path in attempts.rglob("outcome.json")]
    score_attempts = root / "score-attempts" / candidate / config
    score_samples = [json.loads(line) for path in score_attempts.rglob("resources.jsonl")
                     for line in path.read_text(encoding="utf-8").splitlines()]
    score_outcomes = [read_json(path) for path in score_attempts.rglob("outcome.json")]
    all_samples = samples + score_samples
    session = read_json(root / "sessions" / f"{SESSIONS[candidate]}.json")
    if session["active_since_utc"] is not None:
        raise ValueError(f"Candidate session remains active: {candidate}")
    return {"resource_policy": manifest["resource_policy"], "session": session,
            "inference_attempt_count": len(outcomes),
            "inference_interruption_count": sum(row.get("reason") is not None for row in outcomes),
            "scoring_attempt_count": len(score_outcomes),
            "scoring_interruption_count": sum(row.get("reason") is not None
                or row.get("exit_code") != 0 for row in score_outcomes),
            "inference_system_ram_percent_max": max((row["ram_percent"] for row in samples), default=None),
            "scoring_system_ram_percent_max": max((row["ram_percent"] for row in score_samples), default=None),
            "sampled_system_ram_percent_max": max((row["ram_percent"] for row in all_samples), default=None),
            "sampled_device_vram_mib_max": max((gpu["used_mib"] for row in all_samples
                                                for gpu in row["device_wide_gpu"] or []), default=None),
            "hardware_ram_bytes": samples[0]["ram_total_bytes"] if samples else None,
            "hardware_vram_mib": samples[0]["device_wide_gpu"][0]["total_mib"]
                if samples and samples[0]["device_wide_gpu"] else None,
            "timing_policy_comparability": "Historical control uses 75% RAM policy; corrected runs use 90%"}


def practical_evidence(summary: dict[str, Any], control: dict[str, Any],
                       operation: dict[str, Any], protocol: dict[str, Any]) -> dict[str, Any]:
    limits = protocol["practical_eligibility"]
    ram = summary["peak_ram_bytes_max"]
    vram = summary["peak_vram_bytes_max"]
    ram_fraction = ram / operation["hardware_ram_bytes"] if ram is not None else None
    vram_fraction = vram / (operation["hardware_vram_mib"] * 1048576) if vram is not None else None
    p95_ratio = summary["latency_seconds"]["p95"] / control["latency_seconds"]["p95"]
    checks = {"latency": p95_ratio <= limits["maximum_p95_page_latency_vs_homr"],
              "process_tree_ram": ram_fraction is not None and ram_fraction <= limits["maximum_peak_ram_fraction"],
              "device_wide_vram": vram_fraction is not None and vram_fraction <= limits["maximum_peak_vram_fraction"],
              "observed_unattended_screen": operation["inference_interruption_count"] == 0
                  and operation.get("scoring_interruption_count", 0) == 0
                  and operation["session"]["used_seconds"] < 14400}
    return {"frozen_limits": limits, "checks": checks, "observed_limits_pass": all(checks.values()),
            "process_tree_ram_fraction": ram_fraction, "device_wide_vram_fraction": vram_fraction,
            "p95_latency_ratio_vs_shipped": p95_ratio,
            "limits": "Observed bounded session only; timing policies differ; not proof of deployment readiness"}


def decision_evidence(summaries: dict[str, Any], paired: dict[str, Any]) -> dict[str, Any]:
    leader = max(summaries, key=lambda name: summaries[name]["composition_macro"]["onset_duration_f1"])
    interest = {}
    for name, summary in summaries.items():
        if name == "homr_page":
            continue
        comparison = paired[f"{name}_minus_homr_page"]
        positive = comparison["primary_f1_difference"] > 0
        supported = (comparison["bootstrap_95_percent_interval"][0] > 0
                     and comparison["holm_adjusted_superiority_p"] < 0.05)
        interest[name] = ("Merits untouched confirmation as a provisional HOMR challenger"
                          if positive and not summary["duration_classification"]["degenerate_single_class_predictor"]
                          else "No accuracy-led confirmation priority over shipped HOMR from this screen")
        if positive and not supported:
            interest[name] += "; point estimate improved but uncertainty remains"
    gate_checks = {}
    if "fine_tuned_homr" in summaries:
        baseline = summaries["fine_tuned_homr"]
        for name, summary in summaries.items():
            if name in {"homr_page", "fine_tuned_homr"}:
                continue
            difference = paired[f"{name}_minus_fine_tuned_homr"]
            gate_checks[name] = {
                "primary_gain_at_least_0.03": difference["primary_f1_difference"] >= 0.03,
                "statistical_support": difference["bootstrap_95_percent_interval"][0] > 0
                    and difference["holm_adjusted_superiority_p"] < 0.05,
                "pitch_loss_at_most_0.01": baseline["composition_macro"]["pitch_f1"]
                    - summary["composition_macro"]["pitch_f1"] <= 0.01,
                "failure_increase_at_most_0.01": summary["failure_rate"] - baseline["failure_rate"] <= 0.01,
                "penalized_ned_increase_at_most_0.01": summary["failure_penalized_omr_ned_mean"]
                    - baseline["failure_penalized_omr_ned_mean"] <= 0.01}
    return {"descriptive_primary_f1_leader": leader, "provisional_confirmation_interest": interest,
            "numerical_screen_gate_checks_vs_fine_tune": gate_checks,
            "production_decision": "Keep the installed shipped engine; no production replacement from this screen",
            "remaining_decision": "Consolidate Audiveris/Zeus first, then request any untouched confirmation separately",
            "not_established": ["Full-dataset ranking", "Training/evaluation disjointness",
                                "Absence of all conversion/stitching corruption", "Production promotion gate"]}


def build_analysis(current_path: Path, control_path: Path, candidates: list[str]) -> dict[str, Any]:
    if (not candidates or len(set(candidates)) != len(candidates) or "homr_page" not in candidates
            or any(candidate not in ROSTER for candidate in candidates)):
        raise ValueError("Analysis requires distinct HOMR candidates including shipped control")
    current, control = verify_manifest(current_path), verify_manifest(control_path)
    check_sample_agreement(current, control)
    root = output_root(current_path)
    if (root / "worker.lock").exists():
        raise RuntimeError("Candidate or scorer worker lock exists; do not analyze active work")
    all_rows, summaries, sources, operations = {}, {}, {}, {}
    for candidate in candidates:
        manifest = control if candidate == "homr_page" else current
        path = control_path if candidate == "homr_page" else current_path
        require_complete_results(root, manifest, candidate)
        all_rows[candidate], summaries[candidate], source = verified_candidate(root, manifest, candidate)
        sources[candidate] = {"manifest": str(path.relative_to(WORKSPACE)),
                              "manifest_sha256": sha256_file(path),
                              "configuration_sha256": manifest["candidates"][candidate]["identity_sha256"],
                              "summary": source,
                              "result_sha256": {item["id"]: sha256_file(completed_path(root, candidate,
                                  item["id"], manifest["candidates"][candidate]["identity_sha256"]) / "result.json")
                                  for item in manifest["items"]}}
        operations[candidate] = operation_evidence(root, manifest, candidate)
    paired = {f"{candidate}_minus_{baseline}": paired_statistics(all_rows[candidate], all_rows[baseline],
              int(current["seed"])) for baseline in ("homr_page", "fine_tuned_homr")
              if baseline in candidates for candidate in candidates if candidate != baseline}
    adjusted = holm_adjust({name: result["one_sided_superiority_p"] for name, result in paired.items()})
    for name, result in paired.items():
        result["holm_adjusted_superiority_p"] = adjusted[name]
    protocol = read_json(HERE / "reports/phase1/scoring-protocol.json")
    practical = {name: practical_evidence(summaries[name], summaries["homr_page"], operations[name], protocol)
                 for name in candidates}
    return {"schema_version": 1, "scope": "corrected_homr_only_stage4_bounded_screen",
            "sample_sha256": current["sample_sha256"], "pages": len(current["items"]),
            "compositions": len(current["selected_groups"]), "candidates": candidates,
            "candidate_summaries": summaries, "sources": sources, "paired": paired,
            "operations": operations, "practical": practical,
            "decision": decision_evidence(summaries, paired),
            "failed_pages": {name: [{"item_id": row["item_id"], "error": row["error"]}
                for row in rows if row["status"] == "failed"] for name, rows in all_rows.items()},
            "deferred": [name for name in ROSTER if name not in candidates] + ["Audiveris", "Zeus"],
            "excluded_historical_455_configuration": RETIRED_455,
            "training_overlap": "Fine-tune and 455 evaluation overlap is unknown; no disjoint-training claim",
            "statistics": {"bootstrap_resamples": 10000, "bootstrap_seed": int(current["seed"]),
                "unit": "composition mean of paired page F1 differences",
                "superiority": "Exact 2^18 paired composition label swaps, one-sided greater; Holm across reported claims",
                "reference": "https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.permutation_test.html",
                "historical_difference": "Earlier report's bootstrap-tail fraction was not a null-test p-value; not reused"},
            "confirmation_estimate": {name: {"untouched_pages": 343,
                "estimated_inference_and_scoring_seconds": operations[name]["session"]["used_seconds"] * 343 / 59,
                "minimum_four_hour_sessions": math.ceil(operations[name]["session"]["used_seconds"] * 343 / 59 / 14370),
                "basis": "Same-PC current session time per screened page; provisional, includes scoring"}
                for name in candidates},
            "promotion": "Not authorized; bounded screen is insufficient, and Audiveris/Zeus consolidation is pending",
            "analysis_source_sha256": {name: sha256_file(HERE / name) for name in (
                "screening_homr_analysis.py", "screening_homr_statistics.py", "screening_score.py", "screening_report.py")}}


def markdown(report: dict[str, Any]) -> str:
    def number(value: float | None, places: int = 4) -> str:
        return "unavailable" if value is None else f"{value:.{places}f}"

    lines = ["# Corrected HOMR-only Stage 4 report", "",
             f"{report['pages']} frozen pages in {report['compositions']} complete compositions.", "",
             "| Candidate | Pitch/onset/duration F1 | Onset F1 | Pitch F1 | Failures | Penalized OMR-NED |",
             "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for name, summary in report["candidate_summaries"].items():
        macro = summary["composition_macro"]
        lines.append(f"| {name} | {macro['onset_duration_f1']:.4f} | {macro['onset_f1']:.4f} | "
                     f"{macro['pitch_f1']:.4f} | {summary['status_counts'].get('failed', 0)}/59 | "
                     f"{number(summary['failure_penalized_omr_ned_mean'])} |")
    lines += ["", "## Paired composition evidence", "",
              "| Comparison | Primary F1 difference | 95% bootstrap interval | Holm-adjusted superiority p |",
              "| --- | ---: | ---: | ---: |"]
    for name, value in report["paired"].items():
        low, high = value["bootstrap_95_percent_interval"]
        lines.append(f"| {name} | {value['primary_f1_difference']:.4f} | [{low:.4f}, {high:.4f}] | "
                     f"{value['holm_adjusted_superiority_p']:.6f} |")
    lines += ["", "Intervals use 10,000 composition bootstrap resamples. Superiority uses all 262,144 "
              "paired composition label swaps under the exchangeable-label null, with Holm correction. "
              "The earlier bootstrap-tail fraction is not reused as a null-test p-value. "
              "[Method reference](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.permutation_test.html).", "",
              "## Duration, failures and operating evidence", ""]
    for name, summary in report["candidate_summaries"].items():
        duration = summary["duration_classification"]
        operation, practical = report["operations"][name], report["practical"][name]
        cold = summary["cold_start_seconds"]
        lines += [f"### {name}", "",
                  f"Duration balanced accuracy **{number(duration['balanced_accuracy'])}**, macro-F1 "
                  f"**{number(duration['macro_f1'])}**, majority baseline **{number(duration['majority_baseline_accuracy'])}**; "
                  f"single-class predictor: **{duration['degenerate_single_class_predictor']}**.", "",
                  f"Valid-output OMR-NED {number(summary['valid_output_omr_ned_mean'])} "
                  f"({summary['valid_output_omr_ned_count']} pages); complete failure penalties: "
                  f"{summary['failure_penalized_omr_ned_complete']}; scoring errors: {summary['omr_ned_scoring_error_count']}. "
                  f"Missing/extra notes: {summary['missing_note_count']}/{summary['extra_note_count']}. "
                  f"Typed failures: {summary['error_code_stage_counts']}.", "",
                  f"Page latency median/p95 **{number(summary['latency_seconds']['median'], 2)}/"
                  f"{number(summary['latency_seconds']['p95'], 2)} s**; cold workers: {len(cold)} "
                  f"(median {number(statistics.median(cold) if cold else None, 2)} s). Full session: "
                  f"**{operation['session']['used_seconds'] / 60:.1f} min** including scoring. "
                  f"System RAM observed maximum **{operation['sampled_system_ram_percent_max']}%** "
                  f"(inference {operation.get('inference_system_ram_percent_max')}%, "
                  f"scoring {operation.get('scoring_system_ram_percent_max')}%); "
                  f"device-wide VRAM **{operation['sampled_device_vram_mib_max']} MiB**. "
                  f"Admission/pressure RAM policy **{operation['resource_policy']['ram_admission_percent']}%**.", "",
                  f"Frozen practical-limit checks: {practical['checks']}. These use process-tree RAM "
                  "and device-wide VRAM; the separate system-RAM admission limit does not change the frozen "
                  "75% process-memory eligibility rule. Timing against the historical control is descriptive "
                  "because the admission policies differ.", ""]
    lines += ["## Feature breakdowns", "",
              "Subset F1 remains composition-macro; sparse subsets are descriptive.", "",
              "| Feature | Value | Pages | Candidate | Primary F1 |", "| --- | --- | ---: | --- | ---: |"]
    for name, summary in report["candidate_summaries"].items():
        for feature, values in summary["feature_breakdowns"].items():
            for value, metrics in values.items():
                lines.append(f"| {feature} | {value} | {metrics['page_count']} | {name} | "
                             f"{metrics['composition_macro_primary_f1']:.4f} |")
    lines += ["", "## Decision boundary", "",
              f"Descriptive primary-F1 leader: **{report['decision']['descriptive_primary_f1_leader']}**. "
              + report["decision"]["production_decision"] + ".", ""]
    for name, recommendation in report["decision"]["provisional_confirmation_interest"].items():
        lines += [f"- **{name}:** {recommendation}."]
    lines += ["", "Provisional untouched-remainder estimates (343 pages per candidate, inference plus scoring):", ""]
    for name, estimate in report["confirmation_estimate"].items():
        lines += [f"- **{name}:** {estimate['estimated_inference_and_scoring_seconds'] / 3600:.1f} hours, "
                  f"at least {estimate['minimum_four_hour_sessions']} bounded sessions. Same-PC screen throughput "
                  "is an estimate, not a scheduled job."]
    lines += ["",
              "The incompatible historical 455 configuration is excluded. Training overlap for the fine-tune "
              "and 455 remains unknown. Cross-staff coverage is unknown; no cross-staff accuracy claim follows.", "",
              "The complete duration confusion matrices, per-composition differences, failed-page IDs, "
              "source/result/score hashes, and runtime estimates are retained in [report.json](report.json). "
              "No predictions were aligned or shifted, repeats were not expanded, and sounding ties were merged "
              "under the frozen scorer.", "",
              "This is the HOMR-only decision input. Audiveris and Zeus are deferred; the consolidated engine "
              "decision remains pending. No confirmation run or production promotion is authorized by this report.", ""]
    return "\n".join(lines)


def publish(current: Path, control: Path, candidates: list[str]) -> Path:
    report = build_analysis(current, control, candidates)
    directory = output_root(current) / "reports" / f"homr-only-stage4-{digest(report)[:12]}"
    path = directory / "report.json"
    if path.exists():
        if read_json(path) != report or (directory / "REPORT.md").read_text(encoding="utf-8") != markdown(report):
            raise ValueError("Existing analysis report differs")
        return directory
    if directory.exists():
        raise ValueError("Incomplete analysis directory exists; preserve before recovery")
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
    parser.add_argument("--control-manifest", type=Path, required=True)
    parser.add_argument("--candidates", nargs="+", choices=ROSTER, default=list(ROSTER))
    args = parser.parse_args()
    path = publish(args.manifest.resolve(), args.control_manifest.resolve(), args.candidates)
    print(json.dumps({"report": str(path / "REPORT.md"), "json_sha256": sha256_file(path / "report.json")}))
