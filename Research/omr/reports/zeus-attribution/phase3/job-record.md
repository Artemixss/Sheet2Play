# Phase 3 job record — 2026-10-04

## Current state — fixed execution and reporting finished, 2026-10-05

The [Phase 3 report](REPORT.md) supersedes earlier active/no-inference statements.
All15 fixed inputs/25 crops/50 recipe outputs and30 stitched analyses completed.
Verdict mixed causes; full acceptance incomplete, with every criterion labeled.
75 focused fixtures passed; final regression328 passed,14 unchanged failures,
2 skipped,9 subtests passed. [Final regression receipt](resume-20261005-1746/regression-parser-trace/result.json).
[Artifact audit](artifact-audit.json):207 hashes,30 stitched note multisets preserved,
49/50 base-pitch multisets,109 missing full-rest durations,2106 internally consistent
typed durations. [Conversion replay](conversion-diagnostics.json):50/50 byte parity,
15 outputs/57 hidden diagnostic lines (29 upstream/28 wrapper), orphan G3 identified.
Replay-v3 complete/exit0,6.641s, peak RAM54.298%/commit44.364%; earlier serialization
failures preserved. [Receipt](resume-20261005-1746/conversion-diagnostics-v3/result.json).
No worker remains; no inference retry pending. All current live logs/receipts and
diagnostic scripts were preserved from ignored runtime into resume evidence.
Final [native inspection](resume-20261005-1746/final-native.json),19:35local:
RAM54.104%,commit44.227%,18.542GiB headroom, no Python/Git processes or worker lock.
No pressure stop during this resume;85% RAM/commit and4GiB reserve retained.
Earlier pressure receipts and initiating-cause uncertainty remain valid.
No Phase4 remedy, Rokot, new screen, training, spending or promotion authorized.

## 2026-10-05 final conversion observability audit

All prediction/scoring workers are complete. Final focused fixtures: 75 passed;
full regression: 328 passed, 14 unchanged failures, 2 skipped, 9 subtests passed.
Artifact audit verified 207 hashes and all 30 stitched note-element multisets.
One orphan G3 token is absent from generated-offset_entry upstream system 1 XML.
The unchanged wrapper constructs Delinearizer without errout; warnings go into a
private StringIO rather than captured stderr. Empty recorded stderr proves no
warning absence. Replay all 50 saved LMX strings without a model, explicitly
capture errout and require byte-identical XML before accepting diagnostics.
Command recorded before execution; repo cwd, one guarded worker, no Git:

```powershell
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/.runtime/phase3/resume-20261005-1746/conversion-diagnostics --worker-limit-mib 512 --max-seconds 120 -- Research/omr/zeus/.venv/Scripts/python.exe -B Research/omr/.runtime/phase3/resume-20261005-1746/replay_conversion.py
```

Earlier live-job statements below are dated history, superseded by this section.

First replay failed on first-file byte parity after 6.484s (no pressure stop).
Its receipt and exact script are preserved. A diagnostic-only follow-up prints
the first differing byte/context before aborting; it neither overwrites XML nor
relaxes event parity. Command recorded before this follow-up:

```powershell
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/.runtime/phase3/resume-20261005-1746/conversion-diagnostics-v2 --worker-limit-mib 512 --max-seconds 120 -- Research/omr/zeus/.venv/Scripts/python.exe -B Research/omr/.runtime/phase3/resume-20261005-1746/replay_conversion.py
```

V2 identified the difference after 5.875s: filename-based ElementTree serialization
on Windows writes CRLF after the XML declaration, while BytesIO used LF. The
replay now uses the identical filename-based writer into separate ignored files,
retaining the original artifacts and byte-parity requirement. No converter change.

```powershell
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/.runtime/phase3/resume-20261005-1746/conversion-diagnostics-v3 --worker-limit-mib 512 --max-seconds 120 -- Research/omr/zeus/.venv/Scripts/python.exe -B Research/omr/.runtime/phase3/resume-20261005-1746/replay_conversion.py
```

## 2026-10-05 CPU detector preparation correction

Canonical analysis completed11.891s, all15 items/30 recipe pages accepted by unchanged
conversion/stitch/Bridge. Item-macro primary F1.0064309 upstream/.0041483 wrapper.
All25 token sequences differ; direct-dataset parity and resized-prefix equality pass
for every crop. All50 outputs terminate at EOS, no unknown tokens/conversion exceptions.
Every stitched page has an unavailable strict XML trace. The supplemental parser
diagnostic observes the unchanged Bridge parser before stripTies, symmetrically on
prediction/reference; it preserves inferred-timing limitations and changes no primary
score, input, model or recipe. Source/manifest/analysis hashes are recorded separately.

```powershell
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/.runtime/phase3/resume-20261005-1746/parser-diagnostics --max-seconds 300 -- Research/omr/.venv/Scripts/python.exe -B Research/omr/zeus_attribution_parser_trace.py
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/.runtime/phase3/resume-20261005-1746/regression-parser-trace --max-seconds 300 -- Research/omr/.venv/Scripts/python.exe -B Research/omr/.runtime/phase3/resume-20261005-1746/regression-gate/run_regression.py
```

All50 recipe/system outputs completed: representative30.782s, remaining98.469s;
remaining peak RAM57.064%/commit48.294%. No pressure stop or automatic retry.
The first representative diagnostic incorrectly zeroed pages on strict trace errors
although unchanged Bridge accepted their XML. Missing-duration invisible full rests
and negative backups are retained as trace findings. Primary failure policy now uses
conversion, unchanged stitch and stitched-page normalization; per-system diagnostics
do not create a new admission gate.74 focused tests passed9.06s, including real
Bridge and whole-page cases. The old manifest/results are preserved under
`resume-20261005-1746/diagnostic-trace-gate-v1`. Only analyzer source changed in
manifest-v2; all inputs/inference/conversion/model/scorer pins match, so cached
predictions are reused without inference rerun.

```powershell
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/.runtime/phase3/resume-20261005-1746/analyze-representative-v2 --max-seconds 300 -- Research/omr/.venv/Scripts/python.exe -B Research/omr/zeus_attribution_analyze.py --item-id openscore-6211535-page-1 --output-name representative-analysis
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/.runtime/phase3/resume-20261005-1746/regression-trace-policy --max-seconds 300 -- Research/omr/.venv/Scripts/python.exe -B Research/omr/.runtime/phase3/resume-20261005-1746/regression-gate/run_regression.py
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/.runtime/phase3/resume-20261005-1746/analyze-all --max-seconds 300 -- Research/omr/.venv/Scripts/python.exe -B Research/omr/zeus_attribution_analyze.py
```

Preparation-v2 completed152.984s,15 inputs/25 crops frozen, RAM59.672%/commit48.863%
peaks. [Receipt](resume-20261005-1746/prepare-v2/result.json).
All crops reviewed before model inference: [coverage review](CROP_REVIEW.md).
Eleven controls clip notation;6211555 has an overlapping duplicate bass crop.
These actual integration defects remain in identical recipe inputs. No Phase4 remedy.
Final corrected regression325 passed,14 unchanged failures,2 skipped,9 subtests;
failure IDs compared with probe-context run, no additions/removals.
[Receipt](resume-20261005-1746/regression-cpu-detector/result.json).
Representative inference active session85053, runtime `infer-representative`;
command recorded below. Inspect result/lock before analysis or another worker.

Final probe-context regression completed:324 passed,14 failed,2 skipped,9 subtests;
the same12 Git-prohibited legacy tests and2 strict metadata baseline failures.
[Receipt](resume-20261005-1746/regression-probe-context/result.json).
Preparation failed before detector inference because the default CPU constructor
requested absent float32 weights; only the pinned FP16 weights exist. No pressure
stop:10.312s, RAM50.826%/commit44.879% peaks, worker exit1.
[Failed receipt and partial inputs](resume-20261005-1746/prepare/result.json) preserved.
The diagnostic now constructs an explicit CPUExecutionProvider session using those
same FP16 bytes and HOMR's installed run/patch/merge implementation,8 intra-op/1
inter-op threads. No installed runtime source, model, package or shipped behavior changes.
The first focused command used a nonexistent test filename (exit4, no tests); its
receipt remains in runtime. Corrected focused validation precedes a bounded single
baseline detector check, then all15 input preparation and fresh crop review.
No Zeus model inference has started. Full green regression acceptance remains unmet.

Corrected focused suite:72 passed8.92s, supervisor complete15.172s. Single baseline
CPU smoke completed16.500s, detected the expected2 systems; RAM59.798%/commit48.815%
peaks. Provider CPU-only, FP16 weights SHA256
`60f495496cb41473c0521d0811d8f44b9d5cff892d287974a8aebb3eaee2fa83`.
[Smoke receipt](resume-20261005-1746/detector-smoke/result.json),
[runtime evidence](resume-20261005-1746/detector-smoke-output/cpu-runtime.json).
Commands (repository cwd; live logs ignored, copied after completion):

```powershell
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/.runtime/phase3/resume-20261005-1746/regression-cpu-detector --max-seconds 300 -- Research/omr/.venv/Scripts/python.exe -B Research/omr/.runtime/phase3/resume-20261005-1746/regression-gate/run_regression.py
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/.runtime/phase3/resume-20261005-1746/prepare-v2 --max-seconds 3600 -- Research/omr/.venv/Scripts/python.exe -B Research/omr/zeus_attribution_prepare.py prepare --verification-result Research/omr/reports/zeus-attribution/phase3/resume-20261005-1746/identity-bytes/result.json
```

## 2026-10-05 afternoon: explicit resume

The user explicitly requested continuation, revoking the pause. Native17:46:12local
inspection found RAM73.74%,commit44%,18.43GiB commit headroom, no Python/Git/Codex
process under those names and no worker lock. The earlier app-side pressure mechanism
is not established as durably fixed. This manual resume permits one fresh attempt after
bounded preflight; there is no automatic retry if system pressure recurs.

To reduce live diff churn, operational logs are written inside ignored `.runtime`
and copied into the evidence directory after completion. Historical evidence remains.
85% RAM/commit,4GiB reserve and process/deadline containment remain enforced.
The byte verifier uses a smaller512MiB worker allowance, supported by its previously
observed182MiB footprint; detector/model jobs require separate fresh admission.

Commands pre-recorded; repository-root working directory. Verification is dependent
on a successful preflight receipt and remains sequential:

```powershell
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/.runtime/phase3/resume-20261005-1746/preflight --worker-limit-mib 512 --max-seconds 120 -- Research/omr/.venv/Scripts/python.exe -B Research/omr/.runtime/phase3/resume-20261005-1746/preflight.py
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/.runtime/phase3/resume-20261005-1746/identity-bytes --worker-limit-mib 512 --max-seconds 3600 -- Research/omr/.venv/Scripts/python.exe -B Research/omr/zeus_attribution_verify.py Research/omr/reports/zeus-attribution/phase1/diagnostic-identity.json --output Research/omr/reports/zeus-attribution/phase3/verified-bytes.json
```

Bounded preflight passed; [receipt](resume-20261005-1746/preflight/result.json)
complete/exit0,50.891s. Monitor check45s, peak RAM72.950%,commit44.146%, no observed
Git processes, maximum system sampling latency16ms. This supports a guarded attempt,
not a claim that the external app defect is durably fixed.

Byte verification started17:51local, session39444, supervisor29100 and completed18:11local.
[Receipt](resume-20261005-1746/identity-bytes/result.json) complete/exit0,1211.578s;
all113385 runtime files and50 inherited detector files verified. Peak RAM77.671%,
commit46.705%, Git3/private36.55MiB; no pressure stop and lock removed. Runtime
logs were copied after completion, retaining the originals. This successful attempt
does not prove a durable resolution of the prior external diff growth.

Progress was invisible during that run because the output reader buffered64KiB
before writing and did not flush. After job completion, switched to buffered
`read1` and per-block flush, preserving the8MiB cap. A real pipe fixture checks
that progress reaches disk while the producer remains alive. Focused validation
and the deferred tie diagnostic commands recorded before execution:

```powershell
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/.runtime/phase3/resume-20261005-1746/focused-progress --max-seconds 180 -- Research/omr/.venv/Scripts/python.exe -B -m pytest Research/omr/tests/test_execution_safety.py Research/omr/tests/test_zeus_attribution.py -q -o addopts=
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/.runtime/phase3/resume-20261005-1746/tie-diagnostic --max-seconds 180 -- Research/omr/.venv/Scripts/python.exe -B Research/omr/zeus_attribution_ties.py --output Research/omr/.runtime/phase3/resume-20261005-1746/tie-cases
```
After it completes, full research/Bridge regression will use the transient
`.runtime/phase3/resume-20261005-1746/regression-gate/run_regression.py` harness.
Its Python audit hook rejects Git subprocesses before launch and is inherited by
Python children through temporary PYTHONPATH. This enforces recovery policy;
Git-dependent tests may fail explicitly, with no historical identity mock or skip.
The environment setting is scoped to that worker and is not used for import probes.
Regression command recorded before execution; one worker at a time:

```powershell
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/.runtime/phase3/resume-20261005-1746/regression --max-seconds 300 -- Research/omr/.venv/Scripts/python.exe -B Research/omr/.runtime/phase3/resume-20261005-1746/regression-gate/run_regression.py
```

Dependent commands, recorded before execution; each requires a fresh supervisor
admission and completion of its prerequisites. Import resolution must match Phase1;
prepared crops must be visually reviewed before model inference. Commands use the
actual Zeus interpreter and the successful new verification receipt, not an old
blocked receipt. No command below has started at this record update.

```powershell
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/.runtime/phase3/resume-20261005-1746/import-probe --max-seconds 300 -- Research/omr/zeus/.venv/Scripts/python.exe -B Research/omr/zeus_attribution_infer.py probe
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/.runtime/phase3/resume-20261005-1746/prepare --max-seconds 3600 -- Research/omr/.venv/Scripts/python.exe -B Research/omr/zeus_attribution_prepare.py prepare --verification-result Research/omr/reports/zeus-attribution/phase3/resume-20261005-1746/identity-bytes/result.json
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/.runtime/phase3/resume-20261005-1746/infer-representative --max-seconds 1800 -- Research/omr/zeus/.venv/Scripts/python.exe -B Research/omr/zeus_attribution_infer.py infer --item-id openscore-6211535-page-1
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/.runtime/phase3/resume-20261005-1746/analyze-representative --max-seconds 300 -- Research/omr/.venv/Scripts/python.exe -B Research/omr/zeus_attribution_analyze.py --item-id openscore-6211535-page-1 --output-name representative-analysis
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/.runtime/phase3/resume-20261005-1746/infer-remaining --max-seconds 3600 -- Research/omr/zeus/.venv/Scripts/python.exe -B Research/omr/zeus_attribution_infer.py infer --skip-item-id openscore-6211535-page-1
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/.runtime/phase3/resume-20261005-1746/analyze-all --max-seconds 300 -- Research/omr/.venv/Scripts/python.exe -B Research/omr/zeus_attribution_analyze.py
```

## 2026-10-05: actual system pressure and monitor correction

Import-probe-v2 reached Zeus but failed distribution equality solely for the newly
visible repository metadata `sheet2play-omr-research:0.1.0`. All other selected fields
matched, and the closed runtime bytes had passed. The diagnostic had added `omr/src`
to sys.path, unlike Phase1. The unchanged collector now runs with only that additional
distribution search path temporarily excluded; paths are restored even on failure.
Diagnostic source pins remain separate; no installed distribution/version is filtered
or changed. A fixture verifies context isolation and restoration. Original false probe
outputs are retained under [v2 evidence](resume-20261005-1746/import-probe-v2/import-probe-comparison.json).
Commands for the identified setup correction recorded before execution:

```powershell
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/.runtime/phase3/resume-20261005-1746/focused-probe-context --max-seconds 180 -- Research/omr/.venv/Scripts/python.exe -B -m pytest Research/omr/tests/test_execution_safety.py Research/omr/tests/test_zeus_attribution.py -q -o addopts=
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/.runtime/phase3/resume-20261005-1746/import-probe-v3 --max-seconds 300 -- Research/omr/zeus/.venv/Scripts/python.exe -B Research/omr/zeus_attribution_infer.py probe
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/.runtime/phase3/resume-20261005-1746/regression-probe-context --max-seconds 300 -- Research/omr/.venv/Scripts/python.exe -B Research/omr/.runtime/phase3/resume-20261005-1746/regression-gate/run_regression.py
```

Afternoon import probe failed before Zeus imports/model construction: new preparation
module eagerly imported detector adapters requiring psutil, absent from the frozen
Zeus environment. [Failed receipt](resume-20261005-1746/import-probe/result.json)
is retained; no probe output was written. Diagnostic preparation imports are now
lazy, and native Windows affinity/BelowNormal calls replace the extra dependency.
No package installation or frozen-runtime change. Repeat focused/full checks and
run a fresh import-probe-v2 after this identified code correction, not a pressure retry.

```powershell
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/.runtime/phase3/resume-20261005-1746/focused-import-fix --max-seconds 180 -- Research/omr/.venv/Scripts/python.exe -B -m pytest Research/omr/tests/test_execution_safety.py Research/omr/tests/test_zeus_attribution.py -q -o addopts=
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/.runtime/phase3/resume-20261005-1746/import-probe-v2 --max-seconds 300 -- Research/omr/zeus/.venv/Scripts/python.exe -B Research/omr/zeus_attribution_infer.py probe
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/.runtime/phase3/resume-20261005-1746/regression-import-fix --max-seconds 300 -- Research/omr/.venv/Scripts/python.exe -B Research/omr/.runtime/phase3/resume-20261005-1746/regression-gate/run_regression.py
```

Afternoon post-verification checks:70 focused passed, supervisor16.578s; deferred
tie diagnostic complete/exit0,6.969s. [Tie controls](resume-20261005-1746/tie-cases/diagnosis.json)
give original6 written/4 exact merged/6 normalized,F1.4. Removing the independent
voice gives5/3/3,F1=1; removing layout, note types or voice-container inconsistency
preserves all pitched events and still fails to merge. This supports interleaving in
music21's flattened adjacency-based tie processing; the ablation is not a remedy.

Full regression session99471 ended failed/exit1,51.985s:323passed,14failed,2skipped,
9subtests passed. Twelve failures contain the audit-hook Git prohibition; no Git
subprocess launched. Two retain the known strict freeze metadata mismatch. Preserve
[JUnit](resume-20261005-1746/regression-junit.xml) and [worker log](resume-20261005-1746/regression/worker.log).
Complete suite attempted; full green acceptance is unmet. No tests omitted or freeze
identity changed. This historical/policy limitation does not substitute for passing
current focused contracts or byte verification; those passed before dependent diagnostics.

### Afternoon source-contract review, before model execution

Inspected the pinned `zeus/source/zeus/zeus.py` implementation:
`LMXDataset.tf_dataset` decodes one grayscale channel to float32, resizes to height192
with aspect ratio/antialiasing, ragged-batches and prefetches. The released options
have no width cap. The unmodified wrapper uses that resize recipe, then white padding
to a multiple of500 and declares the full padded width through its RaggedTensor.
The encoder derives valid steps as ceil(row width/16) and passes the corresponding
sequence mask to its bidirectional recurrent layers. The diagnostic captures actual
widths, tensor hashes/ranges and prefix equality; output differences compare the
documented combined padding/mask recipe. They do not independently isolate padding
from mask exposure or establish that one is solely causal.

Decoder BOS/EOS is0 internally; EOS is excluded from returned lengths. `predict_step`
subtracts1 from non-EOS indices. Returned tag index0 is therefore the vocabulary's
unknown token, which the wrapper removes while the diagnostic upstream text retains.
The released configuration caps prediction at700; returned length700 indicates the
cap, shorter indicates EOS. Source inspection supports this termination accounting;
actual token/output evidence still requires inference. No model/upstream/wrapper change.

The user reported a possible97% memory reading and explicitly authorized adjusting
limits without another approval request. The new verifier subsequently stopped for
actual system commit pressure: [receipt](identity-bytes-ram-commit/result.json),
elapsed1116.265s, peak commit97.030%, physical RAM70.078%, peak recorded Git count620
and private bytes11,458,371,584. No verified-bytes output; worker exit0 was cleanup,
not successful verification. Worker log ends at `Verifying research_environment`.
Global lock was removed after Job closure. No automatic verifier retry is authorized.

Native process inspection separately counted729 `git diff --no-index` processes,
one repository-associated `diff --numstat` and one `status --porcelain`. Recorded
Git rows include Codex PID27788, whose executable path was independently verified.
The verifier previously used about182MiB private memory. This strongly implicates
app-side diff growth as a contributor; it does not attribute all system commit or
establish the original cause of the earlier crashes. No external process was killed.

System samples were109.123s apart before the stop, despite an intended0.5s sampling
interval. Code review found synchronous Git enumeration before the pressure gate.
The correction separates asynchronous, timestamped Git telemetry from fresh Windows
system counters, closes the owned Job before stop diagnostics, lowers default system
RAM/commit stops to85%, and increases commit reserve to4GiB. Admission reserves the
worker budget plus that reserve. Worker4GiB/16-process containment remains.
Git counters remain record-only; pending/failed/stale telemetry is labelled.

Focused validation only, not a retry of the blocked verifier. Command recorded
before execution, repository-root working directory:

```powershell
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/reports/zeus-attribution/phase3/pressure-monitor-fix/focused --max-seconds 180 -- Research/omr/.venv/Scripts/python.exe -B -m pytest Research/omr/tests/test_execution_safety.py Research/omr/tests/test_zeus_attribution.py -q -o addopts=
```

Phase3 detector/model execution is held: acceptance still requires a complete fresh
byte-verification receipt. Resolve recurrent external diff growth before dependent work.
Historical attempts and their policies below are retained unchanged.

Validation69 passed in9.79s; supervisor complete/exit0,15.688s, peak RAM43.948%,
commit41.033%. Receipt records85% system stop and4GiB reserve. Global lock absent.
Session55570 (verifier) and78663 (focused validation) are complete; do not poll them.
Final native check2026-10-05T00:37:31+03:00: RAM42.8%,commit40%,20.22GiB commit
headroom, no Python/Git process and no worker lock. Six active documents/124 local
links checked with zero broken targets. This does not establish a durable app-side fix.

## 2026-10-05: user-authorized RAM/commit policy and resume

User removed the Git-specific memory cutoff and retained system RAM/commit monitoring.
This supersedes both earlier Git count/memory stops and authorizes a new guarded
verification attempt. Git count/private bytes are informational and still logged;
90% RAM/commit,2 GiB headroom,4 GiB aggregate worker Job commit,16 Job processes,
admission budget reservation and deadline remain unchanged. No agent Git invocation.
No automatic retry of actual system-pressure/containment failures.

Commands recorded before execution, repository-root working directory:

```powershell
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/reports/zeus-attribution/phase3/ram-commit-policy/focused --max-seconds 180 -- Research/omr/.venv/Scripts/python.exe -B -m pytest Research/omr/tests/test_execution_safety.py Research/omr/tests/test_zeus_attribution.py -q -o addopts=
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/reports/zeus-attribution/phase3/identity-bytes-ram-commit --max-seconds 3600 -- Research/omr/.venv/Scripts/python.exe -B Research/omr/zeus_attribution_verify.py Research/omr/reports/zeus-attribution/phase1/diagnostic-identity.json --output Research/omr/reports/zeus-attribution/phase3/verified-bytes.json
```

Sequential only: inspect focused receipt, live workers/lock and native admission before
new verification. Earlier blocked receipts cannot authorize preparation. Keep this
current section separate from preserved historical policy and interruption records below.

Focused revised-policy fixtures62 passed in8.49s; supervisor complete/exit0,14.172s,
peak RAM44.465%,commit41.294%. Count150/private3GiB is informational in native worker
fixture; independent RAM90%/commit90%/headroom/containment failures still stop.
Inspection immediately before verification found no Python/Git workers or global lock.

## User-authorized continuation and operational policy revision

User requested continuation and removal of unjustified process-count stops after the
15-process interruption. Count alone is now recorded, not a stop condition. The prior
burst had193 MB Git private memory,61% RAM and45% commit, so recorded measurements did
not establish imminent memory exhaustion. Git memory at1 GiB,90% RAM/commit,2 GiB
headroom,4 GiB aggregate Job commit,16 Job processes and deadline still stop execution.
This supersedes the count-only rule below and in earlier Phase2 records; no automatic
retry of an actual memory-pressure failure is introduced. No agent Git invocation.

Focused safety and attribution command; working directory remains repository root:

```powershell
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/reports/zeus-attribution/phase3/focused-resume --max-seconds 180 -- Research/omr/.venv/Scripts/python.exe -B -m pytest Research/omr/tests/test_execution_safety.py Research/omr/tests/test_zeus_attribution.py -q
```

Next after focused checks: byte-only verification in `identity-bytes-resume` with a
longer bounded deadline, fresh import-only probe, preparation and fixed development replay.
Preserve the interrupted verifier logs and require a complete new supervisor receipt.

First focused run failed two obsolete pressure-trigger fixtures; remaining checks passed.
Those mocks now trigger retained Git memory pressure. Verifier review also corrected
selected-source pins being mistaken for a closed whole-repository inventory; new fixture
checks unrelated files are allowed while changed/escaping pinned sources fail.
Revised focused command uses output `focused-resume-v2`, same interpreter/tests/deadline.

Byte verification command after focused acceptance:

```powershell
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/reports/zeus-attribution/phase3/identity-bytes-resume --max-seconds 3600 -- Research/omr/.venv/Scripts/python.exe -B Research/omr/zeus_attribution_verify.py Research/omr/reports/zeus-attribution/phase1/diagnostic-identity.json --output Research/omr/reports/zeus-attribution/phase3/verified-bytes.json
```

Focused51 checks passed: `focused-resume-v2`, exit0,14.078s. Byte verifier started
2026-10-04 around19:41UTC, session45074. Resource sample19:52UTC:47.68% RAM,
15.42/35.70GB commit,Git0; worker was active at that sample. No second heavy worker admitted.

### Retained memory-guard interruption

Verifier ended blocked at2026-10-04T19:56:36.061666+00:00 (elapsed999.063s),
`unexpected_Git_private_memory`:150 external Git processes,2,734,989,312 aggregate
private bytes (2.55 GiB) exceeded the1 GiB guard. Peak RAM55.755%, commit55.135%;
this is a policy stop, not proof of an imminent system crash. Stop-time diagnostic
capture recorded `MemoryError`; no verified explanation for that allocation failure.
Saved process records include children of earlier Codex PID24828 and intermediary
parents, but no command lines. The initiating cause remains unresolved.
Worker log ends at `Verifying zeus_environment`; `verified-bytes.json` absent.
Exit0 during owned-tree cleanup is not completed verification. Session45074 no longer
exists. Native inspection2026-10-04T23:49:33+03:00 found no Python/Git workers,
parent24828 absent, global lock absent. No external process was terminated by the agent.
Evidence: `identity-bytes-resume/result.json`, `worker.log`, `resources.jsonl`.
No automatic retry; detector/model jobs below remain held. Focused-input checks may
proceed as separate lightweight validation under unchanged admission/containment.

Pre-inference [image/reference review](REFERENCE_REVIEW.md) completed. Preparation now
uses corrected CPU HOMR detector crops for14 pages and pinned representative reuse;
generated full pages are not systems. Explicit baseline reference system boundaries[0,5]
and leading-rest-preserving system-local diagnosis added; new focused fixtures pending.
Sources and crop bytes remain unfrozen until preparation; no inference yet.

Focused-input checks completed:54 passed, supervisor complete/exit0,15.531s,
`focused-inputs/result.json` and `worker.log`. This includes the three added
system-boundary/leading-rest/underfilled-rest fixtures. Independent required regression
is recorded before execution (no verifier retry or detector/model construction):

```powershell
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/reports/zeus-attribution/phase3/regression --max-seconds 300 -- Research/omr/.venv/Scripts/python.exe -B -m pytest Bridge/tests Research/omr/tests -q -o addopts=
```

For native Windows argument preservation, the actual subprocess argument list includes
the final literal `addopts=`. Inspect this run's receipt/log before claiming acceptance.

Regression failed:319 passed,2 failed,2 skipped,9 subtests passed in48.38s;
supervisor failed/exit1,54.141s, peak RAM60.165%,commit40.938%,Git2/private37,265,408.
Both failures reject historical freeze mismatch (HOMR compatibility and sample-extension
tests). Those legacy test paths also invoke Git indirectly, violating the recovery
restriction; the complete suite should have been inspected for this before launch.
Do not rerun them unchanged or weaken the freeze. Retain all diagnostics.
Read-only freeze diagnosis is recorded before execution with a Python audit hook that
rejects Git subprocesses; it does not retry byte verification or infer current HEAD:

```powershell
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/reports/zeus-attribution/phase3/freeze-diagnosis --max-seconds 180 -- Research/omr/.venv/Scripts/python.exe -B Research/omr/reports/zeus-attribution/phase3/diagnose_freeze.py
```

Diagnosis completed/exit0,6.750s. [Read-only diff](freeze-differences.json):33 added
package metadata entries (16 HOMR,17 research), no other snapshot differences.
This matches the already documented [Phase1 expanded-context failures](../phase1/REPORT.md).
The audit hook prohibited Git; no Git was invoked by this diagnosis. Frozen artifacts
and tests are unchanged; no skip/xfail or narrowed regression was used to mask failures.
All new focused tests pass, but full-suite success in expanded access is not claimed.

Recorded commands (same working directory): focused-input validation is independent;
probe/preparation remain held until a complete new verification receipt exists.
The blocked `identity-bytes-resume/result.json` below cannot authorize preparation;
replace it with a successful new attempt's receipt after manual continuation.

```powershell
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/reports/zeus-attribution/phase3/focused-inputs --max-seconds 180 -- Research/omr/.venv/Scripts/python.exe -B -m pytest Research/omr/tests/test_execution_safety.py Research/omr/tests/test_zeus_attribution.py -q
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/reports/zeus-attribution/phase3/import-verification --max-seconds 300 -- Research/omr/.venv-zeus/Scripts/python.exe -B Research/omr/zeus_attribution_infer.py probe
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/reports/zeus-attribution/phase3/preparation --max-seconds 3600 -- Research/omr/.venv/Scripts/python.exe -B Research/omr/zeus_attribution_prepare.py prepare --verification-result Research/omr/reports/zeus-attribution/phase3/identity-bytes-resume/result.json
```

CPU8,CUDA-1,Job4GiB,16 processes and native admission for every job. Do not launch a
queued command until the preceding worker has ended successfully and saved evidence
is inspected. Crop coverage review follows preparation before smoke/full inference.

Authority: user explicitly requested Phase 3 of [MAIN_PLAN.md](../../../../../plans/MAIN_PLAN.md).
Scope: controlled inference/attribution and deferred tied-chord investigation.
No Phase 4 remedy, Rokot execution, frozen evaluation inference, training or promotion.

Working directory: `C:/Users/bur4x/Desktop/lecture/big_projects/Sheet2Play`.
No Python worker/global `.research-worker.lock` visible at admission. CIM process/resource
queries were denied; use the approved native supervisor measurements. No Git invocation.

First command (resource admission only):

```powershell
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/reports/zeus-attribution/phase3/resource-preflight --max-seconds 60 -- Research/omr/.venv/Scripts/python.exe -B -c "import json; from sheet2play_omr.execution_resources import WindowsResourceSampler; print(json.dumps(WindowsResourceSampler()()))"
```

Preserve all existing evidence. Every CPU worker uses the supervisor's unchanged 4 GiB
aggregate commit cap, process cap, 90% RAM/commit stops, Git/headroom stops and deadline.
No automatic pressure retry. Any CPU inference explicitly disables CUDA; existing VRAM
admission/pressure checks remain required for any detector use.

Development selection fixed before inference: all 12 generated controls;
`openscore-6211535-page-1` (existing representative),
`openscore-6211549-page-1`, `openscore-6211555-page-1` (first two further frozen IDs).
Selection follows frozen manifest order without inspecting predictions. Crop bytes must
be identical between actual upstream dataset inference and padded local wrapper.

## Interrupted verifier attempts

Legacy verifier: owned supervisor19636 and recorded descendants9008/13780/13880/18716
were stopped after discovering Git calls. No surviving Python/Git process was visible;
owner-checked stale lock removed. Invoking the legacy verifier violated the no-Git
recovery instruction; exact invocation count is unverified. Do not use it again.

Byte-only command (elevated for native process/resource measurements):

```powershell
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/reports/zeus-attribution/phase3/identity-bytes --max-seconds 600 -- Research/omr/.venv/Scripts/python.exe -B Research/omr/zeus_attribution_verify.py Research/omr/reports/zeus-attribution/phase1/diagnostic-identity.json --output Research/omr/reports/zeus-attribution/phase3/verified-bytes.json
```

Session95048 ended; supervisor status blocked, `unexpected_Git_process_buildup`,
elapsed588.688s. Worker log stops during research-environment verification;
no completed verification JSON. Saved worker exit0 is not proof of completion.
Final sample2026-10-04T18:55:18.720030+00:00:15 Git processes,192,995,328 private bytes.
Several parent PID24828 children; independently inspected parent is Codex `codex.exe`.
Peak RAM61.1389%, commit44.8217%. No cleanup error; last inspection found no workers/lock.
Logs: `identity-bytes/worker.log`, `resources.jsonl`, `result.json`.

Historical count-only hold (superseded by user continuation above): hold CPU execution per [current handoff](handoff.md) until external growth is
addressed and user confirms continuation. No automatic retry. New attempts must use
a new supervisor evidence directory and `prepare --verification-result <new-result>`;
preserve failed logs. No inference, detector, focused tests or regression yet.
