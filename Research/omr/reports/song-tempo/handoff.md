# Per-song tempo: handoff

**Owning plan:** [`2026-10-19-song-tempo`](../../../../plans/2026-10-19-song-tempo.md)
**Phase status:**
- **Phase 1** shipped and committed 2026-10-21 (`9bd66f9`, [report](phase1/REPORT.md)). "Beyond
  This Station" with the user's map plays 298.82 s against the MuseScore MIDI's 298.82 s. With no
  map, all 129 playing library songs give identical events.
- **Phase 2** (research) is **accepted, not committed** ([report](phase2/REPORT.md)). The frozen
  OCR reader passed every pre-registered check on test and test-b, scored once: start tempo 0.979,
  recall 0.963, mid-score bar 0.974, no false tempos, 187 MiB, 1.34 s per page.

**Next authorized action:** the user checks the Phase 2 report and approves the commit. Phase 3
(detected marks in the TEMPO panel, with Use / Ignore) needs its own request.

## Phase 2 (requested 2026-10-21, "push it and start phase 2"): accepted

Research only, no shipped change. Phase 1 was approved and committed (`9bd66f9`) and pushed the
same day.

### Job record: tempo-truth build

- **Command** (working directory: `Research/omr`):
  `.venv\Scripts\python.exe -B guarded_execution.py --output reports\song-tempo\phase2\jobs\build-1 --max-seconds 3600 -- .venv\Scripts\python.exe -B tempo_truth.py build`
- **Inputs:** the frozen manifests `reports/displacement/phase1/manifest.json` (dev, test) and
  `phase3b/manifest.json` (dev-b, test-b), which are read only. Each item's
  `data/displacement-ruler/<id>/piano.musicxml` is checked against its frozen hash. MuseScore 4.6.5.
- **Outputs:** `data/tempo-truth/<id>/` (marked MusicXML, PDF, label, `truth.json`) and
  `reports/song-tempo/phase2/engraved.json`. One record per item; a rerun skips finished items,
  so it resumes.
- **Safeguards:** the supervisor (85% RAM/commit stops, deadline), and one MuseScore job at a time.
- **Result:** the first attempt (`jobs/build-1`) refused to start, because the supervisor runs
  from the repository root and the interpreter path was relative. The rerun with absolute paths
  (`jobs/build-2`) built 154 of 154 in 365 s, with 345 metronome marks. Frozen as
  `truth-manifest.json` (`tempo_truth.py freeze`).

### Job record: OCR development reads

- **Command** (working directory: `Research/omr`): `bash reports/song-tempo/phase2/run-ocr-dev.sh 1`.
  It runs `tempo_read.py read --candidate ocr` for dev and dev-b, on the truth and control sets,
  each under the supervisor (`jobs/ocr-<split>-<set>-1`, 7,200 s deadline), then `score`.
- **Outputs:** `runs/ocr-<split>-<set>/rows.jsonl` (one row per score, so a rerun resumes) and
  `score.json`. Console: `ocr-dev-1.console.txt`.
- **Code:** `tempo_read.py` as of the 0.7 gap threshold and the OCR no-upscale setting. Every run
  records its own SHA in `run.json`.
- **Attempt 1 (tag 1), stopped by me** partway through dev truth. I changed the layout code while
  it ran, and later runs would have loaded the new code under one recorded hash. The driver
  started the next run each time I stopped one, so I stopped the whole tree (bash driver,
  supervisors, workers). I confirmed no `tempo_read` or `guarded_execution` process was left and
  no lock was present, and deleted its partial `runs/ocr-*` directories. Its receipts remain in
  `jobs/ocr-*-1`.
- **Attempt 2 (tag 2)** started after the layout reached 99.0% exact systems on dev and dev-b. OCR
  results are cached per strip in `ocr-cache/`, keyed by PDF hash, page, box and settings, so a
  rerun after a parsing change does not repeat OCR. All four runs were **blocked** at admission:
  attempt 1's stopped supervisor (PID 25640, `jobs/ocr-dev-control-1`) had left
  `.research-worker.lock` at the repository root. I confirmed PID 25640 was gone and no related
  process was running, then removed the lock.
- **Attempt 3 (tag 3)** is the same code as attempt 2. All four runs completed (194, 186, 77 and
  77 s). OCR matched text on finding marks, with no false tempos, but the beat unit was wrong 6
  times: 3 false dots (a speck of a barline below the note), 2 halves read as quarters (the head's
  ink fraction sat on the 0.45 cutoff), and 1 eighth read as a half (the fill was measured on the
  flag side of the stem). Those runs are kept as `runs/ocr-*.before-unit-fix/`.
- **Attempt 4 (tag 4), the note-unit fix** (user, 2026-10-21: "tune the note unit first"). Tuned on
  dev and dev-b only. A half is now an enclosed head (flood fill), and a dot must be roughly square
  and level with the head. Unit tests: `UnitGlyphTests`. The OCR text comes from the cache, so only
  the glyph step reruns. Console: `ocr-dev-4.console.txt`. All four runs completed. The unit is now
  exact on every matched mark (dev 95.7% → 100%, dev-b 93.9% → 100%), and the start tempo is
  correct on dev 95% → 100% and dev-b 90% → 95%. No false tempos on the controls. The seconds per page
  in these runs are cache hits; real OCR cost is attempt 3's 1.3–1.5 s per page. What remains:
  five bars off by one, from the layout and shared with the text reader, and one OCR miss on
  dev-b (6018965, a small "♩ = 41" crowded by accents above high notes: OCR returns no box there).

### Job record: freeze and test scoring

- **Request:** user, 2026-10-21: "ok proceed with the next phase", read as Phase 2's remaining
  step (thresholds, freeze, test once, library once). Phase 3 waits for the verdict.
- **Rule:** pre-registered in the plan (Phase 2, "Pre-registered rule") before any test read. A
  `verdict` subcommand, added before the freeze, judges it from the run folders.
- **Dev runs at the frozen code:** `bash reports/song-tempo/phase2/run-phase2.sh dev 1` (working
  directory `Research/omr`), into `runs/dev/<candidate>-<split>-<set>/`, receipts
  `jobs/dev-*-1`, console `dev-final-1.console.txt`.
- **Freeze:** `tempo_read.py freeze --candidate ocr --runs runs/dev/* --rule <the plan's rule as JSON>`
  writes `freeze.json`. `read` refuses a test split unless `tempo_read.py` and `tempo_truth.py`
  match it.
- **Test, once:** `bash reports/song-tempo/phase2/run-phase2.sh test 1` into `runs/test/`, then
  `tempo_read.py verdict --truth runs/test/ocr-test-truth runs/test/ocr-test-b-truth --control
  runs/test/ocr-test-control runs/test/ocr-test-b-control --out verdict.json`. A rerun of an
  interrupted test run resumes its rows; it never re-reads a finished item.
- **Result:** dev runs completed, 8 of 8. Frozen 2026-10-21T11:44:43Z (`tempo_read.py` `022d7828…`).
  The test runs completed, 16 of 16 supervised jobs, all exit 0, with no pressure stop. The verdict
  was **ACCEPTED**, every check passing. The library check ran once
  (`jobs/library-1`, 98 s, peak commit 33%): OCR start tempo matches the MIDI on 8 of 11, and the
  other three print no number or a range. Details are in [the report](phase2/REPORT.md).

## Where things are

- **Code:**
  - `Visualization_engine/TempoMapStore.cs`: the model, the store, and `SongTempoMaps` (override,
    seeding from the score, bar names)
  - `Visualization_engine/TempoInput.cs`: rules and the typed field
  - `Visualization_engine/Program.Tempo.cs`: the panel
  - `TempoOverride` in `SongPerformance.cs`
- **User data:** `%LOCALAPPDATA%\Sheet2Play\tempo-maps.json`, created on the first edit. None exists
  yet on this machine.
- **Evidence:**
  - tracked: [`phase1/summary.json`](phase1/summary.json)
  - local: `phase1/library-*/` and `phase1/timeline/`, which hold private paths and are gitignored,
    and `phase1/bench.log` and the two snapshots, which are ignored by the reports' `*.log` / `*.png`
    rules

## Rerunning the checks

- **Tempo against the MIDI** (working directory: repository root):
  `dist\Sheet2Play.exe --verify-timeline <package>\derived\<key>\performance.json "<library>\songs\midi\custom\HOYO-MiX, Mika Kobayashi - Beyond This Station.mid" out.json --tempo 110q,17=110q.,25=186q`
- **No-map regression:** run `--verify-library <new dir>` with two builds and compare the rows'
  `PlainEventsSha256` and `ExpressedEventsSha256`. The baseline was `HEAD` exported with `git archive`
  (a worktree fails on long research paths), with the new `Program.Verification.cs` copied in.
