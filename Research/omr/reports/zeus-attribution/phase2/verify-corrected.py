"""Independent counter-based verification of the completed cached rescore."""
from collections import Counter, defaultdict
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import statistics

WORKSPACE = Path(__file__).resolve().parents[5]
HERE = Path(__file__).resolve().parent
ROOT = HERE / "corrected-v1"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def hashed(path, expected):
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise ValueError(f"Hash mismatch: {path}")
    return actual


def counters(payload):
    # Independent unrestricted reconstruction is compared with the guarded policy
    # only after the report proves zero preserved-beyond-policy values in this sample.
    return Counter((int(row["midi_pitch"]), Fraction(str(row["onset"])).limit_denominator(4096),
                    Fraction(str(row["duration"])).limit_denominator(4096)) for row in payload["notes"])


def f1(predicted, expected):
    count = sum((predicted & expected).values())
    return 2 * count / (sum(predicted.values()) + sum(expected.values())) if count else 0.0


def main():
    report = read(ROOT / "report.json")
    identity = read(ROOT / "identity.json")
    hashed(ROOT / "report.json", read(ROOT / "report-sha256.json")["sha256"])
    for path, expected in identity["scoring_sources"].items():
        hashed(WORKSPACE / path, expected)
    records, artifacts, failures, reconstructions = 0, 0, 0, 0
    for name, source in report["sources"].items():
        hashed(WORKSPACE / source["manifest"], source["manifest_sha256"])
        manifest = read(WORKSPACE / source["manifest"])
        hashed(WORKSPACE / source["summary"]["path"], source["summary"]["sha256"])
        old_summary = read(WORKSPACE / source["summary"]["path"])
        sample_root = WORKSPACE / "Research/omr/reports/screening/v1" / manifest["sample_sha256"][:12]
        configuration = source["configuration_sha256"][:12]
        scores = {}
        for path, expected in report["score_hashes"][name].items():
            hashed(ROOT / path, expected)
            score = read(ROOT / path)
            if score["item_id"] in scores:
                raise ValueError("Duplicate corrected item")
            scores[score["item_id"]] = score
        grouped = {key: defaultdict(list) for key in ("pitch_f1", "onset_f1", "onset_duration_f1")}
        for item in manifest["items"]:
            audit = report["timing_audit"][name][item["id"]]
            assert audit["values_preserved_beyond_unrestricted_policy"] == 0
            reconstructions += audit["reconstructed_values"]
            token = hashlib.sha256(item["id"].encode()).hexdigest()[:20]
            result_path = sample_root / "completed" / name / configuration / token / "result.json"
            hashed(result_path, source["result_sha256"][item["id"]])
            result = read(result_path)
            for artifact in result["artifacts"]:
                path = WORKSPACE / artifact["path"]
                hashed(path, artifact["sha256"])
                assert path.stat().st_size == artifact["bytes"]
                artifacts += 1
            ref_path = WORKSPACE / item["reference_path"]
            hashed(ref_path, item["reference_sha256"])
            reference = read(ref_path)
            hashed(WORKSPACE / reference["reference_musicxml"], reference["reference_musicxml_sha256"])
            truth = counters(reference)
            prediction = Counter()
            if result["status"] == "succeeded":
                canonical = next(a for a in result["artifacts"] if a["role"] == "canonical_events")
                prediction = counters(read(WORKSPACE / canonical["path"]))
            else:
                failures += 1
            score = scores[item["id"]]
            old_path = sample_root / "scored" / name / configuration / manifest["scorer_sha256"][:12] / token / "score.json"
            hashed(old_path, old_summary["item_score_sha256"][item["id"]])
            old = read(old_path)
            for key in ("omr_ned", "omr_ned_status", "failure_penalized_omr_ned", "elapsed_seconds", "status", "error"):
                assert score[key] == old[key], (name, item["id"], key)
            assert score["input_identity"]["result_sha256"] == source["result_sha256"][item["id"]]
            assert score["input_identity"]["reference_sha256"] == item["reference_sha256"]
            assert score["reference_note_count"] == sum(truth.values())
            assert score["predicted_note_count"] == sum(prediction.values())
            assert score["missing_note_count"] == sum((truth - prediction).values())
            assert score["extra_note_count"] == sum((prediction - truth).values())
            for key, width in (("pitch_f1", 1), ("onset_f1", 2), ("onset_duration_f1", 3)):
                p, t = Counter(), Counter()
                for note, count in prediction.items():
                    p[note[:width]] += count
                for note, count in truth.items():
                    t[note[:width]] += count
                actual = f1(p, t)
                assert abs(actual - score[key]) < 1e-14, (name, item["id"], key)
                grouped[key][reference["composition_group"]].append(actual)
            records += 1
        for key, groups in grouped.items():
            assert len(groups) == 18
            actual = statistics.mean(statistics.mean(values) for values in groups.values())
            assert abs(actual - report["candidate_summaries"][name]["composition_macro"][key]) < 1e-14
        duration = report["candidate_summaries"][name]["duration_classification"]
        assert sum(map(sum, duration["matrix_rows_actual_columns_predicted"])) == duration["matched_pitch_onset_notes"]
    assert records == 295 and failures == 10
    result = {"records_verified": records, "artifacts_verified": artifacts,
              "failures_verified": failures, "reconstructed_values": reconstructions,
              "primary_secondary_metrics_independently_recomputed": True,
              "historical_ned_status_errors_runtime_preserved": True,
              "report_sha256": hashlib.sha256((ROOT / "report.json").read_bytes()).hexdigest()}
    output = HERE / "verification.json"
    with output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
