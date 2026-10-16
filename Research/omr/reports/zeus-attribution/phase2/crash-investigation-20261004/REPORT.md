# Windows crash investigation — 2026-10-04

**Finding:** Windows exhausted system commit memory between 00:21 and 00:24 local
time (Europe/Istanbul, UTC+03). This caused application allocation failures and
terminated the desktop compositor. The process that consumed the memory is unknown.
The checked Phase 2 artifacts survived and can be reused; phase closeout remains pending.

## Evidence and limits

The user recalled approximately 00:30, unknown hexadecimal error popups, altered
brightness, a black screen, and an earlier remote-connection failure. The
[System events](System.json) and [Application events](Application.json) were queried for
23:30 on October 3 through 01:00 on October 4. Returned System records span
23:58:55–00:28:32, and Application records 23:31:15–00:28:29.
Event XML supplies precise timestamps;
older Windows Error Reporting file timestamps were not treated as incident times.

| Local time | Evidence | Interpretation |
| --- | --- | --- |
| 00:21:11 | Resource Exhaustion Detector event 1003: commit charge 50,650,583,040 bytes, limit 50,728,964,096 bytes | 99.845% committed; only 74.75 MiB remained |
| 00:21:23, 00:21:25 | Desktop Window Manager exits with `0xc00001ad` | Fatal memory exhaustion; directly supports the black-screen symptom |
| 00:21:25 | Codex package's `ChatGPT.exe` crashes with `0xe0000008` in KERNELBASE.dll | App failure during the cascade; module/exception alone does not identify its initiating cause |
| 00:24:06 | Detector event 1003: charge 50,667,327,488 bytes, same limit; event 1007 fails a 1,629,600-byte allocation | 99.878% committed, 58.78 MiB remaining; even the detector could not allocate memory |
| 00:24:06–00:24:29 | PerfProc/TermService allocation failures, Gaming Services reports pagefile too small, repeated Git/conhost and Cloudflare WARP crashes | Independent corroboration of widespread memory failure; WARP failure could also disrupt networking then |
| 00:24:39 | Power-button timestamp recorded in subsequent Kernel-Power 41; bugcheck code zero | Consistent with power-button intervention to recover the hung machine; no recorded blue-screen code |
| Around 00:25 | Boot events and unexpected-shutdown record | Reboot after the failure; event 41 does not establish an originating power fault |

Exact memory measurements are in [Operational-Detector.json](Operational-Detector.json).
The 47.245 GiB historical commit limit is consistent with physical RAM plus a
32 GiB pagefile. The later snapshot's 16 GiB pagefile allocation is post-reboot state.
Microsoft explains that the commit limit combines RAM and pagefiles and that exhausting
it can freeze/crash applications. [Pagefile documentation](https://learn.microsoft.com/en-us/troubleshoot/windows-client/performance/introduction-to-the-page-file)
The SDK defines `0xc00001ad` as `STATUS_FATAL_MEMORY_EXHAUSTION`.
[Microsoft status definitions](https://github.com/microsoft/win32metadata/blob/main/generation/WinSDK/RecompiledIdlHeaders/shared/ntstatus.h)
Power-button and event-41 interpretation follows
[Microsoft's guidance](https://learn.microsoft.com/en-us/troubleshoot/windows-client/performance/event-id-41-restart).

No usable incident dump or top-consumer event was found. Git/conhost's stack-overflow
and access-violation exceptions do not establish that they consumed the missing memory.
Neither Phase 2, Codex, a driver nor defective RAM is established as the initiating cause.
The brightness change is compatible with compositor disruption, but its mechanism is
unverified. No display-driver reset, WHEA or disk error was found in the scoped window;
this absence does not rule out every hardware or transient USB fault.

## Remote connection and portable SSD

[Redacted app-log excerpts](remote-errors-redacted.log) already report another configured
remote environment offline between 23:00 and 23:58, before the local memory cascade.
Repeated broadcast messages are not unique connection attempts. Its root cause is
unresolved; later WARP crashes cannot explain the earlier failure by themselves.
Official remote availability requires the other host to remain awake, online and running
the app. [Remote connections](https://learn.chatgpt.com/docs/remote-connections)

The [post-reboot snapshot](system-snapshot.json) reports:

- Internal C: NVMe disk and NTFS volume healthy, approximately 61.6 GB free.
- Portable D: Samsung T9 USB disk reports healthy, but its exFAT volume is dirty,
  with `Warning` / `Full Repair Needed`, approximately 125.5 GB free.
- The repository, research interpreter and pagefile are on C; checked repository and
  interpreter paths are not junctions to D.

There is no demonstrated causal link from D to this crash. Its dirty flag is a genuine
unresolved filesystem concern, not proof that particular files were corrupted.
A read-only `chkdsk D:` attempt returned Windows administrative access denied; no
filesystem diagnosis or repair completed. The empty `chkdsk-D-readonly.log` from the
first launch attempt is not a successful check. Back up important D files before any
separately authorized filesystem repair. No drive, driver, pagefile or app setting changed.

## Phase 2 integrity and continuation

The cached rescore finished at 00:17:49, report at 00:17:54, and full regression at
00:18:19, before the first recorded exhaustion at 00:21:11. A fresh independent audit
using the existing verifier passed: [verification.json](../crash-audit-20261004-01/verification.json),
[log](../crash-audit-20261004-01/verification.log).

- All 295 score/result records and 1,257 declared artifacts verified; ten failed
  outcomes remain included. Primary and secondary metrics were independently recomputed.
- Historical NED, status, errors and runtime were preserved. There are 31,497 timing
  reconstructions counted across checked arrays; this is not a unique-note count.
- Corrected report SHA-256 matches
  `040ee6e7de58dec077ccdaa28961ee3e88a367a6dbc16931620e3df9a7cbb255`.
- No worker lock, incomplete/temp score file or matching live research worker was found.
- `git fsck --connectivity-only --no-reflogs --no-dangling` exited zero;
  [log](git-fsck.log) is empty. This checks Git connectivity, not every blob's contents.
- Saved regression evidence is 267 passed, 2 skipped, 9 subtests passed, with one
  expected unreadable-clef warning; focused timing fixtures are 16 passed.

No corruption was found within the audited research inputs and outputs. This does not
certify all Windows files, other untracked project files or portable-SSD contents.
Do not repeat completed scoring/tests solely because of the crash. Resume from
[the Phase 2 handoff](../handoff.md) for implementation/statistical review and acceptance
closeout when the user continues. Before another heavy job, add a system-commit pressure
check alongside the existing 90% physical RAM/device-VRAM safeguards; physical RAM
percentage alone does not cover the observed failure. This investigation changed no runner
or frozen identity and did not start inference or later phases.

## Investigation acceptance

| Criterion | Status | Evidence or remaining issue |
| --- | --- | --- |
| Establish immediate crash mechanism | Met | Exact commit counters, DWM fatal-memory status and multiple allocation failures |
| Identify initiating memory consumer | Unverified | Historical per-process commit/dump unavailable |
| Explain black screen | Met | Desktop compositor terminated due to memory exhaustion |
| Explain brightness alteration | Unverified | No measurement or display-state record |
| Establish earlier remote failure's cause | Unverified | Offline status predates local cascade; other host not inspected |
| Audit preserved Phase 2 work | Met | Fresh 295-record / 1,257-artifact verification and report hash |
| Determine Phase 2 continuability | Met | Cached work reusable; review/closeout pending, no worker/lock |
| Certify portable SSD filesystem | Unverified | Dirty flag; administrative access prevented filesystem check |
| Protect future heavy jobs against commit exhaustion | Unmet | Required safeguard identified, implementation deferred to continuation |

