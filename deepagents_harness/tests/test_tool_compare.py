"""Task 5 — tool 5: compare.

§6 L277: ``compare(paths)`` -> gate table; pure function, no judgement. The one
judgement-shaped thing it must do is *refuse*: §6 L310 and §13 L553 make manifest
equality a precondition for reading a gate delta, and Phase 1 issue 3 found that
``osc_compare`` compared only the first and last manifest, so a drifted run in the
middle of a three-way comparison was reported as if the whole set were comparable.

The table rows are the deterministic ``read_metrics`` verdict. This tool never
authors one.
"""
import json

import pytest

from deepagents_harness import _flws


def _write(tmp_path, name, seed=42, overrides=None, base_overrides=None, ticks=1000):
    """Write an artifact + manifest the way osc_ab_run does."""
    g = _flws.gates()
    cfg = g._osc_config(seed, overrides=overrides)
    base = g._osc_config(seed, overrides=base_overrides)
    manifest = g.build_run_manifest(
        cfg, argv=["pytest"], total_ticks=ticks, burn_in=0, sample=100,
        seam="harness-replace", overrides=overrides or {}, base_cfg=base,
    )
    m = {
        "seed": seed, "K": 380.0, "N_mean": 380.0, "N_min": 370, "N_max": 390,
        "N_cv": 0.02, "amplitude": 0.05, "band_width": 20, "drift_rate": 0.001,
        "reversals": 1, "reversals_per_72k": 7.2, "old_age_bins_median": 2,
        "old_age_bins_max": 3, "old_age_burstiness": 1.5, "starvation_total": 1,
        "old_age_total": 40, "min_n_frac": 0.97, "food_mean": 400.0,
        "food_min": 390, "food_max": 410, "xi_mean": 0.2, "xi_max": 0.4,
        "ms_per_tick": 40.0,
    }
    passed, checks = g.osc_gate_report(m, flat=True)
    path = str(tmp_path / name)
    with open(path, "w") as f:
        json.dump(
            {
                "meta": {"world": "B", "manifest": manifest},
                "metrics": m,
                "gates": [{"name": n, "pass": ok, "status": g._gate_status(ok),
                           "value": v} for n, ok, v in checks],
                "passed": passed,
                "samples": [],
            },
            f,
        )
    g.write_run_manifest(path, manifest)
    return path


def test_returns_one_row_per_run_with_the_gate_values(tmp_path):
    from deepagents_harness.tools import compare

    a = _write(tmp_path, "a.json", seed=42)
    b = _write(tmp_path, "b.json", seed=123)
    out = compare([a, b])
    assert [r["seed"] for r in out["rows"]] == [42, 123]
    assert out["rows"][0]["N_cv"] == 0.02
    assert len(out["rows"][0]["gates"]) == 5


def test_comparable_when_only_the_seed_differs(tmp_path):
    from deepagents_harness.tools import compare

    a = _write(tmp_path, "a.json", seed=42)
    b = _write(tmp_path, "b.json", seed=123)
    out = compare([a, b])
    assert out["comparable"] is True
    assert out["manifest_rule"]["severity"] != "blocking"


def test_comparable_when_a_candidate_carries_a_declared_proposal(tmp_path):
    from deepagents_harness.tools import compare

    base = _write(tmp_path, "base.json", seed=42)
    cand = _write(tmp_path, "cand.json", seed=42,
                  overrides={"population_envelope_enabled": True,
                             "pop_env_lo_frac": 0.96})
    out = compare([base, cand])
    assert out["comparable"] is True
    assert out["rows"][1]["declared_levers"] == {
        "population_envelope_enabled": True, "pop_env_lo_frac": 0.96
    }


def test_refuses_when_an_undeclared_field_drifted(tmp_path):
    from deepagents_harness.tools import compare

    a = _write(tmp_path, "a.json", seed=42)
    b = _write(tmp_path, "b.json", seed=42, base_overrides={"width": 500})
    out = compare([a, b])
    assert out["comparable"] is False
    assert out["manifest_rule"]["rule"] == "manifest_mismatch"
    assert out["manifest_rule"]["severity"] == "blocking"


def test_refuses_when_an_intermediate_run_drifted(tmp_path):
    from deepagents_harness.tools import compare

    a = _write(tmp_path, "a.json", seed=42)
    drifted = _write(tmp_path, "drift.json", seed=123, base_overrides={"width": 500})
    c = _write(tmp_path, "c.json", seed=999)
    out = compare([a, drifted, c])
    assert out["comparable"] is False
    assert "1" in out["manifest_rule"]["message"]


def test_absent_manifests_are_unverified_not_agreement(tmp_path):
    from deepagents_harness.tools import compare

    paths = []
    for name, seed in (("x.json", 42), ("y.json", 123)):
        p = str(tmp_path / name)
        with open(p, "w") as f:
            json.dump({"meta": {"world": "B"}, "metrics": {"seed": seed},
                       "gates": [], "passed": False, "samples": []}, f)
        paths.append(p)
    out = compare(paths)
    assert out["comparable"] is False
    assert out["manifest_rule"]["severity"] == "warning"
    assert "unverified" in out["manifest_rule"]["message"].lower()


def test_the_table_is_labelled_unverified_when_it_may_not_be_read(tmp_path):
    from deepagents_harness.tools import compare

    a = _write(tmp_path, "a.json", seed=42)
    b = _write(tmp_path, "b.json", seed=123, base_overrides={"width": 500})
    out = compare([a, b])
    assert out["delta_readable"] is False
    assert "reference" in out["note"].lower()


def test_is_pure_no_writes_and_repeatable(tmp_path):
    from deepagents_harness.tools import compare

    a = _write(tmp_path, "a.json", seed=42)
    b = _write(tmp_path, "b.json", seed=123)
    before = {p: open(p).read() for p in (a, b)}
    first = compare([a, b])
    second = compare([a, b])
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert {p: open(p).read() for p in (a, b)} == before


def test_refuses_an_empty_path_list():
    from deepagents_harness.tools import compare

    with pytest.raises(ValueError):
        compare([])
