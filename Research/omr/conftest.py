"""Put the research root on sys.path so tests can import the top-level analysis scripts.

The packaged code under `src/sheet2play_omr` is installed and imports on its own. The scripts
beside this file - `evaluate_library.py`, `diagnose_library_drift.py` - are not packaged, and
without this pytest's default import mode only puts `tests/` on the path.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
