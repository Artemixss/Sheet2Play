# Independent operational-safety review — 2026-10-04

Final required code corrections: **none** in the reviewed CPU-worker scope.
The implementation supplies enforced worker containment and pressure checks. It does
not establish the initiating consumer or a durable system/app crash fix.

## Direct inspection and corrections

Reviewed the [supervisor](../../../../guarded_execution.py),
[bootstrap](../../../../guarded_worker.py),
[sampler](../../../../src/sheet2play_omr/execution_resources.py),
[policy](../../../../src/sheet2play_omr/safety_policy.py),
[Windows Job implementation](../../../../src/sheet2play_omr/windows_job.py),
[fixtures](../../../../tests/test_execution_safety.py) and [report](REPORT.md).
This review used source and saved artifacts directly, not only executor summaries.
No Git, tests or research workers were launched by this review.

Earlier required findings are resolved:

- Admission and elapsed budget are rechecked immediately before the start message.
- Late output-reader errors cannot leave a successful result; primary stop reasons
  survive secondary logging errors.
- Diagnostic-capture failures remain evidence rather than replacing the initiating
  exception. Cleanup failures are recorded.
- Unconfirmed Job closure retains the exclusive worker lock, including closure
  failure during an existing pressure abort. Result-persistence failure likewise
  leaves the lock; no automatic retry is present.

Native Job assignment precedes substantive child work. Aggregate committed-memory and
active-process limits are enforced by Windows; the unnamed Job handle is non-inheritable
and closes with kill-on-close. Platform, assignment or resource-sampling failure has no
uncontained execution fallback. The real allocation fixture verifies rejection of a
128 MiB allocation within a 64 MiB Job. Descendant cleanup and unrelated-process survival
are covered by a separate native fixture, without deliberately exhausting the system.

## Verification evidence

| Check | Directly inspected evidence | Result |
| --- | --- | --- |
| Final focused fixtures | [Worker log](focused-final/worker.log), [supervisor result](focused-final/result.json) | 35 passed; exit 0; 14.828 seconds including supervision |
| Final research/Bridge regression | [Worker log](regression-final/worker.log), [supervisor result](regression-final/result.json) | 302 passed, 2 skipped, 9 subtests passed; one expected unreadable-clef warning; exit 0 |
| Final full-run pressure | Final regression result | 45.375 seconds including supervision; peak commit 62.1499%; peak physical RAM 76.1056%; zero Git processes in initial/gate/final samples |
| Operational identity | Both final result manifests versus current source hashes | All five recorded operational-source hashes match |
| Frozen scoring identity | Corrected-v1 identity versus its nine declared source files | All hashes match |
| Frozen corrected report | Direct SHA-256 check | `040ee6e7de58dec077ccdaa28961ee3e88a367a6dbc16931620e3df9a7cbb255` |
| Exclusive worker lock | Direct workspace inspection after final runs | Absent |

## Acceptance and remaining limits

| Criterion | Status | Review verdict |
| --- | --- | --- |
| Enforced CPU-worker containment/admission | Met | Native memory/process ceiling, start gate, commit/RAM/Git tripwires and deadline |
| Meaningful final fixtures and complete relevant regression | Met | Final logs/results above match current operational code |
| Preserve corrected-v1 scoring identity and report | Met | Direct hash checks; operational code remains separate |
| Independent final code/evidence review | Met | Required findings resolved within the stated scope |
| Change and verify paging-file policy | Unmet | Report records a proposal; no Windows setting change is evidenced |
| Identify initiating consumer and demonstrate durable external app fix | Unverified | Git observation followed exhaustion; worker containment does not control independent app processes |
| Certify Windows or portable-SSD contents | Unverified | Prior research-artifact audit has a limited scope |
| Complete Phase 2 implementation/statistical acceptance | Unverified | Separate remaining closeout work; this review does not complete it |

The nominal monitoring interval is 0.5 seconds plus sampling/execution overhead;
sampling is not a real-time system-wide guarantee. External Codex/Git and other apps
are observed, never capped or terminated. Monitoring runs only while this supervisor
runs. Eight Git processes and 1 GiB private-memory thresholds are conservative
operational tripwires, not causal findings. CPU scope adds no VRAM sampling and cannot
replace the existing policies governing future GPU work.

Accept these safeguards for explicitly authorized CPU workers. Do not describe them
as a completed crash fix or repeat a rescore merely to demonstrate execution. Saved
Phase 2 results remain reusable; its remaining review and closeout retain their plan
boundaries. Renewed background buildup or pressure requires evidence capture and a
hold, as the report specifies. The draft report's pending final-test/review rows must
be refreshed from this evidence before closeout.

## Paging-policy addendum — 2026-10-04, after the approved change

The paging-policy row above records the original review before the Windows action.
Its current configured-policy status is **Met**. Direct inspection of
[before.json](pagefile-change/before.json), [after.json](pagefile-change/after.json),
[result.json](pagefile-change/result.json) and
[verification.json](pagefile-change/verification.json) confirms that the sole
`PagingFiles` entry changed from `C:\pagefile.sys 16384 32768` to
`C:\pagefile.sys 0 0`. A separate read-only registry inspection by this reviewer
confirmed that current value and its `MultiString` type. Saved CIM evidence confirms
`AutomaticManagedPagefile=false`, with only C configured and initial/maximum settings
both zero. This is the C-only system-managed policy documented by
[Microsoft Windows Support](https://jpwinsup.github.io/blog/2023/02/08/Performance/Hang_BSOD/HowToChangePagingFileSetting/).

The helper's required evidence-persistence correction is resolved: a final result-write
failure sets a blocked result, preserves the persistence error, attempts and verifies
restoration of the original policy before disposing the registry handle, and exits
nonzero. Its final source was independently inspected before application. This review
performed no paging mutation, reboot, Git command or research-worker execution.

**Runtime capacity after reboot remains Unverified.** Both result and verification
explicitly record `RebootPerformed=false` and
`RuntimeCapacityVerifiedAfterReboot=false`; runtime allocation remains 16,384 MiB in
the saved before/after checks. Do not treat the configured setting as demonstrated
additional live capacity. The initiating external consumer and a durable system/app
crash repair also remain **Unverified**. No repeat scoring or inference is justified
by this policy change; preserve the existing Phase 2 review/closeout boundary.
