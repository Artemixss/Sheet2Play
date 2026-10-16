# Phase 3 execution record

Owner: [MAIN_PLAN.md](../../../../../plans/MAIN_PLAN.md),
`2026-10-06-homr-timing-465`. Authorized 2026-10-08: **Phase 3 only**.
No Phase 4, training, new dependencies/models, production edits or adoption.

Cwd: `C:\Users\bur4x\Desktop\lecture\big_projects\Sheet2Play`.
Supervisor: `Research/omr/guarded_execution.py`, research interpreter
`Research/omr/.venv/Scripts/python.exe`. `PYTHONPATH`: Phase 3 `gate`,
`Research/omr`, `Research/omr/src`, then the specific checked source when needed.
The copied offline/Git gate is isolated from frozen Phase 2 evidence.
85% RAM/commit stops, 4 GiB reserve/aggregate worker cap, 16 processes, one
worker and deadlines below four hours remain mandatory. GPU inference would
require fresh independent admission; none is planned. Keep the 5% allowance stop.

Initial PowerShell process check found no Python/dotnet/Sheet2Play worker and
no `.research-worker.lock`. CIM process inventory was unavailable in the sandbox;
the supervisor records native process/resource evidence before worker release.
No Git was invoked. Account five-hour allowance was 95% remaining at start.

Planned serial jobs: preservation snapshot (600 seconds), cached conversion/MIDI
traces (600), fixed-token native exporter replay and dependency probes in existing
research and intended app interpreters (600 each), relevant fixtures (600), full
Research/Bridge regression (1200), fresh frontend build/playback tests (600),
final preservation and documentation checks (600). Each fresh job directory
contains command/cwd, PID, source identity, full bounded log and resources.
Failures remain; inspect causes before any new attempt. No inference retry planned.

## Completed cached-first jobs

All jobs below use the recorded supervisor, output directory `phase3/jobs/<name>`,
600-second deadlines and the defaults above. No resource stop occurred.

| Job | Worker and arguments | Outcome |
| --- | --- | --- |
| preservation-before | Research `.venv` Python, `homr_465_readiness.py snapshot` | Complete: 7,630 Phase 2 files, 98 protected/pinned entries, 38 production source files |
| cached-traces | Research `.venv` Python, `homr_465_readiness.py trace` | Failed: sandbox denied Windows canonical-path resolution; not a recognition or pressure failure |
| cached-traces-approved | Same script, approved filesystem access | Complete: 12 cached conversions match frozen events; 12 exact research MIDI round trips |
| export-shared | Shared `.runtime/homr-455/venv` Python, `homr_465_export_replay.py shared` | Complete: 12 musical XML replays, native imports and dependency constraints pass |
| export-installed | `Bridge/.venv-homr-gpu` Python, `homr_465_export_replay.py installed` | Complete: same 12 replays and four-position/two-staff fixture; no inference |

The failed conversion receipt remains. `Path.resolve(strict=True)` raised WinError 5;
the file itself was readable. Automatic review approved the same offline guarded
conversion with canonical-path access. No unchanged blind retry or Git operation.

## Next downstream jobs

Inputs: `Research/omr/homr_465_playback_inputs.py`, research `.venv` Python,
`jobs/playback-inputs`, 600 seconds. It generates a separate manifest of cached
candidate XML, paired generated source XML and known-correct Bridge builders;
the known independent-voice tie limitation is explicitly retained.

Probe project: `Research/omr/probes/homr465-playback/Homr465PlaybackProbe.csproj`.
Restore only from an empty local NuGet source plus the existing package cache,
then serial build with no restore, node reuse or shared compilation. Execute
the probe DLL against `phase3/playback-manifest.json`, exclusive
`phase3/playback-results`, through the supervisor. C# invokes the actual
published Bridge using the installed HOMR interpreter for direct-XML conversion,
then calls the existing cache MIDI helpers and real controller with a fake clock/output.
No native audio device or launched GUI. Retain calibrated 0.055-second offset.

All .NET jobs: `DOTNET_PROCESSOR_COUNT=2`, `DOTNET_GCHeapHardLimit=0x10000000`,
`MSBUILDDISABLENODEREUSE=1`, one supervised worker; 600-second deadline each.
Validation: focused timing/tie/normalizer fixtures, then all Research/Bridge tests
(1200 seconds), and fresh serial frontend `dotnet test --no-restore -m:1
-nodeReuse:false -p:UseSharedCompilation=false` (600 seconds), retained XML/TRX logs.

## Demonstrated C# blocker and bounded repair

`playback-inputs` failed a new probe assertion because the golden chord notes use
a different list order. The corrected multiset comparison passed in
`playback-inputs-validated`; both the first generated directory and receipt remain.
`probe-restore` and `probe-build` completed from existing local packages (32
pre-existing nullable warnings, no errors). `playback-probe` then failed on the
first cached XML: published Bridge conversion succeeded, but C#
`OmrPipeline.ValidateResult` called `GetEngineRevision(MusicXml)`, whose missing
switch branch throws. No pressure stop; preserved receipt/stack trace.

Minimal research repair: add only `MusicXml => "direct-xml"` to that revision
switch in an exclusive source copy created by `homr_465_runtime_profile.py`.
`Homr465FrontendProfile.csproj` links unchanged frontend sources except that copy;
all package versions match production. No exporter/normalizer/timing change,
therefore no separate 59-page scoring profile is warranted. Probe rebuild uses
`-p:ResearchProfile=true`, then a new exclusive `playback-results-repaired`
directory. Explicit installed Python selection is intentional: this does not
repair or claim the whole default direct-XML runtime/cache metadata path.
Next jobs: `runtime-profile`, `probe-repaired-restore`, `probe-repaired-build`,
`playback-probe-repaired`, each supervised/offline with 600-second deadline.

The repaired probe passed all 32 inputs (12 candidate, 11 paired XML sources,
9 known-correct/limitation fixtures), including cache MIDI helpers and controller
activity/completion checks. `focused-fixtures` passed before full regression.
The default MusicXml resolver/model-cache contracts are still missing; this repair
is expressly limited to direct-XML ingestion with explicit runtime selection.

Additional frontend regression: isolated `homr465-frontend-tests` project links
every existing frontend test and adds revision/schema/remaining-boundary checks;
it references the single-branch repaired research assembly. Restore from the same
empty local NuGet source, then fresh serial `dotnet test --no-restore -m:1
-nodeReuse:false -p:UseSharedCompilation=false --logger trx` into
`phase3/frontend-test-results`. No production test/source edits.

`full-regression` completed: 417 cases, 2 skipped, 0 failures/errors.
First isolated frontend-test build failed because its source links omitted
`Visualization_engine/Properties/AssemblyInfo.cs`, which grants the existing test
assembly access to internal helpers. This was a profile-project omission, not an
application defect. Link the unchanged Properties sources and rerun as
`frontend-regression-linked`; keep the failed compile receipt. No runtime code
change or relaxation of access/validation checks.

`frontend-regression-linked` built successfully but VSTest could not connect to
its test host in 90 seconds (zero tests executed). Peak RAM 36.32%, commit 30.09%,
no pressure stop. This differs from a musical assertion failure; initiating cause
not yet verified. Preserve aborted TRX. Diagnostic execution uses the freshly
built test DLL directly (`dotnet vstest`, no repeated MSBuild), retains the same
containment/GC limits, writes `frontend-vstest-diag.log`, a new results directory,
and requests sandbox access for VSTest's localhost test-host connection.

`frontend-direct-diagnostic` completed: all 74 tests pass (69 existing plus five
research contract cases), fresh DLL from `frontend-regression-linked` build.
Diagnostics confirm a localhost connection; the preceding timeout's initiating
cause remains unverified because execution mode and access changed together.
No omitted tests, pressure retry or extended deadline. The aborted zero-test TRX
and compile-failure log remain separate from the successful TRX.

## Final acceptance audit and stop

Command (cwd above; offline gate retained):

```powershell
& Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/reports/homr-timing-465/phase3/jobs/final-audit --max-seconds 600 -- Research/omr/.venv/Scripts/python.exe -B Research/omr/homr_465_phase3_audit.py
```

Checks: every Phase 2 file and inventory, all protected/pinned and snapshotted
production-source hashes, both native replay identities, 32 playback input
identities/results, single-branch repair diff, successful JUnit/TRX counts,
every preceding receipt and resource policy, task-relevant documentation links.
The final receipt records completion/failure; [audit.json](audit.json) records
acceptance evidence. Before this last bounded audit there are no live owned
workers or lock. Stop after inspecting its receipt, checking native process/lock
closure and issuing the Phase 3 report/handoff. No Phase 4 or adoption.

First `final-audit` stopped before preservation verification because its early
link check required `preservation-after.json` before the same auditor created it.
This is a new audit ordering defect, not frozen evidence drift. Retain receipt;
defer only the two self-produced artifact links until after write, then require
all links to exist. Repeat the changed auditor as `jobs/final-audit-ordered`,
same command/600-second/default limits. Six prior failed receipts are retained.
The installed music21 distribution inventory is 10.5.0 versus scoring 9.9.1;
the 32 exact JSON agreements are bounded compatibility evidence across that difference.
