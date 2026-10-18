# Remaining timing loss after the shipped timing fix

**Plan ID:** `2026-10-18-remaining-timing-loss`
**Status:** Requested by the user on 2026-10-18 ("complete the remaining timing losses"),
after the [displacement plan](MAIN_PLAN.md) shipped its correction behind the off-by-default
**TIMING FIX** switch. Phases 1-2 are done; Phase 3 scored the frozen candidate once on
2026-10-18 (gain on both engines, one near-correct failure, so not accepted as
pre-registered) and waits on the user's decision. The
[handoff](../Research/omr/reports/timing/handoff.md) records state, evidence and the next action.

## Why

With the fix on, 465 reaches 0.55 onset F1 on the 152 engraved scores it recognised. The
[residual map](../Research/omr/reports/timing/phase1/residual.json) (`timing_residual.py`)
splits what is left with oracles fitted to the exact labels, so these are ceilings:

| | 465 | 426 |
| --- | --- | --- |
| Timing fix (as shipped) | 0.552 | 0.501 |
| Every bar starts where the label's does | 0.855 | 0.809 |
| And every note sits at its label onset within the bar | 0.946 | 0.935 |

Bars in the wrong place cost about 0.30, in-bar placement about 0.09, and wrong or missing
notes about 0.05. The largest bar family is **layout**: every note read with its true duration,
but the exported bar has the wrong length (606 bars on 465, 1,110 on 426). In-bar loss is
mostly wrong durations and missing or different tuplets, which run 480 targets; that is the
[upstream plan](2026-10-17-upstream-exporter-480.md)'s comparison, not this one.

## Phases

1. **Residual map.** Done 2026-10-18 on all four splits, as diagnosis only.
2. **Development repairs.** Blind variants of the timing fix on cached recognitions, tuned on
   dev and dev-b only (`timing_correct.py`, [reports/timing/phase2](../Research/omr/reports/timing/phase2/)).
   `displacement_correct.py` stays the frozen Phase 3 record.
3. **Held-out score, once.** Freeze one variant, then score it once on test and test-b from
   the cached recognitions. On those sets the residual map computed only oracle ceilings and
   mechanism counts; no variant ran there and no gate was chosen from them. Acceptance is the
   displacement plan's Phase 3 rule with the shipped fix as the control: an onset F1 gain whose
   paired interval excludes zero on each engine, pitch F1 down by no more than 0.005, and no
   near-correct score losing more than 0.01. A fresh engraved set (as `displacement_heldout.py`
   built test-b) is optional further confirmation and needs new HOMR inference.
4. **Ship.** Port an accepted variant to `Bridge/timing_correction.py`. Its cache key is its own
   hash, so only corrected songs re-run; the 465 identity is unchanged.

**Out of scope:** training, exporter source changes, and making the switch the default.
