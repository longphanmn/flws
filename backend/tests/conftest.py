"""Shared test setup: keep the app's SQLite database out of the repo."""

import os
import tempfile

import pytest

os.environ["FLATWORLD_DB"] = os.path.join(
    tempfile.mkdtemp(prefix="flatworld_test_"), "test_flatland.db"
)
# Deterministic god passkey so tests may touch laws/control via X-God-Key.
os.environ["FLATWORLD_GOD_KEY"] = "test-key"
# Disable new soft-cap/safeguard engines for deterministic tests (they are integration-tested separately)
os.environ["FLATWORLD_SOFT_CAP_ENABLED"] = "false"
os.environ["FLATWORLD_SAFEGUARD_ENABLED"] = "false"
os.environ["FLATWORLD_MORPHOLOGY_ANNEALING_ENABLED"] = "false"
# Patch Config defaults for tests that construct Config directly
try:
    from app.config import Config as _Cfg
    _Cfg.__dataclass_fields__["soft_cap_enabled"].default = False
    _Cfg.__dataclass_fields__["safeguard_enabled"].default = False
    _Cfg.__dataclass_fields__["morphology_annealing_enabled"].default = False
    # also patch the class attribute for direct instantiation without from_env
    _Cfg.soft_cap_enabled = False  # type: ignore
    _Cfg.safeguard_enabled = False  # type: ignore
    _Cfg.morphology_annealing_enabled = False  # type: ignore
except Exception:
    pass


@pytest.fixture(autouse=True)
def reset_rate_limiters():
    from app import auth

    auth._RATE_LIMITERS.clear()
    yield
    auth._RATE_LIMITERS.clear()


@pytest.fixture
def extended_testclient_god_rate_limit():
    from app import auth

    auth._RATE_LIMITERS["god_api:testclient"] = auth.TokenBucket(10_000, 10_000)


@pytest.fixture
def enable_morphology(monkeypatch):
    """Enable morphology annealing for tests requesting morphology parity."""
    monkeypatch.setenv("FLATWORLD_MORPHOLOGY_ANNEALING_ENABLED", "true")
    from app.config import Config
    old_default = Config.__dataclass_fields__["morphology_annealing_enabled"].default
    old_cls = getattr(Config, "morphology_annealing_enabled", False)
    Config.__dataclass_fields__["morphology_annealing_enabled"].default = True
    Config.morphology_annealing_enabled = True  # type: ignore
    yield
    Config.__dataclass_fields__["morphology_annealing_enabled"].default = old_default
    Config.morphology_annealing_enabled = old_cls  # type: ignore

