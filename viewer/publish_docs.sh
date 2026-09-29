#!/bin/sh
# Copy the viewer + sample fixture into docs/replay/ so GitHub Pages (source: /docs on main)
# or any static host can serve it. The copy defaults to the bundled fixture instead of ../runs/latest.
set -e
cd "$(dirname "$0")/.."
mkdir -p docs/replay/fixtures
cp viewer/index.html viewer/viewer.css docs/replay/
sed "s#'../runs/latest/events.jsonl'#'fixtures/sample-events.jsonl'#" viewer/viewer.js > docs/replay/viewer.js
cp viewer/fixtures/sample-events.jsonl docs/replay/fixtures/
# bundle the latest real run if one exists
if [ -f runs/latest/events.jsonl ]; then
  mkdir -p docs/replay/runs/latest && cp runs/latest/events.jsonl docs/replay/runs/latest/
fi
echo "docs/replay updated"
