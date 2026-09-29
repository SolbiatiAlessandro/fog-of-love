"""Iteration 3: finite stock, adaptive sellers, carry-over cap, price elasticity."""

import math

import pytest

from fog_of_love import goods
from fog_of_love.market import adjust_ask, replenish
from fog_of_love.metrics import Data, log_log_slope, m11_price_dynamics
from fog_of_love.world import World


def make_world(tmp_path, n=6):
    return World(out_dir=tmp_path / "w", model_name="mock", num_agents=n, num_days=3, seed=3)


def names(world):
    return list(world.agents)


def events(world, type_, **match):
    return [e for e in world.log.events if e["type"] == type_ and all(e.get(k) == v for k, v in match.items())]


def test_ask_adjustment_up_down_and_cost_floor():
    cost = goods.production_cost("Linen Shirt")
    assert cost == pytest.approx(54.0)
    assert adjust_ask(90.0, sold=6, stock=6, cost=cost) == pytest.approx(103.5)  # sold out: +15%
    assert adjust_ask(103.5, sold=7, stock=6, cost=cost) == pytest.approx(round(103.5 * 1.15, 2))  # fills >= stock
    assert adjust_ask(90.0, sold=1, stock=6, cost=cost) == pytest.approx(81.0)  # under a third: -10%
    assert adjust_ask(90.0, sold=0, stock=6, cost=cost) == pytest.approx(81.0)
    assert adjust_ask(90.0, sold=2, stock=6, cost=cost) == pytest.approx(90.0)  # exactly a third: unchanged
    assert adjust_ask(90.0, sold=3, stock=6, cost=cost) == pytest.approx(90.0)
    ask = 90.0
    for _ in range(12):
        ask = adjust_ask(ask, sold=0, stock=6, cost=cost)
        assert ask >= cost
    assert ask == pytest.approx(cost)  # never below production cost
    assert adjust_ask(1500.0, sold=0, stock=0, cost=900.0) == pytest.approx(1350.0)  # nothing on offer: lower


def test_replenish_and_carry_over_cap():
    p, cap = goods.production("Designer Coat"), goods.stock_cap("Designer Coat")
    assert (p, cap) == (2, 6)
    assert replenish(0, p, cap) == 2
    assert replenish(2, p, cap) == 4  # unsold High items do not vanish
    assert replenish(4, p, cap) == 6
    assert replenish(6, p, cap) == 6  # capped at 3 x production
    assert replenish(100, p, cap) == 6
    assert goods.production("Food Truck Meal") == 40 and goods.production("Star Farmer") == 8
    assert goods.production("Thrift Hoodie") == 20 and goods.production("Bistro Dinner") == 12
    assert goods.production("Tasting Menu") == 3 and goods.production("Linen Shirt") == 6


def test_stock_depletion_and_seller_reaction(tmp_path):
    world = make_world(tmp_path)
    ns = names(world)
    for a in world.agents.values():
        a.cash = 10_000.0
        a.hours = {"work": 8, "games": 2, "home": 4, "eat": 2}
    # Six agents each bid for 2 Linen Shirts (production 6): only 6 units can clear, highest bidders first.
    bids = {n: [{"good": "Linen Shirt", "price": 90.0 + i, "qty": 2}] for i, n in enumerate(ns)}
    world.market.run_day(1, world.agents, bids, world.log, {n: 0 for n in ns})
    bought = sum(a.inventory.get("Linen Shirt", 0) for a in world.agents.values())
    assert bought == 6
    assert world.agents[ns[-1]].inventory.get("Linen Shirt", 0) == 2  # the highest bidder is served
    assert world.agents[ns[0]].inventory.get("Linen Shirt", 0) == 0  # the lowest bidder is not
    asks = events(world, "market.order", side="ask", good="Linen Shirt")
    assert [e["qty"] for e in asks] == [6, 0, 0]  # the ask carries the remaining stock each round
    assert all(e["stock"] == 6 for e in asks)
    last = events(world, "market.prices", day=1)[-1]
    assert last["sold"]["Linen Shirt"] == 6 and last["stock"]["Linen Shirt"] == 0
    assert last["next_asks"]["Linen Shirt"] == pytest.approx(103.5)  # sold out -> +15%
    assert last["asks"]["Linen Shirt"] == pytest.approx(90.0)  # today's ask, not tomorrow's
    assert last["next_asks"]["Leather Jacket"] == pytest.approx(81.0)  # no sales -> -10%
    assert world.market.ask["Linen Shirt"] == pytest.approx(103.5)
    # Unfilled bids rebid at 1.15x on the later rounds, against an empty shelf, and stay unfilled.
    rebids = events(world, "market.order", side="bid", name=ns[0], good="Linen Shirt")
    assert [e["round"] for e in rebids] == [0, 1, 2]
    assert rebids[1]["price"] == pytest.approx(round(90.0 * 1.15, 2))
    # Day 2: fresh production only (nothing carried over), the raised ask is the price buyers face.
    # Rounds without a trade report the ask, not Concordia's phantom midpoint against an empty shelf.
    assert [e["price"] for e in events(world, "market.clear", good="Linen Shirt", day=1)][1:] == [90.0, 90.0]
    assert "Linen Shirt (Clothing Mid): last price 90.00, asking 103.50, 6 units" in world.market.summary()
    assert "Leather Jacket (Clothing Mid): last price 90.00, asking 81.00, 12 units" in world.market.summary()  # 6 + 6
    world.market.run_day(2, world.agents, {n: [] for n in ns}, world.log, {n: 0 for n in ns})
    last2 = events(world, "market.prices", day=2)[-1]
    assert last2["day_stock"]["Linen Shirt"] == 6 and last2["day_stock"]["Leather Jacket"] == 12
    # Carry-over reaches the cap after enough quiet days.
    for day in range(3, 8):
        world.market.run_day(day, world.agents, {n: [] for n in ns}, world.log, {n: 0 for n in ns})
    world.market.open_day()
    assert world.market.stock["Leather Jacket"] == goods.stock_cap("Leather Jacket") == 18
    assert world.market.ask["Leather Jacket"] == pytest.approx(goods.production_cost("Leather Jacket"))  # floored


def test_clearing_price_moves_with_bids_and_ask(tmp_path):
    world = make_world(tmp_path)
    ns = names(world)
    for a in world.agents.values():
        a.cash = 10_000.0
    world.market.ask["Star Farmer"] = 24.0
    bids = {ns[0]: [{"good": "Star Farmer", "price": 30.0, "qty": 1}]}
    bids.update({n: [] for n in ns[1:]})
    world.market.run_day(1, world.agents, bids, world.log, {n: 0 for n in ns})
    clear = events(world, "market.clear", good="Star Farmer", round=0)[0]
    assert clear["price"] == pytest.approx(27.0)  # midpoint of bid 30 and ask 24
    assert clear["filled"][0]["price"] == pytest.approx(27.0) and clear["ask"] == pytest.approx(24.0)
    assert world.agents[ns[0]].cash == pytest.approx(10_000.0 - 27.0)
    # A bid below the ask does not clear; the round's price is the ask.
    world.market.ask["Kart Rush"] = 30.0
    bids = {ns[1]: [{"good": "Kart Rush", "price": 20.0, "qty": 1}]}
    bids.update({n: [] for n in ns if n != ns[1]})
    world.market.run_day(2, world.agents, bids, world.log, {n: 0 for n in ns})
    clears = events(world, "market.clear", good="Kart Rush", day=2)
    assert [c["price"] for c in clears] == [30.0, 30.0, 30.0] and all(not c["filled"] for c in clears)
    assert "Kart Rush" not in world.agents[ns[1]].inventory


def test_elasticity_on_fixture():
    prices = [90.0, 100.0, 110.0, 121.0, 133.0, 146.0]
    quantities = [p ** -1.5 * 1e4 for p in prices]  # constant elasticity -1.5
    r = log_log_slope(prices, quantities)
    assert r["status"] == "ok" and r["n"] == 6 and r["slope"] == pytest.approx(-1.5, abs=1e-6)
    veblen = log_log_slope(prices, [p ** 0.7 for p in prices])
    assert veblen["slope"] == pytest.approx(0.7, abs=1e-6)
    assert log_log_slope(prices[:4], quantities[:4]) == {"slope": None, "n": 4, "status": "not estimable"}
    flat = log_log_slope([90.0] * 6, quantities)
    assert flat["slope"] is None and "no price variation" in flat["status"]
    assert log_log_slope(prices, [0.0] * 6)["n"] == 0  # days without bids drop out


def test_metric_11_on_a_synthetic_run():
    goods_list = [{"id": g["id"], "category": g["category"], "tier": g["tier"], "list_price": g["list_price"]} for g in goods.GOODS]
    ev = [{"t": 1, "day": 0, "phase": "setup", "type": "setup.world", "agents": [{"name": "A"}, {"name": "B"}],
           "goods": goods_list, "days": 6, "seed": 1}]
    ask = 90.0
    t = 2
    for day in range(1, 7):
        qty = max(1, round(20 * (ask / 90.0) ** -2))  # elastic demand
        ev.append({"t": t, "day": day, "phase": "market", "type": "market.order", "name": "Seller of Linen Shirt",
                   "side": "ask", "good": "Linen Shirt", "price": ask, "qty": 6, "round": 0}); t += 1
        ev.append({"t": t, "day": day, "phase": "market", "type": "market.order", "name": "A", "side": "bid",
                   "good": "Linen Shirt", "price": ask, "qty": qty, "round": 0}); t += 1
        ev.append({"t": t, "day": day, "phase": "market", "type": "market.clear", "good": "Linen Shirt", "price": ask,
                   "filled": [{"buyer": "A", "seller": "Seller of Linen Shirt", "qty": min(qty, 6), "price": ask}], "round": 0}); t += 1
        ev.append({"t": t, "day": day, "phase": "market", "type": "market.clear", "good": "Food Truck Meal", "price": 2.0,
                   "filled": [{"buyer": "A", "seller": "s", "qty": 1, "price": 2.0}], "round": 3, "auto": True}); t += 1
        ask = round(ask * (1.15 if day % 2 else 0.9), 2)
    ev.append({"t": t, "day": 6, "phase": "night", "type": "night.state", "name": "A", "status": "single", "m": {}, "partner": None})
    m = m11_price_dynamics(Data(ev))
    ls = m["goods"]["Linen Shirt"]
    assert ls["units_sold"] == sum(min(max(1, round(20 * (p / 90.0) ** -2)), 6) for p in [90.0, 103.5, 93.15, 107.12, 96.41, 110.87])
    assert ls["clearing_min"] == 90.0 and ls["clearing_max"] == 110.87 and ls["clearing_last"] == 110.87
    assert m["goods"]["Food Truck Meal"]["units_sold"] == 0  # auto meals are not market trades
    e = m["elasticity"]["Linen Shirt"]
    assert e["status"] == "ok" and e["n"] == 6 and e["slope"] < -1.0
    assert m["elasticity"]["Designer Coat"]["status"] == "not estimable"
    assert m["elasticity"]["High clothing (pooled)"]["n"] == 0
    assert m["high_clothing_units_sold"] == 0 and "Linen Shirt" in m["goods_with_price_movement"]
    assert not math.isnan(e["slope"])
