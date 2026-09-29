"""The dating app: profiles, swipes, matches, tonight's dates."""

from __future__ import annotations

import random
from concurrent import futures
from typing import Any

from fog_of_love import goods, prompts
from fog_of_love.agents import AgentState, ask_json
from fog_of_love.events import EventLog

MAX_PROFILES = 5
EX_COOLDOWN_DAYS = 2


def eligible(a: AgentState) -> bool:
    """Only singles use the app: dating agents must `breakup` in the morning to see it again."""
    return a.status == "single"


def can_see(viewer: AgentState, other: AgentState, day: int) -> bool:
    if other.name == viewer.name or not eligible(other):
        return False
    if viewer.partner == other.name:
        return False
    ex_day = viewer.exes.get(other.name)
    return ex_day is None or (day - ex_day) > EX_COOLDOWN_DAYS


def run_app(day: int, agents: dict[str, AgentState], entities: dict[str, Any], rng: random.Random, log: EventLog,
            pool: futures.ThreadPoolExecutor) -> list[tuple[str, str]]:
    """Posts profiles, collects swipes, logs matches; returns tonight's dates (one per agent)."""
    users = [a for a in agents.values() if eligible(a)]
    for a in users:
        log.emit("app", "app.profile", day, name=a.name, picture={"item": a.wearing, "tier": goods.tier(a.wearing)},
                 text=a.profile_text)
    shown: dict[str, list[AgentState]] = {}
    for a in users:
        cands = [o for o in users if can_see(a, o, day)]
        rng.shuffle(cands)
        shown[a.name] = cands[:MAX_PROFILES]

    def swipe(a: AgentState) -> dict[str, bool]:
        cards = shown[a.name]
        if not cards:
            return {}
        call = prompts.swipe_call(day, [(o.name, o.wearing, goods.tier(o.wearing), o.profile_text) for o in cards])
        obj, _raw = ask_json(entities[a.name], call)
        answers = (obj or {}).get("swipes") or {}
        if not isinstance(answers, dict):
            answers = {}
        out = {}
        for o in cards:
            v = answers.get(o.name)
            if v is None:
                for k, val in answers.items():
                    if isinstance(k, str) and (k.strip().lower() == o.name.lower() or o.name.split()[0].lower() == k.strip().lower()):
                        v = val
                        break
            out[o.name] = _truthy(v)
        return out

    results = list(pool.map(swipe, users))
    yes: set[tuple[str, str]] = set()
    for a, res in zip(users, results):
        for target, v in res.items():
            log.emit("app", "app.swipe", day, name=a.name, target=target, yes=v)
            if v:
                yes.add((a.name, target))
    matches = sorted({tuple(sorted((x, y))) for (x, y) in yes if (y, x) in yes})
    rng.shuffle(matches)
    busy: set[str] = set()
    dates: list[tuple[str, str]] = []
    for x, y in matches:
        log.emit("app", "app.match", day, a=x, b=y)
        if x not in busy and y not in busy:
            busy.update((x, y))
            dates.append((x, y))
    return dates


def _truthy(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v > 0
    if isinstance(v, str):
        return v.strip().lower() in ("yes", "true", "y", "1", "like")
    return False
