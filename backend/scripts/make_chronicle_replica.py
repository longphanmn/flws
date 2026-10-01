#!/usr/bin/env python3
"""Build a production-shaped LEGACY replica of the chronicle, for measurement.

The pre-§3.5 numbers in the plan came from a 2.7M-row replica. This regenerates an
equivalent file with the OLD schema — 4 KB pages, `created_at`, `AUTOINCREMENT`,
the two overlapping 2-column indexes — so `scripts/migrate_db.py --bench` can be
measured end to end: file size before/after and every read path before/after, on
the SAME data.

    python3 scripts/make_chronicle_replica.py /var/tmp/chron/replica.db 2700000
    python3 scripts/migrate_db.py --db /var/tmp/chron/replica.db --bench

It is a measurement tool, not part of the service: the event mix is a synthetic
but realistic weighting (deaths and births dominate, fire/bloom/disaster trickle),
so the ABSOLUTE numbers are replica numbers, not production numbers. Re-cut the
tier map from `GET /api/diagnostics/db-census?deep=true` against the real file.
"""
import json
import os
import random
import sqlite3
import sys
import time

LEGACY = """
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
CREATE INDEX idx_events_world_entity ON events(world_id, entity_id, id DESC);
"""

# Weighted like a real chronicle: deaths and births dominate, everything else trickles.
MIX = [
    ("death", 34, lambda r: {"personal_name": f"creature-{r.randint(1, 4000)}",
                             "clan_id": r.randint(1, 40), "kills": r.randint(0, 3),
                             "generation": r.randint(1, 40)}),
    ("birth", 30, lambda r: {"mother": r.randint(1, 4000), "father": r.randint(1, 4000),
                             "clan_id": r.randint(1, 40), "generation": r.randint(1, 40)}),
    ("war", 8, lambda r: {"a": r.randint(1, 40), "b": r.randint(1, 40), "lethal": True,
                          "battlefield": "field", "winner_name": "X"}),
    ("fire", 8, lambda r: {"trees": r.randint(1, 900), "x": r.random() * 100}),
    ("bloom", 6, lambda r: {"kind": "flower", "n": r.randint(1, 9)}),
    ("food_eaten", 5, lambda r: {"entity_id": r.randint(1, 4000), "amount": 1}),
    ("temple", 3, lambda r: {"clan_id": r.randint(1, 40), "clan_name": "Order"}),
    ("predation", 3, lambda r: {"predator": r.randint(1, 4000), "prey": r.randint(1, 4000)}),
    ("disaster", 2, lambda r: {"kind": "flood", "severity": r.random()}),
    ("miracle", 1, lambda r: {"kind": "sign", "clan_id": r.randint(1, 40)}),
]
KINDS = [k for k, _, _ in MIX]
WEIGHTS = [w for _, w, _ in MIX]
BUILDERS = {k: b for k, _, b in MIX}
CASTES = ["Soldier", "Worker", "Priest", "Noble", "Woman", "Merchant", None]
CAUSES = ["starvation", "combat", "old_age", "predation", "cannibalism", "disease", ""]


def build(path: str, rows: int, worlds: int = 3, seed: int = 7) -> None:
    r = random.Random(seed)
    if os.path.exists(path):
        os.remove(path)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA page_size=4096")
    conn.execute("PRAGMA journal_mode=OFF")
    conn.execute("PRAGMA synchronous=OFF")
    conn.executescript(LEGACY)
    for w in range(1, worlds + 1):
        conn.execute(
            "INSERT INTO worlds(id,seed,width,height,boundary,started_at,ended_at) VALUES (?,?,?,?,?,?,?)",
            (w, w * 7919, 100.0, 100.0, "clamp", "2026-01-01T00:00:00+00:00", None),
        )
    per_world = rows // worlds
    t0 = time.perf_counter()
    idc = 0
    for w in range(1, worlds + 1):
        batch = []
        for i in range(per_world):
            idc += 1
            kind = r.choices(KINDS, WEIGHTS)[0]
            payload = BUILDERS[kind](r)
            batch.append((w, i, kind, r.randint(1, 4000), r.choice(CASTES), r.choice(CAUSES),
                          r.random() * 100, r.random() * 100, json.dumps(payload),
                          f"2026-01-01T00:00:{idc % 60:02d}+00:00"))
            if len(batch) >= 20000:
                conn.executemany(
                    "INSERT INTO events(world_id,tick,type,entity_id,caste,cause,x,y,payload,created_at)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?)", batch)
                batch = []
        if batch:
            conn.executemany(
                "INSERT INTO events(world_id,tick,type,entity_id,caste,cause,x,y,payload,created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)", batch)
        conn.commit()
        print(f"  world {w}: {per_world} rows ({time.perf_counter() - t0:.0f}s)", flush=True)
    conn.commit()
    conn.close()
    print(f"built {idc} rows in {time.perf_counter() - t0:.0f}s -> "
          f"{os.path.getsize(path) / 1e6:.0f} MB")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "/var/tmp/replica.db"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 2_700_000
    build(out, n)
