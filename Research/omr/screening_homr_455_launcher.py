"""Run a pinned HOMR 455 ONNX pair in an isolated research runtime."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from homr_candidate_launcher import checked_model_path, select_models
from screening_homr_compatibility import sha256_file, validate
from screening_homr_development_launcher import main as limited_homr_main


def checked_source() -> Path:
    source = Path(os.environ["S2P_HOMR_455_SOURCE"]).resolve()
    expected = os.environ["S2P_HOMR_455_SOURCE_REVISION"]
    if not (source / "homr" / "__init__.py").is_file():
        raise ValueError("Pinned HOMR 455 source tree is missing")
    revision = subprocess.run(["git", "-C", str(source), "rev-parse", "HEAD"],
                              capture_output=True, text=True, check=True, timeout=10).stdout.strip()
    if revision != expected:
        raise ValueError("HOMR 455 source revision changed")
    dirty = subprocess.run(["git", "-C", str(source), "status", "--porcelain", "--", "homr"],
                           capture_output=True, text=True, check=True, timeout=10).stdout
    if dirty:
        raise ValueError("HOMR 455 source files changed")
    sys.path.insert(0, str(source))
    import homr
    if Path(homr.__file__).resolve() != source / "homr" / "__init__.py":
        raise ValueError("HOMR 455 loaded from the wrong environment")
    return source


def verify_tokenizers(source: Path) -> None:
    expected = json.loads(os.environ["S2P_HOMR_455_TOKENIZER_SHA256"])
    if set(expected) != {"lift", "note", "pitch", "rhythm"}:
        raise ValueError("Incomplete HOMR 455 tokenizer identity")
    for name, sha256 in expected.items():
        path = source / "homr" / "transformer" / f"tokenizer_{name}.json"
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != sha256:
            raise ValueError(f"HOMR 455 tokenizer changed: {name}")


def main() -> int:
    source = checked_source()
    verify_tokenizers(source)
    encoder = checked_model_path(os.environ["SHEET2PLAY_CANDIDATE_ENCODER"],
                                 os.environ["SHEET2PLAY_CANDIDATE_ENCODER_SHA256"])
    decoder = checked_model_path(os.environ["SHEET2PLAY_CANDIDATE_DECODER"],
                                 os.environ["SHEET2PLAY_CANDIDATE_DECODER_SHA256"])
    segnet = checked_model_path(os.environ["S2P_HOMR_455_SEGNET"],
                                os.environ["S2P_HOMR_455_SEGNET_SHA256"])
    if encoder == decoder:
        raise ValueError("HOMR 455 encoder and decoder paths are identical")
    contract = Path(os.environ["S2P_HOMR_455_CONTRACT"]).resolve()
    report = Path(os.environ["S2P_HOMR_455_COMPATIBILITY_REPORT"]).resolve()
    if sha256_file(contract) != os.environ["S2P_HOMR_455_CONTRACT_SHA256"]:
        raise ValueError("HOMR 455 compatibility contract changed")
    if sha256_file(report) != os.environ["S2P_HOMR_455_COMPATIBILITY_REPORT_SHA256"]:
        raise ValueError("HOMR 455 compatibility report changed")
    observed = validate(source, encoder, decoder, contract)
    if observed != json.loads(report.read_text(encoding="utf-8")):
        raise ValueError("HOMR 455 live compatibility differs from pinned report")
    select_models(encoder, decoder)
    from homr.segmentation import config as segmentation_config
    segmentation_config.segnet_path_onnx_fp16 = str(segnet)
    print(f"HOMR 455: source={os.environ['S2P_HOMR_455_SOURCE_REVISION']} "
          f"encoder={encoder.name} decoder={decoder.name} segnet={segnet.name}",
          file=sys.stderr, flush=True)
    return limited_homr_main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"HOMR 455 identity check failed: {error}", file=sys.stderr, flush=True)
        raise SystemExit(2) from error
