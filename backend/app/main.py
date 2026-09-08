"""FastAPI application: WebSocket state broadcast + control, REST helpers — Developer: Long Phan <long@minhnhan.in>."""

import asyncio
import json
import os
import random
import sys
import threading
import time
import traceback
from contextlib import asynccontextmanager
from dataclasses import asdict, replace
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from pydantic import ValidationError

from .auth import PasskeyAuth, SetupPasskey, require_god
from .config import Config
from .db import CLAN_PAYLOAD_KEYS, Database
from .protocol import ControlAction, ControlMessage, GodLaws, HelloMessage, StateMessage
from .entities import Creature
from .simulation import Simulation, glyph_for, personal_name_for, variation_for

MIN_SPEED = 0.5  # ticks per second
MAX_SPEED = 120.0

# AZ Phase 1 P1: caches for blocking calls off the event loop
_VERSION_CACHE: dict | None = None
_WIKI_CACHE: dict[str, str] = {}
_PROCSTAT_CACHE: tuple[float, list[dict]] | None = None  # (timestamp, cores)
# BD.1.3 analytics cache (1s memoization)
_ANALYTICS_CACHE: dict[str, tuple[float, dict]] = {}

# AA: C-extension JSON for the ~30 Hz broadcast (GIL-releasing encode);
# falls back to stdlib when orjson is not installed.
try:
    import orjson

    def _dumps(payload: dict) -> str:
        return orjson.dumps(payload, option=orjson.OPT_NON_STR_KEYS).decode("utf-8")
except ModuleNotFoundError:  # pragma: no cover - fallback envs

    def _dumps(payload: dict) -> str:
        return json.dumps(payload, separators=(",", ":"))


class Hub:
    """Tracks connected WebSocket clients and broadcasts snapshots.

    A half-dead client (phone slept, NAT dropped, proxy closed) makes
    `send_text` block forever — that used to park the whole tick loop at
    the broadcast await while HTTP stayed fine (world frozen, ok:true,
    nothing logged). Now every send gets a timeout; wedged clients are
    dropped and the world keeps ticking.

    §AX P0: permessage-deflate disabled on LAN — synchronous zlib on every
    frame cost 33% CPU. See run.sh --ws-per-message-deflate.
    AZ Phase 1 P0: bounded broadcast queue (maxsize 1) — wedged client with
    5 s SEND_TIMEOUT no longer grows memory without limit.
    """

    SEND_TIMEOUT = 5.0  # seconds a client may take per frame before we cut it

    def __init__(self) -> None:
        self.clients: set[WebSocket] = set()
        self._queue: asyncio.Queue[str] | None = None
        self._consumer_task: asyncio.Task | None = None

    def start_queue(self, loop: asyncio.AbstractEventLoop) -> None:
        if self._queue is not None:
            return
        self._queue = asyncio.Queue(maxsize=1)
        self._consumer_task = loop.create_task(self._consume())

    def stop_queue(self) -> None:
        if self._consumer_task is not None:
            self._consumer_task.cancel()
            self._consumer_task = None

    async def _consume(self) -> None:
        assert self._queue is not None
        while True:
            try:
                text = await self._queue.get()
            except asyncio.CancelledError:
                break
            try:
                await self.broadcast_text(text)
            except Exception:
                pass
            finally:
                self._queue.task_done()

    def enqueue_text(self, text: str, loop: asyncio.AbstractEventLoop) -> None:
        """Thread-safe bounded enqueue: drop stale frame on QueueFull."""
        if not text or not self.clients:
            return
        if self._queue is None:
            # fallback: direct fan-out (startup race)
            asyncio.run_coroutine_threadsafe(self.broadcast_text(text), loop)
            return
        def _put():
            try:
                self._queue.put_nowait(text)  # type: ignore
            except asyncio.QueueFull:
                try:
                    self._queue.get_nowait()  # type: ignore
                    self._queue.task_done()
                except Exception:
                    pass
                try:
                    self._queue.put_nowait(text)  # type: ignore
                except Exception:
                    pass
        try:
            loop.call_soon_threadsafe(_put)
        except Exception:
            pass

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.clients.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self.clients.discard(ws)

    async def _send(self, ws: WebSocket, text: str) -> None:
        try:
            await asyncio.wait_for(ws.send_text(text), timeout=self.SEND_TIMEOUT)
        except Exception:
            self.disconnect(ws)

    async def broadcast(self, payload: dict) -> None:
        if not self.clients:
            return
        text = _dumps(payload)
        # Concurrent fan-out: one slow client costs nobody else its timeout.
        await asyncio.gather(
            *(self._send(ws, text) for ws in list(self.clients)),
            return_exceptions=True,
        )

    async def broadcast_text(self, text: str) -> None:
        """§AX P0: single-pass serialization — tick-engine thread already did
        _dumps; event loop just fans out the immutable bytes."""
        if not self.clients or not text:
            return
        await asyncio.gather(
            *(self._send(ws, text) for ws in list(self.clients)),
            return_exceptions=True,
        )


class RuntimeState:
    """Shared mutable runtime: current simulation, pause flag, ticks/sec.

    `lock` guards every touch of the live simulation. Since the tick engine
    runs on its own thread, REST/WS handlers must hold it while reading or
    mutating world state so nobody ever sees a half-advanced tick.
    """

    def __init__(self, config: Config | None = None):
        self.config = config or Config.from_env()
        self.sim = Simulation(self.config)
        self.paused = False
        self.speed = self.config.tick_rate
        self.world_id: int | None = None
        # Last failed tick (if any), sticky for diagnosis — surfaced via
        # /healthz so a sick world is visible without ssh-ing into the box.
        self.last_tick_error: str | None = None
        self.tick_failures = 0
        # Baseline laws that survive Reset (Save). Apply mutates only self.config.
        self.saved_config = self.config
        self.current_preset: str | None = "sustainable"
        self.lock = threading.RLock()
        # §AX P0: lockless snapshot caches — tick-engine thread publishes
        # immutable payloads; REST handlers read without acquiring RT.lock.
        self._cached_clans_payload: dict | None = None
        self._cached_state_text: str | None = None
        # Tick timing ring buffer for /healthz diagnostics (true rate vs target)
        self._tick_times: list[float] = []  # monotonic timestamps of last 300 ticks
        self._tick_durs: list[float] = []  # durations (ms) of last 300 steps
        self._tick_creature_counts: list[int] = []  # creature count at each tick
        # Whole world session tracking for /healthz & diagnostics
        self.session_started_at: float = time.time()
        self.session_start_tick: int = 0
        # Session rollup: stores per-minute stats covering the entire world session (up to 7 days = 10,080 min).
        # One bucket per wall-clock minute.
        from collections import deque as _deque

        self._tick_min_cur: list = [0, 0, 0.0, 0.0, 0, 0, 0, 0]  # [min_key, n, sum_ms, max_ms, sum_pop, overruns, sum_food, last_tick]
        self._tick_minutes: _deque = _deque(maxlen=10080)  # finalized minute dicts, oldest first (7-day capacity)


CONFIG = Config.from_env()
RT = RuntimeState(CONFIG)
HUB = Hub()
DB = Database(os.environ.get("FLATWORLD_DB", str(Path(__file__).resolve().parent.parent / "flatworld.db")))


def start_world() -> None:
    """Register a fresh world row and attach the durable event sink."""
    if RT.world_id is not None:
        DB.end_world(RT.world_id)
    RT.world_id = DB.new_world(RT.config)
    RT.sim.on_event = _on_event


def _on_event(e) -> None:
    """Durable sinks for chronicle events: events feed the genealogy table.

    AA: blooms stay in the in-memory chronicle only — high-frequency,
    low-value, so they never cost a DB write. §AE withers and ambient pings
    are filtered out so history contains real historical milestones.
    AD: writes append to the Database RAM buffer (OS-log); the writer daemon
    drains it every 5s — the sim thread never blocks on SQLite.
    """
    if RT.world_id is None or e.type in ("bloom", "wither", "peace_envoy", "culture", "rivalry"):
        return
    wid = RT.world_id
    DB.log_event(wid, e)
    if e.type == "birth":
        DB.log_birth(
            wid,
            entity_id=e.entity_id,
            caste=e.caste or "",
            clan_id=int(e.payload.get("clan_id") or 0),
            generation=int(e.payload.get("generation") or 0),
            mother_id=int(e.payload.get("mother") or 0),
            father_id=int(e.payload.get("father") or 0),
            born_tick=e.tick,
        )
    elif e.type == "death":
        DB.log_death(wid, e.entity_id, e.tick)


def parse_range_minutes(range_str: str | None, default_minutes: int | None = None) -> int | None:
    if not range_str:
        return default_minutes
    s = range_str.strip().lower()
    if s in ("all", "session", "full", "max", "world"):
        return None
    if s.endswith("m") and s[:-1].isdigit():
        return int(s[:-1])
    if s.endswith("h") and s[:-1].isdigit():
        return int(s[:-1]) * 60
    if s.endswith("d") and s[:-1].isdigit():
        return int(s[:-1]) * 1440
    if s.isdigit():
        return int(s)
    return default_minutes


def _get_process_memory_mb() -> float:
    try:
        import resource
        import sys
        rusage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if sys.platform == "darwin":
            return round(rusage / (1024 * 1024), 1)
        else:
            return round(rusage / 1024, 1)
    except Exception:
        return 0.0


def _format_uptime(seconds: float) -> str:
    secs = int(max(0, seconds))
    days, secs = divmod(secs, 86400)
    hours, secs = divmod(secs, 3600)
    mins, secs = divmod(secs, 60)
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0 or days > 0:
        parts.append(f"{hours}h")
    if mins > 0 or hours > 0 or days > 0:
        parts.append(f"{mins}m")
    parts.append(f"{secs}s")
    return " ".join(parts)


# --------------------------------------------------------------------- loop
def _roll_minute(rt: RuntimeState, dur_ms: float, pop: int, interval_ms: float) -> None:
    """Fold one tick sample into the per-minute /healthz rollup.

    Caller must hold rt.lock. Buckets finalize on minute rollover into
    rt._tick_minutes (10,080-min / 7-day cap, oldest first). The in-progress minute is
    exposed separately so the GUI graph always reaches "now".
    """
    try:
        key = int(time.time() // 60)
        cur = rt._tick_min_cur
        if cur[0] != key:
            if cur[1] > 0:
                food_val = round(cur[6] / cur[1], 1) if len(cur) > 6 else 0
                tick_val = cur[7] if len(cur) > 7 else (rt.sim.tick if hasattr(rt, "sim") else 0)
                rt._tick_minutes.append({
                    "t": cur[0] * 60,
                    "n": cur[1],
                    "avg_ms": round(cur[2] / cur[1], 2),
                    "max_ms": round(cur[3], 2),
                    "avg_pop": round(cur[4] / cur[1], 1),
                    "overruns": cur[5],
                    "avg_food": food_val,
                    "tick": tick_val,
                    "tps": round(cur[1] / 60.0, 2),
                })
            cur[0] = key
            cur[1] = 0
            cur[2] = 0.0
            cur[3] = 0.0
            cur[4] = 0
            cur[5] = 0
            if len(cur) > 6:
                cur[6] = 0
                cur[7] = 0
        cur[1] += 1
        cur[2] += dur_ms
        if dur_ms > cur[3]:
            cur[3] = dur_ms
        cur[4] += pop
        if dur_ms > interval_ms * 1.2:
            cur[5] += 1
        if len(cur) > 6:
            food_cnt = len(rt.sim._cached_foods) if (hasattr(rt, "sim") and getattr(rt.sim, "_cached_foods", None) is not None) else 0
            cur[6] += food_cnt
            cur[7] = rt.sim.tick if hasattr(rt, "sim") else 0
    except Exception:
        pass


def _minute_history(rt: RuntimeState, minutes: int | None = None) -> list[dict]:
    """Finalized minute buckets + the in-progress minute (JSON-ready)."""
    try:
        out = list(rt._tick_minutes)
        cur = rt._tick_min_cur
        if cur[1] > 0:
            food_val = round(cur[6] / cur[1], 1) if len(cur) > 6 else 0
            tick_val = cur[7] if len(cur) > 7 else (rt.sim.tick if hasattr(rt, "sim") else 0)
            now_sec = time.time()
            elapsed_in_min = max(1.0, now_sec - (cur[0] * 60))
            out.append({
                "t": cur[0] * 60,
                "n": cur[1],
                "avg_ms": round(cur[2] / cur[1], 2),
                "max_ms": round(cur[3], 2),
                "avg_pop": round(cur[4] / cur[1], 1),
                "overruns": cur[5],
                "avg_food": food_val,
                "tick": tick_val,
                "tps": round(cur[1] / elapsed_in_min, 2),
                "partial": True,
            })
        if minutes is not None and minutes > 0:
            return out[-minutes:]
        return out
    except Exception:
        return []


def advance_world(rt: RuntimeState, hub: Hub | None = None, force_keyframe: bool = False) -> dict | None:
    """Advance the world one tick (caller holds rt.lock).

    Returns the snapshot payload to broadcast (keyframe or delta), or None when throttled/failed.
    A plain function so tests can drive ticks without the engine thread.
    """
    if rt.paused:
        return None
    t0 = time.monotonic()
    is_extinct_tick = False
    try:
        # AD: chronicle/genealogy writes land in the RAM buffer; the writer
        # daemon commits them off-thread — step() never waits on SQLite.
        rt.sim.step()
        # World End / Extinction: if all creatures die (tick > 30), pause ticking automatically
        if rt.sim.tick > 30 and len(rt.sim._cached_creatures) == 0:
            rt.paused = True
            is_extinct_tick = True
    except Exception as exc:
        # The world must never die silently: one failed tick is logged
        # loudly and skipped — the loop keeps turning (a frozen tick
        # used to look like a crash and needed a restart to fix).
        rt.tick_failures += 1
        rt.last_tick_error = f"{type(exc).__name__}: {exc}"
        print(
            f"\n[tick-engine] step() FAILED at tick={rt.sim.tick}: {rt.last_tick_error} — skipping\n",
            flush=True,
        )
        traceback.print_exc()
        sys.stdout.flush()
        return None
    finally:
        # Record timing for /healthz even when step succeeded (or failed)
        dur_ms = (time.monotonic() - t0) * 1000.0
        try:
            rt._tick_durs.append(dur_ms)
            rt._tick_times.append(time.monotonic())
            rt._tick_creature_counts.append(len(rt.sim._cached_creatures) if getattr(rt.sim, "_cached_creatures", None) is not None else len(rt.sim.world.entities))
            if len(rt._tick_durs) > 300:
                rt._tick_durs.pop(0)
                rt._tick_times.pop(0)
                rt._tick_creature_counts.pop(0)
            # Warn when a single tick overruns the target interval — AZ Phase 1 P2: rate-limit to ~5s
            interval_ms = 1000.0 / max(rt.speed, MIN_SPEED)
            if dur_ms > interval_ms * 1.2:
                now = time.monotonic()
                last = getattr(rt, "_last_overrun_log", 0.0)
                if now - last >= 5.0:
                    print(f"[tick-engine] overrun tick={rt.sim.tick} dur={dur_ms:.1f}ms > interval={interval_ms:.1f}ms (speed={rt.speed})", flush=True)
                    rt._last_overrun_log = now  # type: ignore
            _roll_minute(rt, dur_ms, int(rt._tick_creature_counts[-1]) if rt._tick_creature_counts else 0, interval_ms)
        except Exception:
            pass
    # Extinction tick must always be serialized & cached even with no listeners or throttling,
    # otherwise the world freezes on the last alive tick forever (new WS clients never see extinct).
    is_extinct = is_extinct_tick or (rt.sim.tick > 30 and len(rt.sim._cached_creatures) == 0)
    # If a hub is passed and has no active listeners, skip snapshot payload serialization
    if hub is not None and not hub.clients and not is_extinct:
        return None
    # Throttle broadcast to ~20 Hz when tick rate is high — never throttle extinction
    every = max(1, int(round(rt.speed / 20))) if rt.speed > 20 else 1
    if every > 1 and rt.sim.tick % every != 0 and not is_extinct:
        return None

    # Phase 1 AJ: Broadcast full keyframe every 60 ticks (~2-3s) or when forced/uninitialized;
    # otherwise broadcast lightweight delta payload (85-95% bandwidth reduction).
    if is_extinct or force_keyframe or rt.sim.tick % 60 == 0 or not getattr(rt.sim, "_last_broadcast_state", None):
        p = rt.sim.snapshot_payload()
    else:
        p = rt.sim.snapshot_delta_payload()
    if p is not None and isinstance(p, dict):
        p["paused"] = rt.paused
    return p



def advance_world_lockless(rt: RuntimeState, hub: Hub | None = None, force_keyframe: bool = False) -> dict | None:
    """BJ-4: lockless broadcast pipeline — step under lock, serialize outside.

    Takes `rt.lock` ONLY for `rt.sim.step()` + timing bookkeeping, then
    releases it before the 15–25ms `snapshot_payload()` / delta dict build
    and JSON encoding. Snapshot reads outside the lock must be immutable or
    retried: on `RuntimeError` (concurrent mutation during iteration) we
    retake the lock once and rebuild under it. `advance_world()` is kept
    for tests / single-threaded callers.
    """
    if rt.paused:
        return None
    t0 = time.monotonic()
    is_extinct_tick = False
    try:
        with rt.lock:
            rt.sim.step()
            if rt.sim.tick > 30 and len(rt.sim._cached_creatures) == 0:
                rt.paused = True
                is_extinct_tick = True
    except Exception as exc:
        rt.tick_failures += 1
        rt.last_tick_error = f"{type(exc).__name__}: {exc}"
        print(f"\n[tick-engine] step() FAILED at tick={rt.sim.tick}: {rt.last_tick_error} — skipping\n", flush=True)
        traceback.print_exc()
        sys.stdout.flush()
        return None
    finally:
        dur_ms = (time.monotonic() - t0) * 1000.0
        try:
            with rt.lock:
                rt._tick_durs.append(dur_ms)
                rt._tick_times.append(time.monotonic())
                rt._tick_creature_counts.append(len(rt.sim._cached_creatures) if getattr(rt.sim, "_cached_creatures", None) is not None else len(rt.sim.world.entities))
                if len(rt._tick_durs) > 300:
                    rt._tick_durs.pop(0)
                    rt._tick_times.pop(0)
                    rt._tick_creature_counts.pop(0)
                interval_ms = 1000.0 / max(rt.speed, MIN_SPEED)
                if dur_ms > interval_ms * 1.2:
                    now = time.monotonic()
                    last = getattr(rt, "_last_overrun_log", 0.0)
                    if now - last >= 5.0:
                        print(f"[tick-engine] overrun tick={rt.sim.tick} dur={dur_ms:.1f}ms > interval={interval_ms:.1f}ms (speed={rt.speed})", flush=True)
                        rt._last_overrun_log = now  # type: ignore
                _roll_minute(rt, dur_ms, int(rt._tick_creature_counts[-1]) if rt._tick_creature_counts else 0, interval_ms)
        except Exception:
            pass
    is_extinct = is_extinct_tick or (rt.sim.tick > 30 and len(rt.sim._cached_creatures) == 0)
    if hub is not None and not hub.clients and not is_extinct:
        return None
    every = max(1, int(round(rt.speed / 20))) if rt.speed > 20 else 1
    if every > 1 and rt.sim.tick % every != 0 and not is_extinct:
        return None
    use_keyframe = bool(is_extinct or force_keyframe or rt.sim.tick % 60 == 0 or not getattr(rt.sim, "_last_broadcast_state", None))
    # Serialize OUTSIDE the lock; retry once under lock on concurrent mutation.
    p: dict | None = None
    try:
        p = rt.sim.snapshot_payload() if use_keyframe else rt.sim.snapshot_delta_payload()
    except RuntimeError:
        try:
            with rt.lock:
                p = rt.sim.snapshot_payload() if use_keyframe else rt.sim.snapshot_delta_payload()
        except Exception:
            return None
    except Exception:
        return None
    if p is not None and isinstance(p, dict):
        try:
            p["paused"] = rt.paused
        except Exception:
            pass
    return p


class SimEngine:
    """Owns a dedicated OS thread that advances the world.

    Ticks used to run on the asyncio loop: a slow HTTP client or a big JSON
    broadcast stalled the simulation and vice versa. Now the sim paces itself
    on its own thread, DB writes ride along off-loop, and snapshots serialize
    here — the event loop only ships finished payloads. Shared state crosses
    threads strictly under `rt.lock`.
    """

    def __init__(self, rt: RuntimeState, hub: "Hub") -> None:
        self.rt = rt
        self.hub = hub
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        self._loop = loop or asyncio.get_running_loop()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="tick-engine", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None

    def _run(self) -> None:
        assert self._loop is not None
        stop = self._stop
        while not stop.is_set():
            interval = 1.0 / max(self.rt.speed, MIN_SPEED)
            started = time.monotonic()
            payload = None
            text: str | None = None
            # BJ-4: step under lock, serialize outside — HTTP stays responsive.
            if not self.rt.paused:
                payload = advance_world_lockless(self.rt, self.hub)
                # BD.1.4 WebSocket Analytics Stream Coalescing — 1 Hz analytics frame piggybacks
                if self.hub.clients and payload is not None and isinstance(payload, dict) and payload.get("type") in ("state", "delta_state"):
                    cadence = max(1, int(round(self.rt.speed)))
                    if getattr(self.rt.sim, "tick", 0) % cadence == 0:
                        try:
                            payload["analytics"] = _analytics_payload(self.rt.sim)
                        except Exception:
                            pass
            if payload is not None:
                try:
                    text = _dumps(payload)
                    self.rt._cached_state_text = text  # type: ignore[attr-defined]
                except Exception:
                    text = None
                    self.rt._cached_state_text = None  # type: ignore[attr-defined]
                # AZ Phase 1 P1: take lock for clan cache build; reset to None on exception
                if getattr(self.rt, "sim", None) and (self.rt.sim.tick % 10 == 0 or getattr(self.rt, "_cached_clans_payload", None) is None):
                    try:
                        with self.rt.lock:
                            self.rt._cached_clans_payload = _clans_payload(self.rt.sim)  # type: ignore[attr-defined]
                    except Exception:
                        self.rt._cached_clans_payload = None  # type: ignore[attr-defined]
            # AZ Phase 1 P0: still refresh caches even when no WS clients, so HTTP doesn't freeze
            elif getattr(self.rt, "sim", None) and getattr(self.rt, "_cached_clans_payload", None) is None:
                try:
                    with self.rt.lock:
                        self.rt._cached_clans_payload = _clans_payload(self.rt.sim)  # type: ignore[attr-defined]
                except Exception:
                    self.rt._cached_clans_payload = None  # type: ignore[attr-defined]
            if text is not None:
                self.hub.enqueue_text(text, self._loop)
            elif payload is not None:
                # Fallback if dumps failed — broadcast dict the old way
                try:
                    text2 = _dumps(payload)
                    self.hub.enqueue_text(text2, self._loop)
                except Exception:
                    pass
            elapsed = time.monotonic() - started
            stop.wait(max(0.0, interval - elapsed))


def _try_restore_snapshot() -> bool:
    """Restore same world across backend code deploys (no Reset).

    `deploy.sh` saves `GET /api/state` to `~/app/fl/snapshot.json` before
    killing the old backend. On next start we rehydrate `RT.sim` from that
    payload so tick+entities survive the restart — same world, same tick.
    """
    path = os.environ.get("FLATWORLD_RESTORE_SNAPSHOT", str(Path.home() / "app" / "fl" / "snapshot.json"))
    p = Path(path)
    if not p.exists():
        return False
    try:
        raw = p.read_text()
        data = json.loads(raw)
        if data.get("type") != "state" or "entities" not in data:
            return False
        # Rebuild simulation in-place
        from .entities import Corpse, Creature, Food, House
        # Clear existing
        RT.sim.world.entities.clear()
        RT.sim.world._next_id = 1
        # Also clear cached buckets will be rebuilt on next step
        max_id = 0
        for ent in data["entities"]:
            kind = ent.get("kind")
            eid = int(ent.get("id", 0))
            max_id = max(max_id, eid)
            if kind == "creature":
                c = Creature(
                    shape=ent.get("shape") or "polygon",
                    sides=int(ent.get("sides") or 4),
                    x=float(ent.get("x") or 0),
                    y=float(ent.get("y") or 0),
                    angle=float(ent.get("angle") or 0),
                    speed=0.6,
                    energy=float(ent.get("energy") or 80),
                    caste=ent.get("caste") or "",
                    radius=float(ent.get("radius") or 0),
                    age=int(ent.get("age") or 0),
                    lifespan=float(ent.get("lifespan") or 0),
                    generation=int(ent.get("generation") or 0),
                    clan_id=int(ent.get("clan_id") or 0),
                )
                # preserve extra fields if present
                for k in ("mother_id", "father_id", "health", "infected", "sleeping", "indoors", "status", "chill"):
                    if k in ent and ent[k] is not None:
                        setattr(c, k, ent[k])
                c.id = eid
                RT.sim.world.entities[eid] = c
            elif kind == "food":
                f = Food(x=float(ent.get("x") or 0), y=float(ent.get("y") or 0), growth=float(ent.get("growth") or 0.15), variant=ent.get("variant") or "grass")
                # preserve mature_ticks if present
                if "mature_ticks" in ent:
                    f.mature_ticks = int(ent["mature_ticks"])
                f.id = eid
                RT.sim.world.entities[eid] = f
            elif kind == "house":
                h = House(x=float(ent.get("x") or 0), y=float(ent.get("y") or 0), size=float(ent.get("size") or 6), door_width=float(ent.get("door_width") or 4), door_side=ent.get("door_side") or "south")
                for k in ("clan_id", "clan_color", "is_main", "is_ruin", "abandoned_ticks"):
                    if k in ent and ent[k] is not None:
                        setattr(h, k, ent[k])
                h.id = eid
                RT.sim.world.entities[eid] = h
            elif kind == "corpse":
                co = Corpse(x=float(ent.get("x") or 0), y=float(ent.get("y") or 0), ttl=int(ent.get("ttl") or 600), energy=float(ent.get("energy") or 25))
                co.id = eid
                RT.sim.world.entities[eid] = co
        RT.sim.world._next_id = max_id + 1
        # Restore tick and meta
        RT.sim.tick = int(data.get("tick") or 0)
        # Restore death counters — prefer DB total (survives snapshot resets)
        try:
            db_total = int(DB.death_count(RT.world_id)) if RT.world_id else 0
        except: db_total = 0
        snap_dead = int(data.get("creatures_dead") or 0) if "creatures_dead" in data else 0
        # use max to repair old snapshots that had only post-restart deaths (e.g. 1k vs 42k)
        if db_total or snap_dead:
            try: RT.sim.deaths = max(db_total, snap_dead)
            except: pass
        if "dead_by_cause" in data and isinstance(data["dead_by_cause"], dict):
            try:
                snap_counts = {str(k): int(v) for k, v in data["dead_by_cause"].items()}
                # if DB has more, rebuild from DB for accurate breakdown when snapshot is stale
                if db_total > sum(snap_counts.values()) + 1000:
                    # accurate GROUP BY cause for all deaths (not just recent 50k)
                    try:
                        db = DB._require()
                        rows = db.execute("SELECT cause, COUNT(*) as cnt FROM events WHERE world_id=? AND type=\"death\" GROUP BY cause", (RT.world_id,)).fetchall()
                        counts = { (r["cause"] or "unknown"): int(r["cnt"]) for r in rows }
                        if counts: RT.sim._death_counts = counts
                        else: RT.sim._death_counts = snap_counts
                    except:
                        RT.sim._death_counts = snap_counts
                else:
                    RT.sim._death_counts = snap_counts
            except: pass
        elif RT.world_id:
            try:
                db = DB._require()
                rows = db.execute("SELECT cause, COUNT(*) as cnt FROM events WHERE world_id=? AND type=\"death\" GROUP BY cause", (RT.world_id,)).fetchall()
                counts = { (r["cause"] or "unknown"): int(r["cnt"]) for r in rows }
                if counts: RT.sim._death_counts = counts
            except: pass
        if "clans" in data and isinstance(data["clans"], dict):
            # server keys are strings
            restored_clans: dict[int, dict] = {}
            for k, v in data["clans"].items():
                try:
                    cid = int(k)
                    cinfo = dict(v)
                    restored_clans[cid] = cinfo
                    w_wins = int(cinfo.get("war_wins") or 0)
                    w_losses = int(cinfo.get("war_losses") or 0)
                    if w_wins:
                        RT.sim._clan_war_wins[cid] = w_wins
                    if w_losses:
                        RT.sim._clan_war_losses[cid] = w_losses
                except Exception:
                    continue
            RT.sim.clans = restored_clans
            # repair _next_clan_id
            if restored_clans:
                RT.sim._next_clan_id = max(restored_clans.keys()) + 1
        if "relations" in data and isinstance(data["relations"], list):
            RT.sim.relations = {(int(r["a"]), int(r["b"])): int(r["score"]) for r in data["relations"] if "a" in r and "b" in r}
        if "signals" in data:
            RT.sim.signals = list(data["signals"])
        if "fires" in data:
            RT.sim.fires = list(data["fires"])
        # Rebuild index for next step
        RT.sim.world.rebuild_index()
        RT.sim._refresh_cache()
        # Restore safeguard miracle count from DB so max_miracles limit persists across restarts
        if getattr(RT.sim, "_safeguard", None) is not None and RT.world_id:
            try:
                db = DB._require()
                row = db.execute("SELECT COUNT(*) as cnt FROM events WHERE world_id=? AND type='miracle'", (RT.world_id,)).fetchone()
                if row and row["cnt"] is not None:
                    RT.sim._safeguard.miracles = int(row["cnt"])
            except Exception:
                pass
        print(f"[restore] loaded snapshot tick={RT.sim.tick} entities={len(RT.sim.world.entities)} clans={len(RT.sim.clans)} miracles={getattr(getattr(RT.sim, '_safeguard', None), 'miracles', 0)} from {p}", flush=True)
        # Hotfix live world for N150: reduce query radii and heavy subsystems when pop >800
        c_count = len([e for e in RT.sim.world.entities.values() if e.kind == "creature"])
        if c_count > 800:
            # Apply cheaper laws in-place without POST (preserves tick) — keep most restrictive
            new_cfg = replace(
                RT.config,
                perceive_radius=min(RT.config.perceive_radius, 12.0),
                signal_radius=min(RT.config.signal_radius, 6.0),
                knowledge_enabled=False,
                schism_enabled=False,
                help_call_enabled=False,
                war_enabled=False,
                predation_enabled=False,
                territory_enabled=False,
                carrying_capacity=min(RT.config.carrying_capacity if RT.config.carrying_capacity>0 else 1200, 1200),
                max_population=min(RT.config.max_population if RT.config.max_population>0 else 1300, 1300),
                plant_growth_rate=min(RT.config.plant_growth_rate, 0.03),
                birth_rate=min(RT.config.birth_rate, 0.20),
                food_count=min(RT.config.food_count, 350),
                cannibalism_enabled=False,
                exile_on_kin_eat=False,
            )
            RT.config = new_cfg
            RT.sim.config = new_cfg
            RT.sim.world.config = new_cfg
            print(f"[restore] hotfix {c_count}c: perceive {new_cfg.perceive_radius} signal {new_cfg.signal_radius} cap {new_cfg.carrying_capacity}/{new_cfg.max_population} for 10t/s", flush=True)
        # Move aside so next start is fresh unless explicitly re-saved
        try:
            p.rename(p.with_suffix(".loaded"))
        except Exception:
            pass
        return True
    except Exception as exc:
        print(f"[restore] failed {exc}", flush=True)
        traceback.print_exc()
        return False


@asynccontextmanager
async def lifespan(_: FastAPI):
    DB.connect()
    # Restore persisted preset + laws BEFORE snapshot rehydration, so the
    # continued world (or a fresh founding) runs the remembered rules —
    # otherwise every deploy silently reverts to env defaults relabelled
    # "sustainable".
    try:
        if _restore_law_state(RT):
            print(f"[restore] laws preset={RT.current_preset}", flush=True)
    except Exception as exc:
        print(f"[restore] laws failed {exc}", flush=True)
    # Try to keep same world across deploys
    restored = _try_restore_snapshot()
    if not restored:
        start_world()
    else:
        # reuse existing world_id row, attach event sink
        if RT.world_id is None:
            # find latest world row
            try:
                rows = DB.worlds()
                if rows:
                    RT.world_id = rows[0]["id"]
            except Exception:
                pass
        if RT.world_id is None:
            start_world()
        else:
            RT.sim.on_event = _on_event
            # fixup deaths: snapshot tail (1k) vs DB total (42k) — use DB total
            try:
                db_total = int(DB.death_count(RT.world_id)) if RT.world_id else 0
                if db_total > getattr(RT.sim, "deaths", 0):
                    RT.sim.deaths = db_total
                    db = DB._require()
                    rows = db.execute("SELECT cause, COUNT(*) as cnt FROM events WHERE world_id=? AND type=\"death\" GROUP BY cause", (RT.world_id,)).fetchall()
                    counts = { (r["cause"] or "unknown"): int(r["cnt"]) for r in rows }
                    if counts: RT.sim._death_counts = counts
            except: pass
            # rehydrate clan war wins / losses if missing from snapshot
            try:
                if sum(getattr(RT.sim, "_clan_war_wins", {}).values()) == 0 and RT.world_id:
                    db = DB._require()
                    rows = db.execute(
                        "SELECT json_extract(payload, '$.b') as w, json_extract(payload, '$.a') as l, COUNT(*) as cnt "
                        "FROM events WHERE world_id=? AND type='war' GROUP BY w, l",
                        (RT.world_id,),
                    ).fetchall()
                    for r in rows:
                        w_id = r["w"]
                        l_id = r["l"]
                        cnt = int(r["cnt"] or 0)
                        if w_id is not None:
                            try:
                                w_cid = int(w_id)
                                RT.sim._clan_war_wins[w_cid] = RT.sim._clan_war_wins.get(w_cid, 0) + cnt
                                if w_cid in RT.sim.clans:
                                    RT.sim.clans[w_cid]["war_wins"] = RT.sim._clan_war_wins[w_cid]
                            except (ValueError, TypeError):
                                pass
                        if l_id is not None:
                            try:
                                l_cid = int(l_id)
                                RT.sim._clan_war_losses[l_cid] = RT.sim._clan_war_losses.get(l_cid, 0) + cnt
                                if l_cid in RT.sim.clans:
                                    RT.sim.clans[l_cid]["war_losses"] = RT.sim._clan_war_losses[l_cid]
                            except (ValueError, TypeError):
                                pass
                    if RT.sim._clan_war_wins:
                        print(f"[restore] rehydrated war stats for {len(RT.sim._clan_war_wins)} clans from DB", flush=True)
            except Exception as ex:
                print(f"[restore] warning: failed to rehydrate clan war stats from DB: {ex}", flush=True)
            print(f"[restore] continuing world_id={RT.world_id} tick={RT.sim.tick}", flush=True)
    engine = SimEngine(RT, HUB)
    # AZ Phase 1: start bounded broadcast queue consumer
    try:
        loop = asyncio.get_running_loop()
        HUB.start_queue(loop)
    except Exception:
        pass
    engine.start()
    yield
    engine.stop()
    HUB.stop_queue()
    if RT.world_id is not None:
        DB.end_world(RT.world_id)
    DB.close()


app = FastAPI(
    title="Flatland World Simulation",
    version="0.1.6",
    description="Flatland — 2D world simulation by Long Phan <long@minhnhan.in>",
    contact={"name": "Long Phan", "email": "long@minhnhan.in"},
    lifespan=lifespan,
)
AUTH = PasskeyAuth(DB)
app.state.god_auth = AUTH
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://world.minhnhan.in",
        "https://world.minhnhan.in",
    ],
    allow_origin_regex="https?://.*",
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------ control
async def apply_control(msg: ControlMessage) -> dict:
    payload = None  # snapshots broadcast after the lock is released
    with RT.lock:
        if msg.action is ControlAction.PAUSE:
            RT.paused = True
        elif msg.action is ControlAction.RESUME:
            RT.paused = False
        elif msg.action is ControlAction.STEP:
            RT.sim.step()
            payload = RT.sim.snapshot_payload()
            payload["paused"] = RT.paused
        elif msg.action is ControlAction.RESET:
            # A new world is born with fresh laws of chance: a new random seed.
            # Save persists across worlds, Apply does not — use saved baseline.
            # The chronicle endures in the database.
            base = getattr(RT, "saved_config", RT.config)
            new_cfg = replace(base, seed=random.SystemRandom().randint(0, 2**31 - 1))
            RT.config = new_cfg
            RT.sim = Simulation(new_cfg)
            RT._cached_clans_payload = None
            RT._cached_state_text = None
            RT.paused = False
            start_world()
            # A reset world runs the saved baseline — relabel + persist it so
            # the next deploy restart keeps it too.
            RT.current_preset = detect_current_preset()
            _persist_law_state()
            payload = RT.sim.snapshot_payload()
            payload["paused"] = False
        elif msg.action is ControlAction.SET_SPEED:
            if msg.value is not None:
                RT.speed = min(MAX_SPEED, max(MIN_SPEED, float(msg.value)))
    if payload is not None:
        await HUB.broadcast(payload)
    return {
        "ok": True,
        "paused": RT.paused,
        "speed": RT.speed,
        "tick": RT.sim.tick,
    }


def hello_payload() -> dict:
    return HelloMessage(
        seed=CONFIG.seed,
        tick_rate=RT.speed,
        width=RT.config.width,
        height=RT.config.height,
        boundary=RT.config.boundary,
        paused=RT.paused,
    ).model_dump(mode="json")


# --------------------------------------------------------------------- laws
LAW_FIELDS = tuple(GodLaws.model_fields.keys())



# --- T: presets ----------------------------------------------------------------
# Recalculated for the 400x300 default map (pop ~156, schism/comm/war enabled, war rare).
# Area-tuned numbers scale x3 from the 200x200 baseline: food bounty and population
# Recalculated for high-scale population on modern / low-end CPUs (e.g., Intel N150).
# Area-tuned numbers support 2000-4000+ active inhabitants with 60 FPS batched rendering.
PRESETS: dict[str, dict] = {
    "balance": dict(
        # The Goldilocks condition: gentle harmony for steady 200-350 population multi-generational flourishing.

        boundary="wrap",
        door_clearance=1.5,
        food_count=380,
        plant_growth_rate=0.065,
        plant_spread_rate=0.008,
        nutrient_cycle_rate=0.65,
        plant_variants_enabled=True,
        poison_rate=0.008,
        beast_ratio=0.0,
        diet_strictness=0.0,
        territory_enabled=True,
        territory_radius=14.0,
        trespass_decay=0.45,
        totems_enabled=True,
        succession_enabled=True,
        max_clans=-1,
        schism_enabled=True,
        schism_threshold=0.55,
        schism_min_pop=6,
        communication_enabled=True,
        signal_radius=12.0,
        food_call_rate=0.08,
        alarm_call_rate=0.12,
        knowledge_enabled=True,
        knowledge_ttl=600,
        knowledge_share_rate=0.05,
        help_call_enabled=True,
        help_radius=12.0,
        defense_weight=0.5,
        age_enabled=True,
        age_length=12000,
        culture_enabled=True,
        culture_spread_rate=0.005,
        trait_mutation_rate=0.02,
        wildfire_enabled=True,
        fire_rate=0.00008,
        fire_spread_rate=0.035,
        disaster_enabled=True,
        disaster_rate=0.00004,
        energy_max=100.0,
        energy_decay_per_tick=0.018,
        energy_from_food=32.0,
        hungry_ratio=0.35,
        starving_ratio=0.15,
        perceive_radius=16.0,
        eat_radius=1.4,
        wander_turn=0.35,
        steer_turn=0.45,
        hungry_perceive_mult=1.3,
        desperate_perceive_mult=1.6,
        desperate_speed_mult=1.35,
        food_giveup_ticks=240,
        lifespan_mult=1.0,
        birth_enabled=True,
        adult_age=240.0,  # §BF-2 240 ticks (0.2 days) — founders mature on morning of Day 1
        mate_radius=10.0,
        mate_energy_min=24.0,
        birth_rate=0.080,
        boom_ramp_days=1.2,  # §BF-1 gentle 1.2-day ramp
        boom_birth_floor=0.40,
        boom_cooldown_mult=1.0,  # §BF-3
        boom_energy_mult=1.0,  # §BF-4
        initial_season_offset=0,  # §BF-5 spring start
        sex_ratio=0.5,
        mutation_rate=0.05,
        max_sides=24,
        birth_energy_cost=16.0,
        reproduction_cooldown=240,
        carrying_capacity=400,
        max_population=500,
        euthanasia_threshold=0.7,
        disease_enabled=True,
        disease_outbreak_rate=0.00006,
        disease_rate=0.035,
        disease_radius=3.0,
        disease_energy_drain=0.05,
        recovery_rate=0.060,
        disease_lethality=0.07,
        day_length=1200,
        season_length=12000,
        winter_food_mult=0.82,
        night_sight_mult=0.6,
        weather_enabled=True,
        weather_change_rate=0.002,
        fog_sight_mult=0.6,
        rain_speed_mult=0.85,
        storm_wander_bonus=0.35,
        rain_growth_mult=1.25,
        fog_mushroom_mult=1.35,
        storm_plant_damage=0.02,
        weather_sickness_enabled=False,
        chill_rate=0.04,
        chill_threshold=12.0,
        chill_drain=0.09,
        wet_disease_mult=1.5,
        cohesion_weight=0.0,
        alignment_weight=0.0,
        separation_weight=0.0,
        flock_radius=6.0,
        relation_drift_rate=1.8,
        alliance_threshold=55,
        rivalry_threshold=-45,
        shelter_enabled=True,
        exposure_drain=0.020,
        house_capacity=14,
        house_min_size=5.5,
        house_max_size=8.0,
        house_claim_enabled=True,
        rest_recovery_mult=2.5,
        house_decay_ticks=3000,
        hearths_enabled=True,
        rivers_enabled=True,
        river_count=2,
        relief_enabled=True,
        structural_enabled=True,
        rubble_blocking_enabled=True,
        earthquake_enabled=False,
        earthquake_rate=0.00008,
        signal_speed=8.0,
        lightning_enabled=True,
        lightning_strike_rate=0.0015,
        anomaly_count=3,
        predation_enabled=True,
        predator_ratio=0.008,
        hunt_radius=7.0,
        bite_damage=16.0,
        bite_cooldown=15,
        energy_from_prey=40.0,
        fear_radius=12.0,
        war_enabled=True,
        attack_radius=1.8,
        attack_damage=30.0,
        coalitions_enabled=True,
        coalition_threshold=40,
        coalition_min_size=2,
        leader_decisions_enabled=True,
        resource_sharing_enabled=True,
        larder_capacity=300.0,
        aid_rate=0.05,
        tribute_enabled=True,
        betrayal_enabled=True,
        defection_enabled=True,
        cannibalism_enabled=True,
        cannibalism_hunger_ratio=0.08,
        cannibalism_energy=35.0,
        eat_enemy_enabled=True,
        eat_kin_enabled=False,
        kin_stigma=35,
        exile_on_kin_eat=True,
        food_decay_enabled=True,
        food_lifespan_ticks=8000,
        theology_enabled=True,
        tithe_rate=0.04,
        temple_faith_cost=250.0,
        agriculture_enabled=True,
        granaries_enabled=True,
        granary_capacity=400.0,
        soil_depletion_enabled=True,
        banquets_enabled=True,
        vocalizations_enabled=True,
        scent_enabled=True,
        envoys_enabled=True,
        markets_enabled=True,
        omens_enabled=True,
        dialect_drift_enabled=True,
        nn_inference_hz=15,
        mutation_sigma=0.08,
        crossover_rate=0.5,
        morphology_annealing_enabled=True,
        annealing_start_generation=50,
        annealing_decay_generations=150,
        morph_lambda_override=None,
        vertex_mutation_std=0.05,
        angle_mutation_std=0.02,
        topological_mutation_rate=0.01,
        soft_cap_enabled=True,
        damping_steepness=12.0,
        crowding_stress_mult=1.0,
        resource_strain_mult=2.0,
        safeguard_enabled=True,
        safeguard_critical_pop=12,
        safeguard_relief_ratio=0.30,
        safeguard_genesis_batch=6,
        safeguard_morph_mercy=True,
        safeguard_max_miracles=1,
    ),
    "sustainable": dict(
        # 1000-Day Peace & Flourishing: 360 food, carrying 450, max 600, calm society, rich agriculture, granaries, banquets, temples & sacred avatars.

        boundary="wrap",
        door_clearance=1.5,
        food_count=550,
        plant_growth_rate=0.08,
        plant_spread_rate=0.010,
        nutrient_cycle_rate=0.85,
        plant_variants_enabled=True,
        poison_rate=0.0,
        beast_ratio=0.0,
        diet_strictness=0.0,
        territory_enabled=True,
        territory_radius=16.0,
        trespass_decay=0.15,
        totems_enabled=True,
        succession_enabled=True,
        max_clans=-1,
        schism_enabled=True,
        schism_threshold=0.70,
        schism_min_pop=6,
        communication_enabled=True,
        signal_radius=16.0,
        food_call_rate=0.12,
        alarm_call_rate=0.08,
        knowledge_enabled=True,
        knowledge_ttl=1000,
        knowledge_share_rate=0.08,
        help_call_enabled=True,
        help_radius=14.0,
        defense_weight=0.6,
        age_enabled=True,
        age_length=15000,
        culture_enabled=True,
        culture_spread_rate=0.008,
        trait_mutation_rate=0.02,
        wildfire_enabled=False,
        fire_rate=0.00001,
        fire_spread_rate=0.02,
        disaster_enabled=False,
        disaster_rate=0.00001,
        energy_max=100.0,
        energy_decay_per_tick=0.016,
        energy_from_food=36.0,
        hungry_ratio=0.32,
        starving_ratio=0.12,
        perceive_radius=18.0,
        eat_radius=1.4,
        wander_turn=0.35,
        steer_turn=0.45,
        hungry_perceive_mult=1.3,
        desperate_perceive_mult=1.6,
        desperate_speed_mult=1.30,
        food_giveup_ticks=240,
        lifespan_mult=1.2,
        birth_enabled=True,
        adult_age=220.0,  # §BF-2 220 ticks (0.18 days)
        mate_radius=10.0,
        mate_energy_min=20.0,
        birth_rate=0.085,
        boom_ramp_days=1.0,
        boom_birth_floor=0.45,
        boom_cooldown_mult=1.0,
        boom_energy_mult=1.0,
        initial_season_offset=0,
        sex_ratio=0.5,
        mutation_rate=0.05,
        max_sides=24,
        birth_energy_cost=14.0,
        reproduction_cooldown=220,
        carrying_capacity=380,
        max_population=450,
        euthanasia_threshold=0.75,
        disease_enabled=True,
        disease_outbreak_rate=0.00003,
        disease_rate=0.02,
        disease_radius=3.0,
        disease_energy_drain=0.03,
        recovery_rate=0.080,
        disease_lethality=0.04,
        day_length=1200,
        season_length=12000,
        winter_food_mult=0.88,
        night_sight_mult=0.7,
        weather_enabled=True,
        weather_change_rate=0.002,
        fog_sight_mult=0.7,
        rain_speed_mult=0.9,
        storm_wander_bonus=0.25,
        rain_growth_mult=1.35,
        fog_mushroom_mult=1.5,
        storm_plant_damage=0.01,
        weather_sickness_enabled=False,
        chill_rate=0.03,
        chill_threshold=14.0,
        chill_drain=0.06,
        wet_disease_mult=1.2,
        cohesion_weight=0.0,
        alignment_weight=0.0,
        separation_weight=0.0,
        flock_radius=6.0,
        relation_drift_rate=3.0,
        alliance_threshold=40,
        rivalry_threshold=-70,
        shelter_enabled=True,
        exposure_drain=0.015,
        house_capacity=18,
        house_min_size=5.5,
        house_max_size=8.0,
        house_claim_enabled=True,
        rest_recovery_mult=3.0,
        house_decay_ticks=4000,
        hearths_enabled=True,
        rivers_enabled=True,
        river_count=2,
        relief_enabled=True,
        structural_enabled=True,
        rubble_blocking_enabled=True,
        earthquake_enabled=False,
        earthquake_rate=0.00005,
        signal_speed=8.0,
        lightning_enabled=True,
        lightning_strike_rate=0.001,
        anomaly_count=4,
        predation_enabled=True,
        predator_ratio=0.004,
        hunt_radius=8.0,
        bite_damage=12.0,
        bite_cooldown=15,
        energy_from_prey=40.0,
        fear_radius=12.0,
        war_enabled=True,
        attack_radius=1.8,
        attack_damage=25.0,
        coalitions_enabled=True,
        coalition_threshold=40,
        coalition_min_size=2,
        leader_decisions_enabled=True,
        resource_sharing_enabled=True,
        larder_capacity=400.0,
        aid_rate=0.10,
        tribute_enabled=True,
        betrayal_enabled=False,
        defection_enabled=True,
        cannibalism_enabled=False,
        cannibalism_hunger_ratio=0.06,
        cannibalism_energy=30.0,
        eat_enemy_enabled=False,
        eat_kin_enabled=False,
        kin_stigma=50,
        exile_on_kin_eat=True,
        food_decay_enabled=True,
        food_lifespan_ticks=9000,
        theology_enabled=True,
        tithe_rate=0.05,
        temple_faith_cost=200.0,
        agriculture_enabled=True,
        granaries_enabled=True,
        granary_capacity=500.0,
        soil_depletion_enabled=True,
        banquets_enabled=True,
        vocalizations_enabled=True,
        scent_enabled=True,
        envoys_enabled=True,
        markets_enabled=True,
        omens_enabled=True,
        dialect_drift_enabled=True,
        nn_inference_hz=12,
        mutation_sigma=0.05,
        crossover_rate=0.4,
        morphology_annealing_enabled=True,
        annealing_start_generation=50,
        annealing_decay_generations=150,
        morph_lambda_override=None,
        vertex_mutation_std=0.05,
        angle_mutation_std=0.02,
        topological_mutation_rate=0.01,
        soft_cap_enabled=True,
        damping_steepness=12.0,
        crowding_stress_mult=1.0,
        resource_strain_mult=1.5,
        safeguard_enabled=True,
        safeguard_critical_pop=14,
        safeguard_relief_ratio=0.35,
        safeguard_genesis_batch=8,
        safeguard_morph_mercy=True,
        safeguard_max_miracles=1,
    ),
    "chaos": dict(
        # Total Turmoil: famine, predators, deadly wars, frequent plagues, wildfires, earthquakes, lightning strikes, landslides, collapses, betrayal, cannibalism, rapid seasons.

        boundary="wrap",
        door_clearance=1.5,
        food_count=320,
        plant_growth_rate=0.045,
        plant_spread_rate=0.006,
        nutrient_cycle_rate=0.65,
        plant_variants_enabled=True,
        poison_rate=0.03,
        beast_ratio=0.0,
        diet_strictness=0.0,
        territory_enabled=True,
        territory_radius=16.0,
        trespass_decay=2.0,
        totems_enabled=True,
        succession_enabled=True,
        max_clans=-1,
        schism_enabled=True,
        schism_threshold=0.35,
        schism_min_pop=4,
        communication_enabled=True,
        signal_radius=12.0,
        food_call_rate=0.06,
        alarm_call_rate=0.16,
        knowledge_enabled=True,
        knowledge_ttl=500,
        knowledge_share_rate=0.04,
        help_call_enabled=True,
        help_radius=12.0,
        defense_weight=0.4,
        age_enabled=True,
        age_length=4000,
        culture_enabled=True,
        culture_spread_rate=0.005,
        trait_mutation_rate=0.04,
        wildfire_enabled=True,
        fire_rate=0.0012,
        fire_spread_rate=0.10,
        disaster_enabled=True,
        disaster_rate=0.0004,
        energy_max=100.0,
        energy_decay_per_tick=0.025,
        energy_from_food=28.0,
        hungry_ratio=0.40,
        starving_ratio=0.18,
        perceive_radius=20.0,
        eat_radius=1.4,
        wander_turn=0.45,
        steer_turn=0.55,
        hungry_perceive_mult=1.4,
        desperate_perceive_mult=1.8,
        desperate_speed_mult=1.45,
        food_giveup_ticks=180,
        lifespan_mult=0.9,
        birth_enabled=True,
        adult_age=180.0,
        mate_radius=10.0,
        mate_energy_min=20.0,
        birth_rate=0.095,
        boom_ramp_days=0.8,
        boom_birth_floor=0.60,
        boom_cooldown_mult=1.0,
        boom_energy_mult=1.0,
        initial_season_offset=0,
        sex_ratio=0.5,
        mutation_rate=0.08,
        max_sides=24,
        birth_energy_cost=18.0,
        reproduction_cooldown=200,
        carrying_capacity=350,
        max_population=420,
        euthanasia_threshold=0.65,
        disease_enabled=True,
        disease_outbreak_rate=0.0015,
        disease_rate=0.06,
        disease_radius=3.5,
        disease_energy_drain=0.12,
        recovery_rate=0.015,
        disease_lethality=0.45,
        day_length=800,
        season_length=2400,
        winter_food_mult=0.55,
        night_sight_mult=0.5,
        weather_enabled=True,
        weather_change_rate=0.005,
        fog_sight_mult=0.5,
        rain_speed_mult=0.80,
        storm_wander_bonus=0.50,
        rain_growth_mult=1.20,
        fog_mushroom_mult=1.30,
        storm_plant_damage=0.05,
        weather_sickness_enabled=True,
        chill_rate=0.06,
        chill_threshold=10.0,
        chill_drain=0.25,
        wet_disease_mult=2.0,
        cohesion_weight=0.0,
        alignment_weight=0.0,
        separation_weight=0.0,
        flock_radius=6.0,
        relation_drift_rate=0.25,
        alliance_threshold=80,
        rivalry_threshold=-20,
        shelter_enabled=True,
        exposure_drain=0.06,
        house_capacity=12,
        house_min_size=5.5,
        house_max_size=8.0,
        house_claim_enabled=True,
        rest_recovery_mult=1.5,
        house_decay_ticks=1200,
        hearths_enabled=True,
        rivers_enabled=True,
        river_count=3,
        relief_enabled=True,
        structural_enabled=True,
        rubble_blocking_enabled=True,
        earthquake_enabled=True,
        earthquake_rate=0.0003,
        signal_speed=12.0,
        lightning_enabled=True,
        lightning_strike_rate=0.005,
        anomaly_count=6,
        predation_enabled=True,
        predator_ratio=0.05,
        hunt_radius=10.0,
        bite_damage=40.0,
        bite_cooldown=8,
        energy_from_prey=45.0,
        fear_radius=14.0,
        war_enabled=True,
        attack_radius=2.2,
        attack_damage=60.0,
        coalitions_enabled=True,
        coalition_threshold=50,
        coalition_min_size=2,
        leader_decisions_enabled=True,
        resource_sharing_enabled=True,
        larder_capacity=200.0,
        aid_rate=0.03,
        tribute_enabled=True,
        betrayal_enabled=True,
        defection_enabled=True,
        cannibalism_enabled=True,
        cannibalism_hunger_ratio=0.25,
        cannibalism_energy=50.0,
        eat_enemy_enabled=True,
        eat_kin_enabled=True,
        kin_stigma=20,
        exile_on_kin_eat=True,
        food_decay_enabled=True,
        food_lifespan_ticks=5000,
        theology_enabled=True,
        tithe_rate=0.05,
        temple_faith_cost=300.0,
        agriculture_enabled=True,
        granaries_enabled=True,
        granary_capacity=250.0,
        soil_depletion_enabled=True,
        banquets_enabled=True,
        vocalizations_enabled=True,
        scent_enabled=True,
        envoys_enabled=True,
        markets_enabled=True,
        omens_enabled=True,
        dialect_drift_enabled=True,
        nn_inference_hz=20,
        mutation_sigma=0.12,
        crossover_rate=0.7,
        morphology_annealing_enabled=True,
        annealing_start_generation=0,
        annealing_decay_generations=10,
        morph_lambda_override=None,
        vertex_mutation_std=0.05,
        angle_mutation_std=0.02,
        topological_mutation_rate=0.05,
        soft_cap_enabled=True,
        damping_steepness=10.0,
        crowding_stress_mult=0.50,
        resource_strain_mult=1.5,
        safeguard_enabled=True,
        safeguard_critical_pop=6,
        safeguard_relief_ratio=0.20,
        safeguard_genesis_batch=4,
        safeguard_morph_mercy=False,
        safeguard_max_miracles=1,
    ),
    "extinction": dict(
        # Cataclysmic Collapse & Grim Survival: Extreme famine (120 food), harsh winter (0.3x), rampant disease, severe weather chill, extreme exposure drain, collapsing shelters, deadly predators & wars, desperate cannibalism.

        boundary="wrap",
        door_clearance=1.5,
        food_count=120,
        plant_growth_rate=0.025,
        plant_spread_rate=0.003,
        nutrient_cycle_rate=0.50,
        plant_variants_enabled=True,
        poison_rate=0.05,
        beast_ratio=0.0,
        diet_strictness=0.0,
        territory_enabled=True,
        territory_radius=14.0,
        trespass_decay=2.0,
        totems_enabled=True,
        succession_enabled=True,
        max_clans=-1,
        schism_enabled=True,
        schism_threshold=0.30,
        schism_min_pop=3,
        communication_enabled=True,
        signal_radius=10.0,
        food_call_rate=0.04,
        alarm_call_rate=0.18,
        knowledge_enabled=True,
        knowledge_ttl=400,
        knowledge_share_rate=0.03,
        help_call_enabled=True,
        help_radius=10.0,
        defense_weight=0.3,
        age_enabled=True,
        age_length=8000,
        culture_enabled=True,
        culture_spread_rate=0.003,
        trait_mutation_rate=0.03,
        wildfire_enabled=True,
        fire_rate=0.0008,
        fire_spread_rate=0.08,
        disaster_enabled=True,
        disaster_rate=0.0003,
        energy_max=100.0,
        energy_decay_per_tick=0.04,
        energy_from_food=25.0,
        hungry_ratio=0.45,
        starving_ratio=0.22,
        perceive_radius=14.0,
        eat_radius=1.4,
        wander_turn=0.40,
        steer_turn=0.50,
        hungry_perceive_mult=1.35,
        desperate_perceive_mult=1.7,
        desperate_speed_mult=1.40,
        food_giveup_ticks=150,
        lifespan_mult=0.85,
        birth_enabled=True,
        adult_age=450.0,
        mate_radius=8.0,
        mate_energy_min=30.0,
        birth_rate=0.040,
        boom_ramp_days=2.0,
        boom_birth_floor=0.20,
        boom_cooldown_mult=1.0,
        boom_energy_mult=1.0,
        initial_season_offset=0,
        sex_ratio=0.5,
        mutation_rate=0.06,
        max_sides=24,
        birth_energy_cost=22.0,
        reproduction_cooldown=400,
        carrying_capacity=180,
        max_population=300,
        euthanasia_threshold=0.60,
        disease_enabled=True,
        disease_outbreak_rate=0.0008,
        disease_rate=0.10,
        disease_radius=3.5,
        disease_energy_drain=0.15,
        recovery_rate=0.01,
        disease_lethality=0.50,
        day_length=1000,
        season_length=6000,
        winter_food_mult=0.30,
        night_sight_mult=0.5,
        weather_enabled=True,
        weather_change_rate=0.003,
        fog_sight_mult=0.5,
        rain_speed_mult=0.75,
        storm_wander_bonus=0.45,
        rain_growth_mult=1.15,
        fog_mushroom_mult=1.25,
        storm_plant_damage=0.08,
        weather_sickness_enabled=True,
        chill_rate=0.08,
        chill_threshold=8.0,
        chill_drain=0.30,
        wet_disease_mult=2.5,
        cohesion_weight=0.0,
        alignment_weight=0.0,
        separation_weight=0.0,
        flock_radius=6.0,
        relation_drift_rate=0.3,
        alliance_threshold=85,
        rivalry_threshold=-30,
        shelter_enabled=True,
        exposure_drain=0.08,
        house_capacity=8,
        house_min_size=5.5,
        house_max_size=8.0,
        house_claim_enabled=True,
        rest_recovery_mult=1.2,
        house_decay_ticks=1000,
        hearths_enabled=True,
        rivers_enabled=True,
        river_count=2,
        relief_enabled=True,
        structural_enabled=True,
        rubble_blocking_enabled=True,
        earthquake_enabled=True,
        earthquake_rate=0.0002,
        signal_speed=10.0,
        lightning_enabled=True,
        lightning_strike_rate=0.004,
        anomaly_count=4,
        predation_enabled=True,
        predator_ratio=0.08,
        hunt_radius=9.0,
        bite_damage=60.0,
        bite_cooldown=8,
        energy_from_prey=35.0,
        fear_radius=14.0,
        war_enabled=True,
        attack_radius=2.0,
        attack_damage=60.0,
        coalitions_enabled=True,
        coalition_threshold=60,
        coalition_min_size=2,
        leader_decisions_enabled=True,
        resource_sharing_enabled=True,
        larder_capacity=150.0,
        aid_rate=0.02,
        tribute_enabled=True,
        betrayal_enabled=True,
        defection_enabled=True,
        cannibalism_enabled=True,
        cannibalism_hunger_ratio=0.35,
        cannibalism_energy=40.0,
        eat_enemy_enabled=True,
        eat_kin_enabled=True,
        kin_stigma=15,
        exile_on_kin_eat=True,
        food_decay_enabled=True,
        food_lifespan_ticks=4000,
        theology_enabled=True,
        tithe_rate=0.06,
        temple_faith_cost=400.0,
        agriculture_enabled=True,
        granaries_enabled=True,
        granary_capacity=150.0,
        soil_depletion_enabled=True,
        banquets_enabled=False,
        vocalizations_enabled=True,
        scent_enabled=True,
        envoys_enabled=True,
        markets_enabled=True,
        omens_enabled=True,
        dialect_drift_enabled=True,
        nn_inference_hz=10,
        mutation_sigma=0.1,
        crossover_rate=0.5,
        morphology_annealing_enabled=True,
        annealing_start_generation=50,
        annealing_decay_generations=150,
        morph_lambda_override=None,
        vertex_mutation_std=0.05,
        angle_mutation_std=0.02,
        topological_mutation_rate=0.01,
        soft_cap_enabled=False,
        damping_steepness=12.0,
        crowding_stress_mult=0.80,
        resource_strain_mult=2.0,
        safeguard_enabled=False,
        safeguard_critical_pop=6,
        safeguard_relief_ratio=0.15,
        safeguard_genesis_batch=2,
        safeguard_morph_mercy=False,
        safeguard_max_miracles=1,
    ),
    "boom": dict(
        # High-Scale Population Boom: 500 food, carrying 800, max 1000, rapid reproduction, peaceful flourishing, rich granaries & banquets, temples & bridges.

        boundary="wrap",
        door_clearance=1.5,
        food_count=440,
        plant_growth_rate=0.06,
        plant_spread_rate=0.012,
        nutrient_cycle_rate=0.85,
        plant_variants_enabled=True,
        poison_rate=0.0,
        beast_ratio=0.0,
        diet_strictness=0.0,
        territory_enabled=True,
        territory_radius=14.0,
        trespass_decay=0.0,
        totems_enabled=True,
        succession_enabled=True,
        max_clans=-1,
        schism_enabled=False,
        schism_threshold=0.70,
        schism_min_pop=10,
        communication_enabled=True,
        signal_radius=16.0,
        food_call_rate=0.12,
        alarm_call_rate=0.05,
        knowledge_enabled=True,
        knowledge_ttl=1000,
        knowledge_share_rate=0.08,
        help_call_enabled=True,
        help_radius=16.0,
        defense_weight=0.7,
        age_enabled=True,
        age_length=14400,
        culture_enabled=True,
        culture_spread_rate=0.01,
        trait_mutation_rate=0.02,
        wildfire_enabled=False,
        fire_rate=0.00002,
        fire_spread_rate=0.02,
        disaster_enabled=False,
        disaster_rate=0.00001,
        energy_max=100.0,
        energy_decay_per_tick=0.020,
        energy_from_food=35.0,
        hungry_ratio=0.30,
        starving_ratio=0.12,
        perceive_radius=20.0,
        eat_radius=1.4,
        wander_turn=0.35,
        steer_turn=0.45,
        hungry_perceive_mult=1.3,
        desperate_perceive_mult=1.6,
        desperate_speed_mult=1.35,
        food_giveup_ticks=240,
        lifespan_mult=1.0,
        birth_enabled=True,
        adult_age=120.0,
        mate_radius=12.0,
        mate_energy_min=16.0,
        birth_rate=0.15,
        boom_ramp_days=0.5,  # §BF boom preset: minimal ramp to allow rapid expansion test
        boom_birth_floor=0.70,
        boom_cooldown_mult=1.0,
        boom_energy_mult=1.0,
        initial_season_offset=0,
        sex_ratio=0.5,
        mutation_rate=0.05,
        max_sides=24,
        birth_energy_cost=10.0,
        reproduction_cooldown=140,
        carrying_capacity=800,
        max_population=850,
        euthanasia_threshold=0.7,
        disease_enabled=False,
        disease_outbreak_rate=0.00001,
        disease_rate=0.02,
        disease_radius=2.5,
        disease_energy_drain=0.03,
        recovery_rate=0.05,
        disease_lethality=0.10,
        day_length=1200,
        season_length=14400,
        winter_food_mult=0.85,
        night_sight_mult=0.7,
        weather_enabled=True,
        weather_change_rate=0.001,
        fog_sight_mult=0.7,
        rain_speed_mult=0.90,
        storm_wander_bonus=0.25,
        rain_growth_mult=1.35,
        fog_mushroom_mult=1.45,
        storm_plant_damage=0.01,
        weather_sickness_enabled=False,
        chill_rate=0.02,
        chill_threshold=18.0,
        chill_drain=0.10,
        wet_disease_mult=1.2,
        cohesion_weight=0.0,
        alignment_weight=0.0,
        separation_weight=0.0,
        flock_radius=6.0,
        relation_drift_rate=3.0,
        alliance_threshold=40,
        rivalry_threshold=-95,
        shelter_enabled=True,
        exposure_drain=0.01,
        house_capacity=20,
        house_min_size=5.5,
        house_max_size=8.0,
        house_claim_enabled=True,
        rest_recovery_mult=3.0,
        house_decay_ticks=5000,
        hearths_enabled=True,
        rivers_enabled=True,
        river_count=2,
        relief_enabled=True,
        structural_enabled=True,
        rubble_blocking_enabled=False,
        earthquake_enabled=False,
        earthquake_rate=0.00002,
        signal_speed=8.0,
        lightning_enabled=False,
        lightning_strike_rate=0.0005,
        anomaly_count=2,
        predation_enabled=False,
        predator_ratio=0.01,
        hunt_radius=8.0,
        bite_damage=20.0,
        bite_cooldown=15,
        energy_from_prey=30.0,
        fear_radius=10.0,
        war_enabled=False,
        attack_radius=1.6,
        attack_damage=20.0,
        coalitions_enabled=True,
        coalition_threshold=30,
        coalition_min_size=2,
        leader_decisions_enabled=True,
        resource_sharing_enabled=True,
        larder_capacity=600.0,
        aid_rate=0.10,
        tribute_enabled=False,
        betrayal_enabled=False,
        defection_enabled=False,
        cannibalism_enabled=False,
        cannibalism_hunger_ratio=0.08,
        cannibalism_energy=25.0,
        eat_enemy_enabled=False,
        eat_kin_enabled=False,
        kin_stigma=40,
        exile_on_kin_eat=True,
        food_decay_enabled=True,
        food_lifespan_ticks=12000,
        theology_enabled=True,
        tithe_rate=0.03,
        temple_faith_cost=250.0,
        agriculture_enabled=True,
        granaries_enabled=True,
        granary_capacity=800.0,
        soil_depletion_enabled=False,
        banquets_enabled=True,
        vocalizations_enabled=True,
        scent_enabled=True,
        envoys_enabled=True,
        markets_enabled=True,
        omens_enabled=True,
        dialect_drift_enabled=True,
        nn_inference_hz=15,
        mutation_sigma=0.05,
        crossover_rate=0.3,
        morphology_annealing_enabled=True,
        annealing_start_generation=50,
        annealing_decay_generations=150,
        morph_lambda_override=None,
        vertex_mutation_std=0.05,
        angle_mutation_std=0.02,
        topological_mutation_rate=0.01,
        soft_cap_enabled=True,
        damping_steepness=3.0,
        crowding_stress_mult=0.15,
        resource_strain_mult=0.5,
        safeguard_enabled=True,
        safeguard_critical_pop=20,
        safeguard_relief_ratio=0.40,
        safeguard_genesis_batch=10,
        safeguard_morph_mercy=True,
        safeguard_max_miracles=1,
    ),
    "theocracy": dict(
        # Age of the Sphere & Sacred Faith: Devout spiritual civilization, high faith tithes, glowing temples, avatar miracles, 3D epiphanies, and holy synods.

        boundary="wrap",
        door_clearance=1.5,
        food_count=400,
        plant_growth_rate=0.055,
        plant_spread_rate=0.007,
        nutrient_cycle_rate=0.70,
        plant_variants_enabled=True,
        poison_rate=0.005,
        beast_ratio=0.0,
        diet_strictness=0.0,
        territory_enabled=True,
        territory_radius=15.0,
        trespass_decay=0.2,
        totems_enabled=True,
        succession_enabled=True,
        max_clans=-1,
        schism_enabled=True,
        schism_threshold=0.60,
        schism_min_pop=6,
        communication_enabled=True,
        signal_radius=16.0,
        food_call_rate=0.10,
        alarm_call_rate=0.10,
        knowledge_enabled=True,
        knowledge_ttl=900,
        knowledge_share_rate=0.08,
        help_call_enabled=True,
        help_radius=14.0,
        defense_weight=0.6,
        age_enabled=True,
        age_length=12000,
        culture_enabled=True,
        culture_spread_rate=0.01,
        trait_mutation_rate=0.02,
        wildfire_enabled=True,
        fire_rate=0.00005,
        fire_spread_rate=0.03,
        disaster_enabled=True,
        disaster_rate=0.00003,
        energy_max=100.0,
        energy_decay_per_tick=0.02,
        energy_from_food=34.0,
        hungry_ratio=0.35,
        starving_ratio=0.15,
        perceive_radius=18.0,
        eat_radius=1.4,
        wander_turn=0.35,
        steer_turn=0.45,
        hungry_perceive_mult=1.3,
        desperate_perceive_mult=1.6,
        desperate_speed_mult=1.35,
        food_giveup_ticks=240,
        lifespan_mult=1.1,
        birth_enabled=True,
        adult_age=250.0,
        mate_radius=10.0,
        mate_energy_min=22.0,
        birth_rate=0.075,
        boom_ramp_days=1.5,
        boom_birth_floor=0.35,
        boom_cooldown_mult=1.0,
        boom_energy_mult=1.0,
        initial_season_offset=0,
        sex_ratio=0.5,
        mutation_rate=0.06,
        max_sides=24,
        birth_energy_cost=16.0,
        reproduction_cooldown=280,
        carrying_capacity=380,
        max_population=450,
        euthanasia_threshold=0.7,
        disease_enabled=True,
        disease_outbreak_rate=0.0002,
        disease_rate=0.03,
        disease_radius=3.0,
        disease_energy_drain=0.04,
        recovery_rate=0.04,
        disease_lethality=0.14,
        day_length=1200,
        season_length=12000,
        winter_food_mult=0.80,
        night_sight_mult=0.65,
        weather_enabled=True,
        weather_change_rate=0.002,
        fog_sight_mult=0.65,
        rain_speed_mult=0.85,
        storm_wander_bonus=0.30,
        rain_growth_mult=1.30,
        fog_mushroom_mult=1.40,
        storm_plant_damage=0.015,
        weather_sickness_enabled=False,
        chill_rate=0.03,
        chill_threshold=14.0,
        chill_drain=0.15,
        wet_disease_mult=1.3,
        cohesion_weight=0.0,
        alignment_weight=0.0,
        separation_weight=0.0,
        flock_radius=6.0,
        relation_drift_rate=2.5,
        alliance_threshold=45,
        rivalry_threshold=-60,
        shelter_enabled=True,
        exposure_drain=0.02,
        house_capacity=14,
        house_min_size=5.5,
        house_max_size=8.0,
        house_claim_enabled=True,
        rest_recovery_mult=2.5,
        house_decay_ticks=3000,
        hearths_enabled=True,
        rivers_enabled=True,
        river_count=2,
        relief_enabled=True,
        structural_enabled=True,
        rubble_blocking_enabled=True,
        earthquake_enabled=False,
        earthquake_rate=0.00005,
        signal_speed=8.0,
        lightning_enabled=True,
        lightning_strike_rate=0.001,
        anomaly_count=4,
        predation_enabled=True,
        predator_ratio=0.012,
        hunt_radius=8.0,
        bite_damage=25.0,
        bite_cooldown=15,
        energy_from_prey=40.0,
        fear_radius=12.0,
        war_enabled=True,
        attack_radius=1.8,
        attack_damage=25.0,
        coalitions_enabled=True,
        coalition_threshold=35,
        coalition_min_size=2,
        leader_decisions_enabled=True,
        resource_sharing_enabled=True,
        larder_capacity=350.0,
        aid_rate=0.08,
        tribute_enabled=True,
        betrayal_enabled=False,
        defection_enabled=True,
        cannibalism_enabled=False,
        cannibalism_hunger_ratio=0.10,
        cannibalism_energy=30.0,
        eat_enemy_enabled=False,
        eat_kin_enabled=False,
        kin_stigma=45,
        exile_on_kin_eat=True,
        food_decay_enabled=True,
        food_lifespan_ticks=9000,
        theology_enabled=True,
        tithe_rate=0.07,
        temple_faith_cost=150.0,
        agriculture_enabled=True,
        granaries_enabled=True,
        granary_capacity=450.0,
        soil_depletion_enabled=True,
        banquets_enabled=True,
        vocalizations_enabled=True,
        scent_enabled=True,
        envoys_enabled=True,
        markets_enabled=True,
        omens_enabled=True,
        dialect_drift_enabled=True,
        nn_inference_hz=12,
        mutation_sigma=0.04,
        crossover_rate=0.3,
        morphology_annealing_enabled=True,
        annealing_start_generation=50,
        annealing_decay_generations=150,
        morph_lambda_override=1.0,
        vertex_mutation_std=0.05,
        angle_mutation_std=0.02,
        topological_mutation_rate=0.01,
        soft_cap_enabled=True,
        damping_steepness=4.0,
        crowding_stress_mult=0.25,
        resource_strain_mult=0.9,
        safeguard_enabled=True,
        safeguard_critical_pop=15,
        safeguard_relief_ratio=0.35,
        safeguard_genesis_batch=8,
        safeguard_morph_mercy=True,
        safeguard_max_miracles=1,
    ),
    "warlords": dict(
        # Clash of Clans & Imperial Conquest: Martial dominance, territorial conquests, defensive leagues, granary plunder, and high tactical engagement.

        boundary="wrap",
        door_clearance=1.5,
        food_count=340,
        plant_growth_rate=0.05,
        plant_spread_rate=0.006,
        nutrient_cycle_rate=0.65,
        plant_variants_enabled=True,
        poison_rate=0.01,
        beast_ratio=0.0,
        diet_strictness=0.0,
        territory_enabled=True,
        territory_radius=18.0,
        trespass_decay=1.6,
        totems_enabled=True,
        succession_enabled=True,
        max_clans=-1,
        schism_enabled=True,
        schism_threshold=0.45,
        schism_min_pop=5,
        communication_enabled=True,
        signal_radius=14.0,
        food_call_rate=0.07,
        alarm_call_rate=0.15,
        knowledge_enabled=True,
        knowledge_ttl=600,
        knowledge_share_rate=0.05,
        help_call_enabled=True,
        help_radius=14.0,
        defense_weight=0.5,
        age_enabled=True,
        age_length=10000,
        culture_enabled=True,
        culture_spread_rate=0.006,
        trait_mutation_rate=0.03,
        wildfire_enabled=True,
        fire_rate=0.0001,
        fire_spread_rate=0.04,
        disaster_enabled=True,
        disaster_rate=0.00005,
        energy_max=100.0,
        energy_decay_per_tick=0.024,
        energy_from_food=30.0,
        hungry_ratio=0.38,
        starving_ratio=0.16,
        perceive_radius=18.0,
        eat_radius=1.4,
        wander_turn=0.38,
        steer_turn=0.50,
        hungry_perceive_mult=1.35,
        desperate_perceive_mult=1.65,
        desperate_speed_mult=1.40,
        food_giveup_ticks=200,
        lifespan_mult=0.95,
        birth_enabled=True,
        adult_age=220.0,
        mate_radius=10.0,
        mate_energy_min=24.0,
        birth_rate=0.080,
        boom_ramp_days=1.0,
        boom_birth_floor=0.45,
        boom_cooldown_mult=1.0,
        boom_energy_mult=1.0,
        initial_season_offset=0,
        sex_ratio=0.5,
        mutation_rate=0.06,
        max_sides=24,
        birth_energy_cost=18.0,
        reproduction_cooldown=240,
        carrying_capacity=350,
        max_population=420,
        euthanasia_threshold=0.68,
        disease_enabled=True,
        disease_outbreak_rate=0.0003,
        disease_rate=0.04,
        disease_radius=3.0,
        disease_energy_drain=0.06,
        recovery_rate=0.03,
        disease_lethality=0.20,
        day_length=1200,
        season_length=10000,
        winter_food_mult=0.70,
        night_sight_mult=0.6,
        weather_enabled=True,
        weather_change_rate=0.003,
        fog_sight_mult=0.6,
        rain_speed_mult=0.85,
        storm_wander_bonus=0.35,
        rain_growth_mult=1.25,
        fog_mushroom_mult=1.35,
        storm_plant_damage=0.025,
        weather_sickness_enabled=False,
        chill_rate=0.04,
        chill_threshold=12.0,
        chill_drain=0.18,
        wet_disease_mult=1.5,
        cohesion_weight=0.0,
        alignment_weight=0.0,
        separation_weight=0.0,
        flock_radius=6.0,
        relation_drift_rate=0.6,
        alliance_threshold=50,
        rivalry_threshold=-20,
        shelter_enabled=True,
        exposure_drain=0.03,
        house_capacity=12,
        house_min_size=5.5,
        house_max_size=8.0,
        house_claim_enabled=True,
        rest_recovery_mult=2.0,
        house_decay_ticks=2000,
        hearths_enabled=True,
        rivers_enabled=True,
        river_count=2,
        relief_enabled=True,
        structural_enabled=True,
        rubble_blocking_enabled=True,
        earthquake_enabled=False,
        earthquake_rate=0.0001,
        signal_speed=10.0,
        lightning_enabled=True,
        lightning_strike_rate=0.002,
        anomaly_count=3,
        predation_enabled=True,
        predator_ratio=0.04,
        hunt_radius=9.0,
        bite_damage=35.0,
        bite_cooldown=12,
        energy_from_prey=40.0,
        fear_radius=12.0,
        war_enabled=True,
        attack_radius=2.0,
        attack_damage=60.0,
        coalitions_enabled=True,
        coalition_threshold=30,
        coalition_min_size=2,
        leader_decisions_enabled=True,
        resource_sharing_enabled=True,
        larder_capacity=350.0,
        aid_rate=0.06,
        tribute_enabled=True,
        betrayal_enabled=True,
        defection_enabled=True,
        cannibalism_enabled=True,
        cannibalism_hunger_ratio=0.15,
        cannibalism_energy=40.0,
        eat_enemy_enabled=True,
        eat_kin_enabled=False,
        kin_stigma=30,
        exile_on_kin_eat=True,
        food_decay_enabled=True,
        food_lifespan_ticks=7000,
        theology_enabled=True,
        tithe_rate=0.04,
        temple_faith_cost=300.0,
        agriculture_enabled=True,
        granaries_enabled=True,
        granary_capacity=500.0,
        soil_depletion_enabled=True,
        banquets_enabled=True,
        vocalizations_enabled=True,
        scent_enabled=True,
        envoys_enabled=True,
        markets_enabled=True,
        omens_enabled=True,
        dialect_drift_enabled=True,
        nn_inference_hz=18,
        mutation_sigma=0.09,
        crossover_rate=0.6,
        morphology_annealing_enabled=True,
        annealing_start_generation=50,
        annealing_decay_generations=150,
        morph_lambda_override=None,
        vertex_mutation_std=0.05,
        angle_mutation_std=0.02,
        topological_mutation_rate=0.01,
        soft_cap_enabled=True,
        damping_steepness=7.0,
        crowding_stress_mult=0.40,
        resource_strain_mult=1.3,
        safeguard_enabled=True,
        safeguard_critical_pop=10,
        safeguard_relief_ratio=0.25,
        safeguard_genesis_batch=6,
        safeguard_morph_mercy=True,
        safeguard_max_miracles=1,
    ),
}


def detect_current_preset() -> str | None:
    current_laws = get_laws()
    for name, p_laws in PRESETS.items():
        if all(current_laws.get(k) == v for k, v in p_laws.items()):
            return name
    for name, p_laws in PRESETS.items():
        if (
            current_laws.get("food_count") == p_laws.get("food_count")
            and current_laws.get("carrying_capacity") == p_laws.get("carrying_capacity")
            and current_laws.get("max_population") == p_laws.get("max_population")
        ):
            return name
    return getattr(RT, "current_preset", "balance")


def get_laws() -> dict:
    laws = {name: getattr(RT.config, name) for name in LAW_FIELDS}
    return laws


LAW_STATE_KEY = "law_state_v1"


def _persist_law_state() -> None:
    """Durably remember preset + laws so a backend restart (deploy) keeps them.

    The SQLite DB file is excluded from deploy rsync, so the settings table
    survives restarts while snapshot.json only carries entities. Must be
    called with RT.lock held, after any law change. Best-effort: a persistence
    failure must never break the law change itself.
    """
    try:
        try:
            saved = {name: getattr(RT.saved_config, name) for name in LAW_FIELDS}
        except Exception:
            saved = {}
        payload = {
            "preset": detect_current_preset(),
            "laws": get_laws(),
            "saved_laws": saved,
        }
        DB.set_setting(LAW_STATE_KEY, json.dumps(payload))
    except Exception:
        pass


def _restore_law_state(rt: RuntimeState) -> bool:
    """Re-apply persisted preset/laws at boot, before snapshot rehydration.

    Rebuilds rt.sim with the restored config (used when no snapshot exists).
    Unknown/stale fields are dropped; any failure falls back to env defaults.
    Returns True when a persisted state was applied.
    """
    try:
        raw = DB.get_setting(LAW_STATE_KEY)
    except Exception:
        return False
    if not raw:
        return False
    try:
        data = json.loads(raw)
    except Exception:
        return False
    fields = set(Config.__dataclass_fields__)

    def _clean(d) -> dict:
        return {k: v for k, v in (d or {}).items() if k in fields}

    laws = _clean(data.get("laws"))
    if not laws:
        return False
    saved = _clean(data.get("saved_laws")) or dict(laws)
    try:
        with rt.lock:
            rt.config = replace(rt.config, **laws)
            rt.saved_config = replace(rt.saved_config, **saved)
            rt.current_preset = data.get("preset")
            rt.sim = Simulation(rt.config)
            rt._cached_clans_payload = None
            rt._cached_state_text = None
    except Exception:
        return False
    return True


def apply_laws(laws: GodLaws, persist: bool = True) -> dict:
    """God sets the rules; the world and every creature must obey them.

    persist=True  → Save: current world + future worlds (Reset uses this baseline)
    persist=False → Apply: current world only (Reset reverts to saved baseline)
    """
    updates = {
        k: v for k, v in laws.model_dump(exclude_unset=True).items() if v is not None
    }
    if updates:
        hungry = updates.get("hungry_ratio", RT.config.hungry_ratio)
        starving = updates.get("starving_ratio", RT.config.starving_ratio)
        if starving > hungry:
            raise HTTPException(422, "starving_ratio must be <= hungry_ratio")
        hmin = updates.get("house_min_size", RT.config.house_min_size)
        hmax = updates.get("house_max_size", RT.config.house_max_size)
        if hmax < hmin:
            raise HTTPException(422, "house_max_size must be >= house_min_size")
    with RT.lock:
        cfg = replace(RT.config, **updates)
        RT.config = cfg
        RT.sim.config = cfg  # the living world follows the new law immediately
        RT.sim.world.config = cfg
        if persist:
            # also advance the saved baseline so next Reset inherits it
            if not hasattr(RT, "saved_config"):
                RT.saved_config = RT.config
            else:
                RT.saved_config = replace(RT.saved_config, **updates)
        if "house_claim_enabled" in updates:
            RT.sim._refresh_house_claims()
        # §AP Divine Law Resonance: the shrines chime, the priests preach.
        if updates:
            try:
                RT.sim.on_law_change(sorted(updates.keys()))
            except Exception:
                pass  # theology must never reject a law
        if updates and RT.world_id is not None:
            # AZ Phase 3 P1: batch 180 laws into one transaction while holding RT.lock
            try:
                with DB.batch():
                    for name, value in updates.items():
                        DB.add_law_change(RT.world_id, RT.sim.tick, name, value)
            except Exception:
                for name, value in updates.items():
                    try:
                        DB.add_law_change(RT.world_id, RT.sim.tick, name, value)
                    except Exception:
                        pass
        # Remember preset + laws so the next deploy restart keeps them
        # (applies to both persist=True baseline and persist=False live-only
        # tweaks — a restart continues the world, it is not a Reset).
        if updates:
            _persist_law_state()
    return get_laws()


# ---------------------------------------------------------------- websocket
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await HUB.connect(ws)
    # AZ Phase 1 P0: refresh frozen cache on connect so HTTP doesn't stay stale
    try:
        with RT.lock:
            if getattr(RT, "_cached_clans_payload", None) is None:
                RT._cached_clans_payload = _clans_payload()  # type: ignore
    except Exception:
        RT._cached_clans_payload = None  # type: ignore
    try:
        # AZ Phase 1 P0: use orjson + shared keyframe (stdlib json stalls event loop)
        hello_text = _dumps(hello_payload())
        await asyncio.wait_for(ws.send_text(hello_text), timeout=HUB.SEND_TIMEOUT)
        # share one keyframe per tick across concurrent connects — but stale extinct cache
        # (pre-fix) must be rebuilt so a reconnect after the world ended sees alive=0 and the dialog fires.
        snap_text = RT._cached_state_text
        need_fresh = snap_text is None
        if not need_fresh:
            try:
                # cheap staleness/extinct check without full validation
                is_extinct_live = RT.sim.tick > 30 and len(getattr(RT.sim, "_cached_creatures", [])) == 0
                # quick parse of cached tick/alive to detect stale snapshot
                import json as _json

                cached = _json.loads(snap_text)  # type: ignore[arg-type]
                if cached.get("tick") != RT.sim.tick:
                    need_fresh = True
                elif is_extinct_live and cached.get("creatures_alive") != 0:
                    need_fresh = True
            except Exception:
                need_fresh = True
        if need_fresh:
            with RT.lock:
                snap_text = _dumps(RT.sim.snapshot_payload())
                try:
                    RT._cached_state_text = snap_text  # type: ignore[attr-defined]
                except Exception:
                    pass
        await asyncio.wait_for(
            ws.send_text(snap_text),
            timeout=HUB.SEND_TIMEOUT,
        )
        while True:
            raw = await ws.receive_json()
            try:
                msg = ControlMessage.model_validate(raw)
            except ValidationError:
                continue
            # God control over the socket needs the passkey too (pause/step/
            # reset are as much a hand on the world as any law).
            if not AUTH.verify(raw.get("key")):
                configured = AUTH.configured()
                await asyncio.wait_for(
                    ws.send_json(
                        {
                            "type": "auth_error",
                            "error": "god_key_not_configured" if not configured else "god_key_required",
                            "detail": (
                                "no god passkey exists yet — POST /api/auth/setup first"
                                if not configured
                                else "valid passkey required (key field) to control the world"
                            ),
                        }
                    ),
                    timeout=HUB.SEND_TIMEOUT,
                )
                continue
            await apply_control(msg)
    except WebSocketDisconnect:
        pass
    finally:
        HUB.disconnect(ws)


# --------------------------------------------------------------------- rest
@app.get("/healthz")
async def healthz(
    range: str | None = None,
    minutes: int | None = None,
) -> dict:
    req_mins = minutes
    if req_mins is None and range is not None:
        req_mins = parse_range_minutes(range)

    # True rate from ring buffer (wall-clock)
    avg_dur = round(sum(RT._tick_durs) / len(RT._tick_durs), 2) if RT._tick_durs else 0.0
    max_dur = round(max(RT._tick_durs), 2) if RT._tick_durs else 0.0
    actual_tps = 0.0
    if len(RT._tick_times) >= 2:
        span = RT._tick_times[-1] - RT._tick_times[0]
        if span > 0:
            actual_tps = round((len(RT._tick_times) - 1) / span, 2)

    sim = getattr(RT, "sim", None)
    now = time.time()
    uptime_sec = round(now - getattr(RT, "session_started_at", now), 1)

    alive_creatures = (
        len(sim._cached_creatures)
        if (sim and getattr(sim, "_cached_creatures", None) is not None)
        else (len(sim.world.creatures()) if sim else 0)
    )
    food_count = (
        len(sim._cached_foods)
        if (sim and getattr(sim, "_cached_foods", None) is not None)
        else 0
    )
    houses_count = (
        len(sim._cached_houses)
        if (sim and getattr(sim, "_cached_houses", None) is not None)
        else 0
    )
    clans_count = len(sim.clans) if (sim and hasattr(sim, "clans")) else 0
    deaths_count = getattr(sim, "deaths", 0) if sim else 0
    infected_count = (
        sum(1 for c in sim._cached_creatures if getattr(c, "infected", False))
        if (sim and getattr(sim, "_cached_creatures", None))
        else 0
    )

    caste_counts: dict[str, int] = {}
    if sim and getattr(sim, "_cached_creatures", None):
        for c in sim._cached_creatures:
            k = getattr(c, "caste", "Unknown") or "Unknown"
            caste_counts[k] = caste_counts.get(k, 0) + 1

    sg_active = (
        bool(sim._is_safeguard_active(alive_creatures))
        if (sim and hasattr(sim, "_is_safeguard_active"))
        else False
    )
    sg_eta = round(float(getattr(sim, "_safeguard_eta", 0.0) or 0.0), 3) if sim else 0.0
    sg_tier = int(getattr(sim, "_safeguard_tier", 0) or 0) if sim else 0
    sc_active = (
        bool(sim._is_softcap_active(alive_creatures))
        if (sim and hasattr(sim, "_is_softcap_active"))
        else False
    )
    sc_xi = round(float(getattr(sim, "_density_xi", 0.0) or 0.0), 3) if sim else 0.0

    interval_ms = round(1000.0 / max(RT.speed, MIN_SPEED), 1)
    is_overrun = avg_dur > interval_ms * 1.1

    status_str = "live"
    if RT.last_tick_error:
        status_str = "error"
    elif RT.paused:
        status_str = "paused"
    elif is_overrun:
        status_str = "overrun"

    hist_range = _minute_history(RT, req_mins)
    hist_120 = _minute_history(RT, 120)
    total_session_minutes = len(RT._tick_minutes) + (1 if RT._tick_min_cur[1] > 0 else 0)
    total_overruns = sum(m.get("overruns", 0) for m in RT._tick_minutes) + (RT._tick_min_cur[5] if len(RT._tick_min_cur) > 5 else 0)

    out: dict = {
        "ok": True,
        "status": status_str,
        "tick": sim.tick if sim else 0,
        "paused": RT.paused,
        "speed_target": RT.speed,
        "actual_tps": actual_tps,
        "avg_tick_ms": avg_dur,
        "max_tick_ms": max_dur,
        "interval_ms": interval_ms,
        "clients": len(HUB.clients),
        "db_pending": DB.pending,
        "tick_failures": RT.tick_failures,
        "creatures": alive_creatures,
        "deaths": deaths_count,
        "food_count": food_count,
        "houses_count": houses_count,
        "clans_count": clans_count,
        "infected_count": infected_count,
        "castes": caste_counts,

        # World & Session
        "world_id": RT.world_id,
        "seed": getattr(RT.config, "seed", 0),
        "preset": RT.current_preset,
        "uptime_seconds": uptime_sec,
        "uptime": _format_uptime(uptime_sec),
        "session_start_time": getattr(RT, "session_started_at", now),
        "session_start_tick": getattr(RT, "session_start_tick", 0),
        "session_ticks": (sim.tick - getattr(RT, "session_start_tick", 0)) if sim else 0,
        "session_minutes_total": total_session_minutes,
        "day": getattr(sim, "day", 1) if sim else 1,
        "season": sim._season() if (sim and hasattr(sim, "_season")) else "spring",
        "time_of_day": round(sim._time_of_day(), 3) if (sim and hasattr(sim, "_time_of_day")) else 0.25,
        "weather": getattr(sim, "weather", "clear") if sim else "clear",
        "age": sim._age() if (sim and hasattr(sim, "_age")) else None,

        # Regulation
        "safeguard_active": sg_active,
        "safeguard_eta": sg_eta,
        "safeguard_tier": sg_tier,
        "softcap_active": sc_active,
        "softcap_xi": sc_xi,

        # System & resources
        "memory_mb": _get_process_memory_mb(),
        "threads": threading.active_count(),
        "total_overruns": total_overruns,
        "pid": os.getpid(),

        # Subsystem timings & budget
        "subsystems_ms": dict(getattr(sim, "_phase_ms", {}) or {}) if sim else {},
        "subsystems_avg_ms": sim.phase_averages() if (sim and hasattr(sim, "phase_averages")) else {},
        "tick_budget": {"dev_ms": 45.0, "n150_ms": 85.0, "mean_ms": avg_dur},

        # Rollups
        "history_120m": hist_120,
        "history": hist_range,
        "range": range or (f"{req_mins}m" if req_mins else "all"),
    }
    if RT.last_tick_error:
        out["ok"] = False
        out["last_tick_error"] = RT.last_tick_error
    if is_overrun:
        out["overrun"] = True
    return out


@app.get("/health", response_class=HTMLResponse)
@app.get("/health.html", response_class=HTMLResponse)
async def health_dashboard() -> HTMLResponse:
    candidates = [
        Path(__file__).resolve().parent.parent.parent / "frontend" / "public" / "health.html",
        Path(__file__).resolve().parent.parent.parent / "frontend" / "dist" / "health.html",
        Path("/root/app/fl/frontend/public/health.html"),
        Path("/root/app/fl/frontend/dist/health.html"),
        Path("frontend/public/health.html"),
    ]
    for p in candidates:
        if p.is_file():
            return HTMLResponse(p.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Health page not found</h1>", status_code=404)


@app.get("/api/perf/telemetry")
async def get_telemetry(window_seconds: int = 60) -> dict:
    """Return rolling performance telemetry over recent ticks and CPU core load."""
    now = time.monotonic()
    durs = list(RT._tick_durs)
    times = list(RT._tick_times)
    counts = list(RT._tick_creature_counts)

    # Filter to window
    filtered_durs = [d for d, t in zip(durs, times) if now - t <= window_seconds] if times else durs
    filtered_counts = [c for c, t in zip(counts, times) if now - t <= window_seconds] if times else counts

    actual_tps = 0.0
    if len(times) >= 2:
        span = times[-1] - times[0]
        if span > 0:
            actual_tps = round((len(times) - 1) / span, 2)

    # Compute percentiles
    s_durs = sorted(filtered_durs) if filtered_durs else [0.0]
    p50 = round(s_durs[len(s_durs) // 2], 2)
    p95 = round(s_durs[int(len(s_durs) * 0.95)], 2)
    p99 = round(s_durs[int(len(s_durs) * 0.99)], 2)

    # Read per-core CPU usage — AZ Phase 1 P1: 1s cache off event loop
    global _PROCSTAT_CACHE
    now_proc = time.monotonic()
    if _PROCSTAT_CACHE is not None and now_proc - _PROCSTAT_CACHE[0] < 1.0:
        cores_usage = _PROCSTAT_CACHE[1]
    else:
        cores_usage = []
        try:
            with open("/proc/stat", "r") as f:
                for line in f:
                    parts = line.split()
                    if parts and parts[0].startswith("cpu") and parts[0] != "cpu":
                        t = [int(x) for x in parts[1:]]
                        idle = t[3] + (t[4] if len(t) > 4 else 0)
                        total = sum(t)
                        cores_usage.append({"core": parts[0], "idle": idle, "total": total})
        except Exception:
            pass
        _PROCSTAT_CACHE = (now_proc, cores_usage)

    return {
        "tick": RT.sim.tick,
        "speed_target": RT.speed,
        "actual_tps": actual_tps,
        "sample_count": len(filtered_durs),
        "duration_stats_ms": {
            "min": round(min(filtered_durs), 2) if filtered_durs else 0.0,
            "avg": round(sum(filtered_durs) / len(filtered_durs), 2) if filtered_durs else 0.0,
            "max": round(max(filtered_durs), 2) if filtered_durs else 0.0,
            "p50": p50,
            "p95": p95,
            "p99": p99,
        },
        "creatures": {
            "current": len(RT.sim._cached_creatures) if getattr(RT.sim, "_cached_creatures", None) is not None else 0,
            "min": min(filtered_counts) if filtered_counts else 0,
            "avg": round(sum(filtered_counts) / len(filtered_counts), 1) if filtered_counts else 0,
            "max": max(filtered_counts) if filtered_counts else 0,
        },
        "overruns": sum(1 for d in filtered_durs if d > (1000.0 / max(RT.speed, MIN_SPEED)) * 1.1),
        "proc_cores": cores_usage,
        # BJ-6: per-subsystem timing + tick-budget regression data.
        "subsystems_ms": dict(getattr(RT.sim, "_phase_ms", {}) or {}),
        "subsystems_avg_ms": RT.sim.phase_averages() if hasattr(RT.sim, "phase_averages") else {},
        "tick_budget": {
            "dev_ms": 45.0,
            "n150_ms": 85.0,
            "mean_ms": round(sum(filtered_durs) / len(filtered_durs), 2) if filtered_durs else 0.0,
        },
    }


@app.get("/api/metrics/morphology")
async def get_morphology_metrics() -> dict:
    """BC.6.2 live generational metrics: λ, K, A, P, sharpness, asymmetry."""
    try:
        cfg = RT.config
        soa = getattr(RT.sim, "_soa", None)
        if soa is None or getattr(soa, "N", 0) == 0:
            return {
                "enabled": bool(getattr(cfg, "morphology_annealing_enabled", True)),
                "count": 0,
                "mean_lambda": 0.0,
                "mean_K": 0.0,
                "mean_A": 0.0,
                "mean_P": 0.0,
                "mean_Dmult": 0.0,
                "asymmetry_pct": 0.0,
                "theta_hist": [],
            }
        N = int(soa.N)
        try:
            from .evolution_manager import lambda_for_generation as _lam
            gens = [c.generation for c in RT.sim._cached_creatures[:N] if hasattr(c, "generation")]
            mean_lam = sum(_lam(g, cfg) for g in gens) / len(gens) if gens else 0.0
        except Exception:
            mean_lam = 0.0
        try:
            if hasattr(soa, "morph_traits") and hasattr(soa.morph_traits, "shape"):
                import numpy as _np  # type: ignore
                mt = soa.morph_traits[:N]
                mask = mt[:, 0] > 0
                if int(_np.sum(mask)) == 0:
                    meanK = float(_np.mean(soa.morph_k[:N])) if hasattr(soa, "morph_k") else 0.0
                    return {"enabled": True, "count": N, "mean_lambda": round(mean_lam, 3), "mean_K": round(meanK, 2), "mean_A": 0, "mean_P": 0, "mean_Dmult": 0, "asymmetry_pct": 0, "theta_hist": []}
                meanK = float(_np.mean(soa.morph_k[:N][mask])) if hasattr(soa, "morph_k") else 0.0
                meanA = float(_np.mean(mt[mask, 0]))
                meanP = float(_np.mean(mt[mask, 1]))
                meanD = float(_np.mean(mt[mask, 5]))
                asym = mt[mask, 4]
                pct = float(_np.sum(asym > 0.46) / len(asym) * 100.0) if len(asym) else 0.0
                thetas = mt[mask, 3]
                hist = []
                bins = [0, 0.5, 1.0, 1.5, 2.0, 3.14]
                for i in range(len(bins) - 1):
                    cnt = int(_np.sum((thetas >= bins[i]) & (thetas < bins[i + 1])))
                    hist.append(cnt)
                return {
                    "enabled": True,
                    "count": int(_np.sum(mask)),
                    "mean_lambda": round(mean_lam, 3),
                    "mean_K": round(meanK, 2),
                    "mean_A": round(meanA, 3),
                    "mean_P": round(meanP, 3),
                    "mean_Dmult": round(meanD, 3),
                    "asymmetry_pct": round(pct, 1),
                    "theta_hist": hist,
                }
            else:
                return {"enabled": True, "count": N, "mean_lambda": round(mean_lam, 3), "mean_K": 0, "mean_A": 0, "mean_P": 0, "mean_Dmult": 0, "asymmetry_pct": 0, "theta_hist": []}
        except Exception as e:
            return {"enabled": True, "count": N, "error": str(e), "mean_lambda": round(mean_lam, 3)}
    except Exception as e:
        return {"enabled": False, "error": str(e), "count": 0}


@app.get("/api/metrics/safeguards")
async def get_safeguards_metrics() -> dict:
    """Phase 7.2 — safeguard telemetry: N, eta, tier, miracles, mercy."""
    try:
        cfg = RT.config
        sim = getattr(RT, "sim", None)
        if sim is None:
            return {"enabled": False, "count": 0}
        N = len(getattr(sim, "_cached_creatures", []) or [])
        # also try SoA N
        try:
            soa = getattr(sim, "_soa", None)
            if soa is not None and hasattr(soa, "N"):
                N = int(soa.N)
        except Exception:
            pass
        enabled = bool(getattr(cfg, "safeguard_enabled", False))
        if not enabled:
            return {"enabled": False, "N": N, "eta": 0.0, "tier": 0, "miracles": 0, "mercy": False}
        # compute eta via safeguard engine if available
        eta = 0.0
        tier = 0
        miracles = 0
        mercy = False
        try:
            if hasattr(sim, "_safeguard") and getattr(sim, "_safeguard", None) is not None:
                eta = float(getattr(sim, "_safeguard_eta", 0.0) or 0.0)
                tier = int(getattr(sim, "_safeguard_tier", 0) or 0)
                miracles = int(getattr(sim._safeguard, "miracles", 0) or 0)
                mercy = bool(getattr(sim._safeguard, "mercy_active", lambda x: False)(eta)) if hasattr(sim._safeguard, "mercy_active") else bool(getattr(cfg, "safeguard_morph_mercy", False) and eta > 0.3)
            else:
                from .safeguard_engine import compute_eta, tier_for_eta

                cc = int(getattr(cfg, "carrying_capacity", 350))
                relief = float(getattr(cfg, "safeguard_relief_ratio", 0.30))
                kcrit = int(getattr(cfg, "safeguard_critical_pop", 12))
                eta = compute_eta(N, cc, relief, kcrit, enabled)
                tier = tier_for_eta(eta, N, kcrit)
                mercy = bool(getattr(cfg, "safeguard_morph_mercy", False) and eta > 0.3)
        except Exception:
            pass
        return {"enabled": True, "N": N, "eta": round(eta, 3), "tier": tier, "miracles": miracles, "mercy": mercy, "Kcrit": int(getattr(cfg, "safeguard_critical_pop", 12)), "Ksafe": round(float(getattr(cfg, "carrying_capacity", 350)) * float(getattr(cfg, "safeguard_relief_ratio", 0.30)), 1)}
    except Exception as e:
        return {"enabled": False, "error": str(e), "N": 0}


@app.get("/api/metrics/damping")
async def get_damping_metrics() -> dict:
    """Phase 7.2b — damping telemetry: N, xi, effective birth/decay."""
    try:
        cfg = RT.config
        sim = getattr(RT, "sim", None)
        if sim is None:
            return {"enabled": False, "N": 0}
        N = len(getattr(sim, "_cached_creatures", []) or [])
        try:
            soa = getattr(sim, "_soa", None)
            if soa is not None and hasattr(soa, "N"):
                N = int(soa.N)
        except Exception:
            pass
        enabled = bool(getattr(cfg, "soft_cap_enabled", True))
        if not enabled:
            return {"enabled": False, "N": N, "xi": 0.0, "birth_rate_eff": float(getattr(cfg, "birth_rate", 0.05)), "decay_eff": float(getattr(cfg, "energy_decay_per_tick", 0.022))}
        try:
            from .density_damping import compute_xi, scales_for_xi

            Kcap = int(getattr(cfg, "effective_carrying_capacity", getattr(cfg, "carrying_capacity", 350)))
            if sim is not None and hasattr(sim, "_age"):
                try:
                    from .simulation import AGE_CAP_MULT
                    age_m = sim._age()
                    if age_m is not None:
                        Kcap = max(2, round(Kcap * AGE_CAP_MULT.get(age_m, 1.0)))
                except Exception:
                    pass
            xi = compute_xi(N, Kcap, enabled)
            scales = scales_for_xi(xi, cfg)
            return {
                "enabled": True,
                "N": N,
                "Kcap": Kcap,
                "xi": round(xi, 3),
                "birth_rate_eff": round(float(getattr(cfg, "birth_rate", 0.05)) * scales.get("birth_rate_eff", 1.0), 4),
                "birth_cost_eff": round(float(getattr(cfg, "birth_energy_cost", 20)) * scales.get("birth_cost_eff", 1.0), 1),
                "decay_eff": round(float(getattr(cfg, "energy_decay_per_tick", 0.022)) * scales.get("decay_eff", 1.0), 4),
                "growth_eff": round(float(getattr(cfg, "plant_growth_rate", 0.05)) * scales.get("growth_eff", 1.0), 4),
                "scales": {k: round(v, 3) for k, v in scales.items()},
            }
        except Exception as e:
            return {"enabled": True, "N": N, "error": str(e), "xi": 0.0}
    except Exception as e:
        return {"enabled": False, "error": str(e), "N": 0}


@app.get("/api/version")
async def get_version() -> dict:
    """Version + git revision for footer display."""
    global _VERSION_CACHE
    if _VERSION_CACHE is not None:
        return _VERSION_CACHE
    import subprocess
    version = "0.1.6"
    revision = ""
    try:
        import tomllib
        with open("pyproject.toml", "rb") as f:
            data = tomllib.load(f)
            version = data.get("project", {}).get("version", version)
    except Exception:
        try:
            import pathlib
            txt = pathlib.Path("pyproject.toml").read_text()
            for line in txt.splitlines():
                if line.strip().startswith("version"):
                    parts = line.split("=")
                    if len(parts) == 2:
                        version = parts[1].strip().strip('"').strip("'")
        except Exception:
            pass
    try:
        revision = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=".", timeout=2).decode().strip()
    except Exception:
        try:
            revision = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], timeout=2).decode().strip()
        except Exception:
            revision = "dev"
    _VERSION_CACHE = {
        "version": version,
        "revision": revision,
        "developer": "Long Phan",
        "email": "long@minhnhan.in",
        "contact": "long@minhnhan.in",
    }
    return _VERSION_CACHE


@app.get("/api/config")
async def get_config() -> dict:
    return asdict(RT.config)


@app.get("/api/laws")
async def read_laws() -> dict:
    """Current laws of nature (god-readable)."""
    return get_laws()


# --------------------------------------------------------------------- auth
@app.get("/api/auth/status")
async def auth_status() -> dict:
    """Whether a god passkey exists (public — lets the client ask to enroll)."""
    return {"configured": AUTH.configured()}


@app.post("/api/auth/setup")
async def auth_setup(body: SetupPasskey) -> dict:
    """First-time enrollment: register the god passkey (only before one exists)."""
    try:
        AUTH.setup(body.passkey)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(409, {"error": "god_key_already_configured", "detail": str(exc)}) from exc
    return {"ok": True, "configured": True}


@app.post("/api/laws", dependencies=[Depends(require_god)])
async def write_laws(laws: GodLaws, persist: bool = True, reset: bool = False) -> dict:
    """Set new laws of nature (god-writable).

    persist=true  (default) → Save: current + future worlds (Reset keeps it)
    persist=false → Apply: current world only (Reset reverts)
    reset=true    → also reset world with new laws
    """
    result = apply_laws(laws, persist=persist)
    if reset:
        payload = None
        with RT.lock:
            base = getattr(RT, "saved_config", RT.config) if persist else RT.config
            new_cfg = replace(base, seed=random.SystemRandom().randint(0, 2**31 - 1))
            RT.config = new_cfg
            RT.sim = Simulation(new_cfg)
            RT._cached_clans_payload = None
            RT._cached_state_text = None
            RT.paused = False
            start_world()
            payload = RT.sim.snapshot_payload()
        if payload is not None:
            await HUB.broadcast(payload)
    return result


@app.get("/api/presets")
async def list_presets() -> dict:
    """List available law presets (sustainable is the 1000-day world)."""
    return {
        "presets": list(PRESETS.keys()),
        "details": PRESETS,
        "current": detect_current_preset(),
    }


@app.post("/api/presets/{name}", dependencies=[Depends(require_god)])
async def apply_preset(name: str, persist: bool = True, reset: bool = False) -> dict:
    """Apply a named preset bundle. reset=true also resets the world with new laws."""
    if name not in PRESETS:
        raise HTTPException(404, f"preset {name!r} not found — {list(PRESETS.keys())}")
    RT.current_preset = name
    laws = GodLaws.model_validate(PRESETS[name])
    result = apply_laws(laws, persist=persist)
    if reset:
        payload = None
        with RT.lock:
            base = getattr(RT, "saved_config", RT.config) if persist else RT.config
            new_cfg = replace(base, seed=random.SystemRandom().randint(0, 2**31 - 1))
            RT.config = new_cfg
            RT.sim = Simulation(new_cfg)
            RT._cached_clans_payload = None
            RT._cached_state_text = None
            RT.paused = False
            start_world()
            payload = RT.sim.snapshot_payload()
        if payload is not None:
            await HUB.broadcast(payload)
    return {"preset": name, "laws": result, "reset": reset}


MAJOR_EVENT_TYPES = (
    "war", "conquest", "takeover", "schism", "betrayal", "alliance",
    "coalition_formed", "peace", "regicide", "succession", "outbreak",
    "disaster", "miracle", "synod", "temple", "epiphany", "extinction",
    "clan_extinction"
)


@app.get("/api/history")
async def get_history(
    since: int = 0,
    limit: int = 500,
    type: str | None = None,
    types: str | None = None,
    major: bool = False,
    entity_id: int | None = None,
    clan_id: int | None = None,
) -> dict:
    """The durable chronicle for the current world (paginated by event id).

    §AT-1: `clan_id=N` filters at the SQL level — events whose payload names
    the clan (a/b/clan_id/conquest/schism/takeover pairs) stay queryable even
    after they rolled off the in-memory chronicle.
    AZ Phase 1 P1: read-your-writes from RAM instead of forcing a flush."""
    limit = max(1, min(limit, 2000))
    types_list = None
    if types:
        types_list = [t.strip() for t in types.split(",") if t.strip()]
    elif major:
        types_list = list(MAJOR_EVENT_TYPES)
    clan_names = {}
    with RT.lock:
        for cid, info in RT.sim.clans.items():
            if info.get("name"):
                clan_names[str(cid)] = info["name"]
    db_events = DB.history(
        RT.world_id,
        since_id=since,
        limit=limit,
        type_filter=type,
        types_filter=types_list,
        entity_id=entity_id,
        clan_id=clan_id,
    ) if RT.world_id else []
    # AZ Phase 1 P1: merge pending RAM events without flushing
    if RT.world_id and DB.pending:
        try:
            pend = DB.pending_events(RT.world_id, limit=limit)
            # apply same filters to pending
            filtered = []
            for ev in pend:
                if type and ev["type"] != type:
                    continue
                if types_list and ev["type"] not in types_list:
                    continue
                if entity_id is not None and ev["entity_id"] != entity_id:
                    continue
                if clan_id is not None:
                    if not any(ev["payload"].get(k) == clan_id for k in CLAN_PAYLOAD_KEYS):
                        continue
                if since and ev["id"] and ev["id"] >= since:
                    # pending has id 0, so skip since check for pending
                    pass
                filtered.append(ev)
            # prepend pending (newest) before DB tail, cap to limit
            merged = (filtered + db_events)[:limit]
            db_events = merged
        except Exception:
            pass
    if major:
        # Filter out minor non-lethal combat ticks so major historical milestones aren't crowded out
        db_events = [ev for ev in db_events if ev.get("type") != "war" or ev.get("payload", {}).get("lethal") is True]
    total = DB.death_count(RT.world_id) if RT.world_id else 0
    # include pending deaths not yet flushed
    if RT.world_id and DB.pending:
        try:
            with DB._lock:
                pend_deaths = 0
                for k, args in list(DB._pending):
                    if k == "event":
                        wid, ev = args
                        if wid == RT.world_id and getattr(ev, "type", None) == "death":
                            pend_deaths += 1
                total += pend_deaths
        except Exception:
            pass
    return {
        "world_id": RT.world_id,
        "total_deaths": total,
        "clan_names": clan_names,
        "events": db_events,
    }


@app.get("/api/clans/{clan_id}/history")
async def get_clan_history(clan_id: int, page: int = 0, size: int = 50) -> dict:
    """§AT-1: the FULL filtered event stream for a clan — paginated over the
    in-memory chronicle (newest page first), plus the clan's own internal log
    (leader changes, takeovers, wars, schisms)."""
    with RT.lock:
        if clan_id not in RT.sim.clans:
            raise HTTPException(404, "clan not found")
        size = max(1, min(size, 200))
        page = max(0, page)
        matching = [
            e for e in RT.sim.history
            if any(e.payload.get(k) == clan_id for k in CLAN_PAYLOAD_KEYS)
        ]
        matching.reverse()  # newest first
        start = page * size
        slice_ = matching[start:start + size]
        return {
            "clan_id": clan_id,
            "page": page,
            "size": size,
            "total": len(matching),
            "has_more": start + size < len(matching),
            "events": [e.model_dump(mode="json") for e in slice_],
            # the clan's internal milestone log (capped at 30 in-memory)
            "log": RT.sim.clans[clan_id].get("history", []),
        }


@app.get("/api/worlds")
async def get_worlds() -> dict:
    """All world runs recorded in the database (newest first)."""
    # AZ Phase 1 P1: no forced flush — durability window is 5s, stale lag accepted
    return {"worlds": DB.worlds()}


@app.get("/api/clans/{clan_id}")
async def get_clan(clan_id: int) -> dict:
    """Single clan details with members and history."""
    with RT.lock:
        return _clan_details(clan_id)


def _clan_details(clan_id: int) -> dict:
    if clan_id not in RT.sim.clans:
        raise HTTPException(404, "clan not found")
    info = RT.sim.clans[clan_id]
    # members — AZ Phase 1 P1: use cached creatures + direct imports (no __import__ per member)
    members = []
    for c in (RT.sim._cached_creatures if getattr(RT.sim, "_cached_creatures", None) else RT.sim.world.creatures()):
        if c.clan_id == clan_id:
            members.append({
                "id": c.id,
                "caste": c.caste,
                "sex": c.sex,
                "age": c.age,
                "lifespan": c.lifespan,
                "stage": c.stage,
                "energy": round(c.energy, 1),
                "health": round(c.health, 1),
                "status": c.status,
                "personal_name": personal_name_for(c.id, RT.sim.config.seed, c.generation),
                "glyph": glyph_for(c.id, RT.sim.config.seed, c.generation),
                "personality": getattr(c, "personality", None),
                "title": getattr(c, "title", None),
                "equipped_item": getattr(c, "equipped_item", None),
                "food_basket": getattr(c, "food_basket", 0),
            })
    # houses — a clan can have multiple houses, strictly one main house
    clan_houses = []
    main_house = None
    valid_clan_houses = [
        ent for ent in RT.sim.world.entities.values()
        if ent.kind == "house" and getattr(ent, "clan_id", 0) == clan_id and not getattr(ent, "is_ruin", False)
    ]
    main_hid = info.get("main_house_id")
    if valid_clan_houses and (not main_hid or not any(h.id == main_hid for h in valid_clan_houses)):
        main_hid = valid_clan_houses[0].id
        info["main_house_id"] = main_hid

    for ent in valid_clan_houses:
        is_main = (ent.id == main_hid)
        ent.is_main = is_main
        h_obj = {
            "id": ent.id,
            "x": round(ent.x, 2),
            "y": round(ent.y, 2),
            "size": getattr(ent, "size", 0),
            "is_main": is_main,
            "is_ruin": False,
            "clan_color": getattr(ent, "clan_color", None),
        }
        clan_houses.append(h_obj)
        if is_main:
            main_house = h_obj

    # war record
    wins = int(info.get("war_wins") or getattr(RT.sim, "_clan_war_wins", {}).get(clan_id, 0))
    losses = int(info.get("war_losses") or getattr(RT.sim, "_clan_war_losses", {}).get(clan_id, 0))
    # recent events for this clan
    clan_events = [e for e in RT.sim.history if (e.payload.get("a") == clan_id or e.payload.get("b") == clan_id or e.payload.get("clan_id") == clan_id) ][-20:]
    return {
        "id": clan_id,
        "name": info.get("name"),
        "color": info.get("color"),
        "totem": info.get("totem"),
        "founder_id": info.get("founder_id"),
        "leader_id": info.get("leader_id"),
        "born_tick": info.get("born_tick") or 0,
        "founded_day": (info.get("born_tick") or 0) // max(1, RT.sim.config.day_length),
        "dead_count": getattr(RT.sim, "_clan_deaths", {}).get(clan_id, 0),
        "population": len(members),
        "house": main_house,
        "houses": clan_houses,
        "main_house_id": main_house["id"] if main_house else None,
        "war_wins": wins,
        "war_losses": losses,
        "territory_radius": RT.sim.config.territory_radius if RT.sim.config.territory_enabled else None,
        "specialization": info.get("specialization"),
        "culture": info.get("culture"),
        "members": members,
        "events": [e.model_dump(mode="json") for e in clan_events],
        "history": info.get("history", []),
        "coalition_id": info.get("coalition_id"),  # §AB
        "larder": round(float(info.get("larder", 0.0)), 1),  # §AB clan store
        "tribute_to": info.get("tribute_to"),  # §AB subjugation
        "faith": round(float(info.get("faith", 0.0)), 1),  # §AP clan faith pool
        "shrine_level": int(info.get("shrine_level", 0)),  # §AP shrine/temple
        "governance": info.get("governance", "republic"),  # §AL
        "bylaws": info.get("bylaws", {}),  # §AL
        "task_board": info.get("task_board", {}),  # §AL
    }



@app.get("/api/clans")
async def get_clans() -> dict:
    """Clan roster with lineage, territory and war record."""
    # AZ Phase 1 P0/P1: refresh frozen cache on HTTP serve; lock for build
    cached = getattr(RT, "_cached_clans_payload", None)
    if cached is not None:
        # also refresh if tick drifted >10 ticks since cache (stale while no WS clients)
        try:
            if isinstance(cached, dict) and cached.get("tick", -1) < RT.sim.tick - 10:
                raise ValueError("stale")
            return cached
        except Exception:
            pass
    with RT.lock:
        try:
            payload = _clans_payload()
            RT._cached_clans_payload = payload  # type: ignore
            return payload
        except Exception:
            RT._cached_clans_payload = None  # type: ignore
            raise


def _clans_payload(sim: Simulation | None = None) -> dict:
    sim = sim or RT.sim
    # live clan dict + live population + house territory + war history
    # N150: limit to top 100 alive clans to avoid 1.5MB/5s at 4000 clans
    war_wins = getattr(sim, "_clan_war_wins", {})
    war_losses = getattr(sim, "_clan_war_losses", {})
    # houses by clan
    houses_by_clan: dict[int, dict] = {}
    for ent in sim.world.entities.values():
        if ent.kind == "house" and getattr(ent, "clan_id", 0):
            houses_by_clan[ent.clan_id] = {"x": ent.x, "y": ent.y, "size": getattr(ent, "size", 0), "is_ruin": getattr(ent, "is_ruin", False)}
    # single pass for population count across all clans
    pop_by_clan: dict[int, int] = {}
    for c in sim._get_creatures():
        if c.clan_id:
            pop_by_clan[c.clan_id] = pop_by_clan.get(c.clan_id, 0) + 1
    # §X clan memory — only for top 50 alive clans to avoid 4000× overhead
    alive_cids = [cid for cid, pop in pop_by_clan.items() if pop > 0]
    alive_cids.sort(key=lambda cid: -pop_by_clan.get(cid, 0))
    top_cids = set(alive_cids[:50])
    knowledge_by_clan = {}
    if sim.config.knowledge_enabled and top_cids:
        # compute only for top 50, not all 4000
        all_know = sim.clan_knowledge()
        knowledge_by_clan = {cid: all_know.get(cid) for cid in top_cids if cid in all_know}
    clans = []
    for cid, info in sim.clans.items():
        pop = pop_by_clan.get(cid, 0)
        if pop == 0:
            continue  # skip ghost clans (exile/schism remnants) — saves 1.5MB
        if cid not in top_cids and len(clans) >= 100:
            continue
        house = houses_by_clan.get(cid)
        clans.append({
            "id": cid,
            "name": info.get("name"),
            "color": info.get("color"),
            "totem": info.get("totem"),
            "founder_id": info.get("founder_id"),
            "leader_id": info.get("leader_id"),
            "born_tick": info.get("born_tick") or 0,
            "founded_day": (info.get("born_tick") or 0) // max(1, sim.config.day_length),
            "dead_count": getattr(sim, "_clan_deaths", {}).get(cid, 0),
            "population": pop,
            "house": house,
            "war_wins": int(info.get("war_wins") or war_wins.get(cid, 0)),
            "war_losses": int(info.get("war_losses") or war_losses.get(cid, 0)),
            "territory_radius": sim.config.territory_radius if sim.config.territory_enabled else None,
            "specialization": info.get("specialization"),
            "culture": info.get("culture"),
            "culture_id": info.get("culture_id"),
            "knowledge": knowledge_by_clan.get(cid),
            "coalition_id": info.get("coalition_id"),  # §AB
            "larder": round(float(info.get("larder", 0.0)), 1),  # §AB clan store
            "granary": round(float(info.get("granary", 0.0)), 1),  # §AM grain store
            "harvest_total": round(float(info.get("harvest_total", 0.0)), 1),  # §AM
            "feast": sim.tick < int(info.get("feast_until", 0)),  # §AM banqueting
            "dialect": round(float(info.get("dialect", 0.0)), 3),  # §AN speech drift
            "tribute_to": info.get("tribute_to"),  # §AB subjugation
            "faith": round(float(info.get("faith", 0.0)), 1),  # §AP clan faith pool
            "shrine_level": int(info.get("shrine_level", 0)),  # §AP shrine/temple
            "governance": info.get("governance", "republic"),  # §AL
            "bylaws": info.get("bylaws", {}),  # §AL
            "task_board": info.get("task_board", {}),  # §AL
        })

    # sort by population desc and cap at 100
    clans.sort(key=lambda c: (-c["population"], c["id"]))
    clans = clans[:100]
    names = {str(cid): info.get("name") for cid, info in sim.clans.items() if info.get("name")}
    return {"clans": clans, "names": names, "tick": sim.tick}

# BD.1.3 High-Performance Analytics REST API — 1s memoization, rate-limited
def _analytics_payload(sim) -> dict:
    try:
        from .analytics import get_engine  # type: ignore

        eng = get_engine()
        if not eng.ring.ticks or eng.ring.ticks[-1] != sim.tick:
            try:
                eng.on_tick(sim)
            except Exception:
                pass
        return eng.summary(sim)
    except Exception as e:
        return {"error": str(e), "tick": getattr(sim, "tick", 0)}


@app.get("/api/analytics/summary")
async def get_analytics_summary() -> dict:
    now = time.monotonic()
    cached = _ANALYTICS_CACHE.get("summary")
    if cached and now - cached[0] < 1.0:
        return cached[1]
    with RT.lock:
        payload = _analytics_payload(RT.sim)
    _ANALYTICS_CACHE["summary"] = (now, payload)
    return payload


@app.get("/api/analytics/timeseries")
async def get_analytics_timeseries() -> dict:
    now = time.monotonic()
    cached = _ANALYTICS_CACHE.get("timeseries")
    if cached and now - cached[0] < 1.0:
        return cached[1]
    with RT.lock:
        try:
            from .analytics import get_engine  # type: ignore

            eng = get_engine()
            payload = {"tick": RT.sim.tick, "ring": eng.ring.snapshot(), "mortality": eng.mortality.stacked()}
        except Exception as e:
            payload = {"error": str(e)}
    _ANALYTICS_CACHE["timeseries"] = (now, payload)
    return payload


@app.get("/api/analytics/trophic")
async def get_analytics_trophic() -> dict:
    now = time.monotonic()
    cached = _ANALYTICS_CACHE.get("trophic")
    if cached and now - cached[0] < 1.0:
        return cached[1]
    with RT.lock:
        try:
            from .analytics import get_engine  # type: ignore

            eng = get_engine()
            payload = {"tick": RT.sim.tick, **eng.lotka_volterra(RT.sim), "biodiversity": eng.biodiversity(RT.sim)}
        except Exception as e:
            payload = {"error": str(e)}
    _ANALYTICS_CACHE["trophic"] = (now, payload)
    return payload


@app.get("/api/analytics/hegemony")
async def get_analytics_hegemony() -> dict:
    now = time.monotonic()
    cached = _ANALYTICS_CACHE.get("hegemony")
    if cached and now - cached[0] < 1.0:
        return cached[1]
    with RT.lock:
        try:
            from .analytics import get_engine  # type: ignore

            eng = get_engine()
            payload = {"tick": RT.sim.tick, **eng.hegemony(RT.sim), "gini": eng.gini(RT.sim)}
        except Exception as e:
            payload = {"error": str(e)}
    _ANALYTICS_CACHE["hegemony"] = (now, payload)
    return payload


@app.get("/api/analytics/warnings")
async def get_analytics_warnings() -> dict:
    now = time.monotonic()
    cached = _ANALYTICS_CACHE.get("warnings")
    if cached and now - cached[0] < 1.0:
        return cached[1]
    with RT.lock:
        try:
            from .analytics import get_engine  # type: ignore

            eng = get_engine()
            payload = {
                "tick": RT.sim.tick,
                "famine": eng.famine_horizon(RT.sim),
                "extinction": eng.extinction_cliff(RT.sim),
                "unrest": eng.unrest(RT.sim),
                "casus": eng.casus_belli(RT.sim),
            }
        except Exception as e:
            payload = {"error": str(e)}
    _ANALYTICS_CACHE["warnings"] = (now, payload)
    return payload


def _kin_card(entity_id: int) -> dict:

    """Dossier card for a family-tree node (alive creatures preferred)."""
    seed = RT.sim.config.seed if hasattr(RT.sim, "config") else RT.config.seed
    ent = RT.sim.world.entities.get(entity_id)
    if ent is not None and isinstance(ent, Creature):
        v = variation_for(entity_id, seed)
        return {
            "id": entity_id,
            "caste": ent.caste,
            "alive": True,
            "clan_color": RT.sim.clans.get(ent.clan_id, {}).get("color"),
            "personal_name": personal_name_for(entity_id, seed, ent.generation),
            "glyph": glyph_for(entity_id, seed, ent.generation),
            "hue_shift": v["hue_shift"],
            "scale_jitter": v["scale_jitter"],
            "angle_jitter": v["angle_jitter"],
        }
    # dead or archived — compute deterministic name via genealogy generation if available
    # try DB to get generation
    gen = 0
    if RT.world_id is not None:
        try:
            # quick lookup: genealogy_parents gives child's generation via creatures table
            for tbl in ("creatures",):
                pass
        except Exception:
            pass
    # fallback deterministic with gen 0 (still unique)
    v = variation_for(entity_id, seed)
    return {
        "id": entity_id,
        "caste": None,
        "alive": False,
        "clan_color": None,
        "personal_name": personal_name_for(entity_id, seed, gen),
        "glyph": glyph_for(entity_id, seed, gen),
        "hue_shift": v["hue_shift"],
        "scale_jitter": v["scale_jitter"],
        "angle_jitter": v["angle_jitter"],
    }


@app.get("/api/creature/{creature_id}")
async def get_creature(creature_id: int) -> dict:
    """Live status + personal chronicle + family tree for one creature."""
    # Fast memory snapshot inside lock, DB history outside lock to prevent blocking sim tick
    with RT.lock:
        mem = _creature_mem_dossier(creature_id)
    return _enrich_dossier_from_db(creature_id, mem)


def _creature_mem_dossier(creature_id: int) -> dict:
    ent = RT.sim.world.entities.get(creature_id)
    entity = None
    if ent is not None:
        entity = RT.sim._entity_payload(ent)
        # §BG: enrich dossier with detailed polar morph arrays (for Inspector radar) when available
        try:
            soa = getattr(RT.sim, "_soa", None)
            midx = -1
            if soa is not None and hasattr(soa, "ids"):
                try:
                    import numpy as _npd  # type: ignore
                    if hasattr(soa.ids, "shape"):
                        arrd = soa.ids[: soa.N]  # type: ignore
                        wd = _npd.where(arrd == creature_id)[0]
                        if len(wd):
                            midx = int(wd[0])
                    else:
                        for _jj in range(getattr(soa, "N", 0)):
                            if int(soa.ids[_jj]) == creature_id:  # type: ignore
                                midx = _jj
                                break
                except Exception:
                    midx = -1
            if midx >= 0:
                try:
                    if hasattr(soa, "morph_radii"):
                        k = int(soa.morph_k[midx]) if hasattr(soa, "morph_k") else int(entity.get("sides") or 4)  # type: ignore
                        rr = soa.morph_radii[midx]  # type: ignore
                        pa = soa.morph_angles[midx]  # type: ignore
                        # serialize first k values
                        entity["morph_radii"] = [round(float(rr[i]), 4) for i in range(k)]  # type: ignore
                        entity["morph_angles"] = [round(float(pa[i]), 4) for i in range(k)]  # type: ignore
                        entity["morph_k"] = k
                except Exception:
                    pass
            elif hasattr(RT.sim, "_morph_cache") and creature_id in getattr(RT.sim, "_morph_cache", {}):  # type: ignore
                try:
                    r, a, k = RT.sim._morph_cache[creature_id]  # type: ignore
                    entity["morph_radii"] = [round(float(v), 4) for v in r[:k]]  # type: ignore
                    entity["morph_angles"] = [round(float(v), 4) for v in a[:k]]  # type: ignore
                    entity["morph_k"] = int(k)
                except Exception:
                    pass
            elif hasattr(ent, "_bc_morph_r"):
                try:
                    k = int(getattr(ent, "_bc_morph_k", 4))  # type: ignore
                    entity["morph_radii"] = [round(float(v), 4) for v in getattr(ent, "_bc_morph_r", [])[:k]]  # type: ignore
                    entity["morph_angles"] = [round(float(v), 4) for v in getattr(ent, "_bc_morph_phi", [])[:k]]  # type: ignore
                    entity["morph_k"] = k
                except Exception:
                    pass
            if "morph_radii" not in entity:
                try:
                    from . import evolution_manager as _evo_mgr
                    caste = entity.get("caste") or getattr(ent, "caste", "Gentleman")
                    tr, tphi, tk = _evo_mgr.get_template_for_caste(caste)
                    entity["morph_radii"] = [round(float(v), 4) for v in tr[:tk]]
                    entity["morph_angles"] = [round(float(v), 4) for v in tphi[:tk]]
                    entity["morph_k"] = int(tk)
                except Exception:
                    pass
            # BH-10: full 295-weight genome for Inspector heatmap (detail only)
            if midx >= 0 and hasattr(soa, "genomes"):
                try:
                    g = soa.genomes[midx]  # type: ignore
                    if hasattr(g, "tolist"):
                        entity["nn_genome"] = [round(float(v), 4) for v in g.tolist()]  # type: ignore
                    else:
                        entity["nn_genome"] = [round(float(v), 4) for v in g]  # type: ignore
                    # also include archetype if not already in entity
                    if "archetype" not in entity and hasattr(ent, "_archetype"):
                        entity["archetype"] = getattr(ent, "_archetype", None)  # type: ignore
                except Exception:
                    pass
            elif hasattr(RT.sim, "_nn_cache") and creature_id in getattr(RT.sim, "_nn_cache", {}):  # type: ignore
                try:
                    g = RT.sim._nn_cache[creature_id]  # type: ignore
                    if hasattr(g, "tolist"):
                        entity["nn_genome"] = [round(float(v), 4) for v in g.tolist()]  # type: ignore
                    else:
                        entity["nn_genome"] = [round(float(v), 4) for v in g]  # type: ignore
                except Exception:
                    pass
            elif hasattr(ent, "_nn_genome"):
                try:
                    g = getattr(ent, "_nn_genome", None)  # type: ignore
                    if g is not None:
                        if hasattr(g, "tolist"):
                            entity["nn_genome"] = [round(float(v), 4) for v in g.tolist()]  # type: ignore
                        else:
                            entity["nn_genome"] = [round(float(v), 4) for v in g]  # type: ignore
                except Exception:
                    pass
            # BH-9 archetype from cache (slots fix)
            if entity is not None and entity.get("archetype") is None and hasattr(RT.sim, "_archetype_cache"):
                try:
                    arch = RT.sim._archetype_cache.get(creature_id)  # type: ignore
                    if arch:
                        entity["archetype"] = arch
                except Exception:
                    pass
        except Exception:
            pass

    # Live kin from in-memory creatures
    mother = None
    father = None
    children: dict[int, dict] = {}
    cached = getattr(RT.sim, "_cached_creatures", None)
    all_c = cached if cached is not None else (RT.sim.world.creatures() if hasattr(RT.sim.world, "creatures") else [])
    for other in all_c:
        if other.id != creature_id and creature_id in (other.mother_id, other.father_id):
            children[other.id] = _kin_card(other.id)

    if isinstance(ent, Creature):
        if ent.mother_id:
            mother = _kin_card(ent.mother_id)
        if ent.father_id:
            father = _kin_card(ent.father_id)

    seed = RT.sim.config.seed if hasattr(RT.sim, "config") else RT.config.seed
    clans_dict = dict(getattr(RT.sim, "clans", {}))

    return {
        "entity": entity,
        "mother": mother,
        "father": father,
        "children": children,
        "seed": seed,
        "clans": clans_dict,
    }


def _enrich_dossier_from_db(creature_id: int, mem: dict) -> dict:
    entity = mem["entity"]
    mother = mem["mother"]
    father = mem["father"]
    children = dict(mem["children"])
    seed = mem["seed"]
    clans = mem["clans"]

    if entity is None and RT.world_id is not None:
        try:
            row = DB._require().execute(
                "SELECT caste, clan_id, generation, born_tick FROM creatures WHERE world_id=? AND entity_id=?",
                (RT.world_id, creature_id),
            ).fetchone()
        except Exception:
            row = None
        if row is not None:
            gen = int(row["generation"] or 0)
            clan_id = int(row["clan_id"] or 0)
            v = variation_for(creature_id, seed)
            c_info = clans.get(clan_id, {})
            entity = {
                "id": creature_id,
                "kind": "creature",
                "x": 0.0,
                "y": 0.0,
                "angle": 0.0,
                "caste": row["caste"],
                "clan_id": clan_id or None,
                "clan_color": c_info.get("color") if clan_id else None,
                "clan_name": c_info.get("name") if clan_id else None,
                "clan_totem": c_info.get("totem") if clan_id else None,
                "generation": gen,
                "born_tick": row["born_tick"],
                "personal_name": personal_name_for(creature_id, seed, gen),
                "glyph": glyph_for(creature_id, seed, gen),
                "hue_shift": v["hue_shift"],
                "scale_jitter": v["scale_jitter"],
                "angle_jitter": v["angle_jitter"],
                "sex": "female" if row["caste"] == "Woman" else "male" if row["caste"] else None,
            }
            try:
                from . import evolution_manager as _evo_mgr
                caste = entity.get("caste") or "Gentleman"
                tr, tphi, tk = _evo_mgr.get_template_for_caste(caste)
                entity["morph_radii"] = [round(float(v), 4) for v in tr[:tk]]
                entity["morph_angles"] = [round(float(v), 4) for v in tphi[:tk]]
                entity["morph_k"] = int(tk)
            except Exception:
                pass

    if RT.world_id is not None:
        try:
            gm, gf = DB.genealogy_parents(RT.world_id, creature_id)
            if mother is None and gm:
                mother = {**gm, "alive": False, "clan_color": None}
            if father is None and gf:
                father = {**gf, "alive": False, "clan_color": None}
            for kid in DB.genealogy_children(RT.world_id, creature_id):
                if kid["id"] not in children and kid["id"] != creature_id:
                    children[kid["id"]] = {**kid, "alive": False, "clan_color": None}
        except Exception:
            pass

    events = DB.history(RT.world_id, since_id=0, limit=500, entity_id=creature_id) if RT.world_id else []
    if RT.world_id and DB.pending:
        try:
            pend = DB.pending_events(RT.world_id, limit=500)
            for ev in pend:
                if ev["entity_id"] == creature_id:
                    events.append(ev)
            events = sorted(events, key=lambda e: e.get("tick", 0), reverse=True)[:500]
        except Exception:
            pass
    return {"entity": entity, "events": events, "family": {"mother": mother, "father": father, "children": list(children.values())}}


def _creature_dossier(creature_id: int) -> dict:
    with RT.lock:
        mem = _creature_mem_dossier(creature_id)
    return _enrich_dossier_from_db(creature_id, mem)


def _family_of(creature_id: int) -> dict:
    return _creature_dossier(creature_id).get("family", {"mother": None, "father": None, "children": []})


@app.get("/api/state", response_model=StateMessage)
async def get_state() -> StateMessage:
    with RT.lock:
        return RT.sim.snapshot()


@app.get("/guide", response_class=HTMLResponse)
async def get_guide(request: Request, format: str | None = None, lang: str | None = None):
    """Living guide — merged into /wiki (returns rich wiki HTML or JSON)."""
    if format == "json":
        return JSONResponse(
            {
                "laws": list(GodLaws.model_fields.keys()),
                "routes": [getattr(r, "path", "") for r in app.routes],
            }
        )
    return await get_wiki(request, lang=lang)


@app.get("/wiki", response_class=HTMLResponse)
async def get_wiki(request: Request, lang: str | None = None):
    """Wiki — richer guide with presets, sustainability, playground with i18n (en/vi/fr)."""
    from .wiki_i18n import normalize_lang
    if not lang:
        header = request.headers.get("accept-language", "")
        selected_lang = normalize_lang(header)
    else:
        selected_lang = normalize_lang(lang)

    global _WIKI_CACHE
    if selected_lang in _WIKI_CACHE:
        return HTMLResponse(_WIKI_CACHE[selected_lang])
    from .wiki import build_wiki_html
    html = build_wiki_html(app, lang=selected_lang)
    _WIKI_CACHE[selected_lang] = html
    return HTMLResponse(html)


@app.get("/api/wiki")
async def get_wiki_json(lang: str = "en"):
    """Structured wiki data for frontend Wiki.tsx with i18n support."""
    from .wiki import get_wiki_json as _get
    from .wiki_i18n import normalize_lang

    return _get(app, lang=normalize_lang(lang))


@app.get("/robots.txt", response_class=PlainTextResponse)
async def get_robots_txt():
    """Robots.txt for SEO."""
    return PlainTextResponse(
        "User-agent: *\nAllow: /\nAllow: /wiki\nAllow: /guide\nAllow: /docs\n\nSitemap: https://world.minhnhan.in/sitemap.xml\n",
        media_type="text/plain",
    )


@app.get("/sitemap.xml", response_class=HTMLResponse)
async def get_sitemap_xml():
    """Sitemap.xml for SEO."""
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://world.minhnhan.in/</loc>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>https://world.minhnhan.in/wiki</loc>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>
  <url>
    <loc>https://world.minhnhan.in/guide</loc>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>
  <url>
    <loc>https://world.minhnhan.in/docs</loc>
    <changefreq>monthly</changefreq>
    <priority>0.5</priority>
  </url>
</urlset>"""
    return HTMLResponse(content=xml_content, media_type="application/xml")


@app.get("/docs/god-laws.md", response_class=PlainTextResponse)
async def get_god_laws_md():
    """Serve the markdown docs for god laws — used by wiki + GodPanel hints."""
    candidates = [
        Path("docs/god-laws.md"),
        Path("../docs/god-laws.md"),
        Path(__file__).resolve().parent.parent.parent / "docs" / "god-laws.md",
        Path(__file__).resolve().parent.parent / "public" / "docs" / "god-laws.md",
        Path("frontend/public/docs/god-laws.md"),
        Path("../frontend/public/docs/god-laws.md"),
    ]
    for p in candidates:
        try:
            if p.exists():
                return PlainTextResponse(p.read_text(encoding="utf-8"), media_type="text/markdown; charset=utf-8")
        except Exception:
            continue
    raise HTTPException(404, "god-laws.md not found")


@app.post("/api/control", dependencies=[Depends(require_god)])
async def post_control(msg: ControlMessage) -> dict:
    return await apply_control(msg)
