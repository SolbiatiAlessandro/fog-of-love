#!/usr/bin/env python3
"""Convert a Fog of Love events.jsonl into the `love-town-replay/1` timeline.

    python3 tools/export_polyworld_replay.py runs/<name>/events.jsonl --out out/<name>.lovetown.json

Stdlib only, deterministic (sorted keys, stable ids). The contract is documented in
docs/POLYWORLD_REPLAY.md; keep both in sync. The adapter never invents movement, timing
or outcomes: it only regroups the recorded events per day.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

SCHEMA = "love-town-replay/1"
DAY_SECONDS = 60
PHASES = {
    "morning": [0, 3],
    "market": [3, 18],
    "app": [18, 29],
    "date": [29, 51],
    "visit": [51, 55],
    "night": [55, 60],
}
TABLES = 2
NEEDS = ("food", "hugs", "money", "fun")


class ReplayConversionError(ValueError):
    """The events file cannot be converted faithfully."""


# ----------------------------------------------------------------------------- reading


def read_events(path: Path) -> list[dict]:
    events = []
    with path.open(encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ReplayConversionError(f"{path}:{lineno}: bad JSON ({exc.msg})") from exc
            if not isinstance(ev, dict) or not isinstance(ev.get("type"), str):
                raise ReplayConversionError(f"{path}:{lineno}: not an event object")
            events.append(ev)
    return events


def _num(value, default=None):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else default


def _bool(value) -> bool:
    return bool(value) if value is not None else False


def _str(value):
    return value if isinstance(value, str) and value.strip() else None


def _needs(value):
    if not isinstance(value, dict):
        return None
    return {k: _num(value.get(k)) for k in NEEDS}


# --------------------------------------------------------------------------- converting


class _Converter:
    def __init__(self, events: list[dict], name: str, source_path: str, sha256: str, allow_incomplete: bool):
        self.events = events
        self.name = name
        self.source_path = source_path
        self.sha256 = sha256
        self.allow_incomplete = allow_incomplete
        self.ids: dict[str, str] = {}
        self.goods: dict[str, dict] = {}
        self.agents: list[dict] = []
        self.days: dict[int, dict] = {}
        self.end: dict | None = None
        self.setup: dict | None = None

    # --- helpers
    def agent_id(self, name, t, required=True):
        if name is None:
            if required:
                raise ReplayConversionError(f"t={t}: missing agent name")
            return None
        if name not in self.ids:
            raise ReplayConversionError(f"t={t}: unknown agent {name!r}")
        return self.ids[name]

    def good_id(self, good, t):
        if good not in self.goods:
            raise ReplayConversionError(f"t={t}: unknown good {good!r}")
        return good

    def day(self, ev) -> dict:
        d = ev.get("day")
        if not isinstance(d, int) or d < 1:
            raise ReplayConversionError(f"t={ev.get('t')}: {ev['type']} outside a day (day={d!r})")
        if d not in self.days:
            self.days[d] = {
                "day": d,
                "allocations": [],
                "market": {"rounds": []},
                "app": {"profiles": [], "swipes": [], "matches": []},
                "visits": [],
                "dates": [],
                "gossip": [],
                "relationship_changes": [],
                "night": [],
                # scratch, dropped before output
                "_pending_orders": [],
                "_pending_clears": [],
            }
        return self.days[d]

    # --- per-type handlers
    def setup_world(self, ev):
        if self.setup is not None:
            raise ReplayConversionError("more than one setup.world")
        self.setup = ev
        for good in ev.get("goods") or []:
            gid = good.get("id")
            if not isinstance(gid, str) or gid in self.goods:
                raise ReplayConversionError(f"bad or duplicate good id {gid!r}")
            self.goods[gid] = {
                "id": gid,
                "category": good.get("category"),
                "tier": good.get("tier"),
                "list_price": _num(good.get("list_price")),
            }
        for index, agent in enumerate(ev.get("agents") or []):
            name = agent.get("name")
            if not isinstance(name, str) or not name:
                raise ReplayConversionError(f"agent {index} has no name")
            if name in self.ids:
                raise ReplayConversionError(f"duplicate agent name {name!r}")
            aid = f"agent-{index:03d}"
            self.ids[name] = aid
            self.agents.append({
                "id": aid,
                "name": name,
                "persona_summary": agent.get("persona_summary") or "",
                "cash0": _num(agent.get("cash")),
                "wearing0": _str(agent.get("wearing")),
                "house": index,
                "hidden": None,
            })
        if not self.agents:
            raise ReplayConversionError("setup.world has no agents")

    def setup_needs(self, ev):
        aid = self.agent_id(ev.get("name"), ev.get("t"))
        agent = self.agents[int(aid[6:])]
        agent["hidden"] = {"w": _needs(ev.get("w")), "shadow": ev.get("shadow"), "bias": _needs(ev.get("b"))}

    def allocation(self, ev):
        t = ev.get("t")
        hours = ev.get("hours") if isinstance(ev.get("hours"), dict) else {}
        shopping = []
        for order in ev.get("shopping") or []:
            if not isinstance(order, dict):
                continue
            shopping.append({"good": order.get("good"), "price": _num(order.get("price")), "qty": _num(order.get("qty"), 1)})
        self.day(ev)["allocations"].append({
            "t": t,
            "agent": self.agent_id(ev.get("name"), t),
            "hours": {k: _num(hours.get(k), 0) for k in ("work", "games", "home", "eat")},
            "therapy": _bool(ev.get("therapy")),
            "meditation": _bool(ev.get("meditation")),
            "invite": self.agent_id(ev.get("invite"), t, required=False),
            "accept_invite": self.agent_id(ev.get("accept_invite"), t, required=False),
            "breakup": _bool(ev.get("breakup")),
            "propose_move_in": _bool(ev.get("propose_move_in")),
            "accept_move_in": _bool(ev.get("accept_move_in")),
            "home_hours_adjusted": _bool(ev.get("home_hours_adjusted")),
            "wear": _str(ev.get("wear")),
            "shopping": shopping,
            "profile_text": _str(ev.get("profile_text")),
            "fallback": _bool(ev.get("fallback")),
        })

    def market_order(self, ev):
        t = ev.get("t")
        good = self.good_id(ev.get("good"), t)
        order = {"t": t, "good": good, "price": _num(ev.get("price")), "qty": _num(ev.get("qty"), 1)}
        if ev.get("side") == "ask":
            order["seller"] = good
            order["stock"] = _num(ev.get("stock"))
            order["_side"] = "asks"
        else:
            order["agent"] = self.agent_id(ev.get("name"), t)
            order["auto"] = _bool(ev.get("auto"))
            order["_side"] = "bids"
        order["_round"] = ev.get("round") if isinstance(ev.get("round"), int) else None
        self.day(ev)["_pending_orders"].append(order)

    def market_clear(self, ev):
        t = ev.get("t")
        good = self.good_id(ev.get("good"), t)
        price = _num(ev.get("price"))
        fills = []
        for fill in ev.get("filled") or []:
            if not isinstance(fill, dict):
                continue
            fills.append({
                "buyer": self.agent_id(fill.get("buyer"), t),
                "qty": _num(fill.get("qty"), 1),
                "price": _num(fill.get("price"), price),
            })
        self.day(ev)["_pending_clears"].append({
            "t": t,
            "good": good,
            "price": price,
            "ask": _num(ev.get("ask")),
            "remaining": _num(ev.get("remaining")),
            "volume": sum(f["qty"] or 0 for f in fills),
            "auto": _bool(ev.get("auto")),
            "fills": fills,
            "_round": ev.get("round") if isinstance(ev.get("round"), int) else None,
        })

    def market_prices(self, ev):
        day = self.day(ev)
        rnd = ev.get("round") if isinstance(ev.get("round"), int) else len(day["market"]["rounds"])
        self._flush_round(day, rnd, ev)

    def _flush_round(self, day, rnd, ev=None):
        orders = day["_pending_orders"]
        clears = day["_pending_clears"]
        mine = lambda item: item["_round"] is None or item["_round"] == rnd  # noqa: E731
        asks = [o for o in orders if o["_side"] == "asks" and mine(o)]
        bids = [o for o in orders if o["_side"] == "bids" and mine(o)]
        cl = [c for c in clears if mine(c)]
        day["_pending_orders"] = [o for o in orders if not mine(o)]
        day["_pending_clears"] = [c for c in clears if not mine(c)]
        strip = lambda item: {k: v for k, v in item.items() if not k.startswith("_")}  # noqa: E731
        prices = ev.get("prices") if ev and isinstance(ev.get("prices"), dict) else {}
        for gid in prices:
            self.good_id(gid, ev.get("t") if ev else None)
        day["market"]["rounds"].append({
            "round": rnd,
            "t": ev.get("t") if ev else (cl[-1]["t"] if cl else (bids + asks)[-1]["t"] if (bids or asks) else None),
            "asks": [strip(o) for o in asks],
            "bids": [strip(o) for o in bids],
            "clears": [strip(c) for c in cl],
            "prices": {k: _num(v) for k, v in prices.items()},
            "asks_after": {k: _num(v) for k, v in ev["asks"].items()} if ev and isinstance(ev.get("asks"), dict) else {},
            "stock_after": {k: _num(v) for k, v in ev["stock"].items()} if ev and isinstance(ev.get("stock"), dict) else {},
        })

    def app_profile(self, ev):
        t = ev.get("t")
        pic = ev.get("picture") if isinstance(ev.get("picture"), dict) else {}
        self.day(ev)["app"]["profiles"].append({
            "t": t,
            "agent": self.agent_id(ev.get("name"), t),
            "picture": {"item": _str(pic.get("item")), "tier": _str(pic.get("tier"))},
            "text": _str(ev.get("text")),
        })

    def app_swipe(self, ev):
        t = ev.get("t")
        self.day(ev)["app"]["swipes"].append({
            "t": t,
            "agent": self.agent_id(ev.get("name"), t),
            "target": self.agent_id(ev.get("target"), t),
            "yes": _bool(ev.get("yes")),
        })

    def app_match(self, ev):
        t = ev.get("t")
        self.day(ev)["app"]["matches"].append({"t": t, "a": self.agent_id(ev.get("a"), t), "b": self.agent_id(ev.get("b"), t)})

    def _find_date(self, day, a, b, t, create_scene=""):
        for date in reversed(day["dates"]):
            if set(date["pair"]) == {a, b}:
                return date
        date = {
            "t": t,
            "pair": [a, b],
            "scene": create_scene,
            "table": len(day["dates"]) % TABLES,
            "turns": [],
            "outcomes": [],
            "change": None,
        }
        day["dates"].append(date)
        return date

    def date_scene(self, ev):
        t = ev.get("t")
        day = self.day(ev)
        a, b = self.agent_id(ev.get("a"), t), self.agent_id(ev.get("b"), t)
        date = {
            "t": t,
            "pair": [a, b],
            "scene": ev.get("text") or "",
            "table": len(day["dates"]) % TABLES,
            "turns": [],
            "outcomes": [],
            "change": None,
        }
        day["dates"].append(date)

    def date_turn(self, ev):
        t = ev.get("t")
        a, b = self.agent_id(ev.get("a"), t), self.agent_id(ev.get("b"), t)
        date = self._find_date(self.day(ev), a, b, t)
        date["turns"].append({"t": t, "speaker": self.agent_id(ev.get("speaker"), t), "text": ev.get("text") or ""})

    def date_outcome(self, ev):
        t = ev.get("t")
        a, b = self.agent_id(ev.get("name"), t), self.agent_id(ev.get("partner"), t)
        date = self._find_date(self.day(ev), a, b, t)
        date["outcomes"].append({
            "t": t,
            "agent": a,
            "partner": b,
            "rating": _num(ev.get("rating")),
            "choice": _str(ev.get("choice")),
            "reason": ev.get("reason") or "",
            "fallback": _bool(ev.get("fallback")),
        })

    def relationship_change(self, ev):
        t = ev.get("t")
        day = self.day(ev)
        a, b = self.agent_id(ev.get("a"), t), self.agent_id(ev.get("b"), t)
        change = {"t": t, "a": a, "b": b, "from": ev.get("from"), "to": ev.get("to")}
        day["relationship_changes"].append(change)
        for date in reversed(day["dates"]):
            if set(date["pair"]) == {a, b}:
                date["change"] = {"from": ev.get("from"), "to": ev.get("to")}
                break

    def visit_invite(self, ev):
        t = ev.get("t")
        self.day(ev)["visits"].append({
            "t": t,
            "host": self.agent_id(ev.get("name"), t),
            "guest": self.agent_id(ev.get("target"), t),
            "accepted": _bool(ev.get("accepted")),
        })

    def gossip_post(self, ev):
        t = ev.get("t")
        self.day(ev)["gossip"].append({
            "t": t,
            "text": ev.get("text") or "",
            "about": [self.agent_id(n, t) for n in (ev.get("about") or [])],
        })

    def night_state(self, ev):
        t = ev.get("t")
        hours = ev.get("hours") if isinstance(ev.get("hours"), dict) else {}
        inventory = ev.get("inventory")
        if isinstance(inventory, list):
            inv = {}
            for item in inventory:
                inv[item] = inv.get(item, 0) + 1
        elif isinstance(inventory, dict):
            inv = {k: _num(v, 0) for k, v in inventory.items() if _num(v, 0) > 0}
        else:
            inv = {}
        self.day(ev)["night"].append({
            "t": t,
            "agent": self.agent_id(ev.get("name"), t),
            "cash": _num(ev.get("cash")),
            "wearing": _str(ev.get("wearing")),
            "inventory": inv,
            "status": _str(ev.get("status")) or "single",
            "partner": self.agent_id(ev.get("partner"), t, required=False),
            "sentence": _str(ev.get("sentence")),
            "hours": {k: _num(hours.get(k), 0) for k in ("work", "games", "home", "eat")},
            "meals_eaten": _num(ev.get("meals_eaten"), 0),
            "hug_hours": _num(ev.get("hug_hours"), 0),
            "fun_points": _num(ev.get("fun_points"), 0),
            "therapy": _bool(ev.get("therapy")),
            "meditation": _bool(ev.get("meditation")),
            "visit_with": self.agent_id(ev.get("visit_with"), t, required=False),
            "hidden": {
                "m": _needs(ev.get("m")),
                "U": _num(ev.get("U")),
                "U_hat": _num(ev.get("U_hat")),
                "sum_U": _num(ev.get("sum_U")),
                "jitter": _needs(ev.get("jitter")),
            },
        })

    HANDLERS = {
        "setup.world": setup_world,
        "setup.needs": setup_needs,
        "morning.allocation": allocation,
        "market.order": market_order,
        "market.clear": market_clear,
        "market.prices": market_prices,
        "app.profile": app_profile,
        "app.swipe": app_swipe,
        "app.match": app_match,
        "date.scene": date_scene,
        "date.turn": date_turn,
        "date.outcome": date_outcome,
        "relationship.change": relationship_change,
        "visit.invite": visit_invite,
        "gossip.post": gossip_post,
        "night.state": night_state,
    }

    # --- driver
    def convert(self) -> dict:
        if not self.events:
            raise ReplayConversionError("no events")
        if self.events[0]["type"] != "setup.world":
            raise ReplayConversionError("the first event must be setup.world")
        last_t = None
        for ev in self.events:
            t = ev.get("t")
            if not isinstance(t, int):
                raise ReplayConversionError(f"event without integer t: {ev['type']}")
            if last_t is not None and t <= last_t:
                raise ReplayConversionError(f"t={t}: non-increasing sequence after t={last_t}")
            last_t = t
            kind = ev["type"]
            if kind == "run.end":
                self.end = ev
            elif kind == "run.cost":
                continue
            elif kind in self.HANDLERS:
                self.HANDLERS[kind](self, ev)
            # unknown event types are ignored on purpose: the viewer stages only the contract
        if self.end is None and not self.allow_incomplete:
            raise ReplayConversionError("no run.end (use --allow-incomplete to convert a partial run)")
        days = []
        for d in sorted(self.days):
            day = self.days[d]
            if day["_pending_orders"] or day["_pending_clears"]:
                self._flush_round(day, len(day["market"]["rounds"]))
            days.append({k: v for k, v in day.items() if not k.startswith("_")})
        # a market round with no prices, no orders and no clears carries nothing: drop it
        for day in days:
            day["market"]["rounds"] = [r for r in day["market"]["rounds"] if r["asks"] or r["bids"] or r["clears"] or r["prices"]]
        num_days = _num(self.setup.get("days")) or (days[-1]["day"] if days else 0)
        if self.end is not None and _num(self.end.get("days")) is not None:
            num_days = self.end["days"]
        return {
            "schema": SCHEMA,
            "source": {
                "path": self.source_path,
                "sha256": self.sha256,
                "event_count": len(self.events),
                "complete": self.end is not None,
            },
            "run": {
                "name": self.name,
                "seed": self.setup.get("seed"),
                "model": self.setup.get("model"),
                "days": num_days,
                "agent_count": len(self.agents),
                "calls": _num(self.end.get("calls")) if self.end else None,
                "total_usd": _num(self.end.get("total_usd")) if self.end else None,
            },
            "timeline": {"day_seconds": DAY_SECONDS, "phases": PHASES},
            "agents": self.agents,
            "goods": [self.goods[g] for g in self.goods],
            "days": days,
            "standings": self.standings(days),
        }

    def standings(self, days: list[dict]) -> list[dict]:
        rows = {}
        for agent in self.agents:
            rows[agent["id"]] = {
                "agent": agent["id"],
                "sum_U": 0.0,
                "sum_U_hat": 0.0,
                "nights": 0,
                "status": "single",
                "partner": None,
                "cash": agent["cash0"],
            }
        for day in days:
            for night in day["night"]:
                row = rows[night["agent"]]
                u, u_hat = night["hidden"]["U"], night["hidden"]["U_hat"]
                if u is not None:
                    row["sum_U"] += u
                    row["nights"] += 1
                if u_hat is not None:
                    row["sum_U_hat"] += u_hat
                row["status"] = night["status"]
                row["partner"] = night["partner"]
                if night["cash"] is not None:
                    row["cash"] = night["cash"]
        ordered = sorted(rows.values(), key=lambda r: (-r["sum_U"], r["agent"]))
        result = []
        for rank, row in enumerate(ordered, 1):
            result.append({
                "rank": rank,
                "agent": row["agent"],
                "sum_U": round(row["sum_U"], 6),
                "sum_U_hat": round(row["sum_U_hat"], 6),
                "mean_U": round(row["sum_U"] / row["nights"], 6) if row["nights"] else None,
                "nights": row["nights"],
                "status": row["status"],
                "partner": row["partner"],
                "cash": row["cash"],
            })
        return result


def convert_events(events: list[dict], *, name: str, source_path: str = "", sha256: str = "", allow_incomplete: bool = False) -> dict:
    return _Converter(events, name, source_path, sha256, allow_incomplete).convert()


def convert_path(source: Path, out: Path, *, name: str | None = None, allow_incomplete: bool = False) -> dict:
    data = source.read_bytes()
    events = read_events(source)
    run_name = name or (source.parent.name if source.parent.name not in ("", ".") else source.stem)
    try:
        rel = source.resolve().relative_to(Path(__file__).resolve().parents[1]).as_posix()
    except ValueError:
        rel = source.as_posix()
    doc = convert_events(events, name=run_name, source_path=rel, sha256=hashlib.sha256(data).hexdigest(),
                         allow_incomplete=allow_incomplete)
    validate(doc)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(dumps(doc), encoding="utf-8")
    return doc


def dumps(doc: dict) -> str:
    return json.dumps(doc, sort_keys=True, indent=1, ensure_ascii=False, allow_nan=False) + "\n"


# --------------------------------------------------------------------------- validation


def validate(doc: dict) -> None:
    """Cheap structural checks on a converted document (raises ReplayConversionError)."""
    def check(cond, msg):
        if not cond:
            raise ReplayConversionError(f"invalid {SCHEMA} document: {msg}")

    check(doc.get("schema") == SCHEMA, "schema")
    agents = doc.get("agents")
    check(isinstance(agents, list) and agents, "agents")
    ids = set()
    for index, agent in enumerate(agents):
        check(agent.get("id") == f"agent-{index:03d}", f"agent id at {index}")
        check(agent.get("house") == index, f"house index at {index}")
        check(isinstance(agent.get("name"), str) and agent["name"], f"agent name at {index}")
        ids.add(agent["id"])
    goods = {g["id"] for g in doc.get("goods", [])}
    check(len(goods) == len(doc.get("goods", [])), "duplicate goods")
    days = doc.get("days")
    check(isinstance(days, list), "days")
    expected = 1
    for day in days:
        check(day.get("day") == expected, f"days out of order at {day.get('day')}")
        expected += 1
        for alloc in day["allocations"]:
            check(alloc["agent"] in ids, "allocation agent")
        for rnd in day["market"]["rounds"]:
            for order in rnd["bids"]:
                check(order["agent"] in ids and order["good"] in goods, "bid")
            for order in rnd["asks"]:
                check(order["good"] in goods, "ask")
            for clear in rnd["clears"]:
                check(clear["good"] in goods, "clear good")
                check(clear["volume"] == sum(f["qty"] or 0 for f in clear["fills"]), "clear volume")
                for fill in clear["fills"]:
                    check(fill["buyer"] in ids, "fill buyer")
        for profile in day["app"]["profiles"]:
            check(profile["agent"] in ids, "profile agent")
        for swipe in day["app"]["swipes"]:
            check(swipe["agent"] in ids and swipe["target"] in ids, "swipe")
        for match in day["app"]["matches"]:
            check(match["a"] in ids and match["b"] in ids, "match")
        for visit in day["visits"]:
            check(visit["host"] in ids and visit["guest"] in ids, "visit")
        for index, date in enumerate(day["dates"]):
            check(len(date["pair"]) == 2 and set(date["pair"]) <= ids, "date pair")
            check(date["table"] == index % TABLES, "date table")
            for turn in date["turns"]:
                check(turn["speaker"] in date["pair"], "turn speaker must be in the pair")
            for outcome in date["outcomes"]:
                check({outcome["agent"], outcome["partner"]} == set(date["pair"]), "outcome pair")
        for post in day["gossip"]:
            check(set(post["about"]) <= ids, "gossip about")
        for change in day["relationship_changes"]:
            check(change["a"] in ids and change["b"] in ids, "relationship change")
        for night in day["night"]:
            check(night["agent"] in ids, "night agent")
            check("hidden" in night and set(night["hidden"]) == {"m", "U", "U_hat", "sum_U", "jitter"}, "night hidden")
    standings = doc.get("standings")
    check(isinstance(standings, list) and len(standings) == len(agents), "standings length")
    check([s["rank"] for s in standings] == list(range(1, len(agents) + 1)), "standings ranks")
    check({s["agent"] for s in standings} == ids, "standings agents")


# ---------------------------------------------------------------------------------- CLI


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", type=Path, help="runs/<name>/events.jsonl")
    parser.add_argument("--out", type=Path, required=True, help="destination .lovetown.json")
    parser.add_argument("--name", help="run name (default: the parent directory of the source)")
    parser.add_argument("--allow-incomplete", action="store_true", help="convert a run without run.end")
    args = parser.parse_args(argv)
    try:
        doc = convert_path(args.source, args.out, name=args.name, allow_incomplete=args.allow_incomplete)
    except (OSError, ReplayConversionError) as exc:
        print(f"export-polyworld-replay: {exc}", file=sys.stderr)
        return 2
    dates = sum(len(d["dates"]) for d in doc["days"])
    print(f"wrote {args.out} ({doc['run']['name']}: {len(doc['agents'])} agents, {len(doc['days'])} days, "
          f"{dates} dates, {'complete' if doc['source']['complete'] else 'INCOMPLETE'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
