# Phase 2 execution — 2026-10-07

Owner: [MAIN_PLAN.md](../../../../../plans/MAIN_PLAN.md), `2026-10-06-homr-timing-465`.
The user's new request authorizes Phase 2 only, with a hard total network cap of
3,000,000,000 bytes. Phase 1's earlier 2 GB budget is a separate completed execution.
No Phase 3, training, cloud spending, production edits or promotion.

Sequence: bounded checkpoint/source acquisition; separate 465 compatibility
contract and fixtures; two native development probes; full 32-item development;
configuration freeze; fresh 59-page comparison and reproducible scoring/report.
Candidate source: 33baa326900faa12702df8c4bdcbea034a3d6a34; model pair:
465-597144cab54c8f6d0f6c9619df5c5312694eadd6 FP16.

Working directory: repository root. All substantive workers use
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py,
fresh jobs directories and bounded deadlines. Retain 85% RAM/commit stops,
4 GiB reserve/worker cap, 16 processes; separate 90% VRAM admission/monitor.
Resource failure is preserved and stops dependent execution without automatic retry.

Initial inspection: no root .research-worker.lock, no Python/dotnet/Sheet2Play
process in Get-Process; nvidia-smi reports 6141 MiB total and zero used.
CIM queries were unavailable in the sandbox; supervisor samples remain authoritative.
Account allowance: 19% used / 81% remaining; stop at 5% remaining.

Acquisition command: supervisor --output phase2/jobs/acquisition --max-seconds 900
-- research Python -B Research/omr/homr_465_download.py --evidence phase2
--runtime Research/omr/.runtime/homr-465-upstream. Logs/resources/result in jobs.
Download budget reserves twice each response ceiling plus 1 MB/request and a
100 MB control reserve. No automatic network retries or dependency installation.
Actual payload and conservative reservations are persisted in network-budget.json.
An official release-page browse is covered by the control reserve. External host
traffic and chat-service traffic cannot be certified by payload accounting.

Acquisition attempts: default sandbox DNS failure (no payload); approved network
attempt acquired encoder but sandbox replacement of the budget journal failed during
decoder transfer; explicit reviewed resume under approved permissions succeeded.
All three job receipts and the partial decoder archive remain. Reservations:
804,216,858 bytes; completed payload ledger: 119,202,719 bytes; interrupted decoder
file: 5,308,416 bytes, conservatively additional. No further downloads are needed.

Compatibility: first ordered-position check rejected an incorrect expected order;
actual pinned order is `.`, `upper`, `upper2`, `lower`, `lower2`. Corrected independent
465 contract passed native ONNX/source/vocabulary admission. The 455 contract is unchanged.
13 focused fixtures passed in jobs/focused-fixtures-exclusive. Sandbox hard-link/rename
failures are preserved; new research journals use exclusive writes and fsync.

Two probes: generated-baseline-piano-001 and openscore-6211535 both complete, about
11.5 seconds of native capture each. Capture receipts preserve crops, raw/cleaned
tokens, XML, provider/source identities and memory samples. The initial probe-analysis
failed on sandbox canonical file-path access; approved offline probe-analysis-file-access
completed unchanged, generated primary F1 1.0, no corrected/regressed measure.

Full development command: powershell -ExecutionPolicy Bypass -File
Research/omr/run-homr-465-phase2.ps1 -Mode development. Each remaining item uses its
own guarded 600-second worker/job; the two identity-matched completed probes are reused.
No other research worker/lock was live before dispatch. Usage check: 65% five-hour
allowance remaining. Output: development-sequence.jsonl and jobs/development-candidate-*.

First batch launch failed before inference: Windows PowerShell 5.1 nested the JSON
array inside an extra array wrapper, combining all item IDs into an invalid path.
Removed that wrapper; direct preflight returned 32 items and the first expected ID.
Reviewed launch now running in terminal session 32567. Analysis workers need approved
canonical-path access; inference workers have run successfully inside the sandbox.

Development session 32567 completed all 32 captures, zero explicit/native failures
and zero resource stops. Analysis jobs/development-analysis completed under approved
offline file access. Twelve generated controls: mean primary F1 0.6096882692;
offset_entry and triplet_vs_duple each correct one baseline-wrong measure;
three_voices and tuplet_aligned each regress one baseline-exact measure. OpenScore
remains diagnostic only. Duration: 105 pitch/onset-paired notes, majority baseline
0.60952, balanced accuracy 0.69444, macro-F1 0.69668, multiple predicted classes.
No musical-setting tuning: candidate remains the pinned native pipeline.
17 focused fixtures and fresh compatibility reverification pass.

Next command: guarded homr_465_prepare.py freeze, then powershell -ExecutionPolicy
Bypass -File Research/omr/run-homr-465-phase2.ps1 -Mode comparison. Fresh 59 pages
in 18 groups for each engine, alternating engine order per page, same GPU/driver,
8 CPU threads, shared read-only runtime and native no-title setting. Each guarded
worker deadline 600 seconds; batch refuses dispatch beyond its four-hour boundary.
Inputs/config/scoring/hardware identities are frozen before the first capture.
Ordinary failures are retained and scored zero; resource failures stop the batch.

Freeze identity: 91e7256cd902a6ea2adb9fb415e6847b2ba0b9e94fb03fe8f5f1570ae6544fb9.
Comparison running in terminal session 72555; five-hour allowance 60% remaining.
Before resuming, inspect session/process/lock and comparison-sequence.jsonl;
do not dispatch another copy. The first candidate/control pair both completed.
The generated-control local harms are in development-review.md and are preserved
as admission qualifications; no candidate settings or frozen scoring sources change.

Comparison item 17 control (e2139c49a0b38b5921a9,
test/beethoven/sonata17_1/sonata17_1_6.png) has an explicit native export failure:
installed HOMR music_xml_generator.py build_note_chord asserted group_duration > 0.
This is an ordinary exporter assertion, not a recorded resource-pressure stop.
The candidate capture for that item succeeded. Preserve the control's tokens,
traceback, resources and failed receipt; assign failure-zero scores with no retry
or repair in Phase 2. Other captures continue under the frozen failure policy.

Closeout commands (after all captures, never concurrent with a live worker):
guarded --output jobs/comparison-analysis --max-seconds 1200 -- research Python
-B -c "from homr_465_audit import record_scoring_environment; record_scoring_environment();
from homr_465_analyze import comparison; comparison()". Approved file access is
required by the unchanged production normalizer's strict Windows path resolution.
The actual scoring interpreter/NumPy/normalizer identity is recorded before scoring.
Then a fresh guarded full Research/omr/tests and Bridge/tests regression, and a guarded
homr_465_audit.py in the shared 455 environment to verify native-package versions,
all 150 capture receipts, individual scores, regenerated XML metrics/statistics,
protected assets and budget. The auditor does not change frozen scoring code.

2026-10-08 reviewed continuation: session 72555 is finished, no live worker or lock.
Its control capture be1ce479aa1490d66b01 stopped at session_deadline after a
3632.943356-second telemetry gap. Recorded peak RAM 71.4873%, commit 55.9912%;
no pressure-stop diagnosis is supported. Original guarded receipt/logs remain
at jobs/comparison-control-be1ce479aa1490d66b01; partial native files preserved
at interrupted-20261008/control/be1ce479aa1490d66b01, hashes in resumption-admission.
Two preflight import failures are retained: the shared inference environment has
no psutil. The research interpreter reads pinned runtime distribution metadata;
no installation or inference setting change. Supervised preflight passed.
New hardware/RAM admission is resumption-admission-20261008.json, with the same
GPU UUID/driver and frozen profiles. Safeguards remain 85%, 4 GiB reserve/worker,
16-process containment, 90% GPU stop, 600-second capture deadlines and <=4h batches.
User authorized continuation and RAM-capacity adjustment; dynamic percentages
already use actual capacity, with no 16 GB physical ceiling. Network cap stays 3 GB.
Reviewed interrupted control command: guarded_execution.py --output
jobs/comparison-control-be1ce479aa1490d66b01-resume-20261008 --max-seconds 600 --
shared 455 Python -B homr_465_capture.py --configuration control-configuration.json
--inputs comparison-inputs.json --item be1ce479aa1490d66b01 --output
comparison/control/be1ce479aa1490d66b01. Original partial/failed evidence is retained.
Upon success, the frozen comparison launcher resumes the other remaining items.
Performance reports must distinguish pre-upgrade and post-upgrade RAM cohorts;
the cross-transition page pair cannot support a matched performance comparison.
Reviewed control resumption completed in 30.078 supervisor seconds, no resource stop. Dispatching the frozen comparison launcher for the remaining 12 pairs; previously completed/explicit-failed captures are reused by exact frozen profile identity. Fresh session starts 2026-10-08 after the recorded RAM admission.
Final closeout execution correction: homr_465_audit.py runs in the existing research
Python (shared inference environment lacks psutil required by transitive scoring
imports). It verifies package versions from the pinned inference interpreter's
Lib/site-packages metadata, all source/model hashes, actual native import origins,
three model sessions and provider/thread settings. This does not change captured
inference or frozen scoring. No packages are installed. The scoring environment
records its own actual interpreter/NumPy before the first 59-page scoring.
Planned complete-regression command, working directory workspace root: research
Python -B guarded_execution.py --output phase2/jobs/full-regression --max-seconds
1200 -- research Python -B -c "from zeus_attribution_prepare import configure_cpu;
configure_cpu(); import pytest; raise SystemExit(pytest.main(['Research/omr/tests',
'Bridge/tests', '-q', '--junitxml=Research/omr/reports/homr-timing-465/phase2/full-regression.xml']))".
Planned audit command: guarded --output phase2/jobs/final-audit --max-seconds 900 --
research Python -B -c "from zeus_attribution_prepare import configure_cpu;
configure_cpu(); from homr_465_audit import audit; audit()". Offline gate remains
in PYTHONPATH. Full normalizer analysis/audit require approved file access; logs
stay in each supervisor directory. No worker may overlap another guarded job.
Session 20156 finished exit 0: all 59 candidate/control pairs now have complete outputs or the preserved explicit control exporter failure. No new resource stops during the resumed batch. Starting first full comparison scoring with frozen code, fresh jobs/comparison-analysis (1200-second deadline), offline gate, research interpreter and recorded scoring environment.
Frozen comparison scoring completed: candidate primary composition-macro F1 0.5313290603 vs control 0.4139483028, delta 0.1173807575; paired bootstrap 95% interval [0.0240277078, 0.2202143270], exact one-sided/Holm p=0.0174827576 (one frozen claim). This is supported superiority on the observed screen only; generated regressions remain and no production recommendation/promotion is authorized. Starting full relevant regression under the recorded 1200-second guard.
Full Research/Bridge regression supervisor completed exit 0 in 36.531 seconds. JUnit is full-regression.xml; no failure/error. Starting final offline provenance/scoring reproduction audit in jobs/final-audit, deadline 900 seconds, research interpreter, CPU affinity 8, existing safeguards unchanged.

2026-10-08 Phase 2 acceptance: COMPLETE WITH QUALIFICATIONS. Final audit supervisor
passed in 49.578 seconds. All150 native receipts (149complete/1failed),6608 declared
capture artifacts,51 protected runtime/455-contract assets,3 acquisition archives,
42 preserved interrupted artifacts and118 reproduced scores/timed-events verified.
Composition macro and paired bootstrap/exact/Holm statistics reproduce exactly.
Full JUnit:417cases,2skipped,0failures/0errors;17focused fixtures already passed.
Candidate/control primary F1 .5313290603/.4139483028, supported observed-screen gain
with two generated-measure regressions and unknown training overlap; no component
attribution or production readiness. No frozen code/config tuning or shipped changes.
Network:804216858reserved/119268255retained payload/200512129charged payload ceiling,
all below3000000000cap; no further downloads/installations. Current usable physical
RAM33549094912bytes; percentage admission scales automatically, mandatory safeguard
limits retained. Runtime cohorts in audit/report; exclude the transition pair from
matched performance claims. Original failed supervisor/ordinary export failure and
partial files remain. All terminal sessions finished, no worker or lock remains.
Final REPORT.md, MAIN_PLAN.md, plans index and handoff close Phase2 only. Next action
is review before separately authorizing conditional Phase3 or Phase4; neither began.
Closeout documentation validation: fresh guarded jobs/document-links, deadline60, research interpreter. Check local Markdown targets in MAIN_PLAN, plans index, current handoff and Phase2 REPORT/job-record/development-review; keep external URLs and historical artifacts unchanged.
Closeout documentation link validation passed (jobs/document-links). Final active plan/index/handoff link to Phase2 REPORT and preserve historical Phase1 records. No subsequent inference, tuning or later-phase dispatch.
