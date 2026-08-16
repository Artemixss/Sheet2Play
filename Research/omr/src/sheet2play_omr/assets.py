from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ResearchError


_GIT_SHA1 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_EXECUTABLE_ASSET_SUFFIXES = {".bin", ".json", ".onnx", ".pt", ".pth", ".py", ".safetensors"}


@dataclass(frozen=True, slots=True)
class RuntimePaths:
    project_root: Path
    runtime_root: Path
    source: Path
    model: Path
    base_model: Path
    hf_cache: Path
    lock_file: Path

    @classmethod
    def discover(cls, project_root: Path | None = None) -> "RuntimePaths":
        root = (project_root or Path(__file__).resolve().parents[2]).resolve()
        runtime = root / ".runtime"
        return cls(
            project_root=root,
            runtime_root=runtime,
            source=runtime / "transcoda",
            model=runtime / "model",
            base_model=runtime / "base-model",
            hf_cache=runtime / "hf-cache",
            lock_file=root / "assets.lock.json",
        )


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def load_asset_lock(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ResearchError("ASSET_LOCK_INVALID", "runtime", f"Cannot read {path}: {error}") from error
    if payload.get("schema_version") != 1:
        raise ResearchError("ASSET_LOCK_INVALID", "runtime", "Unsupported asset lock schema")
    _validate_asset_lock(payload)
    return payload


def _validate_asset_lock(payload: dict[str, Any]) -> None:
    try:
        source = payload["source"]
        if source["revision_algorithm"] != "git-sha1":
            raise ValueError("source revision_algorithm must be git-sha1")
        if not _GIT_SHA1.fullmatch(str(source["revision"]).lower()):
            raise ValueError("source revision must be a full 40-character Git SHA-1")
        if not str(source["repository"]).startswith("https://github.com/"):
            raise ValueError("source repository must be an HTTPS GitHub URL")
        if source["require_clean_checkout"] is not True:
            raise ValueError("source must require a clean checkout")

        for section_name in ("model", "base_model"):
            section = payload[section_name]
            if not _GIT_SHA1.fullmatch(str(section["revision"]).lower()):
                raise ValueError(f"{section_name} revision must be a full 40-character snapshot hash")
            required_files = section["required_files"]
            if not isinstance(required_files, dict) or not required_files:
                raise ValueError(f"{section_name} required_files must be a nonempty object")
            for relative_name, expected in required_files.items():
                relative_path = Path(relative_name)
                if relative_path.is_absolute() or ".." in relative_path.parts:
                    raise ValueError(f"unsafe locked path in {section_name}: {relative_name}")
                if not _SHA256.fullmatch(str(expected["sha256"]).lower()):
                    raise ValueError(f"invalid SHA-256 for {section_name}/{relative_name}")
                if int(expected["size"]) <= 0:
                    raise ValueError(f"invalid size for {section_name}/{relative_name}")
    except (KeyError, TypeError, ValueError) as error:
        raise ResearchError("ASSET_LOCK_INVALID", "runtime", f"Invalid asset lock: {error}") from error


def _verify_file(root: Path, relative_name: str, expected: dict[str, Any]) -> None:
    candidate = (root / relative_name).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as error:
        raise ResearchError("ASSET_INVALID", "runtime", f"Unsafe locked asset path: {relative_name}") from error
    if not candidate.is_file():
        raise ResearchError("ASSET_MISSING", "runtime", f"Required asset is missing: {candidate}")
    expected_size = int(expected["size"])
    if candidate.stat().st_size != expected_size:
        raise ResearchError(
            "ASSET_INVALID",
            "runtime",
            f"Size mismatch for {candidate.name}: expected {expected_size}, got {candidate.stat().st_size}",
        )
    actual_hash = sha256_file(candidate)
    expected_hash = str(expected["sha256"]).lower()
    if actual_hash != expected_hash:
        raise ResearchError(
            "ASSET_INVALID",
            "runtime",
            f"SHA-256 mismatch for {candidate.name}: expected {expected_hash}, got {actual_hash}",
        )


def _run_git(source: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(source), *arguments],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise ResearchError("SOURCE_INVALID", "runtime", f"Cannot inspect Transcoda source: {error}") from error
    return result.stdout.strip()


def _verify_source(source: Path, expected: dict[str, Any]) -> str:
    expected_revision = str(expected["revision"]).lower()
    source_revision = _run_git(source, "rev-parse", "--verify", "HEAD^{commit}").lower()
    if source_revision != expected_revision:
        raise ResearchError(
            "SOURCE_INVALID",
            "runtime",
            f"Transcoda revision mismatch: expected {expected_revision}, got {source_revision}",
        )

    actual_remote = _run_git(source, "remote", "get-url", "origin")
    expected_remote = str(expected["repository"])
    if actual_remote != expected_remote:
        raise ResearchError(
            "SOURCE_INVALID",
            "runtime",
            f"Transcoda remote mismatch: expected {expected_remote}, got {actual_remote}",
        )

    tracked_changes = _run_git(source, "status", "--porcelain", "--untracked-files=no")
    if tracked_changes:
        raise ResearchError("SOURCE_INVALID", "runtime", "Transcoda checkout contains tracked modifications")

    untracked = _run_git(source, "ls-files", "--others", "--exclude-standard").splitlines()
    unsafe_untracked = [
        name for name in untracked if Path(name).suffix.lower() in _EXECUTABLE_ASSET_SUFFIXES or name.endswith(".gbnf")
    ]
    if unsafe_untracked:
        raise ResearchError(
            "SOURCE_INVALID",
            "runtime",
            f"Transcoda checkout contains unlocked executable files: {', '.join(unsafe_untracked[:5])}",
        )

    _run_git(source, "fsck", "--no-progress", "--connectivity-only", "HEAD")
    return source_revision


def _verify_no_unlocked_assets(root: Path, locked_names: set[str]) -> None:
    unexpected: list[str] = []
    for candidate in root.rglob("*"):
        if not candidate.is_file() or ".cache" in candidate.relative_to(root).parts:
            continue
        relative_name = candidate.relative_to(root).as_posix()
        if candidate.suffix.lower() in _EXECUTABLE_ASSET_SUFFIXES and relative_name not in locked_names:
            unexpected.append(relative_name)
    if unexpected:
        raise ResearchError(
            "ASSET_INVALID",
            "runtime",
            f"Unlocked executable model assets found under {root}: {', '.join(sorted(unexpected)[:5])}",
        )


def verify_runtime(paths: RuntimePaths | None = None) -> dict[str, str]:
    resolved = paths or RuntimePaths.discover()
    lock = load_asset_lock(resolved.lock_file)
    if not resolved.source.is_dir():
        raise ResearchError(
            "RUNTIME_MISSING",
            "runtime",
            f"Transcoda runtime is missing. Run {resolved.project_root / 'setup_research.ps1'}",
        )
    source_revision = _verify_source(resolved.source, lock["source"])
    model_files = lock["model"]["required_files"]
    base_model_files = lock["base_model"]["required_files"]
    for name, expected in model_files.items():
        _verify_file(resolved.model, name, expected)
    for name, expected in base_model_files.items():
        _verify_file(resolved.base_model, name, expected)
    _verify_no_unlocked_assets(resolved.model, set(model_files))
    _verify_no_unlocked_assets(resolved.base_model, set(base_model_files))
    return {
        "source_revision": source_revision,
        "model_revision": str(lock["model"]["revision"]),
        "model_sha256": str(lock["model"]["required_files"]["model.safetensors"]["sha256"]),
        "base_model_revision": str(lock["base_model"]["revision"]),
        "base_model_sha256": str(lock["base_model"]["required_files"]["model.safetensors"]["sha256"]),
    }
