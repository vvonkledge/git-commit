# git-commit

A [Claude Code custom skill](https://docs.anthropic.com/en/docs/claude-code/skills) that autonomously analyzes your working tree, groups changes into logical commits, and creates clean [Commitizen](https://commitizen-tools.github.io/commitizen/)-formatted messages — with built-in safety hooks to prevent common mistakes.

## What it does

When you invoke `/git-commit` inside Claude Code, the skill:

1. Inspects staged, unstaged, and untracked files
2. Groups related changes into logical units (feature + its tests = one commit, dependency updates = another)
3. Stages files explicitly (never `git add .`)
4. Creates commits with properly formatted Commitizen messages (`feat(auth): add login endpoint`)
5. Outputs a summary report of everything it did

The entire workflow runs autonomously — no interactive prompts.

## Project structure

```
.
├── SKILL.md                        # Skill definition (metadata + instructions)
└── hooks/
    ├── block-git-add-all.py        # Blocks `git add .`, `-A`, `--all`
    ├── block-sensitive-files.py     # Blocks .env, *.pem, *.key, credentials, secrets
    ├── block-debug-artifacts.py     # Blocks *.log, tmp_*, *.tmp, debug_*
    ├── block-large-files.py         # Blocks files > 5 MB
    ├── block-merge-conflicts.py     # Blocks files with unresolved conflict markers
    └── test_hooks.py                # Comprehensive test suite for all hooks
```

## How it works

### SKILL.md

The `SKILL.md` file is a Claude Code [skill definition](https://docs.anthropic.com/en/docs/claude-code/skills). Its YAML front matter configures:

- **`allowed-tools`** — restricts the skill to only `git add`, `git commit`, `git status`, `git diff`, and `git log`
- **`model: haiku`** — runs on a fast, cheap model since the task is well-defined
- **`context: fork`** — runs in a forked context so it doesn't pollute the main conversation
- **`hooks`** — registers five `PreToolUse` hooks that intercept every `Bash` tool call before execution

The Markdown body provides the full prompt: the Commitizen format reference, grouping heuristics, guardrails, and a cookbook of example scenarios.

### PreToolUse hooks

Each hook in `hooks/` is a standalone Python script that acts as a **gate on `git add` commands**. Claude Code pipes a JSON event to stdin before executing any Bash tool call. The hook inspects the command and either:

- **Allows it** — produces no output (silent pass)
- **Blocks it** — writes `{"decision": "block", "reason": "..."}` to stdout

All hooks follow the same pattern:

1. Parse the JSON event from stdin
2. Extract the `command` string from `tool_input`
3. Check if it's a `git add` command (ignore everything else)
4. Inspect the file arguments against their specific rules
5. Block with a descriptive reason if a violation is found

| Hook | What it prevents | Behavior on match |
|------|-----------------|-------------------|
| `block-git-add-all.py` | `git add .`, `git add -A`, `git add --all` | Block the command |
| `block-sensitive-files.py` | `.env*`, `*.pem`, `*.key`, `credentials*`, `*secret*` | Block, list the offending files |
| `block-debug-artifacts.py` | `*.log`, `tmp_*`, `*.tmp`, `debug_*` | Block, list the offending files |
| `block-large-files.py` | Files >= 5 MB | Block, show file sizes |
| `block-merge-conflicts.py` | Files containing `<<<<<<<`, `=======`, `>>>>>>>` | Block the entire command |

Hooks are non-destructive: they only block commands, never modify files.

## Installation

1. Clone this repo into your Claude Code skills directory:

   ```bash
   # Default skill location
   mkdir -p ~/.claude/skills
   git clone git@github.com:vvonkledge/git-commit.git ~/.claude/skills/git-commit
   ```

2. Make the hooks executable (they use `uv run` via shebang):

   ```bash
   chmod +x ~/.claude/skills/git-commit/hooks/*.py
   ```

3. Ensure [uv](https://docs.astral.sh/uv/) is installed — the hooks use inline script metadata (`# /// script`) so no virtual environment setup is needed.

## Usage

Inside any Claude Code session:

```
/git-commit
```

Optionally pass a scope hint to guide commit scoping:

```
/git-commit auth
```

## Running tests

The test suite covers all five hooks with positive, negative, edge-case, and malformed-input tests.

```bash
uv run pytest hooks/test_hooks.py -v
```

## Requirements

- Python >= 3.10
- [uv](https://docs.astral.sh/uv/) (for running scripts with inline dependencies)
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI
