# God Laws — Flatland Simulation Reference

[![GitHub Repo](https://img.shields.io/badge/GitHub-longphanmn%2Fflws-181717.svg?logo=github)](https://github.com/longphanmn/flws)

> **Landing Page**: [https://longphanmn.github.io/flws-page/](https://longphanmn.github.io/flws-page/)  
> **Source Code**: [https://github.com/longphanmn/flws](https://github.com/longphanmn/flws)  
> **Developed by [Long Phan](mailto:long@minhnhan.in)** ([long@minhnhan.in](mailto:long@minhnhan.in) · Demo: [longphanmn.github.io/flws-web/](https://longphanmn.github.io/flws-web/))  
> Built and refined using **OpenCode** and **Antigravity** · Developed from the core concepts of **Edwin A. Abbott's *Flatland***.

In Flatland, God (The Sphere) sets **universal laws of nature**, never intervening in individual lives. Every law has a specified range, default value, and ecological effect. Laws can be adjusted live via the in-app **⚖ The Sphere (God Panel)** or programmatically via `POST /api/laws` and `POST /api/presets/{name}`.

---

## God Panel Layout & Navigation

The God Panel is organized into two primary top-level sections:
1. **`🎯 Presets` (Curated Worlds)**: Instant one-click simulation profiles (`⚖️ Balance`, `🌿 Sustainable`, `🔮 Theocracy`, `⚔️ Warlords`, `🔥 Chaos`, `💀 Extinction`, `🚀 Boom`) with Live Apply and World Reset options.
2. **`⚖️ Laws of Nature` (Macro Domains)**: Direct fine-tuning across 6 high-level ecological domains consolidated into **13 unified groups** with real-time baseline comparison, instant cross-tab search, modified-only & risk-only filtering, interactive `?` hints, and dual slider controls.

### §BN Modernized Controls & Power Features
- **Consolidated 13 Groups**: Reduced from 28 fragmented sub-groups down to 13 intuitive categories (Food & Agriculture, Ecosystem & Flora, Movement & Lifespan, Reproduction & Caste, Population Safety, Evolution Engine, Disease & Plague, Climate & Shelter, Combat & Survival, Society & Governance, Theology & Avatars, Landscape & Elements, Cosmology & Disasters).
- **Composite Dials**:
  - **Carrying pressure** (0–10 intensity): Proportionally tunes damping steepness, crowding stress, and resource strain in one intuitive dial.
  - **Speciation speed** (Slow / Normal / Fast / Immediate / Custom): Sets morphology start and decay generation milestones.
  - **Shape jitter σ** (0.005–0.20): Simultaneously scales radial ($\sigma_r$) and angular ($\sigma_\phi$) geometric mutation rates.
  - **Plague severity** (Mild / Moderate / Lethal / Custom): Sets outbreak frequency, contagion probability, and lethality.
- **Advanced Accordions**: Collapsible `⚙️ Advanced` drawers keep raw expert parameters out of the way for standard play while remaining fully accessible.
- **Logarithmic-Scale Sliders**: Exponential parameters (`food_lifespan_ticks`, `age_length`, `day_length`, `house_decay_ticks`, `season_length`) use logarithmic curves so fine adjustments at lower ranges are responsive and precise.
- **Master Feature Toggle Cards**: Major subsystem switches (`birth_enabled`, `morphology_annealing_enabled`, `disease_enabled`, `weather_enabled`, `safeguard_enabled`, `theology_enabled`, `war_enabled`, `predation_enabled`) are displayed as loud, prominent status cards with green active glow.
- **Grayed-Out Gated Preview**: Child parameters whose parent feature is disabled remain visible at 45% opacity with clear status badges, ensuring discoverability rather than abruptly vanishing.
- **Plain-Language Zone Badges**: Renamed to `✓ balanced` (green), `⚠ pushed` (amber), and `🔴 risk` (red).
- **Clickable Baseline Markers & Values**: Clicking on the slider baseline marker or default label immediately reverts that specific law back to its baseline.
- **Touch Steppers with Long-Press Repeat**: On touch and desktop, holding down `−` or `+` repeatedly steps values for quick adjustments.
- **Emergency `🆘 Panic Rescue`**: One-click footer button that restores generous food abundance, turns on emergency safeguards, and quells all active plagues, wildfires, and natural disasters.
- **Draft Auto-Save**: In-progress modifications are automatically saved to `localStorage` (`fl_god_laws_draft`); an interactive banner allows restoring or discarding previous sessions.
- **JSON Export & Import**: One-click clipboard export and validated JSON import to share and back up custom law configurations.
- **Session Change Log**: In-session audit drawer tracking all parameter modifications with timestamps and old $\rightarrow$ new values.
- **Undo / Redo Stack**: Multi-level undo/redo via toolbar buttons or keyboard shortcuts (`Cmd/Ctrl+Z`, `Cmd/Ctrl+Shift+Z` / `Ctrl+Y`).
- **Cross-Tab Search & Risk Filter**: Searching queries both presets and laws simultaneously; a dedicated `🔴 Risk only` chip filters directly for parameters pushed to extreme values.

> [!NOTE]
> **Understanding Defaults vs. Balance Preset:**
> The **Default** column in this reference reflects the active default preset (**⚖️ Balance**), which is loaded automatically when a world boots or resets to ensure a flourishing 200–350 multi-generational population. Where the bare dataclass baseline (`Config` in `config.py`) differs from the active **⚖️ Balance** preset, both values are explicitly noted (e.g. `380 (Balance) / 210 (Config bare)`).

---

## 1. Ecology & Survival 🌿

### Food & Energy
| Law Parameter | Type | Default | Ecological Effect & Hint |
|---|:---:|:---:|---|
| `food_count` | Integer | `380` *(Config: 210)* | Target living food abundance across the world (winter reduces, summer boosts). |
| `energy_max` | Float | `100.0` | Maximum metabolic energy capacity an organism can store before full saturation. |
| `energy_start` | Float | `85.0` | Initial metabolic energy endowed to newly created founding creatures. |
| `energy_decay_per_tick` | Float | `0.018` *(Config: 0.025)* | Baseline metabolic burn rate per tick without food intake; shelter and infancy reduce decay. |
| `energy_from_food` | Float | `32.0` | Base energy yield from harvesting a mature plant (berry: 48, grass: 32, mushroom: 24, poison: 8). |
| `food_decay_enabled` | Boolean | `true` | Enables mature plants to naturally wither over time and fertilize the living soil. |
| `food_lifespan_ticks` | Integer | `8000` *(Config: 9000)* | Ticks a mature plant lives before naturally withering into the living soil grid. |
| `soil_depletion_enabled` | Boolean | `true` | Repeated harvesting from the same soil cell temporarily reduces subsequent crop yield. |
| `fertile_patches` | Integer | `-1` | Number of high-yield fertile biome regions generated across the terrain. |
| `fertile_food_bias` | Float | `0.7` | Growth rate multiplier for plants sprouting within fertile agricultural patches. |
| `winter_food_mult` | Float | `0.82` *(Config: 0.50)* | Food growth and abundance multiplier during the winter season. |

### Ecosystem & Biodiversity
| Law Parameter | Type | Default | Ecological Effect & Hint |
|---|:---:|:---:|---|
| `plant_variants_enabled` | Boolean | `true` | Enables botanical diversity across 6 distinct functional plant species. |
| `plant_growth_rate` | Float | `0.065` *(Config: 0.05)* | How fast sprouted plants mature into harvestable food; seasons and rain accelerate growth. |
| `plant_spread_rate` | Float | `0.008` *(Config: 0.006)* | Probability per tick that a mature plant drops seeds into adjacent fertile ground. |
| `nutrient_cycle_rate` | Float | `0.65` | Acceleration of plant growth near decomposing corpses (death nourishes new life). |
| `poison_rate` | Float | `0.008` *(Config: 0.01)* | Chance a new wild sprout is poisonous (-30 HP damage on ingestion). |
| `corpses_enabled` | Boolean | `true` | Fallen creatures leave decomposing organic remains that enrich surrounding soil. |
| `corpse_energy` | Float | `25.0` | Caloric reserve contained in a freshly fallen creature corpse. |
| `corpse_ttl` | Integer | `600` | Ticks before a deceased body fully decomposes into the ground. |

### Hunger & Foraging Sight
| Law Parameter | Type | Default | Ecological Effect & Hint |
|---|:---:|:---:|---|
| `hungry_ratio` | Float | `0.35` | Energy threshold (<= 35%) where normalized hunger activates enhanced foraging sight. |
| `hungry_perceive_mult` | Float | `1.3` | Perception range multiplier when an organism is hungry. |
| `starving_ratio` | Float | `0.15` | Critical starvation threshold (<= 15%) triggering desperate speed boost and pulsing red distress. |
| `desperate_speed_mult` | Float | `1.35` | Speed multiplier applied when an organism is in critical starvation. |
| `desperate_perceive_mult` | Float | `1.6` | Extreme sensory perception boost granted to starving organisms hunting for sustenance. |
| `food_giveup_ticks` | Integer | `240` | Ticks an organism will pursue an unreachable plant before recalculating paths. |
| `diet_strictness` | Float | `0.0` | Preference weight for caste-aligned diet vs general foraging opportunism. |

### Agriculture & Granaries
| Law Parameter | Type | Default | Ecological Effect & Hint |
|---|:---:|:---:|---|
| `agriculture_enabled` | Boolean | `true` | Enables seed gathering, cultivated farm plots, irrigation furrows, and tending. |
| `granaries_enabled` | Boolean | `true` | Enables communal settlement granaries to stockpile grains and berries against winter. |
| `granary_capacity` | Float | `400.0` | Maximum units of food a settlement granary can store. |
| `larder_capacity` | Float | `300.0` | Maximum units of food a domestic house larder can store. |

---

## 2. Biology & Evolution 🧬

### Life Cycle & Mortality
| Law Parameter | Type | Default | Ecological Effect & Hint |
|---|:---:|:---:|---|
| `lifespan_mult` | Float | `1.0` | Multiplier scaling all caste natural lifespans (Woman: 4,800t -> Priest: 9,000t); births apply ±30% uniform random jitter ($U(0.7, 1.3)$) to break cohort mortality cascades. |
| `adult_age` | Float | `240.0` *(Config: 600.0)* | Ticks required for a juvenile to reach physical maturity and reproductive eligibility. |
| `health_max` | String | `—` | Caste-level maximum physiological hit points (e.g. Soldier 120, Priest 100, Woman 70); trait property, not a tunable god law. |
| `euthanasia_threshold` | Float | `0.7` | Irregularity threshold at adulthood that triggers Spartan-style societal elimination. |
| `sex_ratio` | Float | `0.5` | Probability a newborn offspring is female (Line caste). |
| `creature_density` | Float | `0.0013` | Scaling factor for founding population density. |
| `spawn_variance` | Float | `0.25` | Spatial variance when scattering founding creatures across the map. |

### Reproduction & Genetics
| Law Parameter | Type | Default | Ecological Effect & Hint |
|---|:---:|:---:|---|
| `birth_enabled` | Boolean | `true` | Master switch permitting mating and generational births. |
| `birth_rate` | Float | `0.080` *(Config: 0.05)* | Base mating probability per tick for mature, fertile couples within contact radius. |
| `birth_energy_cost` | Float | `16.0` *(Config: 20.0)* | Maternal energy investment expended upon delivering offspring. |
| `reproduction_cooldown` | Integer | `240` *(Config: 600)* | Base ticks a female must rest after birth before becoming fertile again; perturbed by ±30% jitter ($U(0.7, 1.3)$) to desynchronize reproductive cycles. |
| `mate_radius` | Float | `10.0` | Spatial proximity required between two eligible partners to initiate courtship. |
| `mate_energy_min` | Float | `24.0` *(Config: 30.0)* | Minimum metabolic energy required for an adult to engage in mating. |
| `mutation_rate` | Float | `0.05` | Probability a child deviates from classical Abbott caste inheritance (n+1). |
| `mutation_sigma` | Float | `0.08` | Gaussian spread standard deviation for caste side mutations. |
| `mutation_heritability` | Float | `0.35` | Heritability coefficient for personality archetypes and behavioral genes. |
| `trait_mutation_rate` | Float | `0.02` | Frequency of spontaneous novel personality mutation in newborns. |
| `crossover_rate` | Float | `0.5` | Probability of chromosomal crossover during neural weight inheritance. |

### Density Soft-Cap Damping & Boom
| Law Parameter | Type | Default | Ecological Effect & Hint |
|---|:---:|:---:|---|
| `carrying_capacity` | Integer | `400` *(Config: 350)* | Equilibrium population threshold K_cap. Damping begins at $0.85 K_{\text{cap}}$ (hysteresis onset) and releases exponentially ($\tau = 300\text{t}$); fixed setpoint across seasons/ages. |
| `max_population` | Integer | `500` *(Config: 420)* | Population ceiling governed by a smooth cosine fertility room ramp from $K_{\text{cap}}$ to $max\_pop$, replacing hard ceiling snaps to eliminate limit cycles. |
| `soft_cap_enabled` | Boolean | `true` | Enables multi-channel homeostatic damping factor $\xi = \max(0, (N - 0.85 K_{\text{cap}})/K_{\text{cap}})$ with exponential release slew ($\tau = 300\text{t}$). |
| `damping_steepness` | Float | `12.0` *(Config: 7.0)* | Non-linear birth suppression steepness with smooth sigmoid transition ($k=5.0$) at onset. Config default is 7.0; Balance preset is 12.0; Theocracy preset follows 7.0. |
| `crowding_stress_mult` | Float | `1.0` *(Config: 1.0)* | Metabolic decay multiplier under high population crowding ($1 + \text{crowding}\cdot\xi + 0.8\cdot\text{crowding}\cdot\xi^2$). |
| `resource_strain_mult` | Float | `2.0` *(Config: 2.0)* | Resource renewal and vegetation spread throttling multiplier under overpopulation strain. |
| `boom_ramp_days` | Float | `1.2` | Founding day grace period where reproduction ramps smoothly to prevent day-1 explosion. |
| `boom_birth_floor` | Float | `0.4` | Initial reproductive throttle during world founding ramp. |
| `boom_cooldown_mult` | Float | `1.0` | Multiplier on mating cooldowns during population boom phases. |
| `boom_energy_mult` | Float | `1.0` | Multiplier on mating energy requirements during boom phases. |

### Extinction Safeguards & Genesis
| Law Parameter | Type | Default | Ecological Effect & Hint |
|---|:---:|:---:|---|
| `safeguard_enabled` | Boolean | `true` | Multi-tier automatic relief system preventing complete colony collapse. |
| `safeguard_relief_ratio` | Float | `0.3` | Population fraction threshold ($K_{\text{safe}} = K_{\text{eff}} \times 0.30$) activating emergency relief, evaluated against unified effective carrying capacity. |
| `safeguard_critical_pop` | Integer | `12` | Critical population floor $K_{\text{crit}}$ triggering emergency Genesis Miracles when population faces imminent extinction. |
| `safeguard_genesis_batch` | Integer | `6` | Number of pristine regular beings created during an emergency Genesis Miracle. |
| `safeguard_max_miracles` | Integer | `1` | Maximum number of Genesis Miracles permitted per world run. |
| `safeguard_morph_mercy` | Boolean | `true` | Suspends adult irregularity euthanasia during demographic crises. |

### Pathology & Disease
| Law Parameter | Type | Default | Ecological Effect & Hint |
|---|:---:|:---:|---|
| `disease_enabled` | Boolean | `true` | Enables contagion transmission, infection drain, and epidemic modeling. |
| `disease_rate` | Float | `0.035` | Spontaneous infection emergence probability per tick. |
| `disease_outbreak_rate` | Float | `6e-05` | Frequency of regional epidemic outbreaks during plague cycles. |
| `disease_radius` | Float | `3.0` | Proximity radius within which infected organisms can transmit pathogens. |
| `disease_energy_drain` | Float | `0.05` | Continuous metabolic energy drain inflicted by active infection. |
| `disease_lethality` | Float | `0.07` *(Config: 0.18)* | Damage inflicted per tick when fighting advanced infection. |
| `recovery_rate` | Float | `0.06` *(Config: 0.03)* | Probability per tick that an infected creature naturally clears the illness. |
| `wet_disease_mult` | Float | `1.5` | Multiplier increasing disease contagion and spread during rain and winter. |

### Micro-RNN Neuroevolution & Locomotion
| Law Parameter | Type | Default | Ecological Effect & Hint |
|---|:---:|:---:|---|
| `perceive_radius` | Float | `16.0` *(Config: 20.0)* | Base perception sight radius for sensory raycasting. |
| `eat_radius` | Float | `1.4` | Interaction distance required to ingest food or harvest plants. |
| `speed_mult` | String | `—` | Locomotion scale determined by caste base speed, modulated by kinematics and modifiers (e.g. desperate_speed_mult, rain_speed_mult); not a direct law. |
| `steer_turn` | Float | `0.45` | Maximum angular steering rate per tick, modulated by moment of inertia I_zz. |
| `wander_turn` | Float | `0.35` | Heading jitter applied when an organism has no active objective. |
| `flock_radius` | Float | `6.0` | Neighbor detection radius for local boids flocking behavior. |
| `separation_weight` | Float | `0.0` | Repulsion force keeping adjacent creatures from crowding too tightly. |
| `alignment_weight` | Float | `0.0` | Heading alignment force with neighboring clan members. |
| `cohesion_weight` | Float | `0.0` | Center-of-mass attraction force toward kin clusters. |
| `defense_weight` | Float | `0.5` | Tactical positioning weight for soldiers protecting vulnerable lines. |
| `fear_radius` | Float | `12.0` | Distance at which peaceful organisms detect predators and flee. |
| `nn_inference_hz` | Integer | `15` | Frequency of full neural network feedforward evaluation. |

### Polar Morphology & Annealing
| Law Parameter | Type | Default | Ecological Effect & Hint |
|---|:---:|:---:|---|
| `morphology_annealing_enabled` | Boolean | `true` | Blends Abbott geometric templates into freely evolving polar polygon genomes. |
| `annealing_start_generation` | Integer | `50` *(Config: 15)* | Generation where morphological annealing decay begins. |
| `annealing_decay_generations` | Integer | `150` *(Config: 250)* | Generations over which annealing factor lambda transitions from 1.0 to 0.0. |
| `morph_lambda_override` | String | `None` | Manual override fixing lambda in [0, 1] (None follows natural generational curve). |
| `vertex_mutation_std` | Float | `0.05` *(Config: 0.025)* | Standard deviation of radial vertex perturbations per generation. |
| `angle_mutation_std` | Float | `0.02` *(Config: 0.012)* | Standard deviation of angular vertex shifts per generation. |
| `topological_mutation_rate` | Float | `0.01` *(Config: 0.008)* | Frequency of vertex insertion/deletion mutations altering K in [3, 24]. |
| `max_sides` | Integer | `24` | Maximum allowable polygon vertex count K for evolving organisms. |

### Predation, Carnivory & Cannibalism
| Law Parameter | Type | Default | Ecological Effect & Hint |
|---|:---:|:---:|---|
| `predation_enabled` | Boolean | `true` *(Config: False)* | Enables carnivorous predators that hunt peaceful herbivores and flatland castes. |
| `predator_ratio` | Float | `0.008` *(Config: 0.0)* | Proportion of founding predator beasts in the ecosystem. |
| `beast_ratio` | Float | `0.0` | Proportion of wild carnivore spawns relative to standard castes. |
| `bite_damage` | Float | `16.0` *(Config: 28.0)* | Combat damage inflicted per predator strike. |
| `bite_cooldown` | Integer | `15` | Ticks between consecutive predator attacks. |
| `hunt_radius` | Float | `7.0` *(Config: 8.0)* | Sensory tracking radius of hunting predators seeking prey. |
| `energy_from_prey` | Float | `40.0` | Metabolic energy yield gained by predators from consuming caught prey. |
| `cannibalism_enabled` | Boolean | `true` | Allows desperate starving organisms to consume fallen corpses of their own species. |
| `cannibalism_energy` | Float | `35.0` | Energy harvested from consuming a fallen kin corpse. |
| `cannibalism_hunger_ratio` | Float | `0.08` | Extreme starvation threshold required before a creature resorts to cannibalism. |
| `eat_kin_enabled` | Boolean | `false` *(Config: True)* | Whether consuming a clan member's corpse is physically possible under starvation. |
| `eat_enemy_enabled` | Boolean | `true` | Whether consuming a defeated rival clan soldier is permitted. |
| `kin_stigma` | Integer | `35` *(Config: 40)* | Social penalty and trust loss incurred when caught consuming kin. |
| `exile_on_kin_eat` | Boolean | `true` | Automatic exile from clan upon committing kin cannibalism. |

---

## 3. Climate & Sky ☀️

### Sky, Seasons & Weather
| Law Parameter | Type | Default | Ecological Effect & Hint |
|---|:---:|:---:|---|
| `weather_enabled` | Boolean | `true` | Enables dynamic weather cycles (Clear, Fog, Rain, Storm). |
| `weather_change_rate` | Float | `0.002` | Frequency of spontaneous atmospheric weather state transitions. |
| `day_length` | Integer | `1200` | Duration of one full day/night cycle in simulation ticks (120s at 10 tps). |
| `season_length` | Integer | `2400` *(Config: 14400)* | Duration of each astronomical season in ticks (2400t = 2 days per season, desynchronized from 12000t Age cycle). |
| `initial_season_offset` | Integer | `0` | Starting season offset when launching a new world seed. |
| `night_sight_mult` | Float | `0.6` | Sensory sight attenuation factor during the dark of night (0.6x). |
| `rain_growth_mult` | Float | `1.25` | Accelerated botanical growth multiplier during rainfall. |
| `rain_speed_mult` | Float | `0.85` | Locomotion friction penalty while moving through wet rain. |
| `storm_wander_bonus` | Float | `0.35` | Additional path deviation caused by violent storm winds. |
| `storm_plant_damage` | Float | `0.02` | Chance severe storms damage exposed wild vegetation. |
| `fog_sight_mult` | Float | `0.6` | Sensory sight reduction factor inside thick fog banks. |
| `fog_mushroom_mult` | Float | `1.35` | Increased sprout frequency of fungal mushrooms during fog. |

### Weather Sickness & Chill
| Law Parameter | Type | Default | Ecological Effect & Hint |
|---|:---:|:---:|---|
| `weather_sickness_enabled` | Boolean | `false` | Enables exposure penalties and chill accumulation. |
| `chill_rate` | Float | `0.04` | Rate of chill accumulation per tick when caught unsheltered in storms or winter nights. |
| `chill_threshold` | Float | `12.0` | Chill level above which continuous hypothermia damage begins (0.18 HP/tick). |
| `chill_drain` | Float | `0.09` *(Config: 0.18)* | Continuous health damage per tick suffered from severe hypothermia. |
| `exposure_drain` | Float | `0.02` *(Config: 0.03)* | Metabolic energy penalty incurred from staying exposed outdoors in harsh weather. |

### Shelter & Recovery
| Law Parameter | Type | Default | Ecological Effect & Hint |
|---|:---:|:---:|---|
| `sleep_enabled` | Boolean | `true` | Organisms require periodic circadian rest to restore stamina. |
| `shelter_enabled` | Boolean | `true` | Walled houses provide thermal protection, safe rest, and predator immunity. |
| `sleep_energy_mult` | Float | `0.5` | Metabolic burn discount enjoyed while sleeping indoors. |
| `rest_recovery_mult` | Float | `2.5` *(Config: 2.0)* | Health regeneration rate multiplier while resting comfortably in shelter. |
| `hearths_enabled` | Boolean | `true` | Indoor hearths provide warmth and accelerate chill dissipation (2.5x). |

---

## 4. Society, Warfare & Trade 🏰

### Settlements & Clans
| Law Parameter | Type | Default | Ecological Effect & Hint |
|---|:---:|:---:|---|
| `territory_enabled` | Boolean | `true` | Settlements project territorial influence zones on the map. |
| `territory_radius` | Float | `14.0` | Spatial radius of clan territorial influence projected from houses. |
| `totems_enabled` | Boolean | `true` | Clans adopt Sacred Avatars of the Sphere (⭕ Radiant Circle, ⚡ Celestial Strike, 👁️ All-Seeing Vertex, 🛡️ Indomitable Monolith, 🌿 Sacred Spiral, ⚖️ Cosmic Scales, 🌀 Dimensional Rift, 🕯️ Eternal Hearth). |
| `succession_enabled` | Boolean | `true` | Clans execute succession rituals upon the demise of their chieftain. |
| `leader_decisions_enabled` | Boolean | `true` | Clan chieftains adjust macro task priorities (food security, defense, expansion). |
| `resource_sharing_enabled` | Boolean | `true` | Sated foragers deposit surplus into settlement larders for hungry kin. |
| `house_claim_enabled` | Boolean | `true` | Homeless citizens can autonomously claim abandoned settlement ruins. |
| `max_clans` | Integer | `-1` | Maximum number of simultaneous active clan factions permitted in the world. |
| `num_houses` | Integer | `-1` | Target number of walled residential houses spawned in the world. |
| `house_density` | Float | `0.00065` | Clustering density of settlement dwellings. |
| `house_min_size` | Float | `5.5` | Minimum interior dimension of generated house structures. |
| `house_max_size` | Float | `8.0` | Maximum interior dimension of clan halls and main houses. |
| `house_gap` | Float | `6.0` | Minimum clearance distance between neighboring houses. |
| `house_capacity` | Integer | `14` *(Config: 12)* | Maximum number of creature occupants permitted inside a single house. |
| `door_clearance` | Float | `1.5` | Width of creature-sized entrance doorways in house perimeter walls. |
| `house_decay_ticks` | Integer | `3000` *(Config: 2400)* | Lifespan ticks of uninhabited houses before crumbling into ruins. |

### Communication & Knowledge
| Law Parameter | Type | Default | Ecological Effect & Hint |
|---|:---:|:---:|---|
| `communication_enabled` | Boolean | `true` | Enables auditory signals, distress chirps, and warning broadcasts. |
| `knowledge_enabled` | Boolean | `true` | Elders transmit skill mastery, oral lore, and mental maps to youth in houses. |
| `vocalizations_enabled` | Boolean | `true` | Neural network outputs control vocal amplitude and frequency outputs. |
| `signal_radius` | Float | `12.0` | Auditory transmission radius of creature vocalizations. |
| `signal_speed` | Float | `8.0` | Propagation speed of acoustic waves across the 2D plane. |
| `alarm_call_rate` | Float | `0.12` | Frequency of distress calls emitted when attacked by hostiles. |
| `food_call_rate` | Float | `0.08` | Frequency of foraging calls alerting clan members to rich food sources. |
| `help_call_enabled` | Boolean | `true` | Starving or injured creatures call nearby kin for assistance. |
| `help_radius` | Float | `12.0` | Range at which kin respond to emergency help calls. |
| `aid_rate` | Float | `0.05` | Altruistic food-sharing rate between kin carrying basket reserves. |
| `knowledge_share_rate` | Float | `0.05` | Speed of skill experience transfer during elder teaching sessions. |
| `knowledge_ttl` | Integer | `600` | Persistence duration of transmitted mental waypoint markers. |
| `dialect_drift_enabled` | Boolean | `true` | Clan vocal frequencies gradually drift over generations into regional dialects. |
| `scent_enabled` | Boolean | `true` | Creatures leave chemical scent trails marking frequently traveled paths. |

### Diplomacy & Warfare
| Law Parameter | Type | Default | Ecological Effect & Hint |
|---|:---:|:---:|---|
| `war_enabled` | Boolean | `true` | Rival clans engage in border skirmishes, granary raids, and house sieges. |
| `attack_damage` | Float | `30.0` | Baseline combat strike damage inflicted by soldiers. |
| `attack_radius` | Float | `1.8` | Melee combat strike range. |
| `coalitions_enabled` | Boolean | `true` | Clans form defensive mutual pacts against dominant expansionist hegemonies. |
| `coalition_min_size` | Integer | `2` | Minimum allied clans required to declare a formal mutual defense league. |
| `coalition_threshold` | Integer | `40` | Minimum threat score required before a coalition activates military defense. |
| `alliance_threshold` | Integer | `55` *(Config: 50)* | Diplomatic relation score required to formalize an alliance treaty. |
| `rivalry_threshold` | Integer | `-45` *(Config: -75)* | Negative relation score triggering hostile rivalry and border skirmishes. |
| `relation_drift_rate` | Float | `1.8` *(Config: 2.2)* | Baseline rate at which inter-clan diplomatic tensions decay toward neutrality. |
| `trespass_decay` | Float | `0.45` *(Config: 0.25)* | Rate at which border trespass grievances decay over time. |
| `tribute_enabled` | Boolean | `true` | Weaker clans pay food grain tribute to avoid destructive military invasion. |
| `envoys_enabled` | Boolean | `true` | Clans dispatch peaceful diplomatic emissaries to negotiate treaties. |
| `markets_enabled` | Boolean | `true` | Inter-clan trade caravans barter goods and share combat/farming techniques. |
| `banquets_enabled` | Boolean | `true` | Allied clans host joint feasts to solidify diplomatic bonds (+25 trust). |

### Internal Politics & Defection
| Law Parameter | Type | Default | Ecological Effect & Hint |
|---|:---:|:---:|---|
| `schism_enabled` | Boolean | `true` | Overcrowded or oppressed factions can rebel and split into independent clans. |
| `schism_min_pop` | Integer | `6` *(Config: 6)* | Minimum clan population required before a civil schism can trigger. |
| `schism_threshold` | Float | `0.55` *(Config: 0.5)* | Internal clan friction threshold required to spark a revolutionary schism. |
| `defection_enabled` | Boolean | `true` | Dissatisfied individuals can abandon their clan and swear loyalty to rivals. |
| `betrayal_enabled` | Boolean | `true` | Corrupt leaders or ambitious soldiers can stage coups and seize power. |

---

## 5. Theology & Sacred Avatars 🔮

### Theology & Ages
| Law Parameter | Type | Default | Ecological Effect & Hint |
|---|:---:|:---:|---|
| `theology_enabled` | Boolean | `true` | Priests build shrines and temples to channel the higher-dimensional Sphere. |
| `temple_faith_cost` | Float | `250.0` *(Config: 400.0)* | Faith points required to consecrate a grand temple dedicated to The Sphere. |
| `tithe_rate` | Float | `0.04` | Fraction of harvested grains tithed to priestly temples to generate divine favor. |
| `culture_enabled` | Boolean | `true` | Spreads cultural memes and traditions that provide passive bonuses to members. |
| `culture_spread_rate` | Float | `0.005` | Velocity of cultural meme transmission between allied settlement houses. |
| `age_enabled` | Boolean | `true` | Periodic cosmic super-seasons transform global ecological parameters. |
| `age_length` | Integer | `12000` | Duration of each cosmic Age in simulation ticks (1200s). |
| `omens_enabled` | Boolean | `true` | Atmospheric celestial portents foreshadow incoming cosmic age transitions. |

---

## 6. World Physics & Disasters ⚙️

### Spatial Topology & Demographics
| Law Parameter | Type | Default | Ecological Effect & Hint |
|---|:---:|:---:|---|
| `width` | Float | `400.0` | World width in spatial coordinate units. |
| `height` | Float | `300.0` | World height in spatial coordinate units. |
| `boundary` | String | `wrap` | World boundary mode (`wrap` for toroidal topology, `clamp` for solid edges). |
| `seed` | Integer | `42` | Primary pseudorandom seed determining procedural terrain and initial state. |
| `tick_rate` | Float | `10.0` | Simulation advancement rate (ticks per second). |
| `history_max` | Integer | `200` | Maximum historical event log entries stored in SQLite. |
| `rock_count` | Integer | `-1` | Number of impassable stone boulders scattered across the map. |
| `anomaly_count` | Integer | `3` | Number of mysterious spatial singularities located in the world. |
| `num_women` | Integer | `-1` | Founding population of Line females (crucial foundation of all lineages). |
| `num_triangles` | Integer | `-1` | Founding population of Isosceles Soldiers and Equilateral Artisans. |
| `num_squares` | Integer | `-1` | Founding population of Square Gentlemen and Merchants. |
| `num_pentagons` | Integer | `-1` | Founding population of Pentagon Professionals and Architects. |
| `num_hexagons` | Integer | `-1` | Founding population of Hexagon Sub-Magistrates. |
| `num_priests` | Integer | `-1` | Founding population of Circular Priests (guardians of religion). |

### Physics, Rivers & Cataclysms
| Law Parameter | Type | Default | Ecological Effect & Hint |
|---|:---:|:---:|---|
| `rivers_enabled` | Boolean | `true` | Procedural natural waterways meandering across the landscape. |
| `river_count` | Integer | `2` | Number of procedural river channels generated across the map. |
| `relief_enabled` | Boolean | `true` | Terrain elevation gradients influencing movement speed and sight. |
| `structural_enabled` | Boolean | `true` | House walls possess physical structural integrity and can degrade under siege. |
| `rubble_blocking_enabled` | Boolean | `true` | Collapsed buildings leave passable debris piles that provide defensive cover. |
| `wildfire_enabled` | Boolean | `true` | Forest fires ignite during summer droughts and spread across dry grass. |
| `fire_rate` | Float | `8e-05` | Spontaneous lightning/drought wildfire ignition probability per tick. |
| `fire_spread_rate` | Float | `0.035` | Velocity of wildfire propagation across flammable vegetation. |
| `earthquake_enabled` | Boolean | `false` | Seismic ground tremors that can fracture terrain and damage dwellings. |
| `earthquake_rate` | Float | `8e-05` | Frequency of tectonic seismic disturbances. |
| `lightning_enabled` | Boolean | `true` | Atmospheric electrical strikes during violent thunderstorms. |
| `lightning_strike_rate` | Float | `0.0015` | Frequency of lightning ground discharges during severe thunderstorms. |
| `disaster_enabled` | Boolean | `true` | Master switch for spontaneous macro natural cataclysms. |
| `disaster_rate` | Float | `4e-05` | Overall occurrence probability for spontaneous global cataclysms. |
| `omp_enabled` | Boolean | `true` | Native OpenMP vector acceleration for intensive spatial physics calculations. |
| `omp_threshold` | Integer | `100` | Minimum entity threshold before activating multi-core OpenMP routines. |

---

## 🎯 Curated World Presets

Flatland includes 7 balanced, pre-configured world profiles:

1. **⚖️ Balance (Default)**: Goldilocks harmony tuned for **200–350 inhabitants** with 380 food, flat carrying capacity 400 (max 500 with smooth cosine fertility room ramp), damping parameters (12.0/1.0/2.0) with $0.85 K$ hysteresis and $\tau = 300\text{t}$ release slew, gentle wars, rare predation, agriculture, extinction safeguards (η), and flourishing multi-generational clans.
2. **🌿 Sustainable**: 1000-day prosperous peace, abundant food (550), carrying capacity 550 (max 600), rich granaries, harvest festivals, and banquets.
3. **🔮 Theocracy**: Age of the Sphere, divine avatars, glowing temples, avatar miracles, 3D epiphanies, and holy synods. Tuned with flat raw $K=380$, and damping parameters (7.0/1.0/2.0) matching Config defaults via automatic database law migration from legacy 4.0/0.25/0.9 pins.
4. **⚔️ Warlords**: Clash of clans, imperial conquests, granary raids, house takeovers, territorial expansion, and defensive coalitions.
5. **🔥 Chaos**: High predator ratio, lethal wars, wildfires, frequent plagues, earthquakes, and fast seasonal turnover.
6. **💀 Extinction**: Severe famine (120 food), harsh winter (0.3×), high exposure decay, testing societal resilience under collapse.
7. **🚀 Boom**: High reproduction, 440 food, carrying capacity 800 (max 850) for monumental metropolis expansion.

Presets can be applied instantly via `POST /api/presets/{name}?reset=true` or selected within **⚖ The Sphere (God Panel)**.
