"""Isolated behavioral checks for checkpoint hooks; no live chats or model calls."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from context_checkpoint import TAIL_BYTES, handle, recent_usage, usage_from_record


class CheckpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="codex-checkpoint-test-")
        self.root = Path(self.temporary.name) / "project"
        self.root.mkdir()
        self.session = str(uuid4())
        self.transcript = Path(self.temporary.name) / f"rollout-{self.session}.jsonl"
        self.transcript.write_text("", encoding="utf-8")
        self.folder = self.root / ".codex" / "checkpoints" / self.session
        prompt = self.root / ".codex" / "COMPACTION_PROMPT.md"
        prompt.parent.mkdir()
        prompt.write_text("Preserve the current authorized task.\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def append_usage(self, tokens: int, timestamp: str = "2026-10-03T12:00:00Z") -> None:
        record = {
            "timestamp": timestamp, "type": "event_msg",
            "payload": {"type": "token_count", "info": {
                "model_context_window": 258400,
                "last_token_usage": {"total_tokens": tokens},
                "total_token_usage": {"total_tokens": 999999999},
            }},
        }
        with self.transcript.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record) + "\n")

    def event(self, name: str, **extra: object) -> dict[str, object]:
        return {"hook_event_name": name, "session_id": self.session,
                "cwd": str(self.root), "transcript_path": str(self.transcript),
                "model": "gpt-6.1-sol", "turn_id": "test-turn", **extra}

    def test_low_context_does_not_create_checkpoint_or_use_cumulative_tokens(self) -> None:
        self.append_usage(10000)
        self.assertEqual(handle(self.event("PreToolUse"), self.root), {})
        self.assertFalse(self.folder.exists())

    def test_reminder_is_once_per_window_at_the_boundary(self) -> None:
        self.append_usage(129199)
        self.assertEqual(handle(self.event("PreToolUse"), self.root), {})
        self.assertFalse(self.folder.exists())
        self.append_usage(129200)
        result = handle(self.event("PreToolUse"), self.root)
        self.assertEqual(result["hookSpecificOutput"]["hookEventName"], "PreToolUse")
        self.assertTrue(result["hookSpecificOutput"]["additionalContext"])
        self.assertIn("50.0%", result["hookSpecificOutput"]["additionalContext"])
        self.assertNotIn("not 55%", result["hookSpecificOutput"]["additionalContext"])
        self.assertEqual(handle(self.event("PreToolUse"), self.root), {})

    def test_compaction_preserves_semantic_handoff_and_records_unknown_usage(self) -> None:
        self.folder.mkdir(parents=True)
        handoff = self.folder / "HANDOFF.md"
        original = "Authorized task: repair a setting; do not start Phase 2.\n"
        handoff.write_text(original, encoding="utf-8")
        self.assertEqual(handle(self.event("PreCompact", trigger="auto"), self.root), {})
        self.assertEqual(handoff.read_text(encoding="utf-8"), original)
        metadata = json.loads((self.folder / "checkpoint.json").read_text(encoding="utf-8"))
        self.assertIsNone(metadata["usage"])
        self.assertTrue(metadata["agent_handoff_present"])
        self.assertEqual(metadata["trigger"], "auto")
        self.assertTrue((self.folder / "KICKOFF.md").is_file())
        self.assertTrue((self.folder / "COMPACTION_PROMPT.md").is_file())

    def test_compact_session_injects_saved_kickoff(self) -> None:
        handle(self.event("PreCompact", trigger="manual"), self.root)
        result = handle(self.event("SessionStart", source="compact"), self.root)
        self.assertEqual(result["hookSpecificOutput"]["hookEventName"], "SessionStart")
        self.assertEqual(result["hookSpecificOutput"]["additionalContext"],
                         (self.folder / "KICKOFF.md").read_text(encoding="utf-8"))
        self.assertFalse(json.loads((self.folder / "checkpoint.json").read_text())["agent_handoff_present"])

    def test_old_usage_does_not_repeat_reminder_after_compaction(self) -> None:
        self.append_usage(129300)
        handle(self.event("PreToolUse"), self.root)
        handle(self.event("PreCompact", trigger="auto"), self.root)
        handle(self.event("SessionStart", source="compact"), self.root)
        self.assertEqual(handle(self.event("PreToolUse"), self.root), {})
        self.append_usage(130000, "2026-10-03T12:01:00Z")
        self.assertIn("hookSpecificOutput", handle(self.event("PreToolUse"), self.root))

    def test_missing_telemetry_still_allows_checkpoint_and_continuation(self) -> None:
        event = self.event("PreCompact", trigger="auto")
        event["transcript_path"] = str(self.transcript.with_name(f"missing-{self.session}.jsonl"))
        handle(event, self.root)
        event.update(hook_event_name="SessionStart", source="compact")
        self.assertIn("hookSpecificOutput", handle(event, self.root))

    def test_old_handoff_is_flagged_and_preserved(self) -> None:
        self.folder.mkdir(parents=True)
        handoff = self.folder / "HANDOFF.md"
        original = "Earlier checkpoint; later edits may be absent.\n"
        handoff.write_text(original, encoding="utf-8")
        os.utime(handoff, (1, 1))
        self.append_usage(129300)
        handle(self.event("PreCompact", trigger="auto"), self.root)
        metadata = json.loads((self.folder / "checkpoint.json").read_text(encoding="utf-8"))
        self.assertEqual(metadata["handoff_freshness"], "possibly_stale")
        self.assertEqual(handoff.read_text(encoding="utf-8"), original)

    def test_missing_handoff_is_explicit_and_not_fabricated(self) -> None:
        self.append_usage(129300)
        handle(self.event("PreCompact", trigger="auto"), self.root)
        metadata = json.loads((self.folder / "checkpoint.json").read_text(encoding="utf-8"))
        self.assertEqual(metadata["handoff_freshness"], "missing")
        self.assertFalse((self.folder / "HANDOFF.md").exists())

    def test_other_folders_subagents_and_startup_do_not_touch_state(self) -> None:
        self.append_usage(140000)
        outside = self.event("PreToolUse")
        outside["cwd"] = str(self.root.parent)
        self.assertEqual(handle(outside, self.root), {})
        self.assertEqual(handle(self.event("PreToolUse", agent_id="child"), self.root), {})
        self.assertEqual(handle(self.event("SessionStart", source="startup"), self.root), {})
        self.assertFalse(self.folder.exists())

    def test_invalid_session_id_cannot_escape_checkpoint_directory(self) -> None:
        event = self.event("PreCompact")
        event["session_id"] = "../../elsewhere"
        with self.assertRaises(ValueError):
            handle(event, self.root)
        self.assertFalse(self.folder.exists())

    @unittest.skipUnless(os.name == "nt", "Windows working-directory alias")
    def test_extended_windows_cwd_receives_reminder(self) -> None:
        self.append_usage(130000)
        event = self.event("PreToolUse")
        event["cwd"] = "\\\\?\\" + str(self.root)
        result = handle(event, self.root)
        self.assertIn("hookSpecificOutput", result)
        self.assertTrue((self.folder / "state.json").is_file())

    @unittest.skipUnless(os.name == "nt", "Windows project-root alias")
    def test_extended_windows_root_writes_to_same_project(self) -> None:
        self.append_usage(130000)
        result = handle(self.event("PreToolUse"), Path("\\\\?\\" + str(self.root)))
        self.assertIn("hookSpecificOutput", result)
        self.assertTrue((self.folder / "state.json").is_file())

    @unittest.skipUnless(os.name == "nt", "Windows working-directory alias")
    def test_extended_windows_outside_cwd_is_rejected(self) -> None:
        self.append_usage(130000)
        event = self.event("PreToolUse")
        event["cwd"] = "\\\\?\\" + str(self.root.with_name("project-other"))
        self.assertEqual(handle(event, self.root), {})
        self.assertFalse(self.folder.exists())

    def test_recent_usage_is_bounded_and_ignores_unrelated_transcripts(self) -> None:
        self.transcript.write_text("x" * (TAIL_BYTES * 2) + "\n", encoding="utf-8")
        self.append_usage(100000)
        usage = recent_usage(str(self.transcript), self.session)
        self.assertIsNotNone(usage)
        self.assertEqual(usage.tokens, 100000)
        self.assertIsNone(recent_usage(str(self.transcript), str(uuid4())))

    def test_invalid_usage_is_not_reported_as_zero(self) -> None:
        for window in (0, -1, "258400", True):
            record = {"timestamp": "2026-10-03T12:00:00Z", "payload": {
                "type": "token_count", "info": {"model_context_window": window,
                                               "last_token_usage": {"total_tokens": 1000}}}}
            self.assertIsNone(usage_from_record(record))


if __name__ == "__main__":
    unittest.main()
