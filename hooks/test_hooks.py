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
from pathlib import Path

import pytest

BLOCK_ADD_ALL = "hooks/block-git-add-all.py"
BLOCK_SENSITIVE = "hooks/block-sensitive-files.py"
BLOCK_DEBUG = "hooks/block-debug-artifacts.py"
BLOCK_LARGE = "hooks/block-large-files.py"
BLOCK_CONFLICTS = "hooks/block-merge-conflicts.py"


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


# ── block-debug-artifacts ────────────────────────────────────────────


class TestBlockDebugArtifacts:
    @pytest.mark.parametrize(
        "command",
        [
            "git add src/app.py",
            "git add README.md",
        ],
        ids=["python-file", "readme"],
    )
    def test_safe_files_pass(self, command):
        assert run_hook(BLOCK_DEBUG, command) is None

    @pytest.mark.parametrize(
        ("command", "expected_pattern"),
        [
            ("git add app.log", "*.log"),
            ("git add tmp_build", "tmp_*"),
            ("git add cache.tmp", "*.tmp"),
            ("git add debug_output", "debug_*"),
        ],
        ids=["log", "tmp-prefix", "tmp-suffix", "debug-prefix"],
    )
    def test_debug_artifact_blocked(self, command, expected_pattern):
        result = run_hook(BLOCK_DEBUG, command)
        assert result is not None
        assert result["decision"] == "block"
        assert expected_pattern in result["reason"]

    def test_mixed_files_blocks_only_artifacts(self):
        result = run_hook(BLOCK_DEBUG, "git add app.log src/app.py debug_output")
        assert result["decision"] == "block"
        assert "app.log" in result["reason"]
        assert "debug_output" in result["reason"]
        assert "src/app.py" not in result["reason"]

    def test_non_git_add_passes(self):
        assert run_hook(BLOCK_DEBUG, "git diff --stat") is None

    def test_malformed_json_passes(self):
        assert run_hook_raw(BLOCK_DEBUG, "not json") is None

    def test_empty_stdin_passes(self):
        assert run_hook_raw(BLOCK_DEBUG, "") is None


# ── block-large-files ────────────────────────────────────────────────


class TestBlockLargeFiles:
    @pytest.fixture()
    def files(self, tmp_path: Path) -> dict[str, Path]:
        small = tmp_path / "small.bin"
        small.write_bytes(b"\x00" * (1 * 1024 * 1024))  # 1 MB

        large = tmp_path / "large.bin"
        large.write_bytes(b"\x00" * (6 * 1024 * 1024))  # 6 MB

        return {"small": small, "large": large}

    def test_large_file_blocked(self, files):
        result = run_hook(BLOCK_LARGE, f"git add {files['large']}")
        assert result is not None
        assert result["decision"] == "block"
        assert "MB" in result["reason"]

    def test_small_file_passes(self, files):
        assert run_hook(BLOCK_LARGE, f"git add {files['small']}") is None

    def test_mixed_files_blocks_only_large(self, files):
        result = run_hook(BLOCK_LARGE, f"git add {files['small']} {files['large']}")
        assert result is not None
        assert result["decision"] == "block"
        assert "large.bin" in result["reason"]
        assert "small.bin" not in result["reason"]

    def test_nonexistent_file_passes(self):
        assert run_hook(BLOCK_LARGE, "git add /tmp/no-such-file-xyz") is None

    def test_non_git_add_passes(self):
        assert run_hook(BLOCK_LARGE, "git diff --stat") is None

    def test_malformed_json_passes(self):
        assert run_hook_raw(BLOCK_LARGE, "not json") is None

    def test_empty_stdin_passes(self):
        assert run_hook_raw(BLOCK_LARGE, "") is None


# ── block-merge-conflicts ─────────────────────────────────────────────


class TestBlockMergeConflicts:
    @pytest.fixture()
    def files(self, tmp_path: Path) -> dict[str, Path]:
        conflicted = tmp_path / "conflicted.py"
        conflicted.write_text(
            "def greet():\n"
            "<<<<<<< HEAD\n"
            '    return "hello"\n'
            "=======\n"
            '    return "hi"\n'
            ">>>>>>> feature\n",
        )

        clean = tmp_path / "clean.py"
        clean.write_text("def greet():\n    return 'hello'\n")

        partial = tmp_path / "partial.py"
        partial.write_text("<<<<<<< HEAD\nsome code\n")

        image = tmp_path / "image.bin"
        image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\xff\xfe" * 100)

        readme = tmp_path / "readme.md"
        readme.write_text("Use ======= as a separator in tables.\n")

        return {
            "conflicted": conflicted,
            "clean": clean,
            "partial": partial,
            "image": image,
            "readme": readme,
        }

    def test_conflicted_file_blocked(self, files):
        result = run_hook(BLOCK_CONFLICTS, f"git add {files['conflicted']}")
        assert result is not None
        assert result["decision"] == "block"
        assert "conflicted.py" in result["reason"]

    def test_clean_file_passes(self, files):
        assert run_hook(BLOCK_CONFLICTS, f"git add {files['clean']}") is None

    def test_partial_marker_blocked(self, files):
        result = run_hook(BLOCK_CONFLICTS, f"git add {files['partial']}")
        assert result is not None
        assert result["decision"] == "block"

    def test_binary_file_passes(self, files):
        assert run_hook(BLOCK_CONFLICTS, f"git add {files['image']}") is None

    def test_false_positive_passes(self, files):
        assert run_hook(BLOCK_CONFLICTS, f"git add {files['readme']}") is None

    def test_mixed_files_blocks_entirely(self, files):
        result = run_hook(
            BLOCK_CONFLICTS,
            f"git add {files['conflicted']} {files['clean']}",
        )
        assert result is not None
        assert result["decision"] == "block"
        assert "conflicted.py" in result["reason"]
        assert "clean.py" not in result["reason"]
        assert "Do not stage any files" in result["reason"]

    def test_nonexistent_file_passes(self):
        assert run_hook(BLOCK_CONFLICTS, "git add /tmp/no-such-file-xyz") is None

    def test_non_git_add_passes(self):
        assert run_hook(BLOCK_CONFLICTS, "git diff --stat") is None

    def test_malformed_json_passes(self):
        assert run_hook_raw(BLOCK_CONFLICTS, "not json") is None

    def test_empty_stdin_passes(self):
        assert run_hook_raw(BLOCK_CONFLICTS, "") is None


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
