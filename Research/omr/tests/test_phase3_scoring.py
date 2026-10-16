from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import phase3_score
from sheet2play_omr.adapter_contract import sha256_file
from sheet2play_omr import phase3_scoring


def _reference(tmp_path: Path) -> dict:
    reference_xml = tmp_path / "reference.musicxml"
    reference_xml.write_text("<score-partwise/>", encoding="utf-8")
    return {
        "item_id": "synthetic", "composition_group": "work-a", "image_sha256": "a" * 64,
        "reference_musicxml": str(reference_xml),
        "reference_musicxml_sha256": sha256_file(reference_xml),
        "measure_boundaries": ["0", "1", "2"],
        "notes": [
            {"midi_pitch": 60, "onset": "0", "duration": "1/2", "staff": 0, "voice": "1"},
            {"midi_pitch": 64, "onset": "1", "duration": "1", "staff": 0, "voice": "1"},
        ],
    }


def _result(tmp_path: Path, *, status: str, notes: list[dict] | None = None) -> dict:
    artifacts = []
    if status == "succeeded":
        canonical = tmp_path / "canonical.json"
        canonical.write_text(json.dumps({"notes": notes}), encoding="utf-8")
        musicxml = tmp_path / "prediction.musicxml"
        musicxml.write_text("<score-partwise/>", encoding="utf-8")
        artifacts = [{"role": role, "path": str(path), "sha256": sha256_file(path)}
                     for role, path in (("canonical_events", canonical), ("musicxml", musicxml))]
    return {
        "item_id": "synthetic", "composition_group": "work-a", "candidate_id": "test",
        "adapter_id": "test-adapter", "status": status,
        "provenance": {"input_sha256": "a" * 64},
        "timings": [{"stage": "total_failed_attempt" if status == "failed" else "recognition",
                     "seconds": 2.5}],
        "resources": {"peak_ram_bytes": 100, "peak_vram_bytes": None,
                      "measurement_notes": ["device-wide WDDM"], "cold_start": True},
        "artifacts": artifacts,
        "error": {"code": "MISSING_SYSTEM", "stage": "stitching"} if status == "failed" else None,
    }


def test_identical_score_and_duration_diagnostics(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reference = _reference(tmp_path)
    monkeypatch.setattr(phase3_scoring, "score_pair", lambda *_: SimpleNamespace(score=0.125))
    result = _result(tmp_path, status="succeeded", notes=reference["notes"])
    scored = phase3_scoring.score_result(result, reference, tmp_path)
    assert scored["onset_duration_f1"] == 1.0
    assert scored["first_divergent_measure"] is None
    assert scored["missing_note_count"] == scored["extra_note_count"] == 0
    assert scored["failure_penalized_omr_ned"] == 0.125
    assert scored["duration"]["confusion"] == [
        {"actual": "1", "predicted": "1", "count": 1},
        {"actual": "1/2", "predicted": "1/2", "count": 1},
    ]


def test_failure_is_zero_scored_and_includes_elapsed_time(tmp_path: Path) -> None:
    scored = phase3_scoring.score_result(_result(tmp_path, status="failed"),
                                         _reference(tmp_path), tmp_path)
    assert scored["onset_duration_f1"] == 0.0
    assert scored["missing_note_count"] == 2
    assert scored["elapsed_seconds"] == 2.5
    assert scored["failure_penalized_omr_ned"] == 1.0
    assert scored["vram_measurement_notes"] == ["device-wide WDDM"]


def test_empty_successful_artifact_is_scored_as_invalid_output(tmp_path: Path) -> None:
    scored = phase3_scoring.score_result(
        _result(tmp_path, status="succeeded", notes=[]), _reference(tmp_path), tmp_path)
    assert scored["status"] == "failed"
    assert scored["error"]["code"] == "INVALID_CANONICAL_OUTPUT"
    assert scored["onset_duration_f1"] == 0.0
    assert scored["failure_penalized_omr_ned"] == 1.0


def test_shifted_onset_and_degenerate_duration_predictor(tmp_path: Path,
                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    reference = _reference(tmp_path)
    altered = [dict(note) for note in reference["notes"]]
    altered[0]["onset"] = "1/4"
    altered[1]["duration"] = "1/2"
    monkeypatch.setattr(phase3_scoring, "score_pair", lambda *_: SimpleNamespace(score=0.5))
    scored = phase3_scoring.score_result(_result(tmp_path, status="succeeded", notes=altered),
                                         reference, tmp_path)
    assert scored["first_divergent_measure"] == 1
    assert scored["onset_duration_f1"] == 0.0
    assert scored["duration"]["confusion"] == [
        {"actual": "1", "predicted": "1/2", "count": 1}
    ]
    duration = phase3_score._duration_summary([
        {"duration": {"confusion": [
            {"actual": "1", "predicted": "1/2", "count": 1},
            {"actual": "1/2", "predicted": "1/2", "count": 1},
        ], "unmatched_expected": 0, "unmatched_predicted": 0}}
    ])
    assert duration["degenerate_single_class_predictor"] is True
    assert duration["majority_baseline_accuracy"] == 0.5


def test_mismatched_result_identity_is_rejected(tmp_path: Path) -> None:
    result = _result(tmp_path, status="failed")
    result["provenance"]["input_sha256"] = "b" * 64
    with pytest.raises(ValueError, match="identities differ"):
        phase3_scoring.score_result(result, _reference(tmp_path), tmp_path)


def test_summary_uses_composition_macro_and_counts_failures() -> None:
    def row(item: str, composition: str, f1: float, elapsed: float, failed: bool) -> dict:
        return {
            "item_id": item, "composition_group": composition,
            "status": "failed" if failed else "succeeded",
            "error": {"code": "MISSING_SYSTEM", "stage": "stitching"} if failed else None,
            "pitch_f1": f1, "onset_f1": f1, "onset_duration_f1": f1,
            "omr_ned": None if failed else 0.0,
            "omr_ned_status": "engine_failed" if failed else "valid",
            "failure_penalized_omr_ned": 1.0 if failed else 0.0,
            "duration": None, "missing_note_count": int(failed), "extra_note_count": 0,
            "elapsed_seconds": elapsed, "cold_start": False,
            "peak_ram_bytes": 10, "peak_vram_bytes": None,
            "vram_measurement_notes": [], "reference_note_count": 4,
            "reference_quarter_length": "1", "reference_measure_count": 1,
        }

    rows = [row("a1", "a", 1.0, 1.0, False),
            row("a2", "a", 0.0, 5.0, True),
            row("b1", "b", 1.0, 2.0, False)]
    manifest = {item["item_id"]: {"notation_features": {"annotated_region_count": 1}}
                for item in rows}
    summary = phase3_score._summary(rows, manifest, {"training_overlap": {}}, "test")
    assert summary["composition_macro"]["onset_duration_f1"] == 0.75
    assert summary["failure_rate"] == pytest.approx(1 / 3)
    assert summary["latency_seconds"]["median"] == 2.0
    assert summary["failure_penalized_omr_ned_mean"] == pytest.approx(1 / 3)
    assert summary["failure_class_rates"]["missing_system"] == pytest.approx(1 / 3)
