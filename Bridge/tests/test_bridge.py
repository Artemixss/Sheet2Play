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
from musicxml_normalizer import NormalizedScore, RawMusicNote, TempoChange  # noqa: E402


class BridgeTests(unittest.TestCase):
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
