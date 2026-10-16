"""Explicit CPU limits for the native Audiveris and neutral Zeus screen."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
from typing import Mapping


def cpu_environment(threads: int) -> dict[str, str]:
    if isinstance(threads, bool) or not isinstance(threads, int) or threads < 1:
        raise ValueError("CPU thread limit must be a positive integer")
    return {"OMP_NUM_THREADS": str(threads), "MKL_NUM_THREADS": str(threads),
            "OPENBLAS_NUM_THREADS": str(threads), "NUMEXPR_NUM_THREADS": str(threads),
            "TF_NUM_INTRAOP_THREADS": str(threads), "TF_NUM_INTEROP_THREADS": "1",
            "JAVA_TOOL_OPTIONS": f"-XX:ActiveProcessorCount={threads}",
            "_JAVA_OPTIONS": "", "JDK_JAVA_OPTIONS": ""}


def validate_cpu_environment(environment: Mapping[str, str], threads: int) -> None:
    if any(environment.get(key) != value for key, value in cpu_environment(threads).items()):
        raise ValueError("Effective CPU environment differs from the recorded screening profile")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.command or args.command[0] != "--" or len(args.command) < 2:
        parser.error("Supply an existing research script after --")
    script = Path(args.command[1]).resolve()
    allowed = {Path(__file__).with_name(name).resolve() for name in (
        "screening_cpu_development.py", "screening_cpu_run.py", "screening_cpu_score.py")}
    if script not in allowed or not script.is_file():
        parser.error("Script is not an allowed screening entry point")
    from screening_common import threads_limit, WORKSPACE
    environment = {**os.environ, **cpu_environment(threads_limit())}
    validate_cpu_environment(environment, threads_limit())
    return subprocess.call([sys.executable, "-B", str(script), *args.command[2:]],
                           cwd=WORKSPACE, env=environment, stdin=subprocess.DEVNULL,
                           creationflags=subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS)


if __name__ == "__main__":
    raise SystemExit(main())
