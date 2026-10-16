# HOMR 465 app integration handoff

Owner: [MAIN_PLAN.md](../../../../plans/MAIN_PLAN.md),
`2026-10-09-homr-465-app-integration`.

## Authorized objective and status

The user requested implementation of the main plan on 2026-10-09. All four
phases are authorized in sequence, subject to their acceptance gates. Phases 1–2
are complete; Phase 3's batch is complete, but fresh-process resume and final audit
are pending. Execution stopped at the selected 5% remaining usage threshold.
Exec session 51352 exited 0; `phase3/jobs/library-migration` is complete with no
live worker/lock. Phase 4 is pending. No delegation or model change.
The initial sections below retain dated preparatory history; the latest phase
records and main plan own current status. Do not launch a second migration copy.

Initial preflight found no Python/dotnet/Sheet2Play worker or active research
lock, 32 GiB usable RAM, about 19 GiB free RAM, about 31% commit use and zero
GPU use. The sandbox denied CIM; approved read-only CIM/GPU inspection passed.
The working tree has extensive prior research edits; preserve them. Branch is
main, remote is https://github.com/Artemixss/Sheet2Play.git.

Five-hour allowance was 20% remaining initially, 5% at the final boundary.
Execution stopped at the selected usage limit. No new job until allowance relief;
do not weaken validation or mark work done. Authorization remains unchanged.

## Execution contract

Workspace: `C:\Users\bur4x\Desktop\lecture\big_projects\Sheet2Play`.
Run substantive jobs serially through `Research/omr/guarded_execution.py` with
`Research/omr/.venv/Scripts/python.exe`; add `Research/omr/src` to PYTHONPATH.
Use fresh directories under `phase1/jobs`, retain worker logs/results/resource
receipts, 85% RAM/commit, 4 GiB reserve/worker, 16 processes and bounded deadlines.
GPU inference separately requires 90% VRAM admission and no training competitor.
Never retry a pressure failure automatically. Native capture ceiling is 64.

Initial jobs: snapshot/preflight (600 seconds), local runtime provisioning (600),
contract fixtures (600), representative inference (600), bounded development
qualification (3600), downstream playback manifest (600), full relevant
regression (1200), frontend tests (600). Record exact commands in each supervisor
receipt before worker release. No installed-app or real-library writes yet.

## Completed implementation and evidence

Snapshot job completed: 108 files, including 65 private settings/cache metadata
files. Snapshot stays ignored under `phase1/snapshot`. Local pinned runtime was
provisioned into ignored `Bridge/.runtime/homr-465`; 426 assets are preserved.
Profile regeneration `profile-final` produced the initial identity. The first app
probe found missing psutil before native inference. `local-psutil-provision`
reused/verified already-local psutil 7.2.2 files after matching both Python 3.11.9
64-bit signatures; no download or existing-package replacement. `profile-psutil`
pins this dependency and generated `Bridge/requirements-homr465.txt`. Current
profile SHA-256 is
`1fd5b26e461688307b7480fe8c1e7bb959152b8436fc8c64fbe4141629f1ac46`.

Implemented isolated offline CUDA launcher, portable enforced supervisor,
schema-2 optional model/profile identity, visible 465/426 selector and recovery,
scratch settings path, source/profile cache identity and external publish assets.
Added Bridge and frontend contract tests. Production default still 426. Native
captures: 1/64. No publishing, real metadata writes, migration or Git delivery.

`bridge-focused` failed on sandbox temporary-path access; approved access resolved
that. `bridge-focused-approved` then had eight passes/three subtests and one new
test constructor error, now fixed (missing required NormalizedScore fields).
`frontend-focused` failed on PowerShell argument splitting; corrected switches
compiled both projects in `frontend-focused-arguments-fixed`, then VSTest child
creation failed with Windows error 1816. Peak RAM 38.89%, commit 31.74%, no pressure
stop, no cleanup error. Initiating cause is unverified; do not call this proven
system commit exhaustion. Keep every failed receipt. Fresh approved inspection
found no Python/dotnet/testhost/Sheet2Play workers or research lock, about 19.6 GiB
free RAM, commit about 31%, and GPU idle. No Git invoked during recovery.

`bridge-focused-fixed` passed nine tests/three subtests. `frontend-direct-diagnostic`
passed all seven new contract cases under unchanged limits and approved localhost
access. Earlier Win1816 initiating cause remains unverified; direct-DLL execution
resolved the immediate test launch. The profile constant changed after these
frontend tests; rebuild and retest the current source before acceptance.

`representative-native-465` failed CLI parsing (--input instead of positional),
zero model calls. `representative-native-465-positional` found missing psutil,
zero native calls. `representative-native-465-provisioned` completed: one baseline
piano image, 56 normalized notes, correct 465 source/model/current profile, all
three model sessions CUDA first, isolated module origins. Outer elapsed 21.625s,
peak RAM 41.68%, commit 38.85%, no stop. Output saved as
`phase1/representative-native-result.json`; inner receipt under scratch-library/
omr-jobs. Both supervisor locks removed. Known musical errors remain unresolved.

`full-python-regression` launched with 1200-second deadline, command
`Research/omr/.venv/Scripts/python.exe -B -m pytest Bridge/tests Research/omr/tests -q`.
Completed with exit0, no stop, elapsed34.203s. Receipt and full diagnostics retained;
do not rerun without a relevant change. No active supervisor/lock remains.

## Next action

### Resumed 2026-10-09

User requested `continue`; five-hour allowance reset (100% remaining at resume).
Fresh approved preflight found no relevant worker or lock, GPU idle, about15GiB
free physical RAM and commit below50%. Resume the same four-phase authorization.
Current frontend build runs in `phase1/jobs/frontend-current-build`, deadline600s,
then direct-DLL full test execution. Preserve preceding usage-stop evidence.

At resume, inspect live jobs/locks and allowance. Rebuild current frontend (quoted -m:1,
-nodeReuse:false, -p:UseSharedCompilation=false; processor count2, GC heap0x10000000),
then direct `dotnet vstest` full suite in a separate supervised job with approved
localhost access. Keep all safeguards. Follow with bounded matched no-title465/426
development qualification (proposed 12 generated + two OpenScore pairs, not yet
selected/executed), 32-input downstream manifest using production frontend/profile
and current Bridge paths. No frozen59-page rerun. The representative scan is not
matched qualification or release acceptance. Phase 2-4 remain pending.

## Phase 1 completed; Phase 2 active (2026-10-09)
Current frontend build and full direct-DLL test run passed (76 tests). Matched
qualification completed 28/28 captures; total Phase 1 count29/64. Analysis found
no new musical-event differences and p95 ratio1.220943. Production 32-input
playback probe passed. No live job/lock remains. See REPORT.md for acceptance.
Next authorized action: scratch published-app verification, then full actual
release gate and one-time real saved engine update after gates. Production
default still426 at this boundary. Phase3/4 are pending. Allowance93% remaining.


Phase2 scratch gate command: guarded_execution.py --output phase2/jobs/scratch-release --max-seconds1200 -- powershell -ExecutionPolicy Bypass -File scripts/verify-release.ps1 -OutputPath tmp/homr465-scratch-app. Cwd repository; logs in supervisor job/worker.log and tmp/homr465-scratch-app/_verify. Library phase2/scratch-library and settings phase2/scratch-settings/settings.json are absolute overrides. No bypasses. Reinspect receipt before launching dependent app verification.

Scratch release passed76 tests/build but asset hashing failed before app launch: Get-FileHash unavailable in child Windows PowerShell. Replaced with .NET SHA256 API; no native capture. Retain failed receipt. Re-run full gate in fresh phase2/jobs/scratch-release-hash-fixed; same1200sec limits and scratch overrides.
Scratch full gate passed all7 steps (76 tests); app screenshot tmp/homr465-scratch-app/_verify/launch.png. Next supervised scratch native: published EXE --verify-omr baseline image Homr465 phase2/scratch-scan, 600sec, same overrides; then separate-process reopen and direct XML import/smoke.
Scratch native scan succeeded56 notes and published isolated CUDA origins; fresh-process reopen retained MIDI/settings. Direct XML import then exposed pre-existing GetModelRevision/GetOmrSettings missing MusicXml; fixed both with regression test. Rebuild/release scratch in fresh job scratch-release-xml-fixed (1200sec); preserve partial persistence job/output, then new suffix directories for remaining verification. No resource stop.
Current scratch gate passed77 tests/all7 steps; published restart/426 persisted selection/XML scan-cache/UI smoke all passed. Inspected native preview and visible Retry HOMR426 error screenshot. Before actual gate, full installed release+private metadata backup: guarded integration_release_backup.py, phase2/jobs/installed-backup, deadline600sec, exclusive phase2/installed-backup destination. No real writes yet.
Full installed backup passed. Actual gate command: guarded_execution.py --output phase2/jobs/installed-release --max-seconds1200 -- powershell -ExecutionPolicy Bypass -File scripts/verify-release.ps1 (no bypass); cwd repository, explicit real home/settings paths. Logs job/worker.log and dist/_verify. Gate closes app after screenshot. Next compare real metadata/settings to backup, then one-time saved engine update and actual EXE matched inputs/reopen; preserve older versions.
Installed full gate passed all7 steps/77 tests; dist/_verify/launch.png, no bypass. Next guarded real settings one-time update after semantic equality with backup: integration_installed_verify.py select, phase2/jobs/real-engine-selection, 600sec; only omr_engine changes. Then published fourteen development inputs in separate qualification library (per-item fresh guarded jobs <=600sec, runner session <=3600sec), same matched no-title426 controls from Phase1. Actual private-library scan/reopen still follows.

## Current boundary — Phase2 accepted, Phase3 active (2026-10-09)
Actual full release gate passed all7 steps/77 tests. Saved real engine changed only once to465; all other settings preserved. Fourteen installed development scans completed (session18931 exit0); native p95 10.81485sec/control13.5225 ratio0.799767. One real retained private PDF scan produced291 notes; separate-process restart/reopen retained identical MIDI/manifest, all177 old/source/rootmetadata file hashes unchanged. Native captures45 overall (29 Phase1,1 scratch,14 installed,1 private). No active job/lock. Evidence phase2/installed-latency.json, private-verification.json and fresh supervisor jobs; private names remain ignored. Phase1/2 complete. Exact next action: implement/test/publish --reconvert inventory/resume, freeze expected57/266+two orphans, then supervised serial migration preserving old caches and recent order/time. Phase4 pending. Previous initial/pending text above is dated history, not current work. Five-hour allowance79% remaining at last boundary.
Phase3 development jobs: migration-build and migration-current-build (600sec, dotnet build Release tests, 2processors/256MiB GC, single MSBuild node), inventory-fixtures (600sec, first2passed/1skipped because research interpreter lacks PyMuPDF). PDF fixture now exercises the already-provisioned app interpreter, no installs. Next migration-focused-test: guarded direct dotnet vstest current Release DLL, filter LibraryMigrationTests|Homr465IntegrationTests,600sec. Then full Python regression including new inventory fixtures; full actual release gate (no bypass), freeze real inventory and review57/266+two orphan identities before inference. No batch started. All commands/logs in fresh supervisor receipts.
Migration focused current frontend fixtures passed18/18. Current full Python regression completed; no heavy work launched concurrently. Next installed migration release: guarded_execution.py --output phase3/jobs/migration-release --max-seconds1200 -- powershell -ExecutionPolicy Bypass -File scripts/verify-release.ps1, cwd repository, real home/settings absolute overrides. Full gate, no bypass, unchanged recognition profile. After successful gate: supervised actual EXE --reconvert inventory exclusive phase3/inventory.json (600sec), review expected59old records/57recoverable/266pages/two source-and-MIDI orphans. All private paths remain ignored.

## Active Phase3 batch command (2026-10-09)
Freeze succeeded:59 manifests,57recoverable scores/266pages,two source orphans. Correction to earlier inventory wording: one orphan retains a MIDI file; one lacks MIDI. Both lack matching retained sources and remain unavailable; preserve both records and the retained MIDI. Inventory: phase3/inventory.json. Current actual release: all7steps/87tests passed; screenshot dist/_verify/launch.png visibly selects465. Focused18tests and current Python regression passed. No fresh scientific inference.
Fresh approved preflight: no relevant workers, no root/native lock, RAM41.38%/18.32GiB free, virtual use37.10%,GPU0MiB/0%. Allowance71%remaining. Recents-before.json preserves all10 entries; settings-before.json will preserve post-selection settings.
Command: Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/reports/homr-465-app-integration/phase3/jobs/library-migration --max-seconds14400 -- dist/Sheet2Play.exe --reconvert resume Research/omr/reports/homr-465-app-integration/phase3/inventory.json Research/omr/reports/homr-465-app-integration/phase3/journal.json
Cwd repository. PYTHONPATH Research/omr/src; SHEET2PLAY_HOME and SHEET2PLAY_SETTINGS_PATH explicitly real C:\Users\bur4x\AppData\Local\Sheet2Play paths. Root supervision85% RAM/commit,4GiB reserve/aggregate worker,16processes,4h; inner page limits/GPU90% unchanged. Progress journal atomically records each item; logs phase3/jobs/library-migration/worker.log and native library omr-jobs receipts. One score at a time. Review any failed/blocked root receipt before resuming; never pressure retry automatically.
Batch launch14400sec was rejected by SafetyLimits before any worker or native capture. Configuration failure, no resource pressure. Preserve phase3/deadline-rejection.json. Correct command uses14300sec (strictly below4h); same fresh library-migration job directory, original inventory/journal, limits unchanged. Checkpoint recorded this correction before release.
Live batch session51352; supervisorPID27548. Current checkpoint refreshed with exact command and post-batch audit/resume actions. Do not start another copy.

## Live batch review and audit preparation (2026-10-09)

At the latest review, 25 scores succeeded, one failed and 31 remain pending;
the two source orphans are unchanged. The ordinary failure is a native HOMR
MusicXML exporter assertion at `music_xml_generator.py:795` for a nonpositive
group duration. Its retained native receipt has the correct profile/source/model
and three CUDA-first sessions; it is not a resource or identity interruption.
Keep the failed old cache/reference and do not retry it implicitly.

The local audit script now checks all migration identities/hashes, all 62
pre-existing cache manifests, the Phase 2 original-file baseline, exact recent
timestamps/order, settings and every native receipt. It also requires a separate
successful resume with every success reused from the journal and no inference.
Run only after the batch and fresh-process resume finish. Failed receipts remain.

Resource timestamps jumped from roughly 02:43 UTC to 15:48 UTC without comparable
page-processing progress. The initiating cause is unverified. The recorded
supervisor still enforces its unchanged 14,300-second deadline using monotonic
elapsed time; do not infer batch duration from that UTC discontinuity. Last RAM
sample was about 56%, with no stop. Five-hour allowance is 50% remaining, above
the selected 5% stop. Git delivery has not begun.

## Final batch review and queued acceptance checks (2026-10-09)

Latest journal review: 55 successes, one ordinary exporter failure, one pending
ten-page score and two source orphans. The original supervisor is still running;
the user's chat interruption did not terminate it. Do not launch another batch.
The post-batch audit now attributes native receipts to each terminal score,
requiring exact page coverage for every fresh success and explicit partial
coverage for the failed score. All private paths remain ignored.

After the original result is complete and its locks/workers are gone, run this
fresh-process resume from the repository with the same explicit real library and
settings environment, `PYTHONPATH=Research/omr/src`, unchanged EXE and inventory:

```powershell
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/reports/homr-465-app-integration/phase3/jobs/library-migration-resume --max-seconds 600 -- dist/Sheet2Play.exe --reconvert resume Research/omr/reports/homr-465-app-integration/phase3/inventory.json Research/omr/reports/homr-465-app-integration/phase3/journal.json
```

Then run the read-only audit, retaining its result and complete diagnostics:

```powershell
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/reports/homr-465-app-integration/phase3/jobs/migration-audit --max-seconds 600 -- Research/omr/.venv/Scripts/python.exe -B Research/omr/integration_migration_audit.py
```

Both jobs are serial, with the recorded 85% RAM/commit stops, 4 GiB reserve and
worker cap, containment and deadlines. Do not retry a pressure stop. Only after
these acceptance checks pass may the authorized focused Git delivery begin.

## Current stop — batch complete, acceptance checks pending (2026-10-09)

The root receipt is complete, exit 0, no stop reason. Monotonic elapsed time is
5,734.766 seconds; peak physical RAM 61.5648%, peak commit 57.2948%. The original
exec session 51352 is closed, and both root/native worker locks are absent.
Journal totals: 56 successes / 258 pages, one failed eight-page score, two source
orphans and zero pending entries. One Phase 2 candidate cache was reused. Native
logs contain 262 completed receipts and one failed receipt; the failed score
completed five pages, failed on page six, and left two pages unattempted.

Codex allowance is 5% remaining (95% used), so no resume/audit or Git job was
started. The batch is fully accounted; Phase 3 is not yet accepted. After allowance
relief, execute the two queued commands above in order, review their receipts and
`phase3/audit.json`, then proceed to focused Git delivery. The audit script's new
per-score receipt attribution has not executed yet. Preserve any failed audit
receipt and diagnose before retrying. Do not rerun recognition or the release gate
without a relevant change. The installed app was closed by the release gate;
normal GUI relaunch and whole-plan closeout remain part of final delivery.
