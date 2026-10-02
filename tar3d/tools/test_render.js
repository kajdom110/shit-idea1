// Phase 7 render tests: angle grid, reference views, scroll sweep, drag rotation, stats.
//
//   python3 -m http.server 8765            # from the repository root
//   node tar3d/tools/test_render.js [angles|views|scroll|drag|stats|all] [outDir]
//
// Needs Playwright with Chromium. THREE_LOCAL=/path/to/three/package serves three.js from disk
// instead of the CDN (for machines without internet access).
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const BASE = process.env.BASE_URL || 'http://localhost:8765/tar3d/preview.html?test';
const which = process.argv[2] || 'all';
const OUT = process.argv[3] || 'docs/tar-3d/test';
fs.mkdirSync(OUT, { recursive: true });

async function open(viewport = { width: 1440, height: 900 }) {
  const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const page = await browser.newPage({ viewport });
  const errors = [];
  page.on('console', (m) => { if (m.type() === 'error' && !/fonts\.g|ERR_CERT|ERR_FAILED/.test(m.text())) errors.push(m.text()); });
  page.on('pageerror', (e) => errors.push(e.message));
  if (process.env.THREE_LOCAL) {
    await page.route('https://cdn.jsdelivr.net/npm/three@0.160.0/**', (r) => {
      const f = path.join(process.env.THREE_LOCAL, r.request().url().split('three@0.160.0/')[1]);
      r.fulfill({ body: fs.readFileSync(f), contentType: 'application/javascript' });
    });
  }
  await page.route('https://fonts.googleapis.com/**', (r) => r.abort());
  await page.goto(BASE);
  await page.waitForFunction(() => window.__tar && window.__tar.ready(), null, { timeout: 120000 });
  await page.waitForTimeout(500);
  return { browser, page, errors };
}

const settle = (page, ms = 700) => page.waitForTimeout(ms);

async function angles() {
  const { browser, page, errors } = await open({ width: 900, height: 1000 });
  for (const pitch of [-60, -30, 0, 30, 60]) {
    for (let yaw = 0; yaw < 360; yaw += 45) {
      await page.evaluate(([y, p]) => window.__tar.pose(y, p, { dist: 230 }), [yaw, pitch]);
      await settle(page);
      await page.screenshot({ path: `${OUT}/angle_y${yaw}_p${pitch}.png` });
    }
  }
  await browser.close();
  return errors;
}

async function views() {
  const { browser, page, errors } = await open({ width: 1000, height: 1000 });
  const V = {
    front: [0, 0, { dist: 230 }], side: [-90, 0, { dist: 230 }], back: [180, 0, { dist: 230 }],
    body_front: [0, 0, { dist: 120, target: [0, 19, -8] }],
    body_three_quarter_back: [150, 0, { dist: 160, target: [0, 30, -8] }],
    head: [0, 0, { dist: 45, target: [0, 88, -0.8] }],
    head_end_on: [0, 70, { dist: 55, target: [0, 88, -0.8] }],
    neck_close: [-20, 10, { dist: 40, target: [0, 62, 0] }],
    heel: [200, 10, { dist: 55, target: [0, 36, -6] }],
  };
  for (const [name, [yaw, pitch, opts]] of Object.entries(V)) {
    await page.evaluate(([y, p, o]) => window.__tar.pose(y, p, o), [yaw, pitch, opts]);
    await settle(page);
    await page.screenshot({ path: `${OUT}/view_${name}.png` });
  }
  await browser.close();
  return errors;
}

async function scroll() {
  const { browser, page, errors } = await open({ width: 1440, height: 900 });
  const steps = [];
  for (let i = 0; i <= 20; i++) steps.push(i / 20);
  for (const [dir, list] of [['down', steps], ['up', [...steps].reverse()]]) {
    for (const p of list) {
      await page.evaluate((v) => window.__tar.scroll(v), p);
      await settle(page, 500);
      if (dir === 'down' || [0, 0.5, 1].includes(p)) await page.screenshot({ path: `${OUT}/scroll_${dir}_${String(Math.round(p * 100)).padStart(3, '0')}.png` });
    }
  }
  await browser.close();
  return errors;
}

async function drag() {
  const { browser, page, errors } = await open({ width: 1440, height: 900 });
  await page.evaluate(() => window.__tar.scroll(0.22));
  await settle(page, 800);
  const moves = { right: [300, 0], left: [-300, 0], down: [0, 250], up: [0, -250], diagonal: [220, 180] };
  const results = {};
  for (const [name, [dx, dy]] of Object.entries(moves)) {
    await page.mouse.move(720, 450);
    await page.mouse.down();
    for (let k = 1; k <= 15; k++) await page.mouse.move(720 + (dx * k) / 15, 450 + (dy * k) / 15);
    await page.mouse.up();
    await settle(page, 300);
    results[name] = await page.evaluate(() => window.__tar.userQuaternion());
    await page.screenshot({ path: `${OUT}/drag_${name}.png` });
    // coast: how much further it turned in the first simulated second after letting go
    const before = results[name];
    await page.evaluate(() => window.__tar.advance(1));
    results[name + '_coast'] = await page.evaluate(() => window.__tar.userQuaternion());
    results[name + '_coastFrom'] = before;
    await page.mouse.dblclick(720, 450);
    await page.evaluate(() => window.__tar.advance(4));
    await settle(page, 300);
  }
  results.afterReturn = await page.evaluate(() => window.__tar.userQuaternion());
  fs.writeFileSync(`${OUT}/drag.json`, JSON.stringify(results, null, 2));
  await browser.close();
  return errors;
}

async function poster() {
  // still image of the final model, for the loading screen and browsers without WebGL
  const { browser, page, errors } = await open({ width: 1200, height: 1500 });
  await page.evaluate(() => window.__tar.pose(-35, 6, { dist: 250 }));
  await settle(page, 1200);
  await page.screenshot({ path: `${OUT}/poster.png` });
  await browser.close();
  return errors;
}

async function stats() {
  const { browser, page, errors } = await open({ width: 1440, height: 900 });
  await page.evaluate(() => window.__tar.scroll(0.22));
  await settle(page, 800);
  const s = await page.evaluate(() => window.__tar.stats());
  fs.writeFileSync(`${OUT}/stats.json`, JSON.stringify(s, null, 2));
  console.log('stats', s);
  await browser.close();
  return errors;
}

(async () => {
  const tasks = { angles, views, scroll, drag, stats, poster };
  const run = which === 'all' ? Object.keys(tasks) : [which];
  for (const name of run) {
    const errors = await tasks[name]();
    console.log(name, errors.length ? 'errors: ' + errors.join(' | ') : 'no console errors');
  }
})();
