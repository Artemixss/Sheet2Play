"""Local, offline parity verification for HOMR epoch-14 ONNX artifacts.

This script intentionally loads the source safetensors checkpoint with strict=True,
uses no network, and writes only JSON evidence next to this script.  It does not
modify the checkpoint, HOMR source tree, or ONNX artifacts.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import onnxruntime as ort
import safetensors.torch
import timm
import torch


ROOT = Path("/root/Sheet2Play/Research/omr/vendor/homr")
CHECKPOINT = ROOT / "current_training/checkpoint-135674/model.safetensors"
ENCODER_ONNX = Path("/root/omr_epoch14_onnx_export/homr_epoch14_encoder_fp16.onnx")
DECODER_ONNX = Path("/root/omr_epoch14_onnx_export/homr_epoch14_decoder_fp16.onnx")
DEV_IMAGE = Path(
    "/root/Sheet2Play/Research/omr/tests/fixtures/transcoda-baseline/baseline-piano.png"
)
OUT = Path(__file__).resolve().parent
ATOL = 0.02
RTOL = 0.02


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def max_difference(left: np.ndarray, right: np.ndarray) -> dict[str, Any]:
    left = left.astype(np.float32, copy=False)
    right = right.astype(np.float32, copy=False)
    delta = np.abs(left - right)
    tolerance = ATOL + RTOL * np.abs(left)
    return {
        "shape": list(left.shape),
        "max_abs": float(delta.max()),
        "mean_abs": float(delta.mean()),
        "max_rel": float((delta / np.maximum(np.abs(left), 1e-8)).max()),
        "violations": int(np.count_nonzero(delta > tolerance)),
        "elements": int(delta.size),
        "pass": bool(np.all(delta <= tolerance)),
    }


def onnx_value(array: np.ndarray, ort_type: str) -> np.ndarray:
    if ort_type == "tensor(float16)":
        return array.astype(np.float16, copy=False)
    if ort_type == "tensor(float)":
        return array.astype(np.float32, copy=False)
    if ort_type == "tensor(int64)":
        return array.astype(np.int64, copy=False)
    raise RuntimeError(f"unsupported ONNX input type: {ort_type}")


def snapshot_io(session: ort.InferenceSession) -> dict[str, Any]:
    return {
        "inputs": [
            {"name": node.name, "type": node.type, "shape": node.shape}
            for node in session.get_inputs()
        ],
        "outputs": [
            {"name": node.name, "type": node.type, "shape": node.shape}
            for node in session.get_outputs()
        ],
    }


def make_development_crop() -> tuple[np.ndarray, dict[str, Any]]:
    image = cv2.imread(str(DEV_IMAGE), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"failed to read development fixture: {DEV_IMAGE}")
    # This rectangle contains the complete top piano system in the public fixture.
    crop = image[50:230, 40:1010]
    if crop.size == 0 or float(np.std(crop)) == 0.0:
        raise RuntimeError("development crop is empty or uniform")
    resized = cv2.resize(crop, (1280, 256), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    normalized = (gray.astype(np.float32) / 255.0 - 0.7931) / 0.1738
    return normalized[None, None, :, :], {
        "source_path": str(DEV_IMAGE),
        "source_sha256": sha256(DEV_IMAGE),
        "source_shape_bgr": list(image.shape),
        "crop_xyxy": [40, 50, 1010, 230],
        "resize_wh": [1280, 256],
        "grayscale": "cv2.COLOR_BGR2GRAY",
        "normalization": {"input_scale": "uint8 / 255", "mean": 0.7931, "std": 0.1738},
        "tensor_shape": [1, 1, 256, 1280],
        "crop_stddev": float(np.std(crop)),
    }


def decoder_inputs(
    session: ort.InferenceSession,
    tokens: dict[str, np.ndarray],
    context: np.ndarray,
    cache_len: int,
    cache: list[np.ndarray],
) -> dict[str, np.ndarray]:
    specs = {node.name: node.type for node in session.get_inputs()}
    values = {
        "rhythms": tokens["rhythms"],
        "pitchs": tokens["pitchs"],
        "lifts": tokens["lifts"],
        "articulations": tokens["articulations"],
        "slurs": tokens["slurs"],
        "context": context,
        "cache_len": np.asarray([cache_len], dtype=np.int64),
    }
    values.update({f"cache_in{i}": cache[i] for i in range(32)})
    return {name: onnx_value(values[name], specs[name]) for name in specs}


def source_decoder_step(
    wrapper: torch.nn.Module,
    tokens: dict[str, np.ndarray],
    context: torch.Tensor,
    cache_len: int,
    cache: list[torch.Tensor],
    device: torch.device,
) -> tuple[list[np.ndarray], list[torch.Tensor]]:
    kwargs = {
        name: torch.from_numpy(value).to(device=device, dtype=torch.long)
        for name, value in tokens.items()
    }
    with torch.no_grad():
        result = wrapper(
            **kwargs,
            context=context,
            cache_len=torch.tensor([cache_len], device=device, dtype=torch.long),
            cache=cache,
            mask=None,
            return_center_of_attention=True,
        )
    outputs = [result[index].detach().float().cpu().numpy() for index in range(6)]
    outputs.append(result[7].detach().float().cpu().numpy())
    return outputs, list(result[8])


def advance_tokens(outputs: list[np.ndarray]) -> dict[str, np.ndarray]:
    names = ["rhythms", "pitchs", "lifts", "positions", "articulations", "slurs"]
    values = {
        name: np.argmax(output[:, -1:, :], axis=-1).astype(np.int64)
        for name, output in zip(names, outputs[:6], strict=True)
    }
    return {
        "rhythms": values["rhythms"],
        "pitchs": values["pitchs"],
        "lifts": values["lifts"],
        "articulations": values["articulations"],
        "slurs": values["slurs"],
    }


def run() -> None:
    if not all(path.is_file() for path in (CHECKPOINT, ENCODER_ONNX, DECODER_ONNX, DEV_IMAGE)):
        missing = [str(path) for path in (CHECKPOINT, ENCODER_ONNX, DECODER_ONNX, DEV_IMAGE) if not path.is_file()]
        raise RuntimeError("required artifact missing: " + ", ".join(missing))
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))

    # get_encoder() requests pretrained timm weights while constructing a model.  The
    # checkpoint supplies all learned parameters, so force an offline skeleton only.
    original_create_model = timm.create_model
    def offline_create_model(*args: Any, **kwargs: Any) -> Any:
        kwargs["pretrained"] = False
        return original_create_model(*args, **kwargs)
    timm.create_model = offline_create_model

    from homr.transformer.configs import Config
    from training.architecture.transformer.decoder import get_score_wrapper, init_cache
    from training.architecture.transformer.tromr_arch import TrOMR

    config = Config()
    state = safetensors.torch.load_file(str(CHECKPOINT), device="cpu")
    model = TrOMR(config)
    strict_result = model.load_state_dict(state, strict=True)
    if strict_result.missing_keys or strict_result.unexpected_keys:
        raise RuntimeError(f"strict checkpoint load failed: {strict_result}")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.eval_mode()
    model.to(device)

    provider_mode = os.environ.get("HOMR_VERIFY_ORT_PROVIDER", "cuda_then_cpu")
    available = ort.get_available_providers()
    if provider_mode == "cpu":
        providers = ["CPUExecutionProvider"]
    else:
        providers = [provider for provider in ("CUDAExecutionProvider", "CPUExecutionProvider") if provider in available]
    encoder_session = ort.InferenceSession(str(ENCODER_ONNX), providers=providers)
    decoder_session = ort.InferenceSession(str(DECODER_ONNX), providers=providers)

    actual_input, crop_info = make_development_crop()
    synthetic = np.linspace(-1.0, 1.0, num=256 * 1280, dtype=np.float32).reshape(1, 1, 256, 1280)
    encoder_cases: dict[str, dict[str, Any]] = {}
    actual_context_pt: torch.Tensor | None = None
    actual_context_onnx: np.ndarray | None = None
    for name, input_array in {"synthetic_gradient_v1": synthetic, "public_piano_crop_v1": actual_input}.items():
        with torch.no_grad():
            source_output = model.encoder(torch.from_numpy(input_array).to(device)).float().cpu().numpy()
        ort_input = onnx_value(input_array, encoder_session.get_inputs()[0].type)
        onnx_output = encoder_session.run(None, {encoder_session.get_inputs()[0].name: ort_input})[0]
        encoder_cases[name] = max_difference(source_output, onnx_output)
        if name == "public_piano_crop_v1":
            actual_context_pt = torch.from_numpy(source_output).to(device)
            actual_context_onnx = onnx_output
    assert actual_context_pt is not None and actual_context_onnx is not None

    wrapper = get_score_wrapper(config, attn_flash=False).to(device).eval()
    wrapper_state = {
        key.removeprefix("decoder.net."): value
        for key, value in state.items()
        if key.startswith("decoder.net.")
    }
    wrapper_result = wrapper.load_state_dict(wrapper_state, strict=True)
    if wrapper_result.missing_keys or wrapper_result.unexpected_keys:
        raise RuntimeError(f"strict wrapper load failed: {wrapper_result}")

    initial = {
        "rhythms": np.asarray([[config.bos_token]], dtype=np.int64),
        "pitchs": np.asarray([[config.nonote_token]], dtype=np.int64),
        "lifts": np.asarray([[config.nonote_token]], dtype=np.int64),
        "articulations": np.asarray([[config.nonote_token]], dtype=np.int64),
        "slurs": np.asarray([[config.nonote_token]], dtype=np.int64),
    }
    source_cache = init_cache(0, device)[0]
    onnx_cache = [np.zeros((1, 8, 0, 64), dtype=np.float32) for _ in range(32)]
    source_tokens = initial
    onnx_tokens = initial
    source_context = actual_context_pt
    onnx_context = actual_context_onnx
    steps: list[dict[str, Any]] = []
    for step in range(3):
        source_outputs, source_cache = source_decoder_step(
            wrapper, source_tokens, source_context, step, source_cache, device
        )
        onnx_outputs = decoder_session.run(
            None, decoder_inputs(decoder_session, onnx_tokens, onnx_context, step, onnx_cache)
        )
        onnx_cache = list(onnx_outputs[7:])
        names = ["rhythm", "pitch", "lift", "position", "articulation", "slur", "attention"]
        heads = {name: max_difference(source, onnx) for name, source, onnx in zip(names, source_outputs, onnx_outputs[:7], strict=True)}
        cache_checks = [max_difference(source.detach().float().cpu().numpy(), onnx) for source, onnx in zip(source_cache, onnx_cache, strict=True)]
        steps.append({
            "step": step,
            "cache_bearing": step > 0,
            "heads": heads,
            "cache": {
                "count": len(cache_checks),
                "max_abs": max(check["max_abs"] for check in cache_checks),
                "violations": sum(check["violations"] for check in cache_checks),
                "pass": all(check["pass"] for check in cache_checks),
            },
        })
        source_tokens = advance_tokens(source_outputs)
        onnx_tokens = advance_tokens(onnx_outputs)
        source_context = source_context[:, :0, :]
        onnx_context = onnx_context[:, :0, :]

    def generate(which: str) -> dict[str, Any]:
        tokens = initial
        cache_source = init_cache(0, device)[0]
        cache_onnx = [np.zeros((1, 8, 0, 64), dtype=np.float32) for _ in range(32)]
        context_source = actual_context_pt
        context_onnx = actual_context_onnx
        sequence: list[list[int]] = []
        for step in range(config.max_seq_len):
            if which == "pytorch":
                outputs, cache_source = source_decoder_step(wrapper, tokens, context_source, step, cache_source, device)
            else:
                full_outputs = decoder_session.run(None, decoder_inputs(decoder_session, tokens, context_onnx, step, cache_onnx))
                outputs = full_outputs[:7]
                cache_onnx = list(full_outputs[7:])
            next_tokens = advance_tokens(outputs)
            row = [
                int(next_tokens["rhythms"][0, 0]), int(next_tokens["pitchs"][0, 0]),
                int(next_tokens["lifts"][0, 0]), int(next_tokens["articulations"][0, 0]),
                int(next_tokens["slurs"][0, 0]),
            ]
            sequence.append(row)
            if row[0] == config.eos_token:
                return {"tokens": sequence, "terminated_eos": True, "steps": step + 1}
            tokens = next_tokens
            context_source = context_source[:, :0, :]
            context_onnx = context_onnx[:, :0, :]
        return {"tokens": sequence, "terminated_eos": False, "steps": config.max_seq_len}

    # Complete greedy generation is run twice per implementation; matching repeats prove
    # determinism, while the cross-implementation comparison detects token divergence.
    generated = {name: [generate(name), generate(name)] for name in ("pytorch", "onnx")}
    pt_a, pt_b = generated["pytorch"]
    onnx_a, onnx_b = generated["onnx"]
    report = {
        "format": "homr-epoch14-parity-verification-v1",
        "status": "pass" if all(case["pass"] for case in encoder_cases.values()) and all(
            all(head["pass"] for head in item["heads"].values()) and item["cache"]["pass"] for item in steps
        ) and pt_a == pt_b and onnx_a == onnx_b and pt_a["tokens"] == onnx_a["tokens"] else "fail",
        "tolerance": {"atol": ATOL, "rtol": RTOL},
        "artifacts": {
            "checkpoint": {"path": str(CHECKPOINT), "sha256": sha256(CHECKPOINT)},
            "encoder_onnx": {"path": str(ENCODER_ONNX), "sha256": sha256(ENCODER_ONNX)},
            "decoder_onnx": {"path": str(DECODER_ONNX), "sha256": sha256(DECODER_ONNX)},
        },
        "source": {"cwd": str(ROOT), "strict_model_load": "pass", "strict_wrapper_load": "pass", "offline_constructor": True},
        "runtime": {"python": sys.version, "torch": torch.__version__, "onnxruntime": ort.__version__, "providers": providers, "provider_mode": provider_mode, "platform": platform.platform()},
        "preprocessing": crop_info,
        "interface": {"encoder": snapshot_io(encoder_session), "decoder": snapshot_io(decoder_session)},
        "vocabulary": {
            "sizes": {name: len(getattr(config.vocab, name)) for name in ("rhythm", "pitch", "lift", "articulation", "slur", "position")},
            "special_ids": {"pad": config.pad_token, "bos": config.bos_token, "eos": config.eos_token, "nonote": config.nonote_token},
        },
        "encoder": encoder_cases,
        "decoder_steps": steps,
        "generation": {
            "pytorch_repeat_equal": pt_a == pt_b,
            "onnx_repeat_equal": onnx_a == onnx_b,
            "cross_tokens_equal": pt_a["tokens"] == onnx_a["tokens"],
            "pytorch": {key: value for key, value in pt_a.items() if key != "tokens"} | {"token_count": len(pt_a["tokens"])},
            "onnx": {key: value for key, value in onnx_a.items() if key != "tokens"} | {"token_count": len(onnx_a["tokens"])},
        },
    }
    (OUT / "verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "generation": report["generation"]}, indent=2))


if __name__ == "__main__":
    run()
