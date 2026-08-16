from __future__ import annotations

import json
import sys
from typing import Any


PROGRESS_PREFIX = "SHEET2PLAY_PROGRESS:"
PROGRESS_SCHEMA_VERSION = 1


def emit_progress(
    *,
    engine: str,
    stage: str,
    status: str,
    message: str,
    page: int | None = None,
    page_count: int | None = None,
    completed_pages: int | None = None,
    elapsed_seconds: float | None = None,
    page_duration_seconds: float | None = None,
    token_count: int | None = None,
) -> None:
    payload: dict[str, Any] = {
        "schema_version": PROGRESS_SCHEMA_VERSION,
        "engine": engine,
        "stage": stage,
        "status": status,
        "message": message,
    }
    optional_values = {
        "page": page,
        "page_count": page_count,
        "completed_pages": completed_pages,
        "elapsed_seconds": elapsed_seconds,
        "page_duration_seconds": page_duration_seconds,
        "token_count": token_count,
    }
    payload.update(
        (name, value) for name, value in optional_values.items() if value is not None
    )
    sys.stderr.write(
        PROGRESS_PREFIX
        + json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        + "\n"
    )
    sys.stderr.flush()
