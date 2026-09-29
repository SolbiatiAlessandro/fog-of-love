"""The Love Town catalogue: clothes (zero function, three tiers), games, restaurant meals."""

from __future__ import annotations

GOODS: list[dict] = [
    {"id": "Thrift Hoodie", "category": "Clothing", "tier": "Low", "list_price": 6.0},
    {"id": "Plain Tee", "category": "Clothing", "tier": "Low", "list_price": 6.0},
    {"id": "Linen Shirt", "category": "Clothing", "tier": "Mid", "list_price": 90.0},
    {"id": "Leather Jacket", "category": "Clothing", "tier": "Mid", "list_price": 90.0},
    {"id": "Designer Coat", "category": "Clothing", "tier": "High", "list_price": 1500.0},
    {"id": "Tailored Suit", "category": "Clothing", "tier": "High", "list_price": 1500.0},
    {"id": "Star Farmer", "category": "Games", "tier": "Standard", "list_price": 30.0},
    {"id": "Kart Rush", "category": "Games", "tier": "Standard", "list_price": 30.0},
    {"id": "Dungeon Delve", "category": "Games", "tier": "Standard", "list_price": 30.0},
    {"id": "Food Truck Meal", "category": "Food", "tier": "Low", "list_price": 2.0},
    {"id": "Bistro Dinner", "category": "Food", "tier": "Mid", "list_price": 18.0},
    {"id": "Tasting Menu", "category": "Food", "tier": "High", "list_price": 80.0},
]

BY_ID: dict[str, dict] = {g["id"]: g for g in GOODS}

# Daily production per good (units added to the seller's stock each morning). Unsold units carry over up to
# STOCK_CAP_DAYS x production. The seller's ask never falls below COST_FRACTION x list price (production cost).
PRODUCTION: dict[tuple[str, str], int] = {
    ("Clothing", "Low"): 20, ("Clothing", "Mid"): 6, ("Clothing", "High"): 2,
    ("Games", "Standard"): 8,
    ("Food", "Low"): 40, ("Food", "Mid"): 12, ("Food", "High"): 3,
}
STOCK_CAP_DAYS = 3
COST_FRACTION = 0.6


def category(good_id: str) -> str:
    return BY_ID[good_id]["category"]


def tier(good_id: str) -> str:
    return BY_ID[good_id]["tier"]


def list_price(good_id: str) -> float:
    return BY_ID[good_id]["list_price"]


def production(good_id: str) -> int:
    g = BY_ID[good_id]
    return PRODUCTION[(g["category"], g["tier"])]


def stock_cap(good_id: str) -> int:
    return STOCK_CAP_DAYS * production(good_id)


def production_cost(good_id: str) -> float:
    return round(COST_FRACTION * list_price(good_id), 2)


def clothing_ids(tier_name: str | None = None) -> list[str]:
    return [g["id"] for g in GOODS if g["category"] == "Clothing" and (tier_name is None or g["tier"] == tier_name)]


def resolve_good(text: str) -> str | None:
    """A good id from free text: exact id, case-insensitive id, or a unique substring match."""
    if not isinstance(text, str):
        return None
    t = text.strip()
    if t in BY_ID:
        return t
    low = t.lower()
    for gid in BY_ID:
        if gid.lower() == low:
            return gid
    hits = [gid for gid in BY_ID if low and (low in gid.lower() or gid.lower() in low)]
    return hits[0] if len(hits) == 1 else None


def cheapest_meal() -> str:
    return min((g["id"] for g in GOODS if g["category"] == "Food"), key=list_price)


def price_summary() -> str:
    return "; ".join(f"{g['id']} ({g['category']} {g['tier']}) {g['list_price']:.0f}" for g in GOODS)
