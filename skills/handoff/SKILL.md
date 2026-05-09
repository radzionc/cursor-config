---
name: handoff
description: Compress session context into self-contained task files that a fresh agent can pick up with zero prior context.
disable-model-invocation: true
---

# Handoff

Create self-contained task files that a fresh agent session can pick up with zero prior context.

The receiving agent will not have the current conversation, session state, or reasoning accumulated during this session. Treat this as a compression step: preserve the minimum information that maximizes the next agent's chance of succeeding immediately.

## Process

### 1. Gather Context

From the conversation, extract:

- **Objective**: the concrete work to be done
- **Current state**: what is already true right now
- **What was tried**: approaches attempted and why they did not work
- **Decisions made**: choices already settled in this session
- **Open questions**: anything unresolved that the next agent must validate
- **Key files**: the specific files involved, with paths from repo root
- **External refs**: GitHub issues, Figma links, URLs, docs
- **Technical findings**: useful discoveries (payload shapes, library versions, root cause hypotheses, relevant source locations)

### 2. Create the Task File(s)

**Place task files in the target repository** — the repo where the work will be done, which may differ from the current workspace. Example: if the work lives under `~/code/frontend-app/`, the handoff file goes in `~/code/frontend-app/tasks/`, not in the current workspace’s `tasks/` folder.

```bash
mkdir -p <target-repo>/tasks
```

File path: `<target-repo>/tasks/<descriptive-kebab-case-name>.md`

If the session produced multiple independent work items, create a separate file for each.

Use the template below. Skip sections that have no content.

```markdown
> When the task is complete, move this file to `tasks/done/` instead of deleting it. See "On completion" below.

# <Clear title describing the work>

## References

- [GitHub issue](https://github.com/...)
- [Figma](https://figma.com/design/...)

## Objective

What must the next agent accomplish.

## Current State

What is already known to be true. Include confirmed facts, current behavior, relevant file paths from repo root, and important discoveries.

## Constraints & Decisions

Known constraints, product decisions, and choices already settled. The next agent should not re-decide these without revalidation.

## What Was Tried

Approaches attempted and why they failed. Prevents the next session from repeating dead ends.

- **Approach 1**: [what] — [why it failed]

## Open Questions

Anything the next agent still needs to verify or decide.

## Acceptance Criteria

How to verify the work is complete.

## First Actions

The first 3-5 concrete steps the next agent should take.
```

### 3. On Completion — Archive, Don't Delete

When the task is finished (or abandoned with a clear outcome), **move** the file into an archive folder rather than deleting it. This preserves the brief so you can retry from scratch if the "done" turned out to be wrong, and keeps a searchable record of past work.

```bash
mkdir -p <target-repo>/tasks/done
mv <target-repo>/tasks/<name>.md <target-repo>/tasks/done/<name>.md
```

Optional but recommended:

- **Date-prefix on move** to avoid collisions with future tasks of the same name: `tasks/done/YYYY-MM-DD-<name>.md`.
- **Append a short `## Completion` section** to the file before moving it, noting date and outcome (e.g. "merged in PR #123", "blocked on X", "superseded by tasks/<other>.md"). Makes `done/` searchable without reading chat history.

### 4. Confirm with the User

Show the created file path(s) and a brief summary. Tell the user to start a fresh chat in the same project and attach the file:

```
@tasks/<name>.md execute this task
```

Don't do any other work — the skill's only job is to produce the task file(s).

## Guidelines

- **Self-contained**: A fresh agent with no conversation history must understand the task fully from the file alone.
- **Zero-memory recipient**: Assume the next agent knows nothing except what is written in the file and what it can inspect in the codebase.
- **Concise**: No filler. Every sentence should carry information the next agent needs.
- **Paths from repo root**: Use `src/foo/bar.ts`, not relative or absolute paths.
- **Code snippets sparingly**: Only when they illustrate something non-obvious. Don't paste entire files.
- **Capture dead ends**: Failed attempts are often the most valuable part of a handoff.
- **Capture decisions**: If the session chose one approach over another, say so explicitly.
- **One task per file**: Don't combine unrelated work items. Create multiple files if needed.
- **Archive, don't delete**: Default completion is moving the file to `tasks/done/`. Deleting loses the brief if the "done" was wrong or you want to retry from scratch.
