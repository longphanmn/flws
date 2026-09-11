import { useEffect, useRef, useState } from 'react'
import type { EntityState, HistoryEvent, StateMessage } from '../types'
import { totemEmoji } from '../totems'
import { useI18n } from '../i18n'
import { CreatureAvatar, CASTE_COLORS } from '../components/CreatureAvatar'
import { computeCreatureRays, rayHitColor } from '../render/raycast'


interface KinCard {
  id: number
  caste: string | null
  alive: boolean
  clan_color: string | null
  personal_name?: string | null
  glyph?: string | null
  hue_shift?: number | null
  scale_jitter?: number | null
}

interface Family {
  mother: KinCard | null
  father: KinCard | null
  children: KinCard[]
}

interface CreatureResponse {
  entity: EntityState | null
  events: HistoryEvent[]
  family?: Family
}


function eventLine(ev: HistoryEvent, t: (k: string, v?: any) => string): string {
  switch (ev.type) {
    case 'birth':
      return t('inspector.bornTo', { mother: (ev.payload as any)?.mother, father: (ev.payload as any)?.father })
    case 'promotion':
      return t('inspector.roseTo', { caste: ev.caste })
    case 'demotion':
      return t('inspector.demoted', { caste: ev.caste })
    case 'recovery':
      return t('inspector.recovered', { id: (ev.payload as any)?.disease_id ?? '' })
    case 'death':
      return t('inspector.diedOf', { cause: ev.cause, x: Math.round(ev.x), y: Math.round(ev.y) })
    default:
      return ev.type
  }
}
// keep for future i18n use
void eventLine

function KinCardView({
  kin,
  role,
  onNavigate,
}: {
  kin: KinCard | null
  role: string
  onNavigate: (id: number) => void
}) {
  const { t } = useI18n()
  if (!kin) return <div className="kin-node empty" style={{ background: '#161b22', border: '1px dashed #30363d', borderRadius: 6, padding: '8px 10px', color: '#8b949e', fontSize: 12 }}>{role}: —</div>
  return (
    <button
      className={`kin-node ${kin.alive ? '' : 'dead'}`}
      onClick={() => onNavigate(kin.id)}
      title={kin.alive ? t('inspector.openDossier') : t('inspector.deceased')}
      style={{ background: kin.alive ? '#161b22' : '#21262d', border: `1px solid ${kin.clan_color ?? '#30363d'}`, borderLeft: `3px solid ${kin.clan_color ?? '#8b949e'}`, borderRadius: 6, padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: 2, cursor: 'pointer', textAlign: 'left', minWidth: 0, width: '100%', overflow: 'hidden' }}
    >
      <span style={{ fontSize: 10, color: '#8b949e', textTransform: 'uppercase', letterSpacing: 0.5 }}>{role} {kin.alive ? '' : '†'}</span>
      <span style={{ fontWeight: 700, color: '#e6edf3', fontSize: 12 }}>{kin.personal_name ? `${kin.personal_name} ` : ''}#{kin.id} <span style={{ opacity: 0.7 }}>{kin.glyph ?? ''}</span></span>
      <span style={{ fontSize: 11, color: kin.alive ? '#3fb950' : '#8b949e' }}>{kin.caste ?? '?'} · {kin.alive ? t('inspector.alive') ?? 'alive' : t('inspector.deceased')}</span>
    </button>
  )
}

// §BG-9 Polar Morphology Radar — mutated vs Abbott ghost
const CANONICAL_TEMPLATES: Record<string, { r: number[]; phi: number[]; k: number }> = {
  Woman: { r: [1.8, 0.2, 0.2], phi: [0.0, Math.PI - 0.08, Math.PI + 0.08], k: 3 },
  Soldier: { r: [1.5, 0.8, 0.8], phi: [0.0, 2.4, 3.88], k: 3 },
  Artisan: { r: [1.0, 1.0, 1.0], phi: [0.0, (2 * Math.PI) / 3, (4 * Math.PI) / 3], k: 3 },
  Gentleman: { r: [1.0, 1.0, 1.0, 1.0], phi: [0, Math.PI / 2, Math.PI, (3 * Math.PI) / 2], k: 4 },
  Professional: { r: [1.0, 1.0, 1.0, 1.0, 1.0], phi: [0, 1, 2, 3, 4].map((i) => (i * 2 * Math.PI) / 5), k: 5 },
  Noble: { r: Array(8).fill(1.0), phi: Array.from({ length: 8 }, (_, i) => (i * 2 * Math.PI) / 8), k: 8 },
  Priest: { r: Array(24).fill(1.0), phi: Array.from({ length: 24 }, (_, i) => (i * 2 * Math.PI) / 24), k: 24 },
}

function getCasteTemplate(caste?: string, sides?: number, shape?: string) {
  if (shape === 'line' || caste === 'Woman' || sides === 2) return CANONICAL_TEMPLATES.Woman
  if (caste && CANONICAL_TEMPLATES[caste]) return CANONICAL_TEMPLATES[caste]
  if (sides === 3) return CANONICAL_TEMPLATES.Soldier
  if (sides === 4) return CANONICAL_TEMPLATES.Gentleman
  if (sides === 5) return CANONICAL_TEMPLATES.Professional
  if (sides && sides >= 24) return CANONICAL_TEMPLATES.Priest
  if (sides && sides >= 6) {
    const k = Math.min(24, sides)
    return { r: Array(k).fill(1.0), phi: Array.from({ length: k }, (_, i) => (i * 2 * Math.PI) / k), k }
  }
  return CANONICAL_TEMPLATES.Gentleman
}

function pseudoRand(seed: number, i: number): number {
  const x = Math.sin(seed * 127.1 + i * 311.7) * 43758.5453
  return x - Math.floor(x)
}

function PolarRadar({ e }: { e: EntityState }) {
  const { t } = useI18n()
  const cx = 70, cy = 70
  const scale = 26 // unit r=1.0 maps to 26px; Soldier apex r=1.5 is 39px, Woman r=1.8 is 46.8px (fits comfortably in 50px radius)
  const tpl = getCasteTemplate(e.caste, e.sides, e.shape)
  const k = Math.max(3, Math.min(24, (e as any).morph_k ?? tpl.k))
  const id = (e as any).id ?? 1
  const irr = (e as any).irregularity ?? 0
  const mt = (e as any).morph_traits as number[] | undefined
  const radii = (e as any).morph_radii as number[] | undefined
  const angles = (e as any).morph_angles as number[] | undefined
  const hasDetailed = Array.isArray(radii) && Array.isArray(angles) && radii.length >= k

  // Ghost Abbott template: orthodox canonical shape for this caste
  // Heading phi=0 points UP (North) with -pi/2
  const ghostPts: Array<[number, number]> = []
  for (let i = 0; i < tpl.k; i++) {
    const a = tpl.phi[i] - Math.PI / 2
    const rr = tpl.r[i] * scale
    ghostPts.push([cx + Math.cos(a) * rr, cy + Math.sin(a) * rr])
  }

  // Mutated points: from detailed arrays or preview from caste template with irregularity
  const mutPts: Array<[number, number]> = []
  if (hasDetailed) {
    for (let i = 0; i < k; i++) {
      const r = Number(radii![i]) || 1.0
      const a = (Number(angles![i]) || (2 * Math.PI * i / k)) - Math.PI / 2
      const rr = r * scale
      mutPts.push([cx + Math.cos(a) * rr, cy + Math.sin(a) * rr])
    }
  } else {
    // Fallback: apply irregularity jitter to the orthodox caste template
    const baseK = tpl.k
    for (let i = 0; i < baseK; i++) {
      const aJ = (pseudoRand(id, i * 2) - 0.5) * irr * 0.4
      const rJ = 1 + (pseudoRand(id, i * 2 + 1) - 0.5) * irr * 0.7
      const a = tpl.phi[i] + aJ - Math.PI / 2
      const rr = tpl.r[i] * rJ * scale
      mutPts.push([cx + Math.cos(a) * rr, cy + Math.sin(a) * rr])
    }
  }

  const mutStr = mutPts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' ')
  const ghostStr = ghostPts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' ')
  const isMutant = irr > 0.25 || (tpl.k !== 4 && k !== tpl.k) || (mt && ((mt[4] ?? 0) > 0.15 || (mt[5] ?? 0) > 0.3))

  return (
    <div style={{ background: '#0d1117', border: '1px solid #21262d', borderRadius: 8, padding: '8px 8px 6px', minWidth: 0, overflow: 'hidden' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 6, marginBottom: 4, minWidth: 0 }}>
        <span style={{ fontSize: 11, color: '#8b949e', textTransform: 'uppercase', letterSpacing: 0.5, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>🧬 Polar Morph — {e.caste} · K={k} {isMutant && <span style={{ color: '#d2a8ff', border: '1px solid #a371f766', background: '#a371f733', padding: '0 4px', borderRadius: 3, fontSize: 9 }}>{t('inspector.mutantTag')}</span>}</span>
        <span style={{ fontSize: 10, color: '#8b949e', flex: 'none' }}>irr {irr.toFixed(3)}</span>
      </div>
      <svg width={140} height={140} viewBox="0 0 140 140" style={{ display: 'block', margin: '0 auto', background: '#161b22', borderRadius: 6, border: '1px solid #30363d', maxWidth: '100%', height: 'auto' }}>
        {/* radial grid: 0.5, 1.0 (canonical unit circle), 1.5 (apex reach) */}
        {[1.5, 1.0, 0.5].map((s, idx) => (
          <circle key={idx} cx={cx} cy={cy} r={scale * s} fill="none" stroke="#21262d" strokeWidth={0.6} strokeDasharray={s === 1.0 ? undefined : '2 2'} />
        ))}
        {/* angle spoke lines for template vertices */}
        {tpl.phi.map((ph, i) => {
          const a = ph - Math.PI / 2
          return <line key={i} x1={cx} y1={cy} x2={cx + Math.cos(a) * scale * 1.6} y2={cy + Math.sin(a) * scale * 1.6} stroke="#21262d" strokeWidth={0.4} />
        })}
        {/* ghost Abbott orthodoxy */}
        <polygon points={ghostStr} fill="none" stroke="#8b949e" strokeWidth={1.1} opacity={0.4} strokeDasharray="3 3" strokeLinejoin="round" />
        {/* mutated polar polygon */}
        <polygon points={mutStr} fill={isMutant ? 'rgba(163,113,247,0.18)' : 'rgba(121,192,255,0.18)'} stroke={isMutant ? '#d2a8ff' : '#79c0ff'} strokeWidth={1.4} strokeLinejoin="round" />
        {/* vertices */}
        {mutPts.map(([x, y], i) => (
          <circle key={i} cx={x} cy={y} r={1.7} fill={isMutant ? '#d2a8ff' : '#79c0ff'} stroke="#0d1117" strokeWidth={0.7} />
        ))}
        {/* centroid */}
        <circle cx={cx} cy={cy} r={1.2} fill="#e6edf3" />
      </svg>
      <div style={{ display: 'flex', gap: 6, marginTop: 4, fontSize: 10, color: '#8b949e', flexWrap: 'wrap', alignItems: 'center' }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><span style={{ width: 10, height: 2, background: '#8b949e', opacity: 0.6, display: 'inline-block', border: '1px dashed #8b949e' }} /> {t('inspector.abbottOrthodoxy')}</span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><span style={{ width: 10, height: 2, background: isMutant ? '#d2a8ff' : '#79c0ff', display: 'inline-block' }} /> {t('inspector.mutated')}</span>
        {mt && <span style={{ marginLeft: 'auto', color: '#8b949e' }}>A {mt[0]?.toFixed(2)} · θ {((mt[3]||0)*180/Math.PI).toFixed(1)}°</span>}
      </div>
    </div>
  )
}
function BiomechHUD({ e }: { e: EntityState }) {
  const { t } = useI18n()
  const mt = (e as any).morph_traits as number[] | undefined
  const irr = (e as any).irregularity ?? 0
  const area = mt?.[0] ?? 0
  const perim = mt?.[1] ?? 0
  const izz = mt?.[2] ?? 0
  const theta = mt?.[3] ?? Math.PI/3
  const asym = mt?.[4] ?? irr/1.5
  const dmult = mt?.[5] ?? 0
  const hasData = mt && area > 1e-6
  const Aref = 2.0, Iref = 0.333, Pref = 5.657
  if (!hasData) {
    return (
      <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: 6, padding: '8px 10px' }}>
        <div style={{ fontSize: 11, color: '#8b949e', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 6 }}>⚙️ Biomechanical Dossier (BG-10)</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, fontSize: 11 }}>
          <span className="chip" style={{ justifyContent: 'space-between', background: '#0d1117' }}>{t('inspector.irregularityLabel')} <b style={{ color: irr>0.4?'#f85149':'#e6edf3' }}>{irr.toFixed(3)}</b></span>
          <span className="chip" style={{ justifyContent: 'space-between', background: '#0d1117' }}>{t('inspector.stageLabel')} <b>{e.stage}</b></span>
          <span className="chip" style={{ justifyContent: 'space-between', background: '#0d1117' }}>{t('inspector.sidesLabel')} <b>{e.sides}</b></span>
          <span className="chip" style={{ justifyContent: 'space-between', background: '#0d1117' }}>Gen <b>{(e as any).generation ?? 0}</b></span>
        </div>
        <div style={{ fontSize: 10, color: '#6e7681', marginTop: 6 }}>{t('inspector.polarPending')}</div>
      </div>
    )
  }
  const sharpDeg = (theta * 180 / Math.PI)
  const sharpPct = Math.max(0, Math.min(100, (1 - theta / (Math.PI)) * 100 + dmult * 30))
  const asymPct = Math.max(0, Math.min(100, asym * 180))
  const areaPct = Math.max(0, Math.min(100, (area / (Aref * 2.5)) * 100))
  const izzPct = Math.max(0, Math.min(100, (izz / (Iref * 2.2)) * 100))
  return (
    <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: 6, padding: '8px 10px', minWidth: 0 }}>
      <div style={{ fontSize: 11, color: '#8b949e', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 6 }}>⚙️ Biomechanical Dossier</div>
      <div className="insp-2col">
        {[
          { label: 'Sharpness θₘᵢₙ', value: `${sharpDeg.toFixed(1)}°`, sub: `D×${dmult.toFixed(2)}`, pct: sharpPct, color: sharpDeg < 30 ? '#ff7b72' : sharpDeg < 60 ? '#f2cc60' : '#79c0ff' },
          { label: 'Irregularity σ²/ r̄', value: asym.toFixed(3), sub: `irr ${irr.toFixed(3)}`, pct: asymPct, color: asym > 0.4 ? '#f85149' : asym > 0.15 ? '#f2cc60' : '#3fb950' },
          { label: 'Rot. Inertia Izz', value: izz.toFixed(3), sub: `/${Iref.toFixed(2)} ${ (izz/Iref).toFixed(2)}×`, pct: izzPct, color: izz > 1.0 ? '#ff7b72' : '#79c0ff' },
          { label: 'Shoelace Area A', value: area.toFixed(2), sub: `/${Aref.toFixed(1)} ${ (area/Aref).toFixed(2)}×`, pct: areaPct, color: '#d2a8ff' },
        ].map((m) => (
          <div key={m.label} style={{ background: '#0d1117', border: '1px solid #21262d', borderRadius: 6, padding: '6px 7px' }}>
            <div style={{ fontSize: 9, color: '#8b949e', textTransform: 'uppercase', letterSpacing: 0.4 }}>{m.label}</div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 6 }}>
              <span style={{ fontSize: 13, fontWeight: 700, color: '#e6edf3' }}>{m.value}</span>
              <span style={{ fontSize: 10, color: '#8b949e' }}>{m.sub}</span>
            </div>
            <div style={{ height: 3, background: '#21262d', borderRadius: 2, overflow: 'hidden', marginTop: 4 }}>
              <div style={{ width: `${Math.round(m.pct)}%`, height: '100%', background: m.color }} />
            </div>
          </div>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 6, marginTop: 6, fontSize: 10, color: '#8b949e', flexWrap: 'wrap' }}>
        <span>P {perim.toFixed(2)}·Pᵣₑf {Pref.toFixed(1)}</span>
        <span style={{ marginLeft: 'auto' }}>Eₘₐₓ ×{Math.max(0.5, Math.min(2.5, area / Aref)).toFixed(2)} · decay ×{Math.max(0.7, Math.min(2.0, perim / Pref)).toFixed(2)}</span>
      </div>
    </div>
  )
}

function SensoryRayCard({ e, state }: { e: EntityState; state?: StateMessage | null }) {
  const { t } = useI18n()
  if (!state) return null

  const rayResult = computeCreatureRays(e, state)
  const [leftRay, , rightRay] = rayResult.rays

  // Radar geometry (SVG)
  const width = 280, height = 118
  const cx = 140, cy = 104
  const radarRadius = 78

  // Relative heading is UP (-PI/2)
  const leftAngleSVG = -Math.PI / 2 + leftRay.relAngleRad
  const midAngleSVG = -Math.PI / 2
  const rightAngleSVG = -Math.PI / 2 + rightRay.relAngleRad

  // Outer arc endpoints
  const arcX1 = cx + Math.cos(leftAngleSVG) * radarRadius
  const arcY1 = cy + Math.sin(leftAngleSVG) * radarRadius
  const arcX2 = cx + Math.cos(rightAngleSVG) * radarRadius
  const arcY2 = cy + Math.sin(rightAngleSVG) * radarRadius

  // Hit positions on radar
  const rayCoords = rayResult.rays.map((r, i) => {
    const angleSVG = i === 0 ? leftAngleSVG : i === 1 ? midAngleSVG : rightAngleSVG
    const frac = Math.max(0.12, Math.min(1.0, r.hitDist / r.maxDist))
    const hitR = frac * radarRadius
    const hx = cx + Math.cos(angleSVG) * hitR
    const hy = cy + Math.sin(angleSVG) * hitR
    const endX = cx + Math.cos(angleSVG) * radarRadius
    const endY = cy + Math.sin(angleSVG) * radarRadius
    const color = rayHitColor(r.hitType)
    return { ...r, angleSVG, hitR, hx, hy, endX, endY, color }
  })

  // Latched NN inputs if available
  const nnInputs = (e as any).nn_inputs as number[] | undefined

  return (
    <div
      className="sensory-ray-card"
      style={{
        background: '#161b22',
        border: '1px solid #30363d',
        borderRadius: 8,
        padding: '10px 12px',
        minWidth: 0,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 13 }}>👁️</span>
          <span style={{ fontSize: 11, fontWeight: 700, color: '#e6edf3', textTransform: 'uppercase', letterSpacing: 0.5 }}>
            {t('inspector.raycastingTitle') ?? 'Sensory Raycasting'}
          </span>
        </div>
        <span style={{ fontSize: 9, color: '#58a6ff', background: 'rgba(56,139,253,0.12)', border: '1px solid rgba(56,139,253,0.3)', borderRadius: 4, padding: '2px 6px', fontWeight: 600 }}>
          BH-7 Neuro-Morph FOV
        </span>
      </div>

      {/* Miniature Vision Radar SVG */}
      <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 8 }}>
        <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} style={{ background: '#0d1117', borderRadius: 6, border: '1px solid #21262d' }}>
          <defs>
            <radialGradient id="rayRadarGlow" cx="50%" cy="90%" r="90%">
              <stop offset="0%" stopColor="#58a6ff" stopOpacity="0.22" />
              <stop offset="70%" stopColor="#58a6ff" stopOpacity="0.04" />
              <stop offset="100%" stopColor="#58a6ff" stopOpacity="0" />
            </radialGradient>
          </defs>

          {/* Vision Cone Sector */}
          <path
            d={`M ${cx} ${cy} L ${arcX1} ${arcY1} A ${radarRadius} ${radarRadius} 0 0 1 ${arcX2} ${arcY2} Z`}
            fill="url(#rayRadarGlow)"
          />
          {/* Outer Arc Perimeter */}
          <path
            d={`M ${arcX1} ${arcY1} A ${radarRadius} ${radarRadius} 0 0 1 ${arcX2} ${arcY2}`}
            fill="none"
            stroke="#58a6ff"
            strokeWidth="1"
            strokeDasharray="2 2"
            opacity="0.4"
          />

          {/* Distance Reference Rings */}
          {[0.33, 0.66, 1.0].map((s, idx) => (
            <path
              key={idx}
              d={`M ${cx + Math.cos(leftAngleSVG) * radarRadius * s} ${cy + Math.sin(leftAngleSVG) * radarRadius * s} A ${radarRadius * s} ${radarRadius * s} 0 0 1 ${cx + Math.cos(rightAngleSVG) * radarRadius * s} ${cy + Math.sin(rightAngleSVG) * radarRadius * s}`}
              fill="none"
              stroke="#30363d"
              strokeWidth="0.7"
              strokeDasharray="2 3"
            />
          ))}

          {/* Ray Lines */}
          {rayCoords.map((r, i) => {
            const isHit = r.hitType !== null
            return (
              <g key={i}>
                {/* Ray line to hit or max distance */}
                {isHit ? (
                  <>
                    <line x1={cx} y1={cy} x2={r.hx} y2={r.hy} stroke={r.color} strokeWidth="3.5" opacity="0.2" />
                    <line x1={cx} y1={cy} x2={r.hx} y2={r.hy} stroke={r.color} strokeWidth="1.6" />
                    {/* Dashed line extending past hit point to max range */}
                    <line x1={r.hx} y1={r.hy} x2={r.endX} y2={r.endY} stroke="#30363d" strokeWidth="1" strokeDasharray="2 2" opacity="0.5" />
                    {/* Hit marker */}
                    <circle cx={r.hx} cy={r.hy} r="3.5" fill="none" stroke={r.color} strokeWidth="1.2" />
                    <circle cx={r.hx} cy={r.hy} r="1.8" fill={r.color} />
                  </>
                ) : (
                  <line x1={cx} y1={cy} x2={r.endX} y2={r.endY} stroke="#8b949e" strokeWidth="1" strokeDasharray="3 3" opacity="0.5" />
                )}
                {/* Angle label at edge */}
                <text
                  x={cx + Math.cos(r.angleSVG) * (radarRadius + 10)}
                  y={cy + Math.sin(r.angleSVG) * (radarRadius + 10)}
                  fill={isHit ? r.color : '#8b949e'}
                  fontSize="8"
                  fontWeight="bold"
                  fontFamily="ui-monospace, monospace"
                  textAnchor="middle"
                  dominantBaseline="middle"
                >
                  {r.relAngleDeg > 0 ? `+${r.relAngleDeg}°` : `${r.relAngleDeg}°`}
                </text>
              </g>
            )
          })}

          {/* Creature Origin (triangle pointing up) */}
          <polygon
            points={`${cx},${cy - 8} ${cx - 5},${cy + 4} ${cx + 5},${cy + 4}`}
            fill="#e6edf3"
            stroke="#30363d"
            strokeWidth="1"
          />
          <circle cx={cx} cy={cy} r="2" fill="#58a6ff" />
        </svg>
      </div>

      {/* 3-Column Ray Metrics Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6, marginBottom: 8 }}>
        {rayCoords.map((r, i) => {
          const isHit = r.hitType !== null
          const col = r.color
          const slotDist = 3 + i * 2
          const slotType = 4 + i * 2
          const latchedDist = nnInputs ? nnInputs[slotDist] : undefined
          const latchedType = nnInputs ? nnInputs[slotType] : undefined

          return (
            <div
              key={i}
              style={{
                background: '#0d1117',
                border: `1px solid ${isHit ? `${col}55` : '#21262d'}`,
                borderTop: `2px solid ${col}`,
                borderRadius: 6,
                padding: '6px 7px',
                display: 'flex',
                flexDirection: 'column',
                gap: 3,
                minWidth: 0,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', fontSize: 10 }}>
                <span style={{ fontWeight: 700, color: '#e6edf3' }}>
                  {i === 0 ? (t('inspector.rayLeft') ?? 'LEFT') : i === 1 ? (t('inspector.rayForward') ?? 'MID') : (t('inspector.rayRight') ?? 'RIGHT')}
                </span>
                <span style={{ color: '#8b949e', fontSize: 9, fontFamily: 'ui-monospace' }}>
                  {r.relAngleDeg > 0 ? `+${r.relAngleDeg}°` : `${r.relAngleDeg}°`}
                </span>
              </div>

              {/* Hit Status Pill */}
              <div
                style={{
                  fontSize: 10,
                  fontWeight: 600,
                  color: isHit ? col : '#8b949e',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
                title={r.hitLabel}
              >
                {isHit ? `🎯 ${r.hitLabel}` : `✨ ${t('inspector.hitTypeClear') ?? 'Clear'}`}
              </div>

              {/* Distance Meter */}
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, color: '#8b949e', fontFamily: 'ui-monospace' }}>
                <span>Dist:</span>
                <span style={{ color: '#e6edf3', fontWeight: 600 }}>{r.hitDist.toFixed(1)}m</span>
              </div>
              <div style={{ height: 3, background: '#21262d', borderRadius: 2, overflow: 'hidden' }}>
                <div
                  style={{
                    width: `${Math.round((r.hitDist / r.maxDist) * 100)}%`,
                    height: '100%',
                    background: col,
                  }}
                />
              </div>

              {/* Neural Input Mapping (Inputs 3-8) */}
              <div style={{ marginTop: 2, paddingTop: 3, borderTop: '1px dashed #21262d', fontSize: 9, color: '#8b949e', display: 'flex', flexDirection: 'column', gap: 1 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: 'ui-monospace' }}>
                  <span>inp[{slotDist}] (dist)</span>
                  <span style={{ color: '#79c0ff', fontWeight: 600 }}>{(latchedDist ?? r.nnDist).toFixed(2)}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: 'ui-monospace' }}>
                  <span>inp[{slotType}] (type)</span>
                  <span style={{ color: r.nnType > 0 ? '#3fb950' : r.nnType < 0 ? '#f85149' : '#8b949e', fontWeight: 700 }}>
                    {(latchedType ?? r.nnType) > 0 ? '+1.0' : (latchedType ?? r.nnType) < 0 ? '-1.0' : '0.0'}
                  </span>
                </div>
              </div>
            </div>
          )
        })}
      </div>

      {/* Explanatory Footer */}
      <div style={{ fontSize: 9, color: '#8b949e', lineHeight: 1.3, background: '#0d1117', padding: '5px 8px', borderRadius: 4, border: '1px solid #21262d' }}>
        <span style={{ color: '#58a6ff', fontWeight: 600 }}>Micro-RNN coupling: </span>
        Inputs 3–8 feed directly into W1 sensory weights (16→12) allowing the creature to steer towards food/allies and evade enemies/walls in real-time.
      </div>
    </div>
  )
}

// BH-10 NN Connectivity Heatmap 16→12→7
function NNHeatmap({ e }: { e: EntityState }) {
  const genome: number[] | undefined = (e as any).nn_genome as number[] | undefined
  const preview: number[] | undefined = (e as any).nn_genome_preview as number[] | undefined
  const g = genome && genome.length >= 295 ? genome : null
  if (!g) {
    return (
      <div style={{ background: '#0d1117', border: '1px solid #21262d', borderRadius: 8, padding: '8px 10px', marginTop: 8, flexShrink: 0 }}>
        <div style={{ fontSize: 11, color: '#8b949e', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 4 }}>🧠 NN Connectivity 16→12→7 (BH-10)</div>
        <div style={{ fontSize: 11, color: '#6e7681' }}>
          Full 295-weight genome not yet cached — preview {preview ? `(${preview.length} weights)` : '(pending)'}.
          {preview && <span style={{ marginLeft: 6, color: '#8b949e' }}>W1[0]={preview[0]?.toFixed(2)}</span>}
        </div>
        <div style={{ height: 3, background: '#21262d', borderRadius: 2, marginTop: 6 }}><div style={{ width: '18%', height: '100%', background: '#388bfd' }} /></div>
      </div>
    )
  }
  // unpack
  const W1 = g.slice(0, 192) // 16*12 row-major i*12+j
  const b1 = g.slice(192, 204)
  const W2 = g.slice(204, 288) // 12*7
  const b2 = g.slice(288, 295)
  const wColor = (v: number) => {
    const c = Math.max(-2, Math.min(2, v))
    if (c > 0) {
      const intensity = Math.min(1, c / 2)
      const r = Math.round(255 * intensity + 60 * (1 - intensity))
      const gb = Math.round(60 + 120 * (1 - intensity))
      return `rgb(${r},${gb},${gb})`
    } else {
      const intensity = Math.min(1, -c / 2)
      const b = Math.round(255 * intensity + 60 * (1 - intensity))
      const rg = Math.round(60 + 120 * (1 - intensity))
      return `rgb(${rg},${rg},${b})`
    }
  }
  const cellW1 = 10, cellH1 = 10, gap = 1
  const W1w = 16 * (cellW1 + gap) + 8, W1h = 12 * (cellH1 + gap) + 18
  const W2w = 12 * (cellW1 + gap) + 8, W2h = 7 * (cellH1 + gap) + 18
  return (
    <div
      className="nn-heatmap-card"
      style={{
        background: '#0d1117',
        border: '1px solid #21262d',
        borderRadius: 8,
        padding: '8px 10px',
        marginTop: 8,
        minWidth: 0,
        overflow: 'visible',
        flexShrink: 0,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 6, marginBottom: 6, minWidth: 0 }}>
        <span style={{ fontSize: 11, color: '#8b949e', textTransform: 'uppercase', letterSpacing: 0.5, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>🧠 NN Connectivity 16→12→7</span>
        <span style={{ fontSize: 9, color: '#6e7681', flex: 'none' }}>295w · BH-5</span>
      </div>
      <div className="nn-heatmap-wrap" style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'center' }}>
        {/* W1 16→12 */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
          <span style={{ fontSize: 9, color: '#8b949e' }}>W1 16×12 Sensory (p0.03 σ0.06)</span>
          <svg width={W1w} height={W1h} style={{ background: '#161b22', borderRadius: 4, border: '1px solid #30363d' }}>
            {Array.from({ length: 12 }, (_, j) => Array.from({ length: 16 }, (_, i) => {
              const v = W1[i * 12 + j]
              return <rect key={`${i}-${j}`} x={4 + i * (cellW1 + gap)} y={10 + j * (cellH1 + gap)} width={cellW1} height={cellH1} fill={wColor(v)} rx={1} />
            }))}
            {/* b1 bottom row */}
            {b1.map((v, j) => <rect key={`b1-${j}`} x={4 + j * (cellW1 + gap)} y={10 + 12 * (cellH1 + gap) + 2} width={cellW1} height={4} fill={wColor(v)} rx={1} />)}
          </svg>
          <span style={{ fontSize: 8, color: '#6e7681' }}>rows hidden 0-11 · cols input 0-15 (ray, vitals, hidden)</span>
        </div>
        {/* W2 12→7 */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
          <span style={{ fontSize: 9, color: '#8b949e' }}>W2 12×7 Motor (p0.05 σ0.10) + Rec (p0.02)</span>
          <svg width={W2w} height={W2h} style={{ background: '#161b22', borderRadius: 4, border: '1px solid #30363d' }}>
            {Array.from({ length: 7 }, (_, k) => Array.from({ length: 12 }, (_, j) => {
              const v = W2[j * 7 + k]
              return <rect key={`${j}-${k}`} x={4 + j * (cellW1 + gap)} y={10 + k * (cellH1 + gap)} width={cellW1} height={cellH1} fill={wColor(v)} rx={1} />
            }))}
            {b2.map((v, k) => <rect key={`b2-${k}`} x={4 + k * (cellW1 + gap)} y={10 + 7 * (cellH1 + gap) + 2} width={cellW1} height={4} fill={wColor(v)} rx={1} />)}
          </svg>
          <span style={{ fontSize: 8, color: '#6e7681' }}>rows out 0-6 (thrust/steer/social…) · cols hidden 0-11</span>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 6, fontSize: 9, color: '#8b949e', justifyContent: 'center' }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><span style={{ width: 10, height: 6, background: 'linear-gradient(90deg,#3060a0,#ff6060)', display: 'inline-block', borderRadius: 2 }} /> −2 → +2</span>
        <span>·</span>
        <span>Hidden { (e as any).nn_hidden?.toFixed(2) ?? '—'} · outputs {(e as any).nn_outputs?.map((v:number)=>v.toFixed(1)).join(', ') ?? '—'}</span>
      </div>
    </div>
  )
}

interface Props {
  id: number
  state?: any
  onClose: () => void
  onNavigate: (id: number) => void
  onSelectClan?: (clanId: number) => void
}

type TabKey = 'vitals' | 'skills' | 'lineage' | 'chronicle'

export default function Inspector({ id, state, onClose, onNavigate, onSelectClan }: Props) {
  const { t } = useI18n()
  const [data, setData] = useState<CreatureResponse | null>(null)
  const [snap, setSnap] = useState<'peek' | 'half' | 'full'>('half')
  const startYRef = useRef<number | null>(null)
  const snapRef = useRef(snap)
  useEffect(() => { snapRef.current = snap }, [snap])
  const handleDragStart = (e: React.TouchEvent) => {
    startYRef.current = e.touches[0].clientY
  }
  const handleDragEnd = (e: React.TouchEvent) => {
    if (startYRef.current === null) return
    const dy = e.changedTouches[0].clientY - startYRef.current
    startYRef.current = null
    const cur = snapRef.current
    if (dy < -30) {
      if (cur === 'peek') setSnap('half')
      else if (cur === 'half') setSnap('full')
    } else if (dy > 30) {
      if (cur === 'full') setSnap('half')
      else if (cur === 'half') setSnap('peek')
      else if (cur === 'peek') onClose()
    }
  }
  const cycleSnap = () => {
    setSnap((s) => (s === 'peek' ? 'half' : s === 'half' ? 'full' : 'peek'))
  }
  const [activeTab, setActiveTab] = useState<TabKey>(() => {
    try {
      const s = sessionStorage.getItem('insp-tab') as TabKey | null
      if (s && ['vitals','skills','lineage','chronicle'].includes(s)) return s
    } catch {}
    return 'vitals'
  })

  useEffect(() => {
    try { sessionStorage.setItem('insp-tab', activeTab) } catch {}
  }, [activeTab])

  useEffect(() => {
    let alive = true
    const load = () =>
      fetch(`/api/creature/${id}`)
        .then((r) => r.json())
        .then((d) => alive && setData(d))
        .catch(() => {})
    load()
    const t = setInterval(() => {
      if (document.hidden) return
      load()
    }, 2000)
    return () => {
      alive = false
      clearInterval(t)
    }
  }, [id])

  // Instant live entity from WebSocket state while full dossier is loading
  const liveEntity = state?.entities?.find((ent: any) => ent.id === id)
  const isCurrent = data?.entity?.id === id
  const e = isCurrent ? data.entity : (liveEntity || null)
  const fam = isCurrent ? data.family : undefined

  const statusChips: Array<{ text: string; cls: string }> = []
  if (e?.status === 'hungry') statusChips.push({ text: t('inspector.hungry'), cls: 'st-hungry' })
  if (e?.status === 'starving') statusChips.push({ text: t('inspector.starving'), cls: 'st-starving' })
  if (e?.infected) statusChips.push({ text: t('inspector.sick'), cls: 'st-sick' })
  if (e?.sleeping) statusChips.push({ text: t('inspector.asleep'), cls: 'st-asleep' })
  if ((e?.chill ?? 0) >= 12) statusChips.push({ text: t('inspector.chilled', { v: (e?.chill ?? 0).toFixed(1) }), cls: 'st-asleep' })
  if ((e?.scars ?? 0) > 0) statusChips.push({ text: `⚔ Veteran (${e?.scars} ${(e?.scars === 1 ? 'scar' : 'scars')})`, cls: 'st-starving' })

  const [arcCopied, setArcCopied] = useState(false)

  // BM-18: Named creature arc story prompt generator
  const copyCreatureStoryArc = async () => {
    if (!e) return
    const name = e.personal_name ? `"${e.personal_name}"` : `Creature #${id}`
    const caste = e.caste ?? 'Citizen'
    const clan = e.clan_name ?? (e.clan_id != null ? `Clan #${e.clan_id}` : 'Independent Realm')
    const events = (data?.events ?? []).slice()
    const birthEv = events.find((ev) => ev.type === 'birth')
    const deathEv = events.find((ev) => ev.type === 'death')
    const promotions = events.filter((ev) => ev.type === 'promotion')
    const kills = events.filter((ev) => ev.type === 'war' || ev.type === 'predation')
    const offspringCount = fam?.children?.length ?? 0

    const promptText = `# The Hero's Journey of ${name} (#${id})

## Writing Objective:
You are an epic bard in Flatland. Write a moving, dramatic character biography following the life, rise, trials, and legacy of this specific geometric creature.

## Character Dossier:
- **Identity**: ${name} #${id} ${e.glyph ?? ''} (${caste})
- **Status**: ${e.alive ? 'Currently Living' : 'Deceased †'}
- **Sex / Form**: ${e.shape === 'line' || e.sex === 'female' ? 'Woman (Razor-sharp line segment)' : `Man (${e.sides}-sided regular polygon)`}
- **Dynasty**: ${clan}
- **Generation**: Gen ${e.generation ?? 0}
- **Lifespan**: Age ${Math.round(e.age ?? 0)} (Max: ${Math.round(e.lifespan ?? 100)})
- **Offspring**: ${offspringCount} children
${birthEv ? `- **Origin**: Born to Mother #${(birthEv.payload as any)?.mother ?? '?'} and Father #${(birthEv.payload as any)?.father ?? '?'} at tick ${birthEv.tick}.` : ''}
${promotions.length > 0 ? `- **Ascent in Society**: Promoted ${promotions.length} time(s), rising to ${caste}.` : ''}
${kills.length > 0 ? `- **Martial Exploits**: Involved in ${kills.length} combat/predation engagements.` : ''}
${deathEv ? `- **Demise**: Died at tick ${deathEv.tick} due to ${deathEv.cause ?? 'unknown causes'}.` : ''}

## Chronicle Milestones:
${events.map((ev) => `- Tick ${ev.tick}: ${ev.type}${ev.caste ? ` (${ev.caste})` : ''}${ev.cause ? ` [cause: ${ev.cause}]` : ''}`).join('\n') || '- No major milestones recorded.'}

## Writing Instructions:
1. Portray the character's perspective within Abbott's rigid 2D geometric caste system.
2. Weave their personal relationships, trials against hunger or frost, battles against rival clans, and their eventual fate into a dramatic narrative arc.
`
    try {
      await navigator.clipboard.writeText(promptText)
      setArcCopied(true)
      setTimeout(() => setArcCopied(false), 2500)
    } catch {}
  }

  return (
    <aside className="inspector" data-snap={snap} onWheel={(e) => e.stopPropagation()}>
      <div
        className="inspector-handle"
        role="button"
        aria-label="drag handle"
        onClick={cycleSnap}
        onTouchStart={handleDragStart}
        onTouchEnd={handleDragEnd}
      />
      {/* Hero Header — compact geometric avatar */}
      <header className="insp-head" onTouchStart={handleDragStart} onTouchEnd={handleDragEnd}>
        <h2 style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap', fontSize: 14 }}>
          <span style={{ color: (e?.caste && CASTE_COLORS[e.caste]) || '#e6edf3' }}>{e?.personal_name ?? `${e?.caste ?? t('inspector.creature')}`} #{id}</span>
          {e?.title ? <span style={{ color: '#e3b341', fontSize: '0.85em', fontWeight: 600, background: 'rgba(227,179,65,0.12)', border: '1px solid #e3b341', borderRadius: 4, padding: '1px 5px' }}>{e.title}</span> : null}
          {e?.glyph ? <span title="soul-code glyph" style={{ fontSize: '0.9em' }}>{e.glyph}</span> : null}
        </h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {/* BM-18: Story Arc Prompt Copy Button */}
          <button
            type="button"
            className="chip"
            onClick={copyCreatureStoryArc}
            style={{
              background: arcCopied ? '#238636' : 'rgba(56, 139, 253, 0.15)',
              borderColor: arcCopied ? '#2ea043' : 'rgba(56, 139, 253, 0.4)',
              color: arcCopied ? '#fff' : '#58a6ff',
              cursor: 'pointer',
              fontWeight: 600,
              fontSize: 10.5,
              padding: '2px 7px',
            }}
            title="Generate and copy single-creature Story Arc narrative prompt"
          >
            {arcCopied ? '✓ Copied!' : '📖 Story Arc'}
          </button>
          <button type="button" className="insp-close-btn" onClick={onClose} aria-label={t('common.close')}>×</button>
        </div>
      </header>

      {e && (
        <div className="chip" style={{ fontSize: 11, opacity: 0.9, margin: '4px 0 6px', display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          <span style={{ background: CASTE_COLORS[e.caste ?? ''] ?? '#21262d', color: '#0d1117', padding: '1px 6px', borderRadius: 4, fontWeight: 700 }}>{e.caste}</span>
          <span>{e.shape === 'line' ? t('inspector.female') : t('inspector.male')} · {e.stage} · Gen {e.generation ?? 0}</span>
          {e.clan_id != null && e.clan_id > 0 ? (
            <button
              type="button"
              className="chip clan-link-chip"
              onClick={() => onSelectClan?.(e.clan_id!)}
              style={{
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 5,
                border: `1px solid ${e.clan_color ?? '#58a6ff'}`,
                background: 'rgba(33,38,45,0.85)',
                color: e.clan_color ?? '#58a6ff',
                borderRadius: 4,
                padding: '1px 6px',
                fontSize: 11,
                fontWeight: 600,
                lineHeight: 1.3,
              }}
              title={t('inspector.openClanDetails', { name: e.clan_name ?? `Clan ${e.clan_id}` })}
            >
              <span className="dot-inline" style={{ background: e.clan_color ?? '#8b949e', width: 6, height: 6, borderRadius: '50%' }} />
              <span>{e.clan_name ?? `Clan ${e.clan_id}`} {totemEmoji(e.clan_totem)}</span>
              <span style={{ fontSize: 9, opacity: 0.85 }}>↗</span>
            </button>
          ) : null}
        </div>
      )}

      {e && (
        <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start', minWidth: 0 }}>
          <div style={{ flex: 'none' }}>
            <CreatureAvatar e={e} />
          </div>
          <div style={{ flex: '1 1 0', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 4 }}>
            {statusChips.length > 0 && (
              <div className="status-row" style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {statusChips.map((s) => (
                  <span key={s.text} className={`status-chip ${s.cls}`} style={{ fontSize: 11, padding: '2px 6px', borderRadius: 4, background: '#161b22', border: '1px solid #30363d' }}>{s.text}</span>
                ))}
              </div>
            )}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4 }}>
              <div className="chip" style={{ background: '#161b22', border: '1px solid #30363d', padding: '6px 8px', borderRadius: 6, display: 'flex', flexDirection: 'column', gap: 1 }}>
                <span style={{ fontSize: 10, color: '#8b949e', textTransform: 'uppercase' }}>{t('inspector.energy')}</span>
                <span style={{ fontWeight: 700, color: '#d29922' }}>{Math.round(e.energy ?? 0)} / 100</span>
                <div className="insp-track" style={{ height: 3 }}><div className="insp-fill" style={{ width: `${Math.min(100, e.energy ?? 0)}%`, background: '#d29922' }} /></div>
              </div>
              <div className="chip" style={{ background: '#161b22', border: '1px solid #30363d', padding: '6px 8px', borderRadius: 6, display: 'flex', flexDirection: 'column', gap: 1 }}>
                <span style={{ fontSize: 10, color: '#8b949e', textTransform: 'uppercase' }}>{t('inspector.health')}</span>
                <span style={{ fontWeight: 700, color: '#3fb950' }}>{Math.round(e.health ?? 0)} / 100</span>
                <div className="insp-track" style={{ height: 3 }}><div className="insp-fill" style={{ width: `${Math.min(100, e.health ?? 0)}%`, background: '#3fb950' }} /></div>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
              {e.personality && <span className="chip" style={{ fontSize: 11, background: '#21262d', border: '1px solid #30363d', padding: '2px 6px' }}>🎭 {e.personality}</span>}
              {e.equipped_item && <span className="chip" style={{ fontSize: 11, background: '#21262d', border: '1px solid #30363d', padding: '2px 6px' }}>{e.equipped_item === 'spear' ? '⚔ spear' : e.equipped_item === 'crown' ? '👑 crown' : e.equipped_item === 'basket' ? `🧺 ${e.food_basket ?? 0}` : e.equipped_item === 'herb_poultice' ? '🌿 poultice' : e.equipped_item}</span>}
              {typeof e.chill === 'number' && e.chill > 0.5 && <span className="chip" style={{ color: '#79c0ff', fontSize: 11 }}>❄ {e.chill.toFixed(1)}</span>}
              {typeof e.scars === 'number' && e.scars > 0 && <span className="chip" style={{ color: '#ff7b72', background: '#21262d', border: '1px solid #da3633', fontSize: 11 }}>⚔ {e.scars} {e.scars === 1 ? 'scar' : 'scars'}</span>}
            </div>
          </div>
        </div>
      )}

      {!e && data && <p className="god-note">{t('inspector.noLongerLiving')}</p>}

      {/* 4-Tab Navigation */}
      <div className="insp-tabs">
        {(
          [
            {
              key: 'vitals',
              icon: '🧬',
              short: t('inspector.tabVitalsShort') !== 'inspector.tabVitalsShort' ? t('inspector.tabVitalsShort') : 'Vitals',
              full: t('inspector.tabVitals') !== 'inspector.tabVitals' ? t('inspector.tabVitals') : 'Vitals & Morph',
            },
            {
              key: 'skills',
              icon: '⚡',
              short: t('inspector.tabSkillsShort') !== 'inspector.tabSkillsShort' ? t('inspector.tabSkillsShort') : 'Skills',
              full: t('inspector.tabSkills') !== 'inspector.tabSkills' ? t('inspector.tabSkills') : 'Skills & Neural',
            },
            {
              key: 'lineage',
              icon: '🌳',
              short: t('inspector.tabLineageShort') !== 'inspector.tabLineageShort' ? t('inspector.tabLineageShort') : 'Lineage',
              full: t('inspector.tabLineage') !== 'inspector.tabLineage' ? t('inspector.tabLineage') : 'Lineage & Kin',
            },
            {
              key: 'chronicle',
              icon: '📜',
              short: t('inspector.tabChronicleShort') !== 'inspector.tabChronicleShort' ? t('inspector.tabChronicleShort') : 'Chronicle',
              full: t('inspector.tabChronicle') !== 'inspector.tabChronicle' ? t('inspector.tabChronicle') : 'Life Chronicle',
              count: data?.events?.length,
            },
          ] as Array<{ key: TabKey; icon: string; short: string; full: string; count?: number }>
        ).map((tab) => (
          <button
            key={tab.key}
            type="button"
            className={activeTab === tab.key ? 'active' : ''}
            onClick={() => setActiveTab(tab.key)}
            title={tab.full}
            aria-selected={activeTab === tab.key}
          >
            <span className="tab-icon">{tab.icon}</span>
            <span className="tab-label">{tab.short}</span>
            {typeof tab.count === 'number' && tab.count > 0 && (
              <span className="tab-badge">{tab.count}</span>
            )}
          </button>
        ))}
      </div>

      {e && activeTab === 'vitals' && (
        <>
          <div className="insp-grid insp-2col">
            <span className="chip" style={{ justifyContent: 'space-between' }}>
              <span>{t('inspector.age')}</span>
              <b>{e.age ?? 0} / {Math.round(e.lifespan ?? 0)}</b>
            </span>
            <span className="chip" style={{ justifyContent: 'space-between' }}>
              <span>{t('inspector.meals')}</span>
              <b>{e.meals ?? 0}</b>
            </span>
            {typeof e.body_temp === 'number' && (
              <span className="chip" style={{ justifyContent: 'space-between' }}>
                <span>🌡️ {t('inspector.bodyTemp')}</span>
                <b>{e.body_temp.toFixed(1)}°C</b>
              </span>
            )}
            {typeof e.irregularity === 'number' && e.irregularity > 0 && (
              <span className="chip" style={{ color: '#f85149', justifyContent: 'space-between' }}>
                <span>{t('inspector.irregularity')}</span>
                <b>{e.irregularity}</b>
              </span>
            )}
            {e.trait && (
              <span className="chip" style={{ justifyContent: 'space-between' }}>
                <span>{t('inspector.traitLabel')}</span>
                <b>{e.trait === 'greedy' ? '⬔' : e.trait === 'peaceful' ? '◯' : e.trait === 'paranoid' ? '⬥' : e.trait === 'bold' ? '▲' : '•'} {e.trait}</b>
              </span>
            )}
            {(e as any).archetype && (
              <span
                className="chip"
                style={{
                  gridColumn: '1 / -1',
                  background: (e as any).archetype === 'Apex Hunter' ? 'rgba(255,123,114,0.18)' : (e as any).archetype === 'Nocturnal Forager' ? 'rgba(121,192,255,0.18)' : (e as any).archetype === 'Granary Courier' ? 'rgba(63,185,80,0.16)' : 'rgba(210,168,255,0.16)',
                  border: `1px solid ${(e as any).archetype === 'Apex Hunter' ? '#ff7b72' : (e as any).archetype === 'Nocturnal Forager' ? '#79c0ff' : (e as any).archetype === 'Granary Courier' ? '#3fb950' : '#d2a8ff'}`,
                  color: '#e6edf3',
                  fontWeight: 700,
                }}
              >
                {(e as any).archetype === 'Apex Hunter' ? '⚔' : (e as any).archetype === 'Nocturnal Forager' ? '🌙' : (e as any).archetype === 'Granary Courier' ? '🧺' : '🛡️'} {(e as any).archetype}
              </span>
            )}
          </div>
          {/* §BG-9 Polar Radar & §BG-10 Biomech HUD */}
          <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 8, minWidth: 0 }}>
            <PolarRadar e={e} />
            <BiomechHUD e={e} />
            <div className="insp-2col" style={{ fontSize: 11 }}>
              <span className="chip" style={{ justifyContent: 'space-between', background: '#161b22' }}>
                <span>{t('inspector.sidesLabel')}</span>
                <b>{e.sides} {(e as any).morph_k && (e as any).morph_k !== e.sides ? <span style={{ color: '#d2a8ff' }}>→ {(e as any).morph_k}</span> : null}</b>
              </span>
              <span className="chip" style={{ justifyContent: 'space-between', background: '#161b22' }}>
                <span>{t('inspector.speed')}</span>
                <b>{typeof (e as any).speed === 'number' ? (e as any).speed.toFixed(2) : '1.00'}</b>
              </span>
              {typeof e.radius === 'number' && (
                <span className="chip" style={{ justifyContent: 'space-between', background: '#161b22' }}>
                  <span>{t('inspector.radius')}</span>
                  <b>{e.radius.toFixed(2)}</b>
                </span>
              )}
              {typeof (e as any).iso_angle === 'number' && (e as any).iso_angle > 0 && (
                <span className="chip" style={{ justifyContent: 'space-between', background: '#161b22' }}>
                  <span>{t('inspector.apexAngle')}</span>
                  <b>{(e as any).iso_angle.toFixed(1)}°</b>
                </span>
              )}
            </div>
          </div>
        </>
      )}

      {e && activeTab === 'skills' && (
        <>
          {/* 2x2 circular mastery badge grid */}
          <div className="insp-2col" style={{ marginBottom: 8, flexShrink: 0 }}>
            {[
              { name: t('inspector.farming'), key: 'farming', icon: '🌾', color: '#3fb950', max: 30 },
              { name: t('inspector.combat'), key: 'combat', icon: '⚔️', max: 30, color: '#ff7b72' },
              { name: t('inspector.foraging'), key: 'foraging', icon: '🦴', max: 30, color: '#d2a8ff' },
              { name: t('inspector.healing'), key: 'healing', icon: '🌿', max: 30, color: '#79c0ff' },
            ].map((sk) => {
              const xp = (e.skills as any)?.[sk.key] ?? 0
              const level = xp >= 30 ? 3 : xp >= 12 ? 2 : xp >= 4 ? 1 : 0
              const lvlName = level === 3 ? t('inspector.master') : level === 2 ? t('inspector.adept') : level === 1 ? t('inspector.novice') : t('inspector.unranked')
              const pct = Math.min(100, (xp / sk.max) * 100)
              return (
                <div key={sk.key} style={{ background: '#161b22', border: `1px solid ${sk.color}44`, borderRadius: 10, padding: '10px 8px', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
                  <div style={{ width: 52, height: 52, borderRadius: '50%', border: `3px solid ${sk.color}`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18, position: 'relative', background: `${sk.color}14` }}>
                    <span>{sk.icon}</span>
                    <div style={{ position: 'absolute', inset: -3, borderRadius: '50%', border: `3px solid transparent`, borderTopColor: sk.color, transform: `rotate(${pct * 3.6}deg)`, opacity: 0.9 }} />
                  </div>
                  <span style={{ fontWeight: 700, color: '#e6edf3', fontSize: 12 }}>{sk.name}</span>
                  <span style={{ fontSize: 11, color: sk.color, fontWeight: 600 }}>{lvlName} · {xp.toFixed(1)}/{sk.max}</span>
                </div>
              )
            })}
          </div>
          {/* Sensory Raycasting */}
          <div style={{ marginBottom: 8, minWidth: 0 }}>
            <SensoryRayCard e={liveEntity ? { ...e, ...liveEntity } : e} state={state} />
          </div>
          {/* Neural radar compact gauges */}
          <div style={{ background: '#0d1117', border: '1px solid #21262d', borderRadius: 8, padding: '8px 10px', flexShrink: 0 }}>
            <div style={{ fontSize: 11, color: '#8b949e', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 6, display: 'flex', justifyContent: 'space-between' }}>
              <span>🧠 Neural Engine (BA)</span>
              <span style={{ color: '#58a6ff', textTransform: 'none' }}>hidden {e.nn_hidden?.toFixed(3) ?? '—'}</span>
            </div>
            {e.nn_hidden == null && !e.nn_outputs ? (
              <div className="chip" style={{ background: '#161b22', border: '1px solid #30363d', padding: '8px', borderRadius: 6, fontSize: 12, color: '#8b949e' }}>{t('inspector.gatheringNeural')}</div>
            ) : (
              <div className="insp-2col">
                {[
                  { label: 'Thrust', idx: 0, color: '#f0883e' },
                  { label: 'Steer', idx: 1, color: '#79c0ff' },
                  { label: 'Interact', idx: 2, color: '#ff7b72' },
                  { label: 'Social', idx: 3, color: '#a371f7' },
                  { label: 'Vocal amp', idx: 4, color: '#e3b341' },
                  { label: 'Vocal freq', idx: 5, color: '#bc8cff' },
                  { label: 'Recurrent', idx: 6, color: '#58a6ff' },
                ].map((o) => {
                  const v = e.nn_outputs?.[o.idx] ?? 0
                  const isSig = o.idx === 0 || o.idx === 4
                  const pct = isSig ? Math.max(0, Math.min(100, v * 100)) : Math.max(0, Math.min(100, (v + 1) * 50))
                  return (
                    <div key={o.label} style={{ background: '#161b22', border: '1px solid #21262d', borderRadius: 6, padding: '4px 6px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#8b949e' }}><span>{o.label}</span><span style={{ color: o.color, fontFamily: 'ui-monospace' }}>{v.toFixed(2)}</span></div>
                      <div className="insp-track" style={{ height: 3, marginTop: 2 }}><div className="insp-fill" style={{ width: `${pct}%`, background: o.color }} /></div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
          {/* BH-10 heatmap */}
          <NNHeatmap e={e} />
        </>
      )}

      {e && activeTab === 'lineage' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, minWidth: 0 }}>
          <div className="insp-2col">
            <KinCardView kin={fam?.mother ?? null} role={t('inspector.mother')} onNavigate={onNavigate} />
            <KinCardView kin={fam?.father ?? null} role={t('inspector.father')} onNavigate={onNavigate} />
          </div>
          <div style={{ textAlign: 'center', background: '#1f6feb', color: '#fff', borderRadius: 6, padding: '6px 8px', fontWeight: 700, fontSize: 12, border: `1px solid ${e.clan_color ?? '#30363d'}` }}>
            #{id} · {t('inspector.currentSubject')} · {e.caste} {e.glyph ?? ''} Gen {e.generation ?? 0}
          </div>
          <div style={{ background: '#161b22', border: '1px solid #21262d', borderRadius: 8, padding: '8px 10px' }}>
            <div style={{ fontSize: 11, color: '#8b949e', textTransform: 'uppercase', marginBottom: 6 }}>{t('inspector.children') ?? 'Offspring'} ({fam?.children.length ?? 0})</div>
            {(fam?.children ?? []).length === 0 ? (
              <span className="chip" style={{ fontSize: 12 }}>{t('inspector.noOffspring')}</span>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 6, maxHeight: 220, overflowY: 'auto', minWidth: 0 }}>
                {fam!.children.map((k) => (
                  <KinCardView key={k.id} kin={k} role={t('inspector.child')} onNavigate={onNavigate} />
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'chronicle' && (
        <ul className="insp-events" style={{ maxHeight: 280, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 2 }}>
          {(data?.events ?? []).slice().reverse().map((ev) => (
            <li key={`${ev.tick}:${ev.type}`} className={`ev-${ev.type}`} style={{ background: '#161b22', border: '1px solid #21262d', borderRadius: 6, padding: '6px 8px', fontSize: 11, display: 'flex', justifyContent: 'space-between', gap: 6 }}>
              <span><b>{ev.type}</b> {ev.cause ? `· ${ev.cause}` : ''} {ev.caste ? `· ${ev.caste}` : ''}</span>
              <span style={{ color: '#8b949e', whiteSpace: 'nowrap' }}>tick {ev.tick}</span>
            </li>
          ))}
          {(data?.events?.length ?? 0) === 0 && <li className="chip">{t('inspector.nothingRecorded')}</li>}
        </ul>
      )}
    </aside>
  )
}
