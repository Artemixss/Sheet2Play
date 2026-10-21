# Sheet2Play

A Windows C#/Raylib desktop app (`dist\Sheet2Play.exe`) that turns sheet music into falling
piano notes played through a sampled piano (Salamander SFZ by default, YDP SoundFont as the
alternative). A Python bridge (`Bridge/`) runs optical music recognition: HOMR 480 by default,
HOMR 465 as the secondary; 426 and Zeus remain in the backend only, for songs already cached
with them. Each conversion is kept as a song package (its MusicXML plus a derived
performance), which the app turns into notes at playback. `Research/omr/` is separate
research tooling.

This file is the shared rulebook for Claude and Codex: Codex reads it directly and
[CLAUDE.md](CLAUDE.md) imports it. Keep repository rules here, not in a second copy. Each
tool's own user-level instructions (for Codex, `~/.codex/AGENTS.md`) also apply.

## Where to look

| Task | Read |
| --- | --- |
| Which plans exist and their status | [plans/README.md](plans/README.md) |
| Current research work, or "implement Phase N" | [plans/MAIN_PLAN.md](plans/MAIN_PLAN.md) and the handoff it links, unless the user names another plan from the index |
| How the app fits together, and known traps | [CONTEXT.md](CONTEXT.md), only the section you need |
| Change frontend or bridge behaviour | [CONTEXT.md traps](CONTEXT.md#3-things-that-will-bite-you) and [verification](CONTEXT.md#4-verification), plus the affected code and tests |
| Song packages, the timeline, expression, pianos | The [MusicXML songs plan](plans/2026-10-19-musicxml-songs.md) and its [handoff](Research/omr/reports/musicxml-songs/handoff.md) |
| The HOMR 480 and 465 runtimes, and what editing a pinned Bridge file costs | [Bridge/HOMR465.md](Bridge/HOMR465.md) |
| Rerun or check a frozen evaluation | [Phase 1 handoff](Research/omr/PHASE1_HANDOFF.md) and [frozen scoring protocol](Research/omr/reports/phase1/scoring-protocol.json) |
| Completed or old work | The [archived plans table](plans/README.md#archived-plans), then only the relevant handoff or [FINDINGS](Research/omr/reports/diagnosis/FINDINGS.md) |
| Upstream HOMR changes | The [latest upstream audit](Research/omr/reports/diagnosis/UPSTREAM_AUDIT_2026-10-17.md); older audits sit beside it |
| Using, building or installing the app | [README.md](README.md) |

Read only what the task needs. Do not open every Markdown file to get oriented, and reuse
context you already loaded unless it changed or was compacted away.

## Scope and authority

- The user's latest explicit decision governs scope. The plan sets objectives and acceptance
  criteria; handoffs record implementation state, evidence and deviations, and supplement the
  plan rather than replacing it. Resolve a material conflict between documents before
  dependent work instead of silently choosing one. Inspect the relevant code rather than
  trusting a document's description of it.
- "Implement Phase N" means MAIN_PLAN.md unless the user names another plan. Phase status
  and the next action live there and in its handoff. Completing one phase does not authorize
  the next, and a request to execute one stage authorizes that stage, not the confirmation
  run, training or promotion after it.
- Archived plans, older handoffs and dated reports are evidence, not work orders, whether or
  not they say so. Their frozen manifests, scoring protocols and evaluation identities remain
  the contract for any rerun: see the [Phase 1 handoff](Research/omr/PHASE1_HANDOFF.md) for
  the evaluation freeze and the [screening handoff](Research/omr/SCREENING_HANDOFF.md) for
  the screening manifests and RAM admission policy.
- Windows commit exhaustion has crashed this machine repeatedly with no verified cause or
  durable remedy, so the [enforced CPU safeguards](Research/omr/reports/zeus-attribution/phase2/safety-fix-20261004/REPORT.md)
  are mandatory for substantive jobs: the recorded supervisor, one heavy worker, 85%
  RAM/commit stops, a 4 GiB system commit reserve, worker containment and deadlines.
  Since 2026-10-17, at the user's request, workers have no per-worker memory cap by
  default (`--worker-limit-mib` sets one when wanted); the system stops still apply.
  GPU admission is separate. Inspect live jobs and locks before launching, preserve failed
  receipts, and never automatically retry a pressure failure or invoke Git during crash recovery.

## Plan lifecycle

- Store project execution plans in `plans/`, indexed by [plans/README.md](plans/README.md).
  Keep the current research plan at `plans/MAIN_PLAN.md`, with a descriptive workstream,
  stable plan ID, phase status, evidence links and next planned step.
- On whole-plan completion, move its full text to `plans/archive/<plan-id>.done.md` and
  update the index, the "Where to look" table above and linked handoffs. Use
  `.superseded.md` or `.cancelled.md` for those outcomes; do not label unfinished work done.
  When a file moves, update the links that point to it rather than leaving a redirect stub.
  Preserve handoffs, experimental evidence and frozen artifacts.
- Keep handoffs beside their evidence and link them from the plan index. Each handoff states
  its owning plan, phase status, acceptance evidence and next authorized action. Do not add
  lifecycle banners or "does not authorize" disclaimers to older records; the evidence rule
  above already covers them.
- After archiving, keep `plans/MAIN_PLAN.md` as a short "No active plan" pointer to the
  closed record until the user selects a new plan. Never overwrite an unarchived plan or
  delete evidence merely to reduce documentation clutter.

## Execution

- **Codex only:** near a compaction boundary, or when asked to prepare one, follow the
  [context checkpoint workflow](docs/agent-checkpoints.md) and keep the per-chat HANDOFF.md
  current. Claude Code sessions do not use it. In either tool, a context reset does not
  authorize another phase or justify repeating completed work.
- Before implementing, state the phase boundary, the evidence it needs and a short task
  list. Do not expand into another phase, or start training or promotion, because a
  prerequisite is missing. Keep the user's model and effort settings until they change
  them, and do not create tasks, sessions or delegates without a user request.
- Preflight the interpreter, runtime and weights, paths, permissions or network, and free
  resources before expensive runs. After a failure, find the cause before retrying; never
  repeat an unchanged command that already failed the same way.
- Validate in stages: unit fixtures, one development item, then the full relevant suite,
  and the release gate for shipped changes. Never drop required coverage, weaken safeguards
  or lower acceptance criteria to save tokens.
- Before a long job, record its command, working directory, input and configuration
  identity, log path and resumable progress in the active handoff or job record. On
  interruption, add the process id, what finished, what remains and the exact next action.
  On resume, check whether it is still running before launching another copy, and reuse
  cached results only when input, code and configuration identities still match.
- Wait on long jobs with completion notifications where available, otherwise with bounded
  waits of up to 60 seconds while doing independent work. Do not create recurring
  monitoring automations without a user request.
- Keep routine tool output to roughly 2,000-4,000 tokens. Query selected JSON fields instead
  of dumping manifests, prediction arrays or report trees, keep full logs on disk and read
  their summaries and failure excerpts. A truncated result needs a narrower follow-up; never
  treat omitted text as reviewed.

## Searching

- Never search from a drive or filesystem root: no `find /`, `find /c`, `dir /s C:\`,
  `Get-ChildItem C:\ -Recurse` or `rg PATTERN C:\`, and nothing equally broad such as the
  whole user profile. A root-wide `find` once ran for three hours and used about 10 GB of
  memory. Search inside this repository, or name the specific install folder you need (for
  HOMR: `Bridge/.venv-homr-gpu` or `Research/omr/vendor/homr`).
- If a command times out, check for leftover processes it started (`find`, `rg`, `python`,
  `powershell`) and stop them before continuing. This cleanup never covers the research
  supervisor or workers recorded in `.research-worker.lock`, or the running app.
- Prefer filename and symbol discovery (`rg --files`, `rg -l`, scoped `rg -n`), limited by
  file type and directory, then read the relevant sections.

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

## Runtime assets

These load from disk relative to `AppContext.BaseDirectory` and are invisible to the
compiler, so a build can succeed while the published app degrades or fails:

- `assets/fonts/Inter-Regular.ttf` and `Inter-SemiBold.ttf` — `UiDesign.cs`. Missing
  fonts silently fall back to Raylib's default; the app still runs and looks wrong.
- `Bridge/bridge.py` plus its sibling imports, and the unpinned `song_entry.py`,
  `song_model.py` and `timing_correction.py` beside it — `OmrPipeline.cs` and
  `SongPerformance.cs`.

The pianos are not in `dist\`: `scripts\install-piano.ps1` (Salamander) and
`scripts\install-soundfont.ps1` (YDP) install them under `%LOCALAPPDATA%\Sheet2Play`,
because every publish wipes `dist\`. With neither installed the app plays silently and says so.

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
- Keep frozen manifests and scoring rules frozen. Tune and debug on development data only.
- Keep private library files local. Spend on cloud compute only when the active plan allows it.
- Keep the project's own dataset generator in any training plan, even when a public corpus
  covers the same ground.

## Conventions

- User-adjustable settings need a visible on-screen control, not just a keyboard shortcut.
- The frontend source is recovered decompiler output with no original comments. Write new
  comments in the style of the surrounding hand-written files, not the decompiled ones.
- Do not add AI `Co-Authored-By` trailers to commits in this repository.
