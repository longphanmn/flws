"""§AE Food decay — nothing lasts forever.

Mature plants wither after food_lifespan_ticks × their variant's pace
(sprouts never rot), fertilise nearby soil as they go, and vanish.
Wither events stay in the in-memory chronicle but never reach the DB.
"""

import pytest
from dataclasses import replace

from fastapi.testclient import TestClient

from app.config import Config
from app.entities import Food
from app.main import app, RT, DB
from app.simulation import Simulation


def make_sim(**kw):
    """Simulation with no worldgen flora; keep_foods pins the bounty law to
    exactly the number of test plants added afterwards."""
    keep = kw.pop('keep_foods', 0)
    s = Simulation(decay_cfg(food_count=0, **kw))
    if keep:
        cfg = replace(s.config, food_count=keep)
        s.config = cfg
        s.world.config = cfg
    return s


@pytest.fixture()
def client():
    c = TestClient(app)
    c.headers["X-God-Key"] = "test-key"
    return c


def decay_cfg(**kw) -> Config:
    kw.setdefault("relief_enabled", False)
    zeros = dict(
        seed=5,
        width=60.0,
        height=60.0,
        num_triangles=0, num_squares=0, num_pentagons=0, num_hexagons=0,
        num_priests=0, num_women=0, food_count=0, num_houses=0,
        weather_enabled=False,
        birth_enabled=False,
        predation_enabled=False,
        war_enabled=False,
        disease_enabled=False,
        shelter_enabled=False,
        schism_enabled=False,
        culture_enabled=False,
        age_enabled=False,
        communication_enabled=False,
        knowledge_enabled=False,
        plant_growth_rate=0.0,  # freeze growth so decay is the only clock
        plant_spread_rate=0.0,
    )
    zeros.update(kw)
    return Config(**zeros)


def test_mature_plant_withers_after_its_lifespan():
    s = make_sim(keep_foods=1, food_decay_enabled=True, food_lifespan_ticks=50)
    plant = s.world.add(Food(x=20.0, y=20.0, growth=1.0))  # mature grass

    for _ in range(49):
        s.step()
    assert plant.id in s.world.entities  # still standing one tick before
    assert plant.mature_ticks == 49

    s.step()
    assert plant.id not in s.world.entities  # gone at its lifespan
    withers = [e for e in s.history if e.type == "wither"]
    assert withers and withers[0].entity_id == plant.id


def test_sprouts_and_growing_plants_never_rot():
    s = make_sim(keep_foods=2, food_lifespan_ticks=10)
    sprout = s.world.add(Food(x=20.0, y=20.0, growth=0.15))
    half = s.world.add(Food(x=26.0, y=20.0, growth=0.6))

    for _ in range(60):  # six lifetimes' worth of ticks
        s.step()

    assert sprout.id in s.world.entities  # only the harvest rots
    assert half.id in s.world.entities
    assert sprout.mature_ticks == 0 and half.mature_ticks == 0


def test_variant_pace_mushroom_fades_four_times_faster():
    life = 100
    grass_world = make_sim(keep_foods=1, food_lifespan_ticks=life)
    shroom_world = make_sim(keep_foods=1, food_lifespan_ticks=life)
    g = grass_world.world.add(Food(x=20.0, y=20.0, growth=1.0, variant="grass"))
    m = shroom_world.world.add(Food(x=20.0, y=20.0, growth=1.0, variant="mushroom"))

    for _ in range(int(life * 0.4)):  # mushroom pace: ×0.4
        grass_world.step()
        shroom_world.step()

    assert m.id not in shroom_world.world.entities  # mushroom already withered
    assert g.id in grass_world.world.entities       # grass still going


def test_disabled_law_freezes_decay():
    s = make_sim(keep_foods=1, food_decay_enabled=False, food_lifespan_ticks=10)
    plant = s.world.add(Food(x=20.0, y=20.0, growth=1.0))

    for _ in range(50):
        s.step()

    assert plant.id in s.world.entities  # immortal while the law is off
    assert plant.mature_ticks == 0


def test_withering_feeds_the_soil():
    s = make_sim(keep_foods=3, food_lifespan_ticks=30, nutrient_cycle_rate=1.0)
    doomed = s.world.add(Food(x=20.0, y=20.0, growth=1.0))
    neighbour = s.world.add(Food(x=25.0, y=20.0, growth=0.4))  # within NUTRIENT_RADIUS
    far = s.world.add(Food(x=50.0, y=50.0, growth=0.4))        # far outside it

    for _ in range(31):
        s.step()
    assert doomed.id not in s.world.entities  # withered and vanished

    boost = 0.5 * 0.5 * 1.0  # WITHER_NUTRIENT_MULT × NUTRIENT_BOOST × rate
    assert neighbour.growth == pytest.approx(0.4 + boost)
    assert far.growth == pytest.approx(0.4)  # too far to feel it


def test_wilting_flag_surfaces_near_the_end():
    s = make_sim(keep_foods=1, food_lifespan_ticks=100)
    plant = s.world.add(Food(x=20.0, y=20.0, growth=1.0))

    for _ in range(70):
        s.step()
    payload = s._entity_payload(plant)
    assert "withering" not in payload  # still hearty at 70%

    for _ in range(15):
        s.step()  # past the 80% wilt threshold
    payload = s._entity_payload(plant)
    assert payload.get("withering") is True


def test_wither_events_never_reach_the_db(client, extended_testclient_god_rate_limit):
    # a live world ticking under short lifespans: chronicle keeps withers,
    # the durable events table does not (throttled like blooms)
    r = client.post("/api/laws?persist=false", json={"food_lifespan_ticks": 100})
    assert r.status_code == 200
    for _ in range(130):
        client.post("/api/control", json={"action": "step"})

    live = [e for e in RT.sim.history if e.type == "wither"]
    durable = DB.history(RT.world_id, since_id=0, limit=2000)
    assert live, "withers belong to the in-memory chronicle"
    assert all(e["type"] != "wither" for e in durable), "withers must skip the DB"


def test_food_decay_law_roundtrip(client):
    r = client.post(
        "/api/laws?persist=false",
        json={"food_decay_enabled": False, "food_lifespan_ticks": 4000},
    )
    assert r.status_code == 200
    laws = r.json()
    assert laws["food_decay_enabled"] is False
    assert laws["food_lifespan_ticks"] == 4000
