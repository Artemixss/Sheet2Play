"""Provenance-checked development diagnosis and preregistered paired scoring."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from fractions import Fraction
import json
from pathlib import Path
import statistics

from homr_465_common import write_new, write_or_verify
from homr_465_prepare import EVIDENCE, HERE, PHASE1, WORKSPACE
from homr_baseline_analyze import duration_diagnostics, reference_notes
from homr_baseline_resume_analyze import completed_trace
from screening_homr_compatibility import digest, sha256_file
from musicxml_normalizer import MusicXmlNormalizationError
from screening_homr_statistics import paired_statistics
from screening_report import holm_adjust
from sheet2play_omr.corrected_scoring import metric_notes
from sheet2play_omr.zeus_trace import metric_summary, normalized_notes, xml_trace


def checked_receipt(root: Path, row: dict, configuration: dict) -> dict | None:
    path = root / "result.json"
    if not path.exists():
        return None
    result = json.loads(path.read_text(encoding="utf-8"))
    if (result["item_id"] != row["item_id"] or result["configuration_identity"] != configuration["identity_sha256"]
            or result["input_sha256"] != row["image"]["sha256"]):
        raise ValueError("Capture/input identity mismatch")
    for artifact in result["artifacts"]:
        if sha256_file(Path(artifact["path"])) != artifact["sha256"]:
            raise ValueError("Capture artifact drift: " + artifact["path"])
    return result


def converted_notes(root: Path, status: str) -> tuple[list, str, str | None]:
    if status != "complete":
        return [], status, None
    try:
        return normalized_notes(root / "input.musicxml"), "complete", None
    except MusicXmlNormalizationError as error:
        return [], "conversion_failed", f"{type(error).__name__}: {error}"


def measure_changes(candidate: list, baseline: list[dict], expected: list, measures: list[dict]) -> list[dict]:
    starts = sorted({Fraction(row["start"]) for row in measures})
    changes = []
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else None
        truth = Counter((n.pitch, n.onset, n.duration) for n in expected if n.onset >= start and (end is None or n.onset < end))
        actual = Counter((n.pitch, n.onset, n.duration) for n in candidate if n.onset >= start and (end is None or n.onset < end))
        old = Counter((n["pitch"], Fraction(n["onset"]), Fraction(n["duration"])) for n in baseline if Fraction(n["onset"]) >= start and (end is None or Fraction(n["onset"]) < end))
        if actual != old:
            changes.append({"reference_measure_ordinal": index + 1, "start": str(start),
                            "baseline_exact": old == truth, "candidate_exact": actual == truth,
                            "corrected": old != truth and actual == truth, "regressed": old == truth and actual != truth,
                            "candidate_missing": sum((truth - actual).values()), "candidate_extra": sum((actual - truth).values())})
    return changes


def development(destination: Path) -> dict:
    configuration = json.loads((EVIDENCE / "candidate-configuration.json").read_text())
    inputs = json.loads((EVIDENCE / "development-inputs.json").read_text())
    pages = {row["item_id"]: row for row in json.loads((PHASE1 / "title-disabled-20261007/boundaries/page-correspondence.json").read_text())["pages"]}
    old = {row["item_id"]: row for row in json.loads((PHASE1 / "title-disabled-20261007/analysis/development-analysis.json").read_text())["development"]}
    analysis_root = EVIDENCE / "analysis"
    analysis_root.mkdir(exist_ok=True)
    rows = []
    for row in inputs:
        root = EVIDENCE / "development" / row["item_id"]
        result = checked_receipt(root, row, configuration)
        item = {"item_id": row["item_id"], "status": "not_attempted" if result is None else result["status"],
                "diagnostic_only": row["collection"] == "open", "accuracy_claim": False}
        if result and result["status"] == "complete":
            item.update(completed_trace(row, root, analysis_root, pages.get(row["item_id"])))
            predicted = normalized_notes(root / "input.musicxml")
            if row["collection"] == "generated":
                expected, measures = reference_notes(row)
                item["measure_changes_against_phase1"] = measure_changes(predicted, old[row["item_id"]]["production_normalized_events"], expected, measures)
                item["baseline_metrics"] = old[row["item_id"]]["metrics"]
            timed = root / "timed-events.json"
            write_or_verify(timed, {"result_sha256": sha256_file(root / "result.json"),
                                   "normalizer_sha256": sha256_file(WORKSPACE / "dist/Bridge/musicxml_normalizer.py"),
                                   "production_normalized_events": item["production_normalized_events"], "literal_xml_events": item["literal_xml_events"]})
            item.update(receipt_sha256=sha256_file(root / "result.json"), timed_events_sha256=sha256_file(timed), elapsed_seconds=result["elapsed_seconds"])
        elif result:
            item["error"] = result.get("error")
        rows.append(item)
    scored = [row for row in rows if "metrics" in row]
    durations = duration_diagnostics(scored)
    durations["interpretation"] = "Conditional on exact pitch/onset matches in generated controls only; OpenScore diagnostic pages are not accuracy-scored"
    report = {"configuration_identity": configuration["identity_sha256"], "development": rows,
              "complete": sum(row["status"] == "complete" for row in rows), "failed": sum(row["status"] == "failed" for row in rows),
              "resource_stopped": sum(row["status"] == "resource_stopped" for row in rows), "not_attempted": sum(row["status"] == "not_attempted" for row in rows),
              "generated_controls_scored": len(scored), "duration": durations,
              "mean_generated_primary_f1": statistics.mean(row["metrics"]["onset_duration_f1"] for row in scored) if scored else None,
              "corrected_generated_measures": sum(change["corrected"] for row in scored for change in row["measure_changes_against_phase1"]),
              "regressed_generated_measures": sum(change["regressed"] for row in scored for change in row["measure_changes_against_phase1"])}
    write_new(destination, report)
    print(json.dumps({name: report[name] for name in ("complete", "failed", "resource_stopped", "not_attempted", "generated_controls_scored", "mean_generated_primary_f1", "corrected_generated_measures", "regressed_generated_measures")}))
    return report


def comparison() -> dict:
    freeze = json.loads((EVIDENCE / "comparison-freeze.json").read_text())
    identity = freeze.pop("identity_sha256")
    if digest(freeze) != identity:
        raise ValueError("Comparison identity drift")
    freeze["identity_sha256"] = identity
    for field in ("sample", "development_analysis", "candidate_configuration", "control_configuration", "normalizer", "scoring_code", "metrics_code", "statistics_code", "analysis_code", "comparison_inputs"):
        row = freeze[field]
        if sha256_file(Path(row["path"])) != row["sha256"]:
            raise ValueError("Comparison freeze drift: " + field)
    for row in freeze["additional_scoring_sources"]:
        if sha256_file(Path(row["path"])) != row["sha256"]:
            raise ValueError("Additional scoring source drift: " + row["path"])
    import musicxml_normalizer
    if Path(musicxml_normalizer.__file__).resolve() != Path(freeze["normalizer"]["path"]).resolve():
        raise ValueError("Unexpected production normalizer import origin")
    inputs = json.loads((EVIDENCE / "comparison-inputs.json").read_text())
    outputs = {}
    for profile in ("candidate", "control"):
        configuration = json.loads((EVIDENCE / (profile + "-configuration.json")).read_text())
        scores = []
        for row in inputs:
            root = EVIDENCE / "comparison" / profile / row["item_id"]
            receipt = checked_receipt(root, row, configuration)
            if receipt is None or receipt["status"] == "resource_stopped":
                raise ValueError("Incomplete/resource-stopped comparison cannot be ranked")
            reference_path = Path(row["reference"]["path"])
            if sha256_file(reference_path) != row["reference"]["sha256"]:
                raise ValueError("Frozen reference changed")
            reference = json.loads(reference_path.read_text())
            if reference["image_sha256"] != row["image"]["sha256"] or reference["item_id"] != row["original_item_id"]:
                raise ValueError("Frozen reference/image correspondence changed")
            xml_reference = WORKSPACE / reference["reference_musicxml"]
            if sha256_file(xml_reference) != reference["reference_musicxml_sha256"]:
                raise ValueError("Reference MusicXML drift")
            expected = metric_notes(reference)
            predicted, status, conversion_error = converted_notes(root, receipt["status"])
            metrics = metric_summary(predicted, expected)
            if status != "complete":
                for name in ("pitch_f1", "onset_f1", "onset_duration_f1"):
                    metrics[name] = 0.0
            score = {"item_id": row["item_id"], "original_item_id": row["original_item_id"], "composition_group": row["composition_group"],
                     "candidate": configuration["candidate"], "status": status, "capture_status": receipt["status"], "conversion_error": conversion_error,
                     "configuration_identity": configuration["identity_sha256"],
                     "comparison_identity": freeze["identity_sha256"], "receipt_sha256": sha256_file(root / "result.json"),
                     "reference_sha256": row["reference"]["sha256"], **metrics, "metrics": metrics, "elapsed_seconds": receipt["elapsed_seconds"]}
            write_or_verify(root / "score.json", score)
            events = [{"pitch": n.pitch, "onset": str(n.onset), "duration": str(n.duration), "staff": n.staff, "voice": n.voice} for n in predicted]
            write_or_verify(root / "timed-events.json", {"normalizer_sha256": freeze["normalizer"]["sha256"], "production_normalized_events": events})
            scores.append(score)
        grouped = defaultdict(list)
        for row in scores:
            grouped[row["composition_group"]].append(row)
        summary = {name: statistics.mean(statistics.mean(row[name] for row in group) for group in grouped.values())
                   for name in ("onset_duration_f1", "onset_f1", "pitch_f1")}
        summary.update(pages=len(scores), groups=len(grouped), conversion_success=sum(row["status"] == "complete" for row in scores),
                       missing_notes=sum(row["missing_notes"] for row in scores), extra_notes=sum(row["extra_notes"] for row in scores),
                       mean_seconds=statistics.mean(row["elapsed_seconds"] for row in scores), median_seconds=statistics.median(row["elapsed_seconds"] for row in scores),
                       total_seconds=sum(row["elapsed_seconds"] for row in scores), duration=duration_diagnostics(scores))
        summary["duration"]["interpretation"] = "Conditional on exact pitch/onset matches; not a substitute for primary transcription F1"
        outputs[profile] = {"scores": scores, "summary": summary}
    paired = paired_statistics(outputs["candidate"]["scores"], outputs["control"]["scores"], freeze["statistics"]["bootstrap_seed"])
    paired["holm_adjusted_p"] = holm_adjust({"465_over_shipped": paired["one_sided_superiority_p"]})["465_over_shipped"]
    report = {"comparison_identity": freeze["identity_sha256"], "outputs": outputs, "paired": paired,
              "supported_superiority": paired["holm_adjusted_p"] < 0.05 and paired["bootstrap_95_percent_interval"][0] > 0,
              "limitations": ["Previously observed screen, not untouched confirmation", "Upstream training overlap unknown", "Candidate is source/weights/pipeline bundle; no weight-only attribution",
                              "Native no-title profile; no general metadata-equivalence claim", "Physical audio and installed executable not tested", "Staff indices are not validated hand labels", "No measured human correction time", "No production promotion"]}
    write_new(EVIDENCE / "comparison-report.json", report)
    print(json.dumps({"candidate": outputs["candidate"]["summary"], "control": outputs["control"]["summary"], "paired": paired, "supported_superiority": report["supported_superiority"]}))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("development", "comparison"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    development(args.output or EVIDENCE / "development-analysis.json") if args.mode == "development" else comparison()
