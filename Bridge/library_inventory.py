"""Read retained HOMR sources and old manifests without changing the library."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

SUPPORTED_SOURCES = {".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def relative_path(path: Path, library: Path) -> str:
    return path.resolve(strict=True).relative_to(library).as_posix()


def page_count(path: Path) -> int:
    if path.suffix.lower() != ".pdf":
        return 1
    import pymupdf

    with pymupdf.open(path) as document:
        if document.is_encrypted or document.page_count <= 0:
            raise ValueError("Retained PDF is encrypted or empty")
        return document.page_count


def inventory(library: Path) -> list[dict[str, object]]:
    library = library.resolve(strict=True)
    sources: dict[str, list[Path]] = {}
    for path in sorted((library / "songs/pdf").glob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED_SOURCES:
            relative_path(path, library)
            sources.setdefault(file_hash(path), []).append(path)
    entries = []
    for manifest_path in sorted((library / "songs/midi/homr").glob("*.mid.cache.json")):
        old_manifest = relative_path(manifest_path, library)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        if manifest.get("engine") != "homr":
            raise ValueError("Non-HOMR manifest in the HOMR directory")
        source_hash = manifest.get("source_sha256")
        if not isinstance(source_hash, str) or len(source_hash) != 64 or any(
                character not in "0123456789abcdef" for character in source_hash):
            raise ValueError("Old manifest has an invalid source identity")
        matching = sources.get(source_hash, [])
        stem = manifest_path.name[:-len(".mid.cache.json")]
        source = next((path for path in matching if path.stem == stem), matching[0] if matching else None)
        midi = Path(str(manifest_path)[:-len(".cache.json")])
        entries.append({
            "id": hashlib.sha256(old_manifest.encode()).hexdigest(),
            "old_manifest": old_manifest,
            "old_manifest_sha256": file_hash(manifest_path),
            "old_midi_sha256": file_hash(midi) if midi.is_file() else None,
            "source_relative_path": relative_path(source, library) if source else None,
            "source_sha256": source_hash,
            "pages": page_count(source) if source else 0,
            "unavailable_reason": None if source else (
                "No matching retained source; old MIDI also missing" if not midi.is_file()
                else "No matching retained source; old MIDI retained"),
        })
    return entries


def main() -> int:
    try:
        if len(sys.argv) != 2:
            raise ValueError("Expected an absolute library directory")
        library = Path(sys.argv[1])
        if not library.is_absolute():
            raise ValueError("Library directory must be absolute")
        print(json.dumps(inventory(library), sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
        print(f"Library inventory failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
