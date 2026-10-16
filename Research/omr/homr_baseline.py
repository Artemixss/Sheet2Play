"""Offline Phase 1 runtime attribution and authoritative development-input audit."""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[1]
sys.path.insert(0, str(HERE / "src"))

from sheet2play_omr.phase2r_development import development_records, _verify_input


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def file_identity(path: Path) -> dict:
    return {"path": str(path.resolve()), "bytes": path.stat().st_size,
            "sha256": digest(path)}


def save(path: Path, value: dict | list) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def resolve_python(bridge: Path) -> Path:
    for directory in (bridge.parent, *bridge.parent.parents):
        candidate = directory / "Bridge/.venv-homr-gpu/Scripts/python.exe"
        if candidate.is_file():
            return candidate
        candidate = directory / ".venv-homr-gpu/Scripts/python.exe"
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("Installed HOMR Python could not be resolved")


PROBE = '''import importlib.util, importlib.metadata, json, sys
from pathlib import Path
import sitecustomize
if not sitecustomize.INSTALLED:
    raise RuntimeError("Offline gate missing")
spec = importlib.util.find_spec("homr")
if spec is None or spec.origin is None:
    raise RuntimeError("HOMR import not resolved")
import homr.transformer.configs as configs
import homr.segmentation.config as segmentation
import homr.music_xml_generator as exporter
import homr.transformer.vocabulary as vocabulary
config = configs.Config()
packages = {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()}
print(json.dumps({"python":sys.executable,"prefix":sys.prefix,"version":sys.version,
    "homr_origin":spec.origin,"packages":packages,
    "module_origins":{"configs":configs.__file__,"segmentation":segmentation.__file__,
        "exporter":exporter.__file__,"vocabulary":vocabulary.__file__},
    "selected_weights":[config.filepaths.encoder_path_fp16,
        config.filepaths.decoder_path_fp16, segmentation.segnet_path_onnx_fp16],
    "config":{k:v for k,v in vars(config).items() if isinstance(v,(str,int,float,bool))},
    "ordered_vocabulary":{k:v for k,v in vars(config.vocab).items()
        if isinstance(v,(list,dict,tuple,str,int))}}))'''


def inventory(output: Path) -> dict:
    bridge = WORKSPACE / "dist/Bridge/bridge.py"
    python = resolve_python(bridge)
    completed = subprocess.run([str(python), "-B", "-c", PROBE], cwd=bridge.parent,
                               capture_output=True, text=True, timeout=120, check=True)
    probe = json.loads(completed.stdout)
    root = Path(probe["homr_origin"]).parent
    source = [file_identity(p) for p in sorted(root.rglob("*.py"))]
    models = [file_identity(Path(p)) for p in probe["selected_weights"]]
    tokenizers = [file_identity(p) for p in sorted((root / "transformer").glob("tokenizer*.json"))]
    bridge_files = [file_identity(p) for p in sorted(bridge.parent.glob("*.py"))]
    comparisons = []
    vendor = HERE / "vendor/homr/homr"
    for item in source:
        live = Path(item["path"])
        other = vendor / live.relative_to(root)
        if other.is_file() and digest(other) != item["sha256"]:
            comparisons.append({"relative_path": str(live.relative_to(root)),
                                "installed_sha256": item["sha256"],
                                "local_vendor_sha256": digest(other)})
            if live.name in {"music_xml_generator.py", "vocabulary.py"}:
                patch = "".join(difflib.unified_diff(
                    other.read_text(encoding="utf-8").splitlines(True),
                    live.read_text(encoding="utf-8").splitlines(True),
                    fromfile=str(other), tofile=str(live)))
                (output / (live.stem + ".local-vendor.diff")).write_text(patch, encoding="utf-8")
    result = {"probe": probe, "python": file_identity(python),
              "executable": file_identity(WORKSPACE / "dist/Sheet2Play.exe"),
              "installed_bridge": bridge_files, "homr_source": source,
              "active_weights": models, "tokenizers": tokenizers,
              "local_vendor_differences": comparisons,
              "vendor_comparison_limit": "Local vendor is a comparator, not proven original release bytes",
              "environment_switches": {name: os.environ.get(name) for name in (
                  "SHEET2PLAY_HOMR_KEEP_TUPLETS", "PYTHONPATH", "CUDA_VISIBLE_DEVICES")},
              "source_matches_published_bridge": all(
                  digest(WORKSPACE / "Bridge" / Path(row["path"]).name) == row["sha256"]
                  for row in bridge_files if (WORKSPACE / "Bridge" / Path(row["path"]).name).is_file()),
              "inference": {"provider": "CUDAExecutionProvider", "gpu": "force",
                            "pdf_dpi": 300, "default_bpm": 120,
                            "tuplet_cleanup_disabled": os.environ.get("SHEET2PLAY_HOMR_KEEP_TUPLETS") == "1"}}
    result["identity_sha256"] = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
    save(output / "runtime-inventory.json", result)
    return result


def eligibility(output: Path) -> list[dict]:
    audit_path = HERE / "reports/phase2r/development-audit-v2.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    previous = {r["item_id"]: r for r in audit["development_items"]}
    rows = []
    for record in development_records(WORKSPACE):
        _verify_input(record)
        old = previous[record.item_id]
        if old["image_sha256"] != record.image_sha256 or old["reference_sha256"] != record.reference_sha256:
            raise ValueError(f"Audit identity mismatch: {record.item_id}")
        page_starts = []
        if record.reference_format == "musicxml":
            tree = ET.parse(record.reference)
            for part in tree.getroot().findall("part"):
                page_starts.append([m.attrib.get("number") for m in part.findall("measure")
                                    if any(p.get("new-page") == "yes" for p in m.findall("print"))])
        generated = record.collection == "generated"
        rows.append({"item_id": record.item_id, "collection": record.collection,
                     "image": file_identity(record.image), "reference": file_identity(record.reference),
                     "reference_format": record.reference_format, "all_pages_hash_verified": True,
                     "audit_sha256": digest(audit_path), "reference_page_break_measures": page_starts,
                     "eligibility": "paired_generated_source" if generated else "diagnostic_only",
                     "numeric_accuracy_eligible": generated,
                     "alignment_evidence": "Single generated page with authoritative paired source; no token round-trip reference"
                        if generated else "Whole-composition notation; first-page range not independently verified",
                     "limitations": [] if generated else ["possible training overlap", "first-page reference range unverified"],
                     "traits": old["features"]})
    save(output / "reference-eligibility.json", rows)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.output.is_dir():
        raise FileNotFoundError(args.output)
    import sitecustomize
    if not getattr(sitecustomize, "INSTALLED", False):
        raise RuntimeError("Offline startup gate is mandatory")
    runtime = inventory(args.output)
    rows = eligibility(args.output)
    print(json.dumps({"runtime_identity": runtime["identity_sha256"], "development_items": len(rows),
                      "generated": sum(r["numeric_accuracy_eligible"] for r in rows),
                      "open_diagnostic_only": sum(not r["numeric_accuracy_eligible"] for r in rows)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
