"""Preserve Zeus LMX, pre-normalization MusicXML, and integration artifacts."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parent.parent
ZEUS = HERE / "zeus"
ZEUS_PYTHON = ZEUS / ".venv" / "Scripts" / "python.exe"
SRC = HERE / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sheet2play_omr.adapter_contract import sha256_file  # noqa: E402
from sheet2play_omr.phase2r_vlm import crop_detected_systems  # noqa: E402


def _run_upstream(image: Path, output: Path, index: int) -> tuple[str, Path]:
    helper = output / f"request-{index}.json"
    helper.write_text(json.dumps([{"page": index, "path": str(image.resolve())}]), encoding="utf-8")
    result = subprocess.run(
        [str(ZEUS_PYTHON), str(ZEUS / "infer_batch.py"), str(helper), str(output)],
        cwd=ZEUS,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-2000:] or f"Zeus exited {result.returncode}")
    summary = json.loads((output / "zeus_summary.json").read_text(encoding="utf-8"))
    row = summary[0]
    if row["status"] != "success":
        raise RuntimeError(str(row.get("error", "Zeus system failed")))
    xml = Path(row["xml_path"])
    native = row.get("lmx")
    if not isinstance(native, str) or not native.strip():
        raise RuntimeError("Zeus helper did not preserve native LMX")
    return native, xml


def _detect_systems(image: Path, temporary: Path, evidence_output: Path) -> list[Path]:
    homr_python = WORKSPACE / "Bridge" / ".venv-homr-gpu" / "Scripts" / "python.exe"
    detector = HERE / "src" / "sheet2play_omr" / "phase2r_detector.py"
    boxes = temporary / "systems.json"
    detector_image = temporary / "detector-preprocessed.png"
    result = subprocess.run(
        [str(homr_python), str(detector), str(image), str(boxes),
         str(detector_image), str(WORKSPACE / "Bridge")],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not boxes.is_file():
        raise RuntimeError(result.stderr[-2000:] or "System detection failed")
    document = json.loads(boxes.read_text(encoding="utf-8"))
    paths = crop_detected_systems(detector_image, document, temporary / "crops",
                                  source_sha256=sha256_file(image))
    evidence_output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(boxes, evidence_output / "detected-systems.json")
    shutil.copy2(detector_image, evidence_output / "detector-preprocessed.png")
    shutil.copy2(temporary / "crops" / "crop-manifest.json", evidence_output / "crop-manifest.json")
    for path in paths:
        shutil.copy2(path, evidence_output / path.name)
    return paths


def _stitch(xml_files: list[Path], destination: Path) -> None:
    if not xml_files:
        raise ValueError("At least one Zeus system is required for stitching")
    trees = [ET.parse(path) for path in xml_files]
    root = trees[0].getroot()
    parts = {part.get("id"): part for part in root.findall("part")}
    if not parts or None in parts or len(parts) != len(root.findall("part")):
        raise RuntimeError("Zeus MusicXML has missing or duplicate part identities")
    for tree in trees[1:]:
        extra = tree.getroot().findall("part")
        extra_parts = {part.get("id"): part for part in extra}
        if None in extra_parts or len(extra_parts) != len(extra) or set(extra_parts) != set(parts):
            raise RuntimeError("Zeus part identities changed while stitching systems")
        for part_id, destination_part in parts.items():
            source_part = extra_parts[part_id]
            for measure in list(source_part):
                if measure.tag.rsplit("}", 1)[-1] == "measure":
                    destination_part.append(measure)
    trees[0].write(destination, encoding="unicode", xml_declaration=True)


def run(input_path: Path, output: Path, mode: str) -> None:
    if not input_path.is_file():
        raise ValueError(f"Input is missing: {input_path}")
    if not ZEUS_PYTHON.is_file():
        raise RuntimeError(f"Zeus Python is missing: {ZEUS_PYTHON}")
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="s2p-phase2-zeus-") as temporary_name:
        temporary = Path(temporary_name)
        inputs = ([input_path] if mode == "upstream" else
                  _detect_systems(input_path, temporary, output / "detector"))
        native: list[dict[str, Any]] = []
        xml_files: list[Path] = []
        for index, image in enumerate(inputs, start=1):
            work = temporary / f"zeus-{index:04d}"
            work.mkdir()
            lmx, xml = _run_upstream(image, work, index)
            native.append({"system": index, "lmx": lmx})
            preserved = output / f"system-{index:04d}.musicxml"
            shutil.copy2(xml, preserved)
            xml_files.append(preserved)
        (output / "native.lmx.json").write_text(
            json.dumps(native, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        _stitch(xml_files, output / "score.musicxml")


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--mode", choices=("upstream", "integration"), required=True)
    args = parser.parse_args(arguments)
    try:
        run(args.input.resolve(), args.output.resolve(), args.mode)
        return 0
    except Exception as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
