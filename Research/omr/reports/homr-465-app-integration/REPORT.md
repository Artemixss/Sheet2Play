# HOMR 465 app integration evidence

Owning plan: [2026-10-09-homr-465-app-integration](../../../../plans/MAIN_PLAN.md).
Implementation, qualification and installed-app validation (Phases 1–2) completed
on 2026-10-09; batch library migration and Git delivery remain pending.

## Phase 1 acceptance

The portable app profile pins source `33baa326900faa12702df8c4bdcbea034a3d6a34`,
465 FP16 encoder/decoder, segnet 308 FP16, CUDA first, 8/1 threads, 300 DPI and
no title detection. Profile SHA-256:
`1fd5b26e461688307b7480fe8c1e7bb959152b8436fc8c64fbe4141629f1ac46`.
The app path imports no Research tooling and leaves installed 426 assets intact.

Fresh matched qualification used all twelve existing generated development
controls and two explicitly selected OpenScore diagnostic pages. All 28 captures
completed; counting the preceding representative probe, Phase 1 used 29 of its
64-capture ceiling. The fourteen 465 outputs reproduced prior native musical
events exactly, including their known errors. Source/model/provider/import
identities were enforced by the launcher. No resource stop or implicit retry.

| Development measure | 465 | 426 |
| --- | ---: | ---: |
| Generated mean pitch/onset/duration F1 | 0.609688 | 0.542100 |
| Native page p95 seconds, fourteen pages | 16.5102 | 13.5225 |
| Conditional duration balanced accuracy | 0.694444 | 0.666667 |
| Conditional duration macro-F1 | 0.696682 | 0.663082 |
| Majority duration baseline accuracy | 0.609524 | 0.530973 |

The duration confusion matrices and labels are retained in
`phase1/qualification/analysis.json`. They describe exact pitch/onset pairs in
generated controls only; neither predictor is single-class. OpenScore pages
are diagnostic-only. The latency ratio is 1.220943; installed-runtime acceptance
must still be established in Phase 2.

Nine focused Bridge tests plus three subtests passed. Full relevant Bridge/research
regression passed (`phase1/jobs/full-python-regression`); current frontend full
suite passed 76 tests. All 32 existing downstream XML/fixture inputs passed using
the production frontend and current Bridge, including MIDI roundtrip and controller
timing checks. Controller checks do not establish physical sound quality.

Evidence remains local under `phase1/`: immutable input/selection manifests,
both engines' native receipts/artifacts, `qualification/analysis.json`,
`playback-manifest.json`, `playback/results.json`, frontend TRX, supervisor
receipts and full worker logs. Failed preparatory jobs are retained in the
[handoff](handoff.md). No frozen 59-page evaluation was rerun.

Known harms remain: extra A5 in `three_voices`, severe `tuplet_aligned` regression,
and independent-voice tie limitation. This bounded integration evidence does not
establish general superiority or satisfy the historical scientific promotion gate.

## Phase 2 acceptance

Scratch publication passed the complete gate, then scan/preview/reopen, saved 426
selection, direct MusicXML import/cache and visible Retry HOMR 426 checks passed.
The direct XML check exposed a missing cache-settings/model identity branch;
the bounded prerequisite fix and regression passed. The real release passed all
seven gate steps and 77 frontend tests, with logs/TRX and actual window screenshot
in `dist/_verify`. Neither tests nor app launch were bypassed.

The entire prior release and private settings/cache metadata were backed up under
local ignored `phase2/installed-backup`. The one-time saved engine update changed
only `omr_engine` to `homr465`. New installs default to 465; a later explicit 426
selection remains respected. Existing Desktop/Start Menu launch targets remain.

All fourteen development pages completed through the actual published EXE in an
isolated qualification library. Installed native page p95 was 10.81485 seconds,
versus 13.5225 for the matched fresh Phase 1 no-title 426 control in the unchanged
app interpreter: ratio 0.799767, below the selected 2× bound. Full app/cache time is
recorded separately per page in `phase2/installed-latency.json`. Each native job
enforced published source/model/profile, isolated origins and actual CUDA-first
sessions; supervisor receipts retain resource use. This is development latency
evidence, not a rerun of the frozen scientific comparison.

One recoverable one-page private PDF was scanned against the explicit real library
and settings paths. The result contained 291 piano notes, validated cache identity,
and an identical MIDI/manifest after a separate-process reopen. All 177 preserved
old-cache/source/root-metadata files retained their hashes. Private filenames,
native receipts and previews remain in ignored local evidence. Physical sound
was not observed; MIDI/controller/preview checks do not establish it.

Failed preparatory gates and partial direct-XML evidence are retained. No resource
stop, implicit pressure retry, frozen evaluation rerun, training or download.

## Phase 3 implementation and frozen inventory

Published inventory/resume modes use the normal 465 cache pipeline with a frozen
source inventory, executable/profile identities and an atomic per-score journal.
Success is recorded before recent references are mapped; a restart validates the
committed cache and repairs that mapping without repeating recognition. Resource,
identity, filesystem and deadline errors stop the batch. Ordinary recognition or
normalization failures are explicitly accounted for and preserve the old version.

Eighteen focused integration/migration cases passed, including interruption,
resume, cache identity, source drift and recent-order preservation. The complete
current Bridge/research Python regression passed. The actual installed release
passed all seven gate steps with 87 frontend tests; its captured window shows 465
selected with 426 available. Recognition profile identity is unchanged.

The frozen inventory contains 59 legacy manifests: 57 recoverable scores with
266 pages and two source orphans. One orphan retains MIDI; the other lacks MIDI.
Neither has a matching retained recognition source. Both records remain intact.
All ten recent entries and saved settings were captured before the batch. The
serial supervised migration completed with 56 successful scores / 258 pages,
one failed eight-page score and two unavailable source orphans, with no pending
entries. One existing 465 cache was reused. Native logs contain 262 completed page
receipts and one failed page receipt: the failed score completed its first five
pages, hit the upstream zero-duration group assertion on page six, and did not
attempt its remaining two pages. Its old version remains available.

The root supervisor completed with exit 0, no resource stop, 5,734.766 seconds
monotonic elapsed time, peak RAM 61.565% and peak commit 57.295%. Both worker locks
are gone. Fresh-process resume and the final independent preservation audit have
not run: the selected 5% remaining usage threshold was reached at this boundary.
Phase 3 acceptance and Phase 4 Git delivery remain pending. Private paths and
receipts remain local.

## Rollback and retained limitations

Select HOMR 426 in the visible engine control for subsequent scans. Existing 426
versions remain in the library and can be reopened when a 465 result is worse or
fails. Selection alone does not replace an already-open 465 cache.

For a full installation rollback, close Sheet2Play and restore the complete
previous `dist` folder from the ignored local `phase2/installed-backup/dist`.
Restore the backed-up root settings/recent metadata and cache manifests from
`phase2/installed-backup/private` to their recorded relative library paths in
`metadata.json`. The prior MIDI files and retained sources are preserved in place;
the new 465 files can remain alongside them. Relaunch the existing Desktop or
Start Menu shortcut, which targets `dist/Sheet2Play.exe`. Keep the backup until
the user accepts the release; do not mix individual binaries from two releases.

The known extra A5, tuplet regression and independent-voice tie limitation remain.
Physical audio was not observed. No untouched scientific confirmation, training,
model download or cloud spending was performed.
