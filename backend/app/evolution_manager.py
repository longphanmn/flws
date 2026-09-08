"""BC.3 Morphological Annealing & Abbott Caste Bridge.

Templates + λ(g) + inheritance / topological mutation.
"""
from __future__ import annotations

import math
import random
from typing import Tuple

try:
    import numpy as np  # type: ignore

    HAS_NUMPY = True
except Exception:
    np = None  # type: ignore
    HAS_NUMPY = False

from .morphology_engine import KMAX, R_MIN, R_MAX

# Abbott canonical templates — polar (r, phi) per caste, K∈[3,24] per new spec
# Woman line degenerate: thin triangle proxy
TEMPLATES: dict[str, Tuple[list, list, int]] = {
    "Woman": ([1.8, 0.2, 0.2], [0.0, math.pi - 0.08, math.pi + 0.08], 3),
    "Soldier": ([1.5, 0.8, 0.8], [0.0, 2.4, 3.88], 3),
    "Artisan": ([1.0, 1.0, 1.0], [0.0, 2 * math.pi / 3, 4 * math.pi / 3], 3),
    "Gentleman": ([1.0] * 4, [i * math.pi / 2 for i in range(4)], 4),
    "Professional": ([1.0] * 5, [i * 2 * math.pi / 5 for i in range(5)], 5),
    "Noble": ([1.0] * 8, [i * 2 * math.pi / 8 for i in range(8)], 8),
    "Priest": ([1.0] * 24, [i * 2 * math.pi / 24 for i in range(24)], 24),
}

# caste -> template key
CASTE_TEMPLATE = {
    "Woman": "Woman",
    "Soldier": "Soldier",
    "Artisan": "Artisan",
    "Gentleman": "Gentleman",
    "Professional": "Professional",
    "Noble": "Noble",
    "Priest": "Priest",
    "Predator": "Noble",
    "Herbivore": "Gentleman",
}


def lambda_for_generation(g: int, config) -> float:
    """3.2 λ(g) per new spec: override -1.0 means auto."""
    override = getattr(config, "morph_lambda_override", None)
    # Spec: if override is not None and >=0, use it; -1.0 means auto annealing
    if override is not None:
        try:
            ov = float(override)
            if ov >= 0.0:
                return max(0.0, min(1.0, ov))
        except Exception:
            pass
    if not getattr(config, "morphology_annealing_enabled", True):
        return 1.0  # frozen classical when explicitly disabled
    g_start = int(getattr(config, "annealing_start_generation", 15))
    g_decay = int(getattr(config, "annealing_decay_generations", 250))
    if g < g_start:
        return 1.0
    if g_decay <= 0:
        return 0.0
    v = 1.0 - (g - g_start) / float(g_decay)
    return max(0.0, min(1.0, v))


def get_template_for_caste(caste: str):
    key = CASTE_TEMPLATE.get(caste, "Gentleman")
    return TEMPLATES[key]


def _pad_to_kmax(arr, k: int, val=0.0):
    out = [val] * KMAX
    for i in range(min(k, KMAX)):
        out[i] = arr[i] if i < len(arr) else val
    return out


def child_morphology_two_parent(
    mother_r, mother_phi, mother_k: int, father_r, father_phi, father_k: int,
    template_r, template_phi, template_k: int, lam: float, config, rng: random.Random
) -> Tuple[list, list, int]:
    """BH-1 Two-Parent Meiotic Polar Crossover. K_child∈[Kmo,Kfa] with sector-arc recombination."""
    # BH-1: K interpolated between parents and template; respect child's caste template
    k_min = min(int(mother_k), int(father_k), int(template_k))
    k_max = max(int(mother_k), int(father_k), int(template_k))
    if int(template_k) not in (int(mother_k), int(father_k)):
        # Child belongs to a caste with a distinct geometric specification (e.g. Woman/Soldier)
        base_k = int(template_k)
    else:
        k_avg = (int(mother_k) + int(father_k)) // 2
        base_k = int(round(lam * template_k + (1 - lam) * k_avg))
        base_k = max(k_min, min(k_max, base_k))
        # allow ±1 drift within interval 30% chance to encourage exploration
        if rng.random() < 0.3 and k_min != k_max:
            base_k += rng.choice((-1, 1))
            base_k = max(k_min, min(k_max, base_k))
    base_k = max(3, min(KMAX, base_k))

    sigma_r = float(getattr(config, "vertex_mutation_std", 0.05))
    sigma_phi = float(getattr(config, "angle_mutation_std", 0.02))
    topo_rate = float(getattr(config, "topological_mutation_rate", 0.01))

    child_r = [1.0] * KMAX
    child_phi = [0.0] * KMAX

    # BH-1 sector-arc recombination: per-vertex source parent chosen 50% (meiotic)
    # We map child fractional progress t=i/K_child to parent indices
    for i in range(base_k):
        tr = template_r[i] if i < template_k and i < len(template_r) else 1.0
        tphi = template_phi[i] if i < template_k and i < len(template_phi) else (2 * math.pi * i / base_k)
        # pick parent source for this sector
        t = i / max(1, base_k)
        mi = int(t * mother_k) % max(1, mother_k)
        fi = int(t * father_k) % max(1, father_k)
        # meiotic choice
        use_mother = rng.random() < 0.5
        pr = mother_r[mi] if use_mother else father_r[fi]
        pphi = mother_phi[mi] if use_mother else father_phi[fi]
        # also consider blending 10% chance of averaging (recombinant intermediate)
        if rng.random() < 0.10:
            pr = 0.5 * (mother_r[mi] + father_r[fi])
            # circular mean for phi: choose shortest arc
            dphi = (father_phi[fi] - mother_phi[mi] + math.pi) % (2 * math.pi) - math.pi
            pphi = (mother_phi[mi] + 0.5 * dphi) % (2 * math.pi)
        noisy_r = pr + rng.gauss(0, sigma_r) if sigma_r > 0 else pr
        noisy_r = max(R_MIN, min(R_MAX, noisy_r))
        noisy_phi = pphi + (rng.gauss(0, sigma_phi) if sigma_phi > 0 else 0.0)
        cr = lam * tr + (1 - lam) * noisy_r
        cphi = lam * tphi + (1 - lam) * noisy_phi
        cr = max(R_MIN, min(R_MAX, cr))
        child_r[i] = cr
        child_phi[i] = cphi

    # Normalize phi: sort circularly
    pairs = sorted([(child_phi[i] % (2 * math.pi), child_r[i]) for i in range(base_k)])
    for i, (ph, rr) in enumerate(pairs):
        child_phi[i] = ph
        child_r[i] = rr
    for i in range(1, base_k):
        if child_phi[i] - child_phi[i - 1] < 0.05:
            child_phi[i] = child_phi[i - 1] + 0.05

    # Topological mutation after sorting: p = rate*(1-lam)
    p_topo = topo_rate * (1 - lam)
    if p_topo > 0 and rng.random() < p_topo:
        if rng.random() < 0.5 and base_k < KMAX:
            xs = [child_r[i] * math.cos(child_phi[i]) for i in range(base_k)]
            ys = [child_r[i] * math.sin(child_phi[i]) for i in range(base_k)]
            longest = -1
            li = 0
            for i in range(base_k):
                j = (i + 1) % base_k
                d2 = (xs[j] - xs[i]) ** 2 + (ys[j] - ys[i]) ** 2
                if d2 > longest:
                    longest = d2
                    li = i
            new_r = (child_r[li] + child_r[(li + 1) % base_k]) * 0.5
            new_phi = (child_phi[li] + child_phi[(li + 1) % base_k]) * 0.5
            if li + 1 < base_k and child_phi[(li + 1) % base_k] < child_phi[li]:
                new_phi = (child_phi[li] + child_phi[(li + 1) % base_k] + 2 * math.pi) * 0.5 % (2 * math.pi)
            child_r.insert(li + 1, new_r)
            child_phi.insert(li + 1, new_phi)
            child_r = child_r[:KMAX]
            child_phi = child_phi[:KMAX]
            base_k = min(KMAX, base_k + 1)
        elif base_k > 3:
            min_gap = float("inf")
            ri = 0
            for i in range(base_k):
                j = (i + 1) % base_k
                gap = (child_phi[j] - child_phi[i]) % (2 * math.pi)
                if gap < min_gap:
                    min_gap = gap
                    ri = j
            del child_r[ri]
            del child_phi[ri]
            child_r.append(1.0)
            child_phi.append(0.0)
            base_k = max(3, base_k - 1)

    # BH-2 Macro-Mutation Spurts (5% at λ≈0 → freeform speciation)
    if lam < 0.07 and rng.random() < 0.05:
        macro = rng.choice(["apex_weapon", "facet_shield", "crystallize"])
        if macro == "apex_weapon":
            # stretch one vertex +50-100%
            idx = rng.randrange(base_k)
            child_r[idx] = max(R_MIN, min(R_MAX, child_r[idx] * rng.uniform(1.5, 2.0)))
        elif macro == "facet_shield":
            # flatten front edges: vertices within ±60° of 0 (forward) → mean radius
            front_idx = [i for i in range(base_k) if min(child_phi[i] % (2*math.pi), 2*math.pi - child_phi[i] % (2*math.pi)) < 1.05]
            if len(front_idx) >= 2:
                mean_r = sum(child_r[i] for i in front_idx) / len(front_idx)
                for i in front_idx:
                    child_r[i] = max(R_MIN, min(R_MAX, mean_r + rng.gauss(0, 0.04)))
        elif macro == "crystallize":
            # regularize into star: alternating radii 1.4 / 0.7, regular angles
            for i in range(base_k):
                child_phi[i] = 2 * math.pi * i / base_k
                child_r[i] = 1.35 if (i % 2 == 0) else 0.65

    # pad to KMAX
    out_r = [1.0] * KMAX
    out_phi = [0.0] * KMAX
    for i in range(KMAX):
        if i < base_k:
            out_r[i] = child_r[i]
            out_phi[i] = child_phi[i]
        else:
            out_phi[i] = 2 * math.pi * i / KMAX
    return out_r, out_phi, base_k


def child_morphology(
    parent_r, parent_phi, parent_k: int, template_r, template_phi, template_k: int, lam: float, config, rng: random.Random
) -> Tuple[list, list, int]:
    """BC.3.3 interpolate child morphology. lam in [0,1]. (Wrapped for single-parent compat → delegates to two-parent with duplicated parent)."""
    return child_morphology_two_parent(
        parent_r, parent_phi, parent_k, parent_r, parent_phi, parent_k,
        template_r, template_phi, template_k, lam, config, rng
    )

    sigma_r = float(getattr(config, "vertex_mutation_std", 0.05))
    sigma_phi = float(getattr(config, "angle_mutation_std", 0.02))
    topo_rate = float(getattr(config, "topological_mutation_rate", 0.01))

    # Build child arrays length KMAX
    child_r = [1.0] * KMAX
    child_phi = [0.0] * KMAX

    # For indices beyond base_k, fill with mean
    for i in range(base_k):
        tr = template_r[i] if i < template_k and i < len(template_r) else 1.0
        tphi = template_phi[i] if i < template_k and i < len(template_phi) else (2 * math.pi * i / base_k)
        pr = parent_r[i] if i < parent_k and i < len(parent_r) else 1.0
        pphi = parent_phi[i] if i < parent_k and i < len(parent_phi) else (2 * math.pi * i / parent_k if parent_k else 0)
        # clamp parent+noise
        noisy_r = pr + rng.gauss(0, sigma_r) if sigma_r > 0 else pr
        noisy_r = max(R_MIN, min(R_MAX, noisy_r))
        noisy_phi = pphi + (rng.gauss(0, sigma_phi) if sigma_phi > 0 else 0.0)
        # interpolation
        cr = lam * tr + (1 - lam) * noisy_r
        cphi = lam * tphi + (1 - lam) * noisy_phi
        cr = max(R_MIN, min(R_MAX, cr))
        child_r[i] = cr
        child_phi[i] = cphi

    # Normalize phi: sort circularly and unwrap to [0,2π)
    # Map to [0,2π) then sort
    phis = [child_phi[i] % (2 * math.pi) for i in range(base_k)]
    phis_sorted = sorted(phis)
    # Reassign sorted phis, keep r associated by sorted order (stable: sort pairs)
    pairs = sorted([(child_phi[i] % (2 * math.pi), child_r[i]) for i in range(base_k)])
    for i, (ph, rr) in enumerate(pairs):
        child_phi[i] = ph
        child_r[i] = rr
    # Ensure monotonic and avoid duplicate angles within 0.05 rad
    for i in range(1, base_k):
        if child_phi[i] - child_phi[i - 1] < 0.05:
            child_phi[i] = child_phi[i - 1] + 0.05
    # wrap last
    if base_k > 1 and (2 * math.pi - child_phi[-1] + child_phi[0]) < 0.05:
        # spread slightly
        pass

    # Topological mutation after sorting: p = rate*(1-lam)
    p_topo = topo_rate * (1 - lam)
    if p_topo > 0 and rng.random() < p_topo:
        if rng.random() < 0.5 and base_k < KMAX:
            # add vertex at longest edge midpoint
            # find longest edge via cartesian
            xs = [child_r[i] * math.cos(child_phi[i]) for i in range(base_k)]
            ys = [child_r[i] * math.sin(child_phi[i]) for i in range(base_k)]
            longest = -1
            li = 0
            for i in range(base_k):
                j = (i + 1) % base_k
                d2 = (xs[j] - xs[i]) ** 2 + (ys[j] - ys[i]) ** 2
                if d2 > longest:
                    longest = d2
                    li = i
            # insert midpoint
            new_r = (child_r[li] + child_r[(li + 1) % base_k]) * 0.5
            new_phi = (child_phi[li] + child_phi[(li + 1) % base_k]) * 0.5
            if li + 1 < base_k and child_phi[(li + 1) % base_k] < child_phi[li]:
                new_phi = (child_phi[li] + child_phi[(li + 1) % base_k] + 2 * math.pi) * 0.5 % (2 * math.pi)
            # insert
            child_r.insert(li + 1, new_r)
            child_phi.insert(li + 1, new_phi)
            # trim to KMAX
            child_r = child_r[:KMAX]
            child_phi = child_phi[:KMAX]
            base_k = min(KMAX, base_k + 1)
        elif base_k > 3:
            # remove vertex with closest angular neighbor (smallest phi gap)
            min_gap = float("inf")
            ri = 0
            for i in range(base_k):
                j = (i + 1) % base_k
                gap = (child_phi[j] - child_phi[i]) % (2 * math.pi)
                if gap < min_gap:
                    min_gap = gap
                    ri = j
            # remove ri
            del child_r[ri]
            del child_phi[ri]
            child_r.append(1.0)
            child_phi.append(0.0)
            base_k = max(3, base_k - 1)

    # pad to KMAX length arrays for SoA
    out_r = [1.0] * KMAX
    out_phi = [0.0] * KMAX
    for i in range(KMAX):
        if i < base_k:
            out_r[i] = child_r[i]
            out_phi[i] = child_phi[i]
        else:
            out_phi[i] = 2 * math.pi * i / KMAX
    return out_r, out_phi, base_k
