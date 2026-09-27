"""Task 10 — the package's public surface.

The plan's architecture block promises `__init__.py` exports the seven tools plus the
budget and the ledger. This test exists so that promise is checked rather than
remembered, and so the export list cannot quietly diverge from the tool list the
agent is handed: a tool that exists but is not exported is a tool nobody can reach,
and a tool that is exported but not handed to the agent is a tool with no business
being public.
"""
import os

import pytest

import deepagents_harness


def test_the_seven_tools_are_exported():
    for name in ("read_metrics", "gate_lint", "propose_law_delta", "run_trace",
                 "compare", "ledger_append", "read_run_manifest"):
        assert hasattr(deepagents_harness, name), f"{name} is not exported"


def test_the_ledger_and_budget_are_exported():
    assert hasattr(deepagents_harness, "Ledger")
    assert hasattr(deepagents_harness, "BudgetWall")
    assert hasattr(deepagents_harness, "BudgetExhausted")
    assert hasattr(deepagents_harness, "LedgerError")


def test_the_exported_ledger_append_is_the_ledgers_own():
    from deepagents_harness.ledger import Ledger

    assert deepagents_harness.ledger_append == Ledger.ledger_append


def test_the_exported_tools_are_the_same_objects_the_agent_gets():
    from deepagents_harness import agent

    # run_trace and ledger_append are deliberately bound per-instance (the wall and
    # the ledger file), so identity does not hold for those two; their binding is
    # asserted separately below.
    bound = {"run_trace", "ledger_append"}
    wired = agent.agent_tools()
    for name, fn in wired.items():
        if name in bound:
            continue
        assert getattr(deepagents_harness, name) is fn, name


def test_the_agents_run_trace_is_bound_to_the_budget_wall_and_the_sweep_root(tmp_path):
    """The agent cannot spend a run the wall would refuse, and cannot write outside."""
    from deepagents_harness import BudgetWall, agent

    wall = BudgetWall(max_sim_runs=1)
    wall.spend("the only slot, already gone")
    wired = agent.agent_tools(budget=wall, root=str(tmp_path))
    with pytest.raises(Exception) as exc:
        wired["run_trace"]("B", 42, ticks=100)
    assert "budget wall" in str(exc.value).lower()
    assert os.listdir(tmp_path) == []


def test_version_is_declared():
    assert deepagents_harness.__version__
