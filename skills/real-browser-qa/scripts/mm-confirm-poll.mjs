#!/usr/bin/env node
/**
 * Fast CDP poll for MetaMask confirm / connect / sign buttons (shared Chromium).
 *
 * Use for multi-step Privy + wallet flows where many popups appear in quick succession.
 * Unlike `metamask-cdp.mjs confirm`, this does not block 30s when nothing is visible.
 *
 * - Connects to the same CDP port as metamask-browser.sh (default 9222).
 * - Does NOT call browser.close() — exits by process end + SIGTERM (leaves Chromium running).
 *
 * Usage:
 *   MM_POLL_FOREVER=1 node ~/.cursor/skills/real-browser-qa/scripts/mm-confirm-poll.mjs
 *   MM_POLL_MAX_MS=120000 node .../mm-confirm-poll.mjs
 *
 * Env:
 *   CDP_PORT          default 9222
 *   MM_POLL_FOREVER=1 run until SIGTERM (recommended: background during dApp actions)
 *   MM_POLL_MAX_MS    max runtime when not forever (default 180000)
 */

import { createRequire } from 'node:module'

const require = createRequire(
  `${process.env.HOME}/.metamask-testing/node/package.json`,
)
const { chromium } = require('playwright')

const CDP_PORT = process.env.CDP_PORT || '9222'
const MM_EXT_ID = 'nkbihfbeogaeaoehlefnkodbefgpgknn'
const MAX_MS = Number(process.env.MM_POLL_MAX_MS || 180_000)
const RUN_FOREVER = process.env.MM_POLL_FOREVER === '1'
const POST_CLICK_DELAY = Number(process.env.MM_POLL_CLICK_DELAY_MS || 3000)

const SELECTORS = [
  'button[data-testid="confirm-btn"]',
  'button[data-testid="confirm-footer-button"]',
  'button[data-testid="page-container-footer-next"]',
  'button[data-testid="request-signature__sign"]',
  'button[data-testid="confirmConnectButton"]',
]

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

async function main() {
  const browser = await chromium.connectOverCDP(
    `http://localhost:${CDP_PORT}`,
  )
  const deadline = RUN_FOREVER ? Number.POSITIVE_INFINITY : Date.now() + MAX_MS
  let clicks = 0

  const onSig = () => {
    process.stderr.write(`mm-confirm-poll: stopping (${clicks} clicks)\n`)
    process.exit(0)
  }
  process.on('SIGTERM', onSig)
  process.on('SIGINT', onSig)

  while (Date.now() < deadline) {
    for (const ctx of browser.contexts()) {
      for (const page of ctx.pages()) {
        const url = page.url()
        if (!url.includes(MM_EXT_ID) || url.includes('unlock')) continue
        for (const sel of SELECTORS) {
          const loc = page.locator(sel).first()
          try {
            const vis = await loc.isVisible({ timeout: 80 })
            if (!vis) continue
            const dis = await loc.isDisabled().catch(() => true)
            if (dis) continue
            await loc.click({ timeout: 1500 })
            clicks++
            process.stderr.write(`mm-confirm-poll: click #${clicks} ${sel}\n`)
            await sleep(POST_CLICK_DELAY)
          } catch {
            /* next selector / page */
          }
        }
      }
    }
    await sleep(150)
  }

  process.stderr.write(`mm-confirm-poll: done (${clicks} clicks)\n`)
  // Intentionally no browser.close(): for connectOverCDP, avoid racing other CDP clients;
  // process exit drops the WebSocket. Chromium stays up for page-cdp / other tools.
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
