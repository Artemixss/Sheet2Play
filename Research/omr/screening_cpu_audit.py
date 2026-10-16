"""Verify a closed CPU screening run and save compact immutable audit evidence."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from screening_common import (completed_path, output_root, read_json, result_identity,
                              scored_path, verify_completed, write_new)
from screening_cpu_manifest import CPU_CANDIDATES, verify_manifest
from screening_consolidated_report import cpu_candidate
from sheet2play_omr.adapter_contract import sha256_file


def audit(path: Path, candidate: str, destination: Path, include_scores: bool) -> dict:
    manifest = verify_manifest(path)
    root = output_root(path)
    if (root / "worker.lock").exists():
        raise RuntimeError("Worker/scorer lock exists; audit only a closed run")
    config = manifest["candidates"][candidate]["identity_sha256"]
    records = []
    for item in manifest["items"]:
        directory = completed_path(root, candidate, item["id"], config)
        result = verify_completed(directory, result_identity(manifest, candidate, item))
        records.append({"item_id": item["id"], "status": result["status"],
                        "error": result.get("error"), "result_sha256": sha256_file(directory / "result.json"),
                        "artifact_count": len(result["artifacts"])})
    summary = None
    if include_scores:
        _, _, summary = cpu_candidate(root, manifest, candidate)
    session = read_json(root / "sessions" / f"stage3-{'audiveris' if candidate == 'audiveris_page' else 'zeus'}-screen-01.json")
    if session["active_since_utc"] is not None:
        raise RuntimeError("Session ledger is active")
    evidence = {"manifest_sha256": sha256_file(path), "configuration_sha256": config,
                "sample_sha256": manifest["sample_sha256"], "result_count": len(records),
                "status_counts": dict(Counter(row["status"] for row in records)),
                "verified_scores": len(records) if include_scores else 0,
                "summary": summary, "session": session, "records": records}
    write_new(destination, evidence)
    return {key: value for key, value in evidence.items() if key != "records"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--candidate", choices=CPU_CANDIDATES, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--include-scores", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit(args.manifest.resolve(), args.candidate, args.output.resolve(), args.include_scores)))
