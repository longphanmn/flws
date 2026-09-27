"""Long's model allowlist: deepseek-v4.1-flash primary, space-bunny fallback,
nothing else without asking him."""
import pytest

from deepagents_harness import agent as agent_mod


def _env_file(tmp_path, primary, fallback=None):
    lines = ["DEEPAGENTS_API_KEY=k", "DEEPAGENTS_PROVIDER=opencode-go",
             "DEEPAGENTS_MODEL=" + primary]
    if fallback:
        lines.append("DEEPAGENTS_FALLBACK_MODEL=" + fallback)
    p = tmp_path / ".env"
    p.write_text("\n".join(lines) + "\n")
    return str(p)


def test_load_refuses_disallowed_primary(tmp_path):
    with pytest.raises(agent_mod.ModelNotAllowed, match="allowlist"):
        agent_mod.load_credentials(_env_file(tmp_path, "gpt-4o"))


def test_load_refuses_disallowed_fallback(tmp_path):
    with pytest.raises(agent_mod.ModelNotAllowed):
        agent_mod.load_credentials(
            _env_file(tmp_path, "deepseek-v4.1-flash", "claude-opus-4"))


def test_load_accepts_allowlisted_pair(tmp_path):
    c = agent_mod.load_credentials(
        _env_file(tmp_path, "deepseek-v4.1-flash", "space-bunny-free"))
    assert c.model == "deepseek-v4.1-flash"
    assert c.fallback_model == "space-bunny-free"


def test_default_fallback_is_space_bunny(tmp_path):
    c = agent_mod.load_credentials(_env_file(tmp_path, "deepseek-v4.1-flash"))
    assert c.fallback_model == "space-bunny-free"


def test_build_refuses_disallowed_kwarg():
    c = agent_mod.Credentials(api_key="k", provider="opencode-go",
                              model="deepseek-v4.1-flash",
                              base_url="https://example.invalid/v1")
    with pytest.raises(agent_mod.ModelNotAllowed):
        agent_mod.build_model(c, model="glm-5.3")


def test_classifier_only_flags_real_unavailability():
    assert agent_mod._is_model_unavailable(
        RuntimeError("Error code: 400 - Model is unavailable"))
    assert agent_mod._is_model_unavailable(RuntimeError("404 model_not_found"))
    assert not agent_mod._is_model_unavailable(
        RuntimeError("Error code: 401 - Invalid API key"))
    assert not agent_mod._is_model_unavailable(
        RuntimeError("Error code: 400 - MissingSessionID"))


def test_build_construction_stays_offline_and_carries_fallback():
    pytest.importorskip("langchain_openai")
    c = agent_mod.Credentials(api_key="k", provider="opencode-go",
                              model="deepseek-v4.1-flash",
                              base_url="https://example.invalid/v1")
    m = agent_mod.build_model(c)  # must not reach the network
    assert m._fb_state["fallback_model"] == "space-bunny-free"
    assert m._fb_state["active"] is None
