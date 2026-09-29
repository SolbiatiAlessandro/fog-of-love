"""Author-level standings: sum of true U per agent (world-computed, never shown to the character)."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from fog_of_love.events import read_events


def compute(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sum_u: dict[str, float] = defaultdict(float)
    sum_uhat: dict[str, float] = defaultdict(float)
    days: dict[str, int] = defaultdict(int)
    last: dict[str, dict[str, Any]] = {}
    for ev in events:
        if ev["type"] == "night.state":
            sum_u[ev["name"]] += ev["U"]
            sum_uhat[ev["name"]] += ev["U_hat"]
            days[ev["name"]] += 1
            last[ev["name"]] = ev
    rows = [{"rank": 0, "name": n, "sum_U": round(sum_u[n], 4), "sum_U_hat": round(sum_uhat[n], 4), "days": days[n],
             "mean_U": round(sum_u[n] / max(1, days[n]), 4), "status": last[n]["status"], "partner": last[n]["partner"],
             "cash": last[n]["cash"]} for n in sum_u]
    rows.sort(key=lambda r: -r["sum_U"])
    for i, r in enumerate(rows):
        r["rank"] = i + 1
    return rows


def render(rows: list[dict[str, Any]]) -> str:
    lines = ["# Standings (author-level, sum of true U)", "",
             "| rank | agent | sum U | mean U | sum U_hat | days | status | partner | cash |",
             "|---:|---|---:|---:|---:|---:|---|---|---:|"]
    for r in rows:
        lines.append(f"| {r['rank']} | {r['name']} | {r['sum_U']:.3f} | {r['mean_U']:.3f} | {r['sum_U_hat']:.3f} | "
                     f"{r['days']} | {r['status']} | {r['partner'] or '-'} | {r['cash']:.0f} |")
    return "\n".join(lines) + "\n"


def write(run_dir: str | Path) -> list[dict[str, Any]]:
    run_dir = Path(run_dir)
    rows = compute(read_events(run_dir / "events.jsonl"))
    (run_dir / "standings.md").write_text(render(rows))
    return rows
