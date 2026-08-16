from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from PIL import Image

from sheet2play_omr.events import extract_canonical_events, parse_kern
from sheet2play_omr.kern import validate_kern


KERN = """**kern\t**kern
*clefG2\t*clefF4
*k[]\t*k[]
*M4/4\t*M4/4
=\t=
4c 4e 4g\t2C
4d\t.
4e\t2G
4f\t.
=\t=
2g\t4C
.\t4E
2c\t4G
.\t4C
=\t=
4d 4f 4a\t2D
4e\t.
4f\t2A
4g\t.
=\t=
2a\t4D
.\t4F
2d\t4A
.\t4D
=\t=
4e 4g 4b\t2E
4f\t.
4g\t2B
4a\t.
=\t=
2b\t4E
.\t4G
2e\t4B
.\t4E
=\t=
4f 4a 4cc\t2F
4g\t.
4a\t2c
4b\t.
=\t=
2cc\t4F
.\t4A
2f\t4c
.\t4F
==\t==
*-\t*-
"""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _render_svg(kern: str) -> str:
    try:
        import verovio
    except ImportError as error:
        raise RuntimeError("verovio==6.0.1 is required to regenerate the fixture") from error
    verovio.enableLog(verovio.LOG_ERROR)
    toolkit = verovio.toolkit()
    toolkit.setOptions(
        {
            "adjustPageHeight": False,
            "adjustPageWidth": False,
            "breaks": "auto",
            "footer": "none",
            "font": "Bravura",
            "justifyVertically": False,
            "measureMinWidth": 30,
            "noJustification": False,
            "pageHeight": 2970,
            "pageMarginBottom": 120,
            "pageMarginLeft": 120,
            "pageMarginRight": 120,
            "pageMarginTop": 120,
            "pageWidth": 2100,
            "scale": 90,
            "spacingStaff": 12,
            "spacingSystem": 12,
        }
    )
    if not toolkit.loadData(kern):
        raise RuntimeError("Verovio rejected the canonical Kern fixture")
    if toolkit.getPageCount() != 1:
        raise RuntimeError(f"Fixture must render to one page, got {toolkit.getPageCount()}")
    svg = toolkit.renderToSVG(1)
    if "class=\"staff\"" not in svg or svg.count("class=\"staff\"") < 2:
        raise RuntimeError("Rendered fixture does not contain two visible staves")
    return svg


def _normalize_pdf_metadata(path: Path) -> None:
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError as error:
        raise RuntimeError("pypdf==6.10.0 is required to regenerate the fixture") from error
    reader = PdfReader(path)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.add_metadata(
        {
            "/CreationDate": "D:19700101000000Z",
            "/ModDate": "D:19700101000000Z",
            "/Producer": "Sheet2Play deterministic fixture generator",
        }
    )
    temporary_path = path.with_suffix(".normalized.pdf")
    with temporary_path.open("wb") as stream:
        writer.write(stream)
    temporary_path.replace(path)


def generate(output_dir: Path) -> dict[str, object]:
    try:
        import cairosvg
    except ImportError as error:
        raise RuntimeError("CairoSVG==2.8.2 is required to regenerate the fixture") from error

    os.environ.setdefault("SOURCE_DATE_EPOCH", "0")
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "kern": output_dir / "baseline-piano.krn",
        "events": output_dir / "baseline-piano.events.json",
        "png": output_dir / "baseline-piano.png",
        "pdf": output_dir / "baseline-piano.pdf",
        "benchmark": output_dir / "benchmark.jsonl",
    }

    validate_kern(KERN)
    canonical = extract_canonical_events(parse_kern(KERN))
    svg = _render_svg(KERN)
    paths["kern"].write_text(KERN, encoding="utf-8")
    paths["events"].write_text(
        json.dumps(canonical.to_json(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    cairosvg.svg2png(
        bytestring=svg.encode("utf-8"),
        write_to=str(paths["png"]),
        output_width=1050,
        output_height=1485,
        background_color="#ffffff",
    )
    cairosvg.svg2pdf(
        bytestring=svg.encode("utf-8"),
        write_to=str(paths["pdf"]),
        output_width=595,
        output_height=842,
    )
    _normalize_pdf_metadata(paths["pdf"])
    with Image.open(paths["png"]) as image:
        darkest, _ = image.convert("L").getextrema()
        if image.size != (1050, 1485) or darkest > 64:
            raise RuntimeError(f"Unexpected fixture raster: size={image.size}, darkest={darkest}")

    paths["benchmark"].write_text(
        json.dumps(
            {
                "id": "baseline-piano-001",
                "kind": "page",
                "image": paths["png"].name,
                "ground_truth_events": paths["events"].name,
                "structural_fixture": True,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": 1,
        "generator": {"verovio": "6.0.1", "cairosvg": "2.8.2", "pypdf": "6.10.0"},
        "note_events": sum(event.kind == "note" for event in canonical.events),
        "files": {
            name: {"name": path.name, "bytes": path.stat().st_size, "sha256": _sha256(path)}
            for name, path in paths.items()
        },
    }
    manifest_path = output_dir / "fixture-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {**manifest, "manifest": str(manifest_path.resolve())}


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the deterministic Transcoda baseline fixture")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(generate(args.output_dir.resolve()), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
