/* Stand-in for the Nim scene, used only to verify the HTML layer and the bridge without WebGL.
 * It drains Module.lovetownCommand and writes Module.lovetownState exactly as
 * docs/POLYWORLD_REPLAY.md describes, with agents placed on a flat grid and the dating pairs
 * at two "tables". Never shipped in docs/replay3d/.
 */
(function () {
  'use strict';
  const M = window.Module;
  const D = window.LoveTownReplay;
  let doc = null, t = 0, playing = true, speed = 1, auto = true, followed = null, autoTimer = 0, last = performance.now();
  function ready() {
    doc = M.lovetownDocument;
    if (!doc) { setTimeout(ready, 30); return; }
    followed = doc.agents[0].id;
    if (typeof M.lovetownReady === 'function') M.lovetownReady(); else M.lovetownReady = true;
    requestAnimationFrame(frame);
  }
  function apply(cmd) {
    const [op, arg] = String(cmd).split(/\s+/);
    if (op === 'play') playing = true; else if (op === 'pause') playing = false;
    else if (op === 'speed') speed = Number(arg) || 1;
    else if (op === 'seek') t = Math.max(0, Math.min(D.totalSeconds(doc), Number(arg) || 0));
    else if (op === 'follow') { if (doc.agents.some((a) => a.id === arg)) followed = arg; auto = false; }
    else if (op === 'auto') auto = arg === '1';
  }
  function frame(now) {
    const dt = Math.min(0.1, (now - last) / 1000); last = now;
    while (M.lovetownCommand.length) apply(M.lovetownCommand.shift());
    if (playing) t = Math.min(D.totalSeconds(doc), t + dt * speed);
    if (auto) { autoTimer += dt; if (autoTimer >= 30) { autoTimer = 0; const i = doc.agents.findIndex((a) => a.id === followed); followed = doc.agents[(i + 1) % doc.agents.length].id; } }
    const snap = D.project(doc, t);
    const cols = Math.ceil(Math.sqrt(doc.agents.length));
    const tables = [{ x: 30, y: 0, z: 4, sx: 0.35, sy: 0.35 }, { x: 34, y: 0, z: 4, sx: 0.65, sy: 0.35 }];
    const agents = doc.agents.map((a, i) => {
      const st = snap.byId.get(a.id);
      let sx = 0.1 + (i % cols) / cols * 0.8, sy = 0.55 + Math.floor(i / cols) / cols * 0.4, place = 'home';
      const date = snap.dates.find((d) => d.active && d.pair.includes(a.id));
      if (date) { const tb = tables[date.table]; sx = tb.sx + (date.pair[0] === a.id ? -0.06 : 0.06); sy = tb.sy; place = 'table'; }
      return { id: a.id, name: a.name, x: (sx - 0.5) * 100, y: 0, z: (sy - 0.5) * 100, wearing: st.wearing, status: st.status, place, sx, sy, visible: true };
    });
    M.lovetownState = { t, day: snap.clock.day, phase: snap.clock.phase, playing, speed, auto, followed, agents,
      anchors: { tables, houses: doc.agents.map((a, i) => ({ agent: a.id, x: 0, y: 0, z: 0, sx: agents[i].sx, sy: agents[i].sy })), workspace: { x: 0, y: 0, z: -30 }, restaurant: { x: 32, y: 0, z: 4 }, therapy: { x: 40, y: 0, z: -20 }, garden: { x: -40, y: 0, z: -20 } } };
    requestAnimationFrame(frame);
  }
  ready();
})();
