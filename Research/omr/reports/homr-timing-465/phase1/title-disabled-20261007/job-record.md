# Phase 1 bounded title-OCR unblock — 2026-10-07

Owner: [MAIN_PLAN.md](../../../../../../plans/MAIN_PLAN.md), plan
`2026-10-06-homr-timing-465`. Explicit user authorization: separate title-disable
research profile, two completed-example musical equivalence checks, one failed-page
probe; continue remaining captures/reference mapping only after a passing probe.
Any allocation failure stops inference with preserved evidence and recommendation.
No production change, download, 465 work or Phase 2. Cumulative network cap remains
2,000,000,000 bytes, with zero research transfers requested.

Preserved failure: ../resume-20261007/development/openscore-6212196/failure-traceback.txt
shows main.process_image -> title_future.result -> title_detection._detect_title_task
-> RapidOCR text detection -> ONNX Conv Add.57_nchwc bad allocation, after parsing.
Exact initiating allocator cause remains unverified. Installed main.py exposes
ProcessingConfig.title_detection and --no-title; false supplies an empty Future
without title OCR. Only this optional metadata setting is changed.

Profile: [profile.json](profile.json), canonical SHA-256 identity recorded in that
file and each capture receipt. Baseline runtime remains e61db08610fe9b475d42a822a9ea265fed780e095758944b71cb2c0b17b0ec66.
Original and resumed captures/failures remain immutable. New captures use this root.
Live preflight 2026-10-07T16:09:41Z: no Python/dotnet/Sheet2Play worker or root lock;
GPU 6141 MiB total, zero used. Usage read: 80% five-hour allowance used, above the
required 5% remaining stop. Inspect usage again at consequential boundaries.

All substantive jobs: Research/omr/.venv/Scripts/python.exe -B
Research/omr/guarded_execution.py --output <root>/jobs/<item> --max-seconds 600 --
Bridge/.venv-homr-gpu/Scripts/python.exe -B Research/omr/homr_baseline_infer.py
--evidence Research/omr/reports/homr-timing-465/phase1 --capture-root <root>
--item <item> --memory-telemetry --research-profile <root>/profile.json.
Cwd repository root; offline gate PYTHONPATH includes phase1/gate, Research/omr,
Research/omr/src. One fresh native process per item, sequential. Receipts/logs:
jobs/<item>/result.json, resources.jsonl, worker.log; native development/<item>.
Unchanged 85% RAM/commit stops, 4 GiB reserve/cap, 16 processes, deadline; separate
fresh 90% GPU admission and two-second monitor. No Git or network in workers.

Execution gates: focused fixtures (passed); equivalence pages 6211535 and 6212193
against their completed title-enabled captures; reviewed equivalence must pass
before openscore-6212196 probe. Any failure stops dependent work. Do not retry a
resource-stopped root. Do not mark Phase 1 complete until remaining evidence and
reference boundaries are resolved or explicitly qualified in acceptance.

## Completed execution and closure

1. Focused profile/batch fixtures passed. Profile creation and each new capture
   record identity `a6cab9a5ac91aa7cd31be843b8cb37a189cd1bc564857dc235a82db8da054c32`.
2. Separate supervised captures for 6211535 and 6212193 completed. Offline
   `homr_title_equivalence.py --baseline <phase1>/resume-20261007 --candidate <root>
   --runtime e61db08610fe9b475d42a822a9ea265fed780e095758944b71cb2c0b17b0ec66`
   passed all nine musical comparisons for both pages; [equivalence.json](equivalence.json).
3. The single supervised 6212196 probe passed, guarded elapsed 13.391 s and sampled
   peak process private memory 3,962,343,424 bytes. No safeguard changed.
4. The twelve-item sequence then passed completely; [sequence.json](sequence.json)
   retains exact order and completion. Root session 63716 exited 0. All inference
   sessions ended; no resource-stopped run was automatically retried.
5. Boundary preparation's first invocation failed with a source syntax error
   before producing evidence; [failed receipt](jobs/boundaries/result.json) retained.
   Corrected source and a separately named supervised job passed; both PDF/XML
   boundaries independently reviewed in [reviewed findings](boundaries/reviewed-findings.json).
   The new [page ledger](boundaries/page-correspondence.json) verifies 20/20 ranges.
6. Supervised analysis used `homr_baseline_resume_analyze.py --evidence <phase1>
   --output <root> --fallback-root <phase1>/resume-20261007 --page-ledger
   <root>/boundaries/page-correspondence.json --analysis-root <root>/analysis`;
   all 32 captures usable, 12 controls scored, zero current failures/unattempted.
7. Regression used the same guarded supervisor, `--max-seconds 1800`, research
   Python with `configure_cpu()` followed by `pytest.main(['Research/omr/tests',
   'Bridge/tests','-q','--junitxml=<root>/regression.xml'])`. Guard completed exit 0,
   37.672 s. [JUnit](regression.xml): 400 recorded cases, two skipped, zero failures/errors.
8. [verify_closeout.py](verify_closeout.py) ran under the same guard with deadline
   600 s and completed exit 0, 6.969 s. It checked 56 protected runtime artifacts,
   362 original / 462 resumed / 734 new inference artifacts, old evidence hashes,
   references, equivalence, all inference safeguards and network/process closure.
   [Executed sources](executed-source) preserve the scripts used; [closeout](closeout.json).

Final live inspection 2026-10-07T16:29:19Z: no Python/dotnet/Sheet2Play process,
no root lock, no blocked network/Git action, GPU 6141 MiB total and zero used.
Usage boundary read: 89% used, 11% remaining. Research transfers requested: zero.
The original Wi-Fi counter reset prevents a measured host-wide network-total claim.
Final documentation/evidence checks verified 55 local links, no root lock or
blocked action. Final allowance read: 93% used, 7% remaining; above the 5% stop.

The bounded user request is complete. Whole Phase 1 remains partial for ten
independent first-error reviews named in the [report](REPORT.md); evidence is
already captured, with no inference rerun required. Stop before production,
465 download/admission or Phase 2. No live job or pending retry remains.
