"""Windows-only containment for an explicitly assigned research worker tree."""
from __future__ import annotations

import ctypes
import os
from types import TracebackType
from typing import Literal


_DWORD = ctypes.c_uint32
_HANDLE = ctypes.c_void_p
_SIZE_T = ctypes.c_size_t
_PROCESS_TERMINATE = 0x0001
_PROCESS_SET_QUOTA = 0x0100
_JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008
_JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9


class _BasicLimitInformation(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", _DWORD),
        ("MinimumWorkingSetSize", _SIZE_T),
        ("MaximumWorkingSetSize", _SIZE_T),
        ("ActiveProcessLimit", _DWORD),
        ("Affinity", _SIZE_T),
        ("PriorityClass", _DWORD),
        ("SchedulingClass", _DWORD),
    ]


class _IoCounters(ctypes.Structure):
    _fields_ = [
        (name, ctypes.c_uint64)
        for name in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount",
        )
    ]


class _ExtendedLimitInformation(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _BasicLimitInformation),
        ("IoInfo", _IoCounters),
        ("ProcessMemoryLimit", _SIZE_T),
        ("JobMemoryLimit", _SIZE_T),
        ("PeakProcessMemoryUsed", _SIZE_T),
        ("PeakJobMemoryUsed", _SIZE_T),
    ]


def _positive_native_integer(value: int, name: str, byte_width: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if not 0 < value < 1 << (byte_width * 8):
        raise ValueError(f"{name} must be positive and fit its Windows native type")
    return value


def _winapi_error(operation: str) -> OSError:
    error = ctypes.WinError(ctypes.get_last_error())
    error.add_note(operation)
    return error


def _kernel32() -> ctypes.WinDLL:
    if os.name != "nt":
        raise OSError("Windows Job Object containment is required; no fallback is permitted")
    library = ctypes.WinDLL("kernel32", use_last_error=True)
    library.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
    library.CreateJobObjectW.restype = _HANDLE
    library.SetInformationJobObject.argtypes = [_HANDLE, ctypes.c_int, ctypes.c_void_p, _DWORD]
    library.SetInformationJobObject.restype = ctypes.c_int32
    library.AssignProcessToJobObject.argtypes = [_HANDLE, _HANDLE]
    library.AssignProcessToJobObject.restype = ctypes.c_int32
    library.OpenProcess.argtypes = [_DWORD, ctypes.c_int32, _DWORD]
    library.OpenProcess.restype = _HANDLE
    library.TerminateJobObject.argtypes = [_HANDLE, _DWORD]
    library.TerminateJobObject.restype = ctypes.c_int32
    library.CloseHandle.argtypes = [_HANDLE]
    library.CloseHandle.restype = ctypes.c_int32
    return library


class WindowsJob:
    """Cap aggregate committed memory/processes and kill the assigned tree on close.

    The caller must hold the child at a start gate until ``assign`` succeeds.
    Processes outside this Job Object are neither limited nor terminated.
    """

    def __init__(self, memory_limit_bytes: int, active_process_limit: int) -> None:
        self._memory_limit_bytes = _positive_native_integer(
            memory_limit_bytes, "memory_limit_bytes", ctypes.sizeof(_SIZE_T)
        )
        self._active_process_limit = _positive_native_integer(
            active_process_limit, "active_process_limit", ctypes.sizeof(_DWORD)
        )
        self._kernel: ctypes.WinDLL | None = None
        self._handle: int | None = None

    def __enter__(self) -> WindowsJob:
        if self._handle is not None:
            raise RuntimeError("WindowsJob is already open")
        self._kernel = _kernel32()
        handle = self._kernel.CreateJobObjectW(None, None)
        if not handle:
            raise _winapi_error("CreateJobObjectW failed")
        self._handle = handle
        try:
            limits = _ExtendedLimitInformation()
            limits.BasicLimitInformation.LimitFlags = (
                _JOB_OBJECT_LIMIT_ACTIVE_PROCESS
                | _JOB_OBJECT_LIMIT_JOB_MEMORY
                | _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            )
            limits.BasicLimitInformation.ActiveProcessLimit = self._active_process_limit
            limits.JobMemoryLimit = self._memory_limit_bytes
            if not self._kernel.SetInformationJobObject(
                self._handle, _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
                ctypes.byref(limits), ctypes.sizeof(limits),
            ):
                raise _winapi_error("SetInformationJobObject failed; child work is forbidden")
        except BaseException as error:
            try:
                self.close()
            except OSError as close_error:
                error.add_note(f"Job handle cleanup also failed: {close_error}")
            raise
        return self

    def _require_open(self) -> tuple[ctypes.WinDLL, int]:
        if self._kernel is None or self._handle is None:
            raise RuntimeError("WindowsJob is not open")
        return self._kernel, self._handle

    @property
    def closed(self) -> bool:
        return self._handle is None

    def assign(self, pid: int) -> None:
        process_id = _positive_native_integer(pid, "pid", ctypes.sizeof(_DWORD))
        if process_id == os.getpid():
            raise ValueError("Assign the waiting worker, never the supervisor itself")
        library, job_handle = self._require_open()
        process_handle = library.OpenProcess(
            _PROCESS_SET_QUOTA | _PROCESS_TERMINATE, False, process_id
        )
        if not process_handle:
            raise _winapi_error(f"OpenProcess failed for worker PID {process_id}")
        assignment_error: BaseException | None = None
        try:
            if not library.AssignProcessToJobObject(job_handle, process_handle):
                raise _winapi_error(
                    f"AssignProcessToJobObject failed for PID {process_id}; child work is forbidden"
                )
        except BaseException as error:
            assignment_error = error
            raise
        finally:
            if not library.CloseHandle(process_handle):
                close_error = _winapi_error(f"CloseHandle failed for worker PID {process_id}")
                if assignment_error is not None:
                    assignment_error.add_note(f"Process handle cleanup also failed: {close_error}")
                else:
                    raise close_error

    def terminate(self, exit_code: int = 2) -> None:
        if isinstance(exit_code, bool) or not isinstance(exit_code, int):
            raise TypeError("exit_code must be an integer")
        if not 0 <= exit_code < 1 << 32:
            raise ValueError("exit_code must fit a Windows unsigned 32-bit integer")
        library, handle = self._require_open()
        if not library.TerminateJobObject(handle, exit_code):
            raise _winapi_error("TerminateJobObject failed")

    def close(self) -> None:
        if self._handle is None:
            return
        library, handle = self._require_open()
        if not library.CloseHandle(handle):
            raise _winapi_error("CloseHandle failed for the Job Object")
        self._handle = None

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        try:
            self.close()
        except OSError as close_error:
            if exc_value is None:
                raise
            exc_value.add_note(f"Job handle cleanup also failed: {close_error}")
        return False
