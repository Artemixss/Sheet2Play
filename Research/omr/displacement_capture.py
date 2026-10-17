#!/usr/bin/env python3
"""Run the shipped 465 and 426 engines over the frozen displacement ruler, keeping raw pages.

Phase 1 of the displacement plan needs a baseline from exactly what the app runs, and Phases
2-3 need the engines' own per-page MusicXML so corrections can be replayed without inference.
The app pipeline is `bridge.run_homr_engine`: render the PDF, recognise each page, normalise
each page, combine. This calls that function from `dist/Bridge`, the published copy, and only
swaps the temporary page directory for a kept one. Everything else is the shipped code path.

Run with the app's own interpreter, isolated so no research module can shadow a Bridge one:

    Bridge\\.venv-homr-gpu\\Scripts\\python.exe -I -B Research/omr/displacement_capture.py

Each (engine, score) writes `result.json` last. A directory without one is an interrupted
attempt: the run stops rather than retry it, so it can be inspected first.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[1]
BRIDGE = WORKSPACE / "dist" / "Bridge"
MANIFEST = HERE / "reports/displacement/phase1/manifest.json"
OUT = HERE / "data/displacement-ruler"
IDENTITY = HERE / "reports/displacement/phase1/capture-identity.json"
ENGINES = ("homr465", "homr")
# Failures that say the machine or runtime is wrong, not the music. They stop the run.
STOPPING_CODES = {"RESOURCE_STOP", "CUDA_UNAVAILABLE", "MODEL_INVALID", "RUNTIME_MISSING"}
SESSION_SECONDS = 13_500

sys.path.insert(0, str(BRIDGE))
os.environ["SHEET2PLAY_HOME"] = str(OUT / "home")

import bridge  # noqa: E402
from musicxml_normalizer import add_seconds  # noqa: E402


PAGE_SECONDS: list[float] = []


def _timed(original):
    def run_page(path: Path) -> Path:
        started = time.perf_counter()
        try:
            return original(path)
        finally:
            PAGE_SECONDS.append(round(time.perf_counter() - started, 3))
    return run_page


bridge.run_homr465_page = _timed(bridge.run_homr465_page)
bridge.run_homr = _timed(bridge.run_homr)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=1) + "\n", encoding="utf-8")


def run_identity(manifest: Path) -> dict[str, object]:
    files = ["bridge.py", "musicxml_normalizer.py", "homr465_native.py", "homr465_profile.py",
             "homr465-profile.json", "homr_gpu.py", "render_pdf.py", "guarded_execution.py"]
    return {"bridge": {name: sha256(BRIDGE / name) for name in files},
            "executable_sha256": sha256(WORKSPACE / "dist" / "Sheet2Play.exe"),
            "python": sys.executable, "manifest_sha256": sha256(manifest)}


def check_identity(manifest: Path) -> None:
    """Each manifest records its run identity beside it; every later set must run Phase 1's bridge.

    The capture never runs the executable, so a later set records its hash without requiring
    Phase 1's: a frontend-only republish leaves recognition unchanged.
    """
    identity = run_identity(manifest)
    record = manifest.parent / IDENTITY.name
    if record.exists():
        recorded = json.loads(record.read_text())
        recorded.pop("phase1_executable_sha256", None)
        if recorded != identity:
            raise SystemExit("Shipped bridge, executable or manifest changed since the first capture")
        return
    first = json.loads(IDENTITY.read_text())
    if any(first[key] != identity[key] for key in ("bridge", "python")):
        raise SystemExit("Shipped bridge or interpreter differs from the Phase 1 capture")
    identity["phase1_executable_sha256"] = first["executable_sha256"]
    write_json(record, identity)


def capture(item: dict[str, object], engine: str) -> dict[str, object]:
    destination = OUT / "captures" / engine / str(item["id"])
    pages_directory = destination / "pages"
    pages_directory.mkdir(parents=True)

    @contextmanager
    def kept_pages(input_path: Path):
        yield bridge.render_pdf_pages(input_path, pages_directory)

    PAGE_SECONDS.clear()
    bridge.prepare_homr_inputs = kept_pages

    pdf = OUT.parent.parent / str(item["pdf"])
    if sha256(pdf) != item["pdf_sha256"]:
        raise SystemExit(f"{item['id']}: PDF changed after the freeze")
    started = time.perf_counter()
    result: dict[str, object] = {"id": item["id"], "engine": engine}
    try:
        output = bridge.run_homr_engine(pdf, engine)
        notes = add_seconds(output.score)
        payload = {"engine": engine, "tempo_changes": [asdict(tempo) for tempo in output.score.tempo_changes],
                   "notes": [asdict(note) for note in notes]}
        write_json(destination / "payload.json", payload)
        result.update(status="ok", notes=len(notes), pages=output.page_count)
    except bridge.BridgeError as error:
        result.update(status="failed", code=error.code, stage=error.stage, error=str(error)[:500])
    except bridge.MusicXmlNormalizationError as error:
        result.update(status="failed", code="NORMALIZATION_FAILED", stage=error.stage, error=str(error)[:500])
    result["elapsed_seconds"] = round(time.perf_counter() - started, 3)
    result["page_seconds"] = list(PAGE_SECONDS)
    images = sorted(pages_directory.glob("page-*.png"))
    result["page_images"] = {path.name: sha256(path) for path in images}
    result["page_musicxml"] = {path.name: sha256(path) for path in sorted(pages_directory.glob("*.musicxml"))}
    for path in images:
        path.unlink()
    write_json(destination / "result.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--split", default="all", help="dev, test, dev-b, test-b, or all")
    parser.add_argument("--ids", nargs="*", help="Restrict to these manifest ids.")
    parser.add_argument("--manifest", type=Path, default=MANIFEST,
                        help="A frozen manifest; the Phase 3 replan sets use phase3b/manifest.json.")
    args = parser.parse_args()
    check_identity(args.manifest.resolve())
    items = [item for item in json.loads(args.manifest.read_text())["items"]
             if args.split in ("all", item["split"]) and (not args.ids or item["id"] in args.ids)]
    session = time.monotonic()
    for index, item in enumerate(items):
        for engine in ENGINES if index % 2 == 0 else tuple(reversed(ENGINES)):
            destination = OUT / "captures" / engine / str(item["id"])
            if (destination / "result.json").exists():
                continue
            if destination.exists():
                raise SystemExit(f"{destination} holds an interrupted attempt; inspect it before resuming")
            if time.monotonic() - session > SESSION_SECONDS:
                print(json.dumps({"stopped": "session limit", "next": item["id"]}), flush=True)
                return 3
            result = capture(item, engine)
            print(json.dumps({key: result.get(key) for key in (
                "id", "engine", "status", "code", "notes", "pages", "elapsed_seconds")}), flush=True)
            if result.get("code") in STOPPING_CODES:
                return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
