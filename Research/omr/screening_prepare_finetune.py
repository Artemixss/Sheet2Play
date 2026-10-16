"""Intake the verified private-report bundle; freeze development admission identity."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess

from screening_common import HERE, REPORTS, WORKSPACE, digest, read_json, write_new
from screening_finetune_compatibility import check_parity
from screening_finetune_extension import (CONTRACT, RUNTIME, SOURCE, build_extended_manifest,
                                         compatibility_evidence)
from sheet2play_omr.adapter_contract import sha256_file

REPORT_COMMIT = "9bf0d477aa75e8c4a7b48ad6b9fdae2d24c1fab7"


def prepare(bundle: Path) -> Path:
    bundle = bundle.resolve()
    inventory = read_json(bundle / "artifact-hash-inventory.json")
    for entry in inventory["files"]:
        file = (bundle / entry["path"]).resolve()
        if (not file.is_relative_to(bundle) or not file.is_file()
                or file.stat().st_size != entry["size_bytes"] or sha256_file(file) != entry["sha256"]):
            raise ValueError(f"Report bundle artifact differs: {entry['path']}")
    provenance, verification = (read_json(bundle / name) for name in
                                ("provenance-manifest-v2.json", "verification.json"))
    check_parity(provenance, verification)
    patch = bundle / provenance["source"]["local_patch"]
    if sha256_file(patch) != provenance["source"]["local_patch_sha256"]:
        raise ValueError("Remote training patch identity differs")
    bundled_source = bundle / "source_bundle"
    for file in bundled_source.rglob("*"):
        if file.is_file() and file.name != "local_changes.patch":
            reconstructed = SOURCE / file.relative_to(bundled_source)
            if not reconstructed.is_file() or sha256_file(file) != sha256_file(reconstructed):
                raise ValueError(f"Reconstructed source differs: {file.relative_to(bundled_source)}")
    for name, expected in provenance["tokenizer_json_files"].items():
        if sha256_file(SOURCE / "homr/transformer" / f"tokenizer_{name}.json") != expected:
            raise ValueError(f"Source tokenizer differs: {name}")
    destination = CONTRACT.parent / "remote-9bf0d47"
    if not destination.exists():
        shutil.copytree(bundle, destination)
    for file in bundle.rglob("*"):
        if file.is_file() and sha256_file(destination / file.relative_to(bundle)) != sha256_file(file):
            raise ValueError("Persisted report evidence differs")
    program = ("import sys,json;sys.path.insert(0,'Research/omr');"
               "from screening_finetune_compatibility import vocabulary;"
               f"from pathlib import Path;labels,special=vocabulary(Path({str(SOURCE.resolve())!r}));"
               "print(json.dumps({'labels':labels,'special_tokens':special}))")
    result = subprocess.run([str(RUNTIME / "Scripts/python.exe"), "-B", "-c", program],
                            cwd=WORKSPACE, capture_output=True, text=True, check=True, timeout=30)
    vocabulary = json.loads(result.stdout)
    evidence = {str(file.relative_to(CONTRACT.parent)).replace("\\", "/"): sha256_file(file)
                for file in destination.rglob("*") if file.is_file()}
    source_files = {file.relative_to(SOURCE).as_posix(): sha256_file(file)
                    for file in (SOURCE / "homr").rglob("*")
                    if file.is_file() and file.suffix in {".py", ".json"}}
    contract = {"schema_version": 1, "report_commit": REPORT_COMMIT,
                "source_revision": provenance["source"]["revision"],
                "checkpoint_sha256": provenance["artifacts"]["checkpoint"]["sha256"],
                "source_files": source_files, "evidence_files": evidence,
                "provenance": "remote-9bf0d47/provenance-manifest-v2.json",
                "verification": "remote-9bf0d47/verification.json", **vocabulary}
    if CONTRACT.exists():
        if read_json(CONTRACT) != contract:
            raise ValueError("Preserve existing fine-tune contract; prepare a new identity for changes")
    else:
        write_new(CONTRACT, contract)
    compatibility_evidence(allow_create=True)
    manifest = build_extended_manifest()
    path = REPORTS / f"manifest-v4-{digest(manifest)[:12]}.json"
    if path.exists():
        if read_json(path) != manifest:
            raise ValueError("Fine-tune manifest content differs")
    else:
        write_new(path, manifest)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    args = parser.parse_args()
    path = prepare(args.bundle)
    print(json.dumps({"manifest": str(path), "sha256": sha256_file(path),
                      "candidate_inference_started": False}))


if __name__ == "__main__":
    main()
