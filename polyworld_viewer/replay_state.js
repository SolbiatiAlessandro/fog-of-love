/* Read-only projection of a love-town-replay/1 document at a replay time t.
 *
 * Browser: window.LoveTownReplay
 * Node:    const LoveTownReplay = require("./replay_state.js")
 *
 * Everything here follows docs/POLYWORLD_REPLAY.md ("Presentation clock"): 60 s per day,
 * six phase windows, items revealed evenly across their window, dates staged on two
 * tables in parallel. The Nim scene applies the same rule, so the HUD and the 3D world agree.
 */
(function install(root, factory) {
  "use strict";
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.LoveTownReplay = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function factory() {
  "use strict";

  const SCHEMA = "love-town-replay/1";
  const PHASE_ORDER = ["morning", "market", "app", "date", "visit", "night"];
  const NEEDS = ["food", "hugs", "money", "fun"];
  const DEFAULT_PHASES = { morning: [0, 3], market: [3, 18], app: [18, 29], date: [29, 51], visit: [51, 55], night: [55, 60] };

  function invariant(condition, message) {
    if (!condition) throw new TypeError(`Invalid Love Town replay: ${message}`);
  }
  const isObject = (v) => v !== null && typeof v === "object" && !Array.isArray(v);

  function validate(doc) {
    invariant(isObject(doc), "document must be an object");
    invariant(doc.schema === SCHEMA, `expected schema ${SCHEMA}, got ${doc.schema}`);
    invariant(Array.isArray(doc.agents) && doc.agents.length > 0, "agents must be a non-empty array");
    invariant(Array.isArray(doc.goods), "goods must be an array");
    invariant(Array.isArray(doc.days), "days must be an array");
    invariant(isObject(doc.run) && Number.isInteger(doc.run.days), "run.days is missing");
    const ids = new Set();
    doc.agents.forEach((a, i) => {
      invariant(a.id === `agent-${String(i).padStart(3, "0")}`, `agent ${i} has id ${a.id}`);
      invariant(typeof a.name === "string" && a.name, `agent ${a.id} has no name`);
      ids.add(a.id);
    });
    doc.days.forEach((d, i) => {
      invariant(d.day === i + 1, `days[${i}] is day ${d.day}`);
      for (const key of ["allocations", "visits", "dates", "gossip", "relationship_changes", "night"]) invariant(Array.isArray(d[key]), `day ${d.day} lacks ${key}`);
      invariant(isObject(d.market) && Array.isArray(d.market.rounds), `day ${d.day} lacks market.rounds`);
      invariant(isObject(d.app) && Array.isArray(d.app.profiles), `day ${d.day} lacks app.profiles`);
      d.night.forEach((n) => invariant(ids.has(n.agent) && isObject(n.hidden), `day ${d.day}: bad night state`));
      d.dates.forEach((x) => invariant(Array.isArray(x.pair) && x.pair.length === 2 && Array.isArray(x.turns), `day ${d.day}: bad date`));
    });
    return doc;
  }

  function daySeconds(doc) { return (doc.timeline && doc.timeline.day_seconds) || 60; }
  function phases(doc) { return (doc.timeline && doc.timeline.phases) || DEFAULT_PHASES; }
  function totalSeconds(doc) { return Math.max(1, doc.run.days) * daySeconds(doc); }

  /** Replay clock at t: day (1-based), offset in day, phase and fraction of the phase elapsed. */
  function clock(doc, t) {
    const ds = daySeconds(doc);
    const total = totalSeconds(doc);
    const tt = Math.max(0, Math.min(total, Number(t) || 0));
    let day = Math.floor(tt / ds) + 1;
    let tin = tt - (day - 1) * ds;
    if (day > doc.run.days) { day = doc.run.days; tin = ds; }
    const win = phases(doc);
    let phase = "morning";
    for (const p of [...PHASE_ORDER].sort((a, b) => (win[a] || [0])[0] - (win[b] || [0])[0])) if (win[p] && tin >= win[p][0]) phase = p;
    const [a, b] = win[phase] || [0, ds];
    const frac = b > a ? Math.max(0, Math.min(1, (tin - a) / (b - a))) : 1;
    return { t: tt, day, tin, phase, phaseFrac: frac, phaseStart: a, phaseEnd: b, daySeconds: ds, total, ended: tt >= total, windows: win };
  }

  function phaseState(clk, phase) {
    if (phase === clk.phase) return "now";
    const win = clk.windows || DEFAULT_PHASES;
    return (win[phase] || [0])[0] < (win[clk.phase] || [0])[0] ? "past" : "future";
  }
  /** How many of n items are visible when a phase is past / now (fraction f) / future. */
  function revealed(n, state, f) {
    if (n <= 0) return 0;
    if (state === "past") return n;
    if (state === "future") return 0;
    return Math.min(n, Math.floor(f * n + 1e-9) + 1);
  }

  /** Staging of one day's dates at fraction f of the date window: which step each date is at. */
  function stageDates(dates, state, f) {
    const byTable = new Map();
    dates.forEach((d, index) => {
      const table = Number.isInteger(d.table) ? d.table : index % 2;
      if (!byTable.has(table)) byTable.set(table, []);
      byTable.get(table).push(index);
    });
    return dates.map((d, index) => {
      const table = Number.isInteger(d.table) ? d.table : index % 2;
      const list = byTable.get(table);
      const slot = list.indexOf(index);
      const k = list.length;
      const steps = 2 + d.turns.length;
      let step;
      if (state === "past") step = steps;
      else if (state === "future") step = -1;
      else {
        const start = slot / k, end = (slot + 1) / k;
        if (f < start) step = -1;
        else if (f >= end) step = steps;
        else step = Math.floor(((f - start) / (end - start)) * steps);
      }
      const turnsShown = Math.max(0, Math.min(d.turns.length, step));
      return {
        index, table, slot, step, steps,
        stage: step < 0 ? "future" : step === 0 ? "walking" : step >= steps ? "done" : step === steps - 1 ? "outcome" : "talking",
        turnsShown,
        outcomesShown: step >= steps - 1,
        active: step >= 0 && step < steps,
      };
    });
  }

  function newAgentState(a) {
    return {
      id: a.id, name: a.name, persona: a.persona_summary || "", house: a.house,
      cash: a.cash0, wearing: a.wearing0 || null, inventory: a.wearing0 ? { [a.wearing0]: 1 } : {},
      status: "single", partner: null, sentence: null, profileText: null,
      sumU: 0, sumUhat: 0, nights: [], lastNight: null, needs: a.hidden || null,
      alloc: null, todayDate: null, lastDate: null, visitWith: null,
    };
  }

  function applyNight(agent, night) {
    if (typeof night.cash === "number") agent.cash = night.cash;
    if (night.wearing) agent.wearing = night.wearing;
    if (isObject(night.inventory)) agent.inventory = { ...night.inventory };
    agent.status = night.status || agent.status;
    agent.partner = night.partner || null;
    agent.sentence = night.sentence || null;
    agent.visitWith = night.visit_with || null;
    const h = night.hidden || {};
    if (typeof h.U === "number") agent.sumU += h.U;
    if (typeof h.U_hat === "number") agent.sumUhat += h.U_hat;
    agent.nights.push({ day: night.day, m: h.m || null, U: h.U ?? null, U_hat: h.U_hat ?? null, sentence: night.sentence || null });
    agent.lastNight = night;
  }

  function applyChange(byId, change) {
    const a = byId.get(change.a), b = byId.get(change.b);
    if (!a || !b) return;
    const to = change.to || "single";
    a.status = to; b.status = to;
    if (to === "single") { a.partner = null; b.partner = null; } else { a.partner = b.id; b.partner = a.id; }
  }

  /** Full HUD snapshot at time t. Pure: rebuilds from the document every call. */
  function project(doc, t) {
    const clk = clock(doc, t);
    const agents = doc.agents.map(newAgentState);
    const byId = new Map(agents.map((a) => [a.id, a]));
    const goods = doc.goods.map((g) => ({ ...g }));
    const goodById = new Map(goods.map((g) => [g.id, g]));
    const history = new Map(goods.map((g) => [g.id, []]));
    const volumes = new Map(goods.map((g) => [g.id, 0]));
    const gossip = [], visitLog = [], changes = [];
    let priced = 0; // sequential index of priced rounds across days (chart x axis)

    const addRound = (day, round) => {
      const hasPrices = round.prices && Object.keys(round.prices).length > 0;
      const volume = new Map();
      for (const c of round.clears || []) volume.set(c.good, (volume.get(c.good) || 0) + (c.volume || 0));
      for (const [gid, v] of volume) volumes.set(gid, (volumes.get(gid) || 0) + v);
      if (!hasPrices) return;
      for (const [gid, price] of Object.entries(round.prices)) {
        if (!history.has(gid)) history.set(gid, []);
        history.get(gid).push({ day, round: round.round, seq: priced, price, volume: volume.get(gid) || 0 });
      }
      priced += 1;
    };
    const applyFills = (round) => {
      for (const c of round.clears || []) for (const f of c.fills || []) {
        const buyer = byId.get(f.buyer);
        if (!buyer) continue;
        const price = typeof f.price === "number" ? f.price : c.price || 0;
        buyer.cash -= price * (f.qty || 1);
        const good = goodById.get(c.good);
        if (good && good.category !== "Food") buyer.inventory[c.good] = (buyer.inventory[c.good] || 0) + (f.qty || 1);
      }
    };

    // Past days: everything applies.
    const pastDays = doc.days.filter((d) => d.day < clk.day);
    for (const d of pastDays) {
      for (const alloc of d.allocations) { const a = byId.get(alloc.agent); if (a) { a.alloc = alloc; if (alloc.wear) a.wearing = alloc.wear; if (alloc.profile_text) a.profileText = alloc.profile_text; } }
      for (const r of d.market.rounds) { addRound(d.day, r); applyFills(r); }
      for (const p of d.app.profiles) { const a = byId.get(p.agent); if (a) { if (p.text) a.profileText = p.text; if (p.picture && p.picture.item) a.wearing = p.picture.item; } }
      for (const v of d.visits) visitLog.push({ ...v, day: d.day });
      for (const g of d.gossip) gossip.push({ ...g, day: d.day });
      for (const date of d.dates) for (const id of date.pair) { const a = byId.get(id); if (a) a.lastDate = { ...date, day: d.day }; }
      for (const c of d.relationship_changes) { changes.push({ ...c, day: d.day }); applyChange(byId, c); }
      for (const n of d.night) { const a = byId.get(n.agent); if (a) applyNight(a, { ...n, day: d.day }); }
    }

    // Today: reveal by phase.
    const today = doc.days.find((d) => d.day === clk.day) || null;
    const f = clk.phaseFrac;
    const st = (p) => phaseState(clk, p);
    const nAlloc = today ? revealed(today.allocations.length, st("morning"), f) : 0;
    const nRounds = today ? revealed(today.market.rounds.length, st("market"), f) : 0;
    const appState = st("app");
    const nProfiles = today ? revealed(today.app.profiles.length, appState, f) : 0;
    // swipes then matches share the app window: profiles in the first third, swipes in the middle, matches last
    const sub = (lo, hi) => Math.max(0, Math.min(1, (f - lo) / (hi - lo)));
    const nSwipes = today ? (appState === "now" ? revealed(today.app.swipes.length, f < 0.25 ? "future" : "now", sub(0.25, 0.8)) : revealed(today.app.swipes.length, appState, f)) : 0;
    const nMatches = today ? (appState === "now" ? revealed(today.app.matches.length, f < 0.8 ? "future" : "now", sub(0.8, 1)) : revealed(today.app.matches.length, appState, f)) : 0;
    const visitState = st("visit");
    const nVisits = today ? revealed(today.visits.length, visitState, f) : 0;
    const nGossip = today ? revealed(today.gossip.length, visitState, f) : 0;
    const dateStage = today ? stageDates(today.dates, st("date"), f) : [];
    const nNight = today ? revealed(today.night.length, st("night"), f) : 0;

    if (today) {
      today.allocations.slice(0, nAlloc).forEach((alloc) => { const a = byId.get(alloc.agent); if (a) { a.alloc = alloc; if (alloc.wear) a.wearing = alloc.wear; if (alloc.profile_text) a.profileText = alloc.profile_text; } });
      today.market.rounds.slice(0, nRounds).forEach((r) => { addRound(today.day, r); applyFills(r); });
      today.app.profiles.slice(0, nProfiles).forEach((p) => { const a = byId.get(p.agent); if (a) { if (p.text) a.profileText = p.text; if (p.picture && p.picture.item) a.wearing = p.picture.item; } });
      today.visits.slice(0, nVisits).forEach((v) => visitLog.push({ ...v, day: today.day }));
      today.gossip.slice(0, nGossip).forEach((g) => gossip.push({ ...g, day: today.day }));
      today.dates.forEach((date, i) => {
        const s = dateStage[i];
        if (s.step < 0) return;
        for (const id of date.pair) { const a = byId.get(id); if (a) a.todayDate = i; }
        if (s.outcomesShown && date.change) {
          const c = today.relationship_changes.find((x) => x.a === date.pair[0] && x.b === date.pair[1] || x.a === date.pair[1] && x.b === date.pair[0]) || { a: date.pair[0], b: date.pair[1], ...date.change };
          changes.push({ ...c, day: today.day });
          applyChange(byId, c);
        }
      });
      today.night.slice(0, nNight).forEach((n) => { const a = byId.get(n.agent); if (a) applyNight(a, { ...n, day: today.day }); });
    }

    const standings = agents.map((a) => ({ id: a.id, name: a.name, sumU: a.sumU, sumUhat: a.sumUhat, nights: a.nights.length, status: a.status, partner: a.partner, cash: a.cash }))
      .sort((x, y) => y.sumU - x.sumU || x.id.localeCompare(y.id));

    const key = [clk.day, clk.phase, nAlloc, nRounds, nProfiles, nSwipes, nMatches, nVisits, nGossip, dateStage.map((s) => s.step).join(","), nNight].join("|");
    return {
      key, clock: clk, agents, byId, goods, goodById,
      market: {
        history, volumes, priced,
        rounds: today ? today.market.rounds.slice(0, nRounds) : [],
        currentRound: today && nRounds > 0 ? today.market.rounds[nRounds - 1] : null,
      },
      app: today ? { profiles: today.app.profiles.slice(0, nProfiles), swipes: today.app.swipes.slice(0, nSwipes), matches: today.app.matches.slice(0, nMatches) } : { profiles: [], swipes: [], matches: [] },
      dates: today ? today.dates.map((d, i) => ({ ...d, day: today.day, ...dateStage[i] })) : [],
      visits: today ? today.visits.slice(0, nVisits) : [],
      visitLog, gossip, changes, standings,
      ended: clk.ended && !!(doc.source && doc.source.complete),
    };
  }

  /** Chart series for the market panel: goods grouped by category with revealed price history. */
  function marketSeries(snapshot) {
    const groups = [];
    for (const category of ["Clothing", "Games", "Food"]) {
      const goods = snapshot.goods.filter((g) => g.category === category);
      if (goods.length) groups.push({ category, goods: goods.map((g) => ({ good: g, history: snapshot.market.history.get(g.id) || [], volume: snapshot.market.volumes.get(g.id) || 0 })) });
    }
    const other = snapshot.goods.filter((g) => !["Clothing", "Games", "Food"].includes(g.category));
    if (other.length) groups.push({ category: "Other", goods: other.map((g) => ({ good: g, history: snapshot.market.history.get(g.id) || [], volume: snapshot.market.volumes.get(g.id) || 0 })) });
    return groups;
  }

  return Object.freeze({ SCHEMA, PHASE_ORDER, NEEDS, validate, clock, phaseState, revealed, stageDates, project, marketSeries, totalSeconds, daySeconds });
});
