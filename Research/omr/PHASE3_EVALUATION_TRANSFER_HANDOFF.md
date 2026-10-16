# Phase 3 evaluation handoff — interrupted run and possible move to another PC

**Lifecycle update, 2026-10-04:** Superseded transfer/continuation proposal, 2026-09-26; preserved as interruption evidence.
[Plans/status index](../../plans/README.md) identifies the owning historical
plan and its successor. Current research phases belong to [the main plan](../../plans/MAIN_PLAN.md);
dated next-step/stop statements below do not authorize new execution.

> **Historical evidence, superseded 2026-09-26.** The user selected the bounded
> [screening comparison plan](../../plans/archive/2026-09-26-omr-screening-comparison.superseded.md) on this PC. The other-PC
> transfer and full 611-page continuation directions below are no longer work
> orders. Preserve their crash, cache, runtime, and audit evidence.

Recorded 2026-09-26, Europe/Istanbul. This was the decision handoff at that date for an
agent discussing how to finish the **reduced pretrained Phase 3 comparison** with
the user. Read the [canonical plan](../../plans/archive/2026-09-26-omr-screening-comparison.superseded.md), [progress review](PHASE3_PROGRESS_REVIEW.md),
[readiness review](PHASE3_READINESS_REVIEW.md), [historical execution handoff](PHASE3_HANDOFF.md),
and [job record](reports/phase3/job-record.md) for the full protocol and history.
The user's latest instruction is to discuss the workload and another PC **before
starting evaluation again**. No process was restarted during this handoff.

## Boundary and decision pending

- Finish the frozen reduced roster only: shipped HOMR complete page, Audiveris
  native page, Zeus neutral corrected page, and Zeus upstream on a separate
  annotated-system track. The eight-page private document is diagnostic only.
- **Do not start Phase 4**, fine-tuned HOMR evaluation, training, rankings,
  production promotion, or a shipped-app publish. Deferred candidates remain
  unevaluated, not zero-scored.
- The user's personal PC hard-froze during the first full inference stage. The
  cause is unknown; empty worker stderr does not identify a driver, thermal,
  memory, or model fault. The user prefers moving the long run to another PC
  if that machine can run it efficiently. Obtain its specifications and agree
  on a validated execution plan before any restart or transfer.

## Exact evaluation size

| Track | Unique inputs | Composition/score grouping | Candidate routes |
| --- | ---: | ---: | --- |
| Primary SMB pianoform pages | 402 pages | 117 composition groups | HOMR, Audiveris, Zeus page |
| Complete SMB pages | 611 pages **including those 402** | 254 composition groups | The same three page routes |
| OLiMPiC annotated systems | 100 system crops | A separate system collection, not 100 complete scores | Zeus upstream only |
| Private diagnostic | 8 rendered pages from one already-inspected score | No verified page-level timing split | HOMR, Audiveris, Zeus page |

Each page route therefore has **611 distinct SMB pages** to infer, although
both 402-page primary and 611-page secondary summaries are scored. The 402
overlapping predictions are intended to be reused after identity checks, not
inferred twice. Across the three page routes that is 1,833 distinct SMB
candidate-page inferences, plus 100 Zeus system inferences and 24 private
candidate-page diagnostics: **1,957 distinct candidate-input runs** in the
complete plan. The private pitch-count diagnostic and system collection must
not be merged into the complete-page ranking. Frozen failures remain in the
denominator.

## Freeze and evidence that existed before the PC freeze

- Configuration: `reports/phase3/phase3-config-freeze-v1-89f385c8790b.json`,
  SHA-256 `3fdd3d76aeab4188244795ea7b5eb310b2129d8d50131290297aeb1a32020633`.
  It pins candidate settings, model and source identities, packages, binaries,
  platform, inputs, scoring, and failure policy. Reverify it before reuse.
- Primary reference audit: 402/402 valid, SHA-256
  `635ffae17143bc93c6fc43171bf0283f605c96b533a4f9f1dfec6a90ed31a89d`.
- Secondary reference audit: 611/611 valid, SHA-256
  `50e5f6942eb2282c37fdecbf5c31b9bb7330224b794620baab1514eb9494b6fb`.
  Its 488 reviewed pedal-import warnings did not break the builder's exact
  sounding-note timing round-trip check.
- OLiMPiC reference audit: 100/100 valid, SHA-256
  `1111a7f43ba8bb5901a9d21f99e217995522c576c4cb5ee9bbccf96c77b43b46`.
- Seven frozen one-item entry commands had completed. The complete research
  test suite passed 115 tests before the current run; the later progress
  review independently reran 16 targeted tests. These do not substitute for
  post-freeze artifact verification.

## Interrupted execution state — do not treat `running` as live

- `Research/omr/.runtime/phase3/sequence/3fdd3d76aeab/state.json` still marks
  stage 1 `primary_homr_page_infer` as `running`, but its old worker PID 26892,
  sequence PID 24440, and one-time completion monitor PID 3292 are all absent.
  **0/20 stages** are recorded complete. The monitor's logs are empty and
  `reports/phase3/PHASE3_COMPLETION_REPORT.md` does not exist.
- The stage stdout ends at **item 255/402**. There are 255 HOMR result JSON
  files and 255 identity sidecars in
  `reports/phase3/evaluation/smb-pianoform/homr_page/`; a 256th raw-output
  directory has no completed report. The last report modification was
  2026-09-26 12:52:26 Europe/Istanbul. The stage and sequence stderr logs
  were empty. **Do not call all 255 results reusable until their identities,
  reports, and declared artifact hashes have been checked after the crash.**
- Logs: `.runtime/phase3/sequence-resume-20260926.{out,err}.log`,
  `.runtime/phase3/sequence/3fdd3d76aeab/primary_homr_page_infer.{out,err}.log`,
  and `.runtime/phase3/completion-monitor.{out,err}.log`. The [job record](reports/phase3/job-record.md)
  also preserves the first interruption and recovery evidence. Do not erase it.
- `phase3_sequence.py` refuses a stale `running` stage or existing stage logs.
  The old monitor command used dead PIDs and must not be relaunched unchanged.
  Its `phase3_completion.py` also assumes the current freeze hash; a new freeze
  requires a reviewed, versioned completion path.

## GPU and wall-clock findings

- HOMR already uses the ONNX CUDA provider with GPU forced. The installed
  runtime lists `CUDAExecutionProvider`.
- The installed Zeus TensorFlow **2.12.1** environment reports zero GPU
  devices and `tf.test.is_built_with_cuda() == False`. Its current page runner
  starts a separate Zeus subprocess and reloads the model for **each detected
  system**. A second NVIDIA GPU on native Windows will not accelerate that
  unchanged runtime. [TensorFlow's installation guidance](https://www.tensorflow.org/install/pip)
  states that 2.10 was the last native-Windows GPU release; newer GPU setups
  use Linux/WSL2 or a separately validated plugin path.
- Audiveris is invoked as a Java/Tesseract batch application with no GPU path
  configured in this comparison. Reference conversion, MusicXML normalization,
  MusicDiff/OMR-NED scoring, and orchestration also require CPU work. The
  whole pipeline cannot simply be switched to GPU.
- Development entry timings on this PC were roughly HOMR 10–15 seconds,
  Audiveris 20–22 seconds, and Zeus page 60–65 seconds per page. Extrapolating
  to 611 unique pages per route gives roughly two hours HOMR, 3–4 hours
  Audiveris, and over ten hours Zeus before full scoring. These are rough
  development-based estimates, not a measured forecast for the other PC.
  A two-hour full benchmark is not credible without measured runtime and
  scheduling improvements. A predeclared smaller subset would be a **pilot**,
  not completion of this Phase 3 protocol.

## Decision and safe continuation for the next agent

1. Ask for the other PC's OS, CPU, RAM, NVIDIA/other GPU and VRAM, free disk,
   and whether Linux or WSL2 is available. Do not assume the other host can
   reuse these Windows virtual environments or binaries. If the user elects
   to reuse the original PC, inspect Windows system/driver evidence for the
   hard freeze before another unattended run; do not assign a cause from OMR
   logs alone.
2. With all workers confirmed absent, back up the stale state and logs; inspect
   the partial raw directory; verify the freeze, reference audits, and all 255
   saved result/sidecar/artifact hashes. Preserve failed candidate outputs as
   valid failure-policy outcomes. Do not launch a duplicate sequence from the
   stale `running` record.
3. On development images only, time the other PC's exact candidate routes.
   For Zeus, first verify a compatible GPU runtime can see the device, then
   measure a complete page including system detection, inference, conversion,
   and stitching. A batched Zeus runner that loads the model once could be
   investigated separately, with output-equivalence fixtures. Do not tune
   against the frozen benchmark pages already observed.
4. Decide the identity path **before** full inference. If the exact pinned
   runtime/configuration and platform verify on the other PC, matching cached
   outputs may be resumed under the same freeze after hash checks. If the
   runtime, GPU backend, runner, or platform changes, create a new versioned
   freeze and keep its results separate; do not silently combine old outputs.
   Run all candidates on the same host for comparable latency/resource claims.
5. Prefer resumable, bounded chunks on the other PC so the user can use this
   PC. Maintain all 611 eligible pages and the unchanged failure policy for
   the full claim. Keep private library material local; plan the eight-page
   diagnostic separately. The comparison's cloud cap remains $10 including
   storage and transfer, and no cloud expense is authorized by this handoff.
6. After all 20 relevant stages and gates complete, rehash the final summaries,
   report primary/secondary/system/private tracks separately with limitations,
   update `PHASE3_HANDOFF.md` and `CONTEXT.md`, and **stop before Phase 4**.

This handoff records a decision point. It is not authorization to restart,
transfer private files, change the frozen scoring rules, or claim a final
engine ranking.
