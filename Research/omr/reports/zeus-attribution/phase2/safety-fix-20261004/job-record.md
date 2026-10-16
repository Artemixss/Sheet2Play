# Operational safety implementation and bounded verification

Authorized by the user's request to fix recurrence safeguards. Phase 2 scoring sources,
corrected-v1 identity/results and historical artifacts remain unchanged. This is CPU-job
containment, not a demonstrated repair of the unknown initiating consumer.

Working directory: `C:/Users/bur4x/Desktop/lecture/big_projects/Sheet2Play`.
Supervisor: `Research/omr/guarded_execution.py`; global `.research-worker.lock` records
its PID/output. Inspect process/log before resuming; never delete a live lock. One worker.

Smoke command (64 MiB contained child tree, 60-second deadline):

```powershell
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/reports/zeus-attribution/phase2/safety-fix-20261004/smoke --worker-limit-mib 64 --max-seconds 60 -- Research/omr/.venv/Scripts/python.exe -B -c "print('guard-smoke')"
```

Admission/continuous checks: 90% RAM and commit, at least 2 GiB remaining commit;
admission also reserves the complete worker allowance. Eight Git processes or 1 GiB
aggregate Git private bytes block execution. External Git is observed, never killed.
Commit/physical/Git sample interval 0.5 seconds, bounded worker output 8 MiB;
separate Job Object caps aggregate worker committed memory and process count and kills
only its assigned descendants on supervisor closure. Job assignment must succeed before
the worker receives its start message. Default worker limit 4 GiB, session14370 seconds.
Existing scoring RAM/VRAM policies remain intact; this CPU wrapper adds no inference.

Per-run `result.json`, `resources.jsonl`, `worker.log` preserve command, operational
source hashes, pressure/abort evidence and exit status. Never retry automatically or
overwrite an output directory. A failed cleanup or unsaved result leaves the owned lock
for explicit investigation instead of admitting another worker. Follow focused policy/containment fixtures with the full
Bridge/research suite under the supervisor. If pressure blocks a run, record it and
resolve pressure before retrying; do not weaken limits or acceptance criteria.

Smoke passed: exit 0, 8.344 seconds, 59.30% peak system commit / 80.49% physical RAM,
zero Git processes. This proves basic Job assignment/start only; enforcement needs fixtures.
Independent source review required rechecking pressure at gate release and late output
reader failures, plus preserving cleanup evidence. These corrections precede the tests.

Focused command (4 GiB outer Job, nested 64 MiB fixture Jobs):

```powershell
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/reports/zeus-attribution/phase2/safety-fix-20261004/focused --max-seconds 180 -- Research/omr/.venv/Scripts/python.exe -B -m pytest Research/omr/tests/test_execution_safety.py -q -o addopts=''
```

Full regression command, after focused checks pass (no inference):

```powershell
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/reports/zeus-attribution/phase2/safety-fix-20261004/regression --max-seconds 600 -- Research/omr/.venv/Scripts/python.exe -B -m pytest Bridge/tests Research/omr/tests -q -o addopts=''
```

Focused passed: 29 tests in 3.36 seconds; supervisor 12.609 seconds, commit57.95%,
RAM78.59%. Full regression passed:299 tests,2 skipped,9 subtests in54.54 seconds;
supervisor63.313 seconds, commit62.66%, RAM79.66%, Git0. Fresh review found two
additional cleanup/evidence issues: preserve the primary stop reason on a late logging
failure; retain the shared lock if Job-handle closure is unconfirmed. Corrections and
three meaningful fixtures require the following fresh focused and complete regression.
Prior run evidence is retained; no rerun of scoring.

```powershell
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/reports/zeus-attribution/phase2/safety-fix-20261004/focused-final --max-seconds 180 -- Research/omr/.venv/Scripts/python.exe -B -m pytest Research/omr/tests/test_execution_safety.py -q -o addopts=''
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/reports/zeus-attribution/phase2/safety-fix-20261004/regression-final --max-seconds 600 -- Research/omr/.venv/Scripts/python.exe -B -m pytest Bridge/tests Research/omr/tests -q -o addopts=''
```

Final focused: 35 passed in 5.97 seconds; supervisor 14.828 seconds, peak commit58.60% /
RAM74.55%. Final full regression: 302 passed, 2 skipped, 9 subtests, one expected clef
warning in 36.30 seconds. Supervisor complete/exit0 in 45.375 seconds; peak commit62.15%
/ RAM76.11%, Git0. No live test worker or global lock after completion. Frozen report
and all declared scoring-source hashes passed. No repeated cached rescore or inference.
The C-only system-managed pagefile proposal and rollback are in [REPORT.md](REPORT.md);
user choice pending, no Windows/app/Git setting applied. Final independent source/evidence
review is saved separately. No unattended job/automation.

## Approved C-only paging change

User approved C: system-managed size on 2026-10-04. Preview parsed and validated without
mutation; before/result are in `pagefile-preview/`. The reviewed helper will be launched
with administrator UAC using `Start-Process -Verb RunAs -WindowStyle Hidden`; only
`PagingFiles` changes from `C:\pagefile.sys 16384 32768` to `C:\pagefile.sys 0 0`.
Automatic management of all drives remains disabled. No reboot is authorized/performed.
Evidence directory: `pagefile-change/` (fresh). Independent post-change registry/CIM
verification will distinguish configured policy from runtime capacity pending reboot.

Planned elevated child command:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\Users\bur4x\Desktop\lecture\big_projects\Sheet2Play\Research\omr\reports\zeus-attribution\phase2\safety-fix-20261004\set-c-pagefile.ps1" -EvidenceDirectory "C:\Users\bur4x\Desktop\lecture\big_projects\Sheet2Play\Research\omr\reports\zeus-attribution\phase2\safety-fix-20261004\pagefile-change" -Apply
```

Pre-apply independent review found a final-evidence write outside the rollback handler.
Corrected it so failed result persistence emits a blocked/nonzero result and attempts
verified rollback before disposing the registry handle. Source reparsed without errors.
The restricted preview was blocked by CIM access denial (`pagefile-preview-final/`),
before mutation. A read-only sandbox escalation produced `pagefile-preview-verified/`:
`preview_validated_no_change`. The wrapper incorrectly checked a stale LASTEXITCODE;
the saved successful JSON status was then checked directly. Neither preview applied a
setting. Independent final helper review accepted the correction. Helper SHA-256:
`071FB587BB63E3BEE81ADCCCC09EDA0BF5F1EE177838595546A6F6350E4FF887`.

## Applied policy and independent verification

At 13:20 local on 2026-10-04, UAC administrator helper PID23388 completed with exit0.
[Launch record](pagefile-launch.json), [before](pagefile-change/before.json),
[after](pagefile-change/after.json) and [result](pagefile-change/result.json) are saved.
Independent [verification](pagefile-change/verification.json) confirms exactly one
REG_MULTI_SZ `C:\pagefile.sys 0 0`, AutomaticManagedPagefile=false, C-only CIM initial/max0.
No reboot performed; current allocation remains16384 MiB, usage1097/peak1121 MiB at check.
Original custom C initial16384/max32768 is preserved for rollback; no portable-drive paging.
Independent reviewer also read current registry and added the configured-policy verdict
in [REVIEW.md](REVIEW.md). No further Windows/app/Git setting changes, rescore or inference.
No observed Git/Python worker or `.research-worker.lock` after verification.

Next exact action, after the user restarts: read current C-only registry/CIM configuration
and actual runtime allocation; inspect native system commit/RAM, Git/process evidence and
live jobs/locks using the reviewed CPU supervisor with a fresh evidence directory. A
blocked admission is not permission to relax limits. Then resume only saved Phase2
implementation/statistical review and closeout; no repeated cached scoring is needed.
The external memory initiator and durable system/app repair remain unverified. No
unattended work, recurring monitor or automatic reboot is pending.

Closeout documentation check: nine task-relevant Markdown files, 152 local link targets,
zero missing ([document-links.json](document-links.json)); external URLs/anchors excluded.
Updated startup/plan/handoff no longer contain a pending paging-choice claim. Final helper
source hash matches the applied identity, and frozen corrected report hash remains exact.
The safety acceptance ledger is current: configured policy/guard/tests/review met;
post-reboot capacity unverified; resume gate unmet pending restart/preflight. Other
system/file integrity and the external memory initiator remain unverified. No app release
needed for these research-only changes; no research worker started during OS closeout.
