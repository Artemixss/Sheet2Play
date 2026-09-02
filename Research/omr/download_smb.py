"""Fetch the Sheet Music Benchmark, pinned to an exact revision.

SMB (arXiv:2506.10488, CC BY 4.0) is 685 pages with `**kern` ground truth, 469 of them
pianoform - the texture this project actually receives, and better matched to it than OLiMPiC,
which is voice-and-piano lieder. It ships the OMR-NED metric, so scoring against it makes
results comparable to published numbers rather than only to this project's own history.

The dataset is **gated**: you must accept its terms on HuggingFace and be authenticated
before any file can be fetched. See the message printed on failure for how.

Pinning works differently to `download_openscore.py`. There is no single archive to hash, so
the revision commit SHA is recorded in the lock file and every later run resolves to that
exact revision - the same guarantee, expressed the way the Hub expresses it.

    .venv/Scripts/python.exe download_smb.py --update-lock
    .venv/Scripts/python.exe download_smb.py --texture pianoform
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ID = "PRAIG/SMB"
LOCK_NAME = "smb.lock.json"

GATED_HELP = """
The Sheet Music Benchmark is a gated dataset. To get access:

  1. Sign in at https://huggingface.co and open
     https://huggingface.co/datasets/PRAIG/SMB
  2. Accept the terms (it asks for contact information).
  3. Create a token at https://huggingface.co/settings/tokens
  4. Authenticate, either with
         huggingface-cli login
     or by setting the environment variable
         HF_TOKEN=<your token>

This is a one-time manual step; it cannot be automated.
"""


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--out", type=Path, default=HERE / "data" / "smb",
                        help="Destination root.")
    parser.add_argument("--lock", type=Path, default=HERE / LOCK_NAME,
                        help="Lock file path.")
    parser.add_argument("--update-lock", action="store_true",
                        help="Record the resolved revision on first download.")
    parser.add_argument("--texture", default="pianoform",
                        help="Texture to keep: pianoform, monophony, quartet, other, or all.")
    parser.add_argument("--manifest", type=Path, default=None,
                        help="Where to write the filtered manifest "
                             "(default: <out>/smb-<texture>.jsonl).")
    return parser.parse_args(argv)


def load_lock(path: Path) -> dict:
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {
        "schema_version": 1,
        "note": (
            "Sheet Music Benchmark (arXiv:2506.10488), CC BY 4.0, gated on HuggingFace. "
            "There is no single archive to hash, so the dataset is pinned by revision SHA: "
            "recorded on first download with --update-lock and required on every run "
            "thereafter."
        ),
        "repo_id": REPO_ID,
        "license": "CC BY 4.0",
        "revision": None,
    }


def save_lock(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def resolve_revision(update_lock: bool, lock: dict) -> str:
    """Return the revision to download, honouring the lock unless recording a new one."""
    from huggingface_hub import HfApi

    pinned = lock.get("revision")
    if pinned and not update_lock:
        return pinned

    info = HfApi().dataset_info(REPO_ID)
    resolved = info.sha
    if pinned and pinned != resolved and not update_lock:
        raise SystemExit(
            f"Revision mismatch.\n  locked   {pinned}\n  upstream {resolved}\n"
            "Re-run with --update-lock only if you intend to move to the new revision."
        )
    return resolved


def download(out: Path, revision: str) -> Path:
    from huggingface_hub import snapshot_download
    from huggingface_hub.errors import GatedRepoError

    # The research venv forces offline mode for inference; downloading needs it off.
    for variable in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        os.environ.pop(variable, None)

    try:
        path = snapshot_download(
            REPO_ID, repo_type="dataset", revision=revision, local_dir=str(out)
        )
    except GatedRepoError:
        print(GATED_HELP, file=sys.stderr)
        raise SystemExit("Cannot download SMB: access has not been granted to this account.")
    return Path(path)


def _texture_of(row: dict) -> str | None:
    """SMB's texture field, tolerating naming differences across revisions."""
    for key in ("texture", "category", "type", "subset", "split_category"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    return None


def build_manifest(root: Path, texture: str, manifest_path: Path) -> int:
    """Filter metadata.jsonl to one texture and write a manifest this harness can consume."""
    metadata = root / "metadata.jsonl"
    if not metadata.is_file():
        raise SystemExit(f"Expected {metadata} in the downloaded snapshot; it is missing.")

    rows = [
        json.loads(line)
        for line in metadata.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not rows:
        raise SystemExit(f"{metadata} is empty.")

    observed = {_texture_of(row) for row in rows} - {None}
    if texture != "all":
        if texture not in observed:
            raise SystemExit(
                f"Texture {texture!r} not present. Observed textures: "
                + (", ".join(sorted(observed)) if observed else "none - no texture field found")
            )
        rows = [row for row in rows if _texture_of(row) == texture]

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
    return len(rows)


def main(argv: list[str] | None = None) -> int:
    args = parse_arguments(argv)
    lock = load_lock(args.lock)

    revision = resolve_revision(args.update_lock, lock)
    print(f"repo     : {REPO_ID}")
    print(f"revision : {revision}")

    root = download(args.out, revision)
    print(f"snapshot : {root}")

    if args.update_lock and lock.get("revision") != revision:
        lock["revision"] = revision
        save_lock(args.lock, lock)
        print(f"revision recorded in {args.lock}")
    elif not lock.get("revision"):
        raise SystemExit(
            f"No revision in {args.lock}. Re-run with --update-lock to record "
            f"{revision} before relying on this dataset."
        )

    manifest = args.manifest or (args.out / f"smb-{args.texture}.jsonl")
    count = build_manifest(root, args.texture.lower(), manifest)
    print(f"texture  : {args.texture} ({count} pages)")
    print(f"manifest : {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
