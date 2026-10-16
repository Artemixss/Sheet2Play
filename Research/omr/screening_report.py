"""Create a bounded screening report from complete, verified score sets."""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import random
import statistics
from typing import Any
import uuid

from screening_common import (WORKSPACE, digest, output_root, read_json, scored_path,
                              verify_manifest, write_new)
from screening_score import score_identity, verify_score
from screening_common import completed_path
from sheet2play_omr.adapter_contract import sha256_file


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    low, high = math.floor(position), math.ceil(position)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def paired_difference(left: list[dict[str, Any]], right: list[dict[str, Any]],
                      seed: int, resamples: int = 10000) -> dict[str, Any]:
    if resamples < 1:
        raise ValueError("Bootstrap requires positive resamples")
    by_left = {row["item_id"]: row for row in left}
    by_right = {row["item_id"]: row for row in right}
    if len(by_left) != len(left) or len(by_right) != len(right) or set(by_left) != set(by_right):
        raise ValueError("Paired candidate item sets differ or contain duplicates")
    groups: dict[str, list[float]] = defaultdict(list)
    for item_id, row in by_left.items():
        other = by_right[item_id]
        if row["composition_group"] != other["composition_group"]:
            raise ValueError("Paired composition identity differs")
        groups[row["composition_group"]].append(
            row["onset_duration_f1"] - other["onset_duration_f1"])
    group_values = [statistics.mean(values) for _, values in sorted(groups.items())]
    count = len(group_values)
    if count != 18:
        raise ValueError("Screening comparison requires 18 composition groups")
    rng = random.Random(seed)
    bootstrap = [statistics.mean(rng.choices(group_values, k=count)) for _ in range(resamples)]
    return {"composition_count": count, "page_count": len(left),
            "primary_f1_difference": statistics.mean(group_values),
            "bootstrap_95_percent_interval": [percentile(bootstrap, 0.025),
                                               percentile(bootstrap, 0.975)],
            "one_sided_superiority_p": (1 + sum(value <= 0 for value in bootstrap)) / (resamples + 1),
            "bootstrap_seed": seed, "bootstrap_resamples": resamples}


def holm_adjust(p_values: dict[str, float]) -> dict[str, float]:
    ordered = sorted(p_values, key=lambda key: (p_values[key], key))
    adjusted, previous = {}, 0.0
    for index, name in enumerate(ordered):
        previous = max(previous, min(1.0, (len(ordered) - index) * p_values[name]))
        adjusted[name] = previous
    return adjusted


def verified_candidate(root: Path, manifest: dict[str, Any], candidate: str):
    available = manifest["candidates"].get(candidate)
    if available is None or available["identity"] is None:
        raise ValueError(f"Candidate is not admitted in this manifest: {candidate}")
    rows = []
    hashes = {}
    config_sha256 = available["identity_sha256"]
    for item in manifest["items"]:
        score_path = scored_path(root, candidate, item["id"], config_sha256,
                                 manifest["scorer_sha256"])
        if not score_path.is_dir():
            raise RuntimeError(f"Candidate score is incomplete: {candidate} {item['id']}")
        result = completed_path(root, candidate, item["id"], config_sha256) / "result.json"
        identity = score_identity(manifest, candidate, item, result)
        rows.append(verify_score(score_path, identity))
        hashes[item["id"]] = sha256_file(score_path / "score.json")
    matching = []
    for path in (root / "summaries" / candidate / config_sha256[:12]).glob("summary-*.json"):
        saved = read_json(path)
        if (saved.get("sample_sha256") == manifest["sample_sha256"] and
                saved.get("configuration_sha256") == available["identity_sha256"]):
            matching.append((path, saved))
    if len(matching) != 1:
        raise ValueError(f"Expected one immutable summary for {candidate}; found {len(matching)}")
    path, summary = matching[0]
    if (summary.get("item_score_sha256") != hashes or
            summary.get("scored_page_count") != len(manifest["items"]) or
            summary.get("composition_count") != 18):
        raise ValueError(f"Candidate summary is incomplete or changed: {candidate}")
    return rows, summary, {"path": str(path.relative_to(WORKSPACE)), "sha256": sha256_file(path)}


def build_report(manifest: dict[str, Any], root: Path, candidates: list[str],
                 kind: str) -> dict[str, Any]:
    if not candidates or len(candidates) != len(set(candidates)):
        raise ValueError("Report needs distinct completed candidates")
    if "homr_page" not in candidates:
        raise ValueError("Shipped HOMR control is required in every screening report")
    if kind == "interim-homr" and any(name not in {"homr_page", "fine_tuned_homr", "homr_455"}
                                      for name in candidates):
        raise ValueError("Interim report contains a non-HOMR candidate")
    all_rows, summaries, sources = {}, {}, {}
    for candidate in candidates:
        all_rows[candidate], summaries[candidate], sources[candidate] = verified_candidate(
            root, manifest, candidate)
    paired = {}
    for baseline in ("homr_page", "fine_tuned_homr"):
        if baseline not in candidates:
            continue
        for candidate in candidates:
            if candidate == baseline:
                continue
            key = f"{candidate}_minus_{baseline}"
            paired[key] = paired_difference(all_rows[candidate], all_rows[baseline],
                                            int(manifest["seed"]))
    adjusted = holm_adjust({key: value["one_sided_superiority_p"] for key, value in paired.items()})
    for key, value in paired.items():
        value["holm_adjusted_superiority_p"] = adjusted[key]
    return {"schema_version": 1, "scope": kind, "sample_sha256": manifest["sample_sha256"],
            "manifest_sha256": digest(manifest), "selected_pages": len(manifest["items"]),
            "selected_compositions": len(manifest["selected_groups"]),
            "candidates": candidates, "candidate_summaries": summaries,
            "summary_sources": sources, "paired": paired,
            "missing_or_deferred_candidates": {
                name: value["status"] for name, value in manifest["candidates"].items()
                if name not in candidates},
            "interpretation": "Bounded screen only; no full-dataset ranking or production promotion",
            "latency_provenance": "Current screening sessions only; historical inference timings excluded"}


def markdown(report: dict[str, Any]) -> str:
    lines = ["# Bounded OMR screening report", "",
             f"Scope: {report['scope']}; {report['selected_pages']} pages in "
             f"{report['selected_compositions']} complete compositions.", "",
             "| Candidate | Pitch+onset+duration F1 | Pitch+onset F1 | Pitch F1 | Failure rate | Failure-penalized OMR-NED |",
             "| --- | ---: | ---: | ---: | ---: | ---: |"]

    def number(value: float | None) -> str:
        return "unavailable" if value is None else f"{value:.4f}"

    for name in report["candidates"]:
        value = report["candidate_summaries"][name]
        metrics = value["composition_macro"]
        lines.append(f"| {name} | {number(metrics['onset_duration_f1'])} | "
                     f"{number(metrics['onset_f1'])} | {number(metrics['pitch_f1'])} | "
                     f"{number(value['failure_rate'])} | "
                     f"{number(value['failure_penalized_omr_ned_mean'])} |")
    lines.extend(["", "## Failure, duration, and operating evidence", ""])
    for name in report["candidates"]:
        value = report["candidate_summaries"][name]
        duration = value["duration_classification"]
        latency = value["latency_seconds"]
        lines.extend([f"### {name}", "",
                      f"Statuses: {value['status_counts']}. Typed error stages: "
                      f"{value['error_code_stage_counts']}.", "",
                      f"OMR-NED: {value['valid_output_omr_ned_count']} valid outputs; "
                      f"{value['failure_penalized_omr_ned_count']} penalized values; "
                      f"{value['omr_ned_scoring_error_count']} scoring errors. "
                      f"Complete penalized metric: {value['failure_penalized_omr_ned_complete']}.", "",
                      f"Missing/extra notes: {value['missing_note_count']}/{value['extra_note_count']}. "
                      f"Duration balanced accuracy {number(duration['balanced_accuracy'])}, "
                      f"macro-F1 {number(duration['macro_f1'])}, majority baseline "
                      f"{number(duration['majority_baseline_accuracy'])}; "
                      f"degenerate single-class predictor: "
                      f"{duration['degenerate_single_class_predictor']}.", "",
                      "Duration confusion matrix (actual, predicted, count): "
                      f"{duration['confusion_matrix']}.", "",
                      f"Comparable session latency median/p95: "
                      f"{number(latency['median'])}/{number(latency['p95'])} s "
                      f"({latency['comparable_page_count']} pages); "
                      f"{latency['excluded_noncomparable_page_count']} excluded from timing. "
                      f"Peak process-tree RAM {value['peak_ram_bytes_max']} bytes; "
                      f"peak sampled device-wide VRAM {value['peak_vram_bytes_max']} bytes.", "",
                      f"Training overlap disclosure: {value['training_overlap']}.", ""])
    lines.extend(["", "## Paired composition differences", ""])
    if report["paired"]:
        lines.extend(["| Comparison | F1 difference | 95% bootstrap interval | Holm-adjusted superiority p |",
                      "| --- | ---: | ---: | ---: |"])
        for name, value in report["paired"].items():
            low, high = value["bootstrap_95_percent_interval"]
            lines.append(f"| {name} | {value['primary_f1_difference']:.4f} | "
                         f"[{low:.4f}, {high:.4f}] | {value['holm_adjusted_superiority_p']:.4f} |")
    else:
        lines.append("No paired comparison is available with the completed roster.")
    lines.extend(["", "## Limits", "",
                  "This sample is a screen with limited power for small differences. "
                  "No production promotion follows from it.",
                  "Device-wide VRAM readings are not per-process usage. "
                  "Timing excludes historical runs.", "",
                  "Missing or deferred candidates are recorded in the accompanying JSON report.", ""])
    return "\n".join(lines)


def report(manifest_path: Path, candidates: list[str], kind: str) -> Path:
    manifest = verify_manifest(manifest_path)
    root = output_root(manifest_path)
    if (root / "worker.lock").exists():
        raise RuntimeError("A candidate or scorer worker lock exists; inspect before reporting")
    result = build_report(manifest, root, candidates, kind)
    directory = root / "reports" / f"{kind}-{digest(result)[:12]}"
    directory.parent.mkdir(parents=True, exist_ok=True)
    if directory.exists():
        if read_json(directory / "report.json") != result:
            raise ValueError("Existing screening report differs")
        return directory
    temporary = directory.parent / f".{directory.name}.{uuid.uuid4().hex}.tmp"
    temporary.mkdir()
    try:
        write_new(temporary / "report.json", result)
        (temporary / "REPORT.md").write_text(markdown(result), encoding="utf-8")
        temporary.rename(directory)
    finally:
        if temporary.exists():
            for path in temporary.iterdir():
                path.unlink()
            temporary.rmdir()
    return directory


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--kind", choices=("interim-homr", "consolidated"), required=True)
    parser.add_argument("--candidates", nargs="+", required=True)
    args = parser.parse_args()
    path = report(args.manifest.resolve(), args.candidates, args.kind)
    print(json.dumps({"report": str(path / "REPORT.md"),
                      "report_json_sha256": sha256_file(path / "report.json")}))


if __name__ == "__main__":
    main()
