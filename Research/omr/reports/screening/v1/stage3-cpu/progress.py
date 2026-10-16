"""Read compact live progress without changing frozen results."""
import json
from collections import Counter
from pathlib import Path
import sys

import psutil

root = Path(__file__).resolve().parent.parent / "2c98d5638c36"
manifest = json.loads((root.parent / "manifest-v5-607ff64134da.json").read_text())
candidate = sys.argv[1]
if candidate not in manifest["candidates"]:
    raise ValueError("Expected a pinned CPU candidate")
config = manifest["candidates"][candidate]["identity_sha256"][:12]
results = [json.loads(p.read_text()) for p in (root / "completed" / candidate / config).glob("*/result.json")]
outcomes = [json.loads(p.read_text()) for p in (root / "attempts" / candidate / config).glob("*/*/outcome.json")]
scores = [p for p in (root / "scored" / candidate / config).rglob("score.json")
          if not any(part.startswith(".") for part in p.relative_to(root).parts)]
score_outcomes = [json.loads(p.read_text()) for p in (root / "score-attempts" / candidate / config).rglob("outcome.json")]
lock = root / "worker.lock"
live = None
if lock.exists():
    live = json.loads(lock.read_text())
    live["process_alive"] = psutil.pid_exists(live["pid"]) and abs(
        psutil.Process(live["pid"]).create_time() - live["creation_time"]) < 0.01
session = root / "sessions" / f"stage3-{'audiveris' if candidate == 'audiveris_page' else 'zeus'}-screen-01.json"
print(json.dumps({"candidate": candidate, "completed": len(results),
    "statuses": dict(Counter(r["status"] for r in results)), "scored": len(scores),
    "completed_attempt_seconds": round(sum(o["elapsed_seconds"] for o in outcomes), 1),
    "ram_peak": max((o["peak_system_ram_percent"] for o in outcomes), default=None),
    "vram_peak_mib": max((o["peak_device_vram_mib"] for o in outcomes), default=None),
    "current_system_ram_percent": psutil.virtual_memory().percent,
    "interruptions": sum(o["reason"] is not None for o in outcomes),
    "score_attempt_seconds": round(sum(o["elapsed_seconds"] for o in score_outcomes), 1),
    "score_interruptions": sum(o["reason"] is not None or o["exit_code"] != 0 for o in score_outcomes),
    "session": json.loads(session.read_text()) if session.exists() else None,
    "lock": {"pid": live["pid"], "creation_time": live["creation_time"],
             "process_alive": live["process_alive"]} if live else None}))
