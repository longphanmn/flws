"""Sensor & actuator pipeline — BA Step 3

Vectorize 16 sensors -> 7 actuators. Reuses world signals where possible,
but is a SoA-native path (not touching Creature fields directly).

Sensor slots:
 0 energy/max, 1 health/max, 2 chill/max
 3-5 left ray (-35°) distance+type, 6-8 mid ray, etc — actually we flatten as
      3 ray distances (3) + 3 ray types (3) interleaved to fill 6 slots.
      To match spec slots 3-8: 3 ray distances + 3 ray type encodings.
 9 audio amp, 10 audio freq, 11 food pheromone, 12 danger pheromone,
 13 collision impulse, 14 slope grade, 15 hidden_state
"""

from __future__ import annotations

import math

try:
    import numpy as np  # type: ignore

    HAS_NUMPY = True
except Exception:  # pragma: no cover
    np = None  # type: ignore
    HAS_NUMPY = False


def _raycast_world(world, origin: tuple[float, float], angle: float, max_dist: float = 32.0, ignore_id: int | None = None) -> tuple[float, str | None]:
    """Fast raycast against world spatial buckets for agent sensory inputs."""
    ox, oy = origin
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    mx = ox + cos_a * (max_dist * 0.5)
    my = oy + sin_a * (max_dist * 0.5)
    candidates = world.query_radius(mx, my, max_dist * 0.6) if hasattr(world, "query_radius") else list(world.entities.values()) if hasattr(world, "entities") else []
    best_dist = max_dist
    best_type = None
    for e in candidates:
        if ignore_id is not None and getattr(e, "id", None) == ignore_id:
            continue
        ex, ey = getattr(e, "x", 0.0), getattr(e, "y", 0.0)
        dx, dy = world.delta(ex, ey, ox, oy) if hasattr(world, "delta") else (ex - ox, ey - oy)
        proj = dx * cos_a + dy * sin_a
        if proj <= 0.2 or proj >= best_dist:
            continue
        perp = abs(dx * sin_a - dy * cos_a)
        kind = getattr(e, "kind", "")
        hit_radius = 1.8 if kind == "food" else 2.2
        if perp <= hit_radius:
            best_dist = proj
            best_type = kind
    return best_dist, best_type


def _batch_raycast_all(grid, x: float, y: float, ray_angles: tuple, max_ds: tuple, ignore_id: int | None = None) -> list:
    """PERF (no logic change): ONE agent-centered query serves all 3 rays.

    A point passing the proj/perp test lies within distance sqrt(max_dist^2 + 1.5^2) <= max_dist + 0.1
    from the origin. radius = r_max + 1.5 guarantees 100% of candidates are tested, reducing query
    area by ~58% compared to the legacy 1.6*r_max. Evaluating candidates once across all 3 rays avoids
    recalculating toroidal deltas 3x per candidate.
    """
    r0, r1, r2 = max_ds
    r_max = r0 if (r0 >= r1 and r0 >= r2) else (r1 if r1 >= r2 else r2)
    radius = r_max + 1.5
    candidates = grid.query_radius(x, y, radius)
    _pos = grid._pos
    _delta = grid._toroidal_delta
    _w = grid.width
    _h = grid.height

    a0, a1, a2 = ray_angles
    c0, s0 = math.cos(a0), math.sin(a0)
    c1, s1 = math.cos(a1), math.sin(a1)
    c2, s2 = math.cos(a2), math.sin(a2)
    best0, best1, best2 = r0, r1, r2
    type0 = type1 = type2 = None

    for eid in candidates:
        if eid == ignore_id:
            continue
        ex, ey, et = _pos[eid]
        dx = _delta(ex, x, _w)
        dy = _delta(ey, y, _h)

        # Ray 0
        p0 = dx * c0 + dy * s0
        if 0.2 < p0 < best0:
            perp0 = dx * s0 - dy * c0
            if -1.5 <= perp0 <= 1.5:
                best0 = p0
                type0 = et

        # Ray 1
        p1 = dx * c1 + dy * s1
        if 0.2 < p1 < best1:
            perp1 = dx * s1 - dy * c1
            if -1.5 <= perp1 <= 1.5:
                best1 = p1
                type1 = et

        # Ray 2
        p2 = dx * c2 + dy * s2
        if 0.2 < p2 < best2:
            perp2 = dx * s2 - dy * c2
            if -1.5 <= perp2 <= 1.5:
                best2 = p2
                type2 = et

    return [(best0, type0), (best1, type1), (best2, type2)]


def build_inputs_batch(soa, spatial_grid=None, world=None, max_chill: float = 12.0) -> object:
    """Build (N,16) inputs from SoA. Pure vectorized where numpy available.

    spatial_grid: optional SpatialHashGrid for raycasts (uses its query).
    world: fallback for terrain slope and entity raycasting if provided.
    """
    N = soa.N
    if N == 0:
        if HAS_NUMPY:
            return np.zeros((0, 16), dtype=np.float32)
        return []

    if HAS_NUMPY:
        # 9.3 zero-alloc: reuse pre-allocated buffer directly, no copy
        inp = soa.inputs_buf[:N]
        inp[:, :] = 0
        # 0-2: normalized vitals
        # stats: [energy, max_energy, health, chill]
        inp[:, 0] = np.clip(soa.stats[:N, 0] / np.maximum(soa.stats[:N, 1], 1e-6), 0, 1)
        inp[:, 1] = np.clip(soa.stats[:N, 2] / 100.0, 0, 1)  # health /100
        inp[:, 2] = np.clip(soa.stats[:N, 3] / max_chill, 0, 1)

        # 3-8: raycasts — BH-7 neuro-morphological coupling
        # Precompute morph-coupled span & sensitivity per agent if traits baked
        has_morph = hasattr(soa, "morph_traits") and getattr(soa.morph_traits, "shape", None) is not None and soa.morph_traits.shape[0] >= N  # type: ignore
        # PERF: resolve the sensing path once per batch (grid/_pos are static
        # across the batch, so branch outcomes are identical per agent).
        use_grid = spatial_grid is not None and bool(getattr(spatial_grid, "_pos", None))
        for n in range(N):
            x = float(soa.pos[n, 0])
            y = float(soa.pos[n, 1])
            ang = float(soa.angle[n])
            aid = int(soa.ids[n])
            # BH-7: cone span by perimeter/area, forward sensitivity by tip sharpness
            span_factor = 1.0
            forward_gain = 1.0
            if has_morph:
                try:
                    # morph_traits: [A,P,Izz,theta,asym,Dmult]
                    perim = float(soa.morph_traits[n, 1])  # type: ignore
                    theta = float(soa.morph_traits[n, 3])  # type: ignore
                    dmult = float(soa.morph_traits[n, 5])  # type: ignore
                    # span widened for bulky / high-perimeter bodies
                    if perim > 1e-3:
                        span_factor = max(0.75, min(1.55, perim / 5.657))
                    # forward ray sensitivity scaled by razor sharpness (smaller theta → larger gain)
                    # dmult already encodes sharpness (0 at 60°, 1 at 0°)
                    forward_gain = 1.0 + dmult * 0.45
                except Exception:
                    pass
            # side ray deltas scaled by span_factor
            deltas = (-0.610865 * span_factor, 0.0, 0.610865 * span_factor)
            ray_angles = (ang + deltas[0], ang + deltas[1], ang + deltas[2])
            max_ds = (32.0, 32.0 * forward_gain, 32.0)
            if use_grid:
                # PERF: one agent-centered query serves all 3 rays (see proof).
                ray_hits = _batch_raycast_all(spatial_grid, x, y, ray_angles, max_ds, ignore_id=aid)
            else:
                ray_hits = []
                for ri2, a2 in enumerate(ray_angles):
                    max_d2 = max_ds[ri2]
                    if spatial_grid is not None and getattr(spatial_grid, "_pos", None):
                        dist2, typ2 = spatial_grid.raycast((x, y), a2, max_d2, ignore_id=aid)
                    elif world is not None:
                        dist2, typ2 = _raycast_world(world, (x, y), a2, max_d2, ignore_id=aid)
                    else:
                        dist2, typ2 = max_d2, None
                    ray_hits.append((dist2, typ2))
            for ri, delta in enumerate(deltas):  # -35°*span,0,+35°*span
                # forward ray (ri==1) gets sensitivity boost via extended max_dist scaling in norm
                max_d = max_ds[ri]
                dist, typ = ray_hits[ri]
                norm = 1.0 - min(dist / max_d, 1.0)
                # forward ray boosted already via max_d scaling; also amplify norm slightly for sharp hunters
                if ri == 1 and forward_gain != 1.0:
                    norm = min(1.0, norm * forward_gain)
                # encode type: food/ally +1, wall 0, enemy -1, none 0
                if typ is None:
                    tval = 0.0
                elif typ in ("food", "ally", "Food", "Ally"):
                    tval = 1.0
                elif typ in ("wall", "obstacle", "rock", "house"):
                    tval = 0.0
                else:
                    tval = -1.0
                # slot mapping: 3,4 = left dist/type, 5,6 = mid, 7,8 = right
                base = 3 + ri * 2
                inp[n, base] = norm
                inp[n, base + 1] = tval

        # 9-10: audio (stub: 0)
        inp[:, 9] = 0.0
        inp[:, 10] = 0.0
        # 11-12: pheromone (stub)
        inp[:, 11] = 0.0
        inp[:, 12] = 0.0
        # 13: collision impulse (stub)
        inp[:, 13] = 0.0
        # 14: slope grade (if world has elevation)
        if world is not None and hasattr(world, "_elev_at"):
            for n in range(N):
                try:
                    # crude grade via two points ahead/behind
                    x = float(soa.pos[n, 0]); y = float(soa.pos[n, 1]); ang = float(soa.angle[n])
                    ahead_x = x + math.cos(ang) * 2.0
                    ahead_y = y + math.sin(ang) * 2.0
                    # use elev_grid if present
                    h0 = world._elev_at(x, y) if hasattr(world, "_elev_at") else 0.5
                    h1 = world._elev_at(ahead_x, ahead_y) if hasattr(world, "_elev_at") else 0.5
                    grade = float(np.clip((h1 - h0) * 4.0, -1, 1)) if HAS_NUMPY else max(-1,min(1,(h1-h0)*4))
                except Exception:
                    grade = 0.0
                inp[n, 14] = grade
        else:
            inp[:, 14] = 0.0
        # 15: hidden
        inp[:, 15] = soa.hidden_state[:N, 0]
        return inp
    else:
        # pure python
        inp = []
        for n in range(N):
            row = [0.0]*16
            # 0-2
            max_e = soa.stats[n][1] if soa.stats[n][1] != 0 else 1.0
            row[0] = max(0,min(1, soa.stats[n][0]/max_e))
            row[1] = max(0,min(1, soa.stats[n][2]/100.0))
            row[2] = max(0,min(1, soa.stats[n][3]/max_chill))
            # raycasts — BH-7 coupling (pure python)
            span_factor = 1.0
            forward_gain = 1.0
            if hasattr(soa, "morph_traits") and len(soa.morph_traits) > n:
                try:
                    mt = soa.morph_traits[n]
                    perim = float(mt[1]) if len(mt) > 1 else 0.0
                    dmult = float(mt[5]) if len(mt) > 5 else 0.0
                    if perim > 1e-3:
                        span_factor = max(0.75, min(1.55, perim / 5.657))
                    forward_gain = 1.0 + dmult * 0.45
                except Exception:
                    pass
            deltas = (-0.610865 * span_factor, 0.0, 0.610865 * span_factor)
            x, y = soa.pos[n]
            ang = soa.angle[n]
            aid = int(soa.ids[n])
            for ri, delta in enumerate(deltas):
                a = ang + delta
                max_d = 32.0 * (forward_gain if ri == 1 else 1.0)
                if spatial_grid is not None and getattr(spatial_grid, "_pos", None):
                    dist, typ = spatial_grid.raycast((x, y), a, max_d, ignore_id=aid)
                elif world is not None:
                    dist, typ = _raycast_world(world, (x, y), a, max_d, ignore_id=aid)
                else:
                    dist, typ = max_d, None
                norm = 1.0 - min(dist / max_d, 1.0)
                if ri == 1 and forward_gain != 1.0:
                    norm = min(1.0, norm * forward_gain)
                tval = 0.0
                if typ in ("food","ally","Food","Ally"):
                    tval = 1.0
                elif typ in ("wall","obstacle","rock","house"):
                    tval = 0.0
                elif typ is not None:
                    tval = -1.0
                base = 3 + ri*2
                row[base] = norm
                row[base+1] = tval
            row[9]=0.0; row[10]=0.0; row[11]=0.0; row[12]=0.0; row[13]=0.0; row[14]=0.0
            row[15]=soa.hidden_state[n][0]
            inp.append(row)
        return inp


def apply_outputs_batch(soa, outputs, k_thrust: float = 0.005) -> None:
    """Map 7 outputs to SoA state: thrust->vel & energy, steer->angle, etc.

    This is the actuator side; world-level side effects (consume, attack,
    mating) are handled by evolution.sim_loop integration, not here.
    """
    N = soa.N
    if N == 0:
        return
    if HAS_NUMPY:
        # outputs shape (N,7)
        thrust = outputs[:, 0]  # [0,1]
        steer = outputs[:, 1]   # [-1,1]
        # apply steer to angle
        soa.angle[:N] += steer * 0.35  # steer_turn ~0.35 rad
        # apply thrust to vel (vel = thrust * direction)
        soa.vel[:N, 0] = np.cos(soa.angle[:N]) * thrust * 0.9
        soa.vel[:N, 1] = np.sin(soa.angle[:N]) * thrust * 0.9
        # pos integration is done at 60Hz in sim_loop; here we just drain energy
        soa.stats[:N, 0] -= (thrust * thrust) * k_thrust * 100.0  # scale to be noticeable
        # clamp
        soa.stats[:N, 0] = np.maximum(soa.stats[:N, 0], 0.0)
        # store outputs for later world queries (social/interact/vocal)
        soa.outputs_buf[:N] = outputs
    else:
        for n in range(N):
            thrust = outputs[n][0]
            steer = outputs[n][1]
            soa.angle[n] += steer * 0.35
            soa.vel[n][0] = math.cos(soa.angle[n]) * thrust * 0.9
            soa.vel[n][1] = math.sin(soa.angle[n]) * thrust * 0.9
            soa.stats[n][0] -= (thrust*thrust) * k_thrust * 100.0
            if soa.stats[n][0] < 0:
                soa.stats[n][0]=0
            soa.outputs_buf[n]=outputs[n][:]
