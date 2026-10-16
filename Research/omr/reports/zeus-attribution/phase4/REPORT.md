# Phase 4 — bounded pipeline remedies and acceptance

Owner: [MAIN_PLAN.md](../../../../../plans/MAIN_PLAN.md), plan
`2026-10-03-zeus-attribution-repair`. User authorized Phase 4 on 2026-10-05
after the [gate review](../../../../../plans/reviews/2026-10-05-phase3-gate-review.md).

**Bounded Phase 4 complete; verdict remains mixed causes.** Git-free validation,
independent-voice tie normalization, symbol coverage and duplicate removal have
supported remedies. Native converter diagnostics are now observable. The isolated
recurrent mask experiment demonstrates a mask-specific decoding effect, but does
not justify adopting padding/masking as a general repair. Recognition remains poor
on most fixed inputs. A fully accepted Zeus pipeline, historical execution-time
provenance and exact traces of malformed output remain unverified.

Research variants are isolated. Shipped Bridge, model weights, token vocabulary,
native converter, scoring tolerance and frozen comparison identities remain
unchanged. Phase 5, screening, training, spending and promotion were not executed.

## Acceptance ledger

| Criterion | Status | Evidence / practical limit |
| --- | --- | --- |
| 4.0 meaningful Git-free validation | Met | Actual pinned source bytes, complete HOMR package file set, revision metadata, model/label/interfaces/import origins and input hashes checked; altered/missing/added source and altered contracts rejected. [Audit](acceptance-audit.json), [compatibility evidence](../../screening/v1/compatibility/homr455-62e6fde61a47.json) |
| Separate historical artifacts from current runtime | Met | Historical freeze hash retained; expanded-visibility current admission records the 33 additional distribution entries under its own identity. [Admission](current-runtime-admission-expanded.json). Equality remains mandatory for the prospectively frozen execution identity. |
| Focused/full green regression | Met | 23 remedy fixtures; full Bridge/research suite **374 passed, 2 skipped, 9 subtests**, zero failures/errors. [JUnit](jobs/final-regression-junit.xml), [supervisor](jobs/final-regression/result.json). Earlier failures retained, not relabeled as passes. |
| 4.1 six segments → four sounding events with independent voice | Met | Exact reproducer retains G3 and merges C4/E4 continuations. Ordinary chords/repeated notes, same-pitch different voice/staff/part, partial ties, tuplets, ambiguous unisons, open/gapped/overlapping ties covered. [Exact/MIDI evidence](tie-acceptance.json), [MIDI](cross-system-chord-tie.mid). |
| General shared normalizer / playback correctness | Unverified beyond bounded variant | Opt-in literal exact MusicXML only. Missing durations and repeats fail closed. MIDI pitch/onset/duration multiplicity verified at 10,080 ticks/quarter; audio output and playback calibration not claimed. A future comparison must apply any accepted normalizer symmetrically to all candidates/references. |
| 4.2 all fixed crops reviewed before inference | Met | 15 inputs / 24 corrected crops; all six contact sheets reviewed prospectively. [Review](crop-review/acceptance.json), [crop identity](crop-manifest.json). Legitimate grand-staff and vocal/piano groups retained; full width and detector coordinates unchanged. |
| Isolate duplicate removal | Met | Only reviewed nested bass fragment removed from openscore-6211555. Cached original systems 1 and 3 yield a separate dedup-only contrast without inference or coordinate changes. [Result](dedup-only-analysis/result.json). |
| 4.3 native diagnostic observability with byte parity | Met | All original 50 outputs byte-identical; private errout exposes 57 lines across 15 outputs. [Replay](conversion-observability.json). Observability is not converter correctness. |
| Padding experiment retaining original valid width | Met | Same padded float pixels/dimensions; only upstream encoder recurrent sequence mask changed. All 24 interventions executed and verified. Two unchanged-mask controls keep identical tokens. [Comparisons](analysis-report.json), [audit](acceptance-audit.json). |
| General padding/conversion repair eligible for adoption | Unmet | Mask changes 22/24 outputs, equals upstream on only 2/24, and one output reaches 700 tokens. Convolution and decoder attention still see padded extent. Malformed native streams do not support reference-free timing reconstruction; no repair selected. |
| Complete fixed execution and all outcomes reported | Met | 72 native outputs, 45 stitched page variants, zero native conversion exceptions / unchanged Bridge page failures; all diagnostics, truncation and zero scores retained. [Full results and duration matrices](analysis-report.json). |
| Exact full-page XML trace / historical provenance | Unverified | 44/45 exact traces unavailable: 41 non-grace notes lacking positive duration, 3 backups before measure start. No inferred timing substituted. Historical execution-time upstream source remains unresolved. Phase 3 is not retroactively fully accepted. |
| Safety and owned-worker cleanup | Met | Every CPU job used the recorded Windows supervisor, 85% RAM/commit stops, 4 GiB reserve, containment and deadlines. No pressure stop, automatic pressure retry or agent Git launch. Failed ordinary validation/preparation receipts preserved. No owned worker/lock at closeout. |

## What changed and why

The original validation failures mixed historical reproduction with today's runtime
and required prohibited Git subprocesses. `phase4_validation.py` verifies revision
metadata directly and compares the actual runtime source inventory and hashes.
Historical screen verification checks immutable recorded artifacts and inputs;
current execution has a separately pinned admission. This does not erase metadata
differences or admit a historical screen as a current live candidate.

`src/sheet2play_omr/research_ties.py` uses exact XML timing and a tie key containing
part, staff, voice and pitch. Only contiguous, unambiguous start/stop segments merge.
Independent notes survive; uncertain tie chains retain events and report issues.
The unchanged Bridge still emits six events on the reproducer; the research variant
emits the four expected sounding events and preserves them through MIDI export.

`phase4_crops.py` expands vertical coverage into verified whitespace. The first
attempt's arbitrary 32-pixel margin/midpoint separator failed on a close system's
slur; the failed crops and receipts remain in `crop-attempt-1` and `jobs`. The
corrected separator occupies a sufficiently wide blank run and never trims the
original box. Visual review confirms complete stems, ledger notes, ties, tuplets,
dynamics, pedal marks and lyrics. The generated baseline's unusual bass-above-treble
layout remains unchanged. This is a reviewed development remedy, not a general
automatic detector claim.

`phase4_conversion.py` routes the pinned native Delinearizer's private errout into
structured diagnostics while preserving output bytes for all 50 replayed streams.
The bounded parity contract covers the observed nonempty native streams. On the
new crops, 10/72 outputs expose 18 diagnostic lines. That change follows changed
recognizer inputs; it is not evidence of a converter logic fix. No malformed
duration, backup or orphan pitch was reconstructed from references.

`phase4_mask.py` temporarily replaces the existing encoder mask call during eager
inference and restores it afterward. Padded image bytes, padded width, weights,
convolution and decoder attention remain identical to the wrapper condition.
Thus wrapper-versus-valid-mask token differences identify a recurrent-mask effect;
upstream-versus-valid-mask differences still include padding/boundary/attention
effects. The result does not identify a universally correct padding policy.

## Fixed development results

These are **diagnostic item-macro** metrics on the same 15 development inputs,
including zero scores. They are not composition-macro benchmark results, paired
superiority evidence or a screening candidate ranking. Primary metrics continue
to use the same Bridge processing for predictions and references; the isolated
tie remedy is not mixed into this crop/mask contrast.

| Condition | Pitch F1 | Onset F1 | Pitch/onset/duration F1 |
| --- | ---: | ---: | ---: |
| Phase 3 original crops, upstream | 0.179290 | 0.013281 | 0.006431 |
| Phase 3 original crops, wrapper | 0.192086 | 0.008595 | 0.004148 |
| Reviewed corrected crops, upstream | 0.263499 | 0.108031 | **0.086350** |
| Reviewed corrected crops, wrapper | 0.242397 | 0.042043 | **0.034547** |
| Same corrected crops/padded bytes, original-width recurrent mask | 0.301326 | 0.065754 | **0.059635** |

The improvement is concentrated: openscore-6211535 upstream primary F1 reaches
0.914414, wrapper 0.257081 and valid-mask 0.706667. Baseline results are 0.277778,
0.238532 and 0.165138 for those conditions. Eleven upstream items and
twelve items in each padded condition still have zero primary F1. This limits
any broad quality conclusion despite demonstrated input defects.

The dedup-only contrast reduces extra notes from 116 to 74 upstream and 102 to 60
wrapper on openscore-6211555, preserving all 69 missing notes; primary F1 stays
zero. It fixes duplicated integration output without fixing recognition.

All 24 crop conditions record vocabulary-valid indices and upstream dataset/direct
prediction parity. No unknown tokens occurred. One valid-mask output on
openscore-6211555 system 2 reaches the unchanged 700-token limit and remains in
the aggregate without tuning, rerun or changed failure policy.

| New condition | Duration majority baseline accuracy | Balanced accuracy | Macro-F1 |
| --- | ---: | ---: | ---: |
| Upstream | 0.470085 | 0.884015 | 0.806396 |
| Wrapper | 0.408163 | 0.424884 | 0.301091 |
| Original-width recurrent mask | 0.432432 | 0.774915 | 0.704680 |

Full confusion matrices, label support, majority baseline macro-F1, unmatched
notes and degeneracy flags are retained in `analysis-report.json`; none of these
conditions is a single-class duration predictor. These duration
diagnostics condition on matched pitch/onset notes and cannot substitute for low
transcription F1 or validate a general duration classifier.

## Reproduction, evidence and next boundary

[Job record](job-record.md) records exact commands, cwd, identities, receipts,
ordinary failed attempts and safety policy. The pre-inference
[experiment manifest](experiment-manifest.json) pins old pipeline/model/source
bytes, new remedy sources, crops, review and the current Zeus import/runtime
contract. The acceptance audit verifies 72 outputs and all immutable pins;
[initial inventory](artifact-inventory.json) records the 605-file pre-documentation
snapshot; the [delivery inventory](artifact-inventory-final.json) excludes mutable
Markdown and includes the closeout receipt. `mask-view` explicitly aliases the valid-mask recipe for the unchanged
analyzer; its duplicate upstream analysis is excluded from aggregates.

No automatic rerun is pending. Next planned action is user review of this bounded
verdict and, only on a separate request, Phase 5 Rokot readiness. A new benchmark
requires its own reviewed proposal and a new candidate identity. The historical
system-memory initiating cause and durable app/system remedy remain unresolved.
