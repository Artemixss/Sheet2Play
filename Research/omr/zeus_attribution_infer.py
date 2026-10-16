"""Compare actual upstream dataset inference with the unchanged wrapper on identical bytes."""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
from pathlib import Path
import pickle
import sys
import time

from zeus_attribution_prepare import HERE, OUT, ROOT, configure_cpu, save_json


def collect_runtime_probe() -> dict:
    from zeus_provenance_probe import collect
    diagnostic_source = (HERE / "src").resolve()
    saved_paths = sys.path.copy()
    try:
        sys.path[:] = [path for path in saved_paths if Path(path).resolve() != diagnostic_source]
        actual = collect(HERE / "zeus")
    finally:
        sys.path[:] = saved_paths
    actual["diagnostic_distribution_context"] = {
        "excluded_search_path": str(diagnostic_source),
        "reason": "Match Phase1 distribution enumeration; diagnostic repository sources are separately pinned",
    }
    return actual


def probe() -> dict:
    actual = collect_runtime_probe()
    expected = json.loads((OUT.parent / "phase1/probe-v2/import-probe.json").read_text())
    keys = ("python", "executable", "prefix", "base_prefix", "tensorflow", "tensorflow_build",
            "gpu_devices", "environment", "symbols", "effective_options", "ordered_tags", "distributions")
    differences = [key for key in keys if actual[key] != expected[key]]
    save_json(OUT / "import-probe.json", actual)
    save_json(OUT / "import-probe-comparison.json", {"keys": keys, "differences": differences,
              "matched": not differences, "inference_started": False})
    if differences:
        raise ValueError(f"Import/configuration changed: {differences}")
    return actual


def describe(image, lengths, timestep: int) -> dict:
    import numpy as np
    array = image.numpy()
    return {"shape": list(array.shape), "minimum": float(array.min()), "maximum": float(array.max()),
            "float32_sha256": hashlib.sha256(array.tobytes()).hexdigest(),
            "valid_widths": np.asarray(lengths).tolist(),
            "encoder_valid_steps": ((np.asarray(lengths) + timestep - 1) // timestep).tolist()}


def convert(lmx: str, destination: Path) -> dict:
    from zeus_runner import lmx_to_musicxml
    from sheet2play_omr.adapter_contract import sha256_file
    diagnostics = io.StringIO()
    try:
        with contextlib.redirect_stderr(diagnostics):
            lmx_to_musicxml(lmx, destination)
        return {"status": "succeeded", "diagnostics": diagnostics.getvalue(),
                "musicxml_sha256": sha256_file(destination)}
    except Exception as error:
        return {"status": "failed", "error": f"{type(error).__name__}: {error}",
                "diagnostics": diagnostics.getvalue()}


def render_tokens(ids: list[int], tags: list[str], *, filter_unknown: bool = False) -> str:
    if any(isinstance(i, bool) or not isinstance(i, int) or i < 0 or i >= len(tags) for i in ids):
        raise ValueError("Decoder emitted invalid vocabulary indices")
    return " ".join(tags[i] for i in ids if not filter_unknown or i > 0)


def infer_crop(runner, crop: Path, expected_hash: str, work: Path) -> None:
    import tensorflow as tf
    from zeus import LMXDataset
    from sheet2play_omr.adapter_contract import sha256_file
    if sha256_file(crop) != expected_hash:
        raise ValueError(f"Input crop changed: {crop}")
    work.mkdir(parents=True, exist_ok=False)
    base = work / "upstream-input"
    # This pickle is written and immediately consumed here, never supplied externally.
    with base.with_suffix(".pickle").open("xb") as stream:
        pickle.dump([{"image": crop.read_bytes(), "lmx": ""}], stream)
    vocabulary = LMXDataset.from_tags(str(runner.model_dir / "tags.txt"))
    dataset = LMXDataset(str(base), runner.args, vocabulary)
    tf_dataset = dataset.tf_dataset(training=False)
    upstream_input, _ = next(iter(tf_dataset))
    if not isinstance(upstream_input, tf.RaggedTensor):
        raise ValueError("Upstream recipe did not produce ragged input")
    upstream_tensor = upstream_input.to_tensor()[0]
    lengths = upstream_input.row_lengths(axis=2).to_tensor().numpy()
    started = time.monotonic()
    upstream_ids = runner.model.predict(tf_dataset, verbose=0)[0].numpy().tolist()
    upstream_seconds = time.monotonic() - started
    upstream_lmx = render_tokens(upstream_ids, runner.tags)
    direct_ids = runner.model.predict_step(upstream_input)[0].numpy().tolist()
    if direct_ids != upstream_ids:
        raise ValueError("Keras dataset/direct inference parity failed")
    captured = {}
    original_predict = runner.model.predict_step
    def capture(data):
        captured["description"] = describe(data.to_tensor()[0],
            data.row_lengths(axis=2).to_tensor().numpy(), runner.args.timestep_width)
        captured["prefix_equal"] = bool(tf.reduce_all(data.to_tensor()[0, :, :tf.shape(upstream_tensor)[1], :] == upstream_tensor).numpy())
        result = original_predict(data)
        captured["ids"] = result[0].numpy().tolist()
        return result
    runner.model.predict_step = capture
    started = time.monotonic()
    try:
        local_lmx = runner.predict_image(crop)
    finally:
        runner.model.predict_step = original_predict
    local_seconds = time.monotonic() - started
    if not captured["prefix_equal"]:
        raise ValueError("Resized wrapper prefix differs from upstream grayscale/resize recipe")
    upstream = {"token_ids": upstream_ids, "lmx": upstream_lmx, "seconds": upstream_seconds,
                "preprocessing": describe(upstream_tensor, lengths, runner.args.timestep_width),
                "direct_predict_step_matches": True}
    local = {"token_ids": captured["ids"], "lmx": local_lmx, "seconds": local_seconds,
             "preprocessing": captured["description"], "resized_prefix_matches": captured["prefix_equal"],
             "unfiltered_lmx": render_tokens(captured["ids"], runner.tags)}
    if local_lmx != render_tokens(captured["ids"], runner.tags, filter_unknown=True):
        raise ValueError("Wrapper token formatting differs from inspected recipe")
    for name, result in (("upstream", upstream), ("wrapper", local)):
        result["unknown_token_count"] = result["token_ids"].count(0)
        result["token_count"] = len(result["token_ids"])
        result["termination"] = "length_limit" if len(result["token_ids"]) == runner.args.max_predict_length else "EOS"
        result["termination_evidence"] = "decoder excludes first EOS; returned length below limit implies EOS"
        result["conversion"] = convert(result["lmx"], work / f"{name}.musicxml")
    save_json(work / "prediction.json", {"crop": str(crop), "crop_sha256": expected_hash,
        "upstream": upstream, "wrapper": local, "token_sequences_equal": upstream_ids == captured["ids"]})
    print(json.dumps({"crop": str(crop), "tokens": [len(upstream_ids), len(captured["ids"])],
                      "seconds": [upstream_seconds, local_seconds]}), flush=True)


def run(item_id: str | None, skip_item_id: str | None) -> None:
    from sheet2play_omr.adapter_contract import sha256_file
    manifest = json.loads((OUT / "experiment-manifest.json").read_text())
    for filename, expected in manifest["sources"].items():
        if sha256_file(Path(filename)) != expected:
            raise ValueError(f"Diagnostic source changed after freeze: {filename}")
    if not json.loads((OUT / "import-probe-comparison.json").read_text())["matched"]:
        raise ValueError("Import resolution must be verified before inference")
    actual = collect_runtime_probe()
    sys.path.insert(0, str(HERE / "zeus"))
    sys.path.insert(0, str(HERE / "zeus/source"))
    saved = json.loads((OUT / "import-probe.json").read_text())
    for key in ("symbols", "effective_options", "ordered_tags", "environment", "tensorflow", "distributions"):
        if actual[key] != saved[key]:
            raise ValueError(f"Inference import resolution differs: {key}")
    from zeus_runner import ZeusRunner
    import tensorflow as tf
    tf.keras.utils.set_random_seed(42)
    runner = ZeusRunner(HERE / "zeus/weights/zeus-olimpic-1.0-2024-02-12.model")
    selected = [i for i in manifest["items"] if (item_id is None or i["item_id"] == item_id)
                and i["item_id"] != skip_item_id]
    if not selected:
        raise ValueError(f"Unknown item: {item_id}")
    for item in selected:
        for number, crop in enumerate(item["crops"], 1):
            work = OUT / "inference" / item["item_id"] / f"system-{number:04d}"
            if work.exists():
                raise FileExistsError(f"Preserve existing evidence; explicit resume needed: {work}")
            infer_crop(runner, Path(crop["path"]), crop["sha256"], work)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("probe", "infer"))
    parser.add_argument("--item-id")
    parser.add_argument("--skip-item-id")
    args = parser.parse_args()
    configure_cpu()
    if args.action == "probe":
        probe()
    else:
        run(args.item_id, args.skip_item_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
