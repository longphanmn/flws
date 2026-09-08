"""SQLite persistence: worlds, chronicle events, and god's law changes.

Deliberately uses the stdlib `sqlite3` behind a thin repository interface:
writes are tiny batches to a local file, so an ORM/async driver would add
loop-affinity hazards without benefit. Swap to SQLAlchemy/Postgres here when
the deployment needs it — callers only touch Database methods.

§AD OS-log semantics: the hot path (chronicle + genealogy) appends to a RAM
buffer; a dedicated writer daemon drains it into SQLite in ONE transaction,
every 5s or when 5000 ops pile up. A crash loses at most the un-flushed tail.
Reads (`history`, genealogy) go straight to SQLite and may lag ≤5s.
"""

import json
import os
import sqlite3
import threading
from collections import deque
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime, timezone

# §AT-1: every event payload key that may name a clan (used by the SQL-level
# clan filter and the paginated clan history endpoint).
CLAN_PAYLOAD_KEYS = (
    "a", "b", "clan_id", "parent", "new_clan",
    "invader_clan", "victim_clan", "winner_clan", "loser_clan",
    "target_clan", "founder", "from", "to",
)
from typing import Any

from .config import Config
from .protocol import HistoryEvent

# §AD: drain the buffer after this many pending ops even before the interval.
FLUSH_MAX_OPS = 5000
# §AD: writer heartbeat — durability window for a hard crash.
FLUSH_INTERVAL = 5.0

_SCHEMA = """
CREATE TABLE IF NOT EXISTS worlds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seed INTEGER NOT NULL,
    width REAL NOT NULL,
    height REAL NOT NULL,
    boundary TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT
);
CREATE TABLE IF NOT EXISTS events (
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
CREATE TABLE IF NOT EXISTS law_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    world_id INTEGER NOT NULL,
    tick INTEGER NOT NULL,
    name TEXT NOT NULL,
    value TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS creatures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    world_id INTEGER NOT NULL,
    entity_id INTEGER NOT NULL,
    caste TEXT,
    clan_id INTEGER,
    generation INTEGER,
    mother_id INTEGER,
    father_id INTEGER,
    born_tick INTEGER,
    died_tick INTEGER
);
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    world_id INTEGER NOT NULL,
    tick INTEGER NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS clan_epitaphs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    world_id INTEGER NOT NULL,
    clan_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    totem TEXT,
    color TEXT,
    founded_tick INTEGER,
    extinct_tick INTEGER,
    peak_population INTEGER,
    peak_tick INTEGER,
    wars_fought INTEGER,
    battles_won INTEGER,
    temples_built INTEGER,
    schisms_caused INTEGER,
    extinction_cause TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_world ON events(world_id, id);
CREATE INDEX IF NOT EXISTS idx_events_world_entity ON events(world_id, entity_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_creatures_world ON creatures(world_id, entity_id);
CREATE INDEX IF NOT EXISTS idx_clan_epitaphs_world ON clan_epitaphs(world_id, clan_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: str):
        self.path = path
        self._conn: sqlite3.Connection | None = None
        # One connection shared across threads (event loop + test workers);
        # a reentrant lock serializes the tiny local writes (the §AD writer
        # drains through batch(), whose statements take the same lock).
        self._lock = threading.RLock()
        # AA: >0 while a batched write window is open — writers skip their
        # own commit so a whole tick costs ONE fsync instead of one per event.
        self._batch_depth = 0
        # §AD OS-log: pending durable ops drained by the writer daemon.
        # AZ Phase3 P2: pre-serialized tuples + high-water watermark
        self._pending: deque[tuple[str, tuple]] = deque()
        self._pending_high_water: int = 0
        self._pending_high_water_mark: int = 0
        self._writer: threading.Thread | None = None
        self._wake = threading.Event()
        self._stopping = False

    # ------------------------------------------------------------ lifecycle
    def connect(self) -> None:
        """Open (once) and migrate."""
        if self._conn is not None:
            return
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        # timeout: wait up to 5s on lock contention instead of failing instantly
        # (a concurrent reader/writer must never crash the tick loop)
        # isolation_level=None → autocommit; transactions are managed
        # explicitly by batch() below.
        self._conn = sqlite3.connect(
            self.path, check_same_thread=False, timeout=5.0, isolation_level=None
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        # §AD: NORMAL + WAL — consistent fsync only at checkpoints; the RAM
        # buffer already bounds crash loss to the un-flushed tail.
        self._conn.execute("PRAGMA synchronous=NORMAL")
        # AZ Phase 3 P1: tune checkpoint and caches
        try:
            self._conn.execute("PRAGMA wal_autocheckpoint=10000")
            self._conn.execute("PRAGMA cache_size=-65536")
            self._conn.execute("PRAGMA temp_store=MEMORY")
            self._conn.execute("PRAGMA mmap_size=268435456")
        except Exception:
            pass
        self._conn.executescript(_SCHEMA)
        # AZ Phase 3 P0: missing indices — guarded migration (2.6M rows)
        try:
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_events_world_type ON events(world_id, type)")
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_events_world_entity ON events(world_id, entity_id, id DESC)")
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_creatures_world_mother ON creatures(world_id, mother_id)")
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_creatures_world_father ON creatures(world_id, father_id)")
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_law_changes_world ON law_changes(world_id)")
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_clan_epitaphs_world ON clan_epitaphs(world_id, clan_id)")
        except Exception:
            pass
        # BM-24: creature details on death (guarded column migrations)
        try:
            self._conn.execute("ALTER TABLE creatures ADD COLUMN personal_name TEXT")
        except Exception:
            pass
        try:
            self._conn.execute("ALTER TABLE creatures ADD COLUMN title TEXT")
        except Exception:
            pass
        try:
            self._conn.execute("ALTER TABLE creatures ADD COLUMN kill_count INTEGER DEFAULT 0")
        except Exception:
            pass
        self._start_writer()

    def _start_writer(self) -> None:
        if self._writer is not None and self._writer.is_alive():
            return
        self._stopping = False
        self._writer = threading.Thread(target=self._writer_loop, name="db-writer", daemon=True)
        self._writer.start()

    def _writer_loop(self) -> None:
        """Drain the RAM buffer into SQLite: 5s heartbeat or 5000 ops."""
        while not self._stopping:
            self._wake.wait(timeout=FLUSH_INTERVAL)
            self._wake.clear()
            try:
                self.flush()
            except Exception:
                # The writer must survive anything; ops stay queued for retry.
                pass

    @property
    def pending(self) -> int:
        """Ops waiting in the RAM buffer (observability / tests)."""
        return len(self._pending)

    @property
    def pending_high_water(self) -> int:
        return self._pending_high_water

    @property
    def pending_high_water_mark(self) -> int:
        return self._pending_high_water_mark

    @property
    def high_water_mark(self) -> int:
        return self._pending_high_water

    def pending_events(self, world_id: int, limit: int = 500) -> list[dict[str, Any]]:
        """AZ Phase 1 P1: read-your-writes from RAM without forcing a flush."""
        out: list[dict[str, Any]] = []
        with self._lock:
            pending_copy = list(self._pending)
        for kind, args in reversed(pending_copy):
            if kind != "event":
                continue
            wid, ev = args  # type: ignore
            if wid != world_id:
                continue
            # need payload dict; HistoryEvent has payload attribute
            try:
                payload = ev.payload if hasattr(ev, "payload") else {}
            except Exception:
                payload = {}
            out.append({
                "id": 0,  # pending has no row id yet; sort after DB rows
                "tick": getattr(ev, "tick", 0),
                "type": getattr(ev, "type", ""),
                "entity_id": getattr(ev, "entity_id", None),
                "caste": getattr(ev, "caste", None),
                "cause": getattr(ev, "cause", None),
                "x": getattr(ev, "x", None),
                "y": getattr(ev, "y", None),
                "payload": dict(payload) if isinstance(payload, dict) else {},
            })
            if len(out) >= limit:
                break
        return out

    def _bump_high_water(self) -> None:
        n = len(self._pending)
        if n > self._pending_high_water:
            self._pending_high_water = n
            self._pending_high_water_mark = n

    # ------------------------------------------------------------- §AD queue
    def log_event(self, world_id: int, event: HistoryEvent) -> None:
        """Buffer one chronicle event (sim thread never touches SQLite)."""
        self._pending.append(("event", (world_id, event)))
        self._bump_high_water()
        if len(self._pending) >= FLUSH_MAX_OPS:
            self._wake.set()

    def log_birth(
        self,
        world_id: int,
        entity_id: int,
        caste: str,
        clan_id: int,
        generation: int,
        mother_id: int,
        father_id: int,
        born_tick: int,
    ) -> None:
        self._pending.append(
            (
                "birth",
                (world_id, entity_id, caste, clan_id, generation, mother_id, father_id, born_tick),
            )
        )
        self._bump_high_water()
        if len(self._pending) >= FLUSH_MAX_OPS:
            self._wake.set()

    def log_death(
        self,
        world_id: int,
        entity_id: int,
        died_tick: int,
        personal_name: str | None = None,
        title: str | None = None,
        kill_count: int = 0,
    ) -> None:
        self._pending.append(("death", (world_id, entity_id, died_tick, personal_name, title, kill_count)))
        self._bump_high_water()
        if len(self._pending) >= FLUSH_MAX_OPS:
            self._wake.set()

    def flush(self) -> int:
        """Drain every buffered op into SQLite in ONE transaction.

        Returns the number of ops written. Forced on world end/reset,
        snapshot save and shutdown; otherwise runs on the writer thread.
        """
        with self._lock:
            if not self._pending:
                return 0
            ops = list(self._pending)
            self._pending.clear()
        conn = self._require()
        try:
            with self.batch():
                # AZ Phase 3 P1: group by kind and use executemany (5000 binds -> 3 statements)
                events = [a for k, a in ops if k == "event"]
                births = [a for k, a in ops if k == "birth"]
                deaths = [a for k, a in ops if k == "death"]
                if events:
                    now = _now()
                    rows = [
                        (wid, ev.tick, ev.type, ev.entity_id, ev.caste, ev.cause, ev.x, ev.y, json.dumps(ev.payload), now)
                        for wid, ev in events
                    ]
                    conn.executemany(
                        "INSERT INTO events(world_id,tick,type,entity_id,caste,cause,x,y,payload,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                        rows,
                    )
                if births:
                    conn.executemany(
                        "INSERT INTO creatures(world_id,entity_id,caste,clan_id,generation,mother_id,father_id,born_tick,died_tick) VALUES (?,?,?,?,?,?,?,?,NULL)",
                        [(wid, eid, caste, clan_id, gen, mid or None, fid or None, bt) for wid, eid, caste, clan_id, gen, mid, fid, bt in births],
                    )
                if deaths:
                    for d_tuple in deaths:
                        wid = d_tuple[0]
                        eid = d_tuple[1]
                        dt = d_tuple[2]
                        p_name = d_tuple[3] if len(d_tuple) > 3 else None
                        title = d_tuple[4] if len(d_tuple) > 4 else None
                        kc = d_tuple[5] if len(d_tuple) > 5 else 0
                        cur = conn.execute(
                            "UPDATE creatures SET died_tick=?, personal_name=COALESCE(?, personal_name), "
                            "title=COALESCE(?, title), kill_count=MAX(?, COALESCE(kill_count, 0)) "
                            "WHERE world_id=? AND entity_id=? AND died_tick IS NULL",
                            (dt, p_name, title, kc, wid, eid),
                        )
                        if cur.rowcount == 0:
                            conn.execute(
                                "INSERT INTO creatures(world_id,entity_id,born_tick,died_tick,personal_name,title,kill_count) VALUES (?,?,NULL,?,?,?,?)",
                                (wid, eid, dt, p_name, title, kc),
                            )
            return len(ops)
        except sqlite3.Error:
            # Put the tail back at the front so nothing is lost; the writer
            # retries after the next heartbeat.
            with self._lock:
                for item in reversed(ops):
                    self._pending.appendleft(item)
            return 0

    def _write_event(self, world_id: int, e: HistoryEvent) -> None:
        assert self._conn is not None
        self._conn.execute(
            "INSERT INTO events(world_id,tick,type,entity_id,caste,cause,x,y,payload,created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                world_id,
                e.tick,
                e.type,
                e.entity_id,
                e.caste,
                e.cause,
                e.x,
                e.y,
                json.dumps(e.payload),
                _now(),
            ),
        )

    @contextmanager
    def batch(self) -> Iterator[None]:
        """Group the writes made inside the block into ONE commit.

        AA: the tick loop wraps each step, so a burst of chronicle/genealogy
        writes commits once per tick. A failure rolls the whole tick's writes
        back instead of half-committing them. Writes outside a batch behave
        exactly as before (each statement auto-commits).
        """
        with self._lock:
            if self._batch_depth == 0:
                self._require().execute("BEGIN")
            self._batch_depth += 1
        try:
            yield
        except Exception:
            with self._lock:
                self._batch_depth = 0
                try:
                    assert self._conn is not None
                    self._conn.rollback()
                except sqlite3.Error:
                    pass
            raise
        else:
            with self._lock:
                self._batch_depth -= 1
                if self._batch_depth == 0:
                    try:
                        assert self._conn is not None
                        self._conn.commit()
                    except sqlite3.Error:
                        pass

    def close(self) -> None:
        """Stop the writer, flush the RAM tail, close the connection."""
        self._stopping = True
        self._wake.set()
        if self._writer is not None:
            self._writer.join(timeout=5.0)
            self._writer = None
        try:
            self.flush()
        except Exception:
            pass
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    @property
    def connected(self) -> bool:
        return self._conn is not None

    def _require(self) -> sqlite3.Connection:
        self.connect()
        assert self._conn is not None
        return self._conn

    # --------------------------------------------------------------- worlds
    def new_world(self, cfg: Config) -> int:
        with self._lock:
            cur = self._require().execute(
                "INSERT INTO worlds(seed,width,height,boundary,started_at) VALUES (?,?,?,?,?)",
                (cfg.seed, cfg.width, cfg.height, cfg.boundary, _now()),
            )
            return int(cur.lastrowid)

    def end_world(self, world_id: int) -> None:
        """Close a world row — the RAM tail flushes first so its chronicle is complete."""
        self.flush()
        with self._lock:
            self._require().execute(
                "UPDATE worlds SET ended_at=? WHERE id=? AND ended_at IS NULL",
                (_now(), world_id),
            )

    def worlds(self, limit: int = 100) -> list[dict]:
        with self._lock:
            rows = self._require().execute(
                "SELECT * FROM worlds ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    # --------------------------------------------------------------- events
    def add_events(self, world_id: int, events: list[HistoryEvent]) -> None:
        if not events:
            return
        with self._lock:
            self._require().executemany(
                "INSERT INTO events(world_id,tick,type,entity_id,caste,cause,x,y,payload,created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                [
                    (
                        world_id,
                        e.tick,
                        e.type,
                        e.entity_id,
                        e.caste,
                        e.cause,
                        e.x,
                        e.y,
                        json.dumps(e.payload),
                        _now(),
                    )
                    for e in events
                ],
            )

    def history(
        self,
        world_id: int,
        since_id: int = 0,
        limit: int = 500,
        type_filter: str | None = None,
        types_filter: Sequence[str] | None = None,
        entity_id: int | None = None,
        clan_id: int | None = None,
        q: str | None = None,
    ) -> list[dict[str, Any]]:
        conditions = ["world_id=?"]
        params: list[Any] = [world_id]
        if since_id:
            conditions.append("id<?")
            params.append(since_id)
        if type_filter:
            conditions.append("type=?")
            params.append(type_filter)
        elif types_filter:
            placeholders = ",".join("?" * len(types_filter))
            conditions.append(f"type IN ({placeholders})")
            params.extend(types_filter)
        if entity_id is not None:
            conditions.append("entity_id=?")
            params.append(entity_id)
        if clan_id is not None:
            # §AT-1: SQL-level clan filter — any payload key that names a clan.
            ors = " OR ".join(
                f"json_extract(payload,'$.{k}')=?" for k in CLAN_PAYLOAD_KEYS
            )
            conditions.append(f"({ors})")
            params.extend([clan_id] * len(CLAN_PAYLOAD_KEYS))
        if q:
            # BM-25: Search query across type, caste, cause, and payload
            conditions.append("(type LIKE ? OR caste LIKE ? OR cause LIKE ? OR payload LIKE ?)")
            pattern = f"%{q}%"
            params.extend([pattern, pattern, pattern, pattern])
        params.append(limit)

        query = f"SELECT * FROM events WHERE {' AND '.join(conditions)} ORDER BY id DESC LIMIT ?"
        with self._lock:
            rows = self._require().execute(query, tuple(params)).fetchall()
        return [
            {
                "id": r["id"],
                "tick": r["tick"],
                "type": r["type"],
                "entity_id": r["entity_id"],
                "caste": r["caste"],
                "cause": r["cause"],
                "x": r["x"],
                "y": r["y"],
                "payload": json.loads(r["payload"] or "{}"),
            }
            for r in rows
        ]

    def death_count(self, world_id: int) -> int:
        with self._lock:
            row = self._require().execute(
                "SELECT COUNT(*) AS n FROM events WHERE world_id=? AND type='death'",
                (world_id,),
            ).fetchone()
        return int(row["n"])

    # ----------------------------------------------------------------- laws
    def add_law_change(
        self, world_id: int, tick: int, name: str, value: Any
    ) -> None:
        with self._lock:
            self._require().execute(
                "INSERT INTO law_changes(world_id,tick,name,value,created_at) VALUES (?,?,?,?,?)",
                (world_id, tick, name, json.dumps(value), _now()),
            )

    # ------------------------------------------------------------- genealogy
    def genealogy_parents(
        self, world_id: int, entity_id: int
    ) -> tuple[dict | None, dict | None]:
        """(mother, father) minimal cards from the genealogy table, if recorded."""
        with self._lock:
            row = self._require().execute(
                "SELECT mother_id, father_id FROM creatures"
                " WHERE world_id=? AND entity_id=?",
                (world_id, entity_id),
            ).fetchone()
        if row is None:
            return None, None
        cards: dict[str, dict | None] = {"m": None, "f": None}
        for pid, which in ((row["mother_id"], "m"), (row["father_id"], "f")):
            if not pid:
                continue
            with self._lock:
                prow = self._require().execute(
                    "SELECT caste FROM creatures WHERE world_id=? AND entity_id=?",
                    (world_id, pid),
                ).fetchone()
            cards[which] = {
                "id": pid,
                "caste": prow["caste"] if prow else None,
            }
        return cards["m"], cards["f"]

    def genealogy_children(self, world_id: int, entity_id: int) -> list[dict]:
        with self._lock:
            rows = self._require().execute(
                "SELECT entity_id, caste FROM creatures WHERE world_id=? AND mother_id=?"
                " UNION "
                "SELECT entity_id, caste FROM creatures WHERE world_id=? AND father_id=?",
                (world_id, entity_id, world_id, entity_id),
            ).fetchall()
        return [{"id": r["entity_id"], "caste": r["caste"]} for r in rows]

    def law_changes(self, world_id: int, limit: int = 200) -> list[dict]:
        with self._lock:
            rows = self._require().execute(
                "SELECT * FROM law_changes WHERE world_id=? ORDER BY id DESC LIMIT ?",
                (world_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------- genealogy
    def add_creature(
        self,
        world_id: int,
        entity_id: int,
        caste: str,
        clan_id: int,
        generation: int,
        mother_id: int,
        father_id: int,
        born_tick: int,
    ) -> None:
        with self._lock:
            self._require().execute(
                "INSERT INTO creatures(world_id,entity_id,caste,clan_id,generation,"
                "mother_id,father_id,born_tick,died_tick) VALUES (?,?,?,?,?,?,?,?,NULL)",
                (world_id, entity_id, caste, clan_id, generation,
                 mother_id or None, father_id or None, born_tick),
            )

    def mark_death(
        self,
        world_id: int,
        entity_id: int,
        died_tick: int,
        personal_name: str | None = None,
        title: str | None = None,
        kill_count: int = 0,
    ) -> None:
        with self._lock:
            cur = self._require().execute(
                "UPDATE creatures SET died_tick=?, personal_name=COALESCE(?, personal_name), "
                "title=COALESCE(?, title), kill_count=MAX(?, COALESCE(kill_count, 0)) "
                "WHERE world_id=? AND entity_id=?",
                (died_tick, personal_name, title, kill_count, world_id, entity_id),
            )
            if cur.rowcount == 0:  # founder with no birth record: insert minimal row
                self._require().execute(
                    "INSERT INTO creatures(world_id,entity_id,born_tick,died_tick,personal_name,title,kill_count)"
                    " VALUES (?,?,NULL,?,?,?,?)",
                    (world_id, entity_id, died_tick, personal_name, title, kill_count),
                )

    # -------------------------------------------------------- clan epitaphs
    def record_clan_epitaph(
        self,
        world_id: int,
        clan_id: int,
        name: str,
        totem: str | None = None,
        color: str | None = None,
        founded_tick: int = 0,
        extinct_tick: int = 0,
        peak_population: int = 0,
        peak_tick: int = 0,
        wars_fought: int = 0,
        battles_won: int = 0,
        temples_built: int = 0,
        schisms_caused: int = 0,
        extinction_cause: str = "eradication",
    ) -> None:
        with self._lock:
            self._require().execute(
                "INSERT INTO clan_epitaphs(world_id,clan_id,name,totem,color,founded_tick,extinct_tick,"
                "peak_population,peak_tick,wars_fought,battles_won,temples_built,schisms_caused,extinction_cause,created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    world_id, clan_id, name, totem, color, founded_tick, extinct_tick,
                    peak_population, peak_tick, wars_fought, battles_won, temples_built, schisms_caused,
                    extinction_cause, _now(),
                ),
            )

    def clan_epitaphs(self, world_id: int, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._require().execute(
                "SELECT * FROM clan_epitaphs WHERE world_id=? ORDER BY extinct_tick DESC LIMIT ?",
                (world_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def clan_epitaph(self, world_id: int, clan_id: int) -> dict[str, Any] | None:
        with self._lock:
            row = self._require().execute(
                "SELECT * FROM clan_epitaphs WHERE world_id=? AND clan_id=? ORDER BY id DESC LIMIT 1",
                (world_id, clan_id),
            ).fetchone()
        return dict(row) if row else None

    def clan_notables(self, world_id: int, clan_id: int) -> dict[str, Any]:
        with self._lock:
            hero_row = self._require().execute(
                "SELECT id, personal_name, title, kill_count FROM creatures "
                "WHERE world_id=? AND clan_id=? AND kill_count > 0 ORDER BY kill_count DESC, id ASC LIMIT 1",
                (world_id, clan_id),
            ).fetchone()
            return {
                "hero": dict(hero_row) if hero_row else None,
            }

    # -------------------------------------------------------------- snapshots
    def get_setting(self, key: str) -> str | None:
        with self._lock:
            row = self._require().execute(
                "SELECT value FROM settings WHERE key=?", (key,)
            ).fetchone()
        return row["value"] if row is not None else None

    def set_setting(self, key: str, value: str) -> None:
        with self._lock:
            self._require().execute(
                "INSERT INTO settings(key,value,created_at) VALUES (?,?,?)"
                " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value, _now()),
            )

    def delete_setting(self, key: str) -> None:
        with self._lock:
            self._require().execute("DELETE FROM settings WHERE key=?", (key,))

    def save_snapshot(self, world_id: int, tick: int, payload: str) -> int:
        """Freeze the world — the RAM tail flushes first so album order holds."""
        self.flush()
        with self._lock:
            cur = self._require().execute(
                "INSERT INTO snapshots(world_id,tick,payload,created_at) VALUES (?,?,?,?)",
                (world_id, tick, payload, _now()),
            )
            return int(cur.lastrowid)

    def list_snapshots(self, world_id: int, limit: int = 50) -> list[dict]:
        with self._lock:
            rows = self._require().execute(
                "SELECT id,world_id,tick,created_at FROM snapshots"
                " WHERE world_id=? ORDER BY id DESC LIMIT ?",
                (world_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_snapshot(self, snapshot_id: int) -> dict | None:
        with self._lock:
            row = self._require().execute(
                "SELECT * FROM snapshots WHERE id=?", (snapshot_id,)
            ).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["payload"] = json.loads(d["payload"])
        return d
