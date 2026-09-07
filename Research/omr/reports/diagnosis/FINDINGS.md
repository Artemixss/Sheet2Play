# Rhythm diagnosis — where HOMR's timing actually breaks

Step 1 of the OMR next-phase plan: locate the rhythm error before spending GPU time on it.
Everything below is measured on the 100-sample OLiMPiC scanned canary (99 produced valid
output), reproduced with `diagnose_rhythm.py`. Raw data is in `diagnosis.json`; cached
predictions are under `predictions/`.

## Headline

The problem is **not** rhythmic imprecision. It is **duration over-accounting**: HOMR emits
more total time than the music contains, and everything after the first error shifts.

A single scalar — the ratio of predicted timeline length to ground-truth length — separates
success from failure almost completely:

| predicted timeline vs truth | n | onset_f1 |
| --- | --- | --- |
| accurate (<= 1.02x) | 47 | **0.884** |
| long, 1.02–1.15x | 23 | 0.344 |
| long, > 1.15x | 29 | 0.269 |

**53% of systems produce a timeline that is too long.** When the length is right, HOMR is
good (0.884). When it is wrong, onsets collapse. Pitch recognition is unaffected throughout
(pitch_f1 0.960 overall).

## What was ruled out

Three cheaper explanations were tested first. All three are largely wrong, and saying so
matters — two of them were my leading hypotheses going in.

**Metric strictness — ruled out.** `sheet2play_omr.metrics` matches onsets by exact rational
equality. Re-scoring the identical predictions through `Bridge/evaluate_omr.evaluate` with a
tolerance barely moves anything:

| group | n | exact | +/-1/32 | +/-1/16 | +/-1/8 |
| --- | --- | --- | --- | --- | --- |
| all | 99 | 0.579 | 0.579 | 0.579 | 0.587 |
| tuplet | 20 | 0.159 | 0.162 | 0.162 | 0.175 |
| no tuplet | 79 | 0.685 | 0.685 | 0.685 | 0.691 |

The errors are structural, not near-misses. A note is not slightly late; it is in the wrong
place.

**Ground-truth/prediction flag asymmetry — real defect, negligible effect.** Ground truth was
loaded with `expand_repeats=False, skip_grace_notes=True` while predictions came from
`bridge.py` with the opposite flags. Scoring both ways: 0.576 legacy vs 0.579 symmetric.
Repeats are rare in this corpus (3–5%) and grace notes are dropped by the duration validator
regardless of the flag, so the mismatch cost almost nothing here. It is still fixed
(`phase3_benchmark.py:69`), because it would silently corrupt any corpus where those
constructs are common.

**HOMR's tuplet-repair heuristic — ruled out as the cause.** `_fix_over_eager_tuplets` in
`homr/transformer/vocabulary.py` strips every tuplet from any measure shorter than the
system median, and homr's own docstring admits "the transformer tends to add too many
tuplets". It looked like the culprit. Neutralising it
(`SHEET2PLAY_HOMR_KEEP_TUPLETS=1`, added to `Bridge/homr_gpu.py`) recovers almost nothing:

| variant | n | onset_f1 |
| --- | --- | --- |
| baseline | 20 | 0.159 |
| tuplet cleanup disabled | 20 | 0.174 |

Only 3 of 20 samples changed at all. The heuristic is not what breaks these systems.

## What tuplets and voices actually predict

Tuplets remain the strongest *predictor* of failure even though the repair heuristic is not
the *cause*:

| group | n | onset_f1 |
| --- | --- | --- |
| no tuplet | 79 | 0.685 |
| tuplet | 20 | **0.159** |

Cross-tabulated against the maximum number of independent voices on a single staff in the
ground truth:

| group | n | onset_f1 |
| --- | --- | --- |
| no tuplet, 1 voice | 20 | 0.830 |
| no tuplet, 2 voices | 46 | 0.613 |
| no tuplet, 3+ voices | 13 | 0.715 |
| tuplet, 2 voices | 16 | 0.145 |

Both tuplets and parallel voices inflate the timeline; tuplets do it far more severely.

## The mechanism

**Corrected.** An earlier revision of this document claimed HOMR's vocabulary has no voice
dimension and therefore serialises parallel voices. That is wrong, and the correction matters
because it changes which fix would work.

HOMR *can* represent two independent rhythmic layers on one staff. The mechanism is `chord`
tokens plus differing durations: `_group_notes` (`music_xml_generator.py:711`) buckets a
chord group by `Fraction` duration and emits each bucket as its own rhythmic layer separated
by `<backup>`, with `get_xml_voice` assigning stable voice numbers. This round-trips
correctly — tokens `[note_2 F4 upper] chord [note_4 D4 upper], [note_4 C4 upper]` produce a
proper half-note voice 2 against two quarter-notes in voice 1.

The real limit is narrower and harder:

1. **The time cursor advances by `min(duration)` over the whole chord group**
   (`SymbolChord.get_duration`, `music_xml_generator.py:65`). There is no token meaning
   "advance by X" or "go back".
2. **There is no tie token.** `grep -n "tie" transformer/vocabulary.py` returns nothing;
   `build_slur()` holds only `slurStart`, `slurStop`, `slurStart_slurStop`. The
   `tieStart`/`tieStop` branches at `music_xml_generator.py:553` are unreachable dead code.

Together those mean: **an onset that falls strictly inside a sustaining note in every voice
cannot be encoded.** In real notation you spell that with a tie, splitting the sustaining
note so a group boundary exists at the right instant. HOMR has no tie, so the cursor
overshoots and the measure grows.

A minimal reproduction — upper staff, voice 1 = dotted quarter then eighth, voice 2 = four
quarters:

```
              expected     HOMR encoding
F4  dotted q    1.0            1.0
D4  quarter     1.0            1.0
C4  quarter     2.0            2.0
G4  eighth      2.5            3.0   <- cursor cannot stop at 2.5
B3  quarter     3.0            3.5
A3  quarter     4.0            4.5
              measure 4.0    measure 4.5   (1.125x)
```

That 1.125x is the same signature as the measured median 1.14x inflation.

This also explains why tuplets predict failure so strongly. Tuplet *arithmetic* is exact —
`note_12` decodes to precisely 1/12, and the triplet ladder 3/6/12/24/48/96 is all present.
What breaks is **polyrhythm**: triplets against straight eighths, 3-against-2, 3-against-4,
where one voice's onsets land inside the other's notes and no tie is available to split them.
That is everywhere in piano writing and rare in the monophonic and homophonic corpora HOMR
was tuned on.

Consistent with this, in the worked example above the four melody notes were read as halves
(duration 8) rather than quarters (duration 4). Once their durations matched voice 1's, they
collapsed into a single layer — the serialisation was a *consequence* of the duration
misread, not proof that voices are unrepresentable.

Two secondary amplifiers: the time-signature numerator is not a token at all but guessed from
the median decoded measure length (`find_division_and_time_signature_nominator`), so wrong
durations also produce a wrong meter; and the position head is not autoregressive — the ONNX
decoder takes no `positions` input, so the model never sees its own previous staff
assignments.

## Confirmed by construction: it is polyrhythm, not tuplets

The OLiMPiC correlation above says tuplet systems fail. It cannot say *why*, because in real
piano music tuplets almost always appear against another voice - the two are confounded, and
no public corpus separates them.

`generate_polyrhythm.py` breaks the confound by engraving cases that vary tuplets and
polyrhythm independently, with labels exact by construction rather than transcribed. Scored
through the same harness:

| case | tuplet | polyrhythm | onset_f1 | span |
| --- | --- | --- | --- | --- |
| homophonic | no | no | **1.000** | 1.00 |
| tuplet_aligned | **yes** | no | **1.000** | 1.00 |
| offset_entry | no | **yes** | **0.143** | 1.50 |
| triplet_vs_duple | yes | yes | 0.400 | 1.33 |
| triplet_vs_quadruple | yes | yes | 0.462 | 0.75 |
| tie_across_barline | no | no | 0.857 | 1.00 |

**Tuplets alone are not a problem at all.** `tuplet_aligned` holds 24 triplet notes in two
staves, and HOMR's onsets come back identical to ground truth to the last digit:

```
expected: 0.0 0.0 0.333 0.333 0.667 0.667 1.0 1.0 1.333 1.333 ... 3.667 3.667
HOMR    : 0.0 0.0 0.333 0.333 0.667 0.667 1.0 1.0 1.333 1.333 ... 3.667 3.667
```

**Polyrhythm alone is catastrophic.** `offset_entry` contains no tuplet whatsoever - just a
dotted quarter in one voice against plain quarters in the other, so one onset lands at beat
1.5, strictly inside the other voice's note:

```
expected: 0.0  0.0  1.0  1.5  2.0  2.0  3.0
HOMR    : 0.0  1.5  2.5  3.5  4.0  4.0  5.0
```

The first onset is right and every later one drifts, with the timeline stretching to 5.0
against a true 3.0 - the cursor overshoot predicted above, reproduced in isolation.

So the earlier framing needs one more correction: tuplets are a *marker* of the failure, not a
cause. What breaks HOMR is an onset it cannot place because it has no tie to split the note
that is sounding. This matters for what comes next - a corpus curated for "more tuplets" would
target the wrong thing, while polyrhythm is the axis that actually separates.

## Refuted: the per-voice cursor fix cannot work

The obvious repair, given the cursor analysis above, is to place notes with a cursor per voice
instead of one global cursor. That was implemented behind
`SHEET2PLAY_HOMR_PER_VOICE_CURSOR=1` and measured. **It changes nothing**, and the reason
matters more than the result.

The premise was that homr's token stream already carries enough information to place the
notes correctly, and only the generator throws it away. Inspecting what homr actually emits
shows the premise is false. For `offset_entry` - a two-voice measure with no tuplets - the
whole token stream is:

```
note_4. G5 upper,  note_4 C4 upper,  note_4 D4 upper,  note_8 A5 upper,
note_2 B5 upper,  chord,  note_4 E4 upper,  note_4 F4 upper
```

**One `chord` token in the entire measure.** homr never marks G5 and C4 as sounding together;
it reads the two-voice passage as a single melodic line. A per-voice cursor has nothing to
separate, so the reconstruction reproduces homr's own onsets exactly - which is what the
measurement showed.

The real-score failure mode is different but equally upstream. On `6984631/p1-s4` homr emits
37 chord tokens, so simultaneity *is* being marked, but every melody note comes back as
`note_2` (half) where the ground truth has quarters. The durations are wrong at the token
level.

So both failure modes are **recognition errors, not generation errors**. In neither case does
the generator receive a correct token stream to work with, and no amount of downstream
cleverness recovers information the model did not produce.

This closes the "fix the decoder" route. It appeared at the time to reopen fine-tuning, on the
reasoning that the vocabulary can express these passages correctly - `chord` plus differing
durations round-trips, and tuplet arithmetic is exact - so the model merely fails to emit that
structure on polyrhythmic piano writing, which is what training data changes.

**That inference was wrong, and the next section measures why.** It generalised from two
constructed examples that happen to round-trip to the claim that the vocabulary is adequate in
general. On real music it is not.

The implementation is left in place but inert (`Bridge/homr_voices.py`, off unless its
variable is set), and the app path was verified byte-identical with the switch unset.

## Measured: the representation ceiling

The question "is the gap learnable?" was settled by measurement rather than argument.
`roundtrip_oracle.py` encodes ground-truth MusicXML into homr's vocabulary with
`music_xml_file_to_tokens`, decodes it straight back with `generate_xml`, and scores the result
against the original through the same normalizer and metrics used on real predictions:

```
MusicXML(truth) --music_xml_file_to_tokens--> tokens --generate_xml--> MusicXML(rebuilt)
```

No model is involved, so the score is the ceiling: the best any perfectly trained model could
achieve while emitting this vocabulary. Across the 75 canary systems both can be scored on:

| | onset_f1 |
| --- | --- |
| HOMR today | 0.624 |
| a perfect model, same vocabulary | **0.690** |
| headroom | **+0.066** |

Splitting by whether the round trip is lossless is what actually decides the fine-tune:

| round trip | n | HOMR | ceiling | headroom |
| --- | --- | --- | --- | --- |
| lossless | 31 | 0.864 | 1.000 | **+0.136** |
| loses time | 44 | 0.455 | 0.472 | **+0.017** |

**The systems whose timelines inflate are already at the representation's ceiling.** That is
the 53% this entire diagnosis is about, and training cannot move them, because the target
itself is unreachable. The remaining headroom lives almost entirely in systems that are
already scoring 0.864.

Three corroborating details:

- **HOMR beats the ceiling on 7 of 75 systems.** On `6986065/p2-s1` it transcribes the music
  perfectly (1.000) while a round trip of the ground truth scores 0.216. When a model
  outscores a faithful encoding of its own label, the label is the defect.
- **The round trip inflates timelines on its own.** 31 of 75 systems come back longer than
  truth, median 1.00 but reaching 1.68 - the same overshoot signature attributed above to
  recognition error, reproduced here with no recognition involved.
- **24 of 100 systems cannot be encoded at all**, raising `ValueError` on slurs
  (`slurStart_slurStart`, 21 cases), `detachedLegato`, and octave shifts. `convert_pdmx.py`
  calls the same encoder, so these are files training silently skips - and dense piano, the
  material the raised complexity ceiling is meant to admit, is exactly where such markings
  cluster.

The constructed cases separate learnable from unreachable cleanly:

| case | HOMR | ceiling | verdict |
| --- | --- | --- | --- |
| homophonic | 1.000 | 1.000 | already solved |
| tuplet_aligned | 1.000 | 1.000 | already solved |
| tie_across_barline | 0.857 | 0.857 | at ceiling |
| three_voices | 0.154 | **1.000** | **learnable** |
| same_position_sustain | 0.444 | **1.000** | **learnable** |
| triplet_vs_duple | 0.400 | 0.600 | partly learnable |
| offset_entry | 0.143 | 0.429 | partly learnable |
| triplet_vs_quadruple | 0.462 | 0.429 | at ceiling |
| quintuplet_vs_duple | 0.471 | 0.333 | above ceiling |
| septuplet_vs_duple | 0.381 | 0.273 | above ceiling |
| syncopation | 0.125 | 0.125 | at ceiling |

So the earlier reading was half right. `three_voices` and `same_position_sustain` are genuine
recognition failures with a perfect target, and a fine-tune should fix them. But every case
where one voice's onsets fall inside another's notes and a tie would be needed to split them
is unreachable, and on real music that case dominates.

Reproduce with:

```bash
cd Research/omr && .venv/Scripts/python.exe roundtrip_oracle.py --both
```

## Fixed: +0.078 onset_f1 with no training at all

Searching homr's own issue tracker turned out to be worth more than any experiment here. The
timing defect is known upstream, and most of the fix already existed.

| upstream work | state | what it does |
| --- | --- | --- |
| PR #141 recover ties from same-pitch slurs | **merged**, after our old pin | reads a tie back out of the slur head |
| PR #146 re-time measures that overflow | **closed by its author** | per-staff cursor, shrinks over-long measures |
| PR #156 `upper2`/`lower2` positions | open, by a collaborator, already retrained | the representation fix — see Plan B below |
| issue #150 chord split causes overflow | open | this project's symptom, independently reported |

Three changes were applied to the vendored clone and measured one at a time. The ceiling first:

| step | ceiling | scoreable | encode failures |
| --- | --- | --- | --- |
| old pin | 0.684 | 76 | 24 |
| + PR #141 | 0.689 | 76 | 24 |
| + slur dedup (below) | 0.689 | **94** | **6** |
| + PR #146 | **0.760** | 94 | 6 |

**The slur dedup fix.** `_collect_articulation` dedupes articulations but not slurs, so a note
that is both tied and slurred — ordinary in piano — produced `slurStart_slurStart`, which
`build_slur()` does not contain, and the file was rejected outright. One `list(set(slurs))`
takes encode failures from 24 to 6. This never showed up as a rhythm bug because it is not one:
it silently removed a fifth of real piano from anything the encoder touches, **including the
training labels `convert_pdmx.py` builds**, and precisely the dense material we most want.

**PR #146 is the large win, and it was abandoned.** Its author closed it saying the problem
space was more complex than expected, and noting *"no change in OMR-NED score as this
improvement didn't seem to be caught by the benchmark."* OMR-NED does not measure onset
placement. Re-measured on real HOMR predictions across the 100-sample canary:

| | baseline | patched | |
| --- | --- | --- | --- |
| onset_f1, all | 0.583 | **0.661** | **+0.078** |
| onset_f1, no tuplet | 0.689 | **0.776** | +0.087 |
| onset_f1, tuplet | 0.159 | 0.201 | +0.042 |
| mean span ratio | 1.128 | **1.088** | |
| **systems running long** | **52%** | **34%** | **-18 points** |
| systems running long, no tuplet | 41% | **21%** | -20 points |
| perfectly transcribed systems | 16 | **25** | |
| pitch_f1 (sanity) | 0.960 | 0.968 | no regression |

That is the reported symptom directly addressed: fewer scores run long, and they run less long.
`6592539/p1-s3` goes from onset_f1 0.157 at span 1.74 to 0.965 at span 1.00.

**It is not free.** 37 systems improve, 45 are unchanged, and **18 regress**, some badly
(`6570092/p1-s4`, 1.000 to 0.206). The regressions share a signature: a system that was already
correctly timed at span 1.00 is pushed *below* it, to 0.88 or 0.74. The shrink logic is not at
fault — it fires only when a measure exceeds `expected` and bails when it falls short. The
estimate is. `expected` is `np.median(measure_duration)`
(`find_division_and_time_signature_nominator`), so when several measures decode short the median
follows them down, correctly timed measures start to look over-long, and the repair damages
them.

**That explanation was tested and is wrong.** Replacing the median with the most common measure
duration changed exactly one of the 18 regressed systems (`6725782/p1-s2`, 0.123 to 0.526) and
left the other 17 untouched; the mean over that set moved 0.302 to 0.324 against a baseline of
0.522. A first attempt, gated on a *strict majority*, was worse than useless — a no-op by
construction, since a strict majority is precisely the case where the median already returns
that value, and the notes came back byte-identical across all 100 systems. Both versions have
been removed rather than left in as dead switches.

So the estimator is not the lever, and what actually breaks these 18 systems is still open. The
next hypothesis worth testing is a guard rather than a better estimate: leave a measure alone
when its decoded duration is already a musically plausible measure length, on the grounds that
the regressed systems all sat at span 1.00 before the repair touched them.

**The constructed cases cannot measure any of this**, and the flat 0.6535 they report is an
artifact rather than a null result. `_plan_voice_repairs` compares each measure against that
same median, and ten of the eleven generated cases are a single measure, where the median is
the measure's own wrong length — so the repair never fires. This is the same trap that made the
earlier tuplet re-test underpowered. Any future generated case meant to exercise measure repair
needs several measures.

### What this does to the training question

The ceiling rose faster than HOMR did, so the gap that training could close got *wider*:

| | before | after |
| --- | --- | --- |
| HOMR | 0.624 | 0.661 |
| ceiling | 0.690 | 0.766 |
| **headroom for training** | **+0.066** | **+0.182** |

Part of that widening is composition — the 18 systems the dedup fix newly admits are hard ones
that pull HOMR's own average down — but the ceiling rise from 0.665 to 0.760 is on an identical
94-sample set and is attributable to PR #146 alone.

The conclusion inverts. Before these fixes a fine-tune competed for 0.066 and was not worth
days of GPU time. Repairing the representation first is what makes training worth doing, and in
that order: **fix the labels, then train on them.**

## The normalizer is not at fault

`Bridge/musicxml_normalizer.py` computes no timing of its own; `start_beat` is one call to
music21's `getOffsetInHierarchy`. To confirm this rather than assume it, the golden corpus in
`Bridge/tests/golden_scores.json` — six scores with exact expected onsets and durations,
whose values had never actually been asserted against anything — is now wired up
(`test_golden_corpus_onsets_and_durations_match`). All six pass, including
`triplet_tuplets` and `multiple_voices_repeats_accidentals` — so the normalizer places
tuplet and two-voice onsets correctly when the MusicXML it is given is correct.

The normalizer handles tuplets, parallel voices, repeats, ties, grand staff and piecewise
tempo correctly. The fault is upstream, in the engine.

## Separate bug: multi-page offset drift

`combine_score_pages` concatenates pages with `page_offset += page.total_beats`, where
`total_beats` is `score.highestTime` — no barline alignment, no quantization. HOMR reads each
page independently and routinely emits a short final measure, so the error compounds and
never recovers:

```
page 1 total_beats = 3.5 (final measure one beat short)
combined onsets: 0.0 1.0 2.0 3.0 | 3.5 4.5 5.5 6.5 | 7.5 8.5 9.5 10.5
                                   ^ page 2 starts at 3.5, not 4.0
8 of 12 onsets land off the beat grid
```

This cannot explain any of the numbers above — the OLiMPiC benchmark feeds single-system
PNGs, so `combine_score_pages` is a no-op there. But it affects the app on real multi-page
PDFs, which is the normal case, and it has no test coverage. Recorded, not fixed.

## What this means for fine-tuning

The plan's Step 3 decision now has evidence behind it, and it is not encouraging for the
"fine-tune HOMR" strategy.

**Read this section as the state before the in-place fixes.** It is kept because its reasoning
still holds — training cannot beat the representation it is trained into — but its numbers are
superseded. Once the ceiling was raised, the headroom went from +0.066 to +0.182 and training
became worth considering again, in that order. The options below are annotated where the fixes
changed them.

- The dominant failure is a **grammar limit, not a training deficiency**. HOMR's rhythm
  alphabet has no tie, and its time cursor can only advance by the shortest duration in the
  current group. No amount of data teaches a model to emit a symbol its alphabet lacks. This
  was the original reading, briefly overturned by the token-stream inspection above, and then
  confirmed by direct measurement: **the ceiling is 0.690 against today's 0.624**, and on the
  systems that actually fail it is 0.472 against 0.455.
- Dense piano — the material this project targets — is full of exactly the polyrhythm and
  offset-entry writing that hits this limit. It is rare in the monophonic and homophonic
  corpora HOMR was tuned on, which is consistent with pitch_f1 staying at 0.960 while onsets
  collapse.
- HOMR is **already trained on MuseScore data**. Upstream Run 426 used
  `lieder + grandstaff + primus + pdmx + musetrainer`, and PDMX is 250K public-domain scores
  scraped from MuseScore. Collecting more MuseScore data reproduces its existing training set.
- The 47 systems whose timeline length is correct already score 0.884. The headroom is not in
  reading rhythm more precisely; it is in the 53% where time accounting breaks.

Options worth weighing before committing GPU time:

1. **Add a tie token and fix the cursor.** This targets the actual defect, but it means
   extending the *rhythm* vocabulary (both the embedding table and the output head) and
   rewriting `build_measures` / `build_note_chord` cursor logic — a grammar redesign
   requiring full decoder retraining, not a LoRA fine-tune. **Largely superseded**: PR #141
   recovers a tie from the slur head without any vocabulary change at all, and is merged.

   An earlier revision of this document also claimed that extending `build_position()` into
   voice IDs "would not move onset F1", on the reasoning that voices are already representable
   and the cursor is the blocker. That is contradicted by upstream PR #156, which does exactly
   that — `upper`/`upper2` and `lower`/`lower2` — and reports no regression from a retrained
   model. The claim assumed an output-head-only change; #156 also rewrites parts of
   `music_xml_generator.py`, so it is not the cheap change the objection was aimed at.
2. **Post-hoc repair.** Span ratio is computable without ground truth: compare each measure's
   decoded length against the time signature. That gives a runtime signal for detecting bad
   measures, and would let the app flag a low-confidence transcription instead of silently
   playing wrong rhythms.
3. **Replace the engine.** Transcoda scored onset_f1 0.897 against HOMR's 0.584 on this same
   canary — consistent with it having a tie or backup representation — but it was removed for
   instability and is AGPL. LEGATO is the current candidate: MIT-licensed, public weights,
   and explicitly built for full-page polyphonic scores. **Weaker now than when written**: the
   in-place fixes above took HOMR from 0.583 to 0.661 without training, so the gap a
   replacement has to justify is narrower than it was.

4. **Plan B — adopt upstream PR #156.** weixlu's open PR distinguishes `upper`/`upper2` and
   `lower`/`lower2` in the position vocabulary, which is what lets two voices on one staff be
   told apart at all rather than inferred from differing durations. The author has already
   retrained it and reports polish 16.89% and smb 13.72% NED, so it comes with weights and no
   GPU cost to us. This is the most likely candidate to raise the ceiling further, and it
   deserves evaluation even if the fixes above hold, precisely because it comes from a project
   collaborator with a retrained model behind it rather than from us. Score it on the canary,
   and run `roundtrip_oracle.py` against its vocabulary to get the new ceiling: if that ceiling
   rises materially, it — not a fine-tune on the present vocabulary — is what makes training
   worthwhile.

**The screening question for any replacement engine is not "does it have voices?" but "can it
encode a tie, and can it place an onset inside a sustaining note?"**

`roundtrip_oracle.py` answers that question for any candidate without training it, and it also
prices option 1 before the work starts: add a tie to the encoder and the cursor logic, re-run
the oracle, and the new ceiling says what full retraining would buy. A ceiling that stays near
0.69 means the redesign is not worth it either.

A practical caveat for any training route: the installed `homr` wheel is **inference-only**.
It ships two ONNX graphs and no PyTorch, no model definition, no `.pth`, no dataset
converters and no `Training.md`. Step zero for any fine-tune is cloning
`github.com/liebharc/homr` and confirming its `training/` tree exists and runs.

## Reproducing

```bash
cd Research/omr && .venv/Scripts/python.exe diagnose_rhythm.py --variants baseline
```

```bash
cd Research/omr && .venv/Scripts/python.exe diagnose_rhythm.py --only-tuplets --variants baseline,keep-tuplets
```

Predictions are cached per sample and variant, so re-scoring is free; pass `--rerun` to
re-invoke HOMR.

The representation ceiling needs no model and runs in seconds:

```bash
cd Research/omr && .venv/Scripts/python.exe roundtrip_oracle.py --both --keep-xml
```
