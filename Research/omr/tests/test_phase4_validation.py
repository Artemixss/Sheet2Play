"""Integrity checks use altered bytes rather than fake successful verification."""
from pathlib import Path
import json
import shutil

import pytest

import phase4_validation as validation
import screening_homr_extension as extension


def source_copy(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    shutil.copytree(extension.SOURCE / "homr", source / "homr",
                    ignore=shutil.ignore_patterns("__pycache__"))
    (source / ".git").mkdir()
    (source / ".git/HEAD").write_text(extension.REVISION + "\n")
    return source


@pytest.mark.parametrize("change", ["added", "missing", "altered", "revision"])
def test_git_free_source_rejects_changes(tmp_path: Path, change: str) -> None:
    source = source_copy(tmp_path)
    target = source / "homr/transformer/vocabulary.py"
    if change == "added":
        (source / "homr/rogue.py").write_text("raise RuntimeError('shadow')\n")
    elif change == "missing":
        target.unlink()
    elif change == "altered":
        target.write_text(target.read_text() + "\nchanged = True\n")
    else:
        (source / ".git/HEAD").write_text("0" * 40)
    with pytest.raises((ValueError, FileNotFoundError)):
        validation.checked_homr_source(source, extension.REVISION)


def test_changed_historical_artifact_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    value = json.loads(extension.BASE_MANIFEST.read_text())
    value["items"][0]["image_sha256"] = "0" * 64
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="Historical artifact"):
        validation.historical_screen(path)


def test_changed_or_missing_input_rejected(tmp_path: Path) -> None:
    path = tmp_path / "image.png"
    path.write_bytes(b"input")
    expected = {"image.png": validation.file_hash(path)}
    path.write_bytes(b"other")
    with pytest.raises(ValueError, match="SHA-256"):
        validation.verify_files(tmp_path, expected)
    path.unlink()
    with pytest.raises(FileNotFoundError):
        validation.verify_files(tmp_path, expected)


@pytest.mark.parametrize("name", ["../escape", "C:/escape"])
def test_inventory_escape_rejected(tmp_path: Path, name: str) -> None:
    with pytest.raises(ValueError, match="Unsafe"):
        validation.safe_path(tmp_path, name)


def test_current_metadata_addition_requires_new_admission() -> None:
    saved = {"runtime": {"packages": {"music21": "9.9.1"}}, "source": "a" * 64}
    observed = {"runtime": {"packages": {"music21": "9.9.1", "new": "1"}}, "source": "a" * 64}
    validation.verify_current_admission(saved, saved)
    with pytest.raises(ValueError, match="Current runtime"):
        validation.verify_current_admission(saved, observed)
