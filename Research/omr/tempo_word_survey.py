"""Phase 4 follow-up: how each tempo word is actually played, from every PDMX pair.

The frozen table (`tempo_word_corpus.py`, `pdmx-freeze.json`) came from the dev half only and was judged once
on the held-out half. That judgement is done, so this survey uses both halves to describe each word as well as
the data allows: its median and spread in quarter BPM, the same for scores tagged classical, by meter (simple,
cut time, compound), and what modifiers such as "molto", "ma non troppo" and "agitato" do to it. It changes no
frozen file and claims no new held-out result.

    python tempo_word_survey.py --marks data/pdmx/marks.jsonl.gz --out reports/song-tempo/phase4/word-survey.json
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import statistics
import sys
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tempo_word_corpus import (ABSOLUTE, absolute_key, quarter_bpm, relative_class, scores, tables,  # noqa: E402
                               word_pairs)

MIN_PAIRS = 8
MODIFIERS = ("molto", "assai", "ma non troppo", "non troppo", "con moto", "con brio", "agitato", "moderato",
             "vivace", "maestoso", "cantabile", "sostenuto", "espressivo", "grazioso", "con fuoco", "poco")


def meter_class(meter: list[int] | None) -> str:
    if not meter:
        return "unknown"
    beats, beat_type = meter
    if beat_type == 8 and beats in (6, 9, 12):
        return "compound"
    if beat_type == 2:
        return "cut"
    if beat_type == 4:
        return "simple"
    return "other"


def spread(values: list[float]) -> dict[str, Any]:
    ordered = sorted(values)
    quantiles = statistics.quantiles(ordered, n=20, method="inclusive") if len(ordered) >= 2 else [ordered[0]] * 19
    return {"n": len(ordered), "median": round(statistics.median(ordered), 1), "p10": round(quantiles[1], 1),
            "p25": round(quantiles[4], 1), "p75": round(quantiles[14], 1), "p90": round(quantiles[17], 1)}


def head_word(words: str) -> str | None:
    return next((word for word in re.findall(r"[a-zà-üß]+", words) if word in ABSOLUTE), None)


# Wikipedia's "Tempo" article (basic tempo markings, read 2026-10-27), which it calls very rough approximations for
# 4/4; Prestissimo's open top is closed with the common 200-208.
REFERENCE = {"grave": (24, 40), "largo": (40, 66), "larghetto": (44, 66), "lento": (40, 60), "adagio": (44, 66),
             "adagietto": (46, 80), "andante": (56, 108), "andantino": (80, 108), "andante moderato": (80, 108),
             "moderato": (108, 120), "allegretto": (112, 120), "allegro moderato": (116, 120), "allegro": (120, 156),
             "molto allegro": (124, 156), "allegro vivace": (124, 156), "vivace": (156, 176),
             "vivacissimo": (172, 176), "allegrissimo": (172, 176), "presto": (168, 200), "prestissimo": (200, 208)}
FOLDS = 5


def fold_of(group: str) -> int:
    return int(hashlib.sha256(f"word-survey-cv:{group}".encode()).hexdigest(), 16) % FOLDS


def cross_validate(all_scores: list[dict[str, Any]]) -> dict[str, Any]:
    """Each candidate table built on four composer folds and scored on the fifth, pooled over the five."""
    errors: dict[str, list[float]] = collections.defaultdict(list)
    by_word: dict[str, dict[str, list[float]]] = collections.defaultdict(lambda: collections.defaultdict(list))
    relative_errors: dict[str, list[float]] = collections.defaultdict(list)
    for fold in range(FOLDS):
        train = [score for score in all_scores if fold_of(score["group"]) != fold]
        test = [score for score in all_scores if fold_of(score["group"]) == fold]
        table = tables(train)
        medians = table["absolute"]
        clamped = {key: min(max(value, REFERENCE[key][0]), REFERENCE[key][1]) if key in REFERENCE else value
                   for key, value in medians.items()}
        midpoints = {key: sum(REFERENCE[key]) / 2 if key in REFERENCE else value for key, value in medians.items()}
        by_meter: dict[tuple[str, str], list[float]] = collections.defaultdict(list)
        for score in train:
            for words, mark, _ in word_pairs(score):
                key = absolute_key(words, medians)
                if key:
                    by_meter[(key, meter_class(mark.get("time")))].append(quarter_bpm(mark))
        meter_medians = {pair: statistics.median(values) for pair, values in by_meter.items() if len(values) >= 10}
        for score in test:
            for words, mark, previous in word_pairs(score):
                truth = quarter_bpm(mark)
                kind = relative_class(words)
                if kind:
                    if previous and kind in table["relative"]:
                        factor = truth / previous
                        relative_errors["class factor"].append(abs(table["relative"][kind] / factor - 1))
                        relative_errors["no change"].append(abs(1 / factor - 1))
                    continue
                key = absolute_key(words, medians)
                if key is None:
                    continue
                guesses = {"A medians": medians[key], "B clamped": clamped[key], "C reference": midpoints[key],
                           "D meter": meter_medians.get((key, meter_class(mark.get("time"))), medians[key]),
                           "120": 120.0}
                for name, guess in guesses.items():
                    error = abs(round(guess) / truth - 1)
                    errors[name].append(error)
                    by_word[key][name].append(error)

    def summary(values: list[float]) -> dict[str, Any]:
        return {"n": len(values), "median_error": round(statistics.median(values), 4),
                "off_by_more_than_40_percent": round(sum(value > 0.4 for value in values) / len(values), 4)}

    return {"absolute": {name: summary(values) for name, values in errors.items()},
            "relative": {name: summary(values) for name, values in relative_errors.items()},
            "absolute_by_word": {key: {name: summary(values)["median_error"] for name, values in names.items()}
                                 | {"n": len(names["120"])}
                                 for key, names in sorted(by_word.items(), key=lambda item: -len(item[1]["120"]))}}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--marks", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    heads: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    phrases: dict[str, list[float]] = collections.defaultdict(list)
    containing: dict[str, list[tuple[str, float]]] = collections.defaultdict(list)
    for score in scores(Path(args.marks)):
        classical = "classical" in (score.get("genres") or "").lower()
        for words, mark, _ in word_pairs(score):
            if relative_class(words) or re.search(r"(?<![a-z])a tempo(?![a-z])", words):
                continue
            bpm = quarter_bpm(mark)
            phrases[words].append(bpm)
            for modifier in MODIFIERS:
                if re.search(rf"(?<![a-z]){modifier}(?![a-z])", words):
                    containing[modifier].append((words, bpm))
            head = head_word(words)
            if head:
                heads[head].append({"bpm": bpm, "classical": classical, "meter": meter_class(mark.get("time")),
                                    "plain": words == head})
    result: dict[str, Any] = {"words": {}, "phrases": {}, "modifiers": {}}
    for head, rows in sorted(heads.items(), key=lambda item: -len(item[1])):
        if len(rows) < MIN_PAIRS:
            continue
        entry = {"all": spread([row["bpm"] for row in rows])}
        plain = [row["bpm"] for row in rows if row["plain"]]
        if len(plain) >= MIN_PAIRS:
            entry["word_alone"] = spread(plain)
        classical = [row["bpm"] for row in rows if row["classical"]]
        if len(classical) >= MIN_PAIRS:
            entry["classical"] = spread(classical)
        for meter in ("simple", "cut", "compound"):
            values = [row["bpm"] for row in rows if row["meter"] == meter]
            if len(values) >= MIN_PAIRS:
                entry[meter] = spread(values)
        result["words"][head] = entry
    for words, values in sorted(phrases.items(), key=lambda item: -len(item[1])):
        if len(values) >= MIN_PAIRS and head_word(words) != words:
            result["phrases"][words] = spread(values)
    for modifier, rows in containing.items():
        ratios = []
        for words, bpm in rows:
            head = head_word(words.replace(modifier, " "))
            if head and head in result["words"]:
                ratios.append(bpm / result["words"][head]["all"]["median"])
        result["modifiers"][modifier] = {
            "n": len(rows), "ratio_to_head_median": round(statistics.median(ratios), 3) if ratios else None,
            "ratio_n": len(ratios), "phrases": collections.Counter(words for words, _ in rows).most_common(8)}
    Path(args.out).write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    for head, entry in result["words"].items():
        line = f"{head:12s} " + " ".join(
            f"{key}={value['median']}[{value['p25']}-{value['p75']}]n{value['n']}" for key, value in entry.items())
        print(line)
    print("phrases:", {words: (value["median"], value["n"]) for words, value in result["phrases"].items()})
    print("modifiers:", {modifier: (value["ratio_to_head_median"], value["ratio_n"])
                         for modifier, value in result["modifiers"].items() if value["n"]})
    print("agitato:", result["modifiers"]["agitato"]["phrases"])
    all_scores = list(scores(Path(args.marks)))
    result["cross_validation"] = cross_validate(all_scores)
    # What the app guesses with: method A (the frozen method) on every pair, since cross-validation found the
    # clamped, meter and reference variants no better.
    result["table_v2"] = tables(all_scores)
    Path(args.out).write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print("cv absolute:", result["cross_validation"]["absolute"])
    print("cv relative:", result["cross_validation"]["relative"])
    for key, value in list(result["cross_validation"]["absolute_by_word"].items())[:16]:
        print("  ", key, value)
    return 0


if __name__ == "__main__":
    sys.exit(main())
