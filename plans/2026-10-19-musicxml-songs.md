# MusicXML songs: keep the score, play its expression, then a better piano and frontend

**Plan ID:** `2026-10-19-musicxml-songs`
**Status:** Proposed 2026-10-19 and approved the same day; the user authorized **Phase 1 only**
("start phase 1"). Phase 1 was completed and accepted the same day; Phase 2 is not authorized.
[Handoff](../Research/omr/reports/musicxml-songs/handoff.md). If an acceptance criterion is not met, ask before changing it, unless the fix
is small. Each later phase needs its own request. The user also said the C# engine may be
reworked (they wrote it and expect flaws), but in a separate request, at the end of this plan
right before Phase 6 converts most of the library.
**Related:** the per-song tempo plan (`2026-10-19-song-tempo`, still in the session plan folder
and to be saved as `plans/2026-10-19-song-tempo.md` when approved) runs after this one. This
plan does not edit it; [Fit with the tempo plan](#fit-with-the-per-song-tempo-plan) lists what
it hands over.

## Why

Every conversion today ends as notes and nothing else:

1. `bridge.py` renders the PDF, runs HOMR once per page and writes each page's MusicXML into a
   `TemporaryDirectory` (`run_native_page` returns `input_path.with_suffix(".musicxml")`). The
   directory is deleted when the run ends. `omr-jobs/<id>/` keeps only receipts and logs.
2. `musicxml_normalizer.normalize_musicxml` parses each page with music21, expands repeats
   **per page** (a repeat that crosses a page fails and plays once), merges ties and emits notes
   (`pitch`, `start_beat`, `duration_beats`, part, staff, voice). `combine_score_pages` stitches
   pages, rounding every page after the first to whole measures.
3. `SongCache.WriteMidi` stores the notes as a MIDI file with velocity 80 for every note
   (`DefaultVelocity`) and the tempo changes. `ReadMidi` turns it into `Note` records. Nothing
   else is kept: no measures, articulations, pedals, dynamics, slurs or voltas.

Verified gaps this plan must work around rather than assume away:

- **HOMR cannot read most of what the user wants.** Its vocabulary
  (`Bridge/.runtime/homr-480/source/homr/transformer/vocabulary.py`) has dynamics and hairpins
  commented out and no pedal or tempo tokens. Its exporter writes articulations (staccato,
  staccatissimo, tenuto, accent, fermata, arpeggiate, trill, tremolo, mordent, breath mark),
  slurs, ties, tuplets, grace notes, repeats and voltas. So for **PDF conversions** this change
  keeps articulations, ties, repeats, voltas, grace notes and measures. **Pedals, dynamics and
  tempo marks survive only for MusicXML imports** (for example MuseScore downloads) until OMR
  learns them, which is out of scope.
- **music21 10.5.0 loses pedals.** The research freeze recorded 488 "Could not import pedal"
  warnings on the OpenScore set (`Research/omr/phase3_freeze.py`). Pedals, and ideally dynamics,
  wedges and `<sound>` attributes, need a direct XML pass.
- **Grace notes are dropped today.** music21 gives them zero duration and `_validate_number(...,
  allow_zero=False)` rejects them with a warning, even though the MusicXML engine passes
  `skip_grace_notes=False`.
- **No MusicXML exists for the current library.** 115 PDFs; caches are 58 `homr465`, 57 `homr`
  (426), 3 `zeus` and 26 files in `custom`, with no `homr480` caches yet. Moving a song to the
  new model means recognizing it again.

## Constraints

- **Pinned files stay untouched.** `bridge.py`, `musicxml_normalizer.py` and the other files
  listed under `bridge_files` in `Bridge/homr465-profile.json` and `homr480-profile.json` are
  hashed into those profiles and into the C# pins (`Homr465ProfileSha256`, `Homr480ProfileSha256`).
  New code goes into **unpinned** modules that import and wrap the pinned ones, following
  `timing_correction.install`. If a pinned edit becomes unavoidable, stop and ask. It then means
  re-running `Research/omr/homr480_provision.py`, updating both C# pins, and every 465/480
  cache name changing (the profile SHA is in the file name, `SongCache.CreateCachePaths`).
- `audioOffsetSeconds` in `Playback.cs` (default 0.055) is never changed. A new sound engine is
  calibrated by the user, by ear, through the existing visible offset control.
- Every user-adjustable setting gets a visible on-screen control.
- Shipped phases pass `scripts\verify-release.ps1`, and are then checked in the relaunched
  `dist\Sheet2Play.exe`. Commits carry no AI co-author trailers.
- The C# frontend is decompiled output (`CONTEXT.md` 3.1). New logic goes in new hand-written
  files. Edits to `Program.cs` and `Note.cs` stay small and covered by tests or smoke snapshots.
- Long GPU work (library re-conversion) runs under the mandatory safeguards: the supervisor, one
  heavy worker, the 85% RAM/commit stops and the 4 GiB commit reserve.

## Target song model

Two layers, each with its own identity:

1. **The score (source of truth).** The MusicXML the song came from, kept verbatim:
   - PDF conversions: HOMR's page files, unmodified, in page order.
   - MusicXML imports: the imported `.mxl` / `.musicxml` file.
   - A **combined MusicXML** (one `score-partwise`, measures renumbered, `<print new-page="yes"/>`
     at page starts) is also written, for export and for opening in MuseScore. It is never used
     for timing, because combining pages needs part alignment that can lose information.
2. **The performance (derived, rebuildable from layer 1 without OMR).** A JSON document, schema
   3, written by an unpinned interpreter:
   - `measures[]`: index, printed number, page, start beat after stitching (and after the timing
     fix when on), length, time signature, pickup flag, barline and repeat or volta marks.
   - `play_order[]`: measure indices in performance order with repeats and voltas expanded over
     the **whole score**, not per page. D.C./D.S./Fine/Coda follow when music21's expander
     handles them; anything it cannot expand is reported, and the measures play once.
   - `notes[]`: pitch, measure, offset within the measure, written duration (ties merged), staff,
     voice, grace flag and articulation flags.
   - `pedals[]`: start/stop/change at measure + offset, plus `<sound damper-pedal>` values.
   - `dynamics[]` (marks and `<sound dynamics>`) and `wedges[]` (cresc./dim. spans).
   - `tempos[]`: only marks actually in the score (`<sound tempo>`, `<metronome>`), with their
     beat unit. When a score has none, the list is empty: no default 120 is written anywhere.
   - `features`: counts of each kind found, and warnings (unexpandable repeats, music21 loss).

**Kept and played:** notes, ties, measures, pickups, repeats and voltas, grace notes,
articulations (staccato and staccatissimo shorten, tenuto holds, accent raises velocity,
arpeggiate rolls the chord), pedals, dynamics and hairpins, tempo marks. **Kept but not played:**
slurs, fermatas (they would bend the timeline; recorded for a later choice), trills, tremolos and
lyrics. Each played feature has an on/off control (Phase 3).

## Where conversion happens

| Option | For | Against |
| --- | --- | --- |
| **A. Bridge interprets structure; C# renders performance** (recommended) | music21, the stitching rules and the timing fix are already Python and tested there; research scoring stays comparable; C# gets a flat, strictly validated JSON | MusicXML imports still need the HOMR venv's Python (true today); interpretation changes need a Python run, cheap and cached |
| B. C# parses MusicXML | No Python for imports; one language at playback | Re-implements repeats, voltas, backup/forward, ties and voices in the decompiled app; diverges from research; no mature .NET MusicXML interpreter |
| C. Bridge emits seconds, as today | Smallest change | Every playback setting (pedal, dynamics, repeats, tempo overlay) would need a Python run |

Split for A:

- **Python** (`Bridge/song_entry.py` and `Bridge/song_model.py`, both new and unpinned):
  `song_entry.py` installs a wrapper around `bridge.normalize_musicxml` that copies each page file
  out before the temporary directory is deleted, then runs `bridge.main` unchanged, so the schema
  v2 JSON on stdout and every runtime and profile check stay as they are. It takes over
  `timing_correction.py`'s role as entry script. `song_model.py` builds layer 2 from layer 1:
  the pinned normalizer's parsing and `_page_advance` stitching, `timing_correction`'s layout
  functions (imported, file unchanged), whole-score repeat expansion, and an ElementTree pass for
  pedals, dynamics, wedges, `<sound>` and `<metronome>`. It can run on stored pages alone
  (`song_model.py --pages DIR`), so no OMR is needed to rebuild.
- **C#** (new `SongModel.cs`, `SongTimeline.cs`, `SongPackageCache.cs`): reads the performance
  JSON with `UnmappedMemberHandling.Disallow`, walks `play_order`, converts beats to seconds through
  a tempo map, applies the playback policy (articulation, dynamics → velocity, pedal events), and
  produces the existing `Note` list plus new control events. C# never parses MusicXML.

## Cache format, identity and migration

**Layout** (in the library, one directory per conversion, written to a temporary directory and
moved into place):

```
songs/scores/<engine>/<source-sha>-<profile-sha>/      (pinned engines; others: <source-sha>)
  recognition.json        engine, revisions, profile SHA, song_entry.py SHA, page SHAs
  pages/page-0001.musicxml ...                         (imports: source.mxl)
  derived/<interp-key>/performance.json
  derived/<interp-key>/score.musicxml                  combined, for export
  derived/<interp-key>/manifest.json                   cache manifest v3
```

**Identity in three layers:**

1. **Recognition** (expensive; only OMR rebuilds it): source SHA-256, engine, engine and model
   revision, runtime profile SHA, `song_entry.py` SHA, page SHAs. The timing fix is **not** part
   of it any more.
2. **Interpretation** (seconds; rebuilt automatically from stored pages): `interp-key` = SHA-256
   of `song_model.py`, `timing_correction.py` (or `off`) and the schema version. Turning
   **TIMING FIX** on or off, or shipping a new interpreter, re-interprets on the next load with no
   OMR run and no prompt.
3. **Playback policy** (never cached): repeats, pedal, dynamics, articulations, piano choice,
   playback rate and the later tempo overlay, all applied when the timeline is built.

The manifest records the SHA-256 of the pages, `performance.json` and `score.musicxml`. A
missing, corrupt or mismatched file is never used. It leads to re-interpretation when the pages
are intact, otherwise to the existing Use cached / Re-run / Cancel flow. The known-failure store
(`OmrFailureStore`) and the cache-hit prompt stay as they are.

**Migration.** The current MIDI caches cannot be upgraded because their MusicXML is gone:

- Manifest v2 MIDI caches stay readable, untouched and listed with a visible **"MIDI (legacy)"**
  badge and a **Re-convert** action. They play exactly as today.
- New conversions write only song packages. `WriteMidi` is no longer called for HOMR or MusicXML
  songs.
- Bulk re-conversion of the 115 PDFs with HOMR 480 reuses `LibraryMigrationRunner` (frozen
  inventory, resumable journal, deadline) under the safeguards. It is a separate,
  user-authorized step (Phase 6). Legacy caches are kept until the user removes them.

## What stays MIDI

- **Direct MIDI files** (`songs/midi/custom/*.mid`, engine `DirectMidi`) stay MIDI. `ReadMidi`
  additionally reads CC64 (sustain) into the same pedal events, so MIDI files gain pedals too.
- **Legacy caches** (above), and the experimental **Zeus** engine, whose output is notes rather
  than MusicXML: it keeps its MIDI cache path unchanged.
- **MIDI device output**: the external-device backend receives note and CC64 events.
- An explicit **Export MIDI** action may write MIDI from the timeline (Phase 5). It is an export,
  not a cache.

## Playback changes

- `PlaybackSession` events gain a control kind (CC64 value) beside note on/off. `Note` stays the
  visual unit; control events live in a parallel sorted array, so `GetVisibleRange` and the
  renderer are unchanged.
- **Seek** restores the pedal state at the target time (last pedal event at or before it);
  pause, stop and song end release the pedal; offline export (WAV/MP3) renders the same events.
- **MeltySynth** 2.4.1 has a per-channel hold pedal (`SetHoldPedal`); `SoundFontEngine` sends
  CC64 through `ProcessMidiMessage` at sample-accurate positions, like notes. `DryWetMidiOutput`
  sends `ControlChangeEvent(64, v)`. `MaximumPolyphony` (256) already anticipates held voices.
- **Velocity** comes from dynamics (pp…ff, sfz, fp, `<sound dynamics>`, wedges interpolated)
  plus accents. With no marks it stays 80, as today.
- **Tempo** comes from the score's marks, otherwise 120 applied at timeline build.

### SFZ piano: options and licences

"MuseScore-like": MuseScore's own Muse Sounds pianos are proprietary and licensed for use inside
MuseScore only, so they are excluded. MuseScore's older default font (MuseScore_General, MIT) is
SF3, which MeltySynth does not read. I believe its piano comes from the Salamander recordings; this
is to be checked against its readme before it is stated anywhere user-facing. Two SFZ pianos are
already in the git-ignored `pianos/`:

| Sample set | Licence | Content | Notes |
| --- | --- | --- | --- |
| **Salamander Grand Piano V3** (Yamaha C5), 1.9 GB, 48 kHz/24-bit | CC BY 3.0 (Alexander Holm): free to redistribute with attribution | 16 velocity layers in minor thirds, release (hammer and string) samples, pedal up/down noise | Uses about 20 opcodes: `sample`, `lokey`/`hikey`, `pitch_keycenter`, `lovel`/`hivel`, `amp_veltrack`, `volume`, `trigger=release`, `rt_decay`, `group`/`off_by`, `lorand`/`hirand`, `on_locc64`/`on_hicc64`, `ampeg_release` |
| Keppy's Steinway, 787 MB | CC BY 4.0 | One sample per key, velocity via a filter | Simpler and less realistic. Fallback only |
| YDP Grand Piano SF2 (current) | CC BY 3.0 | SF2 for MeltySynth | Stays as the default until the user picks otherwise |

| Player | Licence | For | Against |
| --- | --- | --- | --- |
| **Managed C# SFZ subset player** (recommended to try first) | Our code | No native DLL in the release path; reuses `SoundFontEngine`'s sample-accurate scheduler; the sample bank can be memory-mapped, which counts as file-backed rather than commit (this machine's crash risk) | We own the opcode subset; needs care for interpolation, voice stealing and release triggers |
| sfizz via P/Invoke | BSD-2-Clause | Full SFZ v2 with disk streaming | Native DLL to build, ship, hash-check and keep alive; slower upstream activity |
| SFZ → SF2 conversion, keep MeltySynth | Tool-dependent, output follows the sample licence | Cheapest | Loses release samples, pedal noise and `rt_decay`; SF2 is 16-bit |
| FluidSynth | LGPL-2.1 | Mature | SF2/SF3 only, not SFZ |
| BASSMIDI | Commercial for non-free use | — | Excluded |

Samples are installed to `%LOCALAPPDATA%\Sheet2Play\pianos` by a script with a pinned hash, like
`install-soundfont.ps1`, never into `dist` (the gate wipes it). The installer pre-converts to a
single 16-bit sample bank plus an index. The licence and attribution are installed beside it and
shown in the app.

## Effects on the falling-notes view

- Notes fall on the **expanded** timeline (`play_order`). Falling-note length is the sounding
  length after articulation, so what is seen matches what is heard; key highlighting follows it.
- **Hand colour by staff** (MusicXML staff 1/2) replaces today's split at key index 39 for
  MusicXML songs. MIDI and legacy songs keep the key split.
- **Bar lines** across the note field from `measures`, and a **"Bar N"** readout (with the pass,
  for example "Bar 12 · 2nd time"), which the tempo plan also needs.
- A **pedal lane** above the keyboard showing pedal down and up.
- No change to fall speed, look-ahead, `GetVisibleRange` or the hit-line rules in
  `DrawFallingNote`.

## Phases

### Phase 1 — Song package and performance model in the bridge (no shipped change)

*Effort: high. New interpreter with musical edge cases.*

Write `song_entry.py`, `song_model.py` and `Bridge/tests/test_song_model.py`. Use the existing
captures as inputs: `Research/omr/data/displacement-ruler/captures/{homr465,homr480-ab369ac}`
(154 scores each, page MusicXML) and the exact `label.musicxml` files (of 216 scores: 106 have
pedals, 204 dynamics, 110 staccato, 16 repeats). Add small hand-written fixtures for cross-page
repeats, voltas, pickups, grace notes and meter changes.

**Result (2026-10-19): accepted.** All 292 captured recognitions without repeats match the bridge
note for note with the timing fix off and on; the 14 with repeats match exactly once repeat expansion
is off, so their only difference is the whole-score expansion. Feature counts equal an independent
count on all 207 labels; interpretation is byte-for-byte repeatable; the largest score takes 3.2 s
and 82 MiB; no pinned file changed. One criterion was refined as a small change: MuseScore refuses
HOMR's own incomplete measures, so a combined score may be refused only where one of its pages is,
and must open with `--force`. The run also showed that the bridge's per-page repeat expansion is
wrong across pages, ignores `times`, and misplaces staves of uneven length. See the
[Phase 1 report](../Research/omr/reports/musicxml-songs/phase1/REPORT.md) and the
[handoff](../Research/omr/reports/musicxml-songs/handoff.md).

**Accept when:**
- **Parity:** with repeats played as today and expression off, `song_model.py` reproduces the
  current bridge notes (pitch, start and duration beat within 1e-6) on 100% of captured scores
  whose pages have no repeat barlines, with the timing fix off and on (same check as
  `displacement_ship_check.py`). Every score that differs is listed with the reason (cross-page
  repeat expansion, grace notes).
- **Features:** on the exact labels, counts of pedal events, dynamics, wedges, articulations and
  tempo marks equal an independent XML count on 100% of files, including files with music21 pedal
  warnings.
- **Rebuild:** interpreting the stored pages twice gives byte-identical `performance.json`;
  `score.musicxml` parses in music21 and in the MuseScore 4 CLI without errors.
- **Cost:** interpretation of the largest library score takes under 10 s, with peak RAM recorded.
- **Pins:** both profile files and every pinned bridge file hash unchanged.

### Phase 2 — C# song model and cache v3 (shipped; sound unchanged)

*Effort: high. Cache identity and the decompiled frontend.*

`OmrPipeline` launches `song_entry.py` for HOMR and MusicXML engines, with the runtime checks of
the engine. Add `SongModel`/`SongTimeline`/`SongPackageCache`, keep legacy MIDI reading, and make
TIMING FIX a re-interpretation. Playback uses notes from the model. Expression stays off, and
repeats expand across the whole score.

**Accept when:**
- Three fresh 480 library conversions give the same onsets as their v2 JSON within 1 ms (scores
  without repeats).
- Toggling TIMING FIX on a converted song rebuilds in under 15 s with no OMR process
  (`[SONG CACHE] decision=reinterpret` in the log).
- All 118 legacy MIDI caches and 26 custom MIDI files load and play (a test harness loads each).
- Unit tests cover identity mismatch, corrupt files and the atomic write.
- Release gate passes, and one PDF converts end to end in the published exe.

### Phase 3 — Expressive playback (shipped)

*Effort: standard to high.*

Pedal, dynamics, articulation and tempo-mark playback; CC64 for MeltySynth, the MIDI device and
export; CC64 read from direct MIDI files. Visible controls in an **EXPRESSION** panel: Pedal,
Dynamics, Articulations and Repeats, each ON/OFF.

**Accept when:**
- The pedal state is correct at 100% of 1,000 random seek points on fixtures.
- Offline render: with pedal, voices stay active after note-off while CC64 is down (MeltySynth
  voice count) and release when it lifts; without pedal the render equals Phase 2.
- Velocities are ordered pp < p < mf < f < ff on a fixture; wedges are monotone.
- On a MusicXML with tempo marks (ideally the user's "Beyond This Station" MusicXML from MuseScore),
  total length is within 1% of MuseScore's MIDI export and per-bar onsets are within 50 ms.
- All expression off reproduces Phase 2's event list exactly. `audioOffsetSeconds` unchanged.
- Release gate passes.

### Phase 4 — SFZ piano (shipped after a decision spike)

*Effort: high. Real-time audio and memory.*

**4a, spike (no ship):** the managed subset player and sfizz render the same three songs.
Measure commit charge, working set, load time, CPU per block at 256 voices, underruns over a
10-minute render, and opcode coverage on Salamander. Give the user WAVs (YDP vs Salamander) to
compare by ear. The user picks.
**4b:** implement the pick, plus the installer, the **PIANO** selector (YDP / Salamander /
MIDI device) and the attribution text.

**Accept when:** commit charge rises by no more than 300 MB with the bank loaded; there are no
underruns on the library's densest song at 1.0× and 2.0×; a warm load takes under 5 s; offline
renders are deterministic; the user approves the sound; audio sync is re-checked by ear with the
existing control, without editing the Playback.cs default; the release gate passes.

### Phase 5 — Frontend (shipped)

*Effort: standard.*

Bar lines and bar readout, pedal lane, staff colours, song badges (engine, timing fix, "MIDI
(legacy)", found features such as "34 articulations · 0 pedals"), Re-convert, Export MusicXML and
Export MIDI.

**Accept when:** `--smoke` snapshots cover every new screen and state; every new setting has a
visible control; frame time p95 (`Program.Bench`) stays within 10% of the pre-change baseline on
the densest song; the user checks it in the published exe; the release gate passes.

### Phase 6 — Library re-conversion (operational, separate authorization)

Freeze an inventory of the 115 PDFs and run HOMR 480 into song packages through
`LibraryMigrationRunner` under the safeguards. **Accept when** at least as many songs convert as
in the 465 migration (56 succeeded), every failure is recorded with its reason, and legacy caches
are untouched.

## Fit with the per-song tempo plan

- That plan's Phase 1 overlays a user tempo map in `ReadMidi`. After this change, OMR songs have
  no MIDI cache, so its hook moves to `SongTimeline` (beats → seconds), which takes a pluggable
  tempo source. Precedence stays as that plan defines it.
- `measures` + `play_order` are the bar map, which retires that plan's `bar_map.py` sidecar and
  `SHEET2PLAY_BARS:` transport. That plan has to decide whether a change at a printed bar applies on
  every pass of a repeat; the bar map exposes both the printed number and the pass.
- As it asks: measure numbers and pickups are kept, corrected and uncorrected layouts are separate
  interpretations, no default `<sound tempo="120">` is written, and user maps stay overlays outside
  the stored MusicXML.

## Risks

- **Decompiled code.** `Program.cs`, `Note.cs` and the `GameState` handling have decompiler scars.
  Mitigation: new types in new files, an adapter to `Note`, smoke snapshots and tests before each
  edit.
- **Release gate.** New `.py` files must be picked up by the `..\Bridge\*.py` content glob and
  checked by the gate; a native sfizz DLL would need publish and `ExcludeFromSingleFile` rules and
  a gate check. Sample banks live outside `dist`.
- **Cache invalidation.** Three identity layers; a pinned-file edit would invalidate the whole
  465/480 library, so it is avoided; legacy and v3 caches coexist; nothing is reused on mismatch.
- **Expectations.** PDFs gain articulations, repeats and grace notes, not pedals or dynamics
  (HOMR does not read them). Repeats crossing pages now play twice, which can expose HOMR's
  misread repeats; the Repeats switch is the escape hatch.
- **Memory.** A 1.9 GB sample set on a machine with commit-exhaustion crashes: memory-mapped bank
  and the 300 MB budget.
- **Licences.** CC BY attribution for every sample set shown in the app; BSD notice if sfizz ships.
- **Python on load.** Re-interpretation spawns the HOMR venv's Python; it runs only on identity
  change, with progress shown.

## What to test

- `Bridge/tests`: interpreter parity on captures, feature counts on labels, cross-page repeats,
  voltas, pickups, grace notes, meter changes, unexpandable repeats, ties across barlines and
  pages, determinism, and pinned hashes unchanged.
- `Visualization_engine.Tests`: v3 manifest round-trip and every mismatch path, atomic writes,
  legacy MIDI loading, timeline build (repeats on/off, tempo marks, 120 fallback), articulation
  and velocity mapping, pedal seek state, CC64 in direct MIDI, `audioOffsetSeconds` default
  unchanged, and SFZ region selection (key, velocity, round robin, release trigger, `off_by`).
- Offline renders: pedal sustain, determinism, underruns at 256 voices.
- End to end: one PDF per phase through the published exe; the release gate; `--smoke`
  snapshots; frame-time bench.

## Out of scope

Teaching HOMR pedals, dynamics or tempo marks; auto-generated pedal for PDFs; fermata timing;
editing the stored MusicXML; changing `audioOffsetSeconds`; training; cloud spending.
