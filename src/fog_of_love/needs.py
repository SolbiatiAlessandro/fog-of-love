"""Needs, weights, bias, jitter: the one decision that matters (BUILD_SPEC.md, "Needs and utility")."""

from __future__ import annotations

import dataclasses
from typing import Any

import numpy as np

NEEDS = ("food", "hugs", "money", "fun")
WAGE = 12.0
BIAS_STD = 0.10
SHADOW_STD = 0.35
JITTER_STD = 0.10
JITTER_FLOOR = 0.02
THERAPY_COST = 60.0
GAME_DECAY = 0.8


@dataclasses.dataclass
class Needs:
    """One agent's hidden utility: weights, bias (one shadow dimension), and the current jitter std."""

    w: dict[str, float]
    b: dict[str, float]
    shadow: str
    jitter_std: float = JITTER_STD

    @classmethod
    def draw(cls, rng: np.random.Generator) -> "Needs":
        w = rng.dirichlet(np.ones(len(NEEDS)))
        b = {k: float(rng.normal(0.0, BIAS_STD)) for k in NEEDS}
        shadow = NEEDS[int(rng.integers(len(NEEDS)))]
        b[shadow] = float(rng.normal(0.0, SHADOW_STD))
        return cls(w={k: float(v) for k, v in zip(NEEDS, w)}, b=b, shadow=shadow)

    def true_utility(self, m: dict[str, float]) -> float:
        return float(sum(self.w[k] * m[k] for k in NEEDS))

    def draw_jitter(self, rng: np.random.Generator) -> dict[str, float]:
        return {k: float(rng.normal(0.0, self.jitter_std)) for k in NEEDS}

    def observed_utility(self, m: dict[str, float], j: dict[str, float]) -> float:
        raw = sum(self.w[k] * (m[k] + self.b[k] + j[k]) for k in NEEDS)
        return float(min(1.0, max(0.0, raw)))

    def therapy(self) -> None:
        self.b = {k: v * 0.5 for k, v in self.b.items()}

    def meditation(self) -> None:
        self.jitter_std = max(JITTER_FLOOR, self.jitter_std * 0.9)

    def to_dict(self) -> dict[str, Any]:
        return {"w": dict(self.w), "b": dict(self.b), "shadow": self.shadow, "jitter_std": self.jitter_std}


def met_fractions(*, meals_eaten: int, hug_hours: float, cash_earned: float, fun_points: float) -> dict[str, float]:
    """Saturating daily met-fractions m_k in [0, 1]."""
    return {
        "food": min(1.0, meals_eaten / 2.0),
        "hugs": min(1.0, hug_hours / 4.0),
        "money": min(1.0, cash_earned / (8.0 * WAGE)),
        "fun": min(1.0, fun_points / 4.0),
    }


def play_games(yields: dict[str, float], hours: int) -> float:
    """Plays `hours` hours, each hour on the game with the highest current yield; decays that game's yield
    by GAME_DECAY (persistent, mutates `yields`). Returns the fun points earned. No game owned: 0."""
    points = 0.0
    if not yields:
        return 0.0
    for _ in range(int(hours)):
        game = max(yields, key=lambda g: yields[g])
        points += yields[game]
        yields[game] *= GAME_DECAY
    return points
