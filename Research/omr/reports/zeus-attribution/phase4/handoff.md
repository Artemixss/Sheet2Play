# Phase 4 handoff — bounded execution complete

**Lifecycle update, 2026-10-07:** The [owning Zeus/shared repair plan](../../../../../plans/archive/2026-10-03-zeus-attribution-repair.superseded.md)
is superseded by [HOMR 465 and shipped-engine rhythm repairs](../../../../../plans/MAIN_PLAN.md).
This phase's evidence and acceptance limits remain unchanged. Phase 3 stays
qualified; unexecuted Phase 5/Rokot and further Zeus work are deferred.
Read the [new plan handoff](../../homr-timing-465/handoff.md) for current scope.
The dated next-action/authorization statements below are historical; this
documentation transition does not start a new execution phase.

**Lifecycle update, 2026-10-05:** [Bounded Phase 4 complete](REPORT.md), verdict
mixed causes. [Job record](job-record.md), [acceptance audit](acceptance-audit.json).
All 15 inputs/24 reviewed crops/72 native outputs/45 page variants finished.
Exact independent-voice tie/MIDI repair, Git-free validation and byte-identical
converter observability pass. Full regression: 374 passed, 2 skipped, 9 subtests.
Masking is not a general accepted repair; 44/45 exact traces and historical
provenance remain qualified. Research-only variants; shipped Bridge remains pinned.
No owned worker, lock or automatic rerun. Next planned step is user review,
then Phase 5 only on a separate request. No screening/training/spending/promotion.

Final execution evidence: `artifact-inventory-final.json`; excludes mutable
Markdown. Initial `artifact-inventory.json` preserves the earlier snapshot.
Every failed ordinary receipt and partial crop remains preserved. No pressure
stop or automatic pressure retry occurred; maximum RAM/commit peak 58.094%/49.159%.
Git remains prohibited; 85% RAM/commit gates, 4 GiB reserve and containment remain.
Initiating memory cause and durable system/app remedy remain unresolved.

The execution checkpoint below is dated history, **not a pending command**.
Do not rerun completed scripts into existing destinations. Inspect live jobs,
locks and receipts before any later separately authorized execution.

## Earlier execution checkpoint (superseded by completed state above)

Owner: [MAIN_PLAN.md](../../../../../plans/archive/2026-10-03-zeus-attribution-repair.superseded.md), plan
`2026-10-03-zeus-attribution-repair`.

User requested all bounded Phase 4 execution on 2026-10-05 after the
[planner review](../../../../../plans/reviews/2026-10-05-phase3-gate-review.md).
Phase 4 was in progress: validation prerequisites, shared research tie repair,
symbol-safe development crops, then isolated converter/mask diagnostics.
Phase 5, screening, training, cloud spending and promotion remain unauthorized.

No live worker at initial inspection; `.research-worker.lock` absent and
PowerShell found no Python process. CIM process inspection was unavailable in
the sandbox; supervisor admission remains required before any CPU job.

All worker commands use repository root as cwd, the existing
`Research/omr/guarded_execution.py`, 85% RAM/commit stops, 4 GiB reserve,
4 GiB aggregate worker containment, 16 processes and bounded deadlines.
Live receipts/logs go under `Research/omr/.runtime/phase4/`; completed evidence
is copied here. Git launch remains prohibited by inherited audit hooks.
Preserve every failed receipt; do not retry pressure failures automatically.

## Current checkpoint (2026-10-05)

4.0 full regression passes under sandbox and expanded runtime visibility:
364 passed, 2 skipped, 9 subtests. Expanded current admission records all 33
additional distribution entries under a new identity; historical freeze unchanged.
Git-free byte/source-set/revision, vocabulary, weights and import checks reject
real altered inputs. Evidence in `.runtime/phase4/regression-expanded`,
`focused-validation-v2`, `runtime-admission-expanded`, and `compatibility-v2`.

4.1 isolated `src/sheet2play_omr/research_ties.py` preserves voice and merges
six segments into four sounding events; ordinary/adversarial/MIDI fixtures pass.
Bridge/runtime behavior remains pinned and unchanged.

4.2 completed 24 corrected crops for all 15 inputs, six contact sheets visually
accepted before inference in `crop-review/acceptance.json`. Failed preparation
is retained in `crop-attempt-1` and runtime receipts. Midpoint/32-pixel margin
was invalid for a close system's slur; revised separator uses verified blank
space and preserves all symbols. Only explicit contained duplicate removed.

4.3 mask probe passes: upstream `tf.sequence_mask` layer called eagerly with
original valid width, full padded shape unchanged. Research-only monkeypatch
restores original call. It changes recurrent mask only; convolution and decoder
attention remain unchanged, so do not claim a fully width-aware decoder repair.

Next: focused-remedies job, prospective `phase4_experiment.py freeze` with Zeus
interpreter (source/model/import/current-runtime/crop-review verification), then
representative baseline inference and full fixed inference excluding completed
baseline. Each supervised with 4 GiB containment and 85%/4 GiB headroom.
Commands: `phase4_experiment.py infer --item-id generated-baseline-piano-001`,
then `infer --skip-item generated-baseline-piano-001`; deadline 1800 seconds.
Logs: `.runtime/phase4/experiment-freeze`, `representative`, `fixed-inference`.
Inference outputs: `phase4/inference/<item>/system-NNNN/{prediction,mask-prediction}.json`.
Freeze source files before launch; changes require a new prospective identity.
Then replay original 50 conversions with exposed private errout and byte parity;
analyze all 45 page variants, cached dedup-only contrast, exact tie/MIDI evidence;
full final regression, hash/acceptance audit and documentation lifecycle closeout.
No pressure failure occurred; no automatic retry authorized. No worker should
be assumed running after compaction: inspect `.research-worker.lock`, Python
processes and latest supervisor receipt before dependent launch.

Changed files so far: `phase4_validation.py`, Git-free HOMR compatibility and
extension checks, historical-mode `screening_common.py`, and the dirty-source
fixture using real altered bytes rather than mocked Git status.

Validation, acceptance and live command state will be refreshed after each gate.
