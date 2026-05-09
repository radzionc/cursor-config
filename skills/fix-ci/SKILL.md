---
name: fix-ci
description: Diagnose and repair failing GitHub PR checks on the current branch, then push and wait until checks are green.
---

# Fix CI

Repair failing CI/checks for an existing GitHub PR branch. Loop until checks pass or the failure needs human input.

## Scope

This skill owns only check repair:

- diagnose failed checks
- fix code/config/test failures
- verify the failed path when practical
- commit only the fix paths
- push
- wait for the latest PR head checks

It must not create PRs, mark PRs draft/ready, enable auto-merge, merge PRs, edit PR titles, or move issue tracker state.

## Commands

Use the shared PR helper from the repository root:

```bash
npx tsx ~/.cursor/scripts/github-pr.ts status [--pr <number-or-url>]
npx tsx ~/.cursor/scripts/github-pr.ts failed-checks [--pr <number-or-url>]
npx tsx ~/.cursor/scripts/github-pr.ts wait-checks [--pr <number-or-url>]
```

The helper uses `GITHUB_TOKEN` first and falls back to `gh auth token`.

## Workflow

### 1. Identify the failing checks

Run:

```bash
npx tsx ~/.cursor/scripts/github-pr.ts failed-checks
```

Then fetch logs from the best source:

- Prefer `gh run view <run-id> --log-failed` when the failed check maps to a GitHub Actions run.
- Otherwise open/read the failed check URL and reproduce locally.

Do not guess from the check name alone.

### 2. Fix the real failure

Common failures: lint, typecheck, tests, build, generated files, missing dependency updates, stale snapshots, or incorrect environment assumptions.

If the failure is clearly flaky infrastructure, retry once with an empty commit:

```bash
git commit --allow-empty -m "ci: retry checks"
git push
```

Only do this after checking the failure. Do not use empty retries as the first diagnostic step.

### 3. Verify only what maps to the failure

Use the failed check logs and CI workflow files as the source of truth.

- If the failed command is clear and runnable locally, run that command or the smallest equivalent project script.
- If the failure depends on CI-only services, secrets, runners, caches, or a long full-suite run, do not block on local verification. Push the fix and use `wait-checks`.
- Do not invoke local `finish`, QA, or quality-gates workflows from this skill.

Fix local failures that reproduce the CI failure. Otherwise continue to push and wait for CI.

### 4. Commit and push safely

Stage only paths you intentionally changed for the CI fix:

```bash
git add -A -- <paths fixed for ci>
git commit -m "fix: repair ci failure"
git push
```

Use `git push --force-with-lease` only when the branch was rebased or rewritten. Never use `git push --force`.

### 5. Wait for checks

Run:

```bash
npx tsx ~/.cursor/scripts/github-pr.ts wait-checks
```

Exit handling:

- `0` — checks are green; done.
- `2` — latest checks failed; repeat from step 1.
- `3` — checks timed out; inspect `status`. If checks are still pending, run `wait-checks` again with a longer timeout. If a check failed, repeat from step 1.

Stop after 2 full diagnose/fix cycles if the failure still is not understood. Notify the user:

```bash
~/.cursor/scripts/notify.sh "CI keeps failing, need your help"
```

## Rules

- Always diagnose from logs or failed check output before editing.
- Verify locally only when the failing CI command is clear and practical to reproduce.
- Never bundle unrelated dirty work into a CI-fix commit.
- Never leave the PR on a failed latest check unless you have notified the user and explained the blocker.
