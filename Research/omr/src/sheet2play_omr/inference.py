from __future__ import annotations

import gc
import hashlib
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, replace
from functools import partial
from pathlib import Path
from typing import Any, Literal, Protocol

import numpy as np
from PIL import Image

from .assets import RuntimePaths, load_asset_lock, verify_runtime
from .errors import ResearchError
from .events import build_omr_result, extract_canonical_events, parse_kern, write_exports
from .input_pages import TARGET_HEIGHT, TARGET_WIDTH, iter_document_pages, normalize_page
from .kern import combine_pages, validate_kern

class ProgressCallback(Protocol):
    def __call__(self, event: str, **kwargs: Any) -> None: ...

def _progress(event: str, **kwargs: Any) -> None:
    pass


def infer_document(
    input_path: Path,
    output_dir: Path,
    mode: str,
    *,
    paths: RuntimePaths | None = None,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    if mode != "zeus":
        raise ResearchError("DECODER_INVALID", "inference", f"Only zeus engine is supported, got: {mode}")
    from .zeus_engine import infer_zeus_document
    return infer_zeus_document(input_path, output_dir, paths=paths, progress_callback=progress_callback)
