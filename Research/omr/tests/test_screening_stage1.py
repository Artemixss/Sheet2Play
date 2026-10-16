"""Recovery must preserve completed failures and reject partial/corrupted evidence."""
import hashlib
import json
from pathlib import Path

import pytest

from screening_stage1_audit import verify_completed
from screening_stage1_preflight import admission_blockers
from screening_stage1_development import pressure_expired


def fixture_result(tmp_path: Path, status: str = "succeeded"):
    config = {"candidate_id": "shipped_homr", "adapter_id": "direct",
              "source_revision": "frozen"}
    digest = hashlib.sha256(json.dumps(config, sort_keys=True,
                                       separators=(",", ":")).encode()).hexdigest()
    identity = {"item_id": "page", "adapter_config_sha256": digest, "image_sha256": "image"}
    artifacts = []
    for role in ("native", "musicxml", "canonical_events"):
        path = tmp_path / role
        path.write_bytes(b"frozen")
        artifacts.append({"role": role, "path": role, "bytes": 6,
                          "sha256": hashlib.sha256(b"frozen").hexdigest()})
    result = {"schema_version": 1, "item_id": "page", "composition_group": "group",
              "measurement_path": "complete_document", "adapter_config_sha256": digest,
              "candidate_id": "shipped_homr", "adapter_id": "direct", "status": status,
              "provenance": {"adapter_config": config, "input_sha256": "image",
                             "source_revision": "frozen"},
              "artifacts": artifacts, "exit_status": 0 if status == "succeeded" else 1,
              "timings": [{"stage": "recognition", "elapsed_seconds": 1}],
              "error": None if status == "succeeded" else {"code": "TIMEOUT"}}
    path = tmp_path / "report.json"
    path.write_text(json.dumps(result))
    path.with_suffix(".identity.json").write_text(json.dumps(identity))
    return path, identity, result


@pytest.mark.parametrize("status", ["succeeded", "failed"])
def test_completed_outcomes_are_reusable_without_mutation(tmp_path, status):
    path, identity, _ = fixture_result(tmp_path, status)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    checked = verify_completed(path, identity, "group", tmp_path)
    assert checked["status"] == status
    assert checked["artifact_count"] == 3
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


@pytest.mark.parametrize("defect", ["hash", "missing", "sidecar", "pending", "config", "roles"])
def test_rejects_unusable_outcomes(tmp_path, defect):
    path, identity, result = fixture_result(tmp_path)
    if defect == "hash":
        (tmp_path / "native").write_bytes(b"broken")
    elif defect == "missing":
        (tmp_path / "native").unlink()
    elif defect == "sidecar":
        path.with_suffix(".identity.json").write_text("{}")
    else:
        if defect == "pending":
            result["status"] = "pending"
        elif defect == "config":
            result["provenance"]["adapter_config"]["source_revision"] = "changed"
        else:
            result["artifacts"] = []
        path.write_text(json.dumps(result))
    with pytest.raises(ValueError):
        verify_completed(path, identity, "group", tmp_path)


@pytest.mark.parametrize("ram,gpu,blocked", [(70, 89.9, False), (89.9, 0, False),
                                           (90, 0, True),
                                           (0, 90, True), (20, None, True)])
def test_admission_thresholds_fail_closed(ram, gpu, blocked):
    assert bool(admission_blockers(ram, gpu)) is blocked


@pytest.mark.parametrize("ram,gpu", [(float("nan"), 0), (20, -1), (101, 0)])
def test_rejects_invalid_resource_measurement(ram, gpu):
    with pytest.raises(ValueError):
        admission_blockers(ram, gpu)


def test_pressure_requires_thirty_continuous_seconds_and_resets():
    since, expired = pressure_expired(100, None, True)
    assert (since, expired) == (100, False)
    assert pressure_expired(129.9, since, True) == (100, False)
    assert pressure_expired(130, since, True) == (100, True)
    assert pressure_expired(120, since, False) == (None, False)
    assert pressure_expired(130, None, True) == (130, False)


@pytest.mark.parametrize("reason", ["resource_interruption", "session_limit"])
def test_interrupted_worker_is_pending_even_with_a_staged_result(tmp_path, monkeypatch, reason):
    import screening_stage1_development as development
    clock = [0.0]
    stopped = []

    class Process:
        pid = 123
        returncode = None

        def poll(self):
            return self.returncode

        def wait(self, timeout):
            self.returncode = 1

        def create_time(self):
            return 123.0

        def exe(self):
            return "fixture-python"

    process = Process()

    def spawn(*args, **kwargs):
        (tmp_path / "page/candidate-result.json").write_text(json.dumps({"status": "succeeded"}))
        return process

    def stop(root):
        stopped.append(root.pid)
        root.returncode = 1

    sample = {"admission_blockers": ["ram"] if reason == "resource_interruption" else [],
              "ram_percent": 80, "device_wide_gpu": [{"used_mib": 100}]}
    monkeypatch.setattr(development.subprocess, "Popen", spawn)
    monkeypatch.setattr(development.psutil, "Process", lambda pid: process)
    monkeypatch.setattr(development, "resource_sample", lambda: dict(sample))
    monkeypatch.setattr(development, "stop_tree", stop)
    monkeypatch.setattr(development.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(development.time, "sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    monkeypatch.setattr(Process, "memory_info", lambda self: type("Memory", (), {"rss": 100})(), raising=False)
    monkeypatch.setattr(Process, "children", lambda self, recursive: [], raising=False)
    outcome = development.run_page(tmp_path / "page", 0, 14400 if reason == "resource_interruption" else 30)
    assert outcome["status"] == "pending"
    assert outcome["reason"] == reason
    assert stopped == [123]
    assert "report_sha256" not in outcome
    assert (tmp_path / "page/candidate-result.json").is_file()
