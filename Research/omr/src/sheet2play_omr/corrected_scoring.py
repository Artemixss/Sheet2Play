"""Separate scoring revision; the historical Phase-1 scorer remains frozen."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict
import json
import math
from pathlib import Path
from typing import Any

from . import phase3_scoring as historical
from .adapter_contract import sha256_file
from .metrics import MetricNote, calculate_note_metrics, timeline_span
from .timing import rational_time


def metric_notes(payload: dict[str, Any]) -> list[MetricNote]:
    rows = payload.get("notes")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Canonical event payload contains no sounding notes")
    notes = []
    for row in rows:
        pitch = int(row["midi_pitch"])
        onset, duration = rational_time(row["onset"]), rational_time(row["duration"])
        if not 0 <= pitch <= 127 or onset < 0 or duration <= 0:
            raise ValueError("Canonical note has invalid pitch or rational timing")
        notes.append(MetricNote(pitch, onset, duration, int(row["staff"]), str(row["voice"])))
    return notes


def coverage(predicted: list[MetricNote], expected: list[MetricNote]) -> dict[str, Any]:
    def chords(notes: list[MetricNote]) -> dict:
        groups = defaultdict(Counter)
        for note in notes:
            groups[note.onset][note.pitch] += 1
        return groups
    truth, guesses = chords(expected), chords(predicted)
    targets = {onset: pitches for onset, pitches in truth.items() if sum(pitches.values()) > 1}
    complete = sum(not (pitches - guesses.get(onset, Counter())) for onset, pitches in targets.items())
    by_staff = {}
    for staff in sorted({note.staff for note in expected} | {note.staff for note in predicted}):
        actual = Counter((n.pitch, n.onset, n.duration) for n in expected if n.staff == staff)
        guess = Counter((n.pitch, n.onset, n.duration) for n in predicted if n.staff == staff)
        matched = sum((actual & guess).values())
        by_staff[str(staff)] = {"reference_notes": sum(actual.values()),
                                "predicted_notes": sum(guess.values()), "matched_notes": matched,
                                "recall": matched / sum(actual.values()) if actual else None}
    return {"reference_chords": len(targets), "complete_chords": complete,
            "chord_completeness": complete / len(targets) if targets else None,
            "per_staff": by_staff, "staff_interpretation": "notation staff index; not validated hand labels"}


def score_cached(result: dict[str, Any], reference: dict[str, Any], workspace: Path,
                 old: dict[str, Any]) -> dict[str, Any]:
    """Recompute timing-dependent metrics; caller verifies the old score's provenance."""
    if (result["item_id"] != reference["item_id"] or old["item_id"] != result["item_id"]
            or old["candidate_id"] != result["candidate_id"]
            or result["provenance"]["input_sha256"] != reference["image_sha256"]):
        raise ValueError("Cached score/result/reference identities differ")
    expected = metric_notes(reference)
    reference_xml = workspace / reference["reference_musicxml"]
    if sha256_file(reference_xml) != reference["reference_musicxml_sha256"]:
        raise ValueError("Reference MusicXML changed")
    base = {**old, "schema_version": 2, "timing_policy": "symmetric-rational-4096-roundoff-v1"}
    if result["status"] == "failed":
        return {**historical._failed_score(base, len(expected)), "coverage": coverage([], expected)}
    if result["status"] != "succeeded":
        raise ValueError("Unavailable or unknown outcomes cannot be scored")
    canonical = historical._artifact(result, "canonical_events", workspace)
    historical._artifact(result, "musicxml", workspace)
    try:
        predicted = metric_notes(json.loads(canonical.read_text(encoding="utf-8")))
    except (ValueError, KeyError, TypeError, UnicodeError, ZeroDivisionError, OverflowError) as error:
        return {**historical._failed_score({**base, "status": "failed", "error": {
            "code": "INVALID_CANONICAL_OUTPUT", "stage": "scoring", "message": str(error)[:500]}},
            len(expected)), "coverage": coverage([], expected)}
    metrics = asdict(calculate_note_metrics(predicted, expected))
    if not math.isfinite(metrics["mean_offset_error"]):
        metrics["mean_offset_error"] = None
    actual = Counter((n.pitch, n.onset, n.duration) for n in expected)
    guess = Counter((n.pitch, n.onset, n.duration) for n in predicted)
    boundaries = {**reference, "measure_boundaries": [str(rational_time(v)) for v in reference["measure_boundaries"]]}
    return {**base, **metrics, "predicted_note_count": len(predicted),
            "missing_note_count": sum((actual - guess).values()),
            "extra_note_count": sum((guess - actual).values()),
            "duration": historical._duration_pairs(predicted, expected),
            "timeline_length_error": str(timeline_span(predicted) - timeline_span(expected)),
            "first_divergent_measure": historical._first_divergent_measure(predicted, expected, boundaries),
            "coverage": coverage(predicted, expected)}
