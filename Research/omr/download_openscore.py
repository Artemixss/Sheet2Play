"""Fetch OpenScore CC0 corpora and convert them into aligned score/label pairs.

OpenScore is the MuseScore community's own transcription project. Its corpora are
released under CC0 and mirrored on GitHub, so they can be fetched from a pinned commit
rather than scraped: no rate limits to dodge, no terms to breach, and the provenance is
recorded in openscore.lock.json alongside the licence.

These are real human transcriptions, not synthesised scores. The repositories store
MuseScore .mscx files; the MuseScore CLI converts each one into the visual form (PDF)
and the exact matching ground truth (MusicXML), which is the pairing Phase 3 needs.

Two-step by design:

    python download_openscore.py --corpus lieder --update-lock      # fetch + record hash
    python download_openscore.py --corpus lieder --convert --limit 50

Conversion is resumable: scores whose outputs already exist are skipped, so a long run
can be interrupted and continued.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

LOCK_NAME = "openscore.lock.json"
DOWNLOAD_BLOCK_BYTES = 1024 * 1024
DEFAULT_MUSESCORE = "C:\\Program Files\\MuseScore 4\\bin\\MuseScore4.exe"


class OpenScoreError(RuntimeError):
    pass


def load_lock(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise OpenScoreError("Cannot read " + str(path) + ": " + str(error)) from error


def save_lock(path, payload):
    Path(path).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def download(url, destination):
    """Stream the archive to disk, returning its sha256."""
    digest = hashlib.sha256()
    request = urllib.request.Request(url, headers={"User-Agent": "Sheet2Play-OMR/1.0"})
    total = 0
    with urllib.request.urlopen(request, timeout=120) as response:
        with destination.open("wb") as handle:
            while True:
                block = response.read(DOWNLOAD_BLOCK_BYTES)
                if not block:
                    break
                handle.write(block)
                digest.update(block)
                total += len(block)
                print("\r  downloaded " + str(total // (1024 * 1024)) + " MB", end="")
    print("")
    return digest.hexdigest()


def safe_extract(archive_path, destination):
    """Extract, refusing links, devices and paths that escape the destination.

    A tar archive can otherwise write anywhere on disk, and this one is fetched over
    the network.
    """
    destination.mkdir(parents=True, exist_ok=True)
    resolved_root = destination.resolve()
    with tarfile.open(archive_path, "r:gz") as archive:
        for member in archive.getmembers():
            if member.issym() or member.islnk() or member.isdev():
                raise OpenScoreError("Refusing archive link/device: " + member.name)
            target = (resolved_root / member.name).resolve()
            if resolved_root not in target.parents and target != resolved_root:
                raise OpenScoreError("Refusing path outside destination: " + member.name)
        archive.extractall(destination)


def find_musescore(explicit):
    for candidate in (explicit, DEFAULT_MUSESCORE, shutil.which("musescore4"),
                      shutil.which("mscore")):
        if candidate and Path(candidate).exists():
            return str(candidate)
    raise OpenScoreError("MuseScore CLI not found. Pass --musescore <path>.")


def convert_scores(musescore, source_root, output_root, limit, want_pdf):
    """Convert .mscx scores into MusicXML labels and page images."""
    scores = sorted(source_root.rglob("*.mscx"))
    if limit:
        scores = scores[:limit]
    if not scores:
        raise OpenScoreError("No .mscx files found under " + str(source_root))

    labels_dir = output_root / "labels"
    pdf_dir = output_root / "pdf"
    labels_dir.mkdir(parents=True, exist_ok=True)
    if want_pdf:
        pdf_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = output_root / "pairs.jsonl"
    converted = skipped = failed = 0

    with manifest_path.open("a", encoding="utf-8") as manifest:
        for index, score in enumerate(scores, start=1):
            stem = score.stem
            label = labels_dir / (stem + ".musicxml")
            pdf = pdf_dir / (stem + ".pdf")

            if label.exists() and (not want_pdf or pdf.exists()):
                skipped += 1
                continue

            print("[" + str(index) + "/" + str(len(scores)) + "] " + stem)
            try:
                if not label.exists():
                    run_convert(musescore, score, label)
                if want_pdf and not pdf.exists():
                    run_convert(musescore, score, pdf)
            except (OpenScoreError, subprocess.TimeoutExpired) as error:
                print("    SKIP  " + str(error)[:110])
                failed += 1
                continue

            # Layout is <composer>/<set>/<song>/<id>.mscx. Composer matters: a fair
            # train/test split has to be composer-disjoint, or the model memorises a
            # writing style instead of learning to read notation.
            parts = score.parts
            record = {
                "score": str(score.relative_to(source_root)).replace("\\", "/"),
                "label": str(label.relative_to(output_root)).replace("\\", "/"),
                "composer": parts[-4] if len(parts) >= 4 else None,
                "set": parts[-3] if len(parts) >= 3 else None,
                "title": parts[-2] if len(parts) >= 2 else None,
                "license": "CC0-1.0",
            }
            if want_pdf:
                record["pdf"] = str(pdf.relative_to(output_root)).replace("\\", "/")
            manifest.write(json.dumps(record, ensure_ascii=False) + chr(10))
            converted += 1

    print("")
    print("=== converted " + str(converted) + ", already present " + str(skipped)
          + ", failed " + str(failed) + " ===")
    print("Pairs manifest: " + str(manifest_path))
    return converted, failed


def run_convert(musescore, source, target):
    result = subprocess.run([musescore, "-o", str(target), str(source)],
                            capture_output=True, text=True, timeout=300)
    if result.returncode != 0 or not target.exists():
        detail = (result.stderr or result.stdout or "").strip()[:120]
        raise OpenScoreError("MuseScore exit " + str(result.returncode) + ": " + detail)


def main():
    parser = argparse.ArgumentParser(
        description="Download OpenScore CC0 corpora and pair scores with MusicXML labels.")
    parser.add_argument("--corpus", default="lieder",
                        help="Corpus key from openscore.lock.json (lieder, quartets).")
    parser.add_argument("--out", default="data/openscore", help="Destination root.")
    parser.add_argument("--lock", default=LOCK_NAME, help="Lock file path.")
    parser.add_argument("--update-lock", action="store_true",
                        help="Record the archive sha256 on first download.")
    parser.add_argument("--convert", action="store_true",
                        help="Convert .mscx scores to MusicXML after download.")
    parser.add_argument("--pdf", action="store_true",
                        help="Also export a PDF per score (slower).")
    parser.add_argument("--limit", type=int, default=0, help="Convert only the first N scores.")
    parser.add_argument("--musescore", help="Path to the MuseScore executable.")
    args = parser.parse_args()

    try:
        lock_path = Path(args.lock)
        lock = load_lock(lock_path)
        corpora = lock.get("corpora", {})
        if args.corpus not in corpora:
            raise OpenScoreError("Unknown corpus " + args.corpus
                                 + ". Available: " + ", ".join(sorted(corpora)))
        entry = corpora[args.corpus]
        archive_lock = entry["archive"]

        out_root = Path(args.out).resolve() / args.corpus
        source_root = out_root / "source"

        print(entry["name"] + "  (" + entry["license"] + ")")
        print("  repository : " + entry["repository"])
        print("  revision   : " + entry["revision"])
        print("")

        if not source_root.exists():
            with tempfile.TemporaryDirectory() as raw:
                archive_path = Path(raw) / "corpus.tar.gz"
                print("Downloading pinned archive...")
                digest = download(archive_lock["url"], archive_path)

                expected = archive_lock.get("sha256")
                if expected:
                    if digest != expected:
                        raise OpenScoreError(
                            "Archive sha256 mismatch.\n  expected " + expected
                            + "\n  actual   " + digest)
                    print("  sha256 verified")
                elif args.update_lock:
                    archive_lock["sha256"] = digest
                    save_lock(lock_path, lock)
                    print("  sha256 recorded in " + str(lock_path) + ": " + digest)
                else:
                    raise OpenScoreError(
                        "No sha256 in the lock file. Re-run with --update-lock to record "
                        "this one: " + digest)

                print("Extracting...")
                safe_extract(archive_path, source_root)
        else:
            print("Source already present at " + str(source_root))

        score_count = len(list(source_root.rglob("*.mscx")))
        print("  scores available: " + str(score_count))

        if args.convert:
            musescore = find_musescore(args.musescore)
            print("  MuseScore: " + musescore)
            print("")
            convert_scores(musescore, source_root, out_root, args.limit, args.pdf)
        else:
            print("")
            print("Run again with --convert to produce MusicXML labels.")
        return 0
    except OpenScoreError as error:
        print("error: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
