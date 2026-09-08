
export interface EpochDef {
  name: string
  icon: string
  color: string
  startDay: number
  endDay: number
}

interface Props {
  totalDays: number
  currentDay: number
  selectedDay: number | null
  onSelectDay: (day: number) => void
  compact?: boolean
}

export function computeEpochs(maxDay: number): EpochDef[] {
  const epochs: EpochDef[] = []
  if (maxDay < 10) {
    epochs.push({ name: 'Genesis Era', icon: '🌱', color: '#2ea043', startDay: 0, endDay: maxDay })
    return epochs
  }

  const milestones = [
    { name: 'Genesis Era', icon: '🌱', color: '#2ea043', start: 0, end: 9 },
    { name: 'Expansion & Faith', icon: '🏛️', color: '#1f6feb', start: 10, end: 24 },
    { name: 'Age of Strife', icon: '⚔️', color: '#f85149', start: 25, end: 44 },
    { name: 'Plague Era', icon: '☣️', color: '#a371f7', start: 45, end: 64 },
    { name: 'Ice Age', icon: '❄️', color: '#58a6ff', start: 65, end: 89 },
    { name: 'Renaissance', icon: '🌟', color: '#d29922', start: 90, end: Infinity },
  ]

  for (const m of milestones) {
    if (m.start <= maxDay) {
      epochs.push({
        name: m.name,
        icon: m.icon,
        color: m.color,
        startDay: m.start,
        endDay: Math.min(m.end, maxDay),
      })
    }
  }
  return epochs
}

export default function EpochBar({
  totalDays,
  currentDay,
  selectedDay,
  onSelectDay,
  compact = false,
}: Props) {
  const maxDay = Math.max(1, totalDays)
  const epochs = computeEpochs(maxDay)

  return (
    <div
      className="history-epoch-container"
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 6,
        background: '#161b22',
        border: '1px solid #30363d',
        borderRadius: 8,
        padding: compact ? '6px 8px' : '8px 12px',
        marginBottom: 10,
      }}
    >
      {/* BM-8: Horizontal Epoch Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 11, color: '#8b949e' }}>
        <span style={{ fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5 }}>
          ⏳ Epochs of History (Days 0–{maxDay})
        </span>
        <span>
          Current: <b>Day {currentDay}</b> {selectedDay !== null && `· Selected: Day ${selectedDay}`}
        </span>
      </div>

      <div
        style={{
          display: 'flex',
          width: '100%',
          height: compact ? 20 : 26,
          borderRadius: 6,
          overflow: 'hidden',
          background: '#0d1117',
          border: '1px solid #21262d',
          position: 'relative',
        }}
      >
        {epochs.map((ep) => {
          const span = ep.endDay - ep.startDay + 1
          const pct = Math.max(5, (span / (maxDay + 1)) * 100)
          const isSelected = selectedDay !== null && selectedDay >= ep.startDay && selectedDay <= ep.endDay

          return (
            <button
              key={ep.name}
              type="button"
              onClick={() => onSelectDay(ep.startDay)}
              title={`${ep.name} (Days ${ep.startDay}–${ep.endDay === Infinity ? '+' : ep.endDay})`}
              style={{
                width: `${pct}%`,
                background: ep.color,
                border: isSelected ? '2px solid #fff' : 'none',
                opacity: isSelected ? 1 : 0.85,
                color: '#fff',
                fontSize: compact ? 9.5 : 10.5,
                fontWeight: 700,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 4,
                cursor: 'pointer',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                padding: '0 4px',
                transition: 'opacity 0.2s, transform 0.1s',
              }}
            >
              <span>{ep.icon}</span>
              {!compact && <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{ep.name}</span>}
            </button>
          )
        })}
      </div>

      {/* BM-10: Day Navigator Scrubber Slider */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 2 }}>
        <span style={{ fontSize: 11, color: '#8b949e', flex: 'none' }}>Day 0</span>
        <input
          type="range"
          min={0}
          max={maxDay}
          value={selectedDay ?? currentDay}
          onChange={(e) => onSelectDay(parseInt(e.target.value, 10))}
          style={{
            flex: 1,
            accentColor: '#388bfd',
            cursor: 'pointer',
            height: 6,
          }}
          title={`Scrub to Day ${selectedDay ?? currentDay}`}
        />
        <span style={{ fontSize: 11, color: '#8b949e', flex: 'none' }}>Day {maxDay}</span>
        <button
          type="button"
          className="chip"
          onClick={() => onSelectDay(currentDay)}
          style={{
            fontSize: 10.5,
            padding: '2px 6px',
            background: '#21262d',
            border: '1px solid #30363d',
            color: '#58a6ff',
            cursor: 'pointer',
            flex: 'none',
          }}
        >
          Latest
        </button>
      </div>
    </div>
  )
}
