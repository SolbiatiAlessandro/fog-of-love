/* Love Town HUD around the Polyworld WebAssembly scene. Vanilla JS, no build step.
 *
 * Bridge (docs/POLYWORLD_REPLAY.md): the HUD pushes command strings onto Module.lovetownCommand
 * and polls Module.lovetownState every animation frame. Without a scene (window.LOVETOWN_NO_SCENE,
 * or the wasm never reporting ready) the HUD runs on its own clock and shows the transcript column.
 */
var Module = {
  locateFile: (file, prefix) => prefix + file + '?v=lovetown-1',
  canvas: document.getElementById('canvas'),
  arguments: ['/replay.json'],
  lovetownCommand: [],
  // The Nim side calls lovetownState(stateObject) once per frame (or assigns an object to it);
  // the HUD reads the latest value back by calling it without arguments.
  lovetownState: function (state) { if (state && typeof state === 'object') Module.lovetownLatest = state; return Module.lovetownLatest || null; },
  lovetownLatest: null,
  lovetownReady: false,
  lovetownDocument: null,
};
// Windy focuses the canvas at startup; keep the page at the top.
Module.canvas.focus = function (options) { HTMLElement.prototype.focus.call(this, { ...options, preventScroll: true }); };

(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const D = window.LoveTownReplay;
  const esc = (v) => String(v == null ? '' : v).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const initials = (name) => String(name).split(/\s+/).map((p) => p[0]).join('').slice(0, 2).toUpperCase();
  const firstName = (name) => String(name || '').split(/\s+/)[0];
  const fmtCash = (v) => (typeof v === 'number' ? v.toFixed(0) : '—');
  const fmtPrice = (v) => (typeof v === 'number' ? (v >= 100 ? v.toFixed(0) : v.toFixed(2)) : '—');
  const AGENT_HUES = [212, 25, 160, 45, 330, 120, 260, 0, 190, 70, 290, 100];
  const agentColor = (i) => `hsl(${AGENT_HUES[i % AGENT_HUES.length]} 55% 55%)`;
  const TIER_COLOR = () => ({ low: css('--tier-low'), mid: css('--tier-mid'), high: css('--tier-high'), none: css('--tier-none') });
  const normTier = (t) => (t ? String(t).toLowerCase() : null);

  const DEFAULT_RUN = 'dev-24x10-s4-market';
  const ui = {
    doc: null, runs: [], run: null, snapshot: null, lastKey: null,
    t: 0, playing: true, speed: 1, auto: true, reveal: false, follow: null, autoTimer: 0, followIndex: -1,
    scene: !window.LOVETOWN_NO_SCENE, sceneReady: false, bridgeSeen: false, state: null,
    seenSwipes: new Set(), seenMatches: new Set(), shownTurns: new Set(), shownChanges: new Set(),
    personaOpen: false, hoverX: null, labels: new Map(), bubbles: new Map(), lastTs: 0,
  };

  // ------------------------------------------------------------------ bridge
  function command(text) {
    if (ui.scene) Module.lovetownCommand.push(text);
  }
  function setPlaying(v) {
    ui.playing = v; command(v ? 'play' : 'pause');
    $('play').textContent = v ? 'Pause' : 'Play';
    $('play').setAttribute('aria-pressed', v ? 'true' : 'false');
  }
  function setSpeed(v) {
    ui.speed = v; command(`speed ${v}`);
    document.querySelectorAll('[data-speed]').forEach((b) => b.classList.toggle('active', Number(b.dataset.speed) === v));
  }
  function seek(t) {
    ui.t = Math.max(0, Math.min(ui.doc ? D.totalSeconds(ui.doc) : 0, t));
    command(`seek ${ui.t.toFixed(2)}`);
  }
  function setAuto(v) {
    ui.auto = v; ui.autoTimer = 0; command(`auto ${v ? 1 : 0}`);
    $('auto').setAttribute('aria-pressed', v ? 'true' : 'false');
    $('auto').textContent = v ? 'Auto camera: on' : 'Auto camera: off';
  }
  function setReveal(v) {
    ui.reveal = v; document.body.classList.toggle('reveal', v);
    $('reveal').setAttribute('aria-pressed', v ? 'true' : 'false');
    $('reveal').textContent = v ? 'Reveal: on' : 'Reveal: off';
    renderAll();
  }
  function follow(id, manual = true) {
    if (!ui.doc || !ui.doc.agents.some((a) => a.id === id)) return;
    ui.follow = id; ui.followIndex = ui.doc.agents.findIndex((a) => a.id === id); ui.autoTimer = 0;
    if (manual) { command(`follow ${id}`); if (ui.auto) setAuto(false); }
    renderAgentCard();
  }
  function readBridge() {
    if (!ui.scene) return null;
    const s = typeof Module.lovetownState === 'function' ? Module.lovetownState() : Module.lovetownState;
    if (!s || typeof s !== 'object') return null;
    ui.bridgeSeen = true;
    if (typeof s.t === 'number') ui.t = s.t;
    if (typeof s.playing === 'boolean' && s.playing !== ui.playing) { ui.playing = s.playing; $('play').textContent = s.playing ? 'Pause' : 'Play'; $('play').setAttribute('aria-pressed', String(s.playing)); }
    if (typeof s.speed === 'number' && s.speed !== ui.speed) { ui.speed = s.speed; document.querySelectorAll('[data-speed]').forEach((b) => b.classList.toggle('active', Number(b.dataset.speed) === s.speed)); }
    if (typeof s.auto === 'boolean' && s.auto !== ui.auto) { ui.auto = s.auto; $('auto').setAttribute('aria-pressed', String(s.auto)); $('auto').textContent = s.auto ? 'Auto camera: on' : 'Auto camera: off'; }
    if (typeof s.followed === 'string' && s.followed !== ui.follow) follow(s.followed, false);
    return s;
  }

  // ------------------------------------------------------------------ loading
  function setStatus(msg, isError) {
    $('load-status').textContent = msg;
    $('load-status').classList.toggle('error', !!isError);
  }
  function fail(error) {
    $('status').hidden = false; $('status').classList.remove('pending');
    $('status').textContent = 'The replay could not load. ' + String((error && error.message) || error);
    setStatus(String((error && error.message) || error), true);
  }
  async function loadRunsIndex() {
    try {
      const res = await fetch('replays/index.json?v=lovetown-1', { cache: 'no-store' });
      if (!res.ok) return [];
      const list = await res.json();
      return Array.isArray(list) ? list.filter((r) => r && typeof r.name === 'string') : [];
    } catch (e) { return []; }
  }
  function renderRunsPicker() {
    const sel = $('runs');
    sel.innerHTML = ui.runs.map((r) => {
      const meta = [r.agents && r.days ? `${r.agents}×${r.days}` : null, r.model ? String(r.model).replace(/^.*\//, '') : null, typeof r.usd === 'number' ? `USD ${r.usd.toFixed(2)}` : null].filter(Boolean).join(' · ');
      return `<option value="${esc(r.name)}" title="${esc(r.note || '')}">${esc(r.name)}${meta ? ' — ' + esc(meta) : ''}</option>`;
    }).join('');
    sel.value = ui.run;
    sel.hidden = !ui.runs.length;
  }
  const replayPromise = (async () => {
    const params = new URLSearchParams(location.search);
    ui.runs = await loadRunsIndex();
    const requested = params.get('run');
    ui.run = ui.runs.some((r) => r.name === requested) ? requested : (ui.runs.some((r) => r.name === DEFAULT_RUN) ? DEFAULT_RUN : (ui.runs[0] && ui.runs[0].name) || requested || DEFAULT_RUN);
    renderRunsPicker();
    const entry = ui.runs.find((r) => r.name === ui.run);
    const url = (entry ? entry.path : `replays/${ui.run}.lovetown.json`) + '?v=lovetown-1';
    setStatus(`Loading ${ui.run} …`);
    const res = await fetch(url, { cache: 'no-store' });
    if (!res.ok) throw new Error(`Recording unavailable (${res.status}) at ${url}`);
    const doc = D.validate(await res.json());
    ui.doc = doc; Module.lovetownDocument = doc;
    const total = D.totalSeconds(doc);
    $('seek').max = String(total);
    buildDayButtons(doc.run.days);
    $('run-label').textContent = ` Run ${doc.run.name}: ${doc.agents.length} agents, ${doc.run.days} days, ${doc.run.model || 'model unknown'}${typeof doc.run.total_usd === 'number' ? `, USD ${doc.run.total_usd.toFixed(2)}` : ''}.`;
    setStatus(`${doc.run.name}: ${doc.agents.length} agents, ${doc.run.days} days${doc.source && doc.source.complete === false ? ' (incomplete run)' : ''}`);
    applyUrlState(params);
    renderAgentPicker();
    if (!ui.follow) follow(doc.agents[0].id, false);
    renderAll(true);
    return doc;
  })();
  replayPromise.catch(fail);

  Module.preRun = [() => {
    if (ui.doc) return;
    Module.addRunDependency('lovetown-replay');
    replayPromise.then(() => Module.removeRunDependency('lovetown-replay')).catch(() => {});
  }];
  Module.onRuntimeInitialized = () => { if (ui.doc && Module.FS) Module.FS.writeFile('/replay.json', JSON.stringify(ui.doc)); };
  Module.onAbort = fail;
  Module.onExit = (code) => { if (code) fail('Viewer exited with code ' + code); };
  Module.lovetownReady = () => sceneReady();
  function sceneReady() {
    ui.sceneReady = true; $('status').hidden = true; $('play').disabled = false;
    // the scene starts from the HUD's current settings (URL state applied before the scene was ready)
    command(ui.playing ? 'play' : 'pause'); command(`speed ${ui.speed}`); command(`auto ${ui.auto ? 1 : 0}`);
    if (ui.t > 0) command(`seek ${ui.t.toFixed(2)}`);
    if (ui.follow && !ui.auto) command(`follow ${ui.follow}`);
  }
  function noScene(reason) {
    ui.scene = false; ui.sceneReady = false; $('play').disabled = false;
    $('status').hidden = false; $('status').classList.add('pending'); $('status').textContent = reason;
    $('transcript-col').classList.add('show');
  }
  if (!ui.scene) noScene('3D scene not built yet: HUD only, transcript below the canvas.');
  // The wasm normally reports ready within a few seconds; keep the HUD usable if it never does.
  setTimeout(() => { if (ui.scene && !ui.sceneReady && !ui.bridgeSeen) { $('play').disabled = false; if (ui.doc) { $('status').classList.add('pending'); $('status').textContent = 'Waiting for the 3D scene… the HUD runs on its own clock meanwhile.'; $('transcript-col').classList.add('show'); } } }, 6000);

  function applyUrlState(p) {
    const speed = Number(p.get('speed'));
    if ([1, 4, 16].includes(speed)) setSpeed(speed);
    const day = Number(p.get('day')), t = Number(p.get('t'));
    const ds = D.daySeconds(ui.doc);
    if (day >= 1) ui.t = (day - 1) * ds + (isFinite(t) ? Math.max(0, Math.min(ds, t)) : 0);
    else if (isFinite(t) && t > 0) ui.t = t;
    if (p.get('reveal') === '1') setReveal(true);
    if (p.get('play') === '0') setPlaying(false);
    if (p.get('auto') === '0') setAuto(false);
    const f = p.get('follow');
    if (f) { const a = ui.doc.agents.find((x) => x.id === f || x.name === f); if (a) follow(a.id, false); }
  }
  function switchRun(name) {
    const p = new URLSearchParams(location.search);
    ['day', 't', 'follow'].forEach((k) => p.delete(k));
    p.set('run', name);
    location.search = p.toString();
  }
  function buildDayButtons(days) {
    const wrap = $('days'); wrap.innerHTML = '';
    for (let d = 1; d <= days; d++) {
      const b = document.createElement('button');
      b.textContent = `Day ${d}`; b.dataset.day = String(d);
      b.addEventListener('click', () => seek((d - 1) * D.daySeconds(ui.doc)));
      wrap.appendChild(b);
    }
  }

  // ------------------------------------------------------------------ helpers
  function garmentSVG(tier, size, label) {
    const colors = TIER_COLOR();
    const col = colors[tier] || colors.none;
    let path;
    if (tier === 'high') path = 'M32 8 L44 12 L54 20 L50 32 L48 32 L50 60 L14 60 L16 32 L14 32 L10 20 L20 12 Z M32 8 L26 26 L32 34 L38 26 Z';
    else if (tier === 'mid') path = 'M32 10 L42 12 L54 20 L50 30 L46 28 L46 56 L18 56 L18 28 L14 30 L10 20 L22 12 Z M26 12 L32 20 L38 12';
    else path = 'M22 12 L32 16 L42 12 L54 20 L50 30 L46 28 L46 56 L18 56 L18 28 L14 30 L10 20 Z';
    return `<svg class="garment" width="${size}" height="${size}" viewBox="0 0 64 64" role="img" aria-label="${esc(label || tier || '')}"><path d="${path}" fill="${col}" stroke="rgba(0,0,0,0.45)" stroke-width="2" stroke-linejoin="round" fill-rule="evenodd"/></svg>`;
  }
  const tierBadge = (tier) => `<span class="tier-badge tier-${tier || 'none'}">${esc((tier || 'none').toUpperCase())}</span>`;
  const goodTier = (gid) => { const g = ui.snapshot && ui.snapshot.goodById.get(gid); return g ? normTier(g.tier) : null; };
  const agentName = (id) => { const a = ui.doc && ui.doc.agents.find((x) => x.id === id); return a ? a.name : id || ''; };
  const agentIndex = (id) => Math.max(0, ui.doc ? ui.doc.agents.findIndex((x) => x.id === id) : 0);

  // ------------------------------------------------------------------ dating app
  function renderApp() {
    const s = ui.snapshot, app = s.app;
    $('app-day').textContent = `Day ${s.clock.day}`;
    const swipesByTarget = {};
    app.swipes.forEach((sw) => { (swipesByTarget[sw.target] = swipesByTarget[sw.target] || []).push(sw); });
    const matched = new Set(); app.matches.forEach((m) => { matched.add(m.a); matched.add(m.b); });
    $('cards').innerHTML = app.profiles.map((p) => {
      const a = s.byId.get(p.agent);
      const tier = normTier(p.picture.tier) || goodTier(p.picture.item) || 'none';
      const chips = (swipesByTarget[p.agent] || []).map((x) => `<span class="swipe-chip ${x.yes ? 'yes' : 'no'}" title="${esc(agentName(x.agent))} swiped ${x.yes ? 'yes' : 'no'}">${esc(initials(agentName(x.agent)))} ${x.yes ? '✓' : '✗'}</span>`).join('');
      const text = p.text ? esc(p.text) : (a.profileText ? `${esc(a.profileText)} <span class="muted small">(earlier text)</span>` : '<span class="muted"><i>no profile text</i></span>');
      return `<article class="card ${matched.has(p.agent) ? 'matched' : ''} ${p.agent === ui.follow ? 'selected' : ''}" data-agent="${esc(p.agent)}">
        <div class="card-pic">${garmentSVG(tier, 52, p.picture.item)}${tierBadge(tier)}</div>
        <div class="card-body"><h4>${esc(a.name)}${a.status === 'dating' ? ` <span class="muted small">dating ${esc(firstName(agentName(a.partner)))}</span>` : ''}</h4>
          <div class="muted small">wearing ${esc(p.picture.item || a.wearing || '—')}</div>
          <p class="profile-text">${text}</p><div class="chips">${chips}</div></div>
        ${matched.has(p.agent) ? '<span class="heart" aria-label="matched">♥</span>' : ''}</article>`;
    }).join('') || `<p class="muted">${s.clock.phase === 'morning' || s.clock.phase === 'market' ? 'The app opens after the market.' : 'No profiles today: cohabiting and dating agents skip the app.'}</p>`;
    $('swipes').innerHTML = app.swipes.slice(-14).reverse().map((sw) => {
      const fresh = !ui.seenSwipes.has(sw.t); ui.seenSwipes.add(sw.t);
      return `<li class="swipe ${sw.yes ? 'yes' : 'no'} ${fresh ? 'fresh' : ''}"><span>${esc(firstName(agentName(sw.agent)))}</span><span class="arrow">${sw.yes ? '→ ✓' : '→ ✗'}</span><span>${esc(firstName(agentName(sw.target)))}</span></li>`;
    }).join('') || '<li class="muted small">No swipes yet.</li>';
    const pairKey = (a, b) => [a, b].sort().join('|');
    const dateStatus = (d) => {
      if (!d || d.step < 0) return 'matched · date tonight';
      if (d.stage === 'walking') return 'walking to the restaurant';
      if (d.stage === 'talking') return `at table ${d.table + 1} · turn ${d.turnsShown}/${d.turns.length}`;
      const oc = d.outcomes.map((o) => `${esc(firstName(agentName(o.agent)))}: ${esc(o.choice || '—')} (${o.rating == null ? '—' : esc(o.rating)}/10)`).join(' · ');
      return oc + (d.change ? ` → <b>${esc(d.change.to)}</b>` : ' → no change');
    };
    const matchedPairs = new Set();
    const tonight = app.matches.map((m) => {
      const fresh = !ui.seenMatches.has(m.t); ui.seenMatches.add(m.t); matchedPairs.add(pairKey(m.a, m.b));
      const d = s.dates.find((x) => pairKey(x.pair[0], x.pair[1]) === pairKey(m.a, m.b));
      return `<li class="match ${fresh ? 'fresh' : ''}"><span class="heart">♥</span><b>${esc(agentName(m.a))}</b> &amp; <b>${esc(agentName(m.b))}</b><div class="small muted">${dateStatus(d)}</div></li>`;
    }).join('');
    const standing = s.dates.filter((d) => d.step >= 0 && !matchedPairs.has(pairKey(d.pair[0], d.pair[1]))).map((d) =>
      `<li class="match standing"><span class="heart">♡</span><b>${esc(agentName(d.pair[0]))}</b> &amp; <b>${esc(agentName(d.pair[1]))}</b><div class="small muted">standing date (already a couple) · ${dateStatus(d)}</div></li>`).join('');
    $('matches').innerHTML = tonight + standing || '<li class="muted small">No matches yet today.</li>';
  }

  // ------------------------------------------------------------------ followed agent
  function renderAgentCard() {
    const s = ui.snapshot; if (!s) return;
    const a = s.byId.get(ui.follow);
    const el = $('agent');
    if (!a) { el.innerHTML = '<p class="muted">Click an agent in the scene or pick one above.</p>'; return; }
    const tier = goodTier(a.wearing) || 'none';
    const inv = Object.entries(a.inventory).filter(([, n]) => n > 0).map(([gid, n]) => `<span class="chip">${esc(gid)}${n > 1 ? ` ×${n}` : ''}</span>`).join('') || '<span class="muted">nothing</span>';
    const alloc = a.alloc && a.alloc.t && s.clock.day && (a.alloc === (ui.doc.days[s.clock.day - 1] || {}).allocations?.find((x) => x.agent === a.id)) ? a.alloc : null;
    const allocHtml = alloc ? `<div class="alloc">${['work', 'games', 'home', 'eat'].map((k) => `<span><b>${esc(alloc.hours[k] ?? 0)}h</b> ${k}</span>`).join('')}${alloc.therapy ? '<span class="chip">therapy</span>' : ''}${alloc.meditation ? '<span class="chip">meditation</span>' : ''}${alloc.invite ? `<span class="chip">invites ${esc(firstName(agentName(alloc.invite)))}</span>` : ''}${alloc.accept_invite ? `<span class="chip">visits ${esc(firstName(agentName(alloc.accept_invite)))}</span>` : ''}${alloc.propose_move_in ? '<span class="chip">proposes move-in</span>' : ''}${alloc.accept_move_in ? '<span class="chip">accepts move-in</span>' : ''}${alloc.breakup ? '<span class="chip warn">breakup</span>' : ''}${alloc.fallback ? '<span class="chip warn" title="model JSON unparsable; default allocation">fallback</span>' : ''}</div>${alloc.shopping.length ? `<div class="small muted">bids: ${alloc.shopping.map((o) => `${esc(o.good)} ${fmtPrice(o.price)}${o.qty > 1 ? `×${o.qty}` : ''}`).join(', ')}</div>` : ''}` : '<span class="muted">no allocation yet today</span>';
    const partner = a.partner ? `${esc(a.status)} with <b>${esc(agentName(a.partner))}</b>` : esc(a.status);
    const d = a.todayDate != null ? s.dates[a.todayDate] : null;
    const dateHtml = renderTranscript(d && d.step >= 0 ? d : a.lastDate, a.id, d && d.step >= 0 ? 'Tonight' : 'Last date', d && d.step >= 0 ? d.turnsShown : null, d && d.step >= 0 ? d.outcomesShown : true);
    let reveal = '';
    if (ui.reveal && a.needs) {
      const w = a.needs.w || {};
      reveal = `<section class="reveal-only"><h5>Hidden (reveal)</h5><div class="weights">${D.NEEDS.map((k) => `<div class="wrow"><span>${k}${a.needs.shadow === k ? ' <span class="shadow">shadow</span>' : ''}</span><div class="bar"><div class="fill" style="width:${Math.round((w[k] || 0) * 100)}%"></div></div><span class="num">${(w[k] || 0).toFixed(2)}</span></div>`).join('')}</div>
        <div class="small muted">Σ U so far: <b>${a.sumU.toFixed(3)}</b> · Σ Û: ${a.sumUhat.toFixed(3)}</div>
        ${a.nights.length ? `<table class="nights"><thead><tr><th>Day</th><th>m food/hugs/money/fun</th><th class="num">U</th><th class="num">Û</th></tr></thead><tbody>${a.nights.map((n) => `<tr><td>${n.day}</td><td class="small">${D.NEEDS.map((k) => (n.m && typeof n.m[k] === 'number') ? n.m[k].toFixed(2) : '—').join(' / ')}</td><td class="num">${n.U != null ? n.U.toFixed(3) : '—'}</td><td class="num">${n.U_hat != null ? n.U_hat.toFixed(3) : '—'}</td></tr>`).join('')}</tbody></table>` : ''}</section>`;
    }
    const longPersona = a.persona.length > 240;
    el.innerHTML = `<header class="agent-head"><span class="avatar" style="background:${agentColor(agentIndex(a.id))}">${esc(initials(a.name))}</span>
        <div><h3>${esc(a.name)}</h3><div class="small muted">${partner}</div></div>
        <div class="agent-pic">${garmentSVG(tier, 40, a.wearing)}${tierBadge(tier)}</div></header>
      <p class="persona" ${longPersona && !ui.personaOpen ? 'style="max-height:3.9em;overflow:hidden"' : ''}>${esc(a.persona)}</p>
      ${longPersona ? `<button type="button" class="persona-toggle small">${ui.personaOpen ? 'less ▴' : 'more ▾'}</button>` : ''}
      <dl class="facts"><dt>Cash</dt><dd>${fmtCash(a.cash)}</dd><dt>Wearing</dt><dd>${esc(a.wearing || '—')} ${a.wearing ? tierBadge(tier) : ''}</dd><dt>Inventory</dt><dd>${inv}</dd><dt>Today</dt><dd>${allocHtml}</dd><dt>Last night</dt><dd>${a.sentence ? `“${esc(a.sentence)}”` : '<span class="muted">nothing yet</span>'}</dd></dl>
      ${dateHtml}${reveal}`;
    const sel = $('agent-pick'); if (sel.value !== ui.follow) sel.value = ui.follow || '';
  }
  function renderTranscript(d, id, title, turnsShown, outcomesShown) {
    if (!d) return '';
    const other = d.pair[0] === id ? d.pair[1] : d.pair[0];
    const turns = d.turns.slice(0, turnsShown == null ? d.turns.length : turnsShown);
    const turnHtml = turns.map((t) => `<li class="${t.speaker === id ? 'me' : 'them'}"><b>${esc(firstName(agentName(t.speaker)))}:</b> ${esc(t.text)}</li>`).join('');
    const oc = outcomesShown ? d.outcomes.map((o) => `<li><span class="chip">${esc(firstName(agentName(o.agent)))}: ${esc(o.choice || '—')} · ${o.rating == null ? '—' : esc(o.rating)}/10</span>${o.reason ? ` <span class="muted small">${esc(o.reason)}</span>` : ''}</li>`).join('') : '';
    return `<section class="transcript"><h5>${esc(title)} with ${esc(agentName(other))} <span class="muted">(day ${d.day}${Number.isInteger(d.table) ? `, table ${d.table + 1}` : ''})</span></h5>
      ${d.scene ? `<p class="scene small muted">${esc(d.scene)}</p>` : ''}<ol>${turnHtml || '<li class="muted">walking to the restaurant…</li>'}</ol>${oc ? `<ul class="outcomes small">${oc}</ul>` : ''}${outcomesShown && d.change ? `<div class="small">→ <b>${esc(d.change.to)}</b></div>` : ''}</section>`;
  }
  function renderAgentPicker() {
    $('agent-pick').innerHTML = ui.doc.agents.map((a) => `<option value="${esc(a.id)}">${esc(a.name)}</option>`).join('');
  }

  // ------------------------------------------------------------------ live dates (transcript column + bubbles)
  function renderDateLive() {
    const s = ui.snapshot;
    const active = s.dates.filter((d) => d.active);
    $('date-live').innerHTML = active.map((d) => {
      const lastTurn = d.turns[d.turnsShown - 1];
      return `<article><h4><span class="heart" style="color:var(--heart)">♥</span>${esc(agentName(d.pair[0]))} &amp; ${esc(agentName(d.pair[1]))}<span class="stage">table ${d.table + 1} · ${d.stage}</span></h4>
        <ol>${d.turns.slice(Math.max(0, d.turnsShown - 4), d.turnsShown).map((t) => `<li><b>${esc(firstName(agentName(t.speaker)))}:</b> ${esc(t.text)}</li>`).join('') || `<li class="muted small">${esc(d.scene || 'walking to the restaurant')}</li>`}</ol>
        ${d.outcomesShown ? `<div class="small muted">${d.outcomes.map((o) => `${esc(firstName(agentName(o.agent)))}: ${esc(o.choice || '—')} (${o.rating == null ? '—' : esc(o.rating)}/10)`).join(' · ')}${d.change ? ` → <b>${esc(d.change.to)}</b>` : ''}</div>` : ''}${lastTurn ? '' : ''}</article>`;
    }).join('') || `<p class="muted small">${s.clock.phase === 'date' ? 'No dates tonight.' : 'Dates start in the evening (28 s into the day).'}</p>`;
  }
  function renderOverlay(state) {
    const s = ui.snapshot, layer = $('world-labels');
    const positions = new Map();
    if (state && Array.isArray(state.agents)) for (const a of state.agents) if (typeof a.sx === 'number' && typeof a.sy === 'number') positions.set(a.id, a);
    const havePositions = positions.size > 0;
    $('transcript-col').classList.toggle('show', !havePositions || !ui.scene);
    // name labels
    for (const agent of ui.doc.agents) {
      let label = ui.labels.get(agent.id);
      if (!label) {
        label = document.createElement('button'); label.className = 'agent-label'; label.dataset.agent = agent.id; label.type = 'button';
        label.setAttribute('aria-label', `Follow ${agent.name}`); layer.append(label); ui.labels.set(agent.id, label);
      }
      const p = positions.get(agent.id);
      const st = s.byId.get(agent.id);
      label.hidden = !p || p.visible === false;
      if (p) {
        label.style.left = `${p.sx * 100}%`; label.style.top = `${p.sy * 100}%`;
        label.classList.toggle('followed', agent.id === ui.follow);
        const tier = goodTier(p.wearing || st.wearing) || 'none';
        label.innerHTML = `<span class="tier" style="background:${TIER_COLOR()[tier]}"></span>${esc(firstName(agent.name))}`;
      }
    }
    // speech bubbles: the scene's own date nodes when it publishes them (so the bubble matches
    // the turn it is staging), else the current turn of each active date from the projection
    const wanted = new Set();
    const spoken = [];
    if (state && Array.isArray(state.dates)) {
      for (const d of state.dates) if (d && typeof d.speaker === 'string' && d.text) spoken.push({ key: `${s.clock.day}|scene|${d.index}|${d.turn}`, speaker: d.speaker, text: d.text });
    } else {
      for (const d of s.dates) {
        if (!d.active || d.turnsShown === 0 || d.stage === 'outcome') continue;
        const turn = d.turns[d.turnsShown - 1];
        spoken.push({ key: `${d.day}|${d.index}|${d.turnsShown}`, speaker: turn.speaker, text: turn.text });
      }
    }
    for (const line of spoken) {
      const p = positions.get(line.speaker);
      if (!p || p.visible === false) continue;
      wanted.add(line.key);
      let b = ui.bubbles.get(line.key);
      if (!b) {
        b = document.createElement('div'); b.className = 'bubble fresh'; b.dataset.key = line.key;
        b.innerHTML = `<b>${esc(firstName(agentName(line.speaker)))}</b>${esc(line.text)}`;
        layer.append(b); ui.bubbles.set(line.key, b);
      }
      b.style.left = `${p.sx * 100}%`; b.style.top = `${p.sy * 100 - 3}%`;
    }
    for (const [key, b] of ui.bubbles) if (!wanted.has(key)) { b.remove(); ui.bubbles.delete(key); }
    // effects published by the scene (heart / broken-heart), shown once per agent and kind per day
    if (state && Array.isArray(state.effects)) for (const ef of state.effects) {
      const key = `scene|${s.clock.day}|${ef.agent}|${ef.kind}`;
      if (ui.shownChanges.has(key)) continue;
      const p = positions.get(ef.agent); if (!p) continue;
      ui.shownChanges.add(key);
      const e = document.createElement('div'); e.className = 'effect'; e.textContent = ef.kind === 'broken-heart' ? '💔' : '♥';
      e.style.left = `${p.sx * 100}%`; e.style.top = `${p.sy * 100}%`; layer.append(e); setTimeout(() => e.remove(), 1700);
    }
    // relationship effects from the projection (only when the scene does not publish its own)
    for (const c of (state && Array.isArray(state.effects)) ? [] : s.changes) {
      if (c.day !== s.clock.day) continue;
      const key = `${c.day}|${c.a}|${c.b}|${c.to}`;
      if (ui.shownChanges.has(key)) continue;
      ui.shownChanges.add(key);
      const p = positions.get(c.a) || positions.get(c.b);
      if (!p) continue;
      const e = document.createElement('div'); e.className = 'effect'; e.textContent = c.to === 'single' ? '💔' : c.to === 'cohabiting' ? '🏠♥' : '♥';
      e.style.left = `${p.sx * 100}%`; e.style.top = `${p.sy * 100}%`; layer.append(e); setTimeout(() => e.remove(), 1700);
    }
    const activeDates = s.dates.filter((d) => d.active);
    const phaseLabel = { morning: 'Morning', market: 'Market', app: 'Dating app', visit: 'Visits', date: 'Dates', night: 'Night' }[s.clock.phase] || s.clock.phase;
    $('scene-caption').textContent = `Day ${s.clock.day} · ${phaseLabel}${activeDates.length ? ' · ' + activeDates.map((d) => d.pair.map((id) => firstName(agentName(id))).join(' & ')).join(' · ') : ''}${state && state.place ? '' : ''}`;
  }

  // ------------------------------------------------------------------ market chart
  function niceTicks(lo, hi, useLog) {
    const cands = [];
    for (let e = -1; e <= 5; e++) [1, 2, 5].forEach((m) => cands.push(m * Math.pow(10, e)));
    let inside = cands.filter((v) => v >= lo && v <= hi);
    if (!useLog) {
      const span = hi - lo;
      const step = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000].find((st) => span / st <= 4) || 1000;
      inside = [];
      for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) inside.push(Number(v.toFixed(6)));
    }
    while (inside.length > 4) inside = inside.filter((_, i) => i % 2 === 0);
    return inside.length ? inside : [lo, hi];
  }
  function renderMarket() {
    const s = ui.snapshot;
    const canvas = $('market');
    const rect = canvas.parentElement.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    const cw = Math.max(240, rect.width);
    const groups = D.marketSeries(s);
    const panelH = 118, ch = Math.max(120, groups.length * panelH);
    if (canvas.width !== Math.round(cw * dpr) || canvas.height !== Math.round(ch * dpr)) { canvas.width = Math.round(cw * dpr); canvas.height = Math.round(ch * dpr); canvas.style.width = cw + 'px'; canvas.style.height = ch + 'px'; }
    const ctx = canvas.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, cw, ch);
    const days = Math.max(1, ui.doc.run.days);
    const roundsPerDay = Math.max(1, ...ui.doc.days.map((d) => d.market.rounds.filter((r) => r.prices && Object.keys(r.prices).length).length));
    const nx = days * roundsPerDay;
    const font = (px, w) => `${w || 400} ${px}px Inter, system-ui, -apple-system, "Segoe UI", sans-serif`;
    const labelOf = (sr) => { const last = sr.history[sr.history.length - 1]; return `${sr.good.id}${last ? ' ' + fmtPrice(last.price) : ''} · ${sr.volume ? `${sr.volume} sold` : 'no trades'}`; };
    ctx.font = font(10);
    const labelW = Math.max(60, ...groups.flatMap((g) => g.goods.map((sr) => ctx.measureText(labelOf(sr)).width)));
    const padL = 44, padR = Math.min(Math.ceil(labelW) + 20, Math.floor(cw * 0.5)), padT = 18, padB = 14;
    const gameColors = [css('--series-1'), css('--series-2'), css('--series-3')];
    const tiers = TIER_COLOR();
    const xi = (p) => (p.day - 1) * roundsPerDay + Math.min(p.round, roundsPerDay - 1);
    ui.marketHover = [];
    groups.forEach((grp, gi) => {
      const top = gi * panelH, plotW = cw - padL - padR, plotH = panelH - padT - padB;
      const series = grp.goods.map((sr, i) => {
        const twin = grp.goods.filter((x) => x.good.tier === sr.good.tier);
        return { ...sr, color: grp.category === 'Games' ? gameColors[i % gameColors.length] : (tiers[normTier(sr.good.tier)] || tiers.none), dash: grp.category !== 'Games' && twin.length > 1 && twin.indexOf(sr) === 1 ? [5, 4] : null };
      });
      const all = series.flatMap((sr) => sr.history.map((p) => p.price)).concat(grp.goods.map((sr) => sr.good.list_price)).filter((v) => v > 0);
      let lo = Math.min(...all), hi = Math.max(...all);
      if (!isFinite(lo)) { lo = 1; hi = 10; }
      const useLog = hi / lo > 20;
      if (useLog) { lo /= 1.3; hi *= 1.3; } else { const m = (hi - lo) * 0.15 || 1; lo = Math.max(0, lo - m); hi += m; }
      const yOf = (v) => { const f = useLog ? (Math.log(v) - Math.log(lo)) / (Math.log(hi) - Math.log(lo)) : (v - lo) / (hi - lo); return top + padT + plotH - f * plotH; };
      const xOf = (i) => padL + (nx <= 1 ? 0 : (plotW * i) / (nx - 1));
      ctx.fillStyle = css('--text-secondary'); ctx.font = font(11, 600); ctx.textBaseline = 'top'; ctx.textAlign = 'left';
      ctx.fillText(`${grp.category}${useLog ? ' (log scale)' : ''}`, padL, top + 2);
      ctx.strokeStyle = css('--grid'); ctx.lineWidth = 1; ctx.fillStyle = css('--text-muted'); ctx.font = font(10);
      niceTicks(lo, hi, useLog).forEach((v) => { const y = yOf(v); ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(padL + plotW, y); ctx.stroke(); ctx.textAlign = 'right'; ctx.textBaseline = 'middle'; ctx.fillText(v >= 100 ? v.toFixed(0) : v.toFixed(1), padL - 6, y); });
      ctx.textAlign = 'center'; ctx.textBaseline = 'top';
      const labelStep = days > 8 ? Math.ceil(days / 7) : 1;
      for (let d = 1; d <= days; d++) { const x = xOf((d - 1) * roundsPerDay); ctx.strokeStyle = css('--axis'); ctx.beginPath(); ctx.moveTo(x, top + padT + plotH); ctx.lineTo(x, top + padT + plotH + 3); ctx.stroke(); if ((d - 1) % labelStep === 0) ctx.fillText(`D${d}`, x, top + padT + plotH + 3); }
      series.forEach((sr) => {
        const dead = sr.volume === 0;
        ctx.save(); if (dead) ctx.globalAlpha = 0.4;
        ctx.strokeStyle = sr.color; ctx.lineWidth = dead ? 1.5 : 2; ctx.setLineDash(dead ? [2, 4] : (sr.dash || []));
        ctx.beginPath(); sr.history.forEach((p, i) => { const x = xOf(xi(p)), y = yOf(p.price); if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y); }); ctx.stroke(); ctx.setLineDash([]);
        ctx.globalAlpha = 0.65; ctx.fillStyle = sr.color;
        sr.history.filter((p) => p.volume > 0).forEach((p) => { ctx.beginPath(); ctx.arc(xOf(xi(p)), yOf(p.price), 2 + Math.sqrt(p.volume) * 1.6, 0, Math.PI * 2); ctx.fill(); });
        ctx.restore();
        const last = sr.history[sr.history.length - 1];
        const lx = last ? xOf(xi(last)) : padL, ly = last ? yOf(last.price) : yOf(sr.good.list_price || lo);
        ctx.fillStyle = sr.color; ctx.beginPath(); ctx.arc(lx, ly, 3.5, 0, Math.PI * 2); ctx.fill(); ctx.strokeStyle = css('--surface-1'); ctx.lineWidth = 2; ctx.stroke();
        sr.labelY = ly;
      });
      let prev = -1e9;
      series.slice().sort((a, b) => a.labelY - b.labelY).forEach((sr) => {
        const y = Math.max(sr.labelY, prev + 11); prev = y;
        ctx.font = font(10); ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
        ctx.fillStyle = sr.color; ctx.fillRect(padL + plotW + 6, y - 3, 6, 6);
        ctx.fillStyle = sr.volume ? css('--text-secondary') : css('--text-muted'); ctx.fillText(labelOf(sr), padL + plotW + 16, y);
      });
    });
    if (ui.hoverX != null && nx > 0) {
      const plotW = cw - padL - padR;
      const i = Math.round(Math.max(0, Math.min(nx - 1, ((ui.hoverX - padL) / plotW) * (nx - 1))));
      const x = padL + (nx <= 1 ? 0 : (plotW * i) / (nx - 1));
      ctx.strokeStyle = css('--axis'); ctx.lineWidth = 1; ctx.setLineDash([3, 3]); ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, ch); ctx.stroke(); ctx.setLineDash([]);
      const day = Math.floor(i / roundsPerDay) + 1, round = i % roundsPerDay;
      const lines = [`Day ${day} · round ${round + 1}`];
      for (const g of s.goods) { const p = (s.market.history.get(g.id) || []).find((q) => q.day === day && q.round === round); if (p) lines.push(`${g.id}: ${fmtPrice(p.price)}${p.volume ? ` · ${p.volume} sold` : ''}`); }
      const tw = 200, th = 12 * lines.length + 8, bx = Math.min(cw - tw - 4, x + 8), by = 4;
      ctx.fillStyle = css('--surface-2'); ctx.strokeStyle = css('--axis'); ctx.beginPath(); ctx.roundRect(bx, by, tw, th, 4); ctx.fill(); ctx.stroke();
      ctx.fillStyle = css('--text-primary'); ctx.font = font(10); ctx.textAlign = 'left'; ctx.textBaseline = 'top';
      lines.forEach((l, k) => ctx.fillText(l, bx + 6, by + 4 + k * 12));
    }
    renderOrderBook();
  }
  function renderOrderBook() {
    const s = ui.snapshot, r = s.market.currentRound;
    if (!r) { $('orders').innerHTML = `<p class="muted small">${s.clock.phase === 'morning' ? 'The market opens after the morning.' : 'No market round yet.'}</p>`; return; }
    const rows = s.goods.map((g) => {
      const bids = r.bids.filter((o) => o.good === g.id).map((o) => `<span class="order bid" title="${esc(agentName(o.agent))}">${esc(firstName(agentName(o.agent)))} ${fmtPrice(o.price)}${o.auto ? ' (auto)' : ''}</span>`).join('');
      const asks = r.asks.filter((o) => o.good === g.id).map((o) => `<span class="order ask">${fmtPrice(o.price)}×${esc(o.qty)}${o.stock != null ? ` (stock ${esc(o.stock)})` : ''}</span>`).join('');
      const clear = r.clears.find((c) => c.good === g.id);
      if (!bids && !asks && !clear) return '';
      const tier = normTier(g.tier);
      return `<tr><td>${esc(g.id)}${['low', 'mid', 'high'].includes(tier) ? ' ' + tierBadge(tier) : ''}</td><td>${bids || '<span class="muted">—</span>'}</td><td>${asks || '<span class="muted">—</span>'}</td><td class="num">${clear ? fmtPrice(clear.price) : '—'}<span class="muted small">${clear && clear.volume ? ` (${clear.volume} sold)` : ''}</span></td></tr>`;
    }).join('');
    $('orders').innerHTML = `<div class="small muted">Day ${s.clock.day} · round ${r.round + 1}${r.prices && Object.keys(r.prices).length ? '' : ' (automatic meals)'}</div><table><thead><tr><th>Good</th><th>Bids</th><th>Asks</th><th class="num">Clear</th></tr></thead><tbody>${rows}</tbody></table>`;
  }

  // ------------------------------------------------------------------ gossip, standings, clock
  function renderGossip() {
    const s = ui.snapshot;
    const items = s.gossip.map((g) => ({ t: g.t, html: `<li><span class="muted small">Day ${esc(g.day)}</span> ${esc(g.text)}</li>` }))
      .concat(s.visitLog.map((v) => ({ t: v.t, html: `<li class="muted"><span class="small">Day ${esc(v.day)}</span> ${esc(firstName(agentName(v.host)))} invited ${esc(firstName(agentName(v.guest)))} home — ${v.accepted ? 'accepted' : 'declined'}</li>` })))
      .sort((x, y) => y.t - x.t);
    $('gossip').innerHTML = items.map((i) => i.html).join('') || '<li class="muted small">The board is empty: no visits, no posts yet.</li>';
  }
  function renderStandings() {
    const s = ui.snapshot;
    const show = ui.reveal || s.ended;
    $('standings-section').hidden = !show;
    if (!show) return;
    $('standings').innerHTML = `<table><thead><tr><th>#</th><th>Agent</th><th class="num">Σ U</th><th class="num">Σ Û</th><th>status</th><th class="num">cash</th></tr></thead><tbody>${s.standings.map((r, i) => `<tr><td>${i + 1}</td><td><button type="button" class="small" data-agent="${esc(r.id)}" style="padding:1px 6px">${esc(r.name)}</button></td><td class="num">${r.sumU.toFixed(3)}</td><td class="num muted">${r.sumUhat.toFixed(3)}</td><td>${esc(r.status)}${r.partner ? ` · ${esc(firstName(agentName(r.partner)))}` : ''}</td><td class="num">${fmtCash(r.cash)}</td></tr>`).join('')}</tbody></table>`;
    $('standings-note').textContent = s.ended ? `Run ended after ${ui.doc.run.days} days${typeof ui.doc.run.total_usd === 'number' ? ` · USD ${ui.doc.run.total_usd.toFixed(2)}` : ''}.` : 'Live (Σ U over the nights so far). Shown because Reveal is on.';
  }
  function renderClock() {
    const c = ui.snapshot.clock;
    $('clock').textContent = `Day ${c.day} · ${c.phase} · ${c.tin.toFixed(1)} s${ui.scene && !ui.bridgeSeen ? ' · HUD clock' : ''}`;
    if (document.activeElement !== $('seek')) $('seek').value = String(c.t);
    document.querySelectorAll('#days button').forEach((b) => b.classList.toggle('active', Number(b.dataset.day) === c.day));
  }
  function renderAll(force) {
    if (!ui.doc) return;
    ui.snapshot = D.project(ui.doc, ui.t);
    if (!force && ui.snapshot.key === ui.lastKey) { renderClock(); return; }
    ui.lastKey = ui.snapshot.key;
    renderApp(); renderAgentCard(); renderDateLive(); renderMarket(); renderGossip(); renderStandings(); renderClock();
  }

  // ------------------------------------------------------------------ main loop
  function frame(ts) {
    const dt = Math.min(0.1, (ts - ui.lastTs) / 1000 || 0);
    ui.lastTs = ts;
    if (ui.doc) {
      const state = readBridge();
      if (!state) {
        // no scene state yet: the HUD keeps its own clock so the page is usable
        if (ui.playing) ui.t = Math.min(D.totalSeconds(ui.doc), ui.t + dt * ui.speed);
        if (ui.auto) { ui.autoTimer += dt; if (ui.autoTimer >= 30) { ui.autoTimer = 0; ui.followIndex = (ui.followIndex + 1) % ui.doc.agents.length; follow(ui.doc.agents[ui.followIndex].id, false); } }
      }
      renderAll();
      renderOverlay(state);
    }
    requestAnimationFrame(frame);
  }

  // ------------------------------------------------------------------ wiring
  $('play').addEventListener('click', () => setPlaying(!ui.playing));
  document.querySelectorAll('[data-speed]').forEach((b) => b.addEventListener('click', () => setSpeed(Number(b.dataset.speed))));
  $('reveal').addEventListener('click', () => setReveal(!ui.reveal));
  $('auto').addEventListener('click', () => setAuto(!ui.auto));
  $('seek').addEventListener('input', (e) => seek(Number(e.target.value)));
  $('agent-pick').addEventListener('change', (e) => { if (e.target.value) follow(e.target.value); });
  $('runs').addEventListener('change', (e) => { if (e.target.value && e.target.value !== ui.run) switchRun(e.target.value); });
  document.addEventListener('click', (e) => {
    const t = e.target.closest('[data-agent]'); if (t) { follow(t.dataset.agent); return; }
    if (e.target.closest('.persona-toggle')) { ui.personaOpen = !ui.personaOpen; renderAgentCard(); }
  });
  const mk = $('market');
  mk.addEventListener('mousemove', (e) => { const r = mk.getBoundingClientRect(); ui.hoverX = e.clientX - r.left; renderMarket(); });
  mk.addEventListener('mouseleave', () => { ui.hoverX = null; renderMarket(); });
  window.addEventListener('resize', () => { if (ui.snapshot) renderMarket(); });
  document.addEventListener('keydown', (e) => {
    if (['INPUT', 'SELECT', 'TEXTAREA'].includes(e.target.tagName)) return;
    if (e.key === ' ') { e.preventDefault(); setPlaying(!ui.playing); }
    if (e.key === 'r') setReveal(!ui.reveal);
    if (e.key === 'ArrowRight') seek(ui.t + 5);
    if (e.key === 'ArrowLeft') seek(ui.t - 5);
  });
  requestAnimationFrame(frame);
})();
