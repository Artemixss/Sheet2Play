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

## Next action

Phase 3: score the frozen candidate once on test and test-b, from cached recognitions:

```
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/reports/timing/phase3/jobs/test-1 --max-seconds 3600 -- 'Bridge\.venv-homr-gpu\Scripts\python.exe' -I -B Research/omr/timing_correct.py --test
```

It writes `phase2/test.json` once and refuses if the code changed after freezing.
