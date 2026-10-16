"""Run the import-only probe with the existing 90% pressure and CPU limits."""
from __future__ import annotations

from datetime import datetime, timezone
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[5]
RESEARCH = ROOT / "Research/omr"
sys.path.insert(0, str(RESEARCH))

import psutil
from screening_common import threads_limit, POLICY
from screening_cpu_profile import cpu_environment
from screening_stage1_preflight import resource_sample
from screening_stage1_development import stop_tree


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    command = [str(RESEARCH / "zeus/.venv/Scripts/python.exe"), "-B",
               str(RESEARCH / "zeus_provenance_probe.py"), "--zeus-root",
               str(RESEARCH / "zeus"), "--output", str(output / "import-probe.json")]
    sample = resource_sample()
    if sample["admission_blockers"]:
        raise RuntimeError(f"Probe not admitted: {sample['admission_blockers']}")
    for process in psutil.process_iter(["pid", "cmdline"]):
        args = process.info["cmdline"] or []
        if any(Path(arg).name in {"infer_batch.py", "screening_cpu_run.py",
                                  "screening_cpu_score.py", "phase3_sequence.py"} for arg in args):
            raise RuntimeError(f"Existing candidate/scorer worker: {process.pid}")
    environment = {**os.environ, **cpu_environment(threads_limit()), "CUDA_VISIBLE_DEVICES": "-1"}
    with (output / "probe.stdout.log").open("x", encoding="utf-8") as stdout, (
            output / "probe.stderr.log").open("x", encoding="utf-8") as stderr, (
            output / "probe-resources.jsonl").open("x", encoding="utf-8") as resources:
        resources.write(json.dumps(sample) + "\n")
        worker = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=stdout,
                                  stderr=stderr, stdin=subprocess.DEVNULL,
                                  creationflags=subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS)
        process = psutil.Process(worker.pid)
        process.cpu_affinity(process.cpu_affinity()[:threads_limit()])
        record = {"command": command, "cwd": str(ROOT), "pid": worker.pid,
                  "creation_time": process.create_time(), "utc": datetime.now(timezone.utc).isoformat(),
                  "policy": POLICY, "environment": cpu_environment(threads_limit()),
                  "inference_started": False}
        (output / "probe-worker.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        started, pressure_since = time.monotonic(), None
        while worker.poll() is None:
            sample = resource_sample()
            resources.write(json.dumps(sample) + "\n")
            resources.flush()
            now = time.monotonic()
            pressure_since = (pressure_since or now) if sample["admission_blockers"] else None
            if now - started > 120 or (pressure_since is not None and now - pressure_since >= 30):
                stop_tree(process)
                raise RuntimeError("Probe interrupted by timeout or sustained resource pressure")
            time.sleep(5)
        return worker.wait(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main())
