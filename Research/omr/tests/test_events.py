from __future__ import annotations

import importlib.util
import unittest

from sheet2play_omr.events import build_omr_result, extract_canonical_events, parse_kern
from sheet2play_omr.errors import ResearchError


@unittest.skipUnless(importlib.util.find_spec("music21"), "music21 is not installed")
class CanonicalEventTests(unittest.TestCase):
    @staticmethod
    def _score():
        from music21 import chord, meter, note, stream, tie

        score = stream.Score()
        treble = stream.Part(id="treble")
        bass = stream.Part(id="bass")
        for part, pitches in ((treble, ("C4", "E4")), (bass, ("C3", "G3"))):
            first = stream.Measure(number=1)
            first.append(meter.TimeSignature("4/4"))
            voice = stream.Voice(id="voice-a")
            first_chord = chord.Chord(pitches, quarterLength=1)
            voice.insert(0, first_chord)
            voice.insert(1, note.Rest(quarterLength=1))
            tied = note.Note(pitches[0], quarterLength=2)
            tied.tie = tie.Tie("start")
            voice.insert(2, tied)
            first.insert(0, voice)

            second = stream.Measure(number=2)
            second_voice = stream.Voice(id="voice-a")
            continuation = note.Note(pitches[0], quarterLength=2)
            continuation.tie = tie.Tie("stop")
            second_voice.insert(0, continuation)
            second_voice.insert(2, note.Note(pitches[1], quarterLength=2))
            second.insert(0, second_voice)
            part.append((first, second))
            score.insert(0, part)
        return score

    def test_chords_rests_staves_voices_and_ties_are_preserved(self) -> None:
        canonical = extract_canonical_events(self._score())
        notes = [event for event in canonical.events if event.kind == "note"]
        rests = [event for event in canonical.events if event.kind == "rest"]
        self.assertEqual({0, 1}, {event.staff for event in notes})
        self.assertEqual({"voice-a"}, {event.voice for event in notes})
        self.assertEqual(2, len(rests))
        self.assertEqual(4, sum(event.chord_id is not None for event in notes))
        self.assertEqual({"start", "stop"}, {event.tie for event in notes if event.tie})

    def test_playback_result_merges_ties_and_uses_default_tempo(self) -> None:
        result, _ = build_omr_result(self._score())
        self.assertEqual([{"start_beat": 0.0, "bpm": 120.0}], result["tempo_changes"])
        tied = [note for note in result["notes"] if note["pitch"] in {"C4", "C3"}]
        self.assertTrue(any(note["duration_beats"] == 4.0 for note in tied))
        self.assertTrue(all(note["duration_seconds"] > 0 for note in result["notes"]))

    def test_generated_voice_identifiers_are_stable_across_parses(self) -> None:
        kern = """**kern\t**kern
*M4/4\t*M4/4
=1\t=1
4c\t4C
4d\t4D
4e\t4E
4f\t4F
*-\t*-
"""
        identifiers = []
        for _ in range(2):
            canonical = extract_canonical_events(parse_kern(kern))
            identifiers.append(tuple(event.voice for event in canonical.events if event.kind == "note"))
        self.assertEqual(identifiers[0], identifiers[1])
        self.assertEqual({"voice-1"}, set(identifiers[0]))

    def test_converter_rhythm_failure_is_typed(self) -> None:
        inconsistent = """**kern\t**kern
*M4/4\t*M4/4
2c\t4C
4d\t4D
*-\t*-
"""

        with self.assertRaises(ResearchError) as raised:
            parse_kern(inconsistent)

        self.assertEqual("KERN_PARSE_FAILED", raised.exception.code)
        self.assertIn("Inconsistent rhythm analysis", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
