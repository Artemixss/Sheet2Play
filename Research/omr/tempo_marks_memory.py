#!/usr/bin/env python3
"""Peak memory of the shipped tempo reader on one PDF, read in this process from a cold start.

Phase 3 of the per-song tempo plan asks for RAM and commit on the library's densest page before
the release gate. Windows keeps a process's peak working set and peak private (commit) bytes, so
reading the PDF here and asking at the end gives both.

    python tempo_marks_memory.py PDF
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "Bridge"))
import psutil  # noqa: E402

import tempo_marks  # noqa: E402


def main() -> int:
    pdf = Path(sys.argv[1])
    result = tempo_marks.read_pdf(pdf)
    memory = psutil.Process().memory_info()
    print(json.dumps({
        "reader_sha256": result["reader_sha256"], "pages": len(result["pages"]),
        "light_ink_pages": sum(page["light_ink"] for page in result["pages"]),
        "systems": sum(page["systems"] for page in result["pages"]), "marks": len(result["marks"]),
        "seconds": result["seconds"],
        "peak_working_set_mib": round(memory.peak_wset / 2**20, 1),
        "peak_private_mib": round(memory.peak_pagefile / 2**20, 1),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
