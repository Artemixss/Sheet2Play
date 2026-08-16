from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path


BRIDGE_DIRECTORY = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BRIDGE_DIRECTORY.parent


@unittest.skipUnless(
    os.environ.get("SHEET2PLAY_RUN_E2E") == "1",
    "Set SHEET2PLAY_RUN_E2E=1 and SHEET2PLAY_E2E_FIXTURES to run GPU OMR tests",
)
class OmrEndToEndTests(unittest.TestCase):
    def test_pdf_jpeg_and_multipage_tiff_with_homr(self) -> None:
        fixture_value = os.environ.get("SHEET2PLAY_E2E_FIXTURES", "")
        fixture_directory = Path(fixture_value).expanduser().resolve(strict=True)
        inputs = (
            fixture_directory / "score.pdf",
            fixture_directory / "score.jpg",
            fixture_directory / "score-multipage.tiff",
        )
        missing = [str(path) for path in inputs if not path.is_file()]
        self.assertFalse(missing, f"Missing E2E fixtures: {missing}")

        engine = "homr"
        for input_path in inputs:
                with self.subTest(input=input_path.name):
                    completed = subprocess.run(
                        [
                            sys.executable,
                            str(BRIDGE_DIRECTORY / "bridge.py"),
                            "--engine",
                            engine,
                            str(input_path),
                        ],
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=1800,
                        check=False,
                    )
                    self.assertEqual(
                        completed.returncode,
                        0,
                        msg=completed.stderr[-8000:],
                    )
                    result = json.loads(completed.stdout)
                    self.assertEqual(result["schema_version"], 2)
                    self.assertEqual(result["engine"], engine)
                    self.assertTrue(result["tempo_changes"])
                    self.assertTrue(result["notes"])


@unittest.skipUnless(
    os.environ.get("SHEET2PLAY_RUN_TRANSCODA_E2E") == "1",
    "Set SHEET2PLAY_RUN_TRANSCODA_E2E=1 to run the committed CUDA Transcoda fixture",
)
class TranscodaEndToEndTests(unittest.TestCase):
    def test_committed_fixture_returns_clean_schema_v2_json(self) -> None:
        executable = Path("Scripts/python.exe") if os.name == "nt" else Path("bin/python")
        python = PROJECT_ROOT / "Research" / "omr" / ".venv" / executable
        fixture = (
            PROJECT_ROOT
            / "Research"
            / "omr"
            / "tests"
            / "fixtures"
            / "transcoda-baseline"
            / "baseline-piano.png"
        )
        self.assertTrue(python.is_file(), f"Missing Transcoda interpreter: {python}")
        self.assertTrue(fixture.is_file(), f"Missing committed fixture: {fixture}")

        completed = subprocess.run(
            [
                str(python),
                str(BRIDGE_DIRECTORY / "bridge.py"),
                "--engine",
                "transcoda",
                str(fixture),
            ],
            cwd=PROJECT_ROOT,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
            check=False,
        )

        self.assertEqual(0, completed.returncode, msg=completed.stderr[-8000:])
        result = json.loads(completed.stdout)
        self.assertEqual(2, result["schema_version"])
        self.assertEqual("transcoda", result["engine"])
        self.assertTrue(result["tempo_changes"])
        self.assertTrue(result["notes"])
        self.assertIn("SHEET2PLAY_PROGRESS:", completed.stderr)
        self.assertNotIn("SHEET2PLAY_ERROR:", completed.stderr)


if __name__ == "__main__":
    unittest.main()
