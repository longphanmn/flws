"""Task 9 — the G2 smoke, end to end.

G2 (brainstorm §6 L377): decouple N from the seasonal food target -- season-sized
larder/granary buffering, or make beds/territory the binding capacity. It is the one
topology that T0 alone cannot validate, which is why §12 Step 3 points the harness at
it.

What this smoke is for is the *loop*, not the ecology:

    open a card with a predicted signed gate delta  (before any tick)
      -> lint the candidate for structurally unreachable gates
      -> run baseline and candidate, sequential, OMP=1, inside the budget wall
      -> compare them (deterministic verdict, or a refusal to compare)
      -> close the card as confirmed or falsified

The G2 card's own verdict is whatever the measurement says. A falsified card is the
mechanism working, not a smoke failure -- so every test below checks that the smoke
*reports* faithfully, including when the budget wall stops it halfway.
"""
import json
import os

import pytest


def test_the_smoke_runs_the_whole_loop_and_returns_a_trace(smoke_env):
    from deepagents_harness.smoke import run_g2_smoke

    out = run_g2_smoke(**smoke_env)
    assert out["card_id"].startswith("card-0001-")
    assert out["prediction"]["direction"] in ("increase", "decrease")
    assert out["prediction"]["min_delta"] > 0
    # At 100 ticks the predicted gate is structurally unreachable, so the honest
    # verdict is inconclusive, not a confirmed/falsified pair. The first delivery
    # reported "falsified" here by scoring a metric pinned at its floor.
    assert out["verdict"]["status"] in ("confirmed", "falsified", "inconclusive")
    assert out["steps"]


def test_the_card_is_opened_before_the_first_run(smoke_env):
    from deepagents_harness.smoke import run_g2_smoke

    out = run_g2_smoke(**smoke_env)
    steps = {s["step"]: s for s in out["steps"]}
    assert steps["card_opened"]["ts"] <= steps["baseline_run"]["ts"]


def test_it_runs_a_baseline_and_a_candidate(smoke_env):
    from deepagents_harness.smoke import run_g2_smoke

    out = run_g2_smoke(**smoke_env)
    steps = {s["step"]: s for s in out["steps"]}
    assert os.path.exists(steps["baseline_run"]["path"])
    assert os.path.exists(steps["candidate_run"]["path"])


def test_both_artifacts_record_omp_pinned_to_one(smoke_env):
    from deepagents_harness.smoke import run_g2_smoke

    out = run_g2_smoke(**smoke_env)
    for s in out["steps"]:
        if s["step"].endswith("_run"):
            with open(s["path"]) as f:
                man = json.load(f)["meta"]["manifest"]
            assert man["omp_num_threads"] == "1"


def test_the_candidate_declares_the_g2_levers_it_moved(smoke_env):
    from deepagents_harness.smoke import run_g2_smoke

    out = run_g2_smoke(**smoke_env)
    cand = {s["step"]: s for s in out["steps"]}["candidate_run"]
    with open(cand["path"]) as f:
        man = json.load(f)["meta"]["manifest"]
    assert man["overrides"], "the candidate run declared no levers"
    assert set(man["overrides"]) <= set(out["g2_levers"]) | {"population_envelope_enabled"}


def test_every_artifact_is_written_inside_the_sweep_root(smoke_env):
    from deepagents_harness.smoke import run_g2_smoke

    out = run_g2_smoke(**smoke_env)
    root = os.path.abspath(smoke_env["root"])
    for s in out["steps"]:
        if s["step"].endswith("_run"):
            assert os.path.abspath(s["path"]).startswith(root + os.sep)


def test_it_never_touches_the_historical_datasets_or_the_t0_evidence(smoke_env):
    from deepagents_harness.smoke import run_g2_smoke

    repo_sweeps = os.path.abspath(
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "scripts", "sweeps"))
    out = run_g2_smoke(**smoke_env)
    for s in out["steps"]:
        if s["step"].endswith("_run"):
            assert not os.path.abspath(s["path"]).startswith(repo_sweeps + os.sep)
            assert "oscillation_" not in os.path.basename(s["path"])


def test_the_linter_is_consulted_before_the_candidate_run_is_paid_for(smoke_env):
    from deepagents_harness.smoke import run_g2_smoke

    out = run_g2_smoke(**smoke_env)
    names = [s["step"] for s in out["steps"]]
    assert names.index("proposal_check") < names.index("candidate_run")
    assert names.index("baseline_lint") < names.index("candidate_run")


def test_the_baseline_lint_finding_is_reported_rather_than_dropped(smoke_env):
    """A 100-tick baseline cannot score gates 1-4, and the trace must say so."""
    from deepagents_harness.smoke import run_g2_smoke

    out = run_g2_smoke(**smoke_env)
    lint = next(s for s in out["steps"] if s["step"] == "baseline_lint")
    assert lint["advisory"] is True
    assert "advisory" in lint["note"]
    assert isinstance(lint["unreachable_gates"], list)


def test_a_proposal_with_a_dead_knob_is_refused_before_a_single_tick(smoke_env):
    from deepagents_harness.smoke import run_g2_smoke

    smoke_env["levers"] = {"larder_capcity": 1200.0}  # misspelt
    out = run_g2_smoke(**smoke_env)
    names = [s["step"] for s in out["steps"]]
    assert "run_refused" in names
    assert "candidate_run" not in names
    assert out["budget"]["spent"] == 1  # the baseline only; no candidate was paid for
    # An invalid proposal is a failure, not an inconclusive result: something is
    # wrong and saying "inconclusive" would under-report it.
    assert out["verdict"]["status"] == "failed"
    assert "larder_capcity" in out["verdict"]["reason"]


def test_a_budget_too_small_for_the_candidate_is_reported_not_papered_over(smoke_env):
    from deepagents_harness.smoke import run_g2_smoke

    smoke_env["max_sim_runs"] = 1
    out = run_g2_smoke(**smoke_env)
    assert out["budget"]["spent"] == 1
    assert out["verdict"]["status"] == "inconclusive"
    assert "budget" in out["verdict"]["reason"].lower()
    # The card stays OPEN: an unrun candidate is not a falsified hypothesis.
    from deepagents_harness.ledger import Ledger

    assert Ledger(smoke_env["ledger_path"]).card(out["card_id"])["status"] == "open"


def test_the_smoke_spends_at_most_the_budget(smoke_env):
    from deepagents_harness.smoke import run_g2_smoke

    smoke_env["max_sim_runs"] = 3
    out = run_g2_smoke(**smoke_env)
    assert out["budget"]["spent"] <= 3
    assert out["budget"]["max_sim_runs"] == 3


def test_the_ledger_holds_exactly_one_card_after_the_smoke(smoke_env):
    from deepagents_harness.ledger import Ledger
    from deepagents_harness.smoke import run_g2_smoke

    out = run_g2_smoke(**smoke_env)
    cards = Ledger(smoke_env["ledger_path"]).cards()
    assert len(cards) == 1
    assert cards[0]["card_id"] == out["card_id"]


def test_the_smoke_reports_the_endpoint_status_without_leaking_the_key(smoke_env):
    from deepagents_harness.agent import load_credentials
    from deepagents_harness.smoke import run_g2_smoke

    creds = load_credentials("/root/.hermes/.env")
    out = run_g2_smoke(credentials=creds, **smoke_env)
    ep = out["endpoint"]
    # Configured now (DEEPAGENTS_BASE_URL in the env file) - the leak checks are
    # the point of this test and are unchanged.
    assert ep["endpoint_configured"] is True
    assert ep["api_key"] == "<redacted>"
    assert ep["provider"] == "opencode-go"
    blob = json.dumps(out, default=str)
    assert creds.api_key not in blob
    assert str(creds.base_url) not in blob or ep["base_url"] == str(creds.base_url)


def test_the_smoke_works_with_no_credentials_at_all(smoke_env):
    """The deterministic half must not depend on the LLM leg."""
    from deepagents_harness.smoke import run_g2_smoke

    out = run_g2_smoke(credentials=None, **smoke_env)
    assert out["endpoint"]["available"] is False
    assert out["verdict"]["status"] in ("confirmed", "falsified", "inconclusive")
