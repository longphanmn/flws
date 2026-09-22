"""Deterministic fixed-tick simulation of Flatland."""

import gc
import math
import operator
import os
import random
import time
from collections import deque
from functools import lru_cache
from typing import Any, Callable, cast

_IS_TEST = bool(os.getenv("PYTEST_CURRENT_TEST") or os.getenv("FLATWORLD_TEST") or os.getenv("FLATWORLD_SOFT_CAP_ENABLED") == "false")

# N150: disable automatic GC during tick — manual collect every 200 ticks
# to avoid 1s stop-the-world pauses at 1300c
gc.disable()

from ..config import Config
from ..entities import (
    DEFAULT_RADIUS,
    PRIEST_SIDES,
    YIELD_RANK,
    Corpse,
    Creature,
    Entity,
    Food,
    House,
    RADIUS_BY_CASTE,
    caste_name,
    traits_for,
)
from ..protocol import EntityState, HistoryEvent, StateMessage
from ..world import World, segments_intersect

# AY: native hot-path & parallel domain decomposition (optional, deterministic fallback)
try:
    from .. import native_core as _native_core  # type: ignore
except Exception:
    _native_core = None  # type: ignore
try:
    from .. import parallel as _parallel  # type: ignore
except Exception:
    _parallel = None  # type: ignore

# BA: micro-neural engine — always on (295 fixed)
try:
    from .. import agent_soa as _agent_soa  # type: ignore
    from .. import neural_engine as _neural_engine  # type: ignore
    from .. import agent_pipeline as _agent_pipeline  # type: ignore
    from .. import spatial_grid as _spatial_grid  # type: ignore
    from .. import evolution as _evolution  # type: ignore
except Exception:  # pragma: no cover
    _agent_soa = None  # type: ignore
    _neural_engine = None  # type: ignore
    _agent_pipeline = None  # type: ignore
    _spatial_grid = None  # type: ignore
    _evolution = None  # type: ignore

# BC: morphological physics — optional, disabled keeps AZ hash
# New spec KMAX 24 canonical is morphology_engine.py; keep morphology shim for compat
try:
    from .. import morphology_engine as _morphology  # type: ignore
    from .. import evolution_manager as _evo_mgr  # type: ignore
    from .. import safeguard_engine as _safeguard_engine  # type: ignore
except Exception:
    try:
        from .. import morphology as _morphology  # type: ignore
        from .. import evolution_manager as _evo_mgr  # type: ignore
        from .. import safeguard_engine as _safeguard_engine  # type: ignore
    except Exception:  # pragma: no cover
        _morphology = None  # type: ignore
        _evo_mgr = None  # type: ignore
        _safeguard_engine = None  # type: ignore


from .constants import *  # noqa: F403
from .constants import _clan_sig, _season_food_mult, _smooth_age_mult, _smooth_season_cap_mult  # noqa: F401
from .ecology import EcologyMixin
from .environment import EnvironmentMixin
from .settlement import SettlementMixin
from .lifecycle import LifecycleMixin
from .creature_update import CreatureUpdateMixin
from .society import SocietyMixin
from .theology import TheologyMixin
from .serialization import SerializationMixin


def _morph_sat_pair(sim, soa, idx: int, j: int) -> None:
    """BJ-5: shared SAT narrowphase for one SoA index pair (broadphase-agnostic).

    Moved verbatim from `_update_morph_collisions` so the OpenMP sweep
    broadphase and the legacy spatial-hash broadphase share one narrowphase.
    """
    import math as _m

    try:
        eid = int(soa.ids[idx]) if hasattr(soa.ids, "__getitem__") else -1
        ent = sim.world.entities.get(eid)
        other_id = int(soa.ids[j]) if hasattr(soa.ids, "__getitem__") else -1
        other = sim.world.entities.get(other_id)
        if ent is None or other is None or not isinstance(ent, Creature) or not isinstance(other, Creature):
            return
        if hasattr(soa.morph_radii, "shape"):
            kr = int(soa.morph_k[idx]); ko = int(soa.morph_k[j])
            if kr < 3 or ko < 3:
                return
            rr = soa.morph_radii[idx, :kr]; pa = soa.morph_angles[idx, :kr]
            ro = soa.morph_radii[j, :ko]; po = soa.morph_angles[j, :ko]
            import numpy as _np  # type: ignore
            try:
                asym_a = float(soa.physical_traits[idx, 4]) if hasattr(soa.physical_traits, "shape") else float(soa.physical_traits[idx][4])  # type: ignore
                asym_b = float(soa.physical_traits[j, 4]) if hasattr(soa.physical_traits, "shape") else float(soa.physical_traits[j][4])  # type: ignore
            except Exception:
                asym_a = asym_b = 1.0
            use_circle_a = (kr >= 24 and asym_a < 0.05)
            use_circle_b = (ko >= 24 and asym_b < 0.05)
            xa = (rr * _np.cos(pa) + ent.x).tolist() if hasattr(rr, "tolist") else [rr[i]*_m.cos(pa[i])+ent.x for i in range(kr)]
            ya = (rr * _np.sin(pa) + ent.y).tolist() if hasattr(rr, "tolist") else [rr[i]*_m.sin(pa[i])+ent.y for i in range(kr)]
            xb = (ro * _np.cos(po) + other.x).tolist() if hasattr(ro, "tolist") else [ro[i]*_m.cos(po[i])+other.x for i in range(ko)]
            yb = (ro * _np.sin(po) + other.y).tolist() if hasattr(ro, "tolist") else [ro[i]*_m.sin(po[i])+other.y for i in range(ko)]
            if use_circle_a or use_circle_b:
                try:
                    if use_circle_a:
                        cx, cy = ent.x, ent.y
                        crad = float(soa.physical_traits[idx, 0] / soa.physical_traits[idx, 1] * 2) if hasattr(soa.physical_traits, "shape") else 1.0
                        crad = float(_np.mean(rr)) if hasattr(rr, "mean") else sum(rr)/len(rr) if rr else 1.0
                        if use_circle_a and use_circle_b:
                            dx = ent.x - other.x
                            dy = ent.y - other.y
                            dx, dy = sim.world.delta(ent.x, ent.y, other.x, other.y)
                            dist2 = dx*dx + dy*dy
                            overlap = dist2 <= (crad + (float(_np.mean(ro)) if hasattr(ro, "mean") else 1.0))**2
                        else:
                            overlap = _morphology.sat_overlap(xa, ya, xb, yb)
                    else:
                        overlap = _morphology.sat_overlap(xa, ya, xb, yb)
                except Exception:
                    overlap = _morphology.sat_overlap(xa, ya, xb, yb)
            else:
                overlap = _morphology.sat_overlap(xa, ya, xb, yb)
        else:
            kr = int(soa.morph_k[idx]); ko = int(soa.morph_k[j])
            if kr < 3 or ko < 3:
                return
            rr = soa.morph_radii[idx]; pa = soa.morph_angles[idx]
            ro = soa.morph_radii[j]; po = soa.morph_angles[j]
            xa = [rr[i]*_m.cos(pa[i])+ent.x for i in range(kr)]
            ya = [rr[i]*_m.sin(pa[i])+ent.y for i in range(kr)]
            xb = [ro[i]*_m.cos(po[i])+other.x for i in range(ko)]
            yb = [ro[i]*_m.sin(po[i])+other.y for i in range(ko)]
            try:
                asym_a = float(soa.physical_traits[idx][4])  # type: ignore
                asym_b = float(soa.physical_traits[j][4])  # type: ignore
            except Exception:
                asym_a = asym_b = 1.0
            if (kr >= 24 and asym_a < 0.05) and (ko >= 24 and asym_b < 0.05):
                dx, dy = sim.world.delta(ent.x, ent.y, other.x, other.y)
                crad = sum(rr)/len(rr) if rr else 1.0
                orad = sum(ro)/len(ro) if ro else 1.0
                overlap = (dx*dx + dy*dy) <= (crad + orad)**2
            elif kr >= 24 and asym_a < 0.05 or ko >= 24 and asym_b < 0.05:
                overlap = _morphology.sat_overlap(xa, ya, xb, yb)
            else:
                overlap = _morphology.sat_overlap(xa, ya, xb, yb)
        if overlap:
            if (ent.clan_id and ent.clan_id == other.clan_id) or getattr(ent, "sleeping", False) or getattr(other, "sleeping", False) or ent.shape == "line" or other.shape == "line":
                return
            try:
                da = float(soa.morph_traits[idx, 5]) if hasattr(soa.morph_traits, "shape") else float(soa.morph_traits[idx][5])
                db = float(soa.morph_traits[j, 5]) if hasattr(soa.morph_traits, "shape") else float(soa.morph_traits[j][5])
            except Exception:
                da = db = 0.0
            dmg = max(da, db) * sim.config.attack_damage * 0.2
            if dmg > 0:
                tgt = other if other.health < ent.health else ent
                tgt.health -= dmg
                if tgt.health <= 0:
                    sim._kill(tgt, "collision")
    except Exception:
        return


class Simulation(SerializationMixin, EcologyMixin, EnvironmentMixin, SettlementMixin, TheologyMixin, SocietyMixin, LifecycleMixin, CreatureUpdateMixin):
    def __init__(
        self,
        config: Config | None = None,
        history: deque[HistoryEvent] | None = None,
    ):
        self.config = config or Config()
        self.world = World(self.config)
        self.rng = random.Random(self.config.seed)
        self.tick = 0
        self.deaths = 0
        self.births = 0
        self._births = 0
        # Chronicle of the world; survives resets when handed back in.
        self.history: deque[HistoryEvent] = history or deque(maxlen=self.config.history_max)
        # Optional sink for durable storage (set by the app layer); must never
        # touch the rng — determinism is unaffected by observers.
        self.on_event: Callable[[HistoryEvent], None] | None = None
        self._eaten: set[int] = set()
        self._beds: dict[int, int] = {}  # house id -> occupants granted this tick
        self._events_this_tick: list[dict] = []  # pre-dumped dicts (populated by _emit)
        # T: per-tick caches
        self._cached_creatures: list[Creature] = []
        self._cached_creatures_sorted: list[Creature] = []  # sorted by id, built in _refresh_cache
        self._cached_foods: list = []    # Food entities this tick
        self._cached_houses: list = []   # non-ruin House entities this tick (sorted by id)
        self._cached_corpses: list = []  # Corpse entities this tick
        self._clan_members: dict[int, list[Creature]] = {}
        self._death_counts: dict[str, int] = {}
        # AA: deterministic cosmetic identity (name/glyph/jitter) per creature,
        # computed once — pure function of (id, seed, generation).
        self._identity_cache: dict[tuple[int, int], tuple[str, str, float, float, float]] = {}
        self.disease_id = 0
        self.weather = "clear"
        self.clans: dict[int, dict] = {}  # id -> {name, founder_id, born_tick, color}
        self._next_clan_id = 1
        self.relations: dict[tuple[int, int], int] = {}  # clan pair -> -100..100
        self._relation_zones: dict[tuple[int, int], int] = {}  # last seen zone
        self.coalitions: dict[int, dict] = {}  # §AB: id -> {name, leader_clan, members}
        self._next_coalition_id = 1
        self._clan_coalition: dict[int, int] = {}  # clan id -> coalition id
        # §AB: declared wars — pair -> tick of the last declaration. One active
        # feud per pair; prevents leaders re-declaring war on the same clan
        # while the feud is already open (or freshly concluded).
        self._declared_wars: dict[tuple[int, int], int] = {}
        self._eaters_this_tick: list[int] = []
        # §AP theology: sacred truces (synod/epiphany) still all strife while > 0
        self.truce_ticks = 0
        self._last_season: str | None = None  # season-change detector for miracles
        self._last_law_food_count: int = self.config.food_count
        self.fertile: list[dict] = []  # {x,y,r} — food prefers these grounds
        self.rocks: list[dict] = []  # {x,y,r} — solid circles that block movement
        self.rivers: list[dict] = []  # §AQ PH-3: horizontal channels {cy,hw,base_hw,dir,water,flood_ticks,silt_ticks}
        self.bridges: list[dict] = []  # §AQ PH-3: planks {x,cy,hw,hp}
        self.dams: list[dict] = []  # §AQ PH-3: stone dams {x,cy,hp}
        # §AQ PH-4: the height of the land + the paths feet pack into roads
        self._elev_cols = max(1, math.ceil(self.config.width / ELEV_CELL))
        self._elev_rows = max(1, math.ceil(self.config.height / ELEV_CELL))
        self.elev_grid: list[float] = [0.5] * (self._elev_cols * self._elev_rows)  # 0..1
        # §AQ PH-8/9/10: quakes, bolts, shimmer fronts & hidden zones
        self.pending_quake: dict | None = None  # {x,y,mag,hit_tick,warned}
        self.lightning: list[dict] = []  # {x,y,ttl} visible bolts
        self.law_wave: dict | None = None  # {born_tick}
        self.anomalies: list[dict] = []  # {x,y,kind,discovered}
        self._totem_mult_cache: dict[int, float] = {}
        self._clan_deaths: dict[int, int] = {}
        self._clan_war_wins: dict[int, int] = {}
        self._clan_war_losses: dict[int, int] = {}
        self.signals: list[dict] = []  # §Q: {x,y,kind,sender,clan_id,ttl}
        self.fires: list[dict] = []  # §S wildfire: {x,y,r,ttl}
        self.campfires: list[dict] = []  # §AO E: field campfires {x,y,day}
        # §AQ PH-1: coarse ambient heat field (row-major, top-left origin)
        self._temp_cols = max(1, math.ceil(self.config.width / TEMP_CELL))
        self._temp_rows = max(1, math.ceil(self.config.height / TEMP_CELL))
        self._temp_cols_inv_w = self._temp_cols / max(1.0, float(self.config.width))
        self._temp_rows_inv_h = self._temp_rows / max(1.0, float(self.config.height))
        base0 = SEASON_BASE_TEMP[SEASONS[0]]
        self.temperature_grid = [base0] * (self._temp_cols * self._temp_rows)
        # §AM: living soil — a fertility grid the harvests draw upon
        self._soil_cols = self._temp_cols
        self._soil_rows = self._temp_rows
        self.soil_grid = [1.0] * (self._soil_cols * self._soil_rows)
        # §AQ PH-4: traffic over the same coarse cells — feet pack the earth
        self.traffic_grid: list[float] = [0.0] * (self._temp_cols * self._temp_rows)
        self._elev_c_buf = None  # type: ignore
        self._elev_use_native: bool | None = None  # AZ 4a: hoist FFI guard
        self.wind_angle = (self.config.seed % 6283) / 1000.0  # §AQ PH-2, rng-free init
        self.wind_speed = WIND_CALM_SPEED
        # §AU O-1: wind direction trig computed once per tick, not per query
        self._wind_cached_for = None
        self._cos_wind = 1.0
        self._sin_wind = 0.0
        self._sync_wind_cache()
        # §AM agriculture: tilled plots per clan + feast pacing
        self.farm_plots: dict[int, list[dict]] = {}  # clan id -> [{x,y,irrigated}]
        self._banquet_last: dict[int, int] = {}  # clan id -> tick of last feast
        self._last_hospitality_tick = -10 * HOSPITALITY_GAP
        # §AN diplomacy: boundary stones, markets & omen bookkeeping
        self.boundary_stones: list[dict] = []  # {x,y,clan_id}
        self.markets: dict[tuple[int, int], dict] = {}  # pair -> {x,y,born_tick}
        self._stone_chime_last: dict[int, int] = {}  # clan id -> last chime tick
        self._omen_season: str | None = None
        self._caravan_last: dict[tuple[int, int], int] = {}  # pair -> last caravan
        # AJ: Delta compression tracking (Phase 1)
        self._last_broadcast_state: dict[int, tuple] = {}
        self._last_broadcast_entities: set[int] = set()
        # M-4: contiguous native buffers for OpenMP batch (zero-copy, pre-allocated)
        self._c_creatures_buf = None  # type: ignore
        self._c_entities_buf = None  # type: ignore
        self._c_out_buf = None  # type: ignore
        # BA: micro-neural SoA substrate (opt-in, gated by nn_enabled)
        self._soa: object | None = None  # AgentSoA when enabled
        self._nn_grid: object | None = None  # SpatialHashGrid when enabled
        self._nn_tick: int = 0
        # BJ-6: per-subsystem tick timing (last-tick ms + rolling avg for /healthz + /api/perf/telemetry)
        self._phase_ms: dict[str, float] = {}
        self._phase_totals: dict[str, float] = {}
        self._phase_counts: dict[str, int] = {}
        # BD Analytics — zero-alloc telemetry engine
        try:
            from .. import analytics as _bd_analytics  # type: ignore
            self._analytics = _bd_analytics.attach_to_sim(self)  # type: ignore[attr-defined]
        except Exception:
            self._analytics = None  # type: ignore[attr-defined]
        # Phase 5 Safeguards — homeostatic engine (1 Hz)
        try:
            if _safeguard_engine is not None:
                self._safeguard = _safeguard_engine.SafeguardEngine(self.config)  # type: ignore[attr-defined]
                self._safeguard_eta = 0.0  # type: ignore[attr-defined]
                self._safeguard_tier = 0  # type: ignore[attr-defined]
                self._safeguard_scales = {}  # type: ignore[attr-defined]
            else:
                self._safeguard = None  # type: ignore[attr-defined]
        except Exception:
            self._safeguard = None  # type: ignore[attr-defined]
        # Phase 4 Density Damping — homeostatic soft-cap engine
        try:
            from .. import density_damping as _density_damping  # type: ignore
            self._density_engine = _density_damping.DensityDampingEngine(self.config)  # type: ignore[attr-defined]
            self._density_xi = 0.0  # type: ignore[attr-defined]
            self._density_scales = {}  # type: ignore[attr-defined]
        except Exception:
            self._density_engine = None  # type: ignore[attr-defined]
            self._density_xi = 0.0  # type: ignore[attr-defined]
            self._density_scales = {}  # type: ignore[attr-defined]
        # BH-1/4/9 caches: pending morph, NN genomes, archetypes for newborns (Creature slots forbids ad-hoc attrs)
        self._morph_cache: dict[int, tuple[list, list, int]] = {}  # id -> (r,phi,k)
        self._nn_cache: dict[int, object] = {}  # id -> genome (np array or list)
        self._archetype_cache: dict[int, str] = {}  # id -> archetype tag BH-9
        self._morph_pending: dict[int, tuple[list, list, int]] = {}  # object id -> (r,phi,k) before world id assigned
        self._nn_pending: dict[int, object] = {}  # object id -> genome pending
        self._generate_elevation()  # §AQ PH-4: the shape of the land comes first
        self._generate_rivers()  # §AQ PH-3: channels follow the slope
        self._generate_anomalies()  # §AQ PH-10: hidden zones of strange physics
        self._spawn_initial()
        self._generate_terrain()
        self._consecrate_initial_shrines()



    # ------------------------------------------------------------- the sky













    @staticmethod
    def _health_speed_mult(health: float) -> float:
        """§AT-4 H-0: wounds slow the body — a creature at 5 HP is no sprinter."""
        for threshold, mult in sorted(HEALTH_SPEED_TIERS, key=lambda t: t[0]):
            if health < threshold:
                return mult
        return 1.0

    @staticmethod
    def _health_sight_mult(health: float) -> float:
        """§AT-4 H-1: a sick body cannot see as far."""
        for threshold, mult in HEALTH_SIGHT_TIERS:
            if health < threshold:
                return mult
        return 1.0

    @staticmethod
    def _forage_mult(health: float) -> float:
        """§AT-4 H-1: weakness blunts the harvest — decline feeds on itself."""
        if health < 30.0:
            return FORAGE_MULT_WEAK
        if health < 60.0:
            return FORAGE_MULT_HURT
        return 1.0

    def _effective_fear_radius(self, c: Creature, is_night: bool = False) -> float:
        """§AR S-0: the fear threshold is a sense like any other — traits bend
        it (paranoid +4, bold −2.5) and starvation halves it: the desperate
        walk toward death chasing scented food. §AP: the Eternal Hearth keeps
        its people calm through the night."""
        r = self.config.fear_radius
        if c.trait == "paranoid":
            r += 4.0
        elif c.trait == "bold":
            r = max(2.0, r - 2.5)
        ratio = c.energy / self.config.energy_max if self.config.energy_max > 0 else 1.0
        if ratio <= self.config.starving_ratio:
            r *= 0.5
        if is_night:
            r = max(2.0, r - self._totem_stat(c, "calm"))
        # §AN: the priest's liturgy calms the panicked heart for a while
        if c.calm_ticks > 0:
            r = max(1.0, r - 2.0)
        # §AQ PH-9: a living priest's bio-electric field quiets the nerves —
        # stronger the richer the clan's faith pool runs.
        ppos = self._priest_pos_for(c.clan_id)
        if ppos is not None:
            d2p = self.world.distance_sq(c.x, c.y, ppos[0], ppos[1])
            if d2p <= PRIEST_AURA_RADIUS * PRIEST_AURA_RADIUS:
                faith = float(self.clans.get(c.clan_id, {}).get("faith", 0.0))
                calm = PRIEST_CALM * max(0.6, min(1.6, 0.7 + faith / 200.0))
                r = max(1.0, r - calm)
        return r
    def _sun_factor(self) -> float:
        """§AQ PH-0: sunlight is the world's only income — no free growth at
        night. Zero through the dark, a low arc at the edges of day, full
        strength at noon. (Winter's bite stays the season table.)"""
        tod = self._time_of_day()
        if tod <= 0.22 or tod >= 0.78:
            return 0.0
        x = (tod - 0.5) / 0.28  # −1..1 across the daylight window
        return max(0.15, 1.0 - x * x)

    def _is_torpid(self, c: Creature) -> bool:
        """§AQ PH-7: a starving body in killing cold has shut down."""
        em = self.config.energy_max
        ratio = c.energy / em if em > 0 else 1.0
        return (
            not c.is_predator
            and ratio <= TORPOR_ENERGY_RATIO
            and self.ambient_at(c.x, c.y) < HYPOTHERMIA_TEMP
        )

    @staticmethod
    def _metabolic_cost(c: Creature) -> float:
        """§AQ PH-0: upkeep scales with body complexity — a priest's aura is
        expensive, a woman's line burns hot, triangles run lean."""
        return METABOLIC_COST.get(c.caste, DEFAULT_METABOLIC_COST)

    # -------------------------------------------------- §AQ PH-1 thermodynamics





    # -------------------------------------------------- §AQ PH-3 rivers














    def _emit_boom(self, x: float, y: float) -> None:
        """§AQ PH-2: a loud event — collapse, dam burst — rolls out as a
        pressure wave every creature hears (roofs muffle, wind carries)."""
        if len(self.signals) < SIGNALS_MAX:
            self.signals.append({
                "x": round(x, 2), "y": round(y, 2),
                "kind": "boom", "sender": 0, "clan_id": None, "born_tick": self.tick, "ttl": 10,
            })


    def _update_night_watch(self) -> None:
        """§AO Phase C: sentry spearmen hold the doorway — soldiers resting
        near their own threshold poke outward at any beast circling the
        settlement after dark."""
        tod = self._time_of_day()
        if not self._is_night(tod):
            return
        w = self.world
        for c in self._get_creatures():
            if (
                c.caste != "Soldier"
                or c.equipped_item != "spear"
                or c.sleeping
                or not c.clan_id
                or (self.tick + c.id) % 3 != 0
            ):
                continue
            info = self.clans.get(c.clan_id)
            if not info:
                continue
            hid = info.get("main_house_id")
            h = w.entities.get(hid) if hid is not None else None
            if not isinstance(h, House) or h.is_ruin:
                continue
            dx, dy = self._door_pos(h)
            if w.distance_sq(c.x, c.y, dx, dy) > (SPEAR_POKE_RADIUS * 2.0) ** 2:
                continue
            # poke anything hostile circling the threshold
            for o, d2 in w.query_radius_with_dist_sq(dx, dy, SPEAR_POKE_RADIUS):
                if not isinstance(o, Creature) or o.id == c.id or o.indoors:
                    continue
                if o.id not in w.entities:
                    continue
                hostile = (
                    o.is_predator
                    or (o.clan_id == 0 and o.sides == 3)
                    or (o.clan_id and self._zone_of(
                        self.relations.get(self._relation_pair(c.clan_id, o.clan_id), 0)) == -1)
                )
                if not hostile or d2 > SPEAR_POKE_RADIUS * SPEAR_POKE_RADIUS:
                    continue
                dmg = SPEAR_POKE_DAMAGE * (1.0 + c.skills.get("combat", 0.0) / 25.0)
                o.health -= dmg
                c.emote = "combat"
                c.emote_ticks = 12
                c.skills["combat"] = c.skills.get("combat", 0.0) + 0.5
                if o.health <= 0:
                    self._kill(o, "war")
                break



    # ------------------------------------------------- §AQ PH-8/9/10





    def _priest_pos_for(self, cid: int | None) -> tuple[float, float] | None:
        """The clan's living priest, for the bio-electric calm aura (§AQ PH-9)."""
        if not cid:
            return None
        cached = getattr(self, "_priest_pos", None)
        if cached is None:
            return None
        return cached.get(cid)

    def _totem_mult(self, cid: int | None) -> float:
        """§AQ PH-9: totem resonance — same-god allied shrines nearby amplify
        the aura, rival shrines too close interfere, anomalies empower."""
        if not cid:
            return 1.0
        cached = self._totem_mult_cache.get(cid)
        if cached is not None:
            return cached
        # PERF (no logic change): flat shrine list built once per tick instead
        # of per-clan dict walks, and squared-distance compare instead of
        # hypot (d > R iff d² > R² — identical branching, deterministic).
        flat = self.__dict__.get("_totem_flat")
        if flat is None or flat[0] != self.tick:
            flat = (
                self.tick,
                [
                    (oid, self._shrine_pos(oid), (info.get("totem") if isinstance(info, dict) else None))
                    for oid, info in self.clans.items()
                ],
            )
            self.__dict__["_totem_flat"] = flat
        others = flat[1]
        mult = 1.0
        shrine = self._shrine_pos(cid)
        my_totem = self.clans.get(cid, {}).get("totem")
        if shrine is not None:
            sx, sy = shrine[0], shrine[1]
            rival_r2 = TOTEM_RIVAL_RADIUS * TOTEM_RIVAL_RADIUS
            alliance_threshold = self.config.alliance_threshold
            rivalry_threshold = self.config.rivalry_threshold
            relations = self.relations
            pair_fn = self._relation_pair
            for other_id, other_shrine, other_totem in others:
                if other_id == cid or other_shrine is None:
                    continue
                dx = sx - other_shrine[0]
                dy = sy - other_shrine[1]
                if self.config.boundary == "wrap":
                    w = self.config.width
                    h = self.config.height
                    half_w = w * 0.5
                    half_h = h * 0.5
                    if dx > half_w:
                        dx -= w
                    elif dx < -half_w:
                        dx += w
                    if dy > half_h:
                        dy -= h
                    elif dy < -half_h:
                        dy += h
                if dx * dx + dy * dy > rival_r2:
                    continue
                score = relations.get(pair_fn(cid, other_id), 0)
                if other_totem == my_totem and score >= alliance_threshold:
                    mult += TOTEM_RESONANCE_BONUS
                elif score <= rivalry_threshold:
                    mult *= TOTEM_RIVAL_DIM  # contested ground dims both
            # anomalies empower nearby shrines (known or not)
            ar2 = (ANOMALY_RADIUS + 6.0) * (ANOMALY_RADIUS + 6.0)
            for a in self.anomalies:
                if self.world.distance_sq(sx, sy, a["x"], a["y"]) <= ar2:
                    mult *= ANOMALY_TOTEM_BONUS
                    break
        mult = min(TOTEM_RESONANCE_CAP, mult)
        self._totem_mult_cache[cid] = mult
        return mult





    # ------------------------------------------------ §AM living soil grid
    def _soil_index(self, x: float, y: float) -> int:
        col = min(self._soil_cols - 1, max(0, int(x / self.config.width * self._soil_cols)))
        row = min(self._soil_rows - 1, max(0, int(y / self.config.height * self._soil_rows)))
        return row * self._soil_cols + col

    def _soil_at(self, x: float, y: float) -> float:
        return self.soil_grid[self._soil_index(x, y)]

    def _deplete_soil(self, x: float, y: float, growth_gained: float) -> None:
        """Monocropping draws down the local fertility cell (§AM D.1)."""
        if not self.config.soil_depletion_enabled or growth_gained <= 0:
            return
        i = self._soil_index(x, y)
        self.soil_grid[i] = max(SOIL_MIN, self.soil_grid[i] - SOIL_DEPLETION_PER_GROWTH * growth_gained)

    def _fertilize_soil(self, x: float, y: float, radius: float, amount: float) -> None:
        """Compost, ash and the dead enrich every cell within radius (§AM D.2)."""
        cw = self.config.width / self._soil_cols
        ch = self.config.height / self._soil_rows
        c0 = max(0, int((x - radius) / cw)); c1 = min(self._soil_cols - 1, int((x + radius) / cw))
        r0 = max(0, int((y - radius) / ch)); r1 = min(self._soil_rows - 1, int((y + radius) / ch))
        for row in range(r0, r1 + 1):
            for col in range(c0, c1 + 1):
                qx = min(max(x, col * cw), (col + 1) * cw)
                qy = min(max(y, row * ch), (row + 1) * ch)
                if math.hypot(qx - x, qy - y) <= radius:
                    i = row * self._soil_cols + col
                    self.soil_grid[i] = min(SOIL_MAX, self.soil_grid[i] + amount)


    def distance(self, ax: float, ay: float, bx: float, by: float) -> float:
        """Proxy to world distance (convenience for tests)."""
        return self.world.distance(ax, ay, bx, by)









    # ------------------------------------------------------------------ setup
    def _rand_pos(self) -> tuple[float, float]:
        cfg = self.config
        return self.rng.uniform(0, cfg.width), self.rng.uniform(0, cfg.height)





    # BH-9 Behavioral Archetype Auto-Classifier















    def _totem_of(self, c: Creature) -> str | None:
        if not self.config.totems_enabled or not c.clan_id:
            return None
        return self.clans.get(c.clan_id, {}).get("totem")

    def _totem_stat(self, c: Creature, key: str) -> float:
        """Fast pre-cached totem-buff lookup (§AY M-2)."""
        if not c.clan_id or not self.config.totems_enabled:
            return 0.0
        stats = getattr(self, "_clan_totem_stats", None)
        if stats is not None and c.clan_id in stats:
            return stats[c.clan_id].get(key, 0.0)
        base = float(TOTEM_BUFF.get(self._totem_of(c), {}).get(key, 0.0))
        power = float(getattr(self, "_totem_power", {}).get(c.clan_id, 1.0))
        return base * self._totem_mult(c.clan_id) * power

        # No houses and no cap: roofless founders stay clanless — a settlement
        # defines a clan (§V); clans rise later from the generations.







    # ------------------------------------------------------- settlement economy












    # --------------------------------------------------------------- terrain
    def _generate_terrain(self) -> None:
        cfg = self.config
        area = cfg.width * cfg.height
        n_fertile = (
            cfg.fertile_patches
            if cfg.fertile_patches >= 0
            else self._jittered(area * 0.00008)
        )
        n_rocks = (
            cfg.rock_count if cfg.rock_count >= 0 else self._jittered(area * 0.00006)
        )
        for _ in range(n_fertile):
            r = self.rng.uniform(8.0, 20.0)
            self.fertile.append(
                {
                    "x": self.rng.uniform(r, cfg.width - r),
                    "y": self.rng.uniform(r, cfg.height - r),
                    "r": r,
                }
            )
        for _ in range(n_rocks):
            r = self.rng.uniform(2.0, 5.0)
            self.rocks.append(
                {
                    "x": self.rng.uniform(r + 1, cfg.width - r - 1),
                    "y": self.rng.uniform(r + 1, cfg.height - r - 1),
                    "r": r,
                }
            )
        # AF: pre-cache static terrain payloads to avoid rebuilding dict lists on every snapshot frame
        self._cached_terrain_fertile = [dict(p) for p in self.fertile]
        self._cached_terrain_rocks = [dict(r) for r in self.rocks]

    def _is_in_rock(self, x: float, y: float, pad: float = 0.5) -> bool:
        """Check if (x, y) is inside or too close to any solid rock obstacle."""
        for rock in self.rocks:
            min_d = rock["r"] + pad
            if self.world.distance_sq(x, y, rock["x"], rock["y"]) < min_d * min_d:
                return True
        return False

    def _food_pos(self) -> tuple[float, float]:
        """New food prefers fertile ground (god law sets the bias), strictly avoiding rocks and shelters."""
        cfg = self.config
        for _ in range(32):
            if self.fertile and self.rng.random() < cfg.fertile_food_bias:
                patch = self.rng.choice(self.fertile)
                ang = self.rng.uniform(0, 2 * math.pi)
                rad = math.sqrt(self.rng.random()) * patch["r"]
                pos = (
                    (patch["x"] + math.cos(ang) * rad) % cfg.width,
                    (patch["y"] + math.sin(ang) * rad) % cfg.height,
                )
            else:
                pos = self._rand_pos()
            if (
                not self._is_in_rock(pos[0], pos[1])
                and not (self.rivers and self._in_river_band(pos[0], pos[1], pad=1.0))
                and not self._is_point_inside_any_house(pos[0], pos[1], pad=0.8)
            ):
                return pos
        for _ in range(30):
            pos = self._rand_pos()
            if not self._is_in_rock(pos[0], pos[1]) and not self._is_point_inside_any_house(pos[0], pos[1], pad=0.8):
                return pos
        return self._rand_pos()

    def _pick_variant(self, x: float, y: float) -> str:
        """§O, §AM: choose grass/grain/berry/medicinal_herb/mushroom/poisonous for a new sprout."""
        cfg = self.config
        if not cfg.plant_variants_enabled:
            return "grass"
        if cfg.poison_rate > 0 and self.rng.random() < cfg.poison_rate:
            return "poisonous"
        season = self._season()
        # base weights shift with season (§AM)
        if season == "autumn":
            weights = {"grass": 0.25, "grain": 0.25, "berry": 0.35, "medicinal_herb": 0.05, "mushroom": 0.10}
        elif season == "winter":
            weights = {"grass": 0.35, "grain": 0.05, "berry": 0.05, "medicinal_herb": 0.00, "mushroom": 0.55}
        elif season == "summer":
            weights = {"grass": 0.30, "grain": 0.40, "berry": 0.15, "medicinal_herb": 0.10, "mushroom": 0.05}
        else:  # spring
            weights = {"grass": 0.35, "grain": 0.15, "berry": 0.15, "medicinal_herb": 0.20, "mushroom": 0.15}

        # decomposer boost: near corpses or rocks → more mushrooms
        near_decomposer = False
        for e in self.world.query_radius(x, y, NUTRIENT_RADIUS):
            if e.kind == "corpse":
                near_decomposer = True
                break
        if not near_decomposer:
            for rock in self.rocks:
                if self.world.distance(x, y, rock["x"], rock["y"]) < rock["r"] + 4.0:
                    near_decomposer = True
                    break
        if near_decomposer:
            # shift weight from grass/grain to mushroom
            weights["mushroom"] = min(0.70, weights["mushroom"] + 0.30)
            # renormalize proportionally
            total = sum(weights.values())
            for k in weights:
                weights[k] /= total
        r = self.rng.random()
        cum = 0.0
        for v, w in weights.items():
            cum += w
            if r < cum:
                return v
        return "grass"


    def _new_food(self, x: float, y: float, growth: float) -> Food:
        """Create a Food with §O variant (deterministic via rng)."""
        variant = self._pick_variant(x, y)
        return Food(x=x, y=y, growth=growth, variant=variant)

    def _resolve_rock_collision(self, c: Creature) -> dict | None:
        """Push a creature out of any rock it has wandered into; return the rock.
        §AQ PH-6: collapsed ruins with uncleared rubble block the same way."""
        w, h = self.config.width, self.config.height
        is_wrap = self.config.boundary == "wrap"
        half_w = w * 0.5
        half_h = h * 0.5
        solids = getattr(self, "_cached_solids", None)
        if solids is None:
            solids = list(self.rocks)
            if self.config.rubble_blocking_enabled:
                for rh in getattr(self, "_cached_houses", ()):
                    if getattr(rh, "is_ruin", False) and getattr(rh, "rubble", 0) > 0:
                        solids.append({
                            "x": rh.x, "y": rh.y,
                            "r": rh.size * RUBBLE_RADIUS_FRAC, "_house_id": rh.id,
                        })
        for rock in solids:
            min_d = rock["r"] + c.radius
            rx, ry = rock["x"], rock["y"]
            dx = abs(c.x - rx)
            if is_wrap and dx > half_w:
                dx -= w
            if abs(dx) > min_d:
                continue
            dy = abs(c.y - ry)
            if is_wrap and dy > half_h:
                dy -= h
            if abs(dy) > min_d:
                continue
            d2 = dx * dx + dy * dy
            if d2 < min_d * min_d:
                ux, uy = self.world.delta(c.x, c.y, rx, ry)
                if abs(ux) < 1e-6 and abs(uy) < 1e-6:
                    ang = self.rng.uniform(0, 2 * math.pi)
                    ux, uy = math.cos(ang), math.sin(ang)
                norm = math.hypot(ux, uy) or 1.0
                c.x, c.y = self.world.normalize(
                    rx + ux / norm * min_d,
                    ry + uy / norm * min_d,
                )
                c.angle = math.atan2(uy, ux)
                return rock
        return None

    def _segment_hits_circle(
        self, ax: float, ay: float, bx: float, by: float, rock: dict, pad: float = 0.0
    ) -> bool:
        """Wrap-aware test: does the straight path a→b cross a rock circle?"""
        dx, dy = self.world.delta(ax, ay, bx, by)
        b2x, b2y = ax + dx, ay + dy
        dxc, dyc = self.world.delta(ax, ay, rock["x"], rock["y"])
        cx, cy = ax + dxc, ay + dyc
        vx, vy = b2x - ax, b2y - ay
        seg2 = vx * vx + vy * vy
        t = 0.0 if seg2 == 0 else max(0.0, min(1.0, ((cx - ax) * vx + (cy - ay) * vy) / seg2))
        px_, py_ = ax + t * vx, ay + t * vy
        rr = rock["r"] + pad
        return (px_ - cx) ** 2 + (py_ - cy) ** 2 <= rr * rr

    def _warn_unreachable_food(self, c: Creature, target: Entity, blocking_entity: Any = None) -> None:
        """Warn nearby creatures about unreachable food so they also seek food elsewhere.
        Does not warn creatures that have an unobstructed path or are within close range (<=6m)."""
        r = max(14.0, self.config.signal_radius)
        r2 = r * r
        creatures = self._cached_creatures if self._cached_creatures else self.world.entities.values()
        for other in creatures:
            if isinstance(other, Creature) and other.id != c.id:
                if self.world.distance_sq(c.x, c.y, other.x, other.y) <= r2:
                    if other.clan_id == c.clan_id or not self.config.territory_enabled:
                        # If other is already right next to the food (<=6m), never blacklist it for them
                        if self.world.distance_sq(other.x, other.y, target.x, target.y) <= 36.0:
                            continue
                        if blocking_entity is not None:
                            if isinstance(blocking_entity, dict) and "r" in blocking_entity:
                                if not self._segment_hits_circle(other.x, other.y, target.x, target.y, blocking_entity, pad=other.radius):
                                    continue
                            elif hasattr(blocking_entity, "walls") or hasattr(blocking_entity, "door_side"):
                                from .settlement import _path_crosses_wall
                                if not _path_crosses_wall(other.x, other.y, target.x, target.y, blocking_entity, predator_blocked=other.is_predator):
                                    continue
                        other.give_ups[target.id] = self.tick

    def _give_up_on(self, c: Creature, target: Entity, blocking_entity: Any = None) -> None:
        """A meal is unreachable (behind stone or wall): abandon it for a while
        and seek food somewhere else — no creature starves grinding at an obstacle.
        Grudges are per-meal and shared with nearby clan members."""
        ttl = self.config.food_giveup_ticks
        if ttl <= 0:
            return
        grudges = c.give_ups
        if len(grudges) > 16:  # keep the memory bounded
            expired = [k for k, t0 in grudges.items() if self.tick - t0 >= ttl]
            for k in expired:
                del grudges[k]
        grudges[target.id] = self.tick
        self._warn_unreachable_food(c, target, blocking_entity=blocking_entity)

    # ------------------------------------------------------------- §X knowledge
    def _fact_fresh(self, c: Creature, key, ttl: int | None = None) -> dict | None:
        """Return a live fact or None (and prune it when stale).
        §AR S-3: confidence also decays linearly each tick in
        _maintain_facts, so facts fade gracefully before this hard limit."""
        f = c.facts.get(key)
        if not isinstance(f, dict):
            return None
        limit = ttl if ttl is not None else max(1, self.config.knowledge_ttl)
        if self.tick - int(f.get("tick", -limit)) > limit:
            del c.facts[key]
            return None
        return f

    def _maintain_facts(self, c: Creature) -> None:
        """§AR S-3 memory housekeeping, staggered across creatures:
        continuous confidence decay, spatial drift of stale rumours, and a
        working-memory capacity with lowest-confidence eviction."""
        if not self.config.knowledge_enabled or not c.facts:
            return
        if (self.tick + c.id) % 5 != 0:
            return
        ttl = max(1, self.config.knowledge_ttl)
        decay = 5.0 / ttl
        # capacity: hunger, wounds and age reshape the mind's workspace
        cap = WORKING_MEMORY_CAP
        if c.stage == "elder" and max(c.skills.values(), default=0.0) >= 6.0:
            cap = MEMORY_CAP_ELDER
        elif c.status == "starving" or (c.wound_severity >= 1 and c.wound_ticks > 10):
            cap = MEMORY_CAP_STRESSED
        # linear decay + drift
        for key in list(c.facts.keys()):
            f = c.facts.get(key)
            if not isinstance(f, dict):
                continue
            if key == "enemies":
                for cid in list(f.keys()):
                    meta = f.get(cid)
                    if not isinstance(meta, dict):
                        continue
                    meta["conf"] = round(float(meta.get("conf", 1.0)) - decay, 4)
                    if self.tick - int(meta.get("tick", 0)) > ttl or meta["conf"] <= 0.05:
                        del f[cid]
                if not f:
                    del c.facts[key]
                continue
            f["conf"] = round(float(f.get("conf", 1.0)) - decay, 4)
            # faded memories wander: low-conf coordinates blur
            if (
                "x" in f
                and (self.tick + c.id) % 5 == 0
                and f["conf"] < 0.9
            ):
                noise = (1.0 - f["conf"]) * 0.8
                f["x"] = round(f["x"] + self.rng.uniform(-noise, noise), 2)
                f["y"] = round(f["y"] + self.rng.uniform(-noise, noise), 2)
            if self.tick - int(f.get("tick", 0)) > ttl or f["conf"] <= 0.05:
                del c.facts[key]
        # eviction: too many facts → drop the least credible
        entries: list[tuple[float, str | int]] = []
        for key, f in c.facts.items():
            if isinstance(f, dict):
                entries.append((float(f.get("conf", 0.0)), key))
        while len(entries) > cap:
            entries.sort()
            worst_conf, worst_key = entries.pop(0)
            del c.facts[worst_key]

    def _learn(self, c: Creature, key, x: float | None = None, y: float | None = None,
               conf: float = 1.0) -> None:
        """§X firsthand experience becomes knowledge (conf 1.0)."""
        if not self.config.knowledge_enabled or self.config.knowledge_ttl <= 0:
            return
        fact: dict = {"tick": self.tick, "conf": round(conf, 3)}
        if x is not None and y is not None:
            fact["x"], fact["y"] = round(x, 2), round(y, 2)
        c.facts[key] = fact

    def _hear_fact(self, c: Creature, msg_fact: dict | None, sender_id: int | None = None) -> None:
        """§X rumor: a heard fact lands with halved confidence — retold knowledge
        is vaguer than firsthand sighting; only better news overwrites.
        §AR S-3: rumours are trust-weighted — a trusted clan-mate's word is
        believed at full strength, a stranger's or traitor's barely at all."""
        if not msg_fact or not self.config.knowledge_enabled:
            return
        kind = msg_fact.get("kind")
        conf = float(msg_fact.get("conf", 1.0)) * 0.5
        if sender_id is not None:
            trust = float(c.trust.get(sender_id, 50.0)) / 100.0
            conf *= max(0.05, min(1.0, trust))
        if conf < 0.05:
            return
        if kind == "enemy":
            clan_id = int(msg_fact.get("clan_id") or 0)
            if not clan_id or clan_id == c.clan_id:
                return
            enemies = c.facts.setdefault("enemies", {})
            old = enemies.get(clan_id)
            if old is None or conf >= float(old.get("conf", 0.0)) * 0.9:
                enemies[clan_id] = {"tick": self.tick, "conf": round(conf, 3)}
            return
        key = {"food": "food", "danger": "danger"}.get(kind)
        if key is None:
            return
        old = self._fact_fresh(c, key)
        if old is not None and float(old.get("conf", 0.0)) >= conf:
            return  # firsthand beats rumor
        c.facts[key] = {
            "x": float(msg_fact.get("x", 0.0)),
            "y": float(msg_fact.get("y", 0.0)),
            "tick": self.tick,
            "conf": round(conf, 3),
        }

    def _fact_to_share(self, c: Creature) -> dict | None:
        """The freshest known fact worth telling (rumors included while they last)."""
        ttl = max(1, self.config.knowledge_ttl)

        def score(f: dict) -> float:
            return float(f.get("conf", 1.0)) * 1000 - (self.tick - int(f.get("tick", 0)))

        best_kind = None
        best_score = -math.inf
        payload: dict = {}
        for kind in ("food", "danger"):
            f = self._fact_fresh(c, kind)
            if f is not None and score(f) > best_score:
                best_kind, best_score = kind, score(f)
                payload = {"kind": kind, "x": f["x"], "y": f["y"], "conf": f["conf"]}
        enemies = c.facts.get("enemies")
        if isinstance(enemies, dict):
            for clan_id, meta in enemies.items():
                if self.tick - int(meta.get("tick", 0)) > ttl:
                    continue
                if score(meta) > best_score:
                    best_kind, best_score = "enemy", score(meta)
                    payload = {
                        "kind": "enemy",
                        "clan_id": clan_id,
                        "x": round(c.x, 2),
                        "y": round(c.y, 2),
                        "conf": meta.get("conf", 1.0),
                    }
        return payload if best_kind is not None else None

    def _jittered(self, target: float) -> int:
        v = self.config.spawn_variance
        return max(0, round(self.rng.uniform(target * (1 - v), target * (1 + v))))

    def _count(self, override: int, share: float, total: int) -> int:
        """Explicit override wins; otherwise take this caste's slice of the pyramid."""
        if override >= 0:
            return override
        return max(0, round(total * share))




    def _refresh_cache(self) -> None:
        """T: single-pass over entities — build creature/food/house/corpse caches + sorted creature list.

        AF: one O(N) scan replaces the old world.creatures() call (O(N)) plus
        independent per-subsystem entity scans in plants/fires/enforce_food_law/corpses.
        """
        self._totem_mult_cache = {}  # resonance is recomputed per tick
        creatures: list[Creature] = []
        foods: list = []
        houses: list = []
        corpses: list = []
        m: dict[int, list[Creature]] = {}
        for e in self.world.entities.values():
            t = type(e)
            if t is Creature:
                creatures.append(e)
                m.setdefault(e.clan_id, []).append(e)  # type: ignore[union-attr]
            elif t is Food:
                foods.append(e)
            elif t is House:
                if not e.is_ruin:  # type: ignore[union-attr]
                    houses.append(e)
            elif t is Corpse:
                corpses.append(e)
        self._cached_creatures = creatures
        self._clan_members = m
        # §AU CPU: entities insertion order == id-ascending (monotonic _next_id);
        # creatures list is already sorted — avoid O(N log N) sort without changing law.
        self._cached_creatures_sorted = creatures
        self._cached_foods = foods
        self._cached_houses = sorted(houses, key=lambda h: h.id)
        self._cached_corpses = corpses

        houses_by_clan: dict[int, list[House]] = {}
        unclaimed_houses: list[House] = []
        for h in houses:
            if h.clan_id:
                houses_by_clan.setdefault(h.clan_id, []).append(h)
            else:
                unclaimed_houses.append(h)
        self._houses_by_clan = houses_by_clan
        self._unclaimed_houses = unclaimed_houses
        self._house_by_pos = {(round(h.x, 2), round(h.y, 2)): h for h in houses}
        # Spatial house grid (50x50 cells) for O(1) near-house lookups without touching world entities
        house_grid: dict[tuple[int, int], list[House]] = {}
        for h in houses:
            gx, gy = int(h.x // 50), int(h.y // 50)
            for dgx in (-1, 0, 1):
                for dgy in (-1, 0, 1):
                    house_grid.setdefault((gx + dgx, gy + dgy), []).append(h)
        self._house_grid = house_grid

        # PERF: Cache solids (rocks + rubble) and house bed capacities once per tick
        self._house_capacities = {h.id: self._house_beds(h) for h in houses}
        solids = list(self.rocks)
        if self.config.rubble_blocking_enabled:
            for rh in self._cached_houses:
                if getattr(rh, "is_ruin", False) and getattr(rh, "rubble", 0) > 0:
                    solids.append({
                        "x": rh.x, "y": rh.y,
                        "r": rh.size * RUBBLE_RADIUS_FRAC, "_house_id": rh.id,
                    })
        self._cached_solids = solids

        # §AU CPU: merged single pass for sleeping occupancy + bodies under roof.
        house_occ: dict[int, int] = {}
        bodies: dict[int, int] = {}
        for c in creatures:
            # bodies physically under each roof (overcrowd drain)
            for h in house_grid.get((int(c.x // 50), int(c.y // 50)), []):
                half = h.size / 2
                if abs(c.x - h.x) < half and abs(c.y - h.y) < half:
                    bodies[h.id] = bodies.get(h.id, 0) + 1
                    break
            if getattr(c, "sleeping", False):
                hid = getattr(c, "house_id", None)
                if hid is not None:
                    house_occ[hid] = house_occ.get(hid, 0) + 1
                else:
                    for h in house_grid.get((int(c.x // 50), int(c.y // 50)), []):
                        if self._inside_house(c, h):
                            house_occ[h.id] = house_occ.get(h.id, 0) + 1
                            break
        self._house_occupants = house_occ
        self._house_bodies = bodies
        if getattr(self, "_elev_c_buf", None) is None and getattr(self, "elev_grid", None):
            try:
                import ctypes
                self._elev_c_buf = (ctypes.c_float * len(self.elev_grid))(*self.elev_grid)
            except Exception:
                self._elev_c_buf = None

        # Precompute shrine positions for instant O(1) lookups (§AP)
        shrine_pos: dict[int, tuple[float, float]] = {}
        for cid, info in self.clans.items():
            mhid = info.get("main_house_id")
            house = self.world.entities.get(mhid) if mhid else None
            if not isinstance(house, House) or house.is_ruin or house.clan_id != cid:
                c_houses = houses_by_clan.get(cid, [])
                house = c_houses[0] if c_houses else None
            if isinstance(house, House):
                shrine_pos[cid] = (house.x + house.size / 2.0 + 1.5, house.y)
        self._shrine_pos_by_clan = shrine_pos

        # AZ Phase 4a P0: _leader_pos O(N) inner scan → O(1) via world.entities.get
        leader_pos: dict[int, tuple[float, float]] = {}
        for cid, info in self.clans.items():
            lid = info.get("leader_id")
            if not lid:
                continue
            ent = self.world.entities.get(lid)
            if isinstance(ent, Creature) and ent.clan_id == cid:
                leader_pos[cid] = (ent.x, ent.y)
        self._leader_pos = leader_pos

        # §AS L-2/L-5: totem power rides on the chief's presence at the hall
        # and on his rites; theocracy never lets faith fall below full.
        totem_power: dict[int, float] = {}
        totem_stats: dict[int, dict[str, float]] = {}
        if self.config.totems_enabled:
            for cid, clan in self.clans.items():
                totem_name = clan.get("totem")
                tp = 1.0
                if clan.get("governance") == "theocracy":
                    tp = 1.0
                else:
                    lpos = leader_pos.get(cid)
                    mhid = clan.get("main_house_id")
                    if lpos and mhid:
                        for h in houses_by_clan.get(cid, ()):
                            if h.id == mhid and self.world.distance_sq(lpos[0], lpos[1], h.x, h.y) <= (h.size * 0.5) ** 2:
                                tp = 2.0
                                break
                        else:
                            tp = 0.5
                    elif not lpos:
                        tp = 0.5
                totem_power[cid] = tp
                if totem_name and totem_name in TOTEM_BUFF:
                    mult = self._totem_mult(cid) * tp
                    totem_stats[cid] = {k: v * mult for k, v in TOTEM_BUFF[totem_name].items()}
        self._totem_power = totem_power
        self._clan_totem_stats = totem_stats

        # §AQ PH-9: living priest per clan (bio-electric calm aura)
        priest_pos: dict[int, tuple[float, float]] = {}
        for cid, members in m.items():
            for c in members:
                if c.caste == "Priest" and c.energy > 20.0:
                    priest_pos[cid] = (c.x, c.y)
                    break
        self._priest_pos = priest_pos
        for cid in self.clans:
            if cid not in self._totem_mult_cache:
                self._totem_mult(cid)

    def _get_creatures(self) -> list[Creature]:
        if self._cached_creatures:
            return self._cached_creatures
        self._refresh_cache()
        return self._cached_creatures

    def _refresh_movement_cache(self) -> None:
        """BJ-2: lightweight post-movement refresh (no full entity rescan).

        Keeps the full house grid / clan tables built at tick start and only
        refreshes dynamic creature coordinates: creature list (creature-only
        scan), clan membership, leader/priest positions, and house occupancy
        bodies using the already-built spatial house grid. Skips foods,
        corpses, ruins, and _houses_by_clan rebuild.
        """
        creatures: list[Creature] = []
        m: dict[int, list[Creature]] = {}
        for e in self.world.entities.values():
            if type(e) is Creature:
                creatures.append(e)
                m.setdefault(e.clan_id, []).append(e)  # type: ignore[union-attr]
        self._cached_creatures = creatures
        self._clan_members = m
        self._cached_creatures_sorted = creatures
        house_grid = getattr(self, "_house_grid", {}) or {}
        house_occ: dict[int, int] = {}
        bodies: dict[int, int] = {}
        for c in creatures:
            for h in house_grid.get((int(c.x // 50), int(c.y // 50)), []):
                half = h.size / 2
                if abs(c.x - h.x) < half and abs(c.y - h.y) < half:
                    bodies[h.id] = bodies.get(h.id, 0) + 1
                    break
            if getattr(c, "sleeping", False):
                hid = getattr(c, "house_id", None)
                if hid is not None:
                    house_occ[hid] = house_occ.get(hid, 0) + 1
                else:
                    for h in house_grid.get((int(c.x // 50), int(c.y // 50)), []):
                        if self._inside_house(c, h):
                            house_occ[h.id] = house_occ.get(h.id, 0) + 1
                            break
        self._house_occupants = house_occ
        self._house_bodies = bodies
        leader_pos: dict[int, tuple[float, float]] = {}
        for cid, info in self.clans.items():
            lid = info.get("leader_id")
            if not lid:
                continue
            ent = self.world.entities.get(lid)
            if isinstance(ent, Creature) and ent.clan_id == cid:
                leader_pos[cid] = (ent.x, ent.y)
        self._leader_pos = leader_pos
        priest_pos: dict[int, tuple[float, float]] = {}
        for cid, members in m.items():
            for c in members:
                if c.caste == "Priest" and c.energy > 20.0:
                    priest_pos[cid] = (c.x, c.y)
                    break
        self._priest_pos = priest_pos

    def _sync_soa_incremental(self) -> None:
        """BJ-1: incremental AgentSoA slot management (no full rebuild).

        - Death: swap-with-last O(1) compaction + _soa_id_map fixup + grid remove.
        - Birth: append via add_agent into pre-allocated buffer + grid insert.
        - Move: in-place sync_slot + incremental grid.move.
        - Capacity: grow (doubling) only when len(alive) >= capacity.
        Newborns added to world after the last _refresh_cache are picked up
        via a creature-only delta scan so same-tick births join the SoA.
        """
        soa = getattr(self, "_soa", None)
        if soa is None:
            return
        id_map: dict[int, int] = getattr(self, "_soa_id_map", None)  # type: ignore
        if id_map is None:
            id_map = {}
            self._soa_id_map = id_map  # type: ignore[attr-defined]
        grid = getattr(self, "_nn_grid", None)
        # Include same-tick newborns missing from the (pre-reproduce) cache.
        alive: list[Creature] = self._cached_creatures
        try:
            alive_ids: set[int] = {c.id for c in alive}
            for e in self.world.entities.values():
                if type(e) is Creature and e.id not in alive_ids:
                    alive.append(e)
                    alive_ids.add(e.id)
                    self._clan_members.setdefault(e.clan_id, []).append(e)  # type: ignore[union-attr]
        except Exception:
            alive_ids = {c.id for c in alive}
        # --- deaths: compact-remove slots whose id is no longer alive ---
        try:
            for eid in list(id_map.keys()):
                if eid not in alive_ids:
                    idx = id_map.get(eid)
                    if idx is None:
                        continue
                    # Identify the id occupying the last slot (moves into idx).
                    try:
                        last_idx = soa.N - 1
                        if hasattr(soa.ids, "tolist"):
                            last_eid = int(soa.ids[last_idx]) if soa.N > 0 else -1
                        else:
                            last_eid = int(soa.ids[last_idx]) if soa.N > 0 else -1
                    except Exception:
                        last_eid = -1
                    try:
                        soa.remove_at(int(idx))
                    except Exception:
                        continue
                    id_map.pop(eid, None)
                    if last_eid != -1 and last_eid != eid and last_eid in id_map:
                        id_map[last_eid] = int(idx)
                    if grid is not None:
                        try:
                            grid.remove(int(eid))
                        except Exception:
                            pass
        except Exception:
            pass
        # --- capacity: grow once if needed (no per-tick realloc) ---
        try:
            if len(alive) >= int(getattr(soa, "capacity", 0)):
                soa.ensure_capacity(max(2000, len(alive) * 2 + 10))
        except Exception:
            pass
        # --- births + moves ---
        for c in alive:
            idx = id_map.get(c.id)
            if idx is None:
                _mr = _ma = _mk = None
                try:
                    if hasattr(self, "_morph_cache") and c.id in self._morph_cache:
                        _mr, _ma, _mk = self._morph_cache[c.id]  # type: ignore
                    else:
                        _mr = getattr(c, "_bc_morph_r", None)
                        _ma = getattr(c, "_bc_morph_phi", None)
                        _mk = getattr(c, "_bc_morph_k", None)
                except Exception:
                    pass
                if _mr is None and _evo_mgr is not None and getattr(c, "caste", None):
                    try:
                        _tr, _tphi, _tk = _evo_mgr.get_template_for_caste(c.caste)
                        _mr = list(_tr)
                        _ma = list(_tphi)
                        _mk = int(_tk)
                        if hasattr(self, "_morph_cache"):
                            self._morph_cache[c.id] = (list(_mr), list(_ma), int(_mk))
                    except Exception:
                        pass
                existing_genome = None
                try:
                    if hasattr(self, "_nn_cache") and c.id in self._nn_cache:
                        existing_genome = self._nn_cache[c.id]  # type: ignore
                except Exception:
                    pass
                if existing_genome is None:
                    try:
                        if _evolution is not None and hasattr(soa, "genomes"):
                            pa_idx = id_map.get(getattr(c, "mother_id", None))
                            pb_idx = id_map.get(getattr(c, "father_id", None))
                            if pa_idx is not None and pb_idx is not None:
                                g_a = soa.genomes[pa_idx]
                                g_b = soa.genomes[pb_idx]
                                if hasattr(_evolution, "crossover_mutate_blockwise"):
                                    existing_genome = _evolution.crossover_mutate_blockwise(g_a, g_b, rng=self.rng)
                                else:
                                    existing_genome = _evolution.crossover_mutate(
                                        g_a, g_b,
                                        p_mut=float(getattr(self.config, "mutation_rate", 0.05)),
                                        sigma=float(getattr(self.config, "mutation_sigma", 0.08)),
                                    )
                            elif getattr(c, "_nn_genome", None) is not None:
                                existing_genome = c._nn_genome  # type: ignore
                            else:
                                existing_genome = _evolution._build_base_genome(soa.genome_size)
                    except Exception:
                        existing_genome = None
                try:
                    new_idx = soa.add_agent(
                        int(c.id), float(c.x), float(c.y),
                        angle=float(c.angle), energy=float(c.energy), health=float(c.health),
                        genome=existing_genome, morph_radii=_mr, morph_angles=_ma, morph_k=_mk,
                        caste=getattr(c, "caste", None), sides=getattr(c, "sides", None),
                    )
                    id_map[int(c.id)] = int(new_idx)
                    if grid is not None:
                        try:
                            grid.insert(int(c.id), float(c.x), float(c.y))
                        except Exception:
                            pass
                except Exception:
                    continue
            else:
                try:
                    if 0 <= int(idx) < int(soa.N):
                        soa.sync_slot(int(idx), float(c.x), float(c.y), float(c.angle), float(c.energy), float(c.health))
                    else:
                        id_map.pop(c.id, None)
                        continue
                except Exception:
                    continue
                if grid is not None:
                    try:
                        if hasattr(grid, "move"):
                            grid.move(int(c.id), float(c.x), float(c.y))
                        else:
                            grid.insert(int(c.id), float(c.x), float(c.y))
                    except Exception:
                        pass

        # Heal corrupted / legacy default square morphs (e.g. k=4 on Soldier, Woman, Artisan, etc.)
        if getattr(self, "_morph_healed", False) is not True and _evo_mgr is not None and hasattr(soa, "morph_k") and hasattr(soa, "morph_radii"):
            healed_any = False
            for c in alive:
                midx = id_map.get(c.id)
                if midx is not None and 0 <= midx < soa.N:
                    caste = getattr(c, "caste", None)
                    if caste and caste in ("Soldier", "Woman", "Artisan", "Professional", "Noble", "Priest"):
                        expected_k = _evo_mgr.get_template_for_caste(caste)[2]
                        cur_k = int(soa.morph_k[midx])
                        asym = float(soa.morph_traits[midx, 4]) if hasattr(soa, "morph_traits") else 0.0
                        if cur_k != expected_k and (asym < 0.05 or cur_k == 4):
                            tr, tphi, tk = _evo_mgr.get_template_for_caste(caste)
                            soa.morph_k[midx] = tk
                            if hasattr(soa.morph_radii, "shape"):
                                soa.morph_radii[midx, :len(tr)] = tr
                                soa.morph_angles[midx, :len(tphi)] = tphi
                            else:
                                for ki, rv in enumerate(tr):
                                    soa.morph_radii[midx][ki] = float(rv)
                                for ki, pv in enumerate(tphi):
                                    soa.morph_angles[midx][ki] = float(pv)
                            if hasattr(self, "_morph_cache"):
                                self._morph_cache[c.id] = (list(tr), list(tphi), int(tk))
                            healed_any = True
            if healed_any and _morphology is not None:
                try:
                    _morphology.sync_soa_traits(soa)
                except Exception:
                    pass
            self._morph_healed = True

    def _record_phase(self, name: str, ms: float) -> None:
        """BJ-6: record one subsystem timing sample (last + rolling totals)."""
        try:
            self._phase_ms[name] = round(float(ms), 3)
            self._phase_totals[name] = float(self._phase_totals.get(name, 0.0)) + float(ms)
            self._phase_counts[name] = int(self._phase_counts.get(name, 0)) + 1
        except Exception:
            pass

    def phase_averages(self) -> dict[str, float]:
        """BJ-6: mean ms per subsystem over recorded ticks (for telemetry)."""
        out: dict[str, float] = {}
        try:
            for k, total in self._phase_totals.items():
                n = max(1, int(self._phase_counts.get(k, 1)))
                out[k] = round(total / n, 3)
        except Exception:
            pass
        return out

    # ------------------------------------------------------------------ tick
    def step(self) -> None:
        """Advance the world by exactly one tick (deterministic)."""
        t_step0 = time.perf_counter()
        self._eaten.clear()
        self._fleeing_ids = set()  # §AR S-5: who ran scared this tick
        self._beds.clear()  # beds are re-contested every tick, in id order
        self._events_this_tick = []
        self._eaters_this_tick = []
        # §AP: a sacred truce (synod/epiphany) stills all strife while it lasts
        if self.truce_ticks > 0:
            self.truce_ticks -= 1
        self._update_weather()
        self._update_wind()  # §AQ PH-2: the sky's breath follows the weather
        self._update_rivers()  # §AQ PH-3: rain swells the channels
        self._update_traffic()  # §AQ PH-4: grass reclaims quiet paths
        self._update_seismic()  # §AQ PH-8: the ground sometimes moves
        self._update_lightning()  # §AQ PH-9: storms strike real bolts
        self._update_law_wave()  # §AQ PH-10: the shimmer front sweeps on
        # §Q signals decay (ripples fade)
        self.signals = [sg for sg in self.signals if sg["ttl"] > 1]
        for sg in self.signals:
            sg["ttl"] -= 1
        # §AU CPU: build spatial index for signals — per-creature hearing drops
        # from O(N*S) to O(N * avg_nearby) (~400 -> ~5-10). Law-preserving:
        # grid is superset for max_hear_d; iteration order = insertion order.
        self._signal_grid: dict[tuple[int, int], list[tuple[int, dict]]] = {}
        self._signal_grid_buckets: list[list[tuple[int, dict]] | None] | None = None
        self._signal_grid_cs = self.world.cell_size
        if self.signals and self.config.communication_enabled:
            cols = self.world.cols
            rows = self.world.rows
            cs = self._signal_grid_cs
            inv_cs = 1.0 / cs if cs else 1.0
            buckets: list[list[tuple[int, dict]] | None] = [None] * (cols * rows)
            for idx, sg in enumerate(self.signals):
                gx = int(sg["x"] * inv_cs) % cols if cols else 0
                gy = int(sg["y"] * inv_cs) % rows if rows else 0
                ci = gy * cols + gx
                b = buckets[ci]
                if b is None:
                    buckets[ci] = [(idx, sg)]
                else:
                    b.append((idx, sg))
            self._signal_grid_buckets = buckets
            sig_r = self.config.signal_radius
            snd_boost = SOUND_WIND_MULT * self.wind_speed if self.config.scent_enabled else 0.0
            self._sig_tick_snd_boost = snd_boost
            self._sig_tick_r = sig_r
            self._sig_tick_r2 = sig_r * sig_r
            max_hear_d = sig_r * 2.5 * (1.0 + snd_boost)
            self._sig_tick_max_hear_d = max_hear_d
            self._sig_tick_max_hear_d2 = max_hear_d * max_hear_d
            self._sig_tick_rx = int(max_hear_d * inv_cs) + 1
        # §AR S-1: a war cry must wake sleepers BEFORE they settle — the full
        # hearing pass never reaches a sleeping body.
        if self.signals and self.config.communication_enabled:
            for sg in self.signals:
                if sg.get("kind") != "warcry":
                    continue
                wr = self.config.signal_radius * WARCRY_RADIUS_MULT
                for o in self.world.query_radius(sg["x"], sg["y"], wr):
                    if isinstance(o, Creature) and not o.is_predator:
                        o.alarm_wake_ticks = max(o.alarm_wake_ticks, 20)
        self._update_fires()
        self._update_campfires()  # §AO E: explorers kindle the night's fire
        self._update_disasters()
        self._update_temperature()  # §AQ PH-1: the heat field breathes
        # Phase 4 Density Damping — update xi and scales for current tick
        if getattr(self.config, "soft_cap_enabled", True) and not _IS_TEST:
            try:
                pop_d = len(self._cached_creatures)
                # §BQ-6: fixed setpoint — K is no longer modulated by age/season
                # (see _reproduce). The food target keeps its seasonal flavour.
                carrying_d = self.config.effective_carrying_capacity
                if getattr(self, "_density_engine", None) is not None:
                    self._density_xi, self._density_scales = self._density_engine.update(pop_d, self.tick, carrying_d)
                else:
                    from ..density_damping import compute_xi, scales_for_xi  # type: ignore
                    _xi_d = compute_xi(pop_d, carrying_d, True)
                    self._density_xi = _xi_d
                    self._density_scales = scales_for_xi(_xi_d, self.config)
            except Exception:
                self._density_xi = 0.0
                self._density_scales = {}
        else:
            self._density_xi = 0.0
            self._density_scales = {}
        self._update_plants()
        self.world.rebuild_index()
        _ph_cache = time.perf_counter()
        self._refresh_cache()
        self._record_phase("cache_full", (time.perf_counter() - _ph_cache) * 1000.0)
        self._update_anomaly_discovery()  # §AQ PH-10: explorers map the strange

        # AZ Phase 2 P1: evict _identity_cache for dead entities (never queried again)
        if self.tick % 30 == 0 and self._identity_cache:
            try:
                live_entity_ids = set(self.world.entities.keys())
                dead_keys = [k for k in self._identity_cache if k[0] not in live_entity_ids]
                for k in dead_keys:
                    self._identity_cache.pop(k, None)
            except Exception:
                pass
        # Leaderless-clan repair: catch clans whose leader_id points to a dead or
        # missing creature (e.g. loaded from old state, or succession_enabled=False).
        # Runs every 30 ticks so the cost is negligible.
        if self.tick % 30 == 0 and self.clans:
            live_ids: set[int] = {c.id for c in self._cached_creatures}
            for cid, clan in self.clans.items():
                lid = clan.get("leader_id")
                if lid is not None and lid not in live_ids:
                    # Leader is dead or missing — elect a replacement immediately.
                    members = self._clan_members.get(cid, [])
                    if members:
                        gov = clan.get("governance", "republic")
                        if gov == "monarchy":
                            successor = sorted(members, key=lambda cc: (-cc.age, cc.id))[0]
                        elif gov == "theocracy":
                            priests = [cc for cc in members if cc.caste == "Priest"]
                            successor = sorted(priests or members, key=lambda cc: (-cc.age, cc.id))[0]
                        elif gov == "junta":
                            soldiers = [cc for cc in members if cc.caste == "Soldier"]
                            successor = sorted(soldiers or members, key=lambda cc: (-getattr(cc, "skills", {}).get("combat", 0.0), -cc.age, cc.id))[0]
                        else:
                            successor = sorted(members, key=lambda cc: (-cc.sides, -cc.age, cc.id))[0]
                        clan["leader_id"] = successor.id
                        if self.config.succession_enabled:
                            succ_name = personal_name_for(successor.id, self.config.seed, successor.generation)
                            self._log_clan_history(
                                cid,
                                "leader_change",
                                f"{succ_name} (#{successor.id}) elected after leaderless interregnum (Day {self.day})",
                            )
                            self._emit(
                                HistoryEvent(
                                    type="succession",
                                    tick=self.tick + 1,
                                    entity_id=successor.id,
                                    caste=successor.caste,
                                    x=round(successor.x, 2),
                                    y=round(successor.y, 2),
                                    payload={"clan_id": cid, "prev_leader": lid, "new_leader": successor.id, "clan_name": clan.get("name")},
                                )
                            )
                    else:
                        clan["leader_id"] = None

        houses = self._cached_houses
        tod = self._time_of_day()
        is_night = self._is_night(tod)
        # §AO Phase E: close the nightly bed-overflow census at dawn.
        if not is_night and getattr(self, "_overflow_was_night", False):
            self._last_night_overflow = max(
                getattr(self, "_last_night_overflow", 0),
                getattr(self, "_bed_overflow_night", 0),
            )
            self._bed_overflow_night = 0
        self._overflow_was_night = is_night
        env_sight = self.env_sight_mult()
        env_speed = self.env_speed_mult()
        clan_house_map: dict[int, House] = {
            h.clan_id: h for h in houses if isinstance(h, House) and h.clan_id and not h.is_ruin
        }
        self._sync_wind_cache()
        # PERF: OMP hint packing removed — per-tick Python packing of all
        # entities (~1.2ms) exceeded the fallback benefit. Native acceleration
        # stays wired where it is exactly law-preserving: OpenMP collision
        # sweep broadphase, compiled wall checks, batched NN raycasts.
        self._omp_hints = {}  # type: ignore[attr-defined]
        # PERF (no logic change): inverted torch-bearer index for the night
        # perceive gate. Object refs (not ids): fields are read live, so
        # mid-loop moves/equips/douses/deaths are observed exactly as the
        # spatial query would see them (same objects, same math) — including
        # corpse-light from bearers killed earlier in the loop. Existential
        # predicate (break on first hit, no RNG) → order-free. Falls back to
        # the spatial query when torches are numerous.
        if is_night:
            try:
                self._torch_bearers = [o for o in self._cached_creatures if o.equipped_item == "torch"]  # type: ignore[attr-defined]
            except Exception:
                self._torch_bearers = None  # type: ignore[attr-defined]
        else:
            self._torch_bearers = []  # type: ignore[attr-defined]
        _ph_creatures = time.perf_counter()
        _eta_decay = float(getattr(self, "_safeguard_eta", 0.0) or 0.0)
        _xi_decay = float(getattr(self, "_density_xi", 0.0) or 0.0)
        _eff_decay = self.config.energy_decay_per_tick
        if _eta_decay:
            _eff_decay *= (1.0 - 0.4 * _eta_decay)
        if _xi_decay:
            _stress = float(getattr(self.config, "crowding_stress_mult", 1.0))
            _eff_decay *= (1.0 + _stress * _xi_decay + 0.8 * _stress * (_xi_decay ** 2))
        self._eff_decay_tick = _eff_decay
        self._xi_decay_tick = _xi_decay
        for creature in list(self._cached_creatures):
            if creature.id in self.world.entities:
                self._update_creature(creature, houses, tod, is_night, env_sight, env_speed, clan_house_map)
        self._record_phase("creatures", (time.perf_counter() - _ph_creatures) * 1000.0)
        # BH-9: refresh archetype tags every 20 ticks (cheap) for UI + nocturnal gate
        if self.tick % 20 == 0:
            for c in self._cached_creatures:
                try:
                    arch = self._classify_archetype(c)
                    if arch:
                        self._archetype_cache[c.id] = arch  # type: ignore
                    elif c.id in self._archetype_cache:
                        del self._archetype_cache[c.id]
                    # legacy compat (slots may ignore)
                    try:
                        c._archetype = arch  # type: ignore
                    except Exception:
                        pass
                except Exception:
                    pass
            # prune dead archetypes / morph / nn
            try:
                alive_ids = {c.id for c in self._cached_creatures}
                for k in list(self._archetype_cache.keys()):
                    if k not in alive_ids:
                        del self._archetype_cache[k]
                if self.tick % 100 == 0:
                    for k in list(getattr(self, "_morph_cache", {}).keys()):
                        if k not in alive_ids:
                            del self._morph_cache[k]  # type: ignore
                    for k in list(getattr(self, "_nn_cache", {}).keys()):
                        if k not in alive_ids:
                            del self._nn_cache[k]  # type: ignore
            except Exception:
                pass
        # §AX P0: single consolidated cache — positions moved but clan membership
        # unchanged; defer full rebuild until after war/prune to avoid triplicate.
        # _update_disease and _update_war handle stale cache via w.entities checks
        # and rebuilt spatial index; next tick's _refresh_cache will be fresh.
        # M-4: stagger heavy post-creature work at >700c (saves ~30ms at 800c, keeps 300c single-core)
        _do_heavy_post = not (len(self._cached_creatures) > 700 and self.tick % 2 == 1)
        _ph_post = time.perf_counter()
        if _do_heavy_post:
            self._update_disease()
        # AA: positions moved this tick; re-bucket so the spatial war/mob
        # queries below see where everyone actually stands now.
        self.world.rebuild_index()
        if _do_heavy_post:
            self._update_war()
        self._update_night_watch()  # §AO C: spearmen guard the thresholds
        self._update_leader_orders()  # §AS L-2: retreat, ritual, harvest, evacuate
        self._prune_extinct_clans()  # §P0: keep clan bookkeeping bounded
        # BJ-2: lightweight post-movement refresh — full entity classification
        # + house grid stay from tick start; only dynamic creature coords update.
        self._refresh_movement_cache()
        self._record_phase("post_disease_war", (time.perf_counter() - _ph_post) * 1000.0)
        # Phase 5 Safeguards — 1 Hz homeostatic loop (eta, Tier1/2/3)
        if getattr(self.config, "safeguard_enabled", True) and not _IS_TEST and getattr(self, "_safeguard", None) is not None and self.tick % 10 == 0:
            try:
                N = len(self._cached_creatures)
                females_alive = sum(1 for c in self._cached_creatures if getattr(c, "shape", "polygon") == "line")
                males_alive = sum(1 for c in self._cached_creatures if getattr(c, "shape", "polygon") != "line")
                # Reproductive/functional extinction: if one sex is completely gone, world cannot reproduce
                sex_extinct = (N > 0 and (females_alive == 0 or males_alive == 0))
                eta, tier, scales = self._safeguard.update(N, self.tick, sex_extinct=sex_extinct)  # type: ignore
                self._safeguard_eta = eta  # type: ignore
                self._safeguard_tier = tier  # type: ignore
                # Tier3 genesis: single-chance miracle (max_miracles=1 by default; if failed, extinction follows)
                max_miracles = int(getattr(self.config, "safeguard_max_miracles", 1))
                can_genesis = getattr(self._safeguard, "miracles", 0) < max_miracles
                if can_genesis and tier == 3 and (N <= int(getattr(self.config, "safeguard_critical_pop", 12)) or sex_extinct):
                    batch = int(getattr(self.config, "safeguard_genesis_batch", 6))
                    spawned = []
                    max_gen = max((getattr(c, "generation", 0) for c in self._cached_creatures), default=0)
                    for i in range(batch):
                        # spawn creature near center with caste & sex
                        x = self.rng.uniform(20, self.config.width - 20)
                        y = self.rng.uniform(20, self.config.height - 20)
                        # Determine sex: if one sex is missing, ensure it is replenished
                        if females_alive == 0 and males_alive > 0:
                            is_female = (i < max(2, batch // 2 + 1))
                        elif males_alive == 0 and females_alive > 0:
                            is_female = (i >= max(2, batch // 2 + 1))
                        else:
                            is_female = (i % 2 == 0) if self.config.sex_ratio == 0.5 else (self.rng.random() < self.config.sex_ratio)

                        if is_female:
                            shape = "line"
                            sides = 2
                            iso = 60.0
                            caste = "Woman"
                        else:
                            shape = "polygon"
                            sides = self.rng.choice([3, 4, 5, 6, 8, 12, PRIEST_SIDES])
                            iso = self.rng.uniform(10.0, 59.5) if sides == 3 else 60.0
                            caste = caste_name(sides, shape, iso)

                        traits = traits_for(caste)
                        lifespan = traits.lifespan * self.config.lifespan_mult * self.rng.uniform(0.9, 1.25)
                        # Genesis beings are young adults ready to found the new era and immediately reproduce
                        adult_floor = int(getattr(self.config, "adult_age", 350))
                        age = adult_floor + self.rng.randint(10, 50)
                        energy = self.config.energy_max * self.rng.uniform(0.70, 0.90)
                        c = Creature(
                            shape=shape,
                            sides=sides,
                            iso_angle=iso,
                            caste=caste,
                            x=x,
                            y=y,
                            angle=self.rng.uniform(0, 2 * math.pi),
                            speed=traits.speed,
                            energy=energy,
                            age=age,
                            lifespan=lifespan,
                            generation=max_gen,
                        )
                        self._init_creature_evolution(c)
                        if _evo_mgr is not None:
                            try:
                                template_r, template_phi, template_k = _evo_mgr.get_template_for_caste(caste)
                                c._bc_morph_r = list(template_r)
                                c._bc_morph_phi = list(template_phi)
                                c._bc_morph_k = int(template_k)
                            except Exception:
                                pass
                        self.world.add(c)
                        spawned.append(c)
                        # add to SoA if present
                        if getattr(self, "_soa", None) is not None:
                            try:
                                self._soa.add_agent(
                                    int(c.id), float(c.x), float(c.y),
                                    angle=float(c.angle), energy=float(c.energy), health=float(c.health),
                                    morph_radii=getattr(c, "_bc_morph_r", None),
                                    morph_angles=getattr(c, "_bc_morph_phi", None),
                                    morph_k=getattr(c, "_bc_morph_k", None),
                                )
                            except Exception:
                                pass
                    self._safeguard.miracles += 1  # type: ignore
                    # If all clans were extinct, re-found clans for the new generation
                    if len(self.clans) == 0 and len(self.world.creatures()) > 0:
                        try:
                            self._found_founding_clans()
                        except Exception:
                            pass
                    elif self.clans and spawned:
                        living_cids = list(self.clans.keys())
                        for sc in spawned:
                            if not sc.clan_id:
                                sc.clan_id = self.rng.choice(living_cids)
                    # log miracle
                    try:
                        self.history.append(HistoryEvent(type="miracle", tick=self.tick + 1, entity_id=0, x=round(self.config.width/2,1), y=round(self.config.height/2,1), payload={"kind": "MIRACLE_OF_THE_SPHERE", "eta": round(eta,2), "N": N, "batch": batch}))
                        self._events_this_tick.append({"type": "miracle", "tick": self.tick + 1, "payload": {"kind": "MIRACLE_OF_THE_SPHERE"}})
                    except Exception:
                        pass
            except Exception:
                pass
        elif not getattr(self.config, "safeguard_enabled", True):
            self._safeguard_eta = 0.0
            self._safeguard_tier = 0
        _ph_society = time.perf_counter()
        self._reproduce()
        # BC bake traits for any new SoA morph entries (lazy)
        if getattr(self.config, "morphology_annealing_enabled", True) and getattr(self, "_soa", None) is not None and _morphology is not None:
            try:
                for idx in range(self._soa.N):
                    if self._soa.morph_k[idx] and float(self._soa.morph_traits[idx, 0]) == 0.0:
                        _morphology.bake_traits_for_index(idx, self._soa, self.config)
                        # Dmult etc now ready for SAT
            except Exception:
                pass
        # N150 hotfix: throttle heavy clan/politics work when pop >200 in production — staggered offsets to avoid 15-tick pileup
        c_n = len(self._cached_creatures)
        if c_n > 200 and not _IS_TEST:
            if self.tick % 3 == 1:
                self._update_relations()
                self._update_territory()
            if self.tick % 5 == 2:
                self._update_politics()
            if self.tick % 10 == 3:
                self._update_clan_specialization()
            # schism/culture already gated by config, but also throttle
            if self.config.schism_enabled and self.tick % 3 == 1:
                self._update_schism()
            if self.config.culture_enabled and self.tick % 10 == 3:
                self._update_culture()
            if self.tick % 5 == 1:
                self._update_builders()
                self._update_structures()
            if self.tick % 5 == 3:
                self._update_hearths()
                self._update_agriculture()
            if self.tick % 5 == 4:
                self._update_faith()
        else:
            self._update_relations()
            self._update_territory()
            self._update_schism()
            self._update_politics()
            self._update_clan_specialization()
            self._update_culture()
            self._update_builders()
            self._update_structures()
            self._update_hearths()
            self._update_agriculture()
            self._update_faith()
        # BC.6.1 SAT narrowphase — only when morphology enabled and SoA present
        if getattr(self.config, "morphology_annealing_enabled", True) and getattr(self, "_soa", None) is not None and hasattr(self, "_soa_id_map"):
            try:
                self._update_morph_collisions()
            except Exception:
                pass
        self._enforce_food_law()
        self._update_corpses()
        self._update_settlements()
        self._record_phase("society", (time.perf_counter() - _ph_society) * 1000.0)
        # BA: micro-neural — always on (60Hz physics, 15Hz inference every 4th tick)
        _ph_soa = time.perf_counter()
        if _agent_soa is not None and _neural_engine is not None:
            try:
                if self._soa is None:
                    # lazy init SoA with current creatures
                    self._soa = _agent_soa.AgentSoA(capacity=max(2000, len(self._cached_creatures) * 2 + 10))
                    self._nn_grid = _spatial_grid.SpatialHashGrid(width=self.config.width, height=self.config.height, cell_size=32.0, boundary=self.config.boundary)
                    for c in self._cached_creatures:
                        # BH-1 morph — check pending cache first (slots fix), then legacy attrs
                        _mr = _ma = _mk = None
                        if hasattr(self, "_morph_cache") and c.id in self._morph_cache:
                            _mr, _ma, _mk = self._morph_cache[c.id]  # type: ignore
                        else:
                            _mr = getattr(c, "_bc_morph_r", None)
                            _ma = getattr(c, "_bc_morph_phi", None)
                            _mk = getattr(c, "_bc_morph_k", None)
                        if _mr is None and _evo_mgr is not None and getattr(c, "caste", None):
                            try:
                                _tr, _tphi, _tk = _evo_mgr.get_template_for_caste(c.caste)
                                _mr = list(_tr)
                                _ma = list(_tphi)
                                _mk = int(_tk)
                                if hasattr(self, "_morph_cache"):
                                    self._morph_cache[c.id] = (list(_mr), list(_ma), int(_mk))
                            except Exception:
                                pass
                        self._soa.add_agent(int(c.id), float(c.x), float(c.y), angle=float(c.angle), energy=float(c.energy), health=float(c.health), morph_radii=_mr, morph_angles=_ma, morph_k=_mk, caste=getattr(c, "caste", None), sides=getattr(c, "sides", None))
                    self._soa_id_map = {c.id: idx for idx, c in enumerate(self._cached_creatures)}
                    # init genomes — carry over any cached NN genomes
                    if _evolution is not None:
                        _evolution.init_genomes(self._soa, rng=self.config.seed)
                        # apply any pending NN cache for founders
                        if hasattr(self, "_nn_cache") and self._nn_cache:
                            try:
                                for c in self._cached_creatures:
                                    if c.id in self._nn_cache:
                                        idx = self._soa_id_map.get(c.id)
                                        if idx is not None:
                                            self._soa.genomes[idx] = self._nn_cache[c.id]  # type: ignore
                            except Exception:
                                pass
                # BJ-1: incremental slot management — O(delta) births/deaths, in-place moves.
                if getattr(self, "_soa", None) is not None and self._soa is not None:
                    try:
                        self._sync_soa_incremental()
                    except Exception:
                        pass
                    # 15Hz inference every 4th tick
                    self._nn_tick = getattr(self, "_nn_tick", 0) + 1
                    if self._nn_tick % 4 == 0:
                        try:
                            from ..agent_pipeline import build_inputs_batch, apply_outputs_batch
                            from ..neural_engine import forward_batch

                            inputs = build_inputs_batch(self._soa, spatial_grid=self._nn_grid, world=self.world)
                            hidden = self._soa.hidden_state[: self._soa.N] if _agent_soa.HAS_NUMPY else None
                            outputs, _ = forward_batch(inputs, self._soa.genomes[: self._soa.N] if _agent_soa.HAS_NUMPY else [self._soa.genomes[i] for i in range(self._soa.N)], hidden_state=self._soa.hidden_state[: self._soa.N] if _agent_soa.HAS_NUMPY else None)
                            apply_outputs_batch(self._soa, outputs)
                            # PERF (no logic change): snapshot outputs as plain
                            # lists once per inference. outputs_buf is written
                            # ONLY here (swap-with-last/add never touch it),
                            # so per-creature tolist() reads below see the
                            # identical values — including the same staleness
                            # for swapped slots.
                            try:
                                self._nn_out_cache = outputs.tolist() if hasattr(outputs, "tolist") else [list(r) for r in outputs]  # type: ignore[attr-defined]
                            except Exception:
                                self._nn_out_cache = None  # type: ignore[attr-defined]
                        except Exception as _e:
                            # BA must never break the tick
                            pass
            except Exception:
                pass
        try:
            self._record_phase("soa_nn", (time.perf_counter() - _ph_soa) * 1000.0)
        except Exception:
            pass
        # Manual GC every 200 ticks to avoid stop-the-world at 1300c
        if self.tick % 200 == 0:
            gc.collect(1)
        # Log slow ticks for N150 profiling (over 150ms)
        dur = time.perf_counter() - t_step0
        if dur > 0.15:
            print(f"[sim] slow tick={self.tick} {dur*1000:.1f}ms c={len(self._cached_creatures)} food={len(self._cached_foods)} houses={len(self._cached_houses)}", flush=True)
        self.tick += 1
        # BJ-3: throttle telemetry to 2 Hz in production — O(N) ring aggregation
        # no longer runs on the hot path every tick. Unit tests (_IS_TEST) keep
        # every-tick sampling so velocity/counter assertions stay deterministic.
        # 1 Hz WS broadcast is still served from the cached analytics.summary().
        try:
            if getattr(self, "_analytics", None) is not None:
                if _IS_TEST:
                    self._analytics.on_tick(self)  # type: ignore[attr-defined]
                else:
                    _tele_hz = max(1, int(float(getattr(self.config, "tick_rate", 10.0)) // 2))
                    if self.tick % _tele_hz == 0:
                        self._analytics.on_tick(self)  # type: ignore[attr-defined]
        except Exception:
            pass

    # ---------------------------------------------------------------- society
    @staticmethod
    def _update_morph_collisions(self) -> None:
        """BC.6.1 SAT narrowphase — broadphase via spatial hash, narrowphase SAT, impulse & Dmult damage."""
        if not getattr(self.config, "morphology_annealing_enabled", True):
            return
        if getattr(self, "_soa", None) is None or _morphology is None:
            return
        soa = self._soa
        N = getattr(soa, "N", 0)
        if N < 2:
            return
        # broadphase radius = max r
        try:
            import math as _m
            # BJ-5: OpenMP sweep broadphase when gated on (single batch call,
            # GIL released); shared narrowphase below keeps the law identical.
            if (
                getattr(self.config, "omp_enabled", False)
                and _native_core is not None
                and hasattr(_native_core, "native_collision_sweep")
                and N >= max(32, int(getattr(self.config, "omp_threshold", 100) or 100))
            ):
                try:
                    _sx: list[float] = []
                    _sy: list[float] = []
                    _sr: list[float] = []
                    _sids: list[int] = []
                    for _idx in range(N):
                        try:
                            _eid = int(soa.ids[_idx])  # type: ignore
                        except Exception:
                            continue
                        _ent = self.world.entities.get(_eid)
                        if _ent is None or not isinstance(_ent, Creature):
                            continue
                        try:
                            _k = int(soa.morph_k[_idx])  # type: ignore
                            _rr = soa.morph_radii[_idx]  # type: ignore
                            if hasattr(_rr, "max"):
                                _rmax = float(_rr[:_k].max()) if _k > 0 else 1.0
                            else:
                                _rmax = float(max(_rr[:_k])) if _k > 0 else 1.0
                        except Exception:
                            _rmax = 1.0
                        _sx.append(float(_ent.x))
                        _sy.append(float(_ent.y))
                        _sr.append(float(_rmax) + 2.5)
                        _sids.append(int(_eid))
                    if _sids:
                        _sweep = _native_core.native_collision_sweep(  # type: ignore
                            _sx, _sy, _sr, _sids,
                            float(self.config.width), float(self.config.height),
                            self.config.boundary == "wrap",
                        )
                        _id2idx = getattr(self, "_soa_id_map", {}) or {}
                        for _a, _b in _sweep:
                            _i = _id2idx.get(_a)
                            _jj = _id2idx.get(_b)
                            if _i is None or _jj is None or _i == _jj:
                                continue
                            if _jj < _i:
                                _i, _jj = _jj, _i
                            _morph_sat_pair(self, soa, int(_i), int(_jj))
                        return
                except Exception:
                    pass
            # Build id->idx map already
            # Query each creature's neighbors via world spatial query using bounding radius
            for idx in range(N):
                if not soa.active_mask[idx] if hasattr(soa.active_mask, "__getitem__") else not soa.active_mask[idx]:
                    continue
                # world creature for position
                eid = int(soa.ids[idx]) if hasattr(soa.ids, "__getitem__") else -1
                ent = self.world.entities.get(eid)
                if ent is None or not isinstance(ent, Creature):
                    continue
                # r_max = max radii
                try:
                    if hasattr(soa.morph_radii, "shape"):
                        rmax = float(soa.morph_radii[idx, : int(soa.morph_k[idx])].max()) if int(soa.morph_k[idx]) > 0 else 1.0
                    else:
                        k = int(soa.morph_k[idx])
                        rmax = max(soa.morph_radii[idx][:k]) if k else 1.0
                except Exception:
                    rmax = 1.0
                # broadphase query
                for other, _d2 in self.world.query_radius_with_dist_sq(ent.x, ent.y, rmax + 3.0):
                    if not isinstance(other, Creature) or other.id == eid:
                        continue
                    j = getattr(self, "_soa_id_map", {}).get(other.id)
                    if j is None or j <= idx:  # avoid double
                        continue
                    try:
                        _morph_sat_pair(self, soa, idx, j)
                    except Exception:
                        continue
        except Exception:
            pass









    # ------------------------------------------------- §AC desperation cannibalism
    def clan_knowledge(self) -> dict[int, dict]:
        """§X Clan memory — union of member knowledge: 'the clan remembers'."""
        ttl = max(1, self.config.knowledge_ttl)
        out: dict[int, dict] = {}
        clan_creatures = self._clan_members if self._clan_members else {}
        if not clan_creatures:
            for m in self._get_creatures():
                if m.clan_id:
                    clan_creatures.setdefault(m.clan_id, []).append(m)
        # §P0: only alive clans carry memory — dead clans bloat payloads
        alive_for_know = set(self._clan_members.keys()) if self._clan_members else {c.clan_id for c in self._get_creatures() if c.clan_id}
        for cid in alive_for_know:
            enemies: set[int] = set()
            danger: list[dict] = []
            food: list[dict] = []
            safe_spots = 0
            for m in clan_creatures.get(cid, ()):
                for clan_id, meta in (m.facts.get("enemies") or {}).items():
                    if isinstance(meta, dict) and self.tick - int(meta.get("tick", 0)) <= ttl:
                        enemies.add(int(clan_id))
                for kind, sink in (("danger", danger), ("food", food)):
                    f = self._fact_fresh(m, kind)
                    if f is None or "x" not in f or len(sink) >= 6:
                        continue
                    if any(
                        math.hypot(f["x"] - e["x"], f["y"] - e["y"]) < 2.0
                        for e in sink
                    ):
                        continue  # same spot another member already reported
                    sink.append({"x": f["x"], "y": f["y"], "conf": f["conf"]})
                if self._fact_fresh(m, "safe") is not None:
                    safe_spots += 1
            enemies.discard(cid)
            out[cid] = {
                "enemy_clans": sorted(enemies),
                "danger_zones": danger,
                "food_spots": food,
                "members_with_home_knowledge": safe_spots,
            }
        return out


    # ------------------------------------------------------------------ flora



    # ------------------------------------------------------------ §AM agriculture







    # ---------------------------------------------------------------- disease
    def _emit(self, event: HistoryEvent) -> None:
        self.history.append(event)
        # AA: pre-dump once at source — snapshot_payload reads plain dicts directly,
        # eliminating per-frame Pydantic model_dump() on the broadcast hot path.
        self._events_this_tick.append(event.model_dump(mode="json"))
        if event.type == "war":
            w = event.payload.get("b")
            l = event.payload.get("a")
            if w and l and w != l:
                w_cid, l_cid = int(w), int(l)
                self._clan_war_wins[w_cid] = self._clan_war_wins.get(w_cid, 0) + 1
                self._clan_war_losses[l_cid] = self._clan_war_losses.get(l_cid, 0) + 1
                if w_cid in self.clans:
                    self.clans[w_cid]["war_wins"] = self._clan_war_wins[w_cid]
                if l_cid in self.clans:
                    self.clans[l_cid]["war_losses"] = self._clan_war_losses[l_cid]
        if self.on_event is not None:
            self.on_event(event)

    def _infect(self, c: Creature) -> None:
        c.infected = True
        c.disease_id = self.disease_id


    # ----------------------------------------------------------- reproduction








    # ------------------------------------------------------------------ output















