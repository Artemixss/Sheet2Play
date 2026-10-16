"""Run HOMR with explicitly identified research ONNX weights."""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path
from typing import Sequence


BRIDGE = Path(__file__).resolve().parents[2] / "Bridge"
sys.path.insert(0, str(BRIDGE))


def checked_model_path(path_value: str, expected_sha256: str) -> Path:
    path = Path(path_value)
    if not path.is_absolute() or path.suffix.casefold() != ".onnx" or not path.is_file():
        raise ValueError(f"Expected an existing absolute ONNX path: {path_value}")
    if len(expected_sha256) != 64 or any(c not in "0123456789abcdef" for c in expected_sha256.lower()):
        raise ValueError("Expected a SHA-256 digest for each ONNX model")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != expected_sha256.lower():
        raise ValueError(f"ONNX SHA-256 mismatch: {path}")
    return path.resolve()


def select_models(encoder: Path, decoder: Path) -> None:
    from homr.transformer import configs

    original_init = configs.FilePaths.__init__

    def candidate_init(self: configs.FilePaths) -> None:
        original_init(self)
        self.encoder_path_fp16 = str(encoder)
        self.decoder_path_fp16 = str(decoder)

    configs.FilePaths.__init__ = candidate_init
    configs.default_config.filepaths.encoder_path_fp16 = str(encoder)
    configs.default_config.filepaths.decoder_path_fp16 = str(decoder)


def main(arguments: Sequence[str]) -> int:
    try:
        encoder = checked_model_path(
            os.environ["SHEET2PLAY_CANDIDATE_ENCODER"],
            os.environ["SHEET2PLAY_CANDIDATE_ENCODER_SHA256"],
        )
        decoder = checked_model_path(
            os.environ["SHEET2PLAY_CANDIDATE_DECODER"],
            os.environ["SHEET2PLAY_CANDIDATE_DECODER_SHA256"],
        )
        if encoder == decoder:
            raise ValueError("Encoder and decoder must be different ONNX files")
        select_models(encoder, decoder)
        from homr_gpu import run_homr

        return run_homr(arguments)
    except (KeyError, OSError, ValueError) as error:
        print(f"Candidate HOMR model selection failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(tuple(sys.argv[1:])))
