from fractions import Fraction
import json
from pathlib import Path

import pytest

import timing_repair
from sheet2play_omr.corrected_scoring import metric_notes, score_cached
from sheet2play_omr.metrics import calculate_note_metrics
from sheet2play_omr.timing import rational_time
from test_phase3_scoring import _reference, _result


@pytest.mark.parametrize("value,expected", [
    ("0.3333333333333333", Fraction(1, 3)),
    ("0.16666666666666666", Fraction(1, 6)),
    ("14.666666666666666", Fraction(44, 3)),
    ("1/5000", Fraction(1, 5000)),
    ("0.0002", Fraction(1, 5000)),
    ("0.33334", Fraction(16667, 50000)),
])
def test_reconstructs_only_serialization_roundoff(value, expected):
    assert rational_time(value) == expected


@pytest.mark.parametrize("value", ["nan", "inf", "1/0", True, None])
def test_invalid_time(value):
    with pytest.raises((ValueError, ZeroDivisionError)):
        rational_time(value)


def test_symmetric_reading_preserves_real_error_chords_and_voices():
    truth = {"notes": [
        {"midi_pitch": pitch, "onset": "1/3", "duration": "1/6", "staff": staff, "voice": voice}
        for pitch, staff, voice in [(60, 0, "1"), (64, 0, "2"), (48, 1, "1")]]}
    decimal = {"notes": [{**row, "onset": "0.3333333333333333", "duration": "0.16666666666666666"}
                         for row in truth["notes"]]}
    assert calculate_note_metrics(metric_notes(decimal), metric_notes(truth)).onset_duration_f1 == 1
    decimal["notes"][0]["onset"] = "0.33334"
    assert calculate_note_metrics(metric_notes(decimal), metric_notes(truth)).onset_duration_f1 == pytest.approx(2 / 3)


def test_failure_and_invalid_output_accounting(tmp_path):
    reference = _reference(tmp_path)
    failed = _result(tmp_path, status="failed")
    old = {"item_id": "synthetic", "candidate_id": "test", "status": "failed",
           "elapsed_seconds": 2.5, "error": failed["error"]}
    score = score_cached(failed, reference, tmp_path, old)
    assert score["onset_duration_f1"] == 0
    assert score["missing_note_count"] == 2
    assert score["coverage"]["per_staff"]["0"]["recall"] == 0
    assert score["error"]["code"] == "MISSING_SYSTEM"
    result = _result(tmp_path, status="succeeded", notes=[])
    score = score_cached(result, reference, tmp_path, {**old, "status": "succeeded"})
    assert score["error"]["code"] == "INVALID_CANONICAL_OUTPUT"
    assert score["onset_duration_f1"] == 0


def test_timing_changes_leave_ned_runtime_and_pitch_counts_unchanged(tmp_path):
    reference = _reference(tmp_path)
    reference["notes"][0]["duration"] = "1/3"
    notes = [{**row} for row in reference["notes"]]
    notes[0]["duration"] = "0.3333333333333333"
    result = _result(tmp_path, status="succeeded", notes=notes)
    old = {"item_id": "synthetic", "candidate_id": "test", "status": "succeeded",
           "error": None, "omr_ned": 0.25, "failure_penalized_omr_ned": 0.25,
           "omr_ned_status": "valid", "elapsed_seconds": 12}
    score = score_cached(result, reference, tmp_path, old)
    assert score["onset_duration_f1"] == score["pitch_f1"] == 1
    assert score["missing_note_count"] == score["extra_note_count"] == 0
    assert score["elapsed_seconds"] == 12
    assert score["omr_ned"] == 0.25
    result["candidate_id"] = "other"
    with pytest.raises(ValueError, match="identities differ"):
        score_cached(result, reference, tmp_path, old)


def test_exact_musicxml_divisions_pickup_meter_change_chord_voice_and_system_tie(tmp_path):
    import sys
    from music21 import converter
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "Bridge"))
    from musicxml_normalizer import normalize_musicxml
    xml = '''<score-partwise version="4.0"><part-list><score-part id="P1"><part-name>Piano</part-name></score-part></part-list><part id="P1">
    <measure number="0" implicit="yes"><attributes><divisions>3</divisions><time><beats>4</beats><beat-type>4</beat-type></time><clef><sign>G</sign><line>2</line></clef></attributes>
    <note><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration><tie type="start"/><voice>1</voice><type>eighth</type><time-modification><actual-notes>3</actual-notes><normal-notes>2</normal-notes></time-modification></note>
    <note><chord/><pitch><step>E</step><octave>4</octave></pitch><duration>1</duration><tie type="start"/><voice>1</voice><type>eighth</type></note>
    <backup><duration>1</duration></backup><note><pitch><step>G</step><octave>3</octave></pitch><duration>1</duration><voice>2</voice><type>eighth</type></note></measure>
    <measure number="1"><print new-system="yes"/><attributes><time><beats>3</beats><beat-type>4</beat-type></time></attributes>
    <note><pitch><step>C</step><octave>4</octave></pitch><duration>2</duration><tie type="stop"/><voice>1</voice><type>quarter</type></note>
    <note><chord/><pitch><step>E</step><octave>4</octave></pitch><duration>2</duration><tie type="stop"/><voice>1</voice><type>quarter</type></note>
    <note><pitch><step>D</step><octave>4</octave></pitch><duration>7</duration><voice>1</voice><type>half</type></note></measure></part></score-partwise>'''
    path = tmp_path / "exact.musicxml"
    path.write_text(xml, encoding="utf-8")
    normalized = normalize_musicxml(path, expand_repeats=False, skip_grace_notes=True, force_source=True)
    payload = {"notes": [{"midi_pitch": n.midi_pitch, "onset": str(n.start_beat),
                          "duration": str(n.duration_beats), "staff": n.staff_index,
                          "voice": n.voice_identifier} for n in normalized.notes]}
    actual = {(n.pitch, n.onset, n.duration) for n in metric_notes(payload)}
    # Phase 2 preserves the cached normalizer's split chord ties. The approved
    # Phase-3 investigation owns merging them; each segment retains exact XML time.
    assert actual == {(60, Fraction(0), Fraction(1, 3)), (64, Fraction(0), Fraction(1, 3)),
                      (60, Fraction(1, 3), Fraction(2, 3)), (64, Fraction(1, 3), Fraction(2, 3)),
                      (55, Fraction(0), Fraction(1, 3)), (62, Fraction(1), Fraction(7, 3))}
    parsed = converter.parse(str(path), forceSource=True)
    assert {str(ts.ratioString) for ts in parsed.recurse().getElementsByClass("TimeSignature")} == {"4/4", "3/4"}


def test_resumption_rejects_changed_bytes(tmp_path):
    path = tmp_path / "identity.json"
    timing_repair.immutable(path, {"a": 1})
    timing_repair.immutable(path, {"a": 1})
    with pytest.raises(ValueError, match="differs"):
        timing_repair.immutable(path, {"a": 2})
