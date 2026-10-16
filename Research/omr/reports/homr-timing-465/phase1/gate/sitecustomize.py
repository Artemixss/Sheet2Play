"""Offline, Git-free gate inherited by this audit's Python children."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys

_GIT = re.compile(r"(?:^|[\s\"'\/\\])git(?:\.exe)?(?=$|[\s\"'])", re.IGNORECASE)
_RECORD = Path(__file__).with_name("blocked-actions.jsonl")


def _text(value: object) -> str:
    if isinstance(value, (str, bytes, os.PathLike)):
        return os.fsdecode(value)
    if isinstance(value, (tuple, list)):
        return " ".join(_text(part) for part in value)
    return ""


def _audit(event: str, arguments: tuple[object, ...]) -> None:
    blocked = event in {"socket.connect", "socket.sendto", "socket.getaddrinfo", "socket.gethostbyname"}
    if event == "subprocess.Popen":
        blocked = _GIT.search(_text(arguments[0]) + " " + _text(arguments[1])) is not None
    elif event == "os.system":
        blocked = _GIT.search(_text(arguments[0])) is not None
    if not blocked:
        return
    row = json.dumps({"event": event, "pid": os.getpid(), "arguments": _text(arguments)}) + "\n"
    descriptor = os.open(_RECORD, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(descriptor, row.encode("utf-8"))
    finally:
        os.close(descriptor)
    raise PermissionError("Phase 1 revalidation prohibits network access and Git launches")


sys.addaudithook(_audit)
INSTALLED = True
