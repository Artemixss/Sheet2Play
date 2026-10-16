# Context checkpoints in Codex

This is a Sheet2Play-local workflow, configured in [.codex/config.toml](../.codex/config.toml)
and [.codex/hooks.json](../.codex/hooks.json). It uses Codex's native compaction, not another
model call or a recurring monitoring job.

## Threshold and tradeoffs

The current desktop chat reports a 258,400-token window. The native trigger is 142,120
tokens, approximately 55% of that reported window, with `total` accounting. A local tool
hook is configured to remind the agent to save state near 50%, retaining a five-percentage-point
buffer before compaction. The user selected these thresholds on 2026-10-05.

These are preferences, not proven optimums. There is no established universal 50% accuracy
or cost rule in the official guidance consulted. Compaction itself consumes work, may lose
detail and can change caching. A turn or large tool response can overshoot a trigger;
this configuration does not impose a hard 55% cap.

Codex's threshold is an absolute token count. Recalibrate it if the reported context window
changes; do not pretend it follows every model. The hook warns when its observed window
differs. It reads recent token-count records from the hook-provided transcript, not lifetime
cumulative usage. That transcript format is not a stable interface: unavailable telemetry
means no percentage reminder, while native compaction remains configured.

## What happens

1. Near 50%, one reminder per compaction window asks the agent to update changed facts in
   the active plan/handoff/job record, and relevant startup pointers only if their state changed.
   It asks for `.codex/checkpoints/<session-id>/HANDOFF.md` with the current task and next action.
   Keep that handoff current after subsequent material changes until compaction. The buffer
   is headroom for saving/checking state, not a period during which stale documents are accepted.
2. Before native compaction, the hook generates per-chat **KICKOFF.md**, **COMPACTION_PROMPT.md**
   and **checkpoint.json**, retaining any agent-authored handoff. The native prompt template
   is [.codex/COMPACTION_PROMPT.md](../.codex/COMPACTION_PROMPT.md).
3. After compaction, a `SessionStart` hook matching `compact` adds the kickoff instructions to
   the immediate continuation. The agent resumes the same authorized task and checks live jobs.

Semantic document updates are agent work; the script does not rewrite plans or infer success.
The early reminder is best effort, especially if one response crosses both thresholds.
A missing or stale handoff must be recovered from the compacted conversation and evidence.
The mechanical checkpoint records whether the handoff predates the latest observed usage;
that is a conservative freshness warning, not proof of semantic completeness or staleness.
Never rewrite all Markdown files, alter frozen artifacts, or mark a phase complete just to compact.

Each chat has its own directory to avoid conflicting resumptions. These directories are ignored
by Git and routine ripgrep searches. They stay local and are not sent to another service.

## Project-wide activation

Every local chat whose working directory is this Sheet2Play checkout or a subdirectory
shares [.codex/config.toml](../.codex/config.toml) and [.codex/hooks.json](../.codex/hooks.json).
The configuration explicitly enables lifecycle hooks. Each chat still keeps a separate
handoff and checkpoint directory. Windows extended-length working-directory paths
(`\\?\C:\...`) are normalized before the project scope check.

The project is trusted and all three hook definitions have saved trust records, verified
on 2026-10-03. New or changed hook definitions still require review and trust using `/hooks`
in a supported client; changing the script does not create a new hook definition. No model,
effort, approval policy or sandbox setting is changed.

Existing loaded chats retain their configuration snapshot. Editing the project file or
trusting a hook does not prove that an already-running chat reloaded it. After a configuration
change, finish current turns and restart Codex once, then reopen the existing Sheet2Play
chats. This loads the shared project settings without creating replacement chats. New chats
started in this folder also inherit the settings. Other projects' configuration is unchanged.

The 2026-10-03 automatic test exposed this distinction: this already-loaded chat used
`auto_compact_scope_limit=Some(244800)` (about 95%) even though the saved file specified
129,200. A fresh desktop-bundled Codex 0.160.0 `config/read` resolved the trusted project layer
and returned 129,200 with `total` accounting and the configured compaction prompt. The
checkpoint files had not refreshed automatically. Fresh configuration resolution verifies
the saved settings, not activation in an older loaded chat.

On 2026-10-03, after the Windows path fix and explicit feature setting, fresh `config/read` checks for both
ordinary and extended-length project paths returned 129,200, `total`, and `hooks = true`.
Read-only `hooks/list` returned all three handlers enabled and trusted, with no warnings or
errors. The 15 isolated fixture checks passed. No live hook was invoked for this verification;
an automatic run after the desktop reload remained the activation test.

On 2026-10-04, runtime logs confirmed the loaded 129,200-token threshold and automatic
threshold crossings in the Phase 2 chat. The reported hook history showed all 51 runs
failed, including `PreToolUse`, `PreCompact` and `SessionStart`; the shared Windows command
also failed PowerShell parsing, although actual hook stderr was unavailable. Native
compaction works independently of these scripts. The 2026-10-05 threshold change to
142,120 does not repair or establish successful checkpoint preparation/restoration.

On this PC the desktop's bundled Codex is 0.160.0, while the `codex` command found on
PATH is 0.146.0. If the desktop does not expose hook review, use its bundled client
from PowerShell in the project folder, then enter `/hooks`:

```powershell
& 'C:\Users\bur4x\AppData\Local\OpenAI\Codex\bin\8aaf1547b825b104\codex.exe'
```

The bundle path can change after an app update. This command is for interactive hook
review; it does not run the implementation plan. Exit after review with `/quit`.

For an explicitly requested immediate manual checkpoint, ask the agent to save its handoff,
run `/compact`, then say
`Continue the same task from the saved handoff; preserve its authorization boundary.`
The manual fallback works even when hooks are not yet trusted.

## Verification and removal

Run `python -B .codex/hooks/test_context_checkpoint.py` for isolated behavior checks.
After reloading, check that the chat's runtime reports
`auto_compact_scope_limit=Some(142120)` with `Total` accounting. Let an automatic compaction
occur and verify it produces checkpoint files with `trigger: auto` and that the next turn
receives the SessionStart continuation context. A `prepared-not-compacted` record is not
evidence of an automatic hook run. Configuration parsing, a fresh `config/read`, and isolated
fixtures alone do not establish activation in every existing desktop chat. Do not invoke
live hooks manually to claim that an automatic activation test passed.

To revert, remove the three project compaction settings and disable/remove the three
checkpoint hook entries. Keep useful handoffs. Do not delete unrelated project settings.

Official sources: [Configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference),
[hooks and trust](https://learn.chatgpt.com/docs/hooks),
[compaction](https://developers.openai.com/api/docs/guides/compaction).
