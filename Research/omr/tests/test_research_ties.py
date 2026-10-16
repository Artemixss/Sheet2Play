from dataclasses import replace
from fractions import Fraction as F
from pathlib import Path

import pytest

from sheet2play_omr.research_ties import merge_ties, normalize_ties_exact, verify_midi
from sheet2play_omr.zeus_trace import Segment, normalized_notes

SOURCE = Path(__file__).resolve().parents[1] / "reports/zeus-attribution/phase2/cross-system-chord-tie.musicxml"


def segment(onset=F(0), duration=F(1), ties=(), **changes):
    return replace(Segment(60, onset, duration, 0, "1", "P1", 0, onset, ties), **changes)


def test_exact_reproducer_preserves_independent_voice_and_midi(tmp_path: Path):
    result = normalize_ties_exact(SOURCE)
    assert not result.issues
    assert sorted((n.pitch, n.onset, n.duration) for n in result.notes) == [
        (55, F(0), F(1, 3)), (60, F(0), F(1)), (62, F(1), F(7, 3)), (64, F(0), F(1))]
    assert len(normalized_notes(SOURCE)) == 6
    assert verify_midi(result.notes, tmp_path / "ties.mid")["notes"] == 4


@pytest.mark.parametrize("field,value", [("voice", "2"), ("staff", 1), ("part", "P2")])
def test_simultaneous_same_pitch_retains_identity(field, value):
    notes, issues = merge_ties([segment(ties=("start",)),
        segment(**{field: value}), segment(F(1), ties=("stop",))])
    assert len(notes) == 2 and not issues
    assert sorted(n.duration for n in notes) == [F(1), F(2)]


def test_partial_chord_continuation_and_tuplets():
    notes, issues = merge_ties([segment(duration=F(1, 3), ties=("start",)),
        segment(duration=F(1, 3), pitch=64),
        segment(F(1, 3), F(1, 3), ("stop", "start")),
        segment(F(2, 3), F(1, 3), ("stop",))])
    assert not issues and [(n.pitch, n.duration) for n in notes] == [(60, F(1)), (64, F(1, 3))]


@pytest.mark.parametrize("onset", [F(1, 2), F(2)])
def test_gaps_and_overlaps_do_not_merge(onset):
    notes, issues = merge_ties([segment(ties=("start",)), segment(onset, ties=("stop",))])
    assert len(notes) == 2 and issues


def test_open_and_unmatched_ties_keep_events():
    notes, issues = merge_ties([segment(ties=("stop",)), segment(F(1), ties=("start",))])
    assert len(notes) == 2 and {i["kind"] for i in issues} == {"unmatched_or_noncontiguous_stop", "open_start"}


def test_ambiguous_same_voice_unisons_preserved():
    original = [segment(ties=("start",)), segment(ties=("start",)), segment(F(1), ties=("stop",))]
    notes, issues = merge_ties(original)
    assert len(notes) == 3 and len(issues) == 3


def test_ordinary_repeated_notes_and_chords_preserved(tmp_path: Path):
    original = [segment(), segment(pitch=64), segment(F(1)), segment(F(1), pitch=64)]
    notes, issues = merge_ties(original)
    assert notes == tuple(original) and not issues
    assert verify_midi(notes, tmp_path / "plain.mid")["preserved"]


@pytest.mark.parametrize("ties", [("continue",), ("start", "start")])
def test_unsupported_ties_rejected(ties):
    with pytest.raises(ValueError, match="tie type"):
        merge_ties([segment(ties=ties)])


def test_unsupported_missing_duration_fails_closed(tmp_path: Path):
    path = tmp_path / "invalid.musicxml"
    path.write_text('<score-partwise><part id="P1"><measure><note><rest measure="yes"/></note></measure></part></score-partwise>')
    with pytest.raises(ValueError, match="positive duration"):
        normalize_ties_exact(path)
