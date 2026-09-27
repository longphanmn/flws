"""Phase 2 G1 — a hard population envelope, inert until switched on.

A proportional band cannot make the 300-tick smoothed series flat: it always has
a restoring force proportional to displacement, so the population keeps drifting
across it and the reversals gate keeps counting sign flips. The gates instead
require *absorbing* boundaries:

    births hard-vetoed above  K*pop_env_hi_frac
    mortality floored below  K*pop_env_lo_frac

so inside the band the dynamics still run but the boundaries do not leak. The
whole law is behind `population_envelope_enabled`, which defaults to False, so
with the flag unset this file must be a no-op on the simulation — including on
the RNG stream, or the golden determinism lock would move for a disabled law.

Both edges act on *births*, and neither can kill: the ceiling vetoes, the floor
lifts. A lower edge that killed creatures would be an inverted boundary —
imposing deaths on an already-deficient population drives it further down, a
positive feedback away from the band rather than a reflection back into it.
"""

import pytest

from app.config import Config
from app.density_damping import envelope_lower_boost, population_envelope
from app.entities import Creature
from app.simulation import Simulation

ENV_KEYS = (
    "population_envelope_enabled", "pop_env_lo_frac", "pop_env_hi_frac",
    "pop_env_lo_birth_boost",
)


def _cfg(**kw) -> Config:
    """Plenty of food, no war/disease/predation: the only mortality that can act
    is the envelope floor, so a death here is unambiguous evidence."""
    zeros = dict(
        num_triangles=0, num_squares=0, num_pentagons=0, num_hexagons=0,
        num_priests=0, num_women=0, num_houses=-1, house_density=0.0,
        food_count=400, plant_growth_rate=0.05, plant_spread_rate=0.01,
        day_length=100000, season_length=100000, weather_change_rate=0.0,
        shelter_enabled=False, disease_enabled=False, predation_enabled=False,
        war_enabled=False, cannibalism_enabled=False, communication_enabled=False,
        knowledge_enabled=False, schism_enabled=False, corpses_enabled=False,
        birth_enabled=True, age_enabled=False, relief_enabled=False,
        adult_age=1, birth_rate=1.0, reproduction_cooldown=1,
        mate_energy_min=1.0, boom_ramp_days=0.0, safeguard_enabled=False,
        soft_cap_enabled=False, omp_enabled=False,
    )
    zeros.update(kw)
    return Config(**zeros)


# --- the law is off by default and inert -----------------------------------


def test_envelope_flags_exist_with_documented_defaults():
    fields = Config.__dataclass_fields__
    for key in ENV_KEYS:
        assert key in fields, f"{key} is not a Config field"
    assert Config().population_envelope_enabled is False
    assert Config().pop_env_lo_frac == pytest.approx(0.96)
    assert Config().pop_env_hi_frac == pytest.approx(1.04)


def test_envelope_is_inert_when_disabled():
    cfg = _cfg(carrying_capacity=100)
    assert population_envelope(cfg) is None
    assert population_envelope(cfg) is None


def test_envelope_is_inert_on_the_rng_stream_when_disabled():
    """A disabled law must not consume a single random draw, or it moves the
    golden hashes and quietly changes every recorded run."""
    on = _cfg(population_envelope_enabled=False, carrying_capacity=6)
    off = _cfg(carrying_capacity=6)
    assert on == off

    def trace(cfg):
        sim = Simulation(cfg)
        for _ in range(12):
            sim.step()
        return sorted(
            (c.id, round(c.x, 6), round(c.y, 6), round(c.energy, 6))
            for c in sim._cached_creatures
        )

    assert trace(on) == trace(off)


# --- the band itself --------------------------------------------------------


def test_band_is_scaled_by_carrying_capacity():
    cfg = _cfg(population_envelope_enabled=True, carrying_capacity=400)
    lo, hi = population_envelope(cfg)
    assert lo == pytest.approx(400 * 0.96)
    assert hi == pytest.approx(400 * 1.04)


def test_incoherent_band_is_refused():
    """lo >= hi would make the lower boundary unreachable; treat it as off."""
    cfg = _cfg(population_envelope_enabled=True, pop_env_lo_frac=1.0, pop_env_hi_frac=1.0)
    assert population_envelope(cfg) is None


# --- birth veto above K*hi --------------------------------------------------


def _breeding_sim(**kw) -> Simulation:
    """20 fertile adults. K=10 by default, so the ceiling sits far below the
    population; override carrying_capacity to move the band instead."""
    kw.setdefault("carrying_capacity", 10)
    kw.setdefault("max_population", 10_000)
    kw.setdefault("num_women", 10)
    cfg = _cfg(**kw)
    sim = Simulation(cfg)
    for i in range(20):
        sim.world.add(
            Creature(
                x=10.0 + (i % 5) * 4.0, y=10.0 + (i // 5) * 4.0,
                # half males (polygon), half females (line): a birth needs both
                shape="polygon" if i % 2 == 0 else "line",
                energy=90.0, health=100.0, age=100, lifespan=0.0,
            )
        )
    return sim


def _warm(sim):
    """Entities added straight to the world are not in the spatial index until a
    step rebuilds it, and _reproduce finds fathers only through that index."""
    sim.step()
    sim.births = 0
    return [e for e in sim.world.entities.values() if e.kind == "creature"]


def test_births_are_hard_vetoed_above_the_ceiling():
    sim = _breeding_sim(population_envelope_enabled=True)
    sim._cached_creatures = _warm(sim)
    assert len(sim._cached_creatures) > 10 * 1.04, (
        "fixture must start above the envelope ceiling"
    )
    sim._reproduce()
    assert sim.births == 0, "births must be vetoed above K*hi"


def test_births_proceed_inside_the_band():
    sim = _breeding_sim(population_envelope_enabled=True, carrying_capacity=100)
    sim._cached_creatures = _warm(sim)
    assert len(sim._cached_creatures) < 100 * 1.04, "fixture must start inside the band"
    sim._reproduce()
    assert sim.births > 0, "the envelope must not veto births inside the band"


def test_disabled_envelope_leaves_births_untouched():
    sim = _breeding_sim(population_envelope_enabled=False)
    sim._cached_creatures = _warm(sim)
    sim._reproduce()
    assert sim.births > 0


# --- reflecting lower edge below K*lo ---------------------------------------
#
# The floor is a *boundary condition*, not a startup guard. It must push a
# population that has drifted out through the lower edge back up into the band.
# It must never kill: deaths imposed on an already-deficient population drive it
# further down (the inverted-boundary feedback), and the one way this code
# managed that was a per-capita cull hazard — measured 170 culls taking the
# population 38 -> 6 in 400 ticks at K*lo=365, and then, once the reach guard
# was added, still culling a population that had merely fallen a little short.
#
# So the floor is extra *birth room*, peaking at the reach boundary one envelope
# width (K*hi - K*lo) below K*lo: inside that neighbourhood the edge is
# absorbing, and below it the law has no jurisdiction and famine/extinction
# dynamics apply as they always did.

K_TEST = 100.0
LO_TEST = 96.0   # K*0.96
HI_TEST = 104.0  # K*1.04
REACH_TEST = 88.0  # LO - (HI - LO)


def test_lower_boost_is_zero_at_and_above_the_lower_edge():
    for n in (LO_TEST, 99.0, HI_TEST, 400.0):
        assert envelope_lower_boost(n, LO_TEST, HI_TEST, 0.5) == 0.0


def test_lower_boost_peaks_at_the_reach_boundary():
    assert envelope_lower_boost(REACH_TEST, LO_TEST, HI_TEST, 0.5) == pytest.approx(0.5)
    assert envelope_lower_boost(REACH_TEST, LO_TEST, HI_TEST, 2.0) == pytest.approx(2.0)


def test_lower_boost_vanishes_continuously_at_the_lower_edge():
    near = envelope_lower_boost(LO_TEST - 0.5, LO_TEST, HI_TEST, 0.5)
    assert 0.0 < near < 0.05, "the boost must not switch on as a step at K*lo"


def test_lower_boost_grows_monotonically_as_the_population_falls():
    ns = [95.0, 93.0, 91.0, 89.0, 88.0]
    vals = [envelope_lower_boost(n, LO_TEST, HI_TEST, 0.5) for n in ns]
    assert all(b > a for a, b in zip(vals, vals[1:])), (
        f"boost must rise strictly as N falls: {vals}"
    )


def test_lower_boost_stops_at_the_reach_boundary():
    """A world legitimately smaller than the band gets no jurisdiction, or the
    envelope would mask its own equilibrium and keep pumping births forever."""
    for n in (87.0, 50.0, 0.0):
        assert envelope_lower_boost(n, LO_TEST, HI_TEST, 0.5) == 0.0


def test_lower_boost_is_zero_when_the_knob_is_zero():
    assert envelope_lower_boost(90.0, LO_TEST, HI_TEST, 0.0) == 0.0


def test_lower_boost_survives_a_degenerate_band():
    assert envelope_lower_boost(1.0, 0.0, 0.0, 0.5) == 0.0
    assert envelope_lower_boost(1.0, 100.0, 100.0, 0.5) == 0.0


# --- the knob reaches the simulation (F4: no dead levers) --------------------


def test_boost_knob_is_a_config_field_with_a_documented_default():
    assert "pop_env_lo_birth_boost" in Config.__dataclass_fields__
    assert Config().pop_env_lo_birth_boost == pytest.approx(0.5)


def test_boost_knob_is_readable_from_the_environment(monkeypatch):
    monkeypatch.setenv("FLATWORLD_POP_ENV_LO_BIRTH_BOOST", "1.75")
    assert Config.from_env().pop_env_lo_birth_boost == pytest.approx(1.75)
    monkeypatch.delenv("FLATWORLD_POP_ENV_LO_BIRTH_BOOST")
    assert Config.from_env().pop_env_lo_birth_boost == pytest.approx(0.5)


def _breeders(n_creatures, *, boost=None, enabled=True, carrying=100):
    """A breeding population of exactly n_creatures at K=carrying.

    K=100 gives lo=96, hi=104, reach=88, so n=90 sits inside the lower edge's
    jurisdiction and n=20 sits far below it. birth_rate is held well below 1 so
    fertility is *not* saturated: with a saturated rate the boost could not show
    up as extra births even if it were wired in.
    """
    kw = dict(
        carrying_capacity=carrying, max_population=10_000, birth_rate=0.3,
        reproduction_cooldown=100_000,  # nobody breeds during the warm step
        population_envelope_enabled=enabled,
    )
    if boost is not None:
        kw["pop_env_lo_birth_boost"] = boost
    cfg = _cfg(**kw)
    sim = Simulation(cfg)
    for i in range(n_creatures):
        sim.world.add(Creature(
            x=10.0 + (i % 12) * 4.0, y=10.0 + (i // 12) * 4.0,
            shape="polygon" if i % 2 == 0 else "line",
            energy=90.0, health=100.0, age=100, lifespan=0.0,
            repro_cooldown=100_000,
        ))
    return sim


def _breeders_ready(n_creatures, **kw):
    """`_breeders` warmed up and released to breed: the population is still
    exactly n_creatures, but the spatial index exists and nobody is on cooldown."""
    sim = _breeders(n_creatures, **kw)
    cs = _warm(sim)
    assert len(cs) == n_creatures, (
        f"warm step changed the population: {len(cs)} != {n_creatures}"
    )
    for c in cs:
        c.repro_cooldown = 0
    sim._cached_creatures = cs
    return sim


def _births_at(n_creatures, **kw):
    sim = _breeders_ready(n_creatures, **kw)
    sim._reproduce()
    return sim.births


def test_a_population_below_the_lower_edge_gets_extra_birth_room():
    off = _births_at(90, boost=0.0)
    on = _births_at(90, boost=6.0)
    assert off > 0, "fixture must be able to breed at all"
    assert on > off, f"the reflecting floor must lift births: off={off} on={on}"


def test_the_boost_never_fewers_births_than_no_boost():
    """Monotone in the knob: a stronger floor can only add birth room."""
    few = _births_at(90, boost=0.0)
    some = _births_at(90, boost=0.25)
    assert some >= few, f"boost must not suppress births: {few} -> {some}"


def test_no_birth_boost_inside_or_above_the_band():
    """Above the lower edge the floor must be inert, or it would keep the
    population off its own carrying capacity from below."""
    assert _births_at(96, boost=6.0) == _births_at(96, boost=0.0)


def test_no_birth_boost_far_below_the_band():
    far = _births_at(20, boost=6.0)
    off = _births_at(20, boost=0.0)
    assert far == off, "the reach guard must keep the law off a small world"


def test_disabled_envelope_never_boosts_births():
    knob_only = _births_at(90, boost=6.0, enabled=False)
    plain = _births_at(90, boost=0.0, enabled=False)
    assert knob_only == plain


def test_the_lower_edge_never_kills_anything():
    """The regression that the cull hazard caused: deaths imposed below the band
    are a positive feedback away from it."""
    sim = _breeders(90, boost=6.0, carrying=100)
    sim._cached_creatures = [
        e for e in sim.world.entities.values() if e.kind == "creature"
    ]
    assert len(sim._cached_creatures) == 90
    for _ in range(200):
        sim.step()
    causes = dict(getattr(sim, "_death_counts", {}) or {})
    assert causes.get("cull", 0) == 0, f"the lower edge must not cull: {causes}"
    alive = len([e for e in sim.world.entities.values() if e.kind == "creature"])
    assert alive >= 90, f"the lower edge emptied a deficient population: {alive}"

