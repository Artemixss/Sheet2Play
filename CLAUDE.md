# Sheet2Play

Machine-wide rules live in `~/.claude/CLAUDE.md` and apply here too. This file covers only
what is specific to this repository.

## What the user runs

`dist\Sheet2Play.exe`, launched from the Desktop and Start Menu shortcuts that
`scripts/install-shortcut.ps1` creates. Never `dotnet run`. A change is not finished when
it builds and the tests pass — until the app is republished the user is still launching the
previous binary and will report the new feature as missing.

Publish and verify with `/release`, which runs:

```
powershell -ExecutionPolicy Bypass -File scripts\verify-release.ps1
```

The running app holds a lock on `dist\Sheet2Play.exe`, so it must be closed before
publishing. Closing it is safe — the song library and settings live in
`%LOCALAPPDATA%\Sheet2Play`, not in memory. Offer to relaunch it afterwards.

## Layout

- `Visualization_engine/` — the C# frontend (`SynthesiaClone.csproj`, assembly
  `Sheet2Play`). Raylib + DryWetMidi, net9.0-windows.
- `Visualization_engine.Tests/` — xunit suite. `dotnet test`.
- `Bridge/` — the Python OMR bridge. `bridge.py` is the entry point the frontend shells
  out to; it imports `musicxml_normalizer` and `progress_protocol` as siblings.
- `Omr/`, `Research/` — OMR experiments and notes.
- `pianos/` — large sample payloads. Not shipped with the app; exclude from recursive
  greps, they make repo-wide searches time out.

The frontend source is recovered decompiler output, so it carries no original comments.
Write new comments in the style of the surrounding hand-written files, not the decompiled
ones.

## Runtime assets

These load from disk relative to `AppContext.BaseDirectory` and are invisible to the
compiler, so a build can succeed while the published app degrades or fails:

- `assets/fonts/Inter-Regular.ttf` and `Inter-SemiBold.ttf` — `UiDesign.cs`. Missing
  fonts silently fall back to Raylib's default; the app still runs and looks wrong.
- `Bridge/bridge.py` plus its sibling imports — `OmrPipeline.cs`.

`ExcludeFromSingleFile` in the csproj is what keeps them on disk rather than embedded in
the single-file bundle. Do not remove it.

## OMR engine

- Experimental OMR changes stay opt-in and leave the shipped engine's behaviour untouched
  until they are measured.
- Exhaust in-place fixes to the current engine before proposing a replacement.
- Transcoda was removed permanently and must never be restored, even to fix a broken
  import.

## Audio

The `audioOffsetSeconds` default in `Playback.cs` is the user's own by-ear calibration.
Do not replace it with a guessed or "more correct" value.

## ML / Model Selection

Applies to the OMR fine-tuning and dataset work under `Omr/` and `Research/`.

- Never select a model by maximizing a single class-recall metric. Always report the full
  confusion matrix and check for degenerate predictors (all-one-class) before accepting a
  checkpoint.
- Report the trivial always-predict-majority baseline alongside any candidate, and reject
  candidates that do not clearly beat it on balanced accuracy or macro-F1.
- Default to local WSL2 training on the 6 GB GPU; cloud rental is acceptable under roughly
  $10.
- Keep the project's own dataset generator in any training plan, even when a public corpus
  covers the same ground.

## Conventions

- User-adjustable settings need a visible on-screen control, not just a keyboard shortcut.
- Do not add a `Co-Authored-By: Claude` trailer to commits in this repository.
