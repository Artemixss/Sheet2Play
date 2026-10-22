"""Phase 4 of the per-song tempo plan: can printed return words ("a tempo", "Tempo I") be trusted?

Return words name a tempo the song already had, so they can play exactly once the reader finds them at the
right bar. This scores the frozen Phase 2 reader's saved rows (no new OCR run): recall and precision of
return words, whether their kind (first tempo or "a tempo") is right, and whether they land on the right bar
of their page. Absolute and relative words were dropped from Phase 4 because the word-truth corpus had too
few printed word-and-number pairs (see the Phase 4 report).

    python tempo_words.py score RUN [RUN ...]
    python tempo_words.py freeze --rule JSON RUN [RUN ...]      # development runs only
    python tempo_words.py verdict --out FILE RUN [RUN ...]      # test runs, once

`return_kind` is mirrored by `TempoWords.Kind` in the app; `tests/test_tempo_words.py` keeps them in step.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Iterable, Sequence

HERE = Path(__file__).resolve().parent
PHASE2 = HERE / "reports/song-tempo/phase2"
REPORT = HERE / "reports/song-tempo/phase4"
FREEZE = REPORT / "freeze.json"
PHASE2_FREEZE = PHASE2 / "freeze.json"
TEST_SPLITS = ("test", "test-b")

# "Tempo I", "Tempo 1°", "1° Tempo", "Tempo primo", "come prima": back to the song's first tempo. OCR reads
# the roman one as I, l or 1, and the degree sign as °, º or o.
FIRST = re.compile(r"\btempo\s*(?:i|l|1|primo|io|1o)(?![a-z])\s*[°º.]?|(?<![a-z])(?:1|i)\s*[°º]\s*tempo\b"
                   r"|\bcome\s+prima\b", re.IGNORECASE)
A_TEMPO = re.compile(r"(?<![a-z])a\s*tempo\b", re.IGNORECASE)
# A tempo word after the return word changes it ("a tempo, più lento"), so it is no longer exact.
MODIFIER = re.compile(r"più|piu|meno|mosso|animato|calmando|lento|lent\b|vite|plus|moins|rit|rall|allarg|"
                      r"accel|string|langsam|schnell|bewegt|ruhig|slower|faster", re.IGNORECASE)


def return_kind(text: str | None) -> str | None:
    """'first' for Tempo I and its spellings, 'a_tempo' for a tempo, None for anything else."""
    if not text:
        return None
    for kind, pattern in (("first", FIRST), ("a_tempo", A_TEMPO)):
        match = pattern.search(text)
        if match:
            return None if MODIFIER.search(text[match.end():]) else kind
    return None


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_run(run: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    recorded = json.loads((run / "run.json").read_text(encoding="utf-8"))
    frozen = json.loads(PHASE2_FREEZE.read_text(encoding="utf-8"))
    if recorded["tempo_read_sha256"] != frozen["tempo_read_sha256"]:
        raise SystemExit(f"{run} was not read by the frozen Phase 2 reader.")
    if recorded["candidate"] != "ocr":
        raise SystemExit(f"{run} is a {recorded['candidate']} run; the app reads with OCR.")
    rows = [json.loads(line) for line in (run / "rows.jsonl").read_text(encoding="utf-8").splitlines()]
    return recorded, rows


def score_rows(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    totals = {key: 0 for key in ("scores", "truth", "truth_words_only", "found", "matched", "matched_words_only",
                                 "kind_exact", "page_bar_exact", "false")}
    failures: list[dict[str, Any]] = []
    for row in rows:
        totals["scores"] += 1
        found = [d for d in row["detections"] if return_kind(d.get("text"))]
        totals["found"] += len(found)
        used: set[int] = set()
        for mark in row["truth_marks"]:
            kind = return_kind(mark.get("words"))
            if kind is None:
                continue
            words_only = mark.get("bpm") is None
            totals["truth"] += 1
            totals["truth_words_only"] += words_only
            candidates = [(index, d) for index, d in enumerate(found)
                          if index not in used and d["page"] == mark["page"] and d["system"] == mark["system"]]
            if not candidates:
                failures.append({"id": row["id"], "mark": mark, "why": "missed"})
                continue
            index, hit = min(candidates, key=lambda pair: abs((pair[1]["measure"] or 0) - mark["measure"]))
            used.add(index)
            totals["matched"] += 1
            totals["matched_words_only"] += words_only
            kind_ok = return_kind(hit["text"]) == kind
            bar_ok = hit["page_measure"] == mark["measure"] - row["truth_page_first_measure"][mark["page"]]
            totals["kind_exact"] += kind_ok
            totals["page_bar_exact"] += bar_ok
            if not (kind_ok and bar_ok):
                failures.append({"id": row["id"], "mark": mark, "found": {k: hit[k] for k in (
                    "text", "page_measure", "measure")}, "why": "wrong"})
        for index, d in enumerate(found):
            if index not in used:
                totals["false"] += 1
                failures.append({"id": row["id"], "found": {k: d[k] for k in ("page", "system", "measure", "text")},
                                 "why": "false"})

    def ratio(numerator: str, denominator: str) -> float | None:
        return round(totals[numerator] / totals[denominator], 4) if totals[denominator] else None

    return {
        "counts": totals,
        "return_recall": ratio("matched", "truth"),
        "return_recall_words_only": ratio("matched_words_only", "truth_words_only"),
        "return_precision": ratio("matched", "found"),
        "kind_exact_of_matched": ratio("kind_exact", "matched"),
        # Counted from the top of the mark's page, as the app places marks among HOMR's measures for that page.
        "page_bar_exact_of_matched": ratio("page_bar_exact", "matched"),
        "false_per_score": ratio("false", "scores"),
        "failures": failures,
    }


def summary(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key != "failures"}


def score(args: argparse.Namespace) -> None:
    for run in map(Path, args.runs):
        recorded, rows = load_run(run)
        if recorded["split"] in TEST_SPLITS:
            raise SystemExit("Test runs are scored only by verdict, once.")
        result = score_rows(rows)
        print(run.name, json.dumps(summary(result), ensure_ascii=False))
        for failure in result["failures"]:
            print("   ", json.dumps(failure, ensure_ascii=False))


def freeze(args: argparse.Namespace) -> None:
    if FREEZE.exists():
        raise SystemExit(f"{FREEZE} already exists; a freeze is made once.")
    for run in map(Path, args.runs):
        recorded, _ = load_run(run)
        if recorded["split"] in TEST_SPLITS:
            raise SystemExit("A freeze is made from development runs only.")
    write_json(FREEZE, {
        "plan": "2026-10-19-song-tempo", "phase": 4, "frozen_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tempo_words_sha256": sha256(Path(__file__)), "reader_freeze_sha256": sha256(PHASE2_FREEZE),
        "development_runs": [str(Path(run).as_posix()) for run in args.runs], "rule": json.loads(args.rule)})
    print(FREEZE.read_text(encoding="utf-8"))


def verdict(args: argparse.Namespace) -> None:
    frozen = json.loads(FREEZE.read_text(encoding="utf-8"))
    if frozen["tempo_words_sha256"] != sha256(Path(__file__)):
        raise SystemExit("tempo_words.py changed after the freeze.")
    out = Path(args.out)
    if out.exists():
        raise SystemExit(f"{out} exists; the test runs are scored once.")
    runs = [Path(run) for run in args.runs]
    split_rows = []
    for run in runs:
        recorded, rows = load_run(run)
        if recorded["split"] not in TEST_SPLITS or recorded["set"] != "truth":
            raise SystemExit(f"{run} is not a truth run of a test split.")
        split_rows.append(rows)
    pooled = score_rows(row for rows in split_rows for row in rows)
    passes = {">=": lambda value, limit: value >= limit, "<=": lambda value, limit: value <= limit}
    checks = [{"metric": metric, "rule": f"{operator} {limit}", "value": pooled[metric],
               "pass": pooled[metric] is not None and passes[operator](pooled[metric], limit)}
              for metric, (operator, limit) in frozen["rule"].items()]
    result = {"freeze": frozen, "pooled": pooled,
              "splits": {str(run.as_posix()): summary(score_rows(rows)) for run, rows in zip(runs, split_rows)},
              "checks": checks, "accepted": all(check["pass"] for check in checks)}
    write_json(out, result)
    for check in checks:
        print(f"{'PASS' if check['pass'] else 'FAIL'}  {check['metric']:28s} {check['value']}  ({check['rule']})")
    print("ACCEPTED" if result["accepted"] else "NOT ACCEPTED")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    score_parser = commands.add_parser("score")
    score_parser.add_argument("runs", nargs="+")
    score_parser.set_defaults(func=score)
    freeze_parser = commands.add_parser("freeze")
    freeze_parser.add_argument("--rule", required=True)
    freeze_parser.add_argument("runs", nargs="+")
    freeze_parser.set_defaults(func=freeze)
    verdict_parser = commands.add_parser("verdict")
    verdict_parser.add_argument("--out", required=True)
    verdict_parser.add_argument("runs", nargs="+")
    verdict_parser.set_defaults(func=verdict)
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
