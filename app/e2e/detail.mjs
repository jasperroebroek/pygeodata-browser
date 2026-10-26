import { createRequire } from 'module';
const require = createRequire('/usr/local/lib/node_modules/');
const { chromium } = require('playwright');
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
const errors = [];
page.on('pageerror', (e) => errors.push(e.message));
page.on('console', (m) => m.type() === 'error' && errors.push(m.text()));
const out = [];
const check = (n, ok, i = '') => out.push(`${ok ? 'PASS' : 'FAIL'}  ${n}${i ? '  — ' + i : ''}`);
const S = (n) => page.screenshot({ path: new URL(`./shots/D-${n}.png`, import.meta.url).pathname });
await page.goto('http://localhost:5173/', { waitUntil: 'networkidle' });
const count = (s) => page.locator(s).count();
const wait = (ms = 700) => page.waitForTimeout(ms);
const close = async () => { await page.click('.modal-close'); await wait(200); };

// Figure entry
await page.click('.class-card[title="Figure1"]'); await wait(1500);
check('Figure preview renders', await page.locator('.fig-main').evaluate((i) => i.complete && i.naturalWidth > 0));
await S('figure');
await page.click('.fig-main'); await wait(800);
check('Figure click opens preview modal', (await count('.modal-content img')) === 1);
await close();
// Graph popup
await page.click('.dcard-hd-actions .act-btn:text-is("Graph") >> nth=0'); await wait(2500);
check('Class graph popup', (await count('.modal-content svg, .modal-content iframe')) === 1);
await S('graph'); await close();
// Tree popup
if (await count('.act-btn:text-is("Tree")')) {
  await page.click('.act-btn:text-is("Tree")'); await wait(1200);
  check('Tree popup shows explorer', (await count('.modal-content .jx-row')) > 0);
  await S('tree'); await close();
}
// Params popup
await page.click('.act-btn:text-is("Params")'); await wait(1000);
check('Params popup shows explorer', (await count('.modal-content .jx-row')) > 0);
await close();
// Bounds map
if (await count('.js-bounds-map')) {
  await page.click('.js-bounds-map'); await wait(800);
  check('Bounds map modal', (await count('.modal-content iframe')) === 1); await close();
}
// Table entry
const tableCls = await page.locator('.class-card:has(.badge-type-table)').first().getAttribute('title');
await page.click(`.class-card[title="${tableCls}"]`); await wait(2000);
check('Table preview renders', (await count('.tbl-preview table')) > 0, tableCls);
await S('table');
// Linked / co-output link navigates
const link = page.locator('.link-entry-name[href]').first();
if (await link.count()) {
  const cls = (await link.innerText()).trim();
  await link.click(); await wait(1500);
  check('Linked entry navigates to its class', (await count(`.class-card.filtered[title="${cls}"]`)) === 1, cls);
}
// Source -> code
await page.click('.act-btn:text-is("Source")'); await wait(3000);
check('Source opens code view on class', (await page.locator('.code-class-item.active').count()) === 1 && (await count('.source-table')) === 1);
await S('source');
// Find entries back
await page.click('.act-btn:text-is("Find entries")'); await wait(1500);
check('Find entries returns to entries', (await count('tr.row-entry')) > 0);
// Class diff
await page.click('.view-tab:has-text("Code")'); await wait(2000);
await page.click('.code-version-item:has-text("v3")'); await wait(1500);
await page.click('.code-class-item:has-text("FigureCountPerDiseaseGroupContributions")'); await wait(1500);
await page.click('.code-diff-bar .kind-tab:text-is("Diff")'); await wait(1200);
check('Class diff renders', (await count('.code-source-panel .diff-table tr.diff-add, .code-source-panel .diff-table tr.diff-del')) > 0);
await page.click('.kind-tab:text-is("Side by side")'); await wait(500);
check('Side by side renders', (await count('.diff-table--split')) === 1);
await page.click('.kind-tab:text-is("Full")'); await wait(500);
check('Full expand renders more rows', (await count('.diff-table tr')) > 30);
await S('diff');
await page.click('.kind-tab:text-is("Inline")'); await page.click('.kind-tab:text-is("Hunks")');
// Diagnostics
await page.click('.btn-diag'); await wait(400);
check('Diagnostics modal', (await count('.diag-table .diag-val')) >= 5); await S('diag'); await close();
// Clean cache dry run
await page.click('button[title=Menu]');
const disabled = await page.locator('.topbar-menu-item:has-text("Clean cache")').isDisabled();
if (!disabled) {
  await page.click('.topbar-menu-item:has-text("Clean cache")'); await wait(2500);
  check('Clean cache dry-run preview', (await page.locator('.clean-cache-output').innerText()).length > 0);
  await S('clean'); await close();
} else { check('Clean cache enabled (live classes)', false); await page.keyboard.press('Escape'); }
console.log(out.join('\n'));
if (errors.length) console.log('errors:\n' + errors.join('\n'));
await browser.close();
