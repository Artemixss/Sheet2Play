# Remaining timing loss: handoff

**Owning plan:** [`2026-10-18-remaining-timing-loss`](../../../../plans/2026-10-18-remaining-timing-loss.md),
requested 2026-10-18 ("complete the remaining timing losses").

## Phase 1: residual map (done)

`timing_residual.py` over all 154 engraved scores; [residual.json](phase1/residual.json). With
the shipped fix 465 averages 0.552 onset F1; bars in place would give 0.855 and notes in place
0.946 (426: 0.501, 0.809, 0.935). The plan summarises the mechanisms.

## Phase 2: development (done)

`timing_correct.py` extends `displacement_correct.py`'s variant grammar without editing it.
`anchor-all-keepN` anchors every bar, not only bars with holes, unless N hole-free bars on the
page share its length. Plain anchoring had been tried in Phase 3 without the keep gate.
`timing_meter.py` grades each new decision against the label on dev and dev-b
(`phase2/anchor-ledger.json`, local): anchoring a bar longer than the meter is mostly right
(465: 60 fixes, 8 harms), a shorter one is not. Of the new decisions on bars shorter than the
meter whose voices all end together, 46 of 61 were real short bars; of those where HOMR
recognised a time signature, 21 of 23 were real. Two gates follow: `even` keeps a hole-free bar whose voices all end on its
length, and `time` keeps one that carries a recognised time signature.

[development.json](phase2/development.json), dev + dev-b, 60 scores, against the shipped fix:

| Variant | 465 gain | 95% | 426 gain | 95% | Worst drop (465 / 426) |
| --- | --- | --- | --- | --- | --- |
| `anchor-all-keep3` | +0.066 | +0.023, +0.113 | +0.058 | +0.003, +0.120 | −0.390 / −0.549 |
| `anchor-all-keep3-evenunder-time` | +0.076 | +0.039, +0.121 | +0.067 | +0.019, +0.124 | −0.042 / −0.364 |
| **`anchor-all-keep3-even-time`** | +0.059 | +0.026, +0.099 | +0.074 | +0.030, +0.130 | −0.048 / −0.040 |

All carry `fit+`. Pitch is unchanged. The frozen candidate is `fit+anchor-all-keep3-even-time`
([freeze.json](phase2/freeze.json), code hash `c3b6004f…` over `timing_correct.py`,
`displacement_correct.py` and `timing_meter.py`): the best gain whose worst single-score loss
stays small on both engines. Its one near-correct loss on dev is 5799023 on 465 (0.978 to
0.930), a real 4-beat bar on a page mixing 4, 5 and 6 beats; tuning further on single scores
was stopped there. The known one-bar meter change 5937814 still loses 0.672 against the raw
engine, under the shipped fix too.

## Phase 3: held-out score (2026-10-18, not accepted as pre-registered)

Scored once on test and test-b (94 scores) from cached recognitions, with `timing_correct.py
--test` under the supervisor (`phase3/jobs/test-1`, local); [test.json](phase2/test.json).
Against the shipped fix:

| | Shipped | Candidate | Gain | 95% | Better / worse | Worst |
| --- | --- | --- | --- | --- | --- | --- |
| 465 | 0.606 | 0.680 | +0.074 | +0.039, +0.113 | 27 / 4 | −0.045 |
| 426 | 0.545 | 0.588 | +0.042 | +0.017, +0.073 | 26 / 9 | −0.120 |

Pitch is unchanged. The gain holds in every subset: test, test-b, and test-b's meter-change and
single-meter strata, on both engines. The near-correct guard fails once: test-b 6222828, a
meter-change score, goes from 0.995 to 0.952 on 465 (27 near-correct scores on 465, 22 on 426;
no other loses). The largest gains are 5987667 on 465 (0.026 to 0.966) and 6518134 on both
engines (465: 0.097 to 0.866). No test score was inspected beyond these totals.

## Phase 4: shipped (2026-10-18)

The user accepted the candidate despite the near-correct failure ("accept it and ship it").
[Bridge/timing_correction.py](../../../../Bridge/timing_correction.py) now ports
`fit+anchor-all-keep3-even-time`, still behind the off-by-default **TIMING FIX** switch; no C#
change. Its SHA-256 keys the corrected cache, so only songs converted with the switch on re-run,
and no pinned 465 file changed.

- Shipped and research paths agree note for note on all 305 cached recognitions, with no page
  fallbacks (`displacement_ship_check.py`, now pointed at this freeze; `phase4/jobs/ship-check-1`).
- Tests: Bridge and research 451 passed, 2 skipped (`phase4/jobs/regression-1`; 2 new Bridge
  tests, 7 in `test_timing_correct.py`); `verify-release.ps1` passed every step, xunit 94 passed,
  and the published `dist/Bridge/timing_correction.py` matches the source.

- Library spot check (2026-10-18; per-song rows stay local in `data/library-timing/`): the
  published entry converted three library PDFs the user named. On the one with a confirmed
  MuseScore pair (11 pages), onset agreement with that MIDI rose from 0.045 to 0.693, pitch
  0.981 both, length 885.7 to 874.0 beats against the reference's 872.0; this is agreement with
  an imperfect reference, not accuracy. The user's complaint about its length (about seven
  minutes against four) is mostly tempo: the reference plays at 110-186 BPM and the app at its
  default 120. One of the three changed not at all (every page already decoded to whole bars).
  All sides were read from MIDI ticks: `evaluate_library.notes_from_midi` uses music21's import,
  which quantizes onsets and splits notes at bar lines (3,832 notes read as 4,725 here).

## Next action

None authorized. Making the switch the default still waits on the user's review.
