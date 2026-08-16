from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tarfile
import tempfile
import urllib.request
from pathlib import Path, PurePosixPath
from typing import Any


MINIMUM_FREE_BYTES = 20 * 1024**3
DOWNLOAD_BLOCK_BYTES = 1024 * 1024


class DatasetPreparationError(RuntimeError):
    pass


def _read_lock(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        dataset = payload["dataset"]
        archive = dataset["archive"]
        extracted = dataset["extracted"]
        required = (
            archive["name"],
            archive["url"],
            archive["sha256"],
            archive["size"],
            extracted["root"],
            extracted["file_count"],
            extracted["size"],
            extracted["test_system_count"],
            extracted["test_score_count"],
        )
        if any(value in (None, "") for value in required):
            raise ValueError("required lock field is empty")
        return payload
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise DatasetPreparationError(f"Invalid OLiMPiC lock {path}: {error}") from error


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(DOWNLOAD_BLOCK_BYTES):
            digest.update(block)
    return digest.hexdigest()


def verify_archive(path: Path, archive_lock: dict[str, Any]) -> None:
    try:
        size = path.stat().st_size
    except OSError as error:
        raise DatasetPreparationError(f"Cannot inspect archive {path}: {error}") from error
    expected_size = int(archive_lock["size"])
    if size != expected_size:
        raise DatasetPreparationError(
            f"Archive size mismatch: expected {expected_size}, received {size}"
        )
    actual_hash = _sha256(path)
    expected_hash = str(archive_lock["sha256"]).casefold()
    if actual_hash != expected_hash:
        raise DatasetPreparationError(
            f"Archive SHA-256 mismatch: expected {expected_hash}, received {actual_hash}"
        )


def storage_preflight(
    target_root: Path,
    *,
    archive_present: bool,
    archive_size: int,
    extracted_size: int,
) -> dict[str, int | bool]:
    target_root.mkdir(parents=True, exist_ok=True)
    free_before = shutil.disk_usage(target_root).free
    required = extracted_size + (0 if archive_present else archive_size)
    projected_free = free_before - required
    result: dict[str, int | bool] = {
        "archive_present": archive_present,
        "archive_size_bytes": archive_size,
        "extracted_size_bytes": extracted_size,
        "free_before_bytes": free_before,
        "projected_free_bytes": projected_free,
        "minimum_free_bytes": MINIMUM_FREE_BYTES,
        "passed": projected_free >= MINIMUM_FREE_BYTES,
    }
    if not result["passed"]:
        raise DatasetPreparationError(
            "Storage preflight failed: extraction would leave less than 20 GiB free"
        )
    return result


def download_archive(destination: Path, archive_lock: dict[str, Any]) -> None:
    if destination.exists():
        verify_archive(destination, archive_lock)
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.parent / f".{destination.name}.{os.getpid()}.download"
    if temporary.exists():
        raise DatasetPreparationError(f"Refusing to overwrite temporary download {temporary}")
    request = urllib.request.Request(
        str(archive_lock["url"]),
        headers={"User-Agent": "Sheet2Play-Research"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response, temporary.open("xb") as output:
            shutil.copyfileobj(response, output, DOWNLOAD_BLOCK_BYTES)
        verify_archive(temporary, archive_lock)
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _safe_member_path(extraction_root: Path, member: tarfile.TarInfo, expected_root: str) -> Path:
    logical = PurePosixPath(member.name)
    if logical.is_absolute() or ".." in logical.parts or not logical.parts:
        raise DatasetPreparationError(f"Unsafe archive path: {member.name!r}")
    if logical.parts[0] != expected_root:
        raise DatasetPreparationError(
            f"Archive member is outside expected root {expected_root!r}: {member.name!r}"
        )
    if member.issym() or member.islnk() or member.isdev():
        raise DatasetPreparationError(f"Archive links/devices are forbidden: {member.name!r}")
    candidate = extraction_root.joinpath(*logical.parts).resolve()
    root = extraction_root.resolve()
    if candidate != root and root not in candidate.parents:
        raise DatasetPreparationError(f"Archive path escaped extraction root: {member.name!r}")
    return candidate


def inspect_archive(
    archive: Path,
    *,
    expected_root: str,
) -> tuple[list[tarfile.TarInfo], int, int]:
    with tarfile.open(archive, "r:gz") as bundle:
        members = bundle.getmembers()
        for member in members:
            _safe_member_path(Path.cwd(), member, expected_root)
        files = [member for member in members if member.isfile()]
        unsupported = [member.name for member in members if not member.isfile() and not member.isdir()]
        if unsupported:
            raise DatasetPreparationError(f"Unsupported archive member types: {unsupported[:3]}")
        return members, len(files), sum(member.size for member in files)


def _extract_verified_archive(archive: Path, output_parent: Path, lock: dict[str, Any]) -> Path:
    extracted_lock = lock["dataset"]["extracted"]
    expected_root = str(extracted_lock["root"])
    destination = output_parent / expected_root
    if destination.exists():
        return destination

    members, file_count, extracted_size = inspect_archive(
        archive,
        expected_root=expected_root,
    )
    if file_count != int(extracted_lock["file_count"]) or extracted_size != int(
        extracted_lock["size"]
    ):
        raise DatasetPreparationError(
            "Archive table does not match the locked extracted file count and size"
        )

    temporary_root = Path(
        tempfile.mkdtemp(prefix=".olimpic-extract-", dir=output_parent)
    ).resolve()
    try:
        with tarfile.open(archive, "r:gz") as bundle:
            for member in members:
                target = _safe_member_path(temporary_root, member, expected_root)
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                source = bundle.extractfile(member)
                if source is None:
                    raise DatasetPreparationError(f"Cannot read archive member {member.name!r}")
                with source, target.open("xb") as output:
                    shutil.copyfileobj(source, output, DOWNLOAD_BLOCK_BYTES)
        extracted = temporary_root / expected_root
        if not extracted.is_dir():
            raise DatasetPreparationError("Archive did not create its locked root directory")
        extracted.replace(destination)
        return destination
    finally:
        if temporary_root.exists():
            shutil.rmtree(temporary_root)


def verify_dataset(root: Path, extracted_lock: dict[str, Any]) -> dict[str, Any]:
    partition = root / "samples.test.txt"
    try:
        sample_names = [line.strip() for line in partition.read_text(encoding="utf-8").splitlines() if line.strip()]
    except OSError as error:
        raise DatasetPreparationError(f"Cannot read test partition {partition}: {error}") from error
    if len(sample_names) != int(extracted_lock["test_system_count"]):
        raise DatasetPreparationError(
            f"Expected {extracted_lock['test_system_count']} test systems, found {len(sample_names)}"
        )
    if len(set(sample_names)) != len(sample_names):
        raise DatasetPreparationError("Test partition contains duplicate sample identifiers")

    score_ids: set[str] = set()
    missing: list[str] = []
    for sample_name in sample_names:
        logical = PurePosixPath(sample_name)
        if logical.is_absolute() or ".." in logical.parts or len(logical.parts) != 3:
            raise DatasetPreparationError(f"Invalid test sample path {sample_name!r}")
        base = root.joinpath(*logical.parts)
        score_ids.add(logical.parts[1])
        for suffix in (".png", ".lmx", ".musicxml"):
            if not base.with_suffix(suffix).is_file():
                missing.append(str(base.with_suffix(suffix)))
    if missing:
        raise DatasetPreparationError(f"Test partition is missing assets: {missing[:3]}")
    if len(score_ids) != int(extracted_lock["test_score_count"]):
        raise DatasetPreparationError(
            f"Expected {extracted_lock['test_score_count']} test scores, found {len(score_ids)}"
        )
    return {
        "dataset_root": str(root.resolve()),
        "test_system_count": len(sample_names),
        "test_score_count": len(score_ids),
        "triplets_valid": True,
    }


def prepare(lock_path: Path, data_root: Path, *, allow_download: bool) -> dict[str, Any]:
    lock = _read_lock(lock_path)
    archive_lock = lock["dataset"]["archive"]
    extracted_lock = lock["dataset"]["extracted"]
    archive = data_root / "archives" / str(archive_lock["name"])
    preflight = storage_preflight(
        data_root,
        archive_present=archive.is_file(),
        archive_size=int(archive_lock["size"]),
        extracted_size=int(extracted_lock["size"]),
    )
    print(json.dumps({"storage_preflight": preflight}, sort_keys=True), flush=True)
    if not archive.is_file() and not allow_download:
        raise DatasetPreparationError(
            f"Locked archive is missing: {archive}. Re-run with --download."
        )
    if allow_download:
        download_archive(archive, archive_lock)
    verify_archive(archive, archive_lock)
    dataset_root = _extract_verified_archive(archive, data_root, lock)
    verification = verify_dataset(dataset_root, extracted_lock)
    return {
        "schema_version": 1,
        "lock": str(lock_path.resolve()),
        "archive": str(archive.resolve()),
        "archive_sha256": _sha256(archive),
        "storage_preflight": preflight,
        **verification,
    }


def _parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Prepare the locked OLiMPiC scanned dataset")
    parser.add_argument("--lock", type=Path, default=root / "olimpic.lock.json")
    parser.add_argument("--data-root", type=Path, default=root / "data" / "olimpic")
    parser.add_argument("--download", action="store_true")
    return parser.parse_args()


def main() -> int:
    try:
        args = _parse_args()
        result = prepare(args.lock, args.data_root, allow_download=args.download)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except DatasetPreparationError as error:
        print(json.dumps({"error": str(error)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
