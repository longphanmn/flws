"""Network clients for the TUI: WebSocket listener + REST helpers.

WSClient keeps a resilient connection to the live /ws feed (auto-reconnect
with capped exponential backoff) and pushes parsed messages into callbacks.
RESTClient wraps the control/observability endpoints via httpx.

Both are transport-only — no backend code is imported.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
from typing import Any, Callable

import httpx
import websockets

from .state import HelloMessage, StateMessage, StateReconstructor


def god_key() -> str | None:
    """Passkey from the environment — the TUI itself never prompts for auth."""
    return os.environ.get("FLATWORLD_GOD_KEY") or None


def http_base_for(ws_url: str) -> str:
    """Derive the REST base from a ws url (ws://host/api-path → http://host)."""
    base = ws_url
    if base.startswith("wss://"):
        base = "https://" + base[len("wss://"):]
    elif base.startswith("ws://"):
        base = "http://" + base[len("ws://"):]
    # strip path suffixes like /api/ws or /ws
    for suffix in ("/api/ws", "/ws"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    return base.rstrip("/")


class WSClient:
    """Resilient /ws listener. Callbacks run on the app's event loop."""

    def __init__(
        self,
        url: str,
        on_hello: Callable[[HelloMessage], Any],
        on_state: Callable[[StateMessage], Any],
        on_status: Callable[[str], Any],
    ) -> None:
        self.url = url
        self.on_hello = on_hello
        self.on_state = on_state
        self.on_status = on_status
        self._ws: Any = None
        self._task: asyncio.Task | None = None
        self._closing = False
        self._reconstructor = StateReconstructor()

    @property
    def connected(self) -> bool:
        return self._ws is not None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._listen(), name="tui-ws")

    async def stop(self) -> None:
        self._closing = True
        if self._ws is not None:
            with contextlib.suppress(Exception):
                await self._ws.close()
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._task
            self._task = None

    async def send(self, payload: dict) -> None:
        """Fire a control action; silently dropped when disconnected."""
        ws = self._ws
        if ws is None:
            return
        key = god_key()
        if key and "key" not in payload:
            payload = {**payload, "key": key}
        try:
            await ws.send(json.dumps(payload))
        except Exception:
            pass

    async def _listen(self) -> None:
        backoff = 1.0
        while not self._closing:
            try:
                self._reconstructor.reset()
                async with websockets.connect(self.url, max_size=2**25) as ws:
                    self._ws = ws
                    backoff = 1.0
                    self.on_status("connected")
                    async for raw in ws:
                        try:
                            msg = json.loads(raw)
                        except (ValueError, TypeError):
                            continue
                        kind = msg.get("type")
                        if kind == "hello":
                            self.on_hello(HelloMessage.from_dict(msg))
                        elif kind == "state":
                            state_msg = self._reconstructor.process_state(msg)
                            self.on_state(state_msg)
                        elif kind == "delta_state":
                            state_msg = self._reconstructor.process_delta(msg)
                            if state_msg is not None:
                                self.on_state(state_msg)
                        elif kind == "auth_error":
                            self.on_status(f"Auth error: {msg.get('error', 'invalid passkey')}")
                    self._ws = None
                    self._reconstructor.reset()
                    self.on_status("server closed connection")
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 — any socket error must reconnect
                self._ws = None
                self._reconstructor.reset()
                if self._closing:
                    break
                reason = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
                self.on_status(f"reconnecting — {reason}")
            if self._closing:
                break
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 8.0)


class RESTClient:
    """Thin httpx wrapper over the Flatland REST API."""

    def __init__(self, base_url: str, transport: httpx.AsyncBaseTransport | None = None) -> None:
        headers = {"X-God-Key": god_key()} if god_key() else {}
        self._client = httpx.AsyncClient(
            base_url=base_url, timeout=5.0, transport=transport, headers=headers
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get(self, path: str, **params: Any) -> Any:
        r = await self._client.get(path, params=params or None)
        r.raise_for_status()
        return r.json()

    async def laws(self) -> dict[str, Any]:
        return await self._get("/api/laws")

    async def set_laws(self, patch: dict[str, Any], persist: bool) -> dict[str, Any]:
        r = await self._client.post("/api/laws", params={"persist": persist}, json=patch)
        if r.status_code == 422:
            detail = r.json().get("detail", "invalid laws")
            raise ValueError(detail)
        r.raise_for_status()
        return r.json()

    async def clans(self) -> dict[str, Any]:
        return await self._get("/api/clans")

    async def clan(self, clan_id: int) -> dict[str, Any]:
        return await self._get(f"/api/clans/{clan_id}")

    async def creature(self, creature_id: int) -> dict[str, Any]:
        return await self._get(f"/api/creature/{creature_id}")

    async def presets(self) -> dict[str, Any]:
        return await self._get("/api/presets")

    async def apply_preset(self, name: str, persist: bool = True, reset: bool = False) -> dict:
        r = await self._client.post(
            f"/api/presets/{name}", params={"persist": persist, "reset": reset}
        )
        r.raise_for_status()
        return r.json()

    async def worlds(self) -> dict[str, Any]:
        return await self._get("/api/worlds")

    async def history(self, since: int = 0, limit: int = 500) -> dict[str, Any]:
        return await self._get("/api/history", since=since, limit=limit)
