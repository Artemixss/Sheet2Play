from __future__ import annotations

import json
import warnings
from pathlib import Path

import phase1
import pytest


def write_smb_fixture(tmp_path: Path, *, duplicate: bool = False) -> tuple[Path, Path]:
    rows = []
    images = {}
    for index in range(685):
        texture = "Pianoform" if index < 469 else "Other"
        file_name = "test/page-0.png" if duplicate and index == 1 else f"test/page-{index}.png"
        rows.append(
            {
                "file_name": file_name,
                "original_score": f"composer/score-{index // 2}",
                "page_texture": texture,
                "page": str(index),
                "regions": [
                    {
                        "kern": "**kern\n*M4/4\n=1\n4c\n4d\n4e\n4f\n*-\n",
                    }
                ],
            }
        )
        images[file_name] = {"sha256": f"{index:064x}"[-64:], "size": index + 1}
    if duplicate:
        images["test/unselected-extra.png"] = {"sha256": "f" * 64, "size": 1}
    metadata = tmp_path / "metadata.jsonl"
    metadata.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    hashes = tmp_path / "hashes.json"
    hashes.write_text(
        json.dumps({"revision": phase1.SMB_REVISION, "images": images}), encoding="utf-8"
    )
    return metadata, hashes


def test_freeze_smb_filters_case_insensitively_and_validates_kern(
    tmp_path: Path, monkeypatch
) -> None:
    metadata, hashes = write_smb_fixture(tmp_path)
    monkeypatch.setattr(phase1, "parse_kern", lambda _: None)

    frozen, exclusions = phase1.freeze_smb(metadata, hashes)

    assert len(frozen) == 469
    assert exclusions == []
    assert all(row["source_revision"] == phase1.SMB_REVISION for row in frozen)
    assert all(row["image_sha256"] for row in frozen)


def test_freeze_smb_complete_includes_every_texture(tmp_path: Path, monkeypatch) -> None:
    metadata, hashes = write_smb_fixture(tmp_path)
    monkeypatch.setattr(phase1, "parse_kern", lambda _: None)

    frozen, exclusions = phase1.freeze_smb(
        metadata,
        hashes,
        collection="smb-complete",
        texture=None,
    )

    assert len(frozen) == 685
    assert exclusions == []
    assert {row["page_texture"] for row in frozen} == {"Pianoform", "Other"}


def test_freeze_smb_fails_closed_on_missing_image_hash(tmp_path: Path, monkeypatch) -> None:
    metadata, hashes = write_smb_fixture(tmp_path)
    document = json.loads(hashes.read_text(encoding="utf-8"))
    document["images"].pop("test/page-0.png")
    document["images"]["test/replacement.png"] = {"sha256": "f" * 64, "size": 1}
    hashes.write_text(json.dumps(document), encoding="utf-8")
    monkeypatch.setattr(phase1, "parse_kern", lambda _: None)

    try:
        phase1.freeze_smb(metadata, hashes)
    except ValueError as error:
        assert "image hash is missing" in str(error)
    else:
        raise AssertionError("missing selected image hash was accepted")


def test_freeze_smb_rejects_duplicate_identifiers(tmp_path: Path, monkeypatch) -> None:
    metadata, hashes = write_smb_fixture(tmp_path, duplicate=True)
    monkeypatch.setattr(phase1, "parse_kern", lambda _: None)

    try:
        phase1.freeze_smb(metadata, hashes)
    except ValueError as error:
        assert "duplicate file_name" in str(error)
    else:
        raise AssertionError("duplicate SMB identifier was accepted")


def test_freeze_smb_ledgers_malformed_reference(tmp_path: Path, monkeypatch) -> None:
    metadata, hashes = write_smb_fixture(tmp_path)

    def parse(value: str) -> None:
        if value.startswith("bad"):
            raise ValueError("broken rhythm")

    rows = phase1.load_jsonl(metadata)
    rows[0]["regions"][0]["kern"] = "bad reference"
    metadata.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    monkeypatch.setattr(phase1, "parse_kern", parse)

    frozen, exclusions = phase1.freeze_smb(metadata, hashes)

    assert len(frozen) == 468
    assert len(exclusions) == 1
    assert exclusions[0]["reason"] == "reference validation failed"


def test_freeze_smb_resumes_after_interruption_and_reuses_completed_cache(
    tmp_path: Path, monkeypatch
) -> None:
    metadata, hashes = write_smb_fixture(tmp_path)
    cache = tmp_path / "validation-cache.json"
    first_run_calls = 0

    def interrupting_parse(_: str) -> None:
        nonlocal first_run_calls
        first_run_calls += 1
        if first_run_calls == 11:
            raise KeyboardInterrupt

    monkeypatch.setattr(phase1, "parse_kern", interrupting_parse)
    with pytest.raises(KeyboardInterrupt):
        phase1.freeze_smb(metadata, hashes, cache_path=cache)

    cached = json.loads(cache.read_text(encoding="utf-8"))
    assert len(cached["entries"]) == 10

    resumed_calls = 0

    def resumed_parse(_: str) -> None:
        nonlocal resumed_calls
        resumed_calls += 1

    monkeypatch.setattr(phase1, "parse_kern", resumed_parse)
    frozen, exclusions = phase1.freeze_smb(metadata, hashes, cache_path=cache)

    assert len(frozen) == 469
    assert exclusions == []
    assert resumed_calls == 459

    def unexpected_parse(_: str) -> None:
        raise AssertionError("a valid completed cache entry was revalidated")

    monkeypatch.setattr(phase1, "parse_kern", unexpected_parse)
    frozen, exclusions = phase1.freeze_smb(metadata, hashes, cache_path=cache)

    assert len(frozen) == 469
    assert exclusions == []


def test_freeze_smb_rejects_stale_validator_cache(tmp_path: Path, monkeypatch) -> None:
    metadata, hashes = write_smb_fixture(tmp_path)
    cache = tmp_path / "validation-cache.json"
    monkeypatch.setattr(phase1, "parse_kern", lambda _: None)
    phase1.freeze_smb(metadata, hashes, cache_path=cache)
    cached = json.loads(cache.read_text(encoding="utf-8"))
    cached["validator_signature"] = "0" * 64
    cache.write_text(json.dumps(cached), encoding="utf-8")
    validation_calls = 0

    def counting_parse(_: str) -> None:
        nonlocal validation_calls
        validation_calls += 1

    monkeypatch.setattr(phase1, "parse_kern", counting_parse)
    frozen, exclusions = phase1.freeze_smb(metadata, hashes, cache_path=cache)

    assert len(frozen) == 469
    assert exclusions == []
    assert validation_calls == 469


def test_freeze_smb_treats_parser_output_as_validation_failure(
    tmp_path: Path, monkeypatch
) -> None:
    metadata, hashes = write_smb_fixture(tmp_path)
    calls = 0

    def warning_parse(_: str) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            print("negative offset repaired")

    monkeypatch.setattr(phase1, "parse_kern", warning_parse)
    frozen, exclusions = phase1.freeze_smb(metadata, hashes)

    assert len(frozen) == 468
    assert len(exclusions) == 1
    assert exclusions[0]["details"] == ["region 0: parser warning: negative offset repaired"]


def test_freeze_smb_captures_repeated_python_warnings(tmp_path: Path, monkeypatch) -> None:
    metadata, hashes = write_smb_fixture(tmp_path)

    def warning_parse(_: str) -> None:
        warnings.warn("repeated conversion repair", UserWarning)

    monkeypatch.setattr(phase1, "parse_kern", warning_parse)
    frozen, exclusions = phase1.freeze_smb(metadata, hashes)

    assert frozen == []
    assert len(exclusions) == 469
    assert all("repeated conversion repair" in row["details"][0] for row in exclusions)


def test_freeze_olimpic_ledgers_missing_files(tmp_path: Path) -> None:
    manifest = tmp_path / "olimpic.jsonl"
    manifest.write_text(
        json.dumps(
            {
                "identifier": "score/page-system",
                "score_id": "score",
                "image": str(tmp_path / "missing.png"),
                "musicxml": str(tmp_path / "missing.musicxml"),
            }
        )
        + "\n",
        encoding="utf-8",
    )

    frozen, exclusions = phase1.freeze_olimpic(manifest, "test")

    assert frozen == []
    assert exclusions == [
        {"collection": "test", "id": "score/page-system", "reason": "missing image, musicxml"}
    ]


def test_subset_check_fails_closed() -> None:
    try:
        phase1.require_subset({"a", "missing"}, {"a"}, "canary")
    except ValueError as error:
        assert "missing" in str(error)
    else:
        raise AssertionError("non-subset canary was accepted")


@pytest.mark.parametrize(
    "message",
    [
        "Could not import wedge: Error in getting DynamicWedges",
        "Could not import pedal: Error in getting PedalMark",
        "Could not import octave-shift: Error in getting Ottava",
        "Line <dashes> stop without start",
        "Line <bracket> stop without start",
    ],
)
def test_olimpic_notation_spanner_warnings_are_recorded_but_non_fatal(message: str) -> None:
    assert phase1.olimpic_warning_is_fatal(message) is False


@pytest.mark.parametrize(
    "message",
    [
        "Warning: measure 67 is overfull",
        "unknown future parser warning",
    ],
)
def test_olimpic_timing_and_unknown_warnings_fail_closed(message: str) -> None:
    assert phase1.olimpic_warning_is_fatal(message) is True


def test_historical_results_are_never_implicitly_ranking_eligible() -> None:
    audit = phase1.historical_audit()
    assert audit
    assert not any(entry["ranking_eligible"] for entry in audit)


def test_protocol_freezes_failure_and_repeat_semantics() -> None:
    protocol = phase1.scoring_protocol()
    assert protocol["normalization"]["expand_repeats"] is False
    assert protocol["normalization"]["grace_notes_in_primary"] is False
    assert protocol["failure_policy"]["failed_prediction_primary_f1"] == 0.0
    assert protocol["statistics"]["bootstrap_group"] == "composition_group"
    assert protocol["duration_classification"]["report_confusion_matrix"] is True
    assert protocol["duration_classification"]["report_majority_baseline"] is True
    assert protocol["duration_classification"]["reject_degenerate_single_class_predictor"] is True
    assert "source MusicXML to app control" in protocol["evaluation_machinery_fixture_contract"]


def test_evaluation_metadata_requires_features_and_every_candidate_overlap() -> None:
    row = {
        "id": "fixture",
        "composition_group": "composition",
        "ground_truth_provenance": "fixture truth",
        "notation_features": {"has_ties": False},
        "page_system_identity": {"page": "1"},
        "printed_or_scanned": "printed",
        "source_revision": "revision",
        "training_overlap_by_candidate": phase1.training_overlap_by_candidate("smb-pianoform"),
    }
    phase1.require_evaluation_metadata([row], "fixture")

    row["training_overlap_by_candidate"].pop("audiveris")
    with pytest.raises(ValueError, match="candidate-specific overlap"):
        phase1.require_evaluation_metadata([row], "fixture")


def test_phase1_checklist_stops_before_candidate_work() -> None:
    statuses = {
        item["requirement"]: item["status"] for item in phase1.phase1_plan_checklist()
    }
    assert statuses["historical results audited"] == "passed"
    assert statuses["source MusicXML to app control"] == "passed"
    assert statuses["candidate inference or adapter work"] == "not_started_phase_2"
