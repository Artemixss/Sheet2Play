"""Separate historical evidence verification from current, Git-free runtime admission."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE_MANIFEST = HERE / "reports/screening/v1/manifest-v3-0b5eb110e968.json"
SOURCE_MANIFEST_HASH = "5e59f99006c4a8c7c169eee667080f7ff7537010bb1c6f3f91952ee70571de4f"
HISTORICAL_MANIFEST_HASH = "1cf36e06b12a0ce72f7bb1e8e358ea9a8b374449f807f11e4a843f351158e1ee"
HISTORICAL_FREEZE_HASH = "3fdd3d76aeab4188244795ea7b5eb310b2129d8d50131290297aeb1a32020633"


def file_hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def checked_json(path: Path, expected: str) -> dict[str, Any]:
    if file_hash(path) != expected:
        raise ValueError(f"Historical artifact SHA-256 changed: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected an object: {path}")
    return value


def safe_path(root: Path, name: str) -> Path:
    relative = Path(name)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"Unsafe inventory path: {name}")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"Inventory escapes root: {name}")
    return path


def verify_files(root: Path, files: dict[str, str]) -> None:
    if not files:
        raise ValueError("Empty source inventory")
    for name, expected in files.items():
        if not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise ValueError(f"Invalid inventory digest: {name}")
        if file_hash(safe_path(root, name)) != expected:
            raise ValueError(f"source worktree status / SHA-256 changed: {name}")


def read_revision(source: Path) -> str:
    git_dir = source / ".git"
    if not git_dir.is_dir():
        raise ValueError("Source revision metadata is missing or unsupported")
    head = (git_dir / "HEAD").read_text(encoding="ascii").strip()
    if head.startswith("ref: "):
        ref = head[5:]
        path = safe_path(git_dir, ref)
        if path.is_file():
            head = path.read_text(encoding="ascii").strip()
        else:
            packed = (git_dir / "packed-refs").read_text(encoding="ascii").splitlines()
            matches = [line.split()[0] for line in packed
                       if not line.startswith(("#", "^")) and line.split()[1:] == [ref]]
            if len(matches) != 1:
                raise ValueError("Source revision ref is absent or ambiguous")
            head = matches[0]
    if not re.fullmatch(r"[0-9a-f]{40}", head):
        raise ValueError("Source revision metadata is invalid")
    return head


def checked_homr_source(source: Path, revision: str) -> dict[str, str]:
    manifest = checked_json(SOURCE_MANIFEST, SOURCE_MANIFEST_HASH)
    identity = manifest["candidates"]["homr_455"]["identity"]
    if revision != identity["source_revision"] or read_revision(source) != revision:
        raise ValueError("HOMR 455 source revision changed")
    prefix = "Research/omr/.runtime/homr-455-compatible/source/"
    files = {name.removeprefix(prefix): digest
             for name, digest in identity["source_files"].items() if name.startswith(prefix)}
    observed = {path.relative_to(source).as_posix() for path in (source / "homr").rglob("*")
                if path.is_file() and "__pycache__" not in path.parts
                and path.suffix not in {".pyc", ".pyo"}}
    if observed != set(files):
        raise ValueError(f"source worktree status / inventory changed: "
                         f"added={sorted(observed - set(files))}, missing={sorted(set(files) - observed)}")
    verify_files(source, files)
    return files


def historical_screen(path: Path) -> dict[str, Any]:
    """Verify recorded artifacts/inputs; this does not admit today's runtime."""
    saved = checked_json(path, HISTORICAL_MANIFEST_HASH)
    freeze = HERE / "reports/phase3/phase3-config-freeze-v1-89f385c8790b.json"
    checked_json(freeze, HISTORICAL_FREEZE_HASH)
    for item in saved["items"]:
        for name in ("image", "reference"):
            target = safe_path(ROOT, item[f"{name}_path"])
            if file_hash(target) != item[f"{name}_sha256"]:
                raise ValueError(f"Historical input/reference changed: {item['id']}")
    pins = {
        "Research/omr/reports/phase1/smb-pianoform.jsonl": saved["frozen_primary_manifest_sha256"],
        "Research/omr/smb.lock.json": saved["frozen_smb_lock_sha256"],
        "Research/omr/reports/phase1/scoring-protocol.json": saved["scoring_protocol_sha256"],
        "Research/omr/src/sheet2play_omr/phase3_scoring.py": saved["scorer_sha256"],
        "Research/omr/phase3_score.py": saved["scoring_summary_sha256"],
    }
    verify_files(ROOT, pins)
    return saved


def verify_current_admission(saved: dict[str, Any], observed: dict[str, Any]) -> None:
    if saved != observed:
        raise ValueError("Current runtime admission changed; record a new identity before execution")
