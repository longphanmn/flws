# Flatland — 2D Autonomous World Simulation

[![GitHub Repo](https://img.shields.io/badge/GitHub-longphanmn%2Fflws-181717.svg?logo=github)](https://github.com/longphanmn/flws)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![React: 18](https://img.shields.io/badge/React-18-61DAFB.svg)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.6-3178C6.svg)](https://www.typescriptlang.org/)

**Flatland** is an autonomous 2D artificial life and ecosystem simulation developed from the foundational ideas of **Edwin A. Abbott's 1884 classic *Flatland: A Romance of Many Dimensions***. Rather than rigidly mimicking or reenacting the 19th-century novella, this project takes Flatland's core geometric premises — 2D spatial existence, vertex-based caste hierarchy, atmospheric perception, and higher-dimensional observation — and transforms them into a **living, autonomous evolutionary world that dynamically changes and expands over time**.

> **Landing Page**: [https://longphanmn.github.io/flws-page/](https://longphanmn.github.io/flws-page/)  
> **Live Web App**: [https://longphanmn.github.io/flws-web/](https://longphanmn.github.io/flws-web/)  
> **Source Repositories**:
> - Backend Simulation Engine: [`flws`](https://github.com/longphanmn/flws) (FastAPI, Simulation Loop, SoA, Micro-RNN)
> - Web Frontend Client: [`flws-web`](https://github.com/longphanmn/flws-web) (React 18, Canvas2D 60 FPS, Observatory)
> - Landing Page (Private): [`flws-page`](https://github.com/longphanmn/flws-page) (Showcase, Marketing, Lore)  
> **Developed by [Long Phan](mailto:long@minhnhan.in)** ([long@minhnhan.in](mailto:long@minhnhan.in))  
> Built and refined using **OpenCode** and **Antigravity**.  
> Developed from the core mathematical and spatial ideas of **Edwin A. Abbott** (1884).

---

## 🏛️ Design Philosophy: Evolution from Flatland

1. **Developed from the Idea, Not a Literal Mimic**: The simulation embraces Abbott's fundamental concepts — 2D geometric constraints, line and polygon dynamics, generational side inheritance, and the perspective of a 3D observer (the Sphere / God Model) — while freely diverging from Victorian social satire to build an authentic artificial life ecosystem.
2. **Living & Changing Over Time**: The world evolves dynamically across seasons, generations, and historical ages. Organisms develop heritable personalities, master distinct craft disciplines, form tribal coalitions, exchange oral traditions, and manage domestic economies.
3. **Immutable Natural Laws**: The Sphere (God) governs exclusively through universal laws of nature (metabolism, carrying capacity, climate volatility, disease), leaving all individual outcomes to 100% emergent behavior.


### 1. The Sphere (God Model): Laws over Fates
In Flatland, The Sphere (God) sets the **laws of nature** from Spaceland but never touches an individual life. The Sphere cannot kill, heal, or move a single creature; the simulation advances deterministically under physical and biological rules.
- **The Sphere Panel (`⚖ The Sphere`)**: Full control over world dynamics via a dedicated **🎯 Presets** selector and 6 streamlined **⚖️ Macro Domains** (Ecology & Survival, Biology & Evolution, Climate & Sky, Society, Warfare & Trade, Theology & Sacred Avatars, World Physics & Disasters) with instant search, modified-only filtering, baseline comparison, and real-time dual sliders.
- **Curated World Presets**:
  - **⚖️ Balance (Default)**: Goldilocks harmony tuned for **200–350 inhabitants** with 380 food, carrying capacity 400 (max 500), gentle wars, rare predation, agriculture, soft-cap damping ($\xi$), extinction safeguards ($\eta$), and flourishing multi-generational clans.
  - **🌿 Sustainable**: 1000-day prosperous peace, abundant food (550), carrying capacity 550 (max 600), rich granaries, and banquets.
  - **🔮 Theocracy**: Age of the Sphere, divine avatars, glowing temples, avatar miracles, 3D epiphanies, and holy synods.
  - **⚔️ Warlords**: Clash of clans, imperial conquests, granary raids, house takeovers, and defensive coalitions.
  - **🔥 Chaos**: High predator ratio, lethal wars, wildfires, frequent plagues, earthquakes, and fast seasonal turnover.
  - **💀 Extinction**: Famine (120 food), harsh winter (0.3×), high exposure decay, testing societal resilience under collapse.
  - **🚀 Boom**: High reproduction, 440 food, carrying capacity 800 (max 850) for high-scale urban expansion.

### 2. Biology, Castes & Nature's Law
- **Geometric Hierarchy**: Higher side counts perceive farther and live longer (Women shortest → Isosceles Soldiers → Equilateral Artisans → Squares/Pentagons → Polygons → Priests/Circles longest).
- **Heritability & Ascendance**:
  - Sons inherit one more side than their father ($n+1$), ascending the societal ladder across generations.
  - Isosceles triangles creep $+0.5^\circ$ per generation, promoting to regular Equilateral Artisans at $60^\circ$.
  - Daughters inherit the line form of their mother.
  - Mutations may deviate a child's side count, producing irregularity judged at adulthood.
- **Energy Metabolism & Life Stages**:
  - Four distinct life stages: **Infant**, **Juvenile**, **Adult**, and **Elder**.
  - Infants burn 55% less energy per tick (`0.45×`); elders move and see with reduced vigor.
  - Hunger activates enhanced foraging sight; extreme starvation triggers desperate speed and pulsing indicators.
- **Dynamic Homeostasis & Extinction Prevention**:
  - **Density-Dependent Soft-Cap Damping ($\xi$)**: Non-linear negative feedback suppresses birth rate and scales metabolic strain when exceeding carrying capacity.
  - **Extinction Safeguards ($\eta$)**: Emergency multi-tier relief scales and Sphere Genesis miracles prevent collapse when population falls below critical thresholds.
  - **Neural Sensory Foraging**: Micro-RNN 16-sensor raycasting and inductive food-homing biases guide organisms toward sustenance and prevent starvation traps.

### 3. Autonomous Evolution, Skills & Oral Lore
Evolution emerges 100% autonomously without artificial intervention:
- **Personality Archetypes**: Genetic heritability (65%) for traits including `brave`, `cautious`, `altruistic`, `greedy`, `explorer`, and `builder`. Altruistic creatures feed starving kin using basket reserves.
- **Dynamic Equipment & Tools**:
  - **Spears**: $+20\%$ combat damage and strike reach for Soldiers and Apex Predators.
  - **Baskets**: Carry up to 3 food units for field meals while roaming or depositing into settlement larders.
  - **Herb Poultices**: $+25\text{ HP}$ healing and infection remedies for Priests.
  - **Chieftain Crown**: Adorns the leader of each settlement house.
- **Skill Mastery Matrix**: Four masterable disciplines (Farming 🌾, Combat ⚔️, Foraging 🦴, Healing 🌿) unlocking earned titles (*the Slayer*, *the Fearless Champion*, *the Grand Harvester*, *the Wise Shaman*, *the Pathfinder*).
- **Oral Lore in Houses**: Resting elders teach their highest skill mastery to sleeping youth indoors.
- **Thought Bubbles**: Real-time floating emote indicators (`🍖`, `❤️`, `⚔️`, `🌿`, `🏆`, `💤`, `🧺`, `😱`).
- **Cognitive Agency & Tactical Intelligence**: Multi-objective utility AI scoring replaces rigid if/else trees (evaluating survival, duty, traits, and kin needs); spatial waypoint mental maps (`home`, `rich_food`, `danger`, `patrol`); tactical soldier phalanxes, line kiting maneuvers, and interpersonal trust-based buddy pairing.

### 3.1 Geometric Physics & Morphological Evolution (§BC)
- **Polar Genomes & Physical Trait Baking**: Every organism is defined by polar coordinates $(r_i,\phi_i)$ with vertex count $K\in[3,64]$ (ultra-circles up to 64). Biomechanical traits are computed in real time via Green-Gauss and Shoelace formulas: Area $A$, Perimeter $P$, Rotational Inertia $I_{zz}$, Minimum Interior Apex Angle $\theta_{\min}$, and Damage Multiplier $D_{\text{mult}}$.
- **Evolutionary Annealing $\lambda(g)$**: Foundational generations adhere strictly to Abbott orthodoxy ($\lambda=1$); as generations elapse, $\lambda \to 0$ unlocks open-ended speciation, meiotic two-parent crossover, and macro-mutation spurts.
- **Micro-Elman RNN Controllers**: 295 evolvable neural controller weights ($16 \to 12 \to 7$) driving real-time sensory raycasting, predator evasion, forage navigation, and buddy-trust bonding.

### 3.2 Mutational Phenotypes, Veteran Scars & Map Lenses (§BG & §BK)
- **True Isosceles Soldier Razor Apex**: Soldiers render their physical apex angle ($\theta_{\text{iso}} \in [10^\circ, 59.5^\circ]$) pointing forward along their velocity heading.
- **Dynamic Mutated Geometry**: Irregular, asymmetric polygons procedurally generated with vertex offsets and dynamic chaotic oscillation for thrashed mutants ($irr > 0.15$).
- **Visual Phenotypic Accents**:
  - **Blade Glint (Kinetic Pierce)**: High-damage creatures display a sharp neon glint on their sharpest vertex ($\theta_{\min}$).
  - **Heavy Inertia Armor**: High $I_{zz}$ and large Shoelace area creatures display double-stroke perimeter plating and darkened protective fills.
  - **Speciation Chromatic Aberration**: Divergent evolutionary branches ($\lambda \to 0$) emit iridescent dual-tone outlines.
  - **Primordial Genesis Sparks**: Founding ancestors (Gen 0–2) carry an unmistakable radiant 4-point star diamond core pip.
  - **Concentric Lineage Halos & Starburst Corona**: Generational milestones unlock depth rings — Gen 10–24 inner lineage halos, Gen 25–49 double dynasty rings, and Gen 50+ radiating 8-ray Celestial Ancestral Starburst Coronas.
  - **Battle Veteran Wound Scars**: Hardened survivors display visible perimeter notch scars from grievous wounds (`scars > 0`).
- **Interactive Map Lenses**: Instant visual shaders via HUD buttons or keys `1`–`4`:
  - **`1` Classic**: Traditional clan and caste hierarchy colors.
  - **`2` Mutants Lens**: Dims Abbott orthodox shapes; highlights radical mutants in vivid cyan $\to$ neon magenta.
  - **`3` Generations Lens**: Visual gradient from icy primordial blue (Gen 0) to incandescent ancient gold (Gen 50+).
  - **`4` Dynasty Lens**: Highlights clan territory spheres, borders, and ancestral dynasties.
- **Inspector Polar Morphology Radar**: Complete visual parity between the world map and the Inspector dossier; shows the creature's mutated polygon overlaid against the orthodox Abbott template alongside calculated physical metrics ($\theta_{\min}$, irregularity, $I_{zz}$, Area).
- **Active Safeguard & Softcap Status Indicators**: Real-time HUD badges at the bottom-left of the viewport indicating when Extinction Safeguards ($\eta$, green) or Density Soft-Cap Damping ($\xi$, red) are actively interceding.

### 4. Settlements, Clans & Diplomacy
- **Settlement Houses**: Square walled halls with creature-sized doorways; houses block outside elements and wild carnivores.
- **Territory & Clan Banners**: Foundational houses establish spatial clans with distinct banner colors, procedurally generated clan names, and Sacred Avatars of the Sphere (⭕ Radiant Circle, ⚡ Celestial Strike, 👁️ All-Seeing Vertex, 🛡️ Indomitable Monolith, 🌿 Sacred Spiral, ⚖️ Cosmic Scales, 🌀 Dimensional Rift, 🕯️ Eternal Hearth).
- **Division of Labor & Task Board**: Dynamic macro priorities (`balanced`, `food_security`, `defense`, `quarantine_healing`) boost harvester (2.0×) and guard (2.5×) action weights.
- **Governance Archetypes & Succession**: Distinct institutional models (`Monarchy` royal dynasty, `Theocracy` priest succession, `Junta` combat mastery, `Republic` council of elders).
- **Dynamic Bylaws**: Automated policies including winter food rationing (<35 energy threshold) and wartime martial law curfews.
- **Resource Sharing & Larders**: Settlements maintain food larders where sated members deposit surplus and hungry kin withdraw.
- **Diplomacy & Geopolitics**: Emergent alliances, defensive coalitions, tributary pacts, schisms, and territorial rivalries.
- **Macro Geopolitics & Casus Belli**: Intentional war declarations (famine food raids, blood feuds, territorial friction) with historical Casus Belli tracking.
- **Inter-Clan Trade Caravans**: Economic specialization barter between agrarian and warrior clans (+12 relations and combat skill sharing).
- **Tribal Traditions & Harvest Festivals**: Annual autumn harvest celebrations at settlement Main Houses boosting energy (+25), mood, trust, and oral epic lore.

### 5. Environment & Ecosystem
- **Dynamic Seasons & Day/Night**: Spring blossoms, summer abundance, autumn harvests, and winter lean periods.
- **Biodiversity & Functional Nutrition**: Six distinct plant species (Grass, Golden Grain, Berry Bushes, Medicinal Herbs, Fungi Mushrooms, and Poisonous Sprouts) with targeted health-based foraging preferences and nutrient recycling from fallen corpses.

---

## Quickstart

### Prerequisites
- **Git**
- **Python 3.12+** (with [`uv`](https://docs.astral.sh/uv/) recommended)
- **Node.js 18+** & **npm**

### Clone & Launch
```bash
git clone https://github.com/longphanmn/flws.git
cd flws
./run.sh          # Starts FastAPI backend (:8000) and Vite frontend (:5173)
./run.sh tui      # Launches terminal client attached to local backend
```

### Docker Compose (local production)
```bash
cp .env.example .env          # optional — tweak ports / FLATWORLD_* laws
docker compose up --build -d  # backend :8000, frontend :5173 (nginx proxy)
docker compose logs -f        # tail both services
docker compose down           # stop
docker compose down -v        # stop + wipe SQLite volume (fresh world)
```

- **Web UI**: [http://localhost:5173](http://localhost:5173) (Docker or `run.sh`)
- **API Docs (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Living Wiki & Guide**: [http://localhost:8000/wiki](http://localhost:8000/wiki)
- **Health**: [http://localhost:8000/healthz](http://localhost:8000/healthz)

> `docker-compose.yml` builds `backend/Dockerfile` (Python 3.12 + gcc, compiles the OpenMP native core) and `frontend/Dockerfile` (multi-stage node → nginx). The frontend nginx proxies `/ws`, `/api`, `/wiki`, `/guide`, `/docs`, etc. to `backend:8000`, so the browser only needs port `5173`. SQLite persists in the named volume `flatland-data` (`FLATWORLD_DB=/data/flatworld.db`).

---

## Manual Installation & Commands

### Backend Setup
```bash
cd backend
uv sync                                        # Create venv and install dependencies
uv run pytest -v                               # Run comprehensive test suite
uv run uvicorn app.main:app --reload --port 8000
```

### Frontend Setup
```bash
cd frontend
npm install                                    # Install frontend dependencies
npm run dev                                    # Start Vite development server
npm run build                                  # TypeScript compile & production bundle
```

---

## Terminal TUI Client

Flatland includes a complete terminal client powered by **Textual** (`backend/tui/`) that connects to any running world over WebSocket:

```bash
./run.sh tui                                   # Connect to localhost:8000
./run.sh tui ws://<remote-host>:8000/ws        # Connect to a remote server
```

### TUI Keybindings:
| Key | Action |
|:---:|---|
| `Space` | Pause / Resume simulation |
| `S` | Single step forward (1 tick) |
| `R` | Reset world with new procedural seed |
| `F` | Fit camera to entire world |
| `W` | Follow/track currently selected creature |
| `T` | Filter Chronicle log categories |
| `+/-` | Zoom in / Zoom out |
| `H / J / K / L` or Arrows | Pan camera view |
| `Enter` or `I` | Open detailed Creature Inspector dossier |
| `C` | Open Clan Details modal |
| `G` | Open God Laws configuration screen |
| `1` – `9` | Adjust simulation tick speed |
| `?` | Show interactive help |
| `Q` | Quit terminal client |

---

## Architecture & Codebase Map

```
ws/
├── backend/
│   ├── app/
│   │   ├── config.py            # Configuration dataclass & environment loaders
│   │   ├── entities.py          # Creature castes, traits, food variants, and houses
│   │   ├── world.py             # Entity spatial hash index & wrap-aware proximity queries
│   │   ├── simulation/          # Decomposed simulation engine package (§BI)
│   │   │   ├── core.py          # Master Simulation class, deterministic step loop, SoA sync
│   │   │   ├── creature_update.py # Decomposed 7-phase agent tick pipeline
│   │   │   ├── settlement.py    # Housing economy, construction, claims & takeover
│   │   │   ├── lifecycle.py     # Spawning, reproduction, birth, death, skills & diseases
│   │   │   ├── ecology.py       # Flora lifecycle, farming, banquets & nutrient cycling
│   │   │   ├── theology.py      # Faith pools, shrines, miracles, synods & epiphanies
│   │   │   ├── society.py       # Clans, diplomacy, war, coalitions, trade & larders
│   │   │   ├── serialization.py # Snapshot & delta wire protocol serialization
│   │   │   ├── environment.py   # Weather, wind, temperature grid & disasters
│   │   │   └── constants.py     # Simulation constants, tables & name generators
│   │   ├── agent_soa.py         # Vectorized Structure-of-Arrays buffers (positions/velocities/genomes)
│   │   ├── agent_pipeline.py    # Batch vector update pipeline & raycast processing
│   │   ├── neural_engine.py     # Micro-Elman RNN (16→12→7, 295 weights) forward inference
│   │   ├── morphology_engine.py # Polar geometry SAT collision & physical trait baking
│   │   ├── evolution_manager.py # Annealing λ(g), Abbott templates & polar crossover
│   │   ├── spatial_grid.py      # Vectorized spatial grid for fast proximity searches
│   │   ├── analytics.py         # TelemetryRing, macro metrics, demography & biodiversity
│   │   ├── safeguard_engine.py  # Extinction safeguards & Genesis miracles
│   │   ├── density_damping.py   # Soft-cap density damping (ξ)
│   │   ├── auth.py              # God passkey dependency & PBKDF2 cryptographic verification
│   │   ├── protocol.py          # Pydantic schemas shared between backend & frontend
│   │   ├── db.py                # SQLite WAL persistence for worlds, events, lineage & snapshots
│   │   ├── wiki.py              # Living Wiki, API documentation & guide routes
│   │   └── main.py              # FastAPI app, SimEngine thread, Hub broadcaster, REST & WebSocket
│   ├── tui/                     # Textual terminal client
│   └── tests/                   # Pytest test suite (503+ automated tests across 44 suites)
└── frontend/
    └── src/
        ├── analytics/           # Observatory & Macro Analytics Engine
        │   ├── Observatory.tsx  # Full-screen macro dashboard & tab container
        │   ├── MacroOverview.tsx # Demographics, vital health, biomass & speed sparklines
        │   ├── SociologyTab.tsx # Clan hegemony, trade caravans, wars & succession
        │   ├── EcologyTab.tsx   # Botanical diversity, soil health & trophic pyramid
        │   ├── CrisisTab.tsx    # Epidemic spread, starvation alerts & disaster logs
        │   ├── MutationLab.tsx  # Morphological phylogeny tree & 2D morphospace scatter
        │   ├── MetricCard.tsx   # Formatted metric card with trend badges
        │   └── Sparkline.tsx    # Lightweight SVG time-series sparkline
        ├── render/
        │   ├── CanvasRenderer.tsx # High-performance 60 FPS viewport with pointer controls
        │   ├── renderCore.ts      # Hardware-accelerated Canvas2D engine, LOD gates & scratch pools
        │   ├── webglRenderer.ts   # WebGL instanced sprite renderer & shaders
        │   ├── ClanPanel.tsx      # Live clan settlements, totems, and war records (memoized)
        │   ├── ChronicleFeed.tsx  # Filterable, scrollable real-time event log (memoized)
        │   ├── OverviewPanel.tsx  # Day-trend demographics, mortality, hegemon (memoized)
        │   ├── CasteChart.tsx     # Caste demographic distribution proportions
        │   ├── TrophicChart.tsx   # Biomass and trophic level distribution pyramid
        │   └── Collapsible.tsx    # Dynamic flex collapsible accordion component
        ├── components/
        │   ├── CreatureAvatar.tsx # SVG creature avatar with full phenotypic parity & radar
        │   └── ConfirmModal.tsx   # Confirmation dialogs for dangerous actions
        ├── clan/
        │   └── ClanDetails.tsx    # Clan profile, leader residence, founded day & casualty stats
        ├── history/
        │   └── WorldHistoryModal.tsx # Daily chronicle digest, wars, and AI Story export
        ├── god/
        │   ├── GodPanel.tsx       # Interactive Laws of Nature control drawer (6 macro domains)
        │   └── auth.tsx           # Passkey dialog and authorized godFetch client
        ├── inspect/
        │   └── Inspector.tsx      # Creature dossier, vitals, inventory & family tree
        ├── wiki/
        │   └── Wiki.tsx           # In-app interactive wiki & API playground
        ├── types.ts               # TypeScript schemas mirroring backend protocol
        ├── websocket.ts           # Auto-reconnecting WebSocket client
        └── App.tsx                # Main layout, HUD, WS sync, mobile drawer navigation
```

---

## Performance & Scale

- **Offscreen Elevation Grid Caching (§BL)**: The 15,000-cell elevation hillshade is pre-rendered once into an `OffscreenCanvas` bitmap and blitted with a single `ctx.drawImage()` call per frame, eliminating ~900,000 CPU rasterization calls and string parses per second (saving 10–15ms per frame).
- **Level-of-Detail (LOD) Gating (§BL)**: When zoomed out (`camScale < 3.2`), sub-pixel micro-phenotype decorations (blade glints, starburst coronas, genesis sparks, halos, auras, chromatic aberration) are automatically culled, eliminating draw-call saturation while keeping full fidelity when inspecting close-up.
- **Zero-Allocation Batching & Scratch Recycling (§BL)**: Reusable scratch arrays for all castes, crests, and dynamic groups persist across frames by resetting array lengths (`.length = 0`), reducing per-frame heap allocations by >85% and eliminating garbage collection stutters.
- **Decoupled React Virtual DOM (§BL)**: Non-critical DOM sidebars and HUD chips are throttled to ~4 Hz (250ms budget) while the 60 FPS Canvas 2D render loop advances uninhibited directly from mutable refs. Secondary panels (`ChronicleFeed`, `ClanPanel`, `OverviewPanel`) are guarded with `React.memo`.
- **Zero-Allocation Spatial Hash**: Pre-allocated 1D bucket list in `world.py` eliminates tuple allocations and dictionary re-hashing per tick; neighbor lookups use squared-distance early-exits.
- **Dedicated Engine Thread**: Simulation runs on a dedicated high-priority tick loop (`SimEngine` in `main.py`), completely isolating mathematical simulation advancement from asynchronous HTTP/WebSocket I/O.
- **Vectorized Structure-of-Arrays (SoA)**: `AgentSoA` stores agent positions, velocities, energies, and genetic traits in contiguous NumPy arrays for vectorized distance calculations and C-accelerated OpenMP batch processing.

---

## 🌐 Tri-Repository Architecture & Single-System Deployment (§BP)

Flatland is organized into three specialized GitHub repositories with unified same-system deployment:

```
┌──────────────────────────────────────────────────────────────────────────┐
│                             Flatland Ecosystem                           │
├──────────────────────────┬──────────────────────────┬────────────────────┤
│   flws (Backend Engine)  │ flws-web (Web Frontend)  │ flws-page (Private)│
│  FastAPI, Simulation     │ React 18, Vite, TS       │ Landing Showcase,  │
│  SimEngine OS Thread     │ Canvas2D 60 FPS Viewport │ Interactive Canvas │
│  NumPy SoA, Micro-RNN    │ Macro Observatory & HUD  │ Lore & CTA Portal  │
├──────────────────────────┼──────────────────────────┼────────────────────┤
│ Runs on Host:8000        │ Runs on Host:5173 / :80  │ Independent Docs   │
│ Docker: flatland-backend │ Docker: flatland-frontend│ GitHub Pages       │
│ Single-System Production │ Nginx Reverse Proxy      │ Marketing Site     │
└──────────────────────────┴──────────────────────────┴────────────────────┘
```

- **Unified Same-System Deployment**:
  - `docker-compose.yml` orchestrates **both** backend and frontend on the same host system. It supports parameterizing `${BACKEND_DIR:-./backend}` and `${FRONTEND_DIR:-./frontend}` (or sibling `../flws-web`).
  - `deploy.sh` automatically detects multi-repo directory structures, synchronizes code to the production server (`root@192.168.1.21`), compiles native OpenMP C kernels, builds the frontend bundle, and manages background services while preserving live world state.
- **Dual Independent GitHub Pages**:
  - **Web Client**: Deployed independently from `flws-web` to `https://longphanmn.github.io/flws-web/` (connects dynamically via WebSocket/REST to live backend servers).
  - **Landing Page**: Deployed independently from private `flws-page` to `https://longphanmn.github.io/flws-page/`.

---

## Authors & Attribution

- **Repositories**:
  - Backend Engine: [https://github.com/longphanmn/flws](https://github.com/longphanmn/flws)
  - Web Frontend Client: [https://github.com/longphanmn/flws-web](https://github.com/longphanmn/flws-web)
  - Landing Page (Private): [https://github.com/longphanmn/flws-page](https://github.com/longphanmn/flws-page)
- **Live Deployments**:
  - Web Simulation App: [https://longphanmn.github.io/flws-web/](https://longphanmn.github.io/flws-web/)
  - Landing Showcase: [https://longphanmn.github.io/flws-page/](https://longphanmn.github.io/flws-page/)
- **Developed by**: **[Long Phan](mailto:long@minhnhan.in)**  
  Email: [long@minhnhan.in](mailto:long@minhnhan.in)  
- **AI Tooling & Development**: Built and engineered with **OpenCode** and **Antigravity**.
- **Literary Source**: Based on the mathematical concept and social commentary of ***Flatland: A Romance of Many Dimensions*** by **Edwin A. Abbott** (1884).

---

## License

This project is open source and available under the [MIT License](LICENSE). See [LICENSE.md](LICENSE.md) for the full license text.
