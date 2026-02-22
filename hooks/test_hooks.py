#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest"]
# ///
"""Tests for PreToolUse hook scripts.

Run from repo root:  uv run hooks/test_hooks.py
"""

import json
import subprocess

import pytest

BLOCK_ADD_ALL = "hooks/block-git-add-all.py"
BLOCK_SENSITIVE = "hooks/block-sensitive-files.py"


def run_hook(script: str, command: str) -> dict | None:
    """Pipe a tool_input command to a hook script, return parsed output or None."""
    payload = json.dumps({"tool_input": {"command": command}})
    result = subprocess.run(
        ["uv", "run", script],
        input=payload,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout) if result.stdout.strip() else None


def run_hook_raw(script: str, stdin: str) -> dict | None:
    """Pipe raw stdin to a hook script (for malformed-input tests)."""
    result = subprocess.run(
        ["uv", "run", script],
        input=stdin,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout) if result.stdout.strip() else None


# ── block-git-add-all ─────────────────────────────────────────────────


class TestBlockGitAddAll:
    def test_add_dot_blocked(self):
        result = run_hook(BLOCK_ADD_ALL, "git add .")
        assert result["decision"] == "block"

    def test_add_dash_A_blocked(self):
        result = run_hook(BLOCK_ADD_ALL, "git add -A")
        assert result["decision"] == "block"

    def test_add_all_flag_blocked(self):
        result = run_hook(BLOCK_ADD_ALL, "git add --all")
        assert result["decision"] == "block"

    def test_specific_files_pass(self):
        assert run_hook(BLOCK_ADD_ALL, "git add src/app.py utils.py") is None

    def test_non_git_command_pass(self):
        assert run_hook(BLOCK_ADD_ALL, "git diff --stat") is None

    def test_malformed_json_pass(self):
        assert run_hook_raw(BLOCK_ADD_ALL, "not json") is None


# ── block-sensitive-files ─────────────────────────────────────────────


class TestBlockSensitiveFiles:
    @pytest.mark.parametrize(
        "command",
        [
            "git add src/app.py",
            "git add README.md src/utils.py",
            "git add -p src/app.py",
        ],
        ids=["single-safe", "multiple-safe", "with-flag"],
    )
    def test_safe_files_pass(self, command):
        assert run_hook(BLOCK_SENSITIVE, command) is None

    @pytest.mark.parametrize(
        ("command", "expected_pattern"),
        [
            ("git add .env", ".env*"),
            ("git add .env.local", ".env*"),
            ("git add .env.production", ".env*"),
            ("git add deploy.pem", "*.pem"),
            ("git add server.key", "*.key"),
            ("git add credentials.json", "credentials*"),
            ("git add credentials", "credentials*"),
            ("git add src/secrets.yaml", "*secret*"),
            ("git add my_secret_config.py", "*secret*"),
        ],
        ids=[
            "env", "env-local", "env-production",
            "pem", "key",
            "credentials-json", "credentials-bare",
            "secrets-yaml", "secret-in-name",
        ],
    )
    def test_sensitive_file_blocked(self, command, expected_pattern):
        result = run_hook(BLOCK_SENSITIVE, command)
        assert result is not None
        assert result["decision"] == "block"
        assert expected_pattern in result["reason"]

    def test_mixed_files_blocks_only_sensitive(self):
        result = run_hook(BLOCK_SENSITIVE, "git add .env.local src/app.py server.key")
        assert result["decision"] == "block"
        assert ".env.local" in result["reason"]
        assert "server.key" in result["reason"]
        assert "src/app.py" not in result["reason"]

    def test_non_git_add_passes(self):
        assert run_hook(BLOCK_SENSITIVE, "git diff --stat") is None

    def test_git_add_with_no_files_passes(self):
        assert run_hook(BLOCK_SENSITIVE, "git add -p") is None

    def test_malformed_json_passes(self):
        assert run_hook_raw(BLOCK_SENSITIVE, "not json") is None

    def test_empty_stdin_passes(self):
        assert run_hook_raw(BLOCK_SENSITIVE, "") is None


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
