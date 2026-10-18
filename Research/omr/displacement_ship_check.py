#!/usr/bin/env python3
"""Check that the shipped timing correction is the frozen research variant, note for note.

`Bridge/timing_correction.py` ports the frozen variant of the remaining-timing-loss plan,
`fit+anchor-all-keep3-even-time` (`timing_correct.py`, `reports/timing/phase2/freeze.json`); the
displacement plan's Phase 4 shipped `fit+anchor-holes-keep3` the same way. For every cached
recognition of the ruler and the replan sets, this runs the shipped path (the bridge normalizer, the shipped
correction per page, the bridge's `combine_score_pages`) and the research path (`predict`),
and fails unless both place every note identically. No inference, no labels.

    Bridge\\.venv-homr-gpu\\Scripts\\python.exe -I -B Research/omr/displacement_ship_check.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "Bridge"))
sys.path.insert(0, str(HERE / "src"))
sys.path.insert(0, str(HERE))

import musicxml_normalizer as normalizer  # noqa: E402
import timing_correction  # noqa: E402
from displacement_attribution import app_pages  # noqa: E402
from displacement_correct import ENGINES, RULER, manifest_items, predict  # noqa: E402
from timing_correct import FREEZE, load_page  # noqa: E402

VARIANT = json.loads(FREEZE.read_text())["variant"]


def key(start: float, pitch: int, duration: float) -> tuple[int, int, int]:
    return round(start * 1e6), pitch, round(duration * 1e6)


def main() -> int:
    checked = mismatched = fallbacks = 0
    for item in manifest_items(("dev", "test", "dev-b", "test-b")):
        for engine in ENGINES:
            if json.loads((RULER / "captures" / engine / item["id"] / "result.json").read_text())["status"] != "ok":
                continue
            paths = [path for path, _ in app_pages(item, engine)]
            shipped_pages = []
            for number, path in enumerate(paths):
                page = normalizer.normalize_musicxml(path)
                try:
                    page = timing_correction.correct_page(path, page, number == 0)
                except ValueError as error:
                    fallbacks += 1
                    print(f"{item['id']} {engine} page {number + 1}: fallback ({error})", flush=True)
                shipped_pages.append(page)
            shipped = Counter(key(note.start_beat, note.midi_pitch, note.duration_beats)
                              for note in normalizer.combine_score_pages(shipped_pages).notes)
            research = Counter(key(float(start), pitch, float(duration))
                               for _, _, pitch, _, start, duration in predict([load_page(path) for path in paths], VARIANT))
            checked += 1
            if shipped != research:
                mismatched += 1
                print(f"{item['id']} {engine}: MISMATCH, {sum((shipped - research).values())} notes differ", flush=True)
    print(json.dumps({"recognitions": checked, "mismatched": mismatched, "page_fallbacks": fallbacks}))
    return int(bool(mismatched or fallbacks))


if __name__ == "__main__":
    sys.exit(main())
