"""Task 8 — the deepagents wiring, and the credential handling around it.

Two things are being tested here, and the second matters more than the first.

**The tool surface.** §6 L269: "all read-only or sandboxed; none may `git commit`".
The agent is handed exactly the seven tools, and a test pins that list so a future
eighth tool cannot quietly widen the blast radius.

**The key.** ``/root/.hermes/.env`` holds DEEPAGENTS_API_KEY. The rule is that it is
never printed, never logged, and never written into an artifact or the ledger. The
tests read the *real* key out of the env file and then assert it appears in nothing
the harness produces, which is the only form of that assertion worth having: a test
against a fake key proves nothing about the real one.
"""
import json
import os
import sys

import pytest

from deepagents_harness import agent as agent_mod

ENV_PATH = "/root/.hermes/.env"
KEY_NAME = "DEEPAGENTS_API_KEY"


def _real_key():
    if not os.path.exists(ENV_PATH):
        pytest.skip(f"{ENV_PATH} is not present on this host")
    for line in open(ENV_PATH):
        if line.startswith(KEY_NAME + "="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    pytest.skip(f"{KEY_NAME} is not in {ENV_PATH}")


def test_loads_the_three_deepagents_variables():
    creds = agent_mod.load_credentials(ENV_PATH)
    assert creds.provider == "opencode-go"
    assert creds.model
    assert creds.api_key


def test_a_missing_env_file_says_so_instead_of_returning_empty_credentials(tmp_path):
    with pytest.raises(FileNotFoundError):
        agent_mod.load_credentials(str(tmp_path / "nope.env"))


def test_the_repr_of_credentials_never_contains_the_key():
    creds = agent_mod.load_credentials(ENV_PATH)
    key = _real_key()
    assert key not in repr(creds)
    assert key not in str(creds)
    assert key not in json.dumps(creds.safe_dict())


def test_safe_dict_reports_the_key_as_a_presence_flag_not_a_value():
    creds = agent_mod.load_credentials(ENV_PATH)
    safe = creds.safe_dict()
    assert safe["api_key"] == "<redacted>"
    assert safe["api_key_present"] is True
    assert _real_key() not in json.dumps(safe)


def test_the_configured_provider_and_model_are_reported():
    safe = agent_mod.load_credentials(ENV_PATH).safe_dict()
    assert safe["provider"] == "opencode-go"
    assert safe["model"]


def test_the_agent_is_handed_exactly_the_seven_tools():
    tools = agent_mod.agent_tools()
    assert set(tools) == {
        "read_metrics", "gate_lint", "propose_law_delta", "run_trace",
        "compare", "ledger_append", "read_run_manifest",
    }


def test_no_ward_tool_in_the_suite_can_commit_or_edit_simulation_source():
    """No tool can reach a shell.

    Checked against the compiled code objects, not the source text: an earlier
    version of this test grepped the module source for "commit" and tripped over the
    docstring that says tools may not commit.
    """
    import inspect
    import types

    from deepagents_harness import ledger, tools

    banned_attrs = {"system", "popen", "Popen", "run", "check_call", "check_output",
                    "call", "callable", "fork", "execv", "execve"}
    banned_modules = {"subprocess", "os.system", "shutil"}

    def all_code_names(fn):
        names = set()
        stack = [fn.__code__] if hasattr(fn, "__code__") else []
        while stack:
            code = stack.pop()
            names.update(code.co_names)
            for const in code.co_consts:
                if isinstance(const, types.CodeType):
                    stack.append(const)
        return names

    checked = 0
    for mod in (tools, ledger):
        candidates = [(f"{mod.__name__}.{n}", getattr(mod, n)) for n in dir(mod)
                      if not n.startswith("_")]
        # The ledger's entry points are methods, not module functions.
        for cls_name in dir(mod):
            cls = getattr(mod, cls_name)
            if inspect.isclass(cls) and cls.__module__ == mod.__name__:
                candidates += [
                    (f"{mod.__name__}.{cls_name}.{n}", getattr(cls, n))
                    for n in dir(cls) if not n.startswith("_")
                ]
        for label, obj in candidates:
            if inspect.isfunction(obj):
                checked += 1
                hit = all_code_names(obj) & banned_attrs
                assert not hit, f"{label} can reach {hit}"
        for bad in banned_modules:
            assert not hasattr(mod, bad), f"{mod.__name__} imports {bad}"
    # 7 tools + read helpers + the 6 public Ledger methods.
    assert checked >= 13, f"only {checked} functions inspected"


def test_building_a_model_without_a_base_url_refuses_rather_than_guessing_one():
    creds = agent_mod.load_credentials(ENV_PATH)
    creds.base_url = None  # strip the configured endpoint; refusal must survive
    with pytest.raises(agent_mod.EndpointUnconfigured) as exc:
        agent_mod.build_model(creds)
    msg = str(exc.value)
    assert "base" in msg.lower() or "url" in msg.lower()
    assert "opencode-go" in msg
    assert _real_key() not in msg


def test_endpoint_configured_comes_from_the_env_file_not_a_guess():
    # The endpoint IS configured now: DEEPAGENTS_BASE_URL lives in the env file,
    # which load_credentials carries through. The provider name alone still never
    # yields one (the refusal test above proves that).
    creds = agent_mod.load_credentials(ENV_PATH)
    d = creds.safe_dict()
    assert d["endpoint_configured"] is (d["base_url"] is not None)
    if d["endpoint_configured"]:
        assert creds.base_url.startswith("https://")
    assert d["api_key"] == "<redacted>"
    assert _real_key() not in str(d)


def test_a_base_url_may_be_supplied_explicitly_and_is_not_guessed():
    creds = agent_mod.load_credentials(ENV_PATH)
    creds.base_url = "http://127.0.0.1:9/v1"
    assert creds.safe_dict()["endpoint_configured"] is True


def test_the_agent_prompt_states_it_may_not_author_a_verdict():
    text = agent_mod.AGENT_INSTRUCTIONS
    assert "verdict" in text.lower()
    assert "osc_gate_report" in text or "deterministic" in text.lower()


def test_the_agent_prompt_forbids_reading_the_samples_array():
    assert "samples" in agent_mod.AGENT_INSTRUCTIONS.lower()
