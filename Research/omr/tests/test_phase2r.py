from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from sheet2play_omr.adapter_contract import (
    AdapterConfig, AdapterInput, MeasurementPath, RunStatus, sha256_file, unavailable_result,
)
from sheet2play_omr.errors import ResearchError
from sheet2play_omr.phase2r_validation import (
    failure_penalized_composition_macro, record_attempt_measurement, require_complete_systems,
    run_with_typed_failure,
)
from sheet2play_omr.phase2r_vlm import (
    convert_abc, crop_detected_systems, extract_abc, merge_system_abc, stitch_musicxml,
)
from sheet2play_omr.phase2r_detector import save_detection
from sheet2play_omr.phase2r_development import development_records
from sheet2play_omr.phase2_adapters import _prepare_audiveris_input


@pytest.fixture
def abc_converter() -> Path:
    executable = Path(__file__).resolve().parents[1] / ".runtime" / "phase2r" / "croma" / "croma-windows-x86_64.exe"
    if not executable.is_file():
        pytest.skip("Pinned croma converter is not installed")
    return executable


def _input(tmp_path: Path) -> tuple[AdapterConfig, AdapterInput]:
    image = tmp_path / "system.png"
    image.write_bytes(b"fixture")
    config = AdapterConfig(
        "fixture", "fixture-vlm", "test", "https://example.invalid/source", "revision",
        None, None, "ABC", "system", (MeasurementPath.ANNOTATED_CROP,),
    )
    item = AdapterInput("item", "composition", image, sha256_file(image), MeasurementPath.ANNOTATED_CROP)
    return config, item


def test_detector_image_contract_handles_autocrop_and_resize(tmp_path: Path) -> None:
    import cv2
    import numpy as np

    source_path = tmp_path / "source.png"
    detector_path = tmp_path / "detector.png"
    boxes_path = tmp_path / "boxes.json"
    source = np.full((300, 320, 3), 255, dtype=np.uint8)
    source[120:122, 60:260] = 0
    source[170:172, 60:260] = 0
    assert cv2.imwrite(str(source_path), source)
    # Deliberately combine an x/y autocrop offset with a non-unit resize.
    preprocessed = cv2.resize(source[80:230, 40:280], (480, 300))
    grand_staff = SimpleNamespace(staffs=[
        SimpleNamespace(min_x=35, max_x=440, min_y=76, max_y=100),
        SimpleNamespace(min_x=35, max_x=440, min_y=176, max_y=200),
    ])
    save_detection(source_path, detector_path, boxes_path, [grand_staff], preprocessed)
    document = json.loads(boxes_path.read_text(encoding="utf-8"))
    assert document["source_image"]["width"] == 320
    assert document["detector_image"]["width"] == 480
    assert document["coordinate_space"] == "homr_predictions_preprocessed"
    crops = crop_detected_systems(detector_path, document, tmp_path / "crops",
                                  source_sha256=sha256_file(source_path))
    manifest = json.loads((tmp_path / "crops" / "crop-manifest.json").read_text(encoding="utf-8"))
    assert len(crops) == 1
    assert manifest["crops"][0]["sha256"] == sha256_file(crops[0])
    with Image.open(crops[0]) as crop:
        assert crop.width == 480
        # The detector-space crop contains both grand-staff lines and all of their width.
        pixels = np.asarray(crop)
        dark_rows = np.where((pixels[:, 50:430] < 20).any(axis=(1, 2)))[0]
        assert dark_rows.min() <= 30
        assert dark_rows.max() > 110


def test_detector_crop_clamps_boundaries_and_rejects_mismatches(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    detector = tmp_path / "detector.png"
    Image.new("RGB", (80, 100), "white").save(source)
    Image.new("RGB", (40, 50), "white").save(detector)
    document = {
        "coordinate_space": "homr_predictions_preprocessed",
        "source_image": {"sha256": sha256_file(source), "width": 80, "height": 100},
        "detector_image": {"sha256": sha256_file(detector), "width": 40, "height": 50},
        "systems": [{"min_y": -4.2, "max_y": 50.3}],
    }
    crops = crop_detected_systems(detector, document, tmp_path / "crops",
                                  source_sha256=sha256_file(source))
    with Image.open(crops[0]) as crop:
        assert crop.size == (40, 50)
    with pytest.raises(ResearchError, match="source"):
        crop_detected_systems(detector, document, tmp_path / "wrong-source",
                              source_sha256="0" * 64)
    with pytest.raises(ResearchError, match="coordinate space"):
        crop_detected_systems(detector, {**document, "coordinate_space": "original"},
                              tmp_path / "wrong-space", source_sha256=sha256_file(source))
    with pytest.raises(ResearchError, match="dimensions"):
        crop_detected_systems(detector, {**document, "detector_image": {
            **document["detector_image"], "height": 100}}, tmp_path / "wrong-dimensions",
            source_sha256=sha256_file(source))


def test_invalid_native_output_propagates_typed_failure_and_zero_f1(tmp_path: Path) -> None:
    config, item = _input(tmp_path)

    class Adapter:
        def __init__(self) -> None:
            self.config = config

        def run(self, _item: AdapterInput, _output: Path):
            extract_abc("No notation was generated")
            raise AssertionError("Invalid ABC was accepted")

    result = run_with_typed_failure(Adapter(), item, tmp_path / "output")
    assert result.status is RunStatus.FAILED
    assert result.error is not None and result.error["code"] == "INVALID_NOTATION"
    assert failure_penalized_composition_macro([("composition", result, None)]) == 0.0


def test_failed_attempt_retains_elapsed_and_measured_resources(tmp_path: Path) -> None:
    config, item = _input(tmp_path)

    class Adapter:
        def __init__(self) -> None:
            self.config = config

        def run(self, _item: AdapterInput, output: Path):
            record_attempt_measurement(output, stage="recognition_system_1", seconds=2.5,
                                       peak_ram_bytes=1234, peak_vram_bytes=5678,
                                       vram_measurement="device-wide WDDM fallback")
            raise ResearchError("INVALID_NOTATION", "recognition", "bad output")

    result = run_with_typed_failure(Adapter(), item, tmp_path / "failed")
    assert result.status is RunStatus.FAILED
    assert result.timings[0].stage == "total_failed_attempt"
    assert result.timings[0].seconds >= 0
    assert result.timings[1].seconds == 2.5
    assert result.resources.peak_ram_bytes == 1234
    assert result.resources.peak_vram_bytes == 5678


def test_missing_middle_system_is_document_failure(tmp_path: Path) -> None:
    config, item = _input(tmp_path)

    class Adapter:
        def __init__(self) -> None:
            self.config = config

        def run(self, _item: AdapterInput, _output: Path):
            require_complete_systems((1, 2, 3), (1, 3))
            raise AssertionError("Missing system was accepted")

    result = run_with_typed_failure(Adapter(), item, tmp_path / "output")
    assert result.status is RunStatus.FAILED
    assert result.error is not None and result.error["code"] == "MISSING_SYSTEM"
    assert result.error["stage"] == "stitching"


def test_unavailable_candidate_cannot_be_scored_as_zero(tmp_path: Path) -> None:
    config, item = _input(tmp_path)
    result = unavailable_result(config, item, code="RUNTIME_MISSING", message="missing", probe={})
    with pytest.raises(ValueError, match="Unavailable candidates"):
        failure_penalized_composition_macro([("composition", result, None)])


def test_abc_to_musicxml_then_ordered_join_preserves_two_systems(tmp_path: Path, abc_converter: Path) -> None:
    abc_1 = "X:1\nM:4/4\nL:1/4\nK:C\nC D E F|\n"
    abc_2 = "X:1\nM:4/4\nL:1/4\nK:C\nG A B c|\n"
    first = tmp_path / "first.musicxml"
    second = tmp_path / "second.musicxml"
    joined = tmp_path / "joined.musicxml"
    convert_abc(extract_abc(abc_1), first, abc_converter)
    convert_abc(extract_abc(abc_2), second, abc_converter)
    stitch_musicxml([first, second], joined)
    from music21 import converter

    score = converter.parse(str(joined))
    pitches = [note.pitch.nameWithOctave for note in score.recurse().notes]
    assert pitches == ["C4", "D4", "E4", "F4", "G4", "A4", "B4", "C5"]
    assert len(list(score.recurse().getElementsByClass("Measure"))) == 2


def test_abc_conversion_keeps_tuplets_ties_voices_and_meter(tmp_path: Path, abc_converter: Path) -> None:
    abc = (
        "X:1\nM:4/4\nL:1/8\nK:C\n"
        "V:1 clef=treble\n(3CDE F2 G2 A2 | [M:3/4] B2 c2-c2 |\n"
        "V:2 clef=bass\nC,2 D,2 E,2 F,2 | G,2 A,2 B,2 |\n"
    )
    destination = tmp_path / "features.musicxml"
    convert_abc(extract_abc(abc), destination, abc_converter)
    from music21 import converter

    score = converter.parse(str(destination))
    assert len(list(score.recurse().notes)) >= 12
    assert any(note.tie is not None for note in score.recurse().notes)
    assert any(note.duration.tuplets for note in score.recurse().notes)
    assert {str(item.ratioString) for item in score.recurse().getElementsByClass("TimeSignature")} >= {"4/4", "3/4"}


def test_join_preserves_meter_change_at_system_boundary(tmp_path: Path, abc_converter: Path) -> None:
    first = tmp_path / "first.musicxml"
    second = tmp_path / "second.musicxml"
    joined = tmp_path / "joined.musicxml"
    convert_abc("X:1\nM:4/4\nL:1/4\nK:C\nCDEF|\n", first, abc_converter)
    convert_abc("X:1\nM:3/4\nL:1/4\nK:C\nGAB|\n", second, abc_converter)
    stitch_musicxml([first, second], joined)
    from music21 import converter

    score = converter.parse(str(joined))
    meters = [item.ratioString for item in score.recurse().getElementsByClass("TimeSignature")]
    assert meters == ["4/4", "3/4"]
    assert len(list(score.recurse().notes)) == 7


def test_abc_merge_preserves_tie_across_system_boundary(tmp_path: Path, abc_converter: Path) -> None:
    first = "X:1\nM:4/4\nL:1/4\nK:C\nC2 D2- |]\n"
    second = "X:1\nM:4/4\nL:1/4\nK:C\nD2 E2 |]\n"
    destination = tmp_path / "merged.musicxml"
    convert_abc(merge_system_abc([first, second]), destination, abc_converter)
    from sheet2play_omr.phase2_adapters import _canonicalize

    canonical = tmp_path / "events.json"
    _canonicalize(destination, canonical)
    notes = json.loads(canonical.read_text(encoding="utf-8"))["notes"]
    assert len(notes) == 3
    assert any(note["midi_pitch"] == 62 and float(note["duration"]) == 4.0 for note in notes)


def test_abc_merge_keeps_voices_and_inherited_meter(tmp_path: Path, abc_converter: Path) -> None:
    first = (
        "X:1\nM:4/4\nL:1/4\nK:C\nV:1 clef=treble\nV:2 clef=bass\n"
        "[V:1] C D E F |]\n[V:2] C, D, E, F, |]\n"
    )
    second = (
        "X:1\nM:3/4\nL:1/4\nK:G\nV:1 clef=treble\nV:2 clef=bass\n"
        "[V:1] G A B |]\n[V:2] G, A, B, |]\n"
    )
    destination = tmp_path / "merged.musicxml"
    convert_abc(merge_system_abc([first, second]), destination, abc_converter)
    from music21 import converter

    score = converter.parse(str(destination))
    assert len(list(score.recurse().notes)) == 14
    assert {item.ratioString for item in score.recurse().getElementsByClass("TimeSignature")} >= {"4/4", "3/4"}


def test_abc_merge_rejects_changed_voice_identity() -> None:
    first = "X:1\nM:4/4\nL:1/4\nK:C\nV:1 clef=treble\n[V:1] CDEF |]\n"
    second = "X:1\nM:4/4\nL:1/4\nK:C\nV:2 clef=treble\n[V:2] GABc |]\n"
    with pytest.raises(ResearchError, match="Voice identities"):
        merge_system_abc([first, second])


def test_truncated_abc_is_rejected() -> None:
    with pytest.raises(ResearchError, match="closing barline"):
        extract_abc("X:1\nM:4/4\nL:1/4\nK:C\nCDEF|\nGAB")


def test_frozen_development_roster_is_complete_and_disjoint() -> None:
    workspace = Path(__file__).resolve().parents[3]
    records = development_records(workspace)
    assert len(records) == 32
    assert sum(record.collection == "generated" for record in records) == 12
    assert sum(record.collection == "open" for record in records) == 20
    assert len({record.composition_group for record in records if record.collection == "open"}) == 20
    assert all(record.page_images for record in records)


def test_audiveris_preprocessing_scales_small_image_without_mutating_source(tmp_path: Path) -> None:
    source = tmp_path / "small.png"
    Image.new("RGB", (1050, 1485), "white").save(source)
    original_hash = sha256_file(source)
    prepared, scale, elapsed = _prepare_audiveris_input(source, tmp_path)
    assert scale == 2 and elapsed >= 0
    assert prepared != source and sha256_file(source) == original_hash
    with Image.open(prepared) as image:
        assert image.size == (2100, 2970)
        assert image.info["dpi"] == pytest.approx((300, 300), abs=1)


def test_audiveris_preprocessing_keeps_large_image(tmp_path: Path) -> None:
    source = tmp_path / "page.png"
    Image.new("RGB", (2480, 3509), "white").save(source)
    prepared, scale, _ = _prepare_audiveris_input(source, tmp_path)
    assert prepared == source and scale == 1
