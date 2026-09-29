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
