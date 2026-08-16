from __future__ import annotations

import tempfile
import json
import unittest
from pathlib import Path

from sheet2play_omr.olimpic import OlimpicSample, select_stratified_canary
from sheet2play_omr.phase3_benchmark import (
    DECODER_STATE_REVISION,
    _load_checkpoint,
    aggregate_results,
)


class OlimpicPhase3Tests(unittest.TestCase):
    def test_canary_selects_one_system_per_score_deterministically(self) -> None:
        samples = [
            OlimpicSample(
                identifier=f"score-{score}/system-{system}",
                score_id=f"score-{score}",
                image=f"{score}-{system}.png",
                musicxml=f"{score}-{system}.musicxml",
                lmx=f"{score}-{system}.lmx",
            )
            for score in range(5)
            for system in range(4)
        ]
        first = select_stratified_canary(samples, count=5, seed=17)
        second = select_stratified_canary(samples, count=5, seed=17)

        self.assertEqual(first, second)
        self.assertEqual(5, len({sample.score_id for sample in first}))

    def test_phase3_aggregation_records_failures_latency_and_retry_rate(self) -> None:
        rows = [
            {
                "valid": True,
                "seconds": 10.0,
                "peak_vram_bytes": 100,
                "fallback_attempted": False,
                "metrics": {
                    "pitch_f1": 1.0,
                    "onset_f1": 0.8,
                    "onset_duration_f1": 0.7,
                    "mean_offset_error": 0.1,
                    "staff_accuracy": 0.9,
                    "aligned_voice_accuracy": 0.8,
                },
            },
            {
                "valid": False,
                "seconds": 20.0,
                "peak_vram_bytes": 200,
                "fallback_attempted": True,
            },
        ]

        summary = aggregate_results(rows)

        self.assertEqual(0.5, summary["structural_validity"])
        self.assertEqual(0.5, summary["catastrophic_page_failure_rate"])
        self.assertEqual(0.5, summary["beam_to_grammar_retry_rate"])
        self.assertEqual(15.0, summary["median_seconds_per_system"])
        self.assertEqual(20.0, summary["p95_seconds_per_system"])
        self.assertEqual(200, summary["peak_vram_bytes"])

    def test_checkpoint_migration_invalidates_only_stateful_grammar_rows(self) -> None:
        payload = {
            "schema_version": 1,
            "sample_ids": ["beam", "grammar"],
            "transcoda_beam_only": {"beam": {"valid": True}, "grammar": {"valid": False}},
            "transcoda_beam_then_grammar": {
                "beam": {"valid": True, "fallback_attempted": False},
                "grammar": {"valid": False, "fallback_attempted": True},
            },
            "homr": {"beam": {"valid": True}, "grammar": {"valid": True}},
            "determinism": {"sample_id": "beam", "passed": True},
        }
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "checkpoint.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            migrated = _load_checkpoint(path, ["beam", "grammar"])

        self.assertEqual(DECODER_STATE_REVISION, migrated["decoder_state_revision"])
        self.assertIn("beam", migrated["transcoda_beam_then_grammar"])
        self.assertNotIn("grammar", migrated["transcoda_beam_then_grammar"])
        self.assertEqual(2, len(migrated["transcoda_beam_only"]))
        self.assertEqual(2, len(migrated["homr"]))
        self.assertTrue(migrated["determinism"]["passed"])


if __name__ == "__main__":
    unittest.main()
