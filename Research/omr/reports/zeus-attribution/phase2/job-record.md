# Phase 2 job record — 2026-10-04

Authority: [MAIN_PLAN.md](../../../../../plans/archive/2026-10-03-zeus-attribution-repair.superseded.md), Phase 2 requested in this chat.
Scope: shared rational reading and all 295 cached outcome scores, statistics and report.
No inference, Bridge change, training, cloud use, promotion or later phase execution.

Initial quota: 26% used of the five-hour allowance. RAM 78.3%; process inspection
found only the current Python launcher/worker. Historical scorer/source hashes match.

## Reviewed scope decision

The first exact-divisions fixture exposed an existing normalization defect: tied
C4/E4 chords across two systems remain split when another voice is present.
music21 parses the start/stop markers and 1/3, 2/3 durations correctly; Bridge's
`stripTies(inPlace=False, matchByPitch=True)` does not merge this chord.
The earlier partial-chord fixture instead lengthened its untied E4; this was not
used as the final reproducible acceptance fixture.

Work paused before rescoring. The user explicitly chose:
“Keep Phase 2 limited to cached scoring; record and investigate the normalization
defect in Phase 3.” The [reproducer](cross-system-chord-tie.musicxml) and original
[regression failure](regression.log) are preserved. The scoped fixture now verifies
all six cached normalized segments against exact MusicXML divisions; it does not
claim the chord ties are merged. No xfail, skip, normalizer or historical data edit.

## Timing policy

Unrestricted denominator limiting would map genuine `0.33334` to `1/3` and
`1/5000` to `1/4096`. To satisfy preservation of genuine errors, the shared reader
retains exact fractions and applies the existing 4096 reconstruction only within
eight binary64 ULPs. This numerical guard is not an onset matching tolerance.
Both predictions and references use this reader in a new scoring module.
The original reference generator, scorer, adapter and frozen identities are unchanged.

## Verification and run

Initial full suite: 266 passed, 2 skipped, 1 new tied-chord fixture failure.
After the user's scope decision, all 16 focused tests pass (`focused.log`).
Representative cached control: `test/beethoven/sonata02_2/sonata02_2_1.png`, shipped
HOMR. F1 unchanged at 0.007237635705669481; 294 serialized values reconstructed,
maximum change 1/300000000000000 quarter notes; zero values differ from the
unrestricted historical policy. All 59 control input/result/score records verified
before this one-item metric check; no files written by the check.

Working directory: `C:/Users/bur4x/Desktop/lecture/big_projects/Sheet2Play`.
Command (one worker, no inference):

```powershell
Research/omr/.venv/Scripts/python.exe -B Research/omr/timing_repair.py --output Research/omr/reports/zeus-attribution/phase2/corrected-v1
```

Log: `rescore.log`. Per-item 90% RAM/device-VRAM admission samples:
`corrected-v1/resources.jsonl`. Four-hour limit checked between items; stops on
pressure immediately. Immutable per-item scores, input identities and source identity
allow resumption with the same command. A `worker.lock` holds the PID during the run;
check its process and log before resuming. No unattended watcher/automation.

The runner verifies all declared cached artifacts, original score identities/hashes,
references/XML hashes, baseline manifests/summary hashes, frozen scoring sources and
scoring dependency versions. OMR-NED is not executed; original distances are reused
with those unchanged inputs and source/version provenance. Historical dependency
inventories pin versions, not all installed package bytes; no stronger historical
package-byte provenance is inferred.

Completed before the Windows crash: cached rescore ended 00:17:49, report written
00:17:54, full regression ended 00:18:19. All 295 outcomes scored; ten failures retained.
Full regression: 267 passed, 2 skipped, 9 subtests passed, one expected clef warning
(`regression-scoped.log`). Corrected report and scoring identity are in
[the current handoff](handoff.md).

The user's subsequent request prioritizes crash investigation before phase continuation.
[Investigation](crash-investigation-20261004/REPORT.md) confirmed system commit exhaustion
at 00:21–00:24; the initiating consumer remains unknown. The existing independent verifier
passed again after reboot: all 295 records / 1,257 declared artifacts, metrics and report
hash verified (`crash-audit-20261004-01/verification.json`). No research worker, lock or
incomplete score was found. No inference, rerun, repair or configuration change was made
during the investigation.

Pending on continuation: direct independent implementation/statistical review, final
acceptance ledger and phase closeout. Before any new heavy job, add system-commit pressure
protection alongside the existing RAM/VRAM checks. The saved completed scores/tests are
reusable; a crash alone does not require repeating them.

## Recurrence during requested continuation

The user requested continuation, then reported another paging-file warning, app failures
and Wi-Fi disruption. The [recurrence investigation](crash-recurrence-20261004/REPORT.md)
confirms system commit at 99.913% around 11:53–11:57. No scoring/test/inference worker
had started during continuation; file reads/searches and a process listing were performed.
The listing confirms at least 108 Git processes after exhaustion began. The initiating
consumer remains unknown. No OS/app/Git remedy was implemented or demonstrated.

Bounded audit command, same working directory as above:

```powershell
Research/omr/.venv/Scripts/python.exe -B Research/omr/reports/zeus-attribution/phase2/crash-recurrence-20261004/guarded_audit.py
```

Log: [crash-audit-20261004-02.log](crash-audit-20261004-02.log). Exit zero, 24.06 seconds;
295 records / 1,257 artifacts and report hash verified again. Sampling every 0.5 seconds,
the wrapper aborts itself at 90% RAM/commit or 120 seconds, and streams artifact hashing.
Peak observed commit 54.71%, physical RAM 85.08%. It changes neither the pinned scoring
identity nor the scorer/runner and is not system-wide protection. No Git invocation,
tests, rescoring, inference, process kill or configuration change during this investigation.

Execution is held pending resource-control review and investigation of the initiating
problem. Existing results/regression remain reusable; independent Phase 2 acceptance
review/closeout remains pending. Check live processes before any future job.

## Subsequent authorized safeguards

The user requested actual protection and paging-file guidance. Separate operational
[supervisor/Job safeguards](safety-fix-20261004/REPORT.md) preserve frozen scoring sources
and identity. [Safety job record](safety-fix-20261004/job-record.md) holds commands/logs
and review-driven corrections. Final focused35 passed; full research/Bridge302 passed,
2 skipped,9 subtests. Peak commit62.15% / RAM76.11%, Git0; no rescore/inference.
At that test completion, no OS/paging/app/Git settings had changed. The user subsequently
approved C-only system-managed paging; the reviewed administrator helper applied it at
13:20 local on 2026-10-04 (PID 23388, exit zero). Before/after and independent configured-policy
verification are in the [safety record](safety-fix-20261004/job-record.md). No reboot performed;
runtime capacity and execution resume preflight remain pending. Worker protection cannot
establish a durable fix for independent app growth. No worker/global lock remained.

2026-10-04 closeout: post-reboot preflight and independent statistical/implementation review passed. Phase2 complete. See closeout-20261004/REPORT.md and closeout-20261004/job-record.md. No inference/rescore/code changes; frozen identities unchanged. Await Phase3 request.
