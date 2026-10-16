# Shared timing repair — Phase 2

All 295 cached outcomes retained. Historical artifacts and scorer stay frozen.

| Candidate | Historical primary F1 | Corrected primary F1 | Pitch/onset F1 | Pitch F1 | Failures |
|---|---:|---:|---:|---:|---:|
| homr_page | 0.4060904651 | 0.4139483028 | 0.4374030143 | 0.9700843734 | 1 |
| fine_tuned_homr | 0.3844154166 | 0.3906830368 | 0.4148096566 | 0.9840732267 | 0 |
| homr_455 | 0.2856548208 | 0.2861721148 | 0.3066256143 | 0.9678189682 | 1 |
| audiveris_page | 0.0986380314 | 0.0988995658 | 0.1181234938 | 0.7568426895 | 8 |
| zeus_page | 0.0228105412 | 0.0237687636 | 0.0377419391 | 0.5763156234 | 0 |

Eight paired composition superiority claims use exact label swaps, 10,000 bootstrap resamples and Holm adjustment. Full intervals, p-values, sparse duration confusion matrices, majority baselines, balanced accuracy, macro-F1, missing/extra counts and runtime are in report.json.

Chord completeness and notation-staff recall are in each page score; staff is not a validated hand label.

OMR-NED is reused from verified score identities with unchanged XML inputs and frozen implementation/version pins. No new inference, playback, causal Zeus attribution, promotion or confirmation claim.

Holm-significant superiority claims: []. This is a bounded-screen correction, not a new promotion decision.
