"""Adapter tests for tools/export_polyworld_replay.py (love-town-replay/1)."""

import importlib.util
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("export_polyworld_replay", ROOT / "tools" / "export_polyworld_replay.py")
export = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(export)

SMALL_RUN = ROOT / "runs" / "dev-4x2-gemma-s1" / "events.jsonl"


@pytest.fixture(scope="module")
def small_doc(tmp_path_factory):
    out = tmp_path_factory.mktemp("lovetown") / "small.lovetown.json"
    return export.convert_path(SMALL_RUN, out), out


def test_small_run_converts_and_validates(small_doc):
    doc, out = small_doc
    assert doc["schema"] == "love-town-replay/1"
    assert doc["run"]["name"] == "dev-4x2-gemma-s1"
    assert doc["run"]["days"] == 2 and doc["run"]["agent_count"] == 4
    assert doc["source"]["complete"] is True and doc["source"]["event_count"] == 259
    assert [a["id"] for a in doc["agents"]] == ["agent-000", "agent-001", "agent-002", "agent-003"]
    assert [a["house"] for a in doc["agents"]] == [0, 1, 2, 3]
    assert all(a["hidden"] and a["hidden"]["shadow"] for a in doc["agents"])
    assert [d["day"] for d in doc["days"]] == [1, 2]
    assert {g["category"] for g in doc["goods"]} == {"Clothing", "Games", "Food"}
    export.validate(doc)
    export.validate(json.loads(out.read_text()))


def test_names_never_leak_outside_agents(small_doc):
    doc, _ = small_doc
    names = [a["name"] for a in doc["agents"]]
    body = json.dumps({k: v for k, v in doc.items() if k != "agents"})
    # names appear only inside recorded prose (scene text, turns, gossip, reasons), never as references
    for day in doc["days"]:
        for night in day["night"]:
            assert night["agent"].startswith("agent-")
            assert night["partner"] is None or night["partner"].startswith("agent-")
        for date in day["dates"]:
            assert all(p.startswith("agent-") for p in date["pair"])
            assert all(t["speaker"] in date["pair"] for t in date["turns"])
    for name in names:
        assert f'"{name}"' not in body.replace('"text"', "")  # a bare name as a value would be a leaked reference


def test_market_rounds_group_orders_and_clears(small_doc):
    doc, _ = small_doc
    day = doc["days"][0]
    rounds = day["market"]["rounds"]
    assert rounds and rounds[0]["round"] == 0
    priced = [r for r in rounds if r["prices"]]
    assert len(priced) == 3  # three clearing rounds per day
    for r in priced:
        assert set(r["prices"]) == {g["id"] for g in doc["goods"]}
        assert r["asks"] and all(a["seller"] == a["good"] for a in r["asks"])
        for clear in r["clears"]:
            assert clear["volume"] == sum(f["qty"] for f in clear["fills"])
    source = [json.loads(l) for l in SMALL_RUN.read_text().splitlines() if l.strip()]
    fills = sum(len(e["filled"]) for e in source if e["type"] == "market.clear" and e["day"] == 1)
    assert sum(len(c["fills"]) for r in rounds for c in r["clears"]) == fills


def test_dates_carry_turns_outcomes_and_changes(small_doc):
    doc, _ = small_doc
    dates = [d for day in doc["days"] for d in day["dates"]]
    assert len(dates) == 3
    for index, date in enumerate(doc["days"][0]["dates"]):
        assert date["table"] == index % 2
    assert all(len(d["turns"]) == 10 and len(d["outcomes"]) == 2 for d in dates)
    changes = [d["change"] for d in dates if d["change"]]
    assert changes and all(c["to"] in {"single", "dating", "cohabiting"} for c in changes)
    assert all(o["rating"] is None or isinstance(o["rating"], float) for d in dates for o in d["outcomes"])


def test_night_hidden_and_standings(small_doc):
    doc, _ = small_doc
    night = doc["days"][0]["night"][0]
    assert set(night["hidden"]) == {"m", "U", "U_hat", "sum_U", "jitter"}
    assert set(night["hidden"]["m"]) == {"food", "hugs", "money", "fun"}
    assert "U" not in night and "m" not in night  # hidden values only under `hidden`
    standings = doc["standings"]
    assert [s["rank"] for s in standings] == [1, 2, 3, 4]
    assert standings == sorted(standings, key=lambda s: (-s["sum_U"], s["agent"]))
    expected = {}
    for day in doc["days"]:
        for n in day["night"]:
            expected[n["agent"]] = expected.get(n["agent"], 0) + n["hidden"]["U"]
    for s in standings:
        assert s["sum_U"] == pytest.approx(expected[s["agent"]])
        assert s["nights"] == 2


def test_deterministic_output(tmp_path):
    a = export.convert_path(SMALL_RUN, tmp_path / "a.json")
    b = export.convert_path(SMALL_RUN, tmp_path / "b.json")
    assert a == b
    assert (tmp_path / "a.json").read_bytes() == (tmp_path / "b.json").read_bytes()
    assert (tmp_path / "a.json").read_text().endswith("\n")


def test_mock_run_converts(mock_run, tmp_path):
    out_dir, _ = mock_run
    doc = export.convert_path(out_dir / "events.jsonl", tmp_path / "mock.lovetown.json")
    export.validate(doc)
    assert doc["run"]["agent_count"] == 6 and len(doc["days"]) == 4
    assert all(len(day["allocations"]) == 6 and len(day["night"]) == 6 for day in doc["days"])


def test_rejects_bad_input(tmp_path):
    events = [json.loads(l) for l in SMALL_RUN.read_text().splitlines() if l.strip()]
    with pytest.raises(export.ReplayConversionError, match="run.end"):
        export.convert_events([e for e in events if e["type"] != "run.end"], name="x")
    partial = export.convert_events([e for e in events if e["type"] != "run.end"], name="x", allow_incomplete=True)
    assert partial["source"]["complete"] is False and partial["run"]["calls"] is None
    bad = [dict(e) for e in events]
    bad[5]["t"] = bad[4]["t"]
    with pytest.raises(export.ReplayConversionError, match="non-increasing"):
        export.convert_events(bad, name="x")
    unknown = [dict(e) for e in events]
    swipe = next(e for e in unknown if e["type"] == "app.swipe")
    swipe["target"] = "Nobody Here"
    with pytest.raises(export.ReplayConversionError, match="unknown agent"):
        export.convert_events(unknown, name="x")
    with pytest.raises(export.ReplayConversionError, match="setup.world"):
        export.convert_events(events[1:], name="x")
    (tmp_path / "bad.jsonl").write_text('{"type": "setup.world"}\nnot json\n')
    with pytest.raises(export.ReplayConversionError, match="bad JSON"):
        export.read_events(tmp_path / "bad.jsonl")


def test_cli_round_trip(tmp_path, capsys):
    out = tmp_path / "cli.lovetown.json"
    assert export.main([str(SMALL_RUN), "--out", str(out)]) == 0
    assert "4 agents, 2 days, 3 dates, complete" in capsys.readouterr().out
    assert export.main([str(tmp_path / "missing.jsonl"), "--out", str(out)]) == 2
