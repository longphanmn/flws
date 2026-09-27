"""Fix pass 1 — the absent-vs-agree class.

Every finding here is the same defect wearing different clothes: something the code did
NOT check, reported as though it had. This project's premise is "report, don't hide",
so a false all-clear is the highest-grade defect it has, and it appeared in five
places. Each test below fails against the code as it stood.

C1/I4  the smoke closed a gate-3 card while its own lint said gates 1-4 unreachable
C3     gate_lint(<path>) with no samples reported the periodicity check as ok
C4     compare([one_path]) reported the comparison verified
C5     read_metrics reported verdict_consistent=True when no verdict was stored
I1     compare quoted a hand-edited verdict instead of re-deriving it
I2     compare mapped an absent `gates` key to []
I3     read_run_manifest reported manifest presence under the key `comparable`
"""
import json

import pytest

from deepagents_harness import _flws


def _artifact(tmp_path, name, *, samples=True, gates=True, passed=True, **metrics):
    g = _flws.gates()
    m = {
        "seed": 42, "K": 380.0, "N_mean": 380.0, "N_min": 370, "N_max": 390,
        "N_cv": 0.02, "amplitude": 0.05, "band_width": 20, "drift_rate": 0.001,
        "reversals": 1, "reversals_per_72k": 7.2, "old_age_bins_median": 2,
        "old_age_bins_max": 3, "old_age_burstiness": 1.5, "starvation_total": 1,
        "old_age_total": 40, "min_n_frac": 0.97, "food_mean": 400.0,
        "food_min": 390, "food_max": 410, "xi_mean": 0.2, "xi_max": 0.4,
        "ms_per_tick": 40.0,
    }
    m.update(metrics)
    payload = {"meta": {"world": "B"}, "metrics": m, "passed": passed,
               "gates": [{"name": "CV(N)<=0.08", "pass": True, "value": m["N_cv"]}],
               "samples": [{"tick": 100, "pop": 380.0, "food": 400, "xi": 0.2,
                            "age_mult": 1.0, "season_mult": 1.0,
                            "deaths": {"old_age": 2, "starvation": 0}}] * 30}
    if not samples:
        payload.pop("samples")
    if not gates:
        payload.pop("gates")
    if not passed:
        payload.pop("passed")
    path = str(tmp_path / name)
    with open(path, "w") as f:
        json.dump(payload, f)
    manifest = g.build_run_manifest(
        g._osc_config(42), argv=["t"], total_ticks=1000, burn_in=0, sample=100,
        seam="harness-replace", overrides={}, base_cfg=g._osc_config(42))
    g.write_run_manifest(path, manifest)
    return path


# --- C3 ---------------------------------------------------------------------

def test_gate_lint_on_a_path_with_no_samples_does_not_pass_the_periodicity_check(tmp_path):
    from deepagents_harness.tools import gate_lint

    p = _artifact(tmp_path, "nos.json", samples=False)
    out = gate_lint(p)
    f3 = next(r for r in out["rules"] if r["rule"] == "F3_no_periodicity")
    assert f3["severity"] == "unknown", f3


def test_gate_lint_on_a_path_with_an_empty_samples_list_is_also_unknown(tmp_path):
    from deepagents_harness.tools import gate_lint

    g = _flws.gates()
    p = str(tmp_path / "empty.json")
    with open(p, "w") as f:
        json.dump({"meta": {"world": "B"},
                   "metrics": {"xi_mean": 0.2, "old_age_bins_median": 2,
                               "old_age_burstiness": 1.5, "old_age_total": 4,
                               "N_mean": 380.0, "band_width": 1,
                               "drift_rate": 0.0},
                   "samples": [], "passed": True}, f)
    out = gate_lint(p)
    f3 = next(r for r in out["rules"] if r["rule"] == "F3_no_periodicity")
    assert f3["severity"] == "unknown", f3
    assert out["ok"] is False


# --- C4 ---------------------------------------------------------------------

def test_compare_of_a_single_path_is_not_a_comparison(tmp_path):
    from deepagents_harness.tools import compare

    p = _artifact(tmp_path, "one.json")
    out = compare([p])
    assert out["comparable"] is False
    assert out["delta_readable"] is False
    assert "no comparison" in out["note"].lower()


def test_compare_refuses_the_same_path_twice(tmp_path):
    from deepagents_harness.tools import compare

    p = _artifact(tmp_path, "one.json")
    out = compare([p, p])
    assert out["comparable"] is False
    assert "itself" in out["note"].lower()


# --- C5 ---------------------------------------------------------------------

def test_read_metrics_does_not_call_an_absent_verdict_consistent(tmp_path):
    from deepagents_harness.tools import read_metrics

    p = _artifact(tmp_path, "noverdict.json", passed=None)
    out = read_metrics(p)
    assert out["stored_passed"] is None
    assert out["verdict_present"] is False
    assert out["verdict_consistent"] is None


def test_read_metrics_flags_a_non_boolean_stored_verdict(tmp_path):
    from deepagents_harness.tools import read_metrics

    p = _artifact(tmp_path, "strverdict.json")
    with open(p) as f:
        payload = json.load(f)
    payload["passed"] = "false"
    with open(p, "w") as f:
        json.dump(payload, f)
    out = read_metrics(p)
    assert out["verdict_consistent"] is False


# --- I1 / I2 ----------------------------------------------------------------

def test_compare_re_derives_each_rows_verdict_and_flags_a_tampered_one(tmp_path):
    from deepagents_harness.tools import compare

    a = _artifact(tmp_path, "a.json")
    b = _artifact(tmp_path, "b.json", N_cv=0.9, passed=True)
    out = compare([a, b])
    tampered = out["rows"][1]
    assert tampered["passed"] is False, "compare quoted the hand-edited passed:true"
    assert tampered["verdict_consistent"] is False
    assert out["rows"][0]["verdict_consistent"] is True


def test_compare_reports_a_row_with_no_gates_as_absent_not_green(tmp_path):
    from deepagents_harness.tools import compare

    a = _artifact(tmp_path, "a.json")
    b = _artifact(tmp_path, "b.json", gates=None)
    row = compare([a, b])["rows"][1]
    assert row["gates_present"] is False
    assert row["gates"] is None


# --- I3 ---------------------------------------------------------------------

def test_read_run_manifest_reports_provenance_presence_not_comparability(tmp_path):
    from deepagents_harness.tools import read_run_manifest

    p = _artifact(tmp_path, "a.json")
    out = read_run_manifest(p)
    assert out["has_provenance"] is True
    assert "comparable" not in out, (
        "a manifest existing says nothing about comparability to another run; "
        "the key name claimed a check that was never done"
    )


# --- C1 / I4 ----------------------------------------------------------------

def test_a_gate_the_lint_calls_unreachable_is_not_scored(smoke_env):
    """The headline fix.

    The delivered G2 campaign closed its card `falsified` on gate 3 while the same
    run's lint said gates 1-4 were unreachable: xi_mean=0.0 means the controller
    never engaged, and 1000 ticks gives 10 samples, so reversals_per_72k sits at its
    floor of 0.0 and cannot move. A card must not be scored on a gate the run could
    not exercise.
    """
    from deepagents_harness.smoke import run_g2_smoke

    out = run_g2_smoke(**smoke_env)
    assert out["verdict"]["status"] == "inconclusive"
    assert "unreachable" in out["verdict"]["reason"].lower()
    assert out["card_status"] == "open"


def test_the_smoke_lints_the_real_artifact_not_the_read_metrics_envelope(smoke_env):
    """I4: the lint was fed the read_metrics envelope, which has no `samples` and no
    nested metrics, so F5/F6 read keys that were not there and D_in_region came out
    true for a dict with no N_mean."""
    from deepagents_harness.smoke import run_g2_smoke

    out = run_g2_smoke(**smoke_env)
    lint = next(s for s in out["steps"] if s["step"] == "baseline_lint")
    assert lint["metrics_seen"] is True
    # D_max is derived from N_mean, so a positive D_max proves the linter was fed
    # real metrics. It came out 0.0 when it was handed the read_metrics envelope.
    assert lint["admissible"]["D_max"] > 0, (
        "admissible region computed from a dict with no N_mean"
    )


def test_the_smoke_names_the_gate_it_would_not_score(smoke_env):
    from deepagents_harness.smoke import run_g2_smoke

    out = run_g2_smoke(**smoke_env)
    assert out["verdict"]["unreachable_gates"], "the unreachable gates went missing from the verdict"
