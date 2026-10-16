# Phase 2R interruption handoff — 2026-09-23 16:11 UTC

**Lifecycle update, 2026-10-04:** Superseded interruption record; Phase 2R and its bounded correction subsequently completed.
[Plans/status index](../../plans/README.md) identifies the owning historical
plan and its successor. Current research phases belong to [the main plan](../../plans/MAIN_PLAN.md);
dated next-step/stop statements below do not authorize new execution.

## Stop and scope

The user asked to stop without interrupting active work. No active download was cancelled at this stop. Phase 2R remains **in progress**; Phase 3 frozen evaluation, new training, ranking, and production promotion have not started. The prior 15%-remaining usage rule was explicitly withdrawn by the user and is not active. Earlier chat text cannot be erased, but active repository instructions and the amended canonical plan no longer impose that threshold.

The expanded user plan is `C:\Users\bur4x\.codex\attachments\bedfa1d5-a898-4e55-8983-0fce1e9ae823\Pasted text.txt`. Its Phase 2R scope and later-phase boundaries are now recorded in [COMPARISON_PLAN.md](../../plans/archive/2026-09-26-omr-screening-comparison.superseded.md). [comparison-config-v2.json](comparison-config-v2.json) records eight candidate entries, conditional MuSViT, fine-tuned HOMR as the future approval baseline, and the revised gate; the frozen Phase-1 scoring protocol was not changed.

## Completed in this continuation

- Executed the previously literal-success empty-output and missing-middle-system fixture paths through detection, typed failure propagation, and zero-F1 aggregation. The focused Phase-2/2R tests passed: 18 tests.
- Added actual local identity auditing for installed HOMR source, five ONNX weights, four tokenizers, Bridge patch, Zeus code/weights, croma, VLM files, LEGATO source, and Audiveris. Identity remains incomplete for runtimes still downloading. `croma` 1.2.1 is installed and its SHA-256 is `D20ED24CB4682594ABBCFC92537DFA26BB60464C0FB5D99D274B16A903CF5E24`.
- Added a research-only Rokot/Qwen adapter draft, strict ABC-to-MusicXML conversion tests, system-order/missing-system checks, and a separate development audit. No Rokot or Qwen inference has been run; model runtime CLI flags and real output handling still need verification.
- Audited all frozen development inputs: 12 generated controls and 20 open compositions, with per-input hash verification. All 12 controls pass strict croma round-trip. All 20 open references fail strict conversion on warnings; non-scoring diagnostic conversion yields exact-note F1 mean `0.97847`, minimum `0.78669`, so actual projection loss exists. Do **not** count diagnostic conversions as accepted predictions or waive strict failures. The audit covers ties (18), tuplets (16), independent voices (30), meter changes (2), and multi-page items (20). It does not yet validate VLM prediction joins.
- Saved separate immutable audit reports: [development-audit-v1.json](reports/phase2r/development-audit-v1.json), SHA-256 `FCB9F4AC8ACADE764CE6408AED218BEE02C8A1E1C75403F7D2BC539928056EA9`; [development-audit-v2.json](reports/phase2r/development-audit-v2.json), SHA-256 `39C1AADCE339CB036B3C1D8BBEBE1EDEC82D5C5B4598E73B61B632DB31A7BE17`. The Phase-1 freeze and four historical Phase-2 artifact hashes passed verification. Neither historical report was overwritten.

## Downloads deliberately left running

Working directory is the repository root. Payloads and logs are under ignored `Research/omr/.runtime/phase2r/`; command and resume details are in [job-record.md](reports/phase2r/job-record.md). At stop time, process check showed the following. Session IDs are `exec_command` IDs, not OS PIDs; check whether each is still running before launching another copy.

| Job | Session ID | OS PID at 16:11 UTC | State at stop |
| --- | ---: | ---: | --- |
| llama.cpp `b11124` Windows CUDA ZIP | `1697` | `gh` 13180 | Running; ZIP incomplete. Verify ZIP central directory and CLI version after completion. |
| Rokot Q8 model | `55760` | `hf` 10792 | Running; Q8 incomplete at 849,346,560 bytes. Its f16 projector is complete at 819,394,752 bytes, but still needs final hash check. |
| Audiveris 5.11.0 console MSI | `49364` | `gh` 5888 | Running; restarted after a partial sandboxed transfer. Expected complete size 85,062,430 bytes. |

Qwen's Q8 projector finished at 445,053,216 bytes; its text GGUF remains incomplete at 786,432,000 bytes. The previous Qwen download session was stopped before this user stop to diagnose network restrictions; **no Qwen downloader is currently expected to be running**. Rokot's previous sandboxed download failed with a chunked-encoding disconnect; the active `55760` session is an escalated resume. LEGATO `git clone` previously failed DNS, and its dedicated checkpoint remains unavailable locally. Do not assume any partial file is verified or runnable.

## Exact next actions after the user resumes

1. Check sessions `1697`, `55760`, `49364` with `write_stdin` or an OS process/file check **before** starting downloads; let them finish or diagnose their actual failure. Hash completed payloads against pinned expected hashes in `phase2r_identity.py`. Resume Qwen only once network status and other transfers are understood. Do not overwrite or delete partial files blindly.
2. Review and test the research adapters against the actual llama CLI, then run one annotated development crop and one complete development page for Rokot, followed by Qwen. Keep raw/native/MusicXML/canonical artifacts, typed failures, timings, and resource measurements separate from frozen evaluation artifacts. Verify part identity and inherited state in multi-system stitching rather than assuming concatenation is correct.
3. Verify actual LEGATO source/checkpoint access and Audiveris executable; run real development smokes if feasible. Investigate MuSViT decoder checkpoint feasibility. Record explicit unavailable or `requires training—not evaluated` status where prerequisites cannot be obtained within the approved resource/budget limits.
4. Reconcile the strict converter findings, run the complete relevant development and regression suites, update the active Phase-2 handoff and context pointer, and stop before Phase 3. Do not rerun or overwrite Phase-1/old Phase-2 evidence.

The current worktree contains pre-existing user changes and uncommitted Phase-1/2 research. Preserve them. There is no completed Phase-2R readiness claim yet.
