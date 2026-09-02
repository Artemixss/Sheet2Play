from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from sheet2play_omr.olimpic import (
    load_test_partition,
    select_stratified_canary,
    write_benchmark_manifest,
)
from sheet2play_omr.phase3_benchmark import run_checkpointed_benchmark


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Measure the homr baseline over the OLiMPiC scanned partition"
    )
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=root / "data" / "olimpic" / "olimpic-1.0-scanned",
    )
    parser.add_argument("--output-dir", type=Path, default=root / "reports" / "phase3")
    parser.add_argument("--canary-size", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20260814)
    parser.add_argument("--no-full", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    all_samples = load_test_partition(args.dataset_root)
    canary = select_stratified_canary(
        all_samples,
        count=args.canary_size,
        seed=args.seed,
    )
    canary_manifest_hash = write_benchmark_manifest(
        canary,
        args.output_dir / "olimpic-scanned-canary.jsonl",
    )
    full_manifest_hash = write_benchmark_manifest(
        all_samples,
        args.output_dir / "olimpic-scanned-test.jsonl",
    )
    print(
        f"Prepared deterministic canary: {len(canary)} systems across "
        f"{len({sample.score_id for sample in canary})} scores",
        flush=True,
    )
    canary_report = run_checkpointed_benchmark(
        canary,
        args.output_dir / "canary.checkpoint.json",
    )
    canary_report["manifest_sha256"] = canary_manifest_hash
    _write_json(args.output_dir / "canary-report.json", canary_report)

    # The canary and retention gates in sheet2play_omr.gates score a candidate engine
    # against this baseline. There is no candidate now that Transcoda is gone, so this
    # run only measures homr; wire the gates back up when a replacement engine lands.
    final_report: dict[str, Any] = {
        "schema_version": 1,
        "dataset": {
            "root": str(args.dataset_root.resolve()),
            "test_systems": len(all_samples),
            "test_scores": len({sample.score_id for sample in all_samples}),
            "full_manifest_sha256": full_manifest_hash,
        },
        "canary": canary_report,
        "full_benchmark": None,
        "status": "canary_measured",
    }
    if not args.no_full:
        final_report["full_benchmark"] = run_checkpointed_benchmark(
            all_samples,
            args.output_dir / "full.checkpoint.json",
        )
        final_report["status"] = "baseline_measured"

    _write_json(args.output_dir / "phase3-report.json", final_report)
    summary = canary_report["homr"]["summary"]
    print(
        json.dumps(
            {
                "status": final_report["status"],
                "canary_homr": {
                    key: summary[key]
                    for key in (
                        "structural_validity",
                        "pitch_f1",
                        "onset_f1",
                        "onset_duration_f1",
                    )
                },
            }
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Phase 3 cancelled; checkpoint is resumable.", file=sys.stderr)
        raise SystemExit(130)
