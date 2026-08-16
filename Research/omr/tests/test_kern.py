from __future__ import annotations

import unittest

from sheet2play_omr.errors import ResearchError
from sheet2play_omr.kern import combine_pages, validate_kern


SIMPLE_PAGE = """**kern\t**kern
*M4/4\t*M4/4
=1\t=1
4c\t4C
*-\t*-
"""


class KernValidationTests(unittest.TestCase):
    def test_valid_two_staff_page(self) -> None:
        result = validate_kern(SIMPLE_PAGE, page=1)
        self.assertEqual(2, result.initial_spines)
        self.assertEqual(2, result.maximum_spines)

    def test_balanced_split_and_merge_is_valid(self) -> None:
        text = """**kern\t**kern
*^\t*
4c\t4e\t2C
*v\t*v\t*
*-\t*-
"""
        self.assertEqual(3, validate_kern(text).maximum_spines)

    def test_bad_field_count_is_rejected(self) -> None:
        with self.assertRaisesRegex(ResearchError, "expected 2"):
            validate_kern("**kern\t**kern\n4c\n*-\t*-\n", page=1)

    def test_missing_eos_is_truncation_not_repair(self) -> None:
        with self.assertRaises(ResearchError) as raised:
            validate_kern(SIMPLE_PAGE, page=2, saw_eos=False, hit_max_length=True)
        self.assertEqual("KERN_TRUNCATED", raised.exception.code)

    def test_pages_combine_without_intermediate_terminators(self) -> None:
        combined = combine_pages([SIMPLE_PAGE, SIMPLE_PAGE])
        self.assertEqual(1, combined.count("**kern\t**kern"))
        self.assertEqual(1, combined.count("*-\t*-"))
        self.assertEqual(2, combined.count("4c\t4C"))


if __name__ == "__main__":
    unittest.main()

