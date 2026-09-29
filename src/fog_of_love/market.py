"""The market: Concordia's MarketPlace clearing house, driven directly (no game-master engine).

Buyers' bids come from the morning shopping list. Sellers are scripted, one per good, with finite stock: each
morning the seller receives its daily production (`goods.production`), unsold units carrying over up to
`goods.stock_cap`. The ask starts at the list price and adapts after each day: sold out -> +15%; fewer than a
third of the day's stock sold -> -10%, never below production cost (0.6 x list). Three rounds a day: an unfilled
bid is resubmitted next round at 1.15x its price (capped by cash). Trades match the highest bids first against
the ask and clear at the midpoint of bid and ask, as in `MarketPlace._clear_auction`, whose trade_history /
curve_history / price history we keep; the logged clearing price is that of the marginal (last) trade, or the
ask when nothing traded.
"""

from __future__ import annotations

import math
from typing import Any

from concordia.contrib.components.game_master import marketplace

from fog_of_love import goods
from fog_of_love.agents import AgentState
from fog_of_love.events import EventLog

ROUNDS = 3
REBID_FACTOR = 1.15
ASK_UP = 1.15  # sold out
ASK_DOWN = 0.90  # fewer than a third sold
SLOW_SALES_FRACTION = 1 / 3


def seller_name(good_id: str) -> str:
    return f"Seller of {good_id}"


def adjust_ask(ask: float, sold: int, stock: int, cost: float) -> float:
    """The seller's next ask: +15% if the day's stock sold out, -10% (floored at cost) if under a third sold."""
    if stock > 0 and sold >= stock:
        return round(ask * ASK_UP, 2)
    if stock <= 0 or sold < SLOW_SALES_FRACTION * stock:
        return round(max(cost, ask * ASK_DOWN), 2)
    return round(ask, 2)


def replenish(stock: int, production: int, cap: int) -> int:
    """Morning stock: the carry-over plus today's production, capped."""
    return min(cap, max(0, stock) + production)


class Market:
    def __init__(self, agents: dict[str, AgentState]) -> None:
        self.goods = [marketplace.Good(category=g["category"], quality=g["tier"], id=g["id"], price=g["list_price"],
                                       inventory=0) for g in goods.GOODS]
        buyers = [marketplace.MarketplaceAgent(name=n, role="consumer", cash=a.cash, inventory=dict(a.inventory), queue=[])
                  for n, a in agents.items()]
        sellers = [marketplace.MarketplaceAgent(name=seller_name(g.id), role="producer", cash=0.0,
                                                inventory={g.id: 0}, queue=[]) for g in self.goods]
        self.mp = marketplace.MarketPlace(
            acting_player_names=[b.name for b in buyers] + [s.name for s in sellers],
            agents=buyers + sellers, goods=self.goods, market_type="clearing_house",
        )
        self.round_counter = 0
        self.ask: dict[str, float] = {g.id: float(g.price) for g in self.goods}
        self.stock: dict[str, int] = {g.id: 0 for g in self.goods}  # unsold units carried into the next morning
        self.last_price: dict[str, float] = {g.id: float(g.price) for g in self.goods}  # last round's clearing price
        self.day_open = False

    # ---- observation helpers ----------------------------------------------------------------------

    def open_day(self) -> None:
        """Replenish every seller's stock for the day (idempotent until `run_day` closes the day)."""
        if self.day_open:
            return
        for g in self.goods:
            self.stock[g.id] = replenish(self.stock[g.id], goods.production(g.id), goods.stock_cap(g.id))
        self.day_open = True

    def summary(self) -> str:
        """One line per good for the morning observation: last clearing price and units on offer today."""
        self.open_day()
        return "; ".join(f"{g.id} ({g.category} {g.quality}): last price {self.last_price[g.id]:.2f}, asking "
                         f"{self.ask[g.id]:.2f}, {self.stock[g.id]} units" for g in self.goods)

    # ---- the day ---------------------------------------------------------------------------------

    def run_day(self, day: int, agents: dict[str, AgentState], bids: dict[str, list[dict[str, Any]]],
                log: EventLog, eat_hours: dict[str, int] | None = None) -> dict[str, list[str]]:
        """Runs ROUNDS clearing rounds; mutates agents' cash/inventory; returns per-agent outcome messages.
        Then, for every agent whose scheduled eating hours exceed the meals it owns, auto-buys the cheapest meal
        at list price for the shortfall (as far as cash allows), logged as an `auto` bid and fill. Finally each
        seller adjusts its ask for tomorrow from today's sales."""
        mp = self.mp
        self.open_day()
        for name, a in agents.items():
            m = mp._agents[name]
            m.cash, m.inventory, m.queue = a.cash, dict(a.inventory), []
        day_stock = dict(self.stock)
        for g in self.goods:
            s = mp._agents[seller_name(g.id)]
            s.inventory, s.cash, s.queue = {g.id: day_stock[g.id]}, 0.0, []
        pending: dict[str, list[dict[str, Any]]] = {n: [dict(b) for b in bl] for n, bl in bids.items()}
        messages: dict[str, list[str]] = {n: [] for n in agents}
        for r in range(ROUNDS):
            mp._state["round"] = self.round_counter
            for ob in mp._orderbooks.values():
                ob.clear()
            for g in self.goods:
                remaining = int(mp._agents[seller_name(g.id)].inventory.get(g.id, 0))
                mp._orderbooks[g.id].append(marketplace.Order(agent_id=seller_name(g.id), good=g, price=self.ask[g.id],
                                                              qty=remaining, side="ask", round=r))
                log.emit("market", "market.order", day, name=seller_name(g.id), side="ask", good=g.id,
                         price=self.ask[g.id], qty=remaining, round=r, stock=day_stock[g.id])
            for name, bl in pending.items():
                buyer = mp._agents[name]
                for b in bl:
                    if b["qty"] <= 0:
                        continue
                    price = min(float(b["price"]), buyer.cash / max(1, b["qty"])) if buyer.cash > 0 else 0.0
                    price = round(max(0.01, price), 2)
                    b["price"] = price
                    mp._orderbooks[b["good"]].append(marketplace.Order(agent_id=name, good=mp._goods[b["good"]],
                                                                       price=price, qty=int(b["qty"]), side="bid", round=r))
                    log.emit("market", "market.order", day, name=name, side="bid", good=b["good"], price=price,
                             qty=int(b["qty"]), round=r)
            prices: dict[str, float] = {}
            before = len(mp.trade_history)
            for g in self.goods:
                price, _completed, _traded = mp._clear_auction(g.id)
                fills = [{"buyer": t["agent"], "seller": seller_name(g.id), "qty": int(t["transaction_qty"]),
                          "price": round(float(t["transaction_price_avg"]), 2)}
                         for t in mp.trade_history[before:] if t["good"] == g.id and t["side"] == "bid"
                         and t["transaction_qty"] > 0]
                if math.isnan(price) or not fills:
                    # Concordia returns a bid/ask midpoint even when the shelf is empty; without a trade the
                    # round's price is the ask.
                    price = self.ask[g.id]
                prices[g.id] = round(float(price), 2)
                remaining = int(mp._agents[seller_name(g.id)].inventory.get(g.id, 0))
                log.emit("market", "market.clear", day, good=g.id, price=prices[g.id], filled=fills, round=r,
                         ask=self.ask[g.id], remaining=remaining)
                for f in fills:
                    agents[f["buyer"]].add_item(g.id, f["qty"])
                    for b in pending.get(f["buyer"], []):
                        if b["good"] == g.id and b["qty"] > 0:
                            b["qty"] = max(0, b["qty"] - f["qty"])
                            break
            mp.history.append(prices)
            self.last_price = dict(prices)
            asks_today = dict(self.ask)
            stock_now = {g.id: int(mp._agents[seller_name(g.id)].inventory.get(g.id, 0)) for g in self.goods}
            extra: dict[str, Any] = {}
            if r == ROUNDS - 1:
                extra = self.close_day(day_stock)  # sellers set tomorrow's ask from today's sales
            log.emit("market", "market.prices", day, round=r, prices=prices, asks=asks_today, stock=stock_now, **extra)
            self.round_counter += 1
            for name in agents:
                agents[name].cash = float(mp._agents[name].cash)
                q = mp._agents[name].queue
                messages[name].extend(q)
                q.clear()
            for name, bl in pending.items():
                for b in bl:
                    if b["qty"] > 0:
                        b["price"] = round(b["price"] * REBID_FACTOR, 2)
        for name, a in agents.items():
            msg = self.auto_buy_meals(day, a, int((eat_hours or {}).get(name, 0)), log)
            if msg:
                messages[name].append(msg)
        return messages

    def close_day(self, day_stock: dict[str, int]) -> dict[str, Any]:
        """Carry the unsold stock over and let each seller set tomorrow's ask from today's sales. Returns the
        optional fields logged on the day's last `market.prices` event."""
        sold: dict[str, int] = {}
        next_asks: dict[str, float] = {}
        for g in self.goods:
            remaining = int(self.mp._agents[seller_name(g.id)].inventory.get(g.id, 0))
            sold[g.id] = day_stock[g.id] - remaining
            next_asks[g.id] = adjust_ask(self.ask[g.id], sold[g.id], day_stock[g.id], goods.production_cost(g.id))
            self.ask[g.id] = next_asks[g.id]
            self.stock[g.id] = remaining
        self.day_open = False
        return {"day_stock": dict(day_stock), "sold": sold, "next_asks": next_asks}

    @staticmethod
    def auto_buy_meals(day: int, a: AgentState, eat_hours: int, log: EventLog) -> str | None:
        """The world buys the cheapest meal at list price for (eat hours - meals owned), from the agent's cash.
        This is the restaurant's guarantee, outside the sellers' stock."""
        shortfall = max(0, eat_hours - a.meals)
        if shortfall <= 0:
            return None
        gid = goods.cheapest_meal()
        price = goods.list_price(gid)
        qty = min(shortfall, int(a.cash // price)) if price > 0 else shortfall
        if qty <= 0:
            return f"You scheduled {eat_hours}h of eating but own {a.meals} meals and cannot afford more."
        a.cash = round(a.cash - qty * price, 2)
        a.add_item(gid, qty)
        log.emit("market", "market.order", day, name=a.name, side="bid", good=gid, price=float(price), qty=qty,
                 round=ROUNDS, auto=True)
        log.emit("market", "market.clear", day, good=gid, price=float(price), round=ROUNDS, auto=True,
                 filled=[{"buyer": a.name, "seller": seller_name(gid), "qty": qty, "price": float(price)}])
        return (f"You scheduled {eat_hours}h of eating with only {a.meals - qty} meals in stock, so the restaurant "
                f"charged you for {qty} {gid} ({price:.0f} each) automatically.")
