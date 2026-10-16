"""Resumable Phase-2 rescoring of the 295 preserved screening outcomes."""
from __future__ import annotations

import argparse
from fractions import Fraction
import importlib.metadata
import json
from pathlib import Path
import time

import psutil

from phase3_score import _summary
from screening_common import (HERE, WORKSPACE, completed_path, digest, output_root, read_json,
                              result_identity, scored_path, verify_completed, write_new)
from screening_consolidated_report import ROSTER, outcome_counts
from screening_homr_statistics import paired_statistics
from screening_report import holm_adjust
import screening_score
import screening_cpu_score
from screening_stage1_preflight import resource_sample
from sheet2play_omr.adapter_contract import sha256_file
from sheet2play_omr.corrected_scoring import score_cached
from sheet2play_omr.timing import rational_time

BASE = HERE / "reports/screening/v1/2c98d5638c36/reports/consolidated-stage3-836fb923bb33/report.json"
BASE_HASH = "836fb923bb33dd496acd90c6eb229ca22fe7d87c3eb12b95bd6267cfd0305bec"


def verify_file(path: Path, expected: str) -> None:
    if sha256_file(path) != expected:
        raise ValueError(f"Evidence bytes changed: {path}")


def immutable(path: Path, payload: dict) -> None:
    if path.exists():
        if read_json(path) != payload:
            raise ValueError(f"Resumption identity differs: {path}")
    else:
        write_new(path, payload)


def policy_guard(started: float) -> dict:
    sample = resource_sample()
    if sample["admission_blockers"]:
        raise RuntimeError(f"90% resource admission blocked: {sample['admission_blockers']}")
    if time.monotonic() - started >= 4 * 3600 - 30:
        raise RuntimeError("Four-hour session limit; resume preserved scores in a new session")
    return sample


def source_identity(baseline: dict) -> dict:
    freeze_path = HERE / "reports/phase3/phase3-config-freeze-v1-89f385c8790b.json"
    freeze = read_json(freeze_path)
    for name, expected in freeze["research_source_sha256"].items():
        verify_file(HERE / name, expected)
    for name, version in freeze["scoring_versions"].items():
        if importlib.metadata.version(name) != version:
            raise ValueError(f"Scoring dependency version changed: {name}")
    for name, expected in baseline["analysis_source_sha256"].items():
        verify_file(HERE / name, expected)
    files = [Path(__file__), HERE / "src/sheet2play_omr/timing.py",
             HERE / "src/sheet2play_omr/corrected_scoring.py",
             HERE / "src/sheet2play_omr/metrics.py", HERE / "src/sheet2play_omr/phase3_scoring.py",
             HERE / "src/sheet2play_omr/omr_ned.py", HERE / "phase3_score.py",
             HERE / "screening_homr_statistics.py", HERE / "screening_report.py"]
    return {"schema_version": 1, "scope": "phase2_cached_shared_timing_repair",
            "baseline_report_sha256": sha256_file(BASE),
            "sample_sha256": baseline["sample_sha256"],
            "historical_freeze_sha256": sha256_file(freeze_path),
            "scoring_sources": {str(p.relative_to(WORKSPACE)): sha256_file(p) for p in files},
            "scoring_versions": freeze["scoring_versions"],
            "policy": "symmetric denominator limit 4096 within 8 binary64 ULPs; exact fractions retained",
            "matching": "exact pitch/onset/duration; no alignment, onset tolerance or time warping",
            "omr_ned": "reused only from verified original score identities and identical MusicXML bytes; frozen source and versions verified"}


def load_candidate(baseline: dict, name: str) -> tuple[dict, list[tuple]]:
    source = baseline["sources"][name]
    path = WORKSPACE / source["manifest"]
    verify_file(path, source["manifest_sha256"])
    manifest = read_json(path)
    config = source["configuration_sha256"]
    if (manifest["sample_sha256"] != baseline["sample_sha256"]
            or manifest["candidates"][name]["identity_sha256"] != config
            or len(manifest["items"]) != 59 or len(manifest["selected_groups"]) != 18):
        raise ValueError("Candidate sample/configuration differs")
    verify_file(WORKSPACE / source["summary"]["path"], source["summary"]["sha256"])
    summary = read_json(WORKSPACE / source["summary"]["path"])
    root = output_root(path)
    if (root / "worker.lock").exists():
        raise RuntimeError("Historical worker lock exists; inspect before running")
    runner = screening_cpu_score if name in {"zeus_page", "audiveris_page"} else screening_score
    records = []
    for item in manifest["items"]:
        result_dir = completed_path(root, name, item["id"], config)
        verify_file(result_dir / "result.json", source["result_sha256"][item["id"]])
        result = verify_completed(result_dir, result_identity(manifest, name, item))
        verify_file(WORKSPACE / item["reference_path"], item["reference_sha256"])
        score_dir = scored_path(root, name, item["id"], config, manifest["scorer_sha256"])
        verify_file(score_dir / "score.json", summary["item_score_sha256"][item["id"]])
        old = runner.verify_score(score_dir, runner.score_identity(manifest, name, item, result_dir / "result.json"))
        records.append((item, result, old, score_dir))
    return manifest, records


def timing_audit(result: dict, reference: dict) -> dict:
    changed, maximum, guarded = 0, Fraction(0), 0
    from sheet2play_omr.phase3_scoring import _artifact
    payloads = [reference]
    if result["status"] == "succeeded":
        payloads.append(read_json(_artifact(result, "canonical_events", WORKSPACE)))
    for payload in payloads:
        for note in payload["notes"]:
            for field in ("onset", "duration"):
                raw = Fraction(str(note[field]))
                value = rational_time(note[field])
                if value != raw:
                    changed += 1
                    maximum = max(maximum, abs(raw - value))
                guarded += value != raw.limit_denominator(4096)
    return {"reconstructed_values": changed, "maximum_change_quarter_notes": str(maximum),
            "values_preserved_beyond_unrestricted_policy": guarded}


def markdown(report: dict) -> str:
    lines = ["# Shared timing repair — Phase 2", "",
             "All 295 cached outcomes retained. Historical artifacts and scorer stay frozen.", "",
             "| Candidate | Historical primary F1 | Corrected primary F1 | Pitch/onset F1 | Pitch F1 | Failures |",
             "|---|---:|---:|---:|---:|---:|"]
    for name in ROSTER:
        summary = report["candidate_summaries"][name]
        metrics = summary["composition_macro"]
        lines.append(f"| {name} | {report['historical_primary_f1'][name]:.10f} | "
                     f"{metrics['onset_duration_f1']:.10f} | {metrics['onset_f1']:.10f} | "
                     f"{metrics['pitch_f1']:.10f} | {summary['status_counts'].get('failed', 0)} |")
    lines += ["", "Eight paired composition superiority claims use exact label swaps, 10,000 bootstrap "
              "resamples and Holm adjustment. Full intervals, p-values, sparse duration confusion matrices, "
              "majority baselines, balanced accuracy, macro-F1, missing/extra counts and runtime are in report.json.",
              "", "Chord completeness and notation-staff recall are in each page score; staff is not a validated hand label.",
              "", "OMR-NED is reused from verified score identities with unchanged XML inputs and frozen implementation/version pins. "
              "No new inference, playback, causal Zeus attribution, promotion or confirmation claim.", "",
              f"Holm-significant superiority claims: {report['significant_claims']}. "
              "This is a bounded-screen correction, not a new promotion decision.", ""]
    return "\n".join(lines)


def run(destination: Path) -> None:
    started = time.monotonic()
    policy_guard(started)
    baseline = read_json(BASE)
    if digest(baseline) != BASE_HASH or tuple(baseline["candidates"]) != ROSTER:
        raise ValueError("Canonical baseline report changed")
    identity = source_identity(baseline)
    destination.mkdir(parents=True, exist_ok=True)
    lock = destination / "worker.lock"
    with lock.open("x") as stream:
        stream.write(str(psutil.Process().pid))
    try:
        immutable(destination / "identity.json", {**identity, "identity_sha256": digest(identity)})
        rows, summaries, audits, preserved = {}, {}, {}, {}
        with (destination / "resources.jsonl").open("a", encoding="utf-8") as resources:
            for name in ROSTER:
                manifest, records = load_candidate(baseline, name)
                rows[name], audits[name], preserved[name] = [], {}, {}
                for index, (item, result, old, old_dir) in enumerate(records, 1):
                    resources.write(json.dumps(policy_guard(started)) + "\n")
                    resources.flush()
                    reference = read_json(WORKSPACE / item["reference_path"])
                    score = score_cached(result, reference, WORKSPACE, old)
                    audit = timing_audit(result, reference)
                    score["scoring_identity_sha256"] = digest(identity)
                    score["input_identity"] = {"result_sha256": baseline["sources"][name]["result_sha256"][item["id"]],
                                               "reference_sha256": item["reference_sha256"],
                                               "historical_score_sha256": sha256_file(old_dir / "score.json")}
                    path = destination / "scores" / name / (digest({"item": item["id"]})[:20] + ".json")
                    immutable(path, score)
                    rows[name].append(score)
                    audits[name][item["id"]] = audit
                    preserved[name][str(path.relative_to(destination))] = sha256_file(path)
                    print(f"{name}: {index}/59", flush=True)
                summaries[name] = _summary(rows[name], {i["id"]: i for i in manifest["items"]},
                                           {"training_overlap": baseline["candidate_summaries"][name]["training_overlap"]}, name)
                duration = summaries[name]["duration_classification"]
                labels = duration.get("labels", [])
                cells = {(cell["actual"], cell["predicted"]): cell["count"] for cell in duration["confusion_matrix"]}
                duration["matrix_rows_actual_columns_predicted"] = [[cells.get((actual, guess), 0)
                                                                      for guess in labels] for actual in labels]
        paired = {f"{name}_minus_{control}": paired_statistics(rows[name], rows[control],
                  baseline["statistics"]["bootstrap_seed"])
                  for control in ("homr_page", "fine_tuned_homr") for name in ROSTER if name != control}
        adjusted = holm_adjust({key: value["one_sided_superiority_p"] for key, value in paired.items()})
        for key, value in paired.items():
            value["holm_adjusted_superiority_p"] = adjusted[key]
        # Verify historical inputs again before committing the completed report.
        for name in ROSTER:
            load_candidate(baseline, name)
        report = {"schema_version": 2, "scoring_identity_sha256": digest(identity),
                  "candidate_summaries": summaries, "paired": paired, "timing_audit": audits,
                  "historical_primary_f1": {name: baseline["candidate_summaries"][name]["composition_macro"]["onset_duration_f1"] for name in ROSTER},
                  "sources": baseline["sources"], "score_hashes": preserved,
                  "statistics": baseline["statistics"], "pages": 59, "compositions": 18,
                  "outcome_counts": {name: outcome_counts(rows[name]) for name in ROSTER},
                  "significant_claims": [key for key, value in paired.items() if value["holm_adjusted_superiority_p"] < 0.05]}
        immutable(destination / "report.json", report)
        output = destination / "REPORT.md"
        content = markdown(report)
        if output.exists():
            if output.read_text(encoding="utf-8") != content:
                raise ValueError("Existing Markdown report differs")
        else:
            output.write_text(content, encoding="utf-8")
        immutable(destination / "report-sha256.json", {"sha256": sha256_file(destination / "report.json")})
    finally:
        lock.unlink()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output.resolve())
