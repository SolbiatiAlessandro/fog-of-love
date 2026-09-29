"""`fog-of-love run|metrics|standings`."""

from __future__ import annotations

import argparse
import os
import sys


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="fog-of-love", description="Fog of Love: a needs-based dating world in Love Town.")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run an episode")
    r.add_argument("--out", required=True)
    r.add_argument("--model", default="mock", help="OpenRouter slug or 'mock'")
    r.add_argument("--num-agents", type=int, default=12)
    r.add_argument("--num-days", type=int, default=7)
    r.add_argument("--seed", type=int, default=1)
    r.add_argument("--budget-usd", type=float, default=None)
    r.add_argument("--concurrency", type=int, default=8)
    m = sub.add_parser("metrics", help="write metrics.md and metrics.json for a run")
    m.add_argument("run_dir")
    s = sub.add_parser("standings", help="author-level ranking on sum U")
    s.add_argument("run_dir")
    args = p.parse_args(argv)

    if args.cmd == "run":
        from fog_of_love import metrics, standings
        from fog_of_love.world import World

        api_key = os.environ.get("OPENROUTER_API_KEY", "").strip() or None
        world = World(out_dir=args.out, model_name=args.model, num_agents=args.num_agents, num_days=args.num_days,
                      seed=args.seed, budget_usd=args.budget_usd, api_key=api_key, concurrency=args.concurrency)
        summary = world.run()
        standings.write(args.out)
        metrics.write(args.out)
        print(f"run: {args.out} days={summary['days']} calls={summary['calls']} usd={summary['total_usd']:.4f} "
              f"seconds={summary['seconds']}" + (" ABORTED: " + summary["abort_reason"] if summary.get("aborted") else ""))
        return 0
    if args.cmd == "metrics":
        from fog_of_love import metrics

        metrics.write(args.run_dir)
        print(f"wrote {args.run_dir}/metrics.md and metrics.json")
        return 0
    if args.cmd == "standings":
        from fog_of_love import standings

        rows = standings.write(args.run_dir)
        print(standings.render(rows))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
