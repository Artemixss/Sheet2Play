"""Fail-closed source, vocabulary, and ONNX contract for the released HOMR 455 pair."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


HEADS = ("rhythm", "pitch", "lift", "position", "articulation", "slur")


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode("utf-8")).hexdigest()


def require_equal(field: str, observed: Any, expected: Any) -> None:
    if observed != expected:
        raise ValueError(f"HOMR 455 {field}: expected {expected!r}, observed {observed!r}")


def ordered_labels(name: str, vocabulary: dict[str, int]) -> list[str]:
    ids = list(vocabulary.values())
    require_equal(f"{name} vocabulary IDs", sorted(ids), list(range(len(ids))))
    return [label for label, _ in sorted(vocabulary.items(), key=lambda item: item[1])]


def check_source(source: Path, contract: dict[str, Any]) -> None:
    if not (source / "homr" / "__init__.py").is_file():
        raise ValueError(f"HOMR 455 source is missing: {source}")
    from phase4_validation import checked_homr_source
    checked_homr_source(source, contract["source_revision"])


def check_vocabulary(source: Path, contract: dict[str, Any]) -> dict[str, str]:
    sys.path.insert(0, str(source))
    import homr
    from homr.transformer import configs, vocabulary

    for module in (homr, configs, vocabulary):
        if not Path(module.__file__).resolve().is_relative_to(source):
            raise ValueError(f"HOMR 455 imported from wrong source: {module.__file__}")
    config = configs.Config()
    require_equal("default encoder model", Path(config.filepaths.encoder_path_fp16).name,
                  f"encoder_pytorch_model_{contract['model_id']}_fp16.onnx")
    require_equal("default decoder model", Path(config.filepaths.decoder_path_fp16).name,
                  f"decoder_pytorch_model_{contract['model_id']}_fp16.onnx")
    expected_heads = contract["labels"]
    require_equal("vocabulary heads", sorted(expected_heads), sorted(HEADS))
    observed = {name: ordered_labels(name, getattr(config, f"{name}_vocab")) for name in HEADS}
    for name in HEADS:
        require_equal(f"{name} labels", observed[name], expected_heads[name])
    specials = {"pad": config.pad_token, "bos": config.bos_token,
                "eos": config.eos_token, "nonote": config.nonote_token}
    require_equal("special tokens", specials, contract["special_tokens"])
    require_equal("position semantics", observed["position"], [".", "upper", "lower"])
    return {name: digest(observed[name]) for name in HEADS}


def model_interface(path: Path) -> dict[str, Any]:
    import onnxruntime as ort

    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
    session = ort.InferenceSession(str(path), sess_options=options,
                                   providers=["CPUExecutionProvider"])
    try:
        def descriptors(values: list[Any]) -> list[dict[str, Any]]:
            return [{"name": item.name, "shape": item.shape, "type": item.type}
                    for item in values]

        return {"inputs": descriptors(session.get_inputs()),
                "outputs": descriptors(session.get_outputs())}
    finally:
        del session


def validate(source: Path, encoder: Path, decoder: Path, contract_path: Path) -> dict[str, Any]:
    source, encoder, decoder = source.resolve(), encoder.resolve(), decoder.resolve()
    contract_path = contract_path.resolve()
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    require_equal("contract schema", contract["schema_version"], 1)
    check_source(source, contract)
    labels = check_vocabulary(source, contract)
    if encoder == decoder:
        raise ValueError("HOMR 455 encoder and decoder paths are identical")
    models = {}
    for name, path in (("encoder", encoder), ("decoder", decoder)):
        if not path.is_file():
            raise ValueError(f"HOMR 455 {name} is missing: {path}")
        expected = contract["models"][name]
        actual_hash = sha256_file(path)
        require_equal(f"{name} SHA-256", actual_hash, expected["sha256"])
        interface = model_interface(path)
        for direction in ("inputs", "outputs"):
            actual, specified = interface[direction], expected[direction]
            require_equal(f"{name} {direction} count", len(actual), len(specified))
            for index, (observed, wanted) in enumerate(zip(actual, specified, strict=True)):
                require_equal(f"{name} {direction}[{index}]", observed, wanted)
        models[name] = {"sha256": actual_hash, **interface}
    return {"schema_version": 1, "source_revision": contract["source_revision"],
            "contract_sha256": sha256_file(contract_path),
            "validator_sha256": sha256_file(Path(__file__)),
            "verification_dependencies": {"phase4_validation.py": sha256_file(
                Path(__file__).with_name("phase4_validation.py"))},
            "ordered_label_sha256": labels, "models": models}


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--encoder", type=Path, required=True)
    parser.add_argument("--decoder", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(validate(arguments.source, arguments.encoder, arguments.decoder,
                              arguments.contract), sort_keys=True))


if __name__ == "__main__":
    main()
