"""Measure one direct Zeus research-engine development attempt, including failure resources."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parent.parent
SRC = HERE / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sheet2play_omr.adapter_contract import sha256_file  # noqa: E402
from sheet2play_omr.phase2_adapters import run_monitored  # noqa: E402


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(arguments)
    if not args.input.is_file():
        parser.error(f"Development input is missing: {args.input}")
    if args.worker:
        from sheet2play_omr.zeus_engine import infer_zeus_document

        print(infer_zeus_document(args.input, args.output), flush=True)
        return 0
    if args.report is None or args.report.exists() or args.output.exists():
        parser.error("A new, nonexisting report and output directory are required")
    command = [sys.executable, str(Path(__file__).resolve()), "--worker", "--input",
               str(args.input.resolve()), "--output", str(args.output.resolve())]
    environment = {**os.environ, "PYTHONPATH": str(SRC.resolve())}
    process = run_monitored(command, cwd=WORKSPACE, timeout_seconds=900,
                            environment=environment)
    log = args.output / "attempt.log"
    args.output.mkdir(parents=True, exist_ok=True)
    log.write_text(process.stdout + process.stderr, encoding="utf-8")
    artifacts = [
        {"path": path.resolve().relative_to(WORKSPACE).as_posix(), "sha256": sha256_file(path)}
        for path in sorted(args.output.rglob("*")) if path.is_file()
    ]
    report = {
        "phase": "2R correction",
        "scope": "one public open-development page; direct Zeus research-engine path",
        "input_sha256": sha256_file(args.input),
        "zeus_engine_sha256": sha256_file(SRC / "sheet2play_omr" / "zeus_engine.py"),
        "detector_sha256": sha256_file(SRC / "sheet2play_omr" / "phase2r_detector.py"),
        "attempt_runner_sha256": sha256_file(Path(__file__)),
        "exit_status": process.exit_status,
        "timed_out": process.timed_out,
        "seconds": process.seconds,
        "peak_ram_bytes": process.peak_ram_bytes,
        "peak_vram_bytes": process.peak_vram_bytes,
        "vram_measurement": process.vram_measurement,
        "stderr_tail": process.stderr[-1500:],
        "artifacts": artifacts,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.report.with_suffix(args.report.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(args.report)
    print(json.dumps({"exit_status": process.exit_status, "seconds": process.seconds,
                      "peak_ram_bytes": process.peak_ram_bytes,
                      "peak_vram_bytes": process.peak_vram_bytes,
                      "report": str(args.report)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
