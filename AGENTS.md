# Sheet2Play

Each tool's own user-level instructions (for Codex, `~/.codex/AGENTS.md`) also apply. This
file covers only what is specific to this repository.

## Read before working

- Start with the short startup section of [CONTEXT.md](CONTEXT.md), ending at
  `<!-- STARTUP_CONTEXT_END -->`. Follow its links for the requested task; do not read
  the entire historical context or every Markdown file for routine orientation. Reuse
  already-loaded context unless it changed or was compacted away.
- [plans/README.md](plans/README.md) indexes every plan. For research or integration
  work, read [MAIN_PLAN.md](plans/MAIN_PLAN.md) and the handoff it links. "Implement
  Phase N" means that plan unless the user names another. Phase status and the next
  action live there; other entry points link to it rather than restating it.
- The user's latest explicit decision governs scope. The plan sets objectives and
  acceptance criteria; handoffs record implementation state, evidence and deviations,
  and supplement the plan rather than replacing it. Resolve a material conflict between
  documents before dependent work instead of silently choosing one. Inspect the
  relevant code rather than trusting a document's description of it.
- Archived plans, dated handoffs and historical CONTEXT sections are evidence, not work
  orders. Their frozen manifests, scoring protocols and evaluation identities remain the
  contract for any rerun: see the [Phase 1 handoff](Research/omr/PHASE1_HANDOFF.md) for
  the evaluation freeze and the [screening handoff](Research/omr/SCREENING_HANDOFF.md) for
  the screening manifests and RAM admission policy. A request to execute one stage
  authorizes that stage, not the confirmation run, training or promotion after it.
- Windows commit exhaustion has crashed this machine repeatedly with no verified cause or
  durable remedy, so the [enforced CPU safeguards](Research/omr/reports/zeus-attribution/phase2/safety-fix-20261004/REPORT.md)
  are mandatory for substantive jobs: the recorded supervisor, one heavy worker, 85%
  RAM/commit stops, a 4 GiB system commit reserve, worker containment and deadlines.
  Since 2026-10-17, at the user's request, workers have no per-worker memory cap by
  default (`--worker-limit-mib` sets one when wanted); the system stops still apply.
  GPU admission is separate. Inspect live jobs and locks before launching, preserve failed receipts, and
  never automatically retry a pressure failure or invoke Git during crash recovery.
- Keep shared repository rules here. [CLAUDE.md](CLAUDE.md) points here instead of
  maintaining a second copy. Update the active-work links when completing a phase.

## Plan lifecycle

- Store project execution plans in `plans/`, indexed by [plans/README.md](plans/README.md).
  Keep the current research plan at `plans/MAIN_PLAN.md`, with a descriptive
  workstream, stable plan ID, phase status, evidence links and next planned step.
  Completing one phase does not complete the whole plan or authorize the next phase.
- On whole-plan completion, move its full text to `plans/archive/<plan-id>.done.md`
  and update the index, startup links and linked handoffs. Use `.superseded.md`
  or `.cancelled.md` for those outcomes; do not label unfinished work done.
  Keep a concise status/redirect at old locations needed by historical links.
  Preserve handoffs, experimental evidence and frozen artifacts.
- Keep handoffs beside their evidence and link them from the plan index. Each
  handoff must state its owning plan, completed/interrupted/superseded phase
  status, acceptance evidence and next authorized action. Update its lifecycle
  note when later work supersedes a recorded stop; retain the dated history.
- After archiving, keep `plans/MAIN_PLAN.md` as a short "No active plan" pointer
  to the closed record until the user selects a new plan. Never overwrite an
  unarchived plan or delete evidence merely to reduce documentation clutter.
  Older plans are reference material, not work orders; load them only when relevant.

## Efficient execution without weaker validation

- **Codex only:** near a compaction boundary, or when asked to prepare one, follow the
  [context checkpoint workflow](docs/agent-checkpoints.md) and keep the per-chat
  HANDOFF.md current with the authorized objective, evidence, live jobs and exact next
  action. Claude Code sessions do not use this workflow. In any tool, a context reset
  does not authorize another phase or justify repeating completed work.
- For project exploration, inspect the root layout, dependency/build manifests, entry
  points, and relevant tests first. Report architecture, how the user runs it, current
  work, and concrete unknowns. Explore subsystems only to answer the request.
- Before implementation, state the phase boundary, required evidence, and a short task
  breakdown. Resolve recorded readiness gaps before dependent evaluation. Do not expand
  into another phase or start training/promotion merely because a prerequisite is missing.
- For multi-phase work, keep one evidence-grounded plan with each phase's objective,
  deliverables, acceptance evidence, unverified assumptions, and review/replanning triggers.
  Recommend an available model/effort at meaningful boundaries when useful, with a brief
  task-based reason. Use supplied options without researching the model catalog.
- Prefer standard effort for well-defined work with reliable checks; recommend stronger
  reasoning for unresolved architecture, diagnosis, statistics, or consequential decisions.
  Justify the highest effort by specific reasoning needs and parallel execution by useful
  independent tasks. A separate planning agent is optional. Keep the user's selected
  settings until they request a change; continue authorized work as checks pass, reviewing
  consequential milestones and resolving material uncertainty before dependent work.
- Prefer filename/symbol discovery (`rg --files`, `rg -l`, scoped `rg -n`) followed by
  relevant sections/functions. Limit code searches by file type and directory. Query
  selected JSON fields; do not dump full manifests, prediction arrays, or entire report trees.
- Target roughly 2,000-4,000 output tokens for routine tool results. Increase the budget
  for a specific needed artifact, not as a substitute for filtering. A truncated result
  requires a narrower follow-up; never treat omitted text as reviewed.
- Batch independent reads/checks, but summarize their outputs before returning them to
  context. Keep edits and dependent checks sequential. Retain full diagnostic logs on disk
  when running jobs; expose summaries and relevant failure excerpts to the model.
- Preflight the interpreter, candidate runtime/weights, paths, required permissions/network,
  and available resources before expensive execution. After a failure, identify its cause
  before retrying. Do not repeat unchanged commands that already proved the same failure.
- Validate in stages: contract/unit fixtures, one representative development item, then
  the complete relevant development/regression suite. Run the release gate for shipped
  changes when ready. After passing checks, repeat only for subsequent relevant changes,
  failures, or an explicit unresolved concern. Never drop required coverage to save tokens.
- For long jobs, prefer completion/change notifications when available. If polling is
  necessary, use bounded waits appropriate to runtime (up to 60 seconds per blocking wait),
  work on independent tasks between checks, and inspect only new progress or failure output.
  Avoid repeated empty 30-second polls and model turns whose sole decision is "wait again".
  Do not create recurring monitoring automations without a user request.
- Before a long job, record its command, working directory, configuration/input identity,
  log location, and resumable progress in the active handoff or job record. On interruption,
  add the process/session identifier, completed work, remaining work, last validation, and
  exact next action. On resume, check whether it is still running before launching another
  copy. Reuse cached results only when input/code/configuration identities still match.
- Keep one focused implementation task per phase when organizing new work; do not create
  tasks without a user request or restart an existing task just for a small follow-up.
  Do not change model/effort settings, delegate, weaken safeguards, or reduce acceptance
  criteria solely to meet a token target. Optimize retrieval and orchestration first.
- When auditing efficiency, separate cached input, uncached input, output, and reasoning
  (already included in output). Count empty polls, truncations, and retries alongside quality
  outcomes. Raw cumulative tokens are not a subscription-quota or monetary-cost estimate.

## Routine documentation searches

Use `rg --files -g '*.md'` to list project documentation and `rg -n -g '*.md' PATTERN`
to search it. The root `.rgignore` excludes downloaded datasets, vendored dependencies,
virtual environments, model payloads, build output, caches, and piano samples from normal
ripgrep discovery. Do not use `--no-ignore` for routine repository searches. When upstream
documentation is needed, search its explicit directory with `rg --no-ignore` and a narrow
pattern. Search exclusions do not delete files, change Git tracking, or remove licenses.

## What the user runs

`dist\Sheet2Play.exe`, launched from the Desktop and Start Menu shortcuts that
`scripts/install-shortcut.ps1` creates. Do not use `dotnet run` as proof that a change reached
the installed app; it remains valid for isolated development and diagnostic tools.
A user-facing runtime change is not finished when
it builds and the tests pass — until the app is republished the user is still launching the
previous binary and will report the new feature as missing.

For changes to shipped code or runtime assets, use the release skill and run:

```
powershell -ExecutionPolicy Bypass -File scripts\verify-release.ps1
```

The running app holds a lock on `dist\Sheet2Play.exe`, so it must be closed before
publishing. The gate stops the app and relaunches the published executable. Persisted
library/settings live in `%LOCALAPPDATA%\Sheet2Play` (or the configured library location).
Documentation-only changes require link/search checks, not an app shutdown or republish.
Research-only changes require relevant research tests; publish if shipped behavior also changes.

## Layout

- `Visualization_engine/` — the C# frontend (`SynthesiaClone.csproj`, assembly
  `Sheet2Play`). Raylib + DryWetMidi, net9.0-windows.
- `Visualization_engine.Tests/` — xunit suite. `dotnet test`.
- `Bridge/` — the Python OMR bridge. `bridge.py` is the entry point the frontend shells
  out to; it imports `musicxml_normalizer` and `progress_protocol` as siblings.
- `Omr/`, `Research/` — OMR experiments and notes.
- `pianos/` — large sample payloads. Not shipped with the app; exclude from recursive
  greps, they make repo-wide searches time out.

The frontend source is recovered decompiler output, so it carries no original comments.
Write new comments in the style of the surrounding hand-written files, not the decompiled
ones.

## Runtime assets

These load from disk relative to `AppContext.BaseDirectory` and are invisible to the
compiler, so a build can succeed while the published app degrades or fails:

- `assets/fonts/Inter-Regular.ttf` and `Inter-SemiBold.ttf` — `UiDesign.cs`. Missing
  fonts silently fall back to Raylib's default; the app still runs and looks wrong.
- `Bridge/bridge.py` plus its sibling imports — `OmrPipeline.cs`.

Preserve the csproj's asset `ExcludeFromSingleFile` and the bridge's output/publish copy
rules. They differ: do not assume every runtime dependency needs the same metadata.
The release asset checks verify the actual published layout.

## OMR engine

- Experimental OMR changes stay opt-in and leave the shipped engine's behaviour untouched
  until they are measured.
- Use controlled experiments to distinguish recognition, representation, conversion, and
  integration defects. The approved plan authorizes candidate comparison alongside in-place
  investigation; it does not authorize replacing the shipped engine automatically.
- Transcoda was removed permanently and must never be restored, even to fix a broken
  import.

## Audio

The `audioOffsetSeconds` default in `Playback.cs` was calibrated by ear against a real
output chain. Do not replace it with a guessed or "more correct" value.

## ML / Model Selection

Applies to the OMR fine-tuning and dataset work under `Omr/` and `Research/`.

- Use the plan's composition-macro pitch/onset/duration F1, failure policy, paired statistics,
  and promotion gate for OMR comparison. Historical aggregates are not eligible rankings.
- For duration classification, report the full confusion matrix, majority baseline,
  balanced accuracy, and macro-F1; reject degenerate single-class predictors. These diagnostics
  complement the transcription metrics rather than substituting for them.
- Keep Phase-1 manifests and scoring rules frozen. Debug adapters and select inference
  settings on development data only; Phase 2 does not run frozen evaluation inference.
- Use the local 6 GB GPU first for comparison without competing with separate training.
  The existing HOMR fine-tune is outside this comparison; do not restart or alter it.
  Cloud cost for the comparison is capped at $10 total including storage and transfer;
  estimate first and stop before exceeding it. Keep private library files local.
- Keep the project's own dataset generator in any training plan, even when a public corpus
  covers the same ground.

## Conventions

- User-adjustable settings need a visible on-screen control, not just a keyboard shortcut.
- Do not add AI `Co-Authored-By` trailers to commits in this repository.

