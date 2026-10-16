"""Verify epoch-14 provenance, ordered vocabularies, and the live ONNX interface."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from screening_homr_compatibility import digest, model_interface, ordered_labels, sha256_file

HEADS = ("rhythm", "pitch", "lift", "position", "articulation", "slur")


def checked_files(root: Path, files: dict[str, str]) -> None:
    root = root.resolve()
    if not files:
        raise ValueError("Fine-tune source inventory is empty")
    for name, expected in files.items():
        path = (root / name).resolve()
        if not path.is_relative_to(root) or not path.is_file() or sha256_file(path) != expected:
            raise ValueError(f"Fine-tune file identity differs: {name}")


def check_parity(provenance: dict[str, Any], verification: dict[str, Any]) -> None:
    if (provenance.get("format") != "homr-epoch14-provenance-v2"
            or verification.get("status") != "pass"
            or provenance["verification"]["cpu_parity"] != "pass"
            or verification["source"]["strict_model_load"] != "pass"
            or verification["source"]["strict_wrapper_load"] != "pass"
            or verification["tolerance"] != {"atol": 0.02, "rtol": 0.02}):
        raise ValueError("Fine-tune checkpoint/export parity did not pass")
    for name in ("checkpoint", "encoder_onnx", "decoder_onnx"):
        if provenance["artifacts"][name]["sha256"] != verification["artifacts"][name]["sha256"]:
            raise ValueError(f"Fine-tune parity artifact differs: {name}")
    if len(verification["encoder"]) < 2 or not all(
            item["pass"] and item["violations"] == 0 for item in verification["encoder"].values()):
        raise ValueError("Fine-tune encoder parity is incomplete")
    steps = verification["decoder_steps"]
    if len(steps) < 3 or [s["cache_bearing"] for s in steps[:3]] != [False, True, True]:
        raise ValueError("Fine-tune cache-step parity is incomplete")
    for step in steps:
        if (set(step["heads"]) != {*HEADS, "attention"}
                or not all(h["pass"] and h["violations"] == 0 for h in step["heads"].values())
                or step["cache"]["count"] != 32
                or not step["cache"]["pass"] or step["cache"]["violations"] != 0):
            raise ValueError("Fine-tune decoder/cache parity failed")
    generation = verification["generation"]
    if (not generation["pytorch_repeat_equal"] or not generation["onnx_repeat_equal"]
            or not generation["cross_tokens_equal"]
            or generation["pytorch"] != generation["onnx"]
            or generation["pytorch"]["token_count"] < 1
            or not all(generation[name]["terminated_eos"] for name in ("pytorch", "onnx"))):
        raise ValueError("Fine-tune deterministic generation parity failed")


def vocabulary(source: Path) -> tuple[dict[str, list[str]], dict[str, int]]:
    sys.path.insert(0, str(source.resolve()))
    import homr
    from homr.transformer import configs, vocabulary as symbols
    for module in (homr, configs, symbols):
        if not Path(module.__file__).resolve().is_relative_to(source.resolve()):
            raise ValueError("Fine-tune imported from the wrong source tree")
    config = configs.Config()
    labels = {name: ordered_labels(name, getattr(config, f"{name}_vocab")) for name in HEADS}
    special = {name: getattr(config, f"{name}_token") for name in ("pad", "bos", "eos", "nonote")}
    return labels, special


def validate(source: Path, encoder: Path, decoder: Path, contract_path: Path) -> dict[str, Any]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    checked_files(source, contract["source_files"])
    checked_files(contract_path.parent, contract["evidence_files"])
    provenance = json.loads((contract_path.parent / contract["provenance"]).read_text(encoding="utf-8"))
    verification = json.loads((contract_path.parent / contract["verification"]).read_text(encoding="utf-8"))
    check_parity(provenance, verification)
    labels, special = vocabulary(source)
    if labels != contract["labels"] or special != contract["special_tokens"]:
        raise ValueError("Fine-tune ordered vocabulary or special tokens differ")
    if ({name: len(values) for name, values in labels.items()} != verification["vocabulary"]["sizes"]
            or special != verification["vocabulary"]["special_ids"]):
        raise ValueError("Fine-tune vocabulary differs from source-checkpoint verification")
    if encoder.resolve() == decoder.resolve():
        raise ValueError("Fine-tune encoder and decoder paths are identical")
    models = {}
    for name, path in (("encoder", encoder), ("decoder", decoder)):
        expected = provenance["artifacts"][f"{name}_onnx"]["sha256"]
        if not path.is_file() or sha256_file(path) != expected:
            raise ValueError(f"Fine-tune {name} weights differ")
        interface = model_interface(path)
        if interface != verification["interface"][name]:
            raise ValueError(f"Fine-tune {name} ONNX interface differs")
        models[name] = {"sha256": expected, **interface}
    return {"schema_version": 1, "report_commit": contract["report_commit"],
            "source_revision": provenance["source"]["revision"],
            "contract_sha256": sha256_file(contract_path),
            "validator_sha256": sha256_file(Path(__file__)),
            "ordered_label_sha256": {name: digest(values) for name, values in labels.items()},
            "models": models, "verified_provider": "CPUExecutionProvider",
            "local_cuda_requires_complete_page_development": True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "encoder", "decoder", "contract"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(validate(args.source, args.encoder, args.decoder, args.contract), sort_keys=True))


if __name__ == "__main__":
    main()
