from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .assets import RuntimePaths, verify_runtime
from .adaptation import AdapterTrainingConfig, train_adapter
from .benchmark import run_benchmark
from .dataset import load_source_manifest, split_by_composition, validate_fixture_coverage, write_splits
from .errors import ResearchError
from .gates import baseline_adaptation_gate, enforce_cloud_budget, promotion_gate
from .inference import TranscodaRunner, check_determinism, infer_document
from .materialize import materialize_dataset


def _json_file(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ResearchError("INPUT_INVALID", "cli", f"Cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise ResearchError("INPUT_INVALID", "cli", f"Expected a JSON object in {path}")
    return value


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="s2p-omr-research")
    subparsers = parser.add_subparsers(dest="command", required=True)

    verify = subparsers.add_parser("verify-runtime")
    verify.add_argument("--cuda-smoke", action="store_true")

    infer = subparsers.add_parser("infer")
    infer.add_argument("input", type=Path)
    infer.add_argument("--output-dir", type=Path, required=True)
    infer.add_argument("--mode", choices=("beam", "grammar", "zeus"), required=True)

    benchmark = subparsers.add_parser("benchmark")
    benchmark.add_argument("manifest", type=Path)
    benchmark.add_argument("--output", type=Path, required=True)
    benchmark.add_argument("--mode", choices=("beam", "grammar", "zeus", "both"), default="both")
    benchmark.add_argument("--require-acceptance-size", action="store_true")

    dataset = subparsers.add_parser("prepare-dataset")
    dataset.add_argument("manifest", type=Path)
    dataset.add_argument("--output-dir", type=Path, required=True)
    dataset.add_argument("--seed", type=int, default=20260813)
    dataset.add_argument("--train-count", type=int, default=25000)
    dataset.add_argument("--validation-count", type=int, default=2000)
    dataset.add_argument("--test-count", type=int, default=2000)
    dataset.add_argument("--require-fixture-coverage", action="store_true")

    gate = subparsers.add_parser("evaluate-gate")
    gate.add_argument("candidate", type=Path)
    gate.add_argument("homr", type=Path)
    gate.add_argument("--promotion", action="store_true")

    budget = subparsers.add_parser("check-budget")
    budget.add_argument("--hourly-rate", type=float, required=True)
    budget.add_argument("--estimated-hours", type=float, required=True)
    budget.add_argument("--maximum-cost", type=float, default=10.0)

    adaptation = subparsers.add_parser("train-adapter")
    adaptation.add_argument("--train-manifest", type=Path, required=True)
    adaptation.add_argument("--validation-manifest", type=Path, required=True)
    adaptation.add_argument("--candidate-summary", type=Path, required=True)
    adaptation.add_argument("--homr-summary", type=Path, required=True)
    adaptation.add_argument("--output-dir", type=Path, required=True)
    adaptation.add_argument("--hourly-rate", type=float, required=True)
    adaptation.add_argument("--estimated-hours", type=float, required=True)
    adaptation.add_argument("--max-runtime-hours", type=float, default=12.0)
    adaptation.add_argument("--max-temperature-c", type=int, default=85)

    determinism = subparsers.add_parser("check-determinism")
    determinism.add_argument("input", type=Path)
    determinism.add_argument("--mode", choices=("beam", "grammar"), required=True)
    determinism.add_argument("--runs", type=int, default=3)

    materialize = subparsers.add_parser("materialize-dataset")
    materialize.add_argument("split_manifest", type=Path)
    materialize.add_argument("--output-dir", type=Path, required=True)
    materialize.add_argument("--workers", type=int, default=1)
    materialize.add_argument("--seed", type=int, default=20260813)
    return parser


def _execute(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "verify-runtime":
        metadata: dict[str, Any] = verify_runtime()
        if args.cuda_smoke:
            runner = TranscodaRunner("beam", max_tokens=8)
            metadata["cuda_smoke"] = runner.smoke()
        return metadata
    if args.command == "infer":
        return infer_document(args.input, args.output_dir, args.mode)
    if args.command == "benchmark":
        modes = ("beam", "grammar") if args.mode == "both" else (args.mode,)
        return run_benchmark(
            args.manifest,
            args.output,
            modes=modes,
            require_acceptance_size=args.require_acceptance_size,
        )
    if args.command == "prepare-dataset":
        records = load_source_manifest(args.manifest)
        if args.require_fixture_coverage:
            missing = validate_fixture_coverage(records)
            if missing:
                raise ResearchError(
                    "DATASET_INVALID",
                    "dataset",
                    f"Missing required synthetic fixture tags: {sorted(missing)}",
                )
        splits = split_by_composition(
            records,
            seed=args.seed,
            train_count=args.train_count,
            validation_count=args.validation_count,
            test_count=args.test_count,
        )
        return {name: str(path.resolve()) for name, path in write_splits(splits, args.output_dir).items()}
    if args.command == "evaluate-gate":
        candidate = _json_file(args.candidate)
        homr = _json_file(args.homr)
        decision = promotion_gate(candidate, homr) if args.promotion else baseline_adaptation_gate(candidate, homr)
        return {"passed": decision.passed, "failures": list(decision.failures)}
    if args.command == "check-budget":
        cost = enforce_cloud_budget(args.hourly_rate, args.estimated_hours, args.maximum_cost)
        return {"approved": True, "estimated_cost_usd": cost, "maximum_cost_usd": args.maximum_cost}
    if args.command == "train-adapter":
        return train_adapter(
            args.train_manifest,
            args.validation_manifest,
            args.output_dir,
            args.candidate_summary,
            args.homr_summary,
            hourly_rate=args.hourly_rate,
            estimated_hours=args.estimated_hours,
            config=AdapterTrainingConfig(
                max_runtime_hours=args.max_runtime_hours,
                max_temperature_c=args.max_temperature_c,
            ),
        )
    if args.command == "check-determinism":
        return check_determinism(args.input, args.mode, runs=args.runs)
    if args.command == "materialize-dataset":
        return materialize_dataset(
            args.split_manifest,
            args.output_dir,
            workers=args.workers,
            seed=args.seed,
        )
    raise ResearchError("INPUT_INVALID", "cli", f"Unknown command {args.command}")


def main(argv: list[str] | None = None) -> int:
    try:
        args = _build_parser().parse_args(argv)
        result = _execute(args)
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
        return 0
    except ResearchError as error:
        print(
            json.dumps(
                {
                    "error": {
                        "code": error.code,
                        "stage": error.stage,
                        "message": str(error),
                        "page": error.page,
                    }
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    except KeyboardInterrupt:
        print(json.dumps({"error": {"code": "CANCELLED", "stage": "cli", "message": "Cancelled"}}), file=sys.stderr)
        return 130
    except Exception as error:
        print(
            json.dumps(
                {"error": {"code": "INTERNAL_ERROR", "stage": "cli", "message": str(error)}},
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
