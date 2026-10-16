"""Research-only HOMR launch with explicit CPU limits; shipped files stay untouched."""
from __future__ import annotations

import os
import ctypes
from ctypes import wintypes
from pathlib import Path
import sys


def main() -> int:
    threads = int(os.environ["S2P_PREFLIGHT_THREADS"])
    if threads < 1 or threads > max(1, (os.cpu_count() or 1) // 2):
        raise ValueError("Thread limit exceeds half the logical processors")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.SetProcessAffinityMask.argtypes = [wintypes.HANDLE, ctypes.c_size_t]
    process = kernel.GetCurrentProcess()
    mask = (1 << threads) - 1
    if not kernel.SetPriorityClass(process, 0x4000) or not kernel.SetProcessAffinityMask(process, mask):
        raise ctypes.WinError(ctypes.get_last_error())
    import cv2
    import onnxruntime as ort
    cv2.setNumThreads(threads)
    original_session = ort.InferenceSession

    def limited_session(path_or_bytes, sess_options=None, *args, **kwargs):
        options = sess_options if sess_options is not None else ort.SessionOptions()
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        return original_session(path_or_bytes, options, *args, **kwargs)

    ort.InferenceSession = limited_session
    print(f"Stage1 HOMR limits: threads={threads}, inter_op=1, priority=BELOW_NORMAL, affinity_mask={mask}",
          file=sys.stderr, flush=True)
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Bridge"))
    from homr_gpu import main as homr_main
    return homr_main()


if __name__ == "__main__":
    raise SystemExit(main())
