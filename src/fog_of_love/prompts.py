"""Every string the characters see. Keep them short: cost matters, and the mock model keys on the tags."""

from __future__ import annotations

PREMISE = (
    "You just arrived in Love Town, you are a young single career professional, just out of college. "
    "You are still discovering your needs, and you just want to be happy. But oh boy.. How to be happy? "
    "And even more.. What is love?"
)

CONTEXT = (
    PREMISE
    + "\nYou need to find out what makes you content; each night you learn how content you felt.\n"
    "How Love Town works: every day you have 16 waking hours to split between work (paid 12 per hour), playing "
    "videogames you own, time at home, and eating (one hour per meal, at most two meals a day; meals come from "
    "the restaurant). Therapy (60, 2 hours) and meditation (free, 2 hours) are available, at most one per day. "
    "The market sells clothes in three tiers (Low/Mid/High; visible on your dating-app picture and on dates), "
    "videogames, and restaurant meals in three tiers. Time at home counts as time together only with a "
    "cohabiting partner or an invited guest. Every visit by a non-partner to someone's home is posted on the "
    "town gossip board."
)

MORNING_TAG = "Morning decision"
SWIPE_TAG = "Dating app"
DATE_TAG = "On the date"
POST_DATE_TAG = "After the date with"

MORNING_SCHEMA = (
    '{"hours": {"work": int, "games": int, "home": int, "eat": int}, '
    '"shopping": [{"good": "<good id>", "price": number, "qty": int}], '
    '"wear": "<owned clothing id or null>", "therapy": bool, "meditation": bool, '
    '"invite": "<name or null>", "accept_invite": "<name or null>", '
    '"breakup": bool, "accept_move_in": bool, '
    '"profile_text": "<dating profile, up to 240 characters, or null to keep the current one>"}'
)


def morning_call(day: int) -> str:
    return (
        f"{MORNING_TAG}, day {day}. Decide {{name}}'s day. Reply with one JSON object only, no prose, with exactly "
        f"these keys: {MORNING_SCHEMA}. Hours must sum to 16 (14 if therapy or meditation); eat is 0-2. "
        "Shopping entries are bids at the market (price per unit); leave the list empty to buy nothing."
    )


def swipe_call(day: int, profiles: list[tuple[str, str, str, str]]) -> str:
    lines = [f"{i + 1}. {name}: wearing {item} ({tier}). \"{text}\"" for i, (name, item, tier, text) in enumerate(profiles)]
    return (
        f"{SWIPE_TAG}, day {day}. {{name}} sees these profiles:\n" + "\n".join(lines)
        + '\nReply with one JSON object only: {"swipes": {"<name>": true or false, ...}} with one entry per profile.'
    )


def date_turn_call(other: str) -> str:
    return (
        f"{DATE_TAG} with {other} at the restaurant. What does {{name}} say next to {other}? "
        "Reply with only the spoken words, one to three sentences, no name prefix."
    )


def post_date_call(other: str) -> str:
    return (
        f"{POST_DATE_TAG} {other}: privately, reply with one JSON object only: "
        '{"rating": number from 0 to 10, "choice": "ask_again" or "propose_move_in" or "decline", '
        '"reason": "one sentence"}'
    )


def retry_suffix() -> str:
    return "\nYour previous reply was not valid JSON. Reply with only the JSON object."


def kind_of(prompt: str) -> str:
    """Which Fog of Love prompt this is, from the last call to action in the prompt (for the mock and the call log)."""
    tail = prompt[-2500:]
    last = max(tail.rfind(MORNING_TAG), tail.rfind(SWIPE_TAG), tail.rfind(DATE_TAG), tail.rfind(POST_DATE_TAG))
    if last < 0:
        return "other"
    tag = tail[last:]
    if tag.startswith(POST_DATE_TAG):
        return "post_date"
    if tag.startswith(DATE_TAG):
        return "date_turn"
    if tag.startswith(SWIPE_TAG):
        return "swipes"
    return "morning"


def content_sentence(u_hat: float) -> str:
    return f"Last night you felt {round(100 * u_hat)}% content."
