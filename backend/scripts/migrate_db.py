#!/usr/bin/env python3
"""Offline chronicle rebuild: shrink and re-index flatworld.db.

WHY OFFLINE
    A populated SQLite file cannot change its page size, and the 16 KB page win
    (-11% file, 321 ms -> 2.9 ms WAL checkpoint) plus the lean `events` table
    (no `created_at`, no AUTOINCREMENT) both need a full rebuild. Stop the
    service, run this, start it again.

WHAT IT DOES
    backup (VACUUM INTO, a consistent snapshot that also folds the WAL in)
      -> build a fresh file at 16 KB pages from the LIVE schema definition in
         app.db._SCHEMA (one source of truth, so the two cannot drift)
      -> stream every table across, matching columns by name so a legacy
         `events` row simply loses its `created_at`
      -> build event_clans + world_stats in the same streaming pass
      -> ANALYZE, verify per-world counts and an events checksum
      -> atomic rename into <db>.rebuilt, leaving the original in place

ROLLBACK
    The original file is never modified. To roll back: stop the service, move
    <db>.rebuilt aside, put the backup back as <db>, start the service. The
    backup alone is sufficient — the original stays valid throughout.

USAGE
    python3 scripts/migrate_db.py --db ../flatworld.db            # rebuild
    python3 scripts/migrate_db.py --db ../flatworld.db --dry-run  # report only
    python3 scripts/migrate_db.py --db ../flatworld.db --replace  # swap it in
    python3 scripts/migrate_db.py --db ../flatworld.db --bench    # before/after

Exit code 0 on success, 1 on a failed verification (the rebuilt file is then
left beside the original, unreferenced, and the service can be started again
against the original).
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import (  # noqa: E402  (path shim above must run first)
    CLAN_PAYLOAD_KEYS,
    _EVENTS_DDL,
    _EVENT_INDEXES,
    _clan_ids_of,
    _loads,
    PAGE_SIZE,
)

# Everything except `events`, which has its own pass (it fills the side tables).
PLAIN_TABLES = ("worlds", "law_changes", "creatures", "snapshots", "settings", "clan_epitaphs")
CHUNK = 5000
# How many side-table rows the verifier re-derives with SQL json_extract as an
# independent cross-check of the Python extraction.
SAMPLE_ROWS = 200
EVENT_COLUMNS = (
    "id", "world_id", "tick", "type", "entity_id", "caste", "cause", "x", "y", "payload",
)


def _connect_ro(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=30.0)
    conn.row_factory = sqlite3.Row
    return conn


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    """Positional access: works for both Row and plain-tuple row factories."""
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]


def _measure(path: str, conn: sqlite3.Connection) -> dict[str, Any]:
    rows = int(conn.execute("SELECT COUNT(*) FROM events").fetchone()[0])
    out: dict[str, Any] = {
        "path": path,
        "file_bytes": os.path.getsize(path) if os.path.exists(path) else 0,
        "page_size": int(conn.execute("PRAGMA page_size").fetchone()[0]),
        "rows": rows,
    }
    try:
        out["events_bytes"] = int(conn.execute(
            "SELECT SUM(pgsize) FROM dbstat WHERE name='events'"
        ).fetchone()[0] or 0)
        out["index_bytes"] = int(conn.execute(
            "SELECT SUM(pgsize) FROM dbstat WHERE name LIKE 'idx_%'"
        ).fetchone()[0] or 0)
    except sqlite3.Error:
        pass
    out["bytes_per_row"] = round(out["file_bytes"] / rows, 1) if rows else 0.0
    return out


def _create_target(target: str) -> sqlite3.Connection:
    """Fresh file at 16 KB pages carrying exactly the live schema.

    The `events` indexes are deliberately NOT created here: they are built after
    the bulk load (see `migrate`), because inserting rows into an already-indexed
    table fragments the index b-trees — measured at 92.7 MB of freelist pages
    (16% of the file) on the 2.7M-row replica.
    """
    if os.path.exists(target):
        os.remove(target)
    conn = sqlite3.connect(target, isolation_level=None)
    conn.execute(f"PRAGMA page_size={PAGE_SIZE}")
    conn.execute("PRAGMA journal_mode=OFF")       # a rebuild is restartable
    conn.execute("PRAGMA synchronous=OFF")        # ditto — nothing to lose yet
    conn.execute("PRAGMA cache_size=-131072")     # 128 MB: keeps chunked writes fast
    # The lean events DDL first, then every OTHER table from the live schema.
    conn.executescript(_EVENTS_DDL.format(name="events"))
    from app.db import _SCHEMA  # local import: the definition is the source of truth

    for statement in _split_statements(_SCHEMA):
        head = statement.lstrip().upper()
        if head.startswith("CREATE TABLE IF NOT EXISTS EVENTS") or head.startswith("CREATE INDEX"):
            continue
        conn.execute(statement)
    return conn


def _split_statements(script: str) -> list[str]:
    """Split a DDL script on `;`, comment-aware.

    A `--` comment may contain a `;` (the schema's own comments do), so comments
    are stripped per line before splitting — otherwise a comment tail becomes a
    bogus statement.
    """
    lines = [line.split("--", 1)[0] for line in script.splitlines()]
    return [stmt for stmt in (chunk.strip() for chunk in "\n".join(lines).split(";")) if stmt]


def _copy_table(src: sqlite3.Connection, dst: sqlite3.Connection, table: str) -> int:
    """Column-name intersection copy: a legacy extra column is simply left behind."""
    have = _tables(src)
    if table not in have:
        return 0
    src_cols = _columns(src, table)
    dst_cols = _columns(dst, table)
    shared = [c for c in dst_cols if c in src_cols]
    if not shared:
        return 0
    collist = ",".join(shared)
    select = f"SELECT {collist} FROM {table} ORDER BY rowid"
    insert = f"INSERT INTO {table}({collist}) VALUES ({','.join('?' * len(shared))})"
    copied = 0
    cursor = src.execute(select)
    while True:
        rows = cursor.fetchmany(CHUNK)
        if not rows:
            break
        dst.executemany(insert, [tuple(r[c] for c in shared) for r in rows])
        copied += len(rows)
    return copied


def _copy_events(src: sqlite3.Connection, dst: sqlite3.Connection) -> dict[str, Any]:
    """Stream `events`, building event_clans + world_stats in the same pass.

    The payload is parsed once here, in Python, which is the whole point of the
    side table: the clan filter never has to parse JSON in SQL.
    """
    src_cols = _columns(src, "events")
    select = f"SELECT {','.join(EVENT_COLUMNS)} FROM events ORDER BY id"
    insert = (
        "INSERT INTO events(id,world_id,tick,type,entity_id,caste,cause,x,y,payload)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)"
    )
    clans_insert = "INSERT INTO event_clans(world_id, clan_id, event_id) VALUES (?,?,?)"
    dst.execute("BEGIN")
    cursor = src.execute(select)
    rows = 0
    clan_rows = 0
    deaths: dict[int, int] = {}
    ids: list[int] = []
    ticks: list[int] = []
    while True:
        batch = cursor.fetchmany(CHUNK)
        if not batch:
            break
        dst.executemany(insert, [
            (r["id"], r["world_id"], r["tick"], r["type"], r["entity_id"], r["caste"],
             r["cause"], r["x"], r["y"], r["payload"])
            for r in batch
        ])
        for r in batch:
            payload = _loads(r["payload"])
            found = _clan_ids_of(payload)
            for clan_id in found:
                dst.execute(clans_insert, (r["world_id"], clan_id, r["id"]))
            clan_rows += len(found)
            if r["type"] == "death":
                deaths[r["world_id"]] = deaths.get(r["world_id"], 0) + 1
            ids.append(r["id"])
            ticks.append(r["tick"])
        rows += len(batch)
    for world_id, count in deaths.items():
        dst.execute(
            "INSERT INTO world_stats(world_id, death_count) VALUES (?, ?)"
            " ON CONFLICT(world_id) DO UPDATE SET death_count = excluded.death_count",
            (world_id, count),
        )
    dst.execute("COMMIT")
    return {
        "rows": rows,
        "clan_rows": clan_rows,
        "deaths_by_world": deaths,
        # cheap content checksum: row count + id span + tick span
        "checksum": {
            "rows": rows,
            "min_id": min(ids) if ids else None,
            "max_id": max(ids) if ids else None,
            "min_tick": min(ticks) if ticks else None,
            "max_tick": max(ticks) if ticks else None,
            "sum_tick": sum(ticks),
        },
    }


def _verify(src: sqlite3.Connection, dst: sqlite3.Connection) -> dict[str, Any]:
    """Per-world row counts plus the events checksum must match exactly."""
    problems: list[str] = []

    def world_counts(conn: sqlite3.Connection) -> dict[int, int]:
        return {
            int(r[0]): int(r[1])
            for r in conn.execute("SELECT world_id, COUNT(*) FROM events GROUP BY world_id")
        }

    before, after = world_counts(src), world_counts(dst)
    if before != after:
        problems.append(f"per-world event counts differ: {before} != {after}")

    def checksum(conn: sqlite3.Connection) -> tuple:
        return conn.execute(
            "SELECT COUNT(*), MIN(id), MAX(id), MIN(tick), MAX(tick), SUM(tick) FROM events"
        ).fetchone()

    if tuple(checksum(src)) != tuple(checksum(dst)):
        problems.append(f"events checksum differs: {checksum(src)} != {checksum(dst)}")

    for table in PLAIN_TABLES:
        if table not in _tables(src):
            continue
        a = int(src.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        b = int(dst.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        if a != b:
            problems.append(f"{table}: {a} rows -> {b}")

    # the side table must agree with the payloads it was built from
    orphans = int(dst.execute(
        "SELECT COUNT(*) FROM event_clans ec LEFT JOIN events e ON e.id = ec.event_id"
        " WHERE e.id IS NULL OR e.world_id <> ec.world_id"
    ).fetchone()[0] or 0)
    if orphans:
        problems.append(f"event_clans: {orphans} rows point at no event of their world")
    # Cross-check the Python extraction against SQL truth on a sample. json_extract
    # is far too slow for the hot path (that is why the side table exists) but this
    # is a one-shot tool, so a sample is affordable and catches a mis-parsed payload.
    sample = dst.execute(
        "SELECT event_id, clan_id FROM event_clans ORDER BY event_id LIMIT ?",
        (SAMPLE_ROWS,),
    ).fetchall()
    key_list = ",".join(
        f"json_extract(payload, '$.{k}')" for k in CLAN_PAYLOAD_KEYS
    )
    for event_id, clan_id in sample:
        values = dst.execute(
            f"SELECT {key_list} FROM events WHERE id=?", (event_id,)
        ).fetchone()
        if values is None:
            problems.append(
                f"event_clans points at event {event_id}, which the rebuild does not have"
            )
            break
        named = {v for v in values if isinstance(v, int) and not isinstance(v, bool)}
        if int(clan_id) not in named:
            problems.append(
                f"event_clans claims clan {clan_id} for event {event_id},"
                f" whose payload names {sorted(named)} in SQL"
            )
            break

    for world_id, count in before.items():
        true_deaths = int(dst.execute(
            "SELECT COUNT(*) FROM events WHERE world_id=? AND type='death'", (world_id,)
        ).fetchone()[0])
        stored = dst.execute(
            "SELECT death_count FROM world_stats WHERE world_id=?", (world_id,)
        ).fetchone()
        if stored is None or int(stored[0]) != true_deaths:
            problems.append(f"world {world_id}: world_stats {stored and stored[0]} != {true_deaths}")

    if int(dst.execute("PRAGMA page_size").fetchone()[0]) != PAGE_SIZE:
        problems.append(f"target page_size is not {PAGE_SIZE}")
    return {"verified": not problems, "problems": problems}


def _median_ms(call, runs: int = 5) -> float:
    call()  # warm the page cache
    samples = []
    for _ in range(runs):
        t0 = time.perf_counter()
        call()
        samples.append((time.perf_counter() - t0) * 1000)
    samples.sort()
    return round(samples[len(samples) // 2], 3)


def _wal_checkpoint_ms(path: str) -> dict[str, Any]:
    """Checkpoint cost on a throwaway copy, first and steady-state.

    An empty WAL truncates instantly, so a writer batch has to exist first; the
    copy keeps the measurement from writing to the file being measured. The FIRST
    checkpoint is reported separately because it is a one-time WAL-initialisation
    cost on a 16 KB-page file (measured ~200 ms on a 485 MB file) and the steady
    state is what a running service sees (1.4-3.6 ms).
    """
    import shutil
    import tempfile

    with tempfile.TemporaryDirectory(prefix="chron-wal-") as tmp:
        scratch = os.path.join(tmp, "bench.db")
        shutil.copyfile(path, scratch)
        conn = sqlite3.connect(scratch, isolation_level=None)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            samples = []
            for batch in range(3):
                conn.execute("BEGIN")
                for i in range(2000):
                    conn.execute(
                        "INSERT INTO settings(key,value,created_at) VALUES (?,?,?)"
                        " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                        (f"bench{batch}_{i}", str(i), "t0"),
                    )
                conn.execute("COMMIT")
                t0 = time.perf_counter()
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchall()
                samples.append(round((time.perf_counter() - t0) * 1000, 3))
            return {"first": samples[0], "steady": round(sorted(samples[1:])[0], 3)}
        finally:
            conn.close()


def _legacy_rows(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    """The pre-§3.5 projection from db.py, verbatim.

    Both sides of the comparison must pay the same Python cost, or the
    measurement compares raw SQL against the full API and invents regressions
    (it did: 1.10 -> 2.81 ms on a query that is 0.94 ms of SQL either way).
    """
    return [
        {
            "id": r["id"], "tick": r["tick"], "type": r["type"],
            "entity_id": r["entity_id"], "caste": r["caste"], "cause": r["cause"],
            "x": r["x"], "y": r["y"], "payload": json.loads(r["payload"] or "{}"),
        }
        for r in rows
    ]


def _bench_legacy(path: str) -> dict[str, Any]:
    """The PRE-§3.5 read paths, verbatim, so 'before' is measured not asserted.

    These are the exact statements db.py used at 561dc31: the 13-way
    json_extract clan filter, COUNT(*) for death_count, and `SELECT *` history.
    """
    conn = _connect_ro(path)
    try:
        wid = int(conn.execute("SELECT id FROM worlds ORDER BY id LIMIT 1").fetchone()[0])
        clan = 1  # the replica numbers clans 1..40
        ors = " OR ".join(f"json_extract(payload,'$.{k}')=?" for k in CLAN_PAYLOAD_KEYS)
        majors = list(_major_types())
        placeholders = ",".join("?" * len(majors))
        pattern = "%creature%"

        def clan_query() -> list:
            return _legacy_rows(conn.execute(
                f"SELECT * FROM events WHERE world_id=? AND ({ors})"
                f" ORDER BY id DESC LIMIT 200",
                (wid,) + (clan,) * len(CLAN_PAYLOAD_KEYS),
            ).fetchall())

        out = {
            "label": "before (pre-3.5 SQL, same file)",
            "history_clan_200": _median_ms(clan_query),
            "history_major_2000": _median_ms(lambda: _legacy_rows(conn.execute(
                f"SELECT * FROM events WHERE world_id=? AND type IN ({placeholders})"
                f" ORDER BY id DESC LIMIT 2000", (wid, *majors)).fetchall())),
            "history_plain_500": _median_ms(lambda: _legacy_rows(conn.execute(
                "SELECT * FROM events WHERE world_id=? ORDER BY id DESC LIMIT 500", (wid,)
            ).fetchall())),
            "history_entity_500": _median_ms(lambda: _legacy_rows(conn.execute(
                "SELECT * FROM events WHERE world_id=? AND entity_id=? ORDER BY id DESC LIMIT 500",
                (wid, 42)).fetchall())),
            "death_count": _median_ms(lambda: int(conn.execute(
                "SELECT COUNT(*) AS n FROM events WHERE world_id=? AND type='death'", (wid,)
            ).fetchone()["n"])),
            "history_q_like": _median_ms(lambda: _legacy_rows(conn.execute(
                "SELECT * FROM events WHERE world_id=? AND (type LIKE ? OR caste LIKE ?"
                " OR cause LIKE ? OR payload LIKE ?) ORDER BY id DESC LIMIT 500",
                (wid, pattern, pattern, pattern, pattern)).fetchall())),
        }
        out["wal_checkpoint_truncate"] = _wal_checkpoint_ms(path)
        return out
    finally:
        conn.close()


def _bench_current(path: str) -> dict[str, Any]:
    """The post-migration read paths through the public Database interface."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.db import Database

    db = Database(path)
    db._start_writer = lambda: None  # measurement only
    try:
        conn = db.connection
        wid = int(conn.execute("SELECT id FROM worlds ORDER BY id LIMIT 1").fetchone()[0])
        clan = conn.execute(
            "SELECT clan_id FROM event_clans WHERE world_id=? LIMIT 1", (wid,)
        ).fetchone()
        out: dict[str, Any] = {
            "label": "after (Database interface)",
            "history_clan_200": _median_ms(lambda: db.history(wid, limit=200, clan_id=int(clan["clan_id"])))
            if clan else None,
            "history_major_2000": _median_ms(lambda: db.history(
                wid, limit=2000, types_filter=list(_major_types()))),
            "history_plain_500": _median_ms(lambda: db.history(wid, limit=500)),
            "history_entity_500": _median_ms(lambda: db.history(wid, limit=500, entity_id=42)),
            "death_count": _median_ms(lambda: db.death_count(wid)),
            "history_q_like": _median_ms(lambda: db.history(wid, limit=500, q="creature")),
        }
        out["wal_checkpoint_truncate"] = _wal_checkpoint_ms(path)
        return out
    finally:
        db.close()


def _major_types() -> tuple[str, ...]:
    from app.main import MAJOR_EVENT_TYPES

    return MAJOR_EVENT_TYPES


def migrate(
    db_path: str,
    *,
    dry_run: bool = False,
    replace: bool = False,
    bench: bool = False,
    keep_backup: bool = True,
) -> dict[str, Any]:
    """Rebuild `db_path` into `<db>.rebuilt`. Returns a report dict."""
    src_path = os.path.abspath(db_path)
    if not os.path.exists(src_path):
        raise FileNotFoundError(src_path)
    target = src_path + ".rebuilt"
    backup = src_path + f".bak-{time.strftime('%Y%m%d-%H%M%S')}"
    started = time.perf_counter()
    report: dict[str, Any] = {"source": src_path, "target": target, "backup": backup}

    src = _connect_ro(src_path)
    try:
        report["before"] = _measure(src_path, src)
        report["tables"] = sorted(_tables(src))
        if dry_run:
            report["dry_run"] = True
            if bench:
                report["bench_before"] = _bench_legacy(src_path)
            return report

        # 1. backup: VACUUM INTO is a consistent snapshot and folds the WAL in.
        #    The rebuild then reads the BACKUP, not the live file: a writer during
        #    a 3-5 minute run would otherwise diverge the verified output from the
        #    artifact a rollback would restore. src stays open only to read the
        #    schema and the before-measurement.
        if os.path.exists(backup):
            os.remove(backup)
        src.execute("VACUUM INTO ?", (backup,))
        report["backup_bytes"] = os.path.getsize(backup)

        # 2/3/4. rebuild at 16 KB pages, streaming every table
        snapshot = _connect_ro(backup)
        dst = _create_target(target)
        try:
            dst.execute("BEGIN")
            report["plain_tables"] = {
                table: _copy_table(snapshot, dst, table)
                for table in PLAIN_TABLES if table in _tables(snapshot)
            }
            dst.execute("COMMIT")
            report["events"] = _copy_events(snapshot, dst)
            # Bulk-load order: data first, indexes second, then pack the pages.
            # The events indexes are built here rather than in _create_target so
            # SQLite fills their leaves sequentially instead of splitting them.
            for ddl in _EVENT_INDEXES:
                dst.execute(ddl)
            dst.execute("PRAGMA analysis_limit=100")
            dst.execute("ANALYZE")
            dst.execute(f"PRAGMA page_size={PAGE_SIZE}")  # VACUUM must not reset it
            dst.execute("VACUUM")
            report["verify"] = _verify(snapshot, dst)
            report["source_rows_at_end"] = int(
                src.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            )
        finally:
            snapshot.close()
            dst.close()
        report["rows"] = report["events"]["rows"]
        report["verified"] = report["verify"]["verified"]
        if not report["verified"]:
            # The original is untouched; park the half-built file under a name that
            # cannot be mistaken for a usable database.
            failed = target + ".failed"
            os.replace(target, failed) if os.path.exists(target) else None
            report["failed"] = True
            report["failed_file"] = failed
            return report
    finally:
        src.close()

    report["after"] = _measure(target, _connect_ro(target))
    report["elapsed_s"] = round(time.perf_counter() - started, 2)
    if bench:
        report["bench_before"] = _bench_legacy(src_path)
        report["bench_after"] = _bench_current(
            src_path if report.get("replaced") else target
        )
    if replace:
        os.replace(target, src_path)
        report["replaced"] = True
        if not keep_backup:
            os.remove(backup)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline chronicle rebuild (16 KB pages, lean schema, side tables).",
    )
    parser.add_argument("--db", required=True, help="path to flatworld.db")
    parser.add_argument("--dry-run", action="store_true",
                        help="report the current state and exit without writing")
    parser.add_argument("--replace", action="store_true",
                        help="swap the rebuilt file in (otherwise it lands as <db>.rebuilt)")
    parser.add_argument("--bench", action="store_true",
                        help="measure read-path latency before and after")
    parser.add_argument("--no-backup", action="store_true",
                        help="delete the backup after a successful --replace")
    args = parser.parse_args(argv)

    report = migrate(
        args.db,
        dry_run=args.dry_run,
        replace=args.replace,
        bench=args.bench,
        keep_backup=not args.no_backup,
    )
    print(json.dumps(report, indent=2, default=str))
    if report.get("failed"):
        print("\nVERIFICATION FAILED — the original file is untouched:", file=sys.stderr)
        for problem in report["verify"]["problems"]:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    if not report.get("dry_run"):
        before, after = report["before"], report["after"]
        print(
            f"\n{before['rows']} rows | "
            f"{before['file_bytes'] / 1e6:.1f} MB @ {before['page_size']} -> "
            f"{after['file_bytes'] / 1e6:.1f} MB @ {after['page_size']} | "
            f"{before['bytes_per_row']} -> {after['bytes_per_row']} B/row",
            file=sys.stderr,
        )
        if not report.get("replaced"):
            print(f"rebuilt file: {report['target']} (start the service against it, "
                  f"or re-run with --replace)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
