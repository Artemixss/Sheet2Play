# Phase 1 execution record

Owner: [MAIN_PLAN.md](../../../../../plans/MAIN_PLAN.md),
`2026-10-06-homr-timing-465`. Authorized 2026-10-07: **Phase 1 only**.
Hard network cap: **2,000,000,000 bytes**. Use local inputs, no downloads,
installs, source fetches, cloud jobs, production changes or Phase 2 execution.

Cwd: `C:\Users\bur4x\Desktop\lecture\big_projects\Sheet2Play`.
Supervisor: `Research/omr/guarded_execution.py`; interpreter:
`Research/omr/.venv/Scripts/python.exe`. Set `PYTHONPATH` to this directory's
`gate`, `Research/omr`, and `Research/omr/src`. The inherited Python audit hook
blocks sockets/name resolution and Git launches. No substantive CPU job runs
outside the existing supervisor: 85% RAM/commit, 4 GiB reserve/worker cap,
16 processes, one worker, deadline below four hours. GPU inference additionally
requires fresh separate device admission and no competing training.

Before execution, the previous lock named supervisor 7236, absent from the
live process inventory. No Python/dotnet/Git/Sheet2Play process was present.
Its log ended at `Verifying base_python_runtime`; no result receipt exists.
Preserved the lock as `prior-interrupted-worker.lock`, without altering the
previous job's logs or inventing its outcome. See `preflight.json`.

Planned sequential jobs: `jobs/inventory` (runtime hashes/import probe and
32-item eligibility ledger, 1800 seconds); `jobs/focused` (conversion/tie and
Phase 1 fixtures, 600 seconds); `jobs/playback` (offline .NET playback/OMR tests,
600 seconds); development traces under fresh guarded receipts; then required
research/Bridge regression. Every receipt records the exact command, cwd,
source hashes, PID, resource samples and bounded log. Inspect completion before
dependent jobs; preserve failures and do not automatically retry pressure stops.

Research implementation: `Research/omr/homr_baseline.py`. Output in this directory.
No historical score is relabelled as a fresh baseline. Do not start Phase 2.

Playback attempt: test build completed; Windows 1816 prevented test-host spawning inside containment. Receipt reports 62.28% peak RAM, 44.53% commit, no pressure stop and clean Job closure. Do not repeat the build invocation. Next use direct vstest on the freshly built DLL, a two-CPU runtime and a 256 MiB GC heap bound per process; keep all supervisor limits. This isolates test execution from MSBuild/compiler-server allocation. The exact memory/process quota responsible remains unverified.


Development inference: fresh GPU inspection found RTX 4050, 6141 MiB total, 0 MiB used, no compute application/training. Native shipped source/weights/Bridge hashes must match inventory before execution. Research-only hooks capture decoder outputs and exporter inputs without changing returns. Diagnostics enable debug images and staff-position files; musical/default title settings are retained. First guarded item: generated-baseline-piano-001, 600-second deadline; full remaining collection only after inspecting this receipt. Device usage sampled every two seconds; >=90% or unavailable telemetry stops the owned worker. Evidence: development/<id>/result.json, tokens.json, PNG/crop/position/XML artifacts and GPU JSONL.


Representative native inference completed, receipt jobs/development-one: 21.406 seconds, complete/exit 0. Inspectable decoder tokens, exporter inputs, detected positions, staff crops and MusicXML were saved. Full remaining collection command uses the same launcher/identity and a 5400-second deadline, reuses the completed control only after checking its declared hashes; no scoring of unverified OpenScore first pages.


STOP: native batch completed with allocation failures (RapidOCR bad allocation at generated-tie_across_barline; NumPy allocation refusal on all 20 OpenScore pages). 32 receipts: 10 XML successes, 22 failures. Only eight completed controls preceded the first resource failure. Two subsequent XML successes are quarantined as post-resource-failure evidence. The batch wrapper incorrectly continued to later inputs after first allocation failure; preserve executed-source and all receipts, fix its fail-safe, and do not retry inference automatically. Peak RAM 70.05%, commit 55.61%, clean Job closure; system pressure gate did not trigger. Whether aggregate worker containment or another allocator constraint caused the allocation refusal is not independently established. No accuracy ranking or Phase 2 admission is justified.


Independent frontend regression: prior direct test assembly was cached (timestamp 2026-09-17), not proof of a new build. Run a serial build/test of current sources with no restore, no compiler server, no node reuse, two visible .NET CPUs and 256 MiB GC heap bound. Include SongCache MIDI tests and all frontend tests, not only playback. No app publish or installed-binary claim.


Independent analysis (not inference retry): analyze only eight controls completed before the first allocation error; verify all declared artifacts, report first divergent measure, reference MIDI preservation, duration confusion/majority/balanced accuracy/macro-F1 and exact production/research tie boundary. Quarantine later outputs. Command: guarded execution, jobs/analysis, 600 seconds, research Python homr_baseline_analyze.py --output phase1 evidence directory.

## Final outcomes

| Receipt directory | Result |
| --- | --- |
| inventory | Complete; runtime identity and 32-item eligibility ledger |
| focused | Complete; initial conversion/tie/baseline fixtures |
| playback | Failed; Windows 1816 test-host quota refusal, preserved |
| playback-direct | Complete; 51 tests on cached assembly, diagnostic only |
| development-one | Complete; representative generated baseline |
| development-remaining | Failed; allocation refusals, no inference retry |
| frontend-regression | Failed; colon arguments split by PowerShell, preserved |
| frontend-regression-quoted | Complete; fresh serial source build, all 69 frontend tests |
| analysis | Complete; eight pre-failure controls and exact tie/MIDI boundary |
| failsafe-tests | Complete; nine tests including mocked native batch stop |
| regression | Complete; 394 JUnit cases, two skipped, zero failures/errors |
| regression-final | Complete after stop-on-resume/log-opening changes; same 392 passed and two skipped |
| closeout | Complete; 56 protected runtime and 362 inference artifact hashes verified |

All commands/cwd/configuration/deadlines and failures remain in their respective
`jobs/<name>/result.json`, `resources.jsonl` and `worker.log`. The executed capture
sources are frozen under `executed-source/`; corrected source is research-only.
No checkpoint/inference rerun, shipped patch, app publish or Phase 2 activity.

Acceptance is **partial/resource-stopped**, as explained in [REPORT.md](REPORT.md).
Final [network/process snapshot](network-closeout.json) has no owned worker or
root lock. Research transfers/downloads/installs were zero; Wi-Fi counters reset,
so endpoint readings do not establish unrelated host-wide traffic totals.
The execution hard cap is 2,000,000,000 bytes. Review allocator/containment failure
before explicitly resumed Phase 1 inference with fresh output and unchanged
safeguards. Do not automatically retry failed receipts or silently reuse the two
post-failure XML successes. OpenScore page ranges remain unverified.

