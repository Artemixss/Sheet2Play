from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from sheet2play_omr.assets import load_asset_lock, sha256_file
from sheet2play_omr.errors import ResearchError


class AssetTests(unittest.TestCase):
    @staticmethod
    def _valid_lock() -> dict[str, object]:
        artifact = {"sha256": "a" * 64, "size": 1}
        return {
            "schema_version": 1,
            "source": {
                "repository": "https://github.com/example/project.git",
                "revision": "b" * 40,
                "revision_algorithm": "git-sha1",
                "require_clean_checkout": True,
            },
            "model": {
                "revision": "c" * 40,
                "required_files": {"model.safetensors": artifact},
            },
            "base_model": {
                "revision": "d" * 40,
                "required_files": {"model.safetensors": artifact},
            },
        }

    def test_sha256_is_streamed_and_stable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "asset.bin"
            path.write_bytes(b"sheet2play")
            self.assertEqual(hashlib.sha256(b"sheet2play").hexdigest(), sha256_file(path, chunk_size=2))

    def test_unknown_lock_schema_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "assets.lock.json"
            path.write_text(json.dumps({"schema_version": 99}), encoding="utf-8")
            with self.assertRaises(ResearchError):
                load_asset_lock(path)

    def test_short_source_revision_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "assets.lock.json"
            payload = self._valid_lock()
            payload["source"]["revision"] = "abc123"  # type: ignore[index]
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ResearchError):
                load_asset_lock(path)

    def test_unsafe_locked_asset_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "assets.lock.json"
            payload = self._valid_lock()
            payload["model"]["required_files"] = {  # type: ignore[index]
                "../model.safetensors": {"sha256": "a" * 64, "size": 1}
            }
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ResearchError):
                load_asset_lock(path)


if __name__ == "__main__":
    unittest.main()
