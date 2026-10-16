"""Read current Windows worker and Job commit without changing containment."""
from __future__ import annotations

import ctypes
import os
import time

from sheet2play_omr.windows_job import _ExtendedLimitInformation


class _ProcessMemory(ctypes.Structure):
    _fields_ = [("cb", ctypes.c_uint32), ("PageFaultCount", ctypes.c_uint32)] + [
        (name, ctypes.c_size_t) for name in (
            "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
            "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage",
            "PagefileUsage", "PeakPagefileUsage", "PrivateUsage")]


def memory_sample() -> dict:
    if os.name != "nt":
        raise OSError("Windows Job telemetry is required")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    kernel.K32GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32]
    kernel.K32GetProcessMemoryInfo.restype = ctypes.c_int32
    kernel.QueryInformationJobObject.argtypes = [ctypes.c_void_p, ctypes.c_int,
                                                ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p]
    kernel.QueryInformationJobObject.restype = ctypes.c_int32
    process = _ProcessMemory()
    process.cb = ctypes.sizeof(process)
    if not kernel.K32GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(process), process.cb):
        raise ctypes.WinError(ctypes.get_last_error())
    job = _ExtendedLimitInformation()
    if not kernel.QueryInformationJobObject(None, 9, ctypes.byref(job), ctypes.sizeof(job), None):
        raise ctypes.WinError(ctypes.get_last_error())
    # With nested Jobs, a null handle can describe the outer Job. The supervisor
    # receipt identifies the actual 4 GiB containment; these are diagnostic counters.
    return {"utc": time.time(), "pid": os.getpid(), "private_bytes": process.PrivateUsage,
            "peak_private_bytes": process.PeakPagefileUsage,
            "working_set_bytes": process.WorkingSetSize,
            "associated_job_limit_bytes": job.JobMemoryLimit,
            "associated_job_peak_bytes": job.PeakJobMemoryUsed,
            "associated_job_identity": "NULL-handle query; may describe outer Job"}
