---
name: sync-with-main
description: Rebase the current branch onto origin/main, resolve all conflicts, and force-push. Use when user says "sync with main", "rebase on main", "update branch", or when a PR has merge conflicts.
disable-model-invocation: true
---

# Sync with Main

Rebase the current branch onto the latest `origin/main`, resolve all conflicts, and push. Runs to full completion — the user should not need to intervene.

Assumes a squash-merge workflow: commit history cleanliness does not matter. Prioritize safety and correctness over clean history.

## Prerequisites

Must be on a feature branch, not `main`.

## Workflow

### 1. Pre-flight

```bash
CURRENT=$(git branch --show-current)
if [ "$CURRENT" = "main" ]; then
  echo "ERROR: Already on main."
  exit 1
fi

if ! git diff --quiet || ! git diff --cached --quiet; then
  git stash push -m "sync-with-main auto-stash"
fi
```

### 2. Fetch and rebase

```bash
git fetch origin
git rebase origin/main
```

If the rebase succeeds with no conflicts, skip to step 4.

### 3. Resolve conflicts

Follow the **[resolve-rebase-conflicts](../resolve-rebase-conflicts/SKILL.md)** skill to resolve all conflicts and complete the rebase. Do not return here until the rebase is fully done (no remaining rebase steps).

### 4. Push

```bash
git push --force-with-lease
```

### 5. Restore stash

If changes were stashed in step 1:

```bash
git stash pop
```

### 6. Report

Summarize: branch name, commits replayed, conflicts resolved (which files), push status.

## Rules

- **NEVER** use `git push --force` — always `--force-with-lease`.
- **NEVER** leave the rebase incomplete — it must fully finish or be aborted.
- If the rebase is truly unresolvable, abort with `git rebase --abort`, restore stash if applicable, and report to the user.
