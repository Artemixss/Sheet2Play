from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sheet2play_omr.errors import ResearchError
from sheet2play_omr.olimpic import OlimpicSample, select_stratified_canary
from sheet2play_omr.phase3_benchmark import (
    CHECKPOINT_SCHEMA_VERSION,
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

    def test_phase3_aggregation_records_failures_latency_and_vram(self) -> None:
        rows = [
            {
                "valid": True,
                "seconds": 10.0,
                "peak_vram_bytes": 100,
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
            },
        ]

        summary = aggregate_results(rows)

        self.assertEqual(0.5, summary["structural_validity"])
        self.assertEqual(0.5, summary["catastrophic_page_failure_rate"])
        self.assertEqual(15.0, summary["median_seconds_per_system"])
        self.assertEqual(20.0, summary["p95_seconds_per_system"])
        self.assertEqual(200, summary["peak_vram_bytes"])

    def test_checkpoint_starts_empty_resumes_finished_rows_and_rejects_a_reselection(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "checkpoint.json"

            fresh = _load_checkpoint(path, ["one", "two"])
            self.assertEqual(CHECKPOINT_SCHEMA_VERSION, fresh["schema_version"])
            self.assertEqual(["one", "two"], fresh["sample_ids"])
            self.assertEqual({}, fresh["homr"])

            fresh["homr"]["one"] = {"valid": True, "seconds": 4.0}
            path.write_text(json.dumps(fresh), encoding="utf-8")

            resumed = _load_checkpoint(path, ["one", "two"])
            self.assertEqual({"valid": True, "seconds": 4.0}, resumed["homr"]["one"])
            self.assertNotIn("two", resumed["homr"])

            with self.assertRaises(ResearchError) as raised:
                _load_checkpoint(path, ["one", "three"])
            self.assertEqual("BENCHMARK_INVALID", raised.exception.code)


if __name__ == "__main__":
    unittest.main()
