"""Fixed-token replay and existing-interpreter checks, without model execution."""
from __future__ import annotations

import argparse
import importlib.metadata as metadata
import inspect
import json
from pathlib import Path
import sys
import tomllib
import xml.etree.ElementTree as ET

from homr_465_common import write_new
from screening_homr_compatibility import sha256_file

HERE = Path(__file__).resolve().parent
PHASE2 = HERE / "reports/homr-timing-465/phase2"
PHASE3 = PHASE2.parent / "phase3"


def canonical_music(root: ET.Element) -> str:
    # Retained token strings omit attention coordinates; these affect engraving only.
    for node in root.iter():
        node.attrib.pop("default-x", None)
        node.attrib.pop("default-y", None)
    return ET.tostring(root, encoding="unicode")


def replay(label: str) -> None:
    from packaging.requirements import Requirement
    from packaging.version import Version
    config = json.loads((PHASE2 / "candidate-configuration.json").read_text())
    source = Path(config["source"])
    for row in config["source_files"]:
        if sha256_file(Path(row["path"])) != row["sha256"]:
            raise ValueError("Pinned source changed")
    sys.path.insert(0, str(source))
    import homr.music_xml_generator as exporter
    from homr.transformer.vocabulary import EncodedSymbol
    expected_origin = source / "homr/music_xml_generator.py"
    if Path(exporter.__file__).resolve() != expected_origin.resolve():
        raise ValueError("Unexpected exporter origin")
    project = tomllib.loads((source / "pyproject.toml").read_text())
    requirements = project["project"]["dependencies"] + project["project"]["optional-dependencies"]["cuda"]
    dependencies = []
    for value in requirements:
        requirement = Requirement(value)
        try:
            version = metadata.version(requirement.name)
            compatible = Version(version) in requirement.specifier
        except metadata.PackageNotFoundError:
            version, compatible = None, False
        dependencies.append({"requirement": value, "version": version, "declared_compatible": compatible})
    import_probe = {}
    try:
        import homr.main as native
        import_probe = {"success": True, "origin": native.__file__,
                        "process_image": str(inspect.signature(native.process_image)),
                        "processing_config": str(inspect.signature(native.ProcessingConfig))}
    except Exception as error:
        import_probe = {"success": False, "error": f"{type(error).__name__}: {error}"}
    destination = PHASE3 / ("export-" + label)
    destination.mkdir(exist_ok=False)
    outputs = []
    for item in (path.name for path in sorted((PHASE2 / "development").iterdir()) if path.name.startswith("generated-")):
        root = PHASE2 / "development" / item
        tokens = json.loads((root / "tokens.json").read_text())
        staffs = [[EncodedSymbol(*value.split()) for value in voice] for voice in tokens["exporter_inputs"]]
        xml = exporter.generate_xml(exporter.XmlGeneratorArguments(), staffs, tokens["title"])
        matches = canonical_music(xml) == canonical_music(ET.parse(root / "input.musicxml").getroot())
        if not matches:
            raise ValueError("Fixed-token musical replay differs: " + item)
        path = destination / (item + ".musicxml")
        ET.ElementTree(xml).write(path, encoding="utf-8", xml_declaration=True)
        outputs.append({"item_id": item, "musical_xml_matches_cached": matches, "path": str(path), "sha256": sha256_file(path)})
    symbols = [EncodedSymbol("clef_G2", position="upper"), EncodedSymbol("clef_F4", position="lower"), EncodedSymbol("timeSignature/4")]
    for position, pitch in (("upper", "C5"), ("upper2", "E4"), ("lower", "C3"), ("lower2", "E3")):
        if position != "upper":
            symbols.append(EncodedSymbol("chord"))
        symbols.append(EncodedSymbol("note_1", pitch, "_", "_", "_", position))
    symbols.append(EncodedSymbol("barline"))
    xml = exporter.generate_xml(exporter.XmlGeneratorArguments(), [symbols], "")
    probe_path = destination / "four-position-voices.musicxml"
    ET.ElementTree(xml).write(probe_path, encoding="utf-8", xml_declaration=True)
    coordinates = [(note.findtext("pitch/step"), note.findtext("pitch/octave"), note.findtext("staff"), note.findtext("voice")) for note in xml.findall(".//note") if note.find("pitch") is not None]
    if {row[2] for row in coordinates} != {"1", "2"} or any(len({row[3] for row in coordinates if row[2] == staff}) != 2 for staff in ("1", "2")):
        raise ValueError("Additional positions did not retain distinct voices on existing staves")
    write_new(PHASE3 / ("runtime-" + label + ".json"), {
        "python": sys.executable, "python_version": sys.version, "exporter": str(expected_origin),
        "dependencies": dependencies, "native_import": import_probe, "replays": outputs,
        "four_positions": {"path": str(probe_path), "coordinates": coordinates},
        "scope": "Fixed-token export/import only; no inference, GPU session or installed executable execution"})
    print(json.dumps({"label": label, "replayed": len(outputs), "native_import": import_probe["success"],
                      "incompatible": [row for row in dependencies if not row["declared_compatible"]], "coordinates": coordinates}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("label", choices=("shared", "installed"))
    replay(parser.parse_args().label)
