# Flatland — World Simulation TODO

[![GitHub Repo](https://img.shields.io/badge/GitHub-longphanmn%2Fflws-181717.svg?logo=github)](https://github.com/longphanmn/flws)

The Sphere model: The Sphere (God) sets **laws** from Spaceland, never touches individual creatures. Everything else emerges.  
Repository: [https://github.com/longphanmn/flws](https://github.com/longphanmn/flws)  
Legend: [P0] foundational · [P1] core Flatland identity · [P2] flavor/observability · `- [ ]` open · `- [x]` done · *parked* = decided, not pending

> **Active backlog only.** Completed roadmaps §F–§BP (772 items) → [`docs/roadmap-archive.md`](docs/roadmap-archive.md). This file tracks **open items in §BQ** + 10 parked.

---

## §BQ Ecological Realism & Continuous Population Dynamics — Active Backlog (5/5 done) — 2026-09-17

> **Context**: Live production telemetry on `/healthz` and the Health Dashboard (`/health/`) revealed an unnatural digital step-function pattern where population and food lock rigidly onto 3–4 discrete numbers (~240, ~325, ~415, ~480 pop; 251, 281, 361, 475 food) for 20 minutes (12,000 ticks) straight, then abruptly jump.
> **Root Causes**:
> 1. **Phase-Locking**: `season_length == age_length == 12000` with 4 seasons and 4 ages permanently locks Golden $\to$ Spring, Ice $\to$ Summer, Chaos $\to$ Autumn, Plague $\to$ Winter.
> 2. **Instant Guillotine Food Law**: `_enforce_food_law()` instantly spawns or deletes plants on every single tick to force `len(foods) == target`, eliminating resource depletion, grazing pressure, and Lotka-Volterra dynamics.
> 3. **Carrying Capacity Clamping**: `pop >= carrying * 1.15` blocks births abruptly like a brick wall while instant food replenishment drives creatures directly into the softcap ceiling.
> 4. **Step Transitions**: Environmental multipliers jump instantly at tick boundaries rather than smoothly transitioning across days/seasons/ages.

### Ecological Realism & Continuous Dynamics [P0–P1]
- [x] [P0] **BQ-1 Desynchronize Season & Age Cycles** (`config.py` / `main.py` / `environment.py`)
  - Set `season_length` to coprime / natural multiples relative to `age_length` (e.g. 5 seasons per age: restoring `season_length = 2400` ticks = 2 days per season across `age_length = 12000`).
  - Ensures every Age traverses different seasons over time (e.g., Ice experiences winter, spring, and summer) unlocking all 16 $(Season, Age)$ environmental permutations.
- [x] [P0] **BQ-2 Smooth Seasonal & Age Astronomical Transitions** (`constants.py` / `environment.py` / `ecology.py`)
  - Replaced discrete 1-tick step multiplier cliffs (`SEASON_FOOD_MULT`, `AGE_FOOD_MULT`, `AGE_CAP_MULT`) with continuous astronomical solar curve interpolation (cosine/smoothstep easing over cycle boundaries).
  - Eliminated instantaneous shocks to ecosystem carrying capacity and food targets.
- [x] [P0] **BQ-3 Dynamic Food Regrowth Flux & Grazing Depletion** (`ecology.py` / `core.py`)
  - Replaced per-tick hard equality enforcement (`len(foods) == target`) with a rate-limited sprout germination flux proportional to available carrying capacity and seasonal targets.
  - High creature density now genuinely overgrazes and depresses wild food levels, driving organic Lotka-Volterra predator-prey/resource oscillations.
  - Retained instantaneous divine decree adjustments when God changes food laws via API.
- [x] [P0] **BQ-4 Organic Density Damping & Soft-Cap Smoothing** (`lifecycle.py` / `density_damping.py`)
  - Replaced the rigid hard-stop birth clamp (`pop >= carrying * 1.15`) with continuous logistic carrying pressure and exponential decay damping room.
  - Allowed natural metabolic energy availability, reproduction cooldowns, and gentle density damping to govern birth rates so population breathes and fluctuates organically around carrying capacity.
- [x] [P1] **BQ-5 Live Telemetry, Test Suite & Health Dashboard Verification**
  - Verified full test suite passes with 519 passing tests (0 failures).
  - Added dedicated regression test suite `test_continuous_dynamics.py` covering solar curve continuity, age blending, desynchronization, smooth carrying capacity, and bounded regrowth flux.

---

## Parked — decided, not pending (10 items)

These are documented decisions with rationale, not overdue work.

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
1. **BQ-1 Desynchronization before BQ-2 Smoothing** — Base cycle lengths and phase offsets must be settled before calibrating astronomical easing curves.
2. **BQ-3 Food Regrowth Flux before BQ-4 Damping Smoothing** — Grazing feedback and natural food capacity must be active before tuning birth damping room.
3. **Preserve God Laws API contracts** — `food_count`, `carrying_capacity`, `season_length`, `winter_food_mult` remain god-settable parameters; smoothing and regrowth act on internal effective targets.
4. **Pass full test suite** — Every step must maintain 100% pass rate across the 513 existing test cases.

---

## Archive index
§F Infrastructure — Database · §A Life cycle · §B Reproduction · §C Irregularity & caste · §D Health & disease · §E Environment · §G God-law & observability · §H Food ecosystem · §I Society · §J Creature profile · §K Documentation · §L Shelter · Cross-system synergies · §W World generation · §N New frontiers · §O Ecosystem depth · §P Clan depth · §Q Creatures 2.0 · §R Weather as life · §S WorldBox inspirations · §T Sustainability & performance · §U Mobile UI/UX · §V Clan founding redesign · §X Fixes · §X2 Communication II · §Y UI polish · §Z Terminal frontend · §AA Performance round 2 · §AB Politics · §AC Desperation cannibalism · §AD OS-log persistence · §AE Food decay · §AF Performance & Massive Scale · §AG Autonomous Evolution · §AH Energy Dynamics · §AI TUI Feature Parity · §AJ Next-Gen Performance (3 phases) · §AK Clan Lifecycle · §AL Creature Cognitive Agency · §AM Food & Agriculture · §AN Communication, Language & Diplomatic · §AO Nocturnal Perils · §AP Unified Theology · §AQ 2D Physics · §AR Creature Senses · §AS Clan Leader Importance · §AT Four Immediate Issues · §AU Performance Optimizations · §AV Frontend & TUI Performance · §AW Emergency 1–2 TPS · §AX High-Density 20 TPS · §AY Multi-Core Engine · §AY2 World Simulation Presets · §AZ Backend Performance Audit · §BA Micro-Neural Network · §BC Geometric Physics & Morphological Evolution · §BD World Analytics & Telemetry Engine · §BE Creature Movement AI Overhaul · §BF Early Population Boom Limiter · §BG Mutational Shape & Visual Phenotypes · §BH Next-Gen Evolutionary Mutation Engine & Neuroevolution · §BI Simulation Engine Decomposition · §BJ Production Performance & Tick Budget Restoration · §BK Mutational Accents, Avatar Parity & Map Lenses · §BL Frontend High-Performance 60 FPS Engine · §BM Chronicle, World History & AI Story · §BN God Panel UX & Law Cleanup · §BO Production Performance Optimization & Zero-Allocation Engine · §BP Tri-Repository Architectural Split

Full completed content → [`docs/roadmap-archive.md`](docs/roadmap-archive.md)
