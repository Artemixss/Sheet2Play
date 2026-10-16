from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import subprocess

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from library_inventory import file_hash, inventory


def write_manifest(root: Path, name: str, source_hash: str, midi: bool = True) -> Path:
    path = root / f"songs/midi/homr/{name}.mid.cache.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"engine": "homr", "source_sha256": source_hash}))
    if midi:
        path.with_name(f"{name}.mid").write_bytes(b"old midi")
    return path


def test_inventory_matches_by_hash_preserves_original_name_and_accounts_orphan(tmp_path: Path) -> None:
    source = tmp_path / "songs/pdf/original.png"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"source image")
    (source.parent / "000-candidate-copy.png").write_bytes(source.read_bytes())
    old = write_manifest(tmp_path, "original", file_hash(source))
    write_manifest(tmp_path, "missing", "a" * 64, midi=False)
    ignored = tmp_path / "songs/midi/zeus/other.mid.cache.json"
    ignored.parent.mkdir(parents=True)
    ignored.write_text("invalid and deliberately outside the inventory")
    before = file_hash(old)
    rows = inventory(tmp_path)
    assert len(rows) == 2
    ready = next(row for row in rows if row["pages"] == 1)
    assert ready["source_relative_path"] == "songs/pdf/original.png"
    assert ready["old_midi_sha256"] == hashlib.sha256(b"old midi").hexdigest()
    orphan = next(row for row in rows if row["pages"] == 0)
    assert orphan["source_relative_path"] is None
    assert "MIDI also missing" in orphan["unavailable_reason"]
    assert file_hash(old) == before


def test_inventory_counts_every_pdf_page(tmp_path: Path) -> None:
    source = tmp_path / "songs/pdf/score.pdf"
    source.parent.mkdir(parents=True)
    try:
        import pymupdf
    except ImportError:
        python = Path(__file__).resolve().parents[1] / ".venv-homr-gpu/Scripts/python.exe"
        if not python.is_file():
            pytest.skip("Install PyMuPDF or provision the app PDF runtime")
        subprocess.run([str(python), "-B", "-c", "import pymupdf,sys; d=pymupdf.open(); d.new_page(); d.new_page(); d.save(sys.argv[1]); d.close()",
                        str(source)], check=True, timeout=30, capture_output=True)
        write_manifest(tmp_path, "score", file_hash(source))
        result = subprocess.run([str(python), "-B", str(Path(__file__).resolve().parents[1] / "library_inventory.py"),
                                 str(tmp_path)], check=True, timeout=30, capture_output=True, text=True)
        assert json.loads(result.stdout)[0]["pages"] == 2
        return
    with pymupdf.open() as document:
        document.new_page()
        document.new_page()
        document.save(source)
    write_manifest(tmp_path, "score", file_hash(source))
    assert inventory(tmp_path)[0]["pages"] == 2


def test_inventory_rejects_wrong_engine_or_invalid_hash(tmp_path: Path) -> None:
    old = write_manifest(tmp_path, "wrong", "a" * 64)
    old.write_text(json.dumps({"engine": "homr465", "source_sha256": "a" * 64}))
    with pytest.raises(ValueError, match="Non-HOMR"):
        inventory(tmp_path)
    old.write_text(json.dumps({"engine": "homr", "source_sha256": "wrong"}))
    with pytest.raises(ValueError, match="invalid source"):
        inventory(tmp_path)
