import { useState } from 'react'
import type { DayRecord } from './WorldHistoryModal'
import { useI18n } from '../i18n'

interface Props {
  dayRecords: DayRecord[]
  selectedDay: number | null
  onSelectDay: (day: number) => void
  currentPopulation?: number
}

export default function PopulationSparkline({
  dayRecords,
  selectedDay,
  onSelectDay,
  currentPopulation,
}: Props) {
  const { t } = useI18n()
  const [hoverIdx, setHoverIdx] = useState<number | null>(null)

  if (dayRecords.length === 0) return null

  // Ensure chronological order (Day 0, Day 1, ...)
  const chronological = [...dayRecords].sort((a, b) => a.day - b.day)
  const n = chronological.length

  // Build demographic activity metric per day
  // (casualties, outbreaks, wars, disasters)
  const values = chronological.map((d) => d.totalCasualties * 2 + d.wars.length * 3 + d.outbreaks.length * 2)
  const maxVal = Math.max(5, ...values)

  const width = 600
  const height = 48
  const pad = 4

  const points = chronological.map((_, i) => {
    const x = n > 1 ? pad + (i / (n - 1)) * (width - pad * 2) : width / 2
    const y = height - pad - (values[i] / maxVal) * (height - pad * 2)
    return { x, y }
  })

  const pathD = points.reduce((acc, pt, i) => {
    return i === 0 ? `M ${pt.x} ${pt.y}` : `${acc} L ${pt.x} ${pt.y}`
  }, '')

  const areaD = `${pathD} L ${points[points.length - 1].x} ${height} L ${points[0].x} ${height} Z`

  const activeDay = hoverIdx !== null ? chronological[hoverIdx] : selectedDay !== null ? chronological.find(d => d.day === selectedDay) : null

  return (
    <div
      className="history-sparkline-card"
      style={{
        background: '#161b22',
        border: '1px solid #30363d',
        borderRadius: 8,
        padding: '6px 12px',
        marginBottom: 10,
        position: 'relative',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 11, color: '#8b949e', marginBottom: 2 }}>
        <span style={{ fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5 }}>
          {t('history.sparkline.title')}
        </span>
        {activeDay ? (
          <span style={{ color: '#58a6ff' }}>
            {t('history.sparkline.stats', {
              day: activeDay.day,
              dead: activeDay.totalCasualties,
              wars: activeDay.wars.length,
              plagues: activeDay.outbreaks.length,
            })}
          </span>
        ) : (
          <span>{currentPopulation !== undefined ? t('history.sparkline.aliveCurrently', { count: currentPopulation }) : t('history.sparkline.hoverHint')}</span>
        )}
      </div>

      <svg
        viewBox={`0 0 ${width} ${height}`}
        style={{ width: '100%', height: 48, overflow: 'visible', cursor: 'pointer' }}
        onMouseLeave={() => setHoverIdx(null)}
      >
        <defs>
          <linearGradient id="sparklineGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#f85149" stopOpacity="0.4" />
            <stop offset="100%" stopColor="#f85149" stopOpacity="0.0" />
          </linearGradient>
        </defs>

        {/* Background shaded area */}
        <path d={areaD} fill="url(#sparklineGrad)" />

        {/* Line */}
        <path d={pathD} fill="none" stroke="#f85149" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />

        {/* Data points */}
        {points.map((pt, idx) => {
          const d = chronological[idx]
          const isSelected = selectedDay === d.day
          const isHovered = hoverIdx === idx
          const hasAction = values[idx] > 0

          return (
            <circle
              key={d.day}
              cx={pt.x}
              cy={pt.y}
              r={isSelected || isHovered ? 5 : hasAction ? 2.5 : 1}
              fill={isSelected ? '#58a6ff' : isHovered ? '#fff' : hasAction ? '#f85149' : '#30363d'}
              stroke={isSelected ? '#fff' : 'none'}
              strokeWidth={1.5}
              onMouseEnter={() => setHoverIdx(idx)}
              onClick={() => onSelectDay(d.day)}
            />
          )
        })}
      </svg>
    </div>
  )
}
