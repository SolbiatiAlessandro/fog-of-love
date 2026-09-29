/* Fog of Love — replay viewer. Vanilla JS, no build step, no network dependencies.
 *
 * Structure:
 *   1. Pure replay core (parseEvents, assignTimes, Replay) — also exported for Node
 *      so the smoke test parses the fixture with exactly this code.
 *   2. Browser UI (only runs when `document` exists).
 */
(function (root) {
  'use strict';

  // ------------------------------------------------------------------ 1. core
  const DAY_SECONDS = 60;
  // Seconds within a day allotted to each phase (a day plays over 60 s at 1x).
  const PHASE_WINDOW = {
    morning: [0, 10],
    market: [10, 20],
    app: [20, 34],
    visit: [34, 38],
    date: [38, 55],
    night: [55, 60],
  };
  const PHASE_ORDER = ['setup', 'morning', 'market', 'app', 'visit', 'date', 'night'];
  const NEEDS = ['food', 'hugs', 'money', 'fun'];
  const EVENT_TYPES = [
    'setup.world', 'setup.needs', 'morning.allocation', 'market.order', 'market.clear',
    'market.prices', 'app.profile', 'app.swipe', 'app.match', 'date.scene', 'date.turn',
    'date.outcome', 'relationship.change', 'visit.invite', 'gossip.post', 'night.state',
    'run.cost', 'run.end',
  ];

  // Event types that a real run may legitimately never emit (no visits, no gossip, no
  // relationship changes); the strict smoke test warns instead of failing on these.
  const OPTIONAL_EVENT_TYPES = [
    'app.match', 'date.scene', 'date.turn', 'date.outcome', 'relationship.change', 'visit.invite', 'gossip.post',
  ];

  // The engine writes goods as {category: "Clothing"|"Games"|"Food", tier: "Low"|"Mid"|"High"|"Standard"};
  // the fixture used lowercase singulars. Normalise both to one vocabulary.
  const CATEGORY_ALIAS = { clothing: 'clothing', clothes: 'clothing', game: 'game', games: 'game', food: 'food', meal: 'food', meals: 'food', restaurant: 'food' };
  function normCategory(c) { const k = String(c == null ? '' : c).toLowerCase(); return CATEGORY_ALIAS[k] || k || 'other'; }
  function normTier(t) { const k = String(t == null ? '' : t).toLowerCase(); return k || null; }
  /** Inventory arrives as a list (fixture) or {item: qty} (engine); keep {item: qty}. */
  function normInventory(inv) {
    const out = {};
    if (Array.isArray(inv)) inv.forEach((id) => { out[id] = (out[id] || 0) + 1; });
    else if (inv && typeof inv === 'object') Object.entries(inv).forEach(([id, q]) => { if (Number(q) > 0) out[id] = Number(q); });
    return out;
  }

  /** Parse events.jsonl text. Bad lines are reported, not fatal. */
  function parseEvents(text) {
    const events = [];
    const errors = [];
    const lines = String(text).split(/\r?\n/);
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();
      if (!line) continue;
      try {
        const ev = JSON.parse(line);
        if (typeof ev !== 'object' || ev === null || typeof ev.type !== 'string') {
          errors.push({ line: i + 1, error: 'not an event object' });
          continue;
        }
        if (typeof ev.t !== 'number') ev.t = events.length;
        if (typeof ev.day !== 'number') ev.day = 0;
        if (typeof ev.phase !== 'string') ev.phase = ev.type.split('.')[0];
        events.push(ev);
      } catch (e) {
        errors.push({ line: i + 1, error: e.message });
      }
    }
    events.sort((a, b) => a.t - b.t);
    return { events, errors };
  }

  /** Assign each event a wall-clock `time` (seconds on the run clock) from day + phase. */
  function assignTimes(events) {
    const groups = new Map();
    for (const ev of events) {
      const key = ev.day + ':' + ev.phase;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(ev);
    }
    for (const [key, list] of groups) {
      const phase = key.split(':')[1];
      const day = Number(key.split(':')[0]);
      const win = PHASE_WINDOW[phase];
      list.forEach((ev, i) => {
        if (!win || day <= 0) {
          ev.time = 0;
        } else {
          const start = (day - 1) * DAY_SECONDS + win[0];
          const len = win[1] - win[0];
          ev.time = start + (len * i) / list.length;
        }
      });
    }
    events.sort((a, b) => a.time - b.time || a.t - b.t);
    return events;
  }

  function summarize(events) {
    const counts = {};
    const agents = new Set();
    let days = 0;
    for (const ev of events) {
      counts[ev.type] = (counts[ev.type] || 0) + 1;
      if (ev.day > days) days = ev.day;
      if (ev.type === 'setup.world' && Array.isArray(ev.agents)) ev.agents.forEach((a) => agents.add(a.name));
      if (ev.type === 'setup.world' && typeof ev.days === 'number') days = Math.max(days, ev.days);
    }
    return { counts, days, agents: [...agents], total: events.length };
  }

  function newAgent(a) {
    return {
      name: a.name,
      persona_summary: a.persona_summary || '',
      cash: typeof a.cash === 'number' ? a.cash : 0,
      wearing: a.wearing || null,
      inventory: a.wearing ? { [a.wearing]: 1 } : {},
      profileText: null, // last non-empty profile text, reused when a day's text is null
      partner: null,
      status: 'single',
      sentence: null,
      m: null,
      U: null,
      U_hat: null,
      needs: null,
      sumU: 0,
      nights: [],
      lastAlloc: null,
      lastDate: null,
    };
  }

  /** Incremental replay: apply events in order; rebuild from scratch to seek backwards. */
  class Replay {
    constructor(events) {
      this.events = events;
      this.applied = 0;
      this.reset();
    }

    reset() {
      this.applied = 0;
      this.state = {
        day: 0, phase: 'setup', days: 0, seed: null,
        agents: {}, agentOrder: [],
        goods: [], goodById: {},
        priceHistory: {}, book: {}, lastClear: {}, trades: {}, tradeLog: {},
        app: { day: 0, profiles: {}, profileOrder: [], swipes: [], matches: [] },
        dates: [], dateIndex: {}, lastDates: [],
        gossip: [], relationships: [], allocs: {}, visits: [], visitLog: [],
        cost: null, end: null, counts: {}, marketSeq: 0,
      };
    }

    /** Advance so that every event with time <= t is applied. Returns list of newly applied events. */
    seek(t) {
      const ev = this.events;
      if (this.applied > 0 && ev[this.applied - 1].time > t) this.reset();
      const fresh = [];
      while (this.applied < ev.length && ev[this.applied].time <= t) {
        const e = ev[this.applied++];
        this.apply(e);
        fresh.push(e);
      }
      return fresh;
    }

    agent(name) {
      const s = this.state;
      if (!s.agents[name]) {
        s.agents[name] = newAgent({ name });
        s.agentOrder.push(name);
      }
      return s.agents[name];
    }

    newDay(day) {
      const s = this.state;
      s.day = day;
      s.app = { day, profiles: {}, profileOrder: [], swipes: [], matches: [] };
      s.lastDates = s.dates;
      s.dates = [];
      s.dateIndex = {};
      s.allocs = {};
      s.visits = [];
      s.marketSeq = 0;
    }

    apply(ev) {
      const s = this.state;
      s.counts[ev.type] = (s.counts[ev.type] || 0) + 1;
      if (ev.day > s.day) this.newDay(ev.day);
      s.phase = ev.phase;
      switch (ev.type) {
        case 'setup.world': {
          (ev.agents || []).forEach((a) => {
            s.agents[a.name] = newAgent(a);
            s.agentOrder.push(a.name);
          });
          s.goods = (ev.goods || []).map((g) => Object.assign({}, g, { category: normCategory(g.category), tier: normTier(g.tier) }));
          s.goods.forEach((g) => { s.goodById[g.id] = g; s.priceHistory[g.id] = []; s.trades[g.id] = 0; s.tradeLog[g.id] = []; });
          s.days = ev.days || 0;
          s.seed = ev.seed;
          break;
        }
        case 'setup.needs': {
          const a = this.agent(ev.name);
          a.needs = { w: ev.w || {}, shadow: ev.shadow || null };
          break;
        }
        case 'morning.allocation': {
          const a = this.agent(ev.name);
          a.lastAlloc = ev;
          s.allocs[ev.name] = ev;
          break;
        }
        case 'market.order': {
          if (!s.book[ev.good]) s.book[ev.good] = { bids: [], asks: [] };
          const side = ev.side === 'ask' ? 'asks' : 'bids';
          s.book[ev.good][side].push({ name: ev.name, price: ev.price, qty: ev.qty, day: ev.day });
          break;
        }
        case 'market.clear': {
          s.lastClear[ev.good] = { day: ev.day, price: ev.price, filled: ev.filled || [] };
          if (s.book[ev.good]) s.book[ev.good] = { bids: [], asks: [] };
          const good = s.goodById[ev.good];
          let sold = 0;
          (ev.filled || []).forEach((f) => {
            const qty = Number(f.qty) > 0 ? Number(f.qty) : 1;
            sold += qty;
            const buyer = s.agents[f.buyer];
            if (!buyer) return;
            buyer.cash -= (typeof f.price === 'number' ? f.price : ev.price || 0) * qty;
            if (good && good.category !== 'food') buyer.inventory[ev.good] = (buyer.inventory[ev.good] || 0) + qty;
          });
          if (sold > 0) {
            s.trades[ev.good] = (s.trades[ev.good] || 0) + sold;
            if (!s.tradeLog[ev.good]) s.tradeLog[ev.good] = [];
            s.tradeLog[ev.good].push({ day: ev.day, round: typeof ev.round === 'number' ? ev.round : null, seq: s.marketSeq, qty: sold, price: ev.price });
          }
          break;
        }
        case 'market.prices': {
          Object.entries(ev.prices || {}).forEach(([gid, price]) => {
            if (!s.priceHistory[gid]) s.priceHistory[gid] = [];
            s.priceHistory[gid].push({ day: ev.day, round: ev.round, price });
          });
          s.book = {};
          s.marketSeq += 1;
          break;
        }
        case 'app.profile': {
          if (!s.app.profiles[ev.name]) s.app.profileOrder.push(ev.name);
          const a = this.agent(ev.name);
          const text = typeof ev.text === 'string' && ev.text.trim() ? ev.text.trim() : null;
          if (text) a.profileText = text;
          const pic = ev.picture || {};
          // text: today's, else the last non-empty one this agent wrote (fallback: true), else null
          s.app.profiles[ev.name] = { name: ev.name, picture: { item: pic.item || null, tier: normTier(pic.tier) }, text: text || a.profileText || null, fallback: !text, t: ev.t };
          if (pic.item) a.wearing = pic.item;
          break;
        }
        case 'app.swipe': {
          s.app.swipes.push({ name: ev.name, target: ev.target, yes: !!ev.yes, t: ev.t });
          break;
        }
        case 'app.match': {
          s.app.matches.push({ a: ev.a, b: ev.b, t: ev.t });
          break;
        }
        case 'date.scene': {
          const d = { a: ev.a, b: ev.b, scene: ev.text || '', turns: [], outcomes: [], change: null, day: ev.day, t: ev.t };
          s.dates.push(d);
          s.dateIndex[ev.a] = d;
          s.dateIndex[ev.b] = d;
          this.agent(ev.a).lastDate = d;
          this.agent(ev.b).lastDate = d;
          break;
        }
        case 'date.turn': {
          const d = this.findDate(ev.a, ev.b, ev.day);
          d.turns.push({ speaker: ev.speaker, text: ev.text || '', t: ev.t });
          break;
        }
        case 'date.outcome': {
          const d = this.findDate(ev.name, ev.partner, ev.day);
          d.outcomes.push({ name: ev.name, partner: ev.partner, rating: ev.rating, choice: ev.choice, reason: ev.reason || '', t: ev.t });
          break;
        }
        case 'relationship.change': {
          const a = this.agent(ev.a);
          const b = this.agent(ev.b);
          const to = ev.to || 'single';
          a.status = to; b.status = to;
          if (to === 'single') { a.partner = null; b.partner = null; }
          else { a.partner = ev.b; b.partner = ev.a; }
          s.relationships.push({ a: ev.a, b: ev.b, from: ev.from, to, day: ev.day, t: ev.t });
          const d = s.dateIndex[ev.a];
          if (d && (d.b === ev.b || d.a === ev.b)) d.change = { from: ev.from, to };
          break;
        }
        case 'visit.invite': {
          const v = { name: ev.name, target: ev.target, accepted: !!ev.accepted, day: ev.day, t: ev.t };
          s.visits.push(v);
          s.visitLog.unshift(v);
          break;
        }
        case 'gossip.post': {
          s.gossip.unshift({ text: ev.text || '', about: ev.about || [], day: ev.day, t: ev.t });
          break;
        }
        case 'night.state': {
          const a = this.agent(ev.name);
          if (typeof ev.cash === 'number') a.cash = ev.cash;
          if (ev.inventory && typeof ev.inventory === 'object') a.inventory = normInventory(ev.inventory);
          if (ev.wearing) a.wearing = ev.wearing;
          a.partner = ev.partner || null;
          if (ev.status) a.status = ev.status;
          a.sentence = ev.sentence || null;
          a.m = ev.m || null;
          a.U = typeof ev.U === 'number' ? ev.U : null;
          a.U_hat = typeof ev.U_hat === 'number' ? ev.U_hat : null;
          if (a.U !== null) a.sumU += a.U;
          a.nights.push({ day: ev.day, m: ev.m, U: a.U, U_hat: a.U_hat, sentence: a.sentence });
          break;
        }
        case 'run.cost': s.cost = { calls: ev.calls, usd: ev.usd, day: ev.day }; break;
        case 'run.end': s.end = ev; break;
        default: break;
      }
    }

    findDate(a, b, day) {
      const s = this.state;
      let d = s.dateIndex[a];
      if (d && (d.a === b || d.b === b)) return d;
      d = { a, b, scene: '', turns: [], outcomes: [], change: null, day, t: 0 };
      s.dates.push(d);
      s.dateIndex[a] = d;
      s.dateIndex[b] = d;
      return d;
    }

    standings() {
      return this.state.agentOrder
        .map((n) => ({ name: n, sumU: this.state.agents[n].sumU, nights: this.state.agents[n].nights.length }))
        .sort((x, y) => y.sumU - x.sumU);
    }
  }

  const core = { DAY_SECONDS, PHASE_WINDOW, PHASE_ORDER, NEEDS, EVENT_TYPES, OPTIONAL_EVENT_TYPES, normCategory, normTier, normInventory, parseEvents, assignTimes, summarize, Replay };
  if (typeof module !== 'undefined' && module.exports) module.exports = core;
  root.FogOfLove = core;
  if (typeof document === 'undefined') return;

  // ------------------------------------------------------------------ 2. UI
  const $ = (sel) => document.querySelector(sel);
  const esc = (v) => String(v == null ? '' : v).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const fmtCash = (v) => (typeof v === 'number' ? v.toFixed(0) : '—');
  const initials = (name) => String(name).split(/\s+/).map((p) => p[0]).join('').slice(0, 2).toUpperCase();
  const firstName = (name) => String(name).split(/\s+/)[0];
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

  const TIER_COLOR = () => ({ low: css('--tier-low'), mid: css('--tier-mid'), high: css('--tier-high'), none: css('--tier-none') });
  const AGENT_HUES = [212, 25, 160, 45, 330, 120, 260, 0, 190, 70, 290, 100];
  const agentColor = (i) => `hsl(${AGENT_HUES[i % AGENT_HUES.length]} 55% 55%)`;

  // Where the repo root is relative to this page. publish_docs.sh rewrites it to './' for docs/replay/,
  // where the runs are bundled next to the page. runs/index.json (see make_runs_index.py) feeds the picker.
  const RUN_ROOT = './';
  const RUNS_INDEX = RUN_ROOT + 'runs/index.json';
  const FIXTURE_URL = 'fixtures/sample-events.jsonl';

  const ui = {
    events: [], replay: null, loaded: false, runs: [], personaOpen: false, camSnap: false,
    playing: true, speed: 1, playhead: 0, runSeconds: 0,
    follow: null, autoFollow: true, autoTimer: 0, followIndex: -1,
    reveal: false,
    positions: {}, // name -> {x, y}
    seenSwipes: new Set(), seenMatches: new Set(),
    lastApplied: -1, marketDirty: true, hoverX: null,
    cam: { x: 500, y: 320, z: 1 },
  };

  // ---- garment icon (original simple shapes)
  function garmentSVG(tier, size, label) {
    const colors = TIER_COLOR();
    const col = colors[tier] || colors.none;
    let path;
    if (tier === 'high') {
      // long coat / gown silhouette with lapels
      path = 'M32 8 L44 12 L54 20 L50 32 L48 32 L50 60 L14 60 L16 32 L14 32 L10 20 L20 12 Z M32 8 L26 26 L32 34 L38 26 Z';
    } else if (tier === 'mid') {
      // collared shirt
      path = 'M32 10 L42 12 L54 20 L50 30 L46 28 L46 56 L18 56 L18 28 L14 30 L10 20 L22 12 Z M26 12 L32 20 L38 12';
    } else {
      // plain tee
      path = 'M22 12 L32 16 L42 12 L54 20 L50 30 L46 28 L46 56 L18 56 L18 28 L14 30 L10 20 Z';
    }
    const t = tier || 'none';
    return `<svg class="garment garment-${t}" width="${size}" height="${size}" viewBox="0 0 64 64" role="img" aria-label="${esc(label || t)}">
      <path d="${path}" fill="${col}" stroke="rgba(0,0,0,0.45)" stroke-width="2" stroke-linejoin="round" fill-rule="evenodd"/>
    </svg>`;
  }
  function tierBadge(tier) {
    const t = tier || 'none';
    return `<span class="tier-badge tier-${t}">${esc(t.toUpperCase())}</span>`;
  }
  function goodLabel(gid) {
    const g = ui.replay && ui.replay.state.goodById[gid];
    return g ? (g.label || g.id) : (gid || '—');
  }
  function goodTier(gid) {
    const g = ui.replay && ui.replay.state.goodById[gid];
    return g ? g.tier : null;
  }

  // ---- loading
  function setStatus(msg, isError) {
    const el = $('#load-status');
    el.textContent = msg;
    el.classList.toggle('error', !!isError);
  }

  function loadText(text, label) {
    const { events, errors } = parseEvents(text);
    if (!events.length) {
      setStatus(`No events found in ${label}.` + (errors.length ? ` ${errors.length} bad lines.` : ''), true);
      return;
    }
    assignTimes(events);
    const sum = summarize(events);
    ui.events = events;
    ui.replay = new Replay(events);
    ui.runSeconds = Math.max(1, sum.days) * DAY_SECONDS;
    ui.playhead = 0;
    ui.loaded = true;
    ui.seenSwipes.clear();
    ui.seenMatches.clear();
    ui.positions = {};
    ui.lastApplied = -1;
    ui.marketDirty = true;
    ui.followIndex = -1;
    ui.follow = null;
    ui.camSnap = true; // open directly on the followed agent, no fly-in
    $('#seek').max = String(ui.runSeconds);
    $('#seek').value = '0';
    buildDayButtons(sum.days);
    setStatus(`${label}: ${sum.total} events, ${sum.agents.length} agents, ${sum.days} days` + (errors.length ? `, ${errors.length} bad lines skipped` : ''));
    applyUrlState(sum);
    ui.replay.seek(0);
    layoutMap();
    renderAll(true);
  }

  async function loadUrl(url) {
    setStatus(`Loading ${url} …`);
    try {
      const res = await fetch(url, { cache: 'no-store' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      loadText(await res.text(), url);
    } catch (e) {
      setStatus(`Could not load ${url} (${e.message}). Pick a file or load the sample fixture.`, true);
      $('#load-fixture').hidden = false;
    }
  }

  // ---- runs picker
  async function loadRunsIndex() {
    try {
      const res = await fetch(RUNS_INDEX, { cache: 'no-store' });
      if (!res.ok) return [];
      const list = await res.json();
      return Array.isArray(list) ? list.filter((r) => r && typeof r.path === 'string') : [];
    } catch (e) {
      return [];
    }
  }
  const runUrl = (r) => RUN_ROOT + String(r.path).replace(/^\.?\//, '');
  function renderRunsPicker(current) {
    const sel = $('#runs');
    if (!sel) return;
    const opts = ui.runs.map((r) => {
      const meta = [
        r.agents && r.days ? `${r.agents}×${r.days}` : null,
        r.model ? String(r.model).replace(/^.*\//, '') : null,
        typeof r.usd === 'number' ? `USD ${r.usd.toFixed(2)}` : null,
      ].filter(Boolean).join(' · ');
      return `<option value="${esc(runUrl(r))}" title="${esc(r.note || '')}">${esc(r.name)}${meta ? ' — ' + esc(meta) : ''}</option>`;
    });
    opts.push(`<option value="${esc(FIXTURE_URL)}">sample fixture — 6×3 synthetic</option>`);
    sel.innerHTML = opts.join('');
    sel.hidden = false;
    sel.value = current;
    if (sel.value !== current) {
      const o = document.createElement('option');
      o.value = current; o.textContent = current;
      sel.appendChild(o);
      sel.value = current;
    }
  }
  /** Load another run: rewrite ?events= (dropping day/t/follow) and reload from t=0. */
  function switchRun(url) {
    const p = new URLSearchParams(location.search);
    ['day', 't', 'follow'].forEach((k) => p.delete(k));
    p.set('events', url);
    history.replaceState(null, '', location.pathname + '?' + p.toString());
    const sel = $('#runs');
    if (sel && !sel.hidden) { sel.value = url; if (sel.value !== url) renderRunsPicker(url); }
    loadUrl(url);
  }
  async function boot() {
    const p = new URLSearchParams(location.search);
    ui.runs = await loadRunsIndex();
    let url = p.get('events');
    // no ?events=: the first indexed run (largest real run), else the engine's runs/latest
    if (!url) url = ui.runs.length ? runUrl(ui.runs[0]) : RUN_ROOT + 'runs/latest/events.jsonl';
    if (ui.runs.length) renderRunsPicker(url);
    loadUrl(url);
  }

  function applyUrlState(sum) {
    const p = new URLSearchParams(location.search);
    const speed = Number(p.get('speed'));
    if ([1, 4, 16].includes(speed)) setSpeed(speed);
    const day = Number(p.get('day'));
    const t = Number(p.get('t'));
    if (day >= 1) ui.playhead = (day - 1) * DAY_SECONDS + (isFinite(t) ? Math.max(0, Math.min(DAY_SECONDS, t)) : 0);
    else if (isFinite(t) && t > 0) ui.playhead = t;
    if (p.get('reveal') === '1') setReveal(true);
    if (p.get('play') === '0') setPlaying(false);
    if (p.get('auto') === '0') setAuto(false);
    const follow = p.get('follow');
    if (follow && sum.agents.includes(follow)) selectAgent(follow, false);
  }

  // ---- controls
  function setPlaying(v) {
    ui.playing = v;
    $('#play').textContent = v ? 'Pause' : 'Play';
    $('#play').setAttribute('aria-pressed', v ? 'true' : 'false');
  }
  function setSpeed(v) {
    ui.speed = v;
    document.querySelectorAll('[data-speed]').forEach((b) => b.classList.toggle('active', Number(b.dataset.speed) === v));
  }
  function setReveal(v) {
    ui.reveal = v;
    document.body.classList.toggle('reveal', v);
    $('#reveal').setAttribute('aria-pressed', v ? 'true' : 'false');
    $('#reveal').textContent = v ? 'Reveal: on' : 'Reveal: off';
    renderAll(true);
  }
  function setAuto(v) {
    ui.autoFollow = v;
    ui.autoTimer = 0;
    $('#auto').setAttribute('aria-pressed', v ? 'true' : 'false');
    $('#auto').textContent = v ? 'Auto camera: on' : 'Auto camera: off';
  }
  function selectAgent(name, resetTimer) {
    ui.follow = name;
    if (ui.replay) ui.followIndex = ui.replay.state.agentOrder.indexOf(name);
    if (resetTimer !== false) ui.autoTimer = 0;
    renderAgentCard();
  }
  function buildDayButtons(days) {
    const wrap = $('#days');
    wrap.innerHTML = '';
    for (let d = 1; d <= days; d++) {
      const b = document.createElement('button');
      b.textContent = `Day ${d}`;
      b.dataset.day = String(d);
      b.addEventListener('click', () => { ui.playhead = (d - 1) * DAY_SECONDS; });
      wrap.appendChild(b);
    }
  }

  // ---- map layout (world units)
  const map = { w: 1000, h: 640, buildings: {}, houses: {}, tables: [] };
  function layoutMap() {
    const names = ui.replay ? ui.replay.state.agentOrder : [];
    map.buildings = {
      workspace: { x: 40, y: 40, w: 300, h: 190, label: 'WORKSPACE', kind: 'work' },
      garden: { x: 400, y: 40, w: 170, h: 170, label: 'MEDITATION GARDEN', kind: 'garden' },
      therapy: { x: 620, y: 40, w: 190, h: 140, label: 'THERAPY OFFICE', kind: 'therapy' },
      restaurant: { x: 620, y: 240, w: 340, h: 180, label: 'RESTAURANT', kind: 'restaurant' },
    };
    map.tables = [{ x: 710, y: 340 }, { x: 870, y: 340 }];
    map.houses = {};
    // balanced rows: 12 agents → 6 + 6, not 10 + 2
    const rows = Math.ceil(names.length / 10) || 1;
    const perRow = Math.ceil(names.length / rows) || 1;
    const step = 920 / perRow;
    const hw = Math.min(88, step - 14);
    names.forEach((n, i) => {
      const r = Math.floor(i / perRow);
      const c = i % perRow;
      map.houses[n] = { x: 40 + c * step + (step - hw) / 2, y: 470 + r * 90, w: hw, h: 66, label: firstName(n), kind: 'house', owner: n };
    });
    map.h = 470 + rows * 90 + 30;
  }

  function slotOffset(idx, cols, gap) {
    return { dx: ((idx % cols) - (cols - 1) / 2) * gap, dy: Math.floor(idx / cols) * gap };
  }

  /** Where an agent should be at the current playhead. Returns {x,y,place}. */
  function targetPosition(name, slot) {
    const s = ui.replay.state;
    const a = s.agents[name];
    const day = Math.floor(ui.playhead / DAY_SECONDS) + 1;
    const tin = ui.playhead - (day - 1) * DAY_SECONDS;
    const house = map.houses[name] || { x: 500, y: 600, w: 0, h: 0 };
    const home = { x: house.x + house.w / 2, y: house.y + house.h / 2 + 8, place: 'home' };
    const B = map.buildings;
    const center = (b, place) => ({ x: b.x + b.w / 2, y: b.y + b.h / 2 + 14, place });
    if (s.day !== day) return home; // not started this day yet
    // dates
    if (tin >= PHASE_WINDOW.date[0] && tin < PHASE_WINDOW.night[0]) {
      const d = s.dateIndex[name];
      if (d) {
        const idx = s.dates.indexOf(d);
        const tbl = map.tables[idx % map.tables.length];
        const side = d.a === name ? -1 : 1;
        const stack = Math.floor(idx / map.tables.length);
        return { x: tbl.x + side * 34, y: tbl.y + stack * 22, place: 'date' };
      }
      return home;
    }
    if (tin >= PHASE_WINDOW.night[0]) return home;
    const alloc = s.allocs[name];
    if (!alloc) return home;
    const h = alloc.hours || {};
    const extra = (alloc.therapy || alloc.meditation) ? 2 : 0;
    const segs = [];
    const eat = Math.max(0, Math.min(2, h.eat || 0));
    if (h.work > 0) segs.push([h.work, center(B.workspace, 'work')]);
    if (eat >= 1) segs.push([1, center(B.restaurant, 'eat')]);
    if (alloc.therapy) segs.push([2, center(B.therapy, 'therapy')]);
    if (alloc.meditation) segs.push([2, center(B.garden, 'meditation')]);
    if (h.games > 0) segs.push([h.games, Object.assign({}, home, { place: 'games' })]);
    if (eat >= 2) segs.push([1, center(B.restaurant, 'eat')]);
    if (h.home > 0) segs.push([h.home, home]);
    const total = segs.reduce((acc, sg) => acc + sg[0], 0) || 1;
    const dayLen = PHASE_WINDOW.date[0];
    const hour = (tin / dayLen) * total;
    let acc = 0;
    for (const [len, pos] of segs) {
      acc += len;
      if (hour < acc) return pos;
    }
    return home;
  }

  function updatePositions(dt, snap) {
    const s = ui.replay.state;
    const counts = {};
    s.agentOrder.forEach((name, i) => {
      const tgt = targetPosition(name, i);
      const key = tgt.place + ':' + Math.round(tgt.x) + ':' + Math.round(tgt.y);
      const idx = counts[key] = (counts[key] || 0) + 1;
      const cols = tgt.place === 'date' ? 1 : 4;
      const off = tgt.place === 'date' ? { dx: 0, dy: 0 } : slotOffset(idx - 1, cols, 24);
      const tx = tgt.x + off.dx;
      const ty = tgt.y + off.dy;
      const p = ui.positions[name] || (ui.positions[name] = { x: tx, y: ty, place: tgt.place });
      p.place = tgt.place;
      if (snap) { p.x = tx; p.y = ty; return; }
      const k = Math.min(1, dt * 5);
      p.x += (tx - p.x) * k;
      p.y += (ty - p.y) * k;
    });
  }

  // ---- map drawing
  function drawMap(dt) {
    const canvas = $('#map');
    const rect = canvas.parentElement.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    const cw = Math.max(200, rect.width);
    const ch = Math.max(200, rect.height);
    if (canvas.width !== Math.round(cw * dpr) || canvas.height !== Math.round(ch * dpr)) {
      canvas.width = Math.round(cw * dpr);
      canvas.height = Math.round(ch * dpr);
      canvas.style.width = cw + 'px';
      canvas.style.height = ch + 'px';
    }
    const ctx = canvas.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = css('--map-ground');
    ctx.fillRect(0, 0, cw, ch);
    if (!ui.loaded) {
      ctx.fillStyle = css('--text-secondary');
      ctx.font = '14px system-ui, sans-serif';
      ctx.fillText('Load an events.jsonl to see Love Town.', 20, 30);
      return;
    }
    const s = ui.replay.state;
    const base = Math.min(cw / map.w, ch / map.h);
    let tz = base, tx = map.w / 2, ty = map.h / 2;
    const fp = ui.follow && ui.positions[ui.follow];
    if (fp) {
      tz = base * 2.1;
      tx = fp.x; ty = fp.y;
      // clamp so the view stays inside the town
      const vw = cw / tz, vh = ch / tz;
      tx = Math.max(vw / 2, Math.min(map.w - vw / 2, tx));
      ty = Math.max(vh / 2, Math.min(map.h - vh / 2, ty));
    }
    const k = ui.camSnap ? 1 : Math.min(1, dt * 4);
    ui.camSnap = false;
    ui.cam.x += (tx - ui.cam.x) * k;
    ui.cam.y += (ty - ui.cam.y) * k;
    ui.cam.z += (tz - ui.cam.z) * k;
    ctx.translate(cw / 2, ch / 2);
    ctx.scale(ui.cam.z, ui.cam.z);
    ctx.translate(-ui.cam.x, -ui.cam.y);
    ui.cam.view = { cw, ch };

    // streets
    ctx.strokeStyle = css('--map-street');
    ctx.lineWidth = 18;
    ctx.beginPath();
    ctx.moveTo(0, 440); ctx.lineTo(map.w, 440);
    ctx.moveTo(370, 0); ctx.lineTo(370, 440);
    ctx.moveTo(595, 0); ctx.lineTo(595, 440);
    ctx.stroke();

    const font = (px) => `${px}px system-ui, -apple-system, "Segoe UI", sans-serif`;
    ctx.textBaseline = 'top';
    const B = map.buildings;
    for (const b of Object.values(B)) drawBuilding(ctx, b, font);
    // restaurant tables
    map.tables.forEach((t) => {
      ctx.fillStyle = css('--map-table');
      ctx.beginPath(); ctx.arc(t.x, t.y, 26, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = 'rgba(0,0,0,0.4)'; ctx.lineWidth = 2; ctx.stroke();
      ctx.fillStyle = css('--map-chair');
      [-44, 44].forEach((dx) => { ctx.beginPath(); ctx.arc(t.x + dx, t.y, 8, 0, Math.PI * 2); ctx.fill(); });
    });
    // houses
    for (const h of Object.values(map.houses)) drawHouse(ctx, h, font);

    // agents
    const tiers = TIER_COLOR();
    s.agentOrder.forEach((name, i) => {
      const p = ui.positions[name];
      if (!p) return;
      const a = s.agents[name];
      const selected = name === ui.follow;
      // garment band
      const tier = goodTier(a.wearing) || 'none';
      ctx.fillStyle = tiers[tier] || tiers.none;
      roundRect(ctx, p.x - 12, p.y + 9, 24, 7, 3); ctx.fill();
      // body
      ctx.beginPath(); ctx.arc(p.x, p.y, 13, 0, Math.PI * 2);
      ctx.fillStyle = agentColor(i); ctx.fill();
      ctx.lineWidth = selected ? 3 : 1.5;
      ctx.strokeStyle = selected ? '#ffffff' : 'rgba(0,0,0,0.5)'; ctx.stroke();
      ctx.fillStyle = '#0b0b0b';
      ctx.font = `600 ${font(11)}`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(initials(name), p.x, p.y + 0.5);
      ctx.textBaseline = 'top';
      if (selected || ui.cam.z > base * 1.5) {
        ctx.fillStyle = css('--text-primary');
        ctx.font = font(10);
        ctx.fillText(firstName(name), p.x, p.y + 18);
      }
      if (p.place === 'date') drawHeart(ctx, p.x, p.y - 24, 6);
      if (a.status === 'cohabiting' && p.place === 'home') drawHeart(ctx, p.x, p.y - 24, 4);
      ctx.textAlign = 'left';
    });
  }

  function roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }
  function drawHeart(ctx, x, y, r) {
    ctx.fillStyle = css('--heart');
    ctx.beginPath();
    ctx.moveTo(x, y + r);
    ctx.bezierCurveTo(x - r * 1.6, y - r * 0.4, x - r * 0.6, y - r * 1.6, x, y - r * 0.5);
    ctx.bezierCurveTo(x + r * 0.6, y - r * 1.6, x + r * 1.6, y - r * 0.4, x, y + r);
    ctx.fill();
  }
  function drawBuilding(ctx, b, font) {
    const fills = { work: '--map-work', garden: '--map-garden', therapy: '--map-therapy', restaurant: '--map-restaurant' };
    ctx.fillStyle = css(fills[b.kind] || '--map-work');
    roundRect(ctx, b.x, b.y, b.w, b.h, 10); ctx.fill();
    ctx.strokeStyle = 'rgba(0,0,0,0.35)'; ctx.lineWidth = 2; ctx.stroke();
    if (b.kind === 'work') {
      ctx.fillStyle = 'rgba(0,0,0,0.18)';
      for (let r = 0; r < 2; r++) for (let c = 0; c < 4; c++) roundRect(ctx, b.x + 30 + c * 66, b.y + 60 + r * 60, 40, 22, 3), ctx.fill();
    }
    if (b.kind === 'garden') {
      ctx.fillStyle = 'rgba(0,0,0,0.2)';
      [[40, 60], [120, 70], [70, 130], [130, 130]].forEach(([dx, dy]) => { ctx.beginPath(); ctx.arc(b.x + dx, b.y + dy, 14, 0, Math.PI * 2); ctx.fill(); });
    }
    if (b.kind === 'therapy') {
      ctx.fillStyle = 'rgba(0,0,0,0.2)';
      roundRect(ctx, b.x + 30, b.y + 70, 60, 26, 8); ctx.fill();
      roundRect(ctx, b.x + 110, b.y + 70, 40, 26, 8); ctx.fill();
    }
    ctx.fillStyle = css('--text-primary');
    ctx.font = `600 ${font(12)}`;
    ctx.textAlign = 'left';
    ctx.fillText(b.label, b.x + 10, b.y + 8);
  }
  function drawHouse(ctx, h, font) {
    const selected = h.owner === ui.follow;
    ctx.fillStyle = css('--map-house');
    roundRect(ctx, h.x, h.y + 16, h.w, h.h - 16, 6); ctx.fill();
    ctx.strokeStyle = selected ? '#ffffff' : 'rgba(0,0,0,0.35)'; ctx.lineWidth = selected ? 2.5 : 1.5; ctx.stroke();
    ctx.fillStyle = css('--map-roof');
    ctx.beginPath(); ctx.moveTo(h.x - 4, h.y + 18); ctx.lineTo(h.x + h.w / 2, h.y); ctx.lineTo(h.x + h.w + 4, h.y + 18); ctx.closePath(); ctx.fill();
    ctx.fillStyle = css('--text-primary');
    ctx.font = font(10);
    ctx.textAlign = 'center';
    ctx.fillText(h.label, h.x + h.w / 2, h.y + h.h - 12);
    ctx.textAlign = 'left';
  }

  function mapClick(evt) {
    if (!ui.loaded) return;
    const canvas = $('#map');
    const r = canvas.getBoundingClientRect();
    const px = evt.clientX - r.left;
    const py = evt.clientY - r.top;
    const { cw, ch } = ui.cam.view;
    const wx = (px - cw / 2) / ui.cam.z + ui.cam.x;
    const wy = (py - ch / 2) / ui.cam.z + ui.cam.y;
    let best = null, bd = 1e9;
    for (const [name, p] of Object.entries(ui.positions)) {
      const d = Math.hypot(p.x - wx, p.y - wy);
      if (d < 20 && d < bd) { best = name; bd = d; }
    }
    if (!best) {
      for (const [name, h] of Object.entries(map.houses)) {
        if (wx >= h.x && wx <= h.x + h.w && wy >= h.y && wy <= h.y + h.h) best = name;
      }
    }
    if (best) selectAgent(best);
  }

  // ---- dating app panel
  function renderApp() {
    const s = ui.replay.state;
    const app = s.app;
    $('#app-day').textContent = s.day ? `Day ${s.day}` : '';
    const swipesByTarget = {};
    app.swipes.forEach((sw) => { (swipesByTarget[sw.target] = swipesByTarget[sw.target] || []).push(sw); });
    const matchedNames = new Set();
    app.matches.forEach((m) => { matchedNames.add(m.a); matchedNames.add(m.b); });
    const cards = app.profileOrder.map((name) => {
      const p = app.profiles[name];
      const a = s.agents[name];
      const tier = p.picture.tier || goodTier(p.picture.item) || 'none';
      const sw = swipesByTarget[name] || [];
      const chips = sw.map((x) => `<span class="swipe-chip ${x.yes ? 'yes' : 'no'}" title="${esc(x.name)} swiped ${x.yes ? 'yes' : 'no'}">${esc(initials(x.name))} ${x.yes ? '✓' : '✗'}</span>`).join('');
      const statusTxt = a.status === 'dating' ? ` · dating ${esc(firstName(a.partner || ''))}` : '';
      // null text (the model returned none): reuse the agent's last text, marked, else a placeholder
      const textHtml = p.text
        ? `${esc(p.text)}${p.fallback ? ' <span class="muted small">(earlier text)</span>' : ''}`
        : '<span class="muted"><i>no profile text</i></span>';
      return `<article class="card ${matchedNames.has(name) ? 'matched' : ''} ${name === ui.follow ? 'selected' : ''}" data-name="${esc(name)}">
        <div class="card-pic">${garmentSVG(tier, 72, goodLabel(p.picture.item))}${tierBadge(tier)}</div>
        <div class="card-body">
          <h4>${esc(name)}<span class="muted">${statusTxt}</span></h4>
          <div class="muted small">wearing ${esc(goodLabel(p.picture.item))}</div>
          <p class="profile-text">${textHtml}</p>
          <div class="chips">${chips}</div>
        </div>
        ${matchedNames.has(name) ? '<span class="heart" aria-label="matched">♥</span>' : ''}
      </article>`;
    }).join('');
    $('#cards').innerHTML = cards || '<p class="muted">No profiles yet today. Cohabiting agents do not see the app.</p>';

    // swipe feed: latest first, animate unseen
    const feed = app.swipes.slice(-12).reverse().map((sw) => {
      const fresh = !ui.seenSwipes.has(sw.t);
      ui.seenSwipes.add(sw.t);
      return `<li class="swipe ${sw.yes ? 'yes' : 'no'} ${fresh ? 'fresh' : ''}"><span>${esc(firstName(sw.name))}</span><span class="arrow">${sw.yes ? '→ ✓' : '← ✗'}</span><span>${esc(firstName(sw.target))}</span></li>`;
    }).join('');
    $('#swipes').innerHTML = feed || '<li class="muted">No swipes yet.</li>';

    // matches + tonight's dates
    const dateStatus = (d, fallback) => {
      if (!d) return fallback;
      if (d.outcomes.length >= 2) {
        const oc = d.outcomes.map((o) => `${esc(firstName(o.name))}: ${esc(o.choice)} (${esc(o.rating)}/10)`).join(' · ');
        return oc + (d.change ? ` → <b>${esc(d.change.to)}</b>` : ' → no change');
      }
      if (d.turns.length) return `at the restaurant · turn ${d.turns.length}`;
      return 'arriving at the restaurant';
    };
    const pairKey = (a, b) => [a, b].sort().join('|');
    const matchedPairs = new Set();
    const tonight = app.matches.map((m) => {
      const fresh = !ui.seenMatches.has(m.t);
      ui.seenMatches.add(m.t);
      matchedPairs.add(pairKey(m.a, m.b));
      const d = s.dates.find((x) => pairKey(x.a, x.b) === pairKey(m.a, m.b));
      return `<li class="match ${fresh ? 'fresh' : ''}"><span class="heart">♥</span><b>${esc(m.a)}</b> &amp; <b>${esc(m.b)}</b><div class="small muted">${dateStatus(d, 'matched, date tonight')}</div></li>`;
    }).join('');
    // couples already dating get a standing date without a match; list those too
    const standing = s.dates.filter((d) => !matchedPairs.has(pairKey(d.a, d.b))).map((d) =>
      `<li class="match standing"><span class="heart">♡</span><b>${esc(d.a)}</b> &amp; <b>${esc(d.b)}</b><div class="small muted">standing date (already dating) · ${dateStatus(d, '')}</div></li>`).join('');
    $('#matches').innerHTML = (tonight + standing) || '<li class="muted">No matches yet today.</li>';
  }

  // ---- market chart (three small multiples: clothing, games, food)
  function renderMarket() {
    const s = ui.replay.state;
    const canvas = $('#market');
    const rect = canvas.parentElement.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    const cw = Math.max(240, rect.width);
    const groups = [
      { key: 'clothing', title: 'Clothing (price, log scale)', goods: s.goods.filter((g) => g.category === 'clothing') },
      { key: 'game', title: 'Games', goods: s.goods.filter((g) => g.category === 'game') },
      { key: 'food', title: 'Restaurant meals (log scale)', goods: s.goods.filter((g) => g.category === 'food') },
    ].filter((g) => g.goods.length);
    const others = s.goods.filter((g) => !['clothing', 'game', 'food'].includes(g.category));
    if (others.length) groups.push({ key: 'other', title: 'Other goods', goods: others });
    const panelH = 118;
    const ch = Math.max(120, groups.length * panelH);
    if (canvas.width !== Math.round(cw * dpr) || canvas.height !== Math.round(ch * dpr)) {
      canvas.width = Math.round(cw * dpr); canvas.height = Math.round(ch * dpr);
      canvas.style.width = cw + 'px'; canvas.style.height = ch + 'px';
    }
    const ctx = canvas.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, cw, ch);
    const days = Math.max(1, s.days || s.day);
    // the engine numbers rounds from 0, the fixture from 1: place points by offset from the first round seen
    const allRounds = Object.values(s.priceHistory).flatMap((h) => h.map((p) => p.round));
    const roundBase = allRounds.length ? Math.min(...allRounds) : 1;
    const roundsPerDay = Math.max(1, ...Object.values(s.priceHistory).map((h) => h.filter((p) => p.day === 1).length));
    const nx = days * roundsPerDay;
    const xi = (p) => (p.day - 1) * roundsPerDay + (typeof p.round === 'number' ? p.round - roundBase : Math.min(p.seq || 0, roundsPerDay - 1));
    const font = (px, w) => `${w || 400} ${px}px system-ui, -apple-system, "Segoe UI", sans-serif`;
    // right padding fits the longest direct label ("Designer Coat 1500 · no trades"), up to half the width
    const labelOf = (g) => {
      const h = s.priceHistory[g.id] || [];
      const last = h[h.length - 1];
      return `${g.label || g.id}${last ? ' ' + fmtPrice(last.price) : ''} · ${s.trades[g.id] ? `${s.trades[g.id]} sold` : 'no trades'}`;
    };
    ctx.font = font(10);
    const labelW = Math.max(60, ...s.goods.map((g) => ctx.measureText(labelOf(g)).width));
    const padL = 44, padR = Math.min(Math.ceil(labelW) + 20, Math.floor(cw * 0.5)), padT = 18, padB = 14;
    const gameColors = [css('--series-1'), css('--series-2'), css('--series-3')];
    const tiers = TIER_COLOR();
    ui.marketSeries = [];
    groups.forEach((grp, gi) => {
      const top = gi * panelH;
      const plotW = cw - padL - padR;
      const plotH = panelH - padT - padB;
      const series = grp.goods.map((g, i) => {
        const hist = s.priceHistory[g.id] || [];
        const color = g.category === 'game' ? gameColors[i % gameColors.length] : (tiers[g.tier] || tiers.none);
        // second good of a tier is dashed (by id suffix in the fixture, by position in the engine's goods list)
        const twin = grp.goods.filter((x) => x.tier === g.tier);
        const dash = g.category !== 'game' && (/2$/.test(g.id) || (twin.length > 1 && twin.indexOf(g) === 1)) ? [5, 4] : null;
        return { good: g, hist, color, dash, trades: s.trades[g.id] || 0, log: s.tradeLog[g.id] || [] };
      });
      const all = series.flatMap((sr) => sr.hist.map((p) => p.price)).concat(grp.goods.map((g) => g.list_price)).filter((v) => v > 0);
      let lo = Math.min(...all), hi = Math.max(...all);
      const useLog = hi / lo > 20;
      if (!isFinite(lo)) { lo = 1; hi = 10; }
      if (useLog) { lo = lo / 1.3; hi = hi * 1.3; } else { const m = (hi - lo) * 0.15 || 1; lo = Math.max(0, lo - m); hi = hi + m; }
      const yOf = (v) => {
        const f = useLog ? (Math.log(v) - Math.log(lo)) / (Math.log(hi) - Math.log(lo)) : (v - lo) / (hi - lo);
        return top + padT + plotH - f * plotH;
      };
      const xOf = (i) => padL + (nx <= 1 ? 0 : (plotW * i) / (nx - 1));
      // title
      ctx.fillStyle = css('--text-secondary');
      ctx.font = font(11, 600);
      ctx.textBaseline = 'top';
      ctx.fillText(grp.title, padL, top + 2);
      // gridlines: 3 horizontal
      ctx.strokeStyle = css('--grid'); ctx.lineWidth = 1;
      ctx.fillStyle = css('--text-muted'); ctx.font = font(10);
      niceTicks(lo, hi, useLog).forEach((v) => {
        const y = yOf(v);
        ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(padL + plotW, y); ctx.stroke();
        ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
        ctx.fillText(v >= 100 ? v.toFixed(0) : v.toFixed(1), padL - 6, y);
      });
      // day ticks
      ctx.textAlign = 'center'; ctx.textBaseline = 'top';
      for (let d = 1; d <= days; d++) {
        const x = xOf((d - 1) * roundsPerDay);
        ctx.strokeStyle = css('--axis'); ctx.beginPath(); ctx.moveTo(x, top + padT + plotH); ctx.lineTo(x, top + padT + plotH + 3); ctx.stroke();
        ctx.fillText(`D${d}`, x, top + padT + plotH + 3);
      }
      // series. A good that never traded is faint and dotted: its "price" is only the list price
      // carried through the clearing house. Dots mark rounds with fills, area ∝ units sold.
      series.forEach((sr) => {
        const dead = sr.trades === 0;
        ctx.save();
        if (dead) ctx.globalAlpha = 0.4;
        ctx.strokeStyle = sr.color; ctx.lineWidth = dead ? 1.5 : 2; ctx.setLineDash(dead ? [2, 4] : (sr.dash || []));
        ctx.beginPath();
        sr.hist.forEach((p, i) => {
          const x = xOf(xi(p));
          const y = yOf(p.price);
          if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        });
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.globalAlpha = 0.65;
        ctx.fillStyle = sr.color;
        sr.log.forEach((tr) => {
          const x = xOf(xi(tr));
          const y = yOf(typeof tr.price === 'number' && tr.price > 0 ? tr.price : (sr.good.list_price || lo));
          ctx.beginPath(); ctx.arc(x, y, 2 + Math.sqrt(tr.qty) * 1.6, 0, Math.PI * 2); ctx.fill();
        });
        ctx.restore();
        const last = sr.hist[sr.hist.length - 1];
        const lx = last ? xOf(xi(last)) : padL;
        const ly = last ? yOf(last.price) : yOf(sr.good.list_price);
        ctx.fillStyle = sr.color; ctx.beginPath(); ctx.arc(lx, ly, 3.5, 0, Math.PI * 2); ctx.fill();
        ctx.strokeStyle = css('--surface-1'); ctx.lineWidth = 2; ctx.stroke();
        sr.labelY = ly;
      });
      // direct labels at line ends, de-collided; "(no trades)" for goods that never cleared a unit
      const ordered = series.slice().sort((a, b) => a.labelY - b.labelY);
      let prev = -1e9;
      ordered.forEach((sr) => {
        let y = Math.max(sr.labelY, prev + 11);
        prev = y;
        ctx.font = font(10); ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
        ctx.fillStyle = sr.color; ctx.fillRect(padL + plotW + 6, y - 3, 6, 6);
        ctx.fillStyle = sr.trades ? css('--text-secondary') : css('--text-muted');
        ctx.fillText(labelOf(sr.good), padL + plotW + 16, y);
      });
      ui.marketSeries.push({ grp, series, top, xOf, yOf, plotW, padL, roundsPerDay });
    });
    // hover crosshair
    if (ui.hoverX != null && nx > 0) {
      const plotW = cw - padL - padR;
      const i = Math.round(Math.max(0, Math.min(nx - 1, ((ui.hoverX - padL) / plotW) * (nx - 1))));
      const x = padL + (nx <= 1 ? 0 : (plotW * i) / (nx - 1));
      ctx.strokeStyle = css('--axis'); ctx.lineWidth = 1; ctx.setLineDash([3, 3]);
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, ch); ctx.stroke(); ctx.setLineDash([]);
      const day = Math.floor(i / roundsPerDay) + 1, round = (i % roundsPerDay) + roundBase;
      const lines = [`Day ${day} · round ${round - roundBase + 1}`];
      s.goods.forEach((g) => {
        const p = (s.priceHistory[g.id] || []).find((q) => q.day === day && q.round === round);
        if (!p) return;
        const tr = (s.tradeLog[g.id] || []).find((q) => q.day === day && (typeof q.round === 'number' ? q.round === round : q.seq === round - roundBase));
        const vol = tr ? ` · ${tr.qty} sold` : ((s.trades[g.id] || 0) ? '' : ' · no trades');
        lines.push(`${g.label || g.id}: ${fmtPrice(p.price)}${vol}`);
      });
      const tw = 190, th = 12 * lines.length + 8;
      const bx = Math.min(cw - tw - 4, x + 8), by = 4;
      ctx.fillStyle = css('--surface-2'); ctx.strokeStyle = css('--axis');
      roundRect(ctx, bx, by, tw, th, 4); ctx.fill(); ctx.stroke();
      ctx.fillStyle = css('--text-primary'); ctx.font = font(10); ctx.textAlign = 'left'; ctx.textBaseline = 'top';
      lines.forEach((l, k) => ctx.fillText(l, bx + 6, by + 4 + k * 12));
    }
    renderOrderBook();
  }
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
  const fmtPrice = (v) => (typeof v === 'number' ? (v >= 100 ? v.toFixed(0) : v.toFixed(2)) : '—');

  function renderOrderBook() {
    const s = ui.replay.state;
    const rows = s.goods.map((g) => {
      const b = s.book[g.id] || { bids: [], asks: [] };
      const lc = s.lastClear[g.id];
      const bids = b.bids.map((o) => `<span class="order bid" title="${esc(o.name)}">${esc(firstName(o.name))} ${fmtPrice(o.price)}</span>`).join('');
      const asks = b.asks.map((o) => `<span class="order ask" title="${esc(o.name)}">${fmtPrice(o.price)}×${esc(o.qty)}</span>`).join('');
      if (!bids && !asks && !lc) return '';
      return `<tr><td>${esc(g.label || g.id)}${['low', 'mid', 'high'].includes(g.tier) ? ' ' + tierBadge(g.tier) : ''}</td><td>${bids || '<span class="muted">—</span>'}</td><td>${asks || '<span class="muted">—</span>'}</td><td class="num">${lc ? fmtPrice(lc.price) : '—'}<span class="muted small">${lc && lc.filled.length ? ` (${lc.filled.length} filled)` : ''}</span></td></tr>`;
    }).join('');
    $('#orders').innerHTML = rows ? `<table><thead><tr><th>Good</th><th>Bids</th><th>Asks</th><th class="num">Last clear</th></tr></thead><tbody>${rows}</tbody></table>` : '<p class="muted">No orders yet.</p>';
  }

  // ---- gossip
  function renderGossip() {
    const s = ui.replay.state;
    // posts plus the visit invites that produced (or failed to produce) them, newest first
    const items = s.gossip.map((g) => ({ t: g.t, html: `<li><span class="muted small">Day ${esc(g.day)}</span> ${esc(g.text)}</li>` }))
      .concat(s.visitLog.map((v) => ({ t: v.t, html: `<li class="muted"><span class="small">Day ${esc(v.day)}</span> ${esc(firstName(v.name))} invited ${esc(firstName(v.target))} home — ${v.accepted ? 'accepted' : 'declined'}</li>` })))
      .sort((x, y) => y.t - x.t);
    $('#gossip').innerHTML = items.map((i) => i.html).join('') || '<li class="muted">The board is empty: no visits, no posts yet.</li>';
  }

  // ---- selected agent card
  function renderAgentCard() {
    if (!ui.loaded) return;
    const s = ui.replay.state;
    const name = ui.follow;
    const el = $('#agent');
    if (!name || !s.agents[name]) { el.innerHTML = '<p class="muted">Click an agent on the map or pick one below.</p>'; renderAgentPicker(); return; }
    const a = s.agents[name];
    const idx = s.agentOrder.indexOf(name);
    const tier = goodTier(a.wearing) || 'none';
    const inv = Object.entries(a.inventory).map(([gid, n]) => `<span class="chip">${esc(goodLabel(gid))}${n > 1 ? ` ×${n}` : ''}</span>`).join('') || '<span class="muted">nothing</span>';
    const alloc = s.allocs[name];
    const bids = alloc && Array.isArray(alloc.shopping) && alloc.shopping.length
      ? `<div class="alloc small muted">bids: ${alloc.shopping.map((o) => `${esc(goodLabel(o.good))} ${fmtPrice(o.price)}${o.qty > 1 ? `×${esc(o.qty)}` : ''}`).join(', ')}</div>` : '';
    const allocHtml = alloc ? `<div class="alloc">${['work', 'games', 'home', 'eat'].map((k) => `<span><b>${esc((alloc.hours || {})[k] ?? 0)}h</b> ${k}</span>`).join('')}${alloc.therapy ? '<span class="chip">therapy</span>' : ''}${alloc.meditation ? '<span class="chip">meditation</span>' : ''}${alloc.invite ? `<span class="chip">invites ${esc(firstName(alloc.invite))}</span>` : ''}${alloc.accept_invite ? `<span class="chip">visits ${esc(firstName(alloc.accept_invite))}</span>` : ''}${alloc.accept_move_in ? '<span class="chip">accepts move-in</span>' : ''}${alloc.breakup ? '<span class="chip warn">breakup</span>' : ''}${alloc.fallback ? '<span class="chip warn" title="the model\'s JSON could not be parsed; default allocation">fallback</span>' : ''}</div>${bids}` : '<span class="muted">no allocation yet today</span>';
    const longPersona = a.persona_summary.length > 260;
    const partner = a.partner ? `${esc(a.status)} with <b>${esc(a.partner)}</b>` : esc(a.status);
    const d = s.dateIndex[name] || null;
    const last = !d && a.lastDate ? a.lastDate : null;
    const dateHtml = renderTranscript(d || last, name, d ? 'Tonight' : 'Last date');
    let reveal = '';
    if (ui.reveal && a.needs) {
      const w = a.needs.w || {};
      reveal = `<section class="reveal-only"><h5>Hidden (reveal)</h5>
        <div class="weights">${NEEDS.map((k) => `<div class="wrow"><span class="wlabel">${k}${a.needs.shadow === k ? ' <span class="shadow">shadow</span>' : ''}</span><div class="bar"><div class="fill" style="width:${Math.round((w[k] || 0) * 100)}%"></div></div><span class="num">${((w[k] || 0)).toFixed(2)}</span></div>`).join('')}</div>
        <div class="small muted">Σ U so far: <b>${a.sumU.toFixed(3)}</b></div>
        ${a.nights.length ? `<table class="nights"><thead><tr><th>Day</th><th>m food/hugs/money/fun</th><th class="num">U</th><th class="num">Û</th></tr></thead><tbody>${a.nights.map((n) => `<tr><td>${n.day}</td><td class="small">${NEEDS.map((k) => (n.m && typeof n.m[k] === 'number') ? n.m[k].toFixed(2) : '—').join(' / ')}</td><td class="num">${n.U != null ? n.U.toFixed(3) : '—'}</td><td class="num">${n.U_hat != null ? n.U_hat.toFixed(3) : '—'}</td></tr>`).join('')}</tbody></table>` : ''}
      </section>`;
    }
    el.innerHTML = `
      <header class="agent-head">
        <span class="avatar" style="background:${agentColor(idx)}">${esc(initials(name))}</span>
        <div><h3>${esc(name)}</h3><div class="small muted">${partner}</div></div>
        <div class="agent-pic">${garmentSVG(tier, 44, goodLabel(a.wearing))}${tierBadge(tier)}</div>
      </header>
      <p class="persona ${longPersona && !ui.personaOpen ? 'clamp' : ''}" ${longPersona ? 'title="click to expand or collapse"' : ''}>${esc(a.persona_summary)}</p>
      ${longPersona ? `<button type="button" class="linkish persona-toggle">${ui.personaOpen ? 'less ▴' : 'more ▾'}</button>` : ''}
      <dl class="facts">
        <dt>Cash</dt><dd>${fmtCash(a.cash)}</dd>
        <dt>Wearing</dt><dd>${esc(goodLabel(a.wearing))}</dd>
        <dt>Inventory</dt><dd>${inv}</dd>
        <dt>Today</dt><dd>${allocHtml}</dd>
        <dt>Last night</dt><dd>${a.sentence ? `“${esc(a.sentence)}”` : '<span class="muted">nothing yet</span>'}</dd>
      </dl>
      ${dateHtml}
      ${reveal}`;
    renderAgentPicker();
  }
  function renderTranscript(d, name, title) {
    if (!d) return '';
    const other = d.a === name ? d.b : d.a;
    const turns = d.turns.map((t) => `<li class="${t.speaker === name ? 'me' : 'them'}"><b>${esc(firstName(t.speaker))}:</b> ${esc(t.text)}</li>`).join('');
    const oc = d.outcomes.map((o) => `<li><span class="chip">${esc(firstName(o.name))}: ${esc(o.choice)} · ${esc(o.rating)}/10</span>${o.reason ? ` <span class="muted">${esc(o.reason)}</span>` : ''}</li>`).join('');
    return `<section class="transcript"><h5>${esc(title)} with ${esc(other)}${d.day ? ` <span class="muted small">(day ${d.day})</span>` : ''}</h5>
      ${d.scene ? `<p class="scene small muted">${esc(d.scene)}</p>` : ''}
      <ol>${turns}</ol>${oc ? `<ul class="outcomes small">${oc}</ul>` : ''}${d.change ? `<div class="small">→ <b>${esc(d.change.to)}</b></div>` : ''}</section>`;
  }
  function renderAgentPicker() {
    const s = ui.replay.state;
    const sel = $('#agent-pick');
    const cur = sel.value;
    sel.innerHTML = '<option value="">— pick an agent —</option>' + s.agentOrder.map((n) => `<option value="${esc(n)}" ${n === ui.follow ? 'selected' : ''}>${esc(n)}</option>`).join('');
    if (!ui.follow) sel.value = cur;
  }

  // ---- standings
  function renderStandings() {
    const s = ui.replay.state;
    const show = ui.reveal || !!s.end;
    const sec = $('#standings-section');
    sec.hidden = !show;
    if (!show) return;
    const rows = ui.replay.standings().map((r, i) => `<tr><td>${i + 1}</td><td>${esc(r.name)}</td><td class="num">${r.sumU.toFixed(3)}</td><td class="num muted">${r.nights}</td></tr>`).join('');
    $('#standings').innerHTML = `<table><thead><tr><th>#</th><th>Agent</th><th class="num">Σ U</th><th class="num">nights</th></tr></thead><tbody>${rows}</tbody></table>`;
    $('#standings-note').textContent = s.end ? `Run ended after ${s.end.days} days · total cost USD ${Number(s.end.total_usd || 0).toFixed(2)}${s.end.aborted ? ' · aborted' : ''}` : 'Live (Σ U over nights so far). Shown because Reveal is on.';
  }

  function renderClock() {
    const s = ui.replay.state;
    const day = Math.min(Math.max(1, Math.floor(ui.playhead / DAY_SECONDS) + 1), Math.max(1, s.days || s.day || 1));
    const tin = ui.playhead - (day - 1) * DAY_SECONDS;
    let phase = 'morning';
    for (const [p, w] of Object.entries(PHASE_WINDOW)) if (tin >= w[0]) phase = p;
    $('#clock').textContent = `Day ${day} · ${phase} · ${tin.toFixed(1)} s`;
    $('#seek').value = String(ui.playhead);
    document.querySelectorAll('#days button').forEach((b) => b.classList.toggle('active', Number(b.dataset.day) === day));
    const c = s.cost;
    $('#cost').textContent = c ? `${c.calls} calls · USD ${Number(c.usd).toFixed(2)}` : '';
  }

  function renderAll(force) {
    if (!ui.loaded) return;
    renderApp();
    renderMarket();
    renderGossip();
    renderAgentCard();
    renderStandings();
    renderClock();
  }

  // ---- main loop
  let lastTs = 0;
  function frame(ts) {
    const dt = Math.min(0.1, (ts - lastTs) / 1000 || 0);
    lastTs = ts;
    if (ui.loaded) {
      const before = ui.playhead;
      if (ui.playing) ui.playhead = Math.min(ui.runSeconds, ui.playhead + dt * ui.speed);
      if (ui.playhead >= ui.runSeconds && ui.playing) setPlaying(false);
      const fresh = ui.replay.seek(ui.playhead);
      if (Object.keys(map.houses).length !== ui.replay.state.agentOrder.length) layoutMap();
      const seeked = ui.replay.applied < ui.lastApplied || Math.abs(ui.playhead - before) > 2;
      if (fresh.length || ui.replay.applied !== ui.lastApplied) {
        ui.lastApplied = ui.replay.applied;
        renderAll();
      } else {
        renderClock();
      }
      // auto camera
      const s = ui.replay.state;
      if (ui.autoFollow && s.agentOrder.length) {
        ui.autoTimer += dt;
        if (!ui.follow || ui.autoTimer >= 30) {
          ui.autoTimer = 0;
          ui.followIndex = (ui.followIndex + 1) % s.agentOrder.length;
          selectAgent(s.agentOrder[ui.followIndex], false);
        }
      }
      updatePositions(dt, seeked);
    }
    drawMap(dt);
    requestAnimationFrame(frame);
  }

  // ---- wiring
  function init() {
    $('#play').addEventListener('click', () => setPlaying(!ui.playing));
    document.querySelectorAll('[data-speed]').forEach((b) => b.addEventListener('click', () => setSpeed(Number(b.dataset.speed))));
    $('#reveal').addEventListener('click', () => setReveal(!ui.reveal));
    $('#auto').addEventListener('click', () => setAuto(!ui.autoFollow));
    $('#seek').addEventListener('input', (e) => { ui.playhead = Number(e.target.value); });
    $('#map').addEventListener('click', mapClick);
    $('#agent-pick').addEventListener('change', (e) => { if (e.target.value) selectAgent(e.target.value); });
    $('#cards').addEventListener('click', (e) => { const c = e.target.closest('.card'); if (c) selectAgent(c.dataset.name); });
    $('#file').addEventListener('change', (e) => {
      const f = e.target.files[0];
      if (!f) return;
      f.text().then((txt) => loadText(txt, f.name));
    });
    $('#load-fixture').addEventListener('click', () => switchRun(FIXTURE_URL));
    $('#runs').addEventListener('change', (e) => { if (e.target.value) switchRun(e.target.value); });
    $('#agent').addEventListener('click', (e) => { if (e.target.closest('.persona, .persona-toggle')) { ui.personaOpen = !ui.personaOpen; renderAgentCard(); } });
    const mk = $('#market');
    mk.addEventListener('mousemove', (e) => { const r = mk.getBoundingClientRect(); ui.hoverX = e.clientX - r.left; renderMarket(); });
    mk.addEventListener('mouseleave', () => { ui.hoverX = null; renderMarket(); });
    window.addEventListener('resize', () => { if (ui.loaded) renderMarket(); });
    document.addEventListener('keydown', (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
      if (e.key === ' ') { e.preventDefault(); setPlaying(!ui.playing); }
      if (e.key === 'r') setReveal(!ui.reveal);
      if (e.key === 'ArrowRight') ui.playhead = Math.min(ui.runSeconds, ui.playhead + 5);
      if (e.key === 'ArrowLeft') ui.playhead = Math.max(0, ui.playhead - 5);
    });
    setSpeed(1);
    setPlaying(true);
    setAuto(true);
    boot();
    requestAnimationFrame(frame);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})(typeof globalThis !== 'undefined' ? globalThis : this);
