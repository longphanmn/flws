"""Density-Dependent Soft-Cap Damping Engine — Phase 4.

Implements non-linear homeostatic damping xi(N) for overpopulation.
Runs at 1 Hz, zero-alloc when disabled.
"""

from __future__ import annotations

import math
from typing import Dict


XI_ONSET_FRAC = 0.85   # partial damping begins at 0.85*K (below the old hard K edge)
XI_RELEASE_TAU = 300.0  # ticks time-constant for the exponential xi release toward target


def compute_xi(N: int, Kcap: int, enabled: bool) -> float:
    """Overpopulation stress index xi(N) with a hysteresis onset below K.

    Damping now begins at XI_ONSET_FRAC * Kcap instead of exactly Kcap, then
    scales by Kcap:

        xi = max(0, (N - 0.85*Kcap) / Kcap)

    Starting the restoring force below K gives the controller something to pull
    with before the population overshoots, instead of a bang-bang edge at K.
    """
    if not enabled or Kcap <= 0:
        return 0.0
    try:
        onset = float(Kcap) * XI_ONSET_FRAC
        if N <= onset:
            return 0.0
        return (float(N) - onset) / float(Kcap)
    except Exception:
        return 0.0


def population_envelope(config):
    """§G1 the hard absorbing band (lo, hi) in absolute population, or None.

    None means the law is off, or the band is incoherent (lo >= hi, which would
    make the lower edge unreachable). Every call site must treat None as "no
    envelope" and must not consume randomness on that path, so the law stays
    inert — including on the RNG stream — until it is switched on.
    """
    try:
        if not bool(getattr(config, "population_envelope_enabled", False)):
            return None
        kcap = float(getattr(config, "effective_carrying_capacity", 0.0) or 0.0)
        if kcap <= 0:
            return None
        lo = kcap * float(getattr(config, "pop_env_lo_frac", 1.0))
        hi = kcap * float(getattr(config, "pop_env_hi_frac", 1.0))
    except Exception:
        return None
    if not (0.0 < lo < hi):
        return None
    return lo, hi


def envelope_lower_boost(n, lo, hi, lo_boost):
    """§G1 the envelope's reflecting lower edge, as extra birth room.

    The lower edge must push a population that has drifted out through it *back
    up* into the band. It cannot do that by killing: deaths imposed on a
    population that is already short drive it further down, a positive feedback
    away from the band. So the edge lifts births instead, and the lift is a pure
    multiplier of the ordinary birth room.

    It rises linearly from 0 at N = lo (so there is no step discontinuity to
    drive a limit cycle) to ``lo_boost`` at the *reach* boundary, one envelope
    width (hi - lo) below lo. Below reach the law has no jurisdiction: a world
    legitimately smaller than the band is running its own famine/extinction
    dynamics, and a permanent fertility bonus would mask that equilibrium.

    Zero above lo, so the band interior and the ceiling are untouched. Never
    negative, and never any kind of mortality term.
    """
    try:
        n, lo, hi, lo_boost = float(n), float(lo), float(hi), float(lo_boost)
    except (TypeError, ValueError):
        return 0.0
    if lo_boost <= 0.0 or not (0.0 < lo < hi):
        return 0.0
    reach = lo - (hi - lo)
    if n >= lo or n < reach:
        return 0.0
    span = 1.0 - reach / lo
    if span <= 0.0:
        return 0.0
    return lo_boost * (1.0 - n / lo) / span


def scales_for_xi(xi: float, config) -> Dict[str, float]:
    """Compute 4-channel damping scales for xi."""
    try:
        damping = float(getattr(config, "damping_steepness", 7.0))
        crowding = float(getattr(config, "crowding_stress_mult", 1.5))
        resource = float(getattr(config, "resource_strain_mult", 2.0))
        k = float(getattr(config, "damping_sigmoid_k", 5.0))
    except Exception:
        damping = 7.0
        crowding = 1.5
        resource = 2.0
        k = 5.0

    if xi <= 0.0:
        return {
            "birth_rate_eff": 1.0,
            "birth_cost_eff": 1.0,
            "cooldown_eff": 1.0,
            "mate_thr_eff": 1.0,
            "decay_eff": 1.0,
            "growth_eff": 1.0,
            "spread_eff": 1.0,
            "outbreak_eff": 1.0,
            "xi": 0.0,
        }

    # Smooth sigmoid transition: sig = 1/(1+exp(k*xi)), w = 1 - 2*sig
    # Continuous in value (1.0) and slope (0.0) at xi=0 with flat start,
    # transitioning smoothly to existing suppression strength for larger xi.
    sig = 1.0 / (1.0 + math.exp(min(50.0, k * xi)))
    w = max(0.0, min(1.0, 1.0 - 2.0 * sig))

    # Channel 1: aggressive reproductive suppression (cubic & quadratic terms)
    raw_birth_rate_eff = 1.0 / (1.0 + 3.0 * damping * xi + (damping * xi) ** 2)
    raw_birth_cost_eff = 1.0 + 3.0 * xi + 2.0 * xi * xi
    raw_cooldown_eff = 1.0 + 5.0 * xi + 6.0 * xi * xi
    raw_mate_thr_eff = 1.0 + 2.5 * xi + 2.0 * xi * xi

    # Channel 2: crowding stress (quadratic scaling to accelerate resolution)
    raw_decay_eff = 1.0 + crowding * xi + 0.8 * crowding * xi * xi

    # Channel 3: ecological strain
    raw_growth_eff = 1.0 / (1.0 + resource * xi * 1.5)
    raw_spread_eff = 1.0 / (1.0 + 3.0 * xi)

    # Channel 4: social friction (pathogens)
    raw_outbreak_eff = 1.0 + 4.0 * xi

    return {
        "birth_rate_eff": 1.0 + w * (raw_birth_rate_eff - 1.0),
        "birth_cost_eff": 1.0 + w * (raw_birth_cost_eff - 1.0),
        "cooldown_eff": 1.0 + w * (raw_cooldown_eff - 1.0),
        "mate_thr_eff": 1.0 + w * (raw_mate_thr_eff - 1.0),
        "decay_eff": 1.0 + w * (raw_decay_eff - 1.0),
        "growth_eff": 1.0 + w * (raw_growth_eff - 1.0),
        "spread_eff": 1.0 + w * (raw_spread_eff - 1.0),
        "outbreak_eff": 1.0 + w * (raw_outbreak_eff - 1.0),
        "xi": xi,
    }


class DensityDampingEngine:
    """1 Hz engine for xi(N) and scales."""

    def __init__(self, config):
        self.config = config
        self.last_xi = 0.0
        self.last_scales: Dict[str, float] = {}
        self.last_N = 0
        self._last_decay_tick = -1

    def update(self, N: int, tick: int, Kcap: int | None = None) -> tuple[float, Dict[str, float]]:
        # step() computes xi from the previous tick's cache for metabolism, then
        # _reproduce() asks again with the live count. Allow the live count to
        # raise xi immediately, but apply the *release* decay at most once per
        # tick so two calls cannot double-count the slew.
        if Kcap is None:
            Kcap = int(getattr(self.config, "effective_carrying_capacity", getattr(self.config, "carrying_capacity", 350)))
        enabled = bool(getattr(self.config, "soft_cap_enabled", True))
        tau = float(getattr(self.config, "damping_release_tau", XI_RELEASE_TAU) or XI_RELEASE_TAU)
        target = compute_xi(N, Kcap, enabled)
        if not enabled:
            xi = 0.0
        elif target >= self.last_xi:
            xi = target  # onset is immediate — no lag on the braking side
        elif tick != self._last_decay_tick:
            # Exponential release toward the target instead of snapping to 0.
            # Prevents the birth brake from switching fully off the instant N
            # dips below the onset edge (the textbook delay-induced limit cycle).
            xi = target + (self.last_xi - target) * math.exp(-1.0 / max(1.0, tau))
            if (xi - target) < 0.005:
                xi = target
            self._last_decay_tick = tick
        else:
            xi = self.last_xi
        scales = scales_for_xi(xi, self.config)
        self.last_xi = xi
        self.last_scales = scales
        self.last_N = N
        return xi, scales
