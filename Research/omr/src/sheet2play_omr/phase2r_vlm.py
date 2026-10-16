"""Development adapters for system-level Qwen3-VL music transcription."""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from PIL import Image

from .adapter_contract import (
    AdapterConfig, AdapterInput, AdapterResult, Artifact, MeasurementPath,
    ResourceMeasurements, RunStatus, StageTiming, base_provenance,
    portable_path, require_supported, sha256_file,
)
from .errors import ResearchError
from .phase2_adapters import _canonicalize, run_monitored
from .phase2r_identity import (
    EXPECTED_CROMA_SHA256, EXPECTED_CUDA_DLL_SHA256,
    EXPECTED_GGUF_SHA256, EXPECTED_LLAMA_CLI_SHA256,
)
from .phase2r_validation import record_attempt_measurement, require_complete_systems


ROKOT_PROMPT = "Transcribe this sheet music to rokot-ABC."
QWEN_PROMPT = (
    "Transcribe only the notation visible in this single system into one ABC 2.1 tune. "
    "Start with X:1, then M:, L:, K:, and V: lines for each staff or independent voice. "
    "Preserve pitches, durations, rests, ties, tuplets, key and meter changes. "
    "End with a closing barline. Output ABC only: no LilyPond, prose, Markdown, "
    "or repeated staff metadata."
)
HERE = Path(__file__).resolve().parent
ADAPTER_REVISION = sha256_file(Path(__file__))


def _local_name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _children(parent: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in parent if _local_name(child) == name]


def _part_labels(root: ET.Element) -> tuple[str, ...]:
    lists = _children(root, "part-list")
    if len(lists) != 1:
        raise ResearchError("STITCH_INVALID", "stitching", "Expected one MusicXML part list")
    labels = []
    for score_part in _children(lists[0], "score-part"):
        names = _children(score_part, "part-name")
        labels.append((names[0].text or "").strip() if names else "")
    if not labels or any(not label for label in labels):
        raise ResearchError("STITCH_INVALID", "stitching", "Part labels are missing")
    return tuple(labels)


def extract_abc(raw: str) -> str:
    lines = raw.replace("\r\n", "\n").splitlines()
    starts = [index for index, line in enumerate(lines) if re.match(r"^X:\s*\d+\s*$", line)]
    if len(starts) != 1:
        raise ResearchError("INVALID_NOTATION", "recognition", "Expected one ABC X: header")
    text = "\n".join(lines[starts[0]:]).strip()
    if not re.search(r"(?m)^K:\s*\S", text):
        raise ResearchError("INVALID_NOTATION", "recognition", "ABC key header is missing")
    if not re.search(r"(?m)^M:\s*\S", text):
        raise ResearchError("INVALID_NOTATION", "recognition", "ABC meter header is missing")
    if "|" not in text:
        raise ResearchError("INVALID_NOTATION", "recognition", "ABC has no barline")
    if not re.search(r"(?:\|\]?|:\|)\s*$", text):
        raise ResearchError("TRUNCATED_GENERATION", "recognition", "ABC ends before a closing barline")
    return text + "\n"


@dataclass(frozen=True, slots=True)
class AbcSystem:
    reference: str
    meter: str
    unit: str
    key: str
    voices: tuple[tuple[str, str], ...]
    bodies: Mapping[str, str]
    ending_state: tuple[str, str, str]


def _ending_field(body: str, field: str, initial: str) -> str:
    values = re.findall(r"\[" + field + r":\s*([^\]]+)\]", body)
    return values[-1].strip() if values else initial


def _parse_abc_system(abc: str) -> AbcSystem:
    fields: dict[str, str] = {}
    declarations: dict[str, str] = {}
    bodies: dict[str, list[str]] = {}
    body_started = False
    active_voice: str | None = None
    for line in abc.splitlines():
        line = line.strip()
        if not line:
            continue
        field = re.fullmatch(r"([A-Za-z]):\s*(.*)", line)
        if field:
            name, value = field.groups()
            if name == "V":
                parts = value.split(maxsplit=1)
                if not parts:
                    raise ResearchError("INVALID_NOTATION", "stitching", "Empty ABC voice declaration")
                voice_id = parts[0]
                attributes = parts[1].strip() if len(parts) == 2 else ""
                if voice_id in declarations and attributes and declarations[voice_id] != attributes:
                    raise ResearchError("STITCH_INVALID", "stitching", "Voice declaration changed within a system")
                declarations.setdefault(voice_id, attributes)
                if body_started:
                    active_voice = voice_id
                continue
            if not body_started and name in ("X", "M", "L", "K"):
                if name in fields:
                    raise ResearchError("INVALID_NOTATION", "stitching", f"Duplicate ABC {name}: header")
                fields[name] = value.strip()
                continue
            if not body_started and name in ("T", "C", "Q"):
                continue
            raise ResearchError("STITCH_INVALID", "stitching", f"Unsupported ABC field {name}: in system body")
        if line.startswith("%"):
            raise ResearchError("STITCH_INVALID", "stitching", "ABC directives cannot be merged safely")
        marker = re.match(r"^\[V:([^\]\s]+)\]\s*(.*)$", line)
        if marker:
            active_voice = marker.group(1)
            if active_voice not in declarations:
                raise ResearchError("STITCH_INVALID", "stitching", "Music references an undeclared voice")
            line = marker.group(2)
        elif active_voice is None:
            if len(declarations) > 1:
                raise ResearchError("STITCH_INVALID", "stitching", "Unlabeled music with multiple voices")
            active_voice = next(iter(declarations), "")
        if line:
            body_started = True
            bodies.setdefault(active_voice, []).append(line)
    if any(not fields.get(name) for name in ("X", "M", "L", "K")):
        raise ResearchError("INVALID_NOTATION", "stitching", "ABC header is incomplete")
    voice_ids = tuple(declarations) if declarations else ("",)
    if set(bodies) != set(voice_ids):
        raise ResearchError("STITCH_INVALID", "stitching", "One or more declared voices have no music")
    joined = {voice: " ".join(bodies[voice]) for voice in voice_ids}
    if any(not re.search(r"(?:\|\]?|:\|)\s*$", value) for value in joined.values()):
        raise ResearchError("TRUNCATED_GENERATION", "stitching", "A voice ends without a barline")
    states = {
        (
            _ending_field(body, "M", fields["M"]),
            _ending_field(body, "L", fields["L"]),
            _ending_field(body, "K", fields["K"]),
        )
        for body in joined.values()
    }
    if len(states) != 1:
        raise ResearchError("STITCH_INVALID", "stitching", "Voices disagree on ending meter, unit, or key")
    return AbcSystem(
        fields["X"], fields["M"], fields["L"], fields["K"],
        tuple(declarations.items()), joined, states.pop(),
    )


def merge_system_abc(systems: list[str]) -> str:
    if not systems:
        raise ResearchError("MISSING_SYSTEM", "stitching", "No ABC systems were generated")
    if len(systems) == 1:
        return extract_abc(systems[0])
    parsed = [_parse_abc_system(extract_abc(source)) for source in systems]
    first = parsed[0]
    voice_order = tuple(voice for voice, _ in first.voices) if first.voices else ("",)
    for system in parsed[1:]:
        if dict(system.voices) != dict(first.voices) or set(system.bodies) != set(voice_order):
            raise ResearchError("STITCH_INVALID", "stitching", "Voice identities or clefs changed between systems")
    merged: list[str] = [f"X:{first.reference}", f"M:{first.meter}", f"L:{first.unit}", f"K:{first.key}"]
    merged.extend(f"V:{voice} {attributes}".rstrip() for voice, attributes in first.voices)
    for voice in voice_order:
        segments: list[str] = []
        previous_state: tuple[str, str, str] | None = None
        for index, system in enumerate(parsed):
            current_state = (system.meter, system.unit, system.key)
            changes = " ".join(
                f"[{name}:{value}]" for name, value, previous in zip(
                    ("M", "L", "K"), current_state, previous_state or current_state, strict=True
                ) if value != previous
            )
            body = system.bodies[voice]
            if index < len(parsed) - 1:
                body = re.sub(r"\|\]\s*$", "|", body)
            segments.append(" ".join(value for value in (changes, body) if value))
            previous_state = system.ending_state
        merged.append((f"[V:{voice}] " if voice else "") + " ".join(segments))
    return "\n".join(merged) + "\n"


def convert_abc(abc: str, destination: Path, converter_executable: Path) -> None:
    if not converter_executable.is_file():
        raise ResearchError("ABC_CONVERTER_MISSING", "native_to_musicxml", "Pinned croma converter is missing")
    source = destination.with_suffix(".abc")
    source.write_text(abc, encoding="utf-8")
    try:
        completed = subprocess.run(
            [str(converter_executable), "xml", "--strict", "--warnings-as-errors", str(source), "--output", str(destination)],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ResearchError("ABC_CONVERSION_FAILED", "native_to_musicxml", str(error)) from error
    if completed.returncode != 0:
        codes = sorted(set(re.findall(r"(?:warning|error)\[([^]]+)\]", completed.stderr)))
        raise ResearchError(
            "ABC_CONVERSION_FAILED", "native_to_musicxml",
            f"croma exited {completed.returncode}; diagnostic codes: {', '.join(codes) or 'none'}; "
            + (completed.stderr or completed.stdout or "no diagnostic")[-600:],
        )
    if not destination.is_file() or destination.stat().st_size == 0:
        raise ResearchError("ABC_CONVERSION_FAILED", "native_to_musicxml", "MusicXML is empty")
    from music21 import converter

    try:
        score = converter.parse(str(destination), forceSource=True)
    except Exception as error:
        raise ResearchError("ABC_CONVERSION_FAILED", "native_to_musicxml", str(error)) from error
    if not list(score.recurse().notes):
        raise ResearchError("ABC_CONVERSION_FAILED", "native_to_musicxml", "MusicXML has no notes")


def stitch_musicxml(systems: list[Path], destination: Path) -> None:
    if not systems:
        raise ResearchError("MISSING_SYSTEM", "stitching", "No systems were converted")
    trees = [ET.parse(path) for path in systems]
    root = trees[0].getroot()
    target_parts = _children(root, "part")
    if not target_parts:
        raise ResearchError("STITCH_INVALID", "stitching", "MusicXML contains no parts")
    labels = _part_labels(root)
    if len(labels) != len(target_parts):
        raise ResearchError("STITCH_INVALID", "stitching", "Part list and score parts disagree")
    for tree in trees[1:]:
        source_root = tree.getroot()
        source_parts = _children(source_root, "part")
        if len(source_parts) != len(target_parts):
            raise ResearchError("STITCH_INVALID", "stitching", "Part count changed between systems")
        if _part_labels(source_root) != labels:
            raise ResearchError("STITCH_INVALID", "stitching", "Part labels or order changed between systems")
        for target, source in zip(target_parts, source_parts, strict=True):
            for measure in _children(source, "measure"):
                target.append(measure)
    for part in target_parts:
        measures = _children(part, "measure")
        if not measures:
            raise ResearchError("STITCH_INVALID", "stitching", "A stitched part has no measures")
        for index, measure in enumerate(measures, start=1):
            measure.set("number", str(index))
    destination.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(destination, encoding="utf-8", xml_declaration=True)


def crop_detected_systems(
    image: Path, detection: Mapping[str, Any], output: Path,
    *, source_sha256: str,
) -> list[Path]:
    if detection.get("coordinate_space") != "homr_predictions_preprocessed":
        raise ResearchError("DETECTOR_INVALID", "segmentation", "Unknown detector coordinate space")
    source = detection.get("source_image")
    metadata = detection.get("detector_image")
    boxes = detection.get("systems")
    if not isinstance(source, dict) or source.get("sha256") != source_sha256:
        raise ResearchError("DETECTOR_INVALID", "segmentation", "Detector source image hash mismatch")
    if not isinstance(metadata, dict) or not isinstance(boxes, list):
        raise ResearchError("DETECTOR_INVALID", "segmentation", "Detector metadata or systems are invalid")
    if not image.is_file() or sha256_file(image) != metadata.get("sha256"):
        raise ResearchError("DETECTOR_INVALID", "segmentation", "Detector image hash mismatch")
    output.mkdir(parents=True, exist_ok=True)
    crops: list[Path] = []
    crop_records: list[dict[str, Any]] = []
    with Image.open(image) as page:
        if page.width != metadata.get("width") or page.height != metadata.get("height"):
            raise ResearchError("DETECTOR_INVALID", "segmentation", "Detector image dimensions mismatch")
        for index, box in enumerate(boxes, start=1):
            try:
                min_y = float(box["min_y"])
                max_y = float(box["max_y"])
            except (KeyError, TypeError, ValueError) as error:
                raise ResearchError("DETECTOR_INVALID", "segmentation", f"Invalid system box {index}") from error
            if not math.isfinite(min_y) or not math.isfinite(max_y) or max_y <= min_y:
                raise ResearchError("DETECTOR_INVALID", "segmentation", f"Invalid system box {index}")
            top = max(0, math.floor(min_y))
            bottom = min(page.height, math.ceil(max_y))
            if bottom <= top:
                raise ResearchError("DETECTOR_INVALID", "segmentation", f"Invalid system box {index}")
            destination = output / f"system-{index:04d}.png"
            page.crop((0, top, page.width, bottom)).save(destination)
            crops.append(destination)
            crop_records.append({"system": index, "top": top, "bottom": bottom,
                                 "width": page.width, "height": bottom - top,
                                 "sha256": sha256_file(destination)})
    if not crops:
        raise ResearchError("DETECTOR_INVALID", "segmentation", "No systems detected")
    (output / "crop-manifest.json").write_text(json.dumps({
        "coordinate_space": detection["coordinate_space"],
        "source_image": source,
        "detector_image": metadata,
        "crops": crop_records,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return crops


def _max_or_none(values: list[int | None]) -> int | None:
    present = [value for value in values if value is not None]
    return max(present) if present else None


class QwenVlAbcAdapter:
    def __init__(self, workspace: Path, *, rokot: bool) -> None:
        self.workspace = workspace.resolve()
        self.rokot = rokot
        self.runtime = self.workspace / "Research" / "omr" / ".runtime" / "phase2r"
        self.cli = self.runtime / "llama-b11124" / "llama-mtmd-cli.exe"
        self.cuda_libraries = tuple(self.cli.parent / name for name in EXPECTED_CUDA_DLL_SHA256)
        self.converter = self.runtime / "croma" / "croma-windows-x86_64.exe"
        model_dir = self.runtime / ("rokot" if rokot else "qwen")
        self.model = model_dir / (
            "rokot-omr-2b-Q8_0.gguf" if rokot else "Qwen3VL-2B-Instruct-Q8_0.gguf"
        )
        self.projector = model_dir / (
            "mmproj-rokot-omr-2b-f16.gguf" if rokot
            else "mmproj-Qwen3VL-2B-Instruct-Q8_0.gguf"
        )
        self.detector_python = self.workspace / "Bridge" / ".venv-homr-gpu" / "Scripts" / "python.exe"
        self.detector = self.workspace / "Research" / "omr" / "src" / "sheet2play_omr" / "phase2r_detector.py"
        self.prompt = ROKOT_PROMPT if rokot else QWEN_PROMPT
        self.config = AdapterConfig(
            candidate_id="rokot" if rokot else "qwen3_vl_2b_instruct",
            adapter_id="rokot_q8_system_and_page" if rokot else "qwen_q8_system_and_page",
            adapter_revision=ADAPTER_REVISION,
            source_repository=(
                "https://huggingface.co/rokotmidi/rokot-omr-2b" if rokot
                else "https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct-GGUF"
            ),
            source_revision=(
                "7add305aade6fb3a64ad4dde77d410fa68381089" if rokot
                else "52d6c8ffea26cc873ac5ad116f8631268d7eb503"
            ),
            checkpoint=self.model.name,
            checkpoint_revision=(
                "7add305aade6fb3a64ad4dde77d410fa68381089" if rokot
                else "52d6c8ffea26cc873ac5ad116f8631268d7eb503"
            ),
            native_format="ABC",
            input_granularity="detected system",
            supported_paths=(MeasurementPath.ANNOTATED_CROP, MeasurementPath.COMPLETE_DOCUMENT),
            settings={
                "prompt": self.prompt,
                "max_new_tokens": 1600,
                "temperature": 0,
                "seed": 0,
                "image_min_tokens": 1024,
                "precision": "Q8_0 text; f16 projector" if rokot else "Q8_0 text and projector",
                "segmentation": "HOMR detector boxes on exact returned preprocessed image; full-width vertical-margin crops",
                "detector_sha256": sha256_file(self.detector),
                "converter": "croma 1.2.1 strict ABC to MusicXML",
                "converter_sha256": sha256_file(self.converter) if self.converter.is_file() else None,
                "model_sha256": sha256_file(self.model) if self.model.is_file() else None,
                "projector_sha256": sha256_file(self.projector) if self.projector.is_file() else None,
                "cli_sha256": sha256_file(self.cli) if self.cli.is_file() else None,
                "cuda_runtime_sha256": {
                    path.name: sha256_file(path) if path.is_file() else None
                    for path in self.cuda_libraries
                },
            },
        )

    def probe(self) -> Mapping[str, Any]:
        required = (
            self.cli, self.model, self.projector, self.detector,
            self.detector_python, self.converter, *self.cuda_libraries,
        )
        missing = [portable_path(path) for path in required if not path.is_file()]
        expected = {
            self.cli: EXPECTED_LLAMA_CLI_SHA256,
            self.model: EXPECTED_GGUF_SHA256[self.model.name],
            self.projector: EXPECTED_GGUF_SHA256[self.projector.name],
            self.converter: EXPECTED_CROMA_SHA256,
            **{path: EXPECTED_CUDA_DLL_SHA256[path.name] for path in self.cuda_libraries},
        }
        mismatches = [portable_path(path) for path, digest in expected.items()
                      if path.is_file() and sha256_file(path) != digest]
        device_output = ""
        if self.cli.is_file() and not missing and not mismatches:
            try:
                device = subprocess.run(
                    [str(self.cli), "--list-devices"], check=False, capture_output=True,
                    text=True, timeout=30, encoding="utf-8", errors="replace",
                )
                device_output = (device.stdout + device.stderr).strip()[:500]
                cuda_available = device.returncode == 0 and "CUDA0:" in device_output
            except (OSError, subprocess.TimeoutExpired) as error:
                device_output = type(error).__name__
                cuda_available = False
        else:
            cuda_available = False
        return {
            "available": not missing and not mismatches and cuda_available,
            "missing": missing,
            "hash_mismatches": mismatches,
            "cuda_available": cuda_available,
            "device_output": device_output,
            "model_sha256": self.config.settings["model_sha256"],
            "projector_sha256": self.config.settings["projector_sha256"],
            "cli_sha256": self.config.settings["cli_sha256"],
        }

    def _system_images(self, item: AdapterInput, output: Path) -> tuple[list[Path], float]:
        if item.measurement_path is MeasurementPath.ANNOTATED_CROP:
            return [item.input_path], 0.0
        started = time.perf_counter()
        boxes_path = output / "detected-systems.json"
        detector_image = output / "detector-preprocessed.png"
        command = [str(self.detector_python), str(self.detector), str(item.input_path),
                   str(boxes_path), str(detector_image), str(self.workspace / "Bridge")]
        detection = run_monitored(command, cwd=self.workspace, timeout_seconds=300)
        record_attempt_measurement(output, stage="segmentation", seconds=detection.seconds,
                                   peak_ram_bytes=detection.peak_ram_bytes,
                                   peak_vram_bytes=detection.peak_vram_bytes,
                                   vram_measurement=detection.vram_measurement)
        if detection.exit_status != 0 or not boxes_path.is_file():
            raise ResearchError("DETECTOR_FAILED", "segmentation", detection.stderr[-2000:])
        document = json.loads(boxes_path.read_text(encoding="utf-8"))
        return crop_detected_systems(detector_image, document, output / "crops",
                                     source_sha256=item.input_sha256), time.perf_counter() - started

    def run(self, item: AdapterInput, output_directory: Path) -> AdapterResult:
        require_supported(self.config, item)
        probe = self.probe()
        if not probe["available"]:
            from .adapter_contract import unavailable_result
            return unavailable_result(
                self.config, item, code="VLM_RUNTIME_MISSING",
                message="Pinned llama.cpp runtime, model, projector, converter, or detector is missing or mismatched",
                probe=probe,
            )
        output_directory.mkdir(parents=True, exist_ok=True)
        images, segmentation_seconds = self._system_images(item, output_directory)
        native_systems: list[str] = []
        observed: list[int] = []
        processes = []
        for index, image in enumerate(images, start=1):
            command = [
                str(self.cli), "--model", str(self.model), "--mmproj", str(self.projector),
                "--image", str(image), "--prompt", self.prompt,
                "--temp", "0", "--seed", "0", "--image-min-tokens", "1024",
                "--n-predict", "1600",
                "--no-warmup", "--gpu-layers", "99",
            ]
            process = run_monitored(command, cwd=self.runtime, timeout_seconds=1800)
            processes.append(process)
            record_attempt_measurement(output_directory, stage=f"recognition_system_{index}",
                                       seconds=process.seconds, peak_ram_bytes=process.peak_ram_bytes,
                                       peak_vram_bytes=process.peak_vram_bytes,
                                       vram_measurement=process.vram_measurement)
            raw = output_directory / f"system-{index:04d}.raw.txt"
            raw.write_text(process.stdout + "\n" + process.stderr, encoding="utf-8")
            if process.exit_status != 0:
                raise ResearchError(
                    "GENERATION_TIMEOUT" if process.timed_out else "GENERATION_FAILED",
                    "recognition", f"System {index} exited {process.exit_status}: {process.stderr[-1000:]}",
                )
            abc = extract_abc(process.stdout)
            native = output_directory / f"system-{index:04d}.abc"
            native.write_text(abc, encoding="utf-8")
            native_systems.append(abc)
            observed.append(index)
        require_complete_systems(range(1, len(images) + 1), observed)
        started = time.perf_counter()
        merged_native = output_directory / "score.abc"
        try:
            merged_native.write_text(merge_system_abc(native_systems), encoding="utf-8")
            stitched = output_directory / "score.musicxml"
            convert_abc(merged_native.read_text(encoding="utf-8"), stitched, self.converter)
        finally:
            conversion_seconds = time.perf_counter() - started
            record_attempt_measurement(output_directory, stage="native_to_musicxml_and_stitching",
                                       seconds=conversion_seconds)
        started = time.perf_counter()
        try:
            canonical, warnings, normalization_seconds = _canonicalize(
                stitched, output_directory / "canonical-events.json"
            )
        finally:
            record_attempt_measurement(output_directory, stage="shared_normalization",
                                       seconds=time.perf_counter() - started)
        native_manifest = output_directory / "native-systems.json"
        native_manifest.write_text(
            json.dumps(
                [{"system": index, "image_sha256": sha256_file(image),
                  "abc_sha256": sha256_file(output_directory / f"system-{index:04d}.abc")}
                 for index, image in enumerate(images, start=1)],
                indent=2, sort_keys=True,
            ) + "\n", encoding="utf-8",
        )
        artifacts = (
            Artifact.from_path("native", native_manifest, "application/json"),
            Artifact.from_path("merged_abc", merged_native, "text/plain"),
            Artifact.from_path("musicxml", stitched, "application/vnd.recordare.musicxml+xml"),
            canonical,
            Artifact.from_path("attempt_measurements", output_directory / "attempt-measurements.json", "application/json"),
            *( (Artifact.from_path("detector_image", output_directory / "detector-preprocessed.png", "image/png"),
                Artifact.from_path("detector_boxes", output_directory / "detected-systems.json", "application/json"),
                Artifact.from_path("crop_manifest", output_directory / "crops" / "crop-manifest.json", "application/json"))
               if item.measurement_path is MeasurementPath.COMPLETE_DOCUMENT else () ),
            *(Artifact.from_path(f"system_{index}_abc", output_directory / f"system-{index:04d}.abc", "text/plain")
              for index in range(1, len(images) + 1)),
            *(Artifact.from_path(f"system_{index}_raw", output_directory / f"system-{index:04d}.raw.txt", "text/plain")
              for index in range(1, len(images) + 1)),
        )
        result = AdapterResult(
            schema_version=1,
            candidate_id=self.config.candidate_id,
            adapter_id=self.config.adapter_id,
            adapter_config_sha256=self.config.sha256,
            item_id=item.item_id,
            composition_group=item.composition_group,
            measurement_path=item.measurement_path,
            status=RunStatus.SUCCEEDED,
            exit_status=0,
            warnings=warnings,
            timings=(
                StageTiming("segmentation", segmentation_seconds),
                StageTiming("recognition", sum(process.seconds for process in processes)),
                StageTiming("native_to_musicxml_and_stitching", conversion_seconds),
                StageTiming("shared_normalization", normalization_seconds),
            ),
            resources=ResourceMeasurements(
                _max_or_none([process.peak_ram_bytes for process in processes]),
                _max_or_none([process.peak_vram_bytes for process in processes]),
                0.2, True,
                tuple(sorted({process.vram_measurement for process in processes})),
            ),
            artifacts=artifacts,
            provenance={
                **base_provenance(self.config, item),
                "system_count": len(images),
                "joining_strategy": "validated voice/state ABC merge before strict MusicXML conversion",
                "runtime": portable_path(self.cli),
                "converter_version": "croma 1.2.1",
                "device_probe": probe["device_output"],
            },
        )
        result.validate()
        return result
