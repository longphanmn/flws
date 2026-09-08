"""Tests for §BM backend improvements:
- BM-22: /api/history/summary?granularity=day
- BM-23: clan_epitaphs table & persistence
- BM-24: creature death persistence of personal_name, title, kill_count
- BM-25: full-text / keyword search `q` parameter in /api/history
- BM-26: /api/annals endpoint
- BM-12: /api/clan/{clan_id}/biography endpoint
"""

import pytest
from fastapi.testclient import TestClient

from app.config import Config
from app.entities import Creature
from app.main import RT, DB, app, start_world
from app.protocol import HistoryEvent
from app.simulation import Simulation


def fresh_runtime():
    RT.config = Config.from_env()
    RT.paused = True
    RT.speed = RT.config.tick_rate
    RT.sim = Simulation(RT.config)
    start_world()


def test_history_summary_endpoint():
    fresh_runtime()

    # Add events on Day 0 (tick 100) and Day 1 (tick 1300) directly to DB
    events = [
        HistoryEvent(type="war", tick=100, entity_id=1, payload={"a": 1, "b": 2, "lethal": True}),
        HistoryEvent(type="death", tick=105, entity_id=2, cause="combat"),
        HistoryEvent(type="outbreak", tick=1300, entity_id=3, payload={"disease_id": 1}),
        HistoryEvent(type="temple", tick=1400, entity_id=4, payload={"clan_id": 1}),
    ]
    DB.add_events(RT.world_id, events)

    client = TestClient(app)
    res = client.get("/api/history/summary?granularity=day")
    assert res.status_code == 200
    data = res.json()
    assert "days" in data
    days = {d["day"]: d for d in data["days"]}
    assert 0 in days
    assert days[0]["wars"] >= 1
    assert days[0]["casualties"] >= 1
    assert 1 in days
    assert days[1]["outbreaks"] >= 1
    assert days[1]["faith_events"] >= 1


def test_annals_endpoint():
    fresh_runtime()

    events = [
        HistoryEvent(type="war", tick=500, entity_id=10, payload={"a": 1, "b": 2, "lethal": True, "winner_id": 10, "winner_name": "Ares"}),
        HistoryEvent(type="temple", tick=600, entity_id=20, payload={"clan_id": 1, "clan_name": "Order"}),
        HistoryEvent(type="miracle", tick=700, entity_id=30, payload={"clan_id": 1, "clan_name": "Order"}),
        HistoryEvent(type="clan_extinction", tick=800, entity_id=40, payload={"clan_id": 2, "name": "Fallen Clan"}),
    ]
    DB.add_events(RT.world_id, events)

    client = TestClient(app)
    res = client.get("/api/annals")
    assert res.status_code == 200
    annals = res.json()
    assert "milestones" in annals
    assert "notables" in annals
    assert annals["milestones"]["first_temple"] is not None
    assert annals["milestones"]["first_miracle"] is not None
    assert annals["milestones"]["first_extinction"] is not None
    assert annals["notables"]["hero"] is not None
    assert annals["notables"]["hero"]["name"] == "Ares"


def test_clan_biography_endpoint():
    fresh_runtime()
    s = RT.sim

    founder = s.world.add(Creature(x=100.0, y=100.0))
    cid = s._new_clan(founder)

    # Record epitaph in DB
    DB.record_clan_epitaph(
        world_id=RT.world_id,
        clan_id=cid,
        name="Ancient Order",
        totem="circle",
        color="#ff0000",
        founded_tick=10,
        extinct_tick=2500,
        peak_population=42,
        peak_tick=1200,
        wars_fought=5,
        battles_won=3,
        temples_built=2,
        schisms_caused=1,
        extinction_cause="starvation",
    )

    client = TestClient(app)
    res = client.get(f"/api/clan/{cid}/biography")
    assert res.status_code == 200
    bio = res.json()
    assert bio["clan"]["id"] == cid
    assert bio["epitaph"] is not None
    assert bio["epitaph"]["name"] == "Ancient Order"
    assert bio["epitaph"]["extinction_cause"] == "starvation"
    assert bio["epitaph"]["peak_population"] == 42


def test_history_search_q_parameter():
    fresh_runtime()

    events = [
        HistoryEvent(type="war", tick=200, entity_id=99, payload={"battlefield": "Crimson Valley", "general": "Leonidas"}),
        HistoryEvent(type="birth", tick=205, entity_id=101, payload={"personal_name": "Archimedes"}),
    ]
    DB.add_events(RT.world_id, events)

    client = TestClient(app)
    # Search for "Leonidas"
    res1 = client.get("/api/history?q=Leonidas")
    assert res1.status_code == 200
    events1 = res1.json()["events"]
    assert any("Leonidas" in str(e.get("payload")) for e in events1)

    # Search for "Archimedes"
    res2 = client.get("/api/history?q=Archimedes")
    assert res2.status_code == 200
    events2 = res2.json()["events"]
    assert any(e.get("payload", {}).get("personal_name") == "Archimedes" for e in events2)
