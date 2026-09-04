"""Society mixin — clans, diplomacy, warfare, coalitions, leaders, larders, defection, trade, culture, cannibalism, specialization (BI-8)."""

from __future__ import annotations

import itertools
import math
import operator
import random
from typing import Any, Callable, cast

from ..entities import Creature, Entity, Food, House
from ..world import World, segments_intersect
from ..protocol import HistoryEvent
from .constants import *

class SocietyMixin:
    def _update_leader_orders(self) -> None:
        """§AS L-2 — the chief's voice at need: the retreat when bleeding,
        the rite at the great hall, the autumn harvest call, and the
        evacuation when fire or flood comes for the village."""
        cfg = self.config
        if not self.clans or len(self.signals) >= SIGNALS_MAX:
            return
        w = self.world

        def emit(cid: int, leader: Creature, kind: str, ttl: int, **extra) -> None:
            if len(self.signals) < SIGNALS_MAX:
                sg = {
                    "x": round(leader.x, 2), "y": round(leader.y, 2),
                    "kind": kind, "sender": leader.id,
                    "clan_id": cid or None, "born_tick": self.tick, "ttl": ttl,
                }
                sg.update(extra)
                self.signals.append(sg)

        season = self._season()
        for cid in sorted(self.clans.keys()):
            info = self.clans[cid]
            lid = info.get("leader_id")
            leader = self.world.entities.get(lid) if lid is not None else None
            if not isinstance(leader, Creature):
                continue
            mh_id = info.get("main_house_id")
            mh = self.world.entities.get(mh_id) if mh_id is not None else None
            at_home = isinstance(mh, House) and not mh.is_ruin and (
                w.distance(leader.x, leader.y, mh.x, mh.y) <= cfg.territory_radius
            )
            gov = info.get("governance", "republic")
            # 1. retreat — a bleeding general pulls the war party home
            if (
                leader.health <= RETREAT_HEALTH_FRAC * leader.max_health
                and (self.tick + cid) % 20 == 0
            ):
                emit(cid, leader, "retreat", 30)
            # 2. ritual — the rite that powers the totem (§AS L-2/L-5)
            if at_home and self.config.totems_enabled and (self.tick + cid) % RITUAL_INTERVAL == 0:
                power_ticks = RITUAL_TICKS
                if gov == "theocracy":
                    power_ticks *= THEOCRACY_RITUAL_POWER
                info["ritual_until"] = self.tick + power_ticks
                leader.emote = "cheer"
                leader.emote_ticks = 20
            # 3. harvest order — autumn stores decide winter
            if (
                season == HARVEST_ORDER_SEASON
                and at_home
                and cfg.granaries_enabled
                and (self.tick + cid) % 240 == 0
            ):
                emit(cid, leader, "harvest", 60, house_x=round(mh.x, 2), house_y=round(mh.y, 2))
            # 4. evacuation — fire or flood closing on the settlement
            if (self.tick + cid) % 15 == 0:
                hazard = None
                for ffire in self.fires:
                    if w.distance(ffire["x"], ffire["y"], mh.x if mh else leader.x, mh.y if mh else leader.y) < 25.0:
                        hazard = (ffire["x"], ffire["y"])
                        break
                if hazard is None:
                    for rv in self.rivers:
                        if rv.get("flood_ticks", 0) > 0 and mh is not None:
                            dy_ = self._river_dy(mh.y, rv["cy"])
                            if abs(dy_) <= rv["hw"] + 6.0:
                                hazard = (mh.x, rv["cy"])
                                break
                if hazard is not None:
                    hx_, hy_ = hazard
                    dxl, dyl = w.delta(hx_, hy_, leader.x, leader.y)
                    dl = math.hypot(dxl, dyl) or 1e-6
                    ex = leader.x + dxl / dl * 18.0
                    ey = leader.y + dyl / dl * 18.0
                    emit(cid, leader, "evacuate", 40, evac_x=round(ex % cfg.width, 2),
                         evac_y=round(ey % cfg.height, 2))

    def _new_clan(self, founder: Creature | None) -> int:
        """Register a clan: seeded name/totem/culture/specialization (no house yet)."""
        cid = self._next_clan_id
        self._next_clan_id += 1
        # Procedural name: deterministic adj+noun from seed+cid (no rng consumption to keep determinism)
        adj = CLAN_ADJECTIVES[(cid * 13 + self.config.seed) % len(CLAN_ADJECTIVES)]
        noun = CLAN_NOUNS[(cid * 29 + self.config.seed) % len(CLAN_NOUNS)]
        if (cid * 7 + self.config.seed) % 10 < 3:
            name = f"Clan of the {adj} {noun}"
        else:
            name = f"{adj} {noun}"
        totem = None
        if self.config.totems_enabled:
            # §AP: the clan's avatar — a sacred 2D projection of the Sphere,
            # assigned procedurally at founding (deterministic, no rng).
            totem = AVATARS[(cid * 17 + self.config.seed) % len(AVATARS)]
        # specialization drift start — totem biases initial role.
        # COPY: TOTEM_SPEC entries are mutated in place by drift; sharing them
        # across clans (or worlds!) would couple their specializations.
        spec = dict(TOTEM_SPEC.get(totem, {"warrior": 0.33, "farmer": 0.33, "scavenger": 0.34}))
        culture = f"{CULTURE_ADJECTIVES[(cid * 11 + self.config.seed) % len(CULTURE_ADJECTIVES)]} {CULTURE_NOUNS[(cid * 19 + self.config.seed) % len(CULTURE_NOUNS)]}"
        # Governance archetype (§AL)
        if founder and founder.caste in ("Gentleman", "Noble"):
            governance = "monarchy"
        elif founder and founder.caste == "Priest":
            governance = "theocracy"
        elif founder and founder.caste == "Soldier":
            governance = "junta"
        else:
            governance = "republic"

        founder_name = personal_name_for(founder.id, self.config.seed, founder.generation) if founder is not None else None


        self.clans[cid] = {
            "name": name,
            "founder_id": founder.id if founder is not None else None,
            "born_tick": self.tick,
            "color": CLAN_COLORS[(cid - 1) % len(CLAN_COLORS)],
            "totem": totem,
            "leader_id": founder.id if founder is not None else None,
            "governance": governance,
            "bylaws": {
                "rationing": False,
                "martial_law": False,
                "sanctuary": "open",
            },
            "task_board": {
                "priority": "balanced",
                "harvester_weight": 1.0,
                "guard_weight": 1.0,
            },
            "specialization": spec,
            "culture": culture,
            "culture_id": cid,
            "coalition_id": None,
            "larder": 0.0,
            # §AM: the clan granary — grain & cured rations kept against winter
            "granary": 0.0,
            "harvest_total": 0.0,
            "feast_until": 0,
            # §AN: acoustic dialect — drifts apart for isolated clans
            "dialect": 0.0,
            "tribute_to": None,
            "main_house_id": None,
            # §AP theology: clan faith pool + shrine level (0 none, 1 shrine, 2 temple)
            "faith": 0.0,
            "shrine_level": 0,
            "history": [
                {
                    "tick": self.tick,
                    "day": self.day,
                    "event": "founded",
                    "desc": f"Founded as {governance.capitalize()} by {founder_name or f'Leader #{founder.id}' if founder else 'Settlers'} (Day {self.day})",
                }
            ],
        }
        return cid

    def _log_clan_history(self, cid: int, event_type: str, desc: str) -> None:
        """AK: Record major historical milestones for a clan.

        §AN: the great days are also painted on the main house walls by
        the clan's artisans — a mural per milestone, visible to god.
        """
        clan = self.clans.get(cid)
        if not clan:
            return
        if "history" not in clan or not isinstance(clan["history"], list):
            clan["history"] = []
        clan["history"].append({
            "tick": self.tick,
            "day": self.day,
            "event": event_type,
            "desc": desc,
        })
        if len(clan["history"]) > 30:
            clan["history"].pop(0)
        # §AN murals — succession, conquest, feasts & temples earn a painting
        if event_type in ("leader_change", "hq_relocated", "takeover",
                          "war_declared", "festival", "banquet", "temple"):
            hid = clan.get("main_house_id")
            house = self.world.entities.get(hid) if hid is not None else None
            if isinstance(house, House):
                house.murals += 1

    def _set_main_house_for_clan(self, cid: int, house: House) -> None:
        """AK: Ensure strictly ONE main house per clan across entities and metadata."""
        if not cid or cid not in self.clans:
            return
        prev_hid = self.clans[cid].get("main_house_id")
        self.clans[cid]["main_house_id"] = house.id
        for e in self.world.entities.values():
            if isinstance(e, House) and e.clan_id == cid and not e.is_ruin:
                e.is_main = (e.id == house.id)
        # §AN: the clan raises a boundary stone on its border — trespassers ring it.
        if self.config.envoys_enabled and not any(s["clan_id"] == cid for s in self.boundary_stones):
            r = self.config.territory_radius
            for k in range(3):  # deterministic angles; first clear spot wins
                ang = (cid * 2.399 + k * 2.094) % (2 * math.pi)
                sx, sy = self.world.normalize(house.x + math.cos(ang) * r,
                                              house.y + math.sin(ang) * r)
                if not self._is_in_rock(sx, sy):
                    self.boundary_stones.append({"x": round(sx, 2), "y": round(sy, 2), "clan_id": cid})
                    break
        if prev_hid != house.id:
            self._log_clan_history(
                cid,
                "hq_relocated",
                f"Headquarters established at House #{house.id} ({house.x:.0f}, {house.y:.0f})",
            )

    def _clan_centroid(self, members: list[Creature]) -> tuple[float, float]:
        n = max(1, len(members))
        return sum(m.x for m in members) / n, sum(m.y for m in members) / n

    def _found_founding_clans(self) -> None:
        """§V Settlement seeding — every functional house anchors one clan and each
        founding creature joins its nearest house's clan, so soldiers, women,
        nobles and priests mix inside a settlement. `max_clans` caps society
        granularity: -1 = one clan per house; N ≥ 1 clusters the founders into
        exactly N spatial clans instead (greedy k-centre). Deterministic given
        the seed — never touches the rng."""
        cfg = self.config
        founders = sorted(self.world.creatures(), key=lambda c: c.id)
        if not founders:
            return
        houses = self._functional_houses()
        taken_leaders: set[int] = set()

        def found(members: list[Creature], anchor: House | None) -> int:
            leader: Creature | None = None
            pool = [m for m in members if m.id not in taken_leaders]
            if members and not pool:
                pool = list(members)  # more settlements than founders: share leaders
            if pool:
                if anchor is not None:
                    leader = min(
                        pool,
                        key=lambda c: (self.world.distance(c.x, c.y, anchor.x, anchor.y), c.id),
                    )
                else:
                    ax, ay = self._clan_centroid(members)
                    leader = min(pool, key=lambda c: (self.world.distance(c.x, c.y, ax, ay), c.id))
            if leader is not None:
                taken_leaders.add(leader.id)
            cid = self._new_clan(leader)
            for m in members:
                m.clan_id = cid
            return cid

        if cfg.max_clans >= 0:
            k = min(cfg.max_clans, len(founders))
            for members in self._cluster_founders_kcenter(founders, k) if k > 0 else []:
                found(members, None)
            # Anchor claims: each clan settles at the free house nearest its people.
            self._anchor_homeless_clans(sorted(self.clans.keys()))
        elif houses:
            buckets: dict[int, list[Creature]] = {h.id: [] for h in houses}
            for c in founders:
                home = self._nearest_house_to(c.x, c.y, houses)
                buckets[home.id].append(c)
            for h in houses:
                cid = found(buckets[h.id], h)
                if cfg.house_claim_enabled:
                    h.clan_id = cid
                    h.clan_color = self.clans[cid]["color"]
                    self._set_main_house_for_clan(cid, h)

    def _cluster_founders_kcenter(self, founders: list[Creature], k: int) -> list[list[Creature]]:
        """Greedy k-centre over the founding generation (deterministic, rng-free).

        First centre is the founder nearest the world's heart; each next centre
        is the founder farthest from every chosen centre (ties → lowest id).
        Membership goes to the nearest centre (ties → earliest centre)."""
        w = self.world
        cx, cy = self.config.width / 2, self.config.height / 2
        centres = [min(founders, key=lambda c: (w.distance(c.x, c.y, cx, cy), c.id))]
        while len(centres) < k:
            rest = [c for c in founders if all(c.id != ct.id for ct in centres)]
            if not rest:
                break
            nxt = max(
                rest,
                key=lambda c: (min(w.distance(c.x, c.y, ct.x, ct.y) for ct in centres), -c.id),
            )
            centres.append(nxt)
        groups: list[list[Creature]] = [[] for _ in centres]
        for c in founders:
            best_i, best_d = 0, math.inf
            for i, ct in enumerate(centres):
                d = w.distance(c.x, c.y, ct.x, ct.y)
                if d < best_d:
                    best_i, best_d = i, d
            groups[best_i].append(c)
        return [g for g in groups if g]

    def _anchor_homeless_clans(self, clan_ids: list[int]) -> None:
        """§V anchor claims — greedy matching over (clan, house) pairs by distance:
        every homeless clan settles at its nearest free house, each house hosts at
        most one clan. Clans left over (housing shortage) found a new settlement
        via `_claim_house_for_clan` (which respects pinned `num_houses`)."""
        # exclude clanless 0
        clan_ids = [cid for cid in clan_ids if cid and cid in self.clans]
        if not clan_ids:
            return
        if not self.config.house_claim_enabled:
            return
        houses = [h for h in self._functional_houses() if h.clan_id == 0]
        if not houses:
            for cid in clan_ids:
                self._claim_house_for_clan(cid)
            return
        pairs: list[tuple[float, int, int]] = []
        for cid in sorted(clan_ids):
            members = [c for c in self.world.creatures() if c.clan_id == cid]
            if not members:
                continue
            ax, ay = self._clan_centroid(members)
            for h in houses:
                pairs.append((self.world.distance(ax, ay, h.x, h.y), cid, h.id))
        claimed: set[int] = set()
        houses_by_id = {h.id: h for h in houses}
        for _, cid, hid in sorted(pairs):
            if cid in claimed or hid in claimed:
                continue
            claimed.add(cid)
            claimed.add(hid)
            h = houses_by_id[hid]
            h.clan_id = cid
            h.clan_color = self.clans[cid]["color"]
            if not self.clans[cid].get("main_house_id"):
                self._set_main_house_for_clan(cid, h)
            else:
                h.is_main = False
        # clans without a free house: build a settlement when unpinned (§L)
        # (ghost clans with no living members never build)
        for cid in sorted(clan_ids):
            if not any(h.clan_id == cid for h in self._functional_houses()):
                if any(c.clan_id == cid for c in self.world.creatures()):
                    self._claim_house_for_clan(cid)

    def _prune_extinct_clans(self) -> None:
        """§P0: archive clans with 0 living members and 0 owned functional houses.
        Runs every 100 ticks; keeps relations/_clan_members/farm_plots/banquet_last bounded."""
        if self.tick % 100 != 0 or not self.clans:
            return
        # §AX: use fresh world scan — cached _clan_members is stale for clans
        # minted during the current tick's creature loop (e.g. exile bands).
        alive_cids = {c.clan_id for c in self.world.creatures() if c.clan_id}
        owned = {h.clan_id for h in self._functional_houses() if h.clan_id}
        extinct = [cid for cid in list(self.clans.keys()) if cid not in alive_cids and cid not in owned]
        if not extinct:
            return
        extinct_set = set(extinct)
        for cid in extinct:
            info = self.clans.get(cid, {})
            born_tick = info.get("born_tick", 0)
            lifespan_ticks = max(0, self.tick - born_tick)
            self._emit(HistoryEvent(
                type="clan_extinction",
                tick=self.tick + 1,
                entity_id=0,
                x=0.0,
                y=0.0,
                payload={
                    "clan_id": cid,
                    "clan_name": info.get("name") or f"Clan #{cid}",
                    "born_tick": born_tick,
                    "lifespan_ticks": lifespan_ticks,
                    "lifespan_days": round(lifespan_ticks / 1200, 1),
                },
            ))
            del self.clans[cid]
            self._clan_members.pop(cid, None)
            self.farm_plots.pop(cid, None) if hasattr(self, 'farm_plots') else None
            self._banquet_last.pop(cid, None) if hasattr(self, '_banquet_last') else None
            self.clans.pop(cid, None)  # idempotent
        # clean relations involving extinct clans
        for pair in list(self.relations.keys()):
            if pair[0] in extinct_set or pair[1] in extinct_set:
                del self.relations[pair]
        for pair in list(getattr(self, '_declared_wars', {}).keys()):
            if pair[0] in extinct_set or pair[1] in extinct_set:
                del self._declared_wars[pair]

    @staticmethod
    def _relation_pair(a: int, b: int) -> tuple[int, int]:
        return (a, b) if a < b else (b, a)

    def _bump_relation(self, clan_a: int, clan_b: int, delta: int) -> None:
        if not clan_a or not clan_b or clan_a == clan_b:
            return
        pair = self._relation_pair(clan_a, clan_b)
        score = max(-100, min(100, self.relations.get(pair, 0) + delta))
        self.relations[pair] = score

    def _zone_of(self, score: int) -> int:
        if score >= self.config.alliance_threshold:
            return 1  # allies
        if score <= self.config.rivalry_threshold:
            return -1  # rivals
        return 0  # neutral

    def _learn_enemy(self, c: Creature, clan_id: int | None) -> None:
        """§X firsthand: this clan attacked me — remembered fresh at full confidence."""
        if not self.config.knowledge_enabled or not clan_id or clan_id == c.clan_id:
            return
        enemies = c.facts.setdefault("enemies", {})
        old = enemies.get(clan_id)
        enemies[clan_id] = {
            "tick": self.tick,
            "conf": 1.0,
            **({"prev_conf": old["conf"]} if old else {}),
        }

    def _emit_help(self, victim: Creature, aggressor: Creature) -> None:
        """§X Help call — an attacked creature rallies its clan to mob the attacker."""
        if not (self.config.communication_enabled and self.config.help_call_enabled):
            return
        self.signals.append({
            "x": round(victim.x, 2), "y": round(victim.y, 2),
            "kind": "help", "sender": victim.id,
            "clan_id": victim.clan_id or None, "born_tick": self.tick, "ttl": 12,
            "threat_x": round(aggressor.x, 2), "threat_y": round(aggressor.y, 2),
            "threat_clan": aggressor.clan_id or None,
        })

    def _mob_defenders(self, loser: Creature, winner: Creature) -> int:
        """Clan-mates of the victim within earshot of the fight (§X mobbing).

        AA: spatial query around the winner instead of scanning the whole
        roster inside the war pair loop (was O(n) per pair → O(n³)/tick).
        §AR S-0: the sleeping are fully deaf — a body in bed cannot mob.
        """
        if not (self.config.help_call_enabled and self.config.knowledge_enabled):
            return 0
        return sum(
            1
            for o in self.world.query_radius(winner.x, winner.y, self.config.help_radius)
            if o.kind == "creature"
            and o.clan_id == loser.clan_id  # type: ignore[union-attr]
            and o.id != loser.id
            and not o.is_predator  # type: ignore[union-attr]
            and not o.is_herbivore  # type: ignore[union-attr]
            and not o.sleeping  # type: ignore[union-attr]
        )

    def _update_war(self) -> None:
        """Rival-clan creatures fight on contact (§I). Indomitable Monolith reduces damage (§P/AP).

        AA: pair discovery via the spatial hash — id-ascending outer loop, each
        rival neighbour within attack_radius considered once, so the schedule
        is identical to the old O(n²) all-pairs scan at a fraction of the cost.
        """
        cfg = self.config
        if not cfg.war_enabled:
            return
        # §AP: synods and epiphanies impose a sacred truce — strife is stilled.
        if self.truce_ticks > 0:
            return
        # AF: pre-sorted in _refresh_cache; fallback if called outside step()
        creatures = self._cached_creatures_sorted if self._cached_creatures_sorted else sorted(self.world.creatures(), key=operator.attrgetter("id"))
        to_kill: list[tuple[Creature, Creature]] = []
        to_wound: list[tuple[Creature, Creature]] = []
        fallen: set[int] = set()  # losers already scheduled this tick
        r2 = cfg.attack_radius * cfg.attack_radius
        dist_sq = self.world.distance_sq
        w = self.world
        for a in creatures:
            if a.id not in w.entities or a.id in fallen or a.is_predator or a.is_herbivore or not a.clan_id:
                continue
            # §AT-4 H-1: the badly wounded cannot start a fight — they can
            # still be attacked, and grievously wounded bodies never initiate.
            if a.health < COMBAT_MIN_HEALTH or (a.wound_ticks > 0 and a.wound_severity >= 2):
                continue
            neighbours = [
                b
                for b in w.query_radius(a.x, a.y, cfg.attack_radius)
                if b.kind == "creature" and b.id > a.id and b.id not in fallen
            ]
            # §AX P0: early rival rejection — filter kin/non-rivals before assassin
            # checks and sorting (800 creatures → war step 15.6ms → <2ms).
            # Keep only: different clan, both have clan_id, and relation zone == -1 (rival).
            filtered: list[Creature] = []
            for nb in neighbours:  # type: ignore[union-attr]
                nb_c = cast(Creature, nb)
                if nb_c.is_predator or nb_c.is_herbivore or not nb_c.clan_id:
                    continue
                if a.clan_id == nb_c.clan_id:
                    continue
                pair_r = self._relation_pair(a.clan_id, nb_c.clan_id)
                if self._zone_of(self.relations.get(pair_r, 0)) != -1:
                    continue
                if nb_c.id not in w.entities:
                    continue
                filtered.append(nb_c)
            neighbours = filtered  # type: ignore[assignment]
            # §AS L-1 / §P0: bold/junta assassins prioritize enemy chiefs —
            # split without allocating a closure per attacker.
            is_assassin = (
                getattr(a, "trait", None) == "bold"
                or self.clans.get(a.clan_id, {}).get("governance") == "junta"
            )
            if is_assassin:
                chiefs = [cc for cc in neighbours if self.clans.get(cc.clan_id, {}).get("leader_id") == cc.id]  # type: ignore[union-attr]
                if chiefs:
                    chiefs.sort(key=lambda cc: cc.id)  # type: ignore[union-attr]
                    chief_ids = {cc.id for cc in chiefs}
                    rest = [cc for cc in neighbours if cc.id not in chief_ids]  # type: ignore[union-attr]
                    rest.sort(key=lambda cc: cc.id)  # type: ignore[union-attr]
                    neighbours = chiefs + rest
                else:
                    neighbours.sort(key=lambda cc: cc.id)  # type: ignore[union-attr]
            else:
                neighbours.sort(key=lambda cc: cc.id)  # type: ignore[union-attr]
            for b in neighbours:  # type: ignore[union-attr]
                b = cast(Creature, b)
                if b.id not in w.entities or b.is_predator or b.is_herbivore or not b.clan_id or a.clan_id == b.clan_id:
                    continue
                pair = self._relation_pair(a.clan_id, b.clan_id)
                if self._zone_of(self.relations.get(pair, 0)) != -1:
                    continue
                loser, winner = (a, b) if a.id < b.id else (b, a)
                # AA: original semantics — only previously-recorded LOSERS are
                # blocked; a fight's winner may still lose a later duel.
                if loser.id in fallen or winner.id in fallen:
                    continue
                # Indomitable Monolith: 30% damage reduction; warrior specialization adds bite (§P); traits bold/peaceful (§S)
                dmg = cfg.attack_damage
                # warrior clan hits harder
                w_spec = self.clans.get(winner.clan_id, {}).get("specialization", {}).get("warrior", 0.33) if winner.clan_id else 0.33
                dmg *= (0.85 + w_spec * 0.45)
                if winner.trait == "bold":
                    dmg *= 1.25
                elif winner.trait == "peaceful":
                    dmg *= 0.65
                # §AS L-5: the junta's soldiers live for war — their combat
                # mastery grows faster (skill gains scaled in the resolve pass)
                if self.clans.get(winner.clan_id, {}).get("governance") == "junta":
                    pass
                # §AS L-1: an army without its general fights at half strength;
                # a rally before battle sharpens every blade in earshot.
                if winner.clan_id and winner.clan_id not in getattr(self, "_leader_pos", {}):
                    dmg *= LEADERLESS_WAR_MULT
                if getattr(winner, "combat_boost_ticks", 0) > 0:
                    dmg *= 1.0 + COMBAT_RALLY_BONUS
                # §AS L-1: targeted assassination — striking at the enemy chief
                loser_is_enemy_chief = (
                    self.clans.get(loser.clan_id, {}).get("leader_id") == loser.id
                )
                if (
                    loser_is_enemy_chief
                    and (
                        winner.trait == "bold"
                        or self.clans.get(winner.clan_id, {}).get("governance") == "junta"
                    )
                ):
                    dmg *= 1.0 + ASSASSIN_ATTACK_BONUS
                # §AP: the Celestial Strike lends God's Wrath to its warriors
                dmg *= 1.0 + self._totem_stat(winner, "damage")
                if loser.trait == "paranoid":
                    # paranoid dodges? slight reduction
                    dmg *= 0.9
                if winner.energy < 0.20 * cfg.energy_max:
                    dmg *= 0.7  # exhaustion penalty
                if self._totem_stat(loser, "defense"):
                    dmg *= 1.0 - self._totem_stat(loser, "defense")
                # §X mobbing: a surrounded attacker hits softer
                dmg /= 1.0 + cfg.defense_weight * min(self._mob_defenders(loser, winner), 4)
                if dmg >= loser.health:
                    to_kill.append((loser, winner))
                else:
                    to_wound.append((loser, winner))
                fallen.add(loser.id)
        for loser, winner in to_kill:
            if loser.id not in self.world.entities:
                continue
            if hasattr(winner, "skills") and isinstance(winner.skills, dict):
                skill_gain = 3.0
                if self.clans.get(winner.clan_id, {}).get("governance") == "junta":
                    skill_gain *= JUNTA_COMBAT_SKILL  # §AS L-5
                winner.skills["combat"] = winner.skills.get("combat", 0.0) + skill_gain
            winner.energy = max(1.0, winner.energy - 6.0)
            winner.emote = "combat"
            winner.emote_ticks = 25
            loser.emote = "panic"
            loser.emote_ticks = 25
            self._emit_help(loser, winner)  # §X dying cry — the clan remembers
            self._learn_enemy(loser, winner.clan_id)
            self._learn_enemy(winner, loser.clan_id)
            self._kill(loser, "war")
            self._emit(
                HistoryEvent(
                    type="war",
                    tick=self.tick + 1,
                    entity_id=loser.id,
                    caste=loser.caste,
                    x=round(loser.x, 2),
                    y=round(loser.y, 2),
                    payload={
                        "winner": winner.id,
                        "a": loser.clan_id,
                        "b": winner.clan_id,
                        "a_name": self.clans.get(loser.clan_id, {}).get("name"),
                        "b_name": self.clans.get(winner.clan_id, {}).get("name"),
                        "lethal": True,
                    },
                )
            )
            # §AS L-1: killing the enemy chief breaks the army's will —
            # the war ends on the spot (forced peace).
            if loser_is_enemy_chief:
                pair2 = self._relation_pair(loser.clan_id, winner.clan_id)
                self.relations[pair2] = min(100, max(self.relations.get(pair2, 0), 10))
                self._declared_wars.pop(pair2, None)
                self._emit(
                    HistoryEvent(
                        type="peace",
                        tick=self.tick + 1,
                        entity_id=0,
                        payload={
                            "a": loser.clan_id, "b": winner.clan_id,
                            "a_name": self.clans.get(loser.clan_id, {}).get("name"),
                            "b_name": self.clans.get(winner.clan_id, {}).get("name"),
                            "reason": "leader_slain",
                        },
                    )
                )
                # §AS L-4: was this murder DECLARED? An undeclared regicide
                # turns every neutral stomach against the assassin's clan.
                formal = self._declared_wars.pop(
                    self._relation_pair(winner.clan_id, loser.clan_id), None
                )
                if formal is None:
                    self._emit(
                        HistoryEvent(
                            type="regicide",
                            tick=self.tick + 1,
                            entity_id=winner.id,
                            caste=winner.caste,
                            x=round(loser.x, 2),
                            y=round(loser.y, 2),
                            payload={
                                "victim": loser.id, "victim_clan": loser.clan_id,
                                "assassin_clan": winner.clan_id,
                                "assassin": winner.id,
                            },
                        )
                    )
                    for other in sorted(self.clans.keys()):
                        if other in (winner.clan_id, loser.clan_id):
                            continue
                        opair = self._relation_pair(other, winner.clan_id)
                        self.relations[opair] = max(-100, self.relations.get(opair, 0) + REGICIDE_RELATION_HIT)
                        vpair = self._relation_pair(other, loser.clan_id)
                        self.relations[vpair] = min(100, self.relations.get(vpair, 0) + REGICIDE_SYMPATHY)
            self._bump_relation(loser.clan_id, winner.clan_id, -5)
            # §AB mutual defence — the loser attacked a whole coalition
            self._mobilise_coalition(winner.clan_id, loser.clan_id)
            # Territory conquest — winner absorbs loser's territory and house (§S)
            loser_house = None
            for h in (self._cached_houses if self._cached_houses else self._functional_houses()):
                if isinstance(h, House) and h.clan_id == loser.clan_id and not h.is_ruin:
                    loser_house = h
                    break
            if loser_house is not None:
                winner_color = self.clans.get(winner.clan_id, {}).get("color")
                loser_cid = loser.clan_id
                loser_house.clan_id = winner.clan_id
                loser_house.clan_color = winner_color
                loser_house.is_main = False
                loser_house.takeover_tick = self.tick  # §AT-3 render flash
                # §AT-3 orphan cleanup: if this was the loser's seat, re-point
                # or clear it so no clan claims a house it no longer owns.
                if self.clans.get(loser_cid, {}).get("main_house_id") == loser_house.id:
                    remaining = [
                        h for h in (self._cached_houses or self._functional_houses())
                        if isinstance(h, House) and h.clan_id == loser_cid and not h.is_ruin
                    ]
                    if remaining:
                        self._set_main_house_for_clan(loser_cid, max(remaining, key=lambda h: h.size))
                    else:
                        self.clans[loser_cid]["main_house_id"] = None
                self._log_clan_history(
                    winner.clan_id, "conquest",
                    f"Conquered House #{loser_house.id} from {self.clans.get(loser_cid, {}).get('name')} (Day {self.day})",
                )
                self._emit(
                    HistoryEvent(
                        type="conquest",
                        tick=self.tick + 1,
                        entity_id=loser_house.id,
                        x=round(loser_house.x, 2),
                        y=round(loser_house.y, 2),
                        payload={"winner_clan": winner.clan_id, "loser_clan": loser_cid, "house_id": loser_house.id, "winner": winner.id, "loser": loser.id},
                    )
                )
            # §AM E.2 famine raid — a starving war party carries off the granary
            self._try_granary_raid(winner, loser)
        for loser, winner in to_wound:
            if loser.id not in self.world.entities:
                continue
            if hasattr(winner, "skills") and isinstance(winner.skills, dict):
                winner.skills["combat"] = winner.skills.get("combat", 0.0) + 1.2
            winner.energy = max(1.0, winner.energy - 6.0)
            loser.energy = max(1.0, loser.energy - 10.0)
            winner.emote = "combat"
            winner.emote_ticks = 20
            loser.emote = "panic"
            loser.emote_ticks = 20
            self._emit_help(loser, winner)  # §X wounded cry — rally the clan
            self._learn_enemy(loser, winner.clan_id)
            self._learn_enemy(winner, loser.clan_id)
            w_spec2 = self.clans.get(winner.clan_id, {}).get("specialization", {}).get("warrior", 0.33) if winner.clan_id else 0.33
            trait_mult = 1.0
            if winner.trait == "bold":
                trait_mult *= 1.25
            elif winner.trait == "peaceful":
                trait_mult *= 0.65
            if winner.equipped_item == "spear":
                trait_mult *= 1.2
            if winner.energy < 0.20 * cfg.energy_max:
                trait_mult *= 0.7  # exhaustion penalty
            if loser.trait == "paranoid":
                trait_mult *= 0.9
            dmg = cfg.attack_damage * (0.85 + w_spec2 * 0.45) * trait_mult * (1.0 - self._totem_stat(loser, "defense"))
            # §X mobbing softens blows on the wound path too
            dmg /= 1.0 + cfg.defense_weight * min(self._mob_defenders(loser, winner), 4)
            loser.health = max(0, loser.health - dmg)
            # §AT-4 H-1: a heavy blow leaves a lingering wound — regen halves
            # (or quarters, if grievous), the body hobbles, war is over for it.
            if dmg > WOUND_MIN_DAMAGE and loser.id in w.entities:
                loser.wound_ticks = self.rng.randint(WOUND_TICKS_BASE, WOUND_TICKS_BASE + 50)
                loser.wound_severity = 2 if dmg >= 40.0 else 1
            # wounded flees
            dx, dy = self.world.delta(loser.x, loser.y, winner.x, winner.y)
            loser.angle = math.atan2(dy, dx)
            self._emit(
                HistoryEvent(
                    type="war",
                    tick=self.tick + 1,
                    entity_id=loser.id,
                    caste=loser.caste,
                    x=round(loser.x, 2),
                    y=round(loser.y, 2),
                    payload={
                        "winner": winner.id,
                        "a": loser.clan_id,
                        "b": winner.clan_id,
                        "a_name": self.clans.get(loser.clan_id, {}).get("name"),
                        "b_name": self.clans.get(winner.clan_id, {}).get("name"),
                        "lethal": False,
                        "damage": round(dmg, 1),
                    },
                )
            )
            self._bump_relation(loser.clan_id, winner.clan_id, -3)
            # §AB mutual defence on the wound path too
            self._mobilise_coalition(winner.clan_id, loser.clan_id)
            # §AM E.2 famine raid — hunger follows the war band home
            self._try_granary_raid(winner, loser)

    def _try_granary_raid(self, winner: Creature, loser: Creature) -> None:
        """§AM E.2: a martial clan fighting beside a rival's granary hauls away
        what it can when its own stores run empty. Breadbasket clans learn why
        the neighbours build walls."""
        cfg = self.config
        if not (cfg.granaries_enabled and cfg.war_enabled):
            return
        raider_info = self.clans.get(winner.clan_id)
        victim_info = self.clans.get(loser.clan_id)
        if not raider_info or not victim_info or not loser.clan_id:
            return
        # famine condition: the raider's own stores are empty
        if float(raider_info.get("granary", 0.0)) + float(raider_info.get("larder", 0.0)) > 40.0:
            return
        hid = victim_info.get("main_house_id")
        granary_house = self.world.entities.get(hid) if hid is not None else None
        if not isinstance(granary_house, House) or granary_house.is_ruin:
            return
        if self.world.distance(winner.x, winner.y, granary_house.x, granary_house.y) > cfg.territory_radius:
            return  # too far from the store to carry anything off
        loot = min(RAID_GRANARY_MAX, float(victim_info.get("granary", 0.0)))
        if loot < 1.0:
            return
        victim_info["granary"] = float(victim_info.get("granary", 0.0)) - loot
        room = max(0.0, cfg.granary_capacity - float(raider_info.get("granary", 0.0)))
        raider_info["granary"] = float(raider_info.get("granary", 0.0)) + min(loot, room)
        self._bump_relation(loser.clan_id, winner.clan_id, -8)
        self._emit(
            HistoryEvent(
                type="raid",
                tick=self.tick + 1,
                entity_id=winner.id,
                caste=winner.caste,
                x=round(granary_house.x, 2), y=round(granary_house.y, 2),
                payload={
                    "a": winner.clan_id, "b": loser.clan_id,
                    "a_name": raider_info.get("name"), "b_name": victim_info.get("name"),
                    "loot": round(loot, 1),
                },
            )
        )

    def _update_relations(self) -> None:
        """Clan scores rise when strangers feast together and drift toward peace.

        AA: incremental — eater pairs come from the spatial hash instead of an
        O(eaters²) scan; dominant castes and border adjacency are computed once
        per tick (the dominant-caste pass was O(clans×creatures)); pairs that
        relax back to 0 are forgotten so the relation table stays bounded.
        """
        cfg = self.config
        w = self.world

        # Old zones are what the chronicle last saw (neutral for unseen pairs).
        old_zones: dict[tuple[int, int], int] = dict(self._relation_zones)

        # Shared feeding (+2): only actual eater pairs, found via the hash.
        # (Duplicates in _eaters_this_tick collapse — a creature eats once.)
        eaters = sorted(set(self._eaters_this_tick))
        if eaters:
            eater_ids = set(eaters)
            for aid in eaters:
                ea = w.entities.get(aid)
                if not isinstance(ea, Creature):
                    continue
                for n in sorted(
                    (x for x in w.query_radius(ea.x, ea.y, cfg.flock_radius)
                     if x.kind == "creature" and x.id in eater_ids and x.id > ea.id),
                    key=lambda x: x.id,
                ):
                    eb = cast(Creature, n)
                    if not ea.clan_id or not eb.clan_id or ea.clan_id == eb.clan_id:
                        continue
                    self._bump_relation(ea.clan_id, eb.clan_id, +2)

        # Emit events for bumps that crossed a threshold (including bumps done
        # outside this tick via _bump_relation).
        for pair in sorted(list(self.relations.keys())):
            old = old_zones.get(pair, 0)
            new = self._zone_of(self.relations[pair])
            if new != old and new != 0:
                a, b = pair
                self._emit(
                    HistoryEvent(
                        type="alliance" if new == 1 else "rivalry",
                        tick=self.tick + 1,
                        entity_id=0,
                        caste=None,
                        x=0.0,
                        y=0.0,
                        payload={"a": a, "b": b, "score": self.relations[pair]},
                    )
                )
            old_zones[pair] = new

        # Scores relax toward neutrality; crossing a threshold is news.
        rate = int(round(cfg.relation_drift_rate))
        for pair in sorted(list(self.relations.keys())):
            score = self.relations[pair]
            prev_zone = old_zones.get(pair, self._zone_of(score))
            if score > 0:
                score = max(0, score - rate)
            elif score < 0:
                score = min(0, score + rate)
            self.relations[pair] = score
            new_zone = self._zone_of(score)
            if new_zone != prev_zone and new_zone != 0:
                a, b = pair
                self._emit(
                    HistoryEvent(
                        type="alliance" if new_zone == 1 else "rivalry",
                        tick=self.tick + 1,
                        entity_id=0,
                        caste=None,
                        x=0.0,
                        y=0.0,
                        payload={"a": a, "b": b, "score": score},
                    )
                )
            if score == 0:
                # AA: neutral pairs are forgotten — bump re-creates on demand.
                del self.relations[pair]
                self._relation_zones.pop(pair, None)
            else:
                self._relation_zones[pair] = new_zone

        # Diplomacy depth — richer relation factors (§S)
        # Common enemy +, border-adjacency −, same-caste +
        # Applied as small per-tick bumps, still within -100..100
        # Common enemy: a and b share a rival c
        rival_sets: dict[int, set[int]] = {}
        for (a, b), score in self.relations.items():
            if self._zone_of(score) == -1:
                rival_sets.setdefault(a, set()).add(b)
                rival_sets.setdefault(b, set()).add(a)
        for (a, b) in list(self.relations.keys()):
            ra = rival_sets.get(a, set())
            rb = rival_sets.get(b, set())
            if ra & rb:
                self._bump_relation(a, b, +1)

        # Border adjacency: claimed houses within 2*territory_radius — via the
        # spatial hash instead of an O(houses²) scan.
        if cfg.territory_enabled:
            houses_by_clan: dict[int, House] = {}
            for e in w.entities.values():
                if isinstance(e, House) and e.clan_id and not e.is_ruin:
                    houses_by_clan[e.clan_id] = e  # type: ignore[assignment]
            done: set[tuple[int, int]] = set()
            reach = 2 * cfg.territory_radius
            for ca, ha in houses_by_clan.items():
                for n in w.query_radius(ha.x, ha.y, reach):
                    if not isinstance(n, House) or not n.clan_id or n.is_ruin or n.clan_id == ca:
                        continue
                    if w.distance(ha.x, ha.y, n.x, n.y) >= reach:
                        continue
                    pk = self._relation_pair(ca, n.clan_id)
                    if pk in done:
                        continue
                    done.add(pk)
                    self._bump_relation(pk[0], pk[1], -1)

        # Same-caste bonus: clans sharing the most common caste among members —
        # one pass over the cached roster (was one full roster scan PER CLAN).
        caste_counts: dict[int, dict[str, int]] = {}
        for c in self._get_creatures():
            if not c.clan_id:
                continue
            counts = caste_counts.setdefault(c.clan_id, {})
            counts[c.caste] = counts.get(c.caste, 0) + 1
        dominant = {
            cid: max(cnt.items(), key=lambda kv: kv[1])[0]
            for cid, cnt in caste_counts.items()
        }
        for (a, b) in list(self.relations.keys()):
            da = dominant.get(a)
            db = dominant.get(b)
            if da and da == db:
                self._bump_relation(a, b, +1)

        # §AP holy alliances: clans worshipping the same or a complementary
        # avatar sympathise — doctrine draws the faithful together.
        if self.config.totems_enabled and self.clans:
            avatars = {cid: info.get("totem") for cid, info in self.clans.items()}
            for (a, b) in list(self.relations.keys()):
                ta, tb = avatars.get(a), avatars.get(b)
                if not ta or not tb:
                    continue
                if ta == tb or AVATAR_ALLIES.get(ta) == tb or AVATAR_ALLIES.get(tb) == ta:
                    self._bump_relation(a, b, +1)

    def _update_territory(self) -> None:
        """§P: clan territory — members prefer own ground, trespass sours relations."""
        cfg = self.config
        if not cfg.territory_enabled:
            return
        # functional claimed houses are territory anchors
        houses = [h for h in (self._cached_houses if self._cached_houses else self._functional_houses()) if h.clan_id != 0]
        if not houses:
            return
        # Trespass: each creature inside a rival's radius slightly sours the two clans
        # Query spatial hash around each claimed house instead of scanning all creatures
        r = cfg.territory_radius
        r2 = r * r
        dist_sq = self.world.distance_sq
        decay_int = int(round(cfg.trespass_decay))
        for h in houses:
            for c in self.world.query_radius(h.x, h.y, r):
                if not isinstance(c, Creature) or not c.clan_id or c.is_predator or c.is_herbivore:
                    continue
                if h.clan_id == c.clan_id:
                    continue
                if dist_sq(c.x, c.y, h.x, h.y) <= r2:
                    if cfg.trespass_decay >= 1:
                        self._bump_relation(c.clan_id, h.clan_id, -decay_int)
                    else:
                        if self.rng.random() < cfg.trespass_decay:
                            self._bump_relation(c.clan_id, h.clan_id, -1)
                    # §AN C.3: the boundary stone rings — sentries walk the line
                    if (
                        cfg.envoys_enabled
                        and self.tick - self._stone_chime_last.get(h.clan_id, -STONE_CHIME_GAP) >= STONE_CHIME_GAP
                        and len(self.signals) < SIGNALS_MAX
                    ):
                        stone = next(
                            (s for s in self.boundary_stones if s["clan_id"] == h.clan_id
                             and dist_sq(s["x"], s["y"], c.x, c.y) <= 36.0),
                            None,
                        )
                        if stone is not None:
                            self._stone_chime_last[h.clan_id] = self.tick
                            self.signals.append({
                                "x": round(stone["x"], 2), "y": round(stone["y"], 2),
                                "kind": "chime", "sender": 0,
                                "clan_id": h.clan_id or None, "born_tick": self.tick, "ttl": 12,
                                "stone_x": stone["x"], "stone_y": stone["y"],
                                "trespasser_x": round(c.x, 2), "trespasser_y": round(c.y, 2),
                            })

    def _update_schism(self) -> None:
        """§S Schism — unhappy members split off as new clan and war parent."""
        cfg = self.config
        if not cfg.schism_enabled:
            return
        # One schism per tick max to keep determinism smooth
        # AA: one membership pass per tick (was a full roster scan PER CLAN).
        members_by_clan: dict[int, list[Creature]] = self._clan_members if self._clan_members else {}
        if not members_by_clan:
            for c in self._get_creatures():
                if c.clan_id:
                    members_by_clan.setdefault(c.clan_id, []).append(c)
        claimed_houses = {h.clan_id for h in (self._cached_houses if self._cached_houses else self._functional_houses()) if h.clan_id}
        for cid, info in list(self.clans.items()):
            members = members_by_clan.get(cid, [])
            pop = len(members)
            if pop < cfg.schism_min_pop:
                continue
            # Unhappy: starving or homeless (no house)
            has_house = cid in claimed_houses
            unhappy = 0
            for c in members:
                ratio = c.energy / cfg.energy_max if cfg.energy_max else 1
                if ratio <= cfg.starving_ratio:
                    unhappy += 1
                elif not has_house:
                    unhappy += 1
            if pop == 0 or unhappy / pop < cfg.schism_threshold:
                continue
            # Trigger schism: split unhappy half
            # Pick members to split: prioritize unhappy, then oldest
            def is_unhappy(c):
                ratio = c.energy / cfg.energy_max if cfg.energy_max else 1
                return ratio <= cfg.starving_ratio or not has_house
            unhappy_members = [c for c in members if is_unhappy(c)]
            other_members = [c for c in members if not is_unhappy(c)]
            # sort unhappy by age desc, others also
            unhappy_members.sort(key=lambda c: (-c.age, c.id))
            other_members.sort(key=lambda c: (-c.age, c.id))
            # take at least 1, at most pop//2
            take = max(1, min(pop // 2, len(unhappy_members) if unhappy_members else pop // 2))
            movers = unhappy_members[:take]
            if len(movers) < take:
                need = take - len(movers)
                movers += other_members[:need]
            if not movers:
                continue
            # Create new clan
            founder = sorted(movers, key=lambda c: (c.id))[0]
            new_cid = self._next_clan_id
            self._next_clan_id += 1
            adj = CLAN_ADJECTIVES[(new_cid * 13 + self.config.seed) % len(CLAN_ADJECTIVES)]
            noun = CLAN_NOUNS[(new_cid * 29 + self.config.seed) % len(CLAN_NOUNS)]
            if (new_cid * 7 + self.config.seed) % 10 < 3:
                name = f"Clan of the {adj} {noun}"
            else:
                name = f"{adj} {noun}"
            totem = None
            if self.config.totems_enabled:
                totem = AVATARS[(new_cid * 17 + self.config.seed) % len(AVATARS)]
            # inherit parent specialization with slight drift
            parent_spec = self.clans.get(cid, {}).get("specialization", {"warrior": 0.33, "farmer": 0.33, "scavenger": 0.34})
            # small random drift
            spec = dict(parent_spec)
            # culture inherits parent but may diverge
            parent_culture = self.clans.get(cid, {}).get("culture", "Unknown Rite")
            parent_cid = self.clans.get(cid, {}).get("culture_id", cid)
            # 15% chance to diverge into new culture on schism
            if self.rng.random() < 0.15:
                culture = f"{CULTURE_ADJECTIVES[(new_cid * 13 + self.config.seed) % len(CULTURE_ADJECTIVES)]} {CULTURE_NOUNS[(new_cid * 23 + self.config.seed) % len(CULTURE_NOUNS)]}"
                culture_id = new_cid
            else:
                culture = parent_culture
                culture_id = parent_cid
            self.clans[new_cid] = {
                "name": name,
                "founder_id": founder.id,
                "born_tick": self.tick + 1,
                "color": CLAN_COLORS[(new_cid - 1) % len(CLAN_COLORS)],
                "totem": totem,
                "leader_id": founder.id,
                "specialization": spec,
                "culture": culture,
                "culture_id": culture_id,
                "coalition_id": None,
                "larder": 0.0,
                "tribute_to": None,
            }
            for c in movers:
                c.clan_id = new_cid
            # House for new clan — claim free or spawn settlement
            if self.config.house_claim_enabled:
                self._claim_house_for_clan(new_cid)
                # if still homeless (no free house and num_houses pinned), new clan stays homeless (still schismed)
            # Rivalry with parent
            self.relations[self._relation_pair(cid, new_cid)] = -60
            self._relation_zones[self._relation_pair(cid, new_cid)] = -1
            self._emit(
                HistoryEvent(
                    type="schism",
                    tick=self.tick + 1,
                    entity_id=founder.id,
                    caste=founder.caste,
                    x=round(founder.x, 2),
                    y=round(founder.y, 2),
                    payload={
                        "parent": cid,
                        "new_clan": new_cid,
                        "parent_name": info.get("name"),
                        "new_name": name,
                        "members": [c.id for c in movers],
                        "member_count": len(movers),
                        "reason": "unrest",
                    },
                )
            )
            self._emit(
                HistoryEvent(
                    type="rivalry",
                    tick=self.tick + 1,
                    entity_id=0,
                    caste=None,
                    x=0.0,
                    y=0.0,
                    payload={"a": cid, "b": new_cid, "score": -60},
                )
            )
            break  # only one schism per tick

    def _coalition_of(self, clan_id: int) -> int | None:
        return self._clan_coalition.get(clan_id)

    def _coalition_soured(self, members: list[int]) -> bool:
        """True once any member pair falls out of friendship — the bloc dissolves."""
        for i, a in enumerate(members):
            for b in members[i + 1:]:
                if self.relations.get(self._relation_pair(a, b), 0) < 10:
                    return True
        return False

    def _dissolve_coalition(self, coal_id: int, reason: str) -> None:
        info = self.coalitions.pop(coal_id, None)
        if info is None:
            return
        for cid in list(info["members"]):
            if self._clan_coalition.get(cid) == coal_id:
                self._clan_coalition.pop(cid, None)
            clan = self.clans.get(cid)
            if clan is not None and clan.get("coalition_id") == coal_id:
                clan["coalition_id"] = None
        self._emit(
            HistoryEvent(
                type="coalition_dissolved",
                tick=self.tick + 1,
                entity_id=0,
                payload={"coalition": coal_id, "name": info.get("name"), "reason": reason,
                         "members": list(info["members"])},
            )
        )

    def _update_coalitions(self) -> None:
        """§AB Explicit coalitions — leaders propose blocs; allies join; soured ones dissolve."""
        cfg = self.config
        if not cfg.coalitions_enabled:
            return
        # Prune dead clans; a bloc below size or with sour relations dissolves.
        for coal_id in sorted(list(self.coalitions.keys())):
            info = self.coalitions[coal_id]
            info["members"] = [m for m in info["members"] if m in self.clans]
            if len(info["members"]) < max(1, cfg.coalition_min_size - 1) or not info["members"]:
                self._dissolve_coalition(coal_id, reason="faded")
            elif self._coalition_soured(info["members"]):
                self._dissolve_coalition(coal_id, reason="soured")
        # A clan petitions to join an existing bloc.
        if self.rng.random() < COALITION_JOIN_CHANCE:
            claimed_clans = {h.clan_id for h in (self._cached_houses if self._cached_houses else self._functional_houses()) if h.clan_id}
            unaligned = [
                cid for cid in sorted(self.clans.keys())
                if cid not in self._clan_coalition and cid in claimed_clans
            ]
            for cid in unaligned:
                joined = False
                for coal_id in sorted(self.coalitions.keys()):
                    members = self.coalitions[coal_id]["members"]
                    if len(members) >= 8:
                        continue
                    if all(
                        self.relations.get(self._relation_pair(cid, m), 0)
                        >= cfg.coalition_threshold
                        for m in members
                    ):
                        self.coalitions[coal_id]["members"].append(cid)
                        self._clan_coalition[cid] = coal_id
                        self.clans[cid]["coalition_id"] = coal_id
                        self._emit(
                            HistoryEvent(
                                type="coalition_joined",
                                tick=self.tick + 1,
                                entity_id=0,
                                payload={"coalition": coal_id,
                                         "name": self.coalitions[coal_id].get("name"),
                                         "clan": cid},
                            )
                        )
                        joined = True
                        break
                if joined:
                    break
        # A leader founds a new bloc among friendly unaligned clans.
        if self.rng.random() < COALITION_FORM_CHANCE:
            for cid in sorted(self.clans.keys()):
                if cid in self._clan_coalition:
                    continue
                friends = [
                    other
                    for other in sorted(self.clans.keys())
                    if other != cid
                    and other not in self._clan_coalition
                    and self.relations.get(self._relation_pair(cid, other), 0)
                    >= cfg.coalition_threshold
                ]
                if len(friends) + 1 < cfg.coalition_min_size:
                    continue
                members = [cid] + friends[:4]
                coal_id = self._next_coalition_id
                self._next_coalition_id += 1
                name_a = self.clans[cid].get("name", f"Clan {cid}")
                name_b = self.clans[members[1]].get("name", "") if len(members) > 1 else ""
                name = f"Pact of {name_a}" if not name_b else f"{name_a} – {name_b} Pact"
                self.coalitions[coal_id] = {
                    "name": name,
                    "leader_clan": cid,
                    "members": members,
                    "born_tick": self.tick,
                }
                for m in members:
                    self._clan_coalition[m] = coal_id
                    self.clans[m]["coalition_id"] = coal_id
                self._emit(
                    HistoryEvent(
                        type="coalition_formed",
                        tick=self.tick + 1,
                        entity_id=0,
                        payload={"coalition": coal_id, "name": name,
                                 "leader_clan": cid, "members": members},
                    )
                )
                break

    def _mobilise_coalition(self, attacker_clan: int | None, victim_clan: int | None) -> None:
        """§AB Mutual defence — strike one member and every bloc-mate turns on you."""
        if not attacker_clan or not victim_clan or not self.config.coalitions_enabled:
            return
        coal_id = self._clan_coalition.get(victim_clan)
        if not coal_id:
            return
        for m in self.coalitions.get(coal_id, {}).get("members", []):
            if m == victim_clan or m == attacker_clan:
                continue
            self._bump_relation(attacker_clan, m, -12)

    def _remembered_enemy(self, clan_id: int) -> int | None:
        """The freshest enemy the clan collectively remembers (§X union)."""
        ttl = max(1, self.config.knowledge_ttl)
        best: tuple[int, int] | None = None  # (tick, enemy)
        for c in self._clan_members.get(clan_id, ()):
            for enemy, meta in (c.facts.get("enemies") or {}).items():
                t = int(meta.get("tick", 0))
                if int(enemy) != clan_id and self.tick - t <= ttl and (best is None or t > best[0]):
                    best = (t, int(enemy))
        return best[1] if best is not None else None

    def _dispatch_herald(self, cid: int, leader: Creature, rival: int) -> None:
        """§AS L-4: the two chiefs stand too far apart to talk — dispatch the
        highest-caste healthy subject as a herald. The herald must survive
        the journey for diplomacy to succeed (envoy machinery resolves it)."""
        candidates = [
            m for m in self._clan_members.get(cid, ())
            if m.stage in ("adult", "elder")
            and not m.is_predator and not m.is_herbivore
            and m.health > 50.0 and getattr(m, "mission", None) is None
            and m.id != leader.id
        ]
        if not candidates:
            return
        herald = max(candidates, key=lambda m: (m.sides, -m.id))
        rleader_id = self.clans.get(rival, {}).get("leader_id")
        rleader = self.world.entities.get(rleader_id) if rleader_id is not None else None
        tx, ty = (
            (rleader.x, rleader.y) if isinstance(rleader, Creature)
            else (herald.x, herald.y)
        )
        herald.mission = {
            "type": "peace", "target_clan": rival,
            "x": round(tx, 2), "y": round(ty, 2),
            "deadline": self.tick + ENVOY_MISSION_TICKS,
        }
        self._log_clan_history(
            cid, "herald",
            f"Dispatched a herald to {self.clans.get(rival, {}).get('name')} (Day {self.day})",
        )

    def _update_leader_decisions(self) -> None:
        """§AB Leader agency — war, peace, tribute demand and betrayal surface as plots.

        God watches but never vetoes. The leader's heritable trait biases the
        hand: bold → war, peaceful → peace, paranoid → betrayal (with treason).
        """
        cfg = self.config
        if not cfg.leader_decisions_enabled:
            return
        # Prune war markers for dead clans and cooled-down feuds so the map
        # stays bounded and concluded wars can eventually be re-opened.
        if self._declared_wars and self.tick % 500 == 0:
            live = set(self.clans.keys())
            self._declared_wars = {
                p: t for p, t in self._declared_wars.items()
                if p[0] in live and p[1] in live
                and self.tick - t < WAR_DECLARE_COOLDOWN * 4
            }
        pops = {cid: len(m) for cid, m in self._clan_members.items()}
        for cid in sorted(self.clans.keys()):
            info = self.clans[cid]
            lid = info.get("leader_id")
            leader = self.world.entities.get(lid) if lid is not None else None
            if not isinstance(leader, Creature):
                continue
            if self.rng.random() >= LEADER_DECISION_CHANCE:
                continue
            trait = leader.trait
            acted = False
            # Betrayal: break an alliance and strike (paranoid hands first).
            if cfg.betrayal_enabled and trait in ("paranoid", "bold"):
                for pair, score in sorted(self.relations.items()):
                    if self._zone_of(score) != 1 or cid not in pair:
                        continue
                    victim = pair[1] if pair[0] == cid else pair[0]
                    self.relations[pair] = max(-100, score - 95)
                    self.relations[pair] = min(100, self.relations[pair])
                    self._emit(
                        HistoryEvent(
                            type="betrayal",
                            tick=self.tick + 1,
                            entity_id=lid,
                            caste=leader.caste,
                            x=round(leader.x, 2),
                            y=round(leader.y, 2),
                            payload={"a": cid, "b": victim,
                                     "a_name": info.get("name"),
                                     "b_name": self.clans.get(victim, {}).get("name")},
                        )
                    )
                    # Treason: sow false knowledge so third clans distrust the victim too.
                    for other in sorted(self.clans.keys()):
                        if other in (cid, victim):
                            continue
                        mates = self._clan_members.get(other, ())
                        if not mates:
                            continue
                        herald = mates[int(self.rng.random() * len(mates))]
                        if self.world.distance(herald.x, herald.y, leader.x, leader.y) <= TREASON_RADIUS:
                            self.signals.append({
                                "x": round(herald.x, 2), "y": round(herald.y, 2),
                                "kind": "knowledge", "sender": leader.id,
                                "clan_id": other or None, "born_tick": self.tick, "ttl": 12,
                                "fact": {"kind": "enemy", "clan_id": victim,
                                         "x": round(leader.x, 2), "y": round(leader.y, 2),
                                         "conf": 1.0},
                            })
                    acted = True
                    break
            if acted:
                continue
            # Peace: a weakened leader sues a rival for peace.
            # §AP: the Cosmic Scales keep reliable peace — any Scales leader,
            # whatever their trait, may sue, and offers land harder.
            scales_peace = self._totem_stat(leader, "peace") > 0
            if trait == "peaceful" or scales_peace or pops.get(cid, 0) < 3:
                for pair, score in sorted(self.relations.items()):
                    if self._zone_of(score) != -1 or cid not in pair:
                        continue
                    rival = pair[1] if pair[0] == cid else pair[0]
                    my_pop = pops.get(cid, 0)
                    if my_pop and my_pop <= pops.get(rival, 0):
                        # §AS L-4: peace needs a face-to-face meeting — if the
                        # two chiefs stand far apart the offer rides with a
                        # herald instead (envoy mission below).
                        rleader_id = self.clans.get(rival, {}).get("leader_id")
                        rleader = self.world.entities.get(rleader_id) if rleader_id is not None else None
                        leaders_close = isinstance(rleader, Creature) and (
                            self.world.distance(leader.x, leader.y, rleader.x, rleader.y) <= TALK_RADIUS
                        )
                        boost = 90 if scales_peace else 60
                        gov = info.get("governance", "republic")
                        if gov == "republic":
                            boost = int(boost * REPUBLIC_PEACE_MULT)  # §AS L-5
                        elif gov == "junta":
                            boost //= 2  # militarists are half believed
                        if leaders_close:
                            self.relations[pair] = min(100, score + boost)
                            # §AP/§AB fix: peace closes the feud — the pair may only
                            # be re-declared on after the full cooldown.
                            self._declared_wars.pop(pair, None)
                            self._emit(
                                HistoryEvent(
                                    type="peace",
                                    tick=self.tick + 1,
                                    entity_id=0,
                                    payload={"a": cid, "b": rival,
                                             "a_name": info.get("name"),
                                             "b_name": self.clans.get(rival, {}).get("name")},
                                )
                            )
                        elif cfg.envoys_enabled:
                            self._dispatch_herald(cid, leader, rival)
                        acted = True
                        break
            if acted:
                continue
            # §AN C.1 — a peaceful (or deliberative) leader commissions an
            # emissary: a healthy adult carries treaty terms to a rival's
            # main house. God sees the banner; no veto exists.
            if cfg.envoys_enabled and (trait == "peaceful" or info.get("governance") == "republic"):
                for pair, score in sorted(self.relations.items()):
                    if cid not in pair or self._zone_of(score) == 1:
                        continue
                    rival = pair[1] if pair[0] == cid else pair[0]
                    if rival not in self.clans:
                        continue
                    rinfo = self.clans[rival]
                    rhid = rinfo.get("main_house_id")
                    rhouse = self.world.entities.get(rhid) if rhid is not None else None
                    if not isinstance(rhouse, House):
                        continue
                    # pick the healthiest adult non-soldier as herald
                    candidates_m = [
                        m for m in self._clan_members.get(cid, ())
                        if m.stage == "adult" and not m.is_predator and not m.is_herbivore and m.health > 60.0 and getattr(m, "mission", None) is None
                    ]
                    if not candidates_m:
                        break
                    herald = max(candidates_m, key=lambda m: (m.health, -m.id))
                    herald.mission = {
                        "type": "peace", "target_clan": rival,
                        "x": round(rhouse.x, 2), "y": round(rhouse.y, 2),
                        "deadline": self.tick + ENVOY_MISSION_TICKS,
                    }
                    acted = True
                    break
            if acted:
                continue
            # War: declare on an enemy with specific calculated Casus Belli (§AL)
            if trait == "bold" or trait is None or info.get("governance") == "junta":
                # §AS L-5: a theocracy cannot declare war unilaterally — it
                # needs a priest elder at the chief's side to co-sign.
                if info.get("governance") == "theocracy":
                    priest_elder = next(
                        (
                            m for m in self._clan_members.get(cid, ())
                            if m.caste == "Priest" and m.stage in ("adult", "elder")
                            and self.world.distance(m.x, m.y, leader.x, leader.y) <= 15.0
                        ),
                        None,
                    )
                    if priest_elder is None:
                        continue
                enemy = self._remembered_enemy(cid)
                casus_belli = "blood_feud"
                if enemy is None:
                    # Check for famine raid or territory dispute
                    own_larder = float(info.get("larder", 0.0))
                    for pair, score in sorted(self.relations.items()):
                        if cid not in pair:
                            continue
                        rival = pair[1] if pair[0] == cid else pair[0]
                        rival_info = self.clans.get(rival, {})
                        if own_larder < 20.0 and float(rival_info.get("larder", 0.0)) > 60.0:
                            enemy = rival
                            casus_belli = "famine_raid"
                            break
                if enemy is not None and enemy in self.clans and enemy != cid:
                    pair = self._relation_pair(cid, enemy)
                    score = self.relations.get(pair, 0)
                    last_declared = self._declared_wars.get(pair)
                    # One war per pair: skip clans we are already fighting
                    # (zone -1) or that this clan declared on within the
                    # cooldown — a declaration must not repeat itself.
                    if (
                        self._zone_of(score) != -1
                        and (last_declared is None or self.tick - last_declared >= WAR_DECLARE_COOLDOWN)
                    ):
                        # §AS L-5: a republic deliberates two ticks before war.
                        if info.get("governance") == "republic":
                            pending = info.get("war_pending")
                            if pending is None or pending[0] != enemy:
                                info["war_pending"] = (enemy, self.tick)
                                continue
                            if self.tick - pending[1] < 2:
                                continue
                            info.pop("war_pending", None)
                        # §AS L-1: the chief raises the rally BEFORE the blade —
                        # long-distance declarations without it are weaker.
                        if len(self.signals) < SIGNALS_MAX:
                            self.signals.append({
                                "x": round(leader.x, 2), "y": round(leader.y, 2),
                                "kind": "rally", "sender": lid,
                                "clan_id": cid or None, "born_tick": self.tick,
                                "ttl": RALLY_SIGNAL_TTL,
                            })
                        self._bump_relation(cid, enemy, -50)
                        self._declared_wars[pair] = self.tick
                        enemy_name = self.clans.get(enemy, {}).get("name", f"Clan {enemy}")
                        self._log_clan_history(
                            cid,
                            "war_declared",
                            f"Declared war on {enemy_name} (Casus Belli: {casus_belli.replace('_', ' ').capitalize()}, Day {self.day})",
                        )
                        acted = True

            if acted:
                continue
            # Tribute: a strong clan demands protection money from a weak neighbour.
            if cfg.tribute_enabled:
                my_pop = pops.get(cid, 0)
                if my_pop < 2:
                    continue
                for other in sorted(self.clans.keys()):
                    if other == cid or self._clan_coalition.get(other) == self._clan_coalition.get(cid):
                        continue
                    oinfo = self.clans[other]
                    if oinfo.get("tribute_to") is not None:
                        continue
                    if my_pop < pops.get(other, 0) * 1.6:
                        continue
                    pair = self._relation_pair(cid, other)
                    if self._zone_of(self.relations.get(pair, 0)) == -1:
                        continue  # protectors don't extort active enemies
                    oinfo["tribute_to"] = cid
                    break

    def _update_larders(self) -> None:
        """§AB Clan larder — surplus is stored at the settlement, famine draws it down."""
        cfg = self.config
        if not cfg.resource_sharing_enabled:
            return
        houses_by_clan: dict[int, House] = {}
        for e in (self._cached_houses if self._cached_houses else self._functional_houses()):
            if isinstance(e, House) and e.clan_id and not e.is_ruin and e.clan_id not in houses_by_clan:
                houses_by_clan[e.clan_id] = e
        # §AS L-3: the larder answers to its chief. Deposits are accepted only
        # when a living leader stands at the settlement; withdrawals run at a
        # rate set by governance and by the leader's farming wisdom.
        leader_at_settlement: dict[int, bool] = {}
        larder_eff: dict[int, float] = {}
        for cid, info in self.clans.items():
            seat = houses_by_clan.get(cid)
            if seat is None:
                mh_id = info.get("main_house_id")
                if mh_id is not None:
                    mh_e = self.world.entities.get(mh_id)
                    if isinstance(mh_e, House) and not mh_e.is_ruin:
                        seat = mh_e
            lpos3 = getattr(self, "_leader_pos", {}).get(cid)
            present = (
                isinstance(seat, House) and lpos3 is not None
                and self.world.distance(lpos3[0], lpos3[1], seat.x, seat.y) <= self.config.territory_radius
            )
            leader_at_settlement[cid] = present
            gov = info.get("governance", "republic")
            eff = 1.0
            if gov == "republic":
                eff = REPUBLIC_LARDER_EFF
            elif gov == "junta":
                eff = JUNTA_LARDER_EFF
            elif gov == "monarchy":
                eff = 1.0
            if not present:
                eff *= 0.5  # no chief: only a trickle leaves the store
            else:
                leader_c = self.world.entities.get(info.get("leader_id"))
                if isinstance(leader_c, Creature):
                    eff *= 1.0 + leader_c.skills.get("farming", 0.0) / 50.0
            larder_eff[cid] = eff
        starving_by_clan: dict[int, int] = {}
        for c in self._get_creatures():
            if not c.clan_id or c.is_predator or c.is_herbivore:
                continue
            house = houses_by_clan.get(c.clan_id)
            if house is None:
                continue
            clan = self.clans.get(c.clan_id)
            if clan is None:
                continue

            ratio = c.energy / cfg.energy_max if cfg.energy_max else 1.0
            if ratio > 0.75:
                # §AS L-3: deposits need the chief's presence at the settlement
                if not leader_at_settlement.get(c.clan_id, False):
                    continue
                deposit = min(0.5, (ratio - 0.75) * 8.0)
                stored = float(clan.get("larder", 0.0))
                room = max(0.0, cfg.larder_capacity - stored)
                put = min(deposit, room)
                if put > 0:
                    c.energy -= put
                    clan["larder"] = stored + put
            elif ratio <= cfg.starving_ratio:
                stored = float(clan.get("larder", 0.0))
                if stored > 0:
                    take = min(GRANARY_WITHDRAW_RATE * larder_eff.get(c.clan_id, 1.0), stored)
                    clan["larder"] = stored - take
                    c.energy += take
                # §AM C: the dry, roofed granary feeds its own through famine
                if cfg.granaries_enabled:
                    gstored = float(clan.get("granary", 0.0))
                    if gstored > 0:
                        gtake = min(GRANARY_WITHDRAW_RATE, gstored)
                        clan["granary"] = gstored - gtake
                        c.energy = min(cfg.energy_max, c.energy + gtake)
                starving_by_clan[c.clan_id] = starving_by_clan.get(c.clan_id, 0) + 1
        # Tribute: vassals pay their protector on the interval.
        if cfg.tribute_enabled and self.tick % TRIBUTE_INTERVAL == 0:
            for cid in sorted(self.clans.keys()):
                info = self.clans[cid]
                protector = info.get("tribute_to")
                if protector is None or protector not in self.clans:
                    info["tribute_to"] = None
                    continue
                amount = min(float(info.get("larder", 0.0)), 30.0)
                if amount <= 0:
                    continue
                info["larder"] = float(info.get("larder", 0.0)) - amount
                pinfo = self.clans[protector]
                # §AS L-5: a kingdom extracts double protection money
                if pinfo.get("governance") == "monarchy":
                    amount *= MONARCHY_TRIBUTE_MULT
                room = max(0.0, cfg.larder_capacity - float(pinfo.get("larder", 0.0)))
                pinfo["larder"] = float(pinfo.get("larder", 0.0)) + min(amount, room)
                # §AN C.2: the tribute rides in a courier's panniers — grain and
                # herbs carried to the suzerain granary to keep the peace.
                if cfg.granaries_enabled:
                    gpay = min(15.0, float(info.get("granary", 0.0)))
                    if gpay > 0:
                        info["granary"] = float(info.get("granary", 0.0)) - gpay
                        proom = max(0.0, cfg.granary_capacity - float(pinfo.get("granary", 0.0)))
                        pinfo["granary"] = float(pinfo.get("granary", 0.0)) + min(gpay, proom)
                        payer_house = self.world.entities.get(info.get("main_house_id")) if info.get("main_house_id") is not None else None
                        if isinstance(payer_house, House) and len(self.signals) < SIGNALS_MAX:
                            self.signals.append({
                                "x": round(payer_house.x, 2), "y": round(payer_house.y, 2),
                                "kind": "courier", "sender": 0,
                                "clan_id": cid or None, "born_tick": self.tick, "ttl": 20,
                            })
                self._emit(
                    HistoryEvent(
                        type="tribute",
                        tick=self.tick + 1,
                        entity_id=0,
                        payload={"from": cid, "to": protector,
                                 "amount": round(amount, 1),
                                 "from_name": info.get("name"),
                                 "to_name": pinfo.get("name")},
                    )
                )
        # Allied aid: a full-bellied ally feeds a starving one during famine.
        if cfg.aid_rate > 0 and self.rng.random() < cfg.aid_rate:
            for (a, b), score in sorted(self.relations.items()):
                if self._zone_of(score) != 1:
                    continue
                la, lb = (
                    float(self.clans[x].get("larder", 0.0)) for x in (a, b)
                )
                donor, recv = (a, b) if la > lb else (b, a)
                ld, lr = max(la, lb), min(la, lb)
                if ld < cfg.larder_capacity * 0.5 or lr > cfg.larder_capacity * 0.25:
                    continue
                if starving_by_clan.get(recv, 0) <= 0:
                    continue
                aid = min(ld * 0.4, cfg.larder_capacity - lr)
                if aid <= 1:
                    continue
                self.clans[donor]["larder"] = ld - aid
                self.clans[recv]["larder"] = lr + aid

    def _update_defection(self) -> None:
        """§AB Defection — the unhappy walk to a healthier banner, even a rival's."""
        cfg = self.config
        if not cfg.defection_enabled:
            return
        houses_by_clan: set[int] = {
            e.clan_id
            for e in (self._cached_houses if self._cached_houses else self._functional_houses())
            if isinstance(e, House) and e.clan_id and not e.is_ruin
        }
        for c in self._get_creatures():
            if not c.clan_id or c.is_predator or c.is_herbivore:
                continue
            ratio = c.energy / cfg.energy_max if cfg.energy_max else 1.0
            unhappy = ratio <= cfg.starving_ratio or c.clan_id not in houses_by_clan
            if not unhappy or self.rng.random() >= DEFECT_CHANCE:
                continue
            reach = cfg.flock_radius * 3.0
            candidates: dict[int, float] = {}
            for o in self.world.query_radius(c.x, c.y, reach):
                if not isinstance(o, Creature) or o.id == c.id:
                    continue
                if not o.clan_id or o.clan_id == c.clan_id or o.is_predator or o.is_herbivore:
                    continue
                d = self.world.distance(c.x, c.y, o.x, o.y)
                if o.clan_id not in candidates or d < candidates[o.clan_id]:
                    candidates[o.clan_id] = d
            if not candidates:
                continue
            # The healthiest nearby clan wins the defector.
            def vitality(cid: int) -> tuple[float, float]:
                mates = self._clan_members.get(cid, [])
                if not mates:
                    return (0.0, -float(cid))
                avg = sum(m.energy for m in mates) / len(mates)
                roofed = 1.0 if cid in houses_by_clan else 0.0
                return (roofed, avg)
            target = max(candidates, key=vitality)
            old = c.clan_id
            c.clan_id = target
            self._emit(
                HistoryEvent(
                    type="defection",
                    tick=self.tick + 1,
                    entity_id=c.id,
                    caste=c.caste,
                    x=round(c.x, 2),
                    y=round(c.y, 2),
                    payload={"from": old, "to": target,
                             "from_name": self.clans.get(old, {}).get("name"),
                             "to_name": self.clans.get(target, {}).get("name")},
                )
            )
            break  # one defection per tick keeps the world calm

    def _update_diplomacy(self) -> None:
        """§AN orchestrator — envoys, boundary chimes, markets, caravans,
        dialect drift and omens. Fixed order keeps the rng stream stable."""
        cfg = self.config
        # — envoy arrival & mission hygiene (every tick, cheap scan) —
        if cfg.envoys_enabled:
            for c in self._get_creatures():
                mission = getattr(c, "mission", None)
                if not isinstance(mission, dict) or mission.get("type") != "peace":
                    continue
                expired = self.tick >= int(mission.get("deadline", 0))
                target_clan = int(mission.get("target_clan", 0))
                arrived = (
                    not expired
                    and self.world.distance_sq(c.x, c.y, float(mission.get("x", 0.0)), float(mission.get("y", 0.0)))
                    <= max(4.0, cfg.territory_radius * 0.5) ** 2
                )
                if not (arrived or expired or target_clan not in self.clans or c.id not in self.world.entities):
                    continue
                c.mission = None
                if arrived and c.id in self.world.entities and target_clan in self.clans:
                    self._bump_relation(c.clan_id, target_clan, ENVOY_RELATION_BOOST)
                    self._emit(
                        HistoryEvent(
                            type="peace_envoy",
                            tick=self.tick + 1,
                            entity_id=c.id,
                            caste=c.caste,
                            x=round(c.x, 2), y=round(c.y, 2),
                            payload={"a": c.clan_id, "b": target_clan,
                                     "a_name": self.clans.get(c.clan_id, {}).get("name"),
                                     "b_name": self.clans.get(target_clan, {}).get("name"),
                                     "banner": "📜"},
                        )
                    )
        # — prune stones & markets of dead clans —
        live = set(self.clans.keys())
        self.boundary_stones = [s for s in self.boundary_stones if s["clan_id"] in live]
        for pair in list(self.markets.keys()):
            a, b = pair
            zone = self._zone_of(self.relations.get(pair, 0))
            if a not in live or b not in live or zone != 1:
                del self.markets[pair]
        # — markets: allied neighbours found neutral trading posts & barter —
        if cfg.markets_enabled and self.tick % MARKET_CHECK_INTERVAL == 0:
            houses_by_clan: dict[int, House] = {}
            for h in (self._cached_houses if self._cached_houses else self._functional_houses()):
                if isinstance(h, House) and h.clan_id and not h.is_ruin:
                    houses_by_clan.setdefault(h.clan_id, h)
            reach = cfg.territory_radius * 3.0
            for pair, score in sorted(self.relations.items()):
                if self._zone_of(score) != 1 or pair in self.markets:
                    continue
                ha, hb = houses_by_clan.get(pair[0]), houses_by_clan.get(pair[1])
                if ha is None or hb is None or self.world.distance(ha.x, ha.y, hb.x, hb.y) > reach:
                    continue
                mx = round((ha.x + hb.x) / 2.0, 2)
                my = round((ha.y + hb.y) / 2.0, 2)
                if self._is_in_rock(mx, my):
                    continue
                self.markets[pair] = {"x": mx, "y": my, "born_tick": self.tick}
                self._emit(
                    HistoryEvent(
                        type="market",
                        tick=self.tick + 1,
                        entity_id=0,
                        x=mx, y=my,
                        payload={"a": pair[0], "b": pair[1],
                                 "a_name": self.clans.get(pair[0], {}).get("name"),
                                 "b_name": self.clans.get(pair[1], {}).get("name")},
                    )
                )
        if cfg.markets_enabled and self.markets and self.tick % MARKET_BARTER_INTERVAL == 0:
            for pair in sorted(self.markets.keys()):
                ia, ib = self.clans.get(pair[0]), self.clans.get(pair[1])
                if not ia or not ib:
                    continue
                ga, gb = float(ia.get("granary", 0.0)), float(ib.get("granary", 0.0))
                donor, recv = (ia, ib) if ga > gb else (ib, ia)
                surplus = max(ga, gb) - min(ga, gb)
                swap = min(20.0, surplus / 2.0)
                if swap < 2.0:
                    continue
                donor["granary"] = max(0.0, float(donor.get("granary", 0.0)) - swap)
                cap_room = max(0.0, cfg.granary_capacity - float(recv.get("granary", 0.0)))
                recv["granary"] = float(recv.get("granary", 0.0)) + min(swap, cap_room)
                self._bump_relation(pair[0], pair[1], 1)
        # — travelling peddler caravans: news and rare goods between distant clans —
        if cfg.markets_enabled and self.tick % CARAVAN_INTERVAL == 0 and len(self.clans) >= 2:
            ids = sorted(cid for cid in self.clans if any(m.stage == "adult" for m in self._clan_members.get(cid, ())))
            for i, a in enumerate(ids):
                for b in ids[i + 1:]:
                    pair = self._relation_pair(a, b)
                    if self._zone_of(self.relations.get(pair, 0)) == -1:
                        continue
                    last = self._caravan_last.get(pair, -CARAVAN_INTERVAL)
                    if self.tick - last < CARAVAN_INTERVAL:
                        continue
                    ia, ib = self.clans[a], self.clans[b]
                    # goods flow to the leaner store; the chronicle carries the news
                    donor, recv = (ia, ib) if float(ia.get("granary", 0.0)) >= float(ib.get("granary", 0.0)) else (ib, ia)
                    gift = min(10.0, float(donor.get("granary", 0.0)))
                    if gift > 0:
                        donor["granary"] = float(donor.get("granary", 0.0)) - gift
                        room_c = max(0.0, cfg.granary_capacity - float(recv.get("granary", 0.0)))
                        recv["granary"] = float(recv.get("granary", 0.0)) + min(gift, room_c)
                    self._bump_relation(a, b, 2)
                    self._caravan_last[pair] = self.tick
                    self._emit(
                        HistoryEvent(
                            type="caravan",
                            tick=self.tick + 1,
                            entity_id=0,
                            payload={"a": a, "b": b,
                                     "a_name": ia.get("name"), "b_name": ib.get("name"),
                                     "news": True},
                        )
                    )
                    break
                else:
                    continue
                break
        # — season turn: omens from the shrine & dialect drift —
        season = self._season()
        if self._omen_season != season:
            first_turn = self._omen_season is None
            self._omen_season = season
            next_season = SEASONS[(SEASONS.index(season) + 1) % 4]
            if cfg.omens_enabled and not first_turn:
                for cid in sorted(self.clans.keys()):
                    info = self.clans[cid]
                    if int(info.get("shrine_level", 0)) < 1:
                        continue
                    priest = next(
                        (m for m in self._clan_members.get(cid, ()) if m.caste == "Priest" and m.id in self.world.entities),
                        None,
                    )
                    if priest is None:
                        continue
                    shrine = self._shrine_pos(cid)
                    sx, sy = shrine if shrine else (priest.x, priest.y)
                    if len(self.signals) < SIGNALS_MAX:
                        self.signals.append({
                            "x": round(sx, 2), "y": round(sy, 2), "kind": "omen",
                            "sender": priest.id, "clan_id": cid or None,
                            "born_tick": self.tick, "ttl": OMEN_SIGNAL_TTL, "season": next_season,
                        })
                    self._log_clan_history(
                        cid, "omen",
                        f"A priest beheld an omen: the {next_season} approaches (Day {self.day})",
                    )
                    self._emit(
                        HistoryEvent(
                            type="omen",
                            tick=self.tick + 1,
                            entity_id=priest.id,
                            caste=priest.caste,
                            x=round(sx, 2), y=round(sy, 2),
                            payload={"clan_id": cid, "season": next_season,
                                     "clan_name": info.get("name")},
                        )
                    )
            # §AN E.2 linguistic drift — isolated clans grow apart in speech;
            # allies converge toward a shared tongue.
            if cfg.dialect_drift_enabled and not first_turn:
                s_idx = SEASONS.index(season)
                ally_map: dict[int, list[int]] = {}
                for (a, b), score in self.relations.items():
                    if self._zone_of(score) == 1:
                        ally_map.setdefault(a, []).append(b)
                        ally_map.setdefault(b, []).append(a)
                for cid in sorted(self.clans.keys()):
                    info = self.clans[cid]
                    d = float(info.get("dialect", 0.0))
                    mates = ally_map.get(cid)
                    if mates:
                        mean_ally = sum(float(self.clans[m].get("dialect", 0.0)) for m in mates) / len(mates)
                        d += (mean_ally - d) * 0.25
                    else:
                        wobble = ((cid * 31 + s_idx * 7 + cfg.seed) % 9 - 4) * DIALECT_STEP
                        d += wobble
                    info["dialect"] = round(max(-1.0, min(1.0, d)), 4)

    def _update_clan_task_boards_and_bylaws(self) -> None:
        """§AL Clan Division of Labor & Dynamic Bylaws."""
        if not self.clans:
            return
        is_winter = self._season() == "winter"

        for cid, clan in self.clans.items():
            if not isinstance(clan, dict):
                continue
            bylaws = clan.setdefault("bylaws", {"rationing": False, "martial_law": False, "sanctuary": "open"})
            task_board = clan.setdefault("task_board", {"priority": "balanced", "harvester_weight": 1.0, "guard_weight": 1.0})

            # 1. Food security & winter rationing
            larder = float(clan.get("larder", 0.0))
            if is_winter or larder < 30.0:
                bylaws["rationing"] = True
                task_board["priority"] = "food_security"
                task_board["harvester_weight"] = 2.0
            else:
                bylaws["rationing"] = False
                task_board["harvester_weight"] = 1.0

            # 2. Wartime martial law
            is_at_war = False
            for pair, score in self.relations.items():
                if cid in pair and score <= self.config.rivalry_threshold:
                    is_at_war = True
                    break

            if is_at_war:
                bylaws["martial_law"] = True
                task_board["priority"] = "defense"
                task_board["guard_weight"] = 2.5
            else:
                bylaws["martial_law"] = False
                task_board["guard_weight"] = 1.0

            # 3. §AT-4 H-2 plague response: the main house becomes an infirmary —
            # its beds heal twice as well while sickness walks the clan.
            members = self._clan_members.get(cid, ())
            bylaws["plague_response"] = sum(1 for cc in members if cc.infected) >= 2

    def _update_trade_caravans(self) -> None:
        """§AL Inter-Clan Trade Caravans & Economic Specialization Barter."""
        if not self.config.resource_sharing_enabled or self.tick % 80 != 0:
            return
        # Find agricultural clans with surplus and warrior clans
        for cid, info in self.clans.items():
            if not isinstance(info, dict):
                continue
            spec = info.get("specialization", {})
            farmer_ratio = spec.get("farmer", 0.33)
            larder = float(info.get("larder", 0.0))
            if farmer_ratio > 0.35 and larder >= 40.0:
                # Seek a trading partner with neutral or positive relations
                for other_cid, other_info in self.clans.items():
                    if other_cid == cid or not isinstance(other_info, dict):
                        continue
                    pair = self._relation_pair(cid, other_cid)
                    if self._zone_of(self.relations.get(pair, 0)) >= 0:
                        other_spec = other_info.get("specialization", {})
                        if other_spec.get("warrior", 0.33) > 0.35:
                            # Trade: 12 food for combat martial lore
                            trade_amount = 12.0
                            info["larder"] = max(0.0, larder - trade_amount)
                            other_info["larder"] = min(self.config.larder_capacity, float(other_info.get("larder", 0.0)) + trade_amount)
                            self._bump_relation(cid, other_cid, 12)
                            # Boost farmer clan combat training
                            clan_members = self._clan_members.get(cid) or [cc for cc in self._get_creatures() if cc.clan_id == cid]
                            for c in clan_members:
                                if hasattr(c, "skills") and isinstance(c.skills, dict):
                                    c.skills["combat"] = c.skills.get("combat", 0.0) + 1.0
                            break

    def _update_festivals_and_traditions(self) -> None:
        """§AL Tribal Traditions & Autumn Harvest Festival."""
        season_len = max(1, self.config.season_length)
        if self._season() == "autumn" and (self.tick % season_len == season_len - 1):
            houses_by_clan = {}
            for h in (self._cached_houses if self._cached_houses else self._functional_houses()):
                if isinstance(h, House) and h.clan_id and getattr(h, "is_main", False) and not getattr(h, "is_ruin", False):
                    houses_by_clan[h.clan_id] = h

            for cid, clan in self.clans.items():
                if not isinstance(clan, dict):
                    continue
                main_h = houses_by_clan.get(cid)
                if not main_h:
                    continue
                # All clan members near Main House celebrate
                members = self._clan_members.get(cid) or [cc for cc in self._get_creatures() if cc.clan_id == cid]
                for c in members:
                    if self.world.distance(c.x, c.y, main_h.x, main_h.y) <= 18.0:
                        c.energy = min(self.config.energy_max, c.energy + 25.0)
                        c.emote = "cheer"
                        c.emote_ticks = 30
                        lid = clan.get("leader_id")
                        if lid and lid != c.id:
                            if not hasattr(c, "trust") or c.trust is None:
                                c.trust = {}
                            c.trust[lid] = min(100.0, c.trust.get(lid, 0.0) + 10.0)
                        if c.stage in ("infant", "juvenile"):
                            if hasattr(c, "skills") and isinstance(c.skills, dict):
                                c.skills["farming"] = c.skills.get("farming", 0.0) + 2.0


                self._log_clan_history(
                    cid,
                    "festival",
                    f"Celebrated the Annual Autumn Harvest Festival (Day {self.day})",
                )

    def _update_politics(self) -> None:
        """§AB orchestrator — fixed order keeps the rng stream deterministic."""
        self._update_coalitions()
        self._update_leader_decisions()
        self._update_larders()
        self._update_trade_caravans()
        self._update_festivals_and_traditions()
        self._update_defection()
        self._update_clan_task_boards_and_bylaws()
        self._update_diplomacy()  # §AN envoys, markets, dialects & omens

    @staticmethod
    def _is_weak_prey(o: Creature) -> bool:
        """Starving, elder or wounded — the weak are legitimate prey (§AC)."""
        return o.status == "starving" or o.stage == "elder" or o.health < 50.0

    def _cannibal_prey(self, c: Creature, radius: float) -> Creature | None:
        """Nearest eligible living prey for a starving creature (§AC).

        Eligible: enemy-clan members (negative relation) and the weak of any
        clan. Never predators, wild beasts, healthy same-clan adults, infants
        or anyone safe indoors — roofs are sanctuary.
        """
        cfg = self.config
        best: Creature | None = None
        best_d = radius + 1e-9
        for o in self.world.query_radius(c.x, c.y, radius):
            if not isinstance(o, Creature) or o.id == c.id:
                continue
            if o.id not in self.world.entities:
                continue
            if o.is_predator or o.is_herbivore or o.indoors:
                continue  # the Carnivore is never prey; roofs are sanctuary
            if o.stage == "infant":
                continue
            kin = bool(c.clan_id) and o.clan_id == c.clan_id
            weak = self._is_weak_prey(o)
            if kin:
                # only desperate need applies, and only when god allows it
                if not cfg.eat_kin_enabled or not weak:
                    continue
                # §AP: the Cosmic Scales keep the law even while starving —
                # eating kin is a crime their dogma refuses.
                if self._totem_stat(c, "lawful"):
                    continue
            else:
                if not cfg.eat_enemy_enabled:
                    continue
                if not weak:
                    pair = self._relation_pair(c.clan_id, o.clan_id) if c.clan_id and o.clan_id else None
                    rel = self.relations.get(pair, 0) if pair else 0
                    if rel >= 0 or not c.clan_id or not o.clan_id:
                        continue  # strangers must be rivals to be on the menu
            d = self.world.distance(c.x, c.y, o.x, o.y)
            if d < best_d:
                best, best_d = o, d
        return best

    def _exile_kin_eater(self, eater: Creature) -> None:
        """§AC The price of kin-eating — cast out, remembered, warred upon."""
        cfg = self.config
        former = eater.clan_id
        if not former:
            return
        if cfg.exile_on_kin_eat:
            band = self._new_clan(eater)  # a one-being outcast band
            eater.clan_id = band
            stigma = max(1, int(cfg.kin_stigma))
            pair = self._relation_pair(former, band)
            score = -stigma
            self.relations[pair] = max(-100, min(100, score))
            zone = self._zone_of(score)
            if zone != 0:
                self._relation_zones[pair] = zone
            # witnesses remember the outcast band as an enemy (§X knowledge)
            for m in self.world.query_radius(eater.x, eater.y, TREASON_RADIUS):
                if isinstance(m, Creature) and m.clan_id == former:
                    self._learn_enemy(m, band)
            self._emit(
                HistoryEvent(
                    type="exile",
                    tick=self.tick + 1,
                    entity_id=eater.id,
                    caste=eater.caste,
                    x=round(eater.x, 2),
                    y=round(eater.y, 2),
                    payload={
                        "former_clan": former,
                        "band": band,
                        "former_name": self.clans.get(former, {}).get("name"),
                        "personal_name": personal_name_for(eater.id, self.config.seed, eater.generation),
                        "glyph": glyph_for(eater.id, self.config.seed, eater.generation),
                    },
                )
            )

    def _do_cannibalism(self, eater: Creature, prey: Creature) -> None:
        """§AC Kill & feed — contact kill, partial corpse, exile for kin-eaters."""
        cfg = self.config
        kin = bool(eater.clan_id) and prey.clan_id == eater.clan_id
        eater.cannibal_cooldown = CANNIBAL_COOLDOWN
        eater.energy = min(cfg.energy_max, eater.energy + cfg.cannibalism_energy)
        eater.meals += 1
        self._kill(prey, "cannibalism", corpse_energy_mult=CANNIBAL_CORPSE_MULT)
        self._emit(
            HistoryEvent(
                type="cannibalism",
                tick=self.tick + 1,
                entity_id=eater.id,
                caste=eater.caste,
                x=round(prey.x, 2),
                y=round(prey.y, 2),
                payload={"prey": prey.id, "prey_caste": prey.caste, "kin": kin},
            )
        )
        # §AR S-5: reputation is observable — witnesses shun the man-eater.
        pr_sq = cfg.perceive_radius * cfg.perceive_radius
        for o in self._get_creatures():
            if o.id == eater.id:
                continue
            if o.clan_id and o.clan_id == eater.clan_id:
                continue
            if self.world.distance_sq(o.x, o.y, eater.x, eater.y) <= pr_sq:
                if not hasattr(o, "trust") or o.trust is None:
                    o.trust = {}
                o.trust[eater.id] = max(-100.0, o.trust.get(eater.id, 0.0) - 20.0)
        if kin:
            self._exile_kin_eater(eater)

    def _update_clan_specialization(self) -> None:
        """§P Clan specialization — drift toward warrior/farmer/scavenger."""
        # AF: slice the history deque once before the clan loop; was O(history_len × num_clans)
        recent = list(itertools.islice(reversed(self.history), 80))
        # AF: build clan→house map from the house cache (avoids entity scan per clan)
        house_by_clan: dict[int, House] = {}
        for h in self._cached_houses:
            if isinstance(h, House) and h.clan_id and h.clan_id not in house_by_clan:
                house_by_clan[h.clan_id] = h
        for cid, info in self.clans.items():
            spec = info.get("specialization")
            if spec is None:
                spec = {"warrior": 0.33, "farmer": 0.33, "scavenger": 0.34}
                info["specialization"] = spec
            # totem bias already in founding; now environment drift
            house = house_by_clan.get(cid)
            # count recent war involvement (last 80 history)
            war_cnt = sum(1 for ev in recent if ev.type == "war" and (ev.payload.get("a") == cid or ev.payload.get("b") == cid))
            # count food/corpse near house (if has house)
            food_near = 0
            corpse_near = 0
            if house is not None:
                for e in self.world.query_radius(house.x, house.y, 18.0):
                    if e.kind == "food":
                        food_near += 1
                    elif e.kind == "corpse":
                        corpse_near += 1
                for fp in self.fertile:
                    if self.world.distance_sq(fp["x"], fp["y"], house.x, house.y) < 400.0:
                        food_near += 1
            # small drift per tick
            # warrior up if wars, farmer up if food_near, scavenger up if corpse_near
            # normalize drift to keep sum 1
            drift = 0.002
            if war_cnt > 0:
                spec["warrior"] = min(0.8, spec["warrior"] + drift * war_cnt)
            if food_near > 3:
                spec["farmer"] = min(0.8, spec["farmer"] + drift * 0.5)
            if corpse_near > 2:
                spec["scavenger"] = min(0.8, spec["scavenger"] + drift * 0.7)
            # slight decay toward 0.33 to avoid lock-in, plus random jitter
            for k in ("warrior", "farmer", "scavenger"):
                spec[k] += self.rng.uniform(-0.0005, 0.0005)
                spec[k] = max(0.05, min(0.85, spec[k]))
            # renormalize to 1
            tot = spec["warrior"] + spec["farmer"] + spec["scavenger"]
            for k in spec:
                spec[k] = round(spec[k] / tot, 3)

    def _update_culture(self) -> None:
        """§S Culture drift — spreads to neighbours, can split into rival traditions."""
        cfg = self.config
        if not cfg.culture_enabled:
            return
        # spread: allies within territory may adopt same culture
        if self.rng.random() < cfg.culture_spread_rate:
            # pick random allied pair
            allies = [pair for pair, score in self.relations.items() if self._zone_of(score)==1]
            if allies:
                a,b = self.rng.choice(allies)
                # decide direction: a adopts b's culture or vice versa
                ca = self.clans.get(a, {}).get("culture_id")
                cb = self.clans.get(b, {}).get("culture_id")
                if ca is not None and cb is not None and ca != cb:
                    # 50% chance a adopts b
                    if self.rng.random() < 0.5:
                        # a adopts b's culture
                        self.clans[a]["culture"] = self.clans[b].get("culture", "")
                        self.clans[a]["culture_id"] = cb
                    else:
                        self.clans[b]["culture"] = self.clans[a].get("culture", "")
                        self.clans[b]["culture_id"] = ca
        # split: small chance a clan's culture diverges (like schism but culture only)
        for cid, info in list(self.clans.items()):
            if self.rng.random() < 0.0004:  # rare
                new_culture = f"{self.rng.choice(CULTURE_ADJECTIVES)} {self.rng.choice(CULTURE_NOUNS)}"
                info["culture"] = new_culture
                info["culture_id"] = self._next_clan_id + 1000 + cid  # new id distinct
                self._emit(HistoryEvent(type="culture", tick=self.tick+1, entity_id=0, x=0, y=0, payload={"clan_id": cid, "culture": new_culture}))

