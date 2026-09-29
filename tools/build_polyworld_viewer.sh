#!/usr/bin/env bash
# Build the Love Town Polyworld viewer (Nim + real Polyworld engine) from a converted replay.
#
#   tools/build_polyworld_viewer.sh native  <replay.lovetown.json> [OUTPUT_DIR]   -> build/polyworld-native
#   tools/build_polyworld_viewer.sh web     <replay.lovetown.json> [OUTPUT_DIR]   -> build/polyworld-web
#   tools/build_polyworld_viewer.sh publish [<replay.lovetown.json>]              -> docs/replay3d (GitHub Pages)
#
# Environment (all optional):
#   POLYWORLD_ENGINE   Metta-AI/polyworld checkout      (default: ../concordia-polyworld-engine)
#   POLYWORLD_DEPS     pinned engine dependencies        (default: $POLYWORLD_ENGINE/tmp/coworld/deps)
#   POLYWORLD_EMSDK    Emscripten SDK directory, used when emcc is not on PATH
#   POLYWORLD_SKIP_WASM=1  publish: assemble the HTML layer and replays without compiling the scene
#                      (the page then runs the HUD on its own clock and says the 3D scene is pending)
#
# publish converts every run in runs/index.json into docs/replay3d/replays/, writes
# docs/replay3d/replays/index.json for the run picker, builds the web bundle against the
# default replay (dev-24x10-s4-market, or the argument) and copies it into docs/replay3d/.
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
target="${1:-}"
replay="${2:-}"
default_run="dev-24x10-s4-market"

usage() {
  echo "Usage: $0 native|web REPLAY_JSON [OUTPUT_DIR]" >&2
  echo "       $0 publish [REPLAY_JSON]" >&2
  exit 2
}
[[ "$target" == native || "$target" == web || "$target" == publish ]] || usage

export POLYWORLD_ENGINE="${POLYWORLD_ENGINE:-$(dirname "$repo_dir")/concordia-polyworld-engine}"
export POLYWORLD_DEPS="${POLYWORLD_DEPS:-$POLYWORLD_ENGINE/tmp/coworld/deps}"
viewer_dir="$repo_dir/polyworld_viewer"
html_assets=(replay_ui.js replay_state.js replay_ui.css)

# ------------------------------------------------------------------ replays for publish
convert_all_runs() {
  local replays_dir="$1"
  mkdir -p "$replays_dir"
  python3 - "$repo_dir" "$replays_dir" <<'PY'
import json, pathlib, subprocess, sys
repo, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
index = []
for run in json.loads((repo / "runs" / "index.json").read_text()):
    src = repo / run["path"]
    if not src.is_file():
        print(f"skip {run['name']}: {src} missing", file=sys.stderr)
        continue
    dst = out / f"{run['name']}.lovetown.json"
    subprocess.run([sys.executable, str(repo / "tools" / "export_polyworld_replay.py"), str(src), "--out", str(dst),
                    "--name", run["name"]], check=True)
    doc = json.loads(dst.read_text())
    index.append({"name": run["name"], "path": f"replays/{dst.name}", "agents": doc["run"]["agent_count"],
                  "days": doc["run"]["days"], "model": run.get("model"), "usd": run.get("usd"), "note": run.get("note")})
(out / "index.json").write_text(json.dumps(index, indent=2) + "\n")
print(f"{out / 'index.json'}: {len(index)} runs")
PY
}

if [[ "$target" == publish ]]; then
  output="$repo_dir/docs/replay3d"
  convert_all_runs "$output/replays"
  replay="${replay:-$output/replays/$default_run.lovetown.json}"
  [[ -f "$replay" ]] || { echo "Default replay missing: $replay" >&2; exit 2; }
  if [[ "${POLYWORLD_SKIP_WASM:-0}" == 1 ]]; then
    echo "POLYWORLD_SKIP_WASM=1: assembling the HTML layer only (no 3D scene)." >&2
    for asset in "${html_assets[@]}"; do cp "$viewer_dir/$asset" "$output/$asset"; done
    # The Emscripten shell placeholder becomes a marker so the page knows the scene is missing.
    sed 's#{{{ SCRIPT }}}#<script>window.LOVETOWN_NO_SCENE = true;</script>#' "$viewer_dir/web_shell.html" > "$output/index.html"
    rm -f "$output/main.js" "$output/main.wasm" "$output/main.data"
    cp "$replay" "$output/replay.json"
    echo "Published HTML-only bundle: $output/index.html"
    exit 0
  fi
  "$0" web "$replay" "$repo_dir/build/polyworld-web"
  for file in index.html main.js main.wasm main.data replay.json polyworld-commit.txt "${html_assets[@]}"; do
    cp "$repo_dir/build/polyworld-web/$file" "$output/$file"
  done
  echo "Published: $output (serve docs/ and open /replay3d/)"
  exit 0
fi

[[ -n "$replay" ]] || usage
[[ -f "$replay" ]] || { echo "Replay not found: $replay" >&2; exit 2; }
replay="$(cd "$(dirname "$replay")" && pwd)/$(basename "$replay")"
output="${3:-$repo_dir/build/polyworld-$target}"
mkdir -p "$output"
output="$(cd "$output" && pwd)"

if [[ ! -f "$POLYWORLD_ENGINE/src/polyworld/shapes.nim" ]]; then
  echo "Set POLYWORLD_ENGINE to a Metta-AI/polyworld checkout (looked in $POLYWORLD_ENGINE)." >&2
  exit 2
fi
if [[ ! -d "$POLYWORLD_DEPS/silky" ]]; then
  echo "Pinned engine dependencies are missing under $POLYWORLD_DEPS. From POLYWORLD_ENGINE run:" >&2
  echo "  nim r coworld/tools/sync_dependencies.nim" >&2
  exit 2
fi
if [[ ! -f "$viewer_dir/main.nim" ]]; then
  echo "polyworld_viewer/main.nim is not present yet (the scene agent owns it)." >&2
  exit 2
fi
python3 - "$replay" <<'PY'
import json, sys
doc = json.load(open(sys.argv[1]))
assert doc.get("schema") == "love-town-replay/1", f"not a love-town-replay/1 file: {doc.get('schema')!r}"
PY

# Both names are exported: the scene's config.nims was copied from the previous viewer.
export CONCORDIA_POLYWORLD_REPLAY="$replay"
export LOVETOWN_REPLAY="$replay"

if [[ "$target" == web ]]; then
  if ! command -v emcc >/dev/null 2>&1; then
    emsdk_dir="${POLYWORLD_EMSDK:-${EMSDK:-}}"
    if [[ -z "$emsdk_dir" || ! -x "$emsdk_dir/upstream/emscripten/emcc" ]]; then
      echo "Put emcc on PATH or set POLYWORLD_EMSDK to an installed Emscripten SDK." >&2
      exit 2
    fi
    export PATH="$emsdk_dir/upstream/emscripten:$PATH"
  fi
  generated="$output/emscripten"
  export CONCORDIA_POLYWORLD_OUTPUT="$generated"
  export LOVETOWN_OUTPUT="$generated"
  mkdir -p "$generated"
  nim c --hints:off -d:emscripten "$viewer_dir/main.nim"
  for suffix in html js wasm data; do
    if [[ ! -f "$generated/main.$suffix" ]]; then
      echo "Expected browser artifact missing: $generated/main.$suffix" >&2
      exit 1
    fi
  done
  cp "$generated/main.html" "$output/index.html"
  cp "$generated/main.js" "$generated/main.wasm" "$generated/main.data" "$output/"
  for asset in "${html_assets[@]}"; do cp "$viewer_dir/$asset" "$output/$asset"; done
  if [[ -d "$repo_dir/docs/replay3d/replays" ]]; then
    rm -rf "$output/replays"
    cp -R "$repo_dir/docs/replay3d/replays" "$output/replays"
  fi
else
  nim c --hints:off --nimcache:"$output/nimcache" -o:"$output/lovetown-polyworld" "$viewer_dir/main.nim"
fi
[[ "$replay" == "$output/replay.json" ]] || cp "$replay" "$output/replay.json"
git -C "$POLYWORLD_ENGINE" rev-parse HEAD > "$output/polyworld-commit.txt"
if [[ "$target" == native ]]; then
  echo "Built: $output/lovetown-polyworld"
  echo "Run:   $output/lovetown-polyworld $output/replay.json --play"
else
  echo "Built: $output/index.html"
  echo "Serve: python3 -m http.server 8767 --bind 127.0.0.1 --directory $output"
fi
