"""One page of native HOMR inference for an upstream candidate, after `Bridge/homr465_native.py`.

`plans/2026-10-17-upstream-exporter-480.md`, step 3. A candidate pairs a HOMR source tree with
three ONNX models, all listed with SHA-256 in `reports/upstream-480/candidates.json`; every one
is checked before inference. Settings, threads, CUDA, the no-title policy, the 90% VRAM stop
and the network block are the 465 profile's, so a candidate differs from the app only in
source and weights.

Run 480 has no FP16 decoder. Upstream's CUDA path always loads `decoder_path_fp16` and builds
an FP16 cache, so the decoder's precision is taken from its own inputs instead; the FP16 465
decoder is unaffected.

    python -B homr_upstream_native.py CANDIDATE IMAGE RECEIPT
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[1]
CANDIDATES = HERE / "reports/upstream-480/candidates.json"
sys.path.insert(0, str(WORKSPACE / "Bridge"))

from homr465_profile import load_profile, sha256_file  # noqa: E402
from homr465_native import gpu_sample  # noqa: E402


class CandidateError(RuntimeError):
    pass


def resolve(relative: str) -> Path:
    path = (WORKSPACE / relative).resolve()
    if not path.is_relative_to(WORKSPACE.resolve()):
        raise CandidateError(f"Candidate asset escapes the workspace: {relative}")
    return path


def load_candidate(name: str) -> dict:
    candidate = json.loads(CANDIDATES.read_text(encoding="utf-8"))["candidates"][name]
    source = resolve(candidate["source"])
    for row in candidate["source_files"]:
        if sha256_file(source / row["path"]) != row["sha256"]:
            raise CandidateError(f"Candidate source hash mismatch: {row['path']}")
    for kind, row in candidate["models"].items():
        if sha256_file(resolve(row["path"])) != row["sha256"]:
            raise CandidateError(f"Candidate {kind} hash mismatch: {row['path']}")
    return candidate


def configure(candidate: dict, profile: dict, receipt: dict):
    source = resolve(candidate["source"])
    if any(name == "homr" or name.startswith("homr.") for name in sys.modules):
        raise CandidateError("HOMR was imported before candidate source selection")
    sys.path.insert(0, str(source))
    from homr_gpu import configure_cuda
    configure_cuda()
    import cv2
    import onnxruntime as ort
    cv2.setNumThreads(profile["threads"])
    original_session = ort.InferenceSession
    models = {kind: resolve(row["path"]) for kind, row in candidate["models"].items()}
    allowed = {str(path): kind for kind, path in models.items()}

    def session(model, sess_options=None, *args, **kwargs):
        resolved = str(Path(model).resolve())
        if resolved not in allowed:
            raise CandidateError(f"Unexpected native model path: {resolved}")
        options = sess_options if sess_options is not None else ort.SessionOptions()
        options.intra_op_num_threads = profile["threads"]
        options.inter_op_num_threads = profile["inter_op_threads"]
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        result = original_session(model, options, *args, **kwargs)
        providers = result.get_providers()
        receipt.setdefault("sessions", []).append({"model": allowed[resolved], "providers": providers})
        if not providers or providers[0] != profile["provider"]:
            raise CandidateError("Native model did not select CUDAExecutionProvider")
        return result

    ort.InferenceSession = session
    from homr.transformer import configs, decoder_inference
    original_init = configs.FilePaths.__init__

    def selected_init(self):
        original_init(self)
        self.encoder_path_fp16 = str(models["encoder"])
        self.decoder_path_fp16 = str(models["decoder"])

    configs.FilePaths.__init__ = selected_init
    selected_init(configs.default_config.filepaths)
    original_decoder = decoder_inference.ScoreDecoder.__init__

    def decoder_init(self, transformer, fp16, use_gpu, *args, **kwargs):
        fp16 = any(row.type == "tensor(float16)" for row in transformer.get_inputs())
        receipt["decoder_fp16"] = fp16
        original_decoder(self, transformer, fp16, use_gpu, *args, **kwargs)

    decoder_inference.ScoreDecoder.__init__ = decoder_init
    from homr.segmentation import config as segmentation
    segmentation.segnet_path_onnx_fp16 = str(models["segnet"])
    import homr.main as native
    check_origins(source, receipt)
    return native, source


def check_origins(source: Path, receipt: dict) -> None:
    origins = {name: str(Path(module.__file__).resolve()) for name, module in sys.modules.items()
               if (name == "homr" or name.startswith("homr.")) and getattr(module, "__file__", None)}
    if not origins or any(not Path(path).is_relative_to(source) for path in origins.values()):
        raise CandidateError("HOMR imported outside the candidate source tree")
    receipt["module_origins"] = origins


def main(name: str, image: Path, receipt_path: Path) -> int:
    receipt = {"status": "failed", "candidate": name, "python": sys.executable}
    started = time.monotonic()
    stop = threading.Event()
    watcher = None
    try:
        profile, _ = load_profile(verify_assets=False)
        candidate = load_candidate(name)
        receipt.update(source_revision=candidate["source_revision"], model_revision=candidate["model_revision"])
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
                raise RuntimeError("Network access is disabled in candidate HOMR inference")
        sys.addaudithook(offline)
        native, source = configure(candidate, profile, receipt)
        native.process_image(str(image), native.ProcessingConfig(**profile["processing"]),
                             native.XmlGeneratorArguments(False, None, None))
        check_origins(source, receipt)
        if {row["model"] for row in receipt.get("sessions", [])} != {"encoder", "decoder", "segnet"}:
            raise CandidateError("Native inference did not use all three candidate models")
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
    if len(sys.argv) != 4:
        raise SystemExit("Usage: homr_upstream_native.py CANDIDATE IMAGE RECEIPT")
    raise SystemExit(main(sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])))
