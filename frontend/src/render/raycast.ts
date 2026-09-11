import type { EntityState, StateMessage } from '../types'

export type RayHitType = 'food' | 'ally' | 'enemy' | 'house' | 'rock' | 'corpse' | 'wall' | null

export interface RayData {
  index: number
  name: 'left' | 'mid' | 'right'
  angle: number
  relAngleRad: number
  relAngleDeg: number
  maxDist: number
  hitDist: number
  hitType: RayHitType
  hitLabel: string
  hitPoint: { x: number; y: number }
  hitEntityId?: number
  nnDist: number
  nnType: number
}

export interface CreatureRaycastResult {
  origin: { x: number; y: number }
  creatureAngle: number
  spanFactor: number
  forwardGain: number
  rays: [RayData, RayData, RayData]
}

export function rayHitColor(hitType: RayHitType): string {
  switch (hitType) {
    case 'food':
      return '#3fb950'
    case 'ally':
      return '#58a6ff'
    case 'enemy':
      return '#f85149'
    case 'house':
      return '#d29922'
    case 'rock':
      return '#8b949e'
    case 'wall':
      return '#e3b341'
    case 'corpse':
      return '#a371f7'
    default:
      return 'rgba(88, 166, 255, 0.45)'
  }
}

export function toroidalDelta(target: number, origin: number, size: number): number {
  let d = target - origin
  const half = size * 0.5
  if (d > half) d -= size
  else if (d < -half) d += size
  return d
}

/**
 * Compute the 3 sensory rays for a creature matching backend/app/agent_pipeline.py.
 * Slot 3-8 in creature Micro-RNN input:
 *   3, 4: Left ray distance norm & type
 *   5, 6: Forward ray distance norm & type
 *   7, 8: Right ray distance norm & type
 */
export function computeCreatureRays(
  creature: EntityState,
  state: StateMessage,
): CreatureRaycastResult {
  const ox = creature.x
  const oy = creature.y
  const ang = creature.angle ?? 0

  // Morphological coupling (BH-7):
  // morph_traits: [area, perim, izz, theta_min, asym, dmult]
  let spanFactor = 1.0
  let forwardGain = 1.0
  const mt = creature.morph_traits
  if (Array.isArray(mt) && mt.length >= 6) {
    const perim = mt[1]
    const dmult = mt[5]
    if (typeof perim === 'number' && perim > 1e-3) {
      spanFactor = Math.max(0.75, Math.min(1.55, perim / 5.657))
    }
    if (typeof dmult === 'number') {
      forwardGain = 1.0 + dmult * 0.45
    }
  } else if (creature.caste === 'Soldier' || creature.sides === 3) {
    // Fallback for razor-sharp Soldiers if morph_traits not yet baked
    forwardGain = 1.35
    spanFactor = 0.9
  }

  // Base deltas: ±35° scaled by span_factor
  // 0.610865 rad = 35 * π / 180
  const BASE_SPAN_RAD = 0.610865238
  const deltas: [number, number, number] = [
    -BASE_SPAN_RAD * spanFactor,
    0.0,
    BASE_SPAN_RAD * spanFactor,
  ]
  const maxDs: [number, number, number] = [
    32.0,
    32.0 * forwardGain,
    32.0,
  ]
  const rayNames: Array<'left' | 'mid' | 'right'> = ['left', 'mid', 'right']

  const isWrap = state.boundary === 'wrap'
  const W = state.width
  const H = state.height

  const rays: RayData[] = []

  for (let ri = 0; ri < 3; ri++) {
    const delta = deltas[ri]
    const rayAngle = ang + delta
    const maxD = maxDs[ri]
    const cosA = Math.cos(rayAngle)
    const sinA = Math.sin(rayAngle)

    let bestDist = maxD
    let bestType: RayHitType = null
    let bestLabel = 'Clear'
    let bestEntityId: number | undefined

    // 1. World boundary collision if clamp mode
    if (!isWrap) {
      if (cosA > 1e-6) {
        const d = (W - ox) / cosA
        if (d > 0.2 && d < bestDist) {
          const hy = oy + sinA * d
          if (hy >= 0 && hy <= H) {
            bestDist = d
            bestType = 'wall'
            bestLabel = 'Wall (E)'
          }
        }
      } else if (cosA < -1e-6) {
        const d = -ox / cosA
        if (d > 0.2 && d < bestDist) {
          const hy = oy + sinA * d
          if (hy >= 0 && hy <= H) {
            bestDist = d
            bestType = 'wall'
            bestLabel = 'Wall (W)'
          }
        }
      }

      if (sinA > 1e-6) {
        const d = (H - oy) / sinA
        if (d > 0.2 && d < bestDist) {
          const hx = ox + cosA * d
          if (hx >= 0 && hx <= W) {
            bestDist = d
            bestType = 'wall'
            bestLabel = 'Wall (S)'
          }
        }
      } else if (sinA < -1e-6) {
        const d = -oy / sinA
        if (d > 0.2 && d < bestDist) {
          const hx = ox + cosA * d
          if (hx >= 0 && hx <= W) {
            bestDist = d
            bestType = 'wall'
            bestLabel = 'Wall (N)'
          }
        }
      }
    }

    // 2. Intersect world entities
    if (state.entities) {
      for (let i = 0; i < state.entities.length; i++) {
        const e = state.entities[i]
        if (e.id === creature.id) continue

        const dx = isWrap ? toroidalDelta(e.x, ox, W) : (e.x - ox)
        const dy = isWrap ? toroidalDelta(e.y, oy, H) : (e.y - oy)

        const proj = dx * cosA + dy * sinA
        if (proj <= 0.2 || proj >= bestDist) continue

        const perp = Math.abs(dx * sinA - dy * cosA)
        const hitRadius = e.kind === 'food' ? 1.8 : 2.2

        if (perp <= hitRadius) {
          bestDist = proj
          bestEntityId = e.id
          if (e.kind === 'food') {
            bestType = 'food'
            bestLabel = e.variant ? `Food (${e.variant})` : 'Food'
          } else if (e.kind === 'house') {
            bestType = 'house'
            bestLabel = (e as any).clan_name ? `House (${(e as any).clan_name})` : 'House'
          } else if (e.kind === 'corpse') {
            bestType = 'corpse'
            bestLabel = 'Corpse'
          } else if (e.kind === 'creature') {
            const isAlly =
              typeof creature.clan_id === 'number' &&
              creature.clan_id > 0 &&
              creature.clan_id === e.clan_id
            if (isAlly) {
              bestType = 'ally'
              bestLabel = e.personal_name ? `Ally (${e.personal_name})` : `Ally #${e.id}`
            } else {
              bestType = 'enemy'
              bestLabel = e.personal_name ? `Rival (${e.personal_name})` : `Rival #${e.id}`
            }
          }
        }
      }
    }

    // 3. Intersect terrain rocks
    if (state.terrain_rocks) {
      for (let i = 0; i < state.terrain_rocks.length; i++) {
        const rock = state.terrain_rocks[i]
        const dx = isWrap ? toroidalDelta(rock.x, ox, W) : (rock.x - ox)
        const dy = isWrap ? toroidalDelta(rock.y, oy, H) : (rock.y - oy)

        const proj = dx * cosA + dy * sinA
        if (proj <= 0.2 || proj >= bestDist) continue

        const perp = Math.abs(dx * sinA - dy * cosA)
        const r = rock.r ?? 2.0
        if (perp <= r) {
          bestDist = proj
          bestType = 'rock'
          bestLabel = 'Rock'
          bestEntityId = undefined
        }
      }
    }

    // Calculate hit point in world space
    const hitPoint = {
      x: ox + cosA * bestDist,
      y: oy + sinA * bestDist,
    }

    // Normalized neural distance [0, 1] (closer = higher)
    let nnDist = 1.0 - Math.min(bestDist / maxD, 1.0)
    if (ri === 1 && forwardGain !== 1.0) {
      nnDist = Math.min(1.0, nnDist * forwardGain)
    }

    // Type encoding: food/ally = +1.0, obstacle/wall = 0.0, enemy = -1.0, none = 0.0
    let nnType = 0.0
    if (bestType === 'food' || bestType === 'ally') {
      nnType = 1.0
    } else if (bestType === 'enemy') {
      nnType = -1.0
    } else {
      nnType = 0.0
    }

    rays.push({
      index: ri,
      name: rayNames[ri],
      angle: rayAngle,
      relAngleRad: delta,
      relAngleDeg: Math.round((delta * 180) / Math.PI),
      maxDist: maxD,
      hitDist: bestDist,
      hitType: bestType,
      hitLabel: bestLabel,
      hitPoint,
      hitEntityId: bestEntityId,
      nnDist,
      nnType,
    })
  }

  return {
    origin: { x: ox, y: oy },
    creatureAngle: ang,
    spanFactor,
    forwardGain,
    rays: rays as [RayData, RayData, RayData],
  }
}
