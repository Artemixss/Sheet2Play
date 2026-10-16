"""Verify the resumed Phase 1 documentation and preserved evidence offline."""
from pathlib import Path
import ast
import json
import re
from urllib.parse import unquote

from homr_baseline import digest, save
from homr_baseline_closeout import verify_rows

RESUMED = Path(__file__).resolve().parent
EVIDENCE = RESUMED.parent
WORKSPACE = EVIDENCE.parents[4]


def main() -> None:
    closure = json.loads((RESUMED / "closeout.json").read_text())
    verify_rows(closure["artifacts"])
    original = json.loads((EVIDENCE / "verification.json").read_text())
    preserved = [row for row in original["artifacts"]
                 if Path(row["path"]).is_relative_to(EVIDENCE)]
    verify_rows(preserved)
    paths = [WORKSPACE / "plans/MAIN_PLAN.md", WORKSPACE / "plans/README.md",
             EVIDENCE.parent / "handoff.md", RESUMED / "REPORT.md", RESUMED / "job-record.md"]
    links = 0
    for path in paths:
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            if re.match(r"\w+://", target) or target.startswith("#"):
                continue
            local = path.parent / unquote(target.split("#", 1)[0].strip("<>"))
            if not local.exists():
                raise ValueError(f"Broken link: {path} -> {target}")
            links += 1
    scripts = list((RESUMED / "executed-source").glob("*.py")) + [Path(__file__)]
    for path in scripts:
        ast.parse(path.read_text(encoding="utf-8"))
    if closure["phase2_started"] or closure["network"]["RequestedResearchNetworkTransfers"]:
        raise ValueError("Execution scope/network drift")
    if (WORKSPACE / ".research-worker.lock").exists() or (EVIDENCE / "gate/blocked-actions.jsonl").exists():
        raise ValueError("Inspect active lock or blocked action before closure")
    job = json.loads((RESUMED / "jobs/closeout/result.json").read_text())
    if job["status"] != "complete":
        raise ValueError("Closeout incomplete")
    save(RESUMED / "verification.json", {"local_links_checked": links,
         "original_evidence_artifacts_unchanged": len(preserved), "phase2_started": False,
         "status": "verified partial resource-stopped closure",
         "artifacts": [{"path": str(path.resolve()), "sha256": digest(path)}
                       for path in paths + scripts + [RESUMED / "closeout.json", RESUMED / "network-closeout.json"]]})
    print(json.dumps({"local_links_checked": links, "original_evidence_artifacts_unchanged": len(preserved),
                      "status": "verified partial resource-stopped closure"}))


if __name__ == "__main__":
    main()
