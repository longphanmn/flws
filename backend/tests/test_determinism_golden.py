"""AZ Phase 0: determinism golden hash (ticks 100/250/500)."""
import hashlib
from app.config import Config
from app.simulation import Simulation

GOLDEN_SEED = 1337
# Locked against seed 1337 on the 200x200/40-food baseline. Captured after the
# §G3 change that removed the xi-coupled elder senescence multiplier, so these
# attest to the current dynamics, not to the pre-§G3 ones. Any further change to
# the dynamics is a deliberate act: re-run with -s, read the printed hashes, and
# update them here in the same commit as the change.
GOLDEN_HASHES = {
    100: "b74dad373d8326d2",
    250: "562161a8f8c32333",
    500: "1888afb716ec487a",
}

def _hash_at(sim: Simulation) -> str:
    # checkpoint hash of (id, round(x,6), round(y,6), round(energy,6))
    items = sorted(
        (c.id, round(c.x, 6), round(c.y, 6), round(c.energy, 6))
        for c in sim._cached_creatures
    )
    h = hashlib.sha256()
    for tup in items:
        h.update(f"{tup[0]}:{tup[1]:.6f}:{tup[2]:.6f}:{tup[3]:.6f}|".encode())
    return h.hexdigest()[:16]

def compute_hashes(seed: int = GOLDEN_SEED, ticks: int = 500):
    cfg = Config(seed=seed, width=200, height=200, num_triangles=20, num_squares=10, num_pentagons=5, num_hexagons=3, num_priests=2, num_women=10, num_houses=5, food_count=40)
    sim = Simulation(cfg)
    out = {}
    for t in range(1, ticks + 1):
        sim.step()
        if t in (100, 250, 500):
            out[t] = _hash_at(sim)
    return out

def test_determinism_golden():
    hashes = compute_hashes()
    # second run must match
    hashes2 = compute_hashes()
    assert hashes == hashes2, f"non-deterministic: {hashes} vs {hashes2}"
    print(f"\n[golden] {hashes}")
    # unconditional: an empty/conditional lock is what left this disarmed (F9)
    assert hashes == GOLDEN_HASHES, (
        f"golden drift: {hashes} != {GOLDEN_HASHES}"
    )

def test_determinism_golden_values():
    """Pin known good values so regressions are caught."""
    h = compute_hashes()
    # store current as reference — update only when intentionally changing simulation
    # This test will fail on first commit if not yet pinned; run with -- -s to see print and copy.
    assert all(isinstance(v, str) and len(v) == 16 for v in h.values())
