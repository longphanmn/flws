"""Simulation constants — extracted from core.py L1–719 (BI-2)."""

from __future__ import annotations

import math
from functools import lru_cache

# Life-stage multipliers (speed, sight) — the young are small and dim-sighted,
# the elders slow. Fertility multiplier lives on Creature.FERTILITY_MULT.
STAGE_MULT = {
    "infant": (0.60, 0.60),
    "juvenile": (0.85, 0.85),
    "adult": (1.00, 1.00),
    "elder": (0.85, 0.90),
}

SEASONS = ("spring", "summer", "autumn", "winter")
# Winter starves the land; summer is plenty. Winter mult is now a god law (winter_food_mult).
SEASON_FOOD_MULT = {"spring": 1.0, "summer": 1.2, "autumn": 1.0, "winter": 0.5}
SPRING_BIRTH_MULT = 1.25
WINTER_DISEASE_MULT = 1.5

def _season_food_mult(season: str, winter_mult: float) -> float:
    if season == "winter":
        return winter_mult
    return SEASON_FOOD_MULT.get(season, 1.0)


def _smooth_season_food_mult(tick: int, season_length: int, winter_mult: float, offset: int = 0) -> float:
    """Astronomically continuous season food multiplier using solar declination curve."""
    if season_length <= 0:
        return 1.0
    if season_length < 60:
        season_idx = ((tick // season_length) + offset) % 4
        s_name = SEASONS[season_idx]
        return winter_mult if s_name == "winter" else SEASON_FOOD_MULT.get(s_name, 1.0)
    year_len = 4 * season_length
    current_tick = (tick + offset * season_length) % year_len
    theta = 2.0 * math.pi * (current_tick / float(year_len))
    solar_sin = math.sin(theta)
    if solar_sin >= 0.0:
        return 1.0 + solar_sin * (SEASON_FOOD_MULT.get("summer", 1.2) - 1.0)
    else:
        return 1.0 + solar_sin * (1.0 - winter_mult)


def _smooth_age_mult(tick: int, age_length: int, mult_dict: dict[str, float], window_ticks: int = 600) -> float:
    """Smoothly blends age multipliers across era boundaries over window_ticks."""
    if age_length <= 0:
        return 1.0
    if age_length < 100:
        idx = (tick // age_length) % len(AGES)
        return mult_dict.get(AGES[idx], 1.0)
    cur_idx = (tick // age_length) % len(AGES)
    cur_age = AGES[cur_idx]
    target_mult = mult_dict.get(cur_age, 1.0)
    age_tick = tick % age_length
    blend_window = min(window_ticks, age_length // 4)
    if blend_window > 0 and age_tick < blend_window:
        if tick < age_length:
            return target_mult
        prev_idx = (cur_idx - 1) % len(AGES)
        prev_age = AGES[prev_idx]
        prev_mult = mult_dict.get(prev_age, 1.0)
        t = age_tick / float(blend_window)
        # Cosine / smoothstep blend
        smooth_t = 0.5 * (1.0 - math.cos(math.pi * t))
        return prev_mult + smooth_t * (target_mult - prev_mult)
    return target_mult
WEATHER_STATES = ("clear", "rain", "fog", "storm")
AGES = ("Golden", "Ice", "Chaos", "Plague")
AGE_FOOD_MULT = {"Golden": 1.25, "Ice": 0.55, "Chaos": 0.95, "Plague": 0.9}
AGE_MUTATION_MULT = {"Golden": 0.9, "Ice": 1.1, "Chaos": 1.8, "Plague": 1.0}
AGE_DISEASE_MULT = {"Golden": 0.8, "Ice": 1.1, "Chaos": 1.0, "Plague": 1.8}
AGE_BIRTH_MULT = {"Golden": 1.3, "Ice": 0.85, "Chaos": 1.0, "Plague": 0.9}
AGE_CAP_MULT = {"Golden": 1.10, "Chaos": 0.95, "Plague": 0.75, "Ice": 0.55}

YIELD_RADIUS = 2.5  # lower castes step aside within this range

# §L shelter: reference floor area for the house_capacity law (8×8 hall) and maximum bed limit
HOUSE_REF_AREA = 64.0
HOUSE_MAX_BEDS = 16


# §AB politics pacing (per-tick chances; determinism via fixed iteration order)
COALITION_FORM_CHANCE = 0.003  # a leader founds a bloc this often
COALITION_JOIN_CHANCE = 0.01  # an unaligned clan petitions an existing bloc
LEADER_DECISION_CHANCE = 0.01  # a leader acts (war/peace/betrayal/tribute)
TRIBUTE_INTERVAL = 240  # ticks between vassal payments
DEFECT_CHANCE = 0.03  # unhappy member defects per tick
TREASON_RADIUS = 14.0  # false-knowledge seeding reach during betrayal
WAR_DECLARE_COOLDOWN = 1200  # one active feud per pair; no re-declaring inside this window

# §AC desperation cannibalism pacing
CANNIBAL_COOLDOWN = 120  # ticks between desperate kills
CANNIBAL_CORPSE_MULT = 0.5  # the body left after a cannibal feeds

# §AP Unified Theology — shrines beside the main house, dawn & dusk tithes,
# seasonal miracles, law resonance, holy synods and the rare 3D epiphany.
SHRINE_AURA_RADIUS = 10.0   # blessing aura around a level-1 shrine
TEMPLE_AURA_MULT = 3.0      # a temple extends the blessing across territory
TITHE_WINDOW = 0.02         # fraction of a day on either side of sunrise/sunset
BLESS_HEAL_RATE = 0.15      # health/tick the shrine's aura mends (costs faith)
BLESS_FAITH_COST = 0.02     # faith spent per mended member per tick
MIRACLE_FAITH_COST = 150.0  # faith burned per seasonal miracle
MIRACLE_FOOD = 6            # plants gifted by one miracle
SYNOD_INTERVAL = 3600       # crisis-age cadence for the Great Synod
SYNOD_RELATION_BOOST = 4    # every pair warms this much at a synod
EPIPHANY_PERIODS_GAP = 997  # hash modulus: an epiphany is a once-in-ages event
TRUCE_TICKS = 600           # synods and epiphanies still all strife this long

# §AT-4 H-0 — health is a real resource: regeneration demands a fed body,
# weakness slows every stride, and sickly creatures cannot beget children.
HEALTH_REGEN_MIN_ENERGY = 0.4  # fraction of energy_max: regen stalls below this
HEALTH_SELF_DRAIN_ENERGY = 0.2  # below this fraction the body cannibalizes itself
HEALTH_SELF_DRAIN_RATE = 0.05  # health lost per tick while self-cannibalizing
HEALTH_SPEED_TIERS = ((80.0, 0.95), (60.0, 0.85), (40.0, 0.70), (20.0, 0.50))
REPRO_MIN_HEALTH = 50.0  # sickly creatures cannot mate

# §AT-4 H-1 — damage variety: hunger gnaws, age withers, wounds linger, and
# what a body eats decides how well it mends.
EXHAUSTION_ENERGY_FRACTION = 0.20  # chronic-hunger floor
EXHAUSTION_TICKS = 30              # below the floor this long → health drain
EXHAUSTION_DRAIN = 0.08
ELDER_DECAY_RATE = 0.02            # passive health decay in old age
HEALTH_SIGHT_TIERS = ((30.0, 0.75), (60.0, 0.90))  # ascending threshold check
COMBAT_MIN_HEALTH = 30.0           # cannot initiate combat below this
FORAGE_MULT_HURT = 0.80            # harvest mult at health <60
FORAGE_MULT_WEAK = 0.50            # harvest mult at health <30
FOOD_HEAL_BONUS = {                # variant -> (+health/tick, for N ticks)
    "berry": (0.3, 20),
    "grain": (0.2, 30),
    "medicinal_herb": (0.8, 40),
}
REGEN_OUTDOOR_MULT = 0.5   # waking regen in the open
REGEN_INDOOR_MULT = 0.8    # sheltered but awake
WOUND_MIN_DAMAGE = 15.0    # hits above this leave a lingering wound
WOUND_TICKS_BASE = 50      # wounds linger 50–100 ticks
WOUND_SPEED_MULT = {1: 0.85, 2: 0.70}
WOUND_REGEN_DIV = {1: 2.0, 2: 4.0}

# §AT-4 H-2 — systems depth: untreated wounds fester, healthy kin dress them,
# morale bends behaviour long before the body fails, and scars outlive wounds.
WOUND_INFECTION_CHANCE = 0.02  # per-tick risk an untreated wound turns septic
WOUND_INFECTION_AFTER = 30     # ticks before an open wound can fester
DRESS_MIN_HEALTH = 70.0        # a helper must be healthy to dress wounds
DRESS_RADIUS = 3.0             # bandages are applied at arm's reach
MORALE_DEATH_WITNESS = 6.0     # morale lost watching a clan-mate die
MORALE_LEADER_DEATH = 15.0     # extra grief when the fallen one is the chief
MORALE_STARVE_DRAIN = 0.08     # prolonged starvation erodes the will
MORALE_BASE_RECOVER = 0.02     # hearts mend slowly on their own
MORALE_EAT_RESTORE = 12.0      # a meal lifts the spirit
MORALE_AURA_RECOVER = 0.05     # the leader's aura mends hearts slowly
MORALE_FEAST_RECOVER = 0.10    # festivals lift every heart in the clan
MORALE_RALLY_MIN = 60.0        # below this rally calls fall on deaf ears
MORALE_FORAGE_MIN = 40.0       # below this the body stops providing
MORALE_ABANDON = 20.0          # below this a body abandons its clan
MORALE_ABANDON_CHANCE = 0.02   # per-tick chance the broken walk away
OVERCROWD_DRAIN = 0.03         # health/tick per body beyond a house's beds
INFIRMARY_REGEN_MULT = 2.0     # plague-response bylaw doubles rest healing
SCAR_CHANCE = 0.5              # surviving a grievous wound may leave a mark
SCAR_SIGHT_MULT = 0.97         # permanent sight loss per scar
SCAR_SPEED_MULT = 0.98         # permanent stride loss per scar

# §AO — nocturnal perils: the Flatland night is an existential hazard, and
# shelter is the only sanctuary. Night is when the cold kills, the wolves
# prowl in packs, and the blind stumble onto a woman's sharp line.
NIGHT_CHILL_MULT = 3.0         # unsheltered night chill builds this much faster
EXTREME_NIGHT_EXPOSURE = 0.06  # extra energy/tick: winter nights & night storms
FROSTBITE_SPEED_MULT = 0.4     # numb limbs crawl (chill past the threshold)
FROSTBITE_DRAIN = 0.5          # HP/tick of deep frostbite; cause `exposure`
PREDATOR_NIGHT_SIGHT = 1.4     # +40% hunt radius in the dark
PREDATOR_NIGHT_SPEED = 1.2     # +20% stealth chase vs unsheltered prey
PACK_HOUR = 0.85               # past midnight beasts converge in packs
PACK_RADIUS = 18.0             # pack-mates share a kill within this range
DUSK_TOD = 0.62                # dusk rush: instinct screams "home" from here (§BE-E3 earlier alarm)
DUSK_SHELTER_URGE = 2.0        # overrides exploration before nightfall (§BE-E3 stronger urge)
HEARTH_SANCTUARY_HEAL = 1.5    # HP/tick beside a lit hearth
SPEAR_POKE_RADIUS = 3.0        # sentries poke outward from the doorway
SPEAR_POKE_DAMAGE = 22.0       # damage per poke at circling night beasts
PITCH_BLACK_SIGHT = 2.5        # outdoor night sight for non-predators
IMPALE_CHANCE = 0.08           # per-tick blind-collision risk in pitch dark
IMPALE_DAMAGE = 25.0           # a woman's line cuts deep (death: impalement)
MARAUDER_CHANCE = 0.03         # per-tick ambush roll for a dark isosceles
MARAUDER_AMBUSH_RADIUS = 6.0   # strike range against lone foragers
CAMPFIRE_LIGHT_RADIUS = 3.5    # a field campfire's circle of safety
CAMPFIRE_TTL_TO_DAWN = True    # campfires burn until dawn, no refuelling
CAMPFIRE_HEAT = 14.0           # warmth target near the flames
CAMPFIRE_KINDLE_CHANCE = 0.10  # per-tick kindling chance for stranded explorers
BED_OVERFLOW_BUILD_THRESHOLD = 3  # denied beds last night → build pressure

# §AR S-0 — senses interact: ripe plants smell through the dark, and
# desperation dulls fear.
FOOD_SCENT_RADIUS = 8.0  # mature plants are detectable by smell within this range

# §AR S-1..S-7 — senses that interact and suppress each other.
ALARM_HABITUATION_TICKS = 10   # same source this long → u_alarm drops to 0.3
ALARM_HABITUATED_U = 0.3
WARCRY_RADIUS_MULT = 2.0       # a predator pack's cry carries twice as far
ELDER_SIGHT_PENALTY = 0.9      # §AR S-2: old eyes dim a little further
VISION_CONE_COS = 0.0          # ±90° forward cone (cos 90°)
REAR_SIGHT_MULT = 0.5          # the rear 180° sees half as far
TRIANGLE_FALSE_ALARM = 0.30    # §AR S-2 Flatland canon: isosceles misread
TORCH_LIGHT_RADIUS = 6.0       # a torch restores night sight around its bearer
CAMOUFLAGE_RANGE = 2.5         # mature cover hides prey this close to plants
CAMOUFLAGE_HUNT_MULT = 0.8     # ...cutting predator range by a fifth
ORAL_LORE_CONF = 0.3           # §AR S-3: inherited memory arrives vague
WORKING_MEMORY_CAP = 6         # simultaneous facts a mind holds
MEMORY_CAP_STRESSED = 4        # hunger and wounds shrink the world
MEMORY_CAP_ELDER = 8           # a life of experience widens it
PRIEST_ORACLE_INTERVAL = 120   # cadence of the priest's clan briefing
PANIC_CONTAGION = 0.2          # §AR S-5: one runner spooks the flock
PRIEST_CALM_BONUS = 0.2        # ...a priest steadies them
PRIEST_CALM_RADIUS = 4.0       # the priest's calming presence range
RALLY_SIGNAL_TTL = 20
THERMAL_SEEK_UTILITY = 0.35    # §AR S-6: drift toward warmth when freezing
WEATHER_ANTICIPATION_TICKS = 3 # pentagon+ read the sky this fast
DISEASE_SCENT_RADIUS = 4.0     # the sick smell of sickness

# §AM Food & Agriculture — seed & furrow, granary & soil, feast & famine raid.
SEED_SKILL_MIN = 6.0        # farming XP before hands gather/sow seed
TEND_SKILL_MIN = 6.0        # farming XP before a creature tends crops
FARM_PLOTS_PER_CLAN = 3     # tilled plots ring each settlement
CULTIVATED_GROWTH_MULT = 2.0   # sown crops grow this much faster than weeds
CULTIVATED_YIELD_MULT = 2.5    # ...and feed this much better
IRRIGATED_GROWTH_MULT = 1.15   # furrows keep the soil moist through drought
TEND_REGRESS_TICKS = 60     # weeding rolls back the wither clock this far
WINTER_FROST_CHANCE = 0.004 # frost bites exposed (un-cultivated) winter crops
GRANARY_DEPOSIT_SHARE = 0.35   # fraction of a sated grain/berry harvest stored
GRANARY_WITHDRAW_RATE = 3.0    # energy/tick a starving member draws from store
BANQUET_FILL_FRACTION = 0.8   # feast fires when the granary is this full
BANQUET_COST_FRACTION = 0.25  # of the granary consumed by one feast
BANQUET_MIN_GAP = 1200        # ticks between banquets
BANQUET_FEAST_TICKS = 600     # morale window after a feast
BANQUET_FERTILITY_MULT = 1.3  # birth-rate boost while the feast lasts
SOIL_CELL = 25.0              # grid units per soil-fertility cell
SOIL_MIN, SOIL_MAX = 0.3, 1.6
SOIL_DEPLETION_PER_GROWTH = 0.01  # fertility burned per point of growth grown
COMPOST_INTERVAL = 900        # ticks between a farmer's compost rounds
COMPOST_NUTRIENT = 0.4        # soil fertility granted per compost heap
RAID_GRANARY_MAX = 40.0       # most a war party can haul from a rival granary
HOSPITALITY_GAP = 180         # min ticks between sacred-hospitality chronicles

# §AN Communication, language & diplomacy — every caste has a voice.
CHANT_CHANCE = 0.02           # priest liturgy per tick when idle-voiced
HUM_CHANCE = 0.05             # woman's peace-hum while moving
WARCHIRP_CHANCE = 0.15        # soldier's rallying signal on contact
GREET_CHANCE = 0.35           # tactile greeting on close vertex contact
GREET_TRUST = 2.0             # trust gained by touching vertices in peace
ELDER_TOUCH_XP = 0.1          # skill XP passed by an elder's blessing touch
ARTISAN_GIFT_ENERGY = 25.0    # a barter chime's gift from the basket
SCENT_TTL = 220               # forager trail markers fade after this long
DANGER_SCENT_TTL = 300        # death/ruin scent lingers longer
TRAIL_DROP_CHANCE = 0.06      # well-fed finder of rich food leaves a marker
SIGNALS_MAX = 400             # hard cap on live ripples (bounds memory)
ENVOY_MISSION_TICKS = 1200    # an emissary abandons a failed mission after this
ENVOY_RELATION_BOOST = 15     # a delivered peace treaty warms relations this much
MARKET_CHECK_INTERVAL = 480   # allied neighbours found trading posts this often
MARKET_BARTER_INTERVAL = 240  # barter cadence at a standing market
CARAVAN_INTERVAL = 2400       # wandering peddlers set out this often
OMEN_SIGNAL_TTL = 90          # prophetic ripples linger over the shrine
PREPARED_TICKS = 400          # worshippers heed the omen this long
STONE_CHIME_GAP = 90          # min ticks between warning chimes per clan
DIALECT_STEP = 0.02           # per-season drift quantum for isolated clans

# §AS L-0 — the leader is a single point of leverage: an aura when present,
# a crisis when dead.
LEADER_AURA_RADIUS = 15.0
LEADER_SIGHT_BONUS = 0.10     # +10% perceive inside the aura
LEADER_DECAY_MULT = 0.95      # −5% energy burn inside the aura
LEADERLESS_DECAY_MULT = 1.05  # +5% energy burn with no living leader
LEADER_CALM = 1.0             # fear radius shaved inside the aura (braver kin)
LEADERLESS_FEAR = 1.0         # fear radius added when leaderless
LEADERLESS_GAIN_MULT = 0.85   # −15% food energy gain while leaderless
LEADER_SHOCK_ENERGY = 10.0    # instant loss at the leader's death
LEADER_SHOCK_LARDER_MULT = 0.8  # looting: larder loses 20%
LEADER_SHOCK_PANIC_TICKS = 20
LEADER_SHOCK_U_FLEE = 0.3    # flee-urge spike while the panic window lasts
LEADERLESS_CAUTIOUS_CHANCE = 0.01  # per-tick personality drift toward cautious

# §AS L-1..L-6 — the leader as commander, provider, diplomat and symbol.
LEADERLESS_WAR_MULT = 0.5     # an army without a general fights at half strength
BODYGUARD_U_HELP = 1.5        # soldiers hold their chief above all else
COMBAT_BOOST_TICKS = 30       # a rally sharpens blades this long
COMBAT_RALLY_BONUS = 0.3      # effective combat skill while rallied
ASSASSIN_ATTACK_BONUS = 0.2   # bold/junta blades aim for the throat
REGICIDE_RELATION_HIT = -60   # killing chiefs unprovoked: "they murder chiefs"
REGICIDE_SYMPATHY = 40        # ...and mourners rally to the victim's banner
TALK_RADIUS = 6.0             # peace needs two chiefs face to face
RETREAT_HEALTH_FRAC = 0.30    # a bleeding general sounds the retreat
RETREAT_SHELTER_URGE = 2.0    # kin drop everything and run home
RITUAL_INTERVAL = 120         # the chief's rite at the great hall
RITUAL_TOTEM_MULT = 2.0       # the totem answers with doubled power
RITUAL_TICKS = 30             # ...for this long after each rite
HARVEST_ORDER_SEASON = "autumn"  # the chief calls the stores in before winter
ABSENT_TOTEM_MULT = 0.5       # no chief at the hall: half-strength totem
REPUBLIC_PEACE_MULT = 1.2     # councils negotiate hardest
REPUBLIC_LARDER_EFF = 1.25    # ...and portion out stores fairest
MONARCHY_TRIBUTE_MULT = 2.0   # kingdoms extract double protection money
MONARCHY_AURA_MULT = 1.5      # the crown's aura reaches farther
MONARCHY_INBREEDING = 1.25    # thin royal blood mutates more easily
THEOCRACY_RITUAL_POWER = 2.0  # faith doubles every rite
JUNTA_COMBAT_SKILL = 1.5      # soldiers of the junta live for war
JUNTA_LARDER_EFF = 0.75       # ...but stores are portioned wastefully
JUNTA_ASSASSINATION_MULT = 2.0
CONTESTED_SUCCESSION_CHANCE = 0.15  # two equal heirs may split the clan
TOTEM_CHANGE_CHANCE = 0.10    # a new chief may call a new avatar
LAW_INTERPRET_TICKS = 20      # the chief explains God's law for this long

# §AQ PH-0 — foundational axioms: energy is the universal currency.
# Sunlight is the world's only income; every body pays upkeep in proportion
# to its geometric complexity (Flatland: more sides, more ceremony).
METABOLIC_COST = {
    "Woman": 1.5,
    "Soldier": 1.0,   # triangles
    "Artisan": 1.0,   # equilateral triangles
    "Gentleman": 1.1,  # squares
    "Professional": 1.2,  # pentagons
    "Noble": 1.3,     # hexagons and beyond
    "Priest": 1.5,    # near-circles burn energy maintaining the aura
    "Predator": 1.0,
    "Herbivore": 0.9,
}
DEFAULT_METABOLIC_COST = 1.0
HEALING_ENERGY_COST = 0.5  # energy burned per point of health regenerated

# §AQ PH-1 — thermodynamics: a coarse heat field over the land, bodies that
# drift toward it, and houses that keep the world outside at arm's length.
TEMP_CELL = 25.0          # grid units per temperature cell
TEMP_RATE = 0.08          # per-tick relaxation of a cell toward its target
SEASON_BASE_TEMP = {"spring": 12.0, "summer": 24.0, "autumn": 8.0, "winter": -4.0}
DAY_HEAT_AMPLITUDE = 5.0  # extra degrees at noon (negative in the deep night)
FIRE_HEAT = 60.0          # target temp near open flame
FIRE_HEAT_RADIUS = 8.0
BODY_TEMP_DRIFT = 0.06    # fraction of the gap closed per tick
HYPOTHERMIA_TEMP = 2.0    # below this the body builds chill (§R)
CHILL_FROM_COLD_RATE = 0.06
HYPERTHERMIA_TEMP = 36.0  # above this the body cooks
HYPERTHERMIA_DRAIN = 0.15  # health per degree of excess per tick

# §AQ PH-7 — metabolic extremes: a frozen, starving body shuts down to
# near-nothing; sustained cooking drops the body where it stands.
TORPOR_ENERGY_RATIO = 0.10  # energy fraction below which the cold can claim a body
TORPOR_BURN_MULT = 0.05     # torpid metabolism: 5% of the awake burn
HEAT_STROKE_TICKS = 60      # ticks of cooking before the body gives out
HEAT_STROKE_HYST = 4.0      # degrees of cooling before the body rises again

# §AQ PH-8 — seismic & wave physics: the ground sometimes moves, the tall
# castes feel it coming, and no news travels faster than the air carries it.
QUAKE_WARN_TICKS = 3        # high castes feel the deep hum this long ahead
QUAKE_WARN_RADIUS = 30.0    # ...within this range of the coming epicentre
QUAKE_DISPLACEMENT = 3.5    # max shove per body at the epicentre (mag 8)
QUAKE_DAMAGE = 16.0         # health lost at the epicentre, fading outward
QUAKE_ROCK_CRACK_CHANCE = 0.35  # a rock inside the blast may split open
QUAKE_ROCK_SPAWN_CHANCE = 0.15  # ...or the ground may thrust new stone up
# §AQ PH-9 — electrostatics & bio-electric fields
LIGHTNING_KILL_RADIUS = 1.6  # instant death under the strike
LIGHTNING_ROCK_TTL = 240     # a fused, electrostatic rock lingers briefly
LIGHTNING_BOLT_TTL = 6       # the visible bolt fades fast
PRIEST_CALM = 1.5            # fear-radius soothed near a living priest
PRIEST_AURA_RADIUS = 6.0
TOTEM_RESONANCE_BONUS = 0.25  # aura power per same-totem allied shrine nearby
TOTEM_RESONANCE_CAP = 2.0
TOTEM_RIVAL_DIM = 0.75       # rival shrines too close weaken both auras
TOTEM_RIVAL_RADIUS = 22.0
ANOMALY_TOTEM_BONUS = 1.25   # shrines beside an anomaly draw extra power
# §AQ PH-10 — cosmological & metaphysical
LAW_WAVE_TICKS = 30          # the law-change shimmer sweeps the map this long
LAW_WAVE_BAND = 4.0          # half-width of the felt wavefront
ANOMALY_RADIUS = 9.0         # a zone of altered physics
ANOMALY_DISCOVER_SKILL = 3.0  # foraging skill needed to notice one
ANOMALY_GROWTH_MULT = 1.6    # fertile anomaly
ANOMALY_HEAVY_SPEED = 0.7    # heavy anomaly drags the stride
ANOMALY_CALM_DECAY = 0.8     # calm anomaly eases the burn
SHADOW_LENGTH = 1.4          # a roof shadows the ground this far × size
SHADOW_GROWTH_MULT = 0.7     # shade-starved plants grow slower
SUN_EDGE_BAND = 18.0         # dawn/dusk illumination sweeps in from the edges
SUN_EDGE_GROWTH_MULT = 1.15
HOUSE_COMFORT_TEMP = 18.0  # what insulation pulls the indoors toward
# §AQ PH-6 — material physics: four build materials with distinct stats.
MATERIAL_STATS = {
    #            durability (structural HP)   insulation
    "straw": {"durability": 120.0, "insulation": 0.15},
    "wood":  {"durability": 260.0, "insulation": 0.35},
    "stone": {"durability": 480.0, "insulation": 0.55},
    "clay":  {"durability": 320.0, "insulation": 0.70},  # riverbank brick
}
INSULATION_BY_MATERIAL = {m: s["insulation"] for m, s in MATERIAL_STATS.items()}
HOUSE_REF_SIDE = 8.0      # a reference hall; bigger houses shed heat faster
STORM_WEAR = 0.15         # structural HP lost per storm tick
FLOOD_WEAR = 0.60         # structural HP lost per flood tick in the water
REPAIR_RATE = 1.5         # HP a builder restores per tick of masonry work
RUBBLE_RADIUS_FRAC = 0.35  # a collapsed ruin blocks this fraction of its floor

# §AQ PH-2 — the wind: a vector over the land that bends flame and seed.
WIND_CALM_SPEED = 0.25
WIND_RAIN_SPEED = 0.55
WIND_STORM_SPEED = 1.0    # magnitude scales with storm severity
WIND_RATE = 0.05          # relaxation toward the weather's target speed
# prevailing direction by season (radians); re-rolls land near these
WIND_SEASON_BIAS = {"spring": 0.0, "summer": 1.3, "autumn": 2.5, "winter": 4.0}
WIND_FIRE_MULT = 0.8      # extra spread chance per unit of tailwind speed
# §AQ PH-2: the wind carries more than flame — seeds and scent ride it too.
WIND_SEED_BIAS = 0.65     # how strongly seed drift bends downwind (× speed)
SOUND_WIND_MULT = 0.4     # calls carry this much farther to DOWNWIND listeners
# (scent kept gentle — a strong upwind nose destabilises predator/prey cycles)
WIND_SCENT_MULT = 0.35    # upwind reach bonus (prey full, predators half)

# §AQ PH-1 — hearths & radiant fire: warmth is infrastructure, and open
# flame is a double-edged tool (it warms the winter roof AND cooks the unwary).
HEARTH_COMFORT_TEMP = 26.0  # a lit hearth pulls the indoors toward this
HEARTH_PULL = 0.6           # strength of that pull (× size_factor)
HEARTH_FUEL_PER_ENERGY = 60.0  # ticks of burn bought per larder unit
HEARTH_FUEL_MAX = 1200.0    # the woodpile caps out here
HEARTH_BURN_RATE = 1.0      # fuel ticks consumed per tick while lit
HEARTH_REFUEL_INTERVAL = 10  # pacing: kin top up the hearth every N ticks
HEARTH_REFUEL_CHUNK = 0.25  # larder units per top-up
FIRE_SCALD_RADIUS = 4.0     # radiant scalding beyond the flame core
FIRE_SCALD_DAMAGE = 2.2     # health/tick at the flame's edge, fading to zero

# §AQ PH-5 — ecological physics: roots contest the soil, and plants help
# and hinder their neighbours (mushrooms fruit on decay, herbs shelter in
# berry thickets, toxins stunt everything near).
ROOT_COMPETITION = 0.45     # growth divisor per mature neighbour
SYMBIOSIS_RADIUS = 3.5      # root/reach range for neighbour effects
MUSHROOM_CORPSE_MULT = 1.6  # mushrooms fruit where things die
HERB_BERRY_MULT = 1.35      # medicinal herbs thrive beside berries
POISON_SUPPRESS = 0.55      # poisonous plants stunt their neighbours

# §AQ PH-3 — fluid dynamics: rivers are horizontal 1D channels across the map
# (the Planiverse constraint — water can only flow east or west). They cost
# energy to ford, sweep the weak downstream, flood in the rain and leave silt.
RIVER_BASE_HW = 4.0         # calm half-width of a channel band
RIVER_FORD_COST = 0.06      # extra energy/tick while wading
RIVER_SPEED_MULT = 0.6      # wading slows the body
RIVER_SWEEP_SPEED = 0.4     # displacement downstream/tick for the weak
RIVER_SWEEP_HEALTH = 30.0   # below this HP (or any infant) the current wins
RIVER_RAIN_RATE = 0.0035    # water level gained per tick of rain (storm ×1.5)
RIVER_DRY_RATE = 0.0012     # evaporation per tick
RIVER_FLOOD_TICKS = 300     # a flood lasts this long once triggered
RIVER_FLOOD_GROW = 0.05     # per-tick approach to the flooded half-width
RIVER_FLOOD_EBB = 0.02      # per-tick return to the calm channel
RIVER_FLOOD_HW_MULT = 2.2   # flooded half-width multiplier
RIVER_SILT_TICKS = 600      # post-flood enrichment window on the banks
RIVER_SILT_RADIUS = 6.0     # banks beyond the band that catch the silt
RIVER_SILT_MULT = 1.5       # plant growth bonus on fresh silt
RIVER_DROWN_DAMAGE = 1.5    # health/tick in floodwater; foraging skill softens
BRIDGE_HALF_WIDTH = 1.5     # a plank crosses dry within this x-range of its post
BRIDGE_HP = 2400            # ticks a plank bridge lasts without repair
DAM_HP = 3600               # ticks a dam holds before rotting
DAM_STRESS_DAMAGE = 30      # masonry lost per flood tick under pressure
DAM_FLASH_SPIKE = 1.8       # flash-flood half-width spike on dam failure

# §AQ PH-4 — gravity & terrain topology: a smooth height field bends every
# journey (uphill bleeds energy, downhill runs free), sharp drops are cliffs
# you can fall off, and feet pack the earth into roads that choke plant life.
ELEV_CELL = 25.0            # grid units per elevation sample
ELEV_MAX_HEIGHT = 60.0      # world-units between the lowest and highest ground
SLOPE_ENERGY_COST = 0.05    # extra energy/tick per unit of uphill grade
SLOPE_SPEED_MULT = 0.35     # speed lost at the steepest climb
CLIFF_DROP_UNITS = 18.0     # a terraced cell-boundary drop this steep is a cliff (raised from 14 to cut 22%->~8% edges)
FALL_DAMAGE_PER_UNIT = 0.85  # health lost per unit fallen past the threshold (tuned to keep 60-unit plateau lethal)
FALL_COOLDOWN_TICKS = 40     # grace after a fall — no further cliff damage while stunned
TRAFFIC_DECAY = 0.995       # per-tick fade of packed earth
TRAFFIC_DECAY_STAGGERED = TRAFFIC_DECAY ** 10  # §AU O-2: applied every 10th tick
TRAFFIC_PER_PASS = 1.0      # traffic earned per body-tick on a cell
ROAD_SPEED_PER_TRAFFIC = 0.03  # speed bonus per traffic level (packed earth)
ROAD_SPEED_CAP = 0.30       # ...capped here
TRAFFIC_PLANT_BLOCK = 6.0   # traffic above this halts plant growth entirely
AVALANCHE_SLOPE = 0.5       # grade that can slide in the rain
AVALANCHE_CHANCE = 0.002    # per creature per rainy tick on such a slope

# §AE food decay — nothing lasts forever: variant lifespan multipliers (§AM)
FOOD_LIFESPAN_MULT = {
    "grass": 1.0,
    "grain": 2.5,
    "berry": 1.5,
    "medicinal_herb": 1.2,
    "mushroom": 0.4,
    "poisonous": 3.0,
}
WILT_FRACTION = 0.8  # wilting (render fade) begins at this fraction of lifespan
WITHER_NUTRIENT_MULT = 0.5  # a withered plant fertilises at half a corpse's worth

# §H Plants & the nutrient cycle
SPREAD_RADIUS = 6.0  # mature plants seed new ground within this range
NUTRIENT_RADIUS = 10.0  # a fully decayed corpse fertilises plants within this range
NUTRIENT_BOOST = 0.5  # base growth granted by a decayed corpse (× nutrient_cycle_rate)
SPROUT_GROWTH = 0.15  # every newly spawned plant starts here

# §O Biodiversity — plant variants (§O, §AM)
VARIANT_ENERGY = {
    "grass": 32.0,
    "grain": 45.0,
    "berry": 48.0,
    "medicinal_herb": 18.0,
    "mushroom": 24.0,
    "poisonous": 8.0,
}
VARIANT_HEALTH = {
    "grass": 0.0,
    "grain": 2.0,
    "berry": 1.0,
    "medicinal_herb": 30.0,
    "mushroom": 0.0,
    "poisonous": -30.0,
}
VARIANT_GROWTH_MULT = {
    "grass": 1.0,
    "grain": 0.85,
    "berry": 0.65,
    "medicinal_herb": 0.70,
    "mushroom": 0.85,
    "poisonous": 0.60,
}
# seasonal rhythms: grain thrives summer/autumn, berry peaks autumn, herb thrives spring, mushrooms tolerate winter
VARIANT_SEASON_MULT = {
    "grass": {"spring": 1.05, "summer": 1.15, "autumn": 1.00, "winter": 0.45},
    "grain": {"spring": 0.90, "summer": 1.40, "autumn": 1.25, "winter": 0.15},
    "berry": {"spring": 0.50, "summer": 0.80, "autumn": 1.90, "winter": 0.25},
    "medicinal_herb": {"spring": 1.35, "summer": 1.10, "autumn": 0.65, "winter": 0.00},
    "mushroom": {"spring": 1.00, "summer": 0.60, "autumn": 1.35, "winter": 1.10},
    "poisonous": {"spring": 1.00, "summer": 1.00, "autumn": 1.00, "winter": 1.00},
}



# Creature Evolution: Personality Archetypes & Metabolism
PERSONALITIES = ("brave", "cautious", "altruistic", "greedy", "explorer", "builder")
STAGE_ENERGY_MULT = {"infant": 0.45, "juvenile": 0.75, "adult": 1.0, "elder": 0.85}

# Clan crest colors, assigned round-robin as clans are founded.
CLAN_COLORS = (
    "#ffd166", "#06d6a0", "#118ab2", "#ef476f",
    "#c77dff", "#f4a261", "#90be6d", "#e0aaff",
)

# Procedural clan names — seeded adjective + noun table (§P)
CLAN_ADJECTIVES = (
    "Ash", "Stone", "Long", "Silent", "Red", "Grey", "White", "Black", "Bright", "Cold",
    "Wild", "High", "Low", "Dawn", "Dusk", "River", "Mountain", "Forest", "Sun", "Moon",
    "Star", "Wind", "Iron", "Bronze", "Golden", "Silver", "Shadow", "Storm", "Fire", "Ice",
    "Ember", "Frost", "Thorn", "Hollow", "Grim", "Bold", "Swift", "Keen",
)
CLAN_NOUNS = (
    "Wolves", "Hawks", "Shadows", "Blades", "Stewards", "Wardens", "Keepers", "Hunters",
    "Striders", "Sentinels", "Weavers", "Masons", "Reavers", "Echoes", "Thorns", "Flames",
    "Stones", "Winds", "Tides", "Crowns", "Spears", "Shields", "Eyes", "Hands", "Voices",
    "Wings", "Fangs", "Roots", "Branches", "Stars", "Sands", "Waters", "Fires",
)

# §AP Phase A — totems are no longer animals: each clan bears one of the
# eight Sacred Avatars of the Sphere, a 2D projection of the One True God,
# and with it a distinct divine aspect (buff).
AVATARS = (
    "Radiant Circle",       # ⭕ God's Abundance
    "Celestial Strike",     # ⚡ God's Wrath & Justice
    "All-Seeing Vertex",    # 👁️ God's Omniscience
    "Indomitable Monolith", # 🛡️ God's Permanence
    "Sacred Spiral",        # 🌿 God's Renewal
    "Cosmic Scales",        # ⚖️ God's Equilibrium
    "Dimensional Rift",     # 🌀 God's Ascent
    "Eternal Hearth",       # 🕯️ God's Sanctuary
)
# Buff vocabulary (all optional keys, consumed generically via _totem_stat):
#   speed        additive speed multiplier when hunting/fleeing
#   hunt_radius  flat bonus to predator sight
#   harvest      fractional harvest bonus on plants (×1+h) and corpses (×1+0.4h)
#   sight        fractional perceive-radius bonus (×1+s)
#   defense      fractional damage reduction; sheltered healing scales ×(1+d)
#   health       flat health gift at birth
#   birth        fractional fertility bonus for the mother's clan
#   damage       fractional combat-damage bonus for the attacker (Strike)
#   clarity      fraction of the night-sight penalty recovered (Vertex)
#   cold         fraction of chill build resisted (Monolith cold immunity)
#   medicine     herb potency ×(1+m) (Spiral)
#   recovery     disease recovery chance ×(1+r) (Spiral)
#   compost      corpse nutrients near the shrine ×(1+c) (Spiral composting)
#   peace        leader sues for peace harder; war hand stays sheathed (Scales)
#   lawful       kin-eating is refused even while starving (Scales low crime)
#   promote      Isosceles angle rises faster per generation (Rift ascent)
#   mutate       child mutation chance ×(1+m) — adaptability (Rift)
#   lore         elder oral-lore XP transfer ×(1+l) (Rift elder lore)
#   calm         fear radius shaved at night (Hearth nocturnal calmness)
TOTEM_BUFF = {
    "Radiant Circle": {"harvest": 0.30, "birth": 0.20},
    "Celestial Strike": {"damage": 0.25, "speed": 0.06, "hunt_radius": 2.0},
    "All-Seeing Vertex": {"sight": 0.40, "clarity": 1.0},
    "Indomitable Monolith": {"defense": 0.30, "cold": 0.40, "health": 15.0},
    "Sacred Spiral": {"medicine": 1.0, "recovery": 1.0, "compost": 0.5},
    "Cosmic Scales": {"peace": 1.0, "lawful": 1.0},
    "Dimensional Rift": {"promote": 1.0, "mutate": 1.0, "lore": 1.0},
    "Eternal Hearth": {"calm": 1.5, "hearth": 1.0},
}
# Doctrinal kinship: complementary aspects sympathise (§AP holy alliances)
AVATAR_ALLIES = {
    "Radiant Circle": "Sacred Spiral",        # abundance ↔ renewal
    "Celestial Strike": "All-Seeing Vertex",  # wrath ↔ omniscience
    "Indomitable Monolith": "Eternal Hearth", # permanence ↔ sanctuary
    "Cosmic Scales": "Dimensional Rift",      # equilibrium ↔ ascent
}
# Sermon dogma — how each avatar interprets God's law changes (§AP Phase C)
AVATAR_DOGMA = {
    "Radiant Circle": "God's Abundance flows through the law you have set",
    "Celestial Strike": "God's Wrath strikes where the law now points",
    "All-Seeing Vertex": "the All-Seeing Vertex has watched this law take shape",
    "Indomitable Monolith": "God's Permanence sets this law in stone",
    "Sacred Spiral": "God's Renewal turns all things toward this law",
    "Cosmic Scales": "the Cosmic Scales weigh the world and find this law just",
    "Dimensional Rift": "through the Rift, God's Ascent carries us along this law",
    "Eternal Hearth": "the Eternal Hearth warms all who keep this law",
}
# Avatar biases the clan's starting specialization drift (§P specialization)
TOTEM_SPEC = {
    "Radiant Circle": {"warrior": 0.20, "farmer": 0.60, "scavenger": 0.20},
    "Celestial Strike": {"warrior": 0.55, "farmer": 0.20, "scavenger": 0.25},
    "All-Seeing Vertex": {"warrior": 0.25, "farmer": 0.25, "scavenger": 0.50},
    "Indomitable Monolith": {"warrior": 0.45, "farmer": 0.25, "scavenger": 0.30},
    "Sacred Spiral": {"warrior": 0.15, "farmer": 0.45, "scavenger": 0.40},
    "Cosmic Scales": {"warrior": 0.30, "farmer": 0.35, "scavenger": 0.35},
    "Dimensional Rift": {"warrior": 0.25, "farmer": 0.30, "scavenger": 0.45},
    "Eternal Hearth": {"warrior": 0.35, "farmer": 0.40, "scavenger": 0.25},
}

# §AM E.1 — geometric gastronomy: each caste keeps a table of its own.
# Priests and nobles demand refined grain and fruit; soldiers crave meat.
CASTE_DIET_WEIGHTS: dict[str, dict[str, float]] = {
    # variant -> effective-distance multiplier (lower = more desirable)
    "Priest": {"grain": 0.5, "berry": 0.5, "medicinal_herb": 0.5},
    "Noble": {"grain": 0.5, "berry": 0.6},
    "Soldier": {},       # soldiers favour meat — handled via corpse weighting
    "Artisan": {"grain": 0.8},
}

# Personal identity — seeded adjective+noun table (§Q), deterministic id+seed
PERSONAL_FIRSTS = (
    "Alen", "Bran", "Cora", "Dell", "Ember", "Finn", "Galen", "Hala", "Iris", "Joren",
    "Kira", "Lyss", "Maren", "Nora", "Orin", "Pella", "Quill", "Rhea", "Sable", "Taryn",
    "Uri", "Vessa", "Wren", "Xara", "Yara", "Zane", "Aric", "Brielle", "Cade", "Dara",
    "Eldric", "Fiora", "Gideon", "Hessa", "Ivor", "Jessa", "Kell", "Lina", "Mira", "Nessa",
)
PERSONAL_LASTS = (
    "Ash", "Stone", "Hollow", "Quill", "Grey", "Lark", "Vale", "Thorn", "Ember", "Wren",
    "Frost", "Dusk", "Star", "River", "Shadow", "Flame", "Wind", "Haven", "Moor", "Glen",
    "Ridge", "Brook", "Hearth", "Sable", "Wisp", "Bramble", "Harrow", "Tide", "Dell", "Echo",
)
GLYPH_TABLE = ("◈", "⬡", "⬢", "◉", "⬣", "⟡", "✦", "◆", "▲", "●", "✕", "∆", "◐", "◑", "⬔", "⬕", "⟐", "⧫")


def _clan_sig(info: dict) -> tuple:
    """Broadcast signature of a clan's wire-relevant state (AA delta tracking).

    Faith is bucketed: it drifts by fractions every tick (blessings, tithes),
    and an exact comparison would re-send the full clan dict each frame —
    a 25-point step is plenty for the shrine glow and clan panel.
    """
    return (
        info.get("name"), info.get("color"), info.get("totem"),
        info.get("culture"), info.get("leader_id"), info.get("main_house_id"),
        info.get("tribute_to"),
        round(float(info.get("faith", 0.0)) / 25.0), int(info.get("shrine_level", 0)),
        round(float(info.get("granary", 0.0)) / 25.0),  # §AM granary fill (bucketed)
        round(float(info.get("dialect", 0.0)) * 20.0) / 20.0,  # §AN dialect drift
        int(info.get("war_wins", 0)), int(info.get("war_losses", 0)),
    )


@lru_cache(maxsize=4096)
def personal_name_for(entity_id: int, seed: int, generation: int = 0) -> str:
    """Seeded deterministic personal name — god's ledger, never RNG."""
    a = PERSONAL_FIRSTS[(entity_id * 37 + seed) % len(PERSONAL_FIRSTS)]
    b = PERSONAL_LASTS[(entity_id * 73 + seed + generation * 101) % len(PERSONAL_LASTS)]
    return f"{a} {b}"


@lru_cache(maxsize=4096)
def glyph_for(entity_id: int, seed: int, generation: int = 0) -> str:
    return GLYPH_TABLE[(entity_id * 101 + seed + generation * 17) % len(GLYPH_TABLE)]


@lru_cache(maxsize=4096)
def variation_for(entity_id: int, seed: int) -> dict:
    """Subtle per-creature jitter — cosmetic only, never touches RNG."""
    hue = ((entity_id * 9973 + seed) % 241) / 241 * 24 - 12  # -12..+12 deg
    scale = 0.96 + ((entity_id * 7919 + seed) % 109) / 109 * 0.08  # 0.96..1.04
    angle = ((entity_id * 1307 + seed) % 31) / 31 * 0.12 - 0.06  # -0.06..+0.06 rad
    return {"hue_shift": round(hue, 2), "scale_jitter": round(scale, 3), "angle_jitter": round(angle, 3)}

TRAITS = ("greedy", "peaceful", "paranoid", "bold")
TRAIT_GLYPH = {"greedy": "⬔", "peaceful": "◯", "paranoid": "⬥", "bold": "▲"}
CULTURE_ADJECTIVES = ("Ashen", "Ember", "Hollow", "Stone", "River", "Sky", "Thorn", "Iron")
CULTURE_NOUNS = ("Rite", "Way", "Path", "Creed", "Tradition", "Lore", "Custody", "Bond")


