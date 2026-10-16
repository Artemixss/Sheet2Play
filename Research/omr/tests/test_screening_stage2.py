"""Stage-2 selection, immutable results, resume, scoring, and report contracts."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import screening_common as common
import screening_admit
import screening_report
import screening_run
import screening_score
from sheet2play_omr.adapter_contract import sha256_file
from sheet2play_omr.phase3_references import frozen_smb_rows
from sheet2play_omr.phase3_scoring import score_result


def candidate_fixture(tmp_path: Path, status: str = "succeeded"):
    item = {"id": "item", "composition_group": "composition", "image_sha256": "a" * 64,
            "reference_sha256": "b" * 64}
    config = {"candidate_id": "shipped_homr", "adapter_id": "direct", "source_revision": "pinned"}
    config_hash = common.digest(config)
    manifest = {"schema_version": 4, "resource_policy": common.POLICY,
                "sample_sha256": "c" * 64, "candidates": {"homr_page": {
        "identity_sha256": "d" * 64, "identity": {"adapter_config_sha256": config_hash}}}}
    identity = common.result_identity(manifest, "homr_page", item)
    artifacts = []
    for role in ("native", "musicxml", "canonical_events"):
        path = tmp_path / role
        path.write_bytes(role.encode())
        artifacts.append({"role": role, "path": role, "bytes": path.stat().st_size,
                          "sha256": sha256_file(path)})
    result = {"schema_version": 1, "item_id": "item", "composition_group": "composition",
              "adapter_config_sha256": config_hash, "candidate_id": "shipped_homr",
              "adapter_id": "direct", "status": status,
              "exit_status": 0 if status == "succeeded" else 1,
              "provenance": {"adapter_config": config, "input_sha256": "a" * 64},
              "artifacts": artifacts,
              "timings": [{"stage": "recognition", "seconds": 1.0}],
              "resources": {"peak_ram_bytes": 100, "peak_vram_bytes": None,
                            "measurement_notes": ["device-wide"], "cold_start": True},
              "error": None if status == "succeeded" else
              {"code": "TIMEOUT", "stage": "recognition"}}
    return manifest, item, identity, result


def test_historical_ram_policy_cannot_start_new_candidate_work(tmp_path):
    manifest, _, _, _ = candidate_fixture(tmp_path)
    common.require_current_policy(manifest)
    historical = {**manifest, "schema_version": 1, "resource_policy": common.LEGACY_POLICY}
    with pytest.raises(ValueError, match="historical 75% RAM policy"):
        common.require_current_policy(historical)


def test_selection_is_deterministic_and_keeps_whole_groups():
    rows = frozen_smb_rows(common.WORKSPACE, "smb-pianoform")
    groups, chosen = common.select_groups(rows)
    reverse_groups, _ = common.select_groups(list(reversed(rows)))
    assert groups == reverse_groups
    assert len(groups) == 18 and len(chosen) == 59
    assert groups[0] == "chopin/mazurka_51"
    selected_ids = {row["id"] for row in chosen}
    assert {row["composition_group"] for row in chosen} == set(groups)
    assert not {row["composition_group"] for row in rows if row["id"] not in selected_ids} & set(groups)
    counts = {group: sum(row["composition_group"] == group for row in chosen) for group in groups}
    assert sum(1 <= count <= 2 for count in counts.values()) == 7
    assert sum(3 <= count <= 4 for count in counts.values()) == 8
    assert sum(count >= 5 for count in counts.values()) == 3


def test_selection_rejects_changed_frozen_coverage():
    rows = frozen_smb_rows(common.WORKSPACE, "smb-pianoform")
    with pytest.raises(ValueError):
        common.select_groups(rows[:-1])
    with pytest.raises(ValueError, match="Duplicate"):
        common.select_groups([*rows, rows[0]])


def test_atomic_completed_outcomes_preserve_typed_failure_and_artifact_hashes(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "WORKSPACE", tmp_path)
    for status in ("succeeded", "failed"):
        _, _, identity, result = candidate_fixture(tmp_path, status)
        destination = tmp_path / status / "complete"
        common.commit_completed(destination, identity, result, {"origin": "fixture"})
        assert common.verify_completed(destination, identity)["status"] == status
        with pytest.raises(FileExistsError):
            common.commit_completed(destination, identity, result, {"origin": "fixture"})
        assert not list(destination.parent.glob(".*.tmp"))
    (tmp_path / "musicxml").write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="artifact"):
        common.verify_completed(tmp_path / "succeeded/complete", identity)


def test_atomic_completed_outcome_retries_transient_windows_rename_denial(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "WORKSPACE", tmp_path)
    _, _, identity, result = candidate_fixture(tmp_path)
    destination = tmp_path / "completed"
    original_rename = Path.rename
    attempts = []
    monkeypatch.setattr(common.time, "sleep", lambda seconds: None)

    def intermittent_rename(source, target):
        attempts.append(source)
        if len(attempts) <= 2:
            raise PermissionError(5, "transient Windows directory lock")
        return original_rename(source, target)

    monkeypatch.setattr(Path, "rename", intermittent_rename)
    common.commit_completed(destination, identity, result, {})
    assert len(attempts) == 3
    assert common.verify_completed(destination, identity)["status"] == "succeeded"


def test_rejects_incomplete_or_false_success(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "WORKSPACE", tmp_path)
    _, _, identity, result = candidate_fixture(tmp_path)
    result["artifacts"] = []
    with pytest.raises(ValueError, match="required artifacts"):
        common.commit_completed(tmp_path / "completed", identity, result, {})
    result["status"] = "pending"
    with pytest.raises(ValueError, match="identity or status"):
        common.commit_completed(tmp_path / "completed", identity, result, {})
    assert not (tmp_path / "completed").exists()


def test_staged_result_promotes_without_duplicate_inference(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "WORKSPACE", tmp_path)
    monkeypatch.setattr(screening_run, "WORKSPACE", tmp_path)
    _, _, identity, result = candidate_fixture(tmp_path)
    attempt = tmp_path / "attempt"
    attempt.mkdir()
    common.write_new(attempt / "attempt.json", {"identity": identity})
    common.write_new(attempt / "staged-result.json", result)
    completed = tmp_path / "completed/item"
    assert screening_run.promote_staged(attempt, completed, identity)
    assert common.verify_completed(completed, identity)["status"] == "succeeded"


def test_model_timeout_scores_but_runtime_failure_stays_pending(tmp_path):
    _, _, _, result = candidate_fixture(tmp_path, "failed")
    result["exit_status"] = 124
    assert screening_run.is_scored_model_outcome(result)
    result["exit_status"] = 127
    assert not screening_run.is_scored_model_outcome(result)
    result["exit_status"] = 1
    result["error"] = {"code": "OSError", "stage": "adapter"}
    assert not screening_run.is_scored_model_outcome(result)


def test_development_admission_checks_identity_and_artifact_hashes(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "WORKSPACE", tmp_path)
    monkeypatch.setattr(screening_admit, "WORKSPACE", tmp_path)
    manifest, item, _, result = candidate_fixture(tmp_path)
    manifest["resource_policy"] = common.POLICY
    manifest["candidates"]["homr_page"]["identity"]["adapter_config"] = {
        "settings": {"cpu_affinity_count": 8}}
    result.update(measurement_path="complete_document")
    report = tmp_path / "development.json"
    common.write_new(report, result)
    monkeypatch.setattr(screening_admit, "allowed_development_pages",
                        lambda: {"item": {"image_path": "image.png", "image_sha256": "a" * 64,
                                          "composition_group": "composition"}})
    (tmp_path / "image.png").write_bytes(b"input")
    result["provenance"]["input_sha256"] = sha256_file(tmp_path / "image.png")
    allowed = screening_admit.allowed_development_pages()
    allowed["item"]["image_sha256"] = result["provenance"]["input_sha256"]
    monkeypatch.setattr(screening_admit, "allowed_development_pages", lambda: allowed)
    report.write_text(json.dumps(result))
    sidecar = report.with_suffix(".identity.json")
    common.write_new(sidecar, {"item_id": "item", "input_sha256": allowed["item"]["image_sha256"],
                               "adapter_config_sha256": result["adapter_config_sha256"],
                               "report_sha256": sha256_file(report),
                               "resource_policy_sha256": common.digest(common.POLICY),
                               "priority": "below_normal", "cpu_affinity_count": 8})
    checked, checked_sidecar = screening_admit.validate_development_report(
        manifest, "homr_page", report)
    assert checked["status"] == "succeeded" and checked_sidecar == sidecar
    (tmp_path / "musicxml").write_text("changed")
    with pytest.raises(ValueError, match="artifact"):
        screening_admit.validate_development_report(manifest, "homr_page", report)


@pytest.mark.parametrize("reason", ["resource_interruption", "session_limit"])
def test_interrupted_staged_result_remains_pending(tmp_path, monkeypatch, reason):
    monkeypatch.setattr(common, "WORKSPACE", tmp_path)
    monkeypatch.setattr(screening_run, "WORKSPACE", tmp_path)
    _, _, identity, result = candidate_fixture(tmp_path)
    attempt = tmp_path / "attempt"
    attempt.mkdir()
    common.write_new(attempt / "attempt.json", {"identity": identity})
    common.write_new(attempt / "staged-result.json", result)
    common.write_new(attempt / "outcome.json", {"reason": reason, "worker_exit": 1})
    destination = tmp_path / "completed/item"
    assert not screening_run.promote_staged(attempt, destination, identity)
    assert not destination.exists()


def test_lock_refuses_duplicate_and_requires_checked_stale_recovery(tmp_path):
    lock = screening_run.acquire_lock(tmp_path)
    with pytest.raises(RuntimeError, match="still live"):
        screening_run.acquire_lock(tmp_path)
    screening_run.release_lock(lock)
    common.write_new(tmp_path / "worker.lock", {"pid": 999999999, "creation_time": 1})
    with pytest.raises(RuntimeError, match="Stale lock"):
        screening_run.acquire_lock(tmp_path)
    recovered = screening_run.acquire_lock(tmp_path, recover_stale=True)
    assert len(list(tmp_path.glob("worker-lock-retired-*.json"))) == 1
    screening_run.release_lock(recovered)


def test_session_limit_is_cumulative_and_counts_interruption(tmp_path):
    path, _ = screening_run.session_budget(tmp_path, "bounded-run")
    state = common.read_json(path)
    state["used_seconds"] = 14370
    state["active_since_utc"] = None
    screening_run.replace_json(path, state)
    with pytest.raises(RuntimeError, match="Four-hour"):
        screening_run.session_budget(tmp_path, "bounded-run")
    state["used_seconds"] = 0
    state["active_since_utc"] = "2026-09-26T00:00:00+00:00"
    screening_run.replace_json(path, state)
    with pytest.raises(RuntimeError, match="Four-hour"):
        screening_run.session_budget(tmp_path, "bounded-run")


def test_score_requires_every_completed_item_before_scoring(tmp_path):
    manifest, item, _, _ = candidate_fixture(tmp_path)
    manifest["items"] = [item]
    with pytest.raises(RuntimeError, match="pending"):
        screening_score.require_complete_results(tmp_path, manifest, "homr_page")


def test_score_publication_retries_and_accepts_preserved_legacy_identity(tmp_path, monkeypatch):
    current = {"item_id": "item", "runner_sha256": sha256_file(Path(screening_score.__file__)),
               "sample_sha256": "a" * 64}
    legacy = {**current, "runner_sha256": screening_score.LEGACY_SCORE_RUNNER_SHA256}
    original_rename = Path.rename
    attempts = []
    monkeypatch.setattr(common.time, "sleep", lambda seconds: None)

    def intermittent_rename(source, destination):
        attempts.append(source)
        if len(attempts) <= 2:
            raise PermissionError(5, "transient Windows directory lock")
        return original_rename(source, destination)

    monkeypatch.setattr(Path, "rename", intermittent_rename)
    destination = tmp_path / "score"
    screening_score.commit_score(destination, legacy, {"item_id": "item", "status": "failed"})
    assert len(attempts) == 3
    assert screening_score.verify_score(destination, current)["status"] == "failed"
    with pytest.raises(ValueError, match="identity"):
        screening_score.verify_score(destination, {**current, "item_id": "other"})


def test_scoring_failure_agrees_with_frozen_scorer(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "WORKSPACE", tmp_path)
    _, _, identity, result = candidate_fixture(tmp_path, "failed")
    completed = tmp_path / "complete"
    common.commit_completed(completed, identity, result, {})
    reference = {"item_id": "item", "composition_group": "composition", "image_sha256": "a" * 64,
                 "notes": [{"midi_pitch": 60, "onset": "0", "duration": "1",
                            "staff": 0, "voice": "1"}], "measure_boundaries": ["0", "1"]}
    actual = score_result(common.verify_completed(completed, identity), reference, tmp_path)
    assert actual["status"] == "failed"
    assert actual["onset_duration_f1"] == 0.0
    assert actual["failure_penalized_omr_ned"] == 1.0
    assert actual["missing_note_count"] == 1


def test_score_worker_matches_frozen_scorer_on_completed_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "WORKSPACE", tmp_path)
    monkeypatch.setattr(screening_score, "WORKSPACE", tmp_path)
    monkeypatch.setattr(screening_score, "output_root", lambda path: tmp_path)
    manifest, item, _, result = candidate_fixture(tmp_path, "failed")
    reference = {"item_id": item["id"], "composition_group": item["composition_group"],
                 "image_sha256": item["image_sha256"],
                 "notes": [{"midi_pitch": 60, "onset": "0", "duration": "1",
                            "staff": 0, "voice": "1"}], "measure_boundaries": ["0", "1"]}
    reference_path = tmp_path / "reference.json"
    common.write_new(reference_path, reference)
    item.update(reference_path="reference.json", reference_sha256=sha256_file(reference_path))
    manifest["items"] = [item]
    identity = common.result_identity(manifest, "homr_page", item)
    result["provenance"]["timing_source"] = "screening_complete_path"
    completed = common.completed_path(tmp_path, "homr_page", item["id"], "d" * 64)
    common.commit_completed(completed, identity, result, {})
    monkeypatch.setattr(screening_score, "verify_manifest", lambda path: manifest)
    attempt = tmp_path / "scoring-attempt"
    attempt.mkdir()
    screening_score.score_worker(tmp_path / "manifest.json", "homr_page", 0, attempt)
    observed = common.read_json(attempt / "staged-score.json")
    expected = score_result(result, reference, tmp_path)
    assert {key: value for key, value in observed.items() if key != "timing_source"} == expected
    assert observed["timing_source"] == "screening_complete_path"


def test_score_worker_matches_frozen_scorer_on_identical_notes(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from sheet2play_omr import phase3_scoring

    monkeypatch.setattr(common, "WORKSPACE", tmp_path)
    monkeypatch.setattr(screening_score, "WORKSPACE", tmp_path)
    monkeypatch.setattr(screening_score, "output_root", lambda path: tmp_path)
    monkeypatch.setattr(phase3_scoring, "score_pair",
                        lambda *args: SimpleNamespace(score=0.25))
    manifest, item, _, result = candidate_fixture(tmp_path)
    notes = [{"midi_pitch": 60, "onset": "0", "duration": "1", "staff": 0, "voice": "1"}]
    canonical_path = tmp_path / "canonical_events"
    canonical_path.write_text(json.dumps({"notes": notes}))
    artifact = next(a for a in result["artifacts"] if a["role"] == "canonical_events")
    artifact.update(bytes=canonical_path.stat().st_size, sha256=sha256_file(canonical_path))
    reference_xml = tmp_path / "reference.musicxml"
    reference_xml.write_text("<score-partwise/>")
    reference = {"item_id": item["id"], "composition_group": item["composition_group"],
                 "image_sha256": item["image_sha256"], "notes": notes,
                 "reference_musicxml": "reference.musicxml",
                 "reference_musicxml_sha256": sha256_file(reference_xml),
                 "measure_boundaries": ["0", "1"]}
    reference_path = tmp_path / "reference.json"
    common.write_new(reference_path, reference)
    item.update(reference_path="reference.json", reference_sha256=sha256_file(reference_path))
    manifest["items"] = [item]
    completed = common.completed_path(tmp_path, "homr_page", item["id"], "d" * 64)
    common.commit_completed(completed, common.result_identity(manifest, "homr_page", item), result, {})
    monkeypatch.setattr(screening_score, "verify_manifest", lambda path: manifest)
    attempt = tmp_path / "score-attempt"
    attempt.mkdir()
    screening_score.score_worker(tmp_path / "manifest.json", "homr_page", 0, attempt)
    observed = common.read_json(attempt / "staged-score.json")
    expected = score_result(result, reference, tmp_path)
    assert {key: value for key, value in observed.items() if key != "timing_source"} == expected
    assert observed["onset_duration_f1"] == 1.0
    assert observed["failure_penalized_omr_ned"] == 0.25


def test_chunk_cannot_exceed_five_pages(tmp_path):
    with pytest.raises(ValueError, match="chunk"):
        screening_run.run(tmp_path / "manifest.json", "homr_page", tmp_path / "admission.json",
                          "session", 1, 6, False, False)


def test_paired_bootstrap_and_holm_use_complete_compositions():
    left = [{"item_id": f"item-{n}", "composition_group": f"g-{n}",
             "onset_duration_f1": 0.8} for n in range(18)]
    right = [{**row, "onset_duration_f1": 0.5} for row in left]
    first = screening_report.paired_difference(left, right, 20260926, 200)
    second = screening_report.paired_difference(left, right, 20260926, 200)
    assert first == second
    assert first["primary_f1_difference"] == pytest.approx(0.3)
    assert first["bootstrap_95_percent_interval"] == pytest.approx([0.3, 0.3])
    assert screening_report.holm_adjust({"a": 0.01, "b": 0.03}) == {
        "a": 0.02, "b": 0.03}
    with pytest.raises(ValueError, match="item sets"):
        screening_report.paired_difference(left[:-1], right, 20260926, 10)


def test_report_keeps_missing_candidates_explicit(tmp_path, monkeypatch):
    manifest = {"seed": "20260926", "sample_sha256": "a" * 64,
                "items": [{"id": f"item-{n}"} for n in range(18)],
                "selected_groups": [f"g-{n}" for n in range(18)],
                "candidates": {"homr_page": {"status": "ready"},
                               "fine_tuned_homr": {"status": "blocked_export_identity_mismatch"}}}
    rows = [{"item_id": f"item-{n}", "composition_group": f"g-{n}",
             "onset_duration_f1": 0.5} for n in range(18)]
    summary = {"composition_macro": {"onset_duration_f1": 0.5,
                                     "onset_f1": 0.6, "pitch_f1": 0.7},
               "failure_rate": 0.0, "failure_penalized_omr_ned_mean": 0.2,
               "status_counts": {"succeeded": 18}, "error_code_stage_counts": {},
               "valid_output_omr_ned_count": 18,
               "failure_penalized_omr_ned_count": 18,
               "omr_ned_scoring_error_count": 0,
               "failure_penalized_omr_ned_complete": True,
               "missing_note_count": 0, "extra_note_count": 0,
               "duration_classification": {"balanced_accuracy": 1.0, "macro_f1": 1.0,
                                           "majority_baseline_accuracy": 0.5,
                                           "degenerate_single_class_predictor": False,
                                           "confusion_matrix": []},
               "latency_seconds": {"median": 1.0, "p95": 1.0,
                                   "comparable_page_count": 18,
                                   "excluded_noncomparable_page_count": 0},
               "peak_ram_bytes_max": 100, "peak_vram_bytes_max": 200,
               "training_overlap": {"homr_page": ["unknown"]}}
    monkeypatch.setattr(screening_report, "verified_candidate",
                        lambda root, manifest, candidate: (rows, summary, {"sha256": "b" * 64}))
    report = screening_report.build_report(manifest, tmp_path, ["homr_page"], "interim-homr")
    assert report["paired"] == {}
    assert report["missing_or_deferred_candidates"]["fine_tuned_homr"] == "blocked_export_identity_mismatch"
    assert "0.5000" in screening_report.markdown(report)
