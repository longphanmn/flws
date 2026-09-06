import { useState } from 'react'
import Sparkline from './Sparkline'

interface Props {
  title: string
  value: string | number
  subvalue?: string
  hint?: string
  status?: 'healthy' | 'warning' | 'critical' | 'neutral'
  statusLabel?: string
  sparklineData?: number[]
  sparklineColor?: string
  sparklineHeight?: number
  icon?: string
  unit?: string
  style?: React.CSSProperties
}

const STATUS_THEMES = {
  healthy: { bg: '#162b1a', border: '#238636', text: '#3fb950', badge: '🟢' },
  warning: { bg: '#2b2316', border: '#9e6a03', text: '#d29922', badge: '🟡' },
  critical: { bg: '#331919', border: '#da3633', text: '#f85149', badge: '🔴' },
  neutral: { bg: '#161b22', border: '#30363d', text: '#8b949e', badge: '⚪' },
}

export default function MetricCard({
  title,
  value,
  subvalue,
  hint,
  status = 'neutral',
  statusLabel,
  sparklineData,
  sparklineColor,
  sparklineHeight = 36,
  icon,
  unit,
  style,
}: Props) {
  const [showTooltip, setShowTooltip] = useState(false)
  const theme = STATUS_THEMES[status] || STATUS_THEMES.neutral
  const lineColor = sparklineColor || theme.text

  return (
    <div
      style={{
        background: theme.bg,
        border: `1px solid ${theme.border}`,
        borderRadius: 8,
        padding: '8px 10px',
        display: 'flex',
        flexDirection: 'column',
        gap: 6,
        position: 'relative',
        minWidth: 0,
        ...style,
      }}
    >
      {/* Header with Title & Tooltip Trigger */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0, flex: 1 }}>
          {icon && <span style={{ fontSize: 13, flexShrink: 0 }}>{icon}</span>}
          <span
            style={{
              fontSize: 10,
              fontWeight: 600,
              color: '#c9d1d9',
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              minWidth: 0,
            }}
          >
            {title}
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0 }}>
          {statusLabel && (
            <span
              style={{
                fontSize: 9,
                color: theme.text,
                fontWeight: 700,
                background: 'rgba(0,0,0,0.3)',
                padding: '1px 5px',
                borderRadius: 4,
                border: `1px solid ${theme.border}`,
                whiteSpace: 'nowrap',
              }}
            >
              {statusLabel}
            </span>
          )}
          {hint && (
            <button
              type="button"
              onClick={() => setShowTooltip((v) => !v)}
              onMouseEnter={() => setShowTooltip(true)}
              onMouseLeave={() => setShowTooltip(false)}
              aria-label="Info"
              style={{
                background: 'transparent',
                border: 'none',
                color: showTooltip ? '#58a6ff' : '#8b949e',
                cursor: 'pointer',
                padding: 0,
                fontSize: 11,
                lineHeight: 1,
                flexShrink: 0,
              }}
            >
              ⓘ
            </button>
          )}
        </div>
      </div>

      {/* Tooltip Popover */}
      {showTooltip && hint && (
        <div
          style={{
            position: 'absolute',
            top: 28,
            left: 8,
            right: 8,
            zIndex: 50,
            background: '#0d1117',
            border: '1px solid #58a6ff',
            borderRadius: 6,
            padding: '6px 8px',
            fontSize: 10,
            lineHeight: 1.4,
            color: '#e6edf3',
            boxShadow: '0 6px 16px rgba(0,0,0,0.6)',
          }}
        >
          {hint}
        </div>
      )}

      {/* Value Row */}
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 6, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 4, minWidth: 0, flexShrink: 0 }}>
          <span style={{ fontSize: 18, fontWeight: 700, color: '#f0f6fc', lineHeight: 1.1 }}>{value}</span>
          {unit && <span style={{ fontSize: 11, color: '#8b949e' }}>{unit}</span>}
        </div>
        {subvalue && (
          <span
            style={{
              fontSize: 10,
              color: '#8b949e',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              minWidth: 0,
              textAlign: 'right',
            }}
          >
            {subvalue}
          </span>
        )}
      </div>

      {/* Optional Embedded Sparkline */}
      {sparklineData && sparklineData.length > 1 && (
        <Sparkline
          data={sparklineData}
          color={lineColor}
          height={sparklineHeight}
          unit={unit}
          showLast={false}
        />
      )}
    </div>
  )
}
