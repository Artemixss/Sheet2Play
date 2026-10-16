"""Freeze verified fine-tuned HOMR and compatible HOMR 455 under the 90% policy."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from screening_common import HERE, REPORTS, digest, read_json, threads_limit, write_new
from screening_finetune_extension import build_extended_manifest
from screening_homr_extension import candidate_identity
from sheet2play_omr.adapter_contract import sha256_file


SCOPE = "verified_homr_only; unchanged_frozen_sample_and_scoring"


def build_manifest() -> dict[str, Any]:
    manifest = build_extended_manifest()
    candidate = candidate_identity(sha256_file(HERE / "screening_run.py"), threads_limit())
    identity = candidate["identity"]
    identity["source_files"]["Research/omr/screening_prepare_homr_stage4.py"] = sha256_file(Path(__file__))
    candidate["identity_sha256"] = digest(identity)
    return {**manifest, "name": "smb-pianoform-screening-v4-verified-homr",
            "extension_scope": SCOPE,
            "candidates": {**manifest["candidates"], "homr_455": candidate},
            "retired_455_configuration_sha256":
                "cb45056ebb223f4bb82fc7b4eecd4f4fd28d5cd0a00b439bc00e8bde6537a99f"}


def prepare() -> Path:
    manifest = build_manifest()
    path = REPORTS / f"manifest-v4-{digest(manifest)[:12]}.json"
    if path.exists():
        if read_json(path) != manifest:
            raise ValueError("Existing HOMR manifest differs")
    else:
        write_new(path, manifest)
    return path


if __name__ == "__main__":
    path = prepare()
    print(json.dumps({"manifest": str(path), "sha256": sha256_file(path),
                      "candidate_inference_started": False}))
