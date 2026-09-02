# Sheet2Play

> Turns sheet music into synchronized, falling-note piano playback.

Sheet2Play reads sheet music — a PDF, a scan, or a photo — runs it through an Optical Music
Recognition (OMR) pipeline, and renders the result as a Synthesia-style piano roll you can
play back, scrub, and slow down.

## Architecture

The project is two components talking over a process boundary.

### 1. Visualization engine (C# / .NET 9 / Raylib)

The desktop frontend, in `Visualization_engine/`. It owns the UI, the note rendering, and
MIDI playback timing.

* Falling-note piano roll with an 88-key keyboard, scaled to any window size.
* A three-column landing page: **PDF Library**, **Cache Playlist**, and **MIDI Player**.
  Each column has its own search box; terms are matched independently, so
  `rail sparkle` finds `Honkai_Star_Rail_-_Sparkle`.
* Millisecond playback scheduling with an on-screen audio-offset control above the
  keyboard, calibrated during playback and persisted between sessions.
* Variable playback rate from 0.05x to 2.00x.

### 2. OMR bridge (Python)

`Bridge/bridge.py` runs the recognition pipeline and manages its own virtual environments,
so each engine's dependencies stay isolated. It emits structured progress back to the C#
frontend, which renders it as a live progress screen.

`Bridge/musicxml_normalizer.py` converts engine output into a normalized note list. It
tolerates recognition errors: notes with zero duration, impossible pitches, or microtonal
pitches are skipped with a warning rather than aborting the whole score.

## Engines

Selected on the landing page, or with the `H` / `O` shortcuts.

| Engine | Input | Notes |
| --- | --- | --- |
| `Homr` | PDF, images | Default. Faster, general-purpose sheet music. |
| `Zeus` | PDF, images | GPU/CUDA path. Pages are sliced into systems by `Bridge/detect_systems.py` before recognition. |
| `MusicXml` | `.mxl`, `.musicxml`, `.xml` | Bypasses recognition entirely — normalizes the score directly. |
| `DirectMidi` | `.mid`, `.midi` | Bypasses the bridge entirely and parses in C# via DryWetMidi. |

`.mid` and `.mxl` files are exact by definition, so they never run OMR. Dropping one copies
it into `songs/midi/custom/` and it appears in the MIDI Player column.

## Caching

Every successful conversion is cached as a validated MIDI file plus a JSON manifest, keyed
by the **SHA-256 of the source file and the engine**. Re-opening the same PDF with the same
engine loads instantly instead of re-running recognition.

Because that makes it easy to *think* you re-ran an engine when you didn't, loading a source
that already has a cache asks first, and offers **Use cached** / **Re-run** / **Cancel**.
Re-running discards the old cache and forces a genuine pipeline run — the way to verify an
engine still works.

Cached songs appear in the Cache Playlist, filterable by engine and sorted by name.

## Requirements

* [.NET 9 SDK](https://dotnet.microsoft.com/download)
* Python 3.11+ (the bridge builds its own venvs on first run)
* A CUDA GPU — optional, and only for the `Zeus` engine

## Running

From source:

```bash
dotnet run --project Visualization_engine
```

Then drop a file onto the window, press `B` to browse, or pick something from one of the
three library columns.

## Installing as an app

To get a double-clickable `Sheet2Play.exe` that needs no .NET install:

```powershell
.\scripts\publish.ps1
.\scripts\install-shortcut.ps1
```

`publish.ps1` produces a self-contained single-file build in `dist\` and verifies that the
Inter fonts and the Python bridge landed beside it. `install-shortcut.ps1` adds Desktop and
Start Menu shortcuts.

## Where your library lives

Everything the app stores lives in **`%LOCALAPPDATA%\Sheet2Play`** — on Windows that is
`C:\Users\<you>\AppData\Local\Sheet2Play`. Note **Local**, not Roaming. Running from
source and running the published app share this one folder, so a score converted either
way is available to both, and the checkout stays free of user content.

```
%LOCALAPPDATA%\Sheet2Play\
    settings.json        selected engine and playback settings
    recent.json          recently opened songs
    failed-omr.json      remembered OMR failures
    songs\pdf\           sheet music you want to convert
    songs\midi\custom\   .mid / .mxl files, shown in the MIDI Player column
    songs\midi\<engine>\ validated MIDI caches, one folder per engine
```

Paste this into Explorer's address bar to open it:

```
%LOCALAPPDATA%\Sheet2Play\songs\midi\custom
```

Set `SHEET2PLAY_HOME` to use a different folder, or bake it into a shortcut:

```powershell
.\scripts\install-shortcut.ps1 -LibraryHome "D:\Sheet2Play"
```

Supported inputs: `.pdf`, `.png`, `.jpg`, `.jpeg`, `.bmp`, `.tif`, `.tiff`, `.webp`,
`.mid`, `.midi`, `.mxl`, `.musicxml`, `.xml`.

## Controls

| Key | Action |
| --- | --- |
| `Space` | Play / pause |
| `←` / `→` | Seek 5 seconds |
| `[` / `]` | Audio offset by 5 ms, to sync sound with the falling notes |
| `B` | Browse for a file |
| `H` / `O` | Select the Homr / Zeus engine |
| `F11` | Toggle fullscreen |
| `Esc` | Cancel a conversion, or back out of a dialog |

The progress slider can be dragged to scrub, and the playback rate field accepts a typed
value (`Enter` to commit, `Esc` to discard).

## Tests

```bash
dotnet test Visualization_engine.Tests
```

Python-side tests live in `Bridge/tests/` and run under `pytest`.

`MidiTester` is a smoke harness that loads every file in `songs/midi/custom` and builds a
playback session for each, catching MIDI regressions without opening the app:

```bash
dotnet run --project MidiTester
```

### Checking the UI without launching it

The app can render every screen headlessly and write one PNG per state. It uses a hidden
window and a null MIDI output, so it needs neither a display nor a synthesiser, and exits
non-zero if a screen throws:

```bash
dotnet run --project Visualization_engine -- --smoke .\ui-snapshots
```

This is also the quickest way to verify a *published* build, since it catches problems that
only appear after packaging:

```powershell
.\dist\Sheet2Play.exe --smoke .\ui-snapshots
```

## Improving recognition

HOMR is accurate enough for general sheet music but loses rhythmic precision on dense piano
arrangements, which is the material this project actually receives. `Research/omr/` holds the
work aimed at fixing that. It is research tooling, not part of the shipped app.

### Evaluating another engine

The Sheet Music Transformer publishes checkpoints trained on pianoform scores, so the first
question is whether one of them simply beats HOMR — no training required.

```bash
cd Research/omr
.venv/Scripts/python.exe compare_engines.py --pdf <score.pdf> --pages 1 --dpi 200
```

This slices each page into systems, transcribes each one, and reports spine count, note
count, barlines and whether the output is well-formed Humdrum.

**Current finding: it does not beat HOMR.** Output is well-formed and the meter is sometimes
correct, but it recovers around 16 notes from a system holding well over fifty. Note that
rendering resolution dominates the result — at 300 DPI the same page collapses to 4 notes,
at 200 DPI it gives 28 — so sweep `--dpi` before drawing conclusions about any model.

### Datasets

| Dataset | Size | Licence | Role |
| --- | --- | --- | --- |
| OLiMPiC (scanned) | 2,931 aligned samples | CC BY-SA 4.0 | Real scans; robustness |
| OpenScore Lieder | 1,352 scores | CC0 | Volume |
| Your own library | 36 PDFs | third-party | The evaluation target |

```bash
python download_openscore.py --corpus lieder --update-lock   # hash-verified fetch
python download_openscore.py --corpus lieder --convert --pdf # pair with MusicXML
python build_dataset.py --input <scores> --annotate          # engrave training pages
```

`build_dataset.py --annotate` adds title blocks, note-name letters, fingerings and chord
symbols to the rendered *image* while the training label stays the clean score, so a model
has to learn to ignore them. OLiMPiC and OpenScore are the same repertoire in two forms, and
both are voice-and-piano — useful for volume, not a substitute for evaluating on real piano
arrangements.

## Project layout

```
Visualization_engine/        C# frontend (assembly: Sheet2Play)
Visualization_engine.Tests/  xUnit tests for cache, playback and progress
MidiTester/                  MIDI regression smoke harness
Bridge/                      Python OMR pipeline and its tests
Omr/, Research/              Dataset work and OMR experiments
scripts/                     publish and shortcut installers
```

Your sheet music is not in here — see [Where your library lives](#where-your-library-lives).

## Further reading

* [`CONTEXT.md`](CONTEXT.md) — architecture, invariants and known traps. Read this before
  making changes, especially automated ones.
* [`OMR_Next_Phase_Context.md`](OMR_Next_Phase_Context.md) — the roadmap for replacing the
  recognition engine.
