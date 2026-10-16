"""Produce separate Phase 2R readiness evidence using development inputs only."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parent.parent
SRC = HERE / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from phase2 import verify_phase1_freeze  # noqa: E402
from sheet2play_omr.adapter_contract import sha256_file  # noqa: E402
from sheet2play_omr.phase2_fixtures import run_fixture_matrix  # noqa: E402
from sheet2play_omr.phase2r_development import audit_development_collection  # noqa: E402
from sheet2play_omr.phase2r_identity import collect_identity  # noqa: E402


HISTORICAL_PHASE2_HASHES = {
    "phase2-report.json": "bf682bfd73ac201b2509938d720acfce2a823eae2456e7e2bc895feb18b5edd8",
    "adapter-manifest.json": "ce8678292805a0e1e596f6242d117458ef161b0ecbbe6f83c3a178468e673d24",
    "fixture-report.json": "59056e4fac420dee9605e6ec2f1507d31da7e660ea54d1e7faa03c3809841d58",
    "phase2-plan-checklist.json": "df9e088b9e2a0637a1a06453a194ba738d4b2885eff37307e24389b11f7c21bc",
}


def verify_historical_artifacts() -> dict[str, Any]:
    phase1 = verify_phase1_freeze()
    phase2_root = HERE / "reports" / "phase2"
    mismatches = [
        name for name, expected in HISTORICAL_PHASE2_HASHES.items()
        if sha256_file(phase2_root / name) != expected
    ]
    if mismatches:
        raise ValueError("Historical Phase 2 artifacts changed: " + ", ".join(mismatches))
    return {"phase1": phase1, "phase2_artifact_count": len(HISTORICAL_PHASE2_HASHES), "phase2_hash_mismatches": []}


def _write_once(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite Phase 2R evidence: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def audit_development(output: Path) -> dict[str, Any]:
    frozen = verify_historical_artifacts()
    fixtures = run_fixture_matrix()
    if not all(item.passed for item in fixtures):
        raise RuntimeError("Phase 2R fixture matrix failed")
    converter = HERE / ".runtime" / "phase2r" / "croma" / "croma-windows-x86_64.exe"
    staging = HERE / ".runtime" / "phase2r" / "development-audit"
    rows = audit_development_collection(WORKSPACE, converter, staging)
    identity = collect_identity(WORKSPACE)
    feature_counts = Counter(
        name for row in rows for name, present in row["features"].items()
        if isinstance(present, bool) and present
    )
    report = {
        "schema_version": 1,
        "phase": "2R",
        "status": "passed" if all(row["converter_status"] == "succeeded" for row in rows) else "conversion_gaps",
        "scope": {
            "development_only": True,
            "smb_inference_count": 0,
            "olimpic_inference_count": 0,
            "private_diagnostic_inference_count": 0,
            "phase3_started": False,
            "training_started": False,
        },
        "comparison_config_sha256": sha256_file(HERE / "comparison-config-v2.json"),
        "frozen_artifacts": frozen,
        "fixtures": [{"name": row.name, "passed": row.passed, "evidence": row.evidence} for row in fixtures],
        "development_item_count": len(rows),
        "generated_control_count": sum(row["collection"] == "generated" for row in rows),
        "open_composition_count": sum(row["collection"] == "open" for row in rows),
        "feature_counts": dict(sorted(feature_counts.items())),
        "converter_success_count": sum(row["converter_status"] == "succeeded" for row in rows),
        "development_items": rows,
        "runtime_identity": identity,
    }
    _write_once(output, report)
    return report


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--audit-development", action="store_true")
    mode.add_argument("--identity-only", action="store_true")
    parser.add_argument(
        "--output", type=Path,
    )
    args = parser.parse_args(arguments)
    try:
        if args.identity_only:
            output = args.output or HERE / "reports" / "phase2r" / "runtime-identity-v1.json"
            report = {
                "schema_version": 1,
                "phase": "2R",
                "scope": {"development_only": True, "phase3_started": False},
                "comparison_config_sha256": sha256_file(HERE / "comparison-config-v2.json"),
                "frozen_artifacts": verify_historical_artifacts(),
                "identity_collector_sha256": sha256_file(
                    SRC / "sheet2play_omr" / "phase2r_identity.py"
                ),
                "runtime_identity": collect_identity(WORKSPACE),
            }
            _write_once(output, report)
        else:
            output = args.output or HERE / "reports" / "phase2r" / "development-audit-v1.json"
            report = audit_development(output)
    except Exception as error:
        print(f"Phase 2R audit failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    if args.identity_only:
        print(json.dumps({"identity_report": str(output), "phase3_started": False}, sort_keys=True))
    else:
        print(json.dumps({
            "status": report["status"],
            "development_item_count": report["development_item_count"],
            "converter_success_count": report["converter_success_count"],
            "phase3_started": report["scope"]["phase3_started"],
        }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
