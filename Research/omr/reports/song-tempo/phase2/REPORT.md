# Per-song tempo, Phase 2: reading printed tempo marks

**Plan:** [`2026-10-19-song-tempo`](../../../../../plans/archive/2026-10-19-song-tempo.done.md), Phase 2 (research only).
**Requested:** 2026-10-21 ("push it and start phase 2"). Note-unit tuning ("tune the note unit
first") and the freeze and test scoring ("ok proceed with the next phase") were requested the same day.
**Verdict:** **accepted**. The OCR reader passes every pre-registered check on test and test-b,
which were scored once ([`verdict.json`](verdict.json), [`freeze.json`](freeze.json)).
Nothing shipped. Phase 3 needs its own request.

## What was built

- **Tempo-truth set** (`tempo_truth.py`): the displacement ruler's exact labels (dev, dev-b, test,
  test-b, same composer splits), with seeded `<metronome>` marks and tempo words injected and
  re-engraved with MuseScore 4.6.5. 154 scores, 345 metronome marks, 0 failures. The unmodified
  scores are the control set. Frozen as [`truth-manifest.json`](truth-manifest.json).
- **Reader** (`tempo_read.py`), two candidates:
  - `ocr`: render at 300 DPI, find staves, systems and barlines by projection, and run rapidocr on
    the strip above each system. The beat unit comes from the glyph left of "=": an enclosed head
    is a half, a flag is an eighth, and a small square blob level with the head is a dot. The bar
    is the mark's x position against its system's barlines.
  - `text`: the PDF's own text layer, where MuseScore writes SMuFL note code points. Only 14 of
    the 61 library PDFs have one.
- **Scoring:** `score` per run and `verdict` for the frozen rule, pooled over the test splits.
  Unit tests: `tests/test_tempo_read.py` (9).

## Tuning on dev and dev-b (before the freeze)

| Step | Change | Effect |
| --- | --- | --- |
| Layout | Ledger lines kept out of staff detection, beams lying along staff lines filtered, barlines broken by text kept (gap coverage 0.7, swept), start-repeat signs, short last systems | 99.0% of systems exact |
| Embedded marks | Metronome marks inside words ("Andante (♩ = 80)") parsed | Text reader recall 1.00 |
| OCR settings | Long side capped at 2400 px instead of upscaling the short side | Same text in half the time |
| Note unit | Hollow head from an enclosed hole (flood fill), not ink fraction. A dot must be square and level with the head | OCR unit 95.7% → 100% (dev), 93.9% → 100% (dev-b) |

At the frozen code, OCR on dev / dev-b: start tempo 1.00 / 0.95, recall 1.00 / 0.97, mid-page bar
0.98 / 0.92, no false tempos on either truth or control.

## Test result (scored once, frozen reader `022d7828…`)

| Check (pooled test + test-b) | Rule | OCR | Pass |
| --- | --- | --- | --- |
| Start tempo correct (BPM and unit) | ≥ 0.95 | 0.979 (93 of 95) | yes |
| Mark recall | ≥ 0.90 | 0.963 (210 of 218) | yes |
| Mid-score marks on the right bar (page-relative) | ≥ 0.90 | 0.974 (114 of 117) | yes |
| False tempos per score, truth | ≤ 0.02 | 0 | yes |
| False tempos per score, control | ≤ 0.02 | 0 | yes |
| Worker errors | = 0 | 0 | yes |
| Peak memory | ≤ 1024 MiB | 187 MiB | yes |
| Seconds per page (fresh OCR) | ≤ 5 | 1.34 | yes |

Per split, OCR / text:

| | test OCR | test text | test-b OCR | test-b text |
| --- | --- | --- | --- | --- |
| Mark recall | 0.957 | 0.978 | 0.968 | 1.000 |
| Mark precision | 1.000 | 0.978 | 1.000 | 1.000 |
| BPM exact (matched) | 1.000 | 0.989 | 1.000 | 1.000 |
| Unit exact (matched) | 0.989 | 0.989 | 0.992 | 1.000 |
| Start tempo correct | 0.976 | 0.976 | 0.982 | 1.000 |
| Mid-score page bar exact | 0.958 | 0.940 | 0.986 | 0.986 |
| False tempos per score (truth) | 0 | 0.05 | 0 | 0 |
| Seconds per page | 1.40 | 0.10 | 1.27 | 0.09 |

**OCR failures on test (17 of 218 marks):**
- 8 missed outright:
  - 3 sit beside tempo words ("Poco meno mosso", "Più animato").
  - 3 are on one score with a long footnote, which lost all its marks.
  - 2 are plain marks.
- 7 marks one bar off, from the barline step, not OCR.
- 2 unit errors (a quarter read as an eighth, and the reverse).
- No wrong BPM numbers and no invented tempos.

Tempo-word suggestions (not judged) found 67% and 54% of printed words.

## Library check (once, after the test; not part of the rule)

The 11 library PDFs that have a MuseScore MIDI of the same name. Song names stay in the
gitignored `library/` folder.

- **Start tempo:** OCR matches the MIDI's first tempo on 8 of 11 songs. The text layer matches on
  2, because 9 of the 11 have no text layer.
- **The three mismatches are not misreads:**
  - Two scores print no metronome mark (one only "Presto agitato"), so the MIDI's 120 is
    MuseScore's default. OCR rightly reports nothing.
  - One prints a range, "♩ = 117–130". The reader took 117 and the MIDI used 120.
- **Changes:** 11 of the MIDI's 43 per-song distinct tempo values were found, with 1 extra (the range
  above). Most of the MIDI's other values are ritardandos and fermatas that no printed mark
  states.
- **The plan's example song:** the reader found ♩ = 110 at bar 1 and ♩ = 186 at bar 25. The
  bar-17 change is printed as **"♩ = ♩."** (a metric modulation) with no number, so the reader
  cannot read it, and the truth set never contained one.
- Peak commit 33%, 98 s for all 11.

## What this means for Phase 3

- OCR is good enough to propose a start tempo and numbered changes with **Use** / **Ignore**.
  In these tests it never invented a tempo, and its errors were misses or a bar off by one, which
  the panel shows for the user to fix.
- Known gaps a Phase 3 should show rather than hide:
  - Metric modulations ("♩ = ♩.") are not read.
  - Ranges ("117–130") are read as their first number.
  - About 4% of marks are missed.
- Cost after OMR: about 1.3–1.4 s per page and under 200 MiB.

## Files

- Code: `Research/omr/tempo_truth.py`, `tempo_read.py`, `tests/test_tempo_read.py`
- Tracked evidence: `truth-manifest.json`, `engraved.json`, `freeze.json`, `verdict.json`, each
  run's `run.json` and `score.json` under `runs/` (`runs/dev/` and `runs/test/` are the
  frozen-code runs; the others are pre-freeze history), drivers `run-ocr-dev.sh` and
  `run-phase2.sh`, console logs
- Local only (gitignored): `jobs/` (supervisor receipts), `library/`, `ocr-cache/`, every
  `rows.jsonl`
