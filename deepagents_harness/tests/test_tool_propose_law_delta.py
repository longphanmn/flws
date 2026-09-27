"""Task 4 — tool 3: propose_law_delta.

§6 L275: ``propose_law_delta(current, delta)`` -> validated ``dataclasses.replace``
kwargs; rejects non-``Config`` fields (catches F4). This is the agent's entire write
scope: a set of Config field values, applied by the deterministic harness on the
F7-immune ``Config``+``replace`` seam (§7 L345-348, §13 L554-556). The agent never
edits simulation/*.py and never writes law_state_v1; the guardrail here is that a key
which is not a Config field cannot survive validation, because such a key would be a
silent no-op (the F4 dead-knob class, Phase 0.3's own bug).

Values are ABSOLUTE, not relative. The Phase 0-2 proposal door is ``--set
field=value``; a relative delta would make the recorded manifest depend on a
``current`` the harness cannot verify, and the manifest is the comparability
evidence.
"""
import dataclasses

import pytest

from deepagents_harness import _flws


def test_returns_replace_kwargs_with_types_coerced_to_the_config_field():
    from deepagents_harness.tools import propose_law_delta

    out = propose_law_delta(
        current={},
        delta={"population_envelope_enabled": "true", "pop_env_lo_frac": "0.96",
               "width": "400"},
    )
    assert out["proposal"] == {
        "population_envelope_enabled": True,
        "pop_env_lo_frac": 0.96,
        "width": 400,
    }
    assert out["fields"] == ["pop_env_lo_frac", "population_envelope_enabled", "width"]


def test_rejects_a_field_that_is_not_a_config_field():
    from deepagents_harness.tools import propose_law_delta

    with pytest.raises(ValueError) as exc:
        propose_law_delta(current={}, delta={"damping_release_tao": 250.0})
    assert "damping_release_tao" in str(exc.value)
    assert "Config" in str(exc.value)


def test_rejects_a_value_that_cannot_be_read_as_the_declared_type():
    from deepagents_harness.tools import propose_law_delta

    with pytest.raises(ValueError) as exc:
        propose_law_delta(current={}, delta={"pop_env_lo_frac": "not-a-number"})
    assert "pop_env_lo_frac" in str(exc.value)


def test_rejects_a_scalar_only_damping_proposal():
    from deepagents_harness.tools import propose_law_delta

    # §13 L547-549 / the F4 rule: proportional-band constants cannot produce
    # absorbing behaviour, so a proposal that only nudges them is refused before a
    # single tick is spent.
    with pytest.raises(ValueError) as exc:
        propose_law_delta(current={}, delta={"damping_release_tau": 250.0})
    assert "scalar" in str(exc.value).lower()


def test_accepts_a_topology_proposal_that_moves_the_envelope():
    from deepagents_harness.tools import propose_law_delta

    out = propose_law_delta(
        current={},
        delta={"population_envelope_enabled": True, "pop_env_lo_frac": 0.96,
               "pop_env_hi_frac": 1.04},
    )
    assert len(out["proposal"]) == 3
    assert out["is_topology_change"] is True


def test_a_single_envelope_lever_is_not_a_scalar_damping_proposal():
    from deepagents_harness.tools import propose_law_delta

    out = propose_law_delta(current={}, delta={"pop_env_lo_frac": 0.9})
    assert out["proposal"] == {"pop_env_lo_frac": 0.9}


def test_the_returned_kwargs_actually_apply_to_a_real_config():
    from deepagents_harness.tools import propose_law_delta

    g = _flws.gates()
    cfg = g._osc_config(42)
    out = propose_law_delta(
        current=dataclasses.asdict(cfg),
        delta={"population_envelope_enabled": True, "pop_env_lo_frac": 0.96},
    )
    new = dataclasses.replace(cfg, **out["proposal"])
    assert new.population_envelope_enabled is True
    assert new.pop_env_lo_frac == pytest.approx(0.96)
    # A proposal must not disturb the fields it did not name.
    assert new.seed == cfg.seed
    assert new.pop_env_hi_frac == cfg.pop_env_hi_frac


def test_does_not_mutate_the_current_mapping_it_was_given():
    from deepagents_harness.tools import propose_law_delta

    current = {"pop_env_lo_frac": 0.96}
    snapshot = dict(current)
    propose_law_delta(current=current, delta={"pop_env_hi_frac": 1.04})
    assert current == snapshot


def test_reports_the_delta_against_the_current_values_it_was_given():
    from deepagents_harness.tools import propose_law_delta

    out = propose_law_delta(
        current={"pop_env_lo_frac": 0.96},
        delta={"pop_env_lo_frac": 0.90},
    )
    assert out["changed"] == {"pop_env_lo_frac": {"from": 0.96, "to": 0.90}}


def test_an_empty_delta_is_rejected_rather_than_silently_a_no_op():
    from deepagents_harness.tools import propose_law_delta

    with pytest.raises(ValueError):
        propose_law_delta(current={}, delta={})


def test_is_deterministic():
    from deepagents_harness.tools import propose_law_delta

    kw = {"current": {}, "delta": {"pop_env_lo_frac": 0.9, "pop_env_hi_frac": 1.1}}
    assert propose_law_delta(**kw) == propose_law_delta(**kw)
