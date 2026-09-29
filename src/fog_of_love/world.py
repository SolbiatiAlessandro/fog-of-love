"""The day loop: morning decision -> market -> dating app -> dates -> visits -> night. Everything but the model
calls is plain Python; the model is reached only through the Concordia entities' `act`."""

from __future__ import annotations

import json
import random
import time
from concurrent import futures
from pathlib import Path
from typing import Any

import numpy as np

from fog_of_love import goods, prompts
from fog_of_love.agents import AgentState, ask_json, build_entity, persona_summary, pick_names, starting_cash
from fog_of_love.app import run_app
from fog_of_love.dates import run_date
from fog_of_love.events import EventLog
from fog_of_love.gossip import GossipBoard
from fog_of_love.llm import make_model
from fog_of_love.market import Market
from fog_of_love.needs import NEEDS, THERAPY_COST, WAGE, Needs, met_fractions, play_games

DAY_HOURS = 16
DEFAULT_HOURS = {"work": 8, "games": 2, "home": 4, "eat": 2}
DEFAULT_SHOPPING = [{"good": "Food Truck Meal", "price": 2.5, "qty": 2}]


MIN_VISIT_HOME_HOURS = 2


class BudgetExceeded(RuntimeError):
    pass


def ensure_home_hours(hours: dict[str, int], minimum: int) -> dict[str, int]:
    """At least `minimum` home hours, taken from work first, then games (eat and the total are unchanged)."""
    h = dict(hours)
    need = minimum - h.get("home", 0)
    for k in ("work", "games"):
        if need <= 0:
            break
        take = min(need, h.get(k, 0))
        h[k] -= take
        h["home"] = h.get("home", 0) + take
        need -= take
    return h


def play_shared_games(mine: dict[str, float], partners: dict[str, float], hours: int) -> float:
    """Cohabiting: play the best game of the shared collection each hour; yields decay on the owner's copy."""
    combined = {**partners, **mine}
    points = play_games(combined, hours)
    for g, y in combined.items():
        (mine if g in mine else partners)[g] = y
    return points


def normalize_hours(raw: Any, budget: int) -> dict[str, int]:
    """Ints >= 0, eat <= 2, the four buckets summing to `budget` (work/games/home scaled to fit)."""
    h = raw if isinstance(raw, dict) else {}

    def as_int(v: Any) -> int:
        try:
            return max(0, int(round(float(v))))
        except (TypeError, ValueError):
            return 0

    eat = min(2, as_int(h.get("eat", 0)))
    rest = budget - eat
    others = {k: as_int(h.get(k, 0)) for k in ("work", "games", "home")}
    s = sum(others.values())
    if s == 0:
        others = {"work": rest, "games": 0, "home": 0}
    elif s != rest:
        scaled = {k: int(round(v * rest / s)) for k, v in others.items()}
        diff = rest - sum(scaled.values())
        biggest = max(scaled, key=lambda k: scaled[k])
        scaled[biggest] = max(0, scaled[biggest] + diff)
        others = scaled
    return {**others, "eat": eat}


class World:
    def __init__(self, *, out_dir: str | Path, model_name: str, num_agents: int, num_days: int, seed: int,
                 budget_usd: float | None = None, api_key: str | None = None, concurrency: int = 8) -> None:
        self.out = Path(out_dir)
        self.out.mkdir(parents=True, exist_ok=True)
        self.model_name, self.num_days, self.seed, self.budget = model_name, num_days, seed, budget_usd
        self.rng = random.Random(seed)
        self.nrng = np.random.default_rng(seed)
        self.log = EventLog(self.out / "events.jsonl")
        call_log = None if model_name == "mock" else str(self.out / "calls.jsonl")
        self.model, self.hub = make_model(model_name, api_key=api_key, call_log_path=call_log, max_concurrency=concurrency)
        names = pick_names(num_agents, seed)
        cash = starting_cash(num_agents, seed)
        self.agents: dict[str, AgentState] = {}
        for name, c in zip(names, cash):
            wearing = self.rng.choice(goods.clothing_ids("Low"))
            self.agents[name] = AgentState(name=name, persona_summary=persona_summary(name), cash=c, wearing=wearing,
                                           inventory={wearing: 1}, needs=Needs.draw(self.nrng))
        self.entities = {name: build_entity(name, self.model) for name in names}
        self.market = Market(self.agents)
        self.gossip = GossipBoard()
        self.pool = futures.ThreadPoolExecutor(max_workers=max(1, concurrency))
        self.aborted: dict[str, Any] | None = None
        self.started = time.time()

    # ---- run ----------------------------------------------------------------------------------

    def run(self) -> dict[str, Any]:
        self.log.emit("setup", "setup.world", 0, agents=[a.public() for a in self.agents.values()],
                      goods=[{"id": g["id"], "category": g["category"], "tier": g["tier"], "list_price": g["list_price"]}
                             for g in goods.GOODS], days=self.num_days, seed=self.seed, model=self.model_name)
        for a in self.agents.values():
            self.log.emit("setup", "setup.needs", 0, name=a.name, w=a.needs.w, shadow=a.needs.shadow, b=a.needs.b)
        days_done = 0
        try:
            for day in range(1, self.num_days + 1):
                self.morning(day)
                self.check_budget(day, days_done)
                self.market_phase(day)
                dates = self.app_phase(day)
                self.check_budget(day, days_done)
                self.dates_phase(day, dates)
                self.check_budget(day, days_done)
                self.night(day)
                days_done = day
                self.log.emit("night", "run.cost", day, calls=self.calls(), usd=round(self.cost(), 4))
        except BudgetExceeded as err:
            self.aborted = {"reason": str(err), "day": days_done + 1}
        end = {"days": days_done, "total_usd": round(self.cost(), 4), "calls": self.calls(),
               "seconds": round(time.time() - self.started, 1)}
        if self.aborted:
            end["aborted"] = True
            end["abort_reason"] = self.aborted["reason"]
        self.log.emit("night", "run.end", days_done, **end)
        self.log.close()
        self.pool.shutdown(wait=True)
        summary = {"model": self.model_name, "num_agents": len(self.agents), "num_days": self.num_days, "seed": self.seed,
                   "budget_usd": self.budget, **end, "llm": self.hub.snapshot() if self.hub else None}
        (self.out / "run.json").write_text(json.dumps(summary, indent=2))
        if self.hub:
            self.hub.close()
        return summary

    def cost(self) -> float:
        return self.hub.cost_usd() if self.hub else 0.0

    def calls(self) -> int:
        return int(self.hub.stats["calls"]) if self.hub else 0

    def check_budget(self, day: int, days_done: int) -> None:
        if not self.hub or self.budget is None:
            return
        spent = self.cost()
        if spent > self.budget:
            raise BudgetExceeded(f"spent {spent:.4f} USD > budget {self.budget:.2f} on day {day}")
        if days_done >= 1:
            projected = spent / days_done * self.num_days
            if projected > self.budget:
                raise BudgetExceeded(f"projected {projected:.4f} USD for {self.num_days} days > budget {self.budget:.2f} "
                                     f"(spent {spent:.4f} after {days_done} days)")

    # ---- morning ------------------------------------------------------------------------------

    def morning_observation(self, day: int, a: AgentState) -> str:
        inv = ", ".join(f"{g} x{q}" for g, q in a.inventory.items()) or "nothing"
        games = ", ".join(f"{g} (fun yield {y:.2f})" for g, y in a.games.items()) or "none"
        parts = [
            f"Day {day} morning. Cash: {a.cash:.0f}. Wearing: {a.wearing} ({goods.tier(a.wearing)} tier). "
            f"Inventory: {inv}. Meals in stock: {a.meals} (each eating hour consumes one meal; meals are bought at "
            f"the restaurant through shopping and are the only food; if you schedule more eating hours than meals "
            f"you own, the restaurant charges you for the cheapest meal, {goods.cheapest_meal()} at "
            f"{goods.list_price(goods.cheapest_meal()):.0f}, for each missing one). Games owned: {games}. "
            f"Status: {a.status_line()}.",
        ]
        if a.status == "dating" and a.partner:
            parts.append(f"You are dating {a.partner}. Hours you both spend at home are spent together. You have a "
                         f"standing date with {a.partner} tonight. You do not see the dating app while dating; set "
                         f"breakup to true to end it and see the app again. Set propose_move_in to true to propose "
                         f"living together (you would share a home, meals and videogames).")
        elif a.status == "cohabiting" and a.partner:
            pa = self.agents[a.partner]
            pgames = ", ".join(f"{g} (fun yield {y:.2f})" for g, y in pa.games.items()) or "none"
            parts.append(f"You live with {a.partner}. Hours you both spend at home are spent together. You share "
                         f"meals and videogames: {a.partner} has {pa.meals} meals and these games: {pgames}. "
                         f"Set breakup to true to end it.")
        parts.append(a.last_sentence or "This is your first day in Love Town.")
        parts.append(self.gossip.render(day))
        inbox = []
        for inviter in a.pending_invites:
            inbox.append(f"{inviter} invited you to their home today (set accept_invite to \"{inviter}\" to go: you "
                         f"spend your home hours there and get hug time; a visit to anyone but your partner is posted "
                         f"on the gossip board).")
        if a.pending_move_in:
            inbox.append(f"{a.pending_move_in} proposed that you move in together (set accept_move_in to true to accept).")
        parts.append("Inbox: " + (" ".join(inbox) if inbox else "empty."))
        if a.status == "single":
            singles = [o.name for o in self.agents.values() if o.name != a.name and o.status == "single"]
            parts.append("Visits: you can invite another single home (set invite to their name; they decide tomorrow "
                         "morning). If you accept an invite you spend your home hours at their place tonight and get "
                         "hug time (at least 2 hours of your day are moved to home); every non-partner visit is "
                         "posted on the public gossip board.")
            if singles:
                parts.append("Singles you could invite home: " + ", ".join(singles) + ".")
        parts.append("Market list prices: " + goods.price_summary() + ".")
        return "\n".join(parts)

    def decide(self, day: int, a: AgentState) -> dict[str, Any]:
        ent = self.entities[a.name]
        ent.observe(f"[morning, day {day}] " + self.morning_observation(day, a))
        obj, raw = ask_json(ent, prompts.morning_call(day))
        fallback = obj is None
        obj = obj or {"hours": dict(DEFAULT_HOURS), "shopping": list(DEFAULT_SHOPPING)}
        return {"obj": obj, "raw": raw, "fallback": fallback}

    def morning(self, day: int) -> None:
        order = list(self.agents.values())
        results = list(self.pool.map(lambda a: self.decide(day, a), order))
        decisions: dict[str, dict[str, Any]] = {}
        pending_log: list[tuple[AgentState, dict[str, Any]]] = []
        for a, res in zip(order, results):
            obj = res["obj"]
            a.therapy = bool(obj.get("therapy")) and a.cash >= THERAPY_COST
            a.meditation = bool(obj.get("meditation")) and not a.therapy
            if obj.get("therapy") and not a.therapy:
                self.entities[a.name].observe("[morning] Therapy costs 60; not enough cash today.")
            budget = DAY_HOURS - (2 if (a.therapy or a.meditation) else 0)
            a.hours = normalize_hours(obj.get("hours"), budget)
            if a.therapy:
                a.cash -= THERAPY_COST
                a.needs.therapy()
            if a.meditation:
                a.needs.meditation()
            text = obj.get("profile_text")
            if isinstance(text, str) and text.strip():
                a.profile_text = text.strip()[:240]
            wear = goods.resolve_good(obj.get("wear")) if obj.get("wear") else None
            if wear and wear in a.owned_clothing():
                a.wearing = wear
            bids = []
            for b in obj.get("shopping") or []:
                if not isinstance(b, dict):
                    continue
                gid = goods.resolve_good(b.get("good"))
                if gid is None:
                    continue
                try:
                    price = float(b.get("price", goods.list_price(gid)))
                    qty = int(round(float(b.get("qty", 1))))
                except (TypeError, ValueError):
                    continue
                if qty > 0 and price > 0:
                    bids.append({"good": gid, "price": round(price, 2), "qty": min(qty, 10)})
            a.visit_with = None
            a.date_tonight = None
            a.home_hours_adjusted = False
            decisions[a.name] = {"obj": obj, "bids": bids, "raw": res["raw"], "fallback": res["fallback"]}
        # An accepted visit needs home hours on both sides: move at least 2 hours to home before logging.
        for name, d in decisions.items():
            a = self.agents[name]
            accepted = _name_or_none(d["obj"].get("accept_invite"))
            for inviter in a.pending_invites:
                host = self.agents.get(inviter)
                if self._visit_ok(a, host, accepted):
                    for x in (a, host):
                        if x.hours["home"] < MIN_VISIT_HOME_HOURS:
                            x.hours = ensure_home_hours(x.hours, MIN_VISIT_HOME_HOURS)
                            x.home_hours_adjusted = True
        for name, d in decisions.items():
            a, obj = self.agents[name], d["obj"]
            self.log.emit("morning", "morning.allocation", day, name=a.name, hours=a.hours, therapy=a.therapy,
                          meditation=a.meditation, invite=_name_or_none(obj.get("invite")), breakup=bool(obj.get("breakup")),
                          accept_invite=_name_or_none(obj.get("accept_invite")), accept_move_in=bool(obj.get("accept_move_in")),
                          propose_move_in=bool(obj.get("propose_move_in")), home_hours_adjusted=a.home_hours_adjusted,
                          shopping=d["bids"], wear=a.wearing, profile_text=a.profile_text, raw=str(d["raw"])[:600],
                          fallback=d["fallback"])
            if a.home_hours_adjusted:
                self.entities[a.name].observe(f"[morning] Because of tonight's visit, {a.name}'s day now includes "
                                              f"{a.hours['home']} home hours (work {a.hours['work']}h, games {a.hours['games']}h).")
        self.resolve_breakups(day, decisions)
        self.resolve_move_ins(day, decisions)
        self.resolve_proposals(day, decisions)
        self.resolve_visits(day, decisions)
        self._bids = {n: d["bids"] for n, d in decisions.items()}
        self._eat_hours = {n: self.agents[n].hours["eat"] for n in decisions}

    @staticmethod
    def _visit_ok(guest: AgentState, host: AgentState | None, accepted: str | None) -> bool:
        """An accepted invite is honoured unless either side now lives with someone (invites are sent by singles
        to singles, but a date on the evening in between may have made one of them a dating couple: the visit
        still happens, and if they are not each other's partner it is posted on the gossip board)."""
        return (host is not None and accepted is not None and _same(accepted, host.name) and guest.status != "cohabiting"
                and host.status != "cohabiting" and guest.visit_with is None and host.visit_with is None)

    def resolve_breakups(self, day: int, decisions: dict[str, dict[str, Any]]) -> None:
        for name, d in decisions.items():
            a = self.agents[name]
            if d["obj"].get("breakup") and a.partner:
                self.end_relationship(day, a, self.agents[a.partner], "morning")

    def resolve_move_ins(self, day: int, decisions: dict[str, dict[str, Any]]) -> None:
        for name, d in decisions.items():
            a = self.agents[name]
            proposer = a.pending_move_in
            a.pending_move_in = None
            if not proposer or a.partner != proposer or a.status != "dating":
                continue
            if d["obj"].get("accept_move_in") or d["obj"].get("propose_move_in"):
                self.set_relationship(day, a, self.agents[proposer], "cohabiting", "morning")
            else:
                self.entities[proposer].observe(f"[morning] {a.name} did not accept moving in together, for now.")

    def resolve_proposals(self, day: int, decisions: dict[str, dict[str, Any]]) -> None:
        """`propose_move_in: true` in the morning JSON of a dating agent: both propose the same morning ->
        cohabiting now; otherwise the partner gets it in tomorrow's inbox (the pending_move_in path)."""
        for name, d in decisions.items():
            a = self.agents[name]
            if not d["obj"].get("propose_move_in") or a.status != "dating" or not a.partner:
                continue
            b = self.agents[a.partner]
            if decisions.get(b.name, {}).get("obj", {}).get("propose_move_in"):
                self.set_relationship(day, a, b, "cohabiting", "morning")
                continue
            if b.pending_move_in != a.name:
                b.pending_move_in = a.name
                self.entities[b.name].observe(f"[morning] {a.name} proposed that you move in together; you can accept tomorrow morning.")
                self.entities[a.name].observe(f"[morning] You proposed to {b.name} that you move in together; {b.name} answers tomorrow morning.")

    def resolve_visits(self, day: int, decisions: dict[str, dict[str, Any]]) -> None:
        for name, d in decisions.items():
            a = self.agents[name]
            accepted = _name_or_none(d["obj"].get("accept_invite"))
            for inviter in a.pending_invites:
                host = self.agents.get(inviter)
                ok = self._visit_ok(a, host, accepted)
                self.log.emit("visit", "visit.invite", day, name=inviter, target=a.name, accepted=bool(ok))
                if ok:
                    a.visit_with, host.visit_with = host.name, a.name
                    if a.partner != host.name:  # every non-partner visit is public; partners' evenings are not
                        text = f"{a.name} was seen leaving {host.name}'s place late."
                        self.gossip.post(day, text, [a.name, host.name])
                        self.log.emit("visit", "gossip.post", day, text=text, about=[a.name, host.name])
                    self.entities[a.name].observe(f"[visit] {a.name} spends the home hours of day {day} at {host.name}'s place.")
                    self.entities[host.name].observe(f"[visit] {a.name} comes over to {host.name}'s place for the home hours of day {day}.")
            a.pending_invites = []
        for name, d in decisions.items():
            a = self.agents[name]
            target = _name_or_none(d["obj"].get("invite"))
            if target is None or a.status != "single":
                continue
            t = next((o for o in self.agents.values() if _same(target, o.name) and o.name != a.name), None)
            if t is not None and t.status == "single" and a.name not in t.pending_invites:
                t.pending_invites.append(a.name)

    # ---- relationships --------------------------------------------------------------------------

    def set_relationship(self, day: int, a: AgentState, b: AgentState, to: str, phase: str) -> None:
        frm = a.status if a.partner == b.name else "single"
        since = a.partner_since if (a.partner == b.name and a.partner_since is not None) else day
        for x in (a, b):
            x.status, x.partner, x.partner_since = to, (b.name if x is a else a.name), since
        self.log.emit(phase, "relationship.change", day, a=a.name, b=b.name, **{"from": frm, "to": to})
        msg = "are now dating" if to == "dating" else "are now living together"
        for x in (a, b):
            self.entities[x.name].observe(f"[relationship] {a.name} and {b.name} {msg}.")

    def end_relationship(self, day: int, a: AgentState, b: AgentState, phase: str) -> None:
        frm = a.status
        for x in (a, b):
            x.status, x.partner, x.partner_since = "single", None, None
        a.exes[b.name] = day
        b.exes[a.name] = day
        self.log.emit(phase, "relationship.change", day, a=a.name, b=b.name, **{"from": frm, "to": "single"})
        for x in (a, b):
            self.entities[x.name].observe(f"[relationship] {a.name} and {b.name} broke up; both are single again.")

    def drop_other_partner(self, day: int, a: AgentState, keep: AgentState, phase: str) -> None:
        if a.partner and a.partner != keep.name:
            self.end_relationship(day, a, self.agents[a.partner], phase)

    def resolve_date(self, day: int, a: AgentState, b: AgentState, ca: str, cb: str) -> None:
        were_partners = a.partner == b.name
        if ca == "decline" or cb == "decline":
            if were_partners:
                self.end_relationship(day, a, b, "date")
            for me, other, c_other in ((a, b, cb), (b, a, ca)):
                self.entities[me.name].observe(
                    f"[date] {other.name} " + ("does not want to see you again." if c_other == "decline" else "wanted to see you again, but you declined."))
            return
        self.drop_other_partner(day, a, b, "date")
        self.drop_other_partner(day, b, a, "date")
        if ca == "propose_move_in" and cb == "propose_move_in":
            self.set_relationship(day, a, b, "cohabiting", "date")
            return
        if a.partner != b.name:
            self.set_relationship(day, a, b, "dating", "date")
        if ca == "propose_move_in":
            b.pending_move_in = a.name
            self.entities[b.name].observe(f"[date] {a.name} proposed that you move in together; you can accept tomorrow morning.")
        if cb == "propose_move_in":
            a.pending_move_in = b.name
            self.entities[a.name].observe(f"[date] {b.name} proposed that you move in together; you can accept tomorrow morning.")
        for me, other in ((a, b), (b, a)):
            self.entities[me.name].observe(f"[date] {other.name} wants to see you again.")

    # ---- phases ---------------------------------------------------------------------------------

    def market_phase(self, day: int) -> None:
        messages = self.market.run_day(day, self.agents, self._bids, self.log, getattr(self, "_eat_hours", None))
        for name, msgs in messages.items():
            if msgs:
                self.entities[name].observe(f"[market, day {day}] " + " ".join(msgs))

    def app_phase(self, day: int) -> list[tuple[str, str]]:
        dates = run_app(day, self.agents, self.entities, self.rng, self.log, self.pool)
        busy = {n for pair in dates for n in pair}
        for a in self.agents.values():
            if a.status == "dating" and a.name not in busy and a.partner not in busy and a.name < a.partner:
                dates.append((a.name, a.partner))
                busy.update((a.name, a.partner))
        for x, y in dates:
            self.agents[x].date_tonight, self.agents[y].date_tonight = y, x
        return dates

    def dates_phase(self, day: int, dates: list[tuple[str, str]]) -> None:
        if not dates:
            return
        results = list(self.pool.map(lambda p: run_date(day, self.agents[p[0]], self.agents[p[1]], self.entities), dates))
        for (x, y), events in zip(dates, results):
            choices: dict[str, str] = {}
            for ev in events:
                ev = dict(ev)
                t = ev.pop("type")
                self.log.emit("date", t, day, **ev)
                if t == "date.outcome":
                    choices[ev["name"]] = ev["choice"]
            self.resolve_date(day, self.agents[x], self.agents[y], choices[x], choices[y])

    def night(self, day: int) -> None:
        for a in self.agents.values():
            partner = self.agents[a.partner] if a.partner else None
            meals = a.eat(a.hours["eat"])
            if a.status == "cohabiting" and partner is not None and meals < a.hours["eat"]:
                meals += partner.eat(a.hours["eat"] - meals)  # shared inventory: eat from the partner's stock
            hug_hours = 0.0
            if a.status in ("dating", "cohabiting") and partner is not None:
                hug_hours = float(min(a.hours["home"], partner.hours["home"]))  # overlapping home hours together
            elif a.visit_with:
                hug_hours = float(min(a.hours["home"], self.agents[a.visit_with].hours["home"]))
            earned = a.hours["work"] * WAGE
            a.cash += earned
            if a.status == "cohabiting" and partner is not None and partner.games:
                fun = play_shared_games(a.games, partner.games, a.hours["games"])
            else:
                fun = play_games(a.games, a.hours["games"])
            m = met_fractions(meals_eaten=meals, hug_hours=hug_hours, cash_earned=earned, fun_points=fun)
            u = a.needs.true_utility(m)
            j = a.needs.draw_jitter(self.nrng)
            u_hat = a.needs.observed_utility(m, j)
            a.sum_u += u
            a.last_sentence = prompts.content_sentence(u_hat)
            self.entities[a.name].observe(f"[night, day {day}] {a.last_sentence}")
            self.log.emit("night", "night.state", day, name=a.name, m={k: round(m[k], 4) for k in NEEDS}, U=round(u, 4),
                          U_hat=round(u_hat, 4), sentence=a.last_sentence, cash=round(a.cash, 2), inventory=dict(a.inventory),
                          wearing=a.wearing, partner=a.partner, status=a.status, hours=dict(a.hours),
                          meals_eaten=meals, hug_hours=hug_hours, fun_points=round(fun, 3), games=dict(a.games),
                          visit_with=a.visit_with, sum_U=round(a.sum_u, 4), jitter=j, jitter_std=a.needs.jitter_std,
                          bias=a.needs.b, therapy=a.therapy, meditation=a.meditation)


def _name_or_none(v: Any) -> str | None:
    if isinstance(v, str) and v.strip() and v.strip().lower() not in ("null", "none", "no", "false", ""):
        return v.strip()
    return None


def _same(a: str, b: str) -> bool:
    a, b = a.strip().lower(), b.strip().lower()
    return a == b or (a and (a == b.split()[0] or b.startswith(a)))
