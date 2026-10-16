# tuplet_aligned: representation loss, then inconsistent recognized durations

Owner: [MAIN_PLAN.md](../../../../../plans/MAIN_PLAN.md), Phase 3, 2026-10-08.
Use the same pinned native 465/no-title/FP16 cache as Phase 2. No new inference.

The earliest demonstrated representation error is loss of one of the two stacked
tuplet bracket rows between saved span debug and final decoder input. The earliest
demonstrated musical error is in raw tokens: lower C4/D4/E4 durations are half a
beat instead of one third. The later onset compression is already in native XML;
production normalization preserves that timing.

| Stage | Demonstrated observation | Evidence |
| --- | --- | --- |
| Source | Four aligned triplet groups in two voices on one staff: 24 notes, each duration 1/3 beat; onsets 0, 1/3, 2/3 through 11/3 | [Image](../../../data/polyrhythm/tuplet_aligned.png), [source XML](../../../data/polyrhythm/tuplet_aligned.musicxml) |
| Span debug | Both stacked bracket rows and their `3` markings are visible | [Saved intermediate](../phase2/development/generated-tuplet_aligned/input_staff-0_debug_span_points.png) |
| Decoder input | Only one bracket row remains; both rows of pitched noteheads remain visible | [Final crop](../phase2/development/generated-tuplet_aligned/input_staff-0_input.jpg) |
| Raw tokens/positions | Every upper note is `note_12 ... upper` (1/3 beat), every lower note is `note_8 ... upper2` (1/2 beat), grouped as chords | [Raw and cleaned tokens](../phase2/development/generated-tuplet_aligned/tokens.json) |
| Cleanup | Musical tokens are unchanged; final `newline` is added | Same capture and [text](../phase2/development/generated-tuplet_aligned/input.txt) |
| Export | Divisions 6; 24 notes; upper durations 1/3, lower durations 1/2; third group starts at 1/2 instead of 2/3; measure spans 5/2 instead of 4 | [Frozen XML](../phase2/development/generated-tuplet_aligned/input.musicxml), [exact measure/event trace](downstream-traces.json) |
| Normalization/playback | Literal and normalized event multiset matches exactly; app-interpreter JSON agrees; MIDI/controller reproduce the compressed timing | [Frozen events](../phase2/development/generated-tuplet_aligned/timed-events.json), [Bridge JSON](playback-results-repaired/candidate-generated-tuplet_aligned.json), [checks](playback-results-repaired/results.json) |

The source-to-crop loss is bounded by actual saved images. The reviewed
[staff preparation code](../../../.runtime/homr-465-upstream/source/homr/staff_parsing.py)
calculates a tight staff region, crops a larger region for dewarping, dewarps,
recrops to the tight region, removes black edge contours and centers the canvas.
The debug span image precedes those later transformations. No retained image
isolates which of dewarp, recrop or edge cleanup removes the bracket row.
Consequently, “the fixed four-unit margin is the cause” and “that bracket loss
causes these exact duration tokens” remain hypotheses, not demonstrated fixes.
The visible loss also does not establish a weight-only cause.

The native #171 scheduler explains the downstream clock without approximation.
It advances to the next sounding note end. In beats:

| Group | Clock | New note ends | Next clock |
| --- | --- | --- | --- |
| First | 0 | 1/3, 1/2 | 1/3 |
| Second | 1/3 | 2/3, 5/6; earlier lower note still ends at 1/2 | 1/2 |
| Third | 1/2 | 5/6, 1; next earlier end is 2/3 | 2/3 |

The remaining group starts are `5/6, 1, 7/6, 4/3, 3/2, 5/3, 11/6, 2`.
This is an exact consequence of inconsistent raw durations under the native
advance rule, not a newly introduced floating-point or normalizer error.
Correct equal-duration triplets and held-note controls pass. Replacing this
clock rule with the minimum newly emitted duration could break genuine staggered
or held-voice timing; no demonstrated general exporter repair supports that change.

All notes remain on staff 1. The interval rebalancer needs five rhythmic layers
for the overlapping recognized notes; voice number 5 here is still on staff 1,
not a fifth staff or a reliable persistent identity of `upper2`. The separate
four-position fixture confirms second voices on the existing two staves.

Frozen primary F1 stays **0.125**, versus **1.0** for control. Fixed-token export
replays identically in both interpreters. No crop widening, duration replacement,
exporter transplant or model adjustment was selected. A future crop experiment
needs separately retained intermediate images and fresh safeguarded admission;
it is not necessary to close Phase 3 with this recognition limitation documented.
