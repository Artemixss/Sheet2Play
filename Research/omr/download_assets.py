from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any


def _download_snapshot(snapshot_download: Any, section: dict[str, Any], destination: Path, cache: Path) -> None:
    required_files = sorted(str(name) for name in section["required_files"])
    snapshot_download(
        repo_id=str(section["repository"]),
        revision=str(section["revision"]),
        local_dir=destination,
        cache_dir=cache,
        allow_patterns=required_files,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Download only the pinned Transcoda research assets")
    parser.add_argument("--project-root", type=Path, required=True)
    args = parser.parse_args()
    root = args.project_root.resolve()
    sys.path.insert(0, str(root / "src"))

    from huggingface_hub import snapshot_download
    from sheet2play_omr.assets import RuntimePaths, load_asset_lock, verify_runtime

    paths = RuntimePaths.discover(root)
    lock = load_asset_lock(paths.lock_file)
    paths.runtime_root.mkdir(parents=True, exist_ok=True)
    paths.hf_cache.mkdir(parents=True, exist_ok=True)
    os.environ["HF_HOME"] = str(paths.hf_cache)
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"

    _download_snapshot(snapshot_download, lock["model"], paths.model, paths.hf_cache)
    _download_snapshot(snapshot_download, lock["base_model"], paths.base_model, paths.hf_cache)
    verify_runtime(paths)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
