"""Tests for the campaign driver (deepagents_harness/campaign.py).

Two properties are worth a test, and both are tripwires rather than coverage:

* **Every patch anchor still matches the served backend exactly once.** A candidate tree is
  built by string replacement. If someone edits ``creature_update.py`` and an anchor no
  longer matches, ``materialize_tree`` refuses -- but only when a campaign is running, and
  only for the tree that campaign happens to build. This test fails the moment the anchors
  drift, which is the difference between "the campaign noticed" and "the campaign silently
  measured the unmodified code and reported a delta of 0.0".
* **A metric no seed measured stays unmeasured.** ``_agg_metrics`` averages over the seeds
  that have a value and reports how many. A burstiness mean over 1 of 3 seeds presented as a
  mean over 3 is how an unmeasurable gate acquires a verdict.

The candidate trees themselves are not built here: a tree is a full copy of ``backend/`` and
copying it in a unit test buys nothing these two checks do not already cover.
"""
import json
import os
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from deepagents_harness import campaign as C  # noqa: E402
from deepagents_harness import _flws  # noqa: E402
from deepagents_harness.ledger import GATE_METRICS  # noqa: E402

# The gate module is the only source of truth for what a Config field is and for which
# keys the linter classes as scalar damping (F4). Read through the seam, never restated.
SCALAR_DAMPING_KEYS = _flws.gates().SCALAR_DAMPING_KEYS


# --- the anchors are a tripwire on the served source -------------------------

@pytest.mark.parametrize("patch_name", sorted(C.PATCHES))
def test_every_patch_anchor_matches_the_served_backend_exactly_once(patch_name):
    for rel, old, new, expect in C.PATCHES[patch_name]:
        path = os.path.join(C.SRC_BACKEND, rel)
        assert os.path.exists(path), f"{patch_name} patches a file that does not exist: {rel}"
        with open(path) as f:
            src = f.read()
        got = src.count(old)
        assert got == expect, (
            f"patch {patch_name} anchor on {rel} matched {got} time(s), expected {expect}. "
            f"The campaign would either refuse or, worse, apply a no-op and report the "
            f"served physics as a candidate. Anchor starts: {old[:70]!r}"
        )
        assert new != old, f"patch {patch_name} on {rel} replaces the anchor with itself"


def test_patches_touch_only_simulation_source_never_config_or_law_state():
    """A candidate must not be able to change the Config it is compared on, and must
    never reach law_state_v1 -- the one thing the harness is forbidden to write."""
    for patch_name, patches in C.PATCHES.items():
        for rel, _old, _new, _expect in patches:
            assert not rel.endswith("config.py"), f"{patch_name} patches config.py"
            assert "law_state" not in rel, f"{patch_name} touches law_state: {rel}"


def test_a_refused_anchor_stops_the_tree(monkeypatch, tmp_path):
    """A patch that does not apply must abort, not write a tree that measures nothing."""
    monkeypatch.setattr(C, "TREES_DIR", str(tmp_path / "trees"))
    monkeypatch.setitem(C.PATCHES, "BROKEN", [("app/entities.py", "no such anchor", "x", 1)])
    with pytest.raises(SystemExit) as exc:
        C.materialize_tree(["BROKEN"])
    assert "silent no-op" in str(exc.value)


# --- candidate declarations are legal proposals ------------------------------

def test_every_candidate_declares_a_topology_and_a_label():
    for key, spec in C.CANDIDATES.items():
        assert spec["topology"], key
        assert spec["label"], key
        assert isinstance(spec["overrides"], dict), key
        assert set(spec["mechanism_gates"]) <= set(GATE_METRICS), key


def test_no_candidate_is_a_scalar_damping_sweep():
    """F4: proportional-band constants cannot produce absorbing behaviour, and the
    brief forbids scalar sweeps outright."""
    for key, spec in C.CANDIDATES.items():
        scalar = sorted(set(spec["overrides"]) & set(SCALAR_DAMPING_KEYS))
        assert not scalar, f"{key} is a scalar damping sweep: {scalar}"
        assert set(spec["overrides"]) != set(SCALAR_DAMPING_KEYS), key


def test_every_override_is_a_config_field():
    """F4 again, from the other side: a key the simulation cannot read is a silent no-op
    that costs a full campaign to discover."""
    fields = _flws.gates().Config.__dataclass_fields__
    for key, spec in C.CANDIDATES.items():
        for k in spec["overrides"]:
            assert k in fields, f"{key}: {k!r} is not a Config field (dead knob)"


# --- aggregation must not invent a measurement -------------------------------

def test_agg_metrics_keeps_an_unmeasured_metric_unmeasured():
    rows = [
        {"metrics": {"old_age_burstiness": 28.0, "N_cv": 0.1}},
        {"metrics": {"old_age_burstiness": None, "N_cv": 0.3}},
        {"metrics": {"old_age_burstiness": None, "N_cv": 0.2}},
    ]
    agg = C._agg_metrics(rows)
    # burstiness measured on 1 of 3 seeds: the mean is over that one seed, and n says so.
    assert agg["old_age_burstiness"] == (28.0, 1)
    assert agg["N_cv"] == (pytest.approx(0.2), 3)


def test_agg_metrics_reports_none_when_no_seed_measured_it():
    rows = [{"metrics": {"old_age_burstiness": None}}, {"metrics": {}},
            {"metrics": {"old_age_burstiness": None}}]
    agg = C._agg_metrics(rows)
    assert agg["old_age_burstiness"] == (None, 0)
    # A None metric has no signed delta, so a card scored against it must be refused
    # rather than silently computed -- this is ledger._measure's contract.
    assert C.GATE_RESOLUTION[4] > 0


# --- the rung ladder is the one the brief asks for --------------------------

def test_rungs_are_sequential_and_cover_the_ladder():
    assert C.RUNGS["T0"]["ticks"] < C.RUNGS["T1"]["ticks"]
    assert C.RUNGS["T0"]["burn_in"] < C.RUNGS["T0"]["ticks"]
    assert C.RUNGS["T1"]["burn_in"] < C.RUNGS["T1"]["ticks"]
    assert C.SEEDS == (42, 123, 999), "multi-seed is mandatory (F6)"
    # CAMPAIGN-2's wall: 5 T1 candidates + at most one conditional 120k run_gate. These
    # are asserted because the wall is the thing that decides whether a run happens; a
    # silent change to it is a budget decision nobody made.
    assert C.BUDGET["max_t1_candidates"] == 6
    assert C.BUDGET["max_full_run_gate"] == 1
    assert C.BUDGET["max_sim_runs"] >= 6 + len(C.LADDER) * 2 * len(C.SEEDS)
    assert len(C.LADDER) <= C.BUDGET["max_t1_candidates"]
    assert C.BUDGET["deadline_s"] >= 12 * 3600


def test_ladder_order_puts_the_ablation_and_the_seasonal_gap_first():
    """The order is a measurement-driven decision (Ruling 5, then campaign-1's results),
    so it is asserted: if a future edit reorders it, the reason has to be re-derived
    rather than drifted into. Campaign-2 opens with the two rungs campaign-1 never
    measured at a scored rung -- the G1 ablation and the G2 seasonal gap -- and then
    tunes C3 toward 3/3."""
    assert C.LADDER[0] == "C1_G1_env", "the G1 ablation is the control row for everything"
    assert C.LADDER[1] == "C5_G2_food", "gate 5 / seasonal decoupling is the standing gap"
    assert C.LADDER[2:] == ["C3v1_G1xG4t", "C3v2_G1xG4haz", "C3v3_G1xG4deep"]


def test_no_c3_variant_touches_a_forbidden_knob():
    """The brief forbids scalar damping sweeps, law_state_v1, and any topology outside
    the G1/G4/G2/PD families. Each C3 variant changes exactly ONE of C3's own knobs:
    the ceiling's shape, the hazard's shape, or the band's lower bound."""
    variants = [k for k in C.LADDER if k.startswith("C3v")]
    assert len(variants) == 3, f"campaign-2 allows at most 3 C3 variants, got {variants}"
    for key in variants:
        spec = C.CANDIDATES[key]
        assert set(spec["overrides"]) <= {"population_envelope_enabled", "pop_env_lo_frac",
                                          "pop_env_hi_frac", "pop_env_lo_birth_boost"}, (
            f"{key} changes something other than the envelope band bounds")
        assert all(p in ("G4", "G4_EARLY", "G1T") for p in spec["patches"]), (
            f"{key} patches outside C3's own G1/G4 topology: {spec['patches']}")
    base_over = C.CANDIDATES["C3_G1xG4"]["overrides"]
    base_pat = set(C.CANDIDATES["C3_G1xG4"]["patches"])
    for key in variants:
        spec = C.CANDIDATES[key]
        over_diff = {k for k in set(spec["overrides"]) | set(base_over)
                     if spec["overrides"].get(k) != base_over.get(k)}
        assert len(over_diff) <= 1, f"{key} changes {sorted(over_diff)}: more than one knob"
        assert len(set(spec["patches"]) - base_pat - {"G4_EARLY"}) <= 1, (
            f"{key} adds more than one patch")
        # G4_EARLY is G4 with a different elder-onset fraction, so a variant that swaps
        # G4 for G4_EARLY has kept the hazard mechanism and changed its shape.
        assert {"G4", "G4_EARLY"} & set(spec["patches"]), (
            f"{key} drops the G4 hazard mechanism C3 owns")


# --- the exit path: a finished campaign must exit 0 -------------------------

def test_run_ladder_survives_a_system_exit_from_a_candidate_and_returns_zero(monkeypatch):
    """A driver refusal is a RESULT, not a crash.

    `Campaign.__init__`, `materialize_tree` and the budget wall all refuse with
    `SystemExit`, which is a `BaseException` and therefore slips past
    `except Exception`. An uncaught `SystemExit` in one candidate used to end the whole
    process with code 1 *after* the report had been written and the other candidates
    measured -- a complete campaign's results on disk and a failed exit status for the
    wrapper, which is the worst of both. KeyboardInterrupt/SIGTERM must still
    propagate, so only SystemExit is absorbed.
    """
    camp = C.Campaign(lock=False)
    seen = []

    monkeypatch.setattr(camp, "rung_linter", lambda: None)
    monkeypatch.setattr(camp, "do_rung", lambda cand, rung: {"rows": []})
    monkeypatch.setattr(camp, "write_summary", lambda key: seen.append(key))
    monkeypatch.setattr(camp, "save", lambda: None)

    def fake(cand_key, rungs=("T0", "T1")):
        if cand_key == "C1_G1_env":
            raise SystemExit("budget wall: refusing ...")
        return {"T0": {"rows": []}, "T1": {"rows": []}}

    monkeypatch.setattr(camp, "do_candidate", fake)
    rc = camp.run_ladder(["C1_G1_env", "C5_G2_food"])
    assert rc == 0, "a completed ladder must exit 0 even when a candidate refused"
    notes = " ".join(camp.report["notes"])
    assert "C1_G1_env" in notes and "SystemExit" in notes, notes
    assert seen == ["C1_G1_env", "C5_G2_food", "ALL"], seen


def test_run_ladder_does_not_swallow_a_keyboard_interrupt(monkeypatch):
    """Only SystemExit is absorbed. A SIGINT must stop the ladder, not be recorded."""
    camp = C.Campaign(lock=False)
    monkeypatch.setattr(camp, "rung_linter", lambda: None)
    monkeypatch.setattr(camp, "do_rung", lambda cand, rung: {"rows": []})
    monkeypatch.setattr(camp, "save", lambda: None)
    monkeypatch.setattr(camp, "write_summary", lambda key: None)

    def boom(cand_key, rungs=("T0", "T1")):
        raise KeyboardInterrupt

    monkeypatch.setattr(camp, "do_candidate", boom)
    with pytest.raises(KeyboardInterrupt):
        camp.run_ladder(["C1_G1_env"])


@pytest.mark.parametrize("argv,expected", [("--show", 0), ("", 2), ("--ladder", 0)])
def test_main_returns_an_int_exit_code_for_every_mode(monkeypatch, argv, expected):
    """`sys.exit(main() or 0)` collapses a falsy non-int (None) to 0 and a truthy
    non-int to SystemExit, so main() is pinned to return a real int for the modes a
    wrapper can actually invoke."""
    class _NoLock(C.Campaign):
        def __init__(self, **kw):
            kw["lock"] = False
            super().__init__(**kw)

    monkeypatch.setattr(C, "Campaign", _NoLock)
    monkeypatch.setattr(sys, "argv", ["campaign.py"] + ([argv] if argv else []))
    rc = C.main()
    assert isinstance(rc, int) and not isinstance(rc, bool)
    assert rc == expected


def test_worker_mode_returns_zero_not_none(monkeypatch, tmp_path):
    """`main()` returns `worker(...)`, which returned None. `None or 0` happens to be
    0, but a worker that ever returned a truthy value (a path, a dict) would have
    become `SystemExit(<non-int>)` and a non-zero exit. worker() is pinned to 0."""
    from deepagents_harness import tools as T

    spec = tmp_path / "spec.json"
    spec.write_text('{"world": "B", "seed": 42, "ticks": 1, "burn_in": 0, '
                    '"out": "/tmp/x.json", "overrides": {}, '
                    '"backend": "/tmp/tree", "reason": "test"}')
    monkeypatch.setitem(os.environ, "FLWS_BACKEND", "/tmp/tree")
    monkeypatch.setattr(T, "run_trace", lambda **kw: kw["out"])
    monkeypatch.setattr(T, "read_metrics", lambda p: {"metrics": {"ms_per_tick": 1.0}})
    assert C.worker(str(spec)) == 0
    monkeypatch.setattr(sys, "argv", ["campaign.py", "--worker", str(spec)])
    assert C.main() == 0


def test_the_report_records_the_wall_in_force_not_the_one_in_the_file(monkeypatch, tmp_path):
    """`__init__` builds the report with the CURRENT BUDGET and then merges the whole
    previous report over it -- which put campaign-1's wall (4 T1 candidates, 96 sim
    runs, 12 h) back into `budget_declared` on campaign-2, while the wall actually
    refusing runs was the new one. Found live: after five campaign-2 candidates the
    report still claimed max_t1_candidates 4. The report is the artifact of record, so
    a stale budget in it is a false statement about what governed the runs."""
    monkeypatch.setattr(C, "CAMPAIGN_DIR", str(tmp_path / "camp"))
    monkeypatch.setattr(C, "REPORT_PATH", str(tmp_path / "camp" / "campaign_report.json"))
    monkeypatch.setattr(C, "LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    os.makedirs(os.path.dirname(C.REPORT_PATH), exist_ok=True)
    with open(C.REPORT_PATH, "w") as f:
        json.dump({"budget_declared": {"max_t1_candidates": 4, "max_sim_runs": 96,
                                       "deadline_s": 43200},
                   "rungs": {"T0": {"ticks": 1}}, "ladder": [], "notes": []}, f)
    camp = C.Campaign(lock=False)
    assert camp.report["budget_declared"] == C.BUDGET, (
        "the report states a budget the wall did not enforce")
    # and the wall that is actually in force is the module's
    assert camp.budget.max_sim_runs == C.BUDGET["max_sim_runs"]
    assert camp.budget.deadline_s == C.BUDGET["deadline_s"]


def test_every_candidate_is_in_the_ladder_or_carries_a_written_exemption():
    """This test exists because it failed once. C6 was declared in CANDIDATES with a
    documented reason for not being run, and the reason lived only in a comment on the
    other entry -- so the default execution order silently omitted a declared candidate
    and nothing said so. A candidate that is neither scheduled nor exempted is a plan
    defect that costs a full T1 slot to discover."""
    unaccounted = sorted(set(C.CANDIDATES) - set(C.LADDER) - set(C.LADDER_EXEMPT))
    assert not unaccounted, f"candidates neither scheduled nor exempted: {unaccounted}"
    stale = sorted(set(C.LADDER_EXEMPT) - set(C.CANDIDATES))
    assert not stale, f"exemptions for candidates that do not exist: {stale}"
    assert sorted(set(C.LADDER) | set(C.LADDER_EXEMPT)) == sorted(C.CANDIDATES)
    for key, reason in C.LADDER_EXEMPT.items():
        assert len(reason) > 80, f"{key} exemption has no written reason"
