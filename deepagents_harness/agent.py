"""The deepagents orchestrator: wiring, credentials, and the tool surface.

Three rules shape this module.

**The orchestrator cannot author a verdict.** §6 L289-L290 makes the Verifier a
plain function and the agent physically unable to write one. The seven tools it is
handed return numbers; the gate verdict in every artifact is produced by
``osc_gate_report``. Nothing here takes a model's word for anything.

**The key is never printed.** ``/root/.hermes/.env`` is read for DEEPAGENTS_API_KEY
and that value goes into the model client and nowhere else. ``Credentials.__repr__``
and ``safe_dict()`` both redact it, so an accidental ``print(creds)``, a traceback, or
a JSON dump of a config cannot leak it. The tests assert this against the real key
read back out of the env file, not against a fixture.

**The endpoint is never guessed.** The opencode-go provider is live and the model is
listed, but the base URL is not discoverable on this host (see the plan's Ruling 5),
so ``build_model`` refuses with an actionable message instead of constructing a client
pointed at an invented host. Everything that does not need the model -- the seven
tools, the ledger, the budget wall, the deterministic G2 campaign -- runs regardless.
"""
import os
import sys

from . import tools as tools_mod
from .ledger import Ledger

DEFAULT_ENV_PATH = "/root/.hermes/.env"

AGENT_INSTRUCTIONS = """\
You are the Planner for the flws oscillation gate suite. Your job is to turn a
hypothesis into a falsifiable card and a sweep plan. You do not decide whether a run
passed.

Rules you cannot break:
1. You may not author a verdict. The verdict is deterministic output of
   osc_gate_report via read_metrics and compare. Report it verbatim. Never summarise
   a FAIL as a PASS.
2. You may not read the samples array. read_metrics strips it and caps the payload at
   4 KB. Work from metrics and gates only.
3. Every card needs a predicted SIGNED gate delta (gate, direction, min_delta > 0)
   written to the ledger BEFORE any run. A prediction that any result satisfies is
   not a prediction.
4. You may not edit simulation source, and you may not commit anything. Your whole
   write scope is a validated set of Config field values via propose_law_delta.
5. A card whose prediction is not met is archived, not retried.
6. The budget wall is hard. When it refuses, stop and report; do not look for a way
   around it.
"""


class EndpointUnconfigured(RuntimeError):
    """No base URL for the configured provider. Guessing one is not an option."""


class ModelNotAllowed(RuntimeError):
    """A model outside Long's allowlist was requested. Ask Long; never substitute."""


# Long's standing rule: deepagents runs ONLY deepseek-v4.1-flash (primary) with
# space-bunny-free as the fallback. Any other model requires asking him first.
ALLOWED_MODELS = ("deepseek-v4.1-flash", "space-bunny-free")
DEFAULT_PRIMARY = "deepseek-v4.1-flash"
DEFAULT_FALLBACK = "space-bunny-free"
_POLICY_MESSAGE = (
    "deepagents may use only deepseek-v4.1-flash (primary) or space-bunny-free "
    "(fallback). Any other model needs Long's approval - ask him first and wait; "
    "never silently substitute."
)


def _enforce_model_policy(model_name):
    if model_name not in ALLOWED_MODELS:
        raise ModelNotAllowed(
            f"model {model_name!r} is not on the deepagents allowlist. "
            f"{_POLICY_MESSAGE}"
        )
    return model_name


def _is_model_unavailable(exc):
    """True only for 'this model cannot serve now' - never for auth/validation."""
    s = str(exc).lower()
    return any(t in s for t in (
        "model is unavailable", "model_not_found", "no such model",
        "does not exist", "error code: 404", "error code: 503",
        "error code: 502", "no endpoints found",
    ))


class Credentials:
    """DEEPAGENTS_* configuration. The key never leaves this object in plain text."""

    __slots__ = ("api_key", "provider", "model", "base_url", "_source",
                 "fallback_model")

    def __init__(self, api_key, provider, model, base_url=None, source=None,
                 fallback_model=DEFAULT_FALLBACK):
        self.api_key = api_key
        self.provider = provider
        self.model = model
        # Allowlisted fallback only (Long's rule); never any other model.
        self.fallback_model = fallback_model
        # An explicit base_url is the ONLY way an endpoint becomes known. Nothing
        # here infers one from the provider name.
        self.base_url = base_url or os.environ.get("DEEPAGENTS_BASE_URL") or None
        self._source = source

    def __repr__(self):
        return (f"Credentials(provider={self.provider!r}, model={self.model!r}, "
                f"api_key=<redacted>, base_url={self.base_url!r})")

    __str__ = __repr__

    def safe_dict(self):
        """The only sanctioned way to log or serialise this object."""
        return {
            "provider": self.provider,
            "model": self.model,
            "api_key": "<redacted>",
            "api_key_present": bool(self.api_key),
            "base_url": self.base_url,
            "endpoint_configured": bool(self.base_url),
            "source": self._source,
        }


def load_credentials(env_path=DEFAULT_ENV_PATH):
    """Read DEEPAGENTS_API_KEY / _PROVIDER / _MODEL from a dotenv file.

    Parsed here rather than with a dotenv dependency: three keys, and a parser is
    fewer lines than the install. A missing file raises, because a harness that
    starts with no credentials should say so instead of failing at the first call.
    """
    if not os.path.exists(env_path):
        raise FileNotFoundError(
            f"{env_path} not found: the harness reads DEEPAGENTS_API_KEY, "
            f"DEEPAGENTS_PROVIDER and DEEPAGENTS_MODEL from it"
        )
    found = {}
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            if key.startswith("DEEPAGENTS_"):
                found[key] = value.strip().strip('"').strip("'")
    missing = [k for k in ("DEEPAGENTS_API_KEY", "DEEPAGENTS_PROVIDER",
                           "DEEPAGENTS_MODEL") if k not in found]
    if missing:
        raise ValueError(f"{env_path} is missing {missing}")
    # Long's rule is enforced at load: a disallowed value never becomes a
    # Credentials object at all, so no code path downstream can use it.
    primary = _enforce_model_policy(found["DEEPAGENTS_MODEL"])
    fallback = _enforce_model_policy(
        found.get("DEEPAGENTS_FALLBACK_MODEL", DEFAULT_FALLBACK))
    return Credentials(
        api_key=found["DEEPAGENTS_API_KEY"],
        provider=found["DEEPAGENTS_PROVIDER"],
        model=primary,
        # The env file is the single source of truth for the endpoint too:
        # DEEPAGENTS_BASE_URL is carried through here, not just os.environ.
        base_url=found.get("DEEPAGENTS_BASE_URL") or None,
        source=env_path,
        fallback_model=fallback,
    )


def agent_tools(ledger=None, budget=None, root=None):
    """The seven tools, bound to a ledger and a budget wall.

    §6 L269-279. ``ledger_append`` is bound to a concrete Ledger instance so the
    agent has no way to name a different file, and ``run_trace`` to the budget wall
    so it cannot spend a run the wall would refuse. The returned mapping is the whole
    write surface of the agent loop.
    """
    def _ledger_append(hypothesis, expected_gate, result, **kw):
        """Append a hypothesis card with its signed gate delta, and close it.

        `hypothesis` is the claim, `expected_gate` is the gate number 1-5 the claim
        is about, and `result` records what was run. `before` and `after` must be
        metric dicts so the signed delta can be measured. Returns the card id and
        whether the prediction was confirmed or falsified.
        """
        if ledger is None:
            raise RuntimeError("this harness was built without a ledger")
        return ledger.ledger_append(hypothesis, expected_gate, result, **kw)

    def _run_trace(world="B", seed=42, ticks=1000, burn_in=0, out=None, overrides=None):
        """Run one gate trace and return the artifact path.

        `world` is 'A' (moving setpoint) or 'B' (flat). `seed` selects the replicate.
        `ticks` and `burn_in` set the budget. `out` defaults inside the sweep root and
        is refused outside it. `overrides` is a Config-field proposal; a dead knob or
        a scalar-only damping nudge is refused before any tick is spent. Runs are
        sequential with OMP_NUM_THREADS=1 and are counted against the budget wall.
        """
        return tools_mod.run_trace(world, seed, ticks, burn_in, out, overrides,
                                   budget=budget, root=root)

    return {
        "read_metrics": tools_mod.read_metrics,
        "gate_lint": tools_mod.gate_lint,
        "propose_law_delta": tools_mod.propose_law_delta,
        "run_trace": _run_trace,
        "compare": tools_mod.compare,
        "ledger_append": _ledger_append,
        "read_run_manifest": tools_mod.read_run_manifest,
    }


def endpoint_status(credentials):
    """The one reportable summary of whether the LLM leg can run.

    Redacted by construction: it is built from ``safe_dict``, so a trace that
    includes it can never carry the key. ``available`` is False both when there are
    no credentials and when there are credentials with nowhere to send them, and the
    ``reason`` says which -- because those are different problems with different
    fixes.
    """
    if credentials is None:
        return {
            "available": False,
            "reason": "no credentials loaded; the deterministic loop does not need them",
            "api_key": "<redacted>",
            "api_key_present": False,
            "endpoint_configured": False,
            "provider": None,
            "model": None,
        }
    safe = credentials.safe_dict()
    safe["available"] = bool(credentials.base_url)
    if not credentials.base_url:
        safe["reason"] = (
            f"provider {credentials.provider!r} is live but its base URL is not "
            f"discoverable on this host, so the LLM leg did not run; the seven tools, "
            f"the ledger, the budget wall and the gate verdicts are unaffected"
        )
    else:
        safe["reason"] = "endpoint configured; the LLM leg may run"
    return safe


def build_model(credentials, **kwargs):
    """Construct the chat model, or refuse.

    A provider name is not an endpoint. On a host where the opencode-go base URL is
    not discoverable, this raises rather than pointing a client at a plausible-looking
    host, because a request to the wrong endpoint with a real key is worse than no
    request: it can look like a working agent while every call fails.
    """
    if not credentials.base_url:
        raise EndpointUnconfigured(
            f"no base URL is configured for provider {credentials.provider!r} "
            f"(model {credentials.model!r}). The provider is live and the model is "
            f"listed, but opencode-go's endpoint is not discoverable on this host: "
            f"it is in no config file, no env var and not the opencode server's "
            f"documented route. Supply DEEPAGENTS_BASE_URL (or Credentials.base_url) "
            f"to point the agent at it. Every deterministic part of the harness -- "
            f"the seven tools, the ledger, the budget wall, the gate verdicts -- runs "
            f"without it."
        )
    # Policy layer: the requested primary (env or explicit kwarg) and the
    # fallback must both be on Long's allowlist before any client exists.
    requested = kwargs.pop("model", None)
    primary = _enforce_model_policy(requested if requested else credentials.model)
    fallback = _enforce_model_policy(credentials.fallback_model)
    _ = primary  # the allowlist check is the point; the client uses it below

    # opencode-go routes and caches per conversation and rejects anonymous SDK
    # traffic: send a stable session id per harness conversation plus an
    # identifying user agent (docs: opencode.ai/docs/go).
    import uuid  # noqa: PLC0415
    session_id = os.environ.get("DEEPAGENTS_SESSION_ID")
    if not session_id:
        session_id = "flws-deepagents-" + uuid.uuid4().hex[:16]
        os.environ["DEEPAGENTS_SESSION_ID"] = session_id
    headers = {"x-opencode-session": session_id,
               "User-Agent": "flws-deepagents-harness/1.0"}
    kwargs.setdefault("default_headers", {}).update(headers)

    client_cls = _fallback_client_cls()
    client = client_cls(
        model=credentials.model if requested is None else requested,
        base_url=credentials.base_url,
        api_key=credentials.api_key,
        **kwargs,
    )
    # Shared mutable state so bind_tools copies keep the same fallback policy.
    client._fb_state = {
        "fallback_model": fallback,
        "base_kwargs": {"base_url": credentials.base_url,
                        "api_key": credentials.api_key,
                        "default_headers": headers},
        "bound_args": None,
        "active": None,
    }
    os.environ["DEEPAGENTS_MODEL_EFFECTIVE"] = getattr(client, "model_name", None) or str(client.model)
    return client


def _fallback_client_cls():
    """ChatOpenAI subclass whose invoke/ainvoke fall back once, and only ever
    to the allowlisted fallback model. Construction performs no network I/O
    (the wiring test asserts that); the swap happens on the first real call
    that reports the primary model unavailable.
    """
    from langchain_openai import ChatOpenAI  # noqa: PLC0415

    class _FallbackClient(ChatOpenAI):
        _fb_state = None

        def bind_tools(self, tools, **kw):  # noqa: ANN001 - langchain API
            res = super().bind_tools(tools, **kw)
            if self._fb_state is not None:
                self._fb_state["bound_args"] = (tools, kw)
                res._fb_state = self._fb_state
            return res

        def _maybe_swap(self, exc):
            st = self._fb_state
            if st is None:
                return False
            if st.get("active") is not None:
                return True
            if not _is_model_unavailable(exc):
                return False
            kw = dict(st["base_kwargs"])
            kw["model"] = st["fallback_model"]
            fb = ChatOpenAI(**kw)
            if st.get("bound_args") is not None:
                tools, tokw = st["bound_args"]
                fb = fb.bind_tools(tools, **tokw)
            st["active"] = fb
            os.environ["DEEPAGENTS_MODEL_EFFECTIVE"] = st["fallback_model"]
            print(
                f"[deepagents] model policy: primary reported unavailable "
                f"({type(exc).__name__}); fell back to {st['fallback_model']!r} "
                f"per Long's allowlist - no other model is permitted",
                file=sys.stderr,
            )
            return True

        def invoke(self, input, config=None, **kw):  # noqa: A002, ANN001
            st = self._fb_state
            if st is not None and st.get("active") is not None:
                return st["active"].invoke(input, config=config, **kw)
            try:
                return super().invoke(input, config=config, **kw)
            except Exception as exc:  # noqa: BLE001 - classified below
                if self._maybe_swap(exc):
                    return st["active"].invoke(input, config=config, **kw)
                raise

        async def ainvoke(self, input, config=None, **kw):  # noqa: A002, ANN001
            st = self._fb_state
            if st is not None and st.get("active") is not None:
                return await st["active"].ainvoke(input, config=config, **kw)
            try:
                return await super().ainvoke(input, config=config, **kw)
            except Exception as exc:  # noqa: BLE001 - classified below
                if self._maybe_swap(exc):
                    return await st["active"].ainvoke(input, config=config, **kw)
                raise

    return _FallbackClient


def build_agent(credentials, *, ledger=None, budget=None, root=None, **model_kwargs):
    """The deepagents orchestrator, with the seven tools and no verdict authority."""
    from deepagents import create_deep_agent  # noqa: PLC0415 - optional dependency

    return create_deep_agent(
        model=build_model(credentials, **model_kwargs),
        tools=list(agent_tools(ledger=ledger, budget=budget, root=root).values()),
        # deepagents 0.7.19 spells this `system_prompt`; there is no `instructions`
        # parameter, and passing one raises TypeError at construction.
        system_prompt=AGENT_INSTRUCTIONS,
    )
