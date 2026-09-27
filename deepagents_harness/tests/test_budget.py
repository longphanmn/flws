"""Task 6a — the budget wall.

§6 L263: "Budgeter: hard wall-clock + tick budget; refuses to escalate without a
ledger entry". The wall exists because the arithmetic, not the agent, is the
binding constraint: one T2 iteration is ~2 h of a 4-core box and the whole campaign
shape in §6 L301 is 8.2 h, so an engine that cannot say no spends the box on
candidates the linter would have refused.

A refusal is an error, never a silent truncation of the run: a caller that cannot
tell it was cut off will report a partial run as a result.
"""
import pytest


def test_allows_exactly_the_configured_number_of_runs():
    from deepagents_harness.budget import BudgetWall

    wall = BudgetWall(max_sim_runs=3)
    for _ in range(3):
        wall.spend()
    assert wall.used == 3
    assert wall.remaining == 0


def test_refuses_the_run_past_the_wall():
    from deepagents_harness.budget import BudgetWall

    wall = BudgetWall(max_sim_runs=3)
    for _ in range(3):
        wall.spend()
    with pytest.raises(Exception) as exc:
        wall.spend()
    assert "3" in str(exc.value)


def test_the_refusal_names_the_wall_so_the_message_is_actionable():
    from deepagents_harness.budget import BudgetWall

    wall = BudgetWall(max_sim_runs=2)
    wall.spend()
    wall.spend()
    with pytest.raises(Exception) as exc:
        wall.spend("G2 granary buffering")
    msg = str(exc.value)
    assert "G2 granary buffering" in msg
    assert "2" in msg


def test_never_goes_negative_even_after_a_refusal():
    from deepagents_harness.budget import BudgetWall

    wall = BudgetWall(max_sim_runs=1)
    wall.spend()
    with pytest.raises(Exception):
        wall.spend()
    assert wall.used == 1
    assert wall.remaining == 0


def test_records_what_each_run_was_spent_on():
    from deepagents_harness.budget import BudgetWall

    wall = BudgetWall(max_sim_runs=2)
    wall.spend("T0 baseline seed 42")
    assert wall.spends[0]["reason"] == "T0 baseline seed 42"
    assert wall.to_dict()["spent"] == 1


def test_reports_itself_as_a_dict_for_the_ledger():
    from deepagents_harness.budget import BudgetWall

    wall = BudgetWall(max_sim_runs=3)
    wall.spend("x")
    d = wall.to_dict()
    assert d["max_sim_runs"] == 3 and d["spent"] == 1 and d["remaining"] == 2


def test_rejects_a_nonsense_limit():
    from deepagents_harness.budget import BudgetWall

    with pytest.raises(ValueError):
        BudgetWall(max_sim_runs=0)
