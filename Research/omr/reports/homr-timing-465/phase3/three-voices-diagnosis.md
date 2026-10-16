# three_voices: false A5 begins in raw recognition

Owner: [MAIN_PLAN.md](../../../../../plans/MAIN_PLAN.md), Phase 3, 2026-10-08.
Cached candidate: source `33baa326900faa12702df8c4bdcbea034a3d6a34`, model 465
FP16, native no-title profile. No new inference or modified reference.

The authoritative image contains seven notes. The candidate emits those notes
plus A5 (MIDI 81) at beat 0 for four beats. That extra event is already present
in raw decoder output. Cleanup, export and production normalization preserve it.
This is a demonstrated recognition error; the initiating internal model or
detection mechanism is not established.

| Stage | Demonstrated observation | Evidence |
| --- | --- | --- |
| Source | One staff: C5 whole note, E4/F4 half notes, G3/A3/B3/C4 quarter notes; no A5 | [Authoritative image](../../../data/polyrhythm/three_voices.png), [source XML](../../../data/polyrhythm/three_voices.musicxml) |
| Staff representation | Saved decoder crop retains the seven printed noteheads; no printed A5 is visible | [Decoder input](../phase2/development/generated-three_voices/input_staff-0_input.jpg), [span debug](../phase2/development/generated-three_voices/input_staff-0_debug_span_points.png) |
| Raw decoding | `note_1 A5 _ _ _ upper` precedes chorded C5/E4/G3 | [Retained tokens](../phase2/development/generated-three_voices/tokens.json) |
| Cleanup | Same musical tokens, with only the final `newline` added to exporter input | Same token capture and [text](../phase2/development/generated-three_voices/input.txt) |
| Native export | Eight XML notes, A5 onset 0/duration 4; divisions 1, measure span 4 | [Frozen XML](../phase2/development/generated-three_voices/input.musicxml), [exact trace](downstream-traces.json) |
| Normalization | Same pitch/onset/duration multiset, staff and allocated voices retained; no added event | [Frozen timed events](../phase2/development/generated-three_voices/timed-events.json), [reproduced trace](downstream-traces.json) |
| Downstream | Actual published Bridge in app interpreter returns matching JSON; research C# cache/controller preserve eight notes | [Playback result](playback-results-repaired/candidate-generated-three_voices.json), [MIDI/controller checks](playback-results-repaired/results.json) |

The seven intended events remain: C5 `(0,4)`, E4 `(0,2)`, F4 `(2,2)` and
G3/A3/B3/C4 `(0,1)/(1,1)/(2,1)/(3,1)`. Only A5 `(0,4)` is extra.
The frozen primary F1 remains **0.9333333333**, versus **1.0** for the Phase 2
control. No score was recomputed or replaced.

`upper2` is another voice position on the existing staff. It is not a third
staff or a guarantee of one immutable MusicXML voice number. Native 465 rebalance
allocates non-overlapping rhythmic layers per staff; here the C5/A5 chord uses
voice 3, half notes voice 2 and quarter notes voice 1, all on staff 1.
The separate four-position fixture verifies both `upper2` and `lower2` through
native export, actual Bridge conversion and MIDI/playback: two staves, two voices
on each. See [runtime/playback evidence](runtime-playback.md).

Fixed retained tokens replay to the same musical XML in both existing interpreters;
only absent attention engraving coordinates are excluded from that comparison.
No evidence supports a missing #171/#178 behavior or a normalizer-created A5.
Attention error, duplicated whole-note recognition or other internal decoding
behavior are hypotheses. The cache does not identify their initiating cause.

No repair is justified for this case. Dropping A5 by range, chord shape or known
reference would silently remove valid music elsewhere. This bounded regression
remains a recognition qualification for a future trial decision.
