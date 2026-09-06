# Sheet2Play — Context for AI Agents

Orientation for an agent picking this project up cold. `README.md` covers how to use and
build it; this file covers how it is put together, what is fragile, and why several things
look the way they do.

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
Visualization_engine.Tests/  50 xUnit tests
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

Run all of these before claiming something works.

```bash
dotnet build Visualization_engine/SynthesiaClone.csproj     # expect 0 errors
dotnet test Visualization_engine.Tests                      # expect 0 failures
dotnet run --project MidiTester                             # all pass + library report
dotnet run --project Visualization_engine -- --smoke ./out   # 7 PNGs, exit 0
```

The Python suites matter too, and both must be green:

```bash
cd Bridge && ../Research/omr/.venv/Scripts/python.exe -m pytest tests -q
cd Research/omr && .venv/Scripts/python.exe -m pytest tests -q
```

Counts are deliberately not pinned here. This section has claimed 55 while the suite held 50
and then 69; a number that drifts is worse than no number, because it invites someone to
"fix" a passing suite to match a stale doc. Expect zero failures instead.

`--smoke` is the important one for UI work: it renders every screen with a hidden window and
a null MIDI output, so frontend changes can be checked without launching the app. It also
prints the resolved library and its contents, which catches a perfectly-rendered UI pointing
at the wrong folder.

**The build fails while the app is running** — it holds a lock on `bin`. To compile-check
without disturbing a running instance, redirect the output:

```bash
dotnet build Visualization_engine/SynthesiaClone.csproj -p:BaseOutputPath=<temp>/
```

Word COM automation (used to produce the internship report) hangs on PDF export on this
machine; LibreOffice is not installed. Neither is needed for the app.

---

## 5. OMR research state

### Engines in the app

| Engine | Notes |
| --- | --- |
| `Homr` | Default. Reads pitch well, places notes in time badly on polyrhythm - see below. |
| `Zeus` | GPU path. **Labelled "Oemer GPU" in some UI strings** - same engine, historical naming. |
| `MusicXml` | Bypasses recognition; normalises a symbolic score directly. |
| `DirectMidi` | Bypasses the bridge entirely; parsed in C# by DryWetMidi. |

**homr is installed from git, not PyPI.** `setup_gpu.ps1` pins commit `2d0c0a6`
(`0.7.0.post34`). The 0.7.0 release predates `aa5c8ce`, which fixes a crash where a rest
merged into a chord yields a zero-duration element and homr exits non-zero (upstream #136);
upstream releases infrequently and recommends installing from source meanwhile.

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

`antoniorv6/smt-grandstaff` was evaluated and does not beat homr. It has since been
superseded twice, by SMT++ and then LEGATO, so do not invest further there. LEGATO handles
multiple voices per staff and is the candidate if replacing homr ever comes back on the
table; it needs `meta-llama/Llama-3.2-11B-Vision` (gated, access granted) and ~20 GB VRAM.

One lesson from that work still applies generally: **rendering DPI dominated SMT results**,
7x from resolution alone. homr, by contrast, is DPI-insensitive - it rescales each detected
staff to a canonical height, so the hardcoded 300 in `render_pdf.py` is fine.

### Fine-tuning homr

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

## 6. Conventions

- **Do not add a `Co-Authored-By: Claude` trailer** to commits in this repo.
- Commit before large automated refactors. This project has already lost work to an
  automated `git restore`.
- Each OMR engine gets its own virtual environment; do not merge their dependencies.
- Code goes in `Research/omr/vendor/` when vendored from upstream; it is gitignored.
- Model weights, datasets and `.runtime/` directories are gitignored — a 114 MB
  safetensors file and a 29 MB checkpoint were nearly committed once.
