# Phase 2 handoff — 2026-10-04

**Lifecycle update, 2026-10-07:** The [owning Zeus/shared repair plan](../../../../../plans/archive/2026-10-03-zeus-attribution-repair.superseded.md)
is superseded by [HOMR 465 and shipped-engine rhythm repairs](../../../../../plans/MAIN_PLAN.md).
This phase's evidence and acceptance limits remain unchanged. Phase 3 stays
qualified; unexecuted Phase 5/Rokot and further Zeus work are deferred.
Read the [new plan handoff](../../homr-timing-465/handoff.md) for current scope.
The dated next-action/authorization statements below are historical; this
documentation transition does not start a new execution phase.

**Plan directory:** [Plans/status index](../../../../../plans/README.md).

Authority: [MAIN_PLAN.md](../../../../../plans/archive/2026-10-03-zeus-attribution-repair.superseded.md), Phase 2 explicitly requested.
**Phase 2 complete**, including independent implementation/statistical acceptance.
[Closeout report and criterion ledger](closeout-20261004/REPORT.md) directly review
code, saved regression, preserved artifacts and independently recomputed statistics.
Latest turn metadata confirms recorded gpt-6.1-sol / medium configuration.

The user rebooted at20:56 local. C-only system-managed paging has18 GiB active
allocation; [post-reboot evidence](closeout-20261004/post-reboot.json) and guarded
preflight passed. Independent statistical audit passed in57.89 seconds, peak commit
37.82% / RAM59.97%, Git0. No inference, rescore or scoring-code change during closeout.
The initiating memory consumer and durable whole-system crash fix remain unresolved.
CPU containment remains mandatory; no automatic pressure retries or Git during recovery.
Phase3–5, tie normalization repairs, training, spending and promotion need a separate
request. Historical evaluation identities remain frozen.

## Completed work and evidence

Research-only additions:

- [timing.py](../../../src/sheet2play_omr/timing.py): symmetric rational reading,
  denominator limit 4096, exact fractions retained; decimal reconstruction limited to
  eight binary64 ULPs to preserve distinguishable timing errors.
- [corrected_scoring.py](../../../src/sheet2play_omr/corrected_scoring.py): separate
  cached scoring implementation and duration/chord/staff diagnostics.
- [timing_repair.py](../../../timing_repair.py): resumable identity-pinned scoring,
  failure accounting, composition aggregation, paired intervals and Holm statistics.
- [test_timing_repair.py](../../../tests/test_timing_repair.py): 16 passing focused
  cases including exact-divisions MusicXML and invalid/failure/resumption handling.

[Corrected report](corrected-v1/REPORT.md), [full data](corrected-v1/report.json):
295 outcomes, five candidates, 59 pages / 18 compositions each; ten failures retained.
Primary F1: shipped 0.4139483028, fine-tuned 0.3906830368, corrected 455 0.2861721148,
Audiveris 0.0988995658, Zeus 0.0237687636. No Holm-significant superiority claim.

Scoring identity:
`ed9e5b7e6f998b5787ae21dfc0b7f545c42fc0bc83b60fc717f002d6b34aa568`.
Report SHA-256:
`040ee6e7de58dec077ccdaa28961ee3e88a367a6dbc16931620e3df9a7cbb255`.

[Full regression](regression-scoped.log): 267 passed, 2 skipped, 9 subtests passed;
one expected unreadable-clef warning. [Focused log](focused.log): 16 passed.
[First post-crash audit](crash-audit-20261004-01/verification.json) and
[second post-crash audit](crash-audit-20261004-02/verification.json): all 295 scores and
1,257 declared artifacts verified, primary/secondary metrics independently recomputed.
The [job record](job-record.md) preserves commands, logs and prior checks.

## Reviewed deviation and limits

The exact-divisions fixture exposed an existing Bridge/music21 cross-system chord-tie
normalization defect with independent voices. The user chose: “Keep Phase 2 limited to
cached scoring; record and investigate the normalization defect in Phase 3.”
The [reproducer](cross-system-chord-tie.musicxml) and [original failure](regression.log)
remain. Current fixture verifies the six cached split segments, not corrected tie merging.
No Bridge, historical normalizer, adapter, reference generator or scorer was changed.

OMR-NED reuse verifies unchanged inputs, frozen source and dependency versions;
historical dependency inventories do not prove every installed package byte.
Staff coverage is notation-staff coverage, not validated hand coverage. No playback or
MIDI-preservation claim; no inference or causal Zeus verdict in this phase.

## Crash and current jobs

[Crash report](crash-investigation-20261004/REPORT.md): system commit exhausted to
99.878% around 00:21–00:24; desktop compositor and apps failed. Initiating consumer
unknown. Completed rescore/tests preceded the cascade; fresh integrity audit passed.
Portable D has an unresolved dirty exFAT flag; repo/interpreter/pagefile are on C.
The remote host was already offline before the first local crash.

[Recurrence report](crash-recurrence-20261004/REPORT.md): commit reached 99.913%
around 11:53–11:57, with an explicit paging-file warning and Wi-Fi-helper/WARP crashes.
No Phase 2 scoring/test/inference worker had started during continuation. A truncated
process listing showed at least 108 Git processes after exhaustion had already begun;
their initiating role, parentage and complete memory accounting are unverified.
The second bounded artifact audit passed without repeating scoring/tests. That guard
protected only its audit. Subsequent authorized safeguards use a separate CPU supervisor
and Windows Job Object; the frozen scoring runner and all cached artifacts stay unchanged.

Final safety checks:35 focused tests; full Bridge/research regression302 passed,
2 skipped,9 subtests, one expected clef warning. Supervisor45.375 seconds, peak commit
62.15% / RAM76.11%, Git0. [Evidence](safety-fix-20261004/regression-final/result.json),
[test log](safety-fix-20261004/regression-final/worker.log). Frozen report and all declared
scoring-source hashes passed. No repeated scoring or inference. All safety test workers
ended; no global worker lock remained. No unattended job or automation.
[Independent safeguards/paging review](safety-fix-20261004/REVIEW.md) accepted the final
code and directly inspected the configured policy. Original custom C sizes were saved
for rollback; no paging on the portable SSD. This does not establish a durable fix for
external app growth.

Use [guarded_execution.py](../../../guarded_execution.py) for every authorized CPU job:
aggregate Job committed-memory cap4 GiB/process cap16; admission reserves worker budget
plus2 GiB; sample commit/RAM/Git every0.5 seconds; stop at90% pressure, below2 GiB
headroom,8 Git processes/1 GiB aggregate Git private memory, or deadline14370 seconds.
Fail closed on missing measurements or failed assignment; retain lock on unconfirmed
cleanup. External apps/Git are observed only. This CPU control adds no VRAM protection;
existing RAM/VRAM safeguards remain intact. Do not start frozen runners/verifiers/tests
directly, weaken limits or automatically retry pressure failures. The source hashes and
resumable commands are saved separately from corrected-v1. No rescore is needed for review.

## Exact next action

Await an explicit Phase3 request; no Phase2 execution remains. Before any subsequently
authorized CPU job inspect resources, processes and locks and use guarded_execution.py.
Preserve the current scoring identity and all historical artifacts. If external growth
returns, hold execution and retain evidence; do not retry automatically or weaken limits.
The user-deferred tied-chord normalization reproducer belongs to Phase3.

Acceptance: all approved Phase2 cached-scoring criteria **met**, including independent
statistical review, full regression, integrity audits and post-reboot resource preflight.
[Detailed ledger](closeout-20261004/REPORT.md) distinguishes phase acceptance from
unverified crash cause, durable whole-system remedy and OS/portable-SSD integrity.
Actual tie merging, causal Zeus attribution and Rokot readiness are outside completed
Phase2. No live worker or unattended automation remains.
