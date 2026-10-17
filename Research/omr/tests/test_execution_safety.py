import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

import psutil
import pytest

import guarded_execution
from sheet2play_omr.execution_resources import WindowsResourceSampler, _GitTelemetry
from sheet2play_omr.safety_policy import GIB, SafetyLimits, admission_reason, blocking_reason
from sheet2play_omr.windows_job import (
    WindowsJob, _BasicLimitInformation, _ExtendedLimitInformation, _IoCounters,
)


def _safe_sample(**changes):
    return {"committed_bytes": 10 * GIB, "commit_limit_bytes": 32 * GIB,
            "physical_percent": 50.0, "git_count": 0, "git_private_bytes": 0, **changes}


def test_worker_progress_is_visible_before_pipe_closes(tmp_path):
    read_descriptor, write_descriptor = os.pipe()
    reader_pipe = os.fdopen(read_descriptor, "rb")
    writer_pipe = os.fdopen(write_descriptor, "wb", buffering=0)
    destination = tmp_path / "progress.log"
    errors = []
    reader = threading.Thread(target=guarded_execution._output_reader,
        args=(reader_pipe, destination, errors), daemon=True)
    reader.start()
    try:
        writer_pipe.write(b"live progress\n")
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if destination.exists() and destination.read_bytes() == b"live progress\n":
                break
            time.sleep(0.01)
        assert destination.read_bytes() == b"live progress\n"
        assert reader.is_alive() and not errors
    finally:
        writer_pipe.close()
        reader.join(timeout=2)
        reader_pipe.close()
    assert not reader.is_alive() and not errors


@pytest.mark.parametrize("changes,expected", [
    ({"committed_bytes": 85 * GIB, "commit_limit_bytes": 100 * GIB}, "system_commit_at_or_above_85_percent"),
    ({"committed_bytes": 7 * GIB, "commit_limit_bytes": 11 * GIB - 1}, "system_commit_headroom_below_required_reserve"),
    ({"physical_percent": 85}, "physical_RAM_at_or_above_85_percent"),
])
def test_pressure_boundaries(changes, expected):
    assert blocking_reason(_safe_sample(**changes), 0, SafetyLimits()) == expected


def test_admission_reserves_budget_and_continuous_checks_allow_exact_headroom():
    limits = SafetyLimits(worker_bytes=4 * GIB)
    sample = _safe_sample(committed_bytes=24 * GIB)
    assert admission_reason(sample, limits) is None
    assert admission_reason({**sample, "committed_bytes": 24 * GIB + 1}, limits) == "insufficient_commit_headroom_for_worker_budget"
    assert blocking_reason(_safe_sample(committed_bytes=7 * GIB, commit_limit_bytes=11 * GIB), 0, limits) is None
    assert blocking_reason(_safe_sample(), limits.max_seconds, limits) == "session_deadline"


def test_worker_cap_is_optional_and_unbounded_by_default():
    assert SafetyLimits().worker_bytes is None
    assert SafetyLimits(worker_bytes=8 * GIB).worker_bytes == 8 * GIB
    # Without a cap, admission needs only the system reserve that blocking_reason enforces.
    assert admission_reason(_safe_sample(committed_bytes=24 * GIB + 1), SafetyLimits()) is None


@pytest.mark.parametrize("count", [8, 15, 108, 150])
@pytest.mark.parametrize("private_bytes", [193_000_000, GIB, 3 * GIB])
def test_git_activity_without_system_memory_pressure_is_observed_only(count, private_bytes):
    sample = _safe_sample(git_count=count, git_private_bytes=private_bytes)
    assert admission_reason(sample, SafetyLimits()) is None
    assert blocking_reason(sample, 30, SafetyLimits()) is None


@pytest.mark.parametrize("changes", [
    {"committed_bytes": True}, {"commit_limit_bytes": 0}, {"physical_percent": float("nan")},
    {"physical_percent": 101}, {"git_count": 1.5}, {"git_private_bytes": -1},
])
def test_invalid_measurements_fail_closed(changes):
    with pytest.raises(ValueError):
        blocking_reason(_safe_sample(**changes), 0, SafetyLimits())


@pytest.mark.parametrize("changes", [
    {"max_seconds": True}, {"max_seconds": 14400}, {"max_seconds": float("inf")},
    {"worker_bytes": 32 * 1024**2}, {"worker_bytes": True}, {"active_processes": 0},
    {"system_stop_percent": 91}, {"system_stop_percent": True},
    {"commit_headroom_bytes": GIB}, {"commit_headroom_bytes": 9 * GIB},
])
def test_invalid_limits(changes):
    with pytest.raises(ValueError):
        SafetyLimits(**changes)


def test_slow_git_scan_does_not_delay_fresh_pressure_sample():
    started, release = threading.Event(), threading.Event()

    def slow_scan():
        started.set()
        release.wait(5)
        return {"git_count": 620, "git_private_bytes": 11 * GIB, "git_processes": []}

    sampler = WindowsResourceSampler.__new__(WindowsResourceSampler)
    sampler._git_telemetry = _GitTelemetry(slow_scan)

    def query(pointer, size):
        info = pointer._obj
        info.CommitTotal, info.CommitLimit = 10, 32
        info.PhysicalTotal, info.PhysicalAvailable, info.PageSize = 100, 15, GIB
        return 1

    sampler._query = query
    try:
        sampler()
        assert started.wait(1)
        before = time.monotonic()
        sample = sampler()
        assert time.monotonic() - before < 0.5
        assert sample["git_scan_in_progress"]
        assert sample["git_telemetry_state"] == "pending"
        assert blocking_reason(sample, 0, SafetyLimits()) == "physical_RAM_at_or_above_85_percent"
    finally:
        release.set()


def test_git_telemetry_failure_is_explicit_and_does_not_block_snapshots():
    failed = threading.Event()

    def broken_scan():
        failed.set()
        raise MemoryError("fixture")

    telemetry = _GitTelemetry(broken_scan)
    telemetry.snapshot()
    assert failed.wait(1)
    deadline = time.monotonic() + 1
    while telemetry.snapshot()["git_scan_in_progress"] and time.monotonic() < deadline:
        time.sleep(0.01)
    sample = telemetry.snapshot()
    assert sample["git_telemetry_state"] == "error"
    assert sample["git_telemetry_error"] == "MemoryError"
    assert sample["git_observed_utc"] is None


@pytest.fixture
def run_worker(tmp_path, monkeypatch):
    if os.name != "nt":
        pytest.skip("Native Windows containment")
    monkeypatch.setattr(guarded_execution, "process_evidence", lambda: {"fixture": True})

    def run(code, *, sampler=None, job_factory=WindowsJob, seconds=15, memory_mib=64):
        return guarded_execution.run_guarded(
            [sys.executable, "-B", "-c", code], tmp_path, tmp_path / "run",
            SafetyLimits(worker_bytes=memory_mib * 1024**2, max_seconds=seconds),
            sampler=sampler or _safe_sample, job_factory=job_factory, lock_path=tmp_path / "lock")
    return run


def _assert_closed(tmp_path, result):
    saved = json.loads((tmp_path / "run/result.json").read_text())
    assert saved["status"] == result["status"]
    assert not (tmp_path / "lock").exists()
    pid = result["worker_pid"]
    assert pid is None or not psutil.pid_exists(pid)


def test_running_worker_survives_git_burst_below_system_memory_limits(run_worker, tmp_path):
    calls = 0
    def sample():
        nonlocal calls
        calls += 1
        return _safe_sample(git_count=150 if calls >= 4 else 0, git_private_bytes=3 * GIB)
    result = run_worker("import time; time.sleep(1); print('completed')", sampler=sample)
    assert result["status"] == "complete" and result["worker_exit_code"] == 0
    assert result["peak_git_count"] == 150
    assert result["peak_git_private_bytes"] == 3 * GIB
    assert result["git_private_memory_policy"].startswith("record_only")
    assert "completed" in (tmp_path / "run/worker.log").read_text()
    _assert_closed(tmp_path, result)


def test_admission_denial_never_starts_work(run_worker, tmp_path):
    result = run_worker("open('started', 'w').write('unsafe')", sampler=lambda: _safe_sample(physical_percent=90))
    assert result["status"] == "blocked"
    assert result["worker_pid"] is None
    assert not (tmp_path / "started").exists()
    _assert_closed(tmp_path, result)


def test_pressure_before_gate_denies_work(run_worker, tmp_path):
    samples = iter([_safe_sample(), _safe_sample(physical_percent=90)])
    result = run_worker("open('started', 'w').write('unsafe')", sampler=lambda: next(samples))
    assert result["status"] == "blocked"
    assert "physical_RAM" in result["stop_reason"]
    assert not (tmp_path / "started").exists()
    _assert_closed(tmp_path, result)


def test_failed_job_assignment_never_releases_gate(run_worker, tmp_path):
    class RefusedJob:
        closed = True

        def __init__(self, *args):
            pass

        def __enter__(self):
            return self

        def assign(self, pid):
            raise OSError("fixture job assignment denied")

        def __exit__(self, *args):
            return False

    result = run_worker("open('started', 'w').write('unsafe')", job_factory=RefusedJob)
    assert result["status"] == "blocked"
    assert "assignment denied" in result["stop_reason"]
    assert not (tmp_path / "started").exists()
    _assert_closed(tmp_path, result)


def test_real_job_rejects_small_over_budget_allocation(run_worker, tmp_path):
    result = run_worker("try:\n b = bytearray(128 * 1024**2)\nexcept MemoryError:\n print('contained-memory-error')\n raise SystemExit(77)\nraise SystemExit(9)")
    assert result["status"] == "failed"
    assert result["worker_exit_code"] == 77
    assert "contained-memory-error" in (tmp_path / "run/worker.log").read_text()
    _assert_closed(tmp_path, result)


def test_sampling_failure_stops_worker_and_preserves_evidence(run_worker, tmp_path):
    calls = 0

    def sample():
        nonlocal calls
        calls += 1
        if calls >= 4:
            raise OSError("fixture counter query failed")
        return _safe_sample()

    result = run_worker("import time; time.sleep(30)", sampler=sample)
    assert result["status"] == "blocked"
    assert "counter query failed" in result["stop_reason"]
    assert result["peak_commit_percent"] == pytest.approx(31.25)
    assert (tmp_path / "run/resources.jsonl").stat().st_size > 0
    _assert_closed(tmp_path, result)


def test_diagnostic_capture_error_preserves_primary_abort(run_worker, tmp_path, monkeypatch):
    def evidence():
        raise OSError("fixture diagnostic query failed")

    monkeypatch.setattr(guarded_execution, "process_evidence", evidence)
    result = run_worker("print('unsafe')", sampler=lambda: _safe_sample(physical_percent=90))
    assert "physical_RAM" in result["stop_reason"]
    assert "diagnostic query failed" in result["stop_process_evidence"]["capture_error"]
    _assert_closed(tmp_path, result)


@pytest.mark.parametrize("changes,expected", [
    ({"physical_percent": 90}, "physical_RAM"),
    ({"committed_bytes": 90 * GIB, "commit_limit_bytes": 100 * GIB}, "commit_at_or_above"),
])
def test_continuous_pressure_stops_running_worker(run_worker, tmp_path, changes, expected):
    calls = 0

    def sample():
        nonlocal calls
        calls += 1
        return _safe_sample(**(changes if calls >= 4 else {}))

    result = run_worker("import time; open('started','w').write('started'); time.sleep(30)", sampler=sample)
    assert (tmp_path / "started").exists()
    assert result["status"] == "blocked"
    assert expected in result["stop_reason"]
    assert result["final"] == _safe_sample(**changes)
    _assert_closed(tmp_path, result)


def test_pressure_diagnostics_run_after_job_closure(run_worker, tmp_path, monkeypatch):
    jobs = []
    captures = 0
    samples = 0

    class RecordedJob(WindowsJob):
        def __init__(self, *args):
            super().__init__(*args)
            jobs.append(self)

    def evidence():
        nonlocal captures
        captures += 1
        if captures > 1:
            assert jobs[0].closed
        return {"capture": captures}

    def sample():
        nonlocal samples
        samples += 1
        return _safe_sample(physical_percent=85 if samples >= 4 else 50)

    monkeypatch.setattr(guarded_execution, "process_evidence", evidence)
    result = run_worker("import time; time.sleep(30)", sampler=sample, job_factory=RecordedJob)
    assert result["status"] == "blocked"
    assert result["stop_process_evidence"] == {"capture": 2}
    _assert_closed(tmp_path, result)


def test_timeout_stops_worker(run_worker, tmp_path):
    result = run_worker("import time; time.sleep(30)", seconds=1)
    assert result["status"] == "blocked"
    assert "session_deadline" in result["stop_reason"]
    _assert_closed(tmp_path, result)


def test_job_closure_kills_descendants_and_preserves_unrelated_process(run_worker, tmp_path):
    unrelated = subprocess.Popen([sys.executable, "-B", "-c", "import time; time.sleep(30)"],
                                 creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        code = "import subprocess,sys; from pathlib import Path; p=subprocess.Popen([sys.executable,'-B','-c','import time; time.sleep(30)']); Path('descendant').write_text(str(p.pid))"
        result = run_worker(code)
        assert result["status"] == "complete"
        descendant_pid = int((tmp_path / "descendant").read_text())
        deadline = time.monotonic() + 3
        while psutil.pid_exists(descendant_pid) and time.monotonic() < deadline:
            time.sleep(0.05)
        assert not psutil.pid_exists(descendant_pid)
        assert unrelated.poll() is None
        _assert_closed(tmp_path, result)
    finally:
        unrelated.kill()
        unrelated.wait(timeout=3)


def test_existing_lock_is_not_removed(run_worker, tmp_path):
    (tmp_path / "lock").write_text("existing worker")
    result = run_worker("print('unsafe')")
    assert result["status"] == "blocked"
    assert result["worker_pid"] is None
    assert (tmp_path / "lock").read_text() == "existing worker"


def test_late_output_error_cannot_report_success(run_worker, tmp_path, monkeypatch):
    original = guarded_execution._output_reader

    def reader(pipe, destination, errors):
        original(pipe, destination, errors)
        errors.append("fixture late reader failure")

    monkeypatch.setattr(guarded_execution, "_output_reader", reader)
    result = run_worker("print('finished')")
    assert result["status"] == "blocked"
    assert "late reader failure" in result["stop_reason"]
    _assert_closed(tmp_path, result)


def test_secondary_log_failure_preserves_primary_stop(run_worker, tmp_path, monkeypatch):
    original = guarded_execution._output_reader

    def reader(pipe, destination, errors):
        original(pipe, destination, errors)
        errors.append("fixture secondary log failure")

    monkeypatch.setattr(guarded_execution, "_output_reader", reader)
    calls = 0

    def sample():
        nonlocal calls
        calls += 1
        return _safe_sample(physical_percent=90 if calls >= 4 else 50)

    result = run_worker("import time; time.sleep(30)", sampler=sample)
    assert "physical_RAM" in result["stop_reason"]
    assert result["output_errors"] == ["fixture secondary log failure"]
    _assert_closed(tmp_path, result)


@pytest.mark.parametrize("pressure_abort", [False, True])
def test_unconfirmed_job_cleanup_retains_lock(run_worker, tmp_path, pressure_abort):
    class UnconfirmedCloseJob:
        closed = False

        def __init__(self, *args):
            self.real = WindowsJob(*args)

        def __enter__(self):
            self.real.__enter__()
            return self

        def assign(self, pid):
            self.real.assign(pid)

        def __exit__(self, exc_type, exc_value, traceback):
            self.real.close()
            if exc_value is not None:
                exc_value.add_note("fixture Job close unconfirmed")
                return False
            raise OSError("fixture Job close unconfirmed")

    calls = 0

    def sample():
        nonlocal calls
        calls += 1
        return _safe_sample(physical_percent=90 if pressure_abort and calls >= 4 else 50)

    code = "import time; time.sleep(30)" if pressure_abort else "print('finished')"
    result = run_worker(code, sampler=sample, job_factory=UnconfirmedCloseJob)
    assert result["status"] == "blocked"
    assert result["job_cleanup_error"]
    assert (tmp_path / "lock").exists()
    assert not psutil.pid_exists(result["worker_pid"])
    if pressure_abort:
        assert "physical_RAM" in result["stop_reason"]
        assert "fixture Job close unconfirmed" in result["error_notes"]
    else:
        assert "Job close unconfirmed" in result["stop_reason"]


def test_frozen_phase2_identity_is_unchanged():
    phase2 = Path(__file__).resolve().parents[1] / "reports/zeus-attribution/phase2"
    report = phase2 / "corrected-v1/report.json"
    assert hashlib.sha256(report.read_bytes()).hexdigest() == "040ee6e7de58dec077ccdaa28961ee3e88a367a6dbc16931620e3df9a7cbb255"
    workspace = Path(__file__).resolve().parents[3]
    identity = json.loads((phase2 / "corrected-v1/identity.json").read_text())
    for source, expected in identity["scoring_sources"].items():
        assert hashlib.sha256((workspace / source).read_bytes()).hexdigest() == expected


@pytest.mark.skipif(os.name != "nt" or ctypes.sizeof(ctypes.c_void_p) != 8, reason="Windows x64 ABI")
def test_windows_native_job_layout():
    assert ctypes.sizeof(_BasicLimitInformation) == 64
    assert ctypes.sizeof(_IoCounters) == 48
    assert ctypes.sizeof(_ExtendedLimitInformation) == 144
