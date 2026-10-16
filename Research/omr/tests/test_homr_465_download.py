from __future__ import annotations

import io
import json
from pathlib import Path
import zipfile

import pytest

import homr_465_download as download


class Response(io.BytesIO):
    def __init__(self, content: bytes, length: int | None = None):
        super().__init__(content)
        self.headers = {} if length is None else {"Content-Length": str(length)}


def test_reservation_blocks_before_network(tmp_path, monkeypatch):
    budget = download.Budget(tmp_path / "budget.json")
    budget.data["reserved_bytes"] = download.CAP - 1
    monkeypatch.setattr(download.urllib.request, "urlopen", lambda *a, **k: pytest.fail("Network must not start"))
    with pytest.raises(RuntimeError, match="3 GB"):
        budget.fetch("https://example.com", tmp_path / "payload", 2)


@pytest.mark.parametrize("length,content", [(10, b"a"), (None, b"abcdef"), (4, b"abc")])
def test_length_overflow_and_truncation_preserve_failure(tmp_path, monkeypatch, length, content):
    budget = download.Budget(tmp_path / "budget.json")
    monkeypatch.setattr(download.urllib.request, "urlopen", lambda *a, **k: Response(content, length))
    with pytest.raises(RuntimeError):
        budget.fetch("https://example.com", tmp_path / "payload", 5)
    saved = json.loads(budget.path.read_text())
    assert saved["requests"][0]["status"] == "failed"
    assert saved["reserved_bytes"] == download.CONTROL_RESERVE + 1_000_010


def test_complete_response_hash_and_freshness(tmp_path, monkeypatch):
    budget = download.Budget(tmp_path / "budget.json")
    monkeypatch.setattr(download.urllib.request, "urlopen", lambda *a, **k: Response(b"abc", 3))
    target = tmp_path / "payload"
    row = budget.fetch("https://example.com", target, 3)
    assert row["sha256"] == download.hashlib.sha256(b"abc").hexdigest()
    assert budget.data["received_payload_bytes"] == 3
    with pytest.raises(ValueError, match="fresh"):
        budget.fetch("https://example.com", target, 3)


def test_zip_traversal_rejected(tmp_path):
    archive = tmp_path / "source.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("source/../../escape", "bad")
    with pytest.raises(ValueError, match="Unsafe"):
        download.extract(archive, tmp_path / "output", "source/")
    assert not (tmp_path.parent / "escape").exists()


def test_archive_revision_prefix_rejected(tmp_path):
    archive = tmp_path / "source.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("wrong/homr/main.py", "bad")
    with pytest.raises(ValueError, match="revision"):
        download.extract(archive, tmp_path / "output", "pinned/")
