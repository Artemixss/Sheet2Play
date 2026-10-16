# Sheet2Play — Context for AI Agents

Orientation for an agent picking this project up cold. `README.md` covers how to use and
build it; this file covers how it is put together, what is fragile, and why several things
look the way they do.

## Start here

**Plans directory:** [plans/README.md](plans/README.md) indexes the active plan,
completed/superseded archives and their handoffs.

**Research plan entry point:** [MAIN_PLAN.md](plans/MAIN_PLAN.md) owns current
work or the no-active-plan pointer after closeout. Follow it to the owning plan
and handoff for phase status, evidence and the next authorization decision;
this startup page does not duplicate them.

**Preserved prior work:** [archived plans](plans/README.md#archived-plans)
retain their original evidence and limitations. Dated next-action statements
in archived records are not current work orders.

**Resource constraints:** the [repeated Windows commit exhaustion](Research/omr/reports/zeus-attribution/phase2/crash-recurrence-20261004/REPORT.md)
has no verified initiating cause or durable remedy. The [enforced CPU safeguards](Research/omr/reports/zeus-attribution/phase2/safety-fix-20261004/REPORT.md)
remain mandatory: recorded supervisor, one heavy worker, 85% RAM/commit stops,
4 GiB reserve, worker containment and bounded deadlines. Keep the plan's existing
usage stop and separate GPU admission. Check live jobs/locks before execution;
never automatically retry pressure failures or invoke Git during recovery.
C-only system-managed paging and the prior 18 GiB allocation are recorded
historical evidence, not a substitute for fresh resource preflight.
Historical screening/evaluation identities remain frozen.

**Previous comparison:** screening Stages 1-4 are complete. The
[historical comparison baseline](plans/archive/2026-09-26-omr-screening-comparison.superseded.md) owns its frozen
contracts; the [Stage 4 decision](Research/omr/reports/screening/v1/stage4-evaluation/REPORT.md)
retains shipped HOMR. Its numbered stages and older handoffs are background,
not phases of the active main plan.

Sheet2Play is a Windows C#/Raylib desktop app with a Python OMR bridge. The user launches
`dist\Sheet2Play.exe`; research tooling under `Research/omr/` is separate from the app.

| Task | Read next |
| --- | --- |
| Implement or review the current research phase | [MAIN_PLAN.md](plans/MAIN_PLAN.md), its current handoff and relevant code/tests |
| Explore the project | [Architecture](#1-what-the-project-is), [layout](#2-layout), and [user README](README.md); inspect entry points/manifests |
| Verify the comparison evaluation freeze | [Comparison Phase 1 handoff](Research/omr/PHASE1_HANDOFF.md) and [frozen scoring protocol](Research/omr/reports/phase1/scoring-protocol.json) |
| Change frontend/bridge behavior | Relevant [invariants](#3-things-that-will-bite-you), affected code/tests, and [verification](#4-verification) |
| Investigate completed work or an old proposal | [Historical milestones](#completed-and-historical-research-milestones), then only the relevant plan/handoff or [findings](Research/omr/reports/diagnosis/FINDINGS.md) |
| Review upstream HOMR changes | [October 6 audit](Research/omr/reports/diagnosis/UPSTREAM_AUDIT_2026-10-06.md): merged exporter fixes #171/#178, pending training work and unchanged checkpoint inventory; [September 29 audit](Research/omr/reports/diagnosis/UPSTREAM_AUDIT_2026-09-29.md) and [September 26 audit](Research/omr/reports/diagnosis/UPSTREAM_AUDIT_2026-09-26.md) preserve earlier findings. These notes do not authorize execution. |

MAIN_PLAN.md defines active work or links its closed record; handoffs/reviews record execution and limitations.
The user's latest explicit decisions govern scope. Follow [AGENTS.md](AGENTS.md) for
plan lifecycle, efficient execution, search boundaries and release requirements.
This index does not authorize the next phase. Update its active links when phase status
changes. Load history and detailed sections below only when relevant to the request.

<!-- STARTUP_CONTEXT_END -->

---

## 1. What the project is

A Windows desktop application that turns sheet music into animated, playable piano roll
output. A PDF, scan or photo goes in; falling notes above an 88-key keyboard come out,
synchronised to MIDI playback.

Two processes:

| Half | Language | Owns |
| --- | --- | --- |
| `Visualization_engine/` | C# / .NET 9 / Raylib | UI, rendering, playback timing, caching |
| `Bridge/` | Python 3 | Optical Music Recognition, MusicXML normalisation |

They communicate by the C# side launching the Python process and parsing structured
progress lines from its output. This split is deliberate: OMR engines are heavy ML models
that crash and leak, and a crash there must not take the UI down.

`Research/omr/` is a separate research area for evaluating and improving recognition. It
is not part of the shipped app.

---

## 2. Layout

```
Visualization_engine/        C# app (assembly: Sheet2Play)
  Program.cs                 main loop, state machine, all screen drawing
  Program.Smoke.cs           headless --smoke rendering (partial of Program)
  SongCache.cs               cache, library, app-root resolution
  Playback.cs                playback clock, session, MIDI output
  UiDesign.cs                UiTheme + UiLayout, fonts, drawing primitives
  OmrPipeline.cs             engine enum, bridge invocation, error types
Visualization_engine.Tests/  xUnit suite (discover counts at test time)
MidiTester/                  MIDI regression harness + library diagnostics
Bridge/                      bridge.py and the Python OMR pipeline
Research/omr/                dataset tools and engine evaluation
scripts/                     publish.ps1, install-shortcut.ps1
```

---

## 3. Things that will bite you

These are all real incidents from this project, not hypotheticals.

### 3.1 The C# sources are decompiled output

In August 2026 an automated `git restore` reverted tracked files to their April state and a
follow-up `git reset` deleted ~35 files that had only just been committed. They were
recovered from a discarded reflog commit by decompiling the last good binary.

The behaviour is faithful — the rebuilt DLL matched the pre-incident binary byte for byte in
size, and the tests pass — but **there are no original comments**, and the code uses
decompiler idioms: `num`/`num2` locals, `(object)x != null` null checks, explicit record
copy constructors. Missing comments are expected, not a sign of incomplete recovery.

Watch for leftover decompiler scars. Two were found and fixed: a numeric enum comparison
`(uint)(state - 4) <= 1u` that silently broke when a `GameState` member was added, and an
inlined `(StartTime + Duration)` where `Note.EndTime` exists. Others may remain.

Recovery snapshots are pinned locally as branch `recovery/pre-reset` and tags
`recovery-snapshot-fa08f25` / `recovery-decompile-85997e2`. **These are local-only and were
never pushed. Do not delete them.**

### 3.2 User data lives outside the repo

Everything the app stores is in **`%LOCALAPPDATA%\Sheet2Play`** — note *Local*, not Roaming:

```
settings.json  recent.json  failed-omr.json
songs\pdf\            source scores
songs\midi\custom\    .mid / .mxl shown in the MIDI Player column
songs\midi\<engine>\  validated caches, one folder per engine
```

Resolution order is `SHEET2PLAY_HOME` → `%LOCALAPPDATA%\Sheet2Play`. There is deliberately
no repo fallback: source and published builds share one library. `AppSettingsStore`,
`RecentSongsStore` and `OmrFailureStore` already used Local, so `SongCache` matches them.

If the app shows an empty library, check where it resolved to before assuming data loss:

```bash
dotnet run --project MidiTester      # prints the resolved library and per-folder counts
```

### 3.3 The csproj `<Content>` rules are load-bearing

`SynthesiaClone.csproj` must copy `assets/**` and `..\Bridge\*.py` to the output. When these
rules were lost, the app still built and ran — but silently fell back to Raylib's default
font, and the OMR pipeline would have failed at runtime because `bridge.py` was not beside
the executable.

`ExcludeFromSingleFile` on the assets is also required: `PublishSingleFile` embeds binary
content inside the .exe, while `UiDesign` loads fonts from disk relative to
`AppContext.BaseDirectory`. Without it the published app renders with the wrong font while
building and running perfectly.

Use a single-level glob for the bridge (`..\Bridge\*.py`). A recursive one sweeps in
`.venv-homr-gpu` and copies thousands of files on every build.

### 3.4 Failure handling is deliberate, not sloppy

Several places skip a bad element rather than aborting. This is a design decision, made
after single invalid items repeatedly destroyed whole conversions:

- `PlaybackSession` drops unplayable notes (zero duration, out-of-range key) and logs the
  count. It throws only if *every* note is unplayable.
- `musicxml_normalizer.py` skips hallucinated and microtonal notes with a warning.
- `SongCache.GetPdfLibraryCore` deliberately accepts `.png/.jpg/.jpeg/.bmp/.tif/.tiff/.webp`
  alongside `.pdf`, because scanned images are valid OMR input.

Do not "fix" these by making them strict again.

### 3.5 Cache identity

Cached results are keyed on **SHA-256 of the source file plus the engine**, not the
filename. Each cache carries a manifest recording the source hash, engine and model
revision; a cached entry is invalidated when the model revision changes. Because a cache hit
returns instantly and is indistinguishable from a fresh run, loading a source that already
has a cache prompts the user, offering Use cached / Re-run / Cancel.

---

## 4. Verification

Match verification to the change. Documentation-only edits require local link checks and
verification of the documented search scope. Research-only edits require relevant Python
tests. Changes to shipped code or runtime assets require the release gate:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\verify-release.ps1
```

The gate runs the .NET suite, publishes, checks assets, and launches the published app.
Run affected Python suites as well; the gate does not run them:

```powershell
Research\omr\.venv\Scripts\python.exe -m pytest Bridge/tests Research/omr/tests -q
```

Counts are deliberately not pinned here. This section has claimed 55 while the suite held 50
and then 69; a number that drifts is worse than no number, because it invites someone to
"fix" a passing suite to match a stale doc. Expect zero failures instead.

For UI work, `dist\Sheet2Play.exe --smoke .\ui-snapshots` renders every screen with a hidden window and
a null MIDI output, so frontend changes can be checked without launching the app. It also
prints the resolved library and its contents, which catches a perfectly-rendered UI pointing
at the wrong folder.

The running executable locks its own output location: an installed instance locks `dist`,
while a development instance can lock `bin`. The release gate closes the app before publishing.
For an isolated compile check, choose an unused output directory:

```bash
dotnet build Visualization_engine/SynthesiaClone.csproj -p:BaseOutputPath=../tmp/compile-check/
```

Word COM automation (used to produce the internship report) hangs on PDF export on this
machine; LibreOffice is not installed. Neither is needed for the app.

---

## Completed and historical research milestones

Reference evidence only. These dated entries preserve previous decisions and
interruptions; their old next-step and stop instructions are not the current queue.
Current research lifecycle and the next authorization decision are recorded in [MAIN_PLAN.md](plans/MAIN_PLAN.md).

**Canonical Stage 4 complete (2026-09-30):** The user requested evaluation of the
completed five-candidate screen. The [Stage 4 review](Research/omr/reports/screening/v1/stage4-evaluation/REPORT.md)
records **retain shipped HOMR; no accuracy-led challenger confirmation now**.
Shipped/fine-tuned uncertainty is inconclusive; no promotion gate is met. Fresh
audit verified 295 results, 295 scores, 1,257 declared artifacts, complete duration
matrices and eight paired claims. Focused fixtures: 14 passed; full research/bridge:
239 passed, 2 skipped, 9 subtests passed. No inference/scoring rerun or app change.
The historical 343-page remainder is screen-disjoint, **not wholly untouched**:
207 pages already had shipped inference. Only 135 pages/44 whole compositions
have no recorded prior attempt, with composer/review/training limitations. Optional
shipped/fine-tune estimates: 4.36 hours on that inventory, 11.07 on the 343-page
extension. Read the [screening handoff](Research/omr/SCREENING_HANDOFF.md) and
[Stage 4 job record](Research/omr/reports/screening/v1/stage4-evaluation/job-record.md).
**Next decision:** end comparison, separately request bounded Stage 5/readiness,
or authorize preregistered confirmation after eligibility is resolved. Stop before
confirmation, Stage 5, training, cloud spending or promotion; none was started.

**Stage 3 complete (2026-09-30):** The user authorized consolidation after Zeus
scoring. The [five-candidate report](Research/omr/reports/screening/v1/2c98d5638c36/reports/consolidated-stage3-836fb923bb33/REPORT.md) verifies all **295 result/score
pairs** on the unchanged 59-page / 18-composition sample. Primary F1: shipped HOMR
0.4061, repaired fine-tuned HOMR 0.3844, corrected 455 0.2857, Audiveris 0.0986,
neutral Zeus 0.0228. Eight composition-paired comparisons provide no supported
challenger superiority; the shipped/fine-tuned gap is inconclusive. All scores and
summary hashes passed audit; 14 report/statistics/analysis fixtures passed.
Zeus's prior RAM interruption was resolved after RAM relief; all sessions are closed,
no worker lock remains. Valid outputs do not explain Zeus's low transcription accuracy.
Read the [screening handoff](Research/omr/SCREENING_HANDOFF.md) and
[CPU job record](Research/omr/reports/screening/v1/stage3-cpu/job-record.md).
**Historical next action, now completed above:** Stage 4 review/decision. Stop before
untouched confirmation, Stage 5, training, cloud spending or promotion.

**Historical Zeus scoring-only stop (2026-09-30; superseded by consolidation):**
After the user freed RAM, the unchanged scorer reused 23 verified scores, retried
page 24 and completed all 59 scores. Session closed at 7011.924 seconds;
[final Zeus audit](Research/omr/reports/screening/v1/stage3-cpu/zeus-final-audit.json)
passed. The earlier user-directed stop before consolidation was respected, then
superseded by the latest request to finish Stage 3.

**Historical Zeus assistant-model pause (2026-09-30; scorer later resumed):** All59
inference outcomes succeeded and result/artifact hashes verified, including324
systems/1061 preserved raw files. Inference completed in64.8minutes without interruption.
Fresh development/admission and46 fixtures/full239-test regression passed.
Scoring parent77506 exited1 after sustained90% RAM pressure (peak94.8%) on page24;
23saved scores passed exact identity/hash verification, all23 OMR-NED valid.
Page24 remains pending, not a model zero. No worker/lock remains; closed cumulative
session5432.674seconds (90.5minutes), unchanged90% policy/four-hour cap.
Read the [CPU job record](Research/omr/reports/screening/v1/stage3-cpu/job-record.md)
and [screening handoff](Research/omr/SCREENING_HANDOFF.md). The user resumed scoring,
free RAM/recheck resources and identities, then retry the unchanged scorer with
`--retry-pending` using the same session and23cached scores. User's intended split:
cheaper assistant supervises remaining scoring and stops after59scores/summary
verify; later stronger assistant performs consolidated report/final review.
Stage3 remains incomplete. No automatic restart, confirmation, Stage5, training or promotion.

**Historical Stage 3 stop before Zeus (2026-09-29; superseded above):** The user requested Zeus
in a later prompt. Audiveris completed all 59 outcomes/scores, primary F1 0.0986,
eight failures and 52.0 minutes; every identity/artifact/summary hash verified.
No worker/lock remains. Zeus development, admission and screening have not started;
Stage 3 and the five-candidate consolidation remain incomplete. Read the
[CPU job record](Research/omr/reports/screening/v1/stage3-cpu/job-record.md) before
resuming. It preserves runtime access failures and the separately pinned
[v5 CPU manifest](Research/omr/reports/screening/v1/manifest-v5-607ff64134da.json),
with complete readable package inventory and unchanged sample/scorer/90% policy.
Audiveris inference/scoring parents 54939/26551 exited zero; no interruption,
RAM peak 76.9%. Final regression: 239 passed, 2 skipped, 9 subtests passed.
Preserved HOMR 177 results/scores verified. Wait for the later Zeus request, then
reverify the runtime and run fresh development/admission before frozen inference.
Zeus uses the neutral CPU recognition route with its existing GPU detector. Preserve
all HOMR baselines, run one candidate/scorer at a time, and stop before confirmation.

**Selected comparison plan (2026-09-26):** The user replaced the exhaustive-first
sequence with a bounded, roughly 60-page composition-grouped screen. Read the
[canonical comparison plan](plans/archive/2026-09-26-omr-screening-comparison.superseded.md) for the active work
order: verify interrupted evidence, screen shipped/fine-tuned/455 HOMR first,
then Audiveris and Zeus, report, and stop before any larger confirmation run.
The [screening handoff](Research/omr/SCREENING_HANDOFF.md) records **Stages 1 and 2 complete and the requested HOMR-only part of Stage 3 complete**:
255 interrupted reports verified (251 successes, four completed failures), all
1,008 artifact hashes valid, and the primary/secondary audits reverified at
402/402 and 611/611. Item 256 remains an empty partial attempt. Three sequential
resource-limited HOMR development pages passed; RAM briefly peaked at 81.9%,
so unattended stability remains unproven. The hard-freeze cause and fine-tune
export mismatch was unresolved at that historical handoff (resolved below). Stage 2 froze a deterministic screen of **18 full
composition groups/59 pages** with separate gated prepare, admit, run, score, and report
commands. Shipped HOMR and pinned HOMR 455 each completed 59-page screens and scores;
the [interim HOMR report](Research/omr/reports/screening/v1/2c98d5638c36/reports/interim-homr-dd1c0a4aeea5/REPORT.md)
contains the paired comparison.

**Historical fine-tune intake (2026-09-28; subsequent Stage 4 below supersedes its stop):** Phases 1–3 of [the saved repair plan](plans/archive/2026-09-28-homr-finetune-export-repair.done.md)
are complete. The approved source/tokenizer/provenance bundle arrived from private
`Artemixss/report` commit `9bf0d47`; strict checkpoint loads and CPU export parity passed.
The historical decoder hash is stale. Three complete development pages passed through
the local CUDA comparison path under the [final v4 child manifest](Research/omr/reports/screening/v1/manifest-v4-502777eed80a.json)
and [fresh admission](Research/omr/reports/screening/v1/2c98d5638c36/admissions/fine_tuned_homr/9fa13d27f0b7/admission-23d1108e5364.json).
Full regression: 213 passed, 2 skipped, 9 subtests passed. Remote CUDA error 9 is
preserved separately; it did not reproduce locally. No training, re-export, new binary
transfer, production change, or frozen fine-tune screening occurred. **Stop before
Phase 4**; future screening needs a new request. [The job record](Research/omr/reports/screening/finetune-export/job-record.md)
contains commands, identities, resource measurements and verification links. Remote-host
tools could not retrieve the chat; that did not establish that the remote PC was offline.

**HOMR-only Stage 4 complete (2026-09-28):** After the RAM-work pause, the user
authorized corrected fine-tune/455 screening and analysis under the [combined v4 manifest](Research/omr/reports/screening/v1/manifest-v4-e31f2e628e16.json).
Both passed fresh complete-page admission and completed all 59 outcomes/scores with
verified identities/artifacts/summaries. Fine-tune: zero failures, 61.7 minutes; corrected
455: one conversion failure, 61.1 minutes; no resource interruptions or live workers.
The [final report](Research/omr/reports/screening/v1/2c98d5638c36/reports/homr-only-stage4-e35f73ca9f75/REPORT.md)
gives primary F1 **0.4061 shipped / 0.3844 fine-tuned / 0.2857 corrected 455**.
Paired intervals cross zero; neither challenger has supported superiority. Keep shipped
HOMR. Full regression: 219 passed, 2 skipped, 9 subtests passed. [The job record](Research/omr/reports/screening/v1/stage4-homr/job-record.md)
preserves exact commands, provenance, logs and timing milestones. **Stop here:**
Audiveris/Zeus and consolidation remain for a separate request, followed by a separate
decision before any untouched confirmation; no training or promotion occurred.

**455 correction (2026-09-27):** [the interim HOMR review](Research/omr/SCREENING_HOMR_REVIEW.md)
identified a decoder/source mismatch (three position classes versus five). The
[screening handoff](Research/omr/SCREENING_HANDOFF.md) now records an independently
validated repair: complete 455 release source, a checked-in ordered-vocabulary/ONNX
contract, a new immutable v3 identity, three successful complete-page development
runs, and admission. The old 455 outputs remain historical evidence, not a valid
model-quality comparison; **no corrected 59-page screen or score exists**. The fine-tune
was blocked then by missing provenance, now resolved by the intake above. A
user-authorized 95% RAM limit applied only to the corrected development runs; future
screening's 90% policy still needs a separately versioned runner/manifest. Audiveris
and Zeus belong to another request. Preserve
the retired sequence's stale state; check live processes before any later run. The
[Phase 3 handoff](Research/omr/PHASE3_HANDOFF.md),
[interruption handoff](Research/omr/PHASE3_EVALUATION_TRANSFER_HANDOFF.md),
[progress review](Research/omr/PHASE3_PROGRESS_REVIEW.md), and job record are
historical execution evidence, not the active work plan.

## 5. OMR research state

**Historical research context; older proposals superseded as the execution plan.**
Use the [plans index](plans/README.md) and [main plan](plans/MAIN_PLAN.md) with its
current handoff for new work. The [archived comparison](plans/archive/2026-09-26-omr-screening-comparison.superseded.md)
and [completed comparison Phase 1 handoff](Research/omr/PHASE1_HANDOFF.md) retain the
historical contracts. Measurements below describe their original samples, revisions,
and scorers; they are not eligible candidate
rankings under the frozen protocol. Alignment-assisted scores are diagnostics only.
Upstream PR status, checkpoint availability, costs, and training status are dated observations,
not live facts. Verify them before acting. Retain the evidence without reviving old work orders.

### Engines in the app

| Engine | Notes |
| --- | --- |
| `Homr` | Default. Reads pitch well, places notes in time badly on polyrhythm - see below. |
| `Zeus` | GPU path. **Labelled "Oemer GPU" in some UI strings** - same engine, historical naming. |
| `MusicXml` | Bypasses recognition; normalises a symbolic score directly. |
| `DirectMidi` | Bypasses the bridge entirely; parsed in C# by DryWetMidi. |

**homr is installed from git, not PyPI, plus one local patch.** `setup_gpu.ps1` pins commit
`457e7c6` and then applies `Bridge/patches/homr-pr146-retiming.patch` to the installed
package. The current engine revision is `homr-0.7.0.post38+457e7c6+pr146`.

Two upstream changes are why:

- `aa5c8ce` fixes a crash where a rest merged into a chord yields a zero-duration element and
  homr exits non-zero (upstream #136). It is unreleased on PyPI, which is why this installs
  from git at all.
- `5a5a8ee` (**PR #141**) recovers ties from same-pitch slurs. homr has no tie token and
  trains slurs and ties as one class, so this is the only way a tie is read back out, and
  without it an onset falling inside a sustained note cannot be placed.

**PR #146 exists only as a closed pull request**, so there is no commit to pin and it ships as
a patch. Its author closed it after seeing no movement in homr's OMR-NED benchmark, which
does not measure onset placement. Scored on onsets it is the largest single win available.
If the patch stops applying, upstream has moved and it needs reconciling by hand -
`setup_gpu.ps1` prints a warning rather than failing, so check its output after any pin bump.

The research tree under `Research/omr/vendor/homr/` carries the same two changes plus
training-only ones, and is reached by putting it on `PYTHONPATH` (the `patched` variant in
`diagnose_rhythm.py`) so an experiment never disturbs the installed wheel. Use that for
anything unmeasured; the opt-in rule still holds.

The engine revision string lives in **two** places that must agree: `HOMR_ENGINE_REVISION` in
`bridge.py` and `HomrEngineRevision` in `OmrPipeline.cs`. Caches are keyed on it, so bumping
it invalidates every cached conversion by design. `dotnet run --project Visualization_engine
-- --reconvert homr` rebuilds them all in one pass. **A stale `dist/` build is the usual
cause of an empty Cache Playlist** - the published binary validates manifests against its own
compiled-in revision, so republish after any bump.

Exactly one OpenCV distribution may be installed in the homr venv. With both `opencv-python`
and `opencv-python-headless` present they overwrite each other, and every run dies with an
error naming GStreamer rather than the real cause.

`bridge.py` emits only these error codes: `INPUT_INVALID`, `MODEL_INVALID`,
`NORMALIZATION_FAILED`, `RUNTIME_MISSING`.

### What is actually wrong with homr's rhythm

Measured, not assumed. Full write-up in `Research/omr/reports/diagnosis/FINDINGS.md`.

On 100 OLiMPiC scanned systems: **pitch F1 0.960, onset F1 0.585**. 47% of systems emit a
timeline *longer* than the music contains, and that single ratio (`span_ratio`) predicts
onset accuracy better than anything else tried - systems within 1.02x score 0.884, those past
1.15x score 0.269.

The cause is **polyrhythm, not tuplets**. Generated cases vary the two independently, which
no real corpus does because they co-occur:

| case | polyrhythm | onset F1 |
| --- | --- | --- |
| `tuplet_aligned` (24 triplets) | no | **1.000** |
| `offset_entry` (no tuplet at all) | yes | **0.143** |

Every polyrhythm case lands 0.125-0.471; every non-polyrhythm case 0.857-1.000. Upstream
agrees this is a training gap (liebharc/homr#142: "a case homr never covered during
training"), and `training/omr_datasets/convert_pdmx.py` shows why - it caps training data at
complexity 2, excluding dense multi-voice piano entirely.

Three hypotheses were tested and **refuted**; do not re-litigate them without new evidence:

- Metric strictness. A tolerance sweep moves onset F1 only 0.579 to 0.587.
- homr's tuplet-repair heuristic. Disabling it moves the canary 0.159 to 0.174. Note it
  cannot fire on single-measure inputs at all, so generated cases cannot test it.
- A per-voice cursor in the MusicXML generator. Implemented and it changed nothing: homr
  emits one `chord` token in the whole failing measure, so the timing information is not
  there to reconstruct.
- The measure-length estimator behind PR #146's re-timing. Swapping the median for the most
  common measure duration changed 1 of 18 regressed systems; a strict-majority version was a
  no-op by construction. Both removed.

### The representation ceiling, and why it decides the training question

`roundtrip_oracle.py` encodes ground-truth MusicXML into homr's vocabulary and decodes it
straight back, with no model involved. What comes out is the best score a perfectly trained
model could reach. **Run this before proposing any fine-tune**; it is fast and needs no GPU.

The first measurement killed the fine-tune plan: ceiling 0.690 against homr's own 0.624, and
on the systems that actually fail 0.472 against 0.455 - no headroom. Only after the fixes
below did the ceiling rise to 0.766, which is what made training worth revisiting. The
sequence matters: **repair the representation first, then train on labels that are correct.**

Two ways the encoder lies about its own labels, both worth knowing because
`convert_pdmx.py` builds training data with the same code:

- homr outscored a faithful encoding of its ground truth on 7 of 75 systems. When the model
  beats its own label, the label is the defect.
- 24 of 100 systems could not be encoded at all until the slur fix below.

### Fixed without training: onset F1 0.583 to 0.661

Searching upstream's tracker was worth more than any experiment. Most of the fix existed:

| upstream | state | effect |
| --- | --- | --- |
| PR #141 recover ties from same-pitch slurs | merged, after the app's pin | a tie *is* a slur joining adjacent same-pitch notes - homr trains them as one class, so no new token and no retraining |
| PR #146 re-time overflowing measures | **closed by its author** | the large win; he saw "no change in OMR-NED", which does not measure onset placement |
| PR #156 `upper2`/`lower2` positions | open, by a collaborator, already retrained | Plan B, and the likeliest way to raise the ceiling further |
| issue #150 chord split overflows measure | open | this project's symptom, reported independently |
| issue #152 PDMX quality | open | liebharc: "only a few bad examples are needed to degrade performance" - relevant because our patch raises the complexity ceiling 2 to 4 |

Plus one local fix: `_collect_articulation` deduped articulations but not slurs, so a note
both tied and slurred produced `slurStart_slurStart`, absent from `build_slur()`, and the
file was rejected outright. `list(set(slurs))` takes encode failures from 24 to 6. It never
looked like a rhythm bug because it is not one - it silently deleted a fifth of real piano
from everything the encoder touches, training labels included.

Measured on the canary: onset F1 0.583 to 0.661, systems running long 52% to 34%, mean span
1.128 to 1.088, perfect systems 16 to 25, pitch unaffected. **It also regresses 18 of 100**,
all sharing one signature - already correct at span 1.00 and pushed below it. Cause still
open; the next hypothesis is to leave a measure alone when its decoded length is already
musically plausible.

### Shipped, and what it did to the real library

Both engine fixes are **live in the app** as of engine revision
`homr-0.7.0.post38+457e7c6+pr146`, and all 46 library sources were reconverted against it.

| change | library onset F1 |
| --- | --- |
| engine fixes (PR #141 + #146) | **+0.0801** |
| page-stitching fix | +0.0066 |

`Score C`, the score originally reported as playing wrong, went 0.224 to 0.678.

Three things a future session should not have to rediscover:

- **PR #146 regresses 18 of 100 canary systems**, all of which were already correct at span
  1.00 and get pushed below it. The cause is open. The measure-length estimator was the
  obvious suspect and has been **ruled out** by measurement, so do not retry it. If the user
  reports one song sounding worse after an engine change, this is the first thing to suspect.
- **The engine drops about 5.7% of notes**, and that is fine. It shrinks over-long measures,
  so some notes reach zero duration and the validator discards them - 846 across the library.
  pitch F1 moved 0.870 to 0.867, so what goes is homr's duplicated output rather than real
  music. Do not "fix" this without checking pitch recall first.
- **Two caches sit on old revisions** because their source PDFs are no longer in `songs/pdf`. `--reconvert` only touches songs whose
  source still exists. They are orphans, not failures.

### Benchmark corpora do not predict this app

OLiMPiC is *scanned*; the library is engraved MuseScore PDFs, and they are not comparable.
Upstream measures PR #141's tie recall at 0.93-1.00 engraved against 0.04-0.12 on scans, and
the first library song scored onset F1 0.921 where the canary average is 0.583. `evaluate_library.py`
scores the real library against the references listed in a local `reports/library/pairs.json`
(not committed - it names a personal collection), caching
each bridge payload under `reports/library/predictions/` so later analysis costs no GPU;
`diagnose_library_drift.py` reads that cache.
Prefer MusicXML over MIDI as a reference where possible: a MuseScore MIDI is the rendered
performance with repeats expanded, so it will not align with the printed page the OMR reads.

Also note `generate_polyrhythm.py`'s cases are single-measure, and both the tuplet heuristic
and PR #146's re-timing compare a measure against the median of the others - so that corpus
cannot test either, and a flat result there is an artifact rather than evidence.

### Research tooling

All under `Research/omr/`, all reusing one bridge runner (`src/sheet2play_omr/engines.py`):

| Script | Purpose |
| --- | --- |
| `diagnose_rhythm.py` | Canary run with cached predictions; exact vs tolerant metrics, span ratio |
| `generate_polyrhythm.py` | Engraves 11 targeted cases via MuseScore; labels exact by construction |
| `compare_engines.py` | Scores any engine against ground truth; `--engine`, DPI sweep |
| `setup_training.sh` + `patches/` | Rebuilds the training environment on another machine |
| `download_smb.py` | Sheet Music Benchmark fetch (gated; access granted) |

`src/sheet2play_omr/metrics.py` holds `calculate_note_metrics` and `span_ratio`;
`omr_ned.py` adds OMR-NED, the metric published OMR results are quoted in. **OMR-NED runs
opposite to everything else - lower is better.**

Two datasets worth knowing: upstream's benchmark release ships `smb_homr.db`, homr's own
predictions and expected output over 685 SMB pages, which can be mined without running
anything. PDMX is the lawful MuseScore corpus (250K scores, PDF+MIDI+MusicXML, ungated) and
is already what homr trains on - scraping MuseScore would reproduce its training set.

### Datasets on hand

| Dataset | Size | Licence | Use |
| --- | --- | --- | --- |
| OLiMPiC scanned | 2,931 aligned samples | CC BY-SA 4.0 | Real scans, robustness eval |
| OpenScore Lieder | 1,352 scores | CC0 | Volume; `download_openscore.py` |
| Generated polyrhythm | 11 cases | own | The regression suite for rhythm work |
| Local library | 40 PDFs | third-party | **The real evaluation target** |

OLiMPiC is derived from OpenScore Lieder - the same repertoire in two forms, not two
corpora. Both are voice-and-piano, so neither matches dense piano.

### Superseded engine evaluations

The earlier `antoniorv6/smt-grandstaff` experiment did not establish an improvement over
HOMR under its setup. Older SMT checkpoints are outside the current comparison.
The former claim that LEGATO requires approximately 20 GB VRAM is withdrawn as an
unverified assumption. Follow the canonical plan's dedicated checkpoint/loader requirements
and measure actual RAM/VRAM on development examples; do not infer memory from the encoder name.

One lesson from that work still applies generally: **rendering DPI dominated SMT results**,
7x from resolution alone. homr, by contrast, is DPI-insensitive - it rescales each detected
staff to a canonical height, so the hardcoded 300 in `render_pdf.py` is fine.

### Historical fine-tuning notes — superseded as a work order

Viable, and the prerequisites all exist: PyTorch weights for run 426 are published,
`train_transformer` takes `resume` and `fine_tune` (lr 1e-5), and there is a backbone-freeze
callback. Two traps:

- Upstream's `fine_tune=True` unfreezes **only the lift (accidentals) branch** - a leftover
  from PR #52. Rhythm is a perception failure, so a frozen encoder cannot fix it. The
  vendored patch changes this.
- Training auto-downloads and converts **all five** corpora unless `dataset_index` is
  trimmed.

Constraints: Linux (WSL2 works), documented VRAM floor **8 GB**, ~12 GB of data, 2-4 days.
Training caps itself at 90% of VRAM (`SHEET2PLAY_VRAM_FRACTION`) so the machine stays usable.
Watch throughput in the first 15 minutes - a contributor in liebharc/homr#61 hit 70 s/it
under WSL, a 115-day run, while others get 1-2 s/it. Above ~10 s/it, stop; renting is ~$3-5.
Rare-token collapse is the likeliest failure: adding rare tokens took someone's SER from 26%
to 132%.

### Earlier proposed next steps — superseded

The priority order below is retained as historical rationale. It does not supersede the
five phases in the canonical comparison plan or authorize a new training run.

**1. Localised over-accounting.** This was "page count correlates -0.783 with onset accuracy and
nobody knows why". It has been measured, and **the page-count correlation does not survive the
measurement**. Full write-up in FINDINGS.md; the short version:

- **The metric cannot tell displacement from scatter.** Onsets are matched by exact absolute
  equality with no alignment, so a transcription that is musically correct but shifted in time
  scores near zero while span stays 1.00 and pitch stays high. That is the signature the old
  reading attributed to scatter.
- **Correcting displacement takes the correlation to nothing.** Across the eleven scored pairs,
  page count against onset F1 is -0.454; against onset F1 after each 16-quarter window is shifted
  by its own measured offset, **-0.005**. Mean onset F1 on the seven confirmed pairs goes
  **0.2922 to 0.6558**, against a shuffled-reference control of 0.1346.
- **`Score J` is the clean case.** Pitch agreement 0.992, note ratio 0.997, onset F1
  0.118. One shift of -8.25 quarters takes it to 0.806. The engine gains 8.25 beats inside the
  first eighty and transcribes the remaining four hundred of an eight-page score essentially
  perfectly.
- **Page boundaries are not where the drift jumps.** 164 offset jumps across the scored songs, 32
  in a window containing a page boundary, against a chance rate of 0.177 versus 0.195 observed.
  This is the direct version of the earlier aggregate refutation.
- **Three of the original seven references were not the same music as the PDF.** Pairing is now
  a reviewed local `Research/omr/reports/library/pairs.json`, not filename equality, and it records
  the pairings that must *not* be made as well as the ones that hold.
- **Source quality beats score length.** `Score G` and `Score H` are two PDFs sharing a piece, a
  reference and a page count; one recovers to 0.614 and the other to 0.198.

**Confirmed on exact labels.** `build_olimpic_scores.py` rebuilds whole multi-page scores out of
OLiMPiC's single systems - the per-system MusicXML carries consecutive measure numbers, so the
systems tile the piece and concatenate into an exact label. Twenty rebuilt scores, two to six
pages:

| | single systems (n=100) | whole scores (n=20) |
| --- | --- | --- |
| onset F1 as measured | 0.6607 | **0.5206** |
| after local correction | 0.7516 | **0.7714** |
| shuffled-pitch control | 0.2245 | 0.1660 |

A whole score scores 0.14 *worse* than its own systems, and after correction slightly *better*. The
engine is no worse at a page than at a crop; everything it loses over length is displacement - on
labels no MuseScore MIDI was involved in. `5071629` is the cleanest case anywhere in this project:
pitch agreement 1.000, onset F1 0.154, and **0.963** after one shift.

What is still open is the localised over-accounting itself: finding the measures where a score
gains its extra beats. Two failures survive correction and they are different - real span
inflation (`4985990`, 51% long over 141 measures, 0.157 after correction) and outright reading
failures (pitch agreement 0.43-0.52, where timing never enters into it).

**2. Training, whose target changed.** Do not start a fine-tune on the current vocabulary
without re-reading the ceiling argument in FINDINGS.md. The short version:

- Before the fixes, the ceiling was 0.690 against homr's 0.624 - no headroom, and training was
  not worth GPU time.
- The earlier claim of roughly +0.18 learnable headroom mixed sample sets and is superseded
  by the matched-sample estimate below; it is not an acceptance target.
- **The headroom is +0.096, not +0.182.** The larger figure compares means over different sample
  sets. On the same 94 systems homr is 0.6636 against a ceiling of 0.7598, and correcting *both*
  for displacement moves them together (0.7547 against 0.8510) - so the gap is real and not a
  metric artifact, but it is half what CONTEXT used to claim. Against it, fixing displacement is
  worth **+0.251** on whole scores and costs no GPU. Fix the displacement first.
- **Upstream PR #156** is the more interesting target. It splits the position vocabulary into
  `upper`/`upper2` and `lower`/`lower2`, which is what lets two voices on one staff be told
  apart, and a collaborator has already trained it without regression. Its checkpoint (run
  445) is **not published** - the release URL 404s - so getting its benefit means training it.
  A clone sits at `Research/omr/vendor/homr-pr156/`.
- PR #156 does **not** move the round-trip ceiling (0.689, the same as this tree straight
  after PR #141). That is expected rather than damning: the oracle starts from correct ground
  truth, so it cannot see a recognition fix. It means #156 and the shipped decoder fixes are
  complementary, and the sensible training run stacks them.
- Training runs on a second machine the user has access to; the environment is built by
  `Research/omr/setup_training.sh`, which needs WSL2 because the dataset converters use a
  Linux-only MuseScore AppImage. Watch seconds/iteration in the first 15 minutes and abort
  above ~10 s/it - upstream issue #61 has a contributor who hit 70 s/it under WSL, which would
  be a 115-day run.

Ground truth for the library is thin: of 46 songs, 11 have a reference after the pairing review
and 7 of those are confirmed. A MIDI is a rendered performance rather than the printed page, so
note counts differ from the transcription by 0.16x to 1.47x. The user has suggested automating MuseScore
downloads to fix this; if that happens it should fetch **MusicXML, not MIDI**, from the same
score page as the PDF. For training data at scale, PDMX already provides 250K public-domain
MuseScore scores with PDF, MIDI and MusicXML, so there is no reason to build a scraper.

## 6. Conventions

- Follow [AGENTS.md](AGENTS.md) for shared conventions, verification, and search scope.
- Preserve existing user changes and recovery refs during refactors. Inspect Git state first;
  never use restore/reset/clean to discard unrelated work. A historical incident lost work
  through an automated restore; that is not a reason to commit unrelated changes automatically.
- Each OMR engine gets its own virtual environment; do not merge their dependencies.
- Code goes in `Research/omr/vendor/` when vendored from upstream; it is gitignored.
- Model weights, datasets and `.runtime/` directories are gitignored — a 114 MB
  safetensors file and a 29 MB checkpoint were nearly committed once.


## 7. Historical documentation maintenance

### Documentation maintenance handoff — 2026-09-17

The documentation cleanup is complete. Astra's supplied plan is saved as the canonical
comparison plan, with its scientific body preserved except for two portable local links.
Shared rules live in AGENTS.md; CLAUDE.md points there. Older proposals are labeled
superseded, historical evidence is preserved, and stale roadmap/runbook references are repaired
or explicitly marked unavailable. Routine ripgrep discovery now lists eight project Markdown
files through `.rgignore`; downloaded material and licenses remain on disk.
Local link checks and `git diff --check` passed. No runtime code or frozen evaluation artifacts
were changed by this cleanup, so no app publish was needed. Changes remain uncommitted alongside
pre-existing Phase-1 work; preserve that work. At that historical stop point Phase 2 had not
started; later completed-phase handoffs supersede that historical status. Work stopped after
the usage check reached 13% remaining, below the repository's 15% threshold.
