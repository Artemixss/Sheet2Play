# Phase 2 report: C# song model and cache v3

**Plan:** [`2026-10-19-musicxml-songs`](../../../../../plans/2026-10-19-musicxml-songs.md), Phase 2, requested
2026-10-19 ("ok commit phase 1 and continue with phase", read as the next phase). **Result:
accepted; every acceptance criterion met.**
Evidence files that list private library paths (`library-*/library.json`, `convert-*/`,
`timing-toggle/`, `*.log`) stay local.

## What changed

- **`OmrPipeline`**: with a song output directory, HOMR (426/465/480) and MusicXML conversions run
  `song_entry.py` instead of `bridge.py`/`timing_correction.py`, with the same interpreter and
  pinned-runtime checks. `SupportsSongPackage` names those engines; Zeus keeps the MIDI cache.
- **`SongPerformance.cs`** (new): a strict reader for `performance.json` (an unknown field is an
  error), `SongTimeline` (walks the play order, places notes by measure and offset, builds the tempo
  map from the score's own marks, otherwise 120; grace notes left out until Phase 3 gives them a
  playing rule), and `SongInterpreter` (the interpretation key, computed exactly as Python computes
  it, and the runner that re-interprets stored MusicXML).
- **`SongCache.Packages.cs`** (new, a partial of `SongCache`): packages in
  `songs/scores/<engine>/<source-sha>[-<profile-sha>]/` with `song.json` (this app's manifest),
  the entry's `recognition.json` and pages, and `derived/<key>/` with `interpretation.json`.
  Conversion, reopening, re-interpretation into a staging folder moved into place, removal of stale
  interpretations, listing and recents. Any invalid page, manifest or interpretation is never used;
  a run that leaves no valid package, or whose package cannot be interpreted, falls back to the
  MIDI cache. Listing never runs the interpreter.
- **`SongCache.cs`**: made partial; package engines route to the new core; the code after the
  pipeline is extracted (`CompleteLegacyConversion`) so the fallback reuses it; listing, recents and
  the reuse prompt see packages; a MIDI cache whose source has a package is no longer listed.
- **`Program.Verification.cs`**: `--verify-omr` accepts HOMR 480 and packages, with an optional
  `--timing-fix`; new `--verify-library EVIDENCE_DIR` opens every MIDI cache, custom MIDI file and
  package and builds its playback session.
- **Tests**: 15 new in `SongPackageTests` (117 in all, all passing). Two use the real HOMR Python:
  the C# interpretation key equals Python's, and an imported MusicXML file with a repeat converts
  through the real `song_entry.py` and bridge and plays the repeat.

## Acceptance

| Criterion | Result |
| --- | --- |
| Three fresh 480 library conversions match their v2 JSON within 1 ms (scores without repeats) | **Pass.** Sources `7f5e9140`, `608cb0d6`, `bdbc57ee` (2 pages each), converted by the published exe with `--verify-omr … Homr480`: 560, 419 and 617 notes, every key the same, largest onset or end difference 0.0000 ms (the `[SONG CACHE] crosscheck` line). About 45 s each, all of it OMR. |
| Toggling TIMING FIX rebuilds in under 15 s with no OMR process | **Pass.** `--verify-omr 7f5e9140… Homr480 … --timing-fix` on the converted song: `decision=reinterpret omr=false seconds=1.37`, 3.8 s for the whole command; `omr-jobs` held 283 receipt folders before and after, and no page inference ran. |
| Every legacy MIDI cache and custom MIDI file loads and plays | **Pass, criterion corrected.** `--verify-library` before and after the conversions: all 85 songs that played before still play, with identical note counts and durations (56 HOMR 426 caches, 3 Zeus, 26 custom MIDI), and the 4 new packages play. The plan's "all 118" was wrong: 61 caches failed before Phase 2 and still do, none because of it (below). |
| Unit tests cover identity mismatch, corrupt files and the atomic write | **Pass.** A changed page invalidates the package; a corrupt performance is re-interpreted; an interpreter failure leaves no staging folder and falls back; a new interpreter is listed from the old interpretation without running and replaces it when opened. |
| Release gate passes and one PDF converts end to end in the published exe | **Pass.** The third gate run passed all 8 steps. The first two failed only "Published app launches": the window opened and responded but presented no frame, and a Release build of the pre-Phase-2 commit (`af0332b`) did the same, so the screen, not the change, was the cause. The user confirmed the published app opens. |

## Findings outside Phase 2

- **The 58 HOMR 465 caches stopped loading on 2026-10-19.** Commit `237e398` (480 as the default)
  changed `bridge.py`, which re-pinned 465 from profile `1fd5b26e…` to `c06852f3…`; every 465 cache
  names the old profile. Opening one of those songs with 465 re-runs OMR. No library song has a 480
  conversion except the three above, so most of the library converts on first open; Phase 6 is the
  bulk path.
- **2 HOMR 426 manifests have no MIDI file, and 1 HOMR 426 cache has an old engine revision.**
- **58 hash-named PDF copies** (`<source-sha>-<profile-sha>.pdf`) sit in `songs/pdf` beside the 57
  real files, left by the 465 migration's retained-source rule, so the PDF list shows them. Song
  packages do not add more: an outside source is kept under its own name. Left for the C# rework.
- **`--reconvert inventory/resume`** (the 465 migration tool) checks for MIDI caches, so it would
  reject the packages a 465 conversion now produces. It is not needed until Phase 6, which moves it
  to packages.
- **`CONTEXT.md` §3.5 "Cache identity"** still describes MIDI caches only. It has uncommitted edits
  from another chat, so it is left for whoever lands those.

## Next action

Phase 3 (expressive playback), requested the same day.
