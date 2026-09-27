"""F5 — gate 4 must distinguish "not measurable" from "failed".

`old_age_burstiness` is `max/median` over 100-tick old-age bins, so it is
undefined whenever the median bin is 0 — i.e. whenever the world lets its
population age gracefully instead of culling it. The harness scored that
`None` as a hard FAIL, which means a *low old-age mortality* world is graded
as a dynamics failure and any search optimising the gate suite is pushed
toward manufacturing old-age deaths to escape `None`.

The check therefore becomes tri-state: True = pass, False = fail,
None = not measurable. A not-measurable gate must not decide the verdict,
and it must not be able to mask a real failure elsewhere.
"""

import importlib.util
import os

import pytest

_HARNESS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "scripts", "preset_experiment.py",
)


def _load_harness():
    spec = importlib.util.spec_from_file_location("preset_experiment_gate_test", _HARNESS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def pe():
    return _load_harness()


def _metrics(**over):
    """All gates comfortably passing; override one at a time."""
    m = {
        "N_cv": 0.05,
        "amplitude": 0.10,
        "reversals_per_72k": 2.0,
        "old_age_burstiness": 1.5,
        "old_age_bins_median": 4,
        "old_age_bins_max": 6,
        "old_age_total": 40,
        "min_n_frac": 0.80,
    }
    m.update(over)
    return m


def _burst_status(checks):
    return {name: status for name, status, _ in checks}["burstiness<3.0"]


def test_median_zero_old_age_is_not_measurable_not_fail(pe):
    passed, checks = pe.osc_gate_report(
        _metrics(old_age_burstiness=None, old_age_bins_median=0), flat=True
    )
    assert _burst_status(checks) is None, "must be not-measurable, not False"
    assert passed is True, "a not-measurable gate must not decide the verdict"


def test_measurable_burstiness_still_fails_above_threshold(pe):
    passed, checks = pe.osc_gate_report(
        _metrics(old_age_burstiness=4.5, old_age_bins_median=4), flat=True
    )
    assert _burst_status(checks) is False
    assert passed is False


def test_measurable_burstiness_still_passes_below_threshold(pe):
    passed, checks = pe.osc_gate_report(
        _metrics(old_age_burstiness=2.9, old_age_bins_median=4), flat=True
    )
    assert _burst_status(checks) is True
    assert passed is True


def test_not_measurable_does_not_mask_a_real_failure(pe):
    passed, checks = pe.osc_gate_report(
        _metrics(old_age_burstiness=None, old_age_bins_median=0, N_cv=0.5), flat=True
    )
    assert _burst_status(checks) is None
    assert {n: s for n, s, _ in checks}["CV(N)<=0.08"] is False
    assert passed is False
