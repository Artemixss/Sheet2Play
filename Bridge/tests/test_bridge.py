from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

BRIDGE_DIRECTORY = Path(__file__).resolve().parents[1]
if str(BRIDGE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(BRIDGE_DIRECTORY))

import bridge  # noqa: E402
from musicxml_normalizer import (  # noqa: E402
    NormalizedScore,
    RawMusicNote,
    TempoChange,
    normalize_musicxml,
)


class BridgeTests(unittest.TestCase):
    def test_source_musicxml_events_survive_direct_bridge_path(self) -> None:
        from music21 import meter, note, stream, tempo

        with tempfile.TemporaryDirectory() as temporary:
            score = stream.Score()
            part = stream.Part(id="P1")
            measure = stream.Measure(number=1)
            measure.insert(0, meter.TimeSignature("4/4"))
            measure.insert(0, tempo.MetronomeMark(number=120))
            measure.insert(0, note.Note("C#4", quarterLength=1.5))
            part.append(measure)
            score.append(part)
            source = Path(temporary) / "control.musicxml"
            score.write("musicxml", fp=source)

            normalized = normalize_musicxml(source)
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
                exit_code = bridge.main(["--engine", "musicxml", str(source)])

        self.assertEqual(exit_code, 0)
        document = json.loads(stdout.getvalue())
        expected = [
            (
                item.pitch,
                item.midi_pitch,
                item.start_beat,
                item.duration_beats,
                item.part_index,
                item.staff_index,
                item.voice_identifier,
            )
            for item in normalized.notes
        ]
        actual = [
            (
                item["pitch"],
                item["midi_pitch"],
                item["start_beat"],
                item["duration_beats"],
                item["part_index"],
                item["staff_index"],
                item["voice_identifier"],
            )
            for item in document["notes"]
        ]
        self.assertEqual(actual, expected)

    def test_success_stdout_contains_only_schema_json(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            input_path = Path(temporary) / "score.png"
            input_path.write_bytes(b"mocked-input")
            output = self._engine_output("C4", 60)
            stdout = io.StringIO()
            stderr = io.StringIO()
            with mock.patch.object(bridge, "run_homr_engine", return_value=output):
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    exit_code = bridge.main(["--engine", "homr", str(input_path)])

        self.assertEqual(exit_code, 0)
        document = json.loads(stdout.getvalue())
        self.assertEqual(document["schema_version"], 2)
        self.assertEqual(document["engine"], "homr")
        self.assertEqual(document["notes"][0]["midi_pitch"], 60)
        self.assertNotIn("SHEET2PLAY_PROGRESS:", stdout.getvalue())

    def test_homr_remains_an_independent_engine(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            input_path = Path(temporary) / "score.png"
            input_path.write_bytes(b"mocked-input")
            stdout = io.StringIO()
            with mock.patch.object(
                bridge, "run_homr_engine", return_value=self._engine_output("D4", 62)
            ):
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
                    exit_code = bridge.main(["--engine", "homr", str(input_path)])

        self.assertEqual(exit_code, 0)
        document = json.loads(stdout.getvalue())
        self.assertEqual(document["engine"], "homr")
        self.assertEqual(document["engine_revision"], bridge.HOMR_ENGINE_REVISION)

    def test_failure_stdout_is_empty_and_stderr_is_structured(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = bridge.main(["--engine", "homr", "missing.pdf"])

        self.assertNotEqual(exit_code, 0)
        self.assertEqual(stdout.getvalue(), "")
        record_line = next(
            line for line in stderr.getvalue().splitlines()
            if line.startswith(bridge.ERROR_PREFIX)
        )
        record = json.loads(record_line.removeprefix(bridge.ERROR_PREFIX))
        self.assertEqual(record["code"], "INPUT_INVALID")
        self.assertEqual(record["stage"], "input")

    def test_homr_page_without_output_never_reuses_previous_page(self) -> None:
        # HOMR can log a page error and still exit 0; the next page in the same
        # directory must not pick up the page before it.
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            pages = [directory / "page-0001.png", directory / "page-0002.png"]
            for page in pages:
                page.write_bytes(b"png")

            @contextlib.contextmanager
            def prepared(_input_path: Path):
                yield pages

            def fake_homr(command, **_kwargs):
                image = Path(command[-1])
                if image.name == "page-0001.png":
                    image.with_suffix(".musicxml").write_text("<score-partwise/>", encoding="utf-8")
                return mock.Mock(returncode=0)

            with (
                mock.patch.object(bridge, "prepare_homr_inputs", prepared),
                mock.patch.object(bridge, "resolve_homr_python", return_value=Path(sys.executable)),
                mock.patch.object(bridge.subprocess, "run", side_effect=fake_homr),
                mock.patch.object(
                    bridge, "normalize_musicxml", return_value=self._engine_output("C4", 60).score
                ) as normalize,
                contextlib.redirect_stderr(io.StringIO()),
            ):
                with self.assertRaises(bridge.BridgeError) as raised:
                    bridge.run_homr_engine(directory / "score.pdf")

            self.assertEqual(raised.exception.code, "NORMALIZATION_FAILED")
            self.assertEqual(raised.exception.stage, "homr_output")
            self.assertEqual(raised.exception.page, 2)
            normalize.assert_not_called()

    def test_homr_selects_each_page_own_output_in_sequence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            pages = [directory / "page-0001.png", directory / "page-0002.png"]

            def fake_homr(command, **_kwargs):
                Path(command[-1]).with_suffix(".musicxml").write_text("<score-partwise/>", encoding="utf-8")
                return mock.Mock(returncode=0)

            with (
                mock.patch.object(bridge, "resolve_homr_python", return_value=Path(sys.executable)),
                mock.patch.object(bridge.subprocess, "run", side_effect=fake_homr),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                outputs = [bridge.run_homr(page) for page in pages]

            self.assertEqual([path.name for path in outputs], ["page-0001.musicxml", "page-0002.musicxml"])

    @staticmethod
    def _transcoda_result() -> bridge.OmrResult:
        return bridge.OmrResult(
            schema_version=2,
            tempo_changes=(TempoChange(start_beat=0, bpm=120),),
            notes=(
                bridge.MusicNote(
                    pitch="C4",
                    midi_pitch=60,
                    start_beat=0,
                    duration_beats=1,
                    start_seconds=0,
                    duration_seconds=0.5,
                    part_index=0,
                    staff_index=0,
                    voice_identifier="voice-1",
                ),
            ),
        )

    @staticmethod
    def _engine_output(pitch: str, midi_pitch: int) -> bridge.EngineOutput:
        score = NormalizedScore(
            notes=(RawMusicNote(pitch, midi_pitch, 0, 1, 0, 0, "1"),),
            tempo_changes=(TempoChange(start_beat=0, bpm=120),),
            total_beats=1,
            part_count=1,
            staff_count=1,
        )
        return bridge.EngineOutput(score=score, page_count=1, staff_count=1)


if __name__ == "__main__":
    unittest.main()
