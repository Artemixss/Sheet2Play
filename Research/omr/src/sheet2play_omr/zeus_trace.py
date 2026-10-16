"""Exact XML segment/measure traces for diagnosis, separate from benchmark normalization."""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, replace
from fractions import Fraction
from pathlib import Path
import xml.etree.ElementTree as ET

from .metrics import MetricNote, calculate_note_metrics, timeline_span
from .corrected_scoring import coverage
from .phase3_scoring import _duration_pairs
from .timing import rational_time


@dataclass(frozen=True)
class Segment:
    pitch: int
    onset: Fraction
    duration: Fraction
    staff: int
    voice: str
    part: str
    measure: int
    local_onset: Fraction
    ties: tuple[str, ...]

    def metric(self) -> MetricNote:
        return MetricNote(self.pitch, self.onset, self.duration, self.staff, self.voice)

    def json(self) -> dict:
        return {key: str(value) if isinstance(value, Fraction) else value for key, value in asdict(self).items()}


def xml_trace(path: Path) -> tuple[list[Segment], list[dict]]:
    root = ET.parse(path).getroot()
    if root.tag != "score-partwise" or not root.findall("part"):
        raise ValueError("Diagnostic trace requires partwise MusicXML")
    segments, measures = [], []
    staff_base = 0
    for part in root.findall("part"):
        divisions, bar, elapsed = 1, Fraction(4), Fraction(0)
        part_id = part.get("id") or ""
        maximum_staff = max([1] + [int(n.findtext("staff", "1")) for n in part.iter("note")])
        for index, measure in enumerate(part.findall("measure")):
            cursor, used, last_onset = Fraction(0), Fraction(0), Fraction(0)
            backups, forwards = [], []
            for node in measure:
                if node.tag == "attributes":
                    divisions = int(node.findtext("divisions", str(divisions)))
                    if divisions <= 0:
                        raise ValueError("MusicXML divisions must be positive")
                    time = node.find("time")
                    if time is not None and time.find("beats") is not None:
                        beats = sum(int(v) for v in time.findtext("beats").split("+"))
                        bar = Fraction(beats * 4, int(time.findtext("beat-type")))
                elif node.tag in ("backup", "forward"):
                    length = Fraction(int(node.findtext("duration", "0")), divisions)
                    if length < 0:
                        raise ValueError("Negative backup/forward duration")
                    if node.tag == "backup":
                        cursor -= length
                        backups.append(str(length))
                    else:
                        cursor += length
                        used = max(used, cursor)
                        forwards.append(str(length))
                    if cursor < 0:
                        raise ValueError("MusicXML backup precedes measure start")
                elif node.tag == "note":
                    if node.find("grace") is not None:
                        continue
                    duration = Fraction(int(node.findtext("duration", "0")), divisions)
                    if duration <= 0:
                        raise ValueError("Non-grace note requires positive duration")
                    onset = last_onset if node.find("chord") is not None else cursor
                    if node.find("chord") is None:
                        last_onset = onset
                        cursor += duration
                    used = max(used, onset + duration)
                    pitch = node.find("pitch")
                    if pitch is not None:
                        semitone = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[pitch.findtext("step")]
                        alteration = Fraction(pitch.findtext("alter", "0"))
                        midi = (int(pitch.findtext("octave")) + 1) * 12 + semitone + alteration
                        if midi.denominator != 1 or not 0 <= midi <= 127:
                            raise ValueError("Unsupported microtonal or invalid MIDI pitch")
                        segments.append(Segment(int(midi), elapsed + onset, duration,
                            staff_base + int(node.findtext("staff", "1")) - 1, node.findtext("voice", "0"),
                            part_id, index, onset, tuple(t.get("type", "") for t in node.findall("tie"))))
            advance = used if measure.get("implicit") == "yes" or (index == 0 and used < bar) else max(used, bar)
            measures.append({"part": part_id, "index": index, "number": measure.get("number"),
                "start": str(elapsed), "used": str(used), "advance": str(advance), "bar": str(bar),
                "divisions": divisions, "backups": backups, "forwards": forwards,
                "new_system": any(p.get("new-system") == "yes" for p in measure.findall("print")),
                "implicit": measure.get("implicit"), "overflow": used > bar,
                "underfilled": used < bar,
                "full_measure_rests": sum(n.find("rest") is not None and n.find("rest").get("measure") == "yes"
                                          for n in measure.findall("note")),
                "pitched_notes": sum(n.find("pitch") is not None for n in measure.findall("note"))})
            elapsed += advance
        staff_base += maximum_staff
    return segments, measures


def merge_segments(segments: list[Segment]) -> tuple[list[Segment], list[dict]]:
    """Diagnostic merge requires pitch/voice/staff identity and exact contiguity."""
    output: list[Segment] = []
    active: dict[tuple, int] = {}
    issues = []
    for segment in sorted(segments, key=lambda n: (n.onset, n.part, n.staff, n.voice, n.pitch)):
        key = (segment.part, segment.staff, segment.voice, segment.pitch)
        index = active.get(key)
        if "stop" in segment.ties and index is not None:
            previous = output[index]
            if previous.onset + previous.duration == segment.onset:
                output[index] = replace(previous, duration=previous.duration + segment.duration)
                if "start" not in segment.ties:
                    active.pop(key)
                continue
        if "stop" in segment.ties:
            issues.append({"kind": "unmatched_or_noncontiguous_tie_stop", "note": segment.json()})
        if key in active:
            issues.append({"kind": "interrupted_tie_start", "note": output[active.pop(key)].json()})
        output.append(segment)
        if "start" in segment.ties:
            active[key] = len(output) - 1
    issues.extend({"kind": "open_tie_start", "note": output[index].json()} for index in active.values())
    return output, issues


def metric_summary(predicted: list[MetricNote], expected: list[MetricNote]) -> dict:
    metrics = asdict(calculate_note_metrics(predicted, expected))
    import math
    metrics = {key: value if math.isfinite(value) else None for key, value in metrics.items()}
    truth = Counter((n.pitch, n.onset, n.duration) for n in expected)
    guesses = Counter((n.pitch, n.onset, n.duration) for n in predicted)
    return {**metrics, "predicted_notes": len(predicted), "reference_notes": len(expected),
        "missing_notes": sum((truth - guesses).values()), "extra_notes": sum((guesses - truth).values()),
        "timeline_predicted": str(timeline_span(predicted)), "timeline_reference": str(timeline_span(expected)),
        "duration": _duration_pairs(predicted, expected), "coverage": coverage(predicted, expected)}


def local_metrics(predicted: list[Segment], expected: list[Segment]) -> dict:
    indices = sorted({n.measure for n in predicted} | {n.measure for n in expected})
    details = []
    for index in indices:
        def notes(rows):
            return [MetricNote(n.pitch, n.local_onset, n.duration, n.staff, n.voice) for n in rows if n.measure == index]
        details.append({"measure_index": index, **metric_summary(notes(predicted), notes(expected))})
    return {"policy": "diagnostic only; XML ordinal measure pairing with each measure origin reset; unmatched measures retained",
            "measures": details,
            "macro_onset_duration_f1": sum(d["onset_duration_f1"] for d in details) / len(details) if details else None}


def normalized_notes(path: Path) -> list[MetricNote]:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "Bridge"))
    from musicxml_normalizer import normalize_musicxml
    score = normalize_musicxml(path, expand_repeats=False, skip_grace_notes=True, force_source=True)
    return [MetricNote(n.midi_pitch, rational_time(n.start_beat), rational_time(n.duration_beats),
                       n.staff_index, n.voice_identifier) for n in score.notes]
