"""G3/F1 — elder senescence must not be coupled to the global crowding index xi.

The `elder_decay *= 1 + 8*xi + 12*xi^2` term made old-age mortality a function
of the *census* rather than of the individual. Because xi only exists above
0.85*K, an entire elder cohort accumulated under high xi died inside one
compressed window right after a release — the phase-locked old-age burst that
makes gate 4 (burstiness) unreachable. Senescence is a property of the body,
not of the population count.
"""

import pytest

from app.config import Config
from app.entities import Creature
from app.simulation import Simulation


def _cfg(**kw) -> Config:
    """Same isolation envelope the health-core tests use: one lone creature,
    eternal day, no food/houses/war/disease, so health is touched only by the
    senescence and regen branches."""
    zeros = dict(
        num_triangles=0, num_squares=0, num_pentagons=0, num_hexagons=0,
        num_priests=0, num_women=0, food_count=0, num_houses=-1,
        house_density=0.0, day_length=100000, season_length=100000,
        weather_change_rate=0.0, shelter_enabled=False, disease_enabled=False,
        birth_enabled=False, predation_enabled=False, war_enabled=False,
        cannibalism_enabled=False, communication_enabled=False,
        knowledge_enabled=False, schism_enabled=False,
    )
    zeros.update(kw)
    return Config(**zeros)


def _health_after_one_update(xi: float, age: int) -> float:
    """One _update_creature call on a lone creature at a pinned crowding index."""
    sim = Simulation(_cfg())
    c = sim.world.add(
        Creature(
            x=50.0, y=50.0,
            energy=sim.config.energy_max,
            health=50.0,  # well below max_health so regen cannot cap the delta
            age=age, lifespan=1000.0,
        )
    )
    sim._xi_decay_tick = xi
    sim._update_creature(c, [])
    return c.health


def test_elder_mortality_at_fixed_N_is_invariant_to_xi():
    """A step change in xi must not change an elder's one-tick health loss."""
    # guard against a vacuous pass: the elder branch is genuinely live, so an
    # elder ends the tick strictly below an identically-situated adult.
    assert _health_after_one_update(0.0, 800) < _health_after_one_update(0.0, 500)

    baseline = _health_after_one_update(0.0, 800)
    for xi in (0.05, 0.15, 0.30, 0.50, 1.00):
        got = _health_after_one_update(xi, 800)
        assert got == pytest.approx(baseline), (
            f"elder senescence still coupled to xi: xi={xi} -> {got} "
            f"(xi=0 -> {baseline})"
        )
