"""Bridge entry for MusicXML songs: run the bridge unchanged and keep the MusicXML it read.

Phase 1 of `plans/2026-10-19-musicxml-songs.md`. `bridge.py` writes each HOMR page's MusicXML into
a temporary directory and deletes it when the run ends, so the score was lost after every
conversion. This entry wraps `bridge.normalize_musicxml` to copy each page out as the bridge
reads it, then runs `bridge.main` with the remaining arguments. Every runtime and profile check,
the progress protocol and the schema 2 JSON on stdout are the bridge's own; no pinned file
changes.

    song_entry.py --song-output DIR [--timing-correction] --engine ENGINE INPUT

After a successful run, DIR holds the song package:

    recognition.json                 what produced the pages (engine, source, page hashes)
    pages/page-0001.musicxml ...     HOMR's pages, byte for byte (an import: source.<ext>)
    derived/<interpretation key>/    performance.json and score.musicxml (`song_model`)

The package is written beside DIR and moved into place whole, so DIR is either complete or
absent. Packaging never changes the conversion's outcome: a failure is reported on stderr as
`SHEET2PLAY_SONG_ERROR:` with the bridge's exit status unchanged. A package whose interpretation
failed keeps its pages, so it can be interpreted again without OMR. `--timing-correction` applies
the shipped timing fix both to the stdout JSON and to the interpretation.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import timing_correction

SONG_PREFIX = "SHEET2PLAY_SONG:"
SONG_ERROR_PREFIX = "SHEET2PLAY_SONG_ERROR:"
PACKAGE_SCHEMA_VERSION = 1


def split_arguments(arguments: Sequence[str]) -> tuple[Path, bool, list[str]]:
    output: Path | None = None
    timing = False
    remaining: list[str] = []
    iterator = iter(arguments)
    for argument in iterator:
        if argument == "--song-output":
            value = next(iterator, None)
            if value is None:
                raise SystemExit("--song-output needs a directory")
            output = Path(value)
        elif argument.startswith("--song-output="):
            output = Path(argument.split("=", 1)[1])
        elif argument == "--timing-correction":
            timing = True
        else:
            remaining.append(argument)
    if output is None:
        raise SystemExit("song_entry.py needs --song-output DIR")
    return output, timing, remaining


def input_argument(bridge: Any, arguments: Sequence[str]) -> Path | None:
    try:
        return Path(bridge.parse_arguments(list(arguments)).input_path)
    except SystemExit:
        return None


def install_capture(bridge: Any, directory: Path, captured: list[Path], problems: list[str]) -> None:
    """Copy every page the bridge normalizes into `directory`, in the order it reads them.

    A failed copy only costs the package: the conversion itself carries on unchanged.
    """
    normalize = bridge.normalize_musicxml

    def normalize_and_keep(path: Path, *args: Any, **kwargs: Any) -> Any:
        target = directory / f"page-{len(captured) + 1:04d}.musicxml"
        try:
            directory.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            captured.append(target)
        except OSError as error:
            problems.append(f"could not keep {Path(path).name}: {error}")
            captured.append(target)
        return normalize(path, *args, **kwargs)

    bridge.normalize_musicxml = normalize_and_keep


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _report(prefix: str, payload: dict[str, Any]) -> None:
    sys.stderr.write(prefix + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
    sys.stderr.flush()


def write_package(staging: Path, output: Path, *, engine: str, source: Path, kind: str,
                  sources: list[Path], timing: bool) -> dict[str, Any]:
    import song_model

    recognition = {
        "package_schema_version": PACKAGE_SCHEMA_VERSION,
        "kind": kind,
        "engine": engine,
        "source_name": source.name,
        "source_sha256": _sha256(source),
        "song_entry_sha256": _sha256(Path(__file__)),
        "files": [{"name": path.relative_to(staging).as_posix(), "sha256": _sha256(path)} for path in sources],
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (staging / "recognition.json").write_text(json.dumps(recognition, indent=1) + "\n", encoding="utf-8")
    key = song_model.interpretation_key(timing and kind == song_model.OMR_PAGES)
    summary: dict[str, Any] = {"path": str(output), "interpretation_key": key}
    try:
        performance = song_model.write_song(sources, staging / "derived" / key, kind=kind,
                                            timing_correction_enabled=timing)
        summary["features"] = performance["features"]
    except Exception as error:  # noqa: BLE001 - the pages are kept so it can be interpreted again
        shutil.rmtree(staging / "derived", ignore_errors=True)
        summary["interpretation_error"] = f"{type(error).__name__}: {error}"
    if output.exists():
        retired = output.with_name(f".{output.name}.{uuid.uuid4().hex}.old")
        os.replace(output, retired)
        os.replace(staging, output)
        shutil.rmtree(retired, ignore_errors=True)
    else:
        os.replace(staging, output)
    return summary


def run(arguments: Sequence[str], bridge: Any) -> int:
    output, timing, bridge_arguments = split_arguments(arguments)
    engine = timing_correction.engine_argument(bridge_arguments) or "homr"
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = output.with_name(f".{output.name}.{uuid.uuid4().hex}.tmp")
    captured: list[Path] = []
    problems: list[str] = []
    if engine in timing_correction.HOMR_ENGINES:
        install_capture(bridge, staging / "pages", captured, problems)
        if timing:
            timing_correction.install(bridge)
    status = bridge.main(bridge_arguments)
    try:
        if status != 0:
            return status
        source = input_argument(bridge, bridge_arguments)
        if source is None or engine not in timing_correction.HOMR_ENGINES | {"musicxml"}:
            return status
        if engine == "musicxml":
            staging.mkdir(parents=True, exist_ok=True)
            kept = staging / f"source{source.suffix.lower()}"
            shutil.copyfile(source, kept)
            sources, kind = [kept], "musicxml"
        else:
            if problems or not captured:
                raise OSError("; ".join(problems) or "the bridge read no page MusicXML")
            sources, kind = captured, "omr-pages"
        _report(SONG_PREFIX, write_package(staging, output, engine=engine, source=source, kind=kind,
                                           sources=sources, timing=timing))
    except Exception as error:  # noqa: BLE001 - packaging must not change the conversion's outcome
        _report(SONG_ERROR_PREFIX, {"path": str(output), "error": f"{type(error).__name__}: {error}"})
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return status


def main(arguments: Sequence[str] | None = None) -> int:
    import bridge

    return run(list(sys.argv[1:] if arguments is None else arguments), bridge)


if __name__ == "__main__":
    sys.exit(main())
