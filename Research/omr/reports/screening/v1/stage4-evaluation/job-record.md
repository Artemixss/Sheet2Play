# Canonical Stage 4 evaluation — 2026-09-30

The user requested completion of Stage 4 using the completed five-candidate Stage 3
report. This request authorizes analysis and a recommendation. It stops before a
confirmation run, Stage 5, training, cloud spending or production promotion.

Working directory: `C:\Users\bur4x\Desktop\lecture\big_projects\Sheet2Play`.
Interpreter: `Research/omr/.venv/Scripts/python.exe` (existing research environment).
Input: [consolidated report](../2c98d5638c36/reports/consolidated-stage3-836fb923bb33/REPORT.md),
JSON SHA-256 `22423ca7343b5382881577b6b6146066974cfd35710a48d964faa04b1ef8bb85`.
Sample: 59 pages / 18 whole compositions, SHA-256
`2c98d5638c368b1a53bdb3440177d04fa585f9b1ca6ce6adbe65af64cd8e27d1`.
All historical reports, manifests, helper source, predictions and scores are preserved.

## Recorded checks before execution

1. `Research/omr/.venv/Scripts/python.exe -B Research/omr/reports/screening/v1/stage4-evaluation/audit-screen.py`
   verifies saved identities, all result/artifact/score/summary hashes, source inputs,
   duration matrices, summary metrics, eight paired claims and practical limits.
   Completed log: `screen-audit-v2.log`; output: `screen-audit.json`. It performs no model
   inference, new note scoring, runtime installation or candidate readmission.
2. `Research/omr/.venv/Scripts/python.exe -B -m pytest Research/omr/tests/test_screening_consolidated_report.py Research/omr/tests/test_screening_homr_analysis.py Research/omr/tests/test_screening_homr_statistics.py -q -o addopts=''`
   Log: `focused-tests.log`.
3. `Research/omr/.venv/Scripts/python.exe -B -m pytest Research/omr/tests Bridge/tests -q -o addopts=''`
   Log: `regression.log`. Research-only evaluation does not need an app publish.

Independent reviews check the decision gates and historical exposure of the remainder.
Exposure inventory is metadata-only and does not select a future confirmation sample.
Current decision and completed validation are recorded in [REPORT.md](REPORT.md).

## Completed validation and decision

- Saved-evidence audit: unified-exec session `51467`, exit 0. Verified 295 results,
  295 scores, 1,257 declared artifacts, full summary/duration matrices and eight
  paired statistics. All candidate sessions remain closed; worker lock absent.
  Source script SHA-256 `b0a89cad333c8cd99b19079673c3dcb61efcdeb6a1c6e814af99976a68b7c728`;
  [audit JSON](screen-audit.json) SHA-256
  `bab082f64f2dbaeea6441635dcc31d6572403dd7cf0238028bb72d195a0983a0`.
- First audit attempt exited 1 before any candidate checks. It compared Markdown
  regenerated from sorted-key JSON with Markdown rendered from the original
  insertion order. A narrowed diff showed presentation order only. The audit now
  checks Markdown's before/after hash and verifies all numerical/source evidence
  directly. The preserved first log is `screen-audit.log`; Stage 3 data was not
  modified. The corrected audit ran once successfully; no unchanged failed command
  was retried.
- Focused fixtures: exit 0, **14 passed in 0.44 seconds**, `focused-tests.log`.
- Full research/bridge regression: unified-exec session `86658`, exit 0,
  **239 passed, 2 skipped, 9 subtests passed in 39.75 seconds**, `regression.log`;
  one expected unreadable-clef music21 warning.
- Independent exposure command:
  `Research/omr/.venv/Scripts/python.exe Research/omr/reports/screening/v1/stage4-evaluation/audit-confirmation-exposure.py`.
  Both initial run and immutable replay exited 0. All 255 historical report/sidecar
  pairs matched. [Exposure JSON](confirmation-exposure.json) SHA-256
  `548d7314c6c04c60f773145b10332556bb89d352d4a6ea6c5331654e67d574ed`.
- [Decision JSON](decision.json) SHA-256
  `034e6b2ed074c98085e6e6b3ba7b177a2141a49721a3c68f2ea3e6fe4fe04f0b`.
  It records all candidate dispositions, promotion limitations, exposure counts,
  conditional throughput estimates, validation and evidence hashes.
- Final documentation check: **154 local links across seven active/review documents**
  resolve; trailing-whitespace checks and both audit-script syntax checks pass.
  All eight decision evidence hashes still match. Tracked documentation
  `git diff --check` passes with the existing Git Windows line-ending notice.

Canonical Stage 4 is complete: retain shipped HOMR; no accuracy-led challenger
confirmation now. Optional shipped/fine-tune confirmation remains a separate
decision. The 343-page remainder contains 207 previously processed pages; only
135 pages/44 whole compositions have no recorded prior attempt, with substantial
composer imbalance. No confirmation sample was selected or frozen. Historical
Stage 3 "untouched" wording is qualified by this review without rewriting its report.

**Exact next action:** stop execution. The user decides whether to end this
comparison, request separately bounded Stage 5/readiness work, or authorize a
preregistered confirmation with overlap/eligibility resolved. No pending Stage 4
page, inference/scoring job, training, cloud charge or app promotion remains.
