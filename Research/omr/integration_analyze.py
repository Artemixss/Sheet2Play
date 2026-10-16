"""Audit bounded app qualification against generated references and prior native output."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import statistics
import sys

from integration_qualify import ROOT, FROZEN, WORKSPACE, sha256, save_new

sys.path.insert(0, str(WORKSPACE / "Bridge"))
import musicxml_normalizer
from homr_baseline_analyze import duration_diagnostics, reference_notes
from sheet2play_omr.zeus_trace import metric_summary, normalized_notes


def events(notes: list) -> Counter:
    return Counter((n.pitch, n.onset, n.duration, n.staff, n.voice) for n in notes)


def percentile95(values: list[float]) -> float:
    if not values:
        raise ValueError("Latency requires successful page observations")
    ordered = sorted(values)
    position = (len(ordered) - 1) * .95
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def analyze() -> None:
    root = ROOT / "qualification"
    selection = json.loads((root / "selection.json").read_text())
    if sha256(root / "inputs.json") != selection["inputs_sha256"]:
        raise ValueError("Qualification input identity drift")
    rows = json.loads((root / "inputs.json").read_text())
    report = {"profile_sha256": selection["profile_sha256"], "rows": [], "engines": {}}
    differences = []
    for engine in ("homr465", "homr"):
        scored, latencies = [], []
        for row in rows:
            output = root / engine / row["item_id"]
            receipt = json.loads((output / "result.json").read_text())
            for artifact in receipt["artifacts"]:
                if sha256(Path(artifact["path"])) != artifact["sha256"]:
                    raise ValueError("Native artifact drift")
            if receipt["input_sha256"] != row["image"]["sha256"]:
                raise ValueError("Native input identity mismatch")
            result = {"engine": engine, "item_id": row["item_id"], "status": receipt["status"],
                      "diagnostic_only": row["collection"] == "open", "seconds": receipt["elapsed_seconds"]}
            if receipt["status"] == "complete":
                if engine == "homr465" and receipt["runtime_profile_sha256"] != selection["profile_sha256"]:
                    raise ValueError("Native app profile mismatch")
                notes = normalized_notes(output / "input.musicxml")
                result["notes"] = len(notes)
                latencies.append(receipt["elapsed_seconds"])
                if row["collection"] == "generated":
                    truth, _ = reference_notes(row)
                    result["metrics"] = metric_summary(notes, [n.metric() for n in truth])
                    scored.append(result)
                if engine == "homr465":
                    historical = normalized_notes(FROZEN / "development" / row["item_id"] / "input.musicxml")
                    result["matches_prior_native_events"] = events(notes) == events(historical)
                    if not result["matches_prior_native_events"]:
                        differences.append(row["item_id"])
            else:
                result["error"] = receipt.get("error")
            report["rows"].append(result)
        diagnostics = duration_diagnostics(scored)
        diagnostics["interpretation"] = "Conditional duration diagnostics on exact pitch/onset pairs in twelve generated development controls only"
        report["engines"][engine] = {"successful_pages": len(latencies), "p95_seconds": percentile95(latencies),
            "generated_mean_f1": statistics.mean(r["metrics"]["onset_duration_f1"] for r in scored), "duration": diagnostics}
    report["new_event_differences"] = differences
    report["latency_ratio"] = report["engines"]["homr465"]["p95_seconds"] / report["engines"]["homr"]["p95_seconds"]
    report["known_harms"] = ["three_voices extra A5", "tuplet_aligned severe regression", "independent-voice tie limitation"]
    save_new(root / "analysis.json", report)
    print(json.dumps({"new_event_differences": differences, "latency_ratio": report["latency_ratio"],
                      "engines": {k: {n: v[n] for n in ("successful_pages", "p95_seconds", "generated_mean_f1")} for k, v in report["engines"].items()}}))
    if differences:
        raise RuntimeError("Fresh 465 musical-event changes require review before dependent release")


if __name__ == "__main__":
    analyze()
