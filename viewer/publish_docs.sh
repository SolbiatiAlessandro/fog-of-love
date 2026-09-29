#!/bin/sh
# Copy the viewer, the sample fixture and every run listed in runs/index.json into docs/replay/
# so GitHub Pages (source: /docs on main) or any static host can serve it.
# The copy reads runs/index.json next to itself (RUN_ROOT './' instead of '../') and so defaults
# to the first indexed run, the largest real one; the fixture stays reachable through the picker.
set -e
cd "$(dirname "$0")/.."
python3 viewer/make_runs_index.py
mkdir -p docs/replay/fixtures docs/replay/runs
cp viewer/index.html viewer/viewer.css docs/replay/
sed "s#const RUN_ROOT = '../';#const RUN_ROOT = './';#" viewer/viewer.js > docs/replay/viewer.js
grep -q "const RUN_ROOT = './';" docs/replay/viewer.js || { echo "RUN_ROOT rewrite failed" >&2; exit 1; }
cp viewer/fixtures/sample-events.jsonl docs/replay/fixtures/
rm -rf docs/replay/runs
mkdir -p docs/replay/runs
cp runs/index.json docs/replay/runs/index.json
python3 - <<'PY'
import json, pathlib, shutil
for r in json.load(open("runs/index.json")):
    src = pathlib.Path(r["path"])
    dst = pathlib.Path("docs/replay") / r["path"]
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    print(f"bundled {dst} ({dst.stat().st_size // 1024} KB)")
PY
echo "docs/replay updated"
