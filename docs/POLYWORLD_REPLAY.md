# Love Town replay contract (`love-town-replay/1`)

`tools/export_polyworld_replay.py` converts one run's `runs/<name>/events.jsonl` (the
`BUILD_SPEC.md` event stream) into a compact, deterministic JSON timeline for the Nim
Polyworld viewer (`polyworld_viewer/`). The adapter never invents movement, locations,
timing or outcomes; the viewer stages everything from the per-day facts below.

```sh
python3 tools/export_polyworld_replay.py runs/dev-24x10-s4-market/events.jsonl \
  --out out/dev-24x10-s4-market.lovetown.json
```

Stdlib only. The output is `json.dumps(..., sort_keys=True, indent=1)` with a trailing
newline, so identical input gives byte-identical output. Conversion fails (exit 2) when
the input has no `setup.world`, has a duplicate agent name, references an unknown agent
or good, has non-increasing `t`, or lacks `run.end` (pass `--allow-incomplete` to convert
a partial run; `source.complete` is then `false`). Optional `--name <run>` overrides the
run name derived from the parent directory.

## Identifiers

- **Agent ids** are `agent-000`, `agent-001`, ... in `setup.world` `agents` order. Every
  agent reference in the file (allocations, orders, fills, swipes, matches, dates, visits,
  gossip `about`, night states, standings) uses the id, never the display name. Names live
  only in `agents[].name`.
- **Good ids** are the recorded good ids as written in `setup.world` `goods` (for example
  `"Linen Shirt"`); they are the same strings used in `wearing`, `inventory`, orders,
  fills, prices and `picture.item`.
- Sellers are market stalls, not agents. Ask orders carry `seller: <good id>`; a fill
  records only the buyer.
- Days are 1-based (`day: 1` is the first simulated day), as in `events.jsonl`. Market
  rounds are 0-based, as recorded.

## Presentation clock

The JSON carries no seconds. Both the Nim viewer and the HTML layer share this convention
(`timeline` block, also copied from the 2D viewer): one day plays over **60 s at 1x**, so
replay time `t` (seconds) maps to `day = floor(t / 60) + 1` and the offset within the day
picks the phase:

| phase   | seconds in day | staged content                                              |
| ------- | -------------- | ----------------------------------------------------------- |
| morning | 0 – 10         | agents leave home, `allocations` (work, games, home, eat, therapy, meditation) |
| market  | 10 – 20        | `market.rounds` in order (asks, bids, clears)               |
| app     | 20 – 34        | `app.profiles`, `app.swipes`, `app.matches`                 |
| visit   | 34 – 38        | accepted `visits` (guest walks to host's house)             |
| date    | 38 – 55        | `dates` in order, each turn evenly spaced inside the window |
| night   | 55 – 60        | `night` states, `relationship_changes` effects, everyone home |

Within one phase the items are staged in list order, spread evenly across the window
(`date` turns: the window is split evenly among the day's dates, then among each date's
turns). `run.days * 60` is the total length; `t` beyond the end is clamped.

## Top-level object

```json
{
  "schema": "love-town-replay/1",
  "source": {
    "path": "runs/dev-24x10-s4-market/events.jsonl",
    "sha256": "…",
    "event_count": 2907,
    "complete": true
  },
  "run": {
    "name": "dev-24x10-s4-market",
    "seed": 4,
    "model": "google/gemma-3-27b-it",
    "days": 10,
    "agent_count": 24,
    "calls": 922,
    "total_usd": 0.3354
  },
  "timeline": {"day_seconds": 60, "phases": {"morning": [0, 10], "market": [10, 20], "app": [20, 34], "visit": [34, 38], "date": [38, 55], "night": [55, 60]}},
  "agents": [],
  "goods": [],
  "days": [],
  "standings": []
}
```

`run.calls` / `run.total_usd` come from `run.end` (`null` when absent). `run.model` and
`run.seed` come from `setup.world` (`null` when absent).

### `agents[]`

```json
{
  "id": "agent-000",
  "name": "Ulysses Vance",
  "persona_summary": "Ulysses is a 35-year-old professor, …",
  "cash0": 9276.08,
  "wearing0": "Thrift Hoodie",
  "house": 0,
  "hidden": {
    "w": {"food": 0.499, "hugs": 0.057, "money": 0.426, "fun": 0.019},
    "shadow": "money",
    "bias": {"food": -0.164, "hugs": -0.001, "money": 0.085, "fun": 0.015}
  }
}
```

`house` is the agent's house index (equal to the agent's position in the list; the viewer
lays houses out along streets by this index). `hidden` comes from `setup.needs`
(`w` = true Dirichlet weights, `shadow` = the shadow need, `bias` = the recorded `b`);
it is `null` when the run has no `setup.needs` for that agent. Show `hidden` only behind
the Reveal toggle.

### `goods[]`

```json
{"id": "Linen Shirt", "category": "Clothing", "tier": "Mid", "list_price": 90.0}
```

Category is one of `Clothing`, `Games`, `Food` as recorded; tier is `Low`, `Mid`, `High`
or `Standard` (games). The six clothing goods are the garments the characters wear.

### `days[]` — one object per simulated day, in order

```json
{
  "day": 1,
  "allocations": [],
  "market": {"rounds": []},
  "app": {"profiles": [], "swipes": [], "matches": []},
  "visits": [],
  "dates": [],
  "gossip": [],
  "relationship_changes": [],
  "night": []
}
```

Every list keeps the recorded order (by `t`). Each item carries `t` (the source sequence
number) so the viewer can order across lists when it needs to.

**`allocations[]`** — from `morning.allocation`, one per agent per day:

```json
{
  "t": 26, "agent": "agent-000",
  "hours": {"work": 13, "games": 0, "home": 0, "eat": 1},
  "therapy": false, "meditation": true,
  "invite": null, "accept_invite": null,
  "breakup": false, "propose_move_in": false, "accept_move_in": false,
  "wear": "Thrift Hoodie",
  "shopping": [{"good": "Linen Shirt", "price": 90.0, "qty": 1}],
  "profile_text": "Professor. Reader. Thinker. …",
  "fallback": false
}
```

`invite` / `accept_invite` are agent ids or `null`. `wear` is the good the agent chose to
wear for the day (`null` if unrecorded); `profile_text` is `null` when the model gave none.
Fields missing in older runs (`propose_move_in`, `accept_move_in`, `home_hours_adjusted`)
default to `false`. The model's raw text is not copied.

**`market.rounds[]`** — one per `market.prices` event (3 per day in the real runs):

```json
{
  "round": 0,
  "asks": [{"t": 50, "good": "Thrift Hoodie", "price": 6.0, "qty": 20, "stock": 20}],
  "bids": [{"t": 62, "agent": "agent-000", "good": "Linen Shirt", "price": 90.0, "qty": 1, "auto": false}],
  "clears": [{"t": 85, "good": "Thrift Hoodie", "price": 6.0, "ask": 6.0, "remaining": 20, "volume": 0,
              "fills": [{"buyer": "agent-004", "qty": 1, "price": 6.0}]}],
  "prices": {"Thrift Hoodie": 6.0, "Linen Shirt": 90.0},
  "asks_after": {"Thrift Hoodie": 6.0},
  "stock_after": {"Thrift Hoodie": 20}
}
```

Orders and clears are grouped into the round they were recorded with (`round` field; when
an order has no `round`, it belongs to the next `market.prices` that follows it). `volume`
is the sum of `fills[].qty`. `auto` marks auto-bought meals (default `false`); `stock`,
`ask`, `remaining`, `asks_after`, `stock_after` are `null`/`{}` when the run did not record
them. A fill's `price` defaults to the clear price when unrecorded. Orders left after the
last `market.prices` of a day form a final round with `prices: {}`.

**`app.profiles[]`** — from `app.profile`, in recorded order (only the agents who used
the app that day; cohabiting and dating agents skip it):

```json
{"t": 200, "agent": "agent-000", "picture": {"item": "Linen Shirt", "tier": "Mid"}, "text": "Professor. Reader. Thinker. …"}
```

`text` is `null` when the model gave none (the HTML layer falls back to the last
non-empty text of that agent). **`app.swipes[]`**: `{"t", "agent", "target", "yes"}`.
**`app.matches[]`**: `{"t", "a", "b"}`.

**`visits[]`** — from `visit.invite`: `{"t", "host": "agent-005", "guest": "agent-000", "accepted": false}`
(`host` is the inviter `name`, `guest` the invited `target`). Only `accepted: true` visits are
staged as a walk to the host's house.

**`dates[]`** — one per `date.scene`, in order, with the turns and outcomes of that pair:

```json
{
  "t": 352, "pair": ["agent-005", "agent-006"],
  "scene": "Diana Evans and Yusuf Zhang meet for a date at the Love Town restaurant. …",
  "table": 0,
  "turns": [{"t": 353, "speaker": "agent-005", "text": "So, you're a lawyer as well? …"}],
  "outcomes": [{"t": 363, "agent": "agent-005", "partner": "agent-006", "rating": 6.0, "choice": "ask_again", "reason": "…", "fallback": false}],
  "change": {"from": "single", "to": "dating"}
}
```

`table` is `index % 2` of the date within the day (the restaurant has exactly two tables;
dates are sequential, so a table is reused across dates). `change` is the
`relationship.change` recorded for that pair on that day, or `null`. A `date.turn` or
`date.outcome` without a preceding `date.scene` for the pair creates a date with
`scene: ""`. `rating` is a number or `null`; `choice` is `ask_again`, `propose_move_in`,
`decline` or whatever the run recorded.

**`gossip[]`** — from `gossip.post`: `{"t", "text", "about": ["agent-002", "agent-007"]}`.

**`relationship_changes[]`** — every `relationship.change` of the day:
`{"t", "a", "b", "from", "to"}` (`to` in `single`, `dating`, `cohabiting`).

**`night[]`** — from `night.state`, one per agent per day:

```json
{
  "t": 436, "agent": "agent-000",
  "cash": 9340.08,
  "wearing": "Linen Shirt",
  "inventory": {"Thrift Hoodie": 1, "Linen Shirt": 1},
  "status": "dating", "partner": "agent-013",
  "sentence": "Last night you felt 61% content.",
  "hours": {"work": 13, "games": 0, "home": 0, "eat": 1},
  "meals_eaten": 1, "hug_hours": 0.0, "fun_points": 0.0,
  "therapy": false, "meditation": true, "visit_with": null,
  "hidden": {"m": {"food": 0.5, "hugs": 0.0, "money": 1.0, "fun": 0.0}, "U": 0.6753, "U_hat": 0.6076, "sum_U": 0.6753,
             "jitter": {"food": 0.045, "hugs": -0.122, "money": -0.092, "fun": 0.101}}
}
```

Everything outside `hidden` is what the agent itself can see. `hidden` (`m`, `U`, `U_hat`,
`sum_U`, `jitter`) is only for the Reveal toggle. `partner` and `visit_with` are agent ids
or `null`.

### `standings[]`

Final author-level standings, sorted by `sum_U` descending, then by id:

```json
{"rank": 1, "agent": "agent-006", "sum_U": 7.91, "sum_U_hat": 7.40, "nights": 10, "mean_U": 0.791,
 "status": "cohabiting", "partner": "agent-005", "cash": 25102.7}
```

`sum_U` is the sum of `night[].hidden.U` over the run; this is hidden information and
belongs behind Reveal (the same rule as `standings.md`).

## Browser bridge (`web_shell.html` ↔ Nim)

The HTML layer (`polyworld_viewer/replay_ui.js`) owns the HUD; the Nim scene owns the
canvas. They talk through two `Module` members, mirroring the previous viewer's
`concordiaCommand` / `concordiaState`:

**`Module.lovetownCommand`** is a JavaScript array of command strings that the HTML layer
pushes onto. The Nim side drains it every frame (`Module.lovetownCommand.shift()`) and
applies each command in order:

| command             | meaning                                                   |
| ------------------- | --------------------------------------------------------- |
| `play`              | resume the replay clock                                   |
| `pause`             | stop the replay clock                                     |
| `speed <n>`         | clock multiplier, `1`, `4` or `16`                        |
| `seek <t>`          | set the replay clock to `t` seconds (float, clamped)      |
| `follow <agentId>`  | camera follows that agent and disables auto-switching     |
| `auto <0\|1>`       | disable / enable the 30 s auto-switch of the followed agent |

**`Module.lovetownState`** is written by the Nim side once per frame (assign the parsed
object: `Module.lovetownState = JSON.parse(payload)`); the HTML layer polls it in its own
`requestAnimationFrame` loop. If the Nim side instead exposes a function, the HTML calls
it without arguments and uses the return value. The object:

```json
{
  "t": 123.4, "day": 3, "phase": "date",
  "playing": true, "speed": 1, "auto": true,
  "followed": "agent-004",
  "agents": [
    {"id": "agent-004", "name": "Taylor Thompson", "x": 12.0, "y": 0.0, "z": -3.5,
     "wearing": "Leather Jacket", "status": "dating", "place": "table",
     "sx": 0.51, "sy": 0.38, "visible": true}
  ],
  "anchors": {
    "tables": [{"x": 30.0, "y": 0.0, "z": 4.0, "sx": 0.6, "sy": 0.4}, {"x": 34.0, "y": 0.0, "z": 4.0, "sx": 0.7, "sy": 0.45}],
    "houses": [{"agent": "agent-000", "x": -20.0, "y": 0.0, "z": 10.0, "sx": 0.2, "sy": 0.7}],
    "workspace": {"x": 0.0, "y": 0.0, "z": -30.0}, "restaurant": {"x": 32.0, "y": 0.0, "z": 4.0},
    "therapy": {"x": 40.0, "y": 0.0, "z": -20.0}, "garden": {"x": -40.0, "y": 0.0, "z": -20.0}
  }
}
```

`x, y, z` are world coordinates (informational). `sx, sy` are the projected canvas
position of a point just above the agent's head, normalised to `0..1` of the canvas
(origin top-left), and `visible` says whether that point is inside the frame; the HTML
layer anchors speech bubbles and name labels with them. If `sx`/`sy` are absent the
HTML falls back to a transcript column instead of bubbles. `place` is one of `home`,
`street`, `work`, `restaurant`, `table`, `therapy`, `garden`, `visit`. `phase` is one of
the six phase names above (or `setup` before the first day).

Optional: `Module.lovetownReady` — set to `true` (or called, if the HTML made it a
function) once the replay is loaded and the first frame rendered; the HTML enables the
controls then.

**Loading.** Native: the replay path is the first CLI argument. Web: the shell fetches
`replays/<run>.lovetown.json` for `?run=<name>` (default `dev-24x10-s4-market`, list from
`replays/index.json`), writes it to the Emscripten FS at `/replay.json` before `main`
runs, and the Nim side reads `/replay.json`. The build also preloads a default replay at
that path so the page works without the fetch.
