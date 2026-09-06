"""Tests for Safeguard sex extinction recovery and clan re-founding."""

import pytest
from app.config import Config
from app.entities import Creature, House
from app.safeguard_engine import SafeguardEngine, compute_eta, tier_for_eta
from app.simulation import Simulation


def test_safeguard_engine_sex_extinct():
    cfg = Config(carrying_capacity=350, safeguard_critical_pop=12, safeguard_enabled=True)
    engine = SafeguardEngine(cfg)

    # When sex_extinct is False and N=16 > 12, tier is 2 (emergency relief)
    eta, tier, _ = engine.update(16, 10, sex_extinct=False)
    assert tier == 2
    assert not engine.should_genesis(16, sex_extinct=False)

    # When sex_extinct is True (e.g. all females dead), tier must be 3 (Genesis Miracle)
    eta, tier, _ = engine.update(16, 10, sex_extinct=True)
    assert tier == 3
    assert engine.should_genesis(16, sex_extinct=True)


def test_simulation_recovers_when_miracle_succeeds(monkeypatch):
    import app.simulation
    monkeypatch.setattr(app.simulation, "_IS_TEST", False)

    cfg = Config(
        seed=123,
        width=60.0,
        height=60.0,
        safeguard_enabled=True,
        safeguard_critical_pop=12,
        safeguard_genesis_batch=6,
        safeguard_max_miracles=1,
        birth_enabled=True,
        adult_age=350.0,
        mate_radius=30.0,
        mate_energy_min=10.0,
        birth_rate=0.8,
        energy_start=90.0,
        food_count=30,
        num_triangles=0,
        num_squares=0,
        num_pentagons=0,
        num_hexagons=0,
        num_priests=0,
        num_women=0,
        num_houses=0,
    )
    sim = Simulation(cfg)

    # Clear everything
    for e in list(sim.world.entities.values()):
        sim.world.remove(e.id)
    sim.clans.clear()

    # Add 2 functional houses
    for i in range(2):
        sim.world.add(House(x=20.0 + i * 20.0, y=30.0, size=7.0, door_width=3.0, door_side="north"))

    # Add 16 all-male clanless creatures near the houses
    for i in range(16):
        sim.world.add(
            Creature(
                shape="polygon",
                sides=4,
                x=25.0 + (i % 4) * 2.0,
                y=30.0 + (i // 4) * 2.0,
                energy=80.0,
                age=400,
                lifespan=5000,
                clan_id=0,
                generation=60,
            )
        )

    # Confirm starting state: 16 creatures, 0 females, 0 clans
    assert len(sim.world.creatures()) == 16
    assert sum(1 for c in sim.world.creatures() if c.shape == "line") == 0
    assert len(sim.clans) == 0

    # Step simulation across safeguard checks (10 ticks) and settlement checks (50 ticks)
    for _ in range(60):
        sim.step()

    # 1. Clans must be re-founded
    assert len(sim.clans) > 0, "Clans must be re-founded when surviving creatures have no clans"

    # 2. Females must have been spawned by Genesis Miracle
    females = [c for c in sim.world.creatures() if c.shape == "line"]
    assert len(females) > 0, "Females must be spawned to rescue the world from sex extinction"

    # 3. Genesis creatures must inherit world generation
    assert any(c.generation >= 60 for c in females), "Genesis creatures must inherit world generation"

    # 4. Exactly 1 miracle should have fired
    assert sim._safeguard.miracles == 1, "Safeguard must fire at most 1 miracle"


def test_simulation_single_miracle_then_allows_extinction(monkeypatch):
    import app.simulation
    monkeypatch.setattr(app.simulation, "_IS_TEST", False)

    cfg = Config(
        seed=42,
        width=60.0,
        height=60.0,
        safeguard_enabled=True,
        safeguard_critical_pop=12,
        safeguard_genesis_batch=6,
        safeguard_max_miracles=1,
        num_triangles=0,
        num_squares=0,
        num_pentagons=0,
        num_hexagons=0,
        num_priests=0,
        num_women=0,
        num_houses=0,
    )
    sim = Simulation(cfg)
    for e in list(sim.world.entities.values()):
        sim.world.remove(e.id)
    sim.clans.clear()

    # 16 creatures with 0 females triggers the 1 allowed miracle
    for i in range(16):
        sim.world.add(Creature(shape="polygon", sides=4, x=30.0, y=30.0, energy=80.0, age=400, lifespan=5000))

    # Trigger first miracle at tick 10
    for _ in range(15):
        sim.step()

    assert sim._safeguard.miracles == 1
    assert len(sim.world.creatures()) == 22

    # Now assume the miracle fails: disaster / disease / starvation wipes out all creatures
    for c in list(sim.world.creatures()):
        sim.world.remove(c.id)
    sim._refresh_cache()
    assert len(sim.world.creatures()) == 0

    # Advance 30 ticks: safeguard must NOT intervene again; world remains extinct
    for _ in range(30):
        sim.step()

    assert sim._safeguard.miracles == 1, "Miracles must not exceed max_miracles=1"
    assert len(sim.world.creatures()) == 0, "World must be allowed to go extinct when safeguard fails"


def test_safeguard_and_softcap_active_flags(monkeypatch):
    import app.simulation
    monkeypatch.setattr(app.simulation, "_IS_TEST", False)

    cfg = Config(
        seed=999,
        carrying_capacity=50,
        safeguard_relief_ratio=0.30,  # Ksafe = 15
        safeguard_critical_pop=5,
        safeguard_enabled=True,
        soft_cap_enabled=True,
        num_triangles=0,
        num_squares=0,
        num_pentagons=0,
        num_hexagons=0,
        num_priests=0,
        num_women=0,
        num_houses=0,
    )
    sim = Simulation(cfg)
    for e in list(sim.world.entities.values()):
        sim.world.remove(e.id)
    sim._refresh_cache()

    # 1. Extinct: neither should be active
    snap = sim.snapshot_payload()
    assert snap["safeguard_active"] is False
    assert snap["softcap_active"] is False

    # 2. Low population (N = 10 < Ksafe = 15): safeguard active, softcap inactive
    for i in range(10):
        shape = "line" if i % 2 == 0 else "polygon"
        sides = 2 if shape == "line" else 4
        sim.world.add(Creature(shape=shape, sides=sides, x=20.0, y=20.0, energy=80.0, age=100, lifespan=1000))
    sim.step()
    snap = sim.snapshot_payload()
    delta = sim.snapshot_delta_payload()
    assert snap["safeguard_active"] is True
    assert snap["softcap_active"] is False
    assert delta["safeguard_active"] is True
    assert delta["softcap_active"] is False

    # 3. Normal population (N = 30, between Ksafe=15 and Kcap=50): neither active
    for i in range(20):
        shape = "line" if i % 2 == 0 else "polygon"
        sides = 2 if shape == "line" else 4
        sim.world.add(Creature(shape=shape, sides=sides, x=25.0, y=25.0, energy=80.0, age=100, lifespan=1000))
    for _ in range(10):
        sim.step()
    snap = sim.snapshot_payload()
    assert snap["safeguard_active"] is False
    assert snap["softcap_active"] is False

    # 4. Overpopulation (N = 60 > Kcap = 50): softcap active, safeguard inactive
    for i in range(30):
        shape = "line" if i % 2 == 0 else "polygon"
        sides = 2 if shape == "line" else 4
        sim.world.add(Creature(shape=shape, sides=sides, x=30.0, y=30.0, energy=80.0, age=100, lifespan=1000))
    sim.step()
    snap = sim.snapshot_payload()
    delta = sim.snapshot_delta_payload()
    assert snap["safeguard_active"] is False
    assert snap["softcap_active"] is True
    assert delta["safeguard_active"] is False
    assert delta["softcap_active"] is True

