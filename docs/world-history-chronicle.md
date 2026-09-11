# Flatland World History, Chronicle & AI Storytelling (§BM)

> **Landing Page**: [https://longphanmn.github.io/flatland/](https://longphanmn.github.io/flatland/)  
> **Source Code**: [https://github.com/longphanmn/flatland](https://github.com/longphanmn/flatland)  
> **Developed by [Long Phan](mailto:long@minhnhan.in)** ([long@minhnhan.in](mailto:long@minhnhan.in) · Demo: [world.minhnhan.in](https://world.minhnhan.in))  

Flatland features a comprehensive multi-era historiography, analytics, and AI storytelling suite designed to chronicle the epic rise, evolution, conflicts, and collapse of polygon civilizations.

---

## 1. Overview & Architecture

The historical record in Flatland operates across three coordinated tiers:
1. **SQLite Persistence (`history_events`, `creatures`, `clan_epitaphs`)**:
   - Every significant world event (wars, plagues, schisms, regicides, temple consecrations, miracles, cataclysms, extinctions) is captured with exact tick timestamps and rich payload data.
   - Deceased creatures are recorded with their personal names, titles, lifetime kill counts, and genealogical metadata.
   - Perished clans are recorded in the `clan_epitaphs` registry with lifespan ticks, peak populations, wars fought/won, temples built, and cause of extinction.

2. **FastAPI Historical REST APIs**:
   - `GET /api/history`: Filtered event stream with full-text keyword search (`q=`), major events filter (`major=true`), and clan filtering (`clan_id=`).
   - `GET /api/history/summary`: Day-bucketed timeline aggregation (events, casualties, outbreaks, schisms, temples) for sparklines and scrubbing.
   - `GET /api/annals`: Structured world milestones (Bloodiest Day, Worst Plague, First Temple, First Miracle, First Extinction, Hero, Villain).
   - `GET /api/clan/{clan_id}/biography`: Rich clan dossier covering lifespan, peak population, war win/loss record, schisms, temples, top arch-rival, and hero/villain notables.

3. **Frontend Presentation Suite**:
   - **Chronicle Feed (`ChronicleFeed.tsx`)**: Live and historical event stream with "Major Moments" top-5 dramatic days jump chips and exact tick jump navigation.
   - **World History Modal (`WorldHistoryModal.tsx`)**: Multi-tab analytical codex featuring Timeline Scrubber, Records & Legends Leaderboard, Clan Rivalry Matrix & Mortality Analytics, and In-App AI Story Generator.
   - **Clan Biography Card (`ClanDetails.tsx`)**: Dedicated "Bio" tab displaying comprehensive clan history, hall of notables, and deep linking.
   - **Creature Story Arc (`Inspector.tsx`)**: Hero's Journey story generator capturing individual life milestones from birth to grave.

---

## 2. Key Features

### 📅 Timeline Visualization & Epoch Navigation (BM-8 to BM-11)
- **Epoch Bar (`EpochBar.tsx`)**: Color-coded horizontal bar mapping world ages (Genesis, Age of Tribes, Feudal Era, Classical Zenith, Era of Ruin).
- **Crisis & Conflict Sparkline (`PopulationSparkline.tsx`)**: Population curve overlaid with red crisis markers for mass casualties and green markers for disease outbreaks.
- **Day Scrubber (`EpochBar.tsx`)**: Interactive slider to scrub smoothly across any day in the world's history.
- **War Arc Graph (`WarArcGraph.tsx`)**: Curved SVG link connectors visualizing clan vs clan warfare networks within individual days.

### 🏆 Records & Legends Leaderboard (BM-13)
Categorized historical records highlighting world-defining extremes:
- **Sovereign of War**: Deadliest clan by confirmed combat victories.
- **Deadliest Single Day**: Day with the highest lethal casualty count.
- **Greatest Realm**: Clan with the highest peak population at its zenith.
- **Divine Architects**: Clan that consecrated the most temples to the Sacred Sphere.
- **Greatest Schism**: Largest rebellion where dissidents fractured from a mother clan.
- **Legendary Hero & Infamous Villain**: Individual polygons remembered for battlefield prowess or treacherous coups.

### 📊 History Analytics & Deep Metrics (BM-14 to BM-16)
- **Clan Rivalry Heatmap Matrix (`HistoryAnalytics.tsx`)**: Two-dimensional war frequency matrix between all major clans.
- **Mortality Breakdown (`HistoryAnalytics.tsx`)**: Stacked percentage bar chart displaying causes of death (combat, starvation, old age, disease, cataclysms) across 10-day eras.
- **Faith & Devotion Index (`HistoryAnalytics.tsx`)**: Cumulative spiritual index tracking shrines, temples, and divine miracles over time.

### ✨ In-App AI Story Generator (BM-17, BM-18)
- **Direct LLM Integration**: Generates complete novelistic chapters directly in-browser using Google Gemini 1.5 Flash or OpenAI GPT-4o-mini.
- **Zero Server Storage**: API keys are stored solely in the user's browser `localStorage` and never transmitted to the Flatland backend.
- **Prompt Presets & Formats**: Supports Epic Novel Saga, Ancient Chronicle, Spiritual Lore, and Tragic Extinction styles in English, Vietnamese, and French.
- **Focused Mini-Stories**: Single-day story generator ("📖 Tell me about Day X") and individual creature Hero's Journey story arcs ("📖 Story Arc").

### 🔗 Deep Linking & Social Shareability (BM-19 to BM-21)
- **Deep-Link World Day (`?history=42`)**: Automatically opens the World History Modal focused on Day 42.
- **Deep-Link Clan History (`?clan=7`)**: Automatically opens the Clan Details modal on the Biography tab for Clan #7.
- **Share World Card (`ShareWorldCard.ts`)**: Generates high-resolution 1200×630 PNG social preview cards with world stats, top clans, milestones, and dark Abbott-style aesthetics.
