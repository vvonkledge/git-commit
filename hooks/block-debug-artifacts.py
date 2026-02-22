#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""PreToolUse hook that blocks staging debug artifacts.

Prevents `git add` from staging files matching debug artifact patterns:
*.log, tmp_*, *.tmp, debug_*
"""

import json
import shlex
import sys
from fnmatch import fnmatch
from pathlib import PurePosixPath

DEBUG_PATTERNS = [
    "*.log",
    "tmp_*",
    "*.tmp",
    "debug_*",
]


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

    matched: list[tuple[str, str]] = []
    for filepath in file_args:
        basename = PurePosixPath(filepath).name
        for pattern in DEBUG_PATTERNS:
            if fnmatch(basename, pattern):
                matched.append((filepath, pattern))
                break

    if matched:
        lines = ["Debug artifacts detected — remove them from the git add command and skip them:"]
        for filepath, pattern in matched:
            lines.append(f"  - {filepath} (matches {pattern})")
        lines.append("Stage only the non-artifact files instead.")

        result = {
            "decision": "block",
            "reason": "\n".join(lines),
        }
        json.dump(result, sys.stdout)
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
