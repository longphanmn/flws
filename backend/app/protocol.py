"""Wire protocol schemas shared with the web frontend.

Message flow:
  server -> client: {"type": "hello", ...} then {"type": "state", ...} each tick
  client -> server: {"action": "pause"|"resume"|"step"|"reset"|"set_speed", "value": ...}
"""

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class ControlAction(str, Enum):
    PAUSE = "pause"
    RESUME = "resume"
    STEP = "step"
    RESET = "reset"
    SET_SPEED = "set_speed"


class ControlMessage(BaseModel):
    action: ControlAction
    value: Optional[float] = None


class EntityState(BaseModel):
    id: int
    kind: Literal["creature", "food", "house", "corpse"]
    x: float
    y: float
    angle: float
    shape: Optional[Literal["polygon", "line"]] = None
    sides: Optional[int] = None
    caste: Optional[str] = None
    energy: Optional[float] = None
    growth: Optional[float] = None  # plants: 0..1 maturity (renderer scales size)
    variant: Optional[Literal["grass", "grain", "berry", "medicinal_herb", "mushroom", "poisonous"]] = None
    withering: Optional[bool] = None  # §AE: mature plant past its wilt threshold
    cultivated: Optional[bool] = None  # §AM: sown crop — grows faster, feeds better
    irrigated: Optional[bool] = None  # §AM: furrow-watered crop

    size: Optional[float] = None
    status: Optional[Literal["", "hungry", "starving"]] = None
    radius: Optional[float] = None
    age: Optional[int] = None
    lifespan: Optional[float] = None
    stage: Optional[Literal["infant", "juvenile", "adult", "elder"]] = None
    irregularity: Optional[float] = None
    health: Optional[float] = None
    infected: Optional[bool] = None
    meals: Optional[int] = None
    sex: Optional[Literal["male", "female"]] = None
    mother_id: Optional[int] = None
    father_id: Optional[int] = None
    clan_id: Optional[int] = None
    clan_color: Optional[str] = None
    clan_name: Optional[str] = None
    is_predator: Optional[bool] = None
    is_herbivore: Optional[bool] = None
    sleeping: Optional[bool] = None
    indoors: Optional[bool] = None
    generation: Optional[int] = None
    born_tick: Optional[int] = None
    personal_name: Optional[str] = None
    glyph: Optional[str] = None
    hue_shift: Optional[float] = None
    scale_jitter: Optional[float] = None
    angle_jitter: Optional[float] = None
    chill: Optional[float] = None
    body_temp: Optional[float] = None  # §AQ PH-1: body temperature (°C-ish)
    torpid: Optional[bool] = None  # §AQ PH-7: cold-torpor shutdown
    trait: Optional[str] = None
    iso_angle: Optional[float] = None  # §BG: isosceles apex angle for Soldier razor
    morph_k: Optional[int] = None  # §BG: active vertex count K∈[3,24]
    morph_traits: Optional[list[float]] = None  # §BG: [A,P,Izz,theta_min,asym,Dmult]
    morph_radii: Optional[list[float]] = None  # §BG: polar radii (detailed, inspector only)
    morph_angles: Optional[list[float]] = None  # §BG: polar angles (detailed, inspector only)
    archetype: Optional[str] = None  # §BH-9 behavioral archetype tag
    nn_genome: Optional[list[float]] = None  # §BH-10 full 295 weights (inspector heatmap, detail only)
    door_width: Optional[float] = None
    door_offset: Optional[float] = None
    door_side: Optional[Literal["north", "east", "south", "west"]] = None
    is_ruin: Optional[bool] = None
    abandoned_ticks: Optional[int] = None
    takeover_age: Optional[int] = None  # §AT-3: ticks since last hostile takeover
    material: Optional[Literal["straw", "wood", "stone", "clay"]] = None  # §AQ PH-1/6
    murals: Optional[int] = None  # §AN: painted chronicle inscribed on the walls
    hearth_lit: Optional[bool] = None  # §AQ PH-1: fire burns on this hearth
    hp_frac: Optional[float] = None  # §AQ PH-6: structural integrity remaining
    rubble: Optional[bool] = None  # §AQ PH-6: collapsed lot, uncleared rubble
    nn_hidden: Optional[float] = None  # BA: recurrent hidden state [-1,1]
    nn_outputs: Optional[list[float]] = None  # BA: last 7 outputs [thrust,steer,interact,social,vocal_amp,vocal_freq,recurrent]
    nn_genome_preview: Optional[list[float]] = None  # BA: first 8 genome weights preview


class StateMessage(BaseModel):
    type: Literal["state"] = "state"
    tick: int
    seed: int = 0
    width: float
    height: float
    boundary: str
    population: dict[str, int] = Field(default_factory=dict)
    entities: list[EntityState] = Field(default_factory=list)
    creatures_alive: int = 0
    creatures_dead: int = 0
    dead_by_cause: dict[str, int] = Field(default_factory=dict)
    infected_count: int = 0
    time_of_day: float = 0.25
    day: int = 1
    season: Literal["spring", "summer", "autumn", "winter"] = "spring"
    weather: Literal["clear", "rain", "fog", "storm"] = "clear"
    terrain_fertile: list[dict[str, float]] = Field(default_factory=list)
    terrain_rocks: list[dict[str, float]] = Field(default_factory=list)
    relations: list[dict[str, int]] = Field(default_factory=list)
    clans: dict[str, dict[str, Any]] = Field(default_factory=dict)
    events: list["HistoryEvent"] = Field(default_factory=list)
    signals: list[dict[str, Any]] = Field(default_factory=list)
    fires: list[dict[str, Any]] = Field(default_factory=list)
    campfires: list[dict[str, Any]] = Field(default_factory=list)  # §AO field campfires
    boundary_stones: list[dict[str, Any]] = Field(default_factory=list)  # §AN
    markets: list[dict[str, Any]] = Field(default_factory=list)  # §AN trading posts
    wind: dict[str, float] = Field(default_factory=dict)  # §AQ PH-2 {angle,speed}
    rivers: list[dict[str, Any]] = Field(default_factory=list)  # §AQ PH-3 channels
    bridges: list[dict[str, Any]] = Field(default_factory=list)  # §AQ PH-3 planks
    dams: list[dict[str, Any]] = Field(default_factory=list)  # §AQ PH-3 masonry
    elevation: dict[str, Any] = Field(default_factory=dict)  # §AQ PH-4 static height field
    lightning: list[dict[str, Any]] = Field(default_factory=list)  # §AQ PH-9 bolts
    anomalies: list[dict[str, Any]] = Field(default_factory=list)  # §AQ PH-10 discovered zones
    law_wave: dict[str, Any] = Field(default_factory=dict)  # §AQ PH-10 shimmer front
    age: Optional[str] = None
    age_tick: int = 0
    age_day: int = 1
    age_total_days: int = 10
    paused: bool = False
    safeguard_active: bool = False
    softcap_active: bool = False


class DeltaStateMessage(BaseModel):
    """Phase 1 AJ: Lightweight delta snapshot broadcasting only changed/moving entities."""
    type: Literal["delta_state"] = "delta_state"
    tick: int
    seed: int = 0
    upsert_entities: list[EntityState | dict[str, Any]] = Field(default_factory=list)
    remove_ids: list[int] = Field(default_factory=list)
    population: dict[str, int] = Field(default_factory=dict)
    creatures_alive: int = 0
    creatures_dead: int = 0
    dead_by_cause: dict[str, int] = Field(default_factory=dict)
    infected_count: int = 0
    time_of_day: float = 0.25
    day: int = 1
    season: Literal["spring", "summer", "autumn", "winter"] = "spring"
    weather: Literal["clear", "rain", "fog", "storm"] = "clear"
    relations: list[dict[str, int]] = Field(default_factory=list)
    clans: dict[str, dict[str, Any]] = Field(default_factory=dict)
    events: list["HistoryEvent"] = Field(default_factory=list)
    signals: list[dict[str, Any]] = Field(default_factory=list)
    fires: list[dict[str, Any]] = Field(default_factory=list)
    campfires: list[dict[str, Any]] = Field(default_factory=list)  # §AO field campfires
    boundary_stones: list[dict[str, Any]] = Field(default_factory=list)  # §AN
    markets: list[dict[str, Any]] = Field(default_factory=list)  # §AN trading posts
    wind: dict[str, float] = Field(default_factory=dict)  # §AQ PH-2 {angle,speed}
    rivers: list[dict[str, Any]] = Field(default_factory=list)  # §AQ PH-3 channels
    bridges: list[dict[str, Any]] = Field(default_factory=list)  # §AQ PH-3 planks
    dams: list[dict[str, Any]] = Field(default_factory=list)  # §AQ PH-3 masonry
    elevation: dict[str, Any] = Field(default_factory=dict)  # §AQ PH-4 static height field
    lightning: list[dict[str, Any]] = Field(default_factory=list)  # §AQ PH-9 bolts
    anomalies: list[dict[str, Any]] = Field(default_factory=list)  # §AQ PH-10 discovered zones
    law_wave: dict[str, Any] = Field(default_factory=dict)  # §AQ PH-10 shimmer front
    age: Optional[str] = None
    age_tick: int = 0
    age_day: int = 1
    age_total_days: int = 10
    paused: bool = False
    safeguard_active: bool = False
    softcap_active: bool = False



class HistoryEvent(BaseModel):
    type: Literal[
        "death", "birth", "promotion", "demotion", "outbreak", "recovery",
        "bloom", "alliance", "rivalry", "predation", "war", "ruin", "settlement", "succession", "schism",
        "fire", "disaster", "conquest", "culture",
        "coalition_formed", "coalition_joined", "coalition_dissolved",
        "peace", "tribute", "betrayal", "defection", "cannibalism", "exile",
        "wither", "takeover",
        "miracle", "sermon", "synod", "temple", "epiphany", "resonance",
        "compost", "banquet", "raid", "hospitality",
        "peace_envoy", "market", "caravan", "omen", "regicide", "herald",
        "anomaly", "clan_extinction", "extinction",
    ] = ("death")
    tick: int
    entity_id: int
    caste: Optional[str] = None
    cause: str = ""  # death cause when type == "death"
    x: float = 0.0
    y: float = 0.0
    payload: dict[str, Any] = Field(default_factory=dict)


class HelloMessage(BaseModel):
    type: Literal["hello"] = "hello"
    seed: int
    tick_rate: float
    width: float
    height: float
    boundary: str
    paused: bool = False


class GodLaws(BaseModel):
    """Laws of nature god may set across the 6 macro domains. God cannot touch individual creatures."""
    model_config = ConfigDict(extra="ignore")

    # Global Topology
    boundary: Optional[Literal["wrap", "clamp"]] = None

    # 1. Ecology & Survival
    food_count: Optional[int] = Field(None, ge=0, le=2000)
    energy_max: Optional[float] = Field(None, gt=1, le=10000)
    energy_decay_per_tick: Optional[float] = Field(None, ge=0, le=2)
    energy_from_food: Optional[float] = Field(None, ge=0, le=1000)
    plant_variants_enabled: Optional[bool] = None
    plant_growth_rate: Optional[float] = Field(None, ge=0, le=1)
    plant_spread_rate: Optional[float] = Field(None, ge=0, le=1)
    nutrient_cycle_rate: Optional[float] = Field(None, ge=0, le=10)
    poison_rate: Optional[float] = Field(None, ge=0, le=1)
    food_decay_enabled: Optional[bool] = None
    food_lifespan_ticks: Optional[int] = Field(None, ge=100, le=1000000)
    agriculture_enabled: Optional[bool] = None
    granaries_enabled: Optional[bool] = None
    granary_capacity: Optional[float] = Field(None, ge=0, le=100000)

    # 2. Biology & Evolution
    perceive_radius: Optional[float] = Field(None, gt=0.5, le=60)
    eat_radius: Optional[float] = Field(None, gt=0.1, le=10)
    hungry_ratio: Optional[float] = Field(None, gt=0, le=1)
    starving_ratio: Optional[float] = Field(None, gt=0, le=1)
    steer_turn: Optional[float] = Field(None, ge=0, le=3.2)
    birth_enabled: Optional[bool] = None
    lifespan_mult: Optional[float] = Field(None, ge=0.01, le=100)
    adult_age: Optional[float] = Field(None, ge=0, le=100000)
    birth_rate: Optional[float] = Field(None, ge=0, le=1)
    carrying_capacity: Optional[int] = Field(None, ge=-1, le=10000)
    max_population: Optional[int] = Field(None, ge=-1, le=15000)
    mutation_rate: Optional[float] = Field(None, ge=0, le=1)
    mutation_heritability: Optional[float] = Field(None, ge=0, le=1)
    sex_ratio: Optional[float] = Field(None, ge=0, le=1)
    max_sides: Optional[int] = Field(None, ge=3, le=64)
    euthanasia_threshold: Optional[float] = Field(None, ge=0, le=1)
    mutation_sigma: Optional[float] = Field(None, ge=0, le=1)
    crossover_rate: Optional[float] = Field(None, ge=0, le=1)
    morphology_annealing_enabled: Optional[bool] = None
    annealing_start_generation: Optional[int] = Field(None, ge=0, le=1000)
    annealing_decay_generations: Optional[int] = Field(None, ge=1, le=5000)
    morph_lambda_override: Optional[float] = Field(None, ge=-1.0, le=1.0)
    vertex_mutation_std: Optional[float] = Field(None, ge=0, le=0.5)
    angle_mutation_std: Optional[float] = Field(None, ge=0, le=0.5)
    topological_mutation_rate: Optional[float] = Field(None, ge=0, le=0.2)
    safeguard_enabled: Optional[bool] = None
    safeguard_critical_pop: Optional[int] = Field(None, ge=2, le=50)
    safeguard_relief_ratio: Optional[float] = Field(None, ge=0.05, le=0.5)
    safeguard_genesis_batch: Optional[int] = Field(None, ge=1, le=20)
    safeguard_morph_mercy: Optional[bool] = None
    safeguard_max_miracles: Optional[int] = Field(None, ge=1)
    soft_cap_enabled: Optional[bool] = None
    damping_steepness: Optional[float] = Field(None, ge=1.0, le=20.0)
    crowding_stress_mult: Optional[float] = Field(None, ge=0.0, le=1.0)
    resource_strain_mult: Optional[float] = Field(None, ge=0.0, le=2.0)
    boom_ramp_days: Optional[float] = Field(None, ge=0, le=100)
    boom_birth_floor: Optional[float] = Field(None, ge=0, le=1.0)
    boom_cooldown_mult: Optional[float] = Field(None, ge=1.0, le=10.0)
    boom_energy_mult: Optional[float] = Field(None, ge=1.0, le=10.0)
    initial_season_offset: Optional[int] = Field(None, ge=0, le=3)
    disease_enabled: Optional[bool] = None
    disease_outbreak_rate: Optional[float] = Field(None, ge=0, le=1)
    disease_rate: Optional[float] = Field(None, ge=0, le=1)
    disease_energy_drain: Optional[float] = Field(None, ge=0, le=10)
    disease_lethality: Optional[float] = Field(None, ge=0, le=1)

    # 3. Climate & Sky
    weather_enabled: Optional[bool] = None
    sleep_enabled: Optional[bool] = None
    day_length: Optional[int] = Field(None, ge=2, le=200000)
    season_length: Optional[int] = Field(None, ge=2, le=1000000)
    winter_food_mult: Optional[float] = Field(None, ge=0.1, le=2)
    night_sight_mult: Optional[float] = Field(None, ge=0.05, le=2)
    weather_change_rate: Optional[float] = Field(None, ge=0, le=1)
    weather_sickness_enabled: Optional[bool] = None
    chill_drain: Optional[float] = Field(None, ge=0, le=5)
    shelter_enabled: Optional[bool] = None
    exposure_drain: Optional[float] = Field(None, ge=0, le=10)
    house_capacity: Optional[int] = Field(None, ge=1, le=64)
    house_decay_ticks: Optional[int] = Field(None, ge=100, le=100000)
    rest_recovery_mult: Optional[float] = Field(None, ge=0, le=10)

    # 4. Society, Warfare & Trade
    territory_enabled: Optional[bool] = None
    territory_radius: Optional[float] = Field(None, ge=1, le=50)
    trespass_decay: Optional[float] = Field(None, ge=0, le=5)
    max_clans: Optional[int] = Field(None, ge=-1, le=64)
    totems_enabled: Optional[bool] = None
    succession_enabled: Optional[bool] = None
    communication_enabled: Optional[bool] = None
    knowledge_enabled: Optional[bool] = None
    schism_enabled: Optional[bool] = None
    schism_threshold: Optional[float] = Field(None, ge=0, le=1)
    war_enabled: Optional[bool] = None
    attack_damage: Optional[float] = Field(None, ge=0, le=1000)
    predation_enabled: Optional[bool] = None
    predator_ratio: Optional[float] = Field(None, ge=0, le=1)
    hunt_radius: Optional[float] = Field(None, ge=1, le=40)
    bite_damage: Optional[float] = Field(None, ge=0, le=1000)
    energy_from_prey: Optional[float] = Field(None, ge=0, le=1000)
    fear_radius: Optional[float] = Field(None, ge=1, le=40)
    coalitions_enabled: Optional[bool] = None
    coalition_threshold: Optional[int] = Field(None, ge=-100, le=100)
    leader_decisions_enabled: Optional[bool] = None
    resource_sharing_enabled: Optional[bool] = None
    larder_capacity: Optional[float] = Field(None, ge=0, le=5000)
    cannibalism_enabled: Optional[bool] = None
    eat_kin_enabled: Optional[bool] = None
    cannibalism_energy: Optional[float] = Field(None, ge=0, le=1000)

    # 5. Theology & Sacred Avatars
    theology_enabled: Optional[bool] = None
    tithe_rate: Optional[float] = Field(None, ge=0, le=1)
    temple_faith_cost: Optional[float] = Field(None, ge=0, le=100000)
    age_enabled: Optional[bool] = None
    age_length: Optional[int] = Field(None, ge=100, le=1000000)
    culture_enabled: Optional[bool] = None
    culture_spread_rate: Optional[float] = Field(None, ge=0, le=1)

    # 6. World Physics & Disasters
    rivers_enabled: Optional[bool] = None
    river_count: Optional[int] = Field(None, ge=0, le=8)
    relief_enabled: Optional[bool] = None
    structural_enabled: Optional[bool] = None
    earthquake_enabled: Optional[bool] = None
    earthquake_rate: Optional[float] = Field(None, ge=0, le=0.01)
    lightning_enabled: Optional[bool] = None
    lightning_strike_rate: Optional[float] = Field(None, ge=0, le=0.05)
    wildfire_enabled: Optional[bool] = None
    fire_rate: Optional[float] = Field(None, ge=0, le=0.05)
    disaster_enabled: Optional[bool] = None
    disaster_rate: Optional[float] = Field(None, ge=0, le=0.05)
    anomaly_count: Optional[int] = Field(None, ge=0, le=8)
    door_clearance: Optional[float] = Field(None, ge=1, le=5)
    house_min_size: Optional[float] = Field(None, ge=3, le=60)
    house_max_size: Optional[float] = Field(None, ge=3, le=80)
    # --- Additional Config fields for roundtrip tests ---
    aid_rate: Optional[float] = Field(None, ge=0, le=1)
    alarm_call_rate: Optional[float] = Field(None, ge=0, le=1)
    alignment_weight: Optional[float] = Field(None, ge=0, le=10)
    alliance_threshold: Optional[int] = Field(None, ge=-100, le=100)
    attack_radius: Optional[float] = Field(None, ge=0, le=10)
    banquets_enabled: Optional[bool] = None
    beast_ratio: Optional[float] = Field(None, ge=0, le=1)
    betrayal_enabled: Optional[bool] = None
    birth_energy_cost: Optional[float] = Field(None, ge=0, le=1000)
    bite_cooldown: Optional[int] = Field(None, ge=0, le=1000)
    cannibalism_hunger_ratio: Optional[float] = Field(None, ge=0, le=1)
    chill_rate: Optional[float] = Field(None, ge=0, le=10)
    chill_threshold: Optional[float] = Field(None, ge=0, le=1000)
    coalition_min_size: Optional[int] = Field(None, ge=1, le=100)
    cohesion_weight: Optional[float] = Field(None, ge=0, le=10)
    corpse_energy: Optional[float] = Field(None, ge=0, le=1000)
    corpse_ttl: Optional[int] = Field(None, ge=0, le=100000)
    corpses_enabled: Optional[bool] = None
    creature_density: Optional[float] = Field(None, ge=0, le=10)
    defection_enabled: Optional[bool] = None
    defense_weight: Optional[float] = Field(None, ge=0, le=10)
    desperate_perceive_mult: Optional[float] = Field(None, ge=1, le=10)
    desperate_speed_mult: Optional[float] = Field(None, ge=1, le=10)
    dialect_drift_enabled: Optional[bool] = None
    diet_strictness: Optional[float] = Field(None, ge=0, le=1)
    disease_radius: Optional[float] = Field(None, ge=0, le=100)
    eat_enemy_enabled: Optional[bool] = None
    energy_start: Optional[float] = Field(None, ge=0, le=1000)
    envoys_enabled: Optional[bool] = None
    exile_on_kin_eat: Optional[bool] = None
    fertile_food_bias: Optional[float] = Field(None, ge=0, le=10)
    fertile_patches: Optional[int] = Field(None, ge=-1, le=1000)
    fire_spread_rate: Optional[float] = Field(None, ge=0, le=10)
    flock_radius: Optional[float] = Field(None, ge=0, le=100)
    fog_mushroom_mult: Optional[float] = Field(None, ge=0, le=10)
    fog_sight_mult: Optional[float] = Field(None, ge=0, le=10)
    food_call_rate: Optional[float] = Field(None, ge=0, le=1)
    food_giveup_ticks: Optional[int] = Field(None, ge=0, le=100000)
    hearths_enabled: Optional[bool] = None
    height: Optional[float] = Field(None, ge=10, le=10000)
    help_call_enabled: Optional[bool] = None
    help_radius: Optional[float] = Field(None, ge=0, le=100)
    history_max: Optional[int] = Field(None, ge=0, le=1000000)
    house_claim_enabled: Optional[bool] = None
    house_density: Optional[float] = Field(None, ge=0, le=1)
    house_gap: Optional[float] = Field(None, ge=0, le=100)
    hungry_perceive_mult: Optional[float] = Field(None, ge=1, le=10)
    kin_stigma: Optional[float] = Field(None, ge=0, le=1000)
    knowledge_share_rate: Optional[float] = Field(None, ge=0, le=1)
    knowledge_ttl: Optional[int] = Field(None, ge=0, le=1000000)
    markets_enabled: Optional[bool] = None
    mate_energy_min: Optional[float] = Field(None, ge=0, le=1000)
    mate_radius: Optional[float] = Field(None, ge=0, le=100)
    nn_inference_hz: Optional[int] = Field(None, ge=1, le=1000)
    num_hexagons: Optional[int] = Field(None, ge=-1, le=100)
    num_houses: Optional[int] = Field(None, ge=-1, le=100)
    num_pentagons: Optional[int] = Field(None, ge=-1, le=100)
    num_priests: Optional[int] = Field(None, ge=-1, le=100)
    num_squares: Optional[int] = Field(None, ge=-1, le=100)
    num_triangles: Optional[int] = Field(None, ge=-1, le=100)
    num_women: Optional[int] = Field(None, ge=-1, le=100)
    omens_enabled: Optional[bool] = None
    omp_enabled: Optional[bool] = None
    omp_threshold: Optional[int] = Field(None, ge=0, le=10000)
    rain_growth_mult: Optional[float] = Field(None, ge=0, le=10)
    rain_speed_mult: Optional[float] = Field(None, ge=0, le=10)
    recovery_rate: Optional[float] = Field(None, ge=0, le=1)
    relation_drift_rate: Optional[float] = Field(None, ge=0, le=10)
    reproduction_cooldown: Optional[int] = Field(None, ge=0, le=100000)
    rivalry_threshold: Optional[int] = Field(None, ge=-100, le=100)
    rock_count: Optional[int] = Field(None, ge=-1, le=1000)
    rubble_blocking_enabled: Optional[bool] = None
    scent_enabled: Optional[bool] = None
    schism_min_pop: Optional[int] = Field(None, ge=1, le=1000)
    seed: Optional[int] = Field(None, ge=0)
    separation_weight: Optional[float] = Field(None, ge=0, le=10)
    signal_radius: Optional[float] = Field(None, ge=0, le=100)
    signal_speed: Optional[float] = Field(None, ge=0, le=100)
    sleep_energy_mult: Optional[float] = Field(None, ge=0, le=10)
    soil_depletion_enabled: Optional[bool] = None
    spawn_variance: Optional[float] = Field(None, ge=0, le=100)
    storm_plant_damage: Optional[float] = Field(None, ge=0, le=10)
    storm_wander_bonus: Optional[float] = Field(None, ge=0, le=10)
    tick_rate: Optional[float] = Field(None, ge=0.1, le=1000)
    trait_mutation_rate: Optional[float] = Field(None, ge=0, le=1)
    tribute_enabled: Optional[bool] = None
    vocalizations_enabled: Optional[bool] = None
    wander_turn: Optional[float] = Field(None, ge=0, le=10)
    wet_disease_mult: Optional[float] = Field(None, ge=0, le=10)
    width: Optional[float] = Field(None, ge=10, le=10000)

