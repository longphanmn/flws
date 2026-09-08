import type { EntityState } from '../types'
import { CASTE_COLORS } from '../render/renderCore'

export { CASTE_COLORS }

export const SIDES_COLORS: Record<number, string> = {
  2: CASTE_COLORS.Woman || '#ff9bce',
  3: CASTE_COLORS.Soldier || '#ff7b72',
  4: CASTE_COLORS.Gentleman || '#ffa657',
  5: CASTE_COLORS.Professional || '#d2a8ff',
  6: '#79c0ff',
  7: '#bc8cff',
  8: CASTE_COLORS.Noble || '#79c0ff',
  9: '#bc8cff',
  10: '#7ee787',
  24: CASTE_COLORS.Priest || '#e6edf3',
}

export interface CreatureAvatarProps {
  e?: Partial<EntityState> | null
  sides?: number
  shape?: string
  caste?: string
  color?: string
  clanColor?: string
  glyph?: string
  stage?: string
  scaleJitter?: number
  angleJitter?: number
  trait?: string
  infected?: boolean
  status?: string
  chill?: number
  size?: number
}

function pseudoRand(seed: number, i: number): number {
  const x = Math.sin(seed * 127.1 + i * 311.7) * 43758.5453
  return x - Math.floor(x)
}

export function CreatureAvatar({
  e,
  sides: propSides,
  shape: propShape,
  caste: propCaste,
  color: propColor,
  clanColor: propClanColor,
  glyph: propGlyph,
  stage: propStage,
  scaleJitter: propScaleJitter,
  angleJitter: propAngleJitter,
  trait: propTrait,
  infected: propInfected,
  status: propStatus,
  chill: propChill,
  size = 76,
}: CreatureAvatarProps) {
  const caste = e?.caste ?? propCaste
  const sidesRaw = (e as any)?.morph_k ?? e?.sides ?? propSides ?? 4
  const sidesClamped = Math.max(3, Math.min(24, sidesRaw))
  const sides = sidesClamped
  const shape = e?.shape ?? propShape ?? (sides === 2 ? 'line' : 'polygon')
  const isLine = shape === 'line' || sides === 2 || (e as any)?.shape === 'line'
  const isPriest = sides >= 24

  const color = propColor ?? (caste && CASTE_COLORS[caste]) ?? (isLine ? CASTE_COLORS.Woman : CASTE_COLORS[caste || ''] || '#8b949e')
  const clanColor = e?.clan_color ?? propClanColor ?? '#30363d'
  const glyph = e?.glyph ?? propGlyph
  const stage = e?.stage ?? propStage ?? 'adult'
  const scaleJitter = (e as any)?.scale_jitter ?? propScaleJitter ?? 1
  const angleJitter = (e as any)?.angle_jitter ?? propAngleJitter ?? 0
  const trait = (e as any)?.trait ?? propTrait
  const infected = e?.infected ?? propInfected
  const status = e?.status ?? propStatus
  const chill = (e as any)?.chill ?? propChill ?? 0

  const archetype: string | undefined = (e as any)?.archetype
  const irregularity: number = (e as any)?.irregularity ?? 0
  const isoAngle: number | undefined = (e as any)?.iso_angle
  const morphTraits: number[] | undefined = (e as any)?.morph_traits
  const generation: number = (e as any)?.generation ?? 0
  const idSeed: number = (e as any)?.id ?? 1

  const cx = 40
  const cy = 40
  const r = 18 * scaleJitter * (stage === 'infant' ? 0.55 : stage === 'juvenile' ? 0.8 : 1)

  // Derive morph metrics for phenotypes
  const area = morphTraits && morphTraits.length > 0 ? morphTraits[0] : 2.0
  const izz = morphTraits && morphTraits.length > 2 ? morphTraits[2] : 0.3
  const thetaMin = morphTraits && morphTraits.length > 3 ? morphTraits[3] : (sides >= 3 ? (sides - 2) * Math.PI / sides : Math.PI / 3)
  const dmult = morphTraits && morphTraits.length > 5 ? morphTraits[5] : Math.max(0, (Math.cos(thetaMin) - 0.5) / 0.5)
  const isSoldierRazor = caste === 'Soldier' && sides === 3 && typeof isoAngle === 'number' && isoAngle < 59.9
  const hasArmor = (izz > 0.65 || area > 3.0) && !isLine && !isPriest
  const specBase = Math.max(irregularity * 1.8, generation > 40 ? Math.max(0, 1 - (1 - (generation - 15) / 250)) : 0)
  const specIntensity = specBase * ((sides >= 7 || irregularity > 0.25) ? 1 : 0.5)
  const hasSpeciation = specIntensity > 0.42 && !isLine
  const hasGlint = dmult > 0.18 && !isLine
  const hasNucleus = stage === 'elder' && generation >= 10 && !isLine

  // BK-2 & BK-4 to BK-7 visual indicators
  const hasHalo = generation >= 10
  const hasDynasty = generation >= 25
  const hasCorona = generation >= 50
  const hasGenesis = generation <= 2
  const hasAberrantAura = irregularity > 0.18
  const hasCrystallinePatina = generation >= 15
  const scarsCount: number = (e as any)?.scars ?? 0

  // Build main polygon points
  let pointsStr: string | null = null
  let womanPointsStr: string | null = null
  let womanHaloPointsStr: string | null = null
  let womanAuraPointsStr: string | null = null
  let glintPos: [number, number] | null = null
  let ptsArray: Array<[number, number]> = []

  if (isLine) {
    // BG-3 variable thickness needle diamond
    const len = r * 1.3
    const perimFactor = morphTraits && morphTraits[1] ? Math.max(0.7, Math.min(1.9, morphTraits[1] / 5.657)) : 1
    const wMid = Math.max(1.2, r * 0.30 * perimFactor * (0.85 + irregularity * 0.9))
    const ax = Math.cos(angleJitter), ay = Math.sin(angleJitter)
    const px = -ay, py = ax
    const fx = cx + ax * len, fy = cy + ay * len
    const bx = cx - ax * len * 0.92, by = cy - ay * len * 0.92
    const tx = cx + px * wMid, ty = cy + py * wMid
    const bx2 = cx - px * wMid, by2 = cy - py * wMid
    womanPointsStr = `${fx},${fy} ${tx},${ty} ${bx},${by} ${bx2},${by2}`
    if (hasHalo) {
      const hLen = len * 0.6, hMid = wMid * 0.6
      womanHaloPointsStr = `${cx + ax * hLen},${cy + ay * hLen} ${cx + px * hMid},${cy + py * hMid} ${cx - ax * hLen * 0.9},${cy - ay * hLen * 0.9} ${cx - px * hMid},${cy - py * hMid}`
    }
    if (hasAberrantAura) {
      const aLen = len * 1.15, aMid = wMid * 1.45
      womanAuraPointsStr = `${cx + ax * aLen},${cy + ay * aLen} ${cx + px * aMid},${cy + py * aMid} ${cx - ax * aLen * 0.94},${cy - ay * aLen * 0.94} ${cx - px * aMid},${cy - py * aMid}`
    }
  } else if (isPriest) {
    // circle handled separately
    if (irregularity > 0.08) {
      const pts: Array<[number, number]> = []
      for (let i = 0; i < sides; i++) {
        const aJ = (pseudoRand(idSeed, i * 2) - 0.5) * Math.min(0.3, irregularity) * 0.65
        const rJ = 1 + (pseudoRand(idSeed, i * 2 + 1) - 0.5) * Math.min(0.3, irregularity) * 0.5
        const a = (i / sides) * Math.PI * 2 - Math.PI / 2 + angleJitter + aJ
        const rr = r * rJ
        pts.push([cx + Math.cos(a) * rr, cy + Math.sin(a) * rr])
      }
      ptsArray = pts
      pointsStr = pts.map(([x, y]) => `${x},${y}`).join(' ')
      // glint from sharpest
      if (hasGlint) {
        let best = 999, bx = pts[0][0], by = pts[0][1]
        for (let i = 0; i < pts.length; i++) {
          const im1 = (i - 1 + pts.length) % pts.length, ip1 = (i + 1) % pts.length
          const ux = pts[im1][0] - pts[i][0], uy = pts[im1][1] - pts[i][1]
          const vx = pts[ip1][0] - pts[i][0], vy = pts[ip1][1] - pts[i][1]
          const nu = Math.hypot(ux, uy), nv = Math.hypot(vx, vy)
          if (nu < 1e-6 || nv < 1e-6) continue
          const av = Math.acos(Math.max(-1, Math.min(1, (ux * vx + uy * vy) / (nu * nv))))
          if (av < best) { best = av; bx = pts[i][0]; by = pts[i][1] }
        }
        glintPos = [bx, by]
      }
    }
  } else if (isSoldierRazor) {
    const theta = Math.max(8, Math.min(59.8, isoAngle!)) * Math.PI / 180
    const needleMult = (typeof isoAngle === 'number' && isoAngle < 30) ? 1.0 + ((30 - isoAngle) / 30) * 0.45 : 1.0
    const xr = r * 1.05 * needleMult, xb = r * 0.55
    const dx = xr + xb
    const yb = dx * Math.tan(theta / 2)
    const local: Array<[number, number]> = [
      [xr, 0],
      [-xb, yb],
      [-xb, -yb],
    ]
    const ca = Math.cos(angleJitter), sa = Math.sin(angleJitter)
    const pts = local.map(([lx, ly]) => [cx + lx * ca - ly * sa, cy + lx * sa + ly * ca] as [number, number])
    ptsArray = pts
    pointsStr = pts.map(([x, y]) => `${x},${y}`).join(' ')
    if (hasGlint) glintPos = pts[0]
  } else {
    // BG-2 mutated polygon & BG-4 topological aberration & BK-3 jagged spires
    const useMutated = irregularity > 0.02
    const pts: Array<[number, number]> = []
    if (useMutated) {
      for (let i = 0; i < sides; i++) {
        const aJ = (pseudoRand(idSeed, i * 2) - 0.5) * irregularity * 0.65
        let rJ = 1 + (pseudoRand(idSeed, i * 2 + 1) - 0.5) * irregularity * 0.9
        if (irregularity > 0.15 && (i % 2 === 0)) {
          rJ += (pseudoRand(idSeed, i * 5 + 3) > 0.45 ? 1 : -0.25) * irregularity * 0.45
        }
        const a = (i / sides) * Math.PI * 2 - Math.PI / 2 + angleJitter + aJ
        const rr = r * rJ
        pts.push([cx + Math.cos(a) * rr, cy + Math.sin(a) * rr])
      }
    } else {
      for (let i = 0; i < sides; i++) {
        const a = (i / sides) * Math.PI * 2 - Math.PI / 2 + angleJitter
        pts.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r])
      }
    }
    ptsArray = pts
    pointsStr = pts.map(([x, y]) => `${x},${y}`).join(' ')
    if (hasGlint) {
      let best = 999, bx = pts[0][0], by = pts[0][1]
      for (let i = 0; i < pts.length; i++) {
        const im1 = (i - 1 + pts.length) % pts.length, ip1 = (i + 1) % pts.length
        const ux = pts[im1][0] - pts[i][0], uy = pts[im1][1] - pts[i][1]
        const vx = pts[ip1][0] - pts[i][0], vy = pts[ip1][1] - pts[i][1]
        const nu = Math.hypot(ux, uy), nv = Math.hypot(vx, vy)
        if (nu < 1e-6 || nv < 1e-6) continue
        const av = Math.acos(Math.max(-1, Math.min(1, (ux * vx + uy * vy) / (nu * nv))))
        if (av < best) { best = av; bx = pts[i][0]; by = pts[i][1] }
      }
      glintPos = [bx, by]
    }
  }

  // Lineage halo inner points
  let haloPointsStr: string | null = null
  if (hasHalo && ptsArray.length) {
    const innerH = 0.62
    haloPointsStr = ptsArray.map(([x, y]) => {
      const dx = x - cx, dy = y - cy
      return `${cx + dx * innerH},${cy + dy * innerH}`
    }).join(' ')
  }

  // Aberrant aura outer points
  let aberrantAuraPointsStr: string | null = null
  if (hasAberrantAura && ptsArray.length) {
    const auraMult = 1.18
    aberrantAuraPointsStr = ptsArray.map(([x, y]) => {
      const dx = x - cx, dy = y - cy
      return `${cx + dx * auraMult},${cy + dy * auraMult}`
    }).join(' ')
  }

  // Celestial Corona 8 radiating rays
  const coronaRays: Array<{ x1: number; y1: number; x2: number; y2: number }> = []
  if (hasCorona) {
    for (let k = 0; k < 8; k++) {
      const a = angleJitter + (k / 8) * Math.PI * 2
      const r1 = r * 1.08
      const r2 = r * (k % 2 === 0 ? 1.45 : 1.25)
      coronaRays.push({
        x1: cx + Math.cos(a) * r1,
        y1: cy + Math.sin(a) * r1,
        x2: cx + Math.cos(a) * r2,
        y2: cy + Math.sin(a) * r2,
      })
    }
  }

  // Veteran battle scars
  const scarLines: Array<{ x1: number; y1: number; x2: number; y2: number }> = []
  if (scarsCount > 0) {
    const nScars = Math.min(4, scarsCount)
    for (let k = 0; k < nScars; k++) {
      const sAng = angleJitter + (k * 1.25) + 0.6
      const sx = cx + Math.cos(sAng) * r * 0.65
      const sy = cy + Math.sin(sAng) * r * 0.65
      const pLen = 4.2
      const px = -Math.sin(sAng) * pLen
      const py = Math.cos(sAng) * pLen
      scarLines.push({ x1: sx - px, y1: sy - py, x2: sx + px, y2: sy + py })
    }
  }

  // Speciation offset points (chromatic)
  let specPointsA: string | null = null
  let specPointsB: string | null = null
  if (hasSpeciation && ptsArray.length) {
    const offA: Array<[number, number]> = ptsArray.map(([x, y]) => [x + 0.9, y + 0.6] as [number, number])
    const offB: Array<[number, number]> = ptsArray.map(([x, y]) => [x - 0.8, y - 0.5] as [number, number])
    specPointsA = offA.map(([x, y]) => `${x},${y}`).join(' ')
    specPointsB = offB.map(([x, y]) => `${x},${y}`).join(' ')
  }

  // Armor inner polygon
  let armorPointsStr: string | null = null
  if (hasArmor && ptsArray.length) {
    const innerR = 0.78
    const cpts: Array<[number, number]> = ptsArray.map(([x, y]) => {
      const dx = x - cx, dy = y - cy
      return [cx + dx * innerR, cy + dy * innerR] as [number, number]
    })
    armorPointsStr = cpts.map(([x, y]) => `${x},${y}`).join(' ')
  }

  // Nucleus inner polygon
  let nucleusPointsStr: string | null = null
  if (hasNucleus && ptsArray.length) {
    const inner = 0.38
    const cpts: Array<[number, number]> = ptsArray.map(([x, y]) => {
      const dx = x - cx, dy = y - cy
      return [cx + dx * inner, cy + dy * inner] as [number, number]
    })
    nucleusPointsStr = cpts.map(([x, y]) => `${x},${y}`).join(' ')
  }

  // Crystalline core patina polygon
  let patinaPointsStr: string | null = null
  if (hasCrystallinePatina && ptsArray.length) {
    const inner = 0.42
    patinaPointsStr = ptsArray.map(([x, y]) => {
      const dx = x - cx, dy = y - cy
      return `${cx + dx * inner},${cy + dy * inner}`
    }).join(' ')
  }

  return (
    <div style={{ display: 'inline-flex', justifyContent: 'center', alignItems: 'center' }}>
      <svg
        width={size}
        height={size}
        viewBox="0 0 80 80"
        style={{
          background: '#161b22',
          borderRadius: 8,
          border: `1px solid ${clanColor}`,
        }}
      >
        {clanColor && <circle cx={cx} cy={cy} r={r + 6} fill="none" stroke={clanColor} strokeWidth={1.2} opacity={0.9} />}
        {/* §BK-2 Celestial Corona 8 radiating rays for Gen 50+ */}
        {coronaRays.map((ray, i) => (
          <line key={i} x1={ray.x1} y1={ray.y1} x2={ray.x2} y2={ray.y2} stroke="#fde047" strokeWidth={0.9} opacity={0.85} strokeLinecap="round" />
        ))}
        {isLine ? (
          <>
            {womanAuraPointsStr && (
              <polygon points={womanAuraPointsStr} fill="none" stroke={irregularity > 0.28 ? '#f43f5e' : '#a855f7'} strokeWidth={0.9} opacity={0.65} strokeLinejoin="round" />
            )}
            <polygon points={womanPointsStr!} fill={color} fillOpacity={0.22} stroke={color} strokeWidth={1.1} strokeLinejoin="round" />
            {womanHaloPointsStr && (
              <polygon points={womanHaloPointsStr} fill="none" stroke="#e2e8f0" strokeWidth={0.6} opacity={0.5} strokeLinejoin="round" />
            )}
          </>
        ) : isPriest ? (
          pointsStr ? (
            <>
              {aberrantAuraPointsStr && (
                <polygon points={aberrantAuraPointsStr} fill="none" stroke={irregularity > 0.28 ? '#f43f5e' : '#a855f7'} strokeWidth={1.0} opacity={0.65} strokeLinejoin="round" />
              )}
              <polygon points={pointsStr} fill={color} fillOpacity={0.22} stroke={color} strokeWidth={1.2} strokeLinejoin="round" />
              {haloPointsStr && (
                <polygon points={haloPointsStr} fill="none" stroke="#e2e8f0" strokeWidth={0.7} opacity={0.5} strokeLinejoin="round" />
              )}
              {hasArmor && <circle cx={cx} cy={cy} r={r * 0.78} fill={color} fillOpacity={0.10} stroke={color} strokeWidth={0.9} opacity={0.6} />}
            </>
          ) : (
            <>
              {hasAberrantAura && (
                <circle cx={cx} cy={cy} r={r * 1.18} fill="none" stroke={irregularity > 0.28 ? '#f43f5e' : '#a855f7'} strokeWidth={1.0} opacity={0.65} />
              )}
              <circle cx={cx} cy={cy} r={r} fill={color} fillOpacity={0.22} stroke={color} strokeWidth={1.2} />
              {hasHalo && (
                <circle cx={cx} cy={cy} r={r * 0.62} fill="none" stroke="#e2e8f0" strokeWidth={0.7} opacity={0.5} />
              )}
            </>
          )
        ) : (
          <>
            {aberrantAuraPointsStr && (
              <polygon points={aberrantAuraPointsStr} fill="none" stroke={irregularity > 0.28 ? '#f43f5e' : '#a855f7'} strokeWidth={1.0} opacity={0.65} strokeLinejoin="round" />
            )}
            {hasSpeciation && specPointsA && specPointsB && (
              <>
                <polygon points={specPointsA} fill="none" stroke="#d2a8ff" strokeWidth={0.7} opacity={0.45 * Math.min(1, specIntensity)} strokeLinejoin="round" />
                <polygon points={specPointsB} fill="none" stroke="#79c0ff" strokeWidth={0.7} opacity={0.38 * Math.min(1, specIntensity)} strokeLinejoin="round" />
              </>
            )}
            <polygon points={pointsStr!} fill={color} fillOpacity={hasArmor ? 0.30 : 0.22} stroke={color} strokeWidth={hasArmor ? 1.6 : 1.2} strokeLinejoin="round" />
            {haloPointsStr && (
              <polygon points={haloPointsStr} fill="none" stroke="#e2e8f0" strokeWidth={0.7} opacity={0.5} strokeLinejoin="round" />
            )}
            {armorPointsStr && (
              <polygon points={armorPointsStr} fill={color} fillOpacity={0.11} stroke={color} strokeWidth={0.9} opacity={0.55} strokeLinejoin="round" />
            )}
            {hasGlint && glintPos && (
              <g>
                <circle cx={glintPos[0]} cy={glintPos[1]} r={1.6 + dmult * 1.2} fill="#ffe08a" opacity={0.9} />
                <circle cx={glintPos[0]} cy={glintPos[1]} r={0.55} fill="#ffffff" opacity={0.95} />
              </g>
            )}
            {/* §BK-5 Razor needle piercing glint */}
            {isSoldierRazor && typeof isoAngle === 'number' && isoAngle < 30 && ptsArray.length > 0 && (
              <g>
                <line x1={ptsArray[0][0] - Math.cos(angleJitter) * 2} y1={ptsArray[0][1] - Math.sin(angleJitter) * 2} x2={ptsArray[0][0] + Math.cos(angleJitter) * 1.5} y2={ptsArray[0][1] + Math.sin(angleJitter) * 1.5} stroke="#ef4444" strokeWidth={0.9} />
                <circle cx={ptsArray[0][0]} cy={ptsArray[0][1]} r={1.1} fill="#ffffff" />
              </g>
            )}
            {nucleusPointsStr && (
              <g>
                <polygon points={nucleusPointsStr} fill={color} fillOpacity={0.18} stroke="#e6edf3" strokeWidth={0.7} opacity={0.6} strokeLinejoin="round" />
                {glyph && (
                  <text x={cx} y={cy + 1} textAnchor="middle" dominantBaseline="middle" fontSize={r * 0.42} fill="#e6edf3" style={{ fontFamily: 'ui-monospace, monospace' }}>
                    {glyph}
                  </text>
                )}
              </g>
            )}
          </>
        )}

        {/* §BK-4 Ancestral Crystalline Core Patina */}
        {hasCrystallinePatina && (
          patinaPointsStr ? (
            <polygon points={patinaPointsStr} fill={generation >= 50 ? 'rgba(254, 240, 138, 0.40)' : generation >= 25 ? 'rgba(245, 158, 11, 0.32)' : 'rgba(148, 163, 184, 0.25)'} stroke={generation >= 50 ? '#fde047' : generation >= 25 ? '#fbbf24' : '#cbd5e1'} strokeWidth={0.6} strokeLinejoin="round" />
          ) : (
            <circle cx={cx} cy={cy} r={Math.max(3.5, r * 0.4)} fill={generation >= 50 ? 'rgba(254, 240, 138, 0.40)' : generation >= 25 ? 'rgba(245, 158, 11, 0.32)' : 'rgba(148, 163, 184, 0.25)'} stroke={generation >= 50 ? '#fde047' : generation >= 25 ? '#fbbf24' : '#cbd5e1'} strokeWidth={0.6} />
          )
        )}

        {/* §BK-2 Double Concentric Dynasty Ring (Gen 25+) */}
        {hasDynasty && (
          <circle cx={cx} cy={cy} r={Math.max(4, r * 0.36)} fill="none" stroke="#facc15" strokeWidth={0.8} opacity={0.7} />
        )}

        {/* §BK-1 Genesis Spark for Primordials (Gen 0–2) */}
        {hasGenesis && (
          <g>
            <circle cx={cx} cy={cy} r={5.5} fill={generation === 0 ? 'rgba(56, 189, 248, 0.35)' : 'rgba(56, 189, 248, 0.22)'} />
            <path
              d={`M ${cx} ${cy - 4.2} L ${cx + 1.2} ${cy - 1.2} L ${cx + 4.2} ${cy} L ${cx + 1.2} ${cy + 1.2} L ${cx} ${cy + 4.2} L ${cx - 1.2} ${cy + 1.2} L ${cx - 4.2} ${cy} L ${cx - 1.2} ${cy - 1.2} Z`}
              fill={generation === 0 ? '#ffffff' : '#e0f2fe'}
              stroke="#38bdf8"
              strokeWidth={0.6}
            />
          </g>
        )}

        {/* §BK-6 Battle Veteran Wound Scars */}
        {scarLines.map((line, i) => (
          <g key={i}>
            <line x1={line.x1} y1={line.y1} x2={line.x2} y2={line.y2} stroke="#0f172a" strokeWidth={1.2} strokeLinecap="round" />
            <line x1={line.x1 * 0.95 + cx * 0.05} y1={line.y1 * 0.95 + cy * 0.05} x2={line.x2 * 0.95 + cx * 0.05} y2={line.y2 * 0.95 + cy * 0.05} stroke="#991b1b" strokeWidth={0.6} strokeLinecap="round" />
          </g>
        ))}

        {scarsCount > 0 && size >= 60 && (
          <text x={cx - 24} y={cy + 24} fontSize={6.5} fill="#ff7b72" fontWeight={700}>⚔{scarsCount}</text>
        )}
        {/* always show glyph centered for line & priest too, but nucleus already handles */}
        {glyph && !hasNucleus && (
          <text
            x={cx}
            y={cy + 1}
            textAnchor="middle"
            dominantBaseline="middle"
            fontSize={r * 0.85}
            fill="#e6edf3"
            style={{ fontFamily: 'ui-monospace, monospace' }}
          >
            {glyph}
          </text>
        )}
        {hasNucleus && isPriest && glyph && (
          <text x={cx} y={cy + 1} textAnchor="middle" dominantBaseline="middle" fontSize={r * 0.42} fill="#e6edf3" style={{ fontFamily: 'ui-monospace, monospace' }}>
            {glyph}
          </text>
        )}
        {infected && <circle cx={cx + 22} cy={cy - 22} r={4} fill="#3fb950" stroke="#0d1117" strokeWidth={1} />}
        {status === 'starving' && <circle cx={cx + 22} cy={cy - 22} r={4} fill="#f85149" stroke="#0d1117" strokeWidth={1} />}
        {status === 'hungry' && <circle cx={cx + 22} cy={cy - 22} r={4} fill="#d29922" stroke="#0d1117" strokeWidth={1} />}
        {chill >= 12 && <circle cx={cx - 22} cy={cy - 22} r={4} fill="#79c0ff" stroke="#0d1117" strokeWidth={1} />}
        {archetype && size >= 60 && (
          <text x={cx} y={archetype ? 68 : 72} textAnchor="middle" fontSize={6.5} fill={archetype==='Apex Hunter'?'#ff7b72':archetype==='Nocturnal Forager'?'#79c0ff':archetype==='Granary Courier'?'#3fb950':archetype==='Sentry Guard'?'#d2a8ff':'#8b949e'} style={{ fontWeight: 700 }}>
            {archetype==='Apex Hunter'?'⚔ Apex Hunter':archetype==='Nocturnal Forager'?'🌙 Nocturnal':archetype==='Granary Courier'?'🧺 Courier':archetype==='Sentry Guard'?'🛡️ Sentry':archetype}
          </text>
        )}
        {trait && size >= 60 && !archetype && (
          <text x={cx} y={72} textAnchor="middle" fontSize={7} fill="#8b949e">
            {trait === 'greedy' ? '⬔ greedy' : trait === 'peaceful' ? '◯ peaceful' : trait === 'paranoid' ? '⬥ paranoid' : trait === 'bold' ? '▲ bold' : trait}
          </text>
        )}
        {trait && archetype && size >= 60 && (
          <text x={cx} y={74} textAnchor="middle" fontSize={5.5} fill="#6e7681">
            {trait}
          </text>
        )}
      </svg>
    </div>
  )
}

export default CreatureAvatar
