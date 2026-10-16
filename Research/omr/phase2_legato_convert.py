"""Run LEGATO's pinned ABC cleanup/conversion while preserving one MusicXML document."""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from types import ModuleType


def _load_converter(path: Path) -> ModuleType:
    specification = importlib.util.spec_from_file_location("sheet2play_legato_convert", path)
    if specification is None or specification.loader is None:
        raise RuntimeError(f"Cannot load LEGATO converter: {path}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def convert(
    legato_root: Path,
    native_path: Path,
    output_path: Path,
    musescore: Path,
) -> None:
    if not native_path.is_file() or not musescore.is_file():
        raise ValueError("LEGATO native output or MuseScore executable is missing")
    converter = _load_converter(legato_root / "utils" / "convert.py")
    converter.ABC2XML_CMD = [sys.executable, str(legato_root / "utils" / "abc2xml.py")]
    converter.XMLFIX_CMD = [str(musescore)]
    document = json.loads(native_path.read_text(encoding="utf-8"))
    transcriptions = document.get("abc_transcription")
    if not isinstance(transcriptions, list) or len(transcriptions) != 1:
        raise ValueError("Phase-2 LEGATO adapter requires exactly one ABC transcription")
    with tempfile.TemporaryDirectory(prefix="s2p-legato-convert-") as temporary:
        converted = converter.convert_abc_to_xml(document, temporary)
    if not isinstance(converted, list) or len(converted) != 1 or not converted[0].strip():
        raise RuntimeError("LEGATO ABC conversion produced no MusicXML")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(converted[0], encoding="utf-8")


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legato-root", required=True, type=Path)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--musescore", required=True, type=Path)
    args = parser.parse_args(arguments)
    try:
        convert(
            args.legato_root.resolve(),
            args.input.resolve(),
            args.output.resolve(),
            args.musescore.resolve(),
        )
        return 0
    except Exception as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
