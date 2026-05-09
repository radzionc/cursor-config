---
name: start-project
description: Bootstrap a project-scoped, throwaway project-memory skill at the start of a long, messy multi-session task. The user dumps everything they know; this skill writes a self-maintained context file to <repo-root>/.cursor/skills/project-<slug>/SKILL.md (gitignored, local-only) so future sessions in this repo can attach it as @skills/project-<slug> and the agent maintains it as work progresses. Use only when the user explicitly invokes this skill.
disable-model-invocation: true
---

# Start Project

Create a project-scoped, throwaway "project memory" skill that holds the agent's current understanding of a long-running task. The user attaches this memory in subsequent chats; the agent reads it for context and updates it as work progresses.

The created skill lives at `<repo-root>/.cursor/skills/project-<slug>/SKILL.md` — colocated with the work but **gitignored**, so it never enters version control. It is meant to be deleted (or harvested into proper rules/skills) once the task ships.

## When this is invoked

The user runs `@skills/start-project` and dumps unstructured context: goals, repos, files, prior attempts, hunches, links, frustrations. Treat that dump as the source material to distill. Do not start coding; the only output of this skill is the new SKILL.md (and a `.gitignore` line if missing).

## Process

### 1. Locate the target repo

Resolve the repo root:

```bash
git rev-parse --show-toplevel
```

If this fails (not inside a git repo), **stop and ask the user** for the absolute path of the target repo. Do not fall back to `~/.cursor/skills/` — project memory belongs with the project. If the user wants a non-repo destination, they can specify it explicitly.

Use this path as `<repo-root>` for the rest of the process.

### 2. Pick a slug

Derive a short kebab-case slug from the dump (e.g. `billing-rewrite`, `checkout-onboarding-v2`, `auth-migration`). Lowercase, hyphens, ≤ 30 chars. If ambiguous, ask the user once.

Final path: `<repo-root>/.cursor/skills/project-<slug>/SKILL.md`.

### 3. Ensure the path is gitignored

Project memory must never be committed. Before writing anything, verify the path is git-excluded:

```bash
git -C <repo-root> check-ignore .cursor/skills/project-<slug>/
```

If `check-ignore` exits non-zero (path is not ignored), append the following line to `<repo-root>/.gitignore` (create the file if missing):

```
.cursor/skills/project-*/
```

Use the narrow `project-*` glob — not the broader `.cursor/skills/` — so any team-committed skills the repo may already have at sibling paths remain trackable. After editing, re-run `check-ignore` to confirm exclusion.

### 4. Don't overwrite silently

If `<repo-root>/.cursor/skills/project-<slug>/SKILL.md` already exists, stop and ask: overwrite, append, or pick a new slug. Never clobber an existing memory file without consent.

### 5. Distill the dump

Extract from what the user said (and only from what they said — do not invent):

- **Scope** — the bounded task in 1–3 sentences
- **Repo & Surface** — repo path, branch, affected directories/files
- **Mental Model** — how the relevant slice of the system works
- **Decisions** — choices already settled, with brief rationale
- **Open Questions** — what's still uncertain
- **Dead Ends** — what was tried and didn't work, with why
- **Conventions** — codebase-specific patterns an outsider would miss
- **Glossary** — domain terms with their meaning in this context
- **Useful Commands** — how to run, test, inspect, deploy
- **External Refs** — links (issues, designs, docs)

If a section has no content from the dump, leave a one-line placeholder (e.g. `_None yet._`) so the maintaining agent has a clear slot to fill later. Sparse is fine — sections fill in over time.

### 6. Write the file

Create the directory and write `SKILL.md` using the template below. Substitute `<slug>`, `<one-line scope>`, and the distilled content. Preserve the **Maintenance Protocol** section verbatim — it is how the file stays useful.

```bash
mkdir -p <repo-root>/.cursor/skills/project-<slug>
```

Template:

````markdown
---
name: project-<slug>
description: Project memory for <one-line scope>. Local, throwaway context skill — current understanding, decisions, open questions, and pitfalls discovered while working on this multi-session task. The agent that reads this is responsible for keeping it accurate.
disable-model-invocation: true
---

# Project Memory: <Project Name>

> **You (the agent) maintain this file.** When this skill is attached to a conversation, treat the contents below as the authoritative current understanding of the task. As you learn new things — make decisions, hit dead ends, map files, discover conventions — update the relevant sections **before your final response**. See "Maintenance Protocol" at the bottom.

_Last updated: <YYYY-MM-DD>_

## Scope

<One-to-three sentences describing the bounded task.>

## Repo & Surface

- **Repo**: `<absolute path>`
- **Branch**: `<branch>`
- **Affected areas**: `<paths/dirs/files>`

## Mental Model

<How the relevant slice of the system works. Update as understanding deepens.>

## Decisions

- <YYYY-MM-DD>: <decision> — <rationale>

## Open Questions

- [ ] <question>

## Dead Ends

- <approach> — <why it failed>

## Conventions

<Codebase-specific patterns, naming, idioms an outsider would miss.>

## Glossary

- **<term>**: <meaning in this context>

## Useful Commands

```bash
# <description>
<command>
```

## External Refs

- <link> — <what it is>

---

## Maintenance Protocol

This file is the working memory for a multi-session task. It only stays useful if the agent that reads it also writes to it.

1. **Update before your final response.** Whenever the conversation produced new understanding — a decision, a dead end, a mapped file, a learned convention, a resolved question — edit the relevant section here before replying to the user.
2. **Be additive, then compress.** Append new entries, but rewrite sections that have grown bloated. Target the whole file ≤ 300 lines.
3. **Resolve, don't accumulate.** When an Open Question is answered, delete the question and fold the answer into Mental Model or Decisions. When a Dead End becomes irrelevant, remove it.
4. **Distill, don't dump.** No verbatim error messages, no chat residue. Compress to a sentence the next agent can act on.
5. **Capture what would surprise a fresh agent.** Skip anything obvious from reading the codebase. Keep what required investigation, conversation, or trial-and-error to learn.
6. **Bump the timestamp** at the top after each meaningful update.
7. **Local-only.** This file is gitignored and must stay that way. Never propose moving it into a tracked path, a rule, or a shared skill without the user explicitly asking.
8. **Throwaway by design.** When the task ships, the user will delete this file or harvest pieces of it into proper rules/skills. Don't optimize for permanence.
````

### 7. Confirm

After writing, tell the user:

- Full path of the created file
- How to use it next session: `@skills/project-<slug> <your task>` (from within the same repo)
- That the file is gitignored and local-only
- Whether `.gitignore` was modified (and that *that* change is itself a tracked file — they can commit the ignore line if they want; the memory file itself will not be committed)
- That future agents will maintain it automatically when it's attached

Do not do any other work in this invocation. The skill's only job is to produce the seeded memory file (and ensure the ignore rule).

## Guidelines

- **First-principle goal**: produce a file that a fresh agent in a future session can read and immediately be productive. Optimize the template for that one moment.
- **Don't fabricate content.** If the dump is sparse, the file is sparse. Empty placeholders signal "to be filled" — invented content poisons the memory.
- **Always write `disable-model-invocation: true`** on the created skill. It must only activate when the user explicitly attaches it.
- **Never write to `~/.cursor/skills/` or `~/cursor-config/skills/`.** Project memory is repo-scoped. The path is always `<repo-root>/.cursor/skills/project-<slug>/`.
- **Verify the gitignore exclusion** before writing — once. Don't skip it on the assumption that the repo "probably" ignores `.cursor/`. Many repos commit `.cursor/rules/` and `.cursor/skills/` intentionally.
- **Preserve the Maintenance Protocol verbatim.** It is the contract that makes the rest of the system work; rewording weakens it.
