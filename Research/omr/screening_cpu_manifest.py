"""Pin fully readable CPU execution without rewriting historical freezes."""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from typing import Any

from phase3_freeze import snapshot
from screening_common import (HERE, REPORTS, WORKSPACE, FROZEN, POLICY, digest,
                              read_json, write_new, threads_limit)
from screening_common import screening_adapter as base_adapter
from screening_cpu_profile import cpu_environment
from sheet2play_omr.adapter_contract import sha256_file

BASE = REPORTS / "manifest-v4-309c090225de.json"
BASE_SHA256 = "f8f1c6a08caa30b63d3e31c3f11c7e2cc74643b977429e50152007c0504fb5ea"
CPU_CANDIDATES = ("audiveris_page", "zeus_page")
CPU_SOURCES = ("screening_cpu_manifest.py", "screening_cpu_profile.py",
               "screening_cpu_development.py", "screening_cpu_run.py", "screening_cpu_score.py", "screening_cpu_admit.py")


def require_inventory_extension(historical: dict[str, Any], current: dict[str, Any]) -> None:
    left, right = deepcopy(historical), deepcopy(current)
    old_inventory = left["runtime"].pop("python_distributions")
    new_inventory = right["runtime"].pop("python_distributions")
    if left != right or set(old_inventory) != set(new_inventory):
        raise ValueError("Historical source, model, input, parser or non-inventory runtime changed")
    for runtime, packages in old_inventory.items():
        if any(new_inventory[runtime].get(name) != version for name, version in packages.items()):
            raise ValueError("Historical installed package was removed or its version changed")


def screening_adapter(name: str, threads: int, runner_sha256: str):
    if name not in CPU_CANDIDATES:
        raise ValueError("Readable CPU profile supports Audiveris and neutral Zeus only")
    adapter = base_adapter(name, threads, runner_sha256)
    adapter.config = replace(adapter.config, settings={**adapter.config.settings,
        "cpu_environment": cpu_environment(threads), "execution_context": "fully_readable_local",
        "cpu_profile_sha256": sha256_file(HERE / "screening_cpu_profile.py")})
    return adapter


def build_manifest() -> dict[str, Any]:
    if sha256_file(BASE) != BASE_SHA256:
        raise ValueError("Preserved sample source manifest changed")
    historical, current = read_json(FROZEN), snapshot()
    require_inventory_extension(historical, current)
    result = deepcopy(read_json(BASE))
    for key, path in (("frozen_primary_manifest_sha256", HERE / "reports/phase1/smb-pianoform.jsonl"),
                      ("scoring_protocol_sha256", HERE / "reports/phase1/scoring-protocol.json"),
                      ("scorer_sha256", HERE / "src/sheet2play_omr/phase3_scoring.py"),
                      ("scoring_summary_sha256", HERE / "phase3_score.py"),
                      ("historical_phase3_freeze_sha256", FROZEN)):
        if result[key] != sha256_file(path):
            raise ValueError(f"Frozen contract changed: {key}")
    for item in result["items"]:
        for path_key, hash_key in (("image_path", "image_sha256"), ("reference_path", "reference_sha256")):
            if sha256_file(WORKSPACE / item[path_key]) != item[hash_key]:
                raise ValueError(f"Frozen screening input changed: {item['id']}")
    candidates = {}
    runner = sha256_file(HERE / "screening_cpu_run.py")
    for name in CPU_CANDIDATES:
        identity = deepcopy(result["candidates"][name]["identity"])
        for path, expected in identity["source_files"].items():
            if sha256_file(WORKSPACE / path) != expected:
                raise ValueError(f"Historical candidate source changed: {path}")
        adapter = screening_adapter(name, threads_limit(), runner)
        identity.update(adapter_config=adapter.config.to_json(), adapter_config_sha256=adapter.config.sha256,
                        worker_source_sha256=runner, readable_runtime=current["runtime"],
                        execution_context="fully_readable_local")
        identity["source_files"].update({str((HERE / path).relative_to(WORKSPACE)).replace("\\", "/"):
                                       sha256_file(HERE / path) for path in CPU_SOURCES})
        if name == "audiveris_page":
            security = HERE / ".runtime/phase2r/audiveris-extract/Audiveris/runtime/conf/security/java.security"
            identity["java_security_sha256"] = sha256_file(security)
        candidates[name] = {"status": "requires_screening_pipeline_development_entry",
                            "identity": identity, "identity_sha256": digest(identity)}
    result.update(schema_version=5, name="smb-pianoform-screening-v5-readable-cpu",
                  extension_scope="audiveris_neutral_zeus_readable_runtime; unchanged_sample_and_scoring",
                  candidates=candidates, preserved_source_manifest_sha256=BASE_SHA256,
                  readable_runtime_sha256=digest(current["runtime"]), resource_policy=POLICY)
    return result


def verify_manifest(path: Path) -> dict[str, Any]:
    saved = read_json(path)
    if saved != build_manifest():
        raise ValueError("Readable CPU manifest, runtime, profile, input or scorer changed")
    return saved


def require_current_policy(manifest: dict[str, Any]) -> None:
    if manifest.get("schema_version") != 5 or manifest.get("resource_policy") != POLICY:
        raise ValueError("CPU execution requires its pinned v5 manifest and unchanged 90% policy")


def prepare() -> Path:
    manifest = build_manifest()
    path = REPORTS / f"manifest-v5-{digest(manifest)[:12]}.json"
    if path.exists():
        if read_json(path) != manifest:
            raise ValueError("Existing CPU manifest differs")
    else:
        write_new(path, manifest)
    return path


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    path = prepare()
    print(json.dumps({"manifest": str(path), "sha256": sha256_file(path), "inference_started": False}))
