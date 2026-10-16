"""Known exact null distributions and composition-weighting regressions."""
from __future__ import annotations

import pytest

from screening_homr_statistics import composition_differences, exact_superiority_p
from screening_score import (PRESERVED_SHIPPED_SCORE_RUNNER_SHA256,
                             compatible_score_identity)


def test_exact_test_counts_all_label_swaps_and_ties():
    assert exact_superiority_p([0.25] * 18) == 1 / 2 ** 18
    assert exact_superiority_p([-0.25] * 18) == 1.0
    assert exact_superiority_p([0.0] * 18) == 1.0
    assert exact_superiority_p([0.5] + [0.0] * 17) == 0.5


def test_compositions_have_equal_weight_despite_page_count():
    left = [{"item_id": f"item-{index}", "composition_group": f"group-{index}",
             "onset_duration_f1": 0.75} for index in range(18)]
    right = [{**row, "onset_duration_f1": 0.5} for row in left]
    left.append({"item_id": "second-page", "composition_group": "group-0",
                 "onset_duration_f1": 0.0})
    right.append({**left[-1], "onset_duration_f1": 0.5})
    differences = composition_differences(left, right)
    assert differences.count(0.25) == 17
    assert differences.count(-0.125) == 1
    with pytest.raises(ValueError, match="item sets"):
        composition_differences(left + left[:1], right)


def test_preserved_shipped_score_runner_does_not_allow_changed_input():
    expected = {"item_id": "page", "reference_sha256": "a" * 64,
                "runner_sha256": "b" * 64}
    saved = {**expected, "runner_sha256": PRESERVED_SHIPPED_SCORE_RUNNER_SHA256}
    assert compatible_score_identity(expected, saved)
    assert not compatible_score_identity(expected, {**saved, "reference_sha256": "c" * 64})
    assert not compatible_score_identity(expected, {**saved, "runner_sha256": "d" * 64})
