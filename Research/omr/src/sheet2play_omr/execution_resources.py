"""Small Windows commit samples and bounded process evidence without invoking Git."""
from __future__ import annotations

import ctypes
from datetime import datetime, timezone
import os
import threading
import time

import psutil


class _PerformanceInfo(ctypes.Structure):
    _fields_ = [("cb", ctypes.c_uint32)] + [
        (name, ctypes.c_size_t) for name in (
            "CommitTotal", "CommitLimit", "CommitPeak", "PhysicalTotal",
            "PhysicalAvailable", "SystemCache", "KernelTotal", "KernelPaged",
            "KernelNonpaged", "PageSize",
        )
    ] + [(name, ctypes.c_uint32) for name in ("HandleCount", "ProcessCount", "ThreadCount")]


def _row(process: psutil.Process) -> dict:
    memory = process.memory_info()
    return {"pid": process.pid, "parent_pid": process.ppid(), "name": process.name(),
            "created": process.create_time(), "private_bytes": memory.private,
            "threads": process.num_threads()}


def _git_sample() -> dict:
    git_rows = []
    git_bytes, git_count = 0, 0
    inaccessible = 0
    for process in psutil.process_iter(["name"]):
        if (process.info["name"] or "").lower() != "git.exe":
            continue
        try:
            row = _row(process)
        except psutil.NoSuchProcess:
            continue
        except psutil.AccessDenied:
            inaccessible += 1
            continue
        git_count += 1
        git_bytes += row["private_bytes"]
        if len(git_rows) < 16:
            git_rows.append(row)
    return {"git_count": git_count, "git_private_bytes": git_bytes,
            "git_processes": git_rows, "git_processes_not_readable": inaccessible,
            "git_observed_utc": datetime.now(timezone.utc).isoformat(),
            "git_telemetry_state": "partial" if inaccessible else "complete"}


class _GitTelemetry:
    """An in-flight process scan cannot delay the system pressure gate."""

    def __init__(self, collector=_git_sample) -> None:
        self._collector = collector
        self._lock = threading.Lock()
        self._running = False
        self._next_scan = 0.0
        self._latest = {"git_count": 0, "git_private_bytes": 0, "git_processes": [],
                        "git_observed_utc": None, "git_telemetry_state": "pending"}

    def _collect(self) -> None:
        try:
            latest = self._collector()
        except Exception as error:
            with self._lock:
                latest = {**self._latest, "git_telemetry_state": "error",
                          "git_telemetry_error": type(error).__name__}
        with self._lock:
            self._latest = latest
            self._running = False
            self._next_scan = time.monotonic() + 5

    def snapshot(self) -> dict:
        with self._lock:
            if not self._running and time.monotonic() >= self._next_scan:
                self._running = True
                try:
                    threading.Thread(target=self._collect, daemon=True).start()
                except Exception:
                    self._running = False
                    self._next_scan = time.monotonic() + 5
                    self._latest = {**self._latest, "git_telemetry_state": "unavailable"}
            return {**self._latest, "git_scan_in_progress": self._running}


class WindowsResourceSampler:
    def __init__(self) -> None:
        if os.name != "nt":
            raise OSError("Windows commit measurement is required; no physical-only fallback")
        self._library = ctypes.WinDLL("psapi", use_last_error=True)
        self._query = self._library.GetPerformanceInfo
        self._query.argtypes = [ctypes.POINTER(_PerformanceInfo), ctypes.c_uint32]
        self._query.restype = ctypes.c_int32
        self._git_telemetry = _GitTelemetry()

    def __call__(self) -> dict:
        telemetry = self._git_telemetry.snapshot()
        info = _PerformanceInfo()
        info.cb = ctypes.sizeof(info)
        if not self._query(ctypes.byref(info), info.cb):
            raise ctypes.WinError(ctypes.get_last_error())
        if not info.CommitLimit or not info.PhysicalTotal or not info.PageSize:
            raise RuntimeError("Invalid Windows memory counters")
        return {"utc": datetime.now(timezone.utc).isoformat(),
                "committed_bytes": info.CommitTotal * info.PageSize,
                "commit_limit_bytes": info.CommitLimit * info.PageSize,
                "physical_percent": 100 * (1 - info.PhysicalAvailable / info.PhysicalTotal),
                **telemetry}


def process_evidence() -> dict:
    rows, inaccessible = [], 0
    for process in psutil.process_iter():
        try:
            rows.append(_row(process))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            inaccessible += 1
    return {"largest_private_memory_processes": sorted(
        rows, key=lambda row: row["private_bytes"], reverse=True)[:24],
        "processes_not_readable": inaccessible,
        "limitation": "Process private bytes do not account for all system commit; no commandlines captured"}
