"""Enforce the recovery prohibition in this regression process and Python children."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys
from typing import Any

_GIT_TOKEN = re.compile(r"(?:^|[\s\"'\/\\])git(?:\.exe)?(?=$|[\s\"'])", re.IGNORECASE)
_RECORD = Path(__file__).with_name("blocked-git.jsonl")


def _text(value: Any) -> str:
    if isinstance(value, (str, bytes, os.PathLike)):
        return os.fsdecode(value)
    if isinstance(value, (tuple, list)):
        return " ".join(_text(part) for part in value)
    return ""


def _audit(event: str, args: tuple[Any, ...]) -> None:
    if event == "subprocess.Popen":
        command = _text(args[0]) + " " + _text(args[1])
    elif event == "os.system":
        command = _text(args[0])
    else:
        return
    if _GIT_TOKEN.search(command) is None:
        return
    row = json.dumps({"event": event, "pid": os.getpid(), "command": command}) + "\n"
    descriptor = os.open(_RECORD, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(descriptor, row.encode("utf-8"))
    finally:
        os.close(descriptor)
    raise PermissionError("Recovery policy prohibits invoking Git; no process was launched")


sys.addaudithook(_audit)
INSTALLED = True
