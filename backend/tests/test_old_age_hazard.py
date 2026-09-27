"""G4 — hazard-uniformised old-age senescence, config-driven and inert by default.

`c.age >= c.lifespan` is a threshold, i.e. a delta function of age: a cohort
crosses it in the same few ticks, so old-age deaths arrive in lumps and the
100-tick old-age-bin ratio (gate 4) measures the lumpiness of the cohort rather
than the mortality of the population.

The fix replaces the threshold above the elder onset with a memoryless
(constant) hazard. Taking ``lambda = 1 / (lifespan - onset)`` makes the mean age
at death exactly ``lifespan``, so the turnover rate is unchanged and only the
*shape* of the death stream moves: uniform over the old-age window instead of
concentrated at its end.

The whole law is behind `old_age_hazard_enabled`, which defaults to False, so a
disabled law must be the exact old threshold and must not touch the RNG stream
(the determinism golden lock would otherwise move for a disabled law). Every C3
knob — the envelope's and the hazard's — is a real `Config` field, parsed from
`FLATWORLD_*`, pinned in the theocracy preset, steerable/persistable via
`GodLaws`/`LAW_FIELDS`, and backfilled absent-only in `_restore_law_state`.
"""

import json
import random

import pytest

from app.config import Config
from app.simulation.creature_update import CreatureUpdateMixin

C3_KEYS = (
    "population_envelope_enabled", "pop_env_lo_frac", "pop_env_hi_frac",
    "pop_env_lo_birth_boost", "old_age_hazard_enabled", "old_hazard_onset_frac",
)


class _C:
    """Minimal stand-in: only ``age``/``lifespan`` are read by the hazard."""

    def __init__(self, age: float, lifespan: float):
        self.age = age
        self.lifespan = lifespan


class _Stub(CreatureUpdateMixin):
    """The mixin's hazard only needs ``config`` and an RNG."""

    def __init__(self, cfg: Config, seed: int = 0):
        self.config = cfg
        self.rng = random.Random(seed)


def _cfg(**kw) -> Config:
    kw.setdefault("old_age_hazard_enabled", True)
    return Config(**kw)


# --- disabled law is exactly the old threshold, and RNG-inert -------------


def test_disabled_law_is_the_old_threshold():
    s = _Stub(Config(old_age_hazard_enabled=False))
    assert s._senescence_due(_C(0, 100)) is False
    assert s._senescence_due(_C(99.9, 100)) is False
    assert s._senescence_due(_C(100, 100)) is True
    assert s._senescence_due(_C(1000, 100)) is True


def test_disabled_law_consumes_no_randomness():
    """A disabled law must not consume a single random draw, or the golden
    determinism hashes move for a law that is supposed to be off."""
    s = _Stub(Config(old_age_hazard_enabled=False))
    before = s.rng.getstate()
    for age in (0, 50, 99, 100, 1000):
        s._senescence_due(_C(age, 100))
    assert s.rng.getstate() == before


# --- the hazard itself -----------------------------------------------------


def test_no_death_before_the_onset():
    s = _Stub(_cfg(old_hazard_onset_frac=0.75))
    for age in (0, 10, 74, 74.999):
        assert s._senescence_due(_C(age, 100)) is False


def test_onset_scales_with_lifespan():
    s = _Stub(_cfg(old_hazard_onset_frac=0.60))
    assert s._senescence_due(_C(119.9, 200)) is False, "0.60*200 = 120"
    assert any(s._senescence_due(_C(120.0, 200)) for _ in range(2000))


def test_mean_age_at_death_is_still_the_lifespan():
    """lambda = 1/span holds the turnover rate: mean age at death = lifespan."""
    lifespan = 1000.0
    s = _Stub(_cfg(old_hazard_onset_frac=0.75), seed=12345)
    trials = 4000
    total = 0.0
    for _ in range(trials):
        c = _C(0.0, lifespan)
        while not s._senescence_due(c):
            c.age += 1.0
            assert c.age <= 40 * lifespan, "hazard never fired"
        total += c.age
    assert total / trials == pytest.approx(lifespan, rel=0.06)


def test_hazard_staggers_a_synchronised_cohort():
    """A cohort all exactly at the onset must not die together the way the
    threshold killed it: after 10 ticks at p=1/25 per tick most are still alive."""
    lifespan = 100.0
    s = _Stub(_cfg(old_hazard_onset_frac=0.75), seed=7)
    alive = [_C(75.0, lifespan) for _ in range(2000)]
    for _ in range(10):
        alive = [c for c in alive if not s._senescence_due(c)]
    assert 0 < len(alive) < 2000, (
        f"the death stream is still lumped: {len(alive)}/2000 survived 10 ticks"
    )


def test_degenerate_lifespan_falls_back_to_the_threshold():
    """A zero/invalid lifespan must not immortalise a creature: fall back to the
    original threshold semantics."""
    s = _Stub(_cfg())
    assert s._senescence_due(_C(5, 0)) is True
    assert s._senescence_due(_C(0, 0)) is True
    # span <= 0 (onset_frac == 1.0) also falls back to the threshold
    edge = _Stub(_cfg(old_hazard_onset_frac=1.0))
    assert edge._senescence_due(_C(5, 5)) is True
    assert edge._senescence_due(_C(4, 5)) is False


# --- config plumbing: field, env, preset, GodLaws, migration ---------------


def test_c3_knobs_are_real_config_fields():
    fields = Config.__dataclass_fields__
    for key in C3_KEYS:
        assert key in fields, f"{key} is not a Config field — unreachable knob"


def test_c3_defaults_match_the_verified_values():
    cfg = Config()
    # Master flags stay inert by default (determinism contract); parameter
    # defaults are the verified C3 values.
    assert cfg.population_envelope_enabled is False
    assert cfg.pop_env_lo_frac == pytest.approx(0.96)
    assert cfg.pop_env_hi_frac == pytest.approx(1.04)
    assert cfg.pop_env_lo_birth_boost == pytest.approx(0.5)
    assert cfg.old_age_hazard_enabled is False
    assert cfg.old_hazard_onset_frac == pytest.approx(0.75)


def test_env_parsers_set_the_hazard_knobs(monkeypatch):
    monkeypatch.setenv("FLATWORLD_OLD_AGE_HAZARD_ENABLED", "true")
    monkeypatch.setenv("FLATWORLD_OLD_HAZARD_ONSET_FRAC", "0.60")
    cfg = Config.from_env()
    assert cfg.old_age_hazard_enabled is True
    assert cfg.old_hazard_onset_frac == pytest.approx(0.60)
    monkeypatch.delenv("FLATWORLD_OLD_AGE_HAZARD_ENABLED")
    assert Config.from_env().old_age_hazard_enabled is False


def test_theocracy_preset_pins_the_c3_knobs():
    from app.main import PRESETS

    p = PRESETS["theocracy"]
    for key in C3_KEYS:
        assert key in p, f"theocracy preset is missing {key}"
    assert p["population_envelope_enabled"] is False
    assert p["pop_env_lo_frac"] == pytest.approx(0.96)
    assert p["pop_env_hi_frac"] == pytest.approx(1.04)
    assert p["pop_env_lo_birth_boost"] == pytest.approx(0.5)
    assert p["old_age_hazard_enabled"] is False
    assert p["old_hazard_onset_frac"] == pytest.approx(0.75)


def test_god_laws_can_carry_the_c3_knobs():
    from app.main import LAW_FIELDS

    for key in C3_KEYS:
        assert key in LAW_FIELDS, f"{key} not settable/persistable on the served path"


def _write_law_state(blob: dict):
    from app.main import DB, LAW_STATE_KEY

    DB.set_setting(LAW_STATE_KEY, json.dumps(blob))


def _restore():
    from app.main import RuntimeState, _restore_law_state

    rt = RuntimeState(Config.from_env())
    assert _restore_law_state(rt) is True
    return rt


def test_restore_backfills_the_c3_knobs_from_the_preset():
    from app.main import DB, LAW_STATE_KEY, PRESETS

    prev = DB.get_setting(LAW_STATE_KEY)
    try:
        _write_law_state({
            "preset": "theocracy",
            "laws": {"food_count": 400, "carrying_capacity": 380},
            "saved_laws": {"food_count": 400, "carrying_capacity": 380},
        })
        cfg = _restore().config
        preset = PRESETS["theocracy"]
        assert cfg.old_hazard_onset_frac == pytest.approx(preset["old_hazard_onset_frac"])
        assert cfg.old_age_hazard_enabled == preset["old_age_hazard_enabled"]
        assert cfg.pop_env_lo_birth_boost == pytest.approx(preset["pop_env_lo_birth_boost"])
        assert cfg.food_count == 400  # untouched laws still come from the blob
    finally:
        if prev is None:
            DB.delete_setting(LAW_STATE_KEY)
        else:
            DB.set_setting(LAW_STATE_KEY, prev)


def test_restore_never_overwrites_explicit_c3_values():
    from app.main import DB, LAW_STATE_KEY

    prev = DB.get_setting(LAW_STATE_KEY)
    try:
        _write_law_state({
            "preset": "theocracy",
            "laws": {"food_count": 400, "old_age_hazard_enabled": True,
                     "old_hazard_onset_frac": 0.60, "pop_env_lo_frac": 0.72},
            "saved_laws": {},
        })
        cfg = _restore().config
        assert cfg.old_age_hazard_enabled is True
        assert cfg.old_hazard_onset_frac == pytest.approx(0.60)
        assert cfg.pop_env_lo_frac == pytest.approx(0.72)
    finally:
        if prev is None:
            DB.delete_setting(LAW_STATE_KEY)
        else:
            DB.set_setting(LAW_STATE_KEY, prev)
