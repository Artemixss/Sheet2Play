"""Run the production bridge with an opt-in pair of research ONNX models."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parent.parent
sys.path.insert(0, str(WORKSPACE / "Bridge"))


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--encoder", type=Path, required=True)
    parser.add_argument("--encoder-sha256", required=True)
    parser.add_argument("--decoder", type=Path, required=True)
    parser.add_argument("--decoder-sha256", required=True)
    parser.add_argument("--revision", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()
    if not args.input.is_file():
        raise SystemExit(f"Input does not exist: {args.input}")
    if not args.revision.strip():
        raise SystemExit("A nonempty candidate revision is required")

    os.environ["SHEET2PLAY_CANDIDATE_ENCODER"] = str(args.encoder.resolve())
    os.environ["SHEET2PLAY_CANDIDATE_ENCODER_SHA256"] = args.encoder_sha256
    os.environ["SHEET2PLAY_CANDIDATE_DECODER"] = str(args.decoder.resolve())
    os.environ["SHEET2PLAY_CANDIDATE_DECODER_SHA256"] = args.decoder_sha256

    import bridge

    bridge.HOMR_LAUNCHER_FILE = HERE / "homr_candidate_launcher.py"
    bridge.HOMR_ENGINE_REVISION = args.revision
    return bridge.main(("--engine", "homr", str(args.input.resolve())))


if __name__ == "__main__":
    raise SystemExit(main())
