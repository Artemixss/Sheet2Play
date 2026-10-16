from copy import deepcopy

import pytest

from screening_cpu_manifest import require_inventory_extension, require_current_policy
from screening_common import POLICY
from screening_cpu_run import is_scored_model_outcome


def profile() -> dict:
    return {"source": "fixed", "runtime": {"model": "fixed", "python_distributions":
            {"research": {"music21": "9.1.0"}}}, "scoring": "fixed"}


def test_additional_readable_metadata_is_separately_admissible() -> None:
    old = profile()
    current = deepcopy(old)
    current["runtime"]["python_distributions"]["research"]["certifi"] = "2026.7.22"
    require_inventory_extension(old, current)
    assert old == profile()


@pytest.mark.parametrize("field", ["source", "scoring"])
def test_changed_non_inventory_identity_is_rejected(field: str) -> None:
    old, current = profile(), profile()
    current[field] = "changed"
    with pytest.raises(ValueError, match="changed"):
        require_inventory_extension(old, current)


def test_changed_or_removed_existing_package_is_rejected() -> None:
    for packages in ({}, {"music21": "10.0"}):
        old, current = profile(), profile()
        current["runtime"]["python_distributions"]["research"] = packages
        with pytest.raises(ValueError, match="removed or its version changed"):
            require_inventory_extension(old, current)


def test_jvm_access_failure_stays_pending() -> None:
    assert not is_scored_model_outcome({"status": "failed", "error": {
        "code": "AUDIVERIS_FAILED", "message": "Error loading java.security file"}})
    assert is_scored_model_outcome({"status": "failed", "error": {
        "code": "AUDIVERIS_EXPORT_MISSING", "message": "No exported MusicXML"}})


def test_v5_admits_only_the_unchanged_current_resource_policy() -> None:
    require_current_policy({"schema_version": 5, "resource_policy": POLICY})
    with pytest.raises(ValueError, match="pinned v5"):
        require_current_policy({"schema_version": 4, "resource_policy": POLICY})
    with pytest.raises(ValueError, match="90%"):
        require_current_policy({"schema_version": 5, "resource_policy": {**POLICY, "ram_admission_percent": 75}})
