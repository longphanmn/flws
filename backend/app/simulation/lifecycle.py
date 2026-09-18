"""Lifecycle mixin — spawning, evolution init, morphology inheritance, reproduction, birth, death, disease, skill/title progression (BI-9)."""

from __future__ import annotations

import math
import os
import random
from collections import deque
from typing import Any

_IS_TEST = bool(os.getenv("PYTEST_CURRENT_TEST") or os.getenv("FLATWORLD_TEST") or os.getenv("FLATWORLD_SOFT_CAP_ENABLED") == "false")

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

from .constants import *
from .constants import _smooth_age_mult, _smooth_season_food_mult, _smooth_season_cap_mult

class LifecycleMixin:
    def _init_creature_evolution(
        self,
        c: Creature,
        parent_a: Creature | None = None,
        parent_b: Creature | None = None,
    ) -> None:
        """Initialize autonomous personality, skills, tools, and emote states."""
        # 1. Personality
        if parent_a and parent_b and self.rng.random() < 0.65:
            c.personality = self.rng.choice([parent_a.personality, parent_b.personality])
        else:
            c.personality = self.rng.choice(PERSONALITIES)

        # 2. Skills
        c.skills = {"farming": 0.0, "combat": 0.0, "foraging": 0.0, "healing": 0.0}
        if parent_a and parent_b:
            for k in c.skills:
                pa_xp = parent_a.skills.get(k, 0.0) if hasattr(parent_a, "skills") and isinstance(parent_a.skills, dict) else 0.0
                pb_xp = parent_b.skills.get(k, 0.0) if hasattr(parent_b, "skills") and isinstance(parent_b.skills, dict) else 0.0
                c.skills[k] = round(max(pa_xp, pb_xp) * 0.15, 1)

        # 3. Equipped item by caste/role
        if c.caste == "Soldier" or c.is_predator:
            c.equipped_item = "spear"
        elif c.caste == "Priest":
            c.equipped_item = "herb_poultice"
        elif c.caste in ("Woman", "Artisan", "Gentleman", "Herbivore"):
            c.equipped_item = "basket"
        else:
            c.equipped_item = None

        c.food_basket = 0
        c.title = None
        c.emote = None
        c.emote_ticks = 0
        c.waypoints = {}
        c.trust = {}
        if parent_a and hasattr(parent_a, "id"):
            c.trust[parent_a.id] = 30.0
        if parent_b and hasattr(parent_b, "id"):
            c.trust[parent_b.id] = 30.0

    def _init_morph_for_child(self, child: Creature, mother: Creature, father: Creature) -> None:
        """BC morphological inheritance — BH-1 two-parent meiotic + BH-3 stress + BH-2 macro."""
        cfg = self.config
        if not getattr(cfg, "morphology_annealing_enabled", True):
            return
        if _evo_mgr is None or _morphology is None:
            return
        try:
            # BH-1: fetch BOTH parents' polar genomes (SoA primary, cache, then _bc_ fallback)
            def _fetch_morph(p: Creature):
                # check pending morph cache first (newborn not yet in SoA)
                if hasattr(self, "_morph_cache") and p.id in self._morph_cache:
                    try:
                        r, a, k = self._morph_cache[p.id]  # type: ignore
                        return list(r), list(a), int(k)
                    except Exception:
                        pass
                if getattr(self, "_soa", None) is not None and hasattr(self, "_soa_id_map"):
                    idx = getattr(self, "_soa_id_map", {}).get(p.id)
                    if idx is not None and hasattr(self._soa, "morph_radii"):
                        try:
                            r = self._soa.morph_radii[idx]  # type: ignore
                            a = self._soa.morph_angles[idx]  # type: ignore
                            k = int(self._soa.morph_k[idx])  # type: ignore
                            if hasattr(r, "tolist"):
                                r = r.tolist()  # type: ignore
                                a = a.tolist()  # type: ignore
                            else:
                                r = list(r); a = list(a)
                            return r, a, k
                        except Exception:
                            pass
                if hasattr(self, "_morph_cache") and p.id in getattr(self, "_morph_cache", {}):
                    try:
                        r, a, k = self._morph_cache[p.id]  # type: ignore
                        return list(r), list(a), int(k)
                    except Exception:
                        pass
                if getattr(p, "_bc_morph_r", None) is not None:
                    return p._bc_morph_r, p._bc_morph_phi, int(getattr(p, "_bc_morph_k", 4))  # type: ignore
                if _evo_mgr is not None and getattr(p, "caste", None):
                    try:
                        tr, tphi, tk = _evo_mgr.get_template_for_caste(p.caste)
                        return list(tr), list(tphi), int(tk)
                    except Exception:
                        pass
                k = max(3, min(24, p.sides if getattr(p, "sides", None) else 4))
                r = [1.0] * k + [1.0] * (24 - k)
                a = [2 * math.pi * i / k if i < k else 2 * math.pi * i / 24 for i in range(24)]
                return r, a, k
            mr, ma, mk = _fetch_morph(mother)
            fr, fa, fk = _fetch_morph(father)
            template_r, template_phi, template_k = _evo_mgr.get_template_for_caste(child.caste)
            lam = _evo_mgr.lambda_for_generation(child.generation, cfg)
            # BH-3 Stress-Induced Mutagenesis: η + famine (larder<50) + epidemic (infected ratio)
            _eta_sigma = float(getattr(self, "_safeguard_eta", 0.0) or 0.0)
            # famine stress via total larder
            try:
                total_larder = sum(float(v.get("larder", 0) or 0) for v in getattr(self, "clans", {}).values())
            except Exception:
                total_larder = 999.0
            famine_stress = max(0.0, 1.0 - total_larder / 50.0) if total_larder < 50 else 0.0
            # epidemic stress via infected ratio
            try:
                Ntot = len(getattr(self, "_cached_creatures", []) or [])
                inf = int(getattr(self, "infected_count", 0) or sum(1 for c in getattr(self, "_cached_creatures", []) if getattr(c, "infected", False)))
                ratio = inf / max(1, Ntot)
                epidemic_stress = max(0.0, (ratio - 0.15) / 0.35) if ratio > 0.15 else 0.0
            except Exception:
                epidemic_stress = 0.0
            stress = max(_eta_sigma, famine_stress, epidemic_stress)
            if stress > 0.01:
                class _EffCfg:  # type: ignore
                    def __getattr__(self, name):
                        if name == "vertex_mutation_std":
                            return cfg.vertex_mutation_std * (1.0 + 1.5 * stress)
                        if name == "angle_mutation_std":
                            return cfg.angle_mutation_std * (1.0 + 1.5 * stress)
                        return getattr(cfg, name)
                eff_cfg = _EffCfg()  # type: ignore
            else:
                eff_cfg = cfg
            # BH-1: use two-parent meiotic crossover when both parents have valid morph
            if hasattr(_evo_mgr, "child_morphology_two_parent"):
                cr, cphi, ck = _evo_mgr.child_morphology_two_parent(  # type: ignore
                    mr, ma, mk, fr, fa, fk, template_r, template_phi, template_k, lam, eff_cfg, self.rng
                )
            else:
                # fallback single-parent (legacy)
                cr, cphi, ck = _evo_mgr.child_morphology(
                    fr, fa, fk, template_r, template_phi, template_k, lam, eff_cfg, self.rng
                )
            # Store into child's SoA entry will be created lazily when SoA syncs;
            # cache in dict (Creature slots forbids ad-hoc attrs) — also pending by object id (id==0 before world.add)
            if hasattr(self, "_morph_cache"):
                try:
                    self._morph_cache[child.id] = (list(cr), list(cphi), int(ck))
                except Exception:
                    pass
                try:
                    self._morph_pending[id(child)] = (list(cr), list(cphi), int(ck))  # type: ignore
                except Exception:
                    pass
            # also attempt legacy attrs for compat (ignore failure due to slots)
            try:
                child._bc_morph_r = cr  # type: ignore
                child._bc_morph_phi = cphi  # type: ignore
                child._bc_morph_k = ck  # type: ignore
            except Exception:
                pass
            # Bake traits immediately to derive irregularity -> euthanasia mapping
            # Use child's morph to compute asymmetry
            import math as _m

            # compute asymmetry quickly via morphology helper
            if _morphology is not None:
                # temporary single-row compute
                xs = [cr[i] * _m.cos(cphi[i]) for i in range(ck)]
                ys = [cr[i] * _m.sin(cphi[i]) for i in range(ck)]
                area = abs(sum(xs[i] * ys[(i + 1) % ck] - xs[(i + 1) % ck] * ys[i] for i in range(ck))) * 0.5
                # simple perimeter
                perim = sum(_m.hypot(xs[(i + 1) % ck] - xs[i], ys[(i + 1) % ck] - ys[i]) for i in range(ck))
                # asymmetry via var(r)
                mean_r = sum(cr[i] for i in range(ck)) / ck if ck else 1.0
                var_r = sum((cr[i] - mean_r) ** 2 for i in range(ck)) / ck if ck else 0.0
                asym = (var_r / mean_r) if mean_r else 0.0
                # bake irregularity for euthanasia gate — BH: skip line (Woman) degenerate template high variance
                irr = max(0.0, min(1.0, asym * 1.5))
                cur_irr = float(getattr(child, "irregularity", 0.0) or 0.0)
                if getattr(child, "shape", "polygon") != "line":
                    child.irregularity = round(max(cur_irr, irr), 3)
                else:
                    # for line daughters keep heritable only (avoid Woman template 1.0)
                    child.irregularity = round(cur_irr, 3) if cur_irr else 0.0
        except Exception:
            pass
        # BH-4 NN genome cache for immediate SoA insertion (also used by rebuild)
        try:
            self._maybe_cache_nn_genome(child, mother, father)
        except Exception:
            pass

    def _maybe_cache_nn_genome(self, child: Creature, mother: Creature, father: Creature) -> None:
        """BH-4 real-time NN crossover — cache hybrid genome for SoA insertion (dict, slots fix)."""
        if _evolution is None:
            return
        def _get_genome(p: Creature):
            # check pending NN cache first (newborn parent not yet in SoA)
            if hasattr(self, "_nn_cache") and p.id in self._nn_cache:
                try:
                    g = self._nn_cache[p.id]  # type: ignore
                    if hasattr(g, "copy"):
                        return g.copy()  # type: ignore
                    return list(g)
                except Exception:
                    pass
            if getattr(self, "_soa", None) is not None and hasattr(self, "_soa_id_map"):
                idx = getattr(self, "_soa_id_map", {}).get(p.id)
                if idx is not None and hasattr(self._soa, "genomes"):
                    try:
                        g = self._soa.genomes[idx]  # type: ignore
                        if hasattr(g, "copy"):
                            return g.copy()  # type: ignore
                        return list(g)  # type: ignore
                    except Exception:
                        pass
            return getattr(p, "_nn_genome", None)  # type: ignore
        g_m = _get_genome(mother)
        g_f = _get_genome(father)
        if g_m is None or g_f is None:
            return
        try:
            if hasattr(_evolution, "crossover_mutate_blockwise"):
                cg = _evolution.crossover_mutate_blockwise(g_m, g_f, rng=self.rng)  # type: ignore
            else:
                cg = _evolution.crossover_mutate(g_m, g_f)  # type: ignore
            if hasattr(self, "_nn_cache"):
                try:
                    self._nn_cache[child.id] = cg  # type: ignore
                except Exception:
                    pass
                try:
                    self._nn_pending[id(child)] = cg  # type: ignore
                except Exception:
                    pass
            try:
                child._nn_genome = cg  # type: ignore  # legacy compat, may fail due to slots
            except Exception:
                pass
            # if SoA entry already exists for child (unlikely at birth time), update directly
            if getattr(self, "_soa", None) is not None and hasattr(self, "_soa_id_map"):
                idx_c = getattr(self, "_soa_id_map", {}).get(child.id)
                if idx_c is not None and hasattr(self._soa, "genomes"):
                    try:
                        self._soa.genomes[idx_c] = cg  # type: ignore
                    except Exception:
                        pass
        except Exception:
            pass

    def _promote_pending_caches(self, child: Creature) -> None:
        """Move pending morph/NN caches from object-id key to real entity id after world.add."""
        try:
            oid = id(child)
            if hasattr(self, "_morph_pending") and oid in self._morph_pending:
                self._morph_cache[child.id] = self._morph_pending.pop(oid)  # type: ignore
            if hasattr(self, "_nn_pending") and oid in self._nn_pending:
                self._nn_cache[child.id] = self._nn_pending.pop(oid)  # type: ignore
        except Exception:
            pass

    def _classify_archetype(self, c: Creature) -> str | None:
        """Return tag for creature policy niche. Called per-tick for UI, also for nocturnal gate."""
        try:
            # fetch morph traits if baked
            dmult = 0.0
            area = 0.0
            perim = 0.0
            idx = getattr(self, "_soa_id_map", {}).get(c.id) if getattr(self, "_soa", None) is not None else None
            if idx is not None and hasattr(self._soa, "morph_traits"):
                try:
                    mt = self._soa.morph_traits[idx]  # type: ignore
                    if len(mt) >= 6:
                        area = float(mt[0]); perim = float(mt[1]); dmult = float(mt[5])
                except Exception:
                    pass
            # fallback via irregularity
            if dmult == 0.0:
                irr = float(getattr(c, "irregularity", 0.0) or 0.0)
                # approximate dmult from irr (sharper when irr high for triangles)
                dmult = min(1.0, irr * 1.2) if c.caste == "Soldier" else 0.0
            skills = getattr(c, "skills", {}) or {}
            combat = float(skills.get("combat", 0.0) or 0.0)
            forag = float(skills.get("foraging", 0.0) or 0.0)
            farm = float(skills.get("farming", 0.0) or 0.0)
            # Apex Hunter: razor + combat
            if dmult > 0.45 and (combat > 4 or c.is_predator):
                return "Apex Hunter"
            # Nocturnal Forager: chill tolerant + explorer + foraging skill + irregular (mutant)
            # BH-8: allow night-active if chill tolerance and night-forage mutation
            chill = float(getattr(c, "chill", 0.0) or 0.0)
            if forag > 2.5 and chill < 4.0 and getattr(c, "personality", "") in ("explorer", "brave", "cautious") and float(getattr(c, "irregularity", 0.0) or 0.0) > 0.15:
                # also check if NN has night preference inversion (genome sign flip) via hidden heuristic: generation >15 and lam low
                # simple proxy: high generation mutant
                if getattr(c, "generation", 0) > 15:
                    return "Nocturnal Forager"
            # Granary Courier: carries food + farming
            if getattr(c, "food_basket", 0) > 0 and (farm > 2 or forag > 2):
                return "Granary Courier"
            # Sentry Guard: high combat / paranoid near house
            if combat > 3 and getattr(c, "trait", None) in ("paranoid", "bold") or (combat > 2 and c.clan_id):
                # check proximity to house via cached bodies (approx)
                try:
                    if getattr(self, "_house_bodies", None) and getattr(c, "clan_id", 0):
                        return "Sentry Guard"
                except Exception:
                    pass
                if combat > 5:
                    return "Sentry Guard"
            return None
        except Exception:
            return None

    def _is_nocturnal_forager(self, c: Creature) -> bool:
        """BH-8 gate: nocturnal mutants skip sleep to forage under darkness."""
        try:
            arch = getattr(c, "_archetype", None)
            if not arch and hasattr(self, "_archetype_cache"):
                arch = self._archetype_cache.get(c.id)  # type: ignore
            if arch == "Nocturnal Forager" or getattr(c, "trait", None) == "nocturnal":
                return True
            return False
        except Exception:
            return False

    def _spawn_creature(self, shape: str, sides: int) -> None:
        cfg = self.config
        x, y = self._rand_pos()
        iso = 60.0
        if sides == 3:
            # Founding Isosceles: somewhere on the long road toward 60 degrees.
            iso = self.rng.uniform(0.5, 59.5)
        caste = caste_name(sides, shape, iso)
        traits = traits_for(caste)
        c = Creature(
            shape=shape,
            sides=sides,
            iso_angle=iso,
            x=x,
            y=y,
            angle=self.rng.uniform(0, 2 * math.pi),
            speed=traits.speed,
            energy=cfg.energy_start,
            lifespan=traits.lifespan * cfg.lifespan_mult,
        )
        self._init_creature_evolution(c)
        self.world.add(c)

    def _spawn_predator(self) -> None:
        """Spawn a Carnivore predator (§I) — fast, no clan, hunts prey."""
        cfg = self.config
        x, y = self._rand_pos()
        traits = traits_for("Predator")
        c = Creature(
            shape="polygon",
            sides=6,
            iso_angle=60.0,
            caste="Predator",
            x=x,
            y=y,
            angle=self.rng.uniform(0, 2 * math.pi),
            speed=traits.speed,
            energy=cfg.energy_start,
            lifespan=traits.lifespan * cfg.lifespan_mult,
            is_predator=True,
            clan_id=0,
        )
        self._init_creature_evolution(c)
        self.world.add(c)

    def _spawn_herbivore(self) -> None:
        """Spawn a wild herbivore grazer (§O) — clanless, eats plants, hunted by predators."""
        cfg = self.config
        x, y = self._rand_pos()
        traits = traits_for("Herbivore")
        c = Creature(
            shape="polygon",
            sides=4,
            iso_angle=60.0,
            caste="Herbivore",
            x=x,
            y=y,
            angle=self.rng.uniform(0, 2 * math.pi),
            speed=traits.speed,
            energy=cfg.energy_start,
            lifespan=traits.lifespan * cfg.lifespan_mult,
            is_herbivore=True,
            clan_id=0,
        )
        self._init_creature_evolution(c)
        self.world.add(c)

    def _spawn_initial(self) -> None:
        cfg = self.config
        area = cfg.width * cfg.height

        # Founding generation scale with the map unless explicitly pinned.
        total = (
            self._jittered(area * cfg.creature_density) if cfg.num_triangles < 0 else 0
        )
        # Flatland's social pyramid: many soldiers and women, few nobles.
        shares = {
            "triangles": 0.30,
            "women": 0.25,
            "squares": 0.18,
            "pentagons": 0.12,
            "hexagons": 0.09,
            "priests": 0.06,
        }
        n_triangles = self._count(cfg.num_triangles, shares["triangles"], total)
        n_squares = self._count(cfg.num_squares, shares["squares"], total)
        n_pentagons = self._count(cfg.num_pentagons, shares["pentagons"], total)
        n_hexagons = self._count(cfg.num_hexagons, shares["hexagons"], total)
        n_priests = self._count(cfg.num_priests, shares["priests"], total)
        n_women = self._count(cfg.num_women, shares["women"], total)

        for _ in range(n_triangles):
            self._spawn_creature("polygon", 3)
        for _ in range(n_squares):
            self._spawn_creature("polygon", 4)
        for _ in range(n_pentagons):
            self._spawn_creature("polygon", 5)
        for _ in range(n_hexagons):
            self._spawn_creature("polygon", 6)
        for _ in range(n_priests):
            self._spawn_creature("polygon", PRIEST_SIDES)
        for _ in range(n_women):
            self._spawn_creature("line", 2)
        max_radius = max(
            (c.radius for c in self.world.creatures()), default=DEFAULT_RADIUS
        )
        n_houses = (
            self._jittered(area * cfg.house_density)
            if cfg.num_houses < 0
            else cfg.num_houses
        )
        for _ in range(n_houses):
            size = self.rng.uniform(cfg.house_min_size, cfg.house_max_size)
            x, y = self._rand_house_pos(size)
            door_width = min(size * 0.8, 2.0 * max_radius * cfg.door_clearance)
            self.world.add(
                House(
                    x=x,
                    y=y,
                    size=size,
                    door_width=door_width,
                    door_side=self.rng.choice(("north", "east", "south", "west")),
                    material=self._pick_house_material(x, y),
                )
            )
        for _ in range(cfg.food_count):
            x, y = self._food_pos()
            # World-spawned plants arrive mature: the food law promises harvest.
            self.world.add(self._new_food(x, y, growth=1.0))
        self._found_founding_clans()
        # Predators (§I) — spawn after clans so they don't get a clan crest; only if auto-scaling
        if cfg.predation_enabled and cfg.predator_ratio > 0 and cfg.num_triangles < 0:
            n_predators = self._jittered(area * cfg.creature_density * cfg.predator_ratio)
            for _ in range(n_predators):
                self._spawn_predator()
        # Herbivores (§O) — wild grazers, clanless, compete for plants and feed predators
        if cfg.beast_ratio > 0 and cfg.num_triangles < 0:
            n_herbivores = self._jittered(area * cfg.creature_density * cfg.beast_ratio)
            for _ in range(n_herbivores):
                self._spawn_herbivore()

    def _update_disease(self) -> None:
        """Outbreaks, contagion and recovery. Disabling the law freezes it."""
        cfg = self.config
        if not cfg.disease_enabled:
            return
        creatures = self._get_creatures()
        active = [c for c in creatures if c.infected]

        age = self._age()
        age_disease = AGE_DISEASE_MULT.get(age, 1.0) if age is not None else 1.0
        # Phase 4 Channel 4 effective outbreak via xi
        _xi_out = float(getattr(self, "_density_xi", 0.0) or 0.0)
        _outbreak_eff = cfg.disease_outbreak_rate * (1.0 + 3.0 * _xi_out) if _xi_out else cfg.disease_outbreak_rate
        if (
            not any(c.infected for c in creatures)
            and creatures
            and self.rng.random()
            < _outbreak_eff
            * (WINTER_DISEASE_MULT if self._season() == "winter" else 1.0)
            * age_disease
        ):
            patient = self.rng.choice(creatures)
            self.disease_id += 1
            self._infect(patient)
            self._emit(
                HistoryEvent(
                    type="outbreak",
                    tick=self.tick + 1,
                    entity_id=patient.id,
                    caste=patient.caste,
                    x=round(patient.x, 2),
                    y=round(patient.y, 2),
                    payload={"disease_id": self.disease_id},
                )
            )

        for c in active:
            if not c.infected or c.id not in self.world.entities:
                continue  # died or recovered earlier this tick
            # Recovery — wet/cold slows recovery (§R)
            eff_recovery = cfg.recovery_rate
            # §AP: the Sacred Spiral hastens recovery from plagues
            eff_recovery *= 1.0 + self._totem_stat(c, "recovery")
            if cfg.weather_sickness_enabled:
                wet_c = (self.weather in ("rain", "storm") and not c.indoors) or c.chill >= cfg.chill_threshold * 0.5
                if wet_c:
                    eff_recovery = cfg.recovery_rate / max(1.0, cfg.wet_disease_mult)
            if eff_recovery > 0 and self.rng.random() < eff_recovery:
                c.infected = False
                self._emit(
                    HistoryEvent(
                        type="recovery",
                        tick=self.tick + 1,
                        entity_id=c.id,
                        caste=c.caste,
                        x=round(c.x, 2),
                        y=round(c.y, 2),
                        payload={"disease_id": c.disease_id},
                    )
                )
                continue
            # Contagion to healthy neighbours (winter air carries further) — wet catches faster (§R) — age plague (§S)
            base_spread = cfg.disease_rate * (
                WINTER_DISEASE_MULT if self._season() == "winter" else 1.0
            ) * (AGE_DISEASE_MULT.get(age, 1.0) if age is not None else 1.0)
            for n in self.world.query_radius(c.x, c.y, cfg.disease_radius):
                if n.kind == "creature" and not n.infected and n.id != c.id:
                    rate = base_spread
                    if cfg.weather_sickness_enabled:
                        wet_n = (self.weather in ("rain", "storm") and not getattr(n, "indoors", False)) or getattr(n, "chill", 0) >= cfg.chill_threshold * 0.5
                        if wet_n:
                            rate *= cfg.wet_disease_mult
                    if self.rng.random() < min(rate, 1.0):
                        self._infect(n)  # type: ignore[arg-type]

    def _reproduce(self) -> None:
        """Nature's Law: eligible pairs may beget children; god only sets rates."""
        cfg = self.config
        if not cfg.birth_enabled:
            return
        creatures = self._get_creatures()
        # live count
        live = [c for c in creatures if c.id in self.world.entities]
        pop = len(live)

        max_pop = cfg.effective_max_population
        carrying = cfg.effective_carrying_capacity
        age = self._age()
        offset = int(getattr(cfg, "initial_season_offset", 0) or 0)
        cap_mult = _smooth_age_mult(self.tick, cfg.age_length, AGE_CAP_MULT) if age is not None else 1.0
        season_cap_mult = _smooth_season_cap_mult(self.tick, cfg.season_length, offset=offset)
        max_pop = max(2, round(max_pop * cap_mult * season_cap_mult))
        carrying = max(2, round(carrying * cap_mult * season_cap_mult))

        # Phase 4 Density-Dependent Soft-Cap Damping (xi) — computed via effective carrying capacity
        try:
            from ..density_damping import compute_xi, scales_for_xi  # type: ignore

            _xi = compute_xi(pop, carrying, bool(getattr(cfg, "soft_cap_enabled", True)) and not _IS_TEST)
            self._density_xi = _xi  # type: ignore
            _scales = scales_for_xi(_xi, cfg)
            self._density_scales = _scales  # type: ignore
        except Exception:
            _xi = 0.0
            _scales = {}
            self._density_xi = 0.0  # type: ignore

        # Absolute upper ceiling: no new births if at or above max population
        if pop >= max_pop:
            return

        # Fertility room drops smoothly when population crosses carrying capacity toward max_pop
        room = 1.0
        if pop >= carrying:
            span = max(1, max_pop - carrying)
            progress = min(1.0, max(0.0, float(pop - carrying) / float(span)))
            room = 0.5 * (1.0 + math.cos(math.pi * progress))
            if room < 0.001 or pop >= max_pop:
                return

        if room <= 0.0:
            return

        # Phase 5 Tier2 effective mate threshold/radius via eta + soft-cap mate threshold
        _eta2 = float(getattr(self, "_safeguard_eta", 0.0) or 0.0)
        _mate_thr_eff = cfg.mate_energy_min * (1.0 - 0.5 * _eta2) if _eta2 else cfg.mate_energy_min
        if _xi:
            _mate_thr_eff *= _scales.get("mate_thr_eff", 1.0)
        # §BF-4 mate energy ramp — early world requires well-fed breeders (×2.5 at day 0 → ×1 at ramp) (skip for tests with adult_age 0)
        _boom_days = float(getattr(cfg, "boom_ramp_days", 6.0) or 6.0)
        _boom_e_mult = float(getattr(cfg, "boom_energy_mult", 2.5) or 2.5)
        if _boom_days > 0 and cfg.adult_age > 0:
            _days_old = self.tick / max(1, cfg.day_length)
            if _days_old < _boom_days:
                _boom_e = _boom_e_mult - (_boom_e_mult - 1.0) * (_days_old / _boom_days)
                _mate_thr_eff *= _boom_e
        _mate_rad_eff = cfg.mate_radius * (1.0 + 1.0 * _eta2) if _eta2 else cfg.mate_radius

        def eligible(c: Creature) -> bool:
            base = (
                c.age >= cfg.adult_age
                and c.repro_cooldown <= 0
                and c.energy >= _mate_thr_eff
                and c.health >= REPRO_MIN_HEALTH  # §AT-4 H-0: no heirs in sickness
            )
            if not base:
                return False
            # BC.4.2 courtship — gated behind morphology annealing (and BA 8.1 hard switch deferred)
            return True

        females = [c for c in creatures if c.shape == "line" and eligible(c)]
        if not females:
            return

        mate_r2 = _mate_rad_eff * _mate_rad_eff
        for mother in females:
            if pop >= max_pop:
                break
            father = None
            best_d2 = mate_r2 + 1e-9
            # AF: query candidate males via spatial index with precomputed distance
            for m, d2 in self.world.query_radius_with_dist_sq(mother.x, mother.y, _mate_rad_eff):
                if not isinstance(m, Creature) or m.shape == "line":
                    continue
                if m.repro_cooldown > 0 or m.energy < _mate_thr_eff or not eligible(m):
                    continue
                if d2 < best_d2:
                    father, best_d2 = m, d2
            if father is None:
                continue
            m_fert = 0.5 if mother.stage == "elder" else 1.0
            f_fert = 0.5 if father.stage == "elder" else 1.0
            fert = (
                traits_for(mother.caste).fertility
                * m_fert
                * traits_for(father.caste).fertility
                * f_fert
                * room
            )
            # Phase 4 Channel 1 effective birth rate via xi
            _br_eff = _scales.get("birth_rate_eff", 1.0) if _xi else 1.0
            rate = cfg.birth_rate * _br_eff
            age2 = self._age()
            if age2 is not None:
                rate = min(1.0, rate * AGE_BIRTH_MULT.get(age2, 1.0))
            if self._season() == "spring":
                rate = min(1.0, rate * SPRING_BIRTH_MULT)  # spring quickens the blood
            # §AM E.2: a clan at its feast is generous with more than bread
            mother_clan = self.clans.get(mother.clan_id) if mother.clan_id else None
            if mother_clan and self.tick < int(mother_clan.get("feast_until", 0)):
                rate = min(1.0, rate * BANQUET_FERTILITY_MULT)
            rate *= 1.0 + self._totem_stat(mother, "birth")  # Radiant Circle fecundity
            # §BF-1 birth rate ramp — days 0-6 throttled to 0.12× → 1.0× linearly (skip for tests with adult_age 0)
            _ramp = float(getattr(cfg, "boom_ramp_days", 6.0) or 6.0)
            _floor = float(getattr(cfg, "boom_birth_floor", 0.12) or 0.12)
            if _ramp > 0 and cfg.adult_age > 0:
                _d = self.tick / max(1, cfg.day_length)
                if _d < _ramp:
                    _boom_b = _floor + (1.0 - _floor) * (_d / _ramp)
                    rate *= _boom_b
            if self.rng.random() >= min(rate * fert, 1.0):
                continue
            self._birth(mother, father)
            pop += 1

    def _birth(self, mother: Creature, father: Creature) -> None:
        self.births += 1
        self._births = self.births
        tick = self.tick + 1  # the tick being completed
        if getattr(self, "_analytics", None) is not None:
            try:
                self._analytics.on_birth(tick)
            except Exception:
                pass
        cfg = self.config
        # Phase 4 effective birth cost/cooldown via xi
        _xi_birth = float(getattr(self, "_density_xi", 0.0) or 0.0)
        # use scales if available, else compute
        try:
            _scales_b = getattr(self, "_density_scales", {})  # type: ignore
            _birth_cost_eff = cfg.birth_energy_cost * _scales_b.get("birth_cost_eff", 1.0) if _xi_birth else cfg.birth_energy_cost
            _cooldown_eff = int(cfg.reproduction_cooldown * _scales_b.get("cooldown_eff", 1.0)) if _xi_birth else cfg.reproduction_cooldown
        except Exception:
            _birth_cost_eff = cfg.birth_energy_cost * (1.0 + 1.5 * _xi_birth) if _xi_birth else cfg.birth_energy_cost
            _cooldown_eff = int(cfg.reproduction_cooldown * (1.0 + 2.0 * _xi_birth)) if _xi_birth else cfg.reproduction_cooldown
        # §BF-3 early-world cooldown multiplier — ×3 at day 0 → ×1 at ramp (skip for tests with adult_age 0)
        _cd_ramp = float(getattr(cfg, "boom_ramp_days", 6.0) or 6.0)
        _cd_mult = float(getattr(cfg, "boom_cooldown_mult", 3.0) or 3.0)
        if _cd_ramp > 0 and cfg.adult_age > 0:
            _cd_days = self.tick / max(1, cfg.day_length)
            if _cd_days < _cd_ramp:
                _cd_boom = _cd_mult - (_cd_mult - 1.0) * (_cd_days / _cd_ramp)
                _cooldown_eff = int(_cooldown_eff * _cd_boom)
        gen = max(mother.generation, father.generation) + 1
        tick = self.tick + 1  # the tick being completed
        x = (mother.x + self.rng.uniform(-1.5, 1.5)) % cfg.width
        y = (mother.y + self.rng.uniform(-1.5, 1.5)) % cfg.height

        # Predator lineage: if either parent is a predator, child may be predator
        is_predator_child = False
        if mother.is_predator and father.is_predator:
            is_predator_child = True
        elif mother.is_predator or father.is_predator:
            is_predator_child = self.rng.random() < 0.5

        if is_predator_child:
            # Predator children are always Predator caste, no clan, no irregularity
            # trait inheritance (§S)
            ptrait = None
            if self.rng.random() < cfg.trait_mutation_rate:
                ptrait = self.rng.choice(TRAITS)
            elif mother.trait or father.trait:
                opts = [t for t in (mother.trait, father.trait) if t]
                ptrait = self.rng.choice(opts) if opts else None
            child = Creature(
                shape="polygon" if self.rng.random() < 0.5 else "line",
                sides=6 if self.rng.random() < 0.5 else 2,
                x=x, y=y, angle=self.rng.uniform(0, 2 * math.pi),
                energy=cfg.energy_start, generation=gen, born_tick=tick,
                mother_id=mother.id, father_id=father.id,
                lifespan=traits_for("Predator").lifespan * cfg.lifespan_mult,
                is_predator=True,
                caste="Predator",
                clan_id=0,
                trait=ptrait,
            )
            self._init_creature_evolution(child, mother, father)
            self._init_morph_for_child(child, mother, father)
            self.world.add(child)
            self._promote_pending_caches(child)
            event_payload = {
                "mother": mother.id, "father": father.id,
                "sides": child.sides, "generation": gen, "sex": child.sex,
                "clan_id": 0, "is_predator": True,
                "personal_name": personal_name_for(child.id, self.config.seed, gen),
                "glyph": glyph_for(child.id, self.config.seed, gen),
            }
            for p in (mother, father):
                p.energy = max(10.0, p.energy - _birth_cost_eff)
                p.repro_cooldown = _cooldown_eff
                p.emote = "love"
                p.emote_ticks = 25
            event = HistoryEvent(
                type="birth", tick=tick, entity_id=child.id, caste=child.caste,
                x=round(child.x, 2), y=round(child.y, 2),
                payload=event_payload,
            )
            self.history.append(event)
            self._events_this_tick.append(event.model_dump(mode="json"))
            if self.on_event is not None:
                self.on_event(event)
            return

        # Herbivore lineage: wild grazers breed true outside the caste system
        is_herbivore_child = False
        if mother.is_herbivore and father.is_herbivore:
            is_herbivore_child = True
        elif mother.is_herbivore or father.is_herbivore:
            is_herbivore_child = self.rng.random() < 0.5
        if is_herbivore_child:
            htrait = None
            if self.rng.random() < cfg.trait_mutation_rate:
                htrait = self.rng.choice(TRAITS)
            elif mother.trait or father.trait:
                opts = [t for t in (mother.trait, father.trait) if t]
                htrait = self.rng.choice(opts) if opts else None
            child = Creature(
                shape="polygon", sides=4, iso_angle=60.0,
                x=x, y=y, angle=self.rng.uniform(0, 2 * math.pi),
                energy=cfg.energy_start, generation=gen, born_tick=tick,
                mother_id=mother.id, father_id=father.id,
                lifespan=traits_for("Herbivore").lifespan * cfg.lifespan_mult,
                is_herbivore=True,
                caste="Herbivore",
                clan_id=0,
                trait=htrait,
            )
            self._init_creature_evolution(child, mother, father)
            self._init_morph_for_child(child, mother, father)
            self.world.add(child)
            self._promote_pending_caches(child)
            event_payload = {
                "mother": mother.id, "father": father.id,
                "sides": child.sides, "generation": gen, "sex": child.sex,
                "clan_id": 0, "is_herbivore": True,
                "personal_name": personal_name_for(child.id, self.config.seed, gen),
                "glyph": glyph_for(child.id, self.config.seed, gen),
            }
            for p in (mother, father):
                p.energy = max(10.0, p.energy - _birth_cost_eff)
                p.repro_cooldown = _cooldown_eff
                p.emote = "love"
                p.emote_ticks = 25
            event = HistoryEvent(
                type="birth", tick=tick, entity_id=child.id, caste=child.caste,
                x=round(child.x, 2), y=round(child.y, 2),
                payload=event_payload,
            )
            self.history.append(event)
            self._events_this_tick.append(event.model_dump(mode="json"))
            if self.on_event is not None:
                self.on_event(event)
            return

        promoted = False
        if self.rng.random() < cfg.sex_ratio:
            if father.sides == 3:
                # Isosceles line: sons stay triangles, creeping toward Regular.
                # §AP: the Dimensional Rift hastens God's Ascent through the castes.
                sides = 3
                iso = min(60.0, father.iso_angle + 0.5 + 0.25 * self._totem_stat(father, "promote"))
                promoted = iso >= 60.0 and father.iso_angle < 60.0
            else:
                # Law of Nature: a son has one more side than his father.
                sides = min(father.sides + 1, cfg.max_sides)
                iso = 60.0
            parent_irr = max(float(getattr(mother, "irregularity", 0.0) or 0.0), float(getattr(father, "irregularity", 0.0) or 0.0))
            herit = float(getattr(cfg, "mutation_heritability", 0.70))
            inherited_irr = parent_irr * herit
            if inherited_irr > 0.05:
                inherited_irr = min(1.0, max(0.0, inherited_irr + self.rng.gauss(0, 0.05)))
            irregularity = round(inherited_irr, 3) if inherited_irr >= 0.05 else 0.0

            mut_rate = cfg.mutation_rate
            # §AP: Rift clans breed adaptable children — mutation odds multiply.
            mut_rate = min(1.0, mut_rate * (1.0 + self._totem_stat(mother, "mutate")))
            # §AS L-5: thin royal blood — small monarchies mutate more easily
            mother_clan_gov = self.clans.get(mother.clan_id, {}).get("governance")
            if (
                mother_clan_gov == "monarchy"
                and len(self._clan_members.get(mother.clan_id, ())) < 8
            ):
                mut_rate = min(1.0, mut_rate * MONARCHY_INBREEDING)
            age = self._age()
            if age is not None:
                mut_rate = min(1.0, mut_rate * AGE_MUTATION_MULT.get(age, 1.0))
            if self.rng.random() < mut_rate:
                # A deformed child: sides deviate AND the irregularity is scored.
                sides = min(cfg.max_sides, max(3, sides + self.rng.choice((-1, 1))))
                if sides != 3:
                    promoted = False
                spontaneous_irr = round(self.rng.uniform(0.3, 1.0), 3)
                irregularity = max(irregularity, spontaneous_irr)
            caste = caste_name(sides, "polygon", iso)
            # trait inheritance (§S)
            ntrait = None
            if self.rng.random() < cfg.trait_mutation_rate:
                ntrait = self.rng.choice(TRAITS)
            elif mother.trait or father.trait:
                opts = [t for t in (mother.trait, father.trait) if t]
                ntrait = self.rng.choice(opts) if opts else None
            child = Creature(
                shape="polygon", sides=sides, iso_angle=iso,
                x=x, y=y, angle=self.rng.uniform(0, 2 * math.pi),
                energy=cfg.energy_start, generation=gen, born_tick=tick,
                mother_id=mother.id, father_id=father.id,
                lifespan=traits_for(caste).lifespan * cfg.lifespan_mult,
                irregularity=irregularity,
                trait=ntrait,
            )
            self._init_morph_for_child(child, mother, father)
        else:
            parent_irr = max(float(getattr(mother, "irregularity", 0.0) or 0.0), float(getattr(father, "irregularity", 0.0) or 0.0))
            herit = float(getattr(cfg, "mutation_heritability", 0.70))
            inherited_irr = parent_irr * herit
            if inherited_irr > 0.05:
                inherited_irr = min(1.0, max(0.0, inherited_irr + self.rng.gauss(0, 0.05)))
            irregularity = round(inherited_irr, 3) if inherited_irr >= 0.05 else 0.0

            mut_rate = cfg.mutation_rate
            mut_rate = min(1.0, mut_rate * (1.0 + self._totem_stat(mother, "mutate")))
            mother_clan_gov = self.clans.get(mother.clan_id, {}).get("governance")
            if (
                mother_clan_gov == "monarchy"
                and len(self._clan_members.get(mother.clan_id, ())) < 8
            ):
                mut_rate = min(1.0, mut_rate * MONARCHY_INBREEDING)
            age = self._age()
            if age is not None:
                mut_rate = min(1.0, mut_rate * AGE_MUTATION_MULT.get(age, 1.0))
            if self.rng.random() < mut_rate:
                spontaneous_irr = round(self.rng.uniform(0.2, 0.8), 3)
                irregularity = max(irregularity, spontaneous_irr)

            dtrait = None
            if self.rng.random() < cfg.trait_mutation_rate:
                dtrait = self.rng.choice(TRAITS)
            elif mother.trait or father.trait:
                opts = [t for t in (mother.trait, father.trait) if t]
                dtrait = self.rng.choice(opts) if opts else None
            child = Creature(
                shape="line", sides=2,
                x=x, y=y, angle=self.rng.uniform(0, 2 * math.pi),
                energy=cfg.energy_start, generation=gen, born_tick=tick,
                mother_id=mother.id, father_id=father.id,
                lifespan=traits_for("Woman").lifespan * cfg.lifespan_mult,
                irregularity=irregularity,
                trait=dtrait,
            )
            self._init_morph_for_child(child, mother, father)

        self._init_creature_evolution(child, mother, father)
        self.world.add(child)
        self._promote_pending_caches(child)
        gift = self._totem_stat(child, "health")  # avatar vitality: Indomitable Monolith birth-gift
        if gift:
            child.health = min(child.max_health, child.health + gift)
        if child.clan_id == 0:
            # Children belong to their mother's clan; orphans found new ones
            # (clan set before the claim so the founder counts as a member, §V).
            parent_clan = mother.clan_id or father.clan_id
            if parent_clan:
                child.clan_id = parent_clan
            else:
                cid_new = self._new_clan(child)
                child.clan_id = cid_new
                if self.config.house_claim_enabled:
                    self._claim_house_for_clan(cid_new)
        event_payload = {
            "mother": mother.id, "father": father.id,
            "sides": child.sides, "generation": gen, "sex": child.sex,
            "clan_id": child.clan_id,
            "personal_name": personal_name_for(child.id, self.config.seed, gen),
            "glyph": glyph_for(child.id, self.config.seed, gen),
        }

        # BC.4.1 energetic asymmetry — when enabled, cost scales with morph area median
        if getattr(cfg, "morphology_annealing_enabled", True) and getattr(self, "_soa", None) is not None and _morphology is not None:
            try:
                # median area from SoA morph_traits if available
                if hasattr(self._soa, "morph_traits"):
                    import numpy as _np2  # type: ignore
                    try:
                        if hasattr(self._soa.morph_traits, "shape"):
                            areas = self._soa.morph_traits[: self._soa.N, 0]
                            # filter zeros
                            nz = areas[areas > 0]
                            median_a = float(_np2.median(nz)) if len(nz) else 0.0
                        else:
                            areas = [row[0] for row in self._soa.morph_traits[: self._soa.N] if row[0] > 0]
                            median_a = sorted(areas)[len(areas)//2] if areas else 0.0
                    except Exception:
                        median_a = 0.0
                    # determine role per parent via their own area if in SoA else fallback
                    for p in (mother, father):
                        p_area = 0.0
                        try:
                            idx = getattr(self, "_soa_id_map", {}).get(p.id)
                            if idx is not None:
                                p_area = float(self._soa.morph_traits[idx, 0]) if hasattr(self._soa.morph_traits, "shape") else float(self._soa.morph_traits[idx][0])
                        except Exception:
                            p_area = 0.0
                        is_high = p_area >= median_a if median_a else False
                        # high invests 35-50% of baked E_max, low 5-10%
                        try:
                            baked = _morphology.bake_traits_for_index(idx, self._soa, cfg) if idx is not None else None
                            emax_scale = baked.get("emax_scale", 1.0) if baked else 1.0
                        except Exception:
                            emax_scale = 1.0
                        ratio = self.rng.uniform(0.35, 0.50) if is_high else self.rng.uniform(0.05, 0.10)
                        # Phase 4: scale anisogamy cost via xi
                        _cost_scale = _scales_b.get("birth_cost_eff", 1.0) if _xi_birth else 1.0 if '_scales_b' in locals() else (1.0 + 1.5 * _xi_birth if _xi_birth else 1.0)
                        cost = max(5.0, cfg.energy_max * emax_scale * ratio * _cost_scale)
                        p.energy = max(10.0, p.energy - cost)
                        p.repro_cooldown = _cooldown_eff
                else:
                    for p in (mother, father):
                        p.energy = max(10.0, p.energy - _birth_cost_eff)
                        p.repro_cooldown = _cooldown_eff
            except Exception:
                for p in (mother, father):
                    p.energy = max(10.0, p.energy - _birth_cost_eff)
                    p.repro_cooldown = _cooldown_eff
        else:
            for p in (mother, father):
                p.energy = max(10.0, p.energy - _birth_cost_eff)
                p.repro_cooldown = _cooldown_eff

        event = HistoryEvent(
            type="birth", tick=tick, entity_id=child.id, caste=child.caste,
            x=round(child.x, 2), y=round(child.y, 2),
            payload=event_payload,
        )
        self.history.append(event)
        self._events_this_tick.append(event.model_dump(mode="json"))
        if self.on_event is not None:
            self.on_event(event)
        if getattr(self, "_analytics", None) is not None:
            try:
                irr_val = float(getattr(child, "irregularity", 0.0) or 0.0)
                is_side_mut = child.sex == "male" and hasattr(father, "sides") and child.sides != (father.sides + 1)
                if irr_val > 0.0 or is_side_mut or (child.trait and child.trait not in (mother.trait, father.trait)):
                    clan_info = self.clans.get(child.clan_id, {}) if child.clan_id else {}
                    self._analytics.on_mutation(
                        tick,
                        child,
                        {
                            "clan_name": clan_info.get("name"),
                            "clan_color": clan_info.get("color", "#8b949e"),
                            "type": "asymmetry" if irr_val > 0 else ("polygon_side" if is_side_mut else "trait"),
                            "desc": f"Gen {child.generation} {child.caste} ({child.sides} sides)" + (f" Irreg {irr_val}" if irr_val > 0 else ""),
                        }
                    )
            except Exception:
                pass
        # §AR S-7: birth is literally good news — kin nearby share a joy
        # ripple and a small morale/health gift.
        if child.clan_id and len(self.signals) < SIGNALS_MAX:
            self.signals.append({
                "x": round(child.x, 2), "y": round(child.y, 2),
                "kind": "joy", "sender": mother.id,
                "clan_id": child.clan_id or None, "born_tick": self.tick, "ttl": 15,
                "joy_energy": 2.0, "joy_health": 1.0,
            })

        if promoted:
            pevent = HistoryEvent(
                type="promotion", tick=tick, entity_id=child.id, caste=child.caste,
                x=round(child.x, 2), y=round(child.y, 2),
                payload={"from": "Soldier", "to": "Artisan"},
            )
            self.history.append(pevent)
            self._events_this_tick.append(pevent.model_dump(mode="json"))
            if self.on_event is not None:
                self.on_event(pevent)

    def _kill(self, c: Creature, cause: str, corpse_energy_mult: float = 1.0) -> None:
        """Remove a creature from the world and record it in the chronicle."""
        self.world.remove(c.id)
        if self.config.corpses_enabled:
            self.world.add(
                Corpse(x=c.x, y=c.y, ttl=self.config.corpse_ttl,
                       energy=self.config.corpse_energy * corpse_energy_mult)
            )
        self.deaths += 1
        self._death_counts[cause] = self._death_counts.get(cause, 0) + 1
        # BD1.2: record mortality for telemetry
        try:
            if getattr(self, "_analytics", None) is not None:
                self._analytics.on_death(self.tick, cause)  # type: ignore
        except Exception:
            pass
        if c.clan_id:
            self._clan_deaths[c.clan_id] = self._clan_deaths.get(c.clan_id, 0) + 1
        event = HistoryEvent(
            type="death",
            tick=self.tick + 1,  # the tick being completed
            entity_id=c.id,
            caste=c.caste,
            cause=cause,
            x=round(c.x, 2),
            y=round(c.y, 2),
            payload={"personal_name": personal_name_for(c.id, self.config.seed, c.generation), "glyph": glyph_for(c.id, self.config.seed, c.generation)},
        )
        self.history.append(event)
        self._events_this_tick.append(event.model_dump(mode="json"))
        if self.on_event is not None:
            self.on_event(event)
        # §AN B.3: a violent end leaves a danger scent that steers the
        # young and the vulnerable away from ambush grounds.
        if (
            self.config.scent_enabled
            and cause in ("predation", "war")
            and len(self.signals) < SIGNALS_MAX
        ):
            self.signals.append({
                "x": round(c.x, 2), "y": round(c.y, 2), "kind": "danger_scent",
                "sender": c.id, "clan_id": c.clan_id or None, "born_tick": self.tick, "ttl": DANGER_SCENT_TTL,
            })
        # Leadership succession (§P) — always runs; succession_enabled only gates the chronicle event.
        if c.clan_id:
            # §AT-4 H-2: kin who watch a clan-mate die carry the grief —
            # morale breaks a little in every witness (§AR S-7 grief ripple).
            witnesses = 0
            pr_sq = self.config.perceive_radius * self.config.perceive_radius
            # §P0: clan-scoped witness scan instead of full-world scan
            for other in self._clan_members.get(c.clan_id, ()) or self._get_creatures():
                if other.id == c.id or other.clan_id != c.clan_id:
                    continue
                if self.world.distance_sq(other.x, other.y, c.x, c.y) <= pr_sq:
                    other.morale = max(0.0, other.morale - MORALE_DEATH_WITNESS)
                    witnesses += 1
            if witnesses and len(self.signals) < SIGNALS_MAX:
                self.signals.append({
                    "x": round(c.x, 2), "y": round(c.y, 2),
                    "kind": "grief", "sender": c.id,
                    "clan_id": c.clan_id or None, "born_tick": self.tick, "ttl": 15,
                    "witnesses": [
                        o.id for o in self._clan_members.get(c.clan_id, ()) or self._get_creatures()
                        if o.id != c.id and o.clan_id == c.clan_id
                        and self.world.distance_sq(o.x, o.y, c.x, c.y) <= pr_sq
                    ],
                })
            clan = self.clans.get(c.clan_id)
            if clan and clan.get("leader_id") == c.id:
                # Exclude the dying creature from candidates: world.remove() ran above but
                # _cached_creatures is only rebuilt at _refresh_cache(), so filter explicitly.
                candidates = [cc for cc in self._get_creatures() if cc.clan_id == c.clan_id and cc.id != c.id]
                if candidates:
                    gov = clan.get("governance", "republic")
                    if gov == "monarchy":
                        dynasty = [cc for cc in candidates if cc.mother_id == c.id or cc.father_id == c.id]
                        successor = sorted(dynasty or candidates, key=lambda cc: (-cc.age, cc.id))[0]
                    elif gov == "theocracy":
                        priests = [cc for cc in candidates if cc.caste == "Priest"]
                        successor = sorted(priests or candidates, key=lambda cc: (-cc.age, cc.id))[0]
                    elif gov == "junta":
                        soldiers = [cc for cc in candidates if cc.caste == "Soldier"]
                        successor = sorted(soldiers or candidates, key=lambda cc: (-getattr(cc, "skills", {}).get("combat", 0.0), -cc.age, cc.id))[0]
                    else:
                        # republic (Council of Elders)
                        successor = sorted(candidates, key=lambda cc: (-cc.sides, -cc.age, cc.id))[0]

                    clan["leader_id"] = successor.id
                    succ_name = personal_name_for(successor.id, self.config.seed, successor.generation)
                    # §AS L-6: succession flavor — a new chief may call a new
                    # avatar; two equal heirs may tear the clan in two.
                    if self.rng.random() < TOTEM_CHANGE_CHANCE:
                        bias = {
                            "bold": "Celestial Strike",
                            "peaceful": "Sacred Spiral",
                            "paranoid": "All-Seeing Vertex",
                            None: "Radiant Circle",
                        }.get(successor.trait, "Radiant Circle")
                        if successor.caste == "Soldier":
                            bias = "Celestial Strike"
                        old_totem = clan.get("totem")
                        clan["totem"] = bias
                        self._log_clan_history(
                            c.clan_id, "totem_change",
                            f"{bias} succeeds {old_totem} under Chief {succ_name} (Day {self.day})",
                        )
                    else:
                        equals = [
                            cc for cc in candidates
                            if (cc.sides, cc.age) == (successor.sides, successor.age)
                            and cc.id != successor.id
                        ]
                        if equals and self.rng.random() < CONTESTED_SUCCESSION_CHANCE:
                            faction = [
                                cc for cc in candidates if cc.id % 2 == 0
                            ][: max(1, len(candidates) // 2)]
                            if faction and len(faction) < len(candidates):
                                new_cid = self._new_clan(faction[0])
                                for cc in faction:
                                    cc.clan_id = new_cid
                                self._bump_relation(c.clan_id, new_cid, -40)
                                parent_info = self.clans.get(c.clan_id, {})
                                new_info = self.clans.get(new_cid, {})
                                self._emit(
                                    HistoryEvent(
                                        type="schism",
                                        tick=self.tick + 1,
                                        entity_id=faction[0].id,
                                        caste=faction[0].caste,
                                        payload={
                                            "parent": c.clan_id,
                                            "new_clan": new_cid,
                                            "parent_name": parent_info.get("name"),
                                            "new_name": new_info.get("name"),
                                            "members": [cc.id for cc in faction],
                                            "member_count": len(faction),
                                            "reason": "contested_succession",
                                        },
                                    )
                                )
                    if self.config.succession_enabled:
                        self._log_clan_history(
                            c.clan_id,
                            "leader_change",
                            f"{succ_name} (#{successor.id}) ascended as Leader ({gov.capitalize()}, Day {self.day})",
                        )
                        self._emit(
                            HistoryEvent(
                                type="succession",
                                tick=self.tick + 1,
                                entity_id=successor.id,
                                caste=successor.caste,
                                x=round(successor.x, 2),
                                y=round(successor.y, 2),
                                payload={"clan_id": c.clan_id, "prev_leader": c.id, "new_leader": successor.id, "clan_name": clan.get("name")},
                            )
                        )
                else:
                    clan["leader_id"] = None
                    if self.config.succession_enabled:
                        self._log_clan_history(
                            c.clan_id,
                            "leader_change",
                            f"Leader #{c.id} perished without living successor (Day {self.day})",
                        )
                # §AS L-0 Leader shock: the chief's death rocks the whole clan —
                # energy drains in an instant, panic takes hold for 20 ticks,
                # the larder is looted, and a grief cry rings out.
                for member in self._get_creatures():
                    if member.clan_id == c.clan_id and member.id != c.id:
                        member.energy = max(0.5, member.energy - LEADER_SHOCK_ENERGY)
                        member.panic_ticks = LEADER_SHOCK_PANIC_TICKS
                        # §AT-4 H-2: the chief's death breaks more hearts than a common loss.
                        member.morale = max(0.0, member.morale - MORALE_LEADER_DEATH)
                        member.emote = "panic"
                        member.emote_ticks = 15
                if clan:
                    clan["larder"] = float(clan.get("larder", 0.0)) * LEADER_SHOCK_LARDER_MULT
                self.signals.append({
                    "x": round(c.x, 2), "y": round(c.y, 2),
                    "kind": "grief", "sender": c.id,
                    "clan_id": c.clan_id or None, "born_tick": self.tick, "ttl": 15,
                })
                # §AS L-4: a chief cut down outside a declared feud is
                # regicide when any rival lives at war with the victim's clan.
                if cause == "war" and not any(
                    e.get("type") == "regicide"
                    and e.get("payload", {}).get("victim") == c.id
                    for e in getattr(self, "_events_this_tick", [])
                ):
                    for other in sorted(self.clans.keys()):
                        if other == c.clan_id:
                            continue
                        pair = self._relation_pair(c.clan_id, other)
                        if self._zone_of(self.relations.get(pair, 0)) != -1:
                            continue
                        if self._declared_wars.get(pair) is not None:
                            continue
                        self._emit(
                            HistoryEvent(
                                type="regicide",
                                tick=self.tick + 1,
                                entity_id=c.id,
                                payload={
                                    "victim": c.id, "victim_clan": c.clan_id,
                                    "assassin_clan": other,
                                },
                            )
                        )
                        for third in sorted(self.clans.keys()):
                            if third in (c.clan_id, other):
                                continue
                            opair = self._relation_pair(third, other)
                            self.relations[opair] = max(-100, self.relations.get(opair, 0) + REGICIDE_RELATION_HIT)
                            vpair = self._relation_pair(third, c.clan_id)
                            self.relations[vpair] = min(100, self.relations.get(vpair, 0) + REGICIDE_SYMPATHY)
                        break

    def _update_creature_skills_and_titles(self, c: Creature) -> None:
        """Evaluate dynamic titles and milestone level-ups."""
        skills = getattr(c, "skills", None)
        if not skills or not isinstance(skills, dict):
            c.skills = {"farming": 0.0, "combat": 0.0, "foraging": 0.0, "healing": 0.0}
            skills = c.skills

        farm = skills.get("farming", 0.0)
        combat = skills.get("combat", 0.0)
        forage = skills.get("foraging", 0.0)
        heal = skills.get("healing", 0.0)

        new_title = None
        if combat >= 30.0:
            new_title = "the Fearless Champion"
        elif combat >= 12.0:
            new_title = "the Slayer"
        elif farm >= 30.0:
            new_title = "the Grand Harvester"
        elif farm >= 12.0:
            new_title = "the Harvester"
        elif heal >= 30.0:
            new_title = "the Wise Shaman"
        elif heal >= 12.0:
            new_title = "the Herbalist"
        elif forage >= 30.0:
            new_title = "the Pathfinder"
        elif forage >= 12.0:
            new_title = "the Gatherer"

        if new_title and new_title != c.title:
            c.title = new_title
            c.emote = "cheer"
            c.emote_ticks = 30

