# Phase 4 job record — 2026-10-05

Owner: [MAIN_PLAN.md](../../../../../plans/MAIN_PLAN.md), plan
`2026-10-03-zeus-attribution-repair`; user authorized all bounded Phase 4.
Completed. [Verdict/acceptance](REPORT.md), [continuation handoff](handoff.md).

All commands used repository cwd
`C:\Users\bur4x\Desktop\lecture\big_projects\Sheet2Play` and this supervisor:

```powershell
$env:PYTHONPATH = 'Research/omr/src;Research/omr;Research/omr/.runtime/phase4/gate'
& Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py `
  --output Research/omr/.runtime/phase4/fixed-inference --max-seconds 1800 -- `
  Research/omr/zeus/.venv/Scripts/python.exe -B Research/omr/phase4_experiment.py `
  infer --skip-item generated-baseline-piano-001
```

This is the recorded completed invocation, not an automatic rerun instruction.
Default 85% physical RAM/system commit stops, 4 GiB commit reserve, aggregate
4 GiB worker limit, 16 processes, one heavy worker and deadlines retained.
Smaller admission/diagnosis jobs used 1 GiB containment where recorded. CPU-only,
eight-thread/affinity/below-normal configuration inherited. Exact per-job command,
pid, interpreter, cwd, limits, operational-source hashes and resource samples are
in each receipt/log. Source/model/input/review/configuration identities are in
[experiment-manifest.json](experiment-manifest.json), [crop-manifest.json](crop-manifest.json)
and [expanded runtime admission](current-runtime-admission-expanded.json).

| Job | Outcome | Evidence |
| --- | --- | --- |
| compatibility | Complete; initial prerequisite receipt preserved | [Receipt](jobs/compatibility/result.json) |
| focused-validation | Failed: lowercase regex versus capitalized diagnostic; no source-validation bypass | [Receipt](jobs/focused-validation/result.json), [log](jobs/focused-validation/worker.log) |
| compatibility-v2 | Complete after verification-dependency pin and diagnostic correction | [Receipt](jobs/compatibility-v2/result.json) |
| focused-validation-v2 | 27 passed | [Receipt](jobs/focused-validation-v2/result.json) |
| regression-validation | 364 passed, 2 skipped, 9 subtests | [Receipt](jobs/regression-validation/result.json) |
| runtime-admission | Sandbox snapshot matched historical freeze; visibility-limited evidence | [Receipt](jobs/runtime-admission/result.json) |
| runtime-admission-expanded | Full visibility records 33 added distribution entries; new identity | [Receipt](jobs/runtime-admission-expanded/result.json) |
| regression-expanded | 364 passed, 2 skipped, 9 subtests under full visibility | [Receipt](jobs/regression-expanded/result.json) |
| focused-crops | 17 passed before separator refinement | [Receipt](jobs/focused-crops/result.json) |
| crop-preparation | Failed before inference: no whitespace-safe boundary | [Receipt](jobs/crop-preparation/result.json), [log](jobs/crop-preparation/worker.log) |
| crop-boundary-diagnosis | Intentional reproduction of boundary rejection; printed actual blank runs | [Receipt](jobs/crop-boundary-diagnosis/result.json) |
| crop-preparation-v2 | Complete; all 24 systems prepared and visually reviewed | [Receipt](jobs/crop-preparation-v2/result.json), [review](crop-review/acceptance.json) |
| mask-probe | Complete; actual upstream encoder consumed original-width mask | [Receipt](jobs/mask-probe/result.json), [log](jobs/mask-probe/worker.log) |
| focused-remedies | 23 passed, including refined separator | [Receipt](jobs/focused-remedies/result.json) |
| experiment-freeze | Complete prospective pins/import/runtime/review verification | [Receipt](jobs/experiment-freeze/result.json) |
| representative | Baseline's two systems, all three conditions complete | [Receipt](jobs/representative/result.json) |
| conversion-replay | Failed: archived helper's original relative root resolved to `Research/Research`; no conversion started | [Receipt](jobs/conversion-replay/result.json) |
| conversion-replay-v2 | Explicit repository/source roots supplied to unchanged archived helper; all 50 byte-identical | [Receipt](jobs/conversion-replay-v2/result.json) |
| representative-check | Baseline unchanged event analysis passed | [Receipt](jobs/representative-check/result.json) |
| fixed-inference | Remaining 14 items/22 systems/66 outputs complete, no retry | [Receipt](jobs/fixed-inference/result.json) |
| fixed-analysis | All 15 items/45 pages, dedup-only contrast, exact tie/MIDI evidence complete | [Receipt](jobs/fixed-analysis/result.json) |
| final-regression | 374 passed, 2 skipped, 9 subtests; full runtime visibility | [Receipt](jobs/final-regression/result.json), [JUnit](jobs/final-regression-junit.xml) |
| closeout-audit | 72 outputs/current sources/model/crops/masks/old freeze verified, regression failures zero | [Receipt](jobs/closeout-audit/result.json), [audit](acceptance-audit.json) |
| delivery-verification | Failed: link check ran before its own final inventory was generated; no experimental result changed | [Receipt](jobs/delivery-verification/result.json) |
| delivery-verification-v2 | File hashes passed; link check rejected the supervisor receipt which can only be copied after its worker exits | [Receipt](jobs/delivery-verification-v2/result.json) |
| delivery-verification-v3 | Final file hashes and document links checked; supervisor receipt copied after completion | `jobs/delivery-verification-v3/result.json` |

No pressure failure occurred. Highest recorded execution peak was 58.094% physical
RAM and 49.159% system commit in fixed inference. External Git processes were
observed informationally; the worker launch guard stayed inherited and this
execution invoked no Git command. Ordinary failures were diagnosed before any
corrected invocation; all receipts remain. `crop-attempt-1` retains partial failed
crop preparation. No inference output was overwritten or repeated.

The native/private converter diagnostic replay remains byte-identical. The mask
experiment preserves padded pixels and dimensions and records actual valid/padded
steps per output. Dataset/direct upstream parity is checked for every crop; raw
LMX, token IDs, termination, elapsed time and diagnostics are retained.

The initial 605-file inventory predates final documentation; final delivery
verification checks a separate inventory excluding mutable Markdown, links in
changed startup/plan/handoff documents, and worker closure. Its command is
`Research/omr/.venv/Scripts/python.exe -B Research/omr/phase4_verify_delivery.py`
under the same supervisor, deadline 120 seconds, receipt
`.runtime/phase4/delivery-verification-v3`. This final supervisor receipt is
copied after verification and is outside the inventory it supervised.

Completed jobs own no live worker or `.research-worker.lock`. No automatic rerun.
Next planned step: separately requested Phase 5; no screening/training/promotion.
