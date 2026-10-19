# MusicXML songs: handoff

**Owning plan:** [`2026-10-19-musicxml-songs`](../../../../plans/2026-10-19-musicxml-songs.md)
**Phase status:** Phase 1 **complete and accepted** on 2026-10-19 ([report](phase1/REPORT.md)),
committed as `af0332b`. Phase 2 requested the same day ("ok commit phase 1 and continue with
phase") and **accepted**: every criterion met, release gate 8 of 8 ([Phase 2 report](phase2/REPORT.md)).
Phase 3 requested the same day ("commit phase 2 then continue with the next phase"),
**accepted** (gate 8 of 8, [Phase 3 report](phase3/REPORT.md)) and committed after the panel was
made collapsible at the user's suggestion. Phase 4 requested the same day ("after that commit phase 3
then continue with the next phase").
**Next authorized action:** Phase 4a, the SFZ decision spike (no shipped change); 4b waits on the
user's pick. The user wants any C# engine rework as a separate request at the end of the plan, before
Phase 6.
**Phase 3 evidence:** [`phase3/tempo/summary.json`](phase3/tempo/summary.json) (fixture exact
against MuseScore 4; corpus exact up to the first fermata or "rit."); `--verify-library` with
expression off identical for all 90 playing songs (local, `phase3/library-after`); xunit 139
passed, 22 of them in `ExpressionTests`.
**Phase 2 evidence:** 3 fresh 480 conversions equal their bridge notes (0.0000 ms); the timing fix
re-interprets in 1.37 s with no OMR; all 85 previously playing library songs still play; xunit 117
passed. Evidence that lists private library paths stays local (`phase2/library-*`, `convert-*`).
**Acceptance evidence:** [`phase1/summary.json`](phase1/summary.json): parity 292/292 recognitions
without repeats (and the 14 with repeats exact once expansion is off), feature counts 207/207 labels,
100/100 repeatable, 306 combined scores open under the refined MuseScore rule, 3.2 s and 82 MiB for
the largest score, pinned files unchanged. Full Python suites: 476 passed, 2 skipped.

## Phase 1 — what exists

- `Bridge/song_model.py` (new, unpinned): pages or an import → `performance.json` (schema 3)
  and a combined `score.musicxml`. Reuses the pinned normalizer's parsing and `_page_advance`,
  and `timing_correction.lay_out` on its own unexpanded reading of each page.
- `Bridge/song_entry.py` (new, unpinned): wraps `bridge.normalize_musicxml` to keep each page,
  runs `bridge.main` unchanged, and writes a song package (`recognition.json`, `pages/`,
  `derived/<interpretation key>/`). Not called by the app yet; Phase 2 wires it in.
- `Bridge/tests/test_song_model.py`: 25 tests, passing under the research venv (music21 9.9.1)
  and the app's HOMR venv (music21 10.5.0).
- `Research/omr/song_model_check.py`: the acceptance check over the corpus.

## Job record: full acceptance check

- **Command** (working directory: repository root):
  `Research\omr\.venv\Scripts\python.exe -B Research\omr\guarded_execution.py --output Research\omr\reports\musicxml-songs\phase1\jobs\check-3 --max-seconds 10800 -- Bridge\.venv-homr-gpu\Scripts\python.exe -I -B Research\omr\song_model_check.py`
- **Inputs:** cached recognitions under `Research/omr/data/displacement-ruler/captures/{homr465,homr480-ab369ac}`
  for the dev, test, dev-b and test-b manifests, and every `Research/omr/data/displacement-ruler/*/label.musicxml`.
  No inference; MuseScore 4 CLI (`C:\Program Files\MuseScore 4\bin\MuseScore4.exe`) opens each combined score.
- **Code identity** (SHA-256 prefixes at launch; repository at `237e398` plus uncommitted Phase 1 files):
  `song_model.py` c6adf8d16d5c64af, `song_entry.py` ad767c8554f985ec, `timing_correction.py`
  efb65a6d383c4342 (unchanged), `song_model_check.py` 967ea881e9ae450b.
- **Outputs:** `phase1/rows.jsonl` (one row per finished item; a rerun skips finished rows, so it
  resumes), `phase1/summary.json` (acceptance), supervisor receipt and log in `phase1/jobs/check-3/`.

### Interrupted first run (`jobs/check-1`), kept as evidence

Launched 11:37 with `song_model.py` 5046145bf45620dc and `song_model_check.py` 072e1f668a6cbeb0;
stopped by me at 163 rows (homr465 recognitions only) because the code had to change: a malformed
`<duration>` or `<divisions>` aborted the XML pass, and the MuseScore check treated MuseScore's
corruption refusal as a fault of the combined score. MuseScore's log shows the refusal is HOMR's
own incomplete measures ("Incomplete measure … Found: 3/8. Expected: 3/4"), which the source pages
carry too; with `-f` they open. Up to the stop, no score without repeats failed parity. The
supervisor (PID 17044) and its worker were confirmed gone before I removed its own
`.research-worker.lock`. Partial rows: `jobs/check-1/rows-interrupted.jsonl`.

### Interrupted second run (`jobs/check-2`), kept as evidence

Launched 11:56 with `song_model.py` 891a97ece913d896; stopped by me at about 80 rows because one
combined score (6000428, 465) was refused by MuseScore while all its pages open. Its first page has
two parts and the others one, and the measure rests I padded the missing part with took their
length from HOMR's `<duration>` values, which disagree with the note types MuseScore measures by.
Padding now uses empty measures (readers fill them with rests), and a part missing from the first
page opens with its first real measure's attributes. A pre-check of all 7 recognitions whose pages
differ in part count then showed MuseScore crashing (0xC0000005) on 6573780 (465) at random, on the
raw page 2 as often as on the combined score; the check now forces open the pages too before
blaming the combined score. Supervisor PID 20636 confirmed gone before I removed its lock.
Partial rows: `jobs/check-2/rows-interrupted.jsonl`.
