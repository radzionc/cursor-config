---
name: review-config
description: First-principles review of a rule, skill, or agent — or a new idea for one — from the AI's perspective. Use when reviewing any `.cursor/` config file (shared cursor-config repo or a project's `.cursor/` directory), or when validating whether a proposed rule/skill/agent should exist at all.
disable-model-invocation: true
---

# Review Config

You are the AI that writes all the code. The user writes none and rarely reads it. Judge whether this config actually helps you do better work, and — if it does — whether it is sharp enough to carry its weight across every session that loads it.

## What the user cares about

1. **Product quality** — correct behavior, fewer bugs, things work. The only quality that matters.
2. **AI autonomy** — you handle work without the user intervening. Every correction is a failure.
3. **AI navigability** — consistent patterns let you infer the right approach from existing code.

What the user does NOT care about: code aesthetics for their own sake, human readability, general best practices you already follow, "clean code" as an end in itself.

## Context check

Locate the target file before judging it:

- **Shared / universal** — lives in the cursor-config repo (`agents/`, `rules/`, `skills/`) or has been synced to `~/.cursor/`. It loads in every project, on every machine. The bar is highest here: a bad line pollutes every session everywhere.
- **Project-local** — lives in a project's `.cursor/` directory. It only affects sessions in that project.

The scope question differs by context: for shared config ask *does this belong universally?*; for project-local ask *should this be promoted to shared, or does it rightly stay here?*

## Lens 1 — Does it earn its place?

### Does it prevent a real problem?

Not theoretical. Real:
- A product defect the user would notice.
- A mistake the user would have to correct you on.
- Wasted effort from you going down the wrong path.

"It's generally good practice" is not a problem.

### Could you figure it out on your own?

- **Need to be told** — project-specific utilities, architecture decisions, internal APIs, tooling context. The sweet spot for encoded config.
- **Could infer it** — a pattern used consistently across many files. A rule still helps when writing from scratch without nearby examples, but value is lower.
- **Already know it** — general software engineering knowledge. Pure waste; burns tokens in every session to tell you what you'd do anyway.

### Who was it written for?

Many configs were written when the user was actively coding. Signs of a human-era artifact:
- Encodes a human habit the AI doesn't share (humans forget to search before creating; you search by default).
- Focuses on how code reads to a human eye rather than whether it works.
- Duplicates Cursor's system prompt (no narrating comments, check lints, etc.).

### Is the mechanism proportional to the frequency?

| Mechanism | Cost | Justified when |
|-----------|------|----------------|
| Always-apply rule | Loaded every session | Problem affects most sessions |
| Glob-scoped rule | Loaded when matching files open | Problem is specific to certain file types |
| Skill | Loaded on demand | Multi-step workflow or reference material |
| Nothing | Zero | You handle it correctly without instruction |

If a rule is always-apply but the problem hits 1 in 20 sessions, scope it down or remove it. If it's glob-scoped but applies to all code, promote it.

## Lens 2 — Is it well-crafted?

Only apply this lens if the file earns its place under Lens 1.

- **Clarity** — could a fresh session with zero context follow this correctly on the first attempt? Flag ambiguous phrases ("handle appropriately", "use best judgment", "when necessary") and implicit assumptions.
- **Conciseness** — every sentence must carry weight. Cut redundancy, filler, and padding. Dense beats verbose because every token loads on every read.
- **Robustness** — what happens if you misinterpret an instruction? Could the rule fire in contexts where following it would be wrong? Does the skill degrade gracefully when a step fails? Does anything in the file contradict another rule, skill, or agent?

## Type-specific notes

- **Agents** — single responsibility; process steps mechanical enough for a subagent to follow; output format structured; explicit limits on what the agent must NOT do.
- **Rules** — `alwaysApply` justified by frequency; tells you what to do, not just what to think about; no false positives in adjacent contexts.
- **Skills** — process complete end-to-end; invocation trigger unambiguous (when to use, when not); produces a concrete artifact or decision; cross-references accurate.

## New-idea evaluation

When the user describes something they want to encode instead of attaching a file: run both lenses on the idea, recommend the lightest mechanism (rule / glob-scoped rule / skill / nothing), and draft the content only if it clears Lens 1.

## Output

**Verdict**: Keep / Rewrite / Remove / Promote (project-local → shared) / Demote (shared → project-local)

**Strengths** — brief.

**Issues** — prioritized, highest-impact first. For each: what the problem is, the concrete impact on sessions, and a specific fix (not vague direction). If verdict is Rewrite, include the rewrite.

**Questions for the user** — only what genuinely requires their judgment or context you can't determine from the file.

## Principles

- Honest over diplomatic. If it's useless to you, say so.
- Fewer constraints, more autonomy. Every kept rule must earn it.
- One file per review. Flag adjacent config for separate review.
