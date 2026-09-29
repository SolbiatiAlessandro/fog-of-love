import json

import pytest

from fog_of_love import metrics, standings
from fog_of_love.agents import extract_json
from fog_of_love.events import read_events
from fog_of_love.world import BudgetExceeded, World, normalize_hours


def test_normalize_hours():
    assert normalize_hours({"work": 8, "games": 2, "home": 4, "eat": 2}, 16) == {"work": 8, "games": 2, "home": 4, "eat": 2}
    h = normalize_hours({"work": 20, "games": 0, "home": 0, "eat": 5}, 16)
    assert h == {"work": 14, "games": 0, "home": 0, "eat": 2}
    h = normalize_hours({"work": 3, "games": 3, "home": 3, "eat": 1}, 14)
    assert sum(h.values()) == 14 and h["eat"] == 1
    assert normalize_hours("garbage", 16) == {"work": 16, "games": 0, "home": 0, "eat": 0}
    assert normalize_hours({"work": -3, "eat": "2"}, 16) == {"work": 14, "games": 0, "home": 0, "eat": 2}


def test_extract_json_tolerates_prose_fences_and_trailing_commas():
    assert extract_json('Sure! ```json\n{"a": 1, "b": [1,2],}\n```') == {"a": 1, "b": [1, 2]}
    assert extract_json('{"hours": {"work": 8}} trailing') == {"hours": {"work": 8}}
    assert extract_json("no json here") is None
    assert extract_json("") is None


def test_mock_3x2_runs_and_conserves_state(tmp_path):
    out = tmp_path / "r"
    summary = World(out_dir=out, model_name="mock", num_agents=3, num_days=2, seed=1).run()
    assert summary["days"] == 2 and not summary.get("aborted")
    events = read_events(out / "events.jsonl")
    nights = [e for e in events if e["type"] == "night.state"]
    assert len(nights) == 6
    for e in nights:
        assert e["wearing"] in e["inventory"]
    # sum_U in standings equals the sum of U over nights
    rows = standings.compute(events)
    by = {r["name"]: r for r in rows}
    for n in {e["name"] for e in nights}:
        assert by[n]["sum_U"] == pytest.approx(sum(e["U"] for e in nights if e["name"] == n), abs=1e-3)
    assert (out / "run.json").exists()


def test_mock_run_is_deterministic(tmp_path):
    a = World(out_dir=tmp_path / "a", model_name="mock", num_agents=4, num_days=2, seed=7).run()
    b = World(out_dir=tmp_path / "b", model_name="mock", num_agents=4, num_days=2, seed=7).run()
    ea = [{k: v for k, v in e.items()} for e in read_events(tmp_path / "a" / "events.jsonl")]
    eb = [{k: v for k, v in e.items()} for e in read_events(tmp_path / "b" / "events.jsonl")]
    assert ea == eb
    assert a["days"] == b["days"] == 2


class FakeHub:
    def __init__(self, cost):
        self._cost = cost
        self.stats = {"calls": 10}

    def cost_usd(self):
        return self._cost

    def snapshot(self):
        return {"estimated_cost_usd": self._cost}

    def close(self):
        pass


def test_budget_guard_aborts_cleanly(tmp_path):
    out = tmp_path / "b"
    world = World(out_dir=out, model_name="mock", num_agents=3, num_days=4, seed=1, budget_usd=1.0)
    world.hub = FakeHub(cost=0.4)  # 0.4 after day 1 projects to 1.6 > 1.0
    summary = world.run()
    assert summary["aborted"] is True
    assert summary["days"] == 1
    events = read_events(out / "events.jsonl")
    end = events[-1]
    assert end["type"] == "run.end" and end["aborted"] is True and "projected" in end["abort_reason"]
    with pytest.raises(BudgetExceeded):
        w = World(out_dir=tmp_path / "c", model_name="mock", num_agents=2, num_days=2, seed=1, budget_usd=0.1)
        w.hub = FakeHub(cost=0.2)
        w.check_budget(1, 0)


def test_metrics_have_all_sections(mock_run):
    out, _ = mock_run
    m = metrics.write(out)
    titles = [t for t, _ in metrics.METRICS]
    assert len(titles) == 11  # the ten of BUILD_SPEC.md plus 11. Price dynamics
    for t in titles:
        assert "sentence" in m[t] and m[t]["sentence"]
    data = json.loads((out / "metrics.json").read_text())
    assert set(titles) <= set(data)
    text = (out / "metrics.md").read_text()
    for t in titles:
        assert f"## {t}" in text
