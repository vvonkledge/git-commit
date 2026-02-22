---
name: git-commit
description: Autonomously analyzes working tree changes, groups files into logical coherent commits, and creates commits following the Commitizen convention
argument-hint: [optional commit scope hint]
disable-model-invocation: false
user-invocable: true
allowed-tools: Bash(git add:*), Bash(git commit:*), Bash(git status:*), Bash(git diff:*), Bash(git log:*)
model: haiku
context: fork
agent: general-purpose
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "./hooks/block-git-add-all.py"
          timeout: 10
          async: false
          statusMessage: "Validating git command..."
          once: false
        - type: command
          command: "./hooks/block-sensitive-files.py"
          timeout: 10
          async: false
          statusMessage: "Checking for sensitive files..."
          once: false
---

## Purpose

Fully autonomous skill that analyzes all working tree changes, groups files into logical coherent commits, stages them individually, and creates clean Commitizen-formatted commit messages — without any user interaction.

## Context

```bash
echo "=== Git Status ==="
git status --short

echo -e "\n=== Unstaged Changes ==="
git diff --stat

echo -e "\n=== Staged Changes ==="
git diff --cached --stat

echo -e "\n=== Recent Commits ==="
git log --oneline -10
```

## Instructions

### Workflow

1. **Analyze all changes** — review staged, unstaged, and untracked files from the context above
2. **Group files into logical coherent commits** — related changes belong together:
   - Feature code + its tests + its migration → single commit
   - Dependency updates (lockfiles, package manifests) → separate commit
   - Documentation changes → separate commit
   - Config/tooling changes → separate commit
   - Unrelated bug fixes → separate commits
3. **For each group, in dependency order** (deps first, then features, then docs):
   - Stage specific files: `git add <file1> <file2> ...` — **never** use `git add .`, `git add -A`, or `git add --all`
   - Craft a Commitizen-formatted commit message (see format below)
   - Execute commit using a HEREDOC:
     ```
     git commit -m "$(cat <<'EOF'
     <type>(<scope>): <subject>

     <body>

     <footer>
     EOF
     )"
     ```
   - Verify with `git log --oneline -1`
4. **Output the final report** (see Report section)

If the user provided a scope hint argument, use it to guide scope selection across commits.

### Commitizen Format

#### Types

| Type       | When to use                                      |
|------------|--------------------------------------------------|
| `feat`     | A new feature                                    |
| `fix`      | A bug fix                                        |
| `docs`     | Documentation only changes                       |
| `style`    | Formatting, semicolons, etc. (no logic change)   |
| `refactor` | Code change that neither fixes nor adds          |
| `perf`     | Performance improvement                          |
| `test`     | Adding or correcting tests                       |
| `build`    | Build system or external dependency changes      |
| `ci`       | CI configuration changes                         |
| `chore`    | Other changes that don't modify src or test      |
| `revert`   | Reverts a previous commit                        |

#### Message Rules

- **Subject line**: imperative mood, lowercase, no period, ≤72 characters
- **Scope**: the module, component, or area affected (e.g., `auth`, `api`, `cli`)
- **Body**: explain *what* and *why*, not *how* — wrap at 80 characters
- **Footer**: `BREAKING CHANGE: <description>` for breaking changes, `Closes #N` for issue references

### Guardrails

| Condition | Action |
|-----------|--------|
| Sensitive files (`.env*`, `*.pem`, `*.key`, `credentials*`, `*secret*`) | Skip the file, warn in report |
| Large binary files (>5MB) | Skip the file, warn in report |
| Merge conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`) in any file | **Abort entirely**, report conflicted files |
| Debug artifacts (`*.log`, `tmp_*`, `*.tmp`, `debug_*`) | Skip the file, warn in report |
| Grouping is ambiguous | Prefer smaller, atomic commits |
| Purpose of a change is unclear | Use `chore` type |
| Files are already staged | Respect the existing staging — commit staged files first as their own logical group |
| No changes detected | Exit gracefully with message "Nothing to commit" |

## Cookbook

```
IF: All changes belong to a single feature
THEN: Create one `feat(scope): ...` commit
EXAMPLE: New API endpoint + handler + test + migration → single feat commit

IF: Changes span multiple concerns (feature + dependency update + docs)
THEN: Split into separate commits in order: deps → feature → docs
EXAMPLE: package.json update → new component + test → README update

IF: Only test files changed
THEN: Use `test(scope): ...` type
EXAMPLE: test(auth): add unit tests for login flow

IF: A file contains merge conflict markers
THEN: Abort entirely and report the conflicted files
EXAMPLE: "Cannot commit: unresolved conflicts in src/auth.ts"

IF: Sensitive files detected in changes
THEN: Skip them, commit everything else, warn at end
EXAMPLE: ".env.local skipped — contains sensitive data"

IF: Only config or tooling files changed (linter, formatter, tsconfig, etc.)
THEN: Use `chore(scope): ...` type
EXAMPLE: chore(lint): update eslint configuration

IF: Already-staged files exist alongside unstaged changes
THEN: Commit the staged files first as their own group, then process remaining
EXAMPLE: Staged migration committed first → then unstaged feature code
```

## Report

After all commits are created, output a summary:

1. **Commits created**: total count
2. **Commit log**: `git log --oneline -N` showing all new commits (where N = number of commits created)
3. **Skipped files**: list each skipped file with the reason (sensitive, binary, debug artifact)
4. **Warnings**: any additional notes (e.g., "1 sensitive file excluded", "large binary skipped")
