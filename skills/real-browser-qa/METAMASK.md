# MetaMask Mode

Launches Chromium with MetaMask loaded via CDP. Can unlock, confirm, and reject MetaMask popups programmatically. Use when the test requires wallet confirmation.

**The scripts already exist** — do NOT recreate them. Follow the **observe → act → verify** discipline from the main skill (`SKILL.md`).

Two script families handle MetaMask mode:
- `metamask-cdp.mjs` — MetaMask-specific actions (unlock, confirm, reject)
- `page-cdp.mjs` — web page interactions (click, fill, screenshot, navigate)

## Setup & Lifecycle

```bash
source ~/.bashrc 2>/dev/null || source ~/.zshrc 2>/dev/null

# 1. Launch browser (finds MetaMask, syncs data, starts Chromium + CDP)
bash ~/.cursor/skills/real-browser-qa/scripts/metamask-browser.sh <url>

# 2. Unlock MetaMask (reads METAMASK_PASSWORD from env)
node ~/.cursor/skills/real-browser-qa/scripts/metamask-cdp.mjs unlock

# 3. Clean up stale requests from previous sessions
node ~/.cursor/skills/real-browser-qa/scripts/metamask-cdp.mjs cleanup

# 4. Close browser when done
kill $(lsof -ti:9222) 2>/dev/null
```

## Wallet Actions (`metamask-cdp.mjs`)

```bash
MM=~/.cursor/skills/real-browser-qa/scripts/metamask-cdp.mjs

node $MM confirm            # polls up to 30s for Confirm/Sign/Approve button
node $MM reject             # reject the current popup
node $MM cleanup            # reject all stale pending requests
node $MM pages              # list all browser pages (debug)
node $MM screenshot <path>  # screenshot MetaMask page
node $MM text               # read text content from active MM page (notification or home)
node $MM diagnose           # scan all MM pages, detect errors, dump text
node $MM switch-network "Avalanche Fuji"  # switch to a specific network by name
```

Run `confirm` right after triggering a wallet action on the web page.

### Network Switching

MetaMask often starts on a stale or disconnected network (e.g. a local testnet that isn't running). **After unlock + cleanup, always check the current network** by reading MetaMask text (`node $MM text`). If it shows "Unable to connect" or the wrong network, switch before proceeding:

```bash
node $MM switch-network "Avalanche Fuji"
```

The command opens the network selector, switches to the "Custom" tab if needed, and clicks the target network by exact name. If the dApp's deposit form shows "Unsupported network", use this command first, then interact with the dApp's network dropdown to trigger a `switchChain` on the provider side.

## Multi-Popup Polling (`mm-confirm-poll.mjs`)

For flows with many connect/sign/approve steps (e.g. Privy + MetaMask), use a background poller instead of calling `confirm` repeatedly:

```bash
POLL=~/.cursor/skills/real-browser-qa/scripts/mm-confirm-poll.mjs
MM_POLL_FOREVER=1 node $POLL &
POLL_PID=$!
trap 'kill -TERM $POLL_PID 2>/dev/null' EXIT

# … drive the dApp with page-cdp.mjs …

kill -TERM $POLL_PID 2>/dev/null
```

- `MM_POLL_FOREVER=1` — run until SIGTERM (recommended with `trap` cleanup)
- `MM_POLL_MAX_MS=120000` — alternative fixed duration
- `MM_POLL_CLICK_DELAY_MS=3000` — delay after each confirmation click (default 3000ms; MetaMask needs time to process each confirmation before accepting the next request)
- Start the poller **before** the action that opens the first MetaMask popup; stop when the flow reaches a stable state.

## Web Page Actions (`page-cdp.mjs`)

Use for **all** interactions with the web page. Do NOT use inline Playwright scripts or the Cursor built-in browser — they don't share the MetaMask browser session.

```bash
PAGE=~/.cursor/skills/real-browser-qa/scripts/page-cdp.mjs
URL=localhost:3001  # substring to match the target tab

node $PAGE screenshot $URL /tmp/screenshot.png
node $PAGE click $URL "Sign in with wallet"
node $PAGE click-button $URL "Deposit"
node $PAGE fill $URL "Enter amount" 1
node $PAGE clear $URL "Enter amount"
node $PAGE fill-by-label $URL "Amount" 500
node $PAGE goto $URL http://localhost:3001/settings
node $PAGE wait-for-text $URL "Deposit successful"
node $PAGE wait-for-text $URL "Deposit successful" 60000
node $PAGE text $URL
node $PAGE evaluate $URL "document.title"
```

### `wait-for-text` — avoid false positives

On auth/marketing pages, generic text like "Deposit" can match demo tables or hero copy while the user is still on the login screen. Prefer strings that exist only in the post-auth app shell (e.g. "Total balance") rather than generic action words that appear in marketing mocks.

## CDP Concurrency

`metamask-browser.sh` starts one Chromium on CDP port 9222. Both `metamask-cdp.mjs` and `page-cdp.mjs` use `connectOverCDP` — each opens a short-lived client. `browser.close()` drops the WebSocket, not the browser.

- Run heavy automation **sequentially** to avoid tab races
- Kill Chromium only at session end: `kill $(lsof -ti:9222)`

## Typical Workflow

```bash
source ~/.bashrc 2>/dev/null || source ~/.zshrc 2>/dev/null
MM=~/.cursor/skills/real-browser-qa/scripts/metamask-cdp.mjs
PAGE=~/.cursor/skills/real-browser-qa/scripts/page-cdp.mjs
URL=localhost:3001

# 1. Launch, unlock, clean
bash ~/.cursor/skills/real-browser-qa/scripts/metamask-browser.sh http://$URL/
node $MM unlock
node $MM cleanup

# 2. Interact
node $PAGE screenshot $URL /tmp/step1.png
node $PAGE click $URL "Sign in with wallet"
node $MM confirm
node $PAGE click-button $URL "Deposit"
node $PAGE fill $URL "Enter amount" 1
node $PAGE click-button $URL "Deposit"
node $MM confirm
node $MM confirm
node $PAGE wait-for-text $URL "successful"
node $PAGE screenshot $URL /tmp/result.png

# 3. Close
kill $(lsof -ti:9222) 2>/dev/null
```

## Setup (one-time per machine)

1. Install MetaMask in Chrome and configure your wallet
2. Add to `~/.bashrc`: `export METAMASK_PASSWORD="<your-metamask-password>"`

The launch script handles everything else (finding MetaMask, syncing vault data, installing Chromium).

## Session Persistence

The browser profile at `~/.metamask-testing/profile` persists between launches. Web app localStorage and cookies carry over, but **MetaMask extension state is fully re-synced** from Chrome on each launch to prevent stale permission/account data from causing corruption errors.

Browsers scope `localStorage` to the full origin (scheme + hostname + port). Hitting the same dev server via different hostnames counts as different origins. Align automation URLs with how you open the app.

## Rules

- **ALWAYS** end MetaMask sessions by killing CDP Chromium (`kill $(lsof -ti:9222)`)
- **ALWAYS** use `page-cdp.mjs` for web page interactions — never inline Playwright scripts
- **NEVER** recreate the scripts — they exist at `~/.cursor/skills/real-browser-qa/scripts/`
- If MetaMask mode is not set up (no `METAMASK_PASSWORD` env var), escalate to the user
