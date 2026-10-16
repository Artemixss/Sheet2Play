"""Bounded acceptance audit, exact coverage and immutable artifact inventory."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from phase4_validation import file_hash, HISTORICAL_FREEZE_HASH, checked_json
from zeus_attribution_prepare import HERE, configure_cpu, save_json

OUT = HERE / "reports/zeus-attribution/phase4"


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def main() -> None:
    configure_cpu()
    manifest = read(OUT / "experiment-manifest.json")
    report = read(OUT / "analysis-report.json")
    if report["manifest_sha256"] != file_hash(OUT / "experiment-manifest.json"):
        raise ValueError("Analysis identity mismatch")
    for name, expected in manifest["source_pins"].items():
        if file_hash(Path(name)) != expected:
            raise ValueError(f"Pinned original source/model changed: {name}")
    for name, expected in manifest["sources"].items():
        if file_hash(HERE / name) != expected:
            raise ValueError(f"Frozen remedy source changed: {name}")
    checked_json(HERE / "reports/phase3/phase3-config-freeze-v1-89f385c8790b.json", HISTORICAL_FREEZE_HASH)
    rows = []
    for item in manifest["items"]:
        for number, crop in enumerate(item["crops"], 1):
            if file_hash(Path(crop["path"])) != crop["sha256"]:
                raise ValueError("Crop changed")
            work = OUT / "inference" / item["item_id"] / f"system-{number:04d}"
            prediction = read(work / "prediction.json")
            mask = read(work / "mask-prediction.json")
            if prediction["crop_sha256"] != crop["sha256"] or mask["crop_sha256"] != crop["sha256"]:
                raise ValueError("Prediction input identity mismatch")
            masked = mask["wrapper_valid_mask"]
            if masked["preprocessing"] != prediction["wrapper"]["preprocessing"]:
                raise ValueError("Mask condition changed pixels or padded width")
            if not masked["mask_evidence"] or not all(e["valid_steps"] == e["true_count"] == (masked["original_width"] + 15) // 16
                       and e["padded_steps"] >= e["valid_steps"] for e in masked["mask_evidence"]):
                raise ValueError("Original-width mask evidence invalid")
            if all(e["valid_steps"] == e["padded_steps"] for e in masked["mask_evidence"]) and masked["token_ids"] != prediction["wrapper"]["token_ids"]:
                raise ValueError("Unchanged-mask control changed decoder output")
            for variant, output in {"upstream": prediction["upstream"], "wrapper": prediction["wrapper"],
                                    "wrapper_valid_mask": masked}.items():
                if not output["lmx"].strip():
                    raise ValueError("Empty stream lies outside observed conversion parity contract")
                conversion = output["conversion"]
                if conversion["status"] == "succeeded":
                    if file_hash(work / f"{variant}.musicxml") != conversion["musicxml_sha256"]:
                        raise ValueError("Native converted bytes changed")
                rows.append({"item_id": item["item_id"], "system": number, "variant": variant,
                    "conversion_status": conversion["status"], "diagnostics": conversion["diagnostics"],
                    "termination": output["termination"], "unknown_tokens": output["unknown_token_count"]})
    if len(manifest["items"]) != 15 or len(rows) != 72 or len(report["items"]) != 15:
        raise ValueError("Fixed development coverage incomplete")
    stages = Counter()
    for item in report["items"]:
        if set(item["variants"]) != {"upstream", "wrapper", "wrapper_valid_mask"}:
            raise ValueError("Page variant missing")
        for variant, result in item["variants"].items():
            if result.get("trace_failure"):
                stages[result["trace_failure"]["error"]] += 1
    junit = ET.parse(HERE / ".runtime/phase4/final-regression-junit.xml").getroot()
    suites = list(junit.iter("testsuite"))
    failures = sum(int(s.get("failures", "0")) + int(s.get("errors", "0")) for s in suites)
    if failures:
        raise ValueError("Full regression is not green")
    from screening_homr_extension import compatibility_evidence
    compatibility, digest = compatibility_evidence(allow_create=False)
    summary = {"items": 15, "crops": 24, "outputs": 72, "pages": 45,
        "conversion_failures": sum(r["conversion_status"] == "failed" for r in rows),
        "diagnostic_outputs": sum(bool(r["diagnostics"]) for r in rows),
        "diagnostic_lines": sum(len(r["diagnostics"].splitlines()) for r in rows),
        "length_limit_outputs": [r for r in rows if r["termination"] == "length_limit"],
        "unknown_tokens": sum(r["unknown_tokens"] for r in rows), "exact_trace_failures": dict(stages),
        "mask_changed_systems": sum(not r["wrapper_vs_valid_mask_equal"] for r in report["mask_comparisons"]),
        "mask_equals_upstream_systems": sum(r["upstream_vs_valid_mask_equal"] for r in report["mask_comparisons"]),
        "regression": [{k:s.get(k) for k in ("tests", "failures", "errors", "skipped")} for s in suites],
        "compatibility_report": str(compatibility), "compatibility_sha256": digest,
        "current_runtime_admission_sha256": file_hash(OUT / "current-runtime-admission-expanded.json"),
        "historical_freeze_sha256": HISTORICAL_FREEZE_HASH,
        "source_sha256": file_hash(Path(__file__)),
        "additional_sources": {name:file_hash(HERE / name) for name in
            ("phase4_analyze.py", "phase4_replay_conversion.py", "src/sheet2play_omr/research_ties.py",
             "screening_homr_compatibility.py", "screening_homr_extension.py", "screening_common.py")}}
    save_json(OUT / "acceptance-audit.json", summary)
    paths = sorted(p for p in OUT.rglob("*") if p.is_file() and p.name != "artifact-inventory.json")
    save_json(OUT / "artifact-inventory.json", {"scope": "Completed execution evidence before final prose/docs",
        "files": [{"path": str(p.relative_to(OUT)), "bytes": p.stat().st_size, "sha256": file_hash(p)} for p in paths]})
    print(json.dumps({"verified_files":len(paths), "summary": {k:v for k,v in summary.items()
        if k not in {"additional_sources", "exact_trace_failures", "length_limit_outputs"}}}), flush=True)


if __name__ == "__main__":
    main()
