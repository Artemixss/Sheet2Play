"""Native no-title page inference in the isolated, validated HOMR 480 source tree.

The same launcher as `homr465_native.py`, against `homr480-profile.json`. Run 480 publishes no
FP16 decoder and upstream's CUDA path always builds an FP16 cache, so the decoder's precision is
read from its own inputs; the research runs in `Research/omr/reports/upstream-480` used exactly
this.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import threading
import time
import traceback

from homr465_native import gpu_sample
from homr465_profile import ProfileError, asset_path
from homr480_profile import PROFILE_PATH, load_profile


def configure_native(profile: dict, receipt: dict):
    root = asset_path(PROFILE_PATH.parent, profile["runtime_directory"])
    source = root / "source"
    if any(name == "homr" or name.startswith("homr.") for name in sys.modules):
        raise ProfileError("HOMR was imported before isolated source selection")
    sys.path.insert(0, str(source))
    from homr_gpu import configure_cuda
    configure_cuda()
    import cv2
    import onnxruntime as ort
    cv2.setNumThreads(profile["threads"])
    original_session = ort.InferenceSession
    allowed_models = {str(asset_path(root, row["path"])): name for name, row in profile["models"].items()}

    def session(model, sess_options=None, *args, **kwargs):
        resolved = str(Path(model).resolve())
        if resolved not in allowed_models:
            raise ProfileError(f"Unexpected native model path: {resolved}")
        options = sess_options if sess_options is not None else ort.SessionOptions()
        options.intra_op_num_threads = profile["threads"]
        options.inter_op_num_threads = profile["inter_op_threads"]
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        result = original_session(model, options, *args, **kwargs)
        providers = result.get_providers()
        receipt.setdefault("sessions", []).append({"model": allowed_models[resolved], "providers": providers})
        if not providers or providers[0] != profile["provider"]:
            raise ProfileError("Native model did not select CUDAExecutionProvider")
        return result

    ort.InferenceSession = session
    from homr.transformer import configs, decoder_inference
    original_init = configs.FilePaths.__init__

    def selected_init(self):
        original_init(self)
        self.encoder_path_fp16 = str(asset_path(root, profile["models"]["encoder"]["path"]))
        self.decoder_path_fp16 = str(asset_path(root, profile["models"]["decoder"]["path"]))

    configs.FilePaths.__init__ = selected_init
    selected_init(configs.default_config.filepaths)
    original_decoder = decoder_inference.ScoreDecoder.__init__

    def decoder_init(self, transformer, fp16, use_gpu, *args, **kwargs):
        fp16 = any(row.type == "tensor(float16)" for row in transformer.get_inputs())
        receipt["decoder_fp16"] = fp16
        original_decoder(self, transformer, fp16, use_gpu, *args, **kwargs)

    decoder_inference.ScoreDecoder.__init__ = decoder_init
    from homr.segmentation import config as segmentation
    segmentation.segnet_path_onnx_fp16 = str(asset_path(root, profile["models"]["segnet"]["path"]))
    import homr.main as native
    check_origins(source, receipt)
    return native, source


def check_origins(source: Path, receipt: dict) -> None:
    origins = {name: str(Path(module.__file__).resolve()) for name, module in sys.modules.items()
               if (name == "homr" or name.startswith("homr.")) and getattr(module, "__file__", None)}
    if not origins or any(not Path(path).is_relative_to(source) for path in origins.values()):
        raise ProfileError("HOMR imported outside the pinned 480 source tree")
    receipt["module_origins"] = origins


def main(image: Path, receipt_path: Path) -> int:
    receipt = {"status": "failed", "python": sys.executable}
    started = time.monotonic()
    stop = threading.Event()
    watcher = None
    try:
        profile, identity = load_profile()
        receipt.update(runtime_profile_sha256=identity, model_revision=profile["model_revision"], source_revision=profile["source_revision"])
        receipt["gpu_initial"] = gpu_sample()

        def monitor():
            with receipt_path.with_suffix(".gpu.jsonl").open("x", encoding="utf-8") as stream:
                while not stop.wait(2):
                    try:
                        stream.write(json.dumps(gpu_sample()) + "\n")
                        stream.flush()
                    except Exception as error:
                        stream.write(json.dumps({"stop": str(error)}) + "\n")
                        stream.flush()
                        os._exit(90)

        watcher = threading.Thread(target=monitor, daemon=True)
        watcher.start()

        def offline(event, arguments):
            if event in {"socket.connect", "socket.sendto", "socket.getaddrinfo", "socket.gethostbyname"}:
                raise RuntimeError("Network access is disabled in pinned HOMR 480 inference")
        sys.addaudithook(offline)
        native, source = configure_native(profile, receipt)
        native.process_image(str(image), native.ProcessingConfig(**profile["processing"]), native.XmlGeneratorArguments(False, None, None))
        check_origins(source, receipt)
        if {row["model"] for row in receipt.get("sessions", [])} != {"encoder", "decoder", "segnet"}:
            raise ProfileError("Native inference did not use all three pinned models")
        if not image.with_suffix(".musicxml").is_file():
            raise RuntimeError("Native inference produced no MusicXML")
        receipt["status"] = "complete"
    except Exception as error:
        receipt.update(error=f"{type(error).__name__}: {error}", traceback=traceback.format_exc())
        print(receipt["error"], file=sys.stderr, flush=True)
    finally:
        stop.set()
        if watcher:
            watcher.join(timeout=12)
        receipt["elapsed_seconds"] = time.monotonic() - started
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return 0 if receipt["status"] == "complete" else 3


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: homr480_native.py IMAGE RECEIPT")
    raise SystemExit(main(Path(sys.argv[1]), Path(sys.argv[2])))
