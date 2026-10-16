# Phase 1 explicit resumption — 2026-10-07

User request: "do the remaining work" after the documented Phase 1 resource stop.
Phase 1 only; original hard 2,000,000,000-byte network cap remains cumulative.
Use existing local sources, weights, pages and notation; no external transfer.
Previous failed receipts, quarantined successes and closeout remain immutable.

Preflight: [snapshot](../resume-preflight.json), no Python/dotnet/Sheet2Play worker
or root lock; GPU 6,141 MiB total, zero used, no compute application. External
app-origin Git status processes were observed, not launched or killed by this task.
Supervisor defaults remain 85% RAM/commit, 4 GiB reserve and aggregate worker cap,
16 processes, one worker, deadline. No safeguard weakening or Phase 2 work.

Diagnosis hypothesis: the previous batch reused one process; retained native
allocations may explain late failures. This is unverified before controlled work.
Add read-only current-process and Job peak-memory telemetry at native detection,
parsing and page boundaries; record actual Python/import origin. No source/weight,
image size, recognition setting or musical return is changed.

Sequence: guarded focused fixtures; fresh single-item native inference on
generated-tie_across_barline using installed Bridge Python, capture root this
directory, --memory-telemetry. Inspect before any additional inference. If safe,
one fresh supervised process per remaining page; any pressure/allocation failure
stops the sequence, preserving evidence. No unchanged failed batch retry.

Commands/cwd/limits/logs: each jobs/<name>/result.json, resources.jsonl, worker.log.
All substantive CPU jobs use Research/omr/guarded_execution.py and Research Python
as supervisor; native children use Bridge/.venv-homr-gpu/Scripts/python.exe.
PYTHONPATH inherits ../gate plus Research/omr and Research/omr/src. GPU admission
and two-second pressure monitoring remain separate and fresh for each process.

Remaining inputs: generated-tie_across_barline, generated-tuplet_aligned,
generated-triplet_vs_duple, generated-triplet_vs_quadruple; all 20 OpenScore first
pages. Source/page eligibility must be independently established before scores.
Source-derived notation is a reference, never a token oracle or correction input.

Resumed inference ended cleanly at openscore-6212196 (worker exit 2): RapidOCR
Conv Add.57_nchwc bad allocation. All four remaining generated controls and seven
OpenScore pages completed beforehand, each in a fresh process. The failed page
and twelve unattempted pages remain. No inference retry pending. Root loop
session 32984 is closed. Peak system RAM 67.47%, commit 55.59%; worker telemetry
peak private bytes 4,306,792,448. NULL Job telemetry can describe the outer Job;
supervisor receipts pin actual 4,294,967,296-byte containment. Do not infer the
precise allocator cause from these counters or raise limits.

Independent remaining work: local PDF/image/layout correspondence, successful
capture analysis, regression and closure. Page check command: guarded_execution
--output resume-20261007/jobs/page-correspondence --max-seconds 900 -- bundled
Python -B Research/omr/homr_baseline_pages.py --output resume-20261007 --renderer
bundled Poppler pdftoppm.exe. Cwd repository root. No inference or network.

## Completed offline follow-up

Latest evidence: [report](REPORT.md), [analysis](analysis-reviewed/development-analysis.json),
[page ledger](page-font-reviewed/page-correspondence.json),
[reviewed findings](reviewed-findings.json), [failure traces](failure-traces.json),
[closeout](closeout.json), [process/network snapshot](network-closeout.json).
All 12 generated controls and seven OpenScore pages have usable captures.
All 20 first-page PDF renders match frozen images; 18 XML ranges verified. Two
next-page `X1` boundaries remain unresolved. OpenScore has no accuracy scores.

Failed intermediate checks retained:
- jobs/focused: an initial telemetry test incorrectly assumed NULL Job was the
  worker containment Job. It can be an outer Job; supervisor receipts pin the cap.
  Corrected focused test passed in jobs/focused-corrected.
- jobs/page-correspondence: bundled PDF Python lacked Research's psutil imported
  transitively. Removed that unnecessary import; jobs/page-correspondence-corrected
  passed and produced all twenty local renders.
- page-review/page-correspondence.json used a fixed font-size filter and lost
  valid labels; preserved as intermediate evidence. Subsequent page-layout-final
  verified 17 ranges. Latest page-font-reviewed derives each score's actual label
  font and excludes a left-margin page header; 18 ranges verified. Three font-size
  fixtures and the complete suite passed. No inference was repeated for this work.

Latest commands, all cwd repository root, offline gate PYTHONPATH inherited:
- jobs/page-font-reviewed: supervisor 600 s -> bundled Python homr_baseline_pages.py
  --output <resume>/page-font-reviewed --reuse-render-root <resume>/pages --renderer
  bundled Poppler; 25.531 s, complete. No new render or fetch.
- jobs/regression: supervisor 1800 s -> Research Python -B -c configure_cpu +
  pytest Research/omr/tests Bridge/tests -q --junitxml=<resume>/regression.xml;
  38 s, complete, 396 passed / 2 skipped, zero errors/failures.
- jobs/analysis-reviewed: supervisor 600 s -> Research Python -B
  homr_baseline_resume_analyze.py --evidence <phase1> --output <resume>
  --analysis-root <resume>/analysis-reviewed --page-ledger
  <resume>/page-font-reviewed/page-correspondence.json; 7.453 s, complete.
- jobs/closeout: supervisor 600 s -> Research Python -B
  homr_baseline_resume_closeout.py --evidence <phase1> --resumed <resume>;
  6.562 s, complete. Verified 56 protected, 362 original and 462 resumed inference
  artifacts; preserved executed-source snapshot and 14 first-error traces.

Final live snapshot: no Python/dotnet/Sheet2Play worker, no root lock, GPU 0 MiB;
no blocked offline-gate action. All tool sessions closed. Phase 1 remains partial:
6212196 failed allocation and twelve later OpenScore pages were not attempted.
Exact remaining IDs are in closeout.json. No inference retry pending. Next action:
review allocation refusal before a separately reviewed fresh Phase 1 resumption,
and map the two unresolved XML/PDF boundaries. Never proceed to Phase 2 from this
record. Cumulative 2 GB cap retained, zero requested research transfers; host-wide
traffic totals unavailable because the original Wi-Fi counter reset.
