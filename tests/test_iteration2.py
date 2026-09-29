"""Iteration 2: dating-pair hug overlap, app hidden while dating, morning propose_move_in, auto meal purchase,
invite accepted with zero home hours."""

from fog_of_love import app, goods
from fog_of_love.events import read_events
from fog_of_love.world import MIN_VISIT_HOME_HOURS, World, ensure_home_hours


def make_world(tmp_path, n=4, days=3, seed=5):
    return World(out_dir=tmp_path / "w", model_name="mock", num_agents=n, num_days=days, seed=seed)


def names(world):
    return list(world.agents)


def hours(work, games, home, eat):
    return {"work": work, "games": games, "home": home, "eat": eat}


def decision(**obj):
    return {"obj": obj, "bids": [], "raw": "", "fallback": False}


def test_dating_pair_shares_overlapping_home_hours(tmp_path):
    world = make_world(tmp_path)
    a, b, c, _ = (world.agents[n] for n in names(world))
    world.set_relationship(1, a, b, "dating", "date")
    assert a.status == b.status == "dating" and a.partner == b.name and a.partner_since == 1
    a.hours, b.hours, c.hours = hours(8, 2, 5, 1), hours(10, 3, 3, 0), hours(8, 2, 5, 1)
    for x in world.agents.values():
        if not x.hours:
            x.hours = hours(16, 0, 0, 0)
    world.night(1)
    night = {e["name"]: e for e in world.log.events if e["type"] == "night.state"}
    assert night[a.name]["hug_hours"] == 3.0 and night[b.name]["hug_hours"] == 3.0  # min(5, 3)
    assert night[a.name]["m"]["hugs"] == 0.75
    assert night[c.name]["hug_hours"] == 0.0  # single without a visit
    # cohabiting: the same overlap, plus shared goods
    world.set_relationship(2, a, b, "cohabiting", "morning")
    assert a.partner_since == 1  # kept from the dating start
    b.add_item("Kart Rush", 1)
    a.games.clear()
    a.hours, b.hours = hours(6, 4, 4, 2), hours(6, 0, 6, 2)
    world.night(2)
    night2 = [e for e in world.log.events if e["type"] == "night.state" and e["day"] == 2]
    by = {e["name"]: e for e in night2}
    assert by[a.name]["hug_hours"] == 4.0 and by[a.name]["fun_points"] > 0  # played the partner's game
    assert b.games["Kart Rush"] < 1.0  # the decay landed on the owner's copy


def test_app_hidden_while_dating(tmp_path):
    world = make_world(tmp_path, n=5)
    a, b = (world.agents[n] for n in names(world)[:2])
    world.set_relationship(1, a, b, "dating", "date")
    assert not app.eligible(a) and not app.eligible(b)
    dates = world.app_phase(2)
    profiles = {e["name"] for e in world.log.events if e["type"] == "app.profile"}
    swipers = {e["name"] for e in world.log.events if e["type"] == "app.swipe"}
    targets = {e["target"] for e in world.log.events if e["type"] == "app.swipe"}
    assert a.name not in profiles and b.name not in profiles
    assert a.name not in swipers and b.name not in swipers
    assert a.name not in targets and b.name not in targets
    assert tuple(sorted((a.name, b.name))) in {tuple(sorted(p)) for p in dates}  # the standing date
    # after a morning breakup the app is visible again
    world.resolve_breakups(3, {a.name: decision(breakup=True)})
    assert a.status == b.status == "single" and app.eligible(a)


def test_morning_propose_move_in_path(tmp_path):
    world = make_world(tmp_path)
    a, b = (world.agents[n] for n in names(world)[:2])
    world.set_relationship(1, a, b, "dating", "date")
    # day 2: A proposes in the morning; B did not -> pending on B
    d2 = {a.name: decision(propose_move_in=True), b.name: decision()}
    world.resolve_move_ins(2, d2)
    world.resolve_proposals(2, d2)
    assert a.status == "dating" and b.pending_move_in == a.name
    # day 3: B accepts through the existing accept_move_in path
    d3 = {a.name: decision(), b.name: decision(accept_move_in=True)}
    world.resolve_move_ins(3, d3)
    assert a.status == b.status == "cohabiting" and b.pending_move_in is None
    changes = [e for e in world.log.events if e["type"] == "relationship.change"]
    assert changes[-1]["from"] == "dating" and changes[-1]["to"] == "cohabiting" and changes[-1]["day"] == 3
    # both proposing the same morning -> cohabiting at once
    c, d = (world.agents[n] for n in names(world)[2:4])
    world.set_relationship(3, c, d, "dating", "date")
    both = {c.name: decision(propose_move_in=True), d.name: decision(propose_move_in=True)}
    world.resolve_move_ins(4, both)
    world.resolve_proposals(4, both)
    assert c.status == d.status == "cohabiting"
    # a single saying propose_move_in is ignored
    e = world.agents[names(world)[0]]
    world.end_relationship(5, a, b, "morning")
    world.resolve_proposals(5, {a.name: decision(propose_move_in=True)})
    assert a.status == "single"


def test_auto_meal_purchase_covers_scheduled_eating(tmp_path):
    world = make_world(tmp_path)
    a = world.agents[names(world)[0]]
    a.inventory = {a.wearing: 1}
    a.cash = 100.0
    for x in world.agents.values():
        x.hours = hours(14, 0, 0, 2)
    cheapest = goods.cheapest_meal()
    price = goods.list_price(cheapest)
    msgs = world.market.run_day(1, world.agents, {n: [] for n in world.agents}, world.log, {n: 2 for n in world.agents})
    assert a.meals == 2 and a.cash == 100.0 - 2 * price
    assert any("automatically" in m for m in msgs[a.name])
    orders = [e for e in world.log.events if e["type"] == "market.order" and e.get("auto") and e["name"] == a.name]
    clears = [e for e in world.log.events if e["type"] == "market.clear" and e.get("auto")
              and any(f["buyer"] == a.name for f in e["filled"])]
    assert len(orders) == 1 and orders[0]["side"] == "bid" and orders[0]["good"] == cheapest and orders[0]["qty"] == 2
    assert len(clears) == 1 and clears[0]["filled"][0]["qty"] == 2 and clears[0]["price"] == price
    # only the shortfall is bought, and never beyond cash
    a.cash = price * 0.5
    a.eat(2)
    a.add_item(cheapest, 1)
    msgs = world.market.run_day(2, world.agents, {n: [] for n in world.agents}, world.log, {n: 2 for n in world.agents})
    assert a.meals == 1 and any("cannot afford" in m for m in msgs[a.name])
    world.night(2)
    night = next(e for e in world.log.events if e["type"] == "night.state" and e["name"] == a.name)
    assert night["meals_eaten"] == 1


def test_invite_accepted_with_zero_home_hours_gets_two_hug_hours(tmp_path):
    assert ensure_home_hours(hours(14, 2, 0, 0), 2) == hours(12, 2, 2, 0)
    assert ensure_home_hours(hours(0, 1, 0, 2), 2) == hours(0, 0, 1, 2)  # only what work/games can give
    assert ensure_home_hours(hours(8, 2, 4, 2), 2) == hours(8, 2, 4, 2)
    world = World(out_dir=tmp_path / "v", model_name="mock", num_agents=3, num_days=3, seed=11)
    guest, host, other = (world.agents[n] for n in names(world))
    guest.pending_invites = [host.name]

    class Canned:
        def __init__(self, answers):
            self.answers = answers

        def __call__(self, day, a):
            return {"obj": self.answers[a.name], "raw": "canned", "fallback": False}

    world.decide = Canned({
        guest.name: {"hours": hours(14, 2, 0, 0), "accept_invite": host.name, "shopping": []},
        host.name: {"hours": hours(16, 0, 0, 0), "shopping": []},
        other.name: {"hours": hours(8, 2, 4, 2), "shopping": []},
    })
    world.morning(2)
    assert guest.visit_with == host.name and host.visit_with == guest.name
    assert guest.hours == hours(12, 2, 2, 0) and host.hours == hours(14, 0, 2, 0)
    allocs = {e["name"]: e for e in world.log.events if e["type"] == "morning.allocation"}
    assert allocs[guest.name]["hours"]["home"] == MIN_VISIT_HOME_HOURS and allocs[guest.name]["home_hours_adjusted"]
    assert allocs[host.name]["home_hours_adjusted"] and not allocs[other.name]["home_hours_adjusted"]
    assert sum(allocs[guest.name]["hours"].values()) == 16
    invites = [e for e in world.log.events if e["type"] == "visit.invite"]
    posts = [e for e in world.log.events if e["type"] == "gossip.post"]
    assert invites == [dict(invites[0])] and invites[0]["accepted"] and invites[0]["name"] == host.name
    assert len(posts) == 1 and posts[0]["text"] == f"{guest.name} was seen leaving {host.name}'s place late."
    assert posts[0]["about"] == [guest.name, host.name] and posts[0]["phase"] == "visit"
    world.market_phase(2)
    world.night(2)
    night = {e["name"]: e for e in world.log.events if e["type"] == "night.state"}
    assert night[guest.name]["hug_hours"] == 2.0 and night[host.name]["hug_hours"] == 2.0
    assert night[guest.name]["m"]["hugs"] == 0.5
    world.log.close()
    assert all(e["type"] for e in read_events(world.out / "events.jsonl"))
