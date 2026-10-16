from __future__ import annotations

import json
import sys
from fractions import Fraction
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

from PIL import Image
import pytest

import phase2_zeus_runner
from sheet2play_omr.adapter_contract import sha256_file


def _write_score(path: Path, measure_number: int) -> None:
    path.write_text(
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<score-partwise version='4.0'>"
        "<part-list><score-part id='P1'><part-name>Piano</part-name></score-part></part-list>"
        f"<part id='P1'><measure number='{measure_number}'/></part>"
        "</score-partwise>",
        encoding="utf-8",
    )


def test_stitch_preserves_every_system_measure(tmp_path: Path) -> None:
    first = tmp_path / "first.musicxml"
    second = tmp_path / "second.musicxml"
    output = tmp_path / "score.musicxml"
    _write_score(first, 1)
    _write_score(second, 2)

    phase2_zeus_runner._stitch([first, second], output)

    measures = list(ET.parse(output).getroot().iter("measure"))
    assert [item.attrib["number"] for item in measures] == ["1", "2"]


def _write_note_bearing_system(path: Path, *, second: bool, swapped: bool = False) -> None:
    first_parts = (
        ("P1", "<note><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration><tie type='start'/><type>quarter</type><notations><tied type='start'/></notations></note>"),
        ("P2", "<note><pitch><step>G</step><octave>3</octave></pitch><duration>1</duration><type>quarter</type></note>"),
    )
    second_parts = (
        ("P1", "<note><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration><tie type='stop'/><type>quarter</type><notations><tied type='stop'/></notations></note><note><pitch><step>E</step><octave>4</octave></pitch><duration>1</duration><type>quarter</type></note>"),
        ("P2", "<note><pitch><step>A</step><octave>3</octave></pitch><duration>2</duration><type>half</type></note>"),
    )
    selected = second_parts if second else first_parts
    if swapped:
        selected = tuple(reversed(selected))
    attributes = "" if second else "<attributes><divisions>1</divisions><key><fifths>0</fifths></key><time><beats>3</beats><beat-type>4</beat-type></time></attributes>"
    implicit = "" if second else " implicit='yes'"
    parts = "".join(
        f"<part id='{part_id}'><measure number='{1 if second else 0}'{implicit}>{attributes}{notes}</measure></part>"
        for part_id, notes in selected
    )
    path.write_text(
        "<?xml version='1.0' encoding='utf-8'?><score-partwise version='4.0'>"
        "<part-list><score-part id='P1'><part-name>Upper</part-name></score-part>"
        "<score-part id='P2'><part-name>Lower</part-name></score-part></part-list>"
        + parts + "</score-partwise>", encoding="utf-8",
    )


def test_runner_preserves_part_order_pickup_and_cross_system_tie(tmp_path: Path, monkeypatch) -> None:
    sys.path.insert(0, str(phase2_zeus_runner.WORKSPACE / "Bridge"))
    from musicxml_normalizer import normalize_musicxml

    first = tmp_path / "first.musicxml"
    second = tmp_path / "second.musicxml"
    output = tmp_path / "output"
    _write_note_bearing_system(first, second=False)
    _write_note_bearing_system(second, second=True, swapped=True)

    image = tmp_path / "page.png"
    Image.new("RGB", (20, 20), "white").save(image)
    monkeypatch.setattr(phase2_zeus_runner, "_detect_systems", lambda *_args: [first, second])
    monkeypatch.setattr(phase2_zeus_runner, "_run_upstream",
                        lambda _image, _output, index: (f"LMX-{index}", [first, second][index - 1]))
    phase2_zeus_runner.run(image, output, "integration")
    assert json.loads((output / "native.lmx.json").read_text(encoding="utf-8")) == [
        {"system": 1, "lmx": "LMX-1"}, {"system": 2, "lmx": "LMX-2"},
    ]
    score = normalize_musicxml(output / "score.musicxml", expand_repeats=False,
                               skip_grace_notes=True, force_source=True)
    actual = {(note.midi_pitch, Fraction(note.start_beat), Fraction(note.duration_beats), note.part_index)
              for note in score.notes}
    assert actual == {
        (60, Fraction(0), Fraction(2), 0),
        (64, Fraction(2), Fraction(1), 0),
        (55, Fraction(0), Fraction(1), 1),
        (57, Fraction(1), Fraction(2), 1),
    }


def test_stitch_rejects_changed_part_identity(tmp_path: Path) -> None:
    first = tmp_path / "first.musicxml"
    second = tmp_path / "second.musicxml"
    _write_note_bearing_system(first, second=False)
    _write_note_bearing_system(second, second=True)
    text = second.read_text(encoding="utf-8").replace("<part id='P2'>", "<part id='P3'>")
    second.write_text(text, encoding="utf-8")
    with pytest.raises(RuntimeError, match="part identities changed"):
        phase2_zeus_runner._stitch([first, second], tmp_path / "score.musicxml")


def test_zeus_system_crop_uses_detector_image_coordinates(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source.png"
    Image.new("RGB", (80, 100), "white").save(source)
    temporary = tmp_path / "temporary"
    temporary.mkdir()

    def fake_run(command, **_kwargs):
        assert Path(command[1]).name == "phase2r_detector.py"
        boxes = Path(command[3])
        detector_image = Path(command[4])
        image = Image.new("RGB", (40, 50), "white")
        for y in (10, 30):
            for x in range(5, 35):
                image.putpixel((x, y), (0, 0, 0))
        image.save(detector_image)
        boxes.write_text(json.dumps({
            "coordinate_space": "homr_predictions_preprocessed",
            "source_image": {"sha256": sha256_file(source), "width": 80, "height": 100},
            "detector_image": {"sha256": sha256_file(detector_image), "width": 40, "height": 50},
            "systems": [{"min_y": 5, "max_y": 35}],
        }), encoding="utf-8")
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(phase2_zeus_runner.subprocess, "run", fake_run)
    crops = phase2_zeus_runner._detect_systems(source, temporary, tmp_path / "evidence")
    assert len(crops) == 1
    with Image.open(crops[0]) as crop:
        assert crop.size == (40, 30)
        assert crop.getpixel((10, 5)) == (0, 0, 0)
        assert crop.getpixel((10, 25)) == (0, 0, 0)
    assert sha256_file(tmp_path / "evidence" / "system-0001.png") == sha256_file(crops[0])
