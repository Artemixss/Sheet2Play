# Per-song tempo, Phase 4: tempo words

**Plan:** [`2026-10-19-song-tempo`](../../../../../plans/archive/2026-10-19-song-tempo.done.md), Phase 4.
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

## 6. PDMX: absolute and relative words (resumed 2026-10-27)

"ok i got internet access lets go with the download option". `subset_paths.tar.gz`, `PDMX.csv` and
`mxl.tar.gz` from Zenodo record 15571083 (CC BY 4.0, Long et al.), MD5s checked, in `data/pdmx/` (local).
[`tempo_word_corpus.py`](../../../tempo_word_corpus.py) streamed the deduplicated, licence-clean subset:
77,321 scores, 2 unreadable. Only visible marks of the first part count; a word counts once per score. Scores
are split by composer (else artist, else title) into dev (34,737) and held-out (42,582).

**Pairs** ([`pdmx-pairs.json`](pdmx-pairs.json), counts only): dev 1,285 pairs with 13 words at 10+, held-out
1,185 with 13. The bar (150 pairs, 6 words) is met.

**Rule**, written into the handoff before any tempo value was looked at: absolute words, held-out median
|guess ÷ printed − 1| ≤ 0.15, share off by more than 40% ≤ 0.10, one-sided sign test against 120 p < 0.01;
relative words (a faster and a slower class, factor on the number printed before), median factor error
≤ 0.10 and a sign test against no change p < 0.01.

**Dev tuning.** The pre-registered method put each word's tempo in the beat its meter is felt in (6/8 in ♩.);
on dev that made every measure worse than plain quarter BPM (median 0.167 vs 0.152, off by > 40% 19% vs 17%),
because many scores print a quarter-note tempo in any meter. The frozen method uses quarter BPM. The
thresholds were not touched. Dev table ([`pdmx-dev-table.json`](pdmx-dev-table.json)), quarter BPM:
largo 52, lent 58, lento 62, adagio 66, andantino 70, slow 72, andante 80, allegro moderato 98, moderately
102, moderato 108, allegretto 108, allegro 131, fast 160, vivace 160, presto 180; faster × 1.137, slower
× 0.932.

**Verdict** ([`pdmx-freeze.json`](pdmx-freeze.json), [`pdmx-verdict.json`](pdmx-verdict.json), held-out
scored once):

| Kind | Check | Rule | Held-out |
| --- | --- | --- | --- |
| absolute | median error | ≤ 0.15 | **0.167 FAIL** (120 alone: 0.333) |
| absolute | off by > 40% | ≤ 0.10 | **0.168 FAIL** |
| absolute | sign test vs 120 | p < 0.01 | 333 wins, 112 losses, PASS |
| relative | median factor error | ≤ 0.10 | 0.075 PASS (no change: 0.135) |
| relative | sign test vs no change | p < 0.01 | 69 wins, 13 losses, PASS |

**Absolute words not accepted; relative words accepted.** The absolute guess is about twice as close as 120,
but one score in six is more than 40% away: the same word is played very differently from score to score.

**Not measured:** where a relative passage ends. It ends at "a tempo" or "Tempo I", which the reader misses
46% of the time (section 2), so a relative change that played by itself would often never end.

## 7. Shipped: word guesses with USE (2026-10-27)

The user chose, for both kinds, "guess + one-click USE": relative words because the "a tempo" ending their
passage is missed 46% of the time, absolute words because they missed their rule. A word printed without a
number shows `"Più mosso" · GUESS ♩=125` (relative: the factor on the tempo before its bar, in that tempo's
unit) or `"Andante" · GUESS ♩=80` (absolute: the frozen table, in quarters), with USE and IGNORE. Nothing
plays by itself; what plays is unchanged.

- `Visualization_engine/TempoWords.cs`: `Normalized`, `RelativeFactor`, `AbsoluteGuess`, `Guessed`, with the
  frozen table, factors and word lists; `tests/test_tempo_word_corpus.py` `AppParityTests` checks them against
  `pdmx-freeze.json` and `tempo_word_corpus.py`.
- `Program.Tempo.cs`: the GUESS label beside BACK TO; USE, PLAYING and SAME TEMPO work the same for both.
- 246 app tests pass (3 new); research tests pass; release gate 8 of 8. Snapshot from the published exe:
  [07-playback-tempo-guess.png](07-playback-tempo-guess.png) (local; report PNGs are gitignored).

## 8. Words play by default, a re-measured table, and a wider word list (2026-10-27)

**Requests, mid-turn:** "it misses agitato in sergei rachmanivov"; "change the word bpm values correctly ... presto
agiato is 180 but i think it should be around 160-170 ... investigate thoroughly each word"; "i think word tempo
things should played as default ... they are working quite nice"; and five PDMX scores with tempo words added to the
library as `tempo_<song name>`.

**"Agitato" was read but dropped.** OCR read it at 1.00 confidence above bar 14; the frozen reader's word list did
not contain it, so the line was discarded. `Bridge/tempo_marks.py` keeps the frozen list as `FROZEN_LEXICON` (still
checked equal to the research reader's) and adds `EXTRA_WORDS`: every word the app can guess for or name (Phase 4's
absolute, faster and slower lists, "tempo primo", "come prima", "tempo 1") and "agitato". A word is never a number,
so printed tempos read exactly as before: after re-reading all 61 library PDFs with the new reader (`7745ddf9…`,
0 failed), every PDF's printed numbers are identical, no word was lost, and three were added ("Agitato" in the
Rachmaninov Prelude, "poco cresc. ed agitato" in Liebestraum, "Lent et douloureux" in Gymnopédie No. 1). Agitato
alone has 4 PDMX pairs, too few for a guess, so it shows as a hint.

**Each word re-measured** ([`tempo_word_survey.py`](../../../tempo_word_survey.py),
[`word-survey.json`](word-survey.json)). With the held-out judgement done, all 2,470 PDMX pairs were used:
median, middle half and 10–90% per word, the same for scores tagged classical and per meter, and modifier effects.
Four tables were compared by 5-fold composer cross-validation (996 pairs):

| Table | Median error | Off by > 40% |
| --- | --- | --- |
| A: PDMX medians (the frozen method) | 0.167 | 16.6% |
| B: A clamped to Wikipedia's ranges | 0.160 | 16.6% |
| C: Wikipedia midpoints | 0.175 | 18.9% |
| D: a median per meter | 0.161 | 16.0% |
| 120 | 0.333 | 42.4% |

A, B and D are within noise of each other; the textbook midpoints are worst. The app now uses A on all pairs
(`table_v2`): grave 69 (11 pairs from 30 to 112, the weakest entry), largo 50, lent 57, langsam 61, mässig 63,
larghetto 64, lento 66, adagio 69, slow 75, andantino 78, andante 80, slowly 84, andante con moto 86, allegro
moderato 96, moderato 100, moderately 108.5, allegretto 112, allegro 132, vivace 160, fast 171, presto 184,
prestissimo 232; faster × 1.137, slower × 0.898 (dev only: × 0.932).

**Presto.** All 37 scores printing "Presto" put the median at ♩ = 184 (middle half 160–220; classical 180), and
Wikipedia's range is 168–200, so 184 stays. The user's 160–170 sits at the low end, which is where a piece with
dense sixteenth notes such as the Moonlight finale tends to be played; one number per word cannot know that.
"Presto agitato" has a single PDMX pair, so it uses Presto's.

**Words play by default** (the user's decision, against the absolute words' failed rule): `TempoDetection.PrintedMap`
takes the marks in bar order; a number always plays and wins its bar; a word without one plays the tempo it names
(return words) or its guess (relative: the factor on the tempo before; absolute: the table), unless it would not
change the tempo. IGNORE stops any of them; the user's own tempo still replaces them all.

**Five tempo PDFs** (CC0 or public domain, solo piano, no metronome numbers), engraved from PDMX MusicXML with
MuseScore 4 and added to `songs\pdf`: `tempo_Song of the Lark` (Tchaikovsky: Andantino espressivo, un pochettino
più mosso, a tempo), `tempo_Impromptu passione` (Mussorgsky: Andantino amoroso, a tempo ×2, Meno mosso),
`tempo_Consolation No. 1` (Liszt: Andante con moto, a tempo), `tempo_Etudes-tableaux Op. 33` (Rachmaninoff:
Moderato, Tempo I), `tempo_Piece pour piano` (anonymous: Lent, a tempo, Presto ×2). The app's reader finds every
word in them except the second Presto, and reads a "Slow – Accel." instruction on the last page as "Slow".

**Checks:** 246 app tests pass (the three tests that said words never play now assert that they do); research tests
pass, including the app parity test against `table_v2`; release gate 8 of 8; snapshot from the published exe:
[07-playback-tempo-words-playing.png](07-playback-tempo-words-playing.png) (local). Checked by the user and committed
("it works commit and push").
