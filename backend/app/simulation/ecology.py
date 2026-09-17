"""Ecology mixin — flora lifecycle, agriculture, banquets, corpse decomposition, nutrient cycling, food law (BI-4)."""

from __future__ import annotations

import math
import random
from typing import Any

from ..entities import Corpse, Creature, Entity, Food, House
from ..protocol import HistoryEvent
from .constants import *
from .constants import (
    _season_food_mult,
    _smooth_season_food_mult,
    _smooth_age_mult,
    _clan_sig,
    personal_name_for,
    glyph_for,
    variation_for,
)

class EcologyMixin:
    def _update_plants(self) -> None:
        """§H: every plant grows toward maturity; the mature ones spread. §O variant rhythms. §R weather waters/damages. §AE mature plants wither.
        §AQ PH-0: growth rides sunlight — the day cycle is the world's income."""
        cfg = self.config
        sun = self._sun_factor()
        tod = self._time_of_day()
        # §AQ PH-10: precompute roof shadows (cast west, the sun stands east)
        shadow_rects: list[tuple[float, float, float, float]] = []
        for h in (self._cached_houses or self._functional_houses()):
                ext = h.size * SHADOW_LENGTH
                shadow_rects.append((
                    h.x - h.size / 2 - ext, h.x - h.size / 2,
                    h.y - h.size / 2, h.y + h.size / 2,
                ))
        # Phase 5 Tier1 + Phase4 soft-cap: effective growth scaled by eta and xi
        _eta = float(getattr(self, "_safeguard_eta", 0.0) or 0.0)
        _xi_g = float(getattr(self, "_density_xi", 0.0) or 0.0)
        _growth_eff = cfg.plant_growth_rate
        if _eta:
            _growth_eff *= (1.0 + 2.5 * _eta)
        if _xi_g:
            _growth_eff /= (1.0 + float(getattr(cfg, "resource_strain_mult", 1.2)) * _xi_g)
        if _growth_eff > 0 and sun > 0.0:
            season = self._season()
            summer_drought = season == "summer"
            winter = season == "winter"
            for e in self.world.entities.values():
                if isinstance(e, Food) and e.growth < 1.0:
                    if cfg.plant_variants_enabled:
                        vm = VARIANT_GROWTH_MULT.get(e.variant, 1.0)
                        sm = VARIANT_SEASON_MULT.get(e.variant, {}).get(season, 1.0)
                    else:
                        vm, sm = 1.0, 1.0
                    wm = 1.0
                    if self.weather in ("rain", "storm"):
                        wm = cfg.rain_growth_mult
                    elif self.weather == "fog" and e.variant == "mushroom":
                        wm = cfg.fog_mushroom_mult
                    # §AM B: sown crops outrun the wild weeds; furrows hold moisture
                    if e.cultivated:
                        vm *= CULTIVATED_GROWTH_MULT
                        if e.irrigated:
                            vm *= IRRIGATED_GROWTH_MULT
                            wm = max(wm, 1.0)  # drought-proof through the dry heat
                    # §AQ PH-5: roots contest the soil; symbiosis tips the balance.
                    # Mature neighbours crowd the sprout, corpses feed mushrooms,
                    # berries shelter herbs, toxins stunt everything near.
                    near_mature = 0
                    corpse_near = False
                    berry_near = False
                    poison_near = False
                    for o in self.world.query_radius(e.x, e.y, SYMBIOSIS_RADIUS):
                        if o.id == e.id or o.id not in self.world.entities:
                            continue
                        if isinstance(o, Food):
                            if o.growth >= 1.0:
                                if o.variant == "poisonous":
                                    poison_near = True
                                elif (
                                    cfg.plant_variants_enabled
                                    and e.variant == "medicinal_herb"
                                    and o.variant == "berry"
                                ):
                                    berry_near = True  # thicket shelter, not rivalry
                                else:
                                    near_mature += 1
                        elif isinstance(o, Corpse):
                            corpse_near = True
                    eco_mult = 1.0 / (1.0 + ROOT_COMPETITION * near_mature)
                    if cfg.plant_variants_enabled:
                        if e.variant == "mushroom" and corpse_near:
                            eco_mult *= MUSHROOM_CORPSE_MULT
                        elif e.variant == "medicinal_herb" and berry_near:
                            eco_mult *= HERB_BERRY_MULT
                        if poison_near and e.variant != "poisonous":
                            eco_mult *= POISON_SUPPRESS
                    # §AQ PH-10: fertile anomalies grow strange and lush
                    if self.anomalies and self._anomaly_at(e.x, e.y, "fertile"):
                        eco_mult *= ANOMALY_GROWTH_MULT
                    # §AQ PH-10: roofs shade the ground west of them —
                    # shade-starved sprouts grow slower
                    for sh in shadow_rects:
                        if sh[0] <= e.x <= sh[1] and sh[2] <= e.y <= sh[3]:
                            eco_mult *= SHADOW_GROWTH_MULT
                            break
                    # §AQ PH-10: dawn light sweeps in from the east edge,
                    # dusk from the west — the rim gets a brief bonus
                    if (
                        (0.22 < tod < 0.30 and e.x > cfg.width - SUN_EDGE_BAND)
                        or (0.70 < tod < 0.78 and e.x < SUN_EDGE_BAND)
                    ):
                        eco_mult *= SUN_EDGE_GROWTH_MULT
                    # §AQ PH-3: fresh silt on the banks feeds the next harvest
                    for rv in self.rivers:
                        if (
                            rv["silt_ticks"] > 0
                            and self._river_dy(e.y, rv["cy"]) <= rv["hw"] + RIVER_SILT_RADIUS
                        ):
                            eco_mult *= RIVER_SILT_MULT
                            break
                    # §AQ PH-4: packed earth grows nothing — roads starve the field
                    if cfg.relief_enabled:
                        tcol = min(self._temp_cols - 1, max(0, int(e.x / cfg.width * self._temp_cols)))
                        trow = min(self._temp_rows - 1, max(0, int(e.y / cfg.height * self._temp_rows)))
                        traffic = self.traffic_grid[trow * self._temp_cols + tcol]
                        if traffic >= TRAFFIC_PLANT_BLOCK:
                            eco_mult = 0.0
                        elif traffic > 0:
                            eco_mult *= max(0.25, 1.0 - traffic / TRAFFIC_PLANT_BLOCK)
                    # §AM D: the soil gives what the soil has
                    soil = self._soil_at(e.x, e.y)
                    soil_f = max(0.5, min(1.4, 0.55 + 0.45 * soil))
                    age_now = self._age()
                    am = 0.75 if age_now == "Ice" else (1.25 if age_now == "Golden" else 1.0)
                    gained = min(
                        1.0 - e.growth,
                        _growth_eff * vm * sm * wm * am * sun * soil_f * eco_mult,
                    )
                    e.growth += gained
                    self._deplete_soil(e.x, e.y, gained)  # the harvest draws on the land
                    if e.growth >= 1.0:
                        self._emit_bloom(e)
        # §AM C.2: winter frost bites exposed crops — cultivated beds & irrigated
        # furrows shrug it off; everything else in the open fields suffers.
        if (
            cfg.agriculture_enabled
            and self._season() == "winter"
            and WINTER_FROST_CHANCE > 0
        ):
            for e in list(self.world.entities.values()):
                if not isinstance(e, Food) or e.cultivated or e.irrigated:
                    continue
                if e.growth < 0.3:
                    continue  # sprouts sleep under the snow
                if self.rng.random() < WINTER_FROST_CHANCE:
                    e.growth = max(0.0, e.growth - self.rng.uniform(0.15, 0.4))
                    if e.growth <= 0.05:
                        self.world.remove(e.id)
        # §AE Food decay — a mature plant lives food_lifespan_ticks × its
        # variant's pace, wilts near the end, fertilises, then vanishes.
        # Sprouts and growing plants don't rot; only the harvest does.
        if cfg.food_decay_enabled and cfg.food_lifespan_ticks > 0:
            for e in list(self.world.entities.values()):
                if not isinstance(e, Food) or e.growth < 1.0:
                    continue
                life = max(1, round(cfg.food_lifespan_ticks * FOOD_LIFESPAN_MULT.get(e.variant, 1.0)))
                e.mature_ticks = (getattr(e, "mature_ticks", 0) or 0) + 1
                if e.mature_ticks >= life:
                    self._release_nutrients(e, mult=WITHER_NUTRIENT_MULT)  # death feeds life
                    self.world.remove(e.id)
                    self._emit(
                        HistoryEvent(
                            type="wither",
                            tick=self.tick + 1,
                            entity_id=e.id,
                            x=round(e.x, 2),
                            y=round(e.y, 2),
                            payload={"variant": e.variant, "age": e.mature_ticks},
                        )
                    )
        # Storm damage: exposed plants stripped, occasionally uprooted (§R);
        # §AM: furrowed beds hold their soil — irrigation shelters them.
        if self.weather == "storm" and cfg.storm_plant_damage > 0:
            for e in list(self.world.entities.values()):
                if not isinstance(e, Food) or e.irrigated:
                    continue
                if self.rng.random() < cfg.storm_plant_damage:
                    e.growth = max(0.0, e.growth - self.rng.uniform(0.2, 0.5))
                    if e.growth <= 0.05 and self.rng.random() < 0.5:
                        self.world.remove(e.id)
        # Phase 4 Channel 3 effective spread via xi
        _xi_spread = float(getattr(self, "_density_xi", 0.0) or 0.0)
        _spread_eff = cfg.plant_spread_rate / (1.0 + 2.0 * _xi_spread) if _xi_spread else cfg.plant_spread_rate
        if _spread_eff > 0 and sun > 0.0:
            offset = int(getattr(cfg, "initial_season_offset", 0) or 0)
            sm = _smooth_season_food_mult(self.tick, cfg.season_length, cfg.winter_food_mult, offset=offset)
            target = round(cfg.food_count * sm)
            age = self._age()
            if age is not None:
                target = round(target * _smooth_age_mult(self.tick, cfg.age_length, AGE_FOOD_MULT))
            total = sum(1 for e in self.world.entities.values() if e.kind == "food")
            wx, wy = self._cos_wind, self._sin_wind
            seed_blend = min(0.7, WIND_SEED_BIAS * self.wind_speed)
            for parent in list(self.world.entities.values()):
                if not isinstance(parent, Food) or parent.growth < 1.0:
                    continue  # only mature plants carry seeds
                if self.rng.random() >= _spread_eff * sun:
                    continue
                if total >= target:
                    continue  # the land holds exactly god's seasonal bounty
                ang = self.rng.uniform(0, 2 * math.pi)
                rad = self.rng.uniform(0, SPREAD_RADIUS)
                # §AQ PH-2: seeds ride the wind — the drift bends downwind, so
                # groves creep with the prevailing breeze and upwind ground
                # stays clear.
                vx = math.cos(ang) * (1.0 - seed_blend) + wx * seed_blend
                vy = math.sin(ang) * (1.0 - seed_blend) + wy * seed_blend
                norm = math.hypot(vx, vy) or 1.0
                x, y = self.world.normalize(
                    parent.x + vx / norm * rad,
                    parent.y + vy / norm * rad,
                )
                if (
                    not self._is_in_rock(x, y)
                    and not (self.rivers and self._in_river_band(x, y, pad=1.0))
                    and not self._is_point_inside_any_house(x, y, pad=0.8)
                ):
                    self.world.add(self._new_food(x, y, growth=SPROUT_GROWTH))
                    total += 1

    def _emit_bloom(self, plant: Food) -> None:
        """A plant has reached maturity: recorded in the chronicle."""
        self._emit(
            HistoryEvent(
                type="bloom",
                tick=self.tick + 1,
                entity_id=plant.id,
                x=round(plant.x, 2),
                y=round(plant.y, 2),
                payload={"x": round(plant.x, 2), "y": round(plant.y, 2), "variant": plant.variant},
            )
        )

    def _update_corpses(self) -> None:
        """Corpses rot away once their ttl runs out — and death feeds life."""
        if not self.config.corpses_enabled:
            return
        # AF: iterate pre-built corpse cache — no full entity scan needed
        for e in list(self._cached_corpses):
            e.ttl -= 1
            if e.ttl <= 0:
                self._release_nutrients(e)
                self.world.remove(e.id)

    def _ensure_farm_plots(self) -> None:
        """§AM B.1: settled clans till FARM_PLOTS_PER_CLAN plots around their
        main house. Plots near a fertile grove are furrow-irrigated (drought-
        and frost-proof). Deterministic ring angles; never touches the rng."""
        if not self.config.agriculture_enabled or self.tick % 120 != 0:
            return
        living = {c.clan_id for c in self._get_creatures() if c.clan_id}
        # prune plots of dead clans
        self.farm_plots = {cid: p for cid, p in self.farm_plots.items() if cid in living}
        r = max(6.0, self.config.territory_radius * 0.55)
        for cid in sorted(self.clans.keys()):
            hid = self.clans[cid].get("main_house_id")
            house = self.world.entities.get(hid) if hid is not None else None
            if not isinstance(house, House):
                continue
            plots = self.farm_plots.setdefault(cid, [])
            k = len(plots)
            while k < FARM_PLOTS_PER_CLAN:
                ang = (cid * 2.399 + k * 2.094) % (2 * math.pi)
                px, py = self.world.normalize(
                    house.x + math.cos(ang) * r, house.y + math.sin(ang) * r
                )
                if not self._is_in_rock(px, py):
                    irrigated = any(
                        self.world.distance(px, py, f["x"], f["y"]) <= f["r"] + 3.0
                        for f in self.fertile
                    )
                    plots.append({"x": round(px, 2), "y": round(py, 2), "irrigated": irrigated})
                k += 1

    def _sow_and_tend(self) -> None:
        """§AM B: farmers sow seed pouches into empty clan plots; skilled hands
        weed toxic sprouts, tend the beds against premature withering, and
        compost near the settlement to revive exhausted soil."""
        if not self.config.agriculture_enabled:
            return
        main_houses: dict[int, House] = {}
        for h in self._cached_houses:
            if isinstance(h, House) and h.clan_id and not h.is_ruin:
                main_houses.setdefault(h.clan_id, h)
        for c in self._get_creatures():
            if c.is_predator or c.is_herbivore or c.sleeping:
                continue
            farm_xp = float(getattr(c, "skills", {}).get("farming", 0.0))
            # — sowing —
            if (
                c.seeds > 0
                and c.clan_id
                and farm_xp >= SEED_SKILL_MIN
                and self.rng.random() < 0.5
            ):
                plot = next(
                    (
                        p for p in self.farm_plots.get(c.clan_id, ())
                        if self.world.distance_sq(c.x, c.y, p["x"], p["y"]) <= 9.0
                        and not any(
                            isinstance(f, Food)
                            and f.id in self.world.entities
                            and self.world.distance_sq(f.x, f.y, p["x"], p["y"]) <= 1.0
                            for f in (self._cached_foods if self._cached_foods is not None else [e for e in self.world.entities.values() if isinstance(e, Food)])
                        )
                    ),
                    None,
                )
                if plot is not None:
                    c.seeds -= 1
                    variant = "grain" if self.rng.random() < 0.7 else "grass"
                    crop = Food(x=plot["x"], y=plot["y"], growth=SPROUT_GROWTH,
                                variant=variant, cultivated=True,
                                irrigated=bool(plot.get("irrigated")))
                    self.world.add(crop)
                    c.skills["farming"] = farm_xp + 1.0
            # — tending & weeding & compost (staggered per creature) —
            if farm_xp < TEND_SKILL_MIN or (self.tick + c.id) % 9 != 0:
                continue
            for e, _ in self.world.query_radius_with_dist_sq(c.x, c.y, 4.0):
                if isinstance(e, Food):
                    if e.variant == "poisonous" and e.growth < 0.5:
                        self.world.remove(e.id)  # weeded out before it can harm
                    elif e.cultivated:
                        e.mature_ticks = max(0, e.mature_ticks - TEND_REGRESS_TICKS)
            # composting: master farmers refresh the home soil on a long cadence
            if (
                farm_xp >= 12.0
                and c.clan_id in main_houses
                and COMPOST_INTERVAL > 0
                and (self.tick + c.id * 7) % COMPOST_INTERVAL == 0
            ):
                mh = main_houses[c.clan_id]
                if self.world.distance(c.x, c.y, mh.x, mh.y) <= self.config.territory_radius:
                    self._fertilize_soil(mh.x, mh.y, 10.0, COMPOST_NUTRIENT)
                    self._emit(
                        HistoryEvent(
                            type="compost",
                            tick=self.tick + 1,
                            entity_id=c.id,
                            caste=c.caste,
                            x=round(mh.x, 2), y=round(mh.y, 2),
                            payload={"clan_id": c.clan_id,
                                     "clan_name": self.clans.get(c.clan_id, {}).get("name")},
                        )
                    )

    def _update_agriculture(self) -> None:
        """§AM orchestrator — fixed order keeps the rng stream deterministic."""
        self._ensure_farm_plots()
        self._sow_and_tend()
        self._update_banquets()

    def _update_banquets(self) -> None:
        """§AM E.2: an overflowing granary feeds a clan feast — morale, bonds
        and a baby boom while the mead lasts."""
        if not (self.config.banquets_enabled and self.config.granaries_enabled):
            return
        if self.tick % 60 != 0:
            return
        houses_by_clan: dict[int, House] = {}
        for h in self._cached_houses:
            if isinstance(h, House) and h.clan_id and not h.is_ruin:
                houses_by_clan.setdefault(h.clan_id, h)
        for cid in sorted(self.clans.keys()):
            info = self.clans[cid]
            granary = float(info.get("granary", 0.0))
            cap = max(1.0, self.config.granary_capacity)
            if granary < cap * BANQUET_FILL_FRACTION:
                continue
            if self.tick - int(self._banquet_last.get(cid, -BANQUET_MIN_GAP)) < BANQUET_MIN_GAP:
                continue
            house = houses_by_clan.get(cid)
            if house is None:
                continue
            cost = granary * BANQUET_COST_FRACTION
            info["granary"] = granary - cost
            info["feast_until"] = self.tick + BANQUET_FEAST_TICKS
            self._banquet_last[cid] = self.tick
            guests: set[int] = set()  # clans present at the table (incl. cid)
            for m in self._clan_members.get(cid, ()):
                if self.world.distance(m.x, m.y, house.x, house.y) <= self.config.territory_radius:
                    guests.add(m.clan_id)
                    m.energy = min(self.config.energy_max, m.energy + 12.0)
                    m.emote = "cheer"
                    m.emote_ticks = 40
            for other_cid in sorted(guests):
                if other_cid != cid:
                    self._bump_relation(other_cid, cid, 4)
            self._emit(
                HistoryEvent(
                    type="banquet",
                    tick=self.tick + 1,
                    entity_id=house.id,
                    x=round(house.x, 2), y=round(house.y, 2),
                    payload={"clan_id": cid, "clan_name": info.get("name"),
                             "spent": round(cost, 1)},
                )
            )

    def _release_nutrients(self, corpse: Entity, mult: float = 1.0) -> None:
        """A fully decayed corpse (or withered plant, §AE) boosts nearby plant growth."""
        boost = NUTRIENT_BOOST * self.config.nutrient_cycle_rate * mult
        if boost <= 0:
            return
        # §AM D.2: death also refills the living soil grid — the field remembers.
        if self.config.soil_depletion_enabled:
            self._fertilize_soil(corpse.x, corpse.y, NUTRIENT_RADIUS, boost * 0.1)
        # §AP: a Sacred Spiral shrine composts what dies beside it — death is
        # folded back into life faster within the aura.
        for cid, info in self.clans.items():
            if info.get("totem") != "Sacred Spiral" or int(info.get("shrine_level", 0)) < 1:
                continue
            shrine = self._shrine_pos(cid)
            if shrine and self.world.distance_sq(corpse.x, corpse.y, shrine[0], shrine[1]) <= NUTRIENT_RADIUS ** 2:
                boost *= 1.0 + self._totem_stat_compost(info)
                break
        # AF: spatial query around decaying entity instead of scanning all world entities
        for e in self.world.query_radius(corpse.x, corpse.y, NUTRIENT_RADIUS):
            if not isinstance(e, Food):
                continue
            was = e.growth
            e.growth = min(1.0, e.growth + boost)
            if was < 1.0 <= e.growth:
                self._emit_bloom(e)

    def _totem_stat_compost(self, clan_info: dict) -> float:
        return float(TOTEM_BUFF.get(clan_info.get("totem"), {}).get("compost", 0.0))

    def _enforce_food_law(self) -> None:
        """God's bounty or famine, bent by the season and age: winter starves the land."""
        offset = int(getattr(self.config, "initial_season_offset", 0) or 0)
        sm = _smooth_season_food_mult(
            self.tick, self.config.season_length, self.config.winter_food_mult, offset=offset
        )
        target = round(self.config.food_count * sm)
        age = self._age()
        if age is not None:
            am = _smooth_age_mult(self.tick, self.config.age_length, AGE_FOOD_MULT)
            target = round(target * am)
        foods = [e for e in self.world.entities.values() if e.kind == "food" and not getattr(e, "cultivated", False)]
        # Ensure no wild plants exist inside any shelter structure (periodic clean-up to save 50ms/tick)
        if self.tick % 60 == 0:
            inside_shelter_ids = [
                f.id for f in foods if self._is_point_inside_any_house(f.x, f.y, pad=0.2)
            ]
            for f_id in inside_shelter_ids:
                self.world.remove(f_id)
            if inside_shelter_ids:
                foods = [f for f in foods if f.id not in inside_shelter_ids]
        law_changed = getattr(self, "_last_law_food_count", self.config.food_count) != self.config.food_count
        self._last_law_food_count = self.config.food_count
        deficit = target - len(foods)
        if deficit > 0:
            season = self._season()
            growth_init = 1.0
            if age == "Ice":
                growth_init = 0.25
            elif age == "Plague":
                growth_init = 0.45
            elif season == "winter":
                growth_init = 0.4

            # If meadow is unpopulated (cold start/world init), law changed, or in micro-test mode, fill immediately
            if (
                len(foods) == 0
                or law_changed
                or getattr(self.config, "fast_food_spawn", False)
                or self.config.season_length < 60
            ):
                spawn_n = deficit
            else:
                # Regrowth flux bounded per tick to allow genuine grazing depletion
                max_flux = max(1, int(round(target * 0.025)))
                spawn_n = min(deficit, max_flux)

            for _ in range(spawn_n):
                x, y = self._food_pos()
                self.world.add(self._new_food(x, y, growth=growth_init))
        elif deficit < 0:
            ordered = sorted(foods, key=lambda f: f.growth)
            for victim in ordered[:-deficit]:
                self.world.remove(victim.id)

