"""Development-only HOMR system detection with an explicit image-coordinate contract."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _system_boxes(multi_staffs: list[Any]) -> list[dict[str, float]]:
    boxes: list[dict[str, float]] = []
    for multi in multi_staffs:
        min_x = float(min(staff.min_x for staff in multi.staffs))
        max_x = float(max(staff.max_x for staff in multi.staffs))
        min_y = float(min(staff.min_y for staff in multi.staffs))
        max_y = float(max(staff.max_y for staff in multi.staffs))
        height = max_y - min_y
        boxes.append({
            "min_x": min_x,
            "max_x": max_x,
            "min_y": max(0.0, min_y - height * 0.2),
            "max_y": max_y + height * 0.2,
        })
    return boxes


def save_detection(
    source_path: Path, detector_image_path: Path, output_json: Path,
    multi_staffs: list[Any], preprocessed: Any,
) -> None:
    import cv2

    source = cv2.imread(str(source_path))
    if source is None or preprocessed is None or len(preprocessed.shape) < 2:
        raise ValueError("Source or detector image is invalid")
    detector_image_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(detector_image_path), preprocessed):
        raise OSError(f"Could not save detector image: {detector_image_path}")
    restored = cv2.imread(str(detector_image_path), cv2.IMREAD_UNCHANGED)
    if restored is None or restored.shape != preprocessed.shape or not (restored == preprocessed).all():
        raise ValueError("Saved detector image differs from the prediction image")
    document = {
        "schema_version": 2,
        "coordinate_space": "homr_predictions_preprocessed",
        "preprocessing": "HOMR autocrop, resize, CLAHE; crop the returned image directly",
        "source_image": {
            "sha256": _sha256(source_path),
            "width": int(source.shape[1]),
            "height": int(source.shape[0]),
        },
        "detector_image": {
            "sha256": _sha256(detector_image_path),
            "width": int(restored.shape[1]),
            "height": int(restored.shape[0]),
        },
        "systems": _system_boxes(multi_staffs),
    }
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output_json", type=Path)
    parser.add_argument("detector_image", type=Path)
    parser.add_argument("bridge_dir", type=Path)
    args = parser.parse_args(arguments)
    if not args.source.is_file() or not (args.bridge_dir / "homr_gpu.py").is_file():
        parser.error("Source image or pinned Bridge runtime is missing")
    sys.path.insert(0, str(args.bridge_dir.resolve()))
    import homr_gpu

    homr_gpu.configure_cuda()
    from homr.main import ProcessingConfig, detect_staffs_in_image

    config = ProcessingConfig(
        enable_debug=False,
        enable_cache=False,
        write_staff_positions=False,
        read_staff_positions=False,
        selected_staff=0,
        transformer_use_gpu=True,
        segnet_use_gpu=True,
        coreml_encoder=False,
        title_detection=False,
    )
    multi_staffs, preprocessed, _, _, _ = detect_staffs_in_image(str(args.source), config)
    save_detection(args.source, args.detector_image, args.output_json, multi_staffs, preprocessed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
