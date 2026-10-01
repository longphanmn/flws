"""§3.6 — the offline rebuild: `backend/scripts/migrate_db.py`.

A populated SQLite file cannot change its page size, so the 16 KB / lean-schema
win needs a full rebuild. This is the authorized offline path:

    backup -> rebuild at 16 KB pages from the live schema definition -> stream
    every table -> build event_clans + world_stats in the same pass -> ANALYZE ->
    verify per-world row counts and an events checksum -> atomic rename.

If anything fails, the original file is untouched and the backup is still there.
"""

import importlib.util
import os
import sqlite3
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]


def _load_migrate():
    """Import the script by path (backend/scripts is not a package)."""
    spec = importlib.util.spec_from_file_location(
        "migrate_db", BACKEND / "scripts" / "migrate_db.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


LEGACY_SCHEMA = """
CREATE TABLE worlds (id INTEGER PRIMARY KEY AUTOINCREMENT, seed INTEGER NOT NULL, width REAL NOT NULL,
    height REAL NOT NULL, boundary TEXT NOT NULL, started_at TEXT NOT NULL, ended_at TEXT);
CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT, world_id INTEGER NOT NULL, tick INTEGER NOT NULL,
    type TEXT NOT NULL, entity_id INTEGER, caste TEXT, cause TEXT, x REAL, y REAL, payload TEXT,
    created_at TEXT NOT NULL);
CREATE TABLE law_changes (id INTEGER PRIMARY KEY AUTOINCREMENT, world_id INTEGER NOT NULL, tick INTEGER NOT NULL,
    name TEXT NOT NULL, value TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE creatures (id INTEGER PRIMARY KEY AUTOINCREMENT, world_id INTEGER NOT NULL, entity_id INTEGER NOT NULL,
    caste TEXT, clan_id INTEGER, generation INTEGER, mother_id INTEGER, father_id INTEGER,
    born_tick INTEGER, died_tick INTEGER);
CREATE TABLE snapshots (id INTEGER PRIMARY KEY AUTOINCREMENT, world_id INTEGER NOT NULL, tick INTEGER NOT NULL,
    payload TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE clan_epitaphs (id INTEGER PRIMARY KEY AUTOINCREMENT, world_id INTEGER NOT NULL, clan_id INTEGER NOT NULL,
    name TEXT NOT NULL, totem TEXT, color TEXT, founded_tick INTEGER, extinct_tick INTEGER,
    peak_population INTEGER, peak_tick INTEGER, wars_fought INTEGER, battles_won INTEGER,
    temples_built INTEGER, schisms_caused INTEGER, extinction_cause TEXT, created_at TEXT NOT NULL);
CREATE INDEX idx_events_world ON events(world_id, id);
CREATE INDEX idx_events_world_type ON events(world_id, type);
"""

WORLD_TABLES = (
    "worlds", "law_changes", "creatures", "snapshots", "settings", "clan_epitaphs",
)


def _seed_legacy(path, worlds: int = 2, per_world: int = 200) -> None:
    import json

    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA page_size=4096")
        conn.executescript(LEGACY_SCHEMA)
        for w in range(1, worlds + 1):
            conn.execute(
                "INSERT INTO worlds(id,seed,width,height,boundary,started_at,ended_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (w, w * 11, 100.0, 100.0, "clamp", "t0", None if w == worlds else "t1"),
            )
            kinds = ["war", "death", "birth", "temple", "fire", "predation", "bloom", "disaster"]
            rows = []
            for i in range(per_world):
                kind = kinds[i % len(kinds)]
                payload = {"a": i % 7 + 1, "b": i % 5 + 1, "lethal": True}
                if kind == "temple":
                    payload = {"clan_id": i % 7 + 1}
                rows.append((w, i, kind, i, "Soldier", "combat", 1.0, 2.0,
                             json.dumps(payload), f"t{i}"))
            conn.executemany(
                "INSERT INTO events(world_id,tick,type,entity_id,caste,cause,x,y,payload,created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                rows,
            )
            conn.execute(
                "INSERT INTO law_changes(id,world_id,tick,name,value,created_at) VALUES (?,?,?,?,?,?)",
                (w, w, 5, "food_count", "5", "t0"),
            )
            conn.execute(
                "INSERT INTO creatures(id,world_id,entity_id,caste,clan_id,generation,mother_id,"
                "father_id,born_tick,died_tick) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (w, w, 1, "Soldier", 3, 2, 1, 2, 1, 9),
            )
            conn.execute(
                "INSERT INTO snapshots(id,world_id,tick,payload,created_at) VALUES (?,?,?,?,?)",
                (w, w, 100, '{"a": 1}', "t0"),
            )
            conn.execute(
                "INSERT INTO clan_epitaphs(id,world_id,clan_id,name,totem,color,founded_tick,"
                "extinct_tick,peak_population,peak_tick,wars_fought,battles_won,temples_built,"
                "schisms_caused,extinction_cause,created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (w, w, 3, "Order", "circle", "#fff", 1, 900, 40, 400, 2, 1, 1, 0,
                 "starvation", "t0"),
            )
        conn.execute("INSERT INTO settings(key,value,created_at) VALUES (?,?,?)", ("k", "v", "t0"))
        conn.commit()
    finally:
        conn.close()


def _dump_events(path) -> list[tuple]:
    conn = sqlite3.connect(path)
    try:
        return conn.execute(
            "SELECT id, world_id, tick, type, entity_id, caste, cause, x, y, payload"
            " FROM events ORDER BY id"
        ).fetchall()
    finally:
        conn.close()


@pytest.fixture(scope="module")
def migrate():
    return _load_migrate()


def test_migration_reproduces_the_chronicle_exactly(tmp_path, migrate):
    src = str(tmp_path / "legacy.db")
    _seed_legacy(src)
    before = _dump_events(src)

    report = migrate.migrate(src)

    assert _dump_events(src) == before  # source untouched
    target = report["target"]
    assert _dump_events(target) == before  # every row, every column, same ids
    assert report["verified"] is True
    assert report["rows"] == len(before)


def test_migration_builds_the_side_tables_and_counter(tmp_path, migrate):
    src = str(tmp_path / "legacy2.db")
    _seed_legacy(src, worlds=1, per_world=100)
    target = migrate.migrate(src)["target"]
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    try:
        # event_clans: 1.78 rows/event-ish, deduped, ints only
        clans = conn.execute(
            "SELECT clan_id, COUNT(*) AS n FROM event_clans WHERE world_id=1 GROUP BY clan_id"
        ).fetchall()
        assert {r["clan_id"] for r in clans} == {1, 2, 3, 4, 5, 6, 7}
        # every side row points at a real event of the same world
        orphan = conn.execute(
            "SELECT COUNT(*) AS n FROM event_clans ec LEFT JOIN events e ON e.id = ec.event_id"
            " WHERE e.id IS NULL OR e.world_id <> ec.world_id"
        ).fetchone()[0]
        assert orphan == 0
        # the counter equals the true death count
        true_deaths = conn.execute(
            "SELECT COUNT(*) FROM events WHERE world_id=1 AND type='death'"
        ).fetchone()[0]
        assert conn.execute(
            "SELECT death_count FROM world_stats WHERE world_id=1"
        ).fetchone()[0] == true_deaths
        assert int(conn.execute("PRAGMA page_size").fetchone()[0]) == 16384
        assert conn.execute(
            "SELECT COUNT(*) FROM sqlite_stat1 WHERE tbl='events'"
        ).fetchone()[0] > 0
    finally:
        conn.close()


def test_migration_copies_every_other_table(tmp_path, migrate):
    src = str(tmp_path / "legacy3.db")
    _seed_legacy(src, worlds=2, per_world=20)
    target = migrate.migrate(src)["target"]
    old = sqlite3.connect(src)
    new = sqlite3.connect(target)
    try:
        for table in WORLD_TABLES:
            old_rows = old.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            new_rows = new.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            assert new_rows == old_rows, (table, old_rows, new_rows)
        assert new.execute("SELECT ended_at FROM worlds WHERE id=1").fetchone()[0] == "t1"
        assert new.execute("SELECT value FROM settings WHERE key='k'").fetchone()[0] == "v"
    finally:
        old.close()
        new.close()


def test_migration_writes_a_backup_before_touching_anything(tmp_path, migrate):
    src = str(tmp_path / "legacy4.db")
    _seed_legacy(src, worlds=1, per_world=20)
    report = migrate.migrate(src)
    backup = report["backup"]
    assert os.path.exists(backup)
    assert _dump_events(backup) == _dump_events(src)  # the backup is usable as-is
    assert backup != src


def test_migration_refuses_to_clobber_a_second_run(tmp_path, migrate):
    """The target is built beside the source and renamed in; the source stays put
    until the operator retires it, so a second run has something to work from."""
    src = str(tmp_path / "legacy5.db")
    _seed_legacy(src, worlds=1, per_world=20)
    migrate.migrate(src)
    first = _dump_events(src)
    migrate.migrate(src)  # idempotent: migrating an already-migrated file
    assert _dump_events(src) == first


def test_migration_reports_size_and_page_change(tmp_path, migrate):
    src = str(tmp_path / "legacy6.db")
    _seed_legacy(src, worlds=1, per_world=4000)
    report = migrate.migrate(src)
    assert report["before"]["page_size"] == 4096
    assert report["after"]["page_size"] == 16384
    assert report["after"]["rows"] == report["before"]["rows"]
    assert report["after"]["file_bytes"] > 0
    assert report["after"]["bytes_per_row"] > 0
    assert report["before"]["file_bytes"] > 0
    assert report["backup_bytes"] > 0
    # MEASURED: at this size the rebuild is BIGGER (835 KB vs 467 KB):
    # 16 KB pages put a 16 KB floor under each of the ~21 tables/indexes, which
    # dominates a 4000-row file. The -11% win is a 766 MB-file claim; the floor
    # only amortises at scale, so the size assertion lives in the scale test.
    assert report["after"]["bytes_per_row"] > 0


def test_migration_preserves_ids_across_gaps(tmp_path, migrate):
    """`id` is the pagination cursor, so the rebuild must carry it over.

    Letting SQLite renumber made event_clans point at the wrong rows whenever the
    source had a gap (a rolled-back insert), and broke every stored cursor.
    """
    src = str(tmp_path / "gaps.db")
    _seed_legacy(src, worlds=1, per_world=20)
    raw = sqlite3.connect(src)
    try:
        raw.execute("DELETE FROM events WHERE id % 3 = 0")  # leave gaps
        raw.commit()
        before = [r[0] for r in raw.execute("SELECT id FROM events ORDER BY id")]
    finally:
        raw.close()
    assert len(before) < 20 and before != list(range(1, 21))
    target = migrate.migrate(src)["target"]
    after = [r[0] for r in sqlite3.connect(target).execute("SELECT id FROM events ORDER BY id")]
    assert after == before
    conn = sqlite3.connect(target)
    try:
        dangling = conn.execute(
            "SELECT COUNT(*) FROM event_clans ec LEFT JOIN events e ON e.id = ec.event_id"
            " WHERE e.id IS NULL"
        ).fetchone()[0]
        assert dangling == 0
    finally:
        conn.close()


def test_migration_reads_the_backup_not_the_live_file(tmp_path, migrate, monkeypatch):
    """A writer during the 3-5 minute run must not leak into the rebuilt file.

    VACUUM INTO already took a consistent snapshot, so the copy has to read the
    BACKUP: otherwise the verified output diverges from the rollback artifact.
    """
    src = str(tmp_path / "live.db")
    _seed_legacy(src, worlds=1, per_world=20)
    real_copy_events = migrate._copy_events

    def copy_then_write(src_conn, dst_conn):
        result = real_copy_events(src_conn, dst_conn)
        writer = sqlite3.connect(src)
        try:
            writer.execute(
                "INSERT INTO events(world_id,tick,type,entity_id,caste,cause,x,y,payload,created_at)"
                " VALUES (1,9999,'war',9999,'S','',1.0,2.0,'{}','late')"
            )
            writer.commit()
        finally:
            writer.close()
        return result

    monkeypatch.setattr(migrate, "_copy_events", copy_then_write)
    report = migrate.migrate(src)
    conn = sqlite3.connect(report["target"])
    try:
        late = conn.execute(
            "SELECT COUNT(*) FROM events WHERE entity_id=9999"
        ).fetchone()[0]
        assert late == 0, "a row written after the backup leaked into the rebuild"
    finally:
        conn.close()


def test_verify_reports_a_dangling_side_row_instead_of_crashing(tmp_path, migrate):
    """A verification failure must be a reported problem, not a traceback — the
    caller relies on it to park the file and exit non-zero."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "migrate_db2", BACKEND / "scripts" / "migrate_db.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    src = str(tmp_path / "verify.db")
    _seed_legacy(src, worlds=1, per_world=10)
    report = module.migrate(src)
    dst = sqlite3.connect(report["target"])
    try:
        dst.execute("INSERT INTO event_clans(world_id, clan_id, event_id) VALUES (1, 42, 999999)")
        dst.commit()
        result = module._verify(module._connect_ro(src), module._connect_ro(report["target"]))
        assert result["verified"] is False
        assert any("event_clans" in p for p in result["problems"]), result["problems"]
    finally:
        dst.close()


def test_script_help_runs_as_a_module():
    """The tool must be usable as documented: python3 scripts/migrate_db.py --help."""
    import subprocess

    out = subprocess.run(
        [sys.executable, str(BACKEND / "scripts" / "migrate_db.py"), "--help"],
        capture_output=True, text=True, cwd=str(BACKEND),
    )
    assert out.returncode == 0, out.stderr
    assert "--db" in out.stdout
    assert "--dry-run" in out.stdout
