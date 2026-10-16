"""Retain native app-465 artifacts or run the matched no-title app-426 control."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
BRIDGE = HERE.parents[1] / "Bridge"


def capture(engine: str, manifest: Path, item: str, output: Path) -> int:
    rows = json.loads(manifest.read_text(encoding="utf-8"))
    matches = [row for row in rows if row["item_id"] == item]
    if len(matches) != 1:
        raise ValueError("Expected exactly one selected input")
    if engine == "homr":
        from homr_465_capture import capture as capture_control
        return capture_control(manifest.with_name("control-configuration.json"), manifest, item, output)
    sys.path.insert(0, str(BRIDGE))
    from homr465_profile import sha256_file
    from homr465_native import main
    row = matches[0]
    source = Path(row["image"]["path"])
    if sha256_file(source) != row["image"]["sha256"]:
        raise ValueError("Selected input identity drift")
    output.mkdir(parents=True, exist_ok=False)
    image = output / "input.png"
    shutil.copyfile(source, image)
    code = main(image, output / "native.json")
    native = json.loads((output / "native.json").read_text())
    receipt = {**native, "item_id": item, "input_sha256": row["image"]["sha256"],
               "artifacts": [{"path": str(path), "sha256": sha256_file(path)}
                             for path in sorted(output.rglob("*")) if path.is_file()]}
    (output / "result.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: receipt[key] for key in ("item_id", "status", "elapsed_seconds")}))
    return code


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("engine", choices=("homr", "homr465"))
    parser.add_argument("manifest", type=Path)
    parser.add_argument("item")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    raise SystemExit(capture(args.engine, args.manifest, args.item, args.output))
