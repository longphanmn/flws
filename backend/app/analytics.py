"""BD World Analytics & Telemetry Engine — high-performance macro intelligence."""
from __future__ import annotations
import logging
import math, time
from collections import Counter, deque
from typing import Any
PLANT_SPECIES = ["grass", "grain", "berry", "medicinal_herb", "mushroom", "poisonous"]
PERSONALITIES = ["brave", "cautious", "altruistic", "greedy", "explorer", "builder"]
CASTES = ["Soldier", "Artisan", "Gentleman", "Professional", "Noble", "Priest", "Woman", "Predator", "Herbivore"]
MORTALITY_CAUSES = ["starvation", "combat", "predation", "disease", "old_age", "chill", "exposure", "fall", "hyperthermia", "other"]
CAUSE_BUCKET = {
    "starvation": "starvation",
    "exhaustion": "starvation",
    "old_age": "old_age",
    "euthanasia": "old_age",
    "disease": "disease",
    "predation": "predation",
    "war": "combat",
    "combat": "combat",
    "chill": "chill",
    "exposure": "chill",
    "fall": "chill",
    "landslide": "chill",
    "hyperthermia": "chill",
    "impalement": "combat",
    "cannibalism": "combat",
}
def bucket_cause(cause: str) -> str:
    return CAUSE_BUCKET.get(cause, "other")
class TelemetryRing:
    def __init__(self, maxlen: int = 6000, window_ticks: int = 600):
        self.maxlen = maxlen
        self.window_ticks = window_ticks
        self.ticks: deque[int] = deque(maxlen=maxlen)
        self.population: deque[int] = deque(maxlen=maxlen)
        self.biomass: deque[float] = deque(maxlen=maxlen)
        self.energy_saturation: deque[float] = deque(maxlen=maxlen)
        self.avg_lifespan: deque[float] = deque(maxlen=maxlen)
        self.dead: deque[int] = deque(maxlen=maxlen)
        self.birth_velocity: deque[float] = deque(maxlen=maxlen)
        self.death_velocity: deque[float] = deque(maxlen=maxlen)
        self.mutation_freq: deque[float] = deque(maxlen=maxlen)
        self.avg_irregularity: deque[float] = deque(maxlen=maxlen)
        self.max_generation: deque[int] = deque(maxlen=maxlen)
        self.morph_lambda: deque[float] = deque(maxlen=maxlen)
        self._prev_births = 0
        self._prev_deaths = 0
        self._prev_tick = 0
        self._start_tick = 0
        self._birth_ticks: deque[int] = deque()
        self._death_ticks: deque[int] = deque()

    def push(self, tick: int, sim: Any) -> None:
        # BJ-3: cache-first — the tick cache is authoritative on the hot path;
        # fall back to a world scan only when the cache is empty/stale (e.g.
        # direct world.add without a refresh, as in unit tests).
        creatures = getattr(sim, "_cached_creatures", None) or list(sim.world.creatures()) if hasattr(sim, "world") else []
        n = len(creatures)
        biomass = 0.0
        energy_sum = 0.0
        lifespan_sum = 0.0
        mut_count = 0
        irr_sum = 0.0
        max_g = 0
        for c in creatures:
            biomass += getattr(c, "health", 0) + getattr(c, "energy", 0)
            energy_sum += getattr(c, "energy", 0) / max(1, getattr(sim.config, "energy_max", 100) or 100)
            lifespan_sum += getattr(c, "lifespan", 0)
            irr = float(getattr(c, "irregularity", 0.0) or 0.0)
            has_trait = bool(getattr(c, "trait", None))
            if irr > 0.0 or has_trait:
                mut_count += 1
            if irr > 0.0:
                irr_sum += irr
            gen = getattr(c, "generation", 0)
            if gen > max_g:
                max_g = gen
        avg_life = lifespan_sum / max(1, n)
        sat = energy_sum / max(1, n)
        mut_freq = mut_count / max(1, n)
        avg_irr = irr_sum / max(1, n)
        lam = 1.0
        if hasattr(sim, "config"):
            try:
                from .evolution_manager import lambda_for_generation
                lam = lambda_for_generation(max_g, sim.config)
            except Exception:
                lam = 1.0

        curr_births = int(getattr(sim, "births", getattr(sim, "_births", 0)) or 0)
        dead = int(getattr(sim, "deaths", 0) or 0)

        # Handle backward tick, world reset, or initial entry
        if not self.ticks or tick < self._prev_tick or curr_births < self._prev_births or dead < self._prev_deaths:
            self._prev_births = curr_births
            self._prev_deaths = dead
            self._prev_tick = tick
            self._start_tick = tick
            self._birth_ticks.clear()
            self._death_ticks.clear()
            delta_b = 0
            delta_d = 0
        else:
            delta_b = curr_births - self._prev_births
            delta_d = dead - self._prev_deaths
            # Fallback estimation if sim object doesn't track births
            if delta_b == 0 and not hasattr(sim, "births") and not hasattr(sim, "_births"):
                prev_pop = self.population[-1] if self.population else n
                delta_b = max(0, n - prev_pop + delta_d)

        for _ in range(delta_b):
            self._birth_ticks.append(tick)
        for _ in range(delta_d):
            self._death_ticks.append(tick)

        cutoff = tick - self.window_ticks
        while self._birth_ticks and self._birth_ticks[0] < cutoff:
            self._birth_ticks.popleft()
        while self._death_ticks and self._death_ticks[0] < cutoff:
            self._death_ticks.popleft()

        win_dt = max(1, min(self.window_ticks, max(1, tick - self._start_tick)))
        bv = (len(self._birth_ticks) / win_dt) * 600.0
        dv = (len(self._death_ticks) / win_dt) * 600.0

        self.ticks.append(tick)
        self.population.append(n)
        self.biomass.append(round(biomass, 1))
        self.energy_saturation.append(round(sat, 3))
        self.avg_lifespan.append(round(avg_life, 1))
        self.dead.append(dead)
        self.birth_velocity.append(round(bv, 2))
        self.death_velocity.append(round(dv, 2))
        self.mutation_freq.append(round(mut_freq, 3))
        self.avg_irregularity.append(round(avg_irr, 4))
        self.max_generation.append(max_g)
        self.morph_lambda.append(round(lam, 3))
        self._prev_births = curr_births
        self._prev_deaths = dead
        self._prev_tick = tick

    def sparkline(self, key: str, n: int = 60) -> list[float]:
        d = getattr(self, key, None)
        if d is None:
            return []
        lst = list(d)[-n:]
        return lst

    def snapshot(self) -> dict:
        return {
            "ticks": list(self.ticks),
            "population": list(self.population),
            "biomass": list(self.biomass),
            "energy_saturation": list(self.energy_saturation),
            "avg_lifespan": list(self.avg_lifespan),
            "dead": list(self.dead),
            "birth_velocity": list(self.birth_velocity),
            "death_velocity": list(self.death_velocity),
            "mutation_freq": list(self.mutation_freq),
            "avg_irregularity": list(self.avg_irregularity),
            "max_generation": list(self.max_generation),
            "morph_lambda": list(self.morph_lambda),
        }
class MortalityDecomposer:
    def __init__(self):
        self.counts: Counter[str] = Counter()
        self.window: deque[tuple[int, str]] = deque(maxlen=500)
        self.history: deque[dict] = deque(maxlen=300)
    def record(self, tick: int, cause: str) -> None:
        bucket = bucket_cause(cause)
        self.window.append((tick, bucket))
        self.counts[bucket] += 1
        if tick % 10 == 0:
            self.history.append({"tick": tick, **self.distribution()})
    def distribution(self, last_n: int = 500) -> dict[str, float]:
        if not self.window:
            return {k: 0.0 for k in ["starvation", "combat", "predation", "disease", "old_age", "chill", "other"]}
        recent = list(self.window)[-last_n:]
        cnt = Counter(b for _, b in recent)
        total = max(1, len(recent))
        return {k: round(cnt.get(k, 0) / total, 3) for k in ["starvation", "combat", "predation", "disease", "old_age", "chill", "other"]}
    def stacked(self) -> dict:
        return {"distribution": self.distribution(), "counts": dict(self.counts), "window": len(self.window)}
class AnalyticsEngine:
    def __init__(self, maxlen: int = 6000):
        self.ring = TelemetryRing(maxlen=maxlen)
        self.mortality = MortalityDecomposer()
        self.recent_mutations: deque[dict] = deque(maxlen=30)
        self._last_summary: dict | None = None
        self._last_summary_tick: int = -1
        self._last_summary_time: float = 0.0
        self._cached: dict[str, tuple[float, Any]] = {}
    def on_tick(self, sim: Any) -> None:
        try:
            self.ring.push(sim.tick, sim)
            self._last_summary = None
            self._cached.clear()
        except Exception:
            pass
    def on_death(self, tick: int, cause: str) -> None:
        try:
            self.mortality.record(tick, cause)
        except Exception:
            pass
    def on_birth(self, tick: int) -> None:
        pass
    def on_mutation(self, tick: int, creature: Any, details: dict | None = None) -> None:
        try:
            info = details or {}
            self.recent_mutations.append({
                "tick": tick,
                "creature_id": getattr(creature, "id", 0),
                "generation": getattr(creature, "generation", 0),
                "caste": getattr(creature, "caste", "Soldier"),
                "sides": getattr(creature, "sides", 3),
                "irregularity": round(float(getattr(creature, "irregularity", 0.0) or 0.0), 3),
                "clan_id": getattr(creature, "clan_id", None),
                "clan_name": info.get("clan_name"),
                "clan_color": info.get("clan_color", "#8b949e"),
                "type": info.get("type", "morphology"),
                "desc": info.get("desc", "Mutation born"),
            })
            self._last_summary = None
            self._cached.clear()
        except Exception:
            pass
    def generational_tracker(self, sim: Any) -> dict:
        creatures = getattr(sim, "_cached_creatures", None) or list(sim.world.creatures()) if hasattr(sim, "world") else []
        if not creatures:
            return {"mobility": 0, "mutation_freq": 0, "asymmetry_dist": [], "abbott_ladder": {}, "top_mutants": [], "lambda_val": 1.0, "recent_mutations": []}
        gens = Counter(c.generation for c in creatures)
        max_gen = max(gens) if gens else 0
        mobility = round(sum(1 for c in creatures if c.generation == max_gen) / max(1, len(creatures)), 3)
        mutated = sum(1 for c in creatures if (float(getattr(c, "irregularity", 0.0) or 0.0) > 0.0 or bool(getattr(c, "trait", None))))
        mutation_freq = round(mutated / max(1, len(creatures)), 3)
        asym_dist = [round(float(getattr(c, "irregularity", 0.0) or 0.0), 3) for c in creatures if float(getattr(c, "irregularity", 0.0) or 0.0) > 0.0]
        abbott: dict[int, int] = {}
        for c in creatures:
            if getattr(c, "shape", "") == "line" or getattr(c, "sides", 3) == 2:
                k = 2
            else:
                k = getattr(c, "sides", 3)
            abbott[k] = abbott.get(k, 0) + 1
        top_mutants = []
        for c in sorted(creatures, key=lambda x: getattr(x, "irregularity", 0.0) or 0.0, reverse=True):
            irr = float(getattr(c, "irregularity", 0.0) or 0.0)
            if irr <= 0.0:
                break
            clan_info = sim.clans.get(c.clan_id, {}) if (hasattr(sim, "clans") and c.clan_id) else {}
            top_mutants.append({
                "id": c.id,
                "name": getattr(c, "personal_name", None) or f"Creature #{c.id}",
                "glyph": getattr(c, "glyph", None),
                "shape": getattr(c, "shape", "polygon"),
                "caste": c.caste,
                "sides": c.sides,
                "irregularity": round(irr, 3),
                "generation": c.generation,
                "clan_id": c.clan_id,
                "clan_name": clan_info.get("name"),
                "clan_color": clan_info.get("color", "#8b949e"),
                "stage": getattr(c, "stage", "adult"),
                "trait": getattr(c, "trait", None),
                "scale_jitter": round(float(getattr(c, "scale_jitter", 1.0)), 2),
                "angle_jitter": round(float(getattr(c, "angle_jitter", 0.0)), 3),
            })
            if len(top_mutants) >= 6:
                break
        lam = 1.0
        if hasattr(sim, "config"):
            try:
                from .evolution_manager import lambda_for_generation
                lam = lambda_for_generation(max_gen, sim.config)
            except Exception:
                lam = 1.0
        # §BG: morphospace scatter — sample up to 80 points with A vs theta_min
        morph_scatter: list[dict] = []
        phylogeny_nodes: list[dict] = []
        try:
            soa = getattr(sim, "_soa", None)
            # Build id->idx map for fast lookup
            id_to_idx: dict[int, int] = {}
            if soa is not None and hasattr(soa, "ids"):
                try:
                    import numpy as _np  # type: ignore
                    if hasattr(soa.ids, "shape"):
                        arr = soa.ids[: soa.N]  # type: ignore
                        for _ii in range(int(soa.N)):
                            id_to_idx[int(arr[_ii])] = _ii
                    else:
                        for _ii in range(int(getattr(soa, "N", 0))):
                            id_to_idx[int(soa.ids[_ii])] = _ii  # type: ignore
                except Exception:
                    pass
            # Scatter: BJ-3 limit to 20 sampled creatures for 1 Hz broadcast perf
            import random as _rnd
            sampled = creatures[:]
            if len(sampled) > 20:
                _rnd.shuffle(sampled)
                sampled = sampled[:20]
            for c in sampled:
                idx_sc = id_to_idx.get(int(c.id), -1)
                area = None
                theta = None
                sc_asym = float(getattr(c, "irregularity", 0.0) or 0.0)
                if idx_sc >= 0 and soa is not None and hasattr(soa, "morph_traits"):
                    try:
                        mt = soa.morph_traits[idx_sc]  # type: ignore
                        area = float(mt[0]) if len(mt) > 0 else None  # type: ignore
                        theta = float(mt[3]) if len(mt) > 3 else None  # type: ignore
                        if area is not None and area < 1e-6:
                            area = None
                            theta = None
                    except Exception:
                        area = None
                        theta = None
                if area is None:
                    # approximate area from scale_jitter & sides: regular polygon area proxy
                    r = float(getattr(c, "radius", 1.2) or 1.2) * float(getattr(c, "scale_jitter", 1.0) or 1.0)
                    k = int(getattr(c, "sides", 4) or 4)
                    if k >= 3:
                        area = 0.5 * k * r * r * math.sin(2 * math.pi / k)
                    else:
                        area = r * r
                    # approximate theta: 60° for regular, scaled by irregularity & iso_angle
                    if k == 3 and getattr(c, "iso_angle", 60.0) < 60.0:
                        theta = math.radians(float(getattr(c, "iso_angle", 60.0)))
                    else:
                        # sharper when irregular high
                        base_theta = 2 * math.pi / max(3, k)  # interior approx? use pi - 2pi/k
                        # interior angle of regular K-gon
                        base_theta = (k - 2) * math.pi / k
                        theta = max(0.15, base_theta - sc_asym * 0.8)
                morph_scatter.append({
                    "id": c.id,
                    "caste": c.caste,
                    "sides": getattr(c, "sides", 4),
                    "generation": getattr(c, "generation", 0),
                    "irregularity": round(sc_asym, 3),
                    "area": round(float(area or 0.0), 3),
                    "theta_min": round(float(theta or 0.0), 3),
                    "clan_id": getattr(c, "clan_id", None),
                    "clan_color": (sim.clans.get(c.clan_id, {}).get("color") if hasattr(sim, "clans") and getattr(c, "clan_id", None) else "#8b949e"),
                    "is_elder": getattr(c, "stage", "adult") == "elder",
                })
            # Phylogeny: build nodes keyed by generation + sides buckets for lineage overview
            # group by generation quartile
            max_g_for_phy = max(1, max_gen)
            for c in creatures:
                if float(getattr(c, "irregularity", 0.0) or 0.0) <= 0.0 and getattr(c, "generation", 0) < max_g_for_phy * 0.5:
                    continue  # skip low-variance early normals unless high gen
                # keep limited set: top irregular + elders
                if len(phylogeny_nodes) >= 20:
                    break
                phylogeny_nodes.append({
                    "id": c.id,
                    "generation": getattr(c, "generation", 0),
                    "caste": c.caste,
                    "sides": getattr(c, "sides", 4),
                    "irregularity": round(float(getattr(c, "irregularity", 0.0) or 0.0), 3),
                    "stage": getattr(c, "stage", "adult"),
                    "clan_id": getattr(c, "clan_id", None),
                    "mother_id": getattr(c, "mother_id", 0),
                    "father_id": getattr(c, "father_id", 0),
                })
        except Exception:
            morph_scatter = []
            phylogeny_nodes = []
        return {
            "mobility": mobility,
            "mutation_freq": mutation_freq,
            "asymmetry_dist": asym_dist[:20],
            "abbott_ladder": abbott,
            "generations": dict(gens),
            "max_generation": max_gen,
            "lambda_val": round(lam, 3),
            "top_mutants": top_mutants,
            "recent_mutations": list(self.recent_mutations),
            "morph_scatter": morph_scatter,
            "phylogeny_nodes": phylogeny_nodes,
        }
    def lotka_volterra(self, sim: Any) -> dict:
        creatures = getattr(sim, "_cached_creatures", None) or list(sim.world.creatures()) if hasattr(sim, "world") else []
        herb = sum(1 for c in creatures if getattr(c, "is_herbivore", False))
        pred = sum(1 for c in creatures if getattr(c, "is_predator", False))
        foods = getattr(sim, "_cached_foods", None) or [e for e in sim.world.entities.values() if e.kind == "food"] if hasattr(sim, "world") else []
        plant = len(foods)
        return {"herbivores": herb, "predators": pred, "plant_biomass": plant, "phase": [pred, herb, plant]}
    def biodiversity(self, sim: Any) -> dict:
        foods = getattr(sim, "_cached_foods", None) or [e for e in sim.world.entities.values() if e.kind == "food"] if hasattr(sim, "world") else []
        if not foods:
            return {"shannon": 0.0, "evenness": 0.0, "richness": 0, "corpse_recycle": 0}
        cnt = Counter(getattr(f, "variant", "grass") for f in foods)
        total = max(1, len(foods))
        H = -sum((v / total) * math.log(v / total) for v in cnt.values() if v > 0)
        max_H = math.log(len(PLANT_SPECIES)) if len(PLANT_SPECIES) > 1 else 1
        evenness = round(H / max_H, 3) if max_H else 0
        richness = len([k for k in cnt if cnt[k] > 0])
        corpses = len(getattr(sim, "_cached_corpses", []) or [e for e in sim.world.entities.values() if e.kind == "corpse"] if hasattr(sim, "world") else [])
        recycle = round(corpses / max(1, total), 3)
        return {"shannon": round(H, 3), "evenness": evenness, "richness": richness, "corpse_recycle": recycle, "by_species": dict(cnt)}
    def heritability(self, sim: Any) -> dict:
        creatures = getattr(sim, "_cached_creatures", None) or list(sim.world.creatures()) if hasattr(sim, "world") else []
        if not creatures:
            return {"personality_fidelity": {}, "drift": {}}
        by_personality = Counter(getattr(c, "personality", "unknown") for c in creatures)
        drift = {}
        for p in PERSONALITIES:
            drift[p] = Counter(c.caste for c in creatures if getattr(c, "personality", None) == p)
        return {"personality_fidelity": dict(by_personality), "drift": {k: dict(v) for k, v in drift.items()}}
    def hegemony(self, sim: Any) -> dict:
        clans = getattr(sim, "clans", {}) or {}
        members = getattr(sim, "_clan_members", {}) or {}
        if not members and hasattr(sim, "world"):
            members = {}
            for c in getattr(sim, "_cached_creatures", []) or sim.world.creatures():
                if c.clan_id:
                    members.setdefault(c.clan_id, []).append(c)
        total = max(1, sum(len(v) for v in members.values()))
        hhi = sum((len(v) / total) ** 2 for v in members.values()) if total else 0
        clan_houses = getattr(sim, "_houses_by_clan", {}) or {}
        territories = {}
        for cid, lst in members.items():
            dominance = len(lst) / total
            territories[str(cid)] = {"population": len(lst), "dominance": round(dominance, 3), "houses": len(clan_houses.get(cid, []))}
        return {"hhi": round(hhi, 4), "territories": territories, "clan_count": len(members)}
    def gini(self, sim: Any) -> dict:
        clans = getattr(sim, "clans", {}) or {}
        larders = [float(info.get("larder", 0) or 0) for info in clans.values()]
        creatures = getattr(sim, "_cached_creatures", None) or list(sim.world.creatures()) if hasattr(sim, "world") else []
        baskets = [float(getattr(c, "food_basket", 0) or 0) for c in creatures]
        def gini_coeff(arr: list[float]) -> float:
            if not arr or sum(arr) == 0:
                return 0.0
            a = sorted(arr)
            n = len(a)
            cum = 0.0
            for i, v in enumerate(a):
                cum += (i + 1) * v
            total = sum(a)
            return round((2 * cum / (n * total) - (n + 1) / n), 3)
        return {"larder_gini": gini_coeff(larders), "basket_gini": gini_coeff(baskets), "larders": larders[:10]}
    def trade_caravan(self, sim: Any) -> dict:
        markets = getattr(sim, "markets", {}) or {}
        caravan_last = getattr(sim, "_caravan_last", {}) or {}
        return {"market_count": len(markets), "markets": [{"a": k[0], "b": k[1], **v} for k, v in markets.items()][:10], "caravan_routes": len(caravan_last)}
    def casus_belli(self, sim: Any) -> dict:
        relations = getattr(sim, "relations", {}) or {}
        tensions = []
        for (a, b), score in relations.items():
            if score < -20:
                la = float(sim.clans.get(a, {}).get("larder", 0) or 0)
                lb = float(sim.clans.get(b, {}).get("larder", 0) or 0)
                tensions.append({"a": a, "b": b, "score": score, "tension": round(min(1.0, (-score)/100 + (1 if la < 20 or lb < 20 else 0)*0.2), 3)})
        tensions.sort(key=lambda x: x["tension"], reverse=True)
        return {"tensions": tensions[:10], "war_risk": round(max([t["tension"] for t in tensions], default=0), 3)}
    def famine_horizon(self, sim: Any) -> dict:
        clans = getattr(sim, "clans", {}) or {}
        total_larder = sum(float(info.get("larder", 0) or 0) for info in clans.values())
        creatures = getattr(sim, "_cached_creatures", None) or list(sim.world.creatures()) if hasattr(sim, "world") else []
        burn = len(creatures) * getattr(sim.config, "energy_decay_per_tick", 0.18) if hasattr(sim, "config") else 0
        regrowth = getattr(sim.config, "food_count", 40) * getattr(sim.config, "plant_growth_rate", 0.05) if hasattr(sim, "config") else 0
        try:
            season = sim._season() if hasattr(sim, "_season") else "spring"
            mult = {"spring": 1.0, "summer": 1.2, "autumn": 1.0, "winter": 0.5}.get(season, 1.0)
            regrowth *= mult
        except Exception:
            pass
        ticks_until_starvation = int(total_larder / max(0.01, burn - regrowth)) if burn > regrowth else 9999
        winter_vuln = 0.0
        try:
            if (sim._season() if hasattr(sim, "_season") else "") == "winter":
                winter_vuln = round(max(0, burn - regrowth) / max(1, burn), 3)
        except Exception:
            pass
        return {"larder": round(total_larder, 1), "burn_rate": round(burn, 3), "regrowth": round(regrowth, 3), "horizon_ticks": ticks_until_starvation, "winter_vulnerability": winter_vuln}
    def extinction_cliff(self, sim: Any) -> dict:
        creatures = getattr(sim, "_cached_creatures", None) or list(sim.world.creatures()) if hasattr(sim, "world") else []
        try:
            thresh = float(getattr(sim.config, "mate_energy_min", 30)) if hasattr(sim, "config") else 30.0
        except Exception:
            thresh = 30.0
        fertile = sum(1 for c in creatures if getattr(c, "sex", "male") == "female" and getattr(c, "stage", "") == "adult" and float(getattr(c, "energy", 0)) > thresh)
        males = sum(1 for c in creatures if getattr(c, "sex", "male") == "male")
        Nf = fertile
        Nm = max(1, males)
        Ne = 4 * Nm * Nf / (Nm + Nf) if (Nm + Nf) else 0
        alarm = Ne < 10 or Nf < 3
        gens = len(set(getattr(c, "generation", 0) for c in creatures))
        return {"fertile_females": Nf, "males": males, "Ne": round(Ne, 1), "alarm": alarm, "gen_diversity": gens}
    def law_counterfactual(self, sim: Any) -> dict:
        law_hist = getattr(sim, "_law_history", []) or []
        pop = list(self.ring.population)[-10:] if self.ring.population else []
        return {"recent_laws": law_hist[-5:], "population_window": pop, "impact": "correlate law tick vs mortality velocity — see mortality window"}
    def unrest(self, sim: Any) -> dict:
        bodies = getattr(sim, "_house_bodies", {}) or {}
        beds_fn = getattr(sim, "_house_beds", None)
        crowding = 0
        for hid, cnt in bodies.items():
            beds = 4
            if callable(beds_fn):
                try:
                    # find house
                    h = next((e for e in sim.world.entities.values() if getattr(e, "id", None) == hid), None)
                    beds = beds_fn(h) if h else 4
                except Exception:
                    beds = 4
            if isinstance(beds, int) and cnt > beds:
                crowding += cnt - beds
        creatures = getattr(sim, "_cached_creatures", None) or list(sim.world.creatures()) if hasattr(sim, "world") else []
        hungry = sum(1 for c in creatures if getattr(c, "status", "") in ("hungry", "starving"))
        tense = 0
        members = getattr(sim, "_clan_members", {}) or {}
        for lst in members.values():
            pers = Counter(getattr(c, "personality", "unknown") for c in lst)
            if len(pers) > 3:
                tense += 1
        score = crowding * 0.5 + hungry * 0.1 + tense * 2
        return {"crowding": crowding, "hungry": hungry, "tense_clans": tense, "unrest_score": round(score, 2), "schism_risk": score > 10}
    def summary(self, sim: Any) -> dict:
        import time
        now = time.time()
        if self._last_summary is not None and now - self._last_summary_time < 1.0 and getattr(sim, "tick", 0) == self._last_summary_tick:
            return self._last_summary
        cache_key = "summary"
        if cache_key in self._cached and now - self._cached[cache_key][0] < 1.0:
            return self._cached[cache_key][1]
        try:
            payload = {
                "tick": getattr(sim, "tick", 0),
                "ring": self.ring.snapshot(),
                "mortality": self.mortality.stacked(),
                "generational": self.generational_tracker(sim),
                "trophic": self.lotka_volterra(sim),
                "biodiversity": self.biodiversity(sim),
                "heritability": self.heritability(sim),
                "hegemony": self.hegemony(sim),
                "gini": self.gini(sim),
                "trade": self.trade_caravan(sim),
                "casus": self.casus_belli(sim),
                "famine": self.famine_horizon(sim),
                "extinction": self.extinction_cliff(sim),
                "law_impact": self.law_counterfactual(sim),
                "unrest": self.unrest(sim),
                "time": round(now, 2),
            }
        except Exception:
            logging.getLogger(__name__).exception("analytics summary computation failed")
            payload = {"error": "analytics_unavailable", "tick": getattr(sim, "tick", 0)}
        self._last_summary = payload
        self._last_summary_tick = getattr(sim, "tick", 0)
        self._last_summary_time = now
        self._cached[cache_key] = (now, payload)
        return payload
    def sparkline(self, key: str) -> list[float]:
        return self.ring.sparkline(key)
_ENGINE: AnalyticsEngine | None = None
def get_engine(fresh: bool = False) -> AnalyticsEngine:
    global _ENGINE
    if _ENGINE is None or fresh:
        _ENGINE = AnalyticsEngine()
    return _ENGINE
def attach_to_sim(sim: Any, fresh: bool = False) -> AnalyticsEngine:
    eng = get_engine(fresh=fresh)
    try:
        sim._analytics = eng
    except Exception:
        pass
    return eng
