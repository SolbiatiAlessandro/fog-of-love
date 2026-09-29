import numpy as np
import pytest

from fog_of_love import prompts
from fog_of_love.needs import (BIAS_STD, JITTER_FLOOR, JITTER_STD, NEEDS, SHADOW_STD, Needs, met_fractions, play_games)


def test_weights_are_dirichlet_and_bias_has_one_shadow():
    rng = np.random.default_rng(0)
    for _ in range(50):
        n = Needs.draw(rng)
        assert set(n.w) == set(NEEDS)
        assert abs(sum(n.w.values()) - 1.0) < 1e-9
        assert all(v >= 0 for v in n.w.values())
        assert n.shadow in NEEDS
        assert n.jitter_std == JITTER_STD
    # Shadow dimension is drawn with the wider std: its spread over many agents is larger.
    rng = np.random.default_rng(1)
    shadow_b, other_b = [], []
    for _ in range(2000):
        n = Needs.draw(rng)
        shadow_b.append(n.b[n.shadow])
        other_b.extend(v for k, v in n.b.items() if k != n.shadow)
    assert abs(np.std(shadow_b) - SHADOW_STD) < 0.03
    assert abs(np.std(other_b) - BIAS_STD) < 0.01


def test_true_and_observed_utility():
    n = Needs(w={"food": 0.25, "hugs": 0.25, "money": 0.25, "fun": 0.25},
              b={"food": 0.1, "hugs": -0.1, "money": 0.0, "fun": 0.4}, shadow="fun")
    m = {"food": 1.0, "hugs": 0.0, "money": 0.5, "fun": 0.5}
    assert n.true_utility(m) == pytest.approx(0.5)
    j = {k: 0.0 for k in NEEDS}
    assert n.observed_utility(m, j) == pytest.approx(0.5 + 0.25 * 0.4)
    # clipping at 1 and 0
    assert n.observed_utility({k: 1.0 for k in NEEDS}, {k: 0.5 for k in NEEDS}) == 1.0
    assert n.observed_utility({k: 0.0 for k in NEEDS}, {k: -0.5 for k in NEEDS}) == 0.0


def test_therapy_halves_bias_and_meditation_shrinks_jitter():
    n = Needs(w={k: 0.25 for k in NEEDS}, b={"food": 0.2, "hugs": -0.1, "money": 0.05, "fun": 0.3}, shadow="fun")
    n.therapy()
    assert n.b == {"food": 0.1, "hugs": -0.05, "money": 0.025, "fun": 0.15}
    n.meditation()
    assert n.jitter_std == pytest.approx(JITTER_STD * 0.9)
    for _ in range(200):
        n.meditation()
    assert n.jitter_std == JITTER_FLOOR
    rng = np.random.default_rng(0)
    js = [n.draw_jitter(rng)["food"] for _ in range(3000)]
    assert abs(np.std(js) - JITTER_FLOOR) < 0.005


def test_met_fractions_saturate():
    m = met_fractions(meals_eaten=3, hug_hours=6, cash_earned=200, fun_points=9)
    assert m == {"food": 1.0, "hugs": 1.0, "money": 1.0, "fun": 1.0}
    m = met_fractions(meals_eaten=1, hug_hours=2, cash_earned=48, fun_points=1)
    assert m == {"food": 0.5, "hugs": 0.5, "money": 0.5, "fun": 0.25}
    assert met_fractions(meals_eaten=0, hug_hours=0, cash_earned=0, fun_points=0) == {k: 0.0 for k in NEEDS}


def test_game_yield_decays_per_hour_and_persists():
    yields = {"A": 1.0}
    assert play_games(yields, 2) == pytest.approx(1.0 + 0.8)
    assert yields["A"] == pytest.approx(0.64)
    assert play_games(yields, 1) == pytest.approx(0.64)
    assert play_games({}, 5) == 0.0
    two = {"A": 1.0, "B": 1.0}
    assert play_games(two, 2) == pytest.approx(2.0)  # best game each hour: A then B


def test_sentence_only_reveals_rounded_percentage():
    assert prompts.content_sentence(0.634) == "Last night you felt 63% content."
