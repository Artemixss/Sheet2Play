# Canonical Stage 3 — Audiveris/Zeus and consolidation, 2026-09-29

Working directory: `C:\Users\bur4x\Desktop\lecture\big_projects\Sheet2Play`.
The user authorized Audiveris and Zeus and completion of canonical Stage 3. Scope is
the existing **59-page / 18-composition bounded screen**, not the retired exhaustive
Phase-3 sequence. Publish the consolidated report after both candidates, preserve all
HOMR baselines, then stop before confirmation, training, GPU migration or promotion.

## Configuration and preflight

- Fresh manifest: `../manifest-v4-309c090225de.json`, SHA-256
  `f8f1c6a08caa30b63d3e31c3f11c7e2cc74643b977429e50152007c0504fb5ea`.
- Sample `2c98d5638c368b1a53bdb3440177d04fa585f9b1ca6ce6adbe65af64cd8e27d1`,
  unchanged source/reference/scorer/protocol and 90% resource policy.
- Audiveris configuration `45869993de0bd08fcf9ff3573bec1d42b603600f113a90d0fb7c59b10c222174`;
  Zeus `0ba47716087d111ece939d565ff8844748156990e4974ee0c3def6dd07fd3cb2`.
  The older v4 manifest failed verification because it pins the obsolete runner
  `998f791f9fc6`; current unchanged runner is `632818152cb3`. No model/source/metric
  setting was selected from frozen predictions. Preserve the old manifest.
- One candidate/scorer, five-page maximum chunk, eight CPU affinity/thread limits,
  below-normal priority, five-second sampling, 30-second pressure window and four-hour
  cumulative inference/scoring session. System RAM and device VRAM admission are 90%;
  frozen practical eligibility remains separate. No parallel model/scoring jobs.
- Audiveris is the native 5.11.0 CPU page route. Zeus is the corrected neutral CPU
  recognizer, **not the direct app extractor**. TensorFlow 2.12.1 reports zero GPU
  devices. Its existing HOMR detector uses the GPU; this stage is preserved rather
  than porting Zeus recognition. Retain detector/crop/native LMX/per-system XML/join
  and shared-normalization evidence.
- Initial resources: RAM 64.9%, VRAM 0/6,141 MiB, free disk 60.7 GB, no worker/lock.
  Both candidate probes passed. Musical preservation, coordinate, failure/scoring and
  CPU profile fixtures: **29 passed**; log `fixtures.log`. Runtime log `zeus-runtime.log`.
- The old HOMR development tool is itself pinned by fine-tune provenance. It remains
  untouched. New CPU-only admission entry and runtime profile are separately hashed
  in preflight/job/development sidecars. Java active processors and TensorFlow/native
  thread caps implement the manifest's eight-CPU policy. CUDA visibility is preserved
  for the existing detector. Do not change these helpers while jobs are running.

Two initial log pipelines failed because this new directory was missing. The directory
was created, then the fixtures/runtime checks reran successfully with retained logs;
no model inference occurred in either attempt.

## Exact development commands — before any screening

```powershell
Research/omr/.venv/Scripts/python.exe -B Research/omr/screening_cpu_profile.py -- Research/omr/screening_cpu_development.py --manifest Research/omr/reports/screening/v1/manifest-v4-309c090225de.json --candidate audiveris_page --item-id openscore-6211535-page-1 --session-id stage3-audiveris-dev-01
Research/omr/.venv/Scripts/python.exe -B Research/omr/screening_cpu_profile.py -- Research/omr/screening_cpu_development.py --manifest Research/omr/reports/screening/v1/manifest-v4-309c090225de.json --candidate zeus_page --item-id openscore-6211535-page-1 --session-id stage3-zeus-dev-01
```

Execute sequentially, retaining `audiveris-development.log` and `zeus-development.log`.
Before each launch recheck live processes/lock and resources. The development page is
from the frozen disjoint development set. Only a successful complete-page result with
matching source/input/configuration/artifact/CPU witnesses can be freshly admitted via
`screening_admit.py`; record the returned admission path/hash before inference. A failed
development gate blocks that candidate, not the next ready one.

## Planned execution and resume boundary

Audiveris first, Zeus second. Sessions `stage3-audiveris-screen-01` and
`stage3-zeus-screen-01` are separate cumulative ledgers under `../2c98d5638c36/sessions/`.
Use the CPU profile wrapper for unchanged `screening_run.py` and `screening_score.py`.
Start with one five-page chunk; give measured timing to the user before starts
6,11,16,21,26,31,36,41,46,51,56. Save inference logs here and per-item attempt evidence
under the sample root. Stop the parent on nonzero exit/pending outcome; never relaunch
a duplicate. Typed completed model failures retain frozen penalties, while resource
or session interruption stays pending and must not be scored zero.

After all 59 outcomes/artifact hashes verify and the lock is gone, score with the same
candidate session. No overlap. Preserve every partial attempt, score and immutable
summary. Record wrapper command/source/profile hashes, manifest/admission identity,
working directory, log, parent session ID and worker PID/creation-time evidence before
long jobs. On interruption inspect live lock/PID, ledger and staged/completed hashes
before an identical resume. Historical HOMR results remain under their original
manifests; reverify their three complete result/score sets instead of rerunning them.

Exact next action: fresh Audiveris representative development, verify/admit, first
five-page chunk and measured estimate. Zeus development/inference follows sequentially.
The consolidated report must use compatible sample/scorer identities across manifests,
all five candidates, exact composition superiority tests/10,000 bootstrap intervals,
Holm correction, failures, duration matrices/baselines, feature/resource evidence and
training-overlap disclosure. Do not run a confirmation merely because it is recommended.

## Audiveris development access failure — preserved, no screening

The first development command exited with no passing report. The worker exited zero
after recording a typed `AUDIVERIS_FAILED`; JVM startup failed before recognition:
`java.lang.InternalError: Error loading java.security file`, caused by
`java.nio.file.AccessDeniedException` on its bundled
`Research/omr/.runtime/phase2r/audiveris-extract/Audiveris/runtime/conf/security/java.security`.
Attempt/logs are preserved under `../2c98d5638c36/development-attempts/audiveris_page/`
with session `stage3-audiveris-dev-01`. Elapsed worker 5.594 seconds, RAM 66.6%, zero
VRAM use, no resource interruption. No admission or frozen Audiveris page exists.
Check permissions/sandbox access before a changed retry; do not count this runtime
failure as a screening model failure or alter Java security/model files.

## Readable execution profile — new v5 identity, no historical mutation

The approved unsandboxed retry `stage3-audiveris-dev-02` stopped at the historical
freeze guard before launching a model: [log](audiveris-development-02.log). A read-only
[visibility audit](runtime-visibility-difference.json) found **33 additional readable
distribution metadata entries**; every non-inventory field and every previously
recorded package version matched. No dependency installation, source/model change,
parser change or freeze rewrite was performed. The old inventory is preserved.

New CPU-only runner, scorer, admission/development entry and manifest verifier retain
the existing storage, failure, scoring and resource semantics. They pin the full
readable runtime, explicit Java/TensorFlow/native CPU environment and source hashes.
JVM security/launch/access failures now stay pending as infrastructure failures.
All subsequent CPU commands execute in the approved fully readable local context;
new manifest verification requires its complete inventory to match exactly.

Active manifest: `../manifest-v5-1437bf709b62.json`, SHA-256
`c7883b0456872edfb9470ad30ee3fb3d825521165815f786e5bf2f8e37478ddc`.
The earlier v4 CPU candidate identities are superseded without frozen inference.
Sample, scoring, weights, decoder, preprocessing and 90% policy are unchanged.
Fixtures passed: 17 profile/manifest/join/failure tests, followed by 11 tests after
adding explicit JVM-infrastructure classification. Logs `readable-fixtures.log` and
`profile-manifest-fixtures.log`. The full research regression follows development.

Exact fresh Audiveris development command:
`Research/omr/.venv/Scripts/python.exe -B Research/omr/screening_cpu_profile.py -- Research/omr/screening_cpu_development.py --manifest Research/omr/reports/screening/v1/manifest-v5-1437bf709b62.json --candidate audiveris_page --item-id openscore-6211535-page-1 --session-id stage3-audiveris-dev-03`.
Log `audiveris-development-03.log`; same working directory, exclusive lock and resource
limits. Preserve all earlier failures. Verify the returned result/CPU sidecar and
admit through `screening_cpu_admit.py` before frozen screening. Zeus uses this same
manifest and profile after Audiveris closes. Do not use the obsolete v4 commands above.

The v5 attempt `stage3-audiveris-dev-03` stopped before inference because the legacy
policy checker accepts schema 4 only and mislabeled the new schema as historical 75%.
The CPU-only checker now explicitly requires schema 5 and the identical full 90%
policy. Policy/metadata/infrastructure fixtures passed **12 tests**. Preserve the
superseded v5 manifest and failed log; neither produced a model result.

**Final active CPU manifest:** `../manifest-v5-607ff64134da.json`, SHA-256
`c3f28ec525ada8902203caf919da3ecdf4e75db30b84fd2379a4edb30483bc22`.
Exact development command now:
`Research/omr/.venv/Scripts/python.exe -B Research/omr/screening_cpu_profile.py -- Research/omr/screening_cpu_development.py --manifest Research/omr/reports/screening/v1/manifest-v5-607ff64134da.json --candidate audiveris_page --item-id openscore-6211535-page-1 --session-id stage3-audiveris-dev-04`.
Log `audiveris-development-04.log`, approved readable local context. No model settings
were tuned, no benchmark page ran, and no original source/freeze/scoring file changed.

## Audiveris admitted; first screening chunk next

The readable development path passed in **25.594 seconds**, RAM 72.7%, zero VRAM,
no interruption; eight-CPU affinity, explicit runtime caps and below-normal priority
verified. Report `../2c98d5638c36/development/audiveris_page/3f340c6bab3e/openscore-6211535-page-1.json`.
Final configurations: Audiveris `3f340c6bab3e8884240da3a2ffdec61b0bd98ebcf81788d3725d08a9aa5ef137`,
Zeus `81f73b31179a40bf63c608d9adea99f546dac49e57722d436dae205a1b135821`.
Fresh Audiveris admission `../2c98d5638c36/admissions/audiveris_page/3f340c6bab3e/admission-a1a64e391072.json`,
SHA-256 `3f62b883c3871ff1dd43f433a8424bcc6d0f35ddcd414bf124f1dd269d71b980`.
Full research/bridge regression is running in parent exec session **22375**, log
`regression.log`; require it to pass before the first frozen screening chunk.
User provisional estimate: **60–100 minutes** Audiveris including scoring, refined
after the first five pages. Zeus timing is not yet measured under its new profile.

Exact first Audiveris screen command, only after regression passes:
`Research/omr/.venv/Scripts/python.exe -B Research/omr/screening_cpu_profile.py -- Research/omr/screening_cpu_run.py --manifest Research/omr/reports/screening/v1/manifest-v5-607ff64134da.json --candidate audiveris_page --admission Research/omr/reports/screening/v1/2c98d5638c36/admissions/audiveris_page/3f340c6bab3e/admission-a1a64e391072.json --session-id stage3-audiveris-screen-01 --start-index 1 --max-items 5`.
Run in approved readable context, root working directory, log `audiveris-infer.log`.
Only this candidate runs. Preserve the same admission/profile/manifest and cumulative
ledger on continuation; inspect active PID/creation time/lock before any restart.

Full regression session 22375 exited zero: **231 passed, 2 skipped, 9 subtests passed**,
one expected music21 unreadable-clef fixture warning, 24.38 seconds. The first frozen
chunk is now authorized through all entry gates. No original helper/source identity
changed; only the new versioned CPU execution helpers were added.

## First Audiveris chunk verified; continuation

Parent exec 80268 exited zero. All five immutable results, identities and declared
artifact hashes verified; four successes and one typed AUDIVERIS_FAILED recognition
failure on Beethoven sonata05_1_2 are retained. Audit audiveris-first5-audit.json.
Session is closed at 200.766 seconds; no live Python/Java candidate or worker lock.
Peak RAM 74.8%, VRAM 0 MiB, no interruption. Estimate 40–60 more minutes including
scoring, provisional from five pages.

Continue sequential starts 6,11,16,21,26,31,36,41,46,51,56 with the exact prior
CPU profile/run command, unchanged v5 manifest/admission/session and max-items 5.
Append audiveris-infer.log. Parent stops on nonzero exit OR any pending JSON outcome;
never skip pending pages. After 59 verified outcomes, run the CPU profile wrapper
with screening_cpu_score.py --manifest Research/omr/reports/screening/v1/manifest-v5-607ff64134da.json
--candidate audiveris_page --session-id stage3-audiveris-screen-01, log audiveris-score.log.
The same four-hour cumulative session includes all chunks and scoring.

Continuation parent exec session 54939 is active. Initial CPU runner PID 26000,
creation_time 1790677004.9328344, created 2026-09-29T10:16:47.102589+00:00;
worker.lock records command/cwd and advances per chunk. The first scored model
failure includes an internal Audiveris null Sheet during rhythm/score reduction,
followed by FileSystemAlreadyExistsException while its own book store was open.
Raw stdout logs are preserved. This is an engine failure after recognition started,
not the earlier sandbox JVM startup failure; retain its penalty without benchmark tuning.

## Consolidation entry evidence

preserved-homr-audit.json independently rechecks all 177 results/artifact inventories,
177 score identities/hashes and the three immutable summary hashes against the prior
HOMR report. No inference or score regeneration was needed. New consolidated report
fixtures passed seven tests: changed truth/scorer-summary/protocol/freeze/selection
contract rejected; CPU scores require exact current CPU scorer identity even when
legacy HOMR scorer compatibility exists; corrupt score bytes rejected; all-five
rendering and separate confirmation boundary retained. Log consolidated-fixtures.log.
Final research/bridge regression parent 88970 is running, log regression-final.log.

Final regression 88970 exited zero: 238 passed, 2 skipped, 9 subtests passed in
27.31 seconds, expected unreadable-clef fixture warning only. No further source
changes to the pinned CPU inference/development/admission/scorer stack.

## Canonical acceptance evidence map

Stage 2/3 fixture suites cover deterministic composition selection and disjoint
remainder, immutable original artifacts, success/typed failure/pending/corrupt/cache
states, duplicate-worker exclusion, interruption/resume, scorer parity, resource
pressure and four-hour session budget. CPU-specific fixtures additionally cover
readable inventory additions with old versions/non-inventory fields unchanged,
strict v5/90% policy, native CPU environment and JVM startup failures as pending.
Zeus note-bearing fixtures cover two-part order, pickup and cross-system sounding
 ties, rejection of inconsistent part identity and corrected detector coordinates.
All are in regression-final.log (238 passed, 2 skipped, 9 subtests).

Completion requires 59 immutable outcomes AND scores for each CPU candidate;
all five candidates share frozen truth/scoring with their distinct configuration
and runtime-policy provenance retained. Consolidation must retain failure/empty/
invalid/timeout counts, composition metrics, penalized NED, sparse duration matrices,
majority baseline/balanced accuracy/macro-F1, latency/cold-start/resources/features,
training-overlap disclosure, paired bootstrap/exact tests with eight-claim Holm
correction, and an untouched-confirmation estimate. Stop after publishing decision
input and updating handoffs; no subsequent evaluation or Stage 5 is authorized.

resource-function-parity.json proves AST identity for original/CPU acquire/release
lock, command monitor, run_attempt pressure handling, cumulative session budget and
close_session, plus scorer commit/run_score_worker/summary. Their existing fixture
coverage applies to the unchanged implementations; CPU-specific identity/profile
and JVM-infrastructure differences have additional tests. The first read-only
parity probe requested stop_tree as a local function; it is imported in both runners,
so no artifact was written. The corrected explicit function probe passed all nine.

Timing refinement at 24 completed Audiveris pages: the existing corrected HOMR
score-attempt ledgers contain 59 attempts each, totaling 2181.672 seconds (fine-tune)
and 2137.451 seconds (455), median 28.078/28.079 seconds. Scoring is significant;
Audiveris revised estimate 55–75 minutes remaining at that milestone, including
scoring. These are planning estimates, not mixed candidate inference timings.

At 38/59 Audiveris pages, estimate revised to 45–65 minutes remaining including
scoring. Reporting now explicitly counts successful empty outputs and typed empty,
invalid and timeout failures, retaining generic stage/code failures separately.
No scoring semantics changed. Eight consolidated fixtures passed, then full
regression-complete.log: 239 passed, 2 skipped, 9 subtests passed in 27.62 seconds,
expected unreadable-clef fixture warning only. Parent 57643 exited zero.

## Recorded next long jobs — sequential, no inference/scoring overlap

Working directory remains C:/Users/bur4x/Desktop/lecture/big_projects/Sheet2Play.
After Audiveris parent 54939 exits, verify 59 outcomes with screening_cpu_audit.py
and a closed session/absent worker lock. Preserve audiveris-inference-audit.json.
Exact scoring command:
`Research/omr/.venv/Scripts/python.exe -B Research/omr/screening_cpu_profile.py -- Research/omr/screening_cpu_score.py --manifest Research/omr/reports/screening/v1/manifest-v5-607ff64134da.json --candidate audiveris_page --session-id stage3-audiveris-screen-01`.
Log audiveris-score.log, approved readable context, same cumulative session and
thread/priority/resource limits. Scoring failure leaves pending score evidence;
inspect logs and hashes before a changed retry.

After Audiveris scoring and final audit close, exact Zeus development command:
`Research/omr/.venv/Scripts/python.exe -B Research/omr/screening_cpu_profile.py -- Research/omr/screening_cpu_development.py --manifest Research/omr/reports/screening/v1/manifest-v5-607ff64134da.json --candidate zeus_page --item-id openscore-6211535-page-1 --session-id stage3-zeus-dev-01`.
Log zeus-development.log, same cwd/profile/policy; neutral TensorFlow CPU recognition
with unchanged HOMR detector. Require a passing complete-page result and fresh
screening_cpu_admit.py admission before frozen Zeus inference. Do not switch to
app extraction or port the recognizer to GPU.

Audiveris inference parent 54939 exited zero; 59/59 results: 51 succeeded, 8 failed,
no interruption. 2209.250 seconds including chunk overhead, RAM peak 76.9%, VRAM
0 MiB; session closed and lock absent. Full readable CPU manifest/input/source/
runtime verification and all59 result identities/artifact inventories passed:
audiveris-inference-audit.json and .log. Scoring estimate 30–40 minutes from prior
corrected HOMR scorer ledgers. Launch the recorded exact CPU scoring command next.

Audiveris scoring parent exec 26551 is live; scorer PID 1188, creation_time
1790679092.2423298, created_utc 2026-09-29T10:51:34.376594+00:00. worker.lock
records exact command/cwd. First immutable score exists; no inference runs.
The active handoff and CONTEXT now point to this scorer and the completed 59-result
audit. Inspect live lock/process and session before resuming, do not duplicate.

Audiveris scoring reached 10/59 in 146.1 measured worker seconds, no scorer
interruptions. Revised remaining estimate 15–25 minutes from actual CPU-profile
throughput, replacing the conservative historical-HOMR planning estimate. Keep
execution-context timing caveats; do not combine historical and new timings.

## Final stop before Zeus — user's latest scope, 2026-09-29

The user requested stopping before Zeus; it will be done in a later prompt.
No Zeus development, admission, inference or scoring command was launched.
Do not start it automatically. Stage 3 and consolidated five-candidate reporting
remain incomplete; the prepared consolidation code has not published a report.

Audiveris scorer parent 26551 exited zero. Final CPU audit passed all59 immutable
results/artifacts, all59 exact CPU scorer identities/hashes and immutable summary:
`../2c98d5638c36/summaries/audiveris_page/3f340c6bab3e/summary-2904e7a12f86.json`,
SHA-256 `a9724dee8137993ff1c2133b351bc65df5157c10d8db1e1e6af151763cd0d1a8`.
Evidence audiveris-final-audit.json/.log. Full session closed at 3117.563 seconds
(51.96 minutes): inference/chunk overhead 2209.250 seconds, scoring/summary
908.313 seconds. 59 inference and 59 score attempts, no interruptions; lock absent
and no live Python/Java/Audiveris candidate observed after audit.

Primary/onset/pitch composition F1 0.0986380314 / 0.1178657990 / 0.7568426895.
Eight failures: five AUDIVERIS_FAILED:recognition, three
AUDIVERIS_OUTPUT_INVALID:artifact_capture. All51 valid-output NED scores and all8
failure penalties present; penalized NED mean 0.5203582256, zero scoring errors.
Duration balanced accuracy 0.3879694433, macro-F1 0.3521359415, majority accuracy
0.4224256293, majority macro-F1 0.0237580438, no single-class degeneration.
The full sparse confusion matrix has 67 unique cells/25 labels summing to all2185
matched notes; label membership and nonnegative integer counts verified.
Raw output, log, original MXL and normalized/canonical evidence are retained.

Peak system RAM 76.9% inference/72.3% scoring, device-wide VRAM 0 MiB.
Observed memory/VRAM/unattended checks passed; p95 latency 45.5805 seconds was
2.20836x shipped (frozen limit 2x), so current practical-limit checks fail.
Historical control had different admission/runtime context; comparison is
descriptive. Primary F1 is descriptively below shipped 0.4061; new consolidated
paired/bootstrap/eight-claim Holm statistics await Zeus, no statistical inference
or production decision is fabricated. Keep the installed engine.

Final regression: 239 passed, 2 skipped, 9 subtests passed, expected fixture warning.
SCREENING_HANDOFF.md, CONTEXT.md, AGENTS.md and canonical plan reflect this stop.
Exact next action after a later Zeus request: reverify live processes, v5 source,
runtime/model/input identities and resources, then run the recorded
stage3-zeus-dev-01 complete-page development command above. Admit only a verified
passing development report through screening_cpu_admit.py. Process max5 pages per
chunk under a fresh stage3-zeus-screen-01 four-hour session, score only after59
outcomes close, verify all results/scores, publish screening_consolidated_report.py
with the v5 manifest and update the handoff. No confirmation, Stage5, training,
cloud spending or production promotion is authorized.

## Zeus Stage 3 continuation authorized — 2026-09-30

The user explicitly requested Zeus work and completion of canonical Stage 3.
This supersedes the September29 stop before Zeus. Boundary: fresh neutral CPU
complete-page development/admission, 59 frozen pages/scores, five-candidate
consolidation and handoffs. Stop before untouched confirmation, Stage5, training,
cloud work or production promotion. The interrupted prior turn left no live
Python/Java/Audiveris worker, lock, Zeus development or screen session.

zeus-preflight-20260930.json: pinned v5 manifest/runtime/source/weights/input
verification passed, manifest SHA c3f28ec525ada8902203caf919da3ecdf4e75db30b84fd2379a4edb30483bc22,
Zeus config 81f73b31179a40bf63c608d9adea99f546dac49e57722d436dae205a1b135821.
RAM87.2%, GPU0/6141MiB, free disk58.67GB, no admission blockers. Close to90%
RAM policy; retain sustained-pressure guard. 46 relevant contract/representation/
conversion/scoring/report fixtures passed, log zeus-fixtures-20260930.log.

Exact development command:
`Research/omr/.venv/Scripts/python.exe -B Research/omr/screening_cpu_profile.py -- Research/omr/screening_cpu_development.py --manifest Research/omr/reports/screening/v1/manifest-v5-607ff64134da.json --candidate zeus_page --item-id openscore-6211535-page-1 --session-id stage3-zeus-dev-01`.
Working directory C:/Users/bur4x/Desktop/lecture/big_projects/Sheet2Play; approved
fully readable context, eight CPU affinity/threads, below-normal priority,
90% RAM/device-VRAM policy, five-second samples,30-second pressure window.
Log zeus-development.log. No benchmark inference until this complete-page gate
passes and screening_cpu_admit.py saves fresh admission. Preserve detector image,
crops, LMX/system MusicXML/stitch/normalized/canonical artifacts; existing GPU
detector remains unchanged and TensorFlow recognizer stays CPU.

Fresh Zeus development parent35066 is active. Runner PID25252,
creation_time1790753855.8238344, created_utc2026-09-30T07:37:39.741308+00:00.
worker.lock records the exact command/cwd; latest development sample RAM89.2%,
no blockers. Inspect live PID/creation time, lock, ledger and partial artifacts
before any restart. No benchmark inference has started.

## Zeus admitted and first screening chunk — 2026-09-30

Development parent35066 exited zero:95.625seconds, complete neutral page accepted,
91.078seconds recognition/conversion/stitching and1.125seconds normalization.
Peak process-tree RAM1073393664B, sampled systemRAM93.0% transient, device-wide
VRAM1127MiB. No30-second sustained-pressure interruption. CPU/profile/source/
artifact witnesses passed fresh admission at
`../2c98d5638c36/admissions/zeus_page/81f73b31179a/admission-7f0f26183984.json`,
SHAc4aec1c85f55e942c8460a771982fe05e23a06e49fedc7d8446cde8722e8bfde.
Full regression parent79280 exited zero:239passed,2skipped,9subtests in35.97seconds,
expected music21 fixture warning only, logzeus-regression-20260930.log.

Post-regression RAM95.4% blocked screening admission; no frozen item was launched.
User was asked to free RAM. Read-only re-verification of all177 preserved HOMR
results/scores/summary hashes passed. Subsequent actual resource sample at
2026-09-30T07:52:02.086334+00:00: RAM61.6%, GPU0MiB,58.46GBfree disk, no blockers,
no worker lock or live candidate and zero Zeus completed pages. Admission block
has cleared from observed resources; the user's Zeus execution authorization remains.

Exact first-five command:
`Research/omr/.venv/Scripts/python.exe -B Research/omr/screening_cpu_profile.py -- Research/omr/screening_cpu_run.py --manifest Research/omr/reports/screening/v1/manifest-v5-607ff64134da.json --candidate zeus_page --admission Research/omr/reports/screening/v1/2c98d5638c36/admissions/zeus_page/81f73b31179a/admission-7f0f26183984.json --session-id stage3-zeus-screen-01 --start-index 1 --max-items 5`.
Working directory root, approved readable context, logzeus-infer.log. Single
candidate, eight threads/affinity/below-normal,90% RAM/VRAM admission and30second
pressure window; new cumulative four-hour session includes subsequent scoring.
Preserve partial attempts; pending infrastructure/resource/session outcomes are
not scored zero. Verify firstfive hashes/outcomes before identical continuation
at6,11,...56. Preliminary development-based estimate90–150minutes including
scoring, refined after firstfive. No reference/prediction-based parameter changes.

First-five parent92482 running; runner PID33588, creation_time1790754787.7083871, created_utc2026-09-30T07:53:10.786020+00:00. Latest verified counters3completed/3success, RAMpeak68.5%, current69.9%, deviceVRAMpeak231MiB. Inspect matching PID/creation-time and ledger before restarting.

First-five parent92482 exited0; zeus-first5-audit.json reverified all5 result/identity/provenance/declared artifact hashes. All5success, no interruptions, chunk370.828seconds, worker elapsed total368.0seconds, RAMpeak69.7%, deviceVRAM1127MiB. Estimate refined90–110minutes total from firstfive, including scoring/consolidation; page complexity may vary.

Continuation exact command: & Research/omr/reports/screening/v1/stage3-cpu/continue-zeus.ps1. The recorded script expands the identical pinned profile/run/manifest/candidate/admission/session command above with --start-index6,11,16,21,26,31,36,41,46,51,56 and --max-items5. Working directory root; readable approved local context; appended logzeus-infer.log. Stops on nonzero exit or pending outcome. Same four-hour cumulative ledger; no scorer overlap or parameter changes.

Continuation parent95879 active. First continuation runner PID16252, creation_time1790755240.8970237; ledger active_since_utc2026-09-30T08:00:43.056356+00:00, prior used370.828seconds. Each subsequent chunk records its new PID/creation time in worker.lock. Reuse closed firstfive only under existing verified identity.

Consolidation-only report metadata aligned with canonical HOMR465 multi-voice/PR156 deferred status and explicit provisional throughput basis; no pinned inference/scoring helper changed. Eight consolidated-report guard/render fixtures passed after this edit. verify-zeus-preserved.py is a read-only post-screen audit of all successful pages' detector/source/crop hashes, LMX/system counts, preserved system XML/stitch/canonical files and full raw file hashes; failed pages retain original declared artifacts/error without inventing missing downstream evidence.

Live checkpoint:15/59completed, allsuccess,0scored, no interruptions. Cumulative closed chunks1082.297seconds; active next chunk PID30440 creation1790755957.688279, parent95879. RAMpeak69.7%, current64.8%, deviceVRAMpeak1129MiB. Estimated70–90minutes remaining including scoring/consolidation; no acceptance/configuration changes. Exact next action on interruption: inspect parent95879/live worker.lock PID and ledger; resume only still-pending indexes under identical manifest/admission/session, never duplicate the active worker.

Live checkpoint25/59completed, allsuccess,0scored/no interruptions. Closed-chunk cumulative1792.032seconds; continuation parent95879, current runnerPID23380 creation1790756672.6686597. CurrentRAM65.4%, screenRAMpeak69.7%, deviceVRAMpeak1129MiB. Approx55–75minutes remaining; score only after all59outcomes close and hashes verify.

Live checkpoint35/59completed, allsuccess,0scored/no interruptions; closed chunks2386.751seconds. Parent95879 active, current runnerPID13832 creation1790757272.6254935; currentRAM65.1%, peak69.7%, deviceVRAM1129MiB. Recent page times45.6–60.6seconds; revised45–65minutes remaining including scoring and consolidation. No screening parameters changed.

Live checkpoint45/59completed, allsuccess,0scored/no interruptions. Closed-chunk cumulative2986.345seconds; parent95879 active, current runnerPID464 creation1790757877.450816, currentRAM65.3%, screenpeak69.7%, deviceVRAM1129MiB. Approx35–55minutes remaining. First-five verification remains valid; full59 closed inference/artifact/intermediate audits precede scoring.

Live checkpoint55/59completed, allsuccess, no interruptions/zero scores. Closed-chunk cumulative3616.002seconds; final four-page chunk parent95879 runnerPID6540 creation1790758512.410148, RAM66.5%/peak69.7%, deviceVRAM1129MiB. Latest53rd page131.2seconds; complexity varies. Approx25–40minutes remaining including scoring/consolidation. Next: wait for parent95879 exit and verify all59 plus intermediate preservation, then start the exact recorded scorer under this same cumulative session.

Recorded dependent closeout commands (not launched while inference active):
1. Research/omr/.venv/Scripts/python.exe -B Research/omr/screening_cpu_audit.py --manifest Research/omr/reports/screening/v1/manifest-v5-607ff64134da.json --candidate zeus_page --output Research/omr/reports/screening/v1/stage3-cpu/zeus-inference-audit.json
2. Research/omr/.venv/Scripts/python.exe -B Research/omr/reports/screening/v1/stage3-cpu/verify-zeus-preserved.py
3. Research/omr/.venv/Scripts/python.exe -B Research/omr/screening_cpu_profile.py -- Research/omr/screening_cpu_score.py --manifest Research/omr/reports/screening/v1/manifest-v5-607ff64134da.json --candidate zeus_page --session-id stage3-zeus-screen-01
Working directory root, approved fully readable context. Audit writes immutable evidence; score logzeus-score.log, same eight-thread/below-normal profile,90% resource guards and existing four-hour ledger. Verify closed59 outcomes and no lock first. Save scorer parent/PID immediately after launch. No confirmation or later-stage execution.

Inference parent95879 exited0. All59success,0failures,59cold attempts, no interruption, cumulative3889.940seconds (64.8323minutes), attemptworker sum3864.9seconds. Worker.lock absent and ledgerclosed; RAMpeak69.7%, deviceVRAM1129MiB. zeus-inference-audit.json verified59 result/identity/provenance/artifact hashes and source/runtime/model/input identities. zeus-preserved-evidence-audit.json verified59 successful pages,324detected systems,1061raw file hashes; detector/source/crop hashes, nativeLMX counts and per-system/stitch/canonical evidence passed. No scoring yet. Launching recorded scorer now under same session/log/profile.

Scoring parent77506 active; runnerPID30760 creation1790758848.9630964, created_utc2026-09-30T09:00:51.093605+00:00. Sessionactive_since2026-09-30T09:00:51.381269+00:00, prior cumulative3889.940seconds. Exact command/cwd in worker.lock and above; logzeus-score.log. CurrentRAM67.4%, no othercandidate. Estimated20–35minutes remaining including consolidation. On resume inspect currentPIDcreation/session/score-attempt progress, retain scored items under exact identities; no duplicated scorer.

Scoring checkpoint3/59saved; firstthree attempt sum151.5seconds (~50.5sec/page), no interruptions. Parent77506/runner30760 remains active, RAM72.7%. Revised35–55minutes remaining including consolidation; first-page scoring cost exceeds Audiveris throughput, and composition complexity may vary. Keep all59inference outcomes and current score attempts unchanged; no interim quality-selected parameter edits.

Scoring checkpoint7/59saved, attempt sum499.3seconds, no interruptions. A slow scored page took218.657seconds; process-tree RSS observed2917.1MiB, closed-score systemRAMpeak81.7%, subsequently returned65.6%. No threshold interruption/retry. Firstseven average~71sec/page; remaining estimate widened45–75minutes including consolidation, with highly variable OMR-NED cost. Read-only timing query initially assumed inference-only outcome peak key; corrected to closed resource samples, no inference/scoring changes. Parent77506/PID30760 stays active under original session/profile.

Scoring checkpoint15/59saved, attempt sum914.6seconds, no interruptions. First11checked NEDstatuses allvalid; full aggregate/hashes pending final audit. CurrentRAM66.4%, scorerparent77506/PID30760 active. Approx40–60minutes remaining from~61seconds/page average plusverification/consolidation. Cumulative session remains below4hours; all saved identities/artifacts retained.

## Paused by user for assistant-model switch — 2026-09-30
Scorerparent77506 exited1 after the guard stopped page24 under sustainedRAMpressure. Pending item test/beethoven/sonata26_1/sonata26_1_1.png; attempt score-attempts/zeus_page/81f73b31179a/b5f4b3348445/6c215985383acc5b4bc3/attempt-5828546d3fe44381b14236643d42e728. Outcome118.5seconds, exit15, reasonresource_interruption, statuspending. SystemRAMpeak94.8%, seven>=90% five-second samples; preserve pending and never score it as model zero. All59successful inference results remain verified. zeus-pause-audit-20260930.json verified exact current CPU identity/hash for23saved scores, all23NEDvalid. Remaining36scores (oneinterrupted,35unstarted), no Zeus summary/consolidated report yet.
Live process verification after exit: zero candidate/scorer workers, original scorerPID30760 absent, worker.lock absent; ledgerclosed at5432.674seconds (90.5446minutes). LatestobservedRAM85.6%; restore meaningful memoryheadroom before retrying the expensive pendingpage, beyond merely slipping below90%. Never reset the cumulative budget. Alreadycompleted64.8323minutes inference plus25.7122minutes first scoringpass includingpendingattempt. No automatic restart following the user's explicitpause.
The user intends a cheaper assistant to supervise the unchanged scoring scripts, then a stronger assistant to review final evidence/consolidateStage3. Assistant-model switching does not change the local scoring algorithms or frozen inputs. Currentstatuspauseduntilhumanresume. No modelsetting changed by this agent.
Exact next command ONLY after explicitresume and fresh runtime/source/model/input/resource/liveprocess checks:
Research/omr/.venv/Scripts/python.exe -B Research/omr/screening_cpu_profile.py -- Research/omr/screening_cpu_score.py --manifest Research/omr/reports/screening/v1/manifest-v5-607ff64134da.json --candidate zeus_page --session-id stage3-zeus-screen-01 --retry-pending
Working directory C:/Users/bur4x/Desktop/lecture/big_projects/Sheet2Play; approved fullyreadable context remains necessary for exact runtimeinventory, eight CPUthreads/affinity/below-normal, unchanged90% guard/fourhourledger; appendzeus-score.log. Record newparent/PID/creationtime immediately. Preserve failedpartialattempt and reuse23saved verifiedscores. No inference rerun or pinnedsource/scorer/config changes. Ifpendingrecurs, inspectcause before retry; do not relaunch unchanged without newresourceevidence.
Cheaper-model stop boundary: after59scores and immutable summaryverify, run screening_cpu_audit.py --manifest samev5 --candidate zeus_page --include-scores --output Research/omr/reports/screening/v1/stage3-cpu/zeus-final-audit.json; updatehandoff, stopbeforeconsolidation. Laterstronger-model request: reverifyAudiveris/allHOMRcachedreports, publish screening_consolidated_report.py --manifest samev5, verifyallfive/295scores/eightpairedclaims, updatecanonicalStage3complete. No untouchedconfirmation, Stage5, training, cloud orpromotion. Allhistoricalmanifests/results preserved.

## Resume request checked; waiting for more RAM — 2026-09-30
The user requested resuming Zeus scoring-only after switching assistant models, with an explicit stop after all59scores and before consolidation. Fresh preflight found no candidate/scorer workers, no worker.lock, original session ledger closed at5432.674seconds, all59inference results still complete,23saved scores and1 pending score interruption. Current systemRAM85.0%, available2447892480bytes (~2.28GiB); the previous scoring process reached94.8% and the interrupted per-item worker RSS reached2917MiB. Retrying with less currently available RAM than the observed heavy score peak would predict another guard interruption and make no progress, so no scorer launched. Current stage awaits the user's RAM-freed response. Pause audit continues to verify all23 cached score identities/hashes and all were OMR-NED valid. Next action after available memory materially improves: repeat resource/worker/ledger/sample/source/model verification, then run unchanged recorded CPU scorer with --retry-pending under stage3-zeus-screen-01; stop after complete59 score summary and final audit, before consolidation. The historical cumulative time is retained, not reset. Exact current resource preflight captured via progress/psutil; no inference or score configuration changed.

User freed RAM and requested resume, scoring only, stop before consolidation. Preflight at09:34UTC: RAM69.5%, available4,995,702,784B (~4.65GiB); no candidate workers or lock, ledger closed5432.674s, 59results present,23scores. The 23 saved score identity/hash/NED states reverified exactly against immutable zeus-pause-audit-20260930.json; helper made idempotent by requiring existing audit equality. Relaunched scorer with exact prior --retry-pending command. Parent51989; runnerPID7408 creation1790760883.7635703 created09:34:45.914493UTC; command/cwd in worker.lock; appended zeus-score.log. Initial RAM after startup71.9%, still under90%. Never duplicate. Stop after all59scores/audit; no consolidation.

Resume scorer progress parent51989/PID7408 still active. Outcome24 was successfully re-scored and committed, increasing cached verified score count to24; it was the prior pending item. At next snapshot25/59, scorer active/no new interruption, currentRAM71.1%. User-reported RAM relief changed preflight from85%/2.28GiB to69.5%/4.65GiB. Keep monitoring 90%/30s guard; same profile/session/source/scorer, no consolidation.

## Scoring-only pass closed and verified — 2026-09-30
User-reported RAM relief raised preflight to69.5%/4.65GiB; exact23 saved scores reverified; no worker/lock and cumulative closed session5432.674seconds were preserved. Retry used parent51989/runner7408, same v5 manifest/config/scorer/profile/session, with --retry-pending. Page24 (previous exit15/resource_interruption at94.8%) re-scored and committed; no further interruptions. Scorer exited0 and wrote summary summary-106f918dd791.json, SHA256 bea1ff52d402e4a8adb3dda97c4c4cfbd696bdd24db2fcacb9bd2f11979272ef. Final CPU audit zeus-final-audit.json: all59 outcomes succeeded, all59 exact CPU score identities/hashes verified, immutable summary reports59pages/18groups, session closed with7011.924seconds (116.87minutes) cumulative. All raw interim evidence audit remains 59pages/324systems/1061files. Scoring pass complete as requested. STOP HERE: no consolidation, cross-candidate paired stats, final five-candidate report or changes to canonical completion status until a later stronger-model request. User-directed cheaper-model phase complete.

User-directed stop boundary rechecked after final audit: progress59/59 successful results,59/59 CPU verified scores, session closed7011.924s, worker.lock absent, no scorer process. Resource sample64.2%. No consolidate/report/statistics command launched after close. Documentation link check112/112 local targets passed; git diff --check on tracked instruction files passed (line-ending notices only). Stop the task here and await later stronger-model request.

## Consolidation authorized — 2026-09-30
User requested completion of canonical Stage3 after verified59Zeus scores. Boundary: verify allfive59-page/18-group result/score sets, produce consolidated report and paired eight-claim statistics, updatehandoffs, stopbeforeconfirmation/Stage5/training/promotion. No inference/scoring rerun. Fresh live check Zeus59/59, sessionclosed7011.924s, worker.lockabsent, RAM68.8%. Exact consolidation command: Research/omr/.venv/Scripts/python.exe -B Research/omr/screening_consolidated_report.py --manifest Research/omr/reports/screening/v1/manifest-v5-607ff64134da.json. Workingdirectory root; approved fullyreadable context for exactCPUinventory. Log stage3-cpu/consolidation-20260930.log. Reporthelper verifies currentv5 and allpreservedcrossmanifestcontracts/result/score/artifact/summaryhashes before immutable publication. No model setting or model payload changes.


## Canonical Stage 3 complete — 2026-09-30
Consolidation parent 70787 exited 0. Published immutable report:
[REPORT.md](../2c98d5638c36/reports/consolidated-stage3-836fb923bb33/REPORT.md),
JSON SHA-256 `22423ca7343b5382881577b6b6146066974cfd35710a48d964faa04b1ef8bb85`.
Exact command/working directory and `consolidation-20260930.log` recorded above.
Manifest v5 SHA-256 `c3f28ec525ada8902203caf919da3ecdf4e75db30b84fd2379a4edb30483bc22`;
sample SHA-256 `2c98d5638c368b1a53bdb3440177d04fa585f9b1ca6ce6adbe65af64cd8e27d1`.
Consolidator verified all 295 result/score pairs, all five 59-page/18-group summaries,
source/artifact hashes and cross-manifest frozen sample/scoring contracts before
publication. No inference/scoring rerun or pinned helper/model/configuration change.

Read-only `verify-consolidated-report.py` wrote [consolidated-final-audit.json](consolidated-final-audit.json):
295 results / 295 scores / eight claims; complete duration matrix support and
recalculated balanced accuracy, macro-F1 and majority baselines agree to 1e-12.
All eight comparisons retain 18 groups, 59 pages, 10,000 bootstrap samples and
262,144 exact assignments. Relevant report/statistics/analysis fixtures: 14 passed.
Unchanged full research/bridge regression from fresh Zeus development: 239 passed,
2 skipped, 9 subtests passed.

Primary F1: shipped 0.4060904651; repaired fine-tuned 0.3844154166;
corrected 455 0.2856548208; Audiveris 0.0986380314; Zeus 0.0228105412.
Failures respectively 1/0/1/8/0 out of 59. No challenger supported superiority
under eight-claim Holm correction. Fine-tuned minus shipped -0.0216750485,
95% CI [-0.0984760270, 0.0415046906]; small gap inconclusive. Zeus minus shipped
-0.3832799239, 95% CI [-0.5222794891, -0.2525093961]. Its accuracy loss is not
localized to recognition/representation/conversion by these aggregate scores.
Audiveris/Zeus p95 latency ratios 2.208x/3.449x fail frozen 2x requirement;
Zeus had one resolved scoring pressure interruption, so unattended stability fails.
Historical timings use different policy/context and remain descriptive.

Next action: Stage 4 review/decision using the completed report, preserving all
cached evidence. Conditional HOMR 465/Combined and unavailable configurations
remain deferred. Stop before untouched confirmation, Stage 5, training, cloud
spending or production promotion; no later run launched. Historical scoring-only
stop is superseded by this explicit user-authorized closeout. Sessions are closed
and worker lock absent; final live check recorded separately below.

Final live closeout: fully readable process inventory found zero candidate/scorer workers. Both CPU sessions closed, worker.lock absent; Zeus 59/59 successes and scores, Audiveris 51 successes/8 failures and all 59 scores. Current RAM 64.5%. All 126 local documentation links and trailing-whitespace checks passed; tracked CONTEXT.md diff check passed. A sandbox-only process inventory was denied, so this final process check used the same approved readable context as runtime verification. No later job launched.
