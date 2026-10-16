"""Freeze the deterministic composition-group screen without candidate inference."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from screening_common import REPORTS, build_manifest, digest, read_json, write_new
from sheet2play_omr.adapter_contract import sha256_file


def prepare() -> Path:
    manifest = build_manifest()
    path = REPORTS / f"manifest-v{manifest['schema_version']}-{digest(manifest)[:12]}.json"
    if path.exists():
        if read_json(path) != manifest:
            raise ValueError(f"Existing manifest has different content: {path}")
    else:
        write_new(path, manifest)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    path = prepare()
    manifest = read_json(path)
    print(json.dumps({"manifest": str(path), "identity_sha256": digest(manifest),
                      "file_sha256": sha256_file(path),
                      "groups": manifest["selected_group_count"],
                      "pages": manifest["selected_item_count"],
                      "candidate_inference_started": False}))


if __name__ == "__main__":
    main()
