"""Check the bounded Phase 1 documentation and evidence closure offline."""
from pathlib import Path
import ast
import json
import re
from urllib.parse import unquote

from homr_baseline import digest, save

EVIDENCE = Path(__file__).resolve().parent
WORKSPACE = EVIDENCE.parents[4]


def main():
    paths = [WORKSPACE / "plans/MAIN_PLAN.md", WORKSPACE / "plans/README.md",
             EVIDENCE.parent / "handoff.md", EVIDENCE / "REPORT.md", EVIDENCE / "job-record.md"]
    checked = 0
    for path in paths:
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            if re.match(r"\w+://", target) or target.startswith("#"):
                continue
            resolved = path.parent / unquote(target.split("#", 1)[0].strip("<>"))
            if not resolved.exists():
                raise ValueError(f"Broken link: {path} -> {target}")
            checked += 1
    scripts = [WORKSPACE / "Research/omr" / name for name in
               ("homr_baseline.py", "homr_baseline_infer.py", "homr_baseline_analyze.py", "homr_baseline_closeout.py")]
    for path in scripts:
        ast.parse(path.read_text(encoding="utf-8"))
    closure = json.loads((EVIDENCE / "closeout.json").read_text())
    network = closure["network"]
    if closure["phase2_started"] or network["RequestedResearchNetworkTransfers"] != 0:
        raise ValueError("Execution scope or network accounting drift")
    if network["RootWorkerLockPresent"] or network["Processes"]:
        raise ValueError("Final process closure incomplete")
    if (EVIDENCE / "gate/blocked-actions.jsonl").exists():
        raise ValueError("Inspect blocked network/Git attempt before closure")
    job = json.loads((EVIDENCE / "jobs/closeout/result.json").read_text())
    if job["status"] != "complete":
        raise ValueError("Evidence closeout job incomplete")
    artifact_paths = paths + scripts + [EVIDENCE / name for name in
        ("closeout.json", "patch-inventory.json", "failure-traces.json", "development-analysis.json",
         "tie-boundary.json", "runtime-inventory.json", "reference-eligibility.json", "network-closeout.json")]
    save(EVIDENCE / "verification.json", {"local_links_checked": checked, "phase2_started": False,
         "artifacts": [{"path": str(path), "sha256": digest(path)} for path in artifact_paths]})
    print(json.dumps({"local_links_checked": checked, "scope": "Phase 1 only", "status": "verified partial closure"}))


if __name__ == "__main__":
    main()
