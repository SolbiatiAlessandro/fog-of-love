"""Dates: a 10-turn alternating chat between two Concordia entities at the restaurant, then private ratings and
choices. (Plain `act` with a free-text spec; not the dialogic game master. See STATUS.md.)"""

from __future__ import annotations

import re
from typing import Any

from fog_of_love import goods, prompts
from fog_of_love.agents import AgentState, ask_json, ask_text

TURNS = 10
CHOICES = ("ask_again", "propose_move_in", "decline")


def schedule_text(a: AgentState) -> str:
    h = a.hours
    extra = " and therapy" if a.therapy else (" and meditation" if a.meditation else "")
    return f"work {h.get('work', 0)}h, games {h.get('games', 0)}h, home {h.get('home', 0)}h, eating {h.get('eat', 0)}h{extra}"


def scene_text(a: AgentState, b: AgentState) -> str:
    return (
        f"{a.name} and {b.name} meet for a date at the Love Town restaurant. "
        f"{a.name} is wearing {a.wearing} ({goods.tier(a.wearing)} tier). "
        f"{b.name} is wearing {b.wearing} ({goods.tier(b.wearing)} tier). "
        f"{a.name}'s day: {schedule_text(a)}. {b.name}'s day: {schedule_text(b)}."
    )


def clean_line(text: str, speaker: str) -> str:
    t = text.strip().strip('"').strip()
    t = re.sub(rf"^{re.escape(speaker)}\s*(--|:|says:?)\s*", "", t, flags=re.IGNORECASE).strip()
    t = t.strip('"').strip()
    t = t.split("\n")[0].strip() if t else t
    return t[:400] if t else "..."


def parse_outcome(obj: dict[str, Any] | None) -> tuple[float, str, str, bool]:
    """(rating, choice, reason, fallback)."""
    if not obj:
        return 5.0, "decline", "", True
    try:
        rating = float(obj.get("rating", 5.0))
    except (TypeError, ValueError):
        rating = 5.0
    rating = min(10.0, max(0.0, rating))
    choice = str(obj.get("choice", "")).strip().lower().replace(" ", "_")
    if choice not in CHOICES:
        if "move" in choice:
            choice = "propose_move_in"
        elif "again" in choice or "yes" in choice:
            choice = "ask_again"
        else:
            choice = "decline"
    reason = str(obj.get("reason", ""))[:300]
    return rating, choice, reason, False


def run_date(day: int, a: AgentState, b: AgentState, entities: dict[str, Any]) -> list[dict[str, Any]]:
    """Runs the date and returns the events to log, in order (scene, turns, outcomes)."""
    events: list[dict[str, Any]] = []
    scene = scene_text(a, b)
    events.append({"type": "date.scene", "a": a.name, "b": b.name, "text": scene})
    entities[a.name].observe(f"[date, day {day}] {scene}")
    entities[b.name].observe(f"[date, day {day}] {scene}")
    order = [(a, b), (b, a)]
    for turn in range(TURNS):
        speaker, listener = order[turn % 2]
        raw = ask_text(entities[speaker.name], prompts.date_turn_call(listener.name))
        line = clean_line(raw, speaker.name)
        events.append({"type": "date.turn", "a": a.name, "b": b.name, "speaker": speaker.name, "text": line})
        entities[speaker.name].observe(f"[date] {speaker.name} said to {listener.name}: \"{line}\"")
        entities[listener.name].observe(f"[date] {speaker.name} said to {listener.name}: \"{line}\"")
    for me, other in order:
        obj, raw = ask_json(entities[me.name], prompts.post_date_call(other.name))
        rating, choice, reason, fallback = parse_outcome(obj)
        events.append({"type": "date.outcome", "name": me.name, "partner": other.name, "rating": rating,
                       "choice": choice, "reason": reason, "raw": raw[:500], "fallback": fallback})
        entities[me.name].observe(f"[reflection] After the date, {me.name} rated {other.name} {rating:.0f}/10 and chose {choice}.")
    return events
