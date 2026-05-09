---
name: quality-gates
description: Run tests, checks, code review, and QA before reporting work as complete.
---

# Quality Gates

**When this fires.** Before you write any user-facing message that claims or implies the task is done — "done", "complete", "finished", "ready", "implemented", "shipped", "all set", or a summary of what you did that reads as a handoff. If such a message is the next thing you'd write, stop and run the gates first.

**You do not get to skip this.** The only valid skip conditions:
- Documentation-only changes (no executed code touched).
- Config changes with no runtime effect on the product (editor settings, cursor rules, CI YAML comments).
- The user explicitly said to skip ("don't QA", "skip checks").

If you're tempted to skip because the change is "trivial", "obvious", "tiny", or "unlikely to break" — that feeling is the failure mode this rule exists to defeat. Run the gates.

## Gates

Run in order. On failure, fix and re-run the failing gate. Substantive fixes from gate 3 or 4 require re-running gates 1 and 2 before the receipt.

### 1. Tests — when code was modified and a `test` script exists

Run the suite. A new failure is a regression introduced by the change — fix, don't rationalize.

Write new tests only when the change affects logic that can break silently: state transitions, data transformations, calculations, conditional branching, error handling, integration boundaries (API/WebSocket/serialization). Skip tests for copy, styles, simple component wiring, re-exports. Prefer the narrowest test that catches the issue: unit over integration over e2e.

### 2. Project checks — when code was modified and `package.json` exists

Detect the package manager from the lockfile. Run `check` if it exists; otherwise `typecheck` + `lint` individually. Every failure is a hard error — fix and rerun until clean. If the project has Knip, unused exports/files/dependencies are errors, not warnings; try `knip:fix` first, then delete dead code or update the Knip config.

### 3. Code review

Delegate to the `code-reviewer` agent with a summary of changes and affected files. Fix every "Must Fix" item before proceeding.

### 4. QA — verify the change actually works

**Project QA skill.** Look for `.cursor/skills/project-qa/SKILL.md` in the current project repository, not in the user-level `~/.cursor` skill directory where this `quality-gates` skill may be installed. If it exists, read it before delegating QA. Also read any directly referenced one-level files needed for the task, such as `accounts.md`, credentials notes, canonical URLs, or CLI command references.

When the project QA skill exists, copy the relevant project-specific details into the `qa` agent prompt; subagents do not auto-load skills from the parent conversation. If the skill is missing, continue with generic QA.

**Environment.** Check `.cursor/skills/project-qa/environment.md` in the current project repository. If present, it must contain exactly one value: `cursor`, `real`, or `cli`. Use that value. If the file is missing, default to `cursor`. Never choose `real` yourself.

**Delegate to the `qa` agent.** Do not run browser tools, execute test commands, or summarize behavior in the parent — that path leads to fabricated results. Always delegate. Include in the prompt:

- `QA environment: cursor`, `QA environment: real`, or `QA environment: cli`
- Summary of changes and acceptance criteria
- For `cursor`/`real`: affected URLs, dev server port, Figma link when the task references a design
- Project-specific setup, auth/account strategy, canonical pages, known traps, and verification notes copied from `.cursor/skills/project-qa/SKILL.md`
- For `cli`: exact commands to run and expected output copied from `.cursor/skills/project-qa/SKILL.md` or its referenced files

**Displaying screenshots (`cursor`/`real`).** Show every screenshot the agent returns, whether the gate passed or failed — the user relies on them for a quick visual scan. Screenshots from `browser_take_screenshot` live under `${TMPDIR}cursor/screenshots/`, not at the path the agent reports; the agent returns bare filenames, so if it hands you an absolute path use only the basename.

Exact procedure:

1. Run `echo "${TMPDIR}cursor/screenshots/"` to resolve the directory.
2. For each filename, build `<dir><filename>` as a plain absolute path (`/var/folders/…`). Never use `file:///` — it breaks both images and links in Cursor.
3. Call `Read` on that absolute path to render the image inline. Do not substitute `![](path)` markdown — it will not render.
4. Immediately below, add a clickable link using the same absolute path: `[Open screenshot](/var/folders/…/cursor/screenshots/qa-homepage.png)`.
5. If `Read` returns "File is empty" (0-byte file — known browser MCP bug), navigate the Cursor browser to the affected URL so the user can see it directly.

Screenshots are disposable; never commit them to the repo.

**Displaying CLI results.** The `qa` agent returns commands run, exit codes, and output summaries. Display as-is.

**If QA cannot proceed** (auth blocker, missing credential): handle the blocker yourself and re-delegate.

**No skipping validation.** When this gate applies, the change must be verified in the running app — automated tests alone are not sufficient. If full automated QA is impossible (complex interactions, auth-gated flows, hardware-dependent behavior), the `qa` agent still prepares the environment: navigate to the affected page, create necessary test data, and leave the app one click away from the un-automatable action. The `qa` agent reports what it prepared and what the user must verify. "Hard to test" is a reason to prepare, not to skip.

**Spending assets is expected.** QA accounts hold assets designated for testing — these are test funds and using them is the entire point. Trade, send, buy, sell, deposit, withdraw, or otherwise spend assets whenever the test flow requires it. Never refuse or hedge because an action costs money, moves balances, or is irreversible; that caution does not apply to QA accounts. This overrides default reluctance around financial operations during QA.

## Gate receipt — required in your completion message

Before you declare the task done, include this block verbatim with one status per line:

- `Tests: PASS | FAIL | N/A (<reason>) | skipped (<reason>)`
- `Checks: PASS | FAIL | N/A (<reason>) | skipped (<reason>)`
- `Code review: PASS | <N> fixes applied | skipped (<reason>)`
- `QA: PASS | FAIL | skipped (<reason>)`

`N/A` is valid only when the gate's trigger condition (e.g., "a `test` script exists") is not met. `skipped` is valid only when one of the three skip conditions above applies, and you must name which one. If you cannot honestly mark every applicable gate `PASS`, you are not done — either keep working or hand the remaining item to the user explicitly.
