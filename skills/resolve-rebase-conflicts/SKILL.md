---
name: resolve-rebase-conflicts
description: Automatically resolve git rebase conflicts by analyzing both sides and continuing the rebase. Use when a git rebase is in progress and there are merge conflicts.
---

# Resolve Rebase Conflicts

Resolve all conflicts in a git rebase and drive it to completion. Do not stop until the rebase is fully done.

## Workflow

### 1. Assess state

Run `git status` to confirm a rebase is in progress and identify conflicted files.

### 2. Resolve each conflicted file

For each file listed as "both modified":

1. Read the file and locate all conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`).
2. Understand both sides (rebase inverts the usual labels):
   - **HEAD** (above `=======`): the branch you're rebasing onto (`main`) plus any of your commits already successfully replayed.
   - **Incoming** (below `=======`): the commit from your feature branch currently being replayed.
3. Apply resolution judgment:
   - **One side adds code the other doesn't touch** — keep the addition.
   - **Both sides modify the same lines** — combine intent from both. Prefer structural/API changes from main; preserve feature-specific logic from your branch.
   - **Imports** — merge both sets, deduplicate.
   - **Config files (JSON, YAML, TOML, lock files)** — merge keys from both sides.
   - **Genuinely unclear** — combine both sides and flag for the user in the final report.
4. Verify: no conflict markers remain and the file is syntactically valid.
5. Stage: `git add <file>`.

### 3. Continue and iterate

```bash
git rebase --continue
```

If new conflicts appear (next commit being replayed), go back to step 2. Repeat until `git rebase --continue` completes with no remaining steps.

### 4. Report

Summarize: how many commits were replayed, how many conflicts were resolved, which files were affected, and whether any resolutions need a quick review.

## Escalation

Resolve with your best judgment in virtually all cases. Only flag a resolution to the user when both sides make semantically incompatible changes to the same logic (e.g., both redesign the same component differently). Even then, resolve it — just note which file and why it's worth a glance.

If the rebase is truly unresolvable (binary conflicts, corrupted state), abort with `git rebase --abort` and report.

## Rules

- **NEVER** leave conflict markers in any file.
- **NEVER** skip `git rebase --continue` — complete every rebase step.
- **ALWAYS** iterate until the rebase is fully done.
