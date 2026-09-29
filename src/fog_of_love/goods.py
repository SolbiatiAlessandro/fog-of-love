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
SELLER_STOCK = 100  # per good per day; sellers restock every morning


def category(good_id: str) -> str:
    return BY_ID[good_id]["category"]


def tier(good_id: str) -> str:
    return BY_ID[good_id]["tier"]


def list_price(good_id: str) -> float:
    return BY_ID[good_id]["list_price"]


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
