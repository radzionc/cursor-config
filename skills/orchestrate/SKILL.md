---
name: orchestrate
description: Pure orchestration mode — delegate bulk/high-token work to cheaper subagents while keeping tiny overhead-dominated edits in the parent.
disable-model-invocation: true
---

# Orchestrate

You're on an expensive model. Subagents on `composer-2` run for ~10× less per token. Route bulk work through them; keep judgment, planning, and synthesis on yourself.

## Model arg — the only real safeguard

Cursor doesn't reliably block expensive subagents at the hook level, so the discipline is on you. Pass the right model on every Task call:

- **Built-in subagent** (`shell`, `explore`, `generalPurpose`, `browser-use`, `best-of-n-runner`) → `model: "composer-2"`.
- **Custom agent** (anything in `agents/` — `code-reviewer`, `qa`, etc.) → **omit** `model`. The frontmatter sets `composer-2`; passing the arg overrides it.

`"fast"` is silently ignored on built-ins — they inherit the parent. Verified empirically.

## What goes where

Delegation has a fixed setup cost (prompt with full context, parsing the return). Pick by **total token weight**, not principle.
When patch size and token weight disagree, bias toward delegation if the parent would need substantial reading, testing, or retry loops to do the edit safely.

- **Parent owns judgment**: ticket interpretation, architecture choices, acceptance criteria, task split, review triage, and final synthesis.
- **Delegate bulk implementation by default**: multi-file edits, migrations, refactors, tests plus implementation, retry-prone type/lint fixes, long-running commands, and anything likely to take more than a few small patches.
- **Direct edits are exceptions**: a one-line fix, a small single-file change you can make faster than prompting a subagent, prompt/plan artifacts, or a tiny review fix where delegation overhead would dominate.

When this skill is in context because the user invoked `/orchestrate` or equivalent, implementation work is delegated unless it fits one of the direct-edit exceptions. Before editing files yourself, ask: **is this small enough that subagent prompt overhead exceeds the edit?** If not, delegate.

## Implementation handoff packet

For bulk edits, launch `generalPurpose` with `model: "composer-2"` after you have enough context to give a precise packet. Use `best-of-n-runner` with `model: "composer-2"` only for isolated alternatives or risky experiments that benefit from a separate worktree.

Include:

- Goal and acceptance criteria
- Exact file/path scope and files that must not be touched
- Relevant project rules or constraints
- Current branch/worktree state and known dirty files
- Tests/checks to run, with expected outcomes
- Required return format: changed files, commands run, failures, open questions

If a subagent returns vague results, resume that subagent for specifics. Do not silently take the work back into the expensive parent unless the remaining edit is tiny.

## Verification

Verification is sometimes essential — don't skip it when quality is at stake. But don't redo work the subagent already did. If a return is vague, **ask the subagent** for specifics. If you genuinely need independent eyes, spawn a **fresh subagent** for it. Run agreed checks yourself when needed, but don't re-audit implementation line-by-line in the parent.

## Process

Explore in parallel → plan with todos → delegate implementation → synthesize → delegate review/QA → re-delegate fixes on failure (one retry max). Recurrent escalation on a task type → create a custom agent in `agents/`.

For review findings, keep the same split: the parent decides which findings are real; a `composer-2` implementation subagent applies non-trivial fixes and reruns targeted checks.
