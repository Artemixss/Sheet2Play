# Per-song tempo, Phase 4: tempo words

**Plan:** [`2026-10-19-song-tempo`](../../../../../plans/2026-10-19-song-tempo.md), Phase 4.
**Requested:** 2026-10-21 ("add tempo words as phase 4"); started 2026-10-22 ("ok proceed with phase 4").
**Status:** research finished, **not accepted**: no word plays by default. The user then chose option 2
([section 5](#5-shipped-return-words-as-hints-with-use)), shipped 2026-10-22, checked by the user and committed. PDMX download deferred until the user has internet access.

## 1. Corpus for absolute and relative words: too few pairs

A word's tempo can only be learned from scores that print the word *and* a number at the same bar.

- **PDMX** (about 250k MuseScore scores, CC BY 4.0) was proposed; the user declined the 2.2 GB download.
- **OpenScore Lieder** (1,352 MuseScore files, CC0) was already on disk from earlier OMR work. The user chose
  it, with "if theres too few pairs we go back with option 1".

The bar for "enough" was set before any tempo value was looked at: at least 150 pairs, and at least 6 words
with 10 or more pairs each. [`tempo_word_pairs.py`](../../../tempo_word_pairs.py) →
[`word-pairs.json`](word-pairs.json):

| Count | Value |
| --- | --- |
| Visible word + number pairs in one bar | 222 |
| Words with 10 or more pairs | **4** (andantino 13, allegro 13, allegretto 11, moderato 10) |
| Relative words with a printed number before them | 18, nearly all one-off phrases |
| Hidden tempo marks (playback only, skipped) | about 9,400 |

Not enough: a composer-split held-out set would leave about 5 pairs per word. Absolute and relative words
were dropped, and Phase 4 went back to option 1: return words only.

## 2. Return words ("a tempo", "Tempo I")

Return words name a tempo the song already had, so they need no table, only reliable reading.
[`tempo_words.py`](../../../tempo_words.py) scores the frozen Phase 2 reader's saved rows (no new OCR run;
the shipped `Bridge/tempo_marks.py` differs from it only on pages with no staves found). The truth is every
mark in the Phase 2 truth sets whose words are a return word: the Lieder labels' own printed ones plus the
injected ones. `return_kind` accepts "a tempo", "Tempo I", "Tempo 1°", "1° Tempo", "Tempo primo", "come prima",
and rejects them when a tempo word follows ("a tempo, più lento"). Its spellings are unit-tested in
[`tests/test_tempo_words.py`](../../../tests/test_tempo_words.py).

**Development** (truth sets; the control sets are the same scores without injected marks):

| Run | Return words | Recall | Precision | Kind right | Page bar right |
| --- | --- | --- | --- | --- | --- |
| dev | 51 | 0.67 | 0.92 | 1.00 | 1.00 |
| dev-b | 16 | 0.88 | 1.00 | 1.00 | 1.00 |

Nothing was tuned: every spelling the reader produced was classified right. Almost every miss is a mark
printed **below** a staff, because the reader reads only the strip above each system; the false hits are
such marks read from the next system down, 4 to 10 bars late.

**Freeze** ([`freeze.json`](freeze.json), 2026-10-22, before any test row was looked at for return words):
precision ≥ 0.90, kind right ≥ 0.95, page bar right ≥ 0.90, recall ≥ 0.60, false return words ≤ 0.10 per score.

**Verdict** ([`verdict.json`](verdict.json), test and test-b truth pooled, scored once):

| Check | Rule | Pooled | test | test-b |
| --- | --- | --- | --- | --- |
| `return_precision` | ≥ 0.90 | **0.897 FAIL** | 0.947 | 0.800 |
| `return_recall` | ≥ 0.60 | **0.542 FAIL** | 0.706 | 0.356 |
| `kind_exact_of_matched` | ≥ 0.95 | 1.00 | 1.00 | 1.00 |
| `page_bar_exact_of_matched` | ≥ 0.90 | 0.962 | 0.972 | 0.938 |
| `false_per_score` | ≤ 0.10 | 0.064 | 0.050 | 0.074 |

**NOT ACCEPTED.** 41 of the 44 missed marks are printed below the staff. test-b's scores print most of
their "a tempo" there, hence its recall of 0.36.

## 3. What it would have changed in the library

All 61 library PDFs were read in Phase 3. Five print a return word: "Tempo I" in three, "a tempo" and
"a Tempo 1°" in one each. None of the five prints a tempo number, so even an accepted rule would have played
nothing new in them by default. Return words matter there only against tempos the user sets.

## 4. Options left (not authorized)

1. **Close the plan** after Phases 1–3; words stay hints.
2. **A richer hint, no auto-play:** a return word shows the tempo it names ("Tempo I → ♩ = 60") with a
   one-click USE that adds that change to the user's map. The user sees the bar before using it, so the
   wrong-system risk is visible. This does not need the failed rule.
3. **Read text below the staff:** a reader change, so a new frozen reader and fresh truth seeds (the Phase 2
   test splits are now spent for return words too). Larger research.

## 5. Shipped: return words as hints with USE

Chosen 2026-10-22 ("go with option 2 and commit the phase 4 research"). A printed "a tempo" or "Tempo I"
without a number now shows the tempo it names in what plays, `"a tempo" · BACK TO ♩=110`, with **USE**
(adds that change at its bar to the user's map) and **IGNORE**. It never plays by itself. When it names the
tempo already playing it shows SAME TEMPO; when there is nothing to go back to it stays a hint, as do words
such as "Andante".

- `Visualization_engine/TempoWords.cs`: `Kind` (the same spellings as `return_kind`, tested on the same list
  in `TempoTests`), `Resolve` ("Tempo I" is the start tempo; "a tempo" is the tempo before the latest change
  before it, skipping changes at other return words' bars, so taking one in does not make the next go back to
  the passage it ended), `ReturnBars`, `Named`.
- `Program.Tempo.cs` `DrawPrintedMarks`: the BACK TO label, USE, SAME TEMPO. "→" is not in the app's font
  glyph set, hence "BACK TO".
- Tests: 229 app tests pass (3 new: spellings, resolving, never playing by itself). Release gate 8 of 8.
  Snapshot from the published exe: [07-playback-tempo-return.png](07-playback-tempo-return.png).
