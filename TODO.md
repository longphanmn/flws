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
- [x] [P0] **BQ-1 Desynchronize Season & Age Cycles & Database Migration** (`config.py` / `main.py` / `environment.py`)
  - Set `season_length` to coprime / natural multiples relative to `age_length` (5 seasons per age: `season_length = 2400` ticks = 2 days per season across `age_length = 12000`).
  - Added automatic database migration in `_restore_law_state()` to modernize legacy `season_length: 12000` from persisted `flatworld.db`, unlocking an 80-minute (48,000-tick) non-repeating super-cycle across all 16 $(Season, Age)$ environmental combinations.
- [x] [P0] **BQ-2 Smooth Astronomical Midpoint Interpolation & Seasonal Capacity** (`constants.py` / `environment.py` / `ecology.py`)
  - Replaced narrow 600-tick boundary windows with full-cycle continuous midpoint cosine interpolation in `_smooth_age_mult()`, ensuring zero flat plateaus across the 12,000-tick era.
  - Introduced `_smooth_season_cap_mult()` providing continuous $\pm 12\%$ solar expansion and contraction of environmental carrying capacity through the seasons.
- [x] [P0] **BQ-3 Dynamic Food Regrowth Flux & Grazing Depletion** (`ecology.py` / `core.py`)
  - Replaced per-tick hard equality enforcement (`len(foods) == target`) with a rate-limited sprout germination flux proportional to available carrying capacity and seasonal targets.
  - High creature density now genuinely overgrazes and depresses wild food levels, driving organic Lotka-Volterra predator-prey/resource oscillations.
  - Retained instantaneous divine decree adjustments when God changes food laws via API.
- [x] [P0] **BQ-4 Multi-Harmonic Carrying Capacity & Smooth Logistic Soft-Cap** (`lifecycle.py` / `core.py` / `density_damping.py`)
  - Replaced the rigid thermostat wall (`math.exp(-10 * xi)`) with smooth logistic easing between carrying capacity and maximum population.
  - Unified carrying capacity calculations across `lifecycle.py` and `core.py` combining age and seasonal solar multipliers (`carrying * cap_mult * season_cap_mult`) so population naturally breathes and undulates around carrying capacity.
- [x] [P1] **BQ-5 Live Telemetry, Test Suite & Health Dashboard Verification**
  - Verified full test suite passes across 522+ tests (0 failures).
  - Expanded regression test suite `test_continuous_dynamics.py` covering solar carrying capacity, mid-era continuous variation, and non-plateau dynamics.

---

## §BQ-6 Fix Structural Population Bouncing (Moving Setpoint + Cohort Resonance) — 2026-09-22

> **Context**: Live theocracy world (raw K=380) bounced N 218↔519 with ~23 sign reversals in 2h; food oscillated in phase (181↔565). Instrumented 24k-tick run: `corr(food, K_set)=0.99`, `corr(pop, food)=0.77`, CV(N)=0.29, old-age deaths bursty (max 100-tick bin / median = 7.3), starvation only 14% of old-age+starvation deaths. Two independent brainstorms plus the probe ruled out Lotka–Volterra food coupling (regrowth ~10/tick vs consumption ~0.26/tick).

- [x] [P0] **BQ-6.1 Flatten the setpoint** (`lifecycle.py` / `core.py` / `main.py`)
  - Removed `_smooth_age_mult(AGE_CAP_MULT) × _smooth_season_cap_mult` from both `carrying` and `max_pop`; effective K is now the fixed raw K (380 theocracy). The food target keeps its seasonal/era flavour.
  - Replaced the `pop >= max_pop` brick wall with the existing smooth cosine fertility room only.
- [x] [P0] **BQ-6.2 Desynchronize cohorts** (`lifecycle.py`)
  - All four birth sites now jitter `lifespan` by U(0.7, 1.3); post-birth `repro_cooldown` jittered U(0.7, 1.3) at every parent assignment.
- [x] [P0] **BQ-6.3 Hysteresis + release slew** (`density_damping.py`)
  - `compute_xi` now starts partial damping at `0.85 × K` (not the hard K edge).
  - `DensityDampingEngine` releases xi exponentially toward its target with τ = 300 ticks instead of snapping to 0; onset stays immediate. Decay is applied at most once per tick so `step()` + `_reproduce()` cannot double-count.
- [x] [P1] **BQ-6.4 Hygiene** (`safeguard_engine.py` / `serialization.py` / `main.py`)
  - One shared K: safeguard relief and telemetry now use `effective_carrying_capacity`, matching the soft-cap.
  - Theocracy preset no longer pins `damping_steepness=4.0` / `crowding=0.25` / `resource=0.9`; it follows config defaults 7.0/1.0/2.0. A boot migration rewrites only the exact legacy tuple from persisted law state so the tuning actually ships.
- [x] [P0] **BQ-6.5 A/B verification** (`scripts/preset_experiment.py --osc-run/--osc-compare`)
  - 120k ticks, 20k burn-in, seeds 42/123/999, theocracy A (baseline) vs B (fixed); gates on CV(N), amplitude, dN/dt reversals, old-age burstiness, min-N floor.

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
