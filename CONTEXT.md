# CONTEXT.md — Flatland Simulation Engine (`flws`)

## 1. Project Overview & Mission
- **Project Name:** Flatland World Simulation Engine (`flws`)
- **Core Concept:** Autonomous 2D artificial life, continuous ecology, and neuroevolutionary simulation inspired by Edwin A. Abbott's 1884 novella *Flatland: A Romance of Many Dimensions*.
- **Runtime & Stack:** Python 3.12+ (FastAPI, Uvicorn, NumPy), C99 OpenMP shared library (`flatland_core.c`), SQLite in WAL mode, and Textual TUI.
- **Architectural Tenets:**
  1. **Threaded Execution Seam:** The physics/life loop (`Simulation.step()`) executes on a dedicated OS thread (`SimEngine`), decoupling deterministic fixed-timestep ticks (default: 10 TPS / 100ms) from asynchronous REST and WebSocket I/O.
  2. **Dual-Path Acceleration:** Broadphase spatial sweeps, raycasting, and line intersections are accelerated via embedded C99 OpenMP (`_flatland_core.so`), backed by 100% deterministic pure-Python fallbacks.
  3. **Structure-of-Arrays (SoA) Vectorization:** `AgentSoA` stores entity kinematics, sensors, and vitals in contiguous memory buffers feeding a 295-parameter Micro-Elman Recurrent Neural Network forward inference engine.
  4. **Polar Polygon Biomechanics:** Organisms possess continuous $K$-vertex polar morphologies ($K \in [3, 24]$) evaluated via Green-Gauss polygon integration for rotational inertia ($I_{zz}$), Shoelace area, and Separating Axis Theorem (SAT) collision dynamics.
  5. **Macro Homeostasis & Structural Stability:** Dual feedback loops prevent ecosystem collapse and oscillation lock-in: Extinction Safeguard Factor ($\eta$) provides emergency relief during demographic crises using unified effective carrying capacity; Density Soft-Cap Damping ($\xi$) with $0.85 K_{\text{cap}}$ hysteresis onset, exponential release slew ($\tau = 300\text{t}$), smooth cosine fertility room ramp (replacing hard ceilings), and $\pm 30\%$ lifespan/cooldown jitter ($U(0.7, 1.3)$) stabilizes population around a flat carrying setpoint.

---

## 2. Domain Vocabulary & Mathematical Concepts

| Term | Domain Category | Definition & Implementation |
| :--- | :--- | :--- |
| **Toroidal Topology** | World Geometry | Coordinates span $[0, W) \times [0, H)$ (default $400 \times 300$). Displacements wrap across opposite edges when $|\Delta x| > W/2$. |
| **Spatial Hash Grid** | Spatial Index | $O(N)$ uniform 1D bucketed spatial index with fixed $16.0$-unit cell size (`world.py`), eliminating per-tick allocations. |
| **Polar Morphology** | Biomechanics | Vertices defined as $(r_i, \phi_i)$. Area ($A$) via Shoelace formula, perimeter ($P$), and rotational inertia ($I_{zz}$) via Green-Gauss integration. |
| **Sharpest Apex ($\theta_{\min}$)**| Biomechanics | Minimum interior angle of adjacent vertex triplets; inversely proportional to physical strike damage. |
| **Asymmetry Index ($irr$)** | Morphology | Normalized polar radius variance: $\text{Var}(r) / \bar{r}^2$. Deviations beyond threshold trigger societal euthanasia unless saved by mercy laws. |
| **SAT Narrowphase** | Physics | Separating Axis Theorem resolving exact convex/concave polygon penetration, impulses, and kinetic damage. |
| **Micro-Elman RNN** | Neuroevolution | 295 float32 weights ($W_1: 16\times12, W_2: 12\times7$). Inputs: 8 raycasts, velocity, energy, health, day/night, temp, recurrent state. Outputs: thrust, steer, interact, posture, vocalization. |
| **Annealing $\lambda(g)$** | Genetics | Controls morphological drift from Abbott classical templates ($\lambda=1$ for $g < 15$) to open-ended speciation ($\lambda \to 0$). |
| **The Sphere** | Theology / Macro | 3D entity observing from Spaceland. Enacts universal `GodLaws` (climate, mutation, carrying capacity) but cannot move or heal individual agents. |
| **Extinction Safeguard ($\eta$)**| Macro Homeostasis | Relief factor $\eta \in [0, 1]$ active when $N < K_{\text{safe}}$ ($K_{\text{safe}} = K_{\text{eff}} \times \text{relief\_ratio}$, unified with $K_{\text{cap}}$). Boosts flora growth, reduces energy drain, enables morphological mercy, triggers Genesis Miracles. |
| **Density Soft-Cap ($\xi$)** | Macro Homeostasis | Damping factor $\xi = \max(0, (N - 0.85 K_{\text{cap}})/K_{\text{cap}})$. Begins at $0.85 K_{\text{cap}}$ (hysteresis onset) and releases exponentially toward target with $\tau = 300\text{t}$, suppressing birth rates (via sigmoid $k=5.0$) and elevating metabolic stress. Combined with cosine fertility room to $max\_pop$ and $U(0.7, 1.3)$ cohort jitter. |
| **Abbott Castes** | Social Hierarchy | Woman ($sides=2$, line), Isosceles Soldier ($sides=3$, acute), Artisan ($sides=3, \theta=60^\circ$), Gentleman ($sides=4$, square), Noble ($6 \le sides < 24$), Priest ($sides \ge 24$, circle). |
| **Avatars of the Sphere** | Culture / Religion | 8 sacred totems: Radiant Circle, Celestial Strike, All-Seeing Vertex, Indomitable Monolith, Sacred Spiral, Cosmic Scales, Dimensional Rift, Eternal Hearth. |

---

## 3. Architecture & Data Flow

```mermaid
flowchart TD
    subgraph EngineThread ["Dedicated OS Engine Thread (SimEngine)"]
        Loop["Simulation.step() @ 10 TPS"]
        SoA["AgentSoA Vectorized Buffers"]
        RNN["Micro-Elman RNN Inference"]
        SAT["Polar Polygon & SAT Physics"]
        Native["_flatland_core.so (C99 / OpenMP)"]
        DB["SQLite WAL (Chronicles & Lineages)"]
    end

    subgraph ServerIO ["Asyncio / FastAPI Event Loop"]
        Uvicorn["Uvicorn Server (:8000)"]
        Hub["Hub Broadcaster (Non-blocking Queues)"]
        REST["REST Endpoints (/api/*, /healthz)"]
    end

    subgraph Clients ["Ecosystem Clients"]
        Web["flws-web (React / Canvas2D Client)"]
        TUI["flws Textual TUI Client"]
    end

    Loop <--> SoA
    Loop <--> RNN
    Loop <--> SAT
    SAT <--> Native
    Loop -->|Periodic Flush| DB
    Loop -->|Tick State & Deltas| Hub
    Hub -->|WebSocket /ws (StateMessage, DeltaStateMessage)| Web
    Hub -->|WebSocket /ws| TUI
    REST <-->|GodLaws, History, Presets| Web
```

### Protocol Wire Specifications
- **Connection Handshake:** On connect, server transmits `{"type": "hello", ...}` followed by a full `StateMessage`.
- **Tick Deltas (`DeltaStateMessage`):** Transmits `upsert_entities` (entities exceeding movement/vital delta thresholds) and `remove_ids` (culled/deceased IDs) to minimize bandwidth.
- **Security Boundary:** Endpoints modifying world laws (`POST /api/laws`, `POST /api/presets/{name}`, `POST /api/control`) require `X-God-Key` PBKDF2-HMAC-SHA256 authentication.

---

## 4. Key Workflows & Commands

```bash
# 1. Install dependencies via uv
cd /root/workspace/flatland/flws/backend
uv sync

# 2. Build native C OpenMP accelerator (optional; auto-compiled at runtime)
gcc -O3 -shared -fPIC -fopenmp -march=native -ffast-math flatland_core.c -o _flatland_core.so -lm

# 3. Start simulation backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
# Or via orchestrator:
./run.sh backend

# 4. Start backend and auto-launch web client (:5173)
./run.sh

# 5. Launch terminal TUI client
./run.sh tui
# Or connect to remote:
./run.sh tui ws://remote-host:8000/ws

# 6. Execute full Pytest test suite (523+ tests)
cd backend && uv run pytest -v
uv run pytest tests/test_physics_core.py -v
uv run pytest tests/test_neuroevolution.py -v
uv run pytest tests/test_soft_cap.py -v

# 7. Run with Docker Compose
docker compose up --build

# 8. Execute A/B population oscillation verification harness & compare gates
# Gates: CV(N) <= 0.08, amplitude <= 0.25, reversals/72k <= 8.0, burstiness < 3.0, min N > 0.5*K_eff_min
python3 scripts/preset_experiment.py --osc-run --world B --seed 42 --ticks 120000 --burn-in 20000 --out scripts/oscillation_B_42.json
python3 scripts/preset_experiment.py --osc-compare scripts/oscillation_A_42.json scripts/oscillation_B_42.json
```

---

## 5. File & Directory Layout

```
flws/
├── backend/
│   ├── app/
│   │   ├── config.py             # Config frozen dataclass & FLATWORLD_* env parser
│   │   ├── entities.py           # Entity, Creature, Food, House, Corpse, CasteTraits
│   │   ├── world.py              # Spatial hash index, toroidal delta(), line intersections
│   │   ├── flatland_core.c       # Native C99 / OpenMP kernel (raycasting, spatial query, sweep)
│   │   ├── flatland_core.h       # C header declarations & memory-aligned C structs
│   │   ├── native_core.py        # ctypes bridge to _flatland_core.so with Python fallback
│   │   ├── agent_soa.py          # Structure-of-Arrays (SoA) contiguous memory buffers
│   │   ├── agent_pipeline.py     # Batch sensor input preparation & output application
│   │   ├── neural_engine.py      # Micro-Elman RNN (16->12->7) vectorized inference
│   │   ├── morphology_engine.py  # Polar polygon SAT collision, Green-Gauss Shoelace trait baking
│   │   ├── evolution_manager.py  # Abbott templates, λ(g) annealing, two-parent polar crossover
│   │   ├── safeguard_engine.py   # Extinction safeguard factor (η), Tier 1/2/3, Genesis Miracles
│   │   ├── density_damping.py    # Density-dependent soft-cap damping factor (ξ)
│   │   ├── analytics.py          # TelemetryRing, demographic sparklines, trophic distribution
│   │   ├── protocol.py           # Pydantic wire models (StateMessage, DeltaStateMessage, GodLaws)
│   │   ├── auth.py               # PBKDF2-HMAC-SHA256 god passkey authentication & dependency
│   │   ├── db.py                 # SQLite WAL persistence for events, lineages, settings, worlds
│   │   ├── wiki.py / wiki_i18n.py# In-engine living wiki & multilingual documentation renderer
│   │   ├── main.py               # FastAPI application, Hub broadcaster, SimEngine thread, REST & WS
│   │   └── simulation/           # Decomposed simulation domain mixins
│   │       ├── core.py           # Master Simulation class & deterministic step() loop
│   │       ├── creature_update.py# 7-phase creature update pipeline
│   │       ├── constants.py      # Numerical constants, tuning limits, procedural tables
│   │       ├── ecology.py        # Flora lifecycle, agriculture, compost, banquets
│   │       ├── environment.py    # Diurnal cycle, weather, wind, seismic, temperature field
│   │       ├── lifecycle.py      # Reproduction, birth, aging, euthanasia, disease contagion
│   │       ├── settlement.py     # House wall collision, bed contest, ruin collapse, construction
│   │       ├── society.py        # Clan relations, coalitions, war, trade caravans, larders
│   │       ├── theology.py       # Shrines, faith pools, tithes, sacred avatars, synods, miracles
│   │       └── serialization.py  # Snapshot and delta wire serialization
│   ├── tui/                      # Textual terminal client (app.py, client.py, state.py, viewport.py)
│   ├── tests/                    # Pytest test suites (44 test files)
│   ├── Dockerfile                # Multi-stage Python 3.12 + gcc build
│   └── pyproject.toml            # uv project specification & dependencies
├── docs/                         # Specifications (god-laws.md, world-history-chronicle.md)
├── scripts/                      # Benchmarking & headless experiment runners
├── docker-compose.yml            # Dual-service compose file (backend:8000 + flws-web:5173)
├── run.sh                        # Master local launcher script
└── setup.sh                      # Zero-configuration setup script
```

---

## 6. Code Conventions & Architectural Seams
- **Mixins Composition Pattern:** The `Simulation` class composes functionality by inheriting from 8 domain mixins (`SerializationMixin`, `EcologyMixin`, `EnvironmentMixin`, `SettlementMixin`, `TheologyMixin`, `SocietyMixin`, `LifecycleMixin`, `CreatureUpdateMixin`).
- **Zero-Allocation Hot Paths:** Pre-allocated bucket arrays in `World` and in-place SoA updates prevent GC pressure during ticks.
- **Dual Fallback Seam:** Every high-performance C kernel function has a corresponding deterministic pure-Python implementation.
