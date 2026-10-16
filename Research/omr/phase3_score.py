"""Score and summarize one complete, frozen Phase-3 SMB page inference run."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path
from typing import Any

from phase3_freeze import verify_freeze, verify_secondary_audit
from phase3_infer import COLLECTIONS, PAGE_CANDIDATES, _paths, _verify_existing
from sheet2play_omr.adapter_contract import sha256_file
from sheet2play_omr.phase3_references import frozen_smb_rows
from sheet2play_omr.phase3_scoring import score_result


WORKSPACE = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SCORER = HERE / "src" / "sheet2play_omr" / "phase3_scoring.py"
METRICS = ("pitch_f1", "onset_f1", "onset_duration_f1")


def _write_once(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite Phase-3 score: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
                         encoding="utf-8")
    temporary.replace(path)


def _identity(freeze_sha256: str, result_sha256: str, reference_sha256: str) -> dict[str, str]:
    return {"freeze_sha256": freeze_sha256, "result_sha256": result_sha256,
            "reference_sha256": reference_sha256,
            "scoring_module_sha256": sha256_file(SCORER),
            "scoring_runner_sha256": sha256_file(Path(__file__))}


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    low = math.floor(position)
    high = math.ceil(position)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def _macro(values: list[dict[str, Any]], key: str) -> float | None:
    by_composition: dict[str, list[float]] = defaultdict(list)
    for row in values:
        number = row.get(key)
        if number is not None:
            by_composition[row["composition_group"]].append(float(number))
    if not by_composition:
        return None
    return statistics.mean(statistics.mean(items) for items in by_composition.values())


def _duration_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts: Counter[tuple[str, str]] = Counter()
    unmatched_predicted = 0
    unmatched_expected = 0
    for row in rows:
        duration = row["duration"]
        if duration is None:
            continue
        counts.update({(entry["actual"], entry["predicted"]): entry["count"]
                       for entry in duration["confusion"]})
        unmatched_predicted += duration["unmatched_predicted"]
        unmatched_expected += duration["unmatched_expected"]
    actual_counts: Counter[str] = Counter()
    predicted_counts: Counter[str] = Counter()
    for (actual, predicted), count in counts.items():
        actual_counts[actual] += count
        predicted_counts[predicted] += count
    labels = sorted(actual_counts.keys() | predicted_counts.keys())
    total = sum(actual_counts.values())
    if not total:
        return {"matched_pitch_onset_notes": 0, "confusion_matrix": [],
                "unmatched_predicted": unmatched_predicted,
                "unmatched_expected": unmatched_expected, "balanced_accuracy": None,
                "macro_f1": None, "majority_baseline_accuracy": None,
                "majority_baseline_macro_f1": None, "degenerate_single_class_predictor": None}
    recalls = []
    f1s = []
    majority = max(sorted(actual_counts), key=lambda key: actual_counts[key])
    baseline_f1s = []
    for label in labels:
        true_positive = counts[(label, label)]
        support = actual_counts[label]
        predicted = predicted_counts[label]
        if support:
            recalls.append(true_positive / support)
        denominator = support + predicted
        f1s.append(2 * true_positive / denominator if denominator else 0.0)
        baseline_f1s.append(2 * support / (support + total) if label == majority else 0.0)
    active_predictions = [label for label, count in predicted_counts.items() if count]
    return {
        "matched_pitch_onset_notes": total,
        "labels": labels,
        "confusion_matrix": [{"actual": actual, "predicted": predicted, "count": count}
                             for (actual, predicted), count in sorted(counts.items()) if count],
        "unmatched_predicted": unmatched_predicted,
        "unmatched_expected": unmatched_expected,
        "balanced_accuracy": statistics.mean(recalls),
        "macro_f1": statistics.mean(f1s),
        "majority_class": majority,
        "majority_baseline_accuracy": actual_counts[majority] / total,
        "majority_baseline_macro_f1": statistics.mean(baseline_f1s),
        "degenerate_single_class_predictor": len(active_predictions) == 1 and len(actual_counts) > 1,
    }


def _summary(rows: list[dict[str, Any]], manifest: dict[str, dict[str, Any]],
             freeze: dict[str, Any], candidate: str,
             collection: str = "smb-pianoform") -> dict[str, Any]:
    statuses = Counter(row["status"] for row in rows)
    error_counts = Counter(
        f"{row['error'].get('code', 'unknown')}:{row['error'].get('stage', 'unknown')}"
        for row in rows if row["error"])
    times = [row["elapsed_seconds"] for row in rows]
    valid_ned = [row["omr_ned"] for row in rows if row["omr_ned_status"] == "valid"]
    penalized_ned = [row["failure_penalized_omr_ned"] for row in rows
                     if row["failure_penalized_omr_ned"] is not None]
    failure_codes = Counter(row["error"].get("code", "unknown")
                            for row in rows if row["error"])
    features: dict[str, dict[str, Any]] = {}
    feature_names = ("has_independent_voices", "cross_staff", "has_ties", "has_tuplets",
                     "has_meter_changes", "has_repeats")
    for feature in feature_names:
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            groups[str(manifest[row["item_id"]]["notation_features"].get(feature, "unknown"))].append(row)
        features[feature] = {value: {"page_count": len(items),
                                      "composition_count": len({item["composition_group"] for item in items}),
                                      "composition_macro_primary_f1": _macro(items, "onset_duration_f1")}
                             for value, items in sorted(groups.items())}
    for label, classify in (
        ("density_notes_per_quarter", lambda row: "lt4" if row["reference_note_count"] / max(1, float(Fraction(row["reference_quarter_length"]))) < 4 else "ge4"),
        ("document_measure_count", lambda row: "le32" if row["reference_measure_count"] <= 32 else "gt32"),
    ):
        groups = defaultdict(list)
        for row in rows:
            groups[classify(row)].append(row)
        features[label] = {value: {"page_count": len(items),
                                   "composition_macro_primary_f1": _macro(items, "onset_duration_f1")}
                           for value, items in sorted(groups.items())}
    return {
        "schema_version": 1, "scope": "phase3_descriptive_complete_page_no_paired_ranking",
        "collection": collection, "candidate": candidate,
        "eligible_page_count": len(manifest), "scored_page_count": len(rows),
        "composition_count": len({row["composition_group"] for row in rows}),
        "status_counts": dict(sorted(statuses.items())),
        "failure_rate": statuses["failed"] / len(rows),
        "error_code_stage_counts": dict(sorted(error_counts.items())),
        "failure_class_rates": {
            "missing_system": failure_codes["MISSING_SYSTEM"] / len(rows),
            "timeout": sum(count for code, count in failure_codes.items()
                           if "TIMEOUT" in code.upper()) / len(rows),
            "invalid_output": sum(count for code, count in failure_codes.items()
                                  if "INVALID" in code.upper() or "EMPTY" in code.upper()) / len(rows),
            "complete_document": statuses["failed"] / len(rows),
        },
        "composition_macro": {key: _macro(rows, key) for key in METRICS},
        "valid_output_omr_ned_mean": statistics.mean(valid_ned) if valid_ned else None,
        "valid_output_omr_ned_count": len(valid_ned),
        "failure_penalized_omr_ned_mean": statistics.mean(penalized_ned) if penalized_ned else None,
        "failure_penalized_omr_ned_count": len(penalized_ned),
        "failure_penalized_omr_ned_complete": len(penalized_ned) == len(rows),
        "omr_ned_scoring_error_count": sum(row["omr_ned_status"] == "scoring_error" for row in rows),
        "failure_penalty_omr_ned": 1.0,
        "duration_classification": _duration_summary(rows),
        "missing_note_count": sum(row["missing_note_count"] for row in rows),
        "extra_note_count": sum(row["extra_note_count"] for row in rows),
        "latency_seconds": {"median": statistics.median(times), "p95": _percentile(times, 0.95),
                            "includes_failures": True},
        "cold_start_seconds": [row["elapsed_seconds"] for row in rows if row["cold_start"]],
        "peak_ram_bytes_max": max((row["peak_ram_bytes"] for row in rows
                                   if row["peak_ram_bytes"] is not None), default=None),
        "peak_vram_bytes_max": max((row["peak_vram_bytes"] for row in rows
                                    if row["peak_vram_bytes"] is not None), default=None),
        "vram_measurement_notes": sorted({note for row in rows
                                          for note in row["vram_measurement_notes"]}),
        "actual_cloud_cost_usd": 0.0,
        "feature_breakdowns": features,
        "training_overlap": freeze["training_overlap"],
        "reference_interpretation": "Combined SMB region truth exported to MusicXML; OMR-NED is not directly comparable to native **kern published scores",
    }


def run(candidate: str, freeze_path: Path, collection: str = "smb-pianoform") -> Path:
    if candidate not in PAGE_CANDIDATES or collection not in COLLECTIONS:
        raise ValueError("Unsupported complete-page candidate or collection")
    freeze_path = freeze_path.resolve()
    freeze = verify_freeze(freeze_path)
    freeze_hash = sha256_file(freeze_path)
    audit_identity = (freeze["reference_audit"] if collection == "smb-pianoform"
                      else verify_secondary_audit())
    audit = json.loads((WORKSPACE / audit_identity["path"]).read_text(encoding="utf-8"))
    references = {item["id"]: item for item in audit["items"]}
    manifest_rows = frozen_smb_rows(WORKSPACE, collection)
    manifest = {row["id"]: row for row in manifest_rows}
    if len(references) != len(manifest_rows) or set(references) != set(manifest):
        raise RuntimeError("The frozen reference and eligible item sets differ")
    config_hash = freeze["ready"][candidate]["adapter_config_sha256"]
    scored: list[dict[str, Any]] = []
    for index, item in enumerate(manifest_rows, start=1):
        reference_meta = references[item["id"]]
        reference_path = WORKSPACE / reference_meta["reference_path"]
        if not reference_path.is_file() or sha256_file(reference_path) != reference_meta["reference_sha256"]:
            raise RuntimeError(f"Frozen reference changed: {item['id']}")
        report, _ = _paths(candidate, item["id"], config_hash, collection,
                           audit_identity["sha256"])
        if not report.is_file():
            raise RuntimeError(f"Frozen inference is incomplete at {index}/{len(manifest_rows)}: {item['id']}")
        inference_identity = {"schema_version": 1, "freeze_sha256": freeze_hash,
                              "collection": collection,
                              "reference_audit_sha256": audit_identity["sha256"],
                              "candidate": candidate, "item_id": item["id"],
                              "image_sha256": item["image_sha256"],
                              "reference_sha256": reference_meta["reference_sha256"],
                              "adapter_config_sha256": config_hash}
        _verify_existing(report, inference_identity)
        identity = _identity(freeze_hash, sha256_file(report), reference_meta["reference_sha256"])
        output = HERE / "reports" / "phase3" / "scored" / collection / candidate / report.name
        sidecar = output.with_suffix(".identity.json")
        if output.is_file():
            if not sidecar.is_file() or json.loads(sidecar.read_text(encoding="utf-8")) != identity:
                raise RuntimeError(f"Frozen score identity changed: {output}")
            metrics = json.loads(output.read_text(encoding="utf-8"))
        else:
            if sidecar.exists():
                raise FileExistsError(f"Partial score sidecar exists: {sidecar}")
            result = json.loads(report.read_text(encoding="utf-8"))
            reference = json.loads(reference_path.read_text(encoding="utf-8"))
            metrics = score_result(result, reference, WORKSPACE)
            _write_once(output, metrics)
            _write_once(sidecar, identity)
        scored.append(metrics)
        print(json.dumps({"item": index, "total": len(manifest_rows), "id": item["id"],
                          "candidate": candidate, "status": metrics["status"]}, sort_keys=True), flush=True)
    summary = _summary(scored, manifest, freeze, candidate, collection)
    summary["freeze_sha256"] = freeze_hash
    summary["reference_audit_sha256"] = audit_identity["sha256"]
    summary["scorer_sha256"] = sha256_file(SCORER)
    summary["runner_sha256"] = sha256_file(Path(__file__))
    output = HERE / "reports" / "phase3" / f"summary-{collection}-{candidate}-{freeze_hash[:12]}-{audit_identity['sha256'][:12]}.json"
    _write_once(output, summary)
    print(json.dumps({"summary": str(output), "primary_f1": summary["composition_macro"]["onset_duration_f1"]},
                     sort_keys=True), flush=True)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--candidate", choices=PAGE_CANDIDATES, required=True)
    parser.add_argument("--collection", choices=COLLECTIONS, default="smb-pianoform")
    args = parser.parse_args()
    run(args.candidate, args.freeze, args.collection)


if __name__ == "__main__":
    main()
