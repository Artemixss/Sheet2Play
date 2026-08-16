from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from .assets import RuntimePaths, verify_runtime
from .dataset import DatasetRecord
from .errors import ResearchError


def _load_split(path: Path) -> list[DatasetRecord]:
    records: list[DatasetRecord] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise ResearchError("DATASET_INVALID", "materialization", f"Cannot read {path}: {error}") from error
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            records.append(DatasetRecord(**json.loads(line)))
        except (TypeError, json.JSONDecodeError) as error:
            raise ResearchError("DATASET_INVALID", "materialization", f"Invalid line {line_number}: {error}") from error
    if not records:
        raise ResearchError("DATASET_INVALID", "materialization", "Split manifest is empty")
    return records


def materialize_dataset(
    split_manifest: Path,
    output_dir: Path,
    *,
    workers: int = 1,
    seed: int = 20260813,
    paths: RuntimePaths | None = None,
) -> dict[str, Any]:
    if workers < 1:
        raise ResearchError("INPUT_INVALID", "materialization", "workers must be positive")
    runtime = paths or RuntimePaths.discover()
    verify_runtime(runtime)
    records = _load_split(split_manifest)
    input_root = output_dir / "canonical-input"
    generated_root = output_dir / "generated"
    artifacts_root = output_dir / "run-artifacts"
    input_root.mkdir(parents=True, exist_ok=True)
    for record in records:
        source = Path(record.musicxml).resolve(strict=True)
        destination = input_root / f"{record.identifier}{source.suffix.lower()}"
        if destination.exists():
            if destination.read_bytes() != source.read_bytes():
                raise ResearchError(
                    "DATASET_INVALID",
                    "materialization",
                    f"Identifier collision for {record.identifier}",
                )
        else:
            try:
                destination.hardlink_to(source)
            except OSError:
                shutil.copy2(source, destination)

    environment = os.environ.copy()
    environment["PYTHONHASHSEED"] = str(seed)
    command = [
        sys.executable,
        "-m",
        "scripts.dataset_generation.dataset_generation.main",
        str(input_root),
        "--output_dir",
        str(generated_root),
        "--target_samples",
        str(len(records)),
        "--num_workers",
        str(workers),
        "--artifacts_out_dir",
        str(artifacts_root),
        "--resume_mode",
        "auto",
        "--base_seed",
        str(seed),
        "--failure_policy",
        "coverage",
        "--quiet",
        "false",
        "--capture_verovio_diagnostics",
        "true",
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=runtime.source,
            env=environment,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise ResearchError(
            "MATERIALIZATION_FAILED",
            "materialization",
            f"Pinned Transcoda dataset generator failed: {error}",
        ) from error
    return {
        "source_revision": verify_runtime(runtime)["source_revision"],
        "records": len(records),
        "seed": seed,
        "workers": workers,
        "output": str(generated_root.resolve()),
        "exit_code": completed.returncode,
    }
