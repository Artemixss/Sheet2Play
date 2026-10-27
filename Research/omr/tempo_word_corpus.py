"""Phase 4 of the per-song tempo plan: what tempo words mean, from the PDMX corpus.

PDMX (Long et al., about 250k MuseScore scores, CC BY 4.0, Zenodo record 15571083) prints many tempo words
next to a metronome mark. The number printed with a word is the truth for what that word means in practice.

    python tempo_word_corpus.py extract --pdmx data/pdmx --out data/pdmx/marks.jsonl.gz
    python tempo_word_corpus.py pairs --marks data/pdmx/marks.jsonl.gz --out reports/song-tempo/phase4/pdmx-pairs.json

`extract` streams mxl.tar.gz (nothing is unpacked) and keeps, for each score in the deduplicated,
licence-clean subset, the visible tempo-like directions of its first part: words, metronome and the bar.
Hidden marks (print-object="no") are playback tempos, not printed ones, and are skipped. `pairs` counts
word-and-number pairs per split against the bar set before any value was seen (Lieder's: 150 pairs, 6 words
with 10 or more); it prints no tempo values. Scores are split by composer (or artist, or title) so the
held-out half shares no composer with dev.
"""
from __future__ import annotations

import argparse
import collections
import csv
import gzip
import hashlib
import io
import json
import math
import re
import statistics
import sys
import tarfile
import time
import xml.etree.ElementTree as ElementTree
import zipfile
from pathlib import Path
from typing import Any, Iterator, Sequence

SEED = "song-tempo-phase4-pdmx"
MIN_PAIRS, MIN_WORDS, MIN_PAIRS_PER_WORD = 150, 6, 10
QUARTERS = {("whole", 0): 4.0, ("half", 0): 2.0, ("half", 1): 3.0, ("quarter", 0): 1.0, ("quarter", 1): 1.5,
            ("eighth", 0): 0.5, ("eighth", 1): 0.75, ("16th", 0): 0.25}


def normalized_words(text: str) -> str:
    """Lower case, without the number, the note glyphs, brackets and punctuation."""
    text = re.sub(r"[-♩-♬]", " ", text)
    text = re.sub(r"[()\[\]=,.:;!\"'*\d]|\bc\.|\bca\.|\bcirca\b|\bbpm\b", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def group_of(row: dict[str, str]) -> str:
    for column in ("composer_name", "artist_name", "song_name"):
        value = re.sub(r"[^a-z0-9]+", " ", (row.get(column) or "").lower()).strip()
        if value and value != "na":
            return value
    return row["path"]


def split_of(group: str) -> str:
    return "dev" if int(hashlib.sha256(f"{SEED}:{group}".encode()).hexdigest(), 16) % 2 == 0 else "held-out"


def selected(pdmx: Path) -> dict[str, dict[str, str]]:
    """The deduplicated, licence-clean scores, keyed by their mxl path inside the archive."""
    chosen = {}
    with (pdmx / "PDMX.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["subset:deduplicated"] == "True" and row["subset:no_license_conflict"] == "True" and row["mxl"] != "NA":
                chosen[row["mxl"].lstrip("./")] = row
    return chosen


def score_xml(data: bytes) -> bytes:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        root = None
        if "META-INF/container.xml" in names:
            container = ElementTree.fromstring(archive.read("META-INF/container.xml"))
            rootfile = container.find(".//{*}rootfile")
            root = rootfile.get("full-path") if rootfile is not None else None
        if root is None:
            root = next(name for name in names if name.endswith((".xml", ".musicxml")) and not name.startswith("META-INF"))
        return archive.read(root)


def directions(xml: bytes) -> list[dict[str, Any]]:
    """The visible directions with words or a metronome in the first part, with their bar and time signature."""
    root = ElementTree.fromstring(xml)
    part = root.find("part")
    found = []
    if part is None:
        return found
    meter: list[int] | None = None
    for bar, measure in enumerate(part.findall("measure")):
        time_element = measure.find("attributes/time")
        if time_element is not None and (time_element.findtext("beats") or "").isdigit() and \
                (time_element.findtext("beat-type") or "").isdigit():
            meter = [int(time_element.findtext("beats")), int(time_element.findtext("beat-type"))]
        for direction in measure.iter("direction"):
            words_elements = direction.findall("direction-type/words")
            metronome = direction.find("direction-type/metronome")
            if any(element.get("print-object") == "no" for element in [direction, *words_elements, metronome]
                   if element is not None):
                continue
            words = " ".join((element.text or "").strip() for element in words_elements).strip()
            mark: dict[str, Any] = {"bar": bar, "time": meter}
            if words:
                mark["words"] = words
            if metronome is not None:
                per_minute = re.search(r"\d+(?:\.\d+)?", metronome.findtext("per-minute") or "")
                unit = metronome.findtext("beat-unit")
                if per_minute and unit:
                    mark["unit"] = unit
                    mark["dots"] = len(metronome.findall("beat-unit-dot"))
                    mark["per_minute"] = float(per_minute.group())
            sound = direction.find("sound")
            if sound is not None and sound.get("tempo"):
                mark["sound_tempo"] = sound.get("tempo")
            if "words" in mark or "per_minute" in mark:
                found.append(mark)
    return found


def extract(args: argparse.Namespace) -> None:
    pdmx = Path(args.pdmx)
    chosen = selected(pdmx)
    print(f"{len(chosen)} scores selected", flush=True)
    out = Path(args.out)
    counts = collections.Counter()
    started = time.monotonic()
    with tarfile.open(pdmx / "mxl.tar.gz", "r|gz") as archive, gzip.open(out, "wt", encoding="utf-8") as sink:
        for member in archive:
            if not member.isfile():
                continue
            name = member.name.lstrip("./")
            row = chosen.get(name)
            if row is None:
                continue
            counts["read"] += 1
            try:
                marks = directions(score_xml(archive.extractfile(member).read()))
            except Exception as exception:  # a broken file is counted, not fatal
                counts["errors"] += 1
                counts[type(exception).__name__] += 1
                continue
            group = group_of(row)
            sink.write(json.dumps({"mxl": name, "group": group, "split": split_of(group), "version": row["version"],
                                   "genres": row["genres"], "marks": marks}, ensure_ascii=False) + "\n")
            if counts["read"] % 5000 == 0:
                print(f"{counts['read']} read, {counts['errors']} errors, {time.monotonic() - started:.0f} s", flush=True)
    print(json.dumps(dict(counts)), flush=True)


def scores(path: Path) -> Iterator[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            yield json.loads(line)


def pairs(args: argparse.Namespace) -> None:
    by_split: dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)
    groups: dict[str, dict[str, set[str]]] = collections.defaultdict(lambda: collections.defaultdict(set))
    totals = collections.Counter()
    for score in scores(Path(args.marks)):
        totals[f"scores:{score['split']}"] += 1
        seen = set()
        for mark in score["marks"]:
            words = normalized_words(mark.get("words", ""))
            if not words or "per_minute" not in mark or (mark["unit"], mark["dots"]) not in QUARTERS:
                continue
            if words in seen:  # one score counts a word once
                continue
            seen.add(words)
            by_split[score["split"]][words] += 1
            groups[score["split"]][words].add(score["group"])
    result: dict[str, Any] = {"scores": dict(totals), "rule": {"min_pairs": MIN_PAIRS, "min_words": MIN_WORDS,
                                                               "min_pairs_per_word": MIN_PAIRS_PER_WORD}, "splits": {}}
    for split, counter in sorted(by_split.items()):
        rich = [words for words, count in counter.items() if count >= MIN_PAIRS_PER_WORD]
        result["splits"][split] = {
            "pairs": sum(counter.values()), "words_with_10_pairs": len(rich),
            "enough": sum(counter.values()) >= MIN_PAIRS and len(rich) >= MIN_WORDS,
            "top": [{"words": words, "pairs": count, "groups": len(groups[split][words])}
                    for words, count in counter.most_common(60)]}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"scores": result["scores"], **{split: {key: value for key, value in summary.items() if key != "top"}
                                                     for split, summary in result["splits"].items()}}))


# --- Word tables (written 2026-10-27, before any tempo value in PDMX was looked at) -------------------------

# Absolute words, fixed in advance: a phrase gets its own entry with enough dev pairs, otherwise its first
# word from this list ("allegro con brio" -> allegro).
ABSOLUTE = ("prestissimo", "presto", "vivacissimo", "vivace", "vivo", "allegrissimo", "allegretto", "allegro",
            "moderato", "andantino", "andante", "adagietto", "adagio", "larghetto", "largo", "lento", "grave",
            "slowly", "slow", "moderately", "moderate", "fast", "quickly", "lively", "langsam", "mässig", "massig",
            "lebhaft", "schnell", "lent", "modéré", "modere", "vif")
# Relative words, by the way they move the tempo printed before them.
FASTER = ("più mosso", "piu mosso", "più animato", "piu animato", "animato", "più allegro", "piu allegro",
          "faster", "plus vite", "schneller", "doppio movimento")
SLOWER = ("meno mosso", "più lento", "piu lento", "meno", "slower", "moins vite", "langsamer", "calmando",
          "più tranquillo", "piu tranquillo")
MIN_DEV_PAIRS = 10
RULE = {
    "absolute": {"median_error": ["<=", 0.15], "share_off_by_more_than_40_percent": ["<=", 0.10],
                 "sign_test_p_vs_120": ["<", 0.01]},
    "relative": {"median_error": ["<=", 0.10], "sign_test_p_vs_no_change": ["<", 0.01]},
}
FREEZE = Path(__file__).resolve().parent / "reports/song-tempo/phase4/pdmx-freeze.json"


def quarter_bpm(mark: dict[str, Any]) -> float | None:
    quarters = QUARTERS.get((mark.get("unit"), mark.get("dots")))
    return mark["per_minute"] * quarters if quarters and mark.get("per_minute") else None


def relative_class(words: str) -> str | None:
    """'faster' or 'slower' for a relative phrase; a modifier after it ("più mosso, ma tranquillo") is kept."""
    for name, phrases in (("faster", FASTER), ("slower", SLOWER)):
        if any(re.search(rf"(?<![a-zà-ü]){re.escape(phrase)}(?![a-zà-ü])", words) for phrase in phrases):
            return name
    return None


def absolute_key(words: str, phrases: dict[str, float]) -> str | None:
    if relative_class(words) or re.search(r"(?<![a-z])a tempo(?![a-z])", words):
        return None
    if words in phrases:
        return words
    head = next((word for word in re.findall(r"[a-zà-üß]+", words) if word in ABSOLUTE), None)
    return head if head in phrases else None


def word_pairs(score: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any], float | None]]:
    """(words, mark, quarter BPM of the latest earlier printed number) for each numbered mark with words,
    once per words per score."""
    seen: set[str] = set()
    previous: float | None = None
    previous_bar = -1
    for mark in sorted(score["marks"], key=lambda item: item["bar"]):
        bpm = quarter_bpm(mark)
        words = normalized_words(mark.get("words", ""))
        if bpm is not None and words and words not in seen:
            seen.add(words)
            yield words, mark, previous if previous_bar < mark["bar"] else None
        if bpm is not None:
            previous, previous_bar = bpm, mark["bar"]


def tables(dev: list[dict[str, Any]]) -> dict[str, Any]:
    """Medians from the dev scores: the quarter BPM of each absolute phrase and head word, the factor per class.

    Quarters, not the beat the meter is felt in: on dev, converting to the felt beat (6/8 in dotted quarters,
    2/2 in halves) made every measure worse, because many scores print a quarter-note tempo in any meter.
    """
    beats: dict[str, list[float]] = collections.defaultdict(list)
    factors: dict[str, list[float]] = collections.defaultdict(list)
    for score in dev:
        for words, mark, previous in word_pairs(score):
            relative = relative_class(words)
            if relative:
                if previous:
                    factors[relative].append(quarter_bpm(mark) / previous)
                continue
            if re.search(r"(?<![a-z])a tempo(?![a-z])", words):
                continue
            beat = quarter_bpm(mark)
            beats[words].append(beat)
            head = next((word for word in re.findall(r"[a-zà-üß]+", words) if word in ABSOLUTE), None)
            if head and head != words:
                beats[head].append(beat)
    median = lambda values: round(statistics.median(values), 1)  # noqa: E731
    return {
        "absolute": {words: median(values) for words, values in sorted(beats.items())
                     if len(values) >= MIN_DEV_PAIRS and (words in ABSOLUTE or any(
                         word in ABSOLUTE for word in re.findall(r"[a-zà-üß]+", words)))},
        "absolute_pairs": {words: len(values) for words, values in beats.items() if len(values) >= MIN_DEV_PAIRS},
        "relative": {name: round(statistics.median(values), 3) for name, values in factors.items()
                     if len(values) >= MIN_DEV_PAIRS},
        "relative_pairs": {name: len(values) for name, values in factors.items()},
    }


def sign_test(wins: int, losses: int) -> float:
    """One-sided p that the guess wins no more often than the baseline (ties dropped)."""
    total = wins + losses
    if total == 0:
        return 1.0
    return sum(math.comb(total, k) for k in range(wins, total + 1)) / 2 ** total


def evaluate(scores_list: list[dict[str, Any]], table: dict[str, Any]) -> dict[str, Any]:
    absolute, relative = [], []
    for score in scores_list:
        for words, mark, previous in word_pairs(score):
            truth = quarter_bpm(mark)
            kind = relative_class(words)
            if kind:
                if previous and kind in table["relative"]:
                    factor = truth / previous
                    relative.append({"words": words, "error": abs(table["relative"][kind] / factor - 1),
                                     "baseline_error": abs(1 / factor - 1)})
                continue
            key = absolute_key(words, table["absolute"])
            if key is None:
                continue
            guess = round(table["absolute"][key])
            absolute.append({"words": words, "key": key, "truth": truth, "guess": guess,
                             "error": abs(guess / truth - 1), "baseline_error": abs(120 / truth - 1)})

    def summary(rows: list[dict[str, Any]], baseline: str) -> dict[str, Any]:
        if not rows:
            return {"pairs": 0}
        errors = [row["error"] for row in rows]
        wins = sum(row["error"] < row["baseline_error"] for row in rows)
        losses = sum(row["error"] > row["baseline_error"] for row in rows)
        return {"pairs": len(rows), "median_error": round(statistics.median(errors), 4),
                "baseline_median_error": round(statistics.median(row["baseline_error"] for row in rows), 4),
                "share_off_by_more_than_40_percent": round(sum(error > 0.4 for error in errors) / len(rows), 4),
                "wins": wins, "losses": losses, f"sign_test_p_vs_{baseline}": sign_test(wins, losses)}

    by_key: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in absolute:
        by_key[row["key"]].append(row)
    return {"absolute": summary(absolute, "120"), "relative": summary(relative, "no_change"),
            "absolute_by_word": {key: {k: v for k, v in summary(rows, "120").items() if k != "sign_test_p_vs_120"}
                                 for key, rows in sorted(by_key.items(), key=lambda item: -len(item[1]))}}


def split_scores(path: Path, split: str) -> list[dict[str, Any]]:
    return [score for score in scores(path) if score["split"] == split]


def table_command(args: argparse.Namespace) -> None:
    dev = split_scores(Path(args.marks), "dev")
    table = tables(dev)
    result = {"tables": table, "dev": evaluate(dev, table)}
    print(json.dumps(result, indent=1, ensure_ascii=False))


def freeze_command(args: argparse.Namespace) -> None:
    if FREEZE.exists():
        raise SystemExit(f"{FREEZE} exists; a freeze is made once.")
    marks = Path(args.marks)
    dev = split_scores(marks, "dev")
    FREEZE.write_text(json.dumps({
        "plan": "2026-10-19-song-tempo", "phase": 4, "frozen_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tempo_word_corpus_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "marks_sha256": hashlib.sha256(marks.read_bytes()).hexdigest(), "split_seed": SEED,
        "tables": tables(dev), "rule": RULE}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(FREEZE.read_text(encoding="utf-8"))


def verdict_command(args: argparse.Namespace) -> None:
    frozen = json.loads(FREEZE.read_text(encoding="utf-8"))
    marks = Path(args.marks)
    if frozen["tempo_word_corpus_sha256"] != hashlib.sha256(Path(__file__).read_bytes()).hexdigest():
        raise SystemExit("tempo_word_corpus.py changed after the freeze.")
    if frozen["marks_sha256"] != hashlib.sha256(marks.read_bytes()).hexdigest():
        raise SystemExit("The marks file changed after the freeze.")
    out = Path(args.out)
    if out.exists():
        raise SystemExit(f"{out} exists; the held-out half is scored once.")
    result = evaluate(split_scores(marks, "held-out"), frozen["tables"])
    passes = {"<=": lambda value, limit: value <= limit, "<": lambda value, limit: value < limit}
    checks = []
    for kind, metrics in frozen["rule"].items():
        for metric, (operator, limit) in metrics.items():
            value = result[kind].get(metric)
            checks.append({"kind": kind, "metric": metric, "rule": f"{operator} {limit}", "value": value,
                           "pass": value is not None and passes[operator](value, limit)})
    accepted = {kind: all(check["pass"] for check in checks if check["kind"] == kind) for kind in frozen["rule"]}
    out.write_text(json.dumps({"freeze": frozen, "held_out": result, "checks": checks, "accepted": accepted},
                              indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for check in checks:
        print(f"{'PASS' if check['pass'] else 'FAIL'}  {check['kind']:9s} {check['metric']:36s} {check['value']}  ({check['rule']})")
    print(json.dumps(accepted))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    extract_parser = commands.add_parser("extract")
    extract_parser.add_argument("--pdmx", required=True)
    extract_parser.add_argument("--out", required=True)
    extract_parser.set_defaults(func=extract)
    pairs_parser = commands.add_parser("pairs")
    pairs_parser.add_argument("--marks", required=True)
    pairs_parser.add_argument("--out", required=True)
    pairs_parser.set_defaults(func=pairs)
    for name, func in (("table", table_command), ("freeze", freeze_command)):
        command_parser = commands.add_parser(name)
        command_parser.add_argument("--marks", required=True)
        command_parser.set_defaults(func=func)
    verdict_parser = commands.add_parser("verdict")
    verdict_parser.add_argument("--marks", required=True)
    verdict_parser.add_argument("--out", required=True)
    verdict_parser.set_defaults(func=verdict_command)
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
