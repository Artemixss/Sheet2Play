# Per-song tempo, Phase 3: printed tempo marks in the TEMPO panel

**Plan:** [`2026-10-19-song-tempo`](../../../../../plans/archive/2026-10-19-song-tempo.done.md), Phase 3.
**Requested:** 2026-10-21 ("ok commit and push proceed with phase 3"; then "finish the to do lists
then i will check after that commit and push").
**Status:** the USE / IGNORE version was checked by the user and committed (`30bcbff`). The user
then made printed marks play by default ([amendment](#amendment-printed-marks-play-by-default)),
which is shipped (release gate 8 of 8), checked by the user ("it works commit and push") and
committed.

## What ships

- **`Bridge/tempo_marks.py`**: the Phase 2 OCR reader, its layout, OCR strip, beat-unit and bar
  functions copied word for word from the frozen `tempo_read.py` (`022d7828…`). Shipped SHA
  `a04b8f16…`. Two differences from the research file:
  - no OCR cache on disk;
  - a fallback for light staff lines, described below.
  No pinned bridge file changed, and nothing joins a recognition or interpretation key, so no
  song is re-converted.
- **Where it runs:**
  - After every new PDF conversion, before the song opens (progress "Reading printed tempo
    marks"). A failure is logged and the conversion goes on.
  - For songs converted earlier, from **READ PRINTED MARKS** in the TEMPO panel. It reads the
    library's copy of the PDF, found by hash, in the background at below-normal priority, and
    shows "READING MARKS · PAGE n OF m".
- **Where results live:** `songs\tempo-marks\<source sha>.json`, one per PDF. A file counts only
  for the reader SHA that wrote it, so a changed reader offers READ PRINTED MARKS again.
- **Bars:** a PDF conversion has one HOMR page per PDF page, so a mark's bar is its page's first
  bar plus its place on the page, held within the page's bars. When the conversion's pages
  differ from the PDF's, the mark is listed as "PAGE n · NOT IN THIS CONVERSION'S PAGES" and
  cannot be used.
- **The panel:**
  - **PRINTED · N** lists the marks above the bar changes: bar, tempo and any printed words
    ("Calmando ♩. = 74").
  - Each mark has **USE**, which takes it into the song's tempo map (the first bar's sets the
    start tempo; elsewhere it replaces any change at that bar), and **IGNORE**, which is kept in
    `tempo-maps.json` under `ignored_marks`.
  - The header row has **USE ALL**, **READ AGAIN** and **SHOW n IGNORED**.
  - A tempo word without a number is shown as a hint only.
  - A mark already in the map shows **PLAYING**.
  - Nothing changes what a song plays until USE.
- **The TEMPO button:** a song still on the 120 default whose PDF prints a tempo reads
  "DEFAULT · MARK FOUND", so the panel need not be opened to learn it.
- **`--detect-tempo PDF STORE [PERFORMANCE]`:** runs the same path from the command line into a
  store other than the user's.

## Evidence

**Parity with the frozen reader** ([`parity/parity.json`](parity/parity.json), reader
`a04b8f16…`):
- Every mark's page, system, page bar, BPM, beat unit, text, words and suggestion, and every
  page's bar count, are identical to the frozen runs.
- That holds on all 120 dev and dev-b scores (truth and control) and on 11 of 11 library songs of
  the Phase 2 library check.
- `Research/omr/tests/test_tempo_marks.py` checks the copied functions word for word and the
  restated constants.
- The earlier run of reader `9a6e0901…`, before the fallback, was identical too
  ([`parity-before-light-ink/`](parity-before-light-ink/parity.json)).

**Light staff lines** ([`survey/survey.json`](survey/survey.json)):
- The frozen layout counts pixels darker than 128 (of 255) as ink. 3 of the 61 library PDFs draw
  staff lines lighter than that (27 of 285 pages), so it found no staff and read nothing.
- `tempo_marks.py` therefore reads such a page again with pixels darker than 200 counted as ink.
  That finds staves on all 27 pages.
- No page of the measured sets lacked staves (866 dev and test pages), so the fallback cannot
  change any Phase 2 result.
- On the 3 PDFs, checked by eye against the pages (they have no MIDI pair):
  - One gets both its marks right (♩ = 110 at bar 1, ♩ = 125 at bar 9).
  - One correctly has no mark.
  - One, a low-resolution scan scaled up about 3×, has its 100 right but its quarter read as an
    eighth. Its 6-pixel stem looks like a flag to the frozen glyph check.
  - The panel draws the unit, so that error is visible and one click on the unit fixes it.

**The user's example song**, through the published exe: `--detect-tempo` read ♩ = 110 at bar 1
and ♩ = 186 at bar 25, in 15.2 s for 11 pages. Those are the two numbered marks of the map the
user typed in Phase 1. The bar-17 change is printed as "♩ = ♩." with no number and is not read,
as Phase 2 found.

**Memory and time on the library's densest PDFs** (supervised, fresh process each,
`tempo_marks_memory.py`):

| PDF | Pages | Seconds | Peak working set | Peak private (commit) | System commit peak |
| --- | --- | --- | --- | --- | --- |
| Most pages (13 pages, all light ink) | 13 | 13.6 | 373 MiB | 836 MiB | 34.1% |
| Largest file (2.3 MB) | 12 | 14.7 | 366 MiB | 828 MiB | 34.2% |

Phase 2's 187 MiB was the resident size sampled between scores. These are the process peaks,
which include onnxruntime's arenas while a strip is read. The reader is its own process and gives
all of it back when it exits.

**Tests and gate:**
- xunit 199 of 199. The 6 new tests cover placing marks across pages, mismatched pages, USE and
  PLAYING, a stale reader or PDF, ignored marks and the file written as before, and a conversion
  whose reading fails.
- Research reader tests 9 of 9; parity tests 3 of 3; bridge tests 65 ran, OK (2 skipped).
- Release gate `scripts\verify-release.ps1`: 8 of 8.
- The new snapshot `07-playback-tempo-printed` shows the list. In `07-playback-tempo` the start
  row gains READ PRINTED MARKS between RESET and "+ CHANGE AT BAR 2"; nothing else moved.

## Amendment: printed marks play by default

The user, 2026-10-21, after checking the USE / IGNORE version: "i want is this tempo change to be
the default so apply this tempo change to my all songs".

- **Precedence** (`Program.Tempo.cs` `TempoFor` and `StoredTempo`, and the library durations in
  `SongCache.cs`): the user's own map, then the PDF's printed marks, then the score's marks, then
  120.
- **The printed map** (`TempoDetection.PrintedMap`) takes in every usable mark the user did not
  ignore, as USE would. A PDF that prints a change but no starting tempo starts at 120.
- **The panel:**
  - The button reads "TEMPO ♩=110 · PRINTED", plus the number of changes.
  - Printed rows show PLAYING and keep IGNORE, which stops a misread mark playing.
  - RESET returns to the printed tempo; any edit starts the user's map from what plays.
  - The session re-times when marks are read or ignored.
  - The library's "· tempo" tag still means a tempo the user set.
- **Every library PDF read once:** `dist\Sheet2Play.exe --read-printed-tempo` (`jobs/library-read-1`,
  296 s, peak system commit 46%) read 44 PDFs; 17 were read already, and none failed. Of the 61:
  - 37 print tempo numbers (36 at bar 1) and now play them;
  - 11 print tempo words only ("Andante", "Presto", "Tempo I"…);
  - 13 print neither.
- **Tests:** 2 more, 201 of 201. One builds the printed map; the other checks that a listed
  song's length follows its printed tempo until the user sets one, and returns to 120 when the mark
  is ignored. Release gate 8 of 8.

## Deviation from the plan

The plan put detection in `song_entry.py`'s package step, writing `derived/tempo-detected.json`
inside each package.

Instead the app runs the reader, and keeps one result per source PDF in the library, because:
- detection depends only on the PDF;
- the HOMR 480 and 465 conversions of one PDF then share one result, which survives
  re-conversion;
- no bridge file changes;
- songs already in the library get marks from the panel without re-running OMR.

The identity the plan listed is all recorded in the result: reader SHA, OCR model hashes and
settings, DPI and source SHA. The bar mapping uses the conversion's own pages each time the panel
lists the marks.

## Known limits

- Marks printed as an equation of notes ("♩ = ♩.") are not read.
- A range ("♩ = 117–130") is read as its first number.
- About 4% of printed marks are missed (Phase 2 test).
- Bars can be one off where the layout miscounts barlines; the panel shows the bar, and the
  change can be moved by deleting it and adding it at the right bar.
- Low-resolution scans can have the beat unit misread, as above.

## Files

- Shipped:
  - `Bridge/tempo_marks.py`
  - `Visualization_engine/TempoDetection.cs`, `Program.Tempo.cs`, `Program.TempoVerification.cs`
  - the hook in `SongCache.Packages.cs` and the `tempo_marks` progress stage in `OmrProgress.cs`
  - `ignored_marks` in `TempoMapStore.cs`
  - the snapshot in `Program.Smoke.cs`
- Research: `Research/omr/tempo_marks_parity.py`, `tempo_layout_survey.py`,
  `tempo_marks_memory.py`, `tests/test_tempo_marks.py`, driver `run-checks.sh`.
- Tracked evidence: `parity/parity.json`, `parity-before-light-ink/parity.json`,
  `survey/survey.json` (counts only), console logs.
- Local only (gitignored): `jobs/`, `library/` and the nested `*/library/` folders, which name
  songs.
