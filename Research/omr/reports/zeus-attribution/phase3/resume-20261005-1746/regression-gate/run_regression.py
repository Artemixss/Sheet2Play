"""Run complete coverage with a temporary inherited Git prohibition."""
from __future__ import annotations

import os
from pathlib import Path
import sys

import no_git_guard

if not no_git_guard.INSTALLED:
    raise RuntimeError("Git prohibition was not installed")

gate = str(Path(__file__).resolve().parent)
existing = os.environ.get("PYTHONPATH")
os.environ["PYTHONPATH"] = gate + (os.pathsep + existing if existing else "")

import pytest

raise SystemExit(pytest.main([
    "Bridge/tests", "Research/omr/tests", "-q", "-o", "addopts=",
    "--junitxml=" + str(Path(gate).parent / "regression-junit.xml"),
]))
