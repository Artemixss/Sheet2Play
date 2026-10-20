# Phase 4a report: SFZ piano decision spike

**Plan:** [`2026-10-19-musicxml-songs`](../../../../../plans/2026-10-19-musicxml-songs.md), Phase 4a, requested
2026-10-19 ("after that commit phase 3 then continue with the next phase"). No shipped change.
**Result: the managed SFZ player meets every criterion that can be measured without the user's
ears; sfizz is not measured, because using it needs a download the user has not approved.** The
pick between YDP and Salamander is the user's (4b waits on it). Not committed.
The listening files (`listen/`), the bank and the raw measurements (`measure/`) stay local: they are
renders of the user's own songs and 1.3 GB of third-party samples.

## What was built

`Research/sfz-spike/` (a console project outside the app; it references the app for song loading,
sessions, the SoundFont engine and the WAV sink, so both pianos play the same events):

- **`SfzInstrument`** reads `<control>`, `<global>`, `<group>`, `<region>` and 21 opcodes, and counts
  every opcode it meets, so coverage is measured.
- **`SfzBank`** converts the 641 Salamander samples (48 kHz, 24-bit stereo, 1.9 GB) once into a
  single 16-bit file (1,247 MB) and maps it into memory. A mapped file is backed by itself, not by
  the page file, so it does not add to the commit charge that crashes this machine. The first half
  second of every sample is touched at load. Each sample's lead-in (median 9 ms, up to 28 ms of
  near-silence before the hammer) is skipped, keeping 1 ms before the attack.
- **`SfzSynth`** places events on their own sample like `SoundFontEngine`, resamples with a cubic
  (Hermite) interpolator, applies `amp_veltrack` as sfizz does, releases exponentially over
  `ampeg_release`, holds voices under the sustain pedal, plays the 157 release-triggered hammer and
  string-resonance regions with `rt_decay` (deferred while the pedal holds the damper up), plays the
  pedal-down and pedal-up noises on CC64 with `group`/`off_by`, and steals the quietest of 256 voices.
- **`Freeverb`** (public domain), because the app's YDP sound has MeltySynth's reverb and a dry
  Salamander would lose a by-ear comparison for the wrong reason.

## Measurements

Published app's YDP SoundFont through the app's own `SoundFontEngine`, against Salamander through
the spike, on the same sessions with every expression switch on. Block budget 21.33 ms (1,024
frames at 48 kHz); a block slower than its own length is one the app's two-buffer stream could not
have had ready.

| Measure | YDP (today) | Salamander (managed) | Criterion |
| --- | --- | --- | --- |
| Commit (private bytes) added at load | 112.6 MB | **8.5 MB** | ≤ 300 MB: pass |
| Working set added at load | 113.2 MB | 70.3 MB | recorded |
| Load time | 0.05 s | **0.13 s** warm | < 5 s warm: pass |
| Densest song (45,497 notes in 139 s), 10 min at 1.0× | 1 late block (max 49 ms), CPU 6.7% | **0 late blocks** (max 16.2 ms, p99 5.8 ms), CPU 12.2% | no underruns: pass |
| Same at 2.0× | 1 late block (max 27 ms), CPU 8.5% | **0 late blocks** (max 10.7 ms), CPU 15.8% | no underruns: pass |
| 256 voices held under the pedal | max 13.9 ms, CPU 13.8% | max 6.0 ms, CPU 15.4% | recorded |
| Deterministic offline render | (unchanged engine) | **yes**, two renders identical | pass |
| Opcode coverage on Salamander | n/a | **100%** of 3,476 uses of 18 opcodes, no unknown header | recorded |

- The densest song keeps 256 voices sounding throughout, so voices are stolen constantly (615,200
  steals in ten minutes); both pianos cap at 256.
- Private bytes after the ten-minute runs (350 MB) are the spike's own test sessions (the song
  repeated to ten and twenty minutes, about 640,000 notes), not the bank.
- Not measured: a cold disk cache (the bank had just been written, so it was cached; Windows gives
  no way to empty the cache without administrator rights), and real-time playback with the app's
  drawing on the same thread. The worst Salamander block used three quarters of its budget on the
  densest song, so 4b should render on its own audio thread rather than in the frame loop.

## Checks a listener would otherwise have to make

- **Pitch:** every key of one sample comes out the same distance from equal temperament (for example
  44/45/46 at −5.4/−5.5/−5.5 cents), so resampling is exact. The slope from −25 cents in the bass
  to +39 in the treble is the recording's own stretch tuning; YDP shows the same slope.
- **Velocity:** loudness rises with velocity on both (Salamander −50.5 to −21.5 dBFS from 10 to 127;
  YDP −71.6 to −28.5).
- **Timing:** after the lead-in trim, Salamander reaches half its peak 11 ms after the note (median),
  YDP 2.5 to 6 ms; the remainder is the recorded rise of the string, below the 20 to 40 ms at which
  sound and picture visibly part, and the existing audio offset control covers it. On the three
  listening songs both pianos' onsets agree at 20 ms resolution, their loudness envelopes correlate
  0.94 to 0.98, and neither render clicks or clips.

## For the user to judge: `listen/`

Three songs, each as **1 YDP (app today)**, **2 Salamander** (with reverb) and **3 Salamander dry**,
loudness-matched to the YDP render, because the louder of two renders tends to sound better:
"Beyond This Station" (396 pedal changes), "Moonlight" (60 pedal changes) and the Dexter HOMR 480
conversion (no pedal: HOMR reads none).

## Findings outside Phase 4a

- `--render-audio` records the song in the user's recent list, and the recent list does not follow
  `SHEET2PLAY_HOME`, so Phase 3's render of the fixture from a throwaway library added a dead entry
  to the real list. It was removed (backup kept outside the repository). Left for the C# rework.
- sfizz 1.2.3 (January 2024) ships for Windows as `sfizz-1.2.3-win64.zip`, 8.3 MB, from the
  sfztools GitHub releases; whether it holds the library or only plugins is unknown until it is
  downloaded.

## Next action

The user picks the piano from `listen/`, and says whether sfizz should be compared (which needs the
download above). Phase 4b then puts the pick into the app: installer with a pinned hash, PIANO
selector, attribution, its own audio thread, and the release gate.
