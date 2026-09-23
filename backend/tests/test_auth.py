"""God passkey auth: first-time enrollment, then every god call needs the key."""

import pytest
from fastapi.testclient import TestClient

from app import main as app_main
from app.auth import PasskeyAuth
from app.config import Config
from app.db import Database
from app.main import RT, app, start_world
from app.simulation import Simulation

KEY = "open-sesame"


@pytest.fixture(autouse=True)
def fresh_runtime():
    RT.config = Config()
    RT.paused = False
    RT.speed = RT.config.tick_rate
    RT.sim = Simulation(RT.config)
    start_world()
    yield


def swap_auth(monkeypatch) -> None:
    """Point the app at a scratch passkey store (fresh DB → not configured).

    Also clears FLATWORLD_GOD_KEY so the scratch store starts unseeded.
    """
    monkeypatch.delenv("FLATWORLD_GOD_KEY", raising=False)
    auth = PasskeyAuth(Database(":memory:"))
    monkeypatch.setattr(app.state, "god_auth", auth)
    monkeypatch.setattr(app_main, "AUTH", auth)


def test_god_calls_rejected_until_passkey_exists(monkeypatch):
    swap_auth(monkeypatch)
    c = TestClient(app)
    assert c.get("/api/auth/status").json() == {"configured": False}

    r = c.post("/api/control", json={"action": "pause"})
    assert r.status_code == 409
    assert r.json()["detail"]["error"] == "god_key_not_configured"
    r = c.post("/api/laws", json={"food_count": 5})
    assert r.status_code == 409
    r = c.post("/api/presets/chaos")
    assert r.status_code == 409


def test_setup_then_key_required(monkeypatch):
    swap_auth(monkeypatch)
    c = TestClient(app)

    # enroll (first time only)
    r = c.post("/api/auth/setup", json={"passkey": KEY})
    assert r.status_code == 200 and r.json()["configured"] is True
    assert c.get("/api/auth/status").json() == {"configured": True}

    # second enrollment refuses
    r = c.post("/api/auth/setup", json={"passkey": "another-key"})
    assert r.status_code == 409

    # too-short passkeys refuse
    r = c.post("/api/auth/setup", json={"passkey": "abc"})
    assert r.status_code == 422

    # without key: 401; wrong key: 401; right key: 200
    r = c.post("/api/control", json={"action": "pause"})
    assert r.status_code == 401
    r = c.post("/api/control", json={"action": "pause"}, headers={"X-God-Key": "wrong"})
    assert r.status_code == 401
    r = c.post(
        "/api/control", json={"action": "pause"}, headers={"X-God-Key": KEY}
    )
    assert r.status_code == 200 and r.json()["paused"] is True

    # laws + presets honour it too
    r = c.post("/api/laws?persist=false", json={"food_count": 5})
    assert r.status_code == 401
    r = c.post(
        "/api/laws?persist=false",
        json={"food_count": 5},
        headers={"X-God-Key": KEY},
    )
    assert r.status_code == 200
    r = c.post("/api/presets/sustainable", headers={"X-God-Key": KEY})
    assert r.status_code == 200


def test_admin_cli_can_reset_and_clear(monkeypatch):
    swap_auth(monkeypatch)
    c = TestClient(app)
    c.post("/api/auth/setup", json={"passkey": KEY})
    auth = app.state.god_auth
    assert auth.configured()

    # admin recovery: overwrite, old key dies, new one works
    auth.reset("fresh-key")
    assert not auth.verify(KEY)
    assert auth.verify("fresh-key")

    # clear returns the world to first-time enrollment
    auth.clear()
    assert not auth.configured()
    assert not auth.verify("fresh-key")
    r = c.post("/api/control", json={"action": "pause"})
    assert r.status_code == 409
    r = c.post("/api/auth/setup", json={"passkey": KEY})
    assert r.status_code == 200


def test_websocket_control_requires_key(monkeypatch):
    swap_auth(monkeypatch)
    c = TestClient(app)
    with c.websocket_connect("/ws") as ws:
        ws.receive_json()  # hello
        ws.receive_json()  # initial state

        ws.send_json({"action": "step"})  # no key
        err = ws.receive_json()
        assert err["type"] == "auth_error"
        assert err["error"] == "god_key_not_configured"

        c.post("/api/auth/setup", json={"passkey": KEY})
        ws.send_json({"action": "step"})  # still no key on this message
        err = ws.receive_json()
        assert err["type"] == "auth_error"
        assert err["error"] == "god_key_required"

        ws.send_json({"action": "step", "key": KEY})
        state = ws.receive_json()
        assert state["type"] == "state" and state["tick"] == 1
