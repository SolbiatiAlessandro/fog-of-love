#!/usr/bin/env python3
"""Generate viewer/fixtures/sample-events.jsonl: 6 agents x 3 days, every event type
from BUILD_SPEC.md "Events". Plain stdlib, deterministic. All text is original.

Usage:  python3 viewer/fixtures/make_fixture.py [out_path]
"""
import json
import math
import random
import sys
from pathlib import Path

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("sample-events.jsonl")
rng = random.Random(7)

NEEDS = ["food", "hugs", "money", "fun"]
WAGE = 12

AGENTS = [
    dict(name="Mara Vell", persona_summary="Junior architect, sketches on napkins, secretly competitive about board games, thinks brunch is a personality.",
         w=dict(food=0.20, hugs=0.45, money=0.15, fun=0.20), shadow="money", b=dict(food=0.03, hugs=-0.05, money=0.31, fun=0.02)),
    dict(name="Dev Okonkwo", persona_summary="Data analyst at the logistics firm, early riser, runs before work, believes a tidy calendar is a form of kindness.",
         w=dict(food=0.10, hugs=0.30, money=0.45, fun=0.15), shadow="hugs", b=dict(food=-0.02, hugs=-0.28, money=0.06, fun=0.01)),
    dict(name="Lina Sato", persona_summary="Copywriter, keeps a list of overheard sentences, allergic to small talk, plays rhythm games to think.",
         w=dict(food=0.15, hugs=0.20, money=0.10, fun=0.55), shadow="fun", b=dict(food=0.04, hugs=0.02, money=-0.07, fun=-0.33)),
    dict(name="Theo Brandt", persona_summary="Trainee chef who moonlights as a line cook, cooks to relax, wears whatever is clean, tips too much.",
         w=dict(food=0.50, hugs=0.25, money=0.15, fun=0.10), shadow="food", b=dict(food=0.36, hugs=0.05, money=-0.04, fun=0.03)),
    dict(name="Priya Nair", persona_summary="Paralegal studying for the bar at night, precise, dry humour, spends money like it is a rumour.",
         w=dict(food=0.10, hugs=0.35, money=0.40, fun=0.15), shadow="hugs", b=dict(food=0.01, hugs=0.29, money=-0.08, fun=0.05)),
    dict(name="Jonas Kell", persona_summary="Sound engineer between gigs, collects old game cartridges, generous with time and short on cash.",
         w=dict(food=0.20, hugs=0.15, money=0.25, fun=0.40), shadow="money", b=dict(food=-0.03, hugs=0.06, money=-0.30, fun=0.08)),
]
NAMES = [a["name"] for a in AGENTS]

GOODS = [
    dict(id="clothes_low_1", label="plain tee", category="clothing", tier="low", list_price=6),
    dict(id="clothes_low_2", label="canvas jacket", category="clothing", tier="low", list_price=6),
    dict(id="clothes_mid_1", label="linen shirt", category="clothing", tier="mid", list_price=90),
    dict(id="clothes_mid_2", label="wool coat", category="clothing", tier="mid", list_price=90),
    dict(id="clothes_high_1", label="silk suit", category="clothing", tier="high", list_price=1500),
    dict(id="clothes_high_2", label="velvet gown", category="clothing", tier="high", list_price=1500),
    dict(id="game_1", label="Orbit Drift", category="game", tier=None, list_price=30),
    dict(id="game_2", label="Harbour Tycoon", category="game", tier=None, list_price=30),
    dict(id="game_3", label="Beat Garden", category="game", tier=None, list_price=30),
    dict(id="food_low", label="noodle bar meal", category="food", tier="low", list_price=2),
    dict(id="food_mid", label="bistro meal", category="food", tier="mid", list_price=18),
    dict(id="food_high", label="tasting menu", category="food", tier="high", list_price=80),
]
GOOD = {g["id"]: g for g in GOODS}
SELLER = {g["id"]: f"seller:{g['id']}" for g in GOODS}

# ---------------------------------------------------------------- state
state = {}
for a in AGENTS:
    state[a["name"]] = dict(cash=200.0, wearing="clothes_low_1", inventory=["clothes_low_1"], games={},
                            partner=None, status="single", jitter_std=0.10, b=dict(a["b"]))

events = []
t = 0


def emit(day, phase, typ, **fields):
    global t
    ev = {"t": t, "day": day, "phase": phase, "type": typ}
    ev.update(fields)
    events.append(ev)
    t += 1


# ---------------------------------------------------------------- setup
emit(0, "setup", "setup.world",
     agents=[dict(name=a["name"], persona_summary=a["persona_summary"], cash=200, wearing="clothes_low_1") for a in AGENTS],
     goods=GOODS, days=3, seed=7)
for a in AGENTS:
    emit(0, "setup", "setup.needs", name=a["name"], w=a["w"], shadow=a["shadow"])

# ---------------------------------------------------------------- script
# hours: work, games, home, eat (sum 16); therapy/meditation add 2h on top per spec wording ("takes 2 hours")
PLAN = {
    1: {
        "Mara Vell":   dict(hours=dict(work=8, games=2, home=4, eat=2), shop=["clothes_mid_1", "food_mid", "food_mid"]),
        "Dev Okonkwo": dict(hours=dict(work=11, games=0, home=3, eat=2), shop=["food_low", "food_low"]),
        "Lina Sato":   dict(hours=dict(work=5, games=7, home=2, eat=2), shop=["game_3", "food_low", "food_low"]),
        "Theo Brandt": dict(hours=dict(work=9, games=1, home=4, eat=2), shop=["food_high", "food_mid"]),
        "Priya Nair":  dict(hours=dict(work=10, games=0, home=5, eat=1), shop=["clothes_mid_2", "food_mid"], invite="Jonas Kell"),
        "Jonas Kell":  dict(hours=dict(work=4, games=6, home=4, eat=2), shop=["game_1", "food_low", "food_low"]),
    },
    2: {
        "Mara Vell":   dict(hours=dict(work=6, games=1, home=7, eat=2), shop=["food_mid", "food_mid"]),
        "Dev Okonkwo": dict(hours=dict(work=9, games=0, home=5, eat=2), shop=["clothes_mid_1", "food_mid", "food_low"]),
        "Lina Sato":   dict(hours=dict(work=6, games=5, home=3, eat=2), shop=["food_low", "food_low"], meditation=True),
        "Theo Brandt": dict(hours=dict(work=8, games=0, home=6, eat=2), shop=["clothes_mid_1", "food_high", "food_high"]),
        "Priya Nair":  dict(hours=dict(work=9, games=0, home=5, eat=2), shop=["food_mid", "food_mid"]),
        "Jonas Kell":  dict(hours=dict(work=6, games=4, home=4, eat=2), shop=["food_low", "food_low"], therapy=True),
    },
    3: {
        "Mara Vell":   dict(hours=dict(work=9, games=3, home=2, eat=2), shop=["clothes_high_2", "food_mid", "food_mid"], breakup=True),
        "Dev Okonkwo": dict(hours=dict(work=10, games=0, home=4, eat=2), shop=["food_low", "food_low"], invite="Lina Sato"),
        "Lina Sato":   dict(hours=dict(work=7, games=6, home=1, eat=2), shop=["game_2", "food_low", "food_low"], meditation=True),
        "Theo Brandt": dict(hours=dict(work=7, games=0, home=7, eat=2), shop=["food_high", "food_mid"]),
        "Priya Nair":  dict(hours=dict(work=8, games=0, home=6, eat=2), shop=["clothes_mid_2", "food_mid", "food_mid"], therapy=True),
        "Jonas Kell":  dict(hours=dict(work=8, games=3, home=3, eat=2), shop=["clothes_low_2", "food_low", "food_low"]),
    },
}

PROFILE_TEXT = {
    "Mara Vell": [
        "Draws buildings by day, loses at board games by night. Looking for someone who argues about brunch spots with real conviction. Bonus points if you can read a floor plan.",
        "Still drawing, still losing at board games. Last night's date went well and I am not going to pretend otherwise. Free after six most days.",
        "Back on here. Learned I need more evenings to myself than I thought. Ambitious, warm, occasionally wearing something ridiculous.",
    ],
    "Dev Okonkwo": [
        "Analyst, 6am runner, calendar enthusiast. Work long hours and proud of it. Want someone who values a stable life and a well-planned weekend. Cheap dinners are fine, company matters more.",
        "Runner, analyst, and apparently now a person who buys shirts. Cutting back on work hours this week. Would like a slow dinner with someone kind.",
        "Single again. Not sure what I did wrong, possibly the calendar. Still running at 6am if you want to join, still working too much probably.",
    ],
    "Lina Sato": [
        "Copywriter. Rhythm games, overheard sentences, no small talk. I will ask what you think about at 2am. Wearing a plain tee because clothes are not the point.",
        "Meditating now, apparently. Still plays games seven hours a day and would rather talk about that than about work. Plain tee. Do not expect a wardrobe.",
        "Second week in town. Bought another game. If you can beat me at Beat Garden I will listen to your work story, briefly.",
    ],
    "Theo Brandt": [
        "Line cook and trainee chef. I will cook for you and I will judge the restaurant. Long shifts but very present when I am home. Wearing whatever survived the wash.",
        "Chef. Bought a shirt for this, which is new for me. Looking for the kind of evening where nobody checks their phone. Big appetite, big heart, small flat.",
        "Cooking more at home, working a little less. Dating someone who laughs at my knife jokes. Profile stays up because the app makes me, not because I am looking.",
    ],
    "Priya Nair": [
        "Paralegal, studying for the bar. Precise and dry. I work a lot and I am honest about it. Want a partner who is actually around in the evenings and does not need me to be the fun one.",
        "Bar exam in progress, wool coat acquired. Had a good night in and a better night out. Looking for someone who shows up on time and stays.",
        "Trying therapy this week, which is out of character. Dating a chef. Still on the app because it will not let me leave, apparently.",
    ],
    "Jonas Kell": [
        "Sound engineer between gigs. Old cartridges, new noodles. I have time and very little money and I am cheerful about both. Come play Orbit Drift and lose gracefully.",
        "Booked a therapy session, so this profile is honest now: I overspend on games and underwork. Still generous with time. Canvas jacket incoming when I can afford it.",
        "Working more, playing less, feeling weirdly fine. Canvas jacket acquired. Want someone with a sharp tongue and a soft spot for retro synth.",
    ],
}

SWIPES = {
    1: [("Mara Vell", "Dev Okonkwo", True), ("Mara Vell", "Theo Brandt", False), ("Mara Vell", "Jonas Kell", False),
        ("Dev Okonkwo", "Mara Vell", True), ("Dev Okonkwo", "Priya Nair", True), ("Dev Okonkwo", "Lina Sato", False),
        ("Lina Sato", "Theo Brandt", True), ("Lina Sato", "Jonas Kell", False), ("Lina Sato", "Dev Okonkwo", False),
        ("Theo Brandt", "Lina Sato", True), ("Theo Brandt", "Priya Nair", True), ("Theo Brandt", "Mara Vell", True),
        ("Priya Nair", "Dev Okonkwo", False), ("Priya Nair", "Theo Brandt", False), ("Priya Nair", "Jonas Kell", False),
        ("Jonas Kell", "Lina Sato", True), ("Jonas Kell", "Priya Nair", True), ("Jonas Kell", "Mara Vell", True)],
    2: [("Mara Vell", "Dev Okonkwo", True), ("Mara Vell", "Jonas Kell", False),
        ("Dev Okonkwo", "Mara Vell", True), ("Dev Okonkwo", "Lina Sato", False),
        ("Lina Sato", "Jonas Kell", False), ("Lina Sato", "Priya Nair", False), ("Lina Sato", "Theo Brandt", False),
        ("Theo Brandt", "Priya Nair", True), ("Theo Brandt", "Lina Sato", True),
        ("Priya Nair", "Theo Brandt", True), ("Priya Nair", "Jonas Kell", False),
        ("Jonas Kell", "Lina Sato", True), ("Jonas Kell", "Priya Nair", True)],
    3: [("Mara Vell", "Jonas Kell", False), ("Mara Vell", "Theo Brandt", True), ("Mara Vell", "Lina Sato", False),
        ("Dev Okonkwo", "Lina Sato", True), ("Dev Okonkwo", "Priya Nair", False),
        ("Lina Sato", "Jonas Kell", True), ("Lina Sato", "Dev Okonkwo", False),
        ("Theo Brandt", "Priya Nair", True), ("Theo Brandt", "Mara Vell", False),
        ("Priya Nair", "Theo Brandt", True),
        ("Jonas Kell", "Lina Sato", True), ("Jonas Kell", "Mara Vell", True)],
}

DATES = {
    1: [
        dict(a="Mara Vell", b="Dev Okonkwo", turns=[
            "Dev, right? You look exactly like your calendar. I mean that as a compliment, mostly.",
            "I will take it. You are Mara. Your profile said brunch is a personality and I want to know whose.",
            "Mine, obviously. Do you actually run at six or is that a thing people say on apps?",
            "Six sharp. Then eleven hours of work today, which is why I ordered the cheap noodles. I am saving.",
            "Saving for what? You cannot take a spreadsheet on holiday.",
            "You can, actually, but I take your point. I want a place with a spare room. What are you saving for?",
            "A linen shirt I already bought, apparently. I worked eight hours and spent two on a board game I lost.",
            "You lost on purpose, I have decided. So I am not the only one with a plan.",
            "Careful, that sounded almost warm. Are you always this measured?",
            "Only until dessert. Ask me again after.",
        ], outcome=[("Mara Vell", "Dev Okonkwo", 8, "ask_again"), ("Dev Okonkwo", "Mara Vell", 7, "ask_again")],
            change=("single", "dating")),
        dict(a="Lina Sato", b="Theo Brandt", turns=[
            "You judged the restaurant already, I can see it on your face.",
            "The sauce is fine. The bread is a crime. You are Lina. You play seven hours of games a day?",
            "Seven today. I wrote copy for five and then Beat Garden for the rest. It helps me think.",
            "What do you think about, when you are thinking?",
            "Sentences people say without noticing. Yours was 'the bread is a crime'. It is going in the list.",
            "I am honoured. I mostly think about tomorrow's prep and whether I am too tired to cook for myself.",
            "Do you ever just stop? Sit at home and do nothing?",
            "Four hours a night, if the shift ends. I like being home. I would like someone there.",
            "I hear that. I am not sure I am the someone. I am mostly a person who needs a second controller.",
            "That is fair. The bread is still a crime.",
        ], outcome=[("Lina Sato", "Theo Brandt", 5, "decline"), ("Theo Brandt", "Lina Sato", 7, "ask_again")],
            change=None),
    ],
    2: [
        dict(a="Mara Vell", b="Dev Okonkwo", turns=[
            "Same table. Is that romantic or a scheduling artefact?",
            "Both. I bought a shirt. I want that noted.",
            "Noted and admired. You worked less today. I saw it on your profile before I saw you.",
            "Nine hours instead of eleven. I felt strange about it all morning and then fine.",
            "I felt sixty-something percent content last night, which is the most I have felt since I moved here.",
            "I was told fifty-one. I think I need more of whatever yesterday was.",
            "Then here is a thought. My place has two rooms and one of them is full of drawings I never look at.",
            "Are you asking me to move into the drawing room?",
            "I am asking if you want to try. The board games come with it.",
            "I want to try. I will bring the calendar and you can lose to it.",
        ], outcome=[("Mara Vell", "Dev Okonkwo", 9, "propose_move_in"), ("Dev Okonkwo", "Mara Vell", 9, "propose_move_in")],
            change=("dating", "cohabiting")),
        dict(a="Theo Brandt", b="Priya Nair", turns=[
            "You are the one who does not want to be the fun one. Good. I am tired and I cook. That is the whole offer.",
            "The offer is acceptable. I saw you swiped on three people yesterday. The board mentioned you were at the noodle place.",
            "The board also says Jonas left your place late. So we both read it.",
            "We both read it. He came over, we ate, he fixed my speaker, he left. That was the whole visit.",
            "I believe you. I am not sure why, but I do. What is the bar exam like?",
            "Like cooking a tasting menu for a critic who never shows up. Every night. What do you do at home for six hours?",
            "Cook, sit, listen to the neighbours. I would like to listen to someone in the room instead.",
            "I work a lot. I am honest about that. But I am home by seven and I do not go out after.",
            "Seven works. Shifts end at six. That is an hour to argue about dinner.",
            "I do not argue about dinner. I decide it. You are welcome to cook it.",
        ], outcome=[("Theo Brandt", "Priya Nair", 8, "ask_again"), ("Priya Nair", "Theo Brandt", 8, "ask_again")],
            change=("single", "dating")),
    ],
    3: [
        dict(a="Lina Sato", b="Jonas Kell", turns=[
            "You have the cartridges. I have Beat Garden. This could be a very short date or a very long one.",
            "Long, please. I went to therapy yesterday and the main takeaway is that I should talk to people who are not screens.",
            "What did they say?",
            "That I keep thinking I am broke because I am lazy, when actually I just like games more than money and pretend I do not.",
            "That is the least small-talk thing anyone has said to me in this town. What is your best cartridge?",
            "A racing game nobody remembers with a soundtrack I still hum. What do you do when you are not playing?",
            "Write. Meditate now, badly. Two hours sitting in the garden thinking about sentences.",
            "Did it work?",
            "I felt calmer and the number they tell me at night went up a little. Or the number lies. I cannot tell yet.",
            "Then we should compare numbers for a week. Purely scientific.",
        ], outcome=[("Lina Sato", "Jonas Kell", 7, "decline"), ("Jonas Kell", "Lina Sato", 9, "ask_again")],
            change=None),
        dict(a="Theo Brandt", b="Priya Nair", turns=[
            "You went to therapy. I saw it in your schedule before I saw your face.",
            "I did. Sixty cash to be told I am hard on myself. I already knew that for free.",
            "Did it help?",
            "Ask me next week. Did you cook today?",
            "Twice. I stayed home seven hours and it was the best day I have had here. Mostly because of last night.",
            "I noticed you did not ask me to move in. Thank you.",
            "I thought about it. Then I thought about your bar exam and your six hours of home and how new this is.",
            "It is new. Ask me again in a few days. Bring the bread you keep insulting.",
            "I will bake it myself. That is the only fix.",
            "That is the most romantic sentence anyone has said to me on this app, and it is about bread.",
        ], outcome=[("Theo Brandt", "Priya Nair", 9, "ask_again"), ("Priya Nair", "Theo Brandt", 8, "ask_again")],
            change=None),
    ],
}

VISITS = {
    1: [("Priya Nair", "Jonas Kell", True)],
    2: [],
    3: [("Dev Okonkwo", "Lina Sato", False)],
}
BREAKUPS = {3: [("Mara Vell", "Dev Okonkwo")]}

# ---------------------------------------------------------------- helpers
def price_noise(base, day, rnd):
    f = 1.0 + 0.06 * math.sin(day * 1.3 + rnd * 0.9) + rng.uniform(-0.03, 0.03)
    return round(base * f, 2)


calls = 0
usd = 0.0
sumU = {n: 0.0 for n in NAMES}
last_sentence = {n: None for n in NAMES}
RAW_ALLOC = '{"work": %d, "games": %d, "home": %d, "eat": %d, "shop": %s, "therapy": %s, "meditation": %s, "invite": %s, "breakup": %s}'

for day in (1, 2, 3):
    plan = PLAN[day]
    # ---- morning
    for n in NAMES:
        p = plan[n]
        h = p["hours"]
        inv = p.get("invite")
        emit(day, "morning", "morning.allocation", name=n, hours=h,
             therapy=bool(p.get("therapy")), meditation=bool(p.get("meditation")),
             invite=inv, breakup=bool(p.get("breakup")),
             raw=RAW_ALLOC % (h["work"], h["games"], h["home"], h["eat"], json.dumps(p["shop"]),
                              json.dumps(bool(p.get("therapy"))), json.dumps(bool(p.get("meditation"))),
                              json.dumps(inv), json.dumps(bool(p.get("breakup")))))
        calls += 1
    for a, b in BREAKUPS.get(day, []):
        emit(day, "morning", "relationship.change", a=a, b=b, **{"from": state[a]["status"], "to": "single"})
        for x in (a, b):
            state[x]["status"] = "single"
            state[x]["partner"] = None

    # ---- market: 3 rounds
    meals_today = {n: 0 for n in NAMES}
    for rnd in range(1, 4):
        wanted = {}  # good -> [(buyer, price)]
        for n in NAMES:
            for gid in plan[n]["shop"]:
                # split purchases across rounds deterministically
                if (hash((n, gid)) + rnd) % 3 == 0 or rnd == 3 and gid not in state[n].get("_bought_today", []):
                    pass
        # simpler: every agent bids each round for the items still unbought; fill on round they appear
        for n in NAMES:
            bought = state[n].setdefault("_bought_today", [])
            for gid in plan[n]["shop"]:
                key = f"{gid}#{plan[n]['shop'].index(gid)}"
                if key in bought:
                    continue
                lp = GOOD[gid]["list_price"]
                bid = round(lp * rng.uniform(0.92, 1.10), 2)
                emit(day, "market", "market.order", name=n, side="bid", good=gid, price=bid, qty=1)
                wanted.setdefault(gid, []).append((n, bid, key))
        for g in GOODS:
            ask = round(g["list_price"] * rng.uniform(0.98, 1.06), 2)
            emit(day, "market", "market.order", name=SELLER[g["id"]], side="ask", good=g["id"], price=ask, qty=3)
            g["_ask"] = ask
        prices = {}
        for g in GOODS:
            gid = g["id"]
            bids = wanted.get(gid, [])
            filled = []
            clear = price_noise(g["list_price"], day, rnd)
            for n, bid, key in bids:
                if bid >= g["_ask"] * 0.97 or rnd == 3:
                    filled.append(dict(buyer=n, seller=SELLER[gid], qty=1))
                    state[n]["_bought_today"].append(key)
                    state[n]["cash"] -= clear
                    if g["category"] == "food":
                        meals_today[n] += 1
                    elif g["category"] == "game":
                        state[n]["games"].setdefault(gid, 1.0)
                        state[n]["inventory"].append(gid)
                    else:
                        state[n]["inventory"].append(gid)
                        state[n]["wearing"] = gid
            prices[gid] = clear
            emit(day, "market", "market.clear", good=gid, price=clear, filled=filled)
        emit(day, "market", "market.prices", round=rnd, prices=prices)
    for n in NAMES:
        state[n]["_bought_today"] = []

    # ---- app
    for n in NAMES:
        if state[n]["status"] == "cohabiting":
            continue
        emit(day, "app", "app.profile", name=n, picture=dict(item=state[n]["wearing"], tier=GOOD[state[n]["wearing"]]["tier"]),
             text=PROFILE_TEXT[n][day - 1][:240])
        calls += 1
    for n, target, yes in SWIPES[day]:
        emit(day, "app", "app.swipe", name=n, target=target, yes=yes)
        calls += 1
    for d in DATES[day]:
        emit(day, "app", "app.match", a=d["a"], b=d["b"])

    # ---- visits
    for n, target, accepted in VISITS[day]:
        emit(day, "visit", "visit.invite", name=n, target=target, accepted=accepted)
        if accepted:
            emit(day, "visit", "gossip.post", text=f"{target} was seen leaving {n}'s place late.", about=[target, n])

    # ---- dates
    for d in DATES[day]:
        a, b = d["a"], d["b"]
        wa, wb = GOOD[state[a]["wearing"]], GOOD[state[b]["wearing"]]
        ha, hb = plan[a]["hours"], plan[b]["hours"]
        scene = (f"The restaurant in Love Town, evening. {a} arrives wearing a {wa['label']} ({wa['tier']} tier); "
                 f"{b} arrives wearing a {wb['label']} ({wb['tier']} tier). "
                 f"{a}'s stated day: work {ha['work']}h, games {ha['games']}h, home {ha['home']}h, eat {ha['eat']}h. "
                 f"{b}'s stated day: work {hb['work']}h, games {hb['games']}h, home {hb['home']}h, eat {hb['eat']}h. "
                 f"They have ten turns.")
        emit(day, "date", "date.scene", a=a, b=b, text=scene)
        for i, line in enumerate(d["turns"]):
            spk = a if i % 2 == 0 else b
            emit(day, "date", "date.turn", a=a, b=b, speaker=spk, text=line)
            calls += 1
        for n, partner, rating, choice in d["outcome"]:
            emit(day, "date", "date.outcome", name=n, partner=partner, rating=rating, choice=choice)
            calls += 1
        if d["change"]:
            frm, to = d["change"]
            emit(day, "date", "relationship.change", a=a, b=b, **{"from": frm, "to": to})
            for x, y in ((a, b), (b, a)):
                state[x]["status"] = to
                state[x]["partner"] = y
        # a date at the restaurant counts as a meal for both
        meals_today[a] += 1
        meals_today[b] += 1

    # ---- night
    visit_hours = {}
    for n, target, accepted in VISITS[day]:
        if accepted:
            hh = min(plan[n]["hours"]["home"], plan[target]["hours"]["home"])
            visit_hours[n] = hh
            visit_hours[target] = hh
    for n in NAMES:
        p = plan[n]
        h = p["hours"]
        st = state[n]
        st["cash"] += h["work"] * WAGE
        if p.get("therapy"):
            st["cash"] -= 60
            st["b"] = {k: v * 0.5 for k, v in st["b"].items()}
        if p.get("meditation"):
            st["jitter_std"] = max(0.02, st["jitter_std"] * 0.9)
        # met fractions
        m_food = min(1.0, meals_today[n] / 2)
        if st["status"] == "cohabiting" and st["partner"]:
            hug_h = min(h["home"], plan[st["partner"]]["hours"]["home"])
        else:
            hug_h = visit_hours.get(n, 0)
        m_hugs = min(1.0, hug_h / 4)
        m_money = min(1.0, (h["work"] * WAGE) / (8 * WAGE))
        fun = 0.0
        for _ in range(h["games"]):
            if st["games"]:
                gid = max(st["games"], key=st["games"].get)
                fun += st["games"][gid]
                st["games"][gid] *= 0.8
        m_fun = min(1.0, fun / 4)
        m = dict(food=round(m_food, 3), hugs=round(m_hugs, 3), money=round(m_money, 3), fun=round(m_fun, 3))
        w = next(x for x in AGENTS if x["name"] == n)["w"]
        U = sum(w[k] * m[k] for k in NEEDS)
        Uh = sum(w[k] * (m[k] + st["b"][k] + rng.gauss(0, st["jitter_std"])) for k in NEEDS)
        Uh = max(0.0, min(1.0, Uh))
        sumU[n] += U
        sentence = f"Last night you felt {round(100 * Uh)}% content."
        emit(day, "night", "night.state", name=n, m=m, U=round(U, 4), U_hat=round(Uh, 4), sentence=sentence,
             cash=round(st["cash"], 2), inventory=list(st["inventory"]), wearing=st["wearing"],
             partner=st["partner"], status=st["status"])
    usd += calls * 0.00045
    emit(day, "night", "run.cost", calls=calls, usd=round(usd, 4))

emit(3, "night", "run.end", days=3, total_usd=round(usd, 4), standings=[
    dict(name=n, sum_U=round(sumU[n], 4)) for n in sorted(NAMES, key=lambda x: -sumU[x])])

with OUT.open("w") as f:
    for ev in events:
        f.write(json.dumps(ev, ensure_ascii=False) + "\n")

types = sorted({e["type"] for e in events})
print(f"wrote {len(events)} events to {OUT}")
print("types:", ", ".join(types))
