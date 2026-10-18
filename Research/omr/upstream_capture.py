#!/usr/bin/env python3
"""Run upstream HOMR candidates over the engraved displacement sets through the app's own pipeline.

`plans/2026-10-17-upstream-exporter-480.md`, step 3. Each candidate is HOMR main `ab369ac` with
465's or run 480's weights. The page pipeline is `bridge.run_homr_engine` from `dist/Bridge`,
exactly as `displacement_capture.py` runs it, with one swap: each page is recognised by
`homr_upstream_native.py` instead of the pinned 465 runtime, under the same per-page guard.
Rendering, normalisation and stitching are the shipped code, so a candidate differs from the
shipped `homr465` captures only in source and weights. Each rendered page must hash to the
image the shipped capture recognised.

Captures go beside the shipped ones, `data/displacement-ruler/captures/<candidate>/<id>/`, so
`displacement_correct` and `timing_residual` read them unchanged. Like the shipped capture, a
directory without `result.json` is an interrupted attempt and stops the run.

    Bridge\\.venv-homr-gpu\\Scripts\\python.exe -I -B Research/omr/upstream_capture.py --splits dev dev-b
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[1]
BRIDGE = WORKSPACE / "dist" / "Bridge"
RULER = HERE / "data/displacement-ruler"
MANIFESTS = (HERE / "reports/displacement/phase1/manifest.json", HERE / "reports/displacement/phase3b/manifest.json")
CANDIDATES = HERE / "reports/upstream-480/candidates.json"
ACQUISITION = HERE / "reports/upstream-480/acquisition/acquisition.json"
NAMES = ("homr465-ab369ac", "homr480-ab369ac")
STOPPING_CODES = {"RESOURCE_STOP", "CUDA_UNAVAILABLE", "MODEL_INVALID", "RUNTIME_MISSING"}
SESSION_SECONDS = 13_500

sys.path.insert(0, str(BRIDGE))
os.environ["SHEET2PLAY_HOME"] = str(RULER / "home-upstream")

import bridge  # noqa: E402
from musicxml_normalizer import add_seconds  # noqa: E402

PAGE_SECONDS: list[float] = []


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=1) + "\n", encoding="utf-8")


def candidates() -> dict[str, object]:
    """Both candidates from the acquisition record and the 465 profile; written once, then checked."""
    acquired = json.loads(ACQUISITION.read_text())
    profile = json.loads((WORKSPACE / "Bridge/homr465-profile.json").read_text())
    runtime_465 = "Bridge/" + profile["runtime_directory"]
    runtime_480 = "Research/omr/.runtime/homr-480-upstream"
    shipped = {kind: {"path": f"{runtime_465}/{row['path']}", "sha256": row["sha256"]}
               for kind, row in profile["models"].items()}
    source = {"source": f"{runtime_480}/source", "source_revision": acquired["source_revision"],
              "source_files": [{"path": row["path"].removeprefix("source/"), "sha256": row["sha256"]}
                               for row in acquired["source_files"]]}
    value = {"note": "Upstream main with 465 or run 480 weights; 480 pairs its FP16 encoder with its "
                     "FP32 decoder, the only GPU pairing upstream publishes.",
             "candidates": {
                 "homr465-ab369ac": source | {"model_revision": profile["model_revision"], "models": shipped},
                 "homr480-ab369ac": source | {"model_revision": acquired["model_id"] + "-fp16-encoder-fp32-decoder",
                                              "models": {kind: {"path": f"{runtime_480}/{row['path']}",
                                                                "sha256": row["sha256"]}
                                                         for kind, row in acquired["models"].items()}
                                             | {"segnet": shipped["segnet"]}}}}
    if CANDIDATES.exists():
        if json.loads(CANDIDATES.read_text()) != value:
            raise SystemExit("candidates.json differs from the acquisition record")
    else:
        write_json(CANDIDATES, value)
    return value


def page_runner(name: str):
    from guarded_execution import run_guarded
    from execution_safety.safety_policy import SafetyLimits

    def run_page(input_path: Path) -> Path:
        started = time.perf_counter()
        job_root = Path(os.environ["SHEET2PLAY_HOME"]) / "omr-jobs"
        job_root.mkdir(parents=True, exist_ok=True)
        output = job_root / str(uuid.uuid4())
        receipt = output / "native.json"
        command = [str(bridge.resolve_homr_python()), "-B", str(HERE / "homr_upstream_native.py"), name,
                   str(input_path), str(receipt)]
        try:
            result = run_guarded(command, input_path.parent, output, SafetyLimits(max_seconds=1800),
                                 lock_path=job_root / ".worker.lock")
            if result["status"] != "complete":
                details = json.loads(receipt.read_text(encoding="utf-8")) if receipt.is_file() else {}
                error = str(details.get("error") or result["stop_reason"] or "Candidate HOMR failed")
                code = "RESOURCE_STOP" if result["status"] == "blocked" or result["worker_exit_code"] == 90 \
                    else "NORMALIZATION_FAILED"
                if "CandidateError" in error or "ProfileError" in error:
                    code = "MODEL_INVALID"
                elif "CUDA" in error:
                    code = "CUDA_UNAVAILABLE"
                raise bridge.BridgeError(code, name, f"{error}; receipt: {output}")
            details = json.loads(receipt.read_text(encoding="utf-8"))
            if details.get("candidate") != name:
                raise bridge.BridgeError("MODEL_INVALID", name, "Candidate receipt identity mismatch")
            return input_path.with_suffix(".musicxml")
        finally:
            PAGE_SECONDS.append(round(time.perf_counter() - started, 3))

    return run_page


def capture(item: dict[str, object], name: str) -> dict[str, object]:
    destination = RULER / "captures" / name / str(item["id"])
    pages_directory = destination / "pages"
    pages_directory.mkdir(parents=True)
    shipped = json.loads((RULER / "captures/homr465" / str(item["id"]) / "result.json").read_text())

    @contextmanager
    def kept_pages(input_path: Path):
        pages = bridge.render_pdf_pages(input_path, pages_directory)
        rendered = {path.name: sha256(path) for path in pages}
        # The shipped record also hashes HOMR's debug images, which share the page prefix.
        recognised = {name: digest for name, digest in shipped.get("page_images", {}).items() if name in rendered
                      or "_" not in name}
        if recognised and rendered != recognised:
            raise bridge.BridgeError("INPUT_INVALID", "pdf_render", "Rendered pages differ from the shipped capture")
        yield pages

    PAGE_SECONDS.clear()
    bridge.prepare_homr_inputs = kept_pages
    bridge.run_homr465_page = page_runner(name)
    pdf = HERE / str(item["pdf"])
    if sha256(pdf) != item["pdf_sha256"]:
        raise SystemExit(f"{item['id']}: PDF changed after the freeze")
    started = time.perf_counter()
    result: dict[str, object] = {"id": item["id"], "engine": name}
    try:
        output = bridge.run_homr_engine(pdf, "homr465")
        notes = add_seconds(output.score)
        payload = {"engine": name, "tempo_changes": [asdict(tempo) for tempo in output.score.tempo_changes],
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
    parser.add_argument("--splits", nargs="+", default=["dev", "dev-b"], help="dev, test, dev-b, test-b")
    parser.add_argument("--ids", nargs="*", help="Restrict to these manifest ids.")
    parser.add_argument("--candidates", nargs="+", default=list(NAMES), choices=NAMES)
    args = parser.parse_args()
    candidates()
    items = [item for manifest in MANIFESTS for item in json.loads(manifest.read_text())["items"]
             if item["split"] in args.splits and (not args.ids or item["id"] in args.ids)]
    session = time.monotonic()
    for index, item in enumerate(items):
        for name in args.candidates if index % 2 == 0 else list(reversed(args.candidates)):
            destination = RULER / "captures" / name / str(item["id"])
            if (destination / "result.json").exists():
                continue
            if destination.exists():
                raise SystemExit(f"{destination} holds an interrupted attempt; inspect it before resuming")
            if time.monotonic() - session > SESSION_SECONDS:
                print(json.dumps({"stopped": "session limit", "next": item["id"]}), flush=True)
                return 3
            result = capture(item, name)
            print(json.dumps({key: result.get(key) for key in (
                "id", "engine", "status", "code", "notes", "pages", "elapsed_seconds")}), flush=True)
            if result.get("code") in STOPPING_CODES:
                return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
