# Flatland — World Simulation TODO

[![GitHub Repo](https://img.shields.io/badge/GitHub-longphanmn%2Fflws-181717.svg?logo=github)](https://github.com/longphanmn/flws)

The Sphere model: The Sphere (God) sets **laws** from Spaceland, never touches individual creatures. Everything else emerges.  
Repository: [https://github.com/longphanmn/flws](https://github.com/longphanmn/flws)  
Legend: [P0] foundational · [P1] core Flatland identity · [P2] flavor/observability · `- [ ]` open · `- [x]` done · *parked* = decided, not pending

> **Active backlog only.** Completed roadmaps §F–§BP (772 items) → [`docs/roadmap-archive.md`](docs/roadmap-archive.md). This file tracks §BR (chronicle DB) + §BQ (10/10 completed) + 10 parked.

---

## §BR Chronicle DB — reclaim size, restore read/write performance — 2026-10-01

> **Context**: `flatworld.db` reached **5 GB after ~2000 sim-days**; `/api/history` latency and tick rate degraded with it. `config.history_max = 200`, so the in-memory chronicle holds only 200 events — **SQLite is the only chronicle** and nothing could simply be thrown away. Decisions taken: filter noise rather than prune (milestones stay forever), offline rebuild authorised, all three symptoms (API latency, tick-rate decay, disk pressure) in scope.
> **Measured on** a purpose-built 2.7M-row / 542 MB replica with the pre-§3.5 schema (4 KB pages, `created_at`, `AUTOINCREMENT`, the old 2-column indexes), before and after on the same data.

- [x] **[P0] BR-1 Tiered chronicle, not retention** (`db.py` `EVENT_TIERS` / `classify()` / `NOISE` ring)
  `MILESTONE` always durable · `SAMPLED` 1 in `CHRONICLE_SAMPLE_EVERY=10` with `NOISE_PER_TICK_CAP=3` per tick · `NOISE` (bloom, wither, culture, rivalry, peace_envoy) never touches SQLite and lives in a 5000-entry RAM ring that `pending_events()` still serves to `/api/history`. The map is a **denylist** over the 49 types `HistoryEvent` can emit, so a new type stays durable until deliberately reclassified. This bounds the *growth rate*; nothing is deleted.
- [x] **[P0] BR-2 `event_clans` side table** — clan ids extracted once in Python where the payload is already a dict. `WITHOUT ROWID` with primary key `(world_id, clan_id, event_id)`: one b-tree instead of a rowid table plus a duplicate covering index (**measured 21.9 MB → 6.3 MB on 500k side rows**, same read plan, ~12% slower writes). `history(clan_id=N)`: **13.24–20.75 ms → 1.07–1.18 ms (≈17x)**, plan `SEARCH ec USING PRIMARY KEY`.
- [x] **[P0] BR-3 `world_stats` death counter** — bumped inside the transaction that writes the death rows, so it can never disagree with them and rolls back with them. `death_count()`: **9.9–14.9 ms → 0.01 ms**. A SQL trigger was measured at ~10x the write cost and rejected.
- [x] **[P0] BR-4 Lean schema + pragmas** — `events.created_at` dropped (12.6% of bytes; only the wiki mentioned it), `AUTOINCREMENT` dropped, `PRAGMA page_size=16384` before the first write, `mmap_size` clamped to `min(1 GiB, RAM/4)`, `analysis_limit` + `ANALYZE`. A legacy file is rebuilt in place on `connect()` (backfilling `event_clans` and `world_stats`); above 500k rows `connect()` refuses and names the offline tool instead of copying gigabytes at startup.
- [x] **[P0] BR-5 Windowed `q=`** — the candidate set is an id range off `MAX(id)` (`id > MAX(id) - Q_SEARCH_WINDOW`, 50 000) and the pattern is escaped, so `%` and `_` are text. On 500k rows: selective hit **193 ms → 12.2 ms**, no hit 179 ms → 10.8 ms, broad match unchanged at 0.6 ms.
- [x] **[P1] BR-6 `GET /api/diagnostics/db-census`** — rows, B/row, bytes per type and per index (`dbstat`), per-world rows/deaths, `page_size`, `needs_rebuild`, planner stats, WAL size, plus `tiers[].types` (the configured membership) and `byte_sinks` (durable types ranked by byte cost). This is the instrument for re-cutting the tier map from production data instead of the headless inference it was drafted from.
- [x] **[P0] BR-7 `scripts/migrate_db.py`** — offline rebuild: `VACUUM INTO` backup → fresh 16 KB file built from the live `_SCHEMA` → stream every table (columns matched by name) → `event_clans` + `world_stats` in the same pass → deferred index creation → `ANALYZE` → `VACUUM` → verify per-world counts, an events checksum, side-table orphans and a 200-row `json_extract` cross-check → atomic rename. The original is never modified; `--dry-run`, `--replace`, `--bench`.

### Measured outcome (2.7M rows, 542.5 MB → 485.2 MB, **-10.6%**, 179.7 B/row, zero free pages, verified)

| Path | Before | After |
| --- | --- | --- |
| `history(clan_id=N, 200)` | 13.2–20.8 ms | **1.07–1.18 ms** |
| `death_count()` | 9.9–14.9 ms | **0.01 ms** |
| `history(major, 2000)` | 11.5–19.0 ms | 16.4–18.4 ms (≈2–4 ms SQL + ~11 ms building 2 000 dicts) |
| `history(plain, 500)` / `(entity_id, 500)` / `q=` | — | unchanged (same-SQL control: 10.6 vs 11.3 ms) |
| `wal_checkpoint(TRUNCATE)` | 2.6 ms | 1.4 ms steady (**one-time ~200 ms first checkpoint**: WAL init) |
| `/api/history` p95 (300k rows) | — | **2.4 ms** (clan-filtered 1.8 ms) |
| writer drain, 50k durable events | 237 ms | **412 ms** (+3.5 µs/event: the side table + counter) |

- [x] **[P0] BR-8 Three bugs the replica measurement exposed** (each with a failing test first)
  1. `connect()` dropped and recreated all three `events` indexes **on every open** — SQLite stores index DDL without the `IF NOT EXISTS` clause, so the shape comparison never matched. Dropping an index deletes its `sqlite_stat1` rows, so the planner lost its statistics: the clan filter went 0.3 ms → 468 ms after one reconnect, and a 5 GB file would have paid an index rebuild per start. Fixed by comparing the part of the DDL after `ON`.
  2. The rebuild inserted rows with the indexes already in place, leaving **92.7 MB of freelist pages** (16% of the file). Deferred index creation + a final `VACUUM` → zero free pages, −96 MB.
  3. `connect()` raised `sqlite3.OperationalError` when another connection held the write lock. The guarded index/`ANALYZE` steps are optimisations of an already-usable schema, so they now record into `schema_warnings` (reported by the census); the schema rebuild path still raises.
- [ ] **[P1] BR-9 Run the census on the real 5 GB file, then re-cut the tier map** — §BR's `SAMPLED`/`NOISE` membership is an *inference* from a headless 8000-tick run (≈180 MB extrapolated, ~28x short of the reported 5 GB), so the production event mix is still unknown. `GET /api/diagnostics/db-census?deep=true` → `byte_sinks` names the durable types worth re-classifying. Until then, treat `CHRONICLE_SAMPLE_EVERY` / `NOISE_PER_TICK_CAP` as unverified defaults.
- [ ] **[P1] BR-10 `connect()` above the ceiling is a startup wall** — a >500k-row legacy file refuses in place and needs the offline tool. Decide whether that ceiling should auto-run the rebuild instead of refusing.
- [ ] **[P2] BR-11 `/api/clans/{id}/history` still paginates the 200-event deque**, not the durable chronicle. Latent limitation, unchanged by §BR and still worth fixing now that the clan filter is a 1 ms covering-index lookup.

---

## §BQ Ecological Realism & Continuous Population Dynamics — (10/10 done) — 2026-09-17 to 2026-09-22

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
  - *(Note: Modulation of carrying capacity via cap_mult × season_cap_mult in BQ-4 was superseded in §BQ-6.1; swinging the carrying setpoint caused structural bouncing. BQ-6.1 flattened K to a fixed setpoint, keeping continuous seasonal variation on food supply only.)*
- [x] [P1] **BQ-5 Live Telemetry, Test Suite & Health Dashboard Verification**
  - Verified full test suite passes across 523+ tests (0 failures).
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
- [x] [P0] **BQ-6.5 A/B verification harness & gates** (`scripts/preset_experiment.py --osc-run/--osc-compare`)
  - Verification harness: `scripts/preset_experiment.py --osc-run --world A|B --seed <seed> --ticks 120000 --burn-in 20000 --out <path>` and `--osc-compare <paths...>`.
  - Pass gates for World B: $\text{CV}(N) \le 0.08$, $\text{amplitude} \le 0.25$, $\text{reversals}/72\text{k} \le 8.0$, $\text{old-age burstiness} < 3.0$, $\min(N) > 0.5 \times K_{\text{eff\_min}}$.
  - Baseline World A (wanders $\sim 218–519$ around $K=380$ due to moving setpoint + cohort lockstep) vs World B (flat setpoint + hysteresis + cohort jitter). Live verification runs for World A (seeds 42, 123, 999) actively executing in background.
  - Follow-up diagnosis note: Opencode follow-up diagnosis in `ecology.py` identified that wild food supply was still oscillating with era-length age multiplier `_smooth_age_mult(AGE_FOOD_MULT)` (0.55×–1.25×), which caused Ice Age food dips while population ceiling was flat; uncoupling food target from era age multiplier preserves seasonal variation only, keeping food dynamics fully synchronized with flat K.

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
4. **Pass full test suite** — Every step must maintain 100% pass rate across the 523+ automated test cases.

---

## Archive index
§F Infrastructure — Database · §A Life cycle · §B Reproduction · §C Irregularity & caste · §D Health & disease · §E Environment · §G God-law & observability · §H Food ecosystem · §I Society · §J Creature profile · §K Documentation · §L Shelter · Cross-system synergies · §W World generation · §N New frontiers · §O Ecosystem depth · §P Clan depth · §Q Creatures 2.0 · §R Weather as life · §S WorldBox inspirations · §T Sustainability & performance · §U Mobile UI/UX · §V Clan founding redesign · §X Fixes · §X2 Communication II · §Y UI polish · §Z Terminal frontend · §AA Performance round 2 · §AB Politics · §AC Desperation cannibalism · §AD OS-log persistence · §AE Food decay · §AF Performance & Massive Scale · §AG Autonomous Evolution · §AH Energy Dynamics · §AI TUI Feature Parity · §AJ Next-Gen Performance (3 phases) · §AK Clan Lifecycle · §AL Creature Cognitive Agency · §AM Food & Agriculture · §AN Communication, Language & Diplomatic · §AO Nocturnal Perils · §AP Unified Theology · §AQ 2D Physics · §AR Creature Senses · §AS Clan Leader Importance · §AT Four Immediate Issues · §AU Performance Optimizations · §AV Frontend & TUI Performance · §AW Emergency 1–2 TPS · §AX High-Density 20 TPS · §AY Multi-Core Engine · §AY2 World Simulation Presets · §AZ Backend Performance Audit · §BA Micro-Neural Network · §BC Geometric Physics & Morphological Evolution · §BD World Analytics & Telemetry Engine · §BE Creature Movement AI Overhaul · §BF Early Population Boom Limiter · §BG Mutational Shape & Visual Phenotypes · §BH Next-Gen Evolutionary Mutation Engine & Neuroevolution · §BI Simulation Engine Decomposition · §BJ Production Performance & Tick Budget Restoration · §BK Mutational Accents, Avatar Parity & Map Lenses · §BL Frontend High-Performance 60 FPS Engine · §BM Chronicle, World History & AI Story · §BN God Panel UX & Law Cleanup · §BO Production Performance Optimization & Zero-Allocation Engine · §BP Tri-Repository Architectural Split

Full completed content → [`docs/roadmap-archive.md`](docs/roadmap-archive.md)
