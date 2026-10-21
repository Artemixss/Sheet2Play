# Sheet2Play — Context for AI Agents

Reference, not startup reading: [AGENTS.md](AGENTS.md) says which section to open for which
task. `README.md` covers how to use and build the app; this file covers how it is put
together, what is fragile, and the research background.

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
Visualization_engine/        C# app: SynthesiaClone.csproj, assembly Sheet2Play,
                             Raylib + DryWetMidi, net9.0-windows
  Program.cs                 main loop, state machine, all screen drawing
  Program.*.cs               partials: Smoke (headless --smoke), Score (bar lines, pedal
                             lane, EXPORT panel), Expression (EXPRESSION panel), Piano,
                             Batch (--convert-batch), Bench, RenderAudio, Verification
  SongCache.cs               legacy MIDI caches, library, app-root resolution
  SongCache.Packages.cs      song packages: layout, identity, re-interpretation
  SongPerformance.cs         performance.json reader and SongTimeline (beats -> seconds)
  SongExpression.cs          pedal, dynamics, articulations, auto pedal
  SongOverlay.cs             bars and pedal spans drawn over the note field
  TempoMapStore.cs           per-song tempo maps (TEMPO panel: Program.Tempo.cs)
  Playback.cs                playback clock, session
  AudioOutput.cs, Sfz*.cs,   piano backends: SFZ (Salamander), SoundFont (YDP via
  SoundFontEngine.cs         MeltySynth), silent when no piano is installed
  UiDesign.cs                UiTheme + UiLayout, fonts, drawing primitives
  OmrPipeline.cs             engine enum, bridge invocation, profile pins, error types
Visualization_engine.Tests/  xUnit suite (`dotnet test`; discover counts at test time)
MidiTester/                  MIDI regression harness + library diagnostics
Bridge/                      bridge.py and its sibling imports (pinned by the 465/480
                             profiles); song_entry.py wraps it and writes the song
                             package; song_model.py derives performance.json from stored
                             MusicXML; timing_correction.py is the TIMING FIX layout
Omr/, Research/omr/          dataset tools, OMR experiments and engine evaluation
plans/                       execution plans; MAIN_PLAN.md is the current one
scripts/                     publish.ps1, install-shortcut.ps1, verify-release.ps1
pianos/                      large piano samples; not shipped, excluded from searches
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
settings.json  recent.json  failed-omr.json  audio.log  tempo-maps.json
songs\pdf\             source scores
songs\scores\<engine>\ song packages, one folder per conversion (HOMR 480/465, MusicXML)
songs\midi\custom\     .mid / .mxl shown in the MIDI Player column
songs\midi\<engine>\   legacy MIDI caches (426, Zeus, older 465), playable until re-converted
pianos\  soundfonts\   installed Salamander bank and YDP SoundFont
exports\               Export MIDI / MusicXML / WAV / MP3 output
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
filename. Because a cache hit returns instantly and is indistinguishable from a fresh run,
loading a source that already has a cache prompts the user, offering Use cached / Re-run /
Cancel.

**Song packages** (HOMR 480/465 and MusicXML imports, `SongCache.Packages.cs`) have three
identity layers:

1. **Recognition** (only OMR rebuilds it): source SHA, engine, runtime profile SHA,
   `song_entry.py` SHA and page SHAs. Pinned engines put the profile SHA in the folder name.
2. **Interpretation** (`derived/<key>/`, rebuilt from the stored pages in seconds): SHA of
   `song_model.py`, `timing_correction.py` (or `off`) and the schema. Turning TIMING FIX on or
   off, or changing the interpreter, re-interprets on the next load with no OMR.
3. **Playback policy** (never cached): repeats, pedal, dynamics, articulations, piano,
   playback rate and tempo, applied when `SongTimeline` builds the notes.

**Editing a pinned Bridge file re-converts the library.** `bridge.py`,
`musicxml_normalizer.py` and the other files the 465/480 profiles pin are part of the profile
SHA, so changing one means re-provisioning, updating both C# pins and re-running every
465/480 song ([Bridge/HOMR465.md](Bridge/HOMR465.md#homr-480)). Put new behaviour in the
unpinned `song_entry.py` / `song_model.py` path, or in C#, instead.

**Legacy MIDI caches** (manifest v2: 426, Zeus, and 465 songs converted before packages)
record source hash, engine and model revision, and are invalidated when the revision
changes. They play as before with a MIDI (LEGACY) badge and a Re-convert action.

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

## 5. OMR research state

Background for research work. Figures below describe their original samples, revisions and
scorers: they are diagnostics, not eligible candidate rankings, and upstream PR status is a
dated observation. Current work lives in [MAIN_PLAN.md](plans/MAIN_PLAN.md).

### Engines in the app

The [engine table in README](README.md#engines) is current: `Homr480` is the default
(`AppSettings.cs`) and `Homr465` the secondary; they are the only engines the home screen
offers. `Homr` (426) and `Zeus` stay in the backend for their cached songs and the research
tools, and a stored choice of either converts with 480 (`OmrEngines.ToOffered`). `MusicXml`
and `DirectMidi` are imports. The pinned 465 and 480 runtimes are documented in
[Bridge/HOMR465.md](Bridge/HOMR465.md). The rest of this section describes the 426 path, which
backs most of the research history.

**HOMR 426 is installed from git, not PyPI, plus one local patch.** `setup_gpu.ps1` pins commit
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

### Lessons kept from superseded work

- **Rendering DPI dominated SMT results**, 7x from resolution alone, so sweep DPI before
  judging any model. homr is DPI-insensitive: it rescales each detected staff to a canonical
  height, so the hardcoded 300 in `render_pdf.py` is fine.
- **Fine-tuning traps**, should training return: upstream's `fine_tune=True` unfreezes only
  the lift (accidentals) branch, a leftover from PR #52, and a frozen encoder cannot fix a
  perception failure (the vendored patch changes this). Training auto-downloads and converts
  all five corpora unless `dataset_index` is trimmed. The documented VRAM floor is 8 GB, and
  `SHEET2PLAY_VRAM_FRACTION` caps use at 90%. Watch seconds per iteration in the first 15
  minutes and stop above about 10 s/it (liebharc/homr#61 hit 70 s/it under WSL). Rare-token
  collapse is the likeliest failure.
- **PR #156** (`upper2`/`lower2` positions, the likeliest way to raise the representation
  ceiling) has no published checkpoint; a clone sits at `Research/omr/vendor/homr-pr156/`.
- The displacement measurements behind the current plan, and the training-headroom estimate
  (+0.096 on matched samples, against +0.251 from fixing displacement), are in
  [FINDINGS](Research/omr/reports/diagnosis/FINDINGS.md).

## 6. Conventions

- Follow [AGENTS.md](AGENTS.md) for shared conventions, verification, and search scope.
- Preserve existing user changes and recovery refs during refactors. Inspect Git state first;
  never use restore/reset/clean to discard unrelated work. A historical incident lost work
  through an automated restore; that is not a reason to commit unrelated changes automatically.
- Each OMR engine gets its own virtual environment; do not merge their dependencies.
- Code goes in `Research/omr/vendor/` when vendored from upstream; it is gitignored.
- Model weights, datasets and `.runtime/` directories are gitignored — a 114 MB
  safetensors file and a 29 MB checkpoint were nearly committed once.
