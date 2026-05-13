---
name: done
description: >-
  Finish the current work through the project-local finish workflow, then capture high-signal improvement tasks for future AI autonomy, tooling, QA, and code quality. Use when the user explicitly invokes `/done` or asks to wrap up a completed session and reflect on what should improve next.
disable-model-invocation: true
---

# Done

Finish the current work, then think for the future. This skill is explicit session teardown: ship through the project's local finish policy, then create or enrich only the improvement notes that would make future agent work materially better.

Do not use this for ordinary unfinished work. Use `handoff` when the goal is only to preserve an implementation task for a fresh session.

## Principles

- **Local finish owns shipping**: if `.cursor/skills/finish/SKILL.md` exists, read it and delegate that workflow exactly. Do not copy PR, commit, Linear, CI, or merge policy into this shared skill.
- **Reflect from the AI's pain**: capture what slowed agents down, increased risk, or made quality depend on luck.
- **Sparse backlog**: zero improvement files is a valid outcome. Create files only when the issue is worth a future session.
- **Evidence over taste**: prefer concrete session signals over generic refactors or "clean code" notes.
- **Cost evidence over guilt**: only create model-spend improvements when the session shows avoidable expensive-model work and a practical cheaper path.
- **Parent owns improvement files**: the finish subagent ships the branch and reports signals; only the parent creates or enriches `tasks/improve-*.md` after finish returns.

## Workflow

### 1. Start Finish

If `.cursor/skills/finish/SKILL.md` exists in the target repo:

First verify this with a direct exact-path read of `<target-repo>/.cursor/skills/finish/SKILL.md`. Do **not** use a root-level glob or search to decide whether it exists: many repos gitignore `.cursor/`, and ignore-respecting search tools can hide the local finish skill even though `ReadFile` and the eventual subagent can read it. If an exact-path read succeeds, the local finish skill exists.

1. Launch a `generalPurpose` subagent with `model: "composer-2"`.
2. Tell it to read `.cursor/skills/finish/SKILL.md`, follow it exactly, and avoid shortcuts that contradict the local finish policy.
3. Require this return format:

```markdown
## Finish Outcome

PASS | BLOCKED | NOTHING_TO_FINISH

## Shipping Details

- Branch:
- PR:
- Merge/check/review status:
- Local checkout state:

## Retrospective Signals

- [Specific pain, blocker, repeated step, missing tool, unclear project convention, or none]
```

Use the subagent because finish can be long-running and retry-heavy. This follows the essential `orchestrate` rule: built-in subagents get `model: "composer-2"`.

If the local finish skill is missing, do not invent a generic PR flow. Record `Finish Outcome: BLOCKED (missing local finish skill)` and continue only with retrospective capture if the session provides useful signals.

### 2. Reflect While Finish Runs

From the parent session context, list candidate improvements across these categories:

- **ai-infra**: missing or weak rules, skills, agents, hooks, project QA docs, or MCP setup.
- **tooling**: scripts, CLI helpers, browser/email/wallet/test tooling, diagnostics, or automation that would have removed manual or repeated work.
- **project-qa**: missing test accounts, canonical URLs, fixtures, QA steps, seeded states, or verification paths.
- **code-quality**: duplication, confusing contracts, brittle module boundaries, missing shared components, or unsafe patterns noticed while working.
- **workflow**: handoff gaps, costly context discovery, branch/PR friction, or subagent prompts that lacked needed context.
- **cost-control**: avoidable main-model usage, context bloat, missing `composer-2` delegation, repeated high-token discovery, or tooling gaps that forced expensive-model work.

Include subagent experience when available. If a finish, QA, code-review, or implementation subagent reports friction, treat that as first-class evidence.

For cost-control candidates, use observable evidence from the session instead of trying to reconstruct exact billing unless usage data is already available. Examples of strong evidence:

- Broad exploration, multi-file edits, retry loops, long-running checks, or log-heavy debugging stayed in the parent when a `composer-2` subagent could have owned the bulk work.
- A built-in subagent was launched without `model: "composer-2"` or a custom agent was overridden with an explicit expensive model.
- Large files, transcripts, terminal logs, screenshots, or generated outputs were repeatedly read into the parent without narrowing, summarizing, or delegating.
- A missing script, MCP, fixture, QA doc, or project reference forced repeated manual discovery that would recur across future sessions.

Reject cost-control candidates when the only evidence is that the main model was used, when delegation overhead would have exceeded the saved context, when no practical cheaper workflow is clear, or when the issue is already solved by following `orchestrate`.

### 3. Filter Hard

Create an improvement item only when at least one is true:

- It would likely save meaningful future model time or user money.
- It would prevent a class of product regressions or missed QA.
- It exposes missing AI infrastructure: rule, skill, hook, agent, MCP, script, or project QA doc.
- It captures project/code context a fresh agent would otherwise rediscover expensively.

Reject:

- Generic refactors, style preferences, naming opinions, and obvious best practices.
- Vague "clean this up" notes without concrete evidence.
- One-off pain unlikely to recur.
- Items that would be better fixed immediately inside the current task and are still in scope.

Usually create 0-3 items. More than 3 means the candidates need stricter filtering or consolidation.

### 4. Choose Create vs Enrich

Use `tasks/improve-<descriptive-slug>.md` in the right destination repo:

- **Project-specific** issues stay in the target repo: product code contracts, project QA fixtures, local tooling, unclear domain behavior, or repo-specific finish friction.
- **Generic AI workflow** issues go in the shared cursor-config repo: reusable rules, skills, agents, hooks, MCP setup, orchestration discipline, context-management patterns, or model-spend optimizations that apply across projects. Read `~/.cursor/.cursor-config-source` to locate this repo when needed.

Write or append improvement files only after the finish subagent returns. Local finish workflows may commit, push, merge, switch branches, or update `main`; treat the post-finish repo state as the source of truth.

Search existing improvement files in the chosen destination first:

```bash
rg -n "<core keyword>|<related module>|<tool name>" <destination-repo>/tasks/improve-*.md
```

- If an existing file describes the same underlying problem, append a new `## Observation - YYYY-MM-DD` section with the current evidence.
- If the problem is meaningfully different, create a new file.
- If the evidence is weak, create nothing and mention that no improvement item cleared the bar.
- If no `tasks/improve-*.md` files exist yet, treat the search as empty and create a new file only if the candidate passes the filter.

### 5. Improvement File Template

Use this template. Skip sections with no useful content.

```markdown
> When this improvement is complete, move this file to `tasks/done/` instead of deleting it.

# <Improvement title>

## Category

ai-infra | tooling | project-qa | code-quality | workflow | cost-control

## Pain

What was slow, fragile, repetitive, confusing, or quality-degrading in the completed session.

## Evidence

Concrete observations from this session: files, commands, failing checks, subagent reports, repeated searches, unclear APIs, duplicated code, missing docs, missing tools.

## Why It Matters

How this would reduce future tokens, prevent regressions, improve autonomy, or keep the codebase healthier.

## Suggested Direction

Optional. Include only if the likely fix is clear; otherwise state what a future agent should investigate.

## Constraints

Relevant existing rules, skills, project conventions, or reasons not to overbuild.

## Acceptance Criteria

How a future agent knows the improvement is complete.

## First Actions

The first 3-5 concrete steps for the future agent.
```

For recurring issues, append:

```markdown
## Observation - YYYY-MM-DD

- Context:
- New evidence:
- Why this reinforces the existing improvement:
```

## Relationship To Other Skills

- Use `orchestrate`'s model discipline for the finish subagent: built-in subagents get `model: "composer-2"`.
- Use `handoff` for ordinary unfinished product tasks. Use `done` improvement files for future quality, autonomy, and tooling work discovered after finishing a session.
- Use `improve` later to turn one `tasks/improve-*.md` issue into a persistent rule, skill, agent, hook, tool, or code change.
- Use `review-config` standards when proposing AI infrastructure changes: the artifact must solve a real problem, be scoped correctly, and earn its token cost.
- Obey `quality-gates` before claiming implementation work is complete. `/done` does not excuse skipped tests, checks, review, or QA when those gates apply.

## Final Response

Keep the closeout short:

- Finish outcome: merged, ready, blocked, or missing local finish.
- Improvement files created or enriched, with paths.
- If no files were created, say no improvement candidate cleared the bar.
- Any blocker that needs the user.
