# Flatland — World Simulation TODO

[![GitHub Repo](https://img.shields.io/badge/GitHub-longphanmn%2Fflatland-181717.svg?logo=github)](https://github.com/longphanmn/flatland)

The Sphere model: The Sphere (God) sets **laws** from Spaceland, never touches individual creatures. Everything else emerges.  
Repository: [https://github.com/longphanmn/flatland](https://github.com/longphanmn/flatland)  
Legend: [P0] foundational · [P1] core Flatland identity · [P2] flavor/observability · `- [ ]` open · `- [x]` done · *parked* = decided, not pending

> **Active backlog only.** Completed roadmaps §F–§BN (740 items) → [`docs/roadmap-archive.md`](docs/roadmap-archive.md). This file tracks **open items in §BO** + 8 parked.

---

## §BO Production Performance Optimization & Zero-Allocation Engine — Backlog (7/8) — 2026-09-11

> **Context**: Live production profiling (PID 1644998, 192.168.1.21) revealed tick latency spikes up to **80–136ms** with overruns when population expands towards 350–400 creatures (against the 100ms budget for 10.0 TPS). Bottlenecks:
> 1. Signal hearing loop in `creature_update.py` recomputing tick constants, allocating 9,000+ tuples for dict grid queries, sorting via Python lambdas, and allocating generator expressions.
> 2. `world.py` `query_radius` hardcoded `+ 2` padding inspecting 25–49 buckets even for tiny radii.
> 3. Redundant `w.query_radius_with_dist_sq` in panic contagion instead of reusing batched query.
> 4. `ambient_at` floating divisions and `_totem_mult` per-creature recomputations.
> 5. Frontend Canvas2D `bgMutatedPoints` allocating ~16,000 arrays/frame (~1,000,000 allocations/sec).
> 6. Frontend `websocket.ts` allocating 900-element `Array.from(this.entitiesMap.values())` on every delta frame.
> 7. Production server running Vite in development mode instead of optimized production build.
>
> **Constraint**: Zero changes to world simulation laws, formulas, physics, or game balance.

### Backend Simulation & Spatial Optimizations [P0–P1]
- [x] [P0] **BO-1 Signal Hearing Loop Overhaul** (`creature_update.py` / `core.py`)
  - Hoist tick invariants (`max_hear_d`, `max_hear_d2`, `sig_r2`, `_rx`, `snd_boost`, `wx_s`, `wy_s`) to tick-level.
  - Convert `_signal_grid` to a flat 1D list of buckets indexed by `cy * cols + cx`, eliminating ~9,000 tuple allocations and dict lookups per tick.
  - Sort candidate signals with native C tuple comparison (`_cand.sort()` without lambda).
  - Eliminate generator expressions (`for _, sg in _cand:` direct unpack).
  - Reuse computed wrapped coordinates (`dxw, dyw`) in downwind calculations instead of re-calling `w.delta()`. Skip `math.sqrt` when upwind.
- [x] [P0] **BO-2 Spatial Hash Grid Accurate Cell Bounds** (`world.py`)
  - Compute exact cell span `x0_cell = int(math.floor((x - radius) * inv_cs))`, `x1_cell = int(math.floor((x + radius) * inv_cs))` (modulo cols). Reduces checked buckets from 25 to 1–4 buckets for small radii (6x to 25x reduction in bucket scans).
  - Fix toroidal distance early reject: `if edx > half_w: edx = w - edx` so `edx` remains non-negative for early boundary rejection before squaring.
- [x] [P1] **BO-3 Eliminate Redundant Spatial Query in Panic Check** (`creature_update.py:1518`)
  - Reuse the already computed `_batch_list` (which covers `max(cfg.flock_radius, PRIEST_CALM_RADIUS)`) instead of issuing a second spatial hash query.
- [x] [P1] **BO-4 Precomputed Totem Multipliers & Fast Ambient Mapping** (`core.py` / `environment.py`)
  - Precompute `_totem_mult` for all active clans once during `_refresh_cache()` into `_totem_mult_cache`.
  - Precompute scale reciprocals `_inv_width_temp_cols` and `_inv_height_temp_rows` in `environment.py` so `ambient_at` avoids division. Memoize `ambient_at(c.x, c.y)` per creature.

### Frontend Rendering & Transport Optimizations [P0–P1]
- [x] [P0] **BO-5 Zero-Allocation Canvas2D Path Tracing** (`renderCore.ts`)
  - Implement `bgTraceMutatedPath(ctx, ...)` and `bgTraceSoldierRazor(ctx, ...)` that trace directly into Canvas2D context via `ctx.moveTo` / `ctx.lineTo`, eliminating ~16,000 array allocations per frame.
  - Add static scratch pool for point calculations where explicit coordinates are needed.
- [x] [P1] **BO-6 WebSocket Entity List Recycling** (`websocket.ts`)
  - Cache and reuse `entitiesList` on delta frames where entity membership did not change, eliminating 900-element `Array.from()` allocations at 10 Hz.
- [x] [P0] **BO-7 Production Frontend Build & Preview Mode** (`vite.config.ts` / `deploy.sh`)
  - Configure `preview` in `vite.config.ts` with API and WebSocket proxies.
  - Update `deploy.sh` to run `npm run build` and launch `./node_modules/.bin/vite preview --host 0.0.0.0 --port 5173`.

### Verification & Production Deployment [P0]
- [ ] [P0] **BO-8 Verification, Production Deploy & Live Profiling**
  - Run the full 513-test suite to guarantee zero regression.
  - Run `bench_tick.py` and `test_tick_budget.py` (both 170 and 360 pop) to measure latency improvements.
  - Deploy to production via `./deploy.sh` (preserving world state).
  - Profile production server live with `py-spy` and query `/healthz` to verify sustained 10.0 TPS and reduced CPU.

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
