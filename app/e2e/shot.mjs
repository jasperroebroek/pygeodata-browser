// usage: node shot.mjs <name> <url> [steps-json]
// steps: [{click:sel}|{wait:ms}|{waitFor:sel}|{type:[sel,text]}|{eval:js}|{shot:name}|{press:key}|{hover:sel}]
import { createRequire } from 'module';
const require = createRequire('/usr/local/lib/node_modules/');
const { chromium } = require('playwright');
const [,, name, url, stepsJson = '[]'] = process.argv;
const OUT = new URL('./shots/', import.meta.url).pathname;
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 1 });
const logs = [];
page.on('console', m => { if (['error','warning'].includes(m.type())) logs.push(`[${m.type()}] ${m.text()}`); });
page.on('pageerror', e => logs.push(`[pageerror] ${e.message}`));
const t0 = Date.now();
await page.goto(url, { waitUntil: 'networkidle' });
console.log(`loaded ${Date.now() - t0}ms`);
for (const s of JSON.parse(stepsJson)) {
  const t = Date.now();
  if (s.click) await page.click(s.click);
  if (s.dbl) await page.dblclick(s.dbl);
  if (s.hover) await page.hover(s.hover);
  if (s.wait) await page.waitForTimeout(s.wait);
  if (s.waitFor) await page.waitForSelector(s.waitFor);
  if (s.idle) await page.waitForLoadState('networkidle');
  if (s.type) await page.fill(s.type[0], s.type[1]);
  if (s.press) await page.keyboard.press(s.press);
  if (s.eval) console.log('eval:', JSON.stringify(await page.evaluate(s.eval)));
  if (s.shot) await page.screenshot({ path: `${OUT}${name}-${s.shot}.png`, fullPage: !!s.full });
  if (s.click || s.waitFor) console.log(`step ${JSON.stringify(s)} ${Date.now() - t}ms`);
}
await page.screenshot({ path: `${OUT}${name}.png` });
if (logs.length) console.log(logs.join('\n'));
await browser.close();
