from __future__ import annotations

import io
from pathlib import Path
import tarfile

import pytest

from zeus_provenance import compare_release, file_record, inventory, validate_symbols, verify_records
from zeus_provenance_verify import verify_inherited


def bundle(tmp_path: Path, *, reordered: bool = False, unexpected: str | None = None) -> tuple[Path, Path]:
    model = tmp_path / "test.model"
    model.mkdir()
    contents = {"weights.h5": b"checkpoint", "options.json": b'{"height":192}\n',
                "tags.txt": b"<unk>\nnote\nrest\n", "README.md": b"release\n",
                "LICENSE": b"license\n"}
    archive = tmp_path / "published.tar.gz"
    with tarfile.open(archive, "w:gz") as stream:
        for name, data in contents.items():
            member = tarfile.TarInfo(f"{model.name}/{name}")
            member.size = len(data)
            stream.addfile(member, io.BytesIO(data))
            local = data if name == "weights.h5" else data.replace(b"\n", b"\r\n")
            if name == "tags.txt" and reordered:
                local = b"<unk>\r\nrest\r\nnote\r\n"
            (model / name).write_bytes(local)
        if unexpected:
            member = tarfile.TarInfo(unexpected)
            stream.addfile(member, io.BytesIO())
    return archive, model


def test_release_distinguishes_byte_and_semantic_identity(tmp_path: Path) -> None:
    archive, model = bundle(tmp_path)
    result = compare_release(archive, model)
    assert result["members"]["weights.h5"]["byte_equal"]
    assert not result["members"]["tags.txt"]["byte_equal"]
    assert result["members"]["tags.txt"]["semantic_equal"]
    assert result["members"]["options.json"]["semantic_equal"]
    assert result["independent_publisher_digest"] is None


def test_reordered_vocabulary_is_material_mismatch(tmp_path: Path) -> None:
    archive, model = bundle(tmp_path, reordered=True)
    with pytest.raises(ValueError, match="Material"):
        compare_release(archive, model)


def test_changed_weights_are_material_mismatch(tmp_path: Path) -> None:
    archive, model = bundle(tmp_path)
    (model / "weights.h5").write_bytes(b"other-checkpoint")
    with pytest.raises(ValueError, match="Material"):
        compare_release(archive, model)


@pytest.mark.parametrize("name", ["../escape", "/absolute", "test.model/extra", "test.model/tags.txt"])
def test_unexpected_or_duplicate_archive_member_rejected(tmp_path: Path, name: str) -> None:
    archive, model = bundle(tmp_path, unexpected=name)
    with pytest.raises(ValueError, match="Unexpected"):
        compare_release(archive, model)
    assert not (tmp_path.parent / "escape").exists()


def test_shadowed_recognizer_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Model"):
        validate_symbols({"symbols": {"Model": str(tmp_path / "other.py")}}, tmp_path)


def test_environment_changes_and_additions_are_rejected(tmp_path: Path) -> None:
    module = tmp_path / "module.py"
    module.write_text("original", encoding="utf-8")
    records = inventory(tmp_path)
    verify_records(tmp_path, records)
    module.write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="changed"):
        verify_records(tmp_path, records)
    module.write_text("original", encoding="utf-8")
    (tmp_path / "shadow.py").write_text("new", encoding="utf-8")
    with pytest.raises(ValueError, match="file set"):
        verify_records(tmp_path, records)


def test_inventory_path_escape_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="escapes"):
        verify_records(tmp_path, [{"path": "../outside", "sha256": "x", "bytes": 1}])


def test_volatile_bytecode_is_excluded(tmp_path: Path) -> None:
    (tmp_path / "runtime.py").write_text("source", encoding="utf-8")
    cache = tmp_path / "__pycache__"
    cache.mkdir()
    (cache / "runtime.pyc").write_bytes(b"cache")
    assert [row["path"] for row in inventory(tmp_path)] == ["runtime.py"]


def test_inherited_detector_pins_cover_nested_source_and_bridge_patch(tmp_path: Path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    (package / "detector.py").write_text("detector", encoding="utf-8")
    bridge = tmp_path / "homr_gpu.py"
    bridge.write_text("cuda patch", encoding="utf-8")
    pins = {"local_source": {"root": str(package), "files": inventory(package)},
            "bridge_patch": file_record(bridge)}
    assert verify_inherited(pins) == 2
    bridge.write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="Inherited detector"):
        verify_inherited(pins)
