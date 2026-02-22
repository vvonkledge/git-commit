#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""PreToolUse hook that blocks staging large files.

Prevents `git add` from staging files larger than 5 MB.
"""

import json
import shlex
import sys
from pathlib import Path

LARGE_FILE_THRESHOLD = 5 * 1024 * 1024  # 5 MB


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError, ValueError):
        return

    tool_input = event.get("tool_input", {})
    command = tool_input.get("command", "")

    try:
        parts = shlex.split(command)
    except ValueError:
        return

    if len(parts) < 2 or parts[0] != "git" or parts[1] != "add":
        return

    # Extract file arguments (skip "git", "add", and flags)
    file_args = [p for p in parts[2:] if not p.startswith("-")]

    matched: list[tuple[str, float]] = []
    for filepath in file_args:
        p = Path(filepath)
        try:
            if not p.is_file():
                continue
            size = p.stat().st_size
        except (FileNotFoundError, OSError):
            continue
        if size >= LARGE_FILE_THRESHOLD:
            matched.append((filepath, size / (1024 * 1024)))

    if matched:
        lines = ["Large files detected — remove them from the git add command and skip them:"]
        for filepath, size_mb in matched:
            lines.append(f"  - {filepath} ({size_mb:.1f} MB)")
        lines.append("Stage only the non-large files instead.")

        result = {
            "decision": "block",
            "reason": "\n".join(lines),
        }
        json.dump(result, sys.stdout)
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
