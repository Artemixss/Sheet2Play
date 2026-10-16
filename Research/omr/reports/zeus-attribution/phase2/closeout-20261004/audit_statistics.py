"""Read-only closeout audit; deliberately imports no scoring implementation."""
from collections import Counter, defaultdict
import hashlib
import itertools
import json
from pathlib import Path
import random
import statistics

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent / "corrected-v1"
WORKSPACE = HERE.parents[5]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def close(actual, expected):
    if abs(actual - expected) > 1e-12:
        raise ValueError(f"Mismatch: {actual} versus {expected}")


def percentile(values, fraction):
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    index = int(position)
    return ordered[index] + (ordered[min(index + 1, len(ordered) - 1)] - ordered[index]) * (position - index)


def main():
    report = read(ROOT / "report.json")
    expected = read(ROOT / "report-sha256.json")["sha256"]
    if hashlib.sha256((ROOT / "report.json").read_bytes()).hexdigest() != expected:
        raise ValueError("Report hash mismatch")
    for path, digest in read(ROOT / "identity.json")["scoring_sources"].items():
        if hashlib.sha256((WORKSPACE / path).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Source hash mismatch: {path}")
    candidates, diagnostics = {}, {}
    for candidate, paths in report["score_hashes"].items():
        rows = []
        for path, digest in paths.items():
            content = (ROOT / path).read_bytes()
            if hashlib.sha256(content).hexdigest() != digest:
                raise ValueError(f"Score hash mismatch: {path}")
            rows.append(json.loads(content))
        assert len(rows) == 59 and len({r["item_id"] for r in rows}) == 59
        candidates[candidate] = {r["item_id"]: r for r in rows}
        summary = report["candidate_summaries"][candidate]
        for field in ("pitch_f1", "onset_f1", "onset_duration_f1"):
            groups = defaultdict(list)
            for row in rows:
                groups[row["composition_group"]].append(row[field])
            assert len(groups) == 18
            close(statistics.mean(statistics.mean(v) for v in groups.values()), summary["composition_macro"][field])
        confusion = Counter()
        for row in rows:
            if row["duration"] is not None:
                for cell in row["duration"]["confusion"]:
                    confusion[cell["actual"], cell["predicted"]] += cell["count"]
        duration = summary["duration_classification"]
        labels = duration["labels"]
        assert [[confusion[a, p] for p in labels] for a in labels] == duration["matrix_rows_actual_columns_predicted"]
        assert sum(confusion.values()) == duration["matched_pitch_onset_notes"]
        for field in ("missing_note_count", "extra_note_count"):
            assert sum(r[field] for r in rows) == summary[field]
        assert dict(Counter(r["status"] for r in rows)) == summary["status_counts"]
        diagnostics[candidate] = {field: summary[field] for field in (
            "missing_note_count", "extra_note_count", "latency_seconds", "error_code_stage_counts")}
        diagnostics[candidate]["reference_chords"] = sum(r["coverage"]["reference_chords"] for r in rows)
        diagnostics[candidate]["complete_chords"] = sum(r["coverage"]["complete_chords"] for r in rows)
    pvalues = {}
    for claim, saved in report["paired"].items():
        left, right = claim.split("_minus_")
        assert candidates[left].keys() == candidates[right].keys()
        groups = defaultdict(list)
        for item, row in candidates[left].items():
            other = candidates[right][item]
            assert row["composition_group"] == other["composition_group"]
            groups[row["composition_group"]].append(row["onset_duration_f1"] - other["onset_duration_f1"])
        differences = [statistics.mean(groups[g]) for g in sorted(groups)]
        assert len(differences) == 18
        for a, b in zip(differences, saved["composition_differences"], strict=True):
            close(a, b)
        mean = statistics.mean(differences)
        close(mean, saved["primary_f1_difference"])
        threshold = mean - max(1.0, abs(mean)) * 1e-12
        count = sum(statistics.mean(v * s for v, s in zip(differences, signs)) >= threshold
                    for signs in itertools.product((-1, 1), repeat=18))
        pvalues[claim] = count / 2**18
        close(pvalues[claim], saved["one_sided_superiority_p"])
        rng = random.Random(saved["bootstrap_seed"])
        samples = [statistics.mean(rng.choices(differences, k=18)) for _ in range(10000)]
        for actual, expected_ci in zip((percentile(samples, .025), percentile(samples, .975)), saved["bootstrap_95_percent_interval"]):
            close(actual, expected_ci)
    running = 0.0
    for index, (claim, pvalue) in enumerate(sorted(pvalues.items(), key=lambda pair: (pair[1], pair[0]))):
        running = max(running, min(1.0, (len(pvalues) - index) * pvalue))
        close(running, report["paired"][claim]["holm_adjusted_superiority_p"])
    result = {"scores_verified": 295, "paired_claims_verified": len(pvalues),
              "independent_exact_assignments_per_claim": 2**18, "bootstrap_resamples_per_claim": 10000,
              "composition_metrics_dense_duration_matrices_failures_counts_verified": True,
              "report_sha256": expected, "diagnostics": diagnostics}
    with (HERE / "statistical-verification.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps({k: v for k, v in result.items() if k != "diagnostics"}))


if __name__ == "__main__":
    main()
