# Displacement correction: stop one measure's error from shifting the rest of the score

**Plan ID:** `2026-10-17-displacement-correction`
**Status:** Active. Written 2026-10-17. On the same day the user approved the plan
and authorized **Phase 1 only** ("approved do small 465 then start displacement phase 1").
Phases 2–4 each need their own request. Phase 1 baselines were recorded on 2026-10-17;
Phase 2 waits on the user's review. The predecessor
[465 integration plan](archive/2026-10-09-homr-465-app-integration.done.md) is archived
as done. The [handoff](../Research/omr/reports/displacement/handoff.md) records current
state and the next action.

## Why this, and what the evidence does and does not show

The app reads pitch well and places notes in time badly. On exact labels most of that
timing loss is **displacement**: the engine gains or loses beats somewhere, and every later
note inherits the shift. On OLiMPiC whole scores rebuilt with exact MusicXML, onset F1 is
0.5206 as measured and 0.7714 once each 16-quarter window is shifted by its own offset,
against a shuffled control of 0.1660; single systems lose far less (0.6607 to 0.7516). See
[FINDINGS](../Research/omr/reports/diagnosis/FINDINGS.md).

Limits that shape this plan:

- **The correction figures are oracles.** The offsets were fitted against the reference. They
  bound what a blind corrector could recover; they do not promise it.
- **The library has no verified truth.** Its references are MuseScore MIDI downloads, which
  show a pair is the same music but not that its onsets match the printed page. Library
  figures are suggestive only.
- **The 465 app path has no measure re-timing.** PR #146's re-timing was the larger part of
  426's +0.08 onset F1 gain (with PR #141), but the 465 runtime is unpatched upstream source,
  and 465 with re-timing was never tested.

## Constraints

Experimental changes stay opt-in and leave the shipped engine untouched until measured.
Substantive jobs use the [enforced supervisor](../Research/omr/reports/zeus-attribution/phase2/safety-fix-20261004/REPORT.md)
and separate GPU admission. Since 2026-10-17 it applies no per-worker memory cap by default
(user decision); the 85% RAM/commit stops and the system commit reserve remain. Private library files stay local and ignored. No training,
engine replacement or cloud spending. Corrections run on cached recognitions, so each engine
is inferred once per corpus and every variant is cheap post-processing.

## Phase 1 — Build the ruler

*Effort: standard. Defined tooling, checkable outputs.*

1. **Engraved exact set.** Extract the piano parts of the local CC0 OpenScore Lieder corpus
   and engrave them with MuseScore 4 through the project's own `build_dataset.py`. The
   source MusicXML is then exact truth, engraved by the program that produced the library's
   PDFs. Select multi-page scores across the library's range (2-12 pages), favouring
   independent voices and held notes under moving lines. Freeze a manifest with hashes, split
   into **development (about 40 scores)** for diagnosis and tuning and **test (about 40)** scored
   once. Keep the 11 generated polyrhythm cases and 20 rebuilt OLiMPiC scores as existing
   exact controls.
2. **The user's library check set.** The user downloads MusicXML from the same MuseScore
   score page as 6-10 library PDFs, preferring songs in the confirmed pairs. Accept a file
   only if its measure count and page breaks match the PDF and nearly every reference note
   appears in the current transcription. These stay local, are never used for tuning, and
   serve as the real-world direction check.
3. **Baseline.** Score shipped 465 and 426, uncorrected, on both sets: composition-macro
   pitch/onset/duration F1 with paired statistics, the oracle drift profile, and per-score
   drift shape.

**Accept when** both manifests are frozen with hashes, every library XML passes the match
check or is excluded with its reason, and the baselines are recorded.
**Replan if** Lieder piano parts prove much sparser than the library (notes per measure,
voices per staff); then propose a public-domain PDMX piano subset, which needs a download
the user approves.

**Result (2026-10-17): complete for the engraved set; library check set waits on the user.**
80 Lieder piano-only scores (dev 40, test 40) were frozen and captured with both shipped
engines. Pitch+onset+duration F1, 465 / 426: dev 0.330 / 0.297, test 0.440 / 0.398. The
paired 465 gain is not distinguishable from zero (dev +0.033 [−0.046, +0.116], test +0.043
[−0.057, +0.142]). Pitch F1 is 0.92–0.98. The oracle per-window offset lifts onset F1 by
about 0.34–0.39, against 0.06–0.07 for a shuffled control. The most common drift shape
is a single global offset. Lieder pages are denser than the library, so the replan
trigger did not fire. Both engines trained on Lieder, so absolute figures are optimistic.
Details are in the
[handoff](../Research/omr/reports/displacement/handoff.md).

## Phase 2 — Find where scores gain their beats

*Effort: high. Diagnosis and attribution.*

With exact labels, measure numbers align. For each development score, compare every measure's
decoded duration with the truth and the bar length, and attribute each change in cumulative
offset to a mechanism:

- overflow or underflow inside a measure (voices, polyrhythm, chord splits as in #150);
- a dropped or duplicated measure (#188); a measure-count check detects these;
- meter errors: computed versus recognized signature (#161), mixed meters (#167), pickups;
- tuplets, grace notes, and stitching at system and page boundaries.

**Deliverable:** a ledger of gained beats by mechanism, with share of total drift and at
least two verified examples per mechanism (page crop, tokens, MusicXML).
**Accept when** named mechanisms account for most of the gained beats on the development set.
This phase changes no code.

## Phase 3 — Blind correction on the research path

*Effort: high. Design choices with musical edge cases.*

Compare on the development set, against the uncorrected control:

- **C1, PR #146 re-timing ported to the current exporter**, with the guard the September work
  left open: leave a measure alone when its decoded length is already plausible. That
  targets the 18 of 100 canary systems the original re-timing pushed below span 1.00.
- **C2, barline re-anchoring in the normalizer:** each measure starts where the previous one
  ends at its bar length, and an over- or underfull measure is repaired inside its own
  bounds. Pickups, final bars, meter changes and repeat endings are handled explicitly. It
  is engine-agnostic, so it would carry to 480.
- **C1 + C2**, if Phase 2 shows they address different mechanisms.

Tune on development data only, then score the frozen test set once.

**Accept when** the selected variant improves onset F1 on the held-out test set over the
control, with a paired confidence interval excluding zero; pitch F1 does not drop by more
than 0.005; scores already near-correct (span 0.98-1.02, onset F1 0.9 or above) lose no
more than 0.01 each; and the library XML set moves in the same direction.
**Replan if** the best variant gains less than +0.03 onset F1, or harms a musical feature
(pickups, meter changes, tuplets) systematically.

## Phase 4 — Ship behind a visible setting

*Effort: standard. Defined release path. Needs separate authorization.*

Add the accepted correction to the app as a setting with a visible on-screen control, off by
default. Include the correction's identity in the cache key, so corrected and uncorrected
MIDI never share a cache entry. Pass the full release gate and verify the published EXE.
Make it the default only after the user reviews the test-set and library results.

## Out of scope

Training, run 480 adoption (the [separate upstream task](2026-10-17-upstream-exporter-480.md)),
pitch-level misreadings where the notes themselves are wrong, and the audio offset.
