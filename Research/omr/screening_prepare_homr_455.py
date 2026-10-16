"""Freeze a HOMR 455 candidate identity on the existing screening sample."""
from __future__ import annotations

import json

from screening_common import REPORTS, digest, read_json, write_new
from screening_homr_extension import build_extended_manifest, compatibility_evidence
from sheet2play_omr.adapter_contract import sha256_file


def main() -> None:
    compatibility_evidence(allow_create=True)
    manifest = build_extended_manifest()
    path = REPORTS / f"manifest-v{manifest['schema_version']}-{digest(manifest)[:12]}.json"
    if path.exists():
        if read_json(path) != manifest:
            raise ValueError("Existing HOMR 455 manifest has changed")
    else:
        write_new(path, manifest)
    print(json.dumps({"manifest": str(path), "sha256": sha256_file(path),
                      "sample_sha256": manifest["sample_sha256"],
                      "homr_455_configuration_sha256":
                      manifest["candidates"]["homr_455"]["identity_sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
