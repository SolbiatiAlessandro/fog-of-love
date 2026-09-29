#!/usr/bin/env python3
"""Write runs/index.json for the viewer's run picker from runs/*/run.json. Stdlib only.

    python3 viewer/make_runs_index.py [runs_dir]

Each entry: {name, path, agents, days, model, usd, note}. `path` is relative to the repo
root (the viewer prefixes it with its RUN_ROOT). Sorted largest run first (agents x days,
then name), so the viewer's default (the first entry) is the biggest run. Directories
without both run.json and events.jsonl are skipped.
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def scan(runs_dir: pathlib.Path) -> list:
    entries = []
    for d in sorted(runs_dir.iterdir()):
        run_json, events = d / "run.json", d / "events.jsonl"
        if d.is_symlink() or d.name == "latest" or not (d.is_dir() and run_json.is_file() and events.is_file()):
            continue
        try:
            cfg = json.loads(run_json.read_text())
        except json.JSONDecodeError as e:
            print(f"skip {d.name}: {e}", file=sys.stderr)
            continue
        llm = cfg.get("llm") or {}
        bits = []
        if cfg.get("seed") is not None:
            bits.append(f"seed {cfg['seed']}")
        if cfg.get("calls"):
            bits.append(f"{cfg['calls']} calls")
        if cfg.get("seconds"):
            bits.append(f"{float(cfg['seconds']):.0f} s")
        if llm.get("failed_calls"):
            bits.append(f"{llm['failed_calls']} failed calls")
        if cfg.get("aborted"):
            bits.append("aborted")
        try:
            path = events.resolve().relative_to(ROOT).as_posix()
        except ValueError:
            path = str(events)
        entries.append({
            "name": d.name,
            "path": path,
            "agents": cfg.get("num_agents"),
            "days": cfg.get("days", cfg.get("num_days")),
            "model": cfg.get("model"),
            "usd": round(float(cfg.get("total_usd") or 0), 4),
            "note": cfg.get("note") or " · ".join(bits),
        })
    entries.sort(key=lambda e: (-((e["agents"] or 0) * (e["days"] or 0)), e["name"]))
    return entries


def main() -> None:
    runs_dir = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "runs"
    entries = scan(runs_dir)
    out = runs_dir / "index.json"
    out.write_text(json.dumps(entries, indent=2) + "\n")
    print(f"{out}: {len(entries)} runs")
    for e in entries:
        print(f"  {e['name']}: {e['agents']}x{e['days']} {e['model']} USD {e['usd']}")


if __name__ == "__main__":
    main()
