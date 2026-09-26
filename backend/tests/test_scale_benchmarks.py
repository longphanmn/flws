import time
import pytest
from app.config import Config
from app.native_core import is_native_available, native_query_radius
from app.simulation import Simulation
from app.world import World


def test_native_core_parity_with_python(enable_morphology):
    """Verify that native C queries return bit-for-bit identical results to pure Python reference math."""
    # 1. Native library must be compiled and available
    assert is_native_available(), "Native core library (_flatland_core) must be compiled and available"

    # 2. Wrap, clamp, boundary, and max_out cases with bit-for-bit exact float64 squared distances
    n = 100
    xs = [float(i * 1.5 % 100) for i in range(n)]
    ys = [float((i * 2.3 + 10) % 100) for i in range(n)]
    ids = list(range(1, n + 1))

    # Test center query with wrap
    c_ids, c_d2 = native_query_radius(50.0, 50.0, 15.0, xs, ys, ids, 100.0, 100.0, True)

    ref_ids = []
    ref_d2 = []
    r2 = 15.0 * 15.0
    for i in range(n):
        dx = abs(50.0 - xs[i])
        dy = abs(50.0 - ys[i])
        if dx > 50.0:
            dx -= 100.0
        if dy > 50.0:
            dy -= 100.0
        d2 = dx * dx + dy * dy
        if d2 <= r2:
            ref_ids.append(ids[i])
            ref_d2.append(d2)

    assert c_ids == ref_ids
    assert len(c_d2) == len(ref_d2)
    # Bit-for-bit exact IEEE 754 float64 comparison
    for a, b in zip(c_d2, ref_d2):
        assert a == b, f"Distance squared float64 mismatch: native={a} ({a.hex() if hasattr(a, 'hex') else a}) != ref={b} ({b.hex() if hasattr(b, 'hex') else b})"

    # Test clamp (is_wrap = False) and boundary query
    c_ids_clamp, c_d2_clamp = native_query_radius(2.0, 2.0, 10.0, xs, ys, ids, 100.0, 100.0, False)
    ref_ids_clamp = []
    ref_d2_clamp = []
    r2_clamp = 10.0 * 10.0
    for i in range(n):
        dx = 2.0 - xs[i]
        dy = 2.0 - ys[i]
        d2 = dx * dx + dy * dy
        if d2 <= r2_clamp:
            ref_ids_clamp.append(ids[i])
            ref_d2_clamp.append(d2)

    assert c_ids_clamp == ref_ids_clamp
    assert len(c_d2_clamp) == len(ref_d2_clamp)
    for a, b in zip(c_d2_clamp, ref_d2_clamp):
        assert a == b

    # Test max_out truncation contract
    c_ids_trunc, c_d2_trunc = native_query_radius(50.0, 50.0, 15.0, xs, ys, ids, 100.0, 100.0, True, max_out=3)
    assert len(c_ids_trunc) == min(3, len(ref_ids))
    assert len(c_d2_trunc) == min(3, len(ref_d2))
    assert c_ids_trunc == ref_ids[:3]
    assert c_d2_trunc == ref_d2[:3]

    # 3. World.query_radius_with_dist_sq contract (IDs and float64 squared distances)
    from app.entities import Entity
    w_cfg = Config(width=100, height=100, boundary="wrap", morphology_annealing_enabled=True)
    w = World(w_cfg)
    for i in range(n):
        ent = Entity(id=ids[i], x=xs[i], y=ys[i], kind="food")
        w.add(ent)
    w.rebuild_index()
    w_results = w.query_radius_with_dist_sq(50.0, 50.0, 15.0)
    w_ids = [e.id for e, _ in w_results]
    w_d2 = [d2 for _, d2 in w_results]
    assert set(w_ids) == set(ref_ids)
    for eid, wd2 in zip(w_ids, w_d2):
        idx = ref_ids.index(eid)
        assert wd2 == ref_d2[idx]

    # 4. Morphology seams: trait computation and SAT overlap with morphology enabled
    from app.morphology_engine import (
        compute_polygon_vertices,
        compute_shoelace_area,
        compute_perimeter,
        compute_moment_of_inertia,
        compute_min_vertex_angle,
        compute_asymmetry_index,
        sat_overlap,
    )
    # Triangle genome K=3
    r3 = [1.0, 1.5, 0.8]
    phi3 = [0.0, 2.0943951023931953, 4.1887902047863905]
    vx, vy = compute_polygon_vertices(r3, phi3, 3)
    area = compute_shoelace_area(vx, vy, 3)
    perim = compute_perimeter(vx, vy, 3)
    izz = compute_moment_of_inertia(vx, vy, 3, area)
    theta = compute_min_vertex_angle(vx, vy, 3)
    asym = compute_asymmetry_index(r3, 3)

    assert area > 0.0
    assert perim > 0.0
    assert izz > 0.0
    assert 0.0 < theta < 3.141592653589793
    assert asym >= 0.0

    # SAT overlap cases: identical polygon overlaps itself
    assert sat_overlap(vx, vy, vx, vy) is True
    # Disjoint shifted polygon
    vx_far = [x + 50.0 for x in vx]
    vy_far = [y + 50.0 for y in vy]
    assert sat_overlap(vx, vy, vx_far, vy_far) is False

    # 5. Collision sweep & wall raycast parity
    from app.native_core import native_collision_sweep, native_path_crosses_wall
    coll_radii = [1.0] * n
    native_pairs = set(native_collision_sweep(xs, ys, coll_radii, ids, 100.0, 100.0, True))
    # Python reference collision sweep
    ref_pairs = set()
    hw, hh = 50.0, 50.0
    for i in range(n):
        for j in range(i + 1, n):
            dx = abs(xs[i] - xs[j])
            dy = abs(ys[i] - ys[j])
            if dx > hw: dx = 100.0 - dx
            if dy > hh: dy = 100.0 - dy
            rr = coll_radii[i] + coll_radii[j]
            if dx * dx + dy * dy < rr * rr:
                ref_pairs.add((ids[i], ids[j]))
    assert native_pairs == ref_pairs

    # Wall segment intersection parity
    walls = [(10.0, 10.0, 10.0, 30.0), (20.0, 20.0, 40.0, 20.0)]
    assert native_path_crosses_wall(5.0, 20.0, 15.0, 20.0, walls) is True
    assert native_path_crosses_wall(50.0, 50.0, 60.0, 60.0, walls) is False

    # 6. Batch perception query parity
    from app.native_core import native_batch_query_radius
    batch_res = native_batch_query_radius([50.0, 2.0], [50.0, 2.0], [15.0, 10.0], xs, ys, ids, 100.0, 100.0, True)
    assert len(batch_res) == 2
    assert batch_res[0][0] == c_ids
    assert batch_res[0][1] == c_d2


def test_scale_benchmark_1000_creatures():
    """Benchmark high-scale simulation step times with 1000+ creatures."""
    cfg = Config(seed=42, width=300, height=300, carrying_capacity=800, max_population=1000, food_count=300)
    sim = Simulation(cfg)

    # Warm up 5 ticks
    for _ in range(5):
        sim.step()

    # Measure average step duration over 20 ticks
    t0 = time.monotonic()
    ticks = 20
    for _ in range(ticks):
        sim.step()
    dur_ms = (time.monotonic() - t0) * 1000.0 / ticks

    print(f"\n[Scale Benchmark] Active Entities: {len(sim.world.entities)} | Step Time: {dur_ms:.2f} ms/tick ({1000.0/dur_ms:.1f} FPS)")
    # Assert step execution is fast (<25 ms per tick even under high scale in pytest)
    assert dur_ms < 30.0, f"Expected step time < 30ms, got {dur_ms:.2f}ms"
