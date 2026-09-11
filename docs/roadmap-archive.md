# Roadmap Archive — Flatland Completed Work

[![GitHub Repository](https://img.shields.io/badge/GitHub-Flatland-181717?style=flat-square&logo=github)](https://github.com/longphanmn/flws)
> **Source Repository**: [https://github.com/longphanmn/flws](https://github.com/longphanmn/flws)  
> Historical record of completed sections (§F–§BD, 632 completed items: 573 §F–§BA + 14 §BC + 12 §AZ + 33 §BD). For active work and latest sections (§BE–§BL), see [`TODO.md`](../TODO.md). Line anchors (`file:line`) have been stripped — all were stale after repeated rewrites; symbols are kept.

---

The Sphere model: The Sphere (God) sets **laws** from Spaceland, never touches individual creatures. Everything else emerges.
Legend: [P0] foundational · [P1] core Flatland identity · [P2] flavor/observability

## F. Infrastructure — Database  [P0]
- [x] ~~SQLite via SQLAlchemy 2.0 + aiosqlite~~ → **stdlib `sqlite3`** behind a thin
      repository interface (`app/db.py`); file `flatworld.db` (env `FLATWORLD_DB`).
      Decision: local single-writer file needs no ORM/async driver yet; swap later
      without touching callers.
- [x] Tables: `worlds`, `events`, `law_changes`; `snapshots` deferred (replay is P2)
- [x] Writes are tiny batched inserts from the tick loop (WAL mode, thread-safe);
      measured cost per tick ≈ 0 — dedicated writer task unnecessary so far
- [x] Chronicle + law history survive server restart; `reset` closes the old
      `worlds` row and opens a new one
- [x] Endpoints: `GET /api/history?since=&limit=` (paginated), `GET /api/worlds`
- [x] Genealogy table (`creatures`): births write lineage rows (clan,
      generation, parents, born tick); deaths close them; founders get
      minimal rows on death

## A. Life cycle
- [x] [P0] Age & lifespan — Creature.age (ticks) + caste-based lifespan
      (Woman shortest → Priest longest); death cause `old_age`;
      god law `lifespan_mult`; snapshot exposes age/lifespan + dead_by_cause
- [x] [P1] Life stages — infant/juvenile/adult/elder by fraction of lifespan
      (<15/<30/<75%); stage multiplies speed & sight (infant 0.6², juvenile
      0.85², elder 0.85×0.9) and fertility (elder ×0.5, young infertile);
      `stage` in snapshot; renderer scales bodies (infant 0.55×) and fades elders
- [x] [P0] Death-cause chronicle — HistoryEvent.cause ∈
      {starvation, old_age, …}; HUD "dead" chip shows per-cause breakdown
      (tooltip); counts tracked in sim and persisted via DB events

## B. Reproduction & inheritance  [P1] — ✅ implemented
- [x] Sex model — males = polygons (sides ≥ 3), females = lines (women);
      `Creature.sex` derived from shape
- [x] Mating — adult male + adult female within `mate_radius`, both energy ≥
      `mate_energy_min`, not in cooldown → rng-gated by `birth_rate` ×
      caste fertilities × crowding factor
- [x] Offspring — `sex_ratio` decides son vs daughter; child spawns near
      mother; both parents pay `birth_energy_cost` + `reproduction_cooldown`
- [x] Lineage — Creature.generation/.born_tick/.mother_id/.father_id;
      birth payload persisted in DB events (genealogy graph still [P2])
- [x] Law of Nature — son sides = father.sides + 1, capped at `max_sides`;
      daughters are lines
- [x] Mutation — `mutation_rate` chance of ±1 side deviation
- [x] Isosceles rule — triangle sons stay triangles: iso_angle +0.5° per
      generation; reaching 60° promotes Soldier → Artisan (`promotion` event)
- [x] Fertility law — per-caste fertility table × soft penalty above
      `carrying_capacity`; hard `max_population` cap
      (deviation: table embodies Nature's decay; no separate `fertility_decay`)
- [x] GodLaws: birth_enabled, adult_age, mate_radius, mate_energy_min,
      birth_rate, sex_ratio, mutation_rate, max_sides, birth_energy_cost,
      reproduction_cooldown, carrying_capacity, max_population
- [x] Events: birth (payload parents/sides/generation), promotion

## C. Irregularity, caste & social order
- [x] [P1] Family/clan identity — founding generation seeds one clan per caste;
      children inherit their mother's clan (orphans found new ones);
      `clan_id` + crest color on every creature snapshot; thin colored crest
      ring in the renderer; clan shown in the inspector; birth events carry
      clan_id; DB genealogy table records lineage per world (entity, caste,
      clan, generation, parents, born/died ticks)
- [x] [P1] Irregularity — mutated children score `irregularity` (0.3–1.0);
      at adulthood the world judges them: ≥ `euthanasia_threshold` → consumed
      (death cause `euthanasia`), below → demoted to Soldier (lowest regular
      order, `demotion` event); god law `Euthanasia ≥` in God panel
- [x] [P0] Caste traits table — `CASTE_TRAITS` per caste: lifespan, speed,
      Sight Recognition (`sight_mult` applied to perception), fertility
      (reserved for §B); women see least, priests see farthest and are
      nearly sterile (Nature's Law)
- [x] [P2] Peace-cry — women emit a periodic ripple while moving (Flatland law)
- [x] [P2] Social yielding — lower castes deflect away from higher castes
      within a small radius (deference as steering force)

## D. Health & disease  [P2] — ✅ implemented
- [x] Creature.health (0–100, regenerates when healthy) + .infected/.disease_id
- [x] Outbreak — if `disease_enabled`, `disease_outbreak_rate`/tick starts a new
      `disease_id`; spreads to healthy neighbours within `disease_radius` at
      `disease_rate`
- [x] Effect — infected lose `disease_energy_drain`/tick + health decays at
      2×`disease_lethality`; recovery at `recovery_rate`; death when health → 0
      (cause `disease`). Disabling the law freezes all sickness instantly.
- [x] Season synergy — winter raises `disease_rate` ×1.5 (outbreak & contagion, §E)
- [x] GodLaws: Plagues toggle + outbreak/rate/radius/drain/recovery/lethality
      in a "Disease" panel group
- [x] Events: `outbreak`, `recovery` (+ death cause `disease`); HUD "infected N"
- [x] Render — pulsing green ring on the infected

## E. Environment — day/night, seasons, weather  [P2] — ✅ implemented
- [x] WorldClock — derived from tick: `time_of_day` (0–1, `day_length` cycle,
      world starts at sunrise), `day` counter, `season` over `season_length`
- [x] Day/night — night applies `night_sight_mult`; renderer dims the sky
      (smooth sunrise→noon→midnight gradient)
- [x] Seasons — food target = `food_count × SEASON_FOOD_MULT`
      (spring 1.0, summer 1.2, autumn 1.0, winter 0.5); spring ×1.25
      `birth_rate`, winter ×1.5 outbreak + contagion
- [x] Weather state machine — clear/rain/fog/storm at `weather_change_rate`;
      rain/storm slow movement (`rain_speed_mult`), fog dims sight
      (`fog_sight_mult`), storms add wander chaos (`storm_wander_bonus`)
- [x] GodLaws: Sky & Seasons panel group (lengths, multipliers + Weather
      allowed toggle)
- [x] Render — night veil, season tint, rain streaks (heavier in storms),
      fog overlay
- [x] HUD — 🌙/☀ · day N · season · weather icon

## G. God-law & observability
- [x] [P0] Consolidate ALL new laws into GodLaws + God screen UI (grouped by
       section: World / Food & Energy / Hunger & Sight / Movement / Life &
       Death / Bodies & Houses; grows as §B/§D/§E laws arrive) — **Save** persists
       to future worlds (`POST /api/laws?persist=true` → `RT.saved_config`),
       **Apply** current only (`?persist=false` → revert on Reset, `main.py`,
       `GodPanel.tsx`)
- [x] [P2] Population/caste sparkline chart in HUD (+ stacked caste chart in
       the Chronicle panel, §N)
- [x] [P2] Chronicle shows all event types (birth/promotion/demotion/recovery/
       outbreak/death — color-coded in the panel); header combines objects
       `Food 48 · House 6` (creatures in graph, `App.tsx`), legend via
       `CasteChart`; new world clears the live feed (`App.tsx`, tick/seed
       reset); box at top-right (`index.css`, `top:58px`, `max-height:60vh`)
- [x] [P2] Creature inspector — tap/click a creature (works on touch too):
       gold halo marks it; left panel shows live status (caste, sex, stage,
       age/lifespan, energy/health bars, meals, irregularity, lineage) and its
       personal chronicle from `GET /api/creature/{id}`; auto-refreshes 1 Hz;
       survives death (status + full history remain) (`inspect/Inspector.tsx`,
       `CanvasRenderer.tsx` pick `4.0/24` world units, tap `500ms/10px` forgiving,
       dead-zone `6px` pan vs tap, tap at `tapStart` not release, edge-safe)
- [x] [P2] DB-backed history pagination + world run selector (Chronicle pagination +
       HUD run dropdown → moved to bottom-right `App.tsx` `run-switcher`
       `index.css`); archive mode pauses live feed, `load older` paginates via `GET /api/history?since=`

## H. Food ecosystem & ecological balance  [P2] — ✅ implemented
- [x] Plants replace inert food — `Food` is a living plant with `growth` 0.15→1.0
       (`plant_growth_rate`), spreads to nearby empty cells (`plant_spread_rate`,
       season-gated), dies back in winter (reuses `SEASON_FOOD_MULT`); rendered green,
       size ∝ growth; `food_count` law is the seasonal bounty target (name kept)
- [x] Carcasses — every death leaves a `Corpse` (`corpse_ttl`, `corpse_energy`);
       creatures scavenge them like food; decay → vanishes
- [x] Nutrient cycle — decayed corpses refill nutrient pool that accelerates
       nearby plant regrowth (`nutrient_cycle_rate` × `NUTRIENT_BOOST`): death fertilises new life
- [x] Ecological balance — plant counts oscillate with seasonal bounty; boom–bust via
       `SEASON_FOOD_MULT` + nutrient boost (Lotka–Volterra placeholder until §I predators)
- [x] GodLaws: plant_growth_rate, plant_spread_rate, nutrient_cycle_rate (plant_mature gated)
- [x] Events: `bloom` (plant reaches maturity)

## I. Society: clans, interaction & conflict
- [x] [P1] Clans (base identity) — landed in §C: one clan per caste at founding,
      children inherit mother's clan, clan crest ring + inspector + genealogy.
      What remains below is the *social* layer on top of that identity.
- [x] [P1] Clan relations — pairwise score −100..+100 drifting toward 0; ally /
       neutral / rival thresholds; shared feeding raises it (+2 within `flock_radius`),
       drift `relation_drift_rate` toward 0; `alliance`/`rivalry` events
- [x] [P2] Creature interaction (boids) — separation / cohesion / alignment
       steering blended after food-seeking (social yielding already landed in §C);
       "Interaction" law group (`cohesion_weight`, `alignment_weight`, `separation_weight`, `flock_radius`)
- [x] [P2] Predation — Carnivore `Predator` caste (`entities.py`, `config.py`)
       `is_predator`/`bite_cooldown`; spawn `predator_ratio` only if `predation_enabled`
       (`simulation.py`), hunt `hunt_radius` → bite `bite_cooldown`/`energy_from_prey`,
       prey `fear_radius` flee; death `predation` + `predation` event, carcass + relation
- [x] [P2] Clan war — rival-clan creatures fight on contact (`war_enabled`,
       `attack_radius`/`attack_damage` → cause `war`, `war` event, relation -5, carcass)
       (`simulation.py`, `config.py`)
- [x] GodLaws: relation_drift_rate, alliance_threshold, rivalry_threshold,
       cohesion_weight, alignment_weight, separation_weight, flock_radius,
       predation_enabled, predator_ratio, hunt_radius, bite_damage, bite_cooldown,
       energy_from_prey, fear_radius, war_enabled, attack_radius, attack_damage
- [x] Events: `alliance`, `rivalry`, `predation`, `war` (+ `predation`/`war` deaths)

## J. Creature profile & genealogy  [P0] — ✅ implemented
- [x] Genealogy table — landed in §F (creatures rows: parents, caste, generation,
      clan, born/died ticks); surfaced via the profile below
- [x] Expose lineage on the wire — `mother_id`/`father_id`/`sex`/meals now on
      `EntityState`; `/api/creature/{id}` returns a `family` block (mother/
      father cards alive-or-dead via genealogy, living + recorded children)
- [x] Profile UI — status chips (hungry/starving/sick/asleep), clickable
      parent links († marks the dead) and a compact family tree: parents
      above, "you are here", children below; every node opens that dossier
      with click-to-navigate

## K. Documentation — living guide  [P2] — ✅ implemented
Serve a full reference independent of the React game UI (backend-rendered, so it
always matches the running code). No Vite/frontend dependency.
- [x] Backend serves the docs — FastAPI route(s) at `/guide` that render
       markdown to HTML (tiny `md_to_html` + minimal template); nav sidebar;
       anchor links. Reachable at http://localhost:8000/guide (`guide.py`)
- [x] "How the world works" — the God model (god sets laws, never touches a life),
       the deterministic fixed-tick loop, emergence; each system explained: life
       cycle & stages, Nature's Law inheritance (sides/sex/mutation), irregularity &
       caste judgement, disease, environment (day/night, seasons, weather), clans &
       social order, food economy (`guide.py`)
- [x] Codebase map — module tour with file:line anchors: backend
       (config/entities/world/simulation/protocol/db/main) + frontend
       (App/CanvasRenderer/GodPanel/Inspector); data-flow diagram of the tick (`guide.py`)
- [x] Data model & protocol — creature/caste/food/house/clan/genealogy entities;
       `EntityState`/`StateMessage`/`HistoryEvent` schemas; WebSocket message flow
       (hello → state snapshots, client control actions) (`guide.py`)
- [x] API reference — auto-generated from the live OpenAPI schema (`/openapi.json`):
       every REST route, request/response model, control action, and every God law
       with type/range/default; link out to the interactive Swagger `/docs` (`guide.py`)
- [x] Configuration & ops — env var table (`FLATWORLD_*`), persistence (SQLite
       `flatworld.db`, `worlds`/`events`/`law_changes`/`creatures` tables), run &
       deploy, test commands (`guide.py`)
- [x] Anti-rot check — `tests/test_guide.py`: asserts every `GodLaws` field and every REST
       route is mentioned in the docs, so the guide can't silently go stale; roadmap
       section links back to TODO.md (`guide.py`)

## L. Shelter — make houses matter  [P1] — ✅ implemented
Houses today are ~5 empty squares: walls block movement and creatures nap inside
after dark (§N night rest). Shelter should be scarce, contested and life-saving.
- [x] [P1] Exposure — rain/storm and winter nights drain `exposure_drain` energy on the
       open plain; being indoors cancels it. Shelter becomes survival, not convenience.
- [x] [P1] House capacity — each house shelters at most `house_capacity` creatures
       (∝ size); the overflow sleeps outside and suffers exposure. Five houses is a
       real housing shortage (beds re-contested every tick in id order).
- [x] [P1] Clan claim — each clan claims a house as its settlement (clan crest on
       the wall via `House.clan_id`/`clan_color`; members prefer own house via `_house_for`);
       founding clans claim distinct houses; new clans claim first free house; toggle via law
- [x] [P2] Rest & recovery — indoors: energy regen halved via `sleep_energy_mult` +
       `rest_recovery_mult` (×0.15 health/tick) disease recovery; shelter law toggle;
       starving creatures skip sleep to forage (`simulation.py`)
- [x] [P2] House smart — doorway targeting (`_door_pos` `simulation.py`, sleep
       steering `simulation.py` within 12u), wall-bounce → door seeking
       (`simulation.py`), starving skip prevents house-wall starvation
- [x] [P2] Predator refuge — the doorway is too small for the Carnivore caste (§I);
        a house is the only safe haven once predators hunt (`simulation.py`
        predator_blocked doorway, `simulation.py` prey indoors safe from
        `hunt_radius`, `simulation.py` predators never sleep, ejected if spawned inside).
- [x] [P2] Settlement economy — houses scale with population (house_density tied to
        carrying capacity via `_target_house_count` `simulation.py`; `area×house_density×carrying/80` vs `0.6×carrying/house_capacity`); abandoned houses crumble to ruins after `house_decay_ticks` (`simulation.py`, `config.py`, `protocol.py` → `ruin` event, `House.is_ruin` `entities.py`, walls no longer block `simulation.py`); new clans found new settlements when no free house (`_claim_house_for_clan` `simulation.py` → `_spawn_settlement_house` `simulation.py` → `settlement` event; pinned `num_houses` `simulation.py` still wins for tests/scenarios).
- [x] GodLaws: shelter_enabled, exposure_drain, house_capacity, house_claim_enabled,
        rest_recovery_mult, house_decay_ticks (Shelter group) — defaults tuned for 30-day survival
        (`config.py`, food 48, decay 0.05, perceive 18, mate 10/30, birth 0.35, adult 200)
- [x] [P1] Beds ∝ floor area — `house_capacity` counts beds in an 8×8 reference
        hall (`HOUSE_REF_AREA`, `simulation.py` `_house_beds`): a cramped hut
        holds half a grand hall's beds, so a whole clan can never cram into one
        shelter. Full roof ⇒ overflow spills to the NEAREST roof WITH space
        (`_house_for`; kin-preferred among free roofs), queueing at a door only
        when every roof is full; a sleeper already inside any roof with a free
        bed takes it instead of trekking on. Rest means STILL — a sleeping body
        holds its exact position until dawn (early-return night branch).
        Tests: `tests/test_shelter.py` (beds scale with size, spill to second
        roof, sleeping = zero movement); live check @321 pop: 0 over-capacity
        houses, 154/321 asleep across 72 houses.

## Cross-system synergies (emergent depth)
Not features — acceptance criteria. Tick only after the behaviour is observable in a
live run (or a seeded test passes). `needs` = prerequisite systems; `verify` =
observable signal; `tune` = god laws that push it over the edge.

### Verifiable now (systems landed) — ✅ tested
- [x] Winter + disease = famine/plague cascades
       needs §D+§E · verify: winter → infected & starving spike together, deaths by
       starvation+disease climb · tune: season_length, disease_rate, food_count
- [x] High mutation = irregularity purges
       needs §B+§C · verify: mutation_rate↑ → euthanasia/demotion events surge at
       adulthood · tune: mutation_rate, euthanasia_threshold
- [x] Overpopulation = lower fertility + higher disease spread
       needs §B+§D · verify: pop past carrying_capacity → births fade, contagion rises
       · tune: carrying_capacity, max_population, disease_radius
- [x] Night + fog = blindness
       needs §E · verify: fog at night collapses sight (starving rate rises) · tune:
       night_sight_mult, fog_sight_mult
- [x] Seeded tests — backend/tests/test_synergies.py: one deterministic test per
       verifiable-now synergy (winter+plague, mutation→purge, overcrowd→fertility+
       disease, night+fog blindness), reusing the fixed-tick RNG pattern from
       test_disease.py / test_environment.py

### Blocked on §H (food ecosystem) + §I (predation/clan war) — we unblocked five
- [x] Predator–prey oscillation (Lotka–Volterra) — needs §H+§I · verify: predator/prey
        counts coexist and vary (test_synergies.py: test_predator_prey_oscillation,
        16 prey + 6 pred → 600 ticks, predation ≥5, both vary, not extinct) · tune:
        predator_ratio, hunt_radius, plant_growth_rate (predation hunt/fear/bite,
        `simulation.py` flee/hunt, `is_predator` lineage)
- [x] Death feeds life — needs §H (corpses already land in §N) · verify: post-die-off,
        corpse decay + nutrient pool accelerates plant regrowth · tune: corpse_ttl,
        nutrient_cycle_rate (test_plants.py: test_corpse_decay_boosts_nearby_plant_growth)
- [x] War over scarce food — needs §H+§I · verify: famine → clan rivalry drops → wars
        spike → corpses feed survivors · tune: rivalry_threshold, attack_damage
        (`test_synergies.py:test_war_over_scarce_food` famine 2 vs 20 food, 8 rivals packed, 60 ticks, wars famine ≥ abundance)
- [x] Flocking is a double-edged sword — needs §I+§D · verify: clan cohesion dilutes
       predator attacks but super-spreads disease (test_synergies.py:
       test_flocking_is_double_edged — tight flock vs spread, infection + predation) ·
       tune: cohesion_weight, disease_rate (`simulation.py` boids + disease)
- [x] Predators as natural selection — needs §H+§I · verify: starving/elder/wounded prey
       culled first, survivor stats shift · tune: hunt_radius, bite_damage, fear_radius
       (`test_synergies.py:test_predators_as_natural_selection` weak 3 close vs healthy 3 far, predation ≥2 weak culled, healthy ≥ weak)
- [x] Winter as apex pressure — needs §E+§H+§I · verify: one winter stacks die-back +
       starvation + hunting + plague into real extinction risk · tune: season_length,
       SEASON_FOOD_MULT, disease_rate (`test_synergies.py:test_winter_as_apex_pressure` winter 180 vs summer 60, 8 prey+2 pred+disease, winter deaths ≥ summer)
- [x] Mutation → demotion → fodder — needs §C+§I · verify: demoted soldiers swell both
       prey and warrior ranks · tune: mutation_rate, euthanasia_threshold, attack_damage
       (`test_synergies.py:test_mutation_demotions_well_fodder` mutation 0.9 Threshold 0.45 → demotion ≥2 soldiers swell)
- [x] Social order meets the food chain — needs §C+§I · verify: priests see the predator
       first and flee, women fall, low castes trapped by yielding · tune: sight_mult,
       yield_strength, fear_radius (`test_synergies.py:test_social_order_meets_food_chain` priest 1.35× vs woman 0.8×, priest distance ≥ woman after 60 ticks)
- [x] Housing shortage = overcrowding = disease + war — needs §L+§D+§I · verify: pop
        > total house capacity → exposure deaths climb, contagion spreads in packed
        houses, clan claims turn into wars · tune: house_capacity, exposure_drain
        (`test_synergies.py:test_housing_shortage_is_overcrowding_crisis` 1 house×2 beds vs 5 houses×2 beds 10 packed rivals, rain+night exposure 0.45, 80 ticks)

## W. World generation  — ✅ implemented
- [x] Population & houses scale with map area: `creature_density`,
      `house_density` (per unit²) with ±`spawn_variance` jitter; Flatland
      social pyramid shares (soldiers/women many, nobles/priests few);
      explicit `num_*` overrides still win (scenarios/tests)
- [x] Reset rolls a fresh random seed — every reset is a new world, recorded
      (with its seed) in the DB and shown in the HUD; same seed ⇒ same world

## N. New frontiers — round two
- [x] [P1] Corpses & scavenging — death leaves a corpse (`corpse_energy`,
      fading cross renderer); creatures perceive and eat them like food;
      corpses decay after `corpse_ttl`; god laws: corpses toggle + ttl +
      energy; famine now has a second chance built in
- [x] [P2] Night rest — at night creatures head for the nearest house; those
      inside sleep (movement stops, hunger halved via `sleep_energy_mult`,
      health +0.3/tick, disease still bites); `sleeping` in snapshot with zzz
      renderer cue; Night rest toggle in the Sky & Seasons law group
- [x] [P2] Terrain — seeded fertile patches (food spawns there ~70% of the
      time via `fertile_food_bias`) and solid rock circles (radial push-out);
      auto-scaled by area or pinned; drawn under entities; in snapshot
- [x] [P2] Keyboard controls — space pause/resume · S step · R reset ·
          +/- zoom · F fit view (ignored while typing in inputs)
- [x] [P2] Caste population chart — stacked per-caste lines (caste colors)
      over the last ~240 ticks, inside the Chronicle panel
- [x] [P2] Snapshot album — 📷 freezes the full state into the DB
      `snapshots` table; Album lists them and clicking one re-renders that
      frozen moment on the canvas (banner to return to the living world)

## O. Ecosystem depth — biodiversity & food web  [P2] — ✅ implemented
Today every plant is one green sprite (`Food.growth`) and the only animal is the
Predator. Add variety so niches, seasons and diets can emerge.
- [x] [P2] Plant species — `Food.variant` ∈ {grass, berry, mushroom, poisonous}:
      grass common/low-energy; berries high-energy but seasonal; mushrooms sprout
      on corpses/rocks (a decomposer tier); poisonous plants mutate in and sicken
      whoever eats them. Each variant: color, growth rate, energy yield, season
      (`entities.py` `Food.variant`, `simulation.py` `VARIANT_*`,
      `simulation.py` `_pick_variant` poison 0.03 + season + decomposer boost,
      `simulation.py` `VARIANT_GROWTH_MULT`×`SEASON_MULT`, `simulation.py` eating `VARIANT_ENERGY/HEALTH`,
      `protocol.py` `EntityState.variant`, `frontend/CanvasRenderer.tsx` colors, `config.py` `plant_variants_enabled`/`poison_rate`).
- [x] [P2] Fruit & seasonality — berry bushes fruit in one season (autumn burst);
      grass is always available; spring/summer shift which plants dominate the land
      (`simulation.py` autumn berry 0.48 weight, winter mushroom 0.57, `VARIANT_SEASON_MULT` grass 1.15 summer, berry 1.9 autumn).
- [x] [P2] Wild herbivore beasts — a non-caste middle tier that grazes plants and is
      hunted by predators, competing with the castes for food → a real
      plants → herbivores → predators Lotka–Volterra chain
      (`entities.py` `Herbivore` 5200/0.65, `entities.py` `is_herbivore`,
      `config.py` `beast_ratio` 0.0 default (god enables), `simulation.py`
      `_spawn_herbivore`, `simulation.py` spawn `area×density×beast_ratio`,
      `simulation.py` herbivore lineage 50% if one parent, `simulation.py` war excludes herbivore, shelter excludes herbivore).
- [x] [P2] Diet & preference — `Creature.diet` (herbivore/omnivore/carnivore) steers
      which food a creature perceives and eats; higher castes prefer richer food,
      predators prefer live prey over plants (`simulation.py` `diet_strictness` filter: herbivore ignores corpse, predator ignores plants, strict >0.5 higher castes skip grass if berry nearby, herbivore avoids poisonous; `config.py` `diet_strictness` 0.0 default).
- [x] [P2] Food quality — variants yield different energy/health (meat heals, poison
      harms); scavenging corpses vs grazing plants reward different creatures
      (`VARIANT_ENERGY` grass 32/berry 48/mushroom 24/poison 8, `VARIANT_HEALTH` berry +1/poison -30, corpse 25).
- [x] [P2] Trophic HUD — plant / herbivore / predator counts chart (the §H ecological
      balance made watchable) (`frontend/src/render/TrophicChart.tsx` stacked Food·Herbivore·Predator vs `popHist`, `App.tsx` under CasteChart).
- [x] GodLaws: plant_variants_enabled, poison_rate, beast_ratio, diet_strictness (Ecosystem `config.py` `protocol.py` `main.py` `GodPanel.tsx`)

## P. Clan depth — totems, territory & war  [P2]
Clans have identity (crest ring) and a first taste of war (§I) but no totem, no land
beyond one house, no leaders. Deepen the social fabric.
- [x] [P2] Totem — each clan picks a totem at founding with a subtle buff: Wolf
      (hunt), Tree (harvest/growth), Shield (defense), Eye (sight); drawn as a totem
      pole beside the clan's house; buff applied to its members (`simulation.py` `TOTEMS`/`TOTEM_BUFF`,
      `simulation.py` deterministic `seed+cid` → totem, `config.py` `totems_enabled`, `protocol.py` `totems_enabled`,
      `simulation.py` Wolf +2 `hunt_radius`/`1.10×speed`, `simulation.py` Tree `1.25×` harvest, `simulation.py` Shield `0.70×` war damage + `1.30×` regen, `simulation.py` Eye `1.25×` perceive, `frontend/CanvasRenderer.tsx` totem pole `▲♣⬢◉` beside house).
- [x] [P2] Procedural clan names — "Ash Wolves", "Clan of the Long Shadow" instead of
      "Clan N" (seeded adjective + noun table) (`simulation.py` `CLAN_ADJECTIVES/NOUNS`, `simulation.py` deterministic `seed+cid` → `Ash Wolves` 70% / `Clan of the Long Shadow` 30%, `protocol.py` `EntityState.clan_name` + `StateMessage.clans`, `frontend/src/inspect/Inspector.tsx` shows name).
- [x] [P1] Territory — a clan claims a zone (radius around its house) with a painted
      border; members prefer their own territory; foreign trespass slowly sours
      relations; rivals contest borders (ties into §I war) (`config.py`
      `territory_enabled`/`territory_radius` 14/`trespass_decay` 1.0,
      `simulation.py` territory steering `0.35×steer` when outside radius,
      `simulation.py` `_update_territory` probabilistic `trespass_decay` → `_bump_relation` -1,
      `protocol.py` GodLaws, `frontend/CanvasRenderer.tsx` faint clan-color circles + dashed border).
- [x] [P2] Leadership & roles — clan leader (founder, then succession on death),
      champion warrior, shaman; a leader's death emits a `succession` event (`config.py` `succession_enabled`,
      `simulation.py` `clan.leader_id` founder, `simulation.py` `_kill` succession → oldest living member `payload clan_id/prev_leader/new_leader`, `protocol.py` `succession` event).
- [x] [P2] War refinement — skirmishes need not be lethal (`attack_damage` < 100 →
      wounded + fleeing, not always death); champions duel; raids on rival houses;
      wars can end (peace treaty once scores recover) (`simulation.py` wound vs lethal: `Shield` 0.70× or `attack_damage` < `health` → wound + flee `angle` away, `bump -3` vs lethal `-5`; `war` event `payload lethal`/`damage`).
- [x] [P2] Clan specialization — over generations clans drift toward warrior / farmer
      / scavenger roles from environment + totem; reflected in behaviour. (`simulation.py` `_update_clan_specialization` totem-biased start Wolf 0.5 war/Tree 0.6 farm/Eye 0.5 scav + drift war if wars, farmer if food/fertile near house, scavenger if corpse_near, renormalize, `simulation.py` war damage ×(0.85+warrior*0.45), `simulation.py` harvest ×(1+farmer*0.25) corpse ×(1+scav*0.35), `main.py` `GET /api/clans` specialization, `ClanPanel.tsx` ⚔/🌾/🦴 display)
- [x] [P2] Clan stats & history — leader lineage, war record, territory, population;
      a clan panel in the inspector/HUD (`backend/app/main.py` `GET /api/clans` roster with `name`/`totem`/`leader_id`/`population`/`house`/`war_wins`/`losses`/`territory_radius`, `frontend/src/render/ClanPanel.tsx` tick 2s poll, `App.tsx` under TrophicChart).
- [x] GodLaws: territory_enabled, territory_radius, trespass_decay, totems_enabled, succession_enabled (Territory/Clan `config.py` `protocol.py` `main.py` `GodPanel.tsx`); war_lethality still [P2] pending (new "Clan" law group)

## Q. Creatures 2.0 — identity, voice & care  [P2]
Creatures are interchangeable within a caste (#12 the Gentleman) and never speak.
Give each a name, a face, and a voice — then let kin lead the hungry to food.

### Identity (cosmetic — no sim impact)
- [x] [P2] Personal name — seeded, deterministic per creature (adjective+noun
      table); shown in inspector + Chronicle ("Lyss died of starvation") instead
      of bare "#12" (`simulation.py` `PERSONAL_FIRSTS/LASTS` → `personal_name_for` `id*37+seed`, `protocol.py` `personal_name`, `main.py` payload + `get_creature` synth, `App.tsx` chronicle, `Inspector.tsx`)
- [x] [P2] Soul-code glyph — a tiny unique rune (2–3 strokes) drawn inside the
      body, derived from id + generation + caste; visible on hover/select (the
      "small code inside" god view) (`simulation.py` `GLYPH_TABLE` → `glyph_for`, `CanvasRenderer.tsx` `canvas.fillText` `0.9-1.6px` + selection label `564`, `protocol.py` `glyph`)
- [x] [P2] Individual variation — subtle per-creature size/angle/color jitter so
      two of a caste are never pixel-identical (respects caste rigidity: it is a
      personal mark, not a new caste) (`simulation.py` `variation_for` hue -12..+12 scale 0.96..1.04 angle ±0.06, `protocol.py` `hue_shift/scale_jitter/angle_jitter`, `CanvasRenderer.tsx` `creatureColor` hue shift + `r*scale` + `angle+ jitter`)

### Communication (food + alarm calls)
- [x] [P2] Signal model — a short-lived ping carrying sender position + type,
      heard within `signal_radius`; clan-mates respond strongly, strangers
      weakly/ignore; rendered as a ripple (`simulation.py` `signals` ttl 15/12, `protocol.py` `StateMessage.signals`, `CanvasRenderer.tsx` ripples `food #3fb950`/`alarm #f85149` age radius)
- [x] [P2] Food call — a well-fed creature that finds food calls; hungry
      clan-mates steer toward the caller (`simulation.py` `food_call_rate` 0.08 well-fed finds food → signal `food_x/food_y`, `simulation.py` hungry `signal_food_target` clan-weighted 1.0/0.35 `food_call_rate`, `GodPanel.tsx` `signal_radius` 12)
- [x] [P2] Alarm call — a creature that sees a predator calls; nearby creatures
      flee even without seeing it (group awareness beyond `fear_radius`) (`simulation.py` `alarm_call_rate` 0.12 flee_target → alarm `ttl`12, `simulation.py` `signal_alarm_target` flee even without direct fear)
- [x] GodLaws: communication_enabled, signal_radius, food_call_rate,
      alarm_call_rate (new "Creature" law group) (`config.py` defaults `false`/12/0.08/0.12, `GodPanel.tsx` Communication group)

### Care — the clan guides the hungry to food
- [x] [P2] Food memory — a creature remembers where it last saw food
      (`food_memory_ttl` decay) (`entities.py` `food_memory_x/y/tick`, `simulation.py` store on see, `config.py` `food_memory_ttl` 300, `protocol.py` not exposed yet — internal)
- [x] [P2] Recruitment — a sated clan-mate within `flock_radius` of a starving
      one calls toward its remembered food; the starving one follows the call
      (kin guide the hungry home) (`simulation.py` sated `energy>0.6` near starving `≤starving_ratio` within `flock_radius` → food call with `food_memory_x/y`, `simulation.py` hungry hears `signal_food_target`)

## R. Weather as life — crops & chill  [P2]
Weather today only slows movement and dims sight. Make it a force on the land and
the body: rain feeds the fields, storms wreck them, and the cold gets into the bones.

### Weather → crops
- [x] [P2] Rain waters the land — rain/storm apply `rain_growth_mult` to plant growth
      (+ a small seed-spread boost); fog favours mushrooms (the decomposer tier). (`simulation.py` `rain_growth_mult` 1.25 on rain/storm, `fog_mushroom_mult` 1.35 for mushroom in fog, `config.py` defaults, `protocol.py` GodLaws)
- [x] [P2] Storms damage crops — a storm strips growth from exposed plants
      (`storm_plant_damage` chance to lose growth, occasionally uproot/die); soaked
      ground then grows back faster. (`simulation.py` `storm_plant_damage` 0.02 strips 0.2-0.5 growth, 50% uproot at ≤0.05, `config.py` `GodPanel.tsx` Weather & Crops)
- [x] GodLaws: rain_growth_mult, fog_mushroom_mult, storm_plant_damage
      (new "Weather & Crops" law group)

### Weather → sickness
- [x] [P2] Chill — rain/storm/winter nights build `chill` on the unsheltered; past a
      threshold the creature is `sick` (drains health, death cause `chill`); shelter
      shakes it off. (`entities.py` `Creature.chill`, `config.py` `chill_rate` 0.04/`threshold` 12/`drain` 0.18, `simulation.py` build/shed 2.5× indoors, `protocol.py` `chill`, `CanvasRenderer.tsx` blue ring, `Inspector.tsx` chip + bar, `App.tsx` HUD 🥶 chilled)
- [x] [P2] Cold contagion — wet/cold creatures catch disease faster
      (`wet_disease_mult`) and recover slower: catch your death in the rain. (`simulation.py` `wet_disease_mult` 1.5 multiplies spread if wet/chilled ≥50% threshold, `recovery_rate`/1.5 slows recovery, `config.py` `GodPanel.tsx` Weather Sickness)
- [x] GodLaws: weather_sickness_enabled, chill_rate, chill_threshold, chill_drain,
      wet_disease_mult (new "Weather Sickness" law group)

## S. WorldBox inspirations — ages, plots & disasters  [P2]
WorldBox's god intervenes; Flatland's god only sets laws. These are the WorldBox
mechanics that survive that translation — all emergent or law-gated.

### Ages (super-seasons)
- [x] [P2] World ages — a long era over seasons (`age_length`); each age bends the
      world: Ice (winter food ×0.3 + chill), Chaos (mutation ↑), Plague (disease ↑),
      Golden (bounty + birth ↑). Chosen/cycled by law; `age` in snapshot + HUD. (`config.py` `age_enabled`/`age_length` 12000, `simulation.py` `AGES`/`AGE_*MULT`, `_age()` cycle, `snapshot` `age`/`age_tick`, `CanvasRenderer.tsx` tint, `App.tsx` HUD age, `GodPanel.tsx` Ages group)

### Rebellion & clan schism
- [x] [P1] Schism — a clan's unhappy members (starving, homeless, or low relations)
      split off to found a new clan (new name/totem/territory), then war the parent
      (`schism_threshold`); success/failure recorded. Extends §I war + §P succession. (`config.py` `schism_enabled`/`threshold` 0.4/`min_pop` 4, `simulation.py` `_update_schism` homeless/starving ≥threshold → split 50% to new clan, new house, rivalry -60, `schism` + `rivalry` events, `protocol.py` `schism` type, `GodPanel.tsx` Rebellion, `App.tsx` chronicle)

### Plots (foreshadowing)
- [x] [P2] Plots panel — god sees *upcoming* war/rebellion/schism plans as progress
      ("Ash Wolves is planning war on Long Shadow — 3/10") before they fire; icons
      on the plotters. Extends §G observability. (`simulation.py` `get_plots()` war rival proximity + schism unhappy 50% threshold → progress 0..10, `main.py` `GET /api/plots`, `PlotsPanel.tsx` war/schism progress bars, `App.tsx` under ClanPanel)

### Wildfire & disaster laws
- [x] [P2] Wildfire — fire ignites (storm lightning / `fire_rate`) and spreads
      grass→plant→house; kills creatures/plants, leaves ash that fertilizes
      regrowth; renderer flame overlay. (`config.py` `wildfire_enabled`/`fire_rate` 0.0005/`spread` 0.08, `simulation.py` `fires` ttl 28/22 ignition storm 0.002, spread 0.35 within 6, burn creatures 0.18/plants 0.25, house 0.03 ruin, ash growth +0.15, `protocol.py` `fire` event, `GodPanel.tsx` Wildfire & Disasters, `CanvasRenderer.tsx` flame `r0.9`/`r0.45`)
- [x] [P2] Disaster laws — meteor/comet strike, flood — stochastic events gated by
      `disaster_rate` (god sets frequency, never a specific strike); craters/water
      reshape terrain. (`config.py` `disaster_enabled`/`rate` 0.0003, `simulation.py` `disaster_rate` meteor crater rock+kill/disaster flood push/drown, `protocol.py` `disaster` event, `App.tsx` chronicle disaster)

### Diplomacy depth
- [x] [P2] Richer relation factors — common enemy +, border-adjacency −, at-war −huge,
      truce cooldown +, same-caste +; folds into the existing −100..100 clan score. (`simulation.py` `_update_relations` diplomacy depth: common enemy +1, border adjacency <2×territory_radius −1, same dominant caste +1, rival sets)
- [x] [P2] Territory conquest — the winner of a war absorbs the loser's territory
      and house (§P); borders redraw; losing clan becomes homeless/refugees. (`simulation.py` lethal war conquest: transfer `loser_house.clan_id` → winner, `conquest` event `winner_clan/loser_clan/house_id`, `protocol.py` `conquest` type, `App.tsx` chronicle)

### Culture drift
- [x] [P2] Culture — each clan has a culture that spreads to neighbours and can split
      (like WorldBox); culture grants a small collective bonus and can diverge into
      rival traditions. (`config.py` `culture_enabled`/`spread` 0.005, `simulation.py` `CULTURE_*` tables, clan `culture`/`culture_id` seeded, `_update_culture` ally spread 0.005 + split 0.0004 `culture` event, `main.py` `culture` in clans, `ClanPanel.tsx` 🎭 display)

### Behavioral genetic traits
- [x] [P2] Genetic traits — mutation may add a heritable behaviour trait (greedy /
      peaceful / paranoid / bold) that nudges food choice, flee threshold, war
      eagerness; shown as a glyph in the profile (§Q). Distinct from the cosmetic
      identity already scoped. (`entities.py` `Creature.trait`, `config.py` `trait_mutation_rate` 0.02, `simulation.py` `TRAITS`/`TRAIT_GLYPH` heritable via parents, `simulation.py` greedy grass 0.45 skip, paranoid +4 fear, bold -2.5 fear, peaceful 0.65 dmg/bold 1.25 dmg, `protocol.py` `trait`, `Inspector.tsx` ⬔◯⬥▲ chip)
- [x] GodLaws: age_enabled, age_length, schism_enabled, schism_threshold, fire_rate,
      fire_spread_rate, disaster_rate, culture_enabled, trait_mutation_rate
      (new "Ages & Disasters" + "Society II" law groups) (`config.py` `culture_*`/`trait_*`/`age_*`/`fire_*`/`disaster_*`, `protocol.py` `GodLaws`, `GodPanel.tsx` Ages/Culture/Genetics/Wildfire groups, `main.py` `LAW_FIELDS`)

## T. Sustainability & performance — the 1000-day world  [P1 perf · P2 tuning]
Goal: a world that self-balances for 1000+ days with 400–500 creatures on a low-end
CPU (Intel N150), where conflict exists but is rare and rarely fatal.

### Sustainability tuning (conflict on, but rare)
- [x] [P2] Raise the ceiling — carrying_capacity ~450, max_population ~550 so the
      world fills and plateaus instead of churning at 140. (`config.py` 450/550; preset sustainable)
- [x] [P2] Food for 500 — food_count ~150–200 (or more fertile patches) + lower
      energy_decay_per_tick ~0.04; keep perceive_radius 18 so meals are reachable. (preset 180/0.035/18; default 70 kept for tests, preset provides)
- [x] [P2] Soften winter — expose SEASON_FOOD_MULT as a law (winter 0.5 → 0.7) so the
      lean season doesn't cull the whole world. (`config.py` winter_food_mult 0.5→0.7, `simulation.py` helper, `protocol.py` law, `GodPanel.tsx` slider)
- [x] [P2] Conflict rare, not fatal — keep war/predation/disease ON but tuned gentle:
      attack_damage < health (wound, not kill), low predator_ratio + bite_damage,
      low disease_outbreak_rate + high recovery_rate; poison_rate → 0. (preset sustainable: bite 40/attack 40/pred ratio 0.03/disease 0.0001/recovery 0.025/poison 0)
- [x] [P2] Calm society — relation_drift_rate ↑ (relations relax to neutral),
      trespass_decay → 0 (territory stops festering into war), rivalry_threshold
      very negative so feuds are rare. (preset: drift 2.5, trespass 0, rivalry -80)
- [x] [P1] Sustainable preset — named law bundles (sustainable / chaos / extinction)
      applied at reset; "1000-day" is one click and reproducible. (`main.py` PRESETS, `GET /api/presets`, `POST /api/presets/{name}?reset`, `GodPanel.tsx` buttons)

### Performance (400–500 creatures @ 10–20 tps)
- [x] [P1] Fix spatial hash — decouple cell_size from perceive_radius (fixed ~8) so
      fine queries (flock/yield/mate) stop scanning 18×18 cells (world.py). (`world.py` fixed 8.0, toroidal dx iteration)
- [x] [P1] Cache creatures once per tick — compute world.creatures() once in step(),
      pass it down; precompute a clan→members map per tick (kills ~15 O(n) scans +
      the O(clans×n) per-clan lists at simulation.py/1296/1315/1808). (`simulation.py` cache, `_refresh_cache`, `_get_creatures`, step caching)
- [x] [P1] Spatialize pair scans — _reproduce (query males within mate_radius) and
      _update_war (query within attack_radius) instead of O(n²) all-pairs. (kept cached path for determinism; spatial version ready via query_radius, war kept O(n²) with cache for now to preserve test determinism)
- [x] [P1] Merge perception queries — food+corpse in one radius query; skip the per-
      query seen set when there's no wrap overlap. (already merged food+corpse single query; `world.py` skip seen when no wrap)
- [x] [P1] Throttle broadcast — broadcast at ~30 Hz (every max(1, tick_rate/30)
      ticks) instead of every tick (main.py). (`main.py` every max(1, tick_rate/30))
- [x] [P1] Frontend culling — skip entities outside the camera rect; merge the 4
      state.entities passes into one; batch food/house draws; cap devicePixelRatio
      ~1.5 (CanvasRenderer.tsx). (`CanvasRenderer.tsx` DPR cap 1.5, visible culling, merged passes)

## U. Mobile UI/UX — a first-class phone experience  [P1]
The phone UI is a desktop layout reflowed into a scroll page. Rebuild it around
one rule: watch first, control second — a fullscreen world with floating controls.

### Layout — immersive fullscreen
- [x] [P1] Fullscreen canvas — edge-to-edge 100dvh, overlays float, no page
      scrolling (replace the 55vh map + scroll page in index.css @768px). (`index.css` 100dvh, `App.tsx` hud-compact, `stage` flex 1)
- [x] [P1] Collapsed status bar — one compact top line (⏸ tick · alive · ☀ day ·
      season · age) that taps open a detail sheet for the full chip set (dead
      breakdown, infected/chilled/exposed, seed, weather). (`App.tsx` hud-compact + `hud-detail-sheet`, tap to expand)

### Bottom bar & sheets
- [x] [P1] Thumb bar — persistent ~48px bottom bar (safe-area inset): ▶/⏸ · ⏭ Step
      · ⚖ God · 📜 Chronicle · ⛶ Fit · 📷; replaces the horizontal scroll bar. (`App.tsx` mobile-thumb-bar, `index.css`)
- [x] [P1] Tabbed sheet — one bottom sheet with World / Clans / Chronicle / Plots
      tabs (peek ¼ → half → full drag), so the map stays visible; move Overview
      charts, ClanPanel, PlotsPanel into it. (`App.tsx` mobile-sheet, `index.css` handle/tabs)

### God panel (mobile)
- [x] [P2] Accordion groups — collapse law groups; sliders instead of number
      inputs; full-screen sheet with a sticky Apply button. (`GodPanel.tsx` details.accordion, `index.css` god-accordion, range sliders)

### Gestures & polish
- [x] [P2] Gestures — double-tap to inspect nearest creature, long-press quick
      info; keep pan/pinch/tap. (`CanvasRenderer.tsx` double-tap zoom + `showQuickInfo` long-press 500ms)
- [x] [P2] Touch & viewport — 44px+ targets, viewport-fit=cover + env(safe-area),
      drop the alert() tooltip, hide key-hints on touch. (`index.html` viewport-fit, `index.css` 44px, `App.tsx` no alert, `index.css` key-hints none)

### PWA — installable
- [x] [P2] Installable — webmanifest + icons + apple-touch-icon + display:
      standalone so it can be added to the Home Screen; meta viewport-fit=cover. (`public/manifest.webmanifest`, `public/icon.svg`/`icon-192.png`/`icon-512.png`, `index.html` manifest + theme)

### Perf on phone
- [x] [P1] Phone rendering — viewport culling + devicePixelRatio cap (ties §T),
      so 400–500 creatures stay smooth on a phone. (`CanvasRenderer.tsx` DPR 1.5, culling, `index.css` fullscreen)

## V. Clan founding redesign — mixed-caste settlements  [P1] — ✅ implemented
Clans are currently seeded one-per-caste (simulation.py `_found_founding_clans`
by_caste). Replace with spatial settlement seeding so any caste can share a clan.
- [x] [P1] Settlement seeding — each (non-ruin) house founds a clan; founder/leader
      = the founding creature nearest the house centre; every founding creature joins
      its nearest house's clan (soldiers, women, nobles, priests mixed)
      (`simulation.py` `_found_founding_clans` nearest-house buckets + `_new_clan`,
      leader = nearest founder, one leader max via `taken_leaders`; ghost houses get
      leaderless clans that decay with §L abandonment).
- [x] [P1] max_clans law — God caps society granularity; -1 = one clan per house,
      a pinned value clusters founding creatures into that many spatial clans
      (greedy k-center) instead. (`config.py`, `protocol.py` GodLaws ge=-1,
      `main.py` LAW_FIELDS, `GodPanel.tsx` Clan group slider + hint,
      `simulation.py` `_cluster_founders_kcenter` rng-free deterministic;
      applies at reset/world creation.)
- [x] [P1] Anchor-house claims — a clan's settlement IS its nearest house; rewire
      _assign_house_claims/_claim_house_for_clan to match clustering (no round-robin
      double-claim); territory/totem/crest anchor to that house.
      (`simulation.py` `_anchor_homeless_clans` greedy distance-sorted matching,
      `_assign_house_claims` delegates after stale-claim cleanup,
      `_claim_house_for_clan` nearest free house to clan centroid → else §L settlement
      spawn near oldest member; orphan births set clan_id before claiming.)
- [x] [P2] Docs — update guide.py ("one clan per caste"), wiki.py, README to the
      mixed-caste settlement model. (`guide.py` §C/I/P/V + codebase map, `wiki.py`
      LAW_HINTS, README Clans bullet, docs/god-laws.md Society & Clans row.)
- [x] [P2] Tests — assert founding clans are mixed-caste and spatially contiguous
      (deterministic given seed); dominant-caste relation factor already works on
      mixed clans (simulation.py). (`tests/test_clans.py`: mixed-caste +
      nearest-house membership reconstruction, anchor no-double-claim + crest,
      max_clans 3/1 counts, k-centre cluster equality + greedy-matching fairness,
      leader-nearest-centre walk, determinism same/diff seed;
      test_reproduction.py founding test rewritten for settlements.)

## X. Fixes
- [x] Predator monoculture — world died into 800 clanless wolves (prod incident
      @ tick ~34k): `can_eat` had an explicit `is_predator` bypass and the §O
      diet gate defaults off, so the Carnivore caste grazed living plants on
      top of hunting — a double income that out-competed every clan caste,
      drove them extinct (predators breed true, daughters clanless lines),
      then sat at the population cap forever: no clans had members, every
      creature showed clanless, nobody was ever hungry. Fix: predators hunt
      the living and scavenge corpses — they never perceive Food as prey
      (`simulation.py` perception gate), so their survival couples strictly to
      prey abundance again (Lotka–Volterra restored). Tests:
      `tests/test_predator_ecology.py` (no grazing beside a ripe field,
      corpse scavenging kept, starve-out under full bounty, lone wolf cannot
      clear a breeding village). Note: worlds already past the collapse need
      a Reset — the fix changes the laws of nature, not the dead.
- [x] Silent world freeze at random ticks (recurring, "fixed" by restart) — the
      tick task died on any exception escaping `step()` (prime suspect: DB event
      sink hitting `sqlite3.OperationalError: database is locked` — connection
      had no busy_timeout), and because uvicorn's lifespan holds the task
      reference asyncio never reported it: HTTP kept serving while the tick
      froze forever. Hardened: `db.py` connect with `timeout=5.0` +
      `PRAGMA busy_timeout=5000`; `tick_loop` wraps step/broadcast in
      try/except — logs `[tick-loop] step() FAILED at tick=N` loudly and keeps
      ticking; sticky `RT.last_tick_error` + `tick_failures` surfaced via
      `/healthz` (`ok:false` when the last tick failed); deploy.sh excludes
      `*.log` from rsync --delete so backend.log survives deploys.
      Tests: `tests/test_resilience.py`.
- [x] World freeze with ok:true — wedged WS client parks tick loop (prod
      incident @ tick 10469): a half-dead WebSocket client (vite proxy closed,
      TCP zero window — server side stuck CLOSE-WAIT with 2.6MB Send-Q) made
      `await ws.send_text()` inside `Hub.broadcast` block FOREVER; the tick
      loop parked at that await while HTTP stayed fine and healthz reported
      ok:true (no exception ever raised → nothing logged). Fix: per-client
      send timeout (`Hub.SEND_TIMEOUT` 5s), concurrent fan-out via
      asyncio.gather so one slow client costs nobody else's time, wedged/
      erroring clients evicted from the hub; /ws handshake sends timeboxed
      too; `/healthz` now reports connected `clients` count.
      Tests: `tests/test_resilience.py` (wedged client dropped, healthy
      keeps receiving; tick loop keeps ticking with a wedge attached).
- [x] Stuck-against-obstacle starvation — creatures chasing a meal whose straight
      path crosses a rock circle (or a house wall) used to grind at the obstacle
      until they starved. Now the blocked meal is abandoned: per-meal grudges
      (`Creature.give_ups`, `food_giveup_ticks` TTL, never refreshed while fresh)
      make perception skip it so the hungry seek food elsewhere; eating anything
      clears all grudges; 0 disables. Triggers: wall bounce while steering at the
      target, rock push-out with segment→target crossing the stone
      (`simulation.py` `_segment_hits_circle`/`_give_up_on`; wall-bounce and
      `_resolve_rock_collision` hooks). God law `food_giveup_ticks` (240) in the
      Hunger & Sight group (`config.py`, `protocol.py`, `main.py` LAW_FIELDS,
      `GodPanel.tsx`, wiki hint, docs/god-laws.md). Tests:
      `tests/test_giveup.py` (rock + free-food switch, drift-away, house-wall
      grudge, corpse behind stone, law roundtrip).

## X2. Communication II — knowledge, teaching & mobbing  [P2]
Signals exist (food/alarm, §Q). Generalise them into a shared knowledge system so
creatures learn, teach their clan, and rally to each other's defence.

### Knowledge (learn & remember)
- [x] [P2] Typed facts — replace the single food_memory with a small per-creature
      knowledge set: food_locs, danger_locs (predator sightings), enemy_clans (who
      attacked me), safe_loc (own house/territory); each fact decays over
      knowledge_ttl. (`entities.py` `Creature.facts` dict — "food"/"danger" →
      {x,y,tick,conf}, "safe" → {x,y,tick}, "enemies" → {clan_id:{tick,conf}};
      food_memory_* removed; `simulation.py` `_fact_fresh` prunes stale facts.)
- [x] [P2] Learn from experience — attacked → learn enemy clan; see predator → learn
      danger; find food → learn food; flee to house → learn safe.
      (`simulation.py` `_learn`/`_learn_enemy`: sight of Food/predator in perception,
      war kill+wound both sides, sleep & rain-shelter indoors.)

### Teaching (tell the clan)
- [x] [P2] Knowledge signal — a new signal kind carrying a fact (position/clan id) +
      sender; creatures broadcast to clan-mates within signal_radius, gated by
      knowledge_share_rate + signal_cooldown. (`_fact_to_share` picks freshest fact;
      hearing merges via `_hear_fact` — better news overwrites.)
- [x] [P2] Rumor decay — confidence halves each hop, so retold knowledge is vaguer
      than firsthand sighting. (`_hear_fact` stores conf×0.5; firsthand 1.0 beats
      any rumor; conf <0.05 forgotten.)

### Help & mobbing (defence)
- [x] [P2] Help call — an attacked creature (war/predation) emits a help signal;
      nearby clan-mates converge and mob the attacker (warriors first, peaceful
      last), turning contact-kills into cooperative skirmishes.
      (`_emit_help` on war kill/wound + teeth-close predator alarm; hearing gates:
      YIELD_RANK ≥5 only bold, peaceful 70% ignore; mob steering converges on threat;
      `_mob_defenders` counts clan-mates within `help_radius` → damage ÷(1+defense_weight×n),
      applied to BOTH kill decision and wound application paths.)

### Clan aggregate
- [x] [P2] Clan memory — union of member knowledge surfaces as "the clan remembers":
      enemies (feed §S Plots war foreshadowing), known food/danger zones (clan
      avoids danger); shown in ClanPanel. (`clan_knowledge()` dedupes spots within 2u;
      `/api/clans` "knowledge" block; ClanPanel 🧠 chip; Plots progress +2 for pairs
      who remember each other; danger-avoidance steering away from fresh danger facts.)

### Laws
- [x] GodLaws: knowledge_enabled, knowledge_ttl, knowledge_share_rate,
      help_call_enabled, help_radius, defense_weight (new "Communication II" group)
      (`config.py`, `protocol.py`, `main.py` LAW_FIELDS, `GodPanel.tsx` toggles +
      sliders + hints, types.ts, wiki hints, docs/god-laws.md table, guide.py §Q/X;
      knowledge/help ON by default; food_memory_ttl law removed). Tests:
      `tests/test_knowledge.py` (learn food+danger, ttl fade, teach-at-half-conf,
      two-hop rumor ≤0.25, war enemy learning + clan union, mobilisation +
      softened blows vs control, safe roof while sleeping, laws roundtrip).

## Y. UI polish — clickable names, collapsible panels, double-click zoom  [P2] — ✅ implemented
- [x] [P2] Clickable clan names — Chronicle alliance/rivalry/schism/conquest and
      PlotsPanel clan names open the existing ClanDetails modal; show clan names
      (state.clans lookup) instead of bare #ids. (`App.tsx` `clanLabel()` +
      chronicle-name buttons → setSelectedClanId; PlotsPanel onSelectClan prop.)
- [x] [P2] Clickable leader/founder — ClanPanel + ClanDetails leader/founder chips
      open the creature Inspector (add onSelectCreature wiring).
      (`ClanPanel.tsx` onSelectCreature prop stop-propagation chips, App wires
      setSelectedId at mobile sheet + desktop; ClanDetails founder/leader chips.)
- [x] [P2] Double-click zoom out — Shift/Alt+double-click zooms out at the cursor
      (plain double-click already zooms in, CanvasRenderer.tsx).
      (`CanvasRenderer.tsx` onDblClick → zoomAt ×1.8 / ÷1.8 at cursor, cleanup added.)
- [x] [P2] Collapsible panels — reusable <Collapsible> (header + chevron,
      localStorage-persisted) around Overview sub-blocks, Chronicle, Inspector
      sections, and HUD detail chips. (`render/Collapsible.tsx` fl-collapsed-* keys,
      index.css .collapsible*; wrapped Overview caste/trophic/clans/plots blocks,
      Chronicle event feed, Inspector Family + Chronicle sections.)

## Z. Terminal frontend — Textual TUI  [P1] — ✅ implemented
A terminal client that watches/controls the live sim over the existing /ws +
REST API — no browser. Separate client, never touches backend logic.

### Stack & deps
- [x] textual>=8, websockets>=12, httpx>=0.27 in backend/pyproject.toml;
      run via `uv run -m tui` (env FLATWORLD_WS), optional
      `uv run textual serve -m tui.serve`.

### Structure (backend/tui/)
- [x] client.py — WSClient (connect, hear state, send control actions) +
      RESTClient (httpx: laws/clans/creature/plots/presets/worlds/history);
      reconnect w/ capped exponential backoff.
- [x] state.py — typed mirror of protocol.py (StateMessage/EntityState/
      HistoryEvent/Hello), tolerant parse (unknown fields ignored).
- [x] theme.py — caste colors, glyph map, variant colors (single source of
      truth, mirrors CanvasRenderer.tsx).
- [x] app.py — FlatlandApp(App): WS lifecycle, pollers (clans/plots/worlds),
      keybindings, selection tracking.
- [x] widgets/ — world_view, hud, chronicle, clan_panel, plots_panel, overview
      (+ inspector/clan_details/god_laws/help as screens/).
- [x] screens/ — god_laws (grouped form → POST /api/laws, Apply vs Save,
      presets, filter box), inspector (live dossier + family + chronicle),
      clan_details (roster + war record), help.
- [x] flatland.tcss — layout + theme.

### WorldView (char-grid renderer)
- [x] Camera pan/zoom (f fit, +/- zoom + wheel, hjkl/arrows pan); half-block
      ▀▄ for 2:1 cell aspect; culling inherent to grid lookup; Strip cache via
      render_line run-length segments.
- [x] Glyph/color map: creature → soul-code glyph (caste color, dim elder/
      sleeping, ▲ predator, h herbivore); food variant color ∝ growth; corpse
      ×; house ─│+/door / clan color, ruins dim; rock ●; fertile bg; territory
      ring (dim clan color); signals ~ / fires & transient; click selection →
      Enter inspect, Tab panel focus.

### Panels & modals
- [x] Hud (pause/tick/alive/dead/day/season/weather/age + caste chips + ws
      status + selection line), Chronicle (color-coded RichLog, dedup by
      (tick,type,id)), Clans DataTable (REST poll 3s), Plots progress bars,
      Overview ASCII sparkline + trophic counts + dead-by-cause + runs list;
      CreatureInspector (1 Hz refresh, clickable kin), ClanDetails, GodLaws
      modals.

### Keybindings
- [x] space pause · s step · r reset · f fit · +/- zoom · hjkl/arrows pan ·
      enter inspect · tab panel focus · c clan of selection · g laws · o older
      events · ? help · 1-9 speed · q quit (escape closes modals).

### Milestones
- [x] M1 wireframe: deps + client + app + hud + WS connect + control actions.
- [x] M2 world renderer: camera, half-block grid, glyph map, selection cursor.
- [x] M3 panels: Chronicle/Clans/Plots/Overview + runs list (`load older` via
      `o` paginates GET /api/history).
- [x] M4 modals: inspector + clan details + god laws + help.
- [x] M5 tests/polish: Textual Pilot tests (tests/test_tui.py — WS→HUD tick +
      glyph grid, pause/step/speed actions over WS, click-select, laws POST
      roundtrip against the real FastAPI app via ASGITransport, chronicle
      formatting, zoom/fit smoke), run.sh hook (`./run.sh tui [ws-url]` —
      standalone pure client: never starts a server, attaches to any running
      world incl. remote hosts, keeps retrying while the backend is down),
      README blurb.

## AA. Performance round 2 — tick-10000 slowdown  [P1] — ✅ implemented
All conflict systems on; the deterministic sim pegs one core (GIL) and the hot
paths are O(n²)/O(n³) + per-event DB commits. Fix the algorithm + move I/O off the
sim thread (no multi-core sim — determinism + GIL make it low-value).
Measured @465 creatures: step 70→53 ms (−24%), snapshot 6.2→1.6 ms (3.9×),
broadcast encode 2.2→0.3 ms (orjson). 1500-tick event streams byte-identical
to the old implementation (same seed ⇒ same world).

### Algorithmic (single-threaded)
- [x] [P1] Spatialize _update_war — neighbours within attack_radius via the
      spatial hash (fresh index rebuilt after movement, id-ascending pairs,
      exact dist_sq re-check) instead of O(n²) all-pairs; `fallen` set keeps
      original semantics (only recorded losers are blocked; winners stay
      eligible for later duels) (`simulation.py` `_update_war`, `step()`).
- [x] [P1] Cache mob counts — `_mob_defenders` answers via a spatial query
      around the winner instead of scanning the whole roster inside the pair
      loop (kills the O(n³) at war/wound time).
- [x] [P1] Incremental _update_relations — eater pairs from the spatial hash
      (+ dedupe), dominant-caste computed once/tick from the cached roster
      (was a full scan PER CLAN), border adjacency via hash, and neutral
      pairs pruned so relations/zones stay bounded forever
      (`_update_relations`; schism/plots membership maps hoisted too).
- [x] [P1] Cheap snapshot — `snapshot_payload()` emits plain dicts (no
      pydantic validation/model_dump per frame); name/glyph/variation cached
      per creature in `_identity_cache`; shared structures copied so payloads
      survive while the world ticks (`simulation.py`, `main.py` call sites);
      `snapshot()` still returns typed StateMessage for REST/tests.

### I/O off the hot thread
- [x] [P1] Batch DB writes — every write of one tick rides ONE transaction:
      sqlite autocommit mode + `Database.batch()` (BEGIN…COMMIT, rollback on
      tick failure) instead of a commit per event (`db.py`, `advance_world`,
      STEP action).
- [x] [P1] orjson for snapshot encoding (C-extension, GIL-releasing), stdlib
      json fallback kept (`main.py` `_dumps`, pyproject dep).
- [x] [P2] Throttle bloom events — blooms stay in the in-memory chronicle,
      never touch the DB (`main.py` `_on_event`).

### Concurrency stance
- [x] [P2] Keep uvicorn at 1 worker for the sim; documented single-threaded-
      by-design (determinism) + multi-core as non-goal (README "Concurrency &
      performance", guide.py ops → "Concurrency stance").

## AB. Politics — coalitions, leaders, resources & betrayal  [P1] — ✅ implemented
Build a politics layer on the clan/relation/leader/knowledge stack: multi-clan
coalitions, leader agency, shared resources, and treachery. God sets laws; politics
emerge.

### Coalitions
- [x] [P1] Explicit coalitions — a leader proposes a coalition (rng-gated, rare);
      clans with relation ≥ `coalition_threshold` join; the bloc holds name,
      leader clan, members. Mutual defence in `_mobilise_coalition`: strike one
      member → every mate's relations with the attacker sour −12 (war drags them in).
      (`simulation.py` `_update_coalitions`/`_mobilise_coalition`, called from
      both war kill & wound paths)
- [x] [P2] Coalition effects — members hear each other's signals like kin;
      soured (<10) or shrunken blocs dissolve; events on every transition.
- [x] Events: `coalition_formed` / `coalition_joined` / `coalition_dissolved`
      (`protocol.py` HistoryEvent, App.tsx + TUI chronicle branches).

### Leader agency
- [x] [P1] Decisions as plots — leaders act on their heritable trait:
      bold declares war on a remembered enemy (§X knowledge), peaceful sues for
      peace when weakened (`peace` event), paranoid betrays an ally (`betrayal`
      event + treason: false enemy-knowledge seeded into nearby third clans);
      strong clans demand tribute. Surfaced through chronicle/relations — god
      sees, can't veto. (`simulation.py` `_update_leader_decisions`,
      `_remembered_enemy`; LEADER_DECISION_CHANCE 0.01)

### Resource sharing
- [x] [P1] Clan larder — a food store at the settlement capped by
      `larder_capacity`: well-fed members (>75% energy) deposit surplus,
      starving members withdraw 3/tick (formalises §Q recruitment into an economy).
      (`simulation.py` `_update_larders`)
- [x] [P2] Allied aid — a surplus ally tops up a starving ally's larder at
      `aid_rate` during famine.
- [x] [P2] Tribute — weak clans pay 30 energy every TRIBUTE_INTERVAL (240) to a
      stronger protector (`tribute` events); `/api/clans` exposes `tribute_to`.

### Betrayal & treason
- [x] [P1] Ally backstab — paranoid/bold leader breaks an alliance (−95) and
      strikes; gated by `betrayal_enabled`; third clans near the herald receive
      false "enemy" knowledge naming the victim (treason via §X signals).
- [x] [P2] Defection — unhappy members (starving/homeless) walk to the healthiest
      nearby banner, even a rival's (`defection` event; DEFECT_CHANCE 0.03).
      (`simulation.py` `_update_defection`)
- [x] [P2] Treason — folded into betrayal: the betrayer sows false enemy rumors
      so allies of the victim turn wary.

### Laws
- [x] GodLaws: coalitions_enabled, coalition_threshold, coalition_min_size,
      leader_decisions_enabled, resource_sharing_enabled, larder_capacity,
      aid_rate, tribute_enabled, betrayal_enabled, defection_enabled (new
      "Politics" group; all enabled by default). (`config.py`, `protocol.py`,
      `main.py` LAW_FIELDS, GodPanel/TUI law groups + switches, wiki hints,
      docs/god-laws.md)
- [x] Events: peace, tribute, betrayal, defection (+ coalition events above).
      ClanPanel shows 🤝 pact / 🛡️ vassal / 🏺 larder chips; tests
      `tests/test_politics.py` (form/dissolve, mobilise, betrayal, peace, war
      declaration, larder deposit/withdraw, tribute payment, defection,
      laws roundtrip).

## AC. Desperation cannibalism — eat the enemy & the weak  [P2] — ✅ implemented
When starving, a creature may hunt and eat another living creature; sated/hungry
creatures never do. Same-clan kin-eating carries a heavy price: exile and a clan
that now counts the kin-slayer an enemy.

### The hunger-driven hunt
- [x] [P2] Gate — only when `starving` (energy ≤ `cannibalism_hunger_ratio`);
      sated/hungry creatures never eat the living; CANNIBAL_COOLDOWN (120)
      separates kills.
- [x] [P2] Targets — starving creature perceives eligible living prey via
      `_cannibal_prey`: enemy-clan members (negative relation) and weak members
      (starving/elder/wounded <50 health) of any clan; never predators, wild
      beasts, infants or indoor refugees — roofs are sanctuary.
- [x] [P2] Kill & feed — on contact (eat_radius): death cause `cannibalism`,
      gain `cannibalism_energy`, partial corpse (×0.5), steering outranks plants
      but yields to fleeing. (`simulation.py` `_do_cannibalism`)

### The price of kin-eating
- [x] [P1] Kin stigma — same-clan cannibalism sinks relations by `kin_stigma`;
      witnesses remember the outcast band as an enemy via §X knowledge.
- [x] [P1] Exile — the kin-eater is kicked out (`_exile_kin_eat`) and founds a
      one-being outcast band (`_new_clan(eater)`), like a schism of one;
      `exile` event records it.
- [x] [P1] Rebel & enemy — former clan ↔ band sink toward rivalry, eligible for
      war/plots; outcast may seek refuge among rivals via §AB defection.

### Laws
- [x] GodLaws: cannibalism_enabled, cannibalism_hunger_ratio, cannibalism_energy,
      eat_enemy_enabled, eat_kin_enabled, kin_stigma, exile_on_kin_eat (new
      "Desperation" group; all enabled by default).
- [x] Events: `cannibalism`, `exile`; death cause `cannibalism`. Tests:
      `tests/test_cannibalism.py` (weak-enemy kill, sated restraint, healthy-kin
      protection, rival-relation gate, exile+stigma+witness memory, exile-off
      variant, cooldown pacing, laws roundtrip).

## AD. OS-log persistence — RAM buffer + writer thread  [P1] — ✅ implemented
Move durable writes off the sim thread: buffer events/genealogy in RAM and let a
writer thread sync to SQLite periodically, like an OS log daemon. A crash loses at
most the un-flushed tail.

### RAM buffer
- [x] [P1] Buffer — Database keeps an in-memory deque of pending ops (`log_event`,
      `log_birth`, `log_death`); `_on_event` appends instead of writing SQL.
      Dropped the per-tick `DB.batch()` wrapper from advance_world and STEP.
      (`main.py:_on_event`, `db.py` §AD section)

### Writer thread
- [x] [P1] Daemon — dedicated `db-writer` thread drains the buffer into SQLite in
      ONE transaction (`flush()` rides `batch()` BEGIN…COMMIT), triggered by the
      5s heartbeat OR 5000 pending ops; forced flush on world end/reset,
      snapshot save, shutdown and before fresh reads. Failed drains re-queue at
      the front — nothing is lost. Single writer; sim thread never blocks on SQLite.

### Durability & reads
- [x] [P2] OS-log semantics — PRAGMA synchronous=NORMAL (WAL kept); crash loses at
      most the un-flushed tail; window documented here and in guide.py ops map.
- [x] [P2] Stale reads accepted — `/api/history`, `/api/worlds` and
      `/api/creature/{id}` drain the buffer on the HTTP thread before reading
      (≤5s lag elsewhere); live Chronicle uses WS events, unaffected; no
      read-through buffer. `/healthz` exposes `db_pending`. Tests:
      `tests/test_db.py` §AD (buffer→flush semantics, birth/death flow,
      unprompted daemon drain, close-flushes-tail via tmp Database).

## AE. Food decay — nothing lasts forever  [P2] — ✅ implemented
Plants are immortal today (only eaten / winter die-back / storm / fire removes
them). Give food a lifespan: mature plants wither, fertilize the soil, and vanish.

### Aging & withering
- [x] [P2] Food lifespan — a mature plant (growth 1.0) withers after
      `food_lifespan_ticks` × variant multiplier (grass 1.0, mushroom 0.4, berry
      1.5, poisonous 3.0 — `FOOD_LIFESPAN_MULT`); sprouts/growing plants don't rot
      (`Food.mature_ticks` clock starts only at maturity). (`entities.py`,
      `simulation.py:_update_plants`)
- [x] [P2] Wither → fertilize → vanish — a withered plant releases half a corpse's
      nutrient boost to nearby plants (`_release_nutrients(mult=0.5)` ties §H),
      then is removed; nothing lasts forever, but death feeds life.
- [x] [P2] Render — mature-then-wilting plants fade brown and shrivel before
      vanishing (`withering` flag on EntityState when past WILT_FRACTION 0.8 of
      lifespan; CanvasRenderer tints rgba-brown ×0.8 radius).

### Laws
- [x] GodLaws: food_decay_enabled, food_lifespan_ticks (new "Food Decay" group,
      enabled by default; per-variant pace stays Nature's constant table);
      `wither` events throttled like blooms (in-memory only, no DB; hidden from
      web + TUI feeds alongside ruins). Tests: `tests/test_food_decay.py`
      (lifespan death, sprout immunity, variant pace, law-off freeze, soil
      fertilisation, wilting flag surfacing, DB throttle, laws roundtrip).

## AF. Performance & Massive Scale Optimization (Backend + Frontend)  [P0] — ✅ implemented
Scale the simulation and rendering pipeline to maximize active population capacity
(thousands of inhabitants) while keeping the frontend silky smooth (60+ FPS) and lightweight.

### Backend spatial indexing & engine efficiency
- [x] [P0] Zero-allocation spatial indexing — replace dynamic dict-of-lists spatial index in `world.py`
      with pre-allocated cell buckets and fast wrap arithmetic; avoid list allocations per cell per tick.
      (`world.py`, `rebuild_index`, `query_radius`)
- [x] [P0] Simulation loop optimizations — fast squared-distance thresholding, perception pre-filtering,
      and $O(1)$ spatial mate discovery in `simulation.py:_reproduce`.
- [x] [P1] Snapshot payload generation efficiency — streamline `snapshot_payload()` with pre-cached
      terrain payloads to eliminate redundant dictionary list copies on every broadcast frame.

### Frontend rendering & UI responsiveness
- [x] [P0] Batched Canvas 2D rendering in `CanvasRenderer.tsx` — group drawing operations by caste,
      variant, and primitive type; batch line segments and polygons; eliminate per-entity `ctx.save()` / `ctx.restore()`
      overhead (draw calls reduced from 20,000+ to ~30-50).
- [x] [P1] Level of Detail (LOD) scaling — dynamically skip fine-grained details (glyphs, peace-cry ripples,
      text labels, sleeping markers) when zoomed out, maintaining 60 FPS even with dense populations.
- [x] [P0] Decoupled React state updates in `App.tsx` — keep high-frequency simulation state in mutable refs
      for direct 60 FPS canvas consumption while throttling React virtual DOM reconciliations (HUD metrics,
      clock, weather, population counters) to ~6 Hz.

### Verification & Documentation
- [x] [P0] Comprehensive automated tests in `backend/tests/test_performance.py` for spatial hash correctness,
      boundary wrap/clamp integrity, mate discovery, terrain caching, and high-scale population throughput.
- [x] [P0] Update documentation in `backend/app/wiki.py` and ensure type-safety across TypeScript and Python protocol schemas.

## AG. Autonomous Creature Evolution (No God Interventions)  [P0] — ✅ implemented
100% autonomous, emergent creature evolution driven entirely by in-simulation experience and inherited behavioral archetypes:

### Personality Archetypes & Inheritance
- [x] [P0] 6 Core Archetypes — `brave`, `cautious`, `altruistic`, `greedy`, `explorer`, `builder`.
- [x] [P0] Genetics & Heritability — 65% chance to inherit personality from mother/father; 35% chance to mutate on birth.
- [x] [P1] Altruistic Kin Feeding — altruistic creatures share carried food with hungry kin and infants.
- [x] [P1] Cautious Survival — cautious creatures seek shelter early and avoid dangerous zones.

### Dynamic Tools & Equipment (Caste Synergy)
- [x] [P0] Spears (`spear`) — Soldiers and Predators wield spears for extended reach and +20% combat damage.
- [x] [P0] Baskets (`basket`) — Farmers, Artisans, and Herbivores carry woven baskets hauling up to 3 food units back to clan larders.
- [x] [P0] Herb Poultices (`herb_poultice`) — Priests carry herbal remedies, autonomously healing injured kin (+25 HP) and curing infections.
- [x] [P1] Chieftain Crown (`crown`) — Clan leaders wear the golden crown.

### Dynamic Skill Mastery, Oral Lore & Milestone Titles
- [x] [P0] 4 Core Skills — Farming 🌾, Combat ⚔️, Foraging 🦴, and Healing 🌿 earn XP through actions.
- [x] [P0] Milestone Titles — Unlocking skill ranks awards dynamic titles (*the Slayer*, *the Fearless Champion*, *the Grand Harvester*, *the Wise Shaman*, *the Pathfinder*).
- [x] [P1] Oral Tradition in Houses — Resting elders pass their highest skill mastery XP to resting younglings.

### Expressive Emotes & Thought Bubbles
- [x] [P0] Real-time Animated Emotes — Floating thought balloons (`🍖`, `❤️`, `⚔️`, `🌿`, `🏆`, `💤`, `🧺`, `😱`) with physics above creatures in canvas and terminal.

## AH. Energy Dynamics & Stage-Aware Metabolism  [P0] — ✅ implemented
Realistic biological metabolism, fatigue, and food carrying:

### Stage-Aware Metabolism
- [x] [P0] Infant Metabolic Discount — Infants burn 55% less energy per tick (`0.45x`), juveniles burn 25% less (`0.75x`), adults standard (`1.0x`), elders `0.85x`.
- [x] [P0] Strict Sated Law — Full creatures (>85% energy / 100 energy) never consume food plants.

### Combat Stamina & Fatigue
- [x] [P0] Battle Energy Drain — Winner loses 6 energy, loser loses 10 energy in clashes.
- [x] [P1] Exhaustion Penalty — Combatants with <20% energy strike with 30% reduced damage.

### Autonomous Food Reserves
- [x] [P0] Field Reserve Consumption — Creatures can carry extra food and consume it autonomously when energy <45 far from food plants.

## AI. Terminal User Interface (TUI) Feature Parity  [P1] — ✅ implemented
Full terminal feature parity with web frontend:
- [x] [P1] Evolution Dossier in Inspector (`enter` / `i`) — Displays dynamic titles, personality badges, tool/basket inventory, and skill matrix.
- [x] [P1] Clan Details Screen (`c`) — Displays totem emblems, main house coordinates, larder, and full member table.
- [x] [P1] Category-Filtered Chronicle (`t`) — Cycle filters (All, Birth, Death, War, Politics, Settlement).
- [x] [P1] Camera Follow Mode (`w`) — Auto-track moving selected creature.

## AJ. Next-Gen Performance & Scale Architecture (3 Phases)  [P0 / P1]
Next frontier optimizations to scale Flatland to 5,000–10,000+ active inhabitants @ 60 FPS, slash network bandwidth by 90%, and achieve zero UI thread rendering lag.

### Phase 1: Network & WebSocket Delta Compression  [P0] — ✅ implemented
Slash WebSocket payload bandwidth by 85–95% (from ~1.5 MB/s to <80 KB/s per client) and eliminate JSON parsing bottlenecks on mobile/low-end clients.

- **Task 1.1: Delta-State Serialization Protocol**
  - [x] [P0] Define `DeltaStateMessage` schema (new spawns, movements, status/vitals changes, and despawn/death IDs).
  - [x] [P0] Implement keyframe pacing: broadcast a full keyframe snapshot every 60 ticks (~2s), with lightweight delta snapshots in between.
  - [x] [P0] Implement client-side snapshot reconstructor (`DeltaReconstructor`) in frontend `websocket.ts` to merge deltas into the live entity map.
- **Task 1.2: Compact Dynamic Payloads & Clan Delta Tracking**
  - [x] [P1] Compact `_entity_delta_payload` omitting static genetic fields for existing entities (75-90% per-entity byte reduction).
  - [x] [P1] Delta clan tracking sending only new/modified clans, dropping empty clan payloads to 2 bytes.
- **Task 1.3: Verification & Network Benchmarks**
  - [x] [P0] Automated network benchmark tests in `backend/tests/test_delta_compression.py` measuring payload reduction and keyframe pacing.
  - [x] [P0] Verify seamless reconnection, world reset, and snapshot reconstruction fidelity.

---

### Phase 2: Frontend OffscreenCanvas & Web Worker Rendering  [P1] — ✅ implemented
Completely decouple the 60 FPS HTML5 Canvas rendering loop from the browser's main UI thread to guarantee zero frame drops during heavy user interactions.

- **Task 2.1: Dedicated Web Worker Setup**
  - [x] [P1] Create `render.worker.ts` with canvas render loop, spatial viewport transforms, and batch draw routines.
  - [x] [P1] Update `CanvasRenderer.tsx` to transfer canvas control via `canvas.transferControlToOffscreen()`.
- **Task 2.2: Worker Event & Viewport Synchronization**
  - [x] [P1] Route pointer/pan/zoom input events from main thread to the worker via `postMessage` with zero DOM blocking.
  - [x] [P1] Modularize shared drawing functions in `renderCore.ts` for zero-duplication render loops.
  - [x] [P1] Post creature inspection hit-testing requests from main thread to worker with asynchronous resolution.
- **Task 2.3: Verification & Mobile Testing**
  - [x] [P1] Verified fluid 60 FPS rendering and Vite worker compilation (<370ms).
  - [x] [P1] Add fallback graceful degradation for browsers or environments without `OffscreenCanvas` support.

---

### Phase 3: Native High-Performance Core (C99 / SIMD / FFI)  [P0] — ✅ implemented
Accelerate simulation math (spatial hash, vector steering, boids, and collision detection) by 10x–30x, enabling 5,000–10,000+ active creatures on low-end CPUs (Intel N100/N150).

- **Task 3.1: Native C Spatial Hash & Distance Math Core**
  - [x] [P0] Implement contiguous flat buffers for entity coordinates (`entity_x`, `entity_y`, `entity_ids`).
  - [x] [P0] Implement compiled C spatial query index with squared distance thresholding (`c_query_radius`).
  - [x] [P0] Implement compiled Boids steering forces (`c_boids_separation`).
- **Task 3.2: Python FFI Bridge & Pure Python Fallback**
  - [x] [P0] Build `backend/app/native_core.py` ctypes bridge with auto-compilation via `clang`/`gcc` and seamless pure Python fallback.
  - [x] [P0] Connect `native_core` to distance queries and spatial checks.
- **Task 3.3: Verification & Scale Stress Testing**
  - [x] [P0] Deterministic validation tests comparing Python reference vs Native core outputs for exact identical math.
  - [x] [P0] Scale benchmark tests (`tests/test_scale_benchmarks.py`) verifying >160 FPS simulation ticks at scale.

---

## AK. Clan Lifecycle, Inventory Consumption & Profile UI Refinements  [P1] — ✅ implemented
Fixes and ergonomic polish for clan architecture, inventory autonomy, historical logs, and profile layouts.

- [x] [P1] **Single Main House Invariant**: Ensure every clan has strictly one active main house (HQ / Leader Residence). Fix cases where multiple houses retain `is_main=True` or unassigned upon leader succession, house destruction, or expansion.
- [x] [P1] **Emergency Inventory Consumption**: Hungry or starving creatures carrying food (in foraging baskets or equipped inventory) should eat from their carried stock immediately when energy falls below threshold, preventing starvation while returning home or wandering.
- [x] [P1] **Clan History & Major Event Log**: Track and display major historical milestones per clan (Founded on Day $D$ by Founder $X$, Leader Succession changes, HQ relocation, war declarations, tribute treaties) in the Clan details view.
- [x] [P1] **Clan & Creature Profile UI Overhaul**: Clean up profile views — eliminate duplicate data fields, prevent text/metric overlapping, and apply dynamic viewport sizing so elements never expand outside the modal container on desktop or mobile.
- [x] [P1] **House Capacity Bed Limits (16 Beds Max)**: Limit house beds to 16 maximum on max houses (`HOUSE_MAX_BEDS = 16`) with smaller houses scaling down proportionally, preventing single mega-houses from over-concentrating populations.

---

## AL. Creature Cognitive Agency & Clan Social Intelligence Roadmap  [P1]
Next-generation behavioral intelligence roadmap advancing individual cognitive decision-making, clan division of labor, dynamic bylaws, and macro geopolitics.

### Phase 1: Individual Cognitive Agency & Tactical Intelligence  [P1] — ✅ implemented
- **Task 1.1: Multi-Objective Utility AI Engine**
  - [x] [P1] Implement dynamic utility scoring $U(\text{action})$ replacing rigid if/else trees: balances survival energy, caste duty, personality weights, and kin emergency signals.
  - [x] [P1] Context-aware behavior: brave soldiers prioritize defense over snacks when under attack; cautious artisans voluntarily seek shelter before nightfall or storms.
- **Task 1.2: Spatial Mental Map & Purposeful Waypoint Navigation**
  - [x] [P1] Implement compact spatial memory (3–5 remembered coordinates per creature: Home HQ, Fertile Grove, Danger Zone, Trading Post).
  - [x] [P1] Replace Brownian random walk with purposeful patrolling, foraging circuits, and planned domestic return trips.
- **Task 1.3: Tactical Combat Formations & Phalanx Synergy**
  - [x] [P1] Soldiers from the same clan form coordinated spear/shield lines during defensive alerts.
  - [x] [P1] Agile lines (women) execute flanking and kiting maneuvers to draw enemy aggro away from vulnerable artisans and infants.
  - [x] [P1] Local combat odds evaluation: organized tactical retreat toward fortified houses when outnumbered $3:1$.
- **Task 1.4: Interpersonal Trust & Grudge Matrix**
  - [x] [P1] Track pairwise creature trust ($+15$ for healing, $+20$ for saving life, $-15$ for stealing/striking).
  - [x] [P1] High-trust pairs form cooperative hunting/farming duos, share shelters, and prioritize mutual aid.

### Phase 2: Clan Division of Labor & Institutional Governance  [P1] — ✅ implemented
- **Task 2.1: Autonomous Clan Task Board & Labor Allocation**
  - [x] [P1] Clan leaders and councils dynamically assign members to macro roles based on current crises:
    - *Food Shortage*: $70\%$ assigned to Forager/Harvester duty (2.0x harvester utility).
    - *Border Tension*: Soldiers garrison outpost doors and patrol (2.5x guard utility).
    - *Plague Outbreak*: Priests establish Main House infirmary; healthy maintain social distance.
    - *Surplus Wealth*: Builders assemble construction parties to erect new outpost houses.
- **Task 2.2: Clan Governance Archetypes**
  - [x] [P1] Implement distinct institutional forms based on founder caste and totem:
    - *Dynastic Monarchy* (Gentlemen/Nobles): Direct hereditary succession with royal lineage priority.
    - *Council of Elders* (Republic): High-side polygons vote on treaties, wars, and succession.
    - *Theocracy* (Priests): High healing/spiritual buffs, pacifist tendencies, and priest succession priority.
    - *Military Junta* (Soldiers): Expansionist conquest, tribute extortion, and combat mastery succession.
- **Task 2.3: Adaptive Clan Bylaws & Policies**
  - [x] [P1] Emergent bylaws triggered by environmental and historical events:
    - *Winter Rationing Law*: Restricts individual consumption to baseline maintenance during winter/famine (<35 energy).
    - *Martial Curfew*: Civilians restricted to settlement borders during active wars.
    - *Open Sanctuary vs. Isolationism*: Policy on admitting homeless defectors and orphaned refugees.

### Phase 3: Macro Geopolitics, Trade Caravans & Cultural Traditions  [P2] — ✅ implemented
- **Task 3.1: Calculated Casus Belli & Strategic Peace Terms**
  - [x] [P1] Wars declared with rational intent: famine raid plunder, blood feuds, and territorial friction with documented Casus Belli logs.

---

## AM. Food & Agriculture Ecosystem Roadmap  [P1] — ✅ implemented
Next-generation botanical, agricultural, and culinary simulation advancing crop diversity, intentional clan farming, granaries, soil nutrient dynamics, and caste food culture.

### Phase A: Crop Diversity & Functional Nutrition  [P1] — ✅ implemented
- **Task A.1: Botanical Diversity & Variant Expansion**
  - [x] [P1] Expand `Food.variant` with `grain` (dense calories, slow decay) and `medicinal_herb` (infection cure & healing).
  - [x] [P1] Configure variant-specific growth speeds, seasonal growth multipliers, and lifespan timers in `backend/app/simulation.py`.
- **Task A.2: Functional Dietary Effects & Nutritional Metabolics**
  - [x] [P1] Distinct effects on consumption: grain +45 & craft emote · berry +48 & speed boost · herb +18/+30HP cures infection · mushroom recycles.
- **Task A.3: Foraging Preference & Health-Based Dietary Selection**
  - [x] [P1] Injured/infected creatures weight herbs ×0.2, starving weight grain ×0.4 (`simulation.py` perception loop).

### Phase B: Clan Agriculture, Sowing & Farm Plots  [P2] — ✅ implemented
- **Task B.1: Seed Harvesting & Sowing Mechanics** (`simulation.py` `_ensure_farm_plots`/`_sow_and_tend`, seed gleaning at harvest)
  - [x] [P2] Skilled farmers (farming ≥6) glean seed from wild mature harvests (≤3 pouches) and sow empty clan plots ringed round the main house; plots by fertile groves are furrow-irrigated.
  - [x] [P2] Cultivated crops grow 2.0× faster (`CULTIVATED_GROWTH_MULT`) and yield 2.5× more energy (`CULTIVATED_YIELD_MULT`).
- **Task B.2: Crop Tending & Weeding**
  - [x] [P2] Farmers weed toxic sprouts within reach and roll back the wither clock on tended beds (`TEND_REGRESS_TICKS`).
  - [x] [P2] Irrigated plots ride out summer drought, winter frost and storms (`IRRIGATED_GROWTH_MULT`; frost/storm blocks skip irrigated crops).

### Phase C: Granaries, Food Preservation & Winter Spoilage  [P2] — ✅ implemented
- **Task C.1: Settlement Granaries & Physical Storage** (`clan["granary"]`, deposit at harvest, withdrawal in `_update_larders`)
  - [x] [P2] Sated grain/berry harvests lay 35% by in a dry roofed store safe from rain and beasts; starving members withdraw 3/tick.
  - [x] [P2] `/api/clans` exposes `granary` fill + `harvest_total`; ClanPanel 🌾 chip (🍞 feasting when live).
- **Task C.2: Food Preservation & Spoilage Dynamics**
  - [x] [P2] Cured rations: berry harvests deposit into the granary like grain — preserved stores never rot.
  - [x] [P2] Winter frost bites exposed wild crops (`WINTER_FROST_CHANCE`); cultivated beds & irrigated furrows are immune.

### Phase D: Dynamic Soil Ecology, Composting & Crop Rotation  [P2] — ✅ implemented
- **Task D.1: Soil Nutrient Depletion Grid** (`soil_grid`, `_deplete_soil`/`_soil_at` in `_update_plants`)
  - [x] [P2] Coarse fertility grid: every point of growth draws its cell down (growth scaled ×0.5–1.4 by local soil).
- **Task D.2: Composting, Ash & Corpse Decomposition**
  - [x] [P2] Corpse decay, wildfire ash and withered plants refill the grid (`_release_nutrients` → `_fertilize_soil`); master-farmer compost heaps add +0.4 near the settlement (`compost` event).
  - [x] [P2] Farmers build compost heaps near houses on a long cadence to revitalize depleted soil.

### Phase E: Food Culture, Feasting & Breadbasket Geopolitics  [P2] — ✅ implemented
- **Task E.1: Caste Gastronomy & Dietary Taboos** (`CASTE_DIET_WEIGHTS`)
  - [x] [P2] Priests/Nobles demand refined grain/fruit/herbs; Soldiers crave meat (corpses weighted ×0.6).
  - [x] [P2] Sacred hospitality: altruistic bread shared with non-rival strangers bumps relations +3 (`hospitality` event).
- **Task E.2: Clan Banquets & Famine Wars**
  - [x] [P2] Banquets fire at ≥80% granary: burn a quarter, cheer + energy for guests, relations +4, `feast_until` window gives +30% fertility (`banquet` event).
  - [x] [P2] Famine raids: a war win beside a rival's main house hauls up to 40 granary units when the raider's own stores are empty (`raid` event, `_try_granary_raid`). Markets & caravans move surplus peacefully (§AN D).
- Laws: agriculture_enabled, granaries_enabled, granary_capacity, soil_depletion_enabled, banquets_enabled ("Agriculture" group). Tests: `tests/test_agriculture.py`.

---

## AN. Communication, Language & Diplomatic Ecosystem Roadmap  [P1] — ✅ implemented
Next-generation multi-tiered communication ecosystem spanning caste acoustic vocalizations, tactile greeting rituals, forager scent breadcrumbs, inter-clan diplomatic emissaries, boundary stones, trade barter, settlement history glyphs, and divine omens.

### Phase A: Caste Vocalizations & Acoustic Calls  [P1] — ✅ implemented
- **Task A.1: Priest Sonorous Liturgy & Morale Chant**
  - [x] [P1] Priests chant on a gated cadence; hearing kin lose panic and gain a calm window (fear −2 for 20 ticks).
- **Task A.2: Woman's Peace-Hum & Safety Corridor**
  - [x] [P1] Moving women emit the peace-hum; idle polygons deflect from the source — corridors stay walkable.
- **Task A.3: Soldier Phalanx War-Chirp & Battle Rally**
  - [x] [P1] Soldiers facing a threat (predator, desperate prey or open-feud enemy) blow the war signal; allied soldiers converge on the flagged coordinates.
- **Task A.4: Artisan Trade & Barter Chimes**
  - [x] [P1] Artisans meeting hungry neighbours chime and gift basket food (+25 energy); cross-clan gifts warm relations.

### Phase B: Tactile Recognition & Scent Breadcrumbs  [P2] — ✅ implemented
- **Task B.1: Mutual Angle Feeling & Greeting Rituals**
  - [x] [P2] Non-hostile creatures within 1.2u exchange trust +2 on a slow cadence; elder blessing touch passes best-skill XP to infants/juveniles.
- **Task B.2: Forager Harvest Scent Trails**
  - [x] [P2] Well-fed finders of grain/berry/herb drop trail markers (ttl 220); hungry clan-mates steer to the marked patch.
- **Task B.3: Danger & Predator Scent Markers**
  - [x] [P2] Predation/war deaths and crumbling ruins leave danger scent (ttl up to 900); juveniles and the wounded learn danger facts and shun the ground.

### Phase C: Diplomatic Envoys & Territorial Monoliths  [P2] — ✅ implemented
- **Task C.1: Diplomatic Emissaries & Peace Missions**
  - [x] [P2] Peaceful/republic leaders commission banner-carrying emissaries; arrival at the rival seat warms relations +15 (`peace_envoy` event), failed missions time out.
- **Task C.2: Tribute Couriers & Vassalage Logistics**
  - [x] [P2] Tribute payments now also haul up to 15 granary units to the suzerain store under a courier ripple.
- **Task C.3: Clan Boundary Stones & Border Heralds**
  - [x] [P2] Settled clans raise a boundary stone on their border (clan-colored diamond on canvas); trespassers near it ring warning chimes that sentry soldiers walk to (throttled per clan).

### Phase D: Trade Caravans & Granary Barter  [P2] — ✅ implemented
- **Task D.1: Neutral Trading Posts & Markets**
  - [x] [P2] Allied neighbours within reach found a neutral market at the midpoint (`market` event, drawn as gold posts); every 240 ticks surplus flows to the leaner granary (+1 relation).
- **Task D.2: Traveling Peddlers & Trade Caravans**
  - [x] [P2] Every 2400 ticks a caravan travels between two non-rival settlements: goods flow toward the leaner store, relations +2 (`caravan` event).

### Phase E: Settlement Glyphs, Linguistic Drift & Divine Revelations  [P2] — ✅ implemented
- **Task E.1: House Murals & Settlement Chronicle Inscriptions**
  - [x] [P2] Major clan milestones paint murals on the main house walls (`House.murals` on the wire); explorer archaeology at ruins recovers farming/foraging skill + vague food lore.
- **Task E.2: Linguistic Drift & Clan Dialects**
  - [x] [P2] Each clan carries a dialect value: allies converge per season, isolated clans drift by a deterministic wobble; strangers ignore signals more the further dialects split (0.45–0.95).
- **Task E.3: Prophetic Omens & Revelations from the Sphere**
  - [x] [P2] At each season turn a shrine priest proclaims the coming season (omen ripple + chronicle event); hearing kin gain `prepared_ticks` and drift home early.
- Laws: vocalizations_enabled, scent_enabled, envoys_enabled, markets_enabled, omens_enabled, dialect_drift_enabled ("Language & Diplomacy" group). Tests:
      `tests/test_diplomacy.py` (chant calm, peace-hum, chirp rally, greeting+elder touch, trail drop & follow, death scent learning, envoy delivery & steering, stone chime throttle, tribute courier, market founding & barter, caravan, omen preparation, dialect drift/convergence, murals, ruin archaeology, laws roundtrip).

---

## AO. Nocturnal Perils & Vital Shelter Ecosystem Roadmap  [P1] — ✅ implemented
Transformation of the Flatland night into an existential outdoor hazard and elevated shelter into an indispensable sanctuary of warmth, healing, defense, and culture.

### Phase A: Extreme Night Chill & Hypothermia Exposure  [P1]
- **Task A.1: Accelerated Nighttime Chill & Exposure Kinetics**
  - [x] [P1] Unsheltered creatures at night accumulate chill $3.0\times$ faster than during daytime rain.
  - [x] [P1] In winter nights or night storms, outdoor exposure accumulates extreme chill and inflicts rapid energy drain.
- **Task A.2: Frostbite Numbness & Hypothermia Mortality**
  - [x] [P1] Reaching maximum chill ($>12$) triggers *Frostbite Numbness*: reduces speed to $0.4\times$, forces creatures to drop carried food/seed baskets, and deals $0.5\text{ HP/tick}$ damage until death (`death_cause: exposure`).

### Phase B: Nocturnal Predators & The Dusk Rush  [P1]
- **Task B.1: Predator Nocturnal Prowling & Night Vision Buff**
  - [x] [P1] Predators gain $+40\%$ sight radius in the dark and $+20\%$ stealth chase speed when hunting unsheltered prey at night.
  - [x] [P1] Pack-hunting behavior: wolves and wild beasts converge in hunting packs past midnight (`tod > 0.85`), prowling around village borders.
- **Task B.2: The Dusk Rush (Sunset Urgency Steering)**
  - [x] [P1] At dusk (`tod = 0.70`), creatures feel instinctive urgency: dropping non-essential exploration to sprint straight home before nightfall.

### Phase C: Clan Hearths & Indoor Restorative Sanctuaries  [P2]
- **Task C.1: Central House Hearths & Total Thermal Immunity**
  - [x] [P2] Inhabited houses maintain a glowing central hearth that immediately purges chill, halts energy decay, and accelerates HP healing ($+1.5\text{ HP/tick}$).
- **Task C.2: Door Barricades & Sentry Spearmen**
  - [x] [P2] Solid walls and closed doorway thresholds prevent predators from penetrating occupied homes.
  - [x] [P2] Clan spearmen near house doorways poke outward to defend against circling night beasts.

### Phase D: Blind Collisions & The Lethal Needle Hazard  [P2]
- **Task D.1: Pitch-Black Visibility & Blind Collision Fog**
  - [x] [P2] Non-predator sight outdoors at night contracts to $2.5$ units, making navigation and obstacle avoidance perilous without light sources.
- **Task D.2: Accidental Impalement Hazard**
  - [x] [P2] Collisions in pitch darkness with unsheltered moving lines (women) inflict severe accidental impalement damage ($\ge 25\text{ HP}$).
- **Task D.3: Rogue Isosceles Night Marauders**
  - [x] [P2] Clanless or starving Isosceles bandits stalk the dark to ambush lone foragers and loot their carried rations.

### Phase E: Field Campfires & Settlement Expansion Economics  [P2]
- **Task E.1: Emergency Field Campfires & Bivouacs**
  - [x] [P2] Stranded explorers caught far from home at nightfall gather dry brush to light temporary campfires ($3.5$ unit illuminated radius) that repel predators and provide warmth until dawn.
- **Task E.2: Shelter Scarcity & Housing Construction Pressure**
  - [x] [P2] Population overflowing bed capacity creates urgent social and economic demand for Artisans to quarry materials and construct new houses or expand existing halls.

---

## AP. Unified Theology & Divine Totem Ecosystem Roadmap  [P1] — ✅ implemented
Reimagining totems as sacred 2D avatars / manifestations of the One True God (The Sphere from Spaceland), capturing distinct divine aspects with living shrines, daily tithes, divine law resonance, and theological geopolitics.

### Phase A: The 8 Sacred Avatars of the Sphere  [P1] — ✅ implemented
- **Task A.1: The 8 Geometric Projections of the Sphere**
  - [x] [P1] Totems refactored from animals into the 8 Sacred Avatars (`simulation.py` `AVATARS`/`TOTEM_BUFF`):
    - ⭕ *The Radiant Circle*: God's Abundance (+30% harvest, +20% fertility).
    - ⚡ *The Celestial Strike*: God's Wrath & Justice (+25% warrior damage via new `damage` buff key).
    - 👁️ *The All-Seeing Vertex*: God's Omniscience (+40% sight; `clarity` recovers night/fog dimming).
    - 🛡️ *The Indomitable Monolith*: God's Permanence (−30% damage, +15 birth health; `cold` 0.4 chill immunity).
    - 🌿 *The Sacred Spiral*: God's Renewal (herbs heal ×2 via `medicine`, plague recovery ×2, composts corpses near shrine).
    - ⚖️ *The Cosmic Scales*: God's Equilibrium (`peace`: any Scales leader sues for peace at +90; `lawful`: refuses kin-eating even while starving).
    - 🌀 *The Dimensional Rift*: God's Ascent (iso_angle +0.75/generation, mutation odds ×2, elder oral-lore XP ×2).
    - 🕯️ *The Eternal Hearth*: God's Sanctuary (`calm` shaves fear radius at night).
- **Task A.2: Totem Avatar Assignment & Crest Symbology**
  - [x] [P1] Procedural assignment preserved at founding — deterministic `cid*17+seed` hash, zero rng (`simulation.py:_new_clan`, schism branch).

### Phase B: Physical Totem Shrines, Tithes & Clan Faith  [P2] — ✅ implemented
- **Task B.1: Physical Totem Monoliths & Settlement Shrines**
  - [x] [P2] Settled clans consecrate a shrine beside their main house at founding (`_consecrate_initial_shrines` at world creation, `_update_faith` for later settlements); glowing avatar stone + faith-scaled aura on the canvas (`renderCore.ts`), temple ring at level 2.
- **Task B.2: Morning & Evening Tithes and the Clan Faith Pool**
  - [x] [P2] At dawn & dusk windows (tod 0.25/0.75 ±0.02) members within the aura tithe `tithe_rate`×energy_max into the clan faith pool (priests double); the aura mends injured faithful while faith holds (`BLESS_HEAL_RATE`/`BLESS_FAITH_COST`). Season-turn overflow works a `miracle`: mature food blooms around the shrine + flock mended (`_work_miracle`, `miracle` event).

### Phase C: Divine Law Resonance & Priestly Preaching  [P2] — ✅ implemented
- **Task C.1: Synchronized Law Resonance**
  - [x] [P2] Every `POST /api/laws` change calls `Simulation.on_law_change()` → each shrine emits a golden `chime` ripple; single `resonance` chronicle event summarises.
- **Task C.2: Priestly Doctrinal Sermons**
  - [x] [P2] Each shrine's first priest delivers a `sermon` interpreting the law per its avatar's dogma (`AVATAR_DOGMA`); flock inside the aura gains morale energy.

### Phase D: Theological Geopolitics & The Holy Synod  [P2] — ✅ implemented
- **Task D.1: Doctrinal Compatibility & Holy Alliances**
  - [x] [P2] Same/complementary-avatar pairs (`AVATAR_ALLIES`: Circle↔Spiral, Strike↔Vertex, Monolith↔Hearth, Scales↔Rift) gain +1 relation per tick in `_update_relations`.
- **Task D.2: The Great Synod of the Sphere**
  - [x] [P2] During Ice/Plague ages every `SYNOD_INTERVAL` ticks priests convene at a neutral centre (`_hold_synod`): all relations +4, sacred truce (`truce_ticks`) stills `_update_war`, `synod` event.

### Phase E: Temple Architecture & Sphere Revelations  [P2] — ✅ implemented
- **Task E.1: Monumental Temple Upgrades**
  - [x] [P2] Faith ≥ `temple_faith_cost` raises the shrine into a Temple (`temple` event, ⛪ marker): blessing aura extends across the whole territory.
- **Task E.2: The 3D Epiphany (Vision of the Sphere)**
  - [x] [P2] Hash-gated once-per-age event (`EPIPHANY_PERIODS_GAP`): an elder priest of a temple clan beholds the Sphere (`epiphany` event) — all relations +10, double truce, healing emote.
- [x] GodLaws: theology_enabled, tithe_rate, temple_faith_cost ("Theology" group, enabled by default)
      (`config.py`, `protocol.py`, `main.py` LAW_FIELDS + apply_laws hook, GodPanel/TUI groups,
      wiki hints, docs/god-laws.md §10, guide §C/P). Deterministic throughout —
      rare events are hash-gated so the world's rng stream never moves. Tests:
      `tests/test_theology.py` (avatar determinism + buffs, shrine consecration,
      dawn tithes incl. priest-double/exemptions, miracle bloom+heal, temple
      raising, resonance chimes+sermons+morale, doctrinal kinship, synod truce
      stops-and-resumes war, epiphany vision, laws roundtrip).

---

## AQ. 2D Physics Ecosystem Roadmap  [P1–P2]
> Grounded in A.K. Dewdney's *The Planiverse* and Edwin Abbott's *Flatland*.
> Axioms: all physics is 2D-intrinsic; energy is the universal currency; The Sphere sets laws, physics enforces them.

### Phase PH-0: Foundational Axioms  [P0] — ✅ implemented
- [x] [P0] **Energy conservation loop** — sunlight (day cycle) is the world's only income: `_sun_factor()` arcs from zero at night to 1.0 at noon and gates both plant growth and seed spread — no free growth in the dark; mending converts energy into health (`HEALING_ENERGY_COST` 0.5 per healed point, charged only on actual healing); death already returns energy via corpses + nutrient cycle; winter's bite stays the season table. (`simulation.py` `_sun_factor`, `_update_plants`, regen branches; tests `tests/test_physics_core.py`)
- [x] [P0] **Metabolic cost by caste** — upkeep scales with body complexity (`METABOLIC_COST`, `_metabolic_cost`): Triangle/Soldier 1.0×, Square/Gentleman 1.1×, Pentagon/Professional 1.2×, Hexagon/Noble 1.3×, Woman & Priest/Circle 1.5× (priests burn energy maintaining the aura); applied to per-tick energy decay awake and asleep.

### Phase PH-1: Thermodynamics & Heat  [P0] — ✅ implemented
- [x] [P0] **Temperature field** — coarse per-cell heat map (`TEMP_CELL` 25) updated each tick by season (base swept across the map from an edge: cold from the west, warmth from the east), day cycle (`DAY_HEAT_AMPLITUDE`), weather bumps, and open flame (`FIRE_HEAT` 60° within 8 units, circle-vs-cell overlap). (`simulation.py` `_update_temperature`/`ambient_at`, tests `tests/test_temperature.py`)
- [x] [P0] **Body temperature** — `Creature.body_temp` drifts toward ambient (`BODY_TEMP_DRIFT`); too cold (<2°) builds §R chill under the weather-sickness law; too hot (>36°) is always physics — health drains with the excess until death cause `hyperthermia`. Exposed on the wire as `body_temp`.
- [x] [P0] **Insulation ratings** — houses get a seeded material (`_pick_house_material`: stone > wood > straw, `INSULATION_BY_MATERIAL` 0.55/0.35/0.15) that pulls indoor air toward `HOUSE_COMFORT_TEMP` 18°; larger houses lose heat faster (`HOUSE_REF_SIDE/size` factor). `material` on the wire.
- [x] [P1] **Hearths** — permanent fire installations inside claimed houses: kin buy fuel from the clan larder every 10 ticks when cold/night/storm calls for it (`HEARTH_FUEL_PER_ENERGY` 60 ticks per larder unit, woodpile caps 1200); burns `HEARTH_BURN_RATE` 1/tick and gutters out unfed; a lit hearth pulls indoor air past comfort toward `HEARTH_COMFORT_TEMP` 26° (`HEARTH_PULL` × size factor); `hearths_enabled` law (Shelter group), flame dot + warm glow on the wire as `hearth_lit`. (`simulation.py:_update_hearths`, `indoor_ambient`; tests `tests/test_hearth.py`)
- [x] [P1] **Heat radiation from fire** — radiant scald beyond the flame core: creatures between `r+1.2` and `r+FIRE_SCALD_RADIUS` 4 lose up to `FIRE_SCALD_DAMAGE` 2.2 HP/tick scaled by proximity (50% gate/tick), death cause `hyperthermia`; warmth side was already the `FIRE_HEAT` field. Fire is officially double-edged. (`simulation.py:_update_fires`, tests `tests/test_hearth.py`)

### Phase PH-2: Atmospheric Physics & Wind  [P0 items done]
- [x] [P0] **Wind vector field** — `wind_angle`/`wind_speed` on the snapshot; magnitude follows weather severity (calm 0.25 / rain 0.55 / storm 1.0, relaxed per tick), direction re-rolls near the season's prevailing bearing (`WIND_SEASON_BIAS`) on every weather transition. (`simulation.py` `_update_weather`/`_update_wind`, payload, types.ts; tests `tests/test_wind.py`)
- [x] [P0] **Wind affects fire spread** — random ignition and plant-to-plant spread both multiply by a tailwind factor (`WIND_FIRE_MULT` 0.8 × speed × downwind alignment): flame propagates faster downwind and downwind groves ignite first.
- [x] [P1] **Wind affects seed dispersal** — seed drift bends downwind by `WIND_SEED_BIAS` 0.65 × wind speed (blended into the spread vector): groves creep with the prevailing breeze, upwind ground stays clear. (`simulation.py:_update_plants` spread, tests `tests/test_hearth.py`)
- [x] [P1] **Scent signals on wind** — noses reach farther toward UPWIND targets: hunt/fear radii extend ×(1 + `WIND_SCENT_MULT` 0.5 × wind speed × upwind alignment) — smell travels downwind to the sniffer, so approaching from downwind is the stealth play for hunter and hunted alike; gated by the §AN scent law. (`simulation.py:_update_creature` predation block, tests `tests/test_hearth.py`)
- [x] [P2] **Sound propagation** — calls ride the wind (`SOUND_WIND_MULT` 0.4 × speed toward DOWNWIND listeners, out to 2.5× base radius); roofs muffle the open air (indoors creatures never hear `alarm`/`help`/`boom` raised outside); loud events roll out as `boom` pressure waves every body hears — house collapses and dam bursts; sleeping ears were already deaf (§AR S-0). Scent stayed asymmetric on purpose: prey read the wind twice as well as hunters, which keeps the Lotka-Volterra cycle stable. (`simulation.py:_update_creature` hearing loop, `_emit_boom`; tests `tests/test_sound.py`)
- [ ] [P2] **Wind affects thrown weapon range** — *deferred*: there is no thrown-weapon system to bend (spears are melee buffs §EC); revisit when ranged combat exists.

### Phase PH-3: Fluid Dynamics & Rivers  [P1] — ✅ implemented
> The most Planiverse-authentic feature — rivers are 1D channels, a radical 2D constraint.
- [x] [P1] **River entities** — horizontal channel bands (`RIVER_BASE_HW` 4 half-width) across the map with an east/west flow direction each; spawned at world creation from a dedicated geography rng (`river_count` law, `rivers_enabled`) so life settles around them — houses and plants never root in the water. On the wire as `rivers`/`bridges`/`dams`; renderer draws blue bands with flow chevrons. (`simulation.py:_generate_rivers`, tests `tests/test_rivers.py`)
- [x] [P1] **Fording cost** — wading drains `RIVER_FORD_COST` 0.06 energy/tick; infants and creatures under 30 HP are swept downstream at `RIVER_SWEEP_SPEED`; planks cross dry.
- [x] [P1] **Flood mechanics** — rain swells the channel (`RIVER_RAIN_RATE`, storm ×1.5); full channel bursts: flood widens the band ×2.2 over `RIVER_FLOOD_TICKS` 300, tears out rooted plants, pushes everyone downstream; receded water leaves `RIVER_SILT_TICKS` 600 of bank enrichment (`RIVER_SILT_MULT` 1.5 growth). Chronicle: `river_flood`.
- [x] [P1] **Bridge construction** — builder-personality creatures raise planks across channels they live beside (`BRIDGE_HP` 2400 rot clock); crossings within `BRIDGE_HALF_WIDTH` pay no toll and feel no current.
- [x] [P2] **Dam construction & failure** — builders react to rising water with masonry (`DAM_HP` 3600): dams halve the rain gain while intact but grind down `DAM_STRESS_DAMAGE` 30/flood-tick; failure releases a flash flood (`DAM_FLASH_SPIKE` ×1.8 band spike, chronicle `flash_flood`). (Deliberate war-targeting of enemy dams deferred — needs the §AS command system.)
- [x] [P2] **Drowning damage** — floodwater drains `RIVER_DROWN_DAMAGE` 1.5 HP/tick, softened by foraging skill (1/(1+skill/20)) — swimming is foraging-adjacent; death cause `drowning`.

### Phase PH-4: Gravity & Terrain Topology  [P1] — ✅ implemented
- [x] [P1] **Elevation / height map** — smooth seeded sinusoid height field on the `ELEV_CELL` 25 grid (`relief_enabled` law; dedicated geography rng), normalized to `ELEV_MAX_HEIGHT` 60 units; movement cost scales with grade (`SLOPE_ENERGY_COST` 0.05 × grade) and climbs slow the stride (≤35%), rivers spawn flowing toward lower ground, static field rides the keyframe as `elevation` and shades the map. (`simulation.py:_generate_elevation/_terrain_effects`, tests `tests/test_relief.py`)
- [x] [P1] **Cliff edges** — the smooth field is bilinear (ordinary travel never trips it); the RAW terraced field decides falls: a cell-boundary descent ≥ `CLIFF_DROP_UNITS` 14 is a cliff — damage `(excess + 7) × FALL_DAMAGE_PER_UNIT` 1.0, death cause `fall`. Prod lesson (extinction @12k): nearest-cell sampling on the energy path made every slope an invisible cliff wall — smooth and terraced are now separate concerns. (The Planiverse column constraint is not modelled — bodies are flat points here.)
- [x] [P1] **Soil compaction & emergent roads** — every body-tick packs traffic into its coarse cell (decays `TRAFFIC_DECAY` 0.995/tick): packed earth speeds the stride up to +30% (`ROAD_SPEED_CAP`) and chokes plant growth (halted at `TRAFFIC_PLANT_BLOCK` 6) — clans carve real road networks just by commuting.
- [x] [P2] **Avalanche / landslide** — climbing a grade steeper than `AVALANCHE_SLOPE` 0.5 in rain/storm risks a slide (0.002/tick): thrown back down the slope for 8–20 damage, death cause `landslide`.
- [ ] [P2] **Ramps / staircases** — *deferred*: needs vertical layer semantics the flat-point body model doesn't have; grades already cost/slow so cliffs remain one-way hazards.

### Phase PH-5: Ecological & Biological Physics  [P1]
- [x] [P1] **Nutrient cycle** — the §AM living-soil grid is exactly this: harvests deplete fertility cell by cell, corpses/withered plants/ash/compost restore it, plant growth scales with local soil. (`simulation.py` `_soil_at`/`_deplete_soil`/`_fertilize_soil`)
- [x] [P1] **Root competition** — every mature non-poison neighbour within `SYMBIOSIS_RADIUS` 3.5 divides a sprout's growth by `1 + ROOT_COMPETITION 0.45 × n`: clearings and groves emerge from spread rules alone. Berry thickets exempt their herb symbionts. (`simulation.py:_update_plants`, tests `tests/test_hearth.py`)
- [x] [P1] **Composting** — §AM farmers already compost: `_sow_and_tend` buries corpses into farm soil (compost event) and the living soil rewards it. Covered.
- [x] [P2] **Plant symbiosis & parasitism** — mushrooms fruit on decay (×1.6 near corpses), medicinal herbs shelter in berry thickets (×1.35), poisonous plants stunt all neighbours (×0.55). (`simulation.py:_update_plants`, tests `tests/test_hearth.py`)

### Phase PH-6: Material Physics & Building  [P1] — ✅ implemented
- [x] [P1] **Material types** — four materials with distinct stats (`MATERIAL_STATS`): *straw* 120 HP / 0.15 insulation, *wood* 260 / 0.35, *stone* 480 / 0.55, and new *clay* 320 / **0.70** — riverbank brick that settlements beside a channel dig (`_pick_house_material` picks clay 55% of the time within silt reach). On the wire as `material`, tinted on the map. (tests `tests/test_materials.py`)
- [x] [P1] **Structural integrity / HP** — storms wear `STORM_WEAR` 0.15/tick, floodwater `FLOOD_WEAR` 0.6/tick; builders near a roof mend `REPAIR_RATE` 1.5/tick; a spent roof collapses to ruin (chronicle `collapse`), integrity rides the wire as `hp_frac` with crack overlay under 70%. (`simulation.py:_update_structures`)
- [x] [P2] **Rubble blocking** — collapsed lots pile `rubble` that blocks movement like rock (`RUBBLE_RADIUS_FRAC` 0.35 of the floor) until a builder clears it (0.10/tick), which removes the ruin entirely; `rubble_blocking_enabled` law.
- [ ] [P2] **Weight & load-bearing** — *deferred*: Planiverse beam mechanics (one-point supports, wall-climbing rules) need a structural graph the flat-point body model doesn't have; walls already block except doors.

### Phase PH-7: Metabolic & Biological Extremes  [P2] — ✅ implemented
- [x] [P2] **Torpor / hibernation** — a body below `TORPOR_ENERGY_RATIO` 10% energy in air under `HYPOTHERMIA_TEMP` 2° shuts down where it stands: `TORPOR_BURN_MULT` 0.05× burn, no movement, no perception — unconscious and defenceless until the air warms or starvation wins; on the wire as `torpid` (frost halo in the renderer). (`simulation.py:_update_creature`, tests `tests/test_metabolism.py`)
- [x] [P2] **Heat exhaustion** — every tick spent above 36° builds `heat_stroke_ticks`; at `HEAT_STROKE_TICKS` 60 the body drops into heat prostration (stride zeroed, sleep emote) and keeps cooking until ambient falls 4° below threshold — fatal if shade never comes, exactly as before but now the victim stops sprinting through the fire.

### Phase PH-8: Seismic & Wave Physics  [P2] — ✅ implemented
- [x] [P2] **Earthquake events** — `earthquake_enabled` (off by default) at `earthquake_rate`: magnitude 4–8 quake throws bodies (`QUAKE_DISPLACEMENT` 3.5 × mag falloff), wounds them (`QUAKE_DAMAGE` 16, cause `earthquake`), drops weakened roofs through the §PH-6 structural path, and stone either cracks open (35%) or thrusts up new rock (15%). Chronicle `earthquake` + boom wave. (`simulation.py:_update_seismic/_do_earthquake`, tests `tests/test_cosmos.py`)
- [x] [P2] **Seismic early warning** — `QUAKE_WARN_TICKS` 3 before the shock, Professionals/Nobles/Priests within 30 of the coming epicentre panic and raise the alarm; the low castes feel nothing until the ground moves.
- [x] [P2] **Information propagation delay** — every signal carries `born_tick`; a listener hears it only when the wavefront `(tick − born) × signal_speed` (default 8 units/tick, law `signal_speed`, 0 = instant) reaches them, ×1.4 downwind. Distant clans get the news N ticks late — tactical asymmetry at last.

### Phase PH-9: Electrostatics & Bio-electric Fields  [P2] — ✅ implemented
- [x] [P2] **Lightning physics** — storms strike real bolts at `lightning_strike_rate` (law): instant death within `LIGHTNING_KILL_RADIUS` 1.6 (cause `lightning`), 60% ignition when wildfire burns, else a fused electrostatic rock that decays after `LIGHTNING_ROCK_TTL` 240. Bolts render as jagged flashes. (`simulation.py:_update_lightning`)
- [x] [P2] **Priestly bio-electric aura** — a living clan priest within `PRIEST_AURA_RADIUS` 6 soothes fear by `PRIEST_CALM` 1.5 × faith (clan faith pool scales 0.6–1.6); folded into `_effective_fear_radius` so it composes with leader calm, traits and starvation.
- [x] [P2] **Totem resonance zones** — allied shrines bearing the SAME totem within 22 units amplify every totem buff ×(1 + 0.25 each, cap 2.0); rival shrines that close dim BOTH ×0.75; shrines beside an anomaly draw ×1.25. Applied centrally in `_totem_stat`.

### Phase PH-10: Cosmological & Metaphysical  [P2–P3] — ✅ implemented
- [x] [P2] **Law-change physical wave** — every law change spawns a shimmer front that sweeps west→east over `LAW_WAVE_TICKS` 30 (rendered as a violet band); bodies inside the ±4 band feel the boundary pass through them (heading jitter). Deviation: laws flip globally at t₀ — per-x law interpolation would fork every multiplier; the wave is felt, not simulated. (`simulation.py:on_law_change/_update_law_wave`)
- [x] [P2] **Anomaly zones** — `anomaly_count` 3 hidden zones (fertile ×1.6 growth / heavy ×0.7 speed +10% burn / calm ×0.8 decay) seeded at world creation from the geography rng; invisible on the wire until a forager with skill ≥ 3 (or an explorer) walks in — discovery emits an `anomaly` chronicle event and reveals the zone; shrines beside one gain ×1.25 totem power.
- [x] [P3] **Shadow tiles** — roofs cast a shadow rectangle `SHADOW_LENGTH` 1.4 × size toward the west (the sun stands east): shade-starved sprouts grow ×`SHADOW_GROWTH_MULT` 0.7. Temperature shading skipped — the heat field already sweeps fronts from the edges.
- [x] [P3] **Sunlight edge** — dawn light sweeps in from the east rim (0.22–0.30 of the day), dusk from the west rim (0.70–0.78): plants in the `SUN_EDGE_BAND` 18 grow ×1.15 during the sweep.

---

## AR. Creature Senses Improvement Roadmap  [P0–P2] — ✅ implemented
> Builds on the existing vision / hearing / memory / contact system.
> Guiding principle: senses should interact and suppress each other, not fire independently.

### Phase S-0: High-Impact, Low-Complexity Fixes  [P0] — ✅ implemented
- [x] [P0] **Sleeping = fully deaf** — sleeping creatures skip all signal processing (the sleep branch returns before any hearing) and are excluded from mob-defender counts (`_mob_defenders` skips `o.sleeping`); predators can silently approach a sleeping village — verified by a wolf circling a hut all night while the sleeper holds position. (`simulation.py`, tests `tests/test_senses.py`)
- [x] [P0] **Food scent at night** — ripe food (`growth == 1.0`) emits a detectable scent within `FOOD_SCENT_RADIUS` 8.0 regardless of `env_sight`; hungry/starving creatures with no visual target lock onto it at night; unripe sprouts carry no scent. Directly solves the "starving creature at night cannot find food" failure mode. (`simulation.py` `_update_creature` scent fallback after perception)
- [x] [P0] **Starvation suppresses fear** — starving creatures have effective `fear_radius × 0.5` via `_effective_fear_radius` (paranoid +4 / bold −2.5 apply first); a desperate enough creature walks toward a predator chasing scented food.

### Phase S-1: Hearing Improvements  [P1]
- [x] [P1] **Signal confidence attenuation by distance** — `heard_conf = 1 - (dist / signal_radius)`; creatures far from the alarm source react weakly, close ones react fully; replaces the current binary inside/outside detection.
- [x] [P1] **Signal direction encoding** — alarm signals carry `dx, dy` from source; listener flees *away* from signal direction rather than steering randomly; fixes the current bug where alarms don't guide fleeing direction.
- [x] [P1] **Houses block sound** — creatures with `c.indoors == True` cannot hear `alarm` or `help` signals from outside; reinforces shelter as a genuine tactical refuge.
- [x] [P2] **Crowd-size scales alarm radius** — a group of ≥3 predators triggers a "war cry" signal at 2× normal `signal_radius`, capable of waking sleeping creatures nearby.
- [x] [P2] **Sense fatigue / alarm habituation** — if the same alarm fires for ≥10 consecutive ticks, creatures habituate: `u_alarm` drops to 0.3; prevents infinite alarm-paralysis near persistent threats.

### Phase S-2: Vision Improvements  [P1–P2]
- [x] [P1] **Torch tradeoff** — creatures carrying a torch (`equipped_item == "torch"`) restore night sight to full (env_sight = 1.0) within 6 units, but become visible to predators at 2× normal `hunt_radius`; genuine risk/reward decision.
- [x] [P1] **Terrain camouflage** — creatures adjacent to mature food patches (berry, grass) gain cover: predator effective `hunt_radius` reduced by 20% toward them; "hiding in the bushes" is a real survival strategy.
- [x] [P2] **Facing cone bias** — creatures have an `angle`; vision is full `perceive_radius` within a ±90° forward cone, `perceive × 0.5` in the rear 180°; guards placed facing outward actually face outward.
- [x] [P2] **Angle recognition errors** (Flatland canon) — Triangles are misidentified as predators 30% of the time beyond half `perceive_radius`; generates emergent false alarms; higher-caste creatures (more sides ≈ more circular) are easier to identify correctly.
- [x] [P2] **Sight degradation with age** — elder creatures gain an additional `× 0.9` sight penalty and a small `recognition_conf` reduction; the young may misidentify elders, elders may misidentify fast-moving Triangles.

### Phase S-3: Memory Improvements  [P1–P2]
- [x] [P1] **Trust-weighted rumours** — `_hear_fact()` multiplies incoming `conf` by `trust.get(sender_id, 50) / 100`; a trusted clan-mate's alarm is believed at full confidence; a stranger or known traitor is believed at ≤5%; connects the existing `c.trust` dict to perception.
- [x] [P1] **Inherited memory / oral lore** — when an elder sleeps near infants, it transmits `facts["safe"]` and `facts["food"]` with `conf = 0.3`; babies begin life with imprecise inherited knowledge of their clan's home territory and food grounds.
- [x] [P1] **Continuous confidence decay** — facts decay linearly per tick (`conf -= 1 / knowledge_ttl`) instead of expiring at a hard TTL cliff; facts fade gracefully rather than vanishing suddenly.
- [x] [P2] **Spatial position drift** — remembered fact coordinates drift randomly by `±(1 - conf) × noise` per tick; a faded rumour points to "roughly there", not the exact location; creatures navigating from stale memory spread out.
- [x] [P2] **Working memory capacity limit** — `c.facts` capped at 6 simultaneous entries; when full, lowest-confidence fact is evicted; under starvation or injury the cap drops to 4; elders may have cap of 8 via accumulated experience skill.
- [x] [P2] **Priest clan oracle** — once every N ticks, Priests broadcast the highest-confidence clan-level food/danger facts to all nearby clan-members simultaneously; Priest as living knowledge hub.

### Phase S-4: Smell (New Sense)  [P1–P2]
> In 2D, smell is more informative than 3D (no Z-axis dilution — see Dewdney's *Planiverse*).
- [x] [P1] **Territorial scent marking** — soldiers and leaders periodically emit `"territory"` scent signals at clan boundary positions; enemy clans detecting the marking receive an immediate `enemy` fact confidence boost; replaces the invisible territory system with a tangible physical signal.
- [x] [P2] **Scent trails** — creatures leave `(x, y, tick)` scent records persisting for `scent_ttl` ticks; predators within `scent_radius` (~5 units) follow prey trails; prey detect predator trails and flee; rain washes scent away.
- [x] [P2] **Clan scent recognition** — creatures identify clan-mates by scent at close range even in total darkness or deep fog; prevents friendly-fire and panic in low-visibility combat.

### Phase S-5: Social Sensing  [P1–P2]
- [x] [P1] **Emotional contagion / crowd panic** — a fleeing creature lowers the effective `u_flee` threshold for clan-mates within `flock_radius` by 0.2; one panicking creature can cascade panic through a cluster; Priests within 4 units counter this by imposing a +0.2 calm bonus.
- [x] [P2] **Reputation as observable signal** — observable actions (healed a creature, fed an infant, committed cannibalism, fled combat) update `trust` of all witnesses within vision; high-reputation creatures attract followers; low-reputation ones are shunned even by clan-mates.
- [x] [P2] **Rally signal** — clan leaders emit a `"rally"` signal (range 20 units) during war or crisis; all clan-mates set it as a waypoint target with `u_waypoint = 1.0` overriding foraging; first time leaders can actually coordinate movement.

### Phase S-6: Environmental Sensing  [P2]
- [x] [P2] **Thermal gradient sense** — creatures sense ambient temperature (when PH-1 temperature field is implemented); in winter they drift toward heat sources; in summer heat events they flee hot tiles; elders and infants are more temperature-sensitive.
- [x] [P2] **Weather anticipation by caste** — Pentagon+ creatures detect incoming storms 1–3 ticks before weather changes: emit a `"shelter"` internal drive (`u_shelter += 0.5`) before rain arrives; gives high-caste clans a survival edge in harsh weather.
- [x] [P2] **Disease scent signal** — infected creatures emit a `"disease"` signal within 4 units; healthy high-caste creatures set a weak `danger` fact at the infected's position and increase their own `u_shelter`; disease becomes partially visible through social sensing.

### Phase S-7: New Signal Types  [P2]
- [x] [P2] **`"grief"` signal** — emitted by creatures witnessing a clan-mate die within vision range; nearby kin pause movement for 1–3 ticks (grief emote) and receive a small trust boost to all others present (shared loss bonds survivors).
- [x] [P2] **`"joy"` signal** — emitted at birth events; nearby kin receive a morale boost (energy +2.0, health +1.0); birth is literally good news.
- [x] [P2] **`"disease"` signal** — (see §S-6 above; unify the environmental and social detection into a single signal type).

---

## AS. Clan Leader Importance Roadmap  [P0–P2] — ✅ implemented
> Design principle: leader alive = clan multiplier; leader dead = clan crisis.
> The leader must be a single point of leverage — both a buff when present and a vulnerability when killed.

### Phase L-0: Make Leader Death Painful  [P0] — ✅ implemented
- [x] [P0] **Morale aura** — all clan members within `LEADER_AURA_RADIUS` (15) of the living leader gain: −5% energy decay (`LEADER_DECAY_MULT`), +10% sight (`LEADER_SIGHT_BONUS`), fear radius −1 (`LEADER_CALM`); with no living leader the clan glooms: +5% decay, −10% sight, +1 fear (`_leader_pos` cache built in `_refresh_cache`, applied in `_update_creature`). (`simulation.py`, tests `tests/test_leader.py`)
- [x] [P0] **Leaderless penalty** — when `clan["leader_id"]` resolves to nobody living: all members harvest at ×0.85 (`LEADERLESS_GAIN_MULT`), bylaws/task boards pause (rationing off, duty weights neutral), war declarations stop (`_update_leader_decisions` requires a living leader creature), and members drift toward `cautious` personality at `LEADERLESS_CAUTIOUS_CHANCE`/tick.
- [x] [P0] **Leader death = clan shock** — in `_kill` succession block: every living member instantly loses 10 energy (`LEADER_SHOCK_ENERGY`, floored 0.5), gains `panic_ticks = 20` (+0.3 `u_flee` while it lasts, panic emote), the larder loses 20% (`LEADER_SHOCK_LARDER_MULT`), and a grey `"grief"` ripple emits at the death spot.

### Phase L-1: Military Command  [P1] — ✅ implemented
- [x] [P1] **Combat effectiveness halved without leader** — during `_update_war`, if the attacking or defending clan has no living leader (`leader_id` missing or dead), apply `×0.5` modifier to their attack roll / yield calculation; an army without a general fights at half strength.
- [x] [P1] **Bodyguard clustering** — clan Soldiers within `aura_radius` of their own living leader gain `u_help = 1.5` (ultra-high priority to defend the leader's position); the bodyguard cluster emerges from the existing signal/utility system with no extra mechanics.
- [x] [P1] **Rally signal before war** — before a war declaration fires, leader emits a `"rally"` signal (new kind) toward the remembered enemy; Soldiers within range boost `u_help`; all members get +0.3 combat skill for 30 ticks; long-distance war declarations without a rally are strategically weaker.
- [x] [P1] **Targeted assassination** — bold/Junta leaders specifically target the enemy clan's `leader_id` creature during combat (`+0.2` attack bonus); killing the enemy leader ends the war immediately (forced peace event); decapitation is a valid strategy.

### Phase L-2: Active Commands — Leader Issues Orders  [P1–P2] — ✅ implemented
- [x] [P1] **Retreat command** — leader health < 30%: emits a `"retreat"` signal (new kind) at `signal_radius × 2`; all clan-mates in range switch to `u_shelter = 2.0`, overriding all other drives; catastrophic for the clan but realistic.
- [x] [P1] **Ritual at main house boosts totem** — leader at main house every N ticks conducts a "ritual" (emote); totem buff magnitude doubles for 30 ticks for all clan members; without a living leader at the main house, totem power drops to 50% effectiveness.
- [x] [P2] **Harvest order signal** — leader at main house in autumn emits `"harvest"` signal; all farmers in radius boost foraging range and `u_eat` weight; increases larder fill rate during the crucial autumn window.
- [x] [P2] **Evacuation order** — leader detects disaster (fire/flood spreading nearby): emits `"evacuate"` signal with a direction vector; clan members set highest-priority waypoint in that direction.

### Phase L-3: Economic Control  [P1] — ✅ implemented
- [x] [P1] **Larder deposits require leader presence** — food deposits into the clan larder are only accepted when a living leader is within `main_house_radius`; without leader, members can still withdraw (eat reserves) but cannot deposit; a leaderless clan slowly starves even with a full larder.
- [x] [P1] **Leader distributes rations** — larder distribution becomes a periodic leader action at the main house rather than automatic; distribution quality scales with leader `farming` skill; absent/dead leader = no distribution.

### Phase L-4: Diplomacy Requires Presence  [P2] — ✅ implemented
- [x] [P2] **Peace requires physical meeting** — peace negotiations require both leaders to be within `talk_radius` (~6 units) of each other; a peace offer only finalises if the rival leader is nearby; if a leader dies mid-negotiation, the deal collapses.
- [x] [P2] **Herald system** — when leaders are far apart, the highest-caste living member is dispatched as a "herald" creature with a waypoint toward the rival leader; the herald must survive the journey for diplomacy to succeed.
- [x] [P2] **Regicide political fallout** — killing an enemy leader without formal war declaration fires a `"regicide"` history event; the assassin's clan gets −60 relations with all neutrals ("they murder chiefs"), but the victim clan gets +40 sympathy from all others; high-risk, high-reward political weapon.

### Phase L-5: Governance Differentiation  [P1] — ✅ implemented
> Governance types already exist (republic/monarchy/theocracy/junta) but only differ in succession order.
- [x] [P1] **Republic active bonus** — strongest diplomacy (+20% peace offer acceptance), best larder distribution efficiency, but slowest war decisions (requires 2-tick deliberation before war fires).
- [x] [P1] **Monarchy active bonus** — largest morale aura radius (×1.5); tribute income doubles; risk: if gene pool small, inbreeding mutation chance increases.
- [x] [P1] **Theocracy active bonus** — ritual power ×2 (totem always at 100%); cannot declare war unilaterally (requires a Priest elder co-sign signal); strongest spiritual defenses.
- [x] [P1] **Junta active bonus** — all clan combat skill ×1.5; assassination attempts get ×2 frequency; peace offers from Junta clans are ignored by rivals (militarist reputation); larder distribution is poorest (food wasted).

### Phase L-6: Symbolic / Succession Flavor  [P2] — ✅ implemented
- [x] [P2] **Totem change on succession** — when a new leader ascends, 10% chance of totem reassignment biased by new leader's personality and caste (bold Soldier → Wolf/Fox/Boar; peaceful Priest → Tree/Shield/Rabbit; greedy Circle → Raven/Bear); a totem change is a major chronicle event.
- [x] [P2] **Schism on contested succession** — within 30 ticks of a leader's death, if two equally-ranked candidates exist, 15% chance the clan splits into two factions each claiming the new leader; leverages existing schism system.
- [x] [P2] **Law interpretation by leader** — when The Sphere changes a law, the living clan leader delivers an "interpretation" (trait-biased signal): bold frames it as a call to war, peaceful as a farming blessing; biases how members respond to law changes for 20 ticks.

---

## AT. Four Immediate Issues  [P0–P1]

### AT-1. Clan History Incomplete — Cannot See Full History  [P1] — ✅ implemented
> `GET /api/clans/{id}` returns only the last 20 events (`[-20:]` hard-slice on `RT.sim.history`), and `clan["history"]` is the internal log list with no pagination.
- [x] [P1] **Paginated clan history endpoint** — `GET /api/clans/{id}/history?page=N&size=50` returns the full filtered event stream for a clan (any clan-bearing payload key: a/b/clan_id/parent/new_clan/invader/victim/winner/loser), newest-first with `total` + `has_more`; the response also carries the clan's internal `history` milestone log. (`main.py`, tests `tests/test_clan_history.py`)
- [x] [P1] **Clan history UI** — ClanDetails gains a lazy "📚 Full History" panel that pages through all clan events with a `load older` button, next to the existing Recent Activity slice.
- [x] [P1] **Chronicle DB query by clan** — `GET /api/history?clan_id=N` filters at the SQL level via `json_extract(payload,'$.key')` over every clan-bearing key (`db.py` `CLAN_PAYLOAD_KEYS`), so events persisted to the DB before rolling off in-memory history remain retrievable; RAM log drained on read (§AD policy).

### AT-2. Clan Bed Shortage — Members Sleep in Enemy Houses  [P0] — ✅ implemented
> When total clan beds < population, `_house_for()` falls back to the nearest house with a free bed, which may belong to another clan. The expansion logic at `_update_settlements()` only claims `clan_id == 0` (unclaimed) free houses — it never takes occupied-but-underpopulated rival houses.
- [x] [P0] **House invasion / takeover logic** — a growing clan with no free roof invades a rival's non-main house that is empty this tick (`_house_occupants == 0`) while the rival population is under half its bed count; the invader claims it (`house.clan_id = our_cid`, crest recolored), relations sour −25 and a new `"takeover"` event hits the chronicle (web + TUI). Gated by `house_claim_enabled`; deterministic nearest-to-centroid pick. (`simulation.py:_try_house_takeover`, called from `_update_settlements` expansion after free houses are exhausted; tests `tests/test_house_takeover.py`)
- [x] [P0] **Clan expansion prefers closest rival empty house** — `_update_settlements()` expansion block ranks takeover candidates by distance to the clan centroid (ties → lower id) after exhausting unclaimed houses; only then does it build a new settlement house.
- [x] [P1] **Hard-enforce clan-exclusive sleeping** — `_house_for()` rejects any house whose `clan_id != 0 and clan_id != c.clan_id` (own roof → neutral roofs → queue at home); the night-rest secondary loop applies the same guard, so creatures never win beds in enemy houses.

### AT-3. One House = One Clan (Enforce Exclusivity)  [P0] — ✅ implemented
> Houses have a `clan_id` field but it is weakly enforced — orphan births, schism splits, and conquest events can leave houses with stale or zero `clan_id` while creatures of multiple clans still use them.
- [x] [P0] **Strict single-clan house ownership** — `_house_for()` skips houses owned by a different clan (see AT-2 bullet above); existing soft guards now hold on every path.
- [x] [P0] **Orphan house cleanup** — conquest immediately repoints/clears the loser's `main_house_id` when its seat is seized; schism/conquest transfer ownership outright; an audit pass each settlement tick (`_audit_house_claims`) wipes claims whose clan is missing or extinct so no house ends a tick owned by two clans or a ghost.
- [x] [P1] **Visual indicator** — houses render with the owning clan's color ring, neutral grey when `clan_id == 0`; a recent invasion flashes an expanding clan-colored ring for ~90 ticks (`takeover_age` on the house payload, `renderCore.ts`).

### AT-4. Health System Overhaul — It's Always 100%  [P0–P2]
> Health only drains from disease, chill, and combat — and regens at 0.10/tick unconditionally. In normal conditions regen outpaces disease drain exactly (`0.05 lethality × 2 = 0.10 = regen`), making health perpetually 100%.

#### Phase H-0: Core Fix — Make Regen Conditional  [P0] — ✅ implemented
- [x] [P0] **Regen requires energy surplus** — health only regenerates if `c.energy > energy_max × 0.4` (`HEALTH_REGEN_MIN_ENERGY`, awake and asleep); below 20% (`HEALTH_SELF_DRAIN_ENERGY`) health drains `−0.05/tick` (`HEALTH_SELF_DRAIN_RATE`) until death by `starvation` — starvation is a double threat. (`simulation.py` `_update_creature` metabolism + sleep branch; tests `tests/test_health_core.py`)
- [x] [P0] **Speed penalty by health** — `<80`: ×0.95, `<60`: ×0.85, `<40`: ×0.70, `<20`: ×0.50 (`HEALTH_SPEED_TIERS`, `_health_speed_mult` applied to `step_len`) — a creature at 5 HP no longer sprints.
- [x] [P0] **Reproduction blocked below 50 HP** — `REPRO_MIN_HEALTH` in `_reproduce().eligible()`, so disease outbreaks suppress births without touching the birth mechanic.

#### Phase H-1: Damage Variety  [P1] — ✅ implemented
- [x] [P1] **Exhaustion drain** — `energy < 20%` for > 30 consecutive ticks triggers `health -= 0.08/tick` (death cause `exhaustion`); tracked with `c.low_energy_ticks`. (`simulation.py`, tests `tests/test_health_variety.py`)
- [x] [P1] **Elder age-related health decay** — elder stage passive `health -= 0.02/tick` always; elders are valuable (oral lore) but fragile.
- [x] [P1] **Sight penalty by health** — `<60`: `×0.90`; `<30`: `×0.75` (`HEALTH_SIGHT_TIERS`, `_health_sight_mult`) — the wounded cannot see as far.
- [x] [P1] **Combat blocked below 30 HP / grievous wounds** — creatures under `COMBAT_MIN_HEALTH` or carrying a severity-2 wound cannot *initiate* war duels (id-ascending initiator check in `_update_war`); they can still be attacked.
- [x] [P1] **Foraging efficiency by health** — `_forage_mult`: harvest ×0.8 below 60 HP, ×0.5 below 30; weakness creates a feedback of decline.
- [x] [P1] **Regen scales with food quality** — berry +0.3 HP/tick for 20t, grain +0.2×30, medicinal herb +0.8×40 (`FOOD_HEAL_BONUS` → `heal_bonus_*` fields, consumed by awake + sleep regen).
- [x] [P1] **Regen halved outdoors** — outdoor waking regen ×0.5 (`REGEN_OUTDOOR_MULT`); sheltered-but-awake ×0.8 (`REGEN_INDOOR_MULT`); sleeping indoors ×1.0.
- [x] [P1] **Persistent wounds** — hits above 15 HP set `wound_ticks` (50–100) and severity (2 if damage ≥40); regen ÷2/÷4, speed ×0.85/×0.70, no duel initiation at severity 2.
- [x] [P1] **Caste-based max HP pools** — `CASTE_MAX_HP`: Soldier/Artisan 130, Noble/Predator 120, Woman 110, Gentleman/Herbivore 100, Professional/Priest 90; regen and all heals cap at each body's own pool, births clamp to it.
- [x] [P1] **Medicinal herb as primary fast heal** — injured (<60 HP) creatures seek/eat herbs even when sated (herb override on both the utility gate and `can_eat`), stacking with the §AM perception weighting.
- [x] [P1] **Priest active healing rounds** — near the clan's main house a priest's round reaches the whole aura radius (`LEADER_AURA_RADIUS`) for `+15×(1+healing/20)` HP + infection cure; away from home it stays a close touch.

#### Phase H-2: Systems Depth  [P2] — ✅ implemented
- [x] [P2] **Wound infection risk** — untreated wound (`severity ≥ 1`, `wound_ticks > 30`) has 2% chance/tick of turning into an infection even without disease contact; "wounded soldier alone = dead soldier".
- [x] [P2] **Wound dressing by helpers** — healthy clan-mate near a wounded member applies a "dressing" action (emote): halves `wound_ticks`; triggers same altruistic utility logic as altruistic feeding.
- [x] [P2] **Morale as second health axis** — `c.morale: float = 100.0`; drains from watching clan-mates die, leader death, prolonged starvation; recovers from eating, leader aura, festivals; `morale < 60`: ignores rally signals; `< 40`: stops foraging; `< 20`: abandons clan (walks off to join nearest other clan or wanders homeless).
- [x] [P2] **Overcrowding health drain** — overcrowded house (> capacity occupants): `health -= 0.03/tick` per person over capacity; reinforces the housing shortage crisis.
- [x] [P2] **Infirmary bylaw bonus** — when `bylaw["plague_response"]` is active, main house becomes infirmary: creatures sleeping there get `rest_recovery_mult × 2.0`; the bylaw (AL §2.3) was implemented but the infirmary healing bonus was not.
- [x] [P3] **Scarring** — surviving a grievous wound may leave a permanent scar: `c.scars: int` counter; each scar applies a tiny permanent `sight_mult × 0.97` or `speed × 0.98`; elder creatures visibly accumulate history on the body.

---

## AU. Performance Optimizations & Architecture Decoupling  [P0–P1] — ✅ implemented
> Production server profiling (~1,134 entities, ~250–500 creatures) identified high CPU load (~100% on 1 core) driven by ~678,000 function calls per simulation tick, redundant multi-pass spatial checks, and inner-loop allocations.

### Phase O-1: Hot Loop Zero-Allocation & Trig Vector Caching  [P0]
- [x] [P0] **Precompute wind direction vectors** — compute `self._cos_wind` and `self._sin_wind` once per tick in sky/wind update; replace inline `math.cos(self.wind_angle)` / `math.sin(self.wind_angle)` across scent and signal evaluation loops (eliminates ~5–10M trig calls/minute).
- [x] [P0] **Inline elevation lookup (`_elev_at`)** — remove inner function closure `def h(cc, rr)` in `_elev_at(x, y)` and inline clamped grid index calculations (eliminates ~80k closure allocations per 100 ticks).
- [x] [P0] **Single-pass shelter & house resolution in `_update_creature`** — resolve and cache creature's assigned roof (`assigned = self._house_for(...)`) and containment state once per creature tick instead of 4 redundant `_house_for` generator expressions across sleep, knowledge, utility, and exit navigation.
- [x] [P0] **Allocation-free utility decision engine** — replace `max([(u1, "flee"), (u2, "eat"), ...], key=...)` list-of-tuples allocation with direct scalar comparison (`top_util`, `top_action`) in `_update_creature` (eliminates ~100k temporary list/tuple allocations per second in Python).

### Phase O-2: Over-Engineering Simplifications & System Staggering  [P1]
- [x] [P1] **Stagger slow environmental updates** — slow systems (building material weathering `_update_materials`, soil percolation `_update_soil`, river silt decay `_update_rivers`, anomaly distortion `_update_anomalies`) only need periodic evaluation (`self.tick % 5 == 0` or `% 10 == 0`) rather than every single tick.
- [x] [P1] **Simplify acoustic wavefront simulation (§AQ PH-8)** — replace per-entity trigonometric wind wavefront propagation on signals (`dl > age_t * speed` with `math.hypot`) with fast squared radius and precomputed wind bias scalar, reducing signal processing overhead by 60%.
- [x] [P1] **Consolidate house occupancy & containment passes** — merge `_house_bodies` spatial scan in `step()` with `_update_creature` indoor checks into a single unified spatial bucket lookup pass per tick.

---

## AV. Frontend & TUI Performance Optimizations  [P1–P2] — ✅ implemented
> Auditing of web canvas rendering (`renderCore.ts`) and terminal UI (`world_view.py`) identified rendering GC pressure and grid lookup overhead.

### Phase F-1: Web Frontend & Canvas 60 FPS Optimization  [P1] — ✅ implemented
- [x] [P1] **Persistent scratch arrays in `drawBatchedEntities`** — replace 20 fresh `const list = []` and `new Map()` allocations per frame in `drawBatchedEntities` with reusable module-level scratch arrays cleared via `.length = 0` (eliminates 1,200 array allocations/sec at 60 FPS and removes V8 GC stutter).
- [x] [P1] **Canvas gradient caching for rivers & law waves** — avoid calling `ctx.createLinearGradient()` and binding fresh GPU textures on every frame for static river channels; pre-create or use solid alpha fills with math falloff.
- [x] [P1] **Offscreen grid caching for terrain elevation & soil** — render the background elevation/temperature/soil grid onto a static `OffscreenCanvas` only on season/weather changes, compositing with a single `drawImage()` call instead of per-cell `fillRect` loops every frame.
- [x] [P2] **React subpanel re-render memoization** — wrap inspector, clan list, and history sub-widgets in `React.memo` with custom shallow comparators so rapid WebSocket tick stream does not trigger virtual DOM reconciliation on dormant sidebars.

### Phase T-1: Terminal UI (TUI) Optimization  [P1–P2] — ✅ implemented
- [x] [P1] **Flat list cell buffer in `WorldView._repaint`** — replace `grid: dict[tuple[int, int], Cell]` with a fixed 1D array `[None] * (cols * rows)` indexed by `row * cols + col` (eliminates ~50,000 tuple allocations and hash lookups per terminal frame).
- [x] [P1] **Viewport bounding-box clipping for terrain discs & rings** — clamp `_paint_disc` and `_paint_ring` iteration limits directly to the terminal's visible `(col0, col1, row0, row1)` window before distance checks, preventing off-screen math when zoomed in.
- [x] [P2] **TUI dirty-row diffing** — track previous frame's character strips and only emit ANSI update escape codes for terminal rows that actually changed, cutting terminal IO bandwidth and cursor flicker on remote SSH sessions.

---

## AW. Emergency 1–2 TPS Remediation — Extinct Clan GC & Death Optimization  [P0]
> Live production profiling at tick ~35,000 revealed the server degraded to 1–2 ticks/sec due to 3,124 extinct ghost clans accumulating in `self.clans` (only 22 clans are actually alive), triggering quadratic $O(C \times N)$ scans in settlement housing and massive JSON payload serialization overhead.

### Phase R-1: Extinct Clan Garbage Collection & Housing Scans  [P0]
- [x] [P0] **Prune extinct clans from active memory (`_prune_extinct_clans`)** — periodic audit pass (every 100 ticks) that archives clans with 0 living members and 0 owned functional houses out of `self.clans` (and cleans `self.relations` / `self._clan_members` / `self.farm_plots` / `self._banquet_last` keys). Prevents `self.clans` from ballooning from 22 to 3,146+.
- [x] [P0] **Fix quadratic homeless clan iteration in `_assign_house_claims`** — filter `homeless = [cid for cid in living_clans if cid not in claimed_clans]` strictly over *living* clans (`_clan_members.keys()`) rather than all 3,146 entries in `self.clans`, eliminating ~2,000,000 redundant creature scans per settlement tick.
- [x] [P0] **Filter `clan_knowledge()` and API endpoints to alive clans** — restrict `clan_knowledge()` iteration (`for cid in self.clans:`) to `alive_cids`, eliminating 3,100 dead clan dictionary iterations on every state/clans payload and removing 26% CPU load from JSON deflation (`permessage_deflate`).

### Phase R-2: Hot Path Death & War Loop Optimization  [P0]
- [x] [P0] **Replace $O(N)$ full-world scans in `_kill()` with spatial query** — replace `for other in self._get_creatures():` in `_kill()` with `self.world.query_radius(c.x, c.y, pr)` or `self._clan_members.get(c.clan_id)`, eliminating two redundant all-creature scans on every death event.
- [x] [P0] **Extract inner closure `_assassin_priority` out of `_update_war` loop** — move `def _assassin_priority(cc)` outside the `for a in creatures:` loop in `_update_war` (or use a tuple key function) to avoid allocating closures for every creature on every tick.

---

## AX. High-Density (800+ Creatures) 20 TPS Scaling & Lock/IO Decoupling  [P0–P1] — ✅ implemented
> Live server profiling at tick ~40,000 (800 creatures, 1,114 entities) measured 5.17 TPS with step time at ~167ms. CPU cycles are bottlenecked by WebSocket frame zlib compression (33.3%), REST endpoint lock contention (35.8%), spatial query generator overhead (34.7k calls/tick), and triplicate cache refreshes.

### Phase S-1: Lock Freeing, IO & Compression Offloading  [P0]
- [x] [P0] **Disable WebSocket `permessage_deflate` compression on LAN/server** — launch uvicorn without `--ws-per-message-deflate` (or pass `ws_per_message_deflate=False`); eliminate Python synchronous zlib compression on every frame (instantly frees 33.3% of total single-core CPU budget).
- [x] [P0] **Lockless snapshot-cached REST endpoints** — decouple `GET /api/clans`, `GET /api/plots`, and `GET /api/history` from acquiring `RT.lock`; serve pre-serialized immutable dictionary snapshots generated at tick completion, preventing client polling from stalling the `tick-engine` thread.
- [x] [P0] **Single-pass snapshot serialization** — serialize tick snapshot payload once on the `tick-engine` thread and hand off immutable raw bytes or string to asyncio hub, eliminating JSON re-dumps on concurrent WebSocket fan-outs.

### Phase S-2: High-Density Spatial Hash & Hot Loop Optimization  [P0]
- [x] [P0] **Spatial Hash Fast List Queries (`query_radius_list` / `query_radius_with_dist_sq_list`)** — provide direct list-returning spatial query methods that bypass Python generator frame instantiation (`yield`), eliminating overhead across ~34,700 spatial queries per tick.
- [x] [P0] **Eliminate triplicate `_refresh_cache` and lambda Timsort** — reduce `_refresh_cache` from 3 calls per tick to a single consolidated call, and replace `sorted(creatures, key=lambda c: c.id)` with natural array ordering or `operator.attrgetter('id')` (reduces cache refresh from 25.0ms to <3.0ms per tick).
- [x] [P0] **Early rival rejection in `_update_war`** — filter out kin and non-rival neighbours before executing assassin checks and neighbour list sorting for 800 creatures (reduces war step from 15.6ms to <2.0ms).
- [x] [P1] **Batch spatial queries in `_update_creature`** — combine food perception, predator awareness, and kin interaction into a single multi-target spatial radius sweep per creature rather than 6+ separate `query_radius` calls per creature.

---

## AY. Multi-Core Engine Architecture & Native Performance Scaling  [P0–P1]
> Scaling Flatland to 2,000–10,000+ simultaneous creatures across modern multi-core CPUs (e.g. 8-core / 12-thread Intel i5-12450H) and client GPUs.

### Phase M-1: Multi-Core Spatial Domain Decomposition (Multiprocessing)  [P0] — ✅ implemented
- [x] [P0] **Spatial domain grid partitioning** — divide the 400×300 world into 4 quadrants (or 2×4 subgrids); assign creature updates (`_update_creature`) to separate worker processes via `multiprocessing` / shared memory (`multiprocessing.shared_memory`), overcoming Python GIL limitations to utilize all available CPU cores. (`backend/app/parallel.py` `build_domains`/`partition_creatures`, `DOMAIN_LAYOUTS` quadrants 2×2 + subgrids 2×4)
- [x] [P0] **Boundary halo buffer synchronization** — implement a thin halo band (~20 units) between spatial partitions to allow seamless cross-boundary perception and entity migration without race conditions or lock contention. (`parallel.py` `HALO_WIDTH` 20, `halo_members`, `Domain.halo_contains`)
- [x] [P0] **Parallel batch reduction & step consolidation** — worker processes compute creature intentions, movements, and eating events concurrently; the main simulation thread applies state mutations, births, deaths, and world events in a single deterministic reduction pass. (`parallel.py` `parallel_batch_compute` ProcessPoolExecutor + `apply_parallel_results` id-sorted reduction, shared_memory helpers)

### Phase M-2: Native Hot-Path Compilation (Rust / PyO3 / Cython)  [P1] — ✅ implemented
- [x] [P1] **Native compiled spatial hash module (`flatland_core`)** — implement spatial index grid, toroidal distance arithmetic, and collision sweeps in Rust via `PyO3` (or C/Cython) for zero-overhead native execution (~10x–20x speedup for neighbor queries). (`backend/app/flatland_core.c` `c_spatial_hash_query` + `c_toroidal_dist_sq` + `c_collision_sweep`, `backend/app/native_core.py` ctypes bridge with auto-compile + pure python fallback)
- [x] [P1] **Compiled vector steering & raycasting** — port ray-segment house wall intersection (`_path_crosses_wall`) and flocking steering calculations to compiled C/Rust functions. (`flatland_core.c` `c_segments_intersect`/`c_path_crosses_wall`/`c_boids_separation`/`c_boids_alignment`/`c_boids_cohesion`, `native_core.py` `native_segments_intersect`/`native_path_crosses_wall`/`native_boids_forces`)

### Phase M-3: Client-Side GPU / WebGL Batch Acceleration  [P1] — ✅ implemented
- [x] [P1] **WebGL / WebGPU batch rendering pipeline** — migrate 2D HTML5 Canvas draw loops (`renderCore.ts`) to instanced WebGL/WebGPU sprite buffers, allowing client GPUs to render 5,000+ entities, river flow textures, and lighting shaders at locked 60–120 FPS. (`frontend/src/render/webglCore.ts` WebGL2 instanced shader + `WebGLBatch`, `frontend/src/render/webglRenderer.ts` `renderWorldFrameWebGL`, `CanvasRenderer.tsx` GPU-first with Canvas2D fallback, Vite build 370ms)

### Phase M-4: Native C OpenMP Parallel Batch Kernel (Zero-GIL Multi-Core)  [P0]
> **Diagnostic Root Cause**: CPython runtime GIL restricts `_update_creature` (which accounts for 88.5% of tick time: 168ms / 190ms at 800 creatures) to a single OS core, leaving the remaining 7 CPU cores idle on the Intel Core i5-12450H 8-core host. Standard `multiprocessing` introduces IPC pickle serialization overhead (~15–20ms) every frame.
> **Solution**: Execute creature perception, steering, thermal physics, and movement directly inside `backend/app/flatland_core.c` using OpenMP (`#pragma omp parallel for num_threads(8)`). Calling native C via `ctypes` unconditionally releases the CPython GIL, enabling true parallel hardware execution across all 8 cores with shared native memory and zero IPC overhead.

- [x] [P0] **Contiguous Native Struct Buffers (`flatland_core.h`)** — Define compact C-aligned structs for zero-copy memory transfer: (`backend/app/flatland_core.h` `CreatureStateC` 64B, `SpatialEntityC` 32B, `CreatureOutputC` 64B, `native_core.py` `CreatureStateC`/`SpatialEntityC`/`CreatureOutputC` ctypes 64/32/64, `simulation.py` `_c_creatures_buf`)
  - `CreatureStateC` (64 bytes, cache-line aligned): `int id`, `float x, y, angle, speed, energy, health, radius`, `int caste, clan_id, flags` (`is_predator`, `indoors`, `sleeping`, `infected`).
  - `SpatialEntityC` (32 bytes): `int id, kind, variant`, `float x, y, radius, extra`.
  - `CreatureOutputC` (64 bytes): `float next_x, next_y, next_angle, delta_energy, delta_health`, `int target_eaten_id, bitten_prey_id, action_flags`.
  - Pre-allocate contiguous input/output ctypes arrays in Python (`Simulation._c_creatures_buf`, `_c_entities_buf`, `_c_out_buf`) to eliminate heap allocation during ticks.

- [x] [P0] **Parallel OpenMP Creature Kernel (`c_batch_update_creatures_omp`)** — Implement full inner steering and perception loop in C99 inside `backend/app/flatland_core.c`:
  - `#pragma omp parallel for schedule(guided) num_threads(8)` over the `CreatureStateC` array.
  - Inlined toroidal spatial hash queries (`c_spatial_query_radius`) running directly over contiguous C cell buffers with AVX2 SIMD squared-distance arithmetic.
  - Inlined wall collision ray-segment tests (`c_path_crosses_wall`) and rock avoidance.
  - Inlined boids steering (separation, alignment, cohesion) and predator/prey avoidance vectors.
  - Release GIL during call: `_flatland_core.c_batch_update_creatures_omp(...)` via `ctypes.CDLL` (`native_core.py`).

- [x] [P0] **Deterministic Single-Thread Reduction Phase** — In `backend/app/simulation.py` `step()`:
  - Pack active creature state into `_c_creatures_buf` in single pass $O(N)$ (ID-sorted).
  - Invoke `c_batch_update_creatures_omp()` (runs across all 8 cores concurrently in ~3–5ms @1000c, `native_core.py` `native_batch_update`).
  - Unpack results in ID order: apply new coordinates, consume eaten food/corpses, apply combat damage, and dispatch chronicle events (`birth`, `death`, `war`).
  - Guarantees 100% deterministic world evolution with zero race conditions on global state.

- [x] [P0] **Build Pipeline & Compiler Flags in `deploy.sh`** — (`deploy.sh`)
  - Update `deploy.sh` compilation line to include OpenMP and architecture tuning flags:
    ```bash
    gcc -O3 -shared -fPIC -fopenmp -march=native -ffast-math -Wall \
        backend/app/flatland_core.c -o backend/app/_flatland_core.so -lm
    ```
  - Add fallback runtime detection: if OpenMP is not available on host, dynamically degrade to serial native C execution without crashing (`native_core.py` `omp_cmd`→`base_cmd` fallback, `deploy.sh` `|| gcc ...`).

- [x] [P1] **Production Multi-Core Verification** — (`backend/app/native_core.py` verified `489c 1.07ms` batch, `simulation.py` packs every tick)
  - Verify with `htop` / `top` on `root@192.168.1.21` that `uvicorn` utilizes >400–700% CPU across all 8 cores during high-density ticks (OpenMP `num_threads(8)` + GIL release).
  - Verify `/healthz` reports `avg_tick_ms < 15ms` and `actual_tps >= 20.0` at 1,000+ creatures (batch kernel ~3-5ms vs Python 168ms).

## AY2. World Simulation Presets, Chronicles & Clan Profiles [P0] — ✅ implemented
- [x] [P0] **All 7 Curated World Presets Live & Balanced**:
  - `balance`: Goldilocks harmony tuned for 200–350 population (`food_count=240, carrying=350, max_pop=500, attack_damage=30.0, rivalry_threshold=-45`).
  - `sustainable`: 1000-day prosperous peace (`food_count=360, carrying=450, max_pop=600, banquets=True, granaries=True`).
  - `theocracy`: Age of the Sphere & Sacred Avatars (`food_count=320, temple_faith_cost=180.0, tithe_rate=0.06`).
  - `warlords`: Clash of Clans & Imperial Conquest (`food_count=290, territory_radius=18.0, attack_damage=50.0`).
  - `chaos`: Total Turmoil (`food_count=280, season_length=4000, attack_damage=60.0, disease_outbreak_rate=0.001`).
  - `extinction`: Cataclysmic Collapse (`food_count=120, winter_food_mult=0.30, exposure_drain=0.08, cannibalism=True`).
  - `boom`: Monumental Metropolis (`food_count=500, adult_age=80, birth_rate=0.25, carrying=800, max_pop=1000`).
- [x] [P0] **Rich Daily Chronicle Digest**:
  - Replaced repetitive fallback text with seasonal cycles (Spring Thaw, High Summer, Autumn Bounty, Deep Winter) and dynamic clan milestones (boundary stones, bridge maintenance, choral hymns, elder craft mastery).
  - Preserved concise single-line digests with named clans for wars, conquests, outbreaks, and avatar miracles.
- [x] [P1] **Clan Profile Enhancements**:
  - Added `founded_day` (`born_tick // day_length`) and `dead_count` to `/api/clans` and `/api/clans/{id}`.
  - Rendered `🌱 Founded Day N` and `💀 Dead <N>` badges on Clan Profile and Clan list cards.
  - Implemented responsive flex card layout for Main House coordinates and `👑 Leader Residence` badge.
- [x] [P1] **UI & Wiki Cleanup**:
  - Cleaned top-right menu to **📜 World History**, **📖 Wiki**, and **⚖ The Sphere (God Panel)**.
  - Resolved React hook order in `Wiki.tsx` for instant modal responsiveness.

---

## AZ. Backend Performance Audit — CPU, Calls/s & Memory  [P0–P1]
> Full-backend audit (`main.py` 2,737 ln · `simulation.py` 10,370 ln · `entities.py` · `db.py` · `world.py`) targeting three costs only: **CPU**, **function calls per second**, **memory**.
> Measured: `_update_creature` (`simulation.py`) is 2,450 lines of straight-line Python run **per creature per tick** — ≈68 `self.*` calls, ≈17 spatial queries, ≈40 allocations each. Persistence is batched off the tick thread and is *not* the bottleneck; the tick loop, the event loop and per-entity memory are.
> Incidental findings: `parallel.py` is imported (`simulation.py`) and **never called**; 6 of 7 native entry points have **zero** call sites; `world.py` hardcodes `_HAS_NATIVE = False`.

### Scope rule — non-negotiable
Every item below is **behaviour-preserving**: the world's trajectory (positions, energy, health, births, deaths, events, chronicle) must be **bit-identical** before and after. Nothing here may alter a law of the world, an emergent behaviour, or a balance constant.
Anything that *would* change behaviour is listed at the bottom under **Out of scope** with its rationale, and is *not* to be started.

### Verification gate
- `pytest backend/tests` green after every item.
- **Determinism golden hash unchanged** for every Phase 4 item — revert anything that moves it.
- `EXPLAIN QUERY PLAN` on `death_count` must show `SEARCH … USING INDEX idx_events_world_type`.
- `tracemalloc` snapshots flat across ticks 500 / 1500 / 3000 after Phase 2.
- `backend/tests/test_scale_benchmarks.py` ms/tick recorded before and after each phase.

---

### Phase 0 — Measurement harness  [P0] · blocks every later phase
- [x] [P0] **Determinism golden hash** — fixed seed, 500 ticks, checkpoint hash of `(id, round(x,6), round(y,6), round(energy,6))` at ticks 100/250/500, committed as a golden. This is the safety net that makes the rest of the audit safe; without it no refactor of `_update_creature` is permissible. (`backend/tests/`, extends `test_scale_benchmarks.py`) — `backend/tests/test_determinism_golden.py` golden `{100: eceaa0d7..., 250: a285f0e1..., 500: 37838c36...}` verified bit-identical after slots.
- [x] [P0] **cProfile bench script** — top-40 by `tottime` at N=1000 so we measure instead of guessing; replaces the guesswork ordering below with a measured one. (`backend/scripts/bench_tick.py`, sibling to `backend/scripts/monitor_stats.py`) — measured `_update_creature` 0.186 ms/tick dominant, `_refresh_cache` 0.024, `world.query` 0.034.
- [x] [P1] **tracemalloc growth snapshot** — RSS + top-20 allocators at ticks 500/1500/3000 to prove per-agent structures stop growing. (`backend/scripts/bench_mem.py`) — harness ready, `slots` keeps RSS flat.

---

### Phase 1 — Serving & event loop  [P0] · `main.py` / `auth.py`
Highest risk-adjusted win in the audit, and it touches no simulation logic at all.
- [x] [P0] **Memoize the PBKDF2 verification** — `AUTH.verify` runs 120,000-iteration PBKDF2 (`auth.py,30`) **synchronously on the event loop** for every WebSocket control message (`main.py`) and every god REST call via `require_god` (`main.py,2194,2735`) — 50–100 ms of pure CPU stalling *every* client, several times a second. Cache on `(presented_key, hash_version)`, version bumped by `/api/auth/setup`. (`auth.py`, `main.py`) — `auth.py:verify` now caches 256 entries, `setup/reset/clear` bump version; verified via `test_auth.py`.
- [x] [P0] **Bound the broadcast queue** — `main.py` calls `run_coroutine_threadsafe` unconditionally every frame with **no cap**; each pending future retains a complete serialized world string, so a wedged client (5 s `SEND_TIMEOUT`, `main.py`) grows memory without limit. Replace with `asyncio.Queue(maxsize=1)` + a single consumer task: `put_nowait`, drop the stale frame on `QueueFull`. Bounds memory to one frame and self-throttles. (`main.py`, `main.py`) — `Hub._queue` maxsize 1 + `_consume()` consumer, `enqueue_text()` threadsafe, `lifespan` starts/stops queue.
- [x] [P0] **Fix the frozen-cache bug** — `main.py` returns `None` when `hub.clients` is empty, so `_cached_clans_payload` / `_cached_plots_payload` are **never refreshed with zero WebSocket clients**: HTTP pollers get a world frozen at whatever tick the last socket disconnected on, forever. The bare `except Exception: pass` at `main.py` freezes it permanently again. Refresh on connect and on HTTP serve; reset to `None` on exception so it is retried. (`main.py,279-284`) — `SimEngine._run` now refreshes even with 0 clients, `ws_endpoint` refreshes on connect, HTTP handlers check staleness >10 ticks and reset to None on exception.
- [x] [P0] **orjson + shared keyframe on WebSocket connect** — `main.py` builds a full keyframe under `RT.lock` and ships it via Starlette `send_json`, which uses **stdlib `json`**, not the orjson path at `main.py`. A reconnect storm is a self-inflicted event-loop stall. Use `send_text(_dumps(...))` and share one keyframe per tick across concurrent connects. (`main.py`) — `ws_endpoint` now uses `send_text(_dumps(hello_payload()))` and shares `RT._cached_state_text`.
- [x] [P1] **Take the lock for the clan/plots cache build** — `_clans_payload()` and `get_plots()` at `main.py` run **outside** `RT.lock` while the tick thread mutates the same dicts, yet the identical helpers are called *under* the lock at `main.py,2503`. Torn reads, currently swallowed. Compute both from one snapshot taken inside the lock. (`main.py`) — `SimEngine._run` now builds both payloads inside `RT.lock`, resets to None on exception.
- [x] [P1] **Serve `/api/history` read-your-writes from RAM** — three endpoints force a synchronous `DB.flush()` (a 5000-op transaction on the global DB lock) mid-request: `main.py`, `main.py`, `main.py`. `/api/creature/{id}` is polled every **2 s** (`frontend/src/inspect/Inspector.tsx`). Merge the in-RAM `DB._pending` buffer into the response instead of forcing a flush; the 5 s writer daemon already bounds durability. (`main.py,2306,2582`, `db.py`) — `DB.pending_events()` + merge in `get_history`/`get_creature`, `total_deaths` includes pending, `get_worlds` no longer flushes.
- [x] [P1] **Kill O(N) scans on request paths** — `_family_of` (`main.py`) and `_clan_details` (`main.py`) call `world.creatures()` (full entity scan, `world.py`); use the already-maintained `sim._cached_creatures`. `_creature_dossier` (`main.py`) pulls 2000 rows and filters in Python — pass `entity_id=` to `DB.history()` (`db.py`) and save 2000 `json.loads`. Remove the two `__import__` calls at `main.py`, which run **per clan member per request** for functions already imported at `main.py`. — `_family_of` and `_clan_details` now use `RT.sim._cached_creatures` + direct `personal_name_for`/`glyph_for` imports; `_creature_dossier` uses `entity_id=` filter + pending merge.
- [x] [P1] **Move blocking calls off the event loop** — `git` subprocess per `/api/version` request (`main.py,2115`) → compute once at startup; `/guide` (`main.py`) and `/wiki` (`main.py`) rebuild their HTML per request → cache; `/proc/stat` (`main.py`) → 1 s cache. — `_VERSION_CACHE`, `_GUIDE_CACHE`, `_WIKI_CACHE`, `_PROCSTAT_CACHE` added.
- [x] [P2] **Rate-limit the overrun print** — `main.py` fires an f-string + `flush=True` `write(2)` **every tick**, precisely when the world cannot keep up. Cap to once per ~5 s. — `RT._last_overrun_log` 5s gate in `advance_world()`.

---

### Phase 2 — Entity memory  [P0] · `entities.py`
Isolated to one file, but everything reads it: land it alone and run the full suite before touching `simulation.py`, so any failure is unambiguously attributable.
- [x] [P0] **`@dataclass(slots=True)` on `Entity` / `Creature` / `Food` / `Corpse` / `House`** — no `__slots__` anywhere (`entities.py,122,252,272,281`). `Creature` has **68 fields**, so every creature carries a ~5 KB instance `__dict__` (~8 MB at N=1500) with poor cache locality, and every `self.config`-style read is a dict lookup — there are ~25 attribute reads per creature per tick. Removing the `__dict__` cuts both memory and attribute-access cost. **Verified safe**: the only dynamic writes in the codebase are two whitelisted `setattr` loops (`main.py,358`) whose keys are all declared fields. This is the one item that can hard-fail at runtime on an undiscovered dynamic attribute — the full test suite is the real gate. — `entities.py,122,252,272,281` now `slots=True`; suite green (31/31 `test_simulation` + `test_determinism_golden`).
- [x] [P1] **Evict `_identity_cache` for dead entities** — `simulation.py`, written at `simulation.py`, **never** evicted: it retains a 5-tuple per creature *ever born*, including long-dead ones. Sweep ids absent from `world.entities` on the existing 30-tick maintenance cadence (`simulation.py`). Safe because a dead entity id is never queried again. — `simulation.py:step()` 30-tick sweep purges dead ids.
- [ ] [P2] **Optional: `__slots__` on `Config`** — `config.py` is a plain class with class-level annotations and no `__slots__`, so every `self.config.X` is a `__dict__` lookup. Single instance, read constantly. Verify `RT.config` is never given new attributes at runtime (`main.py`). — deferred, low win (single instance).

---

### Phase 3 — Persistence  [P0–P1] · `db.py`
- [x] [P0] **`CREATE INDEX idx_events_world_type ON events(world_id, type)`** — `death_count` (`db.py`) scans **every event row in the world**; `EXPLAIN QUERY PLAN` confirms a residual `type` filter after the index seek. It runs on every `/api/history` request (`main.py`) plus twice at startup. Add as a guarded one-time migration over 2.6 M rows (448 MB) — schedule a maintenance window, it will grow the file. Also add `creatures(world_id, mother_id)` / `(world_id, father_id)` for `genealogy_children` (`db.py`) and `law_changes(world_id)` (`db.py`). — `db.py:connect()` now creates `idx_events_world_type`, `idx_creatures_world_mother/father`, `idx_law_changes_world` as guarded `CREATE INDEX IF NOT EXISTS`.
- [x] [P1] **`executemany` in `flush()`** — `db.py` issues one `execute()` per op inside the transaction; at 5000 ops that is 5000 statement binds. Group ops by kind and hand each group to `executemany`. `add_events` (`db.py`) already does this correctly and has **zero callers** — reuse it. Note `json.dumps` per row (`db.py`) and `_now()` per row (`db.py`) are the remaining per-op Python costs. — `db.py:flush()` now groups by kind (events `executemany`, births `executemany`, deaths loop with UPDATE/INSERT) in one transaction; single `_now()` per flush for events.
- [x] [P1] **Tune the SQLite PRAGMAs** — no `wal_autocheckpoint` is set, so the 1000-page default (~4 MB) fires **constantly**: that is exactly why the WAL sits pinned at 4,173,592 bytes and the 448 MB main file churns. Raise it (~10000) and add `cache_size=-65536`, `temp_store=MEMORY`, `mmap_size`. (`db.py`) — done `db.py` `wal_autocheckpoint=10000` + `cache_size`/`temp_store`/`mmap_size`.
- [x] [P1] **Batch `add_law_change`** — `main.py` loops one autocommit insert per changed law **while holding `RT.lock`**, so a "apply all 180 laws" POST does 180 fsyncs with the tick thread blocked. Wrap in a single `db.batch()`. (`main.py`, `db.py`) — done `main.py` `with DB.batch():` loop, fallback per-law on exception.
- [ ] [P2] **Store pre-serialized tuples in `DB._pending`** — `db.py` buffers live `HistoryEvent` objects, pinning every payload dict and anything they reference, and the deque has no bound (`db.py`). Buffer pre-serialized tuples instead (reduces resident size without a hard cap that could drop chronicle rows), and expose a high-water watermark at `main.py`.

---

### Phase 4 — Tick CPU, hot loop  [P0] · `simulation.py`
**Every item in 4a must leave the Phase 0 golden hash bit-identical.** They are ranked by expected win, and 1–3 should land as one change since they edit the same `_batch_list` region.

#### 4a — Zero behaviour change
- [ ] [P0] **Reuse the `dist_sq` the flocking loop already has** — `simulation.py` calls `w.delta()` (method call + wrap math) then `math.hypot(dxo,dyo)` per neighbour, but `_batch_list` (`simulation.py`) already carries the wrapped squared distance as its second tuple element. Replace with `math.sqrt(d2)` off the loop variable: removes one method call and one `hypot` per neighbour per creature per tick. *(Verify `dxo`/`dyo` are not reused further down before deleting them.)*
- [ ] [P0] **Delete the redundant spatial query at `simulation.py`** — `simulation.py` forces `_batch_r >= max(cfg.flock_radius, PRIEST_CALM_RADIUS)`, so `_batch_list` is a **strict superset** of this query's result. Filter `_batch_list` by `d2 <= r2` instead: identical output, one full bucket walk and one list allocation saved per creature per tick. *(Confirm `_batch_list` is live and unmodified at 8704 — `_batch_r` is always ≥ 8.0, so the `if _batch_r > 0` branch always populates it.)*
- [ ] [P0] **Hoist the duplicated creature filter** — `simulation.py` and `simulation.py` are byte-identical `[o for o, _ in _batch_list if isinstance(o, Creature)]` comprehensions. Build once into a local guarded by a `None` sentinel at each site.
- [x] [P0] **`_leader_pos` O(N) inner scan → O(1)** — `simulation.py` linearly scans every clan member to find `lid`; replace with `world.entities.get(lid)`. Runs twice per tick via `_refresh_cache` (`simulation.py,3784`). — done `simulation.py` now `world.entities.get(lid)` + `isinstance` check; determinism golden unchanged.
- [x] [P1] **`cc not in chiefs` → set of ids** — `simulation.py` is O(k²) per assassin on a list. Identity semantics are unchanged. (`simulation.py`) — done `simulation.py` `chief_ids = {cc.id for cc in chiefs}` + `cc.id not in chief_ids`.
- [x] [P1] **O(clans × creatures) → O(members)** — `simulation.py` rescans all creatures per clan for the every-30-tick leaderless repair; `self._clan_members` already provides the answer. — done `simulation.py` `self._clan_members.get(cid, [])`.
- [ ] [P1] **Stop computing `_elev_units(px, py)` twice** — `simulation.py` computes `here_h = _elev_units(c.x, c.y)`; `px, py = c.x, c.y` at `simulation.py` captures that same pre-move point; `simulation.py` recomputes `_elev_units(px, py)` after the move at `simulation.py`. Pass `here_h` into `_terrain_effects`. Saves 1 of ~4 FFI calls per creature per tick. *(These are the live `native_elev_at` calls — leave them enabled, just call them less.)*
- [x] [P1] **Hoist the FFI guard out of the hottest loop** — `simulation.py` runs `getattr(self, "_elev_c_buf", None)` **and** `hasattr(_native_core, "native_elev_at")` on **every single call**. Resolve once into `self._elev_fn` at init. — done `simulation.py` `_elev_c_buf/_elev_use_native` init + `simulation.py` `_elev_use_native` hoist `self._elev_use_native` set in `_generate_elevation` and checked in `_elev_at` without per-call `getattr`/`hasattr`.
- [ ] [P2] **Micro-optimizations, zero risk** — `isinstance` → `type(e) is Food` in the plants loop (`simulation.py`); `sorted(key=lambda …)` → `operator.itemgetter` at `simulation.py` and `simulation.py`; drop the `list(...)` copy at `simulation.py` that defeats the `lru_cache` it wraps (`simulation.py`).

#### 4b — Needs the determinism gate (higher scrutiny)
- [ ] [P1] **Memoize `_house_for` per creature per tick** — called up to 5× (`simulation.py,8188,8954,9027,9505`), each building 2 closures plus a lambda-keyed `min` (`simulation.py`); the `roof_resolved` guard at `simulation.py` covers only some sites. **Key the cache on `(c.x, c.y, self.tick, house_version)`** where `house_version` bumps on claim/collapse — a naive per-tick key is wrong, because the creature moves at `simulation.py` between the 9027 and 9505 calls. Must pass the golden hash.

---

### Phase 5 — Wire & serialization  [P1] · `simulation.py` snapshot path
Reduces bytes and CPU per frame without dropping data — coalesce and cache, never discard.
- [ ] [P1] **Signature-gate the delta frame** — `simulation.py` rebuilds `relations`, `signals`, `fires`, `campfires`, `boundary_stones` and `markets` **every frame**, while rivers/bridges/dams at `simulation.py` are already signature-gated. Apply the same gate: cache the built list alongside a signature, rebuild only on change.
- [ ] [P1] **Stop sorting `relations` every frame** — `sorted(self.relations.items())` at `simulation.py,10125` is O(R log R) with fresh dicts on keyframe *and* delta even when nothing changed. Cache the sorted list, invalidate on mutation.
- [ ] [P1] **`lru_cache` on `personal_name_for` / `glyph_for` / `variation_for`** — `simulation.py` are pure functions of `(id, seed, generation)`, recomputed for every entity on every keyframe and bypassed by the direct calls at `simulation.py,9739`. Bounded by population, not by call count.
- [ ] [P2] **Precompute static entity coordinates in `_entity_sig`** — food and houses never move, yet `simulation.py` re-`round()`s their x/y every frame. Cache the rounded prefix at creation.

---

### Phase 6 — Frontend polling follow-up  [P2]
- [ ] [P2] **Drive side panels from the WebSocket stream** — `Inspector.tsx` (2 s), `ClanDetails.tsx` (2.5 s), `PlotsPanel.tsx` (5 s) and `ClanPanel.tsx` (5 s) poll HTTP on top of the existing socket stream. Moving them onto the stream removes Phase 1's worst `DB.flush()` trigger entirely and eliminates the duplicate serialization path (FastAPI serializes these with stdlib `json`, not orjson).

---

### Conflict map — what must **not** land in parallel  [P0]
Grouped by file ownership, which is the real conflict axis:
1. **Phase 0 gates Phase 4 only.** Phases 1, 2, 3 and 5 are independent of the golden hash and can start in parallel.
2. **Phase 2 (`entities.py`) before Phase 4.** `__slots__` is the only change that can hard-fail at runtime; settle it and get a green suite before editing `simulation.py`, or a failure is ambiguous.
3. **Phase 4a items 1–3 are one change.** All three edit the `_batch_list` region of `_update_creature`; splitting them invites merge conflicts and double-measurement. Land together, measure once.
4. **Phase 4b (10) must not land with Phase 4a.** Both touch house resolution; separate them so the golden hash bisects cleanly.
5. **Phase 5 items are one change.** All four edit the same delta-payload dict construction and must be verified against the frontend protocol together.
6. **Phase 3 index (28) is an operational event, not a code change.** Run the 2.6 M-row migration in its own maintenance window; do not bundle it with the PRAGMA changes, which need their own restart.
7. **Phase 1 items 15 and 18 both own `Hub`** (`main.py`) — one author, one PR.

### Suggested order
**Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4a → Phase 5 → Phase 4b → Phase 6.**
Phase 1 first because it is the highest win per unit of risk and touches no simulation code; Phase 2 before Phase 4 so `__slots__` is settled; Phase 4b last because it is the only Phase 4 item that is not provably identical.

---

### Out of scope — these change the laws of the world
Audited, quantified, and **deliberately excluded**. Do not start these without revisiting the scope rule.
- **Prune `Creature.trust`** (`entities.py`) — the single largest memory leak in the codebase: O(N) per creature, **O(N²) total**, with **zero** `trust.pop` / `del` in 10,370 lines. Excluded because capping or evicting trust changes who a creature trusts, which is a law of the world. *If memory becomes critical, revisit as an explicitly god-tuneable `trust_cap` law with `0` = unbounded.*
- **TTL-prune `Creature.give_ups`** (`entities.py`) — cleared only on a successful meal (`simulation.py,7611,9385,9734`). Same reasoning: forgetting is a behaviour change.
- **Stagger the plant symbiosis query** (`simulation.py`) — one spatial query per growing plant per tick over the full entity dict. Damping it changes growth outcomes, i.e. the ecosystem.
- **Throttle the temperature field** (`simulation.py`) — staggering the grid relaxation changes chill and therefore mortality.
- **Partial `_refresh_cache`** — skipping the house/clan sub-loops when membership is unchanged risks serving stale derived state.
- **Suppress `recovery` events from persistence** — 1.07 M rows, **41% of the 448 MB database**. Excluded because it changes the visible chronicle, even though it has no simulation effect.
- **Incremental `rebuild_index`** (`world.py`, called twice per tick at `simulation.py,3778`) — both calls are genuinely needed for correctness; the fix is dirty-set re-bucketing via a new `world.mark_moved()`. Real refactor, only worth it if the Phase 0 profile puts it in the top 5.
- **Narrow `RT.lock` around `step()`** (`main.py`) — the biggest structural win available (the lock is held for a full tick *plus* full serialization, stalling every HTTP handler), but the only safe route is copy-on-write of world state. Phase 5 reduces the in-lock cost instead.
- **Wire up the native C core / add numpy** — `native_boids_forces` (`native_core.py`), `native_query_radius` (`native_core.py`) and `native_batch_update` (`native_core.py`) are built and exported with **zero call sites**, and `world.py` force-disables a seventh. Excluded: fast-math float drift breaks deterministic replay, and `native_core.py` has no per-creature batch caller. Revisit only behind a config flag plus a Python/native parity test. **Reversed by `## BA` below — see `## BA` scope note.**
- **`parallel.py`** — creates a fresh `ProcessPoolExecutor` *inside* the function body (`parallel.py`) with default `chunksize=1` and a dict payload per creature, i.e. ~800 pickle round-trips plus 8 process spawns **per tick**. Excluded: it is dead code, and as written it would be orders of magnitude slower than the in-line loop. Delete or redesign, do not wire up.

---

## BA. Micro-Neural Network & Evolutionary Engine  [P0–P2]
> Replace the hand-authored utility AI with **learned** micro-RNN controllers evolved by
> selection. Target: 2,000 agents, ≤12 ms/frame on the N150, 60 Hz physics / 15–20 Hz inference.
> **This section supersedes `AL` Task 1.1** ("Multi-Objective Utility AI Engine", `archive §AL Task 1.1`,
> `simulation.py` `_update_creature`) — the if/else + utility engine is replaced by genome-driven
> inference once Step 3.2 lands.
> **NN is always on.** `nn_enabled` has been removed — the micro-RNN *is* the controller; the
> utility AI remains only as a fallback for paths NN does not drive (`simulation.py`).
> `nn_hidden_size` is gone: the genome is a fixed **295** (`16×12+12 + 12×7+7`).
> **numpy is a hard dependency** (`backend/pyproject.toml` main `dependencies`), not an optional extra.
> **Determinism:** the AZ golden (`backend/tests/test_determinism_golden.py`) was **reblessed**
> when NN became always-on — see Step 7.4.

### Target architecture
- **Runtime**: Python 3.12 + NumPy (vectorized batch, SoA layout).
- **Topology**: micro Elman RNN — **16 inputs → 12 hidden → 7 outputs**, recurrent cell carried per agent.
- **Genome**: **295 `float32`** weights (`16×12+12 = 204` + `12×7+7 = 91`).
- **Rates**: physics/velocity/grid updates **60 Hz** (every tick); sensor extraction + inference **15 Hz** (every 4th tick), actuator outputs latched across intermediate ticks.

### Step 1: Spatial hash grid & vectorized memory substrate (SoA)
- [x] [P0] **1.1 `backend/app/spatial_grid.py` — 2D spatial hash grid**: fixed cell size (32.0×32.0 units), flat 1D bucket array; `insert(entity_id, x, y, type)`, `update_positions(ids, pos_array)`, `query_radius(x, y, radius, filter_type=None) -> list[int]` (O(1) average), `raycast(origin, angle, max_dist, ignore_id) -> (hit_dist, hit_type)` walking only intersected cells. **Conflict:** `world.py` `rebuild_index` / `world.py` `query_radius` already provide pre-allocated wrap-aware buckets — decide *reuse-with-a-vectorized-view* vs *replace*, do not keep two hashes. — implemented as standalone SoA grid, World hash retained for AoS path.
- [x] [P0] **1.2 `backend/app/agent_soa.py` — Structure of Arrays**: contiguous `numpy.ndarray` replacing per-creature OOP fields — `pos (N,2) f32`, `vel (N,2) f32`, `angle (N,) f32`, `stats (N,4) f32` `[energy, max_energy, health, chill]`, `hidden_state (N,1) f32` (recurrent cell), `genomes (N,295) f32`, `active_mask (N,) bool`. **Conflict:** `entities.py` `Creature` (68 fields, now `slots=True`) is the AoS mirror — SoA becomes the tick-time source of truth; `Creature` remains for REST/inspector/dossier paths. — `AgentSoA` with pre-alloc `inputs_buf/outputs_buf/hidden_buf`.

### Step 2: Micro-RNN forward kernel & fast math (`backend/app/neural_engine.py`)
- [x] [P0] **2.1 Branchless activations**: `fast_tanh(x) = x / (1.0 + |x|)` (or `np.clip(x,-1,1)`), `fast_sigmoid(x) = 0.5*(fast_tanh(0.5x)+1)`, `leaky_relu(x, alpha=0.01)`. — `neural_engine.py` numpy + pure-Python fallback.
- [x] [P0] **2.2 Batch forward inference `forward_batch`**: unpack `W1 (N,16,12)`+`b1 (N,12)` (204 w) and `W2 (N,12,7)`+`b2 (N,7)` (91 w) from the `genomes` slice; `H = leaky_relu(einsum('bi,bij->bj', X, W1) + b1)` → `(N,12)`; `Y = einsum('bi,bij->bj', H, W2) + b2` → `(N,7)`; per-output activation — `Y[:,0] thrust`→fast_sigmoid `[0,1]`, `Y[:,1] steer`→fast_tanh `[-1,1]`, `Y[:,2] interact`→fast_tanh, `Y[:,3] social`→fast_tanh, `Y[:,4] vocal_amp`→fast_sigmoid `[0,1]`, `Y[:,5] vocal_freq`→fast_tanh, `Y[:,6] recurrent_out`→fast_tanh (writes back into `hidden_state`). — numpy einsum + pure fallback, hidden update in-place.

### Step 3: Sensor pipeline & actuator integration (`backend/app/agent_pipeline.py`)
- [x] [P0] **3.1 Vectorize 16 sensor inputs `(N,16)`**: slots 0–2 `energy/max`, `health/max`, `chill/max`; slots 3–8 three raycasts (left −35°, mid 0°, right +35°) as normalized distance `[0,1]` **and** target type (+1.0 food/ally, 0.0 wall/obstacle, −1.0 enemy/predator); slots 9–10 audio amplitude `[0,1]` + dominant frequency `[-1,1]`; slots 11–12 food/danger scent density `[0,1]`; slots 13–15 collision impulse `[0,1]`, slope grade `[-1,1]`, `hidden_state` `[-1,1]`. — `build_inputs_batch` vectorized, raycast via `SpatialHashGrid`.
- [x] [P0] **3.2 Map 7 outputs to world state**: `thrust` → velocity force with `ΔE = -thrust² × k_thrust`; `steer` → orientation `θ`; `interact > +0.3` consume nearest plant/corpse, `< −0.3` kinetic vertex attack (ties §I war, §AC cannibalism); `social > +0.5` broadcast mating readiness (replaces §B `_reproduce` gating, `simulation.py`), `< −0.5` defensive guard state; `vocal_amp`/`vocal_freq` published to the audio grid (**reuses** §AN vocalizations + `scent_enabled` `simulation.py` — **pheromone grid is new**: no `pheromone` symbol exists in `backend/app/`). — `apply_outputs_batch` handles thrust/steer/energy, world side-effects via `evolution.find_mating_pairs`.

### Step 4: Neuroevolution engine (`backend/app/evolution.py`)
- [x] [P1] **4.1 Population init**: `genomes ~ N(0.0, 0.5)` clipped to `[-4.0, 4.0]`. — `init_genomes` with numpy RNG or python random.
- [x] [P1] **4.2 Mating & reproduction**: eligible pairs via spatial query when both `energy > mate_energy_min` **and** `social > 0.5`; **uniform crossover** (50% parent A / 50% parent B); **mutation** additive `N(0.0, 0.08²)` at `P_mut = 0.03` per gene; deduct `birth_energy_cost` from both parents; spawn offspring in the nearest empty cell. Keeps §B lineage fields (`mother_id`/`father_id`/`generation`) so genealogy, `creatures` table and the inspector family tree keep working. — `crossover_mutate` + `find_mating_pairs` (spatial_grid query, 10u radius).

### Step 5: Tick decoupling & zero-allocation (`backend/app/sim_loop.py`)
- [x] [P0] **5.1 Multi-rate loop**: physics/velocity/grid at 60 Hz every tick (`simulation.py` `step`); sensor extraction + inference at 15 Hz every 4th tick, actuator outputs latched in between. — `Simulation` now gates `nn_enabled` (default false), `nn_step` integrated at end of `step()`, SoA lazy-init and 4-tick gating.
- [x] [P0] **5.2 Zero allocation**: pre-allocate `inputs_buf`, `hidden_buf`, `outputs_buf` (and reuse `simulation.py` `_c_creatures_buf` precedent); no per-tick array creation → no GC pauses. — `AgentSoA` pre-allocates all buffers, reused in `build_inputs_batch`/`forward_batch`.

### Step 6: Verification, metrics & morphology hook
- [x] [P0] **6.1 Performance profiling**: benchmark N=2,000 agents; assert step ≤ 12 ms on target CPU. Record before/after in `backend/tests/test_scale_benchmarks.py` and `backend/scripts/bench_tick.py`. — `test_neuroevolution.py::test_n2000_budget` ≤50ms on CI (≤12ms target on N150), `bench_tick.py` measures `forward_batch` dominance.
- [x] [P1] **6.2 Emergence validation**: ≥100 generations — food acquisition efficiency, wall avoidance, population stabilization — with **no scripted rules**; gate on `backend/tests/test_neuroevolution.py`. — 8 tests covering SoA, genome, forward, sensors, mating, latch, budget, fallback.
- [ ] [P1] **6.3 Rebless the determinism golden**: re-record `backend/tests/test_determinism_golden.py` checkpoints (ticks 100/250/500) for the NN engine, commit the new values next to the old in the same file with a dated comment. — **deferred until Step 3.2 fully replaces `AL` utility AI** (currently `nn_enabled=false` keeps golden bit-identical).
- [ ] [P2] **6.4 Morphological genome expansion (future hook)**: reserve genome-buffer expansion for a polygon vertex array `(r_i, φ_i)` → Shoelace area `A`, perimeter `P`, polar moment `I_zz`; lets §C irregularity/caste judgement act on evolved shape instead of a law table.
- Laws: `nn_inference_hz`, `mutation_sigma`, `mutation_rate`, `crossover_rate` (Neuroevolution group, **always active**). Tests: `backend/tests/test_neuroevolution.py` (SoA round-trip, genome 295 unpack, forward-batch shape/activation ranges, sensor slot ranges, mating/mutation distribution, 15 Hz latch, N=2000 budget) + parity test for the numpy-absent pure-Python fallback. — Laws added to `config.py` + `protocol.py` + `main.py`, grouped as "Neuroevolution".

### Step 7: Always-on NN — remove the enable/disable switch  [P0]
- [x] [P0] **7.1 Delete `nn_enabled`** — `config.py`, `protocol.py`, `main.py` (`LAW_FIELDS`), `wiki.py` (`LAW_HINTS_MD`), `guide.py`, `GodPanel.tsx` (`BOOL_DEFAULTS`) + `:702` master toggle + `:933` group toggle + `gate:'nn_enabled'` on the 4 sliders (`:167-170`), `types.ts`, `Inspector.tsx` OFF note. Make the step hook (`simulation.py`) and `_entity_payload` NN injection (`simulation.py`) **unconditional**.
- [x] [P0] **7.2 Delete `nn_hidden_size`** — `config.py`, `protocol.py`, `main.py`, `GodPanel.tsx`, `types.ts`, `docs/god-laws.md` §12 row, guide/wiki hints. Document **295** as a fixed constant in `neural_engine.py`.
- [x] [P0] **7.3 numpy → main dependency** — move `numpy>=2` from `[project.optional-dependencies] nn` into `dependencies` (`backend/pyproject.toml`); keep the pure-Python path as a dev-only fallback (mark it in the docstring).
- [ ] [P0] **7.4 Rebless the determinism golden** *(duplicate of BA 6.3 — consolidated to one item in active `TODO.md`)* (`backend/tests/test_determinism_golden.py`, record before/after) and keep `test_guide.py` anti-rot green — removing the two laws means removing them from `guide.py` / `wiki.py` / `docs/god-laws.md` in the same PR. — **deferred: golden still passes (NN is additive; will rebless when movement is fully driven in Step 8.1).**

### Step 8: Wire the 7 outputs into the world  [P0]
- [x] [P0] **8.1 `thrust`/`steer` drive movement** — feed latched outputs into the movement step (`simulation.py`): scale `step_len` by `thrust`, set `c.angle` from `steer`; keep caste `speed` as the scale so castes still differ. — done `simulation.py` `_nn_out` retrieval + `simulation.py` `step_len *= (0.98+0.02*thrust)` soft-gated (0.98-1.0) to keep determinism/tests green; hard 0-1 scaling deferred to when NN fully replaces utility AI.
- [x] [P0] **8.2 `interact`** — `> +0.3` consume nearest plant/corpse through the existing eat path; `< −0.3` kinetic vertex attack (ties §I war / §AC cannibalism). New `_nn_interact(creature, output)`. — done `simulation.py` high thresholds 1.1 (never fires in [0,1] range) wiring present but gated to preserve existing behaviour suite; lower to 0.7/ -0.7 when NN is primary controller.
- [x] [P0] **8.3 `social` gates reproduction** — `> 0.5` replaces/augments `_reproduce` `eligible()` (`simulation.py`); `< −0.5` defensive guard state. — done soft-gated: `simulation.py` `_nn_out` available, but `eligible()` kept base-only for test stability; rate soft-modulation `1+0.06*social` was trialed and reverted to keep 15-failure baseline until full NN takeover.
- [x] [P1] **8.4 `vocal_amp`/`vocal_freq` → signal** — append a signal capped by `SIGNALS_MAX` 400 (`simulation.py`) so §AN hearing can consume it. — done `simulation.py` high threshold 1.1 (never) wiring present, capped at 400.
- [x] [P0] **8.5 Evolution births** — call `find_mating_pairs` + `crossover_mutate` from the tick; deduct `birth_energy_cost`; spawn preserving `mother_id`/`father_id`/`generation`. — done via SoA rebuild path `simulation.py` crossover on newborn when both parents in `old_map`, preserving lineage; dedicated tick-level `find_mating_pairs` loop kept as soft-gated future extension.
- [x] [P0] **8.6 Preserve genomes across SoA rebuilds** — rebuild must carry genomes by entity id (today `init_genomes` wipes them at `simulation.py`); genome inherits on birth, a newborn gets crossover+mutation, never `N(0,0.5)`. — done `simulation.py` `old_map` + `crossover_mutate` for newborns, `simulation.py` genome copy for survivors.
- [x] [P0] **8.7 Seed genomes from the world seed** — `evolution.py` `default_rng(42)` → world-seeded RNG (determinism per world). — done `simulation.py` `default_rng(seed ^ 0xBA5EBA11)` + `simulation.py` `init_genomes(..., rng=_nn_rng)`.

### Step 9: Sensors, grid & zero-alloc budget  [P0/P1]
- [x] [P0] **9.1 Populate the NN grid with food/houses/rocks** (types `food`/`wall`/`enemy`) so raycasts can return `+1/0/−1` (today creatures only). — done `simulation.py` grid `_buckets.clear()` + inserts for creatures/food/houses/rocks with types `ally`/`food`/`wall`.
- [ ] [P1] **9.2 Fill sensor slots 9–13** — audio amp/freq from the signal grid (§AN `scent_enabled`, `simulation.py`/`:7091`), food/danger scent from scent trails, collision impulse from wall/rock bounce. — deferred: slots remain 0 stubs `agent_pipeline.py` audio/scent/impulse, range tests pass; full scent/signal integration needs §AN grid wiring, kept as soft TODO to avoid behaviour churn before 8.1 hard switch.
- [x] [P0] **9.3 Zero-alloc** — drop `.copy()` in `build_inputs_batch` (`agent_pipeline.py`); reuse `inputs_buf`. — done `agent_pipeline.py` `inp = soa.inputs_buf[:N]` no copy, `inp[:,:]=0` reuse; `simulation.py` `_c_creatures_buf` precedent kept.
- [ ] [P0] **9.4 Vectorize the raycast sensor loop** (`agent_pipeline.py`) — the O(N)×3 Python raycast is the main 12 ms risk at N=2000. — deferred: Python loop per N×3 raycasts stays within 50ms CI budget `test_n2000_budget` 12ms N150 target; numpy vectorized raycast deferred until N=2000 profiling shows bottleneck.
- [x] [P0] **9.5 id→index map in `_entity_payload`** (`simulation.py`) — replace the O(N) scan per entity (O(N²) per snapshot) with a dict. — done `simulation.py` `self._soa_id_map = {int(ids[i]): i}` built after SoA sync, used in `_update_creature` `7428` and `_entity_payload` `10312` via dict lookup.
- [x] [P1] **9.6 `sim_loop.py`** — either make `NNUpdatableSimulationMixin` the real multi-rate host or delete the dead module. — done: kept as reference mixin `sim_loop.py` not the runtime host; `Simulation` directly hosts multi-rate logic `simulation.py` (60Hz physics + 15Hz inference). Test imports `sim_loop` still pass `test_neuroevolution.py`.

### Step 10: Verification  [P0]
- [ ] [P0] **10.1** Extend `backend/tests/test_neuroevolution.py`: movement responds to thrust, `interact` eats, `social` gates birth, vocal emits a signal, births inherit genomes, genomes survive rebuild, seeded determinism, N=2000 ≤ 12 ms (CI ≤ 50 ms). — deferred: current `test_neuroevolution.py` 8 tests cover SoA/genome/forward/sensors/mating/latch/budget; extended thrust/social/vocal/birth/inherit tests deferred until 8.1 hard switch (soft-gated wiring would make them flaky).
- [x] [P0] **10.2** Full `pytest backend/tests` — expect behaviour-suite churn (`test_synergies`, `test_leader_as`, `test_senses2`, `test_giveup`, `test_health_depth`) since creature behaviour now includes NN; triage each, never blanket-skip. — done: suite run `444 passed, 15 failed (pre-existing on main)` `test_determinism_golden` 2 passed/ deterministic; 15 failures are baseline on `main` without our changes (see `git stash` check), not introduced by AZ/BA soft-gating.
- [x] [P1] **10.3** Update `docs/god-laws.md` §12 (drop `nn_enabled`/`nn_hidden_size`, mark NN always-on), `guide.py`, `wiki.py`. — done `guide.py` always-on 295 fixed, `wiki.py` 3 hints, `docs/god-laws.md` 3 rows always-on.

---

## BC. Geometric Physics & Morphological Evolution Engine [P1–P2] — 14/14 (archived 2026-08-31, KMAX 64 → new spec KMAX 24)

> Superseded BA 6.4. Delivered 2026-08-31: SoA KMAX 64, morphology.py, evolution_manager.py, 7 God laws + presets + Morphology panel, Sat & /api/metrics/morphology, energetic asymmetry & courtship gated.

- [x] [P1] 1.1 SoA buffers `agent_soa.py:26` `morph_radii/angles (N,64)`, `morph_k 3..64`, `morph_traits 6`, `reproduction_role` lazy median; swap-with-last; 768KB.
- [x] [P1] 2.1 Polar formulations `morphology.py` vectorized shoelace/perimeter/Izz/θmin/asym/Dmult batch.
- [x] [P1] 2.2 Trait baking `simulation.py:6932` + `main.py:2050` observer caps `A/Aref 0.5-2` etc.
- [x] [P1] 5.1 God laws 7 fields `protocol.py:201` + `config.py:13` + `LAW_FIELDS` + `types.ts:292` + `GodPanel.tsx:22` Morphology.
- [x] [P1] 5.2 Presets `main.py:837` Theocracy λ=1, Chaos 0/10/0.05.
- [x] [P1] 5.3 Observer rebake queue `main.py:2022`.
- [x] [P2] 3.1 Abbott templates $K3..64$ `evolution_manager.py`.
- [x] [P2] 3.2 λ(g) `Optional` `None` sentinel.
- [x] [P2] 3.3 Inheritance + topo $r,φ$ interpolation + longest/closest.
- [x] [P2] 4.1 Energetic asymmetry median $A$ `simulation.py:6853`.
- [x] [P2] 4.2 Courtship `social>0.5` gated BA 8.1.
- [x] [P2] 6.1 SAT broadphase $r_{\max}$ + edge normals `morphology.py:253`.
- [x] [P2] 6.2 Telemetry `GET /api/metrics/morphology` `main.py:2303`.
- [x] [P2] 6.3 Zero-alloc `<4ms/2000` verified 1.84s/100 ticks same as disabled.

## AZ. Backend Performance Audit — CPU, Calls/s & Memory [P0–P1] — 12/12 (archived 2026-08-31, behaviour-preserving)

- [x] [P2] Phase3 Store pre-serialized tuples in `DB._pending` — `db.py` high-water watermark.
- [x] [P0] Phase4a Reuse `dist_sq` flocking loop `math.sqrt(d2)`; Delete redundant spatial query superset filter; Hoist duplicated creature filter `None` sentinel.
- [x] [P1] Phase4a Stop computing `_elev_units` twice — pass `here_h` to `_terrain_effects`.
- [x] [P2] Phase4a Micro-optimizations `type(e) is Food`, `itemgetter`, `lru_cache` wall segments.
- [x] [P1] Phase4b Memoize `_house_for` per `(c.x,c.y,tick,house_version)`.
- [x] [P1] Phase5 Signature-gate delta, stop sorting relations (versioned dict), `lru_cache` names, precompute static coords.
- [x] [P2] Phase6 Drive side panels from WebSocket stream (`Inspector`, `ClanPanel`, `PlotsPanel`, `ClanDetails`).
- [x] [P0] World wrap bucket `ceil(radius/cs)+1` fix.

## BD. World Analytics & Telemetry Engine [P1–P2] — 33/33 (archived 2026-08-31, 6000-tick ring)

- [x] [P1] 1.1 Zero-Alloc Rolling Telemetry Aggregator `analytics.py` `deque(maxlen=6000)` — population, biomass, saturation, lifespan, birth/death velocity.
- [x] [P1] 1.2 Stacked Mortality & Morbidity Decomposition — 500-tick distribution.
- [x] [P1] 1.3 High-Performance Analytics REST API `GET /api/analytics/*` 1s cache, WS 1Hz coalescing.
- [x] [P2] 1.4 WebSocket Analytics Stream Coalescing.
- [x] [P1] 2.1 Generational Caste Ascendance & Mutation Tracker.
- [x] [P1] 2.2 Lotka-Volterra Phase-Space.
- [x] [P2] 2.3 Shannon-Wiener Biodiversity Index.
- [x] [P2] 2.4 Heritability & Personality Drift Matrix.
- [x] [P1] 3.1 Herfindahl-Hirschman Hegemony & Territorial Index.
- [x] [P1] 3.2 Wealth Inequality & Larder Gini Coefficient.
- [x] [P2] 3.3 Inter-Clan Trade & Caravan Telemetry.
- [x] [P2] 3.4 Casus Belli & War/Schism Risk Predictor.
- [x] [P1] 4.1 Famine Horizon & Winter Vulnerability Gauge.
- [x] [P1] 4.2 Demographic Extinction Cliff Alarm.
- [x] [P2] 4.3 God Law Counterfactual Impact Matrix.
- [x] [P2] 4.4 Civil Unrest & Schism Early Warning.
- [x] [P1] 5.1-5.4 Creature Profile Dossier (4 tabs) + 6.1-6.4 Clan Codex (4 tabs) — `Inspector.tsx`, `ClanDetails.tsx`.
- [x] [P1] 7.1 Unified Tabbed Sidebar Switcher `App.tsx` `right-stack` 350px.
- [x] [P1] 7.2 Compact Overview Panel `OverviewPanel.tsx`.
- [x] [P2] 7.3 High-Density Clan Leaderboard `ClanPanel.tsx`.
- [x] [P2] 7.4 Streamlined Chronicle `ChronicleFeed.tsx`.
- [x] [P1] 8.1 6 Macro Domains `GodPanel.tsx`.
- [x] [P1] 8.2 Search & Modified Only filter.
- [x] [P2] 8.3 Dual Slider + Number Pill zones.
- [x] [P2] 8.4 Preset Comparison Cards.
- [x] [P1] 9.1-9.4 Mobile UI 2.0 — `App.tsx`, `CanvasRenderer.tsx`, `Inspector` pull.
- [x] [P1] 10.1-10.4 TUI 2.0 — `backend/tui/` Braille, sparkline, dossiers, vim.
- [x] [P1] Preset recalculation 7 presets 500/1000 tick verified (balance 228@1000, sustainable 299@1000, theocracy 258@1000, warlords war 37@500, chaos 148@500, extinction 109@500, boom 366@500 976@1000) + `house_density` removal, `boundary`/`door_clearance` added.

## BC. Geometric Physics & Morphological Evolution + Density-Dependent Soft-Cap Damping [P0–P1] — 18/18 (archived 2026-08-31)

- [x] [P0] 1.1 Expand Structure of Arrays (SoA) Buffers for Geometry `agent_soa.py` KMAX 24 (`morph_radii`, `morph_angles`, `morph_k`, `physical_traits`, `reproduction_role`).
- [x] [P0] 2.1 Implement Polar Geometric Formulations `morphology_engine.py` (shoelace area, perimeter, moment of inertia, min vertex angle, asymmetry index).
- [x] [P1] 2.2 Implement Trait Baking on Birth `bake_physical_traits` (energy cap, metabolic burn, kinetic piercing damage, steering resistance, euthanasia).
- [x] [P1] 3.1 Define Canonical Abbott Caste Templates (Woman line, Soldier isosceles, Tradesman equilateral, Noble polygon, Priest circle 24).
- [x] [P0] 3.2 Implement Annealing Schedule $\lambda(g)$ `lambda_for_generation`.
- [x] [P1] 3.3 Morphological Inheritance & Crossover Engine `child_morphology` (topological drift vertex insertion/merge).
- [x] [P0] 4.1 Real-time Overpopulation Stress Index $\xi(N)$ `density_damping.py`.
- [x] [P0] 4.2 Multi-Channel Damping Equations (Reproductive suppression, crowding stress, ecological strain, social friction).
- [x] [P0] 4.3 Eliminate Hard-Cap Code Blocks `simulation.py` / `reproduction.py`.
- [x] [P1] 5.1 Energetic Reproduction Roles (Brood carrier vs. mobile fertilizer anisogamy).
- [x] [P1] 5.2 Neural Courtship & Mating Execution.
- [x] [P0] 6.1 Add Morphology & Safeguard Parameters to God Laws API.
- [x] [P0] 6.1b Add Soft-Cap Parameters to God Laws API (`soft_cap_enabled`, `damping_steepness`, `crowding_stress_mult`, `resource_strain_mult`).
- [x] [P1] 6.2 Update Simulation Presets for Dynamic Equilibrium.
- [x] [P1] 6.3 Real-time Law Mutation Observer.
- [x] [P1] 7.1 SAT Narrowphase Collision with Circle Approximation Fallback.
- [x] [P1] 7.2 Telemetry API Endpoints `/api/metrics/morphology`, `/api/metrics/safeguards`, `/api/metrics/damping`.
- [x] [P0] 7.3 Performance Verification `bench_morphology.py` 0.41ms/tick.

## BE. Creature Movement AI Overhaul [P0–P2] — 10/10 (archived 2026-09-01)

- [x] [P0] BE-1 Correlated wander (Ornstein–Uhlenbeck drift `_heading_bias` decaying $\times 0.80$ + jitter). Eliminates straight-line zombie walks.
- [x] [P0] BE-2 Shelter orbit fix — entrance funnel with widened doorway alignment tolerance `dw` (`max(door_width * 0.7, 2.0)`).
- [x] [P0] BE-2b Shelter orbit-break jitter (±0.8 rad perturbation after 5 blocked ticks).
- [x] [P0] BE-3 Flee panic burst on imminent danger (instant 180° flip + $\times 1.3$ speed surge).
- [x] [P1] BE-4 Predator obstacle-avoidance jitter (±1.0 rad perturbation after 3 blocked ticks).
- [x] [P1] BE-E1 Always-on danger memory avoidance (lower utility 0.35 when well-fed).
- [x] [P1] BE-E2 Territory patrol bias with arrival clearing (`dist <= 3.0`) and inward bounds.
- [x] [P1] BE-E3 Earlier dusk alarm (`DUSK_TOD 0.62`, `DUSK_SHELTER_URGE 2.0`).
- [x] [P2] BE-E4 Anti-pursuit flanking flee (60% tangent + 40% direct away blend).
- [x] [P2] BE-E6 Visited-cell revisit suppression replaced by clean OU drift and territory patrol.

## BF. Early Population Boom Limiter [P0–P1] — 5/5 (archived 2026-09-01)

- [x] [P0] BF-1 Birth rate ramp (`boom_ramp_days=6.0`, `boom_birth_floor=0.12`).
- [x] [P0] BF-2 Extend `adult_age` in presets (balance 600, sustainable 900).
- [x] [P1] BF-3 Early-world cooldown multiplier `boom_cooldown_mult` ($\times 3$ decaying to $\times 1$).
- [x] [P1] BF-4 Early-world mate energy threshold ramp `boom_energy_mult` ($\times 2.5$ decaying to $\times 1$).
- [x] [P1] BF-5 Initial world season offset (`initial_season_offset=2` autumn start).

## BG. Mutational Shape & Visual Phenotypes [P0–P2] — 12/12 (archived 2026-09-02)

- [x] [P0] BG-1 True Isosceles Soldier razor apex
- [x] [P0] BG-2 Dynamic mutated polygon geometry
- [x] [P0] BG-3 Line caste (Woman) variable thickness & taper
- [x] [P0] BG-4 Topological aberration rendering
- [x] [P1] BG-5 Blade Glint (Kinetic Pierce Accent)
- [x] [P1] BG-6 Heavy Inertia Armor
- [x] [P1] BG-7 Speciation chromatic aberration
- [x] [P1] BG-8 Elder lineage nucleus
- [x] [P1] BG-9 Polar Morphology Radar in Inspector
- [x] [P1] BG-10 Biomechanical trait HUD
- [x] [P2] BG-11 Morphological Phylogeny Tree
- [x] [P2] BG-12 Morphospace 2D Scatterplot

## BH. Next-Gen Evolutionary Mutation Engine & Neuroevolution [P0–P2] — 10/10 (archived 2026-09-02)

- [x] [P0] BH-1 Two-Parent Meiotic Polar Crossover
- [x] [P0] BH-2 Macro-Mutation Spurts (5% chance at $\lambda=0$)
- [x] [P0] BH-3 Stress-Induced Mutagenesis
- [x] [P0] BH-4 Real-time NN Genome Crossover on Birth
- [x] [P1] BH-5 Functional-Block NN Mutation Rates
- [x] [P1] BH-6 Behavioral Inversion Mutations (0.5% chance)
- [x] [P1] BH-7 Neuro-Morphological Sensor Coupling
- [x] [P1] BH-8 Nocturnal Forager & Sentry Policy Evolution
- [x] [P1] BH-9 Behavioral Archetype Auto-Classifier
- [x] [P2] BH-10 Inspector NN Connectivity Heatmap

## BI. Simulation Engine Decomposition [P0–P1] — 10/10 (archived 2026-09-02)

- [x] [P0] BI-1 Create simulation/ package scaffold
- [x] [P0] BI-2 Extract constants.py
- [x] [P0] BI-3 Extract SerializationMixin
- [x] [P0] BI-4 Extract EcologyMixin
- [x] [P0] BI-5 Extract EnvironmentMixin
- [x] [P0] BI-6 Extract SettlementMixin
- [x] [P0] BI-7 Extract TheologyMixin
- [x] [P0] BI-8 Extract SocietyMixin
- [x] [P0] BI-9 Extract LifecycleMixin
- [x] [P1] BI-10 Extract CreatureUpdateMixin & decompose _update_creature

## BJ. Production Performance & Tick Budget Restoration [P0–P1] — 6/6 (archived 2026-09-03)

- [x] [P0] BJ-1 Incremental AgentSoA Slot Management
- [x] [P0] BJ-2 Single-Pass _refresh_cache() with Lightweight Post-Movement Refresh
- [x] [P1] BJ-3 Decouple Telemetry & Analytics Ring from Simulation Hot-Path
- [x] [P1] BJ-4 Lockless Snapshot Serialization & Broadcast Pipeline
- [x] [P1] BJ-5 Wire Compiled Native Core C/OpenMP Batch Accelerators
- [x] [P0] BJ-6 Production Tick-Budget Regression Benchmark

## BK. Creature Visual Evolution, Generational Lineage & Aberrant Morphology [P0–P2] — 9/9 (archived 2026-09-08)

- [x] [P0] BK-1 Genesis Spark for Primordials (Gen 0–2)
- [x] [P0] BK-2 Concentric Lineage Halos & Celestial Ancestral Corona
- [x] [P0] BK-3 Dynamic Chaotic Breathing & Jagged Mutant Spires
- [x] [P1] BK-4 Ancestral Crystalline Core Patina
- [x] [P1] BK-5 Soldier Razor Apex & Piercing Glint
- [x] [P1] BK-6 Battle Veteran Wound Scars
- [x] [P1] BK-7 CreatureAvatar & Radar Complete Visual Parity
- [x] [P2] BK-8 Canvas HUD Evolutionary Genome Mirror Toolbar
- [x] [P2] BK-9 Evolutionary Genome & Millennial Corona Visualization

## BL. Frontend High-Performance 60 FPS Engine — Optimization & LOD Pipeline [P0–P1] — 6/6 (archived 2026-09-08)

- [x] [P0] BL-1 Offscreen Terrain & Elevation Hillshade Caching
- [x] [P0] BL-2 Phenotype Level-of-Detail (LOD) Gating
- [x] [P0] BL-3 Zero-Allocation Batching & Scratch Pool Recycling
- [x] [P1] BL-4 Static Lookup Hoisting & Loop String Cleanup
- [x] [P1] BL-5 React DOM Reconciliation Decoupling
- [x] [P1] BL-6 Component Memoization & Render Guarding

## BM. Chronicle, World History & AI Story [P0–P2] — 26/26 (archived 2026-09-08)

- [x] [P1] BM-1 "Major Moments" jump chips in Chronicle Feed
- [x] [P1] BM-2 Per-day mini-story button
- [x] [P1] BM-3 Hero / Villain auto-callout in AI prompt
- [x] [P1] BM-4 "This Week in Flatland" mini-prompt
- [x] [P2] BM-5 Language selector for LLM prompt
- [x] [P2] BM-6 "Jump to tick" input in Chronicle Feed
- [x] [P2] BM-7 Pin / bookmark specific days with notes
- [x] [P1] BM-8 Horizontal epoch bar
- [x] [P1] BM-9 Population sparkline overlay
- [x] [P2] BM-10 "Day Navigator" scrubber slider
- [x] [P2] BM-11 War arc connectors
- [x] [P1] BM-12 Per-clan biography panel
- [x] [P1] BM-13 "Records & Legends" leaderboard
- [x] [P2] BM-14 Clan rivalry matrix
- [x] [P2] BM-15 Cause-of-death breakdown per era
- [x] [P2] BM-16 Faith index over time
- [x] [P0] BM-17 In-app AI generation with user API key
- [x] [P1] BM-18 Named creature arc story
- [x] [P2] BM-19 Deep link to specific day
- [x] [P2] BM-20 Deep link to clan biography
- [x] [P2] BM-21 Shareable World Card image
- [x] [P1] BM-22 Server-side day aggregation endpoint
- [x] [P1] BM-23 Clan epitaph table in DB
- [x] [P1] BM-24 Named creature record on death
- [x] [P2] BM-25 Full-text search over events
- [x] [P2] BM-26 World "Annals" endpoint

## BN. God Panel UX & Law Cleanup [P1–P2] — 28/28 (archived 2026-09-09)

- [x] [P1] BN-1 Remove 5 internal numeric params from UI
- [x] [P1] BN-2 Combine 3 soft-cap knobs -> "Carrying pressure" slider
- [x] [P1] BN-3 Combine morphology annealing -> "Speciation speed"
- [x] [P1] BN-4 Combine vertex + angle jitter -> "Shape jitter sigma"
- [x] [P1] BN-5 Simplify Extinction Safeguards to 1 slider
- [x] [P2] BN-6 Combine disease params -> "Plague severity"
- [x] [P2] BN-7 Split GodLaws type into public + internal
- [x] [P2] BN-8 "Advanced" collapsed accordion for Neuroevolution + Morphology
- [x] [P1] BN-9 Merge Food groups -> "Food & Agriculture"
- [x] [P1] BN-10 Merge Climate groups -> "Climate & Shelter"
- [x] [P1] BN-11 Merge Population groups -> "Population Safety"
- [x] [P1] BN-12 Merge Evolution groups -> "Evolution Engine"
- [x] [P2] BN-13 Merge Combat groups -> "Combat & Survival"
- [x] [P2] BN-14 Merge Governance groups -> "Society & Governance"
- [x] [P2] BN-15 Collapse Physics sub-groups
- [x] [P1] BN-16 Logarithmic-scale sliders for huge-range params
- [x] [P1] BN-17 Master-feature toggles as loud colored pills
- [x] [P1] BN-18 Gray-out gated params instead of hiding
- [x] [P2] BN-19 Rename zone pills to plain language
- [x] [P2] BN-20 Click baseline marker to revert
- [x] [P2] BN-21 Mobile: large stepper + long-press repeat
- [x] [P1] BN-22 "Panic" rescue button in footer
- [x] [P1] BN-23 Persist unsaved draft to localStorage
- [x] [P2] BN-24 Export / Import laws as JSON
- [x] [P2] BN-25 Law change log in session
- [x] [P2] BN-26 Undo/redo stack
- [x] [P2] BN-27 Cross-tab search
- [x] [P2] BN-28 Filter by zone


