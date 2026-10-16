"""Compatibility gate and symbolic conversion checks for the pinned HOMR 455 release."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

import screening_common as common
import screening_development as development
import screening_homr_compatibility as compatibility
import screening_homr_extension as extension


PYTHON = extension.RUNTIME / "Scripts/python.exe"
OLD_SOURCE = common.HERE / ".runtime/homr-455/source"
VALIDATOR = common.HERE / "screening_homr_compatibility.py"


def validate_with(contract: Path, source: Path = extension.SOURCE,
                  encoder: Path = extension.ENCODER, decoder: Path = extension.DECODER
                  ) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(PYTHON), "-B", str(VALIDATOR), "--source", str(source),
         "--encoder", str(encoder), "--decoder", str(decoder),
         "--contract", str(contract)], capture_output=True, text=True, timeout=30)


def changed_contract(tmp_path: Path, change) -> Path:
    value = common.read_json(extension.CONTRACT)
    change(value)
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_pinned_pair_and_ordered_labels_pass() -> None:
    process = validate_with(extension.CONTRACT)
    assert process.returncode == 0, process.stderr
    report = json.loads(process.stdout)
    contract = common.read_json(extension.CONTRACT)
    assert report["source_revision"] == extension.REVISION
    assert report["ordered_label_sha256"]["position"] == common.digest([".", "upper", "lower"])
    assert {name: model["sha256"] for name, model in report["models"].items()} == {
        name: spec["sha256"] for name, spec in contract["models"].items()}


@pytest.mark.parametrize(("change", "diagnostic"), [
    (lambda c: c["labels"]["position"].insert(2, "upper2"), "position labels"),
    (lambda c: c["labels"]["position"].__setitem__(slice(1, 3), ["lower", "upper"]),
     "position labels"),
    (lambda c: c["models"]["encoder"].__setitem__("sha256", "0" * 64), "encoder SHA-256"),
    (lambda c: c["models"]["decoder"]["outputs"].pop(), "decoder outputs count"),
    (lambda c: c["models"]["decoder"]["inputs"][0].__setitem__("type", "tensor(float16)"),
     "decoder inputs[0]"),
    (lambda c: c["models"]["decoder"]["inputs"][7]["shape"].__setitem__(1, 9),
     "decoder inputs[7]"),
    (lambda c: c.__setitem__("source_revision", "0" * 40), "source revision"),
])
def test_incompatible_contract_is_rejected(tmp_path: Path, change, diagnostic: str) -> None:
    process = validate_with(changed_contract(tmp_path, change))
    assert process.returncode != 0
    assert diagnostic in process.stderr


def test_screened_source_and_missing_model_are_rejected() -> None:
    old = validate_with(extension.CONTRACT, source=OLD_SOURCE)
    assert old.returncode != 0 and "source revision" in old.stderr
    missing = validate_with(extension.CONTRACT, encoder=extension.ENCODER.with_name("missing.onnx"))
    assert missing.returncode != 0 and "encoder is missing" in missing.stderr


def test_dirty_source_is_rejected(tmp_path: Path) -> None:
    import shutil
    source = tmp_path / "source"
    shutil.copytree(extension.SOURCE / "homr", source / "homr", ignore=shutil.ignore_patterns("__pycache__"))
    (source / ".git").mkdir()
    (source / ".git/HEAD").write_text(extension.REVISION + "\n")
    vocabulary = source / "homr/transformer/vocabulary.py"
    vocabulary.write_text(vocabulary.read_text() + "\nchanged = True\n")
    with pytest.raises(ValueError, match="source worktree status"):
        compatibility.check_source(source, common.read_json(extension.CONTRACT))


def test_wrong_imported_source_is_rejected() -> None:
    script = (
        "import json,sys,pathlib;"
        f"sys.path.insert(0,{str(OLD_SOURCE.resolve())!r});"
        "import homr;"
        f"sys.path.insert(0,{str(common.HERE.resolve())!r});"
        "from screening_homr_compatibility import check_vocabulary;"
        f"check_vocabulary(pathlib.Path({str(extension.SOURCE.resolve())!r}),"
        f"json.loads(pathlib.Path({str(extension.CONTRACT.resolve())!r}).read_text()))"
    )
    process = subprocess.run([str(PYTHON), "-B", "-c", script], capture_output=True,
                             text=True, timeout=20)
    assert process.returncode != 0 and "wrong source" in process.stderr


def test_live_manifest_rejects_historical_455_identity(tmp_path: Path,
                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    assert common.verify_manifest(extension.BASE_MANIFEST)["candidates"]["homr_page"] == \
        common.read_json(extension.BASE_MANIFEST)["candidates"]["homr_page"]
    with pytest.raises(ValueError, match="incompatible source"):
        common.verify_manifest(common.REPORTS / "manifest-v2-0de561e2ae9d.json")
    bad = changed_contract(tmp_path, lambda c: c["labels"]["position"].append("lower2"))
    monkeypatch.setattr(extension, "CONTRACT", bad)
    with pytest.raises(subprocess.CalledProcessError):
        extension.build_extended_manifest()


def test_missing_compatibility_report_blocks_verification(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(extension, "REPORTS", tmp_path)
    with pytest.raises(FileNotFoundError, match="compatibility report is missing"):
        extension.compatibility_evidence()


def test_development_ram_override_keeps_other_resource_blocks() -> None:
    sample = {"ram_percent": 90.3,
              "admission_blockers": ["system_ram_at_or_above_90_percent"]}
    assert development.development_blockers(sample, 95) == []
    assert development.development_blockers(sample, 90) == ["system_ram_at_or_above_90_percent"]
    sample["ram_percent"] = 95.0
    assert development.development_blockers(sample, 95) == ["system_ram_at_or_above_95_percent"]
    sample["admission_blockers"].append("device_vram_at_or_above_90_percent")
    assert development.development_blockers(sample, 95) == [
        "device_vram_at_or_above_90_percent", "system_ram_at_or_above_95_percent"]


def test_release_symbolic_conversion_and_shared_normalizer(tmp_path: Path) -> None:
    script = r'''
import json
import pathlib
import sys
import xml.etree.ElementTree as ET
import numpy as np
source = pathlib.Path(sys.argv[1]).resolve()
sys.path.insert(0, str(source))
from homr.transformer.configs import Config
from homr.transformer.decoder_inference import ScoreDecoder, detokenize
from homr.music_xml_generator import XmlGeneratorArguments, generate_xml, get_staff
from homr.transformer.vocabulary import EncodedSymbol
class Session:
    def io_binding(self):
        return None
def parse_lines(lines):
    symbols = []
    for line in lines:
        for index, token in enumerate(line.split("&")):
            fields = token.split()
            if len(fields) != 6:
                raise ValueError(f"Expected six token fields: {token}")
            if index:
                symbols.append(EncodedSymbol("chord"))
            symbols.append(EncodedSymbol(*fields))
    return symbols
decoder = ScoreDecoder(Session(), True, False, Config())
positions = [detokenize(np.array([[i]]), decoder.inv_position_vocab)[0] for i in range(3)]
assert positions == [".", "upper", "lower"]
assert get_staff(EncodedSymbol("note_4", position=positions[2])) == 2
cases = {
    "grand": [
        "clef_G2 . . . . upper&clef_F4 . . . . lower",
        "timeSignature/4 . . . . .",
        "note_4 C4 _ _ _ upper&note_4 C3 _ _ _ lower",
        "rest_4 . _ _ _ lower&note_4 D4 _ _ _ upper",
        "barline . . . . .",
    ],
    "voices": [
        "clef_G2 . . . . upper&clef_F4 . . . . lower",
        "timeSignature/4 . . . . .",
        "note_2 C4 _ _ _ upper&note_4 C3 _ _ _ lower",
        "note_4 D3 _ _ _ lower",
        "barline . . . . .",
    ],
    "tie_tuplet": [
        "clef_G2 . . . . upper", "timeSignature/4 . . . . .",
        "note_4 C4 _ _ slurStart upper", "note_4 C4 _ _ slurStop upper",
        "note_12 D4 _ _ _ upper", "note_12 E4 _ _ _ upper",
        "note_12 F4 _ _ _ upper", "barline . . . . .",
    ],
    "pickup_meter": [
        "clef_G2 . . . . upper", "timeSignature/4 . . . . .",
        "note_4 C4 _ _ _ upper", "barline . . . . .",
        "timeSignature/8 . . . . .", "note_8 D4 _ _ _ upper",
        "barline . . . . .",
    ],
}
for name, lines in cases.items():
    xml = generate_xml(XmlGeneratorArguments(), [parse_lines(lines)], name)
    pathlib.Path(sys.argv[2], name + ".musicxml").write_text(ET.tostring(xml, encoding="unicode"))
print(json.dumps({"positions": positions}))
'''
    environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    process = subprocess.run([str(PYTHON), "-B", "-c", script,
                              str(extension.SOURCE), str(tmp_path)], capture_output=True,
                             text=True, timeout=30, env=environment)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout)["positions"] == [".", "upper", "lower"]

    sys.path.insert(0, str((common.WORKSPACE / "Bridge").resolve()))
    from musicxml_normalizer import normalize_musicxml

    expected = {
        "grand": [("C3", 0.0, 1.0, 1), ("C4", 0.0, 1.0, 0), ("D4", 1.0, 1.0, 0)],
        "voices": [("C3", 0.0, 1.0, 1), ("C4", 0.0, 2.0, 0), ("D3", 1.0, 1.0, 1)],
        "tie_tuplet": [("C4", 0.0, 2.0, 0), ("D4", 2.0, 1 / 3, 0),
                        ("E4", 2 + 1 / 3, 1 / 3, 0), ("F4", 2 + 2 / 3, 1 / 3, 0)],
        "pickup_meter": [("C4", 0.0, 1.0, 0), ("D4", 1.0, 0.5, 0)],
    }
    import xml.etree.ElementTree as ET
    for name, events in expected.items():
        path = tmp_path / f"{name}.musicxml"
        root = ET.parse(path).getroot()
        if name == "grand":
            assert {note.findtext("staff") for note in root.iter("note")} == {"1", "2"}
            assert len([note for note in root.iter("note") if note.find("rest") is not None]) == 1
        if name == "tie_tuplet":
            assert [tie.get("type") for tie in root.iter("tie")] == ["start", "stop"]
            assert [item.get("type") for item in root.iter("tuplet")] == ["start", "stop"]
        if name == "pickup_meter":
            assert len(list(root.iter("measure"))) == 2
        score = normalize_musicxml(path, expand_repeats=False)
        observed = [(note.pitch, note.start_beat, note.duration_beats, note.staff_index)
                    for note in score.notes]
        assert len(observed) == len(events)
        for actual, desired in zip(observed, events, strict=True):
            assert actual[0] == desired[0] and actual[3] == desired[3]
            assert actual[1] == pytest.approx(desired[1])
            assert actual[2] == pytest.approx(desired[2])
