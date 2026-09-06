/** Mirrors backend/app/protocol.py. Keep in sync. */

export type EntityKind = 'creature' | 'food' | 'house' | 'corpse'
export type EntityShape = 'polygon' | 'line'
export type HungerStatus = '' | 'hungry' | 'starving'

export interface EntityState {
  id: number
  kind: EntityKind
  x: number
  y: number
  angle: number
  shape?: EntityShape
  sides?: number
  caste?: string
  energy?: number
  size?: number
  status?: HungerStatus
  radius?: number
  age?: number
  lifespan?: number
  stage?: 'infant' | 'juvenile' | 'adult' | 'elder'
  irregularity?: number
  health?: number
  infected?: boolean
  meals?: number
  clan_id?: number
  clan_color?: string
  clan_name?: string
  clan_totem?: string
  is_predator?: boolean
  is_herbivore?: boolean
  sleeping?: boolean
  indoors?: boolean
  generation?: number
  born_tick?: number
  personal_name?: string
  glyph?: string
  hue_shift?: number
  scale_jitter?: number
  angle_jitter?: number
  chill?: number
  body_temp?: number
  torpid?: boolean | null
  trait?: string | null
  equipped_item?: 'spear' | 'basket' | 'torch' | 'herb_poultice' | 'crown' | null
  food_basket?: number
  personality?: 'brave' | 'cautious' | 'altruistic' | 'greedy' | 'explorer' | 'builder'
  skills?: { farming?: number; combat?: number; foraging?: number; healing?: number }
  title?: string | null
  emote?: 'hungry' | 'love' | 'combat' | 'panic' | 'heal' | 'cheer' | 'sleep' | 'craft' | null
  door_width?: number
  door_offset?: number
  door_side?: 'north' | 'east' | 'south' | 'west'
  is_main?: boolean
  is_ruin?: boolean
  abandoned_ticks?: number
  takeover_age?: number | null
  material?: 'straw' | 'wood' | 'stone'
  hearth_lit?: boolean | null
  hp_frac?: number | null
  rubble?: boolean | null
  murals?: number
  growth?: number
  variant?: 'grass' | 'grain' | 'berry' | 'medicinal_herb' | 'mushroom' | 'poisonous'
  withering?: boolean
  cultivated?: boolean
  irrigated?: boolean

  sex?: 'male' | 'female'
  mother_id?: number
  father_id?: number
  iso_angle?: number | null  // §BG soldier razor
  morph_k?: number | null  // §BG K∈[3,24]
  morph_traits?: number[] | null  // §BG [A,P,Izz,theta_min,asym,Dmult]
  morph_radii?: number[] | null
  morph_angles?: number[] | null
  archetype?: string | null  // §BH-9
  nn_hidden?: number | null
  nn_outputs?: number[] | null
  nn_genome_preview?: number[] | null
  nn_genome?: number[] | null  // §BH-10 full 295 (detail only)
}

export interface ClanHistoryEvent {
  tick: number
  day: number
  event: string
  desc: string
}

export interface ClanInfo {
  name: string
  founder_id: number
  born_tick: number
  founded_day?: number
  dead_count?: number
  color: string
  totem?: string
  culture?: string
  culture_id?: number
  leader_id?: number | null
  main_house_id?: number | null
  coalition_id?: number | null
  larder?: number
  granary?: number
  harvest_total?: number
  feast?: boolean
  dialect?: number
  tribute_to?: number | null
  faith?: number
  shrine_level?: number
  population?: number
  war_wins?: number
  war_losses?: number
  history?: ClanHistoryEvent[]
}

export interface StateMessage {
  type: 'state'
  tick: number
  seed: number
  width: number
  height: number
  boundary: 'wrap' | 'clamp'
  population: Record<string, number>
  entities: EntityState[]
  creatures_alive: number
  creatures_dead: number
  dead_by_cause: Record<string, number>
  infected_count: number
  time_of_day: number
  day: number
  season: 'spring' | 'summer' | 'autumn' | 'winter'
  weather: 'clear' | 'rain' | 'fog' | 'storm'
  terrain_fertile: { x: number; y: number; r: number }[]
  terrain_rocks: { x: number; y: number; r: number }[]
  relations: { a: number; b: number; score: number }[]
  clans: Record<string, ClanInfo>
  events: HistoryEvent[]
  signals: { x: number; y: number; kind: 'food' | 'alarm'; sender: number; clan_id: number | null; ttl: number }[]
  fires: { x: number; y: number; r: number; ttl: number }[]
  campfires?: { x: number; y: number }[]
  boundary_stones?: { x: number; y: number; clan_id: number }[]
  markets?: { x: number; y: number; a: number; b: number }[]
  wind?: { angle: number; speed: number }
  rivers?: { cy: number; hw: number; dir: number; flood: boolean }[]
  bridges?: { x: number; cy: number }[]
  dams?: { x: number; cy: number; hp_frac: number }[]
  elevation?: { cell: number; cols: number; rows: number; h: number[] }
  lightning?: { x: number; y: number; ttl: number }[]
  anomalies?: { x: number; y: number; kind: string }[]
  law_wave?: { born_tick: number; ticks: number }
  age: string | null
  age_tick: number
  age_day?: number
  age_total_days?: number
  paused?: boolean
  analytics?: any
  safeguard_active?: boolean
  softcap_active?: boolean
}

export interface DeltaStateMessage {
  type: 'delta_state'
  tick: number
  seed: number
  upsert_entities: EntityState[]
  remove_ids: number[]
  population: Record<string, number>
  creatures_alive: number
  creatures_dead: number
  dead_by_cause: Record<string, number>
  infected_count: number
  time_of_day: number
  day: number
  season: 'spring' | 'summer' | 'autumn' | 'winter'
  weather: 'clear' | 'rain' | 'fog' | 'storm'
  relations?: { a: number; b: number; score: number }[]
  clans?: Record<string, ClanInfo>

  events: HistoryEvent[]
  signals: { x: number; y: number; kind: 'food' | 'alarm'; sender: number; clan_id: number | null; ttl: number }[]
  fires: { x: number; y: number; r: number; ttl: number }[]
  campfires?: { x: number; y: number }[]
  boundary_stones?: { x: number; y: number; clan_id: number }[]
  markets?: { x: number; y: number; a: number; b: number }[]
  wind?: { angle: number; speed: number }
  rivers?: { cy: number; hw: number; dir: number; flood: boolean }[]
  bridges?: { x: number; cy: number }[]
  dams?: { x: number; cy: number; hp_frac: number }[]
  elevation?: { cell: number; cols: number; rows: number; h: number[] }
  lightning?: { x: number; y: number; ttl: number }[]
  anomalies?: { x: number; y: number; kind: string }[]
  law_wave?: { born_tick: number; ticks: number }
  age: string | null
  age_tick: number
  age_day?: number
  age_total_days?: number
  paused?: boolean
  safeguard_active?: boolean
  softcap_active?: boolean
}


export interface HistoryEvent {
  /** Present only on events fetched from GET /api/history; absent on live-streamed ones. */
  id?: number
  type: 'death' | 'birth' | 'promotion' | 'demotion' | 'outbreak' | 'recovery' | 'bloom' | 'alliance' | 'rivalry' | 'predation' | 'war' | 'ruin' | 'settlement' | 'succession' | 'schism' | 'fire' | 'disaster' | 'conquest' | 'culture' | 'takeover' | 'coalition_formed' | 'coalition_joined' | 'coalition_dissolved' | 'peace' | 'tribute' | 'betrayal' | 'defection' | 'cannibalism' | 'exile' | 'wither'
    | 'coalition_formed' | 'coalition_joined' | 'coalition_dissolved' | 'peace' | 'tribute' | 'betrayal' | 'defection' | 'cannibalism' | 'exile' | 'wither'
    | 'miracle' | 'sermon' | 'synod' | 'temple' | 'epiphany' | 'resonance'
    | 'compost' | 'banquet' | 'raid' | 'hospitality'
    | 'peace_envoy' | 'market' | 'caravan' | 'omen'
    | 'regicide' | 'herald'
  tick: number
  entity_id: number
  caste?: string | null
  cause?: string
  x: number
  y: number
  payload?: Record<string, unknown>
}

export interface HelloMessage {
  type: 'hello'
  seed: number
  tick_rate: number
  width: number
  height: number
  boundary: 'wrap' | 'clamp'
  paused?: boolean
}

/** One row of GET /api/worlds — a past or current world run. */
export interface WorldSummary {
  id: number
  seed: number
  width: number
  height: number
  boundary: 'wrap' | 'clamp'
  started_at: string
  ended_at: string | null
}

/** House wall segments for rendering; mirrors backend _house_wall_segments. */
export function houseWallSegments(
  x: number,
  y: number,
  size: number,
  side: string,
  doorWidth: number,
  doorOffset: number,
): [number, number, number, number][] {
  const h = size / 2
  const x0 = x - h
  const x1 = x + h
  const y0 = y - h
  const y1 = y + h
  const d = doorWidth / 2
  const cx = x + doorOffset
  const cy = y + doorOffset
  switch (side) {
    case 'north':
      return [
        [x0, y0, cx - d, y0],
        [cx + d, y0, x1, y0],
        [x0, y0, x0, y1],
        [x1, y0, x1, y1],
        [x0, y1, x1, y1],
      ]
    case 'west':
      return [
        [x0, y0, x1, y0],
        [x0, y1, x1, y1],
        [x1, y0, x1, y1],
        [x0, y0, x0, cy - d],
        [x0, cy + d, x0, y1],
      ]
    case 'east':
      return [
        [x0, y0, x1, y0],
        [x0, y0, x0, y1],
        [x0, y1, x1, y1],
        [x1, y0, x1, cy - d],
        [x1, cy + d, x1, y1],
      ]
    default: // south
      return [
        [x0, y0, x1, y0],
        [x0, y0, x0, y1],
        [x1, y0, x1, y1],
        [x0, y1, cx - d, y1],
        [cx + d, y1, x1, y1],
      ]
  }
}

export type ControlAction = 'pause' | 'resume' | 'step' | 'reset' | 'set_speed'

export interface ControlMessage {
  action: ControlAction
  value?: number
  /** god passkey — control actions are rejected without it */
  key?: string
}

/** Laws of nature god may set — never per-creature interventions. */
export interface GodLaws {
  boundary?: 'wrap' | 'clamp'
  food_count?: number
  plant_growth_rate?: number
  plant_spread_rate?: number
  nutrient_cycle_rate?: number
  plant_variants_enabled?: boolean
  poison_rate?: number
  beast_ratio?: number
  diet_strictness?: number
  territory_enabled?: boolean
  territory_radius?: number
  trespass_decay?: number
  totems_enabled?: boolean
  succession_enabled?: boolean
  max_clans?: number
  energy_max?: number
  energy_decay_per_tick?: number
  energy_from_food?: number
  hungry_ratio?: number
  starving_ratio?: number
  perceive_radius?: number
  eat_radius?: number
  wander_turn?: number
  steer_turn?: number
  hungry_perceive_mult?: number
  desperate_perceive_mult?: number
  desperate_speed_mult?: number
  food_giveup_ticks?: number
  lifespan_mult?: number

  // Reproduction & inheritance (Nature's Law)
  birth_enabled?: boolean
  adult_age?: number
  mate_radius?: number
  mate_energy_min?: number
  birth_rate?: number
  sex_ratio?: number
  mutation_rate?: number
  mutation_heritability?: number
  max_sides?: number
  birth_energy_cost?: number
  reproduction_cooldown?: number
  carrying_capacity?: number
  max_population?: number
  euthanasia_threshold?: number

  // Health & disease
  disease_enabled?: boolean
  disease_outbreak_rate?: number
  disease_rate?: number
  disease_radius?: number
  disease_energy_drain?: number
  recovery_rate?: number
  disease_lethality?: number

  // Environment: sky, seasons, weather
  day_length?: number
  season_length?: number
  winter_food_mult?: number
  night_sight_mult?: number
  weather_enabled?: boolean
  weather_change_rate?: number
  fog_sight_mult?: number
  rain_speed_mult?: number
  storm_wander_bonus?: number
  sleep_enabled?: boolean
  sleep_energy_mult?: number
  rain_growth_mult?: number
  fog_mushroom_mult?: number
  storm_plant_damage?: number
  weather_sickness_enabled?: boolean
  chill_rate?: number
  chill_threshold?: number
  chill_drain?: number
  wet_disease_mult?: number

  // Shelter — roofs against the sky
  shelter_enabled?: boolean
  hearths_enabled?: boolean
  rivers_enabled?: boolean
  river_count?: number
  relief_enabled?: boolean
  structural_enabled?: boolean
  rubble_blocking_enabled?: boolean
  earthquake_enabled?: boolean
  earthquake_rate?: number
  signal_speed?: number
  lightning_enabled?: boolean
  lightning_strike_rate?: number
  anomaly_count?: number
  exposure_drain?: number
  house_capacity?: number
  house_claim_enabled?: boolean
  rest_recovery_mult?: number
  house_decay_ticks?: number

  communication_enabled?: boolean
  signal_radius?: number
  food_call_rate?: number
  alarm_call_rate?: number

  // Communication II — knowledge, teaching & mobbing (§X)
  knowledge_enabled?: boolean
  knowledge_ttl?: number
  knowledge_share_rate?: number
  help_call_enabled?: boolean
  help_radius?: number
  defense_weight?: number
  age_enabled?: boolean
  age_length?: number
  culture_enabled?: boolean
  culture_spread_rate?: number
  trait_mutation_rate?: number
  wildfire_enabled?: boolean
  fire_rate?: number
  fire_spread_rate?: number
  disaster_enabled?: boolean
  disaster_rate?: number

  schism_enabled?: boolean
  schism_threshold?: number
  schism_min_pop?: number

  // Politics (§AB) — coalitions, leaders, resources, betrayal
  coalitions_enabled?: boolean
  coalition_threshold?: number
  coalition_min_size?: number
  leader_decisions_enabled?: boolean
  resource_sharing_enabled?: boolean
  larder_capacity?: number
  aid_rate?: number
  tribute_enabled?: boolean
  betrayal_enabled?: boolean
  defection_enabled?: boolean

  // Desperation cannibalism (§AC)
  cannibalism_enabled?: boolean
  cannibalism_hunger_ratio?: number
  cannibalism_energy?: number
  eat_enemy_enabled?: boolean
  eat_kin_enabled?: boolean
  kin_stigma?: number
  exile_on_kin_eat?: boolean

  // Food decay (§AE)
  food_decay_enabled?: boolean
  food_lifespan_ticks?: number

  // Unified Theology (§AP) — shrines, tithes & the clan faith pool
  theology_enabled?: boolean
  tithe_rate?: number
  temple_faith_cost?: number

  // Agriculture (§AM) — sowing, farm plots, granaries, soil & feasts
  agriculture_enabled?: boolean
  granaries_enabled?: boolean
  granary_capacity?: number
  soil_depletion_enabled?: boolean
  banquets_enabled?: boolean

  // Communication, language & diplomacy (§AN)
  vocalizations_enabled?: boolean
  scent_enabled?: boolean
  envoys_enabled?: boolean
  markets_enabled?: boolean
  omens_enabled?: boolean
  dialect_drift_enabled?: boolean

  door_clearance?: number
  house_min_size?: number
  house_max_size?: number

  // Predation (§I)
  predation_enabled?: boolean
  predator_ratio?: number
  hunt_radius?: number
  bite_damage?: number
  bite_cooldown?: number
  energy_from_prey?: number
  fear_radius?: number

  // Clan war (§I)
  war_enabled?: boolean
  attack_radius?: number
  attack_damage?: number

  // Society — interaction
  cohesion_weight?: number
  alignment_weight?: number
  separation_weight?: number
  flock_radius?: number
  relation_drift_rate?: number
  alliance_threshold?: number
  rivalry_threshold?: number

  // Neuroevolution (BA) — always on, 295 fixed
  nn_inference_hz?: number
  mutation_sigma?: number
  crossover_rate?: number

  // Morphology (BC) — geometric physics & annealing
  morphology_annealing_enabled?: boolean
  annealing_start_generation?: number
  annealing_decay_generations?: number
  morph_lambda_override?: number | null
  vertex_mutation_std?: number
  angle_mutation_std?: number
  topological_mutation_rate?: number

  // Extinction Safeguards (Phase 5)
  safeguard_enabled?: boolean
  safeguard_critical_pop?: number
  safeguard_relief_ratio?: number
  safeguard_genesis_batch?: number
  safeguard_morph_mercy?: boolean

  // Density-Dependent Soft-Cap Damping (Phase 4)
  soft_cap_enabled?: boolean
  damping_steepness?: number
  crowding_stress_mult?: number
  resource_strain_mult?: number
}
