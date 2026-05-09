#!/usr/bin/env node

// MetaMask CDP interaction helper.
// Connects to Chromium (launched by metamask-browser.sh) via CDP and performs
// MetaMask-specific actions: unlock, confirm, reject, list pages, screenshot,
// read text content, and diagnose errors.
//
// Usage:
//   node scripts/metamask-cdp.mjs unlock
//   node scripts/metamask-cdp.mjs confirm
//   node scripts/metamask-cdp.mjs reject
//   node scripts/metamask-cdp.mjs pages
//   node scripts/metamask-cdp.mjs screenshot <output-path>
//   node scripts/metamask-cdp.mjs text              # read text from active MM page
//   node scripts/metamask-cdp.mjs diagnose           # capture error state + screenshot
//
// Requires: METAMASK_PASSWORD env var (for unlock), playwright in ~/.metamask-testing/node

import { createRequire } from 'module';
const require = createRequire(
  `${process.env.HOME}/.metamask-testing/node/package.json`
);
const { chromium } = require('playwright');

const CDP_PORT = process.env.CDP_PORT || '9222';
const METAMASK_PASSWORD = process.env.METAMASK_PASSWORD;
const MM_EXT_ID = 'nkbihfbeogaeaoehlefnkodbefgpgknn';

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function connect() {
  return chromium.connectOverCDP(`http://localhost:${CDP_PORT}`);
}

function findPages(browser, urlMatch) {
  const results = [];
  for (const ctx of browser.contexts()) {
    for (const page of ctx.pages()) {
      if (page.url().includes(urlMatch)) results.push(page);
    }
  }
  return results;
}

async function cmdUnlock(browser) {
  if (!METAMASK_PASSWORD) {
    console.error('ERROR: METAMASK_PASSWORD env var not set.');
    process.exit(1);
  }

  const pages = findPages(browser, `${MM_EXT_ID}/home.html`);
  if (pages.length === 0) {
    console.log('No MetaMask home page found. It may already be unlocked.');
    return;
  }

  const mmPage = pages[0];
  if (!mmPage.url().includes('unlock')) {
    console.log('MetaMask is already unlocked.');
    return;
  }

  console.log('Unlocking MetaMask...');
  await mmPage.bringToFront();
  await sleep(1000);
  await mmPage.fill('input[data-testid="unlock-password"]', METAMASK_PASSWORD);
  await mmPage.click('button[data-testid="unlock-submit"]');
  await sleep(3000);

  if (mmPage.url().includes('unlock')) {
    console.error('ERROR: MetaMask still on unlock page. Wrong password?');
    process.exit(1);
  }
  console.log('MetaMask unlocked.');
}

async function findNotificationPage(browser) {
  for (const ctx of browser.contexts()) {
    for (const page of ctx.pages()) {
      const url = page.url();
      if (!url.includes(MM_EXT_ID)) continue;
      if (
        url.includes('notification') ||
        url.includes('confirm') ||
        url.includes('signature')
      )
        return page;
    }
  }
  return null;
}

const CONFIRM_SELECTORS = [
  // MetaMask 13.x (primary)
  'button[data-testid="confirm-btn"]',
  // MetaMask <13 (legacy fallbacks)
  'button[data-testid="confirm-footer-button"]',
  'button[data-testid="page-container-footer-next"]',
  'button[data-testid="request-signature__sign"]',
  'button[data-testid="confirmConnectButton"]',
  // Text-based fallbacks
  'button:has-text("Confirm")',
  'button:has-text("Connect")',
  'button:has-text("Sign")',
  'button:has-text("Approve")',
];

async function tryClickButton(page, selectors) {
  for (const sel of selectors) {
    try {
      const btn = await page.$(sel);
      if (btn) {
        const visible = await btn.isVisible();
        const disabled = await btn.isDisabled();
        if (visible && !disabled) {
          await btn.click();
          return sel;
        }
      }
    } catch {
      // Selector might not be supported or page navigated
    }
  }
  return null;
}

async function cmdConfirm(browser) {
  console.log('Looking for MetaMask confirmation...');

  for (let attempt = 0; attempt < 30; attempt++) {
    const page = await findNotificationPage(browser);
    if (page) {
      await page.bringToFront();
      await sleep(1500);

      const clicked = await tryClickButton(page, CONFIRM_SELECTORS);
      if (clicked) {
        console.log(`Clicked: ${clicked}`);
        await sleep(2000);
        return;
      }
    }

    // Also check MetaMask home page for inline confirmations
    if (attempt === 5) {
      for (const mmPage of findPages(browser, `${MM_EXT_ID}/home.html`)) {
        if (mmPage.url().includes('unlock')) continue;
        await mmPage.bringToFront();
        await sleep(1000);
        const clicked = await tryClickButton(mmPage, CONFIRM_SELECTORS);
        if (clicked) {
          console.log(`Clicked in home: ${clicked}`);
          await sleep(2000);
          return;
        }
      }
    }

    await sleep(1000);
    if (attempt % 10 === 0 && attempt > 0)
      console.log(`  Still waiting... (${attempt}s)`);
  }

  console.error('ERROR: No MetaMask confirmation found within 30 seconds.');
  process.exit(1);
}

const REJECT_SELECTORS = [
  // MetaMask 13.x (primary)
  'button[data-testid="cancel-btn"]',
  // MetaMask <13 (legacy fallbacks)
  'button[data-testid="confirm-footer-cancel-button"]',
  'button[data-testid="page-container-footer-cancel"]',
  // Text-based fallbacks
  'button:has-text("Reject")',
  'button:has-text("Cancel")',
];

async function cmdReject(browser) {
  console.log('Looking for MetaMask rejection...');

  const page = await findNotificationPage(browser);
  if (page) {
    await page.bringToFront();
    await sleep(1500);

    const clicked = await tryClickButton(page, REJECT_SELECTORS);
    if (clicked) {
      console.log(`Rejected: ${clicked}`);
      return;
    }
  }

  console.error('No MetaMask confirmation to reject.');
  process.exit(1);
}

async function cmdCleanup(browser) {
  console.log('Cleaning up stale MetaMask requests...');
  let cleaned = 0;

  for (let round = 0; round < 5; round++) {
    const page = await findNotificationPage(browser);
    if (!page) break;

    await page.bringToFront();
    await sleep(1000);

    const clicked = await tryClickButton(page, REJECT_SELECTORS);
    if (clicked) {
      cleaned++;
      console.log(`  Rejected stale request (${clicked})`);
      await sleep(1000);
    } else {
      break;
    }
  }

  console.log(cleaned > 0 ? `Cleaned ${cleaned} stale request(s).` : 'No stale requests found.');
}

async function cmdPages(browser) {
  for (const ctx of browser.contexts()) {
    for (const page of ctx.pages()) {
      const title = await page.title().catch(() => '(no title)');
      console.log(`${page.url()}\n  title: ${title}`);
    }
  }
}

async function cmdScreenshot(browser, outputPath) {
  if (!outputPath) {
    console.error('Usage: metamask-cdp.mjs screenshot <output-path>');
    process.exit(1);
  }

  // Screenshot the first MetaMask page found
  for (const ctx of browser.contexts()) {
    for (const page of ctx.pages()) {
      if (page.url().includes(MM_EXT_ID)) {
        await page.bringToFront();
        await sleep(500);
        await page.screenshot({ path: outputPath });
        console.log(`Screenshot saved: ${outputPath}`);
        return;
      }
    }
  }
  console.error('No MetaMask page found to screenshot.');
  process.exit(1);
}

async function findAnyMmPage(browser) {
  for (const ctx of browser.contexts()) {
    for (const page of ctx.pages()) {
      if (page.url().includes(MM_EXT_ID)) return page;
    }
  }
  return null;
}

async function cmdText(browser) {
  const notification = await findNotificationPage(browser);
  const page = notification || (await findAnyMmPage(browser));
  if (!page) {
    console.error('No MetaMask page found.');
    process.exit(1);
  }
  await page.bringToFront();
  await sleep(500);
  const text = await page.innerText('body').catch(() => '(could not read body text)');
  console.log(text.substring(0, 5000));
}

async function cmdSwitchNetwork(browser, networkName) {
  if (!networkName) {
    console.error('Usage: metamask-cdp.mjs switch-network <network-name>');
    console.error('Example: metamask-cdp.mjs switch-network "Avalanche Fuji"');
    process.exit(1);
  }

  const pages = findPages(browser, `${MM_EXT_ID}/home.html`);
  if (pages.length === 0) {
    console.error('No MetaMask home page found.');
    process.exit(1);
  }
  const mmPage = pages[0];
  await mmPage.bringToFront();
  await sleep(500);

  const networkBtn = mmPage.locator('button:has-text("Localhost"), button:has-text("Ethereum"), button:has-text("Fuji"), button:has-text("Sepolia"), button:has-text("Mainnet"), button:has-text("Arbitrum"), [data-testid="network-display"]').first();
  const hasNetworkBtn = await networkBtn.isVisible({ timeout: 3000 }).catch(() => false);
  if (!hasNetworkBtn) {
    console.error('Could not find the network selector button.');
    process.exit(1);
  }
  await networkBtn.click();
  await sleep(1500);

  const target = mmPage.getByText(networkName, { exact: true }).first();
  const targetVisible = await target.isVisible({ timeout: 3000 }).catch(() => false);
  if (!targetVisible) {
    const customTab = mmPage.getByText('Custom').first();
    if (await customTab.isVisible({ timeout: 1000 }).catch(() => false)) {
      await customTab.click();
      await sleep(1000);
    }
    const targetAfterTab = mmPage.getByText(networkName, { exact: true }).first();
    const found = await targetAfterTab.isVisible({ timeout: 3000 }).catch(() => false);
    if (!found) {
      const bodyText = await mmPage.innerText('body').catch(() => '');
      console.error(`Network "${networkName}" not found. Available networks:`);
      console.error(bodyText.substring(0, 1000));
      process.exit(1);
    }
    await targetAfterTab.click();
  } else {
    await target.click();
  }

  await sleep(2000);
  console.log(`Switched to: ${networkName}`);
}

async function cmdDiagnose(browser) {
  const pages = [];
  for (const ctx of browser.contexts()) {
    for (const page of ctx.pages()) {
      if (page.url().includes(MM_EXT_ID)) pages.push(page);
    }
  }

  if (pages.length === 0) {
    console.log('No MetaMask pages open.');
    return;
  }

  for (const page of pages) {
    const url = page.url();
    const title = await page.title().catch(() => '(no title)');
    console.log(`\n=== ${title} ===`);
    console.log(`URL: ${url}`);

    await page.bringToFront();
    await sleep(500);

    const text = await page.innerText('body').catch(() => '');
    const hasError =
      text.includes('encountered an error') ||
      text.includes('Error message') ||
      text.includes('TypeError') ||
      text.includes('ReferenceError');

    if (hasError) {
      console.log('STATUS: ERROR DETECTED');
      console.log('---');
      console.log(text.substring(0, 3000));
      console.log('---');
    } else {
      console.log('STATUS: OK');
      console.log(`Content preview: ${text.substring(0, 200).replace(/\n/g, ' ')}`);
    }
  }
}

async function main() {
  const [command, ...args] = process.argv.slice(2);
  if (!command) {
    console.log(
      'Usage: metamask-cdp.mjs <unlock|confirm|reject|cleanup|pages|screenshot|text|diagnose|switch-network> [args]'
    );
    process.exit(1);
  }

  const browser = await connect();

  try {
    switch (command) {
      case 'unlock':
        await cmdUnlock(browser);
        break;
      case 'confirm':
        await cmdConfirm(browser);
        break;
      case 'reject':
        await cmdReject(browser);
        break;
      case 'cleanup':
        await cmdCleanup(browser);
        break;
      case 'pages':
        await cmdPages(browser);
        break;
      case 'screenshot':
        await cmdScreenshot(browser, args[0]);
        break;
      case 'text':
        await cmdText(browser);
        break;
      case 'diagnose':
        await cmdDiagnose(browser);
        break;
      case 'switch-network':
        await cmdSwitchNetwork(browser, args[0]);
        break;
      default:
        console.error(`Unknown command: ${command}`);
        process.exit(1);
    }
  } finally {
    // connectOverCDP: closes this client's CDP WebSocket; Chromium keeps running.
    await browser.close();
  }
}

main().catch((e) => {
  console.error(`Fatal: ${e.message}`);
  process.exit(1);
});
