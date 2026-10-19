"""Pinned, portable HOMR 480 runtime identity and asset validation.

Run 480 on upstream main `ab369ac`, the app default since 2026-10-18; HOMR 465 is the secondary
engine. Measured in `Research/omr/reports/upstream-480/handoff.md`. The checks mirror
`homr465_profile.py`, whose helpers this reuses.
"""
from __future__ import annotations

import importlib.metadata
import json
from pathlib import Path
from typing import Any

from homr465_profile import ProfileError, asset_path, sha256_file

SOURCE_REVISION = "ab369ac54277afab582afa4725441f7cbba76593"
MODEL_REVISION = "480-5eed84636c96eca5ce6d8e2f62580b74e7ed85e8-fp16-encoder-fp32-decoder"
MODEL_HASHES = {
    "encoder": "c1450a582576e9bc16152e4c61b9c2f2283da549e1ee890f051883f5e1c7329e",
    "decoder": "4727ac741dca23de8eabbcd8dd2dfa33d5f1ec9cecb64465e6c0fb348616fc8c",
    "segnet": "60f495496cb41473c0521d0811d8f44b9d5cff892d287974a8aebb3eaee2fa83",
}
PROFILE_PATH = Path(__file__).with_name("homr480-profile.json")


def load_profile(path: Path = PROFILE_PATH, *, verify_assets: bool = True) -> tuple[dict[str, Any], str]:
    try:
        profile = json.loads(path.read_text(encoding="utf-8"))
        if profile["schema_version"] != 1 or profile["source_revision"] != SOURCE_REVISION or profile["model_revision"] != MODEL_REVISION:
            raise ProfileError("Unrecognized HOMR 480 profile identity")
        if profile["provider"] != "CUDAExecutionProvider" or profile["threads"] != 8 or profile["inter_op_threads"] != 1 or profile["pdf_dpi"] != 300:
            raise ProfileError("Unapproved HOMR 480 inference settings")
        if profile["processing"]["title_detection"] is not False:
            raise ProfileError("HOMR 480 requires the pinned no-title policy")
        if {name: row["sha256"] for name, row in profile["models"].items()} != MODEL_HASHES:
            raise ProfileError("Unapproved HOMR 480 model hashes")
        if verify_assets:
            root = asset_path(path.parent, profile["runtime_directory"])
            for row in profile["source_files"] + list(profile["models"].values()):
                if sha256_file(asset_path(root, row["path"])) != row["sha256"]:
                    raise ProfileError(f"HOMR 480 asset hash mismatch: {row['path']}")
            for row in profile["bridge_files"]:
                if sha256_file(asset_path(path.parent, row["path"])) != row["sha256"]:
                    raise ProfileError(f"HOMR 480 Bridge hash mismatch: {row['path']}")
            for name, version in profile["package_versions"].items():
                if importlib.metadata.version(name) != version:
                    raise ProfileError(f"HOMR 480 dependency mismatch: {name}; expected {version}")
        return profile, sha256_file(path)
    except (OSError, KeyError, TypeError, ValueError, importlib.metadata.PackageNotFoundError) as error:
        raise ProfileError(f"HOMR 480 runtime profile is unavailable or invalid: {error}") from error
