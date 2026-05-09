# Sync Cursor Features

Update `skills/cursor/cursor-features.md` with the latest Cursor capabilities.

**Edit the features file directly.** This is a mechanical sync, not a design decision.

## The filter — apply before writing anything

The features file is the agent's operational knowledge. It lists **only** features the agent directly invokes, creates, or produces during a session. Apply this test to every changelog entry.

### Include only if one is true

- The agent **creates or edits a file** for it: `.cursor/rules/`, `.cursor/skills/`, `.cursor/agents/`, `.cursor/hooks.json`, `.cursor/mcp.json`, `.cursor/plans/`, `*.canvas.tsx`.
- The agent **invokes it via a tool call**: `Task` (subagents), `SwitchMode`, `AskQuestion`, MCP tools, `Await`.
- The agent's **response format changes**: e.g., canvases as a response artifact, structured MCP content.
- The agent's **behavior fundamentally changes** under it: e.g., Plan Mode's read-only restriction, Debug Mode's evidence collection.

### Exclude — always, no matter how prominent in the changelog

- Keyboard shortcuts, hotkeys, key combinations. The agent cannot press keys.
- UI layout: tabs, panes, tiled views, window management, split views, scroll behavior, rendering.
- Mouse/drag/click interactions: Design Mode, annotation tools, element selection, highlights.
- Voice input, dictation, speech-to-text.
- Dashboard/admin/billing/plan configuration. Bugbot. Cloud Agents settings.
- Cloud infrastructure, self-hosted setups, organizational/team/enterprise controls.
- Editor UX improvements: diff navigation, file tree behavior, search filters, performance fixes.
- Bug fixes to the UI or rendering.
- Any feature that is a **human workflow around Cursor** rather than an **agent capability inside Cursor**.

### The acid test

Ask: *"What would the agent do differently because of this feature?"*

- Answer describes what the **user sees or does in the IDE** → exclude.
- Answer describes **a file the agent creates, a tool it calls, or a response it produces** → include.

If uncertain, exclude. The file is easier to read when tight than when inclusive.

## Style rules for the features file

- No references to other skills, external skill files, or sync instructions. The file stands alone as pure Cursor reference.
- No keyboard shortcuts, UI gestures, window-management instructions.
- No "Staying Up-to-Date" section in the file itself — sync guidance lives here.
- Dense over verbose. Every sentence loads on every read.

## Process

### 1. Fetch the changelog

Fetch https://cursor.com/changelog.

### 2. Read the current reference

Read `skills/cursor/cursor-features.md`. Note the "Last synced" line — version and date.

### 3. Walk every entry newer than the last sync

For each entry, apply the filter **before** drafting any text. If it fails the filter, skip it completely — do not add it to the file, do not mention it in any section.

Then categorize what passes:
- New agent-actionable feature → add to the appropriate section.
- Changed behavior of an existing feature → update the entry.
- Deprecated → remove.

### 4. Update the file

1. Update the "Last synced" line with the new version and today's date.
2. Add or update sections for features that passed the filter.
3. Update the Prospective and Retrospective Decision Matrices if a new feature belongs there.

### 5. Report

```
**Synced**: [old] → [new]
**Added**: [entries that passed the filter, 1 line each]
**Changed**: [updates, 1 line each]
**Filtered out**: [features excluded and which filter category they fell into]
```

If nothing passed the filter, say: "Reference is current as of [version]."
