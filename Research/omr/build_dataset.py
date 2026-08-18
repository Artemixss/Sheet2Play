"""Build aligned (page image, MusicXML) training pairs by engraving scores locally.

Phase 3 needs many pages of sheet music paired with exact ground truth. Rendering
locally with the MuseScore CLI provides that directly:

  * the ground truth *is* the input score, so alignment is exact - there is no OMR
    error to inherit, which a corpus of downloaded PDFs can never guarantee;
  * the engraving comes from the same program musescore.com renders with, so the
    visual domain matches the scores this project targets;
  * volume is limited only by how much MusicXML/MIDI you hold, and nothing depends
    on a third-party site staying reachable or permitting bulk access.

MIDI inputs are engraved too. That is the cheapest way to get dense piano pages in
the target domain: MuseScore lays the MIDI out as a score and exports the matching
MusicXML, so an existing MIDI collection becomes training data.

Known limitations (measured, not assumed):

  * MIDI input can engrave badly. animenz1.mid produced a three-staff layout with an
    empty bass staff, because MuseScore maps MIDI tracks to separate instruments.
    Real piano scores are a two-staff grand staff, so those pages teach wrong layout
    priors. Prefer MusicXML sources; check MIDI-derived pages before training on them.

  * Rendered pages carry no title block, captions, fingerings, chord symbols or
    note-name annotations. Real target PDFs do - the project's own Liyue Battle Theme
    export has a full title/composer/arranger block. This generator models imaging
    degradation only, not the notation layer, so it under-represents that.

  * The project's real inputs are born-digital MuseScore PDF exports, which are clean
    vector renders. For those the variant 0 (clean) images are the closest match, and
    heavy degradation is less representative. Degradation matters for the photo and
    scan inputs the app also accepts.

  * Synthetic data is for training volume. Evaluate on real scores instead - the
    library in songs/pdf holds the actual target distribution.

Usage:
    python build_dataset.py --input ../../Omr/Data_Pipeline/input_xml --out dataset
    python build_dataset.py --input <midi_dir> --variants 3 --dpi 300 --limit 50
"""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

SCORE_SUFFIXES = {".mxl", ".musicxml", ".xml", ".mid", ".midi"}
DEFAULT_MUSESCORE = "C:\\Program Files\\MuseScore 4\\bin\\MuseScore4.exe"


class DatasetBuildError(RuntimeError):
    pass


def find_musescore(explicit):
    candidates = [
        explicit,
        os.environ.get("MUSESCORE_PATH"),
        DEFAULT_MUSESCORE,
        shutil.which("musescore4"),
        shutil.which("mscore"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate)
    raise DatasetBuildError(
        "MuseScore CLI not found. Pass --musescore <path> or set MUSESCORE_PATH.")


def run_musescore(musescore, source, target, dpi):
    command = [musescore, "-o", str(target), str(source)]
    if dpi is not None:
        command += ["-r", str(dpi)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()[:200]
        raise DatasetBuildError(
            "MuseScore failed on " + source.name
            + " (exit " + str(result.returncode) + "): " + detail)


def collect_pages(work, stem):
    """MuseScore writes one page as <stem>.png, several as <stem>-1.png, <stem>-2.png."""
    single = work / (stem + ".png")
    if single.exists():
        return [single]

    def page_index(path):
        tail = path.stem.rsplit("-", 1)[-1]
        return int(tail) if tail.isdigit() else 0

    return sorted(work.glob(stem + "-*.png"), key=page_index)


def degrade(image, rng):
    """Apply scan-like degradation so synthetic pages resemble real scanned input.

    Without this the model only ever sees pristine renders and generalises poorly to
    photographed or scanned sheet music, which is what users actually load.
    """
    params = {}

    angle = rng.uniform(-0.7, 0.7)
    params["skew_deg"] = round(angle, 3)
    image = image.rotate(angle, resample=Image.BICUBIC, expand=False, fillcolor=255)

    blur = rng.uniform(0.0, 0.8)
    params["blur_radius"] = round(blur, 3)
    if blur > 0.05:
        image = image.filter(ImageFilter.GaussianBlur(blur))

    brightness = rng.uniform(0.88, 1.08)
    contrast = rng.uniform(0.85, 1.15)
    params["brightness"] = round(brightness, 3)
    params["contrast"] = round(contrast, 3)
    image = ImageEnhance.Brightness(image).enhance(brightness)
    image = ImageEnhance.Contrast(image).enhance(contrast)

    sigma = rng.uniform(1.0, 6.0)
    params["noise_sigma"] = round(sigma, 3)
    pixels = np.asarray(image, dtype=np.float32)
    generator = np.random.default_rng(rng.randrange(2 ** 31))
    pixels = pixels + generator.normal(0.0, sigma, pixels.shape)
    image = Image.fromarray(np.clip(pixels, 0, 255).astype(np.uint8))

    return image, params


def save_with_jpeg_artifacts(image, path, rng):
    """Round-trip through JPEG; most real-world scans arrive lossily compressed."""
    quality = rng.randint(62, 92)
    image.convert("L").save(path, format="JPEG", quality=quality)
    return quality


def discover_sources(inputs, limit):
    sources = []
    for raw in inputs:
        base = Path(raw).resolve()
        if base.is_file() and base.suffix.lower() in SCORE_SUFFIXES:
            sources.append(base)
        elif base.is_dir():
            for path in sorted(base.rglob("*")):
                if path.suffix.lower() in SCORE_SUFFIXES:
                    sources.append(path)
    if limit:
        sources = sources[:limit]
    return sources


def build(args):
    musescore = find_musescore(args.musescore)
    out_root = Path(args.out).resolve()
    images_dir = out_root / "images"
    labels_dir = out_root / "labels"
    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_root / "manifest.jsonl"

    sources = discover_sources(args.input, args.limit)
    if not sources:
        raise DatasetBuildError("No score files found under: " + ", ".join(args.input))

    print("MuseScore  : " + musescore)
    print("Sources    : " + str(len(sources)) + " score file(s)")
    print("Output     : " + str(out_root))
    print("")

    rng = random.Random(args.seed)
    written = 0
    failed = 0

    with manifest_path.open("a", encoding="utf-8") as manifest:
        for index, source in enumerate(sources, start=1):
            stem = source.stem[:60].replace(" ", "_") + "_" + format(index, "05d")
            label_path = labels_dir / (stem + ".musicxml")
            print("[" + str(index) + "/" + str(len(sources)) + "] " + source.name)

            with tempfile.TemporaryDirectory() as raw_work:
                work = Path(raw_work)
                try:
                    # Ground truth first: a score that will not export cleanly makes
                    # useless training data, so fail before spending time rendering.
                    run_musescore(musescore, source, work / "score.musicxml", None)
                    run_musescore(musescore, source, work / "page.png", args.dpi)
                except (DatasetBuildError, subprocess.TimeoutExpired) as error:
                    print("    SKIP  " + str(error))
                    failed += 1
                    continue

                pages = collect_pages(work, "page")
                if not pages or not (work / "score.musicxml").exists():
                    print("    SKIP  MuseScore produced no pages or no MusicXML")
                    failed += 1
                    continue

                shutil.copyfile(work / "score.musicxml", label_path)

                for page_number, page in enumerate(pages, start=1):
                    original = Image.open(page).convert("L")
                    for variant in range(args.variants + 1):
                        name = (stem + "_p" + format(page_number, "03d")
                                + "_v" + str(variant) + ".jpg")
                        target = images_dir / name
                        if variant == 0:
                            params = {"clean": True}
                            quality = save_with_jpeg_artifacts(original, target, rng)
                        else:
                            degraded, params = degrade(original, rng)
                            quality = save_with_jpeg_artifacts(degraded, target, rng)
                        record = {
                            "image": str(target.relative_to(out_root)).replace("\\", "/"),
                            "label": str(label_path.relative_to(out_root)).replace("\\", "/"),
                            "source": source.name,
                            "page": page_number,
                            "variant": variant,
                            "jpeg_quality": quality,
                            "augmentation": params,
                        }
                        manifest.write(json.dumps(record, ensure_ascii=False) + "\n")
                        written += 1

                produced = len(pages) * (args.variants + 1)
                print("    ok    " + str(len(pages)) + " page(s) -> "
                      + str(produced) + " image(s)")

    print("")
    print("=== " + str(written) + " images from " + str(len(sources) - failed)
          + " scores (" + str(failed) + " skipped) ===")
    print("Manifest: " + str(manifest_path))
    return 0 if written else 1


def main():
    parser = argparse.ArgumentParser(
        description="Engrave scores locally into aligned image/MusicXML training pairs.")
    parser.add_argument("--input", nargs="+", required=True,
                        help="Directories or files holding MusicXML/MXL/MIDI scores.")
    parser.add_argument("--out", default="dataset", help="Output dataset root.")
    parser.add_argument("--dpi", type=int, default=300,
                        help="Render resolution in DPI (default 300).")
    parser.add_argument("--variants", type=int, default=2,
                        help="Degraded copies per page, additional to the clean one.")
    parser.add_argument("--limit", type=int, default=0,
                        help="Only process the first N scores.")
    parser.add_argument("--seed", type=int, default=1234, help="Augmentation seed.")
    parser.add_argument("--musescore", help="Path to the MuseScore executable.")
    args = parser.parse_args()
    try:
        return build(args)
    except DatasetBuildError as error:
        print("error: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
