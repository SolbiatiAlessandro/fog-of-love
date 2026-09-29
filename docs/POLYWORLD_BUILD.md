# Building the Love Town 3D viewer (Polyworld)

The 3D viewer (`polyworld_viewer/`) renders a run of Fog of Love with the real
`Metta-AI/polyworld` Nim engine: a town with houses, a workspace, a restaurant with two
tables, a therapy office and a meditation garden, dressed characters, a camera that
follows one agent, and an HTML HUD (dating app, followed agent, market, gossip, reveal).
Movement in the town is presentation staged from the recorded events; nothing is
simulated again and no model call is needed to watch a replay.

Live: <https://solbiatialessandro.github.io/fog-of-love/replay3d/> (GitHub Pages serves
`docs/`; `docs/replay3d/` is the published bundle). The 2D viewer stays at `/replay/`.

## Dependencies

- Nim 2.2.12 (`/opt/homebrew/bin/nim` on the Mac mini).
- A Polyworld checkout at `../concordia-polyworld-engine` (commit
  `8e9901670d0a6fb5acbcc4ee1053769624776dfa`) with its pinned dependencies synced under
  `tmp/coworld/deps` (`nim r coworld/tools/sync_dependencies.nim` inside the checkout).
- Emscripten 4.0.15 for the browser build; on the Mac mini it is installed at
  `/Users/tashi/Projects/heartleaf-repro-workspace-2026-09-08/emsdk`.
- Python 3.12 for the exporter (stdlib only); Node 26 for the browser smoke test.

```sh
export POLYWORLD_ENGINE="$(cd ../concordia-polyworld-engine && pwd)"      # default if omitted
export POLYWORLD_DEPS="$POLYWORLD_ENGINE/tmp/coworld/deps"                 # default if omitted
export POLYWORLD_EMSDK=/Users/tashi/Projects/heartleaf-repro-workspace-2026-09-08/emsdk
```

The private `polyworld_data` art repository is not available on this machine; the viewer
uses CC0 assets listed in `docs/ASSETS.md` or procedural geometry, never that repository.

## 1. Convert a run

```sh
python3 tools/export_polyworld_replay.py runs/dev-24x10-s4-market/events.jsonl \
  --out out/dev-24x10-s4-market.lovetown.json
.venv/bin/python -m pytest tests/test_polyworld_export.py -q     # 9 adapter tests
```

The contract is `docs/POLYWORLD_REPLAY.md` (`love-town-replay/1`). The five runs under
`runs/` are already converted in `docs/replay3d/replays/` with a `replays/index.json` for
the run picker; `publish` regenerates them.

## 2. Native build

```sh
tools/build_polyworld_viewer.sh native out/dev-24x10-s4-market.lovetown.json
build/polyworld-native/lovetown-polyworld build/polyworld-native/replay.json --play
```

The script checks the engine and dependency directories, compiles
`polyworld_viewer/main.nim` with `polyworld_viewer/config.nims`, copies the replay to
`build/polyworld-native/replay.json` and records the engine commit in
`polyworld-commit.txt`. A third argument overrides the output directory.

## 3. Browser build

```sh
tools/build_polyworld_viewer.sh web out/dev-24x10-s4-market.lovetown.json
python3 -m http.server 8767 --bind 127.0.0.1 --directory build/polyworld-web
# open http://127.0.0.1:8767/?run=dev-24x10-s4-market
```

`web` puts `emcc` from `POLYWORLD_EMSDK` on `PATH`, compiles with `-d:emscripten` (the
replay is preloaded at `/replay.json` and `polyworld_viewer/web_shell.html` is the shell),
then assembles `build/polyworld-web/`: `index.html`, `main.js`, `main.wasm`, `main.data`,
`replay_ui.js`, `replay_state.js`, `replay_ui.css`, `replay.json` and a copy of
`docs/replay3d/replays/`. The page reads `?run=<name>` (default `dev-24x10-s4-market`),
fetches `replays/<name>.lovetown.json`, writes it to the Emscripten FS before `main` runs,
and drives the scene through `Module.lovetownCommand` / `Module.lovetownState`
(see the bridge section of `docs/POLYWORLD_REPLAY.md`).

## 4. Publish to GitHub Pages

```sh
tools/build_polyworld_viewer.sh publish            # converts all runs, builds web, fills docs/replay3d/
git add docs/replay3d && git commit -m "Publish 3D replay" && git push
```

`publish` converts every run in `runs/index.json` into `docs/replay3d/replays/`, writes
`docs/replay3d/replays/index.json`, runs the `web` build against the default replay and
copies the bundle into `docs/replay3d/`. Pages serves it at `/replay3d/` on push.

`POLYWORLD_SKIP_WASM=1 tools/build_polyworld_viewer.sh publish` assembles the HTML layer
and the replays without compiling the scene: the page then says the 3D scene is pending,
runs the HUD on its own clock and shows the live date transcript in a column under the
canvas. Use it only while the Nim scene is not ready.

## 5. Verify in a browser

```sh
npm install --no-save puppeteer-core                     # once; uses the installed Chrome
node tools/polyworld_viewer_smoke.js --stub --shot /tmp/stub.png   # HUD + bridge with polyworld_viewer/stub_scene.js
node tools/polyworld_viewer_smoke.js --dir docs/replay3d --shot /tmp/web.png   # the published bundle
```

The smoke test serves the bundle, loads it in headless Chrome, waits a few seconds of
real time, and checks that the replay loaded, the run picker and dating-app cards
rendered, `Module.lovetownState` was written with projected positions, agent labels and a
speech bubble were placed from them, commands were drained, and no console error fired.
`--stub` swaps the wasm for `stub_scene.js`, a fake Nim side that implements the bridge
contract on a flat grid; it never ships. Headless Chrome on the Mac mini reports no WebGL
context, so the `--dir` check of the real bundle verifies loading and the HUD, not the
rendered scene; look at the native screenshots in `docs/` for that.

Notes: `--dump-dom --virtual-time-budget` in plain headless Chrome fires
`requestAnimationFrame` only once or twice, so the bridge cannot be checked that way;
that is why the smoke test uses puppeteer-core and real time.
