"""Provision the pinned runtime using local source and model bytes only."""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil

from homr465_profile import PROFILE_PATH, asset_path, load_profile, sha256_file


def provision(source: Path, encoder: Path, decoder: Path, segnet: Path, profile_path: Path = PROFILE_PATH) -> None:
    profile, identity = load_profile(profile_path, verify_assets=False)
    root = asset_path(profile_path.parent, profile["runtime_directory"])
    inputs = [(source / row["path"].removeprefix("source/"), row) for row in profile["source_files"]]
    inputs.extend((path, profile["models"][name]) for name, path in (("encoder", encoder), ("decoder", decoder), ("segnet", segnet)))
    for origin, row in inputs:
        if sha256_file(origin) != row["sha256"]:
            raise ValueError(f"Pinned local input hash mismatch: {origin}")
        target = asset_path(root, row["path"])
        if target.exists() and sha256_file(target) != row["sha256"]:
            raise FileExistsError(f"Refusing to overwrite conflicting runtime bytes: {target}")
    for origin, row in inputs:
        target = asset_path(root, row["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copyfile(origin, target)
    load_profile(profile_path)
    print(f"HOMR 465 runtime provisioned and verified: {identity}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "encoder", "decoder", "segnet"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    provision(args.source, args.encoder, args.decoder, args.segnet)
