"""Phase 4 of the per-song tempo plan: are there enough printed word-and-number pairs to learn what tempo words mean?

Counts, in the OpenScore Lieder MuseScore files already on disk, the bars where a visible tempo word and a
visible metronome number are printed together. Hidden marks (playback tempos the transcriber added) are not
printed and are skipped. The bar for "enough", set before any tempo value was looked at: at least 150 pairs,
and at least 6 words with 10 or more pairs each.

    python tempo_word_pairs.py SCORES_DIR --out reports/song-tempo/phase4/word-pairs.json
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
import xml.etree.ElementTree as ElementTree
from pathlib import Path
from typing import Sequence

GLYPHS = re.compile(r"[-♩-♬]")
NUMBER = re.compile(r"=\s*(?:c\.\s*|ca\.\s*|about\s*)?(\d{2,3})")
TEMPO_WORD = re.compile(r"tempo|andante|allegr|adagio|lento|largo|moderato|presto|vivace|mosso|langsam|lebhaft|"
                        r"mässig|lent|vite|animato")
RELATIVE = ("più", "meno", "plus", "moins", "animato", "calmando", "langsamer", "schneller", "bewegter", "doppio")
MIN_PAIRS, MIN_WORDS, MIN_PAIRS_PER_WORD = 150, 6, 10


def flat(element: ElementTree.Element) -> str:
    parts = []
    for node in element.iter():
        if node.text:
            parts.append(node.text)
        if node.tail and node is not element:
            parts.append(node.tail)
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def marks(path: Path) -> list[tuple[int, str, int | None, bool]]:
    """(bar, words, number, visible) for each tempo-like text on the score's first staff."""
    staff = ElementTree.parse(path).getroot().find("Score/Staff")
    found = []
    for bar, measure in enumerate(staff.iter("Measure") if staff is not None else []):
        for element in measure.iter():
            if element.tag not in ("Tempo", "StaffText", "SystemText") or element.find("text") is None:
                continue
            text = flat(element.find("text"))
            number = NUMBER.search(text)
            words = re.sub(r"[(=)\d.,:]|\bc\.|\bca\.|\babout\b", " ", GLYPHS.sub(" ", text))
            words = re.sub(r"\s+", " ", words).strip().lower()
            if element.tag != "Tempo" and not number and not TEMPO_WORD.search(words):
                continue
            found.append((bar, words, int(number.group(1)) if number else None, element.findtext("visible") != "0"))
    return found


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("scores")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    files = sorted(Path(args.scores).rglob("*.mscx"))
    visibility: collections.Counter[str] = collections.Counter()
    pairs: collections.Counter[str] = collections.Counter()
    composers: dict[str, set[str]] = collections.defaultdict(set)
    relative: collections.Counter[str] = collections.Counter()
    for path in files:
        composer = path.relative_to(args.scores).parts[0]
        score_marks = marks(path)
        by_bar: dict[int, list[tuple[int, str, int | None, bool]]] = collections.defaultdict(list)
        for mark in score_marks:
            visibility[("visible" if mark[3] else "hidden") + (" number" if mark[2] else "") + (" words" if mark[1] else "")] += 1
            if mark[3]:
                by_bar[mark[0]].append(mark)
        earlier_number = False
        for bar in sorted(by_bar):
            words = " ".join(mark[1] for mark in by_bar[bar] if mark[1])
            has_number = any(mark[2] for mark in by_bar[bar])
            if words and has_number:
                pairs[words] += 1
                composers[words].add(composer)
                if earlier_number and any(word in words for word in RELATIVE):
                    relative[words] += 1
            earlier_number = earlier_number or has_number
    total = sum(pairs.values())
    rich = sum(1 for count in pairs.values() if count >= MIN_PAIRS_PER_WORD)
    result = {
        "scores": len(files), "marks": dict(visibility), "pairs": total,
        "words_with_10_pairs": rich, "relative_pairs_after_a_number": sum(relative.values()),
        "enough": total >= MIN_PAIRS and rich >= MIN_WORDS,
        "rule": {"min_pairs": MIN_PAIRS, "min_words": MIN_WORDS, "min_pairs_per_word": MIN_PAIRS_PER_WORD},
        "top_pairs": [{"words": words, "pairs": count, "composers": len(composers[words])}
                      for words, count in pairs.most_common(30)],
        "top_relative": relative.most_common(15),
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("scores", "pairs", "words_with_10_pairs",
                                                   "relative_pairs_after_a_number", "enough")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
