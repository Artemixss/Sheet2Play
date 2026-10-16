"""Pinned, portable HOMR 465 runtime identity and asset validation."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
from pathlib import Path
from typing import Any

SOURCE_REVISION = "33baa326900faa12702df8c4bdcbea034a3d6a34"
MODEL_REVISION = "465-597144cab54c8f6d0f6c9619df5c5312694eadd6-fp16"
MODEL_HASHES = {
    "encoder": "50823c061533328f5e64df016d3ed16eb9071a9f5c5ee8621646cf9ac9c8a992",
    "decoder": "aaac38c4f4be13ec587325486f29a60a919924f0eb82d35b52d4a2e7126dfbe0",
    "segnet": "60f495496cb41473c0521d0811d8f44b9d5cff892d287974a8aebb3eaee2fa83",
}
PROFILE_PATH = Path(__file__).with_name("homr465-profile.json")


class ProfileError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def asset_path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or Path(relative).is_absolute():
        raise ProfileError(f"Runtime asset escapes its root: {relative}")
    return path


def load_profile(path: Path = PROFILE_PATH, *, verify_assets: bool = True) -> tuple[dict[str, Any], str]:
    try:
        profile = json.loads(path.read_text(encoding="utf-8"))
        if profile["schema_version"] != 1 or profile["source_revision"] != SOURCE_REVISION or profile["model_revision"] != MODEL_REVISION:
            raise ProfileError("Unrecognized HOMR 465 profile identity")
        if profile["provider"] != "CUDAExecutionProvider" or profile["threads"] != 8 or profile["inter_op_threads"] != 1 or profile["pdf_dpi"] != 300:
            raise ProfileError("Unapproved HOMR 465 inference settings")
        if profile["processing"]["title_detection"] is not False:
            raise ProfileError("HOMR 465 requires the pinned no-title policy")
        if {name: row["sha256"] for name, row in profile["models"].items()} != MODEL_HASHES:
            raise ProfileError("Unapproved HOMR 465 model hashes")
        if verify_assets:
            root = asset_path(path.parent, profile["runtime_directory"])
            for row in profile["source_files"] + list(profile["models"].values()):
                if sha256_file(asset_path(root, row["path"])) != row["sha256"]:
                    raise ProfileError(f"HOMR 465 asset hash mismatch: {row['path']}")
            for row in profile["bridge_files"]:
                if sha256_file(asset_path(path.parent, row["path"])) != row["sha256"]:
                    raise ProfileError(f"HOMR 465 Bridge hash mismatch: {row['path']}")
            for name, version in profile["package_versions"].items():
                if importlib.metadata.version(name) != version:
                    raise ProfileError(f"HOMR 465 dependency mismatch: {name}; expected {version}")
        return profile, sha256_file(path)
    except (OSError, KeyError, TypeError, ValueError, importlib.metadata.PackageNotFoundError) as error:
        raise ProfileError(f"HOMR 465 runtime profile is unavailable or invalid: {error}") from error
