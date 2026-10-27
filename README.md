# Sheet2Play

Turns sheet music into falling-note piano playback.

Give it a PDF, a scan or a photo of piano sheet music. Sheet2Play reads it with optical music
recognition and plays it as falling notes over an 88-key keyboard, through a sampled grand piano.

![Sheet2Play playing the third movement of the Moonlight Sonata](docs/media/demo.gif)

## Features

* **Reads sheet music** with [HOMR](https://github.com/liebharc/homr). MIDI and MusicXML files
  play directly, without recognition.
* **Keeps the score.** Bar lines and a pedal lane fall with the notes, and the **EXPRESSION**
  panel turns pedal, dynamics, articulations, repeats and auto pedal on or off.
* **TEMPO** plays the tempo marks printed in the PDF, both numbers like ♩ = 110 and words like
  Andante or a tempo. Set your own start tempo, or tempo changes by bar, when a mark is wrong or
  missing.
* **TIMING FIX** (on by default) stops one misread measure from shifting the rest of the song.
  Turn it off for a song whose meter really changes.
* **Playback** from 0.05x to 2x, with scrubbing and an audio offset to line the sound up with
  the notes.
* **EXPORT** to WAV, MP3, MIDI or MusicXML.
* **Library.** Converted songs are cached, so opening the same file again is instant.

## Requirements

* Windows and the [.NET 9 SDK](https://dotnet.microsoft.com/download)
* For reading sheet music: an NVIDIA GPU with CUDA, Python 3.11 x64 and the
  [HOMR setup](Bridge/HOMR465.md). MIDI and MusicXML files play without it.
* A piano: run `scripts\install-piano.ps1` (Salamander, the default) or
  `scripts\install-soundfont.ps1` (YDP), then pick it under **PIANO** on the home screen.

## Running

```bash
dotnet run --project Visualization_engine
```

To install it as an app with Desktop and Start Menu shortcuts:

```powershell
.\scripts\publish.ps1
.\scripts\install-shortcut.ps1
```

Drop a file onto the window, press `B` to browse, or pick a song from the library. Supported
files: `.pdf`, `.png`, `.jpg`, `.jpeg`, `.bmp`, `.tif`, `.tiff`, `.webp`, `.mid`, `.midi`,
`.mxl`, `.musicxml`, `.xml`.

Your songs, settings and pianos live in `%LOCALAPPDATA%\Sheet2Play`. Set `SHEET2PLAY_HOME` to
use another folder.

## Controls

| Key | Action |
| --- | --- |
| `Space` | Play / pause |
| `←` / `→` | Seek 5 seconds |
| `[` / `]` | Audio offset by 5 ms |
| `B` | Browse for a file |
| `F11` | Toggle fullscreen |
| `Esc` | Cancel a conversion, or close a dialog |

## Licence

[MIT](LICENSE)
