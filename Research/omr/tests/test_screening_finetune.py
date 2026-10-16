"""Fine-tune provenance failures must not admit an unverified model."""
from __future__ import annotations

import copy
from pathlib import Path

import pytest

import screening_common as common
from screening_finetune_compatibility import HEADS, check_parity, checked_files
from sheet2play_omr.adapter_contract import sha256_file


def parity_fixture():
    artifacts = {name: {"sha256": letter * 64} for name, letter in
                 (("checkpoint", "a"), ("encoder_onnx", "b"), ("decoder_onnx", "c"))}
    provenance = {"format": "homr-epoch14-provenance-v2", "artifacts": artifacts,
                  "verification": {"cpu_parity": "pass"}}
    output = {"terminated_eos": True, "steps": 63, "token_count": 63}
    verification = {"status": "pass", "artifacts": copy.deepcopy(artifacts),
                    "tolerance": {"atol": 0.02, "rtol": 0.02},
                    "source": {"strict_model_load": "pass", "strict_wrapper_load": "pass"},
                    "encoder": {name: {"pass": True, "violations": 0} for name in ("synthetic", "music")},
                    "decoder_steps": [{"cache_bearing": step > 0,
                        "heads": {name: {"pass": True, "violations": 0} for name in (*HEADS, "attention")},
                        "cache": {"pass": True, "violations": 0, "count": 32}} for step in range(3)],
                    "generation": {"pytorch_repeat_equal": True, "onnx_repeat_equal": True,
                                   "cross_tokens_equal": True, "pytorch": output, "onnx": dict(output)}}
    return provenance, verification


def test_verified_generation_and_cache_evidence_passes():
    check_parity(*parity_fixture())


@pytest.mark.parametrize("change", [
    lambda v: v["artifacts"]["decoder_onnx"].update(sha256="d" * 64),
    lambda v: v["source"].update(strict_model_load="missing parameters"),
    lambda v: v["tolerance"].update(atol=1.0),
    lambda v: v["decoder_steps"].pop(),
    lambda v: v["decoder_steps"][1]["cache"].update(count=0),
    lambda v: v["decoder_steps"][0]["heads"].pop("position"),
    lambda v: v["decoder_steps"][2]["heads"]["rhythm"].update(violations=1),
    lambda v: v["generation"].update(cross_tokens_equal=False),
    lambda v: v["generation"]["onnx"].update(terminated_eos=False),
])
def test_incomplete_or_mismatched_parity_cannot_admit(change):
    provenance, verification = parity_fixture()
    change(verification)
    with pytest.raises(ValueError):
        check_parity(provenance, verification)


def test_source_inventory_rejects_tampering_and_escape(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    file = source / "configs.py"
    file.write_text("original", encoding="utf-8")
    inventory = {"configs.py": sha256_file(file)}
    checked_files(source, inventory)
    file.write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="identity differs"):
        checked_files(source, inventory)
    outside = tmp_path / "outside.py"
    outside.write_text("outside", encoding="utf-8")
    with pytest.raises(ValueError, match="identity differs"):
        checked_files(source, {"../outside.py": sha256_file(outside)})


def test_finetune_registered_for_run_and_score_without_weakening_policy():
    assert "fine_tuned_homr" in common.RUNNABLE
    assert common.POLICY["ram_admission_percent"] == 90
    assert common.POLICY["device_vram_admission_percent"] == 90
    assert common.POLICY["max_pages_per_chunk"] == 5
