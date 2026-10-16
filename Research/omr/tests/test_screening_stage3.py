"""HOMR-only Stage-3 identity and sample-extension checks."""
from __future__ import annotations

from pathlib import Path

import pytest

import screening_common as common
import screening_homr_extension as extension
from sheet2play_omr.adapter_contract import sha256_file


def test_homr_455_extension_preserves_frozen_sample_and_control() -> None:
    base = common.read_json(extension.BASE_MANIFEST)
    extended = extension.build_extended_manifest()
    assert extended["sample_sha256"] == base["sample_sha256"]
    assert extended["items"] == base["items"]
    assert extended["candidates"]["homr_page"] == base["candidates"]["homr_page"]
    assert extended["candidates"]["audiveris_page"] == base["candidates"]["audiveris_page"]
    assert extended["candidates"]["zeus_page"] == base["candidates"]["zeus_page"]
    candidate = extended["candidates"]["homr_455"]
    assert candidate["identity_sha256"] == common.digest(candidate["identity"])
    assert candidate["identity"]["source_revision"] == extension.REVISION


def test_homr_455_environment_matches_pinned_assets() -> None:
    candidate = extension.candidate_identity(sha256_file(common.HERE / "screening_run.py"),
                                             common.threads_limit())
    environment = extension.candidate_environment(candidate["identity"])
    for path_key, hash_key in (
            ("SHEET2PLAY_CANDIDATE_ENCODER", "SHEET2PLAY_CANDIDATE_ENCODER_SHA256"),
            ("SHEET2PLAY_CANDIDATE_DECODER", "SHEET2PLAY_CANDIDATE_DECODER_SHA256"),
            ("S2P_HOMR_455_SEGNET", "S2P_HOMR_455_SEGNET_SHA256")):
        assert sha256_file(Path(environment[path_key])) == environment[hash_key]
    assert environment["S2P_HOMR_455_SOURCE_REVISION"] == extension.REVISION


def test_homr_455_rejects_wrong_source_revision(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(extension, "REVISION", "0" * 40)
    with pytest.raises(ValueError, match="source revision"):
        extension.checked_source_files()
