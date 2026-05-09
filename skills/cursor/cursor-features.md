# Cursor AI Features — Agent Operating Knowledge

The agent's operational knowledge of Cursor features it uses directly in a session: files it creates, tools it invokes, response formats it produces. Human-only features (UI layout, keyboard shortcuts, click/drag interactions, dashboard configuration) are excluded — the agent cannot invoke them, so tracking them is noise.

**Last synced**: v3.2 (2026-04-30)

---

## The Toolkit

```
Rules ──────────→ Skills ──────────→ Subagents
Always present    Loaded on demand   Own context window
```

Choose the lightest mechanism that solves the problem. A rule is lighter than a skill. A skill is lighter than a subagent.

---

## 1. Rules (`.cursor/rules/*.mdc`)

Persistent instructions injected into a session as static context. Markdown files with YAML frontmatter.

### Activation Modes

| Mode                | Loaded                          | Use When                                              |
| ------------------- | ------------------------------- | ----------------------------------------------------- |
| Always Apply        | Every conversation              | Non-negotiable standards that apply everywhere        |
| Apply Intelligently | Agent decides from description  | Patterns that apply to most but not all work          |
| Glob-based          | Only when matching files open   | File-type specific conventions                        |
| Manual (@-mention)  | Only when explicitly referenced | Reference material rarely needed                      |

### When to Create
- A project-specific correction was repeated multiple times
- A convention had to be restated across files
- The correction is short and focused

### When NOT to Create
- One-off correction
- Linter-enforceable pattern
- Long multi-step procedure (use a Skill)
- General software knowledge the agent already has

### Anti-patterns
- Many always-on rules competing for attention
- Documenting the obvious
- Duplicating what a linter already enforces

---

## 2. Skills (`.cursor/skills/<name>/SKILL.md`)

On-demand procedures the agent discovers by description and loads when the trigger matches. Markdown files with YAML frontmatter.

Setting `disable-model-invocation: true` turns a skill into an explicit slash command (`/skill-name`). This replaces the deprecated Commands feature.

### When to Create
- Multi-step workflow repeated across sessions
- Domain knowledge that had to be re-explained
- A specialized review or analysis process worth standardizing

### Design Principles
- **Description decides loading** — write it from the agent's perspective: "Use when [specific trigger]."
- **Procedural, not narrative** — checklist with decision branches, not prose.
- **Reference, don't duplicate** — point to files in the codebase rather than copying them; skills that copy code go stale.

---

## 3. Subagents (`.cursor/agents/*.md`, invoked via `Task`)

Specialized assistants running in isolated context windows. The parent delegates work and receives only a summary. Custom subagents are Markdown files with YAML frontmatter.

### The Problem They Solve
Complex tasks generate massive intermediate output (search results, logs, snapshots) that fills the parent's context. Subagents isolate that noise: fresh context, autonomous work, concise summary back.

### Key Constraints
- Subagents start with zero history — the parent must pass all relevant context explicitly in the prompt.
- Run synchronously (parent waits) or asynchronously (parent continues, uses `Await` to poll).
- Background subagents can be resumed by passing the agent ID.
- **Multitask** (`/multitask`, Agents Window): parallelizes work across async subagents instead of only queueing; large jobs can be split for a fleet; queued messages can be multitasked without waiting for the current run to finish.

### Model Configuration
Set `model` in YAML frontmatter (e.g., `model: composer-2`). The frontmatter is the single source of truth — never pass `model` on the Task call; it overrides frontmatter. Valid values: `fast`, `inherit`, `default`, or a specific model ID.

Custom model configuration only takes effect in Max Mode or on usage-based billing. Otherwise subagents silently fall back to Composer.

### When Subagent vs Skill vs Rule

| Need                                      | Use                 |
| ----------------------------------------- | ------------------- |
| Long research that would bloat context    | Subagent            |
| Independent verification (fresh eyes)     | Subagent (readonly) |
| Parallel workstreams                      | Subagent (async)    |
| Step-by-step procedure for the main agent | Skill               |
| Repeated project-specific mistake         | Rule                |

### Anti-patterns
- Vague descriptions ("Use for general tasks") give the parent no signal for delegation.
- Using a subagent where a skill would do — the startup overhead isn't justified.

---

## 4. Hooks (`.cursor/hooks.json`)

Scripts that intercept agent lifecycle events. Each script receives JSON on stdin and responds via exit code or structured output.

### Exit Codes
- `0` — allow the action
- `2` — block the action
- `followup_message` (stop hook only) — keep the agent working

### Lifecycle Events

| Event                  | When                          | Use Case                               |
| ---------------------- | ----------------------------- | -------------------------------------- |
| `beforeReadFile`       | Before agent reads a file     | Block access to sensitive files        |
| `afterFileEdit`        | After agent edits a file      | Auto-lint, auto-format, validate edits |
| `beforeShellExecution` | Before running shell commands | Block dangerous commands               |
| `stop`                 | When agent task completes     | Quality gates, autonomous loops        |

Multi-root workspaces read hook files from all workspace folders, not just the first. In the Agents Window, a session can target a reusable multi-root workspace (multiple folders) so cross-repo edits run in one session without retargeting per repo.

### The Autonomous Agent Loop

The `stop` hook can return a `followup_message` that re-prompts the agent, creating a loop:

```
Agent finishes → stop hook → goal met?
  No: return followup_message → agent continues
  Yes: return empty → agent stops
```

Use cases: iterate until tests pass, refine until output matches a target.

Example `hooks.json`:

```json
{
  "version": 1,
  "hooks": {
    "stop": [{ "command": "bun run .cursor/hooks/grind.ts" }],
    "afterFileEdit": [{ "command": "./scripts/lint-check.sh" }]
  }
}
```

### When to Create
- Quality checks forgotten during sessions (lint, typecheck, test)
- Agent marks work done prematurely
- A validation that should always run automatically

---

## 5. Agent Modes

The mode changes which tools are available and how the agent approaches the task. The agent can switch modes via the `SwitchMode` tool.

| Mode  | Approach                        | Tools                           | When                                                         |
| ----- | ------------------------------- | ------------------------------- | ------------------------------------------------------------ |
| Agent | Autonomous implementation       | All tools                       | Clear task, ready to build                                   |
| Plan  | Research and design first       | Read-only until plan approved   | Unclear requirements, multiple approaches, large scope       |
| Debug | Hypothesis-driven investigation | All tools + debug server        | Bugs, regressions, unexpected behavior                       |
| Ask   | Read-only exploration           | Search tools only               | Understanding code without making changes                    |

Plan Mode produces a reviewable Markdown plan. Plans can be saved to `.cursor/plans/` for resumable work.

Debug Mode instruments code, collects runtime evidence during reproduction, and makes targeted fixes based on evidence rather than guesses.

---

## 6. Canvases (`*.canvas.tsx`)

Interactive React artifacts the agent produces as a response. Canvases can include tables, boxes, diagrams, charts, dashboards, diffs, and to-do lists — rendered beside the chat as durable artifacts.

### When to Use
- Response is a standalone analytical deliverable (audit, investigation, review)
- Data-heavy content that benefits from visual layout
- Results from MCP tools where the data is the deliverable
- Avoiding a large markdown table or dumped code block

### When NOT to Use
- Simple textual answers
- Narrative explanations
- Short, ephemeral output

---

## 7. MCP (Model Context Protocol)

External tool integrations declared in `.cursor/mcp.json` — either a local stdio `command` or a remote `url` (SSE/HTTP). The agent invokes MCP tools like any other tool. MCP outputs support structured content, not just plain text.

### When to Add an MCP
- Agent needs data from an external system and built-in tools can't reach it
- A manual step could be automated with tool access (Figma, Linear, Datadog, Sentry, etc.)

---

## 8. Clarification Questions (`AskQuestion` tool)

The agent can ask the user structured questions while continuing to work. Err toward asking when an assumption would lead to rework; err toward autonomy when the answer is findable in code.

---

## 9. Plans (`.cursor/plans/*.plan.md`)

Saved Markdown plans produced in Plan Mode. The canonical handoff artifact for resuming work in a fresh session: the next session attaches the plan file instead of relying on chat history.

Old chats, exports, and pinned threads are reference material. The attached plan file is the source of truth for fresh-session execution.

---

## Prospective Decision Matrix

| Situation                                             | Feature                                |
| ----------------------------------------------------- | -------------------------------------- |
| Complex task with multiple valid approaches           | Plan Mode                              |
| Verify completed work independently                   | Subagent (readonly)                    |
| Workflow needs to be repeatable                       | Skill                                  |
| Quality check keeps being forgotten                   | Hook                                   |
| Repeated project-specific mistake                     | Rule                                   |
| Long research that would bloat context                | Subagent                               |
| Independent subtasks to run in parallel               | Async subagents, Multitask (`/multitask`) |
| External system access needed                         | MCP                                    |
| Reproducible bug resists normal fixing                | Debug Mode                             |
| Read-only exploration                                 | Ask Mode                               |
| Standalone analytical artifact or dashboard           | Canvas                                 |
| Resuming work from a previous session                 | Saved plan in `.cursor/plans/`         |

---

## Retrospective Decision Matrix

| Session Signal                                | Action                                    |
| --------------------------------------------- | ----------------------------------------- |
| Same mistake repeated                         | Create a Rule                             |
| Multi-step workflow repeated                  | Create a Skill                            |
| Research bloated the conversation             | Use a Subagent next time                  |
| Quality check forgotten                       | Create a Hook                             |
| Wrong thing built without asking              | Plan Mode or more clarification           |
| Trial-and-error debugging wasted time         | Debug Mode                                |
| Missing external tool access                  | Add an MCP                                |
| Context filled, fresh chat needed             | Save a plan to `.cursor/plans/` first     |
| Large markdown table or data dump produced    | Use a Canvas next time                    |
| Independent work stuck behind one long run    | Multitask or async subagents              |
