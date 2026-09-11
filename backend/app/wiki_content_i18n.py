"""Localized markdown content for Flatland Wiki (en, vi, fr).

Includes full translations for:
- HOW_IT_WORKS_MD_I18N
- CONFIG_OPS_MD_I18N
- QUICKSTART_MD_I18N
- CODEBASE_MAP_MD_I18N
- DATA_MODEL_MD_I18N
- CURL_EXAMPLES_I18N
"""

from __future__ import annotations

# ---------------------------------------------------------------------
# How the world works (HOW_IT_WORKS_MD_I18N)
# ---------------------------------------------------------------------

HOW_IT_WORKS_EN = r"""
# How the world works

**The Sphere (God model):** The Sphere (God) sets *laws* from Spaceland, never touches individual creatures. Everything else emerges.

## The deterministic tick
`s = Simulation(Config(seed))` → `s.step()` is fully deterministic (one `random.Random` per world). Same seed ⇒ same world. Tick loop (`backend/app/simulation/core.py` `Simulation.step()`) order: weather → plants → rebuild index → creatures → disease → war → reproduce → relations → food law → corpses → settlements → tick+=1. Simulation advances on a dedicated OS thread (`SimEngine`) with lockless serialization, streaming snapshots over WebSocket `state` every tick.

## Life cycle & stages (§A)
Creature.age ticks + caste-based lifespan (Woman 4800 → Priest 9000). Stage by `age/lifespan`: infant <15%, juvenile <30%, adult <75%, else elder. Stage scales speed & sight (infant 0.6×, elder 0.85×) and fertility (elder ×0.5). Death causes: `starvation`, `old_age`, `euthanasia`, `disease`.

## Health core (§AT-4 H-0)
Health is a resource, not a constant. Regeneration demands an energy surplus: below 40% of `energy_max` (`HEALTH_REGEN_MIN_ENERGY`) wounds stop closing — awake or asleep; sheltered rest heals at `0.15×rest_recovery_mult`, waking regen is `0.1/tick` (+Indomitable Monolith defense). Below 20% energy the body cannibalizes itself: `−0.05` health/tick (`HEALTH_SELF_DRAIN_*`) until death by `starvation` — famine now kills twice. Weakness slows every stride (`HEALTH_SPEED_TIERS`): health <80 ×0.95, <60 ×0.85, <40 ×0.70, <20 ×0.50. Sickly bodies cannot beget children: mating requires `health ≥ REPRO_MIN_HEALTH` (50), so a plague suppresses births without touching birth laws.

## Damage variety & healing economy (§AT-4 H-1)
Chronic hunger gnaws: below 20% energy for more than `EXHAUSTION_TICKS` 30 ticks drains `EXHAUSTION_DRAIN` 0.08 health/tick (death cause `exhaustion`). Age withers: elders lose `ELDER_DECAY_RATE` 0.02/tick passively. Sickness dims the eyes (`HEALTH_SIGHT_TIERS`: <60 ×0.90, <30 ×0.75) and blunts the harvest (`_forage_mult`: −20% under 60 HP, −50% under 30) so decline feeds on itself. The badly wounded (<30 HP) or grievously wounded never start a duel, though they can still be attacked; blows above `WOUND_MIN_DAMAGE` 15 leave a lingering wound (50–100 ticks, severity 1–2 by damage ≥40) that halves or quarters regen and hobbles speed (×0.85/×0.70). Where a body stands decides how fast it mends: waking regen runs at ×0.5 outdoors (`REGEN_OUTDOOR_MULT`) vs ×0.8 sheltered-awake vs full strength asleep indoors. And supper keeps working: berries set +0.3 health/tick for 20 ticks, grain +0.2×30, medicinal herbs +0.8×40 (`FOOD_HEAL_BONUS`) — a hurt creature even seeks herbs on a full stomach (herb targeting ignores the sated gate under 60 HP). Bodies differ in depth, too (`CASTE_MAX_HP`): Soldiers/Artisans pool 130 HP, Nobles/Predators 120, Women 110, Gentlemen/Herbivores 100, Professionals/Priests a delicate 90 — regeneration and healing cap at each body's own pool.

## Physics axioms (§AQ PH-0)
Energy is the universal currency. Sunlight is the world's only income: `_sun_factor()` follows the day cycle — zero through the night, full strength at noon — and gates both plant growth and seed spread, so nothing grows for free in the dark (winter's bite remains the season table). Every body pays upkeep by its geometric complexity (`METABOLIC_COST`): triangles 1.0×, squares 1.1×, pentagons 1.2×, hexagons/nobles 1.3×, women and priests 1.5× (a priest burns energy maintaining the aura) — applied to the per-tick decay on top of stage/lifestyle multipliers. And mending is a conversion, not a miracle: each point of regenerated health costs `HEALING_ENERGY_COST` 0.5 energy (charged only when healing actually happens).

## Thermodynamics & heat (§AQ PH-1)
A coarse ambient heat field (`TEMP_CELL` 25-unit cells, `_update_temperature`) relaxes toward a target each tick: the seasonal base (`SEASON_BASE_TEMP` spring 12° / summer 24° / autumn 8° / winter −4°) swept across the map from an edge — cold fronts enter from the west, warm fronts from the east — plus the day cycle (`DAY_HEAT_AMPLITUDE` ±5°), weather (rain −2°, storm −3°, fog −1°) and open flame (`FIRE_HEAT` 60° within 8 units). Every creature carries `body_temp` (on the wire) that drifts toward the local ambient at `BODY_TEMP_DRIFT`; standing indoors replaces ambient with `indoor_ambient()`, where the house material insulates (`INSULATION_BY_MATERIAL`: straw 0.15 < wood 0.35 < stone 0.55) toward `HOUSE_COMFORT_TEMP` 18°, and larger floors shed heat faster (`HOUSE_REF_SIDE/size`). Extreme heat is always physics: past `HYPERTHERMIA_TEMP` 36° health drains with the excess (`HYPERTHERMIA_DRAIN`) until death by `hyperthermia`. Extreme cold feeds §R chill below `HYPOTHERMIA_TEMP` 2° when the weather-sickness law is on.

## Wind (§AQ PH-2)
The sky has a breath: a wind vector (`wind_angle`/`wind_speed`, on every snapshot payload) whose strength follows the weather — calm 0.25, rain 0.55, storm howls at 1.0 (`WIND_*_SPEED`, relaxed each tick) — and whose direction re-rolls near the season's prevailing bearing whenever the weather turns (`WIND_SEASON_BIAS`). Fire obeys it: both random ignition and plant-to-plant spread multiply by a tailwind factor (`WIND_FIRE_MULT` × speed × alignment), so flame races downwind while upwind groves stand longer.

## Nature's Law inheritance (§B)
Sex: polygons male, lines female (`entities.py:137`). Sons `sides = father.sides+1` capped at `max_sides` (`24→Priest` per new spec; `K∈[3,24]`); daughters lines. Mutation `mutation_rate` ±1 side → `irregularity` 0.3–1.0. Isosceles triangles: `iso_angle+0.5°` per generation, `≥60°` promotes Soldier→Artisan. Fertility: per-caste table × crowding `carrying_capacity`/`max_population`. When `morphology_annealing_enabled` (morphology_engine), polar $(r_i,\phi_i)$ annealing supersedes side-count: $\lambda(g)$ blends Abbott template $K\in[3,24]$ with parental noisy genome, topo $p\cdot(1-\lambda)$.

## Geometric Physics (Morphology Engine, K∈[3,24])
Polar genomes $K\in[3,24]$ SoA `morph_radii/morph_angles/morph_k/physical_traits (A,P,I_{zz},\theta_{\min},asym,Dmult)` — vectorized `morphology_engine.py` `KMAX 24` (`morphology.py` shim). $\lambda(g)=morph\_lambda\_override ?? clamp(1-(g-g_{start})/g_{decay})$ (`g_start 50` `g_decay 150`, `override -1.0` = auto). Baking $E_{\max}\cdot clamp(A/A_{ref},0.5,2.5)$ $decay\cdot clamp(P/P_{ref},0.7,2.0)$ $steer\Delta\theta$ $D_{mult}$ $asym$→$irregularity$ with `safeguard_morph_mercy` ($\eta>0.3$ suspends euthanasia), SAT broadphase $r_{\max}$ + circle fallback ($K\ge24$ & $asym<0.05$) + edge normals + $D_{mult}$ impulse. Telemetry `/api/metrics/morphology` and `/api/metrics/safeguards` (`N,\eta,tier,miracles,mercy`) live.

## Evolutionary Genome Mirror & Visual Phenotypes (§BK-8 / §BK-9)
Flatland unifies map visualization into an **Evolutionary Genome Mirror** where each creature's body dynamically mirrors its living genome, morphological mutations, and generational lineage across millennia (from Gen 0 to Gen 2000+):
- **Generational Epoch Spectrum (Gen 0 → 2000+)**:
  - **Gen 0–4 (Genesis Founders)**: Primordial Sky Cyan (`#38bdf8`) with a pulsing 4-point Genesis Spark.
  - **Gen 5–24 (Pioneers)**: Early Pioneer Aqua (`#06b6d4`).
  - **Gen 25–74 (Dynastic Lines)**: Formative Dynastic Jade (`#10b981`) with a concentric gold Dynasty Core Ring.
  - **Gen 75–199 (Imperial Eras)**: Imperial Classical Violet (`#8b5cf6`).
  - **Gen 200–499 (Sovereign Houses)**: Ancient Sovereign Magenta (`#ec4899`).
  - **Gen 500–999 (Solar Empires)**: Millennial Solar Ember (`#f97316`).
  - **Gen 1000–1999 (Eon Sovereigns)**: Eon Sovereign Gold (`#facc15`).
  - **Gen 2000+ (Celestial Transcendants)**: Transcendent Celestial Diamond Starlight (`#fef08a`).
- **Millennial Coronas & Orbital Halos**:
  - **Gen 50+**: 8-ray Celestial Starburst Corona (`#fde047`).
  - **Gen 200+**: 12-ray Sovereign Sunburst Corona (`#fbbf24`).
  - **Gen 500+**: 16-ray Radiant Astral Corona with dashed orbital halo ring (`#f59e0b`).
  - **Gen 1000+**: 20-ray Solar Eon Corona (`#facc15`).
  - **Gen 2000+**: 24-ray Cosmic Starlight Corona with 8 orbiting diamond starlight cardinal flares (`#fef08a`).
- **Genomic Mutation & Aberration Mirroring**:
  - Regular orthodox creatures retain crisp geometric boundaries.
  - Minor divergence ($0.08 \le irr < 0.16$) shifts hue toward violet and amber.
  - Severe aberrations ($irr \ge 0.16$) shift toward deep magenta and crimson rose (`#f43f5e`).
  - Radical mutants ($irr > 0.18$) radiate a bioluminescent chaotic aura with dynamic vertex breathing.
- **Physical Trait Phenotypes**:
  - **Razor Edges ($D_{mult}$)**: Apex vertex glints sparkle with intensity proportional to offensive sharpness.
  - **Inertia Armor ($I_{zz}$ / Area)**: Thickened double-walled kinetic shell on high-inertia agents.
  - **Ancestral Patina**: Crystalline core patinas solidify with age and lineage.

## World History, Chronicle & AI Storytelling (§BM)
Flatland features an end-to-end multi-era historiography, timeline analytics, and AI storytelling suite:
- **Major Moments & Chronicle Jumps**: Top dramatic days (casualties, conquests, schisms) are automatically highlighted as jump chips above the chronicle feed. Users can jump directly to any specific tick timestamp.
- **Epoch Bar & Population Sparkline**: Interactive temporal navigation with color-coded world epochs (Genesis, Age of Tribes, Feudal Era, Classical Zenith, Era of Ruin) and population curves overlaid with war and plague crisis markers.
- **Records & Legends Leaderboard**: Hall of fame for Sovereign of War, Deadliest Single Day, Greatest Realm, Divine Architects, Largest Schism, and Hero/Villain notables.
- **History Analytics**: Clan Rivalry Heatmap Matrix, Mortality Breakdown (combat, famine, disease, age) across 10-day eras, and Faith Devotion Index over time.
- **In-App AI Story Generator**: Integrated browser-based LLM narrative generator using Google Gemini 1.5 Flash or OpenAI GPT-4o-mini with client-side API keys in localStorage. Supports 4 narrative styles (Saga, Chronicle, Mythos, Tragedy) in EN, VI, and FR.
- **Deep Linking**: Shareable URLs with `?history=42` to auto-open specific world days or `?clan=7` to auto-open clan biographies.

## Irregularity & caste (§C)
Mutated children's `irregularity` judged at `adult_age`: `≥euthanasia_threshold` → consumed (`euthanasia`), else demoted to Soldier. `CASTE_TRAITS` (`entities.py:39`) gives lifespan/speed/sight_mult/fertility. BC maps $asymmetry$ → $irregularity$ for same gate.

## Disease (§D)
`disease_enabled`, `disease_outbreak_rate` starts new `disease_id`, spreads within `disease_radius` at `disease_rate` (winter ×1.5), drains `disease_energy_drain` + health `2×disease_lethality`, recovers `recovery_rate`. Disabling freezes instantly.

## Environment (§E)
Clock from tick: `time_of_day` (`day_length` cycle, starts sunrise), `day`, `season` (`season_length`). Night `night_sight_mult`, fog `fog_sight_mult` stack. `SEASON_FOOD_MULT` spring 1.0/summer 1.2/autumn 1.0/winter 0.5; spring ×1.25 birth, winter ×1.5 disease. Weather FSM clear/rain/fog/storm at `weather_change_rate`: rain/storm `rain_speed_mult`, storm `storm_wander_bonus`.

## Clans & social order (§C/I/P/V)
Settlements seed clans (§V): every non-ruin house founds a clan led by the founding creature nearest its centre, and every founding creature joins its nearest house's clan — soldiers, women, nobles and priests mix inside one settlement (`simulation/settlement.py` `_found_founding_clans`, deterministic given the seed). God law `max_clans` caps society granularity: `-1` = one clan per house; `N ≥ 1` clusters the founders into N spatial clans (greedy k-centre) instead — a pinned value applies at world creation. A clan's settlement IS its anchor house: claims match the clustering (`_assign_house_claims`/`_claim_house_for_clan` pick the free house nearest a clan's people, never round-robin), and territory/totem/crest anchor there. Children inherit mother's `clan_id`; orphans found new clans that settle at the nearest free house (or build one, §L). Procedural name (`CLAN_ADJECTIVES/NOUNS`) + Sacred Avatar of the Sphere (§AP: ⭕ Radiant Circle, ⚡ Celestial Strike, 👁️ All-Seeing Vertex, 🛡️ Indomitable Monolith, 🌿 Sacred Spiral, ⚖️ Cosmic Scales, 🌀 Dimensional Rift, 🕯️ Eternal Hearth — emoji on the map) if `totems_enabled` (`config.py:59`, `simulation/theology.py` `AVATARS`/`TOTEM_BUFF`, `renderCore.tsx` pole + shrine). Clan crest color on snapshot, totem pole + glowing shrine beside the main house, `StateMessage.clans` carries `name`/`totem`/`faith`/`shrine_level`/`leader_id`/`color`. Clan stats & history (§P): `GET /api/clans` roster with `leader_id`/`population`/`house`/`war_wins`/`losses`/`territory_radius`, polled by `ClanPanel.tsx` under trophic chart. Relations −100..+100 drift `relation_drift_rate` →0, threshold `alliance_threshold`/`rivalry_threshold` → `alliance`/`rivalry` events; shared feeding within `flock_radius` `+2`. Boids `cohesion_weight`/`alignment_weight`/`separation_weight` blended after food-seeking; social yielding `YIELD_RADIUS` 2.5. Territory (§P): each settlement anchors a `territory_radius` 14 circle (`config.py:49`, `simulation/society.py` `_update_territory`, `CanvasRenderer.tsx:514`) — members steer home when outside (`0.35×steer`), trespass inside a rival's circle sours relations `trespass_decay` (`protocol.py:127`) via `_bump_relation`. Totem buffs (§AP): eight Sacred Avatars with divine aspects — ⭕ `Radiant Circle` +30% harvest/+20% fertility, ⚡ `Celestial Strike` +25% warrior damage, 👁️ `All-Seeing Vertex` +40% sight + nocturnal clarity, 🛡️ `Indomitable Monolith` −30% damage/cold immunity, 🌿 `Sacred Spiral` herbs ×2/plague recovery/composting, ⚖️ `Cosmic Scales` reliable peace/refuses kin-eating, 🌀 `Dimensional Rift` faster promotion/adaptive mutation/elder lore, 🕯️ `Eternal Hearth` nocturnal calm. Theology (§AP): settled clans consecrate a shrine beside the main house (`_update_faith`); the devout tithe `tithe_rate` at dawn & dusk into the clan faith pool; the aura mends the faithful; faith overflowing at a season turn works a `miracle` (bloom + mending); `temple_faith_cost` raises a Temple whose aura covers all territory (`temple` event); when God sets laws every shrine chimes and priests preach doctrinal `sermons` (`on_law_change` from `POST /api/laws`); same/complementary-avatar clans sympathise (+1 relation, holy alliances); crisis ages convene the Great `synod` (+relations, sacred truce); and rarely an elder priest receives the 3D `epiphany` — all strife stills (`truce_ticks`). Leadership (§P): founder is `leader_id` (`simulation/society.py`), death triggers succession to oldest living member → `succession` event (`protocol.py:129`, `simulation/lifecycle.py`) if `succession_enabled` (`config.py:54`).

## Food economy (§H/N/O)
`Food` is a living plant `growth` 0.15→1.0 (`plant_growth_rate`), spreads `plant_spread_rate` within `SPREAD_RADIUS` 6.0 if below seasonal bounty `food_count×SEASON_FOOD_MULT`. Winter die-back removes youngest first. A meal whose straight path is blocked by a rock circle or a house wall is abandoned for `food_giveup_ticks` — the hungry give up and seek food somewhere else instead of grinding against the obstacle until they starve; eating anything clears the grudge, 0 disables giving up (`_segment_hits_circle`, `_give_up_on`). Death leaves `Corpse` (`corpse_ttl`, `corpse_energy`) edible like food; decay boosts nearby plants `NUTRIENT_BOOST×nutrient_cycle_rate` within `NUTRIENT_RADIUS`. §O biodiversity: `Food.variant` grass/berry/mushroom/poisonous (`entities.py:169`) — `plant_variants_enabled`/`poison_rate` (`config.py:44`), `VARIANT_ENERGY` grass 32/berry 48/mushroom 24/poison 8 and `VARIANT_HEALTH` berry +1/poison -30 (`simulation/constants.py`), growth `VARIANT_GROWTH_MULT`×`VARIANT_SEASON_MULT` (`simulation/ecology.py`), spawn picks berry burst in autumn / mushroom on corpses/rocks (`simulation/ecology.py`), `poisonous` mutates via `poison_rate`; `bloom` carries `variant` (`simulation/ecology.py`). Wild herbivores (§O): `Herbivore` clanless grazers (`entities.py:40`, `is_herbivore`) spawn `area×density×beast_ratio` (`config.py:46`, `simulation/lifecycle.py`), graze plants and are hunted by predators (plants → herbivores → predators); `beast_ratio`/`diet_strictness` GodLaws (`protocol.py:123`). Diet & preference (§O): `diet_strictness` (`config.py:46`) filters perceived meals (`simulation/creature_update.py`) — herbivore ignores `corpse` when strict, predator ignores `food`, higher castes skip low-energy `grass` when strict (`berry` preferred), herbivore avoids `poisonous`; `test_synergies.py:test_diet_preference_respects_strictness` verifies.

## Communication & knowledge (§Q/X)
Signals (§Q): food calls and alarm calls ripple within `signal_radius`; clan-mates respond strongly, strangers weakly. Knowledge (§X): creatures learn typed facts from experience — `food` spots seen/eaten, `danger` at predator sightings, `safe` roofs while sheltered, `enemy` clans that struck them (`Creature.facts`, decay after `knowledge_ttl`). Teaching: `knowledge_share_rate` chance/tick to broadcast the freshest fact to clan-mates; heard facts land at half confidence — retold knowledge is vaguer than firsthand sighting, only better news overwrites. Mobbing: an attacked creature emits a help call; clan-mates within `help_radius` converge on the attacker (warriors first via caste rank, the peaceful lag behind, high castes only when bold), and every defender inside earshot softens the attacker's blows by `defense_weight`. Clan memory: `/api/clans` surfaces each clan's remembered enemies/danger zones/food spots (`clan_knowledge()`), and clans that remember each other as enemies plot wars faster (§S foreshadowing). Full history (§AT-1): `GET /api/clans/{id}/history?page=&size=` paginates the clan's entire filtered event stream (newest first, `total`/`has_more`) alongside the internal milestone log; the durable chronicle filters by clan at the SQL level — `GET /api/history?clan_id=N` matches any clan-bearing payload key (`a`/`b`/`clan_id`/conquest/schism/takeover pairs) so events stay queryable after rolling off the in-memory deque; ClanDetails renders a lazy "Full History" panel with `load older`. Senses interact (§AR S-0): sleeping bodies are fully deaf — a sleeper never processes signals and never counts as a mob defender (`_mob_defenders` skips the asleep), so predators may stalk a silent village. Ripe plants smell through the dark: a hungry or starving creature with no visual target catches the scent of any mature plant (`growth 1.0`) within `FOOD_SCENT_RADIUS` 8.0 at night — blind starvation is cured by the nose. And starvation dulls fear: `_effective_fear_radius` halves `fear_radius` for the starving (traits paranoid +4 / bold −2.5 still apply first), so the desperate walk toward death chasing scented food.

## Politics (§AB)
Coalitions: a leader folds friendly unaligned clans (relation ≥ `coalition_threshold`) into a named bloc (`coalition_formed`/`coalition_joined`); soured or shrunken blocs dissolve (`coalition_dissolved`). Mutual defence — strike one member and every mate's relations with the attacker sour −12, dragging them into the war. Leader agency: leaders act on their heritable trait — bold declares war on a remembered enemy (§X), peaceful sues for peace when weakened (`peace` event), paranoid betrays an ally (`betrayal` event + treason: false enemy knowledge seeded into nearby third clans). Strong clans demand tribute: vassals pay from their larder every 240 ticks (`tribute` events). Resource sharing: each settlement keeps a larder capped by `larder_capacity` — well-fed members deposit surplus, starving members withdraw; full-bellied allies top up starving allies at `aid_rate`. Defection: unhappy members (starving or homeless) walk to the healthiest nearby banner, even a rival's (`defection` events). `/api/clans` exposes `coalition_id`, `larder`, `tribute_to`; ClanPanel shows 🤝 pact / 🛡️ vassal / 🏺 larder chips. The leader is leverage (§AS L-0): kin within `LEADER_AURA_RADIUS` 15 of the living leader gain +10% sight (`LEADER_SIGHT_BONUS`), −5% energy burn (`LEADER_DECAY_MULT`) and a calmer hand (fear radius −1); with no living leader the whole clan glooms — sight −10%, burn +5% (`LEADERLESS_DECAY_MULT`), food gain ×0.85 (`LEADERLESS_GAIN_MULT`), bylaws and task boards pause, war declarations stop, and members drift `cautious` at `LEADERLESS_CAUTIOUS_CHANCE`. The death itself shocks: every member instantly loses 10 energy (`LEADER_SHOCK_ENERGY`), panics for 20 ticks (+0.3 flee urge), the larder loses 20% to looting, and a grey grief ripple marks the spot.

## Desperation cannibalism (§AC)
Only the desperate eat the living: below `cannibalism_hunger_ratio` energy a creature perceives eligible prey — enemy-clan members (negative relation) and the weak (starving, elder, wounded) of any clan; never predators, wild beasts, infants or indoor refugees. On contact within `eat_radius` the prey dies (cause `cannibalism`), the eater gains `cannibalism_energy` and leaves a partial corpse, and a cooldown separates kills. Kin-eating carries a terrible price (`eat_kin_enabled`): the kin-slayer is exiled (`exile_on_kin_eat`) to found a one-being outcast band, witnesses remember the band as an enemy (§X), and relations between former clan and band sink by `kin_stigma` — rivalry, plots, war.

## Food decay (§AE)
Nothing lasts forever: a mature plant lives `food_lifespan_ticks` × its variant's pace (mushroom 0.4×, grass ×1, berry 1.5×, poisonous 3×) before it withers — sprouts and growing plants never rot. Withered plants fade brown in the renderer, release half a corpse's nutrient boost to nearby plants (§H death feeds life), then vanish (`wither` events stay in-memory like blooms, never the DB). The bounty law respawns replacement growth, so plant counts now churn instead of freezing.

## Shelter & Settlements (§L/N)
Houses (`entities.py:184`) squares with doorway; walls block except door — doorway too small for Carnivore predators (§L refuge) so houses are safe havens. Exposure `exposure_drain` outdoors in rain/storm or night unless `indoors`. Beds scale with floor area: `house_capacity` counts beds in an average 8×8 hall (`HOUSE_REF_AREA`), small huts have fewer beds, and large houses are strictly capped at 16 beds max (`HOUSE_MAX_BEDS`). Clans can settle across multiple houses, with the leader residing in the primary **Main House** marked with a golden crown. Abandoned houses decay to ruins (`is_ruin`). One house, one clan (§AT-2/AT-3): a creature sleeps only under its own clan's roof or an unclaimed one — `_house_for()` never returns a foreign house, so rival bodies cannot poison occupancy caps. A growing clan with no free roof may **take over** a weak rival's spare house (non-main, nobody sleeping there tonight, rival population under half its bed count — `_try_house_takeover`): the invader claims it outright, relations sour −25 and a `takeover` event hits the chronicle with an expanding crest-ring flash on the map; conquest-by-war transfers houses too (winner repoints the loser's seat). An audit pass each settlement tick (`_audit_house_claims`) clears claims whose clan died so no house ends a tick owned by a ghost.

## Autonomous Evolution & Tools (§AG)
Evolution emerges 100% autonomously without god interventions:
- **Personality Archetypes**: `brave`, `cautious`, `altruistic`, `greedy`, `explorer`, `builder` (65% heritability). Altruistic creatures feed starving kin with basket food.
- **Dynamic Equipment & Tools**: Soldiers/Predators wield Spears (+20% combat damage & reach); Farmers/Artisans/Herbivores carry Baskets (haul up to 3 food units for field snacks or clan larder deposits); Priests carry Herb Poultices (+25 HP healing & infection cure); Chieftains wear the golden Crown.
- **Skill Mastery & Dynamic Titles**: 4 skills (Farming 🌾, Combat ⚔️, Foraging 🦴, Healing 🌿) progress from Novice to Master, unlocking titles (*the Slayer*, *the Fearless Champion*, *the Grand Harvester*, *the Wise Shaman*, *the Pathfinder*).
- **Oral Lore**: Elders sleeping in houses transmit their highest skill mastery XP to resting youth.
- **Floating Emote Thoughts**: Real-time mood balloons (`🍖`, `❤️`, `⚔️`, `🌿`, `🏆`, `💤`, `🧺`, `😱`) above creature heads.

## Energy Dynamics & Stage Metabolism (§AH)
- **Stage-Aware Metabolism**: Born infants burn 55% less energy per tick (`0.45x`), juveniles burn 25% less (`0.75x`), adults standard (`1.0x`), elders `0.85x`.
- **Combat Stamina**: Duels and war clashes expend energy (winner -6, loser -10); low energy (<20%) causes an exhaustion penalty (30% less damage).
- **Food Reserves & Field Eating**: Roaming creatures with <45 energy autonomously eat carried food from their basket. Full creatures (>85% energy) never eat or destroy food plants.

## Cognitive Agency & Clan Social Intelligence (§AL)
- **Multi-Objective Utility AI Engine**: Dynamic utility scoring evaluating survival energy, caste duty, personality weights, and kin emergency signals.
- **Mental Map & Purposeful Waypoints**: Coordinates for `home`, `rich_food`, `danger`, and `patrol` enable purposeful foraging and perimeter circuits over random Brownian noise.
- **Tactical Combat Formations**: Allied Soldiers in combat align into disciplined phalanxes; 1D lines (women) execute evasive tangential kiting; outnumbered creatures execute organized retreats to shelter.
- **Interpersonal Trust Matrix**: Pairs develop affinity from healing (+15) and feeding (+20), forming loyal buddy pairs for shared foraging.
- **Clan Division of Labor & Task Board**: Dynamic macro priorities (`balanced`, `food_security`, `defense`, `quarantine_healing`) boost harvester (2.0×) and guard (2.5×) action weights.
- **Governance Archetypes**: Distinct institutional succession models (`Monarchy` royal dynasty, `Theocracy` priest succession, `Junta` combat mastery, `Republic` council of elders).
- **Dynamic Bylaws**: Automated policies including winter food rationing (<35 energy threshold) and wartime martial law curfews.
- **Macro Geopolitics & Casus Belli**: Intentional war declarations based on famine food raids, blood feuds, and territorial friction with documented Casus Belli.
- **Inter-Clan Trade Caravans**: Economic specialization barter transferring surplus grain from agrarian clans to martial clans in exchange for combat training and diplomatic goodwill (+12 relations).
- **Tribal Traditions & Harvest Festivals**: Annual autumn celebrations at clan Main Houses boosting energy (+25), mood emotes, leader trust (+10), and oral lore transmission (+2.0 skill XP).

## Food & Botanical Ecology (§AM)
- **Crop Diversity & Botanical Variants**: 6 distinct flora species (`grass`, `grain`, `berry`, `medicinal_herb`, `mushroom`, `poisonous`).
- **Functional Nutrition**:
  - *Golden Grain*: Dense calorie staple (+45 Energy), slow decay rate ($2.5\times$ lifespan), foundational for settlement security.
  - *Sun Berry*: Energy burst (+48 Energy) and +15% movement speed surge.
  - *Medicinal Herb*: Healing remedy (+18 Energy, $+30\text{ HP}$), cures infections, grants heal emotes.
  - *Fungi / Mushroom*: Decomposer thriving near corpses, rocks, and during winter (+24 Energy).
- **Targeted Dietary Selection**: Injured and infected creatures actively seek medicinal herbs (0.2× effective distance weighting); starving creatures seek golden grain (0.4× distance weighting).

## Terminal User Interface (§AI)
A complete Textual terminal interface (`backend/tui/`) attaches to running worlds with:
- Camera follow mode (`w`) tracking moving creatures.
- Category-filtered Chronicle (`t`) (All, Birth, Death, War, Politics, Settlement).
- Full creature dossier inspector (`enter` / `i`) and clan details modal (`c`).
- God laws manager (`g`) and ASCII/half-block renderer (`a` / `f`).

## Micro-Neural Network & Evolutionary Engine (BA)
Every creature carries a **micro Elman RNN** (`16 → 12 → 7`, 295 `float32` weights, fixed) evolved by selection — always on. Sensors (16): vitals, three raycasts ±35°, audio, scent, collision, slope and hidden state. Outputs (7): `thrust`/`steer` (movement + energy drain), `interact` (consume/attack), `social` (mating readiness replaces §B gating), `vocal_amp`/`vocal_freq`, `recurrent_out` (writes `hidden_state`). Physics 60 Hz, inference at `nn_inference_hz` (default 15 Hz, every 4th tick latched, zero-alloc `inputs_buf`/`outputs_buf`). Genomes init `N(0,0.5)` clipped `[-4,4]`; mating via spatial query when `energy > mate_energy_min` and `social > 0.5`; uniform crossover 50/50 + Gaussian mutation `N(0,0.08²)` `p=0.03` (`mutation_sigma`/`crossover_rate` laws). Always-on 295. See `backend/app/agent_soa.py`, `neural_engine.py`, `agent_pipeline.py`, `evolution.py`, `sim_loop.py`, `spatial_grid.py`.
"""

HOW_IT_WORKS_VI = r"""
# Nguyên lý vận hành thế giới

**The Sphere (Thượng đế ba chiều):** The Sphere thiết lập các *định luật tự nhiên* từ Spaceland, tuyệt đối không can thiệp vào số phận của từng sinh vật riêng lẻ. Mọi hành vi và trật tự đều tự vận hành phát sinh.

## Vòng lặp tick tất định
`s = Simulation(Config(seed))` → `s.step()` hoàn toàn tất định (mỗi thế giới dùng đúng một luồng số ngẫu nhiên `random.Random`). Cùng một seed ban đầu sẽ luôn tạo ra cùng một diễn biến lịch sử. Thứ tự thực thi mỗi tick (`backend/app/simulation/core.py` `Simulation.step()`): thời tiết → cây cối sinh trưởng → cập nhật lưới không gian → sinh vật hành động → bệnh dịch lây lan → chiến tranh giao tranh → sinh sản → quan hệ ngoại giao → luật cân bằng thức ăn → xác chết phân hủy → khu định cư → tăng tick+=1. Quá trình tính toán chạy trên một luồng hệ điều hành riêng biệt (`SimEngine`) với cơ chế tuần tự hóa không khóa (lockless), truyền phát trạng thái qua WebSocket `state` mỗi tick.

## Vòng đời & Các giai đoạn (§A)
Tuổi thọ tính theo tick + đẳng cấp (từ Phụ nữ 4.800 tick đến Tu sĩ 9.000 tick). Phân chia giai đoạn theo tỷ lệ `tuổi/tuổi thọ`: Sơ sinh (<15%), Vị thành niên (<30%), Trưởng thành (<75%), Lão niên (≥75%). Tuổi tác ảnh hưởng đến tốc độ di chuyển và tầm nhìn (sơ sinh 0.6×, lão niên 0.85×) cũng như khả năng sinh sản (lão niên giảm 50%). Nguyên nhân tử vong gồm: `starvation` (chết đói), `old_age` (già yếu), `euthanasia` (thanh lọc dị hình), và `disease` (bệnh tật).

## Cơ chế sinh lực cốt lõi (§AT-4 H-0)
Máu (HP) là một nguồn tài nguyên biến động, không phải hằng số cố định. Để tự hồi phục vết thương, sinh vật bắt buộc phải có năng lượng dồi dào: khi năng lượng dưới 40% `energy_max` (`HEALTH_REGEN_MIN_ENERGY`), mọi vết thương sẽ ngừng khép miệng dù đang thức hay ngủ; nghỉ ngơi trong nhà hồi máu theo tỷ lệ `0.15×rest_recovery_mult`, còn hồi phục tự nhiên khi thức là `0.1/tick` (cộng thêm giáp phòng thủ từ avatar Indomitable Monolith). Khi năng lượng tụt dưới 20%, cơ thể tự thiêu đốt sinh lực: giảm `−0.05` HP/tick (`HEALTH_SELF_DRAIN_*`) dẫn tới chết vì kiệt sức. Sinh lực suy yếu làm chậm từng bước chân (`HEALTH_SPEED_TIERS`): HP <80 tốc độ ×0.95, <60 ×0.85, <40 ×0.70, <20 ×0.50. Cơ thể đau ốm không thể phối ngẫu: sinh sản yêu cầu `health ≥ REPRO_MIN_HEALTH` (50 HP), do đó dịch bệnh sẽ ức chế tỷ lệ sinh mà không cần can thiệp vào định luật sinh sản.

## Đa dạng sát thương & Kinh tế trị liệu (§AT-4 H-1)
Đói kinh niên tàn phá cơ thể: dưới 20% năng lượng quá 30 tick sẽ rút `0.08` HP/tick (nguyên nhân tử vong `exhaustion`). Tuổi già bào mòn: sinh vật già mất thụ động `0.02` HP/tick. Bệnh tật làm mờ mắt (HP <60 giảm tầm nhìn 10%, <30 giảm 25%) và làm cùn khả năng thu hoạch (giảm 20% sản lượng khi HP <60, giảm 50% khi <30). Sinh vật bị thương nặng (<30 HP) không bao giờ chủ động gây hấn quyết đấu. Đòn đánh lớn (>15 sát thương) để lại vết thương sâu kéo dài 50–100 tick làm giảm tốc độ và giảm một nửa khả năng hồi máu. Vị trí đứng quyết định tốc độ bình phục: ngoài trời chỉ đạt 50% tốc độ hồi phục so với 80% khi ở trong nhà và 100% khi ngủ say. Thức ăn có tác dụng dược lý: quả mọng hồi +0.3 HP/tick trong 20 tick, ngũ cốc +0.2 HP trong 30 tick, thảo dược +0.8 HP trong 40 tick — sinh vật bị thương sẽ chủ động tìm thảo dược kể cả khi no bụng.

## Tiên đề vật lý tự nhiên (§AQ PH-0)
Năng lượng là đơn vị tiền tệ phổ quát của Flatland. Ánh sáng mặt trời là nguồn thu nhập năng lượng duy nhất: hàm `_sun_factor()` tuân theo chu kỳ ngày đêm — bằng 0 vào ban đêm và đạt đỉnh vào buổi trưa — kiểm soát tốc độ lớn của cây và gieo hạt, nên không loài cây nào có thể lớn tự do trong bóng tối. Mỗi hình dạng cơ thể trả phí tiêu hao theo độ phức tạp hình học (`METABOLIC_COST`): tam giác 1.0×, tứ giác 1.1×, ngũ giác 1.2×, lục giác/quý tộc 1.3×, phụ nữ và tu sĩ 1.5× (tu sĩ tiêu tốn năng lượng để duy trì hào quang). Chữa lành vết thương là quá trình chuyển hóa: mỗi điểm HP phục hồi tiêu tốn 0.5 điểm năng lượng.

## Nhiệt động lực học & Thân nhiệt (§AQ PH-1)
Bản đồ nhiệt độ không gian chia thành các ô 25 đơn vị (`_update_temperature`) dao động theo mùa (Xuân 12°C / Hạ 24°C / Thu 8°C / Đông −4°C) tạo ra các luồng gió lạnh từ phía Tây và gió ấm từ phía Đông, cộng thêm biên độ ngày đêm (±5°C), thời tiết (mưa −2°C, bão −3°C) và ngọn lửa (+60°C trong bán kính 8 đơn vị). Mỗi sinh vật mang thân nhiệt riêng (`body_temp`) cân bằng dần theo môi trường. Đứng trong nhà vật liệu rơm, gỗ, đá giúp cách nhiệt về mức dễ chịu 18°C. Quá nhiệt trên 36°C làm mất máu dẫn đến tử vong do say nắng (`hyperthermia`); lạnh cóng dưới 2°C gây hạ thân nhiệt.

## Gió & Khí quyển (§AQ PH-2)
Bầu trời mang một vector gió (`wind_angle`/`wind_speed`) thay đổi theo thời tiết: lặng gió 0.25, mưa 0.55, bão tố 1.0 và đổi hướng theo mùa. Ngọn lửa tuân theo chiều gió: cả xác suất bén lửa và tốc độ cháy lan nhân với hướng xuôi gió, khiến đám cháy lan nhanh về phía cuối gió.

## Di truyền & Quy luật đẳng cấp (§B)
Giới tính: đa giác là giống đực, đoạn thẳng một chiều là giống cái. Con trai thừa kế số cạnh từ cha: `số cạnh = cha + 1`, giới hạn tối đa 24 cạnh (Trở thành Tu sĩ hình tròn). Con gái luôn là đoạn thẳng. Đột biến cạnh gây ra độ bất đối xứng (`irregularity` từ 0.3 đến 1.0). Tam giác cân có góc đỉnh tăng dần 0.5° mỗi thế hệ; khi đạt ≥60° trở thành tam giác đều và thăng hạng từ Binh lính lên Thợ thủ công. Động cơ hình thái (`morphology_engine`) dùng hệ tọa độ cực $(r_i,\phi_i)$ để nội suy hình thái chuyển tiếp qua các thế hệ.

## Động cơ hình thái & Hình học cực (K∈[3,24])
Bộ gen cực $K\in[3,24]$ lưu trữ cấu trúc SoA gồm bán kính, góc, diện tích, chu vi, mômen quán tính $I_{zz}$, góc nhỏ nhất $\theta_{\min}$ và hệ số bất đối xứng $asym$. Tự động điều chỉnh dung lượng năng lượng, lực đẩy và tính sát thương va chạm. Có cơ chế cứu rỗi (`safeguard_morph_mercy`) tạm hoãn thanh lọc dị hình khi dân số suy kiệt.

## Gương Phản chiếu Bộ gen Tiến hóa & Kiểu hình Trực quan (§BK-8 / §BK-9)
Flatland hợp nhất trực quan hóa bản đồ thành **Gương Phản chiếu Bộ gen Tiến hóa**, nơi thân thể mỗi sinh vật phản chiếu trực tiếp bộ gen sống, đột biến hình thái và huyết mạch dòng dõi trải dài hàng nghìn năm (từ Gen 0 đến Gen 2000+):
- **Phổ màu Kỷ nguyên Huyết thống (Gen 0 → 2000+)**:
  - **Gen 0–4 (Tổ phụ Khai thiên)**: Lam trời sơ nguyên (`#38bdf8`) với Đốm sáng Sáng thế 4 cánh nhấp nháy.
  - **Gen 5–24 (Tiên phong Định cư)**: Lục lam tiên phong (`#06b6d4`).
  - **Gen 25–74 (Gia tộc Định hình)**: Lục bảo vương triều (`#10b981`) kèm Vòng lõi Huyết thống Hoàng kim đồng tâm.
  - **Gen 75–199 (Thời kỳ Đế chế)**: Tím thẫm cổ điển (`#8b5cf6`).
  - **Gen 200–499 (Vương triều Thượng cổ)**: Cánh sen uy nghiêm (`#ec4899`).
  - **Gen 500–999 (Kỷ nguyên Thái dương)**: Hổ phách rực lửa (`#f97316`).
  - **Gen 1000–1999 (Đế vương Vĩnh hằng)**: Vàng kim vương giả (`#facc15`).
  - **Gen 2000+ (Hóa thần Thiên giới)**: Ánh sao Kim cương Tinh tú (`#fef08a`).
- **Vành nhật hoa & Vòng quỹ đạo Hào quang Thiên cổ**:
  - **Gen 50+**: Vành nhật hoa Tinh tú 8 tia sáng (`#fde047`).
  - **Gen 200+**: Nhật hoa Mặt trời Vương giả 12 tia sáng (`#fbbf24`).
  - **Gen 500+**: Vành nhật hoa Tinh vân 16 tia sáng kèm Vòng hào quang quỹ đạo quay quanh (`#f59e0b`).
  - **Gen 1000+**: Nhật hoa Thái dương Vĩnh hằng 20 tia sáng (`#facc15`).
  - **Gen 2000+**: Vành nhật hoa Vũ trụ 24 tia sáng kèm 8 Ngôi sao Kim cương bay quanh theo các phương vị (`#fef08a`).
- **Phản chiếu Đột biến & Dị dạng Hình thái**:
  - Cá thể chuẩn tắc giữ vững đường nét hình học sắc sảo.
  - Lệch nhẹ ($0.08 \le irr < 0.16$) chuyển sắc sang tím và hổ phách.
  - Dị dạng nghiêm trọng ($irr \ge 0.16$) chuyển sắc sang tím thẫm và đỏ thẫm (`#f43f5e`).
  - Đột biến cấp cao ($irr > 0.18$) tỏa Hào quang Phát quang sinh học hỗn loạn với các đỉnh gai micro-dao động.
- **Biểu hiện Đặc tính Vật lý**:
  - **Lưỡi dao Sát thương ($D_{mult}$)**: Ánh kim lóe sáng tại đỉnh nhọn nhất tỷ lệ thuận với độ bén sát thương.
  - **Giáp Quán tính ($I_{zz}$ / Diện tích)**: Vỏ giáp động lực học hai lớp dày dặn gia cố khi quán tính lớn.
  - **Lõi Tinh thể Cổ xưa**: Lõi ngọc hóa cứng cáp theo tuổi đời và niên đại thế hệ.

## Biên niên sử, Lịch sử Thế giới & AI Kể chuyện (§BM)
Flatland trang bị hệ thống phân tích biên niên sử đa thời kỳ và trợ lý viết truyện AI toàn diện:
- **Khoảnh khắc Then chốt & Nhảy mốc thời gian**: 5 ngày biến động lớn nhất (thương vong, thôn tính, ly khai) hiển thị dạng chip nhảy nhanh trên bảng biên niên. Cho phép gõ số tick để nhảy tức thì đến thời khắc lịch sử.
- **Thanh Kỷ nguyên & Đồ thị Dân số**: Điều hướng dòng thời gian với các kỷ nguyên màu sắc (Khởi nguyên, Thời bộ lạc, Kỷ phong kiến, Cực thịnh, Suy vong) cùng biểu đồ dân số đánh dấu khủng hoảng chiến tranh và dịch bệnh.
- **Bảng Kỷ lục & Huyền thoại**: Vinh danh Bộ tộc hiếu chiến nhất, Ngày đẫm máu nhất, Đế chế đông dân nhất, Kiến trúc sư Thần thánh dựng nhiều đền nhất, Đại biến ly khai và các cá thể Anh hùng / Kẻ phản nghịch tiêu biểu.
- **Phân tích Lịch sử**: Ma trận Nhiệt Thù địch giữa các bộ tộc, Biểu đồ Nguyên nhân Tử vong theo kỷ nguyên 10 ngày và Chỉ số Đức tin theo dòng thời gian.
- **Trình Viết truyện AI Tích hợp**: Trực tiếp tạo truyện dạng tiểu thuyết hoặc biên niên sử bằng Gemini 1.5 Flash hoặc OpenAI GPT-4o-mini với khóa API lưu riêng tại trình duyệt người dùng. Hỗ trợ 4 phong cách văn phong (Sử thi, Biên niên, Thần thoại, Bi kịch) bằng cả 3 ngôn ngữ EN, VI, FR.
- **Liên kết Sâu & Thẻ Chia sẻ**: Hỗ trợ đường dẫn `?history=42` để mở trực tiếp ngày thứ 42 hoặc `?clan=7` để mở tiểu sử bộ tộc #7, cùng nút tải ảnh thẻ xã hội chuẩn 1200×630 PNG.

## Phân cấp đẳng cấp & Dị hình (§C)
Đến tuổi trưởng thành, nếu mức độ bất đối xứng vượt ngưỡng (`euthanasia_threshold`), sinh vật sẽ bị xã hội đào thải tiêu hủy; nếu nhẹ hơn sẽ bị giáng cấp làm Binh lính thường. Bảng `CASTE_TRAITS` quy định tuổi thọ, tốc độ, tầm nhìn và độ màu mỡ của từng đẳng cấp.

## Dịch bệnh & Lây nhiễm (§D)
Dịch bệnh tự phát theo tỷ lệ quy định, lây lan trong bán kính tiếp xúc (mùa đông lây nhanh hơn 1.5×), rút cạn năng lượng và trừ máu theo độc lực bệnh. Sinh vật có thể dần bình phục nhờ sức đề kháng tự nhiên hoặc ăn thảo dược.

## Môi trường & Khí hậu (§E)
Thời gian tính theo chu kỳ ngày đêm và 4 mùa trong năm. Ban đêm và sương mù làm giảm tầm nhìn đáng kể. Mùa màng ảnh hưởng trực tiếp đến hệ số thức ăn: Mùa xuân (1.0× thức ăn, +25% sinh sản), Mùa hè (1.2×), Mùa thu (1.0×), Mùa đông (0.5× thức ăn, +50% nguy cơ dịch bệnh). Thời tiết thay đổi ngẫu nhiên giữa Trời quang, Mưa rào, Sương mù và Bão tố.

## Bộ tộc & Trật tự xã hội (§C/I/P/V)
Mỗi ngôi nhà vững chắc khởi nguồn cho một bộ tộc do sinh vật gần tâm nhà nhất làm thủ lĩnh. Con cái mang mã bộ tộc của mẹ. Bộ tộc tôn thờ một trong 8 Linh vật Thần thánh (Vòng tròn Rạng rỡ, Sấm sét Thiên giới, Con mắt Thấu thị, Cự thạch Kiên cường, Vòng xoắn Thần thánh, Bàn cân Vũ trụ, Vết rách Chiều không gian, Ngọn lửa Vĩnh cửu) mang lại bùa chú riêng. Các tộc nhân đóng góp đức tin để thỉnh cầu phép màu mùa màng hoặc xây dựng Đền thờ thiêng liêng.

## Kinh tế thực phẩm & Hệ sinh thái (§H/N/O)
Cây cối phát triển từ mầm non đến trưởng thành và phát tán hạt giống trong bán kính xung quanh. Sinh vật chết để lại xác thịt có thể ăn được hoặc phân hủy nuôi dưỡng đất đai. Hệ thực vật đa dạng gồm 6 loài: Cỏ thông thường, Hạt ngũ cốc, Quả mọng tăng tốc, Thảo dược hồi máu, Nấm hoại sinh và Cây có độc. Thú ăn cỏ hoang dã tự do sinh sôi và là mục tiêu săn mồi của các loài ăn thịt.

## Giao tiếp & Tri thức bầy đàn (§Q/X)
Sinh vật phát tín hiệu gọi ăn hoặc cảnh báo nguy hiểm cho đồng loại. Kinh nghiệm sống (điểm kiếm ăn, mối nguy hiểm, nơi an toàn, kẻ thù) được lưu giữ trong trí nhớ và truyền dạy cho nhau khi trò chuyện. Khi một cá thể bị tấn công, tiếng kêu cứu sẽ triệu tập các chiến binh gần đó đến ứng cứu.

## Chính trị & Bang giao (§AB)
Các bộ tộc thân thiện có thể ký hiệp ước liên minh phòng thủ chung, chia sẻ kho lương thực, hoặc thu cống nạp từ các tộc yếu thế hơn. Thủ lĩnh dũng cảm sẽ tuyên chiến với kẻ thù truyền kiếp, trong khi thủ lĩnh ôn hòa sẽ tìm kiếm hiệp ước hòa bình khi thế lực suy giảm.

## Ăn thịt đồng loại khi tuyệt vọng (§AC)
Khi nạn đói đỉnh điểm khiến năng lượng chạm đáy tuyệt vọng, sinh vật bị ép phải tấn công và ăn thịt các sinh vật yếu thế hoặc kẻ thù để sinh tồn. Kẻ ăn thịt đồng tộc sẽ bị xã hội ruồng bỏ, trở thành kẻ lưu đày và tạo nên mối thù truyền kiếp.

## Cây héo tàn & Tự nhiên luân hồi (§AE)
Cây cối trưởng thành sau một khoảng thời gian sẽ già cỗi và héo úa, giải phóng chất dinh dưỡng cho đất đai xung quanh trước khi biến mất, nhường chỗ cho các mầm sống mới nảy nở.

## Nhà ở & Nơi trú ẩn định cư (§L/N)
Nhà cửa bằng gỗ, rơm hoặc đá che chắn mưa bão và cái lạnh ban đêm. Cửa nhà được thiết kế vừa vặn cho cư dân nhưng quá hẹp đối với các dã thú ăn thịt hung dữ, tạo thành nơi trú ẩn an toàn tuyệt đối.

## Tiến hóa tự chủ & Công cụ (§AG)
Sinh vật sở hữu các thiên hướng tính cách bẩm sinh (`dũng cảm`, `thận trọng`, `vị tha`, `tham lam`, `thám hiểm`, `xây dựng`). Tự động chế tạo và mang theo công cụ: Giáo chiến đấu, Giỏ đựng thức ăn, Túi thảo dược và Vương miện thủ lĩnh. Rèn luyện 4 kỹ năng chính: Canh tác, Chiến đấu, Kiếm ăn và Trị liệu.

## Trao đổi chất & Thể lực chiến đấu (§AH)
Nhu cầu năng lượng thay đổi theo giai đoạn phát triển: trẻ nhỏ tiêu thụ ít hơn 55%, thiếu niên ít hơn 25%. Va chạm chiến trận làm tiêu hao thể lực; kiệt sức sẽ khiến đòn đánh giảm 30% hiệu lực sát thương.

## Trí tuệ bầy đàn Utility AI (§AL)
Hệ thống trí tuệ nhân tạo đa mục tiêu tính toán điểm số sinh tồn, nghĩa vụ đẳng cấp và tín hiệu đồng loại. Sinh vật lập bản đồ tư duy với các tọa độ nhà, vùng thức ăn và điểm tuần tra; phối hợp tác chiến theo đội hình chiến thuật kỷ luật.

## Đa dạng sinh học & Dược tính (§AM)
Hạt vàng cung cấp nguồn năng lượng no lâu; Quả mọng ban tặng sự dẻo dai bứt tốc; Thảo dược giải độc và làm lành vết thương; Nấm phân hủy phát triển tươi tốt quanh xác chết và mùa đông giá rét.

## Giao diện dòng lệnh TUI (§AI)
Bộ điều khiển giao diện terminal đầy đủ gắn trực tiếp vào thế giới đang chạy, hỗ trợ bám sát góc nhìn sinh vật, lọc biên niên sử sự kiện và điều chỉnh luật chơi trực tiếp.

## Mạng nơ-ron hồi quy Elman & Động cơ tiến hóa (BA)
Mỗi sinh vật mang một mạng nơ-ron Elman RNN thu nhỏ (16 đầu vào cảm biến → 12 nơ-ron ẩn → 7 đầu ra vận động với 295 trọng số `float32`). Vận hành song song ở tần số 15 Hz, tiếp nhận thông tin thị giác raycast, âm thanh, mùi hương và trạng thái nội tại để tự học cách sinh tồn và truyền lại bộ gen ưu việt cho đời sau.
"""

HOW_IT_WORKS_FR = r"""
# Fonctionnement du monde Flatland

**La Sphère (Modèle divin) :** La Sphère (Dieu tridimensionnel) édicte les *lois naturelles* depuis Spaceland et n'intervient jamais directement sur le destin d'un être individuel. Tout le reste émerge spontanément.

## Le tick déterministe
`s = Simulation(Config(seed))` → `s.step()` est rigoureusement déterministe (un seul générateur pseudo-aléatoire `random.Random` par monde). Une même graine produit toujours le même univers. Ordre d'exécution de chaque tick (`backend/app/simulation/core.py` `Simulation.step()`) : météo → croissance végétale → mise à jour spatiale → action des créatures → propagation des maladies → combats et guerres → reproduction → relations diplomatiques → régulation des plantes → décomposition des cadavres → colonies → incrément tick+=1. Le moteur s'exécute sur un thread dédié (`SimEngine`) avec sérialisation sans verrou (lockless), diffusant les instantanés via WebSocket `state` à chaque tick.

## Cycle de vie & Stades de développement (§A)
L'âge en ticks s'additionne à l'espérance de vie propre à chaque caste (de 4 800 ticks pour une Femme à 9 000 ticks pour un Prêtre). Les stades se divisent selon le ratio `âge/longévité` : Nourrisson (<15 %), Juvénile (<30 %), Adulte (<75 %), Aîné (≥75 %). L'âge influe sur la vitesse et la portée visuelle (nourrisson 0.6×, aîné 0.85×) ainsi que sur la fertilité (aîné ×0.5). Les causes de trépas sont : `starvation` (inanition), `old_age` (vieillesse), `euthanasia` (purge d'irrégularité), et `disease` (maladie).

## Noyau de vitalité (§AT-4 H-0)
La vie (PV) est une ressource dynamique et non une constante. La régénération exige un excédent calorique : sous 40 % de l'énergie maximale (`HEALTH_REGEN_MIN_ENERGY`), les plaies cessent de cicatriser, éveillé comme endormi. Le repos abrité soigne à raison de `0.15×rest_recovery_mult`, tandis que la guérison éveillée est de `0.1/tick`. Sous 20 % d'énergie, l'organisme s'autocannibale : perte de `−0.05` PV/tick (`HEALTH_SELF_DRAIN_*`) jusqu'à ce que mort s'ensuive. L'affaiblissement ralentit l'allure (`HEALTH_SPEED_TIERS`) : PV <80 vitesse ×0.95, <60 ×0.85, <40 ×0.70, <20 ×0.50. Les corps malades ne peuvent procréer : l'accouplement requiert `health ≥ REPRO_MIN_HEALTH` (50 PV), freinant les naissances lors d'une épidémie sans altérer les lois de fertilité.

## Variété des blessures & Économie des soins (§AT-4 H-1)
La faim chronique ronge : rester sous 20 % d'énergie plus de 30 ticks draine `0.08` PV/tick (cause `exhaustion`). La vieillesse use : les aînés perdent passivement `0.02` PV/tick. La maladie trouble le regard et émousse les récoltes (−20 % de cueillette sous 60 PV, −50 % sous 30 PV). Les blessés graves (<30 PV) n'engagent jamais de duel. Les coups violents (>15 dégâts) infligent une blessure persistante (50 à 100 ticks) diminuant de moitié les soins et entravant l'allure. L'emplacement physique est déterminant : soigner en extérieur n'est efficace qu'à 50 % comparativement à 80 % dans une maison et 100 % durant le sommeil abrité. Les baies soignent +0.3 PV/tick pendant 20 ticks, les céréales +0.2 PV sur 30 ticks et les herbes médicinales +0.8 PV sur 40 ticks.

## Axiomes physiques (§AQ PH-0)
L'énergie est la monnaie universelle de Flatland. La lumière solaire est l'unique apport d'énergie : la fonction `_sun_factor()` suit le cycle solaire (nulle la nuit, maximale à midi) et gouverne la photosynthèse et la dispersion des graines. Chaque créature paye un entretien métabolique selon sa complexité géométrique (`METABOLIC_COST`) : triangles 1.0×, carrés 1.1×, pentagones 1.2×, hexagones et nobles 1.3×, femmes et prêtres 1.5×. Cicatriser consomme de l'énergie : chaque point de vie régénéré coûte 0.5 unité d'énergie.

## Thermodynamique & Température corporelle (§AQ PH-1)
Une grille thermique de 25 unités relaxe chaque tick vers la température saisonnière (Printemps 12°C / Été 24°C / Automne 8°C / Hiver −4°C), animée par des fronts froids venant de l'ouest et chauds de l'est, les variations nycthémérales (±5°C), les intempéries (pluie −2°C, orage −3°C) et la chaleur des feux (+60°C dans un rayon de 8 unités). Les corps s'équilibrent thermiquement avec leur milieu. Les demeures de paille, bois ou pierre isolent les résidents vers un climat tempéré de 18°C. Dépasser 36°C entraîne une hyperthermie fatale ; chuter sous 2°C provoque une hypothermie sévère.

## Vent & Propagation du feu (§AQ PH-2)
Le vent souffle selon un vecteur dynamique (`wind_angle`/`wind_speed`) influencé par la météo : brise calme 0.25, averse 0.55, rafales de tempête 1.0. Le feu suit rigoureusement le vent : propagation et allumage sont multipliés dans le sens du vent, emportant les taillis sous le vent à grande vitesse.

## Hérédité des lois naturelles (§B)
Dimorphisme : les polygones sont mâles, les segments de droite sont femelles. Les fils héritent du nombre de côtés du père plus un : `côtés = père + 1`, plafonné à 24 côtés (devenant ainsi un Prêtre quasi-circulaire). Les filles demeurent des segments unidimensionnels. Les mutations introduisent des asymétries (`irregularity`). Les triangles isocèles voient leur angle au sommet croître de 0.5° par génération ; à 60°, ils deviennent équilatéraux et sont anoblis en Artisans. Le moteur morphologique polarisé $(r_i,\phi_i)$ simule les transitions organiques continues.

## Moteur de morphologie & Physique géométrique (K∈[3,24])
Génome sous forme vectorisée SoA comprenant rayons polaires, angles, superficie, périmètre, moment d'inertie $I_{zz}$ et asymétrie. Les attributs physiques modulent la capacité énergétique, l'impulsion motrice et la force de frappe lors des collisions SAT. Le protocole de clémence (`safeguard_morph_mercy`) suspend l'euthanasie lorsque la population s'effondre.

## Miroir Génomique Évolutif & Phénotypes Visuels (§BK-8 / §BK-9)
Flatland unifie la visualisation cartographique en un **Miroir Génomique Évolutif** où chaque créature reflète dynamiquement son génome vivant, ses mutations morphologiques et sa lignée générationnelle à travers les millénaires (de la Gén 0 à la Gén 2000+) :
- **Spectre des Époques Générationnelles (Gén 0 → 2000+)** :
  - **Gén 0–4 (Fondateurs de la Genèse)** : Cyan ciel primordial (`#38bdf8`) avec étincelle de genèse à 4 branches.
  - **Gén 5–24 (Pionniers)** : Aqua d'exploration précoce (`#06b6d4`).
  - **Gén 25–74 (Dynasties formatrices)** : Jade dynastique (`#10b981`) avec anneau central doré concentrique.
  - **Gén 75–199 (Ères impériales)** : Violet classique impérial (`#8b5cf6`).
  - **Gén 200–499 (Souverains anciens)** : Magenta souverain (`#ec4899`).
  - **Gén 500–999 (Empires solaires)** : Braise solaire millénaire (`#f97316`).
  - **Gén 1000–1999 (Souverains des éons)** : Or souverain (`#facc15`).
  - **Gén 2000+ (Transcendants célestes)** : Étoile de diamant stellaire céleste (`#fef08a`).
- **Couronnes Millénaires & Halos Orbitaux** :
  - **Gén 50+** : Couronne stellaire céleste à 8 rayons (`#fde047`).
  - **Gén 200+** : Couronne solaire souveraine à 12 rayons (`#fbbf24`).
  - **Gén 500+** : Couronne astrale radieuse à 16 rayons avec anneau orbital en pointillés (`#f59e0b`).
  - **Gén 1000+** : Couronne solaire des éons à 20 rayons (`#facc15`).
  - **Gén 2000+** : Couronne cosmique stellaire à 24 rayons avec 8 étoiles de diamant en orbite (`#fef08a`).
- **Expression des Mutations Génomiques & Aberrations** :
  - Les citoyens orthodoxes conservent des contours géométriques nets.
  - Les dérives légères ($0,08 \le irr < 0,16$) décalent la teinte vers le violet et l'ambre.
  - Les aberrations sévères ($irr \ge 0,16$) virent au magenta profond et au rouge cramoisi (`#f43f5e`).
  - Les mutants radicaux ($irr > 0,18$) rayonnent d'une aura bioluminescente chaotique.
- **Traits Physiques & Armures** :
  - **Lames acérées ($D_{mult}$)** : Éclat métallique scintillant au sommet le plus aigu.
  - **Armure d'inertie ($I_{zz}$ / Surface)** : Double coque cinétique épaisse pour les corps à forte inertie.
  - **Noyau cristallin ancestral** : Patine interne durcie avec l'âge et la lignée.

## Histoire du Monde, Chroniques & Récits par IA (§BM)
Flatland propose une suite historiographique, analytique et de génération de récits par IA :
- **Moments Majeurs & Saut Temporel** : Les 5 jours les plus tumultueux (pertes, conquêtes, schismes) sont mis en avant au-dessus du flux chronologique. Possibilité de sauter instantanément à n'importe quel tick précis.
- **Barre d'Époques & Courbe Démographique** : Navigation fluide à travers les ères de Flatland (Genèse, Âge des Tribus, Époque Féodale, Zénith Classique, Ère de Ruine) superposée d'indicateurs de conflits et de pandémies.
- **Panthéon des Records & Légendes** : Classement historique des plus grandes victoires, du jour le plus meurtrier, du royaume le plus peuplé, des architectes divins et des héros/antagonistes célèbres.
- **Analyses Historiques** : Matrice thermique des rivalités claniques, répartition des causes de mortalité par ères de 10 jours et indice de foi au fil du temps.
- **Générateur de Récits IA Intégré** : Rédaction directe de sagas littéraires via Gemini 1.5 Flash ou OpenAI GPT-4o-mini avec clés API stockées localement dans le navigateur.
- **Liens Profonds & Carte de Partage** : URLs partageables avec `?history=42` ou `?clan=7` et exportation de cartes récapitulatives haute résolution 1200×630 au format PNG.

## Hiérarchie des castes & Irrégularité (§C)
À l'âge adulte, toute créature dont l'asymétrie excède le seuil de conformité est bannie ou euthanasiée pour préserver l'ordre géométrique d'Abbott. Les déviations légères entraînent une rétrogradation dans la caste militaire des Soldats.

## Épidémies & Contagion (§D)
Les maladies émergent spontanément selon un taux d'éclosion, se transmettent par proximité (propagation accrue de 50 % en hiver), consument l'énergie et drainent les points de vie. L'organisme peut guérir grâce à son immunité naturelle ou en absorbant des herbes de soin.

## Environnement & Saisons (§E)
Rythme cadencé par le jour et la nuit ainsi que par les quatre saisons. L'obscurité nocturne et le brouillard réduisent considérablement la vue. Les saisons modulent la flore : Printemps (flore 1.0×, natalité +25 %), Été (flore 1.2×), Automne (flore 1.0×), Hiver (flore 0.5×, morbidité épidémique +50 %).

## Clans & Organisation sociale (§C/I/P/V)
Chaque maison permanente fonde un clan autonome mené par la créature la plus proche de son foyer. Les descendants héritent du clan de leur mère. Les clans vénèrent l'un des 8 Avatars Sacrés de la Sphère conférant des bénédictions uniques (Cercle Rayonnant, Frappe Céleste, Sommet Omniscient, Monolithe Indomptable, Spirale Sacrée, Balances Cosmiques, Brèche Dimensionnelle, Foyer Éternel).

## Économie alimentaire & Botanique (§H/N/O)
Les plantes germent, mûrissent et dispersent leurs graines à proximité. Les défunts laissent des dépouilles nutritives qui fertilisent le sol environnant. Six espèces végétales coexistent : l'Herbe commune, les Céréales dorées, les Baies revigorantes, les Herbes curatives, les Champignons décomposeurs et les Plantes vénéneuses. Les herbivores sauvages broutent librement et servent de proies aux prédateurs.

## Communication & Transmission du savoir (§Q/X)
Les créatures émettent des signaux d'appel au festin ou d'alarme. L'expérience acquise (points d'eau et de cueillette, dangers, abris sûrs, clans ennemis) est mémorisée et partagée lors des interactions de groupe. Tout individu agressé appelle à l'aide, mobilisant les guerriers alliés dans le périmètre.

## Géopolitique & Alliances (§AB)
Les clans bienveillants forgent des pactes de défense mutuelle, partagent leurs greniers à provisions ou soumettent des clans rivaux au versement de tributs réguliers. Les chefs belliqueux déclarent des guerres territoriales tandis que les pacificateurs négocient des trêves en période de disette.

## Cannibalisme de désespoir (§AC)
Lorsque la famine menace l'existence même de la colonie et que l'énergie chute à zéro, la loi de la faim pousse les plus désespérés à dévorer les blessés ou les captifs ennemis. Cet acte odieux entraîne le bannissement immédiat du transgresseur, créant une lignée de parias impitoyables.

## Décomposition naturelle (§AE)
Les végétaux arrivés au terme de leur existence flétrissent, brunissent et restituent leurs nutriments au terreau avant de s'effacer, laissant le champ libre à une nouvelle génération de pousses vivaces.

## Habitats & Colonies (§L/N)
Les maisons de pierre, de bois ou de chaume offrent un refuge contre les intempéries et les rigueurs de la nuit. Leurs portes étroites laissent passer les citoyens tout en barrant l'accès aux féroces carnivores sauvages.

## Évolution autonome & Outils (§AG)
Les citoyens développent des tempéraments héréditaires (`brave`, `prudent`, `altruiste`, `avare`, `explorateur`, `bâtisseur`). Ils confectionnent et s'équipent d'outils : lances militaires, paniers de récolte, onguents de soin et couronnes royales, tout en se perfectionnant dans quatre métiers essentiels.

## Métabolisme par stade & Endurance (§AH)
Les dépenses caloriques s'adaptent à l'âge : les nourrissons dépensent 55 % d'énergie en moins, les juvéniles 25 % en moins. Les affrontements guerriers épuisent la vigueur ; la fatigue réduit la force des coups de 30 %.

## Intelligence collective Utility AI (§AL)
Le système d'intelligence artificielle à utilités multiples évalue en temps réel les impératifs de survie, les devoirs de caste et les signaux d'urgence. Les créatures établissent une carte mentale de leur territoire et adoptent des formations tactiques disciplinées en temps de guerre.

## Écologie botanique & Diététique (§AM)
Les Céréales apportent un apport calorique durable ; les Baies procurent une poussée d'accélération ; les Herbes purifient les infections ; les Champignons prospèrent sur les décombres et bravant le gel hivernal.

## Interface terminale TUI (§AI)
Une console Textual complète s'arrime à l'univers en cours d'exécution, permettant de suivre chaque sujet, d'examiner le registre historique et d'ajuster les lois physiques en direct.

## Moteur neuronal Elman & Évolution continue (BA)
Chaque individu est doté d'un réseau récurrent Elman RNN autonome (16 entrées sensorielles → 12 neurones cachés → 7 sorties motrices régies par 295 poids `float32`). Cadencé à 15 Hz, il traite raycasts géométriques, sons et effluves pour s'adapter à son environnement et transmettre ses acquis aux générations futures.
"""

HOW_IT_WORKS_MD_I18N = {
    "en": HOW_IT_WORKS_EN,
    "vi": HOW_IT_WORKS_VI,
    "fr": HOW_IT_WORKS_FR,
}


# ---------------------------------------------------------------------
# Configuration & ops (CONFIG_OPS_MD_I18N)
# ---------------------------------------------------------------------

CONFIG_OPS_EN = """
# Configuration & ops

## Env vars (`FLATWORLD_*`)
| Variable | Default | Description |
|---|---|---|
| `FLATWORLD_WIDTH` | `400` | World width (grid units) |
| `FLATWORLD_HEIGHT` | `300` | World height |
| `FLATWORLD_BOUNDARY` | `wrap` | `wrap` or `clamp` |
| `FLATWORLD_SEED` | `42` | RNG seed |
| `FLATWORLD_TICK_RATE` | `10` | Ticks per second |
| `FLATWORLD_DB` | `backend/flatworld.db` | SQLite path |
| `FLATWORLD_GOD_KEY` | — | Seed/override the god passkey at boot |

## God passkey (auth)
`POST /api/laws`, `POST /api/presets/{name}`, `POST /api/control` and WebSocket control messages need the god passkey (`X-God-Key` header, `key` field on the socket). No credential yet → any god call answers `409` and the web UI asks to create one (`POST /api/auth/setup`). Lost it? Recover on the server only: `cd backend && uv run python -m app.godkey reset <new>` (or `clear`). The TUI takes no prompt: `./run.sh tui ws://host/ws <passkey>` or export `FLATWORLD_GOD_KEY`. Only a PBKDF2 hash is stored.

## Persistence (`db.py:20`)
SQLite `flatworld.db` (WAL, thread lock). Tables:
- `worlds(id, seed, width, height, boundary, started_at, ended_at)`
- `events(id, world_id, tick, type, entity_id, caste, cause, x, y, payload, created_at)`
- `law_changes(id, world_id, tick, name, value, created_at)`
- `creatures(id, world_id, entity_id, caste, clan_id, generation, mother_id, father_id, born_tick, died_tick)`
- `snapshots(id, world_id, tick, payload, created_at)`

History survives restarts; `reset` closes old world row and opens new.

## Concurrency stance & SimEngine
The simulation core is **strictly deterministic** (one seeded RNG stream, one fixed tick order). Run uvicorn with **1 worker** (more workers = several disconnected worlds, not a faster one). Under `SimEngine` (`main.py:446`), simulation advancement runs on its own dedicated background OS thread. State stepping occurs under `RT.lock` while JSON snapshot serialization runs outside the lock (`advance_world_lockless`), so heavy state dumps and WebSocket broadcasts never block REST endpoints or hold the GIL. Key operational & diagnostic endpoints:
- `GET /healthz` — Live server health, current TPS, memory usage, uptime, and active WebSocket client count.
- `GET /api/perf/telemetry` — Rolling telemetry rings: tick duration, lock wait time, and broadcast latencies.
- `GET /api/analytics/summary` — High-level macro demographics, biomass, and trophic distribution.

## Run & deploy
```bash
./run.sh
# or
cd backend && uv run uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev
```

## Tests
```bash
cd backend && uv run pytest -q
cd backend && uv run pytest tests/test_synergies.py -q
```
"""

CONFIG_OPS_VI = """
# Cấu hình & Vận hành

## Biến môi trường (`FLATWORLD_*`)
| Biến môi trường | Mặc định | Ý nghĩa & Mô tả |
|---|---|---|
| `FLATWORLD_WIDTH` | `400` | Chiều rộng không gian thế giới (đơn vị lưới) |
| `FLATWORLD_HEIGHT` | `300` | Chiều cao không gian thế giới |
| `FLATWORLD_BOUNDARY` | `wrap` | Biên giới vô hạn hình xuyến (`wrap`) hoặc tường chặn (`clamp`) |
| `FLATWORLD_SEED` | `42` | Hạt giống ngẫu nhiên khởi tạo thế giới |
| `FLATWORLD_TICK_RATE` | `10` | Số tick tính toán mô phỏng mỗi giây |
| `FLATWORLD_DB` | `backend/flatworld.db` | Đường dẫn tệp cơ sở dữ liệu SQLite |
| `FLATWORLD_GOD_KEY` | — | Khóa mật mã Thượng đế thiết lập lúc khởi động |

## Khóa mật mã Thượng đế (God Passkey)
Các thao tác `POST /api/laws`, `POST /api/presets/{name}`, `POST /api/control` và thông điệp điều khiển qua WebSocket yêu cầu quyền Thượng đế (thông qua header `X-God-Key` hoặc trường `key` trên socket). Nếu hệ thống chưa có mật mã, API sẽ trả về lỗi `409 Conflict` và giao diện web sẽ yêu cầu khởi tạo (`POST /api/auth/setup`). Nếu quên mật mã, có thể đặt lại trực tiếp trên máy chủ bằng lệnh: `cd backend && uv run python -m app.godkey reset <mật_mã_mới>`. Giao diện TUI có thể nhận mật mã qua lệnh: `./run.sh tui ws://host/ws <passkey>` hoặc biến môi trường `FLATWORLD_GOD_KEY`. Hệ thống chỉ lưu trữ chuỗi băm bảo mật PBKDF2.

## Cơ chế lưu trữ dữ liệu bền vững (`db.py:20`)
Cơ sở dữ liệu SQLite `flatworld.db` chạy ở chế độ ghi nhật ký trước WAL (Write-Ahead Logging) và khóa luồng an toàn. Các bảng dữ liệu chính:
- `worlds`: Thông tin các thế giới (mã số, seed, kích thước, thời điểm bắt đầu/kết thúc).
- `events`: Biên niên sử biến cố thế giới (sinh, tử, thăng hạng, chiến tranh, dịch bệnh).
- `law_changes`: Nhật ký thay đổi các định luật của Thượng đế theo tick.
- `creatures`: Gia phả dòng dõi sinh vật (cha mẹ, thế hệ, thời điểm sinh/tử).
- `snapshots`: Các bản sao lưu trạng thái thế giới để khôi phục khi khởi động lại.

## Kiến trúc luồng & Động cơ SimEngine
Lõi mô phỏng được **thiết kế tất định tuyệt đối**: một luồng số ngẫu nhiên duy nhất, một thứ tự thực thi tick cố định. Chạy uvicorn với **1 worker duy nhất**. Với kiến trúc `SimEngine` (`main.py:446`), việc tính toán mô phỏng diễn ra trên một luồng OS nền chuyên trách độc lập với vòng lặp sự kiện asyncio. Bước tiến thế giới diễn ra dưới khóa `RT.lock` trong khi việc mã hóa JSON snapshot diễn ra bên ngoài khóa (`advance_world_lockless`), giúp các yêu cầu HTTP REST luôn phản hồi tức thì mà không bị nghẽn. Các điểm cuối vận hành & chẩn đoán quan trọng:
- `GET /healthz` — Kiểm tra sức khỏe máy chủ, TPS thời gian thực, dung lượng RAM, thời gian chạy và số client kết nối.
- `GET /api/perf/telemetry` — Vòng đo lường hiệu năng: thời gian tick, thời gian giữ khóa và độ trễ phát sóng.
- `GET /api/analytics/summary` — Tổng hợp dữ liệu vĩ mô nhân khẩu học, sinh khối và chuỗi thức ăn.

## Khởi chạy & Vận hành
```bash
./run.sh
# Hoặc khởi chạy thủ công từng thành phần:
cd backend && uv run uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev
```

## Kiểm thử tự động
```bash
cd backend && uv run pytest -q
cd backend && uv run pytest tests/test_synergies.py -q
```
"""

CONFIG_OPS_FR = """
# Configuration & Exploitation

## Variables d'environnement (`FLATWORLD_*`)
| Variable | Défaut | Description |
|---|---|---|
| `FLATWORLD_WIDTH` | `400` | Largeur du monde (unités de grille) |
| `FLATWORLD_HEIGHT` | `300` | Hauteur du monde |
| `FLATWORLD_BOUNDARY` | `wrap` | Bordure torique continue (`wrap`) ou mur hermétique (`clamp`) |
| `FLATWORLD_SEED` | `42` | Graine pseudo-aléatoire du monde |
| `FLATWORLD_TICK_RATE` | `10` | Fréquence de calcul en ticks par seconde |
| `FLATWORLD_DB` | `backend/flatworld.db` | Chemin de la base de données SQLite |
| `FLATWORLD_GOD_KEY` | — | Clé secrète divine définie au démarrage |

## Clé secrète divine (Authentification)
Les commandes `POST /api/laws`, `POST /api/presets/{name}`, `POST /api/control` et les ordres de contrôle WebSocket requièrent l'en-tête d'authentification divine (`X-God-Key` ou le champ `key` du socket). Si aucune clé n'est encore configurée, le serveur renvoie une erreur `409` et l'interface invite à en définir une (`POST /api/auth/setup`). En cas d'oubli, la réinitialisation s'effectue sur le serveur : `cd backend && uv run python -m app.godkey reset <nouvelle_clé>`. Seul un hachage cryptographique sécurisé PBKDF2 est conservé.

## Persistance des données (`db.py:20`)
Base SQLite `flatworld.db` en mode journalisé WAL avec verrou réentrant thread-safe. Tables principales :
- `worlds` : Cycles d'existence des mondes (graine, dimensions, horodatages).
- `events` : Registre historique des événements (naissances, décès, guerres, épidémies).
- `law_changes` : Journal des modifications de lois par la Sphère.
- `creatures` : Lignées généalogiques complètes de chaque citoyen.
- `snapshots` : Instantanés de sauvegarde permettant de restaurer le monde après redémarrage.

## Architecture des threads & Moteur SimEngine
Le cœur de calcul est **rigoureusement déterministe** : une seule graine pseudo-aléatoire ordonnée tick par tick. Uvicorn doit être exécuté avec **1 seul processus worker**. Avec le moteur `SimEngine` (`main.py:446`), l'avancement de la simulation s'exécute sur son propre thread OS dédié, découplé de la boucle asyncio. Le calcul du tick s'opère sous `RT.lock` tandis que la sérialisation JSON des instantanés s'effectue hors verrou (`advance_world_lockless`), évitant tout blocage des requêtes REST. Points d'accès d'exploitation :
- `GET /healthz` — Santé globale du serveur, TPS réel, consommation mémoire, temps de service et clients connectés.
- `GET /api/perf/telemetry` — Télémétrie de performance : temps de calcul par tick, attente de verrou et latence réseau.
- `GET /api/analytics/summary` — Synthèse macroscopique démographique, biomasse et distribution trophique.

## Exécution & Déploiement
```bash
./run.sh
# Ou lancement direct :
cd backend && uv run uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev
```

## Tests de non-régression
```bash
cd backend && uv run pytest -q
cd backend && uv run pytest tests/test_synergies.py -q
```
"""

CONFIG_OPS_MD_I18N = {
    "en": CONFIG_OPS_EN,
    "vi": CONFIG_OPS_VI,
    "fr": CONFIG_OPS_FR,
}


# ---------------------------------------------------------------------
# Codebase map (CODEBASE_MAP_MD_I18N)
# ---------------------------------------------------------------------

CODEBASE_MAP_EN = """
# Codebase map

## Backend (`backend/app/`)
- `config.py:13` — `Config` dataclass: world geometry, densities, food, corpses, behaviour, life, reproduction, disease, environment, shelter, terrain, society, houses, chronicle. `from_env()` + `tick_interval`.
- `entities.py:1` — `CasteTraits`, `CASTE_TRAITS`, `YIELD_RANK`, `caste_name()`, `Creature` (shape/sides/caste/age/lifespan/health/infected/clan_id/sleeping...), `Food` (growth), `Corpse`, `House` (size/door/clan).
- `world.py:32` — `World` registry + uniform spatial hash (`cell_size`, `rebuild_index`), `delta`/`distance` wrap-aware, `query_radius`.
- `simulation/` — Modular simulation package (§BI, replacing legacy `simulation.py:335`):
  - `core.py` — `Simulation` class, deterministic step loop, SoA slot sync, and cache refreshes.
  - `creature_update.py` — Decomposed 7-phase agent loop (`_creature_movement`, `_creature_feeding`, etc.).
  - `settlement.py` — Housing economy, construction, claims, takeovers, and wall collision.
  - `lifecycle.py` — Spawning, reproduction, birth, death, skill titles, and disease propagation.
  - `ecology.py` — Flora lifecycle, farming, banquets, corpse decomposition, and nutrient cycling.
  - `theology.py` — Faith pools, Sacred Avatars, shrines, miracles, synods, and epiphanies.
  - `society.py` — Clans, diplomacy, war, coalitions, larders, trade caravans, and cannibalism.
  - `serialization.py` — Wire snapshot and delta payload generation.
  - `environment.py` — Weather FSM, wind, temperature grid, elevation, and wildfires.
  - `constants.py` — Lookups, multipliers, names, and avatar configurations.
- `agent_soa.py` — SoA buffers (pos/vel/genomes + morph_radii/angles/k/traits) vectorized.
- `agent_pipeline.py` — Vectorized batch sensory raycasting and movement physics.
- `neural_engine.py` — Micro-Elman RNN forward inference (16→12→7, 295 weights).
- `morphology_engine.py` — Polar geometry SAT collision & physical trait baking.
- `evolution_manager.py` — Annealing λ(g), Abbott templates K3..64, polar crossover.
- `spatial_grid.py` — Vectorized spatial grid for fast proximity queries.
- `analytics.py` — TelemetryRing, macro metrics, demography, biodiversity, timeseries.
- `safeguard_engine.py` — Extinction safeguards & Genesis miracles.
- `density_damping.py` — Soft-cap density damping (ξ).
- `auth.py:1` — `require_god` FastAPI dependency for God passkey PBKDF2 verification (`X-God-Key`).
- `protocol.py:7` — Pydantic wire schemas: `ControlAction`, `ControlMessage`, `EntityState`, `StateMessage`, `HistoryEvent`, `HelloMessage`, `GodLaws`.
- `db.py:1` — SQLite WAL persistence for worlds, events, lineage, and snapshots with write buffer.
- `main.py:1` — FastAPI `app`, `SimEngine` dedicated tick thread, `Hub` broadcaster, REST & WebSocket routes.

## Frontend (`frontend/src/`)
- `App.tsx` — Main application layout, HUD, WebSocket synchronization, mobile drawer tabs.
- `analytics/` — Macro Analytics Engine & Observatory:
  - `Observatory.tsx` — Full-screen macro dashboard container with tabbed views.
  - `MacroOverview.tsx` — Demographics, vital health, biomass & speed sparklines.
  - `SociologyTab.tsx` — Clan hegemony, trade caravans, wars & succession tracking.
  - `EcologyTab.tsx` — Botanical diversity, soil health & trophic pyramid.
  - `CrisisTab.tsx` — Epidemic spread, starvation alerts & disaster log.
  - `MutationLab.tsx` — Morphological phylogeny tree & 2D morphospace scatterplot.
  - `MetricCard.tsx` / `Sparkline.tsx` — Lightweight SVG time-series visualizers.
- `render/CanvasRenderer.tsx` — High-performance 60 FPS batched HTML5 Canvas renderer.
- `render/ClanPanel.tsx` — Live clan settlements, totems, and war records.
- `render/ChronicleFeed.tsx` — Filterable, scrollable real-time event log.
- `render/PlotsPanel.tsx` — Multi-metric population, caste, and trophic sparklines.
- `clan/ClanDetails.tsx` — Clan profile, leader residence, founded day & casualty tracking.
- `history/WorldHistoryModal.tsx` — Daily chronicle digest, major wars, and AI Story export.
- `god/GodPanel.tsx` — Interactive Laws of Nature drawer across 6 macro domains.
- `god/auth.tsx` — God passkey modal dialog and authenticated fetch wrapper (`godFetch`).
- `inspect/Inspector.tsx` — Creature dossier, polar morphology radar, vitals & family tree.
- `wiki/Wiki.tsx` — In-app interactive wiki & API playground.
- `types.ts` — TypeScript definitions mirroring backend protocol schemas.
- `websocket.ts` — Auto-reconnecting WebSocket client.

## Data flow
`SimEngine` (dedicated thread) → `sim.step()` → `sim.snapshot()` (lockless serialization) → `HUB.broadcast` → `ws` → `CanvasRenderer` + `App` state. Client → `ControlMessage` → `apply_control` → `RT.config`/`RT.sim` → DB law_changes. Events → `DB.add_events` + genealogy.
"""

CODEBASE_MAP_VI = """
# Bản đồ mã nguồn

## Cấu trúc Backend (`backend/app/`)
- `config.py:13` — Dataclass `Config`: Hình học thế giới, mật độ sinh vật, thức ăn, xác chết, hành vi bầy đàn, sinh sản, dịch bệnh, môi trường, nhà ở, địa hình, xã hội và biên niên sử. Tự động đọc cấu hình từ biến môi trường qua `from_env()`.
- `entities.py:1` — Định nghĩa các thực thể cốt lõi: `CasteTraits`, `CASTE_TRAITS`, `YIELD_RANK`, `caste_name()`, `Creature` (hình dạng, số cạnh, đẳng cấp, tuổi tác, máu, trạng thái nhiễm bệnh, bang phái, ngủ...), `Food` (độ chín sinh trưởng), `Corpse` (xác chết phân hủy), `House` (nhà ở, cửa ra vào, quyền sở hữu).
- `world.py:32` — Lớp đăng ký thực thể `World` tích hợp lưới băm không gian đồng nhất (`cell_size`, `rebuild_index`), tính toán khoảng cách bao quanh hình xuyến và truy vấn bán kính `query_radius`.
- `simulation/` — Gói động cơ mô phỏng mô-đun hóa (§BI):
  - `core.py` — Lớp điều phối `Simulation`, vòng lặp tick tất định, đồng bộ khe SoA và làm mới bộ nhớ đệm.
  - `creature_update.py` — Vòng lặp hành vi sinh vật 7 giai đoạn phân rã (`_creature_movement`, `_creature_feeding`, v.v.).
  - `settlement.py` — Kinh tế nhà ở, xây dựng, tuyên bố chủ quyền, chiếm nhà và va chạm tường.
  - `lifecycle.py` — Khởi tạo dân số, sinh sản, sinh tử, danh hiệu kỹ năng và lây lan dịch bệnh.
  - `ecology.py` — Vòng đời thực vật, nông nghiệp, yến tiệc, phân hủy xác chết và tái tạo dinh dưỡng.
  - `theology.py` — Quỹ đức tin, 8 Avatar Linh thiêng, đền thờ, phép màu, công đồng và hiển linh.
  - `society.py` — Bang tộc, ngoại giao, chiến tranh, liên minh, kho lương, đoàn buôn và ăn thịt đồng loại.
  - `serialization.py` — Đóng gói dữ liệu snapshot và delta truyền qua mạng.
  - `environment.py` — Máy trạng thái thời tiết, gió, lưới nhiệt độ, độ cao và cháy rừng.
  - `constants.py` — Hằng số bảng tra cứu, hệ số nhân và quy tắc đặt tên.
- `agent_soa.py` — Mảng cấu trúc SoA vector hóa tối ưu bộ nhớ đệm CPU cho hàng ngàn sinh vật.
- `agent_pipeline.py` — Xử lý cảm biến raycast và vật lý chuyển động vector hóa hàng loạt.
- `neural_engine.py` — Mạng nơ-ron hồi quy Elman RNN (16→12→7, 295 trọng số) suy luận trực tiếp.
- `morphology_engine.py` — Động cơ hình thái cực, va chạm SAT đa giác và thuộc tính thể chất.
- `evolution_manager.py` — Quản lý ủ nhiệt hình thái λ(g), khuôn mẫu Abbott K3..64 và lai ghép cực.
- `spatial_grid.py` — Lưới không gian vector hóa phục vụ truy vấn lân cận nhanh chóng.
- `analytics.py` — Vòng telemetry, chỉ số vĩ mô, nhân khẩu học và đa dạng sinh học.
- `safeguard_engine.py` — Cơ chế bảo vệ khỏi tuyệt chủng và Phép màu Khởi nguyên.
- `density_damping.py` — Hãm mềm phụ thuộc mật độ (ξ).
- `auth.py:1` — Cơ chế xác thực FastAPI dependency bảo vệ quyền Thượng đế thông qua chuỗi băm PBKDF2 (`X-God-Key`).
- `protocol.py:7` — Định nghĩa lược đồ dữ liệu mạng Pydantic: `ControlAction`, `ControlMessage`, `EntityState`, `StateMessage`, `HistoryEvent`, `HelloMessage`, `GodLaws`.
- `db.py:1` — Lớp bọc SQLite3 `Database` tối ưu với nhật ký WAL, khóa luồng và bộ đệm ghi nền cho các sự kiện sinh, tử, chiến tranh và snapshot.
- `main.py:1` — Điểm khởi đầu FastAPI `app`, luồng động cơ riêng `SimEngine`, bộ phát sóng WebSocket `Hub`, các tuyến API REST và tài liệu `/wiki`.

## Cấu trúc Frontend (`frontend/src/`)
- `App.tsx` — Bố cục ứng dụng chính, thanh HUD thông số, đồng bộ WebSocket và bảng điều khiển đa năng.
- `analytics/` — Đài thiên văn & Động cơ phân tích vĩ mô (Observatory):
  - `Observatory.tsx` — Khung hiển thị toàn màn hình các bảng phân tích vĩ mô theo thẻ.
  - `MacroOverview.tsx` — Biểu đồ sparkline nhân khẩu học, sinh lực, sinh khối và tốc độ.
  - `SociologyTab.tsx` — Bá quyền bang tộc, đoàn buôn liên bộ tộc, chiến tranh và kế vị.
  - `EcologyTab.tsx` — Đa dạng thực vật, độ màu mỡ đất và tháp sinh thái.
  - `CrisisTab.tsx` — Lây lan dịch bệnh, cảnh báo nạn đói và nhật ký thiên tai.
  - `MutationLab.tsx` — Cây phát sinh hình thái học và biểu đồ phân tán không gian hình thái 2D.
  - `MetricCard.tsx` / `Sparkline.tsx` — Khung hiển thị thẻ chỉ số và biểu đồ đường nhẹ SVG.
- `render/CanvasRenderer.tsx` — Bộ hiển thị HTML5 Canvas đồ họa 60 FPS hiệu năng cao với vẽ hàng loạt (batching).
- `render/ClanPanel.tsx` — Bảng hiển thị thông tin bang phái trực tiếp, cây totem linh vật và chiến tích lịch sử.
- `render/ChronicleFeed.tsx` — Dòng sự kiện biên niên sử thời gian thực có bộ lọc thông minh.
- `render/PlotsPanel.tsx` — Biểu đồ sparkline theo dõi dân số, tỷ lệ đẳng cấp và chuỗi thức ăn sinh thái.
- `clan/ClanDetails.tsx` — Hồ sơ chi tiết bang tộc, nơi cư ngụ của thủ lĩnh và thống kê thương vong.
- `history/WorldHistoryModal.tsx` — Nhật ký tóm tắt từng ngày, các cuộc đại chiến và tính năng xuất truyện AI Story.
- `god/GodPanel.tsx` — Bảng điều khiển định luật tự nhiên tương tác với 7 cấu hình mẫu tuyển chọn.
- `god/auth.tsx` — Hộp thoại xác thực mật mã Thượng đế và hàm gọi API bảo mật `godFetch`.
- `inspect/Inspector.tsx` — Bảng hồ sơ cá nhân sinh vật, radar hình thái cực, chỉ số sinh tồn và cây gia phả.
- `wiki/Wiki.tsx` — Bách khoa toàn thư tích hợp sẵn trong ứng dụng và công cụ thử nghiệm API.
- `types.ts` — Định nghĩa kiểu TypeScript ánh xạ chính xác lược đồ giao thức backend.
- `websocket.ts` — Trình khách WebSocket tự động kết nối lại khi gián đoạn mạng.

## Luồng dữ liệu hệ thống
`SimEngine` (luồng riêng) → `sim.step()` → `sim.snapshot()` (tuần tự hóa không khóa) → `HUB.broadcast` → `ws` → `CanvasRenderer` + Trạng thái React `App`. Phía người dùng gửi `ControlMessage` → `apply_control` → Cập nhật cấu hình mô phỏng → Lưu nhật ký luật vào DB. Biến cố thế giới → `DB.add_events` + Lưu hồ sơ gia phả.
"""

CODEBASE_MAP_FR = """
# Carte du code source

## Architecture Backend (`backend/app/`)
- `config.py:13` — Dataclass `Config` : Géométrie du monde, densités, nourriture, dépouilles, dynamique de groupe, reproduction, épidémies, météo, abris, maisons et annales. Détection automatique des variables d'environnement via `from_env()`.
- `entities.py:1` — Définition des entités fondamentales : `CasteTraits`, `CASTE_TRAITS`, `YIELD_RANK`, `caste_name()`, `Creature` (géométrie, côtés, caste, âge, santé, infection, clan, sommeil...), `Food` (maturation), `Corpse` (dépouille), `House` (dimensions, porte, clan).
- `world.py:32` — Registre spatial `World` avec table de hachage spatiale uniforme (`cell_size`, `rebuild_index`), calcul des distances toriques et requêtes de voisinage `query_radius`.
- `simulation/` — Moteur de simulation modulaire décomposé (§BI) :
  - `core.py` — Classe maîtresse `Simulation`, boucle de tick déterministe et synchronisation SoA.
  - `creature_update.py` — Pipeline d'agent en 7 étapes décomposées (`_creature_movement`, `_creature_feeding`, etc.).
  - `settlement.py` — Économie de l'habitat, construction, revendications et franchissement des portes.
  - `lifecycle.py` — Génération d'agents, reproduction, naissance, mort, compétences et propagation des épidémies.
  - `ecology.py` — Cycle végétal, agriculture, banquets, décomposition et recyclage des nutriments.
  - `theology.py` — Réserves de foi, 8 Avatars Sacrés, sanctuaires, miracles, synodes et épiphanies.
  - `society.py` — Clans, diplomatie, guerres, coalitions, greniers, caravanes marchandes et cannibalisme.
  - `serialization.py` — Encodage des trames d'instantanés complets et différentiels (deltas).
  - `environment.py` — Météo, dynamique des vents, grille thermique et incendies.
  - `constants.py` — Constantes de simulation, tables de coefficients et générateurs de noms.
- `agent_soa.py` — Architecture SoA vectorisée pour le traitement en cache de milliers d'agents simultanés.
- `agent_pipeline.py` — Pipeline de perception par lancer de rayons et physique vectorisée par lots.
- `neural_engine.py` — Réseau récurrent Elman RNN (16→12→7, 295 poids) pour le contrôle moteur.
- `morphology_engine.py` — Moteur de morphologie polaire, collisions SAT et calcul des propriétés physiques.
- `evolution_manager.py` — Recuit morphologique λ(g), gabarits géométriques d'Abbott K3..64 et enjambement polaire.
- `spatial_grid.py` — Grille spatiale vectorisée pour requêtes de proximité rapides.
- `analytics.py` — Télémétrie en anneau, métriques macro, démographie et biodiversité.
- `safeguard_engine.py` — Protocoles de sauvegarde contre l'extinction et Miracles de la Genèse.
- `density_damping.py` — Amortissement dynamique de surpopulation (ξ).
- `auth.py:1` — Dépendance de sécurité FastAPI vérifiant la clé divine par hachage PBKDF2 (`X-God-Key`).
- `protocol.py:7` — Schémas réseau Pydantic : `ControlAction`, `ControlMessage`, `EntityState`, `StateMessage`, `HistoryEvent`, `HelloMessage`, `GodLaws`.
- `db.py:1` — Couche SQLite3 `Database` optimisée avec WAL, verrous réentrants et écriture différée en arrière-plan.
- `main.py:1` — Point d'entrée FastAPI `app`, moteur dédié `SimEngine`, diffusion WebSocket `Hub`, routes REST et `/wiki`.

## Architecture Frontend (`frontend/src/`)
- `App.tsx` — Agencement principal de l'application, bandeau HUD, synchronisation WebSocket et volets d'onglets.
- `analytics/` — Observatoire & Moteur d'analyses macroscopiques :
  - `Observatory.tsx` — Conteneur plein écran des tableaux de bord analytiques par onglets.
  - `MacroOverview.tsx` — Graphiques étincelles démographiques, santé, biomasse et vitesse.
  - `SociologyTab.tsx` — Hégémonie des clans, caravanes de troc, guerres et successions.
  - `EcologyTab.tsx` — Diversité botanique, régénération des sols et pyramide trophique.
  - `CrisisTab.tsx` — Évolution des épidémies, alertes famines et catastrophes naturelles.
  - `MutationLab.tsx` — Arbre phylogénétique morphologique et nuage de points morphospécifique 2D.
  - `MetricCard.tsx` / `Sparkline.tsx` — Cartes métriques légères avec visualisations SVG.
- `render/CanvasRenderer.tsx` — Moteur de rendu HTML5 Canvas à 60 FPS avec tracé vectoriel trigonométrique par lots.
- `render/ClanPanel.tsx` — Affichage des colonies de clans en temps réel, totems sacrés et états de guerre.
- `render/ChronicleFeed.tsx` — Fil d'actualité des événements historiques avec filtres contextuels.
- `render/PlotsPanel.tsx` — Graphiques étincelles (sparklines) de la population, des castes et de la chaîne trophique.
- `clan/ClanDetails.tsx` — Fiche détaillée du clan, manoir du chef et bilan des pertes au combat.
- `history/WorldHistoryModal.tsx` — Résumé historique quotidien, grandes guerres et exportation de récit littéraire IA.
- `god/GodPanel.tsx` — Tiroir interactif des lois de la nature avec 7 préréglages de mondes.
- `god/auth.tsx` — Boîte de dialogue d'authentification divine et adaptateur de requêtes `godFetch`.
- `inspect/Inspector.tsx` — Dossier biologique du citoyen, radar morphologique polaire, constantes et généalogie.
- `wiki/Wiki.tsx` — Encyclopédie interactive intégrée et banc d'essai d'API.
- `types.ts` — Interfaces TypeScript calquées sur les schémas du protocole serveur.
- `websocket.ts` — Client WebSocket à reconnexion automatique résiliente.

## Flux de données
`SimEngine` (thread dédié) → `sim.step()` → `sim.snapshot()` (sérialisation sans verrou) → `HUB.broadcast` → `ws` → `CanvasRenderer` + État React `App`. Client → `ControlMessage` → `apply_control` → Mise à jour de la simulation → Journalisation en base. Événements → `DB.add_events` + Généalogie.
"""

CODEBASE_MAP_MD_I18N = {
    "en": CODEBASE_MAP_EN,
    "vi": CODEBASE_MAP_VI,
    "fr": CODEBASE_MAP_FR,
}


# ---------------------------------------------------------------------
# Data model & protocol (DATA_MODEL_MD_I18N)
# ---------------------------------------------------------------------

DATA_MODEL_EN = """
# Data model & protocol

## Entities (in-memory)
- `Creature` (`entities.py:95`): `id`, `x`, `y`, `angle`, `shape` polygon|line, `sides`, `caste`, `radius`, `age`, `lifespan`, `stage` infant|juvenile|adult|elder, `irregularity`, `health` 0–100, `infected`, `sex` male|female, `mother_id`/`father_id`, `clan_id`/`clan_color`, `sleeping`/`indoors`, `generation`, `born_tick`, `energy`, `status` hungry/starving, `meals`.
- `Food` (`entities.py:158`): `x`, `y`, `growth` 0–1.
- `Corpse` (`entities.py:170`): `x`, `y`, `ttl`, `energy`.
- `House` (`entities.py:184`): `x`, `y`, `size`, `door_width`/`door_side`/`door_offset`, `clan_id`/`clan_color` (settlement), `is_ruin`/`abandoned_ticks`, `takeover_tick` (last hostile takeover, §AT-3 render flash); ruin after `house_decay_ticks` (`config.py:113`), `settlement`/`ruin`/`takeover` events.
- Terrain: `fertile: [{x,y,r}]`, `rocks: [{x,y,r}]` in snapshot.

## Wire schemas (`protocol.py`)
- `EntityState` (`protocol.py:27`): `id`, `kind` creature|food|house|corpse, `x`/`y`/`angle`, plus optional fields above.
- `StateMessage` (`protocol.py:62`): `tick`, `seed`, `width`/`height`/`boundary`, `population`, `entities`, `clans`, `creatures_alive`/`creatures_dead`/`dead_by_cause`, `infected_count`, `time_of_day`/`day`/`season`/`weather`, `terrain_fertile`/`terrain_rocks`, `relations`, `events`, plus periodic 1 Hz `analytics` frame (coalesced macro metrics).
- `HistoryEvent` (`protocol.py:86`): `type` death|birth|promotion|demotion|outbreak|recovery|bloom|alliance|rivalry|predation|war|ruin|settlement, `tick`, `entity_id`, `caste`, `cause`, `x`/`y`, `payload` (parents/sides/generation/clan_id etc).
- `HelloMessage` (`protocol.py:99`): `seed`, `tick_rate`, `width`/`height`/`boundary`.
- `ControlMessage` (`protocol.py:22`): `action` pause|resume|step|reset|set_speed + `value`.

## WebSocket flow
Server → client: `{"type":"hello", ...}` then `{"type":"state", ...}` each tick (with coalesced 1 Hz analytics frames for the Observatory). Client → server: `{"action":"pause"|"resume"|"step"|"reset"|"set_speed", "value":...}` (`main.py`).
"""

DATA_MODEL_VI = """
# Mô hình dữ liệu & Giao thức mạng

## Các thực thể trong bộ nhớ (In-memory Entities)
- `Creature` (`entities.py:95`): `id`, tọa độ `x`, `y`, góc quay `angle`, hình dáng `shape` (đa giác `polygon` hoặc đoạn thẳng `line`), số cạnh `sides`, đẳng cấp `caste`, bán kính `radius`, số tuổi `age`, tuổi thọ `lifespan`, giai đoạn `stage` (sơ sinh `infant`, thiếu niên `juvenile`, trưởng thành `adult`, lão niên `elder`), độ bất đối xứng `irregularity`, sinh lực `health` (0–100), nhiễm bệnh `infected`, giới tính `sex`, `mother_id`/`father_id`, mã bang tộc `clan_id`/màu cờ `clan_color`, đang ngủ `sleeping`/trong nhà `indoors`, thế hệ `generation`, thời điểm sinh `born_tick`, năng lượng `energy`, trạng thái đói `status`, số bữa ăn `meals`.
- `Food` (`entities.py:158`): Vị trí `x`, `y`, độ chín sinh trưởng `growth` từ 0.15 đến 1.0.
- `Corpse` (`entities.py:170`): Vị trí `x`, `y`, thời gian phân hủy còn lại `ttl`, lượng năng lượng cung cấp `energy`.
- `House` (`entities.py:184`): Vị trí `x`, `y`, kích thước nhà `size`, độ rộng cửa `door_width`, cạnh đặt cửa `door_side`, bang tộc sở hữu `clan_id`/`clan_color`, dấu hiệu phế tích `is_ruin`, số tick bị bỏ hoang `abandoned_ticks`, thời điểm bị chiếm đoạt `takeover_tick`.
- Địa hình bản đồ (Terrain): Các khu đất màu mỡ `fertile: [{x,y,r}]` và các mỏ đá cản trở `rocks: [{x,y,r}]` được đóng gói trong snapshot.

## Cấu trúc dữ liệu mạng truyền tải (`protocol.py`)
- `EntityState` (`protocol.py:27`): `id`, loại thực thể `kind` (`creature` | `food` | `house` | `corpse`), tọa độ `x`/`y`, hướng quay `angle`, kèm các trường trạng thái sinh học bổ trợ.
- `StateMessage` (`protocol.py:62`): Thông điệp trạng thái toàn thế giới gửi mỗi tick gồm: số tick `tick`, hạt giống `seed`, kích thước bản đồ `width`/`height`/`boundary`, tổng dân số `population`, danh sách thực thể `entities`, thông tin bang phái `clans`, số sinh vật sống/chết và nguyên nhân tử vong, số ca nhiễm bệnh, thời điểm trong ngày/ngày/mùa/thời tiết, địa hình, ma trận quan hệ ngoại giao, danh sách biến cố mới phát sinh, kèm khung dữ liệu `analytics` định kỳ 1 Hz phục vụ Đài thiên văn.
- `HistoryEvent` (`protocol.py:86`): Bản ghi sự kiện lịch sử gồm: loại sự kiện `type` (tử vong, sinh nở, thăng hạng, giáng cấp, bùng dịch, bình phục, cây nở hoa, liên minh, thù địch, săn mồi, tuyên chiến, phế tích, lập ấp), số tick xảy ra, mã thực thể liên quan, đẳng cấp, nguyên nhân, tọa độ và gói dữ liệu bổ trợ `payload`.
- `HelloMessage` (`protocol.py:99`): Thông điệp chào ban đầu khi kết nối WebSocket thành công: hạt giống `seed`, tốc độ tick `tick_rate`, giới hạn thế giới `width`/`height`/`boundary`.
- `ControlMessage` (`protocol.py:22`): Lệnh điều khiển gửi từ giao diện web lên máy chủ: hành động `action` (`pause` tạm dừng, `resume` tiếp tục, `step` chạy một bước, `reset` làm mới thế giới, `set_speed` chỉnh tốc độ) kèm giá trị số `value`.

## Giao thức đồng bộ WebSocket
Máy chủ gửi về trình duyệt: Gửi `{"type":"hello", ...}` ngay khi kết nối, sau đó liên tục phát sóng `{"type":"state", ...}` theo tần số tick (kèm gói `analytics` 1 Hz cho Đài thiên văn). Trình duyệt gửi lên máy chủ: Gửi gói tin điều khiển `{"action":"pause"|"resume"|"step"|"reset"|"set_speed", "value":...}`.
"""

DATA_MODEL_FR = """
# Modèle de données & Protocole réseau

## Entités en mémoire vive (In-memory Entities)
- `Creature` (`entities.py:95`) : Identifiant `id`, position `x`, `y`, orientation `angle`, morphologie `shape` (`polygon` ou `line`), nombre de côtés `sides`, caste sociale `caste`, rayon `radius`, âge `age`, espérance de vie `lifespan`, stade biologique `stage` (`infant`, `juvenile`, `adult`, `elder`), asymétrie `irregularity`, vitalité `health` (0–100), infection `infected`, sexe `sex`, filiation `mother_id`/`father_id`, appartenance `clan_id`/`clan_color`, état de repos `sleeping`/`indoors`, génération généalogique `generation`, tick de naissance `born_tick`, réserve d'énergie `energy`, statut de faim `status`.
- `Food` (`entities.py:158`) : Coordonnées `x`, `y`, stade de maturation végétale `growth` (de 0.15 à 1.0).
- `Corpse` (`entities.py:170`) : Coordonnées `x`, `y`, durée de décomposition restante `ttl`, énergie nutritive `energy`.
- `House` (`entities.py:184`) : Coordonnées `x`, `y`, superficie `size`, largeur de porte `door_width`, clan propriétaire `clan_id`/`clan_color`, statut de ruine `is_ruin`, dernier assaut hostile `takeover_tick`.
- Relief et géographie : Zones de terre arable `fertile: [{x,y,r}]` et rochers infranchissables `rocks: [{x,y,r}]`.

## Schémas du protocole réseau (`protocol.py`)
- `EntityState` (`protocol.py:27`) : `id`, type `kind` (`creature` | `food` | `house` | `corpse`), coordonnées `x`/`y`, angle, et attributs biologiques optionnels.
- `StateMessage` (`protocol.py:62`) : Données complètes diffusées à chaque tick : numéro de `tick`, graine `seed`, dimensions `width`/`height`/`boundary`, population totale, ensemble des entités actives, clans, statistiques de mortalité, horloge nycthémérale, saison, météo, matrice diplomatique, événements récents et charge utile `analytics` à 1 Hz pour l'Observatoire.
- `HistoryEvent` (`protocol.py:86`) : Événement chronologique typé : décès, naissance, promotion, épidémie, rémission, floraison, alliance, guerre, assaut de colonie avec horodatage en tick et charge utile `payload`.
- `HelloMessage` (`protocol.py:99`) : Message d'accueil émis à l'ouverture du WebSocket : graine, cadence de tick, et limites du monde.
- `ControlMessage` (`protocol.py:22`) : Commande émise par l'utilisateur : `action` (`pause`, `resume`, `step`, `reset`, `set_speed`) accompagnée de son paramètre `value`.

## Flux de synchronisation WebSocket
Serveur vers client : `{"type":"hello", ...}` à la connexion, suivi de flux continus `{"type":"state", ...}` à chaque tick d'horloge (intégrant les trames `analytics` 1 Hz). Client vers serveur : Instructions de régulation divine `{"action":"pause"|"resume"|"step"|"reset"|"set_speed", "value":...}`.
"""

DATA_MODEL_MD_I18N = {
    "en": DATA_MODEL_EN,
    "vi": DATA_MODEL_VI,
    "fr": DATA_MODEL_FR,
}


# ---------------------------------------------------------------------
# Curl Examples (CURL_EXAMPLES_I18N)
# ---------------------------------------------------------------------

CURL_EXAMPLES_EN = """
## Curl playground

```bash
# laws
curl localhost:8000/api/laws
curl -X POST localhost:8000/api/laws -H 'content-type: application/json' -d '{"food_count": 90}' 

# presets (1000-day one click)
curl -X POST localhost:8000/api/presets/sustainable?reset=true
curl -X POST localhost:8000/api/presets/chaos
curl -X POST localhost:8000/api/presets/extinction?reset=true

# state & history
curl localhost:8000/api/state | jq .tick
curl localhost:8000/api/history?limit=5 | jq
curl localhost:8000/api/worlds | jq
curl localhost:8000/api/clans | jq

# control
curl -X POST localhost:8000/api/control -H 'content-type: application/json' -d '{"action":"pause"}'
curl -X POST localhost:8000/api/control -d '{"action":"reset"}'

# websocket (live)
# ws://localhost:8000/ws  → {"type":"hello"} then {"type":"state"} throttled ~30Hz
# send {"action":"pause"} / {"action":"set_speed","value":20}
```
"""

CURL_EXAMPLES_VI = """
## Công cụ dòng lệnh Curl thử nghiệm

```bash
# Truy vấn và thiết lập định luật tự nhiên
curl localhost:8000/api/laws
curl -X POST localhost:8000/api/laws -H 'content-type: application/json' -d '{"food_count": 90}' 

# Áp dụng cấu hình mẫu thế giới 1-chạm (thế giới bền vững 1000 ngày)
curl -X POST localhost:8000/api/presets/sustainable?reset=true
curl -X POST localhost:8000/api/presets/chaos
curl -X POST localhost:8000/api/presets/extinction?reset=true

# Truy vấn trạng thái thế giới và lịch sử biên niên sử
curl localhost:8000/api/state | jq .tick
curl localhost:8000/api/history?limit=5 | jq
curl localhost:8000/api/worlds | jq
curl localhost:8000/api/clans | jq

# Điều khiển mô phỏng thời gian thực
curl -X POST localhost:8000/api/control -H 'content-type: application/json' -d '{"action":"pause"}'
curl -X POST localhost:8000/api/control -d '{"action":"reset"}'

# Kết nối trực tiếp WebSocket
# ws://localhost:8000/ws  → Nhận gói {"type":"hello"} sau đó liên tục nhận {"type":"state"} ~30Hz
# Gửi lệnh điều khiển: {"action":"pause"} hoặc {"action":"set_speed","value":20}
```
"""

CURL_EXAMPLES_FR = """
## Exemples de requêtes interactives Curl

```bash
# Consultation et réglage des lois divines
curl localhost:8000/api/laws
curl -X POST localhost:8000/api/laws -H 'content-type: application/json' -d '{"food_count": 90}' 

# Préréglages en un clic (monde durable de 1000 jours)
curl -X POST localhost:8000/api/presets/sustainable?reset=true
curl -X POST localhost:8000/api/presets/chaos
curl -X POST localhost:8000/api/presets/extinction?reset=true

# État du monde en direct et registre d'histoire
curl localhost:8000/api/state | jq .tick
curl localhost:8000/api/history?limit=5 | jq
curl localhost:8000/api/worlds | jq
curl localhost:8000/api/clans | jq

# Contrôle du temps de la simulation
curl -X POST localhost:8000/api/control -H 'content-type: application/json' -d '{"action":"pause"}'
curl -X POST localhost:8000/api/control -d '{"action":"reset"}'

# Flux WebSocket en direct
# ws://localhost:8000/ws  → Réception de {"type":"hello"} puis du flux {"type":"state"} à ~30Hz
# Envoi de commandes : {"action":"pause"} ou {"action":"set_speed","value":20}
```
"""

CURL_EXAMPLES_I18N = {
    "en": CURL_EXAMPLES_EN,
    "vi": CURL_EXAMPLES_VI,
    "fr": CURL_EXAMPLES_FR,
}
