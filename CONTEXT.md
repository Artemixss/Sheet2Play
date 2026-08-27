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
dotnet test Visualization_engine.Tests                      # expect 50/50
dotnet run --project MidiTester                             # expect 18/18 + library report
dotnet run --project Visualization_engine -- --smoke ./out   # 7 PNGs, exit 0
```

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
| `Homr` | Default. Works acceptably; loses rhythmic precision on dense piano. |
| `Zeus` | GPU path. **Labelled "Oemer GPU" in some UI strings** — same engine, historical naming. |
| `MusicXml` | Bypasses recognition; normalises a symbolic score directly. |
| `DirectMidi` | Bypasses the bridge entirely; parsed in C# by DryWetMidi. |

`bridge.py` emits only these error codes: `INPUT_INVALID`, `MODEL_INVALID`,
`NORMALIZATION_FAILED`, `RUNTIME_MISSING`. The C# error screen previously switched on
`OEMER_*` codes that were never produced, making its recovery hint unreachable.

### Datasets on hand

| Dataset | Size | Licence | Use |
| --- | --- | --- | --- |
| OLiMPiC scanned | 2,931 aligned samples | CC BY-SA 4.0 | Real scans, robustness eval |
| OpenScore Lieder | 1,352 scores | CC0 | Volume; `download_openscore.py` |
| Local library | 36 PDFs | third-party | **The real evaluation target** |

OLiMPiC is derived from OpenScore Lieder — the same repertoire in two forms, not two
corpora. Both are voice-and-piano, so neither matches the dense piano arrangements this
project targets.

`build_dataset.py` engraves scores locally into aligned image/MusicXML pairs, with
`--annotate` adding title blocks, note-name letters, fingerings and chord symbols to the
*image* while the label stays clean, so the model must learn to ignore them.

### Sheet Music Transformer evaluation

`antoniorv6/smt-grandstaff` was wired up to test whether a published pianoform model beats
HOMR. **It does not**, on current evidence: output is well-formed Humdrum with occasionally
correct meter, but recovers roughly 16 notes from a system containing well over fifty.

Three traps, each of which fails silently:

1. **Use the 2024 upstream code (`d25acd43`), not master.** The decoder was reimplemented in
   Feb 2025. Against master 210 of 360 tensors do not match, transformers leaves the whole
   decoder randomly initialised, and the model still loads and emits fluent nonsense.
   `SMTTranscriber` now verifies tensor coverage and raises.
2. `SMTConfig` never calls `PretrainedConfig.__init__`; `smt_compat.py` patches it.
3. Feed one **system**, sized as upstream `data.py` does — width kept and clamped, height
   resized to `maxh` without preserving aspect. A full page overflows the positional
   encoding.

**Rendering DPI dominates results.** At 300 DPI systems are squashed and output collapses to
26–59 spines with 4 notes per page; at 200 DPI, where systems are natively ~`maxh` tall, the
same page gives 3–4 spines and 28 notes. A 7× difference from resolution alone.

### HOMR can be fine-tuned — prefer this over a new engine

HOMR is not a black box. Upstream (`liebharc/homr`) documents training in `Training.md`:

- `training/train.py transformer`, with dataset converters for PrIMuS, GrandStaff and
  Lieder — the same corpora researched here.
- Prediction is **multi-head**: separate tokenizers and vocabularies for `rhythm`, `pitch`,
  `lift`, `articulation`, `slur` and `position`. Rhythm is its own head, so the weakness
  this project cares about can be targeted directly.
- A metric already exists: `symbol_error_rate_torch.py`, plus published baselines. Run 426
  (July 2026) reports **SER 4.0%** at system level and OMR-NED 14.5–18.1%, trained on
  lieder + grandstaff + primus + pdmx + musetrainer.

Constraints: training requires **Linux** (WSL2 or the provided `Dockerfile.gpu`), the
documented VRAM floor is **8 GB against this machine's 6 GB** (reduce batch size and raise
gradient accumulation, or rent a GPU — upstream suggests vast.ai and an RTX 3090), the
dataset is ~12 GB, and a full run takes 2–4 days on suitable hardware.

**Measure before training.** HOMR at 4% SER is already trained on GrandStaff and Lieder, so
poor rhythm here may not be model capacity at all. The likelier culprits are `start_beat`
computation in `musicxml_normalizer.py` or staff segmentation quality. Evidence from the SMT
work supports this: results moved 7× on rendering DPI alone, and one bad crop produced a
degenerate transcription. Feed HOMR a cleanly segmented system with known ground truth —
`build_dataset.py` can generate exactly that — and check whether rhythm is still wrong before
spending days on a training run.

---

## 6. Conventions

- **Do not add a `Co-Authored-By: Claude` trailer** to commits in this repo.
- Commit before large automated refactors. This project has already lost work to an
  automated `git restore`.
- Each OMR engine gets its own virtual environment; do not merge their dependencies.
- Code goes in `Research/omr/vendor/` when vendored from upstream; it is gitignored.
- Model weights, datasets and `.runtime/` directories are gitignored — a 114 MB
  safetensors file and a 29 MB checkpoint were nearly committed once.
