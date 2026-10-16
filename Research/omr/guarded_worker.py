"""Wait for successful Job assignment before launching substantive child work."""
import json
import subprocess
import sys


def main() -> int:
    message = sys.stdin.buffer.readline(1024 * 1024)
    if not message.endswith(b"\n"):
        raise ValueError("Missing or oversized supervisor start message")
    payload = json.loads(message)
    command = payload.get("command")
    if payload.get("action") != "start" or not isinstance(command, list) or not command:
        raise ValueError("Invalid supervisor start message")
    if any(not isinstance(argument, str) or not argument or "\0" in argument for argument in command):
        raise ValueError("Invalid worker argument")
    return subprocess.run(command, stdin=subprocess.DEVNULL, check=False).returncode


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as error:
        print(f"Worker refused to start: {error}", file=sys.stderr)
        sys.exit(2)
