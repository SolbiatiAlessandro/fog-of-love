#!/usr/bin/env node
/* Headless-Chrome smoke test for the Love Town 3D viewer's HTML layer and bridge.
 *
 *   node tools/polyworld_viewer_smoke.js --stub            # HUD + bridge against polyworld_viewer/stub_scene.js
 *   node tools/polyworld_viewer_smoke.js --dir docs/replay3d  # a built bundle (wasm); WebGL may be unavailable headless
 *   options: --run <name> --t <seconds> --shot <png> --chrome <path> --seconds <wait>
 *
 * Needs puppeteer-core (npm install --no-save puppeteer-core) and a Chrome binary. Exit 1 on failure.
 */
const fs = require('fs');
const os = require('os');
const path = require('path');
const http = require('http');

const args = process.argv.slice(2);
const opt = (name, dflt) => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : dflt; };
const stub = args.includes('--stub');
const repo = path.resolve(__dirname, '..');
const run = opt('--run', 'dev-24x10-s4-market');
const t = Number(opt('--t', '40'));
const wait = Number(opt('--seconds', '6'));
const chrome = opt('--chrome', process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome');
const shot = opt('--shot', null);

let dir = opt('--dir', null);
if (stub) {
  dir = fs.mkdtempSync(path.join(os.tmpdir(), 'lovetown-stub-'));
  const viewer = path.join(repo, 'polyworld_viewer');
  for (const f of ['replay_ui.js', 'replay_state.js', 'replay_ui.css', 'stub_scene.js']) fs.copyFileSync(path.join(viewer, f), path.join(dir, f));
  fs.cpSync(path.join(repo, 'docs/replay3d/replays'), path.join(dir, 'replays'), { recursive: true });
  const shell = fs.readFileSync(path.join(viewer, 'web_shell.html'), 'utf8');
  fs.writeFileSync(path.join(dir, 'index.html'), shell.replace('{{{ SCRIPT }}}', '<script src="stub_scene.js"></script>'));
}
if (!dir) { console.error('need --stub or --dir'); process.exit(2); }
dir = path.resolve(dir);

const types = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.wasm': 'application/wasm', '.data': 'application/octet-stream', '.png': 'image/png' };
const server = http.createServer((req, res) => {
  const file = path.join(dir, decodeURIComponent(req.url.split('?')[0]).replace(/\/$/, '/index.html'));
  if (!file.startsWith(dir) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) { res.writeHead(404); res.end(); return; }
  res.writeHead(200, { 'Content-Type': types[path.extname(file)] || 'application/octet-stream' });
  fs.createReadStream(file).pipe(res);
});

(async () => {
  let puppeteer;
  try { puppeteer = require('puppeteer-core'); } catch (e) { console.error('npm install --no-save puppeteer-core'); process.exit(2); }
  await new Promise((r) => server.listen(0, '127.0.0.1', r));
  const url = `http://127.0.0.1:${server.address().port}/index.html?run=${run}&t=${t}&auto=0`;
  const browser = await puppeteer.launch({ executablePath: chrome, headless: true, args: ['--no-sandbox', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--window-size=1400,1100'] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1400, height: 1100 });
  const errors = [], logs = [];
  page.on('console', (m) => { logs.push(`${m.type()}: ${m.text()}`); if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) errors.push(m.text()); });
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('response', (r) => { if (r.status() >= 400 && !/favicon/.test(r.url())) errors.push(`${r.status()} ${r.url()}`); });
  await page.goto(url, { waitUntil: 'load' });
  await new Promise((r) => setTimeout(r, wait * 1000));
  const result = await page.evaluate(() => {
    const M = window.Module || {};
    const state = typeof M.lovetownState === 'function' ? M.lovetownState() : M.lovetownState;
    const q = (s) => document.querySelectorAll(s).length;
    const webgl = (() => { try { const c = document.createElement('canvas'); return !!(c.getContext('webgl2') || c.getContext('webgl')); } catch (e) { return false; } })();
    return {
      status: document.getElementById('status').hidden ? 'hidden' : document.getElementById('status').textContent,
      loadStatus: document.getElementById('load-status').textContent,
      clock: document.getElementById('clock').textContent,
      caption: document.getElementById('scene-caption').textContent,
      cards: q('.card'), labelsVisible: q('.agent-label:not([hidden])'), bubbles: q('.bubble'), matches: q('.match'), transcript: q('.transcript li'),
      runs: q('#runs option'), gossip: q('#gossip li'), orders: q('#orders tr'), marketCanvas: (document.getElementById('market') || {}).width || 0,
      bridge: state ? { t: state.t, day: state.day, phase: state.phase, followed: state.followed, agents: (state.agents || []).length, hasSx: !!(state.agents || [])[0] && typeof state.agents[0].sx === 'number' } : null,
      ready: M.lovetownReady === true || typeof M.lovetownReady === 'function', pendingCommands: (M.lovetownCommand || []).length, webgl,
      noScene: !!window.LOVETOWN_NO_SCENE, transcriptColumn: q('#transcript-col.show'), liveDates: q('#date-live article'),
    };
  });
  if (shot) { await page.screenshot({ path: shot, fullPage: false }); result.screenshot = shot; }
  await browser.close();
  server.close();
  const failures = [];
  if (result.cards < 1) failures.push('no dating-app cards');
  if (result.runs < 1) failures.push('run picker empty');
  if (!result.bridge && !result.noScene) failures.push('Module.lovetownState never written');
  if (result.noScene && result.transcriptColumn < 1) failures.push('no-scene bundle must show the transcript column');
  else if (result.bridge && result.bridge.hasSx && result.labelsVisible < 1) failures.push('no positioned agent labels');
  if (result.bridge && result.bridge.hasSx && result.bubbles < 1 && result.bridge.phase === 'date') failures.push('no speech bubble during a date');
  if (result.pendingCommands > 5) failures.push(`commands not drained (${result.pendingCommands})`);
  if (errors.length) failures.push(`console errors: ${errors.slice(0, 3).join(' | ')}`);
  console.log(JSON.stringify(result, null, 1));
  if (failures.length) { console.error('FAIL: ' + failures.join('; ')); console.error(logs.slice(-10).join('\n')); process.exit(1); }
  console.log(`OK (${stub ? 'stub scene' : dir})`);
})().catch((e) => { console.error(e); process.exit(1); });
