# Fog of Love

> You just arrived in Love Town, you are a young single career professional, just out of college. You are still discovering your needs, and you just want to be happy. But oh boy.. How to be happy? And even more.. What is love?

A needs-based dating world for LLM agents, built on Google DeepMind's Concordia, to study how status signaling and dating conventions emerge in a population. Design: `BUILD_SPEC.md`. Progress: `STATUS.md`.

Work in progress (overnight build started 2026-09-28).

## Engine (`fog_of_love`)

Install (Python 3.12, `uv`):

```
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e '.[test]'
.venv/bin/pytest -q
```

Run an episode. `--model mock` runs the whole loop with deterministic canned answers (12 agents x 7 days in about
five seconds, no network); a real run needs `OPENROUTER_API_KEY` in the environment and a budget:

```
.venv/bin/fog-of-love run --out runs/mock-12x7 --model mock --num-agents 12 --num-days 7 --seed 1
.venv/bin/fog-of-love run --out runs/dev-12x7-s1 --model google/gemma-3-27b-it --num-agents 12 --num-days 7 --seed 1 --budget-usd 4
.venv/bin/fog-of-love metrics runs/dev-12x7-s1     # metrics.md + metrics.json (the ten questions)
.venv/bin/fog-of-love standings runs/dev-12x7-s1   # author-level ranking on the sum of true U
```

A run directory holds `events.jsonl` (the viewer reads this), `run.json` (config, calls, cost), `standings.md`,
`metrics.md`, `metrics.json`, and for real runs `calls.jsonl` (per-call usage and text; gitignored).

## Results so far (overnight build, 2026-09-28/29)

All runs on `google/gemma-3-27b-it` via OpenRouter. Total spend USD 0.94. Full readings in `STATUS.md`; per-run `metrics.md` and `standings.md` under `runs/`.

| run | agents x days | USD | what it showed |
| --- | --- | --- | --- |
| `dev-12x7-s1` | 12 x 7 | 0.13 | hugs zero for everyone, no cohabiting, dating pairs churned through the app |
| `dev-12x14-s2` | 12 x 14 | 0.21 | after fixes: 5 cohabiting pairs, hugs on 110/168 agent-days, every cohabiting partner works less |
| `dev-24x10-s3` | 24 x 10 | 0.25 | 11 cohabiting pairs, first home visits and gossip posts, clothes spend up after cohabiting |
| `dev-24x10-s4-market` | 24 x 10 | 0.34 | finite stock and adaptive sellers: 9 of 12 goods move off list price, first High clothing trades (8 units, 900 to 1093.50) |

Consistent across runs: matched pairs are closer in hidden need weights than random pairs, and breakups are farther apart than couples that stay; one Mid item (Linen Shirt, then Leather Jacket) becomes the near-universal app picture within two days, and neither the most-matched nor the most-seen agent wore it first; the "love residual" (staying with a partner when a better-fit willing single exists) is small and non-zero and nobody left. Not yet evidence of a Veblen effect: bids sit at the shown ask, so all price movement comes from the seller rule, and price and time are confounded. Known knobs: progression is too easy (every dating couple moves in), fun stays low, therapy is rarely chosen, dates are a plain 10-turn chat.

## Watch a replay

**Live (3D, primary):** https://solbiatialessandro.github.io/fog-of-love/replay3d/ — Love Town rendered with the
Polyworld engine in WebAssembly: houses along streets, the workspace, the restaurant with two tables, the therapy
office and the meditation garden, dressed agents whose garment changes with what they wear, a camera that follows
one agent and switches every 30 s (toggle, or click an agent), speech bubbles over the date tables, and the HUD:
dating app (profile cards, swipes, matches, tonight's dates), the followed agent's card with the live date
transcript, the market chart with volume, the gossip board, and a Reveal toggle for the hidden weights, U vs Û and
standings. Pick a run in the header (default `dev-24x10-s4-market`); `?run=<name>`, `day`, `t`, `speed`,
`follow=<agent id>`, `reveal=1`, `play=0`, `auto=0` work in the URL. Build, convert and verify:
`docs/POLYWORLD_BUILD.md`; data contract: `docs/POLYWORLD_REPLAY.md`.

**Fallback (2D):** https://solbiatialessandro.github.io/fog-of-love/replay/ — the vanilla HTML/JS viewer
(`viewer/`, no build) with the same panels over a 2D town map. Locally, from the repo root:

```
python3 -m http.server 8000
```

then open <http://localhost:8000/viewer/> (picks from `runs/index.json`; regenerate with
`python3 viewer/make_runs_index.py` after a new run) or
<http://localhost:8000/viewer/?events=../runs/dev-12x7-s1/events.jsonl>. Details, screenshots and the smoke test:
`docs/VIEWER.md`; `sh viewer/publish_docs.sh` refreshes `docs/replay/`.

![Day 7 of dev-12x7-s1: market, standings and Reveal](docs/viewer-real-day7-market-standings.png)

Layout: `src/fog_of_love/{needs,world,agents,market,app,dates,gossip,events,metrics,standings,llm,prompts,goods,cli}.py`,
`vendor/personas.py` (the 50 Concordia signaling personas, Apache header kept), `tests/`.
