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

Watch a run: `python3 -m http.server` in the repo root, then open
`http://localhost:8000/viewer/?events=../runs/dev-12x7-s1/events.jsonl`.

Layout: `src/fog_of_love/{needs,world,agents,market,app,dates,gossip,events,metrics,standings,llm,prompts,goods,cli}.py`,
`vendor/personas.py` (the 50 Concordia signaling personas, Apache header kept), `tests/`.
