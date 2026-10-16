# Phase 2 acceptance closeout — 2026-10-04

**Phase 2 complete within the approved cached-scoring scope.** Phases 3–5 remain
unauthorized. Direct source and saved-evidence review found no required scoring
correction. Historical artifacts and the corrected scoring identity remain unchanged.

Current turn metadata records `gpt-6.1-sol`, effort `medium`; this verifies the
client's recorded routing/configuration, not independent server attestation.

## Results

All candidates retain 59 pages / 18 compositions. Primary scores are composition-macro
pitch/onset/duration F1; failures retain zero transcription F1.

| Candidate | Historical F1 | Corrected F1 | Failures | Missing / extra notes | Historical runtime median / p95 seconds |
|---|---:|---:|---:|---:|---:|
| Shipped HOMR | 0.4060904651 | 0.4139483028 | 1 | 14658 / 14289 | 20.610 / 20.640 |
| Fine-tuned HOMR | 0.3844154166 | 0.3906830368 | 0 | 15247 / 15249 | 25.610 / 30.609 |
| HOMR 455 | 0.2856548208 | 0.2861721148 | 1 | 15414 / 15002 | 25.610 / 30.610 |
| Audiveris | 0.0986380314 | 0.0988995658 | 8 | 20152 / 17082 | 40.563 / 45.580 |
| Zeus | 0.0228105412 | 0.0237687636 | 0 | 21345 / 23517 | 70.578 / 71.192 |

[Frozen corrected report](../corrected-v1/REPORT.md) includes pitch/onset and pitch-only
F1. [Full report](../corrected-v1/report.json) contains duration matrices, baselines,
balanced accuracy, macro-F1, timeline/offset diagnostics, composition aggregates,
paired intervals, failures and runtime. Per-page scores contain chord completeness
and per-staff coverage. [Verified diagnostic totals](statistical-verification.json)
also expose missing/extra notes, chord counts and error-stage counts.

Duration classification is conditional on pitch/onset-matched notes in successful
outputs; failed pages contribute through transcription F1 and missing-note totals.
It is not end-to-end duration accuracy. No candidate has a degenerate single-class
duration predictor. Staff indices are notation labels, not validated hand annotations.
Chord completeness requires all reference pitches at an exact onset; extra pitches
are penalized separately. None of these diagnostics aligns or warps musical time.

Eight exact paired composition superiority tests and 10,000-resample intervals
were independently recomputed. Every Holm-adjusted p-value is 1. Shipped minus
fine-tuned F1 is 0.0232652660, 95% interval [-0.0410163143, 0.1005905813].
The screen supports no challenger-superiority claim; it does not establish equivalence.
Zeus's small correction does not establish the dominant cause of its poor local score.

## Acceptance ledger

| Criterion | Status | Evidence / limitation |
|---|---|---|
| Symmetric centralized rational reading, exact fractions retained | Met | Direct review of timing.py and corrected_scoring.py; denominator 4096 reconstruction only within eight binary64 ULPs |
| Genuine timing errors preserved; no onset tolerance/alignment/warping | Met | Exact matching implementation and 0.33334 distinguishing fixture |
| MusicXML divisions, tuplets, chords, independent voices, pickups, meter changes | Met | Direct fixture review; 16 focused cases passed |
| Cross-system ties | Met for approved cached scope | Fixture validates exact split segments; actual Bridge tie-merging defect explicitly deferred by user to Phase 3 |
| Missing systems, invalid output, failure accounting | Met | Focused fixtures plus all 295 cached outcomes including ten failures |
| Historical artifacts and Phase-1 contracts preserved; separate identity | Met | Two post-crash audits verified 1,257 declared artifacts; fresh audit verified nine scoring sources, 295 scores and report hash |
| Five-candidate primary/secondary scores and composition aggregates | Met | Independent counter recomputation in post-crash audits; fresh aggregate checks |
| Duration matrix/baselines/balanced accuracy/macro-F1 and full timing diagnostics | Met | Direct summary/pairing code review; independent dense matrix totals; conditional interpretation stated above |
| Missing/extra, chord/staff coverage, failures and runtime reported | Met | Full report/page scores and fresh verified diagnostic totals; staff is not a hand proxy |
| Paired intervals, exact tests and multiple-comparison statistics | Met | Independent audit: eight claims, 262,144 sign assignments each, 10,000 bootstrap resamples each, Holm adjustment |
| OMR-NED reuse on verified unchanged XML/implementation/version identities | Met within recorded provenance | Post-crash audit checks unchanged values/input hashes; historical inventory does not attest every dependency package byte |
| Complete research/Bridge regression after code changes | Met | Final saved run: 302 passed, two skipped, nine subtests; expected unreadable-clef warning; no scoring code change during closeout |
| Enforced CPU containment and post-reboot resume preflight | Met | Reviewed safeguards, 35 focused safety tests; active C-only 18 GiB paging; preflight and audit passed under supervisor |
| Initiating external memory consumer / durable whole-system crash remedy | Unverified | Commit exhaustion established; worker safeguards do not cap external applications |
| Whole OS, portable SSD and unrelated-file integrity | Unverified | Research artifacts verified; portable drive dirty flag and broader integrity remain unresolved |
| Correct tie merging / causal Zeus verdict / Rokot readiness / MIDI playback preservation | Unmet, outside Phase 2 | Separate Phase 3–5 work; no playback claim |

## Review and resource evidence

The reviewer inspected timing policy, cached scorer, runner, fixtures, note metrics,
duration pairing/aggregation, bootstrap, exact tests, Holm implementation and the
independent artifact verifier directly. This did not rely solely on the executor's
summary. No required implementation correction was found. Required interpretation
clarifications are recorded above. Additional model experiments are outside this phase.

[Independent audit source](audit_statistics.py), [result](statistical-verification.json),
[supervisor result](statistical-verification/result.json) and
[job record](job-record.md) preserve the command and evidence. Audit completed in
57.89 seconds, peak system commit 37.82% and physical RAM 59.97%, Git count zero.
It imported no scorer and performed no inference or rescore.

[Post-reboot evidence](post-reboot.json) verifies boot at 20:56 local and C-only
system-managed paging with 18,432 MiB active allocation.
[Resource preflight](resource-preflight/result.json) passed. Keep mandatory guarded
CPU execution, one worker, admission headroom, 90% pressure stops, four-hour session
limit, no Git during recovery and no automatic pressure retry. This is evidence of
safe completion of these bounded jobs, not proof the external crash cause is fixed.

Next: await an explicit Phase 3 request; retain the tied-chord reproducer and unresolved
provenance/crash limitations. No live worker or automation should remain at closeout.
