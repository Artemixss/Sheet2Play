"""Guarded, Git-free Phase 4 development commands; no historical benchmark execution."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "reports/zeus-attribution/phase4"
GATE = HERE / ".runtime/phase4/gate"
sys.path[:0] = [str(GATE), str(HERE), str(HERE / "src"), str(ROOT / "Bridge")]
import no_git_guard
from zeus_attribution_prepare import configure_cpu, save_json
from phase4_validation import file_hash


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("compatibility", "admission", "tests"))
    parser.add_argument("args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not no_git_guard.INSTALLED:
        raise RuntimeError("Git prohibition unavailable")
    os.environ["PYTHONPATH"] = os.pathsep.join((str(GATE), str(HERE), str(HERE / "src"), str(ROOT / "Bridge")))
    configure_cpu()
    if args.stage == "admission":
        from phase3_freeze import snapshot
        from screening_common import digest
        from phase4_validation import HISTORICAL_FREEZE_HASH
        current = snapshot()
        legacy_path = HERE / "reports/phase3/phase3-config-freeze-v1-89f385c8790b.json"
        legacy = json.loads(legacy_path.read_text())
        saved = {"schema_version": 1, "scope": "current Phase4 runtime; no historical equality claim",
            "historical_freeze_sha256": HISTORICAL_FREEZE_HASH,
            "current": current, "current_sha256": digest(current),
            "historical_equals_current": legacy == current,
            "added_distributions": {name: sorted(set(packages) - set(legacy["runtime"]["python_distributions"][name]))
                for name, packages in current["runtime"]["python_distributions"].items()},
            "sources": {name: file_hash(HERE / name) for name in ("phase4_validation.py", "phase4_execute.py")},
        }
        destination = OUT / ("current-runtime-admission-expanded.json" if args.args else "current-runtime-admission.json")
        save_json(destination, saved)
        print(json.dumps({"current_sha256": saved["current_sha256"],
                          "historical_equals_current": saved["historical_equals_current"]}), flush=True)
        return 0
    if args.stage == "compatibility":
        import screening_homr_extension as extension
        from phase4_validation import historical_screen, checked_homr_source
        checked_homr_source(extension.SOURCE, extension.REVISION)
        report, digest = extension.compatibility_evidence(allow_create=True)
        historical_screen(extension.BASE_MANIFEST)
        save_json(OUT / "validation-prerequisites.json", {
            "historical_contract": "frozen evidence and selected inputs; not current admission",
            "historical_manifest_sha256": file_hash(extension.BASE_MANIFEST),
            "source_contract": "revision metadata plus complete pinned file set and SHA-256; no Git launch",
            "compatibility_report": str(report), "compatibility_sha256": digest,
            "verification_sources": {name: file_hash(HERE / name) for name in
                ("phase4_validation.py", "screening_homr_compatibility.py", "screening_homr_extension.py", "screening_common.py")},
        })
        print("Historical inputs and current HOMR byte/label/model/interface/import contracts verified", flush=True)
        return 0
    import pytest
    return pytest.main(args.args)


if __name__ == "__main__":
    raise SystemExit(main())
