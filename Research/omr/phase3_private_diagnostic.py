"""Run the frozen page routes on the single local diagnostic without publishing its files."""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

from phase3_development_entry import _adapter
from phase3_freeze import verify_freeze
from phase3_infer import PAGE_CANDIDATES, _verify_existing
from phase3_private_preflight import PAGES, REPORT, _eligible_pair, verify as verify_preflight
from sheet2play_omr.adapter_contract import (
    AdapterInput, MeasurementPath, sha256_file, write_result,
)
from sheet2play_omr.phase2r_validation import run_with_typed_failure
from sheet2play_omr.phase3_references import _raw_note_counter


HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[1]
ROOT = HERE / ".runtime" / "phase3" / "private-diagnostic"


def _write_once(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError("Refusing to overwrite private diagnostic evidence")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
                         encoding="utf-8")
    temporary.replace(path)


def _paths(candidate: str, page: int, image_sha256: str, config_sha256: str) -> tuple[Path, Path]:
    stem = f"page-{page:02d}-{image_sha256[:12]}-{config_sha256[:12]}"
    return (ROOT / "evaluation" / candidate / f"{stem}.json",
            ROOT / "raw" / candidate / stem)


def _context(freeze_path: Path, candidate: str) -> tuple[dict[str, Any], dict[str, Any], Any, str]:
    if candidate not in PAGE_CANDIDATES:
        raise ValueError("Unsupported page candidate")
    freeze = verify_freeze(freeze_path.resolve())
    preflight = verify_preflight()
    if sha256_file(REPORT) != freeze["private_diagnostic"]["preflight_sha256"]:
        raise RuntimeError("Private diagnostic render changed after freeze")
    adapter, _ = _adapter(candidate)
    config_sha256 = adapter.config.sha256  # type: ignore[attr-defined]
    if config_sha256 != freeze["ready"][candidate]["adapter_config_sha256"]:
        raise RuntimeError("Page candidate configuration changed after freeze")
    return freeze, preflight, adapter, config_sha256


def _identity(freeze_path: Path, candidate: str, page: int, image_sha256: str,
              config_sha256: str) -> dict[str, Any]:
    return {"schema_version": 1, "freeze_sha256": sha256_file(freeze_path),
            "private_preflight_sha256": sha256_file(REPORT), "candidate": candidate,
            "item_id": f"{hashlib.sha256(REPORT.read_bytes()).hexdigest()[:16]}:page-{page}",
            "page": page, "image_sha256": image_sha256,
            "adapter_config_sha256": config_sha256}


def infer(candidate: str, freeze_path: Path, start_page: int = 1, max_pages: int = 0) -> None:
    if start_page < 1 or max_pages < 0:
        raise ValueError("Invalid local diagnostic page range")
    freeze_path = freeze_path.resolve()
    _, preflight, adapter, config_sha256 = _context(freeze_path, candidate)
    selected = preflight["pages"][start_page - 1:]
    if max_pages:
        selected = selected[:max_pages]
    if not selected:
        raise ValueError("Selected local diagnostic page range is empty")
    for record in selected:
        page = record["page"]
        identity = _identity(freeze_path, candidate, page, record["sha256"], config_sha256)
        image = PAGES / f"page-{page}.png"
        item = AdapterInput(identity["item_id"], preflight["identity"]["private_id_sha256"],
                            image, record["sha256"], MeasurementPath.COMPLETE_DOCUMENT)
        item.validate()
        report, raw = _paths(candidate, page, record["sha256"], config_sha256)
        if report.is_file():
            status = _verify_existing(report, identity)
            origin = "verified_cache"
        else:
            if raw.exists() or report.with_suffix(".identity.json").exists():
                raise FileExistsError("Partial private diagnostic result needs inspection")
            result = run_with_typed_failure(adapter, item, raw)
            if result.status.value == "unavailable":
                raise RuntimeError("Frozen local diagnostic runtime became unavailable")
            write_result(report, result)
            _write_once(report.with_suffix(".identity.json"), identity)
            status = result.status.value
            origin = "inferred"
        print(json.dumps({"page": page, "total": 8, "candidate": candidate,
                          "status": status, "origin": origin}, sort_keys=True), flush=True)


def _predicted_pitches(result: dict[str, Any]) -> Counter[int]:
    if result["status"] != "succeeded":
        return Counter()
    artifacts = [item for item in result["artifacts"] if item["role"] == "canonical_events"]
    if len(artifacts) != 1:
        raise RuntimeError("Private diagnostic canonical output is missing or ambiguous")
    path = Path(artifacts[0]["path"])
    if not path.is_absolute():
        path = WORKSPACE / path
    if not path.is_file() or sha256_file(path) != artifacts[0]["sha256"]:
        raise RuntimeError("Private diagnostic canonical output changed")
    events = json.loads(path.read_text(encoding="utf-8"))
    return Counter(int(note["midi_pitch"]) for note in events["notes"])


def summarize(candidate: str, freeze_path: Path) -> Path:
    freeze_path = freeze_path.resolve()
    _, preflight, _, config_sha256 = _context(freeze_path, candidate)
    statuses: Counter[str] = Counter()
    predicted: Counter[int] = Counter()
    elapsed: list[float] = []
    pages: list[dict[str, Any]] = []
    for record in preflight["pages"]:
        page = record["page"]
        identity = _identity(freeze_path, candidate, page, record["sha256"], config_sha256)
        path, _ = _paths(candidate, page, record["sha256"], config_sha256)
        if not path.is_file():
            raise RuntimeError(f"Private diagnostic inference incomplete at page {page}/8")
        status = _verify_existing(path, identity)
        result = json.loads(path.read_text(encoding="utf-8"))
        pitches = _predicted_pitches(result)
        predicted.update(pitches)
        statuses[status] += 1
        duration = sum(float(value["seconds"]) for value in result["timings"])
        elapsed.append(duration)
        pages.append({"page": page, "status": status, "predicted_note_count": sum(pitches.values()),
                      "elapsed_seconds": duration, "result_sha256": sha256_file(path)})
    _, _, reference_path = _eligible_pair()
    from music21 import converter

    reference = converter.parse(str(reference_path), forceSource=True)
    reference_pitches: Counter[int] = Counter()
    for (pitch, _, _), count in _raw_note_counter(reference).items():
        reference_pitches[pitch] += count
    matched = sum((reference_pitches & predicted).values())
    reference_count = sum(reference_pitches.values())
    predicted_count = sum(predicted.values())
    complete = statuses["succeeded"] == 8
    pitch_multiset_f1 = (2 * matched / (reference_count + predicted_count)
                         if complete and reference_count + predicted_count else None)
    report = {
        "schema_version": 1, "scope": "already_inspected_private_diagnostic_not_ranking",
        "candidate": candidate, "freeze_sha256": sha256_file(freeze_path),
        "preflight_sha256": sha256_file(REPORT), "eligible_page_count": 8,
        "status_counts": dict(sorted(statuses.items())), "pages": pages,
        "reference_note_count": reference_count, "predicted_note_count": predicted_count,
        "pitch_multiset_f1": pitch_multiset_f1,
        "metric_interpretation": "Unaligned document-wide pitch counts only; no page-level reference timing, onset, duration, or ranking claim",
        "median_page_latency_seconds": statistics.median(elapsed),
        "failure_pages_included": True,
    }
    output = ROOT / "summaries" / f"{candidate}-{report['freeze_sha256'][:12]}.json"
    _write_once(output, report)
    print(json.dumps({"summary": str(output), "status_counts": report["status_counts"],
                      "pitch_multiset_f1": pitch_multiset_f1}, sort_keys=True), flush=True)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("infer", "summarize"))
    parser.add_argument("--freeze", required=True, type=Path)
    parser.add_argument("--candidate", required=True, choices=PAGE_CANDIDATES)
    parser.add_argument("--start-page", type=int, default=1)
    parser.add_argument("--max-pages", type=int, default=0)
    args = parser.parse_args()
    if args.action == "infer":
        infer(args.candidate, args.freeze, args.start_page, args.max_pages)
    else:
        summarize(args.candidate, args.freeze)


if __name__ == "__main__":
    main()
