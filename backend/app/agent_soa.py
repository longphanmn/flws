"""Structure of Arrays substrate — BA Step 1.2

Contiguous numpy arrays for vectorized batch execution. Falls back to
python lists when numpy is not installed.
"""

from __future__ import annotations

from typing import Optional

try:
    import numpy as np  # type: ignore

    HAS_NUMPY = True
except Exception:  # pragma: no cover
    np = None  # type: ignore
    HAS_NUMPY = False


class AgentSoA:
    """SoA storage for BA neural agents.

    Attributes are numpy arrays when available, else python lists.
    Spec KMAX 24 (new) — was 64 for ultra-circles 32/48/64.
    """

    # Morphology KMAX 24 per new spec (was 64)
    KMAX = 24

    def __init__(self, capacity: int, genome_size: int = 295):
        self.capacity = int(capacity)
        self.genome_size = int(genome_size)
        self.N = 0  # active count
        if HAS_NUMPY:
            self.pos = np.zeros((capacity, 2), dtype=np.float64)
            self.vel = np.zeros((capacity, 2), dtype=np.float64)
            self.angle = np.zeros((capacity,), dtype=np.float64)
            # stats: [energy, max_energy, health, chill]
            self.stats = np.zeros((capacity, 4), dtype=np.float64)
            self.hidden_state = np.zeros((capacity, 1), dtype=np.float64)
            self.genomes = np.zeros((capacity, genome_size), dtype=np.float64)
            self.active_mask = np.zeros((capacity,), dtype=np.bool_)
            self.ids = np.zeros((capacity,), dtype=np.int32) - 1
            # BC morphology buffers
            self.morph_radii = np.ones((capacity, self.KMAX), dtype=np.float64)
            self.morph_angles = np.zeros((capacity, self.KMAX), dtype=np.float64)
            # regular K=4 default for first 4 verts, rest uniform
            for k in range(self.KMAX):
                if k < 4:
                    self.morph_angles[:, k] = 2 * np.pi * k / 4
                else:
                    self.morph_angles[:, k] = 2 * np.pi * k / self.KMAX
            self.morph_k = np.full((capacity,), 4, dtype=np.int32)
            self.morph_k = np.clip(self.morph_k, 3, 24)  # clamp per spec
            self.morph_traits = np.zeros((capacity, 6), dtype=np.float64)  # A,P,Izz,theta_min,asym,Dmult
            # new spec name physical_traits (alias for backward compat)
            self.physical_traits = self.morph_traits  # alias, same buffer; slot names per spec
            self.reproduction_role = np.zeros((capacity,), dtype=np.int8)
        else:
            self.pos = [[0.0, 0.0] for _ in range(capacity)]
            self.vel = [[0.0, 0.0] for _ in range(capacity)]
            self.angle = [0.0] * capacity
            self.stats = [[0.0, 0.0, 0.0, 0.0] for _ in range(capacity)]
            self.hidden_state = [[0.0] for _ in range(capacity)]
            self.genomes = [[0.0] * genome_size for _ in range(capacity)]
            self.active_mask = [False] * capacity
            self.ids = [-1] * capacity
            import math as _math
            self.morph_radii = [[1.0]*self.KMAX for _ in range(capacity)]
            # regular K=4 for first 4
            self.morph_angles = [[(2*_math.pi*k/4 if k<4 else 2*_math.pi*k/self.KMAX) for k in range(self.KMAX)] for _ in range(capacity)]
            self.morph_k = [4]*capacity
            self.morph_traits = [[0.0]*6 for _ in range(capacity)]
            self.physical_traits = self.morph_traits  # alias
            self.reproduction_role = [0]*capacity

        # pre-allocated buffers for Step 5.2
        if HAS_NUMPY:
            self.inputs_buf = np.zeros((capacity, 16), dtype=np.float64)
            self.outputs_buf = np.zeros((capacity, 7), dtype=np.float64)
            self.hidden_buf = np.zeros((capacity, 1), dtype=np.float64)
        else:
            self.inputs_buf = [[0.0]*16 for _ in range(capacity)]
            self.outputs_buf = [[0.0]*7 for _ in range(capacity)]
            self.hidden_buf = [[0.0] for _ in range(capacity)]

    def add_agent(self, eid: int, x: float, y: float, angle: float = 0.0, energy: float = 80.0, max_energy: float = 100.0, health: float = 100.0, chill: float = 0.0, genome=None, morph_radii=None, morph_angles=None, morph_k: int | None = None, caste: str | None = None, sides: int | None = None) -> int:
        idx = self.N
        if idx >= self.capacity:
            raise RuntimeError("AgentSoA capacity exceeded")
        # Determine fallback K from caste / sides if morph_k is omitted
        _caste_k_map = {"Woman": 3, "Soldier": 3, "Artisan": 3, "Gentleman": 4, "Professional": 5, "Noble": 8, "Priest": 24}
        if morph_k is not None:
            effective_k = int(max(3, min(24, int(morph_k))))
        elif caste and caste in _caste_k_map:
            effective_k = _caste_k_map[caste]
        elif sides is not None:
            effective_k = 3 if sides <= 3 else int(max(3, min(24, int(sides))))
        else:
            effective_k = 4

        if HAS_NUMPY:
            self.pos[idx, 0] = x
            self.pos[idx, 1] = y
            self.angle[idx] = angle
            self.stats[idx, 0] = energy
            self.stats[idx, 1] = max_energy
            self.stats[idx, 2] = health
            self.stats[idx, 3] = chill
            self.hidden_state[idx, 0] = 0.0
            if genome is not None:
                self.genomes[idx] = genome
            self.active_mask[idx] = True
            self.ids[idx] = int(eid)
            # BC morph — init or copy
            if morph_radii is not None:
                self.morph_radii[idx, :len(morph_radii)] = morph_radii
            elif caste == "Soldier":
                self.morph_radii[idx, :3] = [1.5, 0.8, 0.8]
                self.morph_radii[idx, 3:] = 1.0
            elif caste == "Woman":
                self.morph_radii[idx, :3] = [1.8, 0.2, 0.2]
                self.morph_radii[idx, 3:] = 1.0
            else:
                self.morph_radii[idx, :] = 1.0

            if morph_angles is not None:
                self.morph_angles[idx, :len(morph_angles)] = morph_angles
            elif caste == "Soldier":
                self.morph_angles[idx, :3] = [0.0, 2.4, 3.88]
                for ki in range(3, self.KMAX):
                    self.morph_angles[idx, ki] = 2 * 3.141592653589793 * ki / self.KMAX
            elif caste == "Woman":
                self.morph_angles[idx, :3] = [0.0, 3.141592653589793 - 0.08, 3.141592653589793 + 0.08]
                for ki in range(3, self.KMAX):
                    self.morph_angles[idx, ki] = 2 * 3.141592653589793 * ki / self.KMAX
            else:
                # regular polygon angles for effective_k
                for ki in range(effective_k):
                    self.morph_angles[idx, ki] = 2 * 3.141592653589793 * ki / effective_k
                for ki in range(effective_k, self.KMAX):
                    self.morph_angles[idx, ki] = 2 * 3.141592653589793 * ki / self.KMAX
            self.morph_k[idx] = effective_k
            self.morph_traits[idx, :] = 0.0
            # physical_traits alias already 0
            self.reproduction_role[idx] = 0
        else:
            self.pos[idx] = [float(x), float(y)]
            self.vel[idx] = [0.0, 0.0]
            self.angle[idx] = float(angle)
            self.stats[idx] = [float(energy), float(max_energy), float(health), float(chill)]
            self.hidden_state[idx] = [0.0]
            if genome is not None:
                self.genomes[idx] = list(genome)
            self.active_mask[idx] = True
            self.ids[idx] = int(eid)
            if morph_radii is not None:
                for i, v in enumerate(morph_radii):
                    if i < self.KMAX:
                        self.morph_radii[idx][i] = float(v)
            elif caste == "Soldier":
                self.morph_radii[idx][0] = 1.5
                self.morph_radii[idx][1] = 0.8
                self.morph_radii[idx][2] = 0.8
                for i in range(3, self.KMAX):
                    self.morph_radii[idx][i] = 1.0
            elif caste == "Woman":
                self.morph_radii[idx][0] = 1.8
                self.morph_radii[idx][1] = 0.2
                self.morph_radii[idx][2] = 0.2
                for i in range(3, self.KMAX):
                    self.morph_radii[idx][i] = 1.0
            else:
                for i in range(self.KMAX):
                    self.morph_radii[idx][i] = 1.0

            import math as _mm
            if morph_angles is not None:
                for i, v in enumerate(morph_angles):
                    if i < self.KMAX:
                        self.morph_angles[idx][i] = float(v)
            elif caste == "Soldier":
                self.morph_angles[idx][0] = 0.0
                self.morph_angles[idx][1] = 2.4
                self.morph_angles[idx][2] = 3.88
                for ki in range(3, self.KMAX):
                    self.morph_angles[idx][ki] = 2 * _mm.pi * ki / self.KMAX
            elif caste == "Woman":
                self.morph_angles[idx][0] = 0.0
                self.morph_angles[idx][1] = _mm.pi - 0.08
                self.morph_angles[idx][2] = _mm.pi + 0.08
                for ki in range(3, self.KMAX):
                    self.morph_angles[idx][ki] = 2 * _mm.pi * ki / self.KMAX
            else:
                for ki in range(self.KMAX):
                    if ki < effective_k:
                        self.morph_angles[idx][ki] = 2 * _mm.pi * ki / effective_k
                    else:
                        self.morph_angles[idx][ki] = 2 * _mm.pi * ki / self.KMAX
            self.morph_k[idx] = effective_k
            self.morph_traits[idx] = [0.0]*6
            # physical_traits alias same
            self.reproduction_role[idx] = 0
        self.N += 1
        return idx

    def ensure_capacity(self, min_capacity: int) -> None:
        """BJ-1: grow pre-allocated buffers only when needed (doubling).

        No-op when current capacity already fits. Preserves all N active slots.
        """
        if int(min_capacity) <= self.capacity:
            return
        new_cap = max(int(min_capacity), self.capacity * 2 if self.capacity else 16)
        if HAS_NUMPY:
            import numpy as _np  # type: ignore

            def _grow(arr, shape_fn):
                nxt = _np.zeros(shape_fn(new_cap), dtype=arr.dtype)
                nxt[: self.N] = arr[: self.N]
                return nxt

            self.pos = _grow(self.pos, lambda c: (c, 2))
            self.vel = _grow(self.vel, lambda c: (c, 2))
            self.angle = _grow(self.angle, lambda c: (c,))
            self.stats = _grow(self.stats, lambda c: (c, 4))
            self.hidden_state = _grow(self.hidden_state, lambda c: (c, 1))
            self.genomes = _grow(self.genomes, lambda c: (c, self.genome_size))
            nxt_mask = _np.zeros((new_cap,), dtype=_np.bool_)
            nxt_mask[: self.N] = self.active_mask[: self.N]
            self.active_mask = nxt_mask
            nxt_ids = _np.zeros((new_cap,), dtype=_np.int32) - 1
            nxt_ids[: self.N] = self.ids[: self.N]
            self.ids = nxt_ids
            self.morph_radii = _grow(self.morph_radii, lambda c: (c, self.KMAX))
            self.morph_angles = _grow(self.morph_angles, lambda c: (c, self.KMAX))
            nxt_k = _np.full((new_cap,), 4, dtype=_np.int32)
            nxt_k[: self.N] = self.morph_k[: self.N]
            self.morph_k = nxt_k
            self.morph_traits = _grow(self.morph_traits, lambda c: (c, 6))
            self.physical_traits = self.morph_traits  # keep alias on same buffer
            nxt_role = _np.zeros((new_cap,), dtype=_np.int8)
            nxt_role[: self.N] = self.reproduction_role[: self.N]
            self.reproduction_role = nxt_role
            self.inputs_buf = _grow(self.inputs_buf, lambda c: (c, 16))
            self.outputs_buf = _grow(self.outputs_buf, lambda c: (c, 7))
            self.hidden_buf = _grow(self.hidden_buf, lambda c: (c, 1))
        else:
            _ext = new_cap - self.capacity
            self.pos.extend([[0.0, 0.0] for _ in range(_ext)])
            self.vel.extend([[0.0, 0.0] for _ in range(_ext)])
            self.angle.extend([0.0] * _ext)
            self.stats.extend([[0.0, 0.0, 0.0, 0.0] for _ in range(_ext)])
            self.hidden_state.extend([[0.0] for _ in range(_ext)])
            self.genomes.extend([[0.0] * self.genome_size for _ in range(_ext)])
            self.active_mask.extend([False] * _ext)
            self.ids.extend([-1] * _ext)
            import math as _math

            self.morph_radii.extend([[1.0] * self.KMAX for _ in range(_ext)])
            self.morph_angles.extend(
                [[(2 * _math.pi * k / self.KMAX) for k in range(self.KMAX)] for _ in range(_ext)]
            )
            self.morph_k.extend([4] * _ext)
            self.morph_traits.extend([[0.0] * 6 for _ in range(_ext)])
            self.physical_traits = self.morph_traits
            self.reproduction_role.extend([0] * _ext)
            self.inputs_buf.extend([[0.0] * 16 for _ in range(_ext)])
            self.outputs_buf.extend([[0.0] * 7 for _ in range(_ext)])
            self.hidden_buf.extend([[0.0] for _ in range(_ext)])
        self.capacity = new_cap

    def sync_slot(self, idx: int, x: float, y: float, angle: float, energy: float, health: float) -> None:
        """BJ-1: in-place per-tick shadow sync without reallocation."""
        if HAS_NUMPY:
            self.pos[idx, 0] = x
            self.pos[idx, 1] = y
            self.angle[idx] = angle
            self.stats[idx, 0] = energy
            self.stats[idx, 2] = health
        else:
            self.pos[idx][0] = float(x)
            self.pos[idx][1] = float(y)
            self.angle[idx] = float(angle)
            self.stats[idx][0] = float(energy)
            self.stats[idx][2] = float(health)

    def remove_at(self, idx: int) -> None:
        last = self.N - 1
        if idx < 0 or idx >= self.N:
            return
        if HAS_NUMPY:
            if idx != last:
                self.pos[idx] = self.pos[last].copy()
                self.vel[idx] = self.vel[last].copy()
                self.angle[idx] = self.angle[last]
                self.stats[idx] = self.stats[last].copy()
                self.hidden_state[idx] = self.hidden_state[last].copy()
                self.genomes[idx] = self.genomes[last].copy()
                self.active_mask[idx] = self.active_mask[last]
                self.ids[idx] = self.ids[last]
                self.morph_radii[idx] = self.morph_radii[last].copy()
                self.morph_angles[idx] = self.morph_angles[last].copy()
                self.morph_k[idx] = self.morph_k[last]
                self.morph_traits[idx] = self.morph_traits[last].copy()
                self.reproduction_role[idx] = self.reproduction_role[last]
            self.active_mask[last] = False
            self.ids[last] = -1
        else:
            if idx != last:
                self.pos[idx] = self.pos[last][:]
                self.vel[idx] = self.vel[last][:]
                self.angle[idx] = self.angle[last]
                self.stats[idx] = self.stats[last][:]
                self.hidden_state[idx] = self.hidden_state[last][:]
                self.genomes[idx] = self.genomes[last][:]
                self.active_mask[idx] = self.active_mask[last]
                self.ids[idx] = self.ids[last]
                self.morph_radii[idx] = self.morph_radii[last][:]
                self.morph_angles[idx] = self.morph_angles[last][:]
                self.morph_k[idx] = self.morph_k[last]
                self.morph_traits[idx] = self.morph_traits[last][:]
                self.reproduction_role[idx] = self.reproduction_role[last]
            self.active_mask[last] = False
            self.ids[last] = -1
        self.N -= 1

    def active_indices(self):
        if HAS_NUMPY:
            return np.where(self.active_mask[: self.N])[0]
        return [i for i in range(self.N) if self.active_mask[i]]

    def to_dict(self, idx: int) -> dict:
        if HAS_NUMPY:
            return dict(
                id=int(self.ids[idx]),
                x=float(self.pos[idx, 0]),
                y=float(self.pos[idx, 1]),
                angle=float(self.angle[idx]),
                energy=float(self.stats[idx, 0]),
                max_energy=float(self.stats[idx, 1]),
                health=float(self.stats[idx, 2]),
                chill=float(self.stats[idx, 3]),
                hidden=float(self.hidden_state[idx, 0]),
                morph_k=int(self.morph_k[idx]),
                morph_traits=[float(v) for v in self.morph_traits[idx]],
                reproduction_role=int(self.reproduction_role[idx]),
            )
        return dict(
            id=int(self.ids[idx]),
            x=float(self.pos[idx][0]),
            y=float(self.pos[idx][1]),
            angle=float(self.angle[idx]),
            energy=float(self.stats[idx][0]),
            max_energy=float(self.stats[idx][1]),
            health=float(self.stats[idx][2]),
            chill=float(self.stats[idx][3]),
            hidden=float(self.hidden_state[idx][0]),
            morph_k=int(self.morph_k[idx]),
            morph_traits=[float(v) for v in self.morph_traits[idx]],
            reproduction_role=int(self.reproduction_role[idx]),
        )
