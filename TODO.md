# Flatland — World Simulation TODO

[![GitHub Repo](https://img.shields.io/badge/GitHub-longphanmn%2Fflws-181717.svg?logo=github)](https://github.com/longphanmn/flws)

The Sphere model: The Sphere (God) sets **laws** from Spaceland, never touches individual creatures. Everything else emerges.  
Repository: [https://github.com/longphanmn/flws](https://github.com/longphanmn/flws)  
Legend: [P0] foundational · [P1] core Flatland identity · [P2] flavor/observability · `- [ ]` open · `- [x]` done · *parked* = decided, not pending

> **Active backlog only.** Completed roadmaps §F–§BO (748 items) → [`docs/roadmap-archive.md`](docs/roadmap-archive.md). This file tracks **open items in §BP** (and completed §BO) + 8 parked.

---

## §BO Production Performance Optimization & Zero-Allocation Engine — Backlog (8/8) — 2026-09-11

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
- [x] [P0] **BO-8 Verification, Production Deploy & Live Profiling**
  - Run the full 513-test suite to guarantee zero regression.
  - Run `bench_tick.py` and `test_tick_budget.py` (both 170 and 360 pop) to measure latency improvements.
  - Deploy to production via `./deploy.sh` (preserving world state).
  - Profile production server live with `py-spy` and query `/healthz` to verify sustained 10.0 TPS and reduced CPU.

---

## §BP Tri-Repository Architectural Split: Backend (flws), Web Frontend (flws-web) & Landing Page (flws-page) — Completed (16/16) — 2026-09-11

> **Context & Architecture**: The Flatland project is decoupling from a monorepo structure into three dedicated, specialized GitHub repositories with independent release cadences, distinct deployment pipelines, and two independent GitHub Pages sites:
> 1. **`flws`** (`longphanmn/flws`): Pure backend simulation engine (FastAPI, SimEngine OS thread, NumPy SoA buffers, micro-Elman RNN controllers, polar SAT physics, TUI, SQLite persistence, and pytest suites).
> 2. **`flws-web`** (`longphanmn/flws-web`): Standalone web frontend simulation client (React 18, Vite, TypeScript, Canvas2D/WebGL 60 FPS viewport, Macro Analytics Observatory, Inspector, dynamic WebSocket client). Deploys to independent GitHub Pages (`https://longphanmn.github.io/flws-web/`).
> 3. **`flws-page`** (`longphanmn/flws-page`): Official project landing page and marketing showcase (interactive background creature canvas, audio synthesizer badge, multi-theme selector, lore, and CTA portal). Deploys to independent GitHub Pages (`https://longphanmn.github.io/flws-page/` or custom domain).
>
> **Core Deployment Constraints**:
> - **Unified Same-System Deployment**: Production server (`root@192.168.1.21:~/app/fl`) and `docker-compose.yml` must deploy and run BOTH backend and frontend together on the same host (backend on `:8000`, frontend on `:5173`/`:80` with Nginx reverse proxy).
> - **Seamless `deploy.sh` Orchestration**: `deploy.sh` must work flawlessly across the new code structure, auto-detecting multi-repo sibling directories (`../flws-web`, `../flws-page`), synchronizing changes atomically, and driving both host services and independent GitHub Pages.
> - **Universal Documentation & Wiki Parity**: All documentation (`README.md`, `docs/god-laws.md`, `docs/world-history-chronicle.md`), living wiki engines (`wiki_i18n.py`, `wiki_content_i18n.py`), and static wiki files (`wiki/index.html`, `wiki-vi.html`, `wiki-fr.html`) must cross-reference all 3 repositories and the 2 GitHub Pages.

### 1. Docker Compose & Same-System Unified Deployment [P0]
- [x] [P0] **BP-1 Multi-Repo Source Contexts in `docker-compose.yml`**
  - Parameterize backend and frontend build contexts (`${BACKEND_DIR:-./backend}`, `${FRONTEND_DIR:-./frontend}`) to seamlessly support both monorepo layout and sibling multi-repo checkouts (`../flws-web`).
  - Maintain shared bridge network `flatland` so frontend Nginx container reverse-proxies `/api`, `/ws`, `/healthz`, and `/wiki` directly to `http://backend:8000`.
- [x] [P0] **BP-2 Same-System Production Runtime & Reverse Proxy Validation**
  - Verify container port mappings (`${BACKEND_PORT:-8000}:8000` and `${FRONTEND_PORT:-5173}:80`) operate concurrently on a single host without port collisions.
  - Add multi-repo environment configuration examples in `.env.example` documenting `FRONTEND_DIR`, `BACKEND_DIR`, and `LANDING_DIR`.

### 2. Production Deploy Script (`deploy.sh`) Overhaul for New Code Structure [P0]
- [x] [P0] **BP-3 Multi-Repo Auto-Detection & Path Resolution (`deploy.sh`)**
  - Auto-discover frontend source tree: priority check for `$FRONTEND_DIR`, then sibling repository `$LOCAL_DIR/../flws-web`, then in-tree `$LOCAL_DIR/frontend`.
  - Auto-discover landing page source tree: priority check for `$LANDING_DIR`, then sibling repository `$LOCAL_DIR/../flws-page`, then sibling `$LOCAL_DIR/../flws`.
  - Add CLI flags `--frontend-dir <PATH>` and `--landing-dir <PATH>` with explicit validation and terminal status logging.
- [x] [P0] **BP-4 Atomic Dual-Service Deployment to Same Remote Host (`deploy.sh`)**
  - Detect changes independently across git repositories (inspecting commits/status in `$LOCAL_DIR` and `$FRONTEND_DIR`).
  - Rsync backend from `$LOCAL_DIR/backend` and external frontend from `$FRONTEND_DIR` into `$SERVER:~/app/fl/` so both services reside on the same remote system.
  - Build native OpenMP C kernel (`app/_flatland_core.so`), build frontend production bundle, and launch both backend (uvicorn `:8000`) and frontend (vite preview `:5173`) in background while preserving live world snapshots and database.
- [x] [P0] **BP-5 Dual Independent GitHub Pages Deployments (`deploy.sh`)**
  - Build minified production bundle from `$FRONTEND_DIR` with configurable base path (`VITE_BASE`).
  - Support deploying the web client to the dedicated `flws-web` GitHub Pages repository (`GH_PAGES_WEB_DIR`).
  - Support deploying the landing page and static showcase to the `flws-page` GitHub Pages repository (`GH_PAGES_DIR`).

### 3. Backend Extraction & Standalone Repository (`flws`) [P0]
- [x] [P0] **BP-6 Pure Backend Engine Boundary Isolation (`flws`)**
  - Clean repository root of frontend-specific static bundles, keeping pure simulation engine, FastAPI server, TUI client, test suites, Dockerfile, and native C extension.
  - Maintain clean REST API and WebSocket contract (`/api/*`, `/ws`, `/healthz`, `/wiki`).
- [x] [P0] **BP-7 Cross-Origin Resource Sharing (CORS) & WSS Security (`flws`)**
  - Configure FastAPI CORS middleware and WebSocket origin validators in `backend/app/main.py` to accept requests from both GitHub Pages domains (`longphanmn.github.io/flws-web` and `longphanmn.github.io/flws-page`).
  - Document SSL/TLS termination and WSS proxying requirements when HTTPS GitHub Pages connects to backend servers.

### 4. Web Frontend Dedicated Repository (`flws-web`) & GitHub Pages [P0]
- [x] [P0] **BP-8 Extract `frontend/` to Independent Repository `flws-web`**
  - Extract entire React 18 + Vite + TypeScript codebase to standalone repository `github.com/longphanmn/flws-web`.
  - Configure standalone `package.json`, `tsconfig.json`, Vite configuration, and local preview scripts.
- [x] [P0] **BP-9 Configurable Backend Transport & Runtime Host Override**
  - Wire environment variables `VITE_SIM_API_URL` and `VITE_SIM_WS_URL` with auto-fallback to origin host or `localhost:8000`.
  - Support dynamic host override via URL parameter (`?host=...` or settings modal) so the GitHub Pages client can point to any local or remote Flatland backend instance.
- [x] [P0] **BP-10 Independent GitHub Pages CI/CD Workflow (`flws-web`)**
  - Author `.github/workflows/deploy-pages.yml` in `flws-web` repository.
  - Configure Vite `base: '/flws-web/'` for GitHub Pages hosting at `https://longphanmn.github.io/flws-web/`.

### 5. Landing Page Dedicated Repository (`flws-page`) & GitHub Pages [P0]
- [x] [P0] **BP-11 Extract Landing Page to Dedicated Repository `flws-page`**
  - Extract landing page (`index.html`, `assets/css/style.css`, `assets/js/app.js`, background creature canvas, audio badge, themes) into repository `github.com/longphanmn/flws-page`.
  - Maintain lightweight standalone canvas simulation without heavy backend dependencies.
- [x] [P0] **BP-12 GitHub Pages CI/CD Workflow (`flws-page`)**
  - Configure GitHub Actions deployment workflow with GitHub Pages permissions.
  - Support hosting at `https://longphanmn.github.io/flws-page/` or custom landing domain.
  - Support hosting at `https://longphanmn.github.io/flws-page/` or custom landing domain.
- [x] [P0] **BP-13 Landing Page CTA Buttons Repointing to `flws-web`**
  - Update primary CTA buttons ("Launch Simulation", "Live Demo", "Web App") on landing page to navigate to `https://longphanmn.github.io/flws-web/`.
  - Update footer and navigation links to point to the dedicated `flws-web` app and `flws` backend repository.

### 6. Documentation, Living Wiki & Cross-Repository Synchronization [P0]
- [x] [P0] **BP-14 Core Project Documentation Overhaul (`README.md`, `docs/*`)**
  - Update `README.md` across all 3 repositories to explain the tri-repository architecture with diagrams and cross-links (`flws`, `flws-web`, `flws-page`).
  - Document same-system co-deployment via `docker-compose` and `deploy.sh`.
- [x] [P0] **BP-15 Living Wiki Multi-Language Engine Synchronization (`wiki_i18n.py`, `wiki_content_i18n.py`)**
  - Update Codebase Map in English (`CODEBASE_MAP_EN`), Vietnamese (`CODEBASE_MAP_VI`), and French (`CODEBASE_MAP_FR`) to reflect the tri-repo architecture.
  - Update wiki headers, footers, and API documentation to reference the 3 repositories and dual GitHub Pages endpoints.
- [x] [P0] **BP-16 Static Multi-Language Wiki Pages & OpenAPI Parity (`flws/wiki/` & `demo/wiki/`)**
  - Re-generate and synchronize static wiki pages (`wiki/index.html`, `wiki-vi.html`, `wiki-fr.html`) and Swagger UI docs across repositories to maintain 100% link accuracy.

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
7. **BP-1 & BP-3 Same-system deployment before repository extraction** — Ensure `docker-compose.yml` and `deploy.sh` support external frontend directories before splitting repositories.
8. **BP-9 Dynamic host override before BP-10 GitHub Pages deploy** — Web client must support configurable API/WS endpoints before deploying to standalone GitHub Pages domain.

---

## Archive index
§F Infrastructure — Database · §A Life cycle · §B Reproduction · §C Irregularity & caste · §D Health & disease · §E Environment · §G God-law & observability · §H Food ecosystem · §I Society · §J Creature profile · §K Documentation · §L Shelter · Cross-system synergies · §W World generation · §N New frontiers · §O Ecosystem depth · §P Clan depth · §Q Creatures 2.0 · §R Weather as life · §S WorldBox inspirations · §T Sustainability & performance · §U Mobile UI/UX · §V Clan founding redesign · §X Fixes · §X2 Communication II · §Y UI polish · §Z Terminal frontend · §AA Performance round 2 · §AB Politics · §AC Desperation cannibalism · §AD OS-log persistence · §AE Food decay · §AF Performance & Massive Scale · §AG Autonomous Evolution · §AH Energy Dynamics · §AI TUI Feature Parity · §AJ Next-Gen Performance (3 phases) · §AK Clan Lifecycle · §AL Creature Cognitive Agency · §AM Food & Agriculture · §AN Communication, Language & Diplomatic · §AO Nocturnal Perils · §AP Unified Theology · §AQ 2D Physics · §AR Creature Senses · §AS Clan Leader Importance · §AT Four Immediate Issues · §AU Performance Optimizations · §AV Frontend & TUI Performance · §AW Emergency 1–2 TPS · §AX High-Density 20 TPS · §AY Multi-Core Engine · §AY2 World Simulation Presets · §AZ Backend Performance Audit · §BA Micro-Neural Network · §BC Geometric Physics & Morphological Evolution · §BD World Analytics & Telemetry Engine · §BE Creature Movement AI Overhaul · §BF Early Population Boom Limiter · §BG Mutational Shape & Visual Phenotypes · §BH Next-Gen Evolutionary Mutation Engine & Neuroevolution · §BI Simulation Engine Decomposition · §BJ Production Performance & Tick Budget Restoration · §BK Mutational Accents, Avatar Parity & Map Lenses · §BL Frontend High-Performance 60 FPS Engine · §BM Chronicle, World History & AI Story · §BN God Panel UX & Law Cleanup · §BO Production Performance Optimization & Zero-Allocation Engine

Full completed content → [`docs/roadmap-archive.md`](docs/roadmap-archive.md)
