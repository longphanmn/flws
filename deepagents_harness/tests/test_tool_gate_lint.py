"""Task 3 — tool 2: gate_lint.

§6 L274: ``gate_lint(metrics)`` -> the list of *structurally unreachable* gates,
deterministic, no LLM. The point of the tool is to refuse simulation time on a
candidate no constant can fix (§6 L281-283, §12 Step 3 "a deliberately-broken
proposal is rejected without spending a single tick").

This is a *mapping* over the Phase 1 linter's five rules onto the five gates, not a
second linter. The distinction that matters: a blocking rule makes a gate
unreachable, a warning makes it at-risk, and a rule that could not be evaluated is
"unknown" -- never "ok". A linter that reports "ok" for a check it did not run is
the same false all-clear as Phase 1 issue 5 (agy: "reading a missing key as a match").
"""
import json
import subprocess
import sys

import pytest

from deepagents_harness import _flws

# Gate order as osc_gate_report emits them (§Phase 0.2, preset_experiment.py L571-579).
GATE_CV, GATE_AMP, GATE_REV, GATE_BURST, GATE_MINN = 1, 2, 3, 4, 5


def _metrics(**over):
    m = {
        "seed": 42, "modulated": False, "K": 380.0, "K_eff_min": 380.0,
        "K_eff_max": 380.0, "N_mean": 380.0, "N_min": 376, "N_max": 384,
        "N_cv": 0.011, "amplitude": 0.021, "band_width": 8, "drift_rate": 0.0,
        "reversals": 0, "reversals_per_72k": 0.0, "old_age_bins_median": 2,
        "old_age_bins_max": 3, "old_age_burstiness": 1.5, "starvation_total": 0,
        "old_age_total": 60, "min_n_frac": 0.99, "food_mean": 400.0,
        "food_min": 390, "food_max": 410, "xi_mean": 0.2, "xi_max": 0.4,
        "ms_per_tick": 40.0,
    }
    m.update(over)
    return m


def test_a_measurable_measurable_run_has_no_unreachable_gates():
    from deepagents_harness.tools import gate_lint

    out = gate_lint(_metrics(), pops=[380.0] * 30, sample=100)
    assert out["unreachable_gates"] == []
    assert out["at_risk_gates"] == []
    assert out["ok"] is True


def test_median_zero_burstiness_makes_gate_4_unreachable():
    from deepagents_harness.tools import gate_lint

    out = gate_lint(
        _metrics(old_age_bins_median=0, old_age_burstiness=None, old_age_total=0),
        pops=[380.0] * 30, sample=100,
    )
    assert GATE_BURST in out["unreachable_gates"]
    assert out["ok"] is False


def test_a_controller_that_never_engaged_makes_gates_1_2_3_unreachable():
    from deepagents_harness.tools import gate_lint

    out = gate_lint(_metrics(xi_mean=0.0, xi_max=0.0), pops=[380.0] * 30, sample=100)
    assert set(out["unreachable_gates"]) == {GATE_CV, GATE_AMP, GATE_REV}
    assert out["ok"] is False


def test_broadband_wander_is_at_risk_not_unreachable():
    import random

    from deepagents_harness.tools import gate_lint

    # Genuine broadband wander: white noise, no ACF peak. A sawtooth would not do
    # here -- a period-2 square wave *is* a limit cycle and F3 correctly calls it
    # one, so a sawtooth would test the opposite claim.
    rng = random.Random(1234)
    pops = [380.0 + rng.uniform(-40.0, 40.0) for _ in range(60)]
    out = gate_lint(_metrics(), pops=pops, sample=100)
    f3 = next(r for r in out["rules"] if r["rule"] == "F3_no_periodicity")
    assert f3["severity"] == "warning", f3
    assert out["at_risk_gates"] == [GATE_REV]
    assert GATE_REV not in out["unreachable_gates"]


def test_a_limit_cycle_is_not_at_risk_because_it_is_a_real_period():
    from deepagents_harness.tools import gate_lint

    pops = [380.0 + (40.0 if i % 2 else -40.0) for i in range(40)]
    out = gate_lint(_metrics(), pops=pops, sample=100)
    assert out["at_risk_gates"] == []


def test_a_dead_knob_proposal_is_blocked_as_a_silent_no_op():
    from deepagents_harness.tools import gate_lint

    out = gate_lint(_metrics(), pops=[380.0] * 30, sample=100,
                    proposal={"damping_release_tao": 250.0})
    assert out["ok"] is False
    rule = next(r for r in out["rules"] if r["rule"] == "F4_dead_knob")
    assert rule["severity"] == "blocking"


def test_a_scalar_only_damping_proposal_is_blocked():
    from deepagents_harness.tools import gate_lint

    out = gate_lint(_metrics(), pops=[380.0] * 30, sample=100,
                    proposal={"damping_release_tau": 250.0})
    assert out["ok"] is False


def test_without_samples_the_periodicity_check_is_unknown_never_ok():
    from deepagents_harness.tools import gate_lint

    # The Phase 1 rule reads an empty pops list as [0.0], whose spread is 0, and
    # reports "smoothed series is flat: no reversals to explain". For a run whose
    # samples were never supplied that is a false all-clear, so the harness marks
    # the check unknown instead of passing it through.
    out = gate_lint(_metrics())
    rule = next(r for r in out["rules"] if r["rule"] == "F3_no_periodicity")
    assert rule["severity"] == "unknown"
    assert out["ok"] is False
    assert GATE_REV in out["unknown_gates"]


def test_gate_3_is_unknown_not_ok_when_samples_are_missing():
    from deepagents_harness.tools import gate_lint

    out = gate_lint(_metrics())
    assert GATE_REV in out["unknown_gates"]
    assert GATE_REV not in out["unreachable_gates"]


def test_output_is_deterministic_across_calls():
    from deepagents_harness.tools import gate_lint

    a = gate_lint(_metrics(xi_mean=0.0), pops=[380.0] * 30, sample=100)
    b = gate_lint(_metrics(xi_mean=0.0), pops=[380.0] * 30, sample=100)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_the_tool_needs_no_llm_to_run():
    """§6 L289-L290: the Verifier is a plain function.

    Proven by importing and calling the tools in a subprocess where every LLM
    package is unimportable. If a tool ever grows a model call, this fails.
    """
    blocker = (
        "import sys\n"
        "class Block:\n"
        "    BANNED = ('langchain', 'langgraph', 'deepagents', 'anthropic', 'openai', 'httpx')\n"
        "    def find_module(self, name, path=None):\n"
        "        return self if name.split('.')[0] in self.BANNED else None\n"
        "    def find_spec(self, name, path=None, target=None):\n"
        "        if name.split('.')[0] in self.BANNED:\n"
        "            raise ImportError('LLM package blocked: ' + name)\n"
        "        return None\n"
        "sys.meta_path.insert(0, Block())\n"
    )
    code = blocker + (
        "import json\n"
        "from deepagents_harness import tools\n"
        "m = {'seed':1,'K':380.0,'N_mean':380.0,'N_cv':0.01,'amplitude':0.02,\n"
        "     'band_width':8,'drift_rate':0.0,'reversals_per_72k':0.0,\n"
        "     'old_age_bins_median':2,'old_age_burstiness':1.5,'old_age_total':10,\n"
        "     'min_n_frac':0.99,'xi_mean':0.2}\n"
        "out = tools.gate_lint(m, pops=[380.0]*30, sample=100)\n"
        "assert out['ok'] is True, out\n"
        "print('LLM-FREE-OK')\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True,
        cwd=__import__("os").path.dirname(
            __import__("os").path.dirname(__import__("os").path.dirname(
                __import__("os").path.abspath(__file__)))),
    )
    assert "LLM-FREE-OK" in proc.stdout, proc.stderr[-800:]
