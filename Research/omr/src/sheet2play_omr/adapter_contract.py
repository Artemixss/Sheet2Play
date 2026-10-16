"""Candidate-neutral Phase-2 adapter and artifact contract."""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from .errors import ResearchError


class MeasurementPath(str, Enum):
    REFERENCE_ROUND_TRIP = "reference_round_trip"
    ANNOTATED_CROP = "annotated_crop"
    COMPLETE_DOCUMENT = "complete_document"


class RunStatus(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class AdapterConfig:
    candidate_id: str
    adapter_id: str
    adapter_revision: str
    source_repository: str
    source_revision: str
    checkpoint: str | None
    checkpoint_revision: str | None
    native_format: str
    input_granularity: str
    supported_paths: tuple[MeasurementPath, ...]
    settings: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        required = {
            "candidate_id": self.candidate_id,
            "adapter_id": self.adapter_id,
            "adapter_revision": self.adapter_revision,
            "source_repository": self.source_repository,
            "source_revision": self.source_revision,
            "native_format": self.native_format,
            "input_granularity": self.input_granularity,
        }
        missing = sorted(name for name, value in required.items() if not str(value).strip())
        if missing:
            raise ValueError(f"Adapter config fields cannot be empty: {', '.join(missing)}")
        if not self.supported_paths:
            raise ValueError("Adapter config must declare at least one measurement path")
        if (self.checkpoint is None) != (self.checkpoint_revision is None):
            raise ValueError("Checkpoint name and revision must be supplied together")

    def to_json(self) -> dict[str, Any]:
        document = asdict(self)
        document["supported_paths"] = [item.value for item in self.supported_paths]
        document["settings"] = dict(self.settings)
        return document

    @property
    def sha256(self) -> str:
        payload = json.dumps(
            self.to_json(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class AdapterInput:
    item_id: str
    composition_group: str
    input_path: Path
    input_sha256: str
    measurement_path: MeasurementPath
    reference_path: Path | None = None
    reference_sha256: str | None = None

    def validate(self) -> None:
        if not self.item_id.strip() or not self.composition_group.strip():
            raise ResearchError(
                "ADAPTER_INPUT_INVALID", "input_validation", "Item identity is incomplete"
            )
        if not self.input_path.is_file():
            raise ResearchError(
                "ADAPTER_INPUT_INVALID",
                "input_validation",
                f"Input is missing: {self.input_path}",
            )
        actual = sha256_file(self.input_path)
        if actual != self.input_sha256:
            raise ResearchError(
                "ADAPTER_INPUT_INVALID",
                "input_validation",
                f"Input hash mismatch for {self.item_id}: {actual}",
            )
        if (self.reference_path is None) != (self.reference_sha256 is None):
            raise ResearchError(
                "ADAPTER_INPUT_INVALID",
                "input_validation",
                "Reference path and hash must be supplied together",
            )
        if self.reference_path is not None:
            if not self.reference_path.is_file():
                raise ResearchError(
                    "ADAPTER_INPUT_INVALID",
                    "input_validation",
                    f"Reference is missing: {self.reference_path}",
                )
            if sha256_file(self.reference_path) != self.reference_sha256:
                raise ResearchError(
                    "ADAPTER_INPUT_INVALID",
                    "input_validation",
                    f"Reference hash mismatch for {self.item_id}",
                )


@dataclass(frozen=True, slots=True)
class Artifact:
    role: str
    path: str
    sha256: str
    bytes: int
    media_type: str

    @classmethod
    def from_path(cls, role: str, path: Path, media_type: str) -> "Artifact":
        if not path.is_file():
            raise ResearchError(
                "ADAPTER_ARTIFACT_MISSING", "artifact_validation", f"Missing {role}: {path}"
            )
        size = path.stat().st_size
        if size <= 0:
            raise ResearchError(
                "ADAPTER_ARTIFACT_INVALID", "artifact_validation", f"Empty {role}: {path}"
            )
        return cls(role, portable_path(path), sha256_file(path), size, media_type)


@dataclass(frozen=True, slots=True)
class StageTiming:
    stage: str
    seconds: float

    def __post_init__(self) -> None:
        if not self.stage.strip() or self.seconds < 0:
            raise ValueError("Stage timings require a name and a non-negative duration")


@dataclass(frozen=True, slots=True)
class ResourceMeasurements:
    peak_ram_bytes: int | None
    peak_vram_bytes: int | None
    sample_interval_seconds: float | None
    cold_start: bool
    measurement_notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for value in (self.peak_ram_bytes, self.peak_vram_bytes):
            if value is not None and value < 0:
                raise ValueError("Resource measurements cannot be negative")


@dataclass(frozen=True, slots=True)
class AdapterResult:
    schema_version: int
    candidate_id: str
    adapter_id: str
    adapter_config_sha256: str
    item_id: str
    composition_group: str
    measurement_path: MeasurementPath
    status: RunStatus
    exit_status: int | None
    warnings: tuple[str, ...]
    timings: tuple[StageTiming, ...]
    resources: ResourceMeasurements
    artifacts: tuple[Artifact, ...]
    provenance: Mapping[str, Any]
    error: Mapping[str, Any] | None = None

    def validate(self) -> None:
        if self.schema_version != 1:
            raise ValueError(f"Unsupported adapter-result schema: {self.schema_version}")
        if self.status is RunStatus.SUCCEEDED:
            if self.exit_status != 0:
                raise ValueError("A successful adapter result must have exit status zero")
            roles = {artifact.role for artifact in self.artifacts}
            required = {"native", "musicxml", "canonical_events"}
            if not required <= roles:
                raise ValueError(
                    "Successful adapter result is missing artifacts: "
                    + ", ".join(sorted(required - roles))
                )
            if not self.timings:
                raise ValueError("Successful adapter result requires stage timings")
        elif self.error is None:
            raise ValueError("Failed and unavailable adapter results require a typed error")
        required_provenance = {
            "adapter_config",
            "input_sha256",
            "platform",
            "python",
            "source_revision",
        }
        missing = required_provenance - set(self.provenance)
        if missing:
            raise ValueError("Adapter provenance is incomplete: " + ", ".join(sorted(missing)))

    def to_json(self) -> dict[str, Any]:
        self.validate()
        return {
            "schema_version": self.schema_version,
            "candidate_id": self.candidate_id,
            "adapter_id": self.adapter_id,
            "adapter_config_sha256": self.adapter_config_sha256,
            "item_id": self.item_id,
            "composition_group": self.composition_group,
            "measurement_path": self.measurement_path.value,
            "status": self.status.value,
            "exit_status": self.exit_status,
            "warnings": list(self.warnings),
            "timings": [asdict(item) for item in self.timings],
            "resources": asdict(self.resources),
            "artifacts": [asdict(item) for item in self.artifacts],
            "provenance": dict(self.provenance),
            "error": None if self.error is None else dict(self.error),
        }


class CandidateAdapter(Protocol):
    config: AdapterConfig

    def probe(self) -> Mapping[str, Any]: ...

    def run(self, item: AdapterInput, output_directory: Path) -> AdapterResult: ...


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def workspace_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "Bridge" / "bridge.py").is_file():
            return candidate
    raise RuntimeError("Cannot locate the Sheet2Play workspace")


def portable_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(workspace_root()).as_posix()
    except ValueError:
        return f"<external>/{resolved.name}"


def base_provenance(config: AdapterConfig, item: AdapterInput) -> dict[str, Any]:
    return {
        "adapter_config": config.to_json(),
        "adapter_config_sha256": config.sha256,
        "input_path": portable_path(item.input_path),
        "input_sha256": item.input_sha256,
        "platform": platform.platform(),
        "python": sys.version,
        "source_repository": config.source_repository,
        "source_revision": config.source_revision,
        "checkpoint": config.checkpoint,
        "checkpoint_revision": config.checkpoint_revision,
    }


def unavailable_result(
    config: AdapterConfig,
    item: AdapterInput,
    *,
    code: str,
    message: str,
    probe: Mapping[str, Any],
) -> AdapterResult:
    result = AdapterResult(
        schema_version=1,
        candidate_id=config.candidate_id,
        adapter_id=config.adapter_id,
        adapter_config_sha256=config.sha256,
        item_id=item.item_id,
        composition_group=item.composition_group,
        measurement_path=item.measurement_path,
        status=RunStatus.UNAVAILABLE,
        exit_status=None,
        warnings=(),
        timings=(),
        resources=ResourceMeasurements(None, None, None, True, ("runtime unavailable",)),
        artifacts=(),
        provenance={**base_provenance(config, item), "probe": dict(probe)},
        error={"code": code, "stage": "availability", "message": message},
    )
    result.validate()
    return result


def write_result(path: Path, result: AdapterResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(result.to_json(), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def require_supported(config: AdapterConfig, item: AdapterInput) -> None:
    item.validate()
    if item.measurement_path not in config.supported_paths:
        raise ResearchError(
            "MEASUREMENT_PATH_UNSUPPORTED",
            "input_validation",
            f"{config.adapter_id} does not support {item.measurement_path.value}",
        )


def artifact_roles(artifacts: Sequence[Artifact]) -> set[str]:
    return {item.role for item in artifacts}
