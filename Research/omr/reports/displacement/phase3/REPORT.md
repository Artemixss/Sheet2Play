# Displacement Phase 3: blind correction on the research path

Plan: [MAIN_PLAN.md](../../../../../plans/MAIN_PLAN.md), Phase 3, authorized 2026-10-17. Research path
only; no shipped code changed. HOMR exporter source fixes were set aside at the user's request.

## Result: not accepted; the replan trigger fired

The frozen correction raises onset F1 on the held-out test set on both engines, with intervals
well clear of zero, but it **systematically harms scores with many meter changes**, and on 465
one near-correct score loses 0.55. On the plan's own terms that is not an accept, and it is a
replan ("harms a musical feature systematically").

| Test set (40 scores, scored once) | 465 | 426 |
|---|---|---|
| Onset F1, control → corrected | 0.461 → **0.618** | 0.422 → **0.553** |
| Paired gain, 95% interval | **+0.158** [0.072, 0.252], p 0.0005 | **+0.131** [0.054, 0.212], p 0.0005 |
| Pitch+onset+duration F1 | 0.440 → 0.597 | 0.398 → 0.524 |
| Pitch F1 change (limit −0.005) | 0.000 | 0.000 |
| Scores better / worse | 21 / 8 | 26 / 5 |
| Near-correct worst change (limit −0.01) | **−0.546** (5052787) | 0.000 |
| Library XML direction check | not available | not available |

| Test group | 465 mean (better/worse) | 426 mean (better/worse) |
|---|---|---|
| single meter (34–35 scores) | **+0.205** (20/5, worst −0.052) | **+0.172** (24/2) |
| with tuplets (16) | +0.179 (12/4) | +0.252 (16/0) |
| more than five time signatures (4) | **−0.164** (1/3, worst −0.546) | **−0.201** (1/3) |

The development set showed the same split (6202270, a 2/4–3/4–3/8 song, 0.874 → 0.530 on 465),
so the test confirms a known weakness rather than revealing a new one.

## The frozen correction

[`displacement_correct.py`](../../../displacement_correct.py), variant **anchor-holes**, frozen
before the test run in commit `a0c6bcc` ([freeze.json](freeze.json), source SHA-256
`e06208b1…`). For each page of the engine's own MusicXML, both staves of a part together:

- a measure in which some voice leaves a hole between two of its notes (the lost `<backup>`
  Phase 2 found) advances by its bar length, HOMR's computed page meter;
- every other measure keeps its decoded length, and an opening pickup on page one keeps its
  own;
- notes keep their place inside their measure, and pages are stitched as the app stitches them.

It needs no labels or inference, and its control reproduces the app's payload note for note on
every recognition.

**Why it fails on meter changes:** the bar it anchors to is HOMR's page meter, which the
exporter computes as the page's median decoded measure length. On a page that really changes
meter, a hole-marked measure in the minority meter is forced to the majority's length. Notes
inside correctly read secondary voices can also leave holes, so correct measures get anchored.

## Development (40 scores), what was tried

| Variant (dev) | 465 gain | 426 gain | Near-correct worst (465 / 426) | Verdict |
|---|---|---|---|---|
| anchor: every measure to the page meter (plan's C2) | +0.168 | +0.174 | −0.39 / −0.38 | breaks correct meter changes |
| anchor-holes (frozen) | +0.107 | +0.116 | 0.00 / 0.00 | best that passed every dev guard |
| anchor-holes, local meter ±3 / ±6 | +0.118 / +0.125 | +0.099 / +0.108 | −0.40 / 0.00 at ±3 | not clearly better, more complex |
| keep lengths both staves agree on | +0.004 | +0.001 | 0 | staves share one MusicXML cursor, so they always agree |
| keep recurring or run lengths | +0.04 to +0.07 | +0.05 to +0.06 | small | errors recur too |
| anchor only over-long measures | +0.087 | +0.137 | −0.03 / 0 | misses underflows, still breaks meter changes |
| split pages at HOMR's time-signature marks | +0.170 | +0.122 | −0.39 | 465 rarely marks them |
| pack voices to close holes (the layout fix itself) | −0.13 to +0.08 | −0.07 to +0.10 | up to −0.83 | moves onsets that were right |

The plan's **C1** (port PR #146 re-timing to the current exporter) needs 465's tokens, which
the in-process engine never logged, so it could not be run on cached recognitions; it would
need fresh inference, which was not done without approval.

## What this means

- Re-anchoring measure lengths is worth about **+0.16 onset F1 on single-meter music** with both
  engines, measured on held-out scores. That is the bulk of the library.
- Its blind spot is meter changes, because the only meter it knows is HOMR's page median.
- The layout fault itself (notes placed wrongly inside a measure) is still unrepaired: packing
  voices from the MusicXML alone moved correct notes. It probably needs either the exporter fix
  set aside here, or note positions from the page (465 writes `imgpos` per note).

## Limits

- Dev and test are Lieder piano parts, which both engines saw in training; absolute F1 is
  optimistic, the paired comparison less so.
- The test set is now spent for this plan. Any revised variant needs a fresh held-out set.
- Four test scores carry the meter-change finding; the dev set had the same pattern.

## Reproduce

```
Bridge\.venv-homr-gpu\Scripts\python.exe -I -B Research\omr\displacement_correct.py           (dev)
Bridge\.venv-homr-gpu\Scripts\python.exe -I -B Research\omr\displacement_correct.py --test    (refuses: already scored)
```

Results: [development.json](development.json), [test.json](test.json). Tests:
`Research/omr/tests/test_displacement_correct.py`.
