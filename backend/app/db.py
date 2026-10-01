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

# ---------------------------------------------------------------------------
# §3.2 Lever 1 — tiered chronicle: bound the events table's GROWTH RATE.
#
# `config.history_max` caps the in-memory chronicle at 200 events, so SQLite is
# the only durable record and nothing may be deleted. The lever is therefore
# *what gets written*, not *how much is kept*: high-frequency texture is kept
# in a RAM ring (still readable through the pending_events() overlay) and only
# sampled types land in the table.
#
# The map is a DENYLIST on purpose: NOISE and SAMPLED are explicit opt-outs and
# every other type HistoryEvent can emit defaults to MILESTONE. A new event type
# therefore stays durable until someone deliberately reclassifies it — the safe
# direction to fail in.
MILESTONE = "MILESTONE"
SAMPLED = "SAMPLED"
NOISE = "NOISE"

# Mirrors main.MAJOR_EVENT_TYPES (the `major=true` view) plus the lifecycle
# events the genealogy/annals paths depend on. death/birth MUST stay here: the
# world_stats counter (§3.4) is fed from durable death rows.
MILESTONE_EVENT_TYPES = frozenset({
    "death", "birth", "promotion",
    "war", "conquest", "takeover", "schism", "betrayal", "alliance",
    "coalition_formed", "peace", "regicide", "succession", "outbreak",
    "disaster", "miracle", "synod", "temple", "epiphany",
    "extinction", "clan_extinction",
    "ruin", "exile", "settlement", "banquet",
})
# Real but high-frequency: kept at 1 in CHRONICLE_SAMPLE_EVERY, never dropped.
SAMPLED_EVENT_TYPES = frozenset({
    "fire", "predation", "cannibalism", "raid", "market", "caravan",
    "demotion", "recovery",
})
# Ambient texture that never reaches SQLite (bloom/wither/culture/rivalry/
# peace_envoy were already dropped by the app-layer sink; kept here so the rule
# lives in one place).
NOISE_EVENT_TYPES = frozenset({
    "bloom", "wither", "culture", "rivalry", "peace_envoy",
})
# Every type HistoryEvent can emit, so the map is total and drift is caught by
# test_db_tiers.test_every_emittable_type_is_classified_into_exactly_one_tier.
EMITTABLE_EVENT_TYPES = frozenset({
    "death", "birth", "promotion", "demotion", "outbreak", "recovery",
    "bloom", "alliance", "rivalry", "predation", "war", "ruin", "settlement",
    "succession", "schism", "fire", "disaster", "conquest", "culture",
    "coalition_formed", "coalition_joined", "coalition_dissolved",
    "peace", "tribute", "betrayal", "defection", "cannibalism", "exile",
    "wither", "takeover", "miracle", "sermon", "synod", "temple", "epiphany",
    "resonance", "compost", "banquet", "raid", "hospitality",
    "peace_envoy", "market", "caravan", "omen", "regicide", "herald",
    "anomaly", "clan_extinction", "extinction",
})
EVENT_TIERS: dict[str, str] = {
    **{t: MILESTONE for t in EMITTABLE_EVENT_TYPES},
    **{t: SAMPLED for t in SAMPLED_EVENT_TYPES},
    **{t: NOISE for t in NOISE_EVENT_TYPES},
}

# 1 in N sampled events is durable.
CHRONICLE_SAMPLE_EVERY = 10
# A fire/disaster storm inside ONE tick must not flood the table: the first N
# sampled-type events of a tick keep their SAMPLED tier, the rest degrade to
# NOISE (ring only). Per-tick, so a slow steady rate is unaffected.
NOISE_PER_TICK_CAP = 3
# RAM ring capacity for non-durable texture (~last few hundred ticks).
NOISE_RING_MAX = 5000
# Chronicle rows per multi-row INSERT (10 binds each, so 2000 stays far below
# SQLite's variable ceiling while keeping the flush to a handful of statements).
EVENT_INSERT_CHUNK = 2000


def _by_world(events: Sequence[HistoryEvent]) -> dict[int, list[HistoryEvent]]:
    """Group chronicle events by world, preserving arrival order within a world."""
    out: dict[int, list[HistoryEvent]] = {}
    for wid, ev in events:
        out.setdefault(wid, []).append(ev)
    return out

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
-- §3.3: clan -> event lookup. The payload is parsed ONCE in Python (it is
-- already a dict there), so the clan filter is a covering-index search instead
-- of 13 json_extract calls that each re-parse the whole payload TEXT.
CREATE TABLE IF NOT EXISTS event_clans (
    world_id INTEGER NOT NULL,
    clan_id  INTEGER NOT NULL,
    event_id INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_event_clans ON event_clans(world_id, clan_id, event_id DESC);
-- §3.4: materialized death counter. death_count() is called on every
-- /api/history, /healthz poll and snapshot restore; COUNT(*) over a 2.7M-row
-- index cost 9 ms each time. Bumped inside the flush transaction that already
-- writes the death rows, so it can never disagree with them and rolls back
-- with them. (A SQL TRIGGER was measured at ~10x the write cost — rejected.)
CREATE TABLE IF NOT EXISTS world_stats (
    world_id    INTEGER PRIMARY KEY,
    death_count INTEGER NOT NULL DEFAULT 0
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _row_of(r: Any) -> dict[str, Any]:
    """Project a durable events row into the API's event shape.

    Explicit columns, never SELECT * consumers: `created_at` is dropped in §3.5
    and any new column must not leak into the response.
    """
    return {
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


def _clan_ids_of(payload: dict[str, Any] | None) -> list[int]:
    """§3.3: the clan ids an event names, deduped — the side-table row source.

    CLAN_PAYLOAD_KEYS stays the single source of truth for which payload keys
    count. Only ints count (a JSON string "3" never matched the old SQL
    comparison either, and booleans are not clan ids).
    """
    if not payload:
        return []
    out: list[int] = []
    seen: set[int] = set()
    for key in CLAN_PAYLOAD_KEYS:
        value = payload.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _overlay_row(ev: Any) -> dict[str, Any]:
    """Shape a HistoryEvent like a durable row for the RAM overlay."""
    try:
        payload = ev.payload if hasattr(ev, "payload") else {}
    except Exception:
        payload = {}
    return {
        "id": 0,  # pending has no row id yet; sort after DB rows
        "tick": getattr(ev, "tick", 0),
        "type": getattr(ev, "type", ""),
        "entity_id": getattr(ev, "entity_id", None),
        "caste": getattr(ev, "caste", None),
        "cause": getattr(ev, "cause", None),
        "x": getattr(ev, "x", None),
        "y": getattr(ev, "y", None),
        "payload": dict(payload) if isinstance(payload, dict) else {},
    }


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
        # §3.2: RAM ring for non-durable texture — never reaches SQLite, but the
        # pending_events() overlay still serves it so the web/TUI keeps texture.
        self._noise: deque[tuple[int, HistoryEvent]] = deque(maxlen=NOISE_RING_MAX)
        # per-tick burst counter for SAMPLED types (reset when the tick moves on)
        self._burst_tick: int = -1
        self._burst_count: int = 0
        # how many SAMPLED events have been offered (1 in CHRONICLE_SAMPLE_EVERY)
        self._sample_seen: int = 0

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

    @property
    def noise_pending(self) -> int:
        """Non-durable events held in the RAM ring (overlay visibility only)."""
        return len(self._noise)

    @property
    def ram_events(self) -> int:
        """Un-flushed chronicle events an overlay can serve: durable tail + ring."""
        return len(self._pending) + len(self._noise)

    def classify(self, e: HistoryEvent) -> str:
        """§3.2: which tier this event belongs to — MILESTONE | SAMPLED | NOISE.

        Pure decision plus RAM-only counters (no I/O, safe on the sim thread).
        SAMPLED events beyond NOISE_PER_TICK_CAP in the same tick degrade to
        NOISE so a single-tick fire/disaster storm cannot flood the table.
        """
        tier = EVENT_TIERS.get(e.type, MILESTONE)
        if tier != SAMPLED:
            return tier
        if e.tick != self._burst_tick:
            self._burst_tick = e.tick
            self._burst_count = 0
        self._burst_count += 1
        return SAMPLED if self._burst_count <= NOISE_PER_TICK_CAP else NOISE

    def _ring(self, world_id: int, e: HistoryEvent) -> None:
        self._noise.append((world_id, e))

    def pending_events(self, world_id: int, limit: int = 500) -> list[dict[str, Any]]:
        """Read-your-writes from RAM without forcing a flush.

        AZ Phase 1 P1: the durable OS-log tail. §3.2: also serves the NOISE
        ring, so non-durable texture (fire storms, blooms) is still visible to
        /api/history and the TUI. Merged newest-first by tick.
        """
        with self._lock:
            pending_copy = list(self._pending)
            noise_copy = list(self._noise)
        out: list[dict[str, Any]] = []
        for kind, args in reversed(pending_copy):
            if kind != "event":
                continue
            wid, ev = args  # type: ignore
            if wid != world_id:
                continue
            out.append(_overlay_row(ev))
            if len(out) >= limit:
                break
        for wid, ev in reversed(noise_copy):
            if wid != world_id:
                continue
            out.append(_overlay_row(ev))
            if len(out) >= limit:
                break
        out.sort(key=lambda r: r["tick"], reverse=True)
        return out[:limit]

    def _bump_high_water(self) -> None:
        n = len(self._pending)
        if n > self._pending_high_water:
            self._pending_high_water = n
            self._pending_high_water_mark = n

    # ------------------------------------------------------------- §AD queue
    def log_event(self, world_id: int, event: HistoryEvent) -> None:
        """Buffer one chronicle event (sim thread never touches SQLite).

        §3.2 tiering: NOISE goes to the RAM ring only; SAMPLED is mirrored into
        the ring and made durable 1 in CHRONICLE_SAMPLE_EVERY; MILESTONE is
        always durable. Classification lives here — the single choke point every
        chronicle write passes through — so the app-layer sink needs no filter.
        """
        tier = self.classify(event)
        if tier == NOISE:
            self._ring(world_id, event)
            return
        if tier == SAMPLED:
            self._ring(world_id, event)
            self._sample_seen += 1
            if self._sample_seen % CHRONICLE_SAMPLE_EVERY:
                return
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
                for wid, evs in _by_world(events).items():
                    self._insert_events(wid, evs)
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

    @property
    def connection(self) -> sqlite3.Connection:
        """The live connection (diagnostics: pragmas, EXPLAIN QUERY PLAN, census).

        Not a write path — callers must not mutate schema through it.
        """
        return self._require()

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
    def _insert_events(self, world_id: int, events: Sequence[HistoryEvent]) -> list[int]:
        """Write chronicle rows and return their ids, filling event_clans.

        One multi-row statement per chunk with RETURNING: the ids come back with
        the insert, so event_clans is filled in the same transaction without a
        second query and without assuming contiguous ids on a shared connection.

        The §3.4 death counter is bumped here for the same reason: `death` is a
        MILESTONE tier (so it is always durable) and this loop already sees every
        row, which keeps the counter exact for BOTH entry points — including
        add_events(), which writes death rows with no genealogy op beside them.
        """
        conn = self._require()
        now = _now()
        rows = [
            (world_id, e.tick, e.type, e.entity_id, e.caste, e.cause, e.x, e.y,
             json.dumps(e.payload), now)
            for e in events
        ]
        ids: list[int] = []
        for start in range(0, len(rows), EVENT_INSERT_CHUNK):
            chunk = rows[start:start + EVENT_INSERT_CHUNK]
            sql = (
                "INSERT INTO events(world_id,tick,type,entity_id,caste,cause,x,y,payload,created_at)"
                " VALUES " + ",".join(["(?,?,?,?,?,?,?,?,?,?)"] * len(chunk))
                + " RETURNING id"
            )
            ids.extend(int(r[0]) for r in conn.execute(sql, [v for row in chunk for v in row]))
        clan_rows = [
            (world_id, clan_id, event_id)
            for event_id, e in zip(ids, events)
            for clan_id in _clan_ids_of(e.payload)
        ]
        if clan_rows:
            conn.executemany(
                "INSERT INTO event_clans(world_id, clan_id, event_id) VALUES (?,?,?)", clan_rows
            )
        deaths = sum(1 for e in events if e.type == "death")
        if deaths:
            conn.execute(
                "INSERT INTO world_stats(world_id, death_count) VALUES (?, ?)"
                " ON CONFLICT(world_id) DO UPDATE SET death_count = death_count + excluded.death_count",
                (world_id, deaths),
            )
        return ids

    def add_events(self, world_id: int, events: list[HistoryEvent]) -> None:
        if not events:
            return
        with self._lock:
            self._insert_events(world_id, events)

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
            # §3.3: the clan filter is answered by the side table, never by
            # parsing JSON in SQL. event_clans' (world_id, clan_id, event_id
            # DESC) index serves both the lookup and the newest-first order.
            return self._clan_history(
                world_id, since_id, limit, type_filter, types_filter, entity_id, clan_id, q
            )
        if q:
            # BM-25: Search query across type, caste, cause, and payload
            conditions.append("(type LIKE ? OR caste LIKE ? OR cause LIKE ? OR payload LIKE ?)")
            pattern = f"%{q}%"
            params.extend([pattern, pattern, pattern, pattern])
        params.append(limit)

        query = f"SELECT * FROM events WHERE {' AND '.join(conditions)} ORDER BY id DESC LIMIT ?"
        with self._lock:
            rows = self._require().execute(query, tuple(params)).fetchall()
        return [_row_of(r) for r in rows]

    def _clan_history(
        self,
        world_id: int,
        since_id: int,
        limit: int,
        type_filter: str | None,
        types_filter: Sequence[str] | None,
        entity_id: int | None,
        clan_id: int,
        q: str | None,
    ) -> list[dict[str, Any]]:
        conditions = ["ec.world_id=?", "ec.clan_id=?", "e.world_id=?"]
        params: list[Any] = [world_id, clan_id, world_id]
        if since_id:
            conditions.append("e.id<?")
            params.append(since_id)
        if type_filter:
            conditions.append("e.type=?")
            params.append(type_filter)
        elif types_filter:
            placeholders = ",".join("?" * len(types_filter))
            conditions.append(f"e.type IN ({placeholders})")
            params.extend(types_filter)
        if entity_id is not None:
            conditions.append("e.entity_id=?")
            params.append(entity_id)
        if q:
            conditions.append("(e.type LIKE ? OR e.caste LIKE ? OR e.cause LIKE ? OR e.payload LIKE ?)")
            pattern = f"%{q}%"
            params.extend([pattern, pattern, pattern, pattern])
        params.append(limit)
        query = (
            "SELECT e.id, e.tick, e.type, e.entity_id, e.caste, e.cause, e.x, e.y, e.payload"
            f" FROM event_clans ec JOIN events e ON e.id = ec.event_id"
            f" WHERE {' AND '.join(conditions)} ORDER BY ec.event_id DESC LIMIT ?"
        )
        with self._lock:
            rows = self._require().execute(query, tuple(params)).fetchall()
        return [_row_of(r) for r in rows]

    def death_count(self, world_id: int) -> int:
        """§3.4: the durable death total from world_stats — no table scan.

        Falls back to COUNT(*) (and seeds the counter) for a world whose death
        rows predate the counter, so a migrated file never under-reports.
        """
        with self._lock:
            conn = self._require()
            row = conn.execute(
                "SELECT death_count FROM world_stats WHERE world_id=?", (world_id,)
            ).fetchone()
            if row is not None:
                return int(row["death_count"])
            legacy = conn.execute(
                "SELECT COUNT(*) AS n FROM events WHERE world_id=? AND type='death'",
                (world_id,),
            ).fetchone()
            count = int(legacy["n"])
            conn.execute(
                "INSERT INTO world_stats(world_id, death_count) VALUES (?, ?)"
                " ON CONFLICT(world_id) DO UPDATE SET death_count = excluded.death_count",
                (world_id, count),
            )
            return count

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
