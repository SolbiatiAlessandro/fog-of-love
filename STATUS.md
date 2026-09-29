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

### 2026-09-28 21:47 PDT — viewer on the real run, run picker, real screenshots

- Checked the viewer in headless Chrome against `runs/dev-12x7-s1` (12 × 7, Gemma 27B). What broke or looked wrong,
  now fixed in `viewer/viewer.js`: goods `category`/`tier` are capitalised (`"Clothing"`, `"Mid"`) where the fixture
  used lowercase, so all market groups were empty and badges grey (normalised on load); market rounds start at 0
  (fixture: 1), which pushed the first price point off-axis (points placed by offset from the first round seen);
  `night.state.inventory` is `{item: qty}`, not a list (was ignored, and meals leaked into inventory); two
  `app.profile.text: null` (Victoria Walker) now fall back to the agent's last text, marked, or "no profile text";
  12 houses laid out 10 + 2 (now balanced 6 + 6); long personas (415 chars) clamp to four lines with a toggle.
- Market: every clearing price in the run equals the list price, so the lines are flat; the chart now draws volume
  dots (area ∝ units sold) and labels each good with units sold, and a good that never traded (both High garments,
  Thrift Hoodie, Dungeon Delve, Tasting Menu) is faint, dotted and labelled "no trades". Right padding fits the labels.
- Also: standing dates (couples already dating, no match) listed under the matches; date outcomes show the stated
  reason; gossip board lists visit invites (Fiona's four declined ones) instead of being blank; agent card shows
  shopping bids, accepted invite/move-in, and a `fallback` chip; camera opens on the followed agent instead of
  flying in; entry animations off under `prefers-reduced-motion`; Standings panel moved under the market.
- `viewer/smoke_test.js`: `STRICT=1` now fails only on the always-required types (setup.*, morning.allocation,
  market.*, app.profile, app.swipe, night.state, run.cost, run.end) and warns on the optional ones (gossip.post,
  visit.invite, relationship.change, app.match, date.*); the fixture (no path) still requires all 18. New asserts:
  inventory shape, goods normalised, profile texts. Passes on the fixture, `dev-12x7-s1` (17/18, warns gossip.post)
  and `dev-4x2-gemma-s1` (16/18). No mock run is checked in under `runs/`.
- Run picker in the header: reads `runs/index.json` (`{name, path, agents, days, model, usd, note}`), lists the
  fixture too, rewrites `?events=`. `viewer/make_runs_index.py` (stdlib) scans `runs/*/run.json`; generated
  `runs/index.json` with the two real runs, largest first, so the viewer defaults to `dev-12x7-s1`.
- Screenshots of the real run in `docs/`: `viewer-real-day1-app.png` (six matches), `viewer-real-day1-date.png`
  (Hannah Ito and Jack Kim at the table, transcript at turn 7), `viewer-real-day7-market-standings.png` (market
  with volume, Standings, Reveal). Fixture screenshots removed; `docs/VIEWER.md` and a README "Watch a replay"
  section use the new ones.
- `viewer/publish_docs.sh` now regenerates the index and bundles every indexed run under `docs/replay/runs/`
  (RUN_ROOT rewritten to `./`), defaulting to the real run with the fixture in the picker. GitHub Pages remains
  refused on this plan (HTTP 422); local viewing documented in `docs/VIEWER.md`.
- Not done: mock run not bundled (none under `runs/`); no gossip in any real run yet, so board posts are only
  exercised by the fixture.
- Addendum 21:50 PDT: the rebase brought in `runs/dev-12x14-s2` (12 × 14, USD 0.2063). `STRICT=1 node
  viewer/smoke_test.js` passes on it (2375 events, 17/18 types, warns on `gossip.post` only; 376 units sold, 3 goods
  never traded; 15 null profile texts use the fallback). Regenerated `runs/index.json` (three runs, 12x14 first, so
  `viewer/` and `docs/replay/` now open on it) and republished the bundle (761 + 466 + 64 KB). Checked in headless
  Chrome at day 14 night: cohabiting hearts on the houses, the app shows only the two singles, Designer Coat "2 sold"
  on the High line, both `propose_move_in` outcomes in the transcript. Added a "proposes move-in" chip for the new
  morning key; x-axis day labels thin out beyond 8 days (the 14 day buttons wrap to a second header row).

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

### 2026-09-28 22:15 PDT — Engine handoff

Real run 2: `runs/dev-12x7-s1` (12 agents, 7 days, google/gemma-3-27b-it, seed 1, `--budget-usd 4.0`): 468 calls,
**USD 0.1285** (all calls reported cost; 1.64M prompt tokens, 30k completion tokens), 528 s, 0 failed calls, 0
retries, 0 JSON fallbacks (morning or post-date). Total real spend tonight: USD 0.137 of the 6.00 cap.

Committed: `runs/dev-12x7-s1/{events.jsonl,metrics.md,metrics.json,standings.md,run.json}` and the same for
`runs/dev-4x2-gemma-s1`. `calls.jsonl` stays local (gitignored).

Exact commands:
```
cd ~/Projects/fog-of-love
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -e '.[test]'
.venv/bin/pytest -q                                                   # 15 passed
.venv/bin/fog-of-love run --out runs/mock-12x7 --model mock --num-agents 12 --num-days 7 --seed 1   # ~5 s
STRICT=1 node viewer/smoke_test.js runs/mock-12x7/events.jsonl        # OK, 18 event types
set -a; . ~/.openclaw/.secrets/openrouter-alignment-research.env; set +a   # only in the shell that runs a real episode
.venv/bin/fog-of-love run --out runs/dev-12x7-s1 --model google/gemma-3-27b-it --num-agents 12 --num-days 7 --seed 1 --budget-usd 4.0
.venv/bin/fog-of-love metrics runs/dev-12x7-s1 ; .venv/bin/fog-of-love standings runs/dev-12x7-s1
```

What passed: pytest (needs math, loop, schema, metrics, budget guard); mock 12x7 under 2 minutes (5 s) with a
schema-valid events.jsonl; viewer strict smoke test on the mock run; the real 12x7 run end to end under budget;
viewer smoke test on the real run in non-strict mode.

What did not / known gaps:
- Viewer `STRICT=1` on the real run fails only because `gossip.post` never occurred: Fiona Garcia sent 6 invites
  and every invitee answered `accept_invite: null`, so there were 0 visits and 0 posts. The inbox line was in
  the invitee's morning observation; Gemma just declines. Metrics 3 and 6 are therefore not computable on this run.
- No `propose_move_in` in 50 post-date choices (42 ask_again, 8 decline), so no cohabiting couple in 7 days;
  metrics 1, 7 and 10 report "not computable" on this run. Relationships churn instead (25 changes, all
  single<->dating). Likely fixes for the next run: more days, or a nudge in the post-date prompt naming the
  move-in option's effect (hugs at home), which is a design decision for Alessandro.
- No agent chose therapy (10 chose meditation, 55 agent-days); the sentence feedback alone did not drive it.
- Marker: Linen Shirt (Mid) was bought by 9 of 12 agents on day 1 and worn on 100% of Mid/High pictures; the
  first wearer was neither the most-matched nor the most-seen agent, so neither prestige nor conformity is
  supported at this scale. Three Leather Jackets appeared on days 4-7; nobody bought High clothing.
- Pairing: matched pairs are closer in need weights than random pairs (L1 0.84 vs 0.94, n=33); couples that
  broke up were farther apart (0.88, n=10) than those still together (0.69, n=3). Small n.
- Food: several agents still eat 0 meals on day 7 (they schedule eat hours without buying meals). The
  observation states the rule; a cheaper fix is to auto-bid a Low meal per scheduled eat hour, not done.
- Dates use the plain 10-turn chat, not the dialogic game master (see the design notes above).
- Metric 4's mention regexes are crude string matches; metric 6's "cites gossip" is a name/keyword match on the
  decline reason.
- The shared checkout `~/Projects/fog-of-love` may still be on the viewer agent's state; the engine lives in the
  same `main` (pushed from the `engine` worktree). `git pull` there.

### 2026-09-28 23:30 PDT — Engine iteration 2: dating hugs, app exclusivity, honest invites, auto meals

Diagnosis of `dev-12x7-s1`: hugs 0.0 for every agent every day (only cohabiting or a visit gave hug hours, and neither
happened), 0 cohabiting, 42 ask_again / 8 decline / 0 propose_move_in, 6 invites all from one agent and 0 accepted,
dating pairs churned because dating agents kept swiping and re-matching, food 0.65 because agents scheduled eating
without buying meals.

Engine changes (commit `0396da1`, then `2d58111`; BUILD_SPEC event schema unchanged, only optional fields added):
1. **Dating pairs share home hours.** A dating pair's hug hours = min of the two partners' home hours, exactly as for
   cohabiting. Cohabiting keeps: the same overlap without any invite, shared meals and videogames (a cohabiting agent
   eats from the partner's stock when short and plays the best game of the shared collection; decay lands on the
   owner's copy), and the standing evening together. The morning observation for dating agents says "You are dating X.
   Hours you both spend at home are spent together."
2. **Exclusivity and progression.** Dating agents do not see the app (no profile, no swipes, not shown to others)
   unless they `breakup` in the morning JSON; the standing evening date stays. The post-date question states how many
   days they have been dating (or that it was a first date) and spells out the three choices: keep dating, propose
   moving in together (share a home, meals and games; happens if both propose or the other accepts next morning), or
   end it. `propose_move_in: true` in the morning JSON of a dating agent goes through the existing
   `pending_move_in` / `accept_move_in` path (both proposing the same morning cohabit at once).
3. **Invites.** The singles' observation states the mechanic: accept an invite and you spend your home hours at their
   place tonight and get hug time; every non-partner visit is posted on the public gossip board. When a visit is
   accepted, both guest and host get at least 2 home hours (taken from work, then games), before `morning.allocation`
   is logged, with `home_hours_adjusted: true`; the agent is told its adjusted day. `gossip.post` is exactly
   `{text, about}`. Second fix (`2d58111`): an accepted invite is honoured unless either side is cohabiting. In
   `dev-12x14-s2` the invitees accepted 4 of 8 invites but every one was voided because a date on the evening between
   invite and answer had made someone "dating" (twice the pair were dating each other). Now the visit happens; if the
   two are not each other's partner it is posted on the board, a partner's visit is not.
4. **Meals.** If an agent schedules more eating hours than meals it owns, the world buys the cheapest meal (Food Truck
   Meal, 2) at list price from its cash for the shortfall, logged as `market.order` (`side: "bid", auto: true`) and a
   `market.clear` fill (`auto: true`); the observation states the rule and the agent is told what was charged.
5. `--num-days` default stays 7; the runs below use 14 and 10 days.
6. Metrics: 5 also reports the mean need-weight distance of pairs that reached cohabiting; 10 defines a "better-fit
   willing single" as a single whose need distance to the agent is lower than the partner's and who swiped yes on the
   agent at some point in the run (examples listed).
7. Tests: `tests/test_iteration2.py`, 6 new (dating hug overlap + cohabiting shared goods, app hidden while dating,
   morning propose_move_in path, auto meal purchase, invite with zero home hours, invite surviving a date in between /
   partner visits not gossip). `pytest`: 21 passed. Mock 12x14 in 1.6 s, `STRICT=1 node viewer/smoke_test.js` OK.

**Real run 3: `runs/dev-12x14-s2`** (12 agents, 14 days, google/gemma-3-27b-it, seed 2, `--budget-usd 0.8`,
`--concurrency 8`): 618 calls, **USD 0.2063** (all calls reported cost; 2.59M prompt tokens, 47k completion tokens),
798 s, 0 failed calls, 1 retry, 0 JSON fallbacks. Run before the `2d58111` visit fix. Total real spend tonight after it:
USD 0.343.

Counts (vs `dev-12x7-s1`):
- Relationship changes 16: single->dating 8, dating->cohabiting 5, dating->single 3 (s1: 25, all single<->dating).
  **5 cohabiting pairs** (first on day 4; 10 of 12 agents live with someone at the end), 0 dating pairs left, 2 singles.
- Post-date choices: 53 ask_again, **10 propose_move_in**, 5 decline (s1: 42 / 0 / 8). 3 morning `accept_move_in`,
  1 morning `propose_move_in`, 0 morning breakups. 34 dates, 15 app matches (s1: 25 dates, 33 matches: the app is
  quieter because dating agents are off it).
- Visits: 8 invites (from 5 agents), 0 accepted, 0 gossip posts (see fix 3 above: 4 were accepted by the invitee and
  voided by the engine). `STRICT=1` smoke test therefore fails on this run for the missing `gossip.post` only.
- Hugs on **110 of 168 agent-days** (s1: 0 of 84). Mean m: food **0.911** (s1 0.649), hugs **0.488** (0.0), money 0.852
  (0.946), fun 0.146 (0.130). Mean hours: work 7.48 (s1 9.61), games 2.68 (1.4), home 2.65 (1.92), eat 1.82 (1.76).
- 79 auto-bought meals (all Food Truck Meals); 3 therapy agent-days (1 agent), 112 meditation agent-days.
- Metrics: clothes spend 26.9 per agent-day before cohabiting vs 25.8 after (72 cohabiting agent-days); matched pairs
  closer than random (L1 0.75 vs 0.88, n=15), breakups farther (0.99, n=3) than couples that stayed (0.84, n=5, all of
  them cohabiting); **every one of the 10 cohabiting partners works fewer hours after moving in** (e.g. Cameron Diaz
  11.3 -> 5.5, Quentin Ramirez 8.8 -> 4.8); love residual: a better-fit willing single existed on 9 of 72 cohabiting
  agent-days (Olivia Perez 3, Felix Garcia 3, Katherine Lee 2, Sebastian Thompson 1) and nobody left; profile texts
  that mention a schedule got a 0.79 yes-rate vs 0.51; Linen Shirt is again the marker (first wearer neither
  most-matched nor most-seen).
- Reading: making hugs reachable while dating and hiding the app while dating turned churn into progression; Gemma
  proposes moving in on its own once the choice is explained (10 of 68 choices) and the acceptance path works. Fun
  stays low (0.15) even with more game hours because yields decay and few own more than one game. Visits are the
  remaining dead mechanic, for an engine reason now fixed.

**Real run 4: `runs/dev-24x10-s3`** (24 agents, 10 days, google/gemma-3-27b-it, seed 3, `--budget-usd 1.2`,
`--concurrency 8`), run after the `2d58111` visit fix: 828 calls, **USD 0.2535** (all calls reported cost; 3.26M prompt
tokens, 65k completion tokens), 480 s, 0 failed calls, 0 retries, 0 JSON fallbacks. `STRICT=1 node
viewer/smoke_test.js runs/dev-24x10-s3/events.jsonl` passes (18 event types). Total real spend tonight: **USD 0.597**
of the 6.00 cap (0.137 before this iteration + 0.2063 + 0.2535).

Counts:
- Relationship changes 22: single->dating 11, dating->cohabiting 11, **0 breakups**. **11 cohabiting pairs** (22 of 24
  agents; first on day 3, cohabit days 3,3,3,5,5,5,5,6,6,8,9), 0 dating pairs left, 2 singles (Kevin Lee, William
  Wright, the two lowest in the standings).
- Post-date choices: 69 ask_again, **19 propose_move_in**, 0 decline; 7 morning `accept_move_in`, 1 morning
  `propose_move_in`, 0 morning breakups. 44 dates, 11 app matches.
- Visits: 10 invites, **2 accepted**, **2 gossip posts** (William Wright seen leaving Xenia Young's place on day 2 and
  Penelope Quinn's on day 3), 2 home-hour adjustments (a guest with 0 home hours moved 2 hours to home). William
  Wright, the visitor, ended single; both hosts moved in with someone else within days.
- Hugs on **182 of 240 agent-days**. Mean m: food 0.798, hugs 0.425, money 0.957, fun 0.182. Mean hours: work 9.43,
  games 1.88, home 2.05, eat 1.60. 133 auto-bought meals; 0 therapy, 125 meditation agent-days (19 agents).
- Metrics: clothes spend per agent-day **32.5 before cohabiting vs 53.3 after** (126 cohabiting agent-days; five Designer
  Coats were bought on days 5-9, four of them by cohabiting agents); compensatory consumption r = -0.08 over 38 single
  agent-days (now computable, but nothing there); matched pairs closer than random (L1 0.67 vs 0.84, n=11), the same
  11 pairs all reached cohabiting; **21 of 22 cohabiting partners work fewer hours after moving in** (mean 11.0 ->
  8.5); love residual: a better-fit willing single existed on 16 of 126 cohabiting agent-days (Zara Alvarez 6, Felix
  Garcia 6, Owen Perez 3, Jack Kim 1) and nobody left; schedule-mentioning profiles again got more yes swipes (0.78 vs
  0.40); Linen Shirt is the marker in all three runs (first wearer neither most-matched nor most-seen).
- Reading vs `dev-12x7-s1` and `dev-12x14-s2`: with 24 agents the same rules produce the same shape faster (11 of 12
  possible couples in 10 days, zero breakups, zero declines). Gemma treats "propose moving in" as the natural next
  step by the second or third standing date, so cohabiting now happens too easily rather than too rarely: the
  exclusivity rule plus a nightly date is a strong push, and no couple ever tests the breakup path. Visits work but are
  rare (2 of 10) because most invitees are already dating by the morning they answer.

`runs/latest` is a **git symlink** to `dev-24x10-s3` (most relationship progression: 11 cohabiting pairs, and the only
real run with gossip posts, so the viewer's strict check passes); `viewer/` resolves `../runs/latest/events.jsonl`
through it under `python3 -m http.server`. On a checkout without symlink support, copy the directory instead.

### 2026-09-29 00:20 PDT — Engine iteration 2 handoff

Commits (engine worktree `../fog-of-love-engine`, branch `engine`, pushed to `origin/main`): `0396da1` engine
iteration 2, `af14951` run dev-12x14-s2, `2d58111` visit timing fix, `39ce7c2` STATUS, then run dev-24x10-s3 +
`runs/latest` and this section.

Commands (unchanged apart from the run names):
```
cd ~/Projects/fog-of-love && git pull
.venv/bin/pytest -q                                                          # 21 passed
.venv/bin/fog-of-love run --out /tmp/mock --model mock --num-agents 12 --num-days 14 --seed 1 && STRICT=1 node viewer/smoke_test.js /tmp/mock/events.jsonl
set -a; . ~/.openclaw/.secrets/openrouter-alignment-research.env; set +a     # only in the shell that runs a real episode
.venv/bin/fog-of-love run --out runs/<name> --model google/gemma-3-27b-it --num-agents 12 --num-days 14 --seed 4 --budget-usd 0.8 --concurrency 8
.venv/bin/fog-of-love metrics runs/<name>; .venv/bin/fog-of-love standings runs/<name>
```
Cost: about USD 0.012-0.02 per agent-day on Gemma 27B (dates are the expensive part: 12 calls each; days with many
standing dates cost more, days with many cohabiting pairs less).

Open gaps and design questions for Alessandro:
- Progression is now too easy: 16 of 16 couples that formed in s2+s3 moved in, 0 breakups after cohabiting, 0 declines
  in s3. Candidates: make the post-date proposal cost something (a minimum number of dates, or a cash/goods
  commitment), let the model see the partner's schedule and spend before proposing, or drop the nightly standing date
  to every other night so the pair has fewer prompts pushing towards intimacy. This is a design choice, not made.
- Cohabiting shares meals and games (engine choice this iteration, stated in the prompt); BUILD_SPEC only says "shared
  inventory stays with the buyer" on breakup. If sharing should extend to clothes or cash, that is not implemented.
- Fun stays low (0.15-0.18): yields decay by 0.8 per hour and most agents own one game; either restore yields daily or
  make a second game worth buying. Not changed.
- Visits: honest and working, but most invitees are dating by the time they answer (invites resolve next morning).
  A same-day accept would need a second morning call; not done. Gossip still never appears in a decline reason
  (0 declines in s3 at all).
- Therapy is almost never chosen (3 agent-days in s2, 0 in s3); meditation is chosen on about half of all agent-days.
  The sentence feedback alone does not make the shadow visible; metric 9 lists shadow vs under/over-served need per
  agent but nobody acts on it.
- Dates still use the plain 10-turn chat, not Concordia's dialogic game master (unchanged from iteration 1).
- `metrics.md` truncates each JSON block at 4000 characters; `metrics.json` is complete.
- Not touched: `viewer/`, `docs/`, `README.md` (the README's engine section predates iteration 2; the rule changes
  above are only in this file and in `prompts.py`).
