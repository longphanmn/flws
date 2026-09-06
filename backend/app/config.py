"""World and simulation configuration — Developer: Long Phan <long@minhnhan.in>."""

import os
from dataclasses import dataclass


def _env(name: str, cast, default):
    raw = os.environ.get(name)
    if raw in (None, ""):
        return default
    if cast is bool:
        return raw.lower() in ("true", "1", "yes", "on")
    return cast(raw)


@dataclass(frozen=True)
class Config:
    # World geometry (grid units) — 400x300 = 3x the original 200x200 area
    width: float = 400.0
    height: float = 300.0
    boundary: str = "wrap"  # "wrap" | "clamp"

    # Simulation
    seed: int = 42
    tick_rate: float = 10.0  # ticks per second

    # Initial population (Flatland castes).
    # -1 => auto-scale from map area × density with ±spawn_variance jitter;
    # any value >= 0 pins that group explicitly (used by tests/scenarios).
    num_triangles: int = -1  # soldiers/workmen (isosceles triangles)
    num_squares: int = -1  # gentlemen
    num_pentagons: int = -1  # professionals
    num_hexagons: int = -1  # nobility
    num_priests: int = -1  # near-circles (priesthood)
    num_women: int = -1  # line segments
    num_houses: int = -1

    # World generation densities (per grid unit²) and spawn jitter.
    creature_density: float = 0.0013  # ~156 creatures on the 400×300 map — at least 50 as requested
    house_density: float = 0.00065  # ~78 houses covering >=85% population beds on 400x300 map
    spawn_variance: float = 0.25  # ±25% around the density target

    food_count: int = 210  # was 70 on 200x200 — scales x3 with the 400x300 map
    # Plants & nutrient cycle (§H) + biodiversity (§O)
    plant_growth_rate: float = 0.05
    plant_spread_rate: float = 0.006
    nutrient_cycle_rate: float = 0.65
    plant_variants_enabled: bool = True
    poison_rate: float = 0.01
    beast_ratio: float = 0.0
    diet_strictness: float = 0.0
    winter_food_mult: float = 0.5

    # Territory & clan depth (§P)
    territory_enabled: bool = True  # §P: clans claim zone around house, trespass sours relations
    territory_radius: float = 14.0  # radius of clan territory circle
    trespass_decay: float = 0.25  # was 1.0 — rare war: low trespass decay

    # Clan founding (§V) — settlements define clans, castes mix inside them
    max_clans: int = -1  # -1 = one clan per house; N ≥ 1 clusters founders into N spatial clans

    # Totem & clan depth (§P)
    totems_enabled: bool = True  # §P/AP: each clan bears a Sacred Avatar totem with subtle buff
    succession_enabled: bool = True  # §P: leader succession on death emits succession event

    # Schism — WorldBox rebellion (§S P1) — enabled but rare
    schism_enabled: bool = True  # rebellion enabled by default
    schism_threshold: float = 0.5  # fraction unhappy to trigger
    schism_min_pop: int = 6  # minimum clan pop

    # Ages — super-seasons (§S)
    age_enabled: bool = True  # long era bending world: Ice/Chaos/Plague/Golden
    age_length: int = 12000  # ticks per age (5 seasons)

    # Culture & Traits (§S)
    culture_enabled: bool = True  # clan culture spreads/splits, grants bonus
    trait_mutation_rate: float = 0.02  # chance mutation adds heritable behaviour trait
    culture_spread_rate: float = 0.005  # per tick ally culture spread

    # Wildfire & Disasters (§S)
    wildfire_enabled: bool = True  # fire ignites via storm lightning, spreads
    fire_rate: float = 0.00008  # chance/tick to ignite random plant
    fire_spread_rate: float = 0.035  # spread to neighboring plants
    disaster_enabled: bool = True  # meteor/flood stochastic
    disaster_rate: float = 0.00004  # chance/tick for disaster

    # Communication & Care (§Q) — enabled by default
    communication_enabled: bool = True  # food + alarm calls, clan recruitment — enabled
    signal_radius: float = 12.0  # heard within this range
    food_call_rate: float = 0.08  # well-fed finds food → calls with this chance/tick
    alarm_call_rate: float = 0.12  # sees predator → alarm call chance/tick

    # Communication II — knowledge, teaching & mobbing (§X)
    knowledge_enabled: bool = True  # creatures learn/remember/share facts
    knowledge_ttl: int = 600  # ticks a fact stays in memory before it fades
    knowledge_share_rate: float = 0.05  # chance/tick to broadcast freshest fact to clan
    help_call_enabled: bool = True  # attacked creatures call their clan to mob the attacker
    help_radius: float = 12.0  # clan-mates rally within this range; defenders soften blows
    defense_weight: float = 0.5  # damage reduction per defender mobbing the attacker

    # Corpses & scavenging
    corpses_enabled: bool = True
    corpse_ttl: int = 600  # ticks before a corpse decays away
    corpse_energy: float = 25.0  # energy a fresh corpse holds

    # Food decay (§AE) — nothing lasts forever
    food_decay_enabled: bool = True  # mature plants wither, fertilise, vanish
    food_lifespan_ticks: int = 9000  # ticks a mature plant lives (× variant mult)

    # Agriculture (§AM) — sowing, farm plots, granaries, soil & feasts
    agriculture_enabled: bool = True  # seeds, farm plots, tending & irrigation furrows
    granaries_enabled: bool = True  # clan granaries store grain & cured rations
    granary_capacity: float = 400.0  # units one clan granary holds
    soil_depletion_enabled: bool = True  # monocropping exhausts the living soil
    banquets_enabled: bool = True  # overflowing granaries feed a clan feast

    # Communication, language & diplomacy (§AN)
    vocalizations_enabled: bool = True  # caste chants, peace-hums, war-chirps & chimes
    scent_enabled: bool = True  # forager scent trails and danger scent markers
    envoys_enabled: bool = True  # peace emissaries & boundary stones
    markets_enabled: bool = True  # neutral trading posts & travelling caravans
    omens_enabled: bool = True  # priests foresee the turning of the season
    dialect_drift_enabled: bool = True  # isolated clans drift apart in speech

    # Unified Theology (§AP) — the 8 Sacred Avatars of the Sphere, shrines,
    # dawn & dusk tithes, seasonal miracles, law resonance and temples
    theology_enabled: bool = True  # shrines/tithes/miracles/sermons/synods
    tithe_rate: float = 0.04  # fraction of energy_max offered at each devotion
    temple_faith_cost: float = 400.0  # clan faith needed to raise a temple

    # Behaviour tuning
    perceive_radius: float = 20.0
    eat_radius: float = 1.4
    energy_max: float = 100.0
    energy_start: float = 85.0
    energy_decay_per_tick: float = 0.025
    energy_from_food: float = 32.0
    wander_turn: float = 0.35  # max heading change (rad) when wandering
    steer_turn: float = 0.45  # max heading change when steering to food

    # Life / hunger
    hungry_ratio: float = 0.35  # energy/max at or below -> hungry
    starving_ratio: float = 0.15  # energy/max at or below -> starving
    hungry_perceive_mult: float = 1.3  # hungry creatures notice food farther away
    desperate_perceive_mult: float = 1.6  # starving: even farther
    desperate_speed_mult: float = 1.35  # starving: move faster
    food_giveup_ticks: int = 240  # ticks a meal is abandoned when blocked by rock/wall; seek elsewhere
    lifespan_mult: float = 1.0  # god's law: scale every caste's natural lifespan

    # Reproduction & inheritance (Nature's Law) — tuned for 30-day survival
    birth_enabled: bool = True
    adult_age: float = 600.0  # ticks before a creature may mate (half a day)
    mate_radius: float = 10.0  # max distance between parents
    mate_energy_min: float = 30.0  # both parents must hold this much energy
    birth_rate: float = 0.05  # chance per eligible pair per tick (× fertility)
    sex_ratio: float = 0.5  # probability a child is a son
    mutation_rate: float = 0.05  # chance a son's side count deviates ±1
    mutation_heritability: float = 0.35  # fraction of parental irregularity inherited by child (dampened)
    max_sides: int = 24  # sons stop gaining sides here (= Circle)
    birth_energy_cost: float = 20.0  # each parent pays
    reproduction_cooldown: int = 600  # ticks both parents wait after a birth
    carrying_capacity: int = -1  # soft cap: fertility fades above it; -1 => scale with map area
    max_population: int = -1  # hard cap: no births beyond it; -1 => scale with map area
    euthanasia_threshold: float = 0.7  # irregularity at/below -> demotion, above -> consumed

    # Health & disease
    disease_enabled: bool = True
    disease_outbreak_rate: float = 0.00006  # chance/tick a new outbreak begins
    disease_rate: float = 0.035  # spread chance per healthy neighbour per tick
    disease_radius: float = 3.0  # contagion range
    disease_energy_drain: float = 0.05  # extra energy loss while infected
    recovery_rate: float = 0.03  # chance/tick an infected creature recovers
    disease_lethality: float = 0.18  # scales how fast infection drains health

    # Environment: day/night, seasons, weather
    day_length: int = 1200  # ticks per day cycle
    season_length: int = 14400  # ticks per season; 12 days per season (48-day year)
    night_sight_mult: float = 0.6  # sight scale during the night
    weather_enabled: bool = True
    weather_change_rate: float = 0.002  # chance/tick the weather turns
    fog_sight_mult: float = 0.6  # sight scale in fog
    rain_speed_mult: float = 0.85  # movement scale in rain/storm
    storm_wander_bonus: float = 0.35  # extra heading chaos in storms

    # Weather → crops (§R)
    rain_growth_mult: float = 1.25  # rain/storm boost to plant growth
    fog_mushroom_mult: float = 1.35  # fog boost to mushroom growth
    storm_plant_damage: float = 0.02  # chance/tick storm strips growth from exposed plants

    # Weather → sickness (§R) chill / wet contagion
    weather_sickness_enabled: bool = False  # chill + wet contagion; disabled by default
    chill_rate: float = 0.04  # chill built per tick unsheltered in rain/storm/winter night
    chill_threshold: float = 12.0  # chill at which creature is sick
    chill_drain: float = 0.18  # health drain per tick when chilled
    wet_disease_mult: float = 1.5  # wet/cold catch disease faster, recover slower

    # Night rest
    sleep_enabled: bool = True  # creatures shelter in houses after dark
    sleep_energy_mult: float = 0.5  # energy decay while asleep

    # Shelter — tuned for sustainability (exposure was 0.3, now 0.03)
    shelter_enabled: bool = True  # houses are scarce, contested and life-saving
    exposure_drain: float = 0.03  # extra energy/tick outdoors in rain/storm or at night (was 0.3)
    house_capacity: int = 12  # beds in an 8×8 hall; scales with floor area
    house_claim_enabled: bool = True  # clans claim houses as settlements
    rest_recovery_mult: float = 2.0  # indoor sleeping health regen multiplier
    house_decay_ticks: int = 2400  # abandoned house stands this many ticks before crumbling to ruin

    # Hearths (§AQ PH-1) — permanent fires that warm the roofs that feed them
    hearths_enabled: bool = True  # clan members buy hearth fuel from the larder

    # Terrain (-1 => auto-scale from area)
    fertile_patches: int = -1  # green grounds where food prefers to grow
    rock_count: int = -1  # solid stone circles that block movement
    fertile_food_bias: float = 0.7  # fraction of food spawned on fertile ground

    # Rivers (§AQ PH-3) — horizontal channels: fords, floods, bridges & dams
    rivers_enabled: bool = True
    river_count: int = 2  # channel bands across the map at world creation

    # Relief (§AQ PH-4) — the height of the land: grades, cliffs & roads
    relief_enabled: bool = True  # elevation field bends energy, speed & growth

    # Materials (§AQ PH-6) — structural integrity & the rubble of collapses
    structural_enabled: bool = True  # storms & floods wear buildings; builders mend
    rubble_blocking_enabled: bool = True  # collapsed ruins block lots until cleared

    # Seismic & wave physics (§AQ PH-8)
    earthquake_enabled: bool = False  # rare quakes displace, damage & crack
    earthquake_rate: float = 0.00008  # chance/tick a quake begins
    signal_speed: float = 8.0  # wavefront speed, units/tick (0 = instant news)

    # Electrostatics (§AQ PH-9)
    lightning_enabled: bool = True  # storms strike real bolts
    lightning_strike_rate: float = 0.0015  # chance/tick during a storm

    # Cosmological (§AQ PH-10)
    anomaly_count: int = 3  # hidden zones of altered physics at world creation

    # Society — interaction & clan relations — war rare tuning
    cohesion_weight: float = 0.0  # pull toward same-clan flock centre
    alignment_weight: float = 0.0  # match neighbours' heading
    separation_weight: float = 0.0  # personal-space push from any neighbour
    flock_radius: float = 6.0  # interaction perception range
    relation_drift_rate: float = 2.2  # was 1.0 — relax faster, war rarer
    alliance_threshold: int = 50  # score at/above which two clans are allies
    rivalry_threshold: int = -75  # was -50 — more negative, feuds rarer

    # Predation (§I) — Carnivore caste
    predation_enabled: bool = False
    predator_ratio: float = 0.0
    hunt_radius: float = 8.0  # predator sight for prey
    bite_damage: float = 28.0  # damage on bite (gentle wound)
    bite_cooldown: int = 15  # ticks between bites
    energy_from_prey: float = 40.0  # energy predator gains per kill
    fear_radius: float = 12.0  # prey flee when predator within this range

    # Clan war (§I) — rival clans fight on contact — enabled but rare
    war_enabled: bool = True  # enabled by default, but rare
    attack_radius: float = 1.8  # distance for clan war engagement
    attack_damage: float = 30.0  # wound not lethal, so war rarely fatal

    # Politics (§AB) — coalitions, leader agency, resources, betrayal
    coalitions_enabled: bool = True  # allied clans form defensive blocs
    coalition_threshold: int = 40  # relation score at which a clan may join
    coalition_min_size: int = 2  # smallest viable bloc (incl. founder)
    leader_decisions_enabled: bool = True  # leaders declare war/peace/tribute as plots
    resource_sharing_enabled: bool = True  # clan larder at the settlement
    larder_capacity: float = 300.0  # energy a clan store holds
    aid_rate: float = 0.05  # chance/tick a surplus ally feeds a starving ally
    tribute_enabled: bool = True  # weak clans pay a protector for peace
    betrayal_enabled: bool = True  # leaders may break alliances and strike
    defection_enabled: bool = True  # unhappy members defect to other clans

    # Desperation cannibalism (§AC) — eat the enemy & the weak
    cannibalism_enabled: bool = True  # the starving may hunt the living
    cannibalism_hunger_ratio: float = 0.08  # only at the absolute brink of starvation
    cannibalism_energy: float = 35.0  # gained per desperate kill
    eat_enemy_enabled: bool = True  # enemy-clan members are legitimate prey
    eat_kin_enabled: bool = True  # weak kin too — at a terrible price (disabled in balance & sustainable presets)
    kin_stigma: int = 40  # relation hit between exiled band and former clan
    exile_on_kin_eat: bool = True  # kin-eater cast out, founding an outcast band

    # Houses
    house_min_size: float = 5.5
    house_max_size: float = 8.0
    door_clearance: float = 1.5  # door width = clearance * largest creature diameter
    house_gap: float = 6.0  # min clear gap between house walls — keeps alleys passable so creatures never wedge between shelters

    # Chronicle
    history_max: int = 200  # death events kept in the chronicle

    # M-4 OpenMP multi-core — enabled at >100 for 4× CPU verification
    omp_enabled: bool = True  # use 8-core OpenMP batch when pop exceeds threshold
    omp_threshold: int = 100  # min creatures to trigger parallel batch (tunable via FLATWORLD_OMP_THRESHOLD)

    # BA Micro-Neural Network & Evolutionary Engine — always on (295 fixed)
    nn_inference_hz: int = 15  # inference every N ticks = 60/nn_inference_hz
    mutation_sigma: float = 0.08
    crossover_rate: float = 0.5

    # BC Geometric Physics & Morphological Evolution — annealing governs shape
    morphology_annealing_enabled: bool = True  # BC: master flag
    annealing_start_generation: int = 15  # g_start for λ(g) (grace period before drift)
    annealing_decay_generations: int = 250  # g_decay for λ(g) (smooth gradual decay over 250 gens)
    morph_lambda_override: float | None = None  # BC: Optional -1.0 auto, 0..1 override
    vertex_mutation_std: float = 0.025  # σr for radii (gentle displacement)
    angle_mutation_std: float = 0.012  # σφ for angles (subtle angle drift)
    topological_mutation_rate: float = 0.008  # p_topo * (1-λ) (rare vertex additions/removals)

    # Phase 5 Extinction Safeguards — homeostatic negative feedback
    safeguard_enabled: bool = True
    safeguard_critical_pop: int = 12  # Kcrit
    safeguard_relief_ratio: float = 0.30  # Ksafe = carrying * ratio
    safeguard_genesis_batch: int = 6  # Tier3 batch
    safeguard_morph_mercy: bool = True  # suspend euthanasia when η>0.3
    safeguard_max_miracles: int = 1  # Tier3 genesis miracle limit (1 = trigger once then allow extinction)

    # Phase 4 Density-Dependent Soft-Cap Damping — overpopulation homeostatic
    soft_cap_enabled: bool = True
    damping_steepness: float = 12.0  # birth_rate divisor steepness (aggressive curve)
    crowding_stress_mult: float = 1.0  # metabolic drain multiplier under crowding
    resource_strain_mult: float = 2.0  # plant growth/spread divisor under crowding

    # BF Early Population Boom Limiter — days 0-1.2 birth is gently throttled
    boom_ramp_days: float = 1.2  # days of soft birth ramp at world start (1440 ticks)
    boom_birth_floor: float = 0.40  # birth rate floor at day 0 (0.40× ramped to 1.0× by day 1.2)
    boom_cooldown_mult: float = 1.0  # standard reproduction cooldown
    boom_energy_mult: float = 1.0  # standard mate energy threshold
    initial_season_offset: int = 0  # 0=spring, 1=summer, 2=autumn, 3=winter

    @classmethod
    def from_env(cls) -> "Config":
        """Live runtime config: defaults to the Balance Goldilocks preset."""
        return cls(
            width=_env("FLATWORLD_WIDTH", float, 400.0),
            height=_env("FLATWORLD_HEIGHT", float, 300.0),
            boundary=_env("FLATWORLD_BOUNDARY", str, "wrap"),
            seed=_env("FLATWORLD_SEED", int, 42),
            tick_rate=_env("FLATWORLD_TICK_RATE", float, 10.0),
            food_count=_env("FLATWORLD_FOOD_COUNT", int, 380),
            plant_growth_rate=_env("FLATWORLD_PLANT_GROWTH_RATE", float, 0.065),
            plant_spread_rate=_env("FLATWORLD_PLANT_SPREAD_RATE", float, 0.008),
            winter_food_mult=_env("FLATWORLD_WINTER_FOOD_MULT", float, 0.82),
            poison_rate=_env("FLATWORLD_POISON_RATE", float, 0.008),
            perceive_radius=_env("FLATWORLD_PERCEIVE_RADIUS", float, 16.0),
            energy_decay_per_tick=_env("FLATWORLD_ENERGY_DECAY", float, 0.025),
            carrying_capacity=_env("FLATWORLD_CARRYING_CAPACITY", int, 350),
            max_population=_env("FLATWORLD_MAX_POPULATION", int, 420),
            disease_enabled=_env("FLATWORLD_DISEASE_ENABLED", bool, True),
            disease_outbreak_rate=_env("FLATWORLD_DISEASE_OUTBREAK_RATE", float, 0.00006),
            disease_rate=_env("FLATWORLD_DISEASE_RATE", float, 0.035),
            disease_energy_drain=_env("FLATWORLD_DISEASE_ENERGY_DRAIN", float, 0.05),
            recovery_rate=_env("FLATWORLD_RECOVERY_RATE", float, 0.060),
            disease_lethality=_env("FLATWORLD_DISEASE_LETHALITY", float, 0.07),
            predation_enabled=_env("FLATWORLD_PREDATION_ENABLED", bool, True),
            predator_ratio=_env("FLATWORLD_PREDATOR_RATIO", float, 0.008),
            bite_damage=_env("FLATWORLD_BITE_DAMAGE", float, 16.0),
            bite_cooldown=_env("FLATWORLD_BITE_COOLDOWN", int, 15),
            war_enabled=_env("FLATWORLD_WAR_ENABLED", bool, True),
            attack_damage=_env("FLATWORLD_ATTACK_DAMAGE", float, 30.0),
            relation_drift_rate=_env("FLATWORLD_RELATION_DRIFT", float, 2.2),
            rivalry_threshold=_env("FLATWORLD_RIVALRY_THRESHOLD", int, -45),
            trespass_decay=_env("FLATWORLD_TRESPASS_DECAY", float, 0.45),
            house_capacity=_env("FLATWORLD_HOUSE_CAPACITY", int, 14),
            schism_enabled=_env("FLATWORLD_SCHISM_ENABLED", bool, True),
            schism_threshold=_env("FLATWORLD_SCHISM_THRESHOLD", float, 0.6),
            schism_min_pop=_env("FLATWORLD_SCHISM_MIN_POP", int, 8),
            communication_enabled=_env("FLATWORLD_COMMUNICATION_ENABLED", bool, True),
            omp_enabled=_env("FLATWORLD_OMP_ENABLED", bool, True),
            omp_threshold=_env("FLATWORLD_OMP_THRESHOLD", int, 100),
            morphology_annealing_enabled=_env("FLATWORLD_MORPHOLOGY_ANNEALING_ENABLED", bool, True),
            soft_cap_enabled=_env("FLATWORLD_SOFT_CAP_ENABLED", bool, True),
            safeguard_enabled=_env("FLATWORLD_SAFEGUARD_ENABLED", bool, True),
            safeguard_max_miracles=_env("FLATWORLD_SAFEGUARD_MAX_MIRACLES", int, 1),
            eat_kin_enabled=_env("FLATWORLD_EAT_KIN_ENABLED", bool, False),
            cannibalism_hunger_ratio=_env("FLATWORLD_CANNIBALISM_HUNGER_RATIO", float, 0.08),
        )

    @property
    def tick_interval(self) -> float:
        return 1.0 / self.tick_rate if self.tick_rate > 0 else 0.1

    # -1 sentinels resolve against map area so caps keep pace with density-scaled
    # population (80 carrying / 140 hard cap on the classic 200x200 baseline).
    @property
    def area_scale(self) -> float:
        return (self.width * self.height) / (200.0 * 200.0)

    @property
    def effective_carrying_capacity(self) -> int:
        if self.carrying_capacity >= 0:
            return self.carrying_capacity
        return max(2, round(80 * self.area_scale))

    @property
    def effective_max_population(self) -> int:
        if self.max_population >= 0:
            return self.max_population
        return max(2, round(140 * self.area_scale))
