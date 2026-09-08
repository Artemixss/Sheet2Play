#!/usr/bin/env python3
"""Which library PDF is scored against which reference, and why.

Pairing used to be filename equality: `evaluate_library.py` looked for a MIDI whose stem matched
the PDF's. That is silent in both directions. It misses real pairs whose filenames merely differ
(`if_i_am_with_you.pdf` against `If I am with you.mid`), and - worse - it cannot tell that a pair
it does find is the *same arrangement*. `Dark Souls - Gwyn Lord of Cinder.pdf` carries Finale
metadata naming it "Gwyn, Lord of Cinder (Two Pianos)" and was being scored against a solo
MuseScore MIDI with nearly twice the notes. An onset F1 computed against a different arrangement
is not an engine result, and there were seven songs in the sample.

So pairing is a reviewed file instead of a coincidence, with every decision written down:

- `confirmed` - the reference is the same music as the PDF, and the numbers agree with that.
- `candidate` - plausible but unverified; scored, and reported separately so it cannot quietly
  join the headline.
- `rejected` - a pairing something would otherwise make, with the reason it must not be made.
  These matter as much as the accepted ones: they stop a future session re-adding them.

`reference` is resolved against the library's `songs/` directory, then against this research
tree, so a MusicXML reference downloaded to `Research/omr/data/library_truth/` can replace a
rendered MIDI without changing anything else.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

HERE = Path(__file__).resolve().parent
DEFAULT_PAIRS = HERE / "reports" / "library" / "pairs.json"

SCORED_STATUSES = ("confirmed", "candidate")


@dataclass(frozen=True)
class Pair:
    pdf: str
    reference: str | None
    status: str
    why: str

    @property
    def scored(self) -> bool:
        return self.status in SCORED_STATUSES and self.reference is not None


def load_pairs(path: Path = DEFAULT_PAIRS) -> list[Pair]:
    if not path.is_file():
        return []
    document = json.loads(path.read_text(encoding="utf-8"))
    return [
        Pair(
            pdf=entry["pdf"],
            reference=entry.get("reference"),
            status=entry.get("status", "candidate"),
            why=entry.get("why", ""),
        )
        for entry in document.get("pairs", [])
    ]


def resolve_reference(reference: str, library: Path) -> Path | None:
    """A reference path may be relative to the song library or to this research tree."""
    candidate = Path(reference)
    if candidate.is_absolute():
        return candidate if candidate.is_file() else None
    for root in (library, HERE):
        resolved = root / candidate
        if resolved.is_file():
            return resolved
    return None


def truth_for(
    pdf_stem: str, library: Path, pairs: Iterable[Pair] | None = None
) -> tuple[Path | None, str]:
    """The reference for one PDF and the status behind it.

    Falls back to the old filename-equality rule when no pairs file is present, so the script
    still runs on a checkout that has not built one yet.
    """
    pairs = list(pairs) if pairs is not None else load_pairs()
    if pairs:
        for pair in pairs:
            if pair.pdf != pdf_stem:
                continue
            if not pair.scored:
                return None, pair.status
            resolved = resolve_reference(pair.reference or "", library)
            return resolved, pair.status if resolved else "missing"
        return None, "unlisted"

    legacy = library / "midi" / "custom" / (pdf_stem + ".mid")
    return (legacy if legacy.is_file() else None), "filename-match"
