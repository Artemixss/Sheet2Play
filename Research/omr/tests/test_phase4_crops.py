import numpy as np
import pytest
from phase4_crops import expand_boxes, reviewed_dedup


def test_expansion_retains_clipped_symbols_and_adjacent_groups():
    page = np.full((600, 400), 255, dtype=np.uint8)
    page[110:190, 30:300] = 0
    page[370:430, 20:300] = 0
    boxes = expand_boxes(page, [(140, 165), (390, 410)])
    assert boxes[0][0] < 110 and boxes[0][1] > 190
    assert boxes[1][0] < 370 and boxes[1][1] > 430
    assert boxes[0][1] < boxes[1][0]


def test_nested_staff_fragment_requires_review():
    boxes = [(100, 500), (300, 400), (700, 1100)]
    with pytest.raises(ValueError, match="explicit image review"):
        reviewed_dedup(boxes, {})
    assert reviewed_dedup(boxes, {1: 0}) == [(100, 500), (700, 1100)]


def test_legitimate_adjacent_system_cannot_be_deleted_as_duplicate():
    with pytest.raises(ValueError, match="not contained"):
        reviewed_dedup([(100, 500), (700, 1100)], {1: 0})


def test_no_blank_boundary_fails_closed():
    with pytest.raises(ValueError, match="whitespace-safe"):
        expand_boxes(np.zeros((600, 400), dtype=np.uint8), [(200, 300)])


def test_separator_avoids_symbol_at_naive_midpoint():
    page = np.full((600, 400), 255, dtype=np.uint8)
    page[110:190, 20:300] = 0
    page[240:390, 20:300] = 0
    boxes = expand_boxes(page, [(120, 190), (285, 360)])
    assert boxes[0][1] < 240
    assert boxes[1][0] < 240 and boxes[1][1] > 390
