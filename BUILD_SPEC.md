# Fog of Love — build spec (v1, overnight 2026-09-28/29)

Working title: **Fog of Love**. The world is **Love Town**. Owner: Alessandro Solbiati. Builder: Tashi (Claude agents).
Authoritative design page: `~/Tashi/alignment-knowledge-base/wiki/concepts/love-town-design.md` (read it first).
Reference implementation to reuse from: `~/Projects/coworld-concordia` (private, checkout on this machine).

Premise (verbatim, goes in the README and in every agent's context):
> You just arrived in Love Town, you are a young single career professional, just out of college. You are still discovering your needs, and you just want to be happy. But oh boy.. How to be happy? And even more.. What is love?

## Deliverables (in priority order)

1. `fog_of_love` Python package: engine, CLI, events.jsonl, metrics, tests, mock-model certification.
2. `viewer/`: self-contained HTML/JS replay viewer (no build step, opens from a static server), reads an `events.jsonl` produced by the engine. Dating app panel is first-class.
3. A real dev run: 12 agents, 7 days, house model `google/gemma-3-27b-it` via OpenRouter. **Hard budget: USD 6.00 total for all real runs tonight.** Estimate with a mock run first; abort any run that projects above budget.
4. `runs/<name>/` committed with events.jsonl and the metrics report; `README.md` explains play, watch, develop; a GIF or PNGs of the viewer in `docs/`.
5. GitHub: everything pushed to `SolbiatiAlessandro/fog-of-love` (private). Try to enable GitHub Pages from `/docs` or a `gh-pages` branch serving the viewer + a bundled run; if Pages is unavailable on this plan, ship the viewer so `python -m http.server` in the repo root shows it, and note that in README.

## Model access

`OPENROUTER_API_KEY` is read from the environment for real runs (keep it in a local env file outside the repo). **Never print, log, commit, or echo the key.** Reuse the OpenRouter client from `~/Projects/coworld-concordia/src/concordia_coworld/llm.py` (ModelHub, cost tracking, call log). `mock` model must run the whole loop with canned outputs for tests and certification.

## Engine

Concordia: pin the same commit as coworld-concordia (`gdm-concordia @ git+https://github.com/google-deepmind/concordia.git@3e30a207bb2b75f9cf837fa6b657c466ca450765`). Use Concordia for: agent entities (persona memories, the default `Instructions` component, associative memory), the dialogic game master for dates, and `concordia.contrib.components.game_master.marketplace.MarketPlace` (clearing_house) for the market. Everything else (needs, day loop, app, relationships, gossip, scoring) is ours in plain Python. The 50 personas: reuse `vendor/examples/signaling/configs/personas.py` from coworld-concordia (copy the file; keep the Apache header). Gender is ignored by all mechanics in v1; matching is any-to-any.

### Needs and utility

- Needs k ∈ {food, hugs, money, fun}. Weights `w ~ Dirichlet(alpha=[1,1,1,1])`, one draw per agent, fixed.
- Daily met-fraction `m_k ∈ [0,1]`, saturating:
  - food: meals eaten today / 2 (max 1). Any restaurant tier feeds equally.
  - hugs: overlapping home hours with a cohabiting partner (or an invited guest visit) / 4 (max 1). Singles without a visit: 0.
  - money: cash earned today / 8 hours' wage (max 1). Wage: 12/hour.
  - fun: Σ over hours played of the game's current yield / 4 (max 1). Each owned game's yield starts at 1.0 and decays ×0.8 per hour played (per game, persistent). No game owned: 0.
- True utility `U_t = Σ_k w_k · m_k,t`. Observed `Û_t = clip(Σ_k w_k · (m_k,t + b_k + j_k,t), 0, 1)`.
- Bias `b_k ~ N(0, 0.10)` per agent per dimension, drawn once; one dimension chosen uniformly gets `b_k ~ N(0, 0.35)` (the shadow). Jitter `j_k,t ~ N(0, 0.10)` fresh daily.
- Therapy (cost 60, takes 2 hours): multiply all `b_k` by 0.5. Meditation (free, takes 2 hours): multiply jitter std by 0.9 (persistent, floor 0.02).
- The character is told only: `Last night you felt {round(100*Û)}% content.` Never U, w, b, m.
- Author-level score for standings: `Σ_t U_t` per agent (world-computed, never shown to the character).

### Day loop (per day d = 1..D)

1. **Morning decision** (one model call per agent, JSON): allocate 16 hours across `work`, `games`, `home`, `eat` (eat ≤ 2, each meal 1 hour); shopping list (bids into the market: clothes tiers, games, meals at restaurant tiers); optional `therapy`/`meditation` (2 hours each, at most one per day); app actions (see below); if cohabiting: optional `breakup`. Observation given: cash, inventory, owned games and their yields, partner status, yesterday's content sentence, the gossip board (last 3 days), app inbox.
2. **Market** (Concordia MarketPlace, clearing_house, 3 rounds): sellers as in the signaling example (one per good, production cost = list price). Goods: Clothing Low/Mid/High (2 items each, list prices 6 / 90 / 1500; zero function; worn item shown on app picture and dates), Games (3 items, 30 each), Food Low/Mid/High meals at the restaurant (2 / 18 / 80; each feeds one meal). Keep price history per good per round.
3. **Dating app**: each single (and each dating, not cohabiting) agent has a profile: `picture` = currently worn clothing item + tier, `text` ≤ 240 chars written by the agent. Each morning the agent sees up to 5 profiles (random, excluding current partner and exes of ≤2 days) and swipes yes/no on each. Mutual yes ⇒ a date that evening (one date per agent per day; resolve conflicts by random priority). Cohabiting agents do not see the app.
4. **Dates** (evening): Concordia dialogic game master, 10 turns, at the restaurant. Scene text from the world: both outfits named with tier; each agent's *stated* schedule for the day is visible to the other. After the date, each agent answers privately: (a) rating 0–10 (memory only, never scored), (b) choice ∈ {ask_again, propose_move_in, decline}. Mutual ask_again ⇒ `dating`; mutual propose_move_in (or one proposes and the other, already dating, accepts next morning) ⇒ `cohabiting`.
5. **Visits**: a single agent may `invite` another single to its home in the morning decision; if the invitee accepts (morning call includes inbox), both get hug hours = min of their home hours that day. The world posts `"{A} was seen leaving {B}'s place late."` to the public gossip board. It never adds any judgment.
6. **Night**: compute m, U, Û; append the content sentence to the agent's memory; log everything.

Breakup: either partner can `breakup` in the morning; status → single for both; shared inventory stays with the buyer of each item. Exes cannot match for 2 days.

### Events (events.jsonl, one JSON object per line; the viewer depends on this exactly)

Common fields: `{"t": <int seq>, "day": <int>, "phase": "morning"|"market"|"app"|"date"|"visit"|"night"|"setup", "type": <string>, ...}`

- `setup.world`: `{agents: [{name, persona_summary, cash, wearing}], goods: [{id, category, tier, list_price}], days, seed}`
- `setup.needs` (hidden; viewer shows only when "reveal" toggled): `{name, w: {food,hugs,money,fun}, shadow: <need>}`
- `morning.allocation`: `{name, hours: {work,games,home,eat}, therapy: bool, meditation: bool, invite: <name|null>, breakup: bool, raw: <model text>}`
- `market.order`: `{name, side: "bid"|"ask", good, price, qty}`
- `market.clear`: `{good, price, filled: [{buyer, seller, qty}]}` and `market.prices`: `{round, prices: {good: price}}`
- `app.profile`: `{name, picture: {item, tier}, text}`
- `app.swipe`: `{name, target, yes: bool}`
- `app.match`: `{a, b}`
- `date.scene`: `{a, b, text}`; `date.turn`: `{a, b, speaker, text}`; `date.outcome`: `{name, partner, rating, choice}`; `relationship.change`: `{a, b, from, to}`
- `visit.invite`: `{name, target, accepted}`; `gossip.post`: `{text, about: [names]}`
- `night.state`: `{name, m: {...}, U, U_hat, sentence, cash, inventory, wearing, partner, status}`
- `run.cost`: `{calls, usd}` (periodic) and `run.end`: `{days, total_usd}`

### CLI

`fog-of-love run --out runs/<name> --model google/gemma-3-27b-it|mock --num-agents 12 --num-days 7 --seed 1 [--budget-usd 6]`
`fog-of-love metrics runs/<name>` → writes `runs/<name>/metrics.md` and `metrics.json`
`fog-of-love standings runs/<name>` → author-level ranking on Σ U

Budget guard: track USD from the ModelHub; stop the run cleanly (write `run.end` with `aborted: true`) when the projected total exceeds `--budget-usd`.

### Metrics (metrics.md; each with the number and one sentence)

1. Clothes spend per agent-day before vs after cohabiting.
2. Marker convergence: share of the most-worn High/Mid clothing item on app pictures by day; was it first worn by the most-matched agent (prestige) or the most-seen (conformity)?
3. Compensatory consumption: correlation of unmet hugs (1 − m_hugs) with clothes tier bought, singles only.
4. Profile text: length, mention of schedule/work/money/looks per day; match rate by mention.
5. Pairing: need-weight distance between matched pairs vs random pairs; breakup vs need distance.
6. Gossip: number of visits, posts, and refusals/declines that cite gossip (string match on the board's names in decline reasons).
7. Couples: work hours of each partner before/after; cash transfers if any.
8. Fun: hours on games by day; agents with fun-dominant weights who never date.
9. Self-knowledge: per agent, day of first therapy/meditation; shadow dimension vs which need they under/over-serve.
10. Love residual: for cohabiting agents, days on which a better-fit (lower need distance) willing single existed and they stayed.

## Viewer (`viewer/index.html`, `viewer.js`, `viewer.css`, vanilla JS, no build)

Load `?events=<url to events.jsonl>`. Panels:
- **Town map** (2D, top-down, simple shapes/sprites): workspace, houses (one per agent), restaurant with two tables, therapy office, meditation garden. Agents are placed by their allocation across the day (a day plays over ~60 s at 1×); dates put both agents at a restaurant table.
- **Camera**: follows one agent; auto-switches every 30 s (toggle); clicking an agent follows it.
- **Dating app panel** (prominent): current day's profile cards (outfit picture as a colored garment icon + tier badge + the 240-char text), swipes as they happen, matches with a heart, tonight's dates listed.
- **Market chart**: all goods on one price chart with history; current bids/asks.
- **Gossip board**: the public posts, newest first.
- **Selected agent card**: persona summary, cash, wearing, inventory, partner/status, last night's sentence, the date transcript when on a date. A **Reveal** toggle shows true weights, shadow, U vs Û (off by default).
- **Standings**: author-level Σ U, shown only at the end (or under Reveal).
- Controls: play/pause, speed 1×/4×/16×, day seek.

## Tests and certification

- `pytest`: needs math (U, Û, bias/jitter, therapy/meditation), day loop with mock model for 3 agents × 2 days, event schema validation (every event type present, fields typed), metrics on a fixture, budget guard aborts.
- `fog-of-love run --model mock` must complete 12 agents × 7 days in under 2 minutes and produce a viewer-loadable events.jsonl (`viewer/` opened against it in a headless check if possible; otherwise document a manual check).

## Repo layout

```
fog-of-love/
  README.md  BUILD_SPEC.md  STATUS.md (progress log, newest last)  pyproject.toml
  src/fog_of_love/  {needs.py, world.py, agents.py, market.py, app.py, dates.py, gossip.py, events.py, metrics.py, standings.py, llm.py, cli.py}
  src/fog_of_love/vendor/personas.py  (copied, Apache header kept)
  viewer/  runs/  docs/  tests/
```

## Rules for the builders

- Commit early and often with clear messages; push to origin main. Never commit secrets or the call log.
- Keep STATUS.md current: what works, what does not, costs, commands.
- Prefer boring code. No new frameworks. Python 3.12, `uv`.
- Real runs only after the mock run and the budget estimate; total real spend tonight ≤ USD 6.00.
