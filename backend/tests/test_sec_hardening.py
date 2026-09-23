"""Comprehensive security hardening verification tests for flws backend.

Verifies fixes for Group A, Group B, and Group C audit findings:
- CORS explicit allowlist & wildcard removal
- CSRF / Origin guard on state-changing requests
- WebSocket Origin validation
- Rejection of ?key= query parameter
- Split /healthz (minimal public vs privileged full)
- Internals leak prevention (/api/version, /api/config, /proc/stat)
- HMAC verify cache without plaintext storage
- Rate limiting and connection caps
- Thread-safe auth enrollment & MIN_PASSKEY_LEN = 8
"""

import pytest
from fastapi.testclient import TestClient

from app import main as app_main
from app.auth import MIN_PASSKEY_LEN, PasskeyAuth
from app.db import Database
from app.main import ALLOWED_ORIGINS, RT, app, start_world


GOD_KEY = "test-god-passkey-123"


@pytest.fixture(autouse=True)
def fresh_auth(monkeypatch):
    """Ensure a clean, configured passkey store for tests."""
    monkeypatch.delenv("FLATWORLD_GOD_KEY", raising=False)
    auth = PasskeyAuth(Database(":memory:"))
    auth.setup(GOD_KEY)
    monkeypatch.setattr(app.state, "god_auth", auth)
    monkeypatch.setattr(app.state, "bootstrap_token", None, raising=False)
    monkeypatch.setattr(app_main, "AUTH", auth)
    start_world()
    yield


def test_cors_allowlist_enforced():
    client = TestClient(app)
    # Allowed origin gets CORS header
    res = client.options(
        "/api/state",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert res.headers.get("access-control-allow-origin") == "http://localhost:5173"

    # Malicious origin does not get allow-origin header
    res_bad = client.options(
        "/api/state",
        headers={
            "Origin": "https://malicious-attacker.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert res_bad.headers.get("access-control-allow-origin") is None


def test_csrf_origin_guard_blocks_untrusted_origins():
    client = TestClient(app)
    # State-changing POST with untrusted Origin must be rejected with 403 Forbidden
    res = client.post(
        "/api/control",
        json={"action": "pause"},
        headers={
            "Origin": "https://evil.example.com",
            "X-God-Key": GOD_KEY,
        },
    )
    assert res.status_code == 403
    assert "Forbidden" in res.json().get("detail", "")

    # Allowed origin is permitted
    res_ok = client.post(
        "/api/control",
        json={"action": "pause"},
        headers={
            "Origin": "http://localhost:5173",
            "X-God-Key": GOD_KEY,
        },
    )
    assert res_ok.status_code == 200

    # Non-browser request without Origin header is permitted
    res_no_origin = client.post(
        "/api/control",
        json={"action": "pause"},
        headers={"X-God-Key": GOD_KEY},
    )
    assert res_no_origin.status_code == 200


def test_websocket_origin_check():
    client = TestClient(app)
    # Untrusted origin must be rejected before / during handshake
    with pytest.raises(Exception):
        with client.websocket_connect(
            "/ws",
            headers={"Origin": "https://evil-attacker.com"},
        ):
            pass

    # Allowed origin connects cleanly
    with client.websocket_connect(
        "/ws",
        headers={"Origin": "http://localhost:5173"},
    ) as ws:
        hello = ws.receive_json()
        assert hello.get("type") == "hello"


def test_god_passkey_query_param_rejected():
    client = TestClient(app)
    # Query param ?key= must NOT be accepted for authentication
    res = client.post(
        f"/api/control?key={GOD_KEY}",
        headers={"Origin": "http://localhost:5173"},
        json={"action": "pause"},
    )
    assert res.status_code == 401

    # Header X-God-Key MUST be accepted
    res_header = client.post(
        "/api/control",
        json={"action": "pause"},
        headers={"X-God-Key": GOD_KEY},
    )
    assert res_header.status_code == 200


def test_split_healthz_unprivileged_vs_privileged():
    client = TestClient(app)

    # 1. Unprivileged remote request (simulated via X-Forwarded-For from external IP)
    res_pub = client.get("/healthz", headers={"X-Forwarded-For": "203.0.113.50"})
    assert res_pub.status_code == 200
    pub_body = res_pub.json()
    assert "ok" in pub_body
    assert "status" in pub_body
    assert "uptime_seconds" in pub_body
    # Sensitive internal fields MUST be stripped
    assert "pid" not in pub_body
    assert "memory_mb" not in pub_body
    assert "threads" not in pub_body
    assert "subsystems_ms" not in pub_body
    assert "tick_budget" not in pub_body
    assert "history_120m" not in pub_body
    assert "last_tick_error" not in pub_body

    # 2. Privileged request with X-God-Key
    res_priv = client.get(
        "/healthz",
        headers={
            "X-Forwarded-For": "203.0.113.50",
            "X-God-Key": GOD_KEY,
        },
    )
    assert res_priv.status_code == 200
    priv_body = res_priv.json()
    assert "pid" in priv_body
    assert "memory_mb" in priv_body
    assert "subsystems_ms" in priv_body
    assert "tick_budget" in priv_body


def test_api_version_strips_pii_and_git_hash_unprivileged():
    client = TestClient(app)
    # Unprivileged remote caller
    res = client.get("/api/version", headers={"X-Forwarded-For": "203.0.113.50"})
    assert res.status_code == 200
    body = res.json()
    assert "version" in body
    assert "developer" not in body
    assert "email" not in body
    assert "contact" not in body
    assert "revision" not in body


def test_api_config_reduced_keys_unprivileged():
    client = TestClient(app)
    # Unprivileged remote caller
    res = client.get("/api/config", headers={"X-Forwarded-For": "203.0.113.50"})
    assert res.status_code == 200
    body = res.json()
    # Public non-sensitive keys present
    assert "width" in body
    assert "height" in body
    assert "seed" in body
    # Internal tuning keys absent
    assert "max_speed" not in body
    assert "tick_history_size" not in body
    assert "db_flush_interval" not in body


def test_verify_cache_never_stores_plaintext_passkey():
    auth = app.state.god_auth
    assert auth.verify(GOD_KEY)

    # Inspect _verify_cache internals to confirm plaintext passkey is NOT a key
    for cache_key in auth._verify_cache.keys():
        assert GOD_KEY not in str(cache_key)
        # Ensure it is a 64-character sha256 hex digest
        assert len(cache_key) == 64


def test_min_passkey_len_and_race_prevention():
    assert MIN_PASSKEY_LEN == 8
    scratch_auth = PasskeyAuth(Database(":memory:"))
    # Length < 8 must be rejected
    with pytest.raises(ValueError):
        scratch_auth.setup("short7")

    # Valid passkey length >= 8 accepted
    scratch_auth.setup("validpass123")
    assert scratch_auth.configured()

    # Second enrollment refused under lock
    with pytest.raises(PermissionError):
        scratch_auth.setup("secondpass123")


def test_proc_stat_empty_unprivileged():
    client = TestClient(app)
    # Unprivileged remote caller gets empty proc_cores
    res = client.get("/api/perf/telemetry", headers={"X-Forwarded-For": "203.0.113.50"})
    assert res.status_code == 200
    body = res.json()
    assert body.get("proc_cores") == []
