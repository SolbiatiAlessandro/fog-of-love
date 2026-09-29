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

// every spec event type present (fixture must exercise all of them; real runs may lack some)
const missing = core.EVENT_TYPES.filter((t) => !sum.counts[t]);
const strict = !process.argv[2] || process.env.STRICT === '1';
if (strict) assert.deepStrictEqual(missing, [], `missing event types: ${missing.join(', ')}`);

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
  if (strict) {
    assert.ok(a.needs && a.needs.shadow, `${name} needs`);
    const wsum = core.NEEDS.reduce((acc, k) => acc + (a.needs.w[k] || 0), 0);
    assert.ok(Math.abs(wsum - 1) < 1e-6, `${name} weights sum ${wsum}`);
  }
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

console.log(`OK ${path.relative(process.cwd(), file)}: ${sum.total} events, ${sum.agents.length} agents, ${sum.days} days, ${allDates.length} dates, ${s.gossip.length} gossip posts, ${Object.keys(sum.counts).length} event types`);
if (missing.length) console.log(`note: types absent in this file: ${missing.join(', ')}`);
