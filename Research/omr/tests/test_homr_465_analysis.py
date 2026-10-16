from __future__ import annotations

from fractions import Fraction
import json

import pytest

import homr_465_analyze as analysis
from homr_465_common import write_or_verify
from musicxml_normalizer import MusicXmlNormalizationError
from sheet2play_omr.metrics import MetricNote


def note(pitch: int, onset: int) -> MetricNote:
    return MetricNote(pitch, Fraction(onset), Fraction(1), 0, "1")


def test_failed_export_is_never_normalized(monkeypatch, tmp_path):
    def forbidden(path):
        raise AssertionError("A failed native export must receive failure-zero scoring")
    monkeypatch.setattr(analysis, "normalized_notes", forbidden)
    assert analysis.converted_notes(tmp_path, "failed") == ([], "failed", None)


def test_invalid_musicxml_becomes_explicit_conversion_failure(monkeypatch, tmp_path):
    def invalid(path):
        raise MusicXmlNormalizationError("bad duration")
    monkeypatch.setattr(analysis, "normalized_notes", invalid)
    notes, status, error = analysis.converted_notes(tmp_path, "complete")
    assert notes == [] and status == "conversion_failed" and "bad duration" in error


def test_corrected_and_regressed_measures_keep_independent_clocks():
    expected = [note(60, 0), note(62, 4)]
    candidate = [note(60, 0), note(63, 4)]
    baseline = [{"pitch": 61, "onset": "0", "duration": "1"},
                {"pitch": 62, "onset": "4", "duration": "1"}]
    changes = analysis.measure_changes(candidate, baseline, expected, [{"start": "0"}, {"start": "4"}])
    assert changes[0]["corrected"] and not changes[0]["regressed"]
    assert changes[1]["regressed"] and not changes[1]["corrected"]


def test_interrupted_scoring_reuses_only_identical_derived_evidence(tmp_path):
    path = tmp_path / "score.json"
    write_or_verify(path, {"f1": 0.5, "identity": "original"})
    original = path.read_bytes()
    write_or_verify(path, json.loads(original))
    assert path.read_bytes() == original
    with pytest.raises(ValueError, match="differs"):
        write_or_verify(path, {"f1": 0.6, "identity": "original"})
