"""Read-only evidence verification for the authorized Phase 4 decision review."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any

HERE = Path(__file__).absolute().parent
WORKSPACE = HERE.parents[4]
EVIDENCE = HERE.parent
PHASE2 = EVIDENCE / "phase2"
PHASE3 = EVIDENCE / "phase3"
ARCHIVE = WORKSPACE / "plans/archive/2026-10-06-homr-timing-465.done.md"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def identity(path: Path) -> dict[str, str]:
    return {"path": str(path.absolute()), "sha256": digest(path)}


def write_new(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def verify_rows(rows: list[dict[str, Any]]) -> int:
    for row in rows:
        if digest(Path(row["path"])) != row["sha256"]:
            raise ValueError("Evidence drift: " + row["path"])
    return len(rows)


def verify_tree(root: Path, rows: list[dict[str, Any]]) -> int:
    current = {str(path.absolute()) for path in root.rglob("*") if path.is_file()}
    expected = {row["path"] for row in rows}
    if current != expected:
        raise ValueError(f"File set drift in {root}: added={len(current - expected)}, missing={len(expected - current)}")
    return verify_rows(rows)


def verify_frozen() -> dict[str, int]:
    before = load(PHASE3 / "preservation-before.json")
    return {
        "phase2_files": verify_tree(PHASE2, before["phase2_files"]),
        "protected_and_pinned": verify_rows(before["protected"]),
        "production_sources": verify_rows(before["production_sources"]),
    }


def decision_summary() -> dict[str, Any]:
    report = load(PHASE2 / "comparison-report.json")
    audit = load(PHASE3 / "audit.json")
    return {
        "comparison_identity": report["comparison_identity"],
        "supported_superiority": report["supported_superiority"],
        "paired": report["paired"],
        "candidate": report["outputs"]["candidate"]["summary"],
        "control": report["outputs"]["control"]["summary"],
        "limitations": report["limitations"],
        "phase3_tests": audit["tests"],
        "playback_inputs": audit["playback_inputs"],
    }


def snapshot() -> None:
    counts = verify_frozen()
    phase3_rows = [identity(path) for path in sorted(PHASE3.rglob("*")) if path.is_file()]
    rule_paths = [WORKSPACE / "Research/omr/reports/phase1/scoring-protocol.json",
                  WORKSPACE / "plans/archive/2026-09-26-omr-screening-comparison.superseded.md"]
    production_paths = [WORKSPACE / "dist/Sheet2Play.exe"]
    production_paths += [path for path in sorted((WORKSPACE / "dist/Bridge").glob("*.py")) if path.is_file()]
    write_new(HERE / "preservation-before.json", {
        "phase3_files": phase3_rows,
        "rules": [identity(path) for path in rule_paths],
        "published_files": [identity(path) for path in production_paths],
        "reviewer": identity(Path(__file__)),
        "verified_prior_counts": counts,
        "scope": "Phase 4 artifact-only review; no inference, scoring, test rerun or production write",
    })
    write_new(HERE / "review-evidence.json", decision_summary())
    print(json.dumps({**counts, "phase3_files": len(phase3_rows), "published_files": len(production_paths)}))


def check_links(documents: list[Path]) -> list[dict[str, Any]]:
    results = []
    for document in documents:
        targets = re.findall(r"(?<!!)\[[^\]\n]+\]\(([^)\n]+)\)", document.read_text(encoding="utf-8"))
        checked = 0
        for target in targets:
            if re.match(r"[a-z][a-z0-9+.-]*://", target, flags=re.I) or target.startswith("#"):
                continue
            relative = target.split("#", 1)[0].strip("<>")
            if relative and not (document.parent / relative).exists():
                raise ValueError(f"Broken link in {document}: {target}")
            checked += 1
        results.append({"document": identity(document), "links_checked": checked})
    return results


def verify() -> None:
    before = load(HERE / "preservation-before.json")
    counts = verify_frozen()
    counts["phase3_files"] = verify_tree(PHASE3, before["phase3_files"])
    counts["frozen_rules"] = verify_rows(before["rules"])
    counts["published_files"] = verify_rows(before["published_files"])
    verify_rows([before["reviewer"]])
    documents = [WORKSPACE / name for name in ("plans/MAIN_PLAN.md", "plans/README.md", "CONTEXT.md", "AGENTS.md")]
    documents += [ARCHIVE, EVIDENCE / "handoff.md"] + sorted(HERE.glob("*.md"))
    links = check_links(documents)
    pointer = (WORKSPACE / "plans/MAIN_PLAN.md").read_text(encoding="utf-8")
    if "No active plan" not in pointer or ARCHIVE.name not in pointer:
        raise ValueError("Plan lifecycle pointer is missing")
    if not load(HERE / "review-evidence.json")["supported_superiority"]:
        raise ValueError("Frozen comparison does not support the selected recommendation")
    write_new(HERE / "audit.json", {"verified": counts, "documents": links,
              "review_evidence": identity(HERE / "review-evidence.json"),
              "scope": "Phase 4 closeout only; prior artifacts and production bytes preserved"})
    print(json.dumps({"verified": counts, "documents": len(links), "local_links": sum(row["links_checked"] for row in links)}))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("snapshot", "verify"))
    arguments = parser.parse_args()
    {"snapshot": snapshot, "verify": verify}[arguments.mode]()


if __name__ == "__main__":
    main()
