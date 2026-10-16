"""Capture one isolated native-page input under the mandatory supervisor."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import threading
import time
import traceback

from homr_baseline_infer import gpu_sample, resource_failure
from homr_baseline_resources import memory_sample
from homr_465_compatibility import checked_origins
from screening_homr_compatibility import digest, sha256_file
from homr_465_common import write_new


def verify_config(path: Path) -> dict:
    config = json.loads(path.read_text(encoding="utf-8"))
    expected = config.pop("identity_sha256")
    if digest(config) != expected:
        raise ValueError("Research configuration identity drift")
    config["identity_sha256"] = expected
    if config["title_detection"] is not False or config["threads"] != 8 or config["provider"] != "CUDAExecutionProvider":
        raise ValueError("Unapproved inference setting drift")
    if config["safeguards"] != {"system_stop_percent": 85, "worker_bytes": 4 * 1024**3,
                                "reserve_bytes": 4 * 1024**3, "active_processes": 16, "gpu_stop_percent": 90}:
        raise ValueError("Research safeguard drift")
    if Path(sys.executable).resolve() != Path(config["python"]["path"]).resolve():
        raise ValueError("Unexpected research interpreter")
    artifacts = config["source_files"] + list(config["models"].values()) + [config["segnet"], config["python"], config["capture_script"]]
    if "contract" in config:
        artifacts.append(config["contract"])
    for row in artifacts:
        if sha256_file(Path(row["path"])) != row["sha256"]:
            raise ValueError("Research dependency drift: " + row["path"])
    return config


def configure_native(config: dict, captured: dict):
    import sitecustomize
    if not getattr(sitecustomize, "INSTALLED", False):
        raise RuntimeError("Offline/Git gate missing")
    from zeus_attribution_prepare import configure_cpu
    visible = os.environ.get("CUDA_VISIBLE_DEVICES")
    configure_cpu()
    if visible is None:
        os.environ.pop("CUDA_VISIBLE_DEVICES", None)
    else:
        os.environ["CUDA_VISIBLE_DEVICES"] = visible
    sys.path.insert(0, config["source"])
    sys.path.insert(1, str(Path(__file__).resolve().parents[2] / "dist/Bridge"))
    from homr_gpu import configure_cuda
    configure_cuda()
    import cv2
    import onnxruntime as ort
    cv2.setNumThreads(config["threads"])
    original_session = ort.InferenceSession

    def session(path_or_bytes, sess_options=None, *args, **kwargs):
        options = sess_options if sess_options is not None else ort.SessionOptions()
        options.intra_op_num_threads = config["threads"]
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        result = original_session(path_or_bytes, options, *args, **kwargs)
        row = {"model": str(path_or_bytes), "providers": result.get_providers(),
               "intra_op_threads": options.intra_op_num_threads, "inter_op_threads": options.inter_op_num_threads}
        captured.setdefault("sessions", []).append(row)
        if row["providers"][0] != config["provider"]:
            raise RuntimeError("CUDA provider was not admitted for native musical model")
        return result

    ort.InferenceSession = session
    from homr_candidate_launcher import select_models
    select_models(Path(config["models"]["encoder"]["path"]), Path(config["models"]["decoder"]["path"]))
    from homr.segmentation import config as segmentation
    segmentation.segnet_path_onnx_fp16 = config["segnet"]["path"]
    import homr.main as native
    checked_origins(Path(config["source"]))
    from homr.transformer.staff2score import Staff2Score
    original_predict, original_export = Staff2Score.predict, native.generate_xml

    def predict(self, image):
        values = original_predict(self, image)
        captured.setdefault("decoder_outputs", []).append([str(value) for value in values])
        captured.setdefault("memory", []).append({"stage": "after_decoder", **memory_sample()})
        return values

    def export(arguments, staffs, title):
        captured["exporter_inputs"] = [[str(value) for value in voice] for voice in staffs]
        captured["title"] = title
        return original_export(arguments, staffs, title)

    Staff2Score.predict, native.generate_xml = predict, export
    return native


def capture(config_path: Path, inputs: Path, item_id: str, output: Path) -> int:
    config = verify_config(config_path)
    rows = json.loads(inputs.read_text(encoding="utf-8"))
    matches = [row for row in rows if row["item_id"] == item_id]
    if len(matches) != 1:
        raise ValueError("Expected one explicitly identified input")
    row = matches[0]
    if sha256_file(Path(row["image"]["path"])) != row["image"]["sha256"]:
        raise ValueError("Input image identity drift")
    output.mkdir(parents=True, exist_ok=False)
    image = output / "input.png"
    shutil.copyfile(row["image"]["path"], image)
    captured = {"memory": [{"stage": "before_native", **memory_sample()}]}
    result = {"item_id": item_id, "candidate": config["candidate"], "configuration_identity": config["identity_sha256"],
              "configuration_sha256": sha256_file(config_path), "input_sha256": row["image"]["sha256"],
              "inputs_sha256": sha256_file(inputs), "status": "complete", "title_detection": False,
              "numeric_accuracy_eligible": row["numeric_accuracy_eligible"], "python_executable": sys.executable}
    stopped = threading.Event()
    initial = gpu_sample()

    def monitor():
        with (output / "gpu-resources.jsonl").open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(initial) + "\n")
            while not stopped.wait(2):
                try:
                    stream.write(json.dumps(gpu_sample()) + "\n")
                    stream.flush()
                except Exception as error:
                    stream.write(json.dumps({"stop": str(error)}) + "\n")
                    stream.flush()
                    os._exit(90)

    watcher = threading.Thread(target=monitor, daemon=True)
    watcher.start()
    started = time.monotonic()
    try:
        native = configure_native(config, captured)
        result["homr_origin"] = str(Path(native.__file__).resolve())
        arguments = native.ProcessingConfig(**config["processing"])
        captured["memory"].append({"stage": "before_image", **memory_sample()})
        native.process_image(str(image), arguments, native.XmlGeneratorArguments(False, None, None))
        captured["memory"].append({"stage": "after_image", **memory_sample()})
        result["module_origins"] = checked_origins(Path(config["source"]))
        if not image.with_suffix(".musicxml").is_file() or not captured.get("decoder_outputs"):
            raise RuntimeError("Native page pipeline produced no usable XML/tokens")
    except Exception as error:
        result.update(status="resource_stopped" if resource_failure(error) else "failed", error=f"{type(error).__name__}: {error}")
        (output / "failure-traceback.txt").write_text(traceback.format_exc(), encoding="utf-8")
    finally:
        stopped.set()
        watcher.join(timeout=12)
    result["elapsed_seconds"] = time.monotonic() - started
    write_new(output / "tokens.json", captured)
    result["artifacts"] = [{"path": str(path.resolve()), "sha256": sha256_file(path), "bytes": path.stat().st_size}
                           for path in sorted(output.rglob("*")) if path.is_file()]
    write_new(output / "result.json", result)
    print(json.dumps({name: result[name] for name in ("item_id", "status", "elapsed_seconds")}), flush=True)
    return 2 if result["status"] == "resource_stopped" else 1 if result["status"] == "failed" else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configuration", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--item", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(capture(args.configuration, args.inputs, args.item, args.output))
