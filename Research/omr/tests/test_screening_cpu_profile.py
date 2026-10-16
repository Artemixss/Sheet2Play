from __future__ import annotations

import pytest

from screening_cpu_profile import cpu_environment, validate_cpu_environment


def test_cpu_profile_limits_java_tensorflow_and_native_threads() -> None:
    environment = cpu_environment(8)
    assert environment["JAVA_TOOL_OPTIONS"] == "-XX:ActiveProcessorCount=8"
    assert environment["TF_NUM_INTRAOP_THREADS"] == "8"
    assert environment["TF_NUM_INTEROP_THREADS"] == "1"
    assert "CUDA_VISIBLE_DEVICES" not in environment
    validate_cpu_environment(environment, 8)


@pytest.mark.parametrize("threads", [0, -1, True, 1.5])
def test_invalid_cpu_limit_is_rejected(threads: object) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        cpu_environment(threads)


def test_changed_runtime_limit_is_rejected() -> None:
    environment = {**cpu_environment(8), "JAVA_TOOL_OPTIONS": "-XX:ActiveProcessorCount=16"}
    with pytest.raises(ValueError, match="differs"):
        validate_cpu_environment(environment, 8)
