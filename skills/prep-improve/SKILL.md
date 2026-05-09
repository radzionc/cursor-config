---
name: prep-improve
description: Extract context about an AI workflow issue and copy a self-contained brief to clipboard for running improve in a fresh session.
disable-model-invocation: true
---

# Prep Improve

Gather context about a specific AI workflow issue and copy a self-contained brief to clipboard. The user pastes this into a fresh session with a smart model and attaches `@skills/improve`.

## Why This Exists

The `improve` skill produces persistent artifacts (rules, skills, agents, hooks) that shape every future session. Quality matters — these should run on the smartest available model. But the session where you notice an issue is often running on a cheaper model. This skill bridges the gap: cheap model extracts context, smart model implements the fix.

## Process

### Step 1: Understand the Issue

Parse the user's description. Identify:

- **What went wrong** — the concrete failure or friction
- **When it happened** — which task, codebase, workflow
- **Reproducer** — what triggers the issue (prompt patterns, file types, task types)

If the user references a past session, read the transcript from the agent-transcripts path in system context.

If the issue is too vague, ask **one** focused clarifying question.

### Step 2: Gather Relevant Config

1. Read `~/.cursor/.cursor-config-source` for the cursor-config repo path (fall back to `~/.cursor/`)
2. List `agents/`, `rules/`, `skills/` in the cursor-config repo
3. Read any files related to the issue — existing rules/skills that partially cover it, adjacent config that might need modification
4. If the issue is project-specific, also check the current project's `.cursor/`

### Step 3: Compose the Brief

Build a self-contained message the receiving model can act on immediately with the `improve` skill. Use this structure:

```
## Issue

[What went wrong, when, how often. Include exact quotes of corrections, error messages, or failed outputs from the session.]

## Session Context

[Relevant details: what was being built, what approaches were tried, where the agent went wrong. Only include what helps understand the issue — not the entire session.]

## Existing Config

[Paths and brief summaries of related rules/skills/agents. If an existing file should be modified rather than creating something new, say so explicitly. Include file contents when the receiving model will need them to make edits.]

## Affected Project

[Repo path and relevant file paths, if the issue is project-specific. Omit if universal.]

## Transcript

[If a past session is relevant: include the full absolute path to the transcript file so the receiving model can read it directly. Omit if working from the current session only.]
```

Omit sections that have no content.

### Step 4: Copy to Clipboard

Copy the brief to clipboard. Use `pbcopy` on macOS or `xclip -selection clipboard` on Linux. Then tell the user:

1. Start a fresh chat with your smartest model
2. Paste the clipboard content
3. Attach `@skills/improve`
4. Send

## Guidelines

- **Context extraction, not implementation** — this skill gathers and formats. It does not create rules, skills, or agents. Don't research mechanisms or read `cursor-features.md` — that's `improve`'s job.
- **Self-contained** — the receiving model has zero context from this session. Everything it needs must be in the brief.
- **Preserve specifics** — exact error messages, file paths, correction quotes, and command outputs are more valuable than summaries.
- **Include file contents when needed** — if existing config must be modified, include the content so the receiving model doesn't waste tokens re-reading. For large files (100+ lines), include the relevant section and note the full path for the receiver to read.
- **Concise** — include only what's needed to understand and fix the issue. Don't dump the entire session.
