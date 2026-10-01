"""§3.5 — the `q=` chronicle search is windowed and treats LIKE metacharacters
as literal text.

The search is `LIKE '%q%'` across type/caste/cause/payload, which is a full scan
of the world (measured 103-757 ms on a 2.7M-row table). FTS5 was measured worse
(+53% file size, 3881 ms for `MATCH 'clan'`), so the fix is to bound the scan:
only the newest `Q_SEARCH_WINDOW` events are candidates, and the pattern is
escaped so a user's `%` is a percent sign and not a wildcard.
"""

import sqlite3

import pytest

from app.config import Config
from app.db import Q_SEARCH_WINDOW, Database
from app.protocol import HistoryEvent


@pytest.fixture()
def db(tmp_path):
    d = Database(str(tmp_path / "q.db"))
    try:
        yield d
    finally:
        d.close()


def _seed(db, wid, n: int) -> None:
    db.add_events(wid, [
        HistoryEvent(type="war", tick=i, entity_id=i, caste="Soldier", cause="combat",
                     x=0.0, y=0.0, payload={"personal_name": f"creature-{i}"})
        for i in range(1, n + 1)
    ])


def test_search_finds_a_match_inside_the_window(db, monkeypatch):
    monkeypatch.setattr("app.db.Q_SEARCH_WINDOW", 10)
    wid = db.new_world(Config(seed=1))
    _seed(db, wid, 40)
    assert len(db.history(wid, q="creature-38", limit=100)) == 1


def test_search_ignores_matches_older_than_the_window(db, monkeypatch):
    """The bound is what makes the scan cheap: only the newest N events are candidates."""
    monkeypatch.setattr("app.db.Q_SEARCH_WINDOW", 10)
    wid = db.new_world(Config(seed=1))
    _seed(db, wid, 40)
    # candidates are ticks 31..40, and none of them is named "creature-2"
    assert db.history(wid, q="creature-2", limit=100) == []
    # tick 2's own event is outside the window...
    # ...and it comes back when the window is wide enough
    monkeypatch.setattr("app.db.Q_SEARCH_WINDOW", 100)
    ticks = [e["tick"] for e in db.history(wid, q="creature-2", limit=100)]
    assert 2 in ticks and len(ticks) == 11  # tick 2 plus 20..29


def test_search_window_defaults_to_the_documented_size():
    assert Q_SEARCH_WINDOW == 50_000


def test_search_treats_like_wildcards_as_literal_text(db):
    """`q=%` must not match every row: LIKE metacharacters are escaped."""
    wid = db.new_world(Config(seed=1))
    db.add_events(wid, [
        HistoryEvent(type="war", tick=1, entity_id=1, payload={"personal_name": "half 50% done"}),
        HistoryEvent(type="war", tick=2, entity_id=2, payload={"personal_name": "unrelated"}),
        HistoryEvent(type="war", tick=3, entity_id=3, payload={"personal_name": "a_b"}),
    ])
    assert [e["tick"] for e in db.history(wid, q="50%")] == [1]
    assert [e["tick"] for e in db.history(wid, q="%")] == [1]
    assert [e["tick"] for e in db.history(wid, q="a_b")] == [3]
    assert db.history(wid, q="axb") == []  # _ is not a wildcard any more


def test_search_does_not_let_a_wildcard_run_the_table(db, monkeypatch):
    """The scan is bounded even when the pattern would otherwise match everything."""
    monkeypatch.setattr("app.db.Q_SEARCH_WINDOW", 10)
    wid = db.new_world(Config(seed=1))
    _seed(db, wid, 500)
    seen: list[str] = []
    db.connection.set_trace_callback(seen.append)
    got = db.history(wid, q="creature", limit=1000)
    db.connection.set_trace_callback(None)
    plan = " ; ".join(
        r["detail"] for r in db.connection.execute(
            "EXPLAIN QUERY PLAN " + seen[-1]
        ).fetchall()
    )
    # the window is an id range off MAX(id), so the backwards scan still stops
    # early on a broad match instead of materialising a candidate list
    assert "SCAN events" not in plan, plan
    assert "TEMP B-TREE" not in plan, plan
    assert "MAX(id)" in seen[-1], seen[-1]
    assert [e["tick"] for e in got] == list(range(500, 490, -1))  # 10 newest, not 500


def test_search_still_applies_to_type_and_cause(db):
    wid = db.new_world(Config(seed=1))
    db.add_events(wid, [
        HistoryEvent(type="temple", tick=1, entity_id=1),
        HistoryEvent(type="death", tick=2, entity_id=2, cause="starvation"),
    ])
    assert [e["type"] for e in db.history(wid, q="temple")] == ["temple"]
    assert [e["type"] for e in db.history(wid, q="starvation")] == ["death"]


def test_search_row_count_is_observable(db, monkeypatch):
    """`q=` combined with other filters still honours limit and newest-first."""
    monkeypatch.setattr("app.db.Q_SEARCH_WINDOW", 50)
    wid = db.new_world(Config(seed=1))
    _seed(db, wid, 50)
    got = db.history(wid, q="creature", limit=3)
    assert [e["tick"] for e in got] == [50, 49, 48]
    assert sqlite3.connect(db.path).execute(
        "SELECT COUNT(*) FROM events WHERE world_id=?", (wid,)
    ).fetchone()[0] == 50
