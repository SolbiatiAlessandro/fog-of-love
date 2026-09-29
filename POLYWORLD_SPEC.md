# Fog of Love — Polyworld 3D viewer spec (v1, 2026-09-28/29 night)

The shipped `viewer/` (2D HTML) does not meet the requirement. Alessandro's requirement, verbatim from the design page:

> Similar to Dress to Impress, this game is very centred on looks and dating so there should be clear focus on clothing items, high variety and quality of clothing assets, and a clear camera that shows that. There should be a simple town-like 3D set up, with shared workspace, houses, shared restaurant with two tables, therapy offices, and meditation. People eat alone when not on dates, together when on dates. Camera should follow one social agent and switch every 30 seconds.

And: "it has to be Polyworld like the previous Concordia game, it has to look pretty, agents have to have dresses."

## Reference implementation to copy from

`~/Projects/coworld-concordia/polyworld_viewer/` (Nim `main.nim` + `replay_model.nim`, browser bridge `replay_state.js` / `replay_ui.js` / `replay_ui.css` / `web_shell.html`, `config.nims`, `emscripten/`), `tools/build_polyworld_viewer.sh`, `tools/export_polyworld_replay.py`, `docs/POLYWORLD_BUILD.md`, `docs/POLYWORLD_REPLAY.md`. That viewer builds natively and for the browser against the pinned engine at `~/Projects/concordia-polyworld-engine` (commit `8e9901670d0a6fb5acbcc4ee1053769624776dfa`, deps synced under `tmp/coworld/deps`). Toolchain verified tonight: Nim 2.2.12 at `/opt/homebrew/bin/nim`; Emscripten 4.0.15 at `/Users/tashi/Projects/heartleaf-repro-workspace-2026-09-08/emsdk` (set `POLYWORLD_EMSDK` to that directory).

Engine facts that matter: `src/polyworld/characters.nim` loads glTF character models (`loadCharacterModel(file, targetHeight)`, `readGltfFile`), has toon shading (`newCharacterScene`, `useToonShading`, `setToonHour`), animation clips, `attachGear`. `src/polyworld/chargen/` (modular characters with `clothes.nim`) needs the private `polyworld_data` art repo, which is NOT available on this machine; do not depend on it. `shapes.nim` (ShapeRenderer with boxes/prisms/quads) is what the previous viewer used for procedural geometry. `rtscameras.nim` / `actioncam.nim` for cameras. Look at `examples/heartleaf/graphics.nim` and `examples/gods_of_the_arena/` for the HUD and toon look.

## Clothing assets (the point of the world)

Track A (preferred): CC0 3D characters with real garments. Quaternius "Ultimate Modular Characters" (https://quaternius.com/packs/ultimatemodularcharacters.html, page states CC0; verify the license text on the page and record URL, license and access date in `docs/ASSETS.md`). Download the pack, convert or select glTF/GLB files, and build per-tier outfits: Low = plain tee or hoodie in flat colours; Mid = shirt plus jacket or a simple dress; High = suit, gown or long coat with rich colours and an accessory. If the pack has no dresses, use the closest silhouettes and say so. Recolour materials per garment so each of the 6 clothing goods in the run looks distinct. Load with `loadCharacterModel`; animate idle/walk/sit if clips exist. Keep the total web payload reasonable (target under 25 MB; decimate or drop textures if needed).

Track B (fallback, only if Track A cannot render in the web build within ~60 minutes of trying): procedural characters via ShapeRenderer with real garment silhouettes: dress = flared inverted prism from waist to knee, jacket = torso box with lapel wedges and sleeves, coat = long prism to mid-calf, suit = jacket plus trousers in one colour, tee/hoodie = short torso box with a hood bump; tier-distinct palettes (Low flat pastels, Mid two-tone, High saturated with a metallic accent), hair variants, toon shading. It must still read as "dressed" at the camera distance used.

Either way: the worn garment must be visibly different per agent and per tier, and change when the agent changes what it wears (`night.state.wearing` / morning `wear`).

## Town

One town on the engine's terrain with toon palette and `setToonHour` following the 16-hour day: a shared workspace building, one house per agent along short streets (12 to 24 houses), a restaurant with exactly two tables (dates sit at a table facing each other; solo eaters sit alone), a therapy office, a meditation garden, trees, lamps, paths. Everything is presentation; the engine does not record physical movement, so the viewer stages it deterministically from the events.

## Staging per day (about 60 s per day at 1x)

Morning: agents leave home; work hours at the workspace, game hours at home (a glow in the window or a controller prop), home hours at home; eating at the restaurant alone; therapy at the office; meditation in the garden, in proportion to the allocated hours. Evening: matched pairs walk to the restaurant and sit at a table for the date; each `date.turn` shows as a short speech bubble above the speaker (tiny text or an HTML overlay anchored to the projected position). Visits: the guest walks to the host's house and enters. Night: everyone home; cohabiting pairs share one house. Relationship changes get a small heart or a broken-heart effect. Nothing else invented.

## Camera and HUD

Camera follows one agent at a flattering distance (three-quarter view, character fills a good part of the frame so the outfit is readable), auto-switches to another agent every 30 s (toggle), click an agent to follow. HUD (HTML layer, like the previous viewer): a prominent dating app panel (profile cards: agent name, worn garment and tier, the 240-character text, swipes, matches, tonight's dates), the followed agent's card (persona, cash, wearing, inventory, status and partner, last night's sentence, live date transcript), the market chart (clearing prices per good with volume), the gossip board, a Reveal toggle (true weights, shadow, U vs Û, standings), play/pause, 1x/4x/16x, day seek, run picker from `runs/index.json`.

## Data path

`tools/export_polyworld_replay.py runs/<name>/events.jsonl --out out/<name>.lovetown.json` produces a compact deterministic timeline (`love-town-replay/1`: agents, goods, days, per-day allocations, orders and clears, profiles/swipes/matches, dates with turns and outcomes, visits, gossip, night states, standings). The Nim viewer reads that JSON (native: path argument; web: fetched by `?run=<name>` from `replays/`). The HTML bridge follows the previous viewer's `Module.<game>Command` / `Module.<game>State` pattern; name them `lovetownCommand` / `lovetownState`: commands `play`, `pause`, `speed <n>`, `seek <t>`, `follow <agentId>`, `auto <0|1>`; state returns `{t, day, phase, followed, agents: [{id, name, x, y, z, wearing, status}], anchors for tables/houses}` so the HTML layer can place bubbles and cards.

## Build and publish

`tools/build_polyworld_viewer.sh native <replay.json>` and `... web <replay.json>` (copy and adapt the previous script). Web output to `docs/replay3d/` with all five runs converted into `docs/replay3d/replays/`, `index.html` defaulting to `dev-24x10-s4-market`. GitHub Pages already serves `docs/` at https://solbiatialessandro.github.io/fog-of-love/ so the 3D viewer will be live at `/replay3d/` on push. Update README so the 3D viewer is the primary "Watch a replay" link and the 2D one is the fallback. Native screenshots of a date, a street with several dressed agents, and the workspace go in `docs/` and the README.

## Ownership (two agents in parallel)

- Scene agent owns `polyworld_viewer/*.nim`, `polyworld_viewer/config.nims`, `polyworld_viewer/emscripten/`, `assets/` (downloaded CC0 files plus `docs/ASSETS.md`), and the native build.
- Bridge agent owns `tools/export_polyworld_replay.py`, `polyworld_viewer/*.js`, `*.css`, `web_shell.html`, `tools/build_polyworld_viewer.sh`, `docs/replay3d/`, `docs/POLYWORLD*.md`, README's replay section, and the web build/publish.
- Both: commit small, `git pull --rebase origin main` before every push, append to `STATUS.md` under "Polyworld viewer", never commit secrets, no paid model calls needed.
