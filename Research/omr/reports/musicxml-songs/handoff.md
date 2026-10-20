# MusicXML songs: handoff

**Owning plan:** [`2026-10-19-musicxml-songs`](../../../../plans/2026-10-19-musicxml-songs.md)
**Phase status:** Phase 1 **complete and accepted** on 2026-10-19 ([report](phase1/REPORT.md)),
committed as `af0332b`. Phase 2 requested the same day ("ok commit phase 1 and continue with
phase") and **accepted**: every criterion met, release gate 8 of 8 ([Phase 2 report](phase2/REPORT.md)).
Phase 3 requested the same day ("commit phase 2 then continue with the next phase"),
**accepted** (gate 8 of 8, [Phase 3 report](phase3/REPORT.md)) and committed after the panel was
made collapsible at the user's suggestion. Phase 4 requested the same day ("after that commit phase 3
then continue with the next phase").
**Phase 4a:** done the same day, no shipped change ([Phase 4a report](phase4a/REPORT.md)): the managed
SFZ player passes every measurable criterion; sfizz is unmeasured pending a download approval.
Committed as `ef02e4b` on 2026-10-20. The user then chose **both pianos** in the PIANO selector
("for testing keep implementing both"; some may be removed later on performance), and approved the
sfizz comparison ("if the zip doesn't contain anything useful don't keep chasing").
**sfizz comparison (2026-10-20, done):** same sound as the managed player, but 8 and 52 late
blocks at 1.0x and 2.0x on the densest song (managed: 0 and 0), twice the CPU, and live disk
streaming that falls behind. Not pursued ([4a report](phase4a/REPORT.md#sfizz-comparison-2026-10-20)).
**The user then picked the "2 Salamander" renders** (managed player with reverb) and requested 4b
the same day ("my choice would be those with the 2's ... you can continue phase 4").
**Phase 4b (2026-10-20): shipped, sound approved, committed** ([report](phase4b/REPORT.md)): Salamander through
the managed player as the default piano (YDP and the MIDI device still selectable), audio on its own
thread, PIANO row with attribution, `scripts\install-piano.ps1` (pinned content hash), installed on
this machine from the local copy. Densest song in the published app: 0 underruns at 1.0x and 2.0x,
commit +3.2 MB, load 0.10 s; xunit 149; gate 8 of 8. The user approved the sound and the commit
on 2026-10-20 ("i checked the audio is realy nice i mean salamander ... i approve the commits").
The by-ear sync check was not reported separately and stays open.
**Phase 5 requested 2026-10-20** ("then we can begin phase 5"), with two removals added in the same
message: drop the MIDI device so only the two pianos remain ("we can remove midi synth one let it be
only 2 pianos"), and show only HOMR 480 and 465 in the frontend ("remove model 426 and zeus"; the
backend is left to judgement). **Shipped, not committed** ([Phase 5 report](phase5/REPORT.md)): two
engine cards and two piano cards, 426 and Zeus kept in the backend, bar lines and readout, pedal
lane, staff colours, badges, Export MIDI, Export MusicXML and Re-convert; xunit 163; gate 8 of 8.
**Next authorized action:** the user checks Phase 5 in `dist\Sheet2Play.exe` and approves the
commit. The C# engine rework and Phase 6 each need their own request; the user wants the rework at
the end of the plan, before Phase 6.
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

## Job record: 30 songs with HOMR 480 and the timing fix (2026-10-20)

Requested by the user after the Phase 5 feedback ("i request a 20-30 songs not all i have to be
converted with timing fix+480"; "you pick 30"). Not Phase 6: a chosen subset, through the app's own
conversion path.

- **Command** (working directory: repository root):
  `tmp\batch-app\Sheet2Play-batch.exe --convert-batch tmp\batch-480\songs.txt tmp\batch-480\journal.jsonl`
  (`--engine homr480` and the timing fix are the defaults). The exe is a renamed copy of the
  published `dist` (gate 8 of 8, xunit 170), so the release gate, which stops every `Sheet2Play`
  process, does not stop the batch.
- **Inputs:** `tmp\batch-480\songs.txt`, 30 named PDFs in `%LOCALAPPDATA%\Sheet2Play\songs\pdf` with no
  HOMR 480 package, shortest first (about 165 pages). Library writes: one package per song under
  `songs\scores\homr480`, as an app conversion writes it.
- **Safeguards:** one song at a time; each page runs in the pipeline's supervised worker; before each
  song the batch stops, resumable, at 85% RAM or commit or under 4 GiB of commit left.
- **Progress and resume:** `tmp\batch-480\journal.jsonl` (one line per attempt) and
  `tmp\batch-480\run.log`. Rerunning the same command skips every song already converted; check that
  no `Sheet2Play-batch` process is running first.
- **Result (finished the same day):** 30 of 30 converted, 0 failed, 66.8 minutes of recognition;
  every entry is a package with the timing-fix interpretation and its `score.musicxml`. The library
  now has 39 HOMR 480 packages. The thinnest result is "Blinding Lights" (1 page, 101 notes), worth
  a listen. No memory stop was hit.

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
