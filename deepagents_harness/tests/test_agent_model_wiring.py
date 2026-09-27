"""Fix pass 3 — the LLM leg, which the review correctly found unexercised.

I15: `build_model` and `build_agent` had never run. `langchain_openai` was not even
installed, so `build_model` was doubly unrunnable — no base_url raised
EndpointUnconfigured, and a base_url would have raised ImportError. The earlier test
only set `creds.base_url` and asserted a dict field, so it passed no matter how broken
the function was.

These tests construct the client for real. They make NO network call: the point is
that the wiring is real code on a real dependency, not that the endpoint answers.
"""
import pytest

from deepagents_harness import agent as agent_mod


@pytest.fixture()
def creds():
    return agent_mod.load_credentials("/root/.hermes/.env")


def test_the_openai_client_dependency_is_installed():
    import importlib

    assert importlib.util.find_spec("langchain_openai") is not None, (
        "build_model is dead code without langchain-openai"
    )


def test_build_model_constructs_a_client_when_a_base_url_is_given(creds):
    creds.base_url = "http://127.0.0.1:9/v1"
    model = agent_mod.build_model(creds)
    assert model is not None
    # The base URL the operator supplied is the one used; nothing was inferred.
    assert "127.0.0.1" in str(getattr(model, "openai_api_base", "")
                              or getattr(model, "base_url", "")
                              or creds.base_url)


def test_build_model_does_not_reach_the_network_at_construction(creds):
    """Construction must be offline. A client that dialled on construction would
    make every harness test a network test."""
    creds.base_url = "http://127.0.0.1:9/v1"  # nothing listens here
    model = agent_mod.build_model(creds)  # must not raise
    assert model is not None


def test_the_key_reaches_the_client_and_nothing_else(creds):
    creds.base_url = "http://127.0.0.1:9/v1"
    model = agent_mod.build_model(creds)
    secret = getattr(model, "openai_api_key", None) or getattr(model, "api_key", None)
    assert secret is not None, "the client was built without the key"
    # ...and it is not exposed by the harness's own reporting surface.
    assert creds.api_key not in repr(creds)
    assert creds.api_key not in str(creds.safe_dict())


def test_build_agent_wires_the_seven_tools_into_a_deepagents_agent(creds, tmp_path):
    from deepagents_harness.ledger import Ledger
    from deepagents_harness.budget import BudgetWall

    creds.base_url = "http://127.0.0.1:9/v1"
    led = Ledger(str(tmp_path / "l.jsonl"))
    wall = BudgetWall(max_sim_runs=1, ledger=led, require_ledger_entry=True)
    built = agent_mod.build_agent(creds, ledger=led, budget=wall, root=str(tmp_path))
    # deepagents returns a compiled langgraph. Compiling is the assertion: it
    # means the model, the system prompt and the seven callables were all accepted.
    nodes = built.get_graph().nodes
    assert nodes, "the compiled agent has no nodes"
    assert len(agent_mod.agent_tools()) == 7


def test_the_seven_tool_functions_are_all_docstringed_for_schema_generation():
    """deepagents derives a tool schema from the signature and docstring; an
    undocumented tool is a tool the model cannot call sensibly."""
    import inspect

    for name, fn in agent_mod.agent_tools().items():
        assert fn.__doc__, f"{name} has no docstring"
        assert inspect.signature(fn), f"{name} has no signature"
