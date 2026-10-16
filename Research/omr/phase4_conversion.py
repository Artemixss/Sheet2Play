"""Expose the native delinearizer's private diagnostic stream without repairing output."""
from __future__ import annotations

import io
from pathlib import Path

from phase4_validation import file_hash


def convert_observed(lmx: str, destination: Path) -> dict:
    from app.linearization.Delinearizer import Delinearizer
    from app.symbolic.part_to_score import part_to_score
    if not isinstance(lmx, str) or not lmx.strip():
        return {"status": "failed", "error": "Empty native token stream", "diagnostics": ""}
    diagnostics = io.StringIO()
    try:
        delinearizer = Delinearizer(errout=diagnostics)
        delinearizer.process_text(lmx)
        part_to_score(delinearizer.part_element).write(destination, encoding="utf-8", xml_declaration=True)
        return {"status": "succeeded", "diagnostics": diagnostics.getvalue(),
                "musicxml_sha256": file_hash(destination), "policy": "Native output unchanged; diagnostics do not change acceptance"}
    except Exception as error:
        return {"status": "failed", "error": f"{type(error).__name__}: {error}", "diagnostics": diagnostics.getvalue()}
