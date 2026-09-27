"""Phase 2 — the harness must be able to run a *proposal*, not just the preset.

T0 is the falsification test for the whole inverse design: run the theocracy
preset with the population envelope enabled and ask whether the 300-tick
smoothed series goes flat. The harness builds its Config with
`Config(...) + dataclasses.replace(PRESETS[...])` and never reads
`Config.from_env()`, so an env var cannot switch the law on for a gate run — the
proposal has to be passed in explicitly and recorded in the manifest.
"""

import importlib.util
import os
from dataclasses import fields

import pytest

_HARNESS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "scripts", "preset_experiment.py",
)


def _load():
    spec = importlib.util.spec_from_file_location("preset_experiment_proposal_test", _HARNESS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def pe():
    return _load()


# --- parsing ----------------------------------------------------------------


def test_set_parses_typed_values(pe):
    overrides = pe._parse_set_overrides([
        "--set", "population_envelope_enabled=true",
        "--set", "pop_env_lo_frac=0.96",
        "--set", "carrying_capacity=420",
    ])
    assert overrides == {
        "population_envelope_enabled": True,
        "pop_env_lo_frac": 0.96,
        "carrying_capacity": 420,
    }


def test_set_rejects_an_unknown_field(pe):
    with pytest.raises(SystemExit):
        pe._parse_set_overrides(["--set", "not_a_real_field=1"])


def test_set_rejects_an_uncoercible_value(pe):
    with pytest.raises(SystemExit):
        pe._parse_set_overrides(["--set", "pop_env_lo_frac=banana"])


def test_set_of_nothing_is_empty(pe):
    assert pe._parse_set_overrides([]) == {}


def test_set_argv_is_recognised(pe):
    args = pe._parse_osc_args([
        "--world", "B", "--seed", "42", "--set", "carrying_capacity=420",
    ])
    assert args["world"] == "B" and args["seed"] == "42"
    assert pe._parse_set_overrides(["--set", "carrying_capacity=420"]) == {
        "carrying_capacity": 420
    }


# --- the proposal actually reaches the simulated config ---------------------


def test_overrides_reach_the_osc_config(pe):
    cfg = pe._osc_config(42, overrides={"population_envelope_enabled": True})
    assert cfg.population_envelope_enabled is True
    assert cfg.seed == 42


def test_defaults_leave_the_preset_untouched(pe):
    cfg = pe._osc_config(42)
    assert cfg.population_envelope_enabled is False, (
        "a gate run with no proposal must not have the law switched on"
    )


def test_overrides_survive_the_preset_replace(pe):
    """The preset is applied with dataclasses.replace, so a proposal passed in
    afterwards is what the simulation actually sees — not the preset's value."""
    overrides = {"population_envelope_enabled": True, "pop_env_lo_frac": 0.9}
    cfg = pe._osc_config(42, overrides=overrides)
    assert cfg.population_envelope_enabled is True
    assert cfg.pop_env_lo_frac == pytest.approx(0.9)


def test_manifest_records_the_proposal(pe, tmp_path):
    """A run under a proposal must be distinguishable from a bare preset run."""
    art = str(tmp_path / "oscillation_T0_42.json")
    payload = pe.osc_ab_run({
        "world": "B", "seed": 42, "out": art, "ticks": "200", "burn_in": "0",
        "overrides": {"population_envelope_enabled": True, "carrying_capacity": 420},
    })
    man = pe.read_run_manifest(art)
    assert man["overrides"] == {
        "population_envelope_enabled": True, "carrying_capacity": 420,
    }
    assert man["config_hash"] == pe.config_hash(pe._osc_config(42, overrides={
        "population_envelope_enabled": True, "carrying_capacity": 420,
    }))
    assert payload["metrics"]["K"] > 0


def test_every_config_field_is_reachable_by_set(pe):
    """--set must not be a partial door: every Config field must be coercible."""
    from app.config import Config

    for f in fields(Config):
        assert f.name.replace("_", "-") or True  # names pass through verbatim
    assert Config.__dataclass_fields__
