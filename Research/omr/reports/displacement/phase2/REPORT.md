# Displacement Phase 2: where scores gain their beats

Plan: [MAIN_PLAN.md](../../../../../plans/MAIN_PLAN.md), Phase 2, authorized 2026-10-17 ("approved,
start displacement phase 2"). Development split only (40 scores, 39 recognitions per engine; one
capture per engine failed in Phase 1). Test stays held out. No shipped code changed.

## Result

Named mechanisms account for **100% of the displaced notes** on both engines. About **half** of
them come from one family: **layout**. In these measures HOMR's MusicXML places the notes
wrongly (voices, `<backup>`, cross-staff chords) while the decoded tokens are mostly or entirely
right. Tuplets are second (12–13%), and no other family passes 10%.

| Family (465) | Displaced notes | Gained beats | Notes lost | Fix family alone | Only this family left |
|---|---|---|---|---|---|
| layout | 51.9% | 57.5% | 0 | +0.217 | −0.590 |
| tuplet | 13.4% | 12.0% | 0 | +0.007 | −0.231 |
| garbled measure | 8.7% | 3.6% | 0 | +0.013 | −0.161 |
| page rounding | 5.6% | 0.5% | 0 | −0.015 | −0.049 |
| overflow | 4.9% | 0.5% | 0 | +0.000 | −0.114 |
| underflow | 4.8% | 0.6% | 0 | +0.018 | −0.057 |
| dropped system | 3.4% | 10.0% | 496 | +0.012 | −0.087 |
| repeat expansion | 2.6% | 6.7% | 23 | +0.015 | −0.039 |
| dropped measure | 1.9% | 1.0% | 47 | +0.000 | −0.047 |
| page split into parallel parts | 1.0% | 5.8% | 0 | +0.000 | −0.038 |
| extra measure | 1.0% | 1.7% | 0 | +0.000 | −0.044 |
| pickup or short bar | 0.9% | 0.2% | 0 | +0.000 | −0.047 |

| Family (426) | Displaced notes | Gained beats | Notes lost | Fix family alone | Only this family left |
|---|---|---|---|---|---|
| layout | 49.3% | 58.9% | 0 | +0.183 | −0.621 |
| tuplet | 12.0% | 12.1% | 0 | +0.001 | −0.249 |
| overflow | 9.7% | 2.5% | 0 | +0.015 | −0.254 |
| garbled measure | 6.7% | 2.4% | 0 | +0.002 | −0.152 |
| page rounding | 5.4% | 0.3% | 0 | −0.003 | −0.067 |
| underflow | 3.9% | 0.1% | 0 | +0.004 | −0.012 |
| dropped measure | 3.7% | 0.9% | 79 | +0.011 | −0.062 |
| dropped system | 3.5% | 6.0% | 485 | +0.009 | −0.087 |
| extra measure | 2.0% | 2.3% | 0 | +0.000 | −0.079 |
| repeat expansion | 1.0% | 5.1% | 0 | +0.000 | −0.026 |
| page split into parallel parts | 0.9% | 3.9% | 0 | +0.000 | −0.039 |
| lost page (previous page reused) | 0.5% | 4.9% | 73 | +0.000 | −0.020 |

Baseline notes in place (a label note whose measure starts at its true beat): **0.321** (465),
**0.300** (426), mean per score. Of 43,685 and 43,613 label notes, 73.6% and 71.7% are displaced.
"Fix family alone" is the mean change in that figure when only that family is undone; "only
this family left" is the loss when every other family is undone. The two together say that
layout is both the largest single fix (0.32 → 0.54 for 465) and something no other fix can
work around.

Two scores, 6077132 and 6009685, also lose notes to a **repeat that spans a page break**,
which the app cannot expand (below). That effect is measured on the label alone (448 of 894 and
1,075 of 1,929 truly played notes are wrong from the divergence on), and those two scores are
otherwise attributed with repeats unexpanded on both sides.

## Method

[`displacement_attribution.py`](../../../displacement_attribution.py) runs on the cached Phase 1
page MusicXML, with no inference, under the app's own interpreter (music21 10.5.0; the research
venv has 9.9.1). For every recognition it:

1. rebuilds each staff's timeline the way the app does (music21 lays each staff out as its own
   part; a measure advances by its decoded length; a page advances by its longest staff, rounded
   to whole bars except page one) and **fails unless the pages reproduce the app's cached payload
   note for note**. All 78 pass;
2. aligns predicted to label measures per staff by pitch content (affine gaps, so a lost system
   is one run);
3. gives every measure one mechanism, "family: detail", causes before co-occurrences (below);
4. decomposes each label measure's displacement exactly into its page's start error (each
   earlier page break's stitch error, split by Shapley shares among that page's mechanisms with
   page rounding as a player) plus its offset from its page start (length errors, extra and
   dropped measures, part rewinds). The parts sum to the offset; the script asserts it;
5. splits each displaced measure's notes among the mechanisms by Shapley shares of the binary
   in-place outcome, the unit exact-onset F1 counts, so partly cancelling mechanisms share
   blame instead of netting out. No measure needed the size-based fallback;
6. rebuilds the timeline with one mechanism, one family, or all but one undone. Undoing every
   mechanism puts every note in place on all 78 recognitions.

"Gained beats" is the plan's literal ledger: the sum of |decoded − label| over measure lengths,
plus extra and dropped measures, part rewinds and what rounding adds at page breaks. It weights
long errors (a dropped system) heavily; "displaced notes" weights what onset F1 loses.

Classification order: lost page; repeat expansion; dropped or extra measure (a run of three or
more on a page with fewer detected systems than the label is a dropped system); correct length;
**garbled** (pitch similarity under 0.5); **layout: every note right** (the predicted
(pitch, duration) multiset equals the label's, yet the length differs); **layout: gaps** (some
voice leaves holes the label's does not); meter (only where 426's log says HOMR re-timed the
measure); pickup or short bar; tremolo, then tuplet details (426 strips only where its log and
the exported XML agree on measure numbering); grace note read as a note; then overflow and
underflow by voices, note count or durations.

## Verified examples

Each was checked against the label MusicXML, the predicted page MusicXML and the page image;
426 examples also against its logged tokens. Crops are rendered from the ruler PDFs in the
app's 300 dpi frame (saved at 150 dpi) into `examples/`, which stays local like the repo's other
page renders. The evidence tool, [`displacement_evidence.py`](../../../displacement_evidence.py),
prints any example and recreates its crop (`label`, `show`, `crop SCORE PAGE MEASURE --out FILE`).

| Mechanism | Example | What the evidence shows |
|---|---|---|
| layout: every note right | 6598318 m19, 465 (crop `layout-all-right-6598318-m19.png`) | 9/4 bar; all 10 notes with true durations, but the `<backup>`s do not return voice 1 to its position, so its A4 lands on beat 7 and the bar decodes to 17 beats |
| layout: every note right | 5647683 m51, 465 (crop `layout-all-right-5647683-m51.png`) | chords, rests and sextuplet all right; a staff-2 whole note is written inline with no `<backup>`, pushing staff 1 four beats on (8 for 4) |
| layout: gaps | 6009685 m14, 465 (crop `layout-gaps-6009685-m14.png`) | each beat's chord spans both staves; the lower-staff half is written with no `<chord/>` or `<backup>`, doubling the spacing (10.5 for 4.5) |
| layout: gaps | 5998497 m49, 465 (crop `layout-gaps-5998497-m49.png`) | the same cross-staff interleaving without backups (9.5 for 6) |
| tremolo read as plain notes | 5879039 m19, 465 (crop `tremolo-5879039-m19.png`) | label: half-note two-note tremolos (`<tremolo>` with 2:1 time modification); HOMR: four plain half notes (8 for 4) |
| tremolo read as plain notes | 6469541 m21, 465 (crop `tremolo-6469541-m21.png`) | the same; the label has 62 tremolos |
| tuplet missing | 5934726 m16, 465 (crop `tuplet-missing-5934726-m16.png`) | twelve triplet eighths decoded as plain eighths (6 for 4) |
| tuplet missing | 6060661 m28, 465 (crop `tuplet-missing-6060661-m28.png`) | nine triplet eighths decoded as plain eighths (4.5 for 3) |
| tuplet stripped by HOMR | 5057851 m13, 426 (crop `stripped-426-5057851-m13.png`) | log: "Removing tuplets from measure # 13"; tokens `note_8`; label triplet eighths |
| tuplet stripped by HOMR | 5934726 m16, 426 | log lists m16; tokens `rest_8`/`note_8`; label triplets. 465 loses the same triplets, and runs the same heuristic without logging it |
| garbled: system mis-detected | 5079459 m8–10, 465 | one system (key change, 2/4 bar) split into two partial staff crops; decoded pitches bear no relation to the label |
| garbled: content does not match | 6017382 m41, 465 (crop `garbled-6017382-m41.png`) | every pitch shifted by about the same interval, in a passage with a clef change: consistent with a missed clef |
| dropped system | 6000428 p1; 5669865 p1 | the page has 6 systems; HOMR detected 4 on each (148 and 209 label notes never decoded) |
| page split into parallel parts | 6000428 p1; 5669865 p1 | HOMR wrote the page as two "Piano" parts; the app gives each part its own timeline from beat 0, so the second plays on top of the first |
| repeat expansion: page-wise | 6077132; 6009685 | label repeats span a page break; the app expands each page alone, so 6077132 plays page 2 twice instead of the whole song (70 measures for 117) |
| repeat expansion: exporter | 5057985 m10 (crop `repeat-5057985-m10.png`) | HOMR writes the forward repeat as `<barline location="right"><repeat direction="forward"/>` on the measure before; music21 reads any right-barline repeat as an end repeat, so m1–10 play twice and m1–33 again (page 1 plays 94 measures; the label's page 1 plays 64). Both engines |
| lost page (previous page reused) | 5902873 p2, 426 | HOMR errored on page 2 with an empty message and exited 0; `bridge.select_generated_output` then took page 1's file. Payload 2,107 notes = kept pages 1,717 + page 1 again 390. The only occurrence in the ruler |
| voice merge (overflow) | 5079459 m1, 426 (crop `voices-426-5079459-m1.png`) | a G#4 shared by both voices on each beat is tokenised once, as the dotted eighth, with the sixteenth run after it (6 for 4); 465 keeps the voices apart |
| page rounding | 6009685 page 2 break, 465 | 46-beat stitch error: 44.9 from layout, and rounding to the 4/4 bar adds 1.5 |

Families under 2% of displaced notes on both engines (grace notes, pickups, meter re-timing,
small overflow/underflow details) are in the ledger but have no hand-verified examples.

## Root causes in code

These are where the examples lead; the exact faulty line in the exporter is not yet pinned down.

- **HOMR's MusicXML exporter** (`music_xml_generator.py`, both runtimes: 465 at
  `dist/Bridge/.runtime/homr-465/source/homr`, 426 in `Bridge/.venv-homr-gpu`). TrOmr's tokens carry no
  voice numbers; the exporter assigns voices, `<chord/>` and `<backup>`
  (`build_note_chord`, then `rebalance_measure_voices`, which drops and re-emits backups). The
  layout examples show cross-staff chords and lower-staff notes written without the backup that
  keeps the staves simultaneous.
- **Computed meter (#161).** TrOmr predicts only a time signature's denominator
  (`timeSignature/4`); `find_division_and_time_signature_nominator` sets the numerator to the
  page's median decoded measure length, one value per page. A mid-page meter change cannot be
  written (#167). With no re-timing a written meter cannot change a measure's length in music21,
  so its effect is through page rounding and, in 426, `_plan_voice_repairs` re-timing measures
  toward it (0.8% of 426's displaced notes).
- **Tuplet heuristic.** `_fix_over_eager_tuplets` (both runtimes) strips every tuplet from any
  measure decoded shorter than the page median; 426's exporter can re-infer some afterwards.
- **App page stitching.** Rounding each later page to whole bars repairs small errors but
  rounds a bar's worth of error the wrong way, and uses the page's computed meter.
- **App repeat expansion** is per page (`normalize_musicxml` per page), so a repeat that spans a
  page break plays wrongly whatever the engine reads.
- **Bridge page reuse** (426 path only): reported as a separate task, not fixed here.

## Limits

- "In place" is measure-level: a note counts as in place when its measure starts at its true
  beat. Notes can still be misplaced inside a measure, layout errors especially, so this is not
  onset F1, and the counterfactuals are upper bounds for a correction that only fixes measure
  lengths.
- The binary Shapley split gives any non-zero offset the same weight, so a mechanism adding a
  twentieth of a beat shares blame with one adding a bar. That matches exact-onset scoring; the
  gained-beats column shows magnitude.
- One mechanism per measure. A measure with several faults gets the first in the order above;
  "layout: gaps, other errors too" is explicitly such a mix.
- 465 runs in-process and logs no tokens, so its tuplet losses cannot be split into model
  omissions and the stripping heuristic; 426's can, on pages whose numbering agrees.
- Development split only, both engines trained on Lieder (Phase 1), absolute figures optimistic.
- The Phase 1 scan missed repeats because MuseScore stores them on a score's first staff, the
  vocal part, which the scan never read; the manifest's `repeat_marks` is 0 for three dev
  scores that have them. The frozen manifest is unchanged; this report handles them.

## Reproduce

```
Research\omr\.venv\Scripts\python.exe -B Research\omr\displacement_evidence.py index
Research\omr\.venv\Scripts\python.exe -B Research\omr\guarded_execution.py --output Research\omr\reports\displacement\phase2\jobs\attribution-final --max-seconds 3600 -- Bridge\.venv-homr-gpu\Scripts\python.exe -I -B Research\omr\displacement_attribution.py
```

Output: [`ledger.json`](ledger.json) (tracked: ledger and per-score summaries) and
`attribution.json` (local: every event). Tests: `Research/omr/tests/test_displacement_attribution.py`.
