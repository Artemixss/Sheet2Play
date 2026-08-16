from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from typing import Iterable


@dataclass(frozen=True, slots=True)
class MetricNote:
    pitch: int
    onset: Fraction
    duration: Fraction
    staff: int
    voice: str

    @property
    def offset(self) -> Fraction:
        return self.onset + self.duration


@dataclass(frozen=True, slots=True)
class NoteMetrics:
    pitch_f1: float
    onset_f1: float
    onset_duration_f1: float
    mean_offset_error: float
    staff_accuracy: float
    aligned_voice_accuracy: float


def _f1(matches: int, predicted: int, expected: int) -> float:
    if predicted == 0 and expected == 0:
        return 1.0
    if matches == 0:
        return 0.0
    precision = matches / predicted
    recall = matches / expected
    return 2.0 * precision * recall / (precision + recall)


def _counter_matches(left: Counter[object], right: Counter[object]) -> int:
    return sum((left & right).values())


def _exact_pairs(predicted: list[MetricNote], expected: list[MetricNote]) -> list[tuple[MetricNote, MetricNote]]:
    predicted_buckets: dict[tuple[int, Fraction, Fraction], list[MetricNote]] = defaultdict(list)
    expected_buckets: dict[tuple[int, Fraction, Fraction], list[MetricNote]] = defaultdict(list)
    for note in predicted:
        predicted_buckets[(note.pitch, note.onset, note.duration)].append(note)
    for note in expected:
        expected_buckets[(note.pitch, note.onset, note.duration)].append(note)
    pairs: list[tuple[MetricNote, MetricNote]] = []
    for key in sorted(predicted_buckets.keys() & expected_buckets.keys()):
        predictions = sorted(predicted_buckets[key], key=lambda note: (note.staff, note.voice))
        targets = sorted(expected_buckets[key], key=lambda note: (note.staff, note.voice))
        unused = list(targets)
        for prediction in predictions:
            if not unused:
                break
            best_index = min(
                range(len(unused)),
                key=lambda index: (unused[index].staff != prediction.staff, unused[index].voice != prediction.voice),
            )
            pairs.append((prediction, unused.pop(best_index)))
    return pairs


def _best_voice_score(pairs: list[tuple[MetricNote, MetricNote]]) -> int:
    by_staff: dict[tuple[int, int], list[tuple[str, str]]] = defaultdict(list)
    for predicted, expected in pairs:
        by_staff[(predicted.staff, expected.staff)].append((predicted.voice, expected.voice))
    score = 0
    for voice_pairs in by_staff.values():
        predicted_voices = sorted({pair[0] for pair in voice_pairs})
        expected_voices = sorted({pair[1] for pair in voice_pairs})
        counts = Counter(voice_pairs)

        @lru_cache(maxsize=None)
        def search(index: int, used_mask: int) -> int:
            if index >= len(predicted_voices):
                return 0
            best = search(index + 1, used_mask)
            for target_index, target_voice in enumerate(expected_voices):
                if used_mask & (1 << target_index):
                    continue
                value = counts[(predicted_voices[index], target_voice)]
                best = max(best, value + search(index + 1, used_mask | (1 << target_index)))
            return best

        score += search(0, 0)
    return score


def calculate_note_metrics(predicted: Iterable[MetricNote], expected: Iterable[MetricNote]) -> NoteMetrics:
    predicted_notes = list(predicted)
    expected_notes = list(expected)
    pitch_matches = _counter_matches(
        Counter(note.pitch for note in predicted_notes),
        Counter(note.pitch for note in expected_notes),
    )
    onset_matches = _counter_matches(
        Counter((note.pitch, note.onset) for note in predicted_notes),
        Counter((note.pitch, note.onset) for note in expected_notes),
    )
    exact_pairs = _exact_pairs(predicted_notes, expected_notes)

    onset_pairs: list[tuple[MetricNote, MetricNote]] = []
    expected_by_onset: dict[tuple[int, Fraction], list[MetricNote]] = defaultdict(list)
    for note in expected_notes:
        expected_by_onset[(note.pitch, note.onset)].append(note)
    for note in predicted_notes:
        bucket = expected_by_onset[(note.pitch, note.onset)]
        if bucket:
            onset_pairs.append((note, bucket.pop(0)))
    mean_offset_error = (
        float(sum(abs(prediction.offset - target.offset) for prediction, target in onset_pairs) / len(onset_pairs))
        if onset_pairs
        else float("inf")
    )
    staff_matches = sum(prediction.staff == target.staff for prediction, target in exact_pairs)
    voice_matches = _best_voice_score(exact_pairs)
    exact_count = len(exact_pairs)
    return NoteMetrics(
        pitch_f1=_f1(pitch_matches, len(predicted_notes), len(expected_notes)),
        onset_f1=_f1(onset_matches, len(predicted_notes), len(expected_notes)),
        onset_duration_f1=_f1(exact_count, len(predicted_notes), len(expected_notes)),
        mean_offset_error=mean_offset_error,
        staff_accuracy=staff_matches / exact_count if exact_count else 0.0,
        aligned_voice_accuracy=voice_matches / exact_count if exact_count else 0.0,
    )

