"""Prepare local visual evidence for two implicit-pickup page boundaries."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def prepare(row: dict, output: Path, renderer: Path) -> dict:
    import pdfplumber
    from PIL import Image
    from homr_baseline_pages import layout_markers
    for name in ("source", "pdf", "musicxml"):
        if digest(Path(row[name + "_path"])) != row[name + "_sha256"]:
            raise ValueError("Frozen boundary source changed")
    item = output / row["id"]
    item.mkdir(parents=True, exist_ok=False)
    prefix = item / "page2"
    subprocess.run([str(renderer), "-f", "2", "-l", "2", "-png", "-r", "300",
                    row["pdf_path"], str(prefix)], check=True, timeout=60, capture_output=True)
    pages = list(item.glob("page2-*.png"))
    if len(pages) != 1:
        raise ValueError("Expected one second-page render")
    for path, region, name in ((Path(row["page_images"][0]["path"]), "bottom", "page1-last-systems.png"),
                               (pages[0], "top", "page2-first-systems.png")):
        with Image.open(path) as source:
            box = (0, source.height // 2, source.width, source.height) if region == "bottom" else (
                0, 0, source.width, source.height // 2)
            source.crop(box).save(item / name)
    parts = []
    for part in ET.parse(row["musicxml_path"]).getroot().findall("part"):
        measures = part.findall("measure")
        start = next(i for i, m in enumerate(measures) if i and m.find("print[@new-page='yes']") is not None)
        stop = next((i for i in range(start + 1, len(measures))
                     if measures[i].find("print[@new-page='yes']") is not None), len(measures))
        systems = [m.get("number") for m in measures[start:stop]
                   if m.find("print[@new-system='yes']") is not None]
        excerpt = []
        for m in measures[start - 1:start + 2]:
            excerpt.append({"number": m.get("number"), "implicit": m.get("implicit"),
                            "notes": [{"pitch": {c.tag: c.text for c in n.findall("pitch/*")},
                                       "rest": n.find("rest") is not None, "grace": n.find("grace") is not None,
                                       "duration": n.findtext("duration"), "type": n.findtext("type"),
                                       "voice": n.findtext("voice"), "staff": n.findtext("staff")}
                                      for n in m.findall("note")]})
        parts.append({"part": part.get("id"), "first_page_measure_count": start,
                      "next_page_measure": measures[start].get("number"),
                      "next_page_implicit": measures[start].get("implicit"),
                      "page2_later_system_numbers": systems, "boundary_measures": excerpt})
    with pdfplumber.open(row["pdf_path"]) as pdf:
        _, numbers = layout_markers(pdf.pages[0], pdf.pages[1],
                                    [m.get("number") for m in ET.parse(row["musicxml_path"]).getroot()
                                     .find("part").findall("measure")[:parts[0]["first_page_measure_count"]]]
                                    )
    return {"item_id": row["id"], "parts": parts, "pdf_page2_left_margin_numbers": numbers,
            "source_xml": {"path": row["musicxml_path"], "sha256": row["musicxml_sha256"]},
            "source_pdf": {"path": row["pdf_path"], "sha256": row["pdf_sha256"]},
            "artifacts": [{"path": str(p.resolve()), "sha256": digest(p)} for p in sorted(item.glob("*.png"))]}


def record_review(output: Path, previous: Path, findings: Path) -> None:
    ledger = json.loads(previous.read_text())
    evidence = json.loads((output / "boundary-evidence.json").read_text())
    reviewed = json.loads(findings.read_text())
    cases = {case["item_id"]: case for case in evidence["cases"]}
    if set(cases) != set(reviewed) or set(cases) != {"openscore-6583907", "openscore-6583966"}:
        raise ValueError("Expected exactly the two reviewed implicit boundaries")
    for page in ledger["pages"]:
        if page["item_id"] not in cases:
            continue
        case = cases[page["item_id"]]
        for artifact in case["artifacts"] + [case["source_xml"], case["source_pdf"]]:
            if digest(Path(artifact["path"])) != artifact["sha256"]:
                raise ValueError("Boundary evidence changed")
        parts = case["parts"]
        if (not page["pixel_identity_verified"] or case["source_xml"]["sha256"] != page["whole_reference_sha256"]
                or any(p["next_page_measure"] != "X1" or p["next_page_implicit"] != "yes" or
                       p["page2_later_system_numbers"] != case["pdf_page2_left_margin_numbers"]
                       for p in parts)
                or [p["first_page_measure_count"] for p in parts] !=
                   [p["first_page_measure_count"] for p in page["parts"]]):
            raise ValueError("Reviewed implicit-boundary contract mismatch")
        page.update(range_verified=True, export_layout_matches_pdf=True,
                    boundary_review={"finding": reviewed[page["item_id"]], "artifacts": case["artifacts"],
                                     "evidence_sha256": digest(output / "boundary-evidence.json"),
                                     "review_sha256": digest(findings)})
    ledger["previous_ledger"] = {"path": str(previous.resolve()), "sha256": digest(previous)}
    with (output / "page-correspondence.json").open("x", encoding="utf-8") as stream:
        json.dump(ledger, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"page_ranges_verified": sum(p["range_verified"] for p in ledger["pages"])}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--renderer", type=Path)
    parser.add_argument("--previous-ledger", type=Path)
    parser.add_argument("--reviewed-findings", type=Path)
    args = parser.parse_args()
    if args.previous_ledger:
        if not args.reviewed_findings:
            parser.error("--reviewed-findings is required with --previous-ledger")
        record_review(args.output, args.previous_ledger, args.reviewed_findings)
        raise SystemExit(0)
    if not args.renderer:
        parser.error("--renderer is required to prepare boundary evidence")
    rows = [json.loads(line) for line in Path("Research/omr/reports/phase1/development-open.jsonl")
            .read_text().splitlines() if line.strip()]
    cases = [prepare(row, args.output, args.renderer) for row in rows
             if row["id"] in ("openscore-6583907", "openscore-6583966")]
    with (args.output / "boundary-evidence.json").open("x", encoding="utf-8") as stream:
        json.dump({"cases": cases, "visual_review_pending": True}, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"cases": len(cases)}))
