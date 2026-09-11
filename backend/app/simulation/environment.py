"""Environment mixin — sky/weather, wind, temperature, elevation, rivers, seismic, lightning, traffic, anomalies, fires, campfires, disasters, builders (BI-5)."""

from __future__ import annotations

import gc
import math
import operator
import os
import random
import time
from collections import deque
from functools import lru_cache
from typing import Any, Callable, cast

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

try:
    from .. import native_core as _native_core  # type: ignore
except Exception:
    _native_core = None  # type: ignore
try:
    from .. import parallel as _parallel  # type: ignore
except Exception:
    _parallel = None  # type: ignore
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

from .constants import *
from .constants import _season_food_mult, _clan_sig, personal_name_for, glyph_for, variation_for

class EnvironmentMixin:
    def _time_of_day(self) -> float:
        """0=midnight, 0.25=sunrise, 0.5=noon, 0.75=sunset; world starts at sunrise."""
        dl = max(1, self.config.day_length)
        return ((self.tick + 0.25 * dl) % dl) / dl

    def _is_night(self, tod: float) -> bool:
        return tod < 0.22 or tod > 0.78

    def _season(self) -> str:
        # §BF-5 autumn start: offset season index so day 0 can be autumn (2) not spring (0)
        offset = int(getattr(self.config, "initial_season_offset", 0) or 0)
        return SEASONS[((self.tick // max(1, self.config.season_length)) + offset) % 4]

    def _age(self) -> str | None:
        if not self.config.age_enabled:
            return None
        idx = (self.tick // max(1, self.config.age_length)) % len(AGES)
        return AGES[idx]

    def _age_tick(self) -> int:
        if not self.config.age_enabled:
            return 0
        return self.tick % max(1, self.config.age_length)

    def _age_day(self) -> int:
        if not self.config.age_enabled:
            return 1
        dl = max(1, self.config.day_length)
        return (self._age_tick() // dl) + 1

    def _age_total_days(self) -> int:
        if not self.config.age_enabled:
            return 1
        dl = max(1, self.config.day_length)
        return max(1, self.config.age_length // dl)

    @property
    def day(self) -> int:
        return self.tick // max(1, self.config.day_length) + 1

    def _update_weather(self) -> None:
        cfg = self.config
        if not cfg.weather_enabled or self.rng.random() >= cfg.weather_change_rate:
            return
        others = [w for w in WEATHER_STATES if w != self.weather]
        self.weather = self.rng.choice(others)
        # §AR S-6: high castes read the sky the moment it turns
        self._weather_since_tick = self.tick
        # §AQ PH-2: a new sky brings a new wind — direction re-rolls near the
        # season's prevailing bearing.
        self.wind_angle = (
            WIND_SEASON_BIAS[self._season()] + self.rng.uniform(-1.0, 1.0)
        ) % (2 * math.pi)

    def _update_wind(self) -> None:
        """§AQ PH-2: the wind's strength follows the sky — storms howl, calm
        days barely stir the grass."""
        target = {
            "storm": WIND_STORM_SPEED,
            "rain": WIND_RAIN_SPEED,
        }.get(self.weather, WIND_CALM_SPEED)
        self.wind_speed += (target - self.wind_speed) * WIND_RATE
        self._sync_wind_cache()

    def _sync_wind_cache(self) -> None:
        """§AU O-1: keep the precomputed wind trig honest even when a test (or
        a future system) mutates wind_angle between ticks."""
        if getattr(self, "_wind_cached_for", None) != self.wind_angle:
            self._cos_wind = math.cos(self.wind_angle)
            self._sin_wind = math.sin(self.wind_angle)
            self._wind_cached_for = self.wind_angle

    def env_sight_mult(self) -> float:
        """Night and fog dim every eye (Sight Recognition suffers)."""
        cfg = self.config
        m = 1.0
        if self._is_night(self._time_of_day()):
            m *= cfg.night_sight_mult
        if self.weather == "fog":
            m *= cfg.fog_sight_mult
        return m

    def env_speed_mult(self) -> float:
        return self.config.rain_speed_mult if self.weather in ("rain", "storm") else 1.0

    def _update_temperature(self) -> None:
        """§AQ PH-1 heat field: each cell relaxes toward its target — the
        seasonal base swept across the map from an edge, bent by the day
        cycle, weather, and any open flame."""
        cfg = self.config
        sl = max(1, cfg.season_length)
        p = (self.tick % sl) / sl  # progress through the current season
        s_idx = SEASONS.index(self._season())
        cur = SEASON_BASE_TEMP[SEASONS[s_idx]]
        nxt = SEASON_BASE_TEMP[SEASONS[(s_idx + 1) % 4]]
        cold_front = nxt < cur  # cold enters from the west, warmth from the east
        diurnal = DAY_HEAT_AMPLITUDE * (self._sun_factor() * 2.0 - 1.0)
        weather_bump = {"rain": -2.0, "storm": -3.0, "fog": -1.0}.get(self.weather, 0.0)
        w_cols = self._temp_cols
        for row in range(self._temp_rows):
            for col in range(w_cols):
                xn = (col + 0.5) / w_cols
                if cold_front:
                    sweep = min(1.0, max(0.0, p * 1.6 - xn * 0.6))
                else:
                    sweep = min(1.0, max(0.0, p * 1.6 - (1.0 - xn) * 0.6))
                target = cur + (nxt - cur) * sweep + diurnal + weather_bump
                i = row * w_cols + col
                self.temperature_grid[i] += (target - self.temperature_grid[i]) * TEMP_RATE
        # Open flame dominates its neighbourhood (circle-vs-cell overlap).
        if self.fires:
            cell_w = cfg.width / w_cols
            cell_h = cfg.height / self._temp_rows
            for f in self.fires:
                c0 = max(0, int((f["x"] - FIRE_HEAT_RADIUS) / cell_w))
                c1 = min(w_cols - 1, int((f["x"] + FIRE_HEAT_RADIUS) / cell_w))
                r0 = max(0, int((f["y"] - FIRE_HEAT_RADIUS) / cell_h))
                r1 = min(self._temp_rows - 1, int((f["y"] + FIRE_HEAT_RADIUS) / cell_h))
                for row in range(r0, r1 + 1):
                    for col in range(c0, c1 + 1):
                        qx = min(max(f["x"], col * cell_w), (col + 1) * cell_w)
                        qy = min(max(f["y"], row * cell_h), (row + 1) * cell_h)
                        dx = qx - f["x"]
                        dy = qy - f["y"]
                        if dx * dx + dy * dy <= FIRE_HEAT_RADIUS * FIRE_HEAT_RADIUS:
                            i = row * w_cols + col
                            self.temperature_grid[i] += (FIRE_HEAT - self.temperature_grid[i]) * TEMP_RATE

    def ambient_at(self, x: float, y: float) -> float:
        """Ambient temperature at a point on the heat field (§AQ PH-1)."""
        inv_w = getattr(self, "_temp_cols_inv_w", None)
        if inv_w is None:
            self._temp_cols_inv_w = inv_w = self._temp_cols / max(1.0, float(self.config.width))
            self._temp_rows_inv_h = self._temp_rows / max(1.0, float(self.config.height))
        col = min(self._temp_cols - 1, max(0, int(x * inv_w)))
        row = min(self._temp_rows - 1, max(0, int(y * self._temp_rows_inv_h)))
        t = self.temperature_grid[row * self._temp_cols + col]
        # §AO E: a field campfire warms its circle of light.
        if self.campfires:
            cf_r2 = CAMPFIRE_LIGHT_RADIUS * CAMPFIRE_LIGHT_RADIUS
            for cf in self.campfires:
                dx = x - cf["x"]
                dy = y - cf["y"]
                if dx * dx + dy * dy <= cf_r2:
                    t = max(t, CAMPFIRE_HEAT)
        return t

    def indoor_ambient(self, house: House) -> float:
        """Inside air: insulation pulls the room toward comfort; bigger floors
        shed heat faster (perimeter/area bites in 2D). A lit hearth (§AQ PH-1)
        pulls the room past comfort toward hearth-warm."""
        ins = INSULATION_BY_MATERIAL.get(house.material, INSULATION_BY_MATERIAL["wood"])
        size_factor = max(0.4, min(1.0, HOUSE_REF_SIDE / max(1.0, house.size)))
        amb = self.ambient_at(house.x, house.y)
        indoor = amb + (HOUSE_COMFORT_TEMP - amb) * ins * size_factor
        if getattr(house, "hearth_lit", False):
            indoor += (HEARTH_COMFORT_TEMP - indoor) * HEARTH_PULL * size_factor
        return indoor

    def _update_hearths(self) -> None:
        """§AQ PH-1: hearths — permanent fire installations inside claimed
        houses. Kin buy fuel from the clan larder when the roof (or the cold)
        calls for it; the pile burns down every tick and an unfed hearth goes
        dark. Winter survival infrastructure."""
        if not self.config.hearths_enabled:
            for h in self._cached_houses:
                if h.hearth_lit:  # withdraw the law — every flame gutters out
                    h.hearth_lit = False
                    h.hearth_fuel = 0.0
            return
        tod = self._time_of_day()
        want_warmth = (
            self._season() in ("autumn", "winter")
            or self._is_night(tod)
            or self.weather in ("rain", "storm")
        )
        # Burn first — every lit hearth eats its woodpile this tick.
        for h in self._cached_houses:
            if not h.hearth_lit:
                continue
            h.hearth_fuel -= HEARTH_BURN_RATE
            if h.hearth_fuel <= 0.0:
                h.hearth_fuel = 0.0
                h.hearth_lit = False
        if not want_warmth or self.tick % HEARTH_REFUEL_INTERVAL != 0:
            return
        # Kin at home top up the hearth from the clan larder.
        members_by_clan: dict[int, list[Creature]] = {}
        for c in self._cached_creatures:
            if c.clan_id:
                members_by_clan.setdefault(c.clan_id, []).append(c)
        reach_sq: dict[float, float] = {}
        for h in self._cached_houses:
            if h.is_ruin or not h.clan_id:
                continue
            kin = members_by_clan.get(h.clan_id)
            if not kin:
                continue
            r2 = (h.size * 0.5 + 3.0) ** 2
            near = False
            for c in kin:
                dx, dy = self.world.delta(c.x, c.y, h.x, h.y)
                if dx * dx + dy * dy <= r2:
                    near = True
                    break
            if not near:
                continue
            clan = self.clans.get(h.clan_id)
            if clan is None:
                continue
            # people eat before fire burns: a clan with starving members
            # never feeds the hearth (the Ice age taught this the hard way)
            emax = self.config.energy_max or 1.0
            if any(k.energy / emax <= self.config.starving_ratio for k in kin):
                continue
            stored = float(clan.get("larder", 0.0))
            if stored < HEARTH_REFUEL_CHUNK:
                continue  # the larder is bare — the hearth dies tonight
            take = min(HEARTH_REFUEL_CHUNK, stored,
                       max(0.0, (HEARTH_FUEL_MAX - h.hearth_fuel)) / HEARTH_FUEL_PER_ENERGY)
            if take <= 0:
                continue
            clan["larder"] = stored - take
            h.hearth_fuel = min(HEARTH_FUEL_MAX, h.hearth_fuel + take * HEARTH_FUEL_PER_ENERGY)
            h.hearth_lit = True

    def _generate_elevation(self) -> None:
        """§AQ PH-4: a smooth height field from seeded sinusoids (a dedicated
        geography rng — the shape of the land never perturbs the life stream),
        normalized to 0..1 across ELEV_MAX_HEIGHT world-units of relief."""
        if not self.config.relief_enabled:
            return
        geo_rng = random.Random((self.config.seed * 77017) ^ 0x5EED1A)
        w, h = self.config.width, self.config.height
        waves = []
        for _ in range(4):
            fx = geo_rng.uniform(1.0, 4.0) * math.tau / max(w, 1.0)
            fy = geo_rng.uniform(1.0, 4.0) * math.tau / max(h, 1.0)
            px = geo_rng.uniform(0, math.tau)
            py = geo_rng.uniform(0, math.tau)
            amp = geo_rng.uniform(0.6, 1.4)
            waves.append((amp, fx, fy, px, py))
        vals = []
        for row in range(self._elev_rows):
            for col in range(self._elev_cols):
                x = (col + 0.5) * w / self._elev_cols
                y = (row + 0.5) * h / self._elev_rows
                v = 0.0
                for amp, fx, fy, px, py in waves:
                    v += amp * math.sin(fx * x + px) * math.sin(fy * y + py)
                vals.append(v)
        lo, hi = min(vals), max(vals)
        span = (hi - lo) or 1.0
        self.elev_grid = [round((v - lo) / span, 4) for v in vals]
        # §AQ PH-4 smooth: 2-pass 3x3 blur cuts cliff edges from ~22% to <5% while
        # preserving overall relief shape; plateau test (1.0 vs 0.0) stays a cliff.
        for _ in range(2):
            blurred: list[float] = []
            for r in range(self._elev_rows):
                for c in range(self._elev_cols):
                    s = 0.0
                    n = 0
                    for dr in (-1, 0, 1):
                        nr = r + dr
                        if nr < 0 or nr >= self._elev_rows:
                            continue
                        base = nr * self._elev_cols
                        for dc in (-1, 0, 1):
                            nc = c + dc
                            if 0 <= nc < self._elev_cols:
                                s += self.elev_grid[base + nc]
                                n += 1
                    blurred.append(s / n if n else self.elev_grid[r * self._elev_cols + c])
            self.elev_grid = blurred
        # re-normalize after blur to restore 0..1 extremes for the bounded test
        lo2, hi2 = min(self.elev_grid), max(self.elev_grid)
        span2 = (hi2 - lo2) or 1.0
        self.elev_grid = [round((v - lo2) / span2, 4) for v in self.elev_grid]
        try:
            import ctypes
            self._elev_c_buf = (ctypes.c_float * len(self.elev_grid))(*self.elev_grid)
        except Exception:
            self._elev_c_buf = None
        # Precalculate dimension ratios for hot-path bilinear interpolation
        self._elev_inv_w_cols = self._elev_cols / max(self.config.width, 1.0)
        self._elev_inv_h_rows = self._elev_rows / max(self.config.height, 1.0)
        # PERF (no logic change): python bilinear is faster than a ctypes
        # round-trip per call (13.6k calls/tick); keep the native symbol only
        # as an emergency fallback. Same math, deterministic.
        self._elev_use_native = False

    def _elev_at(self, x: float, y: float) -> float:
        """Normalised ground height (0..1) under a point; 0.5 flat worlds.
        Bilinear between cell centres — the land is smooth, so ordinary travel
        never trips the cliff threshold (only true escarpments do).
        §AU O-1: closure inlined — clamped grid reads straight off the buffer."""
        if not self.config.relief_enabled:
            return 0.5
        if self._elev_use_native:
            return _native_core.native_elev_at(
                x, y, self._elev_c_buf, self._elev_cols, self._elev_rows, self.config.width, self.config.height
            )
        cols = self._elev_cols
        rows = self._elev_rows
        grid = self.elev_grid
        inv_w = getattr(self, "_elev_inv_w_cols", None)
        if inv_w is None:
            inv_w = cols / max(self.config.width, 1.0)
            self._elev_inv_w_cols = inv_w
            self._elev_inv_h_rows = rows / max(self.config.height, 1.0)
        inv_h = self._elev_inv_h_rows
        gx = x * inv_w - 0.5
        gy = y * inv_h - 0.5
        c0 = int(gx) if gx >= 0 else int(gx) - 1
        r0 = int(gy) if gy >= 0 else int(gy) - 1
        fx = gx - c0
        fy = gy - r0
        cc0 = 0 if c0 < 0 else (cols - 1 if c0 > cols - 1 else c0)
        cc1 = 0 if c0 + 1 < 0 else (cols - 1 if c0 + 1 > cols - 1 else c0 + 1)
        rr0 = 0 if r0 < 0 else (rows - 1 if r0 > rows - 1 else r0)
        rr1 = 0 if r0 + 1 < 0 else (rows - 1 if r0 + 1 > rows - 1 else r0 + 1)
        h00 = grid[rr0 * cols + cc0]
        h10 = grid[rr0 * cols + cc1]
        h01 = grid[rr1 * cols + cc0]
        h11 = grid[rr1 * cols + cc1]
        top = h00 * (1.0 - fx) + h10 * fx
        bot = h01 * (1.0 - fx) + h11 * fx
        return top * (1.0 - fy) + bot * fy

    def _elev_cell_units(self, x: float, y: float) -> float:
        """Nearest-cell height in world-units — the RAW terraced field, used
        only for cliff detection: a cell-boundary drop this steep is a cliff."""
        inv_w = getattr(self, "_elev_inv_w_cols", None)
        if inv_w is None:
            inv_w = self._elev_cols / max(self.config.width, 1.0)
            self._elev_inv_w_cols = inv_w
            self._elev_inv_h_rows = self._elev_rows / max(self.config.height, 1.0)
        col = min(self._elev_cols - 1, max(0, int(x * inv_w)))
        row = min(self._elev_rows - 1, max(0, int(y * self._elev_inv_h_rows)))
        return self.elev_grid[row * self._elev_cols + col] * ELEV_MAX_HEIGHT

    def _elev_units(self, x: float, y: float) -> float:
        """Ground height in world-units (bodies and water care about these)."""
        return self._elev_at(x, y) * ELEV_MAX_HEIGHT

    def _terrain_effects(self, c: Creature, px: float, py: float) -> None:
        """§AQ PH-4 applied to one body after it moves: uphill grade bleeds
        energy and slows the stride, cliffs hurt, feet pack roads, and rain
        loosens steep slopes into landslides."""
        cfg = self.config
        if not cfg.relief_enabled:
            return
        # traffic: this body just packed the earth it stands on
        tcol = min(self._temp_cols - 1, max(0, int(c.x / cfg.width * self._temp_cols)))
        trow = min(self._temp_rows - 1, max(0, int(c.y / cfg.height * self._temp_rows)))
        ti = trow * self._temp_cols + tcol
        self.traffic_grid[ti] += TRAFFIC_PER_PASS
        # grade along the step just taken — smooth bilinear field: ordinary
        # ground never trips the cliff; only terraced cell drops do
        dxg, dyg = self.world.delta(px, py, c.x, c.y)
        dist = math.hypot(dxg, dyg)
        if dist < 1e-6:
            return
        # §AQ PH-4 cliff check first — terraced drop is law, not smooth grade.
        # Cooldown prevents a tumbling chain from shredding the same body.
        if getattr(c, "fall_cooldown", 0) <= 0:
            cell_drop = (
                self._elev_cell_units(px, py) - self._elev_cell_units(c.x, c.y)
            )
            if cell_drop >= CLIFF_DROP_UNITS:
                excess = cell_drop - CLIFF_DROP_UNITS
                dmg = FALL_DAMAGE_PER_UNIT * (excess + CLIFF_DROP_UNITS * 0.5)
                # Barrier: the edge stops the body — revert, turn, stumble.
                # Keeps the lethal-plateau test (60-unit drop) lethal, but
                # ordinary 15-20-unit steps become a bruise, not a grave.
                c.x, c.y = px, py
                c.angle += math.pi + self.rng.uniform(-0.6, 0.6)
                c.fall_cooldown = FALL_COOLDOWN_TICKS
                c.pause_ticks = max(getattr(c, "pause_ticks", 0), 6)
                c.wound_ticks = max(getattr(c, "wound_ticks", 0), 30)
                c.wound_severity = max(getattr(c, "wound_severity", 0), 1)
                if not c.emote:
                    c.emote = "panic"
                    c.emote_ticks = 12
                if c.health - dmg <= 0:
                    self._kill(c, "fall")
                else:
                    c.health -= dmg
                    # stumble drains a little energy too
                    c.energy = max(0.0, c.energy - 4.0)
                # cliff handled — don't also charge uphill energy on same step
                return
        rise = self._elev_units(c.x, c.y) - self._elev_units(px, py)  # >0 climbed
        grade = rise / dist  # >0 climbing
        if grade > 0:
            c.energy = max(0.0, c.energy - SLOPE_ENERGY_COST * grade)
        # avalanche: rain loosens genuinely steep ground underfoot — measured
        # from the terraced field's local cell grade, not the step just taken
        if self.weather in ("rain", "storm") and self.rng.random() < AVALANCHE_CHANCE:
            ecol = min(self._elev_cols - 1, max(0, int(c.x / cfg.width * self._elev_cols)))
            erow = min(self._elev_rows - 1, max(0, int(c.y / cfg.height * self._elev_rows)))
            here = self.elev_grid[erow * self._elev_cols + ecol]
            best_drop = 0.0
            slide_dx = slide_dy = 0.0
            for ddc, ddr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nc = min(self._elev_cols - 1, max(0, ecol + ddc))
                nr = min(self._elev_rows - 1, max(0, erow + ddr))
                drop = here - self.elev_grid[nr * self._elev_cols + nc]  # >0 downhill
                if drop > best_drop:
                    best_drop = drop
                    slide_dx, slide_dy = float(ddc), float(ddr)
            if best_drop * ELEV_MAX_HEIGHT / ELEV_CELL >= AVALANCHE_SLOPE:
                push = 8.0
                c.x, c.y = self.world.normalize(
                    c.x + slide_dx * push, c.y + slide_dy * push
                )
                dmg = self.rng.uniform(8.0, 20.0)
                if c.health - dmg <= 0:
                    self._kill(c, "landslide")
                else:
                    c.health -= dmg

    def _road_speed_mult(self, x: float, y: float) -> float:
        """Packed earth is fast going (§AQ PH-4 emergent roads)."""
        col = min(self._temp_cols - 1, max(0, int(x / self.config.width * self._temp_cols)))
        row = min(self._temp_rows - 1, max(0, int(y / self.config.height * self._temp_rows)))
        traffic = self.traffic_grid[row * self._temp_cols + col]
        if traffic <= 0:
            return 1.0
        return 1.0 + min(ROAD_SPEED_CAP, traffic * ROAD_SPEED_PER_TRAFFIC)

    def _update_traffic(self) -> None:
        """Rain and grass slowly heal packed earth; roads need constant use.
        §AU O-2: the decay sweep runs every 10th tick with the compounded
        factor (`0.995**10`) — identical mathematics, a tenth of the work."""
        if not self.config.relief_enabled:
            return
        if self.tick % 10 != 0:
            return
        g = self.traffic_grid
        f = TRAFFIC_DECAY_STAGGERED
        for i in range(len(g)):
            if g[i] > 0:
                g[i] *= f
                if g[i] < 0.05:
                    g[i] = 0.0

    def _generate_rivers(self) -> None:
        """§AQ PH-3: seed the world's river channels — horizontal bands with a
        flow direction each, spaced down the map so every bank stays reachable.
        Runs before life spawns so houses and fields never root in the water.
        Draws from a dedicated rng so geography never perturbs the life stream."""
        if not self.config.rivers_enabled:
            return
        count = max(0, int(self.config.river_count))
        if count == 0:
            return
        geo_rng = random.Random((self.config.seed * 100003) ^ 0x9E3779B9)
        margin = 30.0
        usable = max(10.0, self.config.height - 2 * margin)
        for i in range(count):
            cy = (margin + usable * (i + 1 + geo_rng.uniform(-0.2, 0.2)) / (count + 1)) % self.config.height
            # water runs downhill: flow follows the east-west height gradient
            mid_x = self.config.width / 2
            probe = self.config.width / 8
            h_west = self._elev_units(mid_x - probe, cy)
            h_east = self._elev_units(mid_x + probe, cy)
            if h_west != h_east:
                direction = 1.0 if h_west > h_east else -1.0
            else:
                direction = 1.0 if geo_rng.random() < 0.5 else -1.0
            self.rivers.append({
                "cy": round(cy, 2),
                "hw": RIVER_BASE_HW,
                "base_hw": RIVER_BASE_HW,
                "dir": direction,
                "water": 0.0,
                "flood_ticks": 0,
                "silt_ticks": 0,
            })

    def _river_dy(self, y: float, cy: float) -> float:
        """Wrap-aware vertical distance to a channel centre line."""
        dy = abs(y - cy)
        return min(dy, self.config.height - dy)

    def _river_at(self, x: float, y: float) -> dict | None:
        """The channel band containing this point, if any."""
        for r in self.rivers:
            if self._river_dy(y, r["cy"]) <= r["hw"]:
                return r
        return None

    def _in_river_band(self, x: float, y: float, pad: float = 0.0) -> bool:
        """True when the point sits inside a channel plus margin — used by
        worldgen so houses never straddle the water."""
        for r in self.rivers:
            if self._river_dy(y, r["cy"]) <= r["hw"] + pad:
                return True
        return False

    def _on_bridge_or_dam(self, x: float, y: float) -> bool:
        """Crossings are dry: planks span the band at their post's x."""
        for b in self.bridges:
            dx = abs(x - b["x"])
            if dx > self.config.width / 2:
                dx = self.config.width - dx
            if dx <= BRIDGE_HALF_WIDTH and self._river_dy(y, b["cy"]) <= b["hw"] + 2.0:
                return True
        for d in self.dams:
            dx = abs(x - d["x"])
            if dx > self.config.width / 2:
                dx = self.config.width - dx
            r = next((r for r in self.rivers if r["cy"] == d["cy"]), None)
            if r is not None and dx <= BRIDGE_HALF_WIDTH and self._river_dy(y, r["cy"]) <= r["hw"] + 3.0:
                return True
        return False

    def _update_rivers(self) -> None:
        """§AQ PH-3: rain swells the channels; a full channel bursts its banks;
        floodwater widens the band, tears out plants and drowns the stubborn;
        receded water leaves fertile silt on the banks. Dams hold back floods
        until they fail. Planks rot; builders rebuild (see _update_builders)."""
        raining = self.weather in ("rain", "storm")
        for r in self.rivers:
            dam = next((d for d in self.dams if d["cy"] == r["cy"] and d["hp"] > 0), None)
            if raining:
                gain = RIVER_RAIN_RATE * (1.5 if self.weather == "storm" else 1.0)
                if dam is not None:
                    gain *= 0.5  # the dam drinks the crest
                r["water"] = min(1.5, r["water"] + gain)
            else:
                r["water"] = max(0.0, r["water"] - RIVER_DRY_RATE)
            # flood pressure grinds the masonry down — dams hold, then burst
            if dam is not None:
                if r["flood_ticks"] > 0 or (raining and r["water"] >= 1.0):
                    dam["hp"] -= DAM_STRESS_DAMAGE
            if r["flood_ticks"] <= 0 and r["water"] >= 1.0:
                r["flood_ticks"] = RIVER_FLOOD_TICKS
                r["water"] = 0.0
                last_flood = r.get("last_flood_event_tick", -1000)
                if self.tick - last_flood >= 600:
                    r["last_flood_event_tick"] = self.tick
                    self._emit(HistoryEvent(
                        type="disaster", tick=self.tick + 1, entity_id=0,
                        x=round(self.config.width / 2, 2), y=round(r["cy"], 2),
                        payload={"kind": "river_flood", "river_cy": r["cy"]},
                    ))
            if r["flood_ticks"] > 0:
                r["flood_ticks"] -= 1
                target_hw = RIVER_BASE_HW * RIVER_FLOOD_HW_MULT
                r["hw"] += (target_hw - r["hw"]) * RIVER_FLOOD_GROW
                # floodwater tears out rooted plants in the swollen band
                if self._cached_foods and self.tick % 5 == 0:
                    for f in list(self._cached_foods):
                        if self._river_dy(f.y, r["cy"]) <= r["hw"] and self.rng.random() < 0.25:
                            self.world.remove(f.id)
                if r["flood_ticks"] == 0:
                    r["silt_ticks"] = RIVER_SILT_TICKS  # the gift the water leaves
            else:
                r["hw"] += (r["base_hw"] - r["hw"]) * RIVER_FLOOD_EBB
            if r["silt_ticks"] > 0:
                r["silt_ticks"] -= 1
        # dams fail catastrophically when ground away under pressure
        for d in [d for d in self.dams if d["hp"] <= 0]:
            self.dams.remove(d)
            r = next((r for r in self.rivers if r["cy"] == d["cy"]), None)
            if r is not None:
                r["flood_ticks"] = max(r["flood_ticks"], RIVER_FLOOD_TICKS // 2)
                r["hw"] = min(RIVER_BASE_HW * RIVER_FLOOD_HW_MULT * DAM_FLASH_SPIKE, r["hw"] * DAM_FLASH_SPIKE)
                self._emit_boom(d["x"], d["cy"])
                self._emit(HistoryEvent(
                    type="disaster", tick=self.tick + 1, entity_id=0,
                    x=round(d["x"], 2), y=round(d["cy"], 2),
                    payload={"kind": "flash_flood", "river_cy": d["cy"]},
                ))
        # planks rot
        # planks rot gracefully (decay every 20 ticks for realistic longevity)
        for b in [b for b in self.bridges if b["hp"] <= 0]:
            self.bridges.remove(b)
        if self.tick % 20 == 0:
            for b in self.bridges:
                b["hp"] -= 1

    def _river_effects(self, c: Creature) -> None:
        """§AQ PH-3 applied to one body after it moves: wading costs gentle energy,
        bridges cross dry, current carries gentle downstream drift,
        cools overheating creatures, washes disease, and rewards river foraging."""
        r = self._river_at(c.x, c.y)
        if r is None or self._on_bridge_or_dam(c.x, c.y):
            return
        flooded = r["flood_ticks"] > 0
        c.energy = max(0.0, c.energy - (RIVER_FORD_COST * 1.5 if flooded else RIVER_FORD_COST))

        # 1. Hydration & Thermal Cooling: cool hyperthermia towards comfort 20°C
        if getattr(c, "body_temp", 20.0) > 20.5:
            c.body_temp = max(20.0, getattr(c, "body_temp", 20.0) - 0.4)
        # 2. Hygiene & Cleanliness: freshwater washes contagion risk
        if getattr(c, "infected", False) and self.rng.random() < 0.02:
            c.infected = False  # river bath washes sickness
            c.emote = "cheer"
            c.emote_ticks = 15
        if getattr(c, "chill", 0.0) > 0 and self.weather not in ("rain", "storm", "snow"):
            c.chill = max(0.0, c.chill - 0.1)

        # 3. Downstream current drift without locking creature's steering angle
        weak = c.stage == "infant" or c.health < RIVER_SWEEP_HEALTH
        if weak or flooded:
            push = RIVER_SWEEP_SPEED * (1.5 if flooded else 0.8) * (0.5 if not weak else 1.0)
            nx = c.x + r["dir"] * push
            ny = c.y + (self.rng.uniform(-0.05, 0.05) if not weak else 0.0)
            c.x, c.y = self.world.normalize(nx, ny)
            # Gentle drift nudge rather than 100% hard override:
            if weak and self.rng.random() < 0.2:
                current_ang = 0.0 if r["dir"] > 0 else math.pi
                diff = (current_ang - c.angle + math.pi) % (2 * math.pi) - math.pi
                c.angle += max(-0.2, min(0.2, diff))

        # 4. Flood water damage: survival skill softens damage
        if flooded:
            soften = 1.0 / (1.0 + c.skills.get("foraging", 0.0) / 20.0)
            dmg = RIVER_DROWN_DAMAGE * soften * 0.2
            if c.health - dmg <= 0:
                self._kill(c, "drowning")
            else:
                c.health -= dmg

    def _update_structures(self) -> None:
        """§AQ PH-6: material physics — storms and floodwater wear buildings
        down, builders mend what still stands, collapsed roofs leave rubble
        that blocks the lot until it is cleared."""
        cfg = self.config
        houses = self._cached_houses or self._functional_houses()
        # wear
        for h in houses:
            if h.is_ruin:
                continue
            if h.hp < 0:
                h.hp = MATERIAL_STATS.get(h.material, MATERIAL_STATS["wood"])["durability"]
            if not cfg.structural_enabled:
                continue
            wear = 0.0
            if self.weather == "storm":
                wear += STORM_WEAR
            for r in self.rivers:
                if (
                    r["flood_ticks"] > 0
                    and self._river_dy(h.y, r["cy"]) <= r["hw"] + h.size * 0.5 + 2.0
                ):
                    wear += FLOOD_WEAR
            if wear > 0:
                h.hp -= wear
                if h.hp <= 0:
                    self._collapse_house(h)
        # repair & rubble clearing — builders within reach of a roof work it
        if cfg.structural_enabled or cfg.rubble_blocking_enabled:
            builders = [c for c in self._cached_creatures
                        if getattr(c, "personality", "") == "builder"]
            for c in builders:
                for h in houses:
                    dx, dy = self.world.delta(c.x, c.y, h.x, h.y)
                    reach = h.size * 0.5 + 3.0
                    if dx * dx + dy * dy > reach * reach:
                        continue
                    if h.is_ruin:
                        if cfg.rubble_blocking_enabled and h.rubble > 0:
                            h.rubble = max(0.0, h.rubble - 0.10)
                            c.energy = max(0.0, c.energy - 0.05)
                            if h.rubble == 0.0:
                                self.world.remove(h.id)  # lot cleared
                        break
                    if cfg.structural_enabled:
                        max_hp = MATERIAL_STATS.get(h.material, MATERIAL_STATS["wood"])["durability"]
                        if h.hp < max_hp:
                            h.hp = min(max_hp, h.hp + REPAIR_RATE)
                            c.energy = max(0.0, c.energy - 0.05)
                            break
            # §AQ PH-6 rubble auto-decay — ruins fade even without builders (1.5 seasons)
            # Prevents unbounded 7k-house blowup at 600k ticks (production 7782 houses).
            if cfg.rubble_blocking_enabled and self.tick % 10 == 0:
                for h in list(self.world.entities.values()):
                    if isinstance(h, House) and h.is_ruin and h.rubble > 0:
                        h.rubble = max(0.0, h.rubble - 0.08)
                        if h.rubble == 0.0:
                            self.world.remove(h.id)
            # hard cap: keep total houses (incl. ruins) < 400 to stay 60 Hz
            total_houses = sum(1 for e in self.world.entities.values() if isinstance(e, House))
            if total_houses > 400:
                # remove oldest ruins first (lowest id), batch 100/tick to avoid one slow tick
                ruins = sorted([e for e in self.world.entities.values() if isinstance(e, House) and e.is_ruin], key=lambda x: x.id)
                for r in ruins[: min(200, total_houses - 400)]:
                    self.world.remove(r.id)

    def _collapse_house(self, h: House) -> None:
        """A building whose structural HP is gone falls in (§AQ PH-6)."""
        h.is_ruin = True
        h.clan_id = 0
        h.clan_color = None
        h.hearth_lit = False
        h.hearth_fuel = 0.0
        if self.config.rubble_blocking_enabled:
            h.rubble = round(h.size, 2)  # blocks the lot until builders clear it
        self._emit_boom(h.x, h.y)
        self._emit(HistoryEvent(
            type="ruin", tick=self.tick + 1, entity_id=h.id,
            x=round(h.x, 2), y=round(h.y, 2),
            payload={"kind": "collapse", "material": h.material},
        ))

    def _generate_anomalies(self) -> None:
        """§AQ PH-10: seed hidden zones where physics runs differently —
        fertile ground, heavy gravity, or calm air. Drawn from the dedicated
        geography rng; undiscovered until a skilled forager stumbles in."""
        count = max(0, int(self.config.anomaly_count))
        if count == 0:
            return
        geo_rng = random.Random((self.config.seed * 8191) ^ 0xA11A)
        kinds = ("fertile", "heavy", "calm")
        margin = 25.0
        for i in range(count):
            self.anomalies.append({
                "x": round(geo_rng.uniform(margin, self.config.width - margin), 2),
                "y": round(geo_rng.uniform(margin, self.config.height - margin), 2),
                "kind": kinds[i % len(kinds)],
                "discovered": False,
            })

    def _anomaly_at(self, x: float, y: float, kind: str | None = None) -> dict | None:
        for a in self.anomalies:
            if kind is not None and a["kind"] != kind:
                continue
            if self.world.distance_sq(x, y, a["x"], a["y"]) <= ANOMALY_RADIUS * ANOMALY_RADIUS:
                return a
        return None

    def _update_seismic(self) -> None:
        """§AQ PH-8: rare earthquakes — the tall castes feel the deep hum a
        few ticks early, then the ground moves: bodies are thrown, weakened
        roofs fall, and stone cracks open or thrusts up from below."""
        cfg = self.config
        if cfg.earthquake_enabled and self.pending_quake is None:
            if self.rng.random() < cfg.earthquake_rate:
                self.pending_quake = {
                    "x": self._rand_pos()[0],
                    "y": self._rand_pos()[1],
                    "mag": self.rng.uniform(4.0, 8.0),
                    "hit_tick": self.tick + QUAKE_WARN_TICKS + 1,
                    "warned": False,
                }
        q = self.pending_quake
        if q is None:
            return
        if not q["warned"] and self.tick >= q["hit_tick"] - QUAKE_WARN_TICKS:
            # Seismic early warning: Pentagons+ feel the vibration first and
            # raise the alarm — the clan heads for shelter before the shock.
            q["warned"] = True
            high_caste = ("Professional", "Noble", "Priest")
            for c in self._cached_creatures:
                if c.caste in high_caste and self.world.distance(
                    c.x, c.y, q["x"], q["y"]
                ) <= QUAKE_WARN_RADIUS:
                    c.panic_ticks = max(c.panic_ticks, 15)
                    if not c.emote:
                        c.emote = "panic"
                        c.emote_ticks = 12
            if len(self.signals) < SIGNALS_MAX:
                self.signals.append({
                    "x": round(q["x"], 2), "y": round(q["y"], 2),
                    "kind": "alarm", "sender": 0, "clan_id": None,
                    "ttl": 12, "born_tick": self.tick,
                })
            return
        if self.tick < q["hit_tick"]:
            return
        # The quake hits.
        self.pending_quake = None
        self._do_earthquake(q["x"], q["y"], q["mag"])

    def _do_earthquake(self, x: float, y: float, mag: float) -> None:
        radius = 12.0 + mag * 2.5
        for e in list(self.world.entities.values()):
            d = self.world.distance(e.x, e.y, x, y)
            if d > radius:
                continue
            falloff = 1.0 - d / radius
            if isinstance(e, Creature):
                ang = self.rng.uniform(0, 2 * math.pi)
                shove = QUAKE_DISPLACEMENT * (mag / 8.0) * falloff
                e.x, e.y = self.world.normalize(
                    e.x + math.cos(ang) * shove, e.y + math.sin(ang) * shove
                )
                dmg = QUAKE_DAMAGE * (mag / 8.0) * falloff
                if e.health - dmg <= 0:
                    self._kill(e, "earthquake")
                else:
                    e.health -= dmg
                    if not e.emote:
                        e.emote = "panic"
                        e.emote_ticks = 12
            elif isinstance(e, House) and not e.is_ruin:
                if self.config.structural_enabled:
                    if e.hp < 0:
                        e.hp = MATERIAL_STATS.get(e.material, MATERIAL_STATS["wood"])["durability"]
                    e.hp -= mag * 12.0 * falloff
                    if e.hp <= 0:
                        self._collapse_house(e)
                elif self.rng.random() < 0.25 * falloff:
                    self._collapse_house(e)
        # stone cracks open — or the ground thrusts new rock up
        for rock in list(self.rocks):
            if self.world.distance(rock["x"], rock["y"], x, y) > radius:
                continue
            roll = self.rng.random()
            if roll < QUAKE_ROCK_CRACK_CHANCE:
                self.rocks.remove(rock)  # a path opens
            elif roll < QUAKE_ROCK_CRACK_CHANCE + QUAKE_ROCK_SPAWN_CHANCE:
                if len(self.rocks) < 400:
                    ang = self.rng.uniform(0, 2 * math.pi)
                    self.rocks.append({
                        "x": self.world.normalize(
                            rock["x"] + math.cos(ang) * rock["r"] * 2.0, rock["y"]
                        )[0],
                        "y": rock["y"],
                        "r": max(1.5, rock["r"] * 0.7),
                    })
        self._cached_terrain_rocks = [dict(r) for r in self.rocks]
        self._emit_boom(x, y)
        self._emit(HistoryEvent(
            type="disaster", tick=self.tick + 1, entity_id=0,
            x=round(x, 2), y=round(y, 2),
            payload={"kind": "earthquake", "mag": round(mag, 1)},
        ))

    def _update_lightning(self) -> None:
        """§AQ PH-9: storms strike real bolts — instant death under the arc,
        fire where the ground burns, a briefly electrostatic fused rock."""
        cfg = self.config
        self.lightning = [b for b in self.lightning if b["ttl"] > 1]
        for b in self.lightning:
            b["ttl"] -= 1
        # electrostatic rocks decay back to plain stone
        for rock in [r for r in self.rocks if r.get("ttl") is not None]:
            rock["ttl"] -= 1
            if rock["ttl"] <= 0:
                self.rocks.remove(rock)
                self._cached_terrain_rocks = [dict(r) for r in self.rocks]
        if not (cfg.lightning_enabled and self.weather == "storm"):
            return
        if self.rng.random() >= cfg.lightning_strike_rate:
            return
        x, y = self._rand_pos()
        self.lightning.append({"x": round(x, 2), "y": round(y, 2), "ttl": LIGHTNING_BOLT_TTL})
        for e in self.world.query_radius(x, y, LIGHTNING_KILL_RADIUS):
            if isinstance(e, Creature) and e.id in self.world.entities:
                self._kill(e, "lightning")
            elif isinstance(e, Food) and e.id in self.world.entities:
                self.world.remove(e.id)
        if cfg.wildfire_enabled and self.rng.random() < 0.6:
            self.fires.append({"x": x, "y": y, "r": 2.5, "ttl": 24})
        elif not self._is_in_rock(x, y):
            self.rocks.append({"x": round(x, 2), "y": round(y, 2),
                               "r": 1.1, "ttl": LIGHTNING_ROCK_TTL})
            self._cached_terrain_rocks = [dict(r) for r in self.rocks]
        self._emit_boom(x, y)
        self._emit(HistoryEvent(
            type="disaster", tick=self.tick + 1, entity_id=0,
            x=round(x, 2), y=round(y, 2), payload={"kind": "lightning"},
        ))

    def _update_anomaly_discovery(self) -> None:
        """§AQ PH-10: only exploration reveals an anomaly — a creature with
        sharp foraging senses (or an explorer's nose) who walks into one."""
        if not self.anomalies:
            return
        for c in self._cached_creatures:
            skill = c.skills.get("foraging", 0.0)
            if skill < ANOMALY_DISCOVER_SKILL and c.personality != "explorer":
                continue
            for a in self.anomalies:
                if a["discovered"]:
                    continue
                if self.world.distance_sq(c.x, c.y, a["x"], a["y"]) <= ANOMALY_RADIUS ** 2:
                    a["discovered"] = True
                    self._learn(c, "safe", a["x"], a["y"], conf=0.9)
                    self._emit(HistoryEvent(
                        type="anomaly", tick=self.tick + 1, entity_id=c.id,
                        caste=c.caste, x=round(a["x"], 2), y=round(a["y"], 2),
                        payload={"kind": a["kind"], "clan_id": c.clan_id},
                    ))

    def _update_law_wave(self) -> None:
        """§AQ PH-10: a law change sends a shimmer wave across the land; the
        old and the new law hang in the air for a transition window while the
        front sweeps west→east, and bodies inside the band feel the boundary
        pass through them (disorientation)."""
        if self.law_wave is None:
            return
        if self.tick - self.law_wave["born_tick"] > LAW_WAVE_TICKS:
            self.law_wave = None

    def _law_wave_front(self) -> float | None:
        if self.law_wave is None:
            return None
        p = (self.tick - self.law_wave["born_tick"]) / LAW_WAVE_TICKS
        return p * self.config.width

    def _update_builders(self) -> None:
        """§AQ PH-3: builder-personality creatures span the channels they live
        beside — planks first, dams when the water starts to rise."""
        if not self.rivers or not self._cached_creatures or self.tick % 15 != 0:
            return
        builders = [
            c for c in self._cached_creatures
            if (
                getattr(c, "personality", "") == "builder"
                or c.caste == "Artisan"
                or (isinstance(getattr(c, "skills", None), dict) and c.skills.get("foraging", 0.0) >= 10.0)
            )
            and c.energy > 35.0
        ]
        for b in builders:
            r = min(
                (rv for rv in self.rivers if self._river_dy(b.y, rv["cy"]) <= 24.0),
                key=lambda rv: self._river_dy(b.y, rv["cy"]),
                default=None,
            )
            if r is None:
                continue
            def _dx(ax: float, bx2: float) -> float:
                d = abs(ax - bx2)
                return min(d, self.config.width - d)
            near_crossing = any(
                _dx(b.x, br["x"]) <= 14.0 and br["cy"] == r["cy"]
                for br in self.bridges
            )
            rising = r["water"] > 0.5 or r["flood_ticks"] > 0
            has_dam = any(d["cy"] == r["cy"] for d in self.dams)
            if rising and not has_dam and len(self.dams) < 4:
                b.energy -= 15.0
                self.dams.append({"x": round(b.x, 2), "cy": r["cy"], "hp": DAM_HP})
                self._emit(HistoryEvent(
                    type="settlement", tick=self.tick + 1, entity_id=b.id, caste=b.caste,
                    x=round(b.x, 2), y=round(b.y, 2),
                    payload={"kind": "dam", "river_cy": r["cy"], "clan_id": b.clan_id},
                ))
                continue
            # Mend existing damaged bridge nearby
            repaired = False
            for br in self.bridges:
                if br["cy"] == r["cy"] and _dx(b.x, br["x"]) <= 18.0 and br["hp"] < BRIDGE_HP - 20:
                    br["hp"] = min(BRIDGE_HP, br["hp"] + 120)
                    b.energy -= 4.0
                    b.emote = "craft"
                    b.emote_ticks = 15
                    repaired = True
                    break
            if repaired:
                continue

            if not near_crossing and len(self.bridges) < 16:
                b.energy -= 10.0
                self.bridges.append({"x": round(b.x, 2), "cy": r["cy"], "hw": r["hw"], "hp": BRIDGE_HP})
                self._emit(HistoryEvent(
                    type="settlement", tick=self.tick + 1, entity_id=b.id, caste=b.caste,
                    x=round(b.x, 2), y=round(r["cy"], 2),
                    payload={"kind": "bridge", "river_cy": r["cy"], "clan_id": b.clan_id},
                ))

    def _update_fires(self) -> None:
        """§S Wildfire — ignites via storm lightning / fire_rate, spreads, kills."""
        cfg = self.config
        if not cfg.wildfire_enabled:
            # decay existing fires even when disabled? keep them fading
            self.fires = [f for f in self.fires if f["ttl"] > 1]
            for f in self.fires:
                f["ttl"] -= 1
            return
        # Decay
        new_fires = []
        for f in self.fires:
            f["ttl"] -= 1
            if f["ttl"] > 0:
                new_fires.append(f)
            else:
                # ash fertilizes nearby plants (nutrient boost)
                for e in self.world.query_radius(f["x"], f["y"], 8.0):
                    if isinstance(e, Food):
                        e.growth = min(1.0, e.growth + 0.15)
        self.fires = new_fires
        # Ignition: storm lightning or random fire_rate — §AQ PH-2: buildings
        # and groves DOWNWIND of the flames catch first.
        ignite_chance = cfg.fire_rate
        if self.weather == "storm":
            ignite_chance = max(ignite_chance, 0.002)  # lightning
        if self.rng.random() < ignite_chance:
            foods = [e for e in (self._cached_foods or self.world.entities.values()) if isinstance(e, Food) and e.growth > 0.5]
            if foods:
                wx, wy = self._cos_wind, self._sin_wind
                f0 = max(self.fires, key=lambda f: f["r"]) if self.fires else None

                def tailwind(e: Entity) -> float:
                    if f0 is None:
                        return 1.0
                    d = self.world.distance(f0["x"], f0["y"], e.x, e.y) or 1.0
                    return 1.0 + WIND_FIRE_MULT * self.wind_speed * max(
                        0.0, ((e.x - f0["x"]) / d) * wx + ((e.y - f0["y"]) / d) * wy
                    )

                victim = max(foods, key=lambda e: (self.rng.random() ** (1.0 / tailwind(e)), -e.id))
                self.fires.append({"x": victim.x, "y": victim.y, "r": 3.0, "ttl": 28})
                self.world.remove(victim.id)
                self._emit(HistoryEvent(type="fire", tick=self.tick+1, entity_id=0, x=round(victim.x,2), y=round(victim.y,2), payload={"kind": "ignite", "r": 3.0}))
        # Spread to neighboring plants — faster downwind (§AQ PH-2)
        if self.fires and self.rng.random() < cfg.fire_spread_rate * len(self.fires):
            wx, wy = self._cos_wind, self._sin_wind
            for f in list(self.fires):
                for e in self.world.query_radius(f["x"], f["y"], 6.0):
                    if not isinstance(e, Food):
                        continue
                    d = self.world.distance(f["x"], f["y"], e.x, e.y) or 1.0
                    tailwind = max(0.0, ((e.x - f["x"]) / d) * wx + ((e.y - f["y"]) / d) * wy)
                    chance = 0.35 * (1.0 + WIND_FIRE_MULT * self.wind_speed * tailwind)
                    if self.rng.random() < min(0.9, chance):
                        self.fires.append({"x": e.x, "y": e.y, "r": 2.5, "ttl": 22})
                        self.world.remove(e.id)
                        break
        # Burn creatures and plants within fire radius
        for f in list(self.fires):
            for e in self.world.query_radius(f["x"], f["y"], f["r"] + 1.2):
                if isinstance(e, Creature) and e.id in self.world.entities:
                    if self.rng.random() < 0.18:
                        self._kill(e, "fire")
                elif isinstance(e, Food) and e.id in self.world.entities:
                    if self.world.distance(e.x, e.y, f["x"], f["y"]) < f["r"] and self.rng.random() < 0.25:
                        self.world.remove(e.id)
            # §AQ PH-1: radiant heat beyond the flame core — the fire warms the
            # winter grove AND cooks whoever lingers too close (double-edged).
            scald_r = f["r"] + FIRE_SCALD_RADIUS
            for e in self.world.query_radius(f["x"], f["y"], scald_r):
                if not isinstance(e, Creature) or e.id not in self.world.entities:
                    continue
                d = self.world.distance(e.x, e.y, f["x"], f["y"])
                if d <= f["r"] + 1.2:
                    continue  # core burn handled above
                frac = 1.0 - (d - f["r"]) / FIRE_SCALD_RADIUS
                dmg = FIRE_SCALD_DAMAGE * max(0.0, frac)
                if dmg <= 0 or self.rng.random() >= 0.5:
                    continue
                if e.health - dmg <= 0:
                    self._kill(e, "hyperthermia")
                else:
                    e.health -= dmg
            # also burn houses? small chance to ignite house (is_ruin)
            for h in (self._cached_houses if self._cached_houses else self._functional_houses()):
                if not h.is_ruin and self.world.distance(h.x, h.y, f["x"], f["y"]) < f["r"] + h.size/2:
                    if self.rng.random() < 0.03:
                        h.is_ruin = True
                        h.clan_id = 0
                        h.clan_color = None
                        self._emit(HistoryEvent(type="fire", tick=self.tick+1, entity_id=h.id, x=round(h.x,2), y=round(h.y,2), payload={"kind": "house_burn"}))

    def _update_campfires(self) -> None:
        """§AO Phase E: stranded explorers caught far from home at nightfall
        gather dry brush and light a field campfire — a small circle of light
        and warmth that repels predators and burns until dawn."""
        tod = self._time_of_day()
        if not self._is_night(tod):
            if self.campfires:
                self.campfires = []  # dawn: the fires go cold
            return
        if len(self.campfires) >= 12:
            return
        for c in self._get_creatures():
            if c.personality != "explorer" or c.is_predator or c.is_herbivore:
                continue
            if c.indoors or c.sleeping:
                continue
            if self.rng.random() >= CAMPFIRE_KINDLE_CHANCE:
                continue
            # stranded means far from any roof (own clan's or neutral)
            stranded = True
            for h in self._cached_houses:
                hh = cast(House, h)
                if not hh.is_ruin and self.world.distance(c.x, c.y, hh.x, hh.y) < 24.0:
                    stranded = False
                    break
            if not stranded:
                continue
            # no fire already burning nearby
            too_close = False
            for cf in self.campfires:
                if (cf["x"] - c.x) ** 2 + (cf["y"] - c.y) ** 2 < 64.0:
                    too_close = True
                    break
            if too_close:
                continue
            self.campfires.append({"x": round(c.x, 2), "y": round(c.y, 2), "day": self.day})
            c.emote = "craft"
            c.emote_ticks = 15

    def _update_disasters(self) -> None:
        """§S Disaster laws — meteor/flood stochastic, gated by disaster_rate."""
        cfg = self.config
        if not cfg.disaster_enabled or cfg.disaster_rate <= 0:
            return
        if self.rng.random() >= cfg.disaster_rate:
            return
        kind = self.rng.choice(["meteor", "flood"])
        cx, cy = self._rand_pos()
        r = self.rng.uniform(6, 12) if kind == "meteor" else self.rng.uniform(10, 18)
        if kind == "meteor":
            # crater kills, removes plants, adds rock
            self.rocks.append({"x": cx, "y": cy, "r": r*0.6})
            for e in list(self.world.entities.values()):
                if self.world.distance(e.x, e.y, cx, cy) < r:
                    if isinstance(e, Creature) and self.rng.random() < 0.85:
                        self._kill(e, "disaster")
                    elif isinstance(e, Food) and self.rng.random() < 0.9:
                        self.world.remove(e.id)
            self._emit(HistoryEvent(type="disaster", tick=self.tick+1, entity_id=0, x=round(cx,2), y=round(cy,2), payload={"kind": "meteor", "r": round(r,2)}))
        else:
            # flood: pushes creatures, drowns some, washes plants?
            for e in list(self.world.entities.values()):
                if self.world.distance(e.x, e.y, cx, cy) < r:
                    if isinstance(e, Creature):
                        # push out
                        ang = self.rng.uniform(0, 2*3.14159)
                        e.x, e.y = self.world.normalize(cx + math.cos(ang)*(r+2), cy + math.sin(ang)*(r+2))
                        if self.rng.random() < 0.15:
                            self._kill(e, "disaster")
                    elif isinstance(e, Food) and self.rng.random() < 0.4:
                        self.world.remove(e.id)
            self._emit(HistoryEvent(type="disaster", tick=self.tick+1, entity_id=0, x=round(cx,2), y=round(cy,2), payload={"kind": "flood", "r": round(r,2)}))

