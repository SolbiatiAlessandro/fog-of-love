#!/usr/bin/env node
/* Headless smoke test for the viewer's replay core.
 * Loads viewer.js the same way the browser does (no DOM), parses an events.jsonl,
 * replays it to the end, and asserts the things the panels depend on.
 *
 *   node viewer/smoke_test.js [path/to/events.jsonl]   (default: viewer/fixtures/sample-events.jsonl)
 */
const fs = require('fs');
const path = require('path');
const assert = require('assert');

const core = require(path.join(__dirname, 'viewer.js'));
const file = process.argv[2] || path.join(__dirname, 'fixtures', 'sample-events.jsonl');
const text = fs.readFileSync(file, 'utf8');

const { events, errors } = core.parseEvents(text);
assert.strictEqual(errors.length, 0, `bad lines: ${JSON.stringify(errors.slice(0, 3))}`);
assert.ok(events.length > 0, 'no events');
core.assignTimes(events);
const sum = core.summarize(events);

// Event types. The fixture (no path argument) must exercise all 18. A real run may legitimately
// never emit the social ones (visit.invite, gossip.post, relationship.change, app.match, date.*):
// STRICT=1 warns about those and fails only on the required set (setup.*, morning.allocation,
// market.*, app.profile, app.swipe, night.state, run.cost, run.end).
const missing = core.EVENT_TYPES.filter((t) => !sum.counts[t]);
const fixtureMode = !process.argv[2];
const strict = fixtureMode || process.env.STRICT === '1';
const requiredMissing = missing.filter((t) => !core.OPTIONAL_EVENT_TYPES.includes(t));
const optionalMissing = missing.filter((t) => core.OPTIONAL_EVENT_TYPES.includes(t));
if (fixtureMode) assert.deepStrictEqual(missing, [], `fixture must contain every event type; missing: ${missing.join(', ')}`);
if (strict) assert.deepStrictEqual(requiredMissing, [], `missing required event types: ${requiredMissing.join(', ')}`);
if (optionalMissing.length) console.warn(`warning: no ${optionalMissing.join(', ')} events in this run (allowed; the panels that depend on them stay empty)`);

// times are monotone and inside the run
let prev = -1;
for (const ev of events) {
  assert.ok(typeof ev.time === 'number' && ev.time >= prev, `time not monotone at t=${ev.t}`);
  prev = ev.time;
}
assert.ok(prev <= sum.days * core.DAY_SECONDS, 'event time beyond run length');

// full replay
const rp = new core.Replay(events);
const fresh = rp.seek(sum.days * core.DAY_SECONDS + 1);
assert.strictEqual(fresh.length, events.length, 'not all events applied');
const s = rp.state;
assert.strictEqual(s.agentOrder.length, sum.agents.length, 'agent count');
assert.ok(s.goods.length > 0, 'goods present');
for (const name of s.agentOrder) {
  const a = s.agents[name];
  assert.ok(a.persona_summary.length > 0, `${name} has no persona`);
  assert.strictEqual(a.nights.length, sum.days, `${name} nights != days`);
  assert.ok(typeof a.cash === 'number', `${name} cash`);
  assert.ok(a.wearing, `${name} wearing`);
  assert.ok(a.inventory && typeof a.inventory === 'object' && !Array.isArray(a.inventory), `${name} inventory is {item: qty}`);
  if (strict) {
    assert.ok(a.needs && a.needs.shadow, `${name} needs`);
    const wsum = core.NEEDS.reduce((acc, k) => acc + (a.needs.w[k] || 0), 0);
    assert.ok(Math.abs(wsum - 1) < 1e-6, `${name} weights sum ${wsum}`);
  }
}
// goods are normalised to one vocabulary whatever the producer wrote
for (const g of s.goods) {
  assert.ok(['clothing', 'game', 'food', 'other'].includes(g.category), `good ${g.id} category ${g.category}`);
  assert.ok(g.tier === null || g.tier === g.tier.toLowerCase(), `good ${g.id} tier ${g.tier}`);
  assert.ok(typeof s.trades[g.id] === 'number', `trade count for ${g.id}`);
}
// profile texts: a string (today's or an earlier one, flagged) or null, never ''
for (const p of Object.values(s.app.profiles)) {
  assert.ok(p.text === null || (typeof p.text === 'string' && p.text.length > 0), `profile text for ${p.name}`);
  assert.ok(typeof p.fallback === 'boolean', `profile fallback flag for ${p.name}`);
}
// price history: every good has days*rounds points
const rounds = Math.max(...Object.values(s.priceHistory).map((h) => h.length));
for (const g of s.goods) assert.strictEqual((s.priceHistory[g.id] || []).length, rounds, `price history for ${g.id}`);
// dates: each has a scene, turns and two outcomes; the fixture has 10-turn dates
const allDates = s.lastDates.concat(s.dates);
for (const d of allDates) {
  assert.ok(d.scene, 'date scene');
  assert.ok(d.turns.length >= 1, 'date turns');
  assert.strictEqual(d.outcomes.length, 2, 'date outcomes');
}
// gossip newest first
for (let i = 1; i < s.gossip.length; i++) assert.ok(s.gossip[i - 1].t >= s.gossip[i].t, 'gossip order');
// seeking backwards rebuilds correctly
const rp2 = new core.Replay(events);
rp2.seek(core.DAY_SECONDS * 1.5);
const midDay = rp2.state.day;
rp2.seek(10);
assert.ok(rp2.state.day <= midDay, 'backward seek');
assert.strictEqual(rp2.applied, events.filter((e) => e.time <= 10).length, 'backward seek applied count');
// standings
const st = rp.standings();
assert.strictEqual(st.length, s.agentOrder.length);
for (let i = 1; i < st.length; i++) assert.ok(st[i - 1].sumU >= st[i].sumU);
if (strict) assert.ok(s.end, 'run.end present');

const soldUnits = Object.values(s.trades).reduce((acc, n) => acc + n, 0);
const untraded = s.goods.filter((g) => !s.trades[g.id]).map((g) => g.id);
console.log(`OK ${path.relative(process.cwd(), file)}: ${sum.total} events, ${sum.agents.length} agents, ${sum.days} days, ${allDates.length} dates, ${s.gossip.length} gossip posts, ${s.visitLog.length} visit invites, ${soldUnits} units sold (${untraded.length} goods never traded), ${Object.keys(sum.counts).length}/${core.EVENT_TYPES.length} event types`);
if (missing.length) console.log(`note: types absent in this file: ${missing.join(', ')}`);
