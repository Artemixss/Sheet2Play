"""Reject changed truth, incompatible score reuse, and stale report boundaries."""
from __future__ import annotations

from copy import deepcopy
import json

import pytest

from screening_consolidated_report import ROSTER, markdown, outcome_counts, same_sample, verified_cpu_score
from screening_cpu_score import commit_score, LEGACY_SCORE_RUNNER_SHA256
from screening_common import read_json


@pytest.mark.parametrize("field", ["items", "scoring_summary_sha256", "scoring_protocol_sha256",
                                   "historical_phase3_freeze_sha256", "selection_algorithm"])
def test_cross_manifest_reuse_rejects_changed_frozen_contract(field):
    manifest = {key: key for key in ("sample_sha256", "selected_groups", "seed", "selection_algorithm",
                "scorer_sha256", "scoring_summary_sha256", "scoring_protocol_sha256",
                "historical_phase3_freeze_sha256")}
    manifest["items"] = [{"id": "page", "reference_sha256": "a" * 64}]
    same_sample(manifest, deepcopy(manifest))
    changed = deepcopy(manifest)
    if field == "items":
        changed[field][0]["reference_sha256"] = "b" * 64
    else:
        changed[field] = "different"
    with pytest.raises(ValueError, match=field):
        same_sample(manifest, changed)


def test_cpu_report_rejects_legacy_runner_and_corrupted_score(tmp_path):
    path = tmp_path / "score"
    identity = {"item_id": "page", "runner_sha256": "a" * 64}
    score = {"item_id": "page", "status": "failed", "error": {"code": "MODEL_FAILED"}}
    commit_score(path, identity, score)
    assert verified_cpu_score(path, identity) == score
    saved = read_json(path / "identity.json")
    (path / "identity.json").write_text(json.dumps({**saved, "runner_sha256": LEGACY_SCORE_RUNNER_SHA256}))
    with pytest.raises(ValueError, match="exact pinned runner"):
        verified_cpu_score(path, identity)
    (path / "identity.json").write_text(json.dumps(identity))
    (path / "score.json").write_text(json.dumps({**score, "status": "succeeded"}))
    with pytest.raises(ValueError, match="Score bytes differ"):
        verified_cpu_score(path, identity)


def test_five_candidate_report_has_separate_confirmation_boundary():
    from screening_consolidated_report import HOMR_REPORT
    report = deepcopy(read_json(HOMR_REPORT))
    for candidate in ROSTER[3:]:
        report["candidate_summaries"][candidate] = deepcopy(report["candidate_summaries"]["homr_page"])
        report["operations"][candidate] = deepcopy(report["operations"]["homr_page"])
        report["practical"][candidate] = deepcopy(report["practical"]["homr_page"])
    report["runtime_inventory_disclosure"] = "Readable runtime pinned"
    report["zeus_route"] = "Neutral route"
    report["deferred"] = {"qwen": "development blocked"}
    report["outcome_counts"] = {}
    text = markdown(report)
    assert "Consolidated canonical Stage 3" in text
    assert "Audiveris and Zeus are deferred" not in text
    assert "Stop for a separate confirmation decision" in text
    assert "full sparse confusion matrices" in text
    for candidate in ROSTER:
        assert f"| {candidate} |" in text


def test_empty_output_and_typed_failure_counts_do_not_drop_generic_failure():
    success = {"status": "succeeded", "predicted_note_count": 0, "omr_ned_status": "valid"}
    rows = [success, {**success, "predicted_note_count": 5, "omr_ned_status": "scoring_error"}]
    for code in ("MUSICXML_EMPTY", "MUSICXML_INVALID", "MODEL_TIMEOUT", "AUDIVERIS_FAILED"):
        rows.append({"status": "failed", "error": {"code": code}, "omr_ned_status": "engine_failed"})
    assert outcome_counts(rows) == {"completed": 6, "succeeded": 2, "failed": 4,
        "successful_empty_output": 1, "typed_empty_output": 1, "typed_invalid_output": 1,
        "typed_timeout": 1, "omr_ned_scoring_error": 1}
