"""§3.2/§8 — the db-census: measure the chronicle instead of guessing its shape.

The plan's tier map (SAMPLED/NOISE membership) was inferred from a headless run
that produced ~180 MB where production has 5 GB, so the real event mix is
unknown. `db_census()` is the instrument that settles it: row counts, bytes per
row, bytes per type, bytes per index, and — the part that matters for tuning —
which durable types are the biggest byte sinks and what tier they sit in today.
"""

import pytest
from fastapi.testclient import TestClient

from app.config import Config
from app.db import EVENT_TIERS, Database
from app.main import RT, app, start_world
from app.protocol import HistoryEvent
from app.simulation import Simulation


@pytest.fixture()
def seeded(tmp_path):
    db = Database(str(tmp_path / "census.db"))
    try:
        wid = db.new_world(Config(seed=1))
        db.add_events(wid, [
            HistoryEvent(type="war", tick=i, entity_id=i, caste="Soldier", cause="combat",
                         x=0.0, y=0.0, payload={"a": i % 3 + 1, "b": i % 5 + 1})
            for i in range(1, 61)
        ] + [
            HistoryEvent(type="temple", tick=100 + i, entity_id=i, payload={"clan_id": 1})
            for i in range(1, 11)
        ] + [
            HistoryEvent(type="fire", tick=200 + i, entity_id=i, payload={"trees": 12})
            for i in range(1, 41)
        ])
        yield db, wid
    finally:
        db.close()


def test_census_reports_size_and_shape(seeded):
    db, wid = seeded
    c = db.db_census()
    assert c["events"]["rows"] == 110
    assert c["events"]["bytes"] > 0
    assert 0 < c["events"]["bytes_per_row"] < 100_000
    assert c["page_size"] == 16384
    assert c["needs_rebuild"] is False
    assert c["file_bytes"] > 0
    assert c["wal_bytes"] >= 0
    assert c["planner_stats"] is True


def test_census_attributes_bytes_per_type_and_index(seeded):
    db, _ = seeded
    c = db.db_census()
    by_type = {t["type"]: t for t in c["types"]}
    assert by_type["war"]["rows"] == 60
    assert by_type["temple"]["rows"] == 10
    assert by_type["fire"]["rows"] == 40
    assert sum(t["rows"] for t in c["types"]) == 110
    for t in c["types"]:
        assert t["tier"] == EVENT_TIERS[t["type"]]
    assert c["indexes"]["idx_event_clans"] > 0
    assert c["tables"]["events"] > 0
    assert c["side_tables"]["event_clans_rows"] > 0
    assert c["worlds"][0]["world_id"] == seeded[1]
    assert c["worlds"][0]["rows"] == 110


def test_census_ranks_the_types_worth_retuning(seeded):
    """The tuning signal: durable types by byte cost, so the tier map can be
    re-cut from production evidence instead of a headless guess."""
    db, _ = seeded
    c = db.db_census(deep=True)
    ranked = c["byte_sinks"]
    assert ranked, "a census with rows must name its biggest byte sinks"
    assert [r["type"] for r in ranked] == sorted(
        (r["type"] for r in ranked), key=lambda t: -next(
            x["payload_bytes"] for x in c["types"] if x["type"] == t
        )
    )
    top = ranked[0]
    assert top["rows"] > 0 and top["payload_bytes"] > 0
    assert top["tier"] in EVENT_TIERS.values()
    # the cheap (non-deep) census still ranks by rows, which is enough to retune
    assert db.db_census()["byte_sinks"][0]["type"] == "war"


def test_census_endpoint_is_reachable():
    RT.config = Config.from_env()
    RT.paused = True
    RT.speed = RT.config.tick_rate
    RT.sim = Simulation(RT.config)
    start_world()
    c = TestClient(app)
    c.headers["X-God-Key"] = "test-key"
    r = c.get("/api/diagnostics/db-census")
    assert r.status_code == 200, r.text
    body = r.json()
    for key in ("file_bytes", "page_size", "events", "types", "tiers",
                "indexes", "tables", "worlds", "side_tables",
                "planner_stats", "needs_rebuild", "wal_bytes"):
        assert key in body, key
    assert body["events"]["rows"] >= 0
    # the tier map is visible from production — that is the whole point
    assert "bloom" in body["tiers"]["NOISE"]["types"]
    assert "fire" in body["tiers"]["SAMPLED"]["types"]
    assert "death" in body["tiers"]["MILESTONE"]["types"]
    assert body["tuning"]["sample_every"] == 10


def test_census_proves_noise_never_reaches_the_table():
    """A NOISE type with rows in the table would mean the tiering leaked."""
    RT.config = Config.from_env()
    RT.paused = True
    RT.speed = RT.config.tick_rate
    RT.sim = Simulation(RT.config)
    start_world()
    from app.main import DB

    DB.log_event(RT.world_id, HistoryEvent(type="bloom", tick=1, entity_id=1))
    DB.log_event(RT.world_id, HistoryEvent(type="temple", tick=1, entity_id=2))
    DB.flush()
    c = TestClient(app)
    c.headers["X-God-Key"] = "test-key"
    tiers = c.get("/api/diagnostics/db-census").json()["tiers"]
    assert tiers["NOISE"]["rows"] == 0
    assert tiers["MILESTONE"]["rows"] >= 1


def test_census_deep_flag_does_not_change_the_row_counts(seeded):
    db, _ = seeded
    assert db.db_census()["events"]["rows"] == db.db_census(deep=True)["events"]["rows"]
