# Phase 2 development review

Owner: [MAIN_PLAN.md](../../../../../plans/MAIN_PLAN.md),
`2026-10-06-homr-timing-465`, Phase 2 only. Captures and analysis complete;
the candidate configuration is frozen without development or comparison tuning.
This review is diagnostic evidence, not a new repair work order.

All 32 native captures completed: 12 authoritative generated controls and 20
first-page OpenScore diagnostics. OpenScore has no numerical accuracy scores;
the Phase 1 page-boundary, repeat, training-overlap and literal-reference
qualifications remain. Source/model/import/provider identities and input hashes
are recorded in each receipt. Crops, positions, decoder tokens, cleaned exporter
inputs, XML and production-normalized timed notes are retained.

Generated primary F1 is a descriptive item mean, not a corpus ranking:

| Generated control | Phase 1 shipped | Pinned 465 |
| --- | ---: | ---: |
| baseline-piano-001 | 1.0000 | 1.0000 |
| homophonic | 1.0000 | 1.0000 |
| offset_entry | 0.4286 | 1.0000 |
| quintuplet_vs_duple | 0.3750 | 0.4706 |
| same_position_sustain | 0.0000 | 0.0000 |
| septuplet_vs_duple | 0.0909 | 0.0909 |
| syncopation | 0.1250 | 0.1250 |
| three_voices | 1.0000 | 0.9333 |
| tie_across_barline | 1.0000 | 1.0000 |
| triplet_vs_duple | 0.2000 | 1.0000 |
| triplet_vs_quadruple | 0.2857 | 0.5714 |
| tuplet_aligned | 1.0000 | 0.1250 |

The candidate mean is 0.6096882692. Two measures become exact (offset_entry,
triplet_vs_duple), and two previously exact measures regress (three_voices,
tuplet_aligned). These are explicit local harms, not evidence of a supported
overall gain. The three_voices output contains one extra MIDI pitch 81 event
at onset 0 with duration 4. The aligned-tuplet control keeps 24 notes but has
incorrect durations/onsets: raw and cleaned tokens pair upper `note_12` with
upper2 `note_8`, whereas both reference voices use 1/3-beat durations.
The exported lower voice has 1/2-beat durations and the downstream timeline
contains compressed/shifted onsets. The duration discrepancy is already present
in decoded tokens; this does not identify a weight-only cause or prove every
onset discrepancy originates there. No source/exporter repair was attempted.

Conditional duration diagnostics over 105 exact pitch/onset pairs: majority
baseline 0.6095238095, balanced accuracy 0.6944444444, macro-F1 0.6966821700.
Multiple duration classes are predicted. The full ordered confusion matrix is
in [development-analysis.json](development-analysis.json). Duration diagnostics
do not replace failure-penalized transcription F1.

The installed production normalizer is used unchanged, including its known
independent-voice tie limitation. Physical audio calibration, human correction
time and production promotion are not evaluated. Successful serialization and
compatibility do not erase the musical regressions above.

Acceptance: usable native outputs and reproducible diagnostic/scored development
evidence support the requested observed-screen comparison. They do not establish
the candidate as an improvement or authorize Phase 3/4 or installed-app changes.
