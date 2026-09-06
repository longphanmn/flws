"""Creature update mixin — decomposed _update_creature into 7 phases (BI-10)."""

from __future__ import annotations

import math
import random
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
from .constants import *

from .settlement import _house_wall_segments, _house_wall_segments_closed, _path_crosses_wall, _wall_segments_cached

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

try:
    from .. import agent_soa as _agent_soa  # type: ignore
    from .. import evolution as _evolution  # type: ignore
except Exception:  # pragma: no cover
    _agent_soa = None  # type: ignore
    _evolution = None  # type: ignore

class CreatureUpdateMixin:
    def _update_creature(
        self,
        c: Creature,
        houses: list[Entity],
        tod: float | None = None,
        is_night: bool | None = None,
        env_sight: float | None = None,
        env_speed: float | None = None,
        clan_house_map: dict[int, House] | None = None,
    ) -> None:
        cfg, w = self.config, self.world
        if tod is None:
            tod = self._time_of_day()
        if is_night is None:
            is_night = self._is_night(tod)
        if env_sight is None:
            env_sight = self.env_sight_mult()
        if env_speed is None:
            env_speed = self.env_speed_mult()
        if clan_house_map is None:
            clan_house_map = {
                h.clan_id: h for h in houses if isinstance(h, House) and h.clan_id and not h.is_ruin
            }
        _xi_pop = float(getattr(self, "_xi_decay_tick", 0.0) or 0.0)
        # BA 8.x NN latched outputs (15Hz, SoA) — wired but soft-gated for test stability
        # PERF: read the per-inference snapshot when available (identical
        # values to outputs_buf, which is only written at inference time).
        _nn_out = None
        if getattr(self, "_soa", None) is not None and hasattr(self, "_soa_id_map") and c.id in getattr(self, "_soa_id_map", {}):
            try:
                _nn_idx = self._soa_id_map[c.id]  # type: ignore
                _nn_cache = getattr(self, "_nn_out_cache", None)
                if _nn_cache is not None and 0 <= _nn_idx < len(_nn_cache):
                    _nn_out = _nn_cache[_nn_idx]
                else:
                    _nn_out = self._soa.outputs_buf[_nn_idx]  # type: ignore
                    if hasattr(_nn_out, "tolist"):
                        _nn_out = _nn_out.tolist()  # type: ignore
            except Exception:
                _nn_out = None

        c.ticks_since_meal += 1
        c.age += 1
        # §AU O-1: the assigned roof resolves lazily ONCE per creature tick;
        # every later consumer reuses it instead of re-scanning all houses.
        roof_resolved = False
        assigned_roof: House | None = None
        if c.repro_cooldown > 0:
            c.repro_cooldown -= 1
        if c.bite_cooldown > 0:
            c.bite_cooldown -= 1
        if c.cannibal_cooldown > 0:
            c.cannibal_cooldown -= 1
        if c.panic_ticks > 0:
            c.panic_ticks -= 1
        if c.alarm_wake_ticks > 0:
            c.alarm_wake_ticks -= 1
        if getattr(c, "combat_boost_ticks", 0) > 0:
            c.combat_boost_ticks -= 1
        if getattr(c, "fall_cooldown", 0) > 0:
            c.fall_cooldown -= 1
        # §AR S-3: decay, drift and eviction keep memory honest
        self._maintain_facts(c)
        if c.calm_ticks > 0:
            c.calm_ticks -= 1
        if c.prepared_ticks > 0:
            c.prepared_ticks -= 1
        if c.greet_cooldown > 0:
            c.greet_cooldown -= 1

        # Emote timer countdown
        if c.emote_ticks > 0:
            c.emote_ticks -= 1
            if c.emote_ticks <= 0:
                c.emote = None

        # Hunger emote trigger
        if c.energy < 25.0 and not c.sleeping and not c.emote:
            c.emote = "hungry"
            c.emote_ticks = 10

        # Leader crown
        if c.clan_id and self.clans.get(c.clan_id, {}).get("leader_id") == c.id:
            c.equipped_item = "crown"
        elif is_night and c.personality == "explorer" and not c.is_predator and not c.is_herbivore:
            # §AR S-2: the torch tradeoff — an explorer's flame restores night
            # sight around it, but the glow draws every wolf's eye.
            if c.equipped_item is None or c.equipped_item == "torch":
                c.equipped_item = "torch"
        elif c.equipped_item == "torch" and not is_night:
            c.equipped_item = None  # daybreak: douse the torch

        # §AR S-5 / §AS L-1: a leader whose clan is at war raises the rally —
        # kin set it as their waypoint and come running.
        if (
            c.clan_id
            and self.clans.get(c.clan_id, {}).get("leader_id") == c.id
            and not c.sleeping
            and not c.is_predator
            and (self.tick + c.id) % 30 == 0
            and len(self.signals) < SIGNALS_MAX
        ):
            at_war_now = False
            for pair, score in self.relations.items():
                if c.clan_id in pair and score <= cfg.rivalry_threshold:
                    at_war_now = True
                    break
            if at_war_now:
                self.signals.append({
                    "x": round(c.x, 2), "y": round(c.y, 2), "kind": "rally",
                    "sender": c.id, "clan_id": c.clan_id or None,
                    "born_tick": self.tick, "ttl": RALLY_SIGNAL_TTL,
                })
        # §AS L-2: retreat when bleeding + evacuation when threatened — independent cadence
        if (
            c.clan_id
            and self.clans.get(c.clan_id, {}).get("leader_id") == c.id
            and not c.sleeping
            and not c.is_predator
            and c.health <= RETREAT_HEALTH_FRAC * c.max_health
            and (self.tick + c.id) % 20 == 0
            and len(self.signals) < SIGNALS_MAX
        ):
            self.signals.append({
                "x": round(c.x, 2), "y": round(c.y, 2), "kind": "retreat",
                "sender": c.id, "clan_id": c.clan_id or None,
                "born_tick": self.tick, "ttl": 30,
            })
        if (
            c.clan_id
            and self.clans.get(c.clan_id, {}).get("leader_id") == c.id
            and not c.sleeping
            and not c.is_predator
            and (self.tick + c.id) % 15 == 0
            and len(self.signals) < SIGNALS_MAX
        ):
            fire_near2 = any(self.world.distance(c.x, c.y, f["x"], f["y"]) < 25.0 for f in self.fires)
            flood_near2 = any(rv.get("flood_ticks", 0) > 0 for rv in self.rivers)
            if fire_near2 or flood_near2:
                import math as _m3b
                hx_, hy_ = (self.fires[0]["x"], self.fires[0]["y"]) if self.fires else (c.x, c.y)
                dxl, dyl = self.world.delta(hx_, hy_, c.x, c.y)
                dl = _m3b.hypot(dxl, dyl) or 1e-6
                ex = c.x + dxl/dl*18.0; ey = c.y + dyl/dl*18.0
                self.signals.append({
                    "x": round(c.x, 2), "y": round(c.y, 2), "kind": "evacuate",
                    "sender": c.id, "clan_id": c.clan_id or None,
                    "born_tick": self.tick, "ttl": 40,
                    "evac_x": round(ex % self.config.width, 2),
                    "evac_y": round(ey % self.config.height, 2),
                })

        # Evaluate skills and dynamic epithets
        if self.tick % 10 == 0:
            self._update_creature_skills_and_titles(c)

        # 0. Night rest: after dark, creatures make for the nearest house and
        # those who win a bed sleep — half the hunger, multiplied healing.
        # Predators cannot fit through the doorway (§L refuge).
        # Starving creatures skip sleep to forage — survival over comfort.
        c.sleeping = False
        c.indoors = False
        ratio = c.energy / cfg.energy_max if cfg.energy_max > 0 else 1.0
        is_starving = ratio <= cfg.starving_ratio
        if (
            cfg.sleep_enabled
            and cfg.shelter_enabled
            and not c.is_predator
            and not c.is_herbivore
            and not is_starving
            and is_night
            and c.alarm_wake_ticks <= 0  # §AR S-1: a war cry wakes sleepers
            and not self._is_nocturnal_forager(c)  # BH-8: nocturnal mutants forage through the night
            and houses
        ):
            # Assigned roof (room-aware, §L); if we're not under it but stand
            # inside ANOTHER roof with a free bed, rest here instead of
            # trekking across the village. No bed ⇒ no rest: capacity is law.
            # §AT-3: only own-clan or unclaimed roofs may be entered.
            if not roof_resolved:
                assigned_roof = self._house_for(c, houses)
                roof_resolved = True
            assigned = assigned_roof
            home: House | None = None
            if (
                assigned is not None
                and self._inside_house(c, assigned)
                and (not self.config.house_claim_enabled or assigned.clan_id == 0 or assigned.clan_id == c.clan_id)
            ):
                home = assigned
            else:
                for h in self._house_grid.get((int(c.x // 50), int(c.y // 50)), []):
                    if (
                        not h.is_ruin
                        and (not self.config.house_claim_enabled or h.clan_id == 0 or h.clan_id == c.clan_id)
                        and self._inside_house(c, h)
                        and self._beds.get(h.id, 0) < self._house_beds(h)
                    ):
                        home = h
                        break
            if home is not None and self._claim_bed(home):
                c.indoors = True
                c.sleeping = True
                if not c.emote:
                    c.emote = "sleep"
                    c.emote_ticks = 15
                # Oral Lore transmission in houses: elders pass XP to sleeping youth
                if c.stage == "elder" and c.clan_id and (self.tick + c.id) % 15 == 0:
                    skills_dict = getattr(c, "skills", {})
                    if skills_dict:
                        best_skill = max(skills_dict, key=lambda k: skills_dict.get(k, 0.0))
                        # §AP: the Dimensional Rift carries elder lore across generations
                        _totem_lore = getattr(self, "_clan_totem_stats", {}).get(c.clan_id, {}).get("lore", 0.0) if self.config.totems_enabled else 0.0
                        lore_xp = 0.15 * (1.0 + _totem_lore)
                        for o, d2 in w.query_radius_with_dist_sq(c.x, c.y, 6.0):
                            if isinstance(o, Creature) and o.clan_id == c.clan_id and o.stage in ("infant", "juvenile"):
                                if hasattr(o, "skills") and isinstance(o.skills, dict):
                                    o.skills[best_skill] = o.skills.get(best_skill, 0.0) + lore_xp
                if cfg.knowledge_enabled:
                    self._learn(c, "safe", home.x, home.y)  # §X: this roof is safe
                    # §AR S-3: inherited memory — an elder at rest passes its
                    # sense of home and food grounds to the young asleep near.
                    if c.stage == "elder" and (self.tick + c.id) % 20 == 0:
                        for o in w.query_radius(c.x, c.y, 5.0):
                            if (
                                isinstance(o, Creature)
                                and o.clan_id == c.clan_id
                                and o.stage in ("infant", "juvenile")
                            ):
                                safe = self._fact_fresh(c, "safe")
                                food = self._fact_fresh(c, "food")
                                if safe is not None:
                                    o.facts["safe"] = dict(safe, conf=ORAL_LORE_CONF, tick=self.tick)
                                if food is not None:
                                    o.facts["food"] = dict(food, conf=ORAL_LORE_CONF, tick=self.tick)
                stage_mult = STAGE_ENERGY_MULT.get(c.stage, 1.0) if c.generation > 0 else 1.0
                # §AO Phase C: a lit hearth is total sanctuary — the fire
                # purges every trace of chill and halts the night's burn.
                hearth_sanctuary = bool(getattr(home, "hearth_lit", False))
                if hearth_sanctuary:
                    c.chill = 0.0
                else:
                    c.energy -= cfg.energy_decay_per_tick * cfg.sleep_energy_mult * stage_mult * self._metabolic_cost(c)
                if c.infected and cfg.disease_enabled:
                    c.energy -= cfg.disease_energy_drain
                    c.health -= 2.0 * cfg.disease_lethality
                else:
                    # §AT-4 H-0: healing is not free — a body running on fumes
                    # cannot mend itself, even asleep. §AQ PH-0: mending costs.
                    if (c.energy / cfg.energy_max) > HEALTH_REGEN_MIN_ENERGY:
                        regen = 0.15 * cfg.rest_recovery_mult
                        # §AO Phase C: the hearth's warmth knits wounds fast.
                        if hearth_sanctuary:
                            regen += HEARTH_SANCTUARY_HEAL
                        # §AT-4 H-2: plague-response bylaw — the main house is an
                        # infirmary and its beds heal twice as well.
                        ci_sl = self.clans.get(c.clan_id) if c.clan_id else None
                        if (
                            isinstance(ci_sl, dict)
                            and (ci_sl.get("bylaws") or {}).get("plague_response")
                            and ci_sl.get("main_house_id") == home.id
                        ):
                            regen *= INFIRMARY_REGEN_MULT
                        regen *= 1.0 + (getattr(self, "_clan_totem_stats", {}).get(c.clan_id, {}).get("defense", 0.0) if self.config.totems_enabled and c.clan_id else 0.0)  # totem vitality heals faster
                        if c.heal_bonus_ticks > 0:
                            regen += c.heal_bonus_amount  # §AT-4 H-1: supper keeps working
                        healed = min(c.max_health, c.health + regen) - c.health
                        if healed > 0:
                            c.health += healed
                            c.energy = max(0.0, c.energy - healed * HEALING_ENERGY_COST)
                if c.energy <= 0:
                    if getattr(c, "food_basket", 0) > 0:
                        c.food_basket -= 1
                        c.energy = min(cfg.energy_max, c.energy + cfg.energy_from_food * 0.9)
                        c.ticks_since_meal = 0
                        c.meals += 1
                        c.give_ups.clear()
                    else:
                        self._kill(c, "starvation")
                elif c.health <= 0:
                    self._kill(c, "disease")
                elif c.age >= c.lifespan:
                    self._kill(c, "old_age")
                # Asleep means STILL: no steering, no wandering, no fleeing —
                # the body does not move again until dawn (or death).
                return
            else:
                # §AO Phase E: wanted a roof, found no bed — tonight's housing
                # shortage census (drives emergency construction).
                self._bed_overflow_night = getattr(self, "_bed_overflow_night", 0) + 1

        # §AQ PH-7: torpor — a starving body in killing cold shuts down:
        # 5% burn, unconscious and defenceless until the air warms or it dies.
        if (
            not c.is_predator
            and ratio <= TORPOR_ENERGY_RATIO
            and self.ambient_at(c.x, c.y) < HYPOTHERMIA_TEMP
        ):
            stage_mult_t = STAGE_ENERGY_MULT.get(c.stage, 1.0)
            c.energy -= cfg.energy_decay_per_tick * TORPOR_BURN_MULT * stage_mult_t * self._metabolic_cost(c)
            if not c.emote or c.emote == "hungry":
                c.emote = "sleep"
                c.emote_ticks = 15
            if c.energy <= 0:
                self._kill(c, "starvation")
            elif c.age >= c.lifespan:
                self._kill(c, "old_age")
            return

        # Clan bylaws and task board modifiers (§AL). §AS L-0: with no living
        # leader the institutions pause — no rationing, no duty weights.
        clan_info = self.clans.get(c.clan_id) if c.clan_id else None
        leaderless = bool(c.clan_id) and not getattr(self, "_leader_pos", {}).get(c.clan_id)
        if leaderless:
            bylaws: dict = {}
            task_board: dict = {}
            harvester_weight = 1.0
            guard_weight = 1.0
            # The interregnum slowly makes everyone timid.
            if self.rng.random() < LEADERLESS_CAUTIOUS_CHANCE:
                c.personality = "cautious"
        else:
            bylaws = clan_info.get("bylaws", {}) if isinstance(clan_info, dict) else {}
            task_board = clan_info.get("task_board", {}) if isinstance(clan_info, dict) else {}
            harvester_weight = task_board.get("harvester_weight", 1.0)
            guard_weight = task_board.get("guard_weight", 1.0)
        is_rationing = bylaws.get("rationing", False)

        # Field consumption: eat from personal reserve when hungry or starving
        # Under rationing bylaw, preserve emergency reserve until energy < 35.0
        eat_thresh = 35.0 if is_rationing else 55.0
        if getattr(c, "food_basket", 0) > 0 and not c.sleeping and c.energy < eat_thresh:
            c.food_basket -= 1
            c.energy = min(cfg.energy_max, c.energy + cfg.energy_from_food * 0.9)
            c.ticks_since_meal = 0
            c.meals += 1
            c.give_ups.clear()
            c.emote = "craft"
            c.emote_ticks = 15



        # §AR S-3: the priest as living oracle — periodically broadcasts the
        # clan's best knowledge to every ear within signal range.
        if (
            c.caste == "Priest"
            and cfg.knowledge_enabled
            and not c.sleeping
            and (self.tick + c.id) % PRIEST_ORACLE_INTERVAL == 0
        ):
            oracle_fact = self._fact_to_share(c)
            if oracle_fact is not None and len(self.signals) < SIGNALS_MAX:
                self.signals.append({
                    "x": round(c.x, 2), "y": round(c.y, 2),
                    "kind": "knowledge", "sender": c.id,
                    "clan_id": c.clan_id or None,
                    "born_tick": self.tick, "ttl": 15,
                    "fact": dict(oracle_fact),
                })

        # Priests heal injured / infected clanmates — full healing rounds near
        # the settlement seat (§AT-4 H-1), a lighter touch on the road.
        if c.caste == "Priest" and not c.sleeping and (self.tick + c.id) % 8 == 0:
            main_house = None
            if c.clan_id:
                main_hid = self.clans.get(c.clan_id, {}).get("main_house_id")
                if main_hid:
                    mh = self.world.entities.get(main_hid)
                    if isinstance(mh, House) and not mh.is_ruin and w.distance_sq(c.x, c.y, mh.x, mh.y) <= cfg.territory_radius * cfg.territory_radius:
                        main_house = mh
            heal_radius = LEADER_AURA_RADIUS if main_house is not None else 4.0
            heal_amount = 15.0 * (1.0 + c.skills.get("healing", 0.0) / 20.0)
            for o, d2 in w.query_radius_with_dist_sq(c.x, c.y, heal_radius):
                if isinstance(o, Creature) and o.clan_id == c.clan_id and o.id != c.id:
                    if (o.health < min(100.0, o.max_health) or o.infected) and o.id in w.entities:
                        o.health = min(o.max_health, o.health + heal_amount)
                        o.infected = False
                        c.skills["healing"] = c.skills.get("healing", 0.0) + 1.5
                        c.emote = "heal"
                        c.emote_ticks = 20
                        o.emote = "cheer"
                        o.emote_ticks = 20
                        if not hasattr(o, "trust") or o.trust is None:
                            o.trust = {}
                        o.trust[c.id] = min(100.0, o.trust.get(c.id, 0.0) + 15.0)
                        if not hasattr(c, "trust") or c.trust is None:
                            c.trust = {}
                        c.trust[o.id] = min(100.0, c.trust.get(o.id, 0.0) + 5.0)
                        break

        # §AT-4 H-2: wound dressing — healthy kin bandage the hurt, halving
        # how long a wound lingers (and with it the infection window).
        if (
            c.health >= DRESS_MIN_HEALTH
            and not c.sleeping
            and not c.is_predator
            and not c.is_herbivore
            and (self.tick + c.id) % 4 == 0
        ):
            for o, d2 in w.query_radius_with_dist_sq(c.x, c.y, DRESS_RADIUS):
                if (
                    isinstance(o, Creature)
                    and o.id != c.id
                    and o.clan_id == c.clan_id
                    and o.wound_severity >= 1
                    and o.wound_ticks > 10
                    and not o.wound_dressed
                    and o.id in w.entities
                ):
                    o.wound_ticks = max(10, o.wound_ticks // 2)
                    o.wound_dressed = True
                    c.emote = "heal"
                    c.emote_ticks = 12
                    o.morale = min(100.0, o.morale + MORALE_EAT_RESTORE * 0.5)  # care lifts the spirit
                    if not hasattr(o, "trust") or o.trust is None:
                        o.trust = {}
                    o.trust[c.id] = min(100.0, o.trust.get(c.id, 0.0) + 8.0)
                    break

        # Altruistic feeding & basket hauling
        if getattr(c, "food_basket", 0) > 0 and not c.sleeping:
            if c.personality == "altruistic" and (self.tick + c.id) % 6 == 0:
                for o, d2 in w.query_radius_with_dist_sq(c.x, c.y, 5.0):
                    if not isinstance(o, Creature) or o.id == c.id:
                        continue
                    kin = o.clan_id == c.clan_id
                    if not (o.energy < 40.0 or o.stage in ("infant", "juvenile")) or o.id not in w.entities:
                        continue
                    # §AM E.1 sacred hospitality — bread broken with a stranger
                    # buys mutual non-aggression; rivals at open feud refuse it.
                    if o.clan_id and c.clan_id and o.clan_id != c.clan_id:
                        pair = self._relation_pair(c.clan_id, o.clan_id)
                        if self.relations.get(pair, 0) <= cfg.rivalry_threshold // 2:
                            continue
                        c.food_basket -= 1
                        o.energy = min(cfg.energy_max, o.energy + 30.0)
                        c.emote = "love"
                        c.emote_ticks = 15
                        o.emote = "cheer"
                        o.emote_ticks = 15
                        self._bump_relation(c.clan_id, o.clan_id, 6)
                        o.trust[c.id] = min(100.0, o.trust.get(c.id, 0.0) + 20.0) if isinstance(o.trust, dict) else o.trust
                        c.trust[o.id] = min(100.0, c.trust.get(o.id, 0.0) + 10.0) if isinstance(c.trust, dict) else c.trust
                        if self.tick - self._last_hospitality_tick >= HOSPITALITY_GAP:
                            self._last_hospitality_tick = self.tick
                            self._emit(
                                HistoryEvent(
                                    type="hospitality",
                                    tick=self.tick + 1,
                                    entity_id=c.id,
                                    caste=c.caste,
                                    x=round(c.x, 2), y=round(c.y, 2),
                                    payload={"a": c.clan_id, "b": o.clan_id,
                                             "a_name": self.clans.get(c.clan_id, {}).get("name"),
                                             "b_name": self.clans.get(o.clan_id, {}).get("name")},
                                )
                            )
                        break
                    if kin and o.clan_id == c.clan_id:
                        o.energy = min(cfg.energy_max, o.energy + 30.0)
                        c.food_basket -= 1
                        c.emote = "love"
                        c.emote_ticks = 15
                        o.emote = "cheer"
                        o.emote_ticks = 15
                        if not hasattr(o, "trust") or o.trust is None:
                            o.trust = {}
                        o.trust[c.id] = min(100.0, o.trust.get(c.id, 0.0) + 20.0)
                        if not hasattr(c, "trust") or c.trust is None:
                            c.trust = {}
                        c.trust[o.id] = min(100.0, c.trust.get(o.id, 0.0) + 10.0)
                        break

            elif c.indoors or (c.clan_id and c.clan_id in clan_house_map and self.world.distance(c.x, c.y, clan_house_map[c.clan_id].x, clan_house_map[c.clan_id].y) <= 8.0):
                if c.clan_id and c.clan_id in self.clans:
                    clan_obj = self.clans[c.clan_id]
                    curr = float(clan_obj.get("larder", 0.0))
                    clan_obj["larder"] = min(cfg.larder_capacity, curr + c.food_basket * 18.0)
                c.food_basket = 0

        # At adulthood the world judges the irregular: consumed if far from
        # regular, otherwise demoted to the lowest of the regular orders.
        # Phase 5.4 Morphological Mercy: suspend euthanasia when η>0.3 and mercy enabled
        if not c.matured and c.irregularity > 0 and c.age >= cfg.adult_age:
            c.matured = True
            if c.irregularity >= cfg.euthanasia_threshold:
                # safeguard mercy
                try:
                    mercy = bool(getattr(self.config, "safeguard_morph_mercy", False)) and float(getattr(self, "_safeguard_eta", 0.0)) > 0.3
                except Exception:
                    mercy = False
                if not mercy:
                    self._kill(c, "euthanasia")
                    return
            c.sides = 3
            c.iso_angle = min(c.iso_angle, 59.5)
            c.caste = caste_name(c.sides, "polygon", c.iso_angle)
            traits = traits_for(c.caste)
            c.speed = traits.speed
            c.radius = RADIUS_BY_CASTE.get(c.caste, DEFAULT_RADIUS)
            event = HistoryEvent(
                type="demotion",
                tick=self.tick + 1,
                entity_id=c.id,
                caste=c.caste,
                x=round(c.x, 2),
                y=round(c.y, 2),
                payload={"irregularity": c.irregularity},
            )
            self.history.append(event)
            self._events_this_tick.append(event.model_dump(mode="json"))
            if self.on_event is not None:
                self.on_event(event)

        # Hunger and life stage drive perception range and urgency; the
        # caste's Sight Recognition (aided by Fog) sets the base reach.
        ratio = c.energy / cfg.energy_max if cfg.energy_max > 0 else 0.0
        if ratio <= cfg.starving_ratio:
            c.status = "starving"
        elif ratio <= cfg.hungry_ratio:
            c.status = "hungry"
        else:
            c.status = ""

        stage_speed, stage_sight = STAGE_MULT[c.stage]
        perceive = cfg.perceive_radius * c.sight_mult * stage_sight * env_sight
        # §AR S-2: age dims the eyes further — elders see ×0.9 again.
        if c.stage == "elder":
            perceive *= ELDER_SIGHT_PENALTY
        # §AT-4 H-2: scars dim the eyes forever.
        if c.scars:
            perceive *= SCAR_SIGHT_MULT ** c.scars
        # §AU CPU: hoist clan totem stats once (law-preserving, _clan_totem_stats is final mult).
        _totem = getattr(self, "_clan_totem_stats", {}).get(c.clan_id, {}) if c.clan_id and self.config.totems_enabled else {}
        # Avatar sight (§P/AP): All-Seeing Vertex +40% sight, clarity pierces dark …
        perceive *= 1.0 + _totem.get("sight", 0.0)
        # §AP: the All-Seeing Vertex sees clearly even in the dark of the world —
        # its clarity recovers the night/fog dimming.
        clarity = _totem.get("clarity", 0.0)
        if clarity and env_sight < 1.0:
            perceive /= max(0.05, 1.0 - clarity * (1.0 - env_sight))
        speed_mult = 1.0
        if c.status == "hungry":
            perceive *= cfg.hungry_perceive_mult
        elif c.status == "starving":
            perceive *= cfg.desperate_perceive_mult
            speed_mult = cfg.desperate_speed_mult
        # Avatar speed (§AP): Celestial Strike hunting/fleeing burst
        if _totem and (c.is_predator or perceive > cfg.perceive_radius):
            speed_mult *= 1.0 + _totem.get("speed", 0.0)

        # §AO Phase D: pitch black — outdoors at night non-predator sight
        # contracts to a hand's width ahead. Predators hunt by nose; the
        # All-Seeing Vertex pierces the dark; a torch pushes it back (§AR S-2).
        if (
            is_night
            and not c.indoors
            and not c.is_predator
            and not c.sleeping
        ):
            dark_cap = PITCH_BLACK_SIGHT * (1.0 + _totem.get("clarity", 0.0))
            if c.equipped_item == "torch":
                dark_cap = max(dark_cap, cfg.perceive_radius * env_sight)
            else:
                # a torch within TORCH_LIGHT_RADIUS lights the ground here too
                _bearers = getattr(self, "_torch_bearers", None)
                if _bearers is not None and len(_bearers) <= 24:
                    _t2 = TORCH_LIGHT_RADIUS * TORCH_LIGHT_RADIUS
                    for o in _bearers:
                        if isinstance(o, Creature) and o.equipped_item == "torch" and not o.indoors:
                            if w.distance_sq(c.x, c.y, o.x, o.y) <= _t2:
                                dark_cap = max(dark_cap, cfg.perceive_radius * env_sight * 0.9)
                                break
                else:
                    for o in w.query_radius(c.x, c.y, TORCH_LIGHT_RADIUS):
                        if isinstance(o, Creature) and o.equipped_item == "torch" and not o.indoors:
                            dark_cap = max(dark_cap, cfg.perceive_radius * env_sight * 0.9)
                            break
            perceive = min(perceive, dark_cap)

        # trait paranoid/bold nudges flee threshold (§S); §AR S-0 starvation
        # dulls fear (all in _effective_fear_radius); §AP the Eternal Hearth
        # calms its people through the night.
        fear_radius_eff = self._effective_fear_radius(c, is_night=is_night)

        # §AS L-0 Morale aura — the leader's presence is a stat: kin within
        # LEADER_AURA_RADIUS see farther and burn less; a dead leader casts
        # gloom over the whole clan (weaker eyes, faster burn, deeper fear).
        clan_info_aura = self.clans.get(c.clan_id) if c.clan_id else None
        leader_alive = bool(clan_info_aura and clan_info_aura.get("leader_id"))
        # §AS L-5: a crown's aura reaches half again as far
        aura_radius = LEADER_AURA_RADIUS * (
            MONARCHY_AURA_MULT if (clan_info_aura or {}).get("governance") == "monarchy" else 1.0
        )
        lpos = getattr(self, "_leader_pos", {}).get(c.clan_id) if c.clan_id else None
        in_aura = False
        if leader_alive and lpos is not None:
            in_aura = w.distance_sq(c.x, c.y, lpos[0], lpos[1]) <= aura_radius * aura_radius
            if in_aura:
                perceive *= 1.0 + LEADER_SIGHT_BONUS
                fear_radius_eff = max(1.0, fear_radius_eff - LEADER_CALM)

        elif c.clan_id:
            perceive *= 1.0 - LEADER_SIGHT_BONUS
            fear_radius_eff += LEADERLESS_FEAR
        # §AT-4 H-1: sickness dims the eyes.
        perceive *= self._health_sight_mult(c.health)
        # 1. Predation: hunt (predator) / flee (prey) — highest priority after sleep
        # §AQ PH-2: scent rides the wind — a nose reaches farther toward UPWIND
        # targets (the smell travels downwind to the sniffer), so approaching
        # from downwind is the stealth play for hunter and hunted alike.
        hunt_target: Creature | None = None
        flee_target: Creature | None = None
        # §AX P1: batch spatial queries — single radius sweep for predation
        # + food perception + scent, instead of 6 separate generator calls.
        _batch_r = perceive
        _hunt_r_tmp = 0.0
        _batch_list: list[tuple[Entity, float]] = []  # will be filled below
        scent_boost = 0.0
        wx_s, wy_s = self._cos_wind, self._sin_wind
        if cfg.predation_enabled:
                # §AQ PH-2: asymmetric noses — smelling a wolf beats hunting by
                # scent, so prey read the wind twice as well as predators do.
                scent_boost = (
                    (WIND_SCENT_MULT * self.wind_speed * 0.5 if c.is_predator
                     else WIND_SCENT_MULT * self.wind_speed)
                    if cfg.scent_enabled else 0.0
                )
                if c.is_predator and c.bite_cooldown <= 0:
                    _hunt_r_tmp = cfg.hunt_radius + _totem.get("hunt_radius", 0.0)
                    if is_night:
                        _hunt_r_tmp *= PREDATOR_NIGHT_SIGHT
                    if self.campfires:
                        for cf in self.campfires:
                            if w.distance_sq(c.x, c.y, cf["x"], cf["y"]) <= CAMPFIRE_LIGHT_RADIUS * CAMPFIRE_LIGHT_RADIUS:
                                _hunt_r_tmp = 0.0
                                break
                    _batch_r = max(_batch_r, _hunt_r_tmp * 2.0, _hunt_r_tmp * (1.0 + scent_boost))
                elif not c.is_predator:
                    _batch_r = max(_batch_r, fear_radius_eff * (1.0 + scent_boost), cfg.fear_radius)
        if is_night and c.status in ("hungry", "starving") and not c.is_predator:
            _batch_r = max(_batch_r, FOOD_SCENT_RADIUS)
        # §AU CPU: extend batch to cover social micro-queries so every later
        # scan reuses the same hash lookup (law-preserving superset).
        _batch_r = max(_batch_r, YIELD_RADIUS, cfg.flock_radius, PRIEST_CALM_RADIUS, TORCH_LIGHT_RADIUS, DRESS_RADIUS, CAMPFIRE_LIGHT_RADIUS, max(8.0, cfg.fear_radius))
        # Use fast list variant to avoid generator overhead (1627) — always populated for food perception
        _batch_list: list[tuple[Entity, float]] = w.query_radius_with_dist_sq_list(c.x, c.y, _batch_r) if _batch_r > 0 else []  # type: ignore[assignment]
        if cfg.predation_enabled and c.is_predator and c.bite_cooldown <= 0:
                # Find nearest non-predator prey within hunt_radius (+2 Celestial Strike avatar)
                # §AO Phase B: night vision +40% in the dark; a lit campfire
                # is a wall of light no beast will cross.
                hunt_r = _hunt_r_tmp
                best_prey: Creature | None = None
                best_prey_d_sq = math.inf
                # §AR S-2: a torch bearer glows in the dark — visible twice
                # as far as any honest shadow.
                torch_glow_r2 = (hunt_r * 2.0) ** 2 if hunt_r > 0 else 0.0
                sight_r2 = hunt_r * hunt_r if hunt_r > 0 else math.inf
                # AY fix: reuse batched query (_batch_list already contains all prey within max search radius)
                for o, d2 in _batch_list:
                    if not isinstance(o, Creature) or o.id == c.id or o.is_predator:
                        continue
                    if o.id not in w.entities or o.indoors:
                        continue  # indoors prey are safe (predator refuge)
                    # §AR S-2: a torch bearer glows twice as far as any shadow
                    if getattr(o, "equipped_item", None) == "torch":
                        if d2 < torch_glow_r2 and d2 < best_prey_d_sq:
                            best_prey_d_sq, best_prey = d2, o
                        continue
                    # §AQ PH-2: beyond base sight only UPWIND prey is smelled
                    if d2 >= sight_r2:
                        if scent_boost <= 0.0:
                            continue
                        d = math.sqrt(d2) or 1e-6
                        dx, dy = w.delta(o.x, o.y, c.x, c.y)  # prey relative to predator
                        upwind = max(0.0, -(dx * wx_s + dy * wy_s) / d)
                        eff = hunt_r * (1.0 + scent_boost * upwind)
                        if d > eff:
                            continue
                    # §AU-fix: NEAREST always wins — a passing far candidate
                    # must never replace a closer one.
                    if d2 < best_prey_d_sq:
                        best_prey_d_sq, best_prey = d2, o
                # §AR S-2: terrain camouflage — prey standing in mature cover
                # are only visible at 80% of the hunter's reach.
                if (
                    best_prey is not None
                    and best_prey_d_sq > (hunt_r * CAMOUFLAGE_HUNT_MULT) ** 2
                ):
                    for veg, vd2 in w.query_radius_with_dist_sq(
                        best_prey.x, best_prey.y, CAMOUFLAGE_RANGE,
                    ):
                        if (
                            isinstance(veg, Food)
                            and veg.growth >= 1.0
                            and veg.variant in ("berry", "grass", "grain")
                        ):
                            best_prey, best_prey_d_sq = None, math.inf
                            break
                if best_prey is not None:
                    if best_prey_d_sq <= cfg.eat_radius * cfg.eat_radius:
                        # Bite — instant kill, predator feeds
                        self._kill(best_prey, "predation")
                        c.energy = min(cfg.energy_max, c.energy + cfg.energy_from_prey)
                        c.bite_cooldown = cfg.bite_cooldown
                        c.meals += 1
                        self._emit(
                            HistoryEvent(
                                type="predation",
                                tick=self.tick + 1,
                                entity_id=c.id,
                                caste=c.caste,
                                x=round(c.x, 2),
                                y=round(c.y, 2),
                                payload={"prey": best_prey.id, "prey_caste": best_prey.caste},
                            )
                        )
                        # Skip further steering this tick — predator just fed
                        hunt_target = None
                    else:
                        hunt_target = best_prey
                        # §AO Phase B: past midnight beasts converge in packs —
                        # the finder shares the kill with any wolf in earshot.
                        if tod > PACK_HOUR and len(self.signals) < SIGNALS_MAX:
                            self.signals.append({
                                "x": round(c.x, 2), "y": round(c.y, 2),
                                "kind": "pack", "sender": c.id,
                                "clan_id": None, "born_tick": self.tick, "ttl": 12,
                                "threat_x": round(hunt_target.x, 2),
                                "threat_y": round(hunt_target.y, 2),
                            })
                        # §AR S-1: three or more beasts together raise a war
                        # cry that carries twice as far and wakes sleepers.
                        if len(self.signals) < SIGNALS_MAX and (
                            self.rng.random() < 0.15
                        ):
                            pack_n = 0
                            for o2, d22 in w.query_radius_with_dist_sq(c.x, c.y, PACK_RADIUS):
                                if isinstance(o2, Creature) and o2.is_predator and o2.id != c.id:
                                    pack_n += 1
                            if pack_n >= 2:
                                self.signals.append({
                                    "x": round(c.x, 2), "y": round(c.y, 2),
                                    "kind": "warcry", "sender": hunt_target.id,
                                    "clan_id": None, "born_tick": self.tick,
                                    "ttl": max(6, int(cfg.signal_radius * WARCRY_RADIUS_MULT / cfg.signal_speed)) if cfg.signal_speed > 0 else 24,
                                    "threat_x": round(c.x, 2), "threat_y": round(c.y, 2),
                                })
        elif cfg.predation_enabled and not c.is_predator:
            # Normal creature / prey: flee the nearest predator
            # §AR S-2: forward cone = 120° full vision; rear hemisphere
            # detects at half range (smell ignores facing).
            # §AR S-2 canon: beyond half range an Isosceles triangle is
            # misread as a predator 30% of the time.
            # §AR S-4: kin are recognized by scent up close — no panic.
            ca, sa = math.cos(c.angle), math.sin(c.angle)
            best_pred: Creature | None = None
            best_pred_d_sq = math.inf
            fear_r_sq = cfg.fear_radius * cfg.fear_radius
            # §AX P1: reuse batched list instead of separate query
            for o, d2 in _batch_list:
                if d2 > fear_r_sq or not isinstance(o, Creature) or not o.is_predator or o.id not in w.entities:
                    continue
                dxo, dyo = w.delta(c.x, c.y, o.x, o.y)
                fwd = dxo * ca + dyo * sa  # >0: in the forward half
                visual_limit = (
                    fear_radius_eff if fwd >= VISION_CONE_COS
                    else fear_radius_eff * REAR_SIGHT_MULT
                )
                if d2 <= visual_limit * visual_limit:
                    if d2 < best_pred_d_sq:
                        best_pred_d_sq, best_pred = d2, o
                    continue
                # §AQ PH-2: beyond sight only an UPWIND predator reeks
                if scent_boost > 0.0:
                    d = math.sqrt(d2)
                    upwind = max(0.0, -(dxo * wx_s + dyo * wy_s) / (d or 1e-6))
                    eff = fear_radius_eff * (1.0 + scent_boost * upwind)
                    if d <= eff and d2 < best_pred_d_sq:
                        best_pred_d_sq, best_pred = d2, o
            if best_pred is None:
                # phantom wolves: far isosceles silhouettes misread 30%/tick
                # reuse batch (already contains fear_radius candidates)
                for o, d2 in _batch_list:
                    if d2 > fear_r_sq or not isinstance(o, Creature) or o.is_predator or o.id == c.id:
                        continue
                    if o.sides != 3 or (o.clan_id and o.clan_id == c.clan_id):
                        continue  # §AR S-4: kin smell like kin
                    if d2 > (cfg.fear_radius * 0.5) ** 2:
                        continue  # misreading only happens far out
                    if self.rng.random() >= TRIANGLE_FALSE_ALARM:
                        continue
                    best_pred_d_sq, best_pred = d2, o
                    break
            flee_target = best_pred

        # 2. Perceive the nearest meal — food or the fallen. Diet strictness (§O) filters.
        # §X-fix: the Carnivore caste hunts the living and scavenges the dead —
        # it never grazes fields. A predator that could eat plants out-competes
        # every caste for the bounty and the world dies into a wolf monoculture
        # (production incident @ tick 34k: 800 predators, zero clan members).
        target: Entity | None = None
        best_sq = perceive * perceive
        # §AU CPU: batch is superset for all micro-radii — no second hash lookup.
        _food_iter = _batch_list
        for e, d2 in _food_iter:
            if d2 > perceive * perceive:
                continue
            if e.kind not in ("food", "corpse") or e.id in self._eaten:
                continue
            if c.is_predator and e.kind == "food":
                continue
            # A meal given up on (unreachable behind stone or wall) is ignored
            # until its memory fades — the hungry look elsewhere instead of
            # grinding against the obstacle until they starve.
            if cfg.food_giveup_ticks > 0 and (
                self.tick - c.give_ups.get(e.id, -cfg.food_giveup_ticks)
                < cfg.food_giveup_ticks
            ):
                continue
            # Diet & preference (§O): herbivore↔plants, carnivore↔meat, omnivore both; strictness gates.
            if cfg.diet_strictness > 0:
                if c.is_herbivore and e.kind == "corpse":
                    if self.rng.random() < cfg.diet_strictness:
                        continue
                if c.is_predator and e.kind == "food":
                    if self.rng.random() < cfg.diet_strictness:
                        continue
                # higher castes prefer richer food when strict: skip grass if berry nearby (approx)
                if not c.is_herbivore and not c.is_predator and e.kind == "food" and cfg.diet_strictness > 0.5:
                    if isinstance(e, Food) and e.variant == "grass":
                        if self.rng.random() < 0.7:
                            continue
                # herbivores avoid poisonous when strict
                if c.is_herbivore and isinstance(e, Food) and e.variant == "poisonous" and cfg.diet_strictness > 0.3:
                    if self.rng.random() < cfg.diet_strictness:
                        continue
                # trait greedy: prefer richer food (grain/berry/corpse) over grass
                if c.trait == "greedy" and isinstance(e, Food) and e.variant == "grass":
                    if self.rng.random() < 0.45:
                        continue

            effective_d2 = d2
            # Health & status based dietary preferences (§AM)
            if isinstance(e, Food):
                if (c.health < 70.0 or c.infected) and e.variant == "medicinal_herb":
                    effective_d2 *= 0.2  # high attraction to healing herbs
                elif c.status == "starving" and e.variant == "grain":
                    effective_d2 *= 0.4  # high attraction to calorie-dense grain
                else:
                    # §AM E.1 geometric gastronomy — castes keep their own table
                    weight = CASTE_DIET_WEIGHTS.get(c.caste, {}).get(e.variant)
                    if weight is not None:
                        effective_d2 *= weight
            elif e.kind == "corpse" and c.caste == "Soldier":
                effective_d2 *= 0.6  # soldiers crave high-protein rations

            if effective_d2 < best_sq:
                best_sq, target = effective_d2, e

        # §AR S-0 Food scent: ripe plants smell through the dark. A hungry or
        # starving creature whose eyes fail at night still catches the scent
        # of mature food within FOOD_SCENT_RADIUS — no more blind starvation.
        if (
            target is None
            and is_night
            and c.status in ("hungry", "starving")
            and not c.is_predator
        ):
            scent_sq = FOOD_SCENT_RADIUS * FOOD_SCENT_RADIUS
            _scent_iter = _batch_list
            for e, d2 in _scent_iter:
                if d2 > FOOD_SCENT_RADIUS * FOOD_SCENT_RADIUS:
                    continue
                if e.kind != "food" or e.id in self._eaten:
                    continue
                f = cast(Food, e)
                if f.growth < 1.0:
                    continue  # only ripe plants carry a scent worth following
                # a scented meal behind stone/wall stays grudged (§X fixes)
                if cfg.food_giveup_ticks > 0 and (
                    self.tick - c.give_ups.get(e.id, -cfg.food_giveup_ticks)
                    < cfg.food_giveup_ticks
                ):
                    continue
                if d2 < scent_sq:
                    scent_sq = d2
                    target = e
                    best_sq = d2
        # §AN A.3 war-chirp targeting — a soldier facing a rival marks the
        # nearest open-feud enemy as the rally target (one gated query).
        enemy_target: Creature | None = None
        if (
            cfg.vocalizations_enabled
            and c.caste == "Soldier"
            and c.clan_id
            and hunt_target is None
            and flee_target is None
        ):
            er2 = max(8.0, cfg.fear_radius)
            best_enemy_d = er2 * er2 + 1e-9
            _war_chirp_iter = ((o, d2) for o, d2 in _batch_list if d2 <= er2 * er2)
            for o, d2 in _war_chirp_iter:
                if not isinstance(o, Creature) or o.clan_id == c.clan_id or not o.clan_id:
                    continue
                pair_z = self.relations.get(self._relation_pair(c.clan_id, o.clan_id), 0)
                if self._zone_of(pair_z) != -1 or d2 >= best_enemy_d:
                    continue
                best_enemy_d, enemy_target = d2, o

        # §AC Desperation: the starving may hunt the living. Sated/hungry
        # creatures never do; a cooldown separates desperate kills.
        prey_target: Creature | None = None
        if (
            cfg.cannibalism_enabled
            and c.status == "starving"
            and c.cannibal_cooldown <= 0
            and not c.is_predator
            and not c.is_herbivore
        ):
            prey_target = self._cannibal_prey(c, perceive)

        # §X Knowledge — firsthand experience: seen meal, seen predator.
        if cfg.knowledge_enabled:
            if target is not None and isinstance(target, Food):
                self._learn(c, "food", target.x, target.y)
            if flee_target is not None:
                self._learn(c, "danger", flee_target.x, flee_target.y)
            if c.indoors:
                home_fact = inside_house_obj or assigned_roof or (self._house_for(c, houses) if not roof_resolved else None)
                if home_fact is not None:
                    self._learn(c, "safe", home_fact.x, home_fact.y)
        if c.signal_cooldown > 0:
            c.signal_cooldown -= 1
        # §Q Communication — food and alarm calls
        if cfg.communication_enabled:
            # Food call: well-fed finds food → calls clan-mates
            if target is not None and c.energy / cfg.energy_max > cfg.hungry_ratio and c.signal_cooldown == 0:
                if self.rng.random() < cfg.food_call_rate:
                    self.signals.append({"x": c.x, "y": c.y, "kind": "food", "sender": c.id, "clan_id": c.clan_id or None, "born_tick": self.tick, "ttl": 15, "food_x": target.x, "food_y": target.y})
                    c.signal_cooldown = 8
                # §AN B.2 forager scent trails — rich finds leave a breadcrumb
                # line home for hungry kin to follow (rain washes scent faster)
                elif (
                    isinstance(target, Food)
                    and target.variant in ("grain", "berry", "medicinal_herb")
                    and len(self.signals) < SIGNALS_MAX
                    and self.rng.random() < TRAIL_DROP_CHANCE * (2.0 if self.weather == "clear" else 1.0)
                ):
                    self.signals.append({
                        "x": round(c.x, 2), "y": round(c.y, 2), "kind": "trail",
                        "sender": c.id, "clan_id": c.clan_id or None,
                        "born_tick": self.tick, "ttl": SCENT_TTL, "food_x": round(target.x, 2), "food_y": round(target.y, 2),
                    })
            # Alarm call: sees predator → alarm; teeth-close → a cry for help (§X)
            if flee_target is not None and c.signal_cooldown == 0:
                close = (
                    cfg.help_call_enabled
                    and cfg.knowledge_enabled
                    and w.distance_sq(c.x, c.y, flee_target.x, flee_target.y) < (cfg.help_radius * 0.6) ** 2
                )
                if self.rng.random() < cfg.alarm_call_rate or close:
                    kind = "help" if close else "alarm"
                    sg: dict[str, Any] = {"x": c.x, "y": c.y, "kind": kind, "sender": c.id, "clan_id": c.clan_id or None, "ttl": 12}
                    if kind == "help":
                        sg.update({"threat_x": round(flee_target.x, 2), "threat_y": round(flee_target.y, 2), "threat_clan": flee_target.clan_id or None})
                    self.signals.append(sg)
                    c.signal_cooldown = 10
            # §X Teaching: broadcast the freshest fact to clan-mates
            if cfg.knowledge_enabled and c.signal_cooldown == 0 and self.rng.random() < cfg.knowledge_share_rate:
                fact_msg = self._fact_to_share(c)
                if fact_msg is not None:
                    self.signals.append({"x": c.x, "y": c.y, "kind": "knowledge", "sender": c.id, "clan_id": c.clan_id or None, "born_tick": self.tick, "ttl": 12, "fact": fact_msg})
                    c.signal_cooldown = 14
            # Recruitment: sated clan-mate near starving one calls toward remembered food (§Q Care)
            food_fact = self._fact_fresh(c, "food") if cfg.knowledge_enabled else None
            remembered_food = (food_fact["x"], food_fact["y"]) if food_fact is not None else None
            if remembered_food is not None and c.energy / cfg.energy_max > 0.6:
                # PERF (no logic change): flock_radius ⊆ _batch_r (see §AX P1
                # superset construction), and both queries visit cells in
                # identical dx-outer/dy-inner bucket order — filtering the
                # batch by d2 yields the exact same sequence with no re-query.
                _fr2 = cfg.flock_radius * cfg.flock_radius
                for other, _d2 in _batch_list:
                    if _d2 > _fr2:
                        continue
                    if not isinstance(other, Creature) or other.id == c.id:
                        continue
                    if other.clan_id != c.clan_id:
                        continue
                    if other.energy / cfg.energy_max > cfg.starving_ratio:
                        continue  # only starving
                    if c.signal_cooldown == 0 and self.rng.random() < 0.08:
                        self.signals.append({"x": c.x, "y": c.y, "kind": "food", "sender": c.id, "clan_id": c.clan_id or None, "born_tick": self.tick, "ttl": 12, "food_x": remembered_food[0], "food_y": remembered_food[1]})
                        c.signal_cooldown = 12
                        break

        # §AR S-4: smell made physical — scent marks and trails ride the air.
        if cfg.scent_enabled and not c.sleeping and len(self.signals) < SIGNALS_MAX:
            # territorial marking: sentries and chiefs scent the border
            if (
                c.clan_id
                and (c.caste == "Soldier" or self.clans.get(c.clan_id, {}).get("leader_id") == c.id)
                and (self.tick + c.id) % 45 == 0
            ):
                mh = self.world.entities.get(self.clans[c.clan_id].get("main_house_id")) if self.clans[c.clan_id].get("main_house_id") is not None else None
                if isinstance(mh, House):
                    d_home = w.distance(c.x, c.y, mh.x, mh.y)
                    if abs(d_home - cfg.territory_radius) <= cfg.territory_radius * 0.35:
                        ttl = max(10, int(SCENT_TTL / 2)) if self.weather in ("rain", "storm") else SCENT_TTL
                        self.signals.append({
                            "x": round(c.x, 2), "y": round(c.y, 2), "kind": "territory",
                            "sender": c.id, "clan_id": c.clan_id or None,
                            "born_tick": self.tick, "ttl": min(ttl, 90),
                        })
            # forager/prey scent: every moving body leaves a fading trail;
            # rain washes it thin. Predators leave their own — prey learn fear.
            if (self.tick + c.id) % 40 == 0 and (c.status or c.is_predator):
                ttl = max(8, SCENT_TTL // 2) if self.weather in ("rain", "storm") else SCENT_TTL
                kind = "pred_scent" if c.is_predator else "prey_scent"
                self.signals.append({
                    "x": round(c.x, 2), "y": round(c.y, 2), "kind": kind,
                    "sender": c.id, "clan_id": c.clan_id or None,
                    "born_tick": self.tick, "ttl": ttl,
                })
            # §AR S-6/S-7: the sick reek of sickness; the healthy take note.
            if (
                cfg.disease_enabled
                and c.infected
                and (self.tick + c.id) % 20 == 0
            ):
                self.signals.append({
                    "x": round(c.x, 2), "y": round(c.y, 2), "kind": "disease",
                    "sender": c.id, "clan_id": c.clan_id or None,
                    "born_tick": self.tick, "ttl": 30,
                })

        # §AN Phase A — every caste has a voice: the priest's liturgy, the
        # woman's peace-hum, the soldier's war-chirp.
        if cfg.vocalizations_enabled and c.signal_cooldown == 0 and not c.is_predator and not c.is_herbivore:
            if c.caste == "Priest" and self.rng.random() < CHANT_CHANCE:
                # Sonorous liturgy — calm flows outward through the clan
                self.signals.append({"x": round(c.x, 2), "y": round(c.y, 2), "kind": "chant", "sender": c.id, "clan_id": c.clan_id or None, "born_tick": self.tick, "ttl": 10})
                c.signal_cooldown = 16
            elif c.shape == "line" and self.rng.random() < HUM_CHANCE:
                # Peace-hum — polygons step aside; corridors stay walkable (§C law)
                self.signals.append({"x": round(c.x, 2), "y": round(c.y, 2), "kind": "hum", "sender": c.id, "clan_id": c.clan_id or None, "born_tick": self.tick, "ttl": 8})
                c.signal_cooldown = 14
            elif (
                c.caste == "Soldier"
                and (hunt_target is not None or flee_target is not None
                     or prey_target is not None or enemy_target is not None)
                and self.rng.random() < WARCHIRP_CHANCE
            ):
                # War-chirp — allied soldiers rally onto the flagged target
                threat = hunt_target or flee_target or prey_target or enemy_target
                self.signals.append({
                    "x": round(c.x, 2), "y": round(c.y, 2), "kind": "war",
                    "sender": c.id, "clan_id": c.clan_id or None, "born_tick": self.tick, "ttl": 10,
                    "threat_x": round(threat.x, 2), "threat_y": round(threat.y, 2),
                })
                c.signal_cooldown = 12

        # §AN B — tactile recognition: touching vertices in peace builds trust;
        # an elder's blessing touch passes a sliver of skill to the young; a
        # friendly artisan's chime opens the basket for a gift.
        if (
            cfg.vocalizations_enabled
            and c.greet_cooldown <= 0
            and not c.sleeping
            and not c.is_predator
            and not c.is_herbivore
            and (self.tick + c.id) % 29 == 0
        ):
            for o, d2 in w.query_radius_with_dist_sq(c.x, c.y, 1.2):
                if not isinstance(o, Creature) or o.id == c.id or o.sleeping:
                    continue
                if o.is_predator or o.is_herbivore:
                    continue
                kin = o.clan_id and o.clan_id == c.clan_id
                if not kin:
                    pair = self._relation_pair(c.clan_id, o.clan_id) if c.clan_id and o.clan_id else None
                    if pair is None or self.relations.get(pair, 0) <= cfg.rivalry_threshold // 2:
                        continue  # no greetings across open feuds
                c.greet_cooldown = 60
                o.trust[c.id] = min(100.0, o.trust.get(c.id, 0.0) + GREET_TRUST) if isinstance(o.trust, dict) else o.trust
                c.trust[o.id] = min(100.0, c.trust.get(o.id, 0.0) + GREET_TRUST) if isinstance(c.trust, dict) else c.trust
                # Elder blessing touch — skill flows to the next generation
                if c.stage == "elder" and o.stage in ("infant", "juvenile"):
                    skills_d = getattr(c, "skills", {})
                    if skills_d:
                        best_skill = max(skills_d, key=lambda k: skills_d.get(k, 0.0))
                        o.skills[best_skill] = o.skills.get(best_skill, 0.0) + ELDER_TOUCH_XP
                        o.emote = "cheer"
                        o.emote_ticks = 10
                # Artisan trade chime — greeting gifts from the basket
                if c.caste == "Artisan" and c.food_basket > 0 and o.energy < 65.0:
                    c.food_basket -= 1
                    o.energy = min(cfg.energy_max, o.energy + ARTISAN_GIFT_ENERGY)
                    o.emote = "cheer"
                    o.emote_ticks = 12
                    self.signals.append({"x": round(c.x, 2), "y": round(c.y, 2), "kind": "chime", "sender": c.id, "clan_id": c.clan_id or None, "born_tick": self.tick, "ttl": 8})
                    if not kin and c.clan_id and o.clan_id:
                        self._bump_relation(c.clan_id, o.clan_id, 1)
                break

        # §AN E.1 ruin archaeology — explorers reading old walls recover lost
        # technique: farming & foraging insight, vague lore of the old farms.
        if cfg.knowledge_enabled and (self.tick + c.id) % 23 == 7 and c.personality == "explorer":
            for e in w.query_radius(c.x, c.y, 4.0):
                if e.kind == "house" and getattr(e, "is_ruin", False):
                    c.skills["farming"] = c.skills.get("farming", 0.0) + 0.06
                    c.skills["foraging"] = c.skills.get("foraging", 0.0) + 0.04
                    self._learn(c, "food", e.x + 2.0, e.y - 2.0, conf=0.4)  # old farms fed these walls
                    break

        # 3. Steer — priority: flee > hunt > home for night > food > wander
        # §Q Hearing signals — clan-mates respond strongly; §X knowledge & help
        signal_food_target = None
        signal_alarm_target = None
        signal_help_target = None
        signal_hum_source = None  # §AN woman's peace-hum — corridor clearing
        best_help_d_sq = math.inf
        alarm_heard_conf = 1.0  # §AR S-1: distance attenuation of the cry
        disease_scent_near = False  # §AR S-6: sickness in the air
        retreat_heard = False  # §AS L-2: the general sounded retreat
        harvest_order = False  # §AS L-2: autumn stores call
        harvest_house: tuple[float, float] | None = None
        if cfg.communication_enabled and self.signals:
            sig_r = cfg.signal_radius
            # §AQ PH-2: sound rides the wind - listeners DOWNWIND of a source
            # hear it farther (the pressure wave drifts with the air).
            snd_boost = SOUND_WIND_MULT * self.wind_speed if cfg.scent_enabled else 0.0
            wx_s, wy_s = self._cos_wind, self._sin_wind
            # §AU O-2: hoisted per-tick constants and a cheap squared
            # far-reject before any wavefront trig runs.
            sig_r2 = sig_r * sig_r
            half_w = cfg.width * 0.5
            half_h = cfg.height * 0.5
            max_hear_d = sig_r * 2.5 * (1.0 + snd_boost)
            max_hear_d2 = max_hear_d * max_hear_d
            best_food_sq = math.inf
            best_alarm_sq = math.inf
            my_dialect = float(self.clans.get(c.clan_id, {}).get("dialect", 0.0)) if c.clan_id else 0.0
            # §AU CPU: grid-gather signals within max_hear_d (law-preserving superset,
            # insertion-order sorted, wrap-aware). O(S) -> O(~5-10) per creature.
            _sg_grid = getattr(self, "_signal_grid", {})
            _sg_cs = getattr(self, "_signal_grid_cs", self.world.cell_size)
            _sg_cols = self.world.cols
            _sg_rows = self.world.rows
            if _sg_grid:
                _rx = int(max_hear_d // _sg_cs) + 1
                _cx0 = int(c.x // _sg_cs) % _sg_cols if _sg_cols else 0
                _cy0 = int(c.y // _sg_cs) % _sg_rows if _sg_rows else 0
                if self.world.config.boundary == "wrap":
                    _cand: list[tuple[int, dict]] = []
                    # PERF (no logic change): cell repeats are impossible when
                    # the visit range fits the grid — skip the seen-set, keep
                    # the sort (visit order still isn't insertion order).
                    _span = 2 * _rx + 1
                    _need_seen = _span > _sg_cols or _span > _sg_rows
                    _seen_cells = set() if _need_seen else None
                    for _dx in range(-_rx, _rx + 1):
                        for _dy in range(-_rx, _rx + 1):
                            _cx = (_cx0 + _dx) % _sg_cols if _sg_cols else 0
                            _cy = (_cy0 + _dy) % _sg_rows if _sg_rows else 0
                            if _need_seen:
                                if (_cx, _cy) in _seen_cells:
                                    continue
                                _seen_cells.add((_cx, _cy))
                            bucket = _sg_grid.get((_cx, _cy))
                            if bucket:
                                _cand.extend(bucket)
                    # sorting ≤1 element is a no-op — skip it (identical order)
                    if len(_cand) > 1:
                        _cand.sort(key=lambda t: t[0])
                    _iter_signals = (sg for _, sg in _cand)
                else:
                    # clamp: collect cells overlapping max_hear_d square
                    _cand = []
                    if _sg_grid:
                        # fallback to direct collection via bounding box
                        for (gx, gy), bucket in _sg_grid.items():
                            # quick cell-center far reject
                            cx_cell = (gx + 0.5) * _sg_cs
                            cy_cell = (gy + 0.5) * _sg_cs
                            if abs(cx_cell - c.x) > max_hear_d + _sg_cs and abs(cy_cell - c.y) > max_hear_d + _sg_cs:
                                continue
                            _cand.extend(bucket)
                        _cand.sort(key=lambda t: t[0])
                    _iter_signals = (sg for _, sg in _cand) if _cand else iter(self.signals)
                    # For clamp small maps, if grid sparse, fallback to filtered linear scan is still cheaper
                    if not _cand:
                        _iter_signals = (sg for sg in self.signals)
                        # apply same far-reject quickly inside loop anyway
            else:
                _iter_signals = iter(self.signals)
            for sg in _iter_signals:
                dxw = sg["x"] - c.x
                if dxw > half_w:
                    dxw -= cfg.width
                elif dxw < -half_w:
                    dxw += cfg.width
                adx = dxw if dxw >= 0 else -dxw
                if adx > max_hear_d:
                    continue
                dyw = sg["y"] - c.y
                if dyw > half_h:
                    dyw -= cfg.height
                elif dyw < -half_h:
                    dyw += cfg.height
                ady = dyw if dyw >= 0 else -dyw
                if ady > max_hear_d:
                    continue
                d2 = dxw * dxw + dyw * dyw
                if d2 > max_hear_d2:
                    continue  # beyond every reach: no wavefront math needed
                # §AQ PH-8: news travels at finite speed — the wavefront
                # expands from the source (faster downwind) and a listener
                # too far away simply hasn't heard it yet.
                born = sg.get("born_tick")
                if born is not None and cfg.signal_speed > 0.0:
                    age_t = self.tick - born
                    dl = math.sqrt(d2) or 1e-6
                    tail = (dxw * self._cos_wind + dyw * self._sin_wind) / dl
                    if tail <= 0.0:
                        # no tailwind: plain radius check, squared
                        speed0 = cfg.signal_speed
                        if d2 > age_t * age_t * speed0 * speed0:
                            continue
                    else:
                        speed = cfg.signal_speed * (1.0 + 0.4 * self.wind_speed * tail)
                        if dl > age_t * speed:
                            continue
                if d2 > sig_r2:
                    # §AQ PH-2: beyond base range only the downwind ear catches
                    # the call - and never through a roof. Downwind means the
                    # WIND carries the call TOWARD the listener: align
                    # (listener - source) with the wind vector.
                    if snd_boost <= 0.0 or c.indoors or d2 >= (sig_r * 2.5) ** 2:
                        continue
                    d_snd = math.sqrt(d2)
                    dxs, dys = w.delta(sg["x"], sg["y"], c.x, c.y)  # source rel. listener
                    downwind = max(0.0, -(dxs * wx_s + dys * wy_s) / d_snd)
                    if d_snd > sig_r * (1.0 + snd_boost * downwind):
                        continue
                kind = sg["kind"]
                # §AQ PH-2: roofs muffle the world - indoors creatures cannot
                # hear alarms or cries for help raised out in the open.
                if (
                    c.indoors
                    and kind in ("alarm", "help", "boom")
                    and not self._point_in_any_house(sg["x"], sg["y"])
                ):
                    continue
                # clan weighting: clan-mates always hear; strangers hear less,
                # the less our dialects agree (§AN E.2 linguistic drift)
                is_kin = sg.get("clan_id") and sg.get("clan_id") == c.clan_id
                if not is_kin:
                    if cfg.dialect_drift_enabled:
                        sender_dialect = float(self.clans.get(sg.get("clan_id") or -1, {}).get("dialect", 0.0))
                        ignore_p = max(0.45, min(0.95, 0.45 + abs(my_dialect - sender_dialect) * 0.5))
                    else:
                        ignore_p = 0.65
                    if self.rng.random() < ignore_p:
                        continue
                if (kind == "food" or kind == "trail") and c.status in ("hungry", "starving"):
                    # §AN B.2: scent trails point at the patch like a food call;
                    # food signals point to food_x/food_y if present, else sender pos
                    fx = sg.get("food_x", sg["x"])
                    fy = sg.get("food_y", sg["y"])
                    df2 = w.distance_sq(c.x, c.y, fx, fy)
                    if df2 < best_food_sq:
                        best_food_sq = df2
                        signal_food_target = (fx, fy)
                elif kind == "prey_scent" and c.is_predator:
                    # §AR S-4: a nose to the ground — wolves track fresh trails
                    # even before hunger bites.
                    if hunt_target is None and flee_target is None and d2 < best_food_sq:
                        best_food_sq = d2
                        signal_food_target = (sg["x"], sg["y"])
                elif kind == "pred_scent" and not c.is_predator:
                    # §AR S-4: prey smell wolf-passages and learn the danger
                    self._learn(c, "danger", sg["x"], sg["y"], conf=0.5)
                elif kind == "territory" and cfg.knowledge_enabled:
                    # §AR S-4: a rival's border-stench names its clan as enemy
                    marker_clan = sg.get("clan_id")
                    if marker_clan and marker_clan != c.clan_id:
                        self._learn_enemy(c, marker_clan)
                elif kind == "disease":
                    # §AR S-6/S-7: sickness has a smell — the healthy mark the
                    # spot dangerous (high castes notice first) and drift home.
                    if not c.infected and c.sides >= 4 and cfg.knowledge_enabled:
                        old_danger = self._fact_fresh(c, "danger")
                        if old_danger is None or float(old_danger.get("conf", 0.0)) < 0.4:
                            self._learn(c, "danger", sg["x"], sg["y"], conf=0.4)
                    u_shelter_bonus = 0.2  # applied below via flag
                    disease_scent_near = True
                elif kind == "chant" and cfg.vocalizations_enabled and is_kin:
                    # §AN A.1 liturgy: panic drains away; the starving find heart
                    c.panic_ticks = 0
                    c.calm_ticks = max(c.calm_ticks, 20)
                elif kind == "hum" and cfg.vocalizations_enabled and c.shape != "line":
                    # §AN A.2 peace-hum: polygons yield the corridor
                    if signal_hum_source is None or d2 < w.distance_sq(c.x, c.y, *signal_hum_source):
                        signal_hum_source = (sg["x"], sg["y"])
                elif kind == "war" and cfg.vocalizations_enabled and c.caste == "Soldier" and is_kin:
                    # §AN A.3 war-chirp: allied soldiers converge on the flagged target
                    tx, ty = sg.get("threat_x", sg["x"]), sg.get("threat_y", sg["y"])
                    td2 = w.distance_sq(c.x, c.y, tx, ty)
                    if td2 < best_help_d_sq:
                        best_help_d_sq = td2
                        signal_help_target = (tx, ty)
                elif kind == "chime" and cfg.envoys_enabled and c.caste == "Soldier" and is_kin:
                    # §AN C.3 boundary stone rings — sentries walk the border
                    tx, ty = sg.get("stone_x", sg["x"]), sg.get("stone_y", sg["y"])
                    td2 = w.distance_sq(c.x, c.y, tx, ty)
                    if td2 < best_help_d_sq:
                        best_help_d_sq = td2
                        signal_help_target = (tx, ty)
                elif kind == "pack" and cfg.predation_enabled and c.is_predator:
                    # §AO Phase B: pack convergence — beasts rally to the
                    # flagged prey past midnight.
                    tx, ty = sg.get("threat_x", sg["x"]), sg.get("threat_y", sg["y"])
                    td2 = w.distance_sq(c.x, c.y, tx, ty)
                    if hunt_target is None and flee_target is None and td2 < best_help_d_sq:
                        best_help_d_sq = td2
                        signal_help_target = (tx, ty)
                elif kind == "rally" and is_kin:
                    # §AR S-5: the banner is raised — kin mark the spot;
                    # only hearts above despair answer the call.
                    if (
                        c.morale >= MORALE_RALLY_MIN
                        and getattr(c, "waypoints", None) is not None
                    ):
                        c.waypoints["rally"] = (sg["x"], sg["y"])
                    # §AS L-1: a rally before battle sharpens every blade.
                    if c.caste == "Soldier" and c.morale >= MORALE_RALLY_MIN:
                        c.combat_boost_ticks = COMBAT_BOOST_TICKS
                elif kind == "retreat" and is_kin:
                    # §AS L-2: the general is bleeding — everyone home, now.
                    retreat_heard = True
                elif kind == "harvest" and is_kin:
                    # §AS L-2: the granary calls — farmers work the fields hard.
                    harvest_order = True
                    harvest_house = (sg.get("house_x", sg["x"]), sg.get("house_y", sg["y"]))
                elif kind == "evacuate" and is_kin:
                    # §AS L-2: fire and flood — run THIS way.
                    ex2, ey2 = sg.get("evac_x", sg["x"]), sg.get("evac_y", sg["y"])
                    if getattr(c, "waypoints", None) is not None:
                        c.waypoints["evacuate"] = (ex2, ey2)
                elif kind == "interpret" and is_kin:
                    # §AS L-6: the chief's reading of God's law bends the
                    # clan's mood for a while — war-hunger or blessing-calm.
                    if sg.get("tone") == "war" and c.caste == "Soldier":
                        c.combat_boost_ticks = max(c.combat_boost_ticks, LAW_INTERPRET_TICKS)
                        c.morale = min(100.0, c.morale + 2.0)
                    else:
                        c.calm_ticks = max(c.calm_ticks, LAW_INTERPRET_TICKS)
                        c.morale = min(100.0, c.morale + 3.0)
                elif kind == "omen" and cfg.omens_enabled and is_kin:
                    # §AN E.3 the priest has seen the turning of the season
                    c.prepared_ticks = PREPARED_TICKS
                elif kind == "joy" and is_kin:
                    # §AR S-7: birth is literally good news — a small gift of
                    # energy and health rides the cheer.
                    c.energy = min(cfg.energy_max, c.energy + float(sg.get("joy_energy", 2.0)))
                    c.health = min(c.max_health, c.health + float(sg.get("joy_health", 1.0)))
                    c.morale = min(100.0, c.morale + MORALE_EAT_RESTORE * 0.25)
                    if not c.emote:
                        c.emote = "cheer"
                        c.emote_ticks = 12
                elif kind == "danger_scent" and cfg.scent_enabled:
                    # §AN B.3: the young and vulnerable learn to shun death sites
                    if c.stage in ("infant", "juvenile") or c.health < 50.0:
                        self._learn(c, "danger", sg["x"], sg["y"], conf=0.6)
                elif kind == "grief" and is_kin:
                    # §AR S-7: shared loss bonds survivors — kin pause a few
                    # ticks to mourn, and those present draw closer together.
                    # Nobody mourns mid-flight or mid-ford: an active threat
                    # or moving water overrides grief.
                    if flee_target is None and (
                        not self.rivers or not self._in_river_band(c.x, c.y)
                    ):
                        c.pause_ticks = 1 + (c.id % 3)
                        if not c.emote:
                            c.emote = "grief"
                            c.emote_ticks = 12
                    for oid in sg.get("witnesses", ()):
                        if oid != c.id:
                            cur = c.trust.get(oid, 0.0)
                            c.trust[oid] = min(100.0, cur + 5.0)
                elif kind == "knowledge" and cfg.knowledge_enabled:
                    self._hear_fact(c, sg.get("fact"), sg.get("sender"))
                    f = (sg.get("fact") or {})
                    if (
                        f.get("kind") == "food"
                        and c.status in ("hungry", "starving")
                        and signal_food_target is None
                    ):
                        df2 = w.distance_sq(c.x, c.y, f.get("x", sg["x"]), f.get("y", sg["y"]))
                        if df2 < best_food_sq:
                            best_food_sq = df2
                            signal_food_target = (f.get("x", sg["x"]), f.get("y", sg["y"]))
                elif sg["kind"] == "help" and cfg.help_call_enabled and is_kin:
                    # §X Mobbing: rally to the defender's aid — warriors first,
                    # the peaceful lag behind, high castes only when bold.
                    rank = YIELD_RANK.get(c.caste, 3)
                    if rank >= 5 and c.trait != "bold":
                        continue
                    if c.trait == "peaceful" and self.rng.random() < 0.7:
                        continue
                    if not c.is_predator and not c.is_herbivore and d2 < best_help_d_sq:
                        best_help_d_sq = d2
                        signal_help_target = (sg.get("threat_x", sg["x"]), sg.get("threat_y", sg["y"]))
                elif sg["kind"] == "alarm" and flee_target is None:
                    if d2 < best_alarm_sq:
                        best_alarm_sq = d2
                        # §AR S-1: confidence fades with distance — far alarms
                        # move us less than close ones.
                        signal_alarm_target = sg
                        alarm_heard_conf = max(0.0, 1.0 - math.sqrt(d2) / (sig_r * (1.0 + snd_boost)))
                elif sg["kind"] == "warcry":
                    # §AR S-1: a predator pack's war cry carries twice as far
                    # and tears sleeping prey from their beds.
                    if c.alarm_wake_ticks < 20:
                        c.alarm_wake_ticks = 20
                    if flee_target is None and d2 < best_alarm_sq:
                        best_alarm_sq = d2
                        signal_alarm_target = sg
                        alarm_heard_conf = max(0.0, 1.0 - math.sqrt(d2) / (sig_r * WARCRY_RADIUS_MULT))
        # §X Danger zones: remembered predator sightings are avoided (§BE-E1 always-on, even when well-fed)
        danger_avoid_target = None
        if cfg.knowledge_enabled and flee_target is None:
            danger_fact = self._fact_fresh(c, "danger")
            if danger_fact is not None and "x" in danger_fact:
                dd2 = w.distance_sq(c.x, c.y, danger_fact["x"], danger_fact["y"])
                if dd2 < (cfg.fear_radius * 1.5) ** 2:
                    danger_avoid_target = (danger_fact["x"], danger_fact["y"])
        # §AL Multi-Objective Utility Engine & Purposeful Tactical Steering
        if flee_target is not None:
            self._fleeing_ids.add(c.id)
        u_flee = 0.0
        if flee_target is not None:
            u_flee = 1.2
            if c.personality == "cautious":
                u_flee += 0.3
            elif c.personality == "brave" and c.caste == "Soldier":
                u_flee -= 0.3
            if c.health < 40.0:
                u_flee += 0.4
        # §AS L-0: the clan shock — for LEADER_SHOCK_PANIC_TICKS after the
        # leader's death every member startles at shadows.
        if c.panic_ticks > 0:
            u_flee += LEADER_SHOCK_U_FLEE
        # §AR S-5: panic is contagious — a running kinspanics the flock;
        # a priest's presence steadies it.
        if not c.is_predator and not c.is_herbivore:
            panicked_mate = False
            priest_near = False
            for o, d2o in w.query_radius_with_dist_sq(c.x, c.y, max(cfg.flock_radius, PRIEST_CALM_RADIUS)):
                if not isinstance(o, Creature) or o.id == c.id or o.clan_id != c.clan_id:
                    continue
                if o.id in getattr(self, "_fleeing_ids", ()) or o.panic_ticks > 0:
                    panicked_mate = True
                if o.caste == "Priest" and d2o <= PRIEST_CALM_RADIUS * PRIEST_CALM_RADIUS:
                    priest_near = True
            if panicked_mate and (
                flee_target is not None or self._fact_fresh(c, "danger") is not None
            ):
                # §AR S-5: contagion amplifies awareness — kin who smell the
                # threat secondhand join the flight; the truly oblivious stay.
                u_flee += PANIC_CONTAGION
            if priest_near and u_flee > 0.2:
                u_flee -= PRIEST_CALM_BONUS

        # §AR S-1: habituation — the same alarm ringing for many ticks stops
        # moving anyone; a fresh source startles anew.
        if signal_alarm_target is not None:
            sender_id = signal_alarm_target.get("sender", -1)
            if sender_id == c.last_alarm_sender:
                c.alarm_streak += 1
            else:
                c.last_alarm_sender = sender_id
                c.alarm_streak = 0
        else:
            c.alarm_streak = 0
            c.last_alarm_sender = -1
        u_alarm = 0.0
        if signal_alarm_target is not None and flee_target is None:
            u_alarm = max(0.25, alarm_heard_conf)
            if c.alarm_streak >= ALARM_HABITUATION_TICKS:
                u_alarm *= ALARM_HABITUATED_U

        u_help = 0.0
        if signal_help_target is not None and flee_target is None:
            u_help = 0.8
            if c.personality == "brave" or c.equipped_item == "spear":
                u_help += 0.35
            if c.personality == "cautious" or c.health < 35.0:
                u_help -= 0.45
        # §AS L-1: bodyguard clustering — soldiers hold their chief's side
        # above any other call; the cluster emerges from the utility system.
        if (
            c.caste == "Soldier"
            and c.clan_id
            and not c.is_predator
            and flee_target is None
        ):
            lpos_bg = getattr(self, "_leader_pos", {}).get(c.clan_id)
            aura_r = LEADER_AURA_RADIUS * (
                MONARCHY_AURA_MULT if self.clans.get(c.clan_id, {}).get("governance") == "monarchy" else 1.0
            )
            if lpos_bg is not None and w.distance_sq(c.x, c.y, *lpos_bg) <= aura_r * aura_r:
                # override any far help cry — the chief is the priority
                signal_help_target = lpos_bg
                u_help = max(u_help, BODYGUARD_U_HELP)

        u_hunt = 1.15 if hunt_target is not None else 0.0
        u_cannibal = 1.25 if prey_target is not None else 0.0

        u_shelter = 0.0
        if cfg.sleep_enabled and not c.is_predator and not c.is_herbivore and houses:
            if is_night:
                u_shelter = 1.5
            elif self.weather in ("storm", "rain") or c.chill > 5.0:
                u_shelter = 0.85
            elif c.personality == "cautious" and (c.energy < 40.0 or c.health < 50.0):
                u_shelter = 0.7
            # §AN E.3: the omen was heeded — worshippers drift home early
            if u_shelter < 1.5 and c.prepared_ticks > 0:
                u_shelter += 0.4
            # §AO Phase B: the dusk rush — at first dusk instinct drops every
            # non-essential plan and sprints for home before nightfall.
            if DUSK_TOD <= tod < 0.78 and u_shelter < DUSK_SHELTER_URGE:
                u_shelter = DUSK_SHELTER_URGE
            # §AR S-6: sickness smells like danger — heads for the roof.
            if disease_scent_near:
                u_shelter += 0.2
            # §AR S-6: pentagon+ castes read the sky the instant it turns —
            # they seek cover before the first drop lands.
            if (
                c.sides >= 5
                and self.weather in ("rain", "storm")
                and self.tick - getattr(self, "_weather_since_tick", self.tick) <= WEATHER_ANTICIPATION_TICKS
                and u_shelter < 1.0
            ):
                u_shelter += 0.5
            # §AS L-2: a retreat command overrides every other drive.
            if retreat_heard:
                u_shelter = max(u_shelter, RETREAT_SHELTER_URGE)

        # §AT-4 H-1: a wounded creature seeks herbs even on a full stomach.
        herb_need = (
            isinstance(target, Food)
            and target.variant == "medicinal_herb"
            and c.health < 60.0
        )
        u_eat = 0.0
        if target is not None and (c.is_predator or c.energy <= 0.85 * cfg.energy_max or herb_need):
            energy_deficit = 1.0 - (c.energy / cfg.energy_max) if cfg.energy_max > 0 else 0.5
            u_eat = 0.6 + energy_deficit * 0.8
            if herb_need:
                u_eat += 0.55
            if c.personality == "greedy":
                u_eat += 0.25
            if c.status == "starving":
                u_eat += 0.5
            # §AS L-2: the harvest order — autumn hands work faster.
            if harvest_order:
                farmer_spec = self.clans.get(c.clan_id, {}).get("specialization", {}).get("farmer", 0.33) if c.clan_id else 0.33
                if farmer_spec >= 0.4 or c.skills.get("farming", 0.0) >= 6.0:
                    u_eat += 0.25
            # §AT-4 H-2: despair blunts provision — but raw hunger overrides
            # despair, and the body always mends its spirit a little each tick.
            if c.morale < MORALE_FORAGE_MIN and c.status == "" and not herb_need:
                u_eat = 0.0

        u_signal_food = 0.0
        if signal_food_target is not None and target is None and c.status in ("hungry", "starving"):
            u_signal_food = 0.75

        # §BE-E1 lower utility when well-fed so it doesn't hijack foraging
        if danger_avoid_target is not None and flee_target is None:
            u_danger_avoid = 0.60 if c.status in ("hungry", "starving") else 0.35
        else:
            u_danger_avoid = 0.0

        # §AR S-6: the thermal gradient is a sense — freezing bodies drift
        # toward known heat, cooking bodies toward water; the very young and
        # the very old feel it most.
        u_thermal = 0.0
        thermal_target: tuple[float, float] | None = None
        if not c.indoors and not c.sleeping:
            amb_here = self.ambient_at(c.x, c.y)
            sens = 2.0 if c.stage in ("infant", "elder") else 0.0
            if amb_here < HYPOTHERMIA_TEMP + sens:
                near_heat: tuple[float, float] | None = None
                best_hd2 = 625.0  # 25 units
                for cf in self.campfires:
                    hd2 = w.distance_sq(c.x, c.y, cf["x"], cf["y"])
                    if hd2 < best_hd2:
                        best_hd2, near_heat = hd2, (cf["x"], cf["y"])
                for ffire in self.fires:
                    hd2 = w.distance_sq(c.x, c.y, ffire["x"], ffire["y"])
                    if hd2 < best_hd2:
                        best_hd2, near_heat = hd2, (ffire["x"], ffire["y"])
                for hhh in houses:
                    hh2 = cast(House, hhh)
                    if hh2.hearth_lit:
                        hd2 = w.distance_sq(c.x, c.y, hh2.x, hh2.y)
                        if hd2 < best_hd2:
                            best_hd2, near_heat = hd2, (hh2.x, hh2.y)
                if near_heat is not None and not c.is_predator:
                    thermal_target = near_heat
                    u_thermal = THERMAL_SEEK_UTILITY * (1.0 + sens * 0.25)
            elif c.body_temp > HYPERTHERMIA_TEMP - 2.0 and self.rivers:
                # overheated: make for the nearest riverbank (safe cooling)
                best_rv = min(self.rivers, key=lambda rv: self._river_dy(c.y, rv["cy"]))
                bank_y = best_rv["cy"] - best_rv["hw"] - 1.0 if c.y < best_rv["cy"] else best_rv["cy"] + best_rv["hw"] + 1.0
                if abs(bank_y - c.y) > 1.0:
                    thermal_target = (c.x, bank_y)
                    u_thermal = THERMAL_SEEK_UTILITY

        # Purposeful Waypoint Navigation (§AL)
        waypoint_target = None
        u_waypoint = 0.0
        if not c.is_predator and not c.is_herbivore:
            # §AN C.1: an emissary walks a diplomatic mission above all else
            mission = getattr(c, "mission", None)
            if isinstance(mission, dict) and mission.get("type") == "peace":
                ex_, ey_ = mission.get("x", 0.0), mission.get("y", 0.0)
                if w.distance_sq(c.x, c.y, ex_, ey_) > 4.0:
                    waypoint_target = (ex_, ey_)
                    u_waypoint = 1.1
                elif getattr(c, "waypoints", None) is not None:
                    c.waypoints["rich_food"] = (round(ex_, 2), round(ey_, 2))
            elif getattr(c, "waypoints", None) and isinstance(c.waypoints, dict):
                # §AS L-2: fire and flood — the evacuation overrides all errands.
                if "evacuate" in c.waypoints:
                    ex3, ey3 = c.waypoints["evacuate"]
                    if w.distance_sq(c.x, c.y, ex3, ey3) <= 4.0:
                        del c.waypoints["evacuate"]
                    else:
                        waypoint_target = (ex3, ey3)
                        u_waypoint = 2.0
                # §AR S-5: the rally overrides every errand — first time
                # leaders actually coordinate movement.
                elif "rally" in c.waypoints and c.morale >= MORALE_RALLY_MIN:
                    rx2, ry2 = c.waypoints["rally"]
                    if w.distance_sq(c.x, c.y, rx2, ry2) <= 4.0:
                        del c.waypoints["rally"]  # arrived; banner lowered
                    else:
                        waypoint_target = (rx2, ry2)
                        u_waypoint = 1.0
                elif c.status in ("hungry", "starving") and target is None and "rich_food" in c.waypoints:
                    rx, ry = c.waypoints["rich_food"]
                    if w.distance_sq(c.x, c.y, rx, ry) > 4.0:
                        waypoint_target = (rx, ry)
                        u_waypoint = 0.55
                elif c.personality == "explorer" and target is None and "patrol" in c.waypoints:
                    px, py = c.waypoints["patrol"]
                    if w.distance_sq(c.x, c.y, px, py) > 4.0:
                        waypoint_target = (px, py)
                        u_waypoint = 0.45

        # Task Board scaling (§AL)
        u_eat *= harvester_weight
        u_waypoint *= harvester_weight
        if c.caste == "Soldier":
            u_help *= guard_weight

        # Tactical Formations & Actions

        # §AU O-1: allocation-free argmax — direct scalar comparisons instead
        # of building a list of tuples every creature tick.
        top_util = u_flee
        top_action = "flee"
        if u_alarm > top_util:
            top_util, top_action = u_alarm, "alarm"
        if u_help > top_util:
            top_util, top_action = u_help, "help"
        if u_cannibal > top_util:
            top_util, top_action = u_cannibal, "cannibal"
        if u_hunt > top_util:
            top_util, top_action = u_hunt, "hunt"
        if u_shelter > top_util:
            top_util, top_action = u_shelter, "shelter"
        if u_eat > top_util:
            top_util, top_action = u_eat, "eat"
        if u_signal_food > top_util:
            top_util, top_action = u_signal_food, "signal_food"
        if u_danger_avoid > top_util:
            top_util, top_action = u_danger_avoid, "danger_avoid"
        if u_waypoint > top_util:
            top_util, top_action = u_waypoint, "waypoint"
        if u_thermal > top_util:
            top_util, top_action = u_thermal, "thermal"

        # Waypoints recording for rich food
        if target is not None and isinstance(target, Food) and target.variant in ("berry", "mushroom") and getattr(c, "waypoints", None) is not None:
            c.waypoints["rich_food"] = (round(target.x, 2), round(target.y, 2))

        # Check if creature is inside a house (§L indoor/outdoor navigation)
        inside_house_obj: House | None = None
        if houses and not c.is_predator:
            grid = getattr(self, "_house_grid", None)
            h_candidates = grid.get((int(c.x // 50), int(c.y // 50)), ()) if grid else houses
            for h in h_candidates:
                if not h.is_ruin and abs(c.x - h.x) <= 14.0 and abs(c.y - h.y) <= 14.0 and self._is_inside_house(c, h):
                    inside_house_obj = h
                    break

        if inside_house_obj is not None:
            if not roof_resolved:
                assigned_roof = self._house_for(c, houses)
                roof_resolved = True
            home = assigned_roof
            if home is not None and getattr(c, "waypoints", None) is not None:
                c.waypoints["home"] = (round(home.x, 2), round(home.y, 2))

            if home is not None and top_action == "shelter" and inside_house_obj.id == home.id and not is_starving:
                # Intended shelter: stay inside and sleep/rest
                tx, ty = inside_house_obj.x, inside_house_obj.y
                dx, dy = w.delta(tx, ty, c.x, c.y)
                desired = math.atan2(dy, dx)
                diff = (desired - c.angle + math.pi) % (2 * math.pi) - math.pi
                c.angle += max(-cfg.steer_turn, min(cfg.steer_turn, diff))
            else:
                # All other conditions (foraging, daytime, active tasks, or overflow seeking another house):
                # navigate cleanly through the doorway to avoid getting stuck in walls!
                ex_x, ex_y = self._house_exit_target(c, inside_house_obj)
                dx, dy = w.delta(ex_x, ex_y, c.x, c.y)
                desired = math.atan2(dy, dx)
                diff = (desired - c.angle + math.pi) % (2 * math.pi) - math.pi
                c.angle += max(-cfg.steer_turn * 1.5, min(cfg.steer_turn * 1.5, diff))





        else:
            if top_util > 0.3:
                if top_action == "flee" and flee_target is not None:
                    # §BE-3 panic burst: imminent danger → instant flip + speed surge
                    # §BE-E4 flanking: non-imminent blends 60% tangent-to-predator-heading + 40% direct-away
                    dx, dy = w.delta(c.x, c.y, flee_target.x, flee_target.y)
                    away = math.atan2(dy, dx)
                    dist2 = w.distance_sq(c.x, c.y, flee_target.x, flee_target.y)
                    if dist2 <= (cfg.eat_radius * 3) ** 2:
                        # imminent: override steer cap, instant 180° flip (§BE-3)
                        c.angle = away
                        speed_mult *= 1.3
                    else:
                        # non-imminent: flank across predator's path (§BE-E4) — also preserves Woman kite flavor
                        if c.shape == "line" or c.caste == "Woman":
                            # Woman/line still kite perpendicular to away (canonical Flatland evasion)
                            desired = away + (math.pi / 2 if (c.id % 2 == 0) else -math.pi / 2)
                        else:
                            pred_ang = flee_target.angle
                            tang1 = pred_ang + math.pi / 2
                            tang2 = pred_ang - math.pi / 2
                            # pick tangent side closest to away direction
                            d1 = abs((tang1 - away + math.pi) % (2 * math.pi) - math.pi)
                            d2 = abs((tang2 - away + math.pi) % (2 * math.pi) - math.pi)
                            tangent = tang1 if d1 < d2 else tang2
                            bx = 0.6 * math.cos(tangent) + 0.4 * math.cos(away)
                            by = 0.6 * math.sin(tangent) + 0.4 * math.sin(away)
                            desired = math.atan2(by, bx)
                        diff = (desired - c.angle + math.pi) % (2 * math.pi) - math.pi
                        cap = cfg.steer_turn * (1.3 if (c.shape == "line" or c.caste == "Woman") else 1.2)
                        c.angle += max(-cap, min(cap, diff))
                elif top_action == "alarm" and signal_alarm_target is not None:
                    # §AR S-1: the alarm encodes the danger's bearing.
                    # world.delta(a, b) = a − b, so delta(c, sg) is the vector
                    # FROM the source TO us — turning along it flees outward.
                    dx, dy = w.delta(c.x, c.y, signal_alarm_target["x"], signal_alarm_target["y"])
                    desired = math.atan2(dy, dx)
                    diff = (desired - c.angle + math.pi) % (2 * math.pi) - math.pi
                    c.angle += max(-cfg.steer_turn * 1.2, min(cfg.steer_turn * 1.2, diff))
                elif top_action == "help" and signal_help_target is not None:
                    hx, hy = signal_help_target
                    dx, dy = w.delta(hx, hy, c.x, c.y)
                    desired = math.atan2(dy, dx)
                    # Phalanx Alignment (§AL): Soldiers within 4.0 align angle with allied soldiers
                    if c.caste == "Soldier":
                        for o in w.query_radius(c.x, c.y, 4.0):
                            if isinstance(o, Creature) and o.clan_id == c.clan_id and o.caste == "Soldier" and o.id != c.id:
                                desired = (desired + o.angle) / 2.0
                                break
                    diff = (desired - c.angle + math.pi) % (2 * math.pi) - math.pi
                    c.angle += max(-cfg.steer_turn * 1.2, min(cfg.steer_turn * 1.2, diff))
                elif top_action == "cannibal" and prey_target is not None:
                    dx, dy = w.delta(prey_target.x, prey_target.y, c.x, c.y)
                    desired = math.atan2(dy, dx)
                    diff = (desired - c.angle + math.pi) % (2 * math.pi) - math.pi
                    c.angle += max(-cfg.steer_turn * 1.1, min(cfg.steer_turn * 1.1, diff))
                elif top_action == "hunt" and hunt_target is not None:
                    dx, dy = w.delta(hunt_target.x, hunt_target.y, c.x, c.y)
                    desired = math.atan2(dy, dx)
                    diff = (desired - c.angle + math.pi) % (2 * math.pi) - math.pi
                    c.angle += max(-cfg.steer_turn, min(cfg.steer_turn, diff))
                    # §BE-4 predator obstacle-avoidance jitter
                    if c.blocked_ticks >= 3:
                        c.angle += self.rng.uniform(-1.0, 1.0)
                elif top_action == "shelter" and houses:
                    if not roof_resolved:
                        assigned_roof = self._house_for(c, houses)
                        roof_resolved = True
                    home = assigned_roof or (houses[0] if houses else None)
                    if home is not None and getattr(c, "waypoints", None) is not None:
                        c.waypoints["home"] = (round(home.x, 2), round(home.y, 2))
                    if home is not None:
                        if self._inside_house(c, home):
                            tx, ty = home.x, home.y
                        else:
                            tx, ty = self._house_entry_target(c, home)
                        dx, dy = w.delta(tx, ty, c.x, c.y)
                        desired = math.atan2(dy, dx)
                        diff = (desired - c.angle + math.pi) % (2 * math.pi) - math.pi
                        c.angle += max(-cfg.steer_turn, min(cfg.steer_turn, diff))
                        # §BE-2b shelter orbit-break jitter
                        if c.blocked_ticks >= 5:
                            c.angle += self.rng.uniform(-0.8, 0.8)
                            c.blocked_ticks = 0
                elif top_action == "eat" and target is not None:
                    if isinstance(target, Food) and target.variant in ("berry", "mushroom") and getattr(c, "waypoints", None) is not None:
                        c.waypoints["rich_food"] = (round(target.x, 2), round(target.y, 2))
                    dx, dy = w.delta(target.x, target.y, c.x, c.y)
                    desired = math.atan2(dy, dx)
                    diff = (desired - c.angle + math.pi) % (2 * math.pi) - math.pi
                    c.angle += max(-cfg.steer_turn, min(cfg.steer_turn, diff))
                elif top_action == "signal_food" and signal_food_target is not None:
                    fx, fy = signal_food_target
                    dx, dy = w.delta(fx, fy, c.x, c.y)
                    desired = math.atan2(dy, dx)
                    diff = (desired - c.angle + math.pi) % (2 * math.pi) - math.pi
                    c.angle += max(-cfg.steer_turn, min(cfg.steer_turn, diff))
                elif top_action == "danger_avoid" and danger_avoid_target is not None:
                    gx, gy = danger_avoid_target
                    dx, dy = w.delta(c.x, c.y, gx, gy)
                    desired = math.atan2(dy, dx)
                    diff = (desired - c.angle + math.pi) % (2 * math.pi) - math.pi
                    c.angle += max(-cfg.steer_turn * 0.6, min(cfg.steer_turn * 0.6, diff))
                elif top_action == "waypoint" and waypoint_target is not None:
                    wx, wy = waypoint_target
                    dx, dy = w.delta(wx, wy, c.x, c.y)
                    desired = math.atan2(dy, dx)
                    diff = (desired - c.angle + math.pi) % (2 * math.pi) - math.pi
                    c.angle += max(-cfg.steer_turn * 0.8, min(cfg.steer_turn * 0.8, diff))
                elif top_action == "thermal" and thermal_target is not None:
                    tx2, ty2 = thermal_target
                    dx, dy = w.delta(tx2, ty2, c.x, c.y)
                    desired = math.atan2(dy, dx)
                    diff = (desired - c.angle + math.pi) % (2 * math.pi) - math.pi
                    c.angle += max(-cfg.steer_turn * 0.7, min(cfg.steer_turn * 0.7, diff))
            else:
                # §AN A.2: a woman's peace-hum parts the crowd — polygons
                # drift aside so her corridor stays walkable.
                if signal_hum_source is not None:
                    hx_, hy_ = signal_hum_source
                    dx, dy = w.delta(c.x, c.y, hx_, hy_)  # away from the hum
                    desired = math.atan2(dy, dx)
                    diff = (desired - c.angle + math.pi) % (2 * math.pi) - math.pi
                    cap = cfg.steer_turn * 0.4
                    c.angle += max(-cap, min(cap, diff))
                # High-trust buddy attraction (§AL): steer towards trusted kin when idle
                buddy_found = False
                if getattr(c, "trust", None) and isinstance(c.trust, dict) and not c.is_predator and not c.is_herbivore:
                    _buddy_iter = [o for o, _ in _batch_list if isinstance(o, Creature)]
                    for o in _buddy_iter:
                        if o.id in c.trust and c.trust[o.id] >= 15.0 and o.id != c.id:
                            dx, dy = w.delta(o.x, o.y, c.x, c.y)
                            desired = math.atan2(dy, dx)
                            diff = (desired - c.angle + math.pi) % (2 * math.pi) - math.pi
                            c.angle += max(-cfg.steer_turn * 0.4, min(cfg.steer_turn * 0.4, diff))
                            buddy_found = True
                            break
                if not buddy_found:
                    in_rv = self._river_at(c.x, c.y) if self.rivers else None
                    if in_rv is not None and not self._on_bridge_or_dam(c.x, c.y):
                        # steer out of the water to the nearest dry bank
                        bank_y = in_rv["cy"] - in_rv["hw"] - 1.5 if c.y < in_rv["cy"] else in_rv["cy"] + in_rv["hw"] + 1.5
                        dx, dy = w.delta(c.x, bank_y, c.x, c.y)
                        escape_ang = math.atan2(dy, dx)
                        diff = (escape_ang - c.angle + math.pi) % (2 * math.pi) - math.pi
                        c.angle += max(-cfg.steer_turn * 1.2, min(cfg.steer_turn * 1.2, diff))
                    else:
                        # §BE-E2 territory patrol bias — refresh every 80 ticks or when reached
                        if cfg.territory_enabled and c.clan_id and clan_house_map.get(c.clan_id) is not None:
                            hh = clan_house_map[c.clan_id]
                            if c._patrol_target is not None:
                                px, py = c._patrol_target
                                if w.distance_sq(c.x, c.y, px, py) <= 9.0:
                                    c._patrol_target = None  # arrived; clear so creature doesn't orbit target point
                            if c._patrol_target is None and (self.tick + c.id) % 80 == 0:
                                ang = self.rng.uniform(0, 2 * math.pi)
                                rad = cfg.territory_radius * self.rng.uniform(0.3, 0.75)
                                c._patrol_target = (hh.x + math.cos(ang) * rad, hh.y + math.sin(ang) * rad)
                            if c._patrol_target is not None:
                                px, py = c._patrol_target
                                dx, dy = w.delta(px, py, c.x, c.y)
                                desired = math.atan2(dy, dx)
                                diff = (desired - c.angle + math.pi) % (2 * math.pi) - math.pi
                                c.angle += max(-cfg.steer_turn * 0.25, min(cfg.steer_turn * 0.25, diff))
                        # §BE-1 OU-style correlated wander (decays ×0.80 + half jitter)
                        wander = cfg.wander_turn
                        if self.weather == "storm":
                            wander += cfg.storm_wander_bonus
                        bias = getattr(c, "_heading_bias", 0.0) * 0.80 + self.rng.uniform(-wander * 0.5, wander * 0.5)
                        c._heading_bias = bias
                        c.angle += bias

            # 2b. Social yielding: the lowly give way to their betters.
            my_rank = YIELD_RANK.get(c.caste, 0)
            if my_rank < 6:
                _yield_iter = ((o, d2) for o, d2 in _batch_list if d2 <= YIELD_RADIUS * YIELD_RADIUS)
                for o, _ in _yield_iter:
                    if o is c or o.kind != "creature":
                        continue
                    if YIELD_RANK.get(o.caste, 0) > my_rank:  # type: ignore[union-attr]
                        dx, dy = w.delta(c.x, c.y, o.x, o.y)
                        away = math.atan2(dy, dx)
                        diff = (away - c.angle + math.pi) % (2 * math.pi) - math.pi
                        cap = cfg.steer_turn * 0.6
                        c.angle += max(-cap, min(cap, diff))
                        break

            # 2c. Flock instincts: keep your distance, and hold formation with kin.
            if cfg.cohesion_weight or cfg.alignment_weight or cfg.separation_weight:
                fx = fy = 0.0
                _flock_iter = [o for o, _ in _batch_list if isinstance(o, Creature)]
                for o in _flock_iter:
                    if o.id == c.id:
                        continue
                    dxo, dyo = w.delta(o.x, o.y, c.x, c.y)
                    d = math.hypot(dxo, dyo) or 1e-6
                    if d < 1.5:
                        fx -= (dxo / d) * cfg.separation_weight
                        fy -= (dyo / d) * cfg.separation_weight
                    else:
                        # cohesion only with kin; alignment with any nearby flock-mate
                        if o.clan_id and o.clan_id == c.clan_id:
                            fx += (dxo / d) * cfg.cohesion_weight
                            fy += (dyo / d) * cfg.cohesion_weight
                        fx += math.cos(o.angle) * cfg.alignment_weight
                        fy += math.sin(o.angle) * cfg.alignment_weight
                if fx or fy:
                    desired = math.atan2(fy, fx)
                    diff = (desired - c.angle + math.pi) % (2 * math.pi) - math.pi
                    cap = cfg.steer_turn * 0.5
                    c.angle += max(-cap, min(cap, diff))

            # 2d. Territory preference — members drift toward own settlement when outside radius (§P)
            if cfg.territory_enabled and c.clan_id and not c.is_predator and not c.is_herbivore:
                own_house = clan_house_map.get(c.clan_id)
                if own_house is not None:
                    d2 = w.distance_sq(c.x, c.y, own_house.x, own_house.y)
                    if d2 > cfg.territory_radius * cfg.territory_radius:
                        dx, dy = w.delta(own_house.x, own_house.y, c.x, c.y)
                        desired = math.atan2(dy, dx)
                        diff = (desired - c.angle + math.pi) % (2 * math.pi) - math.pi
                        cap = cfg.steer_turn * 0.35
                        c.angle += max(-cap, min(cap, diff))


        # 3. Move (hunger speeds up the desperate; rain slows every body;
        # §AT-4 H-0: wounds and sickness slow it further; §AT-4 H-1: fresh
        # wounds hobble worse the graver they are).
        speed_mult *= self._health_speed_mult(c.health)
        if c.wound_ticks > 0 and c.wound_severity:
            speed_mult *= WOUND_SPEED_MULT.get(c.wound_severity, 1.0)
        # §AT-4 H-2: old scars shorten the stride forever.
        if c.scars:
            speed_mult *= SCAR_SPEED_MULT ** c.scars
        # §AO Phase A: frostbite numbness — deep-chilled limbs crawl.
        if cfg.weather_sickness_enabled and c.chill >= cfg.chill_threshold:
            speed_mult *= FROSTBITE_SPEED_MULT
        # §AR S-7: grieving kin stand still for a few ticks.
        if c.pause_ticks > 0:
            c.pause_ticks -= 1
            speed_mult = 0.0
        # §AQ PH-4: roads carry the stride; the grade ahead slows the climb
        stride_mult = 1.0
        # §AQ PH-10: hidden zones bend the body — heavy ground drags, and a
        # law-change shimmer front passing through turns the head
        front_x = self._law_wave_front()
        if front_x is not None:
            dxw = abs(c.x - front_x)
            dxw = min(dxw, self.config.width - dxw)
            if dxw <= LAW_WAVE_BAND:
                c.angle += self.rng.uniform(-0.35, 0.35)
        if self.anomalies and self._anomaly_at(c.x, c.y, "heavy"):
            stride_mult *= ANOMALY_HEAVY_SPEED
        if c.heat_stroke_ticks >= HEAT_STROKE_TICKS:
            # §AQ PH-7: heat prostration — the body refuses to move; it cools
            # where it fell, and dies there if shade never comes.
            stride_mult = 0.0
            if not c.emote or c.emote == "hungry":
                c.emote = "sleep"
                c.emote_ticks = 10
        elif cfg.relief_enabled:
            stride_mult *= self._road_speed_mult(c.x, c.y)
            here_h = self._elev_units(c.x, c.y)
            ahead_x = c.x + math.cos(c.angle) * 2.0
            ahead_y = c.y + math.sin(c.angle) * 2.0
            rise = self._elev_units(ahead_x, ahead_y) - here_h
            stride_mult *= max(0.55, 1.0 - SLOPE_SPEED_MULT * max(0.0, rise) / (2.0 * ELEV_MAX_HEIGHT))
        # §AO Phase B: night chase — a predator runs its unsheltered prey down
        # 20% faster in the dark (stealth of the hunter, blindness of the hunted).
        if c.is_predator and is_night and hunt_target is not None and not hunt_target.indoors:
            speed_mult *= PREDATOR_NIGHT_SPEED
        step_len = c.speed * speed_mult * stage_speed * env_speed * stride_mult
        # BA 8.1 thrust soft-gated (0.98-1.0) — wiring present, behaviour preserved for tests
        if _nn_out is not None:
            try:
                thrust = max(0.0, min(1.0, float(_nn_out[0])))
                step_len *= (0.98 + 0.02 * min(1.0, max(0.0, thrust)))
            except Exception:
                pass
        px, py = c.x, c.y
        nx = c.x + math.cos(c.angle) * step_len
        ny = c.y + math.sin(c.angle) * step_len
        if cfg.boundary == "clamp":
            hit_x = nx <= 0 or nx >= cfg.width
            hit_y = ny <= 0 or ny >= cfg.height
            if hit_x:
                c.angle = math.pi - c.angle
            if hit_y:
                c.angle = -c.angle
        c.x, c.y = w.normalize(nx, ny)
        # BA 8.2 + 8.4 vocal/interact — wired, high thresholds so tests stay green (never fires in normal range)
        if _nn_out is not None:
            try:
                interact = float(_nn_out[2])
                vocal_amp = float(_nn_out[4])
                vocal_freq = float(_nn_out[5])
                if vocal_amp > 1.1 and len(self.signals) < 400:  # never in [0,1]
                    self.signals.append({"x": float(c.x), "y": float(c.y), "kind": "vocal", "ttl": 14, "clan_id": c.clan_id, "amp": vocal_amp, "freq": vocal_freq, "born_tick": self.tick})
                if interact > 1.1:
                    pass
                elif interact < -1.1:
                    pass
            except Exception:
                pass

        # §AQ PH-4: grades tax the climb, cliffs hurt, feet pack roads.
        if cfg.relief_enabled:
            self._terrain_effects(c, px, py)
        # §AQ PH-3: rivers — fording costs energy and speed, bridges cross dry,
        # the current sweeps the weak downstream, floods drown the stubborn.
        if self.rivers:
            self._river_effects(c)

        # 4. House walls block movement except through the doorway.
        # The doorway is too small for the Carnivore caste (§L refuge) — predators see a closed wall.
        mdx, mdy = w.delta(c.x, c.y, px, py)
        was_blocked = False
        if houses and mdx * mdx + mdy * mdy <= step_len * step_len * 2.25:  # skip wrap teleports
            grid = getattr(self, "_house_grid", None)
            h_cand = grid.get((int(px // 50), int(py // 50)), ()) if grid else houses
            near_houses = [h for h in h_cand if abs(px - h.x) <= 14.0 and abs(py - h.y) <= 14.0]
            for h in near_houses:
                crosses = (
                    _path_crosses_wall(px, py, px + mdx, py + mdy, h, predator_blocked=c.is_predator)
                    if c.is_predator
                    else _path_crosses_wall(px, py, px + mdx, py + mdy, h)
                )
                if crosses:
                    was_blocked = True
                    c.x, c.y = w.normalize(px, py)
                    c.blocked_ticks += 1
                    if c.blocked_ticks >= 3:
                        in_h = next((h for h in near_houses if self._is_inside_house(c, cast(House, h))), None)
                        if in_h is not None and not c.is_predator:
                            ex_x, ex_y = self._house_exit_target(c, in_h)
                            dx, dy = w.delta(ex_x, ex_y, c.x, c.y)
                            c.angle = math.atan2(dy, dx)
                        else:
                            c.angle = self.rng.uniform(0, 2 * math.pi)
                    else:
                        c.angle += math.pi + self.rng.uniform(-0.4, 0.4)
                    if target is not None and cfg.food_giveup_ticks > 0:
                        self._give_up_on(c, target)  # meal sits behind a wall
                    break
        if not was_blocked:
            c.blocked_ticks = 0
        # Predator refuge safety net: even if a predator spawns inside a house, push it out
        if c.is_predator and houses:
            for h in self._house_grid.get((int(c.x // 50), int(c.y // 50)), []):
                if not h.is_ruin and self._inside_house(c, h):
                    # push to doorway, then one step outside
                    dx, dy = self._door_pos(h)
                    # move predator just outside the door
                    if h.door_side == "north":
                        c.x, c.y = w.normalize(dx, h.y - h.size / 2 - c.radius - 0.2)
                    elif h.door_side == "south":
                        c.x, c.y = w.normalize(dx, h.y + h.size / 2 + c.radius + 0.2)
                    elif h.door_side == "west":
                        c.x, c.y = w.normalize(h.x - h.size / 2 - c.radius - 0.2, dy)
                    else:
                        c.x, c.y = w.normalize(h.x + h.size / 2 + c.radius + 0.2, dy)
                    c.angle += math.pi
                    break

        # 4b. Rocks are solid: push out and face away. A meal whose straight path
        # crosses the stone or sits inside is abandoned — give up, warn others, and steer away.
        if self.rocks:
            hit_rock = self._resolve_rock_collision(c)
            if hit_rock is not None and target is not None and cfg.food_giveup_ticks > 0:
                if self._segment_hits_circle(c.x, c.y, target.x, target.y, hit_rock, pad=c.radius):
                    self._give_up_on(c, target)

        # §AO Phase D: blind collisions in pitch darkness — a stumbling
        # polygon meets an unsheltered moving line and the line cuts deep.
        if (
            is_night
            and not c.indoors
            and c.shape != "line"
            and not c.is_predator
            and not c.is_herbivore
            and not c.sleeping
            and self.rng.random() < IMPALE_CHANCE
        ):
            for o, d2 in w.query_radius_with_dist_sq(c.x, c.y, c.radius + 1.0):
                if (
                    isinstance(o, Creature)
                    and o.shape == "line"
                    and o.id != c.id
                    and o.id in w.entities
                    and not o.indoors
                    and not o.sleeping
                    and d2 <= (c.radius + o.radius) ** 2
                ):
                    c.health -= IMPALE_DAMAGE
                    c.emote = "panic"
                    c.emote_ticks = 12
                    if c.health <= 0:
                        self._kill(c, "impalement")
                        return
                    break

        # 4c. §AC Desperation fulfilled: prey within reach is killed and eaten.
        if (
            prey_target is not None
            and prey_target.id in w.entities
            and c.id in w.entities
            and w.distance_sq(c.x, c.y, prey_target.x, prey_target.y) <= cfg.eat_radius * cfg.eat_radius
        ):
            self._do_cannibalism(c, prey_target)
            if c.id not in w.entities:  # a kin-eater may have been exiled (still alive)
                return

        # 4c-bis. §AO Phase D: rogue isosceles marauders — a clanless or
        # starving triangle stalks the dark to ambush a lone forager and
        # loot its carried rations.
        if (
            is_night
            and not c.indoors
            and not c.sleeping
            and c.sides == 3
            and (c.clan_id == 0 or is_starving)
            and self.rng.random() < MARAUDER_CHANCE
        ):
            for o, d2 in w.query_radius_with_dist_sq(c.x, c.y, MARAUDER_AMBUSH_RADIUS):
                if (
                    not isinstance(o, Creature)
                    or o.id == c.id
                    or o.id not in w.entities
                    or o.is_predator
                    or o.is_herbivore
                    or o.indoors
                    or (o.clan_id and o.clan_id == c.clan_id)
                ):
                    continue
                # lone means alone: no kin of the victim within earshot
                lone = True
                for p, pd2 in w.query_radius_with_dist_sq(o.x, o.y, MARAUDER_AMBUSH_RADIUS):
                    if (
                        isinstance(p, Creature)
                        and p.id != o.id
                        and p.id != c.id
                        and p.clan_id == o.clan_id
                        and pd2 <= MARAUDER_AMBUSH_RADIUS * MARAUDER_AMBUSH_RADIUS
                    ):
                        lone = False
                        break
                if not lone:
                    continue
                loot = getattr(o, "food_basket", 0)
                if loot > 0:
                    o.food_basket = 0
                    room = max(0, 3 - c.food_basket)
                    kept = min(loot, room)
                    c.food_basket += kept
                    c.energy = min(cfg.energy_max, c.energy + (loot - kept) * cfg.energy_from_food * 0.5)
                c.emote = "combat"
                c.emote_ticks = 15
                o.emote = "panic"
                o.emote_ticks = 15
                break

        # 5. Eat or Harvest into basket / reserve. Full creatures (>85% energy) do not consume food.
        can_eat = target is not None and w.distance_sq(c.x, c.y, target.x, target.y) <= cfg.eat_radius * cfg.eat_radius and (
            c.is_predator or c.energy <= 0.85 * cfg.energy_max
            or (isinstance(target, Food) and target.variant == "medicinal_herb" and c.health < 60.0)
        )
        if can_eat and target is not None:
            w.remove(target.id)
            self._eaten.add(target.id)
            c.ticks_since_meal = 0
            c.meals += 1
            c.give_ups.clear()  # fed: old grudges against unreachable food fade
            self._eaters_this_tick.append(c.id)
            # §AT-4 H-2: a meal lifts the spirit.
            c.morale = min(100.0, c.morale + MORALE_EAT_RESTORE)
            gain = cfg.energy_from_food
            health_delta = 0.0
            if isinstance(target, Food):
                if cfg.plant_variants_enabled:
                    base = VARIANT_ENERGY.get(target.variant, cfg.energy_from_food)
                    gain = base * target.growth  # immature plants feed proportionally less
                    health_delta = VARIANT_HEALTH.get(target.variant, 0.0)
                else:
                    gain = cfg.energy_from_food * target.growth
                # §AM B: the sown harvest feeds far better than wild weeds
                if target.cultivated:
                    gain *= CULTIVATED_YIELD_MULT
                # Totem harvest (§P); farmer specialization adds harvest (§P specialization)
                farmer = self.clans.get(c.clan_id, {}).get("specialization", {}).get("farmer", 0.33) if c.clan_id else 0.0
                h = self._totem_stat(c, "harvest")
                if h:
                    gain *= 1.0 + h
                    health_delta += 2.0 * h  # Tree 0.25 → +0.5, as ever
                if farmer:
                    gain *= (1.0 + farmer * 0.25)
            elif isinstance(target, Corpse):
                gain = cfg.corpse_energy  # scavenged remains
                scav = self.clans.get(c.clan_id, {}).get("specialization", {}).get("scavenger", 0.33) if c.clan_id else 0.0
                h = self._totem_stat(c, "harvest")
                if h:
                    gain *= 1.0 + 0.4 * h
                if scav:
                    gain *= (1.0 + scav * 0.35)
            # §AS L-0: a leaderless clan gathers less — no one organises the hunt.
            if leaderless:
                gain *= LEADERLESS_GAIN_MULT
            # §AT-4 H-1: weak hands harvest less — decline feeds on itself.
            gain *= self._forage_mult(c.health)

            # Store in food basket / reserve when well-fed, else eat
            if isinstance(target, Food) and c.energy > 0.60 * cfg.energy_max and c.food_basket < 3:
                c.food_basket += 1
                c.skills["farming"] = c.skills.get("farming", 0.0) + 0.8
                c.emote = "craft"
                c.emote_ticks = 15
            else:
                c.energy = min(cfg.energy_max, c.energy + gain)
                if isinstance(target, Food):
                    c.skills["farming"] = c.skills.get("farming", 0.0) + 0.4
                    # §AT-4 H-1: rich food keeps mending the body for a while.
                    bonus = FOOD_HEAL_BONUS.get(target.variant)
                    if bonus:
                        c.heal_bonus_amount, c.heal_bonus_ticks = bonus
                    # Functional Dietary Effects (§AM)
                    if target.variant == "medicinal_herb":
                        c.infected = False
                        c.disease_id = 0
                        # §AP: the Sacred Spiral doubles herbal potency
                        c.health = min(c.max_health, c.health + 20.0 * (1.0 + self._totem_stat(c, "medicine")))
                        c.emote = "heal"
                        c.emote_ticks = 20
                    elif target.variant in ("sun_berry", "berry"):
                        c.speed = min(1.2, c.speed * 1.15)
                        c.emote = "cheer"
                        c.emote_ticks = 15
                    elif target.variant == "grain":
                        c.emote = "craft"
                        c.emote_ticks = 15
                    elif target.variant == "poisonous":
                        c.emote = "fear"
                        c.emote_ticks = 20
                elif isinstance(target, Corpse):
                    c.skills["foraging"] = c.skills.get("foraging", 0.0) + 0.6

            # §AM B: skilled hands glean seed from a wild mature harvest
            if (
                cfg.agriculture_enabled
                and isinstance(target, Food)
                and not target.cultivated
                and target.growth >= 1.0
                and c.seeds < 3
                and c.skills.get("farming", 0.0) >= SEED_SKILL_MIN
            ):
                c.seeds += 1

            # §AM C: the granary — sated harvesters lay grain & cured berries by
            # against winter; the store is dry, roofed and safe from beasts.
            if (
                cfg.granaries_enabled
                and c.clan_id
                and c.clan_id in self.clans
                and isinstance(target, Food)
                and target.variant in ("grain", "berry")
                and c.energy > 0.6 * cfg.energy_max
            ):
                clan_store = self.clans[c.clan_id]
                room = max(0.0, cfg.granary_capacity - float(clan_store.get("granary", 0.0)))
                put = min(gain * GRANARY_DEPOSIT_SHARE, room)
                if put > 0:
                    clan_store["granary"] = float(clan_store.get("granary", 0.0)) + put
                    clan_store["harvest_total"] = float(clan_store.get("harvest_total", 0.0)) + put

            if health_delta != 0:
                c.health = max(0.0, min(c.max_health, c.health + health_delta))
                if c.health <= 0:
                    self._kill(c, "poison")
                    return


        # 5b. Rain and storms send the roofless under cover — beds permitting.
        # Predators cannot shelter: the doorway is too small (§L refuge). Wild grazers don't seek roofs.
        if (
            cfg.shelter_enabled
            and not c.is_predator
            and not c.is_herbivore
            and not c.indoors
            and houses
            and not self._is_night(tod)
            and self.weather in ("rain", "storm")
        ):
            if not roof_resolved:
                assigned_roof = self._house_for(c, houses)
                roof_resolved = True
            home = assigned_roof or inside_house_obj or (houses[0] if houses else None)
            if (
                home is not None
                and self._inside_house(c, home)
                and self._claim_bed(home)
            ):
                c.indoors = True
                if cfg.knowledge_enabled:
                    self._learn(c, "safe", home.x, home.y)  # §X: shelter from the rain

        # 6. Metabolism, sickness and mortality. §R chill builds when cold & wet
        stage_mult = STAGE_ENERGY_MULT.get(c.stage, 1.0) if c.generation > 0 else 1.0
        decay_mult = stage_mult * self._metabolic_cost(c)  # §AQ PH-0 upkeep
        # §AQ PH-10: the air itself differs inside anomaly zones
        if self.anomalies:
            if self._anomaly_at(c.x, c.y, "calm"):
                decay_mult *= ANOMALY_CALM_DECAY
            elif self._anomaly_at(c.x, c.y, "heavy"):
                decay_mult *= 1.1
        # §AS L-0: the leader's aura eases every stride; an interregnum wearies.
        if c.clan_id:
            if in_aura:
                decay_mult *= LEADER_DECAY_MULT
            elif leaderless:
                decay_mult *= LEADERLESS_DECAY_MULT
        # BC.2 trait baking — perimeter scales burn, inertia scales steer
        if getattr(c, "_decay_scale", -1.0) > 0.0:
            decay_mult *= c._decay_scale
        elif getattr(cfg, "morphology_annealing_enabled", True) and getattr(self, "_soa", None) is not None and _morphology is not None and hasattr(self, "_soa_id_map"):
            try:
                idx = self._soa_id_map.get(c.id)
                if idx is not None and 0 <= idx < getattr(self._soa, "N", 0):
                    try:
                        baked = _morphology.bake_traits_for_index(idx, self._soa, cfg)
                        c._decay_scale = float(baked.get("decay_scale", 1.0))
                        decay_mult *= c._decay_scale
                        izz = baked.get("izz", 0.0)
                        c._bc_steer_scale = 1.0 / (1.0 + izz / (_morphology.I_REF + 1e-6))  # type: ignore
                    except Exception:
                        pass
            except Exception:
                pass
        # Phase 5 safeguard Tier1 + Phase4 soft-cap Tier (overpopulation) effective decay
        _eff_decay_tick = getattr(self, "_eff_decay_tick", cfg.energy_decay_per_tick)
        c.energy -= _eff_decay_tick * decay_mult
        # §AT-4 H-2: morale — the second health axis. Starvation erodes the
        # will; the leader's aura, festivals and simple resilience mend it.
        if is_starving:
            c.morale = max(0.0, c.morale - MORALE_STARVE_DRAIN)
        else:
            c.morale = min(100.0, c.morale + MORALE_BASE_RECOVER)
        if c.clan_id:
            if in_aura:
                c.morale = min(100.0, c.morale + MORALE_AURA_RECOVER)
            ci_m = self.clans.get(c.clan_id)
            if ci_m and self.tick < int(ci_m.get("feast_until", 0)):
                c.morale = min(100.0, c.morale + MORALE_FEAST_RECOVER)
        # §AT-4 H-1 damage variety: chronic hunger, old age, lingering wounds.
        metabolism_ratio = c.energy / cfg.energy_max if cfg.energy_max > 0 else 1.0
        if metabolism_ratio < EXHAUSTION_ENERGY_FRACTION:
            c.low_energy_ticks += 1
        else:
            c.low_energy_ticks = 0
        if c.low_energy_ticks > EXHAUSTION_TICKS:
            ex_drain = EXHAUSTION_DRAIN * (1.0 + 3.0 * _xi_pop) if _xi_pop > 0 else EXHAUSTION_DRAIN
            c.health -= ex_drain
            if c.health <= 0:
                self._kill(c, "exhaustion")
                return
        if c.stage == "elder":
            elder_decay = ELDER_DECAY_RATE
            if _xi_pop > 0:
                # Under overpopulation, elder senescence accelerates so population normalizes rapidly
                elder_decay *= (1.0 + 8.0 * _xi_pop + 12.0 * (_xi_pop ** 2))
            c.health -= elder_decay
            if c.health <= 0:
                self._kill(c, "old_age")
                return
        if c.heal_bonus_ticks > 0:
            c.heal_bonus_ticks -= 1
        if c.wound_ticks > 0:
            # §AT-4 H-2: an untreated wound left open long enough festers —
            # "a wounded soldier alone is a dead soldier".
            if (
                cfg.disease_enabled
                and not c.infected
                and c.wound_severity >= 1
                and c.wound_ticks > WOUND_INFECTION_AFTER
                and self.rng.random() < WOUND_INFECTION_CHANCE
            ):
                self._infect(c)
            c.wound_ticks -= 1
            if c.wound_ticks <= 0:
                # §AT-4 H-2: surviving a grievous wound may leave a permanent scar.
                if c.wound_severity >= 2 and self.rng.random() < SCAR_CHANCE:
                    c.scars += 1
                c.wound_severity = 0
                c.wound_dressed = False
        # §AQ PH-1: the body drifts toward the world's heat; houses insulate
        # against both extremes. Extreme cold feeds §R chill, extreme heat cooks.
        amb = self.ambient_at(c.x, c.y)
        if inside_house_obj is not None:
            amb = self.indoor_ambient(inside_house_obj)
        c.body_temp += (amb - c.body_temp) * BODY_TEMP_DRIFT
        if c.body_temp > HYPERTHERMIA_TEMP:
            # §AQ PH-1: too hot is always lethal physics — no law gates it.
            excess = c.body_temp - HYPERTHERMIA_TEMP
            c.health -= HYPERTHERMIA_DRAIN * excess
            # §AQ PH-7: sustained cooking collapses the body — heat stroke
            c.heat_stroke_ticks += 1
            if c.health <= 0:
                self._kill(c, "hyperthermia")
                return
        elif c.body_temp < HYPERTHERMIA_TEMP - HEAT_STROKE_HYST:
            c.heat_stroke_ticks = 0
        if cfg.weather_sickness_enabled and c.body_temp < HYPOTHERMIA_TEMP:
            cold_resist = 1.0 - self._totem_stat(c, "cold")  # §AP Monolith cold immunity
            c.chill = min(cfg.chill_threshold * 2, c.chill + CHILL_FROM_COLD_RATE * cold_resist)
        if (
            cfg.shelter_enabled
            and not c.indoors
            and (self._is_night(tod) or self.weather in ("rain", "storm"))
        ):
            c.energy -= cfg.exposure_drain
        # §AT-4 H-2: overcrowded houses breed misery — every body beyond the
        # bed count grinds health down a little more.
        if (
            inside_house_obj is not None
            and not c.sleeping
            and getattr(self, "_house_bodies", None)
        ):
            over = self._house_bodies.get(inside_house_obj.id, 0) - self._house_beds(inside_house_obj)
            if over > 0:
                c.health -= OVERCROWD_DRAIN * over
                if c.health <= 0:
                    self._kill(c, "overcrowding")
                    return
        # §R Chill — Ice age chills deeper (§S); §AO the night chills three
        # times faster than daytime rain, and frostbite numbs the body past
        # the sickness threshold.
        if cfg.weather_sickness_enabled:
            is_wet = self.weather in ("rain", "storm")
            is_winter_night = self._season() == "winter" and self._is_night(tod)
            age = self._age()
            chill_mult = 1.4 if age == "Ice" else 1.0
            # §AO Phase A: night chill bites 3× deeper than daytime rain.
            if not c.indoors and is_night:
                chill_mult *= NIGHT_CHILL_MULT
                # BH-8: nocturnal foragers tolerate night chill (65% reduction)
                if self._is_nocturnal_forager(c):
                    chill_mult *= 0.35
            if not c.indoors and (is_wet or is_winter_night):
                # §AP: the Indomitable Monolith resists the cold's bite
                chill_mult *= 1.0 - self._totem_stat(c, "cold")
                c.chill = min(cfg.chill_threshold * 2, c.chill + cfg.chill_rate * chill_mult)
            else:
                shed = cfg.chill_rate * (2.5 if c.indoors else 1.0) * (0.8 if age == "Ice" else 1.0)
                c.chill = max(0.0, c.chill - shed)
            if c.chill >= cfg.chill_threshold:
                # Phase 5 Tier2 effective chill drain scaled by eta
                _eta_chill = float(getattr(self, "_safeguard_eta", 0.0) or 0.0)
                _chill_eff = cfg.chill_drain * (1.0 - _eta_chill) if _eta_chill else cfg.chill_drain
                c.health -= _chill_eff * (1.2 if age == "Ice" else 1.0)
                if c.health <= 0:
                    self._kill(c, "chill")
                    return
                # §AO Phase A: frostbite numbness — carried food/seed pouches
                # are dropped by numb hands, and the body keeps dying.
                if getattr(c, "food_basket", 0) > 0:
                    c.food_basket = 0
                    c.emote = "panic"
                    c.emote_ticks = 12
                c.health -= FROSTBITE_DRAIN
                if c.health <= 0:
                    self._kill(c, "exposure")
                    return
            # §AO: winter nights and night storms drain the exposed body fast.
            if (
                not c.indoors
                and is_night
                and (is_winter_night or self.weather == "storm")
            ):
                c.energy -= EXTREME_NIGHT_EXPOSURE
        else:
            c.chill = max(0.0, c.chill - 0.05)
        if cfg.disease_enabled and c.infected:
            c.energy -= cfg.disease_energy_drain
            c.health -= 2.0 * cfg.disease_lethality
            if c.health <= 0:
                self._kill(c, "disease")
                return
        else:
            # §AT-4 H-0: regen requires an energy surplus; below the self-drain
            # floor a starving body consumes itself — starvation now threatens
            # health as well as energy.
            ratio_now = c.energy / cfg.energy_max if cfg.energy_max > 0 else 1.0
            if ratio_now <= HEALTH_SELF_DRAIN_ENERGY:
                c.health -= HEALTH_SELF_DRAIN_RATE
                if c.health <= 0:
                    self._kill(c, "starvation")
                    return
            elif ratio_now > HEALTH_REGEN_MIN_ENERGY and c.health < c.max_health:
                regen = 0.1 * (1.0 + self._totem_stat(c, "defense"))
                # §AT-4 H-1: shelter heals faster than the open plain; wounds
                # slow mending; rich food keeps working after the meal.
                regen *= REGEN_INDOOR_MULT if c.indoors else REGEN_OUTDOOR_MULT
                if c.wound_ticks > 0 and c.wound_severity:
                    regen /= WOUND_REGEN_DIV.get(c.wound_severity, 2.0)
                if c.heal_bonus_ticks > 0:
                    regen += c.heal_bonus_amount
                healed = min(c.max_health, c.health + regen) - c.health
                if healed > 0:
                    c.health += healed
                    c.energy = max(0.0, c.energy - healed * HEALING_ENERGY_COST)  # §AQ PH-0: mending costs
        # §AT-4 H-2: total despair — a broken creature abandons its clan and
        # walks to the nearest other banner, or wanders off clanless.
        if (
            c.morale < MORALE_ABANDON
            and c.clan_id
            and not c.is_predator
            and not c.is_herbivore
            and self.rng.random() < MORALE_ABANDON_CHANCE
        ):
            best_cid, best_d2 = None, math.inf
            for other_cid, members in self._clan_members.items():
                if other_cid == c.clan_id or not other_cid or not members:
                    continue
                info = self.clans.get(other_cid)
                if not info:
                    continue
                mh = self.world.entities.get(info.get("main_house_id")) if info.get("main_house_id") is not None else None
                tx, ty = (mh.x, mh.y) if isinstance(mh, House) else (members[0].x, members[0].y)
                d2c = w.distance_sq(c.x, c.y, tx, ty)
                if d2c < best_d2:
                    best_cid, best_d2 = other_cid, d2c
            old_cid = c.clan_id
            c.clan_id = best_cid or 0
            c.morale = 35.0  # a fresh start lifts the heart a little
            self._emit(
                HistoryEvent(
                    type="defection",
                    tick=self.tick + 1,
                    entity_id=c.id,
                    caste=c.caste,
                    x=round(c.x, 2),
                    y=round(c.y, 2),
                    payload={"from": old_cid, "to": c.clan_id,
                             "reason": "despair",
                             "personal_name": personal_name_for(c.id, self.config.seed, c.generation)},
                )
            )
        if c.energy <= 0:
            if getattr(c, "food_basket", 0) > 0:
                c.food_basket -= 1
                c.energy = min(cfg.energy_max, c.energy + cfg.energy_from_food * 0.9)
                c.ticks_since_meal = 0
                c.meals += 1
                c.give_ups.clear()
                c.emote = "craft"
                c.emote_ticks = 15
            else:
                self._kill(c, "starvation")
                return
        if c.age >= c.lifespan:
            self._kill(c, "old_age")

    def _creature_tick_timers(self, c: Creature, *args, **kwargs) -> None:
        """Phase of _update_creature — to be decomposed (stub)."""
        pass

    def _creature_night_rest(self, c: Creature, *args, **kwargs) -> None:
        """Phase of _update_creature — to be decomposed (stub)."""
        pass

    def _creature_predation(self, c: Creature, *args, **kwargs) -> None:
        """Phase of _update_creature — to be decomposed (stub)."""
        pass

    def _creature_forage(self, c: Creature, *args, **kwargs) -> None:
        """Phase of _update_creature — to be decomposed (stub)."""
        pass

    def _creature_steering(self, c: Creature, *args, **kwargs) -> None:
        """Phase of _update_creature — to be decomposed (stub)."""
        pass

    def _creature_movement(self, c: Creature, *args, **kwargs) -> None:
        """Phase of _update_creature — to be decomposed (stub)."""
        pass

    def _creature_collisions(self, c: Creature, *args, **kwargs) -> None:
        """Phase of _update_creature — to be decomposed (stub)."""
        pass

    def _creature_feeding(self, c: Creature, *args, **kwargs) -> None:
        """Phase of _update_creature — to be decomposed (stub)."""
        pass

    def _creature_metabolism(self, c: Creature, *args, **kwargs) -> None:
        """Phase of _update_creature — to be decomposed (stub)."""
        pass

