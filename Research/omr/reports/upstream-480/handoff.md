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

Finished 2026-10-19 as `jobs/test-4`: 188 recognitions ok on both candidates (the only failure
was `test-2`'s stale-lock stop, re-run).

## Test result (test + test-b, 94 scores, scored once): passes the pre-registered rule

[score-test-test-b.json](score-test-test-b.json). Onset F1 means:

| | Raw | Fixed | Pitch |
| --- | --- | --- | --- |
| Shipped `homr465` | 0.433 | 0.680 | 0.958 |
| `homr465-ab369ac` | 0.451 | 0.704 | 0.972 |
| `homr480-ab369ac` | 0.584 | 0.747 | 0.973 |

- **480 against shipped, fixed:** +0.068 [+0.024, +0.113], 67 better, 18 worse; raw +0.151
  [+0.081, +0.221]. Pitch +0.015 [+0.002, +0.039]. Failures: 0 against shipped's 1 (4978478).
  Page p95 51.8 s against 37.1 s, ratio 1.40. Every condition of the rule holds.
- **But large single losses:** test-b 6785268 falls from 0.988 to 0.148 and 6222828 from 0.952 to
  0.361 (fixed); 5987757 loses 0.32.
- **480's weights alone,** fixed: +0.044 [+0.004, +0.082]. **Upstream code alone** (465 weights):
  +0.024 [+0.001, +0.054], pitch +0.015, and it reads the score shipped 465 fails.

## Adoption (2026-10-19): HOMR 480 is the app default, HOMR 465 the secondary

The user chose it after the test result ("make 480 default and 465 as secondary nothing else").
HOMR 426 and Zeus are unchanged and still selectable.

- **Bridge:** engine `homr480`, run by `homr480_native.py` against `homr480-profile.json`
  (`82dc0b01…`) and `.runtime/homr-480`, provisioned by `Research/omr/homr480_provision.py`; see
  [Bridge/HOMR465.md](../../../../Bridge/HOMR465.md#homr-480). `bridge.py` changed, so 465's profile
  was re-pinned (`1fd5b26e…` to `c06852f3…`, one line) and the library's 465 caches went stale.
  The timing fix covers `homr480`; its own hash changed, so corrected caches re-run too.
- **App:** `OmrEngine.Homr480`, the default for new or unreadable settings; landing-page cards HOMR
  480 (default), HOMR 465 (secondary), HOMR 426, Zeus; 480's error screen offers "Retry HOMR 465".
  The user's own settings were switched to `homr480`.
- **Evidence:** xunit 102 passed (8 new, `Homr480IntegrationTests`); Bridge and research 451
  passed, 2 skipped (`jobs/regression-1`); the workspace and the published bridge both reproduce
  the research capture's notes exactly for `homr480` and the shipped capture's for `homr465` on
  dev 6654252 (`jobs/e2e-bridge-1`, `jobs/e2e-dist-1`); `verify-release.ps1` passed all 8 steps,
  including the new pinned-480 check (51 runtime assets, 15 Bridge files).
- **Not done:** no batch re-conversion of the library (`Sheet2Play.exe --reconvert homr480`
  would do it, several GPU hours); `AGENTS.md`, `README.md` and `CONTEXT.md` still name 465 as the
  default, because another session holds uncommitted rewrites of all three.

## Flagged follow-up: the two large 480 regressions (after the session's compaction)

The user asked to investigate these further after compacting. Both are deterministic: a
repeat run (`jobs/rerun-bad-2`, `data/upstream-480-rerun/`) wrote byte-identical page MusicXML.
Onset F1, pitch F1 in brackets:

| test-b score | 465 | 480 raw | 480 + timing fix |
| --- | --- | --- | --- |
| 6222828 (meter change) | 0.995 [0.998] | **0.999** [1.000] | 0.361 |
| 6785268 | 0.988 [0.990] | **0.060** [0.982] | 0.148 |

- **6222828 is a timing-fix fault, not a recognition one:** 480 reads it almost perfectly and the
  fix then anchors a real meter change. It is the same score that failed the timing plan's
  near-correct guard on 465 (0.995 to 0.952). With the switch off (the default) 480 is fine here.
- **6785268 is a 480 misreading:** pitch is right but onsets are displaced, so bar lengths or
  voice placement differ from 465's reading of the same pages. Compare 480's and 465's page
  MusicXML bar by bar (`displacement_attribution` and `timing_residual` read both captures).

## Next action

The flagged follow-up above, when the user asks. Making the timing fix the default still waits
on the user's review.
