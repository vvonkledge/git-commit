#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""PreToolUse hook that blocks blanket `git add` commands.

Prevents `git add .`, `git add -A`, `git add -a`, and `git add --all`
to enforce explicit file staging.
"""

import json
import re
import sys


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return

    tool_input = event.get("tool_input", {})
    command = tool_input.get("command", "")

    pattern = r"git\s+add\s+(-[^\s]*\s+)*(\.|-A|-a|--all)(\s|$)"

    if re.search(pattern, command):
        result = {
            "decision": "block",
            "reason": (
                "Blanket staging (git add . / -A / --all) is not allowed. "
                "Stage specific files instead: git add <file1> <file2> ..."
            ),
        }
        json.dump(result, sys.stdout)
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
