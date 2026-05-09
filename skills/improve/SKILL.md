---
name: improve
description: Targeted AI workflow improvement. Investigate a specific issue the user has noticed and implement the right persistent fix (rule, skill, agent, hook, or config change). Use when the user identifies a concrete problem in how the agent operates and wants it resolved.
disable-model-invocation: true
---

# Improve

Take a specific AI workflow issue and implement the right persistent fix. The user describes what went wrong; this skill investigates, selects the lightest mechanism, and ships the solution.

**Run in Agent Mode.** This skill implements changes — it does not just produce a plan.

## Philosophy

The agent starts every session from zero. The ONLY way interactions improve is through persistent artifacts: rules, skills, subagents, hooks, and reference documents. This skill turns a single observation into a concrete, implemented improvement.

**One issue per invocation.** If the user mentions multiple issues, pick the most impactful one and note the rest for follow-up. Deep focus on one issue beats shallow passes on several.

## Process

### Step 1: Understand the Issue

Parse the user's description. Identify:

- **What went wrong** — the concrete failure or friction
- **When it happened** — the context (which task, which codebase, which workflow)
- **How often** — one-off vs recurring pattern

If the user references a past session, read the transcript from the agent-transcripts path provided in system context.

If the issue is too vague to act on, ask **one** focused clarifying question before proceeding. Don't ask multiple questions — pick the one that most constrains the solution space.

### Step 2: Research Existing Config

Before creating anything, understand what already exists.

1. **Read `~/.cursor/skills/cursor/cursor-features.md`** — internalize the available mechanisms and their trade-offs.
2. **Locate the cursor-config repo** — read `~/.cursor/.cursor-config-source` for the repo path. If the file doesn't exist, fall back to `~/.cursor/`.
3. **Browse existing config** — list `agents/`, `rules/`, `skills/` in the cursor-config repo. Read any files that seem related to the issue.
4. **Check project-local config** — if the issue is project-specific, also check the current project's `.cursor/` directory.
5. **Search for overlap** — if an existing rule, skill, or agent partially addresses the issue, prefer modifying it over creating something new.

### Step 3: Choose the Mechanism

Use the **Retrospective Decision Matrix** in `cursor-features.md` to map the issue signal to candidate mechanisms. When multiple mechanisms could work, apply this preference order:

1. **Modify existing config** — if something already covers adjacent ground, extend it
2. **Rule** — agent keeps making the same short, correctable mistake
3. **Skill** — multi-step workflow or domain knowledge needs encoding
4. **Subagent** — work needs independent context or verification
5. **Hook** — quality check must happen automatically, not by instruction
6. **Code change** — the issue is structural (confusing naming, duplication, missing types) and no amount of AI config fixes the root cause

If the issue doesn't warrant any persistent artifact (one-off, already handled, or the agent would get it right with a simple prompt), say so and stop. Not every issue needs a fix.

### Step 4: Determine Scope

Assign a scope to each artifact:

- **Shared** — universally useful across any project, machine, or organization. Implement in cursor-config repo, then sync.
- **Project-local** — specific to this project's codebase, conventions, or domain. Implement in the project's `.cursor/`.
- **Machine-local** — specific to this machine's setup. Implement in `~/.cursor/` directly (not in cursor-config).

### Step 5: Implement

Create or modify the artifact:

- **For new rules** — follow conventions from the `create-rule` skill
- **For new skills** — follow conventions from the `create-skill` skill
- **For shared config** — edit in the cursor-config repo (per `cursor-config-editing` rule), then run `bash <repo-path>/sync.sh` from the repo root
- **For modifications** — read the existing file thoroughly before editing; preserve its structure and conventions

### Step 6: Verify

- **For shared config** — read `~/.cursor/skills/review-config/SKILL.md`, then follow its process to review the artifact you created or modified
- **Quality gates** — the always-apply quality-gates rule handles tests, checks, and code review automatically

### Closing Summary

After implementation, provide a brief summary:

- **Issue**: what was addressed
- **Fix**: what was created or modified (file paths)
- **Scope**: shared / project-local / machine-local
- **Deferred**: any related issues noted for follow-up (if any)

## Guidelines

- **Lightest mechanism first** — a rule is lighter than a skill, a skill is lighter than a subagent. Don't over-engineer.
- **Modify over create** — extending an existing rule or skill avoids config sprawl and keeps related guidance together.
- **Guard against rule accumulation** — before creating a rule, ask: "Would this recur in at least 1 in 10 sessions?" If not, it's a rare edge case. Prefer a note in an existing skill or nothing at all.
- **Dense over verbose** — every token in a rule or skill costs context in future sessions. Cut padding ruthlessly.
- **Evidence over theory** — ground the fix in the concrete issue. "This would have prevented the mistake in [session]" beats "This is generally good practice."

## Related Skills

- `~/.cursor/skills/cursor/cursor-features.md` — mechanism selection knowledge
- `prep-improve` — extracts issue context to clipboard so this skill can run in a fresh session with a smarter model
- `review-config` — first-principles review of whether a rule, skill, or agent earns its place
