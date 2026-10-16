"""Bounded, journaled acquisition of the pinned research candidate; no retries."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.request
import zipfile

REVISION = "33baa326900faa12702df8c4bdcbea034a3d6a34"
MODEL_ID = "465-597144cab54c8f6d0f6c9619df5c5312694eadd6"
CAP = 3_000_000_000
CONTROL_RESERVE = 100_000_000


def save(path: Path, value: dict) -> None:
    # A torn receipt fails JSON parsing on resumption, before another request.
    # Flush the reservation before connecting; Windows sandbox forbids rename/link publication.
    with path.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


class Budget:
    def __init__(self, path: Path) -> None:
        self.path = path
        if path.exists():
            self.data = json.loads(path.read_text(encoding="utf-8"))
            if self.data["cap_bytes"] != CAP:
                raise ValueError("Network cap drift")
        else:
            self.data = {"cap_bytes": CAP, "control_reserve_bytes": CONTROL_RESERVE,
                         "reserved_bytes": CONTROL_RESERVE, "received_payload_bytes": 0,
                         "requests": [], "policy": "Reserve twice each response ceiling plus 1 MB per request for protocol overhead; no automatic retry. Control reserve includes browsing/coordination overhead; unrelated host traffic is not measurable here."}
            save(path, self.data)

    def fetch(self, url: str, destination: Path, ceiling: int) -> dict:
        if ceiling <= 0 or destination.exists():
            raise ValueError("Expected positive ceiling and a fresh destination")
        reservation = ceiling * 2 + 1_000_000
        if self.data["reserved_bytes"] + reservation > CAP:
            raise RuntimeError("Hard 3 GB network budget would be exceeded")
        row = {"url": url, "ceiling_bytes": ceiling, "reserved_bytes": reservation,
               "received_bytes": 0, "status": "started", "started_unix": time.time()}
        self.data["requests"].append(row)
        self.data["reserved_bytes"] += reservation
        save(self.path, self.data)
        digest = hashlib.sha256()
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Sheet2Play-bounded-research", "Accept-Encoding": "identity"})
            with urllib.request.urlopen(request, timeout=60) as response:
                length = response.headers.get("Content-Length")
                if length is not None and int(length) > ceiling:
                    raise RuntimeError("Response length exceeds reserved network ceiling")
                with destination.open("xb") as stream:
                    while True:
                        block = response.read(min(64 * 1024, ceiling - row["received_bytes"] + 1))
                        if not block:
                            break
                        row["received_bytes"] += len(block)
                        self.data["received_payload_bytes"] += len(block)
                        if row["received_bytes"] > ceiling:
                            raise RuntimeError("Response exceeded reserved ceiling; acquisition stopped")
                        digest.update(block)
                        stream.write(block)
                if length is not None and row["received_bytes"] != int(length):
                    raise RuntimeError("Incomplete HTTP response")
            row.update(status="complete", sha256=digest.hexdigest())
        except Exception as error:
            row.update(status="failed", error=f"{type(error).__name__}: {error}")
            raise
        finally:
            row["ended_unix"] = time.time()
            save(self.path, self.data)
        return row


def extract(archive: Path, destination: Path, prefix: str | None = None) -> list[dict]:
    destination.mkdir(parents=True, exist_ok=False)
    rows = []
    with zipfile.ZipFile(archive) as bundle:
        if sum(item.file_size for item in bundle.infolist()) > 700_000_000:
            raise ValueError("Unbounded extracted archive")
        for item in bundle.infolist():
            name = item.filename
            if prefix:
                if not name.startswith(prefix):
                    raise ValueError("Source archive revision prefix mismatch")
                name = name[len(prefix):]
            if not name or item.is_dir():
                continue
            path = (destination / name).resolve()
            if not path.is_relative_to(destination.resolve()) or (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("Unsafe archive entry")
            path.parent.mkdir(parents=True, exist_ok=True)
            data = bundle.read(item)
            path.write_bytes(data)
            rows.append({"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--resume-reviewed", action="store_true")
    args = parser.parse_args()
    args.evidence.mkdir(parents=True, exist_ok=True)
    args.runtime.mkdir(parents=True, exist_ok=True)
    budget = Budget(args.evidence / "network-budget.json")
    metadata = args.evidence / "release-onnx.json"
    if metadata.exists():
        completed = [row for row in budget.data["requests"] if row["status"] == "complete" and row["url"].endswith("/onnx_checkpoints")]
        if not args.resume_reviewed or len(completed) != 1 or hashlib.sha256(metadata.read_bytes()).hexdigest() != completed[0]["sha256"]:
            raise ValueError("Existing metadata requires verified, explicitly reviewed resumption")
    else:
        budget.fetch("https://api.github.com/repos/liebharc/homr/releases/tags/onnx_checkpoints", metadata, 1_000_000)
    release = json.loads(metadata.read_text(encoding="utf-8"))
    cached = json.loads((Path(__file__).parent / ".runtime/upstream-audit-20261005/github-evidence.json").read_text(encoding="utf-8"))
    downloads = args.runtime / "download"
    downloads.mkdir(exist_ok=args.resume_reviewed)
    identity = {"candidate": "homr-465-upstream", "source_revision": REVISION, "model_id": MODEL_ID,
                "release_metadata_sha256": hashlib.sha256(metadata.read_bytes()).hexdigest(), "archives": {}, "models": {}}
    for kind in ("encoder", "decoder"):
        name = f"{kind}_pytorch_model_{MODEL_ID}_fp16.zip"
        matches = [asset for asset in release["assets"] if asset["name"] == name]
        historical = [asset for asset in cached["release_assets"] if asset["name"] == name]
        if len(matches) != 1 or len(historical) != 1:
            raise ValueError("Expected exactly one published checkpoint archive")
        asset, old = matches[0], historical[0]
        if any(asset[field] != old[field] for field in ("id", "size", "digest")):
            raise ValueError("Published checkpoint identity differs from approved audit")
        archive = downloads / name
        completed = [row for row in budget.data["requests"] if row["url"] == asset["browser_download_url"] and row["status"] == "complete"]
        if archive.exists() and completed:
            if not args.resume_reviewed or len(completed) != 1 or hashlib.sha256(archive.read_bytes()).hexdigest() != completed[0]["sha256"]:
                raise ValueError("Existing archive drift")
            row = completed[0]
        else:
            if archive.exists():
                if not args.resume_reviewed:
                    raise ValueError("Partial archive requires reviewed resumption")
                archive.replace(archive.with_suffix(".failed.zip"))
                for attempt in budget.data["requests"]:
                    if attempt["url"] == asset["browser_download_url"] and attempt["status"] == "started":
                        attempt.update(status="interrupted", charged_payload_upper_bound=attempt["ceiling_bytes"])
                save(budget.path, budget.data)
            row = budget.fetch(asset["browser_download_url"], archive, asset["size"])
        if "sha256:" + row["sha256"] != asset["digest"]:
            raise ValueError("Published archive SHA-256 mismatch")
        if (args.runtime / kind).exists():
            if not args.resume_reviewed:
                raise ValueError("Existing model requires review")
            with zipfile.ZipFile(archive) as bundle:
                files = [{"path": item.filename, "bytes": item.file_size, "sha256": hashlib.sha256(bundle.read(item)).hexdigest()} for item in bundle.infolist() if not item.is_dir()]
            for item in files:
                path = args.runtime / kind / item["path"]
                if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
                    raise ValueError("Extracted model drift")
        else:
            files = extract(archive, args.runtime / kind)
        expected = name.removesuffix(".zip") + ".onnx"
        if len(files) != 1 or files[0]["path"] != expected:
            raise ValueError("Unexpected model archive layout")
        identity["archives"][kind] = {"name": name, "bytes": asset["size"], "sha256": row["sha256"], "asset_id": asset["id"]}
        identity["models"][kind] = {**files[0], "absolute_path": str((args.runtime / kind / expected).resolve())}
        save(args.evidence / "acquisition.json", identity)
    archive = downloads / (REVISION + ".zip")
    row = budget.fetch(f"https://codeload.github.com/liebharc/homr/zip/{REVISION}", archive, 150_000_000)
    files = extract(archive, args.runtime / "source", f"homr-{REVISION}/")
    identity["source_archive"] = {"sha256": row["sha256"], "bytes": row["received_bytes"], "url": row["url"]}
    identity["source_files"] = files
    save(args.evidence / "acquisition.json", identity)
    print(json.dumps({"candidate": identity["candidate"], "source_files": len(files), "payload_bytes": budget.data["received_payload_bytes"], "reserved_bytes": budget.data["reserved_bytes"]}))


if __name__ == "__main__":
    main()
