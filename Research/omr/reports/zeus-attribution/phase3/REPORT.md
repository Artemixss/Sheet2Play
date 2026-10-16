# Phase 3 Zeus attribution report — 2026-10-05

Owner: [MAIN_PLAN.md](../../../../../plans/MAIN_PLAN.md), plan `2026-10-03-zeus-attribution-repair`.
**Execution and reporting complete; full acceptance incomplete. Verdict: mixed causes.**
The fixed 15 development items produced 25 crops, 50 recipe/system outputs and 30
stitched pages. Evidence establishes input coverage defects, sensitivity to the
wrapper's padding/masking change, malformed native notation and hidden converter
diagnostics, plus the independent-voice chord-tie normalization defect. These
experiments do not establish universal Zeus model quality or a benchmark ranking.

## Identity, experiment and phase boundary

[Manifest v2](experiment-manifest.json) SHA256
`090da673aeb019010bdc47b7babf8a64143d4706c7d5cdceabf761eb45a42d67` pins all inputs,
references, crops and 17 diagnostic/pipeline sources. Diagnostic runtime identity
`ade1709596afff5023e14bfb73257028ff2bc8521f4ff895ec91dc863b842cbb` passed
[byte verification](verified-bytes.json): 113,385 runtime files plus 50 inherited
detector files. The actual Zeus import probe matches every required field.
Historical execution-time source remains unresolved, as recorded in
[Phase 1](../phase1/REPORT.md); current diagnostic byte parity cannot recover it.

All 12 generated controls, representative `openscore-6211535-page-1`, and additional
`openscore-6211549-page-1`/`openscore-6211555-page-1` were selected before inference.
The actual `LMXDataset.tf_dataset(training=False)` / `Model.predict` path and unchanged
local wrapper consumed identical saved crop bytes. Direct `predict_step` parity
passed 25/25. No model, vocabulary, installed runtime, Bridge normalization, scorer
contract or frozen screening artifact was changed. Research CPU detector setup
explicitly used the existing FP16 weights and original HOMR patch/run/merge code,
CPU provider, 8 intra-op / 1 inter-op threads. Failed float32-path preparation and
setup probes remain preserved in the [job record](job-record.md).

## Supported causes and limits

| Transition | Evidence | Supported attribution / limitation |
| --- | --- | --- |
| Image → crop | [Pre-inference review](CROP_REVIEW.md): eleven single-staff controls clip notation; 6211549 clips bass ledger content; 6211555 has 3 detected crops for 2 engraved systems, including an overlapping bass fragment | Input integration defects are demonstrated. A coordinate-space correction did not establish symbol coverage. Clipped controls cannot judge complete-input recognition |
| Crop → native LMX | Resized prefixes identical 25/25; native sequences differ 25/25; first representative width 1293→1500, encoder-valid steps 81→94 | Wrapper white padding is counted as valid encoder content. The combined padding/mask condition changes decoding; padding pixels versus mask effects are not independently isolated |
| Tokens → MusicXML | 50 EOS terminations, 0 unknown indices, 0 conversion exceptions; 15 outputs carry 57 hidden converter diagnostics; one orphan G3 is discarded | Malformed native grammar plus silent converter error handling are demonstrated. Successful conversion status does not prove lossless conversion |
| System XML → stitched XML | All 30 stitched pages preserve the exact note-element multiset; supplemental parser note counts also agree 30/30 | No note-element loss is observed during stitching. This does not prove every backup, attribute or accumulated boundary offset is correct |
| XML → normalized events | Exact controlled tie reproducer: 6 segments, 4 correctly merged events, 6 unchanged-normalizer events; F1 0.4 | Independent voice interleaving prevents tied chord merging. Layout removal, voice-container consistency and note-type ablations do not resolve it |
| Reference → normalized truth | All 12 generated references match exact merged signatures; 3 open references differ | Evaluation/normalization effects also affect references. Image/reference alignment has explicit hidden-rest and vocal-staff qualifications |

The grayscale/resize content agrees between recipes, with observed float range
approximately 0.00784314–1.000000238. The tiny upper rounding overshoot is not evidence
of a grayscale-scale failure. Upstream variable width and wrapper multiple-of-500
padding are the tested recipe difference; the encoder constructs its mask from
ragged row lengths. Baseline wrapper primary F1 exceeds upstream, so these results
do not justify declaring the upstream recipe universally superior. None of the 50
outputs reached a prediction limit; truncation is not an observed cause in this set.

[Artifact audit](artifact-audit.json) verifies 207 artifact/source/input/reference/crop
hashes, 49/50 native base-pitch multisets, 2,106 typed durations with zero
type/dot/tuplet/division consistency mismatches, and 109 full rests lacking durations.
The base-pitch audit excludes accidental semantics; internal duration consistency
does not mean the recognized durations match the score.

[Conversion replay](conversion-diagnostics.json) uses the pinned Zeus interpreter and
converter sources, explicit `Delinearizer(errout=...)`, and identical filename-based
serialization. All 50 XML hashes match originals. The original wrapper uses a private
StringIO for these diagnostics, so captured stderr is empty even when errors occur.
For `generated-offset_entry` upstream system 1, token `G3` at position 231 is reported
as an additional prefix for `16th` and is discarded: 43 native base pitches become
42 XML pitches. The 50-output replay contains 29 upstream / 28 wrapper diagnostic
lines. Two failed audit attempts are retained: BytesIO used LF in the XML header,
where Windows filename serialization uses CRLF; this difference was identified
before the replay evidence was accepted. No conversion or inference rerun replaced
original outputs.

Literal positive-duration XML tracing is unavailable on all 30 stitched pages due
to missing full-rest durations or backups preceding the measure start. The
[supplemental parser observations](parser-diagnostics.json) use the same Bridge
parser before `stripTies`, with repeats unexpanded and symmetric reference handling.
Music21-inferred rests/timing and backup handling limit these observations; they
are not exact XML event parity. Strict diagnostic failure does not introduce a
new primary failure gate. The incorrect first representative analysis and manifest
v1 are [preserved](resume-20261005-1746/diagnostic-trace-gate-v1/experiment-manifest-v1.json).
Manifest v2 changes only the analyzer source pin; every input/inference/model/
conversion/scoring pin is unchanged, allowing reuse of all cached predictions.

## Global development metrics

These are diagnostic **item-macro** F1 values over 15 items and 619 normalized
reference notes, not composition-macro benchmark estimates. Primary is exact
pitch/onset/duration F1 under unchanged normalization and corrected rational
timing. Missing/extra counts use exact event multisets; pipeline failure means
conversion, stitching or stitched-page normalization failure. Zero pipeline
failures does not imply valid timing or warning-free conversion. Chord completeness
uses exact-onset pitch multisets; staff indices below are not hand labels.

| Recipe | Primary F1 | Pitch/onset F1 | Pitch-only F1 | Predicted notes | Missing | Extra | Pipeline failures | Complete chords |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| upstream | 0.00643092 | 0.01328136 | 0.17929015 | 975 | 602 | 958 | 0 | 1/187 |
| wrapper | 0.00414830 | 0.00859489 | 0.19208641 | 918 | 612 | 911 | 0 | 0/187 |

| Item | Reference notes | Crops | Upstream primary | Wrapper primary | Upstream pitch | Wrapper pitch |
| --- | --- | --- | --- | --- | --- | --- |
| generated-baseline-piano-001 | 56 | 2 | 0.01801802 | 0.03703704 | 0.36036036 | 0.51851852 |
| generated-homophonic | 8 | 1 | 0.00000000 | 0.00000000 | 0.10714286 | 0.15384615 |
| generated-offset_entry | 7 | 1 | 0.00000000 | 0.00000000 | 0.00000000 | 0.12000000 |
| generated-quintuplet_vs_duple | 9 | 1 | 0.00000000 | 0.00000000 | 0.29268293 | 0.21621622 |
| generated-same_position_sustain | 6 | 1 | 0.00000000 | 0.00000000 | 0.05405405 | 0.09523810 |
| generated-septuplet_vs_duple | 11 | 1 | 0.00000000 | 0.00000000 | 0.13333333 | 0.00000000 |
| generated-syncopation | 8 | 1 | 0.00000000 | 0.00000000 | 0.10000000 | 0.26315789 |
| generated-three_voices | 7 | 1 | 0.00000000 | 0.00000000 | 0.13953488 | 0.10810811 |
| generated-tie_across_barline | 3 | 1 | 0.00000000 | 0.00000000 | 0.16666667 | 0.06250000 |
| generated-triplet_vs_duple | 5 | 1 | 0.00000000 | 0.00000000 | 0.10526316 | 0.22727273 |
| generated-triplet_vs_quadruple | 7 | 1 | 0.00000000 | 0.00000000 | 0.14634146 | 0.04878049 |
| generated-tuplet_aligned | 24 | 1 | 0.00000000 | 0.00000000 | 0.10000000 | 0.02469136 |
| openscore-6211535-page-1 | 222 | 5 | 0.04376368 | 0.01342282 | 0.40262582 | 0.40268456 |
| openscore-6211549-page-1 | 177 | 4 | 0.03468208 | 0.01176471 | 0.46242775 | 0.48823529 |
| openscore-6211555-page-1 | 69 | 3 | 0.00000000 | 0.00000000 | 0.11891892 | 0.15204678 |

Full per-item pitch/onset metrics, timelines, voice diagnostics, missing/extra counts
and staff coverage are retained in [analysis-report.json](analysis-report.json).
Eleven clipped generated controls score zero primary F1 for both recipes; the
coverage defect and single-staff domain limit any recognition-quality conclusion.

## Local diagnostics and accumulated drift

Ordinal measures are paired with each measure origin reset, retaining unmatched
measures. Ordinal systems use pre-inference reference boundaries and preserve
leading rests at each part boundary. No alignment, onset tolerance or primary
score change is introduced. The following are **parsed raw-segment** comparisons,
which differ from global normalized tie-merged scoring.

| Item | Upstream measure-local raw F1 | Wrapper measure-local raw F1 | Upstream earliest onset | Wrapper earliest onset |
| --- | --- | --- | --- | --- |
| generated-baseline-piano-001 | 0.01388889 | 0.05648148 | 0 | 0 |
| openscore-6211535-page-1 | 0.03290630 | 0.00445931 | 4 | 4 |
| openscore-6211549-page-1 | 0.08289150 | 0.04354136 | 4 | 1 |
| openscore-6211555-page-1 | 0.00000000 | 0.00000000 | 0 | 0 |

All eleven clipped controls remain zero under measure-local diagnostics. Baseline
and most open systems remain poor locally, so accumulated global drift alone does
not explain the result. Representative upstream system 4 has raw system-local F1
0.57894737 while its page primary F1 is 0.04376368: local content and global timing
can diverge, but raw/merged metric differences also contribute. Both representative
recipes begin pitched content at beat 4. The reference's initially hidden vocal
rest is 4 beats in a 6-beat meter; this is qualified alignment evidence, not a
reference-based prediction repair. All 6211555 ordinal local comparisons are
musically uninterpretable because an extra overlapping crop shifts system pairing.

## Staff coverage and reference qualifications

Historical normalization resets staff indices per part. Baseline reference has two
separate parts whose 56 notes all carry index 0, whereas prediction has one two-staff
part: upstream counts 21/34, wrapper 19/33 for indices 0/1. This cannot support a
left/right-hand recall claim. XML traces preserve part-qualified staff identity;
parser observations use parsed PartStaff ordinals. Open-page index diagnostics:

| Item | Recipe | Historical staff index | Reference | Prediction | Matched | Recall |
| --- | --- | --- | --- | --- | --- | --- |
| openscore-6211535-page-1 | upstream | 0 | 95 | 106 | 2 | 0.02105263 |
| openscore-6211535-page-1 | upstream | 1 | 127 | 129 | 8 | 0.06299213 |
| openscore-6211535-page-1 | wrapper | 0 | 95 | 110 | 0 | 0.00000000 |
| openscore-6211535-page-1 | wrapper | 1 | 127 | 115 | 1 | 0.00787402 |
| openscore-6211549-page-1 | upstream | 0 | 82 | 84 | 4 | 0.04878049 |
| openscore-6211549-page-1 | upstream | 1 | 95 | 85 | 1 | 0.01052632 |
| openscore-6211549-page-1 | wrapper | 0 | 82 | 80 | 2 | 0.02439024 |
| openscore-6211549-page-1 | wrapper | 1 | 95 | 83 | 0 | 0.00000000 |
| openscore-6211555-page-1 | upstream | 0 | 56 | 51 | 0 | 0.00000000 |
| openscore-6211555-page-1 | upstream | 1 | 13 | 65 | 0 | 0.00000000 |
| openscore-6211555-page-1 | wrapper | 0 | 56 | 39 | 0 | 0.00000000 |
| openscore-6211555-page-1 | wrapper | 1 | 13 | 63 | 0 | 0.00000000 |

All 12 generated exact-merged/reference normalized signatures agree. Open-page
exact-merged versus normalized reference events differ: 6211535 220→222, F1
0.98190045; 6211549 177→177, F1 0.98305085; 6211555 68→69, F1 0.97810219.
These are normalization differences, not proof of every reference's musical intent.
First-page boundaries agree with images (19/11/7 measures, 5/4/2 engraved systems).
Baseline boundaries [0,5] are visual evidence because kern import lacks layout.
The syncopation opening eighth rest is not clearly visible; vocal staves are hidden
in piano-only passages and appear later in two open pages. Preserve these
qualifications and references; do not reconstruct missing prediction events.

## Duration classification

Rows are actual, columns predicted, in quarter-note beats; matrices include every
observed class and zeros. Classification is conditional on matched pitch/onset
notes. Unmatched notes remain reported and primary F1 remains decisive. Neither
recipe is single-class degenerate; low match counts limit interpretation.

### upstream

Matched pitch/onset notes: 32; unmatched reference/prediction: 587/943. Balanced accuracy **0.39623932**, macro-F1 **0.31318681**. Majority class `1/2`; majority accuracy **0.40625000**, majority macro-F1 **0.08253968**. Degenerate single-class predictor: **false**.

| Actual / predicted | 1 | 1/2 | 17/2 | 2 | 3/2 | 4 | 8 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 5 | 1 | 0 | 1 | 0 | 0 | 2 |
| 1/2 | 2 | 9 | 1 | 0 | 1 | 0 | 0 |
| 17/2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2 | 1 | 1 | 0 | 0 | 0 | 0 | 0 |
| 3/2 | 1 | 2 | 0 | 0 | 2 | 0 | 0 |
| 4 | 2 | 0 | 0 | 0 | 0 | 1 | 0 |
| 8 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

### wrapper

Matched pitch/onset notes: 15; unmatched reference/prediction: 604/903. Balanced accuracy **0.33035714**, macro-F1 **0.25641026**. Majority class `1/2`; majority accuracy **0.46666667**, majority macro-F1 **0.12727273**. Degenerate single-class predictor: **false**.

| Actual / predicted | 1 | 1/2 | 2 | 3/2 | 3/4 |
| --- | --- | --- | --- | --- | --- |
| 1 | 3 | 0 | 1 | 0 | 0 |
| 1/2 | 1 | 4 | 1 | 0 | 1 |
| 2 | 1 | 0 | 0 | 1 | 0 |
| 3/2 | 0 | 2 | 0 | 0 | 0 |
| 3/4 | 0 | 0 | 0 | 0 | 0 |

## Deferred chord-tie investigation

[Five controlled ablations](resume-20261005-1746/tie-cases/diagnosis.json) isolate the
cause in unchanged music21 9.7.0 `stripTies(matchByPitch=True)`. Original and controls
without new-system layout, with consistent voice containers, or without note-type/
time-modification labels all retain 6 segments and 6 normalized events instead of
4 correctly merged events (F1 0.4). Removing the independent voice produces 5
segments, 3 correct merged/normalized events and F1 1.0. That ablation removes a
musical event and is a causal control, not a valid repair. Adjacent chord matching
is disrupted by independent voice interleaving; the defect is not caused simply
by a page layout marker or rational duration precision.

Prediction normalization versus diagnostic voice/staff-specific parsed tie merging
also differs on baseline wrapper and all open recipes. Parser interpretation and
unmatched/open ties prevent treating every difference as proven intent. The
controlled reproducer establishes the defect without modifying Bridge. A repair
belongs to separately authorized Phase 4.

## Validation, resources and retained failures

75 focused fixtures passed (8.94s; supervisor 15.250s), covering CPU provider/thread
selection, inference recipe/token contracts, rational timing and exact errors,
independent-voice ties, pickup/measure/system timing, invalid inputs/failure policy,
real Bridge acceptance despite unavailable diagnostic XML trace, and live progress
delivery. [Focused receipt](resume-20261005-1746/focused-parser-trace/result.json).
The complete research/Bridge suite finished **328 passed, 14 failed, 2 skipped,
9 subtests passed**. [JUnit](resume-20261005-1746/regression-parser-trace-junit.xml)
and [receipt](resume-20261005-1746/regression-parser-trace/result.json) retain failures.
Failure IDs are unchanged from earlier resume runs: 12 legacy Git-dependent paths
are rejected before subprocess launch by the inherited audit hook; 2 strict
historical-freeze checks detect the documented 33 added metadata entries (16 HOMR,
17 research). No new test was skipped, mocked or xfailed to hide these failures;
the two existing skips remain explicit in JUnit.
Full green regression acceptance is unmet. This is the existing prohibition on
Git during recovery, not an arbitrary test omission.

Every CPU job used the recorded supervisor, one heavy worker at a time, 8 CPU
threads/BelowNormal/allowed affinity, CUDA disabled, 16-process containment and a
deadline. System admission/stops remain 85% physical RAM and commit with 4 GiB
reserve. Detector/model aggregate worker cap remains 4 GiB; byte/audit workers
use 512 MiB. Git count/private memory are informational by explicit user decision.
No assistant Git invocation or external-process termination occurred in this
resume. Receipt wall times include guard/model startup and are not recipe latency.

| Job / receipt | Status | Supervisor seconds | Peak physical RAM | Peak system commit |
| --- | --- | --- | --- | --- |
| [identity-bytes](resume-20261005-1746/identity-bytes/result.json) | complete | 1211.578 | 77.671% | 46.705% |
| [prepare-v2](resume-20261005-1746/prepare-v2/result.json) | complete | 152.984 | 59.672% | 48.863% |
| [infer-representative](resume-20261005-1746/infer-representative/result.json) | complete | 30.782 | 57.073% | 46.926% |
| [infer-remaining](resume-20261005-1746/infer-remaining/result.json) | complete | 98.469 | 57.064% | 48.294% |
| [analyze-all](resume-20261005-1746/analyze-all/result.json) | complete | 11.891 | 55.291% | 44.857% |
| [parser-diagnostics](resume-20261005-1746/parser-diagnostics/result.json) | complete | 11.250 | 54.522% | 44.571% |
| [regression-parser-trace](resume-20261005-1746/regression-parser-trace/result.json) | failed | 33.578 | 55.372% | 47.518% |
| [artifact-audit](resume-20261005-1746/artifact-audit/result.json) | complete | 6.359 | 54.072% | 44.274% |
| [conversion-diagnostics-v3](resume-20261005-1746/conversion-diagnostics-v3/result.json) | complete | 6.641 | 54.298% | 44.364% |

The two recipe timers total 15.515s upstream and 39.330s wrapper; compilation,
different call order and additional upstream direct-parity calls make these
unsuitable for a speed ranking. Representative and remaining inference supervisor
times are 30.782s and 98.469s. The largest physical-RAM peak in the successful
resume was 77.671% during byte verification. No system-pressure failure occurred
in this resume. Earlier actual 97.030% commit and Codex-side diff bursts remain
preserved in the [job record](job-record.md). Async Git telemetry fixes monitor
delay; ignored live logs reduce diff churn. Neither proves a durable resolution
of the initiating app/system memory cause. No pressure failure was retried
automatically. All owned workers are closed and no global job lock remains.
Final [native inspection](resume-20261005-1746/final-native.json) at 19:35 local:
RAM 54.104%, commit 44.227%, 18.542 GiB commit headroom; no Python/Git process
or global worker lock. These are observations at closeout, not a durable crash fix.
The [closeout check](resume-20261005-1746/closeout-check.json) passed: 169 local links
across eight active documents, 207 artifact hashes, three diagnostic script copies,
108 converter/source pins, sidecar identities and the unchanged 14 failure IDs.

## Acceptance by criterion

| Criterion | Status | Evidence / remaining gap |
| --- | --- | --- |
| Fixed 12 controls + representative + 2 preselected open pages | **Met** | Manifest, 15 completed items / 25 crops |
| Verified diagnostic runtime, source and recipe identity | **Met** | Byte verifier, matching actual import probe, source pins, actual dataset/direct parity |
| Historical execution-time source provenance recovered | **Unverified** | Phase 1 uncertainty remains; current parity does not recover historical bytes |
| Grayscale, resize, width/mask and crop-coverage checks | **Met** | Prefix equality 25/25, width/mask evidence, pre-inference visual crop review |
| Complete symbol coverage / valid system enumeration in experiment inputs | **Unmet** | Clipped controls and extra duplicate 6211555 crop; retained for attribution |
| Independently separate white-padding pixels from changed valid-width mask | **Unverified** | Current two-recipe comparison changes both; new isolated condition required |
| Token indexing, unknowns, termination and prediction limit | **Met** | 50 EOS, no unknowns/limit terminations, vocabulary/direct-call contracts |
| Native conversion diagnostics and stitched note-element preservation | **Met** | Byte-identical 50-output warning replay, 30 note-element multiset checks |
| Exact pitches including accidental semantics, durations, voices, backup/forward and boundary parity through every transition | **Unverified** | 30 literal page traces unavailable; parser observations and base-pitch audit have explicit limits |
| Reference image/content validation and qualifications | **Met** | Pre-inference page/control review; explicit syncopation/hidden-rest/vocal limitations |
| All references proven musically aligned with exact normalized truth | **Unverified** | Three open signatures differ; ambiguous opening rest and hidden-staff content remain |
| Global and diagnostic measure/system-local metrics | **Met** | Global report plus symmetric parser observations; ordinal pairing limitation explicit |
| Required metrics, full duration diagnostics, failures and runtime | **Met** | Tables, complete JSON per-item/staff/voice results, guarded receipts |
| Deferred independent-voice chord-tie root cause investigated | **Met** | Five causal controls, exact fixture, unchanged Bridge |
| Relevant fixtures then complete research/Bridge regression executed | **Met** | 75 focused; entire suite executed after final research-code change |
| Full regression passing | **Unmet** | 14 unchanged known failures; frozen identities not rewritten |
| Supported, qualified Zeus attribution verdict | **Met** | Mixed causes; no universal model-quality, ranking or superiority claim |
| RAM/commit containment and clean shutdown | **Met** | Guard receipts, preserved pressure failures, final no-worker/lock inspection |
| Durable initiating memory cause/remedy established | **Unverified** | Successful guarded run does not resolve app-side diff-growth initiation |
| MIDI event preservation / playback correctness | **Unverified** | No MIDI or playback claim made; separate event-preservation gate required |
| Phase 3 boundary preserved | **Met** | Phase 4 remedies, new screening, Rokot, training and promotion require separate requests; whole plan remains unfinished |

## Next boundary

Phase 3's fixed execution and report are finished with the listed acceptance gaps.
Do not repeat inference automatically, rewrite references, alter frozen screening
identities or declare full acceptance. Proposed Phase 4 priorities are symbol-safe
crop coverage/deduplication, observable strict native grammar/conversion failures,
the demonstrated independent-voice tie correction, and an isolated masked-padding
condition. Each needs a separate request and one correction at a time with event
preservation and regression evidence; no accuracy-led promotion is authorized.
Full-green regression requires a safe Git-free verification design and resolution
of historical metadata mismatch without weakening the freeze. Read the
[current handoff](handoff.md) before any continuation.
