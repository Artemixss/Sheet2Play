# Zeus attribution, shared scoring repair, then Rokot readiness — superseded

**Plan ID:** `2026-10-03-zeus-attribution-repair`.
**Lifecycle:** Superseded on 2026-10-07 by the user-selected
[HOMR 465 and shipped-engine rhythm repairs](../MAIN_PLAN.md).
[Plans/status index](../README.md).

This whole plan is **superseded, not completed**. Phases 1–2 and bounded Phase 4
are complete; Phase 3 execution/reporting finished with qualified acceptance.
Phase 5/Rokot was not executed under this plan and is deferred. Further Zeus,
Rokot and other-engine work is outside the replacement plan.

The original plan text below is preserved, with relative links rebased for its
archive location. Its active/current/next-action and authorization statements
are dated history, not current work orders. Preserve all frozen artifacts,
failed receipts, acceptance limits and experimental evidence.

- [Phase 2 independent closeout](../../Research/omr/reports/zeus-attribution/phase2/closeout-20261004/REPORT.md).
- [Phase 3 report and qualified acceptance](../../Research/omr/reports/zeus-attribution/phase3/REPORT.md).
- [Phase 4 acceptance ledger](../../Research/omr/reports/zeus-attribution/phase4/REPORT.md)
  and [historical handoff](../../Research/omr/reports/zeus-attribution/phase4/handoff.md).
- [October 7 Phase 1 revalidation](../../Research/omr/reports/zeus-attribution/phase1/revalidation-20261007/REPORT.md):
  admission stopped before worker launch; original acceptance retained.

## Original plan text (historical)

# Zeus attribution, shared scoring repair, then Rokot readiness

**Plan directory:** [All plans and lifecycle status](../README.md).
**Location update, 2026-10-04:** This is the canonical active plan. Its former
Research/omr path is a compatibility pointer. Phase and authorization status
are unchanged by this documentation move.

**Workstream:** Zeus attribution, shared scoring repair, then Rokot readiness.
**Plan ID:** `2026-10-03-zeus-attribution-repair`.
**Status:** Active plan; Phases 1–2 and bounded Phase 4 complete. Phase 3 fixed execution/reporting finished with qualified acceptance. Phase 4 completed 15 items/24 reviewed crops/72 native outputs/45 page variants, exact tie/MIDI repair and converter observability; verdict mixed causes. Full regression passes 374 tests, 2 skipped, 9 subtests. Masking is not approved as a general repair; historical provenance and 44 unsupported exact XML traces remain qualified. Phase 5 requires a separate request. No owned worker or automatic rerun. Git remains prohibited; 85% RAM/commit stops, 4 GiB reserve and worker containment remain.

- **Completed:** Phase 1 - reconcile Zeus provenance. Read the
  [Phase 1 handoff](../../Research/omr/reports/zeus-attribution/phase1/handoff.md) and
  [ledger/acceptance evidence](../../Research/omr/reports/zeus-attribution/phase1/REPORT.md).
  [2026-10-07 Phase 1 request](../../Research/omr/reports/zeus-attribution/phase1/revalidation-20261007/REPORT.md):
  existing implementation reviewed; fresh revalidation stopped before worker launch
  at 88.326498% RAM under the unchanged 85% gate. Zero task network transfers;
  original acceptance retained, no automatic retry or later-phase execution.
- **Current handoff:** [Phase 4 authorized execution](../../Research/omr/reports/zeus-attribution/phase4/handoff.md).
  [Phase 4 report and acceptance ledger](../../Research/omr/reports/zeus-attribution/phase4/REPORT.md)
  records the completed bounded remedies and remaining pipeline limitations.
  [Phase 3 execution record](../../Research/omr/reports/zeus-attribution/phase3/handoff.md)
  [Phase 3 report and criterion status](../../Research/omr/reports/zeus-attribution/phase3/REPORT.md)
  records completed inference/analysis, supported causes and acceptance gaps.
  [Phase 2 state](../../Research/omr/reports/zeus-attribution/phase2/handoff.md):
  All 295 cached outcomes rescored; regression, both artifact audits and independent
  implementation/statistical review pass. [Phase 2 acceptance closeout](../../Research/omr/reports/zeus-attribution/phase2/closeout-20261004/REPORT.md).
- **Planner review, 2026-10-05:** [Phase 3 gate review and proposed Phase 4 sequence](../reviews/2026-10-05-phase3-gate-review.md).
  Conditional go for bounded development: validation prerequisites, shared tie
  normalization, then separately reviewed crop/conversion/preprocessing remedies.
  Phase 3 is not fully accepted. The user subsequently requested Phase 4 on 2026-10-05.
- **Next planned step:** user review of the Phase 4 verdict, then separately
  requested Phase 5 Rokot readiness. Phase 4.0 resolved the 14 historical regression
  failures with meaningful Git-free checks and separate historical/current contracts;
  final expanded-visibility regression passed 374 tests, 2 skipped, 9 subtests. Current
  runtime admission explicitly records 33 additional distribution entries, preserving
  the old freeze. All 50 original converter outputs replay byte-identically while
  exposing 57 native diagnostic lines. No automatic pressure retry. Historical
  provenance and unsupported exact XML cases remain limitations.
  [Enforced CPU safeguards](../../Research/omr/reports/zeus-attribution/phase2/safety-fix-20261004/REPORT.md)
  remain mandatory; post-reboot C-only paging allocation is 18 GiB. The successful
  resume did not establish a durable system/app memory remedy. Do not invoke Git
  or start CPU workers directly; inspect live jobs/locks and use the supervisor.
- **Authorization:** Phases 1–4 were requested; Phase 3 explicitly on 2026-10-04 and Phase 4 on 2026-10-05. Phase 2 remains cached-scoring only;
  the user deferred the discovered cross-system chord-tie normalization defect to Phase 3.
  Phase 4 authorizes the bounded remedies below; Phase 5/Rokot execution requires a separate request.

> Saved user-supplied plan, 2026-10-03; renamed for discoverability on the same date.
> Assessment claims below are inherited planning evidence until verified by the relevant
> phase. The [frozen comparison contracts](../archive/2026-09-26-omr-screening-comparison.superseded.md) and historical manifests are preserved.

## 1. Assessment grounded in current evidence

**Diagnose Zeus before judging its model quality or starting another comparison.** The score is reproducible, but the recorded pipeline has a confirmed timing-serialization inconsistency and incomplete source provenance.

| Claim or hypothesis | What is verified |
|---|---|
| “Zeus” might be Rokot | **They are different models.** The screened `zeus_page` uses the TensorFlow recognizer from `ufal/olimpic-icdar24`, checkpoint `zeus-olimpic-1.0-2024-02-12.model`, producing LMX. Rokot uses Qwen and produces ABC. |
| Zeus F1 0.0228 might be an aggregation error | Independently recomputed **0.0228105412** from all 59 cached predictions and their references. All checked reference identities, declared output hashes and checkpoint files matched the frozen records. |
| Zeus was faithfully pinned to upstream | **Not established.** The manifest names `df0d842…`; the imported checkout is `a30b153…`. The inventory hashes local helpers but omits imported upstream recognizer/converter source. Historical execution provenance needs reconciliation. |
| Timing representation is consistent | **False.** References reconstruct rational values with denominator limit 4096; prediction events retain decimal strings, which the scorer interprets as exact fractions. |
| That precision defect explains Zeus’s result | **Mostly no.** Symmetric rationalization diagnostically raises Zeus only to **0.0237688**. It affects all five candidates, so correction must be consistent. |
| Conversion alone explains the failure | Already contradicted on one inspected example: raw LMX misreads the key, opening pitches and quarter-note chords before conversion. This demonstrates recognition errors in the current pipeline, not their dominant cause. |
| Truncation explains most failures | Only **1/324 systems** reaches the 700-token limit. Median predicted timeline is **1.116×** the reference; timing drift deserves investigation. |

The relevant code is the [Zeus wrapper](C:/Users/bur4x/Desktop/lecture/big_projects/Sheet2Play/Research/omr/zeus/zeus_runner.py), [reference rationalization](C:/Users/bur4x/Desktop/lecture/big_projects/Sheet2Play/Research/omr/src/sheet2play_omr/phase3_references.py), and [prediction canonicalization](C:/Users/bur4x/Desktop/lecture/big_projects/Sheet2Play/Research/omr/src/sheet2play_omr/phase2_adapters.py).

The previous recommendation also needs these qualifications:

- **Rokot:** its configuration identifies `Qwen3-VL-2B-Instruct` as the parent. Its card specifies cropped-system input and rokot-ABC output. The **1.5 million samples** figure is publisher-reported; independent training records were not verified. [Model card](https://huggingface.co/rokotmidi/rokot-omr-2b)
- **Benchmark:** the raw leaderboard contains **0.440883 OMR-NED** for a Rokot submission associated with revision `cc947b…`, and **0.904951** for HOMR. Multiple Rokot submissions associated with the same revision have different scores. The leaderboard scores uploaded MusicXML rather than independently running each engine; HOMR’s exact configuration is unspecified. These numbers support investigation, not a local ranking or comparison with F1. [Results](https://huggingface.co/datasets/guangyangmusic/IMSLP-Piano-Scores-leaderboard-results/blob/main/results.csv)
- **Rokot is already tried locally:** corrected development artifacts record 10/12 accepted generated controls and 0/20 accepted complete pages, with truncation, conversion and joining failures. Calling it an entirely new immediate trial overlooks this work.
- **README claims:** the default library currently contains **57 PDFs**, not 46. The active screen uses 59 SMB pages. The installed OLiMPiC collection does contain **2,931 images across 200 score directories**, but the frozen eligible test subset is 1,492 systems. The SMT “16 notes” statement is explicitly historical; it is not verified as current checkpoint performance.
- **MuSViT:** the paper supports 9.7 million pretraining pages. BiLSTM/CTC and LoRA describe its staff-level experiments; full-page piano recognition uses an autoregressive Transformer decoder. Encoder access alone does not supply a usable OMR engine. [Paper](https://arxiv.org/html/2606.31811v1)

## 2. Execution order and assistant allocation

| Phase | Recommended assistant | Deliverable and exit gate |
|---|---|---|
| 1. Reconcile Zeus provenance | **GPT-6.1 Sol — high** | Evidence ledger identifying actual source, weights, vocabulary, preprocessing and conversion versions; unresolved historical provenance explicitly recorded |
| 2. Repair shared timing representation | **GPT-6.1 Sol — medium** | Minimal validated correction, separately versioned scoring identity, refreshed five-candidate scores and statistics |
| 3. Attribute Zeus failures | **GPT-6.1 Sol — high** | Controlled experiments locating errors across recognition, conversion, assembly, normalization and references |
| 4. Implement demonstrated pipeline remedies | **GPT-6.1 Sol — medium**; **high** for validation design and causal review | Validation prerequisites, shared tie repair, then isolated Zeus input/conversion remedies; regression and event-preservation evidence |
| 5. Resolve Rokot readiness blockers | **GPT-6.1 Sol — high** for diagnosis; **medium** for defined repairs | Staged remedies, complete development results and a readiness decision |
| Mechanical execution | **Luna — medium** | Hash inventories, prescribed test runs, resumable rescoring and log summaries; escalate deviations to Sol |

Use Luna after commands and acceptance checks are fixed. Keep causal diagnosis, statistical interpretation and architectural choices with Sol. Model changes remain explicit operator choices.

## 3. Shared repair and Zeus investigation

**Provenance first**

- Record imported module paths and hashes, checkpoint/configuration/vocabulary hashes, actual Git revision, dirty state and TensorFlow version. Include the imported recognizer, delinearizer and symbolic conversion dependencies.
- Compare the local checkpoint bundle with the original published release. Distinguish locally consistent hashes from independently verified release provenance.
- Preserve historical manifests. If execution-time upstream source cannot be recovered, label that uncertainty and create a fully pinned identity for diagnostic replays.

**Correct timing representation**

- Centralize the existing rational reconstruction policy and apply it symmetrically when reading prediction and reference events.
- Validate reconstructed values against MusicXML divisions and exact fixtures before adopting the repair. Preserve genuine timing errors; introduce no onset tolerance, alignment or time warping.
- Preserve historical outputs, scores and Phase-1 artifacts. Create a separate corrected scoring identity and rescore all **295 cached outcomes**, including failures.
- Recompute duration diagnostics, composition aggregates, paired intervals and multiple-comparison statistics. Reuse OMR-NED only where its inputs, implementation and provenance are unchanged and verified.
- Deliver a report showing old versus corrected results. The in-memory calculations above remain diagnostics until this validation passes.

**Run controlled Zeus experiments**

Use all 12 generated controls, the existing representative development page, and two additional open-development pages selected by item ID before inference.

1. Run identical crop bytes through the actual upstream dataset/inference recipe and the local wrapper. The wrapper’s `--mode upstream` label alone does not establish upstream parity.
2. Test the documented preprocessing difference separately: upstream variable-width ragged inputs versus local padding to a multiple of 500. Check valid-width masking, grayscale range, resizing and crop coverage.
3. Check token indexing, unknown-token handling, termination and prediction limits against upstream behavior.
4. Trace native LMX → per-system MusicXML → stitched page → normalized events → scorer. Compare pitches, durations, voices, backups/forwards, divisions and system-boundary offsets at each transition.
5. Validate reference content against images on development controls, including pickups, partial measures and missing-staff rests. Hash agreement alone does not prove musical alignment.
6. Report global metrics alongside explicitly diagnostic measure/system-local metrics to distinguish local errors from accumulated drift.

The verdict must distinguish **integration/evaluation defect**, **poor recognition under a verified pipeline**, **mixed causes**, or **unresolved provenance**. Do not infer universal Zeus quality from this dataset.

A remedy must reproduce and resolve a development failure while preserving musical events elsewhere. Any corrected benchmark run receives a new candidate identity and requires a separately reviewed screening proposal.

### Authorized Phase 4 sequence after the 2026-10-05 review

The [planner review](../reviews/2026-10-05-phase3-gate-review.md) supplies evidence,
limitations and exit gates. The user authorized this bounded execution on 2026-10-05.

1. **4.0 — Validation prerequisites.** Resolve the 12 Git-guard and two historical
   freeze failures with meaningful Git-free verification and separate historical
   artifact/current-runtime contracts. Preserve rejection of altered source,
   weights, labels and inputs; retain old freezes. Pass focused and full regression
   before accepting a repair. Exact diagnostics must support the selected repair;
   unsupported XML cases stay explicit rather than acquiring invented timing.
2. **4.1 — Shared independent-voice ties.** Start with the exact reproducer: preserve
   the independent voice while correctly merging six segments into four sounding
   events. Use an isolated research-only or opt-in normalizer, retain ordinary and
   adversarial event semantics, and check MIDI preservation before playback claims.
   A later comparison must process all candidates and references symmetrically.
3. **4.2 — Crop coverage and deduplication.** Review all fixed inputs before inference
   under a new crop identity. Retain notation and legitimate systems/staff groups;
   resolve the demonstrated clipped symbols and duplicate bass fragment separately
   from coordinate transforms. Preserve all original evidence and failures.
4. **4.3 — Remaining conversion/preprocessing remedies.** Expose native converter
   diagnostics before selecting a repair; byte-identical replay establishes
   observability, not correctness. Test padding with original valid-width masking
   before attributing its effect specifically to masks. Review one isolated remedy
   at a time; no reference-driven reconstruction or silent failure-policy change.

The endpoint is a supported verdict on these bounded remedies. Zeus superiority
is not required to close Phase 4 or review Phase 5; persistent recognition failure
does not authorize repeated tuning/training. Each consequential milestone gets
causal review, meaningful regression and a recorded met/unmet/unverified ledger.
Historical provenance and unsupported full-page traces remain qualified unless
new evidence resolves them. Phase 3 full acceptance must not be inferred from
permission to attempt a demonstrated remedy.

## 4. Rokot follow-up after the Zeus review

Proceed with staged repairs using the existing installed Q8 model and matching projector.

- Reconcile local revision `7add305…` with the benchmark-associated revision by relevant file hashes; do not assume identical weights from the model name.
- Reuse corrected crop evidence. Preserve raw generated text, termination information, conversion diagnostics and joining decisions.
- Address one demonstrated blocker per phase: truncation/runtime handling, strict ABC conversion, then joining of voice and musical state. Follow evidence when determining which blocker to repair first.
- Never reconstruct notes, voices, meter or ties from references. Validate any supported lyric-handling change without discarding notation errors.
- After each repair, run relevant fixtures; after the final configuration is fixed, repeat all 12 generated controls and 20 open pages. Report every accepted and failed item.
- Require conversion contracts, successful complete-page development admission and resource checks before proposing a newly pinned screen. Readiness is not superiority.
- Keep vanilla Qwen as a secondary parent-model experiment. Revisit it when a shared pipeline correction could benefit it; avoid repeating unchanged failures.
- Keep MuSViT as a separate decoder/training feasibility project. HOMR 465 and upstream HOMR developments belong to your separate HOMR plan.

The former overall four-hour Stage 5 limit and one-remedy limit are replaced by these separately validated repair phases. New architecture, model configuration or training requirements trigger discussion before dependent work.

## 5. Validation, limits and completion

Required tests cover rational/decimal equivalence, distinguishable timing errors, tuplets, chords, independent voices, ties across systems, pickups, meter changes, missing systems, invalid outputs and failure accounting. Run relevant fixtures followed by the complete research/bridge regression suite after code changes.

Report primary pitch/onset/duration F1, pitch/onset F1, pitch-only F1, full duration diagnostics, missing/extra notes, chord completeness, per-staff coverage, conversion failures and runtime. Treat staff coverage as a hand proxy only where annotations justify it. Check MIDI event preservation before any playback claim.

For current CPU work, use the recorded supervisor with one heavy worker at a time,
85% physical-RAM/system-commit stops, 4 GiB commit reserve, at most 4 GiB aggregate
worker commit, 16-process containment and deadlines within the existing four-hour
unattended-session limit. Git count/private memory are informational; agent Git
invocation remains prohibited during recovery. Historical 90% device-VRAM
admission rules remain separate and do not override the current CPU policy.
The removed budget was the overall Stage 5 limit. Stop assistant work with
**5% of the five-hour allowance remaining**, saving an exact resumable handoff.

Completion produces a refreshed five-candidate report, a supported Zeus attribution verdict, and Rokot readiness evidence. Training, cloud spending, production promotion and larger confirmation remain separate decisions. The original 2026-10-03 planning pass made no runtime or model changes; subsequent phase evidence and documentation updates are linked above.

for executer: "Maintain a concise handoff linking changed files, verification evidence,
deviations, and unresolved issues. At completion, report each acceptance
criterion as met, unmet, or unverified.
for planner:Inspect the relevant
code and verification artifacts; do not rely only on the executor's summary.

Challenge your original assumptions. Identify missing requirements,
regressions, unsupported conclusions, and remaining risks. Prioritize
required corrections and distinguish them from optional improvements."
