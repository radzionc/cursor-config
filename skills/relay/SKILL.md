---
name: relay
description: Compress the current session into a short, receiver-agnostic clipboard brief for another AI agent. Use when handing work off mid-task to a different chat, model, or tool — the user will describe what they want in the receiving session, not here.
disable-model-invocation: true
---

# Relay

Produce a short, dense brief about the current work and copy it to clipboard. The user pastes it into another AI session and tells that agent what to do there.

Do not ask the user what the next agent should do. The brief is receiver-agnostic — pack the context any agent would need to understand the situation, regardless of the task they're given.

## Process

### 1. Gather repo state

Skip if the work is non-code. Otherwise run in parallel:

- `git -C <repo> status --short`
- `git -C <repo> diff --stat HEAD`
- `git -C <repo> log -1 --format='%h %s'`

Read actual diffs (`git diff`, `git diff --cached`) only if needed to summarize what changed per file. The user typically works on `main` with unstaged changes — don't assume a feature branch.

### 2. Pull from this conversation

Extract:

- **Goal** — what the user is trying to accomplish
- **What was done** — concrete progress in this session
- **Decisions** — choices already made that shouldn't be re-litigated
- **References** — Linear/Jira IDs, PR/issue URLs, design links, docs the user mentioned
- **Open threads** — unresolved items or known issues

### 3. Compose the brief

Use this structure. Skip empty sections. Aim for under 40 lines.

```
## Goal
[1-2 sentences: what the user is working on and why.]

## What's been done
[Bulleted progress in this session. For code: one line per touched file with what changed.]

## Decisions & constraints
- [Bulleted, only if non-obvious]

## References
- Linear: ABC-123
- PR: github.com/...

## Open threads
- [Optional — unresolved items, known issues]
```

### 4. Copy to clipboard

`pbcopy` on macOS, `xclip -selection clipboard` on Linux. Tell the user the brief is on the clipboard and ready to paste.

## Guidelines

- **Receiver-agnostic.** Don't guess what the next agent will be asked. Provide context, not instructions.
- **Short beats complete.** Under 40 lines. The receiver can ask for more.
- **AI-readable.** Headings, bullets, exact identifiers. No filler prose, no pleasantries.
- **Quote specifics.** Exact ticket IDs, file paths, error messages, user requirements — not paraphrases.
- **Don't act on the work.** This skill only produces the brief. It does not write messages, do reviews, or modify code.
