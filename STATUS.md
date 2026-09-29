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
export OPENROUTER_API_KEY=...   # only in the shell that runs a real episode; keep the key outside the repo
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

### 2026-09-28 21:44 PDT — Engine iteration 2: dating hugs, app exclusivity, honest invites, auto meals

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
real run with gossip posts, so the viewer's strict check passes). The viewer (since `e24070f`) defaults to the first
entry of `runs/index.json` (largest run) and falls back to `runs/latest/events.jsonl`; `runs/index.json` was regenerated
with `python3 viewer/make_runs_index.py runs` so `dev-24x10-s3` is first (checked: the scanner does not add a
duplicate entry for the `latest` symlink). On a checkout without symlink support, copy the directory instead.

### 2026-09-28 21:52 PDT — Engine iteration 2 handoff

Commits (engine worktree `../fog-of-love-engine`, branch `engine`, pushed to `origin/main`): `0396da1` engine
iteration 2, `af14951` run dev-12x14-s2, `2d58111` visit timing fix, `39ce7c2` STATUS, `c55f8f4` run dev-24x10-s3 +
`runs/latest` and this section.

Commands (unchanged apart from the run names):
```
cd ~/Projects/fog-of-love && git pull
.venv/bin/pytest -q                                                          # 21 passed
.venv/bin/fog-of-love run --out /tmp/mock --model mock --num-agents 12 --num-days 14 --seed 1 && STRICT=1 node viewer/smoke_test.js /tmp/mock/events.jsonl
export OPENROUTER_API_KEY=...   # only in the shell that runs a real episode; keep the key outside the repo
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

### 2026-09-28 22:08 PDT — Engine iteration 3: market

Problem: every clearing price in every real run equalled the list price (sellers asked list = cost with fresh stock of
100 each day; buyers bid at the ask; midpoint clearing), so the market chart was flat and the Veblen / cost-selects-the-
status-good questions could not be asked.

Engine changes (commit `a00684d`; events.jsonl schema unchanged, optional fields only):
1. **Finite stock.** Daily production per good: clothing Low 20 / Mid 6 / High 2, games 8, meals Low 40 / Mid 12 / High 3
   (`goods.PRODUCTION`). Unsold units carry over up to 3x production (`goods.stock_cap`); nothing vanishes. Day 1 opens
   with one day's production. Auto-bought meals (the restaurant's guarantee) stay outside the stock and at list price.
2. **Adaptive scripted sellers.** Ask starts at list; after each day: sold out -> +15%; fewer than a third of the day's
   stock sold -> -10%, floored at production cost = 0.6 x list; rounded to cents (`market.adjust_ask`). The ask is logged
   every round as the `market.order` side `ask` (its `qty` is the remaining stock, `stock` the day's opening stock); the
   day's last `market.prices` event carries `asks`, `stock`, `day_stock`, `sold`, `next_asks`; `market.clear` carries
   `ask` and `remaining`.
3. **Clearing** is still Concordia's `_clear_auction` (highest bids first against the ask, midpoint prices, respecting
   the seller's inventory); unfilled bids rebid at 1.15x for the remaining rounds. Fix: Concordia returns a bid/ask
   midpoint as the "price" even when the shelf is empty and nothing traded; a round without fills now reports the ask.
4. **Morning observation** lists, per good, last round's clearing price, the seller's asking price and the units on
   offer, and that the highest bids are served first. No advice. The list-price line is gone.
5. **Metrics 11. Price dynamics**: per good min/max/last clearing price (rounds with trades, auto meals excluded), ask
   range, units sold, units bid per day; elasticity for Mid/High clothing per good and pooled per tier: OLS slope of
   log(units bid at round 0) on log(that day's ask) over days with at least one bid, "not estimable" under 5 such days.
6. Tests: `tests/test_iteration3.py`, 6 new (ask up/down/floor, replenish and cap, stock depletion with highest bidder
   served and rebids against an empty shelf, clearing at the midpoint and the ask when nothing trades, elasticity on a
   fixture, metric 11 on a synthetic run). `pytest`: 27 passed. Mock 24x10 in 2.5 s, `STRICT=1 node
   viewer/smoke_test.js` OK (18/18).

**Real run 5: `runs/dev-24x10-s4-market`** (24 agents, 10 days, google/gemma-3-27b-it, seed 4, `--budget-usd 0.9`,
`--concurrency 8`): 922 calls, **USD 0.3354** (all 922 calls reported cost; 4.42M prompt tokens, 71k completion
tokens), 521 s, 0 failed calls, 0 retries, 0 JSON fallbacks. `STRICT=1` smoke test OK (2907 events, 18/18 types).
Total real spend tonight after it: about USD 0.94 of the 1.20 cap.

Price dynamics (clearing prices over rounds with trades; asks from list down to the 0.6x floor unless noted):
- Linen Shirt 54.00-103.50 (23 sold; sold out day 1 at 90 -> ask 103.50, then 1-4 bids a day while the ask fell to
  54.00 by day 9). Leather Jacket 55.01-93.15 (21 sold; 18 bids on day 2 at ask 81 sold out the 12 in stock -> 93.15,
  then down to 54.00). Plain Tee 3.93-6.00 (4 sold); Thrift Hoodie never traded (ask 3.60 at the end).
- **High clothing traded for the first time: 8 units** (7 Designer Coat, 1 Tailored Suit) at 900.00-1093.50, all after
  the ask had fallen below list: day 4 at 1093.50 (Diana Evans), day 5 at 1038.83 / 984.15, day 6 three at 984.15, then
  900.00 (the floor). Buyers: Diana Evans (4 coats, started with 6085 cash), Taylor Thompson, Ulysses Vance, Owen Perez,
  Lily Martin. Nobody bought at 1500.
- Games 18.00-30.00 (Kart Rush 30 sold, 18 of them on day 3 at 24.30; Star Farmer 9; Dungeon Delve 8). Food Truck Meal
  1.20-2.00 (165 sold), Bistro Dinner 11.81-18.00 (114 sold; sold out on 3 days, ask back up to 15.62 at the end),
  Tasting Menu never traded (ask down to 48.00).
- 9 of 12 goods moved off a single price; on day 10 every ask but Bistro Dinner's sat at the cost floor.

Elasticity (log units bid on log ask, by day): Linen Shirt **+0.60** (n=10), Leather Jacket +0.34 (n=5), Mid clothing
pooled +0.70 (n=15); Designer Coat not estimable (n=4), Tailored Suit not estimable (n=1), High clothing pooled +1.01
(n=5). Reading: the positive slopes are not evidence of a Veblen effect. Demand for a durable is front-loaded (14 Linen
Shirt bids on day 1 at 90; then agents own one and stop), and the seller cuts the ask on every slow day, so high price
coincides with the early rush and low price with saturation; the regression conflates time with price. A usable
elasticity needs price variation that is not a monotone function of the day (randomised asks or a cost shock) and a
demand measure net of ownership. The High result is the cost-selects-the-status-good question in the other direction:
the good became a status marker only once the seller's rule brought it under 1100.

Buyers: 253 of 259 round-0 bids were placed exactly at the shown ask (6 above, 0 below), so all price movement comes
from the seller rule; Gemma does not haggle. The 1.15x rebid path fired only against empty shelves.

Social side, as before (the market change did not break progression): 13 single->dating, 10 dating->cohabiting,
2 breakups; 18 of 24 agents cohabiting at the end (10 pairs), 4 dating, 2 single. 51 dates, 20 matches; choices 80
ask_again / 20 propose_move_in / 2 decline. 12 invites, **6 accepted visits, 6 gossip posts**. Mean m: food 0.810, hugs
0.428, money 0.922, fun 0.184. 169 auto-bought meals. Clothes spend per agent-day 50.6 before cohabiting vs 43.4 after
(114 cohabiting agent-days); compensatory r = -0.06 over 46 single agent-days (now computable: singles with visits have
hugs > 0); marker is the Leather Jacket (first worn by Owen Perez on day 2; neither most-matched nor most-seen).

Gaps:
- Auto meals are charged at list (2.00) while the Food Truck ask was 1.20 for most of the run; they also bypass stock.
- The seller rule is one-sided in practice: durables sell out once and then never reach a third of stock, so every ask
  decays to the floor within a week. A slower decay (or a threshold on units rather than a stock fraction) would keep
  prices off the floor long enough to measure anything.
- Elasticity as specified (quantity bid vs ask across days) is confounded by ownership; see above.
- `runs/latest` still points at `dev-24x10-s3`; `runs/index.json` regenerated with `dev-24x10-s4-market` second.

## 2026-09-29 morning summary

**Deliverable.** Private repo `SolbiatiAlessandro/fog-of-love`: the `fog_of_love` engine (needs utility with hidden Dirichlet weights, per-agent bias as the shadow and daily jitter; 16-hour day; Concordia entities and clearing-house market; dating app; dates; cohabitation and breakups; visits and a public gossip board; auto meals; adaptive sellers with finite stock), 27 tests, a mock model that certifies the whole loop in seconds, eleven metrics, author-level standings, and a self-contained replay viewer (`viewer/`, `docs/replay/`) with a run picker. GitHub Pages is live since the repo went public on 2026-09-28 evening: https://solbiatialessandro.github.io/fog-of-love/replay/ (local viewing still works with `python3 -m http.server 8000`).

**Runs.** Four real runs on Gemma 3 27B, USD 0.94 total (cap was 6.00): see the README results table. `runs/latest` -> `dev-24x10-s4-market`; `runs/index.json` lists the four real runs plus the tiny 4x2 check.

**Iterations.** 1: engine and viewer. 2: dating pairs share home hours, app hidden while dating, explicit progression choices, honest invites, auto meals (cohabitation and visits appeared). 3: finite stock and adaptive sellers (prices moved, High clothing traded).

**Open for Alessandro.** Progression difficulty (every couple moves in; no post-cohabiting breakups); bids do not haggle (all price movement is the seller rule) so elasticity is not yet interpretable; fun yield decay too harsh; therapy rarely chosen; dates as plain chat rather than the dialogic game master; gender-blind personas with gendered text; the name "Fog of Love" collides with a published board game if this ever goes public.

## Polyworld viewer

### Bridge

- 2026-09-29: `docs/POLYWORLD_REPLAY.md` written first: schema `love-town-replay/1` (agents with `agent-NNN` ids, goods, per-day allocations / market rounds / app / visits / dates / gossip / relationship changes / night states with a `hidden` key, standings), the 60 s-per-day presentation clock with phase windows, and the `Module.lovetownCommand` (string queue) / `Module.lovetownState` (object written per frame, polled by the HTML) bridge. Exporter, tests, build script and HTML layer follow.
- 2026-09-29 00:20: exporter `tools/export_polyworld_replay.py` + `tests/test_polyworld_export.py` (9 tests pass); five runs converted under `docs/replay3d/replays/` with `index.json`. HTML layer written (`web_shell.html`, `replay_state.js` projection with the reveal rule, `replay_ui.js` HUD + bridge, `replay_ui.css`); `tools/build_polyworld_viewer.sh native|web|publish` (publish with `POLYWORLD_SKIP_WASM=1` assembles the HUD-only page). Headless check `tools/polyworld_viewer_smoke.js --stub` (puppeteer-core + installed Chrome, `stub_scene.js` fakes the Nim side): replay loads, 24 cards, 24 positioned labels, 2 speech bubbles during a date, commands drained, no console errors. Published the HUD-only bundle to `docs/replay3d/` so `/replay3d/` is live before the wasm lands; the page says the 3D scene is pending. Waiting on `polyworld_viewer/main.nim` (scene agent has `replay_model.nim`, `town.nim`).
- 2026-09-29 00:30: web pipeline validated end to end with the previous viewer's `main.nim`/`replay_model.nim` copied to a temp dir (`POLYWORLD_VIEWER_DIR` override): `tools/build_polyworld_viewer.sh web` compiled with emcc 4.0.15 in 8.7 s and assembled `index.html`, `main.js`, `main.wasm` (0.8 MB), `main.data`, HUD assets and `replays/`. The published HUD-only bundle passes `tools/polyworld_viewer_smoke.js --dir docs/replay3d` (no-scene mode: transcript column, 2 live dates). Remaining: rebuild and republish once `polyworld_viewer/main.nim` lands; native screenshots are the scene agent's.
- 2026-09-29 00:45: read the scene agent's `main.nim` bridge: it calls `Module.lovetownState(obj)` as a callback (as `concordiaState` did) and `Module.lovetownReady(info)`; the HUD now defines `lovetownState` as a store-and-return function so both the callback and a plain assignment work (doc updated). Stub smoke still passes. Their `main.nim` does not compile yet (`floatField` overload mismatch in `replay_model.nim`, mid-edit); a retry loop rebuilds every 2 minutes and I publish as soon as it links. GitHub Pages already serves the HUD-only page at https://solbiatialessandro.github.io/fog-of-love/replay3d/ (verified live with the smoke test's `--url` mode).
- 2026-09-29 01:00 (for the scene agent): `polyworld_viewer/main.nim` builds for the web with `tools/build_polyworld_viewer.sh web` (1.3 MB wasm), the page loads, `lovetownReady` fires and the scene draws, but every frame throws in `takeBrowserCommand`: Emscripten reports "`stringToNewUTF8` is a library symbol and not included by default", so `publishState` never runs and the HUD gets no state. Fix in `polyworld_viewer/config.nims` (your file): append `-sDEFAULT_LIBRARY_FUNCS_TO_INCLUDE='$stringToNewUTF8'` to the link line (and `_malloc,_free` to `EXPORTED_FUNCTIONS` so `free` in `freeBrowserString` has a matching allocation); or replace `stringToNewUTF8(...)` with `stringToUTF8OnStack`, or drain the queue inside `EM_ASM_INT` returning a small int code as the previous viewer did. I will rebuild and publish as soon as `config.nims` changes. Everything else in your bridge matches the HUD (`Module.lovetownState(obj)` callback, `agents[].sx/sy/visible`, `dates[]`, `effects[]`, `anchors`).
- 2026-09-29 01:30: **3D bundle published** to `docs/replay3d/` (wasm scene + HUD) and pushed; verified in headless Chrome (puppeteer-core, SwiftShader): the scene renders the town and a dressed character, `lovetownReady` fires, `Module.lovetownState` is consumed each frame, labels anchor at `agents[].sx/sy`, commands reach the scene. Workaround for the `stringToNewUTF8` link error: the HUD now calls the exported `_lovetownCommand` via `Module.ccall` and never fills the `Module.lovetownCommand` array when the export exists, so the broken drain is never entered; the `config.nims` fix above is still worth making. Contract change to match the scene's clock: phases are now morning 0–3, market 3–18, app 18–29, date 29–51, visit 51–55, night 55–60 (`docs/POLYWORLD_REPLAY.md`, exporter, `replay_state.js`); the scene's `DayEnd = 26` may become 18 so its "day"/"app" split matches the HUD's market/app split. The HUD caption shows the scene's own phase name when the bridge is up. Note: the published wasm was built from the scene agent's uncommitted `main.nim`/`town.nim`/`replay_model.nim`/`config.nims` at 01:15; republish (`tools/build_polyworld_viewer.sh publish`) after they commit.
- 2026-09-29 01:45: live check of https://solbiatialessandro.github.io/fog-of-love/replay3d/ (smoke `--url`): wasm served, scene ready, bridge state consumed, HUD rendered. Bridge work complete; open: scene agent to commit their Nim and fix `config.nims` link flags (then `tools/build_polyworld_viewer.sh publish` again), and to check that the character's garment follows `wearing` (the HUD said Linen Shirt while the scene still drew the hoodie at day 1, 43 s).

### Scene

- 2026-09-29 00:05 PDT: Track A stopped before any download. The Quaternius pack page card says "License CC0" but its
  License link (https://quaternius.com/license.html) is now the "Quaternius Asset License (QAL) v1.0, last updated
  8/28/2026", whose section 3(a) forbids redistributing the assets themselves (a public repo with `docs/` on Pages would);
  the download is a Google Drive folder. Details, URLs and access date in `docs/ASSETS.md`. Track B instead: procedural
  garments in `polyworld_viewer/town.nim` (ShapeRenderer boxes, prisms, wedges) with one silhouette and palette per
  clothing good: Plain Tee (mint tee, short sleeves, jeans), Thrift Hoodie (baggy, hood, kangaroo pocket, drawstrings),
  Linen Shirt (cream, collar wedges, placket and buttons, rolled sleeves, chinos), Leather Jacket (dark wide torso,
  lapels, silver zip and cuffs, white tee in the V), Designer Coat (crimson flared coat to mid-calf, wide collar, gold
  belt, black boots), Tailored Suit (navy jacket and trousers, lighter lapels, white shirt, gold tie, pocket square).
  Six hair styles, eight hair colours, six skin tones vary per agent. No third-party art; `assets/` is empty.
- 2026-09-29 00:40 PDT: `polyworld_viewer/main.nim` + `town.nim` + `replay_model.nim` + `config.nims` committed and building
  natively (`nim c`, 1.1 MB) and for the web with `tools/build_polyworld_viewer.sh web|native` (1.4 MB wasm, 8 s link).
  Reads the exporter's `love-town-replay/1` (agent ids `agent-NNN` or names, `persona_summary`/`cash0`/`wearing0`,
  `visits`, `app.matches`, `dates[].pair`, `relationship_changes`, `night[]` with `hidden.U`) with the shorter draft
  names as fallbacks; `polyworld_viewer/fixtures/lovetown-fixture-4x2.json` (4 agents x 2 days: allocations with
  therapy and meditation, two dates at both tables, an accepted visit, a breakup, wearing changes) is in the exporter's
  shape.
- Town: four short streets north of an avenue with one house per agent (12 to 24 slots, filled from the centre), an
  open-fronted workspace with 24 desks, the restaurant with two patio tables plus an 8-stool bar for solo eaters, the
  therapy office with a 6-seat couch, the meditation garden (gravel circle, 12 cushions, lantern, cherry tree), trees,
  lamps that light at dusk, benches, flower beds, paved paths and a south promenade. Signs are block letters. The toon
  day tint follows the engine's `paletteAtHour` (table copied from `polyworld/toon.nim` so the wasm does not link the
  glTF renderer); sky colour follows the hour; the 16-hour day runs 07:00 to 23:00.
- Staging (60 s per day, deterministic from the events): morning 0-2 s everyone leaves home; 2-27 s activities in
  proportion to the allocated hours (order varies by agent so venues fill through the day; each segment keeps a floor of
  its walk time plus 1.5 s; seats are booked greedily per venue, overflow stands at the entrance): work seated at a desk,
  eating seated alone at the bar or a free table seat, therapy lounging on the couch, meditation cross-legged on a
  cushion, games on the porch with a controller and a glowing window, home hours on the porch with a book; 27-29 s app
  phase at home with a phone, matches get hearts; 29-51 s dates in rounds of two tables (pairs sit facing each other,
  `date.turn` text spread over the round as a speech balloon in 3D plus tiny text natively; the relationship change gets
  a heart or broken heart in the last 3.5 s of the round); 51-55 s accepted `visits` walk the guest to the host's porch;
  55-60 s night at home, cohabiting pairs on one porch. Garments: the validated morning `wear` until 27 s, then the
  recorded night `wearing` (purchases clear at the market), so outfits change at the app phase.
- Camera: three-quarter follow at 7.2 units (6.4 seated, 5.6 on porches with a higher pitch), dates framed from the patio
  side with both diners in profile, scroll to zoom, snap on seek; auto-switch every 30 s of wall time preferring agents
  on a date, then walkers (toggle with A or `auto 0|1`); click an agent to follow; Tab / `follow next`.
- Bridge (web): exported C functions `lovetownCommand(char*)` and `lovetownState() -> char*` (JSON) in
  `EXPORTED_FUNCTIONS`, callable through `Module.ccall`; the scene also drains `Module.lovetownCommand` (strings or
  `{type, value}` objects) each frame and calls `Module.lovetownState(stateObject)` each frame; `Module.lovetownReady({schema,
  agents, days, daySeconds, phases})` once. Commands: `play`, `pause`, `toggle`, `speed 1|2|4|16`, `seek <seconds>`,
  `day <n>`, `follow <agentId|name|next>`, `auto 0|1`. State: `{schema, t, day, days, daySeconds, dayTime, phase, hour,
  phases, playing, speed, auto, followed, followedIndex, width, height, agents: [{id, name, x, y, z, sx, sy, visible,
  wearing, tier, activity, walking, status, partner, partnerNow, followed}], anchors: {tables: [{index, x, y, z, sx, sy,
  visible}], houses: [{slot, agent, ...}], workspace, restaurant, therapy, garden}, dates: [{index, a, b, table, turn,
  turns, speaker, text}], bubble: {agent, text, turn, sx, sy, visible} | null, effects: [{agent, kind}]}` (`sx`/`sy`
  are 0..1 screen fractions). The `stringToNewUTF8` link error is gone: the queue drain now copies through
  `stringToUTF8` into a Nim buffer (`stringToUTF8`, `lengthBytesUTF8` added to `EXPORTED_RUNTIME_METHODS`); no
  `DEFAULT_LIBRARY_FUNCS_TO_INCLUDE` needed. Phase windows now match the HUD's date 29-51 / visit 51-55 / night 55-60;
  the scene keeps its own "day" 2-27 / "app" 27-29 split and publishes `phases` in state and in the ready payload.
- Verified: native screenshots from `docs/replay3d/replays/dev-24x10-s4-market.lovetown.json` in `docs/`:
  `polyworld-date.png` (day 10, Diana Evans in the Tailored Suit and Owen Perez in the Designer Coat at table 1,
  balloon and transcript line), `polyworld-street.png` (day 10 morning, Taylor Thompson in the Designer Coat with
  Felix Garcia in the Leather Jacket and two more coats on the street), `polyworld-workspace.png` (day 2, seated
  workers in linen shirts and hoodies), `polyworld-garden.png` (Zara Alvarez cross-legged on a cushion). Web: the
  wasm from `tools/build_polyworld_viewer.sh web` runs in headless Chrome (SwiftShader) with a minimal shell: renders
  the fixture date, `lovetownReady` fires, queued and `ccall` commands (`speed 4`, `{type:'seek', t:40}`, `follow`,
  `play`, `pause`, `auto 0`) take effect, state polls return the fields above, no console errors. The "hoodie at day 1,
  43 s" the bridge saw came from the loader reading `nights` while the exporter writes `night`; fixed, the scene now
  draws the night `wearing` from 27 s.
- Open: `tools/build_polyworld_viewer.sh publish` should be rerun by the bridge to republish the fixed scene; no run
  in `runs/` allocates therapy, so the couch is only exercised by the fixture; dates shorter than ~5 s (six dates in a
  day) show only a few turns at 1x.
