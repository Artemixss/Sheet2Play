"""Separate, fail-closed vocabulary/source/interface contract for upstream HOMR 465."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path
import sys

from homr_465_download import MODEL_ID, REVISION, save
from screening_homr_compatibility import HEADS, digest, model_interface, ordered_labels, require_equal, sha256_file

HERE = Path(__file__).resolve().parent


def checked_source(source: Path, acquisition: dict) -> dict[str, str]:
    require_equal("465 revision", acquisition["source_revision"], REVISION)
    require_equal("465 model ID", acquisition["model_id"], MODEL_ID)
    expected = {row["path"]: row["sha256"] for row in acquisition["source_files"] if row["path"].startswith("homr/")}
    observed = {path.relative_to(source).as_posix() for path in (source / "homr").rglob("*")
                if path.is_file() and "__pycache__" not in path.parts and path.suffix not in {".pyc", ".pyo"}}
    require_equal("465 source file inventory", sorted(observed), sorted(expected))
    for name, expected_hash in expected.items():
        require_equal("465 source " + name, sha256_file(source / name), expected_hash)
    return expected


def checked_origins(source: Path) -> dict[str, str]:
    modules = {name: str(Path(module.__file__).resolve()) for name, module in sys.modules.items()
               if (name == "homr" or name.startswith("homr.")) and getattr(module, "__file__", None)}
    if not modules or any(not Path(path).is_relative_to(source.resolve()) for path in modules.values()):
        raise ValueError("465 imported HOMR outside pinned source")
    return modules


def interface_requirements(models: dict, labels: dict, historical: dict) -> None:
    names = ["out_rhythms", "out_pitchs", "out_lifts", "out_positions", "out_articulations", "out_slurs"]
    outputs = models["decoder"]["outputs"]
    require_equal("465 six output heads", [row["name"] for row in outputs[:6]], names)
    for head, row in zip(HEADS, outputs[:6], strict=True):
        require_equal("465 " + head + " dimension", row["shape"], [1, 1, len(labels[head])])
        require_equal("465 " + head + " precision", row["type"], "tensor(float16)")
    for model_name in ("encoder", "decoder"):
        for direction in ("inputs", "outputs"):
            actual = models[model_name][direction]
            old = historical["models"][model_name][direction]
            require_equal(f"465 {model_name} {direction} count", len(actual), len(old))
            for observed, expected in zip(actual, old, strict=True):
                require_equal("465 interface name", observed["name"], expected["name"])
                require_equal("465 interface dtype", observed["type"], expected["type"])
                if observed["name"] == "out_positions":
                    continue
                require_equal("465 interface shape", observed["shape"], expected["shape"])


def inspect(source: Path, evidence: Path) -> dict:
    acquisition = json.loads((evidence / "acquisition.json").read_text(encoding="utf-8"))
    source_files = checked_source(source, acquisition)
    sys.path.insert(0, str(source.resolve()))
    from homr.transformer import configs
    config = configs.Config()
    historical = json.loads((HERE / "homr_455_contract.json").read_text(encoding="utf-8"))
    labels = {name: ordered_labels(name, getattr(config, f"{name}_vocab")) for name in HEADS}
    require_equal("465 position semantics", labels["position"], [".", "upper", "upper2", "lower", "lower2"])
    for name in HEADS:
        if name != "position":
            require_equal("465 " + name + " vocabulary", labels[name], historical["labels"][name])
    specials = {"pad": config.pad_token, "bos": config.bos_token, "eos": config.eos_token, "nonote": config.nonote_token}
    require_equal("465 special token IDs", specials, historical["special_tokens"])
    for kind in ("encoder", "decoder"):
        require_equal("465 configured " + kind, Path(getattr(config.filepaths, kind + "_path_fp16")).name, f"{kind}_pytorch_model_{MODEL_ID}_fp16.onnx")
    models = {}
    for name in ("encoder", "decoder"):
        row = acquisition["models"][name]
        path = Path(row["absolute_path"])
        require_equal("465 " + name + " model SHA-256", sha256_file(path), row["sha256"])
        models[name] = {"sha256": row["sha256"], **model_interface(path)}
    interface_requirements(models, labels, historical)
    versions = {name: importlib.metadata.version(name) for name in
                ("onnxruntime-gpu", "numpy", "opencv-python-headless", "Pillow", "rapidocr", "requests", "pypdfium2", "typing_extensions")}
    return {"schema_version": 1, "candidate": "homr-465-upstream", "source_revision": REVISION,
            "source_archive_sha256": acquisition["source_archive"]["sha256"], "source_files": source_files,
            "model_id": MODEL_ID, "labels": labels, "special_tokens": specials, "models": models,
            "ordered_label_sha256": {name: digest(value) for name, value in labels.items()},
            "tokenizer_sha256": {name: sha256_file(source / f"homr/transformer/tokenizer_{name}.json") for name in ("rhythm", "lift", "pitch", "note")},
            "python_executable": sys.executable, "python_prefix": sys.prefix, "package_versions": versions,
            "origins": checked_origins(source)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--create", action="store_true")
    args = parser.parse_args()
    observed = inspect(args.source.resolve(), args.evidence)
    if args.create:
        if args.contract.exists():
            raise ValueError("Refuse to overwrite an existing 465 contract")
        save(args.contract, observed)
    else:
        require_equal("465 complete compatibility contract", observed, json.loads(args.contract.read_text(encoding="utf-8")))
    report = {"status": "compatible", "contract_sha256": sha256_file(args.contract),
              "validator_sha256": sha256_file(Path(__file__)), "source_revision": REVISION,
              "six_heads": {name: len(observed["labels"][name]) for name in HEADS},
              "model_sha256": {name: observed["models"][name]["sha256"] for name in ("encoder", "decoder")}}
    save(args.evidence / ("compatibility-created.json" if args.create else "compatibility-verified.json"), report)
    print(json.dumps(report))


if __name__ == "__main__":
    main()
