# Scientific comparison of OMR candidates for Sheet2Play

**Plan ID:** `2026-09-26-omr-exhaustive-comparison`.
**Lifecycle:** Superseded on 2026-09-26 by the [selected screening plan](2026-09-26-omr-screening-comparison.superseded.md);
archived in the plans directory on 2026-10-04. This proposal was not completed
as written. Its original planning text follows as reference evidence;
prospective instructions and phase numbering are historical.
[Current plan](../MAIN_PLAN.md); [all plans](../README.md).

The original exhaustive comparison snapshot remains unchanged at
[COMPARISON_PLAN.before-screening.md](../../Research/omr/.runtime/plan-retirement-20260926/COMPARISON_PLAN.before-screening.md).

> **Canonical plan with 2026-09-23 and 2026-09-26 amendments.** The original scientific protocol below
> remains the frozen foundation. The expanded comparison amendment in this document governs
> remaining execution wherever it changes roster, phase sequence, or approval baseline.
> Historical measurements remain evidence, not eligible rankings.

## Phase 4 upstream HOMR extension — 2026-09-26

The user requested adding the reported upstream developments to the plan only.
**This amendment authorizes documentation changes, not execution.** Preserve the
current Phase 3 configurations, results, and `comparison-config-v2.json`; do not
upgrade the installed HOMR environment or restart any job for these additions.

Phase 4 now has baseline and challenger evaluation, a development diagnostic, and a
conditional combined-configuration evaluation, detailed in
[Phase 4 HOMR extension plan](2026-09-26-homr-extension.superseded.md):

- **4A — Fine-tuned HOMR:** retain the existing verified-checkpoint intake, development
  selection, and evaluation. This remains the approval baseline.
- **4B — Upstream HOMR challengers:** evaluate **HOMR-455 upstream** as a new pretrained
  configuration, then **HOMR-PR156 multi-voice** if matching updated weights and decoder
  can be verified. Model 455 is not the PR #156 model. The PR #156 entry updates the
  existing conditional candidate's planned intake; it is not an extra duplicate model.
- **4C — Issue #161 meter-export diagnostic:** check the reported duplicate/conflicting
  time-signature behavior on development fixtures. This is an integration investigation,
  not another model. Only a demonstrated, validated remedy becomes a separately pinned
  pipeline variant of the affected model; run this prerequisite before evaluating that
  variant, regardless of the subsection numbering.
- **4D — HOMR-Combined:** conditionally evaluate one compatible combined configuration
  after the isolated development checks: verified multi-voice weights/decoder, applicable
  455-era changes, and a validated #161 remedy if needed. This is a pipeline configuration,
  not proof that model 455 weights support PR #156's representation. Missing compatible
  weights or a need for retraining means deferred, not permission to train. The user's
  follow-up explicitly adds this combined entry to the plan only.

Do not bundle all upstream news into a moving “455 HOMR” configuration. Pin each model's
source, weights, tokenizer, decoder and patches. Test any #161 fix against the same
model without that fix. A later combined configuration requires its own identity and
compatibility evidence; a PR number or new release alone does not prove improvement.

Future execution requires an explicit request. Create a new configuration manifest for
the extension at that time rather than modifying the active freeze. Inherit frozen
scoring, development-only settings selection, failure handling, training-overlap
disclosure, resource limits, and the unchanged promotion gate. Phase 5 must account for
the added comparisons. Rokot, Qwen, LEGATO and conditional MuSViT remain on the expanded
roadmap; this HOMR extension neither removes them nor starts their development work.

## Expanded comparison amendment — 2026-09-23

The user supplied a new plan that expands the comparison without restarting completed
Phases 1 and 2. The versioned [comparison configuration](../../Research/omr/comparison-config-v2.json)
references the unchanged Phase-1 scoring protocol and records eight candidate entries
plus conditional MuSViT research. The completed Phase-2 report is historical; Phase 2R
closes the [readiness-review](../../Research/omr/PHASE2_READINESS_REVIEW.md) gaps and extends development
adapters before any frozen evaluation.

**Candidate order:** verified fine-tuned HOMR as the new approval baseline; shipped HOMR
as historical control and fallback; Rokot Q8 with its matching vision projector; vanilla
Qwen3-VL-2B-Instruct as Rokot's parent-model control; LEGATO; Zeus upstream and app paths;
Audiveris; and HOMR PR #156 only if compatible weights are verified. Zeus paths and
precision variants are configurations, not independent models. MuSViT is conditional:
verify a usable recognition decoder checkpoint and conversion path; otherwise record
“requires training—not evaluated” and prepare a separate future proposal.

**Phase 2R only:** replace literal-success empty-output and missing-system fixtures with
executed detection, typed failure, and zero-F1 aggregation checks. Verify actual model
weights, source and patch state, tokenizers/processors, converters, and executables.
Run genuine LEGATO and Audiveris development smokes where technically possible. Exercise
all 12 generated controls and 20 open development compositions, including ties, tuplets,
independent voices, meter changes, and multi-system joins. Implement Rokot first and Qwen
second using the neutral adapter contract. Both start on annotated system crops, then use
the same frozen detector/crop policy for complete pages; preserve raw text, MusicXML,
canonical events, failures, resources, and provenance. Use deterministic decoding,
development-selected settings, strict symbolic conversion, and no manual or reference-guided
repair. Preserve system order and inherited musical state across joins. MuSViT feasibility
is investigated without beginning new training.

**Later phases:** Phase 3 freezes ready configurations and runs the pretrained comparison.
Phase 4 evaluates a verified, development-selected fine-tuned HOMR checkpoint and the final
checkpoint if different, plus the separately versioned upstream HOMR extension above.
Phase 5 performs paired statistics, separate accuracy and practical
rankings, and a recommendation. The fine-tune must be verified and selected on development
data before a final replacement decision. SMB, OLiMPiC, and the one eligible private
diagnostic retain their frozen roles and exclusions. Newly added candidate training overlap
is disclosed in a sidecar without changing frozen manifests. Keep composition-grouped
bootstrap intervals, Holm correction, full duration diagnostics, failure-penalized metrics,
and separate system versus complete-page results. Only complete-page results can support an
app replacement recommendation.

The replacement gate now compares against **fine-tuned HOMR**: primary F1 gain at least
0.03 absolute with statistical support; pitch F1 loss at most 0.01; failure rate and
failure-penalized OMR-NED increases at most 0.01 each; no demonstrated conversion or
stitching corruption; and the frozen practical latency and resource requirements. Also
report against shipped HOMR. A regression in the fine-tune does not justify replacing a
better shipped engine. A qualifying candidate requires a separate opt-in integration phase;
this plan does not authorize automatic promotion.

Keep local-first execution, the $10 total cloud cap including storage and transfer, and
private library files local. Estimate from development runs before cloud use. Do not
compete with or restart the separate HOMR training. New MuSViT training is a separate
research stage whose proposal must include a decoder, faithful labels, held-out evaluation,
compute budget, and this project's generator.

## Execution status and reading order

Read [repository instructions](../../AGENTS.md), the startup section of
[project context](../../CONTEXT.md), this plan, and the active
[Phase 2 handoff](../../Research/omr/PHASE2_HANDOFF.md) before phase implementation. Before Phase 3,
check the later [readiness review](../../Research/omr/PHASE2_READINESS_REVIEW.md) against current evidence;
the historical completion report alone does not resolve its recorded gaps. Consult the
[Phase 1 handoff](../../Research/omr/PHASE1_HANDOFF.md) for freeze details and
[historical findings](../../Research/omr/reports/diagnosis/FINDINGS.md) for specific prior evidence.

| Phase | Status as of 2026-09-24 | Execution boundary |
| --- | --- | --- |
| 1. Audit and freeze | Complete; evidence in the handoff | [Frozen report](../../Research/omr/reports/phase1/phase1-report.json), [checklist](../../Research/omr/reports/phase1/phase1-plan-checklist.json), [scoring protocol](../../Research/omr/reports/phase1/scoring-protocol.json) |
| 2. Original adapters and fixtures | Historical completion; readiness gaps recorded | [Historical report](../../Research/omr/reports/phase2/phase2-report.json), [readiness review](../../Research/omr/PHASE2_READINESS_REVIEW.md) |
| 2R. Readiness and expanded adapters | Executed and [coordinate correction completed](../../Research/omr/PHASE2R_CORRECTION_HANDOFF.md); original [handoff](../../Research/omr/PHASE2R_HANDOFF.md) is historical | Selective development readiness; not blanket Phase-3 approval |
| 3. Pretrained comparison | Entry preparation started 2026-09-25; frozen inference not started; see [handoff](../../Research/omr/PHASE3_HANDOFF.md) | Freeze reduced ready roster, then run frozen evaluation inference |
| 4. Fine-tuned baseline and upstream HOMR extension | Planned; extension added 2026-09-26, not executed by this amendment | 4A fine-tune; 4B model 455 and verified updated PR #156; 4C issue #161 diagnostic; 4D conditional HOMR-Combined; [details](2026-09-26-homr-extension.superseded.md) |
| 5. Rankings and recommendation | Not started | No automatic engine replacement |

The handoff records actual counts and exclusions, including the additional frozen parent
OLiMPiC partition and only one eligible local diagnostic pair. These do not silently revise
the plan's primary ranking. Keep frozen artifacts unchanged and disclose discrepancies.
The supplied plan's references to ongoing training and available releases describe its
planning context; verify their status before the relevant phase, without restarting training.
A material change to scope, scoring, or acceptance requires an explicit decision recorded
here and in the relevant handoff. The amendment above is that decision for the expanded
roster and fine-tuned approval baseline; the Phase-1 scoring protocol remains frozen.

---

## 1. Objective and decisions

Determine whether another available engine can improve dense-piano transcription over HOMR, and whether Zeus’s earlier failures came from recognition, conversion, or Sheet2Play’s integration.

Produce **two rankings**:

1. **Recognition accuracy:** performance on identical held-out material, independent of hardware suitability.
2. **Practical suitability:** accuracy plus local memory requirements, processing time, failure rate, and integration effort.

The current HOMR fine-tune continues unchanged. This project phase evaluates existing checkpoints; it does not start another training run or replace the shipped engine.

| Candidate | Role |
|---|---|
| Shipped HOMR | Mandatory reference baseline; freeze its current weights, patches, and settings. |
| Completed HOMR fine-tune | Evaluate after the run finishes, using the same decoder as the reference. |
| HOMR PR #156 | Test the voice-aware representation and compatible weights, if obtainable. Missing weights mean “not evaluated,” never a guessed result. |
| LEGATO | Principal new candidate, using the released specialized OMR checkpoint and approved Llama vision encoder. |
| Zeus | Mandatory reassessment using both upstream inference and the existing app integration. |
| Audiveris | Mandatory automated baseline, measuring rhythm and broader notation quality separately. |

Plain Llama Vision, older SMT checkpoints, ensembles, and training from scratch are outside this comparison. LEGATO 2 remains a research lead until a documented, compatible release is verified.

Audiveris is a hybrid system, including neural classification; classify candidates by measured behavior rather than “traditional versus AI.” [Audiveris architecture](https://github.com/Audiveris/audiveris)

## 2. Establish trustworthy inputs and measurement

**Audit historical evaluation before reusing its numbers.**

The existing [**eval_zeus_on_olimpic.py**](../../Research/omr/eval_zeus_on_olimpic.py) averages each engine’s successful samples separately and uses different extraction paths. Its historical averages are exploratory evidence, not a reliable ranking.

Inventory existing reports and retain only results with identifiable inputs, checkpoint, code revision, preprocessing, scorer settings, and failure counts.

**Freeze three evaluation collections.**

- **Primary: SMB pianoform pages.** Use the released test partition and its page/region ground truth. Evaluate all eligible pianoform pages; report their actual count after metadata inspection.
- **Secondary: complete SMB and the existing 100-system OLiMPiC canary.** Report them separately. OLiMPiC is a regression collection, with known repertoire overlap concerns—not independent proof of generalization.
- **Application diagnostics: the seven confirmed local score/reference pairs.** Verify edition, page coverage, pickup measures, repeats, and transcription alignment. Existing inspected examples remain diagnostics, not an untouched test set.

SMB stays out of training and checkpoint selection. Its current card specifies **CC BY-NC 4.0**; correct the old downloader metadata before future use. [SMB dataset and annotations](https://huggingface.co/datasets/PRAIG/SMB)

Create a separate development collection from **20 openly licensed piano compositions outside the evaluation collections**, plus **12 controlled examples from our own generator**. Check composition overlap, not just file hashes. Use this collection for adapter debugging and any inference-setting selection.

For each evaluation item, record:

- Source revision, file hash, composition/edition group, page/system identity, and ground-truth provenance.
- Printed versus scanned source and relevant notation features.
- Known, absent, or unknown overlap with each model’s training data.

Validate references before viewing candidate predictions. Exclude defective references identically for every engine, retaining an exclusion ledger. If source grouping or training provenance cannot be established, disclose that limitation rather than labeling the collection “unseen.”

## 3. Separate the model from its surrounding pipeline

Implement isolated research adapters using the existing benchmark and metric infrastructure. No frontend API changes are required.

Each adapter accepts an input item and frozen configuration, and preserves:

- Native output: HOMR tokens, Zeus LMX, LEGATO ABC, or Audiveris output.
- MusicXML before shared normalization.
- Canonical note events after normalization.
- Exit status, warnings, stage timings, memory measurements, and complete provenance.

Use three measurement paths:

| Path | What it isolates |
|---|---|
| **Reference round trip** | Convert known symbolic truth through an engine’s representation and back, without recognition. Separates conversion defects from representational limitations. |
| **Recognition with annotated crops** | Supply identical ground-truth system regions to compatible system recognizers. Measures recognition with segmentation removed. |
| **Complete document pipeline** | Start from the same page images, including segmentation, recognition, conversion, and stitching. This determines the deployable ranking. |

Full-page engines retain their intended input granularity. Do not force every architecture into system crops and call that a fair universal comparison.

**Zeus investigation**

Use the existing checkpoint with its upstream preprocessing and decoding settings, then compare against [**zeus_engine.py**](../../Research/omr/src/sheet2play_omr/zeus_engine.py).

Test these differences separately on development examples:

- Annotated crops versus HOMR-detected crops.
- Upstream resizing/padding versus the local width-bucketing implementation.
- Native LMX versus delinearized MusicXML.
- Individual systems versus stitched documents.
- Shared normalization versus the app’s existing event extraction.

Preserve part identity, ties, inherited meter/key/clef state, and pickup timing across joins. A fix is justified only when a controlled comparison demonstrates the defect.

**Other adapters**

- LEGATO: use its dedicated checkpoint and loader. Measure actual memory; do not assume the complete 11B Llama language model is loaded. Audit ABC-to-MusicXML conversion independently. [LEGATO implementation](https://github.com/guang-yng/legato)
- Audiveris: pin a stable release and use unattended processing. No manual corrections or score-specific test-set switches.
- HOMR: compare checkpoints with identical preprocessing and decoding first. Treat PR #156 as a separate model-and-decoder combination.

Render PDFs once at 300 DPI and preserve those images. Allow documented engine-specific internal scaling. Any alternative rendering or decoding settings must be selected on development data and frozen before testing.

## 4. Metrics, tests, and acceptance rules

**Primary metric:** composition-macro **pitch + onset + duration F1**, measured in rational quarter-note time.

Report alongside it:

- Pitch-and-onset F1 and pitch-only F1.
- OMR-NED, with pinned parser, library version, and notation-detail settings.
- Duration confusion matrix for correctly pitch/onset-matched notes, including dotted values and tuplets; report unmatched notes separately.
- Missing/extra notes, missed systems, invalid output, timeout, and complete-document failure rates.
- Timeline length error and first measure where timing diverges.
- Median and 95th-percentile processing time, cold-start time, peak RAM/VRAM, and actual cloud cost.

Use the same event semantics for every engine: merge tied continuations into sounding durations, preserve pickups, disable repeat expansion for printed-page scoring, and exclude grace notes from the primary duration metric while reporting them separately. Test expanded-repeat playback separately.

Do not shift, stretch, or align predictions to the reference for headline results. Any alignment-assisted analysis must be labeled diagnostic.

**Prevent misleading results.**

- Every engine receives the same eligible items.
- Failed predictions receive zero primary F1 and appear in failure counts.
- Report valid-output OMR-NED and a separately labeled failure-penalized summary; never silently drop failures.
- Include constant-duration majority baselines and macro-F1/balanced accuracy for duration classification. High recall for one duration cannot justify a checkpoint.
- Report results by independent voices, cross-staff writing, ties, tuplets, meter changes, density, and document length.
- Compute paired confidence intervals with 10,000 bootstrap resamples grouped by composition. Apply Holm correction to primary superiority tests across challengers. Do not treat pages from one score as independent samples.

**Test the evaluation machinery itself.**

Fixtures must cover identical scores, an omitted note, an inserted note, shifted onsets, tied versus sustained equivalents, overlapping voices, tuplets, pickups, meter changes, repeats, empty output, malformed XML, and a missing middle system.

Include a source-MusicXML-to-app control: when recognition is bypassed, canonical events must survive the bridge unchanged. This identifies app problems that no replacement model can fix.

**Predeclared replacement gate**

A candidate qualifies for promotion consideration only if it:

- Improves primary F1 by **at least 0.03 absolute** over shipped HOMR, with statistically supported superiority.
- Loses no more than **0.01 absolute pitch F1**.
- Worsens neither failure rate nor failure-penalized OMR-NED by more than **one percentage point**.
- Shows no reproducible conversion or stitching defect that corrupts otherwise correct recognition.

These are project acceptance thresholds, not claims about a universal scientific standard. If results are inconclusive, report that and retain HOMR.

## 5. Execution, budget, and deliverables

Run the work in this order:

1. Audit historical results, freeze datasets and scoring rules, and validate reference conversions.
2. Build adapters and verify them on development fixtures.
3. Run the frozen pretrained comparison while HOMR training continues elsewhere.
4. After training finishes, select the fine-tuned checkpoint on development data and evaluate it plus the final checkpoint on the frozen benchmark. Under a separately authorized Phase 4 extension, evaluate pinned upstream model 455 and verified updated PR #156; investigate issue #161 on development data and version any validated pipeline remedy separately.
5. Produce both rankings and a recommendation: retain HOMR, repair an integration defect, evaluate a replacement for shipping, or pursue targeted fine-tuning.

Use the local **6 GB GPU first**, without competing with the separate training machine. Cloud use is capped at **$10 total**, including storage and transfer. Estimate cost from development runs before launching a full cloud benchmark; stop rather than exceed the cap. Keep private library files local.

For the practical ranking, default eligibility requires unattended local operation, peak VRAM below 90% of installed capacity, peak RAM below 75% of physical memory, and 95th-percentile page latency no worse than twice HOMR’s on the same machine. Report accuracy winners separately if they miss these limits.

Deliver:

- Pinned manifests, configurations, environment records, and reproducible commands.
- Raw predictions and stage-level artifacts.
- Per-item metrics, confidence intervals, failure ledger, and feature breakdowns.
- A Zeus attribution report showing which differences arise before recognition, during conversion, or inside the app.
- Separate accuracy and practical rankings, including “not evaluated” entries and limitations.
- A follow-on training proposal only if results identify learnable failures with faithful labels; retain our generator and keep SMB held out.

No automatic engine replacement follows the benchmark. A qualifying candidate enters a separate opt-in integration and release phase.

