from __future__ import annotations

import json
import runpy
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace


def test_detect_systems_matches_pinned_homr_api(tmp_path: Path, monkeypatch) -> None:
    captured: dict[str, object] = {}

    class ProcessingConfig:
        def __init__(self, **values: object) -> None:
            captured["config"] = values

    staff = SimpleNamespace(min_x=10, max_x=90, min_y=20, max_y=60)

    def detect_staffs_in_image(image_path: str, config: object):
        captured["image"] = image_path
        captured["instance"] = config
        return [SimpleNamespace(staffs=[staff])], object(), object(), object(), 1

    fake_gpu = ModuleType("homr_gpu")
    fake_gpu.configure_cuda = lambda: None  # type: ignore[attr-defined]
    fake_main = ModuleType("homr.main")
    fake_main.ProcessingConfig = ProcessingConfig  # type: ignore[attr-defined]
    fake_main.detect_staffs_in_image = detect_staffs_in_image  # type: ignore[attr-defined]
    fake_homr = ModuleType("homr")
    monkeypatch.setitem(sys.modules, "homr_gpu", fake_gpu)
    monkeypatch.setitem(sys.modules, "homr", fake_homr)
    monkeypatch.setitem(sys.modules, "homr.main", fake_main)

    script = Path(__file__).resolve().parents[1] / "detect_systems.py"
    namespace = runpy.run_path(str(script))
    output = tmp_path / "systems.json"
    monkeypatch.setattr(sys, "argv", [str(script), "input.png", str(output)])

    namespace["main"]()

    assert captured["config"] == {
        "enable_debug": False,
        "enable_cache": False,
        "write_staff_positions": False,
        "read_staff_positions": False,
        "selected_staff": 0,
        "transformer_use_gpu": True,
        "segnet_use_gpu": True,
        "coreml_encoder": False,
        "title_detection": False,
    }
    document = json.loads(output.read_text(encoding="utf-8"))
    assert document["systems"] == [
        {"min_x": 10.0, "max_x": 90.0, "min_y": 12.0, "max_y": 68.0}
    ]
