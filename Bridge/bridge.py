from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterable, Iterator, Sequence

from musicxml_normalizer import (
    MusicNote,
    MusicXmlNormalizationError,
    NormalizedScore,
    TempoChange,
    add_seconds,
    combine_score_pages,
    normalize_musicxml,
)
from progress_protocol import emit_progress


LOGGER = logging.getLogger("sheet2play.bridge")
SCHEMA_VERSION = 2
HOMR_ENGINE_REVISION = "homr-0.7.0.post34+2d0c0a6"
ZEUS_ENGINE_REVISION = "df0d842596ccd199882ff958e628d59327ca6cba"
ZEUS_MODEL_REVISION = "2024-02-12"
OUTPUT_SUFFIXES = frozenset({".musicxml", ".mxl"})
SUPPORTED_INPUT_SUFFIXES = frozenset(
    {".bmp", ".jpeg", ".jpg", ".pdf", ".png", ".tif", ".tiff", ".webp", ".xml", ".mxl", ".musicxml"}
)
HOMR_ENVIRONMENT_NAME = ".venv-homr-gpu"
HOMR_LAUNCHER_FILE = Path(__file__).with_name("homr_gpu.py")
PDF_RENDERER_FILE = Path(__file__).with_name("render_pdf.py")
HOMR_PYTHON_OVERRIDE = "SHEET2PLAY_HOMR_PYTHON"
ERROR_PREFIX = "SHEET2PLAY_ERROR:"
EXIT_CODES = {
    "INPUT_INVALID": 2,
    "RUNTIME_MISSING": 3,
    "MODEL_INVALID": 3,
    "CUDA_UNAVAILABLE": 4,
    "CUDA_OUT_OF_MEMORY": 4,
    "ZEUS_INFERENCE_FAILED": 5,
    "ZEUS_OUTPUT_TRUNCATED": 6,
    "KERN_INVALID": 6,
    "KERN_PARSE_FAILED": 6,
    "MUSICXML_PARSE_FAILED": 6,
    "NORMALIZATION_FAILED": 7,
}


class BridgeError(RuntimeError):
    def __init__(
        self,
        code: str,
        stage: str,
        message: str,
        *,
        page: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.stage = stage
        self.page = page

    @property
    def exit_code(self) -> int:
        return EXIT_CODES.get(self.code, 7)


@dataclass(frozen=True, slots=True)
class OmrResult:
    schema_version: int
    engine: str
    engine_revision: str
    tempo_changes: tuple[TempoChange, ...]
    notes: tuple[MusicNote, ...]


@dataclass(frozen=True, slots=True)
class EngineOutput:
    score: NormalizedScore
    page_count: int
    staff_count: int


@dataclass(frozen=True, slots=True)
class ZeusEngineOutput:
    result: OmrResult
    page_count: int
    staff_count: int
    runtime: dict[str, object]


def parse_arguments(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a Sheet2Play OMR engine and emit normalized score JSON"
    )
    parser.add_argument("input_path", type=Path, help="Path to a sheet image or PDF")
    parser.add_argument(
        "--engine",
        choices=("homr", "zeus", "musicxml"),
        default="homr",
        help="OMR engine; homr is production and Zeus is an experimental local engine, musicxml parses direct MXL files",
    )
    return parser.parse_args(arguments)


def validate_input_path(input_path: Path) -> Path:
    try:
        resolved = input_path.expanduser().resolve(strict=True)
    except OSError as error:
        raise BridgeError(
            "INPUT_INVALID", "input", f"Input file is unavailable: {input_path}"
        ) from error
    if not resolved.is_file():
        raise BridgeError("INPUT_INVALID", "input", f"Input is not a file: {resolved}")
    if resolved.suffix.lower() not in SUPPORTED_INPUT_SUFFIXES:
        supported = ", ".join(sorted(SUPPORTED_INPUT_SUFFIXES))
        raise BridgeError(
            "INPUT_INVALID",
            "input",
            f"Unsupported input extension '{resolved.suffix}'. Supported: {supported}",
        )
    return resolved


def file_sha256(
    path: Path, *, error_code: str = "MODEL_INVALID", stage: str = "hash"
) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as error:
        raise BridgeError(error_code, stage, f"Could not hash {path}: {error}") from error
    return digest.hexdigest()


def _environment_python_candidates(
    environment_name: str, override_name: str
) -> Iterable[Path]:
    configured = os.environ.get(override_name)
    if configured:
        yield Path(configured).expanduser()
    bridge_directory = Path(__file__).resolve().parent
    executable = Path("Scripts/python.exe") if os.name == "nt" else Path("bin/python")
    yield bridge_directory / environment_name / executable
    for ancestor in bridge_directory.parents:
        yield ancestor / "Bridge" / environment_name / executable


def _resolve_environment_python(environment_name: str, override_name: str) -> Path:
    checked: list[Path] = []
    for candidate in _environment_python_candidates(environment_name, override_name):
        try:
            resolved = candidate.resolve(strict=True)
        except OSError:
            checked.append(candidate)
            continue
        if resolved.is_file():
            return resolved
        checked.append(candidate)
    raise BridgeError(
        "RUNTIME_MISSING",
        "runtime",
        f"Python environment '{environment_name}' was not found. Set {override_name} "
        f"or run the matching setup script. Checked: {', '.join(map(str, checked))}",
    )


def resolve_homr_python() -> Path:
    return _resolve_environment_python(HOMR_ENVIRONMENT_NAME, HOMR_PYTHON_OVERRIDE)


def list_musicxml_files(directory: Path) -> dict[Path, tuple[int, int]]:
    try:
        entries = tuple(directory.iterdir())
    except OSError as error:
        raise BridgeError(
            "NORMALIZATION_FAILED",
            "homr_output",
            f"Cannot inspect OMR output directory: {directory}",
        ) from error
    files: dict[Path, tuple[int, int]] = {}
    for path in entries:
        if not path.is_file() or path.suffix.lower() not in OUTPUT_SUFFIXES:
            continue
        try:
            resolved = path.resolve(strict=True)
            stat = resolved.stat()
        except OSError:
            continue
        files[resolved] = (stat.st_mtime_ns, stat.st_size)
    return files


def select_generated_output(
    input_path: Path,
    files_before: dict[Path, tuple[int, int]],
    started_at_ns: int,
) -> Path:
    files_after = list_musicxml_files(input_path.parent)
    changed = [path for path, value in files_after.items() if files_before.get(path) != value]
    if not changed:
        changed = [
            path
            for path, (modified, _) in files_after.items()
            if modified >= started_at_ns - 2_000_000_000
        ]
    if not changed:
        raise BridgeError(
            "NORMALIZATION_FAILED",
            "homr_output",
            f"homr completed without creating MusicXML in {input_path.parent}",
        )
    return min(
        changed,
        key=lambda path: (
            path.stem.casefold() != input_path.stem.casefold(),
            -files_after[path][0],
            path.name.casefold(),
        ),
    )


def run_homr(input_path: Path) -> Path:
    homr_python = resolve_homr_python()
    if not HOMR_LAUNCHER_FILE.is_file():
        raise BridgeError(
            "RUNTIME_MISSING", "homr", f"homr launcher is missing: {HOMR_LAUNCHER_FILE}"
        )
    files_before = list_musicxml_files(input_path.parent)
    started_at_ns = time.time_ns()
    environment = os.environ.copy()
    environment["PYTHONUNBUFFERED"] = "1"
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            [str(homr_python), str(HOMR_LAUNCHER_FILE.resolve()), str(input_path)],
            cwd=input_path.parent,
            stdin=subprocess.DEVNULL,
            stdout=sys.stderr,
            stderr=sys.stderr,
            env=environment,
            check=False,
        )
    except OSError as error:
        raise BridgeError("RUNTIME_MISSING", "homr", f"Failed to start homr: {error}") from error
    LOGGER.info("stage=homr elapsed_seconds=%.3f", time.perf_counter() - started)
    if completed.returncode != 0:
        raise BridgeError(
            "NORMALIZATION_FAILED", "homr", f"homr failed with exit code {completed.returncode}"
        )
    return select_generated_output(input_path, files_before, started_at_ns)


def render_pdf_pages(input_path: Path, output_directory: Path) -> list[Path]:
    homr_python = resolve_homr_python()
    if not PDF_RENDERER_FILE.is_file():
        raise BridgeError("RUNTIME_MISSING", "pdf_render", "PDF renderer is missing")
    try:
        completed = subprocess.run(
            [str(homr_python), str(PDF_RENDERER_FILE), str(input_path), str(output_directory)],
            cwd=output_directory,
            stdin=subprocess.DEVNULL,
            stdout=sys.stderr,
            stderr=sys.stderr,
            check=False,
        )
    except OSError as error:
        raise BridgeError(
            "RUNTIME_MISSING", "pdf_render", f"Failed to start PDF renderer: {error}"
        ) from error
    if completed.returncode != 0:
        raise BridgeError(
            "INPUT_INVALID", "pdf_render", f"PDF renderer failed with exit code {completed.returncode}"
        )
    pages = sorted(output_directory.glob("page-*.png"))
    if not pages:
        raise BridgeError("INPUT_INVALID", "pdf_render", "PDF renderer produced no pages")
    return pages


@contextmanager
def prepare_homr_inputs(input_path: Path) -> Iterator[list[Path]]:
    with tempfile.TemporaryDirectory(prefix="sheet2play-homr-") as temporary:
        directory = Path(temporary)
        if input_path.suffix.lower() == ".pdf":
            yield render_pdf_pages(input_path, directory)
        else:
            copied = directory / f"input{input_path.suffix.lower()}"
            shutil.copy2(input_path, copied)
            yield [copied]


def _normalization_error(error: MusicXmlNormalizationError) -> BridgeError:
    if error.stage == "runtime":
        code = "RUNTIME_MISSING"
    elif error.stage in {"parse", "repeat_expansion", "tie_merging"}:
        code = "MUSICXML_PARSE_FAILED"
    else:
        code = "NORMALIZATION_FAILED"
    return BridgeError(code, error.stage, str(error))


def run_homr_engine(input_path: Path) -> EngineOutput:
    try:
        with prepare_homr_inputs(input_path) as inputs:
            page_count = len(inputs)
            emit_progress(
                engine="homr",
                stage="input_inspection",
                status="completed",
                message=f"Prepared {page_count} page(s)",
                page_count=page_count,
                completed_pages=0,
            )
            outputs: list[Path] = []
            for page_number, omr_input in enumerate(inputs, start=1):
                started = time.perf_counter()
                emit_progress(
                    engine="homr",
                    stage="page_inference",
                    status="started",
                    message=f"Processing page {page_number} of {page_count}",
                    page=page_number,
                    page_count=page_count,
                    completed_pages=page_number - 1,
                )
                outputs.append(run_homr(omr_input))
                emit_progress(
                    engine="homr",
                    stage="page_inference",
                    status="completed",
                    message=f"Completed page {page_number} of {page_count}",
                    page=page_number,
                    page_count=page_count,
                    completed_pages=page_number,
                    page_duration_seconds=time.perf_counter() - started,
                )
            emit_progress(
                engine="homr",
                stage="normalization",
                status="started",
                message="Normalizing MusicXML",
                page_count=page_count,
                completed_pages=page_count,
            )
            pages = [normalize_musicxml(path) for path in outputs]
    except MusicXmlNormalizationError as error:
        raise _normalization_error(error) from error
    score = combine_score_pages(pages)
    emit_progress(
        engine="homr",
        stage="normalization",
        status="completed",
        message="MusicXML normalized",
        page_count=len(pages),
        completed_pages=len(pages),
    )
    return EngineOutput(score, len(pages), score.staff_count)


_ZEUS_ERROR_CODES = {
    "ASSET_LOCK_INVALID": "MODEL_INVALID",
    "ASSET_INVALID": "MODEL_INVALID",
    "ASSET_MISSING": "MODEL_INVALID",
    "SOURCE_INVALID": "MODEL_INVALID",
    "CUDA_DEVICE_MISMATCH": "CUDA_UNAVAILABLE",
    "INFERENCE_FAILED": "ZEUS_INFERENCE_FAILED",
    "DECODER_INVALID": "ZEUS_INFERENCE_FAILED",
    "GRAMMAR_INITIALIZATION_FAILED": "MODEL_INVALID",
    "KERN_TRUNCATED": "ZEUS_OUTPUT_TRUNCATED",
    "KERN_PAGE_LAYOUT_MISMATCH": "KERN_INVALID",
    "SEMANTIC_INVALID": "NORMALIZATION_FAILED",
    "EXPORT_FAILED": "NORMALIZATION_FAILED",
    "PREPROCESSING_FAILED": "NORMALIZATION_FAILED",
}


def _map_zeus_error(error: Exception) -> BridgeError:
    original_code = str(getattr(error, "code", "ZEUS_INFERENCE_FAILED"))
    code = _ZEUS_ERROR_CODES.get(original_code, original_code)
    if code not in EXIT_CODES:
        code = "ZEUS_INFERENCE_FAILED"
    stage = str(getattr(error, "stage", "inference"))
    page_value = getattr(error, "page", None)
    page = page_value if isinstance(page_value, int) and not isinstance(page_value, bool) else None
    return BridgeError(code, stage, str(error), page=page)


def _zeus_progress(stage: str, **details: object) -> None:
    page = details.get("page")
    total_pages = details.get("total_pages")
    pages = details.get("pages")
    page_number = page if isinstance(page, int) else None
    page_count = total_pages if isinstance(total_pages, int) else pages if isinstance(pages, int) else None
    completed_pages = max(0, page_number - 1) if page_number is not None else None

    if stage == "input_inspected":
        emit_progress(
            engine="zeus",
            stage="input_inspection",
            status="completed",
            message=f"Prepared {page_count} page(s)",
            page_count=page_count,
            completed_pages=0,
        )
    elif stage == "model_loading":
        emit_progress(
            engine="zeus",
            stage="model_load",
            status="started",
            message="Loading Zeus on CUDA",
            page_count=page_count,
            completed_pages=0,
        )
    elif stage == "model_loaded":
        emit_progress(
            engine="zeus",
            stage="model_load",
            status="completed",
            message="Zeus loaded on CUDA",
            page_count=page_count,
            completed_pages=0,
        )
    elif stage == "grammar_loading":
        emit_progress(
            engine="zeus",
            stage="model_load",
            status="started",
            message="Initializing grammar-constrained retry",
            page=page_number,
            page_count=page_count,
            completed_pages=completed_pages,
        )
    elif stage == "page_start":
        emit_progress(
            engine="zeus",
            stage="page_inference",
            status="started",
            message=f"Reading page {page_number} of {page_count} with beam decoding",
            page=page_number,
            page_count=page_count,
            completed_pages=completed_pages,
        )
    elif stage == "page_retry":
        emit_progress(
            engine="zeus",
            stage="page_inference",
            status="started",
            message=f"Beam output invalid—retrying page {page_number} with grammar decoding",
            page=page_number,
            page_count=page_count,
            completed_pages=completed_pages,
        )
    elif stage == "page_complete":
        seconds = details.get("seconds")
        tokens = details.get("tokens")
        decoder = str(details.get("decoder", "beam"))
        emit_progress(
            engine="zeus",
            stage="page_inference",
            status="completed",
            message=f"Completed page {page_number} of {page_count} with {decoder} decoding",
            page=page_number,
            page_count=page_count,
            completed_pages=page_number,
            page_duration_seconds=float(seconds) if isinstance(seconds, (int, float)) else None,
            token_count=tokens if isinstance(tokens, int) else None,
        )
    elif stage == "normalization_start":
        emit_progress(
            engine="zeus",
            stage="normalization",
            status="started",
            message="Combining and normalizing Zeus notation",
            page_count=page_count,
            completed_pages=page_count,
        )
    elif stage == "normalization_complete":
        emit_progress(
            engine="zeus",
            stage="normalization",
            status="completed",
            message="Zeus notation normalized",
            page_count=page_count,
            completed_pages=page_count,
        )
    elif stage == "export_validation_start":
        emit_progress(
            engine="zeus",
            stage="musicxml_export",
            status="started",
            message="Validating MusicXML and MIDI round trips",
            page_count=page_count,
            completed_pages=page_count,
        )
    elif stage == "export_validation_complete":
        emit_progress(
            engine="zeus",
            stage="musicxml_export",
            status="completed",
            message="MusicXML and MIDI round trips validated",
            page_count=page_count,
            completed_pages=page_count,
        )
    elif stage == "complete":
        emit_progress(
            engine="zeus",
            stage="complete",
            status="completed",
            message="Zeus processing completed",
            page_count=page_count,
            completed_pages=page_count,
        )


def _require_mapping(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise BridgeError("NORMALIZATION_FAILED", "output_validation", f"{name} must be an object")
    return value


def _require_sequence(value: object, name: str) -> list[object]:
    if not isinstance(value, list):
        raise BridgeError("NORMALIZATION_FAILED", "output_validation", f"{name} must be an array")
    return value


def _require_string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BridgeError("NORMALIZATION_FAILED", "output_validation", f"{name} must be a nonempty string")
    return value


def _require_integer(value: object, name: str, *, minimum: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise BridgeError(
            "NORMALIZATION_FAILED",
            "output_validation",
            f"{name} must be an integer greater than or equal to {minimum}",
        )
    return value


def _require_number(value: object, name: str, *, positive: bool = False) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise BridgeError("NORMALIZATION_FAILED", "output_validation", f"{name} must be numeric")
    number = float(value)
    if not math.isfinite(number) or (number <= 0 if positive else number < 0):
        qualifier = "positive" if positive else "non-negative"
        raise BridgeError(
            "NORMALIZATION_FAILED",
            "output_validation",
            f"{name} must be finite and {qualifier}",
        )
    return number


def _parse_zeus_result(value: object) -> OmrResult:
    payload = _require_mapping(value, "Zeus result")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise BridgeError("NORMALIZATION_FAILED", "output_validation", "Unsupported Zeus schema")
    if payload.get("engine") != "zeus":
        raise BridgeError("NORMALIZATION_FAILED", "output_validation", "Incorrect Zeus engine name")
    if payload.get("engine_revision") != ZEUS_ENGINE_REVISION:
        raise BridgeError("MODEL_INVALID", "output_validation", "Incorrect Zeus engine revision")

    tempo_changes: list[TempoChange] = []
    for index, item in enumerate(_require_sequence(payload.get("tempo_changes"), "tempo_changes")):
        tempo = _require_mapping(item, f"tempo_changes[{index}]")
        tempo_changes.append(
            TempoChange(
                start_beat=_require_number(tempo.get("start_beat"), f"tempo_changes[{index}].start_beat"),
                bpm=_require_number(tempo.get("bpm"), f"tempo_changes[{index}].bpm", positive=True),
            )
        )
    if not tempo_changes or tempo_changes[0].start_beat != 0:
        raise BridgeError(
            "NORMALIZATION_FAILED",
            "output_validation",
            "Zeus tempo map must start at beat zero",
        )
    if any(
        current.start_beat <= previous.start_beat
        for previous, current in zip(tempo_changes, tempo_changes[1:])
    ):
        raise BridgeError(
            "NORMALIZATION_FAILED",
            "output_validation",
            "Zeus tempo changes must be strictly ordered by beat",
        )

    notes: list[MusicNote] = []
    for index, item in enumerate(_require_sequence(payload.get("notes"), "notes")):
        note = _require_mapping(item, f"notes[{index}]")
        midi_pitch = _require_integer(note.get("midi_pitch"), f"notes[{index}].midi_pitch", minimum=0)
        if midi_pitch > 127:
            raise BridgeError(
                "NORMALIZATION_FAILED",
                "output_validation",
                f"notes[{index}].midi_pitch exceeds 127",
            )
        notes.append(
            MusicNote(
                pitch=_require_string(note.get("pitch"), f"notes[{index}].pitch"),
                midi_pitch=midi_pitch,
                start_beat=_require_number(note.get("start_beat"), f"notes[{index}].start_beat"),
                duration_beats=_require_number(
                    note.get("duration_beats"), f"notes[{index}].duration_beats", positive=True
                ),
                start_seconds=_require_number(note.get("start_seconds"), f"notes[{index}].start_seconds"),
                duration_seconds=_require_number(
                    note.get("duration_seconds"), f"notes[{index}].duration_seconds", positive=True
                ),
                part_index=_require_integer(note.get("part_index"), f"notes[{index}].part_index", minimum=0),
                staff_index=_require_integer(
                    note.get("staff_index"),
                    f"notes[{index}].staff_index",
                    minimum=0,
                ),
                voice_identifier=_require_string(
                    note.get("voice_identifier"), f"notes[{index}].voice_identifier"
                ),
            )
        )
    if not notes:
        raise BridgeError("NORMALIZATION_FAILED", "note_validation", "Zeus output contains no notes")
    notes.sort(
        key=lambda item: (
            item.start_beat,
            item.part_index,
            item.staff_index,
            item.voice_identifier,
            item.midi_pitch,
        )
    )
    return OmrResult(
        schema_version=SCHEMA_VERSION,
        engine="zeus",
        engine_revision=ZEUS_ENGINE_REVISION,
        tempo_changes=tuple(tempo_changes),
        notes=tuple(notes),
    )


def run_zeus_engine(
    input_path: Path,
    *,
    inference_function: Callable[..., object] | None = None,
) -> ZeusEngineOutput:
    research_error_type: type[BaseException] | tuple[type[BaseException], ...] = ()
    if inference_function is None:
        try:
            from sheet2play_omr.errors import ResearchError
            from sheet2play_omr.inference import infer_document
        except (ImportError, OSError) as error:
            raise BridgeError(
                "RUNTIME_MISSING",
                "runtime",
                "Zeus research package is unavailable. Run "
                "Research/omr/setup_research.ps1 -Profile Inference.",
            ) from error
        inference_function = infer_document
        research_error_type = ResearchError

    try:
        with tempfile.TemporaryDirectory(prefix="sheet2play-zeus-") as temporary:
            summary = inference_function(
                input_path,
                Path(temporary),
                mode="zeus",
                progress_callback=_zeus_progress,
            )
            summary_mapping = _require_mapping(summary, "Zeus summary")
            result = _parse_zeus_result(summary_mapping.get("omr_result"))
            page_count = _require_integer(summary_mapping.get("page_count"), "page_count", minimum=1)
            staff_count = _require_integer(summary_mapping.get("staff_count"), "staff_count", minimum=1)
            return ZeusEngineOutput(result, page_count, staff_count, {})
    except research_error_type as error:
        raise _map_zeus_error(error) from error


def emit_json(result: OmrResult) -> None:
    json.dump(
        asdict(result),
        sys.stdout,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    )
    sys.stdout.write("\n")
    sys.stdout.flush()


def emit_structured_error(error: BridgeError) -> None:
    payload = {
        "code": error.code,
        "stage": error.stage,
        "message": str(error),
        "page": error.page,
    }
    sys.stderr.write(
        ERROR_PREFIX
        + json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        + "\n"
    )
    sys.stderr.flush()


def main(arguments: Sequence[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    started = time.perf_counter()
    try:
        parsed = parse_arguments(arguments)
        input_path = validate_input_path(parsed.input_path)
        source_hash = file_sha256(
            input_path, error_code="INPUT_INVALID", stage="source_hash"
        )
        engine = str(parsed.engine)
        revision = (
            HOMR_ENGINE_REVISION
            if engine == "homr"
            else "direct-xml" if engine == "musicxml"
            else ZEUS_ENGINE_REVISION
        )
        LOGGER.info(
            "engine=%s engine_revision=%s source_sha256=%s input=%s",
            engine,
            revision,
            source_hash,
            input_path,
        )
        if engine == "homr":
            output = run_homr_engine(input_path)
            try:
                notes = add_seconds(output.score)
            except MusicXmlNormalizationError as error:
                raise _normalization_error(error) from error
            if not notes:
                raise BridgeError(
                    "NORMALIZATION_FAILED", "note_validation", "OMR output contains no notes"
                )
            result = OmrResult(
                schema_version=SCHEMA_VERSION,
                engine=engine,
                engine_revision=revision,
                tempo_changes=output.score.tempo_changes,
                notes=notes,
            )
            page_count = output.page_count
            staff_count = output.staff_count
        elif engine == "musicxml":
            from musicxml_normalizer import normalize_musicxml
            score = normalize_musicxml(input_path, expand_repeats=True, skip_grace_notes=False)
            try:
                notes = add_seconds(score)
            except MusicXmlNormalizationError as error:
                raise _normalization_error(error) from error
            result = OmrResult(
                schema_version=SCHEMA_VERSION,
                engine=engine,
                engine_revision=revision,
                tempo_changes=score.tempo_changes,
                notes=notes,
            )
            page_count = 1
            staff_count = score.staff_count
        else:
            zeus_output = run_zeus_engine(input_path)
            result = zeus_output.result
            page_count = zeus_output.page_count
            staff_count = zeus_output.staff_count
        LOGGER.info(
            "engine=%s pages=%d staffs=%d notes=%d tempos=%d total_seconds=%.3f processing_seconds=%.3f",
            engine,
            page_count,
            staff_count,
            len(result.notes),
            len(result.tempo_changes),
            max(note.start_seconds + note.duration_seconds for note in result.notes),
            time.perf_counter() - started,
        )
        emit_json(result)
        return 0
    except BridgeError as error:
        LOGGER.error("code=%s stage=%s page=%s %s", error.code, error.stage, error.page, error)
        emit_structured_error(error)
        return error.exit_code
    except KeyboardInterrupt:
        error = BridgeError("NORMALIZATION_FAILED", "inference", "OMR processing was interrupted")
        emit_structured_error(error)
        return 130
    except Exception as error:
        LOGGER.exception("Unexpected bridge failure")
        wrapped = BridgeError(
            "NORMALIZATION_FAILED", "unexpected", f"Unexpected bridge failure: {error}"
        )
        emit_structured_error(wrapped)
        return wrapped.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
