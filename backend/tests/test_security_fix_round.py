import asyncio
import inspect
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, WebSocketDisconnect
from fastapi.testclient import TestClient
from starlette.datastructures import Headers

from app import analytics as analytics_module
from app import auth as auth_module
from app import main as app_main
from app.auth import PasskeyAuth, TokenBucket, require_god
from app.db import Database
from app.main import ALLOWED_ORIGINS, RT, app, start_world


KEY = "fix-round-passkey"
BOOTSTRAP = "fix-round-bootstrap-token"


def _install_auth(monkeypatch, auth, bootstrap=None):
    monkeypatch.setattr(app.state, "god_auth", auth, raising=False)
    monkeypatch.setattr(app_main, "AUTH", auth)
    monkeypatch.setattr(app.state, "bootstrap_token", bootstrap, raising=False)
    return auth


def _request_for(auth, client_ip="198.51.100.25"):
    return app_main.Request(
        {
            "type": "http",
            "app": app,
            "client": (client_ip, 43210),
            "headers": [(b"x-god-key", b"invalid-key")],
            "method": "POST",
            "path": "/api/control",
        }
    )


def test_env_key_is_immutable_setup_authority_for_empty_db(monkeypatch):
    monkeypatch.setenv("FLATWORLD_GOD_KEY", KEY)
    auth = PasskeyAuth(Database(":memory:"))

    assert auth.source == "env"
    with pytest.raises(PermissionError):
        auth.setup("replacement-passkey")
    assert auth.source == "env"
    assert auth.verify(KEY)
    assert not auth.verify("replacement-passkey")


def test_env_key_remains_authority_when_db_is_populated(monkeypatch):
    monkeypatch.delenv("FLATWORLD_GOD_KEY", raising=False)
    db = Database(":memory:")
    PasskeyAuth(db).setup("database-passkey")
    monkeypatch.setenv("FLATWORLD_GOD_KEY", KEY)
    auth = PasskeyAuth(db)

    with pytest.raises(PermissionError):
        auth.setup("replacement-passkey")
    assert auth.source == "env"
    assert auth.verify(KEY)
    assert not auth.verify("database-passkey")


def test_env_backed_setup_returns_409_even_with_bootstrap(monkeypatch):
    monkeypatch.setenv("FLATWORLD_GOD_KEY", KEY)
    _install_auth(monkeypatch, PasskeyAuth(Database(":memory:")), BOOTSTRAP)
    start_world()

    response = TestClient(app).post(
        "/api/auth/setup",
        headers={
            "Origin": "http://localhost:5173",
            "X-Bootstrap-Token": BOOTSTRAP,
        },
        json={"passkey": "replacement-passkey"},
    )
    assert response.status_code == 409


def test_startup_generates_and_logs_bootstrap_token_once(monkeypatch, capsys):
    monkeypatch.delenv("FLATWORLD_GOD_KEY", raising=False)
    monkeypatch.delenv("FLATWORLD_BOOTSTRAP_TOKEN", raising=False)
    _install_auth(monkeypatch, PasskeyAuth(Database(":memory:")))

    app_main._initialize_bootstrap_auth()
    first_output = capsys.readouterr().out
    token = app.state.bootstrap_token
    assert token
    assert first_output.count("FLATWORLD_BOOTSTRAP_TOKEN=") == 1
    assert first_output.split("FLATWORLD_BOOTSTRAP_TOKEN=", 1)[1].splitlines()[0] == token

    app_main._initialize_bootstrap_auth()
    assert capsys.readouterr().out.count("FLATWORLD_BOOTSTRAP_TOKEN=") == 0


def test_operator_bootstrap_token_is_used_when_provided(monkeypatch, capsys):
    monkeypatch.delenv("FLATWORLD_GOD_KEY", raising=False)
    monkeypatch.setenv("FLATWORLD_BOOTSTRAP_TOKEN", BOOTSTRAP)
    _install_auth(monkeypatch, PasskeyAuth(Database(":memory:")))

    app_main._initialize_bootstrap_auth()
    output = capsys.readouterr().out
    assert app.state.bootstrap_token == BOOTSTRAP
    assert output.count(f"FLATWORLD_BOOTSTRAP_TOKEN={BOOTSTRAP}") == 1


def test_startup_does_not_create_bootstrap_for_populated_db(monkeypatch, capsys):
    monkeypatch.delenv("FLATWORLD_GOD_KEY", raising=False)
    monkeypatch.delenv("FLATWORLD_BOOTSTRAP_TOKEN", raising=False)
    auth = PasskeyAuth(Database(":memory:"))
    auth.setup(KEY)
    _install_auth(monkeypatch, auth)

    app_main._initialize_bootstrap_auth()
    assert app.state.bootstrap_token is None
    assert "FLATWORLD_BOOTSTRAP_TOKEN=" not in capsys.readouterr().out


def test_bootstrap_token_is_required_and_single_use(monkeypatch):
    monkeypatch.delenv("FLATWORLD_GOD_KEY", raising=False)
    _install_auth(monkeypatch, PasskeyAuth(Database(":memory:")), BOOTSTRAP)
    start_world()
    client = TestClient(app)
    body = {"passkey": KEY}
    origin = {"Origin": "http://localhost:5173"}

    assert client.post("/api/auth/setup", headers=origin, json=body).status_code == 403

    accepted = client.post(
        "/api/auth/setup",
        headers={**origin, "X-Bootstrap-Token": BOOTSTRAP},
        json=body,
    )
    assert accepted.status_code == 200

    replay = client.post(
        "/api/auth/setup",
        headers={**origin, "X-Bootstrap-Token": BOOTSTRAP},
        json={"passkey": "second-passkey"},
    )
    assert replay.status_code == 403


def test_rate_limit_runs_before_invalid_god_key_verification(monkeypatch):
    calls = 0

    class FakeAuth:
        @staticmethod
        def configured():
            return True

        @staticmethod
        def verify(_key):
            nonlocal calls
            calls += 1
            return False

    _install_auth(monkeypatch, FakeAuth())
    auth_module._RATE_LIMITERS.clear()
    auth_module._RATE_LIMITERS["god_api:198.51.100.25"] = TokenBucket(1, 0)
    request = _request_for(FakeAuth())

    with pytest.raises(HTTPException) as first:
        require_god(request)
    assert first.value.status_code == 401
    assert calls == 1

    with pytest.raises(HTTPException) as limited:
        require_god(request)
    assert limited.value.status_code == 429
    assert calls == 1
    assert not inspect.iscoroutinefunction(require_god)


def test_verify_cache_stores_successes_only(monkeypatch):
    monkeypatch.delenv("FLATWORLD_GOD_KEY", raising=False)
    auth = PasskeyAuth(Database(":memory:"))
    auth.setup(KEY)

    assert not auth.verify("wrong-passkey")
    assert not auth.verify("wrong-passkey")
    assert len(auth._verify_cache) == 0

    assert auth.verify(KEY)
    assert len(auth._verify_cache) == 1


def test_websocket_closes_after_five_auth_failures(monkeypatch):
    monkeypatch.delenv("FLATWORLD_GOD_KEY", raising=False)
    auth = PasskeyAuth(Database(":memory:"))
    auth.setup(KEY)
    _install_auth(monkeypatch, auth)
    start_world()

    with TestClient(app).websocket_connect("/ws") as websocket:
        assert websocket.receive_json()["type"] == "hello"
        assert websocket.receive_json()["type"] == "state"
        for _ in range(4):
            websocket.send_json({"action": "pause", "key": "wrong-passkey"})
            assert websocket.receive_json()["type"] == "auth_error"

        with pytest.raises(WebSocketDisconnect) as closed:
            websocket.send_json({"action": "pause", "key": "wrong-passkey"})
            websocket.receive_json()
        assert closed.value.code == 1008


def test_duplicate_or_comma_origins_are_rejected_http_and_ws(monkeypatch):
    monkeypatch.delenv("FLATWORLD_GOD_KEY", raising=False)
    auth = PasskeyAuth(Database(":memory:"))
    auth.setup(KEY)
    _install_auth(monkeypatch, auth)
    start_world()
    client = TestClient(app)

    duplicate = [
        ("Origin", "http://localhost:5173"),
        ("Origin", "https://evil.example"),
    ]
    response = client.post(
        "/api/control",
        headers=[*duplicate, ("X-God-Key", KEY)],
        json={"action": "pause"},
    )
    assert response.status_code == 403

    get_response = client.get("/healthz", headers=duplicate)
    assert get_response.status_code == 403

    comma = client.post(
        "/api/control",
        headers={
            "Origin": "http://localhost:5173, https://evil.example",
            "X-God-Key": KEY,
        },
        json={"action": "pause"},
    )
    assert comma.status_code == 403



@pytest.mark.anyio
async def test_websocket_rejects_duplicate_origin_headers():
    class DuplicateOriginWebSocket:
        client = SimpleNamespace(host="198.51.100.30", port=50000)
        headers = Headers(
            raw=[
                (b"origin", b"http://localhost:5173"),
                (b"origin", b"https://evil.example"),
            ]
        )
        app = app
        closed = None

        async def close(self, code=1000):
            self.closed = code

    websocket = DuplicateOriginWebSocket()
    await app_main.ws_endpoint(websocket)
    assert websocket.closed == 1008


def test_missing_origin_requires_non_browser_auth(monkeypatch):
    monkeypatch.delenv("FLATWORLD_GOD_KEY", raising=False)
    auth = PasskeyAuth(Database(":memory:"))
    auth.setup(KEY)
    _install_auth(monkeypatch, auth)
    start_world()
    client = TestClient(app)

    denied = client.post("/api/control", json={"action": "pause"})
    assert denied.status_code == 403

    accepted = client.post(
        "/api/control",
        headers={"X-God-Key": KEY},
        json={"action": "pause"},
    )
    assert accepted.status_code == 200


def test_missing_origin_setup_without_bootstrap_is_forbidden(monkeypatch):
    monkeypatch.delenv("FLATWORLD_GOD_KEY", raising=False)
    _install_auth(monkeypatch, PasskeyAuth(Database(":memory:")))
    start_world()

    response = TestClient(app).post("/api/auth/setup", json={"passkey": KEY})
    assert response.status_code == 403


def test_allowed_origin_parser_skips_invalid_entries():
    origins, invalid = app_main.parse_allowed_origins(
        "https://valid.example, javascript:alert(1), http://invalid.example/path"
    )
    assert "https://valid.example" in origins
    assert all(origin in ALLOWED_ORIGINS for origin in origins[: len(ALLOWED_ORIGINS)])
    assert invalid == ["javascript:alert(1)", "http://invalid.example/path"]


def test_trusted_proxy_client_ip_uses_rightmost_untrusted_xff(monkeypatch):
    monkeypatch.setenv("FLATWORLD_TRUSTED_PROXIES", "10.0.0.0/8,192.0.2.7")
    assert (
        auth_module.client_ip_from_headers(
            "10.1.2.3", "198.51.100.9, 192.0.2.7"
        )
        == "198.51.100.9"
    )
    assert (
        auth_module.client_ip_from_headers("203.0.113.4", "198.51.100.9")
        == "203.0.113.4"
    )


def test_privileged_diagnostics_require_key_even_on_loopback(monkeypatch):
    monkeypatch.delenv("FLATWORLD_GOD_KEY", raising=False)
    auth = PasskeyAuth(Database(":memory:"))
    auth.setup(KEY)
    _install_auth(monkeypatch, auth)
    start_world()
    client = TestClient(app)

    no_key = client.get("/api/perf/telemetry")
    assert no_key.json()["proc_cores"] == []
    with_key = client.get(
        "/api/perf/telemetry", headers={"X-God-Key": KEY}
    )
    assert with_key.status_code == 200


class _RaceWebSocket:
    def __init__(self, peer, release, accepted):
        self.client = SimpleNamespace(host=peer, port=50000)
        self.headers = Headers({})
        self.app = app
        self._release = release
        self._accepted = accepted
        self.accepted = False
        self.closed = None

    async def accept(self):
        self.accepted = True
        self._accepted.append(self)
        await self._release.wait()

    async def send_text(self, _text):
        return None

    async def send_json(self, _payload):
        return None

    async def receive_json(self):
        raise WebSocketDisconnect(code=1000)

    async def close(self, code=1000):
        self.closed = code


@pytest.mark.anyio
async def test_concurrent_websocket_connections_respect_global_cap(monkeypatch):
    accepted = []
    release = asyncio.Event()
    sockets = [
        _RaceWebSocket(f"198.51.100.{index + 1}", release, accepted)
        for index in range(5)
    ]
    monkeypatch.setattr(app_main, "MAX_GLOBAL_WS_CLIENTS", 2)
    monkeypatch.setattr(app_main, "MAX_CLIENT_WS_CONNECTIONS", 10)
    monkeypatch.setattr(app_main, "MAX_WS_AUTH_FAILURES", 5)
    app_main.HUB.clients.clear()
    app_main._WS_GLOBAL_RESERVED = 0

    tasks = [asyncio.create_task(app_main.ws_endpoint(socket)) for socket in sockets]
    await asyncio.sleep(0)
    release.set()
    await asyncio.gather(*tasks)

    assert len([socket for socket in sockets if socket.accepted]) <= 2
    assert len(app_main.HUB.clients) <= 2
    assert all(socket.closed == 1008 for socket in sockets if not socket.accepted)
    assert app_main._WS_GLOBAL_RESERVED == 0


def test_analytics_summary_does_not_expose_engine_exception(monkeypatch):
    engine = analytics_module.get_engine(fresh=True)

    def fail_snapshot():
        raise RuntimeError("analytics-private-exception-marker")

    monkeypatch.setattr(engine.ring, "snapshot", fail_snapshot)
    app_main._ANALYTICS_CACHE.clear()

    response = TestClient(app).get("/api/analytics/summary")
    assert response.status_code == 200
    assert response.json()["error"] == "analytics_unavailable"
    assert "analytics-private-exception-marker" not in response.text


def test_analytics_outer_handler_whitelists_engine_payload(monkeypatch):
    engine = analytics_module.get_engine(fresh=True)
    monkeypatch.setattr(
        engine,
        "summary",
        lambda _sim: {
            "tick": RT.sim.tick,
            "ring": {"safe": True},
            "detail": "analytics-private-detail-marker",
        },
    )
    app_main._ANALYTICS_CACHE.clear()

    body = TestClient(app).get("/api/analytics/summary").json()
    assert body["ring"] == {"safe": True}
    assert "detail" not in body
    assert "analytics-private-detail-marker" not in json.dumps(body)


def test_openapi_has_no_developer_metadata():
    response = TestClient(app).get("/openapi.json")
    assert response.status_code == 200
    assert "@" not in response.text
    assert "Long Phan" not in response.text
    assert "contact" not in response.json()["info"]
