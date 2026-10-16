# Execution safeguards after repeated commit exhaustion

The crashes exhausted Windows system commit, reaching 99.913% in the recurrence.
The initiating consumer remains unidentified. No scoring/test/inference worker had
started in that failed continuation, so a research-worker fix alone cannot establish a
durable system/app repair. Wi-Fi/WARP recovered after reboot according to the user.
The [recurrence investigation](../crash-recurrence-20261004/REPORT.md) preserves the
events; Git buildup observed after exhaustion is evidence, not proven causality.

## Implemented protection

New [CPU supervisor](../../../../guarded_execution.py),
[waiting bootstrap](../../../../guarded_worker.py),
[policy](../../../../src/sheet2play_omr/safety_policy.py),
[Windows sampler](../../../../src/sheet2play_omr/execution_resources.py) and
[Job containment](../../../../src/sheet2play_omr/windows_job.py) are separate from
the frozen scorer/runner identity. All future authorized Phase 2 CPU workers must use
the supervisor; direct starts of timing_repair/pytest/verifiers are prohibited.
This does not authorize new inference or supersede existing VRAM policies.

- Windows Job Object caps aggregate worker committed memory at 4 GiB and processes at 16.
  A waiting bootstrap is assigned before it receives its start message. Assignment or
  measurement failure prevents substantive work. Job closure kills only assigned descendants.
- Admission reserves the entire worker allowance plus 2 GiB system commit headroom.
  Every 0.5 seconds, stop the assigned worker at 90% system commit or physical RAM,
  below 2 GiB commit headroom, or the session deadline. Recheck immediately before gate release.
- Eight Git processes or 1 GiB aggregate Git private memory blocks/stops the assigned
  worker. These are conservative operational tripwires, not validated universal Git
  capacity limits or a diagnosis. External processes are observed, never terminated.
- Exclusive `.research-worker.lock`, fresh output directories, no automatic retries,
  source hashes and bounded 8 MiB worker logs preserve reviewable/resumable evidence.
  An unconfirmed Job closure or process cleanup retains the lock for investigation.
  Failed result persistence also leaves the lock. Never remove it without inspecting
  the recorded supervisor, worker tree and logs. Default deadline 14370 seconds leaves
  30 seconds before the four-hour unattended limit; longer limits are rejected.

This supervisor is CPU-only; it adds no GPU/VRAM control. It cannot cap independently
running Codex/Git or other applications and does not protect desktop activity while no
guarded worker runs. No app/driver/Git configuration, OS repair or unrelated process
termination was applied. The separately approved paging change is recorded below.
A bounded local-app/official-documentation
inspection did not establish a supported Git concurrency setting; no guessed key was used.

## Verification and independent review

[Tests](../../../../tests/test_execution_safety.py) cover exact thresholds, invalid
measurements/limits, admission reservation, pressure before start and during work,
assignment refusal, sampling failure, bounded allocation rejection, timeout, descendant
cleanup/unrelated-process survival, lock collision, late logging failures and unconfirmed
Job closure both during success and an existing abort. The real 64 MiB Job refused a
128 MiB allocation with MemoryError; the tests did not exhaust system memory.

Independent review read source and saved evidence directly. It required correcting the
pre-start sampling gap, late-reader success/error handling, diagnostic/cleanup evidence
and conservative lock retention. [Job record](job-record.md) preserves each run and
the commands. Final focused checks: **35 passed** in 5.97 seconds. Final full regression:
**302 passed, 2 skipped, 9 subtests passed** in 36.30 seconds, one expected unreadable-clef
warning. [Supervisor result](regression-final/result.json): complete/exit 0, 45.375 seconds,
peak observed commit 62.15% / RAM 76.11%, Git 0. [Full test log](regression-final/worker.log).
Earlier passing runs remain preserved. [Final independent review](REVIEW.md) found no
remaining required corrections in the CPU-worker scope.

The frozen report hash remains
`040ee6e7de58dec077ccdaa28961ee3e88a367a6dbc16931620e3df9a7cbb255`.
All declared corrected-v1 scoring source hashes are checked by a regression fixture.
The prior [post-crash audit](../crash-audit-20261004-02/verification.json) verified 295
outcomes/1,257 artifacts. No new rescore, inference or model/configuration change.

## Approved paging-file change and rollback

[Read-only settings evidence](../crash-recurrence-20261004/paging-preflight.json):
only `C:\pagefile.sys`, custom initial 16384 MiB/max 32768 MiB, automatic management
disabled; C has about 114.6 GiB free. Increasing the page file is supported. Windows uses
system-managed sizing by default; sizing depends on peak system commit and crash-dump
requirements. [Microsoft sizing guidance](https://learn.microsoft.com/en-us/troubleshoot/windows-client/performance/how-to-determine-the-appropriate-page-file-size-for-64-bit-versions-of-windows).

The user approved **System managed size for C only**. At 13:20 local on 2026-10-04,
the reviewed [administrator helper](set-c-pagefile.ps1) changed the single REG_MULTI_SZ
entry from `C:\pagefile.sys 16384 32768` to `C:\pagefile.sys 0 0`; all-drive automatic
management remains disabled and the portable SSD is excluded. The helper saved
[before](pagefile-change/before.json), [after](pagefile-change/after.json) and
[result](pagefile-change/result.json), then exited zero. An
[independent registry/CIM check](pagefile-change/verification.json) confirmed the
configured policy and C-only 0/0 setting. This exact C-only system-managed encoding is
documented by [Microsoft Windows Support](https://jpwinsup.github.io/blog/2023/02/08/Performance/Hang_BSOD/HowToChangePagingFileSetting/).

**No reboot was performed.** Active allocation remains 16384 MiB; post-reboot commit
capacity is unverified. Verify it after the user restarts before resuming CPU work.
System-managed sizing permits Windows to adjust capacity, but cannot cure an uncontrolled
consumer. Automatic growth can also
have allocation latency; that mechanism is not established here, where exhaustion
reached the recorded maximum capacity. [Microsoft allocation/growth guidance](https://learn.microsoft.com/en-us/troubleshoot/windows-client/performance/slow-page-file-growth-memory-allocation-errors).

Rollback if needed: `SystemPropertiesAdvanced.exe` → Performance Settings → Advanced
→ Virtual memory Change → select C → Custom size, initial 16384/max 32768 MiB → Set
→ OK; keep automatic management of all drives disabled. Apply a restart when ready.
The helper includes verified rollback attempts on change/verification/evidence failure;
source parsing, fresh preview and independent review preceded this successful application.

## Resume gate and acceptance

No repeated rescore is needed. Continue only the remaining Phase 2 implementation/
statistical review of saved artifacts after a post-reboot resource preflight. Before every CPU job,
inspect live jobs/locks and use the guarded command with a fresh evidence directory.
Do not weaken limits to admit a blocked run. If background buildup/pressure recurs,
save the evidence and hold execution; review app isolation/recovery before further work.
Running a guarded worker from a separate terminal with the desktop app fully exited is
a possible isolation experiment, not a demonstrated repair; no such experiment ran.
Phase 3–5 and the deferred cross-system tie normalization repair remain unauthorized.

| Acceptance criterion | Status | Evidence/limit |
| --- | --- | --- |
| Preserve frozen scores/scoring identity | Met | Regression checks report and declared source hashes; cached audit remains valid |
| Implement enforced CPU worker containment/pressure admission | Met | Job limit, start gate, commit/RAM/Git checks and bounded logs |
| Validate focused fixtures and full research/Bridge regression on final code | Met | 35 focused; 302 full, 2 skipped, 9 subtests; final source hashes recorded |
| Independently inspect final code/evidence | Met | Final source/evidence review accepted CPU safeguards; paging-helper failure correction reviewed |
| Change/verify configured paging-file policy | Met | Approved C-only system-managed value independently verified; before/after/rollback evidence saved |
| Verify paging capacity after reboot | Unverified | No reboot performed; active allocation remains 16384 MiB |
| Pass execution resume gate | Unmet | Await user restart and post-reboot resource preflight |
| Identify initiating consumer / demonstrate durable system crash fix | Unverified | Worker-only protection cannot control external apps |
| Certify other OS/files/portable SSD | Unverified | Research artifact audit is limited; D dirty flag unresolved |
| Complete Phase 2 statistical/implementation acceptance | Unverified | Remains the next phase task; no Phase 3 execution |

## Later verification — 2026-10-04 at21:10 local

The table above records pre-reboot status. Subsequent user reboot at20:56 is verified:
C-only system-managed paging has18 GiB active allocation. Guarded resource preflight
and independent statistical audit both passed. Paging runtime verification, execution
resume gate and Phase2 implementation/statistical acceptance are now **met**.
[Closeout evidence and remaining limitations](../closeout-20261004/REPORT.md).
Initiating external consumer, durable whole-system remedy and OS/SSD integrity remain
unverified. No inference or rescore occurred; the safeguards remain mandatory.
