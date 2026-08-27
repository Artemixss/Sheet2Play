"""Run the Sheet Music Transformer on system-level score images.

Two things must be right or the model produces confident nonsense.

**Use the 2024 code, not master.** The upstream repository reimplemented the decoder
in February 2025 (commit b64afed5, then 2c29df41 "Changed normalization orders").
The published checkpoints predate that, so against master 210 of 360 tensors fail to
match and transformers silently leaves the whole decoder randomly initialised - it
still "loads" and emits a plausible-looking stream of repeated tokens. Against
d25acd43 (2024-09-03) all 360 tensors match exactly and the output is valid Humdrum.

**Feed it one system, sized the way data.py does.** The model carries a fixed 2D
positional encoding of maxh/16 by maxw/16, so a full page overflows it. Width is kept
and clamped to maxw; height is resized to maxh without preserving aspect ratio,
because that is what the model was trained on.

Output is bekern, a Humdrum **kern variant, not MusicXML.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VENDOR = HERE / "vendor" / "SMT-2024"
if str(VENDOR) not in sys.path:
    sys.path.insert(0, str(VENDOR))

import cv2
import numpy as np
import torch

import smt_compat  # must precede the model import; patches SMTConfig
smt_compat.apply()

from data_augmentation.data_augmentation import convert_img_to_tensor  # noqa: E402
from smt_model import SMTModelForCausalLM  # noqa: E402

GRANDSTAFF = "antoniorv6/smt-grandstaff"
CAMERA_GRANDSTAFF = "antoniorv6/smt-camera-grandstaff"


def prepare_image(image: np.ndarray, max_height: int, max_width: int) -> np.ndarray:
    """Match the preprocessing in the upstream data.py."""
    height, width = image.shape[:2]
    if height <= 0 or width <= 0:
        raise ValueError("empty image")
    return cv2.resize(image, (max(16, min(width, max_width)), max_height))


class SMTTranscriber:
    def __init__(self, model_id: str = GRANDSTAFF, device: str | None = None,
                 strict: bool = True):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model_id = model_id
        self.model = SMTModelForCausalLM.from_pretrained(model_id).to(self.device)
        self.model.eval()
        self.max_height = int(getattr(self.model.config, "maxh", 256))
        self.max_width = int(getattr(self.model.config, "maxw", 3056))
        if strict:
            self._assert_weights_loaded()

    def _assert_weights_loaded(self) -> None:
        """Fail loudly if the checkpoint did not populate the model.

        A partially loaded model is the failure mode that cost the most time here:
        it runs, it is fast, and it returns fluent rubbish.
        """
        from huggingface_hub import hf_hub_download
        from safetensors.torch import load_file

        checkpoint = set(load_file(hf_hub_download(self.model_id, "model.safetensors")))
        expected = set(self.model.state_dict())
        unmatched = expected - checkpoint
        if unmatched:
            raise RuntimeError(
                "%d of %d tensors were not loaded from the checkpoint (e.g. %s). "
                "The vendored SMT code does not match this checkpoint."
                % (len(unmatched), len(expected), sorted(unmatched)[:3]))

    def transcribe(self, image: np.ndarray) -> str:
        """Transcribe one system image, returning bekern text."""
        prepared = prepare_image(image, self.max_height, self.max_width)
        tensor = convert_img_to_tensor(prepared).unsqueeze(0).to(self.device)
        with torch.no_grad():
            predictions, _ = self.model.predict(tensor, convert_to_str=True)
        return ("".join(predictions)
                .replace("<b>", "\n")
                .replace("<s>", " ")
                .replace("<t>", "\t"))

    def transcribe_file(self, path: Path) -> str:
        image = cv2.imread(str(path))
        if image is None:
            raise ValueError("could not read image: " + str(path))
        return self.transcribe(image)


def kern_stats(bekern: str) -> dict:
    """Summarise a transcription so two engines can be compared numerically."""
    lines = [ln for ln in bekern.splitlines() if ln.strip()]
    spines = max((len(ln.split("\t")) for ln in lines), default=0)
    notes = 0
    barlines = 0
    for line in lines:
        if line.startswith("="):
            barlines += 1
            continue
        if line.startswith(("!", "*")):
            continue
        for token in line.split("\t"):
            token = token.strip()
            if not token or token == "." or token.endswith("r"):
                continue
            if any(c.isdigit() for c in token) and any(c.lower() in "abcdefg" for c in token):
                notes += 1
    return {
        "chars": len(bekern),
        "records": len(lines),
        "spines": spines,
        "notes": notes,
        "barlines": barlines,
        "well_formed": bekern.lstrip().startswith("**"),
    }
