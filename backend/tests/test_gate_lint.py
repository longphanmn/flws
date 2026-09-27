"""Phase 1 H — the gate linter: a deterministic pre-flight that refuses to burn
a simulation slot on a structurally impossible candidate.

Each rule exists because a real, recorded failure made the next one predictable:

* ``F3_no_periodicity`` — the reversals gate counts sign flips of a 300-tick
  smoothed derivative. If that series has no periodic autocorrelation peak it is
  broadband wander, not a limit cycle, so no release-tau / sigmoid / onset
  constant can fix it; only a topology change can.
* ``F5_median0_burstiness`` — with a median 100-tick old-age bin of 0 the
  burstiness gate is undefined. Escalating a candidate on an undefined gate
  optimizes against nothing.
* ``F4_dead_knob`` — a proposal whose only lever is a knob that never reaches the
  simulation is a no-op; it must be rejected before it costs a tick.
* ``F6_xi_mean_zero`` — a run in which the density controller never engaged
  (xi_mean == 0) has not tested the controller. Seed 42 of the recorded suite
  sits in exactly that attractor.
* ``manifest_mismatch`` — two runs may only be compared if they were produced
  the same way, *and* the comparison has to say which kind it is: a replicate
  (same config, different seed) or a candidate against the baseline it was
  derived from. An absent manifest, or one that does not record the key being
  compared, is a failure to verify — never a match.
"""

import importlib.util
import json
import math
import os

import pytest

_HARNESS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "scripts", "preset_experiment.py",
)
SAMPLE = 100


def _load():
    spec = importlib.util.spec_from_file_location("preset_experiment_lint_test", _HARNESS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def pe():
    return _load()


# --- synthetic runs, fed through the harness' own metric code ---------------


def _run(pops, *, xi=None, oa=1, K=380):
    """A run_oscillation-shaped dict; `pops` is one population per sample."""
    samples = []
    for i, pop in enumerate(pops):
        samples.append({
            "tick": (i + 1) * SAMPLE,
            "pop": pop,
            "food": 400,
            "xi": (xi[i] if xi is not None else 0.2),
            "age_mult": 1.0,
            "season_mult": 1.0,
            "deaths": {"old_age": oa, "starvation": 1},
        })
    return {
        "preset": "theocracy", "seed": 42, "modulated": False, "K": K, "M": int(K * 1.2),
        "total_ticks": len(pops) * SAMPLE, "burn_in": 0, "sample": SAMPLE,
        "elapsed_s": 1.0, "ms_per_tick": 1.0, "samples": samples,
    }


def _rule(report, rule_id):
    for entry in report["rules"]:
        if entry["rule"] == rule_id:
            return entry
    raise AssertionError(f"rule {rule_id} not reported; got {[r['rule'] for r in report['rules']]}")


def _healthy_pops(n=300, K=380):
    """Flat, controller-engaged, measurable old-age mortality: lints clean."""
    return [K] * n


# --- F6: xi_mean == 0 means the controller was never exercised --------------


def test_xi_mean_zero_blocks_escalation(pe):
    run = _run(_healthy_pops(), xi=[0.0] * 300)
    report = pe.gate_lint(run)
    assert report["ok"] is False
    assert _rule(report, "F6_xi_mean_zero")["severity"] == "blocking"
    assert "controller" in _rule(report, "F6_xi_mean_zero")["message"].lower()


def test_engaged_controller_does_not_trigger_f6(pe):
    report = pe.gate_lint(_run(_healthy_pops(), xi=[0.2] * 300))
    assert _rule(report, "F6_xi_mean_zero")["severity"] != "blocking"
    assert report["ok"] is True


# --- F5: median old-age bin 0 => burstiness undefined ----------------------


def test_median_zero_old_age_blocks_escalation(pe):
    report = pe.gate_lint(_run(_healthy_pops(), oa=0))
    assert report["ok"] is False
    assert _rule(report, "F5_median0_burstiness")["severity"] == "blocking"


def test_measurable_old_age_does_not_trigger_f5(pe):
    report = pe.gate_lint(_run(_healthy_pops(), oa=1))
    assert _rule(report, "F5_median0_burstiness")["severity"] != "blocking"
    assert report["ok"] is True


# --- F3: no periodicity => reversals is noise, not a tunable limit cycle ----


def test_limit_cycle_is_not_flagged_as_noise(pe):
    n, period, amp = 300, 40, 20
    pops = [380 + amp * math.sin(2 * math.pi * i / period) for i in range(n)]
    report = pe.gate_lint(_run(pops))
    assert _rule(report, "F3_no_periodicity")["severity"] != "warning"


def test_broadband_wander_is_flagged_as_noise(pe):
    # deterministic pseudo-random walk: no periodicity, plenty of reversals
    n = 300
    pops, x, seed = [], 380, 12345
    for _ in range(n):
        seed = (1103515245 * seed + 12345) % (2 ** 31)
        x += (seed / 2 ** 31 - 0.5) * 12.0
        pops.append(int(x))
    report = pe.gate_lint(_run(pops))
    entry = _rule(report, "F3_no_periodicity")
    assert entry["severity"] == "warning"
    assert "topology" in entry["message"].lower()
    # a warning must not by itself block, and must not be silently absent
    assert report["ok"] is True


def test_flat_series_is_not_flagged_as_noise(pe):
    """A constant smoothed series has no reversals to explain; silence, not noise."""
    report = pe.gate_lint(_run(_healthy_pops()))
    assert _rule(report, "F3_no_periodicity")["severity"] == "ok"


# --- F4: dead knobs, and forbidden scalar-only proposals -------------------


def test_proposal_whose_only_lever_is_tau_is_rejected(pe):
    """τ is a real field now (Phase 0.3), but sweeping it alone is still a no-op
    for the gates: it shapes a proportional band, not the wander reversals counts."""
    run = _run(_healthy_pops())
    proposal = {"damping_release_tau": {"from": 300.0, "to": 120.0}}
    report = pe.gate_lint(run, proposal=proposal)
    assert report["ok"] is False
    entry = _rule(report, "F4_dead_knob")
    assert entry["severity"] == "blocking"
    assert "damping_release_tau" in entry["message"]
    assert "topology" in entry["message"]


def test_proposal_whose_only_lever_is_sigmoid_k_is_rejected(pe):
    run = _run(_healthy_pops())
    proposal = {"damping_sigmoid_k": {"from": 5.0, "to": 9.0}}
    report = pe.gate_lint(run, proposal=proposal)
    assert report["ok"] is False
    assert _rule(report, "F4_dead_knob")["severity"] == "blocking"


def test_proposal_naming_a_non_config_field_is_rejected(pe):
    """The class of bug Phase 0.3 fixed: a key nothing reads is a silent no-op."""
    run = _run(_healthy_pops())
    proposal = {"damping_release_teu": {"from": 300.0, "to": 120.0}}
    report = pe.gate_lint(run, proposal=proposal)
    assert report["ok"] is False
    entry = _rule(report, "F4_dead_knob")
    assert "damping_release_teu" in entry["message"]


def test_no_proposal_means_no_dead_knob_rule(pe):
    report = pe.gate_lint(_run(_healthy_pops()))
    assert _rule(report, "F4_dead_knob")["severity"] == "ok"


def test_proposal_with_a_real_lever_is_not_rejected(pe):
    run = _run(_healthy_pops())
    proposal = {
        "damping_release_tau": {"from": 300.0, "to": 120.0},
        "carrying_capacity": {"from": 350, "to": 380},
    }
    report = pe.gate_lint(run, proposal=proposal)
    assert _rule(report, "F4_dead_knob")["severity"] == "ok"
    assert report["ok"] is True


# --- manifest mismatch: refuse to compare ----------------------------------
#
# A gate delta is only evidence when the two runs were produced the same way.
# What "the same way" tolerates has to be stated, because two different
# comparisons are legitimate and one is not:
#
#   * a replicate — same code, same resolved config, different seed. The seed is
#     the replicate index; refusing this comparison refuses the whole recorded
#     suite.
#   * a candidate against its baseline — same code, same config except the
#     levers the candidate *declares*. Refusing this comparison refuses the
#     whole point of proposing a lever.
#
# What is never tolerated: a field that drifted without anyone declaring it, a
# different code revision, a different tick budget or a different thread count.


def _manifest(**over):
    m = {"git_sha": "abc1234", "config_hash": "cfg9999", "seed": 42,
         "base_config_hash": "base9999",
         "tick_budget": {"total_ticks": 120000, "burn_in": 20000, "sample": 100},
         "omp_num_threads": "1", "seam": "harness-replace", "overrides": {}}
    m.update(over)
    return m


def test_manifest_mismatch_blocks_comparison(pe):
    report = pe.gate_lint(
        _run(_healthy_pops()),
        compare_manifest=(_manifest(), _manifest(git_sha="deadbee")),
    )
    assert report["ok"] is False
    entry = _rule(report, "manifest_mismatch")
    assert entry["severity"] == "blocking"
    assert "git_sha" in entry["message"]


def test_matching_manifests_allow_comparison(pe):
    report = pe.gate_lint(
        _run(_healthy_pops()), compare_manifest=(_manifest(), _manifest())
    )
    assert _rule(report, "manifest_mismatch")["severity"] == "ok"
    assert report["ok"] is True


def test_base_config_hash_difference_blocks_comparison(pe):
    report = pe.gate_lint(
        _run(_healthy_pops()),
        compare_manifest=(_manifest(), _manifest(base_config_hash="base0000")),
    )
    assert report["ok"] is False
    entry = _rule(report, "manifest_mismatch")
    assert entry["severity"] == "blocking"
    assert "base_config_hash" in entry["message"]


def test_two_seeds_of_one_run_are_comparable(pe):
    """Seed 42 against seed 123 is the recorded suite's own comparison."""
    report = pe.gate_lint(
        _run(_healthy_pops()),
        compare_manifest=(
            _manifest(seed=42, config_hash="cfgAAAA"),
            _manifest(seed=123, config_hash="cfgBBBB"),
        ),
    )
    entry = _rule(report, "manifest_mismatch")
    assert entry["severity"] == "ok", entry["message"]
    assert report["ok"] is True


def test_a_proposal_is_comparable_with_its_own_baseline(pe):
    """The candidate-vs-baseline comparison, which the full config_hash refused."""
    report = pe.gate_lint(
        _run(_healthy_pops()),
        compare_manifest=(
            _manifest(overrides={}),
            _manifest(config_hash="cfgCCCC",
                      overrides={"carrying_capacity": 420}),
        ),
    )
    entry = _rule(report, "manifest_mismatch")
    assert entry["severity"] == "ok", entry["message"]
    assert report["ok"] is True


def test_undeclared_drift_is_refused_even_when_the_full_hash_agrees(pe):
    """A stale `config_hash` must not buy a comparison: `base_config_hash` is
    compared independently, so drift nobody declared still fails."""
    report = pe.gate_lint(
        _run(_healthy_pops()),
        compare_manifest=(
            _manifest(config_hash="same", base_config_hash="base1111"),
            _manifest(config_hash="same", base_config_hash="base2222"),
        ),
    )
    assert report["ok"] is False
    assert _rule(report, "manifest_mismatch")["severity"] == "blocking"


def test_comparison_is_labelled_so_the_reader_knows_which_it_is(pe):
    """A replicate check and a proposal check are different claims; say which."""
    replicate = _rule(
        pe.gate_lint(_run(_healthy_pops()),
                     compare_manifest=(_manifest(), _manifest(seed=999))),
        "manifest_mismatch",
    )
    assert "replicate" in replicate["message"]
    proposal = _rule(
        pe.gate_lint(_run(_healthy_pops()), compare_manifest=(
            _manifest(overrides={}),
            _manifest(config_hash="cfgDDDD", overrides={"carrying_capacity": 420}),
        )),
        "manifest_mismatch",
    )
    assert "proposal" in proposal["message"]
    assert "carrying_capacity" in proposal["message"]


# --- every manifest in a multi-run comparison is checked --------------------


def test_an_intermediate_manifest_mismatch_is_caught(pe):
    """Three paths, the middle one drifted: comparing only first-vs-last passes
    the drift through and the table then reports a gate delta that means nothing."""
    report = pe.gate_lint(
        _run(_healthy_pops()),
        compare_manifest=(
            _manifest(),
            _manifest(git_sha="deadbee"),
            _manifest(),
        ),
    )
    assert report["ok"] is False
    entry = _rule(report, "manifest_mismatch")
    assert entry["severity"] == "blocking"
    assert "1" in entry["message"], entry["message"]


def test_every_manifest_is_checked_not_just_the_last(pe):
    report = pe.gate_lint(
        _run(_healthy_pops()),
        compare_manifest=(_manifest(), _manifest(), _manifest(omp_num_threads="8")),
    )
    assert report["ok"] is False
    assert _rule(report, "manifest_mismatch")["severity"] == "blocking"


def test_a_clean_chain_of_four_manifests_compares(pe):
    report = pe.gate_lint(
        _run(_healthy_pops()),
        compare_manifest=(_manifest(seed=42), _manifest(seed=123),
                          _manifest(seed=999), _manifest(seed=7)),
    )
    assert _rule(report, "manifest_mismatch")["severity"] == "ok"
    assert report["ok"] is True


# --- absent manifests must be reported as absent ----------------------------


def test_two_absent_manifests_report_absence_not_agreement(pe):
    """(None or {}).get(k) is None for every key, so a legacy pair used to print
    'manifests agree on ...' — an agreement nobody checked."""
    report = pe.gate_lint(_run(_healthy_pops()), compare_manifest=(None, None))
    entry = _rule(report, "manifest_mismatch")
    assert entry["severity"] == "warning"
    assert "absent" in entry["message"]
    assert "agree" not in entry["message"]


def test_one_absent_manifest_blocks_the_comparison(pe):
    report = pe.gate_lint(
        _run(_healthy_pops()), compare_manifest=(_manifest(), None)
    )
    assert report["ok"] is False
    entry = _rule(report, "manifest_mismatch")
    assert entry["severity"] == "blocking"
    assert "absent" in entry["message"]


def test_a_manifest_missing_a_compare_key_is_not_vacuous_agreement(pe):
    """A pre-fix artifact has no `base_config_hash`; reading that as agreement
    would be exactly the false all-clear this rule exists to prevent."""
    legacy = {k: v for k, v in _manifest().items() if k != "base_config_hash"}
    report = pe.gate_lint(
        _run(_healthy_pops()), compare_manifest=(legacy, legacy)
    )
    assert report["ok"] is False
    entry = _rule(report, "manifest_mismatch")
    assert entry["severity"] == "blocking"
    assert "base_config_hash" in entry["message"]


def test_no_comparison_requested_is_not_a_manifest_verdict(pe):
    entry = _rule(pe.gate_lint(_run(_healthy_pops())), "manifest_mismatch")
    assert entry["severity"] == "ok"
    assert "no comparison" in entry["message"]


# --- the same rules, through the --osc-compare call site --------------------


def _artifact(pe, path, world, seed, manifest, K=380, embed=True):
    """A run-shaped artifact with a manifest beside it, for osc_compare."""
    payload = {
        "meta": {"world": world},
        "metrics": {
            "seed": seed, "N_mean": K, "N_min": K, "N_max": K, "N_cv": 0.0,
            "amplitude": 0.0, "band_width": 0, "drift_rate": 0.0,
            "reversals_per_72k": 0.0, "old_age_burstiness": 1.0,
            "old_age_bins_median": 1.0, "old_age_total": 10,
            "min_n_frac": 1.0, "starvation_total": 1, "xi_mean": 0.2,
        },
        "gates": [], "passed": True, "sample": SAMPLE,
        "samples": [
            {"tick": (i + 1) * SAMPLE, "pop": K, "food": 400, "xi": 0.2,
             "age_mult": 1.0, "season_mult": 1.0,
             "deaths": {"old_age": 1, "starvation": 1}}
            for i in range(30)
        ],
    }
    with open(path, "w") as f:
        json.dump(payload, f)
    if embed:
        payload["meta"]["manifest"] = manifest
        with open(path, "w") as f:
            json.dump(payload, f)
    with open(pe.manifest_path_for(path), "w") as f:
        json.dump(manifest, f)
    return path


def test_osc_compare_checks_every_manifest_not_just_the_first_and_last(pe, tmp_path, capsys):
    """The call site used to hand `(manifests[0], manifests[-1])` to the linter, so
    a drifted run in the middle of a three-way comparison passed unnoticed."""
    paths = [
        _artifact(pe, str(tmp_path / f"oscillation_B_{s}.json"), "B", s, _manifest(seed=s))
        for s in (42, 123, 999)
    ]
    _artifact(pe, paths[1], "B", 123, _manifest(seed=123, git_sha="deadbee"))
    pe.osc_compare(paths)
    out = capsys.readouterr().out
    assert "REFUSING TO COMPARE" in out
    assert "1" in out.split("MANIFEST:")[1].splitlines()[0], out


def test_osc_compare_accepts_a_multi_seed_comparison(pe, tmp_path, capsys):
    """The comparison the recorded suite is made of: same run, three seeds.
    A different seed is a different replicate of one config, so `config_hash`
    agrees and this is reported as the replicate check it is."""
    paths = [
        _artifact(pe, str(tmp_path / f"oscillation_B_{s}.json"), "B", s,
                  _manifest(seed=s))
        for s in (42, 123, 999)
    ]
    pe.osc_compare(paths)
    out = capsys.readouterr().out
    assert "REFUSING TO COMPARE" not in out
    assert "replicate" in out


def test_osc_compare_reports_absent_manifests(pe, tmp_path, capsys):
    """Legacy artifacts: the honest answer is 'unverified', not 'agree'."""
    paths = []
    for s in (42, 123):
        p = str(tmp_path / f"oscillation_B_{s}.json")
        _artifact(pe, p, "B", s, _manifest(), embed=False)
        os.remove(pe.manifest_path_for(p))
        paths.append(p)
    pe.osc_compare(paths)
    out = capsys.readouterr().out
    assert "absent" in out.split("MANIFEST:")[1]
    assert "REFUSING TO COMPARE" not in out


# --- the admissible region is reported next to the measurement --------------


def test_admissible_region_reports_measured_and_allowed_D_r(pe):
    run = _run([380 + (i % 7) - 3 for i in range(300)])
    report = pe.gate_lint(run)
    a = report["admissible"]
    for key in ("D_obs", "r_obs", "D_max", "r_max", "T_req"):
        assert key in a, f"missing {key}"
    assert a["D_obs"] == 6
    assert a["D_max"] > 0 and a["r_max"] > 0
    assert a["D_max"] == pytest.approx(min(0.25, 0.08 * math.sqrt(12)) * 380)
    assert a["r_max"] == pytest.approx(a["D_max"] / a["T_req"])


def test_admissible_region_flags_an_oversized_band(pe):
    wide = [380 + 200 * math.sin(2 * math.pi * i / 40) for i in range(300)]
    report = pe.gate_lint(_run(wide))
    assert report["admissible"]["D_in_region"] is False
    assert report["admissible"]["D_obs"] > report["admissible"]["D_max"]


def test_admissible_region_accepts_a_narrow_band(pe):
    narrow = [380 + 5 * math.sin(2 * math.pi * i / 40) for i in range(300)]
    report = pe.gate_lint(_run(narrow))
    assert report["admissible"]["D_in_region"] is True
