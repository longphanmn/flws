"""§AT-1 — clan history is complete and queryable: paginated endpoint, the
clan's internal log, and a SQL-level clan filter over the durable chronicle."""

import pytest
from fastapi.testclient import TestClient

from app.config import Config
from app.db import Database
from app.entities import Creature
from app.main import RT, app, start_world
from app.protocol import HistoryEvent
from app.simulation import Simulation


def fresh_runtime() -> None:
    RT.config = Config.from_env()
    RT.paused = True  # no engine thread in these tests
    RT.speed = RT.config.tick_rate
    RT.sim = Simulation(RT.config)
    start_world()


def test_clan_history_endpoint_paginates():
    fresh_runtime()

    # fabricate one clan + 55 war events naming it as the loser ("a")
    s = RT.sim
    founder = s.world.add(Creature(x=100.0, y=100.0))
    cid = s._new_clan(founder)
    for i in range(55):
        s.history.append(
            HistoryEvent(
                type="war", tick=i + 1, entity_id=100 + i,
                payload={"a": cid, "b": cid + 1, "lethal": False},
            )
        )
    s._log_clan_history(cid, "war_declared", "test milestone")

    c = TestClient(app)
    c.headers["X-God-Key"] = "test-key"

    r = c.get(f"/api/clans/{cid}/history?page=0&size=50")
    assert r.status_code == 200
    d = r.json()
    assert d["total"] == 55
    assert len(d["events"]) == 50
    assert d["has_more"] is True
    assert any(m["event"] == "war_declared" for m in d["log"])

    r2 = c.get(f"/api/clans/{cid}/history?page=1&size=50")
    d2 = r2.json()
    assert len(d2["events"]) == 5
    assert d2["has_more"] is False
    # newest first ordering across pages
    assert d["events"][0]["tick"] == 55
    assert d2["events"][0]["tick"] == 5


def test_history_db_filter_by_clan(tmp_path):
    """§AT-1: the durable chronicle stays queryable by clan after the
    in-memory deque rolls over."""
    db = Database(str(tmp_path / "t.db"))
    wid = db.new_world(Config(seed=1))
    events = [
        HistoryEvent(type="war", tick=1, entity_id=1,
                     payload={"a": 3, "b": 4, "lethal": True}),
        HistoryEvent(type="takeover", tick=2, entity_id=9,
                     payload={"invader_clan": 7, "victim_clan": 3}),
        HistoryEvent(type="birth", tick=3, entity_id=2,
                     payload={"mother": 10, "father": 11}),
        HistoryEvent(type="death", tick=4, entity_id=5,
                     payload={"clan_id": 3, "personal_name": "X"}),
    ]
    db.add_events(wid, events)
    got = db.history(wid, limit=100, clan_id=3)
    types = sorted(g["type"] for g in got)
    assert types == ["death", "takeover", "war"]
    assert db.history(wid, limit=100, clan_id=7)[0]["type"] == "takeover"
    assert db.history(wid, limit=100, clan_id=99) == []
    db.close()


# ------------------------------------------------------ §3.3 event_clans table
def test_clan_filter_is_answered_by_the_side_table(tmp_path):
    """The clan filter must be a covering-index lookup, not 13x json_extract.

    The old filter re-parsed the whole payload TEXT once per CLAN_PAYLOAD_KEYS
    (169-226 ms at 2.7M rows). The side table is written from the payload dict
    we already hold, so the query never touches JSON at all.
    """
    db = Database(str(tmp_path / "side.db"))
    try:
        wid = db.new_world(Config(seed=1))
        db.add_events(wid, [
            HistoryEvent(type="war", tick=i, entity_id=i,
                         payload={"a": 3, "b": 4, "lethal": True})
            for i in range(1, 51)
        ])
        rows = db.connection.execute(
            "SELECT clan_id, event_id FROM event_clans WHERE world_id=?", (wid,)
        ).fetchall()
        assert len(rows) == 100  # 50 wars x 2 sides, deduped per event
        assert {r["clan_id"] for r in rows} == {3, 4}  # both war sides recorded
        assert len(db.connection.execute(
            "SELECT 1 FROM event_clans WHERE world_id=? AND clan_id=3 LIMIT 1", (wid,)
        ).fetchall()) == 1

        # the query history() actually runs, and its plan
        seen: list[str] = []
        db.connection.set_trace_callback(seen.append)
        got = db.history(wid, limit=10, clan_id=3)
        db.connection.set_trace_callback(None)
        assert len(got) == 10 and got[0]["tick"] == 50  # newest first, limit honoured
        sql = seen[-1]
        assert "json_extract" not in sql
        plan = db.connection.execute(
            "EXPLAIN QUERY PLAN " + sql, (1,) * sql.count("?")
        ).fetchall()
        detail = " | ".join(r["detail"] for r in plan)
        assert "COVERING INDEX idx_event_clans" in detail, detail
        assert "TEMP B-TREE" not in detail, detail
    finally:
        db.close()


def test_side_table_is_written_by_the_ram_log_path_too(tmp_path):
    """log_event()+flush() is the production path; add_events() is the test seam.
    Both must populate event_clans or the clan filter silently loses events."""
    db = Database(str(tmp_path / "log.db"))
    try:
        wid = db.new_world(Config(seed=1))
        db.log_event(wid, HistoryEvent(type="takeover", tick=1, entity_id=1,
                                       payload={"invader_clan": 7, "victim_clan": 3}))
        db.flush()
        assert [e["type"] for e in db.history(wid, clan_id=7)] == ["takeover"]
    finally:
        db.close()


def test_clan_filter_keeps_payload_intact(tmp_path):
    """The side table is an index, not a replacement: the payload still answers."""
    db = Database(str(tmp_path / "payload.db"))
    try:
        wid = db.new_world(Config(seed=1))
        db.add_events(wid, [HistoryEvent(type="war", tick=1, entity_id=1,
                                         payload={"a": 3, "b": 4, "lethal": True})])
        assert db.history(wid, clan_id=3)[0]["payload"] == {"a": 3, "b": 4, "lethal": True}
    finally:
        db.close()


def test_side_table_ignores_non_clan_payload_values(tmp_path):
    """A clan id must be an int named by a CLAN_PAYLOAD_KEYS key — nothing else."""
    db = Database(str(tmp_path / "keys.db"))
    try:
        wid = db.new_world(Config(seed=1))
        db.add_events(wid, [
            HistoryEvent(type="war", tick=1, entity_id=1, payload={"general": 3, "a": 3}),
            HistoryEvent(type="war", tick=2, entity_id=2, payload={"a": "3"}),
            HistoryEvent(type="war", tick=3, entity_id=3, payload={"a": None}),
        ])
        assert [e["tick"] for e in db.history(wid, clan_id=3)] == [1]
    finally:
        db.close()


def test_api_history_accepts_clan_filter():
    fresh_runtime()
    c = TestClient(app)
    c.headers["X-God-Key"] = "test-key"
    r = c.get("/api/history?clan_id=1")
    assert r.status_code == 200
    body = r.json()
    for ev in body["events"]:
        payload = ev["payload"]
        named = [payload.get(k) for k in
                 ("a", "b", "clan_id", "parent", "new_clan",
                  "invader_clan", "victim_clan", "winner_clan", "loser_clan")]
        assert 1 in named
