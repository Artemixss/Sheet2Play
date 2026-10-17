# HOMR 465 integration, library migration, and local release

**Plan ID:** `2026-10-09-homr-465-app-integration`  
**Selected:** 2026-10-09 (Europe/Istanbul).  
**Status:** **Completed** 2026-10-17, all four phases. Implementation was
authorized on 2026-10-09 by "implement main plan". On 2026-10-16, at the user's
request, the work was pushed to origin/main (`5184b78`..`4416d82`) ahead of the
Phase 3 audit. The fresh-process resume and the audit passed on 2026-10-17: 56
successes, 1 failed and 2 unavailable, with none pending. The [report](../../Research/omr/reports/homr-465-app-integration/REPORT.md)
holds acceptance, migration totals, delivery and rollback. The
[execution handoff](../../Research/omr/reports/homr-465-app-integration/handoff.md)
holds the execution history. The text below is the plan as it was executed.

## Goal and selected decisions

Make pinned no-title HOMR **465** the default for new scans after practical app
validation, retain a visible **426** fallback, update the EXE the user launches,
rescan recoverable existing HOMR scores, and commit/push the focused changes
directly to **origin/main**. The user selected measured aggregate improvement
plus app checks as the local adoption criterion; untouched scientific confirmation
is a separate future task.

The [completed research plan](2026-10-06-homr-timing-465.done.md),
[Phase 4 report](../../Research/omr/reports/homr-timing-465/phase4/REPORT.md),
[acceptance ledger](../../Research/omr/reports/homr-timing-465/phase4/acceptance-ledger.md)
and [prior handoff](../../Research/omr/reports/homr-timing-465/handoff.md) preserve
the evidence and limitations. Their dated recommendation for an opt-in trial
predates this selection. Do not rewrite their experiments or claim their full
research promotion gate was met.

- The observed 59-page/18-composition comparison gave primary F1 **0.5313290603
  for 465 versus 0.4139483028 for 426**. Twelve compositions improved; six worsened.
  This supports an aggregate gain on that sample, not improvement on every score.
- Known harms include the extra A5 in `three_voices` and severe `tuplet_aligned`
  regression. Preserve these disclosures and the independent-voice tie limitation.
  Do not hard-code notes, durations or crop changes to conceal them.
- Convert cached songs by recognizing their original PDF/images again. Existing
  MIDI cannot be relabelled or transformed into a genuine 465 recognition result.
- The read-only library inventory found **57 recoverable HOMR scores / 266 pages**,
  plus **two older records lacking matching retained sources**. The frozen migration
  inventory confirmed that one orphan retains MIDI and the other lacks MIDI.
  Direct MIDI, direct MusicXML and Zeus imports are outside it.
- Preserve the existing audio offset and other settings. No training, other-engine
  research, frozen 59-page rerun, new model downloads or cloud spending is included.

## Phase status and next action

| Phase | Objective | Recommended executor | Status / required evidence |
| --- | --- | --- | --- |
| 1 | Implement and qualify the isolated 465 app path | Sol 6.1 High: runtime, identity and compatibility decisions | Complete; [acceptance evidence](../../Research/omr/reports/homr-465-app-integration/REPORT.md) |
| 2 | Validate and publish the installed app | Sol 6.1 Medium: defined release and persistence checks | Complete; all seven release steps, 77 tests, fourteen installed scans, real-library scan/restart |
| 3 | Rescan the recoverable HOMR library | Sol 6.1 Medium: resumable migration with fixed contracts | Batch complete: 56 successes / 258 pages, one failed 8-page score, two source orphans; fresh-process resume and final audit pending |
| 4 | Commit, push and close out | Sol 6.1 Medium: focused delivery and evidence review | Code and evidence pushed 2026-10-16 (`4416d82`); release evidence, migration totals and archive pending |

**Next planned action:** After allowance relief, prove fresh-process resume without
repeated inference, then audit all old/new hashes and recent references. Phase 2
passed the full scratch/installed gates, persisted fallback and direct XML checks,
14 installed development scans (native p95 ratio 0.799767), and one real private
scan with restart/reopen. Only the saved engine field changed to 465; audio and
other settings are preserved. The earlier usage stop remains dated evidence in
the handoff. Phase 3's full release passed 87 tests and all seven steps; the frozen
inventory has 57 recoverable scores/266 pages and two source orphans. One orphan
retains MIDI and the other lacks MIDI; neither can be re-recognized without a source.
The batch finished with no resource stop and no pending entries; one native
exporter failure is accounted for without a retry. No live worker/lock remains.
Phase 3 acceptance awaits resume/audit; the work is pushed, Phase 4 closeout is not done. See the handoff
before launching or resuming any job.
Keep the user's selected model/effort until they request a change; no automatic
delegation or new chats. On execution, keep a single owning handoff and per-phase
evidence under `Research/omr/reports/homr-465-app-integration/`, linked here.

## Runtime, interface and compatibility contracts

- Append `OmrEngine.Homr465` without changing existing enum values. Serialized
  `homr` continues to mean shipped 426; `homr465` selects the new candidate. Extend
  the visible engine selector, progress, error and recovery paths with explicit
  labels and a direct 426 fallback.
- Use source revision **`33baa326900faa12702df8c4bdcbea034a3d6a34`**, the matching
  465 FP16 encoder/decoder and pinned segnet 308 FP16 from the
  [frozen configuration](../../Research/omr/reports/homr-timing-465/phase2/candidate-configuration.json).
  Verify its recorded source and payload hashes. Preserve the frozen research
  configuration; assign the app runtime a separately recorded identity.
- Provision isolated source/model assets under **`Bridge/.runtime/homr-465`**
  using already-local artifacts and existing
  **`Bridge/.venv-homr-gpu/Scripts/python.exe`**. Preserve installed 426
  `site-packages`, weights and caches. Runtime code must work from the published
  app without importing tooling from a Research directory.
- Retain native page processing, `title_detection=false`, 300-DPI rendering,
  `CUDAExecutionProvider`, eight intra-op and one inter-op thread. Carry forward
  the recorded processing settings. Verify imported module origins and actual
  segmentation/encoder/decoder providers; wrong assets or unavailable CUDA fail
  explicitly. Do not silently substitute CPU, 426 or a moving upstream revision.
- Route native 465 MusicXML through the existing HOMR normalization and MIDI
  path. The research-only direct-MusicXML revision branch is not a production
  inference implementation. Leave unrelated direct-XML work and the known tie
  defect outside this integration.
- Keep Bridge schema version **2**. Add optional `model_revision` and
  `runtime_profile_sha256` fields, required and validated for `homr465` while
  preserving old 426 responses. A shared profile manifest pins source, weights,
  settings, relevant dependencies and normalizer identity; publish it with Bridge.
- Persist the same validated identity in 465 caches. Key new cache entries by
  profile identity and source SHA-256 so different files or profiles cannot reuse
  each other's MIDI. Preserve legacy 426 cache layout and contracts; keep good
  426 versions available when a new recognition is worse or fails.
- Add optional **`SHEET2PLAY_SETTINGS_PATH`** to isolate scratch settings as well
  as the existing `SHEET2PLAY_HOME` library override. For the real installation,
  verify **`C:\Users\bur4x\AppData\Local\Sheet2Play`** explicitly: the tool
  sandbox's redirected LocalApplicationData directory is not the user's library.

## Execution phases and acceptance

### Phase 1 — Implement and qualify

1. Inspect the working tree, live jobs/locks, permissions, runtime assets and
   resources. Preserve unrelated edits and snapshot the installed EXE/runtime,
   settings and cache metadata. Record commands, identities, logs and resumable
   progress before substantial jobs.
2. Implement the isolated launcher/profile, bridge dispatch and result validation,
   visible selector/fallback, settings isolation and separate cache identity.
   Reuse portable candidate-launcher and supervisor logic; the installed app
   must not depend on a Research checkout or mutate the frozen artifacts.
3. Qualify fresh native inference in the intended app runtime against a matched
   no-title 426 control using existing rendered development controls and bounded
   OpenScore diagnostic probes. Ceiling: **64 native captures including probes**;
   do not retry repeatedly until success. Generated controls supply numerical
   expectations; OpenScore is diagnostic-only.
4. Reuse the existing [32-input downstream manifest](../../Research/omr/reports/homr-timing-465/phase3/playback-manifest.json)
   for normalization, JSON, MIDI and controller checks, adding new engine/cache
   integration coverage. This manifest contains XML and fixture inputs; it is
   not a 32-image inference benchmark.

**Accept when:** profile/source/model/provider identities agree, legacy 426 still
works, every bounded probe has a receipt or explicit model failure, and affected
fixtures plus full relevant Bridge/research/frontend checks pass. Stop dependent
work on identity/provider/import mismatch, unresolved resource interruption,
cross-profile cache reuse or new unexplained integration-induced musical harm.
Known recognition errors remain disclosed; they do not justify speculative fixes.

### Phase 2 — Validate and publish

1. Use a separately published scratch app with isolated library **and** settings
   first. Verify scan/import/preview/reopen, persisted identities, fallback,
   playback data and representative voice/timing behavior.
2. Back up the installed release and real user metadata. Run the complete release
   gate with no `SkipTests` or `NoLaunch` bypass:

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\verify-release.ps1
   ```

3. Extend release asset checks for the profile and external 465 runtime. Set the
   new-install default to 465 and, after the gates pass, update this user's real
   saved engine selection once while preserving audio and all other settings.
   A later explicit choice of 426 must be respected.
4. Verify actual **`dist\Sheet2Play.exe`** against the real settings/library,
   selected source/model/provider, one scan/import and restart/reopen. The Desktop
   and Start Menu shortcuts already target this EXE; preserve that launch route.

**Accept when:** the full gate passes with retained logs/screenshot evidence and
the published app proves correct engine dispatch, cache identity and persistence.
Installed-runtime p95 page latency must be at most **2×** the matched control;
record resource use. Preserve audio offset and check physical playback when
observable; do not claim verified sound from MIDI/controller tests alone.

### Phase 3 — Migrate the cached HOMR library

1. Build and freeze an inventory from existing HOMR manifests, retained source
   SHA-256 values and recoverable PDFs/images. Reconfirm the expected 57 scores /
   266 pages and two orphan records without exposing private scores externally.
2. Extend the existing headless reconvert path with **inventory and resume** modes.
   Use the same app pipeline/cache writer; process one score at a time. Do not
   force-reprocess every PDF or rerun already validated migration successes.
3. Validate complete-score processing, MIDI roundtrip, hashes and candidate
   identity before committing each new cache. Preserve original sources and 426
   entries. Prefer successful 465 versions while keeping older versions visible.
4. Map recent-song references only after a successful cache commit, preserving
   their ordering/timestamps. Failed or unavailable items keep their old references.
   Record per-item `success`, `failed`, `unavailable` or `pending` with receipts.
   Ordinary model failures are accounted for and the next item may proceed;
   resource/identity failures stop the job.

**Accept when:** every inventory entry is accounted for, each recoverable item is
converted or explicitly failed, the two orphan records are explained, and restart/
resume preserves completed work. Do not say all songs were converted while any
recoverable item remains pending. Old caches and rollback remain available.

### Phase 4 — Commit, push and close out

1. Review and stage only this integration's code, necessary prerequisites, tests,
   pinned setup/profile, attribution and task-relevant documentation. Preserve
   upstream license/attribution. Exclude model payloads, virtual environments,
   private PDFs, song caches and unrelated work; do not add AI co-author trailers.
2. Commit and push directly to **`origin/main`**, as selected. No PR or force-push;
   stop and resolve unexpected remote conflicts without discarding anyone's work.
   The setup must reproduce the pinned runtime; this machine reuses existing bytes.
3. Deliver the pushed commit, verified EXE path, release evidence, migration totals,
   failures/unavailable items, known regressions and rollback steps. Archive this
   plan as `.done.md` only when the delivery and accounting requirements are met.

**Accept when:** GitHub push succeeds, the user's installed EXE is verified, all
migration records are accounted for, and rollback is practical. Report partial
completion honestly if a delivery or migration requirement remains unmet.

## Validation, safeguards and replanning

- Validate affected contract/unit fixtures, one representative development item,
  then full relevant Bridge/research and frontend suites, followed by the release
  gate and published-app checks. Repeat only for relevant changes or failures.
- Cover missing/wrong assets, unavailable CUDA, legacy 426 responses and caches,
  changed profile/source hashes, duplicate filenames, restart/reopen, interrupted
  migration/resume and failed conversions without overwriting good old caches.
- Preserve corrected offset-entry/held-note/triplet controls and representative
  voice/staff, tie, tuplet, pickup, tempo and MIDI quantization checks. Retain the
  extra A5 and tuplet regression as known recognition limitations.
- Use the [enforced Windows supervisor](../../Research/omr/reports/zeus-attribution/phase2/safety-fix-20261004/REPORT.md)
  for substantive jobs: one heavy worker, **85% RAM/system-commit stops**, **4 GiB
  reserve and aggregate worker cap**, process containment and bounded deadlines.
  Retain the 16-process and four-hour unattended-session bounds. GPU admission is
  separate, capped at **90% VRAM**, with no competing training workload.
- Retain the selected **5% remaining five-hour usage stop**. Check allowance at
  meaningful execution boundaries and stop with a resumable checkpoint. Quota
  pressure does not authorize weakened validation or incomplete work marked done.
- Preserve failed receipts and partials. Never automatically retry pressure
  failures or invoke Git during recovery. Verify resolved workspace paths before
  recursive release-folder operations; confirm applicable permissions before
  writing real user metadata outside the workspace.
- Return to review on unresolved runtime incompatibility, new musical corruption,
  resource interruption, latency-gate failure or unexpected library/remote state.
  Keep the working 426 fallback. Untouched confirmation, broader repairs, training
  or further candidates require a separate decision.

[All plans](../README.md).

