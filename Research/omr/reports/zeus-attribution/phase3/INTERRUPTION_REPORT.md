# Phase 3 partial implementation and interruption

Owner: [MAIN_PLAN.md](../../../../../plans/MAIN_PLAN.md), plan
`2026-10-03-zeus-attribution-repair`, Phase3. Authorized scope: controlled Zeus
attribution and deferred chord-tie investigation. Phase3 is incomplete; no Phase4/5,
training, spending, frozen benchmark rerun or promotion.

Lifecycle update2026-10-05: the user removed the Git-specific memory cutoff and resumed
with system RAM/commit safeguards. The hold/limits below describe the preserved earlier
interruption; use the [current handoff](handoff.md) for current authority and execution.

## What stopped and why

The first verifier stopped at15 Git processes with192,995,328 private bytes,
RAM61.14% and commit44.82%. These measurements did not establish imminent memory
exhaustion. The user's subsequent instruction removed count-only stops. Safety-policy
fixtures allow8,15 and108 processes when memory remains within bounds; the supervisor
records count rather than using it as a stop condition.

The resumed verifier hit the retained1 GiB Git-private-memory limit:
[result](identity-bytes-resume/result.json),
[resource history](identity-bytes-resume/resources.jsonl),
[worker log](identity-bytes-resume/worker.log).

| Recorded value at interruption | Value |
|---|---:|
| Stop reason | `unexpected_Git_private_memory` |
| Git count (informational) |150 |
| Aggregate Git private bytes |2,734,989,312 (2.55 GiB) |
| Peak physical RAM |55.755% |
| Peak system commit |55.135% |
| Elapsed supervisor time |999.063 seconds |

This guard crossing does not prove an imminent system crash. Stop-time process
diagnostic capture itself recorded `MemoryError`; its cause and allocation context are
unverified. Saved Git records include old Codex parent PID24828 and intermediary
parents. No command lines were captured, so the initiating command and durable remedy
remain unknown. The agent did not launch Git or terminate external Git during this attempt.

Worker log ends at `Verifying zeus_environment`; no complete verification JSON exists.
Exit0 during stopped-tree cleanup is not successful verification. Native inspection
2026-10-04T23:49:33+03:00 found no Python/Git workers, old parent24828 absent and no
global lock. Both attempts are preserved; the failed verifier has not been automatically retried.

## Completed independent work

Research scripts prepare a fixed15-item experiment, actual upstream and unchanged
local-wrapper replay, token/conversion evidence, XML tracing and global versus diagnostic
local scoring. No inference has run; experiment identity is not yet frozen.
All15 images/references were inspected before outputs: [reference review](REFERENCE_REVIEW.md).
Generated inputs are full pages, requiring corrected detector crops. Hidden vocal rests,
single-staff controls and ambiguous syncopation engraving are qualified rather than repaired.

The deferred independent-voice chord-tie fixture demonstrates six raw segments,
four merged diagnostic events and six events from unchanged Bridge normalization.
Its pitch/onset/duration F1 against diagnostic merged events is0.4. This is fixture-level
normalization attribution, not a Zeus recognition verdict or shipped repair.
Bridge and frozen scoring/reference identities remain unchanged.

Final focused fixtures:54 passed, [receipt](focused-inputs/result.json),
[log](focused-inputs/worker.log), complete/exit0,15.531s. Full regression:
319 passed,2 failed,2 skipped,9 subtests passed ([log](regression/worker.log),
[receipt](regression/result.json), failed/exit1,54.141s). Both failures match
the documented [Phase1 expanded-context issue](../phase1/REPORT.md):
[diff](freeze-differences.json) has33 added package metadata entries and no other
snapshot differences. Git-blocking diagnosis completed/exit0,6.750s.
Legacy regression helpers indirectly invoked Git, violating recovery instructions;
this is recorded in the [job record](job-record.md). Do not rerun those paths unchanged.
No frozen artifact/test change, additional skip or xfail was introduced.

## Phase 3 acceptance status

| Plan criterion | Status | Evidence or remaining requirement |
|---|---|---|
| Actual upstream versus unchanged wrapper on identical crops | Unmet | Implementation exists; detector preparation and inference have not run |
| Preprocessing, valid widths, grayscale, resize and crop coverage | Unverified | Source review/instrumentation prepared; tensors/crop inspection pending; combined recipe difference does not isolate mask effects |
| Tokens, unknowns, termination and prediction limits | Unverified | Unknown-token fixture passes; model/EOS/cap evidence pending |
| LMX → XML → stitching → normalization → scorer trace | Unverified | Failure/trace fixtures and deferred tie attribution pass; replay trace pending |
| Development image/reference content validation | Met for pre-inference review | All15 inspected with qualifications; final crop coverage/pinning pending |
| Global and diagnostic measure/system-local metrics | Unmet | Scoring fixtures pass; complete15-item results absent |
| Relevant fixtures and full research/Bridge regression | Met for execution; full success unmet |54 focused pass;319 full pass,2 known historical-context failures,2 skips,9 subtests pass |
| Qualified Zeus verdict and complete diagnostics | Unmet | Runtime verification incomplete; no recognition verdict or development aggregate |

## Exact next action

Independent regression and source/reference review are recorded above. Dependent execution requires addressing
external growth and explicit manual continuation after this memory-limit failure;
[AGENTS.md](../../../../../AGENTS.md) prohibits automatically retrying pressure failures
or weakening limits. Keep Git count informational. If continuation is authorized, inspect
native processes/resources/locks and run the byte verifier under the supervisor in a new
evidence directory. Preserve failed receipts. Only a complete new receipt can authorize
fresh import probe and detector preparation; then inspect crops, freeze identities, run
one representative replay, complete the fixed set and produce the attribution report.
