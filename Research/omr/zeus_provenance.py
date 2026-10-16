"""Hash current Zeus provenance separately from immutable historical manifests."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
from typing import Any
import zipfile

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[1]
ZEUS = HERE / "zeus"
SOURCE = ZEUS / "source"
MODEL = ZEUS / "weights/zeus-olimpic-1.0-2024-02-12.model"
RELEASE_URL = ("https://github.com/ufal/olimpic-icdar24/releases/download/"
               "zeus-release/zeus-olimpic-1.0-2024-02-12.model.tar.gz")


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_json(value: Any) -> str:
    return digest_bytes(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def file_record(path: Path) -> dict[str, Any]:
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": digest}


def inventory(root: Path) -> list[dict[str, Any]]:
    if not root.is_dir():
        raise ValueError(f"Inventory directory missing: {root}")
    records = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
            record = file_record(path)
            record["path"] = path.relative_to(root).as_posix()
            records.append(record)
    if not records:
        raise ValueError(f"Empty inventory: {root}")
    return records


def compare_release(archive: Path, model: Path) -> dict[str, Any]:
    required = {"weights.h5", "options.json", "tags.txt", "README.md", "LICENSE"}
    records = {}
    with tarfile.open(archive, "r:gz") as bundle:
        for member in bundle.getmembers():
            if member.isdir():
                continue
            parts = PurePosixPath(member.name).parts
            if (not member.isfile() or len(parts) != 2 or parts[0] != model.name
                    or parts[1] not in required or parts[1] in records
                    or member.size > 64 * 1024 * 1024):
                raise ValueError(f"Unexpected release member: {member.name}")
            stream = bundle.extractfile(member)
            if stream is None:
                raise ValueError(f"Unreadable release member: {member.name}")
            published = stream.read()
            local = (model / parts[1]).read_bytes()
            semantic_equal = None
            if parts[1] == "options.json":
                semantic_equal = json.loads(published) == json.loads(local)
            elif parts[1] == "tags.txt":
                semantic_equal = published.decode("utf-8").splitlines() == local.decode("utf-8").splitlines()
            equal = published == local
            newline_equal = parts[1] != "weights.h5" and (
                published.replace(b"\r\n", b"\n") == local.replace(b"\r\n", b"\n"))
            records[parts[1]] = {
                "published_sha256": digest_bytes(published), "local_sha256": digest_bytes(local),
                "published_bytes": len(published), "local_bytes": len(local),
                "byte_equal": equal, "equal_after_crlf_normalization": newline_equal,
                "semantic_equal": semantic_equal,
            }
    if set(records) != required:
        raise ValueError("Incomplete published checkpoint bundle")
    if any(not (row["byte_equal"] or row["equal_after_crlf_normalization"])
           for row in records.values()):
        raise ValueError("Material published/local checkpoint mismatch; stop for review")
    return {"url": RELEASE_URL, "archive": file_record(archive), "members": records,
            "independent_publisher_digest": None,
            "verification_basis": "fresh public release download; no publisher digest available"}


def git_output(root: Path, *arguments: str) -> str:
    result = subprocess.run(["git", "-C", str(root), *arguments], check=True,
                            capture_output=True, timeout=30)
    return result.stdout.decode("utf-8", errors="replace").strip()


def git_comparison(root: Path, revisions: list[str], relative_paths: list[str]) -> dict:
    comparisons = {}
    for revision in revisions:
        full = git_output(root, "rev-parse", "--verify", f"{revision}^{{commit}}")
        files = {}
        for path in relative_paths:
            result = subprocess.run(["git", "-C", str(root), "show", f"{full}:{path}"],
                                    capture_output=True, timeout=30)
            current = (root / path).read_bytes()
            files[path] = {"exists_at_revision": result.returncode == 0,
                           "git_blob_sha256": digest_bytes(result.stdout) if result.returncode == 0 else None,
                           "current_sha256": digest_bytes(current),
                           "equal_after_crlf_normalization": result.returncode == 0 and
                           result.stdout.replace(b"\r\n", b"\n") == current.replace(b"\r\n", b"\n")}
        comparisons[revision] = {"resolved_revision": full, "files": files}
    return comparisons


def validate_symbols(probe: dict, zeus_root: Path) -> list[str]:
    expected = {
        "Model": zeus_root / "source/zeus/zeus.py",
        "Delinearizer": zeus_root / "source/app/linearization/Delinearizer.py",
        "part_to_score": zeus_root / "source/app/symbolic/part_to_score.py",
        "ZeusRunner": zeus_root / "zeus_runner.py",
    }
    for symbol, path in expected.items():
        actual = probe.get("symbols", {}).get(symbol)
        if actual is None or Path(actual).resolve() != path.resolve():
            raise ValueError(f"Unexpected imported source for {symbol}: {actual}")
    paths = {Path(value).resolve() for value in probe["imported_modules"].values()}
    source = (zeus_root / "source").resolve()
    return sorted(path.relative_to(source).as_posix() for path in paths if path.is_relative_to(source))


def verify_records(root: Path, records: list[dict]) -> None:
    for record in records:
        path = (root / record["path"]).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError("Inventory path escapes pinned root")
        actual = file_record(path)
        if any(actual[key] != record[key] for key in ("sha256", "bytes")):
            raise ValueError(f"Pinned file changed: {path}")
    current_paths = {path.relative_to(root).as_posix() for path in root.rglob("*")
                     if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"}
    if current_paths != {row["path"] for row in records}:
        raise ValueError(f"Pinned file set changed: {root}")


def build(probe_path: Path, archive: Path, manifest_path: Path, output: Path) -> dict:
    if output.exists():
        raise FileExistsError(f"Preserve previous evidence: {output}")
    probe = json.loads(probe_path.read_text(encoding="utf-8"))
    if probe.get("probe_source_sha256") != file_record(HERE / "zeus_provenance_probe.py")["sha256"]:
        raise ValueError("Import probe source changed; collect a fresh probe")
    imported = validate_symbols(probe, ZEUS)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    historical = manifest["candidates"]["zeus_page"]
    declared = historical["identity"]["adapter_config"]["source_revision"]
    release = compare_release(archive, MODEL)
    state = {"head": git_output(SOURCE, "rev-parse", "HEAD"),
             "status": git_output(SOURCE, "status", "--porcelain=v1", "--untracked-files=all"),
             "reflog": git_output(SOURCE, "reflog", "--date=iso", "-8"),
             "remote": git_output(SOURCE, "remote", "get-url", "origin")}
    roots = {"zeus_environment": ZEUS / ".venv",
             "research_environment": HERE / ".venv",
             "detector_environment": WORKSPACE / "Bridge/.venv-homr-gpu",
             "base_python_runtime": Path(probe["base_prefix"])}
    environments = {}
    for name, root in roots.items():
        print(f"Hashing {name}", flush=True)
        records = inventory(root)
        environments[name] = {"root": str(root.resolve()), "files": records,
                              "inventory_sha256": digest_json(records)}
    source_paths = git_output(SOURCE, "ls-files", "--", "*.py", "*requirements*.txt", "*LICENSE*", "*README*").splitlines()
    source_records = [dict(file_record(SOURCE / path), path=path) for path in source_paths]
    pinned_files = set(historical["identity"]["source_files"])
    pinned_files.update({str((ZEUS / "zeus_runner.py").relative_to(WORKSPACE)),
                         str((HERE / "src/sheet2play_omr/phase2r_detector.py").relative_to(WORKSPACE)),
                         str((HERE / "src/sheet2play_omr/phase2r_vlm.py").relative_to(WORKSPACE)),
                         str(Path(__file__).relative_to(WORKSPACE)),
                         str((HERE / "zeus_provenance_probe.py").relative_to(WORKSPACE))})
    files = [dict(file_record(WORKSPACE / path), path=Path(path).as_posix()) for path in sorted(pinned_files)]
    imported_records = {name: file_record(Path(path)) for name, path in probe["imported_modules"].items()}
    identity = {"schema_version": 1, "purpose": "diagnostic_only; no screening admission",
                "historical_manifest": file_record(manifest_path),
                "historical_configuration_sha256": historical["identity_sha256"],
                "current_zeus_git": state, "upstream_source": source_records,
                "pipeline_files": files, "environments": environments,
                "imported_modules": imported_records, "probe": probe,
                "checkpoint_release_comparison": release,
                "inherited_detector_identity": historical["identity"]["readable_runtime"]["homr"],
                "historical_execution_source": "unverified; execution-time upstream files not recorded"}
    comparisons = git_comparison(SOURCE, [declared, "zeus-release", state["head"]], imported)
    payload = {"identity": identity, "identity_sha256": digest_json(identity),
               "source_comparison": comparisons,
               "limitations": ["Current import probe is not historical execution evidence",
                               "Source/release identity does not establish upstream inference parity",
                               "No model construction, inference, rescoring or timing correction"]}
    snapshot = output.with_suffix(".source.zip")
    with zipfile.ZipFile(snapshot, "x", compression=zipfile.ZIP_DEFLATED) as bundle:
        for record in source_records:
            bundle.write(SOURCE / record["path"], "upstream/" + record["path"])
        for record in files:
            if not record["path"].endswith("weights.h5"):
                bundle.write(WORKSPACE / record["path"], "pipeline/" + record["path"])
    payload["source_snapshot"] = file_record(snapshot)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return {"identity_sha256": payload["identity_sha256"], "output": str(output),
            "upstream_import_count": len(imported), "environment_file_counts":
            {name: len(value["files"]) for name, value in environments.items()}}


def verify(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    identity = payload["identity"]
    if digest_json(identity) != payload["identity_sha256"]:
        raise ValueError("Diagnostic identity digest mismatch")
    state = identity["current_zeus_git"]
    if (git_output(SOURCE, "rev-parse", "HEAD") != state["head"] or
            git_output(SOURCE, "status", "--porcelain=v1", "--untracked-files=all") != state["status"]):
        raise ValueError("Pinned upstream Git state changed")
    for name, environment in identity["environments"].items():
        print(f"Verifying {name}", flush=True)
        if digest_json(environment["files"]) != environment["inventory_sha256"]:
            raise ValueError("Environment inventory digest mismatch")
        verify_records(Path(environment["root"]), environment["files"])
    for root, records in ((SOURCE, identity["upstream_source"]),
                          (WORKSPACE, identity["pipeline_files"])):
        for record in records:
            actual = file_record(root / record["path"])
            if actual["sha256"] != record["sha256"]:
                raise ValueError(f"Pinned pipeline/source changed: {record['path']}")
    for record in [*identity["imported_modules"].values(), identity["historical_manifest"],
                   identity["checkpoint_release_comparison"]["archive"], payload["source_snapshot"]]:
        if file_record(Path(record["path"]))["sha256"] != record["sha256"]:
            raise ValueError(f"Pinned external evidence changed: {record['path']}")
    return {"verified": True, "identity_sha256": payload["identity_sha256"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("build")
    create.add_argument("--probe", type=Path, required=True)
    create.add_argument("--archive", type=Path, required=True)
    create.add_argument("--manifest", type=Path, required=True)
    create.add_argument("--output", type=Path, required=True)
    check = commands.add_parser("verify")
    check.add_argument("identity", type=Path)
    args = parser.parse_args()
    try:
        result = (verify(args.identity) if args.command == "verify" else
                  build(args.probe, args.archive, args.manifest, args.output))
        print(json.dumps(result))
        return 0
    except (OSError, ValueError, KeyError, subprocess.SubprocessError, tarfile.TarError) as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
