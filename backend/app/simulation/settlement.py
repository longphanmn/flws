"""Settlement mixin — housing economy, construction, claims, takeover, doorway navigation, wall geometry (BI-6)."""

from __future__ import annotations

import math
import random
from functools import lru_cache
from typing import Any, Callable, cast

from ..config import Config
from ..entities import (
    DEFAULT_RADIUS,
    Creature,
    House,
)
from ..protocol import HistoryEvent
from ..world import World, segments_intersect
from .constants import *

class SettlementMixin:
    def _pick_house_material(self, x: float | None = None, y: float | None = None) -> str:
        """Seeded material mix: straw common, stone rare (insulation: straw <
        wood < stone). §AQ PH-6: settlements beside a river dig clay — riverbank
        brick insulates better than anything but stays middling in durability.
        Consumes the rng only at house creation."""
        r = self.rng.random()
        if (
            x is not None and y is not None and self.rivers
            and self._in_river_band(x, y, pad=RIVER_SILT_RADIUS + 4.0)
            and r < 0.55
        ):
            return "clay"
        if r < 0.20:
            return "stone"
        if r < 0.55:
            return "wood"
        return "straw"

    def _point_in_any_house(self, x: float, y: float) -> bool:
        """True when the point stands under some roof (§AQ PH-2 sound block)."""
        for h in self._cached_houses:
            if abs(x - h.x) <= h.size / 2 and abs(y - h.y) <= h.size / 2:
                return True
        return False

    def _inside_house(self, c: Creature, h: House | None) -> bool:
        if h is None or h.is_ruin:
            return False
        return (
            abs(c.x - h.x) < h.size / 2 - 0.3 and abs(c.y - h.y) < h.size / 2 - 0.3
        )

    def _is_inside_house(self, c: Creature, h: House | None) -> bool:
        """Geometric containment inside the four walls of house h."""
        if h is None or h.is_ruin:
            return False
        half = h.size * 0.5
        return abs(c.x - h.x) < half and abs(c.y - h.y) < half

    def _is_point_inside_any_house(self, x: float, y: float, pad: float = 0.5) -> bool:
        """Check if (x, y) falls inside any non-ruin house structure."""
        houses = self._cached_houses if getattr(self, "_cached_houses", None) else self._functional_houses()
        for h in houses:
            if getattr(h, "is_ruin", False):
                continue
            half = h.size * 0.5 + pad
            dx = x - h.x
            if dx < 0: dx = -dx
            if dx >= half:
                continue
            dy = y - h.y
            if dy < 0: dy = -dy
            if dy < half:
                return True
        return False

    def _claim_bed(self, house: House) -> bool:
        """One bed per occupant until the house is full; creatures arrive in id order."""
        taken = self._beds.get(house.id, 0)
        if taken >= self._house_beds(house):
            return False
        self._beds[house.id] = taken + 1
        if hasattr(self, "_house_occupants"):
            self._house_occupants[house.id] = max(self._house_occupants.get(house.id, 0), self._beds[house.id])
        return True

    def _house_beds(self, house: House) -> int:
        """Beds scale with floor area: `house_capacity` is the law for an
        average 8×8 hall — smaller huts have fewer beds, and large houses
        are strictly capped at a maximum of 16 beds (HOUSE_MAX_BEDS)."""
        raw = int(self.config.house_capacity * (house.size * house.size) / HOUSE_REF_AREA)
        return max(1, min(HOUSE_MAX_BEDS, raw))

    def _functional_houses(self) -> list[House]:
        """Non-ruin houses in id order — the possible settlement anchors (§V).

        AF: fast-path returns the per-tick cache (sorted by id) when available.
        Falls back to full entity scan during initialization (pre-first-refresh).
        """
        if self._cached_houses:
            return self._cached_houses
        # Fallback: initialization or outside-tick context (e.g. _spawn_initial)
        return sorted(
            [e for e in self.world.entities.values() if isinstance(e, House) and not e.is_ruin],
            key=lambda h: h.id,
        )

    def _nearest_house_to(self, x: float, y: float, houses: list[House]) -> House | None:
        """Wrap-aware nearest house; ties broken by lower house id (deterministic)."""
        if not houses:
            return None
        return min(houses, key=lambda h: (self.world.distance(x, y, h.x, h.y), h.id))

    def _assign_house_claims(self) -> None:
        """§V Anchor claims — each homeless clan settles at the free house nearest
        its people (never round-robin): a clan's settlement IS its nearest house."""
        if not self.config.house_claim_enabled:
            return
        houses = self._functional_houses()
        # Clear stale claims from previous world generation / disabled period
        for h in houses:
            if h.clan_id and h.clan_id not in self.clans:
                h.clan_id = 0
                h.clan_color = None
                h.is_main = False
        # Clans that already own at least one house keep their claimed settlement
        claimed_clans = {h.clan_id for h in houses if h.clan_id}
        # §P0: only living clans can be homeless — dead entries bloat settlement ticks; exclude clanless 0
        living = {cid for cid in (self._clan_members.keys() if self._clan_members else {c.clan_id for c in self._get_creatures() if c.clan_id}) if cid}
        homeless = [cid for cid in living if cid not in claimed_clans]
        if not homeless:
            return
        self._anchor_homeless_clans(homeless)

    def _claim_house_for_clan(self, clan_id: int) -> None:
        """Claim nearest free house for homeless clan or found a new settlement (§V)."""
        houses = self._functional_houses()
        members = [c for c in self.world.creatures() if c.clan_id == clan_id]
        free = [h for h in houses if h.clan_id == 0]
        if free and members:
            ax, ay = self._clan_centroid(members)
            h = self._nearest_house_to(ax, ay, free)
            h.clan_id = clan_id
            h.clan_color = self.clans.get(clan_id, {}).get("color")
            if not self.clans.get(clan_id, {}).get("main_house_id"):
                self._set_main_house_for_clan(clan_id, h)
            else:
                h.is_main = False
            return
        # No free house: a new clan founds a new settlement (§L settlement economy)
        # But respect explicit overrides: tests/scenarios that pin num_houses keep housing shortage
        if self.config.shelter_enabled and self.config.num_houses < 0:
            founder = min(members, key=lambda c: (-c.age, c.id)) if members else None
            self._spawn_settlement_house(clan_id, near=founder)

    def _refresh_house_claims(self) -> None:
        """Sync house crests with the current law (enable/disable)."""
        houses = self._functional_houses()
        if not self.config.house_claim_enabled:
            for h in houses:  # type: ignore[union-attr]
                h.clan_id = 0
                h.clan_color = None
                h.is_main = False
        else:
            self._assign_house_claims()

    def _target_house_count(self) -> int:
        """Houses scale with map area and population to guarantee >=85% shelter coverage."""
        cfg = self.config
        if cfg.num_houses >= 0:
            return cfg.num_houses
        area = cfg.width * cfg.height
        density_base = round(area * max(cfg.house_density, 0.00055))
        # Ensure enough beds for >= 85% of carrying capacity or active population
        creatures = getattr(self, "_cached_creatures", None)
        pop = len(creatures) if creatures is not None else 100
        target_pop = max(pop, cfg.carrying_capacity if cfg.carrying_capacity > 0 else 100)
        beds_needed = int(target_pop * 0.85)
        # Average beds per house based on mean house size 6.8
        avg_beds = max(1.0, cfg.house_capacity * (6.8 * 6.8) / HOUSE_REF_AREA)
        houses_for_85pct = max(1, math.ceil(beds_needed / avg_beds))
        return max(density_base, houses_for_85pct)

    def _spawn_settlement_house(self, clan_id: int | None = None, near: Creature | None = None) -> House:
        """Spawn a new house — near a clan founder if given, else random; claim it if clan_id."""
        cfg = self.config
        max_radius = max(
            (c.radius for c in self._get_creatures()), default=DEFAULT_RADIUS
        )
        size = self.rng.uniform(cfg.house_min_size, cfg.house_max_size)
        x, y = self._find_non_overlapping_house_pos(size, near=near)
        door_width = min(size * 0.8, 2.0 * max_radius * cfg.door_clearance)
        house = House(
            x=x, y=y, size=size, door_width=door_width,
            door_side=self.rng.choice(("north", "east", "south", "west")),
            material=self._pick_house_material(x, y),
        )
        if clan_id is not None and self.config.house_claim_enabled:
            house.clan_id = clan_id
            house.clan_color = self.clans.get(clan_id, {}).get("color")
            if not self.clans.get(clan_id, {}).get("main_house_id"):
                self._set_main_house_for_clan(clan_id, house)
            else:
                house.is_main = False
        self.world.add(house)
        # Clear any wild plants on the new house foundation
        for fid in [
            e.id for e in self.world.entities.values()
            if e.kind == "food" and abs(e.x - x) < size * 0.5 + 0.5 and abs(e.y - y) < size * 0.5 + 0.5
        ]:
            self.world.remove(fid)
        self._emit(
            HistoryEvent(
                type="settlement", tick=self.tick + 1, entity_id=house.id,
                x=round(house.x, 2), y=round(house.y, 2),
                payload={"clan_id": clan_id, "size": round(size, 2)},
            )
        )
        return house

    def _try_house_takeover(self, cid: int, members: list[Creature], houses: list[House]) -> House | None:
        """§AT-2 Clan Invasion & Resource War — a desperate or growing clan lacking
        shelter or food invades a rival's settlement to secure shelter and plunder supplies.
        Conditions:
          - The invading clan has insufficient beds (len(members) > total_beds) or food shortages.
          - Targets the closest rival house; if undefended or if invader has military superiority,
            seizes the roof and plunders the rival's granary/larder for the starving population.
        Deterministic: nearest to clan centroid, ties by id."""
        if not self.config.house_claim_enabled or not members:
            return None
        ax, ay = self._clan_centroid(members)
        candidates: list[House] = []
        occupants = getattr(self, "_house_occupants", {})
        for h in houses:
            if h.is_ruin or h.clan_id == 0 or h.clan_id == cid:
                continue
            _tt = getattr(h, "takeover_tick", -9999)
            if _tt >= 0 and self.tick - _tt < 600:
                # 600 tick garrison immunity prevents immediate ping-pong takeovers
                continue
            if self.clans.get(h.clan_id, {}).get("main_house_id") == h.id:
                # Main seat protected — the clan seat is never taken (law preserved)
                continue
            rival_members = self._clan_members.get(h.clan_id, [])
            rival_beds = sum(self._house_beds(rh) for rh in houses if rh.clan_id == h.clan_id and not rh.is_ruin)
            # Invade if house is empty tonight and (rival has spare beds or invader has superiority)
            # Law: spare = rival population < half its beds (otherwise they need it)
            is_spare = len(rival_members) * 2 < rival_beds
            has_superiority = len(members) >= len(rival_members)
            is_empty_tonight = occupants.get(h.id, 0) == 0
            if is_empty_tonight and (is_spare or has_superiority):
                candidates.append(h)
        if not candidates:
            return None
        target = min(candidates, key=lambda h: (self.world.distance(ax, ay, h.x, h.y), h.id))
        old_cid = target.clan_id
        target.clan_id = cid
        target.clan_color = self.clans.get(cid, {}).get("color")
        target.is_main = False
        target.takeover_tick = self.tick

        # Plunder food resources from the victim clan to feed the invaders
        victim_info = self.clans.get(old_cid, {})
        invader_info = self.clans.get(cid, {})
        plundered = 0.0
        if victim_info:
            v_granary = float(victim_info.get("granary", 0.0))
            if v_granary > 5.0:
                plundered = min(50.0, v_granary * 0.6)
                victim_info["granary"] = max(0.0, v_granary - plundered)
                if invader_info:
                    invader_info["granary"] = float(invader_info.get("granary", 0.0)) + plundered
                    # Distribute food to feed hungry clan invaders immediately
                    for m in members:
                        if m.energy < 75.0:
                            m.energy = min(100.0, m.energy + 25.0)

        # The rival loses a roof and remembers the theft.
        self._bump_relation(cid, old_cid, -40)
        old_name = self.clans.get(old_cid, {}).get("name", f"Clan #{old_cid}")
        new_name = self.clans.get(cid, {}).get("name", f"Clan #{cid}")
        raid_desc = f" (plundered {plundered:.1f} food)" if plundered > 0 else ""
        self._log_clan_history(
            cid, "takeover",
            f"Invaded & seized House #{target.id} from {old_name}{raid_desc} (Day {self.day})",
        )
        self._log_clan_history(
            old_cid, "takeover_loss",
            f"Lost House #{target.id} to {new_name}{raid_desc} (Day {self.day})",
        )
        self._emit(
            HistoryEvent(
                type="takeover", tick=self.tick + 1, entity_id=target.id,
                x=round(target.x, 2), y=round(target.y, 2),
                payload={
                    "invader_clan": cid, "victim_clan": old_cid,
                    "invader_name": new_name, "victim_name": old_name,
                    "house_id": target.id, "plundered_food": round(plundered, 1),
                },
            )
        )
        return target

    def _update_settlements(self) -> None:
        """Settlement economy tick: grow to meet demand, crumble abandoned houses (§L)."""
        cfg = self.config
        if not cfg.shelter_enabled:
            return
        functional = self._functional_houses()
        # §AT-3 orphan audit runs every settlement tick — claims hygiene first.
        self._audit_house_claims(functional)
        # Respect explicit overrides: pinned scenarios (tests) keep exact housing
        if cfg.num_houses >= 0:
            return
        # — growth: replenish houses when ruined/shortage, paced every 100 ticks —
        target = self._target_house_count()
        if len(functional) < target and (self.tick % 100 == 0):
            self._spawn_settlement_house()
        # §AO Phase E: bed overflow last night is urgent social demand —
        # builders raise an emergency roof even at the density target.
        if (
            getattr(self, "_last_night_overflow", 0) >= BED_OVERFLOW_BUILD_THRESHOLD
            and self.tick % 50 == 0
        ):
            self._last_night_overflow = 0
            if len(functional) < int(target * 1.5):
                self._spawn_settlement_house()

        # — clan expansion: growing clans claim free houses, seize weak rivals'
        #    spares (§AT-2) or build new ones —
        if self.config.house_claim_enabled and (self.tick % 50 == 0):
            # If all clans died out but survivors remain, re-found clans so civilization continues
            if not self.clans and len(self._get_creatures()) >= 4:
                try:
                    self._found_founding_clans()
                except Exception:
                    pass

            living_members_by_clan: dict[int, list[Creature]] = {}
            for c in self._get_creatures():
                if c.clan_id:
                    living_members_by_clan.setdefault(c.clan_id, []).append(c)

            for cid, members in living_members_by_clan.items():
                clan_houses = [h for h in functional if isinstance(h, House) and h.clan_id == cid]
                total_beds = sum(self._house_beds(h) for h in clan_houses)

                # Ensure the clan has strictly ONE designated main house
                if clan_houses:
                    main_hid = self.clans.get(cid, {}).get("main_house_id")
                    if not any(h.id == main_hid for h in clan_houses):
                        main_h = max(clan_houses, key=lambda h: h.size)
                        self._set_main_house_for_clan(cid, main_h)
                    else:
                        for h in clan_houses:
                            h.is_main = (h.id == main_hid)

                # If clan population outgrows beds: claim nearby free house,
                # then invade a weak rival's empty spare (§AT-2), then build.
                if len(members) > total_beds:
                    ax, ay = self._clan_centroid(members)
                    unclaimed = [h for h in functional if isinstance(h, House) and h.clan_id == 0]
                    claimed_free = False
                    if unclaimed:
                        nearest_free = self._nearest_house_to(ax, ay, unclaimed)
                        max_d = cfg.territory_radius * 2.0 if cfg.territory_enabled else 60.0
                        if self.world.distance(ax, ay, nearest_free.x, nearest_free.y) <= max_d:
                            nearest_free.clan_id = cid
                            nearest_free.clan_color = self.clans[cid]["color"]
                            nearest_free.is_main = False
                            claimed_free = True
                    if not claimed_free:
                        invaded = self._try_house_takeover(cid, members, [h for h in functional if isinstance(h, House)])
                        if invaded is None and cfg.num_houses < 0 and len(functional) < target * 1.5:
                            rand_m = self.rng.choice(members)
                            exp_house = self._spawn_settlement_house(cid, near=rand_m)
                            exp_house.is_main = False

        # — decay: abandoned houses crumble to ruins —
        # Build living-clan set once
        living_clans = {c.clan_id for c in self._get_creatures() if c.clan_id}
        for h in list(functional):
            assert isinstance(h, House)
            # A house is abandoned if unclaimed, or its clan has no living members
            is_abandoned = (h.clan_id == 0) or (h.clan_id not in living_clans)
            if is_abandoned:
                h.abandoned_ticks = (getattr(h, "abandoned_ticks", 0) or 0) + 1
            else:
                h.abandoned_ticks = 0
            if h.abandoned_ticks >= cfg.house_decay_ticks:
                h.is_ruin = True
                h.clan_id = 0
                h.clan_color = None
                h.is_main = False
                # §AN B.3: ruins exhale an old danger — keep the young away,
                # and let explorers dig lost knowledge from the stones.
                if cfg.scent_enabled and len(self.signals) < SIGNALS_MAX:
                    self.signals.append({
                        "x": round(h.x, 2), "y": round(h.y, 2), "kind": "danger_scent",
                        "sender": h.id, "clan_id": None, "born_tick": self.tick, "ttl": DANGER_SCENT_TTL * 3,
                    })
                self._emit(
                    HistoryEvent(
                        type="ruin", tick=self.tick + 1, entity_id=h.id,
                        x=round(h.x, 2), y=round(h.y, 2),
                        payload={"abandoned_ticks": h.abandoned_ticks},
                    )
                )

    def _audit_house_claims(self, houses: list[House] | None = None) -> None:
        """§AT-3 orphan-house cleanup — a claim whose clan is missing or has no
        living member is cleared immediately so no house ends a tick owned by
        a ghost; the roof then decays as abandoned through the usual §L path."""
        if houses is None:
            houses = self._functional_houses()
        living: set[int] | None = None
        for h in houses:
            if not h.clan_id:
                continue
            if h.clan_id not in self.clans:
                stale = True
            else:
                if living is None:
                    living = {c.clan_id for c in self._get_creatures() if c.clan_id}
                stale = h.clan_id not in living
            if stale:
                # Re-point the clan's seat before wiping, so main_house_id
                # never dangles on a house the clan no longer owns.
                info = self.clans.get(h.clan_id)
                if info is not None and info.get("main_house_id") == h.id:
                    others = [
                        o for o in houses
                        if o.clan_id == h.clan_id and o.id != h.id and not o.is_ruin
                    ]
                    info["main_house_id"] = max(others, key=lambda o: o.size).id if others else None
                h.clan_id = 0
                h.clan_color = None
                h.is_main = False

    def _house_for(self, c: Creature, houses: list[Entity]) -> House | None:
        """Preferred shelter: the clan's own roofs while they have beds free;
        the clan leader resides and prioritizes the MAIN house; other kin
        spread across all clan houses.

        §AT-2/AT-3 hard exclusivity: a creature sleeps only under its own
        clan's roof (or an unclaimed roof). Foreign houses are never entered —
        one house, one clan — so rival bodies can't poison occupancy caps.
        When every eligible roof is full the creature queues at home instead."""
        if not houses:
            return None

        def dist_sq(h: House) -> float:
            return self.world.distance_sq(c.x, c.y, h.x, h.y)

        def has_room(h: House) -> bool:
            occ = max(getattr(self, "_house_occupants", {}).get(h.id, 0), self._beds.get(h.id, 0))
            if self._inside_house(c, h):
                occ = max(0, occ - 1)
            return occ < self._house_beds(h)

        def allowed(h: House) -> bool:
            return not self.config.house_claim_enabled or h.clan_id == 0 or h.clan_id == c.clan_id

        if getattr(c, "waypoints", None) and "home" in c.waypoints:
            hx, hy = c.waypoints["home"]
            h_pos_map = getattr(self, "_house_by_pos", None)
            h = h_pos_map.get((hx, hy)) if h_pos_map else None
            if h is not None and not h.is_ruin and allowed(h) and has_room(h):
                return h

        if self.config.house_claim_enabled and c.clan_id:
            clan_info = self.clans.get(c.clan_id, {})
            leader_id = clan_info.get("leader_id")
            main_hid = clan_info.get("main_house_id")

            own_houses = getattr(self, "_houses_by_clan", {}).get(c.clan_id, [])
            if own_houses:
                # Leader prioritizes living in the main house
                if c.id == leader_id:
                    main_house = next((h for h in own_houses if h.id == main_hid or getattr(h, "is_main", False)), own_houses[0])
                    if has_room(main_house):
                        return main_house

                # Members (or leader if main house full) choose nearest own house with room
                own_free = [h for h in own_houses if has_room(h)]
                if own_free:
                    return min(own_free, key=dist_sq)

            # All own roofs full (or none): spill to the nearest UNCLAIMED roof
            # with space — never into another clan's house (§AT-2/AT-3).
            unclaimed = getattr(self, "_unclaimed_houses", None)
            if unclaimed is None:
                unclaimed = [h for h in houses if isinstance(h, House) and not h.is_ruin and h.clan_id == 0]
            free = [h for h in unclaimed if has_room(h)]
            if free:
                return min(free, key=dist_sq)

            # Every eligible roof is full: queue at main house (if leader) or nearest own house
            if own_houses:
                if c.id == leader_id:
                    return next((h for h in own_houses if h.id == main_hid or getattr(h, "is_main", False)), own_houses[0])
                return min(own_houses, key=dist_sq)
            return None

        # Clanless creature (or claims disabled): all non-ruined roofs count when claims disabled.
        unclaimed = [
            h for h in houses
            if isinstance(h, House) and not h.is_ruin and (h.clan_id == 0 or not self.config.house_claim_enabled)
        ]
        free = [h for h in unclaimed if has_room(h)]
        return min(free, key=dist_sq) if free else None

    def _door_pos(self, h: House) -> tuple[float, float]:
        """Center of the doorway gap (where creatures can pass)."""
        half = h.size / 2
        if h.door_side == "north":
            return h.x + h.door_offset, h.y - half
        if h.door_side == "south":
            return h.x + h.door_offset, h.y + half
        if h.door_side == "west":
            return h.x - half, h.y + h.door_offset
        # east
        return h.x + half, h.y + h.door_offset

    def _house_entry_target(self, c: Creature, h: House) -> tuple[float, float]:
        """§L Door-seek waypoints — no more grinding at a blank wall.

        Outside a house, the creature aims at a stand-off lane `margin` off
        its NEAREST face: level with the doorway when the door is on this
        face, the door-side corner when the door is around the corner, and
        the short-way corner when the door sits on the far face. Rounding a
        corner hands over to the next face, so the body follows the edges
        until it sees the gap — then walks straight through it. Deterministic,
        rng-free geometry."""
        w = self.world
        half = h.size / 2
        dx, dy = w.delta(c.x, c.y, h.x, h.y)  # house centre -> creature
        ax, ay = abs(dx), abs(dy)
        if ax < half - 0.3 and ay < half - 0.3:
            return h.x, h.y  # already under the roof: settle toward its heart
        m = 0.9  # stand-off lane off the wall
        lim = max(0.5, half - 0.8)  # slide clamp inside the face ends
        dw = max(h.door_width * 0.7, 2.0)  # door alignment tolerance (§BE-2 wider entrance funnel)
        sx = 1.0 if dx >= 0 else -1.0
        sy = 1.0 if dy >= 0 else -1.0
        if ax >= ay:  # nearest face: east / west
            face = "east" if sx > 0 else "west"
            out_x = h.x + sx * (half + m)
            if h.door_side == face:
                if abs(dy - h.door_offset) <= dw:
                    # aligned with the gap: walk straight in
                    return h.x + sx * max(1.0, half - 1.6), h.y + h.door_offset
                return out_x, h.y + max(-lim, min(lim, h.door_offset))
            if h.door_side in ("north", "south"):
                # door around the corner: head for the door-side corner
                return out_x, h.y + (half + m) * (1.0 if h.door_side == "south" else -1.0)
            # door on the far face: take the short way round this one
            return out_x, h.y + sy * (half + m)
        # nearest face: north / south
        face = "south" if sy > 0 else "north"
        out_y = h.y + sy * (half + m)
        if h.door_side == face:
            if abs(dx - h.door_offset) <= dw:
                return h.x + h.door_offset, h.y + sy * max(1.0, half - 1.6)
            return h.x + max(-lim, min(lim, h.door_offset)), out_y
        if h.door_side in ("east", "west"):
            return h.x + (half + m) * (1.0 if h.door_side == "east" else -1.0), out_y
        return h.x + sx * (half + m), out_y

    def _house_exit_target(self, c: Creature, h: House) -> tuple[float, float]:
        """§L Door-exit waypoint: direct path through the doorway to the outside stand-off lane."""
        half = h.size / 2
        m = 0.6
        dx, dy = self._door_pos(h)

        if h.door_side == "north":
            return dx, h.y - half - m
        if h.door_side == "south":
            return dx, h.y + half + m
        if h.door_side == "west":
            return h.x - half - m, dy
        # east
        return h.x + half + m, dy

    def _house_overlaps(self, x: float, y: float, size: float) -> bool:
        """Check if a house at x,y,size would overlap any existing house or rock.

        Houses keep at least `house_gap` clear space between walls so the alley
        between two shelters stays passable — creatures wedged in a tighter gap
        block on a wall whichever way they turn.
        """
        cfg = self.config
        # check houses
        for e in self.world.entities.values():
            if isinstance(e, House) and not e.is_ruin:
                # use world distance for wrap
                dist = self.world.distance(x, y, e.x, e.y)
                min_dist = size / 2 + e.size / 2 + max(cfg.house_gap, 1.5)
                if dist < min_dist:
                    return True
        # check rocks
        for r in self.rocks:
            dist = self.world.distance(x, y, r["x"], r["y"])
            if dist < size / 2 + r["r"] + 1.0:
                return True
        # §AQ PH-3: no roof straddles the water — keep houses off the channels
        if self._in_river_band(x, y, pad=size / 2 + 2.0):
            return True
        return False

    def _find_non_overlapping_house_pos(self, size: float, near: Creature | None = None) -> tuple[float, float]:
        """Find a non-overlapping house position, trying near founder if given."""
        cfg = self.config
        margin = size / 2
        # try near founder first
        if near is not None:
            for _ in range(30):
                x = (near.x + self.rng.uniform(-12, 12)) % cfg.width
                y = (near.y + self.rng.uniform(-12, 12)) % cfg.height
                x = max(margin, min(cfg.width - margin, x))
                y = max(margin, min(cfg.height - margin, y))
                if not self._house_overlaps(x, y, size):
                    return x, y
        # fallback to random with retries
        for _ in range(50):
            x = self.rng.uniform(margin, max(margin, cfg.width - margin))
            y = self.rng.uniform(margin, max(margin, cfg.height - margin))
            if not self._house_overlaps(x, y, size):
                return x, y
        # last resort: return random even if overlaps (avoid infinite loop on crowded map)
        return self.rng.uniform(margin, max(margin, cfg.width - margin)), self.rng.uniform(margin, max(margin, cfg.height - margin))

    def _rand_house_pos(self, size: float) -> tuple[float, float]:
        """Position keeping the whole house inside the world edge (with overlap avoidance)."""
        return self._find_non_overlapping_house_pos(size)

def _house_wall_segments(h: House) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """The house's wall segments; the door side is split around the doorway."""
    return list(
        _wall_segments_cached(
            (h.id, h.x, h.y, h.size, h.door_width, h.door_side or "south", h.door_offset or 0.0)
        )
    )

@lru_cache(maxsize=1024)
def _wall_segments_cached(
    key: tuple,
) -> tuple[tuple[tuple[float, float], tuple[float, float]], ...]:
    """Wall segments are pure geometry — cache them per house.

    Called ~10k times per tick across all creatures; rebuilding the segment
    list each call used to be a top-3 hotspot in the tick profile.
    """
    hid, x, y, size, door_w, side, offset = key
    half = size / 2
    x0, y0 = x - half, y - half
    x1, y1 = x + half, y + half
    d = door_w / 2
    c = offset
    if side == "north":
        return (
            ((x0, y0), (x + c - d, y0)),
            ((x + c + d, y0), (x1, y0)),
            ((x0, y0), (x0, y1)),
            ((x1, y0), (x1, y1)),
            ((x0, y1), (x1, y1)),
        )
    if side == "west":
        return (
            ((x0, y0), (x1, y0)),
            ((x0, y1), (x1, y1)),
            ((x1, y0), (x1, y1)),
            ((x0, y0), (x0, y + c - d)),
            ((x0, y + c + d), (x0, y1)),
        )
    if side == "east":
        return (
            ((x0, y0), (x1, y0)),
            ((x0, y0), (x0, y1)),
            ((x0, y1), (x1, y1)),
            ((x1, y0), (x1, y + c - d)),
            ((x1, y + c + d), (x1, y1)),
        )
    # south (default)
    return (
        ((x0, y0), (x1, y0)),
        ((x0, y0), (x0, y1)),
        ((x1, y0), (x1, y1)),
        ((x0, y1), (x + c - d, y1)),
        ((x + c + d, y1), (x1, y1)),
    )

def _house_wall_segments_closed(h: House) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """Four fully closed walls — the doorway sealed (predator refuge, §L)."""
    half = h.size / 2
    x0, y0 = h.x - half, h.y - half
    x1, y1 = h.x + half, h.y + half
    return [
        ((x0, y0), (x1, y0)),
        ((x0, y0), (x0, y1)),
        ((x1, y0), (x1, y1)),
        ((x0, y1), (x1, y1)),
    ]

def _path_crosses_wall(
    px: float, py: float, qx: float, qy: float, h: House, predator_blocked: bool = False
) -> bool:
    """True if the movement path p->q crosses a house wall (door is passable unless predator_blocked)."""
    if h.is_ruin:
        return False  # crumbled ruins don't block
    # Broad phase — bounding-box reject. Most creature-house pairs are far
    # apart; this cheap test skips the expensive per-segment math below.
    half = h.size * 0.5
    hx, hy = h.x, h.y
    min_x = px if px < qx else qx
    max_x = qx if px < qx else px
    min_y = py if py < qy else qy
    max_y = qy if py < qy else py
    if max_x < hx - half or min_x > hx + half or max_y < hy - half or min_y > hy + half:
        return False
    # BJ-5: compiled C segment intersection for the door-collision hotspot
    # (same math as python segments_intersect; falls back on any error).
    try:
        from ..native_core import native_path_crosses_wall as _native_wall  # type: ignore

        segments = _house_wall_segments_closed(h) if predator_blocked else _house_wall_segments(h)
        flat = [(a[0], a[1], b[0], b[1]) for a, b in segments]
        return bool(_native_wall(float(px), float(py), float(qx), float(qy), flat))
    except Exception:
        pass
    path = ((px, py), (qx, qy))
    segments = _house_wall_segments_closed(h) if predator_blocked else _house_wall_segments(h)
    return any(
        segments_intersect(path[0], path[1], a, b)
        for a, b in segments
    )

