"""Database layer tests: durable chronicle, worlds, and law history."""

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.config import Config
from app.db import Database
from app.main import DB, MAJOR_EVENT_TYPES, RT, _on_event, app, start_world
from app.protocol import HistoryEvent
from app.simulation import Simulation


@pytest.fixture(autouse=True)
def fresh_runtime():
    RT.config = Config.from_env()
    RT.paused = False
    RT.speed = RT.config.tick_rate
    RT.sim = Simulation(RT.config)
    start_world()
    yield


@pytest.fixture()
def client():
    c = TestClient(app)
    c.headers["X-God-Key"] = "test-key"
    return c


def test_world_row_created_and_listed(client):
    worlds = client.get("/api/worlds").json()["worlds"]
    assert len(worlds) >= 1
    assert worlds[0]["ended_at"] is None  # current world is still open
    assert worlds[0]["width"] == RT.config.width


def test_reset_closes_old_world_row(client):
    old_id = RT.world_id
    client.post("/api/control", json={"action": "reset"})
    assert RT.world_id != old_id
    rows = {w["id"]: w for w in client.get("/api/worlds").json()["worlds"]}
    assert rows[old_id]["ended_at"] is not None
    assert rows[RT.world_id]["ended_at"] is None


def test_death_event_persisted(client, extended_testclient_god_rate_limit):
    # famine + fast decay: starvation is inevitable under these laws
    client.post("/api/laws", json={"food_count": 0, "energy_decay_per_tick": 2.0})
    for _ in range(45):
        client.post("/api/control", json={"action": "step"})
    hist = client.get("/api/history").json()
    assert hist["world_id"] == RT.world_id
    assert hist["total_deaths"] >= 1
    deaths = [e for e in hist["events"] if e["type"] == "death"]
    assert deaths and any(d["cause"] == "starvation" for d in deaths)


def test_history_persists_across_reopen(client):
    wid = RT.world_id
    DB.add_events(wid, [HistoryEvent(tick=7, entity_id=1, caste="Noble", cause="starvation", x=1.0, y=2.0)])
    # simulate a restart: a brand-new Database instance over the same file
    fresh = Database(DB.path)
    try:
        rows = fresh.history(wid)
        assert any(e["tick"] == 7 and e["caste"] == "Noble" for e in rows)
        assert fresh.death_count(wid) >= 1
    finally:
        fresh.close()


def test_history_pagination(client):
    wid = RT.world_id
    DB.add_events(
        wid,
        [
            HistoryEvent(tick=t, entity_id=t, caste="Soldier", cause="starvation", x=0.0, y=0.0)
            for t in range(1, 6)
        ],
    )
    all_ids = [e["id"] for e in client.get("/api/history?limit=2000").json()["events"]]
    assert len(all_ids) >= 5
    page = client.get(f"/api/history?since={all_ids[-3]}&limit=2").json()["events"]
    assert [e["id"] for e in page] == all_ids[-2:]


def test_law_changes_recorded(client):
    r = client.post("/api/laws", json={"food_count": 5, "boundary": "clamp"})
    assert r.status_code == 200
    conn = sqlite3.connect(DB.path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT name FROM law_changes WHERE world_id=? ORDER BY id", (RT.world_id,)
        ).fetchall()
    finally:
        conn.close()
    names = [r["name"] for r in rows]
    assert sorted(names) == ["boundary", "food_count"]


def test_creature_endpoint_status_and_history(client):
    from app.entities import Creature

    c = RT.sim.world.add(Creature(x=5.0, y=5.0, sides=4, energy=77.0))
    DB.add_events(
        RT.world_id,
        [
            HistoryEvent(tick=1, entity_id=c.id, caste="Gentleman", cause="",
                         x=5.0, y=5.0,
                         payload={"mother": 2, "father": 3, "generation": 1},
                         type="birth"),
        ],
    )
    data = client.get(f"/api/creature/{c.id}").json()
    assert data["entity"]["caste"] == "Gentleman"
    assert data["entity"]["energy"] == pytest.approx(77.0)
    assert len(data["events"]) == 1
    assert data["events"][0]["type"] == "birth"
    assert data["events"][0]["payload"]["mother"] == 2

    # unknown / dead creature: entity null, chronicle still answers
    DB.add_events(
        RT.world_id,
        [HistoryEvent(tick=2, entity_id=c.id, caste="Gentleman", cause="starvation", x=5.0, y=5.0)],
    )
    RT.sim.world.remove(c.id)
    data = client.get(f"/api/creature/{c.id}").json()
    assert data["entity"] is None
    assert len(data["events"]) == 2


def test_genealogy_table_written(client):
    from app.entities import Creature

    # a birth writes the lineage row; a death closes it
    c = RT.sim.world.add(Creature(x=5.0, y=5.0, sides=4, energy=100.0))
    DB.add_events(
        RT.world_id,
        [
            HistoryEvent(
                type="birth", tick=3, entity_id=c.id, caste="Gentleman",
                x=5.0, y=5.0,
                payload={"mother": 2, "father": 1, "generation": 4, "clan_id": 7},
            )
        ],
    )
    _on_event(HistoryEvent(
        type="birth", tick=3, entity_id=c.id, caste="Gentleman",
        x=5.0, y=5.0,
        payload={"mother": 2, "father": 1, "generation": 4, "clan_id": 7},
    ))
    DB.flush()  # AD: genealogy rides the RAM log until the writer drains
    conn = sqlite3.connect(DB.path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM creatures WHERE world_id=? AND entity_id=?",
            (RT.world_id, c.id),
        ).fetchone()
        assert row is not None
        assert row["mother_id"] == 2 and row["father_id"] == 1
        assert row["generation"] == 4 and row["clan_id"] == 7
        assert row["died_tick"] is None

        RT.sim._kill(c, "starvation")  # records death via on_event too
        DB.flush()  # AD: drain the RAM tail before re-reading
        row = conn.execute(
            "SELECT died_tick FROM creatures WHERE world_id=? AND entity_id=?",
            (RT.world_id, c.id),
        ).fetchone()
        assert row["died_tick"] is not None
    finally:
        conn.close()


def test_creature_family_tree(client):

    from app.entities import Creature

    # mother (alive), father (dies -> genealogy card), child
    mother = RT.sim.world.add(Creature(x=5.0, y=5.0, shape="line", sides=2, energy=100.0))
    father = RT.sim.world.add(Creature(x=6.0, y=5.0, sides=4, energy=100.0))
    child = RT.sim.world.add(
        Creature(x=7.0, y=5.0, sides=4, energy=100.0,
                 mother_id=mother.id, father_id=father.id)
    )
    DB.add_creature(RT.world_id, father.id, "Gentleman", 0, 0, 0, 0, born_tick=0)
    DB.add_creature(RT.world_id, child.id, "Gentleman", 0, 1, mother.id, father.id, born_tick=0)

    fam = client.get(f"/api/creature/{child.id}").json()["family"]
    assert fam["mother"]["id"] == mother.id and fam["mother"]["alive"] is True
    assert fam["father"]["id"] == father.id

    # father dies: still resolvable via genealogy, marked dead
    RT.sim._kill(father, "starvation")
    fam = client.get(f"/api/creature/{child.id}").json()["family"]
    assert fam["father"]["id"] == father.id and fam["father"]["alive"] is False

    # child appears in the father's children list (dead or alive)
    kids = client.get(f"/api/creature/{father.id}").json()["family"]["children"]
    assert any(k["id"] == child.id for k in kids)


def test_events_survive_world_reset_in_db(client):
    wid_before = RT.world_id
    DB.add_events(wid_before, [HistoryEvent(tick=1, entity_id=9, caste="Priest", cause="old_age", x=5.0, y=5.0)])
    client.post("/api/control", json={"action": "reset"})
    # new world's history starts empty...
    assert client.get("/api/history").json()["total_deaths"] == 0
    # ...but the old world's chronicle is still queryable in the database
    assert DB.death_count(wid_before) >= 1


# --------------------------------------------------------------------- §AD OS-log
def test_ram_buffer_flush_semantics(client):
    """log_event queues in RAM; only flush() makes it durable."""
    wid = RT.world_id
    DB.log_event(wid, HistoryEvent(
        type="war", tick=1, entity_id=4242, caste="Soldier", cause="",
        x=1.0, y=2.0, payload={"a": 1, "b": 2},
    ))
    assert DB.pending >= 1

    # direct SQLite read must NOT see it before the flush (writer owns commits)
    conn = sqlite3.connect(DB.path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM events WHERE world_id=? AND entity_id=4242",
            (wid,),
        ).fetchone()
        assert row["n"] == 0
    finally:
        conn.close()

    written = DB.flush()
    assert written >= 1 and DB.pending == 0

    conn = sqlite3.connect(DB.path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT type, payload FROM events WHERE world_id=? AND entity_id=4242",
            (wid,),
        ).fetchone()
        assert row is not None and row["type"] == "war"
    finally:
        conn.close()


def test_log_birth_and_death_flow_through_the_buffer(client):
    from app.entities import Creature

    c = RT.sim.world.add(Creature(x=5.0, y=5.0, sides=4, energy=100.0))
    DB.log_birth(RT.world_id, entity_id=c.id, caste="Gentleman", clan_id=7,
                 generation=3, mother_id=2, father_id=1, born_tick=9)
    DB.log_death(RT.world_id, c.id, 33)
    assert DB.pending >= 2
    DB.flush()

    row = DB.genealogy_parents(RT.world_id, c.id)
    assert row[0] and row[0]["id"] == 2 and row[1] and row[1]["id"] == 1
    conn = sqlite3.connect(DB.path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT died_tick FROM creatures WHERE world_id=? AND entity_id=?",
            (RT.world_id, c.id),
        ).fetchone()
        assert row["died_tick"] == 33
    finally:
        conn.close()


def test_writer_thread_drains_without_help(tmp_path):
    """The daemon drains the buffer on its own heartbeat — no manual flush."""
    import time as _time
    from app.db import Database as _DB

    db = _DB(str(tmp_path / "writer.db"))
    db.connect()
    try:
        wid = db.new_world(RT.config)
        for i in range(5):
            db.log_event(wid, HistoryEvent(
                type="birth", tick=i, entity_id=i + 1, caste="Woman",
                x=0.0, y=0.0, payload={"generation": i},
            ))
        deadline = _time.monotonic() + 6.5  # one 5s heartbeat, generously
        while db.pending > 0 and _time.monotonic() < deadline:
            _time.sleep(0.05)
        assert db.pending == 0  # the writer drained it unprompted
        rows = db.history(wid, since_id=0, limit=10)
        assert len(rows) == 5
    finally:
        db.close()
    assert not db.connected


# --------------------------------------- §3.5 composite indexes + ANALYZE
def _plan_of(db, call) -> str:
    """The query Database actually runs, plus its EXPLAIN QUERY PLAN detail."""
    seen: list[str] = []
    db.connection.set_trace_callback(seen.append)
    call()
    db.connection.set_trace_callback(None)
    sql = seen[-1]
    rows = db.connection.execute("EXPLAIN QUERY PLAN " + sql, (1,) * sql.count("?")).fetchall()
    return " ; ".join(r["detail"] for r in rows)


@pytest.fixture()
def indexed_db(tmp_path):
    """A world with enough rows that the planner has a choice to make."""
    db = Database(str(tmp_path / "idx.db"))
    try:
        wid = db.new_world(RT.config)
        kinds = ["war", "death", "birth", "temple", "miracle", "bloom", "fire", "schism"]
        for start in range(0, 4000, 1000):
            db.add_events(wid, [
                HistoryEvent(type=kinds[i % len(kinds)], tick=start + i, entity_id=i % 50,
                             caste="Soldier", cause="combat", x=0.0, y=0.0,
                             payload={"a": i % 7})
                for i in range(start, start + 1000)
            ])
        yield db, wid
    finally:
        db.close()


def test_type_filtered_history_uses_the_type_index(indexed_db):
    db, wid = indexed_db
    plan = _plan_of(db, lambda: db.history(wid, type_filter="miracle", limit=100))
    assert "idx_events_world_type" in plan, plan
    assert "TEMP B-TREE" not in plan, plan


def test_major_history_never_sorts(indexed_db):
    """An IN-list over the major types must come back newest-first from an index."""
    db, wid = indexed_db
    types = list(MAJOR_EVENT_TYPES)
    plan = _plan_of(db, lambda: db.history(wid, types_filter=types, limit=500))
    assert "TEMP B-TREE" not in plan, plan
    assert "USING INDEX" in plan or "USING COVERING INDEX" in plan, plan
    got = db.history(wid, types_filter=types, limit=500)
    assert [e["id"] for e in got] == sorted((e["id"] for e in got), reverse=True)


def test_entity_history_uses_the_entity_index(indexed_db):
    db, wid = indexed_db
    plan = _plan_of(db, lambda: db.history(wid, entity_id=7, limit=100))
    assert "idx_events_world_entity" in plan, plan
    assert "TEMP B-TREE" not in plan, plan


def test_events_carry_exactly_three_indexes_in_newest_first_order(indexed_db):
    db, _ = indexed_db
    rows = db.connection.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='events'"
        " AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    assert {r["name"] for r in rows} == {
        "idx_events_world", "idx_events_world_type", "idx_events_world_entity"
    }
    for r in rows:
        assert "id DESC" in r["sql"], r["sql"]


# ------------------------------------------- final review: safety regressions
def _legacy_with_gap(path: str, ids=(1, 2, 5)) -> None:
    """A legacy events table whose ids have a GAP (a rolled-back insert), which is
    what breaks any rebuild that lets SQLite renumber the rows."""
    conn = sqlite3.connect(path)
    try:
        conn.executescript("""
        CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT, world_id INTEGER NOT NULL,
            tick INTEGER NOT NULL, type TEXT NOT NULL, entity_id INTEGER, caste TEXT, cause TEXT,
            x REAL, y REAL, payload TEXT, created_at TEXT NOT NULL);
        """)
        conn.executemany(
            "INSERT INTO events(id,world_id,tick,type,entity_id,caste,cause,x,y,payload,created_at)"
            " VALUES (?,1,?,'war',?,'S','',1.0,2.0,?,?)",
            [(i, i, i, json.dumps({"a": 3, "b": 4}), "t") for i in ids],
        )
        conn.commit()
    finally:
        conn.close()


def test_in_place_rebuild_preserves_event_ids(tmp_path):
    """`since_id` is the pagination cursor, so a rebuild must carry the ids over.

    Not copying `id` renumbers the rows whenever the source had a gap (a
    rolled-back insert), which silently breaks every stored cursor.
    """
    path = str(tmp_path / "gaps.db")
    _legacy_with_gap(path)
    db = Database(path)
    try:
        ids = [r["id"] for r in db.connection.execute(
            "SELECT id FROM events ORDER BY id")]
        assert ids == [1, 2, 5]
        assert [e["id"] for e in db.history(1, limit=10)] == [5, 2, 1]
    finally:
        db.close()


def test_in_place_rebuild_is_one_transaction(tmp_path, monkeypatch):
    """A failure mid-rebuild must leave the legacy table intact.

    `executescript()` COMMITs any open transaction, so wrapping the rebuild in
    batch() was not enough: DROP TABLE events and the RENAME were separate
    autocommits, and a crash between them came back as an EMPTY events table.
    """
    path = str(tmp_path / "atomic.db")
    _legacy_with_gap(path)
    real_connect = sqlite3.connect

    class Crashing(sqlite3.Connection):
        """Crashes immediately AFTER the table is dropped — the real failure point."""

        def execute(self, sql, *a, **kw):
            result = super().execute(sql, *a, **kw)
            if sql.strip().upper().startswith("DROP TABLE EVENTS"):
                raise sqlite3.OperationalError("simulated crash mid-rebuild")
            return result

    monkeypatch.setattr(
        sqlite3, "connect",
        lambda *a, **kw: real_connect(*a, factory=Crashing, **kw),
    )
    db = Database(path)
    with pytest.raises(sqlite3.OperationalError):
        db.connect()
    # the legacy rows are still there, ids and all
    raw = real_connect(path)
    try:
        rows = raw.execute("SELECT id, payload FROM events ORDER BY id").fetchall()
        assert [r[0] for r in rows] == [1, 2, 5]
        cols = {r[1] for r in raw.execute("PRAGMA table_info(events)")}
        assert "created_at" in cols  # untouched: the migration did not half-apply
    finally:
        raw.close()


def test_interrupted_rebuild_is_recovered_on_the_next_open(tmp_path):
    """A file left with the copy table still present must be finished, not replaced
    by a fresh empty `events`."""
    path = str(tmp_path / "half.db")
    conn = sqlite3.connect(path)
    try:
        conn.executescript("""
        CREATE TABLE events (id INTEGER PRIMARY KEY, world_id INTEGER NOT NULL, tick INTEGER NOT NULL,
            type TEXT NOT NULL, entity_id INTEGER, caste TEXT, cause TEXT, x REAL, y REAL, payload TEXT);
        CREATE TABLE events_lean (id INTEGER PRIMARY KEY, world_id INTEGER NOT NULL, tick INTEGER NOT NULL,
            type TEXT NOT NULL, entity_id INTEGER, caste TEXT, cause TEXT, x REAL, y REAL, payload TEXT);
        """)
        conn.executemany(
            "INSERT INTO events_lean(id,world_id,tick,type,entity_id,caste,cause,x,y,payload)"
            " VALUES (?,1,?,'war',?,'S','',1.0,2.0,?)",
            [(1, 1, 1, json.dumps({"a": 3})), (2, 2, 2, json.dumps({"a": 4}))],
        )
        conn.commit()
    finally:
        conn.close()
    db = Database(path)
    try:
        assert [r["id"] for r in db.connection.execute("SELECT id FROM events ORDER BY id")] == [1, 2]
        assert db.connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE name='events_lean'"
        ).fetchone()[0] == 0
    finally:
        db.close()


def test_side_table_backfill_is_not_blocked_by_a_seeded_counter(tmp_path):
    """A backfill skipped once (busy file) must be retried forever after.

    It used to be gated on `world_id NOT IN world_stats`, and `death_count()`
    seeds that row from COUNT(*) on the snapshot path — so one contended startup
    left event_clans permanently empty and every `?clan_id=` query answered [].
    """
    path = str(tmp_path / "retry.db")
    _legacy_with_gap(path)
    first = Database(path)
    try:
        first._backfill_side_tables = lambda: None  # as if the file had been locked
        first.connect()
        assert first.connection.execute(
            "SELECT COUNT(*) FROM event_clans").fetchone()[0] == 0
        first.death_count(1)  # the lifespan path seeds world_stats
    finally:
        first.close()
    second = Database(path)
    try:
        assert second.connection.execute(
            "SELECT COUNT(*) FROM event_clans").fetchone()[0] == 6
        assert len(second.history(1, clan_id=3)) == 3
    finally:
        second.close()


def test_death_count_does_not_join_an_open_flush_transaction(tmp_path):
    """The COUNT(*) fallback must not INSERT while a flush transaction is open.

    batch() drops the process lock for its whole body, so death_count() on the
    shared connection joined the writer's transaction: it seeded the row from the
    rows the flush had just written but not yet counted, and the flush's own bump
    then added the same deaths again. The total stuck at double.
    """
    db = Database(str(tmp_path / "race.db"))
    try:
        wid = db.new_world(RT.config)
        with db.batch():
            # the state a flush is in between writing the rows and bumping
            db.connection.execute(
                "INSERT INTO events(world_id,tick,type,entity_id,caste,cause,x,y,payload)"
                " VALUES (?,1,'death',1,'S','combat',1.0,2.0,'{}')", (wid,)
            )
            assert db.death_count(wid) == 1  # the fallback still answers
            assert db.connection.execute(
                "SELECT COUNT(*) FROM world_stats").fetchone()[0] == 0, \
                "the fallback wrote into someone else's transaction"
            db._insert_events(wid, [
                HistoryEvent(type="death", tick=2, entity_id=2, cause="combat")
            ])
        # The counter counts what the WRITER wrote: the manual INSERT above never
        # bumped it, so the total is the flush's own +1. Before the fix the
        # fallback had seeded 1 and the bump made it 2 — the doubled total.
        assert db.death_count(wid) == 1, "the deaths were counted twice"
        true_rows = db.connection.execute(
            "SELECT COUNT(*) AS n FROM events WHERE world_id=? AND type='death'", (wid,)
        ).fetchone()["n"]
        assert true_rows == 2  # the rows are all there; only the counter is the writer's
    finally:
        db.close()


def test_overlay_keeps_ring_events_when_the_durable_tail_is_full(tmp_path):
    """pending_events() must not spend the whole limit on one source.

    Each side used to stop at `limit` on its own, so with a full unflushed tail
    the noise ring contributed a single row — which is exactly the steady state
    the overlay exists for (5000 buffered ops, /api/history limit 500).
    """
    db = Database(str(tmp_path / "overlay.db"))
    try:
        wid = db.new_world(RT.config)
        for i in range(600):
            db.log_event(wid, HistoryEvent(type="war", tick=i, entity_id=i))
        for i in range(600, 610):
            db.log_event(wid, HistoryEvent(type="bloom", tick=i, entity_id=i))
        got = db.pending_events(wid, limit=500)
        assert len(got) == 500
        assert sum(1 for e in got if e["type"] == "bloom") == 10
        assert [e["tick"] for e in got] == sorted((e["tick"] for e in got), reverse=True)
    finally:
        db.close()


def test_log_event_waits_for_the_flush_lock(tmp_path):
    """log_event must synchronise with the writer's swap, or an append that lands
    between flush()'s list() and clear() is silently dropped."""
    import threading

    db = Database(str(tmp_path / "swap.db"))
    try:
        wid = db.new_world(RT.config)
        seen: list[int] = []

        def append_while_locked() -> None:
            db.log_event(wid, HistoryEvent(type="war", tick=1, entity_id=1))
            seen.append(db.pending)

        with db._lock:  # the writer is mid-swap
            worker = threading.Thread(target=append_while_locked)
            worker.start()
            worker.join(timeout=0.5)
            assert worker.is_alive(), "log_event bypassed the flush lock"
            assert seen == []
        worker.join(timeout=2.0)
        assert db.pending == 1
    finally:
        db.close()


def test_census_does_not_hold_the_process_lock(tmp_path, monkeypatch):
    """db_census() scans the whole chronicle; holding the process-wide lock makes
    every history() read and every flush() wait for it."""
    import threading

    import app.db as dbmod

    db = Database(str(tmp_path / "census.db"))
    try:
        wid = db.new_world(RT.config)
        db.add_events(wid, [HistoryEvent(type="war", tick=i, entity_id=i) for i in range(200)])

        seen: list[bool] = []

        def can_another_thread_take_the_lock() -> bool:
            got: list[bool] = []

            def try_it() -> None:
                got.append(db._lock.acquire(timeout=0.05))
                if got[-1]:
                    db._lock.release()

            worker = threading.Thread(target=try_it)
            worker.start()
            worker.join(timeout=2.0)
            return bool(got and got[0])

        class Probing(frozenset):
            """Fires while the census is inside its scan; a reentrant lock cannot be
            probed from the owning thread, so this asks another thread."""

            def __contains__(self, item):
                seen.append(can_another_thread_take_the_lock())
                return frozenset.__contains__(self, item)

        monkeypatch.setattr(dbmod, "_EVENT_INDEX_NAMES", Probing(dbmod._EVENT_INDEX_NAMES))
        db.db_census(deep=True)
        assert seen, "the probe never fired, so the lock was never exercised"
        assert all(seen), "db_census() held the process lock while scanning"
    finally:
        db.close()


def test_reopening_a_healthy_file_keeps_its_planner_statistics(tmp_path, monkeypatch):
    """connect() must not touch a file that is already in the target shape.

    Measured failure: SQLite stores an index's DDL WITHOUT the `IF NOT EXISTS`
    clause it was created with, so a whole-statement comparison never matched and
    every open DROPPED and rebuilt all three events indexes — which also deletes
    their sqlite_stat1 rows. On the 2.7M-row replica the clan filter went from
    0.3 ms to 468 ms after one reconnect, and on a 5 GB file the rebuild itself
    would cost minutes of startup.

    The ceiling is pinned to 0 so startup ANALYZE is skipped, which is the
    production case: a migrated multi-GB file has its statistics from the offline
    tool, and nothing on the open path may remove them.
    """
    import app.db as dbmod

    path = str(tmp_path / "healthy.db")
    db = Database(path)
    try:
        wid = db.new_world(RT.config)
        db.add_events(wid, [
            HistoryEvent(type="war", tick=i, entity_id=i, payload={"a": i % 5 + 1})
            for i in range(500)
        ])
    finally:
        db.close()
    # a migrated file arrives with statistics already in place
    seeded = sqlite3.connect(path)
    try:
        seeded.execute("ANALYZE")
        seeded.commit()
        assert seeded.execute("SELECT COUNT(*) FROM sqlite_stat1").fetchone()[0] > 0
    finally:
        seeded.close()

    def snapshot() -> tuple:
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        try:
            return (
                sorted((r["name"], r["sql"]) for r in conn.execute(
                    "SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='events'")),
                sorted((r["tbl"], r["idx"], r["stat"]) for r in conn.execute(
                    "SELECT tbl, idx, stat FROM sqlite_stat1")),
            )
        finally:
            conn.close()

    monkeypatch.setattr(dbmod, "INPLACE_MIGRATE_MAX_ROWS", 0)
    before = snapshot()
    reopened = Database(path)
    try:
        reopened.connect()  # this is the open path that must not touch the file
    finally:
        reopened.close()
    assert snapshot() == before


def test_connect_survives_a_locked_file(tmp_path, monkeypatch):
    """A second connection holding the write lock must not break connect().

    The guarded index/ANALYZE steps are OPTIMISATIONS on an already-correct
    schema, so a busy database must not stop the service from opening — the
    pre-3.5 connect() swallowed exactly these errors. Observed once in the full
    suite as an intermittent sqlite3.OperationalError out of connect().
    """
    import app.db as dbmod

    monkeypatch.setattr(dbmod, "BUSY_TIMEOUT_MS", 50)
    path = str(tmp_path / "locked.db")
    db = Database(path)
    try:
        wid = db.new_world(RT.config)
        db.add_events(wid, [HistoryEvent(type="war", tick=i, entity_id=i) for i in range(10)])
    finally:
        db.close()

    blocker = sqlite3.connect(path, isolation_level=None)
    try:
        blocker.execute("BEGIN EXCLUSIVE")
        blocker.execute("INSERT INTO settings(key,value,created_at) VALUES ('k','v','t0')")
        fresh = Database(path)  # must not raise
        try:
            fresh.connect()
            assert fresh.connected is True
        finally:
            fresh.close()
    finally:
        blocker.execute("ROLLBACK")
        blocker.close()


def test_legacy_indexes_are_replaced_on_connect(tmp_path):
    """A file carrying the old 2-column indexes must not keep them: the plan's
    10.8 -> 3.2 ms claim rests on the index actually in use."""
    path = str(tmp_path / "old_idx.db")
    _seed_legacy_db(path)
    db = Database(path)
    try:
        rows = db.connection.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='events'"
        ).fetchall()
        by_name = {r["name"]: r["sql"] for r in rows}
        assert set(by_name) >= {"idx_events_world", "idx_events_world_type",
                                "idx_events_world_entity"}
        for name, sql in by_name.items():
            if name == "idx_events_world_entity":
                continue  # already (world_id, entity_id, id DESC) in the legacy file
            assert "id DESC" in sql, (name, sql)
    finally:
        db.close()


def test_planner_stats_exist_after_connect(tmp_path):
    """§3.5: ANALYZE gives the planner statistics; without them it guesses.

    Stats are computed at startup, so the file gets them on the next open — the
    test reflects that: seed rows, reopen, then look.
    """
    path = str(tmp_path / "stats_analyze.db")
    db = Database(path)
    try:
        wid = db.new_world(RT.config)
        db.add_events(wid, [HistoryEvent(type="war", tick=i, entity_id=i) for i in range(200)])
    finally:
        db.close()
    reopened = Database(path)
    try:
        assert int(reopened.connection.execute(
            "SELECT COUNT(*) AS n FROM sqlite_stat1 WHERE tbl='events'"
        ).fetchone()["n"]) > 0
    finally:
        reopened.close()


# ------------------------------------------------- §3.5 lean schema + pragmas
LEGACY_EVENTS_DDL = """
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    world_id INTEGER NOT NULL,
    tick INTEGER NOT NULL,
    type TEXT NOT NULL,
    entity_id INTEGER,
    caste TEXT,
    cause TEXT,
    x REAL,
    y REAL,
    payload TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX idx_events_world ON events(world_id, id);
CREATE INDEX idx_events_world_type ON events(world_id, type);
"""


def _seed_legacy_db(path, page_size: int = 4096) -> None:
    """A pre-§3.5 file: 4 KB pages, created_at, AUTOINCREMENT, the old indexes."""
    conn = sqlite3.connect(path)
    try:
        conn.execute(f"PRAGMA page_size={page_size}")
        conn.execute("CREATE TABLE worlds (id INTEGER PRIMARY KEY AUTOINCREMENT, seed INTEGER)")
        conn.execute("INSERT INTO worlds(id, seed) VALUES (1, 7)")
        conn.executescript(LEGACY_EVENTS_DDL)
        rows = [
            (1, 1, "war", 1, "Soldier", "", 1.0, 2.0, json.dumps({"a": 3, "b": 4}), "t0"),
            (1, 2, "death", 2, "Soldier", "combat", 1.0, 2.0, json.dumps({"clan_id": 3}), "t0"),
            (1, 3, "bloom", 3, None, "", 0.0, 0.0, json.dumps({"n": 1}), "t0"),
        ]
        conn.executemany(
            "INSERT INTO events(world_id,tick,type,entity_id,caste,cause,x,y,payload,created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            rows,
        )
        conn.commit()
    finally:
        conn.close()


def test_fresh_database_uses_16kb_pages(tmp_path):
    db = Database(str(tmp_path / "pages.db"))
    try:
        assert db.connection.execute("PRAGMA page_size").fetchone()[0] == 16384
        assert db.needs_rebuild is False
    finally:
        db.close()


def test_events_table_is_lean(tmp_path):
    """No created_at (derivable from id, 12.6% of the bytes) and no AUTOINCREMENT."""
    db = Database(str(tmp_path / "lean.db"))
    try:
        cols = {r["name"] for r in db.connection.execute("PRAGMA table_info(events)")}
        assert cols == {"id", "world_id", "tick", "type", "entity_id", "caste",
                        "cause", "x", "y", "payload"}
        ddl = db.connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='events'"
        ).fetchone()["sql"]
        assert "AUTOINCREMENT" not in ddl
        assert db.connection.execute(
            "SELECT COUNT(*) AS n FROM sqlite_sequence WHERE name='events'"
        ).fetchone()["n"] == 0
    finally:
        db.close()


def test_legacy_file_is_migrated_on_connect(tmp_path):
    """A pre-§3.5 file must come up lean, with its history, side table and counter."""
    path = str(tmp_path / "legacy.db")
    _seed_legacy_db(path)
    db = Database(path)
    try:
        cols = {r["name"] for r in db.connection.execute("PRAGMA table_info(events)")}
        assert "created_at" not in cols
        # history survived, payload intact
        got = db.history(1, limit=10)
        assert [e["type"] for e in got] == ["bloom", "death", "war"]
        assert got[-1]["payload"] == {"a": 3, "b": 4}
        # the side table and the counter were backfilled from the old rows
        assert [e["tick"] for e in db.history(1, clan_id=3)] == [2, 1]
        assert db.death_count(1) == 1
        counter = db.connection.execute(
            "SELECT death_count FROM world_stats WHERE world_id=1"
        ).fetchone()
        assert int(counter["death_count"]) == 1
    finally:
        db.close()


def test_legacy_4kb_file_is_not_faked_into_16kb(tmp_path):
    """page_size cannot change in place: the file reports it needs the offline tool."""
    path = str(tmp_path / "small.db")
    _seed_legacy_db(path)
    db = Database(path)
    try:
        assert db.connection.execute("PRAGMA page_size").fetchone()[0] == 4096
        assert db.needs_rebuild is True
    finally:
        db.close()


def test_huge_legacy_file_refuses_the_in_place_path(tmp_path, monkeypatch):
    """Above the ceiling, connect() must refuse and name the offline tool —
    it must never start copying gigabytes while the service waits."""
    import app.db as dbmod

    path = str(tmp_path / "huge.db")
    _seed_legacy_db(path)
    monkeypatch.setattr(dbmod, "INPLACE_MIGRATE_MAX_ROWS", 1)
    db = Database(path)
    try:
        with pytest.raises(RuntimeError, match="migrate_db.py"):
            db.connect()
        # the legacy table is still intact — the refusal changed nothing
        legacy = sqlite3.connect(path)
        try:
            cols = {r[1] for r in legacy.execute("PRAGMA table_info(events)")}
            assert "created_at" in cols
            assert legacy.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 3
        finally:
            legacy.close()
    finally:
        db.close()


def test_mmap_is_clamped_to_the_machine(tmp_path):
    """A fixed 256 MB mmap thrashes on a 5 GB file; clamp to min(1 GiB, RAM/4)."""
    import os as _os

    ram = _os.sysconf("SC_PAGE_SIZE") * _os.sysconf("SC_PHYS_PAGES")
    db = Database(str(tmp_path / "mmap.db"))
    try:
        mmap = db.connection.execute("PRAGMA mmap_size").fetchone()[0]
        assert mmap == min(1 << 30, ram // 4), (mmap, min(1 << 30, ram // 4))
    finally:
        db.close()


# --------------------------------------------------------- §3.4 world_stats
def _true_death_count(db, wid: int) -> int:
    row = db.connection.execute(
        "SELECT COUNT(*) AS n FROM events WHERE world_id=? AND type='death'", (wid,)
    ).fetchone()
    return int(row["n"])


def test_death_count_is_exact_across_mixed_flushes(tmp_path):
    """The counter must agree with COUNT(*) after 10k events in many batches."""
    db = Database(str(tmp_path / "stats.db"))
    try:
        wid = db.new_world(RT.config)
        kinds = ["birth", "death", "war", "temple", "death", "outbreak"]
        for batch in range(20):
            for i in range(500):
                db.log_event(wid, HistoryEvent(
                    type=kinds[i % len(kinds)], tick=batch * 500 + i, entity_id=i,
                    caste="Soldier", cause="combat", x=0.0, y=0.0,
                    payload={"a": i % 5},
                ))
            db.flush()
            assert db.death_count(wid) == _true_death_count(db, wid)
        assert db.death_count(wid) == 20 * 167  # 2 death kinds of 6
        # ...and it is a materialized counter, not a scan
        counter = db.connection.execute(
            "SELECT death_count FROM world_stats WHERE world_id=?", (wid,)
        ).fetchone()
        assert counter is not None and int(counter["death_count"]) == 20 * 167
    finally:
        db.close()


def test_death_count_rolls_back_with_a_failed_flush(tmp_path):
    """A flush that dies mid-transaction must not leave the counter ahead of
    the rows — otherwise the next world starts from a phantom death count."""
    db = Database(str(tmp_path / "rollback.db"))
    try:
        wid = db.new_world(RT.config)
        real_insert = db._insert_events

        def insert_then_fail(wid_, events):
            real_insert(wid_, events)
            raise sqlite3.OperationalError("simulated writer failure")

        db._insert_events = insert_then_fail
        db.log_event(wid, HistoryEvent(type="death", tick=1, entity_id=1, cause="combat"))
        assert db.flush() == 0
        assert _true_death_count(db, wid) == 0
        assert db.death_count(wid) == 0
        assert db.pending == 1  # re-queued for the next heartbeat

        # the retry lands both the row and the count
        db._insert_events = real_insert
        assert db.flush() == 1
        assert _true_death_count(db, wid) == 1
        assert db.death_count(wid) == 1
    finally:
        db.close()


def test_death_count_is_a_counter_read_not_a_count_star(tmp_path):
    """§3.4: the hot path must not scan the events table (9 ms at 2.7M rows)."""
    db = Database(str(tmp_path / "fast.db"))
    try:
        wid = db.new_world(RT.config)
        db.add_events(wid, [HistoryEvent(type="death", tick=i, entity_id=i) for i in range(50)])
        seen: list[str] = []
        db.connection.set_trace_callback(seen.append)
        assert db.death_count(wid) == 50
        db.connection.set_trace_callback(None)
        assert "world_stats" in seen[-1], seen[-1]
        assert "events" not in seen[-1], seen[-1]  # the 2.7M-row table is not touched
        assert "COUNT(*)" not in seen[-1].upper(), seen[-1]
    finally:
        db.close()


def test_death_count_covers_the_add_events_seam(tmp_path):
    """add_events() writes death rows without a genealogy op; the count must see them."""
    db = Database(str(tmp_path / "seam.db"))
    try:
        wid = db.new_world(RT.config)
        db.add_events(wid, [
            HistoryEvent(type="death", tick=1, entity_id=1),
            HistoryEvent(type="birth", tick=2, entity_id=2),
        ])
        assert db.death_count(wid) == 1
    finally:
        db.close()
