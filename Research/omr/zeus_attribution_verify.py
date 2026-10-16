"""Verify the pinned diagnostic bytes without invoking Git during recovery."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from zeus_provenance import WORKSPACE, SOURCE, digest_json, file_record, verify_records
from zeus_provenance_verify import verify_inherited


def verify_selected_records(root: Path, records: list[dict]) -> None:
    for record in records:
        path = (root / record["path"]).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError("Selected source path escapes pinned root")
        actual = file_record(path)
        if actual["sha256"] != record["sha256"] or actual["bytes"] != record["bytes"]:
            raise ValueError(f"Pinned source changed: {path}")


def verify_bytes(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    identity = payload["identity"]
    if digest_json(identity) != payload["identity_sha256"]:
        raise ValueError("Diagnostic identity digest mismatch")
    counts = {}
    for name, environment in identity["environments"].items():
        print(f"Verifying {name}", flush=True)
        if digest_json(environment["files"]) != environment["inventory_sha256"]:
            raise ValueError(f"Inventory digest changed: {name}")
        verify_records(Path(environment["root"]), environment["files"])
        counts[name] = len(environment["files"])
    for root, records in ((SOURCE, identity["upstream_source"]),
                          (WORKSPACE, identity["pipeline_files"])):
        verify_selected_records(root, records)
    for record in [*identity["imported_modules"].values(), identity["historical_manifest"],
                   identity["checkpoint_release_comparison"]["archive"], payload["source_snapshot"]]:
        if file_record(Path(record["path"]))["sha256"] != record["sha256"]:
            raise ValueError(f"Pinned evidence changed: {record['path']}")
    return {"verified": True, "identity_sha256": payload["identity_sha256"],
            "runtime_counts": counts,
            "inherited_detector_files_verified": verify_inherited(identity["inherited_detector_identity"]),
            "git_invocations": 0,
            "git_state": "Not queried; pinned source bytes verified, historical HEAD inherited only"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("identity", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify_bytes(args.identity)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps(result), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
