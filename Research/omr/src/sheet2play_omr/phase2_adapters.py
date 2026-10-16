"""Phase-2 candidate adapters with provenance-complete artifact preservation."""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import psutil
from PIL import Image

from .adapter_contract import (
    AdapterConfig,
    AdapterInput,
    AdapterResult,
    Artifact,
    MeasurementPath,
    ResourceMeasurements,
    RunStatus,
    StageTiming,
    base_provenance,
    portable_path,
    require_supported,
    sha256_file,
    unavailable_result,
)
from .errors import ResearchError


ADAPTER_REVISION = sha256_file(Path(__file__).resolve())
SAMPLE_INTERVAL_SECONDS = 0.2


@dataclass(frozen=True, slots=True)
class CommandResult:
    exit_status: int
    seconds: float
    stdout: str
    stderr: str
    peak_ram_bytes: int | None
    peak_vram_bytes: int | None
    vram_measurement: str
    timed_out: bool


def _gpu_memory_by_pid() -> dict[int, int]:
    try:
        completed = subprocess.run(
            [
                "nvidia-smi",
                "--query-compute-apps=pid,used_gpu_memory",
                "--format=csv,noheader,nounits",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired):
        return {}
    values: dict[int, int] = {}
    for line in completed.stdout.splitlines():
        try:
            pid_text, mib_text = (value.strip() for value in line.split(",", 1))
            values[int(pid_text)] = int(mib_text) * 1024 * 1024
        except (TypeError, ValueError):
            continue
    return values


def _device_memory_bytes() -> int | None:
    try:
        completed = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        values = [int(line.strip()) for line in completed.stdout.splitlines() if line.strip()]
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None
    return sum(values) * 1024 * 1024 if values else None


def run_monitored(
    command: Sequence[str],
    *,
    cwd: Path,
    timeout_seconds: int,
    environment: Mapping[str, str] | None = None,
) -> CommandResult:
    started = time.perf_counter()
    # File-backed capture is required: HOMR emits its full token stream on stderr and can
    # exceed the Windows pipe buffer while this parent is sampling memory.
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace") as stdout_file, tempfile.TemporaryFile(
        mode="w+", encoding="utf-8", errors="replace"
    ) as stderr_file:
        process = subprocess.Popen(
            list(command),
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=stdout_file,
            stderr=stderr_file,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=None if environment is None else dict(environment),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        peak_ram = 0
        peak_vram = 0
        per_process_vram_observed = False
        device_vram_observed = False
        timed_out = False
        root = psutil.Process(process.pid)
        while process.poll() is None:
            elapsed = time.perf_counter() - started
            if elapsed > timeout_seconds:
                timed_out = True
                with contextlib.suppress(psutil.Error):
                    for child in root.children(recursive=True):
                        child.kill()
                    root.kill()
                break
            processes = [root]
            with contextlib.suppress(psutil.Error):
                processes.extend(root.children(recursive=True))
            pids: set[int] = set()
            ram = 0
            for candidate in processes:
                with contextlib.suppress(psutil.Error):
                    pids.add(candidate.pid)
                    ram += candidate.memory_info().rss
            peak_ram = max(peak_ram, ram)
            gpu = _gpu_memory_by_pid()
            process_vram = sum(gpu.get(pid, 0) for pid in pids)
            if process_vram:
                per_process_vram_observed = True
                peak_vram = max(peak_vram, process_vram)
            else:
                device_vram = _device_memory_bytes()
                if device_vram is not None:
                    device_vram_observed = True
                    peak_vram = max(peak_vram, device_vram)
            time.sleep(SAMPLE_INTERVAL_SECONDS)
        process.wait()
        stdout_file.seek(0)
        stderr_file.seek(0)
        stdout = stdout_file.read()
        stderr = stderr_file.read()
    vram_measurement = (
        "per-process"
        if per_process_vram_observed
        else "device-wide WDDM fallback"
        if device_vram_observed
        else "unavailable"
    )
    return CommandResult(
        exit_status=124 if timed_out else int(process.returncode or 0),
        seconds=time.perf_counter() - started,
        stdout=stdout,
        stderr=stderr,
        peak_ram_bytes=peak_ram or None,
        peak_vram_bytes=peak_vram or None,
        vram_measurement=vram_measurement,
        timed_out=timed_out,
    )


def _bridge_directory() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "Bridge" / "musicxml_normalizer.py").is_file():
            return candidate / "Bridge"
    raise ResearchError("RUNTIME_MISSING", "normalization", "Cannot locate Bridge")


def _canonicalize(musicxml: Path, destination: Path) -> tuple[Artifact, tuple[str, ...], float]:
    bridge = _bridge_directory()
    if str(bridge) not in sys.path:
        sys.path.insert(0, str(bridge))
    from musicxml_normalizer import normalize_musicxml

    started = time.perf_counter()
    stdout = io.StringIO()
    stderr = io.StringIO()
    caught: list[warnings.WarningMessage]
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            score = normalize_musicxml(
                musicxml,
                expand_repeats=False,
                skip_grace_notes=True,
                force_source=True,
            )
    messages = tuple(
        [f"{item.category.__name__}: {item.message}" for item in caught]
        + [line for line in (*stdout.getvalue().splitlines(), *stderr.getvalue().splitlines()) if line]
    )
    payload = {
        "schema_version": 1,
        "time_unit": "rational quarter-note time",
        "expand_repeats": False,
        "grace_notes_in_primary": False,
        "merge_tied_continuations": True,
        "notes": [
            {
                "pitch": note.pitch,
                "midi_pitch": note.midi_pitch,
                "onset": str(note.start_beat),
                "duration": str(note.duration_beats),
                "part": note.part_index,
                "staff": note.staff_index,
                "voice": note.voice_identifier,
            }
            for note in score.notes
        ],
        "tempo_changes": [
            {"start_beat": str(item.start_beat), "bpm": item.bpm}
            for item in score.tempo_changes
        ],
    }
    if not payload["notes"]:
        raise ResearchError(
            "ADAPTER_OUTPUT_INVALID", "normalization", "MusicXML produced no canonical notes"
        )
    destination.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return (
        Artifact.from_path("canonical_events", destination, "application/json"),
        messages,
        time.perf_counter() - started,
    )


def _copy_musicxml(source: Path, output_directory: Path) -> Path:
    suffix = ".mxl" if source.suffix.casefold() == ".mxl" else ".musicxml"
    destination = output_directory / f"score{suffix}"
    shutil.copy2(source, destination)
    return destination


def _prepare_audiveris_input(source: Path, output_directory: Path) -> tuple[Path, int, float]:
    started = time.perf_counter()
    with Image.open(source) as image:
        width, height = image.size
        if width <= 0 or height <= 0:
            raise ResearchError("INPUT_IMAGE_INVALID", "preprocessing", "Image dimensions are invalid")
        if width >= 2000:
            return source, 1, time.perf_counter() - started
        scale = min(4, max(2, (2000 + width - 1) // width))
        destination = output_directory / "audiveris-input-300dpi.png"
        image.convert("RGB").resize(
            (width * scale, height * scale), Image.Resampling.LANCZOS
        ).save(destination, dpi=(300, 300))
    return destination, scale, time.perf_counter() - started


def _failure(
    config: AdapterConfig,
    item: AdapterInput,
    command: CommandResult,
    *,
    code: str,
    stage: str,
    message: str,
    artifacts: tuple[Artifact, ...] = (),
    provenance_extra: Mapping[str, Any] | None = None,
    extra_timings: tuple[StageTiming, ...] = (),
) -> AdapterResult:
    result = AdapterResult(
        1,
        config.candidate_id,
        config.adapter_id,
        config.sha256,
        item.item_id,
        item.composition_group,
        item.measurement_path,
        RunStatus.FAILED,
        command.exit_status,
        (),
        (*extra_timings, StageTiming(stage, command.seconds)),
        ResourceMeasurements(
            command.peak_ram_bytes,
            command.peak_vram_bytes,
            SAMPLE_INTERVAL_SECONDS,
            True,
            (f"VRAM measurement: {command.vram_measurement}",),
        ),
        artifacts,
        {
            **base_provenance(config, item),
            "command": _portable_command(command_for_provenance.get()),
            **(provenance_extra or {}),
        },
        {"code": code, "stage": stage, "message": _portable_text(message)},
    )
    result.validate()
    return result


def _audiveris_failure_artifacts(
    output_directory: Path, engine_output: Path, process: CommandResult, prepared_input: Path
) -> tuple[Artifact, ...]:
    log = output_directory / "engine.log"
    log.write_text(
        _portable_text(process.stdout + process.stderr) or "(engine emitted no console output)\n",
        encoding="utf-8",
    )
    files = [log]
    if prepared_input != output_directory and prepared_input.parent == output_directory:
        files.append(prepared_input)
    files.extend(path for path in sorted(engine_output.rglob("*")) if path.is_file())
    return tuple(
        Artifact.from_path(f"partial_{index}_{path.name}", path, "application/octet-stream")
        for index, path in enumerate(files, start=1)
        if path.stat().st_size > 0
    )


def _generic_failure_artifacts(
    output_directory: Path, process: CommandResult, sources: Sequence[Path] = (),
) -> tuple[Artifact, ...]:
    output_directory.mkdir(parents=True, exist_ok=True)
    log = output_directory / "engine.log"
    log.write_text(_portable_text(process.stdout + process.stderr)
                   or "(engine emitted no console output)\n", encoding="utf-8")
    for index, source in enumerate(sources, start=1):
        if source.is_file() and source.stat().st_size > 0:
            shutil.copy2(source, output_directory / f"partial-{index}-{source.name}")
    files = [path for path in sorted(output_directory.rglob("*"))
             if path.is_file() and path.stat().st_size > 0]
    return tuple(Artifact.from_path(f"partial_{index}_{path.name}", path,
                                    "application/octet-stream")
                 for index, path in enumerate(files, start=1))


class _CommandContext(threading.local):
    value: tuple[str, ...] = ()

    def set(self, command: Sequence[str]) -> None:
        self.value = tuple(command)

    def get(self) -> tuple[str, ...]:
        return self.value


command_for_provenance = _CommandContext()


def _portable_argument(value: str) -> str:
    candidate = Path(value)
    if not candidate.is_absolute():
        return value
    return portable_path(candidate)


def _portable_command(command: Sequence[str]) -> list[str]:
    return [_portable_argument(value) for value in command]


def _portable_text(value: str) -> str:
    replacements = (
        (tempfile.gettempdir(), "${TEMP}"),
        (str(_bridge_directory().parent), "${WORKSPACE}"),
        (str(Path.home()), "${USERPROFILE}"),
    )
    result = value
    for source, replacement in replacements:
        variants = (source, source.replace("\\", "/"), source.replace("\\", "\\\\"))
        for variant in variants:
            result = result.replace(variant, replacement)
    return result


class ShippedHomrAdapter:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace.resolve()
        self.python = self.workspace / "Bridge" / ".venv-homr-gpu" / "Scripts" / "python.exe"
        self.launcher = self.workspace / "Bridge" / "homr_gpu.py"
        self.config = AdapterConfig(
            candidate_id="shipped_homr",
            adapter_id="shipped_homr_direct",
            adapter_revision=ADAPTER_REVISION,
            source_repository="https://github.com/liebharc/homr",
            source_revision="457e7c6518a10ba755db2e60883419e56c4d7369+pr146",
            checkpoint="homr released ONNX checkpoints",
            checkpoint_revision="homr-0.7.0.post38+457e7c6+pr146",
            native_format="HOMR EncodedSymbol token stream",
            input_granularity="page or system image",
            supported_paths=(MeasurementPath.ANNOTATED_CROP, MeasurementPath.COMPLETE_DOCUMENT),
            settings={"gpu": "force", "normalization": "frozen-phase1"},
        )

    def probe(self) -> Mapping[str, Any]:
        return {
            "available": self.python.is_file() and self.launcher.is_file(),
            "python": portable_path(self.python),
            "launcher": portable_path(self.launcher),
            "missing": [
                portable_path(path) for path in (self.python, self.launcher) if not path.is_file()
            ],
        }

    def run(self, item: AdapterInput, output_directory: Path) -> AdapterResult:
        require_supported(self.config, item)
        probe = self.probe()
        if not probe["available"]:
            return unavailable_result(
                self.config,
                item,
                code="HOMR_RUNTIME_MISSING",
                message="The shipped HOMR runtime is not installed",
                probe=probe,
            )
        output_directory.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="s2p-phase2-homr-") as temporary:
            work = Path(temporary)
            source = work / f"input{item.input_path.suffix.casefold()}"
            shutil.copy2(item.input_path, source)
            command = (str(self.python), str(self.launcher), str(source))
            command_for_provenance.set(command)
            environment = {**os.environ, "PYTHONUNBUFFERED": "1"}
            try:
                process = run_monitored(
                    command, cwd=work, timeout_seconds=600, environment=environment
                )
            except OSError as error:
                process = CommandResult(127, 0.0, "", str(error), None, None, "unavailable", False)
            if process.exit_status != 0:
                return _failure(
                    self.config,
                    item,
                    process,
                    code="TIMEOUT" if process.timed_out else "HOMR_FAILED",
                    stage="recognition",
                    message=process.stderr[-2000:] or "HOMR failed without diagnostics",
                    artifacts=_generic_failure_artifacts(
                        output_directory, process, tuple(work.glob("*.musicxml"))
                    ),
                )
            generated = sorted(work.glob("*.musicxml"), key=lambda path: path.stat().st_mtime_ns)
            if not generated:
                return _failure(
                    self.config,
                    item,
                    process,
                    code="HOMR_OUTPUT_MISSING",
                    stage="conversion",
                    message="HOMR did not produce MusicXML",
                    artifacts=_generic_failure_artifacts(output_directory, process),
                )
            token_lines = [
                line.split("Writing XML", 1)[1].strip()
                for line in process.stderr.splitlines()
                if "Writing XML" in line
            ]
            if not token_lines:
                return _failure(
                    self.config,
                    item,
                    process,
                    code="HOMR_NATIVE_OUTPUT_MISSING",
                    stage="artifact_capture",
                    message="HOMR did not emit its EncodedSymbol token stream",
                    artifacts=_generic_failure_artifacts(output_directory, process, (generated[-1],)),
                )
            native = output_directory / "homr.tokens.txt"
            native.write_text("\n".join(token_lines) + "\n", encoding="utf-8")
            musicxml = _copy_musicxml(generated[-1], output_directory)
        canonical, normalizer_warnings, normalization_seconds = _canonicalize(
            musicxml, output_directory / "canonical-events.json"
        )
        log = output_directory / "engine.log"
        log.write_text(_portable_text(process.stderr), encoding="utf-8")
        artifacts = (
            Artifact.from_path("native", native, "text/plain"),
            Artifact.from_path("musicxml", musicxml, "application/vnd.recordare.musicxml+xml"),
            canonical,
            Artifact.from_path("engine_log", log, "text/plain"),
        )
        result = AdapterResult(
            1,
            self.config.candidate_id,
            self.config.adapter_id,
            self.config.sha256,
            item.item_id,
            item.composition_group,
            item.measurement_path,
            RunStatus.SUCCEEDED,
            0,
            normalizer_warnings,
            (
                StageTiming("recognition_and_native_conversion", process.seconds),
                StageTiming("shared_normalization", normalization_seconds),
            ),
            ResourceMeasurements(
                process.peak_ram_bytes,
                process.peak_vram_bytes,
                SAMPLE_INTERVAL_SECONDS,
                True,
                (f"VRAM measurement: {process.vram_measurement}",),
            ),
            artifacts,
            {**base_provenance(self.config, item), "command": _portable_command(command)},
        )
        result.validate()
        return result


class ZeusAdapter:
    def __init__(self, workspace: Path, *, integration: bool) -> None:
        self.workspace = workspace.resolve()
        self.integration = integration
        self.python = self.workspace / "Research" / "omr" / ".venv" / "Scripts" / "python.exe"
        self.zeus_python = (
            self.workspace / "Research" / "omr" / "zeus" / ".venv" / "Scripts" / "python.exe"
        )
        self.runner = self.workspace / "Research" / "omr" / "phase2_zeus_runner.py"
        self.checkpoint = (
            self.workspace
            / "Research"
            / "omr"
            / "zeus"
            / "weights"
            / "zeus-olimpic-1.0-2024-02-12.model"
        )
        self.config = AdapterConfig(
            candidate_id="zeus",
            adapter_id="zeus_app_integration" if integration else "zeus_upstream",
            adapter_revision=ADAPTER_REVISION,
            source_repository="https://github.com/ufal/olimpic-icdar24",
            source_revision="df0d842596ccd199882ff958e628d59327ca6cba",
            checkpoint="zeus-olimpic-1.0-2024-02-12.model",
            checkpoint_revision="2024-02-12",
            native_format="LMX",
            input_granularity="document with HOMR-detected systems" if integration else "system image",
            supported_paths=(
                (MeasurementPath.COMPLETE_DOCUMENT,)
                if integration
                else (MeasurementPath.ANNOTATED_CROP,)
            ),
            settings={
                "preprocessing": "app-width-bucketing" if integration else "upstream",
                "normalization": "frozen-phase1",
                "runner_sha256": sha256_file(self.runner),
                "system_detector_sha256": (
                    sha256_file(self.workspace / "Bridge" / "detect_systems.py")
                    if integration
                    else None
                ),
            },
        )

    def probe(self) -> Mapping[str, Any]:
        required = (self.python, self.zeus_python, self.runner, self.checkpoint)
        return {
            "available": all(path.exists() for path in required),
            "paths": [portable_path(path) for path in required],
            "missing": [portable_path(path) for path in required if not path.exists()],
        }

    def run(self, item: AdapterInput, output_directory: Path) -> AdapterResult:
        require_supported(self.config, item)
        probe = self.probe()
        if not probe["available"]:
            return unavailable_result(
                self.config,
                item,
                code="ZEUS_RUNTIME_MISSING",
                message="The pinned Zeus runtime or checkpoint is unavailable",
                probe=probe,
            )
        output_directory.mkdir(parents=True, exist_ok=True)
        command = (
            str(self.python),
            str(self.runner),
            "--input",
            str(item.input_path.resolve()),
            "--output",
            str(output_directory.resolve()),
            "--mode",
            "integration" if self.integration else "upstream",
        )
        command_for_provenance.set(command)
        try:
            process = run_monitored(command, cwd=self.workspace, timeout_seconds=900)
        except OSError as error:
            process = CommandResult(127, 0.0, "", str(error), None, None, "unavailable", False)
        if process.exit_status != 0:
            return _failure(
                self.config,
                item,
                process,
                code="TIMEOUT" if process.timed_out else "ZEUS_FAILED",
                stage="recognition",
                message=process.stderr[-2000:] or "Zeus failed without diagnostics",
                artifacts=_generic_failure_artifacts(output_directory, process),
            )
        native = output_directory / "native.lmx.json"
        musicxml = output_directory / "score.musicxml"
        canonical, normalizer_warnings, normalization_seconds = _canonicalize(
            musicxml, output_directory / "canonical-events.json"
        )
        log = output_directory / "engine.log"
        log.write_text(
            _portable_text(process.stdout + process.stderr)
            or "(engine emitted no console output)\n",
            encoding="utf-8",
        )
        artifacts = (
            Artifact.from_path("native", native, "application/json"),
            Artifact.from_path("musicxml", musicxml, "application/vnd.recordare.musicxml+xml"),
            canonical,
            Artifact.from_path("engine_log", log, "text/plain"),
        )
        result = AdapterResult(
            1,
            self.config.candidate_id,
            self.config.adapter_id,
            self.config.sha256,
            item.item_id,
            item.composition_group,
            item.measurement_path,
            RunStatus.SUCCEEDED,
            0,
            normalizer_warnings,
            (
                StageTiming("recognition_conversion_stitching", process.seconds),
                StageTiming("shared_normalization", normalization_seconds),
            ),
            ResourceMeasurements(
                process.peak_ram_bytes,
                process.peak_vram_bytes,
                SAMPLE_INTERVAL_SECONDS,
                True,
                (f"VRAM measurement: {process.vram_measurement}",),
            ),
            artifacts,
            {**base_provenance(self.config, item), "command": _portable_command(command)},
        )
        result.validate()
        return result


class LegatoAdapter:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace.resolve()
        self.root = Path(os.environ.get("SHEET2PLAY_LEGATO_ROOT", ""))
        self.python = Path(os.environ.get("SHEET2PLAY_LEGATO_PYTHON", ""))
        self.model = Path(os.environ.get("SHEET2PLAY_LEGATO_MODEL", ""))
        self.musescore = Path(os.environ.get("SHEET2PLAY_MUSESCORE", ""))
        self.config = AdapterConfig(
            candidate_id="legato",
            adapter_id="legato_dedicated_checkpoint",
            adapter_revision=ADAPTER_REVISION,
            source_repository="https://github.com/guang-yng/legato",
            source_revision="179c228d3d5f67113cf739b44891b3abe046f1dc",
            checkpoint="guangyangmusic/legato",
            checkpoint_revision="2d07c5d0e73186f2c0b12e35ea187bbc30dec18c",
            native_format="ABC and token IDs",
            input_granularity="page image",
            supported_paths=(MeasurementPath.ANNOTATED_CROP, MeasurementPath.COMPLETE_DOCUMENT),
            settings={
                "beam_size": 10,
                "max_length": 2048,
                "precision": "fp16",
                "converter_adapter_sha256": sha256_file(
                    self.workspace / "Research" / "omr" / "phase2_legato_convert.py"
                ),
            },
        )

    def probe(self) -> Mapping[str, Any]:
        required = {
            "root": self.root,
            "python": self.python,
            "model": self.model,
            "musescore": self.musescore,
            "inference": self.root / "scripts" / "inference.py",
            "converter": self.root / "utils" / "convert.py",
        }
        missing = [name for name, path in required.items() if not str(path) or not path.exists()]
        return {
            "available": not missing,
            "missing": missing,
            "requirements": {
                name: _portable_argument(str(path)) for name, path in required.items()
            },
            "gated_checkpoint": True,
        }

    def run(self, item: AdapterInput, output_directory: Path) -> AdapterResult:
        require_supported(self.config, item)
        probe = self.probe()
        if not probe["available"]:
            return unavailable_result(
                self.config,
                item,
                code="LEGATO_RUNTIME_MISSING",
                message="LEGATO requires its isolated Python 3.12 runtime, accepted gated checkpoint, and MuseScore converter",
                probe=probe,
            )
        output_directory.mkdir(parents=True, exist_ok=True)
        native = output_directory / "legato.abc.json"
        inference_command = (
            str(self.python),
            str(self.root / "scripts" / "inference.py"),
            "--model_path",
            str(self.model),
            "--processor_path",
            str(self.model),
            "--image_path",
            str(item.input_path.resolve()),
            "--output_path",
            str(native.resolve()),
            "--batch_size",
            "1",
            "--beam_size",
            "10",
            "--device",
            "cuda",
            "--fp16",
        )
        command_for_provenance.set(inference_command)
        try:
            inference = run_monitored(inference_command, cwd=self.root, timeout_seconds=1800)
        except OSError as error:
            inference = CommandResult(
                127, 0.0, "", str(error), None, None, "unavailable", False
            )
        if inference.exit_status != 0:
            return _failure(
                self.config,
                item,
                inference,
                code="TIMEOUT" if inference.timed_out else "LEGATO_FAILED",
                stage="recognition",
                message=inference.stderr[-2000:] or "LEGATO failed without diagnostics",
            )
        if not native.is_file():
            return _failure(
                self.config,
                item,
                inference,
                code="LEGATO_NATIVE_OUTPUT_MISSING",
                stage="artifact_capture",
                message="LEGATO did not produce its ABC/token JSON",
            )
        musicxml = output_directory / "score.musicxml"
        converter = self.workspace / "Research" / "omr" / "phase2_legato_convert.py"
        conversion_command = (
            str(self.python),
            str(converter),
            "--legato-root",
            str(self.root),
            "--input",
            str(native),
            "--output",
            str(musicxml),
            "--musescore",
            str(self.musescore),
        )
        command_for_provenance.set(conversion_command)
        try:
            conversion = run_monitored(conversion_command, cwd=self.root, timeout_seconds=300)
        except OSError as error:
            conversion = CommandResult(
                127, 0.0, "", str(error), None, None, "unavailable", False
            )
        if conversion.exit_status != 0 or not musicxml.is_file():
            return _failure(
                self.config,
                item,
                conversion,
                code="TIMEOUT" if conversion.timed_out else "LEGATO_CONVERSION_FAILED",
                stage="native_to_musicxml",
                message=conversion.stderr[-2000:] or "LEGATO ABC conversion produced no MusicXML",
            )
        canonical, normalizer_warnings, normalization_seconds = _canonicalize(
            musicxml, output_directory / "canonical-events.json"
        )
        log = output_directory / "engine.log"
        log.write_text(
            _portable_text(
                inference.stdout
                + inference.stderr
                + conversion.stdout
                + conversion.stderr
            )
            or "(engine emitted no console output)\n",
            encoding="utf-8",
        )
        artifacts = (
            Artifact.from_path("native", native, "application/json"),
            Artifact.from_path("musicxml", musicxml, "application/vnd.recordare.musicxml+xml"),
            canonical,
            Artifact.from_path("engine_log", log, "text/plain"),
        )
        result = AdapterResult(
            1,
            self.config.candidate_id,
            self.config.adapter_id,
            self.config.sha256,
            item.item_id,
            item.composition_group,
            item.measurement_path,
            RunStatus.SUCCEEDED,
            0,
            normalizer_warnings,
            (
                StageTiming("recognition", inference.seconds),
                StageTiming("native_to_musicxml", conversion.seconds),
                StageTiming("shared_normalization", normalization_seconds),
            ),
            ResourceMeasurements(
                max(value for value in (inference.peak_ram_bytes, conversion.peak_ram_bytes) if value is not None)
                if inference.peak_ram_bytes is not None or conversion.peak_ram_bytes is not None
                else None,
                max(value for value in (inference.peak_vram_bytes, conversion.peak_vram_bytes) if value is not None)
                if inference.peak_vram_bytes is not None or conversion.peak_vram_bytes is not None
                else None,
                SAMPLE_INTERVAL_SECONDS,
                True,
                (
                    f"recognition VRAM measurement: {inference.vram_measurement}",
                    f"conversion VRAM measurement: {conversion.vram_measurement}",
                ),
            ),
            artifacts,
            {
                **base_provenance(self.config, item),
                "inference_command": _portable_command(inference_command),
                "conversion_command": _portable_command(conversion_command),
            },
        )
        result.validate()
        return result


class AudiverisAdapter:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace.resolve()
        self.executable = Path(os.environ.get("SHEET2PLAY_AUDIVERIS_EXECUTABLE", ""))
        self.config = AdapterConfig(
            candidate_id="audiveris",
            adapter_id="audiveris_unattended",
            adapter_revision=ADAPTER_REVISION,
            source_repository="https://github.com/Audiveris/audiveris",
            source_revision="9e1e55cd2746037d059345881c53e6a6754bffbd",
            checkpoint="Audiveris 5.11.0 classifiers",
            checkpoint_revision="5.11.0",
            native_format="Audiveris OMR project",
            input_granularity="complete document",
            supported_paths=(MeasurementPath.COMPLETE_DOCUMENT,),
            settings={
                "batch": True,
                "manual_corrections": False,
                "export": "MusicXML",
                "small_image_preprocessing": "lanczos-width-at-least-2000px-300dpi-v1",
            },
        )

    def probe(self) -> Mapping[str, Any]:
        return {
            "available": bool(str(self.executable)) and self.executable.is_file(),
            "executable": _portable_argument(str(self.executable)),
            "environment_variable": "SHEET2PLAY_AUDIVERIS_EXECUTABLE",
        }

    def run(self, item: AdapterInput, output_directory: Path) -> AdapterResult:
        require_supported(self.config, item)
        probe = self.probe()
        if not probe["available"]:
            return unavailable_result(
                self.config,
                item,
                code="AUDIVERIS_RUNTIME_MISSING",
                message="Pinned Audiveris 5.11.0 is not installed",
                probe=probe,
            )
        output_directory.mkdir(parents=True, exist_ok=True)
        engine_output = output_directory / "audiveris-output"
        engine_output.mkdir(exist_ok=True)
        prepared_input, input_scale, preprocessing_seconds = _prepare_audiveris_input(
            item.input_path, output_directory
        )
        from .phase2r_validation import record_attempt_measurement

        record_attempt_measurement(output_directory, stage="input_preprocessing",
                                   seconds=preprocessing_seconds)
        command = (
            str(self.executable),
            "-batch",
            "-save",
            "-export",
            "-output",
            str(engine_output.resolve()),
            "--",
            str(prepared_input.resolve()),
        )
        command_for_provenance.set(command)
        try:
            process = run_monitored(command, cwd=output_directory, timeout_seconds=1800)
        except OSError as error:
            process = CommandResult(
                127, 0.0, "", str(error), None, None, "unavailable", False
            )
        record_attempt_measurement(
            output_directory, stage="recognition_and_native_conversion",
            seconds=process.seconds, peak_ram_bytes=process.peak_ram_bytes,
            peak_vram_bytes=process.peak_vram_bytes,
            vram_measurement=process.vram_measurement,
        )
        if process.exit_status != 0:
            return _failure(
                self.config,
                item,
                process,
                code="TIMEOUT" if process.timed_out else "AUDIVERIS_FAILED",
                stage="recognition",
                message=process.stderr[-2000:] or process.stdout[-2000:] or "Audiveris failed without diagnostics",
                artifacts=_audiveris_failure_artifacts(
                    output_directory, engine_output, process, prepared_input
                ),
                provenance_extra={
                    "input_scale": input_scale,
                    "prepared_input_sha256": sha256_file(prepared_input),
                },
                extra_timings=(StageTiming("input_preprocessing", preprocessing_seconds),),
            )
        omr_files = sorted(engine_output.rglob("*.omr"))
        musicxml_files = sorted(
            [*engine_output.rglob("*.mxl"), *engine_output.rglob("*.musicxml"), *engine_output.rglob("*.xml")]
        )
        if len(omr_files) != 1 or len(musicxml_files) != 1:
            return _failure(
                self.config,
                item,
                process,
                code="AUDIVERIS_OUTPUT_INVALID",
                stage="artifact_capture",
                message=f"Expected one OMR project and one MusicXML export; found {len(omr_files)} and {len(musicxml_files)}",
                artifacts=_audiveris_failure_artifacts(
                    output_directory, engine_output, process, prepared_input
                ),
                provenance_extra={
                    "input_scale": input_scale,
                    "prepared_input_sha256": sha256_file(prepared_input),
                },
                extra_timings=(StageTiming("input_preprocessing", preprocessing_seconds),),
            )
        native = output_directory / "audiveris.omr"
        shutil.copy2(omr_files[0], native)
        musicxml = _copy_musicxml(musicxml_files[0], output_directory)
        normalization_started = time.perf_counter()
        try:
            canonical, normalizer_warnings, normalization_seconds = _canonicalize(
                musicxml, output_directory / "canonical-events.json"
            )
        finally:
            record_attempt_measurement(output_directory, stage="shared_normalization",
                                       seconds=time.perf_counter() - normalization_started)
        log = output_directory / "engine.log"
        log.write_text(
            _portable_text(process.stdout + process.stderr)
            or "(engine emitted no console output)\n",
            encoding="utf-8",
        )
        result = AdapterResult(
            1,
            self.config.candidate_id,
            self.config.adapter_id,
            self.config.sha256,
            item.item_id,
            item.composition_group,
            item.measurement_path,
            RunStatus.SUCCEEDED,
            0,
            normalizer_warnings,
            (
                StageTiming("input_preprocessing", preprocessing_seconds),
                StageTiming("recognition_and_native_conversion", process.seconds),
                StageTiming("shared_normalization", normalization_seconds),
            ),
            ResourceMeasurements(
                process.peak_ram_bytes,
                process.peak_vram_bytes,
                SAMPLE_INTERVAL_SECONDS,
                True,
                (f"VRAM measurement: {process.vram_measurement}",),
            ),
            (
                Artifact.from_path("native", native, "application/vnd.audiveris.omr"),
                Artifact.from_path("musicxml", musicxml, "application/vnd.recordare.musicxml"),
                canonical,
                Artifact.from_path("engine_log", log, "text/plain"),
                Artifact.from_path("attempt_measurements", output_directory / "attempt-measurements.json", "application/json"),
                *(
                    (Artifact.from_path("prepared_input", prepared_input, "image/png"),)
                    if input_scale > 1 else ()
                ),
            ),
            {
                **base_provenance(self.config, item),
                "command": _portable_command(command),
                "input_scale": input_scale,
                "prepared_input_sha256": sha256_file(prepared_input),
            },
        )
        result.validate()
        return result


def candidate_adapters(workspace: Path) -> tuple[object, ...]:
    return (
        ShippedHomrAdapter(workspace),
        ZeusAdapter(workspace, integration=False),
        ZeusAdapter(workspace, integration=True),
        LegatoAdapter(workspace),
        AudiverisAdapter(workspace),
    )
