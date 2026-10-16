"""Verify and render the one frozen eligible local diagnostic without disclosing its name."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from PIL import Image

from phase2 import verify_phase1_freeze
from sheet2play_omr.adapter_contract import sha256_file


HERE = Path(__file__).resolve().parent
REPORT = HERE / ".runtime" / "phase3" / "private-diagnostic" / "preflight.json"
PAGES = REPORT.parent / "pages"
LIBRARY = Path.home() / "AppData" / "Local" / "Sheet2Play" / "songs"


def _eligible_pair() -> tuple[dict[str, Any], Path, Path]:
    frozen = json.loads((HERE / "reports" / "phase1" / "local-diagnostics.json").read_text(encoding="utf-8"))
    eligible = [row for row in frozen["items"] if row["eligible"]]
    if len(eligible) != 1 or frozen["eligible"] != 1:
        raise RuntimeError("Frozen local diagnostic eligibility changed")
    item = eligible[0]
    pairs = json.loads((HERE / "reports" / "library" / "pairs.json").read_text(encoding="utf-8"))["pairs"]
    matches = [entry for entry in pairs
               if hashlib.sha256(str(entry.get("pdf", "")).encode("utf-8")).hexdigest() == item["id"]]
    if len(matches) != 1 or matches[0].get("status") != "confirmed":
        raise RuntimeError("Eligible local diagnostic pair is missing or ambiguous")
    pair = matches[0]
    pdf = LIBRARY / "pdf" / f"{pair['pdf']}.pdf"
    reference = next((path for path in (LIBRARY / pair["reference"], HERE / pair["reference"])
                      if path.is_file()), None)
    if not pdf.is_file() or reference is None:
        raise RuntimeError("Eligible local diagnostic source or reference is unavailable")
    if sha256_file(pdf) != item["pdf_sha256"] or sha256_file(reference) != item["reference_sha256"]:
        raise RuntimeError("Eligible local diagnostic differs from the Phase-1 freeze")
    return item, pdf, reference


def _identity(item: dict[str, Any], renderer: Path) -> dict[str, Any]:
    return {
        "private_id_sha256": item["id"],
        "pdf_sha256": item["pdf_sha256"],
        "reference_sha256": item["reference_sha256"],
        "phase1_local_diagnostics_sha256": sha256_file(HERE / "reports" / "phase1" / "local-diagnostics.json"),
        "phase1_pairs_sha256": sha256_file(HERE / "reports" / "library" / "pairs.json"),
        "phase1_review_sha256": sha256_file(HERE / "local-diagnostic-review.json"),
        "renderer_sha256": sha256_file(renderer),
        "preflight_source_sha256": sha256_file(Path(__file__)),
        "render_dpi": 300,
    }


def _page_record(path: Path) -> dict[str, Any]:
    with Image.open(path) as image:
        image.verify()
    with Image.open(path) as image:
        width, height = image.size
    return {"page": int(path.stem.split("-")[-1]), "sha256": sha256_file(path),
            "width": width, "height": height}


def _render(pdf: Path, renderer: Path) -> list[dict[str, Any]]:
    if PAGES.exists():
        raise FileExistsError("Partial local diagnostic rendering needs inspection")
    PAGES.mkdir(parents=True)
    try:
        result = subprocess.run([str(renderer), "-png", "-r", "300", str(pdf), str(PAGES / "page")],
                                capture_output=True, timeout=300, check=False)
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("Local diagnostic render exceeded 300 seconds") from error
    if result.returncode != 0:
        raise RuntimeError(f"Local diagnostic renderer failed with exit code {result.returncode}")
    paths = sorted(PAGES.glob("page-*.png"), key=lambda path: int(path.stem.split("-")[-1]))
    if len(paths) != 8:
        raise RuntimeError(f"Frozen local diagnostic expected eight rendered pages; found {len(paths)}")
    records = [_page_record(path) for path in paths]
    if [record["page"] for record in records] != list(range(1, 9)):
        raise RuntimeError("Local diagnostic rendered page sequence is incomplete")
    return records


def verify() -> dict[str, Any]:
    verify_phase1_freeze()
    item, _, _ = _eligible_pair()
    renderer_name = shutil.which("pdftoppm")
    if renderer_name is None:
        raise RuntimeError("Pinned 300-DPI PDF renderer is unavailable")
    expected = _identity(item, Path(renderer_name))
    if not REPORT.is_file():
        raise RuntimeError("Local diagnostic preflight report is missing")
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    if report.get("identity") != expected or len(report.get("pages", [])) != 8:
        raise RuntimeError("Local diagnostic preflight identity or page count changed")
    for record in report["pages"]:
        page = PAGES / f"page-{record['page']}.png"
        if not page.is_file() or _page_record(page) != record:
            raise RuntimeError("Local diagnostic rendered page changed")
    return report


def main() -> None:
    verify_phase1_freeze()
    item, pdf, _ = _eligible_pair()
    renderer_name = shutil.which("pdftoppm")
    if renderer_name is None:
        raise RuntimeError("Pinned 300-DPI PDF renderer is unavailable")
    renderer = Path(renderer_name)
    if REPORT.exists():
        report = verify()
    else:
        identity = _identity(item, renderer)
        pages = _render(pdf, renderer)
        report = {"schema_version": 1, "scope": "already_inspected_private_diagnostic",
                  "ranking_eligible": False, "identity": identity, "pages": pages}
        REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        verify()
    print(json.dumps({"preflight": str(REPORT), "page_count": len(report["pages"]),
                      "report_sha256": sha256_file(REPORT)}, sort_keys=True))


if __name__ == "__main__":
    main()
