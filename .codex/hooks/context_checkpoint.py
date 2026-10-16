"""Project-scoped Codex checkpoint hooks; no model calls or external communication."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

REMINDER_FRACTION = 0.50
TAIL_BYTES = 262144
MAX_EVENT_BYTES = 1048576
NATIVE_THRESHOLD = 142120


@dataclass(frozen=True)
class Usage:
    timestamp: str
    tokens: int
    window: int


def normalized_path(path: Path) -> Path:
    resolved = path.resolve()
    if os.name != "nt":
        return resolved
    value = str(resolved)
    # Codex stores some Windows working directories with an extended-length prefix.
    if value.startswith("\\\\?\\UNC\\"):
        return Path("\\\\" + value[8:])
    if value.startswith("\\\\?\\"):
        return Path(value[4:])
    return resolved


def usage_from_record(record: dict[str, Any]) -> Usage | None:
    payload = record.get("payload", {})
    if not isinstance(payload, dict) or payload.get("type") != "token_count":
        return None
    info = payload.get("info")
    if not isinstance(info, dict):
        return None
    last = info.get("last_token_usage")
    if not isinstance(last, dict):
        return None
    tokens, window = last.get("total_tokens"), info.get("model_context_window")
    if type(tokens) is not int or type(window) is not int or tokens < 0 or window <= 0:
        return None
    timestamp = record.get("timestamp")
    if not isinstance(timestamp, str):
        return None
    return Usage(timestamp, tokens, window)


def recent_usage(transcript: str | None, session_id: str) -> Usage | None:
    if not transcript:
        return None
    path = Path(transcript)
    if session_id not in path.name or path.suffix != ".jsonl":
        return None
    try:
        with path.open("rb") as stream:
            stream.seek(0, os.SEEK_END)
            start = max(0, stream.tell() - TAIL_BYTES)
            stream.seek(start)
            lines = stream.read(TAIL_BYTES).decode("utf-8", errors="replace").splitlines()
        if start:
            lines = lines[1:]
    except OSError:
        return None
    for line in reversed(lines):
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict) and (usage := usage_from_record(record)):
            return usage
    return None


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Checkpoint state must be a JSON object")
    return data


def additional_context(event: str, context: str) -> dict[str, Any]:
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": context}}


def handoff_freshness(handoff: Path, usage: Usage | None) -> str:
    if not handoff.is_file():
        return "missing"
    if usage is None:
        return "unknown"
    try:
        recorded = datetime.fromisoformat(usage.timestamp.replace("Z", "+00:00"))
    except ValueError:
        return "unknown"
    if recorded.tzinfo is None:
        return "unknown"
    modified = datetime.fromtimestamp(handoff.stat().st_mtime, timezone.utc)
    return "possibly_stale" if modified < recorded else "newer_than_recorded_usage"


def kickoff_text(folder: Path, usage: Usage | None) -> str:
    handoff = folder / "HANDOFF.md"
    available = handoff.is_file()
    handoff_instruction = (
        f"Read the per-chat handoff at `{handoff.as_posix()}` and verify its task/turn\n"
        "identity against the latest user request; a saved handoff can be stale.\n"
        if available else
        "No agent-authored HANDOFF.md was available when this prompt was generated.\n"
        "Use the compacted conversation's current objective and explicitly recover\n"
        "any missing consequential state; do not invent completed work or authorization.\n"
    )
    if available and handoff_freshness(handoff, usage) == "possibly_stale":
        handoff_instruction += (
            "This handoff predates the latest recorded context activity. Reconcile\n"
            "later work from the compacted conversation and current evidence first.\n"
        )
    return (
        "# Continue after compaction\n\n"
        "Resume the same latest user-authorized task, including later steering.\n"
        + handoff_instruction
        + "Reuse already-loaded AGENTS.md/startup instructions. If unavailable, read\n"
        "AGENTS.md and only CONTEXT.md's startup section. Read MAIN_PLAN.md and its\n"
        "current phase handoff only if this task is research phase work. A plan's next\n"
        "phase is not permission to start it.\n\n"
        "Inspect relevant code/evidence for the next action. Check whether recorded\n"
        "processes are still running before starting another worker. Preserve frozen\n"
        "identities and existing acceptance criteria. Do not repeat completed work\n"
        "unless a changed identity, failed check or unresolved concern requires it.\n"
        "Continue within authorized scope; ask only for material missing information\n"
        "or authorization. Compaction does not resolve blockers or cancel the task.\n"
    )


def handle(event: dict[str, Any], root: Path) -> dict[str, Any]:
    root = normalized_path(root)
    cwd = event.get("cwd")
    if not isinstance(cwd, str) or not normalized_path(Path(cwd)).is_relative_to(root):
        return {}
    session_id = str(UUID(str(event.get("session_id", ""))))
    if event.get("agent_id"):
        return {}
    name = event.get("hook_event_name")
    if name not in {"PreToolUse", "PreCompact", "SessionStart"}:
        return {}
    if name == "SessionStart" and event.get("source") != "compact":
        return {}
    folder = root / ".codex" / "checkpoints" / session_id
    if not normalized_path(folder).is_relative_to(root):
        raise ValueError("Checkpoint directory must stay inside the project")
    state_path = folder / "state.json"
    state = load_state(state_path)
    usage = recent_usage(event.get("transcript_path"), session_id)
    if name == "PreToolUse":
        if not usage or usage.tokens < usage.window * REMINDER_FRACTION:
            return {}
        if state.get("reminded") or usage.timestamp <= state.get("before_compact_usage", ""):
            return {}
        state["reminded"] = True
        write_text(state_path, json.dumps(state, indent=2) + "\n")
        context = (
            f"Context checkpoint: latest recorded usage is {usage.tokens}/{usage.window} "
            f"tokens ({usage.tokens / usage.window:.1%}). Before another large read/job, "
            "finish a safe small operation, update only task-relevant documents whose "
            "facts changed, and save a concise per-chat handoff at "
            f"{(folder / 'HANDOFF.md').as_posix()}. Include session/turn ID, current "
            "authorized objective, changed files, actual verification results, unresolved "
            "issues, live job IDs/logs/input identities and the exact next action. "
            "Refresh it after subsequent material changes up to compaction. "
            "Keep scope intact; no automatic next phase or completion claims. "
            "KICKOFF.md and COMPACTION_PROMPT.md are generated before native compaction."
        )
        if NATIVE_THRESHOLD != usage.window * 55 // 100:
            context += (
                f" The native trigger is {NATIVE_THRESHOLD} tokens, not 55% of this "
                "model's reported window. Report that mismatch; do not change settings silently."
            )
        return additional_context(name, context)
    if name == "PreCompact":
        write_text(folder / "KICKOFF.md", kickoff_text(folder, usage))
        prompt = (root / ".codex" / "COMPACTION_PROMPT.md").read_text(encoding="utf-8")
        write_text(folder / "COMPACTION_PROMPT.md", prompt +
                   f"\nPer-chat handoff: `{(folder / 'HANDOFF.md').as_posix()}`.\n"
                   f"Continuation prompt: `{(folder / 'KICKOFF.md').as_posix()}`.\n")
        metadata = {
            "session_id": session_id, "turn_id": event.get("turn_id"),
            "model": event.get("model"), "trigger": event.get("trigger"),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "usage": asdict(usage) if usage else None,
            "agent_handoff_present": (folder / "HANDOFF.md").is_file(),
            "handoff_freshness": handoff_freshness(folder / "HANDOFF.md", usage),
            "note": "Mechanical checkpoint; presence does not prove the handoff is current.",
        }
        write_text(folder / "checkpoint.json", json.dumps(metadata, indent=2) + "\n")
        if usage:
            state["before_compact_usage"] = usage.timestamp
        state["reminded"] = False
        write_text(state_path, json.dumps(state, indent=2) + "\n")
        return {}
    write_text(folder / "KICKOFF.md", kickoff_text(folder, usage))
    state["reminded"] = False
    write_text(state_path, json.dumps(state, indent=2) + "\n")
    return additional_context(name, (folder / "KICKOFF.md").read_text(encoding="utf-8"))


def main() -> None:
    try:
        raw = sys.stdin.buffer.read(MAX_EVENT_BYTES + 1)
        if len(raw) > MAX_EVENT_BYTES:
            raise ValueError("Hook input exceeds the supported size")
        event = json.loads(raw)
        if not isinstance(event, dict):
            raise ValueError("Hook input must be a JSON object")
        result = handle(event, Path(__file__).resolve().parents[2])
    except (OSError, ValueError, TypeError) as error:
        result = {"systemMessage": f"Context checkpoint unavailable: {type(error).__name__}. "
                  "Native compaction is not blocked; preserve task state in the summary."}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
