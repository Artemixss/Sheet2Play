"""Run a Sheet2Play bridge engine as a subprocess and get notes back.

HOMR lives in `Bridge/.venv-homr-gpu`, not the research venv, so it can only be reached by
shelling into `Bridge/bridge.py`. That subprocess dance - timeout, Windows process-tree kill,
JSON parse, structured error - had been copy-pasted into three places that then drifted
apart. This is the single implementation.

The result object is deliberately neutral: callers shape it into whatever row format they
report, rather than this module guessing. `phase3_benchmark` wants checkpoint rows,
`diagnose_rhythm` wants cacheable records, `compare_engines` wants comparison rows.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping

from .errors import ResearchError
from .metrics import MetricNote

DEFAULT_TIMEOUT_SECONDS = 600

# Engines reachable through bridge.py. DirectMidi is deliberately absent: the C# side parses
# MIDI itself and never invokes the bridge for it.
BRIDGE_ENGINES = ("homr", "zeus", "musicxml")


@dataclass(frozen=True, slots=True)
class BridgeResult:
    """One engine invocation. `payload` is bridge schema-version-2 JSON when `ok`."""

    ok: bool
    seconds: float
    payload: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    stdout_tail: str = ""
    stderr_tail: str = ""

    @property
    def error_code(self) -> str | None:
        return None if self.error is None else str(self.error.get("code"))


def workspace_root() -> Path:
    """The repository root, found by looking for Bridge/bridge.py above this file."""
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "Bridge" / "bridge.py").is_file():
            return candidate
    raise ResearchError("RUNTIME_MISSING", "engines", "Cannot locate the Sheet2Play workspace")


def terminate_process_tree(process: subprocess.Popen[str]) -> None:
    """Kill the process and its children.

    HOMR spawns further subprocesses (page rendering, the ONNX runtime), so killing only the
    direct child on Windows leaves orphans holding the GPU.
    """
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        process.kill()


def run_bridge_engine(
    image: str | Path,
    *,
    engine: str = "homr",
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    extra_env: Mapping[str, str] | None = None,
) -> BridgeResult:
    """Invoke `bridge.py --engine <engine> <image>` and return its parsed output.

    `extra_env` is merged over the inherited environment; `bridge.py` copies `os.environ`
    wholesale when it launches HOMR, so variables set here reach the engine itself. That is
    how the tuplet-cleanup diagnostic switch is delivered.

    Never raises for engine failure - a failed run is a `BridgeResult` with `ok=False`, so a
    caller sweeping a corpus records the failure and keeps going.
    """
    if engine not in BRIDGE_ENGINES:
        raise ResearchError(
            "INPUT_INVALID", "engines", f"Unknown bridge engine {engine!r}"
        )
    workspace = workspace_root()
    # bridge.py runs with cwd=Bridge/, so a caller's relative path would resolve against the
    # wrong directory and come back as INPUT_INVALID. Resolve before handing it over.
    image = Path(image).resolve()
    environment = {**os.environ, "PYTHONUNBUFFERED": "1"}
    if extra_env:
        environment.update(extra_env)

    started = time.perf_counter()
    try:
        process = subprocess.Popen(
            [
                sys.executable,
                str(workspace / "Bridge" / "bridge.py"),
                "--engine",
                engine,
                str(image),
            ],
            cwd=workspace / "Bridge",
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError as error:
        return BridgeResult(
            ok=False,
            seconds=time.perf_counter() - started,
            error={"code": "RUNTIME_MISSING", "stage": engine, "message": str(error)},
        )

    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        terminate_process_tree(process)
        stdout, stderr = process.communicate()
        return BridgeResult(
            ok=False,
            seconds=time.perf_counter() - started,
            error={
                "code": "TIMEOUT",
                "stage": engine,
                "message": f"{engine} exceeded {timeout_seconds} seconds",
            },
            stderr_tail=stderr[-2000:],
        )

    elapsed = time.perf_counter() - started
    if process.returncode != 0:
        return BridgeResult(
            ok=False,
            seconds=elapsed,
            error={
                "code": f"{engine.upper()}_FAILED",
                "stage": engine,
                "message": stderr[-2000:],
            },
            stderr_tail=stderr[-2000:],
        )

    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as error:
        return BridgeResult(
            ok=False,
            seconds=elapsed,
            error={"code": "BRIDGE_OUTPUT_INVALID", "stage": engine, "message": str(error)},
            stdout_tail=stdout[-1000:],
            stderr_tail=stderr[-2000:],
        )
    return BridgeResult(ok=True, seconds=elapsed, payload=payload)


def _fraction(value: float | int | str | Fraction) -> Fraction:
    if isinstance(value, Fraction):
        return value
    return Fraction(str(value)).limit_denominator(4096)


def metric_notes_from_bridge(payload: Mapping[str, Any], *, stage: str = "homr") -> list[MetricNote]:
    """Convert bridge schema-version-2 JSON into scoreable notes.

    Onsets arrive as floats and are pulled back onto a rational grid with
    `limit_denominator(4096)`, which recovers exact thirds and fifths so tuplets compare
    equal instead of failing on float noise.
    """
    try:
        notes = [
            MetricNote(
                pitch=int(note["midi_pitch"]),
                onset=_fraction(note["start_beat"]),
                duration=_fraction(note["duration_beats"]),
                staff=int(note["staff_index"]),
                voice=str(note["voice_identifier"]),
            )
            for note in payload["notes"]
        ]
    except (KeyError, TypeError, ValueError) as error:
        raise ResearchError(
            f"{stage.upper()}_OUTPUT_INVALID", stage, str(error)
        ) from error
    if not notes:
        raise ResearchError(f"{stage.upper()}_OUTPUT_INVALID", stage, f"{stage} returned no notes")
    return notes
