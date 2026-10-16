"""Verify local OMR runtime files without trusting declared config revisions alone."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Iterable

from .adapter_contract import portable_path, sha256_file


EXPECTED_GGUF_SHA256 = {
    "rokot-omr-2b-Q8_0.gguf": "df53948ada1a4a584b4c7c81cc7e3293d3457f2e5ec9688271693459eb950f25",
    "mmproj-rokot-omr-2b-f16.gguf": "1074d47f6fd864bffa9d8843bbae30e6aa696ad0d55535ebd77053d81c699bd0",
    "Qwen3VL-2B-Instruct-Q8_0.gguf": "1e8db19207c8ce0733ddd78c2eff8a9e22c27c82f4443df94c25792ed8fe04f2",
    "mmproj-Qwen3VL-2B-Instruct-Q8_0.gguf": "f9a68fabba69c3b81e153367b2c7521030b0fa8bb0de400c9599c8e6725f9c82",
}
EXPECTED_CROMA_SHA256 = "d20ed24cb4682594abbcfc92537dfa26bb60464c0fb5d99d274b16a903cf5e24"
EXPECTED_LLAMA_CLI_SHA256 = "252d8c9a02c20aa7263a38fea69182e3658779f368baaeb57610bfd90e084b9e"
EXPECTED_CUDA_ARCHIVE_SHA256 = "8c79a9b226de4b3cacfd1f83d24f962d0773be79f1e7b75c6af4ded7e32ae1d6"
EXPECTED_CUDA_DLL_SHA256 = {
    "cudart64_12.dll": "d28e42265da7462162a54da6b7a99ea4fa2caf8139d862bb500db875d0b32dfc",
    "cublas64_12.dll": "e40202fe4223c1cd2d2dce7beec59e1ed61c7801bd827309183be9b50e358f4c",
    "cublasLt64_12.dll": "2a896460bef60ed57ef32b0875812f355a6984e671d638bb632f5e8c1d7a831f",
}
EXPECTED_AUDIVERIS_MSI_SHA256 = "5f1b4e96a12c53c7da426814b76e599363c4181e291855996e0a6878dda95f71"
EXPECTED_AUDIVERIS_EXE_SHA256 = "06dbf3b4a5acd4dbbefcf9dfbcef43529ad6afde4ba9330cb856d849cd7fe172"


def file_identity(
    path: Path, *, expected_sha256: str | None = None, expected_bytes: int | None = None
) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size == 0:
        return {
            "path": portable_path(path), "status": "missing",
            "expected_sha256": expected_sha256, "expected_bytes": expected_bytes,
        }
    size = path.stat().st_size
    if expected_bytes is not None and size != expected_bytes:
        return {
            "path": portable_path(path), "status": "incomplete",
            "bytes": size, "expected_bytes": expected_bytes,
        }
    try:
        actual = sha256_file(path)
    except OSError:
        return {"path": portable_path(path), "status": "in_use", "bytes": size}
    return {
        "path": portable_path(path),
        "status": (
            "hashed" if expected_sha256 is None else
            "verified" if actual == expected_sha256 else "hash_mismatch"
        ),
        "sha256": actual,
        "expected_sha256": expected_sha256,
        "bytes": size,
    }


def source_tree_identity(root: Path, files: Iterable[Path]) -> dict[str, Any]:
    records = [
        {"path": path.relative_to(root).as_posix(), "sha256": sha256_file(path)}
        for path in sorted(files)
        if path.is_file()
    ]
    payload = json.dumps(records, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "root": portable_path(root),
        "file_count": len(records),
        "source_tree_sha256": hashlib.sha256(payload).hexdigest(),
        "files": records,
    }


def executable_version(path: Path, args: tuple[str, ...] = ("--version",)) -> dict[str, Any]:
    if not path.is_file():
        return {"status": "missing"}
    try:
        result = subprocess.run(
            [str(path), *args], check=False, capture_output=True, text=True,
            timeout=20, encoding="utf-8", errors="replace",
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"status": "failed", "error": type(error).__name__}
    return {
        "status": "verified" if result.returncode == 0 else "failed",
        "exit_status": result.returncode,
        "version_output": (result.stdout + result.stderr).strip()[:300],
    }


def _homr_identity(workspace: Path) -> dict[str, Any]:
    installed = workspace / "Bridge" / ".venv-homr-gpu" / "Lib" / "site-packages"
    package = installed / "homr"
    distributions = sorted(installed.glob("homr-*.dist-info"))
    direct_url = distributions[0] / "direct_url.json" if distributions else None
    provenance = (
        json.loads(direct_url.read_text(encoding="utf-8"))
        if direct_url is not None and direct_url.is_file() else None
    )
    model_paths = sorted((package / "segmentation").glob("*.onnx"))
    model_paths += sorted((package / "transformer").glob("*.onnx"))
    tokenizers = sorted((package / "transformer").glob("tokenizer_*.json"))
    source_files = list(package.rglob("*.py"))
    return {
        "package_source": provenance,
        "source_revision_verified": (
            provenance is not None
            and provenance.get("vcs_info", {}).get("commit_id")
            == "457e7c6518a10ba755db2e60883419e56c4d7369"
        ),
        "local_source": source_tree_identity(package, source_files),
        "bridge_patch": file_identity(workspace / "Bridge" / "homr_gpu.py"),
        "weights": [file_identity(path) for path in model_paths],
        "tokenizers": [file_identity(path) for path in tokenizers],
        "weight_count": len(model_paths),
        "tokenizer_count": len(tokenizers),
    }


def _zeus_identity(workspace: Path) -> dict[str, Any]:
    zeus = workspace / "Research" / "omr" / "zeus"
    model = zeus / "weights" / "zeus-olimpic-1.0-2024-02-12.model"
    return {
        "checkpoint": {
            "weights": file_identity(model / "weights.h5"),
            "options": file_identity(model / "options.json"),
            "tags": file_identity(model / "tags.txt"),
        },
        "local_source": source_tree_identity(zeus, zeus.glob("*.py")),
        "runner": file_identity(workspace / "Research" / "omr" / "phase2_zeus_runner.py"),
        "detector": file_identity(workspace / "Bridge" / "detect_systems.py"),
    }


def _git_state(root: Path) -> dict[str, Any]:
    if not (root / ".git").exists():
        return {"status": "missing"}
    head = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"], check=False,
        capture_output=True, text=True, timeout=20,
    )
    state = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain"], check=False,
        capture_output=True, text=True, timeout=20,
    )
    return {
        "status": "verified" if head.returncode == 0 and state.returncode == 0 else "failed",
        "head": head.stdout.strip() or None,
        "clean": state.returncode == 0 and not state.stdout.strip(),
        "changed_file_count": len(state.stdout.splitlines()),
    }


def collect_identity(workspace: Path) -> dict[str, Any]:
    runtime = workspace / "Research" / "omr" / ".runtime" / "phase2r"
    legato = runtime / "legato-source"
    files = {
        name: file_identity(
            path,
            expected_sha256=(
                EXPECTED_GGUF_SHA256.get(path.name)
                or EXPECTED_CUDA_DLL_SHA256.get(path.name)
                or {"croma": EXPECTED_CROMA_SHA256,
                    "llama_cli": EXPECTED_LLAMA_CLI_SHA256,
                    "cuda_archive": EXPECTED_CUDA_ARCHIVE_SHA256,
                    "audiveris_installer": EXPECTED_AUDIVERIS_MSI_SHA256,
                    "audiveris_executable": EXPECTED_AUDIVERIS_EXE_SHA256}.get(name)
            ),
            expected_bytes={
                "audiveris_installer": 85062430,
                "cuda_archive": 391443627,
            }.get(name),
        )
        for name, path in {
            "rokot_q8": runtime / "rokot" / "rokot-omr-2b-Q8_0.gguf",
            "rokot_projector": runtime / "rokot" / "mmproj-rokot-omr-2b-f16.gguf",
            "qwen_q8": runtime / "qwen" / "Qwen3VL-2B-Instruct-Q8_0.gguf",
            "qwen_projector": runtime / "qwen" / "mmproj-Qwen3VL-2B-Instruct-Q8_0.gguf",
            "llama_cli": runtime / "llama-b11124" / "llama-mtmd-cli.exe",
            "cuda_archive": runtime / "llama-b11124" / "cudart-llama-bin-win-cuda-12.4-x64.zip",
            "cuda_runtime": runtime / "llama-b11124" / "cudart64_12.dll",
            "cuda_blas": runtime / "llama-b11124" / "cublas64_12.dll",
            "cuda_blas_lt": runtime / "llama-b11124" / "cublasLt64_12.dll",
            "croma": runtime / "croma" / "croma-windows-x86_64.exe",
            "audiveris_installer": runtime / "audiveris" / "Audiveris-5.11.0-windowsConsole-x86_64.msi",
            "audiveris_executable": runtime / "audiveris-extract" / "Audiveris" / "Audiveris.exe",
            "legato_converter": legato / "utils" / "abc2xml.py",
            "musescore": Path("C:/Program Files/MuseScore 4/bin/MuseScore4.exe"),
        }.items()
    }
    return {
        "schema_version": 1,
        "homr": _homr_identity(workspace),
        "zeus": _zeus_identity(workspace),
        "legato_source": _git_state(legato),
        "files": files,
        "converter_version": executable_version(runtime / "croma" / "croma-windows-x86_64.exe"),
        "llama_version": executable_version(runtime / "llama-b11124" / "llama-mtmd-cli.exe"),
        "llama_devices": executable_version(
            runtime / "llama-b11124" / "llama-mtmd-cli.exe", ("--list-devices",)
        ),
        "audiveris_version": executable_version(
            runtime / "audiveris-extract" / "Audiveris" / "Audiveris.exe", ("-version",)
        ),
    }
