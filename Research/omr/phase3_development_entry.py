"""Run one frozen development item through a Phase-3 candidate entry path."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from phase2 import WORKSPACE, development_inputs
from phase2r import verify_historical_artifacts
from sheet2play_omr.adapter_contract import AdapterInput, sha256_file, write_result
from sheet2play_omr.phase2_adapters import AudiverisAdapter, ShippedHomrAdapter, ZeusAdapter
from sheet2play_omr.phase2r_validation import run_with_typed_failure


HERE = Path(__file__).resolve().parent


def _adapter(name: str) -> tuple[object, AdapterInput]:
    crop, page = development_inputs()
    if name == "homr_page":
        return ShippedHomrAdapter(WORKSPACE), page
    if name == "zeus_page":
        return ZeusAdapter(WORKSPACE, integration=True), page
    if name == "zeus_system":
        return ZeusAdapter(WORKSPACE, integration=False), crop
    if name == "audiveris_page":
        executable = HERE / ".runtime" / "phase2r" / "audiveris-extract" / "Audiveris" / "Audiveris.exe"
        os.environ["SHEET2PLAY_AUDIVERIS_EXECUTABLE"] = str(executable.resolve())
        return AudiverisAdapter(WORKSPACE), page
    raise ValueError(f"Unknown development entry: {name}")


def _source_paths(name: str) -> list[Path]:
    shared = [
        HERE / "src" / "sheet2play_omr" / "phase2_adapters.py",
        HERE / "src" / "sheet2play_omr" / "adapter_contract.py",
        HERE / "src" / "sheet2play_omr" / "phase2r_validation.py",
        WORKSPACE / "Bridge" / "musicxml_normalizer.py",
    ]
    if name == "homr_page":
        return shared + [WORKSPACE / "Bridge" / "homr_gpu.py"]
    if name.startswith("zeus_"):
        model = HERE / "zeus" / "weights" / "zeus-olimpic-1.0-2024-02-12.model"
        return shared + [HERE / "phase2_zeus_runner.py", HERE / "zeus" / "infer_batch.py",
                         model / "weights.h5", model / "options.json", model / "tags.txt",
                         WORKSPACE / "Bridge" / "detect_systems.py"]
    return shared + [HERE / ".runtime" / "phase2r" / "audiveris-extract" / "Audiveris" / "Audiveris.exe"]


def _identity(name: str, adapter: object, item: AdapterInput) -> tuple[str, dict[str, Any]]:
    files = {path.resolve().relative_to(WORKSPACE).as_posix(): sha256_file(path)
             for path in _source_paths(name)}
    payload = {
        "candidate": name,
        "adapter_config_sha256": adapter.config.sha256,  # type: ignore[attr-defined]
        "input_sha256": item.input_sha256,
        "files": files,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    return digest, payload


def run_entry(name: str) -> Path:
    verify_historical_artifacts()
    adapter, item = _adapter(name)
    item.validate()
    if not adapter.probe()["available"]:  # type: ignore[attr-defined]
        raise RuntimeError(f"Development runtime unavailable: {name}")
    digest, identity = _identity(name, adapter, item)
    stem = f"{name}-{item.item_id}-{digest[:12]}"
    report = HERE / "reports" / "phase3" / "development-entry" / f"{stem}.json"
    output = HERE / ".runtime" / "phase3" / "development-entry" / stem
    if report.exists() or output.exists():
        raise FileExistsError(f"Entry evidence already exists; inspect it before retrying: {stem}")
    report.parent.mkdir(parents=True, exist_ok=True)
    result = run_with_typed_failure(adapter, item, output)
    write_result(report, result)
    identity_path = report.with_suffix(".identity.json")
    identity_path.write_text(json.dumps(identity, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"name": name, "status": result.status.value, "error": result.error,
                      "report": str(report), "identity_sha256": digest}, sort_keys=True), flush=True)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", choices=("homr_page", "zeus_page", "zeus_system", "audiveris_page"))
    args = parser.parse_args()
    run_entry(args.name)


if __name__ == "__main__":
    main()
