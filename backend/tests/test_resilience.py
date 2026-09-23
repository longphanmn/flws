"""Production hardening: a failed tick must never silently kill the world.

The tick engine used to die on any exception raised inside `step()` (e.g. the
DB event sink hitting `sqlite3.OperationalError: database is locked`). Because
uvicorn's lifespan held the task reference, asyncio never reported the
exception — the world just froze at some tick while HTTP kept serving, and
only a backend restart "fixed" it.
"""

import asyncio
import sqlite3
import threading
import time

from fastapi.testclient import TestClient

from app.config import Config
from app.main import Hub, RuntimeState, SimEngine, app


def quiet_cfg(**kw) -> Config:
    kw.setdefault("relief_enabled", False)
    zeros = dict(
        num_triangles=0, num_squares=0, num_pentagons=0, num_hexagons=0,
        num_priests=0, num_women=0, food_count=0, num_houses=0,
        weather_enabled=False,
    )
    zeros.update(kw)
    return Config(seed=7, **zeros)


def _run_engine(rt: RuntimeState, hub: Hub, seconds: float) -> None:
    """Drive the real SimEngine on a background event loop for a while."""
    engine = SimEngine(rt, hub)
    loop = asyncio.new_event_loop()
    ready = threading.Event()
    def _runner():
        asyncio.set_event_loop(loop)
        hub.start_queue(loop)
        ready.set()
        loop.run_forever()
    th = threading.Thread(target=_runner, daemon=True)
    th.start()
    ready.wait(timeout=1.0)
    try:
        engine.start(loop=loop)
        time.sleep(seconds)
    finally:
        engine.stop()
        loop.call_soon_threadsafe(hub.stop_queue)
        loop.call_soon_threadsafe(loop.stop)
        th.join(timeout=1)


def test_engine_survives_step_failure_and_keeps_ticking(capsys):
    rt = RuntimeState(quiet_cfg())
    calls = {"n": 0}
    original_step = rt.sim.step

    def flaky_step():
        calls["n"] += 1
        if calls["n"] == 2:
            raise sqlite3.OperationalError("database is locked")
        original_step()

    rt.sim.step = flaky_step

    # speed defaults to 10 tps → several ticks in 0.45s; an early one fails loudly
    _run_engine(rt, Hub(), seconds=0.45)

    assert calls["n"] >= 3  # it kept ticking past the failure
    assert rt.last_tick_error is not None and "database is locked" in rt.last_tick_error
    out = capsys.readouterr().out
    assert "[tick-engine] step() FAILED" in out  # loud, greppable marker


def test_healthz_surfaces_last_error():
    from app.main import RT

    client = TestClient(app)
    client.headers["X-God-Key"] = "test-key"
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert "tick" in body and "paused" in body
    RT.last_tick_error = "TestError: injected"
    try:
        body = client.get("/healthz").json()
        assert body["ok"] is False
        assert "injected" in body["last_tick_error"]
    finally:
        RT.last_tick_error = None


# -------------------------------------------------------------------------- #
# Wedged-client freeze (prod incident @ tick 10469): a half-dead WebSocket — #
# phone slept, proxy closed, TCP zero window — made `await ws.send_text()`
# block FOREVER inside Hub.broadcast, parking the tick loop at the broadcast
# await. HTTP kept serving, healthz said ok:true, nothing was logged: the
# world froze silently. Broadcasts must be per-client-timeboxed and wedged
# clients dropped; healthy clients must keep receiving.
# -------------------------------------------------------------------------- #


class _FakeWS:
    """Minimal stand-in for starlette WebSocket."""

    def __init__(self, delay: float | None = None, fail: bool = False):
        self.delay = delay  # None → instant; float seconds → slow/wedged
        self.fail = fail
        self.sent: list[str] = []
        self.dropped = False

    async def send_text(self, text: str) -> None:
        if self.fail:
            raise RuntimeError("connection gone")
        if self.delay is None:
            self.sent.append(text)
        else:
            await asyncio.sleep(self.delay)  # never appends if wedged


def test_broadcast_survives_wedged_client_and_keeps_others_alive():
    hub = Hub()
    fast = _FakeWS()
    slow = _FakeWS(delay=hub.SEND_TIMEOUT * 10)  # effectively frozen socket
    broken = _FakeWS(fail=True)
    hub.clients.update({fast, slow, broken})

    old_timeout = Hub.SEND_TIMEOUT
    Hub.SEND_TIMEOUT = 0.05
    try:
        asyncio.run(hub.broadcast({"type": "state", "tick": 1}))
    finally:
        Hub.SEND_TIMEOUT = old_timeout

    assert len(fast.sent) == 1            # healthy client got the frame
    assert fast in hub.clients
    assert slow not in hub.clients        # wedged client was cut loose
    assert broken not in hub.clients      # erroring client was cut loose


def test_engine_keeps_ticking_with_a_wedged_client_connected(capsys):
    rt = RuntimeState(quiet_cfg(num_triangles=2))
    hub = Hub()
    wedged = _FakeWS(delay=999)           # accepts frames but never drains
    hub.clients.add(wedged)

    old_timeout = Hub.SEND_TIMEOUT
    Hub.SEND_TIMEOUT = 0.05
    hub.SEND_TIMEOUT = 0.05
    try:
        _run_engine(rt, hub, seconds=0.6)
    finally:
        Hub.SEND_TIMEOUT = 10.0
        hub.SEND_TIMEOUT = 10.0

    assert rt.sim.tick >= 3               # world advanced despite the wedge
    assert wedged not in hub.clients      # and the wedge was evicted
