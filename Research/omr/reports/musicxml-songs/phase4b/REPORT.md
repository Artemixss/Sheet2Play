# Phase 4b report: Salamander as a built-in piano

**Plan:** [`2026-10-19-musicxml-songs`](../../../../../plans/2026-10-19-musicxml-songs.md), Phase 4b, requested
2026-10-20 ("my choice would be those with the 2's ... you can continue phase 4"), after the user
asked the day before to keep both pianos for testing ("depending on performance i might delete some in
future but for testing keep implementing both").
**Result: shipped, measured and approved.** Every measurable criterion passes in the published app.
The user approved the sound and the commit on 2026-10-20 ("i checked the audio is realy nice i mean
salamander ... i approve the commits"). The by-ear sync check was not reported separately.

## What shipped

- **The managed SFZ player, moved from the spike into the app:** `SfzInstrument.cs`, `SfzBank.cs`
  and `Freeverb.cs` unchanged apart from the namespace (the bank now writes its index last and
  atomically), and `SfzEngine.cs`, the spike's synth with the app's transport: seek (fast-fades what
  is sounding, then re-triggers held notes like the SoundFont engine), pause (releases, keeps tails
  and reverb decaying, song time stands still), resume (restores the score's pedal), staged rate
  changes, and the same underrun count. Transport moves are silent; only the score's own events play
  pedal and release noises. The gain (0.37) matches the YDP loudness the user's picked renders were
  scaled to; the reverb is the one in those renders.
- **`IPianoEngine`** (`PianoEngine.cs`), implemented by both engines, so the timebase, Export MP3,
  `--render-audio` and the audio thread treat them alike.
- **Audio on its own thread** (`AudioOutput.cs`): a highest-priority thread fills the Raylib stream
  whenever a sub-buffer frees, polling every millisecond (`timeBeginPeriod(1)`); the frame loop only
  re-anchors song time. `LockedPianoEngine` takes one lock around every engine call and publishes song
  time and the running flag for lock-free reads, so drawing never waits out a block render. This
  applies to YDP too.
- **`AudioBackend.SfzPiano`**, the default for new settings. If Salamander is not installed, the app
  falls back to YDP and says why; without either, to the MIDI device. Both built-in pianos share the
  built-in synth's audio offset, because they play through the same stream; the `Playback.cs`
  default is untouched. The user's own settings were not changed (they were on the MIDI device).
- **PIANO row** on the home screen (was AUDIO OUTPUT): Salamander, YDP and MIDI device cards, the
  attribution line ("Salamander Grand Piano V3 by Alexander Holm, CC BY 3.0 · YDP Grand Piano by
  FreePats, CC BY 3.0") for the installed sample sets, and an `SFZ` / `YDP` / `MIDI` badge on the
  playback screen. Refresh picks up a newly installed piano.
- **`scripts\install-piano.ps1`**: downloads the FreePats release (1.26 GB) or takes `-Source` (a
  folder or the `.tar.xz`), checks a pinned SHA-256 over every file of the release (644 files:
  `696d8ac6…9c72d`, so a local copy verifies exactly like a download), copies the `.sfz` and the
  README (licence), builds the bank with `Sheet2Play.exe --build-piano-bank`, and writes `piano.json`
  last, into `%LOCALAPPDATA%\Sheet2Play\pianos\salamander-v3` (or under `SHEET2PLAY_HOME`).
- `--render-audio --piano sfz|ydp` (default: the saved piano), and `--bench --audio sfz|ydp [--rate]`,
  which plays a song through the real, muted audio stream while drawing at 144 fps and reports
  underruns (with their song positions), load time and commit.
- **Underrun counter fix (both engines):** an engine's first fill of an empty stream takes both
  sub-buffers and was counted as an underrun, which put exactly one at 0.00 s on every bench run
  with either piano. It is no longer counted.

## Evidence

- **Installer:** from the local copy, hash verified and bank built in 9.1 s total; the installed
  `bank.s16` and `index.json` are byte-identical to the spike bank behind the renders the user picked.
- **Tests:** xunit 149 passed (139 before; 10 new in `SfzPianoTests`, on a synthetic instrument:
  parsing, bank lead-in trim and 24-bit conversion, a bank from an edited instrument refused, missing and
  incomplete installs, onset on the event's sample, determinism, pedal hold, release samples, seek and
  pause, settings default, and the first-fill rule).
- **Release gate:** 8 of 8, three times (the last after the final bench change).
- **In the published app** (`--bench --audio`), on the library's densest song (rushe, 45,497 notes,
  2:19), the whole song through the real Raylib stream, muted, rendered on the audio thread while the
  playback screen is drawn at 144 fps:

| Run | Load | Commit added | Underruns | Frames late (worst) |
| --- | --- | --- | --- | --- |
| Salamander, 1.0x | 0.10 s | 3.2 MB | **0** | 7.9% (117 ms) |
| Salamander, 2.0x | 0.11 s | 3.8 MB | **0** | 7.8% (115 ms) |
| YDP, 1.0x (before the counter fix) | 0.10 s | 114.4 MB | 1, at 0.00 s | 7.9% (117 ms) |
| No audio, same playback on the stopwatch (`--audio clock`) | | | | 7.8% (117 ms) |
| No audio, paused screen stepped frame by frame (the old bench) | | | | 0.0% (19 ms) |

  Before the counter fix both Salamander runs also showed exactly one underrun, and logging its
  position put it at 0.00 s: the first fill. The 4a criteria are met in the app: commit far under
  300 MB, no underruns at 1.0x and 2.0x, a warm load far under 5 s, and deterministic renders (seeded,
  tested).
- **Finding, not 4b's:** drawing this song while it plays misses 7.8% of 144 fps frames (worst
  117 ms) with or without audio, so the audio thread costs no frames, but the playback screen does
  not keep up on very dense songs. The old bench never saw it because it draws a paused controller,
  with no lit keys. This belongs to Phase 5's frame-time criterion or the C# engine rework.
- **Smoke:** every screen rendered, including the new `01-landing-piano-not-installed` (YDP playing,
  the reason shown) and the PIANO row with Salamander selected and both attributions.

## Not done, and for the user

- **The sync check by ear** with the existing audio offset control (Salamander uses the built-in
  synth's calibrated offset) was not reported separately. The sound itself is approved.
- The download path of the installer was not run (it needs a 1.26 GB download); the folder path was.
  The pin covers the extracted files, so a download that matches the release passes the same check.
- `README.md` should mention `scripts\install-piano.ps1`, but another chat has uncommitted edits to
  it, so it was left alone.
- Not measured: a cold disk cache (as in 4a).
