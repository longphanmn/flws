"""Safeguard Engine — Extinction Safeguards & Homeostatic Auto-Balance (Phase 5).

Implements 1 Hz homeostatic loop eta(N), Tier1/2/3 scaling, genesis, and morph mercy.
Zero-alloc tick when disabled.
"""

from __future__ import annotations

import math
import random
from typing import Dict, List, Optional, Tuple


def compute_eta(N: int, carrying_capacity: int, relief_ratio: float, critical_pop: int, enabled: bool) -> float:
    """Homeostatic relief factor eta(N).

    K_safe = carrying * relief_ratio
    eta = clamp((K_safe - N)/(K_safe - Kcrit), 0,1) if N < K_safe and enabled else 0
    """
    if not enabled:
        return 0.0
    try:
        K_safe = float(carrying_capacity) * float(relief_ratio)
        Kcrit = float(critical_pop)
        if K_safe <= Kcrit:
            return 0.0
        if N >= K_safe:
            return 0.0
        v = (K_safe - float(N)) / (K_safe - Kcrit)
        return max(0.0, min(1.0, v))
    except Exception:
        return 0.0


def tier_for_eta(eta: float, N: int, critical_pop: int, sex_extinct: bool = False, can_genesis: bool = True) -> int:
    """Tier: 0 none, 1 relief (eta>0), 2 emergency (eta>0.3), 3 genesis (N<=Kcrit or sex_extinct, max 1 miracle)."""
    if (N <= critical_pop or sex_extinct) and can_genesis:
        return 3
    if eta > 0.3:
        # Use 0.3 as Tier2 threshold per spec (morph mercy)
        # Tier2 is eta>0 but we distinguish by eta magnitude
        # For now: eta>0.5 -> Tier2, eta>0 -> Tier1, but spec says Tier2 when eta>0 and N<Ksafe
        # We'll map: 0<eta<=0.3 =>1, 0.3<eta<1 =>2, N<=Kcrit =>3
        return 2
    if eta > 0:
        return 1
    return 0


def scales_for_eta(eta: float) -> Dict[str, float]:
    """Tier1/2 scaling factors for eta."""
    return {
        "growth_eff": 1.0 + 2.5 * eta,
        "decay_eff": 1.0 - 0.4 * eta,
        "mate_energy_eff": 1.0 - 0.5 * eta,
        "mate_radius_eff": 1.0 + 1.0 * eta,
        "chill_drain_eff": 1.0 - eta,
        "sigma_eff": 1.0 + 1.5 * eta,
    }


class SafeguardEngine:
    """Homeostatic engine — holds counters, called at 1 Hz from Simulation.step()."""

    def __init__(self, config):
        self.config = config
        self.miracles = 0
        self.last_eta = 0.0
        self.last_tier = 0
        self.last_N = 0

    def update(self, N: int, tick: int, sex_extinct: bool = False) -> Tuple[float, int, Dict[str, float]]:
        cc = int(getattr(self.config, "effective_carrying_capacity", getattr(self.config, "carrying_capacity", 350)))
        relief = float(getattr(self.config, "safeguard_relief_ratio", 0.30))
        kcrit = int(getattr(self.config, "safeguard_critical_pop", 12))
        max_miracles = int(getattr(self.config, "safeguard_max_miracles", 1))
        enabled = bool(getattr(self.config, "safeguard_enabled", True))
        eta = compute_eta(N, cc, relief, kcrit, enabled)
        can_genesis = (self.miracles < max_miracles)
        tier = tier_for_eta(eta, N, kcrit, sex_extinct=sex_extinct, can_genesis=can_genesis)
        scales = scales_for_eta(eta)
        self.last_eta = eta
        self.last_tier = tier
        self.last_N = N
        return eta, tier, scales

    def should_genesis(self, N: int, sex_extinct: bool = False) -> bool:
        kcrit = int(getattr(self.config, "safeguard_critical_pop", 12))
        max_miracles = int(getattr(self.config, "safeguard_max_miracles", 1))
        enabled = bool(getattr(self.config, "safeguard_enabled", True))
        return enabled and (self.miracles < max_miracles) and (N <= kcrit or sex_extinct)

    def mercy_active(self, eta: float) -> bool:
        mercy = bool(getattr(self.config, "safeguard_morph_mercy", True))
        return mercy and eta > 0.3

    def genesis_batch_size(self) -> int:
        return int(getattr(self.config, "safeguard_genesis_batch", 6))
