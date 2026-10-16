"""Trace fixed Phase 3 replay artifacts without changing the historical pipeline."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import statistics
import xml.etree.ElementTree as ET

from zeus_attribution_prepare import HERE, OUT, configure_cpu, save_json
from phase2_zeus_runner import _stitch
from phase3_score import _duration_summary
from sheet2play_omr.adapter_contract import sha256_file
from sheet2play_omr.zeus_trace import (xml_trace, merge_segments, metric_summary, local_metrics,
                                      normalized_notes)


def signature(notes) -> Counter:
    return Counter((n.pitch, n.onset, n.duration) for n in notes)


def system_truth(segments, measures, boundaries=None) -> list[list]:
    first_part = measures[0]["part"]
    maximum = max(m["index"] for m in measures) + 1
    if boundaries is None:
        boundaries = [m["index"] for m in measures if m["part"] == first_part and (m["index"] == 0 or m["new_system"])]
    if not boundaries or boundaries[0] != 0 or boundaries != sorted(set(boundaries)) or any(
            type(index) is not int or not 0 <= index < maximum for index in boundaries):
        raise ValueError("Reference system boundaries must be increasing measure ordinals starting at zero")
    return [[n for n in segments if left <= n.measure < right]
            for left, right in zip(boundaries, boundaries[1:] + [maximum])]


def rebase(segments, measures=None, start_index=None) -> list:
    from dataclasses import replace
    if not segments:
        return []
    if measures is None:
        start = min(n.onset - n.local_onset for n in segments)
        return [replace(n, onset=n.onset - start) for n in segments]
    from fractions import Fraction
    origins = {m["part"]: Fraction(m["start"]) for m in measures if m["index"] == start_index}
    if any(n.part not in origins for n in segments):
        raise ValueError("Reference system lacks a part boundary")
    return [replace(n, onset=n.onset - origins[n.part]) for n in segments]


def part_staff_counts(segments) -> list[dict]:
    counts = Counter((n.part, n.staff) for n in segments)
    return [{"part": part, "global_staff": staff, "notes": count}
            for (part, staff), count in sorted(counts.items())]


def read_prediction(xml: Path) -> dict:
    stage = "xml_trace"
    try:
        ET.parse(xml)
        stage = "unchanged_normalization"
        normalized = normalized_notes(xml)
    except Exception as error:
        return {"status": "failed", "stage": stage, "error": f"{type(error).__name__}: {error}"}
    stage = "xml_trace"
    try:
        raw, measures = xml_trace(xml)
        stage = "diagnostic_tie_merge"
        merged, ties = merge_segments(raw)
        return {"status": "succeeded", "raw": raw, "measures": measures,
                "merged": merged, "ties": ties, "normalized": normalized}
    except Exception as error:
        return {"status": "succeeded", "normalized": normalized,
                "raw": None, "measures": None, "merged": None, "ties": None,
                "trace_failure": {"stage": stage, "error": f"{type(error).__name__}: {error}"}}


def failed_variant(truth, failures, systems, seconds) -> dict:
    return {"status": "failed", "failures": failures, "systems": systems,
            "seconds": seconds, "global": metric_summary([], truth)}


def analyze_item(item: dict, destination: Path) -> dict:
    item_id = item["item_id"]
    reference = Path(item["reference"])
    if sha256_file(reference) != item["reference_sha256"]:
        raise ValueError(f"Reference changed: {item_id}")
    truth_raw, truth_measures = xml_trace(reference)
    truth_merged, truth_ties = merge_segments(truth_raw)
    truth = normalized_notes(reference)
    reference_systems = system_truth(truth_raw, truth_measures, item.get("reference_system_measure_starts"))
    boundaries = item.get("reference_system_measure_starts") or [m["index"] for m in truth_measures
        if m["part"] == truth_measures[0]["part"] and (m["index"] == 0 or m["new_system"])]
    save_json(destination / "reference-trace.json", {"notes": [n.json() for n in truth_raw],
        "measures": truth_measures, "tie_issues": truth_ties, "part_staff_counts": part_staff_counts(truth_raw),
        "exact_merged_vs_normalized": metric_summary(truth, [n.metric() for n in truth_merged])})
    variants = {}
    for variant in ("upstream", "wrapper"):
        systems, xmls, failures, seconds = [], [], [], 0.0
        for index, crop in enumerate(item["crops"], 1):
            work = OUT / "inference" / item_id / f"system-{index:04d}"
            prediction = json.loads((work / "prediction.json").read_text())
            if prediction["crop_sha256"] != crop["sha256"]:
                raise ValueError("Prediction crop identity differs")
            row = prediction[variant]
            seconds += row["seconds"]
            xml = work / f"{variant}.musicxml"
            summary = {"index": index, "token_count": row["token_count"], "termination": row["termination"],
                       "unknown_token_count": row["unknown_token_count"], "conversion": row["conversion"]}
            if row["conversion"]["status"] == "failed":
                failures.append(summary)
                systems.append(summary)
                continue
            if sha256_file(xml) != row["conversion"]["musicxml_sha256"]:
                raise ValueError(f"Converted MusicXML changed: {xml}")
            xmls.append(xml)
            traced = read_prediction(xml)
            if traced["status"] == "failed":
                summary["trace_failure"] = traced
                systems.append(summary)
                continue
            if traced["raw"] is None:
                summary.update({"trace_failure": traced["trace_failure"],
                                "normalized_notes": len(traced["normalized"])})
                systems.append(summary)
                continue
            raw, measures, merged, ties, normalized = (traced[k] for k in
                ("raw", "measures", "merged", "ties", "normalized"))
            expected = rebase(reference_systems[index - 1], truth_measures, boundaries[index - 1]) if index <= len(reference_systems) else []
            summary.update({"raw_notes": len(raw), "exact_merged_notes": len(merged), "normalized_notes": len(normalized),
                "tie_issues": ties, "measure_count": len(measures),
                "overflow_measures": sum(m["overflow"] for m in measures),
                "exact_vs_normalized": metric_summary(normalized, [n.metric() for n in merged]),
                "part_staff_counts": part_staff_counts(raw),
                "system_local_raw": metric_summary([n.metric() for n in raw], [n.metric() for n in expected])})
            save_json(destination / f"{variant}-system-{index:04d}-trace.json",
                      {"notes": [n.json() for n in raw], "measures": measures, "summary": summary})
            systems.append(summary)
        page = destination / f"{variant}-stitched.musicxml"
        if failures or len(xmls) != len(item["crops"]):
            variants[variant] = failed_variant(truth, failures, systems, seconds)
            continue
        try:
            _stitch(xmls, page)
        except Exception as error:
            failure = {"stage": "unchanged_stitch", "error": f"{type(error).__name__}: {error}"}
            variants[variant] = failed_variant(truth, [failure], systems, seconds)
            continue
        traced = read_prediction(page)
        if traced["status"] == "failed":
            variants[variant] = failed_variant(truth, [traced], systems, seconds)
            continue
        raw, measures, merged, ties, normalized = (traced[k] for k in
            ("raw", "measures", "merged", "ties", "normalized"))
        exact_available = raw is not None
        save_json(destination / f"{variant}-page-trace.json", {"notes": [n.json() for n in raw] if exact_available else None,
            "measures": measures, "trace_failure": traced.get("trace_failure"),
            "normalized_notes": [{"pitch": n.pitch, "onset": str(n.onset), "duration": str(n.duration),
                                  "staff": n.staff, "voice": n.voice} for n in normalized]})
        variants[variant] = {"status": "succeeded", "seconds": seconds, "systems": systems,
            "global": metric_summary(normalized, truth),
            "raw_global": metric_summary([n.metric() for n in raw], [n.metric() for n in truth_raw]) if exact_available else None,
            "measure_local": local_metrics(raw, truth_raw) if exact_available else None, "tie_issues": ties,
            "part_staff_counts": part_staff_counts(raw) if exact_available else None,
            "normalizer_vs_exact_segments": metric_summary(normalized, [n.metric() for n in merged]) if exact_available else None,
            "stitch_raw_note_count_preserved": (len(raw) == sum(s["raw_notes"] for s in systems))
                if exact_available and all("raw_notes" in s for s in systems) else None,
            "system_boundary_starts": [m["start"] for m in measures if m["new_system"]] if exact_available else None,
            "trace_failure": traced.get("trace_failure"),
            "trace_policy": "Diagnostic validation never substitutes for unchanged stitched-page normalization failure policy",
            "conversion_diagnostic_count": sum(bool(s["conversion"]["diagnostics"]) for s in systems)}
    return {"item_id": item_id, "collection": item["collection"], "reference_notes": len(truth),
        "reference_systems": len(reference_systems), "detected_systems": len(item["crops"]),
        "reference_tie_issues": truth_ties,
        "reference_part_staff_counts": part_staff_counts(truth_raw),
        "staff_coverage_policy": "normalized staff indices reset per part; coverage is historical-index diagnostic, not hand accuracy; XML counts preserve distinct parts/staves",
        "system_local_policy": "ordinal system pairing; reference origins reset separately at each part's boundary; primary global scoring unchanged",
        "reference_normalizer_matches_exact": signature(truth) == signature([n.metric() for n in truth_merged]),
        "variants": variants}


def aggregate(rows: list[dict], variant: str) -> dict:
    scores = [row["variants"][variant]["global"] for row in rows]
    return {"items": len(rows), "failures": sum(row["variants"][variant]["status"] == "failed" for row in rows),
        "item_macro": {key: statistics.mean(s[key] for s in scores)
                       for key in ("pitch_f1", "onset_f1", "onset_duration_f1")},
        "duration_classification": _duration_summary(scores),
        "missing_notes": sum(s["missing_notes"] for s in scores),
        "extra_notes": sum(s["extra_notes"] for s in scores),
        "seconds": sum(row["variants"][variant]["seconds"] for row in rows)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--item-id")
    parser.add_argument("--output-name", default="analysis")
    args = parser.parse_args()
    if not args.output_name or Path(args.output_name).name != args.output_name:
        parser.error("Output name must be a single directory name")
    configure_cpu()
    manifest = json.loads((OUT / "experiment-manifest.json").read_text())
    rows = []
    for item in manifest["items"]:
        if args.item_id is not None and args.item_id != item["item_id"]:
            continue
        destination = OUT / args.output_name / item["item_id"]
        destination.mkdir(parents=True, exist_ok=False)
        row = analyze_item(item, destination)
        save_json(destination / "result.json", row)
        rows.append(row)
        print(json.dumps({"item_id": item["item_id"], "primary": {v: row["variants"][v]["global"]["onset_duration_f1"]
            for v in row["variants"]}}), flush=True)
    if args.item_id is None:
        save_json(OUT / "analysis-report.json", {"items": rows,
            "aggregate": {v: aggregate(rows, v) for v in ("upstream", "wrapper")},
            "metric_policy": "diagnostic item macro; frozen benchmark and composition-macro ranking unchanged"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
