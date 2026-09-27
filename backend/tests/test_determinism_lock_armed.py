"""F9 — the determinism golden lock must be armed, not decorative.

`test_determinism_golden.py` shipped with `GOLDEN_HASHES = {}` and its
cross-run assertion behind `if GOLDEN_HASHES:`, so it only ever proved
self-consistency *within one process*. Every structural change to the dynamics
therefore had no automated tripwire for the property the whole product is sold
on: same seed => same world.

This pins that the lock is real: populated, complete, and equal to what the
simulation actually produces today. If someone re-arms the conditional, empties
the dict, or a dynamics change moves the world, this fails.
"""

import importlib.util
import os

import pytest

_GOLDEN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_determinism_golden.py")
CHECKPOINTS = (100, 250, 500)


def _load():
    spec = importlib.util.spec_from_file_location("determinism_golden_probe", _GOLDEN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def golden():
    return _load()


def test_golden_hashes_are_populated(golden):
    assert golden.GOLDEN_HASHES, (
        "GOLDEN_HASHES is empty — the golden determinism lock is disarmed and any "
        "dynamics change passes silently"
    )


def test_golden_hashes_cover_every_checkpoint(golden):
    assert set(golden.GOLDEN_HASHES) == set(CHECKPOINTS)


def test_golden_hashes_are_well_formed(golden):
    for tick, value in golden.GOLDEN_HASHES.items():
        assert isinstance(value, str) and len(value) == 16, f"tick {tick}: {value!r}"
        int(value, 16)  # must be hex


def test_locked_hashes_match_a_fresh_run(golden):
    """The unconditional assertion the golden test now carries, as its own test."""
    assert golden.compute_hashes() == golden.GOLDEN_HASHES, (
        "simulation no longer reproduces the committed golden hashes — this is an "
        "intentional dynamics change only if GOLDEN_HASHES was updated with it"
    )
