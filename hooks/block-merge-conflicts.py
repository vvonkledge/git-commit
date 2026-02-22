#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""PreToolUse hook that blocks staging files with merge conflict markers.

Prevents `git add` when any listed file contains unresolved merge conflict
markers (<<<<<<<, =======, >>>>>>>).  Unlike other hooks that skip individual
files, this one aborts the entire command — staging clean files alongside
unresolved conflicts creates partial commits from a broken tree.
"""

import json
import shlex
import sys
from pathlib import Path

CONFLICT_MARKERS = ("<<<<<<<", "=======", ">>>>>>>")


def has_conflict_markers(filepath: Path) -> bool:
    """Return True if *filepath* contains a line starting with a conflict marker."""
    try:
        with filepath.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if line.startswith(CONFLICT_MARKERS):
                    return True
    except (FileNotFoundError, OSError):
        pass
    return False


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

    conflicted: list[str] = []
    for filepath in file_args:
        p = Path(filepath)
        if not p.is_file():
            continue
        if has_conflict_markers(p):
            conflicted.append(filepath)

    if conflicted:
        lines = ["Merge conflict markers detected — resolve all conflicts before committing:"]
        for filepath in conflicted:
            lines.append(f"  - {filepath}")
        lines.append("Do not stage any files until all conflicts above are resolved.")

        result = {
            "decision": "block",
            "reason": "\n".join(lines),
        }
        json.dump(result, sys.stdout)
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
