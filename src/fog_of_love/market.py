"""The market: Concordia's MarketPlace clearing house, driven directly (no game-master engine).

Buyers' bids come from the morning shopping list. Sellers are scripted: one per good, production cost = list
price, asking the list price every round with fresh stock each day. Three rounds a day: an unfilled bid is
resubmitted next round at 1.15x its price (capped by cash). Trades clear at the midpoint of bid and ask, as in
`MarketPlace._clear_auction`, whose trade_history / curve_history / price history we keep.
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


def seller_name(good_id: str) -> str:
    return f"Seller of {good_id}"


class Market:
    def __init__(self, agents: dict[str, AgentState]) -> None:
        self.goods = [marketplace.Good(category=g["category"], quality=g["tier"], id=g["id"], price=g["list_price"],
                                       inventory=goods.SELLER_STOCK) for g in goods.GOODS]
        buyers = [marketplace.MarketplaceAgent(name=n, role="consumer", cash=a.cash, inventory=dict(a.inventory), queue=[])
                  for n, a in agents.items()]
        sellers = [marketplace.MarketplaceAgent(name=seller_name(g.id), role="producer", cash=0.0,
                                                inventory={g.id: goods.SELLER_STOCK}, queue=[]) for g in self.goods]
        self.mp = marketplace.MarketPlace(
            acting_player_names=[b.name for b in buyers] + [s.name for s in sellers],
            agents=buyers + sellers, goods=self.goods, market_type="clearing_house",
        )
        self.round_counter = 0

    def run_day(self, day: int, agents: dict[str, AgentState], bids: dict[str, list[dict[str, Any]]],
                log: EventLog) -> dict[str, list[str]]:
        """Runs ROUNDS clearing rounds; mutates agents' cash/inventory; returns per-agent outcome messages."""
        mp = self.mp
        for name, a in agents.items():
            m = mp._agents[name]
            m.cash, m.inventory, m.queue = a.cash, dict(a.inventory), []
        for g in self.goods:
            s = mp._agents[seller_name(g.id)]
            s.inventory, s.cash, s.queue = {g.id: goods.SELLER_STOCK}, 0.0, []
        pending: dict[str, list[dict[str, Any]]] = {n: [dict(b) for b in bl] for n, bl in bids.items()}
        messages: dict[str, list[str]] = {n: [] for n in agents}
        for r in range(ROUNDS):
            mp._state["round"] = self.round_counter
            for ob in mp._orderbooks.values():
                ob.clear()
            for g in self.goods:
                mp._orderbooks[g.id].append(marketplace.Order(agent_id=seller_name(g.id), good=g, price=g.price,
                                                              qty=goods.SELLER_STOCK, side="ask", round=r))
                log.emit("market", "market.order", day, name=seller_name(g.id), side="ask", good=g.id,
                         price=float(g.price), qty=goods.SELLER_STOCK, round=r)
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
                if math.isnan(price):
                    price = float(g.price)
                prices[g.id] = round(float(price), 2)
                log.emit("market", "market.clear", day, good=g.id, price=prices[g.id], filled=fills, round=r)
                for f in fills:
                    agents[f["buyer"]].add_item(g.id, f["qty"])
                    for b in pending.get(f["buyer"], []):
                        if b["good"] == g.id and b["qty"] > 0:
                            b["qty"] = max(0, b["qty"] - f["qty"])
                            break
            mp.history.append(prices)
            log.emit("market", "market.prices", day, round=r, prices=prices)
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
        return messages
