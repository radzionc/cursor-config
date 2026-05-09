---
name: real-browser-qa
description: Automate a real Chrome instance via playwright-cli and CDP scripts. Use when the Cursor built-in browser is insufficient — browser extensions (wallets), user auth sessions, or Chrome-specific APIs.
---

# Real Browser

Automate a real Chrome instance through `playwright-cli` shell commands or CDP scripts.

- **Extension mode** (`open --extension`): connects to the user's running Chrome with full access to logged-in sessions.
- **Standalone mode** (`open --browser=chrome --headed`): launches a fresh Chrome. No extensions or sessions.
- **MetaMask mode**: launches Chromium with MetaMask via CDP. See [MetaMask Mode](#metamask-mode) below.

## Observe → act → verify

Every real-browser workflow follows this discipline. Most failures ("stuck on dashboard", "button not clicked") trace to **stale plans** — the agent runs steps for an earlier screen instead of reading what's currently visible.

- **Read the page between steps**: After each interaction, take a snapshot and pick the next action from the **current** UI. Never assume you're on the step your original plan expected.
- **Skip-ahead**: If the viewport already shows a later milestone, do that next. Don't replay earlier flows just because a plan listed them.
- **No monolithic scripts**: One big shell script with hardcoded sleeps fails when any screen differs. Use commands as small primitives; branch in the agent between steps.
- **Milestones**: Define visible checkpoints (authenticated shell, modals cleared, target view). If several cycles don't advance past one view, stop — capture URL + visible text, report, and replan.

## Extension & Standalone Modes

```bash
# Extension mode — uses user's running Chrome sessions
source ~/.bashrc 2>/dev/null || source ~/.zshrc 2>/dev/null
npx @playwright/cli open --extension

# Standalone mode — clean Chrome, no sessions
npx @playwright/cli open --browser=chrome --headed <url>

# Commands (both modes)
npx @playwright/cli snapshot
npx @playwright/cli goto <url>
npx @playwright/cli click <ref>
npx @playwright/cli fill <ref> <text>
npx @playwright/cli type <text>
npx @playwright/cli press <key>
npx @playwright/cli hover <ref>
npx @playwright/cli select <ref> <value>
npx @playwright/cli screenshot --filename=<name>.png
npx @playwright/cli tab-list
npx @playwright/cli tab-select <index>
npx @playwright/cli go-back

# Close
npx @playwright/cli close
```

Run `npx @playwright/cli --help` or `npx @playwright/cli <command> --help` for the full command set (`eval`, `run-code`, `console`, `network`, `state-save`/`state-load`, `cookie-*`, `localstorage-*`, `check`, `upload`, `drag`, `--persistent`, etc.).

Extension UIs (wallet popups) are **not** interactable in extension mode — use MetaMask mode for wallet confirmation flows.

### Extension mode setup (one-time per machine)

1. Install the [Playwright MCP Bridge Extension](https://chromewebstore.google.com/detail/playwright-mcp-bridge/mmlmfjhmonkocbjadbfplnigmagldckm) in Chrome
2. Click the extension icon → copy the token
3. Add to `~/.bashrc`: `export PLAYWRIGHT_MCP_EXTENSION_TOKEN="<token>"`

If connection fails, ask the user for the current token.

## MetaMask Mode

For wallet-dependent testing (connect, sign, approve transactions), read and follow the MetaMask supplement:
`~/.cursor/skills/real-browser-qa/METAMASK.md`

MetaMask mode launches Chromium with the MetaMask extension loaded via CDP. It can unlock, confirm, and reject wallet popups programmatically.

## Rules

- **Prefer** incremental steps with **observe → act → verify** over monolithic scripts.
- **ALWAYS** source the shell profile before using env vars.
- **NEVER** pass credentials, seed phrases, or private keys — use env vars.
