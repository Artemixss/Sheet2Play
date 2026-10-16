from __future__ import annotations

import json
import sys
from pathlib import Path

import phase2
import pytest
from PIL import Image
from sheet2play_omr.adapter_contract import (
    AdapterConfig,
    AdapterInput,
    AdapterResult,
    Artifact,
    MeasurementPath,
    ResourceMeasurements,
    RunStatus,
    base_provenance,
    sha256_file,
)
from sheet2play_omr import phase2_adapters
from sheet2play_omr.phase2_adapters import (
    AudiverisAdapter,
    CommandResult,
    LegatoAdapter,
    candidate_adapters,
    run_monitored,
)
from sheet2play_omr.phase2_fixtures import run_fixture_matrix


def test_phase1_freeze_is_unchanged() -> None:
    audit = phase2.verify_phase1_freeze()
    assert audit["passed"] is True
    assert audit["hash_mismatches"] == []


def test_frozen_fixture_matrix_passes_every_case() -> None:
    outcomes = run_fixture_matrix()
    assert len(outcomes) == 14
    assert {item.name for item in outcomes} == {
        "identical score",
        "omitted note",
        "inserted note",
        "shifted onsets",
        "tied versus sustained equivalent",
        "overlapping voices",
        "tuplets",
        "pickup",
        "meter change",
        "repeats",
        "empty output",
        "malformed XML",
        "missing middle system",
        "source MusicXML to app control",
    }
    assert all(item.passed for item in outcomes)


def test_adapter_configs_are_unique_and_provenance_pinned() -> None:
    adapters = candidate_adapters(phase2.WORKSPACE)
    identifiers = [adapter.config.adapter_id for adapter in adapters]
    assert len(identifiers) == len(set(identifiers))
    assert identifiers[0] == "shipped_homr_direct"
    assert {adapter.config.candidate_id for adapter in adapters} == {
        "shipped_homr",
        "zeus",
        "legato",
        "audiveris",
    }
    for adapter in adapters:
        assert len(adapter.config.source_revision) >= 40
        assert len(adapter.config.sha256) == 64
        assert adapter.config.supported_paths


def test_development_inputs_are_hash_verified_and_not_evaluation_items() -> None:
    crop, document = phase2.development_inputs()
    crop.validate()
    document.validate()
    assert crop.measurement_path is MeasurementPath.ANNOTATED_CROP
    assert document.measurement_path is MeasurementPath.COMPLETE_DOCUMENT
    assert "phase1-development" in document.input_path.as_posix()
    assert "smb" not in crop.input_path.as_posix().casefold()
    assert "olimpic" not in crop.input_path.as_posix().casefold()


def test_success_contract_rejects_missing_required_artifacts(tmp_path: Path) -> None:
    source = tmp_path / "input.png"
    source.write_bytes(b"image")
    config = AdapterConfig(
        "fixture",
        "fixture-adapter",
        "v1",
        "https://example.invalid/repository",
        "a" * 40,
        None,
        None,
        "tokens",
        "system",
        (MeasurementPath.ANNOTATED_CROP,),
    )
    item = AdapterInput(
        "item",
        "composition",
        source,
        sha256_file(source),
        MeasurementPath.ANNOTATED_CROP,
    )
    result = AdapterResult(
        1,
        config.candidate_id,
        config.adapter_id,
        config.sha256,
        item.item_id,
        item.composition_group,
        item.measurement_path,
        RunStatus.SUCCEEDED,
        0,
        (),
        (),
        ResourceMeasurements(None, None, None, True),
        (),
        base_provenance(config, item),
    )
    with pytest.raises(ValueError, match="missing artifacts"):
        result.validate()


def test_phase2_report_never_claims_phase3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(phase2, "REPORT_DIRECTORY", tmp_path / "phase2")
    report = phase2.execute(run_inference=False)
    assert report["status"] == "passed"
    assert report["scope"]["phase_3_started"] is False
    assert report["scope"]["smb_inference_count"] == 0
    checklist = json.loads(
        (phase2.REPORT_DIRECTORY / "phase2-plan-checklist.json").read_text(encoding="utf-8")
    )
    assert next(
        row["status"] for row in checklist if row["requirement"] == "frozen evaluation inference"
    ) == "not_started_phase_3"


def test_monitor_does_not_deadlock_on_large_engine_output(tmp_path: Path) -> None:
    result = run_monitored(
        [
            sys.executable,
            "-c",
            "import sys; sys.stdout.write('x' * 200000); sys.stderr.write('y' * 200000)",
        ],
        cwd=tmp_path,
        timeout_seconds=10,
    )
    assert result.exit_status == 0
    assert result.timed_out is False
    assert len(result.stdout) == 200000
    assert len(result.stderr) == 200000


def test_console_redaction_handles_plain_and_repr_escaped_paths() -> None:
    temporary = str(Path.home() / "AppData" / "Local" / "Temp")
    text = temporary + "\\input.png " + temporary.replace("\\", "\\\\") + "\\\\input.png"

    redacted = phase2_adapters._portable_text(text)

    assert str(Path.home()) not in redacted
    assert str(Path.home()).replace("\\", "\\\\") not in redacted
    assert redacted.count("${TEMP}") == 2


def _fake_canonicalize(musicxml: Path, destination: Path):
    assert musicxml.is_file()
    destination.write_text('{"notes":[{"pitch":60}]}\n', encoding="utf-8")
    return Artifact.from_path("canonical_events", destination, "application/json"), (), 0.01


def test_legato_execution_branch_preserves_all_artifact_layers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "input.png"
    source.write_bytes(b"image")
    root = tmp_path / "legato"
    (root / "scripts").mkdir(parents=True)
    (root / "utils").mkdir()
    (root / "scripts" / "inference.py").write_text("", encoding="utf-8")
    (root / "utils" / "convert.py").write_text("", encoding="utf-8")
    python = root / "python.exe"
    model = root / "model"
    musescore = root / "musescore.exe"
    python.write_bytes(b"python")
    model.mkdir()
    musescore.write_bytes(b"musescore")
    adapter = LegatoAdapter(phase2.WORKSPACE)
    adapter.root = root
    adapter.python = python
    adapter.model = model
    adapter.musescore = musescore

    def fake_run(command, **_):
        command = list(command)
        if "--output_path" in command:
            Path(command[command.index("--output_path") + 1]).write_text(
                json.dumps({"abc_transcription": ["X:1\nK:C\nC|"], "tokens": [[1]]}),
                encoding="utf-8",
            )
        else:
            Path(command[command.index("--output") + 1]).write_text(
                "<score-partwise/>", encoding="utf-8"
            )
        return CommandResult(0, 0.1, "", "", 100, 200, "per-process", False)

    monkeypatch.setattr(phase2_adapters, "run_monitored", fake_run)
    monkeypatch.setattr(phase2_adapters, "_canonicalize", _fake_canonicalize)
    item = AdapterInput(
        "item",
        "composition",
        source,
        sha256_file(source),
        MeasurementPath.COMPLETE_DOCUMENT,
    )

    result = adapter.run(item, tmp_path / "output")

    assert result.status is RunStatus.SUCCEEDED
    assert {artifact.role for artifact in result.artifacts} >= {
        "native",
        "musicxml",
        "canonical_events",
    }


def test_audiveris_execution_branch_preserves_native_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "input.png"
    Image.new("RGB", (1050, 1485), "white").save(source)
    executable = tmp_path / "Audiveris.exe"
    executable.write_bytes(b"executable")
    adapter = AudiverisAdapter(phase2.WORKSPACE)
    adapter.executable = executable

    def fake_run(_command, *, cwd: Path, **_):
        engine_output = cwd / "audiveris-output"
        (engine_output / "score.omr").write_bytes(b"omr")
        (engine_output / "score.mxl").write_bytes(b"mxl")
        return CommandResult(0, 0.1, "ok", "", 100, 200, "per-process", False)

    monkeypatch.setattr(phase2_adapters, "run_monitored", fake_run)
    monkeypatch.setattr(phase2_adapters, "_canonicalize", _fake_canonicalize)
    item = AdapterInput(
        "item",
        "composition",
        source,
        sha256_file(source),
        MeasurementPath.COMPLETE_DOCUMENT,
    )

    result = adapter.run(item, tmp_path / "output")

    assert result.status is RunStatus.SUCCEEDED
    assert next(artifact for artifact in result.artifacts if artifact.role == "native").bytes == 3
    assert next(artifact for artifact in result.artifacts if artifact.role == "prepared_input").bytes > 0
    assert result.provenance["input_scale"] == 2


def test_audiveris_failure_preserves_partial_project_and_engine_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "input.png"
    Image.new("RGB", (1050, 1485), "white").save(source)
    executable = tmp_path / "Audiveris.exe"
    executable.write_bytes(b"executable")
    adapter = AudiverisAdapter(phase2.WORKSPACE)
    adapter.executable = executable

    def fake_run(_command, *, cwd: Path, **_):
        (cwd / "audiveris-output" / "score.omr").write_bytes(b"partial project")
        return CommandResult(1, 0.1, "transcription stopped", "failure", 100, None, "unavailable", False)

    monkeypatch.setattr(phase2_adapters, "run_monitored", fake_run)
    item = AdapterInput(
        "item", "composition", source, sha256_file(source), MeasurementPath.COMPLETE_DOCUMENT,
    )
    result = adapter.run(item, tmp_path / "output")

    assert result.status is RunStatus.FAILED
    assert result.error is not None and result.error["code"] == "AUDIVERIS_FAILED"
    assert {artifact.path for artifact in result.artifacts} >= {
        phase2_adapters.portable_path(tmp_path / "output" / "engine.log"),
        phase2_adapters.portable_path(tmp_path / "output" / "audiveris-output" / "score.omr"),
    }
    assert result.provenance["input_scale"] == 2
