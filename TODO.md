# Flatland — World Simulation TODO

[![GitHub Repo](https://img.shields.io/badge/GitHub-longphanmn%2Fflatland-181717.svg?logo=github)](https://github.com/longphanmn/flatland)

The Sphere model: The Sphere (God) sets **laws** from Spaceland, never touches individual creatures. Everything else emerges.  
Repository: [https://github.com/longphanmn/flatland](https://github.com/longphanmn/flatland)  
Legend: [P0] foundational · [P1] core Flatland identity · [P2] flavor/observability · `- [ ]` open · `- [x]` done · *parked* = decided, not pending

> **Active backlog only.** Completed roadmaps §F–§BL (693 items) → [`docs/roadmap-archive.md`](docs/roadmap-archive.md). This file tracks **0 open items** (all completed through §BL) + 8 parked.

---

## §BG Mutational Shape & Visual Phenotypes — ✅ Done (12/12) — 2026-09-02

### Phase 1: Dynamic Mutated Geometry & Razor Isosceles (Canvas2D & SVG) [P0] — ✅ Done
- [x] [P0] **BG-1 True Isosceles Soldier razor apex** — Render Soldiers with their true `iso_angle` ($\theta_{\text{iso}} \in [10^\circ, 59.5^\circ]$) pointing forward along velocity heading in `renderCore.ts` and `CreatureAvatar.tsx` instead of equilateral triangles.
- [x] [P0] **BG-2 Dynamic mutated polygon geometry** — Procedurally reconstruct and render irregular, asymmetric polygons on canvas using `(sides, irregularity, seed, id)` with vertex radii offsets and angular jitter.
- [x] [P0] **BG-3 Line caste (Woman) variable thickness & taper** — Render Women with variable tip sharpness and mid-span taper reflecting perimeter and metabolic genes.
- [x] [P0] **BG-4 Topological aberration rendering** — Render non-standard vertex counts ($K \in [3,24]$, e.g., 7-sided noble, 11-sided aberration) with accurate vertex distribution.

### Phase 2: Visual Mutational Phenotypes & Accents [P1] — ✅ Done
- [x] [P1] **BG-5 Blade Glint (Kinetic Pierce Accent)** — Render a highlighted neon glint on the creature's sharpest interior vertex ($\theta_{\min}$) scaled by attack damage.
- [x] [P1] **BG-6 Heavy Inertia Armor** — Render double-layered perimeter strokes and darker fill opacity for creatures with high rotational inertia $I_{zz}$ and large Shoelace area $A$.
- [x] [P1] **BG-7 Speciation chromatic aberration** — Add iridescent dual-tone edge accents as $\lambda(g) \to 0$ (high generational divergence from Abbott orthodoxy).
- [x] [P1] **BG-8 Elder lineage nucleus** — Render an internal inscribed geometric core or ancestral glyph inside high-generation elders and clan chiefs.

### Phase 3: Inspector Polar Radar & Biomechanical Dossier [P1] — ✅ Done
- [x] [P1] **BG-9 Polar Morphology Radar in Inspector** — Interactive SVG radar overlay in `Inspector.tsx` showing the creature's mutated polygon against the ghosted orthodox Abbott template.
- [x] [P1] **BG-10 Biomechanical trait HUD** — Display live computed metrics: Sharpness Index ($\theta_{\min}$), Irregularity score ($\sigma_r^2/\bar{r}$), Rotational Inertia ($I_{zz}$), and Shoelace Area ($A$).

### Phase 4: Mutation Lab Lineage Tree & Morphospace [P2] — ✅ Done
- [x] [P2] **BG-11 Morphological Phylogeny Tree** — Visual ancestral drift tree in `MutationLab.tsx` showing geometric evolution from founding Platonic solids to aberrant polyforms.
- [x] [P2] **BG-12 Morphospace 2D Scatterplot** — Interactive Area vs. Sharpness scatterplot in Mutation Lab visualizing emergent sub-species clusters.

---

## §BH Next-Gen Evolutionary Mutation Engine & Neuroevolution — ✅ Done (10/10) — 2026-09-02

> **Context**: Decouples evolution from rigid template decay so populations continue speciation even at $\lambda=0.00$. Integrates true two-parent polar crossover, macro-mutations, stress mutagenesis, real-time NN weight evolution (295 weights), and emergent behavioral niches. See `mutation_evolution_brainstorm.md` for full design.

### Phase 1: Two-Parent Polar Crossover & Speciation at $\lambda=0$ [P0] — ✅ Done
- [x] [P0] **BH-1 Two-Parent Meiotic Polar Crossover** — Recombine polar sector arcs from Mother and Father in `evolution_manager.py` `child_morphology()` with vertex-count interpolation $K_{\text{child}} \in [K_{\text{mother}}, K_{\text{father}}]$.
- [x] [P0] **BH-2 Macro-Mutation Spurts (5% chance at $\lambda=0$)** — Add discrete structural mutations: *Apex Weaponization* (stretching one vertex $+50\text{--}100\%$), *Facet Shielding* (flattening front edges), and *Radial Crystallization* (regularizing into star polyforms).
- [x] [P0] **BH-3 Stress-Induced Mutagenesis** — Double morphological mutation variance ($\sigma_r \times (1 + 1.5 \cdot \text{stress})$) during famine ($\text{larder} < 50$) or severe epidemic outbreaks.

### Phase 2: Neural Network (NN) Genome Evolution (295 weights) [P0–P1] — ✅ Done
- [x] [P0] **BH-4 Real-time NN Genome Crossover on Birth** — Hook up `crossover_mutate` in `simulation.py` `_birth()` so every newborn inherits hybridized neural controller weights from both parents.
- [x] [P1] **BH-5 Functional-Block NN Mutation Rates** — Apply block-specific mutation rates: Sensory $W_1$ ($p=0.03, \sigma=0.06$), Motor $W_2$ ($p=0.05, \sigma=0.10$), and Recurrent Memory $W_{\text{rec}}$ ($p=0.02, \sigma=0.04$).
- [x] [P1] **BH-6 Behavioral Inversion Mutations (0.5% chance)** — Implement sensory sign-flip mutations (attraction $\leftrightarrow$ repulsion, daylight $\leftrightarrow$ night-forage preference).
- [x] [P1] **BH-7 Neuro-Morphological Sensor Coupling** — Scale forward ray sensitivity by tip sharpness $\theta_{\min}$ and sensory cone span by body perimeter/area.

### Phase 3: Emergent Behavioral Archetypes & Observability [P1–P2] — ✅ Done
- [x] [P1] **BH-8 Nocturnal Forager & Sentry Policy Evolution** — Allow night-active mutants with chill tolerance to forage under darkness while diurnal creatures sleep.
- [x] [P1] **BH-9 Behavioral Archetype Auto-Classifier** — Automatically classify and tag creature policies in UI (`[Apex Hunter]`, `[Nocturnal Forager]`, `[Granary Courier]`, `[Sentry Guard]`).
- [x] [P2] **BH-10 Inspector NN Connectivity Heatmap** — Render interactive neural connectivity matrix ($16 \to 12 \to 7$) in `Inspector.tsx` showing active synaptic pathways.

---

## §BI Simulation Engine Decomposition — ✅ Done (10/10) — 2026-09-02

> **Context**: `simulation.py` is an 11,624-line monolith containing 7 distinct domains. Decompose into a mixin-based `simulation/` package for maintainability, navigation, and merge-conflict reduction. Zero logic changes — method bodies move as-is. All 487 tests must remain green at every phase.

### Phase 1: Scaffold Package [P0] — ✅ Done
- [x] [P0] **BI-1 Create `simulation/` package scaffold** — Create `backend/app/simulation/` with `__init__.py` re-exporting `Simulation`. Move `simulation.py` → `simulation/core.py`. Update all imports across codebase. Verify `pytest -q` 487/487.
- [x] [P0] **BI-2 Extract `constants.py`** — Move all module-level constants, lookup tables, season/age multipliers, clan name generators, and utility functions (`personal_name_for`, `glyph_for`, `variation_for`) from L1–719 into `simulation/constants.py`.

### Phase 2: Extract Domain Mixins (least coupled first) [P0] — ✅ Done
- [x] [P0] **BI-3 Extract `SerializationMixin`** — Move snapshot/delta wire protocol, entity payloads, identity caching, and hash signatures (~600 lines) into `simulation/serialization.py`.
- [x] [P0] **BI-4 Extract `EcologyMixin`** — Move flora lifecycle, agriculture, banquets, corpse decomposition, nutrient cycling, and food law enforcement (~600 lines) into `simulation/ecology.py`.
- [x] [P0] **BI-5 Extract `EnvironmentMixin`** — Move sky/weather, wind, temperature grids, elevation, rivers, seismic, lightning, traffic, anomalies, fires, campfires, disasters, and builders (~1,300 lines) into `simulation/environment.py`.
- [x] [P0] **BI-6 Extract `SettlementMixin`** — Move housing economy, construction, claims, takeover, doorway navigation, and wall geometry caching (~520 lines) into `simulation/settlement.py`.
- [x] [P0] **BI-7 Extract `TheologyMixin`** — Move faith/shrines, blessings, miracles, synods, epiphanies, and dogma (~500 lines) into `simulation/theology.py`.
- [x] [P0] **BI-8 Extract `SocietyMixin`** — Move clans, diplomacy, warfare, coalitions, leaders, larders, defection, trade, culture, cannibalism, and specialization (~2,200 lines) into `simulation/society.py`.
- [x] [P0] **BI-9 Extract `LifecycleMixin`** — Move spawning, evolution init, morphology inheritance, reproduction, birth, death, disease, and skill/title progression (~1,700 lines) into `simulation/lifecycle.py`.

### Phase 3: Decompose the Agent Loop Monolith [P1] — ✅ Done
- [x] [P1] **BI-10 Extract `CreatureUpdateMixin` & decompose `_update_creature`** — Move the 2,572-line `_update_creature` into `simulation/creature_update.py` and decompose into 7 named phase methods: `_creature_tick_timers`, `_creature_night_rest`, `_creature_predation`, `_creature_forage`, `_creature_steering`, `_creature_movement`, `_creature_collisions`, `_creature_feeding`, `_creature_metabolism`.

---

## §BJ Production Performance & Tick Budget Restoration (3 → 10+ TPS) — ✅ Done (6/6) — 2026-09-03

> **Context**: Production servers (e.g. Intel N150 / 4-core Linux) run new worlds at **~3.0 TPS** (330ms/tick) against a 100ms budget (`tick_rate=10.0`). Profiling reveals that 5 compounded bottlenecks stall each step:
> 1. Full `AgentSoA` & `SpatialHashGrid` allocation/rebuilding every birth/death (~80–120ms)
> 2. Duplicate `_refresh_cache()` passes with O(N) house bounding-box searches (~40–80ms)
> 3. Un-throttled synchronous `_analytics.on_tick()` O(N) telemetry rings (~10–15ms)
> 4. Full JSON payload serialization executed while holding `RT.lock` (~15–25ms)
> 5. Pure Python sequential creature update loop ignoring compiled `c_batch_update_creatures_omp` (~60–100ms)
>
> **Result**: `test_production_tick_budget` (100 ticks, sustainable preset, 170 creatures / 380 food / 88 houses) reports **mean 28.8ms / max 35.5ms** on dev hardware — inside the 45ms budget (85ms N150 equiv). Full suite **490 passed, 14 skipped**.

### Solutions & Implementation Roadmap

- [x] [P0] **BJ-1 Incremental AgentSoA Slot Management (Eliminate Full Rebuild)**
  - **Location**: `backend/app/simulation/core.py:1479-1566`
  - **Problem**: `if self._soa.N != len(self._cached_creatures)` executes on virtually every tick (births/deaths occur constantly). It instantiates a brand-new `AgentSoA(capacity=2000)`, re-allocates 12+ numpy arrays (~800KB), performs deep Python loops copying positions, angles, genomes, and instantiates a brand-new `SpatialHashGrid`.
  - **Solution**: Implement in-place slot management in `AgentSoA`:
    1. *Death*: Compact-remove the dead agent via swap-with-last O(1) compaction (`pos[idx] = pos[N-1]`, `N -= 1`) and update `_soa_id_map`.
    2. *Birth*: Append the newborn directly into slot `self._soa.add_agent(...)` using the existing pre-allocated buffer without reallocating arrays.
    3. *Grid*: Incrementally insert/delete/update agent positions in `SpatialHashGrid` without recreating the grid.
    4. *Capacity*: Only reallocate a larger buffer if `len(creatures) >= capacity`.
  - **Expected Impact**: Saves **80–120ms/tick** (immediately boosts production from ~3.0 TPS to ~6.5 TPS).

- [x] [P0] **BJ-2 Single-Pass `_refresh_cache()` with Lightweight Post-Movement Refresh**
  - **Location**: `backend/app/simulation/core.py:936-1076`, `1158`, `1281`
  - **Problem**: `_refresh_cache()` is called twice per tick (before and after creature updates). Each invocation performs an O(N_entities) scan across all world entities (food, houses, corpses, creatures), constructs a 50×50 spatial house grid, runs nested bounding-box checks for bed/roof occupancy, and computes leader/shrine/priest/totem lookups.
  - **Solution**:
    1. Keep the full entity classification and house grid construction solely at tick start (`L1158`).
    2. Replace the second invocation (`L1281`) with `_refresh_movement_cache()`, which ONLY refreshes dynamic creature coordinates: `_leader_pos`, `_priest_pos`, and updates `house_occ`/`bodies` using the already-built spatial house grid. Skip scanning foods, corpses, ruins, and rebuilding `_houses_by_clan`.
  - **Expected Impact**: Saves **25–40ms/tick**.

- [x] [P1] **BJ-3 Decouple Telemetry & Analytics Ring from Simulation Hot-Path**
  - **Location**: `backend/app/simulation/core.py:1608-1610`, `backend/app/analytics.py:52-137`
  - **Problem**: `self._analytics.on_tick(self)` is called every single tick. It iterates all creatures to aggregate biomass, energy, lifespans, irregularity, and appends to 12 deques. Furthermore, the 1 Hz WebSocket analytics broadcast (`_analytics_payload`) runs `generational_tracker` (sorting all creatures by irregularity, calculating polygon areas/angles with trigonometry) synchronously on the simulation thread.
  - **Solution**:
    1. Throttle telemetry sampling: run `self._analytics.on_tick(self)` at 2 Hz (`if self.tick % max(1, int(self.config.tick_rate // 2)) == 0:`), or maintain running scalar accumulators during birth/death/eat.
    2. In `_analytics_payload`, cache the `summary` result or sample a smaller fixed subset of creatures (e.g. 20 instead of 80) for the morphospace scatterplot.
    3. Ensure `TelemetryRing.push()` avoids re-iterating `world.entities` if `_cached_creatures` is already in memory.
  - **Expected Impact**: Saves **8–15ms/tick** and eliminates periodic 1 Hz stutter spikes.

- [x] [P1] **BJ-4 Lockless Snapshot Serialization & Broadcast Pipeline**
  - **Location**: `backend/app/main.py:345-386`
  - **Problem**: `advance_world()` runs `rt.sim.step()`, then immediately calls `rt.sim.snapshot_payload()` / `snapshot_delta_payload()` and `_clans_payload()` while holding `with self.rt.lock:`. Serializing hundreds of entity dictionaries and encoding JSON inside the lock blocks HTTP API requests and holds the Python GIL during heavy JSON dumps.
  - **Solution**:
    1. Take `rt.lock` ONLY for `rt.sim.step()`.
    2. Extract a shallow list of dirty entity states or a frozen snapshot reference, then immediately release `rt.lock`.
    3. Perform dictionary formatting, delta payload calculation, and `_dumps()` JSON encoding outside the lock before enqueueing to the broadcast hub.
  - **Expected Impact**: Eliminates **15–25ms** of lock contention; keeps HTTP endpoints (`/api/state`, `/healthz`) responsive even during high tick rates.

- [x] [P1] **BJ-5 Wire Compiled Native Core C/OpenMP Batch Accelerators**
  - **Location**: `backend/app/simulation/core.py:1231-1233`, `backend/app/native_core.py:115-180`
  - **Problem**: `deploy.sh:125` compiles `_flatland_core.so` with `-O3 -fopenmp -march=native -ffast-math` containing `c_batch_update_creatures_omp`, `c_query_radius`, and `c_toroidal_dist_sq`. However, `simulation/core.py` runs a purely sequential Python loop over `list(self._cached_creatures)` calling `_update_creature` (~60–100ms for 170 creatures).
  - **Solution**:
    1. Wire `native_core.c_query_radius` and toroidal distance math into the hotspot paths of `_update_creature` (predator prey detection, food perception, house door collision checks).
    2. Enable the OpenMP batch kernel `c_batch_update_creatures_omp` when `config.omp_enabled=True` and living population exceeds `config.omp_threshold`.
  - **Expected Impact**: Saves **30–60ms/tick** at N >= 170.

- [x] [P0] **BJ-6 Production Tick-Budget Regression Benchmark**
  - **Location**: `backend/tests/test_tick_budget.py`
  - **Problem**: Lack of automated CI testing for tick latency under production-sized founding conditions (170 creatures, 380 food, 88 houses).
  - **Solution**:
    1. Add `test_production_tick_budget()` running 100 ticks under the `sustainable` preset.
    2. Assert mean tick duration $\le 45\text{ms}$ on dev hardware (equivalent to $\le 85\text{ms}$ on low-power Intel N150 / 4-core servers), guaranteeing a solid $\ge 11.5\text{ TPS}$ headroom for the 10.0 TPS target.
    3. Include per-subsystem timing telemetry in `/healthz` and `/api/perf/telemetry` for live verification.

---

## §BK Creature Visual Evolution, Generational Lineage & Aberrant Morphology — 2026-09-08

> **Context**: Transforms creature appearance on the map from flat, uniform caste shapes into an intuitive, visually rich living tapestry of generations, mutations, and evolutionary identities. Users can visually distinguish Primordial founders vs. ancient dynasties, identify aberrant/mutant outcasts at a glance, and inspect biomechanical lineages.

### Phase 1: Core Generational Lineage & Aberrant Morphology Rendering [P0] — ✅ Done
- [x] [P0] **BK-1 Genesis Spark for Primordials (Gen 0–2)** — Render an unmistakable glowing central Genesis Spark (star/diamond core pip) inside founding creatures and first ancestors on the map so founders stand out everywhere.
- [x] [P0] **BK-2 Concentric Lineage Halos & Celestial Ancestral Corona** — Render generational depth rings: Gen 10–24 inner lineage halo ($0.65 \times r$), Gen 25–49 double concentric dynasty ring, and Gen 50+ radiating starburst Ancestral Corona ticks around the perimeter.
- [x] [P0] **BK-3 Dynamic Chaotic Breathing & Jagged Mutant Spires** — Procedural dynamic micro-oscillation for irregular vertices ($\Delta r_i \propto \sin(\text{tick} \cdot 0.35 + i \cdot 2.1) \cdot \text{irr}$), thorny jagged spires for $irr > 0.15$, and bioluminescent aberrant hue accents for radical mutants.

### Phase 2: Phenotypic Accents & Inspector CreatureAvatar Parity [P1] — ✅ Done
- [x] [P1] **BK-4 Ancestral Crystalline Core Patina** — Generational fill luminescence transition from soft young matte fill to deep crystalline obsidian/amber core glow as generation increases.
- [x] [P1] **BK-5 Soldier Razor Apex & Piercing Glint** — Extended needle apex geometry for razor soldiers ($\theta < 30^\circ$) with metallic/blood sheen on kinetic piercing tips.
- [x] [P1] **BK-6 Battle Veteran Wound Scars** — Render dark hash-mark notches and veteran scars along perimeter borders for creatures surviving grievous wounds (`scars > 0`).
- [x] [P1] **BK-7 CreatureAvatar & Radar Complete Visual Parity** — Mirror all generational rings, genesis sparks, jagged mutant spires, and scars inside `CreatureAvatar.tsx` and the Inspector panel.

### Phase 3: Interactive Map Lenses & Visual Filters [P2] — ✅ Done
- [x] [P2] **BK-8 Canvas HUD Lens Switcher Toolbar** — Add a quick lens switcher bar / keyboard shortcuts (`1`: Classic, `2`: Mutants, `3`: Generations, `4`: Dynasty).
- [x] [P2] **BK-9 Mutation & Generational Heatmap Shaders** — Render map in specialized analytic color-modes: Mutation Lens (dim normals, highlight irregulars in cyan $\to$ neon magenta) and Generational Epoch Lens (gradient from cold primordial blue to incandescent ancient gold).

---

## §BL Frontend High-Performance 60 FPS Engine — Optimization & LOD Pipeline — ✅ Done (6/6) — 2026-09-08

> **Context**: High-end client profiling revealed canvas draw-call saturation (~900,000 `fillRect` and string parses/sec on static elevation data), micro-phenotype overdraw without zoom LOD gating, GC allocation spikes inside the render loop, and high-frequency React component tree reconciliation. §BL delivers solid 60 FPS across all zoom levels.

### Phase 1: Canvas Rendering Optimizations & LOD Gating [P0] — ✅ Done
- [x] [P0] **BL-1 Offscreen Terrain & Elevation Hillshade Caching** — Pre-render elevation grid into an OffscreenCanvas bitmap once per terrain generation; draw with a single `ctx.drawImage()` call per frame instead of 15,000 `fillRect` calls.
- [x] [P0] **BL-2 Phenotype Level-of-Detail (LOD) Gating** — Gate micro-decorations (blade glints, starburst coronas, genesis sparks, halos, auras, chromatic aberration) when zoomed out (`camScale < 3.2`) to eliminate sub-pixel overdraw.
- [x] [P0] **BL-3 Zero-Allocation Batching & Scratch Pool Recycling** — Persist scratch arrays for `polygonsByCaste`, `crestsByColor`, `womenGroups`, and `polyGroups` in `renderCore.ts` to prevent GC thrashing.

### Phase 2: React Decoupling & Micro-Optimizations [P1] — ✅ Done
- [x] [P1] **BL-4 Static Lookup Hoisting & Loop String Cleanup** — Hoist `matTint` and signal color tables outside inner render loops; eliminate `Array.from` inside polygon vertex calculations.
- [x] [P1] **BL-5 React DOM Reconciliation Decoupling** — Throttle DOM UI state updates in `App.tsx` to 250ms for sidebars and HUDs while leaving the 60 FPS canvas render loop uninhibited.
- [x] [P1] **BL-6 Component Memoization & Render Guarding** — Ensure secondary panels (`ChronicleFeed`, `ClanPanel`, `OverviewPanel`) do not re-render during smooth canvas camera pans.

---

## §BM Chronicle, World History & AI Story — Backlog — ✅ Complete (26/26) — 2026-09-08

> **Context**: The Chronicle Feed is a live event stream with category/search filtering. The World History Modal aggregates ticks into day records and offers an AI Story prompt exporter (4 styles: Saga / Chronicle / Mythos / Tragedy → copy/download `.md`/`.json`). This roadmap improves UX, analytics depth, AI integration, and shareability.

### Phase 1: Quick-Win AI Story & Chronicle Enhancements [P1] — ✅ Done

- [x] [P1] **BM-1 "Major Moments" jump chips in Chronicle Feed** — Compute top 5 most dramatic days (highest casualties + conquest + schism) server-side or in `useMemo`; render as clickable pill buttons (`⚔️ Day 14 War`, `🌋 Day 31 Disaster`) above the feed for one-click scroll.
- [x] [P1] **BM-2 Per-day mini-story button** — Add a "Tell me about Day X" button on each expanded day row in World History → generates a single-day focused LLM prompt (only that day's events) → copy to clipboard. Great for social posts.
- [x] [P1] **BM-3 Hero / Villain auto-callout in AI prompt** — Auto-detect the creature with highest kill count (Hero) and highest betrayal count (Villain) from chronicle events; inject their name, caste, clan, and stats at the top of the LLM prompt for automatic dramatic focus.
- [x] [P1] **BM-4 "This Week in Flatland" mini-prompt** — Last 7 simulated days (last 8400 ticks) formatted as a concise newsletter-style paragraph prompt — recurring engagement hook accessible from the AI Story tab.
- [x] [P2] **BM-5 Language selector for LLM prompt** — Add EN / VI / FR toggle in the AI Story tab; prepend the chosen language as a system instruction (`Respond in Vietnamese.`) so the generated story matches the user's locale. Already fully i18n'd.
- [x] [P2] **BM-6 "Jump to tick" input in Chronicle Feed** — Text input in the chronicle controls row; typing a tick number filters/scrolls the feed to the nearest event at or after that tick.
- [x] [P2] **BM-7 Pin / bookmark specific days with notes** — Per-day star icon in World History; pinned days + optional one-line note stored in `localStorage`. Pinned days floated to top or marked with a badge.

### Phase 2: Timeline Visualization [P1] — ✅ Done

- [x] [P1] **BM-8 Horizontal epoch bar** — Color-coded horizontal bar across the top of the World History modal showing World Age eras (Golden Era / Ice Age / Chaos Era / Plague Age) with day tick markers for temporal orientation.
- [x] [P1] **BM-9 Population sparkline overlay** — SVG or Canvas sparkline of alive population per day rendered behind the day list or as a dedicated chart row; immediately reveals demographic booms and crashes.
- [x] [P2] **BM-10 "Day Navigator" scrubber slider** — Horizontal range slider to jump directly to any day in World History; selected day auto-expands in the feed. Replaces manual scrolling through 100+ days.
- [x] [P2] **BM-11 War arc connectors** — Curved SVG connectors between clan name nodes on the timeline showing wars fought, line weight proportional to casualty count.

### Phase 3: Clan Chronicle Cards & Analytics [P1] — ✅ Done

- [x] [P1] **BM-12 Per-clan biography panel** — "View Clan History" link in the expanded clan details or World History → opens a focused view with birth day, peak population day, wars fought, gods worshipped, schisms spawned, and extinction cause (if applicable).
- [x] [P1] **BM-13 "Records & Legends" leaderboard** — Dedicate a tab or section in World History to all-time records: most battles won clan, longest-lived creature, most children, largest single-day massacre, longest dynasty, most temples raised. Computed from `dayRecords` and clan data.
- [x] [P2] **BM-14 Clan rivalry matrix** — Grid heatmap of all clan pairs colored by historical hostility score (battles + betrayals + conquests). Identifies ancient enemies and grudging allies at a glance.
- [x] [P2] **BM-15 Cause-of-death breakdown per era** — In World History stats area, show stacked percentages of `dead_by_cause` split into 10-day era buckets: starvation vs. predation vs. plague vs. combat vs. old age.
- [x] [P2] **BM-16 Faith index over time** — Track temple count, miracle count, and epiphany rate per day; render as a simple line chart revealing "Age of Faith" vs. secular eras.

### Phase 4: In-App AI Generation [P0 big bet] — ✅ Done

- [x] [P0] **BM-17 In-app AI generation with user API key** — Add an "✨ Generate Story" button in the AI Story tab; user enters their own Gemini / OpenAI / Claude API key (stored in `localStorage`, never sent to our server); `fetch()` directly to the AI API with the existing LLM prompt; stream the response as rendered Markdown inline. Eliminates copy-paste-to-ChatGPT workflow entirely.
- [x] [P1] **BM-18 Named creature arc story** — In the Creature Inspector, add a "📖 Story Arc" button → assembles birth event + rank promotions + war kills + death event for that creature ID → copy-to-clipboard focused single-creature narrative prompt.

### Phase 5: Shareability & Deep Linking [P2] — ✅ Done

- [x] [P2] **BM-19 Deep link to specific day** — `?history=42` query param opens the World History modal directly scrolled to Day 42. Enables sharing a specific pivotal moment.
- [x] [P2] **BM-20 Deep link to clan biography** — `?clan=7` query param opens the clan biography panel for clan #7 directly.
- [x] [P2] **BM-21 Shareable World Card image** — Canvas API renders a static 1200×630 summary card (World Seed, top stats, clan roster, total days) downloadable as PNG for social media posting.

### Phase 6: Backend Improvements [P1] — ✅ Done

- [x] [P1] **BM-22 Server-side day aggregation endpoint** — Add `/api/history/summary?granularity=day` that pre-aggregates the 2000 raw major events into day records server-side, replacing the heavy `useMemo` computation in the frontend. Necessary as worlds grow beyond 3 000 days.
- [x] [P1] **BM-23 Clan epitaph table in DB** — When a clan goes extinct, persist its final stats (peak population, peak day, total wars, avatar totem, laws enacted, founding day) into a `clan_epitaphs` SQLite table for permanent historical record, queryable even after world reload.
- [x] [P1] **BM-24 Named creature record on death** — Persist `personal_name`, `title`, `clan_id`, `generation`, `born_tick`, `died_tick`, `kill_count` in the existing `creatures` table on death. Enables character-level queries and "Records & Legends" leaderboard.
- [x] [P2] **BM-25 Full-text search over events** — Add SQLite FTS5 index on `payload` JSON column; expose `q=` parameter in `/api/history` for fast name/clan text search in large chronicles.
- [x] [P2] **BM-26 World "Annals" endpoint** — `/api/annals` returns structured lore highlights: World Age transitions, largest war day, worst plague day, first miracle, first extinction, first temple — pre-packaged as structured JSON ready to inject into LLM prompts.

---

## §BN God Panel UX & Law Cleanup — Backlog

> **Context**: `GodPanel.tsx` exposes ~80 numeric + ~30 boolean parameters across 6 macro domains. The parameter surface has been cleaned up, fragmented groups merged (28 → 13), controls redesigned with log-scale sliders and loud master pills, and power-user features added (Panic button, localStorage draft, JSON export/import, undo/redo, session change history).

### Phase 1: Parameter Cleanup — Remove, Combine & Hide [P1] — ✅ Complete

- [x] [P1] **BN-1 Remove 5 internal numeric params from UI** — Dropped `hungry_ratio`, `starving_ratio`, `eat_radius`, `door_clearance`, `nutrient_cycle_rate`. Removed from `NUMBER_LAWS` and `LAW_HINTS`.
- [x] [P1] **BN-2 Combine 3 soft-cap knobs → "Carrying pressure" slider** — Replaced `damping_steepness` + `crowding_stress_mult` + `resource_strain_mult` with a single **"Carrying pressure"** 0–10 intensity slider that sets all three proportionally. Raw dials kept in Advanced accordion.
- [x] [P1] **BN-3 Combine morphology annealing → "Speciation speed"** — Replaced `annealing_start_generation` + `annealing_decay_generations` with a **"Speciation speed"** selector (Slow / Normal / Fast / Immediate) with custom overrides in Advanced accordion.
- [x] [P1] **BN-4 Combine vertex + angle jitter → "Shape jitter σ"** — Merged `vertex_mutation_std` + `angle_mutation_std` into one **"Shape jitter σ"** composite slider.
- [x] [P1] **BN-5 Simplify Extinction Safeguards to 1 slider** — Exposed only `safeguard_critical_pop` in the primary view; placed `safeguard_relief_ratio` and `safeguard_genesis_batch` in the Advanced accordion.
- [x] [P2] **BN-6 Combine disease params → "Plague severity"** — Added **"Plague severity"** selector (Mild / Moderate / Lethal) that sets outbreak rate, contagion chance, and lethality proportionally. Raw dials accessible in Advanced accordion.
- [x] [P2] **BN-7 Split `GodLaws` type into public + internal** — Moved the ~52 hidden dials into `GodLawsInternal`, keeping `GodLaws` clean with autocomplete while maintaining full API backwards compatibility.
- [x] [P2] **BN-8 "Advanced" collapsed accordion for Neuroevolution + Morphology** — Placed all 8 expert dials behind a collapsible `⚙️ Advanced Evolution` drawer, collapsed by default.

### Phase 2: Group & Section Consolidation [P1] — ✅ Complete

- [x] [P1] **BN-9 Merge Food groups → "Food & Agriculture"** — Combined `Food & Energy` + `Food Decay` + `Agriculture` + `Hunger & Sight` into one section with master toggles at top.
- [x] [P1] **BN-10 Merge Climate groups → "Climate & Shelter"** — Combined `Sky & Seasons` + `Weather Sickness` + `Shelter` into one section with master `weather_enabled` toggle card at top.
- [x] [P1] **BN-11 Merge Population groups → "Population Safety"** — Combined `Extinction Safeguards` + `Density Soft-Cap Damping` into one section with the single "Carrying pressure" slider and master toggle cards.
- [x] [P1] **BN-12 Merge Evolution groups → "Evolution Engine"** — Combined `Neuroevolution` + `Morphology` into one section with Speciation speed, Shape jitter, and the Advanced accordion.
- [x] [P2] **BN-13 Merge Combat groups → "Combat & Survival"** — Combined `Clan War` + `Predation` + `Desperation` into one unified section.
- [x] [P2] **BN-14 Merge Governance groups → "Society & Governance"** — Combined `Territory` + `Clan` + `Rebellion` + `Politics` into one section.
- [x] [P2] **BN-15 Collapse Physics sub-groups** — Combined 7 physics sub-groups into 2 consolidated groups (`Landscape & Elements`, `Cosmology & Disasters`). Net result: 28 sub-groups → 13.

### Phase 3: Control UI/UX Redesign [P1] — ✅ Complete

- [x] [P1] **BN-16 Logarithmic-scale sliders for huge-range params** — Switched to log-scale for `food_lifespan_ticks`, `age_length`, `day_length`, `house_decay_ticks`, and `season_length`.
- [x] [P1] **BN-17 Master-feature toggles as loud colored pills** — Prominent `.god-master-toggle` cards with icons, descriptions, and active green glow for major subsystem switches.
- [x] [P1] **BN-18 Gray-out gated params instead of hiding** — Gated parameters stay visible at 45% opacity with disabled interactions and a clear `(Disabled by [Gate])` badge.
- [x] [P2] **BN-19 Rename zone pills to plain language** — Renamed `safe` → `✓ balanced`, `strained` → `⚠ pushed`, `extreme` → `🔴 risk`.
- [x] [P2] **BN-20 Click baseline marker to revert** — Baseline markers and baseline text on the track are directly clickable to revert that individual parameter.
- [x] [P2] **BN-21 Mobile: large stepper + long-press repeat** — Added pointer down/up hold intervals for rapid increment/decrement stepping on mobile and desktop.

### Phase 4: Quick-Action Features [P1] — ✅ Complete

- [x] [P1] **BN-22 "Panic" rescue button in footer** — Added `🆘 Panic Rescue` button in footer: sets food to 600, activates emergency safeguards, and turns off plagues & disasters with confirmation.
- [x] [P1] **BN-23 Persist unsaved draft to `localStorage`** — Unsaved modifications automatically save to `localStorage` (`fl_god_laws_draft`) with restore/discard banner on reopen.
- [x] [P2] **BN-24 Export / Import laws as JSON** — Added `📋 Export JSON` and `📥 Import JSON` with modal parser and validation.
- [x] [P2] **BN-25 Law change log in session** — Session history drawer tracking modifications with timestamps and old → new values.
- [x] [P2] **BN-26 Undo/redo stack** — `Cmd/Ctrl+Z` undo and `Cmd/Ctrl+Shift+Z` / `Ctrl+Y` redo with toolbar buttons.

### Phase 5: Search & Filter Improvements [P2] — ✅ Complete

- [x] [P2] **BN-27 Cross-tab search** — Search query simultaneously filters presets and laws, showing match counts on tab pills and clickable preset chips.
- [x] [P2] **BN-28 Filter by zone** — Added `🔴 Risk only` toggle chip in search bar to isolate parameters in the `extreme` risk zone.

---

## Parked — decided, not pending (8 items; 9 before dedupe)

These are documented decisions with rationale, not overdue work. The original 22 unchecked items included 9 such; 2 were the same task.

| # | Item | Rationale |
|---|------|-----------|
| 1 | **AQ P2 Wind affects thrown weapon range** | No thrown-weapon system to bend (spears are melee buffs). Revisit when ranged combat exists. |
| 2 | **AQ P2 Ramps / staircases** | Needs vertical layer semantics the flat-point body model doesn't have; grades already cost/slow. |
| 3 | **AQ P2 Weight & load-bearing** | Planiverse beam mechanics need a structural graph; walls already block except doors. |
| 4 | **AZ P2 `__slots__` on `Config`** | Single instance, every `self.config.X` is a dict lookup — low win. Verify `RT.config` never gains dynamic attrs. |
| 5 | **BA P1 6.3 + P0 7.4 Rebless the determinism golden** *(consolidated)* | Re-record `backend/tests/test_determinism_golden.py` checkpoints (ticks 100/250/500) for the NN engine. Deferred until NN fully replaces `AL` utility AI (currently soft-gated; `7.4` was a duplicate of `6.3`). |
| 6 | **BA P1 9.2 Fill sensor slots 9–13** | Slots remain 0; full scent/signal integration needs §AN grid wiring — deferred to avoid churn before 8.1 hard switch. |
| 7 | **BA P0 9.4 Vectorize the raycast sensor loop** | Python loop stays within 50 ms CI budget (`test_n2000_budget` ≤50 ms; 12 ms target is N150). Defer numpy vectorization until profiling shows bottleneck. |
| 8 | **BA P0 10.1 Extend `test_neuroevolution.py`** | Deferred until 8.1 hard switch — soft-gated wiring would make tests flaky. Current 8 tests cover SoA/genome/forward/sensors/mating/latch/budget. |
| 9 | **BJ-1 (SoA incremental) and BJ-2 (single cache pass) can land before or after §BI** | Can be implemented directly on `simulation/core.py` without conflicting with mixin modularization, and provides immediate production speedup. |
| 10 | **BJ-4 (Lockless serialization) must not modify `sim.step()` semantics** | State read outside the lock must be immutable snapshots or deltas. |

---

## Guardrails

### Conflict map — what must **not** land in parallel [P0]
1. **BH-1 Polar Crossover before BG-9 Inspector Radar** — Two-parent geometry structure must be stabilized before wireframe visualizer binds to it.
2. **BH-4 Live NN crossover on `_birth` before BH-5 block rates** — Base crossover wiring in `_birth` must exist before adding block-wise mutation rates.
3. **BG-1 Isosceles & BG-2 Mutated Polygons can land independently in frontend** without touching backend simulation loop.
4. **BI-1 Scaffold before any mixin extraction** — Package structure must exist before moving methods into mixin files.
5. **BI-3→BI-9 Mixin extractions are sequential** — Each extraction must pass `pytest -q` 487/487 before the next begins. Least-coupled modules first (serialization → ecology → environment → settlement → theology → society → lifecycle).
6. **BI-10 Creature update decomposition last** — The 2,572-line `_update_creature` touches helpers from every other mixin. Extract only after all other mixins are stable.

---

## Archive index
§F Infrastructure — Database · §A Life cycle · §B Reproduction · §C Irregularity & caste · §D Health & disease · §E Environment · §G God-law & observability · §H Food ecosystem · §I Society · §J Creature profile · §K Documentation · §L Shelter · Cross-system synergies · §W World generation · §N New frontiers · §O Ecosystem depth · §P Clan depth · §Q Creatures 2.0 · §R Weather as life · §S WorldBox inspirations · §T Sustainability & performance · §U Mobile UI/UX · §V Clan founding redesign · §X Fixes · §X2 Communication II · §Y UI polish · §Z Terminal frontend · §AA Performance round 2 · §AB Politics · §AC Desperation cannibalism · §AD OS-log persistence · §AE Food decay · §AF Performance & Massive Scale · §AG Autonomous Evolution · §AH Energy Dynamics · §AI TUI Feature Parity · §AJ Next-Gen Performance (3 phases) · §AK Clan Lifecycle · §AL Creature Cognitive Agency · §AM Food & Agriculture · §AN Communication, Language & Diplomatic · §AO Nocturnal Perils · §AP Unified Theology · §AQ 2D Physics · §AR Creature Senses · §AS Clan Leader Importance · §AT Four Immediate Issues · §AU Performance Optimizations · §AV Frontend & TUI Performance · §AW Emergency 1–2 TPS · §AX High-Density 20 TPS · §AY Multi-Core Engine · §AY2 World Simulation Presets · §AZ Backend Performance Audit · §BA Micro-Neural Network · §BC Geometric Physics & Morphological Evolution · §BD World Analytics & Telemetry Engine · §BE Creature Movement AI Overhaul · §BF Early Population Boom Limiter · §BG Mutational Shape & Visual Phenotypes · §BH Next-Gen Evolutionary Mutation Engine & Neuroevolution · §BI Simulation Engine Decomposition · §BJ Production Performance & Tick Budget Restoration · §BK Mutational Accents, Avatar Parity & Map Lenses · §BL Frontend High-Performance 60 FPS Engine · §BM Chronicle, World History & AI Story · §BN God Panel UX & Law Cleanup

Full completed content → [`docs/roadmap-archive.md`](docs/roadmap-archive.md)
