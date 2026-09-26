"""Morphological Physics Engine — polar polygon genomes K∈[3,24].

Vectorized batch with numpy fallback. Zero-alloc tick when disabled.
Implements Phase 2 polar formulations + trait baking per new spec.
"""

from __future__ import annotations

import math
from typing import Optional

try:
    import numpy as np  # type: ignore

    HAS_NUMPY = True
except Exception:  # pragma: no cover
    np = None  # type: ignore
    HAS_NUMPY = False

KMAX = 24
R_MIN, R_MAX = 0.2, 2.5

# Reference square Gentleman r=1.0 K=4 — Aref=2, Pref≈5.657, Iref≈0.333
A_REF = 2.0
P_REF = 4 * math.sqrt(2)  # ≈5.65685
I_REF = 2.0 / 3.0


def compute_polygon_vertices(r, phi, k: int):
    """Convert polar arrays to local Cartesian offsets."""
    import math as _m

    xs = []
    ys = []
    for i in range(k):
        ri = float(r[i]) if hasattr(r, "__getitem__") else float(r)
        ph = float(phi[i]) if hasattr(phi, "__getitem__") else float(phi)
        xs.append(ri * _m.cos(ph))
        ys.append(ri * _m.sin(ph))
    return xs, ys


def compute_shoelace_area(x, y, k: int) -> float:
    s = 0.0
    for i in range(k):
        j = (i + 1) % k
        s += x[i] * y[j] - x[j] * y[i]
    return abs(s) * 0.5


def compute_perimeter(x, y, k: int) -> float:
    p = 0.0
    for i in range(k):
        j = (i + 1) % k
        dx = x[j] - x[i]
        dy = y[j] - y[i]
        p += math.hypot(dx, dy)
    return p


def compute_moment_of_inertia(x, y, k: int, area: float) -> float:
    if area < 1e-6:
        return 0.0
    s = 0.0
    for i in range(k):
        j = (i + 1) % k
        cross = x[i] * y[j] - x[j] * y[i]
        s += cross * (x[i] * x[i] + x[i] * x[j] + x[j] * x[j] + y[i] * y[i] + y[i] * y[j] + y[j] * y[j])
    return abs(s) / (12 * area + 1e-9)


def compute_min_vertex_angle(x, y, k: int) -> float:
    best = math.pi
    for i in range(k):
        im1 = (i - 1) % k
        ip1 = (i + 1) % k
        ux = x[im1] - x[i]
        uy = y[im1] - y[i]
        vx = x[ip1] - x[i]
        vy = y[ip1] - y[i]
        nu = math.hypot(ux, uy)
        nv = math.hypot(vx, vy)
        if nu < 1e-9 or nv < 1e-9:
            continue
        cosv = (ux * vx + uy * vy) / (nu * nv)
        cosv = max(-1.0, min(1.0, cosv))
        ang = math.acos(cosv)
        if ang < best:
            best = ang
    return best if best != math.pi else math.pi * 0.5


def compute_asymmetry_index(r, k: int) -> float:
    if k <= 0:
        return 0.0
    vals = [float(r[i]) for i in range(k)]
    mean = sum(vals) / k
    if mean < 1e-9:
        return 0.0
    var = sum((v - mean) ** 2 for v in vals) / k
    return var / mean


# Keep legacy single helpers for internal use
def _shoelace_single(xs, ys, k: int) -> float:
    return compute_shoelace_area(xs, ys, k)


def _perimeter_single(xs, ys, k: int) -> float:
    return compute_perimeter(xs, ys, k)


def _inertia_single(xs, ys, k: int, area: float) -> float:
    return compute_moment_of_inertia(xs, ys, k, area)


def _min_angle_single(xs, ys, k: int) -> float:
    return compute_min_vertex_angle(xs, ys, k)


def _asymmetry_single(r, k: int) -> float:
    return compute_asymmetry_index(r, k)


def batch_compute_traits(morph_radii, morph_angles, morph_k, out_traits=None):
    """Compute (N,6) physical_traits for all active. Numpy vectorized when possible."""
    if HAS_NUMPY and isinstance(morph_radii, np.ndarray):
        N = morph_radii.shape[0]
        if out_traits is None:
            out_traits = np.zeros((N, 6), dtype=np.float64)
        for idx in range(N):
            k = int(morph_k[idx]) if hasattr(morph_k, "__getitem__") else int(morph_k)
            if k < 3:
                out_traits[idx, :] = 0
                continue
            r = morph_radii[idx]
            phi = morph_angles[idx]
            xs = r[:k] * np.cos(phi[:k])  # type: ignore
            ys = r[:k] * np.sin(phi[:k])  # type: ignore
            x_next = np.roll(xs, -1)
            y_next = np.roll(ys, -1)
            area = float(np.abs(np.sum(xs * y_next - x_next * ys)) * 0.5)
            dx = x_next - xs
            dy = y_next - ys
            perim = float(np.sum(np.sqrt(dx * dx + dy * dy)))
            cross = xs * y_next - x_next * ys
            if area > 1e-6:
                inertia = float(np.abs(np.sum(cross * (xs * xs + xs * x_next + x_next * x_next + ys * ys + ys * y_next + y_next * y_next))) / (12 * area))
            else:
                inertia = 0.0
            best = math.pi
            for i in range(k):
                im1 = (i - 1) % k
                ip1 = (i + 1) % k
                ux = float(xs[im1] - xs[i])
                uy = float(ys[im1] - ys[i])
                vx = float(xs[ip1] - xs[i])
                vy = float(ys[ip1] - ys[i])
                nu = math.hypot(ux, uy)
                nv = math.hypot(vx, vy)
                if nu < 1e-9 or nv < 1e-9:
                    continue
                cosv = (ux * vx + uy * vy) / (nu * nv)
                cosv = max(-1.0, min(1.0, cosv))
                ang = math.acos(cosv)
                if ang < best:
                    best = ang
            theta = best if best != math.pi else math.pi * 0.5
            rk = r[:k]
            mean_r = float(np.mean(rk))
            var_r = float(np.var(rk))
            asym = (var_r / mean_r) if mean_r > 1e-9 else 0.0
            cos_theta = math.cos(theta)
            dmult = max(0.0, (cos_theta - 0.5) / 0.5)
            out_traits[idx, 0] = area
            out_traits[idx, 1] = perim
            out_traits[idx, 2] = inertia
            out_traits[idx, 3] = theta
            out_traits[idx, 4] = asym
            out_traits[idx, 5] = dmult
        return out_traits
    else:
        N = len(morph_radii)
        if out_traits is None:
            out_traits = [[0.0] * 6 for _ in range(N)]
        for idx in range(N):
            k = int(morph_k[idx])
            if k < 3:
                out_traits[idx] = [0.0] * 6
                continue
            r = morph_radii[idx]
            phi = morph_angles[idx]
            xs, ys = compute_polygon_vertices(r, phi, k)
            area = compute_shoelace_area(xs, ys, k)
            perim = compute_perimeter(xs, ys, k)
            inertia = compute_moment_of_inertia(xs, ys, k, area)
            theta = compute_min_vertex_angle(xs, ys, k)
            asym = compute_asymmetry_index(r, k)
            cos_theta = math.cos(theta)
            dmult = max(0.0, (cos_theta - 0.5) / 0.5)
            out_traits[idx][0] = area
            out_traits[idx][1] = perim
            out_traits[idx][2] = inertia
            out_traits[idx][3] = theta
            out_traits[idx][4] = asym
            out_traits[idx][5] = dmult
        return out_traits


def bake_physical_traits(soa, indices=None, config=None) -> None:
    """Batch bake physical_traits for given indices (or all active if None)."""
    if HAS_NUMPY and hasattr(soa, "morph_radii") and hasattr(soa.morph_radii, "shape"):
        N = soa.N
        if N == 0:
            return
        if indices is None:
            indices = range(N)
            # use full batch
            traits = batch_compute_traits(soa.morph_radii[:N], soa.morph_angles[:N], soa.morph_k[:N])
            soa.physical_traits[:N] = traits[:N]  # type: ignore
            # also keep alias for backward compat
            if hasattr(soa, "morph_traits"):
                soa.morph_traits[:N] = traits[:N]
        else:
            # indices as list/array
            import numpy as _np  # type: ignore

            idx_list = list(indices)
            if not idx_list:
                return
            sub_r = soa.morph_radii[idx_list]
            sub_a = soa.morph_angles[idx_list]
            sub_k = soa.morph_k[idx_list]
            traits = batch_compute_traits(sub_r, sub_a, sub_k)
            for i, idx in enumerate(idx_list):
                soa.physical_traits[idx] = traits[i]  # type: ignore
                if hasattr(soa, "morph_traits"):
                    soa.morph_traits[idx] = traits[i]
    else:
        # python fallback list
        N = len(soa.morph_radii) if hasattr(soa, "morph_radii") else 0
        if indices is None:
            indices = range(N)
        for idx in indices:
            k = int(soa.morph_k[idx])
            if k < 3:
                continue
            xs, ys = compute_polygon_vertices(soa.morph_radii[idx], soa.morph_angles[idx], k)
            area = compute_shoelace_area(xs, ys, k)
            perim = compute_perimeter(xs, ys, k)
            izz = compute_moment_of_inertia(xs, ys, k, area)
            theta = compute_min_vertex_angle(xs, ys, k)
            asym = compute_asymmetry_index(soa.morph_radii[idx], k)
            dmult = max(0.0, (math.cos(theta) - 0.5) / 0.5)
            soa.physical_traits[idx] = [area, perim, izz, theta, asym, dmult]  # type: ignore
            if hasattr(soa, "morph_traits"):
                soa.morph_traits[idx] = [area, perim, izz, theta, asym, dmult]

    # Apply trait baking caps per individual if config provided (optional per-agent E_max etc handled in simulation)
    # This function only populates physical_traits; baking to E_max etc is done in simulation's bake wrapper
    return None


def bake_traits_for_index(idx: int, soa, config=None) -> dict:
    """Legacy single-index wrapper (kept for backward compat). Calls batch for one.

    PERF (no logic change): pure function of the slot's immutable morph
    buffers (written once at add_agent, moved only by swap-with-last which
    changes the occupying eid). Memoize per (slot -> eid); a hit returns the
    identical dict and skips the numpy recompute entirely.
    """
    try:
        _bc = getattr(soa, "_bake_cache", None)
        if _bc is None:
            _bc = {}
            soa._bake_cache = _bc  # type: ignore[attr-defined]
        try:
            _eid = int(soa.ids[idx])  # type: ignore
        except Exception:
            _eid = -1
        _hit = _bc.get(int(idx))
        if _hit is not None and _hit[0] == _eid:
            return _hit[1]
    except Exception:
        _bc = None  # type: ignore
        _eid = -1
    bake_physical_traits(soa, indices=[idx], config=config)
    # return dict with baked physics for caller convenience
    if HAS_NUMPY and hasattr(soa, "physical_traits"):
        area, perim, izz, theta, asym, dmult = [float(v) for v in soa.physical_traits[idx]]  # type: ignore
    else:
        area, perim, izz, theta, asym, dmult = soa.physical_traits[idx]  # type: ignore
    emax_scale = max(0.5, min(2.5, (area / A_REF) if A_REF else 1.0))
    decay_scale = max(0.7, min(2.0, (perim / P_REF) if P_REF else 1.0))
    irregularity = max(0.0, min(1.0, asym * 1.5))
    out = {
        "area": area,
        "perimeter": perim,
        "izz": izz,
        "theta_min": theta,
        "asymmetry": asym,
        "dmult": dmult,
        "emax_scale": emax_scale,
        "decay_scale": decay_scale,
        "irregularity": irregularity,
    }
    try:
        if _bc is not None:
            _bc[int(idx)] = (_eid, out)
    except Exception:
        pass
    return out


def sat_overlap(ax, ay, bx, by) -> bool:
    """SAT for convex polygons (ax,ay) and (bx,by) lists. Includes circle fallback for K>=24."""
    import math as _m

    ka = len(ax)
    kb = len(bx)
    if ka < 3 or kb < 3:
        return False

    # Circle approximation fallback: if K>=24 and low asymmetry, use circle-polygon test
    # Caller should check asymmetry <0.05 and K>=24 before calling; we handle generically
    def poly_axes(xs, ys):
        k = len(xs)
        a = []
        for i in range(k):
            j = (i + 1) % k
            ex = xs[j] - xs[i]
            ey = ys[j] - ys[i]
            nx, ny = -ey, ex
            l = _m.hypot(nx, ny)
            if l > 1e-9:
                a.append((nx / l, ny / l))
        return a

    axes_a = poly_axes(ax, ay)
    axes_b = poly_axes(bx, by)
    # If circle-like (K>=24), add single radial axis from centroid delta for efficiency
    # For now, just use polygon axes (circle fallback reduces to 1 axis + polygon normals, but we approximate)
    for nx, ny in axes_a + axes_b:
        min_a = max_a = ax[0] * nx + ay[0] * ny
        for i in range(1, ka):
            p = ax[i] * nx + ay[i] * ny
            if p < min_a:
                min_a = p
            if p > max_a:
                max_a = p
        min_b = max_b = bx[0] * nx + by[0] * ny
        for i in range(1, kb):
            p = bx[i] * nx + by[i] * ny
            if p < min_b:
                min_b = p
            if p > max_b:
                max_b = p
        if max_a < min_b - 1e-9 or max_b < min_a - 1e-9:
            return False
    return True
