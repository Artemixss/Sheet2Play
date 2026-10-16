# Phase 3 handoff — 2026-10-04

**Lifecycle update, 2026-10-07:** The [owning Zeus/shared repair plan](../../../../../plans/archive/2026-10-03-zeus-attribution-repair.superseded.md)
is superseded by [HOMR 465 and shipped-engine rhythm repairs](../../../../../plans/MAIN_PLAN.md).
This phase's evidence and acceptance limits remain unchanged. Phase 3 stays
qualified; unexecuted Phase 5/Rokot and further Zeus work are deferred.
Read the [new plan handoff](../../homr-timing-465/handoff.md) for current scope.
The dated next-action/authorization statements below are historical; this
documentation transition does not start a new execution phase.

Owner: [MAIN_PLAN.md](../../../../../plans/archive/2026-10-03-zeus-attribution-repair.superseded.md), plan
`2026-10-03-zeus-attribution-repair`. User explicitly requested Phase 3 on 2026-10-04.
**Fixed Phase 3 execution and reporting complete on 2026-10-05; full acceptance incomplete.** Phases 1–2 remain complete.
**Lifecycle update, 2026-10-05:** The user subsequently requested bounded Phase 4,
now complete. Continue from the [Phase 4 handoff](../phase4/handoff.md) and
[acceptance ledger](../phase4/REPORT.md). Its current full regression resolves
the historical failures below; exact/provenance limits remain. Phase 5, training,
spending and promotion remain unauthorized. Dated Phase 3 evidence is preserved.

**Planner review, 2026-10-05:** [Gate decision and proposed Phase 4 sequence](../../../../../plans/reviews/2026-10-05-phase3-gate-review.md)
recommends a conditional transition: resolve validation prerequisites, then repair
the shared independent-voice tie defect before isolated crop/conversion experiments.
This is a review recommendation, not full Phase 3 acceptance or Phase 4 authorization.
The canonical plan owns the proposed sequence; the dated execution evidence below
is unchanged. The review's original authorization stop is superseded only by the
explicit subsequent Phase 4 request and completion recorded above.

## Current results and acceptance

Read the [report and criterion status](REPORT.md). All15 fixed inputs/25 crops/50
recipe outputs completed;30 stitched pages accepted by unchanged Bridge. Verdict
mixed causes: clipped/duplicate crops, padding-sensitive native decoding, malformed
native grammar/timing and hidden converter diagnostics, plus independently
demonstrated voice-interleaved chord-tie normalization. No universal quality claim.

75 focused fixtures pass. Final complete regression:328 passed,14 unchanged failures,
2 skipped,9 subtests passed. Twelve legacy tests are blocked before Git launch;
two strict freeze tests retain known33-entry metadata mismatches. Full green
regression remains unmet; no new skip/mock/xfail. [JUnit](resume-20261005-1746/regression-parser-trace-junit.xml).

[Artifact audit](artifact-audit.json) verifies207 hashes and all30 stitched note XML
multisets. Native base pitches preserved49/50; one orphan G3 discarded.109 full
rests lack durations;2106 typed durations internally consistent. [Warning replay](conversion-diagnostics.json)
matches all50 original XML hashes and recovers57 private-buffer diagnostic lines
in15 outputs. All30 literal XML page traces unavailable; [Bridge parser observations](parser-diagnostics.json)
retain inferred-timing/backup and ordinal-pairing limitations. Exact event parity,
accidental semantics, historical source provenance and full reference intent are
not proven. Primary scoring/failure policy and frozen outputs remain unchanged.

All owned workers are closed; no global job lock or automatic rerun remains.
Final [native inspection](resume-20261005-1746/final-native.json),19:35local:
RAM54.104%,commit44.227%,18.542GiB headroom, no Python/Git processes or worker lock.
[Closeout check](resume-20261005-1746/closeout-check.json) passed169 local links,
207 artifact hashes,108 conversion/source pins and unchanged14 regression failure IDs.
Supervisor receipts/scripts are preserved under `resume-20261005-1746`.
The user removed Git-specific count/private-memory stops and authorized limit
adjustments without another approval request. Defaults remain85% RAM/commit,
4GiB reserve,4GiB aggregate worker commit/16 processes and deadlines;512MiB used
for byte/audit jobs. No pressure failure during this resume (largest RAM77.671%).
Historical Codex-side diff-growth initiation and durable memory remedy unresolved.
No agent Git, external-process termination or automatic pressure retry.

Research changes: [input/CPU preparation](../../../zeus_attribution_prepare.py),
[actual recipe comparison](../../../zeus_attribution_infer.py),
[primary/diagnostic analysis](../../../zeus_attribution_analyze.py),
[parser observations](../../../zeus_attribution_parser_trace.py),
[tie ablations](../../../zeus_attribution_ties.py),
[exact trace helpers](../../../src/sheet2play_omr/zeus_trace.py),
[focused fixtures](../../../tests/test_zeus_attribution.py), and
[guarded progress output](../../../guarded_execution.py).
No shipped Bridge/recognizer/model edits or app publish required.

## Earlier afternoon admission/setup record — superseded

The following captures intermediate setup, not a live job or remaining command.

The user first requested a clean stop, then explicitly resumed on2026-10-05 afternoon.
Native inspection found no worker lock or Python/Git workers; RAM73.74%,commit44%.
The bounded monitor preflight passed: maximum fresh-system sampling latency16ms,
peak RAM72.95% and commit44.15%, supervisor complete/exit0. Evidence:
[preflight receipt](resume-20261005-1746/preflight/result.json).
The newly authorized manual byte verifier completed in session39444, supervisor29100,
with512MiB worker containment:113385 runtime files and50 detector files verified,
1211.578s, peak RAM77.671%/commit46.705%. [Receipt](resume-20261005-1746/identity-bytes/result.json).
Progress-reader correction passed70 focused fixtures,16.578s supervisor/exit0.
Full regression completed:323 passed,14 failed,2 skipped,9 subtests passed. Twelve
failures are blocked legacy Git calls; two are the known strict freeze metadata
mismatch. [Receipt](resume-20261005-1746/regression/result.json) and
[JUnit detail](resume-20261005-1746/regression-junit.xml). Full green acceptance remains unmet.
Deferred tie controls completed: unchanged normalization yields6 vs4 exact merged
notes, F1.4. Removing the independent voice alone restores merging; removing layout,
note-type labels or standardizing voice containers does not. [Diagnosis](resume-20261005-1746/tie-cases/diagnosis.json).
Import-only probe-v3 passed,12.719s, all required fields match; final focused71 passed.
Two failed setup probes are preserved; diagnostic eager imports and distribution search
context were corrected without altering frozen environments. Final complete regression
finished:324 passed,14 known failures,2 skipped,9 subtests; no new failures.
CPU preparation failed on absent float32 detector weights; receipt and partial inputs
are preserved. The diagnostic now explicitly selects the existing FP16 CPU fallback
with8/1 ONNX threads.72 focused fixtures pass. Single-page detector smoke is active
before all15 crops and visual review. No Zeus inference yet.
Live logs now go in ignored `.runtime` and are preserved as evidence after completion.
This reduces live diff churn but does not establish a durable app-side fix. Stop and
retain evidence if system pressure recurs; do not automatically repeat failed jobs.

The user explicitly resumed Phase3 after the interruption and requested no further
count-only Git stop. On2026-10-05 the user also removed the Git-specific memory cutoff,
retaining RAM/commit monitoring. Git count and private memory are record-only;
The user subsequently authorized adjusting limits without another approval request
after reporting97% memory. Defaults are now85% RAM/commit and4GiB commit reserve;
the interrupted verifier retained its earlier90%/2GiB policy.4 GiB worker
commit/16-process Job containment and deadline remain enforced. These explicit user
decisions supersede earlier Git count/memory limits and the hold below. Focused policy/attribution fixtures and
fresh admission are required before inference; actual pressure failures are not retried
automatically. No agent Git invocation or external-process termination.

## Preserved interruption evidence

The latest [receipt](identity-bytes-ram-commit/result.json) is blocked for actual
system commit97.030%, RAM70.078%, after1116.265s. Peak recorded Git count620/private
10.67GiB; separate native inspection found729 concurrent `diff --no-index` processes.
Recorded parents include independently verified Codex PID27788. Verification did not
finish; no verified-bytes output or global lock remains. Do not retry the verifier
automatically. The [job record](job-record.md) owns exact evidence and monitoring fixes.
Git telemetry previously blocked the pressure-check path;109s sample gap observed.
The new asynchronous telemetry and stricter profile pass69 focused fixtures;
[receipt](pressure-monitor-fix/focused/result.json) complete/exit0,15.688s,
RAM43.948%/commit41.033%. No verifier retry occurred. Sessions55570/78663 are complete.

[Job record](job-record.md) fixes 12 generated controls and development page 1 of
`openscore-6211535`, `openscore-6211549`, `openscore-6211555` before inference.
The original guarded resource preflight passed. At that interruption no inference,
detector preparation, reference validation, focused tests or new regression had run.

Runtime byte verification stopped: [supervisor result](identity-bytes/result.json),
[worker log](identity-bytes/worker.log), [resource samples](identity-bytes/resources.jsonl).
The supervisor recorded `unexpected_Git_process_buildup`, 15 Git processes,
192,995,328 aggregate private bytes; peak RAM61.14%, commit44.82%.
Several Git children had parent PID24828, independently identified as Codex's
`codex.exe`; others had intermediary parents or desktop app PID23972. This identifies
an app-origin burst, not the initiating cause of earlier system exhaustion.
Worker log ends during `research_environment`; no `verified-bytes.json` exists.
Worker exit0 during stopped-tree cleanup does not establish completed verification.
Last elevated process inspection found no Python/Git workers; global lock absent.

The [Phase 2 safety handoff](../phase2/handoff.md) says:
“If external growth returns, hold execution and retain evidence; do not retry
automatically or weaken limits.” The later explicit user continuation/policy revision
above supersedes this count-only hold; it does not waive memory pressure stops.

An earlier attempt used the legacy verifier before discovering its Git calls;
its owned supervisor/tree was stopped and stale lock owner-checked and removed.
That was a no-Git instruction violation, recorded in the job record. Use only the
new byte-only verifier thereafter; do not infer Git cleanliness or current HEAD.

## Resumed implementation and validation

New research-only scripts: `zeus_attribution_verify.py`, `zeus_attribution_prepare.py`,
`zeus_attribution_infer.py`, `zeus_attribution_analyze.py`; trace module
`src/sheet2play_omr/zeus_trace.py`; fixtures `tests/test_zeus_attribution.py`.
Focused safety/attribution51 fixtures passed under `focused-resume-v2` (exit0,14.078s).
Final focused-input checks54 passed (`focused-inputs`, exit0,15.531s), including
the added crop-boundary/hidden-rest fixtures. Full research/Bridge regression ran:
319 passed,2 failed,2 skipped,9 subtests passed. Both failures are the documented
expanded-access historical-freeze mismatch:33 added package metadata entries, with
no other snapshot difference. [Git-blocking read-only diff](freeze-differences.json)
completed (`freeze-diagnosis`, exit0,6.750s). Legacy suite helpers indirectly invoked
Git, violating recovery instructions; do not rerun those paths unchanged. No frozen
test/artifact change, skip or xfail was introduced. The
experiment is not identity-frozen and no inference has run. Git-free byte verification
in `identity-bytes-resume` ended blocked; session45074 is no longer live.
Historical source, reference generators, scoring identities and Bridge remain unchanged.

Design: hash-pinned bytes; actual upstream LMXDataset/Keras inference versus unchanged
local wrapper on identical crops; preserve token IDs/unknowns/termination and conversion
diagnostics; trace exact XML, unchanged stitching/normalization and global/local metrics.
Pre-inference image inspection found full generated pages with large margins, not
system crops. All14 non-reused pages now require CPU HOMR detection; representative
corrected coordinates reused. Baseline image has two systems; diagnostic reference
boundaries[0,5] explicitly recorded because kern import lacks layout markers. Eleven
other controls are single-staff, not piano grand staffs. Three open pages' first-page
boundaries agree with images (19/11/7 measures;5/4/2 systems). Vocal staff hidden in
piano-only passages; first representative hidden vocal rest is4 beats in a6-beat meter.
Syncopation opening eighth rest is not clearly visible; preserve reference and qualify
claims. System-local origins reset per part at actual boundary, preserving leading rests;
global primary metrics unchanged. Normalized staff indices reset per part, so XML part/staff
counts accompany coverage and no hand-accuracy claim is made.
Investigate the deferred independent-voice tied-chord reproducer without repairing Bridge.

## Preserved 2026-10-04 interruption: then-active Git-memory guard

[Supervisor result](identity-bytes-resume/result.json) records
`unexpected_Git_private_memory`, elapsed999.063s,150 external Git processes and
2,734,989,312 private bytes (2.55 GiB), above the retained1 GiB guard.
Peak RAM55.755% and commit55.135% do not establish imminent system exhaustion.
The stop-time process diagnostic itself recorded `MemoryError`; its cause and scope
are unverified. Recorded Git children include old Codex parent PID24828 and
intermediary parents; commands and the initiating cause were not captured.
[Worker log](identity-bytes-resume/worker.log) ends at `Verifying zeus_environment`;
no `verified-bytes.json` exists. Worker exit0 is cleanup, not verification acceptance.
Native inspection2026-10-04T23:49:33+03:00 found no Python/Git workers or global lock;
parent24828 was absent. Preserve both attempts; do not automatically retry this verifier.
Lightweight focused checks are separate authorized validation, not a verifier retry.

## Exact continuation after 2026-10-05 policy revision

The fixed execution/reporting is finished. Review [REPORT.md](REPORT.md)'s met,
unmet and unverified criteria before claiming full acceptance. No worker is pending;
do not repeat completed byte verification, preparation or inference without a new
identity/diagnostic reason. Existing cached results are reusable only while their
manifest/input/source identities match. Preserve every failed receipt.

Any further authorized Phase3 gap investigation must first inspect live jobs/locks,
use the supervisor and keep RAM/commit/headroom/worker/deadline containment. No Git
or automatic system-pressure retry. Resolving cropped content, duplicate systems,
native grammar handling or chord-tie normalization by changing the pipeline is a
Phase4 remedy requiring a separate request. Rokot is separately requested Phase5.
Historical source recovery and durable app-side memory causality remain unresolved;
the [earlier interruption report](INTERRUPTION_REPORT.md) remains evidence, not the
current execution status. No screen rerun, training, cloud spending or promotion.
