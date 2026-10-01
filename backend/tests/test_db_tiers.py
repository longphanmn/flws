"""Tiered chronicle (§3.2 Lever 1) — the growth-rate bound on the events table.

The production `flatworld.db` reached 5 GB because every emitted event type was
written to SQLite forever. Retention is explicitly NOT the lever (the user chose
"keep the record"); the lever is *tiering*:

- ``MILESTONE`` — always durable.
- ``SAMPLED``   — durable 1 in ``CHRONICLE_SAMPLE_EVERY``; never dropped entirely.
- ``NOISE``     — RAM ring only, never touches SQLite, still readable via the
  ``pending_events()`` overlay so the web/TUI keeps its recent texture.

Nothing is deleted, so the *record* survives: what the bound changes is the
write RATE, which is what made the file climb.
"""

import sqlite3
import typing

import pytest

from app.config import Config
from app.db import (
    CHRONICLE_SAMPLE_EVERY,
    EVENT_TIERS,
    NOISE_PER_TICK_CAP,
    NOISE_RING_MAX,
    Database,
)
from app.protocol import HistoryEvent

TIERS = ("MILESTONE", "SAMPLED", "NOISE")


def _ev(type_: str, tick: int = 1, entity_id: int = 1, **payload) -> HistoryEvent:
    return HistoryEvent(type=type_, tick=tick, entity_id=entity_id, payload=payload or {})


@pytest.fixture()
def db(tmp_path):
    d = Database(str(tmp_path / "tiers.db"))
    d.connect()
    try:
        yield d
    finally:
        d.close()


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    from app.main import RT, app, start_world
    from app.simulation import Simulation

    RT.config = Config.from_env()
    RT.paused = True  # no engine thread here
    RT.speed = RT.config.tick_rate
    RT.sim = Simulation(RT.config)
    start_world()
    c = TestClient(app)
    c.headers["X-God-Key"] = "test-key"
    return c


def _event_rows(db: Database, wid: int) -> list[tuple]:
    conn = sqlite3.connect(db.path)
    try:
        return conn.execute(
            "SELECT type, tick FROM events WHERE world_id=? ORDER BY id", (wid,)
        ).fetchall()
    finally:
        conn.close()


# ------------------------------------------------------------- classification
def test_every_emittable_type_is_classified_into_exactly_one_tier():
    """No type may be unclassified (silent full-persistence) or doubly classified."""
    emittable = typing.get_args(HistoryEvent.model_fields["type"].annotation)
    assert len(emittable) > 40  # guard: the closed Literal really is the source of truth
    unclassified = [t for t in emittable if t not in EVENT_TIERS]
    assert unclassified == [], f"types with no tier (they would persist forever): {unclassified}"
    assert set(EVENT_TIERS.values()) <= set(TIERS)
    extra = [t for t in EVENT_TIERS if t not in emittable]
    assert extra == [], f"tier map names types the model cannot emit: {extra}"


def test_lifecycle_and_major_types_are_always_milestones():
    """death/birth keep the death counter exact; MAJOR_EVENT_TYPES stay durable."""
    always = (
        "death", "birth", "war", "conquest", "takeover", "schism", "betrayal",
        "alliance", "coalition_formed", "peace", "regicide", "succession",
        "outbreak", "disaster", "miracle", "synod", "temple", "epiphany",
        "extinction", "clan_extinction", "promotion", "ruin", "exile",
        "settlement", "banquet",
    )
    assert [t for t in always if EVENT_TIERS[t] != "MILESTONE"] == []


def test_noise_types_are_the_ones_already_filtered_plus_the_ambient_set():
    for t in ("bloom", "wither", "culture", "rivalry", "peace_envoy"):
        assert EVENT_TIERS[t] == "NOISE", t
    for t in ("fire", "predation", "cannibalism", "raid", "market", "caravan",
              "demotion", "recovery"):
        assert EVENT_TIERS[t] == "SAMPLED", t


def test_classify_is_stable_within_a_tick_and_resets_on_the_next_tick(db):
    for i in range(NOISE_PER_TICK_CAP):
        assert db.classify(_ev("fire", tick=10, entity_id=i)) == "SAMPLED"
    # burst beyond the per-tick cap degrades to NOISE (ring only)
    assert db.classify(_ev("fire", tick=10, entity_id=99)) == "NOISE"
    # the counter is per-tick: a new tick gets a fresh budget
    assert db.classify(_ev("fire", tick=11, entity_id=100)) == "SAMPLED"
    # milestones are never burst-capped
    for i in range(NOISE_PER_TICK_CAP + 5):
        assert db.classify(_ev("war", tick=10, entity_id=200 + i)) == "MILESTONE"


# ------------------------------------------------------------------- routing
def test_milestone_is_durable_and_noise_only_lives_in_the_ring(db):
    wid = db.new_world(Config(seed=1))
    db.log_event(wid, _ev("temple", tick=1, entity_id=7, clan_id=3))
    db.log_event(wid, _ev("bloom", tick=1, entity_id=8))
    db.log_event(wid, _ev("wither", tick=1, entity_id=9))
    # read-your-writes: all three visible before the flush
    assert {e["type"] for e in db.pending_events(wid)} == {"temple", "bloom", "wither"}

    db.flush()

    assert _event_rows(db, wid) == [("temple", 1)]
    # the durable one is now a real row; the ring still serves the texture
    assert {e["type"] for e in db.pending_events(wid)} == {"bloom", "wither"}


def test_sampled_events_reach_sqlite_one_in_n(db):
    wid = db.new_world(Config(seed=1))
    for i in range(CHRONICLE_SAMPLE_EVERY * 3):
        db.log_event(wid, _ev("predation", tick=i + 1, entity_id=i))
    db.flush()
    assert len(_event_rows(db, wid)) == 3


def test_sampled_burst_beyond_the_per_tick_cap_is_not_sampled(db):
    wid = db.new_world(Config(seed=1))
    for i in range(NOISE_PER_TICK_CAP + 5):
        db.log_event(wid, _ev("fire", tick=1, entity_id=i))
    db.flush()
    assert _event_rows(db, wid) == []


def test_noise_ring_is_bounded_and_never_grows_the_pending_buffer(db):
    wid = db.new_world(Config(seed=1))
    for i in range(NOISE_RING_MAX + 500):
        db.log_event(wid, _ev("bloom", tick=i, entity_id=i))
    assert db.noise_pending == NOISE_RING_MAX
    assert db.pending == 0  # the RAM log queue stays empty — noise never writes
    assert len(db.pending_events(wid, limit=NOISE_RING_MAX)) == NOISE_RING_MAX


def test_ring_and_durable_events_merge_newest_first(db):
    wid = db.new_world(Config(seed=1))
    db.log_event(wid, _ev("bloom", tick=1, entity_id=1))
    db.log_event(wid, _ev("temple", tick=2, entity_id=2))
    db.log_event(wid, _ev("wither", tick=3, entity_id=3))
    assert [e["tick"] for e in db.pending_events(wid)] == [3, 2, 1]


def test_ring_is_scoped_to_its_world(db):
    wid_a = db.new_world(Config(seed=1))
    wid_b = db.new_world(Config(seed=2))
    db.log_event(wid_a, _ev("bloom", tick=1))
    db.log_event(wid_b, _ev("temple", tick=1))
    assert [e["type"] for e in db.pending_events(wid_b)] == ["temple"]
    assert [e["type"] for e in db.pending_events(wid_a)] == ["bloom"]


# ------------------------------------------------------------- the app sink
def test_app_sink_delegates_tiering_to_the_database(client):
    """main._on_event keeps no type filter of its own: the Database decides.

    A bloom must cost no SQLite write, yet /api/history must still show it.
    """
    from app.main import DB, RT, _on_event

    wid = RT.world_id
    _on_event(_ev("bloom", tick=1, entity_id=9001))
    _on_event(_ev("temple", tick=1, entity_id=9002, clan_id=4))
    DB.flush()

    conn = sqlite3.connect(DB.path)
    try:
        rows = conn.execute(
            "SELECT type FROM events WHERE world_id=? AND entity_id IN (9001, 9002)",
            (wid,),
        ).fetchall()
    finally:
        conn.close()
    assert rows == [("temple",)]  # the bloom never reached SQLite

    body = client.get("/api/history?limit=2000").json()
    types = {e["type"] for e in body["events"] if e["entity_id"] in (9001, 9002)}
    assert types == {"bloom", "temple"}  # ...but it is still served to the UI
