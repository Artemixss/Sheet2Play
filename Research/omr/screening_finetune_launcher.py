"""Fail-closed epoch-14 launch through the resource-limited CUDA page path."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

from homr_candidate_launcher import checked_model_path, select_models
from screening_finetune_compatibility import validate
from screening_homr_compatibility import sha256_file
from screening_homr_development_launcher import main as limited_main


def main() -> int:
    source = Path(os.environ["S2P_FINETUNE_SOURCE"]).resolve()
    contract = Path(os.environ["S2P_FINETUNE_CONTRACT"]).resolve()
    report = Path(os.environ["S2P_FINETUNE_COMPATIBILITY_REPORT"]).resolve()
    for name, path in (("CONTRACT", contract), ("COMPATIBILITY_REPORT", report)):
        if sha256_file(path) != os.environ[f"S2P_FINETUNE_{name}_SHA256"]:
            raise ValueError(f"Fine-tune {name} identity differs")
    encoder = checked_model_path(os.environ["SHEET2PLAY_CANDIDATE_ENCODER"],
                                 os.environ["SHEET2PLAY_CANDIDATE_ENCODER_SHA256"])
    decoder = checked_model_path(os.environ["SHEET2PLAY_CANDIDATE_DECODER"],
                                 os.environ["SHEET2PLAY_CANDIDATE_DECODER_SHA256"])
    segnet = checked_model_path(os.environ["S2P_FINETUNE_SEGNET"], os.environ["S2P_FINETUNE_SEGNET_SHA256"])
    auxiliary = json.loads(os.environ["S2P_FINETUNE_AUXILIARY_MODELS"])
    if not auxiliary:
        raise ValueError("Fine-tune RapidOCR model inventory is empty")
    auxiliary_paths = {checked_model_path(path, sha) for path, sha in auxiliary.items()}
    observed = validate(source, encoder, decoder, contract)
    if observed != json.loads(report.read_text(encoding="utf-8")):
        raise ValueError("Live fine-tune compatibility differs from admission evidence")
    select_models(encoder, decoder)
    from homr.segmentation import config as segmentation
    segmentation.segnet_path_onnx_fp16 = str(segnet)
    import onnxruntime as ort
    original_session = ort.InferenceSession

    def identified_session(path, *args, **kwargs):
        resolved = Path(path).resolve()
        if resolved not in {encoder, decoder, segnet, *auxiliary_paths}:
            raise ValueError(f"Undeclared fine-tune model loaded: {resolved}")
        session = original_session(path, *args, **kwargs)
        if resolved in {encoder, decoder, segnet} and "CUDAExecutionProvider" not in session.get_providers():
            raise RuntimeError(f"Fine-tune CUDA provider is unavailable for {resolved.name}")
        print("FINE_TUNED_HOMR_MODEL=" + json.dumps({"path": str(resolved),
              "sha256": sha256_file(resolved), "providers": session.get_providers()}),
              file=sys.stderr, flush=True)
        return session

    ort.InferenceSession = identified_session
    return limited_main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, OSError, ValueError, RuntimeError) as error:
        print(f"Fine-tune identity/runtime failure: {error}", file=sys.stderr, flush=True)
        raise SystemExit(2) from error
