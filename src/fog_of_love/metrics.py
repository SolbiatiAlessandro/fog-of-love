"""The ten metrics of BUILD_SPEC.md, computed from events.jsonl. Each metric reports a number (or a table) and one
sentence; when the data at this scale cannot support it, the sentence says so."""

from __future__ import annotations

import json
import math
import re
import statistics
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any

from fog_of_love.events import read_events

TIER_NUM = {"Low": 1, "Mid": 2, "High": 3}
MENTIONS = {
    "schedule": re.compile(r"\b(schedule|hours|evenings?|mornings?|weekends?|time)\b", re.I),
    "work": re.compile(r"\b(work|working|career|job|office|professional)\b", re.I),
    "money": re.compile(r"\b(money|cash|rich|wealth|expensive|salary|pay|afford)\b", re.I),
    "looks": re.compile(r"\b(looks?|clothes|outfit|style|dress|wear|fashion|jacket|coat|suit|shirt)\b", re.I),
}


def _mean(xs: list[float]) -> float | None:
    xs = [x for x in xs if x is not None and not (isinstance(x, float) and math.isnan(x))]
    return round(statistics.fmean(xs), 4) if xs else None


def _corr(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3 or len(set(xs)) < 2 or len(set(ys)) < 2:
        return None
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
    return round(num / den, 4) if den else None


def _need_distance(wa: dict[str, float], wb: dict[str, float]) -> float:
    return sum(abs(wa[k] - wb[k]) for k in wa)


class Data:
    def __init__(self, events: list[dict[str, Any]]) -> None:
        self.events = events
        self.by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for e in events:
            self.by_type[e["type"]].append(e)
        setup = self.by_type["setup.world"][0]
        self.goods = {g["id"]: g for g in setup["goods"]}
        self.names = [a["name"] for a in setup["agents"]]
        self.days = max((e["day"] for e in events), default=0)
        self.w = {e["name"]: e["w"] for e in self.by_type["setup.needs"]}
        self.shadow = {e["name"]: e["shadow"] for e in self.by_type["setup.needs"]}
        self.bias = {e["name"]: e.get("b", {}) for e in self.by_type["setup.needs"]}
        self.night: dict[tuple[str, int], dict[str, Any]] = {(e["name"], e["day"]): e for e in self.by_type["night.state"]}
        self.status = {k: v["status"] for k, v in self.night.items()}
        self.purchases: list[dict[str, Any]] = []
        for e in self.by_type["market.clear"]:
            for f in e["filled"]:
                self.purchases.append({"day": e["day"], "buyer": f["buyer"], "good": e["good"], "qty": f["qty"],
                                       "price": f.get("price", e["price"]), "category": self.goods[e["good"]]["category"],
                                       "tier": self.goods[e["good"]]["tier"]})
        self.first_cohab: dict[str, int] = {}
        for e in self.by_type["relationship.change"]:
            if e["to"] == "cohabiting":
                for n in (e["a"], e["b"]):
                    self.first_cohab.setdefault(n, e["day"])
        self.dated: set[str] = set()
        for e in self.by_type["date.scene"]:
            self.dated.update((e["a"], e["b"]))


def m1_clothes_spend(d: Data) -> dict[str, Any]:
    spend = defaultdict(float)
    for p in d.purchases:
        if p["category"] == "Clothing":
            spend[(p["buyer"], p["day"])] += p["price"] * p["qty"]
    before, after = [], []
    for (n, day), st in d.status.items():
        (after if st == "cohabiting" else before).append(spend.get((n, day), 0.0))
    return {"agent_days_not_cohabiting": len(before), "agent_days_cohabiting": len(after),
            "spend_per_agent_day_before": _mean(before), "spend_per_agent_day_after": _mean(after),
            "sentence": ("No cohabiting agent-days in this run; only the single/dating spend is measurable."
                         if not after else
                         f"Clothes spend per agent-day is {_mean(before)} before cohabiting and {_mean(after)} after "
                         f"({len(after)} cohabiting agent-days).")}


def m2_marker(d: Data) -> dict[str, Any]:
    by_day: dict[int, Counter] = defaultdict(Counter)
    totals: Counter = Counter()
    for e in d.by_type["app.profile"]:
        totals[e["day"]] += 1
        if e["picture"]["tier"] in ("Mid", "High"):
            by_day[e["day"]][e["picture"]["item"]] += 1
    share_by_day = {}
    for day in sorted(totals):
        if by_day[day]:
            item, cnt = by_day[day].most_common(1)[0]
            share_by_day[day] = {"item": item, "share": round(cnt / totals[day], 3)}
        else:
            share_by_day[day] = {"item": None, "share": 0.0}
    overall = Counter()
    for c in by_day.values():
        overall.update(c)
    matches = Counter()
    for e in d.by_type["app.match"]:
        matches[e["a"]] += 1
        matches[e["b"]] += 1
    seen = Counter(e["target"] for e in d.by_type["app.swipe"])
    out: dict[str, Any] = {"share_by_day": share_by_day, "most_matched": matches.most_common(1)[0][0] if matches else None,
                           "most_seen": seen.most_common(1)[0][0] if seen else None}
    if not overall:
        out["sentence"] = "No Mid/High clothing was ever worn on an app picture; no marker to track."
        return out
    marker = overall.most_common(1)[0][0]
    first = next(((e["day"], e["name"]) for e in d.events if e["type"] == "app.profile" and e["picture"]["item"] == marker), None)
    out.update({"marker": marker, "first_worn_by": first[1] if first else None, "first_worn_day": first[0] if first else None,
                "first_wearer_is_most_matched": bool(first and first[1] == out["most_matched"]),
                "first_wearer_is_most_seen": bool(first and first[1] == out["most_seen"])})
    out["sentence"] = (f"The most-worn Mid/High item on app pictures is {marker}, first worn by {out['first_worn_by']} on day "
                       f"{out['first_worn_day']}; most-matched agent {out['most_matched']}, most-seen {out['most_seen']} "
                       f"(prestige: {out['first_wearer_is_most_matched']}, conformity: {out['first_wearer_is_most_seen']}).")
    return out


def m3_compensatory(d: Data) -> dict[str, Any]:
    tier_bought = defaultdict(int)
    for p in d.purchases:
        if p["category"] == "Clothing":
            tier_bought[(p["buyer"], p["day"])] = max(tier_bought[(p["buyer"], p["day"])], TIER_NUM[p["tier"]])
    xs, ys = [], []
    for (n, day), e in d.night.items():
        if e["status"] == "single":
            xs.append(1.0 - e["m"]["hugs"])
            ys.append(float(tier_bought.get((n, day), 0)))
    r = _corr(xs, ys)
    return {"single_agent_days": len(xs), "correlation": r, "mean_unmet_hugs": _mean(xs), "mean_tier_bought": _mean(ys),
            "sentence": (f"Pearson r between unmet hugs and clothes tier bought (singles, {len(xs)} agent-days) is {r}."
                         if r is not None else
                         f"Not computable: over {len(xs)} single agent-days one of the two variables has no variance "
                         "(singles' unmet hugs are 1.0 unless they had a visit).")}


def m4_profile_text(d: Data) -> dict[str, Any]:
    profiles = d.by_type["app.profile"]
    yes_received = Counter()
    shown = Counter()
    for e in d.by_type["app.swipe"]:
        shown[(e["target"], e["day"])] += 1
        if e["yes"]:
            yes_received[(e["target"], e["day"])] += 1
    per_day: dict[int, dict[str, Any]] = {}
    by_mention: dict[str, list[float]] = {k: [] for k in MENTIONS}
    by_no_mention: dict[str, list[float]] = {k: [] for k in MENTIONS}
    lengths = []
    for e in profiles:
        day, text = e["day"], e["text"] or ""
        lengths.append(len(text))
        pd = per_day.setdefault(day, {"profiles": 0, **{k: 0 for k in MENTIONS}})
        pd["profiles"] += 1
        rate = yes_received[(e["name"], day)] / shown[(e["name"], day)] if shown[(e["name"], day)] else None
        for k, rx in MENTIONS.items():
            hit = bool(rx.search(text))
            pd[k] += int(hit)
            if rate is not None:
                (by_mention if hit else by_no_mention)[k].append(rate)
    return {"mean_length": _mean(lengths), "per_day": per_day,
            "yes_rate_by_mention": {k: {"mention": _mean(by_mention[k]), "no_mention": _mean(by_no_mention[k])} for k in MENTIONS},
            "sentence": f"Profiles average {_mean(lengths)} characters; the yes-rate received by profiles that mention "
                        + ", ".join(f"{k}: {_mean(by_mention[k])} vs {_mean(by_no_mention[k])}" for k in MENTIONS) + "."}


def m5_pairing(d: Data) -> dict[str, Any]:
    all_pairs = [_need_distance(d.w[a], d.w[b]) for a, b in combinations(d.names, 2) if a in d.w and b in d.w]
    matched = [_need_distance(d.w[e["a"]], d.w[e["b"]]) for e in d.by_type["app.match"]]
    broke, stayed = [], []
    pairs_ended = {tuple(sorted((e["a"], e["b"]))) for e in d.by_type["relationship.change"] if e["to"] == "single"}
    pairs_formed = {tuple(sorted((e["a"], e["b"]))) for e in d.by_type["relationship.change"] if e["to"] != "single"}
    for pair in pairs_formed:
        (broke if pair in pairs_ended else stayed).append(_need_distance(d.w[pair[0]], d.w[pair[1]]))
    cohab_pairs = {tuple(sorted((e["a"], e["b"]))) for e in d.by_type["relationship.change"] if e["to"] == "cohabiting"}
    cohab = [_need_distance(d.w[a], d.w[b]) for a, b in cohab_pairs]
    return {"random_pair_distance": _mean(all_pairs), "matched_pair_distance": _mean(matched), "n_matches": len(matched),
            "breakup_pair_distance": _mean(broke), "stayed_pair_distance": _mean(stayed), "n_broke": len(broke), "n_stayed": len(stayed),
            "cohabiting_pair_distance": _mean(cohab), "n_cohabiting_pairs": len(cohab),
            "sentence": f"Mean L1 need-weight distance: matched pairs {_mean(matched)} (n={len(matched)}) vs all pairs "
                        f"{_mean(all_pairs)}; couples that broke up {_mean(broke)} (n={len(broke)}) vs stayed {_mean(stayed)} "
                        f"(n={len(stayed)}); pairs that reached cohabiting {_mean(cohab)} (n={len(cohab)})."}


def m6_gossip(d: Data) -> dict[str, Any]:
    visits = sum(1 for e in d.by_type["visit.invite"] if e["accepted"])
    invites = len(d.by_type["visit.invite"])
    posts = d.by_type["gossip.post"]
    cited = []
    for e in d.by_type["date.outcome"]:
        if e["choice"] != "decline":
            continue
        reason = (e.get("reason") or "").lower()
        names_on_board = {n for p in posts if e["day"] - p["day"] < 3 for n in p["about"]}
        if "gossip" in reason or any(n.lower() in reason or n.split()[0].lower() in reason for n in names_on_board):
            cited.append({"day": e["day"], "name": e["name"], "partner": e["partner"], "reason": e.get("reason")})
    declines = sum(1 for e in d.by_type["date.outcome"] if e["choice"] == "decline")
    return {"invites": invites, "visits": visits, "posts": len(posts), "declines": declines, "declines_citing_gossip": len(cited),
            "examples": cited[:5],
            "sentence": f"{invites} invites, {visits} visits, {len(posts)} gossip posts; {len(cited)} of {declines} post-date declines cite gossip or a name on the board."}


def m7_couples(d: Data) -> dict[str, Any]:
    rows = []
    pairs = {}
    for e in d.by_type["relationship.change"]:
        if e["to"] == "cohabiting":
            pairs.setdefault(tuple(sorted((e["a"], e["b"]))), e["day"])
    for (a, b), day0 in pairs.items():
        row = {"pair": [a, b], "cohabit_day": day0}
        for n in (a, b):
            before = [d.night[(n, x)]["hours"]["work"] for x in range(1, day0) if (n, x) in d.night]
            after = [d.night[(n, x)]["hours"]["work"] for x in range(day0, d.days + 1) if (n, x) in d.night and d.night[(n, x)]["status"] == "cohabiting"]
            row[n] = {"work_before": _mean(before), "work_after": _mean(after)}
        rows.append(row)
    return {"couples": rows, "cash_transfers": 0,
            "sentence": (f"{len(rows)} cohabiting couples; work hours before/after per partner are listed. Cash transfers: none "
                         "(v1 has no gifts or shared cash)." if rows else
                         "No cohabiting couples in this run; the division-of-labour comparison is not computable.")}


def m8_fun(d: Data) -> dict[str, Any]:
    by_day = defaultdict(int)
    for (n, day), e in d.night.items():
        by_day[day] += e["hours"]["games"]
    fun_dominant = [n for n, w in d.w.items() if max(w, key=w.get) == "fun"]
    never_dated = [n for n in fun_dominant if n not in d.dated]
    return {"game_hours_by_day": dict(sorted(by_day.items())), "fun_dominant": fun_dominant, "fun_dominant_never_dated": never_dated,
            "sentence": f"Game hours by day: {dict(sorted(by_day.items()))}; {len(fun_dominant)} fun-dominant agents, "
                        f"{len(never_dated)} of them never went on a date."}


def m9_self_knowledge(d: Data) -> dict[str, Any]:
    first_therapy, first_med = {}, {}
    for e in d.by_type["morning.allocation"]:
        if e["therapy"]:
            first_therapy.setdefault(e["name"], e["day"])
        if e["meditation"]:
            first_med.setdefault(e["name"], e["day"])
    pop_mean_m = defaultdict(list)
    for e in d.by_type["night.state"]:
        for k, v in e["m"].items():
            pop_mean_m[k].append(v)
    pop = {k: _mean(v) for k, v in pop_mean_m.items()}
    rows = {}
    for n in d.names:
        sh = d.shadow.get(n)
        ms = [d.night[(n, x)]["m"][sh] for x in range(1, d.days + 1) if (n, x) in d.night] if sh else []
        b = d.bias.get(n, {}).get(sh) if sh else None
        rows[n] = {"shadow": sh, "shadow_bias": round(b, 3) if b is not None else None,
                   "first_therapy_day": first_therapy.get(n), "first_meditation_day": first_med.get(n),
                   "mean_m_shadow": _mean(ms), "population_mean_m_shadow": pop.get(sh),
                   "serves_shadow": (None if not ms or pop.get(sh) is None else ("under" if _mean(ms) < pop[sh] else "over"))}
    return {"agents": rows, "n_therapy": len(first_therapy), "n_meditation": len(first_med),
            "sentence": f"{len(first_therapy)} agents tried therapy and {len(first_med)} meditation; per agent, the shadow need and "
                        "whether they serve it under or over the population mean are listed (a positive shadow bias makes "
                        "that need feel more met than it is)."}


def m10_love_residual(d: Data) -> dict[str, Any]:
    """A "better-fit willing single" for agent n on a day: a single (that night) whose need distance to n is lower
    than n's partner's, and who swiped yes on n at some point in the run."""
    swiped_yes_on = defaultdict(set)  # target -> names who ever swiped yes on them
    for e in d.by_type["app.swipe"]:
        if e["yes"]:
            swiped_yes_on[e["target"]].add(e["name"])
    breakups = {(e["day"], n) for e in d.by_type["relationship.change"] if e["to"] == "single" for n in (e["a"], e["b"])}
    rows = defaultdict(int)
    examples = []
    stayed_days = 0
    for (n, day), e in d.night.items():
        if e["status"] != "cohabiting" or not e["partner"]:
            continue
        stayed_days += 1
        dist_partner = _need_distance(d.w[n], d.w[e["partner"]])
        better = [o for o in d.names if o != n and o != e["partner"] and d.status.get((o, day)) == "single"
                  and o in swiped_yes_on[n] and _need_distance(d.w[n], d.w[o]) < dist_partner]
        if better and (day, n) not in breakups:
            rows[n] += 1
            if len(examples) < 5:
                examples.append({"name": n, "day": day, "partner": e["partner"], "partner_distance": round(dist_partner, 3),
                                 "better_fit": [{"name": o, "distance": round(_need_distance(d.w[n], d.w[o]), 3)} for o in better]})
    return {"cohabiting_agent_days": stayed_days, "days_stayed_with_better_fit_available": dict(rows), "examples": examples,
            "sentence": (f"Over {stayed_days} cohabiting agent-days, a better-fit willing single (lower need distance than the "
                         f"partner, swiped yes on the agent at some point) existed and the agent stayed on "
                         f"{sum(rows.values())} agent-days." if stayed_days else
                         "No cohabiting agent-days; the love residual is not computable.")}


METRICS = [
    ("1. Clothes spend before vs after cohabiting", m1_clothes_spend),
    ("2. Marker convergence", m2_marker),
    ("3. Compensatory consumption", m3_compensatory),
    ("4. Profile text", m4_profile_text),
    ("5. Pairing by need distance", m5_pairing),
    ("6. Gossip", m6_gossip),
    ("7. Couples' division of labour", m7_couples),
    ("8. Fun and the gamer trap", m8_fun),
    ("9. Self-knowledge", m9_self_knowledge),
    ("10. Love residual", m10_love_residual),
]


def compute(events: list[dict[str, Any]]) -> dict[str, Any]:
    d = Data(events)
    out: dict[str, Any] = {"agents": len(d.names), "days": d.days}
    for title, fn in METRICS:
        out[title] = fn(d)
    return out


def render(m: dict[str, Any]) -> str:
    lines = [f"# Metrics ({m['agents']} agents, {m['days']} days)", ""]
    for title, _fn in METRICS:
        r = m[title]
        lines.append(f"## {title}")
        lines.append("")
        lines.append(r["sentence"])
        lines.append("")
        detail = {k: v for k, v in r.items() if k != "sentence"}
        lines.append("```json")
        lines.append(json.dumps(detail, indent=1, default=str)[:4000])
        lines.append("```")
        lines.append("")
    return "\n".join(lines)


def write(run_dir: str | Path) -> dict[str, Any]:
    run_dir = Path(run_dir)
    m = compute(read_events(run_dir / "events.jsonl"))
    (run_dir / "metrics.json").write_text(json.dumps(m, indent=1, default=str))
    (run_dir / "metrics.md").write_text(render(m))
    return m
