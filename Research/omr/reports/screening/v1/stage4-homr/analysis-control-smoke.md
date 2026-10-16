# Corrected HOMR-only Stage 4 report

59 frozen pages in 18 complete compositions.

| Candidate | Pitch/onset/duration F1 | Onset F1 | Pitch F1 | Failures | Penalized OMR-NED |
| --- | ---: | ---: | ---: | ---: | ---: |
| homr_page | 0.4061 | 0.4316 | 0.9701 | 1/59 | 0.3620 |

## Paired composition evidence

| Comparison | Primary F1 difference | 95% bootstrap interval | Holm-adjusted superiority p |
| --- | ---: | ---: | ---: |

Intervals use 10,000 composition bootstrap resamples. Superiority uses all 262,144 paired composition label swaps under the exchangeable-label null, with Holm correction. The earlier bootstrap-tail fraction is not reused as a null-test p-value. [Method reference](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.permutation_test.html).

## Duration, failures and operating evidence

### homr_page

Duration balanced accuracy **0.5775**, macro-F1 **0.5218**, majority baseline **0.4741**; single-class predictor: **False**.

Valid-output OMR-NED 0.3510 (58 pages); complete failure penalties: True; scoring errors: 0. Missing/extra notes: 14903/14534. Typed failures: {'HOMR_OUTPUT_MISSING:conversion': 1}.

Page latency median/p95 **20.61/20.64 s**; cold workers: 59 (median 20.61 s). Full session: **52.5 min** including scoring. System RAM observed maximum **71.9%**; device-wide VRAM **1569 MiB**. Admission/pressure RAM policy **75%**.

Frozen practical-limit checks: {'latency': True, 'process_tree_ram': True, 'device_wide_vram': True, 'observed_unattended_screen': True}. These use process-tree RAM and device-wide VRAM; the separate system-RAM admission limit does not change the frozen 75% process-memory eligibility rule. Timing against the historical control is descriptive because the admission policies differ.

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

## Decision boundary

Descriptive primary-F1 leader: **homr_page**. Keep the installed shipped engine; no production replacement from this screen.


Provisional untouched-remainder estimates (343 pages per candidate, inference plus scoring):

- **homr_page:** 5.1 hours, at least 2 bounded sessions. Same-PC screen throughput is an estimate, not a scheduled job.

The incompatible historical 455 configuration is excluded. Training overlap for the fine-tune and 455 remains unknown. Cross-staff coverage is unknown; no cross-staff accuracy claim follows.

The complete duration confusion matrices, per-composition differences, failed-page IDs, source/result/score hashes, and runtime estimates are retained in [report.json](report.json). No predictions were aligned or shifted, repeats were not expanded, and sounding ties were merged under the frozen scorer.

This is the HOMR-only decision input. Audiveris and Zeus are deferred; the consolidated engine decision remains pending. No confirmation run or production promotion is authorized by this report.
