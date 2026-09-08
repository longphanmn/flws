
import { useI18n } from '../i18n'

interface WarDetail {
  aName: string
  bName: string
  battles: number
  casualties: number
}

interface Props {
  wars: WarDetail[]
}

export default function WarArcGraph({ wars }: Props) {
  const { t } = useI18n()
  if (wars.length === 0) return null

  // Extract unique clans
  const clanSet = new Set<string>()
  for (const w of wars) {
    clanSet.add(w.aName)
    clanSet.add(w.bName)
  }
  const clanList = Array.from(clanSet)
  if (clanList.length < 2) return null

  const width = 500
  const height = 90
  const nodeY = 65
  const pad = 40
  const step = (width - pad * 2) / Math.max(1, clanList.length - 1)

  const clanPos: Record<string, number> = {}
  clanList.forEach((c, idx) => {
    clanPos[c] = pad + idx * step
  })

  return (
    <div
      style={{
        background: '#0d1117',
        border: '1px solid #30363d',
        borderRadius: 8,
        padding: '8px 12px',
        margin: '6px 0',
      }}
    >
      <div style={{ fontSize: 10.5, color: '#8b949e', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 4 }}>
        {t('history.warArc.title')}
      </div>

      <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', height: 90, overflow: 'visible' }}>
        {/* Curved war connectors */}
        {wars.map((w, idx) => {
          const x1 = clanPos[w.aName] ?? pad
          const x2 = clanPos[w.bName] ?? (width - pad)
          const midX = (x1 + x2) / 2
          const dist = Math.abs(x1 - x2)
          const arcHeight = Math.min(50, Math.max(20, dist * 0.35))
          const midY = nodeY - arcHeight
          const strokeWidth = Math.min(5, Math.max(1.5, 1 + w.casualties * 0.8))

          return (
            <g key={idx}>
              <path
                d={`M ${x1} ${nodeY} Q ${midX} ${midY} ${x2} ${nodeY}`}
                fill="none"
                stroke="#f85149"
                strokeWidth={strokeWidth}
                opacity={0.8}
              />
              <text
                x={midX}
                y={midY - 4}
                fill="#ff7b72"
                fontSize={9}
                fontWeight={700}
                textAnchor="middle"
              >
                {w.battles} ⚔ ({w.casualties} 💀)
              </text>
            </g>
          )
        })}

        {/* Clan nodes */}
        {clanList.map((c) => {
          const cx = clanPos[c]
          return (
            <g key={c}>
              <circle cx={cx} cy={nodeY} r={6} fill="#238636" stroke="#fff" strokeWidth={1.5} />
              <text
                x={cx}
                y={nodeY + 16}
                fill="#c9d1d9"
                fontSize={9.5}
                fontWeight={600}
                textAnchor="middle"
              >
                {c.length > 14 ? `${c.slice(0, 12)}…` : c}
              </text>
            </g>
          )
        })}
      </svg>
    </div>
  )
}
