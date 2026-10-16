# Zeus provenance Phase 1 — 2026-10-03

Authorized: Phase 1 of the attached Zeus attribution / shared scoring / Rokot plan.
Boundary: source, runtime, checkpoint and conversion provenance only. Stop before
Phase 2 timing changes, rescoring, Phase 3 inference, remedies and Rokot work.
Keep historical manifests/results/freeze unchanged. Pause on material contradictions
or consequential decisions; unresolved historical source is an explicit plan allowance.

Working directory: `C:/Users/bur4x/Desktop/lecture/big_projects/Sheet2Play`.
Initial preflight: RAM 78.1%, no other Python candidate/scorer or worker lock.
Five-hour usage 76%; stop assistant work at 95% with exact resumable evidence.
Machine process query was denied; psutil supplied process enumeration instead.

## Evidence collection and commands

- Current upstream Git HEAD/status/reflog, frozen v5 manifest and source inventories
  inspected without changing checkout, wrappers or model files.
- Public GitHub API request first hit sandbox network restriction; authorized
  network retry hit unauthenticated API rate limit. No authentication workaround.
- Original public release archive downloaded via its release asset URL with
  `Invoke-WebRequest`, cache-busting query `phase1=20261003`, into
  `published-model.tar.gz`. SHA-256
  `85f601cb7370175754c0cd9b2d4799f5a744c6d25e5e4f18705b08b79a0c54d2`,
  27,051,365 bytes. GitHub release asset page identifies this file; no independent
  publisher checksum is available. Local weights match bytes; text files differ
  only in CRLF endings, including identical parsed options/ordered vocabulary.
- Focused tests: `Research/omr/.venv/Scripts/python.exe -B -m pytest
  Research/omr/tests/test_zeus_provenance.py -q`: 11 passed.
- First probe launcher stopped before imports: workspace ancestor depth was one
  level too high. Corrected `parents[6]` to `parents[5]`; no model or output existed.

Before launch, recorded commands:

```powershell
Research/omr/.venv/Scripts/python.exe -B Research/omr/reports/zeus-attribution/phase1/collect-probe.py
Research/omr/.venv/Scripts/python.exe -B Research/omr/zeus_provenance.py build --probe Research/omr/reports/zeus-attribution/phase1/import-probe.json --archive Research/omr/reports/zeus-attribution/phase1/published-model.tar.gz --manifest Research/omr/reports/screening/v1/manifest-v5-607ff64134da.json --output Research/omr/reports/zeus-attribution/phase1/diagnostic-identity.json
```

Probe performs imports only: no model construction or inference. CPU recognition
environment, below-normal priority, eight-thread cap, 90% RAM/device-VRAM admission
and sustained-pressure guard. Probe logs/resources/PID/command persist here. Build
hashes installed runtime files and archives source; it does not import TensorFlow
or run model workers. Build log: `identity-build.log`. On interruption, check live
processes before resuming; preserve any partial snapshot/identity and use a new
output filename if needed. Do not overwrite existing evidence.

Probe v1 completed (PID 6128), TensorFlow 2.12.1/no GPUs, expected imported symbols.
During collection the new utility gained explicit base-interpreter and probe-source
hash fields. Preserve v1; collect a fresh probe under `probe-v2/` so the final
identity binds the collector actually executed. Same import-only command plus
`--output-dir Research/omr/reports/zeus-attribution/phase1/probe-v2`.
Use `probe-v2/import-probe.json` for the build. No inference in either probe.

Identity build launched with the recorded command and v2 probe, exec session 46409;
PowerShell PID 4956, Python launcher 8200, worker 21000 (creation epoch
1791038510.1712599). At the next checkpoint it was hashing the Zeus environment,
worker RSS 129,437,696 bytes, system RAM 82.8%. Environment inventories exclude
volatile Python bytecode only; all other files, native libraries, installed package
source and metadata are hashed, including the shared base interpreter. No heavy
candidate/scorer runs concurrently.

Initial identity build exited 1 on sandbox-denied
`Research/omr/.venv/Lib/site-packages/certifi/__init__.py`, before any identity or
snapshot was written. Retried the identical build with expanded read access,
exec session 68142, log `identity-build-readable.log`; no dependency was omitted.
This reproduces the historical v5 need for a fully readable local inventory.

Expanded-access worker 33220 (creation epoch 1791038808.66521), launcher 32396.
At 14:50 UTC, applied below-normal priority/eight-core affinity to that worker and
attached the existing five-second/30-second 90% pressure monitor, exec session
48337. Samples persist in `inventory-resources.jsonl`; no admission blockers.
Inventory is a low-memory read-only hashing job; monitor stops it if pressure
persists. It does not start candidate inference or a scorer.

Final replay verifier `zeus_provenance_verify.py` checks all diagnostic bytes plus
inherited detector source/weights/tokenizers and the external Bridge CUDA patch.
This avoids treating environment inventory alone as proof of that external file.
Focused suite after detector-mutation fixture: 12 passed.

Full suite command: `Research/omr/.venv/Scripts/python.exe -B -m pytest Bridge/tests
Research/omr/tests -q`. Expanded-access run (`regression.log`, session 38556)
completed with two historical-freeze identity failures. A read-only snapshot diff
proved exactly the 33 metadata additions recorded by v5, with no other field
change; current readable runtime equals the v5 readable runtime exactly.
The historical tests use strict old-freeze equality and are access-context
sensitive. No test or freeze was edited. Repeat the entire suite in its original
sandbox access context (`regression-historical-context.log`) and verify the actual
screen separately against v5 with expanded read access. Preserve both results;
the expanded-context failures remain disclosed rather than skipped or xfailed.

Original-context complete regression exited 0, session 27210, expected two skips
and the existing unreadable-clef fixture warning. No failing tests.

Read-only historical audit command (expanded-access v5 context):

```powershell
Research/omr/.venv/Scripts/python.exe -B Research/omr/screening_cpu_audit.py --manifest Research/omr/reports/screening/v1/manifest-v5-607ff64134da.json --candidate zeus_page --include-scores --output Research/omr/reports/zeus-attribution/phase1/historical-audit.json
```

Log `historical-audit.log`; immutable output. This verifies stored scores and
outcomes only; it neither runs inference nor recomputes a score.

Identity build exited 0. Diagnostic identity
`ade1709596afff5023e14bfb73257028ff2bc8521f4ff895ec91dc863b842cbb`.
Four runtime trees: 25,520 Zeus, 35,638 research, 13,597 detector and 38,630 base
Python files (113,385 total). Source snapshot 154,000 bytes; identity JSON
28,041,635 bytes. All 12 imported upstream paths match current HEAD after newline
normalization. At the release tag only `zeus/zeus.py` differs. At declared dataset
revision recognizer/SER helper are absent and Delinearizer's missing-clef fallback
differs. Inventory monitor exited 0; no resource interruption.

Complete regression: 251 passed, 2 skipped in historical access context. Expanded
context: 249 passed, 2 failed, 2 skipped, exactly the two historical-freeze tests
listed in `regression.log`. Existing bridge subtests also passed.

Required final byte re-verification command (expanded read access):

```powershell
Research/omr/.venv/Scripts/python.exe -B Research/omr/zeus_provenance_verify.py Research/omr/reports/zeus-attribution/phase1/diagnostic-identity.json
```

Log `identity-verify.log`. This rehashes every pinned runtime/source/weight/evidence file
and checks inherited detector pins; no model construction or inference. On a
failure do not declare completion or regenerate a supposedly equivalent identity
without explaining the changed bytes. Preserve all collected evidence.

Historical v5 audit exited 0, session 63805: 59 successful results, 59 saved scores,
236 declared artifacts, closed session. No inference/scoring ran.
Inventory guard captured 144 samples, peak system RAM 84.5%, device-wide VRAM
0.16284%; no blockers/interruption. Final verifier session 61096, launcher 29552,
worker 32576 (creation epoch 1791039875.1186888), monitoring in
`verify-resources.jsonl` with the same priority/affinity/pressure policy.

## Final closeout

Verifier exited 0: full diagnostic byte inventory passed, identity digest unchanged,
50 inherited detector files verified. Verifier source SHA-256
`3e74c36e516fa9180215b2f5c3a10b75c9663d489486396a71cdc3bc9399c4fa`.
Monitor exited 0. No active inventory/probe/verifier/candidate/scorer remains.
Documentation links, four new Python compilation checks and scoped diff whitespace
checks passed. Final allowance reading: 94% used/6% remaining; closing below the
user's 95% cutoff. No assistant/model settings changed or later phase executed.

Acceptance statuses and limitations are in `REPORT.md`; concise changed-file and
continuation pointers in `handoff.md`. Next action requires a new Phase 2 request.
Preserve this identity and historical screen. Before any later diagnostic replay,
reverify bytes and import resolution; a changed runtime/source requires a new identity.
