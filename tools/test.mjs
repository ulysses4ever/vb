// Headless-browser checks for site/index.html + site/data.json.
//
//   npm install            (once; pulls puppeteer and a local Chart.js copy)
//   npm test               (or: node tools/test.mjs)
//   SCREENSHOTS=1 npm test (also writes PNGs to tools/screenshots/)
//
// Serves site/ itself, so no other web server is needed. Chart.js and Google Fonts
// requests are answered locally, so the run works offline. In a sandbox without a
// downloadable Chrome, CHROMIUM=sparticuz uses puppeteer-core + @sparticuz/chromium.
import assert from 'node:assert/strict';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(fileURLToPath(new URL('..', import.meta.url)));
const SITE = path.join(ROOT, 'site');
const SHOTS = process.env.SCREENSHOTS ? path.join(ROOT, 'tools', 'screenshots') : null;
const CHART_JS = path.join(ROOT, 'node_modules', 'chart.js', 'dist', 'chart.umd.js');
const CHART_URL = 'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js';
const data = JSON.parse(fs.readFileSync(path.join(SITE, 'data.json'), 'utf8'));

// ---- tiny static server ----
const TYPES = { '.html': 'text/html; charset=utf-8', '.json': 'application/json', '.js': 'text/javascript' };
const server = http.createServer((req, res) => {
  const p = path.join(SITE, decodeURIComponent(new URL(req.url, 'http://x').pathname).replace(/\/$/, '/index.html'));
  if (!p.startsWith(SITE)) { res.writeHead(403); return res.end(); }
  fs.readFile(p, (err, body) => {
    if (err) { res.writeHead(404); return res.end('not found'); }
    res.writeHead(200, { 'content-type': TYPES[path.extname(p)] || 'application/octet-stream' });
    res.end(body);
  });
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const BASE = `http://127.0.0.1:${server.address().port}/`;

async function launch() {
  if (process.env.CHROMIUM === 'sparticuz') {
    const { default: chromium } = await import('@sparticuz/chromium');
    const { default: puppeteer } = await import('puppeteer-core');
    return puppeteer.launch({ executablePath: await chromium.executablePath(), args: chromium.args, headless: true });
  }
  const { default: puppeteer } = await import('puppeteer');
  return puppeteer.launch({ headless: true });
}
const browser = await launch();
const chartJs = fs.existsSync(CHART_JS) ? fs.readFileSync(CHART_JS) : null;

async function open(query = '', { width = 390, height = 844, dark = false, blockCdn = false } = {}) {
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => {
    const t = m.text();
    if (m.type() !== 'error' || /404/.test(t) || (blockCdn && /Failed to load resource/.test(t))) return;
    errors.push(t);
  });
  await page.setRequestInterception(true);
  page.on('request', (r) => {
    const u = r.url();
    if (u.startsWith('https://')) {
      if (blockCdn) return r.abort();
      if (u === CHART_URL && chartJs) return r.respond({ status: 200, contentType: 'text/javascript', body: chartJs });
      if (u.startsWith('https://fonts.')) return r.respond({ status: 200, contentType: 'text/css', body: '' });
    }
    return r.continue();
  });
  await page.setViewport({ width, height, deviceScaleFactor: 2 });
  await page.emulateMediaFeatures([{ name: 'prefers-color-scheme', value: dark ? 'dark' : 'light' }]);
  await page.goto(BASE + 'index.html' + query, { waitUntil: 'networkidle0' });
  await page.waitForFunction(() => !document.getElementById('table-sec').hidden || !document.getElementById('error').hidden, { timeout: 10000 });
  return { page, errors };
}
const text = (page, sel) => page.$eval(sel, (e) => e.textContent.replace(/\s+/g, ' ').trim());
const overflow = (page) => page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
const shot = (page, name) => SHOTS && page.screenshot({ path: path.join(SHOTS, `${name}.png`), fullPage: true });
if (SHOTS) fs.mkdirSync(SHOTS, { recursive: true });

let passed = 0;
async function check(name, fn) {
  try { await fn(); passed++; console.log(`ok   ${name}`); } catch (e) { console.error(`FAIL ${name}\n     ${e.message}`); process.exitCode = 1; }
}

// Expected values for the latest bulletin, EB-2 rest of world (the page's default queue).
const latest = data.bulletins.reduce((a, b) => (a.month > b.month ? a : b));
const chartKey = latest.uscis_chart === 'final' ? 'final' : 'filing';
const fileCutoff = latest[chartKey]['EB-2']?.ROW;
const addDays = (iso, n) => new Date(Date.parse(`${iso}T00:00:00Z`) + n * 864e5).toISOString().slice(0, 10);

await check('phone, light: loads every bulletin with no errors or sideways scroll', async () => {
  const { page, errors } = await open('?category=EB-2&country=ROW');
  assert.match(await text(page, '#coverage'), new RegExp(`^${data.bulletins.length} bulletins`));
  assert.equal(await page.$$eval('#rows tr', (r) => r.length), data.bulletins.length);
  assert.equal(await page.$$eval('#rows td.in-force', (c) => c.length), data.bulletins.filter((b) => b.uscis_chart).length);
  assert.equal(await overflow(page), 0);
  assert.deepEqual(errors, []);
  await shot(page, 'phone-light');
  await page.close();
});

await check('priority date before / after the filing cutoff gives "Can file" / "Not yet"', async () => {
  if (!fileCutoff || fileCutoff === 'U') return;
  const { page } = await open('?category=EB-2&country=ROW');
  const setPd = (v) => page.$eval('#pd', (el, v) => { el.value = v; el.dispatchEvent(new Event('change', { bubbles: true })); }, v);
  const before = fileCutoff === 'C' ? '2000-01-01' : addDays(fileCutoff, -1);
  await setPd(before);
  assert.match(await text(page, '#ro-verdict'), /^Can file/);
  if (fileCutoff !== 'C') {
    await setPd(fileCutoff);                        // equal to the cutoff is not "earlier than" it
    assert.match(await text(page, '#ro-verdict'), /^Not yet/);
  }
  await page.close();
});

await check('chart: hover and arrow keys show the tooltip', async () => {
  const { page } = await open('?category=EB-2&country=ROW');
  await page.$eval('#chart-sec', (c) => c.scrollIntoView({ block: 'center' }));
  const box = await page.$eval('#chart', (c) => { const r = c.getBoundingClientRect(); return { x: r.left, y: r.top, w: r.width, h: r.height }; });
  await page.mouse.move(box.x + box.w * 0.3, box.y + box.h * 0.5, { steps: 3 });
  assert.match(await page.$eval('#tip', (t) => (t.hidden ? '' : t.innerText)), /bulletin/);
  await page.mouse.move(1, 1);
  await page.focus('#chart');
  await page.keyboard.press('Home');
  const first = data.bulletins.reduce((a, b) => (a.month < b.month ? a : b)).month;
  const [y, m] = first.split('-').map(Number);
  const firstLabel = `${new Date(Date.UTC(y, m - 1, 1)).toLocaleString('en-US', { month: 'long', timeZone: 'UTC' })} ${y}`;
  assert.match(await page.$eval('#tip', (t) => (t.hidden ? '' : t.innerText)), new RegExp(firstLabel));
  await page.close();
});

await check('years scale for long queues (EB-2 India)', async () => {
  const { page, errors } = await open('?category=EB-2&country=IN');
  const ticks = await page.evaluate(() => Chart.getChart('chart').scales.y.ticks.map((t) => t.label));
  assert.ok(ticks.some((t) => /yr$/.test(t)), `ticks: ${ticks}`);
  assert.deepEqual(errors, []);
  await page.close();
});

await check('phone, dark: no errors or sideways scroll', async () => {
  const { page, errors } = await open('?category=EB-2&country=ROW', { dark: true });
  assert.equal(await overflow(page), 0);
  assert.deepEqual(errors, []);
  await shot(page, 'phone-dark');
  await page.close();
});

await check('desktop: no errors or sideways scroll', async () => {
  const { page, errors } = await open('?category=EB-3&country=ROW', { width: 1280, height: 900 });
  assert.equal(await page.$eval('#cat', (s) => s.value), 'EB-3');
  assert.equal(await overflow(page), 0);
  assert.deepEqual(errors, []);
  await shot(page, 'desktop-light');
  await page.close();
});

await check('missing data file shows an error message', async () => {
  const { page } = await open('?data=nope.json');
  assert.match(await text(page, '#error'), /Couldn't load nope\.json: the server answered 404/);
  await page.close();
});

await check('without the chart library the table still renders', async () => {
  const { page, errors } = await open('', { blockCdn: true });
  assert.equal(await page.$eval('#chart-fallback', (e) => !e.hidden), true);
  assert.equal(await page.$$eval('#rows tr', (r) => r.length), data.bulletins.length);
  assert.deepEqual(errors, []);
  await page.close();
});

await browser.close();
server.close();
console.log(`${passed} checks passed${process.exitCode ? ', some failed' : ''}`);
