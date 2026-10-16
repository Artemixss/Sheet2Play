from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from homr_465_capture import verify_config
from homr_465_compatibility import checked_source, interface_requirements
from homr_465_download import MODEL_ID, REVISION
from screening_homr_compatibility import digest, sha256_file

HERE = Path(__file__).resolve().parents[1]


def test_source_extra_file_or_mutation_rejected(tmp_path):
    source = tmp_path / "source"
    (source / "homr").mkdir(parents=True)
    module = source / "homr/__init__.py"
    module.write_text("original")
    acquisition = {"source_revision": REVISION, "model_id": MODEL_ID,
                   "source_files": [{"path": "homr/__init__.py", "sha256": sha256_file(module)}]}
    checked_source(source, acquisition)
    module.write_text("mutated")
    with pytest.raises(ValueError, match="source homr"):
        checked_source(source, acquisition)
    module.write_text("original")
    (source / "homr/extra.py").write_text("extra")
    with pytest.raises(ValueError, match="inventory"):
        checked_source(source, acquisition)


@pytest.mark.parametrize("fault", ["position_dimension", "head_order", "precision", "cache_shape"])
def test_decoder_incompatibility_rejected(fault):
    historical = json.loads((HERE / "homr_455_contract.json").read_text())
    labels = copy.deepcopy(historical["labels"])
    labels["position"] = [".", "upper", "upper2", "lower", "lower2"]
    models = copy.deepcopy(historical["models"])
    models["decoder"]["outputs"][3]["shape"][-1] = 5
    interface_requirements(models, labels, historical)
    if fault == "position_dimension":
        models["decoder"]["outputs"][3]["shape"][-1] = 3
    elif fault == "head_order":
        models["decoder"]["outputs"][0], models["decoder"]["outputs"][1] = models["decoder"]["outputs"][1], models["decoder"]["outputs"][0]
    elif fault == "precision":
        models["decoder"]["outputs"][0]["type"] = "tensor(float)"
    else:
        models["decoder"]["outputs"][7]["shape"][1] = 9
    with pytest.raises(ValueError):
        interface_requirements(models, labels, historical)


def test_valid_identity_does_not_authorize_weaker_safeguards(tmp_path):
    config = {"title_detection": False, "threads": 8, "provider": "CUDAExecutionProvider",
              "safeguards": {"system_stop_percent": 90}}
    config["identity_sha256"] = digest(config)
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match="safeguard"):
        verify_config(path)
