from pathlib import Path
import json
import os
import sys
from types import ModuleType

import pytest

from homr_baseline import digest, resolve_python, save
from homr_baseline_infer import resource_failure
import homr_baseline_infer


def test_installed_runtime_precedes_ancestor_checkout(tmp_path: Path):
    bridge = tmp_path / "dist/Bridge/bridge.py"
    local = bridge.parent / ".venv-homr-gpu/Scripts/python.exe"
    ancestor = tmp_path / "Bridge/.venv-homr-gpu/Scripts/python.exe"
    for path in (local, ancestor):
        path.parent.mkdir(parents=True)
        path.write_bytes(b"runtime")
    assert resolve_python(bridge) == local
    local.unlink()
    assert resolve_python(bridge) == ancestor


def test_missing_runtime_fails_without_system_python_fallback(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="could not be resolved"):
        resolve_python(tmp_path / "dist/Bridge/bridge.py")


def test_evidence_cannot_be_overwritten(tmp_path: Path):
    path = tmp_path / "evidence.json"
    save(path, {"status": "preserved"})
    original = digest(path)
    with pytest.raises(FileExistsError):
        save(path, {"status": "replaced"})
    assert digest(path) == original


@pytest.mark.parametrize("error", [MemoryError(), RuntimeError("MaxPool: bad allocation"),
    RuntimeError("Unable to allocate 39.8 MiB"), OSError("Not enough quota")])
def test_wrapped_allocation_errors_require_batch_stop(error):
    assert resource_failure(error)


def test_musical_export_failure_is_distinct_from_resource_failure():
    assert not resource_failure(ValueError("Invalid note duration"))


def test_native_batch_preserves_failure_and_stops_before_next_input(tmp_path, monkeypatch):
    image = tmp_path / "source.png"
    image.write_bytes(b"fixture image")
    inventory = {"homr_source": [], "active_weights": [], "installed_bridge": [],
                 "identity_sha256": "fixture-runtime"}
    rows = [{"item_id": name, "image": {"path": str(image), "sha256": digest(image)},
             "numeric_accuracy_eligible": True} for name in ("first", "second")]
    (tmp_path / "runtime-inventory.json").write_text(json.dumps(inventory))
    (tmp_path / "reference-eligibility.json").write_text(json.dumps(rows))
    calls = []

    def process_image(*args):
        calls.append(args[0])
        raise RuntimeError("MaxPool: bad allocation")

    native = ModuleType("homr.main")
    native.__file__ = str(tmp_path / "mock_homr.py")
    native.process_image = process_image
    native.generate_xml = lambda *args: None
    native.ProcessingConfig = lambda *args: args
    native.XmlGeneratorArguments = lambda *args: args
    homr = ModuleType("homr")
    homr.main = native
    gpu = ModuleType("homr_gpu")
    gpu.configure_cuda = lambda: None
    transformer = ModuleType("homr.transformer")
    staff = ModuleType("homr.transformer.staff2score")
    staff.Staff2Score = type("Staff2Score", (), {"predict": lambda self, image: []})
    gate = ModuleType("sitecustomize")
    gate.INSTALLED = True
    for name, module in {"homr": homr, "homr.main": native, "homr_gpu": gpu,
                         "homr.transformer": transformer,
                         "homr.transformer.staff2score": staff, "sitecustomize": gate}.items():
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setattr(sys, "argv", ["capture", "--evidence", str(tmp_path)])
    monkeypatch.setattr(homr_baseline_infer, "gpu_sample",
                        lambda: {"utc": 0, "total_mib": 6144, "used_mib": 0})
    assert homr_baseline_infer.main() == 2
    receipt = json.loads((tmp_path / "development/first/result.json").read_text())
    assert receipt["status"] == "resource_stopped"
    assert "bad allocation" in receipt["error"]
    assert len(calls) == 1
    assert not (tmp_path / "development/second").exists()
    assert (tmp_path / "development/first/tokens.json").exists()
    with pytest.raises(RuntimeError, match="Prior resource failure requires review"):
        homr_baseline_infer.main()
    assert len(calls) == 1


@pytest.mark.skipif(os.name != "nt", reason="Windows Job telemetry")
def test_windows_worker_memory_sample_has_current_process_counters():
    from homr_baseline_resources import memory_sample
    sample = memory_sample()
    assert sample["private_bytes"] > 0
    assert sample["peak_private_bytes"] >= sample["private_bytes"]
    assert sample["pid"] == os.getpid()


@pytest.mark.parametrize("height", [5.8, 6.8, 8.0])
def test_page_layout_uses_score_label_font_and_excludes_margin_page_number(height):
    from homr_baseline_pages import layout_markers
    class Page:
        def __init__(self, words):
            self.words = words
        def extract_words(self):
            return self.words
    def word(text, top, font_height):
        return {"text": text, "x0": 42, "top": top, "height": font_height}
    first = Page([word("5", 200, height), word("9", 400, height)])
    second = Page([word("2", 42, 11), word("13", 63, height), word("3", 90, 8.6)])
    assert layout_markers(first, second, ["5", "9"]) == (["5", "9"], ["13"])


def test_title_only_profile_is_identified_and_rejects_musical_or_limit_drift(tmp_path):
    from homr_baseline_profile import title_disabled_profile, validate_profile
    runtime = "a" * 64
    profile = title_disabled_profile(runtime)
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(profile))
    assert validate_profile(path, runtime) == profile
    profile["processing_config_delta"]["selected_staff"] = 0
    path.write_text(json.dumps(profile))
    with pytest.raises(ValueError, match="profile drift"):
        validate_profile(path, runtime)
    profile = title_disabled_profile(runtime)
    profile["safeguards"]["worker_bytes"] *= 2
    path.write_text(json.dumps(profile))
    with pytest.raises(ValueError, match="profile drift"):
        validate_profile(path, runtime)


def test_equivalence_ignores_only_title_and_detects_tempo_changes(tmp_path):
    from homr_title_equivalence import xml_without_title
    left, right = tmp_path / "left.xml", tmp_path / "right.xml"
    template = '<score-partwise><work><work-title>{}</work-title></work><part id="P1"><measure number="1"><direction><sound tempo="{}"/></direction></measure></part></score-partwise>'
    left.write_text(template.format("Detected title", 120))
    right.write_text(template.format("", 120))
    assert xml_without_title(left) == xml_without_title(right)
    right.write_text(template.format("", 121))
    assert xml_without_title(left) != xml_without_title(right)
