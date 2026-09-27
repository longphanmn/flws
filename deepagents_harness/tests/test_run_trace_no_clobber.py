"""Task 9b — a run may never overwrite another run.

Found by the first real G2 smoke, not by a test: the baseline and the candidate both
resolved to `<root>/B_42/B_42.json`, the candidate overwrote the baseline, and the
campaign then reported a signed delta of 0.0 — a run compared with itself. The
mechanism that noticed it was the ledger refusing to confirm a prediction whose delta
was exactly zero, which is the only reason the number was ever looked at.

`default_out_path` derived its run_id from world+seed, so two runs of the same world
and seed collided silently. Two guards now, and both are tested:

* the default run_id is unique per call, so a collision cannot be constructed by
  omission, and
* an existing artifact is never overwritten, so a collision that is constructed
  anyway fails loudly instead of destroying the earlier run's evidence.
"""
import json
import os

import pytest

from deepagents_harness import _flws


def test_two_default_paths_for_the_same_world_and_seed_differ(tmp_path):
    from deepagents_harness.tools import default_out_path

    a = default_out_path("B", 42, root=str(tmp_path))
    b = default_out_path("B", 42, root=str(tmp_path))
    assert a != b


def test_the_default_paths_are_still_inside_the_sweep_root(tmp_path):
    from deepagents_harness.tools import default_out_path

    a = default_out_path("B", 42, root=str(tmp_path))
    b = default_out_path("B", 42, root=str(tmp_path))
    for p in (a, b):
        assert os.path.abspath(p).startswith(os.path.abspath(str(tmp_path)) + os.sep)


def test_a_second_run_does_not_clobber_the_first_artifact(tmp_path):
    from deepagents_harness.tools import run_trace

    first = run_trace("B", 42, ticks=100, root=str(tmp_path))
    with open(first) as f:
        before = json.load(f)

    second = run_trace("B", 42, ticks=100, root=str(tmp_path))
    assert second != first
    with open(first) as f:
        assert json.load(f) == before, "the first run's artifact was overwritten"


def test_refuses_to_overwrite_an_existing_artifact(tmp_path):
    from deepagents_harness.tools import run_trace

    out = run_trace("B", 42, ticks=100, root=str(tmp_path))
    with pytest.raises(FileExistsError):
        run_trace("B", 42, ticks=100, out=out, root=str(tmp_path))


def test_the_refusal_names_the_existing_artifact(tmp_path):
    from deepagents_harness.tools import run_trace

    out = run_trace("B", 42, ticks=100, root=str(tmp_path))
    with pytest.raises(FileExistsError) as exc:
        run_trace("B", 42, ticks=100, out=out, root=str(tmp_path))
    assert os.path.basename(out) in str(exc.value)


def test_an_overwrite_is_possible_only_when_asked_for_explicitly(tmp_path):
    from deepagents_harness.tools import run_trace

    out = run_trace("B", 42, ticks=100, root=str(tmp_path))
    again = run_trace("B", 42, ticks=100, out=out, root=str(tmp_path), overwrite=True)
    assert again == out


def test_the_smoke_keeps_its_baseline_and_candidate_in_separate_files(smoke_env):
    from deepagents_harness.smoke import run_g2_smoke

    out = run_g2_smoke(**smoke_env)
    assert out["baseline_path"] != out["candidate_path"]
    assert os.path.exists(out["baseline_path"])
    assert os.path.exists(out["candidate_path"])


def test_the_smoke_declares_the_candidate_levers_and_the_baseline_declares_none(smoke_env):
    from deepagents_harness.smoke import run_g2_smoke

    out = run_g2_smoke(**smoke_env)
    base = _flws.gates().read_run_manifest(out["baseline_path"])
    cand = _flws.gates().read_run_manifest(out["candidate_path"])
    assert base["overrides"] == {}
    assert cand["overrides"] == out["g2_levers"]


def test_the_two_manifests_differ_so_the_comparison_is_not_a_run_against_itself(smoke_env):
    from deepagents_harness.smoke import run_g2_smoke

    out = run_g2_smoke(**smoke_env)
    g = _flws.gates()
    base = g.read_run_manifest(out["baseline_path"])
    cand = g.read_run_manifest(out["candidate_path"])
    assert base["config_hash"] != cand["config_hash"]
    assert base["base_config_hash"] == cand["base_config_hash"]
