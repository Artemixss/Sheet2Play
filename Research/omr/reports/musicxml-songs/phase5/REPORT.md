# Phase 5 report: frontend

**Plan:** [`2026-10-19-musicxml-songs`](../../../../../plans/2026-10-19-musicxml-songs.md), Phase 5, requested
2026-10-20 ("i approve the commits ... then we can begin phase 5"). In the same message the user asked
for two removals: the MIDI device ("we can remove midi synth one let it be only 2 pianos") and HOMR
426 and Zeus from the home screen ("only 480 and 465 remains in the frontend"), leaving the backend to
judgement ("im not sure wheter they should stay at backand or not ... do what you think is best").
**Result: shipped and measured; waiting on the user's check in the published app.** Not committed.

## What shipped

- **Two pianos.** The PIANO row offers Salamander and YDP only. The MIDI device backend is gone from
  `AudioOutput` (no device is opened any more); a settings file that still names it opens Salamander
  (`AudioBackend.MidiDevice` stays in the enum only so old files read). With neither piano installed
  the app no longer falls back to the Windows MIDI synth: it plays silently (`AudioBackend.Silent`,
  stopwatch clock, notes still fall) and the home screen says to run `scripts\install-piano.ps1`.
  The MIDI device's own offset (`audio_offset_milliseconds`, the user's by-ear 80 ms) stays stored,
  untouched and unused; the `Playback.cs` default is unchanged. AUDIO OFFSET now always saves the
  pianos' offset.
- **Two engines.** The OMR ENGINE row offers HOMR 480 (default) and 465; the O and H shortcuts that
  picked Zeus and 426 are gone. A stored 426 or Zeus choice converts with 480 (`OmrEngines.ToOffered`,
  applied where the app and the bench read the choice; the settings store still reads and writes the
  raw value). The error screen's fallback is always an offered engine: 480 offers 465, everything else
  offers 480. `--reconvert` with no engine now uses 480 rather than 426.
- **Backend kept, on purpose.** 426 and Zeus stay in the bridge, `OmrPipeline` and the caches: the
  library holds 56 songs converted with 426 and 3 with Zeus that still play from the cache playlist
  under their own tabs, their cache identity depends on the engine, and the research tools use them.
  Removing the code would make those songs unplayable and gain nothing; Phase 6 re-converts the
  library with 480 and is the natural point to retire them.
- **Bar lines.** A faint line across the note field where each played bar starts, from the same
  timeline options the session plays (repeats on or off). The first build also numbered each line and
  showed "Bar 12 · 2nd time" at the top left; the user kept the lines and asked for the text to go
  (see the feedback round). `SongOverlay` (new) holds the bars and pedal spans per session and finds
  the visible ones by binary search; its `BarLabel` stays for the tempo plan, unused on screen.
- **Pedal lane.** A narrow lane down the left edge where pedal-down spans fall with the notes, a solid
  edge at each press, and the foot lit while the pedal is down. It shows the pedal that plays (score
  marks with the PEDAL switch on, or a MIDI file's CC64).
- **Staff colours.** In a part with two staves, staff 1 (right hand) is blue and staff 2 green; a part
  with one staff, and every MIDI or legacy song, keeps the split at middle C.
- **Badges.** The header's second line shows a MIDI (LEGACY) badge for conversions cached as MIDI
  before songs kept their score, a TIMING FIX badge when the fix shaped the song, then the note count
  and the score's counts ("255 articulations · 0 pedals · 0 dynamics · 0 repeats"). The engine badge
  was already there. The cache playlist marks legacy rows "· MIDI (legacy)".
- **Export MIDI, Export MusicXML, Re-convert**, right of Export MP3. Export MIDI writes the session
  being heard (expression, repeats and pedal included) at 120 bpm so seconds map exactly to ticks;
  overlapping notes of one pitch go on separate channels, as the MIDI cache does. Export MusicXML
  copies the package's combined `score.musicxml` and is disabled for songs without one. Both write to
  `exports\` atomically and replace an earlier export. Re-convert finds the song's source in
  `songs\pdf` by the hash its package or cache recorded and re-runs recognition with the engine
  selected on the home screen (forced, so the existing conversion is replaced); it is disabled for
  imports and MIDI files. After the user's review these three, with MP3, moved behind an EXPORT
  button below EXPRESSION that opens and closes them the same way and starts closed, so the
  playback screen opens with two small buttons instead of a row of large ones.
- **Notes no longer draw over the header.** A note entering at the top starts at the header's edge
  (its top is clamped), so a long note cannot cover the new facts line. Its bottom edge, the hit-line
  rules, fall speed and look-ahead are unchanged.
- **Bench:** `--bench` now prints frame-time p50, p95 and p99, which the acceptance criterion is stated
  in, and draws the bars and pedal lane like the app.
- **Cheaper button corners** (`UiTheme.DrawButton`, shared): 4 segments per corner instead of 10. At
  the button roundness a corner is 2-4 px, so the look is unchanged, and the dozen buttons on the
  playback screen cost less. This pays for the three new buttons (see Frame time).
- **A stored MIDI-device choice** opens Salamander at startup without a false "fell back" in
  `audio.log`.

## Evidence

- **xunit:** 163 passed (14 new in `FrontendScoreTests`; two recovery-policy tests updated for the
  new fallbacks).
- **Release gate:** 8 of 8 (`dist\_verify\launch.png` shows the two engine and two piano cards).
- **Smoke:** every screen rendered, including the new `01-landing-no-piano`, `07-playback` (a legacy
  song: MIDI (LEGACY) badge, Re-convert lit, MusicXML export disabled) and `07-playback-score` (a 480
  song in the second time through bar 3: staff colours, bar lines, pedal lane, TIMING FIX,
  counts, export status line).
- **Re-convert's source lookup on the real library** (read-only): all 7 packages and 118 of 120
  legacy caches resolve to a file in `songs\pdf`; the other 2 are 426 caches whose PDF is gone, for
  which Re-convert says so.
- **Frame time** (criterion: p95 within 10% of the pre-change baseline on the densest song). The
  baseline is the committed code (`15e2bd4`) plus only the p95 printout, published to
  `tmp\phase5-baseline`; the candidate is the final code, published to `tmp\phase5-candidate`. Runs
  alternate baseline and candidate, `--bench <song> --audio sfz --rate 1.0`, Salamander muted,
  1280x720, the playback screen drawn at 144 fps. rushe is the densest song (45,497 notes, a MIDI
  file, so no bars); STYX HELIX is the densest HOMR 480 song (2,917 notes), which draws everything
  new.

  | Song | Build | p50 | p95 | p99 | Underruns |
  | --- | --- | --- | --- | --- | --- |
  | rushe, 6,000 frames from 30 s | baseline | 0.79 / 0.76 ms | 1.78 / 1.76 ms | 2.29 / 2.15 ms | 0 / 0 |
  | | Phase 5 | 0.75 / 0.75 ms | 1.77 / 1.71 ms | 2.08 / 2.04 ms | 0 / 0 |
  | STYX HELIX, 4,000 frames from 20 s | baseline | 0.72 / 0.69 ms | 1.06 / 1.06 ms | 1.16 / 1.13 ms | 0 / 0 |
  | | Phase 5 | 0.71 / 0.71 ms | 1.10 / 1.06 ms | 1.29 / 1.15 ms | 0 / 0 |

  p95 moves by -4% to +4%, inside the 10%. The first candidate failed it: STYX p95 1.27 ms against
  1.09 (+16%). Timing each part of the playback screen put the cost in the button row (79 µs a
  frame, three of its four buttons new), not in the bars (2 µs), the readout (3 µs) or the facts line
  (18 µs). Four corner segments instead of ten fixed it without changing a pixel (a screenshot
  diff of the buttons is empty). The candidate's worst single frame is about 4 ms higher in every run
  (14-16 ms against 11 ms), one frame per run, consistent with the new drawing code compiling on
  first use; frames late stay at 1 per run in both builds.
- **One stalled bench run:** one of five runs of the first candidate stopped making progress (CPU
  flat for nine minutes) and was killed; its rerun and the 12 later runs of either build finished
  normally. The cause was not found.

## Feedback round (2026-10-20)

The user tried the build and asked for changes ("i like it tho just not the text the background
layer i like it", "my pdf song list is full of random numbers", the Jane Doe report below, and a
pedal idea), then chose: remove both bar texts, Auto pedal, fix the names now and redesign the
playlist later, and "you pick 30 and also delete those random rumber duplicates from the pdf playlist".

- **Bar text removed:** no numbers by the lines and no bar readout; the lines stay.
- **Browse lost a conversion if the file moved during recognition.** The user browsed to a PDF in
  Downloads, it played as MIDI (LEGACY) without TIMING FIX and never reached the playlist; from the
  library folder it worked. The job folders show two full recognitions of the same six pages
  (17:19-17:22 and 17:23-17:26), and only the second left a package. Cause: `song_entry.py` hashes
  its source again after recognition to write the package, and the MIDI fallback copies the source
  too, so a source cut to another folder while the model ran left neither, and the song played once
  from memory. A clean reproduction (`tmp\repro-browse`, the same PDF from outside a fresh library)
  converted correctly, which rules out the outside path itself. Fix: a file picked from outside the
  library is copied into `songs\pdf` before recognition and the copy is converted, so the original
  can move freely and the song is in the library from the start. Test:
  `AFileMovedAwayWhileItIsRecognisedStillBecomesALibrarySong`.
- **Numbered PDFs:** the 58 files named `<source sha>-<profile sha>.pdf` were copies the HOMR 465
  MIDI cache made of PDFs already in the library; each was byte-identical to a named file and nothing
  read them. They were moved to the Recycle Bin (list: `tmp\pdf-duplicates-recycled.txt`, local), so
  `songs\pdf` holds 60 named PDFs. The MIDI cache no longer makes such a copy of a library file, and
  if a numbered copy ever appears again the list shows its song's name (or "Unnamed score").
- **Auto pedal** (EXPRESSION panel, off by default): legato pedalling where the score has no marks.
  The pedal comes up at every bar and wherever the left hand's bass falls to a new pitch class, and
  goes down again 80 ms later, while the new notes are held; changes closer than 160 ms are held
  through; it lets go when the song ends. It replaces the pedal marks while on, and is not offered for
  MIDI files, which carry their own pedal. "Pedal all" was offered and not chosen: a held pedal
  smears every harmony into the next.
- **30 songs with HOMR 480 and the timing fix:** `--convert-batch` (new), resumable, one song at a
  time through the app's conversion path; see the job record in the handoff.
- xunit 170 (7 new); gate 8 of 8; smoke renders every screen.

## Not done, and for the user

- **Check it in the published app** (`dist\Sheet2Play.exe`): open a 480 song and a legacy one, try
  the pedal lane on a MIDI file with pedal, and the three new buttons. Re-convert runs a full
  recognition, which was not run here.
- `AGENTS.md` still says "HOMR 465 by default, HOMR 426 as the fallback", and `README.md` does not
  mention the piano installer; another chat has uncommitted edits to both, so they were left alone.
- The 426 and ZEUS tabs stay in the cache playlist while those songs exist.
- **Playlist redesign**, deferred by the user until they have added UI skills: each song once, best
  version first, and a convert action for PDFs without a 480 version.
