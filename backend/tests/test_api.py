"""API tests: REST endpoints and WebSocket protocol (sim loop not running)."""

import asyncio
import threading
import time

import pytest
from fastapi.testclient import TestClient

from app.config import Config
from app.main import DB, RT, SimEngine, RuntimeState, app, start_world
from app.simulation import Simulation


@pytest.fixture(autouse=True)
def fresh_runtime():
    RT.config = Config.from_env()  # discard any laws set by earlier tests
    RT.paused = False
    RT.speed = RT.config.tick_rate
    RT.sim = Simulation(RT.config)
    start_world()  # fresh DB world row per test
    yield


@pytest.fixture()
def client():
    # No context manager: lifespan (background tick loop) must NOT run here.
    c = TestClient(app)
    c.headers["X-God-Key"] = "test-key"
    return c


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert "tick" in body and "paused" in body


def test_get_config(client):
    cfg = client.get("/api/config").json()
    assert cfg["width"] > 0
    assert cfg["boundary"] in ("wrap", "clamp")
    assert "seed" in cfg


def test_state_and_control_flow(client):
    st = client.get("/api/state").json()
    assert st["type"] == "state"
    assert st["tick"] == 0

    r = client.post("/api/control", json={"action": "pause"})
    assert r.json()["paused"] is True

    r = client.post("/api/control", json={"action": "step"})
    assert r.json()["tick"] == 1

    r = client.post("/api/control", json={"action": "set_speed", "value": 25})
    assert r.json()["speed"] == 25

    r = client.post("/api/control", json={"action": "reset"})
    assert r.json()["tick"] == 0

    st = client.get("/api/state").json()
    assert st["tick"] == 0


def test_sim_engine_ticks_on_its_own_thread_and_lock_guards_reads():
    """The threaded engine advances the world while readers stay consistent."""
    rt = RuntimeState(Config(seed=5, num_houses=2))
    hub = __import__("app.main", fromlist=["Hub"]).Hub()
    engine = SimEngine(rt, hub)
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    try:
        engine.start(loop=loop)
        deadline = time.monotonic() + 5.0
        while rt.sim.tick < 5 and time.monotonic() < deadline:
            time.sleep(0.01)
        assert rt.sim.tick >= 5

        # a reader holding the lock sees an integral snapshot
        with rt.lock:
            snap = rt.sim.snapshot()
        assert snap.tick == rt.sim.tick

        # pause is honoured by the engine thread
        rt.paused = True
        frozen = rt.sim.tick
        time.sleep(0.2)
        assert rt.sim.tick == frozen
        rt.paused = False
    finally:
        engine.stop()
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=1)


def test_websocket_hello_then_state_then_step(client):
    with client.websocket_connect("/ws") as ws:
        hello = ws.receive_json()
        assert hello["type"] == "hello"
        assert hello["width"] == RT.config.width

        state = ws.receive_json()
        assert state["type"] == "state"
        assert state["tick"] == 0

        ws.send_json({"action": "pause", "key": "test-key"})
        ws.send_json({"action": "step", "key": "test-key"})
        state2 = ws.receive_json()
        assert state2["tick"] == 1

        ws.send_json({"action": "reset", "key": "test-key"})
        state3 = ws.receive_json()
        assert state3["tick"] == 0


def test_websocket_initial_message_always_state_not_delta(client):
    """Ensure connecting clients always receive a full state message, even if delta_state was cached."""
    RT._cached_state_text = '{"type":"delta_state","tick":0,"creatures_alive":10}'
    with client.websocket_connect("/ws") as ws:
        hello = ws.receive_json()
        assert hello["type"] == "hello"
        state = ws.receive_json()
        assert state["type"] == "state"
        assert state["tick"] == 0


def test_presets_list_and_apply_all(client):
    """Verify all presets are exposed and can be applied cleanly."""
    r = client.get("/api/presets")
    assert r.status_code == 200
    presets = r.json()["presets"]
    assert "sustainable" in presets
    assert "chaos" in presets
    assert "extinction" in presets
    assert "boom" in presets

    for name in presets:
        resp = client.post(f"/api/presets/{name}?reset=true")
        assert resp.status_code == 200
        data = resp.json()
        assert data["preset"] == name
        assert data["reset"] is True
        assert RT.sim.tick == 0


def test_history_filtering(client):
    """Verify /api/history accepts type and entity_id filters."""
    # Step simulation to generate events
    for _ in range(5):
        RT.sim.step()
    DB.flush()

    res_all = client.get("/api/history")
    assert res_all.status_code == 200
    all_events = res_all.json()["events"]

    # Filter by specific type
    res_births = client.get("/api/history?type=birth")
    assert res_births.status_code == 200
    birth_events = res_births.json()["events"]
    assert all(e["type"] == "birth" for e in birth_events)

    # Filter by specific entity_id
    if all_events:
        eid = all_events[0]["entity_id"]
        res_entity = client.get(f"/api/history?entity_id={eid}")
        assert res_entity.status_code == 200
        entity_events = res_entity.json()["events"]
        assert all(e["entity_id"] == eid for e in entity_events)


def test_wiki_json_and_html(client):
    """Verify /wiki HTML and /api/wiki JSON return valid structured data with laws, routes, presets and i18n."""
    # English default
    r_html = client.get("/wiki")
    assert r_html.status_code == 200
    assert "Flatland" in r_html.text
    assert "Overview" in r_html.text
    assert "genome-mirror" in r_html.text

    # Vietnamese via query param
    r_vi = client.get("/wiki?lang=vi")
    assert r_vi.status_code == 200
    assert "Bách khoa toàn thư Flatland" in r_vi.text
    assert "Tổng quan" in r_vi.text

    # French via query param
    r_fr = client.get("/wiki?lang=fr")
    assert r_fr.status_code == 200
    assert "Encyclopédie Flatland" in r_fr.text
    assert "Aperçu" in r_fr.text

    # Accept-Language header detection
    r_hdr_vi = client.get("/wiki", headers={"Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8"})
    assert r_hdr_vi.status_code == 200
    assert "Bách khoa toàn thư Flatland" in r_hdr_vi.text

    r_hdr_fr = client.get("/wiki", headers={"Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8"})
    assert r_hdr_fr.status_code == 200
    assert "Encyclopédie Flatland" in r_hdr_fr.text

    # English API JSON
    r_json = client.get("/api/wiki")
    assert r_json.status_code == 200
    data = r_json.json()
    assert data["lang"] == "en"
    assert "genome_mirror" in data and len(data["genome_mirror"]) > 100
    assert "laws" in data and len(data["laws"]) > 50
    assert "routes" in data and len(data["routes"]) > 10
    assert "presets" in data and len(data["presets"]) >= 7
    assert "law_details" in data and len(data["law_details"]) > 50
    assert "balance" in data["presets"]
    assert "safeguard_enabled" in data["laws"]
    assert "soft_cap_enabled" in data["laws"]

    # Vietnamese API JSON
    r_json_vi = client.get("/api/wiki?lang=vi")
    assert r_json_vi.status_code == 200
    data_vi = r_json_vi.json()
    assert data_vi["lang"] == "vi"
    assert "Bách khoa toàn thư" in data_vi["overview"]
    assert "thực ăn" in data_vi["law_details"]["food_count"]["hint"] or "thức ăn" in data_vi["law_details"]["food_count"]["hint"]
    assert "Nguyên lý vận hành" in data_vi["how_it_works"]
    assert "Cấu hình & Vận hành" in data_vi["config_ops"]
    assert "Bản đồ mã nguồn" in data_vi["codebase_map"]
    assert "Mô hình dữ liệu" in data_vi["data_model"]

    # French API JSON
    r_json_fr = client.get("/api/wiki?lang=fr")
    assert r_json_fr.status_code == 200
    data_fr = r_json_fr.json()
    assert data_fr["lang"] == "fr"
    assert "Encyclopédie" in data_fr["overview"]
    assert "nourricières" in data_fr["law_details"]["food_count"]["hint"]
    assert "Fonctionnement du monde" in data_fr["how_it_works"]
    assert "Configuration & Exploitation" in data_fr["config_ops"]
    assert "Carte du code source" in data_fr["codebase_map"]
    assert "Modèle de données" in data_fr["data_model"]




