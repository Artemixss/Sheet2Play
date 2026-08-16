from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sheet2play_omr.dataset import DatasetRecord, split_by_composition
from sheet2play_omr.errors import ResearchError
from sheet2play_omr.gates import (
    baseline_adaptation_gate,
    canary_gate,
    enforce_cloud_budget,
    promotion_gate,
    retention_gate,
)


class DatasetAndGateTests(unittest.TestCase):
    def test_compositions_never_cross_splits(self) -> None:
        records = [
            DatasetRecord(
                identifier=f"score-{index}",
                source="grandstaff",
                musicxml=f"score-{index}.musicxml",
                composition_hash=f"composition-{index}",
                staff_count=2,
                instrument="piano",
                license_conflict=False,
            )
            for index in range(12)
        ]
        splits = split_by_composition(
            records,
            seed=7,
            train_count=6,
            validation_count=3,
            test_count=3,
        )
        hashes = [{record.composition_hash for record in split} for split in splits.values()]
        self.assertFalse(hashes[0] & hashes[1])
        self.assertFalse(hashes[0] & hashes[2])
        self.assertFalse(hashes[1] & hashes[2])

    def test_cloud_budget_fails_closed(self) -> None:
        self.assertEqual(9.0, enforce_cloud_budget(1.5, 6.0))
        with self.assertRaises(ResearchError) as raised:
            enforce_cloud_budget(2.0, 6.0)
        self.assertEqual("BUDGET_EXCEEDED", raised.exception.code)

    def test_baseline_and_promotion_gates_are_independent(self) -> None:
        homr = {"pitch_f1": 0.97, "onset_duration_f1": 0.70}
        candidate = {
            "structural_validity": 0.97,
            "pitch_f1": 0.96,
            "onset_duration_f1": 0.76,
        }
        self.assertTrue(baseline_adaptation_gate(candidate, homr).passed)
        self.assertFalse(promotion_gate(candidate, homr).passed)

    def test_canary_and_retention_gates_fail_closed(self) -> None:
        homr = {"pitch_f1": 0.90, "onset_duration_f1": 0.60}
        canary = {
            "structural_validity": 0.90,
            "catastrophic_page_failure_rate": 0.10,
            "pitch_f1": 0.85,
            "onset_duration_f1": 0.60,
        }
        self.assertTrue(canary_gate(canary, homr).passed)
        canary["catastrophic_page_failure_rate"] = 0.11
        self.assertFalse(canary_gate(canary, homr).passed)

        full = {
            "structural_validity": 0.96,
            "catastrophic_page_failure_rate": 0.04,
            "pitch_f1": 0.89,
            "onset_duration_f1": 0.66,
            "median_seconds_per_system": 20.0,
            "peak_vram_bytes": 2 * 1024**3,
        }
        self.assertTrue(retention_gate(full, homr, deterministic=True).passed)
        self.assertFalse(retention_gate(full, homr, deterministic=False).passed)


if __name__ == "__main__":
    unittest.main()
