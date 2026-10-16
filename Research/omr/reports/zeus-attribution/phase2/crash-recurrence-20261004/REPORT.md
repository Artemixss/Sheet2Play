# Repeated Windows memory-exhaustion incident — 2026-10-04

The recurrence exhausted Windows system commit again. The initiating memory consumer
is **unverified**. The earlier investigation diagnosed the failure; it did not implement
a fix. Phase 2 execution is held following the user's new crash report.

Times below are Europe/Istanbul (UTC+03). Raw app timestamps are UTC.

## Confirmed evidence

| Local time | Evidence |
| --- | --- |
| 11:53:28 | Application Popup 26: Windows explicitly warned that virtual memory was exhausted and mentioned increasing the paging file. |
| 11:53:29 | Resource detector 1003: commit charge 50,540,277,760 bytes / limit 50,728,964,096 bytes: **99.628%**, approximately 179.95 MiB remaining. |
| 11:53:35–38 | Windows error reporting itself failed initialization; ASUS Wi-Fi SmartConnect crashed. |
| 11:53:45–11:57:30 | Git, Lively Wallpaper, NVIDIA Overlay and Cloudflare WARP UI crashed; Volsnap/Perflib also reported memory-allocation failures. |
| 11:55:48 | The saved continuation tool output shows at least **108 Git processes**, six console hosts and zero Python processes in its returned rows. This observation occurred **after** the first exhaustion warning. |
| 11:56:56 | Commit charge 50,684,973,056 bytes / the same limit: **99.913%**, approximately 41.95 MiB remaining. |
| 11:57:43 | Resource detector itself failed an approximately 2.22 MiB allocation (error 0x8007000E). |
| 12:05:14–41 | User32 1074 records a user-initiated restart, followed by shutdown/event-log-stop records and reboot. |

Sources: [System events](System.json), [Application events](Application.json),
[resource-detector events](Detector.json). The query started at 11:45:41, twenty
minutes before the recorded boot time; the saved capture is at 12:12:33. The first
incident has a [separate report](../crash-investigation-20261004/REPORT.md).

System commit is the memory Windows promises to applications, backed by RAM and paging
files. Reaching that limit can cause allocation failures and crashes even when a
physical-RAM-only gate has not fired. [Microsoft page-file documentation](https://learn.microsoft.com/en-us/troubleshoot/windows-client/performance/introduction-to-the-page-file).

## Attribution and limits

No Phase 2 scoring, regression or inference worker was launched during the continuation
before this recurrence. The interrupted work consisted of file reads, searches and a
process listing. Thus a new scoring/test run does not explain this incident. This does
not exonerate the desktop app's background activity associated with the repository.

The [recovered process summary](pre-restart-process-summary.json) is a lower bound from
a truncated saved tool result. Its Git rows total approximately 0.802 GiB working set
and 1.714 GiB in the recorded `PagedMemorySize64` property. These are not a complete
system-commit accounting. Parent PIDs, all other processes and earlier memory samples
were not captured. The buildup is a serious lead; neither its initiating role nor its
own source is established.

The [selected app log](app-process-errors-redacted.log) and
[command summary](git-log-summary.json) show stale Git snapshots and background
status/diff failures, including 112 selected command-completion warnings/errors (111
for this repository). This is not a count of concurrent or hung processes. Much of the
failure traffic occurred during exhaustion. Those commands already disabled hooks and
fsmonitor, so there is no evidence supporting either as the cause.

The ASUS Wi-Fi helper and WARP crashes are consistent with the user's network disruption
being part of the cascade. They do not prove corrupted drivers or settings, or explain
the initiating shortage. Brightness/display-state changes were not measured. Postboot
WER entries referencing older August/September dump filenames are not treated as new
hardware faults.

## Corruption audit and operational state

The [bounded audit](../crash-audit-20261004-02/verification.json) again verified all
**295 corrected scores and 1,257 declared artifacts**, preserved all ten failures,
independently recomputed primary/secondary metrics, and verified the report SHA-256:
`040ee6e7de58dec077ccdaa28961ee3e88a367a6dbc16931620e3df9a7cbb255`.
No corruption was found within that scope. [Audit log](../crash-audit-20261004-02.log).

[Audit wrapper](guarded_audit.py) used the existing independent verifier, streamed
artifact hashes, and sampled physical RAM and system commit every 0.5 seconds. It would
abort its own process at 90% pressure or after 120 seconds. The successful audit took
24.06 seconds: peak commit 54.71%, physical RAM 85.08%.
[Resource evidence](../crash-audit-20261004-02/resource-audit.json). This protects only
that audit; it is not a system-wide remedy or a modification of the scoring runner.

The [postboot snapshot](snapshot.json) showed zero Git processes and 49% commit at
12:12:33. C: reported healthy in NTFS events. D: still had an exFAT dirty flag. These
observations do not certify all OS/project files or portable-SSD contents. No filesystem
repair, driver change, paging-file adjustment, Git configuration change or process kill
was performed. No evidence establishes an SSD disconnection as this incident's cause.

## Required next step and acceptance

Keep Phase 2 execution held. Before further execution, review a resource-control approach
covering both system commit and background process buildup. Capture process private
memory, thread counts and parent relationships if the buildup appears, before making a
causal claim. A worker-only guard cannot prevent independent app processes exhausting
memory; increasing the pagefile alone would not establish a repair of the initiating
problem. Do not deliberately reproduce an uncontrolled system-wide crash.

Cached Phase 2 work remains reusable. Its independent implementation/statistical review
and acceptance closeout are pending. No rescoring or regression repeat is required merely
because of this crash; code changes still require the plan's relevant checks.

| Acceptance criterion | Status | Evidence or remaining issue |
| --- | --- | --- |
| Establish immediate recurrence mechanism | Met | Paging-file warning, exact commit counters and allocation failures |
| Identify initiating consumer / root trigger | Unverified | Git buildup confirmed after exhaustion; complete earlier accounting unavailable |
| Establish network disruption mechanism | Unverified | Helper/WARP crashes correlate; complete network causality unavailable |
| Audit saved Phase 2 inputs/results | Met | 295 records / 1,257 artifacts and report hash verified again |
| Certify other files, Windows or portable SSD | Unverified | Content audit limited; D: remains dirty |
| Safely resume Phase 2 execution | Unmet | Resource-control review and initiating-problem investigation remain |
| Claim a durable crash fix | Unmet | No system/app remedy demonstrated; only the audit had a bounded guard |

[Independent review](REVIEW.md) inspected the underlying events, implementation and
audit artifacts; no required correction remained. Changed guidance/report links passed
108 local-target checks. Final inspection found no Git/Python processes or worker lock.

