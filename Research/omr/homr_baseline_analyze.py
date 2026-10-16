"""Diagnose authoritative generated controls and preserve the production tie boundary."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
from fractions import Fraction as F
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[1]
sys.path.insert(0, str(HERE / "src"))
sys.path.insert(0, str(WORKSPACE / "dist/Bridge"))

from homr_baseline import digest, save
from sheet2play_omr.events import extract_canonical_events, parse_kern
from sheet2play_omr.metrics import MetricNote
from sheet2play_omr.research_ties import normalize_ties_exact, verify_midi
from sheet2play_omr.zeus_trace import Segment, metric_summary, normalized_notes, xml_trace
from musicxml_normalizer import add_seconds, normalize_musicxml


def reference_notes(row: dict) -> tuple[list[Segment], list[dict]]:
    source = Path(row["reference"]["path"])
    if row["reference_format"] == "musicxml":
        exact = normalize_ties_exact(source)
        if exact.issues:
            raise ValueError(f"Reference tie issues: {row['item_id']}")
        return list(exact.notes), list(exact.measures)
    score = extract_canonical_events(parse_kern(source.read_text(encoding="utf-8")))
    notes = [Segment(e.midi_pitch, F(e.onset), F(e.duration), e.staff, e.voice,
                     str(e.staff), e.measure - 1, F(e.onset) % 4, ())
             for e in score.events if e.kind == "note"]
    return notes, [{"index": i, "start": str(i * 4)} for i in sorted({n.measure for n in notes})]


def first_difference(predicted: list[MetricNote], expected: list[Segment], measures: list[dict]) -> dict | None:
    boundaries = sorted({F(m["start"]) for m in measures})
    for index, start in enumerate(boundaries):
        end = boundaries[index + 1] if index + 1 < len(boundaries) else None
        def counter(notes):
            return Counter((n.pitch, n.onset, n.duration) for n in notes
                           if n.onset >= start and (end is None or n.onset < end))
        actual, truth = counter(predicted), counter(expected)
        if actual != truth:
            def encode(values):
                return [{"pitch": p, "onset": str(o), "duration": str(d), "count": c}
                        for (p, o, d), c in sorted(values.items())]
            return {"reference_measure_ordinal": index + 1, "start": str(start),
                    "missing": encode(truth - actual), "extra": encode(actual - truth)}
    return None


def duration_diagnostics(rows: list[dict]) -> dict:
    confusion = Counter()
    for row in rows:
        for item in row["metrics"]["duration"]["confusion"]:
            confusion[(item["actual"], item["predicted"])] += item["count"]
    actual = Counter()
    predicted = Counter()
    for (a, p), count in confusion.items():
        actual[a] += count
        predicted[p] += count
    labels = sorted(actual.keys() | predicted.keys(), key=F)
    total = sum(actual.values())
    recalls = [confusion[(a, a)] / actual[a] for a in actual]
    f1s = [2 * confusion[(a, a)] / (actual[a] + predicted[a]) for a in labels]
    return {"labels": labels, "confusion_matrix": [[confusion[(a, p)] for p in labels] for a in labels],
            "paired_notes": total,
            "balanced_accuracy": sum(recalls) / len(recalls) if recalls else None,
            "macro_f1": sum(f1s) / len(f1s) if f1s else None,
            "majority_baseline_accuracy": max(actual.values()) / total if total else None,
            "single_class_predictor": len(predicted) == 1,
            "interpretation": "Conditional on exact pitch/onset pairs in eight pre-resource-failure controls; no corpus/model-ranking claim"}


def analyze(output: Path) -> dict:
    ledger = json.loads((output / "reference-eligibility.json").read_text())
    rows = []
    resource_seen = False
    for row in ledger:
        root = output / "development" / row["item_id"]
        result = json.loads((root / "result.json").read_text())
        for artifact in result["artifacts"]:
            if digest(Path(artifact["path"])) != artifact["sha256"]:
                raise ValueError("Inference artifact mismatch")
        trace = {"item_id": row["item_id"], "status": result["status"],
                 "result_sha256": digest(root / "result.json"), "accuracy_claim": False,
                 "diagnostic_only": row["collection"] == "open", "quarantined": resource_seen}
        if result["status"] != "complete":
            resource_seen = True
            trace["quarantined"] = True
            trace["earliest_demonstrated_error"] = "runtime allocation; not attributable to musical recognition"
            trace["error"] = result["error"]
        elif not resource_seen and row["numeric_accuracy_eligible"]:
            expected, measures = reference_notes(row)
            predicted = normalized_notes(root / "input.musicxml")
            xml_segments, xml_measures = xml_trace(root / "input.musicxml")
            trace["metrics"] = metric_summary(predicted, [n.metric() for n in expected])
            trace["first_difference"] = first_difference(predicted, expected, measures)
            trace["production_normalized_events"] = [
                {"pitch": n.pitch, "onset": str(n.onset), "duration": str(n.duration),
                 "staff": n.staff, "voice": n.voice} for n in predicted]
            trace["literal_xml_events"] = [n.json() for n in xml_segments]
            trace["xml_measures"] = xml_measures
            trace["reference_midi"] = verify_midi(tuple(expected), output / (row["item_id"] + "-reference.mid"))
            trace["earliest_demonstrated_error"] = "Requires image/crop/token review; first event divergence alone does not attribute cause"
        rows.append(trace)
    tie_path = HERE / "reports/zeus-attribution/phase2/cross-system-chord-tie.musicxml"
    research = normalize_ties_exact(tie_path)
    production = normalize_musicxml(tie_path, expand_repeats=False, skip_grace_notes=True, force_source=True)
    expected = sorted((n.pitch, str(n.onset), str(n.duration)) for n in research.notes)
    required = [(55, "0", "1/3"), (60, "0", "1"), (62, "1", "7/3"), (64, "0", "1")]
    if expected != required or len(production.notes) != 6:
        raise ValueError("Independent-voice tie boundary changed unexpectedly; review required")
    tie = {"source_sha256": digest(tie_path), "expected_events": expected,
           "production_events": [asdict(n) for n in production.notes],
           "research_events": [n.json() for n in research.notes],
           "production_timed_events": [asdict(n) for n in add_seconds(production)],
           "research_midi": verify_midi(research.notes, output / "independent-voice-tie.mid"),
           "production_replacement": False, "physical_audio_calibration": "unverified"}
    save(output / "tie-boundary.json", tie)
    usable = [r for r in rows if "metrics" in r]
    report = {"development": rows, "duration": duration_diagnostics(usable),
              "completed_xml": sum(r["status"] == "complete" for r in rows),
              "failed": sum(r["status"] != "complete" for r in rows),
              "pre_resource_failure_controls": len(usable), "phase2_started": False}
    save(output / "development-analysis.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    report = analyze(parser.parse_args().output)
    print(json.dumps({k: report[k] for k in ("completed_xml", "failed", "pre_resource_failure_controls")}))
