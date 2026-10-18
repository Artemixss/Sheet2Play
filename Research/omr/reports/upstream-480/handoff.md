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

## Next action

Score raw and timing-fixed onset, pitch and duration F1 on dev and dev-b against the shipped
`homr465` captures with paired bootstrap, before deciding whether test and test-b are worth
running. The plan's frozen 59-page sample and the generated controls (`tuplet_aligned` among
them) are not wired to this runner yet.
