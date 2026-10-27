import { createRequire } from 'module';
const require = createRequire('/usr/local/lib/node_modules/');
const { chromium } = require('playwright');
const URL_ = process.argv[2] ?? 'http://localhost:5173/';
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
const page = await ctx.newPage();
const errors = [];
page.on('pageerror', (e) => errors.push(e.message));
page.on('console', (m) => m.type() === 'error' && errors.push(m.text()));
let reqs = [];
page.on('request', (r) => r.url().includes('/api/') && reqs.push(decodeURIComponent(r.url())));
const results = [];
const check = (name, ok, info = '') => results.push(`${ok ? 'PASS' : 'FAIL'}  ${name}${info ? '  — ' + info : ''}`);
const lastReq = (frag) => [...reqs].reverse().find((u) => u.includes(frag)) ?? '';
const settle = () => page.waitForTimeout(600);
async function viewSetting(sel) {
  if (!(await page.locator('.vs-popover').count())) await page.click('.vs-wrap .icon-btn');
  await page.click(sel);
  await page.keyboard.press('Escape');
}
const count = (sel) => page.locator(sel).count();
const text = (sel) => page.locator(sel).first().innerText();

await page.goto(URL_, { waitUntil: 'networkidle' });
await page.evaluate(() => localStorage.clear());
await page.reload({ waitUntil: 'networkidle' });
await settle();

// Kind tabs
const allCards = await count('.class-card');
reqs = [];
await page.click('.kind-tab:has(.tab-label[data-label="Figure"])'); await settle();
const figCards = await count('.class-card');
const nonFig = await page.locator('.class-card .badge:not(.badge-type-figure)').count();
check('Kind tab Figure filters classes', figCards > 0 && figCards < allCards && nonFig === 0, `${allCards}→${figCards}`);
check('Kind tab sends kind_filter=figure', lastReq('/api/classes').includes('kind_filter=figure'));
await page.click('.kind-tab:has(.tab-label[data-label="All"])'); await settle();

// Class select + detailed rows
await page.click('.class-card[title="AridityIndex"]'); await settle();
check('Class click loads entries', (await count('tr.row-entry')) === 8);
check('Class click auto-opens first entry', (await count('tr.row-entry.active')) === 1 && (await count('.dcard')) > 1);
check('Detailed shows param rows', (await count('tr.row-param')) > 0);
check('Count chip shows selection', (await text('.count-chip')) === '8 shown', await text('.count-chip'));

// Compact / Detailed
reqs = [];
await page.click('.kind-tab[aria-label=Compact]'); await settle();
check('Compact renders pills', (await count('.entry-pill')) === 8 && (await count('tr.row-param')) === 0);
check('Compact requests row_display=none', lastReq('/api/class-entries').includes('row_display=none'));
await page.click('.vs-wrap .icon-btn');
const segDisabled = await page.locator('.vs-group.disabled .vs-seg-btn:disabled').count();
await page.keyboard.press('Escape');
check('Compact disables param segment', segDisabled === 2);
await page.click('.kind-tab[aria-label=Detailed]'); await settle();
check('Detailed restores table', (await count('tr.row-param')) > 0);

// Selected / All params
await page.click('#top, body', { position: { x: 5, y: 5 } }).catch(() => {});
await page.click('.sb-section-hd:has-text("Search")');
await page.fill('.filter-row input', 'SSP370'); await page.waitForTimeout(900);
check('Search filter narrows entries', (await count('tr.row-entry')) === 2, `${await count('tr.row-entry')} rows`);
check('Search filter pill shown', (await count('.pill-filter')) === 1);
reqs = [];
await viewSetting('.vs-seg-btn:text-is("Selected")'); await settle();
check('Selected params sends row_display=selected', lastReq('/api/class-entries').includes('row_display=selected'));
const selRows = await count('tr.row-param');
await viewSetting('.vs-seg-btn:text-is("All")'); await settle();
const allRows = await count('tr.row-param');
check('Selected params shows fewer rows than All', selRows < allRows, `${selRows} vs ${allRows}`);
await page.click('.filter-row .rm-filter-btn'); await page.waitForTimeout(800);
check('Clearing filter restores entries', (await count('tr.row-entry')) === 8);

// Logic mode
reqs = [];
await page.click('.logic-row .kind-tab:text-is("OR")'); await settle();
check('Logic OR sent', lastReq('/api/classes').includes('logic_mode=OR'));
await page.click('.logic-row .kind-tab:text-is("AND")'); await settle();

// Hide stale
reqs = [];
await viewSetting('.vs-row:has-text("Hide stale")'); await settle();
check('Hide stale sends hide_stale=1', lastReq('/api/classes').includes('hide_stale=1') && lastReq('/api/class-entries').includes('hide_stale=1'));
await page.click('.vs-wrap .icon-btn');
const staleOn = await count('.vs-row[aria-checked=true]:has-text("Hide stale")');
await page.keyboard.press('Escape');
check('Hide stale active + persisted', staleOn === 1 && (await page.evaluate(() => localStorage.getItem('hide_stale'))) === 'true');
await viewSetting('.vs-row:has-text("Hide stale")'); await settle();

// Select mode + cart
const iconVisible = () => page.locator('tr.row-entry .select-icon').first().isVisible();
check('Select icons hidden by default', !(await iconVisible()));
await page.click('.kind-tab[aria-label=Select]'); await settle();
check('Select shows +/− icons', await iconVisible());
await page.locator('tr.row-entry .select-icon').nth(1).click(); await settle();
check('Adding to cart badges Export tab', (await text('.view-tab .tab-badge')) === '1');
check('Cart row highlighted', (await count('tr.row-entry.selected-for-export')) === 1);
await page.click('.kind-tab[aria-label=Select]'); await settle();
check('Leaving select mode keeps cart', (await count('.view-tab .tab-badge')) === 1);

// Spec pill
await page.click('.sb-section-hd:has-text("Spec filters")');
reqs = [];
await page.click('.spec-pill:text-is("EPSG:4326")'); await settle();
check('Spec pill sends spec_filters', lastReq('/api/classes').includes('"crs":["EPSG:4326"]'));
check('Spec pill shows filter pill', (await count('.pill-filter')) === 1);
await page.click('.pill-filter .pill-rm'); await settle();

// Snapshot select
await page.click('.sb-section-hd:has-text("Snapshots")');
const opts = await page.locator('.version-select option').count();
if (opts > 1) {
  reqs = [];
  await page.selectOption('.version-select', { index: 1 }); await settle();
  check('Snapshot select sends version_filter', lastReq('/api/classes').includes('version_filter='));
  check('Snapshot pill shown', (await count('.pill-filter:has-text("Snapshot")')) === 1);
} else check('Snapshot select has options', false);

// Clear all
await page.click('.clear-all-btn'); await settle();
check('Clear all empties pills + selection', (await count('.pill')) === 0 && (await count('tr.row-entry')) === 0);

// Show empty
const before = await count('.class-card');
await viewSetting('.vs-row:has-text("Show empty")'); await settle();
check('Show empty adds empty classes', (await count('.class-card')) > before, `${before}→${await count('.class-card')}`);
await viewSetting('.vs-row:has-text("Show empty")'); await settle();

// Multi-select
await viewSetting('.vs-row:has-text("Multi-select")');
await page.click('.class-card[title="AridityIndex"]'); await settle();
await page.click('.class-card[title="CountModel"]'); await settle();
check('Multi-select keeps both classes', (await count('.class-card.filtered')) === 2 && (await count('.pill:not(.pill-filter)')) === 2);
await viewSetting('.vs-row:has-text("Multi-select")'); await settle();
check('Multi-select off keeps last class', (await count('.class-card.filtered')) === 1);

// Cmd-click additive
await page.click('.class-card[title="AridityIndex"]', { modifiers: ['Meta'] }); await settle();
check('⌘-click adds class', (await count('.class-card.filtered')) === 2);

// Sidebar collapse
await page.click('.sidebar-collapse-btn'); await settle();
const w = await page.locator('.sidebar').evaluate((el) => el.getBoundingClientRect().width);
check('Sidebar collapses', w === 44, `${w}px`);
await page.click('.sidebar-collapse-btn'); await settle();

// Pane resizers persist; double-click resets
async function drag(sel, dx) {
  const hb = await page.locator(sel).boundingBox();
  await page.mouse.move(hb.x + 3, hb.y + 300); await page.mouse.down();
  await page.mouse.move(hb.x + 3 + dx, hb.y + 300, { steps: 5 }); await page.mouse.up();
}
const paneW = (sel) => page.locator(sel).evaluate((el) => el.getBoundingClientRect().width);
const dw0 = await paneW('.detail-pane');
await drag('.detail-pane > .resizer', -150);
const sw0 = await paneW('.sidebar');
await drag('.sidebar > .resizer', 60);
const dw = await paneW('.detail-pane');
const sw = await paneW('.sidebar');
await page.reload({ waitUntil: 'networkidle' }); await settle();
const dw2 = await paneW('.detail-pane');
const sw2 = await paneW('.sidebar');
check('Detail pane resizes and persists', Math.abs(dw - dw2) < 2 && dw > dw0 + 100, `${dw0} → ${dw} / ${dw2}`);
check('Sidebar resizes and persists', Math.abs(sw - sw2) < 2 && sw > sw0 + 40, `${sw0} → ${sw} / ${sw2}`);
await page.dblclick('.sidebar > .resizer'); await settle();
check('Double-click resets sidebar width', Math.abs((await paneW('.sidebar')) - sw0) < 2);

// Arrow keys
await page.click('.class-card[title="AridityIndex"]'); await settle();
await page.keyboard.press('ArrowDown'); await settle();
const activeIdx = await page.locator('tr.row-entry').evaluateAll((rows) => rows.findIndex((r) => r.classList.contains('active')));
check('ArrowDown moves to next entry', activeIdx === 1, `idx ${activeIdx}`);
await page.keyboard.press('Meta+['); await settle();
const backIdx = await page.locator('tr.row-entry').evaluateAll((rows) => rows.findIndex((r) => r.classList.contains('active')));
check('⌘[ goes back', backIdx === 0, `idx ${backIdx}`);

// Parameters card collapsed by default
check('Parameter nodes start collapsed', (await count('.dcard-body--params .jx-depth-1')) === 0);
await page.click('.dcard--params button[title="Expand all"]'); await settle();
check('Expand all opens nested nodes', (await count('.dcard-body--params .jx-depth-1')) > 0 || (await count('.dcard-body--params .jx-toggle')) === 0);

// Theme
await viewSetting('.vs-seg-btn:text-is("Dark")'); await settle();
check('Theme switches to dark', (await page.evaluate(() => document.documentElement.dataset.theme)) === 'dark');
await page.evaluate(() => localStorage.setItem('pgb-theme', 'light'));

// Quick switcher
await page.keyboard.press('Meta+k'); await settle();
check('⌘K opens quick switcher', (await count('.qs')) === 1);
await page.keyboard.type('figure1'); await settle();
await page.keyboard.press('Enter'); await settle();
check('Switcher jumps to class', (await count('.class-card.filtered[title="Figure1"]')) === 1 && (await count('.qs')) === 0);
const fig1 = await page.locator('tr.row-entry').first().getAttribute('data-entry');
await page.click('.class-card[title="AridityIndex"]'); await settle();
await page.click('.search-btn');
await page.keyboard.type(fig1.slice(0, 8)); await page.waitForTimeout(800);
const entryRows = await count('.qs-row:has(.qs-mono)');
await page.keyboard.press('Enter'); await settle();
check('Switcher finds entry by hash prefix', entryRows === 1 && (await count(`tr.row-entry.active[data-entry="${fig1}"]`)) === 1, `${entryRows} hits`);
await page.keyboard.press('Meta+k'); await settle();
await page.keyboard.type('v2'); await page.waitForTimeout(800);
await page.locator('.qs-row:has-text("v2")').first().click(); await page.waitForTimeout(2500);
check('Switcher opens a code version', (await count('.view-tab.active:has-text("Code")')) === 1 && (await count('.code-version-item.active:has-text("v2")')) === 1);
await page.click('.view-tab:has-text("Entries")'); await settle();

// Tabs carry the class selection between Entries and Code
await page.click('.class-card[title="AridityIndex"]'); await settle();
await page.click('.view-tab:has-text("Code")'); await page.waitForTimeout(2500);
check('Code tab opens the selected class', (await count('.code-class-item.active:has-text("AridityIndex")')) === 1);
await page.locator('.code-class-item:has-text("CountModel")').first().click(); await page.waitForTimeout(1500);
await page.click('.view-tab:has-text("Entries")'); await settle();
check('Entries tab selects the code class', (await count('.class-card.filtered[title="CountModel"]')) === 1);

// Pins (the check unpins again, leaving the project's pins as they were)
await page.click('.class-card[title="Figure1"]'); await settle();
const wasPinned = (await count('.pin-btn.active')) === 1;
if (wasPinned) { await page.click('.pin-btn'); await settle(); }
await page.click('.pin-btn'); await settle();
check('Pin button pins the entry', (await count('.pin-btn.active')) === 1);
check('Class shows pin marker', (await count('.class-card[title="Figure1"] .class-card-pins')) === 1);
check('Pinned row shows its pin', (await count('tr.row-entry.active .entry-pin.active')) === 1);
await page.click('tr.row-entry.active .entry-pin'); await settle();
const rowUnpinned = (await count('tr.row-entry.active .entry-pin.active')) === 0 && (await count('.pin-btn.active')) === 0;
await page.click('tr.row-entry.active .entry-pin'); await settle();
check('Row pin toggles', rowUnpinned && (await count('.pin-btn.active')) === 1);
const pinTotal = Number(await page.locator('.kind-tab--pinned .tab-badge').innerText());
await page.click('.class-card[title="Figure1"]'); await settle(); // deselect the class
await page.click('.kind-tab--pinned'); await settle();
check(
  'Pinned pill shows only pinned entries',
  (await count('tr.row-entry')) === pinTotal && (await count('tr.row-entry:has(.entry-pin:not(.active))')) === 0,
  `${await count('tr.row-entry')} rows / ${pinTotal} pins`,
);
check('Pinned view narrows the class list', (await count('.class-card')) <= pinTotal && (await count('.class-card[title="Figure1"]')) === 1);
await page.click('.kind-tab--pinned'); await settle();
await page.click('.class-card[title="Figure1"]'); await settle();
await page.reload({ waitUntil: 'networkidle' }); await settle();
check('Pin persists across reload', (await count('.class-card[title="Figure1"] .class-card-pins')) === 1);
await page.click('.class-card[title="Figure1"]'); await settle();
await page.click('.pin-btn'); await settle();
check('Unpin clears markers', (await count('.class-card-pins')) === 0 || (await count('.class-card[title="Figure1"] .class-card-pins')) === 0);
if (wasPinned) { await page.click('.pin-btn'); await settle(); }

// Views
await page.click('.view-tab:has-text("Export")'); await settle();
check('Export view lists cart', (await count('.view-export tr.row-entry')) === 1);
await page.click('.view-tab:has-text("Code")'); await page.waitForTimeout(2500);
check('Code view lists versions', (await count('.code-version-item')) > 0);
check('Code view shows source pane', (await count('.code-source-panel table, .tree-diff-class')) > 0);
await page.click('.kind-tab:has(.tab-label[data-label="By class"])'); await page.waitForTimeout(1500);
check('By class lists classes', (await count('.code-pane--versions .code-class-item')) > 0);
await page.click('.kind-tab:has(.tab-label[data-label="By version"])'); await page.waitForTimeout(1200);

console.log(results.join('\n'));
console.log(`\n${results.filter((r) => r.startsWith('PASS')).length}/${results.length} passed`);
if (errors.length) console.log('errors:\n' + errors.join('\n'));
await browser.close();
