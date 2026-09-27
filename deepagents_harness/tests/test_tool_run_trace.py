"""Task 6b — tool 4: run_trace, and the sandbox it writes inside.

§6 L276: ``run_trace(world, seed, ticks, burn_in, out)`` -> path; writes only to
``scripts/sweeps/<run_id>/``; OMP pinned to 1. Three guardrails, each a test here:

* the write is sandboxed. The historical ``scripts/oscillation_*.json`` datasets and
  ``/tmp/opencode/t0`` are the evidence base for every earlier phase; a trace that
  landed on one of them would destroy the record the gates are read against.
* OMP is pinned to 1. §13 L550-551: the C kernel hardcodes num_threads(4) on a
  4-core box, so a "parallel" harness makes each run ~2x slower. Sequential is the
  correct setting, not a concession.
* the budget wall is consulted before any tick is spent, never after.
"""
import json
import os

import pytest

from deepagents_harness import _flws


def test_the_default_trace_path_is_inside_scripts_sweeps():
    from deepagents_harness.tools import default_out_path

    out = default_out_path("B", 42)
    assert out.startswith(_flws.SWEEPS_DIR + os.sep)
    assert out.endswith(".json")


def test_refuses_an_out_path_outside_the_sweep_root(tmp_path):
    from deepagents_harness.tools import run_trace

    with pytest.raises(ValueError) as exc:
        run_trace("B", 42, ticks=100, out="/etc/passwd", root=str(tmp_path))
    assert "sweep" in str(exc.value).lower()


def test_refuses_a_traversal_that_would_land_on_a_historical_dataset(tmp_path):
    from deepagents_harness.tools import run_trace

    root = tmp_path / "sweeps"
    root.mkdir()
    with pytest.raises(ValueError):
        run_trace("B", 42, ticks=100,
                  out=str(tmp_path / ".." / "oscillation_B_42.json"),
                  root=str(root))


def test_refuses_to_overwrite_the_historical_oscillation_datasets_even_by_name(tmp_path):
    from deepagents_harness.tools import run_trace

    root = str(tmp_path)
    with pytest.raises(ValueError) as exc:
        run_trace("B", 42, ticks=100, out=os.path.join(root, "oscillation_B_42.json"),
                  root=root)
    assert "oscillation_" in str(exc.value)


def test_runs_a_trace_and_writes_the_artifact_and_its_manifest(tmp_path):
    from deepagents_harness.tools import run_trace

    out = run_trace("B", 42, ticks=100, burn_in=0, root=str(tmp_path))
    assert os.path.exists(out)
    assert os.path.exists(_flws.gates().manifest_path_for(out))
    with open(out) as f:
        payload = json.load(f)
    assert payload["metrics"]["seed"] == 42
    assert len(payload["gates"]) == 5
    assert "samples" in payload


def test_the_manifest_records_omp_pinned_to_one(tmp_path):
    from deepagents_harness.tools import run_trace

    out = run_trace("B", 42, ticks=100, root=str(tmp_path))
    manifest = _flws.gates().read_run_manifest(out)
    assert manifest["omp_num_threads"] == "1"
    assert manifest["seam"] == "harness-replace"
    assert manifest["tick_budget"]["total_ticks"] == 100


def test_the_manifest_records_the_declared_proposal(tmp_path):
    from deepagents_harness.tools import run_trace

    out = run_trace("B", 42, ticks=100, root=str(tmp_path),
                    overrides={"population_envelope_enabled": True,
                               "pop_env_lo_frac": 0.96})
    manifest = _flws.gates().read_run_manifest(out)
    assert manifest["overrides"] == {"population_envelope_enabled": True,
                                     "pop_env_lo_frac": 0.96}


def test_a_proposal_alongside_the_trace_is_recorded_as_its_baseline(tmp_path):
    """A candidate must be comparable to its own baseline (agy issue 2)."""
    from deepagents_harness.tools import run_trace

    out = run_trace("B", 42, ticks=100, root=str(tmp_path),
                    overrides={"population_envelope_enabled": True})
    manifest = _flws.gates().read_run_manifest(out)
    assert manifest["base_config_hash"] != manifest["config_hash"]


def test_spends_the_budget_wall_and_refuses_the_run_past_it(tmp_path):
    from deepagents_harness.budget import BudgetWall
    from deepagents_harness.tools import run_trace

    wall = BudgetWall(max_sim_runs=2)
    run_trace("B", 42, ticks=100, root=str(tmp_path), budget=wall)
    run_trace("B", 123, ticks=100, root=str(tmp_path), budget=wall)
    with pytest.raises(Exception) as exc:
        run_trace("B", 999, ticks=100, root=str(tmp_path), budget=wall)
    assert "2" in str(exc.value)


def test_the_wall_is_consulted_before_any_tick_is_spent(tmp_path):
    from deepagents_harness.budget import BudgetWall
    from deepagents_harness.tools import run_trace

    wall = BudgetWall(max_sim_runs=1)
    wall.spend("something else already used the only slot")
    before = set(os.listdir(tmp_path))
    with pytest.raises(Exception):
        run_trace("B", 42, ticks=100, root=str(tmp_path), budget=wall)
    # No artifact, no manifest, no partial output.
    assert set(os.listdir(tmp_path)) == before


def test_each_trace_gets_its_own_run_id_directory_by_default(tmp_path):
    from deepagents_harness.tools import default_out_path

    a = default_out_path("B", 42, root=str(tmp_path), run_id="r1")
    b = default_out_path("B", 42, root=str(tmp_path), run_id="r2")
    assert os.path.dirname(a) != os.path.dirname(b)
    assert a.startswith(str(tmp_path))
