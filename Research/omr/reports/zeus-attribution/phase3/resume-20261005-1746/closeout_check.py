"""Validate active links and preserved Phase 3 receipt/artifact identities."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / "Research/omr/reports/zeus-attribution/phase3"
EVIDENCE = OUT / "resume-20261005-1746"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_links() -> dict:
    documents = [ROOT / "AGENTS.md", ROOT / "CONTEXT.md", ROOT / "plans/README.md",
                 ROOT / "plans/MAIN_PLAN.md", OUT / "handoff.md", OUT / "job-record.md",
                 OUT / "REPORT.md", OUT / "CROP_REVIEW.md"]
    count = 0
    for document in documents:
        text = document.read_text(encoding="utf-8")
        if document.name == "CONTEXT.md":
            text = text.split("<!-- STARTUP_CONTEXT_END -->", 1)[0]
        for raw in re.findall(r"\[[^\]\n]+\]\(([^)\n]+)\)", text):
            target = unquote(raw.strip("<>" ).split("#", 1)[0])
            if not target or re.match(r"(?:https?|app|codex|mailto):", target):
                continue
            if not (document.parent / target).is_file():
                raise FileNotFoundError(f"Broken link: {document}: {raw}")
            count += 1
    return {"documents": len(documents), "local_file_links": count}


def check_artifacts() -> dict:
    artifact = load(OUT / "artifact-audit.json")
    for record in artifact["artifacts"]:
        if digest(Path(record["path"])) != record["sha256"]:
            raise ValueError(f"Audited artifact changed: {record['path']}")
    copies = [(EVIDENCE / "audit_artifacts.py", artifact["audit_script_sha256"])]
    parser = load(OUT / "parser-diagnostics.json")
    conversion = load(OUT / "conversion-diagnostics.json")
    copies.extend([(ROOT / "Research/omr/zeus_attribution_parser_trace.py", parser["identity"]["script_sha256"]),
                   (EVIDENCE / "replay_conversion.py", conversion["identity"]["script_sha256"])])
    for path, expected in copies:
        if digest(path) != expected:
            raise ValueError(f"Diagnostic script changed: {path}")
    for path, expected in conversion["identity"]["source_hashes"].items():
        if digest(Path(path)) != expected:
            raise ValueError(f"Conversion source changed: {path}")
    manifest_hash = digest(OUT / "experiment-manifest.json")
    if parser["identity"]["manifest_sha256"] != manifest_hash or conversion["identity"]["manifest_sha256"] != manifest_hash:
        raise ValueError("Sidecar manifest identities differ")
    if parser["identity"]["analysis_sha256"] != digest(OUT / "analysis-report.json"):
        raise ValueError("Parser diagnostic analysis identity differs")
    missing_rests = Counter()
    for path in (OUT / "inference").rglob("*.musicxml"):
        for note in ET.parse(path).iter("note"):
            rest = note.find("rest")
            if rest is not None and note.find("duration") is None:
                missing_rests[rest.get("measure")] += 1
    if missing_rests != Counter({"yes": 109}):
        raise ValueError(f"Missing-duration rest classification differs: {missing_rests}")
    return {"hash_records": len(artifact["artifacts"]), "diagnostic_script_copies": len(copies),
            "conversion_source_hashes": len(conversion["identity"]["source_hashes"]),
            "missing_full_rest_duration": missing_rests["yes"]}


def check_regression() -> dict:
    filenames = ("regression-cpu-detector-junit.xml", "regression-parser-trace-junit.xml")
    failures = []
    for filename in filenames:
        root = ET.parse(EVIDENCE / filename)
        failures.append({(n.get("classname"), n.get("name")) for n in root.iter("testcase")
                         if n.find("failure") is not None})
    if failures[0] != failures[1] or len(failures[1]) != 14:
        raise ValueError("Regression failure IDs changed")
    native = load(EVIDENCE / "final-native.json")
    if native["repository_python_workers"] or native["global_worker_lock_exists"]:
        raise ValueError("Native closeout still records live work")
    return {"unchanged_failed_test_ids": len(failures[1]), "owned_workers_closed": True}


def main() -> None:
    result = {"passed": True, "links": check_links(), "artifacts": check_artifacts(),
              "regression": check_regression(), "script_sha256": digest(Path(__file__))}
    with (EVIDENCE / "closeout-check.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
