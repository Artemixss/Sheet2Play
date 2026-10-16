"""Require musical equivalence before probing the title-disabled research profile."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from homr_baseline import digest, save
from homr_baseline_closeout import verify_rows
from homr_baseline_profile import validate_profile
from sheet2play_omr.zeus_trace import normalized_notes, xml_trace


def xml_without_title(path: Path) -> str:
    root = ET.parse(path).getroot()
    title = root.find("work/work-title")
    if title is None:
        raise ValueError("Expected native work-title metadata")
    title.text = ""
    return ET.canonicalize(ET.tostring(root, encoding="unicode"))


def musical_features(root: Path) -> dict:
    tokens = json.loads((root / "tokens.json").read_text())
    crops = {p.name: digest(p) for p in sorted(root.glob("input_staff-*_input.jpg"))}
    if not crops or not tokens.get("decoder_outputs") or not tokens.get("exporter_inputs"):
        raise ValueError("Incomplete native musical capture")
    xml = root / "input.musicxml"
    segments, measures = xml_trace(xml)
    events = sorted((n.pitch, str(n.onset), str(n.duration), n.staff, n.voice)
                    for n in normalized_notes(xml))
    return {"input": digest(root / "input.png"), "crops": crops,
            "positions": digest(root / "input.txt"),
            "decoder_outputs": tokens["decoder_outputs"], "exporter_inputs": tokens["exporter_inputs"],
            "xml_except_title": xml_without_title(xml), "literal_xml": [n.json() for n in segments],
            "measures": measures, "production_timed_events": events}


def compare(baseline: Path, candidate: Path, item: str, profile: dict) -> dict:
    left, right = baseline / "development" / item, candidate / "development" / item
    receipts = []
    for root in (left, right):
        receipt = json.loads((root / "result.json").read_text())
        if receipt["status"] != "complete":
            raise ValueError("Equivalence requires completed captures")
        verify_rows(receipt["artifacts"])
        receipts.append(receipt)
    if (receipts[0]["runtime_identity"] != profile["baseline_runtime_identity"] or
            receipts[1].get("research_profile_identity") != profile["identity_sha256"]):
        raise ValueError("Equivalence profile/runtime identity mismatch")
    a, b = musical_features(left), musical_features(right)
    checks = {key: a[key] == b[key] for key in a}
    no_title = ET.parse(right / "input.musicxml").findtext("work/work-title", "") == ""
    passed = all(checks.values()) and no_title
    return {"item_id": item, "passed": passed, "checks": checks, "title_disabled": no_title,
            "musical_event_count": len(b["production_timed_events"]),
            "baseline_receipt": {"path": str((left / "result.json").resolve()), "sha256": digest(left / "result.json")},
            "profile_receipt": {"path": str((right / "result.json").resolve()), "sha256": digest(right / "result.json")}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--runtime", required=True)
    args = parser.parse_args()
    profile = validate_profile(args.candidate / "profile.json", args.runtime)
    rows = [compare(args.baseline, args.candidate, item, profile)
            for item in ("openscore-6211535", "openscore-6212193")]
    passed = all(row["passed"] for row in rows)
    save(args.candidate / "equivalence.json", {"research_profile_identity": profile["identity_sha256"],
         "passed": passed, "examples": rows, "limit": "Empirical equivalence on these two examples only"})
    print(json.dumps({"passed": passed, "examples": rows}))
    raise SystemExit(0 if passed else 1)
