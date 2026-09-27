"""F4 — `damping_release_tau` and `damping_sigmoid_k` must be reachable knobs.

`density_damping.py` read both through `getattr(config, ..., default)`, but
neither was a `Config` field. They were therefore unreachable by env var, by
preset, by `dataclasses.replace`, and by the oscillation harness's `hasattr`
preset filter: the most-cited lever in the whole population-stability
investigation was dead code with a hard-wired 300.0 / 5.0.

This pins the whole path: field, env parser, preset key, GodLaws surface (so
the served path can persist it), and a narrow `law_state_v1` backfill for
exactly these two keys.
"""

import json

import pytest

from app.config import Config
from app.density_damping import DensityDampingEngine, scales_for_xi

NEW_KEYS = ("damping_release_tau", "damping_sigmoid_k")


# --- 1. real Config fields, not getattr defaults ----------------------------


def test_tau_and_k_are_real_config_fields():
    fields = Config.__dataclass_fields__
    for key in NEW_KEYS:
        assert key in fields, f"{key} is not a Config field — unreachable knob"


def test_config_defaults_match_the_previous_hardwired_constants():
    assert Config().damping_release_tau == pytest.approx(300.0)
    assert Config().damping_sigmoid_k == pytest.approx(5.0)


# --- 2. FLATWORLD_* env parsers --------------------------------------------


def test_env_parsers_set_tau_and_k(monkeypatch):
    monkeypatch.setenv("FLATWORLD_DAMPING_RELEASE_TAU", "123.5")
    monkeypatch.setenv("FLATWORLD_DAMPING_SIGMOID_K", "2.25")
    cfg = Config.from_env()
    assert cfg.damping_release_tau == pytest.approx(123.5)
    assert cfg.damping_sigmoid_k == pytest.approx(2.25)


# --- 3. the engine actually consumes them (not shadowed by the defaults) ----


def test_sigmoid_k_changes_the_scales():
    from dataclasses import replace

    base = Config()
    wide = scales_for_xi(0.30, base)
    sharp = scales_for_xi(0.30, replace(base, damping_sigmoid_k=20.0))
    assert wide["birth_rate_eff"] != pytest.approx(sharp["birth_rate_eff"])


def test_release_tau_changes_the_release_slew():
    from dataclasses import replace

    # Drop N back below onset so the engine takes the *release* branch, and step
    # twice: with a tiny tau xi must snap to the target, with a huge tau it must not.
    K = 400

    def xi_after_two_releases(tau):
        eng = DensityDampingEngine(replace(Config(), damping_release_tau=tau))
        eng.update(400, tick=1, Kcap=K)            # onset: xi snaps up
        eng.update(100, tick=2, Kcap=K)            # release 1
        return eng.update(100, tick=3, Kcap=K)[0]  # release 2

    # A small tau must bleed xi off far faster than a huge one. (tau is a
    # per-tick factor exp(-1/max(1,tau)), so tau=1 leaves ~e^-2 of the onset
    # value after two releases; tau=1e5 leaves essentially all of it.)
    fast = xi_after_two_releases(1.0)
    slow = xi_after_two_releases(100000.0)
    assert fast < 0.05, f"tau=1 should bleed off fast, got {fast}"
    assert slow > 0.1, f"tau=1e5 should barely move, got {slow}"


# --- 4. the preset + the served law surface --------------------------------


def test_theocracy_preset_defines_both_keys():
    from app.main import PRESETS

    for key in NEW_KEYS:
        assert key in PRESETS["theocracy"], f"theocracy preset is missing {key}"


def test_god_laws_can_carry_both_keys():
    from app.main import LAW_FIELDS

    for key in NEW_KEYS:
        assert key in LAW_FIELDS, f"{key} not settable/persistable on the served path"


def test_osc_harness_preset_filter_does_not_drop_them():
    """`_osc_config` keeps only preset keys that are real Config fields, so a
    key that is not a field is silently discarded by the gate harness."""
    from dataclasses import replace

    from app.main import PRESETS

    base = Config()
    laws = {k: v for k, v in PRESETS["theocracy"].items() if hasattr(base, k)}
    for key in NEW_KEYS:
        assert key in laws, f"harness would silently drop {key} via the hasattr filter"
    assert replace(base, **laws).damping_release_tau == PRESETS["theocracy"]["damping_release_tau"]


# --- 5. narrow law_state backfill, exactly these two keys ------------------


def _write_law_state(blob: dict):
    from app.main import DB, LAW_STATE_KEY

    DB.set_setting(LAW_STATE_KEY, json.dumps(blob))


def _restore():
    """_restore_law_state mutates the RuntimeState in place and returns a bool."""
    from app.main import RuntimeState, _restore_law_state

    rt = RuntimeState(Config.from_env())
    assert _restore_law_state(rt) is True
    return rt


def test_restore_backfills_the_two_new_keys_from_the_preset():
    from app.main import DB, LAW_STATE_KEY, PRESETS

    prev = DB.get_setting(LAW_STATE_KEY)
    try:
        _write_law_state({
            "preset": "theocracy",
            "laws": {"food_count": 400, "carrying_capacity": 380},
            "saved_laws": {"food_count": 400, "carrying_capacity": 380},
        })
        cfg = _restore().config
        assert cfg.damping_release_tau == PRESETS["theocracy"]["damping_release_tau"]
        assert cfg.damping_sigmoid_k == PRESETS["theocracy"]["damping_sigmoid_k"]
        # untouched laws still come from the blob
        assert cfg.food_count == 400
    finally:
        if prev is None:
            DB.delete_setting(LAW_STATE_KEY)
        else:
            DB.set_setting(LAW_STATE_KEY, prev)


def test_restore_never_overwrites_an_explicit_value():
    from app.main import DB, LAW_STATE_KEY

    prev = DB.get_setting(LAW_STATE_KEY)
    try:
        _write_law_state({
            "preset": "theocracy",
            "laws": {"food_count": 400, "damping_release_tau": 42.0, "damping_sigmoid_k": 9.0},
            "saved_laws": {},
        })
        cfg = _restore().config
        assert cfg.damping_release_tau == pytest.approx(42.0)
        assert cfg.damping_sigmoid_k == pytest.approx(9.0)
    finally:
        if prev is None:
            DB.delete_setting(LAW_STATE_KEY)
        else:
            DB.set_setting(LAW_STATE_KEY, prev)


def test_restore_backfill_is_limited_to_the_two_new_keys():
    """No other absent law may be invented — the backfill must stay narrow."""
    from app.config import Config as _C
    from app.main import DB, LAW_STATE_KEY, PRESETS

    prev = DB.get_setting(LAW_STATE_KEY)
    try:
        _write_law_state({
            "preset": "theocracy",
            "laws": {"food_count": 400},
            "saved_laws": {},
        })
        cfg = _restore().config
        preset = PRESETS["theocracy"]
        # a control key the preset sets but the backfill must NOT invent
        control = "safeguard_genesis_batch"
        assert control in preset
        assert getattr(cfg, control) == _C().safeguard_genesis_batch
    finally:
        if prev is None:
            DB.delete_setting(LAW_STATE_KEY)
        else:
            DB.set_setting(LAW_STATE_KEY, prev)
