---
name: port
description: Port files between workspaces. Manually invoked — user attaches source content and this skill adapts and applies it to the current workspace.
---

# Port

Move attached content into the current workspace, stripping anything that doesn't belong here.

The current workspace is always the **destination**. The user attaches source files, pastes content, or points to a folder. This skill adapts that content so it fits the destination — correct paths, no leaked references, no foreign terminology.

## Workflow

### 1. Understand source and destination

The user attaches one or more files or pastes content. For each item, determine:

- **What it is**: skill, rule, agent config, code file, reference doc, etc.
- **Where it goes**: infer the target path from the destination workspace's directory structure. Look at existing files for the convention — don't assume a fixed layout. If ambiguous, ask the user.

### 2. Find existing version

Search for the corresponding file in the current workspace. If it exists, read it and note differences — the port should merge with or replace the existing content, not blindly overwrite local structure.

### 3. Adapt

This is the core of the skill. Source content carries context from where it came. Strip or rewrite anything that doesn't belong in the destination.

**Mechanical references** — find and fix:

- Absolute paths pointing to the source machine or project
- Repository references (org/repo names, branch names, remote URLs)
- Hardcoded secrets or tokens — strip, never carry over
- Imports or code references to files that don't exist in the destination — remove with a `TODO(port)` noting what's missing
- Tool or dependency references not available here — flag if critical

**Semantic contamination** — harder to catch, more damaging:

- **Project-specific terminology**: names of services, features, teams, internal tools, or domain concepts that only exist in the source project. Generalize or remove. ("after deploying the widget service" → remove or replace with a generic description)
- **Assumed context**: instructions that only make sense if you know the source project's architecture, conventions, or tech stack. Rewrite to be self-contained.
- **Examples tied to the source**: code samples, file paths in examples, or screenshots referencing source-specific content. Replace with equivalent examples that make sense in the destination, or make them generic.

**When the destination is a shared/universal config repo** (like `cursor-config`), apply extra scrutiny: the content must work for any project, any org. Strip everything project-specific — don't just rename it, remove it or generalize it. Check the repo's README for what belongs and what doesn't.

When unsure whether a reference applies, keep it but add an inline `TODO(port)` comment so the user can review.

### 4. Validate

Before writing, verify the adapted content against the destination:

- Read peer files in the same directory — does the ported content match their conventions (frontmatter, structure, tone, naming)?
- Scan the result one more time for source-specific language that slipped through step 3.
- If the destination file already exists, confirm the merge preserves local customizations that don't conflict.

### 5. Apply

- **File exists**: show a diff summary of what changed, then apply. Prefer surgical edits over full rewrites when the change is small relative to the file.
- **File is new**: create the file at the determined target path.
- **Multiple files**: process each independently through steps 1–4.

### 6. Report

After applying, output a concise summary:

```
Ported:
- <target-path> (updated | created) — <1-line description>
  - Adapted: <list of reference adjustments>
  - TODO(port): <items needing manual review>
```

Omit the Adapted or TODO lines if there are none.

## Guidelines

- **Destination context is king.** Every decision — paths, naming, terminology, structure — should be driven by what already exists in the destination workspace.
- Never carry over secrets, tokens, or credentials.
- When the source removes content that exists locally, apply the removal — don't only add.
- Preserve local customizations that don't conflict with the incoming change. When both sides modified the same section, prefer the incoming version but flag the conflict in the report.
- If the attached content is a diff/patch rather than a full file, apply it as a patch.
- When porting multiple related files, check for cross-references between them — adapt those too.
