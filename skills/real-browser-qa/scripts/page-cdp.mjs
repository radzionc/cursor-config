#!/usr/bin/env node

// Web page CDP interaction helper for MetaMask mode.
// Connects to Chromium (launched by metamask-browser.sh) via CDP and performs
// actions on a non-MetaMask web page matched by URL substring.
//
// Usage:
//   node scripts/page-cdp.mjs screenshot <url-match> <output-path>
//   node scripts/page-cdp.mjs click <url-match> <text>
//   node scripts/page-cdp.mjs click-button <url-match> <button-name>
//   node scripts/page-cdp.mjs fill <url-match> <placeholder> <value>
//   node scripts/page-cdp.mjs clear <url-match> <placeholder>
//   node scripts/page-cdp.mjs fill-by-label <url-match> <label> <value>
//   node scripts/page-cdp.mjs goto <url-match> <new-url>
//   node scripts/page-cdp.mjs wait-for-text <url-match> <text> [timeout-ms]
//   node scripts/page-cdp.mjs text <url-match>
//   node scripts/page-cdp.mjs evaluate <url-match> <js-expression>
//
// <url-match> is a substring to find the right browser tab (e.g. "localhost:3001")

import { createRequire } from 'module';
const require = createRequire(
  `${process.env.HOME}/.metamask-testing/node/package.json`
);
const { chromium } = require('playwright');

const CDP_PORT = process.env.CDP_PORT || '9222';
const MM_EXT_ID = 'nkbihfbeogaeaoehlefnkodbefgpgknn';

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function connect() {
  return chromium.connectOverCDP(`http://localhost:${CDP_PORT}`);
}

async function findPage(browser, urlMatch) {
  for (const ctx of browser.contexts()) {
    for (const page of ctx.pages()) {
      const url = page.url();
      if (url.includes(urlMatch) && !url.includes(MM_EXT_ID)) {
        return page;
      }
    }
  }
  return null;
}

async function getPage(browser, urlMatch) {
  const page = await findPage(browser, urlMatch);
  if (!page) {
    console.error(`ERROR: No page found matching "${urlMatch}"`);
    const pages = [];
    for (const ctx of browser.contexts()) {
      for (const p of ctx.pages()) {
        if (!p.url().includes(MM_EXT_ID)) pages.push(p.url());
      }
    }
    if (pages.length > 0) {
      console.error('Available pages:');
      pages.forEach((u) => console.error(`  ${u}`));
    }
    process.exit(1);
  }
  await page.bringToFront();
  return page;
}

async function cmdScreenshot(browser, urlMatch, outputPath) {
  if (!outputPath) {
    console.error('Usage: page-cdp.mjs screenshot <url-match> <output-path>');
    process.exit(1);
  }
  const page = await getPage(browser, urlMatch);
  await sleep(500);
  await page.screenshot({ path: outputPath });
  console.log(`Screenshot saved: ${outputPath}`);
}

async function cmdClick(browser, urlMatch, text) {
  if (!text) {
    console.error('Usage: page-cdp.mjs click <url-match> <text>');
    process.exit(1);
  }
  const page = await getPage(browser, urlMatch);
  const locator = page.getByText(text, { exact: false });
  const count = await locator.count();
  for (let i = 0; i < count; i++) {
    try {
      await locator.nth(i).click({ timeout: 3000 });
      console.log(`Clicked: "${text}" (match ${i + 1}/${count})`);
      await sleep(1000);
      return;
    } catch {
      // element obscured or not interactable, try next match
    }
  }
  // fallback: force-click the last match (handles overlay scenarios)
  await locator.last().click({ force: true, timeout: 5000 });
  console.log(`Clicked: "${text}" (force, last match)`);
  await sleep(1000);
}

async function cmdFill(browser, urlMatch, placeholder, value) {
  if (!placeholder || value === undefined) {
    console.error(
      'Usage: page-cdp.mjs fill <url-match> <placeholder> <value>'
    );
    process.exit(1);
  }
  const page = await getPage(browser, urlMatch);
  await page.getByPlaceholder(placeholder).fill(value, { timeout: 10000 });
  console.log(`Filled "${placeholder}" with "${value}"`);
}

async function cmdGoto(browser, urlMatch, newUrl) {
  if (!newUrl) {
    console.error('Usage: page-cdp.mjs goto <url-match> <new-url>');
    process.exit(1);
  }
  const page = await getPage(browser, urlMatch);
  await page.goto(newUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
  console.log(`Navigated to: ${newUrl}`);
}

async function cmdWaitForText(browser, urlMatch, text, timeoutMs) {
  if (!text) {
    console.error(
      'Usage: page-cdp.mjs wait-for-text <url-match> <text> [timeout-ms]'
    );
    process.exit(1);
  }
  const timeout = parseInt(timeoutMs || '30000');
  const page = await getPage(browser, urlMatch);
  await page.getByText(text, { exact: false }).first().waitFor({ timeout });
  console.log(`Found: "${text}"`);
}

async function cmdClickButton(browser, urlMatch, name) {
  if (!name) {
    console.error('Usage: page-cdp.mjs click-button <url-match> <button-name>');
    process.exit(1);
  }
  const page = await getPage(browser, urlMatch);
  const locator = page.getByRole('button', { name, exact: false });
  const count = await locator.count();
  for (let i = 0; i < count; i++) {
    try {
      await locator.nth(i).click({ timeout: 3000 });
      console.log(`Clicked button: "${name}" (match ${i + 1}/${count})`);
      await sleep(1000);
      return;
    } catch {
      // button obscured or not interactable, try next match
    }
  }
  await locator.last().click({ force: true, timeout: 5000 });
  console.log(`Clicked button: "${name}" (force, last match)`);
  await sleep(1000);
}

async function cmdClear(browser, urlMatch, placeholder) {
  if (!placeholder) {
    console.error('Usage: page-cdp.mjs clear <url-match> <placeholder>');
    process.exit(1);
  }
  const page = await getPage(browser, urlMatch);
  const input = page.getByPlaceholder(placeholder);
  await input.click({ timeout: 5000 });
  await input.fill('', { timeout: 5000 });
  console.log(`Cleared "${placeholder}"`);
}

async function cmdFillByLabel(browser, urlMatch, label, value) {
  if (!label || value === undefined) {
    console.error(
      'Usage: page-cdp.mjs fill-by-label <url-match> <label> <value>'
    );
    process.exit(1);
  }
  const page = await getPage(browser, urlMatch);
  await page.getByLabel(label).fill(value, { timeout: 10000 });
  console.log(`Filled label "${label}" with "${value}"`);
}

async function cmdEvaluate(browser, urlMatch, expression) {
  if (!expression) {
    console.error(
      'Usage: page-cdp.mjs evaluate <url-match> <js-expression>'
    );
    process.exit(1);
  }
  const page = await getPage(browser, urlMatch);
  const result = await page.evaluate(expression);
  console.log(typeof result === 'object' ? JSON.stringify(result, null, 2) : String(result));
}

async function cmdText(browser, urlMatch) {
  const page = await getPage(browser, urlMatch);
  const text = await page.innerText('body');
  console.log(text.substring(0, 5000));
}

async function main() {
  const [command, ...args] = process.argv.slice(2);
  if (!command) {
    console.log(
      'Usage: page-cdp.mjs <screenshot|click|click-button|fill|clear|fill-by-label|goto|wait-for-text|text|evaluate> <url-match> [args]'
    );
    process.exit(1);
  }

  const browser = await connect();

  try {
    switch (command) {
      case 'screenshot':
        await cmdScreenshot(browser, args[0], args[1]);
        break;
      case 'click':
        await cmdClick(browser, args[0], args.slice(1).join(' '));
        break;
      case 'fill':
        await cmdFill(browser, args[0], args[1], args.slice(2).join(' '));
        break;
      case 'goto':
        await cmdGoto(browser, args[0], args[1]);
        break;
      case 'wait-for-text':
        await cmdWaitForText(browser, args[0], args[1], args[2]);
        break;
      case 'click-button':
        await cmdClickButton(browser, args[0], args.slice(1).join(' '));
        break;
      case 'clear':
        await cmdClear(browser, args[0], args.slice(1).join(' '));
        break;
      case 'fill-by-label':
        await cmdFillByLabel(browser, args[0], args[1], args.slice(2).join(' '));
        break;
      case 'text':
        await cmdText(browser, args[0]);
        break;
      case 'evaluate':
        await cmdEvaluate(browser, args[0], args.slice(1).join(' '));
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
