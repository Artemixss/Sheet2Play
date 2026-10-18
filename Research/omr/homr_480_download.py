"""Bounded, journaled acquisition of run 480 and upstream main for the upstream-exporter plan.

`plans/2026-10-17-upstream-exporter-480.md`, step 1. Fetches run 480's FP16 encoder and FP32
decoder (480 has no FP16 decoder) and the upstream source at `REVISION`, each checked against
the digest the October 17 audit read from the GitHub API. The 465 runtime is not touched; the
candidate lives under `Research/omr/.runtime/homr-480-upstream`. No retries, as in
`homr_465_download.py`, whose budget and extraction this reuses.

    Bridge\\.venv-homr-gpu\\Scripts\\python.exe -I -B Research/omr/homr_480_download.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from homr_465_download import Budget, extract, save  # noqa: E402

REVISION = "ab369ac54277afab582afa4725441f7cbba76593"
MODEL_ID = "480-5eed84636c96eca5ce6d8e2f62580b74e7ed85e8"
RELEASE = "https://github.com/liebharc/homr/releases/download/onnx_checkpoints/"
# Name, bytes and SHA-256 as the GitHub release API listed them on 2026-10-18.
ASSETS = {
    "encoder": (f"encoder_pytorch_model_{MODEL_ID}_fp16.zip", 24_004_451,
                "e9a9bd8aad40ce5ee8e11bb92164ae3ed6fb27203ec24631531aa373256df7d2"),
    "decoder": (f"decoder_pytorch_model_{MODEL_ID}.zip", 37_398_026,
                "86ffc9ad005466672d2b1ccdf8ed8d1babf504ec03f9db22791bf7e72f0d6a0f"),
}
RUNTIME = HERE / ".runtime/homr-480-upstream"
EVIDENCE = HERE / "reports/upstream-480/acquisition"


def main() -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    RUNTIME.mkdir(parents=True, exist_ok=False)
    downloads = RUNTIME / "download"
    downloads.mkdir()
    budget = Budget(EVIDENCE / "network-budget.json")
    identity = {"candidate": "homr-480-upstream", "source_revision": REVISION, "model_id": MODEL_ID,
                "archives": {}, "models": {}}
    for kind, (name, size, digest) in ASSETS.items():
        archive = downloads / name
        row = budget.fetch(RELEASE + name, archive, size)
        if row["sha256"] != digest:
            raise ValueError(f"Published archive SHA-256 mismatch: {name}")
        files = extract(archive, RUNTIME / kind)
        if len(files) != 1 or files[0]["path"] != name.removesuffix(".zip") + ".onnx":
            raise ValueError("Unexpected model archive layout")
        identity["archives"][kind] = {"name": name, "bytes": size, "sha256": digest}
        identity["models"][kind] = {**files[0], "path": f"{kind}/{files[0]['path']}"}
        save(EVIDENCE / "acquisition.json", identity)
    archive = downloads / (REVISION + ".zip")
    row = budget.fetch(f"https://codeload.github.com/liebharc/homr/zip/{REVISION}", archive, 150_000_000)
    files = extract(archive, RUNTIME / "source", f"homr-{REVISION}/")
    identity["source_archive"] = {"sha256": row["sha256"], "bytes": row["received_bytes"], "url": row["url"]}
    identity["source_files"] = [{"path": f"source/{item['path']}", "sha256": item["sha256"]}
                                for item in files if item["path"].startswith("homr/")]
    save(EVIDENCE / "acquisition.json", identity)
    print(json.dumps({"candidate": identity["candidate"], "homr_files": len(identity["source_files"]),
                      "payload_bytes": budget.data["received_payload_bytes"]}))


if __name__ == "__main__":
    main()
