"""Phase 1 I — a run manifest next to every gate artifact.

The oscillation harness builds its Config in-process and never touches the DB,
so nothing in `oscillation_*.json` records which code, which resolved fields,
which argv, which tick budget or which thread count produced a run. Two
artifacts with the same filename pattern are therefore not known to be
comparable, and a gate delta between them proves nothing.

These tests pin the manifest's contents, its stability, that it lands next to
its artifact, and that a real (short) `osc_ab_run` writes one.
"""

import importlib.util
import json
import os
from dataclasses import replace

import pytest

_HARNESS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "scripts", "preset_experiment.py",
)
REQUIRED_KEYS = ("git_sha", "config_hash", "argv", "tick_budget", "omp_num_threads")


def _load():
    spec = importlib.util.spec_from_file_location("preset_experiment_manifest_test", _HARNESS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def pe():
    return _load()


@pytest.fixture
def cfg():
    from app.config import Config

    return Config(width=400, height=300, seed=42)


# --- contents ---------------------------------------------------------------


def test_manifest_carries_every_required_field(pe, cfg):
    man = pe.build_run_manifest(
        cfg, argv=["--osc-run"], total_ticks=1000, burn_in=200, sample=100
    )
    for key in REQUIRED_KEYS:
        assert key in man, f"manifest is missing {key}"
    assert man["seam"] == "harness-replace"


def test_manifest_records_git_sha(pe, cfg):
    man = pe.build_run_manifest(
        cfg, argv=[], total_ticks=10, burn_in=0, sample=100
    )
    assert isinstance(man["git_sha"], str) and man["git_sha"]
    assert man["git_sha"] == pe._git_sha()


def test_manifest_records_the_full_tick_budget(pe, cfg):
    man = pe.build_run_manifest(
        cfg, argv=["x"], total_ticks=120000, burn_in=20000, sample=100
    )
    assert man["tick_budget"] == {
        "total_ticks": 120000, "burn_in": 20000, "sample": 100,
    }


def test_manifest_records_argv(pe, cfg):
    man = pe.build_run_manifest(
        cfg, argv=["--osc-run", "--seed", "42"], total_ticks=10, burn_in=0, sample=100
    )
    assert man["argv"] == ["--osc-run", "--seed", "42"]


def test_manifest_records_omp_num_threads(pe, cfg, monkeypatch):
    monkeypatch.setenv("OMP_NUM_THREADS", "1")
    man = pe.build_run_manifest(cfg, argv=[], total_ticks=10, burn_in=0, sample=100)
    assert man["omp_num_threads"] == "1"
    monkeypatch.delenv("OMP_NUM_THREADS")
    man2 = pe.build_run_manifest(cfg, argv=[], total_ticks=10, burn_in=0, sample=100)
    assert man2["omp_num_threads"] == "<unset>"


# --- the config hash must actually discriminate -----------------------------


def test_config_hash_is_stable_for_the_same_config(pe, cfg):
    a = pe.config_hash(cfg)
    b = pe.config_hash(replace(cfg))
    assert a == b, "config hash must not depend on identity or dict order"
    assert len(a) == 16


def test_config_hash_changes_when_a_field_changes(pe, cfg):
    base = pe.config_hash(cfg)
    assert pe.config_hash(replace(cfg, damping_release_tau=120.0)) != base
    assert pe.config_hash(replace(cfg, damping_sigmoid_k=9.0)) != base
    assert pe.config_hash(replace(cfg, carrying_capacity=999)) != base


def test_config_hash_ignores_the_seed(pe, cfg):
    """The seed is the *replicate index*, not a configuration field.

    Hashing it made every multi-seed comparison fail on `config_hash`, which is
    the one comparison the whole recorded suite is made of.
    """
    assert pe.config_hash(replace(cfg, seed=7)) == pe.config_hash(cfg)
    assert pe.config_hash(replace(cfg, seed=999)) == pe.config_hash(cfg)


def test_manifest_records_the_seed_outside_the_hash(pe, cfg):
    """Seed is still provenance, it just does not travel inside the hash."""
    man = pe.build_run_manifest(
        cfg, argv=[], total_ticks=10, burn_in=0, sample=100
    )
    assert man["seed"] == cfg.seed


def test_manifest_records_the_config_it_was_derived_from(pe):
    """`base_config_hash` is the config *before* the proposal was applied, so a
    candidate run and its baseline can be compared on everything except the
    levers the proposal declares."""
    base = pe._osc_config(42)
    man = pe.build_run_manifest(
        pe._osc_config(42, overrides={"carrying_capacity": 420}),
        argv=[], total_ticks=10, burn_in=0, sample=100, base_cfg=base,
        overrides={"carrying_capacity": 420},
    )
    assert man["base_config_hash"] == pe.config_hash(base)


def test_a_proposal_leaves_the_base_config_hash_untouched(pe):
    base = pe._osc_config(42)
    bare = pe.build_run_manifest(
        base, argv=[], total_ticks=10, burn_in=0, sample=100
    )
    proposed = pe.build_run_manifest(
        pe._osc_config(42, overrides={"population_envelope_enabled": True}),
        argv=[], total_ticks=10, burn_in=0, sample=100, base_cfg=base,
        overrides={"population_envelope_enabled": True},
    )
    assert proposed["base_config_hash"] == bare["base_config_hash"]
    assert proposed["config_hash"] != bare["config_hash"], (
        "the full hash must still see the proposal — that is what makes it a "
        "provenance record rather than a licence to compare anything"
    )


def test_the_base_config_hash_ignores_the_seed(pe):
    """Two replicates of the same configuration are the same configuration."""
    a = pe.build_run_manifest(
        pe._osc_config(42), argv=[], total_ticks=10, burn_in=0, sample=100
    )
    b = pe.build_run_manifest(
        pe._osc_config(999), argv=[], total_ticks=10, burn_in=0, sample=100
    )
    assert a["base_config_hash"] == b["base_config_hash"]


def test_a_manifest_without_a_declared_base_falls_back_to_its_own_config(pe, cfg):
    """A run with no proposal is its own baseline."""
    man = pe.build_run_manifest(
        cfg, argv=[], total_ticks=10, burn_in=0, sample=100
    )
    assert man["base_config_hash"] == man["config_hash"]


def test_undeclared_drift_changes_the_base_config_hash(pe):
    """The drift guard: a field nobody declared as a lever still moves it."""
    a = pe._osc_config(42)
    b = replace(a, max_population=a.max_population + 1)
    drift = pe.build_run_manifest(
        b, argv=[], total_ticks=10, burn_in=0, sample=100
    )
    base = pe.build_run_manifest(
        a, argv=[], total_ticks=10, burn_in=0, sample=100
    )
    assert drift["base_config_hash"] != base["base_config_hash"]


# --- placement: next to the artifact ---------------------------------------


def test_manifest_path_is_next_to_the_artifact(pe):
    art = "/tmp/opencode/oscillation_B_42.json"
    mpath = pe.manifest_path_for(art)
    assert os.path.dirname(mpath) == os.path.dirname(art)
    assert mpath != art
    assert mpath.endswith(".json")


def test_manifest_paths_do_not_collide_across_runs(pe):
    a = pe.manifest_path_for("/tmp/x/oscillation_B_42.json")
    b = pe.manifest_path_for("/tmp/x/oscillation_B_999.json")
    assert a != b


def test_write_then_read_round_trips(pe, cfg, tmp_path):
    art = str(tmp_path / "oscillation_T_7.json")
    with open(art, "w") as f:
        json.dump({"passed": True}, f)
    man = pe.build_run_manifest(
        cfg, argv=["--osc-run"], total_ticks=100, burn_in=0, sample=100
    )
    written = pe.write_run_manifest(art, man)
    assert os.path.dirname(written) == str(tmp_path)
    assert pe.read_run_manifest(art) == man


def test_read_manifest_of_a_missing_artifact_is_none(pe, tmp_path):
    assert pe.read_run_manifest(str(tmp_path / "nope.json")) is None


# --- end to end: a real (short) run writes one ------------------------------


def test_osc_run_writes_a_manifest_next_to_its_artifact(pe, tmp_path):
    art = str(tmp_path / "oscillation_T0_42.json")
    payload = pe.osc_ab_run({
        "world": "B", "seed": 42, "out": art, "ticks": "200", "burn_in": "0",
    })
    assert os.path.exists(art)
    man = pe.read_run_manifest(art)
    assert man is not None, "osc_ab_run must leave a manifest beside its artifact"
    assert man["tick_budget"]["total_ticks"] == 200
    assert man["seam"] == "harness-replace"
    # the artifact embeds it too, so a copied JSON still carries its provenance
    assert payload["meta"]["manifest"]["config_hash"] == man["config_hash"]
    # and the run is linted with its measured-vs-admissible region
    assert "admissible" in payload["lint"]
    assert payload["lint"]["admissible"]["D_obs"] >= 0


def test_osc_run_lint_flags_the_unmeasurable_burstiness_gate(pe, tmp_path, capsys):
    """A 200-tick run cannot produce a measurable old-age burstiness; the lint
    must say so rather than letting it read as a dynamics failure."""
    art = str(tmp_path / "oscillation_T0_7.json")
    pe.osc_ab_run({
        "world": "B", "seed": 7, "out": art, "ticks": "200", "burn_in": "0",
    })
    out = capsys.readouterr().out
    assert "[lint]" in out
    assert "admissible D,r" in out
