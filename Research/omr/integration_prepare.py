"""Export portable safety code and a separate app profile from frozen local bytes."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
BRIDGE = HERE.parents[1] / "Bridge"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare() -> None:
    package = BRIDGE / "execution_safety"
    package.mkdir(exist_ok=True)
    (package / "__init__.py").write_text('', encoding="utf-8")
    for name in ("execution_resources.py", "safety_policy.py", "windows_job.py"):
        shutil.copyfile(HERE / "src/sheet2play_omr" / name, package / name)
    shutil.copyfile(HERE / "guarded_worker.py", BRIDGE / "guarded_worker.py")
    text = (HERE / "guarded_execution.py").read_text(encoding="utf-8")
    text = text.replace("from sheet2play_omr.", "from execution_safety.")
    text = text.replace('WORKSPACE = HERE.parents[1]', 'WORKSPACE = HERE.parent')
    text = text.replace('HERE / "src/sheet2play_omr"', 'HERE / "execution_safety"')
    (BRIDGE / "guarded_execution.py").write_text(text, encoding="utf-8")
    frozen = json.loads((HERE / "reports/homr-timing-465/phase2/candidate-configuration.json").read_text(encoding="utf-8"))
    source = Path(frozen["source"])
    source_files = [{"path": "source/" + Path(row["path"]).relative_to(source).as_posix(), "sha256": row["sha256"]}
                    for row in frozen["source_files"]]
    for name in ("LICENSE", "pyproject.toml"):
        source_files.append({"path": "source/" + name, "sha256": sha256(source / name)})
    models = {name: {"path": "models/" + Path(row["path"]).name, "sha256": row["sha256"]}
              for name, row in {**frozen["models"], "segnet": frozen["segnet"]}.items()}
    bridge_paths = [BRIDGE / name for name in ("bridge.py", "render_pdf.py", "progress_protocol.py", "musicxml_normalizer.py", "homr_gpu.py", "homr465_profile.py",
                    "homr465_native.py", "guarded_execution.py", "guarded_worker.py")]
    bridge_paths.extend(sorted(package.glob("*.py")))
    profile = {"schema_version": 1, "source_revision": "33baa326900faa12702df8c4bdcbea034a3d6a34",
               "model_revision": "465-597144cab54c8f6d0f6c9619df5c5312694eadd6-fp16",
               "runtime_directory": ".runtime/homr-465", "source_files": source_files, "models": models,
               "provider": frozen["provider"], "threads": 8, "inter_op_threads": 1, "pdf_dpi": 300,
               "processing": frozen["processing"], "package_versions": {**frozen["package_versions"], "music21": "10.5.0", "psutil": "7.2.2",
                   **{d.metadata["Name"]: d.version for d in importlib.metadata.distributions() if d.metadata["Name"].lower().startswith("nvidia-")}},
               "bridge_files": [{"path": path.relative_to(BRIDGE).as_posix(), "sha256": sha256(path)} for path in bridge_paths]}
    profile_path = BRIDGE / "homr465-profile.json"
    profile_path.write_text(json.dumps(profile, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (BRIDGE / "requirements-homr465.txt").write_text(
        "".join(f"{name}=={version}\n" for name, version in sorted(profile["package_versions"].items())), encoding="utf-8")
    import sys
    sys.path.insert(0, str(BRIDGE))
    from setup_homr465 import provision
    provision(source, Path(frozen["models"]["encoder"]["path"]), Path(frozen["models"]["decoder"]["path"]), Path(frozen["segnet"]["path"]))


if __name__ == "__main__":
    prepare()
