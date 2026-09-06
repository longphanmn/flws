"""Entity model: Flatland creatures (social castes) and static objects."""

from dataclasses import dataclass, field

# Polygons with at least this many sides are treated as Circles (priests).
PRIEST_SIDES = 24

# Body radius (grid units) per caste. Houses size their doorway from these.
RADIUS_BY_CASTE = {
    "Woman": 0.9,
    "Soldier": 1.05,
    "Gentleman": 1.15,
    "Professional": 1.25,
    "Noble": 1.35,
    "Priest": 1.45,
    "Predator": 1.6,
    "Herbivore": 1.0,
}
DEFAULT_RADIUS = 1.2


@dataclass(frozen=True)
class CasteTraits:
    """The social order of Flatland, expressed as natural law.

    - lifespan: ticks of natural life (at 10 ticks/s: 4800 = 8 minutes)
    - speed: grid units per tick
    - sight_mult: "Sight Recognition" — higher castes perceive farther,
      aided by Fog; women see least
    - fertility: relative reproductive rate (used by §B reproduction;
      Nature's Law: development accelerates while fertility declines)
    """

    lifespan: float
    speed: float
    sight_mult: float = 1.0
    fertility: float = 1.0


CASTE_TRAITS = {
    "Woman": CasteTraits(lifespan=4800, speed=0.75, sight_mult=0.80, fertility=1.20),
    "Soldier": CasteTraits(lifespan=5400, speed=0.85, sight_mult=0.90, fertility=1.10),
    # Equilateral triangle — an Isosceles who reached 60° and became a Regular.
    "Artisan": CasteTraits(lifespan=5700, speed=0.70, sight_mult=0.95, fertility=1.05),
    "Gentleman": CasteTraits(lifespan=6000, speed=0.55, sight_mult=1.00, fertility=1.00),
    "Professional": CasteTraits(lifespan=6600, speed=0.50, sight_mult=1.10, fertility=0.90),
    "Noble": CasteTraits(lifespan=7200, speed=0.45, sight_mult=1.20, fertility=0.80),
    # Priests: longest-lived, sharpest-sighted, nearly sterile (Nature's Law).
    "Priest": CasteTraits(lifespan=9000, speed=0.35, sight_mult=1.35, fertility=0.50),
    "Predator": CasteTraits(lifespan=6600, speed=0.95, sight_mult=1.10, fertility=0.90),
    "Herbivore": CasteTraits(lifespan=5200, speed=0.65, sight_mult=1.00, fertility=1.00),
}
DEFAULT_TRAITS = CasteTraits(lifespan=6000, speed=0.60)

# §AT-4 H-1: bodies differ — triangles are built for violence, lines survive,
# pentagons are delicate. Max health pools by caste (health still starts at 100;
# pools above 100 allow over-healing, pools below clamp at birth).
CASTE_MAX_HP = {
    "Soldier": 130,
    "Artisan": 130,
    "Woman": 110,
    "Gentleman": 100,
    "Professional": 90,
    "Noble": 120,
    "Priest": 90,
    "Predator": 120,
    "Herbivore": 100,
}
DEFAULT_MAX_HP = 100


def max_hp_for(caste: str) -> float:
    return float(CASTE_MAX_HP.get(caste, DEFAULT_MAX_HP))


def traits_for(caste: str) -> CasteTraits:
    return CASTE_TRAITS.get(caste, DEFAULT_TRAITS)


# Social ladder for yielding: the lowly give way to their betters.
YIELD_RANK = {
    "Woman": 0,
    "Soldier": 1,
    "Artisan": 2,
    "Gentleman": 3,
    "Professional": 4,
    "Noble": 5,
    "Priest": 6,
    "Predator": 7,
    "Herbivore": 1,
}


def caste_name(sides: int, shape: str, iso_angle: float = 60.0) -> str:
    """Map a creature's geometry to its Flatland social caste."""
    if shape == "line":
        return "Woman"
    if sides < 3:
        return "Irregular"
    if sides == 3:
        # Isosceles soldiers rise to equilateral Artisans at 60 degrees.
        return "Artisan" if iso_angle >= 60.0 else "Soldier"
    if sides == 4:
        return "Gentleman"
    if sides == 5:
        return "Professional"
    if sides < PRIEST_SIDES:
        return "Noble"
    return "Priest"


@dataclass(slots=True)
class Entity:
    id: int = 0  # assigned by World.add
    kind: str = ""  # "creature" | "food" | "house"
    x: float = 0.0
    y: float = 0.0
    angle: float = 0.0


@dataclass(slots=True)
class Creature(Entity):
    kind: str = "creature"
    shape: str = "polygon"  # "polygon" (male) | "line" (female)
    sides: int = 4
    speed: float = 0.6  # grid units per tick
    energy: float = 80.0
    caste: str = ""
    radius: float = 0.0  # body radius; derived from caste when unset
    age: int = 0  # ticks lived
    lifespan: float = 0.0  # 0 => derived from caste table
    sight_mult: float = 0.0  # 0 => derived from caste table
    iso_angle: float = 59.5  # isosceles triangles: smallest angle, degrees
    generation: int = 0
    born_tick: int = 0
    mother_id: int = 0
    father_id: int = 0
    repro_cooldown: int = 0
    irregularity: float = 0.0  # 0 = regular; mutation may deform a child
    matured: bool = False  # set once the world judges an irregular at adulthood
    health: float = 100.0  # 0..100; disease drains it, time heals it
    infected: bool = False
    disease_id: int = 0
    clan_id: int = 0  # 0 = clanless (assigned at birth / world creation)
    is_predator: bool = False  # Carnivore caste (§I)
    is_herbivore: bool = False  # wild grazer (§O)
    bite_cooldown: int = 0  # ticks until next bite
    cannibal_cooldown: int = 0  # §AC: ticks before another desperate kill
    sleeping: bool = False
    indoors: bool = False  # won a bed in a house this tick
    ticks_since_meal: int = 0
    meals: int = 0
    status: str = ""  # "" | "hungry" | "starving"
    chill: float = 0.0  # §R: cold built when unsheltered in rain/storm/winter night; threshold → sick
    facts: dict = field(default_factory=dict)
    # §X knowledge set: "food"/"danger" -> {"x","y","tick","conf"},
    # "safe" -> {"x","y","tick"}, "enemies" -> {clan_id: {"tick","conf"}}.
    # Facts decay after knowledge_ttl; shared facts arrive with halved confidence.
    signal_cooldown: int = 0  # ticks until next call allowed
    trait: str | None = None  # §S genetic trait: greedy/peaceful/paranoid/bold or None
    give_ups: dict = field(default_factory=dict)  # meal id -> tick abandoned (behind rock/wall)
    blocked_ticks: int = 0  # consecutive moves rebound by a house wall (wedge detector)
    # Creature Evolution systems (autonomous tools, skills, personality & emotes)
    equipped_item: str | None = None  # "spear" | "basket" | "torch" | "herb_poultice" | "crown" | None
    food_basket: int = 0  # current count of food carried in basket (up to 3)
    personality: str = "brave"  # "brave" | "cautious" | "altruistic" | "greedy" | "explorer" | "builder"
    skills: dict = field(default_factory=lambda: {"farming": 0.0, "combat": 0.0, "foraging": 0.0, "healing": 0.0})
    title: str | None = None  # earned dynamic epithet (e.g. "the Fearless", "the Harvester")
    emote: str | None = None  # active emote: "hungry"|"love"|"combat"|"panic"|"heal"|"cheer"|"sleep"|"craft"
    emote_ticks: int = 0  # remaining ticks for emote balloon
    # Cognitive Agency & Social Intelligence (§AL)
    waypoints: dict = field(default_factory=dict)  # {"home": (x,y), "rich_food": (x,y), "danger": (x,y), "patrol": (x,y)}
    trust: dict = field(default_factory=dict)  # target_id -> trust_score (-100..+100)
    # §AS L-0: panic window right after the clan leader's death — flee urge spikes
    panic_ticks: int = 0
    # §AQ PH-1: body temperature (°C-ish) — drifts toward the ambient heat field
    body_temp: float = 20.0
    # §AT-4 H-1 damage variety: chronic hunger, lingering wounds, food-quality healing
    low_energy_ticks: int = 0  # consecutive ticks below the exhaustion floor
    wound_ticks: int = 0  # countdown while a persistent wound lingers
    wound_severity: int = 0  # 0 none | 1 wound | 2 grievous (no combat)
    wound_dressed: bool = False  # §AT-4 H-2: a helper has bandaged this wound
    scars: int = 0  # §AT-4 H-2: permanent marks of survived grievous wounds
    heal_bonus_amount: float = 0.0  # extra health per tick from rich food
    heal_bonus_ticks: int = 0  # countdown for the bonus above
    # §AT-4 H-2: morale — the second health axis; despair stops provision,
    # breaks bonds and finally drives a body to abandon its clan.
    morale: float = 100.0
    pause_ticks: int = 0  # §AR S-7: grieving kin stand still for a few ticks
    # §AR S-1 hearing: alarm habituation and rude awakenings
    alarm_streak: int = 0  # consecutive ticks hearing the SAME alarm source
    last_alarm_sender: int = -1  # sender id of the last heard alarm
    alarm_wake_ticks: int = 0  # >0: a war cry tore us from our sleep
    # §AS L-1: a rally before battle sharpens every blade in earshot
    combat_boost_ticks: int = 0
    # §AM agriculture: seed pouches gathered from wild harvests, sown at farm plots
    seeds: int = 0
    # §AQ PH-7 metabolic extremes: sustained cooking collapses the body
    heat_stroke_ticks: int = 0
    # §AQ PH-4 cliff grace — no repeated tumbles while stunned
    fall_cooldown: int = 0
    # §AN voice & ritual: chant-calm window, omen preparation, greeting pacing,
    # and an active diplomatic mission (emissary)
    calm_ticks: int = 0
    prepared_ticks: int = 0
    greet_cooldown: int = 0
    mission: dict | None = None
    # §BE Creature Movement AI Overhaul: correlated wander, territory patrol
    _heading_bias: float = 0.0  # OU drift for wander (decays ×0.80/tick)
    _patrol_target: tuple[float, float] | None = None  # territory patrol point (refreshed when reached or 80 ticks)
    _decay_scale: float = -1.0
    _bc_steer_scale: float = 1.0

    @property
    def max_health(self) -> float:
        return max_hp_for(self.caste)


    def __post_init__(self) -> None:
        if not self.caste:
            self.caste = caste_name(self.sides, self.shape, self.iso_angle)
        traits = traits_for(self.caste)
        if not self.radius:
            self.radius = RADIUS_BY_CASTE.get(self.caste, DEFAULT_RADIUS)
        if not self.lifespan:
            self.lifespan = traits.lifespan
        if not self.sight_mult:
            self.sight_mult = traits.sight_mult
        # §AT-4 H-1: a soft-bodied caste cannot start above its health pool
        cap = max_hp_for(self.caste)
        if self.health > cap:
            self.health = cap

    @property
    def sex(self) -> str:
        """Flatland: males are polygons, women are lines."""
        return "female" if self.shape == "line" else "male"

    @property
    def stage(self) -> str:
        """Life stage by fraction of natural lifespan."""
        if self.lifespan <= 0:
            return "adult"
        f = self.age / self.lifespan
        if f < 0.15:
            return "infant"
        if f < 0.30:
            return "juvenile"
        if f < 0.75:
            return "adult"
        return "elder"

    FERTILITY_MULT = {"infant": 0.0, "juvenile": 0.0, "adult": 1.0, "elder": 0.5}


@dataclass(slots=True)
class Food(Entity):
    """A living plant: grows from sprout toward maturity (1.0).

    Immature plants feed a creature proportionally to their growth;
    mature plants yield the full bounty. Fresh shoots start at 0.15.
    Variant (§O biodiversity): grass/berry/mushroom/poisonous each
    with distinct color, energy and seasonal rhythm.
    """

    kind: str = "food"
    growth: float = 0.15  # 0..1 — 1.0 means mature
    variant: str = "grass"  # grass | grain | berry | medicinal_herb | mushroom | poisonous
    # poisonous plants sicken; mushrooms are decomposers; herbs cure; grain is calorie-dense
    mature_ticks: int = 0  # §AE: ticks lived since reaching maturity (decay clock)
    cultivated: bool = False  # §AM: sown by farmers — grows faster, feeds better
    irrigated: bool = False  # §AM: furrow-watered — rides out drought, frost & storm



@dataclass(slots=True)
class Corpse(Entity):
    """The remains of the fallen — edible, and fading with every tick."""

    kind: str = "corpse"
    ttl: int = 600  # ticks until fully decayed
    energy: float = 25.0  # what's left to scavenge


@dataclass(slots=True)
class House(Entity):
    kind: str = "house"
    size: float = 6.0  # square side length
    door_width: float = 4.0  # gap in the wall
    door_side: str = "south"  # "north" | "east" | "south" | "west"
    door_offset: float = 0.0  # door centre offset along that wall
    clan_id: int = 0  # claimed by this clan (0 = unclaimed); set when §L enabled
    clan_color: str | None = None  # crest color of claiming clan
    is_main: bool = False  # chief / main house where the clan leader lives
    abandoned_ticks: int = 0  # how long this house has been without a living clan
    is_ruin: bool = False  # crumbled — no shelter, visually distinct
    takeover_tick: int = -1  # §AT-3: tick of the last hostile takeover (render flash)
    material: str = "wood"  # §AQ PH-1: straw | wood | stone — sets the insulation
    murals: int = 0  # §AN: painted chronicle of the clan's great days
    # §AQ PH-1 hearths: a permanent fire installation; fuel is bought from the
    # clan larder and burns down every tick — an unfed hearth goes dark.
    hearth_lit: bool = False
    hearth_fuel: float = 0.0  # ticks of burn remaining
    # §AQ PH-6 materials: structural integrity and the rubble of a collapse
    hp: float = -1.0  # -1 = untouched (full durability of its material)
    rubble: float = 0.0  # >0 while a collapsed ruin still blocks the lot
