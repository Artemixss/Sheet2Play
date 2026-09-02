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

            # A grace note has zero quarterLength, so the duration validation rejects it
            # and _extract_score skips that one element with a warning rather than
            # aborting the score - the deliberate behaviour described in CONTEXT.md 3.4.
            # This test previously asserted the default path *raised*, which stopped being
            # true once that skip was introduced.
            default = normalize_musicxml(path)
            self.assertEqual([item.pitch for item in default.notes], ["E4"])

            normalized = normalize_musicxml(path, skip_grace_notes=True)

        # skip_grace_notes therefore changes how the grace note is discarded, not whether
        # it is: both paths drop it. That is why flipping the flag moved the OLiMPiC
        # rhythm benchmark by less than 0.005 onset F1.
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


    # --- Golden corpus ----------------------------------------------------------------
    #
    # golden_scores.json carries exact expected onsets and durations for six scores
    # covering the notation this project most often gets wrong. Those expected values sat
    # unchecked: the only test that read the file asserted its length and its feature
    # names. The builders below reconstruct each score so the normalizer's timing can be
    # asserted against them with no OMR engine in the loop, which is what makes this a
    # usable rhythm regression suite. `multiple_voices_repeats_accidentals` matters most -
    # two independent voices on one staff is the case HOMR cannot represent, so this test
    # is what proves the fault is the engine and not the normalizer.

    def build_monophonic_melody(self) -> object:
        from music21 import note, stream, tempo

        score, measure = self.new_single_part_score(tempo_bpm=120)
        measure.insert(0, note.Note("C4", quarterLength=1))
        measure.insert(1, note.Note("D4", quarterLength=1))
        measure.insert(2, note.Note("E4", quarterLength=2))
        return score

    def build_dotted_notes_and_ties(self) -> object:
        from music21 import note, stream, tempo, tie

        score, measure = self.new_single_part_score(tempo_bpm=120)
        opening = note.Note("G4", quarterLength=1.5)
        opening.tie = tie.Tie("start")
        continuation = note.Note("G4", quarterLength=1.5)
        continuation.tie = tie.Tie("stop")
        measure.insert(0, opening)
        measure.insert(1.5, continuation)
        measure.insert(3, note.Note("A4", quarterLength=1))
        return score

    def build_triplet_tuplets(self) -> object:
        from fractions import Fraction

        from music21 import note, stream, tempo

        score, measure = self.new_single_part_score(tempo_bpm=120)
        for index, name in enumerate(("C5", "D5", "E5")):
            measure.insert(
                Fraction(index, 3), note.Note(name, quarterLength=Fraction(1, 3))
            )
        return score

    def build_piano_grand_staff_chords(self) -> object:
        from music21 import chord, stream, tempo

        score = stream.Score()
        treble = stream.Part(id="P1")
        upper = stream.Measure(number=1)
        upper.insert(0, tempo.MetronomeMark(number=90))
        upper.insert(0, chord.Chord(["C4", "E4", "G4"], quarterLength=2))
        treble.append(upper)
        bass = stream.Part(id="P2")
        lower = stream.Measure(number=1)
        lower.insert(0, chord.Chord(["C3", "G3"], quarterLength=2))
        bass.append(lower)
        score.append(treble)
        score.append(bass)
        return score

    def build_multiple_voices_repeats_accidentals(self) -> object:
        from music21 import bar, meter, note, stream, tempo

        score = stream.Score()
        part = stream.Part(id="P1")
        measure = stream.Measure(number=1)
        measure.insert(0, tempo.MetronomeMark(number=120))
        measure.insert(0, meter.TimeSignature("2/4"))
        first = stream.Voice(id="1")
        first.insert(0, note.Note("F#4", quarterLength=2))
        second = stream.Voice(id="2")
        second.insert(0, note.Note("B-3", quarterLength=1))
        measure.insert(0, first)
        measure.insert(0, second)
        measure.leftBarline = bar.Repeat(direction="start")
        measure.rightBarline = bar.Repeat(direction="end")
        part.append(measure)
        score.append(part)
        return score

    def build_piecewise_tempo(self) -> object:
        from music21 import note, stream, tempo

        score, measure = self.new_single_part_score(tempo_bpm=60)
        measure.insert(0, note.Note("C4", quarterLength=2))
        measure.insert(1, tempo.MetronomeMark(number=120))
        measure.insert(2, note.Note("D4", quarterLength=1))
        return score

    def new_single_part_score(self, tempo_bpm: float) -> tuple[object, object]:
        from music21 import stream, tempo

        score = stream.Score()
        part = stream.Part(id="P1")
        measure = stream.Measure(number=1)
        measure.insert(0, tempo.MetronomeMark(number=tempo_bpm))
        part.append(measure)
        score.append(part)
        return score, measure

    def test_golden_corpus_onsets_and_durations_match(self) -> None:
        corpus_path = Path(__file__).with_name("golden_scores.json")
        corpus = {
            entry["id"]: entry
            for entry in json.loads(corpus_path.read_text(encoding="utf-8"))
        }
        builders = {
            "monophonic_melody": self.build_monophonic_melody,
            "dotted_notes_and_ties": self.build_dotted_notes_and_ties,
            "triplet_tuplets": self.build_triplet_tuplets,
            "piano_grand_staff_chords": self.build_piano_grand_staff_chords,
            "multiple_voices_repeats_accidentals": (
                self.build_multiple_voices_repeats_accidentals
            ),
            "piecewise_tempo": self.build_piecewise_tempo,
        }
        self.assertEqual(set(builders), set(corpus))

        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for identifier, build in builders.items():
                with self.subTest(score=identifier):
                    path = self.write_score(build(), directory, identifier)
                    normalized = normalize_musicxml(path)

                    actual_notes = sorted(
                        (round(item.start_beat, 6), round(item.duration_beats, 6), item.pitch)
                        for item in normalized.notes
                    )
                    expected_notes = sorted(
                        (
                            round(item["start_beat"], 6),
                            round(item["duration_beats"], 6),
                            item["pitch"],
                        )
                        for item in corpus[identifier]["notes"]
                    )
                    self.assertEqual(actual_notes, expected_notes)

                    actual_tempo = [
                        (round(item.start_beat, 6), round(item.bpm, 6))
                        for item in normalized.tempo_changes
                    ]
                    expected_tempo = [
                        (round(item["start_beat"], 6), round(item["bpm"], 6))
                        for item in corpus[identifier]["tempo_changes"]
                    ]
                    self.assertEqual(actual_tempo, expected_tempo)


    def test_unexpandable_repeats_degrade_instead_of_failing(self) -> None:
        """A repeat music21 cannot expand must not lose the whole score.

        OMR output regularly carries unbalanced repeat barlines - a closing repeat with no
        opening, or one spanning a page break. Aborting there threw away scores that were
        otherwise fine; homr's output for havanagila.pdf did exactly that. Playing a repeated
        section once beats playing nothing, which is the same principle as the skipped notes
        elsewhere in this module.
        """
        from music21 import note, stream, tempo

        with tempfile.TemporaryDirectory() as temporary:
            score = stream.Score()
            part = stream.Part(id="P1")
            measure = stream.Measure(number=1)
            measure.insert(0, tempo.MetronomeMark(number=120))
            measure.insert(0, note.Note("C4", quarterLength=1))
            measure.insert(1, note.Note("D4", quarterLength=1))
            part.append(measure)
            score.append(part)
            path = self.write_score(score, Path(temporary), "unexpandable")

            original = stream.Score.expandRepeats

            def refuse(self, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
                raise RuntimeError("cannot expand these repeats")

            stream.Score.expandRepeats = refuse
            try:
                normalized = normalize_musicxml(path, expand_repeats=True)
            finally:
                stream.Score.expandRepeats = original

        # The score survives, unexpanded, rather than raising.
        self.assertEqual(["C4", "D4"], [item.pitch for item in normalized.notes])
        self.assertEqual([0.0, 1.0], [item.start_beat for item in normalized.notes])


    def test_unreadable_clef_is_dropped_instead_of_losing_the_score(self) -> None:
        """music21 cannot read a clef that is not a letter plus a line number.

        homr emits a TAB clef as <sign>T</sign><line>A</line>; music21 then evaluates
        int("A") and raises, discarding an otherwise complete page. Two files in the local
        library failed exactly this way. Dropping the clef costs a clef and saves the score.
        """
        from music21 import clef, note, stream, tempo

        with tempfile.TemporaryDirectory() as temporary:
            score = stream.Score()
            part = stream.Part(id="P1")
            measure = stream.Measure(number=1)
            measure.insert(0, tempo.MetronomeMark(number=120))
            # Explicit, so music21 actually writes a <clef> element for us to corrupt.
            measure.insert(0, clef.TrebleClef())
            measure.insert(0, note.Note("C4", quarterLength=1))
            measure.insert(1, note.Note("D4", quarterLength=1))
            part.append(measure)
            score.append(part)
            path = self.write_score(score, Path(temporary), "badclef")

            document = path.read_text(encoding="utf-8")
            self.assertIn("<clef", document)
            broken = document.replace(
                "<sign>G</sign>", "<sign>T</sign>", 1
            ).replace("<line>2</line>", "<line>A</line>", 1)
            path.write_text(broken, encoding="utf-8")

            # Confirms the fixture really is unreadable, so this tests the repair and not
            # music21 quietly tolerating it.
            from music21 import converter

            with self.assertRaises(Exception):
                converter.parse(str(path))

            normalized = normalize_musicxml(path)

        self.assertEqual(["C4", "D4"], [item.pitch for item in normalized.notes])


if __name__ == "__main__":
    unittest.main()
