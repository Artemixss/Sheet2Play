# Per-song tempo: a user tempo map first, measured tempo-mark reading second

**Plan ID:** `2026-10-19-song-tempo`
**Status:** First drafted 2026-10-19 and accepted by the user, but deferred ("don't execute it now")
until the MusicXML-song plan landed. **Rewritten 2026-10-21** against the merged MusicXML-song code
(`af0332b` … `7667005`). That change moved the timeline out of the cached MIDI and exposes bars,
so the 2026-10-19 draft's `ReadMidi` overlay and `bar_map.py` sidecar are superseded (see
[Superseded from the 2026-10-19 draft](#superseded-from-the-2026-10-19-draft)). On 2026-10-21
the user authorized **Phase 1** ("refresh the md files first then start phase 1"). It shipped,
was checked by the user and committed the same day (`9bd66f9`,
[Phase 1 report](../Research/omr/reports/song-tempo/phase1/REPORT.md)). **Phase 2** (research)
was requested the same day ("push it and start phase 2") and is **accepted**: the frozen OCR reader
passed every pre-registered check on the test splits, scored once
([Phase 2 report](../Research/omr/reports/song-tempo/phase2/REPORT.md)). It was committed and
pushed (`bf4ed00`). **Phase 3** was requested the same day ("ok commit and push proceed with phase
3"). Printed marks are read after each PDF conversion or from the panel; the USE / IGNORE version
was checked and committed (`30bcbff`). The user then made printed marks **play by default**, and
every library PDF was read once. That amendment was checked by the user ("it works commit and
push") and committed (`b008fd7`). **Phase 4**, tempo words as measured guesses, was added the same
day ("add tempo words as phase 4") and is not started ([Phase 3 report](../Research/omr/reports/song-tempo/phase3/REPORT.md),
[handoff](../Research/omr/reports/song-tempo/handoff.md)).
**Related:** [MusicXML songs](2026-10-19-musicxml-songs.md), whose
[Fit with the per-song tempo plan](2026-10-19-musicxml-songs.md#fit-with-the-per-song-tempo-plan)
section is the hand-over this plan builds on.

## Why

HOMR 480 (the default) and 465 (the secondary) read no tempo marks. A PDF conversion's
`performance.json` therefore has `tempos: []`, and `SongTimeline.BuildTempoMap`
(`Visualization_engine/SongPerformance.cs:466`) falls back to `SongTimelineOptions.DefaultTempoBpm`
= 120.

Measured on 2026-10-21 with the user's song "Beyond This Station" (HOMR 480 package, timing fix
on, 214 measures, 876 beats) and the user's MuseScore MIDI of it
(`songs/midi/custom/HOYO-MiX, Mika Kobayashi - Beyond This Station.mid`):

| From | MuseScore MIDI | OMR bar |
| --- | --- | --- |
| beat 0 | ♩ = 110, 4/4 | bar 1 |
| beat 64 | ♩ = 165 (♩. = 110), 12/8 | bar 17 (the package's 12/8 starts here) |
| beat 112 | ♩ = 186, 4/4 | bar 25 to the end |

That map gives about 4:58. At 120 the app plays 7:18.

## What the merged code already gives this plan

- **A tempo hook.** `SongTimeline` converts beats to seconds through a private `TempoMap` built
  per measure *occurrence* from `performance.Tempos`. A mark applies every time its measure plays
  and holds until the next one. `SongTimelineOptions` already reaches every caller: playback
  (`ExpressionPlayback.ForSong`), the bar overlay (`SongOverlay.For`), offline WAV/MP3
  (`Program.RenderAudio.cs:115`) and `MapPosition`.
- **Position-preserving rebuilds.** `SongTimeline.MapPosition(performance, from, to, seconds)`
  maps a position between two option sets. `ApplyExpressionChange` (`Program.Expression.cs:55`)
  already rebuilds a playing session while keeping place, rate and play state.
- **Bars.** `measures[]` (index, page, start beat, length, time signature, pickup) and
  `play_order[]` are the bar map. Corrected and uncorrected layouts are separate interpretations
  of the same pages.
- **No cache involvement.** Tempo is playback policy, never cached (MusicXML plan, "Identity in
  three layers"). The package check uses the default `SongTimelineOptions`
  (`SongCache.Packages.cs:47`), so an overlay cannot invalidate a package.
- **Exports follow the session.** Export MIDI writes `playback.Session.Notes`
  (`Program.Score.cs:249`), so it follows the user's tempo with no extra work. Export MusicXML
  writes the stored score and stays OMR output.

## Facts found on 2026-10-21 that shape the design

- **`measures[].number` is not unique in PDF conversions.** HOMR numbers measures per page, so
  "Beyond This Station" has `number` 1–16, then 1–8, 1–24 and so on across 11 pages. Only the
  combined `score.musicxml` numbers them 1–214 (`song_model.py:1019`: running index + 1, no
  pickup 0). The tempo map therefore stores the **measure index**, and the panel shows
  **index + 1** for OMR songs. That matches Export MusicXML and what MuseScore shows when the user
  opens it. MusicXML imports show their printed number.
- **Bar numbers are not drawn on the note field.** The user removed them in Phase 5 and kept the
  lines (`DrawBarLines`, `Program.Score.cs:62`). `SongOverlay.BarLabel` exists but has no caller.
  Any "Bar N" text belongs inside the TEMPO panel only.
- **The UI font has no music glyphs.** `UiDesign.cs:66` loads code points 32–0x024F, so ♩ and ♪
  cannot be typed as text. Beat-unit symbols are drawn with Raylib primitives, the way
  `DrawPanelButton` draws its chevron.
- **`SongLoadResult` has no source hash.** The package manifest has `SourceSha256`, but it is not
  passed through. Phase 1 adds it.
- **Legacy and MIDI songs have no score.** About 59 songs still play from manifest v2 MIDI
  caches (426, Zeus, older 465) until Phase 6 of the MusicXML plan re-converts them. Direct MIDI
  files carry their own tempo.

## Tempo semantics (all phases)

- **Precedence:** the user's map, then the marks printed in the PDF (Phase 3; all but the ones
  the user ignored), then the score's own marks (MusicXML imports), then 120. The user decided on
  2026-10-21, after checking Phase 3, that printed marks play by default ("i want is this tempo
  change to be the default so apply this tempo change to my all songs"); before that they played
  only after USE. A user map **replaces** the score's marks as a whole. It is
  not merged with them, so what plays is exactly what the panel lists.
- **Repeats:** a change at a bar applies on every pass of that bar, which is the rule
  `BuildTempoMap` already uses for printed marks.
- **Beat unit:** BPM is entered per beat unit (♩, ♩., 𝅗𝅥, 𝅗𝅥., ♪) and stored as entered. It is
  converted to quarter BPM only when the tempo map is built. Allowed range: 10–400 BPM of the
  chosen unit.
- **Playback rate** (0.05–2.00x) still multiplies on top as practice speed. `audioOffsetSeconds`
  is not touched.
- **Overlays only.** User and detected maps are never written into stored MusicXML, pages or
  `performance.json`. No default `<sound tempo="120">` is written anywhere.

## Phase 1 — Per-song tempo map with bar changes (shipped)

*Effort: standard.* The 2026-10-19 draft split this into a start-tempo phase and a bar phase.
The merged bar map lets both ship together.

**Result (2026-10-21): shipped, not committed.**
- "Beyond This Station" with the user's map plays 298.82 s against the MIDI's 298.82 s, with a
  median bar difference of 0.1 ms. It played 438 s before.
- With no map, all 129 playing library songs give identical events.
- Frame-time p95 +1% to +5%; xunit 193; release gate 8 of 8.
- Deviations: no `duration_seconds` or `timing_correction` in the store, the range is 10–400 BPM
  of the chosen unit, and the change type is named `BarTempo`.

See the [Phase 1 report](../Research/omr/reports/song-tempo/phase1/REPORT.md).

**Store.** A new `TempoMapStore` (`Visualization_engine/TempoMapStore.cs`), modelled on
`RecentSongsStore` and `OmrFailureStore`. It writes `tempo-maps.json` beside `settings.json` in
`%LOCALAPPDATA%\Sheet2Play`, with atomic writes (temp file + move) and repair like
`AppSettingsStore.ReadOrRepair`.
- Key: source SHA-256. Entry: `start {bpm, beat_unit}`, `changes[] {measure_index, bpm,
  beat_unit}`, plus `engine`, `measure_count` and `timing_correction` recorded when the map was
  last edited, `duration_seconds` (display only, recomputed on each load) and `updated_utc`.
- **Another conversion of the same PDF** (the other engine, or a re-run that found a different
  number of bars): the start tempo always applies. Bar changes apply only when `measure_count`
  matches. Otherwise the panel shows them in amber as "set on HOMR 465 (214 bars); this
  conversion has 210" with **Keep** / **Clear**, and they do not play until kept. It is never
  silently wrong. The timing fix does not change the measure count (one measure per page measure
  either way). A test checks this.

**Timeline.** `SongTimelineOptions` gains an optional `TempoOverride` (start quarter BPM plus
changes by measure index), a record with value equality so option comparison stays correct.
`BuildTempoMap` uses it in place of `performance.Tempos` when it is present. `SongLoadResult`
gains `SourceSha256`, filled from the package manifest. Offline WAV/MP3 render passes the same
override.

**Control.** A **TEMPO** button joins the bottom-left panel stack, above EXPRESSION and EXPORT,
drawn with `DrawPanelButton` and closed at every start (the user's collapsible-panel rule).
- Button label: "TEMPO" plus the start mark (drawn note glyph + "=110"), or "TEMPO · 120 default"
  in the warning colour when the song plays the fallback, so a missing tempo is never hidden.
- Panel row: start-BPM stepper with a typed field (built like `PlaybackRateEditor`), beat-unit
  selector, **Bar N** readout of the bar playing now (panel only), **+ CHANGE AT BAR N** (adds
  a change at the current bar with the current tempo, so the user can play, pause where it speeds
  up, and press it), and **RESET** (back to the score's marks, or 120).
- Changes list: a compact list opening above the row, with one line per change (bar, BPM, beat
  unit), each editable and deletable.
- Applying while playing rebuilds the session through `SongTimeline.MapPosition` (same bar, same
  point within it), as `ApplyExpressionChange` does.
- Disabled with a reason for legacy caches ("Re-convert to set a tempo") and direct MIDI files
  ("This MIDI file keeps its own tempo").

**Library.** A song with a map shows its tempo'd duration from `duration_seconds` and a
" · tempo" tag next to the timing-fix tag.

**Tests** (`Visualization_engine.Tests`):
- Store round trip, repair of a corrupt file, and atomic write.
- Override timing against hand-computed seconds, including ♩. in 12/8.
- Repeats: a change plays on every pass.
- Precedence: user over score marks over 120.
- `MapPosition` keeps the bar and offset across a tempo change.
- The measure-count mismatch path does not play bar changes.
- Measure count is equal with the timing fix on and off on fixture pages.
- Package files and manifests are byte-identical before and after a map is set.
- `--smoke` snapshots of the closed button, the open panel and the changes list.

**Accept when:**
- "Beyond This Station" with ♩ = 110 at bar 1, ♩. = 110 at bar 17 and ♩ = 186 at bar 25 is
  within 1% of the MuseScore MIDI's length. Per-bar onsets agree with that MIDI to a median
  absolute error under 50 ms over the bars both share. (The package has 876 beats and the MIDI
  872, so the comparison aligns by bar, not by total.)
- With no map, every playing library song gives identical events to before (the existing
  `--verify-library` check).
- Frame time p95 (`Program.Bench`) stays within 10% on the densest song.
- `audioOffsetSeconds` is unchanged, the release gate passes, and the user checks it in the
  published exe.

## Phase 2 — Research: can printed tempo marks be read? (accepted 2026-10-21)

*Effort: high.* This is what the user's 2026-10-20 note calls the "tempo tracker". It runs only
after Phase 1, so that reading has a store and a panel to feed.

- **Tempo-truth set (new; frozen manifests untouched).** The exact-label sets hold almost no tempo
  truth: only 5 of 207 `Research/omr/data/displacement-ruler/*/label.musicxml` files have a
  `<metronome>` or `<sound tempo>`. Build derived copies of those labels (dev, dev-b, test,
  test-b, same composer splits) with injected `<metronome>` marks and tempo words: seeded BPM and
  beat units (♩, ♩., 𝅗𝅥), at bar 1 and at 0–3 mid-score bars, at system starts and mid-system.
  Re-engrave them with the project's own MuseScore generator at the pinned version. The set gets
  its own manifest and SHA. The unmodified sets are the false-detection control: `cresc.`,
  `rit.`, `a tempo`, `Una corda` and the like must not become tempos.
- **Real-score sanity set (private, local only).** 11 library PDFs have a MuseScore MIDI of the
  same name in `songs/midi/custom` (found 2026-10-21). Their MIDI tempo events give start-tempo
  and change truth on real engravings. They are reported separately and are not used to tune.
- **Candidates** (unpinned `Research/omr/tempo_read.py`):
  - (a) `rapidocr` 3.9.2 (already in `Bridge/.venv-homr-gpu`) on the strip above each system,
    with system boxes from HOMR staff detection as `Bridge/detect_systems.py` gets them. It reads
    the digits after "=".
  - (b) A small template or classifier for the beat-unit glyph left of "=", because OCR will not
    read note glyphs.
  - (c) A tempo-word lexicon that produces *suggestions only*, because words do not fix a BPM.
  - The mark's x position against barlines gives the bar.
  - HOMR's `title_detection.py` deliberately filters tempo-like text out and is not a tempo
    reader. Its pinned no-title policy is not touched.
- **Metrics:** mark recall and precision, exact BPM, beat-unit accuracy, bar accuracy, false
  tempos per score on the control sets, and peak RAM and seconds per page under the mandatory
  safeguards (supervisor, one heavy worker, stop at 85%). OCR runs on the CPU, and the 426
  PaddleOCR detector once failed with "bad allocation" under a 4 GiB cap, so memory is measured,
  not assumed.
- **Freeze:** pre-register acceptance after dev and dev-b, before test. Proposed thresholds:
  start-tempo exact BPM ≥ 0.95 where a mark is printed, false tempos ≤ 0.02 per score, and bar
  accuracy ≥ 0.9 for mid-score marks. Then score test and test-b once.
- **Pre-registered rule (written 2026-10-21, before any test-split read).** The judged candidate
  is **OCR**, because 47 of the 61 library PDFs have no text layer. The text-layer reader is scored
  and reported but not judged, since it is only a shortcut for PDFs that have one. The rule is
  judged on test and test-b pooled, with each split shown, by `tempo_read.py verdict` against
  `freeze.json`. Phase 2 is accepted only if every check passes:

  | Set | Metric | Rule | Why |
  | --- | --- | --- | --- |
  | truth | `start_tempo_correct` (BPM **and** beat unit exact, at bar 1) | ≥ 0.95 | Stricter than exact BPM: ♩. = 110 read as ♩ = 110 plays 1.5× too slow |
  | truth | `mark_recall` | ≥ 0.90 | So a reader that finds only bar 1 cannot pass |
  | truth | `mid_page_bar_exact` (mid-score marks, bar counted from the top of the mark's page) | ≥ 0.90 | The app would place a mark among HOMR's measures for that page, so a wrong system elsewhere does not move it |
  | truth | `false_tempos_per_score` | ≤ 0.02 | |
  | control | `false_tempos_per_score` (unmarked scores) | ≤ 0.02 | `cresc.`, `rit.`, `a tempo` must not become tempos |
  | truth, control | worker `errors` | = 0 | |
  | truth, control | `peak_rss_mib` | ≤ 1024 | Phase 3 runs it after OMR on the user's machine |
  | truth, control | `seconds_per_page` (fresh OCR, no cache) | ≤ 5 | |

  On dev and dev-b, after tuning, OCR stood at: start tempo 1.00 and 0.95, recall 1.00 and 0.97,
  mid-page bar 0.98 and 0.92, no false tempos, about 186 MiB and 1.4 s per page. The library
  check (11 PDFs with a MuseScore MIDI) is run once after the test scoring and reported. It is not
  part of the rule.

## Phase 3 — Ship detection (committed 2026-10-21, with the play-by-default amendment)

*As built* ([report](../Research/omr/reports/song-tempo/phase3/REPORT.md)). The plan below put
detection in `song_entry.py` and its result in each package's `derived/`. Instead:
- the app runs `Bridge/tempo_marks.py` (the frozen reader, copied word for word, parity-checked);
- the result is kept once per source PDF in `songs\tempo-marks\`, so the 480 and 465
  conversions of a PDF share it, it survives re-conversion, and no bridge file changes;
- songs already in the library read their marks from the panel's READ PRINTED MARKS, without
  OMR;
- a page whose light grey staff lines the frozen layout cannot see is read again with lighter ink
  counted (3 library PDFs; no measured page is affected);
- after the user's check, printed marks **play by default** (user, 2026-10-21) unless the user
  set a tempo of their own: IGNORE stops a mark playing, RESET returns to the printed tempo, and
  `--read-printed-tempo` read every library PDF once.

As planned:

- Detection runs after OMR from `song_entry.py`'s package step, outside the pinned files. It
  writes `derived/tempo-detected.json` keyed by the `tempo_read.py` SHA, the OCR model hashes,
  the render DPI and the recognition identity. It is part of neither the recognition nor the
  interpretation key, so adding it re-converts nothing. Existing packages get it from a
  re-run, or from a separate opt-in pass that renders pages without running OMR.
- In the TEMPO panel, detected marks appear as "Detected ♩ = 110 at bar 1" with **Use** /
  **Ignore**. Accepted marks fill the user map, and the user's own edits always win. Tempo words
  are shown as suggestions only.
- Re-measure RAM and commit on the library's densest page before the release gate.

## Phase 4 — Tempo words as guesses (added 2026-10-21; not started)

*Effort: high.* Requested 2026-10-21 ("add tempo words as phase 4"). The user first said words
should "stay as hint" and floated a percentage change when a word appears, without deciding.
Phase 4 measures whether words can play safely, and ships only what passes.

**Why a phase of its own.** Words fix no BPM. Published ranges disagree widely: Moderato is
given as anywhere from about 86 to 126, Andante about 72 to 108, Adagio about 55 to 76, and
MuseScore's tempo-text presets are editable defaults, not a standard. A guess can therefore make
a song worse than 120, so it is measured before it plays.

**What the library holds (2026-10-21, all 61 PDFs read):** 11 PDFs print only words and 13
print nothing. About 35 word marks were found, most without a number: andante 4, presto,
allegretto, prestissimo and "Tempo I" 3 each, then allegro, adagio, lento, animato, rubato and
"a tempo" 2 each, and single moderato, maestoso, più mosso, meno mosso, più animato and mosso.
That is too few to tune on, so the table comes from a public corpus, and the library is only a
sanity check, as in Phase 2.

**Three kinds of word, three rules:**

| Kind | Examples | What plays | Why |
| --- | --- | --- | --- |
| Return | "a tempo", "Tempo I", "Tempo primo", "come prima", "l'istesso tempo" | The tempo it names: the one before the last relative change, the first tempo, or the same tempo | Exact whenever an earlier tempo is known; no guessing |
| Relative | "più mosso", "meno mosso", "più lento", "animato", "più animato", "calmando", "doppio movimento" | The tempo before it times a factor (for example 1.15 or 0.87; "doppio movimento" 2) | A factor guess on a known tempo; the factor table is measured |
| Absolute | Largo, Adagio, Lento, Andante, Andantino, Moderato, Allegretto, Allegro, Vivace, Presto, Prestissimo, with "molto", "assai", "con moto", "ma non troppo" | A BPM from the table, only where no number is printed at or before that bar | The weakest guess; it never overrides a printed number |

Not played: rit., accel., rubato and fermatas (curves and pauses stay out of scope), and
character words such as "Maestoso" or "Tranquillo" unless the corpus shows they carry a
consistent tempo.

**Research (unpinned code beside `tempo_read.py`; nothing pinned changes):**
- **Word truth.** A public MusicXML corpus whose scores print a tempo word and a metronome mark
  at the same bar (candidates: PDMX, the OpenScore Lieder and string-quartet sets), split by
  composer into dev and held-out, with its own manifest and SHA. The word gives the input, the
  printed number the truth. Relative factors come from the corpus's own consecutive numbered
  pairs around a relative word.
- **Reading the words.** Word recall on new seeded truth pages from the project's MuseScore
  generator (new `test-c` seeds, because Phase 2's test splits are spent), and false words on
  the unmarked controls.
- **Baselines.** Each guess is scored against what plays today: 120 for absolute words, no
  change for relative words.
- **Freeze before the held-out read** (thresholds proposed, set from dev):
  - absolute words: median |guess ÷ truth − 1| ≤ 0.15, and better than 120 on a paired test;
  - relative words: median factor error ≤ 0.10, and better than no change;
  - return words: exact on every seeded case;
  - word reading: recall ≥ 0.90, false tempo words ≤ 0.02 per score.
- **Library sanity check, not judged:** the 11 MIDI-paired songs and the words-only PDFs, start
  tempo against the MIDI where one exists.

**Ship (only what passes):**
- The word table lives in the app (`TempoWords.cs`, versioned), so the frozen reader and its
  per-PDF store stay as they are unless word reading itself needs a fix. A reader change changes
  `reader_sha256` and the store reads again.
- Precedence becomes: the user's map, then printed numbers, then return words, then passing
  word guesses, then the score's own marks, then 120.
- Guesses are labelled in the TEMPO panel ("Andante · GUESS ♩=…"), each with IGNORE, and they
  play by default only if their kind passed the rule. A kind that fails stays a hint, as now.
- Release gate, a library listing check (durations of the 11 words-only songs before and after),
  and the user's check.

## Recommended order

1. **Phase 1.** Fixes every song package at once with no OMR or pin change, and gives Phase 2 a
   place to land.
2. **Phase 2** as research, after Phase 1 or alongside its review.
3. **Phase 3** only on acceptance.
4. **Phase 4** (tempo words) only when the user starts it; it reuses Phase 3's reader and
   store.

Phase 6 of the MusicXML plan (library re-conversion) is independent. Songs it converts gain the
TEMPO panel automatically, and maps keyed by source SHA survive the re-conversion (start tempo
always, bar changes when the bar count matches).

## Verification

- **Per phase:** `Visualization_engine.Tests` and `Bridge/tests`, then one development song, then
  the full suites, then `powershell -ExecutionPolicy Bypass -File scripts\verify-release.ps1`
  for shipped phases, then a check in the relaunched `dist\Sheet2Play.exe`.
- **Regressions:** with no map set, playback is identical, and `audioOffsetSeconds` is unchanged.
  Commits carry no AI co-author trailers.

## Out of scope

- Editing pinned bridge files (`bridge.py`, `musicxml_normalizer.py`) or HOMR's title policy.
- Writing tempo into stored MusicXML. A later "Export MusicXML with tempo" can be its own request.
- Training an OCR model.
- rit./accel. curves and fermatas, which stay unplayed as in the MusicXML plan.
- Changing playback-rate behaviour.
- Tempo for legacy MIDI caches. They get it by being re-converted.

## Superseded from the 2026-10-19 draft

- **`ReadMidi` overlay on cached ticks:** song packages have no MIDI cache, so the hook is now
  `SongTimelineOptions` / `BuildTempoMap`.
- **`Bridge/bar_map.py` sidecar, `SHEET2PLAY_BARS:` stderr transport and `<midi>.bars.json`:**
  retired, because `measures` + `play_order` are the bar map.
- **Store changes by printed bar number:** replaced by measure index, because HOMR's printed
  numbers restart on every page.
- **TEMPO button in the crowded header near `DrawPlaybackRateControl`:** replaced by the
  bottom-left panel stack.
- **Separate start-tempo and bar phases:** merged into Phase 1.

Kept from the draft: overlays rather than cache rewrites, no default `<sound tempo>`, no OCR
accuracy claims from the existing sets, and rapidocr title detection not treated as a tempo
reader.
