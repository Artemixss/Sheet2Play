# Upstream exporter and run 480: handoff

**Owning plan:** [`2026-10-17-upstream-exporter-480`](../../../../plans/2026-10-17-upstream-exporter-480.md),
authorized 2026-10-18 ("approved, download run 480 weights and test the new things").

## State

**Step 1 (provision) is done.** `homr_480_download.py` fetched run 480's FP16 encoder, its FP32
decoder and upstream main `ab369ac` (64.8 MB, three requests, no retries), each matching the
digest the GitHub release API listed. They live in `Research/omr/.runtime/homr-480-upstream`
(ignored); [acquisition.json](acquisition/acquisition.json) and the
[network budget](acquisition/network-budget.json) are the receipts. The shipped 465 runtime,
its profile and its caches are untouched. Upstream main still defaults to 465, adds no
dependencies, and leaves the vocabulary and decoder code unchanged.

Run 480 has no FP16 decoder, and upstream's CUDA path always loads the FP16 one. The research
launcher `homr_upstream_native.py` therefore reads the decoder's precision from its own inputs;
the FP16 465 decoder is unaffected. So 480 runs as FP16 encoder plus FP32 decoder, the only GPU
pairing upstream publishes, and its comparison with 465 mixes weights with decoder precision.

**Steps 2-3 are built, not yet run.** [candidates.json](candidates.json) pins two candidates on
`ab369ac`: `homr465-ab369ac` (465 weights, separating the exporter and staff-detection
changes) and `homr480-ab369ac`. `upstream_capture.py` runs them through `dist/Bridge`'s own
`run_homr_engine`, with only the page recognizer swapped, and checks that every rendered page
hashes to the one the shipped `homr465` capture recognised. Captures go beside the shipped
ones in `data/displacement-ruler/captures/<candidate>/`, so the timing fix and its scoring read
them unchanged. The set is the displacement plan's 154 engraved scores: dev 123 pages,
dev-b 53, test 130, test-b 126. At the shipped capture's 25 s per page that is about 2.5 hours
for both candidates on dev and dev-b, and 3.6 hours on test and test-b.

## Runs

- **Smoke, 2026-10-18 (passed):** dev 6654252 on both candidates, `jobs/smoke-1` (local), 104 s.
  Receipts: every model on `CUDAExecutionProvider`, HOMR modules from the `ab369ac` tree, 465's
  decoder FP16 and 480's FP32. Pages took about 16 s on 465 and 20 s on 480.
- **Dev and dev-b, started 2026-10-18:** 60 scores, 176 pages, both candidates, run from the
  workspace root:

  ```
  Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/reports/upstream-480/jobs/dev-1 --max-seconds 14300 -- 'Bridge\.venv-homr-gpu\Scripts\python.exe' -I -B Research/omr/upstream_capture.py --splits dev dev-b
  ```

  Progress is one `result.json` per score in `data/displacement-ruler/captures/<candidate>/`;
  the log is `jobs/dev-1/worker.log`. If interrupted, check that no supervisor is alive, keep
  the receipt, inspect any directory without `result.json`, then rerun the same command: it
  skips finished scores.

  Finished 2026-10-18: all 120 recognitions ok (`jobs/dev-1`, local).

## Development result (dev + dev-b, 60 scores)

`upstream_score.py`, [score-dev-dev-b.json](score-dev-dev-b.json). "Fixed" is the shipped timing
fix, `fit+anchor-all-keep3-even-time`. Onset F1 means:

| | Raw | Fixed | Pitch |
| --- | --- | --- | --- |
| Shipped `homr465` | 0.321 | 0.505 | 0.934 |
| `homr465-ab369ac` | 0.331 | 0.525 | 0.953 |
| `homr480-ab369ac` | 0.420 | 0.585 | 0.954 |

- **480 against shipped, fixed:** +0.080 onset F1 [+0.028, +0.137], 36 better, 23 worse, worst
  −0.421; raw +0.099 [+0.036, +0.163].
- **480's weights alone** (against `homr465-ab369ac`): fixed +0.060 [+0.018, +0.106], raw +0.089
  [+0.028, +0.152], pitch +0.001 [−0.001, +0.004].
- **Upstream code alone** (465 weights): fixed +0.020 [−0.007, +0.050], raw +0.010
  [+0.000, +0.023]. Its pitch gain, +0.019, is mostly dev-b 5866060, which shipped 465 fails
  and upstream main reads.
- **Practical fit:** page p95 44.7 s for 480 against 31.7 s for 465 on the same code, ratio 1.41,
  inside the plan's 2x gate; peak VRAM 1,569 of 6,141 MiB (25.5%) for both.

## Pre-registered test rule (recorded before test and test-b were recognised)

On test + test-b (94 scores), scored once with the same script: `homr480-ab369ac` is an
improvement for the app if its fixed onset F1 beats shipped `homr465` fixed with a paired 95%
interval above zero, its pitch F1 is not lower by more than 0.005, it fails no more scores than
shipped 465, page p95 stays within 2x of `homr465-ab369ac`, and VRAM stays under 90%. The same
figures are reported for `homr465-ab369ac`. Adopting either as the app default is the user's
decision under the plan, after the release gate; this rule only says whether the evidence
supports it.

## Next action

Recognise test and test-b with both candidates (256 pages, about four hours; the supervisor's
3.75-hour limit may stop it once, and the same command resumes):

```
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/reports/upstream-480/jobs/test-1 --max-seconds 14300 -- 'Bridge\.venv-homr-gpu\Scripts\python.exe' -I -B Research/omr/upstream_capture.py --splits test test-b
```

Started 2026-10-18 and stopped at the user's request ("continue the test later") after one score
(6902355, both candidates ok). The interrupted 480 attempt on 7006856 was moved, unchanged, to
`data/upstream-480-interrupted/`; rerunning the command above resumes from 7006856.
Resumed at the user's request ("ok continue") as `jobs/test-2`, same command with that output;
the stopped supervisor's stale `.research-worker.lock` (process gone) was kept in `jobs/test-1/`.
`test-2` failed its first page in 7 s with `RESOURCE_STOP`: not pressure, but the per-page lock
`home-upstream/omr-jobs/.worker.lock` the stop had also left (owner gone). That lock and the
failed 7006856 attempt were kept in `data/upstream-480-interrupted/`, and the same command
resumed as `jobs/test-3`.
Stopped again 2026-10-19 at the user's request after 121 of about 184 recognitions, all ok. Both
locks and the unfinished 465 attempt on 6484095 are kept in `data/upstream-480-interrupted/stop-20261019/`,
so the same command (with a new output folder) resumes from 6484095.

Then `upstream_score.py --splits test test-b`. The plan's frozen 59-page sample and the
generated controls (`tuplet_aligned` among them) are not wired to this runner yet.
