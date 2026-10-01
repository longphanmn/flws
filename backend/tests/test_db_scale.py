"""§7 — the chronicle at scale: query plans and the numbers behind them.

Deliberately NO timing assertions. The plan's success criteria are measurements
("every latency target is a measurement, not an assertion"), and a wall-clock
assertion in the suite would flake on a loaded host. What IS asserted here is
structural — the query plan, the wasted-page bound, the side table's shape —
because those are the things that silently regress. The latencies are printed
so a run leaves the numbers on record.
"""

import json
import sqlite3
import time

import pytest

from app.config import Config
from app.db import Database
from app.main import MAJOR_EVENT_TYPES
from app.protocol import HistoryEvent

ROWS = 300_000
KINDS = ("war", "death", "birth", "temple", "fire", "bloom", "predation", "disaster", "miracle")


@pytest.fixture(scope="module")
def big(tmp_path_factory):
    """One world, 300k rows, a realistic payload mix. Built once for the module."""
    db = Database(str(tmp_path_factory.mktemp("scale") / "scale.db"))
    try:
        wid = db.new_world(Config(seed=1))
        for start in range(0, ROWS, 20_000):
            db.add_events(wid, [
                HistoryEvent(
                    type=KINDS[i % len(KINDS)], tick=i, entity_id=i % 5000,
                    caste="Soldier", cause="combat", x=1.0, y=2.0,
                    payload={"a": i % 40 + 1, "b": i % 17 + 1, "clan_id": i % 40 + 1,
                             "personal_name": f"creature-{i}", "lethal": True},
                )
                for i in range(start, start + 20_000)
            ])
        yield db, wid
    finally:
        db.close()


def _median_ms(call, runs: int = 5) -> float:
    call()
    samples = []
    for _ in range(runs):
        t0 = time.perf_counter()
        call()
        samples.append((time.perf_counter() - t0) * 1000)
    samples.sort()
    return round(samples[len(samples) // 2], 3)


def _plan_of(db, call) -> str:
    seen: list[str] = []
    db.connection.set_trace_callback(seen.append)
    call()
    db.connection.set_trace_callback(None)
    return " ; ".join(
        r["detail"] for r in db.connection.execute(
            "EXPLAIN QUERY PLAN " + seen[-1], (1,) * seen[-1].count("?")
        ).fetchall()
    )


def test_clan_filter_is_driven_by_the_side_table(big):
    """The clan filter must never walk the world.

    Measured failure mode: with `JOIN`, SQLite picks `events` as the driving
    table and probes event_clans per row — 351 ms at 2.7M rows against 0.32 ms
    for the pinned order. The plan string alone did not catch it (event_clans
    appears either way), so this asserts the driving table and the absence of a
    sort.
    """
    db, wid = big
    plan = _plan_of(db, lambda: db.history(wid, limit=200, clan_id=3))
    assert plan.startswith("SEARCH ec USING PRIMARY KEY"), plan
    assert "TEMP B-TREE" not in plan, plan
    assert "USING INDEX idx_events_world" not in plan, plan


def test_every_chronicle_read_is_index_served(big):
    db, wid = big
    assert "TEMP B-TREE" not in _plan_of(db, lambda: db.history(wid, limit=500)), "plain"
    assert "TEMP B-TREE" not in _plan_of(db, lambda: db.history(
        wid, limit=2000, types_filter=list(MAJOR_EVENT_TYPES))), "major"
    assert "TEMP B-TREE" not in _plan_of(db, lambda: db.history(wid, limit=500, entity_id=7)), "entity"
    assert "TEMP B-TREE" not in _plan_of(db, lambda: db.history(wid, limit=500, q="creature-7")), "q"


def test_death_count_is_a_single_row_read_at_scale(big):
    db, wid = big
    plan = _plan_of(db, lambda: db.death_count(wid))
    assert "world_stats" in plan, plan
    assert "events" not in plan, plan


def test_chronicle_stays_within_its_size_budget(big):
    """B/row must not creep: the whole point of dropping created_at and the
    16 KB rebuild. Loose bound on purpose — this catches a structural regression
    (a re-added column, a duplicated side table), not page-level noise."""
    db, wid = big
    census = db.db_census(deep=False)
    assert census["events"]["rows"] == ROWS
    assert census["events"]["bytes_per_row"] < 400, census["events"]
    assert census["side_tables"]["event_clans_bytes"] < census["tables"]["events"] / 2, census
    assert census["page_size"] == 16384


def test_measured_read_path_latencies(big, record_property):
    """Printed, not asserted: the §7 numbers for this replica."""
    db, wid = big
    numbers = {
        "history(clan_id=3, 200)": _median_ms(lambda: db.history(wid, limit=200, clan_id=3)),
        "history(major, 2000)": _median_ms(lambda: db.history(
            wid, limit=2000, types_filter=list(MAJOR_EVENT_TYPES))),
        "history(plain, 500)": _median_ms(lambda: db.history(wid, limit=500)),
        "history(entity_id=7, 500)": _median_ms(lambda: db.history(wid, limit=500, entity_id=7)),
        "death_count()": _median_ms(lambda: db.death_count(wid)),
        "history(q=creature-7, 500)": _median_ms(lambda: db.history(wid, limit=500, q="creature-7")),
    }
    record_property("read_path_ms", json.dumps(numbers, indent=2))
    print("\n[chronicle scale] " + json.dumps(numbers, indent=2))


def test_measured_wal_checkpoint(big, record_property):
    """A writer batch then TRUNCATE, on the live file (the §7 criterion 4 shape)."""
    db, wid = big
    conn = db.connection
    conn.execute("BEGIN")
    for i in range(2000):
        conn.execute(
            "INSERT INTO settings(key,value,created_at) VALUES (?,?,?)"
            " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (f"scale{i}", str(i), "t0"),
        )
    conn.execute("COMMIT")
    t0 = time.perf_counter()
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchall()
    ms = round((time.perf_counter() - t0) * 1000, 3)
    record_property("wal_checkpoint_truncate_ms", ms)
    print(f"\n[chronicle scale] wal_checkpoint(TRUNCATE): {ms} ms")


def test_api_history_handler_latency_at_scale(big, record_property):
    """The endpoint, not just the method: JSON encoding and the RAM overlay count."""
    from fastapi.testclient import TestClient

    from app.main import RT, app
    from app.simulation import Simulation

    RT.config = Config.from_env()
    RT.paused = True
    RT.speed = RT.config.tick_rate
    RT.sim = Simulation(RT.config)
    RT.world_id = big[1]
    client = TestClient(app)
    client.headers["X-God-Key"] = "test-key"
    samples = []
    for _ in range(12):
        t0 = time.perf_counter()
        r = client.get("/api/history?limit=500")
        assert r.status_code == 200, r.text
        samples.append((time.perf_counter() - t0) * 1000)
    samples.sort()
    p95 = round(samples[int(len(samples) * 0.95) - 1], 3)
    record_property("api_history_p95_ms", p95)
    print(f"\n[chronicle scale] /api/history p95 over 12 calls: {p95} ms "
          f"(median {round(samples[len(samples)//2], 3)} ms)")
    # a clan-filtered request is the path the side table exists for
    clan = []
    for _ in range(12):
        t0 = time.perf_counter()
        r = client.get("/api/history?clan_id=3&limit=500")
        assert r.status_code == 200, r.text
        clan.append((time.perf_counter() - t0) * 1000)
    clan.sort()
    print(f"[chronicle scale] /api/history?clan_id=3 p95: "
          f"{round(clan[int(len(clan) * 0.95) - 1], 3)} ms")
    record_property("api_history_clan_p95_ms", round(clan[int(len(clan) * 0.95) - 1], 3))


def test_drain_time_does_not_regress(big, tmp_path):
    """The writer path is a stated risk: 50k durable events must still drain in
    well under a second, because the writer thread holds the shared connection
    while API reads wait on it."""
    db = Database(str(tmp_path / "drain.db"))
    db._start_writer = lambda: None  # measure the flush itself, not the daemon race
    try:
        wid = db.new_world(Config(seed=1))
        for i in range(50_000):
            db.log_event(wid, HistoryEvent(
                type="war", tick=i, entity_id=i % 5000, caste="Soldier", cause="combat",
                x=1.0, y=2.0, payload={"a": i % 40 + 1, "b": i % 17 + 1, "lethal": True},
            ))
        t0 = time.perf_counter()
        written = db.flush()
        drain_ms = (time.perf_counter() - t0) * 1000
        assert written == 50_000
        print(f"\n[chronicle scale] drain 50k events: {drain_ms:.0f} ms")
        # 10x the pre-change measurement, so a structural regression still fails
        assert drain_ms < 5000, drain_ms
    finally:
        db.close()


def test_migrated_file_has_no_wasted_pages(big, tmp_path):
    """Vacuumed rebuild: no freelist left behind (92.7 MB of it on the 2.7M
    replica when the indexes were built before the rows)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "migrate_db", __import__("pathlib").Path(__file__).resolve().parents[1]
        / "scripts" / "migrate_db.py"
    )
    assert spec and spec.loader
    migrate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migrate)

    import test_db_migrate

    src = str(tmp_path / "scale_legacy.db")
    test_db_migrate._seed_legacy(src, worlds=1, per_world=ROWS // 8)
    report = migrate.migrate(src)
    assert report["verified"] is True
    conn = sqlite3.connect(report["target"])
    try:
        page_size = int(conn.execute("PRAGMA page_size").fetchone()[0])
        free = int(conn.execute("PRAGMA freelist_count").fetchone()[0])
        total = int(conn.execute("PRAGMA page_count").fetchone()[0])
        assert page_size == 16384
        assert free * page_size < 0.02 * total * page_size, (free, total, page_size)
        # ANALYZE must survive the VACUUM: the planner needs events statistics
        stats = conn.execute(
            "SELECT COUNT(*) FROM sqlite_stat1 WHERE tbl='events'"
        ).fetchone()[0]
        assert stats > 0, "VACUUM dropped the planner statistics for events"
    finally:
        conn.close()
