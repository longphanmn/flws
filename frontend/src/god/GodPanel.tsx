import React, { useEffect, useMemo, useRef, useState } from 'react'
import { godFetch } from './auth'
import { useI18n } from '../i18n'
import type { GodLaws } from '../types'
import { apiUrl } from '../config'


const GodPanelErrorFallback = ({ error, onReset }: { error: any; onReset: () => void }) => {
  const { t } = useI18n()
  return (
    <div style={{ padding: 16, color: '#f85149' }}>
      <h3 style={{ margin: '0 0 8px' }}>{t('god.ui.crashed')}</h3>
      <pre style={{ whiteSpace: 'pre-wrap', fontSize: 11, background: '#161b22', padding: 8, borderRadius: 6, border: '1px solid #30363d' }}>{String(error?.message ?? error)}</pre>
      <button onClick={onReset} style={{ marginTop: 8, padding: '6px 10px', background: '#21262d', border: '1px solid #30363d', borderRadius: 6, color: '#e6edf3', cursor: 'pointer' }}>{t('god.ui.retry')}</button>
    </div>
  )
}

class GodPanelErrorBoundary extends React.Component<{ children: React.ReactNode }, { hasError: boolean; error: any }> {
  state = { hasError: false, error: null as any }
  static getDerivedStateFromError(error: any) { return { hasError: true, error } }
  componentDidCatch(error: any, info: any) { console.error('[GodPanel] crash', error, info) }
  render() {
    if (this.state.hasError) {
      return <GodPanelErrorFallback error={this.state.error} onReset={() => this.setState({ hasError: false, error: null })} />
    }
    return this.props.children
  }
}

type NumberLawKey = Exclude<keyof GodLaws, 'boundary'>
type BoolLawKey = {
  [K in NumberLawKey]: GodLaws[K] extends boolean | undefined ? K : never
}[NumberLawKey]

interface LawSpec {
  key: NumberLawKey
  label: string
  min: number
  max: number
  step: number
  group: string
  gate?: BoolLawKey | BoolLawKey[]
  scale?: 'log'
  isAdvanced?: boolean
}

// §BN-1, §BN-9..15: Cleaned up parameters, consolidated groups, and marked log-scale / advanced controls
const NUMBER_LAWS: LawSpec[] = [
  // 1. Food & Agriculture (merged Food & Energy, Food Decay, Agriculture, Hunger & Sight)
  { key: 'food_count', label: 'Food abundance', min: 0, max: 1000, step: 5, group: 'Food & Agriculture' },
  { key: 'energy_max', label: 'Max energy', min: 10, max: 500, step: 5, group: 'Food & Agriculture' },
  { key: 'energy_decay_per_tick', label: 'Energy decay / tick', min: 0, max: 2, step: 0.01, group: 'Food & Agriculture' },
  { key: 'energy_from_food', label: 'Energy from food', min: 0, max: 100, step: 1, group: 'Food & Agriculture' },
  { key: 'food_lifespan_ticks', label: 'Food lifespan (ticks)', min: 100, max: 100000, step: 100, group: 'Food & Agriculture', gate: 'food_decay_enabled', scale: 'log' },
  { key: 'granary_capacity', label: 'Granary capacity', min: 0, max: 2000, step: 25, group: 'Food & Agriculture', gate: 'granaries_enabled' },
  { key: 'perceive_radius', label: 'Base sight radius', min: 1, max: 40, step: 0.5, group: 'Food & Agriculture' },

  // 2. Ecosystem & Flora
  { key: 'plant_growth_rate', label: 'Plant growth / tick', min: 0, max: 1, step: 0.01, group: 'Ecosystem & Flora' },
  { key: 'plant_spread_rate', label: 'Plant spread chance', min: 0, max: 1, step: 0.005, group: 'Ecosystem & Flora' },
  { key: 'poison_rate', label: 'Poison sprout chance', min: 0, max: 1, step: 0.01, group: 'Ecosystem & Flora', gate: 'plant_variants_enabled' },

  // 3. Movement & Lifespan
  { key: 'steer_turn', label: 'Turning agility', min: 0.05, max: 2, step: 0.05, group: 'Movement & Lifespan' },
  { key: 'lifespan_mult', label: 'Lifespan ×', min: 0.05, max: 5, step: 0.05, group: 'Movement & Lifespan' },

  // 4. Reproduction & Caste
  { key: 'birth_rate', label: 'Birth rate', min: 0, max: 1, step: 0.05, group: 'Reproduction & Caste', gate: 'birth_enabled' },
  { key: 'carrying_capacity', label: 'Carrying capacity', min: -1, max: 5000, step: 25, group: 'Reproduction & Caste', gate: 'birth_enabled' },
  { key: 'max_population', label: 'Hard pop cap', min: -1, max: 8000, step: 25, group: 'Reproduction & Caste', gate: 'birth_enabled' },
  { key: 'mutation_rate', label: 'Caste mutation rate', min: 0, max: 1, step: 0.01, group: 'Reproduction & Caste', gate: 'birth_enabled' },
  { key: 'mutation_heritability', label: 'Mutation heritability', min: 0, max: 1, step: 0.05, group: 'Reproduction & Caste', gate: 'birth_enabled' },
  { key: 'sex_ratio', label: 'Son probability', min: 0, max: 1, step: 0.05, group: 'Reproduction & Caste', gate: 'birth_enabled' },
  { key: 'adult_age', label: 'Adult age', min: 0, max: 5000, step: 50, group: 'Reproduction & Caste', gate: 'birth_enabled' },
  { key: 'max_sides', label: 'Max caste sides', min: 3, max: 64, step: 1, group: 'Reproduction & Caste', gate: 'birth_enabled' },
  { key: 'euthanasia_threshold', label: 'Euthanasia ≥', min: 0.3, max: 1, step: 0.05, group: 'Reproduction & Caste', gate: 'birth_enabled' },

  // 5. Population Safety (Safeguards & Density Soft-Cap Damping)
  { key: 'safeguard_critical_pop', label: 'Emergency pop floor (Kcrit)', min: 2, max: 50, step: 1, group: 'Population Safety', gate: 'safeguard_enabled' },
  { key: 'safeguard_relief_ratio', label: 'Relief threshold ratio (Ksafe)', min: 0.05, max: 0.50, step: 0.01, group: 'Population Safety', gate: 'safeguard_enabled', isAdvanced: true },
  { key: 'safeguard_genesis_batch', label: 'Genesis miracle batch', min: 1, max: 20, step: 1, group: 'Population Safety', gate: 'safeguard_enabled', isAdvanced: true },
  { key: 'damping_steepness', label: 'Damping steepness', min: 1.0, max: 20.0, step: 0.5, group: 'Population Safety', gate: 'soft_cap_enabled', isAdvanced: true },
  { key: 'crowding_stress_mult', label: 'Crowding stress mult', min: 0.0, max: 1.0, step: 0.05, group: 'Population Safety', gate: 'soft_cap_enabled', isAdvanced: true },
  { key: 'resource_strain_mult', label: 'Resource strain mult', min: 0.0, max: 2.0, step: 0.05, group: 'Population Safety', gate: 'soft_cap_enabled', isAdvanced: true },

  // 6. Evolution Engine (Neuroevolution & Morphology)
  { key: 'mutation_sigma', label: 'NN mutation σ', min: 0, max: 0.5, step: 0.01, group: 'Evolution Engine', isAdvanced: true },
  { key: 'crossover_rate', label: 'NN crossover rate', min: 0, max: 1, step: 0.05, group: 'Evolution Engine', isAdvanced: true },
  { key: 'morph_lambda_override', label: 'Manual λ override (-1 = auto)', min: -1.0, max: 1.0, step: 0.05, group: 'Evolution Engine', gate: 'morphology_annealing_enabled', isAdvanced: true },
  { key: 'vertex_mutation_std', label: 'Vertex jitter σr', min: 0.005, max: 0.20, step: 0.005, group: 'Evolution Engine', gate: 'morphology_annealing_enabled', isAdvanced: true },
  { key: 'angle_mutation_std', label: 'Angle jitter σφ', min: 0.005, max: 0.10, step: 0.005, group: 'Evolution Engine', gate: 'morphology_annealing_enabled', isAdvanced: true },
  { key: 'topological_mutation_rate', label: 'Topo mutation rate', min: 0.0, max: 0.10, step: 0.005, group: 'Evolution Engine', gate: 'morphology_annealing_enabled', isAdvanced: true },
  { key: 'annealing_start_generation', label: 'Morphology start gen', min: 0, max: 500, step: 5, group: 'Evolution Engine', gate: 'morphology_annealing_enabled', isAdvanced: true },
  { key: 'annealing_decay_generations', label: 'Morphology decay gens', min: 10, max: 5000, step: 25, group: 'Evolution Engine', gate: 'morphology_annealing_enabled', isAdvanced: true },

  // 7. Disease & Plague
  { key: 'disease_energy_drain', label: 'Energy drain / tick', min: 0, max: 2, step: 0.05, group: 'Disease & Plague', gate: 'disease_enabled' },
  { key: 'disease_outbreak_rate', label: 'Outbreak rate / tick', min: 0, max: 0.05, step: 0.0005, group: 'Disease & Plague', gate: 'disease_enabled', isAdvanced: true },
  { key: 'disease_rate', label: 'Contagion chance', min: 0, max: 1, step: 0.01, group: 'Disease & Plague', gate: 'disease_enabled', isAdvanced: true },
  { key: 'disease_lethality', label: 'Lethality', min: 0, max: 1, step: 0.05, group: 'Disease & Plague', gate: 'disease_enabled', isAdvanced: true },

  // 8. Climate & Shelter (merged Sky & Seasons, Weather Sickness, Shelter)
  { key: 'day_length', label: 'Day length (ticks)', min: 4, max: 20000, step: 4, group: 'Climate & Shelter', scale: 'log' },
  { key: 'season_length', label: 'Season length (ticks)', min: 4, max: 100000, step: 10, group: 'Climate & Shelter', scale: 'log' },
  { key: 'winter_food_mult', label: 'Winter food ×', min: 0.1, max: 1.5, step: 0.05, group: 'Climate & Shelter' },
  { key: 'night_sight_mult', label: 'Night sight ×', min: 0.05, max: 2, step: 0.05, group: 'Climate & Shelter' },
  { key: 'weather_change_rate', label: 'Weather turn chance', min: 0, max: 1, step: 0.001, group: 'Climate & Shelter', gate: 'weather_enabled' },
  { key: 'exposure_drain', label: 'Exposure drain / tick', min: 0, max: 2, step: 0.05, group: 'Climate & Shelter', gate: 'shelter_enabled' },
  { key: 'house_capacity', label: 'House capacity', min: 1, max: 20, step: 1, group: 'Climate & Shelter', gate: 'shelter_enabled' },
  { key: 'house_decay_ticks', label: 'House decay ticks', min: 100, max: 100000, step: 100, group: 'Climate & Shelter', gate: 'shelter_enabled', scale: 'log' },
  { key: 'rest_recovery_mult', label: 'Rest healing ×', min: 0.5, max: 5, step: 0.25, group: 'Climate & Shelter', gate: 'shelter_enabled' },
  { key: 'chill_drain', label: 'Chill drain / tick', min: 0, max: 5, step: 0.05, group: 'Climate & Shelter', gate: 'weather_sickness_enabled' },

  // 9. Combat & Survival (merged Clan War, Predation, Desperation)
  { key: 'attack_damage', label: 'Attack damage', min: 0, max: 200, step: 10, group: 'Combat & Survival', gate: 'war_enabled' },
  { key: 'predator_ratio', label: 'Predator ratio', min: 0, max: 1, step: 0.01, group: 'Combat & Survival', gate: 'predation_enabled' },
  { key: 'hunt_radius', label: 'Hunt radius', min: 1, max: 40, step: 1, group: 'Combat & Survival', gate: 'predation_enabled' },
  { key: 'bite_damage', label: 'Bite damage', min: 0, max: 200, step: 10, group: 'Combat & Survival', gate: 'predation_enabled' },
  { key: 'energy_from_prey', label: 'Energy from prey', min: 0, max: 200, step: 5, group: 'Combat & Survival', gate: 'predation_enabled' },
  { key: 'fear_radius', label: 'Fear radius', min: 1, max: 40, step: 1, group: 'Combat & Survival', gate: 'predation_enabled' },
  { key: 'cannibalism_energy', label: 'Energy per kill', min: 0, max: 200, step: 5, group: 'Combat & Survival', gate: 'cannibalism_enabled' },

  // 10. Society & Governance (merged Territory, Clan, Rebellion, Politics)
  { key: 'max_clans', label: 'Max clans', min: -1, max: 24, step: 1, group: 'Society & Governance' },
  { key: 'territory_radius', label: 'Territory radius', min: 1, max: 50, step: 1, group: 'Society & Governance', gate: 'territory_enabled' },
  { key: 'trespass_decay', label: 'Trespass decay / tick', min: 0, max: 5, step: 0.05, group: 'Society & Governance', gate: 'territory_enabled' },
  { key: 'larder_capacity', label: 'Larder capacity', min: 0, max: 2000, step: 25, group: 'Society & Governance', gate: 'resource_sharing_enabled' },
  { key: 'coalition_threshold', label: 'Coalition threshold', min: -100, max: 100, step: 5, group: 'Society & Governance', gate: 'coalitions_enabled' },
  { key: 'schism_threshold', label: 'Schism threshold', min: 0, max: 1, step: 0.05, group: 'Society & Governance', gate: 'schism_enabled' },

  // 11. Theology & Avatars
  { key: 'tithe_rate', label: 'Tithe rate', min: 0, max: 0.5, step: 0.01, group: 'Theology & Avatars', gate: 'theology_enabled' },
  { key: 'temple_faith_cost', label: 'Temple faith cost', min: 50, max: 5000, step: 50, group: 'Theology & Avatars', gate: 'theology_enabled' },
  { key: 'age_length', label: 'Age length (ticks)', min: 100, max: 1000000, step: 100, group: 'Theology & Avatars', gate: 'age_enabled', scale: 'log' },
  { key: 'culture_spread_rate', label: 'Culture spread / tick', min: 0, max: 1, step: 0.0005, group: 'Theology & Avatars', gate: 'culture_enabled' },

  // 12. Landscape & Elements
  { key: 'river_count', label: 'River count', min: 0, max: 8, step: 1, group: 'Landscape & Elements', gate: 'rivers_enabled' },

  // 13. Cosmology & Disasters
  { key: 'fire_rate', label: 'Fire ignite / tick', min: 0, max: 0.05, step: 0.0001, group: 'Cosmology & Disasters', gate: 'wildfire_enabled' },
  { key: 'disaster_rate', label: 'Disaster / tick', min: 0, max: 0.05, step: 0.0001, group: 'Cosmology & Disasters', gate: 'disaster_enabled' },
  { key: 'earthquake_rate', label: 'Quake rate / tick', min: 0, max: 0.001, step: 0.00001, group: 'Cosmology & Disasters', gate: 'earthquake_enabled' },
  { key: 'lightning_strike_rate', label: 'Bolt rate / storm tick', min: 0, max: 0.02, step: 0.0005, group: 'Cosmology & Disasters', gate: 'lightning_enabled' },
  { key: 'anomaly_count', label: 'Anomaly zones', min: 0, max: 8, step: 1, group: 'Cosmology & Disasters' },
]

/* 6 Macro Domains Consolidated into 13 Groups — §BN-9..15 */
interface DomainSpec { id: string; icon: string; label: string; shortLabel: string; groups: string[] }
const DOMAINS: DomainSpec[] = [
  { id: 'ecology', icon: '🌿', label: 'Ecology & Survival', shortLabel: 'Ecology', groups: ['Food & Agriculture', 'Ecosystem & Flora'] },
  { id: 'biology', icon: '🧬', label: 'Biology & Evolution', shortLabel: 'Biology', groups: ['Movement & Lifespan', 'Reproduction & Caste', 'Population Safety', 'Evolution Engine', 'Disease & Plague'] },
  { id: 'climate', icon: '☀️', label: 'Climate & Sky', shortLabel: 'Climate', groups: ['Climate & Shelter'] },
  { id: 'society', icon: '🏰', label: 'Society, Warfare & Trade', shortLabel: 'Society', groups: ['Combat & Survival', 'Society & Governance'] },
  { id: 'theology', icon: '🔮', label: 'Theology & Sacred Avatars', shortLabel: 'Theology', groups: ['Theology & Avatars'] },
  { id: 'physics', icon: '⚙️', label: 'World Physics & Disasters', shortLabel: 'Physics', groups: ['Landscape & Elements', 'Cosmology & Disasters'] },
]

const GROUP_KEY: Record<string, string> = {
  'Food & Agriculture': 'foodAgriculture',
  'Ecosystem & Flora': 'ecosystemFlora',
  'Movement & Lifespan': 'movementLifespan',
  'Reproduction & Caste': 'reproductionCaste',
  'Population Safety': 'populationSafety',
  'Evolution Engine': 'evolutionEngine',
  'Disease & Plague': 'diseasePlague',
  'Climate & Shelter': 'climateShelter',
  'Combat & Survival': 'combatSurvival',
  'Society & Governance': 'societyGovernance',
  'Theology & Avatars': 'theologyAvatars',
  'Landscape & Elements': 'landscapeElements',
  'Cosmology & Disasters': 'cosmologyDisasters',
}

const BOOL_DEFAULTS: Partial<Record<BoolLawKey, boolean>> = {
  birth_enabled: true,
  disease_enabled: false,
  weather_enabled: true,
  sleep_enabled: true,
  shelter_enabled: true,
  weather_sickness_enabled: false,
  territory_enabled: true,
  totems_enabled: true,
  succession_enabled: true,
  communication_enabled: true,
  knowledge_enabled: true,
  wildfire_enabled: false,
  disaster_enabled: false,
  culture_enabled: false,
  age_enabled: true,
  schism_enabled: true,
  plant_variants_enabled: true,
  predation_enabled: false,
  war_enabled: true,
  coalitions_enabled: true,
  leader_decisions_enabled: true,
  resource_sharing_enabled: true,
  cannibalism_enabled: true,
  eat_kin_enabled: true,
  food_decay_enabled: true,
  theology_enabled: true,
  agriculture_enabled: true,
  granaries_enabled: true,
  rivers_enabled: true,
  relief_enabled: true,
  structural_enabled: true,
  earthquake_enabled: false,
  lightning_enabled: true,
  morphology_annealing_enabled: true,
  safeguard_enabled: true,
  safeguard_morph_mercy: true,
  soft_cap_enabled: true,
}

const LAW_HINTS: Partial<Record<NumberLawKey, string>> = {
  food_count: 'The world keeps this much food alive — bounty or famine (winter ×0.5, summer ×1.2).',
  energy_max: 'Maximum metabolic energy capacity an organism can store before full saturation (10–500).',
  energy_decay_per_tick: 'Baseline metabolic burn rate per tick without food intake; shelter and infancy reduce decay.',
  energy_from_food: 'Base energy yield from harvesting a mature plant (berry 48, grass 32, mushroom 24, poison 8).',
  food_lifespan_ticks: 'Ticks a mature plant lives before naturally withering into the living soil grid.',
  granary_capacity: 'Units of food a settlement granary can store; sated harvesters deposit grain and berries.',
  perceive_radius: 'Base perception sight radius; scaled by caste (Woman 0.8×, Priest 1.35×), night (0.6×), and fog.',
  plant_growth_rate: 'How fast sprouted plants mature into harvestable food; seasons and rain accelerate growth.',
  plant_spread_rate: 'Probability per tick that a mature plant drops seeds into adjacent fertile ground.',
  poison_rate: 'Chance a new wild sprout is poisonous (-30 HP damage on ingestion).',
  steer_turn: 'Maximum heading angular turn rate per tick, dynamically scaled by creature moment of inertia (Izz).',
  lifespan_mult: 'Multiplier scaling all caste lifespans (Woman: 4,800 ticks → Priest: 9,000 ticks).',
  birth_rate: 'Base reproduction probability per eligible mating pair per tick when energy and adult age are met.',
  carrying_capacity: 'Population density threshold above which fertility begins to gradually diminish.',
  max_population: 'Hard global population cap preventing any new births until density declines.',
  mutation_rate: 'Probability a newborn son deviates ±1 side from classical caste inheritance.',
  mutation_heritability: 'Fraction of parental irregularity inherited by offspring; lower values prevent rapid mutation spread.',
  sex_ratio: 'Probability a child is a son (ascending regular polygon) vs daughter (agile line).',
  adult_age: 'Ticks required for an infant/juvenile to mature into a sexually fertile adult (220 ticks).',
  max_sides: 'Upper limit on regular polygon vertex ascendance (up to Priest / Circle status).',
  euthanasia_threshold: 'Irregularity threshold; deformed infants exceeding this are consumed at adulthood.',
  safeguard_critical_pop: 'Population floor Kcrit (≤12) triggering emergency Tier 3 Genesis miracles from The Sphere.',
  safeguard_relief_ratio: 'Carrying capacity ratio Ksafe = carrying × ratio (0.30) below which Tier 1/2 relief scales activate.',
  safeguard_genesis_batch: 'Number of pristine regular polygon beings created per Tier 3 Genesis miracle.',
  damping_steepness: 'Divisor coefficient damping birth rate as population overshoots carrying capacity (1/(1+d*xi^2)).',
  crowding_stress_mult: 'Multiplier scaling metabolic energy drain under overpopulation density stress (1+c*xi).',
  resource_strain_mult: 'Multiplier scaling plant growth & spread slowdown under overpopulation strain (1/(1+r*xi)).',
  mutation_sigma: 'Gaussian mutation standard deviation (σ) applied to genome weights during crossover.',
  crossover_rate: 'Probability of uniform 50/50 parental genome blending during sexual reproduction.',
  annealing_start_generation: 'Generation where polar morphology begins decaying from Abbott templates (higher = delays speciation).',
  annealing_decay_generations: 'Generations over which polar morphology annealing decays from Abbott templates to free evolution (higher = slower speciation).',
  morph_lambda_override: 'Manually pin morphology λ weight (1.0 = strict classical, 0.0 = freeform divergence, -1 = auto annealing).',
  vertex_mutation_std: 'Radial jitter magnitude σr applied to polar genome radii when offspring are born (lower = subtle shapes).',
  angle_mutation_std: 'Angular jitter magnitude σφ applied to polar genome vertex angles (lower = subtle angles).',
  topological_mutation_rate: 'Probability of adding or removing vertices during reproduction (lower = slower topological speciation).',
  disease_energy_drain: 'Metabolic energy drained per tick from infected creatures.',
  disease_outbreak_rate: 'Spontaneous plague outbreak probability per tick during crowded or unsanitary conditions.',
  disease_rate: 'Transmission rate of contagion when in close contact with an infected organism.',
  disease_lethality: 'Direct health (HP) damage dealt per tick to actively diseased creatures.',
  day_length: 'Total duration in ticks of a single diurnal day/night cycle (2400 ticks).',
  season_length: 'Duration in ticks of each season (Spring, Summer, Autumn, Winter).',
  winter_food_mult: 'Winter food abundance multiplier (0.7 gentle, 0.5 harsh, 0.3 extinction collapse).',
  night_sight_mult: 'Perception radius multiplier during night ticks for non-nocturnal castes.',
  weather_change_rate: 'Frequency of meteorological transitions between clear, rain, fog, and storm.',
  exposure_drain: 'Health and energy drain per tick when outdoors during harsh storms, heavy rain, or freezing winter.',
  house_capacity: 'Bed capacity inside a settlement hall; excess members sleep outdoors or search for other roofs.',
  house_decay_ticks: 'Ticks before an abandoned, roofless house crumbles into ruins.',
  rest_recovery_mult: 'Health regeneration multiplier when sleeping indoors under a roof.',
  chill_drain: 'Direct health drain per tick when chilled outdoors without shelter.',
  attack_damage: 'Base damage dealt by soldiers and warriors in inter-clan battles.',
  predator_ratio: 'Fraction of population spawned as predatory carnivores hunting prey.',
  hunt_radius: 'Aggro detection radius within which carnivores and war parties acquire targets.',
  bite_damage: 'Combat damage dealt per carnivore attack or predatory strike.',
  energy_from_prey: 'Caloric energy extracted from slaying and eating a prey creature.',
  fear_radius: 'Distance at which herbivores and vulnerable castes detect threats and execute evasion.',
  cannibalism_energy: 'Energy gained by starving creatures resorting to eating fallen kin or rivals.',
  max_clans: 'Maximum number of sovereign clans spawned during world initialization.',
  territory_radius: 'Radius of clan territorial influence around settlement houses; trespass sours diplomacy.',
  trespass_decay: 'Diplomatic relation points lost per tick when a rival clan enters marked territory.',
  larder_capacity: 'Energy capacity of settlement communal food stores where surplus is shared.',
  coalition_threshold: 'Diplomatic trust score required for two friendly clans to form a defensive coalition.',
  schism_threshold: 'Dissatisfaction fraction (hunger, homelessness) triggering a factional clan schism.',
  tithe_rate: 'Fraction of energy devout worshippers offer at shrines each dawn & dusk to build clan faith.',
  temple_faith_cost: 'Faith points required to consecrate a glowing Temple of the Sphere.',
  age_length: 'Ticks per historical age (Golden Age, Ice Age, Age of Chaos, Age of Plague).',
  culture_spread_rate: 'Rate at which allied clans sharing borders adopt common cultural traits and beliefs.',
  river_count: 'Number of procedural river channels carved across the terrain at world generation.',
  fire_rate: 'Probability per tick that a mature plant ignites during dry spells or lightning strikes.',
  disaster_rate: 'Stochastic probability of catastrophic environmental disasters (meteors, deluges).',
  earthquake_rate: 'Frequency of seismic quakes that crack buildings and shake terrain.',
  lightning_strike_rate: 'Frequency of deadly electrical arc strikes during thunder storms.',
  anomaly_count: 'Number of mysterious spatial anomaly zones altering local physics.',
}

const BOOL_HINTS: Partial<Record<BoolLawKey, string>> = {
  birth_enabled: 'Master switch enabling reproduction, mating, and generational ascendance.',
  disease_enabled: 'Enables contagious pathogen transmission, quarantine behavior, and priestly healing.',
  weather_enabled: 'Enables dynamic meteorological cycles (sun, rain, fog, storms).',
  sleep_enabled: 'Enables diurnal sleep cycles, house resting, and oral lore transfer.',
  shelter_enabled: 'Enables walled house mechanics, door navigation, and roof protection.',
  weather_sickness_enabled: 'Enables exposure chill and hypothermia when caught unsheltered in rain or winter.',
  territory_enabled: 'Enables clan boundary markings, territory defence, and trespass penalties.',
  totems_enabled: 'Enables Sacred Avatar totem blessings for each clan settlement.',
  succession_enabled: 'Enables dynamic governance leadership transfers on chieftain death.',
  communication_enabled: 'Enables vocalizations, alarm chirps, peace hums, and emotional thought bubbles.',
  knowledge_enabled: 'Enables spatial memory, waypoint mapping, and rumor broadcasting among kin.',
  wildfire_enabled: 'Enables combustive flame propagation across dense vegetation and forests.',
  disaster_enabled: 'Enables cataclysmic meteors, floods, and natural world disturbances.',
  culture_enabled: 'Enables traditions, governance archetypes, and cultural diffusion.',
  age_enabled: 'Enables historical epoch progression (Golden Age, Ice Age, Age of Chaos, Age of Plague).',
  schism_enabled: 'Enables internal clan fractures when members starve or lack shelter.',
  plant_variants_enabled: 'Enables botanical diversity across 6 distinct functional plant species.',
  predation_enabled: 'Enables carnivorous predator-prey ecology and hunting dynamics.',
  war_enabled: 'Enables inter-clan warfare, tactical raids, and territorial conquest.',
  coalitions_enabled: 'Enables mutual defensive alliances and diplomatic treaties.',
  leader_decisions_enabled: 'Enables chieftain governance bylaws (rationing, martial law, war declarations).',
  resource_sharing_enabled: 'Enables communal larders and altruistic basket food sharing.',
  cannibalism_enabled: 'Enables desperate consumption of the living during extreme starvation.',
  eat_kin_enabled: 'Allows consumption of deceased or weak clanmates at the cost of tribal exile and feuds.',
  food_decay_enabled: 'Enables mature plants to wither over time and fertilize the living soil.',
  theology_enabled: 'Enables the 8 Sacred Avatars, shrines, temples, miracles, and divine tithes.',
  agriculture_enabled: 'Enables seed gathering, farm plots, irrigation furrows, and agricultural tending.',
  granaries_enabled: 'Enables communal settlement granaries to stockpile grains and berries against winter.',
  rivers_enabled: 'Enables water channels, fords, water currents, bridges, and dams.',
  relief_enabled: 'Enables topographical elevation, slope inertia, cliffs, and road packing.',
  structural_enabled: 'Enables weather wear on buildings, builder repairs, and roof collapse into rubble.',
  earthquake_enabled: 'Enables seismic tremors that shake terrain and damage weakened structures.',
  lightning_enabled: 'Enables real lightning strikes during storms that ignite fires and damage creatures.',
  morphology_annealing_enabled: 'Enables polar genome evolution transitioning from Abbott templates to free morphology.',
  safeguard_enabled: 'Enables emergency Sphere safeguards preventing total extinction of species.',
  soft_cap_enabled: 'Enables density-dependent soft-cap damping on birth rates and metabolic strain.',
}

// §BN-16: Logarithmic scale conversion helpers for huge-range parameters
function valToSlider(val: number, min: number, max: number, scale?: 'log'): number {
  if (scale !== 'log' || min <= 0 || max <= min) {
    return max === min ? 0 : Math.max(0, Math.min(1000, ((val - min) / (max - min)) * 1000))
  }
  const safeVal = Math.max(min, Math.min(max, val))
  return Math.max(0, Math.min(1000, (Math.log(safeVal / min) / Math.log(max / min)) * 1000))
}

function sliderToVal(sliderPos: number, min: number, max: number, step: number, scale?: 'log'): number {
  if (scale !== 'log' || min <= 0 || max <= min) {
    const raw = min + (sliderPos / 1000) * (max - min)
    return Math.round(raw / step) * step
  }
  const frac = Math.max(0, Math.min(1, sliderPos / 1000))
  const raw = min * Math.pow(max / min, frac)
  if (step >= 1) return Math.round(raw)
  return Number(raw.toFixed(step < 0.01 ? 3 : 2))
}

function Switch({ checked, onChange, title }: { checked: boolean; onChange: (v: boolean) => void; title?: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      title={title}
      onClick={() => onChange(!checked)}
      className="god-switch-btn"
      style={{
        width: 38,
        height: 22,
        minHeight: 22,
        maxHeight: 22,
        borderRadius: 11,
        background: checked ? '#238636' : '#21262d',
        border: `1px solid ${checked ? '#2ea043' : '#30363d'}`,
        position: 'relative',
        cursor: 'pointer',
        flex: 'none',
        padding: 0,
        margin: 0,
        transition: 'background .15s',
      }}
    >
      <span
        style={{
          position: 'absolute',
          top: 2,
          left: checked ? 18 : 2,
          width: 16,
          height: 16,
          borderRadius: '50%',
          background: '#e6edf3',
          boxShadow: '0 1px 2px rgba(0,0,0,0.4)',
          transition: 'left .15s',
          display: 'block',
        }}
      />
    </button>
  )
}

interface Props { open: boolean; onClose: () => void }

const PRESET_META: Record<string, { color: string; border: string; bg: string; badge?: string }> = {
  balance: { color: '#e3b341', border: '#d29922', bg: 'rgba(227, 179, 65, 0.15)', badge: 'DEFAULT' },
  sustainable: { color: '#3fb950', border: '#2ea043', bg: 'rgba(63, 185, 80, 0.15)' },
  theocracy: { color: '#bc8cff', border: '#a371f7', bg: 'rgba(188, 140, 255, 0.15)' },
  warlords: { color: '#f0883e', border: '#d26a1b', bg: 'rgba(240, 136, 62, 0.15)' },
  chaos: { color: '#f85149', border: '#da3633', bg: 'rgba(248, 81, 73, 0.15)' },
  extinction: { color: '#ff7b72', border: '#f85149', bg: 'rgba(255, 123, 114, 0.15)' },
  boom: { color: '#79c0ff', border: '#388bfd', bg: 'rgba(121, 192, 255, 0.15)' },
}

const PRESET_BADGES: Record<string, string[]> = {
  balance: ['Food: 300', 'Winter: 0.80×', 'Cap: 400'],
  sustainable: ['Food: 550 (Abundant)', 'Winter: 0.85×', 'Cap: 550'],
  theocracy: ['Food: 400 (Faith)', 'Winter: 0.80×', 'Cap: 500'],
  warlords: ['Food: 340 (War)', 'Winter: 0.70×', 'Cap: 450'],
  chaos: ['Food: 320 (Scarce)', 'Winter: 0.55× (Harsh)', 'Cap: 350'],
  extinction: ['Food: 120 (Harsh)', 'Winter: 0.30× (Cold)', 'Cap: 180'],
  boom: ['Food: 440 (Boom)', 'Winter: 0.85×', 'Cap: 800'],
}

const PRESET_IMPACT: Record<string, string> = {
  balance: '⚖ Stable equilibrium — all 15+ mechanics harmonized',
  sustainable: '🌿 Flourishing growth — rich fields, full granaries, calm winters',
  theocracy: '🔮 Divine devotion — miracles, temples & sacred resonance',
  warlords: '⚔️ Martial age — conquests, alliances & plundered larders',
  chaos: '🔥 Turmoil — predators, plague, fire & quakes test survival',
  extinction: '💀 Collapse — famine, chill & cannibalism cull the weak',
  boom: '🚀 Metropolis — rapid births, bumper harvests & grand settlements',
}

function detectPreset(laws: GodLaws, presetsDetails?: Record<string, Record<string, any>>): string | null {
  if (presetsDetails) {
    for (const [name, p] of Object.entries(presetsDetails)) {
      if (Object.entries(p).every(([k, v]) => (laws as any)[k] === v)) return name
    }
    for (const [name, p] of Object.entries(presetsDetails)) {
      if (
        laws.food_count === p.food_count &&
        laws.carrying_capacity === p.carrying_capacity &&
        laws.max_population === p.max_population
      ) return name
    }
  }
  if (laws.food_count === 300 && laws.carrying_capacity === 400) return 'balance'
  if (laws.food_count === 550 && laws.carrying_capacity === 550) return 'sustainable'
  if (laws.food_count === 400 && laws.carrying_capacity === 500) return 'theocracy'
  if (laws.food_count === 340 && laws.carrying_capacity === 450) return 'warlords'
  if (laws.food_count === 320 && laws.carrying_capacity === 350) return 'chaos'
  if (laws.food_count === 120 && laws.carrying_capacity === 180) return 'extinction'
  if (laws.food_count === 440 && laws.carrying_capacity === 800) return 'boom'
  return null
}

function getZone(value: number, baseline: number | undefined, min: number, max: number): 'safe' | 'strained' | 'extreme' {
  if (baseline === undefined || baseline === null) return 'safe'
  const range = max - min
  if (range === 0) return 'safe'
  const dist = Math.abs(value - baseline) / range
  if (dist < 0.15) return 'safe'
  if (dist < 0.32) return 'strained'
  return 'extreme'
}

interface ChangeEntry {
  key: string
  label: string
  from: any
  to: any
  time: string
}

const DRAFT_KEY = 'fl_god_laws_draft'

function GodPanelInner({ open, onClose }: Props) {
  const { t } = useI18n()
  const [laws, setLaws] = useState<GodLaws>({})
  const [baselineLaws, setBaselineLaws] = useState<GodLaws>({})
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [currentPreset, setCurrentPreset] = useState<string | null>('balance')
  const [expandedPreset, setExpandedPreset] = useState<string | null>('balance')
  const [presetsDetails, setPresetsDetails] = useState<Record<string, Record<string, any>> | null>(null)
  const [activeSection, setActiveSection] = useState<'presets' | 'laws'>(() => {
    try { return (sessionStorage.getItem('god-section') as 'presets' | 'laws') || 'presets' } catch { return 'presets' }
  })
  const [isMobile, setIsMobile] = useState(() => typeof window !== 'undefined' && window.innerWidth <= 768)
  const [searchQuery, setSearchQuery] = useState('')
  const [showModifiedOnly, setShowModifiedOnly] = useState(false)
  const [filterRiskOnly, setFilterRiskOnly] = useState(false)
  const [openHint, setOpenHint] = useState<string | null>(null)
  const [activeDomain, setActiveDomain] = useState<string>(() => {
    try { return sessionStorage.getItem('god-domain') || 'ecology' } catch { return 'ecology' }
  })

  // §BN-23: LocalStorage Draft Persistence
  const [draftBanner, setDraftBanner] = useState<{ laws: GodLaws; date: string } | null>(null)

  // §BN-24: JSON Export/Import
  const [showImportModal, setShowImportModal] = useState(false)
  const [importText, setImportText] = useState('')
  const [importError, setImportError] = useState<string | null>(null)
  const [exportedCopied, setExportedCopied] = useState(false)

  // §BN-25: Session Change Log
  const [changeLog, setChangeLog] = useState<ChangeEntry[]>([])
  const [showChangeLog, setShowChangeLog] = useState(false)

  // §BN-26: Undo/Redo Stack
  const [undoStack, setUndoStack] = useState<GodLaws[]>([])
  const [redoStack, setRedoStack] = useState<GodLaws[]>([])

  // Touch step repeating refs (§BN-21)
  const stepTimerRef = useRef<any>(null)
  const stepIntervalRef = useRef<any>(null)

  useEffect(() => {
    try { sessionStorage.setItem('god-section', activeSection) } catch { /* ignore */ }
  }, [activeSection])

  useEffect(() => {
    try { sessionStorage.setItem('god-domain', activeDomain) } catch { /* ignore */ }
  }, [activeDomain])

  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth <= 768)
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  // Load laws & presets on open
  useEffect(() => {
    if (!open) return
    setLoading(true)
    setError(null)
    Promise.all([
      fetch('/api/laws').then((r) => r.json()),
      fetch('/api/presets').then((r) => r.json()).catch(() => null),
    ])
      .then(([lawsData, presetsData]) => {
        setLaws(lawsData)
        setBaselineLaws(lawsData)
        setUndoStack([])
        setRedoStack([])
        if (presetsData?.details) setPresetsDetails(presetsData.details)
        const detected = presetsData?.current || detectPreset(lawsData, presetsData?.details) || 'balance'
        setCurrentPreset(detected)
        setExpandedPreset(detected)

        // Check for saved draft in localStorage
        try {
          const rawDraft = localStorage.getItem(DRAFT_KEY)
          if (rawDraft) {
            const parsed = JSON.parse(rawDraft)
            if (parsed?.laws && Object.keys(parsed.laws).length > 0) {
              const differs = Object.entries(parsed.laws).some(([k, v]) => (lawsData as any)[k] !== v)
              if (differs) {
                setDraftBanner({ laws: parsed.laws, date: parsed.date || 'earlier session' })
              }
            }
          }
        } catch { /* ignore */ }
      })
      .catch(() => setError('failed to load laws'))
      .finally(() => setLoading(false))
  }, [open])

  // §BN-23: Save draft on changes (if modified from baseline)
  useEffect(() => {
    if (loading || Object.keys(laws).length === 0) return
    try {
      const isMod = Object.keys(laws).some((k) => (laws as any)[k] !== (baselineLaws as any)[k])
      if (isMod) {
        localStorage.setItem(DRAFT_KEY, JSON.stringify({ laws, date: new Date().toLocaleTimeString() }))
      } else {
        localStorage.removeItem(DRAFT_KEY)
      }
    } catch { /* ignore */ }
  }, [laws, baselineLaws, loading])

  // §BN-26: Keyboard shortcuts for Undo/Redo
  useEffect(() => {
    if (!open) return
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'z') {
        if (e.shiftKey) {
          e.preventDefault()
          handleRedo()
        } else {
          e.preventDefault()
          handleUndo()
        }
      } else if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'y') {
        e.preventDefault()
        handleRedo()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [open, undoStack, redoStack, laws])

  const recordChange = (prev: GodLaws, _next: GodLaws, key: string, label: string, from: any, to: any) => {
    setUndoStack((s) => [...s, prev].slice(-50))
    setRedoStack([])
    const now = new Date()
    const timeStr = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`
    setChangeLog((c) => [{ key, label, from, to, time: timeStr }, ...c].slice(0, 50))
  }

  const handleUndo = () => {
    if (undoStack.length === 0) return
    const prev = undoStack[undoStack.length - 1]
    setUndoStack((s) => s.slice(0, -1))
    setRedoStack((s) => [...s, laws])
    setLaws(prev)
    setCurrentPreset(detectPreset(prev, presetsDetails ?? undefined))
  }

  const handleRedo = () => {
    if (redoStack.length === 0) return
    const next = redoStack[redoStack.length - 1]
    setRedoStack((s) => s.slice(0, -1))
    setUndoStack((s) => [...s, laws])
    setLaws(next)
    setCurrentPreset(detectPreset(next, presetsDetails ?? undefined))
  }

  const set = (key: NumberLawKey, raw: string | number) => {
    const val = raw === '' ? undefined : Number(raw)
    const oldVal = (laws as any)[key]
    if (oldVal === val) return
    const updated = { ...laws, [key]: val }
    recordChange(laws, updated, key, key, oldVal, val)
    setLaws(updated)
    setCurrentPreset(detectPreset(updated, presetsDetails ?? undefined))
  }

  const revertOne = (key: NumberLawKey) => {
    const base = (baselineLaws as any)[key]
    if (base === undefined || (laws as any)[key] === base) return
    const updated = { ...laws, [key]: base }
    recordChange(laws, updated, key, `Revert ${key}`, (laws as any)[key], base)
    setLaws(updated)
    setCurrentPreset(detectPreset(updated, presetsDetails ?? undefined))
  }

  const stepVal = (key: NumberLawKey, min: number, max: number, step: number, dir: 1 | -1, scale?: 'log') => {
    const raw = laws[key]
    const curr = (typeof raw === 'number' && !isNaN(raw)) ? raw : min
    let next: number
    if (scale === 'log' && min > 0) {
      const pos = valToSlider(curr, min, max, 'log')
      const nextPos = Math.max(0, Math.min(1000, pos + dir * 25))
      next = sliderToVal(nextPos, min, max, step, 'log')
    } else {
      next = Math.max(min, Math.min(max, Number((curr + dir * step).toFixed(4))))
    }
    set(key, next)
  }

  const startStepHold = (key: NumberLawKey, min: number, max: number, step: number, dir: 1 | -1, scale?: 'log') => {
    stepVal(key, min, max, step, dir, scale)
    stopStepHold()
    stepTimerRef.current = setTimeout(() => {
      stepIntervalRef.current = setInterval(() => {
        stepVal(key, min, max, step, dir, scale)
      }, 100)
    }, 250)
  }

  const stopStepHold = () => {
    if (stepTimerRef.current) clearTimeout(stepTimerRef.current)
    if (stepIntervalRef.current) clearInterval(stepIntervalRef.current)
    stepTimerRef.current = null
    stepIntervalRef.current = null
  }

  const boolVal = (k: BoolLawKey) => laws[k] ?? BOOL_DEFAULTS[k] ?? false

  const setBool = (k: BoolLawKey, v: boolean) => {
    const oldVal = boolVal(k)
    if (oldVal === v) return
    const updated = { ...laws, [k]: v }
    recordChange(laws, updated, k, k, oldVal, v)
    setLaws(updated)
    setCurrentPreset(detectPreset(updated, presetsDetails ?? undefined))
  }

  const gateOpen = (gate?: BoolLawKey | BoolLawKey[]) =>
    !gate || (Array.isArray(gate) ? gate : [gate]).every((g) => boolVal(g))

  const modifiedKeys = useMemo(() => {
    const set = new Set<string>()
    for (const spec of NUMBER_LAWS) {
      const cur = (laws as any)[spec.key]
      const base = (baselineLaws as any)[spec.key]
      if (cur !== undefined && base !== undefined && cur !== base) set.add(spec.key)
      else if ((cur === undefined) !== (base === undefined) && cur !== base) set.add(spec.key)
    }
    for (const k of Object.keys(BOOL_DEFAULTS) as BoolLawKey[]) {
      if ((laws as any)[k] !== undefined && (laws as any)[k] !== (baselineLaws as any)[k]) set.add(k)
    }
    return set
  }, [laws, baselineLaws])

  const q = searchQuery.trim().toLowerCase()
  const presetKeys = ['balance','sustainable','theocracy','warlords','chaos','extinction','boom'] as const

  // §BN-27: Cross-tab search matches
  const matchingPresets = useMemo(() => {
    if (!q) return []
    return presetKeys.filter((key) => {
      const label = (t(`god.presets.${key}`) || '').toLowerCase()
      const subtitle = (t(`god.presets.${key}Subtitle`) || '').toLowerCase()
      const desc = (t(`god.presets.${key}Desc`) || '').toLowerCase()
      return label.includes(q) || subtitle.includes(q) || desc.includes(q) || key.includes(q)
    })
  }, [q, presetKeys, t])

  const matchesSearch = (spec: LawSpec): boolean => {
    if (!q) return true
    const hint = (LAW_HINTS[spec.key] || '').toLowerCase()
    const label = spec.label.toLowerCase()
    const group = spec.group.toLowerCase()
    const key = spec.key.toLowerCase()
    return label.includes(q) || hint.includes(q) || group.includes(q) || key.includes(q)
  }

  const filteredSpecs = (specs: LawSpec[], includeAdvanced: boolean = false) => {
    let out = specs.filter((s) => includeAdvanced || !s.isAdvanced)
    out = out.filter(matchesSearch)
    if (showModifiedOnly) out = out.filter((s) => modifiedKeys.has(s.key))
    if (filterRiskOnly) {
      out = out.filter((s) => {
        const curVal = (typeof laws[s.key] === 'number') ? (laws[s.key] as number) : s.min
        const baseVal = (typeof baselineLaws[s.key] === 'number') ? (baselineLaws[s.key] as number) : undefined
        return getZone(curVal, baseVal, s.min, s.max) === 'extreme'
      })
    }
    return out
  }

  const riskKeysCount = useMemo(() => {
    return NUMBER_LAWS.filter((s) => {
      const curVal = (typeof laws[s.key] === 'number') ? (laws[s.key] as number) : s.min
      const baseVal = (typeof baselineLaws[s.key] === 'number') ? (baselineLaws[s.key] as number) : undefined
      return getZone(curVal, baseVal, s.min, s.max) === 'extreme'
    }).length
  }, [laws, baselineLaws])

  // §BN-17: Master Feature Toggle Component
  const MasterToggleCard = ({
    k,
    icon,
    label,
    desc,
  }: {
    k: BoolLawKey
    icon: string
    label: string
    desc: string
  }) => {
    const active = boolVal(k)
    return (
      <div className={`god-master-toggle ${active ? 'active' : ''}`}>
        <div className="god-master-toggle-info">
          <span className="god-master-toggle-title">
            <span style={{ fontSize: 16 }}>{icon}</span>
            {t(`godToggles.${k}`) !== `godToggles.${k}` ? t(`godToggles.${k}`) : label}
          </span>
          <span className="god-master-toggle-desc">
            {t(`godToggles.${k}Hint`) !== `godToggles.${k}Hint` ? t(`godToggles.${k}Hint`) : (BOOL_HINTS[k] || desc)}
          </span>
        </div>
        <Switch checked={active} onChange={(v) => setBool(k, v)} title={label} />
      </div>
    )
  }

  const ToggleRow = ({ k, label, title, hideIfOff }: { k: BoolLawKey; label: string; title?: string; hideIfOff?: BoolLawKey | BoolLawKey[] }) => {
    if (hideIfOff && !gateOpen(hideIfOff)) return null
    const getTrLabel = () => {
      if (t(`godToggles.${k}`) !== `godToggles.${k}` ? t(`godToggles.${k}`) : undefined) return t(`godToggles.${k}`)
      if (t(`godLaws.${k}`) !== `godLaws.${k}` ? t(`godLaws.${k}`) : undefined) return t(`godLaws.${k}`)
      return label
    }
    const getTrTitle = () => {
      if (t(`godToggles.${k}Hint`) !== `godToggles.${k}Hint` ? t(`godToggles.${k}Hint`) : undefined) return t(`godToggles.${k}Hint`)
      if (t(`godHints.${k}`) !== `godHints.${k}` ? t(`godHints.${k}`) : undefined) return t(`godHints.${k}`)
      return title || BOOL_HINTS[k] || ''
    }
    const trLabel = getTrLabel()
    const trTitle = getTrTitle()
    if (showModifiedOnly && !modifiedKeys.has(k)) {
      if (q) {
        const trLabel2 = trLabel.toLowerCase()
        const trTitle2 = trTitle.toLowerCase()
        if (!trLabel2.includes(q) && !trTitle2.includes(q) && !k.includes(q)) return null
      } else return null
    }
    if (q) {
      const trLabel2 = trLabel.toLowerCase()
      const trTitle2 = trTitle.toLowerCase()
      if (!trLabel2.includes(q) && !trTitle2.includes(q) && !k.includes(q)) return null
    }
    const isMod = modifiedKeys.has(k)
    const isOpen = openHint === k
    return (
      <div style={{ borderBottom: '1px solid #21262d', background: isMod ? 'rgba(227,179,65,0.06)' : undefined, borderLeft: isMod ? '2px solid #d29922' : '2px solid transparent' }}>
        <div className="god-row god-toggle-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, padding: '9px 12px' }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <span title={trTitle} style={{ color: isMod ? '#e3b341' : '#e6edf3', fontSize: 13, fontWeight: isMod ? 600 : 500, display: 'inline-flex', alignItems: 'center', gap: 6 }}>
              {trLabel}
            </span>
            {isMod && <span style={{ fontSize: 9, padding: '1px 5px', borderRadius: 4, background: '#d29922', color: '#0d1117', fontWeight: 800 }}>MOD</span>}
            {trTitle && (
              <button
                type="button"
                className={`god-hint-btn ${isOpen ? 'active' : ''}`}
                onClick={() => setOpenHint(isOpen ? null : k)}
                title={trTitle}
                aria-label={`hint for ${trLabel}`}
              >
                ?
              </button>
            )}
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            {isMod && <button onClick={() => setBool(k, (baselineLaws as any)[k] ?? BOOL_DEFAULTS[k] ?? false)} title={t('god.ui.revert_title')} className="god-revert-btn">{t('god.ui.revert')}</button>}
            <Switch checked={boolVal(k)} onChange={(v) => setBool(k, v)} title={trTitle ?? trLabel} />
          </span>
        </div>
        {isOpen && trTitle && (
          <div className="god-hint-box" style={{ margin: '0 12px 8px' }}>
            {trTitle}
            <div style={{ marginTop: 6 }}>
              <a href="./docs/god-laws.md" target="_blank" rel="noreferrer" style={{ fontSize: 11, color: '#58a6ff' }}>{t('god.ui.open_docs')} ↗</a>
              {' · '}
              <a href={apiUrl('/wiki#god-laws')} target="_blank" rel="noreferrer" style={{ fontSize: 11, color: '#58a6ff' }}>{t('god.ui.wiki_link')} ↗</a>
            </div>
          </div>
        )}
      </div>
    )
  }

  const postLaws = async (persist: boolean, reset: boolean = false) => {
    setError(null)
    setSaved(false)
    setSubmitting(true)
    try {
      const qs = `?persist=${persist ? 'true' : 'false'}${reset ? '&reset=true' : ''}`
      const res = await godFetch(`/api/laws${qs}`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(laws),
      })
      const body = await res.json().catch(() => null)
      if (!res.ok) {
        throw new Error(
          typeof body?.detail === 'string'
            ? body.detail
            : (body?.detail?.[0]?.msg ?? 'law rejected'),
        )
      }
      const lawsData = body?.laws ?? body
      setLaws(lawsData)
      setBaselineLaws(lawsData)
      setCurrentPreset(detectPreset(lawsData, presetsDetails ?? undefined))
      setSaved(true)
      localStorage.removeItem(DRAFT_KEY)
      setDraftBanner(null)
      setTimeout(() => setSaved(false), 2500)
    } catch (e) {
      if (e instanceof Error && e.message === 'cancelled') return
      setError(e instanceof Error ? e.message : 'failed to apply law')
    } finally {
      setSubmitting(false)
    }
  }

  const apply = () => postLaws(false)
  const save = () => postLaws(true)
  const applyAndReset = () => postLaws(true, true)

  // §BN-22: Panic Rescue Action
  const handlePanicRescue = async () => {
    const confirmMsg = t('god.ui.panicConfirm') || 'Trigger Panic Rescue? Sets food to 600, activates emergency safeguards, and turns off plagues & disasters.'
    if (!window.confirm(confirmMsg)) return
    const panicLaws: Partial<GodLaws> = {
      food_count: Math.max(600, laws.food_count ?? 300),
      disease_enabled: false,
      wildfire_enabled: false,
      disaster_enabled: false,
      earthquake_enabled: false,
      weather_sickness_enabled: false,
      safeguard_enabled: true,
      safeguard_critical_pop: 20,
    }
    const updated = { ...laws, ...panicLaws }
    recordChange(laws, updated, 'panic_rescue', '🆘 Panic Rescue', 'current', 'rescue defaults')
    setLaws(updated)
    setCurrentPreset(detectPreset(updated, presetsDetails ?? undefined))
    setError(null)
    setSubmitting(true)
    try {
      await godFetch('/api/laws?persist=false', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(updated),
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    } catch (e: any) {
      setError(e.message || 'Panic rescue apply failed')
    } finally {
      setSubmitting(false)
    }
  }

  // §BN-24: Export JSON
  const handleExportJSON = async () => {
    const jsonStr = JSON.stringify(laws, null, 2)
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(jsonStr)
        setExportedCopied(true)
        setTimeout(() => setExportedCopied(false), 2200)
      } else {
        throw new Error('no clipboard')
      }
    } catch {
      window.prompt('Copy laws configuration JSON:', jsonStr)
    }
  }

  // §BN-24: Import JSON
  const handleImportSubmit = () => {
    try {
      setImportError(null)
      const parsed = JSON.parse(importText)
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
        throw new Error('Invalid JSON format: expected an object of laws')
      }
      const updated = { ...laws, ...parsed }
      recordChange(laws, updated, 'import_json', '📥 Import JSON', 'current', 'imported')
      setLaws(updated)
      setCurrentPreset(detectPreset(updated, presetsDetails ?? undefined))
      setShowImportModal(false)
      setImportText('')
    } catch (e: any) {
      setImportError(e.message || 'Failed to parse JSON')
    }
  }

  const selectPreset = (name: string) => {
    setExpandedPreset(name)
    setCurrentPreset(name)
    fetch('/api/presets')
      .then((r) => r.json())
      .then((data) => {
        if (data.details?.[name]) {
          const updated = { ...laws, ...data.details[name] }
          recordChange(laws, updated, 'preset_select', `Preset ${name}`, currentPreset, name)
          setLaws(updated)
        }
      })
      .catch(() => {})
  }

  const applyPreset = async (name: string, reset: boolean) => {
    setError(null)
    setSaved(false)
    setSubmitting(true)
    try {
      const res = await godFetch(`/api/presets/${name}?persist=true${reset ? '&reset=true' : ''}`, { method: 'POST' })
      const body = await res.json().catch(() => null)
      if (!res.ok) {
        throw new Error(
          typeof body?.detail === 'string'
            ? body.detail
            : (body?.detail?.[0]?.msg ?? 'preset failed'),
        )
      }
      const newLaws = body.laws ?? body
      setLaws(newLaws)
      setBaselineLaws(newLaws)
      setCurrentPreset(name)
      setExpandedPreset(name)
      setSaved(true)
      localStorage.removeItem(DRAFT_KEY)
      setDraftBanner(null)
      setTimeout(() => setSaved(false), 2500)
    } catch (e) {
      if (e instanceof Error && e.message === 'cancelled') return
      setError(e instanceof Error ? e.message : 'preset failed')
    } finally {
      setSubmitting(false)
    }
  }

  // Active preset meta
  const activePresetMeta = currentPreset ? (PRESET_META as any)[currentPreset] : null

  // Domain law counts
  const domainLawCounts = useMemo(() => {
    const m: Record<string, number> = {}
    for (const d of DOMAINS) {
      let c = 0
      for (const g of d.groups) c += NUMBER_LAWS.filter(s => s.group === g && !s.isAdvanced).length
      m[d.id] = c
    }
    return m
  }, [])

  // §BN-2: Carrying pressure composite slider
  const currentCarryingPressure = typeof laws.damping_steepness === 'number' ? laws.damping_steepness : 4.0
  const setCarryingPressure = (p: number) => {
    const clamped = Math.max(0, Math.min(10, p))
    const updated = {
      ...laws,
      damping_steepness: clamped,
      crowding_stress_mult: Number((clamped * 0.05).toFixed(3)),
      resource_strain_mult: Number((clamped * 0.125).toFixed(3)),
    }
    recordChange(laws, updated, 'carrying_pressure', 'Carrying pressure', currentCarryingPressure, clamped)
    setLaws(updated)
    setCurrentPreset(detectPreset(updated, presetsDetails ?? undefined))
  }

  // §BN-3: Speciation speed selector
  const SPECIATION_PRESETS: Record<string, { start: number; decay: number; label: string }> = {
    slow: { start: 50, decay: 500, label: 'Slow' },
    normal: { start: 20, decay: 200, label: 'Normal' },
    fast: { start: 5, decay: 50, label: 'Fast' },
    immediate: { start: 0, decay: 10, label: 'Immediate' },
  }
  const activeSpeciationPreset = useMemo(() => {
    const start = laws.annealing_start_generation ?? 20
    const decay = laws.annealing_decay_generations ?? 200
    for (const [name, p] of Object.entries(SPECIATION_PRESETS)) {
      if (p.start === start && p.decay === decay) return name
    }
    return 'custom'
  }, [laws.annealing_start_generation, laws.annealing_decay_generations])

  const setSpeciationSpeed = (name: string) => {
    const p = SPECIATION_PRESETS[name]
    if (!p) return
    const updated = {
      ...laws,
      annealing_start_generation: p.start,
      annealing_decay_generations: p.decay,
    }
    recordChange(laws, updated, 'speciation_speed', 'Speciation speed', activeSpeciationPreset, name)
    setLaws(updated)
    setCurrentPreset(detectPreset(updated, presetsDetails ?? undefined))
  }

  // §BN-4: Shape jitter σ composite slider
  const currentShapeJitter = typeof laws.vertex_mutation_std === 'number' ? laws.vertex_mutation_std : 0.03
  const setShapeJitter = (j: number) => {
    const clamped = Math.max(0.005, Math.min(0.20, j))
    const updated = {
      ...laws,
      vertex_mutation_std: clamped,
      angle_mutation_std: Number((clamped * 0.5).toFixed(4)),
    }
    recordChange(laws, updated, 'shape_jitter', 'Shape jitter σ', currentShapeJitter, clamped)
    setLaws(updated)
    setCurrentPreset(detectPreset(updated, presetsDetails ?? undefined))
  }

  // §BN-6: Plague severity selector
  const PLAGUE_PRESETS: Record<string, { outbreak: number; rate: number; lethality: number; label: string }> = {
    mild: { outbreak: 0.001, rate: 0.05, lethality: 0.05, label: 'Mild' },
    moderate: { outbreak: 0.005, rate: 0.15, lethality: 0.15, label: 'Moderate' },
    lethal: { outbreak: 0.02, rate: 0.40, lethality: 0.40, label: 'Lethal' },
  }
  const activePlaguePreset = useMemo(() => {
    const o = laws.disease_outbreak_rate ?? 0.005
    const r = laws.disease_rate ?? 0.15
    const l = laws.disease_lethality ?? 0.15
    for (const [name, p] of Object.entries(PLAGUE_PRESETS)) {
      if (Math.abs(p.outbreak - o) < 0.001 && Math.abs(p.rate - r) < 0.01 && Math.abs(p.lethality - l) < 0.01) {
        return name
      }
    }
    return 'custom'
  }, [laws.disease_outbreak_rate, laws.disease_rate, laws.disease_lethality])

  const setPlagueSeverity = (name: string) => {
    const p = PLAGUE_PRESETS[name]
    if (!p) return
    const updated = {
      ...laws,
      disease_outbreak_rate: p.outbreak,
      disease_rate: p.rate,
      disease_lethality: p.lethality,
    }
    recordChange(laws, updated, 'plague_severity', 'Plague severity', activePlaguePreset, name)
    setLaws(updated)
    setCurrentPreset(detectPreset(updated, presetsDetails ?? undefined))
  }

  // Renders a numeric law row
  const renderLawRow = ({ key, label, min, max, step, gate, scale }: LawSpec) => {
    const translatedLabel = t(`godLaws.${key}`) !== `godLaws.${key}` ? t(`godLaws.${key}`) : label
    const hint = (t(`godHints.${key}`) !== `godHints.${key}` ? t(`godHints.${key}`) : LAW_HINTS[key])
    const isOpen = openHint === key
    const rawCur = laws[key]
    const curVal = (typeof rawCur === 'number' && !isNaN(rawCur)) ? rawCur : min
    const rawBase = baselineLaws[key]
    const baseVal = (typeof rawBase === 'number' && !isNaN(rawBase)) ? rawBase : undefined
    const isModified = modifiedKeys.has(key)
    const isGated = !gateOpen(gate)
    const zone = getZone(curVal, baseVal, min, max)

    const sliderPos = valToSlider(curVal, min, max, scale)
    const baseSliderPos = baseVal !== undefined ? valToSlider(baseVal, min, max, scale) : null
    const pct = sliderPos / 10
    const basePct = baseSliderPos !== null ? baseSliderPos / 10 : null

    const fmt = (v: number | null | undefined) => {
      if (v === null || v === undefined || isNaN(v)) return '—'
      return step < 1 ? v.toFixed(step < 0.01 ? 3 : 2) : String(Math.round(v))
    }

    const qLower = q
    const labelMatch = qLower && translatedLabel.toLowerCase().includes(qLower)

    return (
      <div
        key={key}
        className={`god-law-row zone-${zone} ${isModified ? 'modified' : ''} ${isGated ? 'god-gated-disabled' : ''}`}
        style={{ borderBottom: '1px solid #21262d', padding: '10px 12px', background: isModified ? 'rgba(227,179,65,0.05)' : undefined }}
      >
        <div className="god-law-head" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <span style={{ display: 'inline-flex', gap: 6, alignItems: 'center', flex: 1, minWidth: 0 }}>
            <span
              title={hint}
              style={{
                color: isModified ? '#e3b341' : '#e6edf3',
                fontSize: 13,
                fontWeight: isModified ? 600 : 500,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                background: labelMatch ? 'rgba(227,179,65,0.2)' : undefined,
                padding: labelMatch ? '0 3px' : 0,
                borderRadius: 3,
              }}
            >
              {translatedLabel}
            </span>
            {scale === 'log' && <span className="god-log-badge" title="Logarithmic scale dial">LOG</span>}
            {isModified && <span className="god-mod-dot" title={t('god.ui.modified_from_preset')}>●</span>}
            {isGated && <span className="god-gated-badge">⚠️ {t('god.ui.disabledBy', { gate: String(gate) })}</span>}
            {hint && (
              <button
                type="button"
                className={`god-hint-btn ${isOpen ? 'active' : ''}`}
                onClick={() => setOpenHint(isOpen ? null : key)}
                title={hint}
                aria-label={`hint for ${translatedLabel}`}
              >
                ?
              </button>
            )}
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, flex: 'none' }}>
            {isModified && (
              <button onClick={() => revertOne(key)} title={t('god.ui.revert_title')} className="god-revert-btn">
                {t('god.ui.revert')}
              </button>
            )}
            <span className={`god-zone-pill zone-${zone}`} title={t('god.ui.zone_distance', { zone: t(`god.ui.zones.${zone}`) || zone })}>
              {t(`god.ui.zones.${zone}`) || zone}
            </span>
          </span>
        </div>

        {/* Dual slider + number pill with §BN-16 log-scale & §BN-21 touch repeat */}
        <div className="god-dual-control">
          <div className="god-slider-wrap">
            <div className="god-slider-track">
              <div className="god-slider-zones">
                <span className="z-extreme-left" />
                <span className="z-strained-left" />
                <span className="z-safe" />
                <span className="z-strained-right" />
                <span className="z-extreme-right" />
              </div>
              <div className="god-slider-fill" style={{ width: `${pct}%` }} />
              {/* §BN-20: Clickable baseline marker */}
              {basePct !== null && baseVal !== undefined && (
                <span
                  className="god-baseline-marker"
                  style={{ left: `${basePct}%` }}
                  onClick={() => revertOne(key)}
                  title={`Click to revert to default (${fmt(baseVal)})`}
                />
              )}
            </div>
            <input
              type="range"
              className="god-range"
              min={0}
              max={1000}
              step={1}
              value={sliderPos}
              onChange={(e) => {
                const nextVal = sliderToVal(Number(e.target.value), min, max, step, scale)
                set(key, nextVal)
              }}
              style={{ ['--pct' as any]: `${pct}%` }}
            />
          </div>

          <span className={`god-number-pill zone-${zone}`}>
            <button
              type="button"
              className="god-pill-step"
              onPointerDown={() => startStepHold(key, min, max, step, -1, scale)}
              onPointerUp={stopStepHold}
              onPointerLeave={stopStepHold}
              aria-label="decrease"
            >
              −
            </button>
            <input
              type="number"
              className="god-pill-input"
              min={min}
              max={max}
              step={step}
              value={curVal}
              onChange={(e) => set(key, e.target.value)}
            />
            <button
              type="button"
              className="god-pill-step"
              onPointerDown={() => startStepHold(key, min, max, step, 1, scale)}
              onPointerUp={stopStepHold}
              onPointerLeave={stopStepHold}
              aria-label="increase"
            >
              +
            </button>
          </span>
        </div>

        {baseVal !== undefined && (
          <div className="god-baseline-row">
            {/* §BN-20: Clickable baseline text */}
            <span className="god-baseline-text" onClick={() => revertOne(key)} title="Click to revert to default">
              {t('god.ui.default_label', { val: fmt(baseVal) })} · {curVal > baseVal ? `+${fmt(curVal - baseVal)}` : curVal < baseVal ? fmt(curVal - baseVal) : (t('god.ui.baseline') || 'baseline')}
            </span>
            <span className="god-range-labels"><span>{fmt(min)}</span><span>{fmt(max)}</span></span>
          </div>
        )}

        {isOpen && hint && (
          <div className="god-hint-box">
            {hint}
            <div style={{ marginTop: 6 }}>
              <a href="./docs/god-laws.md" target="_blank" rel="noreferrer" style={{ fontSize: 11, color: '#58a6ff' }}>{t('god.ui.open_docs')} ↗</a>
              {' · '}
              <a href={apiUrl('/wiki#god-laws')} target="_blank" rel="noreferrer" style={{ fontSize: 11, color: '#58a6ff' }}>{t('god.ui.wiki_link')} ↗</a>
            </div>
          </div>
        )}
      </div>
    )
  }

  const foot = (
    <footer className="god-foot">
      {/* Feedback / Status Alert Pill */}
      {(error || saved || submitting) && (
        <div className="god-foot-status-bar" role="status" aria-live="polite">
          {error && (
            <div className="god-foot-status-pill god-status-error">
              <span className="god-status-icon">⚠️</span>
              <span className="god-status-text">{error}</span>
            </div>
          )}
          {!error && saved && (
            <div className="god-foot-status-pill god-status-success">
              <span className="god-status-icon">✓</span>
              <span className="god-status-text">{t('god.presets.saved') || 'Laws active'}</span>
            </div>
          )}
          {!error && !saved && submitting && (
            <div className="god-foot-status-pill god-status-pending">
              <span className="god-status-spinner" />
              <span className="god-status-text">{t('god.presets.applying') || 'Applying…'}</span>
            </div>
          )}
        </div>
      )}

      {/* Auxiliary Row: Panic Rescue & Data Tools */}
      <div className="god-foot-aux-row">
        <button
          type="button"
          className="god-panic-btn god-foot-panic"
          disabled={submitting}
          onClick={handlePanicRescue}
          title={t('god.ui.panicConfirm')}
        >
          <span className="god-foot-btn-icon">🚨</span>
          <span className="god-foot-btn-label">{t('god.ui.panicBtn') || 'Panic Rescue'}</span>
        </button>

        <div className="god-foot-tools-group">
          <button
            type="button"
            className="god-foot-tool-btn"
            onClick={handleExportJSON}
            title={t('god.ui.copyJsonTitle')}
          >
            <span className="god-foot-btn-icon">{exportedCopied ? '✓' : '📤'}</span>
            <span className="god-foot-btn-label">{exportedCopied ? (t('god.ui.copied') || 'Copied!') : (t('god.ui.exportJson') || 'Export JSON')}</span>
          </button>
          <button
            type="button"
            className="god-foot-tool-btn"
            onClick={() => setShowImportModal(true)}
            title={t('god.ui.importJsonTitle')}
          >
            <span className="god-foot-btn-icon">📥</span>
            <span className="god-foot-btn-label">{t('god.ui.importJson') || 'Import JSON'}</span>
          </button>
        </div>
      </div>

      {/* Primary Action Dock */}
      <div className="god-foot-main-row">
        <div className="god-foot-secondary-actions">
          <button
            type="button"
            className="god-foot-action-btn god-foot-apply"
            onClick={apply}
            disabled={submitting}
            title={t('god.footer.applyDesc')}
          >
            <span className="god-foot-btn-icon">⚡</span>
            <span className="god-foot-btn-label">{t('god.footer.apply')}</span>
          </button>
          <button
            type="button"
            className="god-foot-action-btn god-foot-save god-save"
            onClick={save}
            disabled={submitting}
            title={t('god.footer.saveDesc')}
          >
            <span className="god-foot-btn-icon">💾</span>
            <span className="god-foot-btn-label">{t('god.footer.save')}</span>
          </button>
        </div>
        <button
          type="button"
          className="god-foot-action-btn god-foot-apply-reset"
          onClick={applyAndReset}
          disabled={submitting}
          title={t('god.footer.applyResetDesc')}
        >
          <span className="god-foot-btn-icon">🔄</span>
          <span className="god-foot-btn-label">{t('god.footer.applyReset').replace(/^🔄\s*/, '')}</span>
        </button>
      </div>
    </footer>
  )

  const head = (
    <header className="god-head">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 16 }}>⚖️</span>
          <h2 style={{ margin: 0, fontSize: 15, fontWeight: 700, letterSpacing: '0.02em', color: '#f0f6fc' }}>
            {t('god.title')}
          </h2>
        </div>
        <span style={{ fontSize: 11, color: '#8b949e' }}>
          {t('god.subtitle')}
        </span>
      </div>
      <button className="god-close" onClick={onClose} aria-label="close">
        ×
      </button>
    </header>
  )

  const body = (
    <>
      {/* §BN-23: Unsaved Draft Banner */}
      {draftBanner && (
        <div className="god-draft-banner">
          <span>⚠️ {t('god.ui.draftBanner')} ({draftBanner.date})</span>
          <div style={{ display: 'flex', gap: 6 }}>
            <button
              type="button"
              className="god-draft-btn"
              style={{ background: '#238636', border: '1px solid #2ea043', color: '#fff' }}
              onClick={() => {
                setLaws(draftBanner.laws)
                setCurrentPreset(detectPreset(draftBanner.laws, presetsDetails ?? undefined))
                setDraftBanner(null)
              }}
            >
              {t('god.ui.draftRestore')}
            </button>
            <button
              type="button"
              className="god-draft-btn"
              style={{ background: '#21262d', border: '1px solid #30363d', color: '#c9d1d9' }}
              onClick={() => {
                localStorage.removeItem(DRAFT_KEY)
                setDraftBanner(null)
              }}
            >
              {t('god.ui.draftDiscard')}
            </button>
          </div>
        </div>
      )}

      {/* Top Segmented Mode Switcher: Presets vs Laws of Nature */}
      <div className="god-segmented-control" role="tablist" aria-label="God panel sections">
        <button
          type="button"
          role="tab"
          aria-selected={activeSection === 'presets'}
          className={`god-segment-btn ${activeSection === 'presets' ? 'active' : ''}`}
          onClick={() => setActiveSection('presets')}
        >
          <span style={{ fontSize: 14 }}>🎯</span>
          <span>{t('god.curatedPresetsTitle')}</span>
          <span className="god-segment-pill">
            {q ? matchingPresets.length : presetKeys.length}
          </span>
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeSection === 'laws'}
          className={`god-segment-btn ${activeSection === 'laws' ? 'active' : ''}`}
          onClick={() => setActiveSection('laws')}
        >
          <span style={{ fontSize: 14 }}>⚖️</span>
          <span>{t('god.lawsOfNatureTitle')}</span>
          <span className="god-segment-pill">
            {filteredSpecs(NUMBER_LAWS).length}
          </span>
        </button>
      </div>

      {activeSection === 'presets' && (
        <div className="god-group" style={{ display: 'flex', flexDirection: 'column', gap: 10, border: 'none', padding: 0 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%', marginBottom: 2 }}>
            <span style={{ fontSize: 12, color: '#8b949e', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              {t('god.presets.title')}
            </span>
            <span
              style={{
                fontSize: 11,
                padding: '2px 10px',
                borderRadius: 12,
                background: activePresetMeta ? activePresetMeta.bg : 'rgba(163, 113, 247, 0.15)',
                border: `1px solid ${activePresetMeta ? activePresetMeta.border : '#8b949e'}`,
                color: activePresetMeta ? activePresetMeta.color : '#d2a8ff',
                fontWeight: 700,
              }}
            >
              {activePresetMeta && currentPreset ? `${t('god.presets.active', { name: t(`god.presets.${currentPreset}`) })}` : t('god.presets.custom')}
            </span>
          </div>

          <div className="god-preset-grid">
            {(q ? matchingPresets : presetKeys).map((key) => {
              const meta = PRESET_META[key as keyof typeof PRESET_META]
              const label = t(`god.presets.${key}`)
              const subtitle = t(`god.presets.${key}Subtitle`)
              const description = t(`god.presets.${key}Desc`)
              const badges = PRESET_BADGES[key] || []
              const impact = PRESET_IMPACT[key] || ''
              const { color, border, bg, badge } = meta as any
              const isActive = currentPreset === key
              const isExpanded = expandedPreset === key
              return (
                <div
                  key={key}
                  onClick={() => selectPreset(key)}
                  className="god-preset-card"
                  data-active={isActive ? 'true' : 'false'}
                  data-expanded={isExpanded ? 'true' : 'false'}
                  style={{
                    background: isActive ? bg : isExpanded ? '#1c2128' : '#161b22',
                    border: `1.5px solid ${isActive ? border : isExpanded ? '#444c56' : '#30363d'}`,
                    borderRadius: 8,
                    padding: '10px 12px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 6,
                    cursor: 'pointer',
                    boxShadow: isActive ? `0 0 14px ${bg}` : 'none',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                      <span style={{ fontSize: 14, fontWeight: 700, color: isActive ? color : '#e6edf3' }}>{label}</span>
                      <span style={{ fontSize: 11, color: '#8b949e', fontStyle: 'italic' }}>({subtitle})</span>
                    </div>
                    <div style={{ display: 'flex', gap: 4, flex: 'none' }}>
                      {badge && (
                        <span style={{ fontSize: 9, padding: '1px 5px', borderRadius: 4, background: '#d29922', color: '#0d1117', fontWeight: 800 }}>
                          {badge}
                        </span>
                      )}
                      {isActive && (
                        <span style={{ fontSize: 9, padding: '1px 6px', borderRadius: 4, background: color, color: '#0d1117', fontWeight: 800 }}>
                          ● ACTIVE
                        </span>
                      )}
                    </div>
                  </div>

                  <p style={{ fontSize: 12, color: '#c9d1d9', margin: 0, lineHeight: 1.4 }}>
                    {description}
                  </p>
                  <p style={{ fontSize: 11, color: '#8b949e', margin: 0, lineHeight: 1.3, fontStyle: 'italic' }}>{impact}</p>

                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 2 }}>
                    {badges.map((b) => (
                      <span key={b} className="god-preset-badge" style={{ fontSize: 10, padding: '2px 7px', borderRadius: 10, background: isActive ? 'rgba(0,0,0,0.25)' : '#21262d', color: isActive ? color : '#8b949e', border: `1px solid ${isActive ? border : '#30363d'}`, fontWeight: 600 }}>
                        {b}
                      </span>
                    ))}
                  </div>

                  <div style={{ display: 'flex', gap: 6, marginTop: 6, flexWrap: 'wrap' }}>
                    <button
                      type="button"
                      disabled={submitting}
                      onClick={(e) => {
                        e.preventDefault()
                        e.stopPropagation()
                        applyPreset(key, false)
                      }}
                      title={`Apply ${label} laws live`}
                      className="god-preset-apply"
                      style={{
                        flex: 1,
                        padding: isMobile ? '10px 8px' : '6px 8px',
                        fontSize: 11,
                        fontWeight: 600,
                        background: '#21262d',
                        borderColor: isActive ? border : '#30363d',
                        color: isActive ? color : '#c9d1d9',
                        borderRadius: 6,
                        cursor: 'pointer',
                        minHeight: isMobile ? 44 : undefined,
                        touchAction: 'manipulation',
                        WebkitTapHighlightColor: 'transparent',
                      }}
                    >
                      ⚡ Apply Live
                    </button>
                    <button
                      type="button"
                      disabled={submitting}
                      onClick={(e) => {
                        e.preventDefault()
                        e.stopPropagation()
                        applyPreset(key, true)
                      }}
                      title={`Apply ${label} + reset world`}
                      className="god-preset-reset"
                      style={{
                        flex: 1,
                        padding: isMobile ? '10px 8px' : '6px 8px',
                        fontSize: 11,
                        fontWeight: 700,
                        background: '#238636',
                        borderColor: '#2ea043',
                        color: '#fff',
                        borderRadius: 6,
                        cursor: 'pointer',
                        minHeight: isMobile ? 44 : undefined,
                        touchAction: 'manipulation',
                        WebkitTapHighlightColor: 'transparent',
                      }}
                    >
                      🔄 Apply & Reset
                    </button>
                  </div>
                  {isActive && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.preventDefault()
                        e.stopPropagation()
                        setActiveSection('laws')
                      }}
                      style={{
                        marginTop: 2,
                        padding: '5px 8px',
                        fontSize: 11,
                        fontWeight: 600,
                        background: 'transparent',
                        border: '1px dashed #484f58',
                        color: '#58a6ff',
                        borderRadius: 6,
                        cursor: 'pointer',
                        textAlign: 'center',
                      }}
                    >
                      🛠️ Customise laws for {label} ➔
                    </button>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {activeSection === 'laws' && (
        <>
          {loading ? (
            <p className="god-note">{t('god.presets.loading' as any) || 'reading the tablets…'}</p>
          ) : (
            <>
              {/* Active Preset Status Ribbon */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 10px', background: '#161b22', border: '1px solid #30363d', borderRadius: 8 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                  <span style={{ fontSize: 11, color: '#8b949e' }}>{t('god.baselinePrefix')}</span>
                  <span style={{ fontSize: 12, fontWeight: 700, color: activePresetMeta ? activePresetMeta.color : '#e6edf3' }}>
                    {activePresetMeta && currentPreset ? t(`god.presets.${currentPreset}`) : (t('god.presets.custom') || 'Custom')}
                  </span>
                  {modifiedKeys.size > 0 && (
                    <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 6, background: 'rgba(227,179,65,0.18)', color: '#e3b341', fontWeight: 700 }}>
                      {t('god.ui.modified_count', { count: modifiedKeys.size })}
                    </span>
                  )}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  {/* §BN-26: Undo / Redo Toolbar */}
                  <button
                    type="button"
                    onClick={handleUndo}
                    disabled={undoStack.length === 0}
                    title={t('god.ui.undoTitle')}
                    style={{ background: 'transparent', border: 'none', color: undoStack.length > 0 ? '#c9d1d9' : '#484f58', cursor: undoStack.length > 0 ? 'pointer' : 'default', padding: '2px 4px', fontSize: 13 }}
                  >
                    ↺
                  </button>
                  <button
                    type="button"
                    onClick={handleRedo}
                    disabled={redoStack.length === 0}
                    title={t('god.ui.redoTitle')}
                    style={{ background: 'transparent', border: 'none', color: redoStack.length > 0 ? '#c9d1d9' : '#484f58', cursor: redoStack.length > 0 ? 'pointer' : 'default', padding: '2px 4px', fontSize: 13 }}
                  >
                    ↻
                  </button>
                  {/* §BN-25: Change Log toggle */}
                  <button
                    type="button"
                    onClick={() => setShowChangeLog(!showChangeLog)}
                    title={t('god.ui.toggleHistoryTitle')}
                    style={{ background: '#21262d', border: '1px solid #30363d', borderRadius: 4, color: '#8b949e', fontSize: 11, padding: '2px 6px', cursor: 'pointer' }}
                  >
                    📜 {t('god.ui.changeLog')} ({changeLog.length})
                  </button>
                  <button
                    type="button"
                    onClick={() => setActiveSection('presets')}
                    style={{ fontSize: 11, color: '#58a6ff', background: 'transparent', border: 'none', cursor: 'pointer', padding: 0, fontWeight: 600 }}
                  >
                    {t('god.ui.switch_preset')}
                  </button>
                </div>
              </div>

              {/* §BN-25: Session Change Log Popover */}
              {showChangeLog && (
                <div className="god-history-popover">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6, borderBottom: '1px solid #30363d', paddingBottom: 4 }}>
                    <span style={{ fontWeight: 700, color: '#e6edf3' }}>{t('god.ui.sessionModifications')}</span>
                    <button onClick={() => setShowChangeLog(false)} style={{ background: 'transparent', border: 'none', color: '#8b949e', cursor: 'pointer' }}>×</button>
                  </div>
                  {changeLog.length === 0 ? (
                    <div style={{ color: '#8b949e', padding: 8, textAlign: 'center' }}>{t('god.ui.noModifications')}</div>
                  ) : (
                    changeLog.map((entry, idx) => (
                      <div key={idx} className="god-history-item">
                        <div>
                          <span style={{ color: '#e6edf3', fontWeight: 600 }}>{entry.label}</span>
                          <span style={{ color: '#8b949e', marginLeft: 6 }}>{String(entry.from ?? '—')} ➔ <b style={{ color: '#e3b341' }}>{String(entry.to ?? '—')}</b></span>
                        </div>
                        <span style={{ color: '#6e7681', fontSize: 10 }}>{entry.time}</span>
                      </div>
                    ))
                  )}
                </div>
              )}

              {/* Law Search, Modified Filter & Risk Filter — §BN-27, §BN-28 */}
              <div className="god-search-bar">
                <div className="god-search-input-wrap">
                  <span className="god-search-icon">🔍</span>
                  <input
                    className="god-search-input"
                    type="text"
                    placeholder={t('god.ui.search_placeholder')}
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                  {searchQuery && (
                    <button className="god-search-clear" onClick={() => setSearchQuery('')} title={t('god.ui.clear_search')}>×</button>
                  )}
                </div>

                <button
                  className={`god-filter-btn ${showModifiedOnly ? 'active' : ''}`}
                  onClick={() => setShowModifiedOnly(!showModifiedOnly)}
                  title={t('god.ui.show_modified_title')}
                >
                  {showModifiedOnly ? '✓ ' : ''}{t('god.ui.show_modified', { count: modifiedKeys.size })}
                </button>

                {/* §BN-28: Filter by Risk Zone */}
                <button
                  className={`god-filter-btn ${filterRiskOnly ? 'active' : ''}`}
                  onClick={() => setFilterRiskOnly(!filterRiskOnly)}
                  title={t('god.ui.extremeFilterTitle')}
                  style={{ color: filterRiskOnly ? '#ff7b72' : undefined, borderColor: filterRiskOnly ? '#f85149' : undefined }}
                >
                  {t('god.ui.riskOnly')} ({riskKeysCount})
                </button>

                {showModifiedOnly && modifiedKeys.size > 0 && (
                  <button
                    className="god-revert-all"
                    onClick={() => {
                      recordChange(laws, baselineLaws, 'revert_all', 'Revert All', 'modified', 'baseline')
                      setLaws({ ...baselineLaws })
                    }}
                    title={t('god.ui.revert_all_title')}
                  >
                    {t('god.ui.revert_all')}
                  </button>
                )}
              </div>

              {/* §BN-27: Matching presets banner when searching */}
              {q && matchingPresets.length > 0 && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: '#8b949e', margin: '-4px 0 6px', padding: '0 4px', flexWrap: 'wrap' }}>
                  <span>{t('god.ui.matchingPresets')}</span>
                  {matchingPresets.map((pk) => (
                    <button
                      key={pk}
                      type="button"
                      onClick={() => {
                        selectPreset(pk)
                        setActiveSection('presets')
                      }}
                      style={{ background: '#21262d', border: '1px solid #30363d', borderRadius: 4, color: '#58a6ff', fontSize: 11, cursor: 'pointer', padding: '1px 6px' }}
                    >
                      {t(`god.presets.${pk}`)}
                    </button>
                  ))}
                </div>
              )}

              {/* Edge of world boundary */}
              <div style={{ borderBottom: '1px solid #30363d', background: modifiedKeys.has('boundary' as any) ? 'rgba(227,179,65,0.06)' : undefined, borderLeft: (modifiedKeys.has('boundary' as any) ? '2px solid #d29922' : '2px solid transparent') }}>
                <label className="god-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '9px 12px' }}>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ color: '#e6edf3', fontSize: 13, fontWeight: 500 }}>{t('godToggles.edgeOfWorld' as any) || 'Edge of world'}</span>
                    <button
                      type="button"
                      className={`god-hint-btn ${openHint === 'boundary' ? 'active' : ''}`}
                      onClick={() => setOpenHint(openHint === 'boundary' ? null : 'boundary')}
                      title={t('god.ui.edge_hint_title')}
                      aria-label="hint for edge of world"
                    >
                      ?
                    </button>
                  </span>
                  <select
                    value={laws.boundary ?? 'wrap'}
                    onChange={(e) =>
                      setLaws((l) => ({ ...l, boundary: e.target.value as 'wrap' | 'clamp' }))
                    }
                    style={{ minHeight: 32, padding: '4px 8px' }}
                  >
                    <option value="wrap">{t('god.edge.wrap')}</option>
                    <option value="clamp">{t('god.edge.walls')}</option>
                  </select>
                </label>
                {openHint === 'boundary' && (
                  <div className="god-hint-box" style={{ margin: '0 12px 8px' }} dangerouslySetInnerHTML={{ __html: t('god.ui.edge_hint_body') }} />
                )}
              </div>

              {/* Domain selector grid */}
              {!q && !showModifiedOnly && !filterRiskOnly && (
                <div className="god-domain-grid" role="tablist" aria-label="Law domains">
                  {DOMAINS.map((d) => (
                    <button
                      key={d.id}
                      type="button"
                      role="tab"
                      aria-selected={activeDomain === d.id}
                      className={`god-domain-card-btn ${activeDomain === d.id ? 'active' : ''}`}
                      onClick={() => setActiveDomain(d.id)}
                      title={`${t(`god.domains.${d.id}`) !== `god.domains.${d.id}` ? t(`god.domains.${d.id}`) : d.label}`}
                    >
                      <span className="god-domain-btn-label">
                        <span className="god-domain-icon">{d.icon}</span>
                        <span>{t(`god.domainShort.${d.id}`) !== `god.domainShort.${d.id}` ? t(`god.domainShort.${d.id}`) : d.shortLabel}</span>
                      </span>
                      <span className="god-domain-count">{domainLawCounts[d.id] ?? 0}</span>
                    </button>
                  ))}
                </div>
              )}

              {(q || showModifiedOnly || filterRiskOnly) && (
                <div className="god-search-meta">
                  {q ? t('god.ui.match_count', { count: filteredSpecs(NUMBER_LAWS).length, q }) : ''}
                  {q && showModifiedOnly ? ' · ' : ''}
                  {showModifiedOnly ? t('god.ui.modified_indicator', { count: modifiedKeys.size }) : ''}
                  <button
                    className="god-search-clear-link"
                    onClick={() => {
                      setSearchQuery('')
                      setShowModifiedOnly(false)
                      setFilterRiskOnly(false)
                    }}
                  >
                    {t('god.ui.clear_filters')}
                  </button>
                </div>
              )}

              {/* Render Domains & Consolidated Groups */}
              {(q || showModifiedOnly || filterRiskOnly ? DOMAINS : DOMAINS.filter(d => d.id === activeDomain)).map((domain) => {
                const groupSections = domain.groups.map((group) => {
                  const allInGroup = NUMBER_LAWS.filter((l) => l.group === group)
                  const visibleSpecs = filteredSpecs(allInGroup)
                  const isFiltering = !!q || showModifiedOnly || filterRiskOnly
                  if (isFiltering && visibleSpecs.length === 0) {
                    // Check if any toggles in this group match
                    const toggleGroups = new Set([
                      'Food & Agriculture', 'Ecosystem & Flora', 'Reproduction & Caste',
                      'Population Safety', 'Evolution Engine', 'Disease & Plague',
                      'Climate & Shelter', 'Combat & Survival', 'Society & Governance',
                      'Theology & Avatars', 'Landscape & Elements', 'Cosmology & Disasters'
                    ])
                    if (!toggleGroups.has(group)) return null
                  }

                  // Domain-specific master toggles & composites
                  const special = (
                    <>
                      {/* Food & Agriculture */}
                      {group === 'Food & Agriculture' && (
                        <>
                          <ToggleRow k="food_decay_enabled" label="Food decay" title="mature plants wither over time and fertilize the living soil" />
                          <ToggleRow k="agriculture_enabled" label="Agriculture" title="seed gathering, farm plots, irrigation furrows, and tending" />
                          <ToggleRow k="granaries_enabled" label="Granaries" title="dry roofed granaries storing grain against famine" hideIfOff="agriculture_enabled" />
                        </>
                      )}

                      {/* Ecosystem & Flora */}
                      {group === 'Ecosystem & Flora' && (
                        <ToggleRow k="plant_variants_enabled" label="Plant variants" title="botanical diversity across grass, berry, mushroom, poison" />
                      )}

                      {/* Reproduction & Caste */}
                      {group === 'Reproduction & Caste' && (
                        <MasterToggleCard
                          k="birth_enabled"
                          icon="🌱"
                          label="Reproduction & Mating"
                          desc="Master switch enabling reproduction, mating, and generational ascendance"
                        />
                      )}

                      {/* Population Safety (BN-2, BN-5, BN-11) */}
                      {group === 'Population Safety' && (
                        <>
                          <MasterToggleCard
                            k="safeguard_enabled"
                            icon="🛡️"
                            label="Extinction Safeguards"
                            desc="Sphere emergency interventions when living species count hits critical floor"
                          />
                          <ToggleRow k="soft_cap_enabled" label="Density Soft-Cap Damping" title="damps birth rate and scales metabolic strain when exceeding carrying capacity" />

                          {/* §BN-2: Carrying pressure composite slider */}
                          <div className="god-composite-card">
                            <div className="god-composite-head">
                              <span style={{ fontSize: 13, fontWeight: 600, color: '#e6edf3' }}>
                                {t('god.ui.carryingPressure')} ({currentCarryingPressure.toFixed(1)} / 10.0)
                              </span>
                              <span style={{ fontSize: 11, color: '#8b949e' }}>
                                Damping: {currentCarryingPressure.toFixed(1)} · Stress: {(currentCarryingPressure * 0.05).toFixed(2)}×
                              </span>
                            </div>
                            <input
                              type="range"
                              min={0.0}
                              max={10.0}
                              step={0.5}
                              value={currentCarryingPressure}
                              onChange={(e) => setCarryingPressure(Number(e.target.value))}
                              className="god-range"
                            />
                            <span style={{ fontSize: 10.5, color: '#8b949e' }}>
                              {t('god.ui.carryingPressureDesc')}
                            </span>
                          </div>

                          {/* §BN-5: Advanced Safeguards Accordion */}
                          <details className="god-advanced-accordion">
                            <summary>{t('god.ui.advancedSafeguards')}</summary>
                            <div style={{ padding: '6px 0' }}>
                              {allInGroup.filter(s => s.isAdvanced).map(renderLawRow)}
                            </div>
                          </details>
                        </>
                      )}

                      {/* Evolution Engine (BN-3, BN-4, BN-8, BN-12) */}
                      {group === 'Evolution Engine' && (
                        <>
                          <MasterToggleCard
                            k="morphology_annealing_enabled"
                            icon="🧬"
                            label="Morphological Annealing"
                            desc="Enables polar genome evolution transitioning from rigid Abbott templates to freeform geometric physics"
                          />

                          {/* §BN-3: Speciation Speed Selector */}
                          <div className="god-composite-card">
                            <div className="god-composite-head">
                              <span style={{ fontSize: 13, fontWeight: 600, color: '#e6edf3' }}>
                                {t('god.ui.speciationSpeed')}
                              </span>
                              <div className="god-pill-select-group">
                                {Object.keys(SPECIATION_PRESETS).map((key) => (
                                  <button
                                    key={key}
                                    type="button"
                                    className={`god-pill-select-btn ${activeSpeciationPreset === key ? 'active' : ''}`}
                                    onClick={() => setSpeciationSpeed(key)}
                                  >
                                    {SPECIATION_PRESETS[key].label}
                                  </button>
                                ))}
                              </div>
                            </div>
                            <span style={{ fontSize: 10.5, color: '#8b949e' }}>
                              Start Gen: {laws.annealing_start_generation ?? 20} · Decay Gens: {laws.annealing_decay_generations ?? 200}
                            </span>
                          </div>

                          {/* §BN-4: Shape Jitter σ Composite Slider */}
                          <div className="god-composite-card">
                            <div className="god-composite-head">
                              <span style={{ fontSize: 13, fontWeight: 600, color: '#e6edf3' }}>
                                {t('god.ui.shapeJitter')} ({currentShapeJitter.toFixed(3)})
                              </span>
                              <span style={{ fontSize: 11, color: '#8b949e' }}>
                                σr: {currentShapeJitter.toFixed(3)} · σφ: {(currentShapeJitter * 0.5).toFixed(3)}
                              </span>
                            </div>
                            <input
                              type="range"
                              min={0.005}
                              max={0.20}
                              step={0.005}
                              value={currentShapeJitter}
                              onChange={(e) => setShapeJitter(Number(e.target.value))}
                              className="god-range"
                            />
                          </div>

                          {/* §BN-8: Collapsed Advanced Accordion */}
                          <details className="god-advanced-accordion">
                            <summary>{t('god.ui.advancedEvolution')}</summary>
                            <div style={{ padding: '6px 0' }}>
                              <div className="god-note" style={{ fontSize: 11, opacity: 0.7, padding: '4px 10px' }}>
                                {t('god.ui.notes.neuroevolution')}
                              </div>
                              {allInGroup.filter(s => s.isAdvanced).map(renderLawRow)}
                            </div>
                          </details>
                        </>
                      )}

                      {/* Disease & Plague (BN-6) */}
                      {group === 'Disease & Plague' && (
                        <>
                          <MasterToggleCard
                            k="disease_enabled"
                            icon="☣️"
                            label="Plagues & Pathology"
                            desc="Enables contagious pathogen outbreaks, quarantine behavior, and priestly healing"
                          />

                          {/* §BN-6: Plague Severity Selector */}
                          <div className="god-composite-card">
                            <div className="god-composite-head">
                              <span style={{ fontSize: 13, fontWeight: 600, color: '#e6edf3' }}>
                                {t('god.ui.plagueSeverity')}
                              </span>
                              <div className="god-pill-select-group">
                                {Object.keys(PLAGUE_PRESETS).map((key) => (
                                  <button
                                    key={key}
                                    type="button"
                                    className={`god-pill-select-btn ${activePlaguePreset === key ? 'active' : ''}`}
                                    onClick={() => setPlagueSeverity(key)}
                                  >
                                    {PLAGUE_PRESETS[key].label}
                                  </button>
                                ))}
                              </div>
                            </div>
                          </div>

                          {/* Advanced Disease Accordion */}
                          <details className="god-advanced-accordion">
                            <summary>{t('god.ui.advancedPlague')}</summary>
                            <div style={{ padding: '6px 0' }}>
                              {allInGroup.filter(s => s.isAdvanced).map(renderLawRow)}
                            </div>
                          </details>
                        </>
                      )}

                      {/* Climate & Shelter (BN-10) */}
                      {group === 'Climate & Shelter' && (
                        <>
                          <MasterToggleCard
                            k="weather_enabled"
                            icon="⛅"
                            label="Dynamic Weather"
                            desc="Enables meteorological cycles (sun, rain, fog, storms)"
                          />
                          <ToggleRow k="sleep_enabled" label="Night rest" title="creatures shelter in houses after dark" />
                          <ToggleRow k="shelter_enabled" label="Shelter allowed" title="creatures may claim roofs against rain and storms" />
                          <ToggleRow k="weather_sickness_enabled" label="Weather sickness" title="chill and hypothermia when caught unsheltered in storms or winter" />
                        </>
                      )}

                      {/* Combat & Survival (BN-13) */}
                      {group === 'Combat & Survival' && (
                        <>
                          <MasterToggleCard
                            k="war_enabled"
                            icon="⚔️"
                            label="Inter-Clan Warfare"
                            desc="Rival clans fight on contact, contest borders, and plunder resources"
                          />
                          <MasterToggleCard
                            k="predation_enabled"
                            icon="🐺"
                            label="Predator-Prey Ecology"
                            desc="Carnivorous predators hunt herbivores and vulnerable castes"
                          />
                          <ToggleRow k="cannibalism_enabled" label="Cannibalism" title="the starving may hunt and consume living enemies" />
                          <ToggleRow k="eat_kin_enabled" label="Eat kin" title="weak kin may be eaten at the cost of tribal exile and feuds" hideIfOff="cannibalism_enabled" />
                        </>
                      )}

                      {/* Society & Governance (BN-14) */}
                      {group === 'Society & Governance' && (
                        <>
                          <ToggleRow k="territory_enabled" label="Territory claimed" title="clans claim borders around their houses" />
                          <ToggleRow k="totems_enabled" label="Sacred Avatars" title="each clan bears one of the 8 Sacred Avatars of the Sphere" />
                          <ToggleRow k="succession_enabled" label="Succession" title="leader succession on chieftain death" />
                          <ToggleRow k="communication_enabled" label="Communication & Signals" title="food calls, alarm calls, vocalizations and scent ripples" />
                          <ToggleRow k="knowledge_enabled" label="Knowledge & Memory" title="creatures remember food and hazard coordinates" />
                          <ToggleRow k="coalitions_enabled" label="Coalitions" title="allied clans form defensive military blocs" />
                          <ToggleRow k="leader_decisions_enabled" label="Leader decisions" title="leaders declare war, sue for peace, demand tribute" />
                          <ToggleRow k="resource_sharing_enabled" label="Resource sharing" title="communal settlement larder sharing" />
                          <ToggleRow k="schism_enabled" label="Schism allowed" title="unhappy clan members split off to found rebel faction" />
                        </>
                      )}

                      {/* Theology & Avatars */}
                      {group === 'Theology & Avatars' && (
                        <>
                          <MasterToggleCard
                            k="theology_enabled"
                            icon="🔮"
                            label="Theology of the Sphere"
                            desc="Enables shrines, dawn & dusk tithes, healing auras, miracles, and temples"
                          />
                          <ToggleRow k="culture_enabled" label="Culture" title="culture spreads to allied neighbours granting shared bonuses" />
                          <ToggleRow k="age_enabled" label="Ages" title="super-seasons: Golden / Ice / Chaos / Plague" />
                          <div className="god-note" style={{ fontSize: 11, opacity: 0.7, padding: '4px 10px' }}>
                            {t('god.ui.notes.theology_avatars')}
                          </div>
                        </>
                      )}

                      {/* Landscape & Elements (BN-15) */}
                      {group === 'Landscape & Elements' && (
                        <>
                          <ToggleRow k="rivers_enabled" label="Rivers" title="water channels with current, fords and bridges" />
                          <ToggleRow k="relief_enabled" label="Relief (elevation)" title="topographical elevation, slopes, cliffs and fall damage" />
                          <ToggleRow k="structural_enabled" label="Structural integrity" title="building decay and builder repairs" />
                        </>
                      )}

                      {/* Cosmology & Disasters (BN-15) */}
                      {group === 'Cosmology & Disasters' && (
                        <>
                          <ToggleRow k="wildfire_enabled" label="Wildfire" title="fire ignites and spreads across vegetation and houses" />
                          <ToggleRow k="disaster_enabled" label="Disasters" title="cataclysmic meteors, floods, and natural disturbances" />
                          <ToggleRow k="earthquake_enabled" label="Earthquakes" title="seismic tremors that shake terrain and crack stone" />
                          <ToggleRow k="lightning_enabled" label="Storm lightning" title="deadly electrical arc strikes during storms" />
                          <div className="god-note" style={{ fontSize: 11, opacity: 0.7, padding: '4px 10px' }}>
                            {t('god.ui.notes.cosmology')}
                          </div>
                        </>
                      )}
                    </>
                  )

                  const rows = visibleSpecs.map(renderLawRow)

                  return (
                    <section key={group} className="god-group">
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, borderBottom: '1px solid #30363d', paddingBottom: 6 }}>
                        <h3 style={{ margin: 0, fontSize: 13, color: '#e3b341', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                          {(t(`god.groups.${GROUP_KEY[group] ?? group}`) !== `god.groups.${GROUP_KEY[group] ?? group}` ? t(`god.groups.${GROUP_KEY[group] ?? group}`) : group)}
                        </h3>
                        <span style={{ fontSize: 10, color: '#8b949e', fontWeight: 600, background: '#21262d', padding: '1px 6px', borderRadius: 10, border: '1px solid #30363d' }}>
                          {t('god.ui.laws_count', { count: visibleSpecs.length })}
                        </span>
                      </div>
                      {special}
                      {rows}
                    </section>
                  )
                }).filter(Boolean)

                if (groupSections.length === 0) return null
                return (
                  <div key={domain.id} className="god-domain-section">
                    <div className="god-domain-header">
                      <span className="god-domain-title">{domain.icon} {t(`god.domains.${domain.id}`) !== `god.domains.${domain.id}` ? t(`god.domains.${domain.id}`) : domain.label}</span>
                      <span className="god-domain-meta">{t('god.ui.groups_sections', { groups: groupSections.length, sections: groupSections.length })}</span>
                    </div>
                    {groupSections}
                  </div>
                )
              })}
            </>
          )}
        </>
      )}

      {/* §BN-24: Import JSON Modal Dialog */}
      {showImportModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.7)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: 16,
          }}
          onClick={() => setShowImportModal(false)}
        >
          <div
            style={{
              background: '#161b22',
              border: '1px solid #30363d',
              borderRadius: 8,
              padding: 16,
              width: '100%',
              maxWidth: 480,
              display: 'flex',
              flexDirection: 'column',
              gap: 12,
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{ margin: 0, color: '#e6edf3', fontSize: 14 }}>{t('god.ui.importModalTitle')}</h3>
            <p style={{ margin: 0, color: '#8b949e', fontSize: 11 }}>
              {t('god.ui.importModalDesc')}
            </p>
            <textarea
              rows={8}
              value={importText}
              onChange={(e) => setImportText(e.target.value)}
              placeholder='{ "food_count": 400, "birth_rate": 0.4 }'
              style={{
                background: '#0d1117',
                border: '1px solid #30363d',
                borderRadius: 6,
                color: '#c9d1d9',
                padding: 8,
                fontFamily: 'monospace',
                fontSize: 12,
              }}
            />
            {importError && <span style={{ color: '#f85149', fontSize: 11 }}>{importError}</span>}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button
                type="button"
                onClick={() => setShowImportModal(false)}
                style={{ padding: '6px 12px', background: '#21262d', border: '1px solid #30363d', borderRadius: 6, color: '#c9d1d9', cursor: 'pointer' }}
              >
                {t('common.cancel')}
              </button>
              <button
                type="button"
                onClick={handleImportSubmit}
                style={{ padding: '6px 12px', background: '#238636', border: '1px solid #2ea043', borderRadius: 6, color: '#fff', fontWeight: 600, cursor: 'pointer' }}
              >
                {t('god.ui.applyImportedJson')}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )

  if (isMobile) {
    return (
      <div className="god-screen" role="dialog" aria-label="Laws of Nature">
        {head}
        <div className="god-screen-body">{body}</div>
        {foot}
      </div>
    )
  }

  return (
    <aside className="god-panel" onClick={e => e.stopPropagation()}>
      {head}
      {body}
      {foot}
    </aside>
  )
}

export default function GodPanel(props: Props) {
  if (!props.open) return null
  return (
    <GodPanelErrorBoundary>
      <GodPanelInner {...props} />
    </GodPanelErrorBoundary>
  )
}
