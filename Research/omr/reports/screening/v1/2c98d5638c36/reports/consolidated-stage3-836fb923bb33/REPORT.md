# Consolidated canonical Stage 3 screening report

59 frozen pages in 18 complete compositions.

| Candidate | Pitch/onset/duration F1 | Onset F1 | Pitch F1 | Failures | Penalized OMR-NED |
| --- | ---: | ---: | ---: | ---: | ---: |
| homr_page | 0.4061 | 0.4316 | 0.9701 | 1/59 | 0.3620 |
| fine_tuned_homr | 0.3844 | 0.4096 | 0.9841 | 0/59 | 0.3645 |
| homr_455 | 0.2857 | 0.3060 | 0.9678 | 1/59 | 0.3851 |
| audiveris_page | 0.0986 | 0.1179 | 0.7568 | 8/59 | 0.5204 |
| zeus_page | 0.0228 | 0.0370 | 0.5763 | 0/59 | 0.8069 |

## Paired composition evidence

| Comparison | Primary F1 difference | 95% bootstrap interval | Holm-adjusted superiority p |
| --- | ---: | ---: | ---: |
| fine_tuned_homr_minus_homr_page | -0.0217 | [-0.0985, 0.0415] | 1.000000 |
| homr_455_minus_homr_page | -0.1204 | [-0.2536, 0.0199] | 1.000000 |
| audiveris_page_minus_homr_page | -0.3075 | [-0.4235, -0.1955] | 1.000000 |
| zeus_page_minus_homr_page | -0.3833 | [-0.5223, -0.2525] | 1.000000 |
| homr_page_minus_fine_tuned_homr | 0.0217 | [-0.0415, 0.0985] | 1.000000 |
| homr_455_minus_fine_tuned_homr | -0.0988 | [-0.2375, 0.0462] | 1.000000 |
| audiveris_page_minus_fine_tuned_homr | -0.2858 | [-0.4132, -0.1741] | 1.000000 |
| zeus_page_minus_fine_tuned_homr | -0.3616 | [-0.5136, -0.2297] | 1.000000 |

Intervals use 10,000 composition bootstrap resamples. Superiority uses all 262,144 paired composition label swaps under the exchangeable-label null, with Holm correction. The earlier bootstrap-tail fraction is not reused as a null-test p-value. [Method reference](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.permutation_test.html).

## Duration, failures and operating evidence

Duration diagnostics condition on matched pitch/onset notes; full sparse confusion matrices and majority-baseline macro-F1 are in report.json. Headline scores retain all failed/unmatched notes.

### homr_page

Duration balanced accuracy **0.5775**, macro-F1 **0.5218**, majority baseline **0.4741**; single-class predictor: **False**.

Valid-output OMR-NED 0.3510 (58 pages); complete failure penalties: True; scoring errors: 0. Missing/extra notes: 14903/14534. Typed failures: {'HOMR_OUTPUT_MISSING:conversion': 1}.

Page latency median/p95 **20.61/20.64 s**; cold workers: 59 (median 20.61 s). Full session: **52.5 min** including scoring. System RAM observed maximum **71.9%** (inference 71.9%, scoring 68.9%); device-wide VRAM **1569 MiB**. Admission/pressure RAM policy **75%**.

Frozen practical-limit checks: {'latency': True, 'process_tree_ram': True, 'device_wide_vram': True, 'observed_unattended_screen': True}. These use process-tree RAM and device-wide VRAM; the separate system-RAM admission limit does not change the frozen 75% process-memory eligibility rule. Timing against the historical control is descriptive because the admission policies differ.

### fine_tuned_homr

Duration balanced accuracy **0.6143**, macro-F1 **0.5480**, majority baseline **0.4279**; single-class predictor: **False**.

Valid-output OMR-NED 0.3645 (59 pages); complete failure penalties: True; scoring errors: 0. Missing/extra notes: 15434/15436. Typed failures: {}.

Page latency median/p95 **25.61/30.61 s**; cold workers: 59 (median 25.61 s). Full session: **61.7 min** including scoring. System RAM observed maximum **67.7%** (inference 67.7%, scoring 65.5%); device-wide VRAM **1572 MiB**. Admission/pressure RAM policy **90%**.

Frozen practical-limit checks: {'latency': True, 'process_tree_ram': True, 'device_wide_vram': True, 'observed_unattended_screen': True}. These use process-tree RAM and device-wide VRAM; the separate system-RAM admission limit does not change the frozen 75% process-memory eligibility rule. Timing against the historical control is descriptive because the admission policies differ.

### homr_455

Duration balanced accuracy **0.6228**, macro-F1 **0.5688**, majority baseline **0.3989**; single-class predictor: **False**.

Valid-output OMR-NED 0.3745 (58 pages); complete failure penalties: True; scoring errors: 0. Missing/extra notes: 15424/15012. Typed failures: {'HOMR_OUTPUT_MISSING:conversion': 1}.

Page latency median/p95 **25.61/30.61 s**; cold workers: 59 (median 25.61 s). Full session: **61.1 min** including scoring. System RAM observed maximum **70.9%** (inference 69.5%, scoring 70.9%); device-wide VRAM **1569 MiB**. Admission/pressure RAM policy **90%**.

Frozen practical-limit checks: {'latency': True, 'process_tree_ram': True, 'device_wide_vram': True, 'observed_unattended_screen': True}. These use process-tree RAM and device-wide VRAM; the separate system-RAM admission limit does not change the frozen 75% process-memory eligibility rule. Timing against the historical control is descriptive because the admission policies differ.

### audiveris_page

Duration balanced accuracy **0.3880**, macro-F1 **0.3521**, majority baseline **0.4224**; single-class predictor: **False**.

Valid-output OMR-NED 0.4451 (51 pages); complete failure penalties: True; scoring errors: 0. Missing/extra notes: 20159/17089. Typed failures: {'AUDIVERIS_FAILED:recognition': 5, 'AUDIVERIS_OUTPUT_INVALID:artifact_capture': 3}.

Page latency median/p95 **40.56/45.58 s**; cold workers: 59 (median 40.56 s). Full session: **52.0 min** including scoring. System RAM observed maximum **76.9%** (inference 76.9%, scoring 72.3%); device-wide VRAM **0 MiB**. Admission/pressure RAM policy **90%**.

Frozen practical-limit checks: {'latency': False, 'process_tree_ram': True, 'device_wide_vram': True, 'observed_unattended_screen': True}. These use process-tree RAM and device-wide VRAM; the separate system-RAM admission limit does not change the frozen 75% process-memory eligibility rule. Timing against the historical control is descriptive because the admission policies differ.

### zeus_page

Duration balanced accuracy **0.2340**, macro-F1 **0.1650**, majority baseline **0.4437**; single-class predictor: **False**.

Valid-output OMR-NED 0.8069 (59 pages); complete failure penalties: True; scoring errors: 0. Missing/extra notes: 21375/23547. Typed failures: {}.

Page latency median/p95 **70.58/71.19 s**; cold workers: 59 (median 70.58 s). Full session: **116.9 min** including scoring. System RAM observed maximum **94.8%** (inference 69.7%, scoring 94.8%); device-wide VRAM **1129 MiB**. Admission/pressure RAM policy **90%**.

Frozen practical-limit checks: {'latency': False, 'process_tree_ram': True, 'device_wide_vram': True, 'observed_unattended_screen': False}. These use process-tree RAM and device-wide VRAM; the separate system-RAM admission limit does not change the frozen 75% process-memory eligibility rule. Timing against the historical control is descriptive because the admission policies differ.

## Feature breakdowns

Subset F1 remains composition-macro; sparse subsets are descriptive.

| Feature | Value | Pages | Candidate | Primary F1 |
| --- | --- | ---: | --- | ---: |
| cross_staff | unknown | 59 | homr_page | 0.4061 |
| density_notes_per_quarter | ge4 | 37 | homr_page | 0.2740 |
| density_notes_per_quarter | lt4 | 22 | homr_page | 0.4978 |
| document_measure_count | gt32 | 16 | homr_page | 0.2906 |
| document_measure_count | le32 | 43 | homr_page | 0.4118 |
| has_independent_voices | False | 14 | homr_page | 0.4879 |
| has_independent_voices | True | 45 | homr_page | 0.3997 |
| has_meter_changes | False | 58 | homr_page | 0.4098 |
| has_meter_changes | True | 1 | homr_page | 0.0791 |
| has_repeats | False | 35 | homr_page | 0.4429 |
| has_repeats | True | 24 | homr_page | 0.4036 |
| has_ties | True | 59 | homr_page | 0.4061 |
| has_tuplets | False | 40 | homr_page | 0.4545 |
| has_tuplets | True | 19 | homr_page | 0.2770 |
| cross_staff | unknown | 59 | fine_tuned_homr | 0.3844 |
| density_notes_per_quarter | ge4 | 37 | fine_tuned_homr | 0.1986 |
| density_notes_per_quarter | lt4 | 22 | fine_tuned_homr | 0.5518 |
| document_measure_count | gt32 | 16 | fine_tuned_homr | 0.3329 |
| document_measure_count | le32 | 43 | fine_tuned_homr | 0.4077 |
| has_independent_voices | False | 14 | fine_tuned_homr | 0.3760 |
| has_independent_voices | True | 45 | fine_tuned_homr | 0.4406 |
| has_meter_changes | False | 58 | fine_tuned_homr | 0.3887 |
| has_meter_changes | True | 1 | fine_tuned_homr | 0.0791 |
| has_repeats | False | 35 | fine_tuned_homr | 0.4063 |
| has_repeats | True | 24 | fine_tuned_homr | 0.4195 |
| has_ties | True | 59 | fine_tuned_homr | 0.3844 |
| has_tuplets | False | 40 | fine_tuned_homr | 0.4741 |
| has_tuplets | True | 19 | fine_tuned_homr | 0.3132 |
| cross_staff | unknown | 59 | homr_455 | 0.2857 |
| density_notes_per_quarter | ge4 | 37 | homr_455 | 0.2101 |
| density_notes_per_quarter | lt4 | 22 | homr_455 | 0.3391 |
| document_measure_count | gt32 | 16 | homr_455 | 0.3385 |
| document_measure_count | le32 | 43 | homr_455 | 0.2743 |
| has_independent_voices | False | 14 | homr_455 | 0.3220 |
| has_independent_voices | True | 45 | homr_455 | 0.3421 |
| has_meter_changes | False | 58 | homr_455 | 0.2908 |
| has_meter_changes | True | 1 | homr_455 | 0.0791 |
| has_repeats | False | 35 | homr_455 | 0.3762 |
| has_repeats | True | 24 | homr_455 | 0.2495 |
| has_ties | True | 59 | homr_455 | 0.2857 |
| has_tuplets | False | 40 | homr_455 | 0.3200 |
| has_tuplets | True | 19 | homr_455 | 0.1842 |
| cross_staff | unknown | 59 | audiveris_page | 0.0986 |
| density_notes_per_quarter | ge4 | 37 | audiveris_page | 0.0643 |
| density_notes_per_quarter | lt4 | 22 | audiveris_page | 0.1296 |
| document_measure_count | gt32 | 16 | audiveris_page | 0.0708 |
| document_measure_count | le32 | 43 | audiveris_page | 0.1045 |
| has_independent_voices | False | 14 | audiveris_page | 0.0234 |
| has_independent_voices | True | 45 | audiveris_page | 0.1171 |
| has_meter_changes | False | 58 | audiveris_page | 0.1005 |
| has_meter_changes | True | 1 | audiveris_page | 0.0499 |
| has_repeats | False | 35 | audiveris_page | 0.1121 |
| has_repeats | True | 24 | audiveris_page | 0.0695 |
| has_ties | True | 59 | audiveris_page | 0.0986 |
| has_tuplets | False | 40 | audiveris_page | 0.1195 |
| has_tuplets | True | 19 | audiveris_page | 0.0744 |
| cross_staff | unknown | 59 | zeus_page | 0.0228 |
| density_notes_per_quarter | ge4 | 37 | zeus_page | 0.0247 |
| density_notes_per_quarter | lt4 | 22 | zeus_page | 0.0161 |
| document_measure_count | gt32 | 16 | zeus_page | 0.0162 |
| document_measure_count | le32 | 43 | zeus_page | 0.0269 |
| has_independent_voices | False | 14 | zeus_page | 0.0128 |
| has_independent_voices | True | 45 | zeus_page | 0.0279 |
| has_meter_changes | False | 58 | zeus_page | 0.0231 |
| has_meter_changes | True | 1 | zeus_page | 0.0000 |
| has_repeats | False | 35 | zeus_page | 0.0216 |
| has_repeats | True | 24 | zeus_page | 0.0250 |
| has_ties | True | 59 | zeus_page | 0.0228 |
| has_tuplets | False | 40 | zeus_page | 0.0257 |
| has_tuplets | True | 19 | zeus_page | 0.0209 |

## Decision boundary

Descriptive primary-F1 leader: **homr_page**. Keep the installed shipped engine; no production replacement from this screen.

- **fine_tuned_homr:** No accuracy-led confirmation priority over shipped HOMR from this screen.
- **homr_455:** No accuracy-led confirmation priority over shipped HOMR from this screen.
- **audiveris_page:** No accuracy-led confirmation priority over shipped HOMR from this screen; current practical-limit checks fail.
- **zeus_page:** No accuracy-led confirmation priority over shipped HOMR from this screen; current practical-limit checks fail.

Provisional untouched-remainder estimates (343 pages per candidate, inference plus scoring):

- **homr_page:** 5.1 hours, at least 2 bounded sessions. Same-PC screen throughput is an estimate, not a scheduled job.
- **fine_tuned_homr:** 6.0 hours, at least 2 bounded sessions. Same-PC screen throughput is an estimate, not a scheduled job.
- **homr_455:** 5.9 hours, at least 2 bounded sessions. Same-PC screen throughput is an estimate, not a scheduled job.
- **audiveris_page:** 5.0 hours, at least 2 bounded sessions. Same-PC screen throughput is an estimate, not a scheduled job.
- **zeus_page:** 11.3 hours, at least 3 bounded sessions. Same-PC screen throughput is an estimate, not a scheduled job.

The incompatible historical 455 configuration is excluded. Training overlap for the fine-tune and 455 remains unknown. Cross-staff coverage is unknown; no cross-staff accuracy claim follows.

The complete duration confusion matrices, per-composition differences, failed-page IDs, source/result/score hashes, and runtime estimates are retained in [report.json](report.json). No predictions were aligned or shifted, repeats were not expanded, and sounding ties were merged under the frozen scorer.

All five priority candidates are included. Canonical Stage 3 is complete. Stop for a separate confirmation decision; no confirmation, training or production promotion is authorized.

CPU v5 pins fully readable inventory; historical inventory omitted 33 metadata entries. Existing versions, sources, models, parser and scoring contracts match; no historical rewrite or dependency installation occurred.

Neutral CPU recognizer with existing GPU HOMR detector; direct app extractor is excluded.

Outcome counts retain successful empty outputs separately; typed empty/invalid/timeout counts use the saved engine error codes. Generic failures retain their original stage/code.

- **homr_page:** {'completed': 59, 'succeeded': 58, 'failed': 1, 'successful_empty_output': 0, 'typed_empty_output': 0, 'typed_invalid_output': 0, 'typed_timeout': 0, 'omr_ned_scoring_error': 0}.

- **fine_tuned_homr:** {'completed': 59, 'succeeded': 59, 'failed': 0, 'successful_empty_output': 0, 'typed_empty_output': 0, 'typed_invalid_output': 0, 'typed_timeout': 0, 'omr_ned_scoring_error': 0}.

- **homr_455:** {'completed': 59, 'succeeded': 58, 'failed': 1, 'successful_empty_output': 0, 'typed_empty_output': 0, 'typed_invalid_output': 0, 'typed_timeout': 0, 'omr_ned_scoring_error': 0}.

- **audiveris_page:** {'completed': 59, 'succeeded': 51, 'failed': 8, 'successful_empty_output': 0, 'typed_empty_output': 0, 'typed_invalid_output': 3, 'typed_timeout': 0, 'omr_ned_scoring_error': 0}.

- **zeus_page:** {'completed': 59, 'succeeded': 59, 'failed': 0, 'successful_empty_output': 0, 'typed_empty_output': 0, 'typed_invalid_output': 0, 'typed_timeout': 0, 'omr_ned_scoring_error': 0}.

Deferred configurations: qwen: current complete-page readiness failed; rokot: bounded development remedy deferred; legato: recognition runtime unavailable; musvit: verified decoder/checkpoint unavailable; homr_465_multi_voice: PR #156 merged and weights published; local matching source/weights/vocabulary/decoder and development admission remain unverified; homr_combined: compatibility unverified.
