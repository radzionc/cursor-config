---
name: resolve-pr-comments
description: Address CodeRabbit (or other AI reviewer) comments on a pull request to make it merge-ready.
disable-model-invocation: true
---

# Resolve PR Review Comments

Address unresolved GitHub PR review threads so the PR can become merge-ready.

## Usage

Provide the PR link or number. The agent will:

1. Fetch all unresolved review comments
2. Classify each thread as AI-only, human, or mixed
3. Critically evaluate each suggestion before implementing
4. Push valid fixes
5. Resolve conversations after they are handled

## Auth Model

- Use the repo's configured `git` remote for fetch/push. SSH account selection comes from the repository remote, not from GitHub CLI.
- Do **not** require GitHub MCP or `gh` for this workflow unless the user explicitly wants them.

## Workflow

### 1. Fetch Review Comments

List unresolved review threads:

```bash
npx tsx ~/.cursor/scripts/github-pr.ts threads --pr <PR_NUMBER_OR_URL>
```

Focus on unresolved threads and critically inspect the actual code before changing anything.

Thread classes:

- `ai` — every participant is an automated reviewer/bot. No reply is needed.
- `human` — every participant is human or unknown.
- `mixed` — an automated reviewer thread has human participation.

### 2. Evaluate Each Comment Critically

AI reviewers (CodeRabbit, etc.) can be wrong. Before implementing any suggestion:

- **Verify the claim**: Does the code actually have the issue described? Check actual behavior, not just static analysis.
- **Question "critical" or "major" labels**: These are often overstated. A real critical bug would likely have been caught during development.
- **Check if current code works**: If functionality works correctly, the suggestion may be based on misunderstanding.
- **Prefer no-op over churn**: If the benefit is small, speculative, stylistic, or risky, skip it.
- **Ask the user** if a human or mixed thread is questionable or would require significant changes.

### 3. Decide What Is Actually Worth Fixing

Good candidates to address:

- Real correctness bugs
- Missing null/error handling that can actually break runtime behavior
- Clear typing or API misuse that can fail checks or production behavior
- Straightforward test or logic gaps with low regression risk

Usually skip:

- Purely stylistic suggestions
- Large refactors disguised as review comments
- Speculative performance concerns
- Comments that conflict with existing local review, QA, or working behavior
- Suggestions that would expand scope or create regression risk near the finish line

### 4. Address Valid Comments

For comments that are actually valid:

- Implement the fix
- Group related changes efficiently
- Keep the change as small as possible

For AI-only invalid suggestions, resolve without replying. For human or mixed invalid/questionable suggestions, bring the thread to the user instead of silently dismissing it.

### 5. Run Checks

Run the project's check script. Fix any errors before proceeding.

### 6. Push and Resolve

```bash
git add -A -- <paths changed for review comments>
git commit -m "$(cat <<'EOF'
fix: address PR review comments

EOF
)"
git push
```

Resolve handled conversations:

```bash
npx tsx ~/.cursor/scripts/github-pr.ts resolve-all-threads --pr <PR_NUMBER_OR_URL> --include-human
```

For AI-only threads that needed no code changes:

```bash
npx tsx ~/.cursor/scripts/github-pr.ts resolve-ai-threads --pr <PR_NUMBER_OR_URL>
```

## Goal

- All review threads resolved
- All checks pass
- PR ready to merge

## Rules

- AI-only reviewer comments do not need replies; resolve them after triage.
- Human and mixed threads need attention. Fix clearly correct comments; ask the user for ambiguous, risky, or product-judgment comments.
- Never resolve a human or mixed thread before it is handled.
- `--include-human` is an explicit safety latch. Only use it after a full `threads` pass and after all human/mixed threads are addressed or approved by the user.
- Never bundle unrelated work into the review-fix commit.
