"""The app's guarded runner: recovering the job lock a killed conversion left behind."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import psutil
import pytest

BRIDGE_DIRECTORY = Path(__file__).resolve().parents[1]
if str(BRIDGE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(BRIDGE_DIRECTORY))

from execution_safety.safety_policy import SafetyLimits  # noqa: E402

# Research/omr has its own guarded_execution module, so load the Bridge copy by path.
_SPEC = importlib.util.spec_from_file_location(
    "bridge_guarded_execution", BRIDGE_DIRECTORY / "guarded_execution.py")
guarded_execution = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(guarded_execution)

GIB = 1024**3


def _safe_sample():
    return {"committed_bytes": 10 * GIB, "commit_limit_bytes": 32 * GIB,
            "physical_percent": 50.0, "git_count": 0, "git_private_bytes": 0}


@pytest.fixture
def run_job(tmp_path, monkeypatch):
    if os.name != "nt":
        pytest.skip("Native Windows containment")
    monkeypatch.setattr(guarded_execution, "process_evidence", lambda: {"fixture": True})

    def run(*, reclaim_dead_owner=True):
        return guarded_execution.run_guarded(
            [sys.executable, "-B", "-c", "print('finished')"], tmp_path, tmp_path / "run",
            SafetyLimits(worker_bytes=64 * 1024**2, max_seconds=15), sampler=_safe_sample,
            lock_path=tmp_path / ".worker.lock", reclaim_dead_owner=reclaim_dead_owner)
    return run


def _dead_pid() -> int:
    process = subprocess.Popen([sys.executable, "-c", "pass"])
    process.wait(timeout=15)
    return process.pid


def _write_lock(tmp_path, pid: int, *, owner_finished=False) -> dict:
    owner = {"supervisor_pid": pid, "output": str(tmp_path / "killed")}
    (tmp_path / "killed").mkdir()
    if owner_finished:
        (tmp_path / "killed/result.json").write_text("{}")
    (tmp_path / ".worker.lock").write_text(json.dumps(owner), encoding="utf-8")
    return owner


def _assert_blocked_by(tmp_path, result, lock_text):
    assert result["status"] == "blocked"
    assert "FileExistsError" in result["stop_reason"]
    assert result["worker_pid"] is None
    assert (tmp_path / ".worker.lock").read_text(encoding="utf-8") == lock_text


def test_lock_of_killed_supervisor_is_reclaimed(run_job, tmp_path):
    owner = _write_lock(tmp_path, _dead_pid())
    result = run_job()
    assert result["status"] == "complete"
    assert result["reclaimed_lock"] == owner
    assert not (tmp_path / ".worker.lock").exists()
    assert list(tmp_path.glob(".worker.lock*")) == []
    assert (tmp_path / "killed").is_dir()


def test_reused_owner_pid_does_not_hold_the_lock(run_job, tmp_path):
    owner = _write_lock(tmp_path, os.getpid())
    os.utime(tmp_path / ".worker.lock", (946684800, 946684800))
    result = run_job()
    assert result["status"] == "complete"
    assert result["reclaimed_lock"] == owner


def test_live_supervisor_keeps_its_lock(run_job, tmp_path):
    _write_lock(tmp_path, os.getpid())
    text = (tmp_path / ".worker.lock").read_text(encoding="utf-8")
    _assert_blocked_by(tmp_path, run_job(), text)


def test_lock_kept_after_finished_supervisor_is_not_reclaimed(run_job, tmp_path):
    _write_lock(tmp_path, _dead_pid(), owner_finished=True)
    text = (tmp_path / ".worker.lock").read_text(encoding="utf-8")
    _assert_blocked_by(tmp_path, run_job(), text)


def test_live_bridge_worker_keeps_the_lock(run_job, tmp_path):
    _write_lock(tmp_path, _dead_pid())
    text = (tmp_path / ".worker.lock").read_text(encoding="utf-8")
    orphan = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)",
                               str(BRIDGE_DIRECTORY / "guarded_worker.py")])
    try:
        _assert_blocked_by(tmp_path, run_job(), text)
    finally:
        orphan.kill()
        orphan.wait(timeout=15)


@pytest.mark.parametrize("text", ["existing worker", '{"output": "x"}'])
def test_lock_with_unknown_owner_is_not_removed(run_job, tmp_path, text):
    (tmp_path / ".worker.lock").write_text(text, encoding="utf-8")
    _assert_blocked_by(tmp_path, run_job(), text)


def test_reclaim_is_opt_in(run_job, tmp_path):
    _write_lock(tmp_path, _dead_pid())
    text = (tmp_path / ".worker.lock").read_text(encoding="utf-8")
    _assert_blocked_by(tmp_path, run_job(reclaim_dead_owner=False), text)
