"""Render Phase 3 report tables directly from preserved evidence."""
from pathlib import Path
import json

OUT = Path(__file__).resolve().parents[5] / "Research/omr/reports/zeus-attribution/phase3"
EVIDENCE = "resume-20261005-1746"
RECIPES = ("upstream", "wrapper")


def load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def table(headers, rows):
    return "\n".join(["| " + " | ".join(headers) + " |",
                      "| " + " | ".join("---" for _ in headers) + " |",
                      *("| " + " | ".join(str(v) for v in row) + " |" for row in rows)])


def global_tables(analysis):
    aggregates = analysis["aggregate"]
    rows = []
    for recipe in RECIPES:
        row = aggregates[recipe]
        macro = row["item_macro"]
        scores = [item["variants"][recipe]["global"] for item in analysis["items"]]
        rows.append([recipe, f'{macro["onset_duration_f1"]:.8f}', f'{macro["onset_f1"]:.8f}',
                     f'{macro["pitch_f1"]:.8f}', sum(s["predicted_notes"] for s in scores),
                     row["missing_notes"], row["extra_notes"], row["failures"],
                     f'{sum(s["coverage"]["complete_chords"] for s in scores)}/187'])
    text = table(["Recipe", "Primary F1", "Pitch/onset F1", "Pitch-only F1", "Predicted notes",
                  "Missing", "Extra", "Pipeline failures", "Complete chords"], rows)
    rows = []
    for item in analysis["items"]:
        variants = item["variants"]
        rows.append([item["item_id"], item["reference_notes"], item["detected_systems"],
                     *(f'{variants[r]["global"]["onset_duration_f1"]:.8f}' for r in RECIPES),
                     *(f'{variants[r]["global"]["pitch_f1"]:.8f}' for r in RECIPES)])
    return text + "\n\n" + table(["Item", "Reference notes", "Crops", "Upstream primary",
                                    "Wrapper primary", "Upstream pitch", "Wrapper pitch"], rows)


def duration_tables(analysis):
    sections = []
    for recipe in RECIPES:
        row = analysis["aggregate"][recipe]["duration_classification"]
        counts = {(c["actual"], c["predicted"]): c["count"] for c in row["confusion_matrix"]}
        sections.append(f'### {recipe}\n\nMatched pitch/onset notes: {row["matched_pitch_onset_notes"]}; '
                        f'unmatched reference/prediction: {row["unmatched_expected"]}/{row["unmatched_predicted"]}. '
                        f'Balanced accuracy **{row["balanced_accuracy"]:.8f}**, macro-F1 '
                        f'**{row["macro_f1"]:.8f}**. Majority class `{row["majority_class"]}`; '
                        f'majority accuracy **{row["majority_baseline_accuracy"]:.8f}**, majority macro-F1 '
                        f'**{row["majority_baseline_macro_f1"]:.8f}**. '
                        f'Degenerate single-class predictor: **{str(row["degenerate_single_class_predictor"]).lower()}**.\n\n'
                        + table(["Actual / predicted", *row["labels"]],
                                [[label, *(counts.get((label, pred), 0) for pred in row["labels"])]
                                 for label in row["labels"]]))
    return "\n\n".join(sections)


def local_table(parser):
    return table(["Item", "Upstream measure-local raw F1", "Wrapper measure-local raw F1",
                  "Upstream earliest onset", "Wrapper earliest onset"],
                 [[item["item_id"],
                   *(f'{item["variants"][r]["measure_local_parsed_raw"]["macro_onset_duration_f1"]:.8f}' for r in RECIPES),
                   *(item["variants"][r]["earliest_pitched_onset"] for r in RECIPES)]
                  for item in parser["items"] if item["item_id"] == "generated-baseline-piano-001"
                  or item["item_id"].startswith("openscore")])


def coverage_table(analysis):
    rows = []
    for item in analysis["items"]:
        if not item["item_id"].startswith("openscore"):
            continue
        for recipe in RECIPES:
            for staff, row in item["variants"][recipe]["global"]["coverage"]["per_staff"].items():
                rows.append([item["item_id"], recipe, staff, row["reference_notes"], row["predicted_notes"],
                             row["matched_notes"], "unavailable" if row["recall"] is None else f'{row["recall"]:.8f}'])
    return table(["Item", "Recipe", "Historical staff index", "Reference", "Prediction", "Matched", "Recall"], rows)


def resources_table():
    names = ("identity-bytes", "prepare-v2", "infer-representative", "infer-remaining", "analyze-all",
             "parser-diagnostics", "regression-parser-trace", "artifact-audit", "conversion-diagnostics-v3")
    rows = []
    for name in names:
        receipt = load(f"{EVIDENCE}/{name}/result.json")
        rows.append([f'[{name}]({EVIDENCE}/{name}/result.json)', receipt["status"],
                     f'{receipt["elapsed_seconds"]:.3f}', f'{receipt["peak_physical_percent"]:.3f}%',
                     f'{receipt["peak_commit_percent"]:.3f}%'])
    return table(["Job / receipt", "Status", "Supervisor seconds", "Peak physical RAM", "Peak system commit"], rows)


def main():
    analysis = load("analysis-report.json")
    parser = load("parser-diagnostics.json")
    report = """# Phase 3 Zeus attribution report — 2026-10-05

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
42 XML pitches. Fifty recipe outputs contain 29 upstream / 28 wrapper diagnostic
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

""" + global_tables(analysis) + """

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

""" + local_table(parser) + """

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

""" + coverage_table(analysis) + """

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

""" + duration_tables(analysis) + """

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
17 research). No test was skipped, mocked or xfailed to hide these failures.
Full green regression acceptance is unmet. This is the existing prohibition on
Git during recovery, not an arbitrary test omission.

Every CPU job used the recorded supervisor, one heavy worker at a time, 8 CPU
threads/BelowNormal/allowed affinity, CUDA disabled, 16-process containment and a
deadline. System admission/stops remain 85% physical RAM and commit with 4 GiB
reserve. Detector/model aggregate worker cap remains 4 GiB; byte/audit workers
use 512 MiB. Git count/private memory are informational by explicit user decision.
No assistant Git invocation or external-process termination occurred in this
resume. Receipt wall times include guard/model startup and are not recipe latency.

""" + resources_table() + """

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
| Phase 4 remedy, new screen, Rokot, training or promotion | **Unmet / outside current authorization** | Not executed; separate requests required |

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
"""
    with (OUT / "REPORT.md").open("x", encoding="utf-8") as stream:
        stream.write(report)
    print(f"Wrote REPORT.md: {len(report.splitlines())} lines")


if __name__ == "__main__":
    main()
