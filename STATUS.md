# STATUS

Build log, newest entry last.

## 2026-09-28 21:00 PDT — start

Repo created, BUILD_SPEC.md written. Engine and viewer agents launched.

## Viewer

### 2026-09-28 21:20 PDT — viewer, fixture, smoke test, docs

- `viewer/index.html`, `viewer.js`, `viewer.css`: vanilla replay viewer, no build, no CDN.
  Loads `?events=<url>` (default `../runs/latest/events.jsonl`), file picker fallback, and a
  "Load sample fixture" button. Panels: town map (workspace, houses, restaurant with two
  tables, therapy office, meditation garden; agents move per allocation over a 60 s day;
  dates at tables), following camera with 30 s auto-switch, dating app (garment icon by
  tier + badge + text, animated swipes, matches with hearts, tonight's dates), market small
  multiples with hover + order book, gossip board, agent card with transcript, Reveal
  toggle (weights, shadow, U vs Û, standings), play/pause, 1×/4×/16×, day seek.
- `viewer/fixtures/make_fixture.py` → `sample-events.jsonl`: 6 agents × 3 days, 480 events,
  all 18 event types.
- `node viewer/smoke_test.js` replays the fixture through the browser's own loader: passes.
- `docs/VIEWER.md` with two headless-Chrome screenshots (`docs/viewer-*.png`).
- `viewer/publish_docs.sh` → `docs/replay/` static copy (defaults to the fixture).
- GitHub Pages: `gh api -X POST .../pages` → HTTP 422 "Your current plan does not support
  GitHub Pages for this repository." Layout left ready; `python3 -m http.server` from the
  repo root shows the viewer at `/viewer/`.
- Not done: no real run bundled yet (engine agent's job); the viewer has only been checked
  against the fixture.

## Engine

### 2026-09-28 21:55 PDT — engine on main, mock certified, tiny real run

Built in a separate worktree (`../fog-of-love-engine`, branch `engine`) after untracked engine files vanished
from the shared checkout during the viewer's setup; commits are rebased onto `origin/main` and pushed with
`git push origin engine:main`.

What works:
- `fog_of_love` package installs with `uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -e '.[test]'`
  (Concordia pinned to the coworld-concordia commit `3e30a207`).
- `fog-of-love run --model mock`: 12 agents x 7 days in ~5 s, 1.6k events, all 18 event types; the viewer's
  `STRICT=1 node viewer/smoke_test.js <events>` passes on it.
- `pytest`: 15 tests. Needs math (Dirichlet weights, bias with one shadow dimension at std 0.35, daily jitter,
  therapy halves bias, meditation shrinks jitter std by 0.9 to a 0.02 floor, U and clipped U-hat, sentence, game
  yield decay), hours normalisation, JSON extraction, 3x2 mock loop, determinism, budget guard aborting with
  `run.end{aborted: true}`, event schema (every type, required fields and types), metrics (ten sections).
- Needs, day loop, market, app, dates, visits/gossip, night, metrics, standings, CLI as in BUILD_SPEC.md.

Design choices (deviations to know about):
- Entities: Concordia `EntityAgentWithLogging` with the default `Instructions`, a `Constant` context (premise +
  "find out what makes you content" + the world rules), a `Constant` with the persona memories, `LastNObservations(40)`
  over an associative memory, and `ConcatActComponent` (one model call per act, no intermediate questions:
  cost). Weights, bias and per-need numbers are never in any prompt; the night sentence is the only feedback.
- Market: Concordia's `MarketPlace` clearing house (`_clear_auction`, trade/curve/price history) driven directly,
  without the game-master engine. Sellers are scripted (one per good, ask = list price = production cost, fresh
  stock daily); buyers' bids come from the morning JSON; unfilled bids rebid at 1.15x for three rounds; trades
  clear at the bid/ask midpoint. Goods: 6 clothes (2 per tier, 6/90/1500), 3 games (30), 3 meals (2/18/80).
- Dates: a plain 10-turn alternating chat between the two entities via `act` with a free-text spec, both
  observing every line, then a private JSON (rating, choice, reason) each. Not the dialogic game master (its
  per-turn GM calls would triple the cost and the wiring was not worth the night). Dating couples without an app
  date get a standing date each evening (that is how `propose_move_in` gets a second chance).
- Morning decision is one JSON with hours, shopping bids, wear, therapy/meditation, invite, accept_invite,
  breakup, accept_move_in, profile_text. Parse: first balanced `{}` block, trailing commas tolerated, one retry,
  then a default allocation logged with `fallback: true` and the raw text. Hours are normalised to 16 (14 with
  therapy/meditation), eat <= 2.
- Invites resolve the next morning (the invitee's inbox), so the first visit can happen on day 2.
- Starting cash uses the signaling example's "mixed" distribution (500 to 100k+), so High clothing (1500) is
  reachable for some agents: that inequality is the point of the signaling question.
- Temperature capped at 0.7; Gemma answers in fenced JSON, which the parser accepts.

Real run 1: `runs/dev-4x2-gemma-s1` (4 agents, 2 days, google/gemma-3-27b-it, budget 0.50): 52 calls, USD 0.0085
(all 52 calls reported cost), 41 s, 0 failed calls, 0 JSON fallbacks. About USD 0.001 per agent-day including
dates (~2.4k prompt tokens per call). Finding: agents scheduled eating hours but bought no meals, so food was 0
for everyone; the morning observation now states that eating consumes a bought meal. Projected 12x7 cost:
about USD 0.15, so the full 7-day run goes ahead under `--budget-usd 4.0`.
