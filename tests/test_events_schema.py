"""Every event type of BUILD_SPEC.md appears in a mock run, with the required fields and types."""

import json

from fog_of_love.events import PHASES, read_events

S, I, F, B, L, D = str, int, (int, float), bool, list, dict
NUM = (int, float)
REQUIRED = {
    "setup.world": {"agents": L, "goods": L, "days": I, "seed": I},
    "setup.needs": {"name": S, "w": D, "shadow": S},
    "morning.allocation": {"name": S, "hours": D, "therapy": B, "meditation": B, "invite": (str, type(None)),
                           "breakup": B, "raw": S},
    "market.order": {"name": S, "side": S, "good": S, "price": NUM, "qty": I},
    "market.clear": {"good": S, "price": NUM, "filled": L},
    "market.prices": {"round": I, "prices": D},
    "app.profile": {"name": S, "picture": D, "text": S},
    "app.swipe": {"name": S, "target": S, "yes": B},
    "app.match": {"a": S, "b": S},
    "date.scene": {"a": S, "b": S, "text": S},
    "date.turn": {"a": S, "b": S, "speaker": S, "text": S},
    "date.outcome": {"name": S, "partner": S, "rating": NUM, "choice": S},
    "relationship.change": {"a": S, "b": S, "from": S, "to": S},
    "visit.invite": {"name": S, "target": S, "accepted": B},
    "gossip.post": {"text": S, "about": L},
    "night.state": {"name": S, "m": D, "U": NUM, "U_hat": NUM, "sentence": S, "cash": NUM, "inventory": D,
                    "wearing": S, "partner": (str, type(None)), "status": S},
    "run.cost": {"calls": I, "usd": NUM},
    "run.end": {"days": I, "total_usd": NUM},
}


def test_every_event_type_present_with_required_fields(mock_run):
    out, summary = mock_run
    events = read_events(out / "events.jsonl")
    seen = {e["type"] for e in events}
    missing = set(REQUIRED) - seen
    assert not missing, f"missing event types in mock run: {missing}"
    last_t = 0
    for e in events:
        assert e["t"] == last_t + 1
        last_t = e["t"]
        assert isinstance(e["day"], int)
        assert e["phase"] in PHASES
        assert e["type"] in REQUIRED, e["type"]
        for field, typ in REQUIRED[e["type"]].items():
            assert field in e, f"{e['type']} missing {field}: {e}"
            assert isinstance(e[field], typ), f"{e['type']}.{field} has type {type(e[field])}"
            assert not isinstance(e[field], bool) or typ is B or B in (typ if isinstance(typ, tuple) else (typ,))


def test_typed_subfields(mock_run):
    out, _ = mock_run
    for e in read_events(out / "events.jsonl"):
        t = e["type"]
        if t == "setup.world":
            for a in e["agents"]:
                assert {"name", "persona_summary", "cash", "wearing"} <= set(a)
            for g in e["goods"]:
                assert {"id", "category", "tier", "list_price"} <= set(g)
        elif t == "setup.needs":
            assert set(e["w"]) == {"food", "hugs", "money", "fun"}
            assert abs(sum(e["w"].values()) - 1) < 1e-6
        elif t == "morning.allocation":
            assert set(e["hours"]) == {"work", "games", "home", "eat"}
            assert sum(e["hours"].values()) == (14 if (e["therapy"] or e["meditation"]) else 16)
            assert 0 <= e["hours"]["eat"] <= 2
        elif t == "market.order":
            assert e["side"] in ("bid", "ask")
        elif t == "market.clear":
            for f in e["filled"]:
                assert {"buyer", "seller", "qty"} <= set(f)
        elif t == "app.profile":
            assert {"item", "tier"} <= set(e["picture"])
            assert len(e["text"]) <= 240
        elif t == "date.outcome":
            assert e["choice"] in ("ask_again", "propose_move_in", "decline")
            assert 0 <= e["rating"] <= 10
        elif t == "relationship.change":
            assert e["from"] in ("single", "dating", "cohabiting") and e["to"] in ("single", "dating", "cohabiting")
        elif t == "night.state":
            assert set(e["m"]) == {"food", "hugs", "money", "fun"}
            assert all(0 <= v <= 1 for v in e["m"].values())
            assert 0 <= e["U"] <= 1 and 0 <= e["U_hat"] <= 1
            assert e["sentence"].startswith("Last night you felt ")
            assert e["status"] in ("single", "dating", "cohabiting")


def test_each_line_is_standalone_json(mock_run):
    out, _ = mock_run
    with open(out / "events.jsonl") as f:
        for line in f:
            json.loads(line)
