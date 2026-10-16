# Phase 1 revalidation — 2026-10-07

Owner: [MAIN_PLAN.md](../../../../../../plans/MAIN_PLAN.md), plan
`2026-10-03-zeus-attribution-repair`. User requested **Phase 1 only** with a
hard **2,000,000,000-byte** total network limit. Existing Phase 1 is complete;
this request revalidates its evidence without overwriting the original closeout.
Later historical phases remain historical; this execution does not authorize them.

## Authorized work and execution record

Repository cwd: `C:\Users\bur4x\Desktop\lecture\big_projects\Sheet2Play`.
No Python/Git process or `.research-worker.lock` at initial inspection.
Interpreter: existing `Research/omr/.venv/Scripts/python.exe`.
All CPU workers use `Research/omr/guarded_execution.py`, its unchanged 85%
RAM/commit gate, 4 GiB reserve, 4 GiB worker containment and 16-process limit.
No pressure failure may be retried automatically.

Planned commands, using this directory as `$evidence`:

```powershell
$env:PYTHONPATH = "$evidence/gate;Research/omr;Research/omr/src"
& Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output "$evidence/jobs/bytes" --max-seconds 1800 -- Research/omr/.venv/Scripts/python.exe -B -c "from zeus_attribution_prepare import configure_cpu; configure_cpu(); import runpy; runpy.run_path('Research/omr/zeus_attribution_verify.py', run_name='__main__')" Research/omr/reports/zeus-attribution/phase1/diagnostic-identity.json --output "$evidence/verified-bytes.json"
& Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output "$evidence/jobs/fixtures" --max-seconds 300 -- Research/omr/.venv/Scripts/python.exe -B -c "from zeus_attribution_prepare import configure_cpu; configure_cpu(); import pytest; raise SystemExit(pytest.main(['Research/omr/tests/test_zeus_provenance.py', '-q', '-p', 'no:cacheprovider']))"
```

Logs and resumable progress: `jobs/<name>/worker.log`, `resources.jsonl`,
`result.json`; receipts retain actual arguments and process identifiers.
No model construction, inference, scoring or Phase 2 work is planned.

Network policy: reuse the cached original public release archive; make no network
requests, dependency installation or source fetch. The local `gate/sitecustomize.py`
blocks Python network access and Git launches in supervisor/worker processes.
Task artifact transfer budget is therefore 0 bytes used of 2,000,000,000 bytes.
This does not claim to meter unrelated host traffic or Codex service traffic.

## Checkpoint

**Resume authorized, 2026-10-07:** user cleared RAM and explicitly requested another
attempt. Fresh inspection found no Python/Git process or worker lock. Run the
recorded byte command with `jobs/bytes-2`, retaining the original blocked receipt.
Output remains `verified-bytes.json` (not yet created). This supersedes the earlier
stop as the active checkpoint; resource limits/network cap and Phase 1 boundary
are unchanged. No automatic pressure retry is authorized after this attempt.

**Stopped at admission.** [Byte-verification receipt](jobs/bytes/result.json):
`physical_RAM_at_or_above_85_percent`, RAM **88.326498%** at
2026-10-07 16:53:13 Europe/Istanbul. System commit was 22,152,384,512 /
35,696,578,560 bytes. No worker launched; no cleanup error, Python process or
repository worker lock remained. No automatic retry is pending.

[Report and acceptance ledger](REPORT.md), [machine-readable closeout](closeout.json).
Fixtures, fresh import probe, cached release comparison and complete byte verification
remain unexecuted in this request. The original accepted Phase 1 evidence is preserved;
its completed status is not revoked by current admission pressure. Historical
execution-time upstream source remains unverified. No implementation change occurred.

Next action requires explicit resume after RAM relief: inspect processes/lock, run
fresh admission and the byte-verification command above with a **new** `jobs/bytes-2`
destination. Never overwrite the blocked receipt or launch another copy. Inspect
the result before dependent fixtures, cached bundle checks or an import-only probe.
Keep the offline/Git gate and all existing resource limits. Stop before Phase 2.

Final documentation checks passed: all report/handoff relative links resolve;
closeout JSON agrees with the admission receipt, zero transfer count and no Phase 2
execution. Plan/index revalidation pointers resolve. Worker lock remains absent.
