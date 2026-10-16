"""Reuse the already-local supervisor dependency in the matching app interpreter."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil
import subprocess
import sys


def install() -> None:
    workspace = Path(__file__).resolve().parents[2]
    target = workspace / "Bridge/.venv-homr-gpu/Lib/site-packages"
    python = workspace / "Bridge/.venv-homr-gpu/Scripts/python.exe"
    signature = 'import json,sys,struct;print(json.dumps([list(sys.version_info[:3]),struct.calcsize("P")]))'
    actual = json.loads(subprocess.check_output([str(python), "-B", "-c", signature], text=True))
    expected = json.loads(subprocess.check_output([sys.executable, "-B", "-c", signature], text=True))
    if actual != expected or importlib.metadata.version("psutil") != "7.2.2":
        raise RuntimeError("Local psutil reuse requires identical Python ABI and pinned version")
    source = Path(importlib.metadata.distribution("psutil").locate_file(""))
    rows = []
    for name in ("psutil", "psutil-7.2.2.dist-info"):
        origin, destination = source / name, target / name
        if destination.exists():
            raise FileExistsError(f"Refusing to replace existing package: {destination}")
        for path in sorted(origin.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                rows.append({"path": str(path.relative_to(source)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        shutil.copytree(origin, destination, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for row in rows:
        if hashlib.sha256((target / row["path"]).read_bytes()).hexdigest() != row["sha256"]:
            raise RuntimeError("Local psutil copy failed verification")
    subprocess.run([str(python), "-B", "-c", 'import psutil; assert psutil.__version__ == "7.2.2"; print(psutil.Process().memory_info())'], check=True)
    print(json.dumps({"python_signature": actual, "version": "7.2.2", "verified_files": rows}))


if __name__ == "__main__":
    install()
