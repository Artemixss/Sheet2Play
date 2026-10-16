"""Fixed, reviewed Phase4 development replay: crop-only, then recurrent mask only."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

from phase4_validation import file_hash, verify_current_admission
from zeus_attribution_prepare import HERE, ROOT, configure_cpu, save_json

OUT = HERE / "reports/zeus-attribution/phase4"
OLD = OUT.parent / "phase3"
SOURCES = ("phase4_experiment.py", "phase4_mask.py", "phase4_conversion.py", "phase4_crops.py",
           "phase4_validation.py", "zeus_attribution_infer.py", "zeus_attribution_analyze.py")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def preflight() -> dict:
    import zeus_attribution_infer as inference
    identity = read_json(OUT.parent / "phase1/diagnostic-identity.json")
    prior = read_json(OLD / "experiment-manifest.json")
    if identity["identity_sha256"] != prior["diagnostic_identity"]:
        raise ValueError("Previous diagnostic identity differs")
    pins = dict(prior["sources"])
    for row in identity["identity"]["upstream_source"]:
        pins[str(HERE / "zeus/source" / row["path"])] = row["sha256"]
    for row in identity["identity"]["pipeline_files"]:
        pins[str(ROOT / row["path"])] = row["sha256"]
    for name, row in identity["identity"]["checkpoint_release_comparison"]["members"].items():
        pins[str(HERE / "zeus/weights/zeus-olimpic-1.0-2024-02-12.model" / name)] = row["local_sha256"]
    for name, expected in pins.items():
        if file_hash(Path(name)) != expected:
            raise ValueError(f"Source/model bytes changed: {name}")
    actual, saved = inference.collect_runtime_probe(), read_json(OLD / "import-probe.json")
    keys = ("symbols", "effective_options", "ordered_tags", "environment", "tensorflow", "distributions")
    for key in keys:
        verify_current_admission(saved[key], actual[key])
    crops = read_json(OUT / "crop-manifest.json")
    review = read_json(OUT / "crop-review/acceptance.json")
    if review["crop_manifest_sha256"] != file_hash(OUT / "crop-manifest.json") or not review["accepted"]:
        raise ValueError("Every fixed crop requires prior visual review")
    for item in crops["items"]:
        for name in ("image", "reference", "detector_page"):
            if file_hash(Path(item[name])) != item[f"{name}_sha256"]:
                raise ValueError(f"Input changed: {item['item_id']} {name}")
        for crop in item["crops"]:
            if file_hash(Path(crop["path"])) != crop["sha256"]:
                raise ValueError("Reviewed crop changed")
    return {"items": crops["items"], "source_pins": pins,
        "sources": {name: file_hash(HERE / name) for name in SOURCES},
        "crop_manifest_sha256": file_hash(OUT / "crop-manifest.json"),
        "review_sha256": file_hash(OUT / "crop-review/acceptance.json"),
        "runtime_probe_sha256": hashlib.sha256(json.dumps({k: actual[k] for k in keys}, sort_keys=True).encode()).hexdigest(),
        "scope": "24 reviewed systems / 15 fixed development items; unchanged weights, tokens, conversion and scoring",
        "variants": ["upstream", "wrapper", "wrapper_valid_mask"],
        "mask_scope": "Only encoder recurrent mask shortened; padded pixels/width, convolution and decoder attention unchanged",
        "failure_policy": "Unchanged native conversion and stitched-page Bridge acceptance; exact traces remain separate"}


def infer_mask(runner, crop: Path, work: Path) -> None:
    import tensorflow as tf
    import zeus_attribution_infer as inference
    from phase4_mask import original_width_mask
    from phase4_conversion import convert_observed
    prediction = read_json(work / "prediction.json")
    image = tf.image.convert_image_dtype(tf.image.decode_image(tf.io.read_file(str(crop)), channels=1), tf.float32)
    resized = tf.image.resize(image, [runner.args.height, tf.int32.max], preserve_aspect_ratio=True, antialias=True)
    width = int(tf.shape(resized)[1].numpy())
    captured, original = {}, runner.model.predict_step

    def capture(data):
        captured["preprocessing"] = inference.describe(data.to_tensor()[0], data.row_lengths(axis=2).to_tensor().numpy(), runner.args.timestep_width)
        result = original(data)
        captured["token_ids"] = result[0].numpy().tolist()
        return result

    runner.model.predict_step = capture
    started = time.monotonic()
    try:
        with original_width_mask(runner.model, width, runner.args.timestep_width) as evidence:
            lmx = runner.predict_image(crop)
    finally:
        runner.model.predict_step = original
    if captured["preprocessing"] != prediction["wrapper"]["preprocessing"]:
        raise ValueError("Mask condition changed padded image bytes/width")
    ids = captured["token_ids"]
    row = {**captured, "lmx": lmx, "seconds": time.monotonic() - started,
        "original_width": width, "mask_evidence": evidence, "token_count": len(ids),
        "unknown_token_count": ids.count(0),
        "termination": "length_limit" if len(ids) == runner.args.max_predict_length else "EOS",
        "conversion": convert_observed(lmx, work / "wrapper_valid_mask.musicxml")}
    save_json(work / "mask-prediction.json", {"crop_sha256": prediction["crop_sha256"], "wrapper_valid_mask": row})
    print(json.dumps({"mask_crop": str(crop), "tokens": len(ids), "mask": evidence}), flush=True)


def run(item_id: str | None, skip_item: str | None) -> None:
    import zeus_attribution_infer as inference
    from phase4_conversion import convert_observed
    manifest = read_json(OUT / "experiment-manifest.json")
    observed = preflight()
    verify_current_admission(manifest, observed)
    sys.path[:0] = [str(HERE / "zeus"), str(HERE / "zeus/source")]
    from zeus_runner import ZeusRunner
    import tensorflow as tf
    tf.keras.utils.set_random_seed(42)
    runner = ZeusRunner(HERE / "zeus/weights/zeus-olimpic-1.0-2024-02-12.model")
    inference.convert = convert_observed
    selected = [i for i in manifest["items"] if (item_id is None or i["item_id"] == item_id) and i["item_id"] != skip_item]
    if not selected:
        raise ValueError("No selected fixed input")
    for item in selected:
        for number, crop in enumerate(item["crops"], 1):
            work = OUT / "inference" / item["item_id"] / f"system-{number:04d}"
            inference.infer_crop(runner, Path(crop["path"]), crop["sha256"], work)
            infer_mask(runner, Path(crop["path"]), work)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "infer"))
    parser.add_argument("--item-id")
    parser.add_argument("--skip-item")
    args = parser.parse_args()
    configure_cpu()
    if args.action == "freeze":
        manifest = preflight()
        save_json(OUT / "experiment-manifest.json", manifest)
        print(json.dumps({"frozen": True, "items": len(manifest["items"])}), flush=True)
    else:
        run(args.item_id, args.skip_item)


if __name__ == "__main__":
    main()
