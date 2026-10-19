"""Provision the app's HOMR 480 runtime and re-pin both native profiles.

`plans/2026-10-17-upstream-exporter-480.md`, adoption, chosen by the user on 2026-10-19 ("make
480 default and 465 as secondary"). Copies the acquired run 480 encoder and decoder, upstream
main `ab369ac` and 465's segnet into `Bridge/.runtime/homr-480`, each checked against its
recorded hash, and writes `Bridge/homr480-profile.json` in the 465 profile's format. Adding the
engine changed `bridge.py`, which 465's profile pins, so 465's Bridge hashes are refreshed too:
that is the deliberate 465 identity bump. Nothing is overwritten that differs.

    Bridge\\.venv-homr-gpu\\Scripts\\python.exe -I -B Research/omr/homr480_provision.py
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[1]
BRIDGE = WORKSPACE / "Bridge"
ACQUIRED = HERE / ".runtime/homr-480-upstream"
ACQUISITION = HERE / "reports/upstream-480/acquisition/acquisition.json"
RUNTIME = BRIDGE / ".runtime/homr-480"
PROFILE_465 = BRIDGE / "homr465-profile.json"
PROFILE_480 = BRIDGE / "homr480-profile.json"
SHARED_BRIDGE = ["bridge.py", "render_pdf.py", "progress_protocol.py", "musicxml_normalizer.py", "homr_gpu.py"]
SAFETY = ["guarded_execution.py", "guarded_worker.py", "execution_safety/__init__.py",
          "execution_safety/execution_resources.py", "execution_safety/safety_policy.py",
          "execution_safety/windows_job.py"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_profile(path: Path, profile: dict) -> None:
    # The 465 profile's own format: two-space JSON, a final newline, CRLF line ends.
    path.write_bytes((json.dumps(profile, indent=2) + "\n").replace("\n", "\r\n").encode("utf-8"))


def copy_checked(origin: Path, target: Path, digest: str) -> None:
    if sha256(origin) != digest:
        raise ValueError(f"Input hash mismatch: {origin}")
    if target.exists():
        if sha256(target) != digest:
            raise FileExistsError(f"Refusing to overwrite differing runtime bytes: {target}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(origin, target)


def bridge_rows(names: list[str]) -> list[dict]:
    return [{"path": name, "sha256": sha256(BRIDGE / name)} for name in names]


def main() -> None:
    acquired = json.loads(ACQUISITION.read_text(encoding="utf-8"))
    profile_465 = json.loads(PROFILE_465.read_text(encoding="utf-8"))
    sources = [(ACQUIRED / row["path"], row["path"], row["sha256"]) for row in acquired["source_files"]]
    for name in ("LICENSE", "pyproject.toml"):
        sources.append((ACQUIRED / "source" / name, f"source/{name}", sha256(ACQUIRED / "source" / name)))
    for origin, relative, digest in sources:
        copy_checked(origin, RUNTIME / relative, digest)
    segnet = profile_465["models"]["segnet"]
    models = {}
    for kind, origin, digest in (
            ("encoder", ACQUIRED / acquired["models"]["encoder"]["path"], acquired["models"]["encoder"]["sha256"]),
            ("decoder", ACQUIRED / acquired["models"]["decoder"]["path"], acquired["models"]["decoder"]["sha256"]),
            ("segnet", BRIDGE / profile_465["runtime_directory"] / segnet["path"], segnet["sha256"])):
        relative = f"models/{origin.name}"
        copy_checked(origin, RUNTIME / relative, digest)
        models[kind] = {"path": relative, "sha256": digest}
    profile_480 = {key: profile_465[key] for key in profile_465}
    profile_480.update(
        bridge_files=bridge_rows(SHARED_BRIDGE + ["homr465_profile.py", "homr465_native.py", "homr480_profile.py",
                                                  "homr480_native.py"] + SAFETY),
        model_revision=acquired["model_id"] + "-fp16-encoder-fp32-decoder",
        models=models, runtime_directory=".runtime/homr-480",
        source_files=sorted(({"path": relative, "sha256": digest} for _, relative, digest in sources),
                            key=lambda row: row["path"]),
        source_revision=acquired["source_revision"])
    write_profile(PROFILE_480, profile_480)
    profile_465["bridge_files"] = bridge_rows([row["path"] for row in profile_465["bridge_files"]])
    write_profile(PROFILE_465, profile_465)
    print(json.dumps({"homr480_profile_sha256": sha256(PROFILE_480), "homr465_profile_sha256": sha256(PROFILE_465),
                      "homr480_source_files": len(sources)}))


if __name__ == "__main__":
    main()
