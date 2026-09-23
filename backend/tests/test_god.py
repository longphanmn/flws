"""God screen tests: god sets laws of nature, never touches individual creatures."""

import pytest
from fastapi.testclient import TestClient

from dataclasses import replace

from app.config import Config
from app.main import RT, app, start_world
from app.simulation import Simulation


@pytest.fixture(autouse=True)
def fresh_runtime():
    # discard any laws set by earlier tests; ages off so exact food counts hold
    RT.config = replace(Config.from_env(), age_enabled=False)
    RT.paused = False
    RT.speed = RT.config.tick_rate
    RT.sim = Simulation(RT.config)
    start_world()
    yield


@pytest.fixture()
def client():
    # No context manager: lifespan (background tick loop) must NOT run here.
    c = TestClient(app)
    c.headers["X-God-Key"] = "test-key"
    return c


def test_get_laws_returns_current(client):
    laws = client.get("/api/laws").json()
    assert laws["food_count"] == Config.from_env().food_count
    assert laws["boundary"] == "wrap"
    assert laws["energy_decay_per_tick"] == pytest.approx(Config.from_env().energy_decay_per_tick)


def test_god_declares_famine_and_world_follows(client):
    r = client.post("/api/laws", json={"food_count": 5})
    assert r.status_code == 200
    assert r.json()["food_count"] == 5

    client.post("/api/control", json={"action": "step"})
    state = client.get("/api/state").json()
    foods = [e for e in state["entities"] if e["kind"] == "food"]
    assert len(foods) == 5


def test_god_declares_bounty_and_world_follows(client):
    client.post("/api/laws", json={"food_count": 60})
    client.post("/api/control", json={"action": "step"})
    state = client.get("/api/state").json()
    foods = [e for e in state["entities"] if e["kind"] == "food"]
    assert len(foods) == 60


def test_laws_survive_reset(client):
    client.post("/api/laws", json={"perceive_radius": 30.0})
    client.post("/api/control", json={"action": "reset"})
    assert client.get("/api/laws").json()["perceive_radius"] == 30.0
    assert client.get("/api/config").json()["perceive_radius"] == 30.0


def test_invalid_law_rejected(client):
    r = client.post("/api/laws", json={"energy_decay_per_tick": 99})
    assert r.status_code == 422
    # world unchanged
    assert client.get("/api/laws").json()["energy_decay_per_tick"] == pytest.approx(Config().energy_decay_per_tick)


def test_starving_ratio_above_hungry_rejected(client):
    r = client.post("/api/laws", json={"starving_ratio": 0.9, "hungry_ratio": 0.2})
    assert r.status_code == 422


def test_house_max_below_min_rejected(client):
    r = client.post("/api/laws", json={"house_min_size": 10.0, "house_max_size": 5.0})
    assert r.status_code == 422


def test_boundary_law_applies_live(client):
    client.post("/api/laws", json={"boundary": "clamp"})
    assert client.get("/api/config").json()["boundary"] == "clamp"


def test_partial_law_update_keeps_other_laws(client):
    before = client.get("/api/laws").json()
    client.post("/api/laws", json={"eat_radius": 2.5})
    after = client.get("/api/laws").json()
    assert after["eat_radius"] == pytest.approx(2.5)
    for key in ("food_count", "energy_max", "steer_turn"):
        assert after[key] == before[key]


def test_lifespan_mult_law_scales_new_creatures(client):
    client.post("/api/laws", json={"lifespan_mult": 0.5})
    client.post("/api/control", json={"action": "reset"})
    state = client.get("/api/state").json()
    lifespans = {e["lifespan"] for e in state["entities"] if e["kind"] == "creature"}
    # CASTE_LIFESPAN × 0.5 for every caste present in the initial population
    assert lifespans == {2400.0, 2700.0, 3000.0, 3300.0, 3600.0, 4500.0}


def test_deaths_appear_in_history_api(client, extended_testclient_god_rate_limit):
    # famine + fast decay: starvation is inevitable under these laws
    client.post("/api/laws", json={"food_count": 0, "energy_decay_per_tick": 2.0})
    for _ in range(45):
        client.post("/api/control", json={"action": "step"})
    hist = client.get("/api/history").json()
    assert hist["total_deaths"] >= 1
    assert len(hist["events"]) >= 1
    # history now returns newest first (DESC), so last is oldest — check any starvation
    assert any(e.get("cause") == "starvation" and e.get("type") == "death" for e in hist["events"])
    ev = next(e for e in hist["events"] if e.get("cause") == "starvation")
    assert {"tick", "caste", "x", "y"} <= set(ev)


def test_balance_preset_application_and_listing(client):
    presets = client.get("/api/presets").json()
    assert "balance" in presets["presets"]
    r = client.post("/api/presets/balance?persist=true")
    assert r.status_code == 200
    laws = r.json()["laws"]
    assert laws["food_count"] == 380
    assert laws["carrying_capacity"] == 400
    assert laws["max_population"] == 500
    assert laws["predation_enabled"] is True
    assert laws["war_enabled"] is True
    assert laws["disease_enabled"] is True
    assert client.get("/api/presets").json()["current"] == "balance"


def test_post_all_laws_roundtrip_accepts_auto_negative_sentinels(client):
    """Regression: /api/laws crashed with 422 'Input should be greater than or equal to 0'
    when frontend submitted get_laws() containing auto-scaling -1 sentinels."""
    laws = client.get("/api/laws").json()
    assert laws["num_triangles"] == -1
    assert laws["fertile_patches"] == -1
    assert laws["rock_count"] == -1
    # Toggling morphology_annealing_enabled and posting entire laws dictionary should succeed
    laws["morphology_annealing_enabled"] = True
    r = client.post("/api/laws", json=laws)
    assert r.status_code == 200
    res = r.json()
    assert res["morphology_annealing_enabled"] is True


def test_post_laws_with_seed_greater_than_one_billion(client):
    """Regression: /api/laws crashed with 422 'Input should be less than or equal to 1000000000'
    when random seed rolled between 1,000,000,000 and 2**31-1 and frontend submitted laws."""
    laws = client.get("/api/laws").json()
    laws["seed"] = 1_543_210_987
    laws["morphology_annealing_enabled"] = True
    r = client.post("/api/laws", json=laws)
    assert r.status_code == 200
    res = r.json()
    assert res["seed"] == 1_543_210_987
    assert res["morphology_annealing_enabled"] is True


def test_presets_have_morphology_annealing_enabled_by_default():
    """Verify Polar morphology is enabled by default in presets."""
    from app.main import PRESETS
    assert PRESETS["balance"]["morphology_annealing_enabled"] is True
    assert PRESETS["sustainable"]["morphology_annealing_enabled"] is True



