from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


BRIDGE_DIRECTORY = Path(__file__).resolve().parents[1]
if str(BRIDGE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(BRIDGE_DIRECTORY))

from musicxml_normalizer import (  # noqa: E402
    MusicXmlNormalizationError,
    TempoChange,
    TempoTimeline,
    add_seconds,
    normalize_musicxml,
)


class MusicXmlNormalizerTests(unittest.TestCase):
    def write_score(self, score: object, directory: Path, name: str) -> Path:
        path = directory / f"{name}.musicxml"
        score.write("musicxml", fp=path)
        return path

    def test_piecewise_tempo_converts_crossing_note_duration(self) -> None:
        from music21 import chord, stream, tempo

        with tempfile.TemporaryDirectory() as temporary:
            score = stream.Score()
            part = stream.Part(id="P1")
            measure = stream.Measure(number=1)
            measure.insert(0, tempo.MetronomeMark(number=60))
            measure.insert(0, chord.Chord(["C4", "E4"], quarterLength=2))
            measure.insert(1, tempo.MetronomeMark(number=120))
            part.append(measure)
            score.append(part)

            normalized = normalize_musicxml(
                self.write_score(score, Path(temporary), "tempo")
            )
            notes = add_seconds(normalized)

        self.assertEqual(len(notes), 2)
        self.assertEqual([change.bpm for change in normalized.tempo_changes], [60.0, 120.0])
        self.assertAlmostEqual(notes[0].duration_seconds, 1.5)
        self.assertEqual({note.start_seconds for note in notes}, {0.0})

    def test_tied_notes_merge_into_one_sustained_event(self) -> None:
        from music21 import bar, note, stream, tie

        with tempfile.TemporaryDirectory() as temporary:
            score = stream.Score()
            part = stream.Part(id="P1")
            first_measure = stream.Measure(number=1)
            first = note.Note("G4", quarterLength=1)
            first.tie = tie.Tie("start")
            first_measure.append(first)
            first_measure.rightBarline = bar.Barline("regular")
            second_measure = stream.Measure(number=2)
            second = note.Note("G4", quarterLength=2)
            second.tie = tie.Tie("stop")
            second_measure.append(second)
            part.append([first_measure, second_measure])
            score.append(part)

            normalized = normalize_musicxml(
                self.write_score(score, Path(temporary), "ties")
            )

        self.assertEqual(len(normalized.notes), 1)
        self.assertEqual(normalized.notes[0].pitch, "G4")
        self.assertAlmostEqual(normalized.notes[0].duration_beats, 3.0)

    def test_repeats_expand_into_playback_order(self) -> None:
        from music21 import bar, note, stream

        with tempfile.TemporaryDirectory() as temporary:
            score = stream.Score()
            part = stream.Part(id="P1")
            first_measure = stream.Measure(number=1)
            first_measure.leftBarline = bar.Repeat(direction="start")
            first_measure.append(note.Note("C4", quarterLength=1))
            second_measure = stream.Measure(number=2)
            second_measure.append(note.Note("D4", quarterLength=1))
            second_measure.rightBarline = bar.Repeat(direction="end", times=2)
            part.append([first_measure, second_measure])
            score.append(part)

            path = self.write_score(score, Path(temporary), "repeats")
            normalized = normalize_musicxml(path)
            unexpanded = normalize_musicxml(path, expand_repeats=False)

        self.assertEqual([item.pitch for item in normalized.notes], ["C4", "D4", "C4", "D4"])
        self.assertEqual([item.start_beat for item in normalized.notes], [0.0, 1.0, 2.0, 3.0])
        self.assertEqual([item.pitch for item in unexpanded.notes], ["C4", "D4"])

    def test_voices_tuplets_and_chords_are_preserved(self) -> None:
        from music21 import chord, duration, note, stream

        with tempfile.TemporaryDirectory() as temporary:
            score = stream.Score()
            part = stream.Part(id="P1")
            measure = stream.Measure(number=1)
            upper = stream.Voice(id="upper")
            lower = stream.Voice(id="lower")
            triplet_duration = duration.Duration(1 / 3)
            for pitch in ("C5", "D5", "E5"):
                upper.append(note.Note(pitch, duration=triplet_duration))
            lower.append(chord.Chord(["C3", "G3"], quarterLength=1))
            measure.insert(0, upper)
            measure.insert(0, lower)
            part.append(measure)
            score.append(part)

            normalized = normalize_musicxml(
                self.write_score(score, Path(temporary), "voices")
            )

        self.assertEqual(len(normalized.notes), 5)
        self.assertEqual({item.voice_identifier for item in normalized.notes}, {"upper", "lower"})
        upper_notes = [item for item in normalized.notes if item.voice_identifier == "upper"]
        self.assertTrue(all(abs(item.duration_beats - (1 / 3)) < 1e-9 for item in upper_notes))
        lower_notes = [item for item in normalized.notes if item.voice_identifier == "lower"]
        self.assertEqual({item.start_beat for item in lower_notes}, {0.0})

    def test_grace_notes_can_be_excluded_for_system_level_metrics(self) -> None:
        from music21 import duration, note, stream

        with tempfile.TemporaryDirectory() as temporary:
            score = stream.Score()
            part = stream.Part(id="P1")
            measure = stream.Measure(number=1)
            grace = note.Note("D4")
            grace.duration = duration.GraceDuration()
            measure.append(grace)
            measure.append(note.Note("E4", quarterLength=1))
            part.append(measure)
            score.append(part)
            path = self.write_score(score, Path(temporary), "grace")

            with self.assertRaises(MusicXmlNormalizationError):
                normalize_musicxml(path)
            normalized = normalize_musicxml(path, skip_grace_notes=True)

        self.assertEqual([item.pitch for item in normalized.notes], ["E4"])

    def test_tempo_timeline_inserts_default_and_is_piecewise(self) -> None:
        timeline = TempoTimeline([TempoChange(start_beat=2, bpm=60)])
        self.assertAlmostEqual(timeline.seconds_at(2), 1.0)
        self.assertAlmostEqual(timeline.seconds_at(3), 2.0)

    def test_malformed_musicxml_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "broken.musicxml"
            path.write_text("<score-partwise><broken>", encoding="utf-8")
            with self.assertRaises(MusicXmlNormalizationError):
                normalize_musicxml(path)

    def test_golden_corpus_contains_six_feature_complete_scores(self) -> None:
        corpus_path = Path(__file__).with_name("golden_scores.json")
        corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
        self.assertEqual(len(corpus), 6)
        all_features = {feature for score in corpus for feature in score["features"]}
        self.assertTrue(
            {
                "monophonic",
                "dotted",
                "ties",
                "tuplets",
                "grand_staff",
                "chords",
                "voices",
                "repeats",
                "accidentals",
                "tempo_changes",
            }.issubset(all_features)
        )


if __name__ == "__main__":
    unittest.main()
