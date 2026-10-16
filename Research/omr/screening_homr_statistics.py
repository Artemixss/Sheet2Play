"""Paired composition statistics for the corrected HOMR screen."""
from __future__ import annotations

from collections import defaultdict
import math
import statistics
from typing import Any

import numpy as np

from screening_report import paired_difference


def composition_differences(left: list[dict[str, Any]],
                            right: list[dict[str, Any]]) -> list[float]:
    by_right = {row["item_id"]: row for row in right}
    if (len(by_right) != len(right) or len({row["item_id"] for row in left}) != len(left)
            or {row["item_id"] for row in left} != set(by_right)):
        raise ValueError("Paired item sets differ or contain duplicates")
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in left:
        other = by_right[row["item_id"]]
        if row["composition_group"] != other["composition_group"]:
            raise ValueError("Paired composition differs")
        difference = row["onset_duration_f1"] - other["onset_duration_f1"]
        if not math.isfinite(difference):
            raise ValueError("Nonfinite paired metric")
        grouped[row["composition_group"]].append(difference)
    if len(grouped) != 18:
        raise ValueError("Expected the 18 frozen composition groups")
    return [statistics.mean(grouped[group]) for group in sorted(grouped)]


def exact_superiority_p(differences: list[float]) -> float:
    if len(differences) != 18 or not all(math.isfinite(value) for value in differences):
        raise ValueError("Exact test requires 18 finite composition differences")
    null_sums = np.array([0.0])
    for difference in differences:
        null_sums = np.concatenate((null_sums + difference, null_sums - difference))
    observed = math.fsum(differences)
    tolerance = max(1.0, abs(observed)) * 1e-12
    return float(np.count_nonzero(null_sums >= observed - tolerance) / null_sums.size)


def paired_statistics(left: list[dict[str, Any]], right: list[dict[str, Any]],
                      seed: int) -> dict[str, Any]:
    differences = composition_differences(left, right)
    result = paired_difference(left, right, seed)
    # Bootstrap intervals estimate effect uncertainty; null label swaps test superiority.
    result.pop("one_sided_superiority_p")
    result.update(one_sided_superiority_p=exact_superiority_p(differences),
                  hypothesis_test="exact paired composition label swaps; alternative greater",
                  null_assignments=2 ** len(differences),
                  composition_differences=differences)
    return result
