from __future__ import annotations

import hashlib
import json
import math
import os
import statistics
import subprocess
import sys
import time
from dataclasses import asdict
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable

from PIL import Image

from .errors import ResearchError
from .events import CanonicalScore, extract_canonical_events, parse_kern

from .metrics import MetricNote, calculate_note_metrics
from .olimpic import OlimpicSample
from .production import RETRYABLE_PAGE_CODES


CHECKPOINT_SCHEMA_VERSION = 1
DECODER_STATE_REVISION = 3
HOMR_TIMEOUT_SECONDS = 600


def _workspace_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "Bridge" / "bridge.py").is_file():
            return candidate
    raise ResearchError("RUNTIME_MISSING", "benchmark", "Cannot locate the Sheet2Play workspace")


def _fraction(value: float | int | str | Fraction) -> Fraction:
    if isinstance(value, Fraction):
        return value
    return Fraction(str(value)).limit_denominator(4096)


def _canonical_metric_notes(score: CanonicalScore) -> list[MetricNote]:
    notes = [
        MetricNote(
            pitch=int(event.midi_pitch),
            onset=Fraction(event.onset),
            duration=Fraction(event.duration),
            staff=event.staff,
            voice=event.voice,
        )
        for event in score.events
        if event.kind == "note" and event.midi_pitch is not None
    ]
    if not notes:
        raise ResearchError("SEMANTIC_INVALID", "benchmark", "Prediction contains no notes")
    return notes


def load_ground_truth_notes(path: Path) -> list[MetricNote]:
    bridge_directory = _workspace_root() / "Bridge"
    bridge_path = str(bridge_directory)
    if bridge_path not in sys.path:
        sys.path.insert(0, bridge_path)
    try:
        from musicxml_normalizer import MusicXmlNormalizationError, normalize_musicxml

        score = normalize_musicxml(
            path,
            expand_repeats=False,
            skip_grace_notes=True,
        )
    except (ImportError, OSError) as error:
        raise ResearchError(
            "GROUND_TRUTH_INVALID", "ground_truth", f"Cannot load MusicXML normalizer: {error}"
        ) from error
    except MusicXmlNormalizationError as error:
        raise ResearchError(
            "GROUND_TRUTH_INVALID", "ground_truth", f"Cannot normalize {path}: {error}"
        ) from error
    notes = [
        MetricNote(
            pitch=note.midi_pitch,
            onset=_fraction(note.start_beat),
            duration=_fraction(note.duration_beats),
            staff=note.staff_index,
            voice=note.voice_identifier,
        )
        for note in score.notes
    ]
    if not notes:
        raise ResearchError("GROUND_TRUTH_INVALID", "ground_truth", f"No notes in {path}")
    return notes


def _serialize_metrics(predicted: list[MetricNote], expected: list[MetricNote]) -> dict[str, Any]:
    payload = asdict(calculate_note_metrics(predicted, expected))
    if not math.isfinite(payload["mean_offset_error"]):
        payload["mean_offset_error"] = None
    return payload


def _error_payload(error: Exception) -> dict[str, Any]:
    return {
        "code": str(getattr(error, "code", error.__class__.__name__)),
        "stage": str(getattr(error, "stage", "benchmark")),
        "message": str(error)[:2000],
        "page": getattr(error, "page", None),
    }


def _result_row(
    sample: OlimpicSample,
    prediction: PageInference,
    canonical: CanonicalScore,
    expected: list[MetricNote],
    *,
    elapsed_seconds: float,
    fallback_attempted: bool,
) -> dict[str, Any]:
    return {
        "id": sample.identifier,
        "score_id": sample.score_id,
        "valid": True,
        "decoder": prediction.mode,
        "fallback_attempted": fallback_attempted,
        "seconds": elapsed_seconds,
        "decoder_seconds": prediction.seconds,
        "peak_vram_bytes": prediction.peak_vram_bytes,
        "tokens": prediction.tokens,
        "kern_sha256": hashlib.sha256(prediction.kern.encode("utf-8")).hexdigest(),
        "metrics": _serialize_metrics(_canonical_metric_notes(canonical), expected),
    }


def _validate_transcoda_prediction(prediction: PageInference) -> CanonicalScore:
    parsed = parse_kern(prediction.kern)
    return extract_canonical_events(parsed, validate_ties=False)


def _transcoda_pair(
    runner: TranscodaRunner,
    sample: OlimpicSample,
    expected: list[MetricNote],
    *,
    page: int,
    total: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    with Image.open(sample.image) as source:
        image = source.convert("RGB")
    beam_started = time.perf_counter()
    try:
        beam_prediction = runner.predict(image, page=page, total_pages=total, mode="beam")
        beam_canonical = _validate_transcoda_prediction(beam_prediction)
        beam_elapsed = time.perf_counter() - beam_started
        beam_row = _result_row(
            sample,
            beam_prediction,
            beam_canonical,
            expected,
            elapsed_seconds=beam_elapsed,
            fallback_attempted=False,
        )
        return beam_row, dict(beam_row)
    except ResearchError as beam_error:
        beam_elapsed = time.perf_counter() - beam_started
        beam_row = {
            "id": sample.identifier,
            "score_id": sample.score_id,
            "valid": False,
            "decoder": "beam",
            "fallback_attempted": False,
            "seconds": beam_elapsed,
            "peak_vram_bytes": int(runner.torch.cuda.max_memory_allocated(0)),
            "error": _error_payload(beam_error),
        }
        if beam_error.code not in RETRYABLE_PAGE_CODES:
            production_row = dict(beam_row)
            production_row["fallback_attempted"] = False
            return beam_row, production_row
        return beam_row, _grammar_retry(
            runner,
            sample,
            expected,
            beam_row,
            image=image,
            page=page,
            total=total,
        )
    except Exception:
        raise
    finally:
        image.close()


def _grammar_retry(
    runner: TranscodaRunner,
    sample: OlimpicSample,
    expected: list[MetricNote],
    beam_row: dict[str, Any],
    *,
    image: Image.Image,
    page: int,
    total: int,
) -> dict[str, Any]:
    grammar_started = time.perf_counter()
    beam_seconds = float(beam_row.get("seconds", 0.0))
    try:
        grammar_prediction = runner.predict(
            image,
            page=page,
            total_pages=total,
            mode="grammar",
        )
        grammar_canonical = _validate_transcoda_prediction(grammar_prediction)
        production_row = _result_row(
            sample,
            grammar_prediction,
            grammar_canonical,
            expected,
            elapsed_seconds=beam_seconds + (time.perf_counter() - grammar_started),
            fallback_attempted=True,
        )
        production_row["beam_error"] = beam_row["error"]
        return production_row
    except ResearchError as grammar_error:
        return {
            "id": sample.identifier,
            "score_id": sample.score_id,
            "valid": False,
            "decoder": "grammar",
            "fallback_attempted": True,
            "seconds": beam_seconds + (time.perf_counter() - grammar_started),
            "peak_vram_bytes": int(runner.torch.cuda.max_memory_allocated(0)),
            "beam_error": beam_row["error"],
            "error": _error_payload(grammar_error),
        }


def _metric_notes_from_bridge(payload: dict[str, Any]) -> list[MetricNote]:
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
        raise ResearchError("HOMR_OUTPUT_INVALID", "homr", str(error)) from error
    if not notes:
        raise ResearchError("HOMR_OUTPUT_INVALID", "homr", "homr returned no notes")
    return notes


def _terminate_process_tree(process: subprocess.Popen[str]) -> None:
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


def _run_homr(sample: OlimpicSample, expected: list[MetricNote]) -> dict[str, Any]:
    workspace = _workspace_root()
    command = [
        sys.executable,
        str(workspace / "Bridge" / "bridge.py"),
        "--engine",
        "homr",
        sample.image,
    ]
    started = time.perf_counter()
    process = subprocess.Popen(
        command,
        cwd=workspace / "Bridge",
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    try:
        stdout, stderr = process.communicate(timeout=HOMR_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        _terminate_process_tree(process)
        stdout, stderr = process.communicate()
        return {
            "id": sample.identifier,
            "score_id": sample.score_id,
            "valid": False,
            "seconds": time.perf_counter() - started,
            "peak_vram_bytes": 0,
            "error": {
                "code": "TIMEOUT",
                "stage": "homr",
                "message": f"homr exceeded {HOMR_TIMEOUT_SECONDS} seconds",
            },
            "stderr_tail": stderr[-2000:],
        }
    elapsed = time.perf_counter() - started
    if process.returncode != 0:
        return {
            "id": sample.identifier,
            "score_id": sample.score_id,
            "valid": False,
            "seconds": elapsed,
            "peak_vram_bytes": 0,
            "error": {"code": "HOMR_FAILED", "stage": "homr", "message": stderr[-2000:]},
        }
    try:
        payload = json.loads(stdout)
        predicted = _metric_notes_from_bridge(payload)
    except (json.JSONDecodeError, ResearchError) as error:
        return {
            "id": sample.identifier,
            "score_id": sample.score_id,
            "valid": False,
            "seconds": elapsed,
            "peak_vram_bytes": 0,
            "error": _error_payload(error),
            "stdout_tail": stdout[-1000:],
            "stderr_tail": stderr[-2000:],
        }
    return {
        "id": sample.identifier,
        "score_id": sample.score_id,
        "valid": True,
        "seconds": elapsed,
        "peak_vram_bytes": 0,
        "metrics": _serialize_metrics(predicted, expected),
    }


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def _mean_metric(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [
        float(row["metrics"][key])
        for row in rows
        if row.get("valid") and row.get("metrics", {}).get(key) is not None
    ]
    values = [value for value in values if math.isfinite(value)]
    return statistics.fmean(values) if values else None


def aggregate_results(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    samples = list(rows)
    valid = [row for row in samples if row.get("valid")]
    latencies = [float(row["seconds"]) for row in samples if row.get("seconds") is not None]
    fallback_attempts = sum(bool(row.get("fallback_attempted")) for row in samples)
    return {
        "samples": len(samples),
        "valid_samples": len(valid),
        "structural_validity": len(valid) / len(samples) if samples else 0.0,
        "catastrophic_page_failure_rate": 1.0 - len(valid) / len(samples) if samples else 1.0,
        "pitch_f1": _mean_metric(samples, "pitch_f1") or 0.0,
        "onset_f1": _mean_metric(samples, "onset_f1") or 0.0,
        "onset_duration_f1": _mean_metric(samples, "onset_duration_f1") or 0.0,
        "mean_offset_error": _mean_metric(samples, "mean_offset_error"),
        "staff_accuracy": _mean_metric(samples, "staff_accuracy") or 0.0,
        "voice_accuracy": _mean_metric(samples, "aligned_voice_accuracy") or 0.0,
        "median_seconds_per_system": statistics.median(latencies) if latencies else None,
        "p95_seconds_per_system": _percentile(latencies, 0.95),
        "peak_vram_bytes": max((int(row.get("peak_vram_bytes", 0)) for row in samples), default=0),
        "beam_to_grammar_retry_rate": fallback_attempts / len(samples) if samples else 0.0,
    }


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.{os.getpid()}.tmp"
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _load_checkpoint(path: Path, sample_ids: list[str]) -> dict[str, Any]:
    if not path.is_file():
        return {
            "schema_version": CHECKPOINT_SCHEMA_VERSION,
            "decoder_state_revision": DECODER_STATE_REVISION,
            "sample_ids": sample_ids,
            "transcoda_beam_only": {},
            "transcoda_beam_then_grammar": {},
            "homr": {},
            "determinism": None,
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ResearchError("BENCHMARK_INVALID", "checkpoint", str(error)) from error
    if payload.get("schema_version") != CHECKPOINT_SCHEMA_VERSION or payload.get("sample_ids") != sample_ids:
        raise ResearchError(
            "BENCHMARK_INVALID",
            "checkpoint",
            "Checkpoint schema or sample selection does not match this run",
        )
    if payload.get("decoder_state_revision") != DECODER_STATE_REVISION:
        invalidated = {
            identifier
            for identifier, row in payload["transcoda_beam_then_grammar"].items()
            if row.get("fallback_attempted")
        }
        for identifier in invalidated:
            payload["transcoda_beam_then_grammar"].pop(identifier, None)
        determinism = payload.get("determinism")
        if determinism and determinism.get("sample_id") in invalidated:
            payload["determinism"] = None
        payload["decoder_state_revision"] = DECODER_STATE_REVISION
    return payload


def _ordered_rows(results: dict[str, Any], sample_ids: list[str]) -> list[dict[str, Any]]:
    return [results[identifier] for identifier in sample_ids if identifier in results]


def run_checkpointed_benchmark(
    samples: list[OlimpicSample],
    checkpoint_path: Path,
    *,
    progress: Any = print,
) -> dict[str, Any]:
    sample_ids = [sample.identifier for sample in samples]
    checkpoint = _load_checkpoint(checkpoint_path, sample_ids)
    by_id = {sample.identifier: sample for sample in samples}

    missing_transcoda = [
        identifier
        for identifier in sample_ids
        if identifier not in checkpoint["transcoda_beam_then_grammar"]
    ]
    runner: TranscodaRunner | None = None
    if missing_transcoda:
        runner = TranscodaRunner("beam")
        for index, identifier in enumerate(sample_ids, start=1):
            if identifier not in missing_transcoda:
                continue
            sample = by_id[identifier]
            progress(f"[TRANSCODA] {index}/{len(samples)} {identifier}")
            expected = load_ground_truth_notes(Path(sample.musicxml))
            existing_beam = checkpoint["transcoda_beam_only"].get(identifier)
            if existing_beam is not None and not existing_beam.get("valid"):
                with Image.open(sample.image) as source:
                    retry_image = source.convert("RGB")
                try:
                    beam_row = existing_beam
                    production_row = _grammar_retry(
                        runner,
                        sample,
                        expected,
                        beam_row,
                        image=retry_image,
                        page=index,
                        total=len(samples),
                    )
                finally:
                    retry_image.close()
            else:
                beam_row, production_row = _transcoda_pair(
                    runner,
                    sample,
                    expected,
                    page=index,
                    total=len(samples),
                )
            checkpoint["transcoda_beam_only"][identifier] = beam_row
            checkpoint["transcoda_beam_then_grammar"][identifier] = production_row
            _atomic_write_json(checkpoint_path, checkpoint)

    if runner is not None and checkpoint.get("determinism") is None:
        valid_ids = [
            identifier
            for identifier in sample_ids
            if checkpoint["transcoda_beam_then_grammar"][identifier].get("valid")
        ]
        if valid_ids:
            identifier = valid_ids[0]
            sample = by_id[identifier]
            expected = load_ground_truth_notes(Path(sample.musicxml))
            hashes = [checkpoint["transcoda_beam_then_grammar"][identifier]["kern_sha256"]]
            for run_number in (2, 3):
                progress(f"[DETERMINISM] run {run_number}/3 {identifier}")
                _, row = _transcoda_pair(
                    runner,
                    sample,
                    expected,
                    page=run_number,
                    total=3,
                )
                hashes.append(str(row.get("kern_sha256", "")))
            checkpoint["determinism"] = {
                "sample_id": identifier,
                "runs": 3,
                "hashes": hashes,
                "passed": len(set(hashes)) == 1 and all(hashes),
            }
        else:
            checkpoint["determinism"] = {
                "sample_id": None,
                "runs": 0,
                "hashes": [],
                "passed": False,
            }
        _atomic_write_json(checkpoint_path, checkpoint)

    for index, sample in enumerate(samples, start=1):
        if sample.identifier in checkpoint["homr"]:
            continue
        progress(f"[HOMR] {index}/{len(samples)} {sample.identifier}")
        expected = load_ground_truth_notes(Path(sample.musicxml))
        checkpoint["homr"][sample.identifier] = _run_homr(sample, expected)
        _atomic_write_json(checkpoint_path, checkpoint)

    report = {
        "schema_version": 1,
        "decoder_state_revision": DECODER_STATE_REVISION,
        "sample_count": len(samples),
        "checkpoint": str(checkpoint_path.resolve()),
        "transcoda_beam_only": {
            "summary": aggregate_results(
                _ordered_rows(checkpoint["transcoda_beam_only"], sample_ids)
            ),
            "samples": _ordered_rows(checkpoint["transcoda_beam_only"], sample_ids),
        },
        "transcoda_beam_then_grammar": {
            "summary": aggregate_results(
                _ordered_rows(checkpoint["transcoda_beam_then_grammar"], sample_ids)
            ),
            "samples": _ordered_rows(
                checkpoint["transcoda_beam_then_grammar"], sample_ids
            ),
        },
        "homr": {
            "summary": aggregate_results(_ordered_rows(checkpoint["homr"], sample_ids)),
            "samples": _ordered_rows(checkpoint["homr"], sample_ids),
        },
        "determinism": checkpoint["determinism"],
    }
    return report
