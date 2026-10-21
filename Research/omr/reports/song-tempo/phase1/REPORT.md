# Phase 1 report: per-song tempo map with bar changes

**Plan:** [`2026-10-19-song-tempo`](../../../../../plans/2026-10-19-song-tempo.md), Phase 1, requested
2026-10-21 ("refresh the md files first then start phase 1").
**Result: shipped and measured; waiting on the user's check in the published app.** Not committed.

## What shipped

- **TEMPO panel** (`Program.Tempo.cs`). A button in the bottom-left stack above EXPRESSION, closed at
  every start. It always shows the start tempo ("TEMPO ♩=110 · 2 CHANGES"), and "♩=120 · DEFAULT" in
  the warning colour when the song plays the fallback. When open, it shows:
  - the start tempo: − / + by 1 BPM, a typed field, and a beat-unit button cycling ♩ ♩. 𝅗𝅥 𝅗𝅥. ♪
  - **RESET**
  - **+ CHANGE AT BAR N** for the bar playing now, which adds a change there and opens its field for
    typing
  - one row per change above the start row (bar, tempo, DELETE), six at a time and scrolled with
    the wheel

  Note glyphs are drawn, because the UI font has no music symbols. Songs without a score show the
  button disabled with the reason: "RE-CONVERT TO SET" (legacy caches) or "FROM THE FILE" (MIDI
  files). Space and the arrow keys are ignored while typing.
- **Store** (`TempoMapStore.cs`). `tempo-maps.json` beside `settings.json`, keyed by the source
  file's SHA-256. Writes are atomic. An unreadable file is moved aside as `.unreadable-<time>`, not
  overwritten, and an invalid entry is dropped without losing the others.
- **Timeline** (`SongPerformance.cs`). `SongTimelineOptions.Tempo` (a `TempoOverride` with value
  equality) replaces the score's marks as a whole in `BuildTempoMap`. Changes are stored by
  measure index and play on every pass, the rule printed marks already follow. Editing re-times
  the session through `SongTimeline.MapPosition`, keeping the bar, the point within it, the speed
  and the play state.
- **Starting from the score.** The first edit seeds the map with what the song plays now: its marks
  in their own units, or quarters where a `<sound tempo>` disagrees with the printed metronome, or
  120. Nothing changes until the user changes something.
- **Another conversion of the same PDF.** The start tempo always applies. Bar changes apply only
  when the measure count matches. Otherwise they are listed in amber ("SET ON HOMR 465 WITH 214
  BARS; THIS HAS 210. NOT PLAYING.") with **KEEP** and **CLEAR**.
- **Bar numbers.** HOMR numbers measures per page, so "Beyond This Station" has 11 bar 1s. Bars are
  shown as their place in the song (1–214, the numbers in Export MusicXML) for PDF conversions,
  and as printed for imports (`SongTempoMaps.BarName`, also used by `SongOverlay`).
- **Everywhere the song plays.** The library lists a song at its tempo'd length with a "· tempo"
  tag, refreshed when leaving a song whose map changed. Export MIDI, WAV and MP3 follow the session.
  `--render-audio` and `--bench` read the stored map.
- **Verification tools.** `--verify-timeline ... --tempo SPEC` (for example `110q,17=110q.,25=186q`)
  applies a map without touching the store, and reports the median bar difference.
  `--verify-library` rows gain exact event hashes, so two builds can be compared song by song.

## Evidence

- **"Beyond This Station" against the user's MuseScore MIDI** ([`summary.json`](summary.json)),
  HOMR 480 package with the timing fix, 214 bars:

  | Tempo | App length | MIDI length | Median / max bar difference | Notes matched (of 3,897) | Median onset error |
  | --- | --- | --- | --- | --- | --- |
  | none (120) | 438.00 s (7:18) | 298.82 s | 62.5 s / 138.5 s | 738 | 0.112 s |
  | ♩ 110, bar 17 ♩. 110, bar 25 ♩ 186 | 298.82 s (4:59) | 298.82 s | 0.1 ms / 0.3 ms | 2,980 | 0.1 ms |

  The published `dist\Sheet2Play.exe` gives the same figures. Bars are compared by placing each
  bar's beat on both tempo maps, so this measures tempo alone. The 917 unmatched notes are
  recognition differences, not tempo.
- **No map plays exactly as before.** I ran `--verify-library` with a build of `HEAD` (`7667005`,
  with the same event-hash column added) and with this build, over the whole library:
  - 190 songs, 129 playing (43 packages, 59 legacy caches, 27 MIDI files)
  - **0 rows differ**, including the exact event hashes of all 129, with expression off and on

  The other 61 are legacy caches (58 HOMR 465, 3 HOMR 426) rejected as outdated in both builds.
  They predate this work. Local only: `library-before/`, `library-after/`.
- **Frame time** (criterion: p95 within 10% of the baseline on the densest song). Release
  single-file builds of `HEAD` and this code, alternating, `--bench SONG --audio sfz --rate 1.0`,
  1280x720:

  | Song | Build | p50 | p95 | p99 | Underruns | Late frames |
  | --- | --- | --- | --- | --- | --- | --- |
  | rushe (MIDI, 45,497 notes), 6,000 frames from 30 s | baseline | 0.69 ms | 1.67 ms | 1.96 ms | 0 | 1 |
  | | Phase 1 | 0.73 / 0.72 ms | 1.73 / 1.69 ms | 2.16 / 2.08 ms | 0 / 0 | 2 / 1 |
  | STYX HELIX (HOMR 480), 4,000 frames from 20 s | baseline | 0.64 / 0.64 ms | 1.07 / 1.04 ms | 1.17 / 1.17 ms | 0 / 0 | 1 / 1 |
  | | Phase 1 | 0.71 / 0.67 ms | 1.12 / 1.09 ms | 1.25 / 1.21 ms | 0 / 0 | 1 / 1 |

  - **p95 changes:** rushe +1% to +4%, STYX +5%. Both are inside the 10%.
  - **Stalled run:** the first baseline rushe run stalled (15 fps for 389 s, as one Phase 5 run did)
    and is left out.
  - **Worst single frame:** about 4–7 ms higher in every candidate run, one frame per run. That is
    consistent with the new drawing code compiling on first use.
  - **Code drift:** the candidate was published a few minutes before two small fixes (the panel's
    cache keyed on the score; scrolling a new change into view). Neither adds per-frame work.
- **Tests.**
  - xunit **193** passed (23 new: `TempoTests` and one in `SongPackageTests`, which checks that the
    package files are byte-identical after a map is set).
  - Bridge tests 67 passed, 2 skipped. One is new: the timing fix keeps every measure's index, page
    and number, so one map serves both layouts.
- **Release gate:** 8 of 8. Smoke from the published exe renders every screen, including
  `07-playback-score` (closed button, "♩=120 · DEFAULT") and `07-playback-tempo` (panel open with
  two changes).

## Deviations from the plan

- **The store keeps no `duration_seconds`.** The library already loads each song's performance
  when it lists it, so it computes the tempo'd length directly.
- **The store keeps no `timing_correction` field.** A test shows the fix never changes the
  measures.
- **The range is 10–400 BPM of the chosen unit,** not 20–400 quarter BPM. Slow dotted-half and
  fast eighth marks need it.
- **Names.** The change type is `BarTempo`, because `TempoChange` was already the bridge schema's.
  Change rows use a DELETE pill, not ×.

## Not done, and for the user

- **Check it in `dist\Sheet2Play.exe`.**
  1. Open "Beyond This Station" and open TEMPO.
  2. Set 110, play to bar 17, and press **+ CHANGE AT BAR 17**.
  3. Type 110 and click the unit until it shows ♩., then do the same at bar 25 with 186.
  4. The length should read about 4:59.
- **Legacy caches cannot be re-timed.** 61 of them no longer load at all (outdated revisions). They
  will be re-converted by Phase 6 of the MusicXML plan, or by Re-convert one at a time.
- **Printed tempo marks are still not read.** That is Phase 2 (research), which needs its own
  request.
