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
* Millisecond playback scheduling with a configurable audio offset.
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

```bash
dotnet run --project Visualization_engine
```

Then drop a file onto the window, press `B` to browse, or pick something from one of the
three library columns.

Supported inputs: `.pdf`, `.png`, `.jpg`, `.jpeg`, `.bmp`, `.tif`, `.tiff`, `.webp`,
`.mid`, `.midi`, `.mxl`, `.musicxml`, `.xml`.

## Controls

| Key | Action |
| --- | --- |
| `Space` | Play / pause |
| `←` / `→` | Seek 5 seconds |
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

## Project layout

```
Visualization_engine/      C# frontend (assembly: SynthesiaClone)
Visualization_engine.Tests/  xUnit tests for cache, playback and progress
Bridge/                    Python OMR pipeline and its tests
Omr/                       Dataset and training experiments
songs/                     Local sheet music, MIDI and caches (not tracked)
```
