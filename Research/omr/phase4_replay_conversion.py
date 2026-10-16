"""Replay all original conversions through observed native output with byte parity."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

from zeus_attribution_prepare import HERE, ROOT, configure_cpu, save_json
from phase4_validation import file_hash
from phase4_conversion import convert_observed

OUT = HERE / "reports/zeus-attribution/phase4"
OLD = OUT.parent / "phase3"


def main() -> None:
    configure_cpu()
    path = OLD / "resume-20261005-1746/replay_conversion-v2.py"
    spec = importlib.util.spec_from_file_location("pinned_replay", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Replay loader unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT, module.HERE, module.OUT, module.SOURCE = ROOT, HERE, OLD, HERE / "zeus/source"
    manifest, identity = module.load_pinned_sources()
    sys.path.insert(0, str(HERE / "zeus/source"))
    destination = OUT / "conversion-replay"
    destination.mkdir(exist_ok=False)
    rows = []
    import json
    for item in manifest["items"]:
        for number, crop in enumerate(item["crops"], 1):
            work = OLD / "inference" / item["item_id"] / f"system-{number:04d}"
            prediction = json.loads((work / "prediction.json").read_text())
            if prediction["crop_sha256"] != crop["sha256"]:
                raise ValueError("Historical input identity changed")
            for recipe in ("upstream", "wrapper"):
                original = prediction[recipe]
                xml = work / f"{recipe}.musicxml"
                target = destination / f"{item['item_id']}-{number}-{recipe}.musicxml"
                result = convert_observed(original["lmx"], target)
                expected = original["conversion"]["musicxml_sha256"]
                if result["status"] != "succeeded" or file_hash(xml) != expected or result["musicxml_sha256"] != expected:
                    raise ValueError("Observed conversion changed bytes or failure policy")
                rows.append({"item_id": item["item_id"], "system": number, "recipe": recipe,
                    "byte_parity": True, **result})
    save_json(OUT / "conversion-observability.json", {"rows": rows, "prior_identity": identity,
        "source_sha256": file_hash(Path(__file__)), "converter_sha256": file_hash(HERE / "phase4_conversion.py"),
        "summary": {"outputs": len(rows), "byte_parity_outputs": len(rows),
            "outputs_with_diagnostics": sum(bool(r["diagnostics"]) for r in rows),
            "diagnostic_lines": sum(len(r["diagnostics"].splitlines()) for r in rows)}})
    print(f"Verified {len(rows)} native byte-identical observed conversions", flush=True)


if __name__ == "__main__":
    main()
