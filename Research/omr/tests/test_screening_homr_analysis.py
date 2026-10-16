"""Reject incompatible samples and distinguish operating policy from eligibility."""
from __future__ import annotations

import copy

import pytest

from screening_homr_analysis import RETIRED_455, check_sample_agreement, markdown, practical_evidence


def test_analysis_rejects_changed_truth_or_incompatible_455():
    manifest = {key: key for key in ("sample_sha256", "selected_groups", "scorer_sha256",
                "scoring_protocol_sha256", "seed")}
    manifest["items"] = [{"id": "page", "reference_sha256": "a" * 64}]
    manifest["candidates"] = {"homr_455": {"identity_sha256": "b" * 64}}
    check_sample_agreement(manifest, copy.deepcopy(manifest))
    changed = copy.deepcopy(manifest)
    changed["items"][0]["reference_sha256"] = "c" * 64
    with pytest.raises(ValueError, match="items"):
        check_sample_agreement(manifest, changed)
    manifest["candidates"]["homr_455"]["identity_sha256"] = RETIRED_455
    with pytest.raises(ValueError, match="Incompatible"):
        check_sample_agreement(manifest, manifest)


def test_high_system_pressure_does_not_rewrite_frozen_process_memory_limit():
    summary = {"peak_ram_bytes_max": 800, "peak_vram_bytes_max": 1048576,
               "latency_seconds": {"p95": 20}}
    operation = {"hardware_ram_bytes": 1000, "hardware_vram_mib": 10,
                 "sampled_system_ram_percent_max": 88, "inference_interruption_count": 0,
                 "session": {"used_seconds": 3000}}
    protocol = {"practical_eligibility": {"maximum_p95_page_latency_vs_homr": 2,
                "maximum_peak_ram_fraction": 0.75, "maximum_peak_vram_fraction": 0.9}}
    practical = practical_evidence(summary, summary, operation, protocol)
    assert practical["checks"]["process_tree_ram"] is False
    assert practical["checks"]["device_wide_vram"] is True
    assert practical["observed_limits_pass"] is False


def test_report_retains_all_failed_candidate_and_missing_duration_diagnostics():
    summary = {"composition_macro": {"onset_duration_f1": 0.0, "onset_f1": 0.0, "pitch_f1": 0.0},
        "status_counts": {"failed": 59}, "failure_penalized_omr_ned_mean": 1.0,
        "duration_classification": {"balanced_accuracy": None, "macro_f1": None,
            "majority_baseline_accuracy": None, "degenerate_single_class_predictor": None},
        "cold_start_seconds": [], "valid_output_omr_ned_mean": None, "valid_output_omr_ned_count": 0,
        "failure_penalized_omr_ned_complete": True, "omr_ned_scoring_error_count": 0,
        "missing_note_count": 500, "extra_note_count": 0,
        "error_code_stage_counts": {"HOMR_OUTPUT_MISSING:conversion": 59},
        "latency_seconds": {"median": None, "p95": None}, "feature_breakdowns": {}}
    report = {"pages": 59, "compositions": 18, "candidate_summaries": {"homr_page": summary},
        "paired": {}, "operations": {"homr_page": {"session": {"used_seconds": 100},
            "sampled_system_ram_percent_max": 60, "sampled_device_vram_mib_max": 0,
            "resource_policy": {"ram_admission_percent": 90}}},
        "practical": {"homr_page": {"checks": {"latency": False}}},
        "decision": {"descriptive_primary_f1_leader": "homr_page", "production_decision": "Keep control",
                     "provisional_confirmation_interest": {}}, "confirmation_estimate": {}}
    output = markdown(report)
    assert "59/59" in output
    assert "Valid-output OMR-NED unavailable (0 pages)" in output
    assert "balanced accuracy **unavailable**" in output
    assert "Missing/extra notes: 500/0" in output
