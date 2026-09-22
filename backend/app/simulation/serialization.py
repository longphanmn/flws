"""Serialization mixin — snapshot/delta, payloads, identity cache, hash signatures (BI-3)."""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Any

from ..config import Config
from ..entities import Corpse, Creature, Entity, Food, House
from ..protocol import EntityState, HistoryEvent, StateMessage
from ..world import World, segments_intersect
from .constants import *

from .constants import _clan_sig, _season_food_mult, personal_name_for, glyph_for, variation_for


class SerializationMixin:
    def _is_safeguard_active(self, alive: int) -> bool:
        safeguard_enabled = bool(getattr(self.config, "safeguard_enabled", True))
        if not safeguard_enabled or alive <= 0:
            return False
        sg_tier = getattr(self, "_safeguard_tier", 0)
        sg_eta = getattr(self, "_safeguard_eta", 0.0)
        cc = int(getattr(self.config, "effective_carrying_capacity", getattr(self.config, "carrying_capacity", 350)))
        relief = float(getattr(self.config, "safeguard_relief_ratio", 0.30))
        ksafe = cc * relief
        if alive >= ksafe and sg_tier < 3:
            return False
        return bool(sg_tier > 0 or sg_eta > 0.0)

    def _is_softcap_active(self, alive: int) -> bool:
        soft_cap_enabled = bool(getattr(self.config, "soft_cap_enabled", True))
        if not soft_cap_enabled or alive <= 0:
            return False
        return bool(getattr(self, "_density_xi", 0.0) > 0.0)

    def _cached_identity(self, entity_id: int, generation: int) -> tuple[str, str, float, float, float]:
        """AA: name/glyph/jitter computed once per creature — never per frame."""
        key = (entity_id, generation)
        hit = self._identity_cache.get(key)
        if hit is None:
            seed = self.config.seed
            v = variation_for(entity_id, seed)
            hit = (
                personal_name_for(entity_id, seed, generation),
                glyph_for(entity_id, seed, generation),
                v["hue_shift"],
                v["scale_jitter"],
                v["angle_jitter"],
            )
            self._identity_cache[key] = hit
        return hit

    def _entity_sig(self, e: Entity) -> tuple:
        """Compact signature for delta change detection."""
        if isinstance(e, Creature):
            return (
                0,
                round(e.x, 1),
                round(e.y, 1),
                round(e.angle, 1),
                round(e.energy),
                e.status,
                round(e.health),
                e.stage,
                e.sleeping,
                e.infected,
                e.indoors,
                getattr(e, "emote", None),
                getattr(e, "equipped_item", None),
                getattr(e, "food_basket", 0),
                getattr(e, "title", None),
                getattr(e, "scars", 0),
                self._is_torpid(e),
            )
        if isinstance(e, Food):
            is_withering = False
            if (
                self.config.food_decay_enabled
                and e.growth >= 1.0
                and e.mature_ticks
                >= WILT_FRACTION
                * max(1, round(self.config.food_lifespan_ticks * FOOD_LIFESPAN_MULT.get(e.variant, 1.0)))
            ):
                is_withering = True
            return (1, round(e.x, 1), round(e.y, 1), round(e.growth, 1), is_withering)
        if isinstance(e, House):
            return (2, round(e.x, 1), round(e.y, 1), e.clan_id, bool(getattr(e, "is_ruin", False)),
                    e.hearth_lit, int(max(0.0, min(1.0, e.hp / 480.0)) * 20) if e.hp >= 0 else -1, e.rubble > 0)
        if isinstance(e, Corpse):
            return (3, round(e.x, 1), round(e.y, 1), e.ttl // 30)
        return (4, round(e.x, 1), round(e.y, 1))

    def _entity_delta_payload(self, e: Entity) -> dict:
        """Compact payload containing only dynamic attributes for existing entities."""
        if isinstance(e, Creature):
            d: dict[str, Any] = {
                "id": e.id,
                "kind": e.kind,
                "torpid": self._is_torpid(e) or None,
                "x": round(e.x, 2),
                "y": round(e.y, 2),
                "angle": round(e.angle, 3),
                "energy": round(e.energy, 1),
                "status": e.status,
                "health": round(e.health, 1),
                "age": e.age,
                "stage": e.stage,
                "sleeping": e.sleeping,
                "indoors": e.indoors,
                "chill": round(e.chill, 2),
            }
            if e.infected:
                d["infected"] = True
            emote = getattr(e, "emote", None)
            if emote is not None:
                d["emote"] = emote
            item = getattr(e, "equipped_item", None)
            if item is not None:
                d["equipped_item"] = item
            basket = getattr(e, "food_basket", 0)
            if basket:
                d["food_basket"] = basket
            title = getattr(e, "title", None)
            if title is not None:
                d["title"] = title
            scars = getattr(e, "scars", 0)
            if scars:
                d["scars"] = scars
            return d
        if isinstance(e, Food):
            is_withering = False
            if (
                self.config.food_decay_enabled
                and e.growth >= 1.0
                and e.mature_ticks
                >= WILT_FRACTION
                * max(1, round(self.config.food_lifespan_ticks * FOOD_LIFESPAN_MULT.get(e.variant, 1.0)))
            ):
                is_withering = True
            d = {
                "id": e.id,
                "kind": e.kind,
                "x": round(e.x, 2),
                "y": round(e.y, 2),
                "growth": round(e.growth, 2),
            }
            if is_withering:
                d["withering"] = True
            return d
        if isinstance(e, House):
            return {
                "id": e.id,
                "kind": e.kind,
                "clan_id": e.clan_id or None,
                "clan_color": e.clan_color,
                "is_main": bool(e.clan_id and self.clans.get(e.clan_id, {}).get("main_house_id") == e.id),
                "takeover_age": (self.tick - e.takeover_tick) if getattr(e, "takeover_tick", -1) >= 0 else None,
                "is_ruin": e.is_ruin or None,
                # §AQ PH-1: the hearth's state rides the delta so the flame
                # lights and gutters without a keyframe
                "hearth_lit": e.hearth_lit or None,
                # §AQ PH-6: integrity & rubble ride when they matter
                "hp_frac": (
                    round(max(0.0, e.hp) / MATERIAL_STATS.get(e.material, MATERIAL_STATS["wood"])["durability"], 2)
                    if e.hp >= 0 and e.hp < MATERIAL_STATS.get(e.material, MATERIAL_STATS["wood"])["durability"] * 0.98
                    else (None if not e.is_ruin else 0.0)
                ),
                "rubble": bool(e.rubble > 0) or None,
            }
        return {
            "id": e.id,
            "kind": e.kind,
            "x": round(e.x, 2),
            "y": round(e.y, 2),
            "angle": round(e.angle, 3),
        }

    def snapshot_payload(self) -> dict:
        """AA: the broadcast payload as plain dicts — no pydantic validation
        and no model_dump on the hot path. Shared nested structures are copied,
        so the payload stays valid while the world keeps ticking."""
        cfg = self.config
        entities: list[dict] = []
        population: dict[str, int] = {}
        alive = 0
        infected = 0
        clans = self.clans
        new_state: dict[int, tuple] = {}
        for e in self.world.entities.values():
            entities.append(self._entity_payload(e, clans))
            new_state[e.id] = self._entity_sig(e)
            if isinstance(e, Creature):
                label = e.caste
                alive += 1
                if e.infected:
                    infected += 1
            else:
                label = e.kind.capitalize()
            population[label] = population.get(label, 0) + 1

        self._last_broadcast_state = new_state
        self._last_broadcast_entities = set(new_state.keys())
        self._last_broadcast_clans = {
            str(cid): _clan_sig(info)
            for cid, info in self.clans.items()
        }


        return {
            "type": "state",
            "tick": self.tick,
            "seed": cfg.seed,
            "width": cfg.width,
            "height": cfg.height,
            "boundary": cfg.boundary,
            "population": population,
            "entities": entities,
            "creatures_alive": alive,
            "creatures_dead": self.deaths,
            "dead_by_cause": dict(self._death_counts),
            "infected_count": infected,
            "time_of_day": round(self._time_of_day(), 3),
            "day": self.day,
            "season": self._season(),
            "weather": self.weather,
            "terrain_fertile": getattr(self, "_cached_terrain_fertile", self.fertile),
            "terrain_rocks": getattr(self, "_cached_terrain_rocks", self.rocks),
            "relations": [
                {"a": a, "b": b, "score": s}
                for (a, b), s in sorted(self.relations.items())
            ],
            "clans": {
                str(k): {kk: (dict(vv) if isinstance(vv, dict) else vv) for kk, vv in v.items()}
                for k, v in self.clans.items()
            },
            "events": self._events_this_tick,  # AA: pre-dumped in _emit() — zero work here
            "signals": [dict(sg) for sg in self.signals],
            "fires": [dict(f) for f in self.fires],
            # §AO E: field campfires (tiny list, rides every frame)
            "campfires": [dict(cf) for cf in self.campfires],
            "boundary_stones": [dict(s) for s in self.boundary_stones],
            "markets": [dict(m, a=pair[0], b=pair[1]) for pair, m in self.markets.items()],
            "wind": {"angle": round(self.wind_angle, 3), "speed": round(self.wind_speed, 3)},
            # §AQ PH-3: channels, planks & masonry ride every frame (tiny lists)
            "rivers": [
                {"cy": r["cy"], "hw": round(r["hw"], 2),
                 "dir": r["dir"], "flood": r["flood_ticks"] > 0}
                for r in self.rivers
            ],
            "bridges": [{"x": b["x"], "cy": b["cy"]} for b in self.bridges],
            "dams": [
                {"x": d["x"], "cy": d["cy"], "hp_frac": round(max(0.0, d["hp"]) / DAM_HP, 2)}
                for d in self.dams
            ],
            # §AQ PH-4: the static height field rides only the keyframe
            "elevation": (
                {"cell": ELEV_CELL, "cols": self._elev_cols, "rows": self._elev_rows,
                 "h": self.elev_grid}
                if self.config.relief_enabled else {}
            ),
            # §AQ PH-9: visible bolts ride every frame (short-lived, few)
            "lightning": [dict(b) for b in self.lightning],
            # §AQ PH-10: only DISCOVERED anomalies appear on the wire
            "anomalies": [
                {"x": a["x"], "y": a["y"], "kind": a["kind"]}
                for a in self.anomalies if a["discovered"]
            ],
            # §AQ PH-10: the law-change shimmer front
            "law_wave": (
                {"born_tick": self.law_wave["born_tick"],
                 "ticks": LAW_WAVE_TICKS}
                if self.law_wave is not None else {}
            ),
            "wind": {"angle": round(self.wind_angle, 3), "speed": round(self.wind_speed, 3)},
            "age": self._age(),
            "age_tick": self._age_tick(),
            "age_day": self._age_day(),
            "age_total_days": self._age_total_days(),
            "safeguard_active": self._is_safeguard_active(alive),
            "softcap_active": self._is_softcap_active(alive),
        }

    def snapshot_delta_payload(self) -> dict:

        """Phase 1 AJ: Lightweight delta snapshot payload.

        Broadcasts only newly spawned, removed, or modified entities since last frame.
        Reduces payload size by 85–95%.
        """
        cfg = self.config
        upsert_entities: list[dict] = []
        population: dict[str, int] = {}
        alive = 0
        infected = 0
        clans = self.clans

        curr_entities = self.world.entities
        curr_ids = set(curr_entities.keys())
        prev_ids = self._last_broadcast_entities
        remove_ids = list(prev_ids - curr_ids)

        new_state: dict[int, tuple] = {}
        last_state = self._last_broadcast_state

        for eid, e in curr_entities.items():
            sig = self._entity_sig(e)
            new_state[eid] = sig
            if eid not in last_state:
                # Newly spawned entity: send full payload
                upsert_entities.append(self._entity_payload(e, clans))
            elif last_state[eid] != sig:
                # Existing entity modified: send compact delta payload
                upsert_entities.append(self._entity_delta_payload(e))

            if isinstance(e, Creature):
                label = e.caste
                alive += 1
                if e.infected:
                    infected += 1
            else:
                label = e.kind.capitalize()
            population[label] = population.get(label, 0) + 1

        self._last_broadcast_state = new_state
        self._last_broadcast_entities = curr_ids

        # Delta clans tracking: send only new or modified clans
        curr_clans = self.clans
        delta_clans: dict[str, dict] = {}
        last_clans = getattr(self, "_last_broadcast_clans", {})
        for cid, info in curr_clans.items():
            s_cid = str(cid)
            # Compare representation against last broadcast
            sig = _clan_sig(info)
            if s_cid not in last_clans or last_clans[s_cid] != sig:
                delta_clans[s_cid] = {kk: (dict(vv) if isinstance(vv, dict) else vv) for kk, vv in info.items()}
                last_clans[s_cid] = sig
        self._last_broadcast_clans = last_clans

        # §AQ PH-3: channels/planks/masonry ride deltas only when they change —
        # the client keeps the last known layout otherwise (websocket.ts ??).
        rivers_sig = (
            tuple((r["cy"], round(r["hw"], 1), r["dir"], r["flood_ticks"] > 0) for r in self.rivers),
            tuple((b["x"], b["cy"]) for b in self.bridges),
            tuple((d["x"], d["cy"], d["hp"] // 60) for d in self.dams),
        )
        geo: dict = {}
        if rivers_sig != getattr(self, "_last_rivers_sig", None):
            self._last_rivers_sig = rivers_sig
            geo = {
                "rivers": [
                    {"cy": r["cy"], "hw": round(r["hw"], 2),
                     "dir": r["dir"], "flood": r["flood_ticks"] > 0}
                    for r in self.rivers
                ],
                "bridges": [{"x": b["x"], "cy": b["cy"]} for b in self.bridges],
                "dams": [
                    {"x": d["x"], "cy": d["cy"], "hp_frac": round(max(0.0, d["hp"]) / DAM_HP, 2)}
                    for d in self.dams
                ],
            }
        # §AQ PH-9/10: bolts ride when present; anomalies/wave only on change
        if self.lightning:
            geo["lightning"] = [dict(b) for b in self.lightning]
        anomalies = [
            {"x": a["x"], "y": a["y"], "kind": a["kind"]}
            for a in self.anomalies if a["discovered"]
        ]
        a_sig = tuple((a["x"], a["y"]) for a in anomalies)
        if a_sig != getattr(self, "_last_anomalies_sig", None):
            self._last_anomalies_sig = a_sig
            geo["anomalies"] = anomalies
        if self.law_wave is not None:
            geo["law_wave"] = {"born_tick": self.law_wave["born_tick"], "ticks": LAW_WAVE_TICKS}

        return {
            "type": "delta_state",
            "tick": self.tick,
            "seed": cfg.seed,
            "upsert_entities": upsert_entities,
            "remove_ids": remove_ids,
            "population": population,
            "creatures_alive": alive,
            "creatures_dead": self.deaths,
            "dead_by_cause": dict(self._death_counts),
            "infected_count": infected,
            "time_of_day": round(self._time_of_day(), 3),
            "day": self.day,
            "season": self._season(),
            "weather": self.weather,
            "relations": [
                {"a": a, "b": b, "score": s}
                for (a, b), s in sorted(self.relations.items())
            ],
            "clans": delta_clans,
            "events": self._events_this_tick,
            "signals": [dict(sg) for sg in self.signals],
            "fires": [dict(f) for f in self.fires],
            # §AO E: field campfires (tiny list, rides every frame)
            "campfires": [dict(cf) for cf in self.campfires],
            "boundary_stones": [dict(s) for s in self.boundary_stones],
            "markets": [dict(m, a=pair[0], b=pair[1]) for pair, m in self.markets.items()],
            "wind": {"angle": round(self.wind_angle, 3), "speed": round(self.wind_speed, 3)},
            **geo,
            "age": self._age(),
            "age_tick": self._age_tick(),
            "age_day": self._age_day(),
            "age_total_days": self._age_total_days(),
            "safeguard_active": self._is_safeguard_active(alive),
            "softcap_active": self._is_softcap_active(alive),
        }

    def snapshot(self) -> StateMessage:
        """Typed snapshot for cold paths (REST /api/state, tests)."""
        return StateMessage.model_validate(self.snapshot_payload())

    def _entity_payload(self, e: Entity, clans: dict | None = None) -> dict:
        if clans is None:
            clans = self.clans
        if isinstance(e, Creature):
            name, glyph, hue_shift, scale_jitter, angle_jitter = self._cached_identity(
                e.id, e.generation
            )
            c_meta = clans.get(e.clan_id) if e.clan_id else None
            base: dict = {
                "id": e.id,
                "kind": e.kind,
                "x": round(e.x, 3),
                "y": round(e.y, 3),
                "angle": round(e.angle, 4),
                "shape": e.shape,
                "sides": e.sides,
                "caste": e.caste,
                "energy": round(e.energy, 2),
                "status": e.status,
                "radius": round(e.radius, 3),
                "age": e.age,
                "lifespan": round(e.lifespan, 1),
                "stage": e.stage,
                "irregularity": e.irregularity,
                "health": round(e.health, 1),
                "infected": e.infected,
                "scars": getattr(e, "scars", 0) or None,
                "sex": e.sex,
                "mother_id": e.mother_id or None,
                "father_id": e.father_id or None,
                "clan_id": e.clan_id or None,
                "clan_color": c_meta.get("color") if c_meta else None,
                "clan_name": c_meta.get("name") if c_meta else None,
                "clan_totem": c_meta.get("totem") if c_meta else None,
                "is_predator": e.is_predator or None,
                "is_herbivore": e.is_herbivore or None,
                "sleeping": e.sleeping,
                "indoors": e.indoors,
                "generation": e.generation,
                "born_tick": e.born_tick,
                "personal_name": name,
                "glyph": glyph,
                "hue_shift": hue_shift,
                "scale_jitter": scale_jitter,
                "angle_jitter": angle_jitter,
                "chill": round(e.chill, 2),
                "body_temp": round(getattr(e, "body_temp", 20.0), 1),
                # §AQ PH-7: cold-torpor collapses the body in place
                "torpid": self._is_torpid(e) or None,
                "trait": e.trait,
                "iso_angle": round(float(getattr(e, "iso_angle", 60.0) or 60.0), 2) if e.sides == 3 else None,
                "archetype": getattr(e, "_archetype", None) or getattr(self, "_archetype_cache", {}).get(e.id),  # BH-9
                "equipped_item": getattr(e, "equipped_item", None),
                "food_basket": getattr(e, "food_basket", 0) or None,
                "personality": getattr(e, "personality", "brave"),
                "skills": getattr(e, "skills", None),
                "title": getattr(e, "title", None),
                "emote": getattr(e, "emote", None),
            }
            # §BG: morph traits (iso_angle already above; add morph_k + morph_traits)
            try:
                soa = getattr(self, "_soa", None)
                if soa is not None and hasattr(soa, "ids"):
                    midx = -1
                    try:
                        import numpy as _np2  # type: ignore
                        if hasattr(soa.ids, "shape"):
                            arr2 = soa.ids[: soa.N]  # type: ignore
                            w2 = _np2.where(arr2 == e.id)[0]
                            if len(w2):
                                midx = int(w2[0])
                        else:
                            for _ii in range(getattr(soa, "N", 0)):
                                if int(soa.ids[_ii]) == e.id:  # type: ignore
                                    midx = _ii
                                    break
                    except Exception:
                        midx = -1
                    if midx >= 0 and hasattr(soa, "morph_k"):
                        try:
                            base["morph_k"] = int(soa.morph_k[midx])  # type: ignore
                        except Exception:
                            pass
                        try:
                            if hasattr(soa, "morph_traits"):
                                mt = soa.morph_traits[midx]  # type: ignore
                                # only expose when baked (area>0)
                                if hasattr(mt, "__len__") and len(mt) >= 6:
                                    # check area not zero
                                    _area = float(mt[0]) if hasattr(mt, "__getitem__") else 0.0
                                    if _area > 1e-6:
                                        base["morph_traits"] = [round(float(v), 4) for v in mt]  # type: ignore
                        except Exception:
                            pass
                    # expose polar radii/angles for detailed inspector (lightweight: 6 floats extra per tick is ok, but full 24*2 is heavy)
                    # For per-tick payload we send only morph_traits; detailed arrays are only for /api/creature detail below
            except Exception:
                pass
            # BA: NN state — always on, SoA has this creature
            if getattr(self, "_soa", None) is not None:
                try:
                    soa = self._soa  # type: ignore
                    idx = -1
                    if hasattr(soa, "ids"):
                        try:
                            import numpy as _np  # type: ignore

                            if hasattr(soa.ids, "shape"):
                                arr = soa.ids[: soa.N]  # type: ignore
                                w = _np.where(arr == e.id)[0]
                                if len(w):
                                    idx = int(w[0])
                            else:
                                for i in range(soa.N):
                                    if int(soa.ids[i]) == e.id:  # type: ignore
                                        idx = i
                                        break
                        except Exception:
                            for i in range(getattr(soa, "N", 0)):
                                try:
                                    if int(soa.ids[i]) == e.id:  # type: ignore
                                        idx = i
                                        break
                                except Exception:
                                    continue
                    if idx >= 0:
                        try:
                            if hasattr(soa.hidden_state, "shape"):
                                base["nn_hidden"] = round(float(soa.hidden_state[idx, 0]), 3)  # type: ignore
                                base["nn_outputs"] = [round(float(v), 3) for v in soa.outputs_buf[idx].tolist()]  # type: ignore
                                base["nn_genome_preview"] = [round(float(v), 3) for v in soa.genomes[idx, :8].tolist()]  # type: ignore
                            else:
                                base["nn_hidden"] = round(float(soa.hidden_state[idx][0]), 3)  # type: ignore
                                base["nn_outputs"] = [round(float(v), 3) for v in soa.outputs_buf[idx]]  # type: ignore
                                base["nn_genome_preview"] = [round(float(v), 3) for v in soa.genomes[idx][:8]]  # type: ignore
                        except Exception:
                            pass
                except Exception:
                    pass
            return base
        if isinstance(e, House):
            return {
                "id": e.id,
                "kind": e.kind,
                "x": round(e.x, 3),
                "y": round(e.y, 3),
                "angle": round(e.angle, 4),
                "size": round(e.size, 2),
                "door_width": round(e.door_width, 2),
                "door_offset": round(e.door_offset, 2),
                "door_side": e.door_side,
                "clan_id": e.clan_id or None,
                "clan_color": e.clan_color,
                "is_main": bool(e.clan_id and self.clans.get(e.clan_id, {}).get("main_house_id") == e.id),
                "is_ruin": e.is_ruin or None,

                "abandoned_ticks": e.abandoned_ticks or None,
                "material": e.material,  # §AQ PH-1 insulation tier
                # §AT-3: recent hostile takeover — renderer flashes the crest
                "takeover_age": (self.tick - e.takeover_tick) if getattr(e, "takeover_tick", -1) >= 0 else None,
                # §AN: painted chronicle of great days on the walls
                "murals": e.murals or None,
                # §AQ PH-1: fire burns on this hearth
                "hearth_lit": e.hearth_lit or None,
                # §AQ PH-6: structural integrity & rubble state
                "hp_frac": (
                    round(max(0.0, e.hp) / MATERIAL_STATS.get(e.material, MATERIAL_STATS["wood"])["durability"], 2)
                    if e.hp >= 0 else None
                ),
                "rubble": bool(e.rubble > 0) or None,
            }
        if isinstance(e, Food):
            is_withering = False
            if (
                self.config.food_decay_enabled
                and e.growth >= 1.0
                and e.mature_ticks
                >= WILT_FRACTION
                * max(1, round(self.config.food_lifespan_ticks * FOOD_LIFESPAN_MULT.get(e.variant, 1.0)))
            ):
                is_withering = True
            d = {
                "id": e.id,
                "kind": e.kind,
                "x": round(e.x, 3),
                "y": round(e.y, 3),
                "angle": round(e.angle, 4),
                "growth": round(e.growth, 3),
                "variant": e.variant,
            }
            if is_withering:
                d["withering"] = True
            # §AM: sown & furrowed crops read differently on the field
            if e.cultivated:
                d["cultivated"] = True
            if e.irrigated:
                d["irrigated"] = True
            return d
        return {
            "id": e.id,
            "kind": e.kind,
            "x": round(e.x, 3),
            "y": round(e.y, 3),
            "angle": round(e.angle, 4),
        }

    def _entity_state(self, e: Entity) -> EntityState:
        return EntityState.model_validate(self._entity_payload(e))

