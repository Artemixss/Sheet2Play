"""Verify fixed evidence and changed-document links without starting inference."""
from __future__ import annotations

import json
from pathlib import Path
import re

from phase4_validation import file_hash, safe_path
from zeus_attribution_prepare import HERE, ROOT, configure_cpu, save_json

OUT = HERE / "reports/zeus-attribution/phase4"


def main() -> None:
    configure_cpu()
    docs = [ROOT / "AGENTS.md", ROOT / "CONTEXT.md", ROOT / "plans/MAIN_PLAN.md",
            ROOT / "plans/README.md", OUT / "REPORT.md", OUT / "handoff.md",
            OUT / "job-record.md", OUT.parent / "phase3/handoff.md"]
    links, bad = 0, []
    for doc in docs:
        content = doc.read_text(encoding="utf-8")
        if doc.name == "CONTEXT.md":
            content = content.split("<!-- STARTUP_CONTEXT_END -->")[0]
        for match in re.finditer(r"\[[^\]\n]+\]\(([^)\n]+)\)", content):
            target = match[1].strip("<>").split("#", 1)[0]
            if not target or re.match(r"^[a-z]+://", target):
                continue
            links += 1
            if not (doc.parent / target).exists():
                bad.append((doc, target))
    audit = json.loads((OUT / "acceptance-audit.json").read_text())
    if audit["outputs"] != 72 or audit["pages"] != 45:
        raise ValueError("Incomplete fixed outcome audit")
    destination = OUT / "artifact-inventory-final.json"
    paths = sorted(p for p in OUT.rglob("*") if p.is_file() and p.suffix != ".md"
                   and not p.name.startswith("artifact-inventory") and p.name != "delivery-verification.json")
    records = [{"path":str(p.relative_to(OUT)), "bytes":p.stat().st_size, "sha256":file_hash(p)} for p in paths]
    save_json(destination, {"scope":"Final execution evidence; mutable Markdown and inventory/verification receipts excluded", "files":records})
    for row in records:
        path = safe_path(OUT, row["path"])
        if path.stat().st_size != row["bytes"] or file_hash(path) != row["sha256"]:
            raise ValueError("Delivery evidence changed during verification")
    remaining = [f"{doc.relative_to(ROOT)} -> {target}" for doc, target in bad
                 if not (doc.parent / target).exists()]
    if remaining:
        raise ValueError(f"Broken links: {remaining}")
    save_json(OUT / "delivery-verification.json", {"verified_files":len(records), "checked_links":links,
        "inventory_sha256":file_hash(destination), "source_sha256":file_hash(Path(__file__)),
        "documents":{str(p.relative_to(ROOT)):file_hash(p) for p in docs}})
    print(json.dumps({"verified_files":len(records), "checked_links":links}), flush=True)


if __name__ == "__main__":
    main()
