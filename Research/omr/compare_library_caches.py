"""Compare two engines on the real library using the app's own cached recognitions.

evaluate_library.py re-runs the bridge, which costs GPU time and only exercises the shipped
426 path. After a library migration both engines' results already sit in the app's MIDI
caches, so this reads them instead: each reference pair in pairs.json is joined to each
engine's cache by the source file's SHA-256, and the cache's MIDI is located by the
midi_sha256 its manifest records. Both sides are therefore exactly what the user hears.

Scoring reuses diagnose_library_drift.diagnose and evaluate_library.notes_from_midi
unchanged, so onset F1, drift recovery and the shuffled control mean what they mean there.
Per-song rows name the songs and go to the ignored reports/library directory; stdout
carries only anonymous row numbers and aggregates.

    python compare_library_caches.py                 # homr (426) against homr465
    python compare_library_caches.py homr homr465
"""

from __future__ import annotations

import hashlib
import json
import os
import statistics
import sys
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "src"))

from diagnose_library_drift import diagnose, page_count  # noqa: E402
from evaluate_library import notes_from_midi  # noqa: E402
from library_pairs import load_pairs, resolve_reference  # noqa: E402

LIBRARY = Path(os.environ.get("LOCALAPPDATA", "")) / "Sheet2Play" / "songs"
OUT = HERE / "reports" / "library"
SUMMARY = (
    ("onset_f1", None, "onset F1"),
    ("recovered_onset_f1", None, "after drift correction"),
    ("recovered_gain", None, "drift-recoverable gain"),
    ("control_recovered_onset_f1", None, "shuffled control (recovered)"),
    ("pitch_f1", "reference", "pitch F1"),
    ("pitch_agreement", "reference", "pitch agreement"),
    ("span_ratio", "reference", "span ratio"),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def cache_index(engine: str) -> dict[str, dict]:
    """source_sha256 -> manifest and MIDI path, for caches whose MIDI is still present."""
    folder = LIBRARY / "midi" / engine
    midi_by_hash = {sha256(path): path for path in folder.glob("*.mid")}
    index: dict[str, dict] = {}
    for path in folder.glob("*.json"):
        try:
            manifest = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            continue
        midi = midi_by_hash.get(str(manifest.get("midi_sha256", "")).lower())
        source = str(manifest.get("source_sha256", "")).lower()
        if midi and source:
            index[source] = {"manifest": manifest, "midi": midi}
    return index


def find_source(stem: str) -> Path | None:
    matches = [path for path in (LIBRARY / "pdf").iterdir() if path.is_file() and path.stem == stem]
    return matches[0] if matches else None


def score(engines: tuple[str, str]) -> list[dict]:
    indexes = {engine: cache_index(engine) for engine in engines}
    rows = []
    for pair in load_pairs():
        if not pair.scored:
            continue
        source = find_source(pair.pdf)
        reference = resolve_reference(pair.reference, LIBRARY)
        if source is None or reference is None:
            rows.append({"song": pair.pdf, "status": pair.status, "error": "source or reference missing"})
            continue
        digest = sha256(source)
        expected = notes_from_midi(reference)
        row = {"song": pair.pdf, "status": pair.status, "pages": page_count(source)}
        for engine in engines:
            hit = indexes[engine].get(digest)
            if hit is None:
                row[engine] = {"error": f"no {engine} cache with its MIDI present"}
                continue
            result = diagnose(pair.pdf, notes_from_midi(hit["midi"]), expected, row["pages"], Fraction(16))
            result.pop("windows", None)
            result["engine_revision"] = hit["manifest"].get("engine_revision")
            result["midi_sha256"] = hit["manifest"].get("midi_sha256")
            row[engine] = result
        rows.append(row)
    return rows


def report(rows: list[dict], first: str, second: str) -> None:
    print(f"columns: onset F1, drift-corrected onset F1, pitch F1, span ratio - each {first} then {second}")
    for number, row in enumerate(rows, 1):
        a, b = row.get(first, {}), row.get(second, {})
        if "onset_f1" not in a or "onset_f1" not in b:
            print(f"{number:>2} {row['status']:9} skipped: {a.get('error') or b.get('error') or row.get('error')}")
            continue
        same = " identical MIDI" if a.get("midi_sha256") == b.get("midi_sha256") else ""
        print(
            f"{number:>2} {row['status']:9} {str(row['pages']):>3}p | "
            f"{a['onset_f1']:.3f} {b['onset_f1']:.3f} ({b['onset_f1'] - a['onset_f1']:+.3f}) | "
            f"{a['recovered_onset_f1']:.3f} {b['recovered_onset_f1']:.3f} | "
            f"{a['reference']['pitch_f1']:.3f} {b['reference']['pitch_f1']:.3f} | "
            f"{a['reference']['span_ratio']:.3f} {b['reference']['span_ratio']:.3f}{same}"
        )
    for label, statuses in (("CONFIRMED", {"confirmed"}), ("ALL SCORED", {"confirmed", "candidate"})):
        both = [r for r in rows if r["status"] in statuses and "onset_f1" in r.get(first, {}) and "onset_f1" in r.get(second, {})]
        if not both:
            continue
        print(f"\n{label} (n={len(both)}){first:>22} {second:>9}     delta")
        for key, sub, name in SUMMARY:
            x = statistics.mean(r[first][sub][key] if sub else r[first][key] for r in both)
            y = statistics.mean(r[second][sub][key] if sub else r[second][key] for r in both)
            print(f"  {name:30s} {x:7.4f}  {y:7.4f}  {y - x:+7.4f}")
        better = sum(1 for r in both if r[second]["onset_f1"] > r[first]["onset_f1"] + 0.01)
        worse = sum(1 for r in both if r[second]["onset_f1"] < r[first]["onset_f1"] - 0.01)
        print(f"  {second} better / worse / tied on onset (0.01 margin): {better} / {worse} / {len(both) - better - worse}")


def main(argv: list[str]) -> int:
    engines = (argv[0], argv[1]) if len(argv) >= 2 else ("homr", "homr465")
    rows = score(engines)
    OUT.mkdir(parents=True, exist_ok=True)
    output = OUT / f"library-{engines[1]}-vs-{engines[0]}.json"
    output.write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")
    print(f"pairs scored: {len(rows)}; per-song detail in {output.relative_to(HERE)}")
    report(rows, *engines)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
