"""Tests for §BQ Continuous Ecosystem Dynamics.

Validates:
- Smooth continuous seasonal solar declination (_smooth_season_food_mult)
- Smooth age multiplier interpolation (_smooth_age_mult)
- Phase desynchronization between seasons (2,400 ticks) and ages (12,000 ticks)
- Smooth carrying capacity and exponential decay damping room
- Rate-limited regrowth flux preventing artificial instant-refill plateaus
- Instant divine decree response on food law alteration
"""

import math
from dataclasses import replace
import pytest
from app.config import Config
from app.simulation.constants import (
    AGE_CAP_MULT,
    AGE_FOOD_MULT,
    _smooth_age_mult,
    _smooth_season_food_mult,
)
from app.simulation.core import Simulation


def test_smooth_season_food_mult_continuity():
    """Verify season food multiplier is strictly continuous with no jump discontinuities."""
    season_len = 2400
    winter_mult = 0.65
    year_len = season_len * 4

    # Equinox at tick 0 should yield 1.0
    mult_0 = _smooth_season_food_mult(0, season_len, winter_mult)
    assert abs(mult_0 - 1.0) < 1e-4

    # Summer peak at tick 2400 should be ~1.20
    mult_summer = _smooth_season_food_mult(season_len, season_len, winter_mult)
    assert mult_summer > 1.14

    # Winter trough at tick 7200 should be ~0.65
    mult_winter = _smooth_season_food_mult(season_len * 3, season_len, winter_mult)
    assert mult_winter < 0.66

    # Test tick-to-tick smoothness across the entire year
    for tick in range(0, year_len, 50):
        m1 = _smooth_season_food_mult(tick, season_len, winter_mult)
        m2 = _smooth_season_food_mult(tick + 1, season_len, winter_mult)
        # Delta per single tick must be smooth (< 0.001 per tick)
        assert abs(m2 - m1) < 0.001

    # Check across boundary wrap (tick year_len - 1 to year_len)
    m_end = _smooth_season_food_mult(year_len - 1, season_len, winter_mult)
    m_start = _smooth_season_food_mult(year_len, season_len, winter_mult)
    assert abs(m_start - m_end) < 0.001


def test_smooth_age_mult_continuity():
    """Verify age food multiplier transitions continuously without sudden step jumps."""
    age_len = 12000

    # Check smoothness across age boundary (e.g. tick 11999 to 12000)
    for boundary_tick in [age_len, 2 * age_len, 3 * age_len]:
        m_before = _smooth_age_mult(boundary_tick - 1, age_len, AGE_FOOD_MULT)
        m_at = _smooth_age_mult(boundary_tick, age_len, AGE_FOOD_MULT)
        m_after = _smooth_age_mult(boundary_tick + 1, age_len, AGE_FOOD_MULT)
        assert abs(m_at - m_before) < 0.001
        assert abs(m_after - m_at) < 0.001


def test_season_age_desynchronization():
    """Verify that season and age cycles are desynchronized (5:1 ratio => 1 season shift per age)."""
    cfg = Config(season_length=2400, age_length=12000)
    sim = Simulation(cfg)

    # Age 0 (Golden) starts at tick 0
    assert sim._age() == "Golden"
    assert sim._season() == "spring"

    # Age 1 (Ice) starts at tick 12000:
    # 12000 / 2400 = 5 seasons elapsed.
    # 5 % 4 = 1 -> "summer" (not spring!)
    sim.tick = 12000
    assert sim._age() == "Ice"
    assert sim._season() == "summer"

    # Age 2 (Chaos) starts at tick 24000:
    # 24000 / 2400 = 10 seasons elapsed.
    # 10 % 4 = 2 -> "autumn"
    sim.tick = 24000
    assert sim._age() == "Chaos"
    assert sim._season() == "autumn"

    # Age 3 (Plague) starts at tick 36000:
    # 36000 / 2400 = 15 seasons elapsed.
    # 15 % 4 = 3 -> "winter"
    sim.tick = 36000
    assert sim._age() == "Plague"
    assert sim._season() == "winter"


def test_smooth_carrying_capacity():
    """Verify carrying capacity changes smoothly between ages."""
    cfg = Config(carrying_capacity=100, age_length=12000)
    sim = Simulation(cfg)

    # Near boundary of Golden -> Ice (tick 11990 to 12010):
    mult_before = _smooth_age_mult(11990, cfg.age_length, AGE_CAP_MULT)
    mult_after = _smooth_age_mult(12010, cfg.age_length, AGE_CAP_MULT)

    cap_before = round(cfg.effective_carrying_capacity * mult_before)
    cap_after = round(cfg.effective_carrying_capacity * mult_after)

    # Capacity should change continuously, not jump discretely
    assert abs(cap_after - cap_before) < 5


def test_rate_limited_food_regrowth():
    """Verify wild food does not instantly refill to 100% in a single tick when heavily grazed."""
    cfg = Config(food_count=100, season_length=2400, age_length=12000, age_enabled=False)
    sim = Simulation(cfg)

    # Let simulation settle initial food
    sim._enforce_food_law()
    initial_foods = [e for e in sim.world.entities.values() if e.kind == "food"]
    assert len(initial_foods) == 100

    # Simulate sudden grazing depletion: remove 40 foods
    for f in initial_foods[:40]:
        sim.world.remove(f.id)

    assert len([e for e in sim.world.entities.values() if e.kind == "food"]) == 60

    # Advance tick by 1; food must not jump straight back to 100
    sim.tick = 1
    sim._enforce_food_law()
    foods_after_1_tick = [e for e in sim.world.entities.values() if e.kind == "food"]
    assert len(foods_after_1_tick) < 70  # Bounded regrowth flux (max ~3 per tick)
    assert len(foods_after_1_tick) > 60  # But positive regrowth


def test_instant_divine_decree_food_law():
    """Verify that when God changes food_count law, the adjustment is immediate."""
    cfg = Config(food_count=100, season_length=2400, age_length=12000, age_enabled=False)
    sim = Simulation(cfg)
    sim._enforce_food_law()
    assert len([e for e in sim.world.entities.values() if e.kind == "food"]) == 100

    # Divine intervention: double food count
    sim.config = replace(sim.config, food_count=200)
    sim.tick = 1
    sim._enforce_food_law()
    assert len([e for e in sim.world.entities.values() if e.kind == "food"]) == 200
