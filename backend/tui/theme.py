"""Theme — the single source of truth for TUI colors, glyphs and icons.

Mirrors frontend/src/render/CanvasRenderer.tsx so both clients read alike.
"""

from __future__ import annotations

# Caste colors (match CASTE_COLORS in CanvasRenderer.tsx)
CASTE_COLORS: dict[str, str] = {
    "Soldier": "#ff7b72",
    "Artisan": "#f2cc60",
    "Gentleman": "#ffa657",
    "Professional": "#d2a8ff",
    "Noble": "#79c0ff",
    "Priest": "#e6edf3",
    "Woman": "#ff9bce",
    "Predator": "#ff3838",
    "Herbivore": "#90be6d",
}

DEFAULT_CREATURE_COLOR = "#8b949e"

# Plant variants (match variantColors in CanvasRenderer.tsx)
VARIANT_COLORS: dict[str, str] = {
    "grass": "#3fb950",
    "berry": "#f85149",
    "mushroom": "#a67c52",
    "poisonous": "#8957e5",
}

# Soul-code glyphs per creature come from EntityState.glyph; these are the
# fallback marks when a state has none (or for special kinds).
FALLBACK_GLYPHS: dict[str, str] = {
    "Soldier": "s",
    "Artisan": "a",
    "Gentleman": "g",
    "Professional": "p",
    "Noble": "n",
    "Priest": "o",
    "Woman": "w",
}

GLYPH_PREDATOR = "^"
GLYPH_HERBIVORE = "h"
GLYPH_CORPSE = "x"
GLYPH_HOUSE_WALL_H = "-"
GLYPH_HOUSE_WALL_V = "|"
GLYPH_HOUSE_CORNER = "+"
GLYPH_HOUSE_DOOR = "/"
GLYPH_ROCK = "@"
GLYPH_FOOD_SPROUT = "."
GLYPH_FOOD_MATURE = "*"
GLYPH_FIRE = "&"
GLYPH_SIGNAL = "~"
GLYPH_RIVER = "~"
GLYPH_BRIDGE = "="
GLYPH_DAM = "H"
GLYPH_BOUNDARY_STONE = "•"
GLYPH_MARKET = "M"
GLYPH_ANOMALY = "🌀"
GLYPH_LIGHTNING = "⚡"
GLYPH_CAMPFIRE = "▲"

# Chronicle event colors (match index.css/App.tsx ev-* classes)
EVENT_COLORS: dict[str, str] = {
    "birth": "#3fb950",
    "promotion": "#d2a8ff",
    "demotion": "#ff7b72",
    "death": "#8b949e",
    "predation": "#ff3838",
    "war": "#f85149",
    "alliance": "#3fb950",
    "rivalry": "#d29922",
    "schism": "#e3b341",
    "succession": "#d2a8ff",
    "settlement": "#79c0ff",
    "conquest": "#ff7b72",
    "takeover": "#ff7b72",
    "culture": "#bc8cff",
    "fire": "#ff6b35",
    "disaster": "#e3b341",
    "outbreak": "#d29922",
    "recovery": "#3fb950",
    "bloom": "#56d364",
    "ruin": "#8b949e",
    # §AB politics / §AC desperation / §AE decay
    "coalition_formed": "#7ee787",
    "coalition_joined": "#7ee787",
    "coalition_dissolved": "#8b949e",
    "peace": "#3fb950",
    "tribute": "#e3b341",
    "betrayal": "#f85149",
    "defection": "#d2a8ff",
    "cannibalism": "#ff6b6b",
    "exile": "#db6d28",
    "wither": "#a67c52",
    # §AP unified theology
    "miracle": "#7ee787",
    "sermon": "#d2a8ff",
    "synod": "#e3b341",
    "temple": "#e3b341",
    "epiphany": "#bc8cff",
    "resonance": "#e3b341",
    # Additional events
    "clan_extinction": "#ff7b72",
    "extinction": "#f85149",
    "anomaly": "#79c0ff",
    "raid": "#f85149",
    "banquet": "#e3b341",
    "compost": "#a67c52",
    "hospitality": "#7ee787",
    "peace_envoy": "#7ee787",
    "market": "#d2a8ff",
    "caravan": "#ffa657",
    "regicide": "#ff3838",
    "herald": "#d2a8ff",
    "omen": "#bc8cff",
}

SIGNAL_COLORS = {
    "food": "#3fb950",
    "alarm": "#f85149",
    "help": "#ffd166",
    "knowledge": "#79c0ff",
    "grief": "#8b949e",
    "chime": "#e3b341",
    "chant": "#b392f0",
    "hum": "#ff9ecd",
    "war": "#ff7b72",
    "trail": "#d2a8ff",
    "danger_scent": "#6e7681",
    "courier": "#e3b341",
    "omen": "#e3b341",
}

SEASON_ICONS = {"spring": "*", "summer": "S", "autumn": "%", "winter": "W"}
WEATHER_ICONS = {"clear": "O", "rain": ",", "fog": "=", "storm": "/"}

STATUS_COLORS = {"hungry": "#d29922", "starving": "#f85149"}

# Creature Evolution Icons & Badges
PERSONALITY_ICONS: dict[str, str] = {
    "brave": "🛡️ Brave",
    "cautious": "🌾 Cautious",
    "altruistic": "🤝 Altruistic",
    "greedy": "💰 Greedy",
    "explorer": "🧭 Explorer",
    "builder": "🔨 Builder",
}

ITEM_ICONS: dict[str, str] = {
    "spear": "🗡️ Spear",
    "basket": "🧺 Basket",
    "crown": "👑 Crown",
    "herb_poultice": "🌿 Herb Poultice",
}

EMOTE_ICONS: dict[str, str] = {
    "hungry": "🍖 Hungry",
    "love": "❤️ Love",
    "combat": "⚔️ Combat",
    "panic": "😱 Panic",
    "heal": "🌿 Healing",
    "cheer": "🏆 Cheer",
    "sleep": "💤 Asleep",
    "craft": "🧺 Harvest",
}

TOTEM_ICONS: dict[str, str] = {
    "Radiant Circle": "⭕ Radiant Circle",
    "Celestial Strike": "⚡ Celestial Strike",
    "All-Seeing Vertex": "👁️ All-Seeing Vertex",
    "Indomitable Monolith": "🛡️ Indomitable Monolith",
    "Sacred Spiral": "🌿 Sacred Spiral",
    "Cosmic Scales": "⚖️ Cosmic Scales",
    "Dimensional Rift": "🌀 Dimensional Rift",
    "Eternal Hearth": "🕯️ Eternal Hearth",
}

SKILL_ICONS: dict[str, str] = {
    "farming": "🌾 Farming",
    "combat": "⚔️ Combat",
    "foraging": "🦴 Foraging",
    "healing": "🌿 Healing",
}


def caste_color(caste: str | None) -> str:
    if caste is None:
        return DEFAULT_CREATURE_COLOR
    return CASTE_COLORS.get(caste, DEFAULT_CREATURE_COLOR)


def dim(color: str) -> str:
    # Quick terminal dim color
    return f"dim {color}"
