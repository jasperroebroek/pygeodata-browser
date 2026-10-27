// usage: node perf.mjs [url]   (default: the built app served by the API on :8780)
import { createRequire } from 'module';
const require = createRequire('/usr/local/lib/node_modules/');
const { chromium } = require('playwright');
const URL_ = process.argv[2] ?? 'http://127.0.0.1:8780/';
const cardSel = (c) => `.class-card[title="${c}"]`;
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
const page = await ctx.newPage();
let bytes = 0;
page.on('response', async (r) => {
  if (!r.url().includes('/api/')) return;
  try { bytes += (await r.body()).length; } catch {}
});
const res = [];
async function timed(name, fn) {
  bytes = 0;
  const t = performance.now();
  await fn();
  // let pending paints settle into the measurement
  await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
  res.push(`${name.padEnd(42)} ${String(Math.round(performance.now() - t)).padStart(6)} ms  ${(bytes / 1024).toFixed(0).padStart(7)} KB`);
}
await timed('cold load → classes clickable', async () => {
  await page.goto(URL_);
  await page.waitForSelector(cardSel('CountModel') + ':has(.kind-icon)');
});
await timed('click AridityIndex → rows + detail', async () => {
  await page.click(cardSel('AridityIndex'));
  await page.waitForFunction(() => document.querySelectorAll('tr.row-entry').length === 8 && !!document.querySelector('tr.row-param'));
  await page.waitForSelector('.dcard-hd-label:text-is("Entry")');
});
await timed('ArrowDown → next entry detail', async () => {
  const before = await page.locator('.dcard-hd-actions .act-btn--mono').innerText();
  await page.keyboard.press('ArrowDown');
  await page.waitForFunction((b) => document.querySelector('.dcard-hd-actions .act-btn--mono')?.textContent.trim() !== b, before.trim());
});
await timed('click CountPrediction (1916) → rows', async () => {
  await page.click(cardSel('CountPrediction'));
  await page.waitForFunction(() => [...document.querySelectorAll('tr.row-entry .entry-cls')].some((e) => e.textContent === 'CountPrediction'));
});
await timed('scroll big table to bottom ×5', async () => {
  for (let i = 0; i < 5; i++) {
    const n = await page.locator('tr.row-entry').count();
    await page.locator('.main-pane .table-scroll').evaluate((el) => (el.scrollTop = el.scrollHeight));
    await page.waitForFunction((n) => document.querySelectorAll('tr.row-entry').length > n, n, { timeout: 15000 }).catch(() => {});
  }
});
res.push(`  rows rendered after scrolling: ${await page.locator('tr.row-entry').count()}`);
await timed('Compact toggle (big class)', async () => {
  await page.click('.kind-tab[aria-label=Compact]');
  await page.waitForSelector('.entry-pill');
});
await timed('Figure kind tab', async () => {
  await page.click('.kind-tab:has(.tab-label[data-label="Figure"])');
  await page.waitForFunction(() => ![...document.querySelectorAll('.class-card .kind-icon')].some((i) => i.classList.contains('kind-icon--data')));
});
const heap = await page.evaluate(() => performance.memory?.usedJSHeapSize ?? 0);
res.push(`  JS heap: ${(heap / 1e6).toFixed(1)} MB, DOM nodes: ${await page.evaluate(() => document.getElementsByTagName('*').length)}`);
console.log(res.join('\n'));
await browser.close();
