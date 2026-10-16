"""Capture pinned Delinearizer diagnostics without changing saved conversion bytes."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[5]
HERE = ROOT / "Research/omr"
OUT = HERE / "reports/zeus-attribution/phase3"
SOURCE = HERE / "zeus/source"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_pinned_sources() -> tuple[dict, dict]:
    manifest_path = OUT / "experiment-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    identity = json.loads((OUT.parent / "phase1/diagnostic-identity.json").read_text())
    receipt = json.loads((OUT / "verified-bytes.json").read_text())
    if not receipt["verified"] or receipt["identity_sha256"] != manifest["diagnostic_identity"]:
        raise ValueError("Successful byte verification is required")
    if identity["identity_sha256"] != manifest["diagnostic_identity"]:
        raise ValueError("Diagnostic source identity changed")
    if Path(sys.executable).resolve() != Path(identity["identity"]["probe"]["executable"]).resolve():
        raise ValueError("Replay must use the pinned Zeus interpreter")
    pins = dict(manifest["sources"])
    for record in identity["identity"]["upstream_source"]:
        path = (SOURCE / record["path"]).resolve()
        if not path.is_relative_to(SOURCE.resolve()):
            raise ValueError("Pinned upstream path escapes its root")
        pins[str(path)] = record["sha256"]
    for path, expected in pins.items():
        if digest(Path(path)) != expected:
            raise ValueError(f"Pinned source changed: {path}")
    return manifest, {"manifest_sha256": digest(manifest_path),
                      "diagnostic_identity": identity["identity_sha256"],
                      "source_hashes": pins, "script_sha256": digest(Path(__file__))}


def replay_one(delinearizer_type, part_to_score, result: dict, path: Path) -> dict:
    if result["conversion"]["status"] != "succeeded":
        raise ValueError(f"Original conversion failed: {path}")
    expected = result["conversion"]["musicxml_sha256"]
    if digest(path) != expected:
        raise ValueError(f"Saved XML changed: {path}")
    diagnostics = io.StringIO()
    delinearizer = delinearizer_type(errout=diagnostics)
    delinearizer.process_text(result["lmx"])
    buffer = io.BytesIO()
    part_to_score(delinearizer.part_element).write(buffer, encoding="utf-8", xml_declaration=True)
    actual = hashlib.sha256(buffer.getvalue()).hexdigest()
    if actual != expected:
        original, replayed = path.read_bytes(), buffer.getvalue()
        offset = next((i for i, pair in enumerate(zip(original, replayed)) if pair[0] != pair[1]),
                      min(len(original), len(replayed)))
        print(json.dumps({"first_difference": offset, "original_bytes": len(original),
                          "replayed_bytes": len(replayed),
                          "original_context": repr(original[max(0, offset-60):offset+180]),
                          "replay_context": repr(replayed[max(0, offset-60):offset+180])}), flush=True)
        raise ValueError(f"Diagnostic replay changed XML: {path}")
    messages = diagnostics.getvalue()
    return {"byte_parity": True, "musicxml_sha256": actual, "diagnostics": messages,
            "diagnostic_lines": len(messages.splitlines()),
            "original_stderr_diagnostics": result["conversion"]["diagnostics"],
            "lmx_sha256": hashlib.sha256(result["lmx"].encode()).hexdigest()}


def main() -> None:
    manifest, identity = load_pinned_sources()
    sys.path.insert(0, str(SOURCE))
    from app.linearization.Delinearizer import Delinearizer
    from app.symbolic.part_to_score import part_to_score
    rows = []
    for item in manifest["items"]:
        for number, crop in enumerate(item["crops"], 1):
            work = OUT / "inference" / item["item_id"] / f"system-{number:04d}"
            prediction = json.loads((work / "prediction.json").read_text())
            if prediction["crop_sha256"] != crop["sha256"]:
                raise ValueError("Saved prediction refers to a different crop")
            for recipe in ("upstream", "wrapper"):
                row = replay_one(Delinearizer, part_to_score, prediction[recipe],
                                 work / f"{recipe}.musicxml")
                rows.append({"item_id": item["item_id"], "system": number,
                             "recipe": recipe, **row})
    summary = {"outputs": len(rows), "byte_parity_outputs": sum(r["byte_parity"] for r in rows),
               "outputs_with_diagnostics": sum(bool(r["diagnostics"]) for r in rows),
               "diagnostic_lines": sum(r["diagnostic_lines"] for r in rows)}
    with (OUT / "conversion-diagnostics.json").open("x", encoding="utf-8") as stream:
        json.dump({"identity": identity, "summary": summary, "rows": rows}, stream,
                  indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
