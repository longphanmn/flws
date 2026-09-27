"""Task 1 — tool 7: read_run_manifest.

Brainstorm §6 L279 asks for git sha, config hash, law-state hash, tick budget and
ms/tick. Four of those five are in the Phase 1 manifest schema. Two are not, and
the tool has to say so rather than invent them:

* ms/tick is recorded per run by osc_metrics, not by the manifest, so it is read
  from the artifact's own metrics.
* There is no law-state hash, and there must not be one: the gate path builds its
  Config in-process and never opens the SQLite law_state_v1 (F7/C4), so there is
  no law state to hash. Reporting a hash here would be a fabricated provenance
  claim about the one thing this harness is forbidden to touch.
"""
import json
import os

import pytest

from deepagents_harness import _flws


@pytest.fixture()
def artifact(tmp_path):
    """A real artifact + manifest, written by the Phase 1 manifest code itself."""
    g = _flws.gates()
    seed = 42
    cfg = g._osc_config(seed, overrides={"damping_release_tau": 250.0})
    base = g._osc_config(seed)
    manifest = g.build_run_manifest(
        cfg,
        argv=["pytest"],
        total_ticks=1000,
        burn_in=0,
        sample=100,
        seam="harness-replace",
        overrides={"damping_release_tau": 250.0},
        base_cfg=base,
    )
    path = str(tmp_path / "run.json")
    with open(path, "w") as f:
        json.dump({"metrics": {"seed": seed, "ms_per_tick": 61.25}}, f)
    g.write_run_manifest(path, manifest)
    return path


def test_returns_the_manifest_provenance_fields(artifact):
    from deepagents_harness.tools import read_run_manifest

    out = read_run_manifest(artifact)
    assert out["manifest_present"] is True
    assert out["git_sha"]
    assert out["config_hash"]
    assert out["base_config_hash"]
    assert out["tick_budget"] == {"total_ticks": 1000, "burn_in": 0, "sample": 100}
    assert out["omp_num_threads"]
    assert out["seam"] == "harness-replace"
    assert out["seed"] == 42


def test_returns_ms_per_tick_from_the_artifact_metrics(artifact):
    from deepagents_harness.tools import read_run_manifest

    assert read_run_manifest(artifact)["ms_per_tick"] == 61.25


def test_records_the_declared_proposal_so_a_candidate_is_not_mistaken_for_a_baseline(artifact):
    from deepagents_harness.tools import read_run_manifest

    assert read_run_manifest(artifact)["overrides"] == {"damping_release_tau": 250.0}


def test_law_state_is_reported_as_never_touched_never_hashed(artifact):
    from deepagents_harness.tools import read_run_manifest

    out = read_run_manifest(artifact)
    assert out["law_state_hash"] is None
    assert "law_state" in out["law_state_note"]
    assert "never" in out["law_state_note"]


def test_a_missing_manifest_is_reported_absent_not_as_agreement(tmp_path):
    from deepagents_harness.tools import read_run_manifest

    path = str(tmp_path / "legacy.json")
    with open(path, "w") as f:
        json.dump({"metrics": {"seed": 1, "ms_per_tick": 5.0}}, f)

    out = read_run_manifest(path)
    assert out["manifest_present"] is False
    # Reading an absent key through `(m or {}).get(k)` is how Phase 1 printed
    # "manifests agree" for two artifacts that had none (agy issue 5).
    assert out["git_sha"] is None
    assert out["config_hash"] is None
    assert out["has_provenance"] is False


def test_a_missing_artifact_raises_instead_of_returning_an_empty_dict(tmp_path):
    from deepagents_harness.tools import read_run_manifest

    with pytest.raises(FileNotFoundError):
        read_run_manifest(str(tmp_path / "nope.json"))


def test_manifest_version_is_reported_so_a_schema_drift_is_visible(artifact):
    from deepagents_harness.tools import read_run_manifest

    out = read_run_manifest(artifact)
    assert out["manifest_version"] == _flws.gates().MANIFEST_VERSION
    assert os.path.exists(_flws.gates().manifest_path_for(artifact))
