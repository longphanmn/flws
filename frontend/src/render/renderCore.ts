import type { EntityState, LensMode, StateMessage } from '../types'
import { houseWallSegments } from '../types'
import { TOTEMS } from '../totems'
import { computeCreatureRays, rayHitColor } from './raycast'

export const TAU = Math.PI * 2
const _riverGradCacheGlobal = new Map<string, CanvasGradient>()
// @ts-ignore unused alias kept for type compat
const _riverGradCache: Map<string, CanvasGradient> = _riverGradCacheGlobal as Map<string, CanvasGradient>
// §AO E: matches backend CAMPFIRE_LIGHT_RADIUS
const CAMPFIRE_LIGHT_RADIUS = 3.5
export const PRIEST_SIDES = 24
export const MIN_SCALE_FACTOR = 0.4
export const MAX_SCALE = 80

// §BG: deterministic pseudo-random per creature/vertex (sin-hash, no allocation)
function bgPseudoRand(seed: number, i: number): number {
  const x = Math.sin(seed * 127.1 + i * 311.7) * 43758.5453
  return x - Math.floor(x)
}
// §BG & §BK: mutated polygon helpers — reconstruct irregular vertices from (sides, irregularity, id)
export function bgMutatedPoints(
  cx: number, cy: number, sides: number, radius: number, baseAngle: number,
  irregularity: number, id: number, tick = 0,
): Array<[number, number]> {
  const irr = Math.max(0, Math.min(1, irregularity || 0))
  const pts: Array<[number, number]> = []
  const startAng = baseAngle - Math.PI / 2
  const dynamicOsc = irr > 0.04 && tick > 0
  for (let i = 0; i < sides; i++) {
    const aJitter = (bgPseudoRand(id, i * 2) - 0.5) * irr * 0.65
    let rJitter = 1 + (bgPseudoRand(id, i * 2 + 1) - 0.5) * irr * 0.9
    // BK-3: Jagged spires / thorny barbs on irregular mutants
    if (irr > 0.15 && (i % 2 === 0)) {
      rJitter += (bgPseudoRand(id, i * 5 + 3) > 0.45 ? 1 : -0.25) * irr * 0.45
    }
    // BK-3: Dynamic chaotic breathing oscillation
    if (dynamicOsc) {
      rJitter += Math.sin(tick * 0.28 + i * 2.1 + (id % 17)) * irr * 0.12
    }
    const a = startAng + (i / sides) * TAU + aJitter
    const rr = radius * rJitter
    pts.push([cx + Math.cos(a) * rr, cy + Math.sin(a) * rr])
  }
  return pts
}
// §BG & §BK-5: true isosceles soldier razor apex points (extended needle apex when θ < 30°)
export function bgSoldierRazor(cx: number, cy: number, radius: number, heading: number, isoAngleDeg: number): Array<[number, number]> {
  const theta = Math.max(8, Math.min(59.8, isoAngleDeg)) * Math.PI / 180
  const needleMult = isoAngleDeg < 30 ? 1.0 + ((30 - isoAngleDeg) / 30) * 0.45 : 1.0
  const xr = radius * 1.05 * needleMult
  const xb = radius * 0.55
  const dx = xr + xb
  const yb = dx * Math.tan(theta / 2)
  // local triangle: apex forward, base left/right behind
  const local: Array<[number, number]> = [
    [xr, 0],
    [-xb, yb],
    [-xb, -yb],
  ]
  const ca = Math.cos(heading), sa = Math.sin(heading)
  return local.map(([lx, ly]) => [cx + lx * ca - ly * sa, cy + lx * sa + ly * ca])
}

// Scratch buffer for points where explicit array coordinates are required (e.g. blade glint sharpest vertex)
const _scratchPts: [number, number][] = []
for (let i = 0; i < 64; i++) _scratchPts.push([0, 0])

export function bgMutatedPointsScratch(
  cx: number, cy: number, sides: number, radius: number, baseAngle: number,
  irregularity: number, id: number, tick = 0,
): [number, number][] {
  const irr = Math.max(0, Math.min(1, irregularity || 0))
  const startAng = baseAngle - Math.PI / 2
  const dynamicOsc = irr > 0.04 && tick > 0
  const n = Math.min(sides, 64)
  for (let i = 0; i < n; i++) {
    const aJitter = (bgPseudoRand(id, i * 2) - 0.5) * irr * 0.65
    let rJitter = 1 + (bgPseudoRand(id, i * 2 + 1) - 0.5) * irr * 0.9
    if (irr > 0.15 && (i % 2 === 0)) {
      rJitter += (bgPseudoRand(id, i * 5 + 3) > 0.45 ? 1 : -0.25) * irr * 0.45
    }
    if (dynamicOsc) {
      rJitter += Math.sin(tick * 0.28 + i * 2.1 + (id % 17)) * irr * 0.12
    }
    const a = startAng + (i / sides) * TAU + aJitter
    const rr = radius * rJitter
    _scratchPts[i][0] = cx + Math.cos(a) * rr
    _scratchPts[i][1] = cy + Math.sin(a) * rr
  }
  return _scratchPts
}

// Zero-allocation mutated polygon path tracer directly into Canvas2D
export function bgTraceMutatedPath(
  ctx: CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D | CanvasPath,
  cx: number, cy: number, sides: number, radius: number, baseAngle: number,
  irregularity: number, id: number, tick = 0,
): void {
  const irr = Math.max(0, Math.min(1, irregularity || 0))
  const startAng = baseAngle - Math.PI / 2
  const dynamicOsc = irr > 0.04 && tick > 0
  for (let i = 0; i < sides; i++) {
    const aJitter = (bgPseudoRand(id, i * 2) - 0.5) * irr * 0.65
    let rJitter = 1 + (bgPseudoRand(id, i * 2 + 1) - 0.5) * irr * 0.9
    if (irr > 0.15 && (i % 2 === 0)) {
      rJitter += (bgPseudoRand(id, i * 5 + 3) > 0.45 ? 1 : -0.25) * irr * 0.45
    }
    if (dynamicOsc) {
      rJitter += Math.sin(tick * 0.28 + i * 2.1 + (id % 17)) * irr * 0.12
    }
    const a = startAng + (i / sides) * TAU + aJitter
    const rr = radius * rJitter
    const px = cx + Math.cos(a) * rr
    const py = cy + Math.sin(a) * rr
    if (i === 0) ctx.moveTo(px, py)
    else ctx.lineTo(px, py)
  }
  ctx.closePath()
}

// Zero-allocation soldier razor triangle path tracer
export function bgTraceSoldierRazor(
  ctx: CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D | CanvasPath,
  cx: number, cy: number, radius: number, heading: number, isoAngleDeg: number,
): void {
  const theta = Math.max(8, Math.min(59.8, isoAngleDeg)) * Math.PI / 180
  const needleMult = isoAngleDeg < 30 ? 1.0 + ((30 - isoAngleDeg) / 30) * 0.45 : 1.0
  const xr = radius * 1.05 * needleMult
  const xb = radius * 0.55
  const dx = xr + xb
  const yb = dx * Math.tan(theta / 2)
  const ca = Math.cos(heading), sa = Math.sin(heading)

  ctx.moveTo(cx + xr * ca, cy + xr * sa)
  ctx.lineTo(cx - xb * ca - yb * sa, cy - xb * sa + yb * ca)
  ctx.lineTo(cx - xb * ca + yb * sa, cy - xb * sa - yb * ca)
  ctx.closePath()
}

// Apex point of soldier razor (zero allocation tuple replacement)
export function bgSoldierRazorApex(
  cx: number, cy: number, radius: number, heading: number, isoAngleDeg: number,
): [number, number] {
  const needleMult = isoAngleDeg < 30 ? 1.0 + ((30 - Math.max(8, Math.min(59.8, isoAngleDeg))) / 30) * 0.45 : 1.0
  const xr = radius * 1.05 * needleMult
  return [cx + xr * Math.cos(heading), cy + xr * Math.sin(heading)]
}

// §BK-9 Unified Genome Mirror & Evolutionary Lens styling helper
export function getCreatureLensStyle(
  c: EntityState,
  _lensMode: LensMode = 'mutants',
): { color: string; fillAlpha: number; strokeAlpha: number } {
  const gen = (c as any).generation ?? 0
  const irr = (c as any).irregularity ?? 0
  const mt = (c as any).morph_traits as number[] | undefined
  const dmult = mt && mt.length > 5 ? mt[5] : 0

  // 1. Generational Epoch Base Color (Evolving across millennia from Gen 0 to Gen 2000+)
  let baseColor: string
  if (gen < 5) {
    baseColor = '#38bdf8' // Primordial Genesis Sky Cyan
  } else if (gen < 25) {
    baseColor = '#06b6d4' // Early Pioneer Aqua
  } else if (gen < 75) {
    baseColor = '#10b981' // Formative Dynasty Jade
  } else if (gen < 200) {
    baseColor = '#8b5cf6' // Imperial Classical Violet
  } else if (gen < 500) {
    baseColor = '#ec4899' // Ancient Sovereign Magenta
  } else if (gen < 1000) {
    baseColor = '#f97316' // Millennial Solar Ember
  } else if (gen < 2000) {
    baseColor = '#facc15' // Eon Sovereign Gold
  } else {
    baseColor = '#fef08a' // Gen 2000+: Transcendent Celestial Diamond Starlight
  }

  // 2. Genomic Mutation & Aberration Shifts
  let color = baseColor
  if (irr > 0.28) {
    // Extreme radioactive mutation
    color = '#f43f5e'
  } else if (irr > 0.16) {
    // Severe aberration
    color = gen >= 500 ? '#f43f5e' : '#d946ef'
  } else if (irr > 0.08) {
    // Moderate genetic drift
    color = gen >= 200 ? '#e11d48' : '#a855f7'
  } else if (irr < 0.03 && gen < 50) {
    // Strict Abbott geometric orthodoxy
    if (c.caste && CASTE_COLORS[c.caste]) {
      color = CASTE_COLORS[c.caste]
    }
  }

  // 3. Fill and stroke alpha mirroring genetic vitality & age
  const fillAlpha = Math.min(0.58, 0.22 + Math.min(0.24, gen / 2500) + irr * 0.16)
  const strokeAlpha = Math.min(1.0, 0.88 + (dmult * 0.12) + (gen > 200 ? 0.12 : 0))

  return { color, fillAlpha, strokeAlpha }
}

export function clusterEntities<T extends { x: number; y: number }>(entities: T[], maxDist: number = 38.0): T[][] {
  if (entities.length === 0) return []
  const clusters: T[][] = []
  const visited = new Set<number>()

  for (let i = 0; i < entities.length; i++) {
    if (visited.has(i)) continue
    const cluster: T[] = []
    const queue: number[] = [i]
    visited.add(i)

    while (queue.length > 0) {
      const currIdx = queue.pop()!
      const curr = entities[currIdx]
      cluster.push(curr)

      for (let j = 0; j < entities.length; j++) {
        if (visited.has(j)) continue
        const other = entities[j]
        const dx = curr.x - other.x
        const dy = curr.y - other.y
        if (dx * dx + dy * dy <= maxDist * maxDist) {
          visited.add(j)
          queue.push(j)
        }
      }
    }
    clusters.push(cluster)
  }
  return clusters
}

export const CASTE_COLORS: Record<string, string> = {
  Soldier: '#ff7b72',
  Artisan: '#f2cc60',
  Gentleman: '#ffa657',
  Professional: '#d2a8ff',
  Noble: '#79c0ff',
  Priest: '#e6edf3',
  Woman: '#ff9bce',
  Predator: '#ff3838',
  Herbivore: '#90be6d',
}

export const EMOTE_ICONS: Record<string, string> = {
  hungry: '🍖',
  love: '❤️',
  combat: '⚔️',
  panic: '😱',
  heal: '🌿',
  cheer: '🏆',
  sleep: '💤',
  craft: '🧺',
  grief: '🥀',
  fear: '❗',
}

export interface Camera {
  scale: number
  ox: number
  oy: number
  initialized: boolean
}

export function drawWeather(
  ctx: CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D,
  weather: string,
  cw: number,
  ch: number,
): void {
  if (weather === 'fog') {
    ctx.fillStyle = 'rgba(190,205,225,0.13)'
    ctx.fillRect(0, 0, cw, ch)
    return
  }
  if (weather !== 'rain' && weather !== 'storm') return
  const isMobile = cw <= 768
  const drops = isMobile ? (weather === 'storm' ? 50 : 25) : (weather === 'storm' ? 120 : 60)
  const t = performance.now() / 16
  ctx.strokeStyle = 'rgba(140,170,220,0.35)'
  ctx.lineWidth = Math.max(1, cw / 1200)
  ctx.beginPath()
  for (let i = 0; i < drops; i++) {
    const x = (i * 977 + t * (13 + (i % 5))) % cw
    const y = (i * 613 + t * (23 + (i % 7) * 3)) % ch
    ctx.moveTo(x, y)
    ctx.lineTo(x - cw * 0.004, y + ch * 0.02)
  }
  ctx.stroke()
}

// §AQ PH-6: house wall tints
const HOUSE_MAT_TINT: Record<string, string> = {
  straw: 'rgba(214,177,94,0.10)',
  wood: 'rgba(150,111,64,0.12)',
  stone: 'rgba(140,150,160,0.14)',
  clay: 'rgba(190,106,66,0.16)',
}

// §AN / §AP Signal color lookup
const SIGNAL_COLOR: Record<string, string> = {
  food: '#3fb950',
  alarm: '#f85149',
  help: '#ffd166',
  knowledge: '#79c0ff',
  grief: '#8b949e',
  chime: '#e3b341', // §AP divine law resonance + §AN boundary stones
  chant: '#b392f0', // §AN priest liturgy
  hum: '#ff9ecd',   // §AN woman's peace-hum
  war: '#ff7b72',   // §AN soldier war-chirp
  trail: '#d2a8ff', // §AN forager scent trail
  danger_scent: '#6e7681', // §AN death-site marker
  courier: '#e3b341',      // §AN tribute courier
  omen: '#e3b341',         // §AN season omen
}

interface GroupBatch {
  list: EntityState[]
  fillAlpha: number
  strokeAlpha: number
}

// §BL-1: Cached offscreen canvas for elevation hillshade (eliminates 15,000 fillRect/frame)
interface ElevationCache {
  canvas: HTMLCanvasElement | OffscreenCanvas
  ref: number[]
  rows: number
  cols: number
}
let _cachedElev: ElevationCache | null = null

function getElevationCanvas(elev: { cell: number; rows: number; cols: number; h?: number[] }): HTMLCanvasElement | OffscreenCanvas | null {
  if (!elev || !elev.h || !elev.h.length || !elev.rows || !elev.cols) return null
  if (
    _cachedElev &&
    _cachedElev.ref === elev.h &&
    _cachedElev.rows === elev.rows &&
    _cachedElev.cols === elev.cols
  ) {
    return _cachedElev.canvas
  }

  const cols = elev.cols
  const rows = elev.rows
  let canvas: HTMLCanvasElement | OffscreenCanvas
  if (typeof OffscreenCanvas !== 'undefined') {
    canvas = new OffscreenCanvas(cols, rows)
  } else {
    canvas = document.createElement('canvas')
    canvas.width = cols
    canvas.height = rows
  }

  const ctx = canvas.getContext('2d') as CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D | null
  if (!ctx) return null

  const imgData = ctx.createImageData(cols, rows)
  const data = imgData.data
  const hArr = elev.h

  for (let row = 0; row < rows; row++) {
    const rowOffset = row * cols
    for (let col = 0; col < cols; col++) {
      const idx = rowOffset + col
      const h = hArr[idx] ?? 0.5
      const light = hArr[rowOffset + Math.max(0, col - 1)] ?? h
      const shade = h - light
      const v = Math.round(18 + h * 26)
      const r = Math.max(0, Math.min(255, Math.round(v + shade * 40)))
      const g = Math.max(0, Math.min(255, Math.round(v + 8 + shade * 30)))
      const b = Math.max(0, Math.min(255, Math.round(v - 4)))
      const a = 140 // ~0.55 * 255
      const p = idx * 4
      data[p] = r
      data[p + 1] = g
      data[p + 2] = b
      data[p + 3] = a
    }
  }

  ctx.putImageData(imgData, 0, 0)
  _cachedElev = {
    canvas,
    ref: elev.h,
    rows,
    cols,
  }
  return canvas
}

// §AV F-1 & §BL-3: persistent scratch arrays & reusable map buckets — cleared via .length=0 each frame
// instead of allocating fresh arrays/Maps per 60 FPS tick.
const _scratch = {
  grass: [] as EntityState[],
  grain: [] as EntityState[],
  berry: [] as EntityState[],
  herb: [] as EntityState[],
  mushroom: [] as EntityState[],
  poison: [] as EntityState[],
  cultivated: [] as EntityState[],
  corpses: [] as EntityState[],
  houses: [] as EntityState[],
  women: [] as EntityState[],
  polygonsByCaste: new Map<string, EntityState[]>(),
  crestsByColor: new Map<string, EntityState[]>(),
  womenGroups: new Map<string, GroupBatch>(),
  polyGroups: new Map<string, GroupBatch>(),
  sleeping: [] as EntityState[],
  hungry: [] as EntityState[],
  starving: [] as EntityState[],
  infected: [] as EntityState[],
  chilled: [] as EntityState[],
  torpid: [] as EntityState[],
  glyphs: [] as EntityState[],
  visible: [] as EntityState[],
}

export function drawBatchedEntities(
  ctx: CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D,
  entities: EntityState[],
  visible: (x: number, y: number, r?: number) => boolean,
  camScale: number,
  selectedId: number | null,
  tick = 0,
  lensMode: LensMode = 'classic',
): EntityState[] {
  const isZoomedOut = camScale < 4.0
  const isVeryZoomedOut = camScale < 2.2
  const isDense = entities.length > 300

  const grassPlants = _scratch.grass; grassPlants.length = 0
  const grainPlants = _scratch.grain; grainPlants.length = 0
  const berryPlants = _scratch.berry; berryPlants.length = 0
  const herbPlants = _scratch.herb; herbPlants.length = 0
  const mushroomPlants = _scratch.mushroom; mushroomPlants.length = 0
  const poisonPlants = _scratch.poison; poisonPlants.length = 0
  const cultivatedPlants = _scratch.cultivated; cultivatedPlants.length = 0
  const corpses = _scratch.corpses; corpses.length = 0
  const houses = _scratch.houses; houses.length = 0
  const women = _scratch.women; women.length = 0
  const polygonsByCaste = _scratch.polygonsByCaste
  for (const list of polygonsByCaste.values()) list.length = 0
  const crestsByColor = _scratch.crestsByColor
  for (const list of crestsByColor.values()) list.length = 0
  const womenGroups = _scratch.womenGroups
  for (const g of womenGroups.values()) g.list.length = 0
  const polyGroups = _scratch.polyGroups
  for (const g of polyGroups.values()) g.list.length = 0
  const sleepingCreatures = _scratch.sleeping; sleepingCreatures.length = 0
  const hungryCreatures = _scratch.hungry; hungryCreatures.length = 0
  const starvingCreatures = _scratch.starving; starvingCreatures.length = 0
  const infectedCreatures = _scratch.infected; infectedCreatures.length = 0
  const chilledCreatures = _scratch.chilled; chilledCreatures.length = 0
  const torpidCreatures = _scratch.torpid; torpidCreatures.length = 0
  const glyphCreatures = _scratch.glyphs; glyphCreatures.length = 0
  const visibleCreatures = _scratch.visible; visibleCreatures.length = 0

  for (const e of entities) {
    const rad = (e as any).radius ?? (e as any).size ?? 1.5
    if (!visible(e.x, e.y, rad)) continue

    if (e.kind === 'food') {
      if ((e as any).cultivated) {
        cultivatedPlants.push(e) // §AM sown fields read as wheat-gold
        continue
      }
      const v = e.variant ?? 'grass'
      if (v === 'grain') grainPlants.push(e)
      else if (v === 'berry') berryPlants.push(e)
      else if (v === 'medicinal_herb') herbPlants.push(e)
      else if (v === 'mushroom') mushroomPlants.push(e)
      else if (v === 'poisonous') poisonPlants.push(e)
      else grassPlants.push(e)
      continue
    }


    if (e.kind === 'corpse') {
      corpses.push(e)
      continue
    }

    if (e.kind === 'house') {
      houses.push(e)
      continue
    }

    visibleCreatures.push(e)
    if (e.shape === 'line') {
      women.push(e)
    } else {
      const caste = e.caste || 'Soldier'
      let list = polygonsByCaste.get(caste)
      if (!list) {
        list = []
        polygonsByCaste.set(caste, list)
      }
      list.push(e)
    }

    if (e.clan_color) {
      let list = crestsByColor.get(e.clan_color)
      if (!list) {
        list = []
        crestsByColor.set(e.clan_color, list)
      }
      list.push(e)
    }

    if (e.sleeping && camScale >= 4.5) sleepingCreatures.push(e)
    if (camScale >= 1.8) {
      if (e.infected) infectedCreatures.push(e)
      if (e.status === 'starving') starvingCreatures.push(e)
      else if (e.status === 'hungry') hungryCreatures.push(e)
      if ((e.chill ?? 0) >= 12) chilledCreatures.push(e)
      if (e.torpid) torpidCreatures.push(e)
    }    if (e.glyph && ((camScale >= 6.0 && !isDense) || selectedId === e.id)) glyphCreatures.push(e)
  }

  // Draw Houses
  for (const h of houses) {
    if (h.is_ruin) {
      const size = (h.size ?? 8) * 0.7
      ctx.strokeStyle = 'rgba(110,118,129,0.25)'
      ctx.lineWidth = 0.2
      ctx.setLineDash([0.8, 0.6])
      ctx.strokeRect(h.x - size / 2, h.y - size / 2, size, size)
      ctx.setLineDash([])
      ctx.fillStyle = 'rgba(110,118,129,0.08)'
      ctx.fillRect(h.x - size / 2, h.y - size / 2, size, size)
    } else {
      const size = h.size ?? 8
      const segs = houseWallSegments(
        h.x,
        h.y,
        size,
        h.door_side ?? 'south',
        h.door_width ?? 3,
        h.door_offset ?? 0,
      )
      ctx.strokeStyle = h.clan_color ?? '#8b949e'
      ctx.lineWidth = 0.35
      ctx.beginPath()
      for (const [ax, ay, bx, by] of segs) {
        ctx.moveTo(ax, ay)
        ctx.lineTo(bx, by)
      }
      ctx.stroke()
      // §AQ PH-6 & §BL-4: material reads at a glance using hoisted HOUSE_MAT_TINT
      const tint = h.material ? HOUSE_MAT_TINT[h.material] : undefined
      if (tint) {
        ctx.fillStyle = tint
        ctx.fillRect(h.x - size / 2, h.y - size / 2, size, size)
      }
      if (h.hp_frac != null && h.hp_frac < 0.7) {
        ctx.strokeStyle = `rgba(20,24,28,${0.5 * (1 - h.hp_frac)})`
        ctx.lineWidth = 0.2
        ctx.setLineDash([1.2, 0.9])
        ctx.strokeRect(h.x - size / 2, h.y - size / 2, size, size)
        ctx.setLineDash([])
      }
      if (h.clan_color) {
        ctx.fillStyle = h.clan_color
        ctx.globalAlpha = 0.18
        ctx.fillRect(h.x - size / 2, h.y - size / 2, size, 1.2)
        ctx.globalAlpha = 1
      }
      // §AT-3: brief takeover flash — an expanding ring fades over ~90 ticks
      const tAge = h.takeover_age
      if (tAge !== null && tAge !== undefined && tAge >= 0 && tAge < 90) {
        const fade = 1 - tAge / 90
        ctx.strokeStyle = h.clan_color ?? '#f85149'
        ctx.globalAlpha = 0.7 * fade
        ctx.lineWidth = 0.25 + 0.5 * fade
        ctx.beginPath()
        ctx.arc(h.x, h.y, size / 2 + 1.5 + tAge * 0.06, 0, TAU)
        ctx.stroke()
        ctx.globalAlpha = 1
      }
      // §AQ PH-1: a lit hearth — warm glow and a flame dot on the floor
      if (h.hearth_lit) {
        const flick = 0.85 + 0.3 * Math.sin(tick * 0.7 + h.x)
        ctx.fillStyle = 'rgba(255,158,60,0.16)'
        ctx.beginPath()
        ctx.arc(h.x, h.y, size * 0.42 * flick, 0, TAU)
        ctx.fill()
        ctx.fillStyle = '#ffa657'
        ctx.beginPath()
        ctx.arc(h.x, h.y, 0.9 * flick, 0, TAU)
        ctx.fill()
        ctx.fillStyle = '#ffe08a'
        ctx.beginPath()
        ctx.arc(h.x, h.y - 0.2, 0.45, 0, TAU)
        ctx.fill()
      }
    }
  }

  // Draw Plants
  const drawPlantBatch = (plants: EntityState[], fillStyle: string) => {
    if (plants.length === 0) return
    ctx.fillStyle = fillStyle
    ctx.beginPath()
    for (const f of plants) {
      const r = f.withering
        ? (0.35 + 0.55 * (f.growth ?? 0.15)) * 0.8
        : 0.35 + 0.55 * (f.growth ?? 0.15)
      ctx.moveTo(f.x + r, f.y)
      ctx.arc(f.x, f.y, r, 0, TAU)
    }
    ctx.fill()
  }

  drawPlantBatch(grassPlants, '#3fb950')
  drawPlantBatch(grainPlants, '#e3b341')
  drawPlantBatch(berryPlants, '#f85149')
  drawPlantBatch(herbPlants, '#2ea043')
  drawPlantBatch(mushroomPlants, '#a67c52')
  drawPlantBatch(poisonPlants, '#8957e5')
  drawPlantBatch(cultivatedPlants, '#d8c341')


  if (poisonPlants.length > 0) {
    ctx.globalAlpha = 0.25
    ctx.strokeStyle = '#8957e5'
    ctx.lineWidth = 0.3
    ctx.beginPath()
    for (const f of poisonPlants) {
      const r = (0.35 + 0.55 * (f.growth ?? 0.15)) * 1.4
      ctx.moveTo(f.x + r, f.y)
      ctx.arc(f.x, f.y, r, 0, TAU)
    }
    ctx.stroke()
    ctx.globalAlpha = 1
  }

  // Draw Corpses
  if (corpses.length > 0) {
    ctx.strokeStyle = '#5a6572'
    ctx.globalAlpha = 0.8
    ctx.lineWidth = 0.3
    ctx.beginPath()
    for (const c of corpses) {
      ctx.moveTo(c.x - 1.1, c.y - 1.1)
      ctx.lineTo(c.x + 1.1, c.y + 1.1)
      ctx.moveTo(c.x - 1.1, c.y + 1.1)
      ctx.lineTo(c.x + 1.1, c.y - 1.1)
      ctx.moveTo(c.x + 0.5, c.y)
      ctx.arc(c.x, c.y, 0.5, 0, TAU)
    }
    ctx.stroke()
    ctx.globalAlpha = 1
  }

  // §BG & §BK Draw Women (Lines) — variable thickness & taper (BG-3) + BK-3 dynamic twitch + BK-9 lens
  if (women.length > 0) {
    for (const w of women) {
      const style = getCreatureLensStyle(w, lensMode)
      let g = womenGroups.get(style.color)
      if (!g) {
        g = { list: [], fillAlpha: style.fillAlpha, strokeAlpha: style.strokeAlpha }
        womenGroups.set(style.color, g)
      } else {
        g.fillAlpha = style.fillAlpha
        g.strokeAlpha = style.strokeAlpha
      }
      g.list.push(w)
    }

    for (const [color, group] of womenGroups.entries()) {
      if (group.list.length === 0) continue
      ctx.fillStyle = color
      ctx.strokeStyle = color
      ctx.lineWidth = 0.35
      ctx.beginPath()
      for (const w of group.list) {
        const stage = w.stage ?? 'adult'
        const sizeF = stage === 'infant' ? 0.55 : stage === 'juvenile' ? 0.8 : 1.0
        const r = (w.radius ?? 0.9) * sizeF * (w.scale_jitter ?? 1)
        const len = Math.max(1.8, r * 2.4)
        const ang = w.angle + (w.angle_jitter ?? 0)
        const irr = (w as any).irregularity ?? 0
        const mt = (w as any).morph_traits as number[] | undefined
        const perimFactor = mt && mt[1] ? Math.max(0.7, Math.min(1.9, mt[1] / 5.657)) : 1
        let wMid = Math.max(0.16, r * 0.30 * perimFactor * (0.85 + irr * 0.9))
        // BK-3 Dynamic chaotic twitch for irregular women
        if (irr > 0.04 && tick > 0) {
          wMid *= (1 + Math.sin(tick * 0.28 + (w.id % 13)) * irr * 0.22)
        }
        // needle diamond: front tip, midTop, back tip, midBottom
        const ca = Math.cos(ang), sa = Math.sin(ang)
        const paX = -sa, paY = ca // perp
        const frontX = w.x + ca * len, frontY = w.y + sa * len
        const backX = w.x - ca * len * 0.92, backY = w.y - sa * len * 0.92
        const midTopX = w.x + paX * wMid, midTopY = w.y + paY * wMid
        const midBotX = w.x - paX * wMid, midBotY = w.y - paY * wMid
        ctx.moveTo(frontX, frontY)
        ctx.lineTo(midTopX, midTopY)
        ctx.lineTo(backX, backY)
        ctx.lineTo(midBotX, midBotY)
        ctx.closePath()
      }
      ctx.globalAlpha = group.fillAlpha
      ctx.fill()
      ctx.globalAlpha = group.strokeAlpha
      ctx.stroke()
      ctx.globalAlpha = 1
    }
  }

  // §BG & §BK Draw Polygons — mutated geometry (BG-1, BG-2, BG-4) + BK-9 lens
  const useCircleLOD = isVeryZoomedOut || (isZoomedOut && isDense)
  for (const list of polygonsByCaste.values()) {
    if (list.length === 0) continue
    for (const c of list) {
      const style = getCreatureLensStyle(c, lensMode)
      let g = polyGroups.get(style.color)
      if (!g) {
        g = { list: [], fillAlpha: style.fillAlpha, strokeAlpha: style.strokeAlpha }
        polyGroups.set(style.color, g)
      } else {
        g.fillAlpha = style.fillAlpha
        g.strokeAlpha = style.strokeAlpha
      }
      g.list.push(c)
    }
  }

  for (const [color, group] of polyGroups.entries()) {
    if (group.list.length === 0) continue
    ctx.beginPath()
    for (const c of group.list) {
      const stage = c.stage ?? 'adult'
      const sizeF = stage === 'infant' ? 0.55 : stage === 'juvenile' ? 0.8 : 1.0
      const r = (c.radius ?? 1.2) * sizeF * (c.scale_jitter ?? 1)
      const sidesRaw = (c as any).morph_k ?? c.sides ?? 4
      const sides = Math.max(3, Math.min(24, sidesRaw))
      const ang = c.angle + (c.angle_jitter ?? 0)
      const irr = (c as any).irregularity ?? 0
      const isoAngle = (c as any).iso_angle
      const isSoldierRazor = c.caste === 'Soldier' && sides === 3 && typeof isoAngle === 'number' && isoAngle < 59.9
      if (isSoldierRazor) {
        bgTraceSoldierRazor(ctx, c.x, c.y, r, ang, isoAngle)
        continue
      }
      if (useCircleLOD || sides >= PRIEST_SIDES) {
        if (irr > 0.08 && sides >= PRIEST_SIDES) {
          bgTraceMutatedPath(ctx, c.x, c.y, sides, r, ang, Math.min(0.3, irr), c.id, tick)
        } else {
          ctx.moveTo(c.x + r, c.y)
          ctx.arc(c.x, c.y, r, 0, TAU)
        }
      } else {
        if (irr > 0.02) {
          bgTraceMutatedPath(ctx, c.x, c.y, sides, r, ang, irr, c.id, tick)
        } else {
          const startAng = ang - Math.PI / 2
          for (let i = 0; i < sides; i++) {
            const a = startAng + (i / sides) * TAU
            const px = c.x + Math.cos(a) * r
            const py = c.y + Math.sin(a) * r
            if (i === 0) ctx.moveTo(px, py)
            else ctx.lineTo(px, py)
          }
          ctx.closePath()
        }
      }
    }
    ctx.globalAlpha = group.fillAlpha
    ctx.fillStyle = color
    ctx.fill()
    ctx.globalAlpha = group.strokeAlpha
    ctx.strokeStyle = color
    ctx.lineWidth = 0.3
    ctx.stroke()
    ctx.globalAlpha = 1.0
  }
  // §BG & §BK Visual phenotypes overlays — BG-5 Blade Glint, BG-6 Armor, BG-7 Speciation, BG-8 Elder nucleus, BK-1 Genesis Spark, BK-2 Lineage Halos & Corona, BK-3 Aberrant Aura
  // §BL-2 LOD Gating: skip expensive sub-pixel phenotypic decorations when zoomed out unless selected
  const isPhenotypeZoomedOut = camScale < 3.2
  for (const c of visibleCreatures) {
    if (c.kind !== 'creature') continue
    if (isPhenotypeZoomedOut && c.id !== selectedId) continue
    const isLine = c.shape === 'line'
    const mt = (c as any).morph_traits as number[] | undefined
    const irr = (c as any).irregularity ?? 0
    const stage = (c as any).stage ?? 'adult'
    const gen = (c as any).generation ?? 0
    const sidesRaw = (c as any).morph_k ?? c.sides ?? 4
    const sides = Math.max(3, Math.min(24, sidesRaw))
    const sizeF = stage === 'infant' ? 0.55 : stage === 'juvenile' ? 0.8 : 1
    const r = (c.radius ?? (isLine ? 0.9 : 1.2)) * sizeF * ((c as any).scale_jitter ?? 1)
    const len = isLine ? Math.max(1.8, r * 2.4) : 0
    const ang = c.angle + ((c as any).angle_jitter ?? 0)
    const perimFactor = isLine && mt && mt[1] ? Math.max(0.7, Math.min(1.9, mt[1] / 5.657)) : 1
    let wMid = isLine ? Math.max(0.16, r * 0.30 * perimFactor * (0.85 + irr * 0.9)) : 0
    if (isLine && irr > 0.04 && tick > 0) {
      wMid *= (1 + Math.sin(tick * 0.28 + (c.id % 13)) * irr * 0.22)
    }
    const lensStyle = getCreatureLensStyle(c, lensMode)
    const color = lensStyle.color

    if (!isLine) {
      // parse traits
      const area = mt && mt.length > 0 ? mt[0] : 2.0
      const izz = mt && mt.length > 2 ? mt[2] : 0.3
      const thetaMin = mt && mt.length > 3 ? mt[3] : 2.0
      const dmult = mt && mt.length > 5 ? mt[5] : Math.max(0, (Math.cos(thetaMin) - 0.5)/0.5)

      // BG-6 Heavy inertia armor — double perimeter + darker fill when high Izz/area
      if ((izz > 0.65 || area > 3.2) && sides < PRIEST_SIDES) {
        ctx.globalAlpha = 0.18
        ctx.fillStyle = color
        ctx.beginPath()
        if ((c.caste === 'Soldier' && sides===3 && typeof (c as any).iso_angle==='number' && (c as any).iso_angle < 59.9)) {
          bgTraceSoldierRazor(ctx, c.x, c.y, r*0.88, ang, (c as any).iso_angle)
        } else if (irr > 0.02) {
          bgTraceMutatedPath(ctx, c.x, c.y, sides, r*0.88, ang, irr, c.id, tick)
        } else {
          const sa = ang - Math.PI/2
          for(let i=0;i<sides;i++){ const a=sa+(i/sides)*TAU; const px=c.x+Math.cos(a)*r*0.88, py=c.y+Math.sin(a)*r*0.88; if(i===0) ctx.moveTo(px,py); else ctx.lineTo(px,py);} ctx.closePath()
        }
        ctx.fill()
        ctx.globalAlpha = 0.55
        ctx.strokeStyle = color
        ctx.lineWidth = 0.55
        ctx.stroke()
        ctx.globalAlpha = 1
      }
      // BG-5 & §BL-4 Blade glint — neon on sharpest vertex scaled by Dmult (zero-allocation)
      if (dmult > 0.18) {
        let gx = c.x, gy = c.y
        let found = false
        if (c.caste === 'Soldier' && sides===3 && typeof (c as any).iso_angle==='number' && (c as any).iso_angle < 59.9) {
          const tip = bgSoldierRazorApex(c.x, c.y, r, ang, (c as any).iso_angle)
          gx = tip[0]; gy = tip[1]; found = true
        } else if (irr <= 0.02) {
          // Regular polygon: apex vertex is at ang - PI/2
          gx = c.x + Math.cos(ang - Math.PI / 2) * r
          gy = c.y + Math.sin(ang - Math.PI / 2) * r
          found = true
        } else {
          // compute polygon points and find sharpest by interior angle
          const pts = bgMutatedPointsScratch(c.x, c.y, sides, r, ang, irr, c.id, tick)
          let best = 999, bx = pts[0][0], by = pts[0][1]
          for (let i = 0; i < sides; i++) {
            const im1 = (i - 1 + sides) % sides, ip1 = (i + 1) % sides
            const ux = pts[im1][0] - pts[i][0], uy = pts[im1][1] - pts[i][1]
            const vx = pts[ip1][0] - pts[i][0], vy = pts[ip1][1] - pts[i][1]
            const nu = Math.hypot(ux, uy), nv = Math.hypot(vx, vy)
            if (nu < 1e-6 || nv < 1e-6) continue
            const cosv = (ux * vx + uy * vy) / (nu * nv)
            const av = Math.acos(Math.max(-1, Math.min(1, cosv)))
            if (av < best) { best = av; bx = pts[i][0]; by = pts[i][1]; }
          }
          gx = bx; gy = by; found = true
        }
        if (found) {
          const glintAlpha = Math.min(0.95, 0.35 + dmult * 0.75)
          const glintR = 0.35 + dmult * 0.7
          ctx.globalAlpha = glintAlpha
          ctx.fillStyle = '#ffe08a'
          ctx.beginPath()
          ctx.arc(gx, gy, glintR, 0, TAU)
          ctx.fill()
          ctx.globalAlpha = glintAlpha * 0.5
          ctx.strokeStyle = '#ffffff'
          ctx.lineWidth = 0.25
          ctx.beginPath()
          ctx.moveTo(gx - 0.6, gy)
          ctx.lineTo(gx + 0.6, gy)
          ctx.moveTo(gx, gy - 0.6)
          ctx.lineTo(gx, gy + 0.6)
          ctx.stroke()
          ctx.globalAlpha = 1
        }
      }
      // BG-7 Speciation chromatic aberration — iridescent dual-tone when divergent
      const genLambdaProxy = gen > 40 ? Math.max(0, Math.min(1, 1 - (gen - 15)/250)) : 1
      const specIntensity = Math.max(irr*1.8, (1-genLambdaProxy))* (sides >=7 || irr>0.25 ? 1 : 0.5)
      if (specIntensity > 0.42) {
        ctx.globalAlpha = 0.42 * Math.min(1, specIntensity)
        ctx.strokeStyle = specIntensity > 0.7 ? '#ff7b72' : '#d2a8ff'
        ctx.lineWidth = 0.22
        ctx.beginPath()
        if (irr > 0.02) {
          bgTraceMutatedPath(ctx, c.x+0.22, c.y+0.13, sides, r, ang, irr, c.id, tick)
        } else {
          const sa = ang - Math.PI/2
          for(let i=0;i<sides;i++){ const a=sa+(i/sides)*TAU; const px=c.x+0.22+Math.cos(a)*r, py=c.y+0.13+Math.sin(a)*r; if(i===0) ctx.moveTo(px,py); else ctx.lineTo(px,py);} ctx.closePath()
        }
        ctx.stroke()
        ctx.strokeStyle = '#79c0ff'
        ctx.globalAlpha = 0.32 * Math.min(1, specIntensity)
        ctx.beginPath()
        if (irr > 0.02) {
          bgTraceMutatedPath(ctx, c.x-0.18, c.y-0.12, sides, r, ang, irr, c.id, tick)
        } else {
          const sa = ang - Math.PI/2
          for(let i=0;i<sides;i++){ const a=sa+(i/sides)*TAU; const px=c.x-0.18+Math.cos(a)*r, py=c.y-0.12+Math.sin(a)*r; if(i===0) ctx.moveTo(px,py); else ctx.lineTo(px,py);} ctx.closePath()
        }
        ctx.stroke()
        ctx.globalAlpha = 1
      }
    }

    // §BK-3 Bioluminescent Aberrant Aura for radical mutants (irr > 0.18)
    if (irr > 0.18) {
      const auraPulse = 1 + Math.sin(tick * 0.35 + (c.id % 19)) * 0.08
      const auraR = r * 1.18 * auraPulse
      const auraColor = irr > 0.28 ? '#f43f5e' : '#a855f7'
      ctx.beginPath()
      if (isLine) {
        const ca = Math.cos(ang), sa = Math.sin(ang)
        const paX = -sa, paY = ca
        const aLen = len * 1.14 * auraPulse
        const aMid = wMid * 1.45 * auraPulse
        ctx.moveTo(c.x + ca * aLen, c.y + sa * aLen)
        ctx.lineTo(c.x + paX * aMid, c.y + paY * aMid)
        ctx.lineTo(c.x - ca * aLen * 0.94, c.y - sa * aLen * 0.94)
        ctx.lineTo(c.x - paX * aMid, c.y - paY * aMid)
        ctx.closePath()
      } else if (c.caste === 'Soldier' && sides === 3 && typeof (c as any).iso_angle === 'number' && (c as any).iso_angle < 59.9) {
        bgTraceSoldierRazor(ctx, c.x, c.y, auraR, ang, (c as any).iso_angle)
      } else if (sides >= PRIEST_SIDES) {
        ctx.arc(c.x, c.y, auraR, 0, TAU)
      } else {
        bgTraceMutatedPath(ctx, c.x, c.y, sides, auraR, ang, irr, c.id, tick)
      }
      ctx.strokeStyle = auraColor
      ctx.lineWidth = 0.35
      ctx.globalAlpha = Math.min(0.65, (irr - 0.15) * 2.8)
      ctx.stroke()
      ctx.globalAlpha = 1
    }

    // §BK-2 Concentric Lineage Halos & Celestial Ancestral Corona
    // Gen 10–24: inner lineage halo
    if (gen >= 10 && !isVeryZoomedOut) {
      const haloR = r * 0.62
      ctx.beginPath()
      if (isLine) {
        const ca = Math.cos(ang), sa = Math.sin(ang)
        const paX = -sa, paY = ca
        const hLen = len * 0.6
        const hMid = Math.max(0.12, wMid * 0.6)
        ctx.moveTo(c.x + ca * hLen, c.y + sa * hLen)
        ctx.lineTo(c.x + paX * hMid, c.y + paY * hMid)
        ctx.lineTo(c.x - ca * hLen * 0.9, c.y - sa * hLen * 0.9)
        ctx.lineTo(c.x - paX * hMid, c.y - paY * hMid)
        ctx.closePath()
      } else if (c.caste === 'Soldier' && sides === 3 && typeof (c as any).iso_angle === 'number' && (c as any).iso_angle < 59.9) {
        bgTraceSoldierRazor(ctx, c.x, c.y, haloR, ang, (c as any).iso_angle)
      } else if (sides >= PRIEST_SIDES) {
        ctx.arc(c.x, c.y, haloR, 0, TAU)
      } else if (irr > 0.02) {
        bgTraceMutatedPath(ctx, c.x, c.y, sides, haloR, ang, irr, c.id, tick)
      } else {
        const sa = ang - Math.PI / 2
        for (let i = 0; i < sides; i++) {
          const a = sa + (i / sides) * TAU
          const px = c.x + Math.cos(a) * haloR, py = c.y + Math.sin(a) * haloR
          if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py)
        }
        ctx.closePath()
      }
      ctx.strokeStyle = '#e2e8f0'
      ctx.lineWidth = 0.22
      ctx.globalAlpha = 0.45
      ctx.stroke()
      ctx.globalAlpha = 1
    }

    // Gen 25+: double concentric dynasty core ring
    if (gen >= 25 && !isVeryZoomedOut) {
      ctx.beginPath()
      ctx.arc(c.x, c.y, Math.max(0.35, r * 0.36), 0, TAU)
      ctx.strokeStyle = '#facc15'
      ctx.lineWidth = 0.28
      ctx.globalAlpha = 0.65
      ctx.stroke()
      ctx.globalAlpha = 1
    }

    // §BK-2 Celestial Ancestral Coronas (scaling dynamically across millennia up to Gen 2000+)
    if (gen >= 50) {
      let rayCount = 8
      let coronaBase = r * 1.08
      let coronaOuterLong = r * 1.40
      let coronaOuterShort = r * 1.22
      let coronaColor = '#fde047'
      let spinSpeed = 0.015
      let strokeW = 0.35
      let alpha = 0.80

      if (gen >= 2000) {
        // Gen 2000+: Cosmic Starlight Corona (24 radiating coronal rays + orbiting diamond starlight flares)
        rayCount = 24
        coronaBase = r * 1.10
        coronaOuterLong = r * 1.85
        coronaOuterShort = r * 1.38
        coronaColor = '#fef08a'
        spinSpeed = 0.008
        strokeW = 0.45
        alpha = 0.95
      } else if (gen >= 1000) {
        // Gen 1000-1999: Solar Eon Corona (20 rays)
        rayCount = 20
        coronaBase = r * 1.10
        coronaOuterLong = r * 1.70
        coronaOuterShort = r * 1.34
        coronaColor = '#facc15'
        spinSpeed = 0.010
        strokeW = 0.40
        alpha = 0.90
      } else if (gen >= 500) {
        // Gen 500-999: Radiant Astral Corona (16 rays)
        rayCount = 16
        coronaBase = r * 1.08
        coronaOuterLong = r * 1.55
        coronaOuterShort = r * 1.28
        coronaColor = '#f59e0b'
        spinSpeed = 0.012
        strokeW = 0.38
        alpha = 0.85
      } else if (gen >= 200) {
        // Gen 200-499: Sovereign Sunburst Corona (12 rays)
        rayCount = 12
        coronaBase = r * 1.08
        coronaOuterLong = r * 1.48
        coronaOuterShort = r * 1.25
        coronaColor = '#fbbf24'
        spinSpeed = 0.014
        strokeW = 0.35
        alpha = 0.80
      }

      const coronaSpin = tick * spinSpeed
      ctx.beginPath()
      for (let k = 0; k < rayCount; k++) {
        const a = ang + coronaSpin + (k / rayCount) * TAU
        const ca = Math.cos(a), sa = Math.sin(a)
        const isTier1 = k % 4 === 0
        const isTier2 = k % 2 === 0
        const outerR = isTier1 ? coronaOuterLong : isTier2 ? (coronaOuterLong + coronaOuterShort) * 0.5 : coronaOuterShort
        ctx.moveTo(c.x + ca * coronaBase, c.y + sa * coronaBase)
        ctx.lineTo(c.x + ca * outerR, c.y + sa * outerR)
      }
      ctx.strokeStyle = coronaColor
      ctx.lineWidth = strokeW
      ctx.globalAlpha = alpha
      ctx.stroke()

      // Gen 500+: Pulsing outer orbital halo ring connecting the rays
      if (gen >= 500 && !isVeryZoomedOut) {
        ctx.beginPath()
        const ringR = (coronaBase + coronaOuterShort) * 0.5
        ctx.arc(c.x, c.y, ringR, 0, TAU)
        ctx.strokeStyle = coronaColor
        ctx.lineWidth = 0.22
        ctx.setLineDash([0.6, 0.6])
        ctx.globalAlpha = alpha * 0.5
        ctx.stroke()
        ctx.setLineDash([])
      }

      // Gen 2000+: Diamond starlight flares at cardinal & intercardinal tips
      if (gen >= 2000 && !isVeryZoomedOut) {
        ctx.globalAlpha = 0.95
        ctx.fillStyle = '#ffffff'
        for (let k = 0; k < 8; k++) {
          const a = ang + coronaSpin + (k / 8) * TAU
          const px = c.x + Math.cos(a) * coronaOuterLong
          const py = c.y + Math.sin(a) * coronaOuterLong
          ctx.beginPath()
          ctx.arc(px, py, 0.32, 0, TAU)
          ctx.fill()
        }
      }

      ctx.globalAlpha = 1
    }

    // §BK-1 Genesis Spark for Primordials (Gen 0–2)
    if (gen <= 2) {
      const starR = Math.max(0.42, r * 0.26) * (gen === 0 ? 1.25 : gen === 1 ? 1.1 : 0.95)
      const pulse = 1 + Math.sin(tick * 0.25 + (c.id % 11)) * 0.15
      const sr = starR * pulse
      // Soft outer glow
      ctx.beginPath()
      ctx.arc(c.x, c.y, sr * 1.8, 0, TAU)
      ctx.fillStyle = gen === 0 ? 'rgba(56, 189, 248, 0.35)' : 'rgba(56, 189, 248, 0.20)'
      ctx.fill()
      // 4-point star pip
      ctx.beginPath()
      ctx.moveTo(c.x, c.y - sr)
      ctx.lineTo(c.x + sr * 0.28, c.y - sr * 0.28)
      ctx.lineTo(c.x + sr, c.y)
      ctx.lineTo(c.x + sr * 0.28, c.y + sr * 0.28)
      ctx.lineTo(c.x, c.y + sr)
      ctx.lineTo(c.x - sr * 0.28, c.y + sr * 0.28)
      ctx.lineTo(c.x - sr, c.y)
      ctx.lineTo(c.x - sr * 0.28, c.y - sr * 0.28)
      ctx.closePath()
      ctx.fillStyle = gen === 0 ? '#ffffff' : '#e0f2fe'
      ctx.fill()
      ctx.strokeStyle = '#38bdf8'
      ctx.lineWidth = 0.2
      ctx.stroke()
    }

    // BG-8 Elder lineage nucleus — inscribed core for elders/high gen
    if (stage === 'elder' && gen >= 10 && !isLine) {
      const innerR = r * 0.38
      const glyph = (c as any).glyph
      ctx.globalAlpha = 0.28
      ctx.fillStyle = color
      ctx.beginPath()
      if (sides >= PRIEST_SIDES) {
        ctx.arc(c.x, c.y, innerR, 0, TAU)
      } else {
        const sa = ang - Math.PI/2
        for(let i=0;i<sides;i++){ const a=sa+(i/sides)*TAU; const px=c.x+Math.cos(a)*innerR, py=c.y+Math.sin(a)*innerR; if(i===0) ctx.moveTo(px,py); else ctx.lineTo(px,py);} ctx.closePath()
      }
      ctx.fill()
      ctx.globalAlpha = 0.55
      ctx.strokeStyle = '#e6edf3'
      ctx.lineWidth = 0.2
      ctx.stroke()
      if (glyph && r > 0.9) {
        ctx.globalAlpha = 0.9
        ctx.fillStyle = '#e6edf3'
        ctx.font = `${innerR*0.9}px ui-monospace, monospace`
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        ctx.fillText(glyph, c.x, c.y + 0.08)
      }
      ctx.globalAlpha = 1
    }

    // §BK-4 Ancestral Crystalline Core Patina (gen >= 15)
    if (gen >= 15 && !isVeryZoomedOut) {
      const coreR = Math.max(0.4, r * 0.42)
      ctx.beginPath()
      if (sides >= PRIEST_SIDES || isLine) {
        ctx.arc(c.x, c.y, coreR, 0, TAU)
      } else {
        const sa = ang - Math.PI / 2
        for (let i = 0; i < sides; i++) {
          const a = sa + (i / sides) * TAU
          const px = c.x + Math.cos(a) * coreR, py = c.y + Math.sin(a) * coreR
          if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py)
        }
        ctx.closePath()
      }
      ctx.fillStyle = gen >= 2000 ? 'rgba(254, 240, 138, 0.70)' : gen >= 1000 ? 'rgba(250, 204, 21, 0.58)' : gen >= 500 ? 'rgba(245, 158, 11, 0.48)' : gen >= 200 ? 'rgba(236, 72, 153, 0.42)' : gen >= 50 ? 'rgba(254, 240, 138, 0.38)' : gen >= 25 ? 'rgba(245, 158, 11, 0.28)' : 'rgba(148, 163, 184, 0.20)'
      ctx.fill()
      ctx.strokeStyle = gen >= 2000 ? '#ffffff' : gen >= 1000 ? '#fef08a' : gen >= 500 ? '#facc15' : gen >= 200 ? '#ec4899' : gen >= 50 ? '#fde047' : gen >= 25 ? '#fbbf24' : '#94a3b8'
      ctx.lineWidth = gen >= 500 ? 0.35 : 0.22
      ctx.stroke()
    }

    // §BK-5 Soldier Razor Piercing Glint & Metallic Apex Accent (θ < 30°)
    if (c.caste === 'Soldier' && sides === 3 && typeof (c as any).iso_angle === 'number' && (c as any).iso_angle < 30) {
      const [tipX, tipY] = bgSoldierRazorApex(c.x, c.y, r, ang, (c as any).iso_angle)
      const ca = Math.cos(ang), sa = Math.sin(ang)
      ctx.beginPath()
      ctx.moveTo(tipX - ca * 0.7, tipY - sa * 0.7)
      ctx.lineTo(tipX + ca * 0.5, tipY + sa * 0.5)
      ctx.strokeStyle = '#ef4444'
      ctx.lineWidth = 0.35
      ctx.stroke()
      ctx.beginPath()
      ctx.arc(tipX, tipY, 0.42, 0, TAU)
      ctx.fillStyle = '#ffffff'
      ctx.fill()
    }

    // §BK-6 Battle Veteran Wound Scars (scars > 0)
    const scarsCount = (c as any).scars as number | undefined
    if (scarsCount && scarsCount > 0 && !isVeryZoomedOut) {
      const nScars = Math.min(4, scarsCount)
      ctx.lineWidth = 0.3
      for (let k = 0; k < nScars; k++) {
        const sAng = ang + (k * 1.25) + 0.6
        const sx = c.x + Math.cos(sAng) * r * 0.65
        const sy = c.y + Math.sin(sAng) * r * 0.65
        const pLen = 0.55
        const px = -Math.sin(sAng) * pLen
        const py = Math.cos(sAng) * pLen
        // Dark slash mark
        ctx.beginPath()
        ctx.moveTo(sx - px, sy - py)
        ctx.lineTo(sx + px, sy + py)
        ctx.strokeStyle = '#0f172a'
        ctx.stroke()
        // Dried blood red undertone
        ctx.beginPath()
        ctx.moveTo(sx - px * 0.6, sy - py * 0.6)
        ctx.lineTo(sx + px * 0.6, sy + py * 0.6)
        ctx.strokeStyle = '#991b1b'
        ctx.stroke()
      }
    }

    // BH-9 archetype mini-icon above creature when zoomed (nocturnal etc)
    const arch = (c as any).archetype as string | undefined
    if (arch && camScale >= 3.0) {
      const icon = arch==='Apex Hunter'?'⚔' : arch==='Nocturnal Forager'?'🌙' : arch==='Granary Courier'?'🧺' : arch==='Sentry Guard'?'🛡️' : ''
      if (icon) {
        const ax = c.x, ay = c.y - r - 1.8
        ctx.globalAlpha = 0.92
        ctx.fillStyle = '#0d1117'
        ctx.beginPath()
        ctx.roundRect(ax - 1.0, ay - 1.0, 2.0, 1.8, 0.3)
        ctx.fill()
        ctx.globalAlpha = 1
        ctx.font = '1.2px ui-monospace, monospace'
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        ctx.fillText(icon, ax, ay)
      }
    }
  }

  // Draw Crests
  for (const [clanColor, list] of crestsByColor.entries()) {
    if (list.length === 0) continue
    ctx.globalAlpha = 0.85
    ctx.strokeStyle = clanColor
    ctx.lineWidth = 0.18
    ctx.beginPath()
    for (const c of list) {
      const stage = c.stage ?? 'adult'
      const sizeF = stage === 'infant' ? 0.55 : stage === 'juvenile' ? 0.8 : 1.0
      const r = (c.radius ?? 1.2) * sizeF + 0.45
      ctx.moveTo(c.x + r, c.y)
      ctx.arc(c.x, c.y, r, 0, TAU)
    }
    ctx.stroke()
    ctx.globalAlpha = 1
  }

  // Draw Status Rings
  if (starvingCreatures.length > 0) {
    const pulse = 0.35 + 0.45 * Math.sin(performance.now() / 120)
    ctx.globalAlpha = pulse
    ctx.strokeStyle = '#f85149'
    ctx.lineWidth = 0.4
    ctx.beginPath()
    for (const c of starvingCreatures) {
      const r = (c.radius ?? 1.2) + 0.9
      ctx.moveTo(c.x + r, c.y)
      ctx.arc(c.x, c.y, r, 0, TAU)
    }
    ctx.stroke()
    ctx.globalAlpha = 1
  }

  if (hungryCreatures.length > 0) {
    ctx.globalAlpha = 0.65
    ctx.strokeStyle = '#d29922'
    ctx.lineWidth = 0.22
    ctx.beginPath()
    for (const c of hungryCreatures) {
      const r = (c.radius ?? 1.2) + 0.7
      ctx.moveTo(c.x + r, c.y)
      ctx.arc(c.x, c.y, r, 0, TAU)
    }
    ctx.stroke()
    ctx.globalAlpha = 1
  }

  if (infectedCreatures.length > 0) {
    const pulse = 0.4 + 0.3 * Math.sin(performance.now() / 180)
    ctx.globalAlpha = pulse
    ctx.strokeStyle = '#3fb950'
    ctx.lineWidth = 0.45
    ctx.beginPath()
    for (const c of infectedCreatures) {
      const r = (c.radius ?? 1.2) + 1.2
      ctx.moveTo(c.x + r, c.y)
      ctx.arc(c.x, c.y, r, 0, TAU)
    }
    ctx.stroke()
    ctx.globalAlpha = 1
  }

  if (chilledCreatures.length > 0) {
    ctx.globalAlpha = 0.55
    ctx.strokeStyle = '#79c0ff'
    ctx.lineWidth = 0.35
    ctx.beginPath()
    for (const c of chilledCreatures) {
      const r = (c.radius ?? 1.2) + 0.5
      ctx.moveTo(c.x + r, c.y)
      ctx.arc(c.x, c.y, r, 0, TAU)
    }
    ctx.stroke()
    ctx.globalAlpha = 1
  }

  // §AQ PH-7: torpid bodies — a faint frost-blue halo, unconscious where they fell
  if (torpidCreatures.length > 0) {
    ctx.globalAlpha = 0.4
    ctx.strokeStyle = '#a5d8ff'
    ctx.lineWidth = 0.3
    ctx.beginPath()
    for (const c of torpidCreatures) {
      const r = (c.radius ?? 1.2) + 0.9
      ctx.moveTo(c.x + r, c.y)
      ctx.arc(c.x, c.y, r, 0, TAU)
    }
    ctx.stroke()
    ctx.globalAlpha = 1
  }

  // Draw Sleeping Markers
  if (sleepingCreatures.length > 0) {
    ctx.globalAlpha = 0.8
    ctx.fillStyle = '#c9d1d9'
    ctx.font = '1.6px ui-monospace, monospace'
    for (const c of sleepingCreatures) {
      const r = c.radius ?? 1.2
      ctx.fillText('z', c.x + r + 0.4, c.y - r - 0.2)
    }
    ctx.globalAlpha = 1
  }

  // Draw Glyphs
  if (glyphCreatures.length > 0) {
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.font = '1.2px ui-monospace, monospace'
    for (const c of glyphCreatures) {
      const isSel = selectedId === c.id
      ctx.globalAlpha = isSel ? 1 : 0.75
      ctx.fillStyle = isSel ? '#e6edf3' : 'rgba(230,237,243,0.85)'
      if (isSel) {
        ctx.strokeStyle = 'rgba(11,15,20,0.9)'
        ctx.lineWidth = 0.25
        ctx.strokeText(c.glyph!, c.x, c.y + 0.15)
      }
      ctx.fillText(c.glyph!, c.x, c.y + 0.15)
    }
    ctx.globalAlpha = 1
  }

  // Draw Items
  if (!isVeryZoomedOut) {
    for (const c of visibleCreatures) {
      if (!c.equipped_item) continue
      const r = c.radius ?? 1.2
      const ang = c.angle + (c.angle_jitter ?? 0)

      if (c.equipped_item === 'spear') {
        const tipX = c.x + Math.cos(ang) * (r + 1.8)
        const tipY = c.y + Math.sin(ang) * (r + 1.8)
        const baseX = c.x + Math.cos(ang) * (r - 0.4)
        const baseY = c.y + Math.sin(ang) * (r - 0.4)
        ctx.strokeStyle = '#d29922'
        ctx.lineWidth = 0.35
        ctx.beginPath()
        ctx.moveTo(baseX, baseY)
        ctx.lineTo(tipX, tipY)
        ctx.stroke()
        ctx.fillStyle = '#ff7b72'
        ctx.beginPath()
        ctx.arc(tipX, tipY, 0.4, 0, TAU)
        ctx.fill()
      } else if (c.equipped_item === 'crown') {
        ctx.font = '1.7px ui-monospace, monospace'
        ctx.textAlign = 'center'
        ctx.textBaseline = 'bottom'
        ctx.fillText('👑', c.x, c.y - r - 0.3)
      } else if (c.equipped_item === 'basket') {
        const bx = c.x + Math.cos(ang + Math.PI / 2) * (r + 0.6)
        const by = c.y + Math.sin(ang + Math.PI / 2) * (r + 0.6)
        ctx.font = '1.3px ui-monospace, monospace'
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        ctx.fillText('🧺', bx, by)
        if ((c.food_basket ?? 0) > 0) {
          ctx.fillStyle = '#3fb950'
          ctx.beginPath()
          ctx.arc(bx + 0.5, by - 0.5, 0.3, 0, TAU)
          ctx.fill()
        }
      } else if (c.equipped_item === 'herb_poultice') {
        const hx = c.x + Math.cos(ang - Math.PI / 2) * (r + 0.6)
        const hy = c.y + Math.sin(ang - Math.PI / 2) * (r + 0.6)
        ctx.font = '1.3px ui-monospace, monospace'
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        ctx.fillText('🌿', hx, hy)
      }
    }
  }

  // Draw Thought Emotes
  const nowTime = performance.now() / 1000
  for (const c of visibleCreatures) {
    if (!c.emote && !c.sleeping) continue
    const emoteKey = c.emote ?? (c.sleeping ? 'sleep' : null)
    if (!emoteKey) continue
    const icon = EMOTE_ICONS[emoteKey]
    if (!icon) continue

    const r = c.radius ?? 1.2
    const bob = Math.sin(nowTime * 4.5 + c.id * 0.7) * 0.3
    const bx = c.x
    const by = c.y - r - 2.2 + bob

    ctx.fillStyle = 'rgba(13, 17, 23, 0.88)'
    ctx.strokeStyle = '#58a6ff'
    ctx.lineWidth = 0.25
    const bw = 2.8
    const bh = 2.4
    ctx.beginPath()
    ctx.roundRect(bx - bw / 2, by - bh / 2, bw, bh, 0.8)
    ctx.fill()
    ctx.stroke()

    ctx.font = '1.6px ui-monospace, monospace'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(icon, bx, by + 0.1)
  }

  return houses
}

export function drawCreatureRaycasting(
  ctx: CanvasRenderingContext2D,
  creature: EntityState,
  state: StateMessage,
  camScale: number,
  tick: number,
): void {
  const result = computeCreatureRays(creature, state)
  const ox = result.origin.x
  const oy = result.origin.y
  const leftRay = result.rays[0]
  const midRay = result.rays[1]
  const rightRay = result.rays[2]

  ctx.save()

  // 1. Sensory Field of View Cone (Arc fan)
  const coneRadius = Math.max(leftRay.maxDist, rightRay.maxDist, midRay.maxDist)
  try {
    const coneGrad = ctx.createRadialGradient(ox, oy, 0, ox, oy, coneRadius)
    coneGrad.addColorStop(0, 'rgba(56, 139, 253, 0.16)')
    coneGrad.addColorStop(0.7, 'rgba(56, 139, 253, 0.04)')
    coneGrad.addColorStop(1, 'rgba(56, 139, 253, 0.0)')

    ctx.fillStyle = coneGrad
    ctx.beginPath()
    ctx.moveTo(ox, oy)
    ctx.arc(ox, oy, coneRadius, leftRay.angle, rightRay.angle)
    ctx.closePath()
    ctx.fill()
  } catch {}

  // Cone perimeter arc
  ctx.strokeStyle = 'rgba(88, 166, 255, 0.28)'
  ctx.lineWidth = Math.max(0.18, 0.8 / camScale)
  ctx.setLineDash([0.6, 0.6])
  ctx.beginPath()
  ctx.arc(ox, oy, coneRadius, leftRay.angle, rightRay.angle)
  ctx.stroke()
  ctx.setLineDash([])

  // 2. Individual Rays (Left, Mid, Right)
  const tagLabels: Array<{ text: string; x: number; y: number; color: string }> = []

  for (let i = 0; i < 3; i++) {
    const ray = result.rays[i]
    const col = rayHitColor(ray.hitType)
    const isHit = ray.hitType !== null

    // A. Sensing beam corridor (the ±1.5 units tolerance width)
    ctx.strokeStyle = isHit ? `${col}18` : 'rgba(88, 166, 255, 0.04)'
    ctx.lineWidth = 2.4
    ctx.beginPath()
    ctx.moveTo(ox, oy)
    ctx.lineTo(ray.hitPoint.x, ray.hitPoint.y)
    ctx.stroke()

    // B. Core Ray Line
    if (isHit) {
      // Glow underlay
      ctx.strokeStyle = `${col}40`
      ctx.lineWidth = Math.max(0.6, 2.4 / camScale)
      ctx.beginPath()
      ctx.moveTo(ox, oy)
      ctx.lineTo(ray.hitPoint.x, ray.hitPoint.y)
      ctx.stroke()

      // Crisp core line
      ctx.strokeStyle = col
      ctx.lineWidth = Math.max(0.3, 1.2 / camScale)
      ctx.beginPath()
      ctx.moveTo(ox, oy)
      ctx.lineTo(ray.hitPoint.x, ray.hitPoint.y)
      ctx.stroke()

      // C. Hit Impact Marker
      const pulse = Math.sin(tick * 0.2 + i * 2) * 0.15
      const ringR = 0.7 + pulse
      ctx.strokeStyle = col
      ctx.lineWidth = Math.max(0.2, 0.9 / camScale)
      ctx.beginPath()
      ctx.arc(ray.hitPoint.x, ray.hitPoint.y, ringR, 0, TAU)
      ctx.stroke()

      ctx.fillStyle = col
      ctx.beginPath()
      ctx.arc(ray.hitPoint.x, ray.hitPoint.y, 0.3, 0, TAU)
      ctx.fill()

      // Dotted connection line to target entity center if slightly offset
      if (ray.hitEntityId && state.entities) {
        const tgt = state.entities.find((e) => e.id === ray.hitEntityId)
        if (tgt && (Math.abs(tgt.x - ray.hitPoint.x) > 0.3 || Math.abs(tgt.y - ray.hitPoint.y) > 0.3)) {
          ctx.strokeStyle = `${col}66`
          ctx.lineWidth = Math.max(0.15, 0.6 / camScale)
          ctx.setLineDash([0.4, 0.4])
          ctx.beginPath()
          ctx.moveTo(ray.hitPoint.x, ray.hitPoint.y)
          ctx.lineTo(tgt.x, tgt.y)
          ctx.stroke()
          ctx.setLineDash([])
        }
      }
    } else {
      // Clear line of sight (dashed line)
      ctx.strokeStyle = 'rgba(139, 148, 158, 0.45)'
      ctx.lineWidth = Math.max(0.2, 0.8 / camScale)
      ctx.setLineDash([0.8, 0.8])
      ctx.beginPath()
      ctx.moveTo(ox, oy)
      ctx.lineTo(ray.hitPoint.x, ray.hitPoint.y)
      ctx.stroke()
      ctx.setLineDash([])
    }

    // Telemetry label data for high-zoom view
    if (camScale >= 3.0) {
      const prefix = i === 0 ? 'L' : i === 1 ? 'MID' : 'R'
      const labelText = isHit
        ? `${prefix}: ${ray.hitLabel} ${ray.hitDist.toFixed(1)}m`
        : `${prefix}: Clear`
      const placeDist = isHit ? Math.max(2.0, ray.hitDist * 0.7) : ray.maxDist * 0.55
      const lx = ox + Math.cos(ray.angle) * placeDist
      const ly = oy + Math.sin(ray.angle) * placeDist
      tagLabels.push({ text: labelText, x: lx, y: ly, color: col })
    }
  }

  // 3. Render telemetry badges on canvas
  if (tagLabels.length > 0) {
    ctx.font = 'bold 0.85px ui-monospace, monospace'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    for (const tag of tagLabels) {
      const metrics = ctx.measureText(tag.text)
      const pw = metrics.width + 0.8
      const ph = 1.2
      ctx.fillStyle = 'rgba(13, 17, 23, 0.85)'
      ctx.fillRect(tag.x - pw / 2, tag.y - ph / 2, pw, ph)
      ctx.strokeStyle = tag.color
      ctx.lineWidth = 0.15
      ctx.strokeRect(tag.x - pw / 2, tag.y - ph / 2, pw, ph)
      ctx.fillStyle = '#e6edf3'
      ctx.fillText(tag.text, tag.x, tag.y)
    }
  }

  ctx.restore()
}

export function renderWorldFrame(
  ctx: CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D,
  state: StateMessage,
  cw: number,
  ch: number,
  cam: Camera,
  selectedId: number | null,
  selectedClanId: number | null,
  lensMode: LensMode = 'classic',
): void {
  ctx.setTransform(1, 0, 0, 1, 0, 0)
  ctx.fillStyle = '#0b0f14'
  ctx.fillRect(0, 0, cw, ch)

  // Sky tint
  const sun = Math.sin((state.time_of_day - 0.25) * TAU)
  const darkness = Math.max(0, Math.min(1, 0.55 - 0.55 * sun))
  if (darkness > 0.01) {
    ctx.fillStyle = `rgba(4,8,24,${(darkness * 0.45).toFixed(3)})`
    ctx.fillRect(0, 0, cw, ch)
  }

  const seasonTint: Record<string, string> = {
    spring: 'rgba(80,160,90,0.05)',
    summer: 'rgba(220,180,60,0.05)',
    autumn: 'rgba(200,120,50,0.06)',
    winter: 'rgba(150,190,255,0.08)',
  }
  ctx.fillStyle = seasonTint[state.season] ?? 'rgba(0,0,0,0)'
  ctx.fillRect(0, 0, cw, ch)

  const padVL = 2
  const vL0 = -cam.ox / cam.scale - padVL
  const vR0 = (cw - cam.ox) / cam.scale + padVL
  const vT0 = -cam.oy / cam.scale - padVL
  const vB0 = (ch - cam.oy) / cam.scale + padVL
  const visible0 = (x: number, y: number, r = padVL) =>
    x + r >= vL0 && x - r <= vR0 && y + r >= vT0 && y - r <= vB0

  if (state.age) {
    const ageTint: Record<string, string> = {
      Golden: 'rgba(255,215,80,0.07)',
      Ice: 'rgba(150,200,255,0.09)',
      Chaos: 'rgba(180,80,255,0.06)',
      Plague: 'rgba(80,200,80,0.06)',
    }
    const at = ageTint[state.age]
    if (at) {
      ctx.fillStyle = at
      ctx.fillRect(0, 0, cw, ch)
    }
  }

  drawWeather(ctx, state.weather, cw, ch)

  ctx.strokeStyle = 'rgba(110,118,129,0.45)'
  ctx.lineWidth = 1
  ctx.strokeRect(cam.ox, cam.oy, state.width * cam.scale, state.height * cam.scale)

  // Grid
  let step = 5
  while (step * cam.scale < 28 && step < 100) step *= 2
  ctx.strokeStyle = 'rgba(110,118,129,0.12)'
  ctx.beginPath()
  for (let x = step; x < state.width; x += step) {
    ctx.moveTo(cam.ox + x * cam.scale, cam.oy)
    ctx.lineTo(cam.ox + x * cam.scale, cam.oy + state.height * cam.scale)
  }
  for (let y = step; y < state.height; y += step) {
    ctx.moveTo(cam.ox, cam.oy + y * cam.scale)
    ctx.lineTo(cam.ox + state.width * cam.scale, cam.oy + y * cam.scale)
  }
  ctx.stroke()

  // §AQ PH-4 & §BL-1: subtle hillshade under everything — hardware blitted from cached offscreen canvas
  const elev = state.elevation
  if (elev && elev.h?.length) {
    const elevCanvas = getElevationCanvas(elev)
    if (elevCanvas) {
      const prevSmoothing = ctx.imageSmoothingEnabled
      ctx.imageSmoothingEnabled = false
      ctx.drawImage(
        elevCanvas as any,
        cam.ox,
        cam.oy,
        elev.cols * elev.cell * cam.scale,
        elev.rows * elev.cell * cam.scale,
      )
      ctx.imageSmoothingEnabled = prevSmoothing
    }
  }

  // §AQ PH-9: lightning bolts — a white jagged flash with a hot core
  for (const b of state.lightning ?? []) {
    const px = cam.ox + b.x * cam.scale
    const py = cam.oy + b.y * cam.scale
    const a = Math.max(0, (b.ttl ?? 0) / 6)
    ctx.globalAlpha = 0.85 * a
    ctx.strokeStyle = '#e3b341'
    ctx.lineWidth = 0.9
    ctx.beginPath()
    ctx.moveTo(px, cam.oy)
    let seg = 0
    let sy = cam.oy
    while (sy < py - 4) {
      sy += (py - cam.oy) / 7
      seg = Math.sin(b.x * 13.7 + sy * 3.1) * 3.0
      ctx.lineTo(px + seg, sy)
    }
    ctx.lineTo(px, py)
    ctx.stroke()
    ctx.strokeStyle = '#ffffff'
    ctx.lineWidth = 0.3
    ctx.stroke()
    ctx.globalAlpha = 0.5 * a
    ctx.fillStyle = '#fff8d0'
    ctx.beginPath()
    ctx.arc(px, py, 2.2 * a + 0.4, 0, TAU)
    ctx.fill()
    ctx.globalAlpha = 1
  }

  // §AQ PH-10: discovered anomaly zones — faint pulsing wrong-colour ground
  for (const a of state.anomalies ?? []) {
    const px = cam.ox + a.x * cam.scale
    const py = cam.oy + a.y * cam.scale
    const pulse = 0.5 + 0.2 * Math.sin(state.tick * 0.05 + a.x)
    const tint =
      a.kind === 'fertile' ? 'rgba(80,220,120,' :
      a.kind === 'heavy' ? 'rgba(130,90,200,' : 'rgba(120,190,230,'
    ctx.fillStyle = `${tint}${0.10 * pulse})`
    ctx.beginPath()
    ctx.arc(px, py, 9 * cam.scale, 0, TAU)
    ctx.fill()
    ctx.strokeStyle = `${tint}${0.35 * pulse})`
    ctx.lineWidth = 0.3
    ctx.setLineDash([1.5, 1.2])
    ctx.stroke()
    ctx.setLineDash([])
  }

  // §AQ PH-10: the law-change shimmer wave sweeping west → east
  const lw = state.law_wave
  if (lw && lw.born_tick != null) {
    const p = Math.min(1, Math.max(0, (state.tick - lw.born_tick) / (lw.ticks || 30)))
    if (p < 1) {
      const fx = cam.ox + p * state.width * cam.scale
      const grad = ctx.createLinearGradient(fx - 30, 0, fx + 30, 0)
      grad.addColorStop(0, 'rgba(210,168,255,0)')
      grad.addColorStop(0.5, `rgba(210,168,255,${0.35 * (1 - p)})`)
      grad.addColorStop(1, 'rgba(210,168,255,0)')
      ctx.fillStyle = grad
      ctx.fillRect(fx - 30, cam.oy, 60, state.height * cam.scale)
    }
  }

  // Fertile grounds & Rocks
  for (const p of state.terrain_fertile ?? []) {
    ctx.fillStyle = 'rgba(80,160,90,0.10)'
    ctx.beginPath()
    ctx.arc(cam.ox + p.x * cam.scale, cam.oy + p.y * cam.scale, p.r * cam.scale, 0, TAU)
    ctx.fill()
  }
  for (const r of state.terrain_rocks ?? []) {
    ctx.fillStyle = '#30363d'
    ctx.strokeStyle = '#6e7681'
    ctx.lineWidth = 1
    ctx.beginPath()
    ctx.arc(cam.ox + r.x * cam.scale, cam.oy + r.y * cam.scale, r.r * cam.scale, 0, TAU)
    ctx.fill()
    ctx.stroke()
  }

  // §AV F-1: river gradients are static per (cy,hw,flood) — cache the gradient
  // instead of creating fresh GPU textures per frame.
  const _riverGradCache = (_riverGradCacheGlobal as Map<string, CanvasGradient>)
  // §AQ PH-3: rivers — horizontal channel bands with a flow direction
  for (const rv of state.rivers ?? []) {
    const cy = cam.oy + rv.cy * cam.scale
    const hw = Math.max(1, rv.hw * cam.scale)
    const gkey = `${Math.round(cy)}:${Math.round(hw)}:${rv.flood ? 1 : 0}`
    let grad = _riverGradCache.get(gkey)
    if (!grad) {
      grad = ctx.createLinearGradient(0, cy - hw, 0, cy + hw)
    if (rv.flood) {
      grad.addColorStop(0, 'rgba(60,120,190,0.10)')
      grad.addColorStop(0.5, 'rgba(70,140,210,0.45)')
      grad.addColorStop(1, 'rgba(60,120,190,0.10)')
    } else {
      grad.addColorStop(0, 'rgba(50,110,180,0.08)')
      grad.addColorStop(0.5, 'rgba(60,130,200,0.32)')
      grad.addColorStop(1, 'rgba(50,110,180,0.08)')
    }
      _riverGradCache.set(gkey, grad)
    }
    ctx.fillStyle = grad
    ctx.fillRect(cam.ox, cy - hw, state.width * cam.scale, hw * 2)
    // flow direction chevrons drift along the current
    ctx.strokeStyle = rv.flood ? 'rgba(160,210,255,0.5)' : 'rgba(150,200,240,0.28)'
    ctx.lineWidth = 1
    const t = (state.tick % 90) / 90
    ctx.beginPath()
    for (let x = ((t * 40) % 40); x < state.width; x += 40) {
      const px = cam.ox + x * cam.scale
      const d = rv.dir >= 0 ? 1 : -1
      ctx.moveTo(px - 3 * d, cy)
      ctx.lineTo(px + 3 * d, cy)
    }
    ctx.stroke()
  }

  // §AQ PH-3: bridges & dams cross the channels
  for (const b of state.bridges ?? []) {
    const rv = (state.rivers ?? []).find((r) => r.cy === b.cy)
    const hw = Math.max(2, (rv?.hw ?? 4) * cam.scale)
    ctx.fillStyle = '#8a6d3b'
    ctx.fillRect(cam.ox + (b.x - 1.5) * cam.scale, cam.oy + (b.cy * cam.scale - hw), 3 * cam.scale, hw * 2)
    ctx.strokeStyle = 'rgba(227,179,65,0.8)'
    ctx.strokeRect(cam.ox + (b.x - 1.5) * cam.scale, cam.oy + (b.cy * cam.scale - hw), 3 * cam.scale, hw * 2)
  }
  for (const d of state.dams ?? []) {
    const h = 10 * cam.scale
    ctx.fillStyle = `rgba(110,118,129,${0.5 + 0.5 * (d.hp_frac ?? 1)})`
    ctx.fillRect(cam.ox + (d.x - 2) * cam.scale, cam.oy + d.cy * cam.scale - h / 2, 4 * cam.scale, h)
  }

  // Territory circles
  for (const e of state.entities) {
    if (e.kind === 'house' && e.clan_id && !e.is_ruin && e.clan_color) {
      if (!visible0(e.x, e.y, 14)) continue
      const tr = 14
      ctx.fillStyle = e.clan_color
      ctx.globalAlpha = 0.07
      ctx.beginPath()
      ctx.arc(cam.ox + e.x * cam.scale, cam.oy + e.y * cam.scale, tr * cam.scale, 0, TAU)
      ctx.fill()
      ctx.globalAlpha = 0.18
      ctx.strokeStyle = e.clan_color
      ctx.lineWidth = 1
      ctx.setLineDash([5, 4])
      ctx.beginPath()
      ctx.arc(cam.ox + e.x * cam.scale, cam.oy + e.y * cam.scale, tr * cam.scale, 0, TAU)
      ctx.stroke()
      ctx.setLineDash([])
      ctx.globalAlpha = 1
    }
  }

  // Signals — uses hoisted SIGNAL_COLOR (§BL-4)
  if (state.signals) {
    for (const sg of state.signals) {
      if (!visible0(sg.x, sg.y, 5)) continue
      const sx = cam.ox + sg.x * cam.scale
      const sy = cam.oy + sg.y * cam.scale
      // long-lived signals (§AN scent trails outlive the 15-tick ripple
      // window) must never push the radius negative — arc() throws on that
      const age = Math.max(0, 15 - (sg.ttl ?? 0))
      const radius = (4 + age * 2.2) * (cam.scale / 12)
      const alpha = Math.max(0, 0.45 - age * 0.03)
      if (alpha <= 0) continue
      ctx.globalAlpha = alpha
      const signalColor = SIGNAL_COLOR[sg.kind] ?? '#f85149'
      ctx.strokeStyle = signalColor
      ctx.lineWidth = 1.2
      ctx.beginPath()
      ctx.arc(sx, sy, radius, 0, TAU)
      ctx.stroke()
      ctx.globalAlpha = 0.9
      ctx.fillStyle = signalColor
      ctx.beginPath()
      ctx.arc(sx, sy, 2, 0, TAU)
      ctx.fill()
      ctx.globalAlpha = 1
    }
  }

  // Entities & World Space
  ctx.setTransform(cam.scale, 0, 0, cam.scale, cam.ox, cam.oy)
  const pad = 2
  const vL = -cam.ox / cam.scale - pad
  const vR = (cw - cam.ox) / cam.scale + pad
  const vT = -cam.oy / cam.scale - pad
  const vB = (ch - cam.oy) / cam.scale + pad
  const visible = (x: number, y: number, r = pad) =>
    x + r >= vL && x - r <= vR && y + r >= vT && y - r <= vB

  // §AN boundary stones — clan-colored diamonds on the border
  if (state.boundary_stones) {
    for (const st of state.boundary_stones) {
      if (!visible(st.x, st.y, 2)) continue
      const color = state.clans?.[String(st.clan_id)]?.color ?? '#8b949e'
      ctx.globalAlpha = 0.9
      ctx.fillStyle = color
      ctx.beginPath()
      ctx.moveTo(st.x, st.y - 1.2)
      ctx.lineTo(st.x + 1.2, st.y)
      ctx.lineTo(st.x, st.y + 1.2)
      ctx.lineTo(st.x - 1.2, st.y)
      ctx.closePath()
      ctx.fill()
      ctx.globalAlpha = 1
    }
  }

  // §AN neutral trading posts
  if (state.markets) {
    for (const m of state.markets) {
      if (!visible(m.x, m.y, 2)) continue
      ctx.globalAlpha = 0.85
      ctx.strokeStyle = '#e3b341'
      ctx.lineWidth = 0.4
      ctx.beginPath()
      ctx.arc(m.x, m.y, 1.6, 0, TAU)
      ctx.stroke()
      ctx.fillStyle = '#e3b341'
      ctx.beginPath()
      ctx.arc(m.x, m.y, 0.45, 0, TAU)
      ctx.fill()
      ctx.globalAlpha = 1
    }
  }

  // Fires
  if (state.fires) {
    for (const f of state.fires) {
      if (!visible(f.x, f.y, f.r)) continue
      const alpha = Math.max(0.35, Math.min(0.9, f.ttl / 28))
      ctx.globalAlpha = alpha
      ctx.fillStyle = '#ff6b35'
      ctx.beginPath()
      ctx.arc(f.x, f.y, f.r * 0.9, 0, TAU)
      ctx.fill()
      ctx.strokeStyle = '#ffd166'
      ctx.lineWidth = 0.25
      ctx.stroke()
      ctx.fillStyle = '#ffd166'
      ctx.globalAlpha = alpha * 0.85
      ctx.beginPath()
      ctx.arc(f.x, f.y, f.r * 0.45, 0, TAU)
      ctx.fill()
      ctx.globalAlpha = 1
    }
  }

  // §AO E: field campfires — a small warm glow with a ring of light
  if (state.campfires) {
    for (const cf of state.campfires) {
      if (!visible(cf.x, cf.y, 4)) continue
      ctx.globalAlpha = 0.14
      ctx.fillStyle = '#ffb347'
      ctx.beginPath()
      ctx.arc(cf.x, cf.y, CAMPFIRE_LIGHT_RADIUS, 0, TAU)
      ctx.fill()
      ctx.globalAlpha = 0.95
      ctx.fillStyle = '#ff8c42'
      ctx.beginPath()
      ctx.arc(cf.x, cf.y, 0.7, 0, TAU)
      ctx.fill()
      ctx.fillStyle = '#ffd166'
      ctx.beginPath()
      ctx.arc(cf.x, cf.y - 0.15, 0.35, 0, TAU)
      ctx.fill()
      ctx.globalAlpha = 1
    }
  }

  const visibleHouses = drawBatchedEntities(ctx, state.entities, visible, cam.scale, selectedId, state.tick, lensMode)

  // Totem Poles + §AP Shrines & Temples of the Sphere
  const drawnShrines = new Set<string>()
  for (const e of visibleHouses) {
    if (!e.clan_id || e.is_ruin) continue
    const clan = state.clans?.[String(e.clan_id)]
    const totem: string | undefined = clan?.totem
    const isMain = e.is_main
    const size = e.size ?? 8
    const poleX = e.x + size / 2 + 1.2
    const poleY = e.y - size / 2 + 1.0
    ctx.save()
    ctx.translate(poleX, poleY)
    ctx.fillStyle = isMain ? '#e3b341' : '#8b949e'
    ctx.fillRect(-0.2, -1.3, 0.4, 2.6)
    const info = totem ? TOTEMS[totem] : null
    ctx.fillStyle = info?.color ?? '#e6edf3'
    ctx.font = isMain ? '2.1px ui-monospace, monospace' : '1.7px ui-monospace, monospace'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(info?.emoji ?? (isMain ? '👑' : '•'), 0, -1.8)
    if (isMain) {
      ctx.fillStyle = '#e3b341'
      ctx.font = '1.3px ui-monospace, monospace'
      ctx.fillText('👑', 0, -3.4)
    }
    ctx.restore()

    // §AP shrine beside the main house: a glowing avatar stone whose aura
    // scales with faith; a temple (level 2) shines across the territory.
    const shrineLevel = clan?.shrine_level ?? 0
    if (isMain && shrineLevel >= 1 && !drawnShrines.has(String(e.clan_id))) {
      drawnShrines.add(String(e.clan_id))
      const faith = clan?.faith ?? 0
      const sx = e.x + size / 2 + 1.5
      const sy = e.y
      const glowA = Math.min(0.55, 0.18 + faith / 800)
      const auraR = shrineLevel >= 2 ? Math.max(10, 14) : 10
      // blessing aura
      ctx.globalAlpha = glowA * (shrineLevel >= 2 ? 0.5 : 0.35)
      ctx.fillStyle = info?.color ?? '#e3b341'
      ctx.beginPath()
      ctx.arc(sx, sy, auraR, 0, TAU)
      ctx.fill()
      ctx.globalAlpha = 1
      // the shrine stone itself
      ctx.save()
      ctx.translate(sx, sy)
      ctx.fillStyle = shrineLevel >= 2 ? '#e3b341' : '#6e7681'
      ctx.fillRect(-0.5, -1.4, 1.0, 2.8)
      ctx.font = '1.9px ui-monospace, monospace'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText(info?.emoji ?? '⭕', 0, -2.4)
      if (shrineLevel >= 2) {
        ctx.strokeStyle = '#e3b341'
        ctx.lineWidth = 0.35
        ctx.setLineDash([1.4, 1.0])
        ctx.beginPath()
        ctx.arc(0, 0, auraR, 0, TAU)
        ctx.stroke()
        ctx.setLineDash([])
        ctx.font = '1.2px ui-monospace, monospace'
        ctx.fillStyle = '#e3b341'
        ctx.fillText('⛪', 0, -4.2)
      }
      ctx.restore()
    }
  }

  // Selection Halo & Sensory Raycasting
  if (selectedId !== null) {
    const selEnt = state.entities.find((e) => e.id === selectedId)
    if (selEnt) {
      if (selEnt.kind === 'creature' && ctx instanceof CanvasRenderingContext2D) {
        drawCreatureRaycasting(ctx, selEnt, state, cam.scale, state.tick)
      }
      ctx.strokeStyle = '#e3b341'
      ctx.lineWidth = 0.4
      ctx.setLineDash([1.2, 0.8])
      ctx.beginPath()
      ctx.arc(selEnt.x, selEnt.y, (selEnt.radius ?? 1.2) + 2.0, 0, TAU)
      ctx.stroke()
      ctx.setLineDash([])
      if ((selEnt as any).personal_name) {
        ctx.fillStyle = '#e6edf3'
        ctx.font = '2px ui-monospace, monospace'
        ctx.textAlign = 'center'
        ctx.textBaseline = 'bottom'
        const titleSuffix = (selEnt as any).title ? ` ${(selEnt as any).title}` : ''
        const label = `${(selEnt as any).personal_name}${titleSuffix} ${(selEnt as any).glyph ?? ''}`
        ctx.strokeStyle = 'rgba(11,15,20,0.85)'
        ctx.lineWidth = 0.4
        ctx.strokeText(label, selEnt.x, selEnt.y - (selEnt.radius ?? 1.2) - 2.5)
        ctx.fillText(label, selEnt.x, selEnt.y - (selEnt.radius ?? 1.2) - 2.5)
      }
    }
  }

  // Selected Clan Highlight
  if (selectedClanId !== null) {
    const clan = state.clans?.[String(selectedClanId)]
    const clanColor = clan?.color ?? '#58a6ff'
    const clanName = clan?.name ?? `Clan ${selectedClanId}`
    const clanTotem = clan?.totem
    const totemChar = (clanTotem && TOTEMS[clanTotem]?.emoji) || '🚩'

    const clanHouses = state.entities.filter((e) => e.kind === 'house' && e.clan_id === selectedClanId && !e.is_ruin)
    const clanMembers = state.entities.filter((e) => e.kind === 'creature' && e.clan_id === selectedClanId)

    for (const m of clanMembers) {
      ctx.strokeStyle = clanColor
      ctx.lineWidth = 0.35
      ctx.setLineDash([1.0, 0.8])
      ctx.beginPath()
      ctx.arc(m.x, m.y, (m.radius ?? 1.2) + 1.6, 0, TAU)
      ctx.stroke()
      ctx.setLineDash([])
    }

    for (const h of clanHouses) {
      if (h.is_main) {
        ctx.strokeStyle = '#e3b341'
        ctx.lineWidth = 0.5
        ctx.setLineDash([2, 1.5])
        ctx.beginPath()
        ctx.arc(h.x, h.y, (h.size ?? 6) * 0.75, 0, TAU)
        ctx.stroke()
        ctx.setLineDash([])
        ctx.fillStyle = '#e3b341'
        ctx.font = '1.7px ui-monospace, monospace'
        ctx.textAlign = 'center'
        ctx.textBaseline = 'bottom'
        ctx.fillText('👑 Leader Main House', h.x, h.y - (h.size ?? 6) / 2 - 1.2)
      }
    }

    const clanEntities = clanHouses.length > 0 ? clanHouses : clanMembers
    if (clanEntities.length > 0) {
      // Spatial clustering: group nearby houses/settlements within 40 units
      const clusters = clusterEntities(clanEntities, 40.0)

      for (let ci = 0; ci < clusters.length; ci++) {
        const cluster = clusters[ci]
        let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity
        let hasMain = false
        for (const e of cluster) {
          minX = Math.min(minX, e.x)
          maxX = Math.max(maxX, e.x)
          minY = Math.min(minY, e.y)
          maxY = Math.max(maxY, e.y)
          if ((e as any).is_main) hasMain = true
        }

        const padC = cluster.length === 1 ? 8 : 12
        minX -= padC; maxX += padC
        minY -= padC; maxY += padC

        ctx.strokeStyle = clanColor
        ctx.lineWidth = 0.55
        ctx.setLineDash([3.0, 2.0])
        ctx.strokeRect(minX, minY, maxX - minX, maxY - minY)
        ctx.fillStyle = clanColor
        ctx.globalAlpha = 0.06
        ctx.fillRect(minX, minY, maxX - minX, maxY - minY)
        ctx.globalAlpha = 1
        ctx.setLineDash([])

        const midX = (minX + maxX) / 2
        const bannerY = minY - 2.8
        let bannerText = `${totemChar} ${clanName}`
        if (clusters.length === 1) {
          bannerText = `${totemChar} ${clanName} (${clanMembers.length} members · ${clanHouses.length} houses)`
        } else if (hasMain) {
          bannerText = `👑 ${clanName} (Main Village · ${cluster.length} ${cluster.length === 1 ? 'house' : 'houses'})`
        } else {
          bannerText = `📍 ${clanName} (Outpost · ${cluster.length} ${cluster.length === 1 ? 'house' : 'houses'})`
        }

        ctx.font = '2.2px ui-monospace, monospace'
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        const bw = Math.max(24, (bannerText.length * 1.35) + 4)
        const bh = 3.8

        ctx.fillStyle = 'rgba(13,17,23,0.92)'
        ctx.strokeStyle = clanColor
        ctx.lineWidth = 0.35
        ctx.fillRect(midX - bw / 2, bannerY - bh / 2, bw, bh)
        ctx.strokeRect(midX - bw / 2, bannerY - bh / 2, bw, bh)

        ctx.fillStyle = '#e6edf3'
        ctx.fillText(bannerText, midX, bannerY + 0.1)
      }
    }
  }

  ctx.setTransform(1, 0, 0, 1, 0, 0)
}

export function pickCreatureAt(
  state: StateMessage | null,
  clientX: number,
  clientY: number,
  cam: Camera,
  dpr: number,
): number | null {
  if (!state) return null
  const px = clientX * dpr
  const py = clientY * dpr
  const pickRadiusWorld = Math.max(6.0, 44 / cam.scale)
  let bestId: number | null = null
  let bestD = Infinity
  for (const e of state.entities) {
    if (e.kind !== 'creature') continue
    const sx = cam.ox + e.x * cam.scale
    const sy = cam.oy + e.y * cam.scale
    const d = Math.hypot(sx - px, sy - py)
    if (d < bestD) {
      bestD = d
      bestId = e.id
    }
  }
  if (bestId !== null && bestD <= Math.max(28, pickRadiusWorld * cam.scale)) return bestId
  return null
}
