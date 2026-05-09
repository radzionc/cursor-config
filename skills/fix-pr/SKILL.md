---
name: fix-pr
description: Drive an existing GitHub pull request to PR_READY: checks green, no merge conflicts, and review threads resolved.
---

# Fix PR

Drive an existing GitHub PR to **PR_READY**:

- latest checks are green
- branch is not blocked by merge conflicts or being behind the base
- review threads are resolved

This skill stops at PR readiness. It must not decide the organization's finish destination: draft PR, ready-for-review PR, auto-merge, manual merge, Linear/Jira handoff, release notes, screenshots, or local branch cleanup.

## Commands

Run from the target repo root:

```bash
npx tsx ~/.cursor/scripts/github-pr.ts status [--pr <number-or-url>]
npx tsx ~/.cursor/scripts/github-pr.ts ready [--pr <number-or-url>]
npx tsx ~/.cursor/scripts/github-pr.ts threads [--pr <number-or-url>]
npx tsx ~/.cursor/scripts/github-pr.ts resolve-ai-threads [--pr <number-or-url>]
npx tsx ~/.cursor/scripts/github-pr.ts resolve-all-threads [--pr <number-or-url>] --include-human
```

Use `--include-human` only after the review-thread triage below says every human or mixed thread has been addressed or the user has approved resolution.

The helper uses `GITHUB_TOKEN` first and falls back to `gh auth token`.

## Workflow

### 1. Inspect PR state

Run:

```bash
npx tsx ~/.cursor/scripts/github-pr.ts status [--pr <number-or-url>]
```

Use the output as the queue of blockers. Repeat the workflow until `ready` exits `0`.

### 2. Checks are failed, cancelled, or timed out

Use the `fix-ci` skill. It owns diagnosis, targeted verification when useful, commit, push, and waiting for checks.

After `fix-ci` reports green checks, return to step 1. New pushes can create new review threads or merge conflicts.

### 3. Merge conflicts or branch behind base

First follow the local `finish` skill or repo PR script if it defines branch update behavior.

If no local policy exists, choose the safe update path for the repo:

- Use `sync-with-main` only when rebase plus `git push --force-with-lease` is acceptable for this branch.
- Otherwise merge the PR base branch into the current branch, resolve conflicts, commit, push, and return to step 1.

### 4. Review threads

Run:

```bash
npx tsx ~/.cursor/scripts/github-pr.ts threads [--pr <number-or-url>]
```

Threads are classified:

- `ai` — every participant is an automated reviewer/bot. No reply is needed.
- `human` — every participant is human or unknown.
- `mixed` — an automated reviewer thread has human participation.

Handle all classes, but apply different standards.

#### AI-only threads

Critically inspect the claim:

- If it identifies a real product defect, fix it, verify locally, commit, push, and return to step 1.
- If it is style, churn, speculative, already-working behavior, or conflicts with project patterns, resolve it without code changes.

After triage:

```bash
npx tsx ~/.cursor/scripts/github-pr.ts resolve-ai-threads [--pr <number-or-url>]
```

#### Human or mixed threads

Human comments need attention before resolution.

- If every human or mixed thread in the latest `threads` output is clearly correct and low-risk, address all of them. Implement code changes when needed, add concise replies when explanation is needed, verify the touched path, commit, push, then resolve:
  ```bash
  npx tsx ~/.cursor/scripts/github-pr.ts resolve-all-threads [--pr <number-or-url>] --include-human
  ```
- If the comment requires product judgment, disagrees with the current task intent, is ambiguous, or would require a risky change, notify the user and stop:
  ```bash
  ~/.cursor/scripts/notify.sh "Human PR review needs your decision"
  ```

Do a full `threads` pass before using `--include-human`. The helper resolves every unresolved thread, so do not run it while any human or mixed thread from the latest pass remains unaddressed. Do not silently dismiss human or mixed threads.

### 5. Confirm readiness

Run:

```bash
npx tsx ~/.cursor/scripts/github-pr.ts ready [--pr <number-or-url>]
```

Exit handling:

- `0` — PR is ready; report the PR URL and the remaining local finish workflow, if any.
- `1` — PR still has blockers; return to step 1.

## Rules

- Never stop after one push. Recheck PR state until `PR_READY` is true or user input is required.
- Never resolve human or mixed threads without addressing them or asking the user.
- Never reply to AI-only reviewer comments unless the project explicitly requires it; resolving is enough.
- Never use `git push --force`; use `--force-with-lease` only after rebase/rewrite.
- Keep finish policy out of this skill. Local `finish` skills decide what to do after `PR_READY`.
